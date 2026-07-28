"""Tests for sidecar settings parsing and RD error classification edges.

Targets the helpers that the Sonar coverage report flagged as thin in
sidecar/sidecar.py:

- _classify_rd_error: the message→code bucket function. Frontend
  localization depends on a stable mapping, so every documented bucket
  is asserted from at least one realistic message shape.
- _resolve_strategy: precedence of request override vs settings vs
  hard-coded "smart" default.
- _resolve_int_setting: int+string both accepted, invalid types ignored,
  zero/negative ignored (so an accidentally-zeroed setting can't disable
  the cache_wait or min_size_mb thresholds).
- _rd_client: builds with state token by default, honours token_override,
  honours min_size_mb from settings, and raises when no token is set.

No HTTP, no real RD instance — `realdebrid.RealDebrid` is patched at
the import site inside _rd_client so we observe only the constructor
arguments.
"""

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Mirror test_sidecar_protocol.py's loader so this file targets the same
# sidecar/sidecar.py module instance and shares no state with any retired
# top-level `sidecar` spike.
_DAEMON_PATH = ROOT / "sidecar" / "sidecar.py"
_spec = importlib.util.spec_from_file_location("sidecar_daemon_settings", _DAEMON_PATH)
sd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sd)


# ---------------------------------------------------------------------------
# _classify_rd_error
# ---------------------------------------------------------------------------

class ClassifyRdError(unittest.TestCase):
    """Every public RD error message shape must bucket into a stable code."""

    def test_401_status_token_invalid(self):
        self.assertEqual(sd._classify_rd_error("HTTP 401: bad token"),
                         sd._RD_ERR_AUTH)

    def test_chinese_token_invalid_message(self):
        # The Chinese branch is the actual message thrown by RealDebrid
        # for 401 — the classifier must match it too.
        self.assertEqual(sd._classify_rd_error("API token 無效或已過期"),
                         sd._RD_ERR_AUTH)

    def test_token_expired_phrase(self):
        # "token" + "過期" path (covers the second arm of the 401 OR).
        self.assertEqual(sd._classify_rd_error("Your token 已過期 please refresh"),
                         sd._RD_ERR_AUTH)

    def test_403_premium_required(self):
        self.assertEqual(sd._classify_rd_error("HTTP 403: forbidden"),
                         sd._RD_ERR_PREMIUM)

    def test_chinese_premium_required(self):
        self.assertEqual(sd._classify_rd_error("帳號權限不足（需要 Premium 會員）"),
                         sd._RD_ERR_PREMIUM)

    def test_magnet_error_containing_digits_not_misclassified(self):
        self.assertEqual(sd._classify_rd_error("磁力解析失敗: IPZZ-403.mkv"),
                         sd._RD_ERR_MAGNET)

    def test_premium_english_keyword(self):
        self.assertEqual(sd._classify_rd_error("requires premium subscription"),
                         sd._RD_ERR_PREMIUM)

    def test_429_rate_limited(self):
        self.assertEqual(sd._classify_rd_error("HTTP 429: too fast"),
                         sd._RD_ERR_RATE)

    def test_rate_limit_phrase(self):
        # Matches the "rate" AND "limit" co-occurrence arm.
        self.assertEqual(sd._classify_rd_error("rate limit exceeded"),
                         sd._RD_ERR_RATE)

    def test_magnet_error_internal_marker(self):
        # process_magnet raises with "磁力解析失敗: ..." — that's the bucket.
        self.assertEqual(sd._classify_rd_error("磁力解析失敗: bad torrent"),
                         sd._RD_ERR_MAGNET)

    def test_magnet_error_english_state_string(self):
        # In case RD ever surfaces the raw state name in the message.
        self.assertEqual(sd._classify_rd_error("got magnet_error from RD"),
                         sd._RD_ERR_MAGNET)

    def test_download_failed_chinese(self):
        self.assertEqual(sd._classify_rd_error("下載失敗"),
                         sd._RD_ERR_DOWNLOAD)

    def test_download_failed_english(self):
        self.assertEqual(sd._classify_rd_error("download failed"),
                         sd._RD_ERR_DOWNLOAD)

    def test_unknown_falls_back_to_api(self):
        self.assertEqual(sd._classify_rd_error("some weird thing happened"),
                         sd._RD_ERR_API)

    def test_empty_falls_back_to_api(self):
        self.assertEqual(sd._classify_rd_error(""), sd._RD_ERR_API)

    def test_none_safe(self):
        # The classifier defensively handles None via `(message or "")`.
        self.assertEqual(sd._classify_rd_error(None), sd._RD_ERR_API)


