"""rd_outcome_log 與 scripts/rd_log_report 的單元與邊界測試。

規格：docs/specs/2026-08-01-rd-outcome-log.md

重點在三類不變量：
  1. redaction —— 這份日誌寫進 log 目錄，而既有的發布 gate 會 grep 整個目錄找
     `magnet:\\?xt|urn:btih` 並預期零輸出。寫出那種字串會讓一條既有的驗收
     步驟從「預期無輸出」變成必然命中。
  2. 日誌永不影響送出 —— 任何寫入失敗都必須被吞掉。
  3. 三元標籤與兩道防呆（樣本偏斜、自造命中）真的生效。
"""

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import rd_outcome_log  # noqa: E402
import rd_log_report  # noqa: E402

# 這兩個 sentinel 一旦出現在日誌裡，既有的 redaction gate 就會開始命中。
FULL_MAGNET = "magnet:?xt=urn:btih:0201592fDEADBEEF0201592fDEADBEEF02015920&dn=SNOS-192"


class TempLogMixin:
    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.log_dir = Path(self._tmp.name)
        rd_outcome_log.reset_for_tests()
        rd_outcome_log.configure(self.log_dir)

    def tearDown(self):
        rd_outcome_log.reset_for_tests()
        self._tmp.cleanup()

    def lines(self) -> list[dict]:
        p = self.log_dir / "rd_outcomes.jsonl"
        if not p.exists():
            return []
        return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]

    def raw(self) -> str:
        p = self.log_dir / "rd_outcomes.jsonl"
        return p.read_text(encoding="utf-8") if p.exists() else ""


class WriteBasicsTest(TempLogMixin, unittest.TestCase):
    def test_send_line_is_one_json_object_with_no_formatter_prefix(self):
        rd_outcome_log.log_send(outcome="completed", elapsed_ms=812, btih8="0201592f")
        raw = self.raw()
        self.assertEqual(len(raw.strip().splitlines()), 1)
        # formatter 若不是 "%(message)s"，這裡會因為時間/層級前綴而爆掉
        obj = json.loads(raw)
        self.assertEqual(obj["event"], "send")
        self.assertEqual(obj["elapsed_ms"], 812)
        self.assertEqual(obj["v"], rd_outcome_log.SCHEMA_VERSION)

    def test_timestamp_carries_milliseconds_and_offset(self):
        rd_outcome_log.log_send(outcome="completed", elapsed_ms=1)
        ts = self.lines()[0]["ts"]
        # 秒級精度會把快取命中與後續 check 的時間差壓成 0
        self.assertRegex(ts, r"T\d{2}:\d{2}:\d{2}\.\d{3}")
        self.assertRegex(ts, r"[+\-]\d{2}:\d{2}$")

    def test_meta_fields_are_carried_through(self):
        rd_outcome_log.log_send(
            outcome="pending", elapsed_ms=15000,
            meta={"code": "SNOS-192", "name": "hhd800.com@SNOS-192-1080p.mp4",
                  "size": "5.4GB, 1個文件", "tags": ["高清"], "date": "2026-06-18",
                  "source": "javdb", "group_seq": 3, "group_size": 5,
                  "date_rank": 2, "size_rank": 1},
            cache_wait=15, file_pick="smart", min_size_mb=500,
        )
        o = self.lines()[0]
        self.assertEqual(o["code"], "SNOS-192")
        self.assertEqual(o["tags"], ["高清"])
        self.assertEqual(o["date_rank"], 2)
        self.assertEqual(o["cache_wait"], 15)

    def test_no_verdict_fields_are_written(self):
        """§2：只記觀測不記判定。出現這些欄位代表規則被複製到 Python 了。"""
        rd_outcome_log.log_send(
            outcome="completed", elapsed_ms=1,
            meta={"name": "hhd800.com@ABC-1080p.mp4", "tags": ["高清"]},
        )
        o = self.lines()[0]
        for banned in ("rd_class", "tier", "is_hd", "has_prefix", "prefix", "age_days"):
            self.assertNotIn(banned, o, f"{banned} 是判定結果，不該固化進日誌")

    def test_check_event_shape(self):
        rd_outcome_log.log_check(outcome="completed", elapsed_ms=320,
                                 torrent_id="T1", link_count=2)
        o = self.lines()[0]
        self.assertEqual(o["event"], "check")
        self.assertEqual(o["torrent_id"], "T1")
        self.assertEqual(o["link_count"], 2)


