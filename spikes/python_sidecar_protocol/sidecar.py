"""Python sidecar — JavDB / Real-Debrid CLI invoked by Tauri/Rust.

Design principles:
- stdout: a single JSON object per command, no log mixing
- stderr: optional diagnostics, must NOT contain cookies / full magnet / token
- argv: must NOT contain secrets — all sensitive inputs arrive via
  --cookies-file, --env-file, or --handshake-stdin
- One-shot CLI in M1; M3 promotes this to a long-running daemon

CLI:
    python sidecar.py fetch-javdb <url>
    python sidecar.py --cookies-file PATH fetch-javdb <url>
    python sidecar.py --env-file PATH fetch-javdb <url>
    python sidecar.py --handshake-stdin fetch-javdb <url>   # JSON line on stdin

Handshake JSON shape (M3 reuses this verbatim):
    {
      "cookies":  "k=v; k=v",
      "rd_token": "<token-or-null>",
      "settings": { ... settings.json contents ... },
      "paths":    { "data_dir": "...", "log_dir": "..." }
    }

M1 logging contract:
- sidecar.main() calls setup_logging() explicitly. Log dir comes from
  app_logging's fallback chain (JAVDB_LOG_DIR > %LOCALAPPDATA% > console-only).
- The handshake's `paths.log_dir` field is parsed and cached on the args
  namespace but is NOT applied to logging in M1 — by the time we read the
  handshake line, setup_logging has already configured handlers.
- M3's daemon protocol reverses this order: handshake first, then logging.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import IO

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from javdb_magnet_gui import create_session, fetch_magnets, load_cookies  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers (pure functions; no I/O beyond what's named)
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


def read_cookies_from_file(path: Path) -> dict[str, str]:
    """Read a cookie file at `path` and parse it. Missing/empty file returns {}."""
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8").strip()
    return parse_cookie_string(raw)


def read_handshake_json(stream: IO[str]) -> dict:
    """Read one line of JSON from `stream` and parse. Empty input raises ValueError."""
    line = stream.readline()
    if not line:
        raise ValueError("Empty handshake input on stdin")
    return json.loads(line)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="sidecar.py")
    p.add_argument("--cookies-file", type=Path, default=None, dest="cookies_file",
                   help="Path to a cookies.txt file (semicolon-separated key=value).")
    p.add_argument("--env-file", type=Path, default=None, dest="env_file",
                   help="Path to a .env file (RD_API_TOKEN etc.).")
    p.add_argument("--handshake-stdin", action="store_true", dest="handshake_stdin",
                   help=("Read one line of JSON from stdin: "
                         "{cookies, rd_token, settings, paths}. "
                         "Overrides --cookies-file / --env-file when present."))
    p.add_argument("command", choices=["fetch-javdb"],
                   help="Subcommand. M1 supports only fetch-javdb; M3 adds the rest.")
    p.add_argument("url", nargs="?", help="URL for fetch-javdb.")
    return p


def _ensure_handshake(args: argparse.Namespace, stdin: IO[str]) -> dict:
    """Read handshake JSON once and cache on args, so cookies and env resolvers
    share the single stdin-line read."""
    cached = getattr(args, "_cached_handshake", None)
    if cached is not None:
        return cached
    handshake = read_handshake_json(stdin)
    args._cached_handshake = handshake
    return handshake


def resolve_cookies(args: argparse.Namespace, stdin: IO[str]) -> dict[str, str]:
    """Resolve cookies dict by source priority:
       1. --handshake-stdin  (use `cookies` field)
       2. --cookies-file PATH
       3. legacy javdb_magnet_gui.load_cookies() (uses app_dir() — discouraged
          for sidecar but kept for backwards-compat callers without flags)
    """
    if args.handshake_stdin:
        handshake = _ensure_handshake(args, stdin)
        return parse_cookie_string(handshake.get("cookies", "") or "")
    if args.cookies_file is not None:
        return read_cookies_from_file(args.cookies_file)
    return load_cookies()


def resolve_env(args: argparse.Namespace, stdin: IO[str]) -> dict[str, str]:
    """Resolve env dict (RD_API_TOKEN, UI_*, etc.) by source priority:
       1. --handshake-stdin  (use `rd_token` + flatten `settings`)
       2. --env-file PATH    (parsed via realdebrid.load_env)
       3. {} (empty)

    M1 only validates this resolver; the only command that consumes it
    (send-rd) arrives in M5.
    """
    if args.handshake_stdin:
        handshake = _ensure_handshake(args, stdin)
        env: dict[str, str] = {}
        token = handshake.get("rd_token")
        if token:
            env["RD_API_TOKEN"] = token
        settings = handshake.get("settings") or {}
        rd = settings.get("rd") or {}
        if rd.get("file_pick"):
            env["RD_FILE_PICK"] = rd["file_pick"]
        if rd.get("min_size_mb") is not None:
            env["RD_MIN_SIZE_MB"] = str(rd["min_size_mb"])
        ui = settings.get("ui") or {}
        if ui.get("theme"):
            env["UI_THEME"] = ui["theme"]
        if ui.get("scale"):
            env["UI_SCALE"] = str(ui["scale"])
        return env
    if args.env_file is not None:
        from realdebrid import load_env
        return load_env(args.env_file)
    return {}


def cmd_fetch_javdb(url: str, cookies: dict[str, str]) -> dict:
    """Run a JavDB fetch with explicit cookies dict. Returns the response payload."""
    session, engine = create_session()
    result = fetch_magnets(url, session, cookies)

    error = result.get("error", "") or None
    magnets_in = result.get("magnets", []) or []
    magnets_out = [
        {
            "name": m.get("name", ""),
            "size": m.get("size", ""),
            "tags": list(m.get("tags", [])),
            "date": m.get("date", ""),
            "magnet_redacted": redact_magnet(m.get("magnet", "")),
        }
        for m in magnets_in
    ]

    return {
        "ok": (not error) and len(magnets_out) > 0,
        "command": "fetch-javdb",
        "engine": engine,
        "url": url,
        "code": result.get("code", "") or "",
        "title": result.get("title", "") or "",
        "magnet_count": len(magnets_out),
        "magnets": magnets_out,
        "error": error,
    }


def main(argv: list[str], stdin: IO[str] | None = None, stdout: IO[str] | None = None) -> int:
    # M1 contract: sidecar initializes its own logging because importing
    # javdb_magnet_gui no longer auto-runs setup_logging.
    from app_logging import setup_logging
    setup_logging()

    parser = build_parser()
    args = parser.parse_args(argv[1:])

    stdin = stdin if stdin is not None else sys.stdin
    stdout = stdout if stdout is not None else sys.stdout

    if args.command != "fetch-javdb":
        # argparse's `choices` already rejects others; defensive only.
        print(f"Unsupported command: {args.command}", file=sys.stderr)
        return 2
    if not args.url:
        print("URL required for fetch-javdb", file=sys.stderr)
        return 2
    if not args.url.startswith(("http://", "https://")):
        print("URL must start with http(s)", file=sys.stderr)
        return 2

    try:
        cookies = resolve_cookies(args, stdin)
        # resolve_env is called for parity with M5; result currently unused for fetch.
        # The call validates the resolver path so missing-flag handling is exercised.
        _env = resolve_env(args, stdin)
        del _env
        payload = cmd_fetch_javdb(args.url, cookies)
    except Exception as e:
        # Redact: stderr gets exception type only; stdout gets a redacted JSON envelope.
        # Never echo the message body — it could include cookies / token / magnet
        # content depending on which exception was raised.
        print(f"sidecar error: {type(e).__name__}", file=sys.stderr)
        payload = {
            "ok": False,
            "command": "fetch-javdb",
            "engine": "unknown",
            "url": args.url,
            "code": "",
            "title": "",
            "magnet_count": 0,
            "magnets": [],
            "error": f"{type(e).__name__}: <redacted>",
        }

    stdout.write(json.dumps(payload, ensure_ascii=False))
    stdout.write("\n")
    stdout.flush()
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
