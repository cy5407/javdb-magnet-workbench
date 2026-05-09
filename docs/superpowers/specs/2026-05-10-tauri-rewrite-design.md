---
name: Tauri rewrite production plan
description: Production plan to migrate the JavDB magnet workbench from a single-process tkinter app to a Tauri (Svelte+Rust) UI driven by a long-running PyInstaller Python sidecar daemon. Covers blocker fixes, sidecar protocol, storage layout, UI feature parity, testing, packaging, and 8-milestone roadmap.
type: design
date: 2026-05-10
status: awaiting reviewer approval
---

# Tauri Rewrite — Production Plan

## 1. Context & Decisions Locked-In

This is the production plan for rewriting `javdb_magnet_gui.py` (tkinter) as a Tauri desktop app. Five preceding spikes already closed off alternative architectures:

| Spike | Outcome | Status |
|-------|---------|--------|
| `spikes/rust_fetch_javdb/` | reqwest+rustls → HTTP 403 (Cloudflare TLS fingerprint reject) | Closed: not viable |
| `spikes/rquest_fetch_javdb/` | rquest → Windows BoringSSL build chain blocker (cmake+NASM+MSVC); `rquest-util` GPL-3.0 risk | Closed: not viable |
| `spikes/python_sidecar_protocol/` | Python sidecar via CLI JSON works | Validated baseline |
| `spikes/pyinstaller_sidecar/` | `sidecar.exe` (23.9 MB) + Rust driver works; surfaced 3 packaging issues | Validated; 1 A-blocker open |
| `spikes/tauri_sidecar_poc/` | End-to-end Tauri → sidecar.exe works (probe binary path, not WebView) | Validated |

**Architecture decision (locked):** Tauri UI (Svelte+TS) → Rust orchestration (Tauri 2 + tauri-plugin-store + tauri-plugin-shell) → long-running Python sidecar daemon (PyInstaller, JSON-lines over stdio).

**This document does not change code.** It is a plan submitted for reviewer approval.

---

## 2. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│ Tauri Window (WebView2)                                          │
│   Svelte + TypeScript                                            │
│   - URL batch input / sortable result tree / filter row          │
│   - Settings dialog / Send-RD dialog / Retry dialog / Log viewer │
│   - Receives only: magnet_redacted + magnet_handle               │
│   - Never receives, persists, or logs full magnet                │
└──────────────────────────┬───────────────────────────────────────┘
                           │ Tauri IPC (invoke / events)
