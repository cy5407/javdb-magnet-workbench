"""把 spikes/python_sidecar_protocol/sidecar.py 打包成 sidecar.exe

用法（從 repo root 執行）：
    python spikes/pyinstaller_sidecar/build_sidecar.py

產出：
    spikes/pyinstaller_sidecar/dist/sidecar.exe

注意：
- 不會打包 .env / cookies.txt 進 exe
- PyInstaller 中間檔放在 spikes/pyinstaller_sidecar/build/、.spec 也放在同層
- 主程式既有的 build.py 是打 GUI；本檔只處理 sidecar
"""

import shutil
import subprocess
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


def ensure_pyinstaller():
    """檢查 PyInstaller，沒裝就安裝。回傳採用的策略字串供 NOTES 使用。"""
    try:
        import PyInstaller  # noqa: F401
        return "already-installed"
    except ImportError:
        print("PyInstaller 未安裝，使用 pip 安裝...", file=sys.stderr)
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        return "installed-via-pip"


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
        # repo root 加進 PyInstaller 搜尋路徑，讓 javdb_magnet_gui / realdebrid / app_logging 能被解析
        "--paths", str(REPO_ROOT),
        # curl_cffi 有 native deps，要 collect-all
        "--hidden-import", "curl_cffi",
        "--hidden-import", "curl_cffi.requests",
        "--collect-all", "curl_cffi",
        # 主要 modules 強制收進去
        "--hidden-import", "javdb_magnet_gui",
        "--hidden-import", "realdebrid",
        "--hidden-import", "app_logging",
        str(ENTRY),
    ]
    subprocess.check_call(cmd, cwd=REPO_ROOT)


def post_build():
    exe = DIST / f"{APP_NAME}.exe"
    if not exe.exists():
        print(f"⚠️ build artifact not found: {exe}", file=sys.stderr)
        sys.exit(1)
    size_mb = exe.stat().st_size / 1024 / 1024
    print(f"\n✅ Build complete: {exe}", file=sys.stderr)
    print(f"   Size: {size_mb:.1f} MB", file=sys.stderr)
    print(f"\nUsage (M3 daemon):", file=sys.stderr)
    print(f"  Tauri spawns this exe as an externalBin sidecar; the daemon", file=sys.stderr)
    print(f"  reads JSON-line commands from stdin and writes responses to", file=sys.stderr)
    print(f"  stdout. See docs/superpowers/specs/2026-05-10-tauri-rewrite-design.md §5.", file=sys.stderr)
    print(f"\nLog destination:", file=sys.stderr)
    print(f"  Set $env:JAVDB_LOG_DIR or rely on the "
          f"%LOCALAPPDATA%\\JavDBMagnet\\logs fallback.", file=sys.stderr)
    print(f"\nBinary placement:", file=sys.stderr)
    print(f"  This output IS the Tauri externalBin path:", file=sys.stderr)
    print(f"    {exe}", file=sys.stderr)


if __name__ == "__main__":
    strategy = ensure_pyinstaller()
    print(f"PyInstaller: {strategy}", file=sys.stderr)
    clean()
    build()
    post_build()
