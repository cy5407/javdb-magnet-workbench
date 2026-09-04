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
import errno
import json
import re
import sys
import time
import urllib.parse
import uuid
from pathlib import Path
from typing import IO, Any, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:  # pragma: no cover — module-init path tweak, runs once on import
    sys.path.insert(0, str(ROOT))

# Daemon-boundary responsibility: ensure stdout speaks UTF-8 even when the
# inheriting console (Windows cmd / PowerShell) defaults to a code page
# that would mangle JavDB titles or magnet `dn=` values. Keep this OUT of
# javdb_scraper.py — that's a pure library and should not touch stdio.
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from javdb_scraper import create_session, fetch_magnets, parse_size_gb  # noqa: E402
import rd_outcome_log  # noqa: E402

PROTOCOL_VERSION = 1
SIDECAR_VERSION = "0.1.0"

# Per-call input limits to prevent attacker-controlled HTML / IPC payloads
# from ballooning state.magnets. Numbers calibrated to comfortably exceed
# any legitimate JavDB detail page (rarely >20 magnets/page) while bounding
# memory: 1000 magnets × 4096 bytes ≈ 4 MiB worst-case per fetch.
MAX_FETCH_MAGNETS = 1000      # cap on magnets returned by one cmd_fetch_javdb
MAX_REGISTER_MAGNETS = 1000   # cap on magnets accepted by one cmd_register_magnets
MAX_MAGNET_URI_LEN = 4096     # cap on a single magnet URI length (bytes)
MAX_SCRAPE_BATCH_ID_LEN = 128

# KEEP IN SYNC with app/src-tauri/src/{settings,sidecar_manager}.rs and the
# frontend validators. The sidecar is a second settings boundary: startup
# handshake receives the JSON file before read_settings returns a clamped copy
# to the WebView, and pending retry later reads this state directly.
MIN_RD_CACHE_WAIT_SECS = 5
MAX_RD_CACHE_WAIT_SECS = 300
MAX_RD_MIN_SIZE_MB = 1_000_000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MAGNET_SCHEME = "magnet:"

# BTIH v1 is 40 hex chars; v2 is 64. The {1,128} bound keeps the regex
# linear (Sonar flags unbounded `+` on `[a-f0-9]` as polynomial
# backtracking) while still covering both.
_REDACT_MAGNET_RX = re.compile(
    r"^magnet:\?xt=urn:btih:([a-f0-9]{1,128})",
    re.IGNORECASE,
)


def redact_magnet(uri: str) -> str:
    """Keep `magnet:?xt=urn:btih:` + first 8 hex chars + `...`; drop the rest."""
    if not uri:
        return ""
    m = _REDACT_MAGNET_RX.match(uri)
    if m:
        return f"magnet:?xt=urn:btih:{m.group(1)[:8]}..."
    return f"{_MAGNET_SCHEME}..." if uri.lower().startswith(_MAGNET_SCHEME) else "<not-a-magnet>"


def _btih8(uri: str) -> str:
    """First 8 hex chars of the BTIH, lower-cased. `""` when unparseable.

    A join key for the outcome log that is deliberately NOT `redact_magnet()`
    output: that returns `magnet:?xt=urn:btih:<8hex>...`, and the release
    redaction gates (log-redaction-verification.md:23, m6a-release-smoke.md:53)
    grep the whole log directory for exactly `magnet:\\?xt|urn:btih` expecting
    zero hits. Bare hex carries the same joining power without tripping them.
    Same 8-char convention realdebrid._extract_magnet_hash already uses.
    """
    if not uri:
        return ""
    m = _REDACT_MAGNET_RX.match(uri)
    return m.group(1)[:8].lower() if m else ""