┌──────────────────────────▼───────────────────────────────────────┐
│ Rust backend (orchestration)                                     │
│   - PathManager: %APPDATA%/JavDBMagnet/* + %LOCALAPPDATA%/.../logs│
│   - tauri-plugin-store: settings.json (single source of truth)   │
│   - SidecarManager: spawn / health-check / restart / shutdown    │
│   - Tauri commands:                                              │
│       fetch_javdb, send_to_rd, retry_pending,                    │
│       test_token, rd_user, copy_magnet,                          │
│       read_settings, write_settings,                             │
│       list_pending, remove_pending, open_log_file                │
│   - Holds NO full magnet strings in long-lived state             │
│   - copy_magnet: short-lived round-trip → OS clipboard write     │
└──────────────────────────┬───────────────────────────────────────┘
                           │ stdio JSON-lines (long-running daemon)
                           │ Handshake (stdin only, never argv):
                           │   { cookies, rd_token, settings, paths }
┌──────────────────────────▼───────────────────────────────────────┐
│ sidecar.exe (PyInstaller, ~24 MB)                                │
│   - Reuses fetch_magnets / RealDebrid (.process_magnet, .check_) │
│   - All HTTP via curl_cffi (Cloudflare bypass, validated)        │
│   - Owns the **only** copy of full magnet strings                │
│   - Maintains an in-memory MagnetHandleTable (UUID → magnet)     │
│   - Emits redacted magnet + handle_id over the wire              │
│   - Reads cookies/token/settings from handshake; never reads .env│
│     and never calls app_dir()                                    │
└──────────────────────────┬───────────────────────────────────────┘
                           │ HTTPS (curl_cffi, Chrome 124 impersonation)
                       JavDB / Real-Debrid
```

---

## 3. Core Principles

### 3.1 Magnet Boundary

The full magnet URI is the most sensitive data the app handles. The plan enforces strict containment:

| Boundary | Allowed to hold full magnet? |
|----------|------------------------------|
| Frontend (WebView, Svelte stores, localStorage, sessionStorage) | **Never** |
| Tauri event payloads | **Never** |
| Rust long-lived state (Tauri State, tauri-plugin-store) | **Never** |
| Rust short-lived stack frame inside `copy_magnet` / `send_to_rd` | Permitted, must be dropped before returning |
| OS clipboard (system service, short-lived) | Permitted (user-initiated copy) |
| `pending_torrents.json` | **Never** — store `torrent_id` only |
| Log files (Rust, Python, sidecar stderr) | **Never** — only `redact_magnet()` output |
| Sidecar daemon process memory (`MagnetHandleTable`) | **The only authoritative store** |

**Copy-magnet flow:**

```
User clicks "Copy magnet" on row with handle_id=H
  → frontend invoke('copy_magnet', { handle_id: H })
  → Rust: send {cmd:"resolve_magnet", handle_id:H} on sidecar stdin
  → Sidecar replies {magnet: "magnet:?xt=..."} on stdout
  → Rust writes magnet to OS clipboard via tauri-plugin-clipboard-manager
  → Rust drops the local string; returns Ok(()) to frontend
  → Frontend updates status: "已複製磁力連結"  (no payload)
```

Sidecar-side clipboard writes are explicitly rejected for v1 (avoids pulling pyperclip / pywin32 into PyInstaller bundle).

**Manual-paste magnet (Send-RD with user-supplied magnet):** This is the one case where a full magnet originates outside the sidecar. The contract:
1. User pastes magnet into Send-RD dialog text area (browser memory, transient).
2. Frontend sends magnet to Rust via invoke (Tauri IPC, in-process).
3. Rust **does not retain** the magnet — it is forwarded immediately on sidecar stdin as part of `send_rd` request payload.
4. Sidecar inserts it into MagnetHandleTable and processes via existing `process_magnet`.
5. Rust drops the magnet from its local stack frame.
6. The magnet is **not** written to logs at any layer. Tauri IPC payloads are not logged unless `RUST_LOG=trace` (and v1 README explicitly warns to never enable trace logging when handling magnets).

Manual paste is in scope for M5 but flagged as the highest-risk surface; mitigation: input field is `<textarea>` (not `<input>`) so browser autofill won't capture it, and the dialog is modal with explicit "送出" submit.

### 3.2 Settings Authority

Rust owns settings. Sidecar receives a settings snapshot at handshake and never reads files for configuration.

### 3.3 Path Authority

Rust owns all paths. Sidecar receives required paths (data dir for `pending_torrents.json`, optional log dir override) at handshake. Sidecar **never** calls `app_dir()` or `Path(sys.executable).parent`.

### 3.4 No Secrets on argv

`token`, `cookies` content, full magnet strings, and `RD_API_TOKEN` are passed via stdin handshake or per-request stdin frames. They are never argv. Rationale: Windows process listings (`tasklist`, Event Viewer process events, third-party security tools) capture full command lines.

---

## 4. Storage Layout (Locked)

| Purpose | Path | Owner | Format |
|---------|------|-------|--------|
| Settings | `%APPDATA%\JavDBMagnet\settings.json` | Rust (tauri-plugin-store) | JSON |
| Cookies (JavDB session jar) | `%APPDATA%\JavDBMagnet\cookies.txt` | Rust (read into handshake) | Plaintext (semicolon-separated) |
| Pending torrents | `%APPDATA%\JavDBMagnet\pending_torrents.json` | Rust read/write; sidecar receives data via IPC | JSON array |
| Logs (debug.log + rotation) | `%LOCALAPPDATA%\JavDBMagnet\logs\debug.log` | Both Rust and Python write here (separate logger names) | Rotating, 5 MB × 3 |
| Sidecar binary | `<install-dir>\resources\sidecar-x86_64-pc-windows-msvc.exe` | Tauri bundler | Read-only |
| PyInstaller temp extraction | `%TEMP%\_MEIxxxxxx\` | OS-managed; daemon model minimizes residue | Auto-cleanup |

**Forbidden:** sidecar **never** writes to `<exe_dir>`. Settings/cookies/pending **never** ship in installer. Logs **never** ship in installer.

`%APPDATA%` (Roaming) is chosen for settings/cookies/pending so they roam with the user profile across machines if Roaming is configured. `%LOCALAPPDATA%` (Local) is chosen for logs because logs are machine-local debug data.

### 4.1 settings.json schema (v1)

```json
{
  "version": 1,
  "rd": {
    "api_token": "string (token; v1 not OS-keyring protected)",
    "file_pick": "smart|largest|video|all",
    "min_size_mb": 500,
    "cache_wait_seconds": 15,
    "wait_timeout_seconds": 300
  },
  "ui": {
    "scale": "auto | 1.0 | 1.25 | 1.5 | 1.75 | 2.0 | 2.5 | 3.0",
    "theme": "light | dark"
  }
}
```

### 4.2 pending_torrents.json schema (v1)

```json
[
  {
    "torrent_id": "rd-torrent-id",
    "code": "SNOS-192",
    "size_label": "5.62GB, 7個文件",
    "name": "rd-reported filename",
    "added_at": "2026-05-10T14:30:00",
    "progress": 0,
    "rd_status": "magnet_conversion|waiting_files_selection|...",
    "files_selected": false,
    "strategy": "smart"
  }
]
```

**Note the absence of any `magnet` field** — pending entries hold only `torrent_id`, which is what RD's API needs for `check_torrent`. This is the migration delta from current `pending_torrents.json` which stores the full magnet.

### 4.3 Migration from legacy paths

A first-run importer (M7) detects:
- `<old-exe-dir>\.env` → parse and write to `settings.json`
- `<old-exe-dir>\cookies.txt` → copy to `%APPDATA%\JavDBMagnet\cookies.txt`
- `<old-exe-dir>\pending_torrents.json` → copy, **strip `magnet` fields**, write back to `%APPDATA%\JavDBMagnet\pending_torrents.json`

After successful import, show a one-shot dialog explaining that the old files are kept in place (not deleted) and can be removed by the user.

---

## 5. Sidecar Protocol Schema (JSON-lines, v1)

Transport: stdin/stdout, one JSON object per line, UTF-8, `\n` terminator. Stderr reserved for diagnostics (logging output). All requests carry a `request_id` for correlation; responses echo it. Protocol version negotiation occurs in the `hello` handshake.

### 5.1 Lifecycle

```
[Rust spawns sidecar.exe]
  Rust → sidecar (stdin):
    {"cmd":"hello","protocol_version":1,"request_id":"r-0"}
  sidecar → Rust (stdout):
    {"ok":true,"request_id":"r-0","protocol_version":1,
     "sidecar_version":"<from PyInstaller build manifest>",
     "engine":"curl_cffi","curl_cffi_version":"0.14.0"}

  Rust → sidecar:
    {"cmd":"handshake","request_id":"r-1",
     "cookies":"<javdb-cookie-string-from-rust-handshake>",
     "rd_token":"<token-or-null>",
     "settings":{ ... settings.json contents ... },
     "paths":{ "data_dir":"C:/Users/.../AppData/Roaming/JavDBMagnet",
               "log_dir":"C:/Users/.../AppData/Local/JavDBMagnet/logs" }}
  sidecar → Rust:
    {"ok":true,"request_id":"r-1"}

[ready: Rust may now send fetch_javdb / send_rd / etc.]

[shutdown initiated by Rust on app close]
  Rust → sidecar:
    {"cmd":"shutdown","request_id":"r-N"}
  sidecar → Rust:
    {"ok":true,"request_id":"r-N"}
  [sidecar exits 0 within 3s; Rust SIGKILLs after 5s]
```

### 5.2 Commands

#### `ping` (health check)
```
→ {"cmd":"ping","request_id":"..."}
← {"ok":true,"request_id":"...","uptime_seconds":123}
```

#### `fetch_javdb`
```
→ {"cmd":"fetch_javdb","request_id":"...","url":"https://javdb.com/v/RkX3Rp"}
← {"ok":true,"request_id":"...","result":{
     "engine":"curl_cffi","url":"...","code":"SNOS-166","title":"...",
     "magnet_count":3,
     "magnets":[
       {"handle_id":"h-uuid-1","name":"...","size":"4.36GB, 2個文件",
        "tags":["高清"],"date":"2026-05-07",
        "magnet_redacted":"magnet:?xt=urn:btih:0201592f..."}
     ]
   }}
```

The `handle_id` is a UUIDv4 generated by the sidecar; entries live in `MagnetHandleTable` until either the daemon shuts down or `forget_magnets` is called. The handle table has no LRU bound in v1 (a JavDB session rarely exceeds 100 magnets); v2 may add one.

#### `resolve_magnet` (used by `copy_magnet` Rust command)
```
→ {"cmd":"resolve_magnet","request_id":"...","handle_id":"h-uuid-1"}
← {"ok":true,"request_id":"...","magnet":"magnet:?xt=urn:btih:0201592f9a...&dn=..."}
```
Or, if the handle is unknown (daemon was restarted since fetch):
```
← {"ok":false,"request_id":"...","error":{"code":"unknown_handle",
                                          "message":"Magnet handle not in current session"}}
```
Frontend reaction: show "請重新擷取以取得磁力連結" inline error; do not retry automatically.

#### `resolve_magnets` (plural; used by `copy_magnets_bulk`)
```
→ {"cmd":"resolve_magnets","request_id":"...","handle_ids":["h-uuid-1","h-uuid-2","h-uuid-3"]}
← {"ok":true,"request_id":"...",
   "magnets":[
     {"handle_id":"h-uuid-1","magnet":"magnet:?xt=..."},
     {"handle_id":"h-uuid-2","magnet":"magnet:?xt=..."}
   ],
   "unknown":["h-uuid-3"]}
```
Partial-success semantics: known handles are returned; unknown ones go in the `unknown` array. Rust writes the resolved magnets to clipboard joined with `\n`; if any handles were unknown, the status bar shows "已複製 N 個（M 個已過期）".

#### `send_rd`
```
→ {"cmd":"send_rd","request_id":"...",
   "items":[
     {"handle_id":"h-uuid-1","code":"SNOS-166","size_label":"4.36GB, 2個文件"}
   ],
   "manual_magnets":[
     {"magnet":"magnet:?xt=urn:btih:...&dn=...","code":"USER-001","size_label":""}
   ],
   "options":{"strategy":"smart","cache_wait":15,"min_size_mb":500}}

[sidecar streams progress events for each item:]
← {"event":"rd_progress","request_id":"...","index":0,"code":"SNOS-166","message":"新增磁力..."}
← {"event":"rd_progress","request_id":"...","index":0,"code":"SNOS-166","message":"等待解析檔案清單..."}
← {"event":"rd_item_done","request_id":"...","index":0,"code":"SNOS-166",
   "result":{"status":"completed","name":"...","torrent_id":"...","links":[{...}]}}
[or:]
← {"event":"rd_item_done","request_id":"...","index":0,"code":"SNOS-166",
   "result":{"status":"pending","torrent_id":"...","name":"...","progress":42,
             "rd_status":"downloading","files_selected":true}}

[after all items processed:]
← {"ok":true,"request_id":"...","summary":{"completed":2,"pending":1,"errors":0}}
```

`links[].download` is a Real-Debrid unrestricted HTTPS URL (not a magnet) — these are safe to surface to the frontend and may be persisted in app session state for the duration of the dialog.

#### `retry_pending`
```
→ {"cmd":"retry_pending","request_id":"...",
   "items":[
     {"torrent_id":"rd-id-1","code":"SNOS-166","strategy":"smart"}
   ]}
[streams rd_item_done events as above; magnets are not required for retry —
 RD already has the torrent. magnet field is omitted from retry items.]
```

Note: `retry_pending` items do **not** carry a magnet, because RD's `check_torrent` works on `torrent_id`. This is why pending JSON does not store magnets.

#### `rd_user` (token test / show user info)
```
→ {"cmd":"rd_user","request_id":"...","token":"<optional override>"}
← {"ok":true,"request_id":"...","user":{
     "username":"...","type":"premium","expiration":"2026-12-31","points":1000}}
```
If `token` is supplied, sidecar uses it for this single call without persisting (used by Settings dialog "測試連線" before save). Otherwise sidecar uses the token from the most recent `handshake`.

#### `forget_magnets` (clear handle table after "Clear results" button)
```
→ {"cmd":"forget_magnets","request_id":"..."}
← {"ok":true,"request_id":"...","forgot":17}
```

#### `update_settings` (after Settings dialog save)
```
→ {"cmd":"update_settings","request_id":"...","settings":{ ... }}
← {"ok":true,"request_id":"..."}
```
Sidecar updates its in-memory settings; Rust separately persists to `settings.json`.

### 5.3 Error Envelope

All non-OK responses use:
```json
{
  "ok": false,
  "request_id": "...",
  "error": {
    "code": "string-enum (see below)",
    "message": "user-facing summary, redacted",
    "internal": "developer-only detail (logged to file, never sent to frontend)"
  }
}
```

Error code enum (v1):
- `unknown_handle` — sidecar doesn't know the handle_id
- `network` — HTTP/transport failure
- `cloudflare_block` — JavDB returned 403 / challenge detected
- `rd_auth` — RD 401/403
- `rd_rate_limit` — RD 429 after 3 retries
- `rd_torrent_error` — RD reports magnet_error or download error
- `parse_error` — JavDB HTML structure unexpected
- `bad_request` — protocol violation (missing field, wrong type)
- `internal` — uncaught exception

Internal field is **not** forwarded to the frontend by Rust. Rust logs `internal` to the rotating log file and surfaces only `message` to the UI.

### 5.4 Timeout & Cancellation

- Per-request timeout: 60 s default for `fetch_javdb`, 600 s for `send_rd` (sum of all items × cache_wait), 60 s for `retry_pending` per item, 10 s for `ping`/`hello`/`handshake`/`resolve_magnet`/`forget_magnets`/`update_settings`.
- On timeout, Rust sends `{"cmd":"cancel","request_id":"<original>"}`. Sidecar attempts to abort the current HTTP request and emits `{"ok":false,"request_id":"...","error":{"code":"cancelled"}}`.
- If sidecar does not respond to cancel within 5 s, Rust kills the daemon and triggers restart (see 5.5).

### 5.5 Restart Behavior

- On daemon crash (stdout closed, exit code != 0, no response to ping for 30 s), Rust:
  1. Emits a Tauri event `sidecar_state` with `{state: "restarting"}`.
  2. Spawns a new sidecar.exe.
  3. Replays `hello` + `handshake` with current settings/cookies/token.
  4. Emits `sidecar_state` with `{state: "ready"}`.
  5. **Does not** replay in-flight requests automatically. Frontend receives error `{code: "sidecar_restart"}` for affected requests; user must re-trigger.
- Magnet handle table is empty after restart. Frontend shows handles as stale; copy/send operations error with `unknown_handle`; user must re-fetch.
- Maximum 3 automatic restarts in a 5-minute window; further crashes surface a dialog and stop auto-restart.

### 5.6 Protocol Versioning

- `hello` carries `protocol_version: 1` from Rust.
- Sidecar replies with the same field; if mismatch, sidecar refuses with `{ok:false, error:{code:"protocol_mismatch", message:"sidecar v1 vs requested v2"}}` and Rust shows an error dialog ("sidecar 版本不相容，請重新安裝").
- Bumping protocol version requires sidecar.exe rebuild + Tauri rebuild together. Mixed versions are rejected at handshake, not at runtime.

---

## 6. Settings & Token Risk Model (v1)

| Risk | v1 Posture | Post-v1 Hardening |
|------|------------|-------------------|
| RD API token at rest | Plaintext in `settings.json` under `%APPDATA%\JavDBMagnet\` | Move to OS keyring (Windows Credential Manager via `windows-credentials` crate) |
| File ACL | Inherits user-account ACL on `%APPDATA%` (other local users can't read by default) | Same; OS-level guarantee |
| Token in frontend | **Never** in localStorage / sessionStorage / Svelte stores. Settings dialog reads token via `read_settings`, displays masked, writes via `write_settings`. | Same |
| Token in logs | Rust must log `***` instead of token value. Python sidecar's existing `_request` already truncates `data` at 80 chars but does not redact Authorization headers — sidecar must explicitly redact in handshake-acknowledge log line. | Same |
| Token in IPC payload | Tauri IPC is in-process (no network). Acceptable for v1. | Same |
| Cookies file | Plaintext at `%APPDATA%\JavDBMagnet\cookies.txt`. Same threat model as token. | OS keyring or DPAPI-encrypted |
| Token in process tree | Never on argv. Always via stdin handshake. | Same |

**Explicit non-goals for v1:** anti-tamper, anti-debug, encrypted-at-rest beyond OS ACL. This is a personal desktop tool, not a vault.

---

## 7. UI Feature Parity Matrix

Mapped from `javdb_magnet_gui.py:168` (App class) and dialogs.

| Current GUI feature | Source | Tauri equivalent | Milestone |
|---------------------|--------|------------------|-----------|
| URL batch input (multi-line) | App, line ~182 | `<textarea>` in main view | M4 |
| 開始擷取 button + per-URL random delay 3-6s + 429 retry | App, ~291 | `invoke("fetch_javdb")` looped from frontend with delay; sidecar handles single-URL fetch | M4 |
| Status text ("擷取中... i/N") | App, ~213 | Svelte store + status bar | M4 |
| Result tree (parent: 番號+標題; children: 番號/大小/標籤/日期/磁力) | App, ~268 | Svelte component with collapsible groups, sortable columns | M4 |
| Sortable columns (click header) | App, ~456 | Svelte sort logic on local result store | M4 |
| Filter row: keyword / HD-only / min-size / max-size | App, ~217 | Svelte derived store; reactive filter | M4 |
| Group pick: 全部/最大/最小/最少檔案 | App, ~257 | Same | M4 |
| 重置 filter | App, ~250 | Same | M4 |
| 複製篩選後的磁力連結 (bulk copy) | App, ~432 | `copy_magnets_bulk` Tauri command resolves all visible handles → one clipboard write | M4 |
| Double-click row → copy single magnet | App, ~446 | `copy_magnet(handle_id)` per §3.1 flow | M4 |
| 清空結果 | App, ~493 | Frontend clears local store + invoke `forget_magnets` | M4 |
| 送至 Real-Debrid → RDInputDialog | App, ~524 | Modal Svelte dialog; "use scraped" or "manual paste" | M5 |
| RDDialog (per-magnet progress, file picks, links) | App, ~682 | Modal dialog subscribing to `rd_progress`/`rd_item_done` events | M5 |
| 重試待處理 → RetryDialog | App, ~553, ~1145 | Modal with table of pending items, "重新檢查全部"/"移除選取" | M5 |
| 待處理清單持久化 | App, ~39-71 | Rust read/write `%APPDATA%\JavDBMagnet\pending_torrents.json` (no magnet field) | M5 |
| 設定 dialog | App, ~510, ~916 | Modal Svelte form bound to `read_settings`/`write_settings` | M6 |
| 測試連線 (RD user info before save) | App, ~1102 | Calls `rd_user` with override token | M6 |
| 查看日誌 (open with system editor) | App, ~498 | `open_log_file` Tauri command using `tauri-plugin-shell` open | M6 |
| Theme toggle 🌙/☀️ | App, ~513 | Svelte theme store; persists via `write_settings.ui.theme`; CSS variables | M4 (basic toggle) / M6 (settings dialog) |
| DPI scaling | `_apply_dpi_scaling` ~1391 | WebView2 handles DPI natively; CSS `rem` units; Settings UI scale = CSS root font-size multiplier | M4 |
| Per-monitor DPI awareness | `_enable_dpi_awareness` ~1357 | Tauri 2 default; no manual code needed | M2 |

**Out of feature parity for v1** (matches user spec): no auto-retry timer, no scheduled scrapes.

---

## 8. Testing Strategy

### 8.1 Tier 1 — Existing Python unit tests (preserve)

`tests/test_core_logic.py` — 41 tests covering `parse_size_gb`, `parse_file_count`, `RealDebrid._extract_code`, `_filename_matches_code`, `pick_files` (all/video/largest/smart). **Keep running unchanged.** They lock the domain logic that the sidecar inherits unmodified.

Acceptance gate every milestone: `python -m unittest discover -s tests -v` → `Ran 41 tests in <1s OK`.

### 8.2 Tier 2 — New sidecar protocol tests (Python, pytest or unittest)

Location: `tests/test_sidecar_protocol.py`

Coverage:
- `hello` → returns expected version + engine
- `handshake` accepts settings/cookies/token; subsequent `fetch_javdb` request uses them
- `fetch_javdb` for a fixture HTML (saved local file, no network) → returns expected handles + redacted magnets
- `resolve_magnet` returns full magnet for known handle; returns `unknown_handle` error for unknown
- `forget_magnets` empties the table
- Error envelope shape for each error code
- `protocol_mismatch` rejection on bad version
- `cancel` interrupts an in-flight request

These run **without network**. JavDB HTTP fetch is mocked at the `curl_cffi.requests.Session` boundary (or the helper that wraps it). Real-Debrid HTTP is mocked at the `requests.Session` boundary. RD-side behavior is already covered by tier 1; protocol tests focus on the JSON-lines framing, handshake, and error semantics.

### 8.3 Tier 3 — Rust command tests (Rust, `cargo test`)

Location: `app/src-tauri/src/<module>.rs` `#[cfg(test)]` blocks + `app/src-tauri/tests/`

Coverage:
- `PathManager` resolves correct `%APPDATA%`/`%LOCALAPPDATA%` on Windows; XDG fallback on Linux/macOS dev machines
- `SidecarManager`: spawn → handshake → ping (uses a Python script stub that mimics the protocol; not the real PyInstaller exe)
- `MagnetCopyFlow`: round-trips a handle, asserts the local string is dropped (memory safety smoke), asserts no log line contains `magnet:?xt=`
- Settings load/save round-trip via tauri-plugin-store mock
- Error envelope deserialization
- Restart logic: simulated stdout EOF triggers respawn within 3s

### 8.4 Tier 4 — Frontend smoke tests (Vitest + @testing-library/svelte)

Location: `app/src/lib/**/*.test.ts`

Coverage:
- Filter logic: given a fixed result set, filter row produces expected visible rows
- Sort logic: column click reorders correctly
- Settings form validation matches Python's `_validate` (line 1055): min_size_mb non-negative int, cache_wait ≥ 5, wait_timeout ≥ 30, ui_scale either "auto" or 0.5–5.0
- Magnet redaction component never renders a string starting with `magnet:?xt=urn:btih:` followed by full hex (snapshot test)

These do **not** spawn Tauri runtime; they test pure component logic. Tauri integration is covered by the manual smoke checklist below.

### 8.5 Tier 5 — Manual integration smoke (per milestone)

Pre-authorized URL only: `https://javdb.com/v/RkX3Rp`.