# ---------------------------------------------------------------------------
# _resolve_strategy
# ---------------------------------------------------------------------------

class ResolveStrategy(unittest.TestCase):
    def test_request_override_wins(self):
        state = sd.DaemonState()
        state.settings = {"rd": {"file_pick": "smart"}}
        self.assertEqual(sd._resolve_strategy(state, "largest"), "largest")

    def test_empty_override_falls_back_to_settings(self):
        state = sd.DaemonState()
        state.settings = {"rd": {"file_pick": "video"}}
        self.assertEqual(sd._resolve_strategy(state, ""), "video")

    def test_none_override_falls_back_to_settings(self):
        state = sd.DaemonState()
        state.settings = {"rd": {"file_pick": "video"}}
        self.assertEqual(sd._resolve_strategy(state, None), "video")

    def test_no_settings_defaults_to_smart(self):
        state = sd.DaemonState()
        # state.settings = {} (default)
        self.assertEqual(sd._resolve_strategy(state, None), "smart")

    def test_settings_with_non_string_file_pick_defaults_to_smart(self):
        state = sd.DaemonState()
        state.settings = {"rd": {"file_pick": 123}}  # wrong type → ignored
        self.assertEqual(sd._resolve_strategy(state, None), "smart")

    def test_settings_with_no_rd_key_defaults_to_smart(self):
        state = sd.DaemonState()
        state.settings = {"ui": {"theme": "dark"}}
        self.assertEqual(sd._resolve_strategy(state, None), "smart")

    def test_non_string_override_falls_back(self):
        state = sd.DaemonState()
        state.settings = {"rd": {"file_pick": "video"}}
        # Non-string override is ignored.
        self.assertEqual(sd._resolve_strategy(state, 42), "video")


# ---------------------------------------------------------------------------
# _resolve_int_setting
# ---------------------------------------------------------------------------

class ResolveIntSetting(unittest.TestCase):
    def test_int_override_wins(self):
        state = sd.DaemonState()
        state.settings = {"rd": {"cache_wait_seconds": 99}}
        self.assertEqual(
            sd._resolve_int_setting(state, "cache_wait_seconds", 7, 15),
            7,
        )

    def test_string_digit_override_accepted(self):
        state = sd.DaemonState()
        self.assertEqual(
            sd._resolve_int_setting(state, "cache_wait_seconds", "12", 15),
            12,
        )

    def test_zero_override_ignored(self):
        # An accidentally-zero override must NOT zero out the threshold;
        # falls through to settings, then default.
        state = sd.DaemonState()
        state.settings = {"rd": {"cache_wait_seconds": 30}}
        self.assertEqual(
            sd._resolve_int_setting(state, "cache_wait_seconds", 0, 15),
            30,
        )

    def test_min_size_zero_override_allowed(self):
        state = sd.DaemonState()
        state.settings = {"rd": {"min_size_mb": 500}}
        self.assertEqual(
            sd._resolve_int_setting(state, "min_size_mb", 0, 500, min_value=0),
            0,
        )

    def test_negative_override_ignored(self):
        state = sd.DaemonState()
        self.assertEqual(
            sd._resolve_int_setting(state, "cache_wait_seconds", -3, 15),
            15,
        )

    def test_non_digit_string_override_ignored(self):
        state = sd.DaemonState()
        self.assertEqual(
            sd._resolve_int_setting(state, "cache_wait_seconds", "fifteen", 15),
            15,
        )

    def test_setting_int_used(self):
        state = sd.DaemonState()
        state.settings = {"rd": {"min_size_mb": 1024}}
        self.assertEqual(
            sd._resolve_int_setting(state, "min_size_mb", None, 500),
            1024,
        )

    def test_setting_string_digit_used(self):
        state = sd.DaemonState()
        state.settings = {"rd": {"min_size_mb": "750"}}
        self.assertEqual(
            sd._resolve_int_setting(state, "min_size_mb", None, 500),
            750,
        )

    def test_min_size_setting_zero_used(self):
        state = sd.DaemonState()
        state.settings = {"rd": {"min_size_mb": 0}}
        self.assertEqual(
            sd._resolve_int_setting(state, "min_size_mb", None, 500, min_value=0),
            0,
        )

    def test_cache_wait_setting_zero_falls_back_to_default(self):
        state = sd.DaemonState()
        state.settings = {"rd": {"cache_wait_seconds": 0}}
        self.assertEqual(
            sd._resolve_int_setting(state, "cache_wait_seconds", None, 15),
            15,
        )

    def test_bool_values_are_not_treated_as_ints(self):
        state = sd.DaemonState()
        state.settings = {"rd": {"min_size_mb": True, "cache_wait_seconds": False}}
        self.assertEqual(
            sd._resolve_int_setting(state, "min_size_mb", False, 500, min_value=0),
            500,
        )
        self.assertEqual(
            sd._resolve_int_setting(state, "cache_wait_seconds", True, 15),
            15,
        )

    def test_missing_setting_returns_default(self):
        state = sd.DaemonState()
        self.assertEqual(
            sd._resolve_int_setting(state, "min_size_mb", None, 500),
            500,
        )

    def test_no_rd_key_returns_default(self):
        state = sd.DaemonState()
        state.settings = {"ui": {}}
        self.assertEqual(
            sd._resolve_int_setting(state, "min_size_mb", None, 500),
            500,
        )

    def test_string_with_whitespace_not_accepted(self):
        # `.isdigit()` rejects " 12" — defensive against pasted values.
        state = sd.DaemonState()
        self.assertEqual(
            sd._resolve_int_setting(state, "min_size_mb", " 12 ", 500),
            500,
        )


