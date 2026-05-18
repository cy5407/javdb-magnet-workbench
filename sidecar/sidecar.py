"""JavDB / Real-Debrid sidecar daemon.

JSON-lines protocol over stdin/stdout. One JSON object per line, UTF-8.

M3 commands implemented:
    hello, handshake, ping, fetch_javdb, resolve_magnet, resolve_magnets,
    forget_magnets, register_magnets, update_settings, shutdown, cancel.

M5 commands implemented:
    rd_user, rd_set_token, rd_send_magnet, rd_check_pending.
    Per-magnet (singular) shape so the Rust caller can drive a batch loop
    with progress events, cancellation between items, and dynamic pacing.
    Pending state lives on the Rust side; the sidecar is stateless beyond
    the single in-flight magnet handle table from M3.

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
import urllib.parse
import uuid
from pathlib import Path
from typing import IO, Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Daemon-boundary responsibility: ensure stdout speaks UTF-8 even when the
# inheriting console (Windows cmd / PowerShell) defaults to a code page
# that would mangle JavDB titles or magnet `dn=` values. Keep this OUT of
# javdb_scraper.py — that's a pure library and should not touch stdio.
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from javdb_scraper import create_session, fetch_magnets  # noqa: E402

PROTOCOL_VERSION = 1
SIDECAR_VERSION = "0.1.0"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# BTIH v1 is 40 hex chars; v2 is 64. The {1,128} bound keeps the regex
# linear (Sonar flags unbounded `+` on `[a-fA-F0-9]` as polynomial
# backtracking) while still covering both.
_REDACT_MAGNET_RX = re.compile(
    r"^(magnet:\?xt=urn:btih:)([a-fA-F0-9]{1,128})"
)


def redact_magnet(uri: str) -> str:
    """Keep `magnet:?xt=urn:btih:` + first 8 hex chars + `...`; drop the rest."""
    if not uri:
        return ""
    m = _REDACT_MAGNET_RX.match(uri)
    if m:
        return f"{m.group(1)}{m.group(2)[:8]}..."
    return "magnet:..." if uri.startswith("magnet:") else "<not-a-magnet>"


def extract_magnet_dn(uri: str) -> str:
    """Extract and URL-decode the `dn=` parameter from a magnet URI.

    Magnet links typically include a display name (e.g.
    `dn=[javdb.com]SNOS-192`) which is the closest thing each magnet
    has to a per-row identifier. The frontend uses this as the row's
    `name` field so the "paste-magnet" path can render JAV codes in
    the result table and the "送至 RD 進度" 番號 column — without it,
    rows fall back to the synthetic group code "(直接貼上 N)".

    Returns `""` if no `dn=` is present. The value is URL-decoded
    (`+` -> space, `%XX` -> char) so multi-byte / spaced names display
    correctly. Not a secret: dn is the publicly-advertised name of the
    torrent, included in the magnet by the publisher.

    Parsing goes through stdlib `urllib.parse` instead of a regex over
    the raw URI so we never run an unbounded `[^&]+` capture (Sonar
    flags those as super-linear). `parse_qs` already handles `+` and
    `%XX` decoding for the value.
    """
    if not uri:
        return ""
    parsed = urllib.parse.urlparse(uri)
    values = urllib.parse.parse_qs(
        parsed.query, keep_blank_values=True
    ).get("dn")
    if not values:
        return ""
    return values[0]


def parse_cookie_string(s: str) -> dict[str, str]:
    """Parse `k=v; k=v` cookie header into dict. Empty/whitespace returns {}.

    Pairs containing CR or LF are dropped: a stray newline inside a
    cookie value is the classic shape for HTTP-header injection / response
    splitting (CWE-93). The desktop app never legitimately needs a
    multi-line cookie, so refusing is safer than escaping (F-05).
    """
    if not s or not s.strip():
        return {}
    out: dict[str, str] = {}
    for pair in s.split(";"):
        pair = pair.strip()
        if "=" not in pair:
            continue
        if "\r" in pair or "\n" in pair:
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
        # Forward table: handle_id -> full magnet URI (original text, used
        # for clipboard write and RD HTTP body).
        self.magnets: dict[str, str] = {}
        # Reverse table: dedupe_key -> handle_id. The dedupe key is
        # `btih:<lowercase-hash>` when the magnet has a parseable
        # urn:btih:<hex>, otherwise the trimmed full string. This makes
        # two magnets with the same BTIH but different `dn=`, parameter
        # order, or hash case map to the SAME handle — without it, the
        # "send to RD" path could still double-bill for cosmetically
        # different but semantically identical magnets.
        self.magnet_to_handle: dict[str, str] = {}
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


_HANDSHAKE_TOKEN_WARNING = {
    "code": "rd_token_format_invalid",
    # Generic message — never echoes the dirty value (M1). Covers both
    # the wrong-type case (e.g. hand-crafted handshake with rd_token=123)
    # and the wrong-shape case (e.g. dirty keyring blob with punctuation).
    "message": (
        "rd_token from handshake was not a well-formed Real-Debrid "
        "token (expected a string of <=255 ASCII alphanumeric chars); "
        "the value has been dropped and no token is configured"
    ),
}


def cmd_handshake(state: DaemonState, req: dict) -> dict:
    state.cookies = parse_cookie_string(req.get("cookies", "") or "")
    # F-04 cross-path leak: if a malformed token slipped past the Rust
    # guards (e.g. a corrupted keyring entry from an earlier version,
    # or a hand-crafted handshake), refuse to carry it into state.
    # rd_send_magnet would otherwise hand the dirty value straight to
    # the Real-Debrid API. Empty string here means "no token configured"
    # — cmd_rd_user / cmd_rd_send_magnet already surface that as
    # rd_no_token, which is the correct user-facing signal.
    #
    # Type-guard ordering matters here: a non-string rd_token (number /
    # list / object from a hand-crafted handshake) MUST NOT reach
    # _is_valid_rd_token, which would TypeError on len()/iteration and
    # turn the whole dispatch into an `internal` error envelope. None
    # and "" are the steady-state "not configured" shapes and stay
    # silent; anything else of the wrong type is warned and dropped.
    raw = req.get("rd_token")
    warnings: list[dict] = []
    if raw is None or raw == "":
        rd_token = ""
    elif isinstance(raw, str) and _is_valid_rd_token(raw):
        rd_token = raw
    else:
        # Machine-readable so a future UI/agent can prompt the user to
        # re-enter the token rather than silently seeing "rd_no_token".
        warnings.append(dict(_HANDSHAKE_TOKEN_WARNING))
        rd_token = ""
    state.rd_token = rd_token
    state.settings = req.get("settings") or {}
    state.paths = req.get("paths") or {}
    state.handshake_done = True
    extra = {"warnings": warnings} if warnings else None
    return _ok(req, extra)


def cmd_ping(state: DaemonState, req: dict) -> dict:
    return _ok(req, {"uptime_seconds": int(time.time() - state.start_time)})


_BTIH_PREFIX = "urn:btih:"
_HEX_CHARS = frozenset("0123456789abcdef")


def _magnet_dedupe_key(full: str) -> str:
    """Identity key for magnet dedupe.

    Two magnet URIs that point at the same BitTorrent v1 content should
    hash to the same key even if they differ in:
      - `dn=` (display name) — JavDB sometimes serves different `dn`s
        for the same hash
      - parameter order — `magnet:?dn=...&xt=urn:btih:HASH` vs
        `magnet:?xt=urn:btih:HASH&dn=...`
      - tracker (`tr=`) list — different mirrors of the same content
      - hash case — some sources emit uppercase hex

    Strategy: parse the magnet URI with stdlib `urllib.parse` (avoids
    unbounded regex over the raw string, which Sonar flags as
    super-linear), find an `xt` value of the form `urn:btih:<hex>`,
    lowercase the hex and return `btih:<hex>`. If no BTIH can be
    parsed (e.g. v2 `urn:btmh:` or a malformed string that somehow
    slipped past upstream validation), fall back to the trimmed full
    string so dedupe still works conservatively.
    """
    stripped = full.strip()
    parsed = urllib.parse.urlparse(stripped)
    for xt in urllib.parse.parse_qs(
        parsed.query, keep_blank_values=True
    ).get("xt", []):
        lower = xt.lower()
        if not lower.startswith(_BTIH_PREFIX):
            continue
        hash_hex = lower[len(_BTIH_PREFIX):]
        if hash_hex and all(c in _HEX_CHARS for c in hash_hex):
            return "btih:" + hash_hex
    return stripped


def _intern_magnet(state: DaemonState, full: str) -> tuple[str, bool]:
    """Look up `full` in the reverse table (keyed by the normalized
    dedupe key, not the raw string); reuse the existing handle_id if
    found, otherwise allocate a new one. Returns `(handle_id, deduped)`.
    Updates BOTH the forward (`state.magnets`) and reverse
    (`state.magnet_to_handle`) maps so every caller sees the same
    identity.
    """
    key = _magnet_dedupe_key(full)
    existing = state.magnet_to_handle.get(key)
    if existing is not None:
        return existing, True
    handle_id = f"h-{uuid.uuid4()}"
    state.magnets[handle_id] = full
    state.magnet_to_handle[key] = handle_id
    return handle_id, False


_JAVDB_ALLOWED_HOST = "javdb.com"


def _is_javdb_host(host: str) -> bool:
    """True iff `host` is javdb.com or an immediate subdomain.

    requests.Session.get(url, cookies=dict) does NOT scope cookies by
    host — every cookie in the dict is appended to the outgoing
    `Cookie:` header no matter what URL `url` points at. Without a host
    allowlist, a user tricked into supplying an arbitrary HTTPS URL
    would leak `_jdb_session` + `cf_clearance` to the attacker's
    endpoint (F-01 / CWE-200 / CWE-540).
    """
    if not host:
        return False
    host = host.lower()
    return host == _JAVDB_ALLOWED_HOST or host.endswith("." + _JAVDB_ALLOWED_HOST)


def cmd_fetch_javdb(state: DaemonState, req: dict) -> dict:
    if not state.handshake_done:
        return _err(req, "bad_request", "handshake required before fetch_javdb")
    url = req.get("url")
    # Require https:// — JavDB itself serves over TLS, so accepting plain
    # http:// here would only enable MITM / Cloudflare-bypass attempts
    # against the user's cookies, never a legitimate fetch. Sonar's
    # "Using http protocol is insecure" (S5332) flags the previous
    # http-or-https accept-list as a clear-text-channel risk.
    if not isinstance(url, str) or not url.startswith("https://"):
        return _err(req, "bad_request", "url must start with https://")
    # F-01: pin the host to javdb.com (or *.javdb.com). See
    # _is_javdb_host for the rationale; without this gate the JavDB
    # cookies would be sent to any HTTPS URL the caller passes in.
    try:
        host = (urllib.parse.urlparse(url).hostname or "")
    except ValueError:
        return _err(req, "bad_request", "url is not a valid URL")
    if not _is_javdb_host(host):
        return _err(req, "bad_request", "url host not allowed")

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
        # Intern via the reverse table so a magnet that already has a
        # handle (e.g. re-fetch of the same JavDB page, or previously
        # registered by the paste path) keeps its existing handle_id.
        handle_id, _deduped = _intern_magnet(state, full)
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
    # Reverse table must clear with the forward table — otherwise a
    # later register would falsely "dedupe" against a stale entry
    # whose handle no longer exists.
    state.magnet_to_handle.clear()
    return _ok(req, {"forgot": n})


def cmd_register_magnets(state: DaemonState, req: dict) -> dict:
    """Register raw magnet URIs into the handle table without going through
    a JavDB fetch. Used by the "paste magnet → send to RD" UI path.

    Each input must start with `magnet:`; non-magnets are returned in
    `invalid` so the frontend can flag them. Deduplication is performed
    via the reverse table (`state.magnet_to_handle`) so a magnet that
    already has a handle — whether from a previous register call OR a
    previous fetch_javdb — keeps that handle and is flagged
    `deduped: true`. This is what prevents the "send N to RD" path
    from double-billing the same magnet across groups.
    """
    magnets_in = req.get("magnets")
    if not isinstance(magnets_in, list):
        return _err(req, "bad_request", "magnets must be a list of strings")

    registered: list[dict] = []
    invalid: list[str] = []

    for raw in magnets_in:
        if not isinstance(raw, str):
            invalid.append(str(raw))
            continue
        s = raw.strip()
        if not s.startswith("magnet:"):
            invalid.append(s)
            continue

        handle_id, deduped = _intern_magnet(state, s)
        registered.append({
            "handle_id": handle_id,
            "magnet_redacted": redact_magnet(s),
            "name": extract_magnet_dn(s),
            "deduped": deduped,
        })

    return _ok(req, {"registered": registered, "invalid": invalid})


def cmd_update_settings(state: DaemonState, req: dict) -> dict:
    new_settings = req.get("settings")
    if new_settings is not None:
        state.settings = new_settings
    return _ok(req)


def cmd_set_cookies(state: DaemonState, req: dict) -> dict:
    """Update state.cookies at runtime so a cf_clearance refresh doesn't
    require an app restart.

    Mirrors ``cmd_rd_set_token``:
      - handshake gate (F-17): refuse until handshake is established.
      - ``cookies`` may be ``null`` / ``""`` to clear, or a non-empty
        ``Cookie:``-header-style string (``k=v; k=v``) to set.
      - parsing reuses ``parse_cookie_string`` (already drops CR/LF
        pairs per F-05).

    The full cookies blob is opaque text — we don't size-validate here
    beyond what ``parse_cookie_string`` already enforces because the
    Rust caller (``save_cookies`` / ``migrate_cookies_now``) applies
    the [`cookie_store::COOKIES_MAX_BYTES`] cap before crossing IPC.
    """
    if not state.handshake_done:
        return _err(req, "bad_request", "handshake required before set_cookies")
    cookies = req.get("cookies")
    if cookies is None:
        state.cookies = {}
        return _ok(req, {"set": False})
    if not isinstance(cookies, str):
        return _err(req, "bad_request", "cookies must be a string when provided")
    if not cookies.strip():
        state.cookies = {}
        return _ok(req, {"set": False})
    state.cookies = parse_cookie_string(cookies)
    return _ok(req, {"set": bool(state.cookies)})


def cmd_cancel(state: DaemonState, req: dict) -> dict:
    # M3 sidecar processes commands synchronously; nothing is "in flight"
    # that an out-of-band cancel could interrupt. Acknowledge so the Rust
    # caller's protocol-level cancel path does not error. Real cancellation
    # arrives with a future async-aware refactor.
    return _ok(req)


# ---------------------------------------------------------------------------
# M5: Real-Debrid commands
#
# Design notes:
# - Per-magnet (singular) request/response. The Rust caller drives the batch
#   loop, which lets us emit progress events between items and stop early
#   on cancel without protocol-level streaming.
# - Sidecar is the only place RD HTTP traffic happens; the Rust layer never
#   sees the RD token in flight (only on rd_set_token).
# - Pending state lives in Rust; sidecar does NOT persist torrent ids to disk.
# - Errors are mapped to stable codes so the frontend can localize messages
#   without regex-matching English strings.
# ---------------------------------------------------------------------------

_RD_ERR_AUTH = "rd_token_invalid"
_RD_ERR_PREMIUM = "rd_premium_required"
_RD_ERR_RATE = "rd_rate_limited"
_RD_ERR_API = "rd_api_error"
_RD_ERR_NO_TOKEN = "rd_no_token"
_RD_ERR_MAGNET = "rd_magnet_error"
_RD_ERR_DOWNLOAD = "rd_download_failed"
_RD_ERR_NOT_FOUND = "rd_torrent_missing"
_RD_ERR_INTERNAL = "rd_internal"

_RD_NO_TOKEN_MSG = "RD token not configured"


def _classify_rd_error(message: str) -> str:
    """Bucket a RealDebridError message into a stable error code."""
    m = (message or "").lower()
    if "401" in m or "token 無效" in m or ("token" in m and "過期" in m):
        return _RD_ERR_AUTH
    if "403" in m or "premium" in m or "權限不足" in m:
        return _RD_ERR_PREMIUM
    if "429" in m or ("rate" in m and "limit" in m):
        return _RD_ERR_RATE
    if "magnet_error" in m or "磁力解析失敗" in m or "磁力錯誤" in m:
        return _RD_ERR_MAGNET
    if "下載失敗" in m or "download failed" in m:
        return _RD_ERR_DOWNLOAD
    return _RD_ERR_API


def _rd_client(state: DaemonState, token_override: str | None = None,
               min_size_mb: int | None = None):
    """Build a fresh RealDebrid client. Cheap (just a requests.Session).

    `token_override` lets `rd_user` validate a candidate token without
    mutating state.rd_token until the user confirms.
    """
    from realdebrid import RealDebrid, RealDebridError  # local import: heavy
    token = token_override if token_override is not None else state.rd_token
    if not token:
        raise RealDebridError("RD_API_TOKEN not configured")
    if min_size_mb is None:
        rd_settings = (state.settings or {}).get("rd") or {}
        try:
            min_size_mb = int(rd_settings.get("min_size_mb", 500))
        except (TypeError, ValueError):
            min_size_mb = 500
    return RealDebrid(token, min_size_mb=min_size_mb)


def _resolve_strategy(state: DaemonState, override: str | None) -> str:
    if isinstance(override, str) and override:
        return override
    rd_settings = (state.settings or {}).get("rd") or {}
    s = rd_settings.get("file_pick")
    return s if isinstance(s, str) and s else "smart"


def _resolve_int_setting(state: DaemonState, key: str, override, default: int) -> int:
    if isinstance(override, int) and override > 0:
        return override
    if isinstance(override, str) and override.isdigit():
        return int(override)
    rd_settings = (state.settings or {}).get("rd") or {}
    v = rd_settings.get(key)
    if isinstance(v, int) and v > 0:
        return v
    if isinstance(v, str) and v.isdigit():
        return int(v)
    return default


def cmd_rd_user(state: DaemonState, req: dict) -> dict:
    """Validate token + return account snapshot. Token override allowed
    so the settings UI can probe a candidate token before saving."""
    from realdebrid import RealDebridError
    token_override = req.get("token")
    if token_override is not None and not isinstance(token_override, str):
        return _err(req, "bad_request", "token must be a string when provided")
    if not token_override and not state.rd_token:
        return _err(req, _RD_ERR_NO_TOKEN, _RD_NO_TOKEN_MSG)
    try:
        client = _rd_client(state, token_override=token_override or None)
        info = client._request("GET", "/user")
    except RealDebridError as e:
        return _err(req, _classify_rd_error(str(e)), str(e))
    except Exception as e:
        return _err(req, _RD_ERR_INTERNAL, f"{type(e).__name__}: <redacted>")
    return _ok(req, {
        "user": {
            "username": info.get("username", ""),
            "type": info.get("type", ""),
            "expiration": info.get("expiration", ""),
            "points": info.get("points", 0),
        }
    })


# !!! KEEP IN SYNC with the Rust `secret_store::RD_TOKEN_MAX_LEN`
# (`app/src-tauri/src/secret_store.rs`). Same rule applied on both
# sides of the IPC.
_RD_TOKEN_MAX_LEN = 255


def _is_valid_rd_token(token: str) -> bool:
    """Real-Debrid API tokens are 52 ASCII alphanumeric characters at
    time of writing. Bound to <=255 chars / ASCII-alnum so a paste of
    surrounding HTML, a stray newline, or a stale OAuth blob can't be
    stored as a token (F-04).

    !!! KEEP IN SYNC with the Rust ``secret_store::is_valid_rd_token``
    (``app/src-tauri/src/secret_store.rs``). The two implementations
    MUST accept and reject exactly the same strings — handshake
    (Python) and credential store (Rust) both gate on this rule, and
    drift would let a token pass one side but fail the other (silent
    UX breakage where the keyring holds a value the sidecar then drops
    at handshake time, or vice versa). If you change the rule, update
    both files in the same commit and re-run both test suites.
    """
    return (
        0 < len(token) <= _RD_TOKEN_MAX_LEN
        and all(c.isascii() and c.isalnum() for c in token)
    )


def cmd_rd_set_token(state: DaemonState, req: dict) -> dict:
    """Update state.rd_token at runtime. Used by the settings UI after the
    user pastes / changes a token, so a sidecar restart isn't needed."""
    # F-17: align with cmd_rd_send_magnet — require handshake first so a
    # caller cannot push tokens before the protocol is established.
    if not state.handshake_done:
        return _err(req, "bad_request", "handshake required before rd_set_token")
    token = req.get("token")
    if token is None:
        state.rd_token = ""
        return _ok(req, {"set": False})
    if not isinstance(token, str):
        return _err(req, "bad_request", "token must be a string")
    if token == "":
        # Treat an explicit empty string like null — a clear, not a set.
        state.rd_token = ""
        return _ok(req, {"set": False})
    if not _is_valid_rd_token(token):
        return _err(req, "bad_request", "rd_token_format_invalid")
    state.rd_token = token
    return _ok(req, {"set": True})


