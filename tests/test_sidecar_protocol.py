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

# Load sidecar/sidecar.py under a unique module name. Historical note: a
# retired spike (spikes/python_sidecar_protocol/sidecar.py) used to live in
# the import path under the bare name `sidecar`; both that spike and its
# test (test_sidecar_cli.py) were removed in the M9 simplify pass. The
# explicit-path load is kept to avoid name shadowing if a future spike
# reintroduces a top-level `sidecar` module.
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

    def test_uppercase_scheme_redacted_to_canonical_scheme(self):
        full = "MAGNET:?xt=urn:btih:ABCDEF0123456789&dn=test"
        self.assertEqual(sd.redact_magnet(full),
                         "magnet:?xt=urn:btih:ABCDEF01...")

    def test_empty_returns_empty(self):
        self.assertEqual(sd.redact_magnet(""), "")

    def test_non_btih_magnet(self):
        self.assertEqual(sd.redact_magnet("magnet:?xt=urn:other"), "magnet:...")
        self.assertEqual(sd.redact_magnet("MAGNET:?xt=urn:other"), "magnet:...")

    def test_not_a_magnet(self):
        self.assertEqual(sd.redact_magnet("https://example.com"), "<not-a-magnet>")


class ExtractMagnetDn(unittest.TestCase):
    def test_extracts_plain_dn(self):
        self.assertEqual(
            sd.extract_magnet_dn("magnet:?xt=urn:btih:abc&dn=SNOS-192"),
            "SNOS-192",
        )

    def test_extracts_dn_with_javdb_prefix(self):
        self.assertEqual(
            sd.extract_magnet_dn("magnet:?xt=urn:btih:abc&dn=%5Bjavdb.com%5DSNOS-192"),
            "[javdb.com]SNOS-192",
        )

    def test_extracts_dn_with_plus_as_space(self):
        # JavDB sometimes emits `+` for spaces (form-encoded). unquote_plus
        # decodes those to literal spaces; raw `%20` would too.
        self.assertEqual(
            sd.extract_magnet_dn("magnet:?xt=urn:btih:abc&dn=Hello+World"),
            "Hello World",
        )

    def test_dn_position_independent(self):
        # `dn` can appear before `xt` in the param list.
        self.assertEqual(
            sd.extract_magnet_dn("magnet:?dn=ABCD-123&xt=urn:btih:abc&tr=udp://t"),
            "ABCD-123",
        )

    def test_no_dn_returns_empty(self):
        self.assertEqual(
            sd.extract_magnet_dn("magnet:?xt=urn:btih:abc&tr=udp://t"),
            "",
        )

    def test_empty_input_returns_empty(self):
        self.assertEqual(sd.extract_magnet_dn(""), "")