class RedactionTest(TempLogMixin, unittest.TestCase):
    def test_full_magnet_in_any_field_drops_the_whole_line(self):
        rd_outcome_log.log_send(outcome="completed", elapsed_ms=1,
                                meta={"name": FULL_MAGNET})
        self.assertEqual(self.lines(), [])
        self.assertEqual(rd_outcome_log.dropped_count(), 1)

    def test_redacted_magnet_form_is_also_refused(self):
        """redact_magnet() 的輸出本身就含 urn:btih，一樣會觸發既有 gate。"""
        rd_outcome_log.log_send(outcome="completed", elapsed_ms=1,
                                meta={"name": "magnet:?xt=urn:btih:0201592f..."})
        self.assertEqual(self.lines(), [])

    def test_case_insensitive(self):
        rd_outcome_log.log_send(outcome="completed", elapsed_ms=1,
                                meta={"code": "URN:BTIH:ABCD"})
        self.assertEqual(self.lines(), [])

    def test_dropped_payload_is_not_re_emitted_anywhere(self):
        """擋下來的內容不得換個檔案寫出去。"""
        import logging

        captured = []

        class _Cap(logging.Handler):
            def emit(self, record):
                captured.append(self.format(record))

        root = logging.getLogger()
        h = _Cap()
        h.setFormatter(logging.Formatter("%(message)s"))
        root.addHandler(h)
        try:
            rd_outcome_log.log_send(outcome="completed", elapsed_ms=1,
                                    meta={"name": FULL_MAGNET})
        finally:
            root.removeHandler(h)
        self.assertNotIn("urn:btih", "\n".join(captured).lower())

    def test_clean_line_still_written(self):
        """反向斷言：避免「整行都不寫」冒充遮蔽成功。"""
        rd_outcome_log.log_send(outcome="completed", elapsed_ms=1,
                                btih8="0201592f", meta={"code": "SNOS-192"})
        self.assertEqual(len(self.lines()), 1)
        self.assertIn("0201592f", self.raw())
        self.assertIn("SNOS-192", self.raw())
        self.assertNotRegex(self.raw(), r"(?i)urn:btih|magnet:\?xt")


class IsolationTest(unittest.TestCase):
    def test_lines_do_not_leak_into_root_logger(self):
        """app_logging 把 handler 掛在 root；不切斷傳播的話每行 JSON 會同時
        灌進 debug.log，把番號與檔名帶去一個沒打算承載它們的檔案。"""
        import logging
        import tempfile

        captured = []

        class _Cap(logging.Handler):
            def emit(self, record):
                captured.append(record.getMessage())

        with tempfile.TemporaryDirectory() as d:
            rd_outcome_log.reset_for_tests()
            rd_outcome_log.configure(Path(d))
            root = logging.getLogger()
            h = _Cap()
            root.addHandler(h)
            try:
                rd_outcome_log.log_send(outcome="completed", elapsed_ms=1,
                                        meta={"code": "SNOS-192"})
            finally:
                root.removeHandler(h)
                rd_outcome_log.reset_for_tests()
        self.assertEqual(captured, [])


class DisabledAndFailureTest(unittest.TestCase):
    def tearDown(self):
        rd_outcome_log.reset_for_tests()

    def test_env_off_writes_nothing(self):
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            old = os.environ.get("JAVDB_RD_LOG")
            os.environ["JAVDB_RD_LOG"] = "0"
            try:
                rd_outcome_log.reset_for_tests()
                self.assertIsNone(rd_outcome_log.configure(Path(d)))
                rd_outcome_log.log_send(outcome="completed", elapsed_ms=1)
                self.assertFalse((Path(d) / "rd_outcomes.jsonl").exists())
            finally:
                if old is None:
                    os.environ.pop("JAVDB_RD_LOG", None)
                else:
                    os.environ["JAVDB_RD_LOG"] = old

    def test_other_env_values_keep_it_on(self):
        import os
        import tempfile
        for val in ("1", "", "yes", "0 "):
            with tempfile.TemporaryDirectory() as d:
                old = os.environ.get("JAVDB_RD_LOG")
                os.environ["JAVDB_RD_LOG"] = val
                try:
                    rd_outcome_log.reset_for_tests()
                    expect_on = val.strip() != "0"
                    got = rd_outcome_log.configure(Path(d))
                    self.assertEqual(got is not None, expect_on, f"JAVDB_RD_LOG={val!r}")
                finally:
                    if old is None:
                        os.environ.pop("JAVDB_RD_LOG", None)
                    else:
                        os.environ["JAVDB_RD_LOG"] = old
                    rd_outcome_log.reset_for_tests()

    def test_none_log_dir_disables_silently(self):
        """app_logging 降級成 console-only 時（Linux 上沒有 LOCALAPPDATA 就會
        發生），本功能必須靜默停用而不是自己發明一個路徑。"""
        rd_outcome_log.reset_for_tests()
        self.assertIsNone(rd_outcome_log.configure(None))
        rd_outcome_log.log_send(outcome="completed", elapsed_ms=1)   # 不得丟例外

    def test_unwritable_dir_disables_silently(self):
        rd_outcome_log.reset_for_tests()
        # 用一個「父層是檔案」的路徑，保證 mkdir 失敗且不依賴 root 權限差異
        import tempfile
        with tempfile.NamedTemporaryFile() as f:
            self.assertIsNone(rd_outcome_log.configure(Path(f.name) / "sub"))
            rd_outcome_log.log_send(outcome="completed", elapsed_ms=1)

    def test_non_path_log_dir_creates_nothing(self):
        """`Path(x)` stringifies almost anything, and the next call is
        mkdir(parents=True) — so a stray object would materialise a directory
        tree in whatever the current working directory happens to be. A mocked
        setup_logging() handing over a MagicMock did exactly that."""
        import os
        import tempfile
        from unittest import mock as _mock

        with tempfile.TemporaryDirectory() as cwd:
            prev = os.getcwd()
            os.chdir(cwd)
            try:
                for bogus in (_mock.MagicMock(), object(), 42, ["a"]):
                    rd_outcome_log.reset_for_tests()
                    self.assertIsNone(rd_outcome_log.configure(bogus), repr(bogus))
                    rd_outcome_log.log_send(outcome="completed", elapsed_ms=1)
                self.assertEqual(sorted(os.listdir(cwd)), [],
                                 "configure() 在 CWD 建了目錄")
            finally:
                os.chdir(prev)

    def test_str_log_dir_is_accepted(self):
        """反向斷言：別為了擋掉 MagicMock 而把合法的 str 路徑也擋掉。"""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            rd_outcome_log.reset_for_tests()
            try:
                self.assertIsNotNone(rd_outcome_log.configure(str(d)))
                rd_outcome_log.log_send(outcome="completed", elapsed_ms=1)
                self.assertTrue((Path(d) / "rd_outcomes.jsonl").exists())
            finally:
                # handler 必須在 TemporaryDirectory 清理前關閉：Windows 不允許
                # 刪除仍被開啟的檔案，否則 cleanup 會丟 PermissionError。
                rd_outcome_log.reset_for_tests()

    def test_unserializable_payload_is_swallowed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            rd_outcome_log.reset_for_tests()
            try:
                rd_outcome_log.configure(Path(d))
                rd_outcome_log.log_send(outcome="completed", elapsed_ms=1,
                                        meta={"code": object()})   # 不可序列化
                self.assertEqual((Path(d) / "rd_outcomes.jsonl").read_text(), "")
            finally:
                rd_outcome_log.reset_for_tests()

    def test_handler_failure_is_swallowed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            rd_outcome_log.reset_for_tests()
            rd_outcome_log.configure(Path(d))
            import logging
            lg = logging.getLogger("rd_outcomes")

            class _Boom(logging.Handler):
                def emit(self, record):
                    raise OSError("disk full")

            lg.handlers.clear()
            lg.addHandler(_Boom())
            rd_outcome_log.log_send(outcome="completed", elapsed_ms=1)   # 不得丟例外


