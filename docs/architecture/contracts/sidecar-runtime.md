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
| `realdebrid.RealDebrid` | `_rd_client` | Performs all RD HTTP requests. |
| `realdebrid.RealDebridError` | RD commands | Stable error bucketing. |
| `app_logging.setup_logging` | `main` | Initializes logging before handshake. |
| `javdb_scraper.parse_size_gb` | `_record_group_meta` | Ranks a fetch's rows by file size for the outcome log. |
| `rd_outcome_log` | `main`, RD commands | Appends one JSONL observation per send / check to `rd_outcomes.jsonl`. Every entry point swallows its own failures — the outcome log must never be able to fail a send. |

### State Model

`DaemonState` is the only long-lived mutable object. It keeps:

- handshake snapshot: `cookies`, `rd_token`, `settings`, `paths`
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

`internal` is currently empty in most expected errors. The dispatch boundary redacts uncaught exception detail as `<redacted>`.

### Commands

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
| `rd_user` | `cmd_rd_user` | token required | RD `/user` |
| `rd_set_token` | `cmd_rd_set_token` | no | no |
| `rd_send_magnet` | `cmd_rd_send_magnet` | yes | RD |
| `rd_check_pending` | `cmd_rd_check_pending` | token required | RD |
| `shutdown` | special in `dispatch` / `run_daemon` | no | no |

---

## 3. Helpers

### `redact_magnet(uri: str) -> str` ([sidecar.py:49](../../../sidecar/sidecar.py#L49))

**Purpose**: Return a non-secret magnet display string.

**Contract**:
- Params: `uri`, any string.
- Returns: `""` for empty input; `magnet:?xt=urn:btih:<first8>...` for parseable BTIH magnets; `magnet:...` for other magnet schemes; `<not-a-magnet>` otherwise.
- Side effects: none.
- Errors: none expected.

**Calls**: `re.match`.

**Called by**: `cmd_fetch_javdb`, `cmd_register_magnets`.

### `extract_magnet_dn(uri: str) -> str` ([sidecar.py:62](../../../sidecar/sidecar.py#L62))

**Purpose**: Extract URL-decoded `dn=` display name from a magnet.

**Contract**:
- Params: `uri`, any string.
- Returns: decoded display name, or `""` when absent/empty.
- Side effects: imports `urllib.parse` lazily.
- Errors: none expected for string input.

**Calls**: `_DN_RX.search`, `urllib.parse.unquote_plus`.

**Called by**: `cmd_register_magnets`.

### `parse_cookie_string(s: str) -> dict[str, str]` ([sidecar.py:86](../../../sidecar/sidecar.py#L86))

**Purpose**: Parse a raw browser cookie header into a dict.

**Contract**:
- Params: `s`, cookie header like `k=v; k2=v2`.
- Returns: dict of trimmed key/value pairs; invalid pairs without `=` are skipped.
- Side effects: none.
- Errors: none expected.

**Calls**: string splitting/trimming only.

**Called by**: `cmd_handshake`.

### `DaemonState.__init__(self)` ([sidecar.py:104](../../../sidecar/sidecar.py#L104))

**Purpose**: Initialize per-process mutable state.

**Contract**:
- Params: none beyond `self`.
- Returns: `None`.
- Side effects: records `time.time()` as `start_time`.
- Errors: none expected.

**Called by**: `run_daemon` when no test state is injected.

### `_ok(req: dict, extra: dict | None = None) -> dict` ([sidecar.py:136](../../../sidecar/sidecar.py#L136))

**Purpose**: Build a success response with request correlation.

**Contract**:
- Params: original `req`, optional `extra` fields.
- Returns: dict with `ok: true`, `request_id`, and merged extra fields.
- Side effects: none.
- Errors: none expected.

**Called by**: all successful handlers and `dispatch` for `shutdown`.

### `_err(req: dict, code: str, message: str, internal: str = "") -> dict` ([sidecar.py:143](../../../sidecar/sidecar.py#L143))

**Purpose**: Build a stable error envelope.

