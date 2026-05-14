# Function Contracts & Call Traces — Index

**Branch**: `refactor/m9-simplify` · **Generated**: 2026-05-14 · **Last refreshed**: post M9 Phase 5-B (HEAD `9c3612d`) — index reflects the renames/deletes from Phase 2 / 4 / 5-A / 5-B. **Scope**: every function in the production Tauri/Svelte/Rust/Python sidecar path, plus historical reference for the retired Tk GUI under `legacy/`.

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
| 1 | Rust Tauri backend | [`contracts/rust-backend.md`](contracts/rust-backend.md) | 28 `#[tauri::command]` exports + all internal helpers across 9 runtime `.rs` files, plus build-script `build.rs` |
| 2 | Svelte/TS frontend lib | [`contracts/frontend-lib.md`](contracts/frontend-lib.md) | every export + internal helper across `magnetUtils.ts`, `rdSender.ts`, `scraper.ts`, `settingsValidation.ts`, `types.ts`, `main.ts` |
| 3 | `App.svelte` UI monolith | [`contracts/app-svelte.md`](contracts/app-svelte.md) | ~35 functions, ~50 `$state` vars, 10 `$derived`, 24 distinct `invoke()` call sites |
| 4 | Sidecar runtime daemon | [`contracts/sidecar-runtime.md`](contracts/sidecar-runtime.md) | live `sidecar/sidecar.py` JSONL daemon, all helpers + command handlers |
| 5 | Sidecar build + dev driver | [`contracts/sidecar.md`](contracts/sidecar.md) | `build_sidecar.py` + the historical `driver_rust/src/main.rs` spike harness |
| 6 | Python live + retired legacy | [`contracts/python-legacy.md`](contracts/python-legacy.md) | `app_logging.py`, `realdebrid.py`, `javdb_scraper.py` (live in sidecar) + retired-overview for `legacy/javdb_magnet_gui.py` |

**Coverage**: production runtime + build-time support + retired legacy references, split across the layer documents above. (Per-file source/doc line counts are not pinned here — they drift on every refactor; check the actual files when an exact number is needed.)

---

## Source inventory and split decision

Files are categorized into **5 explicit buckets** by their role in product execution. The first three buckets (production runtime, build script, legacy Python) own the contracts in this reference. The last two (spike/prototype, tests) are **NOT** product contract owners — they're either scratch space or regression references for the production contracts.

### Bucket 1 — Production runtime (contract owners)

Code that actually executes when an end-user runs `javdbmagnet.exe` and clicks something.

| Layer | Files | Doc |
|---|---|---|
| Rust Tauri backend | `app/src-tauri/src/{main.rs,lib.rs,commands.rs,legacy_import.rs,path_manager.rs,pending.rs,secret_store.rs,settings.rs,sidecar_manager.rs}` | [`contracts/rust-backend.md`](contracts/rust-backend.md) |
| Frontend lib | `app/src/main.ts`, `app/src/lib/{magnetUtils,rdSender,scraper,settingsValidation,types}.ts` | [`contracts/frontend-lib.md`](contracts/frontend-lib.md) |
| Frontend UI monolith | `app/src/App.svelte` | [`contracts/app-svelte.md`](contracts/app-svelte.md) |
| Sidecar runtime daemon | `sidecar/sidecar.py` | [`contracts/sidecar-runtime.md`](contracts/sidecar-runtime.md) |
| JavDB scraper library | `javdb_scraper.py` (M9; imported by sidecar daemon + tests; pure HTTP+parse, zero Tk/app_logging deps) | [`contracts/python-legacy.md`](contracts/python-legacy.md) §`javdb_scraper.py` |
| RD client + logging helpers | `realdebrid.py`, `app_logging.py` (imported by sidecar daemon) | [`contracts/python-legacy.md`](contracts/python-legacy.md) |

### Bucket 2 — Build scripts (contract owners, build-time only)

Code that runs at build/packaging time, not at user runtime. Contracts matter because changing them affects what ships.