class ParseCookieString(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(
            sd.parse_cookie_string("a=1; b=2"),
            {"a": "1", "b": "2"},
        )

    def test_empty(self):
        self.assertEqual(sd.parse_cookie_string(""), {})

    def test_whitespace_only(self):
        self.assertEqual(sd.parse_cookie_string("   "), {})

    def test_skips_pairs_without_equals(self):
        self.assertEqual(
            sd.parse_cookie_string("foo; bar=baz; quux"),
            {"bar": "baz"},
        )

    def test_value_may_contain_equals(self):
        self.assertEqual(sd.parse_cookie_string("key=a=b=c"), {"key": "a=b=c"})

    def test_drops_pair_with_lf(self):
        # F-05: a `\n` inside a cookie KV is the shape of HTTP-header
        # injection / response splitting. The desktop app never
        # legitimately needs multi-line cookies; refuse the whole pair
        # rather than escape.
        self.assertEqual(
            sd.parse_cookie_string("good=1; bad=injected\nX-Evil: 1; ok=2"),
            {"good": "1", "ok": "2"},
        )

    def test_drops_pair_with_cr(self):
        self.assertEqual(
            sd.parse_cookie_string("good=1; bad=v\rX-Evil: 1"),
            {"good": "1"},
        )

    def test_drops_pair_with_crlf(self):
        self.assertEqual(
            sd.parse_cookie_string("good=1; bad=v\r\nX-Evil: 1"),
            {"good": "1"},
        )

    def test_drops_pair_when_lf_in_key(self):
        self.assertEqual(
            sd.parse_cookie_string("good=1; bad\nname=v"),
            {"good": "1"},
        )


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

    def test_handshake_drops_malformed_token(self):
        # F-04 cross-path leak: a dirty value from a corrupted keyring
        # entry (or a hand-crafted handshake) MUST NOT land in
        # state.rd_token; otherwise rd_send_magnet would feed it
        # straight into the Real-Debrid API on the very first call.
        # The handshake itself still succeeds (other state needs to be
        # set up); the rd_token slot just clears to empty so the user
        # sees `rd_no_token` instead of a 401. M1: a machine-readable
        # warning is included so a future UI/agent can prompt the user
        # to re-enter the token rather than silently failing later.
        state = sd.DaemonState()
        dirty = "abc-123"  # dash → fails format
        resp = _call(state, {
            "cmd": "handshake", "request_id": "r",
            "cookies": "k=v",
            "rd_token": dirty,
            "settings": {}, "paths": {},
        })
        self.assertTrue(resp["ok"])
        self.assertEqual(state.rd_token, "")
        self.assertTrue(state.handshake_done)
        # Warning is structured (list of dicts with stable `code`) so a
        # future UI can switch on it without regex-matching prose.
        warnings = resp.get("warnings")
        self.assertIsInstance(warnings, list)
        self.assertEqual(len(warnings), 1)
        self.assertEqual(warnings[0]["code"], "rd_token_format_invalid")
        self.assertIn("message", warnings[0])
        # The dirty token value MUST NOT round-trip back to the caller.
        serialized = json.dumps(resp)
        self.assertNotIn(dirty, serialized,
                         f"handshake response leaked the dirty token: {serialized}")

    def test_handshake_drops_overlong_token(self):
        state = sd.DaemonState()
        dirty = "a" * 256
        resp = _call(state, {
            "cmd": "handshake", "request_id": "r",
            "cookies": "",
            "rd_token": dirty,
            "settings": {}, "paths": {},
        })
        self.assertEqual(state.rd_token, "")
        # Same warning shape regardless of which rule failed.
        warnings = resp.get("warnings") or []
        self.assertEqual([w["code"] for w in warnings], ["rd_token_format_invalid"])
        self.assertNotIn(dirty, json.dumps(resp))

    def test_handshake_keeps_well_formed_token(self):
        # A 52-char ASCII-alphanumeric token (RD's documented shape)
        # must pass through the handshake guard unchanged. Without this
        # assertion the regression would be invisible: the test above
        # would pass even if we accidentally dropped every token.
        # And there must be NO warning — only the malformed path is
        # supposed to emit one.
        state = sd.DaemonState()
        good = "A" * 52
        resp = _call(state, {
            "cmd": "handshake", "request_id": "r",
            "cookies": "",
            "rd_token": good,
            "settings": {}, "paths": {},
        })
        self.assertEqual(state.rd_token, good)
        self.assertNotIn("warnings", resp)

    def test_handshake_null_token_does_not_warn(self):
        # Absent/null token is the steady-state for a fresh install —
        # it's "not configured", not "configured but dirty". Must be a
        # silent ok response so the UI doesn't surface a misleading
        # warning to a user who hasn't pasted a token yet.
        state = sd.DaemonState()
        resp = _call(state, {
            "cmd": "handshake", "request_id": "r",
            "cookies": "", "rd_token": None,
            "settings": {}, "paths": {},
        })
        self.assertTrue(resp["ok"])
        self.assertNotIn("warnings", resp)

    def test_handshake_rejects_non_string_token_without_typeerror(self):
        # M1.1 — defence against a hand-crafted handshake (or a future
        # mis-encoded Rust call) that ships rd_token as a non-string:
        # number, list, or object. Before the type guard, _is_valid_rd_token
        # would TypeError on len()/iteration and the dispatch boundary
        # would render an `internal` error envelope, losing the chance
        # to surface a clear warning. Now: handshake stays ok, state
        # clears to empty, response carries the same rd_token_format_invalid
        # warning shape as the string-malformed path, and the dirty value
        # is NEVER round-tripped back through IPC.
        cases = [
            ("number", 1234567890),
            ("negative_number", -987654321),
            ("float", 12.5),
            ("bool_true", True),
            ("list", ["DIRTY_TOKEN_SENTINEL_LIST"]),
            ("dict", {"DIRTY_KEY": "DIRTY_TOKEN_SENTINEL_DICT"}),
        ]
        for label, bad in cases:
            with self.subTest(label=label):
                state = sd.DaemonState()
                resp = _call(state, {
                    "cmd": "handshake", "request_id": f"r-{label}",
                    "cookies": "",
                    "rd_token": bad,
                    "settings": {}, "paths": {},
                })
                self.assertTrue(resp["ok"], f"{label}: {resp}")
                # Critical: handshake must NOT degrade into an `internal`
                # envelope from a TypeError in the validator.
                self.assertNotIn("error", resp)
                self.assertEqual(state.rd_token, "")
                self.assertTrue(state.handshake_done)
                warnings = resp.get("warnings") or []
                self.assertEqual(
                    [w["code"] for w in warnings],
                    ["rd_token_format_invalid"],
                    f"{label}: {warnings}",
                )
                # Leak check is scoped to the non-protocol part of the
                # response. Including `ok` and `request_id` would create
                # a false positive on small primitives — e.g. bad=True
                # serializes to "true", which always appears as
                # `"ok": true` in the envelope, regardless of leak status.
                payload = {k: v for k, v in resp.items()
                           if k not in ("ok", "request_id")}
                payload_blob = json.dumps(payload, ensure_ascii=False)
                self.assertNotIn(
                    json.dumps(bad, ensure_ascii=False),
                    payload_blob,
                    f"{label} leaked dirty value into response payload: {payload_blob}",
                )

    def test_handshake_empty_string_token_does_not_warn(self):
        # Explicit "" should behave like None — caller chose to send an
        # empty value rather than omit the field. Either way it's the
        # steady-state "not configured" shape, not a dirty token, so
        # the response must stay silent.
        state = sd.DaemonState()
        resp = _call(state, {
            "cmd": "handshake", "request_id": "r",
            "cookies": "", "rd_token": "",
            "settings": {}, "paths": {},
        })
        self.assertTrue(resp["ok"])
        self.assertEqual(state.rd_token, "")
        self.assertNotIn("warnings", resp)


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

    def test_fetch_rejects_http_scheme(self):
        # JavDB is https-only; accepting plain http:// would only enable
        # MITM against the user's session cookies. Sonar S5332 flags
        # http-accepting endpoints — keep this test as the contract.
        resp = _call(self.state, {"cmd": "fetch_javdb", "request_id": "r1",
                                  "url": "http://javdb.com/v/x"})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "bad_request")

    def test_fetch_rejects_non_javdb_host(self):
        # F-01: requests.Session.get(url, cookies=dict) does NOT scope
        # cookies by host — every cookie in the dict is appended to the
        # outgoing request regardless of `url`. Without an allowlist,
        # any HTTPS URL the caller supplies would leak `_jdb_session`
        # and `cf_clearance`. Reject anything that isn't javdb.com or
        # a .javdb.com subdomain.
        with mock.patch.object(sd, "create_session") as cs, \
             mock.patch.object(sd, "fetch_magnets") as fm:
            resp = _call(self.state, {"cmd": "fetch_javdb", "request_id": "r1",
                                      "url": "https://attacker.example/leak"})
            self.assertFalse(resp["ok"])
            self.assertEqual(resp["error"]["code"], "bad_request")
            # Critical: cookies must NOT reach the network layer.
            cs.assert_not_called()
            fm.assert_not_called()

    def test_fetch_rejects_lookalike_host(self):
        # `javdb.com.attacker.example` is a subdomain of attacker.example,
        # NOT of javdb.com. `endswith` without the leading dot would
        # have matched it — guard against the classic suffix bypass.
        resp = _call(self.state, {"cmd": "fetch_javdb", "request_id": "r1",
                                  "url": "https://evil.javdb.com.attacker.example/"})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "bad_request")

    def test_fetch_rejects_url_with_userinfo_pointing_elsewhere(self):
        # `https://javdb.com@attacker.example/...` parses with hostname
        # = attacker.example. Must be rejected.
        resp = _call(self.state, {"cmd": "fetch_javdb", "request_id": "r1",
                                  "url": "https://javdb.com@attacker.example/p"})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "bad_request")

    def test_fetch_accepts_subdomain_of_javdb(self):
        # `*.javdb.com` is allowed (mirrors, regional fronts).
        with mock.patch.object(sd, "create_session",
                               return_value=(mock.MagicMock(), "mock_engine")), \
             mock.patch.object(sd, "fetch_magnets") as mock_fetch:
            mock_fetch.return_value = {
                "url": "https://en.javdb.com/v/x", "code": "", "title": "",
                "error": "", "magnets": [],
            }
            resp = _call(self.state, {"cmd": "fetch_javdb", "request_id": "r1",
                                      "url": "https://en.javdb.com/v/x"})
        self.assertTrue(resp["ok"])

    def test_fetch_host_match_is_case_insensitive(self):
        with mock.patch.object(sd, "create_session",
                               return_value=(mock.MagicMock(), "mock_engine")), \
             mock.patch.object(sd, "fetch_magnets") as mock_fetch:
            mock_fetch.return_value = {
                "url": "https://JAVDB.com/v/x", "code": "", "title": "",
                "error": "", "magnets": [],
            }
            resp = _call(self.state, {"cmd": "fetch_javdb", "request_id": "r1",
                                      "url": "https://JAVDB.com/v/x"})
        self.assertTrue(resp["ok"])

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

    def test_is_javdb_host_empty_returns_false(self):
        # Empty / None hostnames (urlparse on a malformed URL) must be
        # rejected — never matched against the allowlist.
        self.assertFalse(sd._is_javdb_host(""))

    def test_fetch_malformed_url_rejected(self):
        # urllib.parse.urlparse raises ValueError on certain IPv6-like
        # inputs ("https://["). The handler must convert that into a
        # bad_request error envelope, not let it bubble up.
        with mock.patch.object(sd.urllib.parse, "urlparse",
                               side_effect=ValueError("malformed")):
            resp = _call(self.state, {"cmd": "fetch_javdb", "request_id": "r1",
                                      "url": "https://[/v/x"})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "bad_request")

    def test_fetch_non_403_network_error_passes_through(self):
        # Errors that don't contain "403" map to the generic network
        # error code, not cloudflare_block.
        with mock.patch.object(sd, "create_session",
                               return_value=(mock.MagicMock(), "mock_engine")), \
             mock.patch.object(sd, "fetch_magnets") as mock_fetch:
            mock_fetch.return_value = {
                "url": "https://javdb.com/v/x",
                "code": "", "title": "", "error": "HTTP 500 server error",
                "magnets": [],
            }
            resp = _call(self.state, {"cmd": "fetch_javdb", "request_id": "r1",
                                      "url": "https://javdb.com/v/x"})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "network")
        self.assertIn("HTTP 500", resp["error"]["message"])


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

    def test_non_string_handle_id_becomes_unknown(self):
        # If the caller passes a non-string entry (e.g. accidentally an int)
        # it's coerced to str and reported as unknown — never crashes.
        resp = _call(self.state, {
            "cmd": "resolve_magnets", "request_id": "r1",
            "handle_ids": ["h-1", 42, None, "h-2"],
        })
        self.assertTrue(resp["ok"])
        self.assertEqual(len(resp["magnets"]), 2)
        # Both non-string entries surface in "unknown" as their str() form.
        self.assertIn("42", resp["unknown"])
        self.assertIn("None", resp["unknown"])


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

    def test_non_string_cmd_returns_bad_request(self):
        # cmd field present but not a string → bad_request, not internal.
        state = sd.DaemonState()
        resp = _call(state, {"cmd": 123, "request_id": "r1"})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "bad_request")


