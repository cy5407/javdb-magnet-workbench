"""Tests for realdebrid.RealDebrid._request error/retry branches.

Covers:
- _parse_retry_after: header present, missing, malformed → fallback
- 429 retry path uses Retry-After header and gives up after 3 retries
- 401 / 403 mapped to RealDebridError with the expected Chinese message
- Generic non-ok status (e.g. 500) surfaces the API error message
- 204 / empty body → None return
- RealDebrid(token="") raises RealDebridError immediately

``load_env`` was removed from ``realdebrid.py`` (F-06 hardening) and now
lives in ``legacy._legacy_env`` — see ``tests/test_legacy_env.py``.

All HTTP traffic is mocked via patch.object(rd.session, "request"). No
network or token is required.
"""

import sys
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from realdebrid import RealDebrid, RealDebridError  # noqa: E402


def _resp(status: int, *, json_body=None, headers=None, content: bytes = b"{}") -> mock.MagicMock:
    """Build a fake requests.Response-like mock."""
    r = mock.MagicMock()
    r.status_code = status
    r.ok = 200 <= status < 300
    r.headers = headers or {}
    r.content = content
    if json_body is None:
        r.json.return_value = {}
    else:
        r.json.return_value = json_body
    r.text = "" if json_body is None else str(json_body)
    return r


# ---------------------------------------------------------------------------
# RealDebrid construction
# ---------------------------------------------------------------------------

class Construction(unittest.TestCase):
    def test_empty_token_raises(self):
        with self.assertRaises(RealDebridError):
            RealDebrid("")

    def test_token_set_as_bearer_auth_header(self):
        rd = RealDebrid("tok-xyz")
        self.assertEqual(rd.session.headers["Authorization"], "Bearer tok-xyz")
        # Default min_size_mb is 500 per source default.
        self.assertEqual(rd.min_size_mb, 500)

    def test_min_size_mb_override(self):
        rd = RealDebrid("tok-xyz", min_size_mb=1000)
        self.assertEqual(rd.min_size_mb, 1000)


# ---------------------------------------------------------------------------
# _parse_retry_after
# ---------------------------------------------------------------------------

