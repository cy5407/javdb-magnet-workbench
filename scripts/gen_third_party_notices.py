"""產生 release 用的 THIRD_PARTY_NOTICES.txt。

MIT／Apache／BSD 這類授權要求散佈二進位檔時附上原作者的版權與授權聲明，
所以 portable zip 必須帶這份檔案。內容只收「會被打包進 exe 的東西」：

- Python：sidecar 執行期依賴（requirements-sidecar.txt 中 PyInstaller 以外的
  套件及其 transitive 依賴）、PyInstaller bootloader、CPython 本身。
- Rust：`cargo metadata` 中 Windows target 的一般依賴（不含 dev／build 依賴）。
- 前端：`app/package.json` 的 dependencies 與 Svelte runtime，及其依賴。

授權全文從各套件自己附的檔案讀出，相同全文只印一次。找不到全文的套件仍
列出 SPDX 授權名稱與來源網址。

用法（在 repo 根目錄，用 sidecar 打包所用的 venv 執行）：
    python scripts/gen_third_party_notices.py <輸出檔>
"""

from __future__ import annotations

import importlib.metadata as md
import json
import re
import subprocess  # nosec B404 — fixed argv, no user input
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = REPO_ROOT / "requirements-sidecar.txt"
APP_DIR = REPO_ROOT / "app"
TAURI_DIR = APP_DIR / "src-tauri"
WINDOWS_TARGET = "x86_64-pc-windows-msvc"

# 只在打包期使用、不會出現在 sidecar.exe 執行期的套件。PyInstaller 本身另以
# bootloader 條目列出。
BUILD_ONLY_PY = {"pyinstaller", "pyinstaller-hooks-contrib", "altgraph", "pefile",
                 "macholib", "setuptools", "pywin32-ctypes", "packaging"}
# build_sidecar.py 以 --exclude-module 排除、不會進 sidecar.exe 的套件。
EXCLUDED_PY = {"chardet"}

LICENSE_FILE_RX = re.compile(r"^(licen[cs]e|copying|notice|copyright)([-_.].*)?$", re.I)


@dataclass
class Component:
    name: str
    version: str
    license: str
    url: str = ""
    texts: list[str] = field(default_factory=list)


def _norm(name: str) -> str:
    return re.sub(r"[-_.\s]+", "-", name).lower()


def _read_texts(paths) -> list[str]:
    out = []
    for p in sorted(paths, key=lambda x: x.name.lower()):
        try:
            t = p.read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        if t:
            out.append(t)
    return out


# ---------------------------------------------------------------- Python

def _requirement_roots() -> list[str]:
    roots = []
    for line in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        roots.append(re.split(r"[=<>!~\[ ;]", line, maxsplit=1)[0])
    return roots


def _py_license(meta) -> str:
    expr = meta.get("License-Expression")
    if expr:
        return expr.strip()
    raw = (meta.get("License") or "").strip().splitlines()
    if raw and len(raw[0]) <= 80:
        return raw[0]
    classifiers = [c.split("::")[-1].strip() for c in meta.get_all("Classifier") or []
                   if c.startswith("License ::")]
    return "; ".join(classifiers) or "見授權全文"


def _py_url(meta) -> str:
    for entry in meta.get_all("Project-URL") or []:
        label, _, url = entry.partition(",")
        if label.strip().lower() in ("source", "homepage", "repository", "source code"):
            return url.strip()
    return (meta.get("Home-page") or "").strip()


def _py_license_texts(dist) -> list[str]:
    files = [f for f in dist.files or []
             if LICENSE_FILE_RX.match(Path(str(f)).name) and ".dist-info" in str(f)]
    return _read_texts(Path(dist.locate_file(f)) for f in files)


def collect_python() -> list[Component]:
    seen: dict[str, Component] = {}

    def walk(name: str) -> None:
        key = _norm(name)
        if key in seen or key in BUILD_ONLY_PY or key in EXCLUDED_PY:
            return
        try:
            dist = md.distribution(name)
        except md.PackageNotFoundError:
            return
        meta = dist.metadata
        seen[key] = Component(meta["Name"], dist.version, _py_license(meta),
                              _py_url(meta), _py_license_texts(dist))
        for req in dist.requires or []:
            if "extra ==" in req:
                continue
            walk(re.split(r"[=<>!~\[ ;(]", req.strip(), maxsplit=1)[0])

    for root in _requirement_roots():
        walk(root)

    comps = sorted(seen.values(), key=lambda c: c.name.lower())

    try:
        pyi = md.distribution("pyinstaller")
        comps.append(Component(
            "PyInstaller bootloader", pyi.version,
            "GPL-2.0-or-later WITH Bootloader-exception",
            "https://github.com/pyinstaller/pyinstaller", _py_license_texts(pyi)))
    except md.PackageNotFoundError:
        pass

    py_license = Path(sys.base_prefix) / "LICENSE.txt"
    comps.append(Component(
        "CPython", "%d.%d.%d" % sys.version_info[:3], "PSF-2.0",
        "https://www.python.org/", _read_texts([py_license]) if py_license.exists() else []))

    for c in comps:
        if _norm(c.name) == "curl-cffi":
            c.texts.append(
                "curl_cffi 的原生模組靜態連結了 curl-impersonate 及其相依函式庫"
                "（libcurl、BoringSSL 等）。各函式庫的授權條款見\n"
                "https://github.com/lexiforest/curl-impersonate")
    return comps