class DispatchInternalError(unittest.TestCase):
    """`dispatch` is the IPC boundary that catches uncaught handler
    exceptions and renders them as `internal` envelopes — exception bodies
    must NEVER cross the boundary verbatim (could contain tokens, cookies,
    paths). Test by patching a registered handler to raise.

    Contract (see `_err` + the dispatch except-clause):
      - code = "internal"
      - message = "<ExcType>: <redacted>" (type name is OK; body is NOT)
      - internal = "" (default; the redacted marker stays in `message`)
    """

    def test_handler_exception_rendered_as_internal(self):
        state = sd.DaemonState()
        # cmd_ping always succeeds; swap its DISPATCH entry to a raiser.
        original = sd.DISPATCH["ping"]
        sd.DISPATCH["ping"] = mock.MagicMock(
            side_effect=RuntimeError("secret-traceback-leak-XYZ"))
        try:
            resp = _call(state, {"cmd": "ping", "request_id": "r"})
        finally:
            sd.DISPATCH["ping"] = original
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "internal")
        self.assertEqual(resp["request_id"], "r")
        # Type marker lives in `message` (e.g. "RuntimeError: <redacted>"),
        # which is fine — the rule is "don't leak the secret body".
        self.assertIn("RuntimeError", resp["error"]["message"])
        self.assertIn("<redacted>", resp["error"]["message"])
        # Neither field may echo the raised exception body.
        self.assertNotIn("secret-traceback-leak-XYZ", resp["error"]["message"])
        self.assertNotIn("secret-traceback-leak-XYZ", resp["error"]["internal"])


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
        self.assertIsNone(sd.run_daemon(stdin, stdout))

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
        self.assertIsNone(sd.run_daemon(stdin, stdout))
        self.assertEqual(stdout.getvalue(), "")

    def test_blank_lines_between_commands_are_skipped(self):
        # Mixing blank lines and whitespace-only lines into the stream must
        # not produce error envelopes — they are simply skipped. Without
        # this, an editor adding trailing newlines could spam bad_request
        # envelopes back to the Rust caller.
        commands = [
            {"cmd": "ping", "request_id": "r1"},
            {"cmd": "shutdown", "request_id": "r2"},
        ]
        stdin = io.StringIO(
            json.dumps(commands[0]) + "\n"
            "\n"        # blank line
            "   \n"     # whitespace only
            + json.dumps(commands[1]) + "\n"
        )
        stdout = io.StringIO()
        self.assertIsNone(sd.run_daemon(stdin, stdout))
        responses = [json.loads(line) for line in stdout.getvalue().splitlines() if line]
        # Exactly two responses — the two commands. Blank lines emit nothing.
        self.assertEqual(len(responses), 2)
        self.assertEqual(responses[0]["request_id"], "r1")
        self.assertEqual(responses[1]["request_id"], "r2")
        for r in responses:
            self.assertTrue(r["ok"])

    def test_run_daemon_stops_after_shutdown_even_if_more_lines_follow(self):
        # Lines after shutdown should be ignored; the daemon must exit
        # cleanly at the shutdown ack — anything else would mean a hung
        # session in a misbehaving stdin.
        stdin = io.StringIO(
            json.dumps({"cmd": "shutdown", "request_id": "r"}) + "\n"
            + json.dumps({"cmd": "ping", "request_id": "should-not-fire"}) + "\n"
        )
        stdout = io.StringIO()
        self.assertIsNone(sd.run_daemon(stdin, stdout))
        responses = [json.loads(line) for line in stdout.getvalue().splitlines() if line]
        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0]["request_id"], "r")


# ---------------------------------------------------------------------------
# M5: Real-Debrid commands
#
# realdebrid.RealDebrid is mocked at the import boundary so no HTTP / token /
# network is exercised. We assert the protocol envelope, not the RD library.
# ---------------------------------------------------------------------------


def _rd_state(token: str = "tok-x", settings: dict | None = None) -> "sd.DaemonState":
    state = sd.DaemonState()
    state.handshake_done = True
    state.rd_token = token
    state.settings = settings or {"rd": {"file_pick": "smart", "min_size_mb": 500,
                                          "cache_wait_seconds": 15}}
    return state