**Contract**:
- Params: original `req`, stable `code`, user-facing `message`, optional internal string.
- Returns: dict with `ok: false` and nested `error`.
- Side effects: none.
- Errors: none expected.

**Called by**: validation failures, command failures, and `dispatch` exception boundary.

### `_magnet_dedupe_key(full: str) -> str` ([sidecar.py:186](../../../sidecar/sidecar.py#L186))

**Purpose**: Normalize magnets so equivalent BTIH links reuse one handle.

**Contract**:
- Params: full magnet string.
- Returns: `btih:<lowercase hash>` when an `xt=urn:btih:` parameter is found; otherwise trimmed input.
- Side effects: none.
- Errors: none expected.

**Calls**: `_BTIH_RX.search`.

**Called by**: `_intern_magnet`.

### `_intern_magnet(state: DaemonState, full: str) -> tuple[str, bool]` ([sidecar.py:211](../../../sidecar/sidecar.py#L211))

**Purpose**: Allocate or reuse a stable per-process magnet handle.

**Contract**:
- Params: daemon `state`, full magnet string.
- Returns: `(handle_id, deduped)` where `deduped` is true if an existing handle was reused.
- Side effects: may mutate `state.magnets` and `state.magnet_to_handle`.
- Errors: none expected.

**Calls**: `_magnet_dedupe_key`, `uuid.uuid4`.

**Called by**: `cmd_fetch_javdb`, `cmd_register_magnets`.

### `_btih8(uri: str) -> str`

**Purpose**: First 8 hex chars of a magnet's BTIH, lower-cased — the join key for the outcome log.

**Contract**:
- Params: full magnet URI. Unparseable / empty → `""`.
- Returns: bare hex, e.g. `"0201592f"`. Same 8-char convention as `realdebrid._extract_magnet_hash`.
- Errors: none.

**Why not `redact_magnet()`**: that returns `magnet:?xt=urn:btih:<8hex>...`, and the
release redaction gates ([log-redaction-verification.md:23](../../troubleshooting/log-redaction-verification.md),
[m6a-release-smoke.md:53](../../sessions/m6a-release-smoke.md)) grep the whole log
directory for exactly `magnet:\?xt|urn:btih` expecting zero hits. Bare hex carries
the same joining power without turning a passing gate into a permanent false alarm.

**Called by**: `cmd_rd_send_magnet`.

### `_elapsed_ms(started: float) -> int`

**Purpose**: Milliseconds since a `time.monotonic()` mark, floored at 0.

**Why monotonic**: `elapsed_ms` is the field that separates "RD already had this
cached" from "RD downloaded it while we waited" — `time.time()` would let a clock
adjustment corrupt exactly that distinction. (Note `process_magnet`'s own
`cache_wait` budget *does* use wall clock, `realdebrid.py:327`; the two clocks
coexist in one send.)

**Called by**: `cmd_rd_send_magnet`, `cmd_rd_check_pending`.

### `_record_group_meta(state, code, rows, batch_id=None) -> None`

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

### `_begin_scrape_meta_batch(state, batch_id) -> None`

**Purpose**: Reconcile sidecar metadata when the frontend replaces all visible web groups.

**Contract**:
- A repeated id is a no-op.
- On a fresh id, old JavDB-only metadata is removed; a handle also owned by a manual row is
  downgraded to its separately stored manual metadata.
- Called before URL validation, so a rejected first URL still settles ownership for the new
  visible batch.

**Called by**: `cmd_fetch_javdb`.

### `_parse_decimal_int(value) -> int | None`

**Purpose**: Parse JSON integer or strict ASCII decimal-string settings (optional single minus,
no whitespace) without throwing. Booleans, malformed text, and Unicode-only digits return `None`.

**Called by**: `_normalize_runtime_settings`, `_coerce_int_setting`.

### `_normalize_runtime_settings(settings) -> dict`

**Purpose**: Copy persisted settings and enforce the sidecar's RD numeric bounds.

