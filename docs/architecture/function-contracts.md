# Function Contracts & Call Traces — Index

**Branch**: `claude/docs-code-alignment-8xcd4e` · **Generated**: 2026-05-14 · **Last refreshed**: 2026-10-16 against HEAD `7c877a8` (release 0.3.1 + PR #11) — index, inventory, call graph and punch list re-verified against source. **Scope**: every function in the production Tauri/Svelte/Rust/Python sidecar path, plus historical reference for the retired Tk GUI under `legacy/`.

This document is the **entry point** to a per-layer reference set. Each layer file documents every function with: purpose, params/returns, side effects, errors, async behavior, and the **call trace** (which functions it invokes, including cross-language bridges like `invoke()` and sidecar stdio).

---

## How to read this doc

1. Start with the **cross-layer call graph** below — it shows how a user click in the Svelte UI ends up executing a Python function inside `sidecar.exe`.
2. Drill into the relevant **layer file** for full per-function contracts.
3. The **punch list** at the bottom summarizes oddities/bugs every agent flagged — useful as a refactor checklist.

---

## Layers

| # | Layer | File | Functions documented |
|---|---|---|---|
| 1 | Rust Tauri backend | [`contracts/rust-backend.md`](contracts/rust-backend.md) | 31 `#[tauri::command]` exports (28 in `commands.rs`, 3 in `settings.rs`) + all internal helpers across 10 runtime `.rs` files, plus build-script `build.rs` / `build_support.rs` |
| 2 | Svelte/TS frontend lib | [`contracts/frontend-lib.md`](contracts/frontend-lib.md) | every export + internal helper across `magnetUtils.ts`, `rdPriority.ts`, `rdSender.ts`, `scraper.ts`, `settingsValidation.ts`, `errText.ts`, `flashAction.ts`, `types.ts`, `main.ts` |
| 3 | `App.svelte` UI monolith | [`contracts/app-svelte.md`](contracts/app-svelte.md) | ~65 functions, ~56 `$state` vars, 27 `$derived`, 36 `invoke()` call sites over 28 distinct commands |
| 4 | Sidecar runtime daemon | [`contracts/sidecar-runtime.md`](contracts/sidecar-runtime.md) | live `sidecar/sidecar.py` JSONL daemon, all helpers + command handlers |
| 5 | Sidecar build pipeline | [`contracts/sidecar.md`](contracts/sidecar.md) | `build_sidecar.py` (PyInstaller packaging). The argv-style `driver_rust` spike harness was removed in M9 Phase 8-C. |
| 6 | Python live + retired legacy | [`contracts/python-legacy.md`](contracts/python-legacy.md) | `app_logging.py`, `realdebrid.py`, `javdb_scraper.py` (live in sidecar) + retired-overview for `legacy/javdb_magnet_gui.py` |

**Coverage**: production runtime + build-time support + retired legacy references, split across the layer documents above. (Per-file source/doc line counts are not pinned here — they drift on every refactor; check the actual files when an exact number is needed.)

---

## Source inventory and split decision

Files are categorized into **5 explicit buckets** by their role in product execution. The first three buckets (production runtime, build script, legacy Python) own the contracts in this reference. The last two (spike/prototype, tests) are **NOT** product contract owners — they're either scratch space or regression references for the production contracts.

### Bucket 1 — Production runtime (contract owners)

Code that actually executes when an end-user runs `javdbmagnet.exe` and clicks something.

| Layer | Files | Doc |
|---|---|---|
| Rust Tauri backend | `app/src-tauri/src/{main.rs,lib.rs,commands.rs,cookie_store.rs,legacy_import.rs,path_manager.rs,pending.rs,secret_store.rs,settings.rs,sidecar_manager.rs}` | [`contracts/rust-backend.md`](contracts/rust-backend.md) |
| Frontend lib | `app/src/main.ts`, `app/src/lib/{magnetUtils,rdPriority,rdSender,scraper,settingsValidation,errText,flashAction,types}.ts` | [`contracts/frontend-lib.md`](contracts/frontend-lib.md) |
| Frontend UI monolith | `app/src/App.svelte` | [`contracts/app-svelte.md`](contracts/app-svelte.md) |
| Sidecar runtime daemon | `sidecar/sidecar.py` | [`contracts/sidecar-runtime.md`](contracts/sidecar-runtime.md) |
| JavDB scraper library | `javdb_scraper.py` (M9; imported by sidecar daemon + tests; pure HTTP+parse, zero Tk/app_logging deps) | [`contracts/python-legacy.md`](contracts/python-legacy.md) §`javdb_scraper.py` |
| RD client + logging helpers | `realdebrid.py`, `app_logging.py` (imported by sidecar daemon) | [`contracts/python-legacy.md`](contracts/python-legacy.md) |
| RD outcome log | `rd_outcome_log.py` (imported by sidecar daemon; appends `rd_outcomes.jsonl` next to `debug.log`) | [`contracts/sidecar-runtime.md`](contracts/sidecar-runtime.md) §1 + [spec](../specs/2026-08-01-rd-outcome-log.md) |

### Bucket 2 — Build scripts (contract owners, build-time only)

Code that runs at build/packaging time, not at user runtime. Contracts matter because changing them affects what ships.

| Layer | Files | Doc |
|---|---|---|
| Rust build script | `app/src-tauri/build.rs`, `app/src-tauri/build_support.rs` (`has_integration_tests`; also compiled into the lib unit tests via `#[path]` in `lib.rs`) | Documented in [`rust-backend.md`](contracts/rust-backend.md) |
| Sidecar packaging | `spikes/pyinstaller_sidecar/build_sidecar.py` | [`contracts/sidecar.md`](contracts/sidecar.md) |
| Frontend config | `app/vite.config.ts`, `app/svelte.config.js`, `app/src/vite-env.d.ts` | Noted in [`frontend-lib.md`](contracts/frontend-lib.md); no business logic |
| Release pipeline | `scripts/build-release.ps1` (+ `scripts/release-scan-allowlist.txt`, the only path excluded from its source-secret scan), `scripts/test-release-scan.ps1` (executable Red tests for that scan), `scripts/verify-windows-build.ps1` (Windows pre/post-build gate; does not package) | Self-documenting; sequenced in the README of [`contracts/sidecar.md`](contracts/sidecar.md) |
| Outcome-log analysis | `scripts/rd_log_report.py` | Offline only — never imported by the app. This is where the *hypotheses* live: it carries its own copy of the prefix list and resolution regex so alternative rules can be scored against existing logs without a format change. Divergence from `rdPriority.ts` is the intended use, not a defect. |
| Wiki citation check | `scripts/verify_wiki_citations.py` | Dev/CI tooling only — checks `.agents/wiki/patterns/*.md` citations against source; never imported by the app. |

### Bucket 3 — Retired Python (historical reference only)

Pre-Tauri implementation, fully **retired in M9**. Kept in the repo under `legacy/` so future readers can study the original Tk UX, but no longer bundled into `sidecar.exe` and not imported by any production module.

| Files | Doc |
|---|---|
| `legacy/javdb_magnet_gui.py` (moved from root in M9 Phase 5-B; pre-Tauri Tk desktop app; only `create_session`/`fetch_magnets`/`parse_size_gb`/`parse_file_count` ever mattered to the sidecar and those four have been promoted to `javdb_scraper.py`) | [`contracts/python-legacy.md`](contracts/python-legacy.md) §`legacy/javdb_magnet_gui.py` (overview) |
| `legacy/_legacy_env.py` (`load_env` `.env` parser moved out of `realdebrid.py` for F-06; only caller is `legacy/javdb_magnet_gui.py`, guarded by `tests/test_legacy_env.py`), `legacy/__init__.py` (package docstring: do not import `legacy.*` from production) | — |

**Removed in M9**:
- `javdb_magnet.py` — standalone CLI scraper, never imported by anything; deleted in Phase 2 (M9 phase commits were later squashed into `31a54ca`)
- `build.py` — legacy Tk PyInstaller build script, replaced by `scripts/build-release.ps1` + `spikes/pyinstaller_sidecar/build_sidecar.py`; deleted in Phase 2

**Note**: `app_logging.py` and `realdebrid.py` were originally listed in this bucket as "legacy", but they remain **live** in the sidecar runtime and are now classified under Bucket 1.

### Bucket 4 — Spike / prototype (NOT contract owners)

Exploratory code from earlier milestones. Useful for understanding how decisions were reached, but **not authoritative** for the live runtime. The `pyinstaller_sidecar` spike is the one exception — its `build_sidecar.py` is actively used (see Bucket 2), while the rest is reference material only.

| Path | Status | Notes |
|---|---|---|
| `spikes/pyinstaller_sidecar/driver_rust/` | **Removed in M9 (Phase 8-C)** | Argv-style spike harness from the M3 era (`<exe> fetch-javdb <url>`). Incompatible with the live JSONL daemon protocol and could not smoke-test the M9 sidecar; deleted to stop misleading future debugging. The live protocol contract is in [`sidecar-runtime.md`](contracts/sidecar-runtime.md). |
| `spikes/python_sidecar_protocol/` | **Retired in M9 (Phase 4)** | The original spike `sidecar.py` + `driver_rust/` were deleted; only `NOTES.md` remains as historical record (marked RETIRED). The live runtime is now `sidecar/sidecar.py`. |
| `spikes/rust_fetch_javdb/`, `spikes/rquest_fetch_javdb/` | **Removed in M9 (Phase 2)** | Native Rust JavDB-fetch experiments that were closed as not-viable (reqwest TLS fingerprint blocked by Cloudflare; rquest Windows build chain issue). Both spike directories were deleted; design decisions remain documented in `docs/superpowers/specs/2026-05-10-tauri-rewrite-design.md`. |

**Rule for refactors**: when changing sidecar protocol behavior, update `sidecar/sidecar.py` + `sidecar-runtime.md` + the relevant Rust caller. Do NOT treat the spike driver as authoritative.

### Bucket 5 — Tests (NOT contract owners; regression references)

Tests assert behavior; they do not define it. Treat them as guardrails for the contracts in Buckets 1–3.

| Path | Role |
|---|---|
| `tests/test_core_logic.py` | 41 unit tests over `pick_files` (4 strategies), `_extract_code`, `_filename_matches_code` (from `realdebrid.RealDebrid`), `parse_size_gb`, `parse_file_count` (from `javdb_scraper`), plus 2 `TestCiDependencySync` tests pinning `sonarcloud.yml` to the requirements files (43 total). **This is the regression bar** any Rust/JS port of the Python core must clear. |
| `tests/test_*.py` (other 12 files) | Sidecar protocol/settings (`test_sidecar_protocol.py`, `test_sidecar_settings.py`), scraper fetch, RD request/logging, `app_logging`, RD outcome log (+ e2e) and `scripts/rd_log_report.py`, legacy `.env` parser, `.ps1` encoding, wiki-citation checker. |
| `app/src/lib/*.test.ts`, `app/src/App.test.ts` | Vitest specs over the frontend lib modules (incl. `mainEntry.test.ts` for `main.ts`) and `App.svelte` component flows with a mocked `invoke`. Document the "happy path" + edge cases each helper is contracted to handle. |
| `app/src-tauri/src/**/#[cfg(test)] mod tests`, `app/src-tauri/tests/sidecar_command.rs` | Rust unit tests inside each backend module, plus one integration test that builds the real sidecar `Command` on tauri's `MockRuntime` without spawning. Several modules duplicate a `temp_dir()` helper (see punch list). |

### Out of analysis scope

| Path | Why excluded |
|---|---|
| `build/`, `dist/`, `dist.7z`, `*.spec`, `__pycache__/`, `target/`, `node_modules/` | Generated artifacts / package caches. |
| `release/`, `JavDBMagnet.spec` | Build output. |
| `cookies.txt`, `pending_torrents.json`, `.env`, `magnet.txt`, `logs/` | Runtime user data, not source. |
| `javdbmagnet.exe`, `sidecar.exe` (repo root), `architecture.json` / `lifecycle.json` / `workflow.json` | Committed release binaries and archify diagram specs (the rendered `.html` is gitignored and generated locally). |
| `vendor/wayland-scanner-0.31.10/` | Patched third-party crate wired in via `[patch.crates-io]` in `app/src-tauri/Cargo.toml`; not project logic. |
| `.agent-hooks/`, `.agents/`, `.claude/` | Agent tooling (hooks, skills, wiki), not product code. |

### Why split this way

Work was split by **execution boundary**: each bucket owns code with a homogeneous trust + lifecycle posture. Bucket 1 ships and runs at user-time; Bucket 2 runs at build-time; Bucket 3 is archival only (the live sidecar imports were reclassified into Bucket 1); Bucket 4 is scratch space; Bucket 5 is verification. Keeping the boundaries explicit prevents an agent (or a future refactor) from accidentally treating a spike driver or a test fixture as the source of truth for live behavior.

---

## Architectural shape (one-paragraph)

The app is a **3-tier Windows desktop application**: a Svelte 5 single-page UI (`App.svelte` + eight `lib/*.ts` modules) talks to a Rust Tauri backend (10 `.rs` modules, 31 `#[tauri::command]` exports) via `invoke()`; the Rust backend spawns and owns a long-running **PyInstaller-bundled Python sidecar** process (`sidecar.exe`) that performs all JavDB scraping and Real-Debrid REST traffic. There is **no Tauri event emission** from Rust and **no `listen(...)` subscription** from the frontend — progress for batch operations is driven by **JS-side callbacks** (`onProgress`) that the lib helpers call after each per-item `invoke()` returns. Cancellation is via `AbortSignal` checked at iteration boundaries (in-flight `invoke`s always complete). The sidecar contract is **process-based stdio JSON** (one request line in, one response line out).

---

## Cross-layer call graph

The eight user-visible flows, from UI click down to Python execution. File:line links point into the per-layer docs.

### Flow 1 — App boot

```
main.rs::main                                    (app/src-tauri/src/main.rs:4)
└── lib.rs::run                                  (app/src-tauri/src/lib.rs:385)
    └── Builder::default()
        ├── .plugin(store / shell / clipboard-manager / dialog)
        ├── .setup(|app| ...)
        │   ├── PathManager::new + ensure_dirs   (app/src-tauri/src/path_manager.rs)
        │   ├── load_handshake_inputs            (lib.rs:49)
        │   │   ├── load_cookies → migrate_cookies_from_file (cookies.txt → keyring)
        │   │   │                  else cookie_store::get_cookies
        │   │   ├── read <data_dir>/settings.json
        │   │   ├── secret_store::get_rd_token, else migrate_legacy_token
        │   │   └── commands::blank_rd_api_token(settings) — handshake never carries rd.api_token
        │   ├── block_on(SidecarManager::spawn_and_handshake)  (lib.rs:407) ⚠ blocks setup
        │   │   │                                (app/src-tauri/src/sidecar_manager.rs:205)
        │   │   ├── sidecar_command → app.shell().sidecar("sidecar") + JAVDB_LOG_DIR env
        │   │   ├── spawn child; async_runtime::spawn(stdout line reader → mpsc)
        │   │   ├── request("hello", { protocol_version: 1 })
        │   │   └── request("handshake", { cookies, rd_token, settings, paths })
        │   └── app.manage(PathManager) / app.manage(SidecarManager)
        └── .invoke_handler(generate_handler![...31 commands])
        ↓ webview opens, App.svelte mounts
App.svelte::onMount                              (app/src/App.svelte:230)
├── invoke('get_paths')              → settings::get_paths
├── loadAndApplySettings
│   └── invoke('read_settings')      → settings::read_settings
├── invoke('rd_has_token')           → commands::rd_has_token
├── reloadPendingSilently
│   └── invoke('pending_list')       → commands::pending_list
├── invoke('get_legacy_default_dir') → commands::get_legacy_default_dir
└── refreshCookiesStatus
    └── invoke('migrate_cookies_now') → commands::migrate_cookies_now
        (on error: invoke('get_cookies_status') → commands::get_cookies_status)
```

### Flow 2 — Scrape JavDB URLs

```
App.svelte::startScrape (click "開始擷取")       (app/src/App.svelte:322)
├── invoke('forget_magnets', { handleIds: staleIds }) — release replaced web-group handles
└── lib/scraper.ts::scrapeBatch                  (app/src/lib/scraper.ts:231)
    │   AbortSignal checked between urls; random delay + rate-limit retry
    └── for each url:
        ├── invoke('fetch_javdb', { url, batchId }) → commands::fetch_javdb (commands.rs:36)
        │   └── SidecarManager::request          (sidecar_manager.rs)
        │       ├── write JSON line to sidecar stdin
        │       └── await line on stdout channel
        │       ↓ over the pipe to sidecar.exe
        │       PyInstaller bundle entry:
        │           sidecar/sidecar.py::cmd_fetch_javdb   (contracts/sidecar-runtime.md)
        │           └── javdb_scraper::create_session   (javdb_scraper.py)   [M9: was javdb_magnet_gui]
        │           └── javdb_scraper::fetch_magnets    (javdb_scraper.py)
        │                 ├── curl_cffi.requests (Chrome-124 impersonation)
        │                 └── BeautifulSoup parse → list[magnet dict]
        │           └── intern full magnets → handle_id + redacted magnet
        ├── onProgress({ index, total, group })
        └── App.svelte: applyScrapeProgressForRun → groups[index-1] updated
```

`batchId` is stable across every URL and rate-limit retry in one `scrapeBatch` call, then
changes for the next call. The sidecar uses it to keep first-occurrence metadata within the
currently visible batch while allowing a shared manual/web handle to be reattributed after
`startScrape` replaces the old web groups.

### Flow 3 — Send batch to Real-Debrid

```
App.svelte::sendSelectedToRd (click "送出已勾選") (app/src/App.svelte:994)
├── rdSendTriage ($derived) → lib/rdPriority.ts::summarizeRdLikelihood — LOCAL triage, no IPC.
│   RD removed /torrents/instantAvailability in 2024, so the "will this hit
│   cache?" question is answered by heuristics on the row's own metadata.
│   low > 0 → confirmation panel first (全部送出 / 只送高機率 / 取消 → confirmSend);
│   low == 0 → straight through. Either way the send itself is runSendBatch.
└── runSendBatch                                 (app/src/App.svelte:1057)
    └── lib/rdSender.ts::sendBatch               (app/src/lib/rdSender.ts:149)
        └── for each item:
            ├── invoke('rd_send_magnet', { handleId, options: { strategy, min_size_mb, cache_wait, code, size_label } })
            │   → commands::rd_send_magnet       (commands.rs:443)
            │     └── SidecarManager::request("rd_send_magnet", ...)
            │         ↓ sidecar.exe
            │         sidecar.py::cmd_rd_send_magnet
            │         └── realdebrid.RealDebrid.process_magnet
            │             ├── add_magnet (POST /torrents/addMagnet)
            │             ├── poll torrent_info until cache_wait deadline
            │             ├── on waiting_files_selection → _select_files_during_wait
            │             │   └── pick_files (smart | video | largest | all)
            │             │       └── _extract_code / _filename_matches_code
            │             │   └── select_files
            │             └── downloaded → _collect_links → { status: "completed", links }
            │                 else → _build_pending_result → { status: "pending", ... }
            │         └── rd_outcome_log.log_send
            │     └── if pending → pending.rs::add (Rust-side; no frontend invoke)
            └── onProgress({ index, total, item })
```

### Flow 4 — Retry pending queue

```
App.svelte::retryAllPending  (~90 lines)         (app/src/App.svelte:1203)
└── lib/rdSender.ts::retryPending                (app/src/lib/rdSender.ts:311)
    └── for each pending entry:
        ├── invoke('rd_check_pending', { torrentId, strategy }) → commands::rd_check_pending (commands.rs:538)
        │   ├── SidecarManager::request("rd_check_pending", ...)
        │   │   ↓ sidecar.exe
        │   │   sidecar.py::cmd_rd_check_pending
        │   │   └── realdebrid.RealDebrid.check_torrent
        │   │   → { status: "completed" | "pending" | "missing" }
        │   └── Rust persists: completed/missing → pending.rs::remove;
        │                      pending → pending.rs::update_status
        └── onProgress({ index, total, torrent_id, entry, result })
↑ back to App.svelte:
  - per-event reconciliation via lib/rdSender.ts::applyRetryEventToProgressRows
  - reloadPendingSilently → invoke('pending_list'), then a summary message;
    completed links → invoke('copy_rd_links_bulk', { links })
```

### Flow 5 — Paste magnets (manual entry)

```
App.svelte::registerPastedMagnets  (~106 lines — refactor hotspot) (app/src/App.svelte:431)
├── lib/scraper.ts::parseMagnetBatch → list of magnet strings
├── invoke('register_magnets', { magnets })     — one call for the whole batch
│   → commands::register_magnets                 (commands.rs:113)
│     └── SidecarManager::request("register_magnets", ...)
│         ↓ sidecar.exe
│         sidecar.py::cmd_register_magnets → _intern_magnet (handle table) + manual_meta
└── synthesize ScrapedGroup with url = `manual://${Date.now()}`
    ↑ sentinel recognized everywhere through lib/magnetUtils.ts::isManualGroup
```

### Flow 6 — Save settings

```
App.svelte::saveSettings                         (app/src/App.svelte:1532)
├── settingsValid ($derived over lib/settingsValidation.ts::validateSettingsDraft → Record<field, error>)
├── invoke('write_settings', { settings })       → settings::write_settings
│   └── tauri-plugin-store → <data_dir>/settings.json (%APPDATA%\JavDBMagnet on Windows)
└── invoke('update_sidecar_settings', { settings }) → commands::update_sidecar_settings
                                                   └── SidecarManager::request("update_settings", ...)
   ⚠ Rust does NOT chain these — frontend must call both. (See punch list.) The one
     Rust-side update_settings push is the legacy .env import (Flow 7).
```

### Flow 7 — Legacy import (.env / cookies.txt / pending_torrents.json)

```
App.svelte::applyLegacyImportConfirmed (settings panel) (app/src/App.svelte:1580)
└── invoke('apply_legacy_import', { sourceDir })
    → commands::apply_legacy_import              (app/src-tauri/src/commands.rs:634)
      ├── validate_legacy_source (non-empty dir, not the data dir)
      ├── legacy_import::preview                 (app/src-tauri/src/legacy_import.rs)
      ├── import_env_block → read_legacy_env (spawn_blocking) → legacy_import::parse_env
      │   ├── RD_API_TOKEN → secret_store::set_rd_token + sidecar rd_set_token
      │   │                  (sidecar: token change → _close_rd_session)
      │   └── settings patch → import_env_settings_patch → tauri-plugin-store settings.json
      │       └── on save: push_imported_settings → sidecar update_settings
      │           (settings_push_body re-blanks rd.api_token; failure → report.warnings)
      ├── import_cookies_block → copy cookies.txt into data dir (restart warning)
      └── import_pending_block → legacy_import::merge_legacy_pending → pending.rs::save
↑ back to App.svelte: env_imported → loadAndApplySettings; if the settings editor is open,
  settingsDraft = freshSettingsDraft(updated)
```

### Flow 8 — RD token test / save / clear (settings panel)

```
App.svelte::rdTestToken (click "測試連線")        (app/src/App.svelte:873)
└── invoke('rd_test_token', { token })           → commands::rd_test_token (commands.rs:329)
    └── rd_test_token_with                       (commands.rs:338)
        ├── check_candidate_token                (commands.rs:316)
        │   "" → Err("rd_no_token"); fails secret_store::is_valid_rd_token
        │   → Err("rd_token_format_invalid")  — returned before any sidecar RPC
        └── SidecarManager::request("rd_user", { token })
            ↓ sidecar.exe
            sidecar.py::cmd_rd_user — same format gate again (code rd_token_format_invalid,
            │                         before any HTTP), then
            └── _rd_client(token_override).user() → GET /user
↑ errors render via lib/rdSender.ts::rdErrorMessage(code)

App.svelte::rdSaveToken                          (app/src/App.svelte:889)
└── invoke('rd_save_token') → is_valid_rd_token → secret_store::set_rd_token
    → sidecar rd_set_token (token changed → _close_rd_session); then invoke('rd_check_user')
App.svelte::rdClearToken                         (app/src/App.svelte:914)
└── invoke('rd_clear_token') → secret_store::delete_rd_token
    → sidecar rd_set_token { token: null } → _close_rd_session
```

---

## Bridge surfaces

### Tauri command surface (Rust ↔ JS)

31 `#[tauri::command]` exports (28 in `commands.rs`, 3 in `settings.rs`) registered in [`lib.rs::run`](contracts/rust-backend.md). The frontend uses all 31 names (3 from `lib/*`: `fetch_javdb`, `rd_send_magnet`, `rd_check_pending`; 28 from `App.svelte`). See [rust-backend.md](contracts/rust-backend.md) for the full table.

### Sidecar command surface (Rust ↔ Python via stdio JSON)

Per the live Rust caller, the sidecar accepts a JSON line `{ "cmd": "...", "request_id": "...", ...command_fields }` and replies with `{ "ok": bool, "request_id": "...", ... }`. See [`contracts/sidecar-runtime.md`](contracts/sidecar-runtime.md) for full per-command contracts.

- `hello`, `handshake`, `ping`
- `fetch_javdb`
- `resolve_magnet`, `resolve_magnets`, `forget_magnets`, `register_magnets`
- `update_settings`, `set_cookies`, `cancel`, `shutdown`
- `rd_user`, `rd_set_token`
- `rd_send_magnet`
- `rd_check_pending`

The Rust side sends every command above except `cancel` and `shutdown`, which the sidecar accepts but no Rust caller issues. [`contracts/sidecar.md`](contracts/sidecar.md) covers only the PyInstaller build; the argv-style spike driver it used to describe was deleted in M9 Phase 8-C.

### Event surface (Tauri events)

**Empty.** No Rust-side `emit()`, no JS-side `listen()`. Progress is JS-driver-based via callbacks.

---

## Module dependency graph

```
Rust backend (app/src-tauri/src/):
  main.rs ─→ lib.rs ─→ {commands, cookie_store, sidecar_manager, settings,
                        secret_store, path_manager, pending, legacy_import}
  commands.rs  ─→ {sidecar_manager, pending, settings, secret_store, cookie_store,
                   legacy_import, path_manager,
                   lib::{STORE_FILE, migrate_cookies_from_file}}
  legacy_import.rs ─→ {pending}
  settings.rs ─→ {path_manager, sidecar_manager::{MIN,MAX}_RD_CACHE_WAIT_SECS}
  secret_store.rs, cookie_store.rs ─→ (keyring)
  sidecar_manager.rs ─→ (tauri_plugin_shell sidecar Command, tokio mpsc)

Frontend (app/src/):
  main.ts ─→ App.svelte
  App.svelte ─→ {lib/scraper, lib/rdSender, lib/magnetUtils, lib/rdPriority,
                 lib/settingsValidation, lib/errText, lib/flashAction, lib/types,
                 @tauri-apps/api/core::invoke, @tauri-apps/plugin-shell::open}
  lib/{scraper,rdSender} ─→ {lib/errText, lib/types, @tauri-apps/api/core::invoke}
  lib/{settingsValidation,rdPriority} ─→ lib/types only
  lib/flashAction ─→ svelte/reactivity
  lib/magnetUtils ─→ lib/rdPriority ─→ lib/types
  ↑ 2026-08-01: the lib layer is no longer entirely flat. magnetUtils imports
    rdPriority (isHdRow / pickRdCandidate) so "HD" and the RD-cache heuristic
    have ONE definition. rdPriority must stay a leaf — that is why its
    same-date tie-break is an injected comparator instead of a parseSizeGb
    import, which would close a cycle. Apart from scraper/rdSender importing
    errText, every other lib module is still a leaf.

Sidecar (PyInstaller bundle, runtime):
  sidecar/sidecar.py ─→ {app_logging::setup_logging (in main),
                         realdebrid::{RealDebrid, RealDebridError} (lazy local import),
                         rd_outcome_log,
                         javdb_scraper::{create_session, fetch_magnets,
                                         parse_size_gb}}
  realdebrid.py ─→ app_logging::get_logger
  ↑ M9 Phase 5-A: javdb_scraper.py provides the four pure HTTP/parse helpers
    extracted from the retired javdb_magnet_gui.py. The sidecar bundle no
    longer pulls in Tk/tkinter/ttk/messagebox/DPI helpers (-3.02 MiB).

Retired (M9 Phase 5-B; lives under legacy/ for historical reference):
  legacy/javdb_magnet_gui.py — pre-Tauri Tk desktop app; no production importer.
                               Only `tests/test_app_logging.py` still touches it
                               via importlib (lazy-logging contract guard).
```

---

## Punch list — findings flagged during analysis

Each agent surfaced refactor-relevant oddities. Consolidated here.

### Rust backend (`rust-backend.md` "Notable Findings")

- ~~**`forget_magnets` skips the `ok` check**~~ **RESOLVED M9 Phase 0-A**: updated `commands.rs` to call `ensure_ok(&resp)?`. [`commands.rs:150`](../../app/src-tauri/src/commands.rs#L150)
- **No Rust-side log file.** Sidecar stderr is dropped on the floor ([`sidecar_manager.rs:231`](../../app/src-tauri/src/sidecar_manager.rs#L231)); the sidecar writes its own `debug.log` via `app_logging` (Rust forwards `JAVDB_LOG_DIR`). Rust's only diagnostics are six `eprintln!` calls in `lib.rs` (cookie handshake/migration + legacy-token migration, [`lib.rs:93`](../../app/src-tauri/src/lib.rs#L93)–[`194`](../../app/src-tauri/src/lib.rs#L195)), invisible from the windows-subsystem release exe.
- ~~**`SidecarManager` has no `Drop`**~~ — `SidecarInner` now implements `Drop` (kills the child) ([`sidecar_manager.rs:82`](../../app/src-tauri/src/sidecar_manager.rs#L82)). **Still no respawn-on-crash**: any timeout / closed stdout / parse error / `request_id` mismatch calls `mark_dead`, and every later `request()` fails with `sidecar is dead: …` until the user restarts the app.
- **`block_on` during `.setup`** for the sidecar handshake. Any sidecar slowness delays window open. [`lib.rs:407`](../../app/src-tauri/src/lib.rs#L407)
- **`STORE_FILE` is defined twice** — [`lib.rs:28`](../../app/src-tauri/src/lib.rs#L28) (also used by `commands.rs` as `crate::STORE_FILE`) and [`settings.rs:13`](../../app/src-tauri/src/settings.rs#L13). Same for `pending_torrents.json` (`pending.rs` `FILE_NAME`, `legacy_import.rs` `LEGACY_PENDING_FILE`) and `cookies.txt` (`lib.rs` literal, `commands.rs` `COOKIES_FILE_NAME`, `legacy_import.rs` `LEGACY_COOKIES_FILE`).
- **`update_sidecar_settings` is not chained from `write_settings`** — frontend must call both. Silent footgun if a future caller only calls one. (The legacy `.env` import is the exception: `push_imported_settings` sends `update_settings` from Rust after saving.)
- **`rd_has_token` is gratuitously `async`** — no `await`, no `State<'_, _>`; it only calls the synchronous `secret_store::get_rd_token`.
- **`_err_code` has a leading underscore despite being used** — called by `ensure_ok` (which most commands go through) and directly by `import_rd_token` and `settings_push_warning`. Style inconsistency.
- **Duplicated `temp_dir` test helpers** — `pending.rs`, `legacy_import.rs`, and two separate copies in `commands.rs` (`tests_m7b`, `tests_cookies_e2e`), plus the `temp_data_dir` variant in `lib.rs`.
- **Tests at [`legacy_import.rs:472`](../../app/src-tauri/src/legacy_import.rs#L472)** (also lines 556, 658) build the key as `["RD_API", "TOKEN"].join("_")` to keep the token-assignment line from appearing verbatim in test fixtures (audit hygiene). The parser itself still matches the literal `"RD_API_TOKEN"` at line 154.

### Frontend lib (`frontend-lib.md`)

- ~~**`sortRows(column="code")` actually sorts by `name`**~~ **RESOLVED M9 Phase 3**: `"code"` removed from `SortColumn` union type. [`magnetUtils.ts`](../../app/src/lib/magnetUtils.ts)

### App.svelte (`app-svelte.md` "Refactor hotspots")

- **`retryAllPending` (~90 lines)** — mixes iteration/accumulators, post-loop disk refresh, and a multi-fragment clipboard summary. ~~Duplicates the `for (i; i<rdSendProgress.length; i++)` reconciliation loop body across `completed` and `missing` branches.~~ **RESOLVED**: both branches now call `applyRetryEventToProgressRows` ([`rdSender.ts:269`](../../app/src/lib/rdSender.ts#L269)).
- **Status-message state is fragmented across 8+ variables** (`statusMessage`, `pingMessage`, `rdMessage`, `registerStatus`, `pendingMessage`, `cookiesError`+`cookiesMessage`, `settingsMessage`+`settingsMessageKind`, `legacyError`) in two competing shapes (plain string vs `{kind, text}`). Section rendering is inconsistent and hard to extract.
- **`registerPastedMagnets` (~106 lines)** — packs parse / error-heuristic / invoke / cross-group dedupe / synthetic-group construction inline. ~~The `url.startsWith('manual://')` sentinel is **also** load-bearing in `buildVisibleSendItems`~~ **RESOLVED** for the sentinel: every check now goes through `isManualGroup` ([`magnetUtils.ts:50`](../../app/src/lib/magnetUtils.ts#L50)) and `buildVisibleSendItems` no longer exists. The function length and synthetic-group construction (`buildSyntheticPasteGroup()`) remain open.

### Sidecar runtime (`sidecar-runtime.md`)

- ~~**`cmd_forget_magnets` ignores `handle_ids`**~~ **RESOLVED M9 Phase 0-B**: updated `cmd_forget_magnets` in `sidecar.py` to support optional `handle_ids` subset deletion, reverse index cleanup, and element type validation. [`sidecar.py:639`](../../sidecar/sidecar.py#L639)
- **`cmd_cancel` is an acknowledgement only** — it cannot interrupt in-flight JavDB or RD work because the daemon loop is synchronous. User-visible cancellation is batch-boundary cancellation in JS (`AbortSignal`), not Python-level cancellation; no Rust caller sends `cancel` at all. [`sidecar.py:780`](../../sidecar/sidecar.py#L780)
- **`main` accepts `--daemon` but always runs daemon mode** — harmless now, but the CLI shape implies a mode switch that no longer exists. [`sidecar.py:1374`](../../sidecar/sidecar.py#L1374)

### Sidecar build/driver (`sidecar.md`)

- ~~**Stale constants in `driver_rust`** — `SIDECAR_NAME = "sidecar.exe"` and the path walker probes `dist/<SIDECAR_NAME>`, but `build_sidecar.py` (post-M3) writes `sidecar-x86_64-pc-windows-msvc.exe` to `app/src-tauri/binaries/`. Auto-discovery is therefore broken in-tree; the driver only works via `SIDECAR_EXE` env var or a manual rename. Drift not flagged anywhere.~~ **RESOLVED M9 Phase 8-C**: entire `driver_rust/` deleted; not replaced (CI smoke-testing of `sidecar.exe` is a separate future workitem).
- **`clean()` is broader than its name suggests** — it wipes the entire `app/src-tauri/binaries/` directory, not just the sidecar artifact. Safe today; latent footgun.

### Python legacy (`python-legacy.md`)

- ~~**`javdb_magnet.py` is orphan/dead code** in the repo — no importer.~~ **RESOLVED M9 Phase 2** (squashed into `31a54ca`): file deleted.
- ~~**~1,300 lines of widget code in `javdb_magnet_gui.py`** is bundled into `sidecar.exe` but never executed at runtime. Only `create_session` and `fetch_magnets` are imported by the sidecar entry. Removing the widget classes (or splitting the file) would shrink the .exe and remove confusion.~~ **RESOLVED M9 Phase 5-A/5-B**: four pure HTTP/parse helpers extracted to `javdb_scraper.py` (squashed into `31a54ca`); sidecar bundle no longer pulls in Tk (-3.02 MiB). The full Tk source moved to `legacy/javdb_magnet_gui.py` (squashed into `31a54ca`) and is no longer in the bundle.
- **The behavioral contract the port must preserve** is captured in `tests/test_core_logic.py` — unit tests over `parse_size_gb`, `parse_file_count` (now imported from `javdb_scraper`), `_extract_code`, `_filename_matches_code`, and `pick_files`'s 4 strategies (from `realdebrid.RealDebrid`). Treat these as the regression bar for any Rust/JS reimplementation.

---

## How to keep this current

When refactoring:

1. If a function moves, update its file:line in the matching layer doc.
2. If an `invoke()` command is added/removed/renamed, update both the Rust layer (command list) and the JS layer (call sites), plus the cross-layer flow that uses it.
3. If a sidecar command changes shape, update `sidecar-runtime.md` AND the relevant Rust caller in `rust-backend.md`; update `sidecar.md` only when the build pipeline changes.
4. Punch-list items: when resolved, strike them with `~~strikethrough~~` rather than deleting — keeps the history of what was once a problem.
5. To regenerate from scratch: re-run the layer analyses for Rust backend, frontend lib, App.svelte, sidecar runtime, sidecar build/driver, and Python legacy; they were designed to be idempotent against a clean working tree.