Per milestone, document in PR description:
- Which tier 1–4 commands/tests passed
- Manual smoke result for the milestone-specific UI flow
- Confirm no full magnet appeared in: Rust log, Python log, frontend devtools console, network tab, settings.json, pending_torrents.json
- Confirm cookies.txt was deleted from any test scratch location

### 8.6 Secret scan (pre-commit, CI)

Run before every commit:
```powershell
git diff --cached | Select-String -Pattern `
  "RD_API_TOKEN=.+|_jdb_session=|cf_clearance=|Authorization: Bearer|magnet:\?xt=urn:btih:[A-Fa-f0-9]{32,}"
```
Expected: empty. Any match blocks the commit. M8 wires this into a git pre-commit hook (opt-in; documented in CONTRIBUTING).

### 8.7 Authorized vs no-network test split

- **No-network** (run on every PR, every commit): tiers 1–4
- **Authorized integration** (run manually before milestone tag): tier 5 against the pre-authorized URL

CI does not run tier 5; it runs only no-network tiers.

---

## 9. Packaging & Release

### 9.1 Build pipeline

```
1. Rebuild sidecar:
   python spikes/pyinstaller_sidecar/build_sidecar.py
   → dist\sidecar-x86_64-pc-windows-msvc.exe

2. Tauri build (consumes the sidecar via externalBin):
   cd app
   npm run tauri build
   → src-tauri\target\release\bundle\nsis\JavDBMagnet_<ver>_x64-setup.exe
   → src-tauri\target\release\bundle\msi\... (NOT produced; NSIS only)
   → src-tauri\target\release\JavDBMagnet.exe (loose) → repackaged into portable.zip

