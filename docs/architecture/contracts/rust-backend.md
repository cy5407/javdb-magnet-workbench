# Rust Backend — Function Contracts & Call Trace

Reference document for the Tauri 2.x Rust backend powering JavDBMagnet. Each function has a contract entry (params / returns / side effects / errors / async / authorization), an outbound call list, and a reverse "called by" list.

All file:line references are absolute to the workspace root.

---

## 1. Overview

### Crate

- Crate name: `javdbmagnet_lib` (library) + thin `javdbmagnet` binary entry.
- Edition / runtime: Tauri 2 with `tauri::async_runtime` (tokio under the hood).
- Top-level module layout (declared in [lib.rs:1-7](app/src-tauri/src/lib.rs:1)):
  - `commands` — `#[tauri::command]` exports (the JS-callable API surface).
  - `path_manager` — resolves `%APPDATA%\JavDBMagnet` and `%LOCALAPPDATA%\JavDBMagnet\logs`.
  - `pending` — `pending_torrents.json` CRUD with atomic write.
  - `legacy_import` — pure parse/sanitize for the M7a-lite import flow.
  - `secret_store` — RD token via the OS credential manager (`keyring` crate).
  - `settings` — `tauri-plugin-store`-backed `settings.json` schema.
  - `sidecar_manager` — long-lived Python sidecar with line-delimited JSON RPC.

### Binary entry → library entry

- [main.rs:4-6](app/src-tauri/src/main.rs:4) `fn main()` → `javdbmagnet_lib::run()`.
- [build.rs:1-3](app/src-tauri/build.rs:1) build-script `fn main()` → `tauri_build::build()` (Cargo build time, not runtime).
- [lib.rs:87-155](app/src-tauri/src/lib.rs:87) `pub fn run()` builds the Tauri app, registers plugins, wires `setup`, declares `invoke_handler`.

### Tauri command surface (JS-callable API)

Registered via `tauri::generate_handler!` at [lib.rs:123-152](app/src-tauri/src/lib.rs:123). In source order:

| Command | Module | Async | File:Line |
|---|---|---|---|
| `get_paths` | settings | sync | [settings.rs:91](app/src-tauri/src/settings.rs:91) |
| `read_settings` | settings | sync | [settings.rs:99](app/src-tauri/src/settings.rs:99) |
| `write_settings` | settings | sync | [settings.rs:117](app/src-tauri/src/settings.rs:117) |
| `sidecar_ping` | commands | async | [commands.rs:29](app/src-tauri/src/commands.rs:29) |
| `fetch_javdb` | commands | async | [commands.rs:34](app/src-tauri/src/commands.rs:34) |
| `copy_magnet` | commands | async | [commands.rs:53](app/src-tauri/src/commands.rs:53) |
| `copy_magnets_bulk` | commands | async | [commands.rs:164](app/src-tauri/src/commands.rs:164) |
| `copy_rd_links_bulk` | commands | async | [commands.rs:223](app/src-tauri/src/commands.rs:223) |
| `forget_magnets` | commands | async | [commands.rs:147](app/src-tauri/src/commands.rs:147) |
| `register_magnets` | commands | async | [commands.rs:117](app/src-tauri/src/commands.rs:117) |
| `rd_has_token` | commands | async | [commands.rs:285](app/src-tauri/src/commands.rs:285) |
| `rd_test_token` | commands | async | [commands.rs:293](app/src-tauri/src/commands.rs:293) |
| `rd_save_token` | commands | async | [commands.rs:313](app/src-tauri/src/commands.rs:313) |
| `rd_clear_token` | commands | async | [commands.rs:333](app/src-tauri/src/commands.rs:333) |
| `rd_check_user` | commands | async | [commands.rs:348](app/src-tauri/src/commands.rs:348) |
| `rd_send_magnet` | commands | async | [commands.rs:401](app/src-tauri/src/commands.rs:401) |
| `rd_check_pending` | commands | async | [commands.rs:516](app/src-tauri/src/commands.rs:516) |
| `pending_list` | commands | async | [commands.rs:579](app/src-tauri/src/commands.rs:579) |
| `pending_remove` | commands | async | [commands.rs:586](app/src-tauri/src/commands.rs:586) |
| `pending_clear` | commands | async | [commands.rs:594](app/src-tauri/src/commands.rs:594) |
| `get_legacy_default_dir` | commands | sync | [commands.rs:612](app/src-tauri/src/commands.rs:612) |
| `preview_legacy_import` | commands | sync | [commands.rs:617](app/src-tauri/src/commands.rs:617) |
| `apply_legacy_import` | commands | async | [commands.rs:626](app/src-tauri/src/commands.rs:626) |
| `get_cookies_status` | commands | sync | [commands.rs:861](app/src-tauri/src/commands.rs:861) |
| `create_cookies_template` | commands | sync | [commands.rs:894](app/src-tauri/src/commands.rs:894) |
| `open_data_dir` | commands | sync | [commands.rs:928](app/src-tauri/src/commands.rs:928) |
| `open_logs_dir` | commands | sync | [commands.rs:933](app/src-tauri/src/commands.rs:933) |
| `update_sidecar_settings` | commands | async | [commands.rs:905](app/src-tauri/src/commands.rs:905) |

### Shared `tauri::State`

Two values are `.manage()`d at setup time ([lib.rs:104](app/src-tauri/src/lib.rs:104), [lib.rs:119](app/src-tauri/src/lib.rs:119)):

| Type | Owner | Lifetime |
|---|---|---|
| `PathManager` | [path_manager.rs:17](app/src-tauri/src/path_manager.rs:17) | for the app's lifetime |
| `SidecarManager` | [sidecar_manager.rs:22](app/src-tauri/src/sidecar_manager.rs:22) | for the app's lifetime (one daemon child) |

Plus the `tauri-plugin-store` Store (file-backed, opened on demand via `app.store(...)`).

### Constants

- `STORE_FILE = "settings.json"` — [lib.rs:15](app/src-tauri/src/lib.rs:15) and a private duplicate at [settings.rs:12](app/src-tauri/src/settings.rs:12).
- `APP_FOLDER = "JavDBMagnet"` — [path_manager.rs:14](app/src-tauri/src/path_manager.rs:14).
- `PROTOCOL_VERSION = 1` — [sidecar_manager.rs:20](app/src-tauri/src/sidecar_manager.rs:20).
- `COOKIES_FILE_NAME = "cookies.txt"` — [commands.rs:818](app/src-tauri/src/commands.rs:818). Also redefined as `pub const LEGACY_COOKIES_FILE` in [legacy_import.rs:30](app/src-tauri/src/legacy_import.rs:30).
- `SERVICE = "JavDBMagnet"`, `ACCOUNT = "RD_API_TOKEN"` — [secret_store.rs:17-18](app/src-tauri/src/secret_store.rs:17).
- `FILE_NAME = "pending_torrents.json"` — [pending.rs:19](app/src-tauri/src/pending.rs:19). Also redefined as `LEGACY_PENDING_FILE` in [legacy_import.rs:31](app/src-tauri/src/legacy_import.rs:31).
- `LEGACY_ENV_FILE = ".env"` — [legacy_import.rs:29](app/src-tauri/src/legacy_import.rs:29).
- `COOKIES_TEMPLATE` — large UTF-8 (no BOM) instruction blob, [commands.rs:868](app/src-tauri/src/commands.rs:868).

---

## 2. Entry Points

### `main.rs` flow

`fn main()` at [main.rs:4-6](app/src-tauri/src/main.rs:4) just calls `javdbmagnet_lib::run()`. The `#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]` line at [main.rs:2](app/src-tauri/src/main.rs:2) hides the console window in release builds.

### `build.rs` flow

`fn main()` at [build.rs:1-3](app/src-tauri/build.rs:1) is the Cargo build-script entry. It calls `tauri_build::build()` so Tauri can generate build-time metadata/resources. It is executed by Cargo before compiling the app crate and is not part of the runtime call graph.

### `lib::run()` flow

[lib.rs:87-155](app/src-tauri/src/lib.rs:87). Steps:

1. `tauri::Builder::default()` —
2. `.plugin(tauri_plugin_store::Builder::new().build())` — Store plugin ([lib.rs:89](app/src-tauri/src/lib.rs:89)).
3. `.plugin(tauri_plugin_shell::init())` — Shell plugin (used for sidecar spawn + external open).
4. `.plugin(tauri_plugin_clipboard_manager::init())` — clipboard (Rust-only access; never exposed to frontend directly).
5. `.plugin(tauri_plugin_dialog::init())` — folder picker for legacy-import path input.
6. `.setup(|app| ...)` — synchronous bootstrap (see below).
7. `.invoke_handler(tauri::generate_handler![...])` — registers the 28-command surface.
8. `.run(tauri::generate_context!())` — main loop. Calls `.expect("error while running tauri application")` on failure.

### Setup hook ([lib.rs:93-122](app/src-tauri/src/lib.rs:93))

1. `PathManager::new(app.handle())` → resolves data + log paths from env vars (Windows) or `app_data_dir()` (other OS).
2. `path_manager.ensure_dirs()` → `create_dir_all` for both.
3. `load_handshake_inputs(&path_manager)` → returns `(cookies: String, rd_token: Option<String>, settings_value: Value)`. Reads cookies.txt, settings.json, then either reads token from keyring or migrates from legacy plaintext.
4. Build `paths: Value` JSON with `data_dir` + `log_dir`.
5. `app.manage(path_manager)` — install PathManager into state.
6. `tauri::async_runtime::block_on(SidecarManager::spawn_and_handshake(...))` — **synchronous-from-setup-thread** call that spawns the sidecar, performs `hello` + `handshake` over stdin/stdout. Failure here makes the window not open.
7. `app.manage(manager)` — install SidecarManager into state.

### Frontend-callable entry points

See the table in §1. Every `#[tauri::command]` function is one entry point.

---

## 3. Per-file Function Reference

---

## 3.1 `main.rs`

### `fn main()`  *(main.rs:4)*

**Purpose**: Process entry; delegates to library.