# ---------------------------------------------------------------------------
# _rd_client
# ---------------------------------------------------------------------------

class RdClientFactory(unittest.TestCase):
    """_rd_client wires state → RealDebrid constructor args. We replace
    the realdebrid module entry in sys.modules so the inline `from
    realdebrid import RealDebrid, RealDebridError` inside _rd_client
    picks up our fake without monkeypatching internals."""

    def setUp(self):
        # Build a stand-in module exposing RealDebrid + RealDebridError.
        import types
        self.fake_module = types.ModuleType("realdebrid_stub")

        class _FakeError(Exception):
            pass

        constructed: list[tuple] = []

        class _FakeClient:
            def __init__(self, token, min_size_mb=500, deadline=None):
                constructed.append((token, min_size_mb))
                self.token = token
                self.min_size_mb = min_size_mb
                self.deadline = deadline

        self.fake_module.RealDebrid = _FakeClient
        self.fake_module.RealDebridError = _FakeError
        self.constructed = constructed
        self._FakeError = _FakeError

        # _rd_client does `from realdebrid import RealDebrid, RealDebridError`,
        # so we patch the module slot, not an attribute on sd.
        self._patcher = mock.patch.dict(sys.modules,
                                         {"realdebrid": self.fake_module})
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()

    def test_uses_state_token_and_settings_min_size(self):
        state = sd.DaemonState()
        state.rd_token = "tok-A"
        state.settings = {"rd": {"min_size_mb": 800}}
        client = sd._rd_client(state)
        self.assertEqual(client.token, "tok-A")
        self.assertEqual(client.min_size_mb, 800)
        self.assertEqual(self.constructed[-1], ("tok-A", 800))

    def test_token_override_does_not_mutate_state(self):
        state = sd.DaemonState()
        state.rd_token = "tok-A"
        sd._rd_client(state, token_override="tok-B")
        self.assertEqual(self.constructed[-1][0], "tok-B")
        # state.rd_token must remain unchanged — `rd_user` relies on this
        # to validate a candidate token without committing it.
        self.assertEqual(state.rd_token, "tok-A")

    def test_min_size_mb_override_wins(self):
        state = sd.DaemonState()
        state.rd_token = "tok"
        state.settings = {"rd": {"min_size_mb": 800}}
        sd._rd_client(state, min_size_mb=2000)
        self.assertEqual(self.constructed[-1][1], 2000)

    def test_min_size_mb_settings_garbage_falls_back_to_500(self):
        state = sd.DaemonState()
        state.rd_token = "tok"
        # Wrong type → int() raises TypeError → caught → falls back to 500.
        state.settings = {"rd": {"min_size_mb": [1, 2]}}
        sd._rd_client(state)
        self.assertEqual(self.constructed[-1][1], 500)

    def test_min_size_mb_settings_non_numeric_string_falls_back_to_500(self):
        state = sd.DaemonState()
        state.rd_token = "tok"
        state.settings = {"rd": {"min_size_mb": "huge"}}
        sd._rd_client(state)
        self.assertEqual(self.constructed[-1][1], 500)

    def test_min_size_mb_settings_zero_is_preserved(self):
        state = sd.DaemonState()
        state.rd_token = "tok"
        state.settings = {"rd": {"min_size_mb": 0}}
        sd._rd_client(state)
        self.assertEqual(self.constructed[-1][1], 0)

    def test_min_size_mb_bool_setting_falls_back_to_500(self):
        state = sd.DaemonState()
        state.rd_token = "tok"
        state.settings = {"rd": {"min_size_mb": True}}
        sd._rd_client(state)
        self.assertEqual(self.constructed[-1][1], 500)

    def test_no_token_raises_rd_error(self):
        state = sd.DaemonState()
        # state.rd_token = "" (default)
        with self.assertRaises(self._FakeError):
            sd._rd_client(state)