class StatusTrailTest(TempLogMixin, unittest.TestCase):
    def test_consecutive_duplicates_collapse(self):
        rd_outcome_log.log_send(
            outcome="pending", elapsed_ms=1,
            status_trail=["queued", "queued", "queued", "downloading"],
        )
        self.assertEqual(self.lines()[0]["status_trail"], ["queued", "downloading"])

    def test_capped(self):
        rd_outcome_log.log_send(outcome="pending", elapsed_ms=1,
                                status_trail=[f"s{i}" for i in range(50)])
        self.assertEqual(len(self.lines()[0]["status_trail"]),
                         rd_outcome_log.MAX_STATUS_TRAIL)

    def test_garbage_is_dropped(self):
        rd_outcome_log.log_send(outcome="pending", elapsed_ms=1,
                                status_trail=["ok", None, 5, "", "next"])
        self.assertEqual(self.lines()[0]["status_trail"], ["ok", "next"])

    def test_non_list_is_tolerated(self):
        rd_outcome_log.log_send(outcome="pending", elapsed_ms=1, status_trail="oops")
        self.assertEqual(self.lines()[0]["status_trail"], [])


# ---------------------------------------------------------------------------
# 報表
# ---------------------------------------------------------------------------

def send(**over):
    base = {
        "v": 1, "ts": "2026-08-01T12:00:00.000+08:00", "event": "send",
        "btih8": "aaaaaaaa", "torrent_id": "T1", "outcome": "completed",
        "elapsed_ms": 500, "rd_status": "downloaded", "status_trail": [],
        "progress": 0, "files_selected": True, "link_count": 1, "error_code": None,
        "code": "ABC-123", "name": "ABC-123.mp4", "size": "5GB, 1個文件",
        "tags": [], "date": "2026-07-30", "source": "javdb",
        "group_seq": 1, "group_size": 3, "date_rank": 1, "size_rank": 1,
        "cache_wait": 15, "file_pick": "smart", "min_size_mb": 500,
    }
    base.update(over)
    return base


def check(**over):
    base = {"v": 1, "ts": "2026-08-01T12:05:00.000+08:00", "event": "check",
            "torrent_id": "T1", "outcome": "completed", "elapsed_ms": 300,
            "rd_status": "downloaded", "progress": 100, "link_count": 1,
            "error_code": None}
    base.update(over)
    return base