3. Bundle audit (M8 build script):
   - assert no .env / cookies.txt / *.log / pending_torrents.json in either artifact
   - assert sidecar.exe SHA256 matches the build manifest
```

### 9.2 `tauri.conf.json` `bundle.externalBin`

```json
{
  "bundle": {
    "active": true,
    "targets": ["nsis"],
    "externalBin": ["binaries/sidecar"],
    "windows": {
      "nsis": {
        "installMode": "perUser",
        "displayLanguageSelector": false,
        "languages": ["English", "TradChinese"]
      }
    }
  }
}
```

`binaries/sidecar` resolves at bundle time to `binaries/sidecar-x86_64-pc-windows-msvc.exe` per Tauri's externalBin naming convention.

### 9.3 Sidecar resolution at runtime

| Mode | Path |
|------|------|
| `npm run tauri dev` | Resolved via `tauri_plugin_shell::ShellExt::sidecar()` — Tauri returns the dev-mode path (`src-tauri/binaries/sidecar-...exe`) |
| `npm run tauri build` (NSIS install) | `<install-dir>\resources\sidecar-x86_64-pc-windows-msvc.exe` |
| Portable zip | Same relative path inside the zip; runs from extracted folder |

The Rust code uses `tauri_plugin_shell::Command::new_sidecar("sidecar")` exclusively — no manual path construction (replaces the `locate_sidecar_exe()` from the PoC).

### 9.4 Defender / SmartScreen

V1 ships **unsigned**. Expected user friction:
- SmartScreen blocks first run with "Unknown publisher"; user clicks "More info" → "Run anyway"
- Defender may quarantine on download; whitelist instructions in README

Mitigations in v1:
- README clearly warns
- NSIS installer explicitly is `installMode: perUser` to avoid UAC prompt
- M8 scaffolds a `signtool.exe` step in the build script behind a `SIGN=1` env flag, ready for when a code-signing cert is acquired

Code-signing cert acquisition is **explicitly out of v1 scope**.

### 9.5 Release artifact contents (audit)

NSIS installer must contain:
- `JavDBMagnet.exe` (Tauri main)
- `WebView2Loader.dll` (bundled by Tauri)
- `resources\sidecar-x86_64-pc-windows-msvc.exe`
- `resources\icons\*`
- License/readme

Must NOT contain:
- `.env`, `cookies.txt`, `pending_torrents.json`, `logs\`, `magnet.txt`
- `*.spec`, `build\`, `dist\` (PyInstaller intermediates)
- `target\` (Rust intermediates)
- `.claude\`, `.git\`

Portable zip: same set, directory layout matching install layout.

---

## 10. Phased Roadmap (8 milestones)

Order rationale: Python blockers first (M1) — `app_logging` import-time write to `<exe_dir>\logs` is an A-blocker that contaminates every subsequent sidecar test on read-only deployments. Tauri skeleton (M2) before any sidecar wiring (M3) so reviewers can see the app shell and confirm the storage layout independently.

### M1 — Python production blocker fixes + protocol skeleton (S)

**Purpose:** Eliminate import-time filesystem writes in sidecar; add CLI/stdin handshake plumbing without daemonizing.

**Scope** (Python-only; no Rust, no Tauri changes):
- `app_logging.setup_logging`: convert to lazy init (no mkdir at import); add `JAVDB_LOG_DIR` env var override; mkdir fallback chain `<override>` → `%LOCALAPPDATA%\JavDBMagnet\logs` → console-only
- `javdb_magnet_gui.py`: drop the module-level `setup_logging()` call (line 31); call it from `if __name__ == "__main__":` instead
- `javdb_magnet_gui.py` lines 34-36: keep `app_dir() / "cookies.txt"` for the legacy GUI (it still ships) but mark with `# TODO(M7): legacy path` — do not break the existing tkinter app
- Modify the existing `spikes/python_sidecar_protocol/sidecar.py` (this is the actual source today; `spikes/pyinstaller_sidecar/sidecar.py` does not exist — `build_sidecar.py` packages the protocol-spike script). Add: `--cookies-file <path>` flag, `--env-file <path>` flag, and a `--handshake-stdin` mode that reads one line of JSON `{cookies, rd_token, settings, paths}` from stdin before processing commands.
- Update `spikes/pyinstaller_sidecar/build_sidecar.py` if any new hidden imports / data files are needed by the new flags.
- The sidecar **does not yet** become a long-running daemon. It still exits after one command. Daemon transition (and the promotion to a non-spike location `sidecar/sidecar.py`) is M3.