**Contract**:
- Non-dicts become `{}`; unrelated keys and unknown RD keys are preserved.
- Signed integer values clamp to `cache_wait_seconds` 5–300 and `min_size_mb` 0–1,000,000.
  Invalid types are removed so downstream readers use their defaults.
- This is the common boundary for both writers of `state.settings`: handshake and
  `update_settings`.

---

## 4. Command Handlers

### `cmd_hello(state: DaemonState, req: dict) -> dict` ([sidecar.py:155](../../../sidecar/sidecar.py#L155))

**Purpose**: Protocol-version negotiation.

**Contract**:
- Params: `protocol_version` must equal `PROTOCOL_VERSION` (`1`).
- Returns: success with `protocol_version`, `sidecar_version`, and `engine`; or `protocol_mismatch`.
- Side effects: none.
- Errors: none raised.

**Calls**: `_ok`, `_err`.

**Called by**: `dispatch` for `cmd="hello"`; Rust calls it during `SidecarManager::spawn_and_handshake`.

### `cmd_handshake(state: DaemonState, req: dict) -> dict` ([sidecar.py:170](../../../sidecar/sidecar.py#L170))

**Purpose**: Load startup cookies, token, settings, and paths into sidecar memory.

**Contract**:
- Params: optional `cookies` string, `rd_token`, `settings`, `paths`. Persisted RD numeric
  settings are copied and clamped before entering `state.settings` (`cache_wait_seconds`
  5–300; `min_size_mb` 0–1,000,000), because pending retry consumes this state directly.
- Returns: success envelope.
- Side effects: mutates `state.cookies`, `state.rd_token`, `state.settings`, `state.paths`, `state.handshake_done`.
- Errors: none raised.

**Calls**: `parse_cookie_string`, `_ok`.

**Called by**: Rust immediately after `hello`.

### `cmd_ping(state: DaemonState, req: dict) -> dict` ([sidecar.py:179](../../../sidecar/sidecar.py#L179))

**Purpose**: Liveness and uptime check.

**Contract**:
- Params: none.
- Returns: success with integer `uptime_seconds`.
- Side effects: none.
- Errors: none expected.

**Calls**: `time.time`, `_ok`.

### `cmd_fetch_javdb(state: DaemonState, req: dict) -> dict` ([sidecar.py:229](../../../sidecar/sidecar.py#L229))

**Purpose**: Scrape one JavDB URL and intern returned magnets.

**Contract**:
- Params: `url` must be a `https://` string; required `batch_id` must be a non-empty string
  of at most 128 characters.
- Returns: success with `result.engine`, `url`, `code`, `title`, `magnet_count`, `magnets[]`; or errors `bad_request`, `cloudflare_block`, `network`.
- Preconditions: `state.handshake_done` must be true.
- Side effects: creates an HTTP session, performs network I/O, may add handles to
  `state.magnets` / `state.magnet_to_handle`, and records first-occurrence metadata per
  `batch_id`. A new batch may reattribute an intentionally surviving shared handle.
- Errors: catches all exceptions from `create_session` / `fetch_magnets` and redacts type only.

**Calls**: `create_session`, `fetch_magnets`, `_intern_magnet`, `redact_magnet`, `_ok`, `_err`.

**Called by**: Rust `commands::fetch_javdb`.

### `cmd_resolve_magnet(state: DaemonState, req: dict) -> dict` ([sidecar.py:279](../../../sidecar/sidecar.py#L279))

**Purpose**: Convert one handle back to the full magnet for clipboard/RD use.

**Contract**:
- Params: `handle_id` string.
- Returns: success with full `magnet`, or `bad_request` / `unknown_handle`.
- Side effects: none.
- Errors: none expected.

**Calls**: `_ok`, `_err`.

**Called by**: Rust `commands::copy_magnet`.

### `cmd_resolve_magnets(state: DaemonState, req: dict) -> dict` ([sidecar.py:290](../../../sidecar/sidecar.py#L290))

**Purpose**: Batch-resolve handles for bulk clipboard writes.

**Contract**:
- Params: `handle_ids` list.
- Returns: success with `magnets: [{handle_id, magnet}]` and `unknown: []`.
- Side effects: none.
- Errors: none expected beyond `bad_request`.

