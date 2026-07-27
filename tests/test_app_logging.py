"""Tests for app_logging — no-network, no-side-effects on import.

Protects M1's A-blocker fix:
- Importing app_logging must NOT mkdir or open log files.
- setup_logging() respects JAVDB_LOG_DIR env override.
- Fallback chain: JAVDB_LOG_DIR > %LOCALAPPDATA%/JavDBMagnet/logs > console-only.
- Importing legacy.javdb_magnet_gui must NOT auto-initialize logging.

All tests that call setup_logging set JAVDB_LOG_DIR to a tempdir to avoid
polluting the developer's real %LOCALAPPDATA%/JavDBMagnet/logs.

To force "unwritable" paths in tests, we put a regular file at a location and
then ask setup_logging to mkdir UNDER that file. mkdir then fails with
NotADirectoryError on Windows. This avoids relying on a specific drive letter
not being mounted.
"""

import importlib
import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _force_reimport(module_name: str):
    """Drop a module from sys.modules and re-import it fresh."""
    sys.modules.pop(module_name, None)
    return importlib.import_module(module_name)


def _detach_file_handlers():
    """Remove FileHandlers from the root logger so temp dirs can be deleted."""
    root = logging.getLogger()
    for h in list(root.handlers):
        if isinstance(h, logging.FileHandler):
            h.close()
            root.removeHandler(h)


class ImportSideEffects(unittest.TestCase):
    """Importing app_logging must not create directories or open files."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        os.environ["JAVDB_LOG_DIR"] = self._tmp

    def tearDown(self):
        os.environ.pop("JAVDB_LOG_DIR", None)
        _detach_file_handlers()
        # Best-effort cleanup; tests should not have created files here
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_import_does_not_create_log_dir(self):
        _force_reimport("app_logging")
        self.assertEqual(
            list(Path(self._tmp).iterdir()), [],
            "app_logging import unexpectedly created files in JAVDB_LOG_DIR",
        )

    def test_import_does_not_set_initialized(self):
        mod = _force_reimport("app_logging")
        self.assertFalse(
            mod._initialized,
            "app_logging._initialized should be False after fresh import",
        )

    def test_get_log_file_returns_none_before_setup(self):
        mod = _force_reimport("app_logging")
        self.assertIsNone(mod.get_log_file())


class EnvOverride(unittest.TestCase):
    """JAVDB_LOG_DIR env var must override the default log directory."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        self._saved_localappdata = os.environ.get("LOCALAPPDATA")

    def tearDown(self):
        os.environ.pop("JAVDB_LOG_DIR", None)
        if self._saved_localappdata is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = self._saved_localappdata
        _detach_file_handlers()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_override_used_when_set(self):
        target = Path(self._tmp) / "logs"
        os.environ["JAVDB_LOG_DIR"] = str(target)

        mod = _force_reimport("app_logging")
        log_file = mod.setup_logging()

        self.assertEqual(log_file.parent, target)
        self.assertTrue(target.is_dir(), "override dir should be created")
        self.assertTrue(log_file.exists(), "log file should be opened")
        self.assertEqual(mod.get_log_file(), log_file)

    def test_override_empty_string_falls_back_to_localappdata(self):
        os.environ["JAVDB_LOG_DIR"] = ""
        os.environ["LOCALAPPDATA"] = self._tmp

        mod = _force_reimport("app_logging")
        log_file = mod.setup_logging()
        expected = Path(self._tmp) / "JavDBMagnet" / "logs"
        self.assertEqual(log_file.parent, expected)