class ParseRetryAfter(unittest.TestCase):
    def test_integer_seconds(self):
        resp = mock.MagicMock()
        resp.headers = {"Retry-After": "7"}
        self.assertEqual(RealDebrid._parse_retry_after(resp), 7.0)

    def test_float_seconds(self):
        resp = mock.MagicMock()
        resp.headers = {"Retry-After": "2.5"}
        self.assertEqual(RealDebrid._parse_retry_after(resp), 2.5)

    def test_missing_header_falls_back_to_5(self):
        resp = mock.MagicMock()
        resp.headers = {}
        self.assertEqual(RealDebrid._parse_retry_after(resp), 5.0)

    def test_non_numeric_falls_back_to_5(self):
        # HTTP allows Retry-After to be an HTTP-date string; the simple
        # float parse can't read it, so the implementation falls back.
        resp = mock.MagicMock()
        resp.headers = {"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}
        self.assertEqual(RealDebrid._parse_retry_after(resp), 5.0)


# ---------------------------------------------------------------------------
# _request status-code branches
# ---------------------------------------------------------------------------

class RequestStatusBranches(unittest.TestCase):
    def setUp(self):
        self.rd = RealDebrid("tok")

    def test_401_raises_token_invalid(self):
        with mock.patch.object(self.rd.session, "request",
                               return_value=_resp(401)):
            with self.assertRaises(RealDebridError) as cm:
                self.rd._request("GET", "/user")
        # The classifier in sidecar matches "401" OR "token 無效".
        msg = str(cm.exception)
        self.assertTrue("401" in msg or "token" in msg.lower() or "無效" in msg,
                        f"unexpected message: {msg!r}")

    def test_403_raises_premium_required(self):
        with mock.patch.object(self.rd.session, "request",
                               return_value=_resp(403)):
            with self.assertRaises(RealDebridError) as cm:
                self.rd._request("GET", "/user")
        msg = str(cm.exception)
        # Sidecar's classifier matches "403" OR "權限不足" OR "premium".
        self.assertTrue("403" in msg or "權限不足" in msg or "premium" in msg.lower(),
                        f"unexpected message: {msg!r}")

    def test_generic_non_ok_surfaces_api_error_field(self):
        bad = _resp(500, json_body={"error": "boom internal"}, content=b'{"error":"boom internal"}')
        with mock.patch.object(self.rd.session, "request", return_value=bad):
            with self.assertRaises(RealDebridError) as cm:
                self.rd._request("GET", "/torrents/info/x")
        self.assertIn("500", str(cm.exception))
        self.assertIn("boom internal", str(cm.exception))

    def test_non_ok_without_json_body_falls_back_to_text(self):
        bad = mock.MagicMock()
        bad.status_code = 502
        bad.ok = False
        bad.headers = {}
        bad.content = b"<html>bad gateway</html>"
        bad.text = "<html>bad gateway</html>"
        bad.json.side_effect = ValueError("not json")
        with mock.patch.object(self.rd.session, "request", return_value=bad):
            with self.assertRaises(RealDebridError) as cm:
                self.rd._request("GET", "/anything")
        self.assertIn("502", str(cm.exception))

    def test_non_ok_html_text_not_echoed_in_user_message(self):
        # SEC-py-rd-01: when RD returns non-JSON (e.g. an HTML error page from
        # an upstream proxy), the response text MUST NOT bleed into the user-
        # visible RealDebridError message — that text reaches the IPC error
        # envelope and would be a log/XSS vector. Fall back to a generic
        # "API error" string instead.
        bad = mock.MagicMock()
        bad.status_code = 502
        bad.ok = False
        bad.headers = {}
        bad.content = b"<html>bad gateway</html>"
        bad.text = "<html>bad gateway</html>"
        bad.json.side_effect = ValueError("not json")
        with mock.patch.object(self.rd.session, "request", return_value=bad):
            with self.assertRaises(RealDebridError) as cm:
                self.rd._request("GET", "/anything")
        msg = str(cm.exception)
        self.assertIn("502", msg)
        self.assertNotIn("<html>", msg)
        self.assertNotIn("bad gateway", msg)
        self.assertIn("API error", msg)

    def test_oversized_json_error_truncated_to_80_chars(self):
        # SEC-py-rd-01: even when RD returns a typed json["error"] string,
        # bound it to 80 chars before placing it in the user-visible message —
        # an unbounded server-controlled string in the error envelope is a
        # log-spam / DoS vector.
        bad = _resp(500,
                    json_body={"error": "x" * 500},
                    content=b'{"error":"' + b"x" * 500 + b'"}')
        with mock.patch.object(self.rd.session, "request", return_value=bad):
            with self.assertRaises(RealDebridError) as cm:
                self.rd._request("GET", "/x")
        msg = str(cm.exception)
        self.assertIn("500", msg)
        # Format is "HTTP <code>: <msg>"; the <msg> chunk must be exactly
        # 80 'x' characters (bounded by the slice).
        payload = msg.split(": ", 1)[1]
        self.assertEqual(payload, "x" * 80)
        self.assertEqual(len(payload), 80)

    def test_3xx_response_rejected_as_redirect(self):
        # With allow_redirects=False on the request layer, any 3xx that
        # surfaces is an unexpected upstream redirect — treat it as an error
        # rather than silently following or returning success.
        redirect = mock.MagicMock()
        redirect.status_code = 301
        # requests.Response.ok is True for 301 (since it's < 400); the guard
        # must fire before the ok-fast-path runs.
        redirect.ok = True
        redirect.headers = {"Location": "https://evil.example/"}
        redirect.content = b""
        redirect.json.return_value = {}
        redirect.text = ""
        with mock.patch.object(self.rd.session, "request", return_value=redirect):
            with self.assertRaises(RealDebridError) as cm:
                self.rd._request("GET", "/x")
        msg = str(cm.exception)
        self.assertIn("301", msg)
        self.assertIn("redirect", msg.lower())

    def test_request_passes_allow_redirects_false(self):
        # Defense-in-depth: the underlying session.request call must opt out
        # of redirect-following so Authorization can't be auto-replayed to a
        # rogue Location host. (requests strips Authorization on cross-host
        # redirects, but we don't want to depend on that.)
        captured: dict = {}

        def _capture(*args, **kwargs):
            captured.update(kwargs)
            return _resp(200, json_body={}, content=b"{}")

        with mock.patch.object(self.rd.session, "request", side_effect=_capture):
            self.rd._request("GET", "/x")
        self.assertIs(captured.get("allow_redirects"), False)

    def test_204_returns_none(self):
        # No body — selectFiles and deleteTorrent return 204 No Content.
        nobody = mock.MagicMock()
        nobody.status_code = 204
        nobody.ok = True
        nobody.headers = {}
        nobody.content = b""
        nobody.json.return_value = None
        with mock.patch.object(self.rd.session, "request", return_value=nobody):
            self.assertIsNone(self.rd._request("DELETE", "/torrents/delete/x"))

    def test_200_with_json_returns_parsed(self):
        ok = _resp(200, json_body={"id": "abc", "filename": "x"},
                   content=b'{"id":"abc","filename":"x"}')
        with mock.patch.object(self.rd.session, "request", return_value=ok):
            out = self.rd._request("GET", "/torrents/info/abc")
        self.assertEqual(out, {"id": "abc", "filename": "x"})


# ---------------------------------------------------------------------------
# _request 429 retry path
# ---------------------------------------------------------------------------

class RequestRateLimit(unittest.TestCase):
    def setUp(self):
        self.rd = RealDebrid("tok")

    def test_429_then_200_retries_and_succeeds(self):
        first = _resp(429, headers={"Retry-After": "1"})
        second = _resp(200, json_body={"ok": True}, content=b'{"ok":true}')
        with mock.patch.object(self.rd.session, "request",
                               side_effect=[first, second]) as mock_req, \
             mock.patch("realdebrid.time.sleep") as mock_sleep:
            out = self.rd._request("GET", "/torrents")
        self.assertEqual(out, {"ok": True})
        self.assertEqual(mock_req.call_count, 2)
        # Retry-After=1 must drive the sleep duration.
        mock_sleep.assert_called_once_with(1.0)

    def test_429_uses_default_5s_when_no_retry_after(self):
        first = _resp(429)  # no Retry-After header
        second = _resp(200, json_body={}, content=b"{}")
        with mock.patch.object(self.rd.session, "request",
                               side_effect=[first, second]), \
             mock.patch("realdebrid.time.sleep") as mock_sleep:
            self.rd._request("GET", "/torrents")
        mock_sleep.assert_called_once_with(5.0)

    def test_429_negative_retry_after_retries_immediately_if_remaining_budget(self):
        first = _resp(429, headers={"Retry-After": "-5"})
        second = _resp(200, json_body={"ok": True}, content=b'{"ok":true}')
        import time
        deadline = time.monotonic() + 50.0
        with mock.patch.object(self.rd.session, "request", side_effect=[first, second]) as mock_req, \
             mock.patch("realdebrid.time.sleep") as mock_sleep:
            out = self.rd._request("GET", "/torrents", deadline=deadline)
        self.assertEqual(out, {"ok": True})
        self.assertEqual(mock_req.call_count, 2)
        mock_sleep.assert_not_called()


# ---------------------------------------------------------------------------
# add_magnet / select_files / delete_torrent thin wrappers
# ---------------------------------------------------------------------------

class ApiWrappers(unittest.TestCase):
    def setUp(self):
        self.rd = RealDebrid("tok")

    def test_add_magnet_returns_id_from_json(self):
        with mock.patch.object(self.rd.session, "request",
                               return_value=_resp(201,
                                                  json_body={"id": "TID-1", "uri": "x"},
                                                  content=b'{"id":"TID-1"}')):
            self.assertEqual(self.rd.add_magnet("magnet:?xt=urn:btih:abc"), "TID-1")

    def test_add_magnet_validates_response_result(self):
        invalid_bodies = [
            _resp(200, json_body="not-a-dict", content=b'"not-a-dict"'),
            _resp(200, json_body={}, content=b'{}'),
            _resp(200, json_body={"id": ""}, content=b'{"id":""}'),
            _resp(200, json_body={"id": 123}, content=b'{"id":123}'),
        ]
        for resp_obj in invalid_bodies:
            with mock.patch.object(self.rd.session, "request", return_value=resp_obj):
                with self.assertRaises(RealDebridError) as cm:
                    self.rd.add_magnet("magnet:?xt=urn:btih:abc")
                self.assertIn("無效的 torrent id", str(cm.exception))

    def test_select_files_joins_list_into_csv(self):
        captured: dict = {}

        def _capture(*args, **kwargs):
            captured.update(kwargs)
            return _resp(204, content=b"")

        with mock.patch.object(self.rd.session, "request", side_effect=_capture):
            self.rd.select_files("TID-1", [1, 3, 5])
        self.assertEqual(captured["data"], {"files": "1,3,5"})

    def test_select_files_string_passthrough(self):
        captured: dict = {}

        def _capture(*args, **kwargs):
            captured.update(kwargs)
            return _resp(204, content=b"")

        with mock.patch.object(self.rd.session, "request", side_effect=_capture):
            self.rd.select_files("TID-1", "all")
        self.assertEqual(captured["data"], {"files": "all"})

    def test_delete_torrent_swallows_rd_error(self):
        # delete is best-effort; the public method must not propagate.
        with mock.patch.object(self.rd.session, "request",
                               return_value=_resp(404,
                                                  json_body={"error": "nope"},
                                                  content=b'{"error":"nope"}')):
            # Should NOT raise.
            self.rd.delete_torrent("TID-missing")


# ---------------------------------------------------------------------------
# check_torrent branches (network mocked at _request level)
# ---------------------------------------------------------------------------

class CheckTorrent(unittest.TestCase):
    def setUp(self):
        self.rd = RealDebrid("tok")

    def test_404_returns_missing(self):
        with mock.patch.object(self.rd, "_request",
                               side_effect=RealDebridError("HTTP 404: not found")):
            out = self.rd.check_torrent("TID-x")
        self.assertEqual(out, {"status": "missing", "torrent_id": "TID-x"})

    def test_non_404_error_propagates(self):
        with mock.patch.object(self.rd, "_request",
                               side_effect=RealDebridError("HTTP 500: boom")):
            with self.assertRaises(RealDebridError):
                self.rd.check_torrent("TID-x")

    def test_downloaded_returns_completed_with_links(self):
        info = {"status": "downloaded", "filename": "n", "links": ["https://l/1"]}
        unrestricted = {"download": "https://dl/1", "filename": "n.mp4",
                        "filesize": 100, "streamable": 1}
        with mock.patch.object(self.rd, "_request") as mock_req:
            # First call: torrent_info; second call: unrestrict_link
            mock_req.side_effect = [info, unrestricted]
            out = self.rd.check_torrent("TID-x")
        self.assertEqual(out["status"], "completed")
        self.assertEqual(out["torrent_id"], "TID-x")
        self.assertEqual(out["links"][0]["download"], "https://dl/1")

    def test_pending_returns_progress_and_status(self):
        info = {"status": "downloading", "filename": "n", "progress": 42}
        with mock.patch.object(self.rd, "_request", return_value=info):
            out = self.rd.check_torrent("TID-x")
        self.assertEqual(out["status"], "pending")
        self.assertEqual(out["rd_status"], "downloading")
        self.assertEqual(out["progress"], 42)

    def test_waiting_files_selection_auto_selects_then_downloaded(self):
        # 1st info: waiting_files_selection with files
        # 2nd info (after select): downloaded
        # 3rd call: unrestrict_link
        files = [
            {"id": 1, "path": "/x/big.mp4", "bytes": 2 * 1024**3},
            {"id": 2, "path": "/x/small.txt", "bytes": 1},
        ]
        info_wait = {"status": "waiting_files_selection", "files": files,
                     "filename": "x"}
        info_done = {"status": "downloaded", "filename": "x.mp4",
                     "links": ["https://l/1"]}
        unrestricted = {"download": "https://dl/1", "filename": "x.mp4",
                        "filesize": 0, "streamable": 0}
        with mock.patch.object(self.rd, "_request") as mock_req:
            # torrent_info → select_files (204) → torrent_info → unrestrict_link
            mock_req.side_effect = [info_wait, None, info_done, unrestricted]
            out = self.rd.check_torrent("TID-x", strategy="largest")
        self.assertEqual(out["status"], "completed")
        self.assertEqual(len(out["links"]), 1)
        # The select_files POST call should have happened
        select_calls = [c for c in mock_req.call_args_list
                        if c.args[0] == "POST" and "selectFiles" in c.args[1]]
        self.assertEqual(len(select_calls), 1)

    def test_waiting_files_selection_no_pick_falls_through_to_pending(self):
        # pick_files returns [] when files is empty; no select_files call,
        # status stays as waiting_files_selection → returns pending.
        info_wait = {"status": "waiting_files_selection", "files": [],
                     "filename": "x", "progress": 0}
        with mock.patch.object(self.rd, "_request", return_value=info_wait):
            out = self.rd.check_torrent("TID-x")
        self.assertEqual(out["status"], "pending")
        self.assertEqual(out["rd_status"], "waiting_files_selection")


# ---------------------------------------------------------------------------
# _collect_links branches
# ---------------------------------------------------------------------------

class CollectLinks(unittest.TestCase):
    def setUp(self):
        self.rd = RealDebrid("tok")

    def test_empty_links_returns_empty_list(self):
        # torrent info without `links` → early-return []
        out = self.rd._collect_links({"links": []})
        self.assertEqual(out, [])

    def test_missing_links_key_returns_empty_list(self):
        out = self.rd._collect_links({})
        self.assertEqual(out, [])

    def test_unrestrict_failure_recorded_as_error_entry(self):
        # First link succeeds, second raises → second slot preserves the
        # cross-language RdLink shape and carries an error string.
        good = {"download": "https://dl/ok", "filename": "ok.mp4",
                "filesize": 1, "streamable": 0}
        info = {"links": ["https://l/a", "https://l/b"]}
        with mock.patch.object(self.rd, "unrestrict_link") as un:
            un.side_effect = [good, RealDebridError("HTTP 503: gone")]
            out = self.rd._collect_links(info)
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["download"], "https://dl/ok")
        self.assertEqual(out[1]["original"], "https://l/b")
        self.assertEqual(out[1]["download"], "")
        self.assertEqual(out[1]["filename"], "")
        self.assertEqual(out[1]["filesize"], 0)
        self.assertEqual(out[1]["streamable"], 0)
        self.assertIn("503", out[1]["error"])


