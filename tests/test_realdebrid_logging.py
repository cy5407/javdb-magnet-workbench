"""Regression tests for RealDebrid debug-log redaction.

Protects the security invariant:
    Full magnet text (including the BTIH hash and dn= number code) must NEVER
    reach log files. Only handle_id and "<redacted>" placeholders are allowed.

The leak fixed here was in realdebrid.RealDebrid._request: it logged
`data["magnet"][:80]`, which always covers `magnet:?xt=urn:btih:` (20 chars)
plus the full 40-char hash. With debug.log defaulting to DEBUG, the hash
landed in `%LOCALAPPDATA%\\JavDBMagnet\\logs\\debug.log` on every send-to-RD.

These tests mock requests.Session.request so no network is touched.
"""

import logging
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from realdebrid import RealDebrid  # noqa: E402


class _CaptureHandler(logging.Handler):
    """Captures formatted log records into a list for assertion."""

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(self.format(record))


def _fake_response(status: int = 200, payload: dict | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.ok = 200 <= status < 300
    resp.content = b"{}" if payload is None else b'{"id":"x"}'
    resp.json.return_value = payload if payload is not None else {"id": "fake-id"}
    resp.headers = {}
    return resp


class RedactsMagnetInDebugLog(unittest.TestCase):
    SAMPLE_MAGNET = (
        "magnet:?xt=urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF"
        "&dn=SNOS-192-FULL-TITLE-LEAK-CHECK"
    )

    def setUp(self) -> None:
        self.handler = _CaptureHandler()
        self.handler.setFormatter(logging.Formatter("%(name)s %(levelname)s %(message)s"))
        self.rd_logger = logging.getLogger("realdebrid")
        self._prev_level = self.rd_logger.level
        self.rd_logger.setLevel(logging.DEBUG)
        self.rd_logger.addHandler(self.handler)

    def tearDown(self) -> None:
        self.rd_logger.removeHandler(self.handler)
        self.rd_logger.setLevel(self._prev_level)

    def _all_log_text(self) -> str:
        return "\n".join(self.handler.records)

    def test_add_magnet_does_not_log_btih_or_dn(self):
        rd = RealDebrid("test-token")
        with patch.object(rd.session, "request", return_value=_fake_response()) as mock_req:
            rd.add_magnet(self.SAMPLE_MAGNET)

        # Sanity: the real outgoing request still carries the full magnet —
        # we only redact the LOG copy, not the API payload.
        sent_kwargs = mock_req.call_args.kwargs
        self.assertEqual(sent_kwargs["data"]["magnet"], self.SAMPLE_MAGNET)

        log_text = self._all_log_text()
        self.assertNotIn("urn:btih", log_text)
        self.assertNotIn("DEADBEEF", log_text)
        self.assertNotIn("SNOS-192", log_text)
        self.assertIn("<redacted>", log_text)
        # The redacted marker must be inside the data dict, not just floating.
        self.assertIn("'magnet': '<redacted>'", log_text)

    def test_non_magnet_data_fields_still_truncated_at_80(self):
        # selectFiles uses data={"files": "..."} — must keep its 80-char truncation.
        rd = RealDebrid("test-token")
        long_value = "f" * 200
        kwargs_seen: dict = {}

        def _capture(*_a, **kw):
            kwargs_seen.update(kw)
            return _fake_response(status=204)

        with patch.object(rd.session, "request", side_effect=_capture):
            rd._request("POST", "/torrents/selectFiles/abc", data={"files": long_value})

        log_text = self._all_log_text()
        # Truncation marker present, full string absent.
        self.assertIn("...", log_text)
        self.assertNotIn(long_value, log_text)
        # The original payload is unchanged on the wire.
        self.assertEqual(kwargs_seen["data"]["files"], long_value)

    def test_unrestrict_link_field_is_not_redacted(self):
        # Only key=="magnet" should be redacted. A normal field like "link"
        # follows the truncation rule.
        rd = RealDebrid("test-token")
        link = "https://real-debrid.com/d/" + ("A" * 90)
        with patch.object(
            rd.session, "request",
            return_value=_fake_response(payload={"download": "https://x"}),
        ):
            rd.unrestrict_link(link)

        log_text = self._all_log_text()
        self.assertNotIn("<redacted>", log_text)
        # First 80 chars are visible, but the full 90+ tail is cut off.
        self.assertIn(link[:80], log_text)
        self.assertNotIn(link, log_text)


class RedactsAuthHeadersInDebugLog(unittest.TestCase):
    """Defense-in-depth coverage for ``_redact_log_kwargs``.

    The Bearer token normally lives on ``session.headers["Authorization"]`` so
    it never reaches the per-request kwargs path; but if a caller ever passes
    ``headers={...}`` to ``_request`` (per-request override), the redactor must
    still mask ``Authorization`` / ``Proxy-Authorization`` / ``Cookie`` so the
    token / session cookie cannot leak into ``debug.log``.
    """

    BEARER_TOKEN = "SECRETBEARER_DO_NOT_LEAK_INTO_LOGS_0123456789"
    SESSION_COOKIE = "SECRETSESSION_DO_NOT_LEAK_jdb_session=xyz"

    def test_authorization_header_is_redacted(self):
        # Pure unit: drive the redactor directly so we don't have to fake out
        # the whole HTTP stack.
        out = RealDebrid._redact_log_kwargs({
            "headers": {"Authorization": f"Bearer {self.BEARER_TOKEN}"},
        })
        rendered = repr(out)
        self.assertNotIn(self.BEARER_TOKEN, rendered)
        self.assertEqual(out, {"headers": {"Authorization": "<redacted>"}})

    def test_cookie_and_proxy_auth_headers_are_redacted(self):
        out = RealDebrid._redact_log_kwargs({
            "headers": {
                "Cookie": self.SESSION_COOKIE,
                "Proxy-Authorization": "Basic SECRETPROXYCREDS_DO_NOT_LEAK",
                "X-Custom-Trace": "trace-id-not-secret",
            },
        })
        rendered = repr(out)
        self.assertNotIn(self.SESSION_COOKIE, rendered)
        self.assertNotIn("SECRETPROXYCREDS", rendered)
        self.assertEqual(out["headers"]["Cookie"], "<redacted>")
        self.assertEqual(out["headers"]["Proxy-Authorization"], "<redacted>")
        # Non-auth headers stay visible (truncated at 80 chars if long).
        self.assertEqual(out["headers"]["X-Custom-Trace"], "trace-id-not-secret")

    def test_header_match_is_case_insensitive(self):
        # requests normalises header keys but a user-supplied dict can be
        # lower / mixed case. Redaction must not depend on capitalisation.
        out = RealDebrid._redact_log_kwargs({
            "headers": {"authorization": f"Bearer {self.BEARER_TOKEN}"},
        })
        self.assertNotIn(self.BEARER_TOKEN, repr(out))
        self.assertEqual(out["headers"]["authorization"], "<redacted>")

    def test_data_and_headers_both_handled(self):
        # When both kwargs are present neither path is shadowed by the other.
        out = RealDebrid._redact_log_kwargs({
            "data": {"magnet": "magnet:?xt=urn:btih:DEAD", "files": "all"},
            "headers": {"Authorization": "Bearer LEAKABLE"},
        })
        self.assertEqual(out["data"]["magnet"], "<redacted>")
        self.assertEqual(out["data"]["files"], "all")
        self.assertEqual(out["headers"]["Authorization"], "<redacted>")
        self.assertNotIn("LEAKABLE", repr(out))

    def test_empty_kwargs_still_returns_empty_dict(self):
        # Backwards-compat: callers used to rely on `_redact_log_kwargs({}) == {}`.
        self.assertEqual(RealDebrid._redact_log_kwargs({}), {})
        self.assertEqual(RealDebrid._redact_log_kwargs({"timeout": 30}), {})


class LogTorrentInfoSummaryTests(unittest.TestCase):
    """Cover the debug-only summary emitted after torrent_info responses."""

    def test_dict_without_files_key_does_not_log(self):
        logger = logging.getLogger("realdebrid")
        capture = _CaptureHandler()
        logger.addHandler(capture)
        try:
            RealDebrid._log_torrent_info_summary({"status": "downloaded"})
        finally:
            logger.removeHandler(capture)
        self.assertEqual(capture.records, [])

    def test_non_dict_input_does_not_log(self):
        logger = logging.getLogger("realdebrid")
        capture = _CaptureHandler()
        logger.addHandler(capture)
        try:
            RealDebrid._log_torrent_info_summary("not-a-dict")
        finally:
            logger.removeHandler(capture)
        self.assertEqual(capture.records, [])

    def test_dict_with_files_logs_status_progress_files_links(self):
        logger = logging.getLogger("realdebrid")
        prev_level = logger.level
        logger.setLevel(logging.DEBUG)
        capture = _CaptureHandler()
        capture.setLevel(logging.DEBUG)
        capture.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(capture)
        try:
            RealDebrid._log_torrent_info_summary({
                "status": "downloaded",
                "progress": 100,
                "files": [{"id": 1}, {"id": 2}],
                "links": ["https://example/dl/1"],
            })
        finally:
            logger.removeHandler(capture)
            logger.setLevel(prev_level)
        self.assertEqual(len(capture.records), 1)
        msg = capture.records[0]
        self.assertIn("status=downloaded", msg)
        self.assertIn("progress=100", msg)
        self.assertIn("files=2", msg)
        self.assertIn("links=1", msg)


if __name__ == "__main__":
    unittest.main()