class LabelTest(unittest.TestCase):
    def test_fast_completed_is_a_hit(self):
        rows = rd_log_report.label_sends([send(elapsed_ms=800)], 5000)
        self.assertEqual(rows[0]["label"], "hit")

    def test_slow_completed_is_not_a_hit(self):
        """completed 混了『RD 早就有』與『等了很久才下載完』——後者對使用者
        而言是等待，不是命中。"""
        rows = rd_log_report.label_sends([send(elapsed_ms=48000)], 5000)
        self.assertEqual(rows[0]["label"], "slow")

    def test_threshold_is_configurable_and_actually_moves_the_label(self):
        ev = [send(elapsed_ms=8000)]
        self.assertEqual(rd_log_report.label_sends(ev, 5000)[0]["label"], "slow")
        self.assertEqual(rd_log_report.label_sends(ev, 10000)[0]["label"], "hit")

    def test_pending_without_check_is_a_miss(self):
        rows = rd_log_report.label_sends([send(outcome="pending", elapsed_ms=15000)], 5000)
        self.assertEqual(rows[0]["label"], "miss")

    def test_pending_rescued_by_a_later_check_is_slow_not_miss(self):
        """三元標籤的存在理由：這一筆與『三天後仍沒有』完全不同。"""
        rows = rd_log_report.label_sends(
            [send(outcome="pending", elapsed_ms=15000), check()], 5000)
        self.assertEqual(rows[0]["label"], "slow")

    def test_check_on_a_different_torrent_does_not_rescue(self):
        rows = rd_log_report.label_sends(
            [send(outcome="pending", torrent_id="T1"), check(torrent_id="T9")], 5000)
        self.assertEqual(rows[0]["label"], "miss")

    def test_pending_check_does_not_rescue(self):
        rows = rd_log_report.label_sends(
            [send(outcome="pending"), check(outcome="pending")], 5000)
        self.assertEqual(rows[0]["label"], "miss")

    def test_error_is_excluded_from_hit_rate(self):
        rows = rd_log_report.label_sends([send(outcome="error")], 5000)
        self.assertEqual(rows[0]["label"], "error")

    def test_missing_or_garbage_elapsed_is_never_counted_as_a_hit(self):
        """舊期待：缺 elapsed_ms 當成 0 → hit。
        Red 原因：這份報表唯一的產出就是命中率，容錯往「灌高」那一邊倒等於
        讓壞資料自動變成好消息。schema v1 一定會寫這個欄位，但未來換 schema、
        換寫入端或手動合併外部日誌時就會出現缺欄位。
        新期待：無法證明是秒回的一律記 slow。"""
        for bad in (None, "abc", True):
            ev = send()
            if bad is None:
                del ev["elapsed_ms"]
            else:
                ev["elapsed_ms"] = bad
            self.assertEqual(rd_log_report.label_sends([ev], 5000)[0]["label"], "slow",
                             f"elapsed_ms={bad!r}")

    def test_terminal_failure_counts_as_miss(self):
        """規格 §3：「沒人有 = 始終 pending / 終態失敗」。把磁力終態失敗排除於
        分母會系統性高估命中率——規則越糟、失敗越多，表反而越漂亮。"""
        for code in ("rd_magnet_error", "rd_download_failed"):
            rows = rd_log_report.label_sends(
                [send(outcome="error", error_code=code)], 5000)
            self.assertEqual(rows[0]["label"], "miss", code)

    def test_environment_errors_stay_out_of_the_denominator(self):
        """token 過期／429 與「這個磁力有沒有人有」無關，算進 miss 會把環境
        問題誤報成磁力不存在。"""
        for code in ("rd_token_invalid", "rd_rate_limited", "rd_api_error", None):
            rows = rd_log_report.label_sends(
                [send(outcome="error", error_code=code)], 5000)
            self.assertEqual(rows[0]["label"], "error", code)

    def test_a_check_older_than_the_send_does_not_rescue_it(self):
        """只存 torrent_id 而丟掉時間的話，任何一次舊的 completed check 都能
        把後來的 send 救成 slow。"""
        rows = rd_log_report.label_sends([
            send(outcome="pending", torrent_id="T1", ts="2026-08-01T12:00:00.000+08:00"),
            check(torrent_id="T1", ts="2026-08-01T09:00:00.000+08:00"),
        ], 5000)
        self.assertEqual(rows[0]["label"], "miss")

    def test_a_later_check_still_rescues(self):
        rows = rd_log_report.label_sends([
            send(outcome="pending", torrent_id="T1", ts="2026-08-01T12:00:00.000+08:00"),
            check(torrent_id="T1", ts="2026-08-01T12:04:00.000+08:00"),
        ], 5000)
        self.assertEqual(rows[0]["label"], "slow")