| Layer | Files | Doc |
|---|---|---|
| Rust build script | `app/src-tauri/build.rs` | Documented in [`rust-backend.md`](contracts/rust-backend.md) |
| Sidecar packaging | `spikes/pyinstaller_sidecar/build_sidecar.py` | [`contracts/sidecar.md`](contracts/sidecar.md) |
| Frontend config | `app/vite.config.ts`, `app/src/vite-env.d.ts` | Noted in [`frontend-lib.md`](contracts/frontend-lib.md); no business logic |
| Release pipeline | `scripts/build-release.ps1` | Self-documenting; sequenced in the README of [`contracts/sidecar.md`](contracts/sidecar.md) |

### Bucket 3 — Retired Python (historical reference only)

Pre-Tauri implementation, fully **retired in M9**. Kept in the repo under `legacy/` so future readers can study the original Tk UX, but no longer bundled into `sidecar.exe` and not imported by any production module.

| Files | Doc |
|---|---|
| `legacy/javdb_magnet_gui.py` (moved from root in M9 Phase 5-B; pre-Tauri Tk desktop app; only `create_session`/`fetch_magnets`/`parse_size_gb`/`parse_file_count` ever mattered to the sidecar and those four have been promoted to `javdb_scraper.py`) | [`contracts/python-legacy.md`](contracts/python-legacy.md) §`legacy/javdb_magnet_gui.py` (overview) |

**Removed in M9**:
- `javdb_magnet.py` — standalone CLI scraper, never imported by anything; deleted in Phase 2 (commit `066f9ac`)
- `build.py` — legacy Tk PyInstaller build script, replaced by `scripts/build-release.ps1` + `spikes/pyinstaller_sidecar/build_sidecar.py`; deleted in Phase 2

**Note**: `app_logging.py` and `realdebrid.py` were originally listed in this bucket as "legacy", but they remain **live** in the sidecar runtime and are now classified under Bucket 1.

### Bucket 4 — Spike / prototype (NOT contract owners)

Exploratory code from earlier milestones. Useful for understanding how decisions were reached, but **not authoritative** for the live runtime. The `pyinstaller_sidecar` spike is the one exception — its `build_sidecar.py` is actively used (see Bucket 2), while the rest is reference material only.

| Path | Status | Notes |
|---|---|---|
| `spikes/pyinstaller_sidecar/driver_rust/` | Reference-only spike driver | Demonstrates the M3 `argv` sidecar mode. **Does NOT speak the current JSONL daemon protocol** — that's owned by `sidecar/sidecar.py` (see [`sidecar-runtime.md`](contracts/sidecar-runtime.md)). |
| `spikes/python_sidecar_protocol/` | **Retired in M9 (Phase 4)** | The original spike `sidecar.py` + `driver_rust/` were deleted; only `NOTES.md` remains as historical record (marked RETIRED). The live runtime is now `sidecar/sidecar.py`. |
| `spikes/rust_fetch_javdb/`, `spikes/rquest_fetch_javdb/` | **Removed in M9 (Phase 2)** | Native Rust JavDB-fetch experiments that were closed as not-viable (reqwest TLS fingerprint blocked by Cloudflare; rquest Windows build chain issue). Both spike directories were deleted; design decisions remain documented in `docs/superpowers/specs/2026-05-10-tauri-rewrite-design.md`. |

**Rule for refactors**: when changing sidecar protocol behavior, update `sidecar/sidecar.py` + `sidecar-runtime.md` + the relevant Rust caller. Do NOT treat the spike driver as authoritative.

### Bucket 5 — Tests (NOT contract owners; regression references)

Tests assert behavior; they do not define it. Treat them as guardrails for the contracts in Buckets 1–3.

| Path | Role |
|---|---|
| `tests/test_core_logic.py` | 41 unit tests over `pick_files` (4 strategies), `_extract_code`, `_filename_matches_code`, `parse_size_gb`, `parse_file_count`. **This is the regression bar** any Rust/JS port of the Python core must clear. |
| `app/src/lib/*.test.ts` | Vitest specs over the frontend lib modules. Document the "happy path" + edge cases each lib helper is contracted to handle. |
| `app/src-tauri/src/**/#[cfg(test)] mod tests` | Rust unit tests inside each backend module. Three of them duplicate a `temp_dir()` helper (see punch list). |

### Out of analysis scope

