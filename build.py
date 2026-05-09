"""打包腳本：用 PyInstaller 把 GUI 打包成單一 .exe

用法：
    python build.py

產出：
    dist/JavDBMagnet.exe
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
DIST = ROOT / "dist"
BUILD = ROOT / "build"
SPEC = ROOT / "JavDBMagnet.spec"
APP_NAME = "JavDBMagnet"


def ensure_pyinstaller():
    try:
        import PyInstaller  # noqa: F401
        return
    except ImportError:
        print("PyInstaller 未安裝，開始安裝...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])


def clean():
    for path in (DIST, BUILD, SPEC):
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            print(f"已清除: {path.name}")


def build():
    print(f"開始打包 {APP_NAME}...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", APP_NAME,
        "--clean",
        # 顯式包含 hidden imports（curl_cffi 有時會漏）
        "--hidden-import", "curl_cffi",
        "--hidden-import", "curl_cffi.requests",
        "--collect-all", "curl_cffi",
        # 入口
        "javdb_magnet_gui.py",
    ]
    subprocess.check_call(cmd, cwd=ROOT)


def post_build():
    exe = DIST / f"{APP_NAME}.exe"
    if not exe.exists():
        print(f"⚠️ 找不到產物: {exe}")
        return

    # 複製範例設定檔與 README 到 dist
    for src_name in (".env.example", "README.md"):
        src = ROOT / src_name
        if src.exists():
            shutil.copy(src, DIST / src_name)
            print(f"已複製: {src_name}")

    print()
    print(f"✅ 打包完成: {exe}")
    print(f"   大小: {exe.stat().st_size / 1024 / 1024:.1f} MB")
    print()
    print("下一步：")
    print(f"  1. 把 {DIST} 整個資料夾發給朋友（或只發 .exe）")
    print(f"  2. 朋友把 .env.example 改名為 .env 並填入 RD_API_TOKEN")
    print(f"  3. 雙擊 {APP_NAME}.exe 執行")


if __name__ == "__main__":
    ensure_pyinstaller()
    clean()
    build()
    post_build()