# ---------------------------------------------------------------------------
# process_magnet branches
#
# All HTTP boundaries are mocked at the RealDebrid method level (add_magnet,
# torrent_info, etc.) so no requests/Session is touched.
#
# Time is driven by a small fake-clock helper rather than a finite
# `side_effect=[...]` list. Reason: `mock.patch("realdebrid.time.time", ...)`
# patches the SHARED `time` module — the `logging` module also calls
# `time.time()` when formatting records, so a finite list runs out and
# raises StopIteration mid-test. The fake clock is an unbounded callable
# that advances only when `time.sleep` is called, which (a) survives any
# number of incidental logging calls and (b) still lets us push past the
# `cache_wait` deadline deterministically.
# ---------------------------------------------------------------------------


class _FakeClock:
    """Monotonic clock that advances only when `sleep` is called.

    Returns the current `now` for every `time()` invocation — incidental
    callers (e.g. logging's record timestamp) just see the same value
    repeatedly and never affect loop control. A real sleep advances
    `now` by `sleep_advance` regardless of the requested seconds; tests
    set `sleep_advance` large enough that one sleep can push past the
    cache_wait deadline (so timeout cases finish in O(1) iterations).
    """

    def __init__(self, start: float = 0.0, sleep_advance: float = 0.0):
        self.now = start
        self.sleep_advance = sleep_advance

    def time(self) -> float:
        return self.now

    def sleep(self, _secs: float) -> None:
        self.now += self.sleep_advance


