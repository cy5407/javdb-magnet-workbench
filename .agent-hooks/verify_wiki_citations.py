#!/usr/bin/env python3
"""檢查 .agents/wiki/patterns/*.md 裡的原始碼引用是否還對得上現場程式碼。

用法：
    python scripts/verify_wiki_citations.py [--wiki DIR] [--root DIR]

存在理由：Wiki 的 pattern 檔宣稱自己引用的是 Verbatim Code，但散文不會在
程式碼被重構時自己報錯。2026-09-01 的稽核就抓到 `_ok`/`_err` 的「逐字引用」
其實是憑記憶重寫的簽名（`payload` vs `extra`、`internal` 是否可省略），
呼叫端照著寫會誤判錯誤信封形狀。這支腳本把那類漂移變成紅燈。

認三種引用寫法：
- `path:12`、`path:12-34`——路徑相對於 --root。
- [文字](../../path:12)——路徑相對於該 pattern 檔自己。
- `repo@commit:path:12`——證據在另一個庫，repo 是 --root 的同層目錄，
  內容以 `git show <commit>:<path>` 取，所以引用釘在 commit 上而不是「現在」。

檢查三件事：
1. **檔案存在**：每個引用指向的檔案要在。外部庫在這台不存在時回報
   `external_unverifiable`，與「引用錯了」分開——前者換台機器可能驗得過。
2. **行號在範圍內**：引用的行號不能超過檔案長度。
3. **片段仍存在**：fenced code block 去除縮排後必須連續存在於單一引用範圍內。

刻意寬鬆的地方（避免假警報淹沒真訊號）：
- 不同區段需拆成不同 code block，不可用各行分散存在推論整段是真實引用。
- 沒有帶行號的 inline code（如 `sidecar.py`、`SKILL.md`）不視為引用。
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple, Optional

_EXT = r"(?:py|rs|ts|tsx|svelte|md|toml|json|mjs|js|go|ps1|sh|txt|yaml|yml)"

# 兩種寫法都要認。
#
# 1. 反引號 `path:12` 或 `path:12-34`，路徑相對於 --root。
# 2. markdown 連結 [任意文字](path:12)，路徑相對於**該 pattern 檔自己**。
#
# 只認第 1 種的代價已經付過：2026-09-05 兩篇 pattern 共 11 筆連結式引用因另一台
# 的改動而全部漂移，閘門回報「0 個問題」——見 wiki/skill-impact.md 的
# citation-gate-covers-markdown-links 那一列。閘門報 0 問題與引用全錯可以並存。
# 2026-09-22 量到的第二批：13 筆裸行號引用全部指到空行、`}`、別人的變數。
#
# 副檔名白名單避免把 `rd_send_magnet:pending` 這類非路徑字串誤判為引用。
CITATION_RE = re.compile(rf"`([^`\n]+\.{_EXT}):(\d+)(?:-(\d+))?`")
LINK_CITATION_RE = re.compile(rf"\]\((?!https?:)([^)\s]+\.{_EXT}):(\d+)(?:-(\d+))?\)")

# 3. 外部庫 `repo@commit:path:12`。證據來自另一個 repo 時用這種寫法。
#
# 為什麼要有第三種：pattern 是跨專案蒸餾出來的，證據本來就常在別的庫。寫成本地
# 路徑的話，閘門只能回報 missing_file——那句話讀起來像「引用是錯的」，但實測
# 2026-09-22 那五筆全部正確，只是不在這個庫。假紅燈跟假綠燈一樣糟：六筆紅燈掛了
# 好幾週沒人動，閘門就變成背景雜訊。
#
# commit 是必填。少了它，「證據」只是「那個庫現在長這樣」，明天就不成立；
# 釘住 commit 之後這條引用才是可以重驗的事實。
EXTERNAL_RE = re.compile(
    rf"`([A-Za-z0-9._-]+)@([0-9a-f]{{7,40}}):([^`\n]+\.{_EXT}):(\d+)(?:-(\d+))?`")
FENCE_RE = re.compile(r"^\s*```")

# 引用與 code block 之間允許的距離（行）。Wiki 的寫法一律是引用行緊接 fence，
# 放寬到 3 行足以容納括號換行，又不會誤抓上一段落的引用。
LOOKBACK_LINES = 3


class Citation(NamedTuple):
    path: str
    start: int
    end: int
    # 連結式引用的路徑基準是該文件自己的目錄，不是 --root。兩種基準都試，
    # 因為兩種寫法在同一份 pattern 裡混用是常態。
    doc_relative: bool = False
    # 外部庫引用：repo 名（與 --root 同層的目錄）與釘住的 commit。
    repo: Optional[str] = None
    commit: Optional[str] = None


class Finding(NamedTuple):
    doc: Path
    line: int
    kind: str
    message: str


def parse_citations(text: str) -> list[Citation]:
    out = []
    # 外部庫的寫法整段也符合本地反引號的形狀（`repo@commit:path:12` 裡的
    # `…:path:12` 會被 CITATION_RE 吃掉），所以先抽掉再掃本地的，否則同一筆會被
    # 算成兩筆，而且其中一筆帶著解不開的路徑變成假 missing_file。
    for m in EXTERNAL_RE.finditer(text):
        start = int(m.group(4))
        end = int(m.group(5)) if m.group(5) else start
        out.append(Citation(m.group(3), start, end, False, m.group(1), m.group(2)))
    local_text = EXTERNAL_RE.sub("", text)
    for pattern, doc_relative in ((CITATION_RE, False), (LINK_CITATION_RE, True)):
        for m in pattern.finditer(local_text):
            start = int(m.group(2))
            end = int(m.group(3)) if m.group(3) else start
            out.append(Citation(m.group(1), start, end, doc_relative))
    return out


def _read_lines(root: Path, base: Path, rel: str) -> Optional[list[str]]:
    """把引用路徑解成檔案內容。`base` 是該筆引用的解析基準。

    解出來的路徑仍必須落在 root 底下——連結式引用寫的是 `../../scripts/...`，
    正常情況解完還在庫內；解到庫外的一律當作查不到，不去讀庫外的檔案。
    """
    target = (base / rel).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError:
        return None
    if not target.is_file():
        return None
    return target.read_text(encoding="utf-8").splitlines()


def _read_external(root: Path, cit: Citation) -> tuple[Optional[list[str]], Optional[str]]:
    """讀外部庫在指定 commit 的檔案內容。回傳 (內容, 不可驗的理由)。

    「這台沒有那個庫」與「引用錯了」是兩件事，必須分開回報：前者在另一台機器上
    可能驗得過，後者不管在哪台都是錯的。混成同一種 finding，就會有人為了讓閘門
    變綠而去改一條其實正確的引用。
    """
    repo = (root.parent / cit.repo).resolve()
    if not (repo / ".git").exists():
        return None, f"找不到外部庫 {cit.repo}（找的位置：{repo}）"
    proc = subprocess.run(
        ["git", "-C", str(repo), "show", f"{cit.commit}:{cit.path}"],
        capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        detail = proc.stderr.strip().splitlines()
        return None, (f"{cit.repo} 取不到 {cit.commit}:{cit.path}"
                      f"（{detail[0] if detail else 'git show 失敗'}）")
    return proc.stdout.splitlines(), None


def check_document(doc: Path, root: Path) -> list[Finding]:
    findings: list[Finding] = []
    lines = doc.read_text(encoding="utf-8").splitlines()
    sources: dict[tuple, Optional[list[str]]] = {}
    unverifiable: dict[tuple, str] = {}

    def source_of(cit: Citation) -> Optional[list[str]]:
        key = (cit.repo, cit.commit, cit.path, cit.doc_relative)
        if key not in sources:
            if cit.repo:
                sources[key], reason = _read_external(root, cit)
                if reason:
                    unverifiable[key] = reason
            else:
                base = doc.parent if cit.doc_relative else root
                sources[key] = _read_lines(root, base, cit.path)
        return sources[key]

    # --- 檢查 1 與 2：所有帶行號的引用 -------------------------------------
    for lineno, text in enumerate(lines, 1):
        for cit in parse_citations(text):
            src = source_of(cit)
            if src is None:
                key = (cit.repo, cit.commit, cit.path, cit.doc_relative)
                if key in unverifiable:
                    findings.append(Finding(doc, lineno, "external_unverifiable",
                                            unverifiable[key]))
                    continue
                findings.append(Finding(doc, lineno, "missing_file",
                                        f"引用的檔案不存在：{cit.path}"))
                continue
            if cit.start < 1 or cit.end < cit.start or cit.end > len(src):
                where = f"{cit.repo}@{cit.commit}:" if cit.repo else ""
                findings.append(Finding(
                    doc, lineno, "line_out_of_range",
                    f"{where}{cit.path}:{cit.start}-{cit.end} 超出檔案長度（{len(src)} 行）"))

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
        cits = [c for c in parse_citations(preamble) if source_of(c) is not None]
        if not cits:
            continue

        body_exact = [ln.strip() for ln in block]
        contiguous = False
        for cit in cits:
            source = [ln.strip() for ln in (source_of(cit) or [])[cit.start - 1:cit.end]]
            if body_exact and any(source[n:n + len(body_exact)] == body_exact
                                  for n in range(len(source) - len(body_exact) + 1)):
                contiguous = True
        if not contiguous:
            findings.append(Finding(doc, fence_line, "snippet_not_contiguous",
                                    "片段必須完整連續存在於單一引用範圍；分段引用請拆開區塊。"))
    return findings


def resolve_wiki(root: Path, explicit: Optional[str]) -> tuple[Optional[Path], list[Path]]:
    """決定要檢查哪個 pattern 目錄。

    寫死單一預設值的代價已經付過：預設 `.agents/wiki/patterns` 是**專案端**裝配後的
    形狀，中央庫自己的 wiki 放在 `wiki/patterns`，於是這支閘門對中央庫的 pattern
    一份都沒檢查過，要人記得手動補 --wiki 才會動。改為依序探測兩種已知形狀。

    回傳 (命中的目錄或 None, 探測過的候選清單)。
    """
    if explicit:
        path = Path(explicit)
        return (path if path.is_absolute() else root / path), []

    candidates = [root / "wiki" / "patterns", root / ".agents" / "wiki" / "patterns"]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate, candidates
    return None, candidates


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="專案根目錄（引用路徑的基準）")
    parser.add_argument("--wiki", default=None,
                        help="pattern 檔所在目錄（省略時依序探測 wiki/patterns、"
                             ".agents/wiki/patterns）")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    wiki, candidates = resolve_wiki(root, args.wiki)
    # 找不到目錄一律 exit 2（fail-closed）：呼叫端不能把「沒東西可檢查」讀成「檢查通過」。
    if wiki is None:
        tried = "、".join(str(c) for c in candidates)
        print(f"找不到 wiki 目錄，已嘗試：{tried}", file=sys.stderr)
        return 2
    if not wiki.is_dir():
        print(f"找不到 wiki 目錄：{wiki}", file=sys.stderr)
        return 2

    docs = sorted(wiki.glob("*.md"))
    findings: list[Finding] = []
    uncovered = []
    citations = 0
    for doc in docs:
        count = len(parse_citations(doc.read_text(encoding="utf-8")))
        citations += count
        if not count:
            uncovered.append(doc.name)
        findings.extend(check_document(doc, root))

    for f in findings:
        rel = f.doc.relative_to(root) if f.doc.is_relative_to(root) else f.doc
        print(f"{rel}:{f.line}: [{f.kind}] {f.message}")

    print(f"\n檢查 {len(docs)} 份 pattern、{citations} 個引用，發現 {len(findings)} 個問題。")
    if uncovered or not docs:
        print(f"NOT_VERIFIED: {', '.join(uncovered) or 'no patterns'}")
    return 1 if findings else (2 if uncovered or not docs else 0)


if __name__ == "__main__":
    sys.exit(main())