class DedupeTest(unittest.TestCase):
    def test_second_send_of_same_magnet_is_excluded(self):
        """第二次必定命中——因為第一次是使用者自己放進 RD 的。"""
        rows = rd_log_report.label_sends([
            send(btih8="aaaa", outcome="pending", ts="2026-08-01T10:00:00.000+08:00"),
            send(btih8="aaaa", outcome="completed", ts="2026-08-01T11:00:00.000+08:00"),
        ], 5000)
        kept, dropped = rd_log_report.dedupe_first_per_btih(rows)
        self.assertEqual(dropped, 1)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["label"], "miss")     # 保留的是最早那筆

    def test_terminal_failure_does_not_poison_a_later_independent_send(self):
        """終態失敗會先刪掉 RD torrent，後一筆不是第一次送出所造的 cache。

        舊 dedupe 把 terminal miss 也放進 seen，導致後來真正命中的獨立嘗試
        被當成「自造命中」丟掉，恰好抹去規則可能隨時間改善的證據。
        """
        rows = rd_log_report.label_sends([
            send(btih8="aaaa", outcome="error", error_code="rd_magnet_error",
                 ts="2026-08-01T10:00:00.000+08:00"),
            send(btih8="aaaa", outcome="completed", elapsed_ms=10,
                 ts="2026-08-01T11:00:00.000+08:00"),
            # Once a retained send really has seeded RD, later observations
            # are self-created and should still be removed.
            send(btih8="aaaa", outcome="completed", elapsed_ms=5,
                 ts="2026-08-01T12:00:00.000+08:00"),
        ], 5000)
        kept, dropped = rd_log_report.dedupe_first_per_btih(rows)
        self.assertEqual([r["label"] for r in kept], ["miss", "hit"])
        self.assertEqual(dropped, 1)

    def test_environment_error_also_never_seeds_the_low_level_dedupe_helper(self):
        """build_report removes environment errors before dedupe, but the
        helper itself must not silently assume every caller already filtered.
        An API error cannot prove a torrent survived in RD.
        """
        rows = rd_log_report.label_sends([
            send(btih8="aaaa", outcome="error", error_code="rd_rate_limited",
                 ts="2026-08-01T10:00:00.000+08:00"),
            send(btih8="aaaa", outcome="completed", elapsed_ms=10,
                 ts="2026-08-01T11:00:00.000+08:00"),
        ], 5000)
        kept, dropped = rd_log_report.dedupe_first_per_btih(rows)
        self.assertEqual([r["label"] for r in kept], ["error", "hit"])
        self.assertEqual(dropped, 0)

    def test_blank_btih_rows_are_all_kept(self):
        rows = rd_log_report.label_sends(
            [send(btih8=""), send(btih8=""), send(btih8="")], 5000)
        kept, dropped = rd_log_report.dedupe_first_per_btih(rows)
        self.assertEqual((len(kept), dropped), (3, 0))


class SignalTest(unittest.TestCase):
    def test_prefixes_are_reported_separately(self):
        """兩站合併成一個 boolean 就永遠看不出其中一個沒用。"""
        self.assertEqual(rd_log_report.sig_prefix(send(name="hhd800.com@A-1.mp4")),
                         "hhd800.com@")
        self.assertEqual(rd_log_report.sig_prefix(send(name="489155.com@A-1.mp4")),
                         "489155.com@")
        self.assertEqual(rd_log_report.sig_prefix(send(name="A-1.mp4")), "(無前綴)")

    def test_prefix_match_is_case_insensitive_and_embedded(self):
        self.assertEqual(
            rd_log_report.sig_prefix(send(name="[javdb.com]HHD800.com@A-1.mp4")),
            "hhd800.com@")

    def test_hd_source_split(self):
        self.assertEqual(rd_log_report.sig_hd_source(send(tags=["高清"])), "tag")
        self.assertEqual(rd_log_report.sig_hd_source(send(name="A-1 1080p.mp4")),
                         "檔名解析度")
        self.assertEqual(rd_log_report.sig_hd_source(send(name="A-1.mp4")), "非高清")

    def test_hd_source_tag_wins_over_filename(self):
        self.assertEqual(
            rd_log_report.sig_hd_source(send(tags=["高清"], name="A-1 1080p.mp4")), "tag")

    def test_jav_serial_is_not_read_as_a_resolution(self):
        """259LUXU-1080 是真實番號，不是解析度。"""
        self.assertEqual(rd_log_report.sig_hd_source(send(name="259LUXU-1080.mp4")),
                         "非高清")
        self.assertEqual(rd_log_report.sig_hd_source(send(name="A 1920x1080.mp4")),
                         "檔名解析度")

    def test_age_bucket_computed_from_ts_minus_date(self):
        self.assertEqual(
            rd_log_report.sig_age_bucket(
                send(ts="2026-08-01T12:00:00.000+08:00", date="2026-07-30")), "0-7 天")
        self.assertEqual(
            rd_log_report.sig_age_bucket(
                send(ts="2026-08-01T12:00:00.000+08:00", date="2025-01-01")), "365 天以上")

    def test_age_bucket_tolerates_missing_or_garbage_date(self):
        for d in ("", "not-a-date", None):
            self.assertEqual(rd_log_report.sig_age_bucket(send(date=d)), "(無日期)")

    def test_rank_signals(self):
        self.assertEqual(rd_log_report.sig_date_rank(send(date_rank=1)), "組內最早")
        self.assertEqual(rd_log_report.sig_date_rank(send(date_rank=3)), "組內第 3 早")
        self.assertEqual(rd_log_report.sig_date_rank(send(date_rank=None)), "(無群組)")


