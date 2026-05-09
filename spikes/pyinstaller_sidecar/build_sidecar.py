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
ENTRY = REPO_ROOT / "spikes" / "python_sidecar_protocol" / "sidecar.py"
DIST = SPIKE_DIR / "dist"
BUILD = SPIKE_DIR / "build"
SPEC = SPIKE_DIR / "sidecar.spec"
APP_NAME = "sidecar"


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
        print(f"⚠️ 找不到產物: {exe}", file=sys.stderr)
        sys.exit(1)
    size_mb = exe.stat().st_size / 1024 / 1024
    print(f"\n✅ 打包完成: {exe}", file=sys.stderr)
    print(f"   大小: {size_mb:.1f} MB", file=sys.stderr)
    print(f"\n注意：sidecar.exe 會去 exe 所在資料夾找 cookies.txt（透過主程式的 app_dir() 邏輯）。", file=sys.stderr)
    print(f"        spike 測試需要把 repo root 的 cookies.txt 複製到 {DIST}/", file=sys.stderr)


if __name__ == "__main__":
    strategy = ensure_pyinstaller()
    print(f"PyInstaller: {strategy}", file=sys.stderr)
    clean()
    build()
    post_build()
