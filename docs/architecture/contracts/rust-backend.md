# Rust Backend — Function Contracts & Call Trace

Reference document for the Tauri 2.x Rust backend powering JavDBMagnet. Each function has a contract entry (params / returns / side effects / errors / async / authorization), an outbound call list, and a reverse "called by" list.

All file:line references are absolute to the workspace root.

Last refreshed against HEAD `7c877a8` on 2026-10-16.

---

## 1. Overview

### Crate

- Crate name: `javdbmagnet_lib` (library, `crate-type = ["staticlib", "cdylib", "rlib"]`) + thin `javdbmagnet` binary entry ([Cargo.toml](app/src-tauri/Cargo.toml)).
- Edition / runtime: Rust 2021, Tauri 2 with `tauri::async_runtime` (tokio under the hood; `tokio` is a direct dep with `features = ["sync"]` for `mpsc`).
- `keyring` 3 is split per target: `windows-native` (Windows), `apple-native` (macOS), `linux-native-sync-persistent` + `crypto-rust` (Linux). Dev-dependency `tauri` with `features = ["test"]` provides `MockRuntime` for `tests/sidecar_command.rs`.
- Top-level module layout (declared in [lib.rs:1-8](app/src-tauri/src/lib.rs:1)):
  - `commands` — `#[tauri::command]` exports (the JS-callable API surface).
  - `cookie_store` — JavDB cookie blob via the OS credential manager (`keyring` crate).
  - `path_manager` — resolves `%APPDATA%\JavDBMagnet` and `%LOCALAPPDATA%\JavDBMagnet\logs`.
  - `pending` — `pending_torrents.json` CRUD with atomic write.
  - `legacy_import` — pure parse/sanitize for the M7a-lite import flow.
  - `secret_store` — RD token via the OS credential manager (`keyring` crate).
  - `settings` — `tauri-plugin-store`-backed `settings.json` schema.
  - `sidecar_manager` — long-lived Python sidecar with line-delimited JSON RPC.
  - `build_support` — `#[cfg(test)]` only, `#[path = "../build_support.rs"]` ([lib.rs:10-13](app/src-tauri/src/lib.rs:10)), so the build-script helper's tests run under `cargo test`.
- `sidecar_manager::sidecar_command` is re-exported `#[doc(hidden)] pub use` at [lib.rs:25-26](app/src-tauri/src/lib.rs:25) solely so `tests/sidecar_command.rs` can reach it.

### Binary entry → library entry

- [main.rs:4-6](app/src-tauri/src/main.rs:4) `fn main()` → `javdbmagnet_lib::run()`.
- [build.rs:3-29](app/src-tauri/build.rs:3) build-script `fn main()` → `tauri_build::build()` plus the MSVC test-manifest step (Cargo build time, not runtime).
- [lib.rs:385-456](app/src-tauri/src/lib.rs:385) `pub fn run()` builds the Tauri app, registers plugins, wires `setup`, declares `invoke_handler`.

### Tauri command surface (JS-callable API)

Registered via `tauri::generate_handler!` at [lib.rs:421-453](app/src-tauri/src/lib.rs:421) — 31 commands. In source order:

| Command | Module | Async | File:Line | Frontend caller |
|---|---|---|---|---|
| `get_paths` | settings | sync | [settings.rs:103](app/src-tauri/src/settings.rs:103) | [App.svelte:232](app/src/App.svelte:232) |
| `read_settings` | settings | sync | [settings.rs:111](app/src-tauri/src/settings.rs:111) | [App.svelte:214](app/src/App.svelte:214) |
| `write_settings` | settings | sync | [settings.rs:139](app/src-tauri/src/settings.rs:139) | [App.svelte:290](app/src/App.svelte:290), [App.svelte:1549](app/src/App.svelte:1549) |
| `sidecar_ping` | commands | async | [commands.rs:31](app/src-tauri/src/commands.rs:31) | [App.svelte:314](app/src/App.svelte:314) |
| `fetch_javdb` | commands | async | [commands.rs:36](app/src-tauri/src/commands.rs:36) | [scraper.ts:116](app/src/lib/scraper.ts:116) |
| `copy_magnet` | commands | async | [commands.rs:56](app/src-tauri/src/commands.rs:56) | [App.svelte:540](app/src/App.svelte:540) |
| `copy_magnets_bulk` | commands | async | [commands.rs:159](app/src-tauri/src/commands.rs:159) | [App.svelte:555](app/src/App.svelte:555) |
| `copy_rd_links_bulk` | commands | async | [commands.rs:226](app/src-tauri/src/commands.rs:226) | [App.svelte:1134](app/src/App.svelte:1134), [App.svelte:1153](app/src/App.svelte:1153), [App.svelte:1171](app/src/App.svelte:1171), [App.svelte:1273](app/src/App.svelte:1273) |
| `forget_magnets` | commands | async | [commands.rs:141](app/src-tauri/src/commands.rs:141) | [App.svelte:377](app/src/App.svelte:377), [App.svelte:737](app/src/App.svelte:737) |
| `register_magnets` | commands | async | [commands.rs:113](app/src-tauri/src/commands.rs:113) | [App.svelte:451](app/src/App.svelte:451) |
| `rd_has_token` | commands | async | [commands.rs:307](app/src-tauri/src/commands.rs:307) | [App.svelte:249](app/src/App.svelte:249) |
| `rd_test_token` | commands | async | [commands.rs:329](app/src-tauri/src/commands.rs:329) | [App.svelte:876](app/src/App.svelte:876) |
| `rd_save_token` | commands | async | [commands.rs:356](app/src-tauri/src/commands.rs:356) | [App.svelte:895](app/src/App.svelte:895) |
| `rd_clear_token` | commands | async | [commands.rs:377](app/src-tauri/src/commands.rs:377) | [App.svelte:916](app/src/App.svelte:916) |
| `rd_check_user` | commands | async | [commands.rs:390](app/src-tauri/src/commands.rs:390) | [App.svelte:903](app/src/App.svelte:903), [App.svelte:935](app/src/App.svelte:935) |
| `rd_send_magnet` | commands | async | [commands.rs:443](app/src-tauri/src/commands.rs:443) | [rdSender.ts:137](app/src/lib/rdSender.ts:137) |
| `rd_check_pending` | commands | async | [commands.rs:538](app/src-tauri/src/commands.rs:538) | [rdSender.ts:143](app/src/lib/rdSender.ts:143) |
| `pending_list` | commands | async | [commands.rs:587](app/src-tauri/src/commands.rs:587) | [App.svelte:224](app/src/App.svelte:224), [App.svelte:1192](app/src/App.svelte:1192) |
| `pending_remove` | commands | async | [commands.rs:594](app/src-tauri/src/commands.rs:594) | [App.svelte:1625](app/src/App.svelte:1625) |
| `pending_clear` | commands | async | [commands.rs:602](app/src-tauri/src/commands.rs:602) | [App.svelte:1640](app/src/App.svelte:1640) |
| `get_legacy_default_dir` | commands | sync | [commands.rs:620](app/src-tauri/src/commands.rs:620) | [App.svelte:259](app/src/App.svelte:259) |
| `preview_legacy_import` | commands | sync | [commands.rs:625](app/src-tauri/src/commands.rs:625) | [App.svelte:1315](app/src/App.svelte:1315) |
| `apply_legacy_import` | commands | async | [commands.rs:634](app/src-tauri/src/commands.rs:634) | [App.svelte:1591](app/src/App.svelte:1591) |
| `get_cookies_status` | commands | sync | [commands.rs:1050](app/src-tauri/src/commands.rs:1050) | [App.svelte:1344](app/src/App.svelte:1344), [App.svelte:1406](app/src/App.svelte:1406) |
| `migrate_cookies_now` | commands | async | [commands.rs:1074](app/src-tauri/src/commands.rs:1074) | [App.svelte:1336](app/src/App.svelte:1336) |
| `save_cookies` | commands | async | [commands.rs:1132](app/src-tauri/src/commands.rs:1132) | [App.svelte:1434](app/src/App.svelte:1434) |
| `clear_cookies` | commands | async | [commands.rs:1203](app/src-tauri/src/commands.rs:1203) | [App.svelte:1385](app/src/App.svelte:1385) |
| `create_cookies_template` | commands | sync | [commands.rs:1248](app/src-tauri/src/commands.rs:1248) | [App.svelte:1484](app/src/App.svelte:1484) |
| `open_data_dir` | commands | sync | [commands.rs:1276](app/src-tauri/src/commands.rs:1276) | [App.svelte:1461](app/src/App.svelte:1461) |
| `open_logs_dir` | commands | sync | [commands.rs:1281](app/src-tauri/src/commands.rs:1281) | [App.svelte:1470](app/src/App.svelte:1470) |
| `update_sidecar_settings` | commands | async | [commands.rs:1259](app/src-tauri/src/commands.rs:1259) | [App.svelte:1553](app/src/App.svelte:1553) |

### Shared `tauri::State`

Two values are `.manage()`d at setup time ([lib.rs:402](app/src-tauri/src/lib.rs:402), [lib.rs:417](app/src-tauri/src/lib.rs:417)):

| Type | Owner | Lifetime |
|---|---|---|
| `PathManager` | [path_manager.rs:17](app/src-tauri/src/path_manager.rs:17) | for the app's lifetime |
| `SidecarManager` | [sidecar_manager.rs:59](app/src-tauri/src/sidecar_manager.rs:59) | for the app's lifetime (one daemon child) |

Plus the `tauri-plugin-store` Store (file-backed, opened on demand via `app.store(...)`).

### Config & capabilities

