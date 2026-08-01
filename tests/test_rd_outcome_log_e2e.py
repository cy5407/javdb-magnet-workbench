"""RD 成效日誌的端到端實測：真的跑起 sidecar 子行程、真的走 JSON-lines 協定、
真的打一台 HTTP 伺服器、真的檢查落地的 rd_outcomes.jsonl。

單元測試證明各函式的行為；這一支證明的是**組裝起來會動**——logging 在
`main()` 裡被 configure、handler 掛對了、檔案落在 `JAVDB_LOG_DIR`、每一行都是
合法 JSON、而且既有的發布 redaction gate 掃過整個 log 目錄仍然零命中。

`realdebrid.API_BASE` 是模組層常數且刻意沒有環境變數覆寫（多一條可外部指向的
API base 就多一條把 token 送去別處的路）。這裡改用測試自備的 `sitecustomize.py`
在直譯器啟動時就地改寫該常數——production code 一行都不必為了測試而讓步。
"""

import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# RD token 必須通過 _is_valid_rd_token（52 個 ASCII 英數）
FAKE_TOKEN = "A" * 52
MAGNET = ("magnet:?xt=urn:btih:0201592fdeadbeef0201592fdeadbeef02015920"
          "&dn=hhd800.com%40ABC-123-1080p.mp4")
BTIH8 = "0201592f"


class _FakeRD(BaseHTTPRequestHandler):
    """最小可用的 RD API 模擬。scenario 由 server 屬性驅動。"""

    def log_message(self, *a):        # 靜音，別污染測試輸出
        pass

    def _json(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        p = self.path
        if p == "/torrents/addMagnet":
            self.server.calls.append("addMagnet")
            self._json(201, {"id": self.server.torrent_id})
        elif p.startswith("/torrents/selectFiles/"):
            self.server.calls.append("selectFiles")
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif p == "/unrestrict/link":
            self._json(200, {"download": "https://dl.example/abc.mp4",
                             "filename": "abc.mp4", "filesize": 5_000_000_000,
                             "streamable": 1})
        else:
            self._json(404, {"error": "not found"})

    def do_GET(self):
        if self.path.startswith("/torrents/info/"):
            self.server.calls.append("info")
            idx = min(self.server.info_index, len(self.server.info_seq) - 1)
            self.server.info_index += 1
            self._json(200, self.server.info_seq[idx])
        else:
            self._json(404, {"error": "not found"})


FILES = [{"id": 1, "path": "/ABC-123-1080p.mp4", "bytes": 5_000_000_000, "selected": 0}]


def _info(status, **over):
    base = {"status": status, "progress": 0, "filename": "ABC-123-1080p.mp4",
            "files": FILES, "links": []}
    base.update(over)
    return base


class _Server:
    def __init__(self, info_seq, torrent_id="T-1"):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), _FakeRD)
        self.httpd.info_seq = info_seq
        self.httpd.info_index = 0
        self.httpd.torrent_id = torrent_id
        self.httpd.calls = []
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        host, port = self.httpd.server_address[:2]
        self.base = f"http://{host}:{port}"
        return self

    def __exit__(self, *exc):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)