**Calls**: `_ok`, `_err`.

**Called by**: Rust `commands::copy_magnets_bulk`.

### `cmd_forget_magnets(state: DaemonState, req: dict) -> dict` ([sidecar.py:430](../../../sidecar/sidecar.py#L430))

**Purpose**: Clear all or specified in-memory magnet handles.

**Contract**:
- Params: optional `handle_ids` (omitted/null = clear all; `[]` = no-op; list of handle strings = delete specified handles and update reverse index; mixed non-string types return `bad_request` with zero state mutations).
- Returns: success with `forgot` count of deleted handles.
- Side effects: removes matching handles from `state.magnets` and `state.magnet_to_handle`.
- Errors: `bad_request` if `handle_ids` contains non-string elements.

**Calls**: `_ok`, `_err`.

**Called by**: Rust `commands::forget_magnets`.

### `cmd_register_magnets(state: DaemonState, req: dict) -> dict` ([sidecar.py:318](../../../sidecar/sidecar.py#L318))

**Purpose**: Register user-pasted magnets without scraping JavDB.

**Contract**:
- Params: `magnets` list of strings.
- Returns: success with `registered[]` (`handle_id`, redacted magnet, display name, deduped flag) and `invalid[]`.
- Side effects: interns valid magnets into the handle table.
- Errors: none expected beyond `bad_request`.

**Calls**: `_intern_magnet`, `redact_magnet`, `extract_magnet_dn`, `_ok`, `_err`.

**Called by**: Rust `commands::register_magnets`.

### `cmd_update_settings(state: DaemonState, req: dict) -> dict` ([sidecar.py:357](../../../sidecar/sidecar.py#L357))

**Purpose**: Refresh in-memory settings after Rust persists settings.

**Contract**:
- Params: optional `settings`; non-null dict replaces `state.settings` after the same RD
  numeric normalization used by `cmd_handshake`.
- Returns: success.
- Side effects: may mutate `state.settings`.
- Errors: none expected.

**Calls**: `_normalize_runtime_settings`, `_ok`.

**Called by**: Rust `commands::update_sidecar_settings`.

### `cmd_set_cookies(state: DaemonState, req: dict) -> dict`

**Purpose**: Replace `state.cookies` at runtime so refreshing an expired `cf_clearance` does not require restarting the app.

**Contract**:
- Params: `cookies` — `null` / `""` clears; a non-empty `Cookie:`-header-style string (`k=v; k=v`) replaces. Any other type is a `bad_request`.
- **Requires handshake** (F-17): refuses before one is established. This is the only non-RD command besides `fetch_javdb` with that gate — mirrors `cmd_rd_set_token`.
- Returns: success.
- Side effects: mutates `state.cookies`.

**No size validation here on purpose**: the Rust caller (`save_cookies` / `migrate_cookies_now`) applies `cookie_store::COOKIES_MAX_BYTES` before the value crosses IPC, and `parse_cookie_string` already drops CR/LF pairs (F-05).

**Calls**: `parse_cookie_string`, `_ok`, `_err`.

**Called by**: Rust cookie-save and cookie-migration paths.

### `cmd_cancel(state: DaemonState, req: dict) -> dict` ([sidecar.py:364](../../../sidecar/sidecar.py#L364))

**Purpose**: Protocol-level acknowledgement for future cancellation support.

**Contract**:
- Params: ignored.
- Returns: success.
- Side effects: none.
- Errors: none expected.

**Calls**: `_ok`.

**Important behavior**: It does not interrupt in-flight JavDB/RD work; the daemon is synchronous.

---

## 5. Real-Debrid Helpers And Commands

### `_classify_rd_error(message: str) -> str` ([sidecar.py:397](../../../sidecar/sidecar.py#L397))

**Purpose**: Map `RealDebridError` text into stable frontend-localizable codes.

**Contract**:
- Params: arbitrary error message.
- Returns: one of `rd_token_invalid`, `rd_premium_required`, `rd_rate_limited`, `rd_magnet_error`, `rd_download_failed`, or `rd_api_error`.
- Side effects: none.
- Errors: none expected.