class RdUser(unittest.TestCase):
    def test_returns_user_snapshot_on_success(self):
        state = _rd_state()
        fake = mock.MagicMock()
        fake._request.return_value = {
            "username": "alice", "type": "premium",
            "expiration": "2026-12-01", "points": 9999,
        }
        with mock.patch.object(sd, "_rd_client", return_value=fake):
            resp = _call(state, {"cmd": "rd_user", "request_id": "r"})
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["user"]["username"], "alice")
        self.assertEqual(resp["user"]["type"], "premium")

    def test_no_token_returns_rd_no_token(self):
        state = sd.DaemonState()
        state.handshake_done = True
        state.rd_token = ""
        resp = _call(state, {"cmd": "rd_user", "request_id": "r"})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "rd_no_token")

    def test_token_override_probes_without_state_token(self):
        state = sd.DaemonState()
        state.handshake_done = True  # but state.rd_token = ""
        fake = mock.MagicMock()
        fake._request.return_value = {"username": "bob", "type": "premium",
                                       "expiration": "", "points": 0}
        with mock.patch.object(sd, "_rd_client", return_value=fake):
            resp = _call(state, {
                "cmd": "rd_user", "request_id": "r", "token": "candidate",
            })
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["user"]["username"], "bob")

    def test_invalid_token_classified_as_rd_token_invalid(self):
        from realdebrid import RealDebridError
        state = _rd_state()
        with mock.patch.object(sd, "_rd_client",
                               side_effect=RealDebridError("HTTP 401: token 無效或已過期")):
            resp = _call(state, {"cmd": "rd_user", "request_id": "r"})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "rd_token_invalid")

    def test_premium_required_classified(self):
        from realdebrid import RealDebridError
        state = _rd_state()
        with mock.patch.object(sd, "_rd_client",
                               side_effect=RealDebridError("HTTP 403: 帳號權限不足")):
            resp = _call(state, {"cmd": "rd_user", "request_id": "r"})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "rd_premium_required")

    def test_token_must_be_string_when_provided(self):
        # Non-string token override → bad_request, regardless of state.rd_token.
        state = _rd_state()
        resp = _call(state, {"cmd": "rd_user", "request_id": "r", "token": 1234})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "bad_request")

    def test_internal_exception_redacted(self):
        # A non-RealDebridError that escapes _rd_client must bucket to
        # rd_internal and must NOT echo the exception body in the envelope.
        state = _rd_state()
        with mock.patch.object(sd, "_rd_client",
                               side_effect=RuntimeError("secret-payload-XYZ")):
            resp = _call(state, {"cmd": "rd_user", "request_id": "r"})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], sd._RD_ERR_INTERNAL)
        self.assertNotIn("secret-payload-XYZ", resp["error"]["message"])
        self.assertNotIn("secret-payload-XYZ", resp["error"]["internal"])


class RdSetToken(unittest.TestCase):
    def _post_handshake_state(self):
        state = sd.DaemonState()
        state.handshake_done = True
        return state

    def test_set_token_updates_state(self):
        state = self._post_handshake_state()
        # 52-char ASCII-alphanumeric matches the current RD token shape.
        token = "A" * 52
        resp = _call(state, {"cmd": "rd_set_token", "request_id": "r", "token": token})
        self.assertTrue(resp["ok"])
        self.assertTrue(resp["set"])
        self.assertEqual(state.rd_token, token)

    def test_null_token_clears_state(self):
        state = self._post_handshake_state()
        state.rd_token = "old"
        resp = _call(state, {"cmd": "rd_set_token", "request_id": "r", "token": None})
        self.assertTrue(resp["ok"])
        self.assertFalse(resp["set"])
        self.assertEqual(state.rd_token, "")

    def test_empty_string_token_clears_state(self):
        # rd_save_token sends `{ "token": Null }` on empty input, but be
        # defensive: an explicit empty string is treated like null —
        # clear, not format error — so callers don't get a confusing
        # `rd_token_format_invalid` from a clear gesture.
        state = self._post_handshake_state()
        state.rd_token = "old"
        resp = _call(state, {"cmd": "rd_set_token", "request_id": "r", "token": ""})
        self.assertTrue(resp["ok"])
        self.assertFalse(resp["set"])
        self.assertEqual(state.rd_token, "")

    def test_non_string_token_rejected(self):
        state = self._post_handshake_state()
        resp = _call(state, {"cmd": "rd_set_token", "request_id": "r", "token": 123})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "bad_request")

    def test_requires_handshake(self):
        # F-17: align with rd_send_magnet — without handshake, calling
        # rd_set_token must error. Defence in depth against any future
        # caller that tries to push a token before the protocol is
        # established.
        state = sd.DaemonState()  # handshake_done = False
        resp = _call(state, {
            "cmd": "rd_set_token", "request_id": "r", "token": "A" * 52,
        })
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "bad_request")
        # And the token must NOT have been stored.
        self.assertEqual(state.rd_token, "")

    def test_rejects_token_with_dash(self):
        # F-04: RD tokens are ASCII-alphanumeric. A paste that brings in
        # punctuation (a stray dash, a wrapping comment, etc.) must be
        # refused so a malformed value never gets persisted as a token.
        state = self._post_handshake_state()
        resp = _call(state, {
            "cmd": "rd_set_token", "request_id": "r", "token": "abc-123",
        })
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "bad_request")
        self.assertEqual(state.rd_token, "")

    def test_rejects_token_with_whitespace(self):
        state = self._post_handshake_state()
        resp = _call(state, {
            "cmd": "rd_set_token", "request_id": "r", "token": "abc 123",
        })
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "bad_request")

    def test_rejects_token_with_newline(self):
        # Most common copy-paste accident; explicit assertion.
        state = self._post_handshake_state()
        resp = _call(state, {
            "cmd": "rd_set_token", "request_id": "r", "token": "abc\n",
        })
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "bad_request")

    def test_rejects_overlong_token(self):
        state = self._post_handshake_state()
        resp = _call(state, {
            "cmd": "rd_set_token", "request_id": "r", "token": "a" * 256,
        })
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "bad_request")
        self.assertEqual(state.rd_token, "")

    def test_rejects_non_ascii_token(self):
        # Unicode digits (e.g. fullwidth) are alnum but NOT ASCII.
        state = self._post_handshake_state()
        resp = _call(state, {
            "cmd": "rd_set_token", "request_id": "r", "token": "ＡＢＣ123",
        })
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "bad_request")


