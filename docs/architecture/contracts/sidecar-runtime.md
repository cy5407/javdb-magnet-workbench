# Sidecar Runtime — Function Contracts & Call Trace

Reference for the live Python JSON-lines daemon in [`sidecar/sidecar.py`](../../../sidecar/sidecar.py). This is the process spawned by `SidecarManager::spawn_and_handshake`; it is not a spike-only file.

---

## 1. Runtime Role

`sidecar/sidecar.py` is a synchronous, single-process daemon. Rust writes one UTF-8 JSON object per line to stdin and waits for exactly one JSON object per line from stdout. Stderr is diagnostics-only and must not contain cookies, RD tokens, full magnets, or tracebacks.

### External Dependencies

| Import | Used by | Runtime role |
|---|---|---|
| `javdb_scraper.create_session` | `cmd_fetch_javdb` | Creates the curl/browser-impersonating HTTP session. |
| `javdb_scraper.fetch_magnets` | `cmd_fetch_javdb` | Scrapes a JavDB page and returns code/title/magnet rows. |
| `realdebrid.RealDebrid` | `_rd_client` (lazy import) | Performs all RD HTTP requests. |
| `realdebrid.RealDebridError` | `_rd_client`, `cmd_rd_user`, `cmd_rd_send_magnet`, `cmd_rd_check_pending` (lazy imports) | Stable error bucketing. |
| `requests.Session` | `_rd_client` (lazy import) | One shared session in `state.rd_session`, reused across RD commands that use the stored token. |
| `app_logging.setup_logging` | `main` (lazy import) | Initializes logging before handshake. |
| `javdb_scraper.parse_size_gb` | `_record_group_meta` | Ranks a fetch's rows by file size for the outcome log. |
| `rd_outcome_log` | `main` (`configure`), `cmd_rd_send_magnet` (`log_send`), `cmd_rd_check_pending` (`log_check`) | Appends one JSONL observation per send / check to `rd_outcomes.jsonl`. Every entry point swallows its own failures — the outcome log must never be able to fail a send. Module contract: [`python-legacy.md` §3](python-legacy.md#3-rd_outcome_logpy). |

### State Model

`DaemonState` is the only long-lived mutable object. It keeps:

- handshake snapshot: `handshake_done`, `cookies`, `rd_token`, `settings`, `paths`
- magnet handle table: `handle_id -> full magnet`
- reverse dedupe table: normalized magnet key -> handle_id
- `magnet_meta`: `handle_id -> {code, name, size, tags, date, source, group_seq,
  group_size, date_rank, size_rank}` — the scraped row as it looked at fetch time.
  Written by `cmd_fetch_javdb` / `cmd_register_magnets`, read ONLY by the outcome
  log, dropped alongside the handle in `cmd_forget_magnets`. Group ranks have to be
  computed at fetch time: only the rows the user actually sends reach the log, so
  "was this the oldest of the five?" is unanswerable afterwards.
- `manual_meta`: sparse manual-row backup keyed by handle. At a new scrape-batch
  boundary, a shared handle is restored to this metadata before new web results arrive;
  this covers the case where the new web batch omits that BTIH entirely.
- `active_scrape_batch_id`: prevents retries and later URLs in the same batch from
  resetting first-occurrence metadata while allowing the next replace-all batch to do so.
- `fetch_seq`: monotonic per-session fetch counter, so two fetches of the same JAV
  code stay distinguishable in the log
- `start_time` for `ping`
- `rd_session`: lazily created shared `requests.Session` for RD calls made with the stored
  token. Torn down by `_close_rd_session` (drops the `Authorization` header, closes, sets
  `None`) whenever the credential it carries stops being current: `cmd_rd_set_token` on a
  clear (`null` / `""`) or a change to a different token, `cmd_handshake` when the resulting
  token differs from `state.rd_token`, `cmd_shutdown`, and the `finally` of `run_daemon`

The sidecar persists no protocol state. The one thing it does write is the
append-only outcome log (`rd_outcomes.jsonl`, next to `debug.log`) — a diagnostic
side channel that nothing reads back at runtime. Pending torrent state lives in
Rust (`pending.rs`), and settings/token persistence lives in Rust (`settings.rs`,
`secret_store.rs`).

---

## 2. Protocol Surface

### Request Envelope

Every normal request is a JSON object:

```json
{ "cmd": "fetch_javdb", "request_id": "r-3", "...": "command fields" }
```

`request_id` is not required by the sidecar, but Rust always sends it and rejects responses with mismatched ids.

### Success Envelope

Produced by `_ok`:

```json
{ "ok": true, "request_id": "r-3", "...": "command result" }
```

### Error Envelope

Produced by `_err`:

```json
{
  "ok": false,
  "request_id": "r-3",
  "error": { "code": "bad_request", "message": "...", "internal": "" }
}
```

`internal` is always `""` in the current code (no caller passes it). Uncaught handler exceptions become code `internal` at the dispatch boundary, and unexpected exceptions inside RD handlers become `rd_internal`; both use message `"<ExceptionType>: <redacted>"`. A missing / non-string / unknown `cmd` returns `bad_request` (`unknown command: ...`).

### Commands

`DISPATCH` ([sidecar.py:1270](../../../sidecar/sidecar.py#L1270)) maps 16 commands:

| `cmd` | Handler | Requires handshake | Calls external HTTP |
|---|---|---:|---:|
| `hello` | `cmd_hello` | no | no |
| `handshake` | `cmd_handshake` | no | no |
| `ping` | `cmd_ping` | no | no |
| `fetch_javdb` | `cmd_fetch_javdb` | yes | JavDB |
| `resolve_magnet` | `cmd_resolve_magnet` | no | no |
| `resolve_magnets` | `cmd_resolve_magnets` | no | no |
| `forget_magnets` | `cmd_forget_magnets` | no | no |
| `register_magnets` | `cmd_register_magnets` | no | no |
| `update_settings` | `cmd_update_settings` | no | no |
| `set_cookies` | `cmd_set_cookies` | **yes** | no |
| `cancel` | `cmd_cancel` | no | no-op |
| `shutdown` | `cmd_shutdown` (loop exit in `run_daemon`) | no | no |
| `rd_user` | `cmd_rd_user` | yes + token (stored or `token` override) | RD `/user` |
| `rd_set_token` | `cmd_rd_set_token` | yes | no |
| `rd_send_magnet` | `cmd_rd_send_magnet` | yes + token | RD |
| `rd_check_pending` | `cmd_rd_check_pending` | yes + token | RD |

Rust never sends `cancel` or `shutdown` today (`SidecarManager` only kills the child on `mark_dead` / drop).

---

## 3. Helpers

### Module constants

| Constant | Value | Role |
|---|---|---|
| `PROTOCOL_VERSION` | `1` | Must equal the Rust `sidecar_manager::PROTOCOL_VERSION` sent in `hello`. |
| `SIDECAR_VERSION` | `"0.1.0"` | Reported by `hello`. |
| `MAX_FETCH_MAGNETS` | `1000` | Magnets kept from one `fetch_javdb` page (extra rows are truncated). |
| `MAX_REGISTER_MAGNETS` | `1000` | Max list length for `register_magnets` (over → `bad_request`). |
| `MAX_MAGNET_URI_LEN` | `4096` | Longer magnets are dropped (fetch) or reported `invalid` (register). |
| `MAX_SCRAPE_BATCH_ID_LEN` | `128` | `fetch_javdb.batch_id` upper bound. |
| `MIN_RD_CACHE_WAIT_SECS` / `MAX_RD_CACHE_WAIT_SECS` | `5` / `300` | Clamp for persisted `rd.cache_wait_seconds`; KEEP IN SYNC with `settings.rs` / `sidecar_manager.rs`. |
| `MAX_RD_MIN_SIZE_MB` | `1_000_000` | Ceiling for persisted `rd.min_size_mb`. |
| `_RD_TOKEN_MAX_LEN` | `255` | KEEP IN SYNC with Rust `secret_store::RD_TOKEN_MAX_LEN`. |
| `_JAVDB_ALLOWED_HOST` | `"javdb.com"` | Host allowlist root for `fetch_javdb`. |

### `redact_magnet(uri: str) -> str` ([sidecar.py:87](../../../sidecar/sidecar.py#L87))

**Purpose**: Return a non-secret magnet display string.

**Contract**:
- Params: `uri`, any string.
- Returns: `""` for empty input; `magnet:?xt=urn:btih:<first8>...` when the URI starts with `magnet:?xt=urn:btih:<hex>` (case-insensitive, hex kept as-is); `magnet:...` for other `magnet:` URIs; `<not-a-magnet>` otherwise.
- Side effects: none.
- Errors: none expected.

**Calls**: `_REDACT_MAGNET_RX.match` (`^magnet:\?xt=urn:btih:([a-f0-9]{1,128})`, `re.IGNORECASE`).

**Called by**: `_process_scraped_magnets` (via `cmd_fetch_javdb`), `cmd_register_magnets`.

### `extract_magnet_dn(uri: str) -> str` ([sidecar.py:118](../../../sidecar/sidecar.py#L118))

**Purpose**: Extract URL-decoded `dn=` display name from a magnet.

**Contract**:
- Params: `uri`, any string.
- Returns: first decoded `dn` value (`+` → space, `%XX` decoded), or `""` when absent/empty.
- Side effects: none.
- Errors: none expected for string input.

**Calls**: `urllib.parse.urlparse`, `urllib.parse.parse_qs(..., keep_blank_values=True)`.

**Called by**: `cmd_register_magnets`.

### `parse_cookie_string(s: str) -> dict[str, str]` ([sidecar.py:149](../../../sidecar/sidecar.py#L149))

**Purpose**: Parse a raw browser cookie header into a dict.

**Contract**:
- Params: `s`, cookie header like `k=v; k2=v2`.
- Returns: dict of trimmed key/value pairs; empty/whitespace input → `{}`; pairs without `=` are skipped; pairs containing CR or LF are dropped (F-05, CWE-93).
- Side effects: none.
- Errors: none expected.

**Calls**: string splitting/trimming only.

**Called by**: `cmd_handshake`, `cmd_set_cookies`.

### `DaemonState.__init__(self)` ([sidecar.py:183](../../../sidecar/sidecar.py#L183))

**Purpose**: Initialize per-process mutable state.

**Contract**:
- Params: none beyond `self`.
- Returns: `None`.
- Side effects: records `time.time()` as `start_time`; `rd_session = None`; `active_scrape_batch_id = None`; `fetch_seq = 0`.
- Errors: none expected.

**Called by**: `run_daemon` when no test state is injected.

### `_ok(req: dict, extra: dict | None = None) -> dict` ([sidecar.py:223](../../../sidecar/sidecar.py#L223))

**Purpose**: Build a success response with request correlation.

**Contract**:
- Params: original `req`, optional `extra` fields.
- Returns: dict with `ok: true`, `request_id` (`req.get("request_id")`, may be `None`), and merged extra fields.
- Side effects: none.
- Errors: none expected.

**Called by**: all successful handlers, including `cmd_shutdown`.

### `_err(req: dict, code: str, message: str, internal: str = "") -> dict` ([sidecar.py:230](../../../sidecar/sidecar.py#L230))

**Purpose**: Build a stable error envelope.

**Contract**:
- Params: original `req`, stable `code`, user-facing `message`, optional internal string.
- Returns: dict with `ok: false` and nested `error`.
- Side effects: none.
- Errors: none expected.

**Called by**: validation failures, command failures, and `dispatch` exception boundary.

### `_magnet_dedupe_key(full: str) -> str` ([sidecar.py:313](../../../sidecar/sidecar.py#L313))

**Purpose**: Normalize magnets so equivalent BTIH links reuse one handle.

**Contract**:
- Params: full magnet string.
- Returns: `btih:<lowercase hash>` for the first `xt` value of the form `urn:btih:<hex>` (any case, hex-only); otherwise `raw:<trimmed input>` (or `""` for empty input). The `raw:` namespace keeps non-BTIH inputs from forging a `btih:` collision.
- Side effects: none.
- Errors: none expected.

**Calls**: `urllib.parse.urlparse`, `urllib.parse.parse_qs`.

**Called by**: `_intern_magnet`, `cmd_forget_magnets`.

### `_intern_magnet(state: DaemonState, full: str) -> tuple[str, bool]` ([sidecar.py:350](../../../sidecar/sidecar.py#L350))

**Purpose**: Allocate or reuse a stable per-process magnet handle.

**Contract**:
- Params: daemon `state`, full magnet string.
- Returns: `(handle_id, deduped)` where `handle_id` is `h-<uuid4>` and `deduped` is true if an existing handle was reused.
- Side effects: may mutate `state.magnets` and `state.magnet_to_handle`.
- Errors: none expected.

**Calls**: `_magnet_dedupe_key`, `uuid.uuid4`.

**Called by**: `_process_scraped_magnets` (via `cmd_fetch_javdb`), `cmd_register_magnets`.

### `_is_javdb_host(host: str) -> bool` ([sidecar.py:371](../../../sidecar/sidecar.py#L371))

**Purpose**: Host allowlist for `fetch_javdb` (F-01): true iff `host` (lower-cased) is `javdb.com` or ends with `.javdb.com`.

**Why**: `fetch_magnets` passes the cookie dict on every GET, so any other host would receive `_jdb_session` / `cf_clearance`. Deliberately NOT widened to numeric mirrors (`javdb\d*.com`) — rejected in review because there is no trustworthy list of which numbered domains JavDB owns.

**Called by**: `_validate_javdb_url`.

### `_validate_batch_id(batch_id) -> tuple[str, str] | None` ([sidecar.py:496](../../../sidecar/sidecar.py#L496))

**Purpose**: Return `("bad_request", "batch_id must be a non-empty bounded string")` unless `batch_id` is a non-empty `str` of at most `MAX_SCRAPE_BATCH_ID_LEN` (128) characters; `None` when valid.

**Called by**: `cmd_fetch_javdb`.

### `_validate_javdb_url(url) -> tuple[str, str] | None` ([sidecar.py:502](../../../sidecar/sidecar.py#L502))

**Purpose**: URL gate for `fetch_javdb`. Errors (all `bad_request`): `url must start with https://` (non-string or not `https://`), `url is not a valid URL` (`urlparse` `ValueError`), `url host not allowed` (`_is_javdb_host` false). `None` when valid.

**Called by**: `cmd_fetch_javdb`.

### `_process_scraped_magnets(state, magnets_in) -> list[dict]` ([sidecar.py:522](../../../sidecar/sidecar.py#L522))

**Purpose**: Bound, validate and intern the rows returned by `fetch_magnets`.

**Contract**:
- Truncates to `MAX_FETCH_MAGNETS` rows; silently drops rows whose `magnet` is not a `str`, is longer than `MAX_MAGNET_URI_LEN`, or does not start with `magnet:` (case-insensitive).
- Returns `[{handle_id, name, size, tags, date, magnet_redacted}]` — never the full magnet.
- Side effects: `_intern_magnet` on each kept row.

**Calls**: `_intern_magnet`, `redact_magnet`.

**Called by**: `cmd_fetch_javdb`.

### `_btih8(uri: str) -> str` ([sidecar.py:97](../../../sidecar/sidecar.py#L97))

**Purpose**: First 8 hex chars of a magnet's BTIH, lower-cased — the join key for the outcome log.

**Contract**:
- Params: full magnet URI. Unparseable / empty → `""` (same `_REDACT_MAGNET_RX` as `redact_magnet`).
- Returns: bare hex, e.g. `"0201592f"`. Same 8-char convention as `realdebrid._extract_magnet_hash`.
- Errors: none.

**Why not `redact_magnet()`**: that returns `magnet:?xt=urn:btih:<8hex>...`, and the
release redaction gates ([log-redaction-verification.md:23](../../troubleshooting/log-redaction-verification.md),
[m6a-release-smoke.md:53](../../sessions/m6a-release-smoke.md)) grep the whole log
directory for exactly `magnet:\?xt|urn:btih` expecting zero hits. Bare hex carries
the same joining power without turning a passing gate into a permanent false alarm.

**Called by**: `cmd_rd_send_magnet`.

### `_elapsed_ms(started: float) -> int` ([sidecar.py:113](../../../sidecar/sidecar.py#L113))

**Purpose**: Milliseconds since a `time.monotonic()` mark, floored at 0.

**Why monotonic**: `elapsed_ms` is the field that separates "RD already had this
cached" from "RD downloaded it while we waited" — `time.time()` would let a clock
adjustment corrupt exactly that distinction. (Note `process_magnet`'s own
`cache_wait` budget *does* use wall clock, `realdebrid.py:354`; the two clocks
coexist in one send.)

**Called by**: `cmd_rd_send_magnet`, `cmd_rd_check_pending`.

### `_record_group_meta(state, code, rows, batch_id=None) -> None` ([sidecar.py:400](../../../sidecar/sidecar.py#L400))

**Purpose**: Store each fetched row's raw fields plus its 1-based rank inside that fetch.

**Contract**:
- Duplicate handles are canonicalized first-occurrence-wins, matching the frontend's visible
  row. `group_size`, `date_rank`, and `size_rank` all use that unique-handle set.
- `date_rank` 1 = oldest upload; missing dates sort last via `_NO_DATE_SORT_KEY`
  (`"9999-99-99"`). A raw `""` compares below every ISO date, which would hand
  rank 1 to every undated row — same sentinel and same reasoning as the frontend's
  `rdPriority.rdDateKey`.
- `size_rank` 1 = largest, via `javdb_scraper.parse_size_gb`.
- In the same `batch_id`, the first JavDB group that claims a handle wins. A later batch may
  overwrite it, while manual-only metadata may still be upgraded to JavDB metadata.
- Side effects: writes `state.magnet_meta`. `_batch_id` is an internal ownership marker and is
  excluded by the outcome logger's public-field allowlist.

**Deliberately stores raw values only** — no prefix match, no HD verdict. The
heuristic's single source of truth is `app/src/lib/rdPriority.ts`, and a frozen
verdict would lock old log rows into whatever the rules were the day they were
written. See [the outcome-log spec §2](../../specs/2026-08-01-rd-outcome-log.md).

**Called by**: `cmd_fetch_javdb`.

### `_begin_scrape_meta_batch(state, batch_id) -> None` ([sidecar.py:473](../../../sidecar/sidecar.py#L473))

**Purpose**: Reconcile sidecar metadata when the frontend replaces all visible web groups.

**Contract**:
- A `None` or repeated id is a no-op.
- On a fresh id, old JavDB-only metadata is removed; a handle also owned by a manual row is
  downgraded to its separately stored manual metadata.
- Called before URL validation, so a rejected first URL still settles ownership for the new
  visible batch.

**Called by**: `cmd_fetch_javdb`.

### `_parse_decimal_int(value) -> int | None` ([sidecar.py:845](../../../sidecar/sidecar.py#L845))

**Purpose**: Parse JSON integer or strict ASCII decimal-string settings (optional single minus,
no whitespace) without throwing. Booleans, malformed text, and Unicode-only digits return `None`.

**Called by**: `_normalize_runtime_settings`, `_coerce_int_setting`.

### `_normalize_runtime_settings(settings) -> dict` ([sidecar.py:864](../../../sidecar/sidecar.py#L864))

**Purpose**: Copy persisted settings and enforce the sidecar's RD numeric bounds.

**Contract**:
- Non-dicts become `{}`; unrelated keys and unknown RD keys are preserved.
- Signed integer values clamp to `cache_wait_seconds` 5–300 and `min_size_mb` 0–1,000,000.
  Invalid types are removed so downstream readers use their defaults.
- This is the common boundary for both writers of `state.settings`: handshake and
  `update_settings`.

---

## 4. Command Handlers

### `cmd_hello(state: DaemonState, req: dict) -> dict` ([sidecar.py:242](../../../sidecar/sidecar.py#L242))

**Purpose**: Protocol-version negotiation.

**Contract**:
- Params: `protocol_version` must equal `PROTOCOL_VERSION` (`1`).
- Returns: success with `protocol_version`, `sidecar_version` (`"0.1.0"`), and `engine` (always the literal `"curl_cffi"`); or `protocol_mismatch` (`sidecar v1 vs requested v<n>`).
- Side effects: none.
- Errors: none raised.

**Calls**: `_ok`, `_err`.

**Called by**: `dispatch` for `cmd="hello"`; Rust calls it during `SidecarManager::spawn_and_handshake`.

### `cmd_handshake(state: DaemonState, req: dict) -> dict` ([sidecar.py:270](../../../sidecar/sidecar.py#L270))

**Purpose**: Load startup cookies, token, settings, and paths into sidecar memory.

**Contract**:
- Params: optional `cookies` string (non-string → `{}`), `rd_token`, `settings`, `paths`
  (non-dict → `{}`). Persisted RD numeric settings are copied and clamped before entering
  `state.settings` (`cache_wait_seconds` 5–300; `min_size_mb` 0–1,000,000), because pending
  retry consumes this state directly.
- `rd_token` is validated before storing (F-04): `null` / `""` → no token; a string passing
  `_is_valid_rd_token` is stored; anything else is dropped (`state.rd_token = ""`) and the
  response carries `warnings: [{code: "rd_token_format_invalid", message}]` — the message
  never echoes the value.
- Returns: success envelope (plus `warnings` only when the token was dropped).
- Side effects: mutates `state.cookies`, `state.rd_token`, `state.settings`, `state.paths`, `state.handshake_done`.
  `paths.log_dir` is stored but not re-applied to logging (Rust passes it as `JAVDB_LOG_DIR` at spawn).
  When the resulting token differs from `state.rd_token`, closes the pooled `state.rd_session`
  first (`_close_rd_session`), so a re-handshake never reuses the old credential's pool; the
  same token keeps the pool.
- Errors: none raised.

**Calls**: `parse_cookie_string`, `_is_valid_rd_token`, `_close_rd_session`, `_normalize_runtime_settings`, `_ok`.

**Called by**: Rust `SidecarManager::spawn_and_handshake` immediately after `hello`.

### `cmd_ping(state: DaemonState, req: dict) -> dict` ([sidecar.py:305](../../../sidecar/sidecar.py#L305))

**Purpose**: Liveness and uptime check.

**Contract**:
- Params: none.
- Returns: success with integer `uptime_seconds`.
- Side effects: none.
- Errors: none expected.

**Calls**: `time.time`, `_ok`.

**Called by**: Rust `commands::sidecar_ping`.

### `cmd_fetch_javdb(state: DaemonState, req: dict) -> dict` ([sidecar.py:550](../../../sidecar/sidecar.py#L550))

**Purpose**: Scrape one JavDB URL and intern returned magnets.

**Contract**:
- Params: `url` must be a `https://` URL whose host is `javdb.com` or `*.javdb.com`; required
  `batch_id` must be a non-empty string of at most 128 characters.
- Order: handshake check → `batch_id` validation → `_begin_scrape_meta_batch` → URL validation → network.
- Returns: success with `result: {engine, url, code, title, magnet_count, magnets: [{handle_id, name, size, tags, date, magnet_redacted}]}`
  (`engine` is whatever `create_session` reported: `"curl_cffi"` or `"requests"`); or errors
  `bad_request` (handshake / `batch_id` / URL), `cloudflare_block` (scraper `error` contains `"403"`),
  `network` (`fetch failed: <ExceptionType>` on exception, otherwise the scraper's `error` string, e.g. `HTTP 404`).
- Preconditions: `state.handshake_done` must be true.
- Side effects: creates (and closes) an HTTP session, performs network I/O, may add handles to
  `state.magnets` / `state.magnet_to_handle`, increments `state.fetch_seq`, and records
  first-occurrence metadata per `batch_id`. A new batch may reattribute an intentionally surviving shared handle.
- Errors: catches all exceptions from `create_session` / `fetch_magnets` and redacts type only.

**Calls**: `_validate_batch_id`, `_begin_scrape_meta_batch`, `_validate_javdb_url`, `create_session`, `fetch_magnets`, `_process_scraped_magnets`, `_record_group_meta`, `_ok`, `_err`.

**Called by**: Rust `commands::fetch_javdb`.

### `cmd_resolve_magnet(state: DaemonState, req: dict) -> dict` ([sidecar.py:610](../../../sidecar/sidecar.py#L610))

**Purpose**: Convert one handle back to the full magnet for clipboard/RD use.

**Contract**:
- Params: `handle_id` string.
- Returns: success with full `magnet`, or `bad_request` / `unknown_handle`.
- Side effects: none.
- Errors: none expected.

**Calls**: `_ok`, `_err`.

**Called by**: Rust `commands::copy_magnet`.

### `cmd_resolve_magnets(state: DaemonState, req: dict) -> dict` ([sidecar.py:621](../../../sidecar/sidecar.py#L621))

**Purpose**: Batch-resolve handles for bulk clipboard writes.

**Contract**:
- Params: `handle_ids` list.
- Returns: success with `magnets: [{handle_id, magnet}]` and `unknown: [...]` (unknown ids, and `str(x)` of non-string entries).
- Side effects: none.
- Errors: none expected beyond `bad_request`.

**Calls**: `_ok`, `_err`.

**Called by**: Rust `commands::copy_magnets_bulk`.

### `cmd_forget_magnets(state: DaemonState, req: dict) -> dict` ([sidecar.py:639](../../../sidecar/sidecar.py#L639))

**Purpose**: Clear all or specified in-memory magnet handles.

**Contract**:
- Params: optional `handle_ids` (omitted/null = clear all; `[]` = no-op; list of handle strings = delete specified handles and update reverse index; mixed non-string types return `bad_request` with zero state mutations).
- Returns: success with `forgot` count of deleted handles (duplicates in the list count once).
- Side effects: clear-all empties `state.magnets`, `state.magnet_to_handle`, `state.magnet_meta`, `state.manual_meta` and resets `state.active_scrape_batch_id`; the per-handle path removes each handle from `state.magnets`, `state.magnet_meta`, `state.manual_meta`, and its reverse-index entry when it still points at that handle.
- Errors: `bad_request` (`handle_ids must be a list of strings`) if `handle_ids` is not a list or contains non-string elements.

**Calls**: `_magnet_dedupe_key`, `_ok`, `_err`.

**Called by**: Rust `commands::forget_magnets`.

### `cmd_register_magnets(state: DaemonState, req: dict) -> dict` ([sidecar.py:673](../../../sidecar/sidecar.py#L673))

**Purpose**: Register user-pasted magnets without scraping JavDB.

**Contract**:
- Params: `magnets` list (at most `MAX_REGISTER_MAGNETS` = 1000 entries). Each entry is stripped; non-strings, entries over 4096 chars, and entries not starting with `magnet:` (case-insensitive) go to `invalid` truncated to 64 chars.
- Returns: success with `registered[]` (`{handle_id, magnet_redacted, name, deduped}`, `name` = `extract_magnet_dn`) and `invalid[]`.
- Side effects: interns valid magnets into the handle table; stores a sparse `source:"manual"` record in `state.manual_meta` (first occurrence wins) and copies it into `state.magnet_meta` only when that handle has no metadata yet.
- Errors: `bad_request` when `magnets` is not a list or exceeds the cap.

**Calls**: `_intern_magnet`, `redact_magnet`, `extract_magnet_dn`, `_ok`, `_err`.

**Called by**: Rust `commands::register_magnets`.

### `cmd_update_settings(state: DaemonState, req: dict) -> dict` ([sidecar.py:740](../../../sidecar/sidecar.py#L740))

**Purpose**: Refresh in-memory settings after Rust persists settings.

**Contract**:
- Params: optional `settings`; non-null dict replaces `state.settings` after the same RD
  numeric normalization used by `cmd_handshake`.
- Returns: success.
- Side effects: may mutate `state.settings`.
- Errors: `bad_request` when `settings` is present but not a dict/null.

**Calls**: `_normalize_runtime_settings`, `_ok`, `_err`.

**Called by**: Rust `commands::update_sidecar_settings`.

### `cmd_set_cookies(state: DaemonState, req: dict) -> dict` ([sidecar.py:749](../../../sidecar/sidecar.py#L749))

**Purpose**: Replace `state.cookies` at runtime so refreshing an expired `cf_clearance` does not require restarting the app.

**Contract**:
- Params: `cookies` — `null` / `""` clears; a non-empty `Cookie:`-header-style string (`k=v; k=v`) replaces. Any other type is a `bad_request`.
- **Requires handshake** (F-17): refuses before one is established. This is the only non-RD command besides `fetch_javdb` with that gate — mirrors `cmd_rd_set_token`.
- Returns: success with `set: bool` (`false` on clear, else whether any pair survived parsing).
- Side effects: mutates `state.cookies`.

**No size validation here on purpose**: the Rust caller (`save_cookies` / `migrate_cookies_now`) applies `cookie_store::COOKIES_MAX_BYTES` before the value crosses IPC, and `parse_cookie_string` already drops CR/LF pairs (F-05).

**Calls**: `parse_cookie_string`, `_ok`, `_err`.

**Called by**: Rust `commands::push_cookies_to_sidecar`, used by `save_cookies`, `migrate_cookies_now`, and `clear_cookies` (sends `""`).

### `cmd_cancel(state: DaemonState, req: dict) -> dict` ([sidecar.py:780](../../../sidecar/sidecar.py#L780))

**Purpose**: Protocol-level acknowledgement for future cancellation support.

**Contract**:
- Params: ignored.
- Returns: success.
- Side effects: none.
- Errors: none expected.

**Calls**: `_ok`.

**Important behavior**: It does not interrupt in-flight JavDB/RD work; the daemon is synchronous.

### `cmd_shutdown(state: DaemonState, req: dict) -> dict` ([sidecar.py:1265](../../../sidecar/sidecar.py#L1265))

**Purpose**: Release the shared RD session before the loop exits.

**Contract**:
- Returns: success.
- Side effects: `_close_rd_session(state)` — drops the session's `Authorization` header, closes `state.rd_session` (errors swallowed) and sets it to `None`. The loop exit itself happens in `run_daemon`, which checks `cmd == "shutdown"` before dispatch and returns after emitting the response.

**Calls**: `_close_rd_session`, `_ok`.

---

## 5. Real-Debrid Helpers And Commands

RD error codes (constants at [sidecar.py:802-811](../../../sidecar/sidecar.py#L802)): `rd_token_invalid`, `rd_premium_required`, `rd_rate_limited`, `rd_api_error`, `rd_no_token` (message `RD token not configured`), `rd_magnet_error`, `rd_download_failed`, `rd_internal`. `rd_no_token` and `rd_internal` are emitted directly by handlers; the rest come from `_classify_rd_error`. `cmd_rd_user` additionally emits the literal code `rd_token_format_invalid` (no constant; same string as Rust `secret_store::RD_TOKEN_FORMAT_ERR`) for a malformed `token` override.

### `_classify_rd_error(message: str) -> str` ([sidecar.py:814](../../../sidecar/sidecar.py#L814))

**Purpose**: Map `RealDebridError` text into stable frontend-localizable codes.

**Contract**:
- Params: arbitrary error message (lower-cased before matching).
- Returns, first match wins: `rd_magnet_error` (`magnet_error` / `磁力解析失敗` / `磁力錯誤`), `rd_download_failed` (`下載失敗` / `download failed`), `rd_token_invalid` (starts `http 401:`, `token 無效`, or `token`+`過期`), `rd_premium_required` (starts `http 403:`, `premium`, `權限不足`), `rd_rate_limited` (starts `http 429:`, `rate`+`limit`, `頻率過高`), else `rd_api_error`. Note `realdebrid` reports an exhausted deadline as `HTTP 429: 請求超過時間預算`, so it surfaces as `rd_rate_limited`.
- Side effects: none.
- Errors: none expected.

**Called by**: `cmd_rd_user`, `cmd_rd_send_magnet`, `cmd_rd_check_pending`.

### `_rd_settings(state: DaemonState) -> dict` ([sidecar.py:830](../../../sidecar/sidecar.py#L830))

**Purpose**: Return `state.settings["rd"]` when it is a dict, else `{}` — so a truthy non-dict `rd` cannot turn every RD command into an opaque `internal` envelope.

**Called by**: `_rd_client`, `_resolve_strategy`, `_resolve_int_setting`.

### `_rd_client(state: DaemonState, token_override: str | None = None, min_size_mb: int | None = None, deadline: float | None = None)` ([sidecar.py:899](../../../sidecar/sidecar.py#L899))

**Purpose**: Build a `RealDebrid` client from state or a token override.

**Contract**:
- Params: daemon `state`, optional token override, optional minimum size (default: `rd.min_size_mb` ≥ 0 from settings, else `500`), optional `time.monotonic()` deadline forwarded to `RealDebrid`.
- Returns: `RealDebrid` instance.
- Side effects: imports `realdebrid` lazily. When no override is given and a stored token exists, lazily creates `state.rd_session` (`requests.Session`), attaches it as `client.session`, sets its `Authorization: Bearer <token>` header, and marks `client._shared_session = True` so `client.close()` leaves it open. Override clients (`rd_user` probe) use their own session.
- Errors: raises `RealDebridError("RD_API_TOKEN not configured")` if no token is available.

**Calls**: `RealDebrid(...)`.

**Called by**: `cmd_rd_user`, `cmd_rd_send_magnet`, `cmd_rd_check_pending`.

### `_close_rd_session(state: DaemonState) -> None` ([sidecar.py:1252](../../../sidecar/sidecar.py#L1252))

**Purpose**: Tear down the pooled RD session so neither its `Authorization` header nor its keep-alive sockets outlive the credential they were built for.

**Contract**:
- Params: daemon `state` (read via `getattr(state, "rd_session", None)`, so a partial test state is fine).
- Returns: `None`.
- Side effects: when a session exists — pops `Authorization` from `session.headers` (if it supports `pop`), calls `session.close()`, then sets `state.rd_session = None`. No-op when there is none.
- Errors: exceptions from the header pop / `close()` are swallowed; `rd_session` is reset regardless.

**Calls**: `session.headers.pop`, `session.close`.

**Called by**: `cmd_handshake` (token changed), `cmd_rd_set_token` (clear, or token changed), `cmd_shutdown`, `run_daemon` (`finally`).

### `_resolve_strategy(state: DaemonState, override: str | None) -> str` ([sidecar.py:937](../../../sidecar/sidecar.py#L937))

**Purpose**: Resolve RD file-pick strategy.

**Contract**:
- Params: optional request override.
- Returns: override if non-empty string; else `state.settings.rd.file_pick`; else `"smart"`.
- Side effects: none.
- Errors: none expected.

**Called by**: `cmd_rd_send_magnet`, `cmd_rd_check_pending`.

### `_coerce_int_setting(value, *, min_value: int) -> int | None` ([sidecar.py:945](../../../sidecar/sidecar.py#L945))

**Purpose**: `_parse_decimal_int(value)` if it is `>= min_value`, else `None`.

**Called by**: `_rd_client`, `_resolve_int_setting`.

### `_resolve_int_setting(state: DaemonState, key: str, override, default: int, *, min_value: int = 1) -> int` ([sidecar.py:950](../../../sidecar/sidecar.py#L950))

**Purpose**: Resolve integer settings from request override, then `settings.rd[key]`, then default.

**Contract**:
- Params: settings key, untyped override, default, keyword-only `min_value`.
- Returns: integer `>= min_value` (or `default`).
- Side effects: none.
- Errors: none expected.

**Called by**: `cmd_rd_send_magnet` (`cache_wait_seconds` with `min_value=1`, `min_size_mb` with `min_value=0`).

### `cmd_rd_user(state: DaemonState, req: dict) -> dict` ([sidecar.py:968](../../../sidecar/sidecar.py#L968))

**Purpose**: Validate a candidate or stored RD token and return account metadata.

**Contract**:
- Params: optional `token` string (non-string → `bad_request`); an empty override falls back to the stored token.
- Preconditions: handshake done (`bad_request` otherwise); a non-empty override must pass `_is_valid_rd_token` (error **code** `rd_token_format_invalid`, message the same, returned before any HTTP call — an invalid header value would otherwise surface as an opaque `rd_internal`); override or stored token present (`rd_no_token` otherwise).
- Returns: success with `user: {username, type, expiration, points}`; or stable RD error.
- Side effects: performs RD `/user` HTTP request with a `time.monotonic() + 50.0` deadline; closes the client in `finally`.
- Errors: `rd_token_format_invalid` as above. Note `cmd_rd_set_token` reports the same condition as code `bad_request` with message `rd_token_format_invalid`. Otherwise catches `RealDebridError` (classified) and generic exceptions (`rd_internal`, `<Type>: <redacted>`).

**Calls**: `_is_valid_rd_token`, `_rd_client`, `RealDebrid.user`, `RealDebrid.close`, `_classify_rd_error`, `_ok`, `_err`.

**Called by**: Rust `commands::rd_test_token` (sends `token`), `commands::rd_check_user` (no body).

### `_is_valid_rd_token(token: str) -> bool` ([sidecar.py:1012](../../../sidecar/sidecar.py#L1012))

**Purpose**: Token shape rule (F-04): `0 < len <= 255` and every char ASCII alphanumeric. **KEEP IN SYNC** with Rust `secret_store::is_valid_rd_token` — both sides must accept exactly the same strings.

**Called by**: `cmd_handshake`, `cmd_rd_user`, `cmd_rd_set_token`.

### `cmd_rd_set_token(state: DaemonState, req: dict) -> dict` ([sidecar.py:1033](../../../sidecar/sidecar.py#L1033))

**Purpose**: Update the in-memory RD token after Rust saves or clears it.

**Contract**:
- **Requires handshake** (F-17): `bad_request` (`handshake required before rd_set_token`) before one is established.
- Params: `token` string, or `null` / `""` to clear.
- Returns: success with `set: bool` (`false` on clear).
- Side effects: mutates `state.rd_token`. On a clear (`null` or `""`), and on a change to a different token, calls `_close_rd_session` (drops the `Authorization` header, closes, sets `None`), so neither the header nor keep-alive sockets outlive the old credential and the next RD call builds a session with the new header. Setting the same token keeps the pool.
- Errors: `bad_request` with message `token must be a string` for non-string/non-null; `bad_request` with message `rd_token_format_invalid` when `_is_valid_rd_token` fails (state untouched).

**Calls**: `_is_valid_rd_token`, `_close_rd_session`, `_ok`, `_err`.

**Called by**: Rust `commands::rd_save_token`, `commands::rd_clear_token`, and `commands::import_rd_token` (`apply_legacy_import`'s `.env` token step).

### `cmd_rd_send_magnet(state: DaemonState, req: dict) -> dict` ([sidecar.py:1063](../../../sidecar/sidecar.py#L1063))

**Purpose**: Add one known magnet handle to RD and attempt file selection/cache wait.

**Contract**:
- Params: `handle_id` string; optional `strategy`, `cache_wait`, `min_size_mb`.
- Returns: success with `{status:"completed", torrent_id, name, links}` or `{status:"pending", torrent_id, name, rd_status, progress, files_selected, strategy}`; or stable error.
- Preconditions: handshake done (`bad_request`), token present (`rd_no_token`), `handle_id` a string (`bad_request`) and known (`unknown_handle`).
- Timeout budget alignment: `cache_wait` resolves via `_resolve_int_setting` (request → `rd.cache_wait_seconds` → 15); when the request did not carry an integer `cache_wait >= 1`, the result is capped at 15. `deadline = time.monotonic() + cache_wait + 75.0`, so Python stays inside Rust's `sidecar_manager::timeout_for` budget (`cache_wait + 90`, or `15 + 90 = 105` s when omitted).
- Session lifecycle: `RealDebrid` client is created with `deadline` and `client.close()` runs in a `finally` block on all code paths (the shared `state.rd_session` itself stays open).
- Side effects: performs RD HTTP operations through `RealDebrid.process_magnet`; appends exactly one `event:"send"` row to the outcome log on **every** exit path once preconditions pass — completed, pending and error alike (precondition failures return before any RD call and log nothing). Dropping the error rows would bias the hit-rate tables upward, so failures are observations too.
- Passes `observer=trail.append` into `process_magnet` to capture the RD status transitions; the returned dict only carries the terminal status, so without the callback there is no way to tell "queued behind other downloads" from "actively downloading".
- Errors: catches `RealDebridError` and generic exceptions.

**Calls**: `_resolve_strategy`, `_resolve_int_setting`, `_btih8`, `_elapsed_ms`, `_rd_client`, `RealDebrid.process_magnet`, `RealDebrid.close`, `rd_outcome_log.log_send`, `_classify_rd_error`, `_ok`, `_err`.

**Called by**: Rust `commands::rd_send_magnet` (which persists the pending entry via `pending::add`).

### `cmd_rd_check_pending(state: DaemonState, req: dict) -> dict` ([sidecar.py:1180](../../../sidecar/sidecar.py#L1180))

**Purpose**: Poll one saved RD torrent id.

**Contract**:
- Params: non-empty `torrent_id` string; optional `strategy`.
- Preconditions: handshake done (`bad_request`), token present (`rd_no_token`).
- Returns: success with `{status:"completed", torrent_id, name, links}`, `{status:"missing", torrent_id}`, or `{status:"pending", torrent_id, name, rd_status, progress}`; or stable error.
- Side effects: performs RD HTTP requests through `RealDebrid.check_torrent(torrent_id, strategy=..., magnet="")` with a `time.monotonic() + 50.0` deadline (no magnet: pending records never store it, so `smart` cannot code-match on retry); appends one `event:"check"` row via `rd_outcome_log.log_check` on every exit path after the precondition checks.
- Errors: catches `RealDebridError` (classified) and generic exceptions (`rd_internal`).

**Calls**: `_resolve_strategy`, `_rd_client`, `RealDebrid.check_torrent`, `RealDebrid.close`, `rd_outcome_log.log_check`, `_elapsed_ms`, `_classify_rd_error`, `_ok`, `_err`.

**Called by**: Rust `commands::rd_check_pending`.

---

## 6. Dispatch And Loop

### `dispatch(state: DaemonState, req: dict) -> dict` ([sidecar.py:1290](../../../sidecar/sidecar.py#L1290))

**Purpose**: Route one parsed request to a handler.

**Contract**:
- Params: daemon state and request dict.
- Returns: handler response; a missing / non-string / unknown `cmd` → `bad_request` (`unknown command: <repr>`). `shutdown` goes to `cmd_shutdown`; loop exit happens in `run_daemon`.
- Side effects: handler-dependent.
- Errors: catches all handler exceptions and returns code `internal`, message `<ExceptionType>: <redacted>`.

**Calls**: `DISPATCH.get`, selected handler, `_err`.

**Called by**: `run_daemon`.

### `_emit(stdout: IO[str], obj: dict) -> None` ([sidecar.py:1310](../../../sidecar/sidecar.py#L1310))

**Purpose**: Serialize and flush one response line.

**Contract**:
- Params: text stdout stream, response object.
- Returns: `None`.
- Side effects: writes one JSON line (`ensure_ascii=False`) and flushes.
- Errors: `BrokenPipeError` / `EPIPE` → `sys.exit(0)` (Rust side is gone); other `OSError`s propagate.

**Calls**: `json.dumps`, `stdout.write`, `stdout.flush`.

**Called by**: `run_daemon`.

### `run_daemon(stdin: IO[str], stdout: IO[str], state: DaemonState | None = None) -> None` ([sidecar.py:1321](../../../sidecar/sidecar.py#L1321))

**Purpose**: Main JSON-lines read/dispatch/write loop.

**Contract**:
- Params: text input/output streams; optional injected state for tests.
- Returns: `None` after the loop exits cleanly — either on stdin EOF or after acknowledging `shutdown`. The CLI entry maps this to exit code 0; there is no other terminal state.
- Side effects: reads stdin forever, writes stdout responses, mutates daemon state through handlers.
  On any exit from the loop (EOF, `shutdown`, or a propagating error) a `finally` runs
  `_close_rd_session(state)`. Rust normally ends the sidecar with `child.kill()`
  (`sidecar_manager.rs`), which skips this; it matters when stdin closes because the parent
  died without killing the child.
- Errors: blank lines are skipped; invalid JSON (`invalid JSON line`) and non-object requests (`request must be a JSON object`) become `bad_request` envelopes with `request_id: null`; stream I/O errors may propagate.

**Calls**: `DaemonState`, `json.loads`, `dispatch`, `_emit`, `_close_rd_session`.

**Called by**: `main`.

### `main(argv: list[str]) -> int` ([sidecar.py:1374](../../../sidecar/sidecar.py#L1374))

**Purpose**: CLI entry; parse flags, initialize logging, run daemon.

**Contract**:
- Params: process argv. `--daemon` is accepted but not semantically required; daemon mode is always used.
- Returns: `0` after `run_daemon` returns.
- Side effects: configures logging; configures the outcome log in `log_file.parent` only when the root logger actually has a `FileHandler` (otherwise `rd_outcome_log.configure(None)` disables it — `setup_logging` returns a last-attempted path even in console-only mode, which used to drop `rd_outcomes.jsonl` into the CWD); reads stdin/writes stdout. Module import also reconfigures `sys.stdout` to UTF-8 (`errors="replace"`).
- Errors: argparse may exit for invalid options.

**Calls**: `argparse.ArgumentParser`, `setup_logging`, `rd_outcome_log.configure`, `run_daemon`.

**Called by**: `if __name__ == "__main__"`.

---

## 7. Cross-Layer Trace Summary

```
Rust SidecarManager::request(cmd, body)
└── writes {"cmd": cmd, "request_id": "...", ...}\n to sidecar stdin
    └── run_daemon
        ├── json.loads
        ├── dispatch
        │   └── command handler
        │       ├── JavDB path: create_session → fetch_magnets → _intern_magnet
        │       ├── clipboard path: resolve_magnet(s) from state.magnets
        │       └── RD path: _rd_client → RealDebrid method
        └── _emit JSON response line
            └── Rust line reader receives stdout, verifies request_id
```

Important boundaries:

- Full magnet text crosses from sidecar to Rust only for clipboard operations through `resolve_magnet(s)`.
- Full magnet text crosses from Rust to sidecar for `register_magnets`.
- RD token enters sidecar during initial `handshake`, later `rd_set_token`, and as a candidate `token` on `rd_user` (`rd_test_token`); it is never returned.
- `cancel` is only an ack. Real cancellation currently occurs at JS batch boundaries, not inside the Python process.