def _elapsed_ms(started: float) -> int:
    """Milliseconds since a `time.monotonic()` mark, floored at 0."""
    return max(0, int((time.monotonic() - started) * 1000))


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
        # handle_id -> the JavDB row as scraped (name/size/tags/date/code) plus
        # its rank inside the group it came from. Kept ONLY so the outcome log
        # can record what the row looked like at send time; nothing in the
        # protocol reads it back. Group ranks have to be computed here at fetch
        # time because only the rows the user actually sends reach the log —
        # the group can never be reconstructed afterwards.
        self.magnet_meta: dict[str, dict] = {}
        # Manual rows can share a BTIH/handle with a JavDB row. Keep their
        # sparse metadata separately so starting a new web batch can downgrade
        # a surviving manual-only handle after the old web groups disappear.
        self.manual_meta: dict[str, dict] = {}
        self.active_scrape_batch_id: str | None = None
        # Monotonic per-session counter so two fetches of the same JAV code
        # stay distinguishable in the log.
        self.fetch_seq = 0
        self.start_time = time.time()
        self.rd_session = None


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
    cookies_raw = req.get("cookies")
    if isinstance(cookies_raw, str):
        state.cookies = parse_cookie_string(cookies_raw)
    else:
        state.cookies = {}

    # Defensive ordering (F-04): `rd_token` MUST be validated before storing.
    # Passing a non-string or non-conforming token falls back to "" + warning.
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

    settings_raw = req.get("settings")
    state.settings = _normalize_runtime_settings(settings_raw)

    paths_raw = req.get("paths")
    state.paths = paths_raw if isinstance(paths_raw, dict) else {}

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
    slipped past upstream validation), fall back to `raw:` + trimmed full
    string so fallback key and btih key live in different namespaces and
    hostile non-btih inputs cannot forge collisions.
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
    return "raw:" + stripped if stripped else ""




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

    Deliberately NOT widened to numeric mirrors (`javdb\\d*.com`): a review
    round proposed it, and it was rejected because there is no trustworthy
    official list of which numbered domains JavDB actually owns. Every extra
    host in this allowlist is another endpoint the session cookies get handed
    to, so the allowlist only grows on evidence, never on convenience.
    """
    if not host:
        return False
    host = host.lower()
    return host == _JAVDB_ALLOWED_HOST or host.endswith("." + _JAVDB_ALLOWED_HOST)


# Sort key for a missing upload date. Must sort AFTER every real ISO date:
# a raw "" compares as smaller than "2019-01-01", which would hand rank 1
# ("earliest upload") to every row JavDB left undated. Same sentinel and same
# reasoning as the frontend's rdPriority.rdDateKey.
_NO_DATE_SORT_KEY = "9999-99-99"


def _record_group_meta(
    state: DaemonState,
    code: str,
    rows: list[dict],
    batch_id: str | None = None,
) -> None:
    """Remember each row's scraped fields + its rank inside this fetch.

    Ranks are 1-based: `date_rank` 1 = oldest upload, `size_rank` 1 = largest
    file. They are computed HERE rather than at analysis time because the log
    only ever sees the rows the user chose to send — "was this the oldest of
    the five?" is unanswerable once the other four are gone.

    Deliberately stores raw scraped values only. No prefix matching, no HD
    verdict: the heuristic's single source of truth is rdPriority.ts, and a
    frozen verdict would lock old log rows into whatever the rules were the
    day they were written.
    """
    # One handle is one sendable candidate. The frontend dedupes by handle and
    # keeps the first visible occurrence, so ranks and metadata must be based
    # on that same canonical row. Dict comprehensions over the raw rows used to
    # keep the LAST duplicate's rank while the loop below kept the FIRST row's
    # fields, producing impossible combinations such as "oldest row, rank 2".
    canonical_rows: list[dict] = []
    seen_handles: set[str] = set()
    for row in rows:
        hid = row["handle_id"]
        if hid in seen_handles:
            continue
        seen_handles.add(hid)
        canonical_rows.append(row)

    by_date = sorted(canonical_rows, key=lambda r: (r.get("date") or _NO_DATE_SORT_KEY))
    date_rank = {r["handle_id"]: i + 1 for i, r in enumerate(by_date)}
    by_size = sorted(
        canonical_rows,
        key=lambda r: parse_size_gb(r.get("size") or ""),
        reverse=True,
    )
    size_rank = {r["handle_id"]: i + 1 for i, r in enumerate(by_size)}

    for r in canonical_rows:
        hid = r["handle_id"]
        prev = state.magnet_meta.get(hid)
        # An earlier JavDB group in this visible scrape batch already claimed this handle
        # (same BTIH on two pages — a re-release or a compilation). Keep the
        # first claim: the frontend attributes the row first-occurrence-wins
        # with web groups at the array head (rowClassByHandle,
        # buildSelectedSendItems), so the code/tags/rank the user actually
        # acted on are the FIRST group's. Recording the second group's would
        # log a class the user never saw — and rank is unrecoverable once
        # overwritten. Manual metadata is the opposite case and must still be
        # upgraded: it only ever carries a `dn=`.
        if (prev is not None and prev.get("source") == "javdb"
                and prev.get("_batch_id") == batch_id):
            continue
        state.magnet_meta[hid] = {
            "code": code,
            "name": r.get("name", ""),
            "size": r.get("size", ""),
            "tags": list(r.get("tags", []) or []),
            "date": r.get("date", ""),
            "source": "javdb",
            # Internal ownership marker only; rd_outcome_log copies an
            # explicit allowlist of public metadata fields and never emits it.
            "_batch_id": batch_id,
            "group_seq": state.fetch_seq,
            "group_size": len(canonical_rows),
            "date_rank": date_rank[hid],
            "size_rank": size_rank[hid],
        }


def _begin_scrape_meta_batch(state: DaemonState, batch_id: str | None) -> None:
    """Align metadata ownership with the frontend's replace-all web batch.

    startScrape forgets web-only handles but deliberately retains handles also
    shown by a manual row. If the new batch never returns that BTIH, no fetch
    can overwrite its old JavDB metadata; restore the separately-held manual
    metadata at the batch boundary so the outcome log matches the rows still
    visible. A repeated URL/retry in the same batch is a no-op.
    """
    if batch_id is None or batch_id == state.active_scrape_batch_id:
        return
    for hid in list(state.magnet_meta):
        meta = state.magnet_meta[hid]
        if meta.get("source") != "javdb":
            continue
        manual = state.manual_meta.get(hid)
        if manual is None:
            state.magnet_meta.pop(hid, None)
        else:
            state.magnet_meta[hid] = dict(manual)
    state.active_scrape_batch_id = batch_id


def _validate_batch_id(batch_id: Any) -> Optional[tuple[str, str]]:
    if not isinstance(batch_id, str) or not batch_id or len(batch_id) > MAX_SCRAPE_BATCH_ID_LEN:
        return ("bad_request", "batch_id must be a non-empty bounded string")
    return None


def _validate_javdb_url(url: Any) -> Optional[tuple[str, str]]:
    # Require https:// — JavDB itself serves over TLS, so accepting plain
    # http:// here would only enable MITM / Cloudflare-bypass attempts
    # against the user's cookies, never a legitimate fetch. Sonar's
    # "Using http protocol is insecure" (S5332) flags the previous
    # http-or-https accept-list as a clear-text-channel risk.
    if not isinstance(url, str) or not url.startswith("https://"):
        return ("bad_request", "url must start with https://")
    try:
        host = (urllib.parse.urlparse(url).hostname or "")
    except ValueError:
        return ("bad_request", "url is not a valid URL")
    # F-01: pin the host to javdb.com (or *.javdb.com). See
    # _is_javdb_host for the rationale; without this gate the JavDB
    # cookies would be sent to any HTTPS URL the caller passes in.
    if not _is_javdb_host(host):
        return ("bad_request", "url host not allowed")
    return None


def _process_scraped_magnets(state: DaemonState, magnets_in: list[dict]) -> list[dict]:
    """Bound, validate and intern magnets parsed from page."""
    if len(magnets_in) > MAX_FETCH_MAGNETS:
        magnets_in = magnets_in[:MAX_FETCH_MAGNETS]
    magnets_out = []
    for m in magnets_in:
        full = m.get("magnet", "")
        if not isinstance(full, str) or len(full) > MAX_MAGNET_URI_LEN:
            continue   # silently drop oversized — the page itself is malicious
        if not full.lower().startswith(_MAGNET_SCHEME):
            continue   # F-xx: hostile page may serve non-magnet hrefs
                       # the register path enforces the same prefix, so both writers
                       # into the handle table agree.
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
    return magnets_out


def cmd_fetch_javdb(state: DaemonState, req: dict) -> dict:
    if not state.handshake_done:
        return _err(req, "bad_request", "handshake required before fetch_javdb")
    url = req.get("url")
    batch_id = req.get("batch_id")
    batch_err = _validate_batch_id(batch_id)
    if batch_err is not None:
        return _err(req, batch_err[0], batch_err[1])
    assert isinstance(batch_id, str)

    # The frontend has already replaced its web groups by the time this RPC is
    # made. Reset ownership before URL validation as well as before network I/O:
    # an allowlist rejection is still a settled first row of the new batch.
    _begin_scrape_meta_batch(state, batch_id)

    url_err = _validate_javdb_url(url)
    if url_err is not None:
        return _err(req, url_err[0], url_err[1])
    assert isinstance(url, str)

    try:
        session, engine = create_session()
        try:
            result = fetch_magnets(url, session, state.cookies)
        finally:
            if hasattr(session, "close"):
                session.close()
    except Exception as e:
        # Redact: never echo exception message; type only.
        return _err(req, "network", f"fetch failed: {type(e).__name__}")

    error = result.get("error", "") or ""
    if error:
        if "403" in error:
            return _err(req, "cloudflare_block",
                        "JavDB returned 403 / challenge")
        return _err(req, "network", error)

    magnets_out = _process_scraped_magnets(state, result.get("magnets", []) or [])

    state.fetch_seq += 1
    _record_group_meta(
        state,
        result.get("code", "") or "",
        magnets_out,
        batch_id=batch_id,
    )

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
    if "handle_ids" not in req or req.get("handle_ids") is None:
        n = len(state.magnets)
        state.magnets.clear()
        state.magnet_to_handle.clear()
        state.magnet_meta.clear()
        state.manual_meta.clear()
        state.active_scrape_batch_id = None
        return _ok(req, {"forgot": n})

    handle_ids = req.get("handle_ids")
    if not isinstance(handle_ids, list):
        return _err(req, "bad_request", "handle_ids must be a list of strings")

    if not all(isinstance(hid, str) for hid in handle_ids):
        return _err(req, "bad_request", "handle_ids must be a list of strings")

    seen = set()
    forgot = 0
    for hid in handle_ids:
        if hid in seen:
            continue
        seen.add(hid)
        if hid in state.magnets:
            magnet_uri = state.magnets.pop(hid)
            key = _magnet_dedupe_key(magnet_uri)
            if state.magnet_to_handle.get(key) == hid:
                del state.magnet_to_handle[key]
            state.magnet_meta.pop(hid, None)
            state.manual_meta.pop(hid, None)
            forgot += 1
    return _ok(req, {"forgot": forgot})


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
    if len(magnets_in) > MAX_REGISTER_MAGNETS:
        return _err(req, "bad_request",
                    f"too many magnets (max {MAX_REGISTER_MAGNETS})")

    registered: list[dict] = []
    invalid: list[str] = []

    for raw in magnets_in:
        if not isinstance(raw, str):
            invalid.append(str(raw)[:64])
            continue
        s = raw.strip()
        if len(s) > MAX_MAGNET_URI_LEN:
            invalid.append(s[:64])   # truncate for invalid list so we don't echo full
            continue
        if not s.lower().startswith(_MAGNET_SCHEME):
            invalid.append(s[:64])
            continue

        handle_id, deduped = _intern_magnet(state, s)
        dn = extract_magnet_dn(s)
        # Keep a separate sparse backup even when JavDB metadata currently wins.
        # A later scrape replaces all web groups but retains shared manual
        # handles; if the new web batch omits this BTIH, the backup becomes the
        # truthful metadata for the still-visible manual row.
        manual_meta = {
            "code": "",
            "name": dn,
            "size": "",
            "tags": [],
            "date": "",
            "source": "manual",
            "group_seq": None,
            "group_size": None,
            "date_rank": None,
            "size_rank": None,
        }
        # First manual occurrence wins, matching the frontend's stable group
        # order when the same handle is pasted again.
        state.manual_meta.setdefault(handle_id, manual_meta)
        if handle_id not in state.magnet_meta:
            state.magnet_meta[handle_id] = dict(state.manual_meta[handle_id])
        registered.append({
            "handle_id": handle_id,
            "magnet_redacted": redact_magnet(s),
            "name": dn,
            "deduped": deduped,
        })

    return _ok(req, {"registered": registered, "invalid": invalid})


def cmd_update_settings(state: DaemonState, req: dict) -> dict:
    new_settings = req.get("settings")
    if new_settings is not None and not isinstance(new_settings, dict):
        return _err(req, "bad_request", "settings must be a dict when provided")
    if new_settings is not None:
        state.settings = _normalize_runtime_settings(new_settings)
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
_RD_ERR_INTERNAL = "rd_internal"

_RD_NO_TOKEN_MSG = "RD token not configured"


def _classify_rd_error(message: str) -> str:
    """Bucket a RealDebridError message into a stable error code."""
    m = (message or "").lower()
    if "magnet_error" in m or "磁力解析失敗" in m or "磁力錯誤" in m:
        return _RD_ERR_MAGNET
    if "下載失敗" in m or "download failed" in m:
        return _RD_ERR_DOWNLOAD
    if m.startswith("http 401:") or "token 無效" in m or ("token" in m and "過期" in m):
        return _RD_ERR_AUTH
    if m.startswith("http 403:") or "premium" in m or "權限不足" in m:
        return _RD_ERR_PREMIUM
    if m.startswith("http 429:") or ("rate" in m and "limit" in m) or "頻率過高" in m:
        return _RD_ERR_RATE
    return _RD_ERR_API


def _rd_settings(state: DaemonState) -> dict:
    """Nested `rd` settings, guaranteed dict.

    `settings` itself is type-guarded at the handshake/update_settings
    boundary, but the nested `rd` key is not — a truthy non-dict (string,
    list) would otherwise reach `.get()` and turn every RD command into an
    opaque `internal` envelope until settings are replaced.
    """
    settings = state.settings
    if not isinstance(settings, dict):
        return {}
    rd = settings.get("rd")
    return rd if isinstance(rd, dict) else {}


def _parse_decimal_int(value) -> int | None:
    """Parse a JSON integer/string without letting malformed text escape.

    `str.isdigit()` is not an int() safety check: Unicode superscripts return
    true but cannot be parsed, and stripping '-' accepts strings like '--5'.
    """
    if type(value) is int:
        return value
    if not isinstance(value, str) or not value:
        return None
    digits = value[1:] if value.startswith("-") else value
    if not digits or not digits.isascii() or not digits.isdigit():
        return None
    try:
        return int(value, 10)
    except ValueError:
        return None


def _normalize_runtime_settings(settings) -> dict:
    """Copy settings and clamp persisted RD numerics at the sidecar boundary.

    This function protects both writers of state.settings (handshake and
    update_settings). Request-local overrides have their own parsing path;
    cache_wait is bounded there, while min_size_mb is intentionally forwarded
    as a non-negative integer and remains capped here for persisted settings.
    """
    if not isinstance(settings, dict):
        return {}
    normalized = dict(settings)
    rd_raw = settings.get("rd")
    if not isinstance(rd_raw, dict):
        return normalized
    rd = dict(rd_raw)
    bounds = {
        "cache_wait_seconds": (MIN_RD_CACHE_WAIT_SECS, MAX_RD_CACHE_WAIT_SECS),
        "min_size_mb": (0, MAX_RD_MIN_SIZE_MB),
    }
    for key, (floor, ceiling) in bounds.items():
        if key not in rd:
            continue
        # Parse any signed integer first, then clamp. Using `floor` as
        # the parser minimum would discard cache_wait=1 and fall back to 15,
        # whereas Rust's persisted-settings contract deliberately maps it to
        # the nearest valid value (5).
        value = _parse_decimal_int(rd.get(key))
        if value is None:
            rd.pop(key, None)
        else:
            rd[key] = max(floor, min(value, ceiling))
    normalized["rd"] = rd
    return normalized


def _rd_client(state: DaemonState, token_override: str | None = None,
               min_size_mb: int | None = None, deadline: float | None = None):
    """Build a fresh RealDebrid client. Cheap (just a requests.Session).

    `token_override` lets `rd_user` validate a candidate token without
    mutating state.rd_token until the user confirms.
    """
    from realdebrid import RealDebrid, RealDebridError  # local import: heavy
    token = token_override if token_override is not None else state.rd_token
    if not token:
        raise RealDebridError("RD_API_TOKEN not configured")
    if min_size_mb is None:
        rd_settings = _rd_settings(state)
        min_size_mb = _coerce_int_setting(
            rd_settings.get("min_size_mb"),
            min_value=0,
        )
        if min_size_mb is None:
            min_size_mb = 500

    session = None
    if token_override is None and state.rd_token:
        if getattr(state, "rd_session", None) is None:
            import requests
            state.rd_session = requests.Session()
        session = state.rd_session

    if deadline is not None:
        client = RealDebrid(token, min_size_mb=min_size_mb, deadline=deadline)
    else:
        client = RealDebrid(token, min_size_mb=min_size_mb)
    if session is not None and hasattr(client, "session"):
        client.session = session
        client.session.headers["Authorization"] = f"Bearer {token}"
        client._shared_session = True
    return client


def _resolve_strategy(state: DaemonState, override: str | None) -> str:
    if isinstance(override, str) and override:
        return override
    rd_settings = _rd_settings(state)
    s = rd_settings.get("file_pick")
    return s if isinstance(s, str) and s else "smart"


def _coerce_int_setting(value, *, min_value: int) -> int | None:
    parsed = _parse_decimal_int(value)
    return parsed if parsed is not None and parsed >= min_value else None


def _resolve_int_setting(
    state: DaemonState,
    key: str,
    override,
    default: int,
    *,
    min_value: int = 1,
) -> int:
    result = _coerce_int_setting(override, min_value=min_value)
    if result is not None:
        return result
    rd_settings = _rd_settings(state)
    result = _coerce_int_setting(rd_settings.get(key), min_value=min_value)
    if result is not None:
        return result
    return default



def cmd_rd_user(state: DaemonState, req: dict) -> dict:
    """Validate token + return account snapshot. Token override allowed
    so the settings UI can probe a candidate token before saving."""
    from realdebrid import RealDebridError
    if not state.handshake_done:
        return _err(req, "bad_request", "handshake required before rd_user")
    token_override = req.get("token")
    if token_override is not None and not isinstance(token_override, str):
        return _err(req, "bad_request", "token must be a string when provided")
    if not token_override and not state.rd_token:
        return _err(req, _RD_ERR_NO_TOKEN, _RD_NO_TOKEN_MSG)
    try:
        deadline = time.monotonic() + 50.0
        client = _rd_client(state, token_override=token_override or None, deadline=deadline)
        try:
            info = client.user()
        finally:
            client.close()
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
    if state.rd_token != token:
        if getattr(state, "rd_session", None) is not None:
            try:
                state.rd_session.close()
            except Exception:
                pass
            state.rd_session = None
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
    req_cw_raw = req.get("cache_wait")
    # `type(...) is int` (not isinstance) so bools don't slip through, matching
    # _coerce_int_setting.
    req_has_cw = type(req_cw_raw) is int and req_cw_raw >= 1
    resolved_cw = _resolve_int_setting(
        state, "cache_wait_seconds", req.get("cache_wait"), 15, min_value=1,
    )
    # The Rust caller computes its timeout budget from the request payload:
    # `cache_wait + 90` when present, `15 + 90` when omitted (sidecar_manager.rs
    # timeout_for). Our deadline must stay inside whichever budget Rust used, so
    # only clamp to 15 when the request actually omitted the field.
    cache_wait = resolved_cw if req_has_cw else min(resolved_cw, 15)
    min_size_mb = _resolve_int_setting(
        state, "min_size_mb", req.get("min_size_mb"), 500, min_value=0,
    )

    # Outcome-log bookkeeping. monotonic (not time.time) because elapsed is the
    # field that separates "RD already had it" from "RD downloaded it while we
    # waited" — a wall-clock jump would silently corrupt exactly that.
    started = time.monotonic()
    trail: list[str] = []
    meta = state.magnet_meta.get(handle_id)
    log_ctx = {
        "btih8": _btih8(magnet),
        "meta": meta,
        "cache_wait": cache_wait,
        "file_pick": strategy,
        "min_size_mb": min_size_mb,
    }

    try:
        deadline = time.monotonic() + cache_wait + 75.0
        client = _rd_client(state, min_size_mb=min_size_mb, deadline=deadline)
        try:
            result = client.process_magnet(
                magnet, strategy=strategy, cache_wait=cache_wait,
                observer=trail.append,
            )
        finally:
            client.close()
    except RealDebridError as e:
        code = _classify_rd_error(str(e))
        # Failures are observations too: a magnet that RD refuses outright is a
        # different phenomenon from one that merely queues, and dropping the
        # error rows would bias the hit-rate tables upward.
        rd_outcome_log.log_send(
            outcome="error", elapsed_ms=_elapsed_ms(started), status_trail=trail,
            rd_status=trail[-1] if trail else "", error_code=code, **log_ctx,
        )
        return _err(req, code, str(e))
    except Exception as e:
        rd_outcome_log.log_send(
            outcome="error", elapsed_ms=_elapsed_ms(started), status_trail=trail,
            rd_status=trail[-1] if trail else "", error_code=_RD_ERR_INTERNAL, **log_ctx,
        )
        return _err(req, _RD_ERR_INTERNAL, f"{type(e).__name__}: <redacted>")

    status = result.get("status")
    if status == "completed":
        links = result.get("links", [])
        rd_outcome_log.log_send(
            outcome="completed", elapsed_ms=_elapsed_ms(started), status_trail=trail,
            torrent_id=result.get("torrent_id", ""),
            # process_magnet's completed dict carries no status field; the last
            # thing the poll loop saw is what got us here.
            rd_status=trail[-1] if trail else "",
            files_selected=True, link_count=len(links), **log_ctx,
        )
        return _ok(req, {
            "status": "completed",
            "torrent_id": result.get("torrent_id", ""),
            "name": result.get("name", ""),
            "links": links,
        })
    # pending
    rd_outcome_log.log_send(
        outcome="pending", elapsed_ms=_elapsed_ms(started), status_trail=trail,
        torrent_id=result.get("torrent_id", ""),
        rd_status=result.get("rd_status", ""),
        progress=result.get("progress", 0),
        files_selected=bool(result.get("files_selected", False)),
        **log_ctx,
    )
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
    if not state.handshake_done:
        return _err(req, "bad_request", "handshake required before rd_check_pending")
    if not state.rd_token:
        return _err(req, _RD_ERR_NO_TOKEN, _RD_NO_TOKEN_MSG)
    torrent_id = req.get("torrent_id")
    if not isinstance(torrent_id, str) or not torrent_id:
        return _err(req, "bad_request", "torrent_id must be a non-empty string")
    strategy = _resolve_strategy(state, req.get("strategy"))

    started = time.monotonic()
    try:
        deadline = time.monotonic() + 50.0
        client = _rd_client(state, deadline=deadline)
        try:
            result = client.check_torrent(torrent_id, strategy=strategy, magnet="")
        finally:
            client.close()
    except RealDebridError as e:
        code = _classify_rd_error(str(e))
        rd_outcome_log.log_check(
            outcome="error", elapsed_ms=_elapsed_ms(started),
            torrent_id=torrent_id, error_code=code,
        )
        return _err(req, code, str(e))
    except Exception as e:
        rd_outcome_log.log_check(
            outcome="error", elapsed_ms=_elapsed_ms(started),
            torrent_id=torrent_id, error_code=_RD_ERR_INTERNAL,
        )
        return _err(req, _RD_ERR_INTERNAL, f"{type(e).__name__}: <redacted>")

    status = result.get("status")
    if status == "completed":
        links = result.get("links", [])
        # Joined to the original send row by torrent_id. This pair is the only
        # thing that separates "pending, done four minutes later" from
        # "pending, still nothing days on" — without it every pending row in
        # the log looks identical.
        rd_outcome_log.log_check(
            outcome="completed", elapsed_ms=_elapsed_ms(started),
            torrent_id=torrent_id, rd_status="downloaded",
            progress=100, link_count=len(links),
        )
        return _ok(req, {
            "status": "completed",
            "torrent_id": torrent_id,
            "name": result.get("name", ""),
            "links": links,
        })
    if status == "missing":
        rd_outcome_log.log_check(
            outcome="missing", elapsed_ms=_elapsed_ms(started), torrent_id=torrent_id,
        )
        return _ok(req, {"status": "missing", "torrent_id": torrent_id})
    rd_outcome_log.log_check(
        outcome="pending", elapsed_ms=_elapsed_ms(started), torrent_id=torrent_id,
        rd_status=result.get("rd_status", ""), progress=result.get("progress", 0),
    )
    return _ok(req, {
        "status": "pending",
        "torrent_id": torrent_id,
        "name": result.get("name", ""),
        "rd_status": result.get("rd_status", ""),
        "progress": result.get("progress", 0),
    })


def cmd_shutdown(state: DaemonState, req: dict) -> dict:
    if getattr(state, "rd_session", None) is not None:
        try:
            state.rd_session.close()
        except Exception:
            pass
        state.rd_session = None
    return _ok(req)


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
    "shutdown": cmd_shutdown,
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
    try:
        stdout.write(json.dumps(obj, ensure_ascii=False))
        stdout.write("\n")
        stdout.flush()
    except OSError as e:
        if isinstance(e, BrokenPipeError) or getattr(e, "errno", None) == errno.EPIPE:
            sys.exit(0)
        raise


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
    import logging

    from app_logging import setup_logging
    log_file = setup_logging()
    # The outcome log rides in whatever directory debug.log resolved to; if
    # logging itself could not get a file, we must NOT invent a path of our own.
    #
    # Truthiness of `log_file` is not that signal: setup_logging returns the
    # LAST ATTEMPTED path even when every candidate failed and it degraded to
    # console-only. Trusting it there put `rd_outcomes.jsonl` in the process's
    # current working directory — on Linux, where neither JAVDB_LOG_DIR nor
    # LOCALAPPDATA is set, that is every single run. Ask the root logger whether
    # a file handler actually got attached instead.
    file_backed = any(isinstance(h, logging.FileHandler)
                      for h in logging.getLogger().handlers)
    rd_outcome_log.configure(log_file.parent if (log_file and file_backed) else None)

    run_daemon(sys.stdin, sys.stdout)
    return 0


if __name__ == "__main__":  # pragma: no cover — script entry guard
    sys.exit(main(sys.argv))