**Called by**: `cmd_rd_user`, `cmd_rd_send_magnet`, `cmd_rd_check_pending`.

### `_rd_client(state: DaemonState, token_override: str | None = None, min_size_mb: int | None = None)` ([sidecar.py:413](../../../sidecar/sidecar.py#L413))

**Purpose**: Build a fresh `RealDebrid` client from state or a token override.

**Contract**:
- Params: daemon `state`, optional token override, optional minimum size.
- Returns: `RealDebrid` instance.
- Side effects: imports `realdebrid` lazily; creates a `requests.Session` inside `RealDebrid`.
- Errors: raises `RealDebridError` if no token is configured.

**Calls**: `RealDebrid(...)`.

**Called by**: `cmd_rd_user`, `cmd_rd_send_magnet`, `cmd_rd_check_pending`.

### `_resolve_strategy(state: DaemonState, override: str | None) -> str` ([sidecar.py:433](../../../sidecar/sidecar.py#L433))

**Purpose**: Resolve RD file-pick strategy.

**Contract**:
- Params: optional request override.
- Returns: override if non-empty string; else `state.settings.rd.file_pick`; else `"smart"`.
- Side effects: none.
- Errors: none expected.

**Called by**: `cmd_rd_send_magnet`, `cmd_rd_check_pending`.

### `_resolve_int_setting(state: DaemonState, key: str, override, default: int) -> int` ([sidecar.py:441](../../../sidecar/sidecar.py#L441))

**Purpose**: Resolve positive integer settings from request override, settings, or default.

**Contract**:
- Params: settings key, untyped override, default.
- Returns: positive integer.
- Side effects: none.
- Errors: none expected.

**Called by**: `cmd_rd_send_magnet`.

### `cmd_rd_user(state: DaemonState, req: dict) -> dict` ([sidecar.py:455](../../../sidecar/sidecar.py#L455))

**Purpose**: Validate a candidate or stored RD token and return account metadata.

**Contract**:
- Params: optional `token` string.
- Returns: success with `user.username`, `type`, `expiration`, `points`; or stable RD error.
- Side effects: performs RD `/user` HTTP request.
- Errors: catches `RealDebridError` and generic exceptions.

**Calls**: `_rd_client`, `client._request("GET", "/user")`, `_classify_rd_error`, `_ok`, `_err`.

**Called by**: Rust `rd_test_token`, `rd_check_user`.

### `cmd_rd_set_token(state: DaemonState, req: dict) -> dict` ([sidecar.py:481](../../../sidecar/sidecar.py#L481))

**Purpose**: Update the in-memory RD token after Rust saves or clears it.

**Contract**:
- Params: `token` string, or `null` to clear.
- Returns: success with `set: bool`.
- Side effects: mutates `state.rd_token`.
- Errors: `bad_request` when `token` is neither string nor null.

**Calls**: `_ok`, `_err`.

**Called by**: Rust `rd_save_token`, `rd_clear_token`.

### `cmd_rd_send_magnet(state: DaemonState, req: dict) -> dict` ([sidecar.py:494](../../../sidecar/sidecar.py#L494))

**Purpose**: Add one known magnet handle to RD and attempt file selection/cache wait.

**Contract**:
- Params: `handle_id` string; optional `strategy`, `cache_wait`, `min_size_mb`.
- Returns: success with `status="completed"` and `links`, or `status="pending"` with torrent/progress fields; or stable error.
- Preconditions: handshake done, token present, handle exists.
- Timeout budget alignment: `effective_cache_wait` is bounded by `req`'s `cache_wait` baseline (15 if missing in `req`); `deadline = time.monotonic() + effective_cache_wait + 75.0`, keeping Python's budget (max 90s when `req` omits `cache_wait`) strictly within Rust's 105s timeout limit.
- Session lifecycle: `RealDebrid` client is created with `deadline` and strictly closed via `finally` block on all code paths.
- Side effects: performs RD HTTP operations through `RealDebrid.process_magnet`; appends exactly one `event:"send"` row to the outcome log on **every** exit path — completed, pending and error alike. Dropping the error rows would bias the hit-rate tables upward, so failures are observations too.
- Passes `observer=trail.append` into `process_magnet` to capture the RD status transitions; the returned dict only carries the terminal status, so without the callback there is no way to tell "queued behind other downloads" from "actively downloading".
- Errors: catches `RealDebridError` and generic exceptions.