class ProcessMagnet(unittest.TestCase):
    SAMPLE_MAGNET = "magnet:?xt=urn:btih:0123456789abcdef&dn=SNOS-192"

    def setUp(self):
        self.rd = RealDebrid("tok")

    def _patch_clock(self, sleep_advance: float = 0.0):
        """Patch realdebrid.time.time / .sleep with a fake clock and return
        a context that yields the clock. Default sleep_advance=0 keeps the
        clock pinned at 0 — use a value > cache_wait to drive timeout tests."""
        clk = _FakeClock(sleep_advance=sleep_advance)
        # Patch via the module reference so `import time` in realdebrid uses
        # our fake. We use `new` (not `side_effect`) so the wrapped function
        # IS the clock method — no MagicMock list bookkeeping to exhaust.
        p_time = mock.patch("realdebrid.time.time", new=clk.time)
        p_sleep = mock.patch("realdebrid.time.sleep", new=clk.sleep)
        return clk, p_time, p_sleep

    def test_downloaded_immediately_returns_completed(self):
        info = {"status": "downloaded", "filename": "f.mp4",
                "links": ["https://l/1"], "progress": 100}
        unrestricted = {"download": "https://dl/1", "filename": "f.mp4",
                        "filesize": 1, "streamable": 0}
        _, p_t, p_s = self._patch_clock()
        with p_t, p_s, \
             mock.patch.object(self.rd, "add_magnet", return_value="T-1"), \
             mock.patch.object(self.rd, "torrent_info", return_value=info), \
             mock.patch.object(self.rd, "unrestrict_link", return_value=unrestricted):
            out = self.rd.process_magnet(self.SAMPLE_MAGNET)
        self.assertEqual(out["status"], "completed")
        self.assertEqual(out["torrent_id"], "T-1")
        self.assertEqual(out["name"], "f.mp4")
        self.assertEqual(out["links"][0]["download"], "https://dl/1")

    def test_waiting_files_selection_then_downloaded(self):
        files = [{"id": 1, "path": "/x/movie.mp4", "bytes": 5 * 1024**3}]
        info_wait = {"status": "waiting_files_selection", "files": files,
                     "filename": "m.mp4", "progress": 0}
        info_done = {"status": "downloaded", "filename": "m.mp4",
                     "links": [], "progress": 100}
        _, p_t, p_s = self._patch_clock()
        # Clock pinned at 0, waiting_files_selection does `continue` (no
        # sleep), then second iteration sees downloaded → returns. No
        # timeout risk.
        with p_t, p_s, \
             mock.patch.object(self.rd, "add_magnet", return_value="T-2"), \
             mock.patch.object(self.rd, "torrent_info",
                               side_effect=[info_wait, info_done]), \
             mock.patch.object(self.rd, "select_files") as sel:
            out = self.rd.process_magnet(self.SAMPLE_MAGNET, strategy="largest")
        self.assertEqual(out["status"], "completed")
        # select_files must have been invoked with the only candidate id.
        sel.assert_called_once_with("T-2", [1])

    def test_magnet_error_raises_and_deletes(self):
        info = {"status": "magnet_error", "filename": "bad", "progress": 0}
        _, p_t, p_s = self._patch_clock()
        with p_t, p_s, \
             mock.patch.object(self.rd, "add_magnet", return_value="T-3"), \
             mock.patch.object(self.rd, "torrent_info", return_value=info), \
             mock.patch.object(self.rd, "delete_torrent") as dele:
            with self.assertRaises(RealDebridError) as cm:
                self.rd.process_magnet(self.SAMPLE_MAGNET)
        self.assertIn("磁力解析失敗", str(cm.exception))
        dele.assert_called_once_with("T-3")

    def test_error_status_raises_and_deletes(self):
        info = {"status": "error", "filename": "", "progress": 0}
        _, p_t, p_s = self._patch_clock()
        with p_t, p_s, \
             mock.patch.object(self.rd, "add_magnet", return_value="T-4"), \
             mock.patch.object(self.rd, "torrent_info", return_value=info), \
             mock.patch.object(self.rd, "delete_torrent") as dele:
            with self.assertRaises(RealDebridError) as cm:
                self.rd.process_magnet(self.SAMPLE_MAGNET)
        self.assertIn("下載失敗", str(cm.exception))
        dele.assert_called_once_with("T-4")

    def test_pick_files_empty_raises_and_deletes(self):
        # waiting_files_selection but pick_files returns [] → delete + raise.
        info_wait = {"status": "waiting_files_selection", "files": [],
                     "progress": 0}
        _, p_t, p_s = self._patch_clock()
        with p_t, p_s, \
             mock.patch.object(self.rd, "add_magnet", return_value="T-5"), \
             mock.patch.object(self.rd, "torrent_info", return_value=info_wait), \
             mock.patch.object(self.rd, "pick_files", return_value=[]), \
             mock.patch.object(self.rd, "delete_torrent") as dele:
            with self.assertRaises(RealDebridError) as cm:
                self.rd.process_magnet(self.SAMPLE_MAGNET)
        self.assertIn("沒有可選的檔案", str(cm.exception))
        dele.assert_called_once_with("T-5")

    def test_timeout_returns_pending(self):
        # Loop enters once (status=downloading), sleeps once → clock jumps
        # past deadline → while-check fails → return pending. One sleep is
        # enough because sleep_advance > cache_wait.
        info = {"status": "downloading", "filename": "p", "progress": 17}
        _, p_t, p_s = self._patch_clock(sleep_advance=1000.0)
        with p_t, p_s, \
             mock.patch.object(self.rd, "add_magnet", return_value="T-6"), \
             mock.patch.object(self.rd, "torrent_info", return_value=info):
            out = self.rd.process_magnet(self.SAMPLE_MAGNET, cache_wait=15)
        self.assertEqual(out["status"], "pending")
        self.assertEqual(out["torrent_id"], "T-6")
        self.assertEqual(out["rd_status"], "downloading")
        self.assertEqual(out["progress"], 17)
        self.assertFalse(out["files_selected"])

    def test_timeout_after_files_selected_returns_pending(self):
        # waiting_files_selection → select → still downloading → timeout.
        files = [{"id": 1, "path": "/x/m.mp4", "bytes": 3 * 1024**3}]
        info_wait = {"status": "waiting_files_selection", "files": files,
                     "filename": "n", "progress": 0}
        info_dl = {"status": "downloading", "filename": "n", "progress": 50}
        _, p_t, p_s = self._patch_clock(sleep_advance=1000.0)
        with p_t, p_s, \
             mock.patch.object(self.rd, "add_magnet", return_value="T-7"), \
             mock.patch.object(self.rd, "torrent_info",
                               side_effect=[info_wait, info_dl, info_dl]), \
             mock.patch.object(self.rd, "select_files"):
            out = self.rd.process_magnet(self.SAMPLE_MAGNET)
        self.assertEqual(out["status"], "pending")
        self.assertTrue(out["files_selected"])
        self.assertEqual(out["progress"], 50)

    def test_progress_callback_invoked_on_each_log(self):
        info = {"status": "downloaded", "filename": "f", "links": [], "progress": 100}
        progress_calls: list[str] = []
        _, p_t, p_s = self._patch_clock()
        with p_t, p_s, \
             mock.patch.object(self.rd, "add_magnet", return_value="T-8"), \
             mock.patch.object(self.rd, "torrent_info", return_value=info):
            self.rd.process_magnet(self.SAMPLE_MAGNET,
                                    progress=progress_calls.append)
        # At minimum: "新增磁力...", "等待解析檔案清單...", "已快取..."
        self.assertGreaterEqual(len(progress_calls), 2)
        self.assertTrue(any("新增磁力" in m for m in progress_calls))

    def test_magnet_without_btih_uses_unknown_marker(self):
        # The function should still process a malformed magnet (no btih hash);
        # the log marker just becomes "unknown" — no exception path here.
        info = {"status": "downloaded", "filename": "x", "links": [], "progress": 100}
        _, p_t, p_s = self._patch_clock()
        with p_t, p_s, \
             mock.patch.object(self.rd, "add_magnet", return_value="T-9"), \
             mock.patch.object(self.rd, "torrent_info", return_value=info):
            out = self.rd.process_magnet("magnet:?xt=urn:sha1:zz&dn=no-btih")
        self.assertEqual(out["status"], "completed")