class SetCookies(unittest.TestCase):
    """Cookies live-update path. M9 added this so a cf_clearance refresh
    doesn't need a sidecar restart — the Rust ``migrate_cookies_now`` /
    ``save_cookies`` commands push the new value through this command
    so ``state.cookies`` is current before the next ``fetch_javdb``.
    """

    def _post_handshake_state(self):
        state = sd.DaemonState()
        state.handshake_done = True
        return state

    def test_set_cookies_updates_state(self):
        state = self._post_handshake_state()
        resp = _call(state, {
            "cmd": "set_cookies", "request_id": "r",
            "cookies": "_jdb_session=abc; cf_clearance=xyz; locale=zh",
        })
        self.assertTrue(resp["ok"])
        self.assertTrue(resp["set"])
        self.assertEqual(state.cookies["_jdb_session"], "abc")
        self.assertEqual(state.cookies["cf_clearance"], "xyz")
        self.assertEqual(state.cookies["locale"], "zh")

    def test_set_cookies_replaces_prior_state(self):
        # A subsequent set fully replaces — not merges — so an updated
        # cf_clearance overwrites the previous one cleanly.
        state = self._post_handshake_state()
        state.cookies = {"_jdb_session": "old", "cf_clearance": "stale"}
        resp = _call(state, {
            "cmd": "set_cookies", "request_id": "r",
            "cookies": "_jdb_session=new; cf_clearance=fresh",
        })
        self.assertTrue(resp["ok"])
        self.assertEqual(state.cookies, {
            "_jdb_session": "new",
            "cf_clearance": "fresh",
        })

    def test_null_cookies_clears_state(self):
        state = self._post_handshake_state()
        state.cookies = {"_jdb_session": "old"}
        resp = _call(state, {
            "cmd": "set_cookies", "request_id": "r", "cookies": None,
        })
        self.assertTrue(resp["ok"])
        self.assertFalse(resp["set"])
        self.assertEqual(state.cookies, {})

    def test_empty_string_clears_state(self):
        state = self._post_handshake_state()
        state.cookies = {"_jdb_session": "old"}
        resp = _call(state, {
            "cmd": "set_cookies", "request_id": "r", "cookies": "   ",
        })
        self.assertTrue(resp["ok"])
        self.assertFalse(resp["set"])
        self.assertEqual(state.cookies, {})

    def test_non_string_rejected(self):
        state = self._post_handshake_state()
        resp = _call(state, {
            "cmd": "set_cookies", "request_id": "r", "cookies": 123,
        })
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "bad_request")
        # state must be untouched
        self.assertEqual(state.cookies, {})

    def test_requires_handshake(self):
        # F-17 mirror: without handshake the daemon refuses cookie updates
        # so an out-of-protocol caller can't seed cookies before identity
        # is established.
        state = sd.DaemonState()  # handshake_done = False
        resp = _call(state, {
            "cmd": "set_cookies", "request_id": "r",
            "cookies": "_jdb_session=abc",
        })
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "bad_request")
        self.assertEqual(state.cookies, {})

    def test_crlf_pairs_dropped(self):
        # F-05 lives in parse_cookie_string; this confirms the live-update
        # path also benefits from it (header-injection defence in depth).
        state = self._post_handshake_state()
        resp = _call(state, {
            "cmd": "set_cookies", "request_id": "r",
            "cookies": "good=ok; bad=injection\nattack; other=fine",
        })
        self.assertTrue(resp["ok"])
        self.assertEqual(state.cookies, {"good": "ok", "other": "fine"})


class RdSendMagnet(unittest.TestCase):
    def _state_with_magnet(self):
        state = _rd_state()
        state.magnets["h-1"] = "magnet:?xt=urn:btih:abc&dn=test"
        return state

    def test_handshake_required(self):
        state = sd.DaemonState()
        # handshake_done = False
        state.rd_token = "tok"
        resp = _call(state, {"cmd": "rd_send_magnet", "request_id": "r",
                              "handle_id": "h-1"})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "bad_request")

    def test_no_token_returns_rd_no_token(self):
        state = self._state_with_magnet()
        state.rd_token = ""
        resp = _call(state, {"cmd": "rd_send_magnet", "request_id": "r",
                              "handle_id": "h-1"})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "rd_no_token")

    def test_unknown_handle(self):
        state = self._state_with_magnet()
        resp = _call(state, {"cmd": "rd_send_magnet", "request_id": "r",
                              "handle_id": "h-missing"})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "unknown_handle")

    def test_handle_id_must_be_string(self):
        state = self._state_with_magnet()
        # Numeric handle id → bad_request (separate from unknown_handle so
        # the frontend can flag a protocol mistake vs. a missed entry).
        resp = _call(state, {"cmd": "rd_send_magnet", "request_id": "r",
                              "handle_id": 42})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "bad_request")

    def test_completed_path(self):
        state = self._state_with_magnet()
        fake = mock.MagicMock()
        fake.process_magnet.return_value = {
            "status": "completed",
            "torrent_id": "ABC123",
            "name": "test torrent",
            "links": [{"original": "x", "download": "https://rd/y",
                       "filename": "f.mp4", "filesize": 1234, "streamable": 0}],
        }
        with mock.patch.object(sd, "_rd_client", return_value=fake):
            resp = _call(state, {"cmd": "rd_send_magnet", "request_id": "r",
                                  "handle_id": "h-1"})
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["status"], "completed")
        self.assertEqual(resp["torrent_id"], "ABC123")
        self.assertEqual(len(resp["links"]), 1)
        # process_magnet called with strategy from settings
        kwargs = fake.process_magnet.call_args.kwargs
        self.assertEqual(kwargs["strategy"], "smart")
        self.assertEqual(kwargs["cache_wait"], 15)

    def test_pending_path(self):
        state = self._state_with_magnet()
        fake = mock.MagicMock()
        fake.process_magnet.return_value = {
            "status": "pending",
            "torrent_id": "XYZ",
            "name": "n",
            "rd_status": "downloading",
            "progress": 12.5,
            "files_selected": True,
        }
        with mock.patch.object(sd, "_rd_client", return_value=fake):
            resp = _call(state, {"cmd": "rd_send_magnet", "request_id": "r",
                                  "handle_id": "h-1"})
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["status"], "pending")
        self.assertEqual(resp["torrent_id"], "XYZ")
        self.assertEqual(resp["rd_status"], "downloading")
        self.assertEqual(resp["progress"], 12.5)
        self.assertEqual(resp["strategy"], "smart")
        self.assertTrue(resp["files_selected"])

    def test_strategy_override_in_request(self):
        state = self._state_with_magnet()
        fake = mock.MagicMock()
        fake.process_magnet.return_value = {"status": "completed",
                                             "torrent_id": "T", "name": "n",
                                             "links": []}
        with mock.patch.object(sd, "_rd_client", return_value=fake):
            _call(state, {"cmd": "rd_send_magnet", "request_id": "r",
                           "handle_id": "h-1", "strategy": "largest",
                           "cache_wait": 5, "min_size_mb": 1000})
        # Override flowed through to process_magnet
        kwargs = fake.process_magnet.call_args.kwargs
        self.assertEqual(kwargs["strategy"], "largest")
        self.assertEqual(kwargs["cache_wait"], 5)

    def test_magnet_error_classified(self):
        from realdebrid import RealDebridError
        state = self._state_with_magnet()
        with mock.patch.object(sd, "_rd_client",
                               side_effect=RealDebridError("磁力解析失敗: bad torrent")):
            resp = _call(state, {"cmd": "rd_send_magnet", "request_id": "r",
                                  "handle_id": "h-1"})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "rd_magnet_error")


