"""No-network tests for sidecar/sidecar.py JSON-lines daemon (M3).

All HTTP boundaries (create_session, fetch_magnets) are mocked. Tests run
without setting up logging — they exercise dispatch directly so no log
handlers are attached and %LOCALAPPDATA% is not touched.
"""

import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Load sidecar/sidecar.py under a unique module name so it doesn't collide
# with the legacy spike's sidecar.py that test_sidecar_cli.py imports as `sidecar`.
_DAEMON_PATH = ROOT / "sidecar" / "sidecar.py"
_spec = importlib.util.spec_from_file_location("sidecar_daemon_m3", _DAEMON_PATH)
sd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sd)


def _call(state: sd.DaemonState, req: dict) -> dict:
    """Helper: dispatch a request through the daemon, return response dict."""
    return sd.dispatch(state, req)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class RedactMagnet(unittest.TestCase):
    def test_full_hex_redacted_to_8_chars(self):
        full = "magnet:?xt=urn:btih:0123456789abcdef&dn=test"
        self.assertEqual(sd.redact_magnet(full),
                         "magnet:?xt=urn:btih:01234567...")

    def test_empty_returns_empty(self):
        self.assertEqual(sd.redact_magnet(""), "")

    def test_non_btih_magnet(self):
        self.assertEqual(sd.redact_magnet("magnet:?xt=urn:other"), "magnet:...")

    def test_not_a_magnet(self):
        self.assertEqual(sd.redact_magnet("https://example.com"), "<not-a-magnet>")


class ParseCookieString(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(
            sd.parse_cookie_string("a=1; b=2"),
            {"a": "1", "b": "2"},
        )

    def test_empty(self):
        self.assertEqual(sd.parse_cookie_string(""), {})


# ---------------------------------------------------------------------------
# hello / handshake
# ---------------------------------------------------------------------------

class Hello(unittest.TestCase):
    def test_hello_returns_protocol_version(self):
        state = sd.DaemonState()
        resp = _call(state, {"cmd": "hello", "protocol_version": 1, "request_id": "r1"})
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["request_id"], "r1")
        self.assertEqual(resp["protocol_version"], 1)
        self.assertIn("sidecar_version", resp)
        self.assertEqual(resp["engine"], "curl_cffi")

    def test_hello_rejects_mismatched_version(self):
        state = sd.DaemonState()
        resp = _call(state, {"cmd": "hello", "protocol_version": 99, "request_id": "r1"})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "protocol_mismatch")


class Handshake(unittest.TestCase):
    def test_handshake_stores_state(self):
        state = sd.DaemonState()
        resp = _call(state, {
            "cmd": "handshake", "request_id": "r2",
            "cookies": "k=v; other=val",
            "rd_token": "tok",
            "settings": {"ui": {"theme": "dark"}},
            "paths": {"data_dir": "/d", "log_dir": "/l"},
        })
        self.assertTrue(resp["ok"])
        self.assertEqual(state.cookies, {"k": "v", "other": "val"})
        self.assertEqual(state.rd_token, "tok")
        self.assertEqual(state.settings, {"ui": {"theme": "dark"}})
        self.assertEqual(state.paths, {"data_dir": "/d", "log_dir": "/l"})
        self.assertTrue(state.handshake_done)

    def test_handshake_handles_null_token(self):
        state = sd.DaemonState()
        resp = _call(state, {
            "cmd": "handshake", "request_id": "r2",
            "cookies": "", "rd_token": None,
            "settings": {}, "paths": {},
        })
        self.assertTrue(resp["ok"])
        self.assertEqual(state.rd_token, "")


# ---------------------------------------------------------------------------
# ping
# ---------------------------------------------------------------------------

class Ping(unittest.TestCase):
    def test_ping_returns_uptime(self):
        state = sd.DaemonState()
        resp = _call(state, {"cmd": "ping", "request_id": "r1"})
        self.assertTrue(resp["ok"])
        self.assertIn("uptime_seconds", resp)
        self.assertGreaterEqual(resp["uptime_seconds"], 0)


# ---------------------------------------------------------------------------
# fetch_javdb
# ---------------------------------------------------------------------------

