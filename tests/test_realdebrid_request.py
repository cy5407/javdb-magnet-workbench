"""Tests for realdebrid.RealDebrid._request error/retry branches.

Covers:
- _parse_retry_after: header present, missing, malformed → fallback
- 429 retry path uses Retry-After header and gives up after 3 retries
- 401 / 403 mapped to RealDebridError with the expected Chinese message
- Generic non-ok status (e.g. 500) surfaces the API error message
- 204 / empty body → None return
- load_env: simple parser, comments, missing file
- RealDebrid(token="") raises RealDebridError immediately

All HTTP traffic is mocked via patch.object(rd.session, "request"). No
network or token is required.
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from realdebrid import RealDebrid, RealDebridError, load_env  # noqa: E402


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

    def test_429_gives_up_after_3_retries(self):
        # 4 total responses: initial + 3 retries, all 429 → finally raise.
        responses = [_resp(429, headers={"Retry-After": "0"})] * 4
        with mock.patch.object(self.rd.session, "request",
                               side_effect=responses) as mock_req, \
             mock.patch("realdebrid.time.sleep"):
            with self.assertRaises(RealDebridError) as cm:
                self.rd._request("GET", "/torrents")
        self.assertEqual(mock_req.call_count, 4)
        self.assertIn("429", str(cm.exception))


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


# ---------------------------------------------------------------------------
# load_env
# ---------------------------------------------------------------------------

class LoadEnv(unittest.TestCase):
    def test_missing_file_returns_empty(self):
        self.assertEqual(load_env(Path("/no/such/path.env")), {})

    def test_parses_pairs_and_strips_quotes(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".env",
                                          encoding="utf-8") as tmp:
            tmp.write("# this is a comment\n")
            tmp.write("\n")
            tmp.write("RD_API_TOKEN=abc-123\n")
            tmp.write('QUOTED="hello world"\n')
            tmp.write("SQUOTED='single'\n")
            tmp.write("no_equals_sign\n")
            tmp.write("PADDED  =   spaced   \n")
            path = Path(tmp.name)
        try:
            env = load_env(path)
        finally:
            path.unlink()
        self.assertEqual(env["RD_API_TOKEN"], "abc-123")
        self.assertEqual(env["QUOTED"], "hello world")
        self.assertEqual(env["SQUOTED"], "single")
        self.assertEqual(env["PADDED"], "spaced")
        self.assertNotIn("no_equals_sign", env)


if __name__ == "__main__":
    unittest.main(verbosity=2)