def cmd_rd_send_magnet(state: DaemonState, req: dict) -> dict:
    """Add one magnet to RD, select files, wait `cache_wait` seconds.

    Returns one of:
      status="completed" with `links` (cached or quick cache hit)
      status="pending"   with `torrent_id`+`progress`+`rd_status`
                         (caller persists torrent_id on its side)
      ok=false           on non-recoverable error (token, bad magnet, etc.)
    """
    from realdebrid import RealDebridError
    if not state.handshake_done:
        return _err(req, "bad_request", "handshake required before rd_send_magnet")
    if not state.rd_token:
        return _err(req, _RD_ERR_NO_TOKEN, _RD_NO_TOKEN_MSG)

    handle_id = req.get("handle_id")
    if not isinstance(handle_id, str):
        return _err(req, "bad_request", "handle_id must be a string")
    magnet = state.magnets.get(handle_id)
    if magnet is None:
        return _err(req, "unknown_handle", "magnet handle not in current session")

    strategy = _resolve_strategy(state, req.get("strategy"))
    cache_wait = _resolve_int_setting(state, "cache_wait_seconds", req.get("cache_wait"), 15)
    min_size_mb = _resolve_int_setting(state, "min_size_mb", req.get("min_size_mb"), 500)

    try:
        client = _rd_client(state, min_size_mb=min_size_mb)
        result = client.process_magnet(magnet, strategy=strategy, cache_wait=cache_wait)
    except RealDebridError as e:
        return _err(req, _classify_rd_error(str(e)), str(e))
    except Exception as e:
        return _err(req, _RD_ERR_INTERNAL, f"{type(e).__name__}: <redacted>")

    status = result.get("status")
    if status == "completed":
        return _ok(req, {
            "status": "completed",
            "torrent_id": result.get("torrent_id", ""),
            "name": result.get("name", ""),
            "links": result.get("links", []),
        })
    # pending
    return _ok(req, {
        "status": "pending",
        "torrent_id": result.get("torrent_id", ""),
        "name": result.get("name", ""),
        "rd_status": result.get("rd_status", ""),
        "progress": result.get("progress", 0),
        "files_selected": bool(result.get("files_selected", False)),
        "strategy": strategy,
    })