**What is explicitly NOT in M1:**
- No Tauri code
- No frontend code
- No JSON-lines protocol loop (single-shot CLI still)
- No magnet handle table
- No restart logic

**Acceptance:**
```powershell
python -m unittest discover -s tests -v   # 41 tests pass
python -m py_compile app_logging.py javdb_magnet_gui.py realdebrid.py spikes/python_sidecar_protocol/sidecar.py spikes/pyinstaller_sidecar/build_sidecar.py
# Rebuild sidecar
python spikes/pyinstaller_sidecar/build_sidecar.py
# Smoke 1: sidecar runs in a read-only directory without import-time crash
#          AND finds cookies via --cookies-file (NOT exe-adjacent)
mkdir C:\Temp\readonly_test
copy spikes\pyinstaller_sidecar\dist\sidecar.exe C:\Temp\readonly_test\
icacls C:\Temp\readonly_test /deny "%USERNAME%:(W)"
# Cookies live in user appdata, NOT next to the exe and NOT inside the readonly dir
$env:JAVDB_LOG_DIR = "C:\Temp\sidecar_logs"
$cookiesPath = "$env:APPDATA\JavDBMagnet\cookies.txt"   # user must have placed cookies here for this test
C:\Temp\readonly_test\sidecar.exe fetch-javdb https://javdb.com/v/RkX3Rp --cookies-file "$cookiesPath"
# Expect: exits 0, returns JSON, log lines went to C:\Temp\sidecar_logs\debug.log
#         no write attempted to C:\Temp\readonly_test\

# Smoke 2: same scenario via --handshake-stdin (proves M3-readiness)
$handshake = '{"cookies":"<paste-cookie-string-here>","rd_token":null,"settings":{},"paths":{"data_dir":"' + $env:APPDATA + '\JavDBMagnet","log_dir":"' + $env:LOCALAPPDATA + '\JavDBMagnet\logs"}}'
$handshake | C:\Temp\readonly_test\sidecar.exe fetch-javdb https://javdb.com/v/RkX3Rp --handshake-stdin
# Expect: identical JSON result; cookies never read from filesystem

icacls C:\Temp\readonly_test /reset
del C:\Temp\readonly_test\sidecar.exe
```

**Rollback:** revert the M1 commit; legacy GUI continues to work because `app_logging` lazy init falls back to `app_dir()` if `JAVDB_LOG_DIR` not set.

**Risk:**
- Lazy init might surprise downstream callers that assume the log file exists immediately. Mitigation: keep the existing `setup_logging() → Path` return contract; the path is computed eagerly even though mkdir is deferred.
- The legacy GUI still uses `app_dir()` for cookies/.env; that is intentional — M7 handles migration.

---

### M2 — App skeleton: `app/` directory (M)

**Purpose:** Establish the Tauri 2 + Svelte project scaffold and storage layout without yet integrating the sidecar.