class FallbackChain(unittest.TestCase):
    """Fallback ordering: JAVDB_LOG_DIR > %LOCALAPPDATA% > console-only."""

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        # Put a regular file here; using it as a "parent" makes mkdir fail.
        self._blocker = Path(self._tmp) / "blocker_file"
        self._blocker.write_text("not a dir", encoding="utf-8")
        self._saved_localappdata = os.environ.get("LOCALAPPDATA")

    def tearDown(self):
        os.environ.pop("JAVDB_LOG_DIR", None)
        if self._saved_localappdata is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = self._saved_localappdata
        _detach_file_handlers()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_fallback_to_localappdata_when_override_unwritable(self):
        # Override path is "<file>/logs" — mkdir fails because parent is a file.
        unwritable = self._blocker / "logs"
        os.environ["JAVDB_LOG_DIR"] = str(unwritable)

        # LOCALAPPDATA points to a writable subdir of our tempdir
        writable = Path(self._tmp) / "writable_appdata"
        writable.mkdir()
        os.environ["LOCALAPPDATA"] = str(writable)

        mod = _force_reimport("app_logging")
        log_file = mod.setup_logging()

        expected_dir = writable / "JavDBMagnet" / "logs"
        self.assertEqual(log_file.parent, expected_dir)
        self.assertTrue(expected_dir.is_dir())
        self.assertTrue(log_file.exists())

    def test_fallback_to_console_only_when_all_unwritable(self):
        # Both candidates point under the blocker file; mkdir fails for both.
        os.environ["JAVDB_LOG_DIR"] = str(self._blocker / "override_logs")
        os.environ["LOCALAPPDATA"] = str(self._blocker)

        mod = _force_reimport("app_logging")
        log_file = mod.setup_logging()

        # No FileHandler should be attached
        root = logging.getLogger()
        file_handlers = [h for h in root.handlers if isinstance(h, logging.FileHandler)]
        self.assertEqual(
            file_handlers, [],
            "should fall back to console-only when no dir is writable",
        )
        # log_file is still a Path so callers can show it diagnostically
        self.assertIsInstance(log_file, Path)
        self.assertFalse(log_file.exists(), "no file should have been created")

    def test_setup_logging_is_idempotent(self):
        target = Path(self._tmp) / "idempotent_logs"
        os.environ["JAVDB_LOG_DIR"] = str(target)

        mod = _force_reimport("app_logging")
        first = mod.setup_logging()
        second = mod.setup_logging()
        self.assertEqual(first, second)
        # Subsequent calls should not duplicate handlers
        root = logging.getLogger()
        file_handlers = [h for h in root.handlers if isinstance(h, logging.FileHandler)]
        self.assertEqual(len(file_handlers), 1,
                         "idempotent setup_logging should not duplicate handlers")


class JavdbGuiImportSideEffects(unittest.TestCase):
    """Importing legacy.javdb_magnet_gui must NOT auto-initialize logging.

    Originally a regression guard for the M1 fix that made setup_logging
    lazy (the Tk GUI's module-load was triggering mkdir + FileHandler).
    The GUI moved to legacy/ in M9 but the lazy-logging contract still
    matters: any module that does `from app_logging import get_logger`
    at import time must not cause setup_logging() to fire.
    """

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        os.environ["JAVDB_LOG_DIR"] = self._tmp

    def tearDown(self):
        os.environ.pop("JAVDB_LOG_DIR", None)
        _detach_file_handlers()
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_import_does_not_initialize_logging(self):
        # Force fresh imports
        for mod in ("app_logging", "legacy.javdb_magnet_gui"):
            sys.modules.pop(mod, None)

        _force_reimport("app_logging")
        _force_reimport("legacy.javdb_magnet_gui")

        self.assertEqual(
            list(Path(self._tmp).iterdir()), [],
            "legacy.javdb_magnet_gui import unexpectedly initialized logging",
        )

        import app_logging
        self.assertFalse(app_logging._initialized)
        self.assertIsNone(app_logging.get_log_file())


class FileHandlerOSErrorFallback(unittest.TestCase):
    """When RotatingFileHandler raises OSError, setup_logging falls back to
    console-only without crashing. Exercises the 'attach handler returned
    False' path that fires after a directory was chosen.
    """

    def setUp(self):
        self._tmp = tempfile.mkdtemp()
        os.environ["JAVDB_LOG_DIR"] = self._tmp
        # Reset module so setup_logging() actually runs.
        sys.modules.pop("app_logging", None)

    def tearDown(self):
        os.environ.pop("JAVDB_LOG_DIR", None)
        _detach_file_handlers()
        sys.modules.pop("app_logging", None)
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)

    def test_oserror_on_handler_open_degrades_to_console_only(self):
        from unittest.mock import patch

        app_logging = _force_reimport("app_logging")
        with patch(
            "app_logging.RotatingFileHandler",
            side_effect=OSError("simulated open failure"),
        ):
            resolved = app_logging.setup_logging()
        # Path is still computed via the fallback; module shouldn't have raised.
        self.assertIsInstance(resolved, Path)
        # No file handler attached on the root logger.
        root = logging.getLogger()
        self.assertFalse(
            any(isinstance(h, logging.FileHandler) for h in root.handlers),
            "expected console-only fallback, but a FileHandler was attached",
        )


    def test_resolved_log_file_published_before_initialized(self):
        from unittest import mock
        mod = _force_reimport("app_logging")
        observed_resolved = []

        old_get_logger = logging.getLogger
        def spy_get_logger(name=None):
            if mod._initialized:
                observed_resolved.append(mod._resolved_log_file)
            return old_get_logger(name)

        with mock.patch("logging.getLogger", side_effect=spy_get_logger):
            mod.setup_logging()

        self.assertTrue(len(observed_resolved) > 0)
        self.assertTrue(all(r is not None for r in observed_resolved),
                        f"Observed _resolved_log_file as None while _initialized was True: {observed_resolved}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
