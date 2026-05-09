"""JavDB / Real-Debrid sidecar daemon.

JSON-lines protocol over stdin/stdout. One JSON object per line, UTF-8.

M3 commands implemented:
    hello, handshake, ping, fetch_javdb, resolve_magnet, resolve_magnets,
    forget_magnets, update_settings, shutdown, cancel.

M5 commands deferred:
    send_rd, retry_pending, rd_user.

Stderr is for diagnostics only; it must NEVER contain cookies, RD token,
full magnet URIs, or full traceback. Internal exceptions are caught at
the dispatch boundary and rendered as redacted error envelopes on stdout.

The handshake's `paths.log_dir` field is parsed and stored but is NOT
re-applied to logging at runtime (logging is set up before handshake is
read so the daemon can emit log lines about its own startup). The Rust
caller controls log_dir via the JAVDB_LOG_DIR environment variable.
"""

import argparse
import json
import re
import sys
import time
import uuid
from pathlib import Path
from typing import IO, Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from javdb_magnet_gui import create_session, fetch_magnets  # noqa: E402

PROTOCOL_VERSION = 1
SIDECAR_VERSION = "0.1.0"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def redact_magnet(uri: str) -> str:
    """Keep `magnet:?xt=urn:btih:` + first 8 hex chars + `...`; drop the rest."""
    if not uri:
        return ""
    m = re.match(r"^(magnet:\?xt=urn:btih:)([a-fA-F0-9]+)", uri)
    if m:
        return f"{m.group(1)}{m.group(2)[:8]}..."
    return "magnet:..." if uri.startswith("magnet:") else "<not-a-magnet>"


def parse_cookie_string(s: str) -> dict[str, str]:
    """Parse `k=v; k=v` cookie header into dict. Empty/whitespace returns {}."""
    if not s or not s.strip():
        return {}
    out: dict[str, str] = {}
    for pair in s.split(";"):
        pair = pair.strip()
        if "=" not in pair:
            continue
        key, value = pair.split("=", 1)
        out[key.strip()] = value.strip()
    return out


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class DaemonState:
    """In-memory state for a sidecar daemon process.

    Holds the handshake snapshot (cookies / token / settings / paths) and the
    MagnetHandleTable (UUID -> full magnet URI). Cleared on shutdown; never
    persisted to disk.
    """

    def __init__(self):
        self.handshake_done = False
        self.cookies: dict[str, str] = {}
        self.rd_token: str = ""
        self.settings: dict[str, Any] = {}
        self.paths: dict[str, str] = {}
        self.magnets: dict[str, str] = {}
        self.start_time = time.time()


# ---------------------------------------------------------------------------
# Envelopes
# ---------------------------------------------------------------------------

def _ok(req: dict, extra: dict | None = None) -> dict:
    out = {"ok": True, "request_id": req.get("request_id")}
    if extra:
        out.update(extra)
    return out


def _err(req: dict, code: str, message: str, internal: str = "") -> dict:
    return {
        "ok": False,
        "request_id": req.get("request_id"),
        "error": {"code": code, "message": message, "internal": internal},
    }


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def cmd_hello(state: DaemonState, req: dict) -> dict:
    requested = req.get("protocol_version")
    if requested != PROTOCOL_VERSION:
        return _err(
            req,
            "protocol_mismatch",
            f"sidecar v{PROTOCOL_VERSION} vs requested v{requested}",
        )
    return _ok(req, {
        "protocol_version": PROTOCOL_VERSION,
        "sidecar_version": SIDECAR_VERSION,
        "engine": "curl_cffi",
    })


def cmd_handshake(state: DaemonState, req: dict) -> dict:
    state.cookies = parse_cookie_string(req.get("cookies", "") or "")
    state.rd_token = req.get("rd_token") or ""
    state.settings = req.get("settings") or {}
    state.paths = req.get("paths") or {}
    state.handshake_done = True
    return _ok(req)


def cmd_ping(state: DaemonState, req: dict) -> dict:
    return _ok(req, {"uptime_seconds": int(time.time() - state.start_time)})


def cmd_fetch_javdb(state: DaemonState, req: dict) -> dict:
    if not state.handshake_done:
        return _err(req, "bad_request", "handshake required before fetch_javdb")
    url = req.get("url")
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        return _err(req, "bad_request", "url must start with http(s)")

    try:
        session, engine = create_session()
        result = fetch_magnets(url, session, state.cookies)
    except Exception as e:
        # Redact: never echo exception message; type only.
        return _err(req, "network", f"fetch failed: {type(e).__name__}")

    error = result.get("error", "") or ""
    if error:
        if "403" in error:
            return _err(req, "cloudflare_block",
                        "JavDB returned 403 / challenge")
        return _err(req, "network", error)

    magnets_in = result.get("magnets", []) or []
    magnets_out = []
    for m in magnets_in:
        full = m.get("magnet", "")
        handle_id = f"h-{uuid.uuid4()}"
        state.magnets[handle_id] = full
        magnets_out.append({
            "handle_id": handle_id,
            "name": m.get("name", ""),
            "size": m.get("size", ""),
            "tags": list(m.get("tags", [])),
            "date": m.get("date", ""),
            "magnet_redacted": redact_magnet(full),
        })

    return _ok(req, {
        "result": {
            "engine": engine,
            "url": url,
            "code": result.get("code", "") or "",
            "title": result.get("title", "") or "",
            "magnet_count": len(magnets_out),
            "magnets": magnets_out,
        }
    })