# ---------------------------------------------------------------------------
# rd_send_magnet wiring of settings & overrides
# ---------------------------------------------------------------------------

class RdSendMagnetSettingsWiring(unittest.TestCase):
    """Settings precedence flowing through cmd_rd_send_magnet:
    request override > settings > default. Mirrors the existing
    `test_strategy_override_in_request` but covers cache_wait & min_size_mb
    explicitly and the all-defaults path."""

    def _state_with_magnet(self, settings=None):
        # `settings is None` means "use the populated default"; an
        # explicit `settings={}` is preserved so we can exercise the
        # "no settings → hard-coded defaults" path. `settings or default`
        # would collapse {} into the default and hide that branch.
        state = sd.DaemonState()
        state.handshake_done = True
        state.rd_token = "tok"
        if settings is None:
            state.settings = {"rd": {"file_pick": "smart",
                                      "cache_wait_seconds": 20,
                                      "min_size_mb": 750}}
        else:
            state.settings = settings
        state.magnets["h-1"] = "magnet:?xt=urn:btih:abc&dn=Y"
        return state

    def _stub_client(self):
        fake = mock.MagicMock()
        fake.process_magnet.return_value = {"status": "completed",
                                             "torrent_id": "T", "name": "n",
                                             "links": []}
        return fake

    def test_defaults_to_settings_values(self):
        state = self._state_with_magnet()
        fake = self._stub_client()
        with mock.patch.object(sd, "_rd_client", return_value=fake) as m:
            sd.dispatch(state, {"cmd": "rd_send_magnet", "request_id": "r",
                                "handle_id": "h-1", "cache_wait": 20})
        # _rd_client must receive min_size_mb=750 from settings
        kwargs = m.call_args.kwargs
        self.assertEqual(kwargs["min_size_mb"], 750)
        # process_magnet honours cache_wait=20 from settings
        pm_kwargs = fake.process_magnet.call_args.kwargs
        self.assertEqual(pm_kwargs["strategy"], "smart")
        self.assertEqual(pm_kwargs["cache_wait"], 20)

    def test_no_settings_uses_hard_coded_defaults(self):
        # Empty settings → smart / 15s / 500MB defaults.
        state = self._state_with_magnet(settings={})
        fake = self._stub_client()
        with mock.patch.object(sd, "_rd_client", return_value=fake) as m:
            sd.dispatch(state, {"cmd": "rd_send_magnet", "request_id": "r",
                                "handle_id": "h-1"})
        self.assertEqual(m.call_args.kwargs["min_size_mb"], 500)
        pm_kwargs = fake.process_magnet.call_args.kwargs
        self.assertEqual(pm_kwargs["strategy"], "smart")
        self.assertEqual(pm_kwargs["cache_wait"], 15)

    def test_request_overrides_individual_fields(self):
        state = self._state_with_magnet()
        fake = self._stub_client()
        with mock.patch.object(sd, "_rd_client", return_value=fake) as m:
            sd.dispatch(state, {"cmd": "rd_send_magnet", "request_id": "r",
                                "handle_id": "h-1", "strategy": "video",
                                "cache_wait": 3, "min_size_mb": 1500})
        self.assertEqual(m.call_args.kwargs["min_size_mb"], 1500)
        pm_kwargs = fake.process_magnet.call_args.kwargs
        self.assertEqual(pm_kwargs["strategy"], "video")
        self.assertEqual(pm_kwargs["cache_wait"], 3)

    def test_min_size_zero_setting_is_passed_to_rd_client(self):
        state = self._state_with_magnet(
            settings={"rd": {"file_pick": "smart",
                             "cache_wait_seconds": 20,
                             "min_size_mb": 0}},
        )
        fake = self._stub_client()
        with mock.patch.object(sd, "_rd_client", return_value=fake) as m:
            sd.dispatch(state, {"cmd": "rd_send_magnet", "request_id": "r",
                                "handle_id": "h-1"})
        self.assertEqual(m.call_args.kwargs["min_size_mb"], 0)

    def test_unexpected_exception_redacted(self):
        # A non-RealDebridError that escapes _rd_client / process_magnet
        # must be classified rd_internal AND must not echo the message body.
        state = self._state_with_magnet()
        with mock.patch.object(sd, "_rd_client",
                               side_effect=RuntimeError("secret-leak-here")):
            resp = sd.dispatch(state, {"cmd": "rd_send_magnet", "request_id": "r",
                                       "handle_id": "h-1"})
        self.assertFalse(resp["ok"])
        self.assertEqual(resp["error"]["code"], sd._RD_ERR_INTERNAL)
        self.assertNotIn("secret-leak-here", resp["error"]["message"])
        # The internal field should contain only the exception type + <redacted>.
        self.assertNotIn("secret-leak-here", resp["error"]["internal"])