class _Sidecar:
    """真的 spawn 一個 sidecar 行程並用協定跟它對話。"""

    def __init__(self, rd_base: str, log_dir: Path, extra_env=None):
        self.rd_base = rd_base
        self.log_dir = log_dir
        self.extra_env = extra_env or {}
        self._sitedir = tempfile.TemporaryDirectory()

    def __enter__(self):
        site = Path(self._sitedir.name)
        (site / "sitecustomize.py").write_text(
            "import os, sys\n"
            "sys.path.insert(0, os.environ['E2E_REPO_ROOT'])\n"
            "import realdebrid\n"
            "realdebrid.API_BASE = os.environ['E2E_RD_BASE']\n",
            encoding="utf-8",
        )
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join([str(site), str(ROOT)])
        env["E2E_REPO_ROOT"] = str(ROOT)
        env["E2E_RD_BASE"] = self.rd_base
        env["JAVDB_LOG_DIR"] = str(self.log_dir)
        env.pop("JAVDB_RD_LOG", None)
        env.update(self.extra_env)
        self.proc = subprocess.Popen(
            [sys.executable, str(ROOT / "sidecar" / "sidecar.py"), "--daemon"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", env=env, bufsize=1,
        )
        return self

    def call(self, req: dict) -> dict:
        self.proc.stdin.write(json.dumps(req) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            raise AssertionError(f"sidecar died: {self.proc.stderr.read()}")
        return json.loads(line)

    def __exit__(self, *exc):
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self._sitedir.cleanup()


def _handshake(sc: _Sidecar) -> dict:
    return sc.call({"cmd": "handshake", "request_id": "h1", "protocol_version": 1,
                    "rd_token": FAKE_TOKEN, "cookies": "",
                    "settings": {"file_pick": "smart", "min_size_mb": 500,
                                 "cache_wait_seconds": 5},
                    "paths": {}})


def _register(sc: _Sidecar, magnet: str = MAGNET) -> str:
    resp = sc.call({"cmd": "register_magnets", "request_id": "r1", "magnets": [magnet]})
    assert resp["ok"], resp
    return resp["registered"][0]["handle_id"]


def _read_log(log_dir: Path) -> list[dict]:
    p = log_dir / "rd_outcomes.jsonl"
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


class E2ECachedHit(unittest.TestCase):
    """RD 立刻回 downloaded —— 快取命中那條路。"""

    def test_send_then_check_produce_joinable_log_rows(self):
        seq = [_info("waiting_files_selection"),
               _info("downloaded", progress=100, links=["https://real-debrid.com/d/XYZ"])]
        with tempfile.TemporaryDirectory() as d:
            log_dir = Path(d)
            with _Server(seq) as srv, _Sidecar(srv.base, log_dir) as sc:
                self.assertTrue(_handshake(sc)["ok"])
                hid = _register(sc)
                resp = sc.call({"cmd": "rd_send_magnet", "request_id": "s1",
                                "handle_id": hid, "cache_wait": 5})
                self.assertTrue(resp["ok"], resp)
                self.assertEqual(resp["status"], "completed")

                chk = sc.call({"cmd": "rd_check_pending", "request_id": "c1",
                               "torrent_id": "T-1"})
                self.assertTrue(chk["ok"], chk)

            rows = _read_log(log_dir)

        sends = [r for r in rows if r["event"] == "send"]
        checks = [r for r in rows if r["event"] == "check"]
        self.assertEqual(len(sends), 1, rows)
        self.assertEqual(len(checks), 1, rows)

        s = sends[0]
        self.assertEqual(s["outcome"], "completed")
        self.assertEqual(s["torrent_id"], "T-1")
        self.assertEqual(s["btih8"], BTIH8)
        self.assertEqual(s["link_count"], 1)
        self.assertIsInstance(s["elapsed_ms"], int)
        # 這條路上 RD 是秒回的；若量測壞掉（例如量成 wall clock 的日期差）
        # 這裡會爆
        self.assertLess(s["elapsed_ms"], 5000)
        # 狀態轉移確實被 observer 收集到了
        self.assertEqual(s["status_trail"], ["waiting_files_selection", "downloaded"])
        # 送出當下的設定被記下來了 —— 少了它，跨設定的樣本無法比較
        self.assertEqual(s["cache_wait"], 5)
        self.assertEqual(s["file_pick"], "smart")
        self.assertEqual(s["min_size_mb"], 500)
        # 手貼磁力：name 來自 dn=，其餘 metadata 為空（不是「非高清」，是「未知」）
        self.assertEqual(s["source"], "manual")
        self.assertEqual(s["name"], "hhd800.com@ABC-123-1080p.mp4")
        self.assertEqual(s["tags"], [])
        self.assertIsNone(s["group_size"])

        # check 事件可用 torrent_id 與 send join —— 這是把 pending 拆成
        # 「後來完成」與「始終沒有」的唯一依據
        self.assertEqual(checks[0]["torrent_id"], s["torrent_id"])
        self.assertEqual(checks[0]["outcome"], "completed")


class E2EPendingAndError(unittest.TestCase):
    def test_pending_send_is_logged_with_rd_status(self):
        # 永遠停在 queued：cache_wait 到期後變 pending
        seq = [_info("waiting_files_selection"), _info("queued", progress=13)]
        with tempfile.TemporaryDirectory() as d:
            log_dir = Path(d)
            with _Server(seq) as srv, _Sidecar(srv.base, log_dir) as sc:
                _handshake(sc)
                hid = _register(sc)
                resp = sc.call({"cmd": "rd_send_magnet", "request_id": "s1",
                                "handle_id": hid, "cache_wait": 1})
                self.assertTrue(resp["ok"], resp)
                self.assertEqual(resp["status"], "pending")
            rows = _read_log(log_dir)

        s = [r for r in rows if r["event"] == "send"][0]
        self.assertEqual(s["outcome"], "pending")
        self.assertEqual(s["rd_status"], "queued")
        self.assertEqual(s["progress"], 13)
        self.assertTrue(s["files_selected"])
        self.assertIn("queued", s["status_trail"])

    def test_terminal_failure_is_logged_as_error_not_dropped(self):
        """錯誤列被丟掉的話，命中率會被系統性高估。"""
        seq = [_info("magnet_error")]
        with tempfile.TemporaryDirectory() as d:
            log_dir = Path(d)
            with _Server(seq) as srv, _Sidecar(srv.base, log_dir) as sc:
                _handshake(sc)
                hid = _register(sc)
                resp = sc.call({"cmd": "rd_send_magnet", "request_id": "s1",
                                "handle_id": hid, "cache_wait": 5})
                self.assertFalse(resp["ok"], resp)
                self.assertEqual(resp["error"]["code"], "rd_magnet_error")
            rows = _read_log(log_dir)

        s = [r for r in rows if r["event"] == "send"][0]
        self.assertEqual(s["outcome"], "error")
        self.assertEqual(s["error_code"], "rd_magnet_error")
        self.assertEqual(s["btih8"], BTIH8)


class E2ERedactionGate(unittest.TestCase):
    """跑真正的發布 gate pattern，掃整個 log 目錄。"""

    def test_no_forbidden_pattern_anywhere_in_the_log_dir(self):
        import re
        seq = [_info("waiting_files_selection"),
               _info("downloaded", progress=100, links=["https://real-debrid.com/d/XYZ"])]
        with tempfile.TemporaryDirectory() as d:
            log_dir = Path(d)
            with _Server(seq) as srv, _Sidecar(srv.base, log_dir) as sc:
                _handshake(sc)
                hid = _register(sc)
                sc.call({"cmd": "rd_send_magnet", "request_id": "s1",
                         "handle_id": hid, "cache_wait": 5})

            # docs/troubleshooting/log-redaction-verification.md:23 的 pattern
            gate = re.compile(r"magnet:\?xt|urn:btih", re.IGNORECASE)
            hits = []
            files = list(log_dir.rglob("*"))
            for f in files:
                if not f.is_file():
                    continue
                text = f.read_text(encoding="utf-8", errors="replace")
                for i, line in enumerate(text.splitlines(), 1):
                    if gate.search(line):
                        hits.append(f"{f.name}:{i}")
            # 反向斷言：確定我們真的掃到了東西，而不是掃了一個空目錄就宣告通過
            self.assertTrue(any(f.name == "rd_outcomes.jsonl" for f in files if f.is_file()),
                            f"沒有產生 rd_outcomes.jsonl，這條 gate 等於沒驗：{files}")
        self.assertEqual(hits, [], f"新日誌觸發了既有的 redaction gate：{hits}")

    def test_token_never_reaches_the_log_dir(self):
        seq = [_info("downloaded", progress=100, links=[])]
        with tempfile.TemporaryDirectory() as d:
            log_dir = Path(d)
            with _Server(seq) as srv, _Sidecar(srv.base, log_dir) as sc:
                _handshake(sc)
                hid = _register(sc)
                sc.call({"cmd": "rd_send_magnet", "request_id": "s1",
                         "handle_id": hid, "cache_wait": 5})
            blob = "\n".join(f.read_text(encoding="utf-8", errors="replace")
                             for f in log_dir.rglob("*") if f.is_file())
        self.assertNotIn(FAKE_TOKEN, blob)
        self.assertNotIn("Bearer", blob)


class E2EDisabled(unittest.TestCase):
    def test_env_off_writes_no_outcome_file_but_send_still_works(self):
        """關閉開關不得影響送出本身。"""
        seq = [_info("downloaded", progress=100, links=[])]
        with tempfile.TemporaryDirectory() as d:
            log_dir = Path(d)
            with _Server(seq) as srv, \
                 _Sidecar(srv.base, log_dir, extra_env={"JAVDB_RD_LOG": "0"}) as sc:
                _handshake(sc)
                hid = _register(sc)
                resp = sc.call({"cmd": "rd_send_magnet", "request_id": "s1",
                                "handle_id": hid, "cache_wait": 5})
                self.assertTrue(resp["ok"], resp)
                self.assertEqual(resp["status"], "completed")
            self.assertFalse((log_dir / "rd_outcomes.jsonl").exists())
            # debug.log 仍應照常產生 —— 關的是成效日誌，不是整個 logging
            self.assertTrue((log_dir / "debug.log").exists())


class E2EReportOverRealLog(unittest.TestCase):
    """報表腳本必須讀得懂真的跑出來的檔案，不是只讀得懂測試捏造的 dict。"""

    def test_report_runs_against_a_real_log_file(self):
        seq = [_info("waiting_files_selection"),
               _info("downloaded", progress=100, links=["https://real-debrid.com/d/XYZ"])]
        with tempfile.TemporaryDirectory() as d:
            log_dir = Path(d)
            with _Server(seq) as srv, _Sidecar(srv.base, log_dir) as sc:
                _handshake(sc)
                hid = _register(sc)
                sc.call({"cmd": "rd_send_magnet", "request_id": "s1",
                         "handle_id": hid, "cache_wait": 5})

            out = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "rd_log_report.py"),
                 "--log", str(log_dir / "rd_outcomes.jsonl")],
                capture_output=True, text=True, encoding="utf-8",
            )
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("RD 送出成效報表", out.stdout)
        self.assertIn("納入統計 1", out.stdout)
        self.assertIn("秒回", out.stdout)
        # 只有一筆樣本，報表必須明講不下結論
        self.assertIn("樣本不足", out.stdout)


if __name__ == "__main__":
    unittest.main()
