"""把 sidecar/sidecar.py 打包成 sidecar.exe

用法（從 repo root 執行）：
    python spikes/pyinstaller_sidecar/build_sidecar.py
    # 或：cd app && npm run sidecar:build

產出：
    app/src-tauri/binaries/sidecar-x86_64-pc-windows-msvc.exe
    （Tauri 2 externalBin 路徑，會被 javdbmagnet.exe 直接 spawn）

注意：
- 不會打包 .env / cookies.txt 進 exe
- PyInstaller 中間檔放在 spikes/pyinstaller_sidecar/build/、.spec 也放在同層
- M3 起 entry 已從 spikes/python_sidecar_protocol/sidecar.py 改為 sidecar/sidecar.py；
  舊 spike 已 retired (見 spikes/python_sidecar_protocol/NOTES.md)
"""

import importlib.metadata
import re
import shutil
# Build script: all subprocess invocations below use literal argv arrays.
import subprocess  # nosec B404
import sys
from pathlib import Path

# 從本檔位置回推 repo root：
# spikes/pyinstaller_sidecar/build_sidecar.py → repo root
SPIKE_DIR = Path(__file__).resolve().parent
REPO_ROOT = SPIKE_DIR.parent.parent
# M3: entry promoted from spikes/python_sidecar_protocol/ to sidecar/
ENTRY = REPO_ROOT / "sidecar" / "sidecar.py"
# M3: output goes directly into the Tauri externalBin layout.
# Tauri 2 expects `binaries/<name>-<target-triple>` (with `.exe` on Windows).
DIST = REPO_ROOT / "app" / "src-tauri" / "binaries"
BUILD = SPIKE_DIR / "build"
APP_NAME = "sidecar-x86_64-pc-windows-msvc"
SPEC = SPIKE_DIR / f"{APP_NAME}.spec"
REQUIREMENTS = REPO_ROOT / "requirements-sidecar.txt"


def _pinned_versions() -> dict[str, str]:
    """Parse requirements-sidecar.txt into `{lowercase_name: pinned_version}`.

    Strict: only `name==version` lines (plus comments / blank lines) are
    accepted. Any other syntax (>=, ~=, extras, markers, URLs, …) fails the
    build — this file's whole point is exact reproducibility.
    """
    rel = REQUIREMENTS.relative_to(REPO_ROOT)
    if not REQUIREMENTS.exists():
        sys.exit(f"missing {rel}; cannot verify build deps")
    rx = re.compile(r"^\s*([A-Za-z0-9_.\-]+)\s*==\s*(\S+)\s*$")
    pinned: dict[str, str] = {}
    for n, raw in enumerate(REQUIREMENTS.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = rx.match(raw)
        if not m:
            sys.exit(f"{rel}:{n}: only `name==version` pins are allowed, got: {raw!r}")
        pinned[m.group(1).lower()] = m.group(2)
    if not pinned:
        sys.exit(f"{rel}: no pins found")
    return pinned


def ensure_pinned_deps() -> dict[str, str]:
    """Verify every package in requirements-sidecar.txt is installed at the
    exact pinned version. Fail fast on missing / mismatch. Returns the pin
    map so the caller can print a one-line summary.

    Does NOT touch the host Python environment (no auto pip install).
    """
    rel = REQUIREMENTS.relative_to(REPO_ROOT)
    pinned = _pinned_versions()
    fix = f"pip install -r {rel}"
    for name, want in pinned.items():
        try:
            installed = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            sys.exit(f"{name}: not installed (pinned=={want})\n  {fix}")
        if installed != want:
            sys.exit(
                f"{name}: version mismatch (installed={installed}, pinned={want})\n  {fix}"
            )
    return pinned


def clean():
    for p in (DIST, BUILD, SPEC):
        if p.exists():
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
            print(f"已清除: {p.name}", file=sys.stderr)


def build():
    if not ENTRY.exists():
        print(f"找不到 sidecar 入口: {ENTRY}", file=sys.stderr)
        sys.exit(1)

    print(f"打包 {ENTRY.name} → {DIST / (APP_NAME + '.exe')}", file=sys.stderr)
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--console",                   # console mode：保留 stdout/stderr
        "--name", APP_NAME,
        "--clean",
        "--distpath", str(DIST),
        "--workpath", str(BUILD),
        "--specpath", str(SPIKE_DIR),
        # repo root 加進 PyInstaller 搜尋路徑，讓 javdb_scraper / realdebrid / app_logging 能被解析
        "--paths", str(REPO_ROOT),
        # curl_cffi 有 native deps，要 collect-all
        "--hidden-import", "curl_cffi",
        "--hidden-import", "curl_cffi.requests",
        "--collect-all", "curl_cffi",
        # 主要 modules 強制收進去
        # M9: sidecar 使用 javdb_scraper（純 HTTP+parse 模組），不再 import
        # javdb_magnet_gui，故 Tk/widgets 不會被 PyInstaller bundle 進 sidecar.exe。
        "--hidden-import", "javdb_scraper",
        "--hidden-import", "realdebrid",
        "--hidden-import", "app_logging",
        str(ENTRY),
    ]
    # cmd is a literal PyInstaller argv built in this file (no user input).
    subprocess.check_call(cmd, cwd=REPO_ROOT)  # nosec B603


def post_build():
    exe = DIST / f"{APP_NAME}.exe"
    if not exe.exists():
        print(f"⚠️ build artifact not found: {exe}", file=sys.stderr)
        sys.exit(1)
    size_mb = exe.stat().st_size / 1024 / 1024
    print(f"\n✅ Build complete: {exe}", file=sys.stderr)
    print(f"   Size: {size_mb:.1f} MB", file=sys.stderr)
    print("\nUsage (M3 daemon):", file=sys.stderr)
    print("  Tauri spawns this exe as an externalBin sidecar; the daemon", file=sys.stderr)
    print("  reads JSON-line commands from stdin and writes responses to", file=sys.stderr)
    print("  stdout. See docs/superpowers/specs/2026-05-10-tauri-rewrite-design.md §5.", file=sys.stderr)
    print("\nLog destination:", file=sys.stderr)
    print("  Set $env:JAVDB_LOG_DIR or rely on the "
          "%LOCALAPPDATA%\\JavDBMagnet\\logs fallback.", file=sys.stderr)
    print("\nBinary placement:", file=sys.stderr)
    print("  This output IS the Tauri externalBin path:", file=sys.stderr)
    print(f"    {exe}", file=sys.stderr)


if __name__ == "__main__":
    pinned = ensure_pinned_deps()
    summary = ", ".join(f"{n}=={v}" for n, v in pinned.items())
    print(f"Pinned deps: {summary}", file=sys.stderr)
    clean()
    build()
    post_build()