**Calls**: `_resolve_strategy`, `_resolve_int_setting`, `_rd_client`, `RealDebrid.process_magnet`, `_classify_rd_error`, `_ok`, `_err`.

**Called by**: Rust `rd_send_magnet`.

### `cmd_rd_check_pending(state: DaemonState, req: dict) -> dict` ([sidecar.py:548](../../../sidecar/sidecar.py#L548))

**Purpose**: Poll one saved RD torrent id.

**Contract**:
- Params: non-empty `torrent_id` string; optional `strategy`.
- Returns: success with `status="completed"`, `"missing"`, or `"pending"`; or stable error.
- Side effects: performs RD HTTP requests through `RealDebrid.check_torrent`.
- Errors: catches `RealDebridError` and generic exceptions.

**Calls**: `_resolve_strategy`, `_rd_client`, `RealDebrid.check_torrent`, `_classify_rd_error`, `_ok`, `_err`.

**Called by**: Rust `rd_check_pending`.

---

## 6. Dispatch And Loop

### `dispatch(state: DaemonState, req: dict) -> dict` ([sidecar.py:609](../../../sidecar/sidecar.py#L609))

**Purpose**: Route one parsed request to a handler.

**Contract**:
- Params: daemon state and request dict.
- Returns: handler response; `shutdown` is acknowledged here but loop exit happens in `run_daemon`.
- Side effects: handler-dependent.
- Errors: catches all handler exceptions and returns `internal` with redacted type.

**Calls**: `DISPATCH.get`, selected handler, `_ok`, `_err`.

**Called by**: `run_daemon`.

### `_emit(stdout: IO[str], obj: dict) -> None` ([sidecar.py:633](../../../sidecar/sidecar.py#L633))

**Purpose**: Serialize and flush one response line.

**Contract**:
- Params: text stdout stream, response object.
- Returns: `None`.
- Side effects: writes one JSON line and flushes.
- Errors: I/O errors propagate to caller.

**Calls**: `json.dumps`, `stdout.write`, `stdout.flush`.

**Called by**: `run_daemon`.

### `run_daemon(stdin: IO[str], stdout: IO[str], state: DaemonState | None = None) -> None` ([sidecar.py:639](../../../sidecar/sidecar.py#L639))

**Purpose**: Main JSON-lines read/dispatch/write loop.

**Contract**:
- Params: text input/output streams; optional injected state for tests.
- Returns: `None` after the loop exits cleanly — either on stdin EOF or after acknowledging `shutdown`. The CLI entry maps this to exit code 0; there is no other terminal state.
- Side effects: reads stdin forever, writes stdout responses, mutates daemon state through handlers.
- Errors: invalid JSON and non-object requests are converted to error envelopes; stream I/O errors may propagate.

**Calls**: `DaemonState`, `json.loads`, `dispatch`, `_emit`.

**Called by**: `main`.

### `main(argv: list[str]) -> int` ([sidecar.py:687](../../../sidecar/sidecar.py#L687))

**Purpose**: CLI entry; parse flags, initialize logging, run daemon.

**Contract**:
- Params: process argv. `--daemon` is accepted but not semantically required; daemon mode is always used.
- Returns: daemon exit code.
- Side effects: configures logging; reads stdin/writes stdout.
- Errors: argparse may exit for invalid options.

**Calls**: `argparse.ArgumentParser`, `setup_logging`, `run_daemon`.

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
- RD token enters sidecar during initial `handshake` and later `rd_set_token`; it is never returned.
- `cancel` is only an ack. Real cancellation currently occurs at JS batch boundaries, not inside the Python process.
