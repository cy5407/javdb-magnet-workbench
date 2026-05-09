"""Tests for spikes/python_sidecar_protocol/sidecar.py — no network.

Covers M1's added flags: --cookies-file, --env-file, --handshake-stdin.
All HTTP boundaries are mocked. Tests that call sidecar.main() set
JAVDB_LOG_DIR to a tempdir so they do not touch %LOCALAPPDATA%.
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

# Add sidecar's folder so we can import it as a module
SIDECAR_DIR = ROOT / "spikes" / "python_sidecar_protocol"
if str(SIDECAR_DIR) not in sys.path:
    sys.path.insert(0, str(SIDECAR_DIR))

import sidecar  # noqa: E402


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

class ParseCookieString(unittest.TestCase):
    def test_basic(self):
        s = "_jdb_session=abc; cf_clearance=xyz; locale=zh"
        self.assertEqual(
            sidecar.parse_cookie_string(s),
            {"_jdb_session": "abc", "cf_clearance": "xyz", "locale": "zh"},
        )

    def test_empty_string(self):
        self.assertEqual(sidecar.parse_cookie_string(""), {})

    def test_whitespace_only(self):
        self.assertEqual(sidecar.parse_cookie_string("   "), {})

    def test_skips_pairs_without_equals(self):
        s = "foo; bar=baz; quux"
        self.assertEqual(sidecar.parse_cookie_string(s), {"bar": "baz"})

    def test_value_may_contain_equals(self):
        s = "key=a=b=c"
        self.assertEqual(sidecar.parse_cookie_string(s), {"key": "a=b=c"})


class ReadCookiesFromFile(unittest.TestCase):
    def test_reads_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cookies.txt"
            path.write_text("a=1; b=2", encoding="utf-8")
            self.assertEqual(sidecar.read_cookies_from_file(path), {"a": "1", "b": "2"})

    def test_missing_file_returns_empty(self):
        self.assertEqual(
            sidecar.read_cookies_from_file(Path("/no/such/file.txt")),
            {},
        )

    def test_empty_file_returns_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cookies.txt"
            path.write_text("", encoding="utf-8")
            self.assertEqual(sidecar.read_cookies_from_file(path), {})


class ReadHandshakeJson(unittest.TestCase):
    def test_reads_one_line(self):
        payload = {"cookies": "k=v", "rd_token": "t", "settings": {}, "paths": {}}
        stream = io.StringIO(json.dumps(payload) + "\n{ignored: true}")
        self.assertEqual(sidecar.read_handshake_json(stream), payload)

    def test_empty_stream_raises(self):
        with self.assertRaises(ValueError):
            sidecar.read_handshake_json(io.StringIO(""))


# ---------------------------------------------------------------------------
# argparse + resolvers
# ---------------------------------------------------------------------------

class ArgumentParser(unittest.TestCase):
    def test_parses_minimal(self):
        args = sidecar.build_parser().parse_args(
            ["fetch-javdb", "https://javdb.com/v/abc"]
        )
        self.assertEqual(args.command, "fetch-javdb")
        self.assertEqual(args.url, "https://javdb.com/v/abc")
        self.assertIsNone(args.cookies_file)
        self.assertIsNone(args.env_file)
        self.assertFalse(args.handshake_stdin)

    def test_parses_cookies_file(self):
        args = sidecar.build_parser().parse_args([
            "--cookies-file", "C:/tmp/cookies.txt",
            "fetch-javdb", "https://javdb.com/v/x",
        ])
        self.assertEqual(args.cookies_file, Path("C:/tmp/cookies.txt"))

    def test_parses_env_file(self):
        args = sidecar.build_parser().parse_args([
            "--env-file", "C:/tmp/.env",
            "fetch-javdb", "https://javdb.com/v/x",
        ])
        self.assertEqual(args.env_file, Path("C:/tmp/.env"))

    def test_parses_handshake_stdin(self):
        args = sidecar.build_parser().parse_args([
            "--handshake-stdin",
            "fetch-javdb", "https://javdb.com/v/x",
        ])
        self.assertTrue(args.handshake_stdin)


class ResolveCookies(unittest.TestCase):
    def test_cookies_file_used_when_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            cookies_path = Path(tmp) / "cookies.txt"
            cookies_path.write_text("only=fromfile", encoding="utf-8")

            args = sidecar.build_parser().parse_args([
                "--cookies-file", str(cookies_path),
                "fetch-javdb", "https://javdb.com/v/x",
            ])
            self.assertEqual(
                sidecar.resolve_cookies(args, io.StringIO("")),
                {"only": "fromfile"},
            )

    def test_handshake_stdin_used_when_set(self):
        handshake = {"cookies": "from=stdin", "rd_token": None,
                     "settings": {}, "paths": {}}
        stdin = io.StringIO(json.dumps(handshake) + "\n")
        args = sidecar.build_parser().parse_args([
            "--handshake-stdin",
            "fetch-javdb", "https://javdb.com/v/x",
        ])
        self.assertEqual(
            sidecar.resolve_cookies(args, stdin),
            {"from": "stdin"},
        )


class ResolveEnv(unittest.TestCase):
    def test_env_file_loaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "RD_API_TOKEN=fake_token_123\nUI_THEME=dark\n",
                encoding="utf-8",
            )
            args = sidecar.build_parser().parse_args([
                "--env-file", str(env_path),
                "fetch-javdb", "https://javdb.com/v/x",
            ])
            env = sidecar.resolve_env(args, io.StringIO(""))
            self.assertEqual(env.get("RD_API_TOKEN"), "fake_token_123")
            self.assertEqual(env.get("UI_THEME"), "dark")

    def test_no_env_source_returns_empty(self):
        args = sidecar.build_parser().parse_args([
            "fetch-javdb", "https://javdb.com/v/x",
        ])
        self.assertEqual(sidecar.resolve_env(args, io.StringIO("")), {})

    def test_handshake_stdin_routes_token_and_settings(self):
        handshake = {
            "cookies": "x=y",
            "rd_token": "tok_from_stdin",
            "settings": {
                "rd": {"file_pick": "smart", "min_size_mb": 500},
                "ui": {"theme": "dark", "scale": "auto"},
            },
            "paths": {"data_dir": "C:/data", "log_dir": "C:/logs"},
        }
        stdin = io.StringIO(json.dumps(handshake) + "\n")
        args = sidecar.build_parser().parse_args([
            "--handshake-stdin",
            "fetch-javdb", "https://javdb.com/v/x",
        ])

        cookies = sidecar.resolve_cookies(args, stdin)
        # Stdin should now be consumed; resolve_env must use the cache
        self.assertEqual(stdin.read(), "",
                         "stdin should be EOF after handshake")
        env = sidecar.resolve_env(args, stdin)

        self.assertEqual(cookies, {"x": "y"})
        self.assertEqual(env.get("RD_API_TOKEN"), "tok_from_stdin")
        self.assertEqual(env.get("RD_FILE_PICK"), "smart")
        self.assertEqual(env.get("RD_MIN_SIZE_MB"), "500")
        self.assertEqual(env.get("UI_THEME"), "dark")
        self.assertEqual(env.get("UI_SCALE"), "auto")

    def test_handshake_stdin_empty_raises(self):
        args = sidecar.build_parser().parse_args([
            "--handshake-stdin",
            "fetch-javdb", "https://javdb.com/v/x",
        ])
        with self.assertRaises(ValueError):
            sidecar.resolve_cookies(args, io.StringIO(""))


# ---------------------------------------------------------------------------
# main() with mocked network
# ---------------------------------------------------------------------------

class MainEndToEndMocked(unittest.TestCase):
    """End-to-end main() tests with HTTP fully mocked.

    Each test sets JAVDB_LOG_DIR to a tempdir so setup_logging() does not
    pollute the real %LOCALAPPDATA%.
    """

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._saved_log_dir = os.environ.get("JAVDB_LOG_DIR")
        os.environ["JAVDB_LOG_DIR"] = self._tmp

        # Ensure setup_logging will run fresh in main()
        import app_logging
        app_logging._initialized = False
        app_logging._resolved_log_file = None
        # Detach any pre-existing FileHandlers from previous tests
        import logging
        for h in list(logging.getLogger().handlers):
            if isinstance(h, logging.FileHandler):
                h.close()
                logging.getLogger().removeHandler(h)

    def tearDown(self):
        if self._saved_log_dir is None:
            os.environ.pop("JAVDB_LOG_DIR", None)
        else:
            os.environ["JAVDB_LOG_DIR"] = self._saved_log_dir
        # Detach handlers before tempdir cleanup
        import logging
        for h in list(logging.getLogger().handlers):
            if isinstance(h, logging.FileHandler):
                h.close()
                logging.getLogger().removeHandler(h)
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_main_passes_cookies_from_file_to_fetch(self):
        with tempfile.TemporaryDirectory() as tmp:
            cookies_path = Path(tmp) / "cookies.txt"
            cookies_path.write_text("k=v", encoding="utf-8")

            stub_session = mock.MagicMock()

            with mock.patch.object(sidecar, "create_session",
                                   return_value=(stub_session, "mock_engine")), \
                 mock.patch.object(sidecar, "fetch_magnets") as mock_fetch:
                mock_fetch.return_value = {
                    "url": "https://javdb.com/v/x",
                    "code": "ABC-123",
                    "title": "fixture",
                    "magnets": [],
                    "error": "",
                }

                argv = ["sidecar.py", "--cookies-file", str(cookies_path),
                        "fetch-javdb", "https://javdb.com/v/x"]
                stdout = io.StringIO()
                rc = sidecar.main(argv, stdin=io.StringIO(""), stdout=stdout)

                # rc=1 because magnet_count=0; not the focus
                self.assertIn(rc, (0, 1))

                # Verify cookies were forwarded correctly
                pos_args, _ = mock_fetch.call_args
                self.assertEqual(pos_args[2], {"k": "v"},
                                 "cookies dict from --cookies-file must reach fetch_magnets")

                # Verify stdout is a valid single-line JSON
                payload = json.loads(stdout.getvalue().strip())
                self.assertEqual(payload["command"], "fetch-javdb")
                self.assertEqual(payload["engine"], "mock_engine")

    def test_main_returns_redacted_envelope_on_exception(self):
        with mock.patch.object(sidecar, "create_session",
                               side_effect=RuntimeError("secret-leak-message-not-shown")):
            argv = ["sidecar.py", "fetch-javdb", "https://javdb.com/v/x"]
            stdout = io.StringIO()
            stderr_capture = io.StringIO()
            with mock.patch("sys.stderr", stderr_capture):
                rc = sidecar.main(argv, stdin=io.StringIO(""), stdout=stdout)

            self.assertEqual(rc, 1)
            payload = json.loads(stdout.getvalue().strip())
            self.assertFalse(payload["ok"])
            # Error message must be redacted — not contain the raised message
            self.assertIn("RuntimeError", payload["error"])
            self.assertIn("<redacted>", payload["error"])
            self.assertNotIn("secret-leak-message-not-shown", payload["error"])
            # Stderr also must not leak the message body
            self.assertNotIn("secret-leak-message-not-shown", stderr_capture.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