# ---------------------------------------------------------------- Rust

def collect_rust() -> list[Component]:
    out = subprocess.run(  # nosec B603 B607 — fixed argv
        ["cargo", "metadata", "--format-version", "1", "--locked",
         "--filter-platform", WINDOWS_TARGET],
        cwd=TAURI_DIR, capture_output=True, text=True, encoding="utf-8", check=True,
    ).stdout
    data = json.loads(out)
    packages = {p["id"]: p for p in data["packages"]}
    nodes = {n["id"]: n for n in data["resolve"]["nodes"]}
    root = data["resolve"]["root"]

    reachable, stack = set(), [root]
    while stack:
        pid = stack.pop()
        if pid in reachable:
            continue
        reachable.add(pid)
        for dep in nodes[pid]["deps"]:
            # kind None = 一般依賴；dev／build 依賴不會進 exe。
            if any(k["kind"] is None for k in dep["dep_kinds"]):
                stack.append(dep["pkg"])

    comps = []
    for pid in reachable - {root}:
        p = packages[pid]
        crate_dir = Path(p["manifest_path"]).parent
        files = [f for f in crate_dir.iterdir() if f.is_file() and LICENSE_FILE_RX.match(f.name)]
        comps.append(Component(p["name"], p["version"],
                               p.get("license") or "見授權全文",
                               p.get("repository") or p.get("homepage") or "",
                               _read_texts(files)))
    return sorted(comps, key=lambda c: (c.name.lower(), c.version))


# ---------------------------------------------------------------- 前端

def collect_frontend() -> list[Component]:
    pkg = json.loads((APP_DIR / "package.json").read_text(encoding="utf-8"))
    roots = list(pkg.get("dependencies", {}))
    # Svelte 列在 devDependencies，但它的 runtime 會被編進前端 bundle。
    roots.append("svelte")
    modules = APP_DIR / "node_modules"
    seen: dict[str, Component] = {}

    def walk(name: str) -> None:
        if name in seen:
            return
        pdir = modules / name
        pj = pdir / "package.json"
        if not pj.exists():
            return
        j = json.loads(pj.read_text(encoding="utf-8"))
        lic = j.get("license")
        if not isinstance(lic, str):
            lic = json.dumps(lic, ensure_ascii=False) if lic else "見授權全文"
        repo = j.get("repository")
        url = repo.get("url", "") if isinstance(repo, dict) else (repo or j.get("homepage", ""))
        files = [f for f in pdir.iterdir() if f.is_file() and LICENSE_FILE_RX.match(f.name)]
        seen[name] = Component(name, j.get("version", ""), lic, url, _read_texts(files))
        for dep in j.get("dependencies", {}):
            walk(dep)

    for r in roots:
        walk(r)
    return sorted(seen.values(), key=lambda c: c.name.lower())


# ---------------------------------------------------------------- 輸出

def render(sections: list[tuple[str, list[Component]]]) -> str:
    lines = [
        "JavDBMagnet — 第三方授權聲明 / Third-Party Notices",
        "=" * 60,
        "",
        "本程式包含下列第三方元件，各元件依其原授權條款散佈。",
        "JavDBMagnet 本身的授權見同資料夾的 LICENSE.txt。",
        "",
    ]
    text_ids: dict[str, int] = {}
    text_users: dict[int, list[str]] = {}
    for title, comps in sections:
        lines += [f"## {title}（{len(comps)} 項）", ""]
        for c in comps:
            refs = []
            for t in c.texts:
                tid = text_ids.setdefault(t, len(text_ids) + 1)
                text_users.setdefault(tid, []).append(f"{c.name} {c.version}")
                refs.append(f"[{tid}]")
            ref = (" 授權全文 " + " ".join(refs)) if refs else "（套件未附授權全文，條款見來源網址）"
            url = f"  {c.url}" if c.url else ""
            lines.append(f"- {c.name} {c.version} — {c.license}{url}{ref}")
        lines.append("")
    lines += ["", "## 授權全文", ""]
    for text, tid in text_ids.items():
        users = text_users[tid]
        shown = ", ".join(users[:8]) + (f" 等 {len(users)} 項" if len(users) > 8 else "")
        lines += ["-" * 60, f"[{tid}] 適用：{shown}", "-" * 60, text, ""]
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    sections = [
        ("Python sidecar（sidecar.exe）", collect_python()),
        ("Rust 後端（javdbmagnet.exe）", collect_rust()),
        ("前端（嵌入 javdbmagnet.exe）", collect_frontend()),
    ]
    for title, comps in sections:
        if not comps:
            print(f"{title}：沒有收集到任何元件，拒絕產出不完整的聲明", file=sys.stderr)
            return 1
    Path(argv[1]).write_text(render(sections), encoding="utf-8", newline="\r\n")
    total = sum(len(c) for _, c in sections)
    print(f"THIRD_PARTY_NOTICES: {total} components → {argv[1]}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