**Scope:**
- New top-level `app/` directory: `app/` (Svelte+Vite frontend), `app/src-tauri/` (Rust)
- Tauri 2 init via `npm create tauri-app@latest -- --template svelte-ts`
- Add plugins: `tauri-plugin-store`, `tauri-plugin-shell`, `tauri-plugin-clipboard-manager`, `tauri-plugin-dialog`
- `PathManager` Rust module: resolves `%APPDATA%\JavDBMagnet\` and `%LOCALAPPDATA%\JavDBMagnet\logs\`; creates dirs on first launch
- `read_settings` / `write_settings` Tauri commands wired to tauri-plugin-store; settings.json schema enforced via serde
- Empty Svelte UI: window opens, displays "JavDBMagnet" header, shows resolved data dir + log dir for verification
- Dark/light theme toggle (CSS variables, persists to settings)
- `.gitignore` updated for `app/node_modules/`, `app/src-tauri/target/`, `app/dist/`

**Acceptance:**
```powershell
cd app
npm install
npm run tauri build         # produces NSIS installer with empty UI
npm run tauri dev           # window opens, header visible, theme toggle works
# Verify storage:
# - %APPDATA%\JavDBMagnet\ exists
# - %APPDATA%\JavDBMagnet\settings.json contains the default schema after first save
# - %LOCALAPPDATA%\JavDBMagnet\logs\ exists
cargo test --manifest-path app/src-tauri/Cargo.toml
```

**Rollback:** delete `app/` directory; nothing else in repo depends on it yet.

**Risk:**
- WebView2 runtime may need installer hint on Windows 10 builds without it. Mitigation: Tauri's NSIS template includes WebView2 bootstrapper detection; document in README.
- `app/` directory placement may conflict with future plans. Decision: top-level `app/` is the cleanest separation; legacy `javdb_magnet_gui.py` and tests remain at root until M7 retirement.

---

### M3 — Sidecar bundling + daemon protocol (M)

**Purpose:** Convert sidecar to JSON-lines daemon; bundle via Tauri externalBin; wire `SidecarManager` in Rust.

**Scope:**
- Promote `spikes/python_sidecar_protocol/sidecar.py` (the actual source today) to a non-spike location: `sidecar/sidecar.py` (new toplevel directory). Update `spikes/pyinstaller_sidecar/build_sidecar.py` accordingly. Both spike directories keep `NOTES.md` pointers to the new location.
- Sidecar daemon main loop: read line, dispatch by `cmd`, write response line. No buffering between requests; flush after each.
- Implement: `hello`, `handshake`, `ping`, `fetch_javdb`, `resolve_magnet`, `resolve_magnets`, `forget_magnets`, `update_settings`, `shutdown`, `cancel` (M5 adds `send_rd`, `retry_pending`, `rd_user`)
- `MagnetHandleTable` (Python dict, UUIDv4 keys). Cleared on `forget_magnets` and on `shutdown`.
- PyInstaller rebuild produces `sidecar-x86_64-pc-windows-msvc.exe` (renamed for Tauri's externalBin naming)
- `tauri.conf.json` adds `bundle.externalBin: ["binaries/sidecar"]`; sidecar exe copied to `app/src-tauri/binaries/` by build script
- `SidecarManager` Rust module: spawn → hello → handshake → ready; ping every 30 s; restart on crash (max 3/5min)
- `fetch_javdb` Tauri command end-to-end: frontend invoke → SidecarManager → daemon → response → frontend receives `{magnets:[{handle_id, magnet_redacted, ...}]}`
- `copy_magnet` Tauri command: handle → resolve → clipboard write → drop string (per §3.1)
- Frontend gets a debug pane that lists handles, lets you click "test copy" — minimal UI just to prove the round-trip

**Acceptance:**
```powershell
python spikes/pyinstaller_sidecar/build_sidecar.py    # or new sidecar/build.py
# Tauri build copies sidecar.exe into bundle
cd app
npm run tauri dev
# In WebView debug pane:
# - click "fetch" with the authorized URL → see 3 redacted magnets + handle IDs
# - click "test copy" on a row → clipboard contains a magnet:? string
# - clipboard string never appears in Rust log, frontend devtools console, or anywhere on disk
# Manual: verify no "magnet:?xt=urn:btih:" appears in:
#   %LOCALAPPDATA%\JavDBMagnet\logs\debug.log
#   app\src-tauri\target\release\... (any file)
cargo test --manifest-path app/src-tauri/Cargo.toml
python -m unittest discover -s tests -v
```

**Rollback:** Revert M3; M2 skeleton still works (no sidecar usage).

**Risk:**
- Daemon stdio buffering deadlock: Python's stdout default buffering can hang Rust reader. Mitigation: `print(json.dumps(resp), flush=True)` after every response; set `sys.stdout.reconfigure(line_buffering=True)` at startup.
- Cookies/token leaking into log via uncaught traceback. Mitigation: top-level `try/except` in daemon loop redacts all error messages before writing to stderr or log.
- Handle table memory growth. Mitigation: `forget_magnets` called on every "Clear results" + on shutdown. v1 has no LRU; documented as v2 work.

---

### M4 — UI: scrape + filter + result tree (L)

**Purpose:** Feature-parity for the JavDB scraping path. **No Real-Debrid yet.**

**Scope subdivided into internal tasks:**

1. **URL input view** — `<textarea>` with line-per-URL parsing; "開始擷取" button; "清空結果" button; status bar
2. **Scrape worker (frontend)** — loops URLs, applies 3-6s random delay between (matching `App.scrape_worker` line 305), invokes `fetch_javdb` per URL; on 429-detected error, waits 10–15s and retries once; emits status updates via Svelte store
3. **Result tree component** — collapsible groups (parent: code+title; children: per-magnet rows); columns 番號/大小/標籤/日期/redacted-magnet; each child row carries `handle_id` in dataset attribute (not visible)
4. **Sortable columns** — click column header → reorder; arrow indicator; matches `App.sort_column` semantics (line 456): special-case for `大小` (parse via `parse_size_gb` ported to TS); other columns lexicographic
5. **Filter row** — keyword (text), 只顯示高清 (checkbox), min/max size GB (numeric), 重置 button, 每組只留 (combobox: 全部顯示/檔案最大的/檔案最小的/檔案數量最少的); reactive Svelte derived store filters the tree
6. **Copy magnet (single)** — double-click row → invoke `copy_magnet(handle_id)` → status "已複製: {code} 的磁力連結"
7. **Copy all visible magnets (bulk)** — invoke `copy_magnets_bulk` Tauri command with the list of currently-visible handle_ids; Rust calls sidecar `resolve_magnets` (plural) once, joins returned magnets with `\n`, writes clipboard, drops string. If any handles unknown (post-restart), copy proceeds for known ones and status reports both counts.
8. **Theme toggle** — 🌙/☀️ button; CSS variables for light/dark; persists via `write_settings.ui.theme`
9. **DPI scale** — read settings.ui.scale; apply via CSS `:root { font-size: calc(16px * var(--ui-scale)); }`
10. **Empty state + error state** — "尚未擷取任何網址" / "[錯誤] {url} - {error}"

**Acceptance:**
```powershell
python -m unittest discover -s tests -v
cargo test --manifest-path app/src-tauri/Cargo.toml
cd app && npm run test          # Vitest tier 4
npm run tauri dev
# Manual smoke (authorized URL only):
# - Paste https://javdb.com/v/RkX3Rp into URL box
# - Click 開始擷取 → see SNOS-166 group with 3 redacted magnets
# - Sort by 大小 → ordering matches Python GUI's sort
# - Filter: keyword "高清" → only 2 rows visible
# - Filter: min size 5 → only 1 row visible
# - Double-click a row → clipboard contains `magnet:?xt=urn:btih:0201592f...&dn=...` (full)
# - Toggle theme → persists across restart
# - Inspect %LOCALAPPDATA%\JavDBMagnet\logs\debug.log: no full magnet present
# - Inspect frontend devtools Application tab: no full magnet in localStorage / sessionStorage / IndexedDB
```

**Rollback:** revert M4; M3 debug-pane scrape still works for sidecar verification.

**Risks:**
- Result tree perf with 100+ rows on slow machines. Mitigation: Svelte's virtual list not needed at this scale; flagged for v2 if reports come in.
- Bulk copy round-trip latency: handled by §5.2 `resolve_magnets` plural variant — one daemon round-trip regardless of N.

---

### M5 — UI: Real-Debrid send + pending retry (L)

**Purpose:** Feature parity for RD operations and persistence.

**Scope subdivided into internal tasks:**

1. **Sidecar protocol additions** — implement `send_rd`, `retry_pending`, `rd_user` per §5.2; streaming events `rd_progress` / `rd_item_done`
2. **Send-RD source-select dialog (RDInputDialog parallel)** — radio: "use scraped (N items)" vs "manual paste"; manual paste textarea; strategy combobox (smart/largest/video/all); 送出/取消
3. **Send-RD progress dialog (RDDialog parallel)** — table with code/filename/size/status/download-link columns; subscribes to streaming events; updates rows as `rd_item_done` arrives
4. **Manual-paste handling** — magnet flows: Svelte form → Tauri invoke `send_to_rd` payload includes `manual_magnets` array → Rust forwards to sidecar without retaining → sidecar inserts into MagnetHandleTable + processes
5. **Pending list persistence (Rust side)** — `list_pending` / `add_pending` / `remove_pending` Tauri commands wrap `pending_torrents.json` r/w; **no magnet field stored** (just torrent_id, code, size_label, name, added_at, progress, rd_status, files_selected, strategy)
6. **Retry dialog (RetryDialog parallel)** — table of pending items; "重新檢查全部" calls sidecar `retry_pending` with all torrent_ids; "移除選取" deletes from JSON only (does not delete RD-side torrent); "複製本次完成連結" writes RD `download` URLs (which are HTTPS, not magnets — safe to surface and persist in dialog state)
7. **Copy RD download links** — same flow as bulk magnet copy, but for `download` URLs which are not sensitive
8. **Token gate** — if `settings.rd.api_token` is empty, send-RD button disabled with tooltip "請先在設定中填入 RD_API_TOKEN"

**Acceptance:**
```powershell
python -m unittest discover -s tests -v
cd sidecar && python -m pytest tests/test_sidecar_protocol.py -v   # tier 2
cargo test --manifest-path app/src-tauri/Cargo.toml
cd app && npm run test
npm run tauri dev
# Manual smoke (authorized URL + valid RD token in settings):
# - Fetch the authorized URL
# - Click 送至 Real-Debrid → dialog opens, "use scraped" pre-selected
# - Strategy: smart → 送出
# - Progress dialog streams events; eventual outcome: completed or pending
# - If pending: close dialog, click 重試待處理 → see pending entry
# - 重新檢查全部 → row updates with current rd_status
# - %APPDATA%\JavDBMagnet\pending_torrents.json: contains entry with NO magnet field
# - Logs contain no full magnet at any tier
# Manual paste smoke:
# - Open send-RD dialog, switch to "manual paste"
# - Paste a known good magnet
# - 送出 → behaves identically
# - Verify magnet appears nowhere in Rust log, settings.json, pending_torrents.json
```

**Rollback:** revert M5; M4 fetch-only flow continues to work.

**Risks:**
- **Manual paste is the highest-risk surface in v1.** Mitigation per §3.1: textarea (not input), modal dialog, no Rust retention, no log writes. If reviewer wants stricter v1, manual paste can be deferred to a v1.1 feature flag — but recommended path is to ship it with the documented mitigations because the current Python GUI has it and removing it is feature-regression.
- Streaming events require backpressure handling if user closes dialog mid-batch. Mitigation: Tauri events fire-and-forget; sidecar continues processing but Rust drops un-listened events. Sidecar always finishes the batch (so RD-side state is consistent).
- `pending_torrents.json` legacy entries (from current GUI) contain magnets. M5 reads them but **does not migrate**; M7's importer drops the magnet field on import.

---

### M6 — UI: settings dialog + log viewer + token test (M)

**Purpose:** Settings UI parity + log viewer.

**Scope:**
- Settings dialog (modal): RD section (token entry with show/hide toggle, RD token URL link), file-pick strategy combobox + dynamic help text matching `update_strategy_help` (line 1046), min size MB, cache wait, wait timeout, UI scale combobox, theme combobox, 測試連線 / 儲存 / 取消 buttons
- 測試連線: invoke `test_token` Tauri command → sidecar `rd_user` with override → display username/type/expiration/points (matching `SettingsDialog.test_connection` line 1102)
- Validation matches Python's `_validate` (line 1055): non-negative min_size_mb, cache_wait ≥ 5, wait_timeout ≥ 30, ui_scale in [0.5, 5.0]
- 查看日誌: `open_log_file` Tauri command using `tauri-plugin-shell` to launch `%LOCALAPPDATA%\JavDBMagnet\logs\debug.log` in default editor
- Settings save → invokes `write_settings` (persists) + sends `update_settings` to sidecar (in-memory propagation)

**Acceptance:**
```powershell
python -m unittest discover -s tests -v
cargo test
cd app && npm run test
npm run tauri dev
# Manual:
# - Open settings dialog
# - Enter RD token, click 測試連線 → see user info
# - Adjust strategy / min size; save
# - settings.json reflects changes
# - sidecar uses new settings on next send_rd (verified by examining size threshold behavior)
# - Click 查看日誌 → debug.log opens in default editor
```

**Rollback:** revert M6; M5 still works but settings can only be edited by hand-editing `settings.json`.

**Risks:**
- Editor launch may fail on user systems without a default `.log` association. Mitigation: fallback to opening containing folder.
- `update_settings` race with an in-flight `send_rd` batch. Mitigation: sidecar applies settings only at request boundaries, not mid-request.

---

### M7 — Migration tool + .env import (S)

**Purpose:** First-launch detection of legacy artifacts; one-shot import wizard.

**Scope:**
- On first launch (no `settings.json` yet), Rust scans for legacy paths:
  - `<install-dir>\.env`, `<install-dir>\cookies.txt`, `<install-dir>\pending_torrents.json` (if user installed v1 over the old tkinter exe location)
  - `%USERPROFILE%\Desktop\程式語言\爬蟲\` and a few common dev paths (configurable list)
- Migration wizard modal: lists detected files, "匯入" / "跳過"
- Import logic:
  - `.env` → parse keys → write to `settings.json`
  - `cookies.txt` → copy bytes to `%APPDATA%\JavDBMagnet\cookies.txt`
  - `pending_torrents.json` → load, drop `magnet` field from each entry, write to new path
- Old files left in place (not deleted); wizard offers a "已匯入完成，可手動刪除舊檔" notice

**Acceptance:**
```powershell
# Setup: place sample .env / cookies.txt / pending_torrents.json (with magnet field) in a test dir
$env:JAVDB_LEGACY_SCAN_DIR = "C:\Temp\legacy_javdb"
npm run tauri dev
# Wizard shows 3 detected files
# Click 匯入
# Verify:
# - %APPDATA%\JavDBMagnet\settings.json populated from .env keys
# - %APPDATA%\JavDBMagnet\cookies.txt matches old file bytes
# - %APPDATA%\JavDBMagnet\pending_torrents.json has entries WITHOUT magnet field
# Run the app — settings/cookies work, pending list visible
```

**Rollback:** revert M7; users with no `settings.json` go through default-empty-settings flow.

**Risks:**
- Legacy `.env` may have keys not in v1 schema. Mitigation: log unknown keys, skip.
- User may have already-encrypted or DPAPI-protected `.env` (unlikely in this codebase). Mitigation: try plaintext parse; on failure, surface error and let user copy values manually.

---

### M8 — Packaging: NSIS installer + portable zip + secret scan (M)

**Purpose:** Production-ready release artifacts.

**Scope:**
- Build script (PowerShell or Node): orchestrates sidecar build + Tauri build + bundle audit + portable zip packaging
- Bundle audit: scans NSIS installer + portable zip contents; fails build if any forbidden file present (see §9.5)
- Secret scan: pre-commit hook (opt-in) running the regex from §8.6
- README updates: install instructions, SmartScreen workaround, portable usage, where settings/logs live, where cookies must be placed (or how to import)
- `signtool.exe` invocation behind `SIGN=1` env var (no-op without cert; tested with self-signed cert in CI placeholder)
- CI workflow (GitHub Actions) running tiers 1–4 on every PR; release workflow on tag triggering build+audit (no sign step in CI without cert secret)

**Acceptance:**
```powershell
.\build-release.ps1
# Output:
#   release\JavDBMagnet_<ver>_x64-setup.exe
#   release\JavDBMagnet_<ver>_portable.zip
#   release\sidecar.sha256
#   release\bundle-audit.txt  (lists every file in both artifacts; flagged forbidden = 0)
# Install on a clean Windows VM (or sandbox):
#   - SmartScreen warning expected; click through
#   - App launches, opens window
#   - Settings dialog works
#   - %APPDATA% / %LOCALAPPDATA% paths created correctly
# Portable test:
#   - Extract zip on USB stick
#   - Run JavDBMagnet.exe
#   - Settings still go to %APPDATA% (per design)
```

**Rollback:** revert M8; M7's app is still launchable from `npm run tauri build` manually.

**Risks:**
- Bundle audit false positive on `WebView2Loader.dll` or vendor binaries. Mitigation: explicit allow-list of expected DLLs.
- `signtool.exe` integration breaks the build for contributors without it. Mitigation: `SIGN=1` opt-in; default off.
- Defender quarantines the sidecar.exe (curl_cffi BoringSSL is sometimes flagged). Mitigation: README workaround; long-term a code-signing cert resolves it.

---

## 11. Things Explicitly NOT in Scope (v1)

1. **No pure-Rust HTTP path** (reqwest/rquest/impit). Closed by spikes.
2. **No new HTTP engine evaluation.** curl_cffi via sidecar is the chosen path.
3. **No GPL-licensed deps in Rust** (rquest-util excluded).
4. **No code-signing certificate purchase.** M8 scaffolds the pipeline; cert acquisition is a separate decision.
5. **No tkinter GUI changes** beyond M1's logging fix. The legacy GUI keeps running unmodified during M1–M7.
6. **No SQLite migration.** Settings → JSON via tauri-plugin-store; pending → JSON. SQLite is overkill for ≤100 pending items.
7. **No agent/automation features.** No auto-retry timer, no scheduled scrapes. Manual triggers only.
8. **No new JavDB URLs** beyond pre-authorized `https://javdb.com/v/RkX3Rp` unless explicitly authorized per request.
9. **No implementation code changes during planning.** This document (the spec itself) is the only output of the planning phase; no `.py` / `.rs` / `.ts` / config files are touched.
10. **No OS keyring integration for RD token.** Deferred post-v1. Token in tauri-plugin-store under `%APPDATA%` ACL is acceptable for v1.
11. **No complete-magnet persistence outside sidecar memory.** Specifically: no full magnet in Rust state (Tauri State, tauri-plugin-store), frontend state (Svelte stores, localStorage, sessionStorage, IndexedDB), logs (Rust log, Python log, sidecar stderr), or `pending_torrents.json`.
12. **No sidecar-side clipboard writes.** Clipboard is a Rust-side responsibility (avoids pulling pyperclip/pywin32 into the bundle).
13. **No mid-request settings hot-reload.** `update_settings` applies at request boundaries.
14. **No automatic in-flight request replay** after sidecar crash. User must re-trigger.
15. **No protocol version-skew tolerance.** Mismatched sidecar.exe and Tauri exe rejected at handshake.
16. **No Linux/macOS support in v1.** Windows-only. (The architecture is portable, but M2–M8 acceptance criteria are Windows-specific.)
17. **No multi-user / shared-machine accommodation.** App is per-user (`installMode: perUser`); shared profiles are out of scope.