class RdCheckPending(unittest.TestCase):
    def test_no_token(self):
        state = sd.DaemonState()
        state.handshake_done = True
        state.rd_token = ""
        resp = _call(state, {"cmd": "rd_check_pending", "request_id": "r",
                              "torrent_id": "ABC"})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "rd_no_token")

    def test_torrent_id_required(self):
        state = _rd_state()
        resp = _call(state, {"cmd": "rd_check_pending", "request_id": "r"})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "bad_request")

    def test_completed_returns_links(self):
        state = _rd_state()
        fake = mock.MagicMock()
        fake.check_torrent.return_value = {
            "status": "completed", "name": "n",
            "links": [{"original": "x", "download": "y",
                       "filename": "f", "filesize": 0, "streamable": 0}],
        }
        with mock.patch.object(sd, "_rd_client", return_value=fake):
            resp = _call(state, {"cmd": "rd_check_pending", "request_id": "r",
                                  "torrent_id": "ABC"})
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["status"], "completed")
        self.assertEqual(resp["torrent_id"], "ABC")
        self.assertEqual(len(resp["links"]), 1)
        # Magnet param was empty (we don't store magnet in pending records)
        kwargs = fake.check_torrent.call_args.kwargs
        self.assertEqual(kwargs["magnet"], "")

    def test_still_pending(self):
        state = _rd_state()
        fake = mock.MagicMock()
        fake.check_torrent.return_value = {
            "status": "pending", "name": "n",
            "rd_status": "downloading", "progress": 30,
        }
        with mock.patch.object(sd, "_rd_client", return_value=fake):
            resp = _call(state, {"cmd": "rd_check_pending", "request_id": "r",
                                  "torrent_id": "ABC"})
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["status"], "pending")
        self.assertEqual(resp["progress"], 30)

    def test_missing_torrent(self):
        state = _rd_state()
        fake = mock.MagicMock()
        fake.check_torrent.return_value = {"status": "missing", "torrent_id": "ABC"}
        with mock.patch.object(sd, "_rd_client", return_value=fake):
            resp = _call(state, {"cmd": "rd_check_pending", "request_id": "r",
                                  "torrent_id": "ABC"})
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["status"], "missing")

    def test_torrent_id_non_string_returns_bad_request(self):
        state = _rd_state()
        resp = _call(state, {"cmd": "rd_check_pending", "request_id": "r",
                              "torrent_id": 42})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "bad_request")

    def test_torrent_id_empty_string_returns_bad_request(self):
        state = _rd_state()
        resp = _call(state, {"cmd": "rd_check_pending", "request_id": "r",
                              "torrent_id": ""})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "bad_request")

    def test_realdebrid_error_classified(self):
        # RealDebridError from check_torrent → mapped via _classify_rd_error
        # (e.g. 401 → rd_token_invalid).
        from realdebrid import RealDebridError
        state = _rd_state()
        with mock.patch.object(sd, "_rd_client",
                               side_effect=RealDebridError("HTTP 401: token 無效")):
            resp = _call(state, {"cmd": "rd_check_pending", "request_id": "r",
                                  "torrent_id": "ABC"})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], sd._RD_ERR_AUTH)

    def test_internal_exception_redacted(self):
        # Non-RD exception → rd_internal envelope with body redacted.
        state = _rd_state()
        with mock.patch.object(sd, "_rd_client",
                               side_effect=RuntimeError("hidden-trace-XYZ")):
            resp = _call(state, {"cmd": "rd_check_pending", "request_id": "r",
                                  "torrent_id": "ABC"})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], sd._RD_ERR_INTERNAL)
        self.assertNotIn("hidden-trace-XYZ", resp["error"]["message"])
        self.assertNotIn("hidden-trace-XYZ", resp["error"]["internal"])


class RdDispatchRegistration(unittest.TestCase):
    def test_all_rd_commands_dispatchable(self):
        for cmd in ("rd_user", "rd_set_token", "rd_send_magnet", "rd_check_pending"):
            self.assertIn(cmd, sd.DISPATCH, f"{cmd} missing from DISPATCH")


