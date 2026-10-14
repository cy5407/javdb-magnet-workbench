"""PowerShell 腳本含非 ASCII 字元時必須帶 UTF-8 BOM。

Windows PowerShell 5.1 讀取沒有 BOM 的腳本時用系統 ANSI 編碼（這台是
cp950），中文註解與字串會把 tokenizer 讀壞。2026-10-15 實測：
test-release-scan.ps1 與 verify-windows-build.ps1 在 5.1 下分別有 5 與 20 個
ParserError，而 `npm run release`／`release:test` 走的正是 powershell.exe
（5.1）。pwsh 7 預設 UTF-8，所以只在 pwsh 上驗證的人看不到這個問題。
"""

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOM = b"\xef\xbb\xbf"
SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "target", "dist", "release"}


def _ps1_files() -> list[Path]:
    return sorted(
        p for p in ROOT.rglob("*.ps1")
        if not SKIP_DIRS.intersection(p.relative_to(ROOT).parts)
    )


class Ps1Encoding(unittest.TestCase):
    def test_non_ascii_ps1_scripts_start_with_utf8_bom(self):
        files = _ps1_files()
        self.assertTrue(files, "找不到任何 .ps1，檢查不能把空集合當成通過")
        missing = [
            str(p.relative_to(ROOT))
            for p in files
            if any(b > 0x7F for b in p.read_bytes()) and not p.read_bytes().startswith(BOM)
        ]
        self.assertEqual(missing, [], "含非 ASCII 卻沒有 UTF-8 BOM，Windows PowerShell 5.1 會讀壞")

    def test_release_scripts_are_covered(self):
        # npm run release / release:test / release:audit 跑的兩支，加上會用 5.1
        # 再跑一次 release-scan 測試的 verify 腳本，一定要在掃描範圍內。
        names = {p.name for p in _ps1_files()}
        required = {"build-release.ps1", "test-release-scan.ps1", "verify-windows-build.ps1"}
        self.assertTrue(required <= names, sorted(required - names))


if __name__ == "__main__":
    unittest.main()