# ---------------------------------------------------------------------------
# Non-dict rd settings safety
# ---------------------------------------------------------------------------

class NonDictRdSettingsHandling(unittest.TestCase):
    def test_non_dict_rd_settings_does_not_break_rd_commands(self):
        state = sd.DaemonState()
        sd.dispatch(state, {"cmd": "handshake", "request_id": "r0", "cookies": "", "rd_token": "tok", "settings": {}, "paths": {}})
        sd.dispatch(state, {"cmd": "update_settings", "request_id": "r1", "settings": {"rd": "pwn"}})
        resp = sd.dispatch(state, {"cmd": "rd_user", "request_id": "r2"})
        if not resp["ok"]:
            self.assertNotIn(resp["error"]["code"], [sd._RD_ERR_INTERNAL, "internal"])

    def test_non_dict_rd_settings_list_variant(self):
        state = sd.DaemonState()
        sd.dispatch(state, {"cmd": "handshake", "request_id": "r0", "cookies": "", "rd_token": "tok", "settings": {}, "paths": {}})
        sd.dispatch(state, {"cmd": "update_settings", "request_id": "r1", "settings": {"rd": [1, 2]}})
        resp = sd.dispatch(state, {"cmd": "rd_user", "request_id": "r2"})
        if not resp["ok"]:
            self.assertNotIn(resp["error"]["code"], [sd._RD_ERR_INTERNAL, "internal"])

    def test_rd_settings_helper_returns_dict(self):
        state = sd.DaemonState()
        state.settings = None
        self.assertEqual(sd._rd_settings(state), {})
        state.settings = "not-a-dict"
        self.assertEqual(sd._rd_settings(state), {})
        state.settings = {"rd": "string-rd"}
        self.assertEqual(sd._rd_settings(state), {})
        state.settings = {"rd": [1, 2]}
        self.assertEqual(sd._rd_settings(state), {})
        state.settings = {"rd": {"min_size_mb": 500}}
        self.assertEqual(sd._rd_settings(state), {"min_size_mb": 500})


if __name__ == "__main__":
    unittest.main(verbosity=2)