| Path | Why excluded |
|---|---|
| `build/`, `dist/`, `dist.7z`, `*.spec`, `__pycache__/`, `target/`, `node_modules/` | Generated artifacts / package caches. |
| `release/`, `JavDBMagnet.spec` | Build output. |
| `cookies.txt`, `pending_torrents.json`, `.env`, `magnet.txt`, `logs/` | Runtime user data, not source. |

### Why split this way

Work was split by **execution boundary**: each bucket owns code with a homogeneous trust + lifecycle posture. Bucket 1 ships and runs at user-time; Bucket 2 runs at build-time; Bucket 3 is partly Bucket-1 (the sidecar imports) and partly archival; Bucket 4 is scratch space; Bucket 5 is verification. Keeping the boundaries explicit prevents an agent (or a future refactor) from accidentally treating a spike driver or a test fixture as the source of truth for live behavior.

---

## Architectural shape (one-paragraph)

The app is a **3-tier Windows desktop application**: a Svelte 5 single-page UI (`App.svelte` + four `lib/*.ts` modules) talks to a Rust Tauri backend (9 `.rs` modules, 28 `#[tauri::command]` exports) via `invoke()`; the Rust backend spawns and owns a long-running **PyInstaller-bundled Python sidecar** process (`sidecar.exe`) that performs all JavDB scraping and Real-Debrid REST traffic. There is **no Tauri event emission** from Rust and **no `listen(...)` subscription** from the frontend — progress for batch operations is driven by **JS-side callbacks** (`onProgress`) that the lib helpers call after each per-item `invoke()` returns. Cancellation is via `AbortSignal` checked at iteration boundaries (in-flight `invoke`s always complete). The sidecar contract is **process-based stdio JSON** (one request line in, one response line out).

---

## Cross-layer call graph

The seven user-visible flows, from UI click down to Python execution. File:line links point into the per-layer docs.

### Flow 1 — App boot

```
main.rs::main                                    (app/src-tauri/src/main.rs:1)
└── lib.rs::run                                  (app/src-tauri/src/lib.rs)
    └── Builder::default().setup(|app| ...)
        ├── path_manager::resolve_*              (app/src-tauri/src/path_manager.rs)
        ├── settings::load_settings              (app/src-tauri/src/settings.rs)
        ├── SidecarManager::new                  (app/src-tauri/src/sidecar_manager.rs)
        │   ├── Command::new("sidecar-...exe")
        │   ├── spawn child process
        │   └── tokio::spawn(line_reader_task)
        ├── block_on(sidecar.request("ping"))    (lib.rs:109) ⚠ blocks setup
        └── manage::<State<SidecarManager>>(...)
        ↓ webview opens, App.svelte mounts
App.svelte::onMount                              (app/src/App.svelte)
├── invoke('get_app_paths')        → commands::get_app_paths
├── invoke('read_settings')        → commands::read_settings
├── invoke('list_pending')         → commands::list_pending
├── invoke('cookies_status')       → commands::cookies_status
└── invoke('rd_has_token')         → commands::rd_has_token
```

### Flow 2 — Scrape JavDB URLs

```
App.svelte::handleScrape (click "抓取")          (app/src/App.svelte)
└── lib/scraper.ts::scrapeBatch                  (app/src/lib/scraper.ts)
    │   AbortSignal checked between urls
    └── for each url:
        ├── invoke('fetch_javdb', { url })       → commands::fetch_javdb (commands.rs)
        │   └── SidecarManager::request          (sidecar_manager.rs)
        │       ├── write JSON line to sidecar stdin
        │       └── await line on stdout channel
        │       ↓ over the pipe to sidecar.exe
        │       PyInstaller bundle entry:
        │           sidecar/sidecar.py            (contracts/sidecar-runtime.md)
        │           └── javdb_scraper::create_session   (javdb_scraper.py)   [M9: was javdb_magnet_gui]
        │           └── javdb_scraper::fetch_magnets    (javdb_scraper.py)
        │                 ├── curl_cffi.requests (Chrome-124 impersonation)
        │                 └── BeautifulSoup parse → list[magnet dict]
        ├── callback(onProgress, { url, ok, magnets|error })
        └── App.svelte $state.scrapeResults.push(...)
```