# ---------------------------------------------------------------------------
# Deadline and Retry-After Bounds
# ---------------------------------------------------------------------------

class DeadlineAndRetryAfterBounds(unittest.TestCase):
    def setUp(self):
        self.rd = RealDebrid("tok")

    def test_max_retry_after_constant_exists(self):
        from realdebrid import MAX_RETRY_AFTER_SECONDS
        self.assertEqual(MAX_RETRY_AFTER_SECONDS, 10)

    def test_retry_after_capped_at_max(self):
        r429 = _resp(429, headers={"Retry-After": "999"})
        r200 = _resp(200, json_body={"ok": True})
        with mock.patch.object(self.rd.session, "request", side_effect=[r429, r200]), \
             mock.patch("time.sleep") as mock_sleep:
            res = self.rd._request("GET", "/user", deadline=time.monotonic() + 100.0)
            self.assertEqual(res, {"ok": True})
            mock_sleep.assert_called_once()
            self.assertAlmostEqual(mock_sleep.call_args[0][0], 10.0, places=2)

    def test_retry_after_negative_clamped_to_zero(self):
        r429 = _resp(429, headers={"Retry-After": "-5"})
        r200 = _resp(200, json_body={"ok": True})
        with mock.patch.object(self.rd.session, "request", side_effect=[r429, r200]), \
             mock.patch("time.sleep") as mock_sleep:
            res = self.rd._request("GET", "/user")
            self.assertEqual(res, {"ok": True})
            mock_sleep.assert_not_called()

    def test_deadline_exhausted_raises_realdebrid_error_rate(self):
        with mock.patch.object(self.rd.session, "request") as mock_req:
            deadline = time.monotonic() - 1.0
            with self.assertRaises(RealDebridError) as cm:
                self.rd._request("GET", "/user", deadline=deadline)
            self.assertIn("429", str(cm.exception))
            mock_req.assert_not_called()

    def test_close_method_closes_session(self):
        with mock.patch.object(self.rd.session, "close") as mock_close:
            self.rd.close()
            mock_close.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