class ReportTest(unittest.TestCase):
    def test_selection_bias_warning_fires_without_a_control_group(self):
        """一鍵勾選會讓『非高清』永遠沒樣本，那張表就無法證偽推薦規則。"""
        events = [send(btih8=f"h{i:06d}", tags=["高清"]) for i in range(30)]
        out = rd_log_report.build_report(events, 5000, 10, False)
        self.assertIn("選擇偏誤警告", out)
        self.assertIn("非高清", out)

    def test_no_warning_when_a_control_group_exists(self):
        events = ([send(btih8=f"a{i:06d}", tags=["高清"]) for i in range(15)]
                  + [send(btih8=f"b{i:06d}", tags=[], name="X.mp4",
                          outcome="pending") for i in range(15)])
        out = rd_log_report.build_report(events, 5000, 10, False)
        self.assertNotIn("選擇偏誤警告", out)

    def test_small_buckets_are_marked_not_conclusive(self):
        out = rd_log_report.build_report([send(btih8="a1")], 5000, 10, False)
        self.assertIn("樣本不足", out)

    def test_empty_log_says_so_instead_of_crashing(self):
        out = rd_log_report.build_report([], 5000, 10, False)
        self.assertIn("沒有可統計的樣本", out)

    def test_malformed_events_do_not_crash_the_report(self):
        out = rd_log_report.build_report(
            [{"event": "send"}, {"event": "check"}, send()], 5000, 10, False)
        self.assertIn("整體", out)

    def test_load_events_reads_rotated_backups_and_skips_bad_lines(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "rd_outcomes.jsonl"
            p.write_text(json.dumps(send()) + "\n{ broken\n", encoding="utf-8")
            (Path(d) / "rd_outcomes.jsonl.1").write_text(
                json.dumps(send(btih8="bbbb")) + "\n", encoding="utf-8")
            events = rd_log_report.load_events(p)
        self.assertEqual(len(events), 2)


# ---------------------------------------------------------------------------
# sidecar 端的 metadata 保存。fetch_javdb 走不到 e2e（host 允許清單只放行
# javdb.com），所以群組排名的正確性在這裡以 in-process 方式釘住。
# ---------------------------------------------------------------------------

import importlib.util  # noqa: E402
from unittest import mock  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "sidecar_daemon_rdlog", ROOT / "sidecar" / "sidecar.py")
sd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sd)

M1 = "magnet:?xt=urn:btih:" + "1" * 40
M2 = "magnet:?xt=urn:btih:" + "2" * 40
M3 = "magnet:?xt=urn:btih:" + "3" * 40


def _fetch_result(magnets):
    return {"url": "https://javdb.com/v/x", "code": "ABC-123", "title": "T",
            "magnets": magnets, "error": ""}