class FetchJavdb(unittest.TestCase):
    def setUp(self):
        self.state = sd.DaemonState()
        self.state.handshake_done = True
        self.state.cookies = {"k": "v"}

    def test_fetch_requires_handshake(self):
        state = sd.DaemonState()
        resp = _call(state, {"cmd": "fetch_javdb", "request_id": "r1",
                             "url": "https://javdb.com/v/x"})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "bad_request")

    def test_fetch_validates_url(self):
        resp = _call(self.state, {"cmd": "fetch_javdb", "request_id": "r1",
                                  "url": "not-a-url"})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "bad_request")

    def test_fetch_returns_handles_and_redacted_magnets(self):
        full_magnet = (
            "magnet:?xt=urn:btih:"
            "0123456789abcdef"
            "&dn=ABC-123"
        )
        with mock.patch.object(sd, "create_session",
                               return_value=(mock.MagicMock(), "mock_engine")), \
             mock.patch.object(sd, "fetch_magnets") as mock_fetch:
            mock_fetch.return_value = {
                "url": "https://javdb.com/v/x",
                "code": "ABC-123",
                "title": "fixture",
                "error": "",
                "magnets": [
                    {"name": "ABC-123", "size": "5GB",
                     "tags": ["high-def"], "date": "2026-01-01",
                     "magnet": full_magnet},
                ],
            }
            resp = _call(self.state, {"cmd": "fetch_javdb", "request_id": "r1",
                                      "url": "https://javdb.com/v/x"})

        self.assertTrue(resp["ok"])
        result = resp["result"]
        self.assertEqual(result["code"], "ABC-123")
        self.assertEqual(result["magnet_count"], 1)
        self.assertEqual(result["engine"], "mock_engine")
        m = result["magnets"][0]
        self.assertTrue(m["handle_id"].startswith("h-"))
        # Redacted magnet must not contain full hash, dn=, or query body
        self.assertEqual(m["magnet_redacted"],
                         "magnet:?xt=urn:btih:01234567...")
        self.assertNotIn("dn=", m["magnet_redacted"])
        self.assertNotIn("ABC-123", m["magnet_redacted"])
        # Handle resolves to the full magnet
        self.assertEqual(self.state.magnets[m["handle_id"]], full_magnet)

    def test_fetch_403_maps_to_cloudflare_block(self):
        with mock.patch.object(sd, "create_session",
                               return_value=(mock.MagicMock(), "mock_engine")), \
             mock.patch.object(sd, "fetch_magnets") as mock_fetch:
            mock_fetch.return_value = {
                "url": "https://javdb.com/v/x",
                "code": "", "title": "", "error": "HTTP 403",
                "magnets": [],
            }
            resp = _call(self.state, {"cmd": "fetch_javdb", "request_id": "r1",
                                      "url": "https://javdb.com/v/x"})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "cloudflare_block")

    def test_fetch_uncaught_exception_redacted(self):
        with mock.patch.object(sd, "create_session",
                               side_effect=RuntimeError("secret-leak")):
            resp = _call(self.state, {"cmd": "fetch_javdb", "request_id": "r1",
                                      "url": "https://javdb.com/v/x"})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "network")
        # Message must not echo the raised exception text
        self.assertNotIn("secret-leak", resp["error"]["message"])


# ---------------------------------------------------------------------------
# resolve_magnet / resolve_magnets / forget_magnets
# ---------------------------------------------------------------------------

class ResolveMagnet(unittest.TestCase):
    def setUp(self):
        self.state = sd.DaemonState()
        self.full = (
            "magnet:?xt=urn:btih:"
            "0123456789abcdef&dn=test"
        )
        self.state.magnets["h-known"] = self.full

    def test_resolve_known(self):
        resp = _call(self.state, {"cmd": "resolve_magnet", "request_id": "r1",
                                  "handle_id": "h-known"})
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["magnet"], self.full)

    def test_resolve_unknown_returns_unknown_handle(self):
        resp = _call(self.state, {"cmd": "resolve_magnet", "request_id": "r1",
                                  "handle_id": "h-stale"})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "unknown_handle")

    def test_resolve_handle_id_must_be_string(self):
        resp = _call(self.state, {"cmd": "resolve_magnet", "request_id": "r1",
                                  "handle_id": 42})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "bad_request")


class ResolveMagnetsPlural(unittest.TestCase):
    def setUp(self):
        self.state = sd.DaemonState()
        self.state.magnets["h-1"] = "magnet:?xt=urn:btih:aaaa1111&dn=a"
        self.state.magnets["h-2"] = "magnet:?xt=urn:btih:bbbb2222&dn=b"

    def test_partial_success(self):
        resp = _call(self.state, {
            "cmd": "resolve_magnets", "request_id": "r1",
            "handle_ids": ["h-1", "h-stale", "h-2"],
        })
        self.assertTrue(resp["ok"])
        self.assertEqual(len(resp["magnets"]), 2)
        self.assertEqual(resp["unknown"], ["h-stale"])
        # Both magnets resolved
        magnets_by_id = {m["handle_id"]: m["magnet"] for m in resp["magnets"]}
        self.assertEqual(magnets_by_id["h-1"], self.state.magnets["h-1"])
        self.assertEqual(magnets_by_id["h-2"], self.state.magnets["h-2"])

    def test_handle_ids_must_be_list(self):
        resp = _call(self.state, {"cmd": "resolve_magnets", "request_id": "r1",
                                  "handle_ids": "not-a-list"})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "bad_request")


