"""Centralized logging setup with lazy initialization.

Import-time guarantees (M1 A-blocker fix):
- No mkdir
- No FileHandler creation
- No file open

setup_logging() must be called explicitly to initialize.
Fallback chain: JAVDB_LOG_DIR > %LOCALAPPDATA%/JavDBMagnet/logs > console-only.

`app_dir()` is exported because legacy callers (javdb_magnet_gui's
COOKIE_FILE / ENV_FILE / PENDING_FILE) still need it. M7 retires those.
It is NOT used for log-dir resolution.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def app_dir() -> Path:
    """Application install directory (next to the .exe when frozen, else next to source)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


_initialized = False
_resolved_log_file: Path | None = None

_LOG_FILE_NAME = "debug.log"


def _candidate_log_dirs() -> list[Path]:
    """Ordered log-dir candidates. setup_logging() tries each in turn.

    Per M1 spec: JAVDB_LOG_DIR > %LOCALAPPDATA%\\JavDBMagnet\\logs.
    Deliberately excludes app_dir()/logs — including it would re-introduce the
    A-blocker on read-only deployments and break the console-only fallback test
    on writable dev worktrees.
    """
    candidates: list[Path] = []
    override = os.environ.get("JAVDB_LOG_DIR", "").strip()
    if override:
        candidates.append(Path(override))
    local_appdata = os.environ.get("LOCALAPPDATA", "").strip()
    if local_appdata:
        candidates.append(Path(local_appdata) / "JavDBMagnet" / "logs")
    return candidates


def _try_make_dir(p: Path) -> Path | None:
    """Attempt to mkdir p and verify writability via a probe. Return p or None."""
    try:
        p.mkdir(parents=True, exist_ok=True)
        probe = p / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return p
    except OSError:
        return None


def _resolve_log_dir() -> tuple[Path | None, Path | None]:
    """Walk candidate dirs and return (chosen, last_attempted)."""
    last_attempted: Path | None = None
    for candidate in _candidate_log_dirs():
        last_attempted = candidate
        result = _try_make_dir(candidate)
        if result is not None:
            return result, last_attempted
    return None, last_attempted


def _log_file_for(dir_: Path | None) -> Path:
    """Diagnostic path used when no writable dir was secured."""
    return (dir_ / _LOG_FILE_NAME) if dir_ else Path(_LOG_FILE_NAME)


def _attach_file_handler(root: logging.Logger, log_file: Path) -> bool:
    """Attach a RotatingFileHandler. Return False if the file can't be opened."""
    try:
        file_handler = RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
    except OSError:
        return False
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    root.addHandler(file_handler)
    return True


def _attach_console_handler(root: logging.Logger, debug: bool) -> None:
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.DEBUG if debug else logging.INFO)
    console_handler.setFormatter(logging.Formatter(
        "[%(levelname)s] %(name)s: %(message)s",
    ))
    root.addHandler(console_handler)


def setup_logging(debug: bool = False) -> Path:
    """Initialize logging. Idempotent.

    Returns the resolved log file path on success, or the last-attempted path
    when all candidates fail and we degrade to console-only. Callers can use
    get_log_file() to retrieve the same value later.
    """
    global _initialized, _resolved_log_file
    if _initialized and _resolved_log_file is not None:
        return _resolved_log_file

    debug = debug or os.environ.get("DEBUG") == "1"

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()

    chosen_dir, last_attempted = _resolve_log_dir()

    if chosen_dir is None:
        log_file = _log_file_for(last_attempted)
    else:
        log_file = chosen_dir / _LOG_FILE_NAME
        if not _attach_file_handler(root, log_file):
            chosen_dir = None
            log_file = _log_file_for(last_attempted)

    _attach_console_handler(root, debug)

    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)

    _initialized = True
    _resolved_log_file = log_file
    if chosen_dir is None:
        logging.getLogger(__name__).warning(
            f"All log dir candidates failed; running console-only. Last attempted: {last_attempted}"
        )
    else:
        logging.getLogger(__name__).info(f"Logging initialized. File: {log_file}")
    return log_file


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def get_log_file() -> Path | None:
    """Return the resolved log file path, or None if setup_logging hasn't run yet."""
    return _resolved_log_file