class GroupMetaTest(unittest.TestCase):
    def setUp(self):
        self.state = sd.DaemonState()
        self.state.handshake_done = True

    def _fetch(self, magnets, *, batch_id="batch-a"):
        with mock.patch.object(sd, "create_session", return_value=(mock.MagicMock(), "test")), \
             mock.patch.object(sd, "fetch_magnets", return_value=_fetch_result(magnets)):
            resp = sd.dispatch(self.state, {"cmd": "fetch_javdb", "request_id": "r1",
                                            "url": "https://javdb.com/v/x",
                                            "batch_id": batch_id})
        self.assertTrue(resp["ok"], resp)
        return resp["result"]["magnets"]

    def test_ranks_and_group_fields(self):
        rows = self._fetch([
            {"name": "old-small", "size": "1GB, 1個文件", "tags": [],
             "date": "2026-01-01", "magnet": M1},
            {"name": "new-big", "size": "9GB, 1個文件", "tags": ["高清"],
             "date": "2026-06-01", "magnet": M2},
        ])
        meta = {r["handle_id"]: self.state.magnet_meta[r["handle_id"]] for r in rows}
        by_name = {m["name"]: m for m in meta.values()}
        self.assertEqual(by_name["old-small"]["date_rank"], 1)   # 最早
        self.assertEqual(by_name["new-big"]["date_rank"], 2)
        self.assertEqual(by_name["new-big"]["size_rank"], 1)     # 最大
        self.assertEqual(by_name["old-small"]["size_rank"], 2)
        for m in meta.values():
            self.assertEqual(m["group_size"], 2)
            self.assertEqual(m["code"], "ABC-123")
            self.assertEqual(m["source"], "javdb")
            self.assertEqual(m["group_seq"], 1)

    def test_undated_row_does_not_steal_rank_1(self):
        """空字串在字串比較下小於任何 ISO 日期。沒有 sentinel 的話，JavDB 沒給
        日期的列會在每一組都奪得「最早上傳」。"""
        rows = self._fetch([
            {"name": "undated", "size": "1GB", "tags": [], "date": "", "magnet": M1},
            {"name": "dated", "size": "1GB", "tags": [], "date": "2019-01-01",
             "magnet": M2},
        ])
        meta = {self.state.magnet_meta[r["handle_id"]]["name"]:
                self.state.magnet_meta[r["handle_id"]] for r in rows}
        self.assertEqual(meta["dated"]["date_rank"], 1)
        self.assertEqual(meta["undated"]["date_rank"], 2)

    def test_second_fetch_does_not_reattribute_a_shared_handle(self):
        """同一 BTIH 出現在兩個 JavDB 頁面時，日誌必須沿用**使用者實際看到的
        那一組**的 metadata。前端是 first-occurrence-wins 且 web 群組在陣列頭，
        sidecar 若改記後一組，會把 tags/date/rank 換成使用者沒依據過的值——
        而 rank 一旦被覆蓋就再也算不回來。"""
        first = self._fetch([
            {"name": "FIRST-001", "size": "9GB", "tags": ["高清"],
             "date": "2026-01-01", "magnet": M1},
            {"name": "other", "size": "1GB", "tags": [], "date": "2026-02-01",
             "magnet": M2},
        ])
        hid = [r["handle_id"] for r in first if r["name"] == "FIRST-001"][0]
        before = dict(self.state.magnet_meta[hid])

        self._fetch([
            {"name": "SECOND-999", "size": "1GB", "tags": [],
             "date": "2026-05-05", "magnet": M1},
        ])
        after = self.state.magnet_meta[hid]
        self.assertEqual(after["name"], "FIRST-001")
        self.assertEqual(after["tags"], ["高清"])
        self.assertEqual(after["group_seq"], before["group_seq"])
        self.assertEqual(after["date_rank"], before["date_rank"])

    def test_javdb_still_upgrades_manual_meta(self):
        """反向斷言：別為了擋覆寫而把「手貼列後來被擷取到」的升級也擋掉——
        手貼 meta 只有 dn=，被真資料取代才是對的。"""
        sd.dispatch(self.state, {"cmd": "register_magnets", "request_id": "p1",
                                 "magnets": [M1 + "&dn=PASTED"]})
        rows = self._fetch([{"name": "REAL-001", "size": "5GB", "tags": ["高清"],
                             "date": "2026-01-01", "magnet": M1}])
        meta = self.state.magnet_meta[rows[0]["handle_id"]]
        self.assertEqual(meta["source"], "javdb")
        self.assertEqual(meta["name"], "REAL-001")

    def test_new_ui_batch_reattributes_handle_kept_alive_by_manual_row(self):
        """startScrape replaces every web group but preserves a shared manual
        handle. The next UI batch must therefore replace the old web metadata,
        even though the underlying magnet handle intentionally survives.
        """
        first = self._fetch([
            {"name": "OLD-001", "size": "9GB", "tags": ["高清"],
             "date": "2025-01-01", "magnet": M1},
        ], batch_id="batch-old")
        hid = first[0]["handle_id"]
        sd.dispatch(self.state, {"cmd": "register_magnets", "request_id": "p1",
                                 "magnets": [M1 + "&dn=PASTED"]})

        self._fetch([
            {"name": "NEW-999", "size": "1GB", "tags": [],
             "date": "2026-05-05", "magnet": M1},
        ], batch_id="batch-new")

        meta = self.state.magnet_meta[hid]
        self.assertEqual(meta["name"], "NEW-999")
        self.assertEqual(meta["code"], "ABC-123")
        self.assertEqual(meta["tags"], [])

    def test_new_batch_downgrades_shared_handle_when_new_web_rows_omit_it(self):
        first = self._fetch([
            {"name": "OLD-001", "size": "9GB", "tags": ["高清"],
             "date": "2025-01-01", "magnet": M1},
        ], batch_id="batch-old")
        hid = first[0]["handle_id"]
        sd.dispatch(self.state, {"cmd": "register_magnets", "request_id": "p1",
                                 "magnets": [M1 + "&dn=PASTED"]})

        self._fetch([
            {"name": "OTHER", "size": "2GB", "tags": [],
             "date": "2026-06-01", "magnet": M2},
        ], batch_id="batch-new")

        self.assertEqual(self.state.magnet_meta[hid]["source"], "manual")
        self.assertEqual(self.state.magnet_meta[hid]["name"], "PASTED")
        self.assertEqual(self.state.magnet_meta[hid]["date_rank"], None)

    def test_rejected_first_url_still_begins_the_new_metadata_batch(self):
        first = self._fetch([
            {"name": "OLD-001", "size": "9GB", "tags": ["高清"],
             "date": "2025-01-01", "magnet": M1},
        ], batch_id="batch-old")
        hid = first[0]["handle_id"]
        sd.dispatch(self.state, {"cmd": "register_magnets", "request_id": "p1",
                                 "magnets": [M1 + "&dn=PASTED"]})

        resp = sd.dispatch(self.state, {"cmd": "fetch_javdb", "request_id": "bad",
                                        "url": "https://javdb521.com/v/B",
                                        "batch_id": "batch-new"})
        self.assertFalse(resp["ok"])
        self.assertEqual(self.state.magnet_meta[hid]["source"], "manual")
        self.assertIsNone(self.state.magnet_meta[hid]["date_rank"])

    def test_production_send_logs_post_batch_manual_source_without_internal_id(self):
        import tempfile

        first = self._fetch([
            {"name": "OLD-001", "size": "9GB", "tags": ["高清"],
             "date": "2025-01-01", "magnet": M1},
        ], batch_id="batch-old")
        hid = first[0]["handle_id"]
        sd.dispatch(self.state, {"cmd": "register_magnets", "request_id": "p1",
                                 "magnets": [M1 + "&dn=PASTED"]})
        sd.dispatch(self.state, {"cmd": "fetch_javdb", "request_id": "bad",
                                 "url": "https://javdb521.com/v/B",
                                 "batch_id": "batch-new"})
        self.state.rd_token = "tok"
        fake = mock.MagicMock()
        fake.process_magnet.return_value = {
            "status": "pending", "torrent_id": "T", "name": "n",
            "rd_status": "queued", "progress": 0, "files_selected": True,
        }
        with tempfile.TemporaryDirectory() as d:
            rd_outcome_log.reset_for_tests()
            try:
                rd_outcome_log.configure(Path(d))
                with mock.patch.object(sd, "_rd_client", return_value=fake):
                    resp = sd.dispatch(self.state, {
                        "cmd": "rd_send_magnet", "request_id": "send", "handle_id": hid,
                    })
                self.assertTrue(resp["ok"], resp)
                row = json.loads((Path(d) / "rd_outcomes.jsonl").read_text(encoding="utf-8"))
                self.assertEqual(row["source"], "manual")
                self.assertEqual(row["name"], "PASTED")
                self.assertNotIn("_batch_id", row)
            finally:
                # 必須在 with 區塊內關閉 handler，否則 Windows 上
                # TemporaryDirectory 清理會因檔案仍開啟而失敗。
                rd_outcome_log.reset_for_tests()

    def test_duplicate_btih_in_one_group_uses_first_visible_rows_ranks(self):
        """The frontend sends first occurrence metadata for a shared handle;
        rank maps must use that same canonical row instead of the last duplicate.
        """
        rows = self._fetch([
            {"name": "FIRST", "size": "9GB", "tags": [],
             "date": "2025-01-01", "magnet": M1},
            {"name": "SECOND", "size": "1GB", "tags": [],
             "date": "2026-01-01", "magnet": M1 + "&dn=SECOND"},
        ])
        meta = self.state.magnet_meta[rows[0]["handle_id"]]
        self.assertEqual(meta["name"], "FIRST")
        self.assertEqual(meta["group_size"], 1)
        self.assertEqual(meta["date_rank"], 1)
        self.assertEqual(meta["size_rank"], 1)

    def test_group_seq_increments_across_fetches(self):
        self._fetch([{"name": "a", "size": "1GB", "tags": [], "date": "2026-01-01",
                      "magnet": M1}])
        rows = self._fetch([{"name": "b", "size": "1GB", "tags": [], "date": "2026-01-01",
                             "magnet": M2}])
        self.assertEqual(self.state.magnet_meta[rows[0]["handle_id"]]["group_seq"], 2)

    def test_paste_does_not_clobber_richer_javdb_meta(self):
        """同一 BTIH 的手貼列拿到的是同一個 handle。若讓它覆寫，日誌會宣稱這列
        沒有 tags/date/排名 —— 而它其實有。"""
        rows = self._fetch([{"name": "real-name", "size": "5GB, 1個文件",
                             "tags": ["高清"], "date": "2026-01-01", "magnet": M1}])
        hid = rows[0]["handle_id"]
        resp = sd.dispatch(self.state, {"cmd": "register_magnets", "request_id": "p1",
                                        "magnets": [M1]})
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["registered"][0]["handle_id"], hid)
        self.assertEqual(resp["registered"][0]["deduped"], True)
        meta = self.state.magnet_meta[hid]
        self.assertEqual(meta["source"], "javdb")
        self.assertEqual(meta["tags"], ["高清"])
        self.assertEqual(meta["date"], "2026-01-01")

    def test_paste_of_a_new_magnet_gets_manual_meta(self):
        resp = sd.dispatch(self.state, {"cmd": "register_magnets", "request_id": "p1",
                                        "magnets": [M3 + "&dn=PASTED-1"]})
        hid = resp["registered"][0]["handle_id"]
        meta = self.state.magnet_meta[hid]
        self.assertEqual(meta["source"], "manual")
        self.assertEqual(meta["name"], "PASTED-1")
        self.assertIsNone(meta["group_size"])

    def test_forget_drops_meta(self):
        rows = self._fetch([{"name": "a", "size": "1GB", "tags": [], "date": "2026-01-01",
                             "magnet": M1}])
        hid = rows[0]["handle_id"]
        sd.dispatch(self.state, {"cmd": "forget_magnets", "request_id": "f1",
                                 "handle_ids": [hid]})
        self.assertNotIn(hid, self.state.magnet_meta)

    def test_forget_all_clears_meta(self):
        self._fetch([{"name": "a", "size": "1GB", "tags": [], "date": "2026-01-01",
                      "magnet": M1}])
        sd.dispatch(self.state, {"cmd": "forget_magnets", "request_id": "f1"})
        self.assertEqual(self.state.magnet_meta, {})

    def test_btih8_helper(self):
        self.assertEqual(sd._btih8(M1), "1" * 8)
        self.assertEqual(sd._btih8("magnet:?xt=urn:btih:ABCDEF0123456789"), "abcdef01")
        self.assertEqual(sd._btih8("not-a-magnet"), "")
        self.assertEqual(sd._btih8(""), "")
        # 這個 helper 的整個存在理由：回傳值不得含觸發發布 gate 的字串
        self.assertNotRegex(sd._btih8(M1), r"(?i)urn:btih|magnet:\?xt")


if __name__ == "__main__":
    unittest.main()