class RegisterMagnets(unittest.TestCase):
    """Paste-raw-magnet path: register magnets straight into the handle table
    without going through a JavDB fetch."""

    def test_registers_unique_magnets(self):
        state = sd.DaemonState()
        m1 = "magnet:?xt=urn:btih:0123456789abcdef&dn=A"
        m2 = "magnet:?xt=urn:btih:fedcba9876543210&dn=B"
        resp = _call(state, {
            "cmd": "register_magnets", "request_id": "r",
            "magnets": [m1, m2],
        })
        self.assertTrue(resp["ok"])
        self.assertEqual(len(resp["registered"]), 2)
        self.assertEqual(resp["invalid"], [])
        # Both got distinct handle_ids and the table now holds the full URIs
        ids = {r["handle_id"] for r in resp["registered"]}
        self.assertEqual(len(ids), 2)
        self.assertEqual(state.magnets[resp["registered"][0]["handle_id"]], m1)
        self.assertEqual(state.magnets[resp["registered"][1]["handle_id"]], m2)
        # And only the redacted form is returned
        self.assertTrue(
            resp["registered"][0]["magnet_redacted"].startswith("magnet:?xt=urn:btih:01234567")
        )

    def test_dedupes_identical_magnets(self):
        state = sd.DaemonState()
        m = "magnet:?xt=urn:btih:0123456789abcdef&dn=Same"
        resp = _call(state, {
            "cmd": "register_magnets", "request_id": "r",
            "magnets": [m, m, "  " + m + "  "],
        })
        self.assertTrue(resp["ok"])
        self.assertEqual(len(resp["registered"]), 3)
        # Only one handle in the state table
        self.assertEqual(len(state.magnets), 1)
        # All three entries share the same handle_id
        ids = {r["handle_id"] for r in resp["registered"]}
        self.assertEqual(len(ids), 1)
        # The 2nd and 3rd entries are flagged deduped
        self.assertFalse(resp["registered"][0]["deduped"])
        self.assertTrue(resp["registered"][1]["deduped"])
        self.assertTrue(resp["registered"][2]["deduped"])

    def test_invalid_inputs_separated(self):
        state = sd.DaemonState()
        m_ok = "magnet:?xt=urn:btih:abc&dn=X"
        resp = _call(state, {
            "cmd": "register_magnets", "request_id": "r",
            "magnets": [m_ok, "https://not-a-magnet.example", "", 123],
        })
        self.assertTrue(resp["ok"])
        self.assertEqual(len(resp["registered"]), 1)
        self.assertEqual(len(resp["invalid"]), 3)
        # Only the valid one ended up in the handle table
        self.assertEqual(len(state.magnets), 1)

    def test_non_list_input_returns_bad_request(self):
        state = sd.DaemonState()
        resp = _call(state, {
            "cmd": "register_magnets", "request_id": "r",
            "magnets": "magnet:?xt=urn:btih:abc",
        })
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "bad_request")

    def test_empty_list_returns_empty_arrays(self):
        state = sd.DaemonState()
        resp = _call(state, {
            "cmd": "register_magnets", "request_id": "r", "magnets": [],
        })
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["registered"], [])
        self.assertEqual(resp["invalid"], [])
        self.assertEqual(len(state.magnets), 0)

    def test_dispatch_registered(self):
        self.assertIn("register_magnets", sd.DISPATCH)

    def test_register_returns_dn_as_name(self):
        """`register_magnets` should expose each input's `dn=` value as
        `name` so the frontend can use it for per-row display in the
        paste-magnet flow."""
        state = sd.DaemonState()
        resp = _call(state, {
            "cmd": "register_magnets", "request_id": "r",
            "magnets": [
                "magnet:?xt=urn:btih:0000000000000000000000000000000000000001&dn=ABC-123",
                "magnet:?xt=urn:btih:0000000000000000000000000000000000000002&dn=%5Bjavdb.com%5DDEF-456",
                "magnet:?xt=urn:btih:0000000000000000000000000000000000000003",  # no dn
            ],
        })
        self.assertTrue(resp["ok"])
        self.assertEqual(len(resp["registered"]), 3)
        self.assertEqual(resp["registered"][0]["name"], "ABC-123")
        self.assertEqual(resp["registered"][1]["name"], "[javdb.com]DEF-456")
        self.assertEqual(resp["registered"][2]["name"], "")

    def test_same_magnet_across_requests_reuses_handle(self):
        """Magnet registered in request A, then again in request B → same
        handle, B's row flagged deduped. Prevents the bug where the same
        btih ended up with two handles → two RD sends."""
        state = sd.DaemonState()
        m = "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&dn=Cross"
        resp_a = _call(state, {
            "cmd": "register_magnets", "request_id": "a", "magnets": [m],
        })
        self.assertTrue(resp_a["ok"])
        h_a = resp_a["registered"][0]["handle_id"]
        self.assertFalse(resp_a["registered"][0]["deduped"])

        resp_b = _call(state, {
            "cmd": "register_magnets", "request_id": "b", "magnets": [m],
        })
        self.assertTrue(resp_b["ok"])
        h_b = resp_b["registered"][0]["handle_id"]
        self.assertEqual(h_a, h_b)
        self.assertTrue(resp_b["registered"][0]["deduped"])
        # Only ONE entry in the forward table even though we called twice.
        self.assertEqual(len(state.magnets), 1)

    def test_mixed_batch_existing_plus_new(self):
        """Batch containing one already-registered magnet plus one new
        magnet: existing returns its prior handle with deduped=True; new
        gets a fresh handle with deduped=False."""
        state = sd.DaemonState()
        m_old = "magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa&dn=Old"
        m_new = "magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb&dn=New"
        first = _call(state, {
            "cmd": "register_magnets", "request_id": "1", "magnets": [m_old],
        })
        h_old = first["registered"][0]["handle_id"]

        mixed = _call(state, {
            "cmd": "register_magnets", "request_id": "2",
            "magnets": [m_old, m_new],
        })
        self.assertTrue(mixed["ok"])
        self.assertEqual(len(mixed["registered"]), 2)
        rows = {r["handle_id"]: r for r in mixed["registered"]}
        # Old re-appears with same handle + deduped=True
        self.assertIn(h_old, rows)
        self.assertTrue(rows[h_old]["deduped"])
        # New got a fresh handle + deduped=False
        other_ids = [hid for hid in rows if hid != h_old]
        self.assertEqual(len(other_ids), 1)
        self.assertFalse(rows[other_ids[0]]["deduped"])
        # Forward table has both entries; reverse table is consistent.
        self.assertEqual(len(state.magnets), 2)
        self.assertEqual(len(state.magnet_to_handle), 2)

    def test_same_btih_different_dn_dedupes_to_same_handle(self):
        """Same BTIH but different display names → same handle. JavDB
        sometimes emits different `dn=` for the same hash; before the
        BTIH-keyed dedupe these would have become two handles and
        double-billed RD."""
        state = sd.DaemonState()
        hash40 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        m_a = f"magnet:?xt=urn:btih:{hash40}&dn=Title-A"
        m_b = f"magnet:?xt=urn:btih:{hash40}&dn=Title-B"
        resp = _call(state, {
            "cmd": "register_magnets", "request_id": "r",
            "magnets": [m_a, m_b],
        })
        self.assertTrue(resp["ok"])
        self.assertEqual(len(resp["registered"]), 2)
        # Same handle for both rows; second is deduped.
        self.assertEqual(
            resp["registered"][0]["handle_id"],
            resp["registered"][1]["handle_id"],
        )
        self.assertFalse(resp["registered"][0]["deduped"])
        self.assertTrue(resp["registered"][1]["deduped"])
        # Forward table holds ONE entry — only the first-seen original
        # text is retained; that's fine since both point at the same
        # torrent content.
        self.assertEqual(len(state.magnets), 1)

    def test_same_btih_different_hash_case_dedupes(self):
        """Hex hash case differences (uppercase vs lowercase) must not
        split into two handles."""
        state = sd.DaemonState()
        lower = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        upper = lower.upper()
        m_lo = f"magnet:?xt=urn:btih:{lower}&dn=lo"
        m_up = f"magnet:?xt=urn:btih:{upper}&dn=up"
        resp = _call(state, {
            "cmd": "register_magnets", "request_id": "r",
            "magnets": [m_lo, m_up],
        })
        self.assertEqual(
            resp["registered"][0]["handle_id"],
            resp["registered"][1]["handle_id"],
        )
        self.assertTrue(resp["registered"][1]["deduped"])
        self.assertEqual(len(state.magnets), 1)

    def test_same_btih_different_parameter_order_dedupes(self):
        """Parameter order in the URI must not affect dedupe — `xt`
        before or after `dn` should still match."""
        state = sd.DaemonState()
        h = "cccccccccccccccccccccccccccccccccccccccc"
        first = _call(state, {
            "cmd": "register_magnets", "request_id": "1",
            "magnets": [f"magnet:?xt=urn:btih:{h}&dn=N&tr=udp://t1"],
        })
        second = _call(state, {
            "cmd": "register_magnets", "request_id": "2",
            "magnets": [f"magnet:?dn=N&tr=udp://t1&xt=urn:btih:{h}"],
        })
        self.assertEqual(
            first["registered"][0]["handle_id"],
            second["registered"][0]["handle_id"],
        )
        self.assertTrue(second["registered"][0]["deduped"])

    def test_dedupe_key_falls_back_when_no_btih(self):
        """No parseable BTIH → fall back to the trimmed full string so
        dedupe still works conservatively. Caller may legitimately
        register an unusual magnet:?xt=urn:sha1:... etc."""
        # Direct unit test of the pure helper (no state involved).
        self.assertEqual(
            sd._magnet_dedupe_key("magnet:?xt=urn:btih:DEADBEEF&dn=A"),
            "btih:deadbeef",
        )
        # No btih → fallback
        self.assertEqual(
            sd._magnet_dedupe_key("  magnet:?xt=urn:sha1:abc  "),
            "magnet:?xt=urn:sha1:abc",
        )
        # Empty fallback
        self.assertEqual(sd._magnet_dedupe_key("   "), "")

    def test_forget_then_re_register_yields_fresh_handle(self):
        """After forget_magnets clears both tables, registering the same
        magnet text should allocate a new handle (deduped=False), not
        falsely match against a stale reverse-table entry."""
        state = sd.DaemonState()
        m = "magnet:?xt=urn:btih:cccccccccccccccccccccccccccccccccccccccc&dn=Recycle"
        first = _call(state, {
            "cmd": "register_magnets", "request_id": "1", "magnets": [m],
        })
        h_first = first["registered"][0]["handle_id"]
        self.assertFalse(first["registered"][0]["deduped"])

        forgot = _call(state, {
            "cmd": "forget_magnets", "request_id": "f",
        })
        self.assertTrue(forgot["ok"])
        self.assertEqual(state.magnets, {})
        self.assertEqual(state.magnet_to_handle, {})

        second = _call(state, {
            "cmd": "register_magnets", "request_id": "2", "magnets": [m],
        })
        h_second = second["registered"][0]["handle_id"]
        self.assertFalse(second["registered"][0]["deduped"])
        # New handle, distinct from the forgotten one.
        self.assertNotEqual(h_first, h_second)