def cmd_rd_check_pending(state: DaemonState, req: dict) -> dict:
    """Re-check a previously-pending torrent_id. No magnet is required:
    caller-side pending records DO NOT store the magnet (per security model).
    """
    from realdebrid import RealDebridError
    if not state.rd_token:
        return _err(req, _RD_ERR_NO_TOKEN, _RD_NO_TOKEN_MSG)
    torrent_id = req.get("torrent_id")
    if not isinstance(torrent_id, str) or not torrent_id:
        return _err(req, "bad_request", "torrent_id must be a non-empty string")
    strategy = _resolve_strategy(state, req.get("strategy"))

    try:
        client = _rd_client(state)
        # We pass empty magnet — pending entries that still need file
        # selection cannot be auto-fixed without the original magnet, by
        # design (pending JSON never holds magnet text). The frontend
        # surfaces this as "needs reselection" if it ever happens.
        result = client.check_torrent(torrent_id, strategy=strategy, magnet="")
    except RealDebridError as e:
        return _err(req, _classify_rd_error(str(e)), str(e))
    except Exception as e:
        return _err(req, _RD_ERR_INTERNAL, f"{type(e).__name__}: <redacted>")

    status = result.get("status")
    if status == "completed":
        return _ok(req, {
            "status": "completed",
            "torrent_id": torrent_id,
            "name": result.get("name", ""),
            "links": result.get("links", []),
        })
    if status == "missing":
        return _ok(req, {"status": "missing", "torrent_id": torrent_id})
    return _ok(req, {
        "status": "pending",
        "torrent_id": torrent_id,
        "name": result.get("name", ""),
        "rd_status": result.get("rd_status", ""),
        "progress": result.get("progress", 0),
    })


DISPATCH = {
    "hello": cmd_hello,
    "handshake": cmd_handshake,
    "ping": cmd_ping,
    "fetch_javdb": cmd_fetch_javdb,
    "resolve_magnet": cmd_resolve_magnet,
    "resolve_magnets": cmd_resolve_magnets,
    "forget_magnets": cmd_forget_magnets,
    "register_magnets": cmd_register_magnets,
    "update_settings": cmd_update_settings,
    "set_cookies": cmd_set_cookies,
    "cancel": cmd_cancel,
    "rd_user": cmd_rd_user,
    "rd_set_token": cmd_rd_set_token,
    "rd_send_magnet": cmd_rd_send_magnet,
    "rd_check_pending": cmd_rd_check_pending,
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
               state: DaemonState | None = None) -> None:
    """Read JSON lines from `stdin`, write JSON-line responses to `stdout`.

    Returns on `shutdown` command or stdin EOF. Errors are emitted as JSON
    envelopes on `stdout`, not signalled through the return value — the
    caller treats every normal exit as success (exit code 0).
    """
    state = state or DaemonState()
    while True:
        line = stdin.readline()
        if not line:
            return
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
            return


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

    run_daemon(sys.stdin, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