### Flow 3 — Send batch to Real-Debrid

```
App.svelte::handleSendToRD (click "送 RD")       (app/src/App.svelte)
└── lib/rdSender.ts::sendBatch                   (app/src/lib/rdSender.ts)
    └── for each magnet:
        ├── invoke('rd_send_magnet', { magnet, strategy, minSizeMb })
        │   → commands::rd_send_magnet           (commands.rs)
        │     └── SidecarManager::request("rd_send_magnet", ...)
        │         ↓ sidecar.exe
        │         sidecar.py::cmd_rd_send_magnet
        │         └── realdebrid.RealDebrid.process_magnet
        │             ├── _request(POST /torrents/addMagnet)
        │             ├── get_torrent_info
        │             ├── pick_files (smart | video | largest | all)
        │             │   └── _extract_code / _filename_matches_code
        │             ├── select_files
        │             └── get_torrent_info → return { id, status, links | pending }
        ├── if pending → invoke('add_pending')   → commands::add_pending
        │                                          → pending.rs::add
        └── callback(onProgress, { magnet, ok, links|pending|error })
```

### Flow 4 — Retry pending queue

```
App.svelte::retryAllPending  (115 lines — refactor hotspot)
└── lib/magnetUtils.ts::retryPending             (app/src/lib/magnetUtils.ts)
    └── for each pending entry:
        ├── invoke('rd_check_pending', { id })   → commands::rd_check_pending
        │   └── SidecarManager::request("rd_check_pending", ...)
        │       ↓ sidecar.exe
        │       sidecar.py::cmd_rd_check_pending
        │       └── realdebrid.RealDebrid.check_torrent
        │       → { status: "downloaded" | "downloading" | "error" }
        ├── if downloaded → links → invoke('remove_pending')
        └── callback(onProgress, ...)
↑ back to App.svelte:
  - duplicated reconciliation loop body (completed vs missing branches)
  - rebuilds rdSendProgress, refreshes pending from disk, builds clipboard summary
```

### Flow 5 — Paste magnets (manual entry)

```
App.svelte::registerPastedMagnets  (95 lines — refactor hotspot)
├── parse textarea → list of magnet strings
├── for each → invoke('register_magnets', { magnets })
│   → commands::register_magnets
│     └── pending.rs::add or settings store mutation
└── synthesize ScrapedGroup with url = "manual://<jav-code>"
    ↑ sentinel is ALSO load-bearing in buildVisibleSendItems
```

### Flow 6 — Save settings

```
App.svelte::saveSettings
├── lib/settingsValidation.ts::validateSettings  (returns null | error string)
├── invoke('write_settings', { settings })       → commands::write_settings
│   └── settings.rs::write_settings              (file write to %APPDATA%)
└── invoke('update_sidecar_settings', { ... })   → commands::update_sidecar_settings
                                                   └── SidecarManager::request("update_settings", ...)
   ⚠ Rust does NOT chain these — frontend must call both. (See punch list.)
```

### Flow 7 — Legacy import (.env / cookies.txt / pending_torrents.json)

```
App.svelte::applyLegacyImport (settings panel)
└── invoke('apply_legacy_import', { sourcePath })
    → commands::apply_legacy_import
      └── legacy_import.rs::apply                (app/src-tauri/src/legacy_import.rs)
          ├── parse legacy .env → write new settings
          ├── parse cookies.txt → cookies store
          ├── parse pending_torrents.json → pending queue
          └── (Token migration: eprintln! the only log line in the codebase)
```

---

## Bridge surfaces

### Tauri command surface (Rust ↔ JS)

28 `#[tauri::command]` exports registered in [`lib.rs::run`](contracts/rust-backend.md). The frontend uses 27 distinct names (3 from `lib/*`, 24 from `App.svelte`). See [rust-backend.md](contracts/rust-backend.md) for the full table.

### Sidecar command surface (Rust ↔ Python via stdio JSON)

Per the live Rust caller, the sidecar accepts a JSON line `{ "cmd": "...", "request_id": "...", ...command_fields }` and replies with `{ "ok": bool, "request_id": "...", ... }`. See [`contracts/sidecar-runtime.md`](contracts/sidecar-runtime.md) for full per-command contracts.