**Contract**:
- Params: none.
- Returns: `()` (Tauri owns the run loop).
- Side effects: spawns the entire app (window, plugins, sidecar). Panics if `tauri::Builder::run` returns `Err` (via `.expect(...)` inside `run()`).
- Errors: panics via `.expect` deep inside `run()`.
- Async: no (Tauri's runtime is set up internally).
- Authorization: none.

**Calls**:
- `javdbmagnet_lib::run()` → [lib.rs:87](app/src-tauri/src/lib.rs:87).

**Called by**: OS process loader (no Rust callers).

---

## 3.2 `build.rs`

### `fn main()`  *(build.rs:1)*

**Purpose**: Cargo build-script entry for Tauri build metadata/resource generation.

**Contract**:
- Params: none.
- Returns: `()`.
- Side effects: delegates to Tauri build tooling.
- Errors: build-script failures surface through Cargo/Tauri build output.
- Async: no.
- Authorization: none.

**Calls**:
- `tauri_build::build()`.

**Called by**: Cargo build-script execution before compiling `app/src-tauri`.

---

## 3.3 `lib.rs`

### `fn load_handshake_inputs(path_manager: &PathManager) -> (String, Option<String>, Value)`  *(lib.rs:27)*

**Purpose**: Read disk-side handshake inputs (cookies file, settings JSON, RD token) needed to start the sidecar.

**Contract**:
- Params: `path_manager` — borrowed; only `path_manager.data_dir` is used (immutable view).
- Returns: tuple `(cookies, rd_token, settings_value)`:
  - `cookies`: trimmed contents of `<data_dir>/cookies.txt`. Empty string if missing.
  - `rd_token`: `Some(token)` if found in OS credential store, else attempted legacy migration from `settings.rd.api_token`. `None` if neither source had a value.
  - `settings_value`: the `"settings"` object out of `<data_dir>/settings.json`. Defaults to empty JSON object on any read/parse failure.
- Side effects: file I/O on `cookies.txt` and `settings.json`. May invoke `migrate_legacy_token` which writes the keyring + rewrites the JSON wrapper.
- Errors: no error type; all errors are swallowed into defaults. `migrate_legacy_token` writes to stderr on keyring failure.
- Async: no.
- Authorization: requires `path_manager` ([lib.rs:93](app/src-tauri/src/lib.rs:93)) but no other invariants.

**Calls**:
- `std::fs::read_to_string(cookies_path)` and `(settings_path)`.
- `serde_json::from_str::<Value>` — settings parse.
- `secret_store::get_rd_token()` → [secret_store.rs:34](app/src-tauri/src/secret_store.rs:34).
- `migrate_legacy_token(...)` → [lib.rs:53](app/src-tauri/src/lib.rs:53).

**Called by**:
- `run()` setup closure ([lib.rs:97](app/src-tauri/src/lib.rs:97)).

---

### `fn migrate_legacy_token(path_manager: &PathManager, settings_value: &Value) -> Option<String>`  *(lib.rs:53)*

**Purpose**: One-shot M4→M5 migration. Pulls `settings.rd.api_token` (legacy plaintext) into the credential store, then scrubs the JSON file.

**Contract**:
- Params:
  - `path_manager` — borrowed; uses `data_dir` to locate `settings.json`.
  - `settings_value` — the `"settings"` JSON value as read from the store wrapper.
- Returns: `Some(token)` if a non-empty token was found (caller hands it to the sidecar so the first handshake still works). `None` if there was nothing to migrate.
- Side effects:
  - Writes the keyring (`secret_store::set_rd_token`).
  - Rewrites `<data_dir>/settings.json` with the `rd.api_token` field blanked. Best-effort: any read/parse/write failure leaves the file alone.
  - Prints to **stderr** (not the app log) on keyring write failure ([lib.rs:62](app/src-tauri/src/lib.rs:62)).
- Errors: only stderr; never returns an error variant. If keyring write fails, returns `Some(token)` anyway so the in-memory copy is still usable for this run.
- Async: no.
- Authorization: none beyond having `path_manager`.

**Calls**:
- `secret_store::set_rd_token(&token)` → [secret_store.rs:25](app/src-tauri/src/secret_store.rs:25).
- `std::fs::read_to_string` / `serde_json::from_str` / `serde_json::to_string_pretty` / `std::fs::write` on `settings.json`.
- `eprintln!` for the keyring failure path.

**Called by**:
- `load_handshake_inputs` ([lib.rs:43](app/src-tauri/src/lib.rs:43)).

---

### `pub fn run()`  *(lib.rs:87)*

**Purpose**: Build and run the Tauri application.

**Contract**:
- Params: none.
- Returns: never returns normally; `.expect(...)` panics on Tauri runtime error.
- Side effects: spawns the WebView, registers four plugins (store, shell, clipboard-manager, dialog), spawns the sidecar process via `block_on`, manages two pieces of state, registers 28 commands.
- Errors: the setup closure returns `Result<(), Box<dyn Error>>`. Errors there cause `Builder::run` to fail and the `.expect` to panic ([lib.rs:154](app/src-tauri/src/lib.rs:154)).
- Async: no (uses `block_on` to drive sidecar handshake during synchronous setup).
- Authorization: this IS the bootstrap.

**Calls**:
- `tauri::Builder::default()` + `.plugin(...)` x4.
- `PathManager::new(app.handle())` → [path_manager.rs:24](app/src-tauri/src/path_manager.rs:24) (or [path_manager.rs:38](app/src-tauri/src/path_manager.rs:38) on non-Windows).
- `path_manager.ensure_dirs()` → [path_manager.rs:45](app/src-tauri/src/path_manager.rs:45).
- `load_handshake_inputs(&path_manager)` → [lib.rs:27](app/src-tauri/src/lib.rs:27).
- `app.manage(path_manager)` / `app.manage(manager)`.
- `tauri::async_runtime::block_on(SidecarManager::spawn_and_handshake(...))` → [sidecar_manager.rs:35](app/src-tauri/src/sidecar_manager.rs:35).
- `tauri::generate_handler![...]` — macro registers the command vec.
- `tauri::generate_context!()` — macro for build-time embedding.

**Called by**:
- `main()` ([main.rs:5](app/src-tauri/src/main.rs:5)).
- Mobile entry point (`tauri::mobile_entry_point`) for mobile builds ([lib.rs:86](app/src-tauri/src/lib.rs:86)).

---

## 3.4 `commands.rs`

### `pub async fn sidecar_ping(sidecar: State<'_, SidecarManager>) -> Result<Value, String>`  *(commands.rs:29)*

**Purpose**: Health-check the sidecar.

**Contract**:
- Params: `sidecar` — managed state handle to the daemon.
- Returns: raw JSON `Value` from the sidecar's `ping` reply. The frontend treats truthy `ok` as healthy.
- Side effects: one JSON-line over the sidecar stdin/stdout; serialized through the sidecar mutex.
- Errors: any sidecar transport error bubbles up as `Err(String)`.
- Async: yes; blocks on the sidecar's mutex.
- Authorization: requires sidecar managed state (i.e. setup completed).

**Calls**:
- `sidecar.request("ping", Value::Null)` → [sidecar_manager.rs:116](app/src-tauri/src/sidecar_manager.rs:116).

**Called by**: frontend (Tauri invoke).

---

### `pub async fn fetch_javdb(sidecar, url, batch_id) -> Result<Value, String>`

**Purpose**: Trigger the sidecar's JavDB page scrape for a given URL; return the `result` payload (already redacted by the sidecar).

**Contract**:
- Params:
  - `sidecar` — managed state.
  - `url` — JavDB page URL. No client-side validation; sidecar enforces the JavDB origin policy.
  - `batch_id` — required frontend scrape-batch id, forwarded as `batch_id`. All URLs/retries
    in one visible batch share it; a later batch uses a fresh id. The sidecar rejects an empty
    id or one longer than 128 characters.
- Returns: the `result` JSON value from the response. `Value::Null` if missing.
- Side effects: sidecar RPC + whatever HTTP/cookie work the sidecar performs (out of scope here).
- Errors: returns `Err(String)` containing either the sidecar's `error.message` ([commands.rs:42](app/src-tauri/src/commands.rs:42)) or a transport error.
- Async: yes; serialized through sidecar mutex.
- Authorization: requires the sidecar to have been handshake'd (it was, by `run()`).

**Calls**:
- `sidecar.request("fetch_javdb", json!({"url": url, "batch_id": batch_id}))`.

**Called by**: frontend.

---

### `pub async fn copy_magnet(app: AppHandle, sidecar: State<'_, SidecarManager>, handle_id: String) -> Result<(), String>`  *(commands.rs:53)*

**Purpose**: Resolve a previously-redacted handle into its full magnet URI and write it to the OS clipboard. Magnet text never crosses back into the frontend.

**Contract**:
- Params:
  - `app` — AppHandle for clipboard access.
  - `sidecar` — managed state.
  - `handle_id` — the per-row id returned earlier by `fetch_javdb` or `register_magnets`.
- Returns: `Ok(())` after the clipboard write completes; magnet text is dropped immediately ([commands.rs:77](app/src-tauri/src/commands.rs:77)).
- Side effects: sidecar RPC; one OS clipboard write.
- Errors:
  - `Err(error.code)` from the sidecar (e.g. `unknown_handle`).
  - `Err("response missing magnet field")` if response shape is malformed.
  - `Err(<clipboard error>)` if `ClipboardExt::write_text` fails.
- Async: yes.
- Authorization: requires sidecar.

**Calls**:
- `sidecar.request("resolve_magnet", ...)` → [sidecar_manager.rs:116](app/src-tauri/src/sidecar_manager.rs:116).
- `app.clipboard().write_text(magnet)` → tauri-plugin-clipboard-manager.

**Called by**: frontend.

---

### `pub struct CopyBulkResult { copied: usize, unknown: usize }`  *(commands.rs:82)*

DTO. Serialized to frontend.

---

### `pub struct RegisteredMagnet { handle_id, magnet_redacted, name, deduped }`  *(commands.rs:88)*

DTO. `name` is the magnet's `dn=` parameter (empty when missing). `deduped` flags inputs the sidecar collapsed onto an existing handle.

---

### `pub struct RegisterMagnetsResult { registered: Vec<RegisteredMagnet>, invalid: Vec<String> }`  *(commands.rs:103)*

DTO.

---

### `pub async fn register_magnets(sidecar: State<'_, SidecarManager>, magnets: Vec<String>) -> Result<RegisterMagnetsResult, String>`  *(commands.rs:117)*

**Purpose**: Register raw user-pasted magnet URIs into the sidecar's handle table so the paste-magnet → RD path can use the same `handle_id` workflow as scrape results.

**Contract**:
- Params:
  - `sidecar` — managed state.
  - `magnets` — raw input strings. Anything not starting with `magnet:` is filtered into the `invalid` field by the sidecar.
- Returns: registered handles (redacted) + invalid raw strings.
- Side effects: sidecar handle-table mutation. **Full magnet text crosses IPC inbound only** (the comment at [commands.rs:115](app/src-tauri/src/commands.rs:115) is explicit).
- Errors:
  - `Err(code)` from sidecar via `_err_code` ([commands.rs:259](app/src-tauri/src/commands.rs:259)).
  - `Err(<serde error>)` if response can't deserialize into `RegisteredMagnet` / `String` vectors.
- Async: yes.
- Authorization: requires sidecar.

**Calls**:
- `sidecar.request("register_magnets", ...)` → [sidecar_manager.rs:116](app/src-tauri/src/sidecar_manager.rs:116).
- `_err_code(&resp)` → [commands.rs:259](app/src-tauri/src/commands.rs:259).
- `serde_json::from_value` twice (`Vec<RegisteredMagnet>`, `Vec<String>`).

**Called by**: frontend (paste-magnet flow).

---

### `pub async fn forget_magnets(sidecar: State<'_, SidecarManager>, handle_ids: Option<Vec<String>>) -> Result<u64, String>`  *(commands.rs:147)*

**Purpose**: Drop sidecar handle-table entries. `None` = forget all.

**Contract**:
- Params: `handle_ids` — list of ids or `None` for "all".
- Returns: number of handles dropped. Compatible with two field names: `forgot` or `forgotten` ([commands.rs:157-158](app/src-tauri/src/commands.rs:157)).
- Errors: transport errors propagate; calls `ensure_ok` so sidecar error envelopes propagate as `Err`.
- Async: yes.
- Authorization: requires sidecar.

**Calls**: `sidecar.request("forget_magnets", payload)` → [sidecar_manager.rs:116](app/src-tauri/src/sidecar_manager.rs:116).

**Called by**: frontend (clearing the result tree).

---

### `pub async fn copy_magnets_bulk(app: AppHandle, sidecar: State<'_, SidecarManager>, handle_ids: Vec<String>) -> Result<CopyBulkResult, String>`  *(commands.rs:164)*

**Purpose**: Batch version of `copy_magnet` — newline-joined magnets to the OS clipboard, count of unknown ids.

**Contract**:
- Params: list of handle ids.
- Returns: `{copied, unknown}` counts. Empty input → empty clipboard write skipped ([commands.rs:194](app/src-tauri/src/commands.rs:194)).
- Side effects: sidecar RPC + one clipboard write (skipped on empty).
- Errors: `Err("resolve_magnets failed")` for non-ok response, or transport / clipboard errors.
- Async: yes.

**Calls**:
- `sidecar.request("resolve_magnets", ...)`.
- `app.clipboard().write_text(joined)`.

**Called by**: frontend.

---

### `pub struct CopyRdLinksBulkResult { copied: usize }`  *(commands.rs:208)*

DTO.

---

### `pub async fn copy_rd_links_bulk(app: AppHandle, links: Vec<String>) -> Result<CopyRdLinksBulkResult, String>`  *(commands.rs:223)*

**Purpose**: Write a batch of RD direct-download links to the OS clipboard. Mirrors `copy_magnets_bulk` so frontend doesn't import the clipboard plugin directly.

**Contract**:
- Params: list of strings; whitespace-only entries are trimmed and silently dropped.
- Returns: post-filter `copied` count. `copied = 0` for empty/all-whitespace input — no error.
- Side effects: at most one clipboard write. Links are not logged.
- Errors: clipboard write error → `Err(String)`.
- Async: yes — but does NOT require sidecar state.

**Calls**: `app.clipboard().write_text(joined)`.

**Called by**: frontend.

---

### `fn _err_code(resp: &Value) -> String`  *(commands.rs:259)*

**Purpose**: Extract `resp.error.code` from a sidecar response, defaulting to `"unknown"`. Helper used throughout the RD commands.

**Contract**:
- Params: borrowed JSON value (typically a non-`ok` sidecar response).
- Returns: owned `String` of the error code.
- Side effects: none.
- Errors: never errors; always returns a string.
- Async: no.

**Calls**: only `Value::get` / `as_str` chains.

**Called by**:
- `register_magnets` ([commands.rs:125](app/src-tauri/src/commands.rs:125))
- `rd_test_token` ([commands.rs:304](app/src-tauri/src/commands.rs:304))
- `rd_save_token` ([commands.rs:325](app/src-tauri/src/commands.rs:325))
- `rd_clear_token` ([commands.rs:339](app/src-tauri/src/commands.rs:339))
- `rd_check_user` ([commands.rs:351](app/src-tauri/src/commands.rs:351))
- `rd_send_magnet` ([commands.rs:428](app/src-tauri/src/commands.rs:428))
- `rd_check_pending` ([commands.rs:528](app/src-tauri/src/commands.rs:528))
- `apply_legacy_import` ([commands.rs:693](app/src-tauri/src/commands.rs:693))
- `update_sidecar_settings` ([commands.rs:919](app/src-tauri/src/commands.rs:919))

---

### `pub struct RdUserInfo { username, type, expiration, points }`  *(commands.rs:267)*

DTO. `#[serde(rename = "type")]` because `type` is a reserved keyword.

### `pub struct RdHasTokenResult { present: bool }`  *(commands.rs:279)*

DTO.

---

### `pub async fn rd_has_token() -> Result<RdHasTokenResult, String>`  *(commands.rs:285)*

**Purpose**: Tell the frontend whether a token is saved (without revealing it).

**Contract**:
- Params: none. Notably does **not** take `State<SidecarManager>` — purely a keyring read.
- Returns: `{present: bool}`.
- Side effects: one keyring read.
- Errors: `Err(<keyring error string>)` if the credential store can't be queried.
- Async: yes (signature requires it for Tauri; body is sync).

**Calls**: `secret_store::get_rd_token()` → [secret_store.rs:34](app/src-tauri/src/secret_store.rs:34).

**Called by**: frontend.

---

### `pub async fn rd_test_token(sidecar: State<'_, SidecarManager>, token: String) -> Result<RdUserInfo, String>`  *(commands.rs:293)*

**Purpose**: Validate a candidate token by calling RD `/user` via the sidecar, without persisting.

**Contract**:
- Params:
  - `token` — candidate. Empty short-circuits to `Err("rd_no_token")`.
- Returns: account info from RD.
- Side effects: sidecar RPC; sidecar performs HTTP to real-debrid.com. Token does NOT touch the keyring.
- Errors:
  - `Err("rd_no_token")` for empty input.
  - `Err(<code>)` from `_err_code` for non-ok response.
  - `Err(<serde error>)` if user shape can't deserialize.
- Async: yes.
- Authorization: requires sidecar.

**Calls**:
- `sidecar.request("rd_user", json!({"token": token}))`.
- `_err_code`, `serde_json::from_value`.

**Called by**: frontend (settings dialog).

---

### `pub async fn rd_save_token(sidecar: State<'_, SidecarManager>, token: String) -> Result<(), String>`  *(commands.rs:313)*

**Purpose**: Persist a token to the credential store AND push it to the running sidecar.

**Contract**:
- Params: `token` — empty string is treated by `secret_store::set_rd_token` as "delete" ([secret_store.rs:27-29](app/src-tauri/src/secret_store.rs:27)); the sidecar push uses `Value::Null` in that case.
- Returns: `Ok(())`. Local `token` string drops at end of fn.
- Side effects:
  - Keyring write (or delete if empty).
  - Sidecar `rd_set_token` RPC.
- Errors:
  - `Err(<keyring error>)` from `set_rd_token`.
  - `Err(<code>)` if sidecar returns non-ok.
- Async: yes.
- Authorization: requires sidecar.

**Calls**:
- `secret_store::set_rd_token(&token)` → [secret_store.rs:25](app/src-tauri/src/secret_store.rs:25).
- `sidecar.request("rd_set_token", payload)`.
- `_err_code`.

**Called by**: frontend (settings save).

---

### `pub async fn rd_clear_token(sidecar: State<'_, SidecarManager>) -> Result<(), String>`  *(commands.rs:333)*

**Purpose**: Delete token from credential store and tell the sidecar to forget it.

**Contract**:
- Params: only sidecar state.
- Returns: `Ok(())`.
- Side effects: keyring delete; sidecar `rd_set_token: null` RPC.
- Errors: from either step.
- Async: yes.
- Authorization: requires sidecar.

**Calls**:
- `secret_store::delete_rd_token()` → [secret_store.rs:43](app/src-tauri/src/secret_store.rs:43).
- `sidecar.request("rd_set_token", json!({"token": null}))`.
- `_err_code`.

**Called by**: frontend.

---

### `pub async fn rd_check_user(sidecar: State<'_, SidecarManager>) -> Result<RdUserInfo, String>`  *(commands.rs:348)*

**Purpose**: Refresh account info using the **sidecar's current** token (no token argument). Separate from `rd_test_token` so the secret never crosses IPC just to refresh.

**Contract**:
- Params: only sidecar state.
- Returns: `RdUserInfo`.
- Side effects: sidecar RPC; sidecar HTTP to RD.
- Errors: `Err(<code>)` from `_err_code` or `Err(<serde error>)`.
- Async: yes.
- Authorization: requires sidecar AND the sidecar must have a token (otherwise it returns a code like `rd_no_token`).

**Calls**:
- `sidecar.request("rd_user", Value::Null)`.
- `_err_code`, `serde_json::from_value`.

**Called by**: frontend.

---

### `pub struct RdSendOptions { strategy, min_size_mb, cache_wait, code, size_label }`  *(commands.rs:358)*

DTO. `code` and `size_label` are display-only — passed through so a `Pending` outcome can be persisted with the same labels the UI is showing.

### `pub struct RdLink { original, download, filename, filesize, streamable }`  *(commands.rs:369)*

DTO mirroring RD's unrestrict link response.

### `pub enum RdSendOutcome { Completed{...}, Pending{...} }`  *(commands.rs:381)*

`#[serde(tag = "status", rename_all = "snake_case")]` — frontend gets a discriminated union with `status: "completed" | "pending"`.

---

### `pub async fn rd_send_magnet(sidecar, path_manager, handle_id, options) -> Result<RdSendOutcome, String>`  *(commands.rs:401)*

**Purpose**: Send a magnet (by handle_id) to RD. Returns either the unrestricted links (cache hit) or a Pending entry that's also persisted to disk.

**Contract**:
- Params:
  - `sidecar`, `path_manager` — managed state.
  - `handle_id` — sidecar handle.
  - `options` — optional `RdSendOptions`. Defaults to all-None.
- Returns:
  - `Completed { torrent_id, name, links }` — RD returned unrestricted links immediately.
  - `Pending { torrent_id, name, rd_status, progress }` — RD is still working; entry was persisted via `pending::add`.
- Side effects:
  - Sidecar RPC (`rd_send_magnet`), which internally calls RD's API.
  - On Pending path: writes `<data_dir>/pending_torrents.json` atomically via `pending::add`.
- Errors: `Err(<code>)` from `_err_code` or `Err(<serde error>)` for links deserialization, or `Err(<pending::add error>)` from disk write.
- Async: yes.
- Authorization: requires sidecar.

**Calls**:
- `sidecar.request("rd_send_magnet", payload)`.
- `_err_code`.
- `serde_json::from_value::<Vec<RdLink>>` (for `Completed`).
- `PendingEntry::new(...)` → [pending.rs:60](app/src-tauri/src/pending.rs:60).
- `pending::add(&path_manager.data_dir, entry)` → [pending.rs:119](app/src-tauri/src/pending.rs:119).

**Called by**: frontend (the "send" action).

---

### `pub enum RdCheckOutcome { Completed, Pending, Missing }`  *(commands.rs:494)*

Three-variant tag union for the retry-poll command.

---

### `pub async fn rd_check_pending(sidecar, path_manager, torrent_id, strategy) -> Result<RdCheckOutcome, String>`  *(commands.rs:516)*

**Purpose**: Re-poll a previously-pending torrent. **Always mutates** pending_torrents.json based on outcome:
- `completed` → entry removed.
- `missing` → entry removed.
- `pending` → entry's `last_progress` / `last_rd_status` / `last_checked_at` refreshed.

**Contract**:
- Params:
  - `torrent_id`, optional `strategy` override.
- Returns: one of the three variants.
- Side effects: sidecar RPC + at least one disk read; one disk write if state changes.
- Errors: `Err(<code>)` from `_err_code`, or disk / serde errors from pending I/O.
- Async: yes.
- Authorization: requires sidecar.

**Calls**:
- `sidecar.request("rd_check_pending", payload)`.
- `_err_code`.
- `pending::remove(&path_manager.data_dir, &torrent_id)` → [pending.rs:129](app/src-tauri/src/pending.rs:129).
- `pending::update_status(&data_dir, &torrent_id, &rd_status, progress)` → [pending.rs:138](app/src-tauri/src/pending.rs:138).
- `serde_json::from_value::<Vec<RdLink>>`.

**Called by**: frontend (the "retry" loop and manual poll button).

---

### `pub async fn pending_list(path_manager: State<'_, PathManager>) -> Result<Vec<PendingEntry>, String>`  *(commands.rs:579)*

**Purpose**: Return the full pending list.

**Contract**: Pure pass-through to `pending::load`.
- Side effects: one disk read.
- Errors: from `pending::load`.
- Async: yes (Tauri sig requirement).
- Authorization: requires path_manager only.

**Calls**: `pending::load(&path_manager.data_dir)` → [pending.rs:86](app/src-tauri/src/pending.rs:86).

**Called by**: frontend (initial render + after retries).

---

### `pub async fn pending_remove(path_manager, torrent_id) -> Result<Vec<PendingEntry>, String>`  *(commands.rs:586)*

**Purpose**: Drop one entry; return the new list.

**Calls**: `pending::remove(&path_manager.data_dir, &torrent_id)` → [pending.rs:129](app/src-tauri/src/pending.rs:129).

**Called by**: frontend (manual delete).

---

### `pub async fn pending_clear(path_manager: State<'_, PathManager>) -> Result<(), String>`  *(commands.rs:594)*

**Purpose**: Wipe pending_torrents.json (writes an empty array).

**Calls**: `pending::clear(&path_manager.data_dir)` → [pending.rs:162](app/src-tauri/src/pending.rs:162).

**Called by**: frontend.

---

### `pub fn get_legacy_default_dir() -> String`  *(commands.rs:612)*

**Purpose**: Return `JAVDB_LEGACY_IMPORT_DIR` env var (or empty string) — pure pre-fill helper.

**Contract**:
- Params: none.
- Returns: env var value or `""`.
- Side effects: env var read only; **no file I/O** (explicit in the doc comment).
- Errors: never errors.
- Async: no.
- Authorization: none.

**Calls**: `std::env::var(...)`.

**Called by**: frontend.

---

### `pub fn preview_legacy_import(source_dir: String) -> Result<LegacyImportPreview, String>`  *(commands.rs:617)*

**Purpose**: Inspect a candidate legacy directory and report what's importable. Pure preview — no mutation.

**Contract**:
- Params: `source_dir` — user-typed path; trimmed.
- Returns: `LegacyImportPreview` with presence flags, key names, and warnings. NEVER echoes secret values.
- Side effects: file reads only.
- Errors: `Err("source_dir is empty")` for blank input.
- Async: no.
- Authorization: none.

**Calls**: `legacy_import::preview(Path::new(trimmed))` → [legacy_import.rs:297](app/src-tauri/src/legacy_import.rs:297).

**Called by**: frontend (preview button).

---

### `pub async fn apply_legacy_import(app, path_manager, sidecar, source_dir) -> Result<LegacyImportReport, String>`  *(commands.rs:626)*

**Purpose**: The actual M7a-lite import. Side-effect orchestrator over `.env`, `cookies.txt`, and `pending_torrents.json` from `source_dir`.

**Contract**:
- Params:
  - `source_dir` — user-provided path. Refuses empty / non-directory / same as `data_dir`.
- Returns: `LegacyImportReport` (counts + warnings + source-file list). Each step is best-effort — a failure in one section adds a warning but doesn't abort the others.
- Side effects:
  - For `.env`:
    - RD token → `secret_store::set_rd_token` + sidecar `rd_set_token`.
    - Non-secret settings → merge into the tauri-plugin-store `settings.json`. Forces `rd.api_token` to "" with a belt-and-suspenders pass ([commands.rs:714-720](app/src-tauri/src/commands.rs:714)).
  - For `cookies.txt`: file copy into `<data_dir>/cookies.txt`. Always adds a warning instructing the user to restart for the new cookies to take effect, because the running sidecar already loaded its cookies at handshake time.
  - For `pending_torrents.json`: read source, sanitize via `legacy_import::merge_legacy_pending`, write merged list via `pending::save`.
- Errors:
  - `Err("source_dir is empty")`, `Err(<format!>)` for non-directory or same-as-data-dir.
  - Otherwise: returns `Ok(report)` even on partial failures; failures are appended to `report.warnings`.
- Async: yes (does sidecar RPC for the token push).
- Authorization: requires `path_manager` and `sidecar`.

**Calls**:
- `legacy_import::preview(src)` → [legacy_import.rs:297](app/src-tauri/src/legacy_import.rs:297).
- `std::fs::read_to_string(src.join(LEGACY_ENV_FILE))`.
- `legacy_import::parse_env(&s)` → [legacy_import.rs:92](app/src-tauri/src/legacy_import.rs:92).
- `secret_store::set_rd_token(token)`.
- `sidecar.request("rd_set_token", ...)` → [sidecar_manager.rs:116](app/src-tauri/src/sidecar_manager.rs:116).
- `app.store(&store_path)` → tauri-plugin-store.
- `serde_json::to_value(crate::settings::Settings::default())`.
- `legacy_import::apply_settings_patch(&mut base, &parsed.settings_patch)` → [legacy_import.rs:364](app/src-tauri/src/legacy_import.rs:364).
- `store.set("settings", base)` + `store.save()`.
- `std::fs::create_dir_all(&path_manager.data_dir)`, `std::fs::copy(...)` for cookies.
- `pending::load(&path_manager.data_dir)` → [pending.rs:86](app/src-tauri/src/pending.rs:86).
- `legacy_import::merge_legacy_pending(&raw, &existing)` → [legacy_import.rs:261](app/src-tauri/src/legacy_import.rs:261).
- `pending::save(&path_manager.data_dir, &merged)` → [pending.rs:100](app/src-tauri/src/pending.rs:100).
- `_err_code(&resp)`.

**Called by**: frontend (apply button).

---

### `pub struct CookiesStatus { present, path, modified_iso, size_bytes }`  *(commands.rs:820)*

DTO. `modified_iso` is ISO-8601 UTC or `None`.

---

### `pub(crate) fn cookies_status_for(data_dir: &Path) -> CookiesStatus`  *(commands.rs:833)*

**Purpose**: Pure helper — report cookies.txt presence/size/mtime without reading the file body. Defended in test [commands.rs:1010](app/src-tauri/src/commands.rs:1010).

**Contract**:
- Params: borrowed path to the data dir.
- Returns: `CookiesStatus`. Path is always echoed (even when file missing) so the UI can show "expected at <path>".
- Side effects: one `metadata()` call.
- Errors: never errors; missing file maps to `present: false`.
- Async: no.

**Calls**: `std::fs::metadata`, `meta.modified()`, `chrono::DateTime::<Utc>::from(st).to_rfc3339()`.

**Called by**:
- `get_cookies_status` ([commands.rs:862](app/src-tauri/src/commands.rs:862)).
- Tests at [commands.rs:984](app/src-tauri/src/commands.rs:984), [commands.rs:996](app/src-tauri/src/commands.rs:996), [commands.rs:1015](app/src-tauri/src/commands.rs:1015).

---

### `pub fn get_cookies_status(path_manager: State<PathManager>) -> CookiesStatus`  *(commands.rs:861)*

**Purpose**: Tauri-command wrapper around `cookies_status_for`.

**Calls**: `cookies_status_for(&path_manager.data_dir)`.

**Called by**: frontend.

---

### `pub(crate) fn write_cookies_template_to(data_dir: &Path) -> Result<(), String>`  *(commands.rs:878)*

**Purpose**: Write the inline-instructed cookies.txt scaffold (UTF-8 without BOM). Refuses to overwrite — losing a working file is worse than failing.

**Contract**:
- Params: data dir.
- Returns: `Ok(())` after write.
- Side effects: `create_dir_all(data_dir)` + `fs::write` of `COOKIES_TEMPLATE` bytes to `<data_dir>/cookies.txt`.
- Errors:
  - `Err("cookies.txt 已存在，建立範本前請先在資料目錄手動移除")` if file exists.
  - `Err("mkdir ...")` or `Err("write ...")` for IO failures.
- Async: no.

**Calls**: `std::fs::create_dir_all`, `std::fs::write`.

**Called by**:
- `create_cookies_template` ([commands.rs:895](app/src-tauri/src/commands.rs:895)).
- Tests at [commands.rs:1029](app/src-tauri/src/commands.rs:1029), [commands.rs:1056](app/src-tauri/src/commands.rs:1056).

---

### `pub fn create_cookies_template(path_manager: State<PathManager>) -> Result<(), String>`  *(commands.rs:894)*

**Purpose**: Tauri-command wrapper around `write_cookies_template_to`.

**Calls**: `write_cookies_template_to(&path_manager.data_dir)`.

**Called by**: frontend ("create template" button).

---

### `pub async fn update_sidecar_settings(sidecar: State<'_, SidecarManager>, settings: Value) -> Result<(), String>`  *(commands.rs:905)*

**Purpose**: Push the latest persisted settings to the running sidecar so changes take effect without a restart. Belt-and-suspenders blanks `rd.api_token` before sending.

**Contract**:
- Params: `settings` — raw JSON object (the frontend's current settings).
- Returns: `Ok(())`.
- Side effects: mutates a clone of `settings` (`rd.api_token = ""`); sidecar RPC `update_settings`.
- Errors: `Err(<code>)` via `_err_code` if non-ok.
- Async: yes.
- Authorization: requires sidecar.

**Calls**: `sidecar.request("update_settings", ...)`, `_err_code`.

**Called by**: frontend (settings save flow).

---

### `pub fn open_data_dir(path_manager: State<PathManager>) -> Result<(), String>`  *(commands.rs:928)*

**Purpose**: Open the data directory in the OS file manager (Windows: explorer.exe).

**Calls**: `open_in_explorer(&path_manager.data_dir)`.

**Called by**: frontend.

---

### `pub fn open_logs_dir(path_manager: State<PathManager>) -> Result<(), String>`  *(commands.rs:933)*

**Purpose**: Same as `open_data_dir` but for the log dir.

**Calls**: `open_in_explorer(&path_manager.log_dir)`.

**Called by**: frontend.

---

### `fn open_in_explorer(p: &Path) -> Result<(), String>`  *(commands.rs:937)*

**Purpose**: Windows-only `explorer.exe <p>` spawn. Best-effort `create_dir_all` before opening so explorer has something to show.

**Contract**:
- Params: borrowed path.
- Returns: `Ok(())` after spawning the process.
- Side effects: may create the directory; spawns `explorer.exe` (Windows) or returns an "OS not supported" error.
- Errors:
  - `Err("mkdir ...")` on dir-create failure.
  - `Err("spawn explorer: ...")` on spawn failure.
  - `Err("open_in_explorer not implemented for this OS: ...")` on non-Windows.
- Async: no.

**Calls**: `std::fs::create_dir_all`, `std::process::Command::new("explorer.exe").arg(...).spawn()`.

**Called by**: `open_data_dir`, `open_logs_dir`.

---

### Tests (`tests_m7b` module) — [commands.rs:963-1065](app/src-tauri/src/commands.rs:963)

- `fn temp_dir() -> PathBuf` — process-id + counter-based tempdir. Same pattern is duplicated in [legacy_import.rs:410](app/src-tauri/src/legacy_import.rs:410) and [pending.rs:174](app/src-tauri/src/pending.rs:174).
- `fn cookies_status_missing_file()` — verifies missing-file status shape.
- `fn cookies_status_present_file()` — verifies present-file metadata.
- `fn cookies_status_does_not_leak_body()` — defense-in-depth: serialized status never contains cookie body.
- `fn create_cookies_template_writes_utf8_no_bom()` — checks BOM-free output and required Chinese instruction headers.
- `fn create_cookies_template_refuses_overwrite()` — original file preserved.

---

## 3.5 `legacy_import.rs`

### `pub struct LegacyImportPreview { source_dir, source_dir_valid, env_present, cookies_present, pending_present, env_settings_keys, has_rd_token, pending_count, warnings }`  *(legacy_import.rs:36)*

DTO. Reports presence + recognized key names only — never values.

### `pub struct LegacyImportReport { env_imported, rd_token_imported, cookies_imported, pending_imported, pending_skipped, sources, warnings }`  *(legacy_import.rs:55)*

DTO. Pure tallies + diagnostic strings.

### `pub struct ParsedEnv { token, recognized_keys, settings_patch, warnings }`  *(legacy_import.rs:69)*

DTO. `token` and `settings_patch` are structurally separate — by construction `parse_env` cannot place `RD_API_TOKEN` into `settings_patch`.

---

### `pub fn parse_env(content: &str) -> ParsedEnv`  *(legacy_import.rs:92)*

**Purpose**: Parse `.env` file text. Pure function — no I/O.

**Contract**:
- Params: borrowed string content. Lines that are blank or start with `#` are skipped.
- Returns: `ParsedEnv` with:
  - `token` — RD_API_TOKEN value (or None if empty/missing).
  - `recognized_keys` — names of keys that were successfully consumed.
  - `settings_patch` — JSON map keyed by top-level setting section (`rd`, `ui`).
  - `warnings` — strings for malformed lines, unknown keys, non-numeric numerics.
- Side effects: none.
- Errors: never returns Err; bad lines/keys go to `warnings`.
- Async: no.

**Recognized keys**:
- `RD_API_TOKEN` → `token` (never patch).
- `RD_FILE_PICK` → `settings_patch.rd.file_pick`.
- `RD_MIN_SIZE_MB` → `settings_patch.rd.min_size_mb` (u32; warning on parse fail).
- `RD_WAIT_TIMEOUT` → warning only; no settings patch because `cache_wait_seconds` is the only RD wait budget.
- `RD_CACHE_WAIT` → `settings_patch.rd.cache_wait_seconds` (u32).
- `UI_SCALE` → `settings_patch.ui.scale`.
- `UI_THEME` → `settings_patch.ui.theme`.

Quote stripping: matched `"..."` or `'...'` pairs.

**Calls**: only stdlib `str::lines`, `str::split_once`, `str::parse::<u32>`, `serde_json::Map::insert`.

**Called by**:
- `preview` ([legacy_import.rs:320](app/src-tauri/src/legacy_import.rs:320)).
- `apply_legacy_import` ([commands.rs:664](app/src-tauri/src/commands.rs:664)).
- Tests at [legacy_import.rs:424](app/src-tauri/src/legacy_import.rs:424), [legacy_import.rs:450](app/src-tauri/src/legacy_import.rs:450), [legacy_import.rs:464](app/src-tauri/src/legacy_import.rs:464), [legacy_import.rs:473](app/src-tauri/src/legacy_import.rs:473), [legacy_import.rs:485](app/src-tauri/src/legacy_import.rs:485).

---

### `pub fn sanitize_pending_entry(raw: &Value) -> Option<PendingEntry>`  *(legacy_import.rs:195)*

**Purpose**: Convert one raw legacy pending object into a sanitized `PendingEntry`. Strips magnet/secret-bearing fields **by construction** — only allow-listed fields survive.

**Contract**:
- Params: borrowed JSON value (one element of the legacy array).
- Returns: `Some(entry)` if `torrent_id` is present and non-empty after trim. `None` otherwise.
- Allow-list (and aliases):
  - `torrent_id` (required).
  - `code`, `name`.
  - `size_label` ← falls back to `size`.
  - `strategy` ← defaults to `"smart"` if empty.
  - `added_at` ← defaults to `Utc::now().to_rfc3339()` if empty.
  - `last_progress` ← falls back to `progress`.
  - `last_rd_status` ← falls back to `rd_status`.
  - `last_checked_at` (Option<String>).
- Deliberately ignored (commented at [legacy_import.rs:243](app/src-tauri/src/legacy_import.rs:243)): `magnet`, `magnet_uri`, `full_magnet`, `magnet_url`, `magnet_text`, `files_selected`, `api_token`.
- Side effects: may call `chrono::Utc::now()` if `added_at` is empty.
- Errors: returns `None` instead of erroring.
- Async: no.

**Calls**: `Value::as_object`, `as_str`, `as_f64`; `chrono::Utc::now().to_rfc3339()`.

**Called by**:
- `merge_legacy_pending` ([legacy_import.rs:275](app/src-tauri/src/legacy_import.rs:275)).
- Tests at [legacy_import.rs:509](app/src-tauri/src/legacy_import.rs:509), [legacy_import.rs:523](app/src-tauri/src/legacy_import.rs:523).

---

### `pub fn merge_legacy_pending(legacy_raw: &str, existing: &[PendingEntry]) -> Result<(Vec<PendingEntry>, usize, usize), String>`  *(legacy_import.rs:261)*

**Purpose**: Merge legacy pending entries with the current list. Dedupes by `torrent_id` — existing entries win (legacy is never allowed to clobber state).

**Contract**:
- Params:
  - `legacy_raw` — JSON array as a string.
  - `existing` — current pending list.
- Returns: `(merged_list, imported_count, skipped_count)`.
  - `imported` = new entries added.
  - `skipped` = entries that either had no `torrent_id` (corrupt) or duplicated an existing id.
- Side effects: none.
- Errors: `Err("parse pending JSON: ...")` for invalid JSON.
- Async: no.

**Calls**:
- `serde_json::from_str::<Vec<Value>>`.
- `sanitize_pending_entry(raw)` per element.
- `HashSet<String>` for dedup.

**Called by**:
- `apply_legacy_import` ([commands.rs:784](app/src-tauri/src/commands.rs:784)).
- Tests at [legacy_import.rs:536](app/src-tauri/src/legacy_import.rs:536), [legacy_import.rs:561](app/src-tauri/src/legacy_import.rs:561), [legacy_import.rs:571](app/src-tauri/src/legacy_import.rs:571).

---

### `pub fn preview(source_dir: &Path) -> LegacyImportPreview`  *(legacy_import.rs:297)*

**Purpose**: Inspect `source_dir` and count importable items. Reads files just enough to count entries / collect key names. **Never echoes any value** that came from `.env` / cookies.txt / a magnet.

**Contract**:
- Params: borrowed path.
- Returns: `LegacyImportPreview`. `source_dir_valid: false` if not a directory.
- Side effects: file reads (`.env`, `pending_torrents.json` if present). cookies.txt presence is checked via `is_file()` only — never read.
- Errors: never errors; everything goes to `warnings`.
- Async: no.

**Calls**:
- `Path::is_dir`, `Path::is_file`, `Path::join`.
- `fs::read_to_string` for `.env` and `pending_torrents.json`.
- `parse_env(&s)`.
- `serde_json::from_str::<Vec<Value>>` for pending count.

**Called by**:
- `preview_legacy_import` ([commands.rs:622](app/src-tauri/src/commands.rs:622)).
- `apply_legacy_import` ([commands.rs:657](app/src-tauri/src/commands.rs:657)).
- Tests at [legacy_import.rs:577](app/src-tauri/src/legacy_import.rs:577), [legacy_import.rs:604](app/src-tauri/src/legacy_import.rs:604).

---

### `pub fn apply_settings_patch(base: &mut Value, patch: &Map<String, Value>)`  *(legacy_import.rs:364)*

**Purpose**: Merge a settings patch into a base Settings JSON value. Defensive: never lets `rd.api_token` leak through and always blanks it as a final safety net.

**Contract**:
- Params:
  - `base` — `&mut Value` (a serialized `Settings`). No-op if not an object.
  - `patch` — typically `ParsedEnv.settings_patch`.
- Returns: `()`.
- Side effects: mutates `base` in place. Forces `base.rd.api_token = ""` even if the patch tried to inject one (test [legacy_import.rs:624](app/src-tauri/src/legacy_import.rs:624)).
- Errors: silent no-op on non-object base.
- Async: no.

**Calls**: only `Value::as_object_mut`, `Map::entry`, `insert`, `or_insert_with`.

**Called by**:
- `apply_legacy_import` ([commands.rs:712](app/src-tauri/src/commands.rs:712)).
- Test at [legacy_import.rs:641](app/src-tauri/src/legacy_import.rs:641).

---

### Tests module — [legacy_import.rs:400-651](app/src-tauri/src/legacy_import.rs:400)

- `temp_dir()` — tempdir helper (duplicates the same pattern in pending and commands).
- `parse_env_routes_token_outside_settings_patch` — key invariant.
- `parse_env_handles_quoted_values_and_comments`.
- `parse_env_warns_on_unknown_and_malformed`.
- `parse_env_warns_on_non_numeric_for_numeric_keys`.
- `parse_env_empty_token_is_treated_as_unset`.
- `sanitize_pending_drops_magnet_fields`.
- `sanitize_pending_requires_torrent_id`.
- `merge_legacy_pending_is_idempotent_by_torrent_id`.
- `merge_legacy_pending_skips_already_existing_ids`.
- `merge_legacy_pending_rejects_corrupt_input`.
- `preview_handles_missing_source_dir`.
- `preview_reports_files_without_echoing_values`.
- `apply_settings_patch_merges_and_clears_api_token`.

Notable detail: `parse_env_routes_token_outside_settings_patch` constructs the literal key string from `["RD_API", "TOKEN"].join("_")` ([legacy_import.rs:425](app/src-tauri/src/legacy_import.rs:425)) — appears to be to avoid letting `RD_API_TOKEN` appear verbatim in the source for auditing tools.

---

## 3.6 `path_manager.rs`

### `pub struct PathManager { data_dir: PathBuf, log_dir: PathBuf }`  *(path_manager.rs:17)*

`#[derive(Debug, Clone)]`. Two absolute paths. Held in `tauri::State` for the app's lifetime.

---

### `pub fn PathManager::new(_app_handle: &AppHandle) -> Result<Self, Box<dyn std::error::Error>>` (Windows)  *(path_manager.rs:24)*

**Purpose**: Resolve `data_dir` and `log_dir` on Windows using `%APPDATA%` and `%LOCALAPPDATA%`. Deliberately ignores Tauri's `app_data_dir()` (which would put data under `%APPDATA%\<bundle.identifier>` instead of `%APPDATA%\JavDBMagnet`).

**Contract**:
- Params: `_app_handle` — unused on Windows (signature matches non-Windows variant).
- Returns: `Ok(PathManager{...})` with:
  - `data_dir = %APPDATA%\JavDBMagnet`
  - `log_dir  = %LOCALAPPDATA%\JavDBMagnet\logs`
- Side effects: reads env vars.
- Errors: `Err("APPDATA env var not set")` / `Err("LOCALAPPDATA env var not set")`.
- Async: no.

**Calls**: `std::env::var(...)`, `PathBuf::from`, `Path::join`.

**Called by**: `lib::run()` setup ([lib.rs:94](app/src-tauri/src/lib.rs:94)).

---

### `pub fn PathManager::new(app_handle: &AppHandle) -> Result<Self, Box<dyn std::error::Error>>` (non-Windows)  *(path_manager.rs:38)*

**Purpose**: Dev-only fallback so `cargo check` passes on Linux/macOS. Production targets Windows only.

**Contract**:
- Returns: `Ok(Self{...})` with paths from `app_handle.path().app_data_dir()` and `.app_log_dir()`.
- Errors: from Tauri's path resolution.

**Calls**: `tauri::Manager::path`, `PathResolver::app_data_dir`, `app_log_dir`.

**Called by**: `lib::run()` setup ([lib.rs:94](app/src-tauri/src/lib.rs:94)).

---

### `pub fn PathManager::ensure_dirs(&self) -> std::io::Result<()>`  *(path_manager.rs:45)*

**Purpose**: `mkdir -p` for both `data_dir` and `log_dir`.

**Contract**:
- Side effects: filesystem mutation.
- Errors: `io::Error` from `create_dir_all`.
- Async: no.

**Calls**: `std::fs::create_dir_all` twice.

**Called by**: `lib::run()` setup ([lib.rs:95](app/src-tauri/src/lib.rs:95)).

---

## 3.7 `pending.rs`

### `pub struct PendingEntry { torrent_id, code, name, size_label, strategy, added_at, last_progress, last_rd_status, last_checked_at }`  *(pending.rs:22)*

Serde-derived DTO. `#[serde(default)]` on most fields so older files round-trip cleanly. `strategy` defaults to `"smart"` via `default_strategy`. `last_checked_at: Option<String>` is the only nullable field.

---

### `fn default_strategy() -> String`  *(pending.rs:55)*

Returns `"smart"`. Trivial. Called only by serde via `#[serde(default = "default_strategy")]`.

---

### `pub fn PendingEntry::new(torrent_id, code, name, size_label, strategy) -> Self`  *(pending.rs:60)*

**Purpose**: Constructor that stamps `added_at = Utc::now().to_rfc3339()` and zeros the runtime-mutable fields.

**Contract**:
- Side effects: `chrono::Utc::now()` clock read.
- Errors: cannot fail.
- Async: no.

**Calls**: `chrono::Utc::now()`, `to_rfc3339()`.

**Called by**:
- `commands::rd_send_magnet` ([commands.rs:474](app/src-tauri/src/commands.rs:474)).
- Test `sample` at [pending.rs:182](app/src-tauri/src/pending.rs:182), [legacy_import.rs:549](app/src-tauri/src/legacy_import.rs:549).

---

### `fn pending_path(data_dir: &Path) -> PathBuf`  *(pending.rs:81)*

Trivial: `data_dir.join("pending_torrents.json")`. Called by `load`, `save`, `tests::entries_have_no_magnet_field`.

---

### `pub fn load(data_dir: &Path) -> Result<Vec<PendingEntry>, String>`  *(pending.rs:86)*

**Purpose**: Read pending list. Missing file → empty vec. Empty/whitespace file → empty vec.

**Contract**:
- Returns: `Ok(Vec)`. `Err("read ...: ...")` or `Err("parse ...: ...")` for IO/parse errors.
- Side effects: one disk read.
- Errors: as above; never panics.
- Async: no.

**Calls**: `Path::exists`, `fs::read_to_string`, `serde_json::from_str`.

**Called by**:
- `commands::pending_list` ([commands.rs:582](app/src-tauri/src/commands.rs:582)).
- `commands::apply_legacy_import` ([commands.rs:783](app/src-tauri/src/commands.rs:783)).
- `pending::add` ([pending.rs:120](app/src-tauri/src/pending.rs:120)).
- `pending::remove` ([pending.rs:130](app/src-tauri/src/pending.rs:130)).
- `pending::update_status` ([pending.rs:144](app/src-tauri/src/pending.rs:144)).
- Several tests.

---

### `pub fn save(data_dir: &Path, entries: &[PendingEntry]) -> Result<(), String>`  *(pending.rs:100)*

**Purpose**: Atomic write via sibling `pending_torrents.json.tmp` + rename.

**Contract**:
- Side effects:
  - `create_dir_all(data_dir)`.
  - Write tmp file with serialized body, `sync_all` (best-effort), then rename.
- Errors: `Err("mkdir ...: ...")`, `Err("create ...")`, `Err("write ...")`, `Err("serialize: ...")`, `Err("rename ... -> ...: ...")`.
- Async: no.

**Calls**: `fs::create_dir_all`, `serde_json::to_string_pretty`, `fs::File::create`, `Write::write_all`, `File::sync_all`, `fs::rename`.

**Called by**:
- `commands::apply_legacy_import` ([commands.rs:786](app/src-tauri/src/commands.rs:786)).
- `pending::add`, `pending::remove`, `pending::update_status`, `pending::clear`.

---

### `pub fn add(data_dir: &Path, entry: PendingEntry) -> Result<Vec<PendingEntry>, String>`  *(pending.rs:119)*

**Purpose**: Add entry; replaces any existing entry with the same `torrent_id`.

**Contract**:
- Side effects: load + save (one read, one atomic write).
- Errors: from `load` or `save`.
- Async: no.

**Calls**: `load`, `Vec::retain`, `Vec::push`, `save`.

**Called by**:
- `commands::rd_send_magnet` pending path ([commands.rs:483](app/src-tauri/src/commands.rs:483)).
- Several tests.

---

### `pub fn remove(data_dir: &Path, torrent_id: &str) -> Result<Vec<PendingEntry>, String>`  *(pending.rs:129)*

**Purpose**: Remove by id. No-op if missing.

**Contract**: Side effects identical to `add`.

**Calls**: `load`, `Vec::retain`, `save`.

**Called by**:
- `commands::rd_check_pending` ([commands.rs:534](app/src-tauri/src/commands.rs:534), [commands.rs:550](app/src-tauri/src/commands.rs:550)).
- `commands::pending_remove` ([commands.rs:590](app/src-tauri/src/commands.rs:590)).
- Test.

---

### `pub fn update_status(data_dir: &Path, torrent_id: &str, rd_status: &str, progress: f64) -> Result<Vec<PendingEntry>, String>`  *(pending.rs:138)*

**Purpose**: Mutate one entry's `last_progress` / `last_rd_status` / `last_checked_at = Utc::now()`. No-op if id missing.

**Contract**:
- Side effects: load + (conditional) save. Writes `Utc::now().to_rfc3339()` into `last_checked_at`.
- Errors: from load/save.
- Async: no.

**Calls**: `load`, `Utc::now().to_rfc3339()`, `save`.

**Called by**:
- `commands::rd_check_pending` ([commands.rs:569](app/src-tauri/src/commands.rs:569)).
- Test at [pending.rs:230](app/src-tauri/src/pending.rs:230).

---

### `pub fn clear(data_dir: &Path) -> Result<(), String>`  *(pending.rs:162)*

**Purpose**: Save an empty list (delete-by-overwrite).

**Calls**: `save(data_dir, &[])`.

**Called by**:
- `commands::pending_clear` ([commands.rs:595](app/src-tauri/src/commands.rs:595)).
- Test.

---

### Tests — [pending.rs:166-258](app/src-tauri/src/pending.rs:166)

- `temp_dir`, `sample` (PendingEntry factory).
- `missing_file_returns_empty`.
- `add_and_load_roundtrips`.
- `add_replaces_same_torrent_id`.
- `remove_nonexistent_is_noop`.
- `update_status_writes_back`.
- `entries_have_no_magnet_field` — defense-in-depth: serialized file contains neither `"magnet:"` nor `"magnet"` field name.
- `clear_empties_the_list`.

---

## 3.8 `secret_store.rs`

### `fn entry() -> Result<keyring::Entry, String>`  *(secret_store.rs:20)*

**Purpose**: Build a `keyring::Entry` for `SERVICE="JavDBMagnet"` / `ACCOUNT="RD_API_TOKEN"`.

**Contract**: pure wrapper; errors mapped to `format!("keyring entry: {e}")`.

**Calls**: `keyring::Entry::new`.

**Called by**: `set_rd_token`, `get_rd_token`, `delete_rd_token`.

---

### `pub fn set_rd_token(token: &str) -> Result<(), String>`  *(secret_store.rs:25)*

**Purpose**: Persist a token. Empty string → delete.

**Contract**:
- Side effects: OS credential store mutation.
- Errors: `Err("keyring entry: ...")` from `entry()`, `Err("keyring set: ...")` from `set_password`, or whatever `delete_internal` returns.
- Async: no.

**Calls**: `entry()`, `keyring::Entry::set_password`, `delete_internal` (when token is empty).

**Called by**:
- `lib::migrate_legacy_token` ([lib.rs:61](app/src-tauri/src/lib.rs:61)).
- `commands::rd_save_token` ([commands.rs:317](app/src-tauri/src/commands.rs:317)).
- `commands::apply_legacy_import` ([commands.rs:675](app/src-tauri/src/commands.rs:675)).

---

### `pub fn get_rd_token() -> Result<Option<String>, String>`  *(secret_store.rs:34)*

**Purpose**: Read the token. `Ok(None)` if no entry yet.

**Contract**:
- Side effects: OS credential store read.
- Errors: `Err("keyring entry: ...")` / `Err("keyring get: ...")`. `NoEntry` is mapped to `Ok(None)` (not an error).
- Async: no.

**Calls**: `entry()`, `keyring::Entry::get_password`.

**Called by**:
- `lib::load_handshake_inputs` ([lib.rs:41](app/src-tauri/src/lib.rs:41)).
- `commands::rd_has_token` ([commands.rs:286](app/src-tauri/src/commands.rs:286)).

---

### `pub fn delete_rd_token() -> Result<(), String>`  *(secret_store.rs:43)*

**Purpose**: Drop the keyring entry.

**Calls**: `entry()`, `delete_internal(&e)`.

**Called by**: `commands::rd_clear_token` ([commands.rs:334](app/src-tauri/src/commands.rs:334)).

---

### `fn delete_internal(e: &keyring::Entry) -> Result<(), String>`  *(secret_store.rs:48)*

**Purpose**: Delete helper. `NoEntry` is treated as success.

**Calls**: `keyring::Entry::delete_credential`.

**Called by**: `set_rd_token` (when token is empty) and `delete_rd_token`.

---

## 3.9 `settings.rs`

### `pub struct UiSettings { theme, scale }`  *(settings.rs:16)*

DTO. `Default`: `theme="light"`, `scale="auto"`.

### `pub struct RdSettings { api_token, file_pick, min_size_mb, cache_wait_seconds }`  *(settings.rs:31)*

DTO. `Default`: empty token, `file_pick="smart"`, `min_size_mb=500`, `cache_wait_seconds=15`.

### `fn default_version() -> u32`  *(settings.rs:51)*

Returns `1`. Serde default for `Settings::version`.

### `pub struct Settings { version, ui, rd }`  *(settings.rs:56)*

DTO. Top-level shape that lands inside `settings.json` under the key `"settings"`.

---

### `fn without_secrets(mut settings: Settings) -> Settings`  *(settings.rs:75)*

**Purpose**: Clear `rd.api_token` so the legacy plaintext field never crosses back into the WebView. Applied on both read and write paths.

**Contract**:
- Side effects: in-place mutation of the moved value.
- Errors: cannot fail.
- Async: no.

**Calls**: `String::clear`.

**Called by**: `read_settings`, `write_settings`, and a test.

---

### `pub struct PathInfo { data_dir: String, log_dir: String }`  *(settings.rs:85)*

DTO returned by `get_paths`.

---

### `pub fn get_paths(path_manager: State<PathManager>) -> PathInfo`  *(settings.rs:91)*

**Purpose**: Return the resolved data + log dirs as strings.

**Contract**:
- Side effects: none.
- Errors: none.
- Async: no.

**Calls**: `Path::display`.

**Called by**: frontend.

---

### `pub fn read_settings(app: AppHandle, path_manager: State<PathManager>) -> Result<Settings, String>`  *(settings.rs:99)*

**Purpose**: Read settings out of `<data_dir>/settings.json` via tauri-plugin-store. Always blanks `rd.api_token` before returning.

**Contract**:
- Side effects: store open + read; one disk read.
- Errors: `Err(<store error>)` or `Err(<serde error>)`. Missing store yields `Settings::default()`.
- Async: no.

Uses an absolute path so the plugin doesn't resolve under its default `BaseDirectory::AppData` (which would land under `%APPDATA%\<identifier>\` instead of `%APPDATA%\JavDBMagnet\`).

**Calls**: `app.store(store_path)`, `Store::get`, `serde_json::from_value::<Settings>`, `without_secrets`.

**Called by**: frontend.

---

### `pub fn write_settings(app: AppHandle, path_manager: State<PathManager>, settings: Settings) -> Result<(), String>`  *(settings.rs:117)*

**Purpose**: Persist settings to `<data_dir>/settings.json`. Blanks `rd.api_token` before serializing.

**Contract**:
- Side effects: disk write (atomic semantics owned by tauri-plugin-store).
- Errors: `Err(<store error>)`, `Err(<serde error>)`, `Err(<save error>)`.
- Async: no.

**Calls**: `app.store(...)`, `serde_json::to_value`, `Store::set`, `Store::save`, `without_secrets`.

**Called by**: frontend.

---

### Test — [settings.rs:130-143](app/src-tauri/src/settings.rs:130)

- `without_secrets_clears_legacy_rd_token_field` — drops a populated `api_token` and confirms it's blanked.

---

## 3.10 `sidecar_manager.rs`

### `pub struct SidecarManager { inner: Arc<Mutex<SidecarInner>> }`  *(sidecar_manager.rs:22)*

Managed in `tauri::State` for the app's lifetime. The `Arc<Mutex<_>>` serializes all requests to the single Python subprocess.

### `struct SidecarInner { child: CommandChild, line_rx: mpsc::UnboundedReceiver<String>, request_counter: u64 }`  *(sidecar_manager.rs:26)*

Private. `child.write(...)` is the stdin sender. `line_rx` is the receiving end of an unbounded mpsc channel — a background task drains the plugin-shell event stream and pushes complete newline-delimited lines here. `request_counter` produces monotonic `r-N` IDs.

---

### `pub async fn SidecarManager::spawn_and_handshake(app, cookies, rd_token, settings, paths) -> Result<Self, String>`  *(sidecar_manager.rs:35)*

**Purpose**: Spawn the bundled `sidecar` binary, perform `hello` + `handshake`, and return a manager ready for `request(...)`.

**Contract**:
- Params:
  - `app: &AppHandle` — used for the shell-plugin sidecar resolve.
  - `cookies: String` — JavDB cookies as a single string.
  - `rd_token: Option<String>` — token if available.
  - `settings: Value` — the `"settings"` object from settings.json (or empty obj).
  - `paths: Value` — `{"data_dir": ..., "log_dir": ...}` JSON.
- Returns: `Ok(SidecarManager)` once both `hello` (with `{"protocol_version": 1}`) and `handshake` returned `ok: true`.
- Side effects:
  - Spawns a child process via `tauri-plugin-shell`.
  - Spawns a tokio task that lives until the child terminates: parses CommandEvent::Stdout chunks into lines (trims `\n` and `\r`) and pushes to the unbounded channel. `CommandEvent::Stderr` is **silently dropped** ([sidecar_manager.rs:71-75](app/src-tauri/src/sidecar_manager.rs:71)); the comment explains M6 will wire stderr to the log file.
  - Writes 2 JSON lines on stdin during construction.
- Errors:
  - `Err("sidecar resolve failed: ...")` / `Err("sidecar spawn failed: ...")` from plugin-shell.
  - `Err("sidecar hello failed: <error.message>")` if hello rejected.
  - `Err("sidecar handshake failed: <error.message>")` if handshake rejected.
- Async: yes. Called via `block_on` in `lib::run`.
- Authorization: this is the bootstrap.

**Calls**:
- `app.shell().sidecar("sidecar")` → `tauri_plugin_shell::ShellExt`.
- `Command::spawn` from plugin-shell.
- `tauri::async_runtime::spawn` for the line-reader task.
- `tokio::sync::mpsc::unbounded_channel`.
- `self.request("hello", ...)`, `self.request("handshake", ...)` → [sidecar_manager.rs:116](app/src-tauri/src/sidecar_manager.rs:116).
- `error_message(&resp)` → [sidecar_manager.rs:167](app/src-tauri/src/sidecar_manager.rs:167).

**Called by**: `lib::run` setup ([lib.rs:109](app/src-tauri/src/lib.rs:109)).

---

### `pub async fn SidecarManager::request(&self, cmd: &str, body: Value) -> Result<Value, String>`  *(sidecar_manager.rs:116)*

**Purpose**: Send one JSON-line request to the sidecar and await one JSON-line response. The core RPC primitive.

**Contract**:
- Params:
  - `cmd` — the `cmd` field injected into the outgoing object.
  - `body` — must be a JSON object or `Value::Null`. Other shapes are rejected.
- Returns: parsed `Value` of the response line.
- Side effects:
  - Acquires `self.inner.lock().await` — **all requests are globally serialized**. (See concurrency model header comment.)
  - Increments `request_counter`; constructs `request_id = "r-N"`.
  - Writes `<serialized line>\n` to the child's stdin.
  - Reads one line from `line_rx`.
- Errors:
  - `Err("request body must be a JSON object or null, got <value>")` for misshapen body.
  - `Err("serialize failed: ...")` from `serde_json::to_string`.
  - `Err("stdin write failed: ...")` from `CommandChild::write`.
  - `Err("sidecar closed before response")` if the line channel returned `None` (the bg task exited).
  - `Err("response parse failed: ...")` if the line isn't valid JSON.
  - `Err("request_id mismatch: expected r-N, got ...")` if the sidecar returns the wrong correlation id.
- Async: yes; awaits both the mutex and the channel.
- Authorization: requires the sidecar to be alive.

**Calls**:
- `Mutex::lock`.
- `serde_json::to_string`.
- `CommandChild::write`.
- `mpsc::UnboundedReceiver::recv`.
- `serde_json::from_str`.

**Called by**:
- `spawn_and_handshake` (twice — hello + handshake).
- Every `#[tauri::command]` that talks to the sidecar (15 of them; full list in the §1 table).

---

### `fn error_message(resp: &Value) -> Option<&str>`  *(sidecar_manager.rs:167)*

**Purpose**: Helper to extract `resp.error.message` as a borrowed `&str`.

**Calls**: only `Value::get` / `as_str`.

**Called by**: `spawn_and_handshake` for the hello/handshake failure messages.

---

## 4. Cross-cutting Concerns

### 4.1 Error type(s)

There is **no custom error enum**. Every fallible function returns `Result<T, String>`, with the `String` typically formatted via `format!("<context>: {e}")`. Tauri serializes the `Err` arm verbatim to the frontend.

A handful of low-level functions use `Result<T, std::io::Error>` (`PathManager::ensure_dirs`) or `Result<T, Box<dyn std::error::Error>>` (`PathManager::new`), but those are only called from the setup closure where the conversion is `?`-eliminated into a `Box<dyn Error>`.

Common error-string shapes:
- `format!("read {}: {e}", path.display())` — pending IO.
- `format!("keyring entry: {e}")` — keyring failures.
- `format!("mkdir {}: {e}", ...)` — directory creation.
- `_err_code(&resp)` — sidecar non-ok responses surface only the `error.code` (e.g. `unknown_handle`, `rd_no_token`).

### 4.2 Logging conventions

There is **no logging crate** wired up in this code. The only places anything is emitted from Rust are:
- `eprintln!` in `migrate_legacy_token` ([lib.rs:62](app/src-tauri/src/lib.rs:62)) — keyring write failure.
- `.expect(...)` at the bottom of `run()` ([lib.rs:154](app/src-tauri/src/lib.rs:154)) — panic on Tauri runtime error.

Stderr from the sidecar process is **silently dropped** by the line-reader background task ([sidecar_manager.rs:71-75](app/src-tauri/src/sidecar_manager.rs:71)). The comment promises M6 will wire it to a log file; that's a TODO at the time of this audit.

### 4.3 Event emission patterns

The backend **does not emit any Tauri events** (no `app.emit(...)` calls anywhere). All frontend↔backend communication is request/response via `#[tauri::command]`.

### 4.4 Settings / state mutation flow

```
frontend write_settings → settings.rs::write_settings → tauri-plugin-store
                                                        ↓
                                                <data_dir>/settings.json
                                                        ↑
frontend read_settings → settings.rs::read_settings → tauri-plugin-store
                                                        ↑
                                          (without_secrets applied both ways)

frontend update_sidecar_settings → commands.rs::update_sidecar_settings → SidecarManager → sidecar process
```

Notably, `write_settings` and `update_sidecar_settings` are **separate commands** and the frontend is responsible for calling both. There is no Rust-side observer pattern; if the frontend writes settings without pushing to the sidecar, the sidecar stays out of sync until the next app restart.

### 4.5 Sidecar lifecycle

- **Spawn**: synchronous during setup via `block_on(SidecarManager::spawn_and_handshake)` ([lib.rs:109](app/src-tauri/src/lib.rs:109)). Setup failure means the window does not open.
- **Handshake**: `hello` (protocol version negotiation) then `handshake` (cookies, token, settings, paths).
- **Health check**: there is **no periodic ping**. `sidecar_ping` exists but is invoked by the frontend on demand.
- **Concurrency**: a single `tokio::sync::Mutex` serializes all requests. This was a deliberate choice because the sidecar's dispatch loop is single-threaded synchronous ([sidecar_manager.rs:7-10](app/src-tauri/src/sidecar_manager.rs:7)).
- **Shutdown**: **there is no explicit shutdown path**. `SidecarManager` does not implement `Drop`. The sidecar child is owned by `CommandChild` inside the managed state; when the app process exits, the child process is left to whatever cleanup tauri-plugin-shell provides. No goodbye message is sent.
- **Crash handling**: if the line-reader task exits (e.g. `CommandEvent::Terminated`), any subsequent `request(...)` call hits `Err("sidecar closed before response")` once the channel drains. There is no automatic respawn.

### 4.6 Path discovery / config dirs

- `data_dir` = `%APPDATA%\JavDBMagnet` on Windows ([path_manager.rs:24-33](app/src-tauri/src/path_manager.rs:24)).
- `log_dir` = `%LOCALAPPDATA%\JavDBMagnet\logs`.
- Non-Windows fallback uses Tauri's `app_data_dir()` / `app_log_dir()` — dev convenience only.
- Both dirs are `create_dir_all`'d during setup.
- The choice to hardcode `JavDBMagnet` (rather than the reverse-DNS bundle identifier) is documented at [path_manager.rs:7-9](app/src-tauri/src/path_manager.rs:7) — spec §4.

### 4.7 Security invariants (per-module annotations)

1. **RD token never lives in plaintext on disk** after the first launch: `migrate_legacy_token` moves it to the keyring and blanks `settings.rd.api_token`. Both `read_settings` and `write_settings` go through `without_secrets` ([settings.rs:75](app/src-tauri/src/settings.rs:75)) which clears the field defensively.
2. **Magnet text only crosses the IPC boundary inbound**: `register_magnets` is the only inbound path; everywhere else, magnets are referenced by `handle_id` only. Comments at [commands.rs:6-9](app/src-tauri/src/commands.rs:6) and [commands.rs:113-116](app/src-tauri/src/commands.rs:113) document the invariant; the `entries_have_no_magnet_field` test ([pending.rs:241](app/src-tauri/src/pending.rs:241)) and `sanitize_pending_drops_magnet_fields` test ([legacy_import.rs:494](app/src-tauri/src/legacy_import.rs:494)) defend the persistence side.
3. **cookies.txt body is never returned**: `cookies_status_for` reports only metadata, defended by `cookies_status_does_not_leak_body` ([commands.rs:1010](app/src-tauri/src/commands.rs:1010)).
4. **The legacy importer cannot exfiltrate values**: `preview` only echoes presence flags and key names. The `preview_reports_files_without_echoing_values` test ([legacy_import.rs:586](app/src-tauri/src/legacy_import.rs:586)) asserts no echo of test secrets.
5. **`rd.api_token` is structurally unreachable from `.env` patches**: `parse_env` puts the token into a separate `ParsedEnv.token` field; `apply_settings_patch` ([legacy_import.rs:381-383](app/src-tauri/src/legacy_import.rs:381)) explicitly skips any `rd.api_token` key in the patch and then re-blanks the field as a final safety net.

---

## 5. Call Graph (top entry points)

### 5.1 `lib::run` → setup

```
lib::run                                              (lib.rs:87)
├── PathManager::new                                  (path_manager.rs:24)
│   └── std::env::var(APPDATA / LOCALAPPDATA)
├── PathManager::ensure_dirs                          (path_manager.rs:45)
│   └── std::fs::create_dir_all  x2
├── load_handshake_inputs                             (lib.rs:27)
│   ├── std::fs::read_to_string  (cookies.txt, settings.json)
│   ├── serde_json::from_str
│   ├── secret_store::get_rd_token                    (secret_store.rs:34)
│   │   ├── keyring::Entry::new
│   │   └── keyring::Entry::get_password
│   └── migrate_legacy_token (only if keyring empty)  (lib.rs:53)
│       ├── secret_store::set_rd_token                (secret_store.rs:25)
│       ├── std::fs::read_to_string + serde_json roundtrip
│       └── std::fs::write
├── tauri::AppHandle::manage(PathManager)
├── tauri::async_runtime::block_on(
│     SidecarManager::spawn_and_handshake )           (sidecar_manager.rs:35)
│   ├── ShellExt::sidecar("sidecar").spawn
│   ├── tauri::async_runtime::spawn (line reader task)
│   ├── self.request("hello", ...)                    (sidecar_manager.rs:116)
│   └── self.request("handshake", ...)
├── tauri::AppHandle::manage(SidecarManager)
└── tauri::generate_handler![ ... 28 commands ... ]
```

### 5.2 `commands::fetch_javdb`

```
commands::fetch_javdb                                 (commands.rs:34)
└── SidecarManager::request("fetch_javdb", ...)       (sidecar_manager.rs:116)
    ├── Mutex::lock
    ├── CommandChild::write
    ├── mpsc::UnboundedReceiver::recv
    └── serde_json::from_str
```

### 5.3 `commands::copy_magnet`

```
commands::copy_magnet                                 (commands.rs:53)
├── SidecarManager::request("resolve_magnet", ...)    (sidecar_manager.rs:116)
└── ClipboardExt::clipboard().write_text(magnet)      (tauri-plugin-clipboard-manager)
    [ local `magnet` String drops at function end ]
```

### 5.4 `commands::copy_magnets_bulk`

```
commands::copy_magnets_bulk                           (commands.rs:164)
├── SidecarManager::request("resolve_magnets", ...)
└── ClipboardExt::clipboard().write_text(joined)
```

### 5.5 `commands::copy_rd_links_bulk`

```
commands::copy_rd_links_bulk                          (commands.rs:223)
└── ClipboardExt::clipboard().write_text(joined)
    [ No sidecar — pure clipboard write with trim/filter ]
```

### 5.6 `commands::register_magnets`

```
commands::register_magnets                            (commands.rs:117)
├── SidecarManager::request("register_magnets", ...)
├── _err_code (on failure)                            (commands.rs:259)
└── serde_json::from_value  x2  (RegisteredMagnet, String)
```

### 5.7 `commands::rd_send_magnet`

```
commands::rd_send_magnet                              (commands.rs:401)
├── SidecarManager::request("rd_send_magnet", ...)
├── _err_code (on failure)
├── if status == "completed":
│   └── serde_json::from_value::<Vec<RdLink>>
└── if status == "pending":
    ├── PendingEntry::new                             (pending.rs:60)
    │   └── chrono::Utc::now().to_rfc3339()
    └── pending::add                                  (pending.rs:119)
        ├── pending::load                             (pending.rs:86)
        │   └── std::fs::read_to_string + serde_json::from_str
        └── pending::save                             (pending.rs:100)
            ├── std::fs::create_dir_all
            ├── serde_json::to_string_pretty
            ├── std::fs::File::create  +  write_all  +  sync_all
            └── std::fs::rename (tmp → real)
```

### 5.8 `commands::rd_check_pending`

```
commands::rd_check_pending                            (commands.rs:516)
├── SidecarManager::request("rd_check_pending", ...)
├── _err_code (on failure)
├── if status == "completed":
│   ├── pending::remove                               (pending.rs:129)
│   │   ├── pending::load
│   │   └── pending::save
│   └── serde_json::from_value::<Vec<RdLink>>
├── if status == "missing":
│   └── pending::remove
└── if status == "pending":
    └── pending::update_status                        (pending.rs:138)
        ├── pending::load
        ├── chrono::Utc::now().to_rfc3339()
        └── pending::save
```

### 5.9 `commands::rd_save_token`

```
commands::rd_save_token                               (commands.rs:313)
├── secret_store::set_rd_token                        (secret_store.rs:25)
│   ├── keyring::Entry::new
│   └── keyring::Entry::set_password
│       (or delete_internal if empty)
└── SidecarManager::request("rd_set_token", ...)
```

### 5.10 `commands::apply_legacy_import`

```
commands::apply_legacy_import                         (commands.rs:626)
├── legacy_import::preview                            (legacy_import.rs:297)
│   ├── std::fs::read_to_string (.env, pending.json)
│   ├── legacy_import::parse_env                      (legacy_import.rs:92)
│   └── serde_json::from_str::<Vec<Value>>
│
├── if env_present:
│   ├── std::fs::read_to_string
│   ├── legacy_import::parse_env
│   ├── (if token):
│   │   ├── secret_store::set_rd_token
│   │   └── SidecarManager::request("rd_set_token", ...)
│   │       └── _err_code (on failure)
│   └── (if non-secret patch):
│       ├── app.store(store_path)                    (tauri-plugin-store)
│       ├── Store::get("settings")
│       │   (fallback: serde_json::to_value(Settings::default()))
│       ├── legacy_import::apply_settings_patch       (legacy_import.rs:364)
│       ├── Store::set("settings", base)
│       └── Store::save
│
├── if cookies_present:
│   ├── std::fs::create_dir_all
│   └── std::fs::copy(src_cookies, dst_cookies)
│
└── if pending_present:
    ├── std::fs::read_to_string
    ├── pending::load (existing)                      (pending.rs:86)
    ├── legacy_import::merge_legacy_pending           (legacy_import.rs:261)
    │   ├── serde_json::from_str::<Vec<Value>>
    │   └── legacy_import::sanitize_pending_entry x N (legacy_import.rs:195)
    │       └── chrono::Utc::now (only if added_at empty)
    └── pending::save                                 (pending.rs:100)
```

---

## 6. Notable Findings / Oddities

- ~~**`forget_magnets` does not check `resp.ok`**~~ **RESOLVED M9 Phase 0-A**: updated `commands::forget_magnets` ([commands.rs:146](app/src-tauri/src/commands.rs#L146)) to call `ensure_ok(&resp)?`.
- **No Rust-side logging**. The only diagnostic output is `eprintln!` in one migration path, plus `.expect` panic. Sidecar stderr is dropped on the floor. The comment at [sidecar_manager.rs:73-75](app/src-tauri/src/sidecar_manager.rs:73) acknowledges this as a deferred M6 item.
- **No graceful sidecar shutdown**. `SidecarManager` has no `Drop` impl and no goodbye message. The child process termination is whatever the OS / plugin-shell does at app exit.
- **No sidecar respawn on crash**. Once the line-reader task exits, all subsequent `request(...)` calls error with `"sidecar closed before response"` and the user has to restart the app.
- **Three independent `temp_dir` test helpers** in [pending.rs:174](app/src-tauri/src/pending.rs:174), [legacy_import.rs:410](app/src-tauri/src/legacy_import.rs:410), [commands.rs:970](app/src-tauri/src/commands.rs:970) — duplicated rather than factored into a shared dev-dep or test util.
- **`STORE_FILE` is defined twice** — `pub` in [lib.rs:15](app/src-tauri/src/lib.rs:15) and `private` in [settings.rs:12](app/src-tauri/src/settings.rs:12). `apply_legacy_import` uses `crate::STORE_FILE` while `settings.rs` uses its own. Mild duplication risk if one is changed and the other isn't.
- **`pending::FILE_NAME` and `legacy_import::LEGACY_PENDING_FILE`** both hardcode `"pending_torrents.json"`. Similar duplication for `cookies.txt` (`commands::COOKIES_FILE_NAME` vs `legacy_import::LEGACY_COOKIES_FILE`).
- **`update_settings` push to sidecar is not automatic**. After `write_settings`, the frontend must also call `update_sidecar_settings` for the running daemon to pick up the change. No Rust-side hook chains these.
- **Test at [legacy_import.rs:425](app/src-tauri/src/legacy_import.rs:425) reconstructs `"RD_API_TOKEN"`** as `["RD_API", "TOKEN"].join("_")`. Appears to be intentional — keeps the literal string out of grep-able source for auditing.
- **`block_on` during `.setup`** ([lib.rs:109](app/src-tauri/src/lib.rs:109)). The sidecar handshake is performed on the setup thread; any slowness there delays window-open. Reasonable given the rest of the app assumes the sidecar exists.
- **`_err_code` is named with a leading underscore** despite being widely used ([commands.rs:259](app/src-tauri/src/commands.rs:259)). Usually that convention signals "intentionally unused" — a stylistic inconsistency rather than a bug.
- **`pending::save` calls `f.sync_all().ok()`** ([pending.rs:111](app/src-tauri/src/pending.rs:111)) — sync failures are ignored. Acceptable on Windows where `sync_all` is best-effort, but worth noting.
- **`copy_rd_links_bulk` takes `AppHandle` but not `SidecarManager`** — it's the only `copy_*` command that doesn't go through the sidecar at all. The link strings are already on the frontend.
- **`rd_has_token` is async but does no awaiting**. Required by Tauri's command macro when `State<'_, _>` is involved — but this one doesn't even take state. The async signature is gratuitous; sync `pub fn rd_has_token() -> Result<RdHasTokenResult, String>` would work.

---

*End of Rust backend contract reference.*