def cmd_resolve_magnet(state: DaemonState, req: dict) -> dict:
    handle_id = req.get("handle_id")
    if not isinstance(handle_id, str):
        return _err(req, "bad_request", "handle_id must be a string")
    full = state.magnets.get(handle_id)
    if full is None:
        return _err(req, "unknown_handle",
                    "magnet handle not in current session")
    return _ok(req, {"magnet": full})


def cmd_resolve_magnets(state: DaemonState, req: dict) -> dict:
    handle_ids = req.get("handle_ids")
    if not isinstance(handle_ids, list):
        return _err(req, "bad_request", "handle_ids must be a list")
    found = []
    unknown = []
    for hid in handle_ids:
        if not isinstance(hid, str):
            unknown.append(str(hid))
            continue
        full = state.magnets.get(hid)
        if full is None:
            unknown.append(hid)
        else:
            found.append({"handle_id": hid, "magnet": full})
    return _ok(req, {"magnets": found, "unknown": unknown})


def cmd_forget_magnets(state: DaemonState, req: dict) -> dict:
    n = len(state.magnets)
    state.magnets.clear()
    return _ok(req, {"forgot": n})


def cmd_update_settings(state: DaemonState, req: dict) -> dict:
    new_settings = req.get("settings")
    if new_settings is not None:
        state.settings = new_settings
    return _ok(req)


def cmd_cancel(state: DaemonState, req: dict) -> dict:
    # M3 sidecar processes commands synchronously; nothing is "in flight"
    # that an out-of-band cancel could interrupt. Acknowledge so the Rust
    # caller's protocol-level cancel path does not error. Real cancellation
    # arrives with a future async-aware refactor.
    return _ok(req)


DISPATCH = {
    "hello": cmd_hello,
    "handshake": cmd_handshake,
    "ping": cmd_ping,
    "fetch_javdb": cmd_fetch_javdb,
    "resolve_magnet": cmd_resolve_magnet,
    "resolve_magnets": cmd_resolve_magnets,
    "forget_magnets": cmd_forget_magnets,
    "update_settings": cmd_update_settings,
    "cancel": cmd_cancel,
}


def dispatch(state: DaemonState, req: dict) -> dict:
    """Dispatch one parsed request dict and return the response dict.

    Catches and redacts uncaught exceptions so traceback content never
    crosses the IPC boundary.
    """
    cmd = req.get("cmd")
    if cmd == "shutdown":
        # Caller-side concern: run_daemon breaks out of the loop after
        # emitting the response. Here we just produce the ack.
        return _ok(req)
    handler = DISPATCH.get(cmd) if isinstance(cmd, str) else None
    if handler is None:
        return _err(req, "bad_request", f"unknown command: {cmd!r}")
    try:
        return handler(state, req)
    except Exception as e:
        return _err(req, "internal", f"{type(e).__name__}: <redacted>")


# ---------------------------------------------------------------------------
# Daemon loop
# ---------------------------------------------------------------------------

def _emit(stdout: IO[str], obj: dict) -> None:
    stdout.write(json.dumps(obj, ensure_ascii=False))
    stdout.write("\n")
    stdout.flush()


def run_daemon(stdin: IO[str], stdout: IO[str],
               state: DaemonState | None = None) -> int:
    """Read JSON lines from `stdin`, write JSON-line responses to `stdout`.

    Exits 0 on `shutdown` command or stdin EOF.
    """
    state = state or DaemonState()
    while True:
        line = stdin.readline()
        if not line:
            return 0
        line = line.strip()
        if not line:
            continue

        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            _emit(stdout, {
                "ok": False,
                "request_id": None,
                "error": {"code": "bad_request",
                          "message": "invalid JSON line",
                          "internal": ""},
            })
            continue

        if not isinstance(req, dict):
            _emit(stdout, {
                "ok": False,
                "request_id": None,
                "error": {"code": "bad_request",
                          "message": "request must be a JSON object",
                          "internal": ""},
            })
            continue

        is_shutdown = req.get("cmd") == "shutdown"
        resp = dispatch(state, req)
        _emit(stdout, resp)
        if is_shutdown:
            return 0


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="sidecar")
    parser.add_argument(
        "--daemon", action="store_true",
        help="Run as JSON-lines daemon over stdin/stdout (M3 default).",
    )
    parser.parse_args(argv[1:])

    # Initialize logging before handshake. Log dir resolution is delegated to
    # app_logging's fallback chain (JAVDB_LOG_DIR > %LOCALAPPDATA%); the Rust
    # caller is responsible for setting the env var if a specific path is
    # required.
    from app_logging import setup_logging
    setup_logging()

    return run_daemon(sys.stdin, sys.stdout)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