- [tauri.conf.json](app/src-tauri/tauri.conf.json): `identifier = "com.javdbmagnet.app"`, `bundle.externalBin = ["binaries/sidecar"]` (resolved at runtime by `app.shell().sidecar("sidecar")`), CSP `default-src 'self'; script-src 'self'; object-src 'none'; frame-src 'none'`, `withGlobalTauri: false`.
- [capabilities/default.json](app/src-tauri/capabilities/default.json) (window `main`): `core:default` plus `shell:allow-open` scoped to `https://real-debrid.com/apitoken` only (used by the frontend's `openExternal` from `@tauri-apps/plugin-shell`, [App.svelte:5](app/src/App.svelte:5)). No `clipboard-manager`, `dialog` or `store` permissions are granted, so the WebView reaches clipboard / settings only through the Rust commands above.

### Constants

- `STORE_FILE = "settings.json"` — private `const` at [lib.rs:28](app/src-tauri/src/lib.rs:28) (reached from `commands.rs` as `crate::STORE_FILE`) and a private duplicate at [settings.rs:13](app/src-tauri/src/settings.rs:13). `SETTINGS_KEY = "settings"` — [settings.rs:14](app/src-tauri/src/settings.rs:14).
- `COOKIES_MAX_BYTES = 64 * 1024` — `u64` at [lib.rs:36](app/src-tauri/src/lib.rs:36) (handshake-time file read cap) and `usize` at [cookie_store.rs:32](app/src-tauri/src/cookie_store.rs:32) (keyring write cap). `COOKIES_TOO_LARGE_ERR = "cookies_too_large"` — [cookie_store.rs:37](app/src-tauri/src/cookie_store.rs:37).
- `APP_FOLDER = "JavDBMagnet"` — [path_manager.rs:14](app/src-tauri/src/path_manager.rs:14).
- `PROTOCOL_VERSION = 1` — [sidecar_manager.rs:34](app/src-tauri/src/sidecar_manager.rs:34).
- Sidecar request budgets — `DEFAULT_REQUEST_TIMEOUT_SECS = 60` ([sidecar_manager.rs:37](app/src-tauri/src/sidecar_manager.rs:37)), `RD_SEND_TIMEOUT_SLACK_SECS = 90` ([sidecar_manager.rs:42](app/src-tauri/src/sidecar_manager.rs:42)), `MAX_RD_CACHE_WAIT_SECS = 300` ([sidecar_manager.rs:47](app/src-tauri/src/sidecar_manager.rs:47)), `MIN_RD_CACHE_WAIT_SECS = 5` ([sidecar_manager.rs:53](app/src-tauri/src/sidecar_manager.rs:53)), `DEFAULT_RD_CACHE_WAIT_SECS = 15` ([sidecar_manager.rs:57](app/src-tauri/src/sidecar_manager.rs:57)).
- `LOG_DIR_ENV = "JAVDB_LOG_DIR"` — [sidecar_manager.rs:152](app/src-tauri/src/sidecar_manager.rs:152).
- `COOKIES_FILE_NAME = "cookies.txt"` — [commands.rs:971](app/src-tauri/src/commands.rs:971). Also redefined as `pub const LEGACY_COOKIES_FILE` in [legacy_import.rs:30](app/src-tauri/src/legacy_import.rs:30), and hardcoded as a literal in `load_cookies` ([lib.rs:85](app/src-tauri/src/lib.rs:85)).
- `CLEARED_SIDECAR_STALE = "cookies_cleared_sidecar_stale"` — [commands.rs:1217](app/src-tauri/src/commands.rs:1217). Matched by prefix in the frontend's `clearCookies` ([App.svelte:1396](app/src/App.svelte:1396)).
- RD token keyring entry: `SERVICE = "JavDBMagnet"`, `ACCOUNT = "RD_API_TOKEN"` — [secret_store.rs:17-18](app/src-tauri/src/secret_store.rs:17). `RD_TOKEN_MAX_LEN = 255` ([secret_store.rs:29](app/src-tauri/src/secret_store.rs:29)), `RD_TOKEN_FORMAT_ERR = "rd_token_format_invalid"` ([secret_store.rs:52](app/src-tauri/src/secret_store.rs:52)).
- Cookie keyring entry: `SERVICE = "JavDBMagnet"`, `ACCOUNT = "JAVDB_COOKIES"` — [cookie_store.rs:25-26](app/src-tauri/src/cookie_store.rs:25).
- `FILE_NAME = "pending_torrents.json"` — [pending.rs:19](app/src-tauri/src/pending.rs:19). Also redefined as `LEGACY_PENDING_FILE` in [legacy_import.rs:31](app/src-tauri/src/legacy_import.rs:31). `MAX_PENDING_FILE_BYTES = 4 MiB` — [pending.rs:25](app/src-tauri/src/pending.rs:25).
- `LEGACY_ENV_FILE = ".env"` — [legacy_import.rs:29](app/src-tauri/src/legacy_import.rs:29).
- `COOKIES_TEMPLATE` — large UTF-8 (no BOM) instruction blob, [commands.rs:1222](app/src-tauri/src/commands.rs:1222).

---

## 2. Entry Points

### `main.rs` flow

`fn main()` at [main.rs:4-6](app/src-tauri/src/main.rs:4) just calls `javdbmagnet_lib::run()`. The `#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]` line at [main.rs:2](app/src-tauri/src/main.rs:2) hides the console window in release builds.

### `build.rs` flow

`fn main()` at [build.rs:3-29](app/src-tauri/build.rs:3) is the Cargo build-script entry. It calls `tauri_build::build()` so Tauri can generate build-time metadata/resources, emits `cargo:rerun-if-changed=tests` / `build_support.rs`, and — only when `CARGO_CFG_TARGET_ENV == "msvc"` **and** `build_support::has_integration_tests("tests")` — emits `cargo:rustc-link-arg-tests` for the Common Controls v6 manifest. It is executed by Cargo before compiling the app crate and is not part of the runtime call graph.

### `lib::run()` flow

[lib.rs:385-456](app/src-tauri/src/lib.rs:385). Steps:

1. `tauri::Builder::default()` —
2. `.plugin(tauri_plugin_store::Builder::new().build())` — Store plugin ([lib.rs:387](app/src-tauri/src/lib.rs:387)).
3. `.plugin(tauri_plugin_shell::init())` — Shell plugin (used for sidecar spawn + the frontend's scoped external open).
4. `.plugin(tauri_plugin_clipboard_manager::init())` — clipboard (Rust-only access; never exposed to frontend directly).
5. `.plugin(tauri_plugin_dialog::init())` — registered, but no `dialog:*` permission is granted in `capabilities/default.json` and the frontend does not import `@tauri-apps/plugin-dialog`.
6. `.setup(|app| ...)` — synchronous bootstrap (see below).
7. `.invoke_handler(tauri::generate_handler![...])` — registers the 31-command surface.
8. `.run(tauri::generate_context!())` — main loop. Calls `.expect("error while running tauri application")` on failure.

### Setup hook ([lib.rs:391-420](app/src-tauri/src/lib.rs:391))

1. `PathManager::new(app.handle())` → resolves data + log paths from env vars (Windows) or `app_data_dir()` (other OS).
2. `path_manager.ensure_dirs()` → `create_dir_all` for both.
3. `load_handshake_inputs(&path_manager)` → returns `(cookies: String, rd_token: Option<String>, settings_value: Value)`. Cookies come from `load_cookies` (migrates a real `cookies.txt` into the keyring and deletes the file, else reads the keyring); reads settings.json; then either reads the RD token from the keyring or migrates it from legacy plaintext; finally blanks `rd.api_token` in the settings value handed to the sidecar.
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
- `javdbmagnet_lib::run()` → [lib.rs:385](app/src-tauri/src/lib.rs:385).

**Called by**: OS process loader (no Rust callers).

---

## 3.2 `build.rs` / `build_support.rs`

### `fn main()`  *(build.rs:3)*

**Purpose**: Cargo build-script entry for Tauri build metadata/resource generation, plus embedding the Common Controls v6 manifest into **test targets only** on MSVC (tauri-build embeds it into the app binary only; the mock App in `tests/sidecar_command.rs` links comctl32's `TaskDialogIndirect` and would otherwise die with `STATUS_ENTRYPOINT_NOT_FOUND` / 0xC0000139). See [docs/platform/windows-build.md](docs/platform/windows-build.md) §3.

**Contract**:
- Params: none.
- Returns: `()`.
- Side effects: delegates to Tauri build tooling; prints `cargo:rerun-if-changed=tests`, `cargo:rerun-if-changed=build_support.rs`; on MSVC with integration tests present prints `cargo:rustc-link-arg-tests=/MANIFEST:EMBED` and the `/MANIFESTDEPENDENCY:...Microsoft.Windows.Common-Controls...6.0.0.0...` line ([build.rs:19-34](app/src-tauri/build.rs:19)). The gate exists because Cargo rejects `rustc-link-arg-tests` when the package has no test target.
- Errors: build-script failures surface through Cargo/Tauri build output.
- Async: no.
- Authorization: none.

**Calls**:
- `tauri_build::build()`.
- `build_support::has_integration_tests(Path::new("tests"))`.

**Called by**: Cargo build-script execution before compiling `app/src-tauri`.

---

### `pub fn has_integration_tests(tests_dir: &Path) -> bool`  *(build_support.rs:11)*

**Purpose**: Mirror Cargo's test-target auto-discovery: `tests/*.rs` or `tests/*/main.rs`. Assumes the manifest keeps auto-discovery (no `autotests = false`, no `[[test]]` path outside `tests/`).

**Contract**:
- Params: directory to scan.
- Returns: `true` if any top-level `.rs` file or any subdirectory with `main.rs` exists; `false` if the dir is missing/unreadable or holds neither.
- Side effects: one `read_dir`.
- Errors: none (missing dir → `false`).
- Async: no.

**Calls**: `std::fs::read_dir`, `Path::is_dir`, `Path::is_file`, `Path::extension`.

**Called by**: `build.rs` `main` ([build.rs:20](app/src-tauri/build.rs:20)); its own tests via the `#[cfg(test)]` include in [lib.rs:11-13](app/src-tauri/src/lib.rs:11).

### Tests — [build_support.rs:25-121](app/src-tauri/build_support.rs:25)

- `Scratch` — tempdir helper with `file` / `dir` and a `Drop` cleanup.
- `missing_tests_dir_has_no_integration_tests`, `empty_tests_dir_has_no_integration_tests`, `non_rust_files_are_not_test_targets`, `top_level_rs_file_is_a_test_target`, `subdir_needs_main_rs_to_be_a_test_target`.

---

## 3.3 `lib.rs`

### `fn load_handshake_inputs(path_manager: &PathManager) -> (String, Option<String>, Value)`  *(lib.rs:49)*

**Purpose**: Read handshake inputs (cookies, settings JSON, RD token) needed to start the sidecar.

**Contract**:
- Params: `path_manager` — borrowed; only `path_manager.data_dir` is used (immutable view).
- Returns: tuple `(cookies, rd_token, settings_value)`:
  - `cookies`: from `load_cookies` — the extracted cookie pairs of a freshly migrated `cookies.txt`, else the keyring value, else empty string.
  - `rd_token`: `Some(token)` if a non-empty token was found in the OS credential store, else the result of `migrate_legacy_token` over `settings.rd.api_token`. `None` if neither source had a usable value (including a keyring read error with nothing to migrate).
  - `settings_value`: the `"settings"` object out of `<data_dir>/settings.json`. Defaults to empty JSON object on any read/parse failure. `rd.api_token` is blanked (`commands::blank_rd_api_token`, [lib.rs:64](app/src-tauri/src/lib.rs:64)) after migration has read it, so the handshake never carries the legacy plaintext token into sidecar memory — even when a malformed legacy value is deliberately left on disk.
- Side effects: file I/O on `cookies.txt` and `settings.json`; keyring reads. May migrate `cookies.txt` into the keyring (deleting the file) and may invoke `migrate_legacy_token`, which writes the keyring + rewrites the JSON wrapper.
- Errors: no error type; all errors are swallowed into defaults. `load_cookies` / `migrate_cookies_from_file` / `migrate_legacy_token` write diagnostics to stderr.
- Async: no.
- Authorization: requires `path_manager` ([lib.rs:392](app/src-tauri/src/lib.rs:392)) but no other invariants.

**Calls**:
- `load_cookies(path_manager)` → [lib.rs:84](app/src-tauri/src/lib.rs:84).
- `std::fs::read_to_string(settings_path)`.
- `serde_json::from_str::<Value>` — settings parse.
- `secret_store::get_rd_token()` → [secret_store.rs:74](app/src-tauri/src/secret_store.rs:74).
- `migrate_legacy_token(...)` → [lib.rs:177](app/src-tauri/src/lib.rs:177).
- `commands::blank_rd_api_token(&mut settings_value)` → [commands.rs:878](app/src-tauri/src/commands.rs:878).

**Called by**:
- `run()` setup closure ([lib.rs:395](app/src-tauri/src/lib.rs:395)).

---

### `fn load_cookies(path_manager: &PathManager) -> String`  *(lib.rs:84)*

**Purpose**: Resolve cookies for the sidecar handshake. Precedence: (1) `cookies.txt` with a real cookie pair → migrate to keyring, delete file, use it; (2) else the credential store; (3) else empty (sidecar surfaces `cloudflare_block` on first fetch).

**Contract**:
- Params: `path_manager` — uses `data_dir.join("cookies.txt")`.
- Returns: cookie string, possibly empty.
- Side effects: see `migrate_cookies_from_file`; one keyring read when nothing was migrated.
- Errors: none returned. A keyring read failure prints `[handshake] cookie keyring read failed: {e}` to stderr and falls back to empty.
- Async: no.

**Calls**:
- `migrate_cookies_from_file(&cookies_path)` → [lib.rs:112](app/src-tauri/src/lib.rs:112).
- `cookie_store::get_cookies()` → [cookie_store.rs:68](app/src-tauri/src/cookie_store.rs:68).

**Called by**: `load_handshake_inputs` ([lib.rs:50](app/src-tauri/src/lib.rs:50)).

---

### `pub(crate) fn migrate_cookies_from_file(cookies_path: &Path) -> Option<String>`  *(lib.rs:112)*

**Purpose**: One-shot file→keyring→delete migration for `cookies.txt`. Shared by startup and the on-demand `migrate_cookies_now` command.

**Contract**:
- Params: path to `cookies.txt`.
- Returns: `Some(extracted)` — the cookie pairs joined with `"; "` — if a real cookie pair was found (even when the keyring write failed, so the session still works). `None` if the file is missing, larger than `COOKIES_MAX_BYTES` (64 KiB), unreadable, template-only / comment-only, or the extraction is empty.
- Side effects:
  - `metadata` + `read_to_string` on the file.
  - `cookie_store::set_cookies(&extracted)` — only the extracted pairs, not the raw file (the template's comment header alone would exceed Windows Credential Manager's ~2.5 KiB blob cap).
  - On keyring success: best-effort `remove_file(cookies_path)`; a delete failure leaves the file for idempotent re-migration next time.
  - On keyring failure: file is left in place.
  - stderr lines: oversized refusal, keyring write failure (`...falling back to file`), file-delete failure.
- Errors: never returns an error variant.
- Async: no.

**Calls**:
- `std::fs::metadata`, `std::fs::read_to_string`, `std::fs::remove_file`.
- `cookie_store::file_has_real_cookies` → [cookie_store.rs:107](app/src-tauri/src/cookie_store.rs:107).
- `cookie_store::extract_cookie_lines` → [cookie_store.rs:131](app/src-tauri/src/cookie_store.rs:131).
- `cookie_store::set_cookies` → [cookie_store.rs:57](app/src-tauri/src/cookie_store.rs:57).

**Called by**:
- `load_cookies` ([lib.rs:87](app/src-tauri/src/lib.rs:87)).
- `commands::migrate_cookies_now` ([commands.rs:1079](app/src-tauri/src/commands.rs:1079)).
- Tests at [lib.rs:315](app/src-tauri/src/lib.rs:315), [lib.rs:336](app/src-tauri/src/lib.rs:336), [lib.rs:350](app/src-tauri/src/lib.rs:350), [commands.rs:1763](app/src-tauri/src/commands.rs:1763), [commands.rs:1814](app/src-tauri/src/commands.rs:1814), [commands.rs:1849](app/src-tauri/src/commands.rs:1849), [commands.rs:2096](app/src-tauri/src/commands.rs:2096).

---

### `fn migrate_legacy_token(path_manager: &PathManager, settings_value: &Value) -> Option<String>`  *(lib.rs:177)*

**Purpose**: One-shot M4→M5 migration. Pulls `settings.rd.api_token` (legacy plaintext) into the credential store, then scrubs the JSON file.

**Contract**:
- Params:
  - `path_manager` — borrowed; uses `data_dir` to locate `settings.json`.
  - `settings_value` — the `"settings"` JSON value as read from the store wrapper.
- Returns: `Some(token)` if a non-empty token that passes `secret_store::is_valid_rd_token` was found (caller hands it to the sidecar so the first handshake still works). `None` if there was nothing to migrate **or** the legacy value is malformed.
- Side effects:
  - Malformed value (fails `is_valid_rd_token`): prints to stderr ([lib.rs:186](app/src-tauri/src/lib.rs:186)) and touches nothing — the plaintext field stays so the user can see/fix it, and it never reaches the keyring or the handshake (F-04).
  - Writes the keyring (`secret_store::set_rd_token`).
  - Rewrites `<data_dir>/settings.json` with the `rd.api_token` field blanked. Best-effort: any read/parse/write failure leaves the file alone.
  - Prints to **stderr** (not the app log) on keyring write failure ([lib.rs:195](app/src-tauri/src/lib.rs:195)).
- Errors: only stderr; never returns an error variant. If keyring write fails, returns `Some(token)` anyway (plaintext left in place) so the in-memory copy is still usable for this run.
- Async: no.
- Authorization: none beyond having `path_manager`.

**Calls**:
- `secret_store::is_valid_rd_token(&token)` → [secret_store.rs:43](app/src-tauri/src/secret_store.rs:43).
- `secret_store::set_rd_token(&token)` → [secret_store.rs:62](app/src-tauri/src/secret_store.rs:62).
- `std::fs::read_to_string` / `serde_json::from_str` / `serde_json::to_string_pretty` / `std::fs::write` on `settings.json`.
- `eprintln!` for the invalid-format and keyring-failure paths.

**Called by**:
- `load_handshake_inputs` ([lib.rs:62](app/src-tauri/src/lib.rs:62)).
- Tests at [lib.rs:279](app/src-tauri/src/lib.rs:279), [lib.rs:305](app/src-tauri/src/lib.rs:305).

---

### Tests — [lib.rs:223-382](app/src-tauri/src/lib.rs:223)

- `temp_data_dir()` — builds a throwaway `PathManager`; `write_wrapper()` — writes a settings wrapper with a given `rd.api_token`.
- `migrate_legacy_token_skips_invalid_value_and_keeps_settings_intact`.
- `migrate_legacy_token_no_token_returns_none_without_modifying_settings`.
- `migrate_cookies_no_file_returns_none`.
- `migrate_cookies_template_only_file_is_not_migrated`.
- `migrate_cookies_refuses_oversized_file`.
- `load_handshake_inputs_never_hands_rd_api_token_to_sidecar` — drives `load_handshake_inputs` itself with a malformed legacy token on disk: the returned settings carry `rd.api_token = ""` while the on-disk value stays. The token is malformed on purpose so `migrate_legacy_token` never writes the keyring (the test only reads the credential store).

---

### `pub fn run()`  *(lib.rs:385)*

**Purpose**: Build and run the Tauri application.

**Contract**:
- Params: none.
- Returns: never returns normally; `.expect(...)` panics on Tauri runtime error.
- Side effects: spawns the WebView, registers four plugins (store, shell, clipboard-manager, dialog), spawns the sidecar process via `block_on`, manages two pieces of state, registers 31 commands.
- Errors: the setup closure returns `Result<(), Box<dyn Error>>`. Errors there cause `Builder::run` to fail and the `.expect` to panic ([lib.rs:455](app/src-tauri/src/lib.rs:455)).
- Async: no (uses `block_on` to drive sidecar handshake during synchronous setup).
- Authorization: this IS the bootstrap.

**Calls**:
- `tauri::Builder::default()` + `.plugin(...)` x4.
- `PathManager::new(app.handle())` → [path_manager.rs:24](app/src-tauri/src/path_manager.rs:24) (or [path_manager.rs:38](app/src-tauri/src/path_manager.rs:38) on non-Windows).
- `path_manager.ensure_dirs()` → [path_manager.rs:45](app/src-tauri/src/path_manager.rs:45).
- `load_handshake_inputs(&path_manager)` → [lib.rs:49](app/src-tauri/src/lib.rs:49).
- `app.manage(path_manager)` / `app.manage(manager)`.
- `tauri::async_runtime::block_on(SidecarManager::spawn_and_handshake(...))` → [sidecar_manager.rs:205](app/src-tauri/src/sidecar_manager.rs:205).
- `tauri::generate_handler![...]` — macro registers the command vec.
- `tauri::generate_context!()` — macro for build-time embedding.

**Called by**:
- `main()` ([main.rs:5](app/src-tauri/src/main.rs:5)).
- Mobile entry point (`tauri::mobile_entry_point`) for mobile builds ([lib.rs:384](app/src-tauri/src/lib.rs:384)).

---

## 3.4 `commands.rs`

### `pub async fn sidecar_ping(sidecar: State<'_, SidecarManager>) -> Result<Value, String>`  *(commands.rs:31)*

**Purpose**: Health-check the sidecar.

**Contract**:
- Params: `sidecar` — managed state handle to the daemon.
- Returns: raw JSON `Value` from the sidecar's `ping` reply (no `ok` check in Rust). The frontend treats truthy `ok` as healthy.
- Side effects: one JSON-line over the sidecar stdin/stdout; serialized through the sidecar mutex.
- Errors: any sidecar transport error bubbles up as `Err(String)`.
- Async: yes; blocks on the sidecar's mutex.
- Authorization: requires sidecar managed state (i.e. setup completed).

**Calls**:
- `sidecar.request("ping", Value::Null)` → [sidecar_manager.rs:271](app/src-tauri/src/sidecar_manager.rs:271).

**Called by**: frontend (Tauri invoke).

---

### `pub async fn fetch_javdb(sidecar, url, batch_id) -> Result<Value, String>`  *(commands.rs:36)*

**Purpose**: Trigger the sidecar's JavDB page scrape for a given URL; return the `result` payload (already redacted by the sidecar).

**Contract**:
- Params:
  - `sidecar` — managed state.
  - `url` — JavDB page URL. No client-side validation; sidecar enforces the JavDB origin policy.
  - `batch_id` — required frontend scrape-batch id, forwarded as `batch_id`. All URLs/retries
    in one visible batch share it; a later batch uses a fresh id. The sidecar rejects a
    non-string, an empty id, or one longer than 128 characters (`MAX_SCRAPE_BATCH_ID_LEN`).
- Returns: the `result` JSON value from the response. `Value::Null` if missing.
- Side effects: sidecar RPC + whatever HTTP/cookie work the sidecar performs (out of scope here).
- Errors: returns `Err(String)` containing either the sidecar's `error.message` (or `"unknown error"` when absent) ([commands.rs:44-50](app/src-tauri/src/commands.rs:44)) or a transport error. Note: unlike most commands this surfaces `error.message`, not `error.code`.
- Async: yes; serialized through sidecar mutex.
- Authorization: requires the sidecar to have been handshake'd (it was, by `run()`).

**Calls**:
- `sidecar.request("fetch_javdb", json!({"url": url, "batch_id": batch_id}))`.

**Called by**: frontend.

---

### `pub async fn copy_magnet(app: AppHandle, sidecar: State<'_, SidecarManager>, handle_id: String) -> Result<(), String>`  *(commands.rs:56)*

**Purpose**: Resolve a previously-redacted handle into its full magnet URI and write it to the OS clipboard. Magnet text never crosses back into the frontend.

**Contract**:
- Params:
  - `app` — AppHandle for clipboard access.
  - `sidecar` — managed state.
  - `handle_id` — the per-row id returned earlier by `fetch_javdb` or `register_magnets`.
- Returns: `Ok(())` after the clipboard write completes; magnet text is dropped immediately ([commands.rs:73-74](app/src-tauri/src/commands.rs:73)).
- Side effects: sidecar RPC; one OS clipboard write.
- Errors:
  - `Err(error.code)` from the sidecar via `ensure_ok` (e.g. `unknown_handle`).
  - `Err("response missing magnet field")` if response shape is malformed.
  - `Err(<clipboard error>)` if `ClipboardExt::write_text` fails.
- Async: yes.
- Authorization: requires sidecar.

**Calls**:
- `sidecar.request("resolve_magnet", ...)` → [sidecar_manager.rs:271](app/src-tauri/src/sidecar_manager.rs:271).
- `ensure_ok(&resp)` → [commands.rs:274](app/src-tauri/src/commands.rs:274).
- `app.clipboard().write_text(magnet)` → tauri-plugin-clipboard-manager.

**Called by**: frontend.

---

### `pub struct CopyBulkResult { copied: usize, unknown: usize }`  *(commands.rs:79)*

DTO. Serialized to frontend.

---

### `pub struct RegisteredMagnet { handle_id, magnet_redacted, name, deduped }`  *(commands.rs:85)*

DTO. `name` is the magnet's `dn=` parameter (empty when missing). `deduped` flags inputs the sidecar collapsed onto an existing handle. Both `#[serde(default)]`.

---

### `pub struct RegisterMagnetsResult { registered: Vec<RegisteredMagnet>, invalid: Vec<String> }`  *(commands.rs:100)*

DTO.

---

### `pub async fn register_magnets(sidecar: State<'_, SidecarManager>, magnets: Vec<String>) -> Result<RegisterMagnetsResult, String>`  *(commands.rs:113)*

**Purpose**: Register raw user-pasted magnet URIs into the sidecar's handle table so the paste-magnet → RD path can use the same `handle_id` workflow as scrape results.

**Contract**:
- Params:
  - `sidecar` — managed state.
  - `magnets` — raw input strings. Anything not starting with `magnet:` is filtered into the `invalid` field by the sidecar.
- Returns: registered handles (redacted) + invalid raw strings. Missing `registered` / `invalid` fields default to `[]`.
- Side effects: sidecar handle-table mutation. **Full magnet text crosses IPC inbound only** (the comment at [commands.rs:110-111](app/src-tauri/src/commands.rs:110) is explicit).
- Errors:
  - `Err(code)` from sidecar via `ensure_ok` ([commands.rs:120](app/src-tauri/src/commands.rs:120)).
  - `Err(<serde error>)` if response can't deserialize into `RegisteredMagnet` / `String` vectors.
- Async: yes.
- Authorization: requires sidecar.

**Calls**:
- `sidecar.request("register_magnets", ...)` → [sidecar_manager.rs:271](app/src-tauri/src/sidecar_manager.rs:271).
- `ensure_ok(&resp)` → [commands.rs:274](app/src-tauri/src/commands.rs:274).
- `serde_json::from_value` twice (`Vec<RegisteredMagnet>`, `Vec<String>`).

**Called by**: frontend (paste-magnet flow).

---

### `pub async fn forget_magnets(sidecar: State<'_, SidecarManager>, handle_ids: Option<Vec<String>>) -> Result<u64, String>`  *(commands.rs:141)*

**Purpose**: Drop sidecar handle-table entries. `None` = forget all (sent as a `null` body).

**Contract**:
- Params: `handle_ids` — list of ids or `None` for "all".
- Returns: number of handles dropped. Compatible with two field names: `forgot` or `forgotten` ([commands.rs:152-153](app/src-tauri/src/commands.rs:152)); the sidecar currently replies with `forgot`. Missing → `0`.
- Errors: transport errors propagate; calls `ensure_ok` so sidecar error envelopes propagate as `Err(code)`.
- Async: yes.
- Authorization: requires sidecar.

**Calls**: `sidecar.request("forget_magnets", payload)` → [sidecar_manager.rs:271](app/src-tauri/src/sidecar_manager.rs:271); `ensure_ok`.

**Called by**: frontend (clearing the result tree / unchecking all rows).

---

### `pub async fn copy_magnets_bulk(app: AppHandle, sidecar: State<'_, SidecarManager>, handle_ids: Vec<String>) -> Result<CopyBulkResult, String>`  *(commands.rs:159)*

**Purpose**: Batch version of `copy_magnet` — newline-joined magnets to the OS clipboard, count of unknown ids.

**Contract**:
- Params: list of handle ids.
- Returns: `{copied, unknown}` counts. `unknown` = sidecar's `unknown` array length **plus** resolved entries whose `magnet` is missing / non-string / whitespace-only. No resolvable magnets → clipboard write skipped ([commands.rs:170](app/src-tauri/src/commands.rs:170)).
- Side effects: sidecar RPC + one clipboard write (skipped on empty).
- Errors: `Err(error.code)` via `ensure_ok` for a non-ok response, or transport / clipboard errors.
- Async: yes.

**Calls**:
- `sidecar.request("resolve_magnets", ...)`.
- `resolved_magnets_from_response(&resp)` → [commands.rs:181](app/src-tauri/src/commands.rs:181).
- `app.clipboard().write_text(joined)`.

**Called by**: frontend.

---

### `fn resolved_magnets_from_response(resp: &Value) -> Result<(Vec<String>, usize), String>`  *(commands.rs:181)*

**Purpose**: Pure parser for the `resolve_magnets` reply: `ensure_ok`, then collect each `magnets[].magnet` string (non-blank) and count `unknown.len() + malformed`.

**Calls**: `ensure_ok`.

**Called by**: `copy_magnets_bulk` ([commands.rs:167](app/src-tauri/src/commands.rs:167)); tests at [commands.rs:1435](app/src-tauri/src/commands.rs:1435), [commands.rs:1449](app/src-tauri/src/commands.rs:1449).

---

### `pub struct CopyRdLinksBulkResult { copied: usize }`  *(commands.rs:212)*

DTO.

---

### `pub async fn copy_rd_links_bulk(app: AppHandle, links: Vec<String>) -> Result<CopyRdLinksBulkResult, String>`  *(commands.rs:226)*

**Purpose**: Write a batch of RD direct-download links to the OS clipboard. Mirrors `copy_magnets_bulk` so frontend doesn't import the clipboard plugin directly.

**Contract**:
- Params: list of strings; each is trimmed and empty results are silently dropped.
- Returns: post-filter `copied` count. `copied = 0` for empty/all-whitespace input — no error.
- Side effects: at most one clipboard write. Links are not logged.
- Errors: clipboard write error → `Err(String)`.
- Async: yes — but does NOT require sidecar state.

**Calls**: `app.clipboard().write_text(joined)`.

**Called by**: frontend.

---

### `fn _err_code(resp: &Value) -> String`  *(commands.rs:262)*

**Purpose**: Extract `resp.error.code` from a sidecar response, defaulting to `"unknown"`.

**Contract**:
- Params: borrowed JSON value (typically a non-`ok` sidecar response).
- Returns: owned `String` of the error code.
- Side effects: none.
- Errors: never errors; always returns a string.
- Async: no.

**Calls**: only `Value::get` / `as_str` chains.

**Called by**:
- `ensure_ok` ([commands.rs:278](app/src-tauri/src/commands.rs:278)).
- `settings_push_warning` ([commands.rs:762](app/src-tauri/src/commands.rs:762)).
- `import_rd_token` ([commands.rs:824](app/src-tauri/src/commands.rs:824)).

---

### `fn ensure_ok(resp: &Value) -> Result<(), String>`  *(commands.rs:274)*

**Purpose**: Guard for the standard `{"ok": bool, ...}` sidecar response. `Ok(())` when `ok == true`, else `Err(_err_code(resp))`.

**Called by**:
- `copy_magnet` ([commands.rs:64](app/src-tauri/src/commands.rs:64))
- `register_magnets` ([commands.rs:120](app/src-tauri/src/commands.rs:120))
- `forget_magnets` ([commands.rs:150](app/src-tauri/src/commands.rs:150))
- `resolved_magnets_from_response` ([commands.rs:182](app/src-tauri/src/commands.rs:182))
- `rd_test_token_with` ([commands.rs:343](app/src-tauri/src/commands.rs:343))
- `rd_save_token` ([commands.rs:370](app/src-tauri/src/commands.rs:370))
- `rd_clear_token` ([commands.rs:382](app/src-tauri/src/commands.rs:382))
- `rd_check_user` ([commands.rs:392](app/src-tauri/src/commands.rs:392))
- `rd_send_magnet` ([commands.rs:463](app/src-tauri/src/commands.rs:463))
- `rd_check_pending` ([commands.rs:549](app/src-tauri/src/commands.rs:549))
- `push_cookies_to_sidecar` ([commands.rs:1152](app/src-tauri/src/commands.rs:1152))
- `update_sidecar_settings` ([commands.rs:1268](app/src-tauri/src/commands.rs:1268))

---

### `fn str_field(resp: &Value, key: &str) -> String`  *(commands.rs:285)*

Read a string field off a sidecar response, `""` when missing or not a string. Used by `rd_send_magnet` and `rd_check_pending`.

---

### `pub struct RdUserInfo { username, type, expiration, points }`  *(commands.rs:290)*

DTO. `#[serde(rename = "type")]` because `type` is a reserved keyword (field is `r#type`). All fields `#[serde(default)]`.

### `pub struct RdHasTokenResult { present: bool }`  *(commands.rs:302)*

DTO.

---

### `pub async fn rd_has_token() -> Result<RdHasTokenResult, String>`  *(commands.rs:307)*

**Purpose**: Tell the frontend whether a token is saved (without revealing it).

**Contract**:
- Params: none. Notably does **not** take `State<SidecarManager>` — purely a keyring read.
- Returns: `{present: bool}` (`true` for any `Some`, including an empty string).
- Side effects: one keyring read.
- Errors: `Err(<keyring error string>)` if the credential store can't be queried.
- Async: yes (signature requires it for Tauri; body is sync).

**Calls**: `secret_store::get_rd_token()` → [secret_store.rs:74](app/src-tauri/src/secret_store.rs:74).

**Called by**: frontend.

---

### `fn check_candidate_token(token: &str) -> Result<(), String>`  *(commands.rs:316)*

**Purpose**: Gate a "test connection" candidate before it reaches the sidecar. Same format rule as every credential-store write path (F-04): a value that cannot be a token would otherwise go into an HTTP header and come back as an opaque internal error instead of a format message.

**Contract**:
- Params: borrowed candidate token.
- Returns: `Ok(())` for a non-empty token passing `secret_store::is_valid_rd_token`.
- Side effects: none.
- Errors: `Err("rd_no_token")` for `""`; `Err(RD_TOKEN_FORMAT_ERR)` (`"rd_token_format_invalid"`) for anything else that fails `is_valid_rd_token`.
- Async: no.

**Calls**: `secret_store::is_valid_rd_token` → [secret_store.rs:43](app/src-tauri/src/secret_store.rs:43).

**Called by**: `rd_test_token_with` ([commands.rs:339](app/src-tauri/src/commands.rs:339)), test `check_candidate_token_rejects_before_the_sidecar_sees_it`.

---

### `pub async fn rd_test_token(sidecar: State<'_, SidecarManager>, token: String) -> Result<RdUserInfo, String>`  *(commands.rs:329)*

**Purpose**: Validate a candidate token by calling RD `/user` via the sidecar, without persisting.

**Contract**:
- Params:
  - `token` — candidate. The command only delegates to the private `rd_test_token_with(&SidecarManager, token)` (so tests can drive the body with `SidecarManager::dead_for_tests`). Pre-checked by `check_candidate_token`: empty short-circuits to `Err("rd_no_token")`; anything failing `secret_store::is_valid_rd_token` short-circuits to `Err(RD_TOKEN_FORMAT_ERR)` before the sidecar is called (same F-04 rule as the write paths; the sidecar's `cmd_rd_user` enforces it again).
- Returns: account info from RD (`resp.user`).
- Side effects: sidecar RPC; sidecar performs HTTP to real-debrid.com. Token does NOT touch the keyring.
- Errors:
  - `Err("rd_no_token")` for empty input.
  - `Err("rd_token_format_invalid")` for a malformed candidate — no RPC is sent.
  - `Err(<code>)` via `ensure_ok` for non-ok response.
  - `Err(<serde error>)` if user shape can't deserialize.
- Async: yes.
- Authorization: requires sidecar.

**Calls**:
- `rd_test_token_with(&sidecar, token)` → [commands.rs:338](app/src-tauri/src/commands.rs:338).

**Called by**: frontend (settings dialog).

---

### `async fn rd_test_token_with(sidecar: &SidecarManager, token: String) -> Result<RdUserInfo, String>`  *(commands.rs:338)*

**Purpose**: Body of `rd_test_token`, taking the manager directly so tests can drive it with `SidecarManager::dead_for_tests`. Contract as `rd_test_token` above.

**Calls**:
- `check_candidate_token(&token)` → [commands.rs:316](app/src-tauri/src/commands.rs:316).
- `sidecar.request("rd_user", json!({"token": token}))`.
- `ensure_ok`, `serde_json::from_value`.

**Called by**: `rd_test_token` ([commands.rs:333](app/src-tauri/src/commands.rs:333)), test `rd_test_token_refuses_malformed_token_before_any_request`.

---

### `pub async fn rd_save_token(sidecar: State<'_, SidecarManager>, token: String) -> Result<(), String>`  *(commands.rs:356)*

**Purpose**: Persist a token to the credential store AND push it to the running sidecar.

**Contract**:
- Params: `token` — non-empty values must pass `secret_store::is_valid_rd_token` (≤255 ASCII alphanumeric); empty string is treated by `secret_store::set_rd_token` as "delete" ([secret_store.rs:67-68](app/src-tauri/src/secret_store.rs:67)); the sidecar push uses `Value::Null` in that case.
- Returns: `Ok(())`. Local `token` string drops at end of fn.
- Side effects:
  - Keyring write (or delete if empty).
  - Sidecar `rd_set_token` RPC.
- Errors:
  - `Err("rd_token_format_invalid")` (`RD_TOKEN_FORMAT_ERR`) for a malformed non-empty token — checked before the keyring or sidecar are touched.
  - `Err(<keyring error>)` from `set_rd_token`.
  - `Err(<code>)` if sidecar returns non-ok (keyring has already been written by then).
- Async: yes.
- Authorization: requires sidecar.

**Calls**:
- `secret_store::is_valid_rd_token(&token)` → [secret_store.rs:43](app/src-tauri/src/secret_store.rs:43).
- `secret_store::set_rd_token(&token)` → [secret_store.rs:62](app/src-tauri/src/secret_store.rs:62).
- `sidecar.request("rd_set_token", payload)`.
- `ensure_ok`.

**Called by**: frontend (settings save).

---

### `pub async fn rd_clear_token(sidecar: State<'_, SidecarManager>) -> Result<(), String>`  *(commands.rs:377)*

**Purpose**: Delete token from credential store and tell the sidecar to forget it.

**Contract**:
- Params: only sidecar state.
- Returns: `Ok(())`.
- Side effects: keyring delete; sidecar `rd_set_token: null` RPC.
- Errors: from either step.
- Async: yes.
- Authorization: requires sidecar.

**Calls**:
- `secret_store::delete_rd_token()` → [secret_store.rs:83](app/src-tauri/src/secret_store.rs:83).
- `sidecar.request("rd_set_token", json!({"token": null}))`.
- `ensure_ok`.

**Called by**: frontend.

---

### `pub async fn rd_check_user(sidecar: State<'_, SidecarManager>) -> Result<RdUserInfo, String>`  *(commands.rs:390)*

**Purpose**: Refresh account info using the **sidecar's current** token (no token argument). Separate from `rd_test_token` so the secret never crosses IPC just to refresh.

**Contract**:
- Params: only sidecar state.
- Returns: `RdUserInfo`.
- Side effects: sidecar RPC; sidecar HTTP to RD.
- Errors: `Err(<code>)` via `ensure_ok` or `Err(<serde error>)`.
- Async: yes.
- Authorization: requires sidecar AND the sidecar must have a token (otherwise it returns a code like `rd_no_token`).

**Calls**:
- `sidecar.request("rd_user", Value::Null)`.
- `ensure_ok`, `serde_json::from_value`.

**Called by**: frontend.

---

### `pub struct RdSendOptions { strategy, min_size_mb, cache_wait, code, size_label }`  *(commands.rs:399)*

DTO (`Default`, `Deserialize`). All fields `Option`. `code` and `size_label` are display-only — passed through so a `Pending` outcome can be persisted with the same labels the UI is showing.

### `pub struct RdLink { original, download, filename, filesize, streamable, error }`  *(commands.rs:410)*

DTO mirroring RD's unrestrict link response. `filesize` / `streamable` default to `0`; `error: Option<String>` defaults to `None` and is omitted when serializing if `None` (per-link unrestrict failure).

### `pub enum RdSendOutcome { Completed{...}, Pending{...} }`  *(commands.rs:424)*

`#[serde(tag = "status", rename_all = "snake_case")]` — frontend gets a discriminated union with `status: "completed" | "pending"`.

---

### `pub async fn rd_send_magnet(sidecar, path_manager, handle_id, options) -> Result<RdSendOutcome, String>`  *(commands.rs:443)*

**Purpose**: Send a magnet (by handle_id) to RD. Returns either the unrestricted links (cache hit) or a Pending entry that's also persisted to disk.

**Contract**:
- Params:
  - `sidecar`, `path_manager` — managed state.
  - `handle_id` — sidecar handle.
  - `options` — optional `RdSendOptions`. Defaults to all-None. Only `strategy`, `min_size_mb`, `cache_wait` are forwarded (when `Some`).
- Returns:
  - `Completed { torrent_id, name, links }` — RD returned unrestricted links immediately.
  - `Pending { torrent_id, name, rd_status, progress }` — any other `status`; entry was persisted via `pending::add` with `strategy` taken from `resp.strategy` (default `"smart"`) and `code` / `size_label` from `options`.
- Side effects:
  - `SidecarManager::request` first validates `cache_wait` (`timeout_for`); out-of-range values are rejected **before** anything is sent to the sidecar.
  - Sidecar RPC (`rd_send_magnet`), which internally calls RD's API. Request budget is `cache_wait` (default 15) + 90 s.
  - On Pending path: writes `<data_dir>/pending_torrents.json` atomically via `pending::add`.
- Errors: `Err("rd_send_magnet: cache_wait=<n> below floor 5s" | "... above ceiling 300s")` from `timeout_for`; `Err(<code>)` via `ensure_ok`; `Err(<serde error>)` for links deserialization; `Err(<pending::add error>)` from disk write.
- Async: yes.
- Authorization: requires sidecar.

**Calls**:
- `sidecar.request("rd_send_magnet", payload)`.
- `ensure_ok`, `str_field`.
- `serde_json::from_value::<Vec<RdLink>>` (for `Completed`).
- `PendingEntry::new(...)` → [pending.rs:66](app/src-tauri/src/pending.rs:66).
- `pending::add(&path_manager.data_dir, entry)` → [pending.rs:133](app/src-tauri/src/pending.rs:133).

**Called by**: frontend (the "send" action, `lib/rdSender.ts`).

---

### `pub enum RdCheckOutcome { Completed, Pending, Missing }`  *(commands.rs:517)*

Three-variant tag union for the retry-poll command (`status: "completed" | "pending" | "missing"`).

---

### `pub async fn rd_check_pending(sidecar, path_manager, torrent_id, strategy) -> Result<RdCheckOutcome, String>`  *(commands.rs:538)*

**Purpose**: Re-poll a previously-pending torrent. **Always mutates** pending_torrents.json based on outcome:
- `completed` → entry removed.
- `missing` → entry removed.
- anything else (treated as `pending`) → entry's `last_progress` / `last_rd_status` / `last_checked_at` refreshed.

**Contract**:
- Params:
  - `torrent_id`, optional `strategy` override.
- Returns: one of the three variants.
- Side effects: sidecar RPC + at least one disk read; one disk write if state changes. On `completed` the entry is removed **before** links are deserialized.
- Errors: `Err(<code>)` via `ensure_ok`, or disk / serde errors from pending I/O.
- Async: yes.
- Authorization: requires sidecar.

**Calls**:
- `sidecar.request("rd_check_pending", payload)`.
- `ensure_ok`, `str_field`.
- `pending::remove(&path_manager.data_dir, &torrent_id)` → [pending.rs:143](app/src-tauri/src/pending.rs:143).
- `pending::update_status(&data_dir, &torrent_id, &rd_status, progress)` → [pending.rs:152](app/src-tauri/src/pending.rs:152).
- `serde_json::from_value::<Vec<RdLink>>`.

**Called by**: frontend (the "retry" loop and manual poll, `lib/rdSender.ts`).

---

### `pub async fn pending_list(path_manager: State<'_, PathManager>) -> Result<Vec<PendingEntry>, String>`  *(commands.rs:587)*

**Purpose**: Return the full pending list.

**Contract**: Pure pass-through to `pending::load`.
- Side effects: one disk read.
- Errors: from `pending::load`.
- Async: yes (Tauri sig requirement).
- Authorization: requires path_manager only.

**Calls**: `pending::load(&path_manager.data_dir)` → [pending.rs:92](app/src-tauri/src/pending.rs:92).

**Called by**: frontend (initial render + after retries).

---

### `pub async fn pending_remove(path_manager, torrent_id) -> Result<Vec<PendingEntry>, String>`  *(commands.rs:594)*

**Purpose**: Drop one entry; return the new list.

**Calls**: `pending::remove(&path_manager.data_dir, &torrent_id)` → [pending.rs:143](app/src-tauri/src/pending.rs:143).

**Called by**: frontend (manual delete).

---

### `pub async fn pending_clear(path_manager: State<'_, PathManager>) -> Result<(), String>`  *(commands.rs:602)*

**Purpose**: Wipe pending_torrents.json (writes an empty array).

**Calls**: `pending::clear(&path_manager.data_dir)` → [pending.rs:169](app/src-tauri/src/pending.rs:169).

**Called by**: frontend.

---

### `pub fn get_legacy_default_dir() -> String`  *(commands.rs:620)*

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

### `pub fn preview_legacy_import(source_dir: String) -> Result<LegacyImportPreview, String>`  *(commands.rs:625)*

**Purpose**: Inspect a candidate legacy directory and report what's importable. Pure preview — no mutation.

**Contract**:
- Params: `source_dir` — user-typed path; trimmed.
- Returns: `LegacyImportPreview` with presence flags, key names, and warnings. NEVER echoes secret values.
- Side effects: file reads only.
- Errors: `Err("source_dir is empty")` for blank input.
- Async: no.
- Authorization: none.

**Calls**: `legacy_import::preview(Path::new(trimmed))` → [legacy_import.rs:347](app/src-tauri/src/legacy_import.rs:347).

**Called by**: frontend (preview button).

---

### `pub async fn apply_legacy_import(app, path_manager, sidecar, source_dir) -> Result<LegacyImportReport, String>`  *(commands.rs:634)*

**Purpose**: The actual M7a-lite import. Side-effect orchestrator over `.env`, `cookies.txt`, and `pending_torrents.json` from `source_dir`, delegating each block to a private helper.

**Contract**:
- Params:
  - `source_dir` — user-provided path. Refuses empty / non-directory / same as `data_dir` (`validate_legacy_source`).
- Returns: `LegacyImportReport` (counts + warnings + source-file list). `preview.warnings` are copied in first. Each step is best-effort — a failure in one section adds a warning but doesn't abort the others.
- Side effects:
  - For `.env` (`import_env_block`):
    - RD token → validated by `validate_legacy_rd_token`; a malformed value only adds a warning (keyring and sidecar untouched). Valid → `secret_store::set_rd_token` + sidecar `rd_set_token`.
    - Non-secret settings → merge into the tauri-plugin-store `settings.json`, blank `rd.api_token` belt-and-suspenders, then round-trip through `Settings` + `clamp_rd_settings` so out-of-range numerics land clamped ([commands.rs:848-861](app/src-tauri/src/commands.rs:848)). After a successful save, `push_imported_settings` sends the saved (clamped) settings to the running sidecar (`update_settings`, body from `settings_push_body`, which blanks `rd.api_token` again); a failed push becomes a `report.warnings` entry (`sidecar update_settings: …`) via `settings_push_warning`. Without this push the sidecar's in-memory settings would stay stale until the next restart.
  - For `cookies.txt` (`import_cookies_block`): file copy into `<data_dir>/cookies.txt` (refused if source and destination canonicalize to the same path). Always adds a warning instructing the user to restart for the new cookies to take effect, because the running sidecar already loaded its cookies at handshake time.
  - For `pending_torrents.json` (`import_pending_block`): read source, sanitize via `legacy_import::merge_legacy_pending`, write merged list via `pending::save`.
- Errors:
  - `Err("source_dir is empty")`, `Err("source_dir is not a directory: <path>")`, `Err("source_dir must not be the app data directory")`.
  - Otherwise: returns `Ok(report)` even on partial failures; failures are appended to `report.warnings`.
- Async: yes (sidecar RPCs for the token push and the settings push; the `.env` read runs on `spawn_blocking`).
- Authorization: requires `path_manager` and `sidecar`.

**Calls**:
- `validate_legacy_source(&source_dir, &data_dir)` → [commands.rs:662](app/src-tauri/src/commands.rs:662).
- `legacy_import::preview(&src)` → [legacy_import.rs:347](app/src-tauri/src/legacy_import.rs:347).
- `import_env_block(...)` → [commands.rs:691](app/src-tauri/src/commands.rs:691).
- `import_cookies_block(...)` → [commands.rs:888](app/src-tauri/src/commands.rs:888).
- `import_pending_block(...)` → [commands.rs:927](app/src-tauri/src/commands.rs:927).

**Called by**: frontend (apply button).

#### Private helpers of `apply_legacy_import`

- `fn validate_legacy_source(source_dir: &str, data_dir: &Path) -> Result<PathBuf, String>` *(commands.rs:662)* — trim, `is_dir`, and canonicalized `!= data_dir`.
- `async fn import_env_block(app, data_dir, sidecar, src, report)` *(commands.rs:691)* — `read_legacy_env(src)` (warning `read .env failed: …` on error), `legacy_import::parse_env` ([commands.rs:705](app/src-tauri/src/commands.rs:705)), parse warnings prefixed `.env: `, then `import_rd_token` and/or `import_env_settings_patch`; when the latter returns `Some(saved_settings)`, `push_imported_settings`. Marked `#[deny(unused_variables)]` ([commands.rs:690](app/src-tauri/src/commands.rs:690)): the body needs an `AppHandle`, so no unit test reaches it — dropping the push call leaves `saved_settings` unused, which this turns into a build error instead of a silently stale sidecar.
- `async fn read_legacy_env(src: &Path) -> Result<String, String>` *(commands.rs:727)* — reads `<src>/.env` inside `tauri::async_runtime::spawn_blocking` so a slow (user-chosen, possibly network) path does not stall an async worker; join and I/O errors both map to `Err(e.to_string())`.
- `async fn push_imported_settings(sidecar: &SidecarManager, saved_settings: Value, report)` *(commands.rs:737)* — `sidecar.request("update_settings", settings_push_body(saved_settings))` ([commands.rs:743](app/src-tauri/src/commands.rs:743)); a warning from `settings_push_warning` is appended to `report.warnings`. Never aborts the rest of the import.
- `fn settings_push_body(settings: Value) -> Value` *(commands.rs:753)* — `blank_rd_api_token` then `{"settings": settings}`. Blanks again (as `update_sidecar_settings` does) so this path cannot ship the token even if the importer's own sweep goes away.
- `fn settings_push_warning(result: Result<Value, String>) -> Option<String>` *(commands.rs:759)* — `None` for `{"ok": true}`; `Some("sidecar update_settings: <code>")` (via `_err_code`) for a non-ok reply; `Some("sidecar update_settings: <transport error>")` for `Err`.
- `pub(crate) fn validate_legacy_rd_token(token: &str) -> Result<(), String>` *(commands.rs:772)* — pure; `Err("ignored legacy RD_API_TOKEN: value does not match the Real-Debrid API token format (expected ≤255 ASCII alphanumeric chars); credential store and sidecar left untouched")` on failure.
- `async fn import_rd_token(sidecar, src, token, report)` *(commands.rs:793)* — validate → `secret_store::set_rd_token` ([commands.rs:805](app/src-tauri/src/commands.rs:805), warning `credential store: …`) → `sidecar.request("rd_set_token", …)` (warning `sidecar: …` or `sidecar rd_set_token: <code>` via `_err_code`). Sets `rd_token_imported` and pushes `<src>/.env (RD_API_TOKEN)` to `sources` only on full success.
- `fn import_env_settings_patch(app, data_dir, src, patch, report) -> Option<Value>` *(commands.rs:830)* — `app.store(data_dir.join(crate::STORE_FILE))`, `store.get("settings")` (fallback `Settings::default()`), `legacy_import::apply_settings_patch` ([commands.rs:848](app/src-tauri/src/commands.rs:848)), `blank_rd_api_token`, `clamp_rd_settings` round-trip, `store.set` + `store.save`. Sets `env_imported` and returns `Some(saved settings)` on success; returns `None` with warning `settings store: …` / `settings save: …` on failure.
- `pub(crate) fn blank_rd_api_token(settings: &mut Value)` *(commands.rs:878)* — sets `rd.api_token = ""` if the field exists. Also used by `settings_push_body`, `update_sidecar_settings`, and `lib::load_handshake_inputs` ([lib.rs:64](app/src-tauri/src/lib.rs:64)).
- `fn import_cookies_block(data_dir, src, report)` *(commands.rs:888)* — `create_dir_all`, same-path guard, `std::fs::copy`; sets `cookies_imported`.
- `fn import_pending_block(data_dir, src, report)` *(commands.rs:927)* — `read_to_string`, `pending::load` ([commands.rs:936](app/src-tauri/src/commands.rs:936)), `legacy_import::merge_legacy_pending` ([commands.rs:943](app/src-tauri/src/commands.rs:943)), `pending::save` ([commands.rs:950](app/src-tauri/src/commands.rs:950)); sets `pending_imported` / `pending_skipped`.

---

### `pub struct CookiesStatus { present, path, modified_iso, size_bytes, storage }`  *(commands.rs:974)*

DTO. `modified_iso` is ISO-8601 UTC or `None` (always `None` for keyring storage). `storage` is `"none"` | `"file"` | `"keyring"`.

---

### `pub(crate) fn cookies_status_with_keyring(data_dir: &Path, in_keyring: bool) -> CookiesStatus`  *(commands.rs:1008)*

**Purpose**: Pure helper — report cookies status without reading the file body. `in_keyring` is injected so unit tests never touch the real OS keyring. Defended in test [commands.rs:1547](app/src-tauri/src/commands.rs:1547).

**Contract**:
- Params: borrowed path to the data dir; keyring presence flag.
- Returns: `CookiesStatus`. Precedence: file exists → `storage: "file"`, `present: true`, size + mtime; else `in_keyring` → `storage: "keyring"`, `present: true`, size 0; else `storage: "none"`, `present: false`. Path is always echoed (even when file missing) so the UI can show "expected at <path>".
- Side effects: one `metadata()` call.
- Errors: never errors.
- Async: no.

**Calls**: `std::fs::metadata`, `meta.modified()`, `chrono::DateTime::<Utc>::from(st).to_rfc3339()`.

**Called by**:
- `cookies_status_for` ([commands.rs:1046](app/src-tauri/src/commands.rs:1046)).
- Tests at [commands.rs:1492](app/src-tauri/src/commands.rs:1492), [commands.rs:1507](app/src-tauri/src/commands.rs:1507), [commands.rs:1523](app/src-tauri/src/commands.rs:1523), [commands.rs:1534](app/src-tauri/src/commands.rs:1534), [commands.rs:1554](app/src-tauri/src/commands.rs:1554).

---

### `pub(crate) fn cookies_status_for(data_dir: &Path) -> CookiesStatus`  *(commands.rs:1038)*

**Purpose**: Production wrapper — queries the keyring (`cookie_store::get_cookies()` returning a non-empty value; a backend error counts as "not in keyring") and delegates to `cookies_status_with_keyring`.

**Calls**: `cookie_store::get_cookies()` → [cookie_store.rs:68](app/src-tauri/src/cookie_store.rs:68), `cookies_status_with_keyring`.

**Called by**:
- `get_cookies_status` ([commands.rs:1051](app/src-tauri/src/commands.rs:1051)), `migrate_cookies_now` ([commands.rs:1082](app/src-tauri/src/commands.rs:1082)), `save_cookies` ([commands.rs:1139](app/src-tauri/src/commands.rs:1139)), `clear_cookies` ([commands.rs:1211](app/src-tauri/src/commands.rs:1211)).
- `tests_cookies_e2e` tests (e.g. [commands.rs:1869](app/src-tauri/src/commands.rs:1869)).

---

### `pub fn get_cookies_status(path_manager: State<PathManager>) -> CookiesStatus`  *(commands.rs:1050)*

**Purpose**: Tauri-command wrapper around `cookies_status_for`. Plain read — never migrates.

**Calls**: `cookies_status_for(&path_manager.data_dir)`.

**Called by**: frontend.

---

### `pub async fn migrate_cookies_now(sidecar, path_manager) -> Result<CookiesStatus, String>`  *(commands.rs:1074)*

**Purpose**: "重新整理 / 套用變更" — run the startup file→keyring→delete migration on demand and push the migrated value to the running sidecar (no restart needed).

**Contract**:
- Params: sidecar + path_manager state.
- Returns: post-migration `CookiesStatus`.
- Side effects: `migrate_cookies_from_file(<data_dir>/cookies.txt)`; if it returned `Some`, sidecar `set_cookies` RPC. Template-only / oversized / missing file → no migration, status read only.
- Errors: `Err(<code>)` / transport error from the sidecar push (the keyring write and file delete have already happened by then). Keyring-write failures inside the migration are not surfaced (the value is still pushed).
- Async: yes.
- Authorization: requires sidecar.

**Calls**: `crate::migrate_cookies_from_file` → [lib.rs:112](app/src-tauri/src/lib.rs:112), `push_cookies_to_sidecar` → [commands.rs:1145](app/src-tauri/src/commands.rs:1145), `cookies_status_for`.

**Called by**: frontend (cookies status refresh on mount and "重新整理" button).

---

### `pub(crate) fn validate_cookies_input(cookies: &str) -> Result<String, String>`  *(commands.rs:1095)*

**Purpose**: Pure validation for `save_cookies`. Returns the trimmed value, or `Err("cookies_empty")` for blank input, or `Err("cookies_too_large")` (`cookie_store::COOKIES_TOO_LARGE_ERR`) over 64 KiB.

**Calls**: `cookie_store::check_cookies_format` → [cookie_store.rs:46](app/src-tauri/src/cookie_store.rs:46).

**Called by**: `save_cookies_local` ([commands.rs:1116](app/src-tauri/src/commands.rs:1116)); tests at [commands.rs:1624](app/src-tauri/src/commands.rs:1624), [commands.rs:1637](app/src-tauri/src/commands.rs:1637), [commands.rs:1648](app/src-tauri/src/commands.rs:1648).

---

### `pub(crate) fn save_cookies_local(data_dir: &Path, cookies: &str) -> Result<String, String>`  *(commands.rs:1112)*

**Purpose**: Validate, write the keyring, then best-effort delete any stale `cookies.txt` (so the next startup doesn't re-migrate an older file over the fresh value). Returns the trimmed stored value.

**Calls**: `validate_cookies_input`, `cookie_store::set_cookies` → [cookie_store.rs:57](app/src-tauri/src/cookie_store.rs:57), `std::fs::remove_file` (errors ignored).

**Called by**: `save_cookies` ([commands.rs:1137](app/src-tauri/src/commands.rs:1137)); tests at [commands.rs:1929](app/src-tauri/src/commands.rs:1929), [commands.rs:1971](app/src-tauri/src/commands.rs:1971), [commands.rs:1988](app/src-tauri/src/commands.rs:1988).

---

### `pub async fn save_cookies(sidecar, path_manager, cookies: String) -> Result<CookiesStatus, String>`  *(commands.rs:1132)*

**Purpose**: Direct paste path: validate, write the credential store, scrub stale `cookies.txt`, push to the running sidecar.

**Contract**:
- Params: `cookies` — `Cookie:`-header-style string from the UI.
- Returns: post-save `CookiesStatus` (expected `storage: "keyring"`).
- Side effects: keyring write; possible file delete; sidecar `set_cookies` RPC.
- Errors: `Err("cookies_empty")`, `Err("cookies_too_large")`, keyring errors, or sidecar `Err(<code>)` / transport error (keyring already written by then). Empty input is never a clear — `clear_cookies` is the explicit gesture.
- Async: yes.
- Authorization: requires sidecar.

**Calls**: `save_cookies_local`, `push_cookies_to_sidecar`, `cookies_status_for`.

**Called by**: frontend.

---

### `async fn push_cookies_to_sidecar(sidecar: &SidecarManager, value: &str) -> Result<(), String>`  *(commands.rs:1145)*

**Purpose**: `sidecar.request("set_cookies", json!({"cookies": value}))` + `ensure_ok`. An empty string is the sidecar protocol's clear signal.

**Called by**: `migrate_cookies_now` ([commands.rs:1080](app/src-tauri/src/commands.rs:1080)), `save_cookies` ([commands.rs:1138](app/src-tauri/src/commands.rs:1138)), `clear_cookies` ([commands.rs:1208](app/src-tauri/src/commands.rs:1208)).

---

### `pub(crate) fn clear_cookies_local(data_dir: &Path) -> Result<(), String>`  *(commands.rs:1173)*

**Purpose**: Delete the plaintext `cookies.txt` (template scaffold included) **first**, then the keyring entry. Order is load-bearing: a surviving file would be re-migrated into the keyring by `migrate_cookies_from_file`. `NotFound` counts as success.

**Contract**:
- Errors: `Err("remove <path>: <e>")` for a non-`NotFound` delete failure (keyring left intact); keyring errors from `cookie_store::delete_cookies`.

**Calls**: `std::fs::remove_file`, `cookie_store::delete_cookies` → [cookie_store.rs:86](app/src-tauri/src/cookie_store.rs:86).

**Called by**: `clear_cookies` ([commands.rs:1207](app/src-tauri/src/commands.rs:1207)); tests at [commands.rs:2019](app/src-tauri/src/commands.rs:2019), [commands.rs:2047](app/src-tauri/src/commands.rs:2047), [commands.rs:2069](app/src-tauri/src/commands.rs:2069), [commands.rs:2094](app/src-tauri/src/commands.rs:2094).

---

### `pub async fn clear_cookies(sidecar, path_manager) -> Result<CookiesStatus, String>`  *(commands.rs:1203)*

**Purpose**: "清除 cookies" — wipe the JavDB session from the file, the OS credential store, and the running sidecar.

**Contract**:
- Returns: post-clear `CookiesStatus` (expected `storage: "none"`).
- Side effects: `clear_cookies_local`; sidecar `set_cookies` with `""`.
- Errors:
  - From `clear_cookies_local` (nothing reported as cleared).
  - Sidecar push failure → `Err("cookies_cleared_sidecar_stale: <e>")` (`CLEARED_SIDECAR_STALE` prefix): the stored cookies are already gone, only the running sidecar still holds the old session until restart. The frontend matches the prefix ([App.svelte:1396](app/src/App.svelte:1396)).
- Async: yes.
- Authorization: requires sidecar.

**Calls**: `clear_cookies_local`, `push_cookies_to_sidecar`, `cookies_status_for`.

**Called by**: frontend.

---

### `pub(crate) fn write_cookies_template_to(data_dir: &Path) -> Result<(), String>`  *(commands.rs:1232)*

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
- `create_cookies_template` ([commands.rs:1249](app/src-tauri/src/commands.rs:1249)).
- Tests at [commands.rs:1565](app/src-tauri/src/commands.rs:1565), [commands.rs:1661](app/src-tauri/src/commands.rs:1661).

---

### `pub fn create_cookies_template(path_manager: State<PathManager>) -> Result<(), String>`  *(commands.rs:1248)*

**Purpose**: Tauri-command wrapper around `write_cookies_template_to`.

**Calls**: `write_cookies_template_to(&path_manager.data_dir)`.

**Called by**: frontend ("create template" button).

---

### `pub async fn update_sidecar_settings(sidecar: State<'_, SidecarManager>, settings: Value) -> Result<(), String>`  *(commands.rs:1259)*

**Purpose**: Push the latest persisted settings to the running sidecar so changes take effect without a restart. Belt-and-suspenders blanks `rd.api_token` before sending.

**Contract**:
- Params: `settings` — raw JSON object (the frontend's current settings).
- Returns: `Ok(())`.
- Side effects: `blank_rd_api_token` on the owned value (`rd.api_token = ""` if present); sidecar RPC `update_settings` with body `{"settings": sanitized}`.
- Errors: `Err(<code>)` via `ensure_ok` if non-ok.
- Async: yes.
- Authorization: requires sidecar.

**Calls**: `blank_rd_api_token` → [commands.rs:878](app/src-tauri/src/commands.rs:878), `sidecar.request("update_settings", ...)`, `ensure_ok`.

**Called by**: frontend (settings save flow). The only other sender of sidecar `update_settings` is `push_imported_settings` (legacy `.env` import), which builds the same blanked body via `settings_push_body`.

---

### `pub fn open_data_dir(path_manager: State<PathManager>) -> Result<(), String>`  *(commands.rs:1276)*

**Purpose**: Open the data directory in the OS file manager (Windows: explorer.exe).

**Calls**: `open_in_explorer(&path_manager.data_dir)`.

**Called by**: frontend.

---

### `pub fn open_logs_dir(path_manager: State<PathManager>) -> Result<(), String>`  *(commands.rs:1281)*

**Purpose**: Same as `open_data_dir` but for the log dir.

**Calls**: `open_in_explorer(&path_manager.log_dir)`.

**Called by**: frontend.

---

### `fn open_in_explorer(p: &Path) -> Result<(), String>`  *(commands.rs:1285)*

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

### Tests

`tests_task_contracts` — [commands.rs:1311-1465](app/src-tauri/src/commands.rs:1311):
- `check_candidate_token_rejects_before_the_sidecar_sees_it` — `""` → `rd_no_token`; `abc-123`, embedded space / newline, full-width, 256 chars → `rd_token_format_invalid`.
- `settings_push_body_never_carries_the_rd_token`.
- `rd_test_token_refuses_malformed_token_before_any_request` — drives `rd_test_token_with` against `SidecarManager::dead_for_tests`: malformed / empty tokens fail with their format codes, while a well-formed one reaches the sidecar (`sidecar is dead: unit test`). Dropping the pre-check turns the first assertion into the dead-sidecar error.
- `read_legacy_env_reads_the_file_and_reports_a_missing_one`.
- `push_imported_settings_reports_a_failed_push_as_a_warning` — dead sidecar → `report.warnings == ["sidecar update_settings: sidecar is dead: unit test"]`.
- `settings_push_warning_reports_only_failures`.
- `rd_link_deserializes_completed_payload_with_error_entry`.
- `resolved_magnets_response_preserves_sidecar_error_code`.
- `resolved_magnets_counts_malformed_entries_as_unknown`.

`tests_m7b` — [commands.rs:1467-1670](app/src-tauri/src/commands.rs:1467) (no real keyring access):
- `fn temp_dir() -> PathBuf` — process-id + counter-based tempdir. Same pattern is duplicated in [lib.rs:230](app/src-tauri/src/lib.rs:230), [legacy_import.rs:457](app/src-tauri/src/legacy_import.rs:457), [pending.rs:181](app/src-tauri/src/pending.rs:181) and `tests_cookies_e2e` ([commands.rs:1736](app/src-tauri/src/commands.rs:1736)).
- `cookies_status_missing_file_and_no_keyring`, `cookies_status_missing_file_but_keyring_populated`, `cookies_status_file_overrides_keyring`, `cookies_status_present_file`.
- `cookies_status_does_not_leak_body` — defense-in-depth: serialized status never contains cookie body.
- `create_cookies_template_writes_utf8_no_bom` — checks BOM-free output and required Chinese instruction headers.
- `validate_legacy_rd_token_passes_valid_value`, `validate_legacy_rd_token_rejects_with_warning_text`, `validate_legacy_rd_token_rejects_overlong_and_non_ascii`.
- `validate_cookies_input_rejects_empty`, `validate_cookies_input_rejects_oversized`, `validate_cookies_input_trims_whitespace_around_real_value`.
- `create_cookies_template_refuses_overwrite` — original file preserved.

`tests_cookies_e2e` — [commands.rs:1688-2108](app/src-tauri/src/commands.rs:1688) (touches the **real** OS credential store; on Linux needs a usable D-Bus Secret Service):
- `keyring_lock()` (global mutex) + `KeyringSandbox` (snapshot / clear / restore the user's real cookies on `Drop`), `temp_dir()`.
- Goal 1 (startup / refresh migration): `goal_1_migration_writes_keyring_and_removes_file`, `goal_1_oversized_template_migrates_just_the_cookie_line`, `goal_1_template_only_file_leaves_keyring_untouched`.
- Goal 2 (status): `goal_2_status_reports_none_when_neither_file_nor_keyring`, `goal_2_status_reports_keyring_when_only_keyring_has_value`, `goal_2_status_reports_file_when_file_present_regardless_of_keyring`.
- Goal 3 (paste path): `goal_3_paste_path_writes_keyring_and_removes_stale_file`, `goal_3_paste_path_rejects_empty_without_touching_keyring`, `goal_3_paste_path_rejects_oversized_without_touching_keyring`.
- Clear: `clear_removes_both_the_file_and_the_keyring_entry`, `clear_succeeds_when_only_the_keyring_has_a_value`, `clear_removes_a_template_only_file_too`, `clear_sticks_across_a_restart_no_re_migration`.

---

## 3.5 `legacy_import.rs`

### `pub struct LegacyImportPreview { source_dir, source_dir_valid, env_present, cookies_present, pending_present, env_settings_keys, has_rd_token, pending_count, warnings }`  *(legacy_import.rs:36)*

DTO. Reports presence + recognized key names only — never values.

### `pub struct LegacyImportReport { env_imported, rd_token_imported, cookies_imported, pending_imported, pending_skipped, sources, warnings }`  *(legacy_import.rs:55)*

DTO. Pure tallies + diagnostic strings.

### `pub struct ParsedEnv { token, recognized_keys, settings_patch, warnings }`  *(legacy_import.rs:69)*

DTO. `token` and `settings_patch` are structurally separate — by construction `parse_env` cannot place `RD_API_TOKEN` into `settings_patch`.

---

### `pub fn parse_env(content: &str) -> ParsedEnv`  *(legacy_import.rs:94)*

**Purpose**: Parse `.env` file text. Pure function — no I/O.

**Contract**:
- Params: borrowed string content. Lines (after trim) that are blank or start with `#` are skipped.
- Returns: `ParsedEnv` with:
  - `token` — RD_API_TOKEN value (or None if empty/missing). Not format-validated here.
  - `recognized_keys` — names of keys that were successfully consumed.
  - `settings_patch` — JSON map keyed by top-level setting section (`rd`, `ui`).
  - `warnings` — strings for malformed lines (`ignored malformed line: …`), unknown keys (`ignored unknown key: …`), non-u32 numerics (`<KEY> not a u32 non-negative integer`), and the deprecated `RD_WAIT_TIMEOUT`.
- Side effects: none.
- Errors: never returns Err; bad lines/keys go to `warnings`.
- Async: no.

**Recognized keys** (routed by `dispatch_env_entry`, [legacy_import.rs:146](app/src-tauri/src/legacy_import.rs:146)):
- `RD_API_TOKEN` → `token` (never patch).
- `RD_FILE_PICK` → `settings_patch.rd.file_pick`.
- `RD_MIN_SIZE_MB` → `settings_patch.rd.min_size_mb` (u32; warning on parse fail).
- `RD_WAIT_TIMEOUT` → warning `ignored deprecated key: RD_WAIT_TIMEOUT` only; no settings patch because `cache_wait_seconds` is the only RD wait budget.
- `RD_CACHE_WAIT` → `settings_patch.rd.cache_wait_seconds` (u32; range is clamped later by the importer, not here).
- `UI_SCALE` → `settings_patch.ui.scale`.
- `UI_THEME` → `settings_patch.ui.theme`.

Empty string values for token / string keys are skipped silently. Quote stripping (`strip_matched_quotes`, [legacy_import.rs:128](app/src-tauri/src/legacy_import.rs:128)): one matched `"..."` or `'...'` pair.

**Calls**: `strip_matched_quotes`, `dispatch_env_entry` → `assign_token` / `assign_str_setting` / `assign_u32_setting` ([legacy_import.rs:169-207](app/src-tauri/src/legacy_import.rs:169)); stdlib `str::lines`, `str::split_once`, `str::parse::<u32>`, `serde_json::Map::insert`.

**Called by**:
- `read_env_for_preview` ([legacy_import.rs:315](app/src-tauri/src/legacy_import.rs:315)) ← `preview`.
- `commands::import_env_block` ([commands.rs:705](app/src-tauri/src/commands.rs:705)).
- Tests at [legacy_import.rs:474](app/src-tauri/src/legacy_import.rs:474), [legacy_import.rs:503](app/src-tauri/src/legacy_import.rs:503), [legacy_import.rs:513](app/src-tauri/src/legacy_import.rs:513), [legacy_import.rs:522](app/src-tauri/src/legacy_import.rs:522), [legacy_import.rs:536](app/src-tauri/src/legacy_import.rs:536), [legacy_import.rs:546](app/src-tauri/src/legacy_import.rs:546), [legacy_import.rs:558](app/src-tauri/src/legacy_import.rs:558).

---

### `pub fn sanitize_pending_entry(raw: &Value) -> Option<PendingEntry>`  *(legacy_import.rs:216)*

**Purpose**: Convert one raw legacy pending object into a sanitized `PendingEntry`. Strips magnet/secret-bearing fields **by construction** — only allow-listed fields survive.

**Contract**:
- Params: borrowed JSON value (one element of the legacy array).
- Returns: `Some(entry)` if `torrent_id` is a string that is non-empty after trim (stored trimmed). `None` otherwise.
- Allow-list (and aliases):
  - `torrent_id` (required).
  - `code`, `name`.
  - `size_label` ← falls back to `size`.
  - `strategy` ← defaults to `"smart"` if empty.
  - `added_at` ← defaults to `Utc::now().to_rfc3339()` if empty.
  - `last_progress` ← falls back to `progress`.
  - `last_rd_status` ← falls back to `rd_status`.
  - `last_checked_at` (Option<String>).
- Deliberately ignored (commented at [legacy_import.rs:259-260](app/src-tauri/src/legacy_import.rs:259)): `magnet`, `magnet_uri`, `full_magnet`, `magnet_url`, `magnet_text`, `files_selected`, `api_token`.
- Side effects: may call `chrono::Utc::now()` if `added_at` is empty.
- Errors: returns `None` instead of erroring.
- Async: no.

**Calls**: `Value::as_object`, `as_str`, `as_f64`; `chrono::Utc::now().to_rfc3339()`.

**Called by**:
- `merge_legacy_pending` ([legacy_import.rs:291](app/src-tauri/src/legacy_import.rs:291)).
- Tests at [legacy_import.rs:579](app/src-tauri/src/legacy_import.rs:579), [legacy_import.rs:593](app/src-tauri/src/legacy_import.rs:593).

---

### `pub fn merge_legacy_pending(legacy_raw: &str, existing: &[PendingEntry]) -> Result<(Vec<PendingEntry>, usize, usize), String>`  *(legacy_import.rs:277)*

**Purpose**: Merge legacy pending entries with the current list. Dedupes by `torrent_id` — existing entries win (legacy is never allowed to clobber state).

**Contract**:
- Params:
  - `legacy_raw` — JSON array as a string.
  - `existing` — current pending list.
- Returns: `(merged_list, imported_count, skipped_count)`.
  - `imported` = new entries added.
  - `skipped` = entries that either had no `torrent_id` (corrupt) or duplicated an existing / earlier id.
- Side effects: none.
- Errors: `Err("parse pending JSON: ...")` for invalid JSON.
- Async: no.

**Calls**:
- `serde_json::from_str::<Vec<Value>>`.
- `sanitize_pending_entry(raw)` per element.
- `HashSet<String>` for dedup.

**Called by**:
- `commands::import_pending_block` ([commands.rs:943](app/src-tauri/src/commands.rs:943)).
- Tests at [legacy_import.rs:606](app/src-tauri/src/legacy_import.rs:606), [legacy_import.rs:631](app/src-tauri/src/legacy_import.rs:631), [legacy_import.rs:641](app/src-tauri/src/legacy_import.rs:641).

---

### `pub fn preview(source_dir: &Path) -> LegacyImportPreview`  *(legacy_import.rs:347)*

**Purpose**: Inspect `source_dir` and count importable items. Reads files just enough to count entries / collect key names. **Never echoes any value** that came from `.env` / cookies.txt / a magnet.

**Contract**:
- Params: borrowed path.
- Returns: `LegacyImportPreview`. `source_dir_valid: false` (plus a warning) if not a directory. `env_settings_keys` excludes `RD_API_TOKEN` (reported via `has_rd_token`).
- Side effects: file reads (`.env`, `pending_torrents.json` if present). cookies.txt presence is checked via `is_file()` only — never read.
- Errors: never errors; everything goes to `warnings` (e.g. `pending_torrents.json is not a JSON array`).
- Async: no.

**Calls**:
- `Path::is_dir`, `Path::is_file`, `Path::join`.
- `read_env_for_preview(&env_path)` → [legacy_import.rs:312](app/src-tauri/src/legacy_import.rs:312) (`fs::read_to_string` + `parse_env`).
- `read_pending_count(&pending_path)` → [legacy_import.rs:334](app/src-tauri/src/legacy_import.rs:334) (`fs::read_to_string` + `serde_json::from_str::<Vec<Value>>`).

**Called by**:
- `commands::preview_legacy_import` ([commands.rs:630](app/src-tauri/src/commands.rs:630)).
- `commands::apply_legacy_import` ([commands.rs:643](app/src-tauri/src/commands.rs:643)).
- Tests at [legacy_import.rs:647](app/src-tauri/src/legacy_import.rs:647), [legacy_import.rs:674](app/src-tauri/src/legacy_import.rs:674).

---

### `pub fn apply_settings_patch(base: &mut Value, patch: &Map<String, Value>)`  *(legacy_import.rs:401)*

**Purpose**: Merge a settings patch into a base Settings JSON value. Defensive: never lets `rd.api_token` leak through and always blanks it as a final safety net.

**Contract**:
- Params:
  - `base` — `&mut Value` (a serialized `Settings`). No-op if not an object.
  - `patch` — typically `ParsedEnv.settings_patch`.
- Returns: `()`.
- Side effects: mutates `base` in place. Object-valued patch entries merge field-by-field (`merge_patch_entry`, [legacy_import.rs:414](app/src-tauri/src/legacy_import.rs:414)), scalar ones replace. Forces `base.rd.api_token = ""` (`clear_rd_api_token`, [legacy_import.rs:434](app/src-tauri/src/legacy_import.rs:434)) even if the patch tried to inject one (test [legacy_import.rs:694](app/src-tauri/src/legacy_import.rs:694)).
- Errors: silent no-op on non-object base.
- Async: no.

**Calls**: `merge_patch_entry`, `clear_rd_api_token`; `Value::as_object_mut`, `Map::entry`, `insert`, `or_insert_with`.

**Called by**:
- `commands::import_env_settings_patch` ([commands.rs:848](app/src-tauri/src/commands.rs:848)).
- Test at [legacy_import.rs:711](app/src-tauri/src/legacy_import.rs:711).

---

### Tests module — [legacy_import.rs:447-721](app/src-tauri/src/legacy_import.rs:447)

- `temp_dir()` — tempdir helper (duplicates the same pattern in lib, pending and commands).
- `parse_env_routes_token_outside_settings_patch` — key invariant.
- `parse_env_handles_quoted_values_and_comments`.
- `parse_env_warns_on_unknown_and_malformed`.
- `parse_env_warns_on_non_numeric_for_numeric_keys`.
- `parse_env_rejects_u32_overflow_numeric_values`.
- `parse_env_ignores_deprecated_wait_timeout`.
- `parse_env_empty_token_is_treated_as_unset`.
- `sanitize_pending_drops_magnet_fields`.
- `sanitize_pending_requires_torrent_id`.
- `merge_legacy_pending_is_idempotent_by_torrent_id`.
- `merge_legacy_pending_skips_already_existing_ids`.
- `merge_legacy_pending_rejects_corrupt_input`.
- `preview_handles_missing_source_dir`.
- `preview_reports_files_without_echoing_values`.
- `apply_settings_patch_merges_and_clears_api_token`.

Notable detail: `parse_env_routes_token_outside_settings_patch` (and two other tests) construct the literal key string from `["RD_API", "TOKEN"].join("_")` ([legacy_import.rs:472](app/src-tauri/src/legacy_import.rs:472)) — appears to be to avoid letting `RD_API_TOKEN` appear verbatim in the source for auditing tools.

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

**Called by**: `lib::run()` setup ([lib.rs:392](app/src-tauri/src/lib.rs:392)).

---

### `pub fn PathManager::new(app_handle: &AppHandle) -> Result<Self, Box<dyn std::error::Error>>` (non-Windows)  *(path_manager.rs:38)*

**Purpose**: Fallback so `cargo check` / the Linux lib test gate pass on Linux/macOS. The in-source comment still says V1 ships Windows-only.

**Contract**:
- Returns: `Ok(Self{...})` with paths from `app_handle.path().app_data_dir()` and `.app_log_dir()`.
- Errors: from Tauri's path resolution.

**Calls**: `tauri::Manager::path`, `PathResolver::app_data_dir`, `app_log_dir`.

**Called by**: `lib::run()` setup ([lib.rs:392](app/src-tauri/src/lib.rs:392)).

---

### `pub fn PathManager::ensure_dirs(&self) -> std::io::Result<()>`  *(path_manager.rs:45)*

**Purpose**: `mkdir -p` for both `data_dir` and `log_dir`.

**Contract**:
- Side effects: filesystem mutation.
- Errors: `io::Error` from `create_dir_all`.
- Async: no.

**Calls**: `std::fs::create_dir_all` twice.

**Called by**: `lib::run()` setup ([lib.rs:393](app/src-tauri/src/lib.rs:393)).

---

## 3.7 `pending.rs`

### `pub struct PendingEntry { torrent_id, code, name, size_label, strategy, added_at, last_progress, last_rd_status, last_checked_at }`  *(pending.rs:28)*

Serde-derived DTO. `#[serde(default)]` on most fields so older files round-trip cleanly (`torrent_id` and `added_at` are required). `strategy` defaults to `"smart"` via `default_strategy`. `last_checked_at: Option<String>` is the only nullable field.

---

### `fn default_strategy() -> String`  *(pending.rs:61)*

Returns `"smart"`. Trivial. Called only by serde via `#[serde(default = "default_strategy")]`.

---

### `pub fn PendingEntry::new(torrent_id, code, name, size_label, strategy) -> Self`  *(pending.rs:66)*

**Purpose**: Constructor that stamps `added_at = Utc::now().to_rfc3339()` and zeros the runtime-mutable fields.

**Contract**:
- Side effects: `chrono::Utc::now()` clock read.
- Errors: cannot fail.
- Async: no.

**Calls**: `chrono::Utc::now()`, `to_rfc3339()`.

**Called by**:
- `commands::rd_send_magnet` ([commands.rs:496](app/src-tauri/src/commands.rs:496)).
- Test `sample` at [pending.rs:190](app/src-tauri/src/pending.rs:190), [legacy_import.rs:619](app/src-tauri/src/legacy_import.rs:619).

---

### `fn pending_path(data_dir: &Path) -> PathBuf`  *(pending.rs:87)*

Trivial: `data_dir.join("pending_torrents.json")`. Called by `load`, `save`, and tests (`entries_have_no_magnet_field`, `load_rejects_oversized_file`, `load_accepts_file_just_under_limit`).

---

### `pub fn load(data_dir: &Path) -> Result<Vec<PendingEntry>, String>`  *(pending.rs:92)*

**Purpose**: Read pending list. Missing file → empty vec. Empty/whitespace file → empty vec. Files over `MAX_PENDING_FILE_BYTES` (4 MiB) are refused before reading.

**Contract**:
- Returns: `Ok(Vec)`. `Err("stat ...: ...")`, `Err("<path> exceeds max size (<n> > 4194304 bytes)")`, `Err("read ...: ...")` or `Err("parse ...: ...")` for IO/size/parse errors.
- Side effects: one `metadata` + one disk read.
- Errors: as above; never panics.
- Async: no.

**Calls**: `Path::exists`, `fs::metadata`, `fs::read_to_string`, `serde_json::from_str`.

**Called by**:
- `commands::pending_list` ([commands.rs:590](app/src-tauri/src/commands.rs:590)).
- `commands::import_pending_block` ([commands.rs:936](app/src-tauri/src/commands.rs:936)).
- `pending::add` ([pending.rs:134](app/src-tauri/src/pending.rs:134)).
- `pending::remove` ([pending.rs:144](app/src-tauri/src/pending.rs:144)).
- `pending::update_status` ([pending.rs:158](app/src-tauri/src/pending.rs:158)).
- Several tests.

---

### `pub fn save(data_dir: &Path, entries: &[PendingEntry]) -> Result<(), String>`  *(pending.rs:114)*

**Purpose**: Atomic write via sibling `pending_torrents.json.tmp` + rename.

**Contract**:
- Side effects:
  - `create_dir_all(data_dir)`.
  - Write tmp file with serialized body, `sync_data` (best-effort, result ignored), then rename.
- Errors: `Err("mkdir ...: ...")`, `Err("create ...")`, `Err("write ...")`, `Err("serialize: ...")`, `Err("rename ... -> ...: ...")`.
- Async: no.

**Calls**: `fs::create_dir_all`, `serde_json::to_string_pretty`, `fs::File::create`, `Write::write_all`, `File::sync_data`, `fs::rename`.

**Called by**:
- `commands::import_pending_block` ([commands.rs:950](app/src-tauri/src/commands.rs:950)).
- `pending::add`, `pending::remove`, `pending::update_status`, `pending::clear`.

---

### `pub fn add(data_dir: &Path, entry: PendingEntry) -> Result<Vec<PendingEntry>, String>`  *(pending.rs:133)*

**Purpose**: Add entry; replaces any existing entry with the same `torrent_id`.

**Contract**:
- Side effects: load + save (one read, one atomic write).
- Errors: from `load` or `save`.
- Async: no.

**Calls**: `load`, `Vec::retain`, `Vec::push`, `save`.

**Called by**:
- `commands::rd_send_magnet` pending path ([commands.rs:505](app/src-tauri/src/commands.rs:505)).
- Several tests.

---

### `pub fn remove(data_dir: &Path, torrent_id: &str) -> Result<Vec<PendingEntry>, String>`  *(pending.rs:143)*

**Purpose**: Remove by id. No-op if missing (still re-saves the file).

**Contract**: Side effects identical to `add`.

**Calls**: `load`, `Vec::retain`, `save`.

**Called by**:
- `commands::rd_check_pending` ([commands.rs:554](app/src-tauri/src/commands.rs:554), [commands.rs:566](app/src-tauri/src/commands.rs:566)).
- `commands::pending_remove` ([commands.rs:598](app/src-tauri/src/commands.rs:598)).
- Test.

---

### `pub fn update_status(data_dir: &Path, torrent_id: &str, rd_status: &str, progress: f64) -> Result<Vec<PendingEntry>, String>`  *(pending.rs:152)*

**Purpose**: Mutate one entry's `last_progress` / `last_rd_status` / `last_checked_at = Utc::now()`. No-op (no write) if id missing.

**Contract**:
- Side effects: load + (conditional) save. Writes `Utc::now().to_rfc3339()` into `last_checked_at`.
- Errors: from load/save.
- Async: no.

**Calls**: `load`, `Utc::now().to_rfc3339()`, `save`.

**Called by**:
- `commands::rd_check_pending` ([commands.rs:577](app/src-tauri/src/commands.rs:577)).
- Test at [pending.rs:240](app/src-tauri/src/pending.rs:240).

---

### `pub fn clear(data_dir: &Path) -> Result<(), String>`  *(pending.rs:169)*

**Purpose**: Save an empty list (delete-by-overwrite).

**Calls**: `save(data_dir, &[])`.

**Called by**:
- `commands::pending_clear` ([commands.rs:603](app/src-tauri/src/commands.rs:603)).
- Test.

---

### Tests — [pending.rs:173-289](app/src-tauri/src/pending.rs:173)

- `temp_dir`, `sample` (PendingEntry factory).
- `missing_file_returns_empty`.
- `add_and_load_roundtrips`.
- `add_replaces_same_torrent_id`.
- `remove_nonexistent_is_noop`.
- `update_status_writes_back`.
- `entries_have_no_magnet_field` — defense-in-depth: serialized file contains neither `"magnet:"` nor `"magnet"` field name.
- `clear_empties_the_list`.
- `load_rejects_oversized_file`.
- `load_accepts_file_just_under_limit`.

---

## 3.8 `secret_store.rs`

### `pub const RD_TOKEN_MAX_LEN: usize = 255`  *(secret_store.rs:29)* / `pub fn is_valid_rd_token(token: &str) -> bool`  *(secret_store.rs:43)*

**Purpose**: Single RD token format rule (F-04): non-empty, ≤ 255 bytes, all ASCII alphanumeric. Must stay in sync with the sidecar's `_RD_TOKEN_MAX_LEN` / `_is_valid_rd_token` in [sidecar/sidecar.py](sidecar/sidecar.py) (comment at [secret_store.rs:27-28](app/src-tauri/src/secret_store.rs:27), [secret_store.rs:35-42](app/src-tauri/src/secret_store.rs:35)). Empty is *invalid* here; callers that support "clear" check `is_empty()` themselves.

**Called by**: `set_rd_token` ([secret_store.rs:63](app/src-tauri/src/secret_store.rs:63)), `lib::migrate_legacy_token` ([lib.rs:185](app/src-tauri/src/lib.rs:185)), `commands::rd_save_token` ([commands.rs:360](app/src-tauri/src/commands.rs:360)), `commands::validate_legacy_rd_token` ([commands.rs:773](app/src-tauri/src/commands.rs:773)), tests.

### `pub const RD_TOKEN_FORMAT_ERR: &str = "rd_token_format_invalid"`  *(secret_store.rs:52)*

Stable error code for a non-empty token that fails `is_valid_rd_token`.

---

### `fn entry() -> Result<keyring::Entry, String>`  *(secret_store.rs:54)*

**Purpose**: Build a `keyring::Entry` for `SERVICE="JavDBMagnet"` / `ACCOUNT="RD_API_TOKEN"` (Windows Credential Manager target `RD_API_TOKEN.JavDBMagnet` — keyring 3 builds it as `{user}.{service}`).

**Contract**: pure wrapper; errors mapped to `format!("keyring entry: {e}")`.

**Calls**: `keyring::Entry::new`.

**Called by**: `set_rd_token`, `get_rd_token`, `delete_rd_token`.

---

### `pub fn set_rd_token(token: &str) -> Result<(), String>`  *(secret_store.rs:62)*

**Purpose**: Persist a token. Empty string → delete. Non-empty input is validated **before** the keyring is touched.

**Contract**:
- Side effects: OS credential store mutation.
- Errors: `Err("rd_token_format_invalid")` for a malformed non-empty token, `Err("keyring entry: ...")` from `entry()`, `Err("keyring set: ...")` from `set_password`, or whatever `delete_internal` returns.
- Async: no.

**Calls**: `is_valid_rd_token`, `entry()`, `keyring::Entry::set_password`, `delete_internal` (when token is empty).

**Called by**:
- `lib::migrate_legacy_token` ([lib.rs:194](app/src-tauri/src/lib.rs:194)).
- `commands::rd_save_token` ([commands.rs:363](app/src-tauri/src/commands.rs:363)).
- `commands::import_rd_token` ([commands.rs:805](app/src-tauri/src/commands.rs:805)).
- Test `set_rd_token_rejects_invalid_before_touching_keyring`.

---

### `pub fn get_rd_token() -> Result<Option<String>, String>`  *(secret_store.rs:74)*

**Purpose**: Read the token. `Ok(None)` if no entry yet.

**Contract**:
- Side effects: OS credential store read.
- Errors: `Err("keyring entry: ...")` / `Err("keyring get: ...")`. `NoEntry` is mapped to `Ok(None)` (not an error).
- Async: no.

**Calls**: `entry()`, `keyring::Entry::get_password`.

**Called by**:
- `lib::load_handshake_inputs` ([lib.rs:60](app/src-tauri/src/lib.rs:60)).
- `commands::rd_has_token` ([commands.rs:308](app/src-tauri/src/commands.rs:308)).

---

### `pub fn delete_rd_token() -> Result<(), String>`  *(secret_store.rs:83)*

**Purpose**: Drop the keyring entry.

**Calls**: `entry()`, `delete_internal(&e)`.

**Called by**: `commands::rd_clear_token` ([commands.rs:378](app/src-tauri/src/commands.rs:378)).

---

### `fn delete_internal(e: &keyring::Entry) -> Result<(), String>`  *(secret_store.rs:88)*

**Purpose**: Delete helper. `NoEntry` is treated as success; other failures → `Err("keyring delete: ...")`.

**Calls**: `keyring::Entry::delete_credential`.

**Called by**: `set_rd_token` (when token is empty) and `delete_rd_token`.

---

### Tests — [secret_store.rs:95-148](app/src-tauri/src/secret_store.rs:95)

- `is_valid_rd_token_accepts_realistic_shape`.
- `is_valid_rd_token_rejects_format_violations`.
- `set_rd_token_rejects_invalid_before_touching_keyring` — works without a usable secret-service backend because validation precedes `entry()`.

---

## 3.9 `settings.rs`

### `pub struct UiSettings { theme, scale }`  *(settings.rs:17)*

DTO. `Default`: `theme="light"`, `scale="auto"`.

### `pub struct RdSettings { api_token, file_pick, min_size_mb, cache_wait_seconds }`  *(settings.rs:32)*

DTO. `Default`: empty token, `file_pick="smart"`, `min_size_mb=500`, `cache_wait_seconds=15`.

### `fn default_version() -> u32`  *(settings.rs:50)*

Returns `1`. Serde default for `Settings::version`.

### `pub struct Settings { version, ui, rd }`  *(settings.rs:55)*

DTO. Top-level shape that lands inside `settings.json` under the key `"settings"` (`SETTINGS_KEY`). `ui` / `rd` are `#[serde(default)]`.

---

### `pub(crate) fn clamp_rd_settings(mut s: Settings) -> Settings`  *(settings.rs:78)*

**Purpose**: Clamp persisted RD numerics into the range the send path accepts: `cache_wait_seconds` into `[MIN_RD_CACHE_WAIT_SECS, MAX_RD_CACHE_WAIT_SECS]` = `[5, 300]`, `min_size_mb` to at most `1_000_000`. An out-of-range `cache_wait_seconds` would otherwise make `timeout_for` reject every `rd_send_magnet`.

**Contract**: pure; cannot fail.

**Called by**: `read_settings` ([settings.rs:131](app/src-tauri/src/settings.rs:131)), `write_settings` ([settings.rs:146](app/src-tauri/src/settings.rs:146)), `commands::import_env_settings_patch` ([commands.rs:858](app/src-tauri/src/commands.rs:858)), test.

---

### `fn without_secrets(mut settings: Settings) -> Settings`  *(settings.rs:87)*

**Purpose**: Clear `rd.api_token` so the legacy plaintext field never crosses back into the WebView. Applied on both read and write paths.

**Contract**:
- Side effects: in-place mutation of the moved value.
- Errors: cannot fail.
- Async: no.

**Calls**: `String::clear`.

**Called by**: `read_settings`, `write_settings`, and a test.

---

### `pub struct PathInfo { data_dir: String, log_dir: String }`  *(settings.rs:97)*

DTO returned by `get_paths`.

---

### `pub fn get_paths(path_manager: State<PathManager>) -> PathInfo`  *(settings.rs:103)*

**Purpose**: Return the resolved data + log dirs as strings.

**Contract**:
- Side effects: none.
- Errors: none.
- Async: no.

**Calls**: `Path::display`.

**Called by**: frontend.

---

### `pub fn read_settings(app: AppHandle, path_manager: State<PathManager>) -> Result<Settings, String>`  *(settings.rs:111)*

**Purpose**: Read settings out of `<data_dir>/settings.json` via tauri-plugin-store. Clamps RD numerics on the way out and always blanks `rd.api_token` before returning.

**Contract**:
- Side effects: store open + read; one disk read.
- Errors: `Err(<store error>)` or `Err(<serde error>)`. Missing `"settings"` key yields `Settings::default()`.
- Async: no.

Uses an absolute path so the plugin doesn't resolve under its default `BaseDirectory::AppData` (which would land under `%APPDATA%\<identifier>\` instead of `%APPDATA%\JavDBMagnet\`).

**Calls**: `app.store(store_path)`, `Store::get`, `serde_json::from_value::<Settings>`, `clamp_rd_settings`, `without_secrets`.

**Called by**: frontend.

---

### `pub fn write_settings(app: AppHandle, path_manager: State<PathManager>, settings: Settings) -> Result<(), String>`  *(settings.rs:139)*

**Purpose**: Persist settings to `<data_dir>/settings.json`. Clamps RD numerics and blanks `rd.api_token` before serializing.

**Contract**:
- Side effects: disk write (atomic semantics owned by tauri-plugin-store).
- Errors: `Err(<store error>)`, `Err(<serde error>)`, `Err(<save error>)`.
- Async: no.

**Calls**: `app.store(...)`, `clamp_rd_settings`, `without_secrets`, `serde_json::to_value`, `Store::set`, `Store::save`.

**Called by**: frontend.

---

### Tests — [settings.rs:153-188](app/src-tauri/src/settings.rs:153)

- `without_secrets_clears_legacy_rd_token_field` — drops a populated `api_token` and confirms it's blanked.
- `clamp_rd_settings_clamps_out_of_bounds_values` — 1 → 5, 9999 → 300, `min_size_mb` 5,000,000 → 1,000,000; in-range values unchanged.

---

## 3.10 `sidecar_manager.rs`

### `pub struct SidecarManager { inner: Arc<Mutex<SidecarInner>> }`  *(sidecar_manager.rs:59)*

Managed in `tauri::State` for the app's lifetime. The `Arc<Mutex<_>>` (`tauri::async_runtime::Mutex`) serializes all requests to the single Python subprocess.

### `struct SidecarInner { child: Option<CommandChild>, line_rx: mpsc::UnboundedReceiver<String>, request_counter: u64, dead: Option<String> }`  *(sidecar_manager.rs:63)*

Private. `child.write(...)` is the stdin sender. `line_rx` is the receiving end of an unbounded mpsc channel — a background task drains the plugin-shell event stream and pushes complete newline-delimited lines here. `request_counter` produces monotonic `r-N` IDs. `dead` holds the permanent failure reason once set.

- `fn mark_dead(&mut self, reason: String) -> String` *(sidecar_manager.rs:73)* — best-effort `child.kill()` (takes the child), records `dead = Some(reason)`, returns `reason`.
- `impl Drop for SidecarInner` *(sidecar_manager.rs:82)* — kills the child if still held.

### `pub(crate) fn SidecarManager::dead_for_tests(reason: &str) -> Self`  *(sidecar_manager.rs:93)*

`#[cfg(test)]` only ([sidecar_manager.rs:88](app/src-tauri/src/sidecar_manager.rs:88)). Builds a manager whose `SidecarInner` has `child: None` and `dead: Some(reason)`, so every `request()` fails fast with `Err("sidecar is dead: <reason>")` and nothing is spawned. Lets command bodies (`rd_test_token_with`, `push_imported_settings`) be tested for whether they reach the sidecar at all.

---

### Private helpers

- `fn timeout_error(cmd: &str, secs: u64) -> String` *(sidecar_manager.rs:106)* — `"sidecar request '<cmd>' timed out after <secs>s; restart the app to recover"`.
- `fn timeout_for(cmd: &str, body: &Value) -> Result<u64, String>` *(sidecar_manager.rs:118)* — 60 s for every command except `rd_send_magnet`, which gets `cache_wait + 90`. `cache_wait` missing/null → 15; non-integer / negative → `Err("rd_send_magnet: cache_wait must be a non-negative integer, got …")`; `< 5` → `Err("rd_send_magnet: cache_wait=<n> below floor 5s")`; `> 300` → `Err("… above ceiling 300s")`. On `Err` the request is never sent.
- `fn sidecar_env(paths: &Value) -> Vec<(&'static str, String)>` *(sidecar_manager.rs:166)* — `[("JAVDB_LOG_DIR", log_dir)]` when `paths.log_dir` is a non-blank string (forwarded as-is, untrimmed), else empty.
- `fn drain_line(buffer: &mut Vec<u8>) -> Option<String>` *(sidecar_manager.rs:192)* — pop one `\n`-terminated line, strip `\n` and a preceding `\r`, lossy UTF-8.
- `fn error_message(resp: &Value) -> Option<&str>` *(sidecar_manager.rs:337)* — `resp.error.message`.
- `fn require_ok(resp: &Value, what: &str) -> Result<(), String>` *(sidecar_manager.rs:346)* — `Err("sidecar <what> failed: <error.message | '<what> failed'>")` for a non-ok reply.

---

### `pub fn sidecar_command<R: Runtime>(app: &AppHandle<R>, paths: &Value) -> Result<Command, String>`  *(sidecar_manager.rs:179)*

**Purpose**: Resolve the bundled `sidecar` (`app.shell().sidecar("sidecar")`) and attach `.envs(sidecar_env(paths))`, without spawning. `pub` and re-exported `#[doc(hidden)]` from [lib.rs:25-26](app/src-tauri/src/lib.rs:25) only so `tests/sidecar_command.rs` can inspect it through `MockRuntime`.

**Errors**: `Err("sidecar resolve failed: ...")`.

**Called by**: `spawn_and_handshake` ([sidecar_manager.rs:212](app/src-tauri/src/sidecar_manager.rs:212)); integration tests at [tests/sidecar_command.rs:38](app/src-tauri/tests/sidecar_command.rs:38), [tests/sidecar_command.rs:49](app/src-tauri/tests/sidecar_command.rs:49).

---

### `pub async fn SidecarManager::spawn_and_handshake(app, cookies, rd_token, settings, paths) -> Result<Self, String>`  *(sidecar_manager.rs:205)*

**Purpose**: Spawn the bundled `sidecar` binary, perform `hello` + `handshake`, and return a manager ready for `request(...)`.

**Contract**:
- Params:
  - `app: &AppHandle` — used for the shell-plugin sidecar resolve.
  - `cookies: String` — JavDB cookies as a single string.
  - `rd_token: Option<String>` — token if available.
  - `settings: Value` — the `"settings"` object from settings.json (or empty obj).
  - `paths: Value` — `{"data_dir": ..., "log_dir": ...}` JSON.
- Returns: `Ok(SidecarManager)` once both `hello` (with `{"protocol_version": 1}`) and `handshake` (`{"cookies", "rd_token", "settings", "paths"}`) returned `ok: true`.
- Side effects:
  - Spawns a child process via `tauri-plugin-shell`, passing `paths.log_dir` as `JAVDB_LOG_DIR` in the child environment. The command is built by `sidecar_command(app, &paths)` (resolve `sidecar` + `.envs(sidecar_env(&paths))`), re-exported `#[doc(hidden)]` from lib.rs solely so the integration test `tests/sidecar_command.rs` can inspect it through tauri's MockRuntime without spawning. On MSVC, build.rs embeds the Common Controls v6 manifest into test targets only (`cargo:rustc-link-arg-tests`) so that test exe can load; see docs/platform/windows-build.md §3. The value is forwarded as-is and `app_logging` `.strip()`s it, so leading/trailing whitespace is never part of the effective log path; a missing, non-string or whitespace-only `log_dir` sets nothing, leaving the sidecar's own fallback (`%LOCALAPPDATA%\JavDBMagnet\logs` → console-only). The handshake `paths.log_dir` field alone does not reach logging: the sidecar configures logging before reading the handshake.
  - Spawns a tokio task that lives until the child terminates: parses `CommandEvent::Stdout` chunks into lines via `drain_line` and pushes to the unbounded channel. `CommandEvent::Stderr` is **silently dropped** ([sidecar_manager.rs:231-235](app/src-tauri/src/sidecar_manager.rs:231)); the comment says M6 will wire stderr to the log file. `CommandEvent::Terminated` ends the task.
  - Writes 2 JSON lines on stdin during construction.
- Errors:
  - `Err("sidecar resolve failed: ...")` / `Err("sidecar spawn failed: ...")` from plugin-shell.
  - `Err("sidecar hello failed: <error.message>")` if hello rejected (via `require_ok`).
  - `Err("sidecar handshake failed: <error.message>")` if handshake rejected.
  - Any `request` error (timeout, EOF, …) during hello/handshake.
- Async: yes. Called via `block_on` in `lib::run`.
- Authorization: this is the bootstrap.

**Calls**:
- `sidecar_command(app, &paths)` → [sidecar_manager.rs:179](app/src-tauri/src/sidecar_manager.rs:179) → `tauri_plugin_shell::ShellExt::sidecar`.
- `Command::spawn` from plugin-shell.
- `tauri::async_runtime::spawn` for the line-reader task.
- `tokio::sync::mpsc::unbounded_channel`.
- `self.request("hello", ...)`, `self.request("handshake", ...)` → [sidecar_manager.rs:271](app/src-tauri/src/sidecar_manager.rs:271).
- `require_ok(&resp, ...)` → [sidecar_manager.rs:346](app/src-tauri/src/sidecar_manager.rs:346).

**Called by**: `lib::run` setup ([lib.rs:407-415](app/src-tauri/src/lib.rs:407)).

---

### `pub async fn SidecarManager::request(&self, cmd: &str, body: Value) -> Result<Value, String>`  *(sidecar_manager.rs:271)*

**Purpose**: Send one JSON-line request to the sidecar and await one JSON-line response, bounded by a per-command timeout. The core RPC primitive.

**Contract**:
- Params:
  - `cmd` — the `cmd` field injected into the outgoing object.
  - `body` — must be a JSON object or `Value::Null`. Other shapes are rejected.
- Returns: parsed `Value` of the response line (no `ok` check — callers do that).
- Side effects:
  - `timeout_for(cmd, &body)` runs **before** locking or sending; a validation error means nothing reaches the sidecar.
  - Acquires `self.inner.lock().await` — **all requests are globally serialized**. (See concurrency model header comment.)
  - Fails fast if the manager is already dead.
  - Increments `request_counter`; constructs `request_id = "r-N"`.
  - Writes `<serialized line>\n` to the child's stdin.
  - Reads one line from `line_rx` under `tokio::time::timeout`.
  - On stdin-write failure, missing child, timeout, EOF, parse failure or `request_id` mismatch: `mark_dead` (kills the child) — the manager stays dead for the rest of the process.
- Errors:
  - `timeout_for` validation errors (only `rd_send_magnet`).
  - `Err("sidecar is dead: <reason>")` once dead.
  - `Err("request body must be a JSON object or null, got <value>")` for misshapen body.
  - `Err("serialize failed: ...")` from `serde_json::to_string`.
  - `Err("child handle missing")` / `Err("stdin write failed: ...")` from `CommandChild::write` (marks dead).
  - `Err("sidecar request '<cmd>' timed out after <N>s; restart the app to recover")` (marks dead).
  - `Err("sidecar closed before response")` if the line channel returned `None` (the bg task exited; marks dead).
  - `Err("response parse failed: ...")` if the line isn't valid JSON (marks dead).
  - `Err("request_id mismatch: expected r-N, got ...")` if the sidecar returns the wrong correlation id (marks dead).
- Async: yes; awaits both the mutex and the channel.
- Authorization: requires the sidecar to be alive.

**Calls**:
- `timeout_for` → [sidecar_manager.rs:118](app/src-tauri/src/sidecar_manager.rs:118).
- `Mutex::lock`.
- `serde_json::to_string`.
- `CommandChild::write`.
- `tokio::time::timeout` + `mpsc::UnboundedReceiver::recv`.
- `serde_json::from_str`.
- `SidecarInner::mark_dead` → [sidecar_manager.rs:73](app/src-tauri/src/sidecar_manager.rs:73).

**Called by**:
- `spawn_and_handshake` (twice — hello + handshake).
- Every `#[tauri::command]` that talks to the sidecar (17 of them: `sidecar_ping`, `fetch_javdb`, `copy_magnet`, `copy_magnets_bulk`, `forget_magnets`, `register_magnets`, `rd_test_token` via `rd_test_token_with`, `rd_save_token`, `rd_clear_token`, `rd_check_user`, `rd_send_magnet`, `rd_check_pending`, `apply_legacy_import` via `import_rd_token` and `push_imported_settings`, `migrate_cookies_now` / `save_cookies` / `clear_cookies` via `push_cookies_to_sidecar`, `update_sidecar_settings`).

---

### Tests — [sidecar_manager.rs:355-502](app/src-tauri/src/sidecar_manager.rs:355)

- `mark_dead_records_reason_and_is_idempotent`, `require_ok_propagates_err_on_error_envelope`, `timeout_error_names_the_command_and_actual_secs`.
- `timeout_for_normal_command_uses_default`, `timeout_for_rd_send_magnet_missing_cache_wait_uses_default_15`, `timeout_for_rd_send_magnet_at_ceiling`, `timeout_for_rd_send_magnet_above_ceiling_errors`, `timeout_for_rd_send_magnet_non_integer_errors`, `timeout_for_rd_send_magnet_below_floor_errors`.
- `sidecar_env_forwards_log_dir_as_javdb_log_dir`, `sidecar_env_leaves_trimming_to_the_sidecar`, `sidecar_env_is_empty_without_a_usable_log_dir`.
- `sidecar_command` wiring tests live in `tests/sidecar_command.rs` (§3.12).

---

## 3.11 `cookie_store.rs`

Secret storage for the JavDB cookie blob, mirroring `secret_store` (keyring `SERVICE="JavDBMagnet"`, `ACCOUNT="JAVDB_COOKIES"`, [cookie_store.rs:25-26](app/src-tauri/src/cookie_store.rs:25)). `cookies.txt` stays the user-facing edit format but is treated as a write-once scratchpad migrated into the keyring (see `lib::migrate_cookies_from_file`). No format validation beyond the 64 KiB size cap — the cookie header is opaque.

### `pub const COOKIES_MAX_BYTES: usize = 64 * 1024`  *(cookie_store.rs:32)* / `pub const COOKIES_TOO_LARGE_ERR: &str = "cookies_too_large"`  *(cookie_store.rs:37)*

Size cap mirroring `lib::COOKIES_MAX_BYTES`, and its stable error code.

---

### `fn entry() -> Result<keyring::Entry, String>`  *(cookie_store.rs:39)*

`keyring::Entry::new(SERVICE, ACCOUNT)`; errors → `"keyring entry: {e}"`. Called by `set_cookies`, `get_cookies`, `delete_cookies`.

---

### `pub fn check_cookies_format(value: &str) -> Result<(), String>`  *(cookie_store.rs:46)*

**Purpose**: Pure size check — `Err("cookies_too_large")` when `value.len() > COOKIES_MAX_BYTES`.

**Called by**: `set_cookies` ([cookie_store.rs:58](app/src-tauri/src/cookie_store.rs:58)), `commands::validate_cookies_input` ([commands.rs:1100](app/src-tauri/src/commands.rs:1100)), tests.

---

### `pub fn set_cookies(value: &str) -> Result<(), String>`  *(cookie_store.rs:57)*

**Purpose**: Persist a cookie blob. Size-checked **before** the keyring is touched; empty string → delete.

**Contract**:
- Side effects: OS credential store mutation.
- Errors: `Err("cookies_too_large")`, `Err("keyring entry: ...")`, `Err("keyring set: ...")`, or `delete_internal` errors.
- Async: no.

**Calls**: `check_cookies_format`, `entry()`, `keyring::Entry::set_password`, `delete_internal`.

**Called by**: `lib::migrate_cookies_from_file` ([lib.rs:144](app/src-tauri/src/lib.rs:144)), `commands::save_cookies_local` ([commands.rs:1117](app/src-tauri/src/commands.rs:1117)), `KeyringSandbox::drop` and e2e tests.

---

### `pub fn get_cookies() -> Result<Option<String>, String>`  *(cookie_store.rs:68)*

**Purpose**: Read the blob. `NoEntry` → `Ok(None)`; other failures → `Err("keyring get: ...")`.

**Called by**: `lib::load_cookies` ([lib.rs:91](app/src-tauri/src/lib.rs:91)), `commands::cookies_status_for` ([commands.rs:1043](app/src-tauri/src/commands.rs:1043)), `KeyringSandbox::new` and e2e tests.

---

### `pub fn delete_cookies() -> Result<(), String>`  *(cookie_store.rs:86)*

**Purpose**: Remove the keyring entry. Only half of a clear — `commands::clear_cookies_local` owns deleting the file first so the next handshake does not re-migrate it.

**Calls**: `entry()`, `delete_internal`.

**Called by**: `commands::clear_cookies_local` ([commands.rs:1180](app/src-tauri/src/commands.rs:1180)), `KeyringSandbox` (tests).

---

### `fn delete_internal(e: &keyring::Entry) -> Result<(), String>`  *(cookie_store.rs:91)*

`NoEntry` is success; other failures → `"keyring delete: {err}"`. Called by `set_cookies` (empty value) and `delete_cookies`.

---

### `pub fn file_has_real_cookies(content: &str) -> bool`  *(cookie_store.rs:107)*

**Purpose**: Heuristic: at least one trimmed, non-empty, non-`#` line containing `=`. Keeps a template-only file from clobbering a good keyring value.

**Called by**: `lib::migrate_cookies_from_file` ([lib.rs:125](app/src-tauri/src/lib.rs:125)), tests.

---

### `pub fn extract_cookie_lines(content: &str) -> String`  *(cookie_store.rs:131)*

**Purpose**: Keep only cookie-pair lines (trimmed, non-empty, non-`#`, contains `=`) joined with `"; "`, so the keyring blob stays under Windows Credential Manager's ~2.5 KiB cap and matches the `Cookie:`-header shape the sidecar's `parse_cookie_string` expects. Empty string if none.

**Called by**: `lib::migrate_cookies_from_file` ([lib.rs:135](app/src-tauri/src/lib.rs:135)), tests.

---

### Tests — [cookie_store.rs:140-253](app/src-tauri/src/cookie_store.rs:140)

- `file_has_real_cookies_rejects_template_only`, `file_has_real_cookies_accepts_edited_template`, `file_has_real_cookies_rejects_empty_and_whitespace`, `file_has_real_cookies_rejects_comments_with_equals`.
- `check_cookies_format_rejects_oversized`, `check_cookies_format_accepts_at_cap_and_smaller`.
- `extract_cookie_lines_strips_template_comments`, `extract_cookie_lines_joins_multi_line_cookie_blocks`, `extract_cookie_lines_template_only_yields_empty_string`.

---

## 3.12 `tests/sidecar_command.rs`

Integration test (separate test target) guarding the spawn wiring: the command `spawn_and_handshake` runs must carry `JAVDB_LOG_DIR`. Uses `tauri::test::{mock_builder, mock_context, noop_assets, MockRuntime}` with `tauri_plugin_shell::init()`, converts the `Command` into `std::process::Command` and reads `get_envs()`.

- `mock_app_with_shell()` *(tests/sidecar_command.rs:15)*, `command_env(cmd)` *(tests/sidecar_command.rs:22)*.
- `sidecar_command_carries_javdb_log_dir` *(tests/sidecar_command.rs:36)* — env is exactly `[("JAVDB_LOG_DIR", Some("/tmp/logs"))]`.
- `sidecar_command_sets_no_env_without_log_dir` *(tests/sidecar_command.rs:47)* — `{}` paths → no env.

---

## 4. Cross-cutting Concerns

### 4.1 Error type(s)

There is **no custom error enum**. Every fallible function returns `Result<T, String>`, with the `String` typically formatted via `format!("<context>: {e}")`. Tauri serializes the `Err` arm verbatim to the frontend.

A handful of low-level functions use `Result<T, std::io::Error>` (`PathManager::ensure_dirs`) or `Result<T, Box<dyn std::error::Error>>` (`PathManager::new`), but those are only called from the setup closure where the conversion is `?`-eliminated into a `Box<dyn Error>`.

Common error-string shapes:
- `format!("read {}: {e}", path.display())` — pending IO.
- `format!("keyring entry: {e}")` — keyring failures (both `secret_store` and `cookie_store`).
- `format!("mkdir {}: {e}", ...)` — directory creation.
- `ensure_ok(&resp)` / `_err_code(&resp)` — sidecar non-ok responses surface only the `error.code` (e.g. `unknown_handle`, `rd_no_token`). Exception: `fetch_javdb` surfaces `error.message`.
- Stable Rust-side codes: `rd_token_format_invalid` (`rd_save_token`, and `rd_test_token` before any RPC via `check_candidate_token`), `rd_no_token` (empty `rd_test_token` input), `cookies_empty`, `cookies_too_large`, `cookies_cleared_sidecar_stale: <e>`.
- `sidecar is dead: <reason>` — every request after a timeout / EOF / protocol corruption.

### 4.2 Logging conventions

There is **no logging crate** wired up in this code. The only places anything is emitted from Rust are:
- `eprintln!` in `load_cookies` ([lib.rs:93](app/src-tauri/src/lib.rs:93)) — cookie keyring read failure.
- `eprintln!` in `migrate_cookies_from_file` ([lib.rs:115](app/src-tauri/src/lib.rs:115), [lib.rs:145](app/src-tauri/src/lib.rs:145), [lib.rs:156](app/src-tauri/src/lib.rs:156)) — oversized file, keyring write failure, file delete failure.
- `eprintln!` in `migrate_legacy_token` ([lib.rs:186](app/src-tauri/src/lib.rs:186), [lib.rs:195](app/src-tauri/src/lib.rs:195)) — malformed legacy token, keyring write failure.
- `.expect(...)` at the bottom of `run()` ([lib.rs:455](app/src-tauri/src/lib.rs:455)) — panic on Tauri runtime error.

In a release (`windows_subsystem = "windows"`) build these stderr lines go nowhere visible (noted at [cookie_store.rs:121-122](app/src-tauri/src/cookie_store.rs:121)).

Stderr from the sidecar process is **silently dropped** by the line-reader background task ([sidecar_manager.rs:231-235](app/src-tauri/src/sidecar_manager.rs:231)). The comment promises M6 will wire it to a log file; that's still a TODO. The sidecar writes its own log file under `JAVDB_LOG_DIR`.

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
                       (clamp_rd_settings + without_secrets applied both ways)

frontend update_sidecar_settings → commands.rs::update_sidecar_settings → SidecarManager → sidecar process

frontend apply_legacy_import → import_env_block → import_env_settings_patch → tauri-plugin-store (save)
                                                └→ push_imported_settings → SidecarManager ("update_settings")
```

Notably, `write_settings` and `update_sidecar_settings` are **separate commands** and the frontend is responsible for calling both ([App.svelte:1549](app/src/App.svelte:1549), [App.svelte:1553](app/src/App.svelte:1553)). There is no Rust-side observer pattern; if the frontend writes settings without pushing to the sidecar, the sidecar stays out of sync until the next app restart. Note `update_sidecar_settings` forwards the frontend's raw object (not the clamped copy that `write_settings` persisted). The one Rust-side push is the legacy `.env` import: after `import_env_settings_patch` saves, `push_imported_settings` sends the saved (clamped, token-blanked) settings to the sidecar itself.

### 4.5 Sidecar lifecycle

- **Spawn**: synchronous during setup via `block_on(SidecarManager::spawn_and_handshake)` ([lib.rs:407](app/src-tauri/src/lib.rs:407)). Setup failure means the window does not open.
- **Handshake**: `hello` (protocol version negotiation) then `handshake` (cookies, token, settings, paths). `JAVDB_LOG_DIR` is passed via the child environment, not the handshake.
- **Health check**: there is **no periodic ping**. `sidecar_ping` exists but is invoked by the frontend on demand.
- **Concurrency**: a single `tauri::async_runtime::Mutex` (tokio) serializes all requests. This was a deliberate choice because the sidecar's dispatch loop is single-threaded synchronous ([sidecar_manager.rs:7-8](app/src-tauri/src/sidecar_manager.rs:7)).
- **Liveness / timeouts**: every request is bounded — 60 s default, `cache_wait + 90` s for `rd_send_magnet` (max 390 s) ([sidecar_manager.rs:10-23](app/src-tauri/src/sidecar_manager.rs:10)).
- **Shutdown**: no explicit goodbye message. `SidecarInner` implements `Drop` ([sidecar_manager.rs:82-104](app/src-tauri/src/sidecar_manager.rs:82)) and best-effort kills the child when the managed state is dropped.
- **Crash handling**: timeout, EOF (`CommandEvent::Terminated` ends the reader task), stdin write failure, unparsable line or `request_id` mismatch → `mark_dead` kills the child and every subsequent `request(...)` fails fast with `Err("sidecar is dead: <reason>")`. There is no automatic respawn; the user must restart the app.

### 4.6 Path discovery / config dirs

- `data_dir` = `%APPDATA%\JavDBMagnet` on Windows ([path_manager.rs:24-33](app/src-tauri/src/path_manager.rs:24)).
- `log_dir` = `%LOCALAPPDATA%\JavDBMagnet\logs`.
- Non-Windows fallback uses Tauri's `app_data_dir()` / `app_log_dir()` (i.e. under the `com.javdbmagnet.app` identifier).
- Both dirs are `create_dir_all`'d during setup.
- The choice to hardcode `JavDBMagnet` (rather than the reverse-DNS bundle identifier) is documented at [path_manager.rs:7-9](app/src-tauri/src/path_manager.rs:7) — spec §4.

### 4.7 Security invariants (per-module annotations)

1. **RD token never lives in plaintext on disk** after the first launch: `migrate_legacy_token` moves a valid legacy token to the keyring and blanks `settings.rd.api_token` (a malformed legacy value is left in place and never reaches the keyring or handshake). Both `read_settings` and `write_settings` go through `without_secrets` ([settings.rs:87](app/src-tauri/src/settings.rs:87)) which clears the field defensively. **Settings sent to the sidecar never carry `rd.api_token`**: every path blanks it with `blank_rd_api_token` — the handshake (`load_handshake_inputs`, [lib.rs:64](app/src-tauri/src/lib.rs:64)), `update_sidecar_settings`, and the legacy import push (`settings_push_body`); the token reaches the sidecar only as the separate `rd_token` / `rd_set_token` value.
2. **RD token format is gated on every keyring write path**: `secret_store::set_rd_token` validates before touching the keyring, and `rd_save_token` / `import_rd_token` / `migrate_legacy_token` pre-check with `is_valid_rd_token` (same rule as the sidecar's `_is_valid_rd_token`). The non-persisting `rd_test_token` applies the same rule (`check_candidate_token`) before any sidecar RPC.
3. **Magnet text only crosses the IPC boundary inbound**: `register_magnets` is the only inbound path; everywhere else, magnets are referenced by `handle_id` only. Comments at [commands.rs:3-9](app/src-tauri/src/commands.rs:3) and [commands.rs:110-111](app/src-tauri/src/commands.rs:110) document the invariant; the `entries_have_no_magnet_field` test ([pending.rs:248](app/src-tauri/src/pending.rs:248)) and `sanitize_pending_drops_magnet_fields` test ([legacy_import.rs:564](app/src-tauri/src/legacy_import.rs:564)) defend the persistence side.
4. **JavDB cookies live in the OS credential store**: a real `cookies.txt` is migrated (extracted pairs only) and deleted at startup / `migrate_cookies_now`; `save_cookies` writes the keyring directly; `clear_cookies` removes file, keyring and sidecar copy (file first, so it can't be resurrected).
5. **cookies body is never returned**: `cookies_status_with_keyring` reports only metadata, defended by `cookies_status_does_not_leak_body` ([commands.rs:1547](app/src-tauri/src/commands.rs:1547)).
6. **The legacy importer cannot exfiltrate values**: `preview` only echoes presence flags and key names. The `preview_reports_files_without_echoing_values` test ([legacy_import.rs:656](app/src-tauri/src/legacy_import.rs:656)) asserts no echo of test secrets.
7. **`rd.api_token` is structurally unreachable from `.env` patches**: `parse_env` puts the token into a separate `ParsedEnv.token` field; `merge_patch_entry` ([legacy_import.rs:426-428](app/src-tauri/src/legacy_import.rs:426)) explicitly skips any `rd.api_token` key in the patch and `clear_rd_api_token` then re-blanks the field as a final safety net.
8. **Clipboard / dialog / store plugins are not exposed to the WebView**: `capabilities/default.json` grants only `core:default` and a single-URL `shell:allow-open`.

---

## 5. Call Graph (top entry points)

### 5.1 `lib::run` → setup

```
lib::run                                              (lib.rs:385)
├── PathManager::new                                  (path_manager.rs:24)
│   └── std::env::var(APPDATA / LOCALAPPDATA)
├── PathManager::ensure_dirs                          (path_manager.rs:45)
│   └── std::fs::create_dir_all  x2
├── load_handshake_inputs                             (lib.rs:49)
│   ├── load_cookies                                  (lib.rs:84)
│   │   ├── migrate_cookies_from_file                 (lib.rs:112)
│   │   │   ├── std::fs::metadata + read_to_string (cookies.txt, ≤ 64 KiB)
│   │   │   ├── cookie_store::file_has_real_cookies   (cookie_store.rs:107)
│   │   │   ├── cookie_store::extract_cookie_lines    (cookie_store.rs:131)
│   │   │   ├── cookie_store::set_cookies             (cookie_store.rs:57)
│   │   │   └── std::fs::remove_file
│   │   └── cookie_store::get_cookies (if nothing migrated) (cookie_store.rs:68)
│   ├── std::fs::read_to_string (settings.json) + serde_json::from_str
│   ├── secret_store::get_rd_token                    (secret_store.rs:74)
│   │   ├── keyring::Entry::new
│   │   └── keyring::Entry::get_password
│   └── migrate_legacy_token (only if keyring empty)  (lib.rs:177)
│       ├── secret_store::is_valid_rd_token           (secret_store.rs:43)
│       ├── secret_store::set_rd_token                (secret_store.rs:62)
│       ├── std::fs::read_to_string + serde_json roundtrip
│       └── std::fs::write
├── tauri::AppHandle::manage(PathManager)
├── tauri::async_runtime::block_on(
│     SidecarManager::spawn_and_handshake )           (sidecar_manager.rs:205)
│   ├── sidecar_command (ShellExt::sidecar("sidecar").envs(JAVDB_LOG_DIR)) (sidecar_manager.rs:179)
│   ├── Command::spawn
│   ├── tauri::async_runtime::spawn (line reader task)
│   ├── self.request("hello", ...)                    (sidecar_manager.rs:271)
│   └── self.request("handshake", ...)
├── tauri::AppHandle::manage(SidecarManager)
└── tauri::generate_handler![ ... 31 commands ... ]
```

### 5.2 `commands::fetch_javdb`

```
commands::fetch_javdb                                 (commands.rs:36)
└── SidecarManager::request("fetch_javdb", ...)       (sidecar_manager.rs:271)
    ├── timeout_for (60 s)
    ├── Mutex::lock
    ├── CommandChild::write
    ├── tokio::time::timeout(mpsc::UnboundedReceiver::recv)
    └── serde_json::from_str
```

### 5.3 `commands::copy_magnet`

```
commands::copy_magnet                                 (commands.rs:56)
├── SidecarManager::request("resolve_magnet", ...)    (sidecar_manager.rs:271)
├── ensure_ok                                         (commands.rs:274)
└── ClipboardExt::clipboard().write_text(magnet)      (tauri-plugin-clipboard-manager)
    [ local `magnet` String drops at function end ]
```

### 5.4 `commands::copy_magnets_bulk`

```
commands::copy_magnets_bulk                           (commands.rs:159)
├── SidecarManager::request("resolve_magnets", ...)
├── resolved_magnets_from_response                    (commands.rs:181)
│   └── ensure_ok
└── ClipboardExt::clipboard().write_text(joined)      (skipped when nothing resolved)
```

### 5.5 `commands::copy_rd_links_bulk`

```
commands::copy_rd_links_bulk                          (commands.rs:226)
└── ClipboardExt::clipboard().write_text(joined)
    [ No sidecar — pure clipboard write with trim/filter ]
```

### 5.6 `commands::register_magnets`

```
commands::register_magnets                            (commands.rs:113)
├── SidecarManager::request("register_magnets", ...)
├── ensure_ok (on failure → error.code)               (commands.rs:274)
└── serde_json::from_value  x2  (RegisteredMagnet, String)
```

### 5.7 `commands::rd_send_magnet`

```
commands::rd_send_magnet                              (commands.rs:443)
├── SidecarManager::request("rd_send_magnet", ...)
│   └── timeout_for (cache_wait ∈ [5, 300] else Err before send; budget cache_wait + 90 s)
├── ensure_ok (on failure)
├── if status == "completed":
│   └── serde_json::from_value::<Vec<RdLink>>
└── else (pending):
    ├── PendingEntry::new                             (pending.rs:66)
    │   └── chrono::Utc::now().to_rfc3339()
    └── pending::add                                  (pending.rs:133)
        ├── pending::load                             (pending.rs:92)
        │   └── std::fs::metadata (≤ 4 MiB) + read_to_string + serde_json::from_str
        └── pending::save                             (pending.rs:114)
            ├── std::fs::create_dir_all
            ├── serde_json::to_string_pretty
            ├── std::fs::File::create  +  write_all  +  sync_data
            └── std::fs::rename (tmp → real)
```

### 5.8 `commands::rd_check_pending`

```
commands::rd_check_pending                            (commands.rs:538)
├── SidecarManager::request("rd_check_pending", ...)
├── ensure_ok (on failure)
├── if status == "completed":
│   ├── pending::remove                               (pending.rs:143)
│   │   ├── pending::load
│   │   └── pending::save
│   └── serde_json::from_value::<Vec<RdLink>>
├── if status == "missing":
│   └── pending::remove
└── else (pending):
    └── pending::update_status                        (pending.rs:152)
        ├── pending::load
        ├── chrono::Utc::now().to_rfc3339()
        └── pending::save (only if the id exists)
```

### 5.9 `commands::rd_save_token`

```
commands::rd_save_token                               (commands.rs:356)
├── secret_store::is_valid_rd_token (non-empty only)  (secret_store.rs:43)
├── secret_store::set_rd_token                        (secret_store.rs:62)
│   ├── keyring::Entry::new
│   └── keyring::Entry::set_password
│       (or delete_internal if empty)
├── SidecarManager::request("rd_set_token", ...)
└── ensure_ok
```

### 5.10 `commands::apply_legacy_import`

```
commands::apply_legacy_import                         (commands.rs:634)
├── validate_legacy_source                            (commands.rs:662)
├── legacy_import::preview                            (legacy_import.rs:347)
│   ├── read_env_for_preview → parse_env              (legacy_import.rs:312 / :94)
│   └── read_pending_count                            (legacy_import.rs:334)
│
├── if env_present: import_env_block                  (commands.rs:691)
│   ├── read_legacy_env                               (commands.rs:727)
│   │   └── spawn_blocking(std::fs::read_to_string(.env))
│   ├── legacy_import::parse_env
│   ├── (if token): import_rd_token                   (commands.rs:793)
│   │   ├── validate_legacy_rd_token                  (commands.rs:772)
│   │   ├── secret_store::set_rd_token
│   │   └── SidecarManager::request("rd_set_token", ...)
│   │       └── _err_code (on failure)
│   └── (if non-secret patch): import_env_settings_patch (commands.rs:830)
│       ├── app.store(store_path)                     (tauri-plugin-store)
│       ├── Store::get("settings")
│       │   (fallback: serde_json::to_value(Settings::default()))
│       ├── legacy_import::apply_settings_patch       (legacy_import.rs:401)
│       ├── blank_rd_api_token                        (commands.rs:878)
│       ├── settings::clamp_rd_settings (typed round-trip) (settings.rs:78)
│       ├── Store::set("settings", base)
│       ├── Store::save
│       └── (if Some(saved_settings)): push_imported_settings (commands.rs:737)
│           ├── settings_push_body → blank_rd_api_token (commands.rs:753)
│           ├── SidecarManager::request("update_settings", ...)
│           └── settings_push_warning → _err_code (on non-ok) (commands.rs:759)
│
├── if cookies_present: import_cookies_block          (commands.rs:888)
│   ├── std::fs::create_dir_all
│   └── std::fs::copy(src_cookies, dst_cookies)
│
└── if pending_present: import_pending_block          (commands.rs:927)
    ├── std::fs::read_to_string
    ├── pending::load (existing)                      (pending.rs:92)
    ├── legacy_import::merge_legacy_pending           (legacy_import.rs:277)
    │   ├── serde_json::from_str::<Vec<Value>>
    │   └── legacy_import::sanitize_pending_entry x N (legacy_import.rs:216)
    │       └── chrono::Utc::now (only if added_at empty)
    └── pending::save                                 (pending.rs:114)
```

### 5.11 Cookie commands

```
commands::migrate_cookies_now                         (commands.rs:1074)
├── lib::migrate_cookies_from_file                    (lib.rs:112)
├── push_cookies_to_sidecar (only if migrated)        (commands.rs:1145)
│   └── SidecarManager::request("set_cookies", {cookies}) + ensure_ok
└── cookies_status_for                                (commands.rs:1038)
    └── cookie_store::get_cookies → cookies_status_with_keyring

commands::save_cookies                                (commands.rs:1132)
├── save_cookies_local                                (commands.rs:1112)
│   ├── validate_cookies_input → cookie_store::check_cookies_format
│   ├── cookie_store::set_cookies
│   └── std::fs::remove_file(cookies.txt) (best-effort)
├── push_cookies_to_sidecar
└── cookies_status_for

commands::clear_cookies                               (commands.rs:1203)
├── clear_cookies_local                               (commands.rs:1173)
│   ├── std::fs::remove_file(cookies.txt)  (NotFound ok)
│   └── cookie_store::delete_cookies
├── push_cookies_to_sidecar("")  → on Err: "cookies_cleared_sidecar_stale: <e>"
└── cookies_status_for
```

---

## 6. Notable Findings / Oddities

- ~~**`forget_magnets` does not check `resp.ok`**~~ **RESOLVED M9 Phase 0-A**: `commands::forget_magnets` now calls `ensure_ok(&resp)?` ([commands.rs:150](app/src-tauri/src/commands.rs:150)).
- **No Rust-side logging crate**. Diagnostics are `eprintln!` in the cookie/token migration paths plus the `.expect` panic; in a windowed release build stderr is invisible. Sidecar stderr is dropped on the floor. The comment at [sidecar_manager.rs:232-234](app/src-tauri/src/sidecar_manager.rs:232) acknowledges this as a deferred M6 item.
- **No graceful sidecar shutdown message**. `SidecarInner`'s `Drop` kills the child; no goodbye is sent.
- **No sidecar respawn on crash**. Once `mark_dead` fires (timeout / EOF / protocol corruption), all subsequent `request(...)` calls error with `"sidecar is dead: <reason>"` and the user has to restart the app.
- **Five independent `temp_dir`-style test helpers** in [lib.rs:230](app/src-tauri/src/lib.rs:230), [pending.rs:181](app/src-tauri/src/pending.rs:181), [legacy_import.rs:457](app/src-tauri/src/legacy_import.rs:457), [commands.rs:1474](app/src-tauri/src/commands.rs:1474), [commands.rs:1736](app/src-tauri/src/commands.rs:1736) (plus `Scratch` in `build_support.rs` and an inline tempdir in `read_legacy_env_reads_the_file_and_reports_a_missing_one`, [commands.rs:1357](app/src-tauri/src/commands.rs:1357)) — duplicated rather than factored into a shared dev-dep or test util.
- **`STORE_FILE` is defined twice** — private `const` in [lib.rs:28](app/src-tauri/src/lib.rs:28) and private in [settings.rs:13](app/src-tauri/src/settings.rs:13). `import_env_settings_patch` uses `crate::STORE_FILE` while `settings.rs` uses its own. Mild duplication risk if one is changed and the other isn't.
- **`COOKIES_MAX_BYTES` is defined twice** with different types — `u64` in [lib.rs:36](app/src-tauri/src/lib.rs:36), `usize` in [cookie_store.rs:32](app/src-tauri/src/cookie_store.rs:32).
- **`pending::FILE_NAME` and `legacy_import::LEGACY_PENDING_FILE`** both hardcode `"pending_torrents.json"`. Similar duplication for `cookies.txt` (`commands::COOKIES_FILE_NAME` vs `legacy_import::LEGACY_COOKIES_FILE` vs the literal in `lib::load_cookies`).
- ~~**Stale in-source comments about cookie storage**~~ — fixed 2026-10-16: [secret_store.rs:14-15](app/src-tauri/src/secret_store.rs:14) and the M7b banner at [commands.rs:965-968](app/src-tauri/src/commands.rs:965) now point at `cookie_store`.
- **Legacy cookie import still copies to `cookies.txt`**: `import_cookies_block` writes the plaintext file and warns "restart the app", but the file is migrated into the keyring by the next `migrate_cookies_now` (frontend on-mount refresh) or handshake.
- **`update_settings` push to sidecar is not automatic after `write_settings`**. The frontend must also call `update_sidecar_settings` for the running daemon to pick up the change. The one Rust-side push is `apply_legacy_import`'s `.env` settings block, which calls `update_settings` itself after saving (`push_imported_settings`).
- **Tests at [legacy_import.rs:472](app/src-tauri/src/legacy_import.rs:472) (and :556, :658) reconstruct `"RD_API_TOKEN"`** as `["RD_API", "TOKEN"].join("_")`. Appears to be intentional — keeps the literal string out of grep-able source for auditing.
- **`block_on` during `.setup`** ([lib.rs:407](app/src-tauri/src/lib.rs:407)). The sidecar handshake is performed on the setup thread; any slowness there (bounded by the 60 s request timeout) delays window-open. Reasonable given the rest of the app assumes the sidecar exists.
- **`_err_code` is named with a leading underscore** despite being used ([commands.rs:262](app/src-tauri/src/commands.rs:262); called by `ensure_ok`, `settings_push_warning` and `import_rd_token`). Usually that convention signals "intentionally unused" — a stylistic inconsistency rather than a bug.
- **`pending::save` calls `f.sync_data().ok()`** ([pending.rs:125](app/src-tauri/src/pending.rs:125)) — sync failures are ignored. Acceptable on Windows where the flush is best-effort, but worth noting.
- **`copy_rd_links_bulk` takes `AppHandle` but not `SidecarManager`** — it's the only `copy_*` command that doesn't go through the sidecar at all. The link strings are already on the frontend.
- **`rd_has_token` is async but does no awaiting**. Required by Tauri's command macro when `State<'_, _>` is involved — but this one doesn't even take state. The async signature is gratuitous; sync `pub fn rd_has_token() -> Result<RdHasTokenResult, String>` would work.
- **`tauri-plugin-dialog` is registered but unreachable from the WebView** — no `dialog:*` capability and no frontend import.

---

*End of Rust backend contract reference.*