---

## 12. Open Questions / Deferred Decisions

- **Code-signing cert acquisition** — defer until v1 ships and SmartScreen friction is measured against actual install volume.
- **Sidecar size optimization** (`--exclude-module tkinter`) — defer to v1.1; quantify after release.
- **Handle table LRU** — defer; current memory growth is bounded by user behavior (~100 magnets/session).
- **Translation / i18n** — current strings are zh-TW; no English UI in v1. Rust error codes are stable English keys (`unknown_handle`, etc.) for log diagnostics.
- **Telemetry / crash reporting** — none in v1. No external network calls outside JavDB / Real-Debrid.

---

## 13. Acceptance Gates (every milestone)

Every milestone PR must include:

```
[ ] python -m unittest discover -s tests -v   → 41/41 OK
[ ] python -m py_compile <changed Python files>
[ ] cargo test --manifest-path app/src-tauri/Cargo.toml   → all passing
[ ] cd app && npm run test   → all passing  (M2+)
[ ] Manual smoke checklist for the milestone (in PR description)
[ ] Secret scan: git diff --cached against the §8.6 regex → empty
[ ] No full magnet in: any committed file, any log path, any JSON file
[ ] No staged: .env / cookies.txt / *.exe / dist/ / build/ / target/ / .claude/ / pending_torrents.json
[ ] git status --short --branch on dev branch
```

---

## 14. Glossary

- **handle_id** — UUIDv4 string identifying an entry in the sidecar's MagnetHandleTable. Crosses the IPC boundary; the magnet it refers to does not.
- **redacted magnet** — a string of the form `magnet:?xt=urn:btih:<8 hex chars>...` produced by `redact_magnet()` in the sidecar. Safe to display, log, and persist.
- **legacy GUI** — `javdb_magnet_gui.py`, the current tkinter app. Shipped alongside the Tauri app during M1–M7; retired or kept-for-fallback per a later decision (out of scope here).
- **PoC sidecar driver** — `spikes/tauri_sidecar_poc/src-tauri/src/bin/probe.rs`. Removed in M3 once SidecarManager replaces it.