class RegisterMagnetLimits(unittest.TestCase):
    def _state(self):
        s = sd.DaemonState()
        s.handshake_done = True   # not strictly required by register_magnets but mirror the realistic state
        return s

    def test_rejects_too_many_magnets(self):
        state = self._state()
        payload = ["magnet:?xt=urn:btih:abc"] * (sd.MAX_REGISTER_MAGNETS + 1)
        resp = sd.cmd_register_magnets(state, {"request_id": "r", "magnets": payload})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], "bad_request")
        self.assertEqual(len(state.magnets), 0)

    def test_drops_oversized_uri_to_invalid(self):
        state = self._state()
        long_uri = "magnet:?xt=urn:btih:abc&dn=" + "x" * (sd.MAX_MAGNET_URI_LEN + 10)
        resp = sd.cmd_register_magnets(state, {"request_id": "r",
                                               "magnets": [long_uri, "magnet:?xt=urn:btih:def"]})
        self.assertTrue(resp["ok"])
        # The good one registers; the long one lands in invalid (possibly truncated)
        self.assertEqual(len(resp["registered"]), 1)
        self.assertEqual(len(resp["invalid"]), 1)
        # Invalid entry should be bounded — never echo the full attacker string
        self.assertLessEqual(len(resp["invalid"][0]), 64)

    def test_accepts_uppercase_magnet_scheme(self):
        state = self._state()
        magnet = (
            "MAGNET:?xt=urn:btih:ABCDEF0123456789ABCDEF0123456789ABCDEF01"
            "&dn=SNOS-192"
        )
        resp = sd.cmd_register_magnets(state, {
            "request_id": "r",
            "magnets": [magnet],
        })
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["invalid"], [])
        self.assertEqual(len(resp["registered"]), 1)
        handle_id = resp["registered"][0]["handle_id"]
        self.assertEqual(state.magnets[handle_id], magnet)
        self.assertEqual(resp["registered"][0]["name"], "SNOS-192")
        self.assertEqual(
            resp["registered"][0]["magnet_redacted"],
            "magnet:?xt=urn:btih:ABCDEF01...",
        )


class FetchJavdbLimits(unittest.TestCase):
    def _state(self):
        s = sd.DaemonState()
        s.handshake_done = True
        return s

    def test_caps_returned_magnets_to_max_fetch(self):
        state = self._state()
        n = sd.MAX_FETCH_MAGNETS + 50
        magnets = [{"magnet": f"magnet:?xt=urn:btih:{i:040x}",
                    "name": "", "size": "", "tags": [], "date": ""}
                   for i in range(n)]
        fake_result = {"url": "https://javdb.com/v/x", "code": "", "title": "",
                       "magnets": magnets, "error": ""}
        with mock.patch.object(sd, "fetch_magnets", return_value=fake_result), \
             mock.patch.object(sd, "create_session",
                               return_value=(mock.MagicMock(), "requests")):
            resp = sd.cmd_fetch_javdb(state, {"request_id": "r",
                                              "url": "https://javdb.com/v/x"})
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["result"]["magnet_count"], sd.MAX_FETCH_MAGNETS)
        self.assertEqual(len(state.magnets), sd.MAX_FETCH_MAGNETS)

    def test_drops_oversized_uri_from_page(self):
        state = self._state()
        short = "magnet:?xt=urn:btih:" + "a" * 40
        long_ = "magnet:?xt=urn:btih:" + "a" * 40 + "&dn=" + "y" * (sd.MAX_MAGNET_URI_LEN + 100)
        magnets = [
            {"magnet": short, "name": "ok", "size": "", "tags": [], "date": ""},
            {"magnet": long_, "name": "evil", "size": "", "tags": [], "date": ""},
        ]
        fake_result = {"url": "https://javdb.com/v/x", "code": "", "title": "",
                       "magnets": magnets, "error": ""}
        with mock.patch.object(sd, "fetch_magnets", return_value=fake_result), \
             mock.patch.object(sd, "create_session",
                               return_value=(mock.MagicMock(), "requests")):
            resp = sd.cmd_fetch_javdb(state, {"request_id": "r",
                                              "url": "https://javdb.com/v/x"})
        self.assertTrue(resp["ok"])
        self.assertEqual(resp["result"]["magnet_count"], 1)
        # state should hold only the short one
        self.assertEqual(len(state.magnets), 1)
        self.assertEqual(list(state.magnets.values())[0], short)


class MainCli(unittest.TestCase):
    """Cover the argparse + setup_logging + run_daemon wire-up in main()."""

    def test_main_invokes_setup_and_daemon_and_returns_zero(self):
        with mock.patch.object(sd, "run_daemon") as run_daemon, \
             mock.patch("app_logging.setup_logging") as setup_logging:
            rc = sd.main(["sidecar.py", "--daemon"])
        self.assertEqual(rc, 0)
        setup_logging.assert_called_once()
        run_daemon.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
