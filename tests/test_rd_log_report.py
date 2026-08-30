"""Tests for scripts/rd_log_report.py — path containment validation and CLI behavior.

Guarantees:
- load_events only reads files contained within allowed log directories
  (candidates from JAVDB_LOG_DIR and %LOCALAPPDATA%\\JavDBMagnet\\logs).
- Resolving paths with .. that escape allowed dirs is blocked (containment, not just resolve).
- Rotated backup files (.1, .2, ...) inside allowed dirs are loaded correctly.
- main() returns 2 and outputs an error to sys.stderr when ValueError is caught.
- All tests use temporary directories and monkeypatched environment variables,
  without touching real %LOCALAPPDATA% or system log paths.
"""

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import rd_log_report  # noqa: E402


class TestRdLogReportContainment(unittest.TestCase):
    """Test path containment verification in rd_log_report."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.allowed_dir = self.tmp_path / "allowed_logs"
        self.allowed_dir.mkdir(parents=True, exist_ok=True)
        self.outside_dir = self.tmp_path / "outside_dir"
        self.outside_dir.mkdir(parents=True, exist_ok=True)

        self._env_patcher = mock.patch.dict(
            os.environ,
            {
                "JAVDB_LOG_DIR": str(self.allowed_dir),
                "LOCALAPPDATA": str(self.tmp_path / "dummy_localappdata"),
            },
        )
        self._env_patcher.start()

    def tearDown(self):
        self._env_patcher.stop()
        self._tmp.cleanup()

    def test_load_events_success_with_rotated_backup(self):
        """a. JAVDB_LOG_DIR 指向 tmp 目錄時，讀取該目錄下的 rd_outcomes.jsonl 成功，且輪替備份 .1 一併載入。"""
        main_log = self.allowed_dir / "rd_outcomes.jsonl"
        rot_log = self.allowed_dir / "rd_outcomes.jsonl.1"
        main_log.write_text(
            json.dumps({"event": "send", "outcome": "completed", "elapsed_ms": 120, "btih8": "aaaa1111"}) + "\n",
            encoding="utf-8",
        )
        rot_log.write_text(
            json.dumps({"event": "send", "outcome": "completed", "elapsed_ms": 250, "btih8": "bbbb2222"}) + "\n",
            encoding="utf-8",
        )
        events = rd_log_report.load_events(main_log)
        self.assertEqual(len(events), 2)
        btihs = [e.get("btih8") for e in events]
        self.assertIn("aaaa1111", btihs)
        self.assertIn("bbbb2222", btihs)

    def test_load_events_outside_allowed_dir_raises_value_error(self):
        """b. 傳入不在允許目錄內的絕對路徑 → load_events 丟 ValueError。"""
        outside_log = self.outside_dir / "rd_outcomes.jsonl"
        outside_log.write_text(
            json.dumps({"event": "send", "outcome": "completed", "elapsed_ms": 100}) + "\n",
            encoding="utf-8",
        )
        with self.assertRaises(ValueError) as ctx:
            rd_log_report.load_events(outside_log)
        self.assertIn("不在允許的日誌目錄內", str(ctx.exception))
        self.assertIn("JAVDB_LOG_DIR", str(ctx.exception))

    def test_load_events_parent_traversal_raises_value_error(self):
        """c. 傳入含 .. 的路徑（解析後跳出允許目錄）→ 丟 ValueError。"""
        outside_file = self.outside_dir / "secret.jsonl"
        outside_file.write_text(
            json.dumps({"event": "send", "outcome": "completed", "elapsed_ms": 100}) + "\n",
            encoding="utf-8",
        )
        traversal_path = self.allowed_dir / ".." / "outside_dir" / "secret.jsonl"
        with self.assertRaises(ValueError) as ctx:
            rd_log_report.load_events(traversal_path)
        self.assertIn("不在允許的日誌目錄內", str(ctx.exception))

    def test_main_handles_value_error_returns_2_and_writes_stderr(self):
        """d. main() 在遇到該 ValueError 時回傳 2 並且訊息寫到 stderr。"""
        outside_log = self.outside_dir / "rd_outcomes.jsonl"
        outside_log.write_text(
            json.dumps({"event": "send", "outcome": "completed", "elapsed_ms": 100}) + "\n",
            encoding="utf-8",
        )
        stderr_buf = io.StringIO()
        with mock.patch("sys.stderr", stderr_buf):
            ret = rd_log_report.main(["rd_log_report.py", "--log", str(outside_log)])
        self.assertEqual(ret, 2)
        err_output = stderr_buf.getvalue()
        self.assertIn("不在允許的日誌目錄內", err_output)
        self.assertIn("JAVDB_LOG_DIR", err_output)

    def test_ensure_within_log_dirs_empty_candidates_raises_value_error(self):
        """當候選清單為空時，_ensure_within_log_dirs 一律拋出 ValueError。"""
        with mock.patch.dict(os.environ, {"JAVDB_LOG_DIR": "", "LOCALAPPDATA": ""}):
            some_log = self.allowed_dir / "rd_outcomes.jsonl"
            with self.assertRaises(ValueError) as ctx:
                rd_log_report._ensure_within_log_dirs(some_log)
            self.assertIn("不在允許的日誌目錄內", str(ctx.exception))
            self.assertIn("(無)", str(ctx.exception))

    def test_main_missing_log_returns_1(self):
        """指定不存在的檔案時，main() 回傳 1 並提示找不到檔案。"""
        missing_log = self.allowed_dir / "non_existent.jsonl"
        stderr_buf = io.StringIO()
        with mock.patch("sys.stderr", stderr_buf):
            ret = rd_log_report.main(["rd_log_report.py", "--log", str(missing_log)])
        self.assertEqual(ret, 1)
        self.assertIn("找不到 rd_outcomes.jsonl", stderr_buf.getvalue())

    def test_main_success_returns_0(self):
        """合法路徑與資料時，main() 產出報表並回傳 0。"""
        main_log = self.allowed_dir / "rd_outcomes.jsonl"
        main_log.write_text(
            json.dumps({"event": "send", "outcome": "completed", "elapsed_ms": 100, "btih8": "aaaa1111"}) + "\n",
            encoding="utf-8",
        )
        stdout_buf = io.StringIO()
        with mock.patch("sys.stdout", stdout_buf):
            ret = rd_log_report.main(["rd_log_report.py", "--log", str(main_log)])
        self.assertEqual(ret, 0)
        self.assertIn("RD 送出成效報表", stdout_buf.getvalue())


if __name__ == "__main__":
    unittest.main()
