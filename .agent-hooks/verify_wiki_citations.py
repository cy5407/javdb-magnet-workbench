#!/usr/bin/env python3
"""檢查 .agents/wiki/patterns/*.md 裡的原始碼引用是否還對得上現場程式碼。

用法：
    python scripts/verify_wiki_citations.py [--wiki DIR] [--root DIR]

存在理由：Wiki 的 pattern 檔宣稱自己引用的是 Verbatim Code，但散文不會在
程式碼被重構時自己報錯。2026-09-01 的稽核就抓到 `_ok`/`_err` 的「逐字引用」
其實是憑記憶重寫的簽名（`payload` vs `extra`、`internal` 是否可省略），
呼叫端照著寫會誤判錯誤信封形狀。這支腳本把那類漂移變成紅燈。

檢查三件事：
1. **檔案存在**：每個 `path:line` 或 `path:start-end` 引用指向的檔案要在。
2. **行號在範圍內**：引用的行號不能超過檔案長度。
3. **片段仍存在**：緊接在引用之後的 fenced code block，每一行（去除縮排後）
   都要能在被引用的檔案裡找到；區塊第一行的實際行號要落在引用的行號範圍內。

刻意寬鬆的地方（避免假警報淹沒真訊號）：
- 比對以「去縮排的單行存在性」為準，不要求整段連續。Wiki 為了可讀性會把
  method 的縮排拉平，也會把同一檔案的兩個區段併進同一個 code block。
- 沒有帶行號的 inline code（如 `sidecar.py`、`SKILL.md`）不視為引用。
"""

import argparse
import re
import sys
from pathlib import Path
from typing import NamedTuple, Optional

# `path:12` 或 `path:12-34`；副檔名白名單避免把 `rd_send_magnet:pending` 這類
# 非路徑字串誤判為引用。
CITATION_RE = re.compile(
    r"`([\w./\\-]+\.(?:py|rs|ts|tsx|svelte|md|toml|json)):(\d+)(?:-(\d+))?`"
)
FENCE_RE = re.compile(r"^\s*```")

# 引用與 code block 之間允許的距離（行）。Wiki 的寫法一律是引用行緊接 fence，
# 放寬到 3 行足以容納括號換行，又不會誤抓上一段落的引用。
LOOKBACK_LINES = 3


class Citation(NamedTuple):
    path: str
    start: int
    end: int


class Finding(NamedTuple):
    doc: Path
    line: int
    kind: str
    message: str


def parse_citations(text: str) -> list[Citation]:
    out = []
    for m in CITATION_RE.finditer(text):
        start = int(m.group(2))
        end = int(m.group(3)) if m.group(3) else start
        out.append(Citation(m.group(1), start, end))
    return out


def _read_lines(root: Path, rel: str) -> Optional[list[str]]:
    target = (root / rel).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError:
        return None
    if not target.is_file():
        return None
    return target.read_text(encoding="utf-8").splitlines()


def _locate(needle: str, lines: list[str]) -> list[int]:
    """回傳 needle（已 strip）出現的所有 1-based 行號。"""
    return [i for i, line in enumerate(lines, 1) if line.strip() == needle]


def check_document(doc: Path, root: Path) -> list[Finding]:
    findings: list[Finding] = []
    lines = doc.read_text(encoding="utf-8").splitlines()
    sources: dict[str, Optional[list[str]]] = {}

    def source_of(rel: str) -> Optional[list[str]]:
        if rel not in sources:
            sources[rel] = _read_lines(root, rel)
        return sources[rel]

    # --- 檢查 1 與 2：所有帶行號的引用 -------------------------------------
    for lineno, text in enumerate(lines, 1):
        for cit in parse_citations(text):
            src = source_of(cit.path)
            if src is None:
                findings.append(Finding(doc, lineno, "missing_file",
                                        f"引用的檔案不存在：{cit.path}"))
                continue
            if cit.end > len(src):
                findings.append(Finding(
                    doc, lineno, "line_out_of_range",
                    f"{cit.path}:{cit.start}-{cit.end} 超出檔案長度（{len(src)} 行）"))

    # --- 檢查 3：code block 內容 -------------------------------------------
    i = 0
    while i < len(lines):
        if not FENCE_RE.match(lines[i]):
            i += 1
            continue
        fence_line = i + 1
        block: list[str] = []
        i += 1
        while i < len(lines) and not FENCE_RE.match(lines[i]):
            block.append(lines[i])
            i += 1
        i += 1  # 跳過結尾 fence

        preamble = "\n".join(lines[max(0, fence_line - 1 - LOOKBACK_LINES):fence_line - 1])
        cits = [c for c in parse_citations(preamble) if source_of(c.path) is not None]
        if not cits:
            continue

        pool: list[str] = []
        for cit in cits:
            pool.extend(source_of(cit.path) or [])

        body = [ln.strip() for ln in block if ln.strip()]
        missing = [ln for ln in body if not _locate(ln, pool)]
        if missing:
            shown = "；".join(missing[:3])
            more = f"（另有 {len(missing) - 3} 行）" if len(missing) > 3 else ""
            findings.append(Finding(
                doc, fence_line, "snippet_not_found",
                f"引用 {cits[0].path} 的區塊有 {len(missing)} 行在原始碼找不到：{shown}{more}"))
            continue

        if not body:
            continue
        anchor = body[0]
        hits: list[tuple[str, int]] = []
        for cit in cits:
            src = source_of(cit.path) or []
            hits.extend((cit.path, n) for n in _locate(anchor, src))
        in_range = any(
            path == cit.path and cit.start <= n <= cit.end
            for path, n in hits
            for cit in cits
        )
        if not in_range:
            actual = "、".join(f"{p}:{n}" for p, n in hits[:3]) or "找不到"
            cited = "、".join(f"{c.path}:{c.start}-{c.end}" for c in cits)
            findings.append(Finding(
                doc, fence_line, "line_drift",
                f"區塊首行不在引用的行號範圍內：引用 {cited}，實際位於 {actual}"))

    return findings


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="專案根目錄（引用路徑的基準）")
    parser.add_argument("--wiki", default=".agents/wiki/patterns",
                        help="pattern 檔所在目錄")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    wiki = (root / args.wiki) if not Path(args.wiki).is_absolute() else Path(args.wiki)
    if not wiki.is_dir():
        print(f"找不到 wiki 目錄：{wiki}", file=sys.stderr)
        return 2

    docs = sorted(wiki.glob("*.md"))
    findings: list[Finding] = []
    for doc in docs:
        findings.extend(check_document(doc, root))

    for f in findings:
        rel = f.doc.relative_to(root) if f.doc.is_relative_to(root) else f.doc
        print(f"{rel}:{f.line}: [{f.kind}] {f.message}")

    print(f"\n檢查 {len(docs)} 份 pattern，發現 {len(findings)} 個問題。")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
