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

### State Model

`DaemonState` is the only long-lived mutable object. It keeps:

- handshake snapshot: `cookies`, `rd_token`, `settings`, `paths`
- magnet handle table: `handle_id -> full magnet`
- reverse dedupe table: normalized magnet key -> handle_id
- `start_time` for `ping`

Nothing is persisted by the sidecar. Pending torrent state lives in Rust (`pending.rs`), and settings/token persistence lives in Rust (`settings.rs`, `secret_store.rs`).

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
- Params: optional `cookies` string, `rd_token`, `settings`, `paths`.
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
- Params: `url` must be an `http://` or `https://` string.
- Returns: success with `result.engine`, `url`, `code`, `title`, `magnet_count`, `magnets[]`; or errors `bad_request`, `cloudflare_block`, `network`.
- Preconditions: `state.handshake_done` must be true.
- Side effects: creates an HTTP session, performs network I/O, may add handles to `state.magnets` / `state.magnet_to_handle`.
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

### `cmd_forget_magnets(state: DaemonState, req: dict) -> dict` ([sidecar.py:308](../../../sidecar/sidecar.py#L308))

**Purpose**: Clear all in-memory magnet handles.

**Contract**:
- Params: currently ignores `handle_ids`; clears all handles.
- Returns: success with `forgot` count.
- Side effects: clears `state.magnets` and `state.magnet_to_handle`.
- Errors: none expected.

**Calls**: `_ok`.

**Called by**: Rust `commands::forget_magnets`.

**Contract mismatch**: Rust may send `handle_ids`, but this handler does not do selective deletion.

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
- Params: optional `settings`; non-null value replaces `state.settings`.
- Returns: success.
- Side effects: may mutate `state.settings`.
- Errors: none expected.

**Calls**: `_ok`.

**Called by**: Rust `commands::update_sidecar_settings`.

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
- Side effects: performs RD HTTP operations through `RealDebrid.process_magnet`.
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
