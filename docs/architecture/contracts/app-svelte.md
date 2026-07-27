# `app/src/App.svelte` — Function & State Contract Reference

**Source**: [`app/src/App.svelte`](../../../app/src/App.svelte) (2177 lines, single-file Svelte 5 component)
**Branch context**: `codex/function-contracts-analysis` — this document maps the surface area before/during refactor.

The file is organized as:

- `<script lang="ts">` — lines [1–1061](../../../app/src/App.svelte#L1)
- `<main>` markup — lines [1063–1820](../../../app/src/App.svelte#L1063)
- `<style>` — lines [1822–2177](../../../app/src/App.svelte#L1822)

---

## 1. Component overview

### 1.1 Imports

**Tauri APIs**

- `onMount` from `svelte` ([App.svelte:2](../../../app/src/App.svelte#L2))
- `invoke` from `@tauri-apps/api/core` ([App.svelte:3](../../../app/src/App.svelte#L3))
- `open as openExternal` from `@tauri-apps/plugin-shell` ([App.svelte:4](../../../app/src/App.svelte#L4))

**Lib modules**

- `./lib/scraper` — `parseMagnetBatch`, `parseUrlBatch`, `scrapeBatch`, type `ScrapeProgressEvent` ([App.svelte:5–10](../../../app/src/App.svelte#L5))
- `./lib/magnetUtils` — `dedupeByHandleId`, `processGroupRows` ([App.svelte:11](../../../app/src/App.svelte#L11))
- `./lib/settingsValidation` — `FILE_PICK_VALUES`, `SCALE_PRESETS`, `THEME_VALUES`, `validateSettingsDraft` ([App.svelte:12–17](../../../app/src/App.svelte#L12))
- `./lib/rdSender` — `rdErrorMessage`, `retryPending`, `sendBatch`, types `RdRetryEvent`, `RdSendBatchEvent`, `RdSendItem` ([App.svelte:18–25](../../../app/src/App.svelte#L18))

**Types (from `./lib/types`)** ([App.svelte:26–46](../../../app/src/App.svelte#L26))

`defaultFilterState`, `CookiesStatus`, `CopyBulkResult`, `CopyRdLinksBulkResult`, `FilterState`, `LegacyImportPreview`, `LegacyImportReport`, `GroupPick`, `MagnetRow`, `PathInfo`, `PendingEntry`, `PingResponse`, `RdSendProgress`, `RdUserInfo`, `ScrapedGroup`, `Settings`, `SortColumn`, `SortDirection`, `Theme`.

**Svelte 5 runes used**: `$state`, `$derived`, `$derived.by`. Lifecycle: `onDestroy` disposes the flash controller (`flash.dispose()`); no `$effect`.

### 1.2 Tauri command surface — every `invoke()` call

| Rust command | Caller (App.svelte) | Line |
|---|---|---|
| `get_paths` | `onMount` | [143](../../../app/src/App.svelte#L143) |
| `read_settings` | `onMount`, `saveSettings`, `applyLegacyImportConfirmed` | [152](../../../app/src/App.svelte#L152), [946](../../../app/src/App.svelte#L946), [995](../../../app/src/App.svelte#L995) |
| `rd_has_token` | `onMount` | [164](../../../app/src/App.svelte#L164) |
| `pending_list` | `onMount`, `sendVisibleToRd` (finally), `refreshPending`, `retryAllPending` (finally), `applyLegacyImportConfirmed` | [170](../../../app/src/App.svelte#L170), [647](../../../app/src/App.svelte#L647), [689](../../../app/src/App.svelte#L689), [776](../../../app/src/App.svelte#L776), [1007](../../../app/src/App.svelte#L1007) |
| `get_legacy_default_dir` | `onMount` | [178](../../../app/src/App.svelte#L178) |
| `write_settings` | `toggleTheme`, `saveSettings` | [200](../../../app/src/App.svelte#L200), [935](../../../app/src/App.svelte#L935) |
| `sidecar_ping` | `pingSidecar` | [211](../../../app/src/App.svelte#L211) |
| `register_magnets` | `registerPastedMagnets` | [282](../../../app/src/App.svelte#L282) |
| `copy_magnet` | `copyOne` | [365](../../../app/src/App.svelte#L365) |
| `copy_magnets_bulk` | `copyVisible` | [388](../../../app/src/App.svelte#L388) |
| `forget_magnets` | `clearResults` | [461](../../../app/src/App.svelte#L461) |
| `rd_test_token` | `rdTestToken` | [498](../../../app/src/App.svelte#L498) |
| `rd_save_token` | `rdSaveToken` | [516](../../../app/src/App.svelte#L516) |
| `rd_check_user` | `rdSaveToken`, `rdRefreshUser` | [523](../../../app/src/App.svelte#L523), [554](../../../app/src/App.svelte#L554) |
| `rd_clear_token` | `rdClearToken` | [536](../../../app/src/App.svelte#L536) |
| `copy_rd_links_bulk` | `copyRdDownloads`, `retryAllPending` | [672](../../../app/src/App.svelte#L672), [793](../../../app/src/App.svelte#L793) |
| `preview_legacy_import` | `previewLegacyImport` | [836](../../../app/src/App.svelte#L836) |
| `apply_legacy_import` | `applyLegacyImportConfirmed` | [986](../../../app/src/App.svelte#L986) |
| `get_cookies_status` | `refreshCookiesStatus` | [850](../../../app/src/App.svelte#L850) |
| `open_data_dir` | `openDataDir` | [860](../../../app/src/App.svelte#L860) |
| `open_logs_dir` | `openLogsDir` | [869](../../../app/src/App.svelte#L869) |
| `create_cookies_template` | `createCookiesTemplate` | [879](../../../app/src/App.svelte#L879) |
| `update_sidecar_settings` | `saveSettings` | [939](../../../app/src/App.svelte#L939) |
| `pending_remove` | `removePending` | [1024](../../../app/src/App.svelte#L1024) |
| `pending_clear` | `clearAllPending` | [1038](../../../app/src/App.svelte#L1038) |

Indirect `invoke` calls also happen inside the lib modules — `scrapeBatch`, `sendBatch`, `retryPending` each issue their own per-item invokes (e.g. `scrape_javdb_url`, `rd_send_magnet`, `rd_pending_status`). They are documented in those modules; from App.svelte's perspective they are a single async iterator.

### 1.3 Event subscription surface

**None.** No `listen(...)` calls anywhere in the file. Progress is streamed via callbacks passed to `scrapeBatch` / `sendBatch` / `retryPending`, not via Tauri events. Cancellation uses `AbortController`s.

### 1.4 Reactive graph (`$derived` dependencies)

| Derived | Depends on | Line |
|---|---|---|
| `okCount` | `groups[].status` | [477](../../../app/src/App.svelte#L477) |
| `errCount` | `groups[].status` | [478](../../../app/src/App.svelte#L478) |
| `totalRawMagnets` | `groups[].result.magnet_count` | [479](../../../app/src/App.svelte#L479) |
| `allVisibleRows` (`$derived`) | `webVisibleRows`, `manualVisibleRows` | [620](../../../app/src/App.svelte#L620) |
| `settingsErrors` | `settingsDraft` | [897](../../../app/src/App.svelte#L897) |
| `settingsValid` | `settingsErrors` | [900](../../../app/src/App.svelte#L900) |
| `rdCompletedCount` | `rdSendProgress[].status` | [1046](../../../app/src/App.svelte#L1046) |
| `rdPendingCount` | `rdSendProgress[].status` | [1049](../../../app/src/App.svelte#L1049) |
| `rdErrorCount` | `rdSendProgress[].status` | [1052](../../../app/src/App.svelte#L1052) |
| `rdDownloadLinkCount` | `rdSendProgress[].status`, `rdSendProgress[].links` | [1055](../../../app/src/App.svelte#L1055) |

### 1.5 Lifecycle

- `onMount` ([App.svelte:141–189](../../../app/src/App.svelte#L141)) — boot-time IPC to populate paths, settings, RD token presence, pending list, legacy default dir, cookies status. Best-effort: every step is wrapped in its own `try/catch` so a partial failure still allows the rest of the UI to render.
- `onDestroy(() => flash.dispose())` clears all pending flash timers on unmount. No `$effect`. Cancellation tokens (`scrapeAbort`, `rdSendAbort`, `retryAbort`) are not torn down on unmount — fine for a top-level component but worth noting.

---

## 2. State catalog

### 2.1 Paths / theme / boot

| Var | Type | Initial | Mutated by | Read by |
|---|---|---|---|---|
| `dataDir` | `string` | `"（載入中）"` | `onMount` | markup [1071](../../../app/src/App.svelte#L1071) |
| `logDir` | `string` | `"（載入中）"` | `onMount` | markup [1073](../../../app/src/App.svelte#L1073) |
| `theme` | `Theme` | `"light"` | `onMount`, `toggleTheme`, `saveSettings`, `applyLegacyImportConfirmed` | `toggleTheme`, markup [1080](../../../app/src/App.svelte#L1080) |
| `settings` | `Settings \| null` | `null` | `onMount`, `saveSettings`, `applyLegacyImportConfirmed`, `toggleTheme` (mutates `.ui.theme`) | `sendVisibleToRd` (for defaults), `openSettingsEditor`, `revertSettingsDraft` |
| `statusMessage` | `string` | `""` | `toggleTheme`, `startScrape` (guard), `copyOne`, `copyVisible`, `clearResults`, `onMount` (catch) | markup [1083](../../../app/src/App.svelte#L1083) |

### 2.2 JavDB scrape / magnet batch

| Var | Type | Initial | Mutated by | Read by |
|---|---|---|---|---|
| `urlBatch` | `string` | `"https://javdb.com/v/RkX3Rp\n"` | `bind:value` textarea [1454](../../../app/src/App.svelte#L1454) | `startScrape` |
| `magnetBatch` | `string` | `""` | `bind:value` textarea [1560](../../../app/src/App.svelte#L1560), cleared in `registerPastedMagnets` | `registerPastedMagnets` |
| `isRegistering` | `boolean` | `false` | `registerPastedMagnets` | button disabled [1567](../../../app/src/App.svelte#L1567) |
| `registerStatus` | `{kind, text} \| null` | `null` | `registerPastedMagnets` | markup [1574](../../../app/src/App.svelte#L1574) |
| `groups` | `ScrapedGroup[]` | `[]` | `startScrape`, `scrapeBatch` callback (slot replace), `registerPastedMagnets`, `clearResults` | many: `processedRows`, `buildVisibleSendItems`, `copyVisible`, `webVisibleRows` / `manualVisibleRows` / `allVisibleRows`, `okCount`, `errCount`, `totalRawMagnets`, markup [1583](../../../app/src/App.svelte#L1583) |
| `scrapeProgress` | `{done, total}` | `{0,0}` | `startScrape`, `scrapeBatch` callback, `clearResults` | markup [1486](../../../app/src/App.svelte#L1486) |
| `isScraping` | `boolean` | `false` | `startScrape` (set/finally) | button disabled / labels [1461–1476](../../../app/src/App.svelte#L1461) |
| `scrapeAbort` | `AbortController \| null` | `null` | `startScrape`, `cancelScrape`, `clearResults` | `cancelScrape` |

### 2.3 Filter / sort / collapse

| Var | Type | Initial | Mutated by | Read by |
|---|---|---|---|---|
| `filter` | `FilterState` | `defaultFilterState()` | `bind:value` inputs, `commitMinSize`, `commitMaxSize`, `setGroupPick`, `resetFilter` | `processedRows`, `allVisibleRows`（經 `webVisibleRows`/`manualVisibleRows`） |
| `minSizeInput` | `string` | `""` | input bind [1516](../../../app/src/App.svelte#L1516), `resetFilter` | `commitMinSize` |
| `maxSizeInput` | `string` | `""` | input bind [1526](../../../app/src/App.svelte#L1526), `resetFilter` | `commitMaxSize` |
| `sortColumn` | `SortColumn \| null` | `null` | `toggleSort`, `resetFilter` | `processedRows`, `sortIndicator` |
| `sortDirection` | `SortDirection` | `"asc"` | `toggleSort`, `resetFilter` | `processedRows`, `sortIndicator` |
| `collapsed` | `Record<string, boolean>` | `{}` | `toggleCollapsed`, `clearResults` | markup [1585](../../../app/src/App.svelte#L1585) |

### 2.4 Ping / sidecar

| Var | Type | Initial | Mutated by | Read by |
|---|---|---|---|---|
| `pingMessage` | `string` | `""` | `pingSidecar` | markup [1092](../../../app/src/App.svelte#L1092) |

### 2.5 Real-Debrid token + user

| Var | Type | Initial | Mutated by | Read by |
|---|---|---|---|---|
| `rdHasToken` | `boolean` | `false` | `onMount`, `rdSaveToken`, `rdClearToken`, `applyLegacyImportConfirmed` | `sendVisibleToRd`, `rdRefreshUser`, markup (many gates) |
| `rdUser` | `RdUserInfo \| null` | `null` | `rdTestToken`, `rdSaveToken`, `rdClearToken`, `rdRefreshUser` | markup [1110](../../../app/src/App.svelte#L1110) |
| `rdTokenInput` | `string` | `""` | input bind [1141](../../../app/src/App.svelte#L1141), cleared in `rdSaveToken`/`rdClearToken` | `rdTestToken`, `rdSaveToken` |
| `rdShowToken` | `boolean` | `false` | checkbox bind [1147](../../../app/src/App.svelte#L1147), `rdSaveToken` (resets) | input `type` attr |
| `rdMessage` | `string` | `""` | many RD handlers | markup [1159](../../../app/src/App.svelte#L1159) |

### 2.6 Real-Debrid send-batch progress

| Var | Type | Initial | Mutated by | Read by |
|---|---|---|---|---|
| `rdSendProgress` | `RdSendProgress[]` | `[]` | `sendVisibleToRd`, `sendBatch` callback (slot replace), `retryAllPending` (reconciles completed/missing) | derived counts, `copyRdDownloads`, markup [1716](../../../app/src/App.svelte#L1716) |
| `rdSendDone` | `{done,total}` | `{0,0}` | `sendVisibleToRd`, `sendBatch` callback | markup [1688](../../../app/src/App.svelte#L1688) |
| `isRdSending` | `boolean` | `false` | `sendVisibleToRd` (set/finally) | disabled gates, `sendVisibleToRd` guard |
| `rdSendAbort` | `AbortController \| null` | `null` | `sendVisibleToRd`, `cancelRdSend` | `cancelRdSend` |

### 2.7 Pending list (RD waiting)

| Var | Type | Initial | Mutated by | Read by |
|---|---|---|---|---|
| `pendingEntries` | `PendingEntry[]` | `[]` | `onMount`, `sendVisibleToRd` (finally), `refreshPending`, `retryAllPending` (finally), `removePending`, `clearAllPending`, `applyLegacyImportConfirmed` | `retryAllPending` (input), markup [1759](../../../app/src/App.svelte#L1759) |
| `isRetryingPending` | `boolean` | `false` | `retryAllPending` (set/finally) | disabled gates |
| `retryAbort` | `AbortController \| null` | `null` | `retryAllPending`, `cancelRetry` | `cancelRetry` |
| `pendingMessage` | `{kind, text} \| null` | `null` | `refreshPending`, `retryAllPending`, `removePending`, `clearAllPending` | markup [1769](../../../app/src/App.svelte#L1769) |

### 2.8 Legacy import (M7a-lite)

| Var | Type | Initial | Mutated by | Read by |
|---|---|---|---|---|
| `legacyPath` | `string` | `""` | `onMount` (env default), input bind [1182](../../../app/src/App.svelte#L1182) | `previewLegacyImport`, `applyLegacyImportConfirmed` |
| `legacyPreview` | `LegacyImportPreview \| null` | `null` | `previewLegacyImport` (set/clear) | markup [1200](../../../app/src/App.svelte#L1200), apply button enable [1192](../../../app/src/App.svelte#L1192) |
| `legacyReport` | `LegacyImportReport \| null` | `null` | `previewLegacyImport` (clear), `applyLegacyImportConfirmed` | markup [1237](../../../app/src/App.svelte#L1237) |
| `legacyBusy` | `boolean` | `false` | both legacy functions (set/finally) | disabled gates |
| `legacyError` | `string` | `""` | both legacy functions | markup [1197](../../../app/src/App.svelte#L1197) |
| `legacyShown` | `boolean` | `false` | `onMount` (if env default), toggle button [1168](../../../app/src/App.svelte#L1168) | `{#if}` gate [1172](../../../app/src/App.svelte#L1172) |

### 2.9 Cookies status (M7b)

| Var | Type | Initial | Mutated by | Read by |
|---|---|---|---|---|
| `cookiesStatus` | `CookiesStatus \| null` | `null` | `refreshCookiesStatus` (set/clear) | markup [1412](../../../app/src/App.svelte#L1412) |
| `cookiesShown` | `boolean` | `false` | toggle button [1403](../../../app/src/App.svelte#L1403) | `{#if}` gate [1407](../../../app/src/App.svelte#L1407) |
| `cookiesError` | `string` | `""` | `refreshCookiesStatus`, `openDataDir`, `openLogsDir`, `createCookiesTemplate` | markup [1431](../../../app/src/App.svelte#L1431) |
| `cookiesMessage` | `{kind, text} \| null` | `null` | `createCookiesTemplate` | markup [1434](../../../app/src/App.svelte#L1434) |

### 2.10 Settings editor (M7c)

| Var | Type | Initial | Mutated by | Read by |
|---|---|---|---|---|
| `settingsShown` | `boolean` | `false` | toggle button [1282](../../../app/src/App.svelte#L1282), `openSettingsEditor`, `saveSettings` doesn't auto-close | `{#if}` gate [1289](../../../app/src/App.svelte#L1289) |
| `settingsDraft` | `Settings \| null` | `null` | `openSettingsEditor`, `saveSettings`, `revertSettingsDraft` + `bind:value` in form | `settingsErrors`, `saveSettings`, form binds |
| `settingsSaving` | `boolean` | `false` | `saveSettings` (set/finally) | disabled gates |
| `settingsMessage` | `string` | `""` | many settings handlers | markup [1392](../../../app/src/App.svelte#L1392) |
| `settingsMessageKind` | `"ok"\|"error"\|"info"` | `"info"` | mirrored with `settingsMessage` | `data-kind` attr [1393](../../../app/src/App.svelte#L1393) |

---

## 3. Functions / handlers (source order)

### 3.1 UI helpers — theme & scale

#### `applyTheme(t: Theme): void`  *(App.svelte:[121](../../../app/src/App.svelte#L121))*

**Purpose**: Set `document.documentElement.dataset.theme` so CSS variables switch.

**Contract**:
- Pure DOM side effect on `<html>`.
- No state read/write inside the component graph.

**Calls**: DOM `dataset` property set.

**Triggered by**: `onMount`, `toggleTheme`, `saveSettings`, `applyLegacyImportConfirmed`.

---

#### `applyScale(raw: string): void`  *(App.svelte:[131](../../../app/src/App.svelte#L131))*

**Purpose**: Translate `settings.ui.scale` ("auto" | "0.5".."3.0") into a `--ui-scale` CSS var + root `font-size`.

**Contract**:
- `"auto"` → scale = 1. Numeric strings clamp to `[0.5, 3.0]`. Anything else → 1.
- Side effect: sets CSS variable and inline root font-size.
- No invoke calls.

**Calls**: `parseFloat`, DOM `style.setProperty`.

**Triggered by**: `onMount`, `saveSettings`, `applyLegacyImportConfirmed`.

---

### 3.2 Initialization / boot

#### `onMount(async () => {...})`  *(App.svelte:[141](../../../app/src/App.svelte#L141))*

**Purpose**: Best-effort boot — populate paths, settings (+ apply theme/scale), RD token presence, pending list, legacy default dir, cookies status.

**Contract**:
- Async. Each IPC wrapped in its own `try/catch` so partial failures don't abort the rest.
- Writes: `dataDir`, `logDir`, `settings`, `theme`, `rdHasToken`, `pendingEntries`, `legacyPath`, `legacyShown`, plus `statusMessage` on settings failure.
- Errors surfaced as `console.warn` for non-critical; `statusMessage` for settings failure; inline text in `dataDir`/`logDir` for path failure.

**Calls**:
- `invoke('get_paths')` → `PathInfo`
- `invoke('read_settings')` → `Settings`
- `invoke('rd_has_token')` → `{present}`
- `invoke('pending_list')` → `PendingEntry[]`
- `invoke('get_legacy_default_dir')` → `string`
- `applyTheme(theme)`, `applyScale(s.ui.scale)`, `refreshCookiesStatus()`

**Triggered by**: Svelte mount.

---

### 3.3 Theme / sidecar quick handlers

#### `toggleTheme(): Promise<void>`  *(App.svelte:[191](../../../app/src/App.svelte#L191))*

**Purpose**: Flip light/dark, persist via `write_settings`.

**Contract**:
- Guard: if `settings === null` or `isThemeSaving === true`, returns immediately to prevent reentrancy / rapid double clicks.
- 3-State Sync & Rollback: Optimistically updates `theme`, `settings.ui.theme`, and `settingsDraft.ui.theme`. If `write_settings` fails, rolls back all three states to their previous value and sets `statusMessage`.
- Concurrency: `isThemeSaving` guard is released in a `finally` block.

**Calls**: `applyTheme(theme)`, `invoke('write_settings', { settings })`.

**Triggered by**: Markup button [1079](../../../app/src/App.svelte#L1079).

---

#### `pingSidecar(): Promise<void>`  *(App.svelte:[208](../../../app/src/App.svelte#L208))*

**Purpose**: Health-check sidecar; show uptime + request_id.

**Contract**: Writes `pingMessage`. Catches errors into `pingMessage`.

**Calls**: `invoke('sidecar_ping')` → `PingResponse`.

**Triggered by**: Markup button [1090](../../../app/src/App.svelte#L1090).

---

### 3.4 JavDB scrape flow

#### `startScrape(): Promise<void>`  *(App.svelte:[218](../../../app/src/App.svelte#L218))*

**Purpose**: Parse URL textarea, render placeholder slots, invoke batch scraper with abort signal.

**Contract**:
- Guard: returns early if `isScraping`.
- If `parseUrlBatch` returns empty → writes `statusMessage`, returns.
- Mutates: `groups` (placeholders), `scrapeProgress`, `isScraping` (set + finally false), `scrapeAbort` (new + finally null).
- Per-URL settle: callback receives `{index, total, group}` and replaces `groups[index-1]`.

**Calls**:
- `parseUrlBatch(urlBatch)` → `string[]` (lib/scraper.ts:72)
- `scrapeBatch(urls, callback, { signal })` (lib/scraper.ts:114) — that lib internally invokes `scrape_javdb_url` per URL.

**Triggered by**: Markup button [1461](../../../app/src/App.svelte#L1461).

---

#### `cancelScrape(): void`  *(App.svelte:[256](../../../app/src/App.svelte#L256))*

**Purpose**: Abort in-flight scrape via `scrapeAbort.abort()`.

**Calls**: `AbortController.abort()`.

**Triggered by**: Markup button [1464](../../../app/src/App.svelte#L1464).

---

### 3.5 Paste-magnet flow

#### `registerPastedMagnets(): Promise<void>`  *(App.svelte:[265](../../../app/src/App.svelte#L265))*

**Purpose**: Parse pasted magnet text, register via sidecar, splice result rows into `groups` as a synthetic `manual://<ts>` group so downstream filter/sort/send-to-RD plumbing applies unchanged.

**Contract**:
- Guard: returns early if `isRegistering`.
- If no valid magnets, detects the JavDB-URL-misuse pattern (`/^\s*https?:\/\//im`) and produces a tailored error message.
- Dedupes new rows against `existingHandleIds` snapshotted from current `groups` so a re-paste of a known magnet doesn't double-list (would also double-bill RD).
- Mutates: `isRegistering`, `registerStatus`, `groups` (append synthetic group), `magnetBatch` (cleared on success).
- Synthetic group code is `"(直接貼上 N)"`; per-row `name` comes from sidecar's `dn=` extract (so each row can carry its own JAV code).

**Calls**:
- `parseMagnetBatch(magnetBatch)` (lib/scraper.ts:94)
- `invoke('register_magnets', { magnets })` → `{ registered[], invalid[] }`

**Triggered by**: Markup button [1567](../../../app/src/App.svelte#L1567).

---

### 3.6 Clipboard / single-row actions

#### `copyOne(handle_id: string, label: string): Promise<void>`  *(App.svelte:[363](../../../app/src/App.svelte#L363))*

**Purpose**: Copy one magnet via sidecar (handle-id indirection — UI never sees raw magnet).

**Contract**: Writes `statusMessage` (ok or error).

**Calls**: `invoke('copy_magnet', { handleId })`.

**Triggered by**: Per-row `複製` button [1667](../../../app/src/App.svelte#L1667), per-row `ondblclick` [1657](../../../app/src/App.svelte#L1657).

---

#### `copyVisible(): Promise<void>`  *(App.svelte:[372](../../../app/src/App.svelte#L372))*

**Purpose**: Bulk-copy every handle id from currently visible (filtered/sorted/group-picked) rows, deduped across groups.

**Contract**: Early return if `ids.length === 0`. Writes `statusMessage`. Reports `result.copied` and `result.unknown` (stale handles) separately.

**Calls**: `processedRows(g)` per group; `invoke('copy_magnets_bulk', { handleIds })` → `CopyBulkResult`.

**Triggered by**: Markup button [1466](../../../app/src/App.svelte#L1466).

---

### 3.7 Filter / sort / collapse helpers

#### `processedRows(g: ScrapedGroup): MagnetRow[]`  *(App.svelte:[401](../../../app/src/App.svelte#L401))*

**Purpose**: Thin wrapper delegating to `processGroupRows` (lib/magnetUtils.ts:147) with current filter/sort state.

**Reads**: `filter`, `sortColumn`, `sortDirection`. **Pure** w.r.t. component state.

**Called by**: `copyVisible`, `buildVisibleSendItems`, `webVisibleRows` / `manualVisibleRows` derived（`allVisibleRows` 由兩者組成，供三個全選/反選按鈕共用）, markup `{@const rows = processedRows(g)}` [1584](../../../app/src/App.svelte#L1584).

---

#### `toggleSort(col: SortColumn): void`  *(App.svelte:[405](../../../app/src/App.svelte#L405))*

**Purpose**: If same column → flip direction; else set new column + `asc`. **Writes** `sortColumn`, `sortDirection`.

**Triggered by**: Table header buttons [1629, 1634, 1639, 1644](../../../app/src/App.svelte#L1629).

---

#### `sortIndicator(col: SortColumn): string`  *(App.svelte:[414](../../../app/src/App.svelte#L414))*

**Purpose**: Returns `" ▲"`, `" ▼"`, or `""` based on whether `col` matches `sortColumn`. Used in header labels.

**Triggered by**: Markup interpolation in table headers.

---

#### `commitMinSize(): void`  *(App.svelte:[419](../../../app/src/App.svelte#L419))*

**Purpose**: Commit `minSizeInput` (string) into `filter.min_size_gb` (number | null). `parseFloat` + finite-and-positive check; otherwise `null`.

**Triggered by**: `onchange` on min-size input [1517](../../../app/src/App.svelte#L1517).

---

#### `commitMaxSize(): void`  *(App.svelte:[424](../../../app/src/App.svelte#L424))*

**Purpose**: Symmetric to `commitMinSize` for `maxSizeInput`/`filter.max_size_gb`.

**Triggered by**: `onchange` on max-size input [1527](../../../app/src/App.svelte#L1527).

---

#### `setGroupPick(p: GroupPick): void`  *(App.svelte:[429](../../../app/src/App.svelte#L429))*

**Purpose**: Writes `filter.group_pick`. Trivial setter (could be inlined; called from the `<select>` `onchange` arrow [1534](../../../app/src/App.svelte#L1534)).

---

#### `resetFilter(): void`  *(App.svelte:[433](../../../app/src/App.svelte#L433))*

**Purpose**: Reset filter+sort+input-strings to defaults.

**Writes**: `filter`, `minSizeInput`, `maxSizeInput`, `sortColumn`, `sortDirection`.

**Triggered by**: Markup button [1542](../../../app/src/App.svelte#L1542).

---

#### `toggleCollapsed(url: string): void`  *(App.svelte:[441](../../../app/src/App.svelte#L441))*

**Purpose**: Flip `collapsed[url]` boolean (used as group card collapse state).

**Triggered by**: Per-group toggle button [1590](../../../app/src/App.svelte#L1590).

---

#### `clearResults(): Promise<void>`  *(App.svelte:[445](../../../app/src/App.svelte#L445))*

**Purpose**: Wipe `groups`, abort any in-flight scrape, and tell sidecar to forget the handles.

**Contract**:
- If `isScraping` → aborts scrape first.
- Snapshots all handle_ids before clearing `groups` (so we can pass them to `forget_magnets`).
- Always clears local UI state (`groups = []`, `scrapeProgress`, `collapsed`) — sidecar GC failure is degraded to a warning, not surfaced as an error.

**Calls**: `scrapeAbort?.abort()`, `invoke('forget_magnets', { handleIds })` → `number`.

**Triggered by**: Markup button [1476](../../../app/src/App.svelte#L1476).

---

### 3.8 Real-Debrid token management

#### `rdTestToken(): Promise<void>`  *(App.svelte:[495](../../../app/src/App.svelte#L495))*

**Purpose**: One-shot token test that doesn't persist — calls `rd_test_token` with the typed-in token. Writes `rdUser` on success, `rdMessage` either way.

**Calls**: `invoke('rd_test_token', { token })` → `RdUserInfo`. Wraps errors with `rdErrorMessage(code)` (lib/rdSender.ts:216).

**Triggered by**: Markup button [1150](../../../app/src/App.svelte#L1150).

---

#### `rdSaveToken(): Promise<void>`  *(App.svelte:[510](../../../app/src/App.svelte#L510))*

**Purpose**: Persist token to system credential store; immediately re-verify via `rd_check_user` (which reads from store, so the token never crosses IPC again).

**Contract**:
- Guard: empty input → `rdMessage` early return.
- Writes: `rdHasToken`, `rdTokenInput` (clears), `rdShowToken` (false), `rdUser`, `rdMessage`.

**Calls**: `invoke('rd_save_token', { token })`, `invoke('rd_check_user')`.

**Triggered by**: Markup button [1153](../../../app/src/App.svelte#L1153).

---

#### `rdClearToken(): Promise<void>`  *(App.svelte:[534](../../../app/src/App.svelte#L534))*

**Purpose**: Remove token from credential store; clear `rdUser`/`rdTokenInput`/`rdHasToken`.

**Calls**: `invoke('rd_clear_token')`.

**Triggered by**: Markup button [1107](../../../app/src/App.svelte#L1107).

---

#### `rdRefreshUser(): Promise<void>`  *(App.svelte:[547](../../../app/src/App.svelte#L547))*

**Purpose**: Re-query the stored token for fresh user info (points, expiration).

**Contract**: Guard if no token. Writes `rdUser`, `rdMessage`.

**Calls**: `invoke('rd_check_user')` → `RdUserInfo`.

**Triggered by**: Markup button [1106](../../../app/src/App.svelte#L1106).

---

### 3.9 Real-Debrid send-batch flow

#### `buildVisibleSendItems(): RdSendItem[]`  *(App.svelte:[578](../../../app/src/App.svelte#L578))*

**Purpose**: Construct the `RdSendItem[]` payload from currently visible rows, deduped by `handle_id`.

**Contract**:
- Pure (no state mutation).
- Code-resolution: paste groups (`url.startsWith('manual://')`) prefer the row's own `name` (sidecar's `dn=` extract) — falls back to group code. JavDB groups prefer the group code.
- Dedupe via `dedupeByHandleId` (lib/magnetUtils.ts:169) — first occurrence wins.

**Reads**: `groups`, plus `filter`/`sortColumn`/`sortDirection` via `processedRows`.

**Called by**: `sendVisibleToRd`.

---

#### `sendVisibleToRd(): Promise<void>`  *(App.svelte:[598](../../../app/src/App.svelte#L598))*

**Purpose**: Send currently visible magnets to Real-Debrid, streaming per-item progress.

**Contract**:
- Guards: `isRdSending` reentry; `rdHasToken` (writes `rdMessage`); empty items (writes `rdMessage`).
- Initialises `rdSendProgress` slots (one per item, status `"pending"`), `rdSendDone`, `rdSendAbort`.
- Per-item callback replaces `rdSendProgress[index-1]`; only advances `done` counter when status leaves `"sending"` (so in-flight items don't tick the counter).
- `finally`: clears `isRdSending`/`rdSendAbort`, refreshes `pendingEntries` from disk (sidecar may have added entries for `in_pending` items).
- Passes `settings.rd.{file_pick, min_size_mb, cache_wait_seconds}` as `defaults` when present; falls back to `{}` if `settings` is null.

**Calls**:
- `buildVisibleSendItems()`
- `sendBatch(items, callback, { signal, defaults })` (lib/rdSender.ts:70) — that lib invokes `rd_send_magnet` per item.
- `invoke('pending_list')` (in `finally`).

**Triggered by**: Markup button [1470](../../../app/src/App.svelte#L1470).

---

#### `cancelRdSend(): void`  *(App.svelte:[654](../../../app/src/App.svelte#L654))*

**Purpose**: Abort the in-flight send batch.

**Triggered by**: Markup button [1696](../../../app/src/App.svelte#L1696).

---

#### `copyRdDownloads(): Promise<void>`  *(App.svelte:[658](../../../app/src/App.svelte#L658))*

**Purpose**: Collect every `link.download` URL from `completed` rows and dump to clipboard via sidecar bulk-copy.

**Contract**: Empty lines → `rdMessage` + return. Otherwise reports `result.copied`.

**Calls**: `invoke('copy_rd_links_bulk', { links })` → `CopyRdLinksBulkResult`.

**Triggered by**: Markup button [1699](../../../app/src/App.svelte#L1699).

---

### 3.10 Pending retry flow

#### `refreshPending(): Promise<void>`  *(App.svelte:[687](../../../app/src/App.svelte#L687))*

**Purpose**: Reload `pending_torrents.json` from disk. Does NOT query RD (per the explicit comment).

**Contract**: Writes `pendingEntries`, `pendingMessage` (`info` on ok, `error` on failure). The explicit message exists so the button isn't "silent".

**Calls**: `invoke('pending_list')`.

**Triggered by**: Markup button [1782](../../../app/src/App.svelte#L1782).

---

#### `retryAllPending(): Promise<void>`  *(App.svelte:[699](../../../app/src/App.svelte#L699))*

**Purpose**: Loop every pending entry through `retryPending`, reconcile any matching row in `rdSendProgress`, then auto-copy newly-completed download links to clipboard and produce a summary line.

**Contract**:
- Guards: `isRetryingPending` reentry, empty list early return.
- Per-event reconciliation:
  - `completed` → bump `completedCount`; collect download URLs; find matching `rdSendProgress[i].torrent_id` and flip it to `completed` with the fresh links (so the 直連 N counter and row labels update without a manual re-send).
  - `pending` → bump `stillPendingCount`.
  - `missing` → bump `missingCount`; flip the matching `rdSendProgress` row to `error` with `error_code = "rd_torrent_missing"`.
  - else → bump `errorCount`, capture `error_code`.
- `finally`: refresh `pendingEntries` from disk (sidecar deletes completed/missing entries; updates progress on still-pending). Deliberately bypasses `refreshPending()` so the generic "已重新載入" message doesn't overwrite the retry summary.
- After loop: build summary string, append `copy_rd_links_bulk` result if links were collected, surface first error code via `rdErrorMessage`.

**Calls**:
- `retryPending(entries, callback, { signal })` (lib/rdSender.ts:155) — invokes `rd_pending_status` per entry internally.
- `invoke('pending_list')` (in `finally`).
- `invoke('copy_rd_links_bulk', { links })` if completedLinks not empty.
- `rdErrorMessage(code)` (lib/rdSender.ts:216).

**Triggered by**: Markup button [1774](../../../app/src/App.svelte#L1774).

---

#### `cancelRetry(): void`  *(App.svelte:[815](../../../app/src/App.svelte#L815))*

**Purpose**: Abort in-flight retry. Triggered by markup button [1780](../../../app/src/App.svelte#L1780).

---

#### `removePending(torrent_id: string): Promise<void>`  *(App.svelte:[1022](../../../app/src/App.svelte#L1022))*

**Purpose**: Remove a single pending entry; sidecar returns the new list. Writes `pendingEntries`, `pendingMessage`.

**Calls**: `invoke('pending_remove', { torrentId })` → `PendingEntry[]`.

**Triggered by**: Per-row 「移除」 button [1812](../../../app/src/App.svelte#L1812).

---

#### `clearAllPending(): Promise<void>`  *(App.svelte:[1036](../../../app/src/App.svelte#L1036))*

**Purpose**: Wipe all pending entries.

**Calls**: `invoke('pending_clear')`. Sets `pendingEntries = []`.

**Triggered by**: Markup button [1785](../../../app/src/App.svelte#L1785).

---

### 3.11 Legacy import (M7a-lite)

#### `previewLegacyImport(): Promise<void>`  *(App.svelte:[825](../../../app/src/App.svelte#L825))*

**Purpose**: Read `legacyPath`, ask sidecar to inspect files without applying anything. Secret values are NEVER echoed back to WebView (sidecar contract).

**Contract**:
- Resets `legacyError`/`legacyReport`/`legacyPreview` first.
- Empty path → `legacyError`, return.
- Writes `legacyPreview` on success; `legacyError` on failure; `legacyBusy` set/finally.

**Calls**: `invoke('preview_legacy_import', { sourceDir })` → `LegacyImportPreview`.

**Triggered by**: Markup button [1187](../../../app/src/App.svelte#L1187).

---

#### `applyLegacyImportConfirmed(): Promise<void>`  *(App.svelte:[976](../../../app/src/App.svelte#L976))*

**Purpose**: Apply a previewed legacy import — sidecar writes RD token to credential store, applies env-derived settings, copies cookies, imports pending entries. Then this function refreshes ALL dependent UI state.

**Contract**:
- Same guard / busy / error handling shape as `previewLegacyImport`.
- After success, conditionally refreshes:
  - `rd_token_imported` → `rdHasToken = true`
  - `env_imported` → re-`read_settings` + apply theme/scale
  - `pending_imported > 0` → re-fetch `pending_list`
  - `cookies_imported` → `refreshCookiesStatus()`
- Writes `legacyReport`, `legacyError`, `legacyBusy`.

**Calls**:
- `invoke('apply_legacy_import', { sourceDir })` → `LegacyImportReport`.
- `invoke('read_settings')` (conditional).
- `invoke('pending_list')` (conditional).
- `refreshCookiesStatus()` (conditional).
- `applyTheme`, `applyScale` (conditional).

**Triggered by**: Markup button [1191](../../../app/src/App.svelte#L1191).

---

### 3.12 Cookies / data-dir helpers (M7b)

#### `refreshCookiesStatus(): Promise<void>`  *(App.svelte:[847](../../../app/src/App.svelte#L847))*

**Purpose**: Refresh cookies-file snapshot (path, size, mtime — never content).

**Contract**: Clears `cookiesError`; writes `cookiesStatus` (or nulls + `cookiesError` on failure).

**Calls**: `invoke('get_cookies_status')` → `CookiesStatus`.

**Triggered by**: `onMount`, `createCookiesTemplate`, `applyLegacyImportConfirmed`, markup button [1438](../../../app/src/App.svelte#L1438).

---

#### `openDataDir(): Promise<void>`  *(App.svelte:[857](../../../app/src/App.svelte#L857))*

**Purpose**: Open the app's data dir in the OS file manager. Writes `cookiesError` on failure.

**Calls**: `invoke('open_data_dir')`.

**Triggered by**: Markup button [1439](../../../app/src/App.svelte#L1439).

---

#### `openLogsDir(): Promise<void>`  *(App.svelte:[866](../../../app/src/App.svelte#L866))*

**Purpose**: Symmetric to `openDataDir` for the logs directory.

**Calls**: `invoke('open_logs_dir')`.

**Triggered by**: Markup button [1440](../../../app/src/App.svelte#L1440).

---

#### `createCookiesTemplate(): Promise<void>`  *(App.svelte:[875](../../../app/src/App.svelte#L875))*

**Purpose**: Have sidecar write a placeholder `cookies.txt` so the user can fill it in. Then auto-refresh status.

**Contract**: Writes `cookiesMessage` (ok/error); on success calls `refreshCookiesStatus`.

**Calls**: `invoke('create_cookies_template')`, `refreshCookiesStatus()`.

**Triggered by**: Markup button [1442](../../../app/src/App.svelte#L1442) (only visible when cookies missing).

---

#### `formatBytes(n: number): string`  *(App.svelte:[890](../../../app/src/App.svelte#L890))*

**Purpose**: Format byte count as B / KB / MB string (no GB tier — cookies files are tiny).

**Pure**. Called by markup for `cookiesStatus.size_bytes` formatting [1417](../../../app/src/App.svelte#L1417).

---

### 3.13 Settings editor (M7c)

#### `openSettingsEditor(): void`  *(App.svelte:[902](../../../app/src/App.svelte#L902))*

**Purpose**: Initialise `settingsDraft` as a shallow-cloned editable copy of `settings`, blanking `api_token` (the editor never displays it). Sets `settingsShown = true`.

**Contract**:
- Guard: if `settings` is null, writes `settingsMessage`/Kind = error and returns.
- Writes `settingsDraft`, `settingsShown`, `settingsMessage`.

**Triggered by**: Toggle button [1282](../../../app/src/App.svelte#L1282) (only opens, never via direct call).

---

#### `saveSettings(): Promise<void>`  *(App.svelte:[919](../../../app/src/App.svelte#L919))*

**Purpose**: Persist `settingsDraft` to disk, push to sidecar for the current session, then refresh canonical `settings` + dependent UI (theme/scale).

**Contract**:
- Guards: no draft → return; not `settingsValid` → message + return.
- Always blanks `api_token` on save (defense in depth — sidecar also blanks it).
- `update_sidecar_settings` failure is non-fatal (just `console.warn`).
- After save, re-`read_settings` so canonical state matches disk + re-clones draft.
- Writes: `settingsSaving` (set/finally), `settingsMessage`, `settingsMessageKind`, `settings`, `theme`, `settingsDraft`.

**Calls**:
- `invoke('write_settings', { settings: toSave })`
- `invoke('update_sidecar_settings', { settings: toSave })`
- `invoke('read_settings')`
- `applyTheme`, `applyScale`.

**Triggered by**: Markup button [1387](../../../app/src/App.svelte#L1387).

---

#### `revertSettingsDraft(): void`  *(App.svelte:[965](../../../app/src/App.svelte#L965))*

**Purpose**: Reset `settingsDraft` to the currently-loaded `settings` (un-saved edits discarded).

**Triggered by**: Markup button [1390](../../../app/src/App.svelte#L1390).

---

### 3.14 Trivial inline arrow callbacks (summary)

These are inlined in markup rather than declared at the top level; they're listed for completeness:

- `() => (legacyShown = !legacyShown)` — toggle button [1168](../../../app/src/App.svelte#L1168)
- `() => { if (!settingsShown) openSettingsEditor(); else settingsShown = false; }` — settings toggle [1282](../../../app/src/App.svelte#L1282)
- `() => (cookiesShown = !cookiesShown)` — cookies toggle [1403](../../../app/src/App.svelte#L1403)
- `(e) => { e.preventDefault(); openExternal('https://real-debrid.com/apitoken').catch(...) }` — external link [1129](../../../app/src/App.svelte#L1129)
- `(e) => setGroupPick((e.currentTarget as HTMLSelectElement).value as GroupPick)` — group-pick select [1534](../../../app/src/App.svelte#L1534)
- `() => toggleCollapsed(g.url)` — per-group toggle [1590](../../../app/src/App.svelte#L1590)
- `() => toggleSort('name'|'size'|'tags'|'date')` — table header buttons [1629–1645](../../../app/src/App.svelte#L1629)
- `() => copyOne(m.handle_id, m.name || g.result!.code)` — per-row copy [1657, 1667](../../../app/src/App.svelte#L1657)
- `() => removePending(p.torrent_id)` — pending row remove [1812](../../../app/src/App.svelte#L1812)

---

## 4. Call graph — top user flows

### 4.1 Boot

```
Svelte mount
└── onMount [141]
    ├── invoke('get_paths')                 → sets dataDir, logDir
    ├── invoke('read_settings')             → settings, theme
    │   ├── applyTheme(theme)               [121] → <html data-theme>
    │   └── applyScale(s.ui.scale)          [131] → CSS var + font-size
    ├── invoke('rd_has_token')              → rdHasToken
    ├── invoke('pending_list')              → pendingEntries
    ├── invoke('get_legacy_default_dir')    → legacyPath, legacyShown
    └── refreshCookiesStatus()              [847]
        └── invoke('get_cookies_status')    → cookiesStatus
```

### 4.2 "Scrape" button click

```
button.onclick [1461]
└── startScrape [218]
    ├── parseUrlBatch(urlBatch)             (lib/scraper.ts:72)
    ├── (init groups, scrapeProgress, isScraping, scrapeAbort)
    └── scrapeBatch(urls, cb, {signal})     (lib/scraper.ts:114)
        ├── per URL: invoke('scrape_javdb_url', ...)
        └── cb(ev: ScrapeProgressEvent)
            └── groups[ev.index-1] = ev.group; scrapeProgress = {ev.index, ev.total}
```

UI re-render path: `groups` mutation → `processedRows` recomputed in markup → derived `okCount` / `errCount` / `totalRawMagnets` / `allVisibleRows` update → status bar + groups list re-render.

### 4.3 "Send to RD" button click

```
button.onclick [1470]
└── sendVisibleToRd [598]
    ├── buildVisibleSendItems [578]
    │   ├── for each group: processedRows(g)
    │   │   └── processGroupRows(g, filter, sortColumn, sortDirection) (lib/magnetUtils.ts:147)
    │   └── dedupeByHandleId (lib/magnetUtils.ts:169)
    ├── (init rdSendProgress, rdSendDone, rdSendAbort)
    └── sendBatch(items, cb, {signal, defaults}) (lib/rdSender.ts:70)
        ├── per item: invoke('rd_send_magnet', ...)
        └── cb(ev: RdSendBatchEvent)
            └── rdSendProgress[ev.index-1] = ev.item
                if ev.item.status !== "sending": rdSendDone = {ev.index, ev.total}
    finally:
    └── invoke('pending_list')   → pendingEntries (pick up newly added in_pending)
```

### 4.4 "Paste magnet → register" flow

```
button.onclick [1567]
└── registerPastedMagnets [265]
    ├── parseMagnetBatch(magnetBatch) (lib/scraper.ts:94)
    ├── invoke('register_magnets', { magnets })
    ├── snapshot existingHandleIds from current groups[].result.magnets
    ├── filter resp.registered: skip deduped+existing
    └── (push synthetic group with url='manual://<ts>' into groups)
```

Downstream: visible-count derived recomputes, filter/sort table picks up new rows, and the send-to-RD button activates (assuming `rdHasToken`).

### 4.5 "Retry all pending" flow

```
button.onclick [1774]
└── retryAllPending [699]
    ├── (init isRetryingPending, retryAbort, pendingMessage)
    └── retryPending(pendingEntries, cb, {signal}) (lib/rdSender.ts:155)
        ├── per entry: invoke('rd_pending_status', ...)
        └── cb(ev: RdRetryEvent)
            ├── completed → collect links + flip matching rdSendProgress row → "completed"
            ├── pending   → bump stillPending
            ├── missing   → flip matching rdSendProgress row → "error/rd_torrent_missing"
            ├── else      → bump errorCount, capture error_code
            └── pendingMessage = "重試中 N/M…"
    finally:
    └── invoke('pending_list')   → pendingEntries
    if completedLinks:
    └── invoke('copy_rd_links_bulk', {links})
    pendingMessage = final summary
```

### 4.6 "Save settings" flow

```
button.onclick [1387]
└── saveSettings [919]
    ├── validate via $derived settingsValid
    ├── invoke('write_settings', { settings: toSave })   (api_token blanked)
    ├── invoke('update_sidecar_settings', { settings })  (non-fatal on failure)
    ├── invoke('read_settings')                          → settings
    ├── applyTheme(theme); applyScale(settings.ui.scale)
    └── settingsDraft re-cloned from fresh settings
```

### 4.7 "Apply legacy import" flow

```
button.onclick [1191]
└── applyLegacyImportConfirmed [976]
    ├── invoke('apply_legacy_import', { sourceDir })   → LegacyImportReport
    ├── if rd_token_imported: rdHasToken = true
    ├── if env_imported:
    │   └── invoke('read_settings') + applyTheme + applyScale
    ├── if pending_imported > 0:
    │   └── invoke('pending_list')
    └── if cookies_imported:
        └── refreshCookiesStatus()
```

---

## 5. Markup-side notes

### 5.1 Top-level structure

`<main class="container">` is one big sequence of `<section>` blocks. There is **no router**, **no modal overlay**, **no nested component** — every panel is inline and always rendered (some are gated by collapse booleans, but none of them is a true modal).

| Section | Lines | Gate | Notes |
|---|---|---|---|
| `<h1>` + subtitle | [1064–1065](../../../app/src/App.svelte#L1064) | always | header |
| 儲存位置 (Storage paths) | [1067–1075](../../../app/src/App.svelte#L1067) | always | shows `dataDir`, `logDir` |
| 主題 (Theme) | [1077–1085](../../../app/src/App.svelte#L1077) | always | `toggleTheme` button + `statusMessage` |
| Sidecar | [1087–1095](../../../app/src/App.svelte#L1087) | always | `pingSidecar` button |
| Real-Debrid | [1097–1161](../../../app/src/App.svelte#L1097) | always | token input, save/test/clear; conditional: `rdUser` user line, `rdMessage` status |
| 匯入舊版資料 (Legacy import) | [1163–1275](../../../app/src/App.svelte#L1163) | `{#if legacyShown}` [1172](../../../app/src/App.svelte#L1172) | preview / apply / report inside; preview-vs-report shown by `{#if legacyPreview}` and `{#if legacyReport}` |
| 應用程式設定 (Settings editor) | [1277–1396](../../../app/src/App.svelte#L1277) | `{#if settingsShown && settingsDraft}` [1289](../../../app/src/App.svelte#L1289) | two `<fieldset>`s (RD behaviour + UI). Bound via `bind:value={settingsDraft.rd.*/ui.*}` |
| JavDB Cookies | [1398–1446](../../../app/src/App.svelte#L1398) | `{#if cookiesShown}` [1407](../../../app/src/App.svelte#L1407) | refresh / open dirs / create template |
| 批次擷取 (Scrape) | [1448–1549](../../../app/src/App.svelte#L1448) | always | URL textarea + action row + status bar + filter row + groups (only when `groups.length > 0`) |
| 直接貼磁力 (Paste magnet) | [1551–1682](../../../app/src/App.svelte#L1551) | always | magnet textarea + register button + **groups list rendering lives here** (`{#if groups.length > 0}` [1581](../../../app/src/App.svelte#L1581)) |
| 送至 Real-Debrid 進度 (Send progress) | [1684–1757](../../../app/src/App.svelte#L1684) | `{#if rdSendProgress.length > 0}` [1684](../../../app/src/App.svelte#L1684) | per-row status table; only Cancel button visible while sending |
| 待處理（Real-Debrid） (Pending) | [1759–1819](../../../app/src/App.svelte#L1759) | `{#if pendingEntries.length > 0}` [1759](../../../app/src/App.svelte#L1759) | retry-all / refresh-local / clear-all + per-row table |

### 5.2 Event binding hotspots

- **Settings form binds** (drives derived `settingsErrors`/`settingsValid`): [1299, 1317, 1332, 1347, 1361, 1374](../../../app/src/App.svelte#L1299).
- **Filter row** (drives `processedRows`): [1502, 1507, 1516–1517, 1526–1527, 1533–1535, 1542](../../../app/src/App.svelte#L1502).
- **Group table sort header buttons**: [1629–1645](../../../app/src/App.svelte#L1629).
- **Per-row magnet copy** (both row dblclick and per-row button): [1657, 1666](../../../app/src/App.svelte#L1657).
- **Scrape action row**: [1461–1476](../../../app/src/App.svelte#L1461).
- **Send-to-RD action row**: [1696, 1699](../../../app/src/App.svelte#L1696).
- **Pending action row**: [1773–1787](../../../app/src/App.svelte#L1773).
- **Per-pending row remove**: [1812](../../../app/src/App.svelte#L1812).

### 5.3 `{#each}` lists

- `legacyPreview.warnings` [1228](../../../app/src/App.svelte#L1228)
- `legacyReport.sources` [1255](../../../app/src/App.svelte#L1255)
- `legacyReport.warnings` [1265](../../../app/src/App.svelte#L1265)
- `FILE_PICK_VALUES` / `THEME_VALUES` / `SCALE_PRESETS` `<option>` lists [1300, 1362, 1375](../../../app/src/App.svelte#L1300)
- `groups` keyed by `g.url` [1583](../../../app/src/App.svelte#L1583)
- `rows` keyed by `m.handle_id` [1653](../../../app/src/App.svelte#L1653)
- `rdSendProgress` keyed by `row.handle_id` [1716](../../../app/src/App.svelte#L1716)
- `row.links` (per `completed` row) [1735](../../../app/src/App.svelte#L1735)
- `pendingEntries` keyed by `p.torrent_id` [1803](../../../app/src/App.svelte#L1803)

### 5.4 Style

The `<style>` block ([1822–2177](../../../app/src/App.svelte#L1822)) is component-scoped (Svelte default). It uses CSS custom properties (`--color-*`, `--ui-scale`) that `applyTheme` / `applyScale` and `index.css` are responsible for defining. No animations, no media queries, no nested selectors — purely declarative.

---

## 6. Refactor hotspots

Brief and factual; final judgement is the user's.

1. **`retryAllPending` ([699–813](../../../app/src/App.svelte#L699)) is ~115 lines**, mixes four concerns: iteration/accumulators, per-event reconciliation against `rdSendProgress`, post-loop pending-list refresh (with a deliberate bypass of `refreshPending`), and a multi-fragment summary builder that also performs a follow-up clipboard write. Easy split: (a) reconciliation helper `reconcileRdProgressRow(torrent_id, patch)`, (b) summary-string builder, (c) thin orchestrator. Same reconciliation logic exists in two `for` loops (completed branch [727–737](../../../app/src/App.svelte#L727), missing branch [745–755](../../../app/src/App.svelte#L745)) — direct duplication.

2. **Status-message state is fragmented across 8+ variables** with similar shapes: `statusMessage` (plain string), `pingMessage` (plain string), `rdMessage` (plain string), `registerStatus` ({kind,text}), `pendingMessage` ({kind,text}), `cookiesError`+`cookiesMessage`, `settingsMessage`+`settingsMessageKind`, `legacyError`. Several pieces of code write to one or another based on which section they belong to; consolidating around a single `{kind, text, scope}` discriminated union (or one-per-section helper) would also let the markup use a single inline-msg component.

3. **`registerPastedMagnets` ([265–361](../../../app/src/App.svelte#L265)) is ~95 lines** packing four steps inline: parse + heuristic error detection, sidecar invoke, cross-group dedupe with `existingHandleIds`, and synthetic group construction with bespoke `name`/`code` logic. The synthetic-group code resolution rule (`name` for paste groups, group `code` for JavDB) is also re-implemented in `buildVisibleSendItems` ([578–596](../../../app/src/App.svelte#L578)) via the `isPasteGroup = g.url.startsWith('manual://')` check — that string sentinel is used in two places and isn't a named constant. A `groupKind: "javdb" | "manual"` discriminator on `ScrapedGroup` would localize the rule.

Adjacent smaller observations (not in the top 3, but worth listing):

- `applyLegacyImportConfirmed` ([976–1020](../../../app/src/App.svelte#L976)) re-implements three pieces of boot logic (`read_settings` + theme/scale apply; `pending_list` fetch; `refreshCookiesStatus`) — extracting an `applySettingsFromDisk()` helper would remove the duplication shared with `onMount` and `saveSettings`.
- `settingsDraft` is rebuilt with the same shallow-clone+blank-token shape in three places ([910–914](../../../app/src/App.svelte#L910), [931–934](../../../app/src/App.svelte#L931), [950–954](../../../app/src/App.svelte#L950), [967–971](../../../app/src/App.svelte#L967)) — pull out `cloneSettingsForDraft(s)`.
- `groups` is mutated as both whole-array replacement and per-index slot replacement (`groups[ev.index-1] = ev.group`) — the latter relies on Svelte 5 fine-grained reactivity but is easy to miss; a comment near the declaration would help.
- `cancelScrape` / `cancelRdSend` / `cancelRetry` are three identical 3-line wrappers around three `AbortController?.abort()` calls; could be a single `abortController.value?.abort()` pattern with a shared helper, but they're cheap as-is.