- `hello`, `handshake`, `ping`
- `fetch_javdb`
- `resolve_magnet`, `resolve_magnets`, `forget_magnets`, `register_magnets`
- `update_settings`, `cancel`, `shutdown`
- `rd_user`, `rd_set_token`
- `rd_send_magnet`
- `rd_check_pending`

The older driver docs in [`contracts/sidecar.md`](contracts/sidecar.md) describe the PyInstaller build and spike driver, including its stale argv-mode assumptions.

### Event surface (Tauri events)

**Empty.** No Rust-side `emit()`, no JS-side `listen()`. Progress is JS-driver-based via callbacks.

---

## Module dependency graph

```
Rust backend (app/src-tauri/src/):
  main.rs ─→ lib.rs ─→ {commands, sidecar_manager, settings, secret_store,
                        path_manager, pending, legacy_import}
  commands.rs  ─→ {sidecar_manager, pending, settings, secret_store}
  legacy_import.rs ─→ {settings, secret_store, pending}
  sidecar_manager.rs ─→ (std::process, tokio)

Frontend (app/src/):
  main.ts ─→ App.svelte
  App.svelte ─→ {lib/scraper, lib/rdSender, lib/magnetUtils,
                 lib/settingsValidation, lib/types,
                 @tauri-apps/api/core::invoke}
  lib/{scraper,rdSender,magnetUtils,settingsValidation} ─→ lib/types only
  lib/* are a FLAT LEAF LAYER — no lib imports another.

Sidecar (PyInstaller bundle, runtime):
  sidecar/sidecar.py ─→ {app_logging, realdebrid,
                         javdb_scraper::{create_session, fetch_magnets,
                                         parse_size_gb, parse_file_count}}
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

- **`forget_magnets` skips the `ok` check** — silently returns 0 on sidecar failure. Unique among sidecar-wrapping commands. [`commands.rs:155`](../../app/src-tauri/src/commands.rs#L155)
- **No Rust-side logging anywhere.** Sidecar stderr is dropped on the floor. Only `eprintln!` in the codebase is the legacy-token migration. [`sidecar_manager.rs:71`](../../app/src-tauri/src/sidecar_manager.rs#L71)
- **`SidecarManager` has no `Drop` and no respawn-on-crash.** Once the line-reader task exits, every subsequent `request()` errors out and the user must restart the app.
- **`block_on` during `.setup`** for the sidecar handshake. Any sidecar slowness delays window open. [`lib.rs:109`](../../app/src-tauri/src/lib.rs#L109)
- **`STORE_FILE` is defined twice** — [`lib.rs:15`](../../app/src-tauri/src/lib.rs#L15) and [`settings.rs:12`](../../app/src-tauri/src/settings.rs#L12). Same for `pending_torrents.json` and `cookies.txt` path literals.
- **`update_sidecar_settings` is not chained from `write_settings`** — frontend must call both. Silent footgun if a future caller only calls one.
- **`rd_has_token` is gratuitously `async`** — no `await`, no `State<'_, _>`.
- **`_err_code` has a leading underscore despite 9 callers** — style inconsistency.
- **Three duplicated `temp_dir` test helpers** in `pending.rs`, `legacy_import.rs`, `commands.rs`.
- **Test at [`legacy_import.rs:425`](../../app/src-tauri/src/legacy_import.rs#L425)** deliberately splits `"RD_API_TOKEN"` to avoid the string appearing verbatim in source (audit hygiene).

### Frontend lib (`frontend-lib.md`)

- **`sortRows(column="code")` actually sorts by `name`** — `MagnetRow` has no `code` field. Latent bug. [`magnetUtils.ts:132`](../../app/src/lib/magnetUtils.ts#L132)

### App.svelte (`app-svelte.md` "Refactor hotspots")

- **`retryAllPending` (~115 lines)** — mixes iteration/accumulators, per-event reconciliation of `rdSendProgress`, post-loop disk refresh, and a multi-fragment clipboard summary. Duplicates the `for (i; i<rdSendProgress.length; i++)` reconciliation loop body across `completed` and `missing` branches.
- **Status-message state is fragmented across 8+ variables** (`statusMessage`, `pingMessage`, `rdMessage`, `registerStatus`, `pendingMessage`, `cookiesError`+`cookiesMessage`, `settingsMessage`+`settingsMessageKind`, `legacyError`) in two competing shapes (plain string vs `{kind, text}`). Section rendering is inconsistent and hard to extract.
- **`registerPastedMagnets` (~95 lines)** — packs parse / error-heuristic / invoke / cross-group dedupe / synthetic-group construction inline. The `url.startsWith('manual://')` sentinel is **also** load-bearing in `buildVisibleSendItems` — a `groupKind: "javdb" | "manual"` field on `ScrapedGroup` (or extracting `buildSyntheticPasteGroup()` + `resolveRowCode()`) would localize the rule.

### Sidecar runtime (`sidecar-runtime.md`)

- **`cmd_forget_magnets` ignores `handle_ids`** — Rust can send a selective deletion payload, but the live sidecar clears the entire handle table and returns the total old count. This makes the Rust command name/signature more precise than the daemon behavior. [`sidecar.py:308`](../../sidecar/sidecar.py#L308)
- **`cmd_cancel` is an acknowledgement only** — it cannot interrupt in-flight JavDB or RD work because the daemon loop is synchronous. User-visible cancellation is currently batch-boundary cancellation in JS/Rust, not Python-level cancellation. [`sidecar.py:364`](../../sidecar/sidecar.py#L364)
- **`main` accepts `--daemon` but always runs daemon mode** — harmless now, but the CLI shape implies a mode switch that no longer exists. [`sidecar.py:687`](../../sidecar/sidecar.py#L687)

### Sidecar build/driver (`sidecar.md`)

- **Stale constants in `driver_rust`** — `SIDECAR_NAME = "sidecar.exe"` and the path walker probes `dist/<SIDECAR_NAME>`, but `build_sidecar.py` (post-M3) writes `sidecar-x86_64-pc-windows-msvc.exe` to `app/src-tauri/binaries/`. Auto-discovery is therefore broken in-tree; the driver only works via `SIDECAR_EXE` env var or a manual rename. Drift not flagged anywhere.
- **`clean()` is broader than its name suggests** — it wipes the entire `app/src-tauri/binaries/` directory, not just the sidecar artifact. Safe today; latent footgun.

### Python legacy (`python-legacy.md`)

- ~~**`javdb_magnet.py` is orphan/dead code** in the repo — no importer.~~ **RESOLVED M9 Phase 2** (commit `066f9ac`): file deleted.
- ~~**~1,300 lines of widget code in `javdb_magnet_gui.py`** is bundled into `sidecar.exe` but never executed at runtime. Only `create_session` and `fetch_magnets` are imported by the sidecar entry. Removing the widget classes (or splitting the file) would shrink the .exe and remove confusion.~~ **RESOLVED M9 Phase 5-A/5-B**: four pure HTTP/parse helpers extracted to `javdb_scraper.py` (commit `39bedd3`); sidecar bundle no longer pulls in Tk (-3.02 MiB). The full Tk source moved to `legacy/javdb_magnet_gui.py` (commit `9c3612d`) and is no longer in the bundle.
- **The behavioral contract the port must preserve** is captured in `tests/test_core_logic.py` — unit tests over `parse_size_gb`, `parse_file_count` (now imported from `javdb_scraper`), `_extract_code`, `_filename_matches_code`, and `pick_files`'s 4 strategies. Treat these as the regression bar for any Rust/JS reimplementation.

---

## How to keep this current

When refactoring:

1. If a function moves, update its file:line in the matching layer doc.
2. If an `invoke()` command is added/removed/renamed, update both the Rust layer (command list) and the JS layer (call sites), plus the cross-layer flow that uses it.
3. If a sidecar command changes shape, update `sidecar-runtime.md` AND the relevant Rust caller in `rust-backend.md`; update `sidecar.md` only when the build or spike driver changes.
4. Punch-list items: when resolved, strike them with `~~strikethrough~~` rather than deleting — keeps the history of what was once a problem.
5. To regenerate from scratch: re-run the layer analyses for Rust backend, frontend lib, App.svelte, sidecar runtime, sidecar build/driver, and Python legacy; they were designed to be idempotent against a clean working tree.