class ForgetMagnets(unittest.TestCase):
    def test_forget_clears_table(self):
        state = sd.DaemonState()
        state.magnets["h-1"] = "m1"
        state.magnets["h-2"] = "m2"
        resp = _call(state, {"cmd": "forget_magnets", "request_id": "r1"})
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["forgot"], 2)
        self.assertEqual(state.magnets, {})

    def test_forget_empty_returns_zero(self):
        state = sd.DaemonState()
        resp = _call(state, {"cmd": "forget_magnets", "request_id": "r1"})
        self.assertEqual(resp["forgot"], 0)


# ---------------------------------------------------------------------------
# update_settings / cancel
# ---------------------------------------------------------------------------

class UpdateSettings(unittest.TestCase):
    def test_replaces_settings(self):
        state = sd.DaemonState()
        state.settings = {"ui": {"theme": "light"}}
        resp = _call(state, {"cmd": "update_settings", "request_id": "r1",
                             "settings": {"ui": {"theme": "dark"}}})
        self.assertTrue(resp["ok"])
        self.assertEqual(state.settings, {"ui": {"theme": "dark"}})

    def test_no_settings_keeps_existing(self):
        state = sd.DaemonState()
        state.settings = {"a": 1}
        resp = _call(state, {"cmd": "update_settings", "request_id": "r1"})
        self.assertTrue(resp["ok"])
        self.assertEqual(state.settings, {"a": 1})


class Cancel(unittest.TestCase):
    def test_cancel_acknowledged(self):
        state = sd.DaemonState()
        resp = _call(state, {"cmd": "cancel", "request_id": "r1"})
        self.assertTrue(resp["ok"])


# ---------------------------------------------------------------------------
# Unknown / malformed
# ---------------------------------------------------------------------------

class UnknownCommand(unittest.TestCase):
    def test_unknown_returns_bad_request(self):
        state = sd.DaemonState()
        resp = _call(state, {"cmd": "no_such_command", "request_id": "r1"})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "bad_request")

    def test_missing_cmd_returns_bad_request(self):
        state = sd.DaemonState()
        resp = _call(state, {"request_id": "r1"})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "bad_request")


# ---------------------------------------------------------------------------
# Error envelope shape
# ---------------------------------------------------------------------------

class ErrorEnvelope(unittest.TestCase):
    def test_error_has_code_message_internal(self):
        state = sd.DaemonState()
        resp = _call(state, {"cmd": "no_such_command", "request_id": "r1"})
        self.assertFalse(resp["ok"])
        err = resp["error"]
        self.assertIn("code", err)
        self.assertIn("message", err)
        self.assertIn("internal", err)


# ---------------------------------------------------------------------------
# run_daemon — end-to-end via io.StringIO streams
# ---------------------------------------------------------------------------

class DaemonLoop(unittest.TestCase):
    def test_full_session_hello_handshake_ping_shutdown(self):
        commands = [
            {"cmd": "hello", "protocol_version": 1, "request_id": "r1"},
            {"cmd": "handshake", "request_id": "r2",
             "cookies": "k=v", "rd_token": None, "settings": {}, "paths": {}},
            {"cmd": "ping", "request_id": "r3"},
            {"cmd": "shutdown", "request_id": "r4"},
        ]
        stdin = io.StringIO("\n".join(json.dumps(c) for c in commands) + "\n")
        stdout = io.StringIO()
        rc = sd.run_daemon(stdin, stdout)
        self.assertEqual(rc, 0)

        responses = [json.loads(line) for line in stdout.getvalue().splitlines() if line]
        self.assertEqual(len(responses), 4)
        for i, expected_id in enumerate(["r1", "r2", "r3", "r4"]):
            self.assertEqual(responses[i]["request_id"], expected_id)
            self.assertTrue(responses[i]["ok"], f"response {i}: {responses[i]}")

    def test_invalid_json_produces_bad_request_envelope(self):
        stdin = io.StringIO("not-json\n")
        stdout = io.StringIO()
        sd.run_daemon(stdin, stdout)
        resp = json.loads(stdout.getvalue().splitlines()[0])
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "bad_request")

    def test_non_object_json_produces_bad_request_envelope(self):
        stdin = io.StringIO("[1, 2, 3]\n")
        stdout = io.StringIO()
        sd.run_daemon(stdin, stdout)
        resp = json.loads(stdout.getvalue().splitlines()[0])
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "bad_request")

    def test_eof_exits_cleanly(self):
        stdin = io.StringIO("")
        stdout = io.StringIO()
        rc = sd.run_daemon(stdin, stdout)
        self.assertEqual(rc, 0)
        self.assertEqual(stdout.getvalue(), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
