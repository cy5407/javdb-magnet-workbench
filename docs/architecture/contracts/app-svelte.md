# `app/src/App.svelte` — Function & State Contract Reference

**Source**: [`app/src/App.svelte`](../../../app/src/App.svelte) (3422 lines, single-file Svelte 5 component)
**Last refreshed**: against HEAD `7c877a8` on 2026-10-16 (originally written on `codex/function-contracts-analysis` against a 2177-line revision).

The file is organized as:

- `<script lang="ts">` — lines [1–1668](../../../app/src/App.svelte#L1)
- `<main>` markup — lines [1670–2873](../../../app/src/App.svelte#L1670)
- `<style>` — lines [2875–3426](../../../app/src/App.svelte#L2875)

Surface at a glance: 65 top-level functions (+ the `onMount` callback), 56 `$state` vars, 27
`$derived` (5 of them `$derived.by`), 36 `invoke()` call sites reaching 28 distinct Rust
commands.

---

## 1. Component overview

### 1.1 Imports

**Svelte / Tauri APIs**

- `onDestroy`, `onMount` from `svelte` ([App.svelte:2](../../../app/src/App.svelte#L2))
- `invoke` from `@tauri-apps/api/core` ([App.svelte:4](../../../app/src/App.svelte#L4))
- `open as openExternal` from `@tauri-apps/plugin-shell` ([App.svelte:5](../../../app/src/App.svelte#L5))

**Lib modules**

- `./lib/flashAction` — `createFlashController` ([App.svelte:3](../../../app/src/App.svelte#L3))
- `./lib/scraper` — `applyScrapeProgressForRun`, `parseMagnetBatch`, `parseUrlBatch`, `scrapeBatch`, type `ScrapeProgressEvent` ([App.svelte:6–12](../../../app/src/App.svelte#L6))
- `./lib/errText` — `errText` ([App.svelte:13](../../../app/src/App.svelte#L13))
- `./lib/magnetUtils` — `dedupeByHandleId`, `isManualGroup`, `pickRdReadyRow`, `processGroupRows` ([App.svelte:14–19](../../../app/src/App.svelte#L14))
- `./lib/rdPriority` — `classifyRow`, `rdBadge`, `summarizeRdLikelihood`, types `RdCandidate`, `RdPickTier`, `RdRowClass` ([App.svelte:20–27](../../../app/src/App.svelte#L20))
- `./lib/settingsValidation` — `FILE_PICK_VALUES`, `SCALE_PRESETS`, `THEME_VALUES`, `validateSettingsDraft` ([App.svelte:28–33](../../../app/src/App.svelte#L28))
- `./lib/rdSender` — `applyRetryEventToProgressRows`, `buildRdDisplayRows`, `collectDownloadLinksFromRow`, `formatCompletedAt`, `rdErrorMessage`, `retryPending`, `sendBatch`, `sortCompletedRowsByCompletionTime`, types `RdRetryEvent`, `RdSendBatchEvent`, `RdSendItem` ([App.svelte:34–46](../../../app/src/App.svelte#L34))

**Types (from `./lib/types`)** ([App.svelte:47–67](../../../app/src/App.svelte#L47))

`defaultFilterState`, `CookiesStatus`, `CopyBulkResult`, `CopyRdLinksBulkResult`, `FilterState`, `LegacyImportPreview`, `LegacyImportReport`, `GroupPick`, `MagnetRow`, `PathInfo`, `PendingEntry`, `PingResponse`, `RdSendProgress`, `RdUserInfo`, `ScrapedGroup`, `Settings`, `SortColumn`, `SortDirection`, `Theme`.

**Svelte 5 runes used**: `$state`, `$derived`, `$derived.by`. Lifecycle: `onMount`, plus `onDestroy(() => flash.dispose())` ([App.svelte:1117](../../../app/src/App.svelte#L1117)) which clears all pending flash timers; no `$effect`.

**Non-reactive module-level bindings**: `TAB_ORDER` (const, [75](../../../app/src/App.svelte#L75)), `scrapeAbort` / `scrapeRunId` ([108–109](../../../app/src/App.svelte#L108)), `rdSendAbort` ([134](../../../app/src/App.svelte#L134)), `retryAbort` ([149](../../../app/src/App.svelte#L149)), `flash` (const `createFlashController()`, [1116](../../../app/src/App.svelte#L1116)). The three `AbortController` holders are plain `let`, not `$state`.

### 1.2 Tauri command surface — every `invoke()` call

36 call sites, 28 distinct commands:

| Rust command | Caller (App.svelte) | Line |
|---|---|---|
| `get_paths` | `onMount` | [232](../../../app/src/App.svelte#L232) |
| `read_settings` | `loadAndApplySettings` (used by `onMount`, `saveSettings`, `applyLegacyImportConfirmed`) | [214](../../../app/src/App.svelte#L214) |
| `rd_has_token` | `onMount` | [249](../../../app/src/App.svelte#L249) |
| `pending_list` | `reloadPendingSilently` (used by `onMount`, `runSendBatch` finally, `retryAllPending` finally, `applyLegacyImportConfirmed`), `refreshPending` | [224](../../../app/src/App.svelte#L224), [1192](../../../app/src/App.svelte#L1192) |
| `get_legacy_default_dir` | `onMount` | [259](../../../app/src/App.svelte#L259) |
| `write_settings` | `toggleTheme`, `saveSettings` | [290](../../../app/src/App.svelte#L290), [1549](../../../app/src/App.svelte#L1549) |
| `sidecar_ping` | `pingSidecar` | [314](../../../app/src/App.svelte#L314) |
| `forget_magnets` | `startScrape` (stale web handles), `clearResults` | [377](../../../app/src/App.svelte#L377), [737](../../../app/src/App.svelte#L737) |
| `register_magnets` | `registerPastedMagnets` | [448](../../../app/src/App.svelte#L448) |
| `copy_magnet` | `copyOne` | [540](../../../app/src/App.svelte#L540) |
| `copy_magnets_bulk` | `copySelected` | [555](../../../app/src/App.svelte#L555) |
| `rd_test_token` | `rdTestToken` | [876](../../../app/src/App.svelte#L876) |
| `rd_save_token` | `rdSaveToken` | [895](../../../app/src/App.svelte#L895) |
| `rd_check_user` | `rdSaveToken`, `rdRefreshUser` | [903](../../../app/src/App.svelte#L903), [935](../../../app/src/App.svelte#L935) |
| `rd_clear_token` | `rdClearToken` | [916](../../../app/src/App.svelte#L916) |
| `copy_rd_links_bulk` | `copyRdDownloads`, `copyRdRow`, `copyRdSingleLink`, `retryAllPending` | [1133](../../../app/src/App.svelte#L1133), [1152](../../../app/src/App.svelte#L1152), [1170](../../../app/src/App.svelte#L1170), [1272](../../../app/src/App.svelte#L1272) |
| `preview_legacy_import` | `previewLegacyImport` | [1315](../../../app/src/App.svelte#L1315) |
| `migrate_cookies_now` | `refreshCookiesStatus` | [1336](../../../app/src/App.svelte#L1336) |
| `get_cookies_status` | `refreshCookiesStatus` (fallback), `clearCookies` (`cookies_cleared_sidecar_stale` path) | [1344](../../../app/src/App.svelte#L1344), [1406](../../../app/src/App.svelte#L1406) |
| `clear_cookies` | `clearCookies` | [1385](../../../app/src/App.svelte#L1385) |
| `save_cookies` | `saveCookies` | [1434](../../../app/src/App.svelte#L1434) |
| `open_data_dir` | `openDataDir` | [1461](../../../app/src/App.svelte#L1461) |
| `open_logs_dir` | `openLogsDir` | [1470](../../../app/src/App.svelte#L1470) |
| `create_cookies_template` | `createCookiesTemplate` | [1484](../../../app/src/App.svelte#L1484) |
| `update_sidecar_settings` | `saveSettings` | [1553](../../../app/src/App.svelte#L1553) |
| `apply_legacy_import` | `applyLegacyImportConfirmed` | [1591](../../../app/src/App.svelte#L1591) |
| `pending_remove` | `removePending` | [1625](../../../app/src/App.svelte#L1625) |
| `pending_clear` | `clearAllPending` | [1640](../../../app/src/App.svelte#L1640) |

Indirect `invoke` calls also happen inside the lib modules — `scrapeBatch` (`fetch_javdb`, [scraper.ts:116](../../../app/src/lib/scraper.ts#L116)), `sendBatch` (`rd_send_magnet`, [rdSender.ts:137](../../../app/src/lib/rdSender.ts#L137)) and `retryPending` (`rd_check_pending`, [rdSender.ts:143](../../../app/src/lib/rdSender.ts#L143)) each issue their own per-item invokes. They are documented in `frontend-lib.md`; from App.svelte's perspective they are a single async call with a progress callback. Together the 28 direct + 3 indirect commands are exactly the 31 registered in `generate_handler!` ([lib.rs:421–453](../../../app/src-tauri/src/lib.rs#L421)).

### 1.3 Event subscription surface

**None.** No `listen(...)` calls anywhere in the file. Progress is streamed via callbacks passed to `scrapeBatch` / `sendBatch` / `retryPending`, not via Tauri events. Cancellation uses `AbortController`s (plus `scrapeRunId` to drop late scrape events from a cancelled run).

### 1.4 Reactive graph (`$derived` dependencies)

| Derived | Depends on | Line |
|---|---|---|
| `settingsWriteBusy` | `isThemeSaving`, `settingsSaving`, `legacyBusy` — every `settings.json` writer excludes the others (`write_settings` is a whole-file overwrite) | [191](../../../app/src/App.svelte#L191) |
| `groupProcessedRowsMap` (`$derived.by`) | `groups`, `filter`, `sortColumn`, `sortDirection` — memoised `processGroupRows` per group url | [569](../../../app/src/App.svelte#L569) |
| `webGroups` | `groups` (non-manual) | [758](../../../app/src/App.svelte#L758) |
| `okCount` | `webGroups[].status` | [759](../../../app/src/App.svelte#L759) |
| `errCount` | `webGroups[].status` | [760](../../../app/src/App.svelte#L760) |
| `totalRawMagnets` | `webGroups[].result.magnet_count` | [761](../../../app/src/App.svelte#L761) |
| `webVisibleRows` | `webGroups`, `processedRows` | [768](../../../app/src/App.svelte#L768) |
| `manualVisibleRows` | `groups` (manual), `processedRows` | [769](../../../app/src/App.svelte#L769) |
| `allVisibleRows` | `webVisibleRows`, `manualVisibleRows` | [772](../../../app/src/App.svelte#L772) |
| `webVisibleMagnets` | `webVisibleRows` (deduped count) | [776](../../../app/src/App.svelte#L776) |
| `allSelectableRows` | `groups[].result.magnets`（不看 `filter`） | [777](../../../app/src/App.svelte#L777) |
| `webHandleIds` | `webGroups[].result.magnets` | [780](../../../app/src/App.svelte#L780) |
| `selectableMagnets` | `allSelectableRows` (deduped count) | [783](../../../app/src/App.svelte#L783) |
| `selectedMagnets` | `allSelectableRows`, `selectedHandles` | [784](../../../app/src/App.svelte#L784) |
| `sendButtonLabel` (`$derived.by`) | `manualVisibleRows`, `selectedMagnets`, `webGroups`, `groups`, `selectedHandles` | [787](../../../app/src/App.svelte#L787) |
| `rdCandidates` (`$derived.by`) | `groups`, `filter`, `sortColumn`, `sortDirection`（全部經 `rdConsideredRows` → `processedRows`） | [803](../../../app/src/App.svelte#L803) |
| `rdPickByGroup` | `rdCandidates` | [816](../../../app/src/App.svelte#L816) |
| `rdPickedHandles` | `rdCandidates` | [821](../../../app/src/App.svelte#L821) |
| `rowClassByHandle` (`$derived.by`) | `groups[].result.magnets`（不看 `filter`） | [834](../../../app/src/App.svelte#L834) |
| `rdSendTriage` (`$derived.by`) | `groups`, `selectedHandles`（經 `buildSelectedSendItems`）, `rowClassByHandle` — 送出前確認面板與 `confirmSend` 的唯一資料來源 | [849](../../../app/src/App.svelte#L849) |
| `settingsErrors` | `settingsDraft` | [1505](../../../app/src/App.svelte#L1505) |
| `settingsValid` | `settingsErrors` | [1508](../../../app/src/App.svelte#L1508) |
| `rdCompletedCount` | `rdSendProgress[].status` | [1649](../../../app/src/App.svelte#L1649) |
| `rdPendingCount` | `rdSendProgress[].status` | [1652](../../../app/src/App.svelte#L1652) |
| `rdErrorCount` | `rdSendProgress[].status` | [1655](../../../app/src/App.svelte#L1655) |
| `rdDownloadLinkCount` | `rdSendProgress[].status`, `rdSendProgress[].links` | [1658](../../../app/src/App.svelte#L1658) |
| `rdDisplayRows` | `rdSendProgress` via `buildRdDisplayRows` (display-only order; `rdSendProgress` itself is never reordered) | [1667](../../../app/src/App.svelte#L1667) |

### 1.5 Lifecycle

- `onMount` ([App.svelte:230–270](../../../app/src/App.svelte#L230)) — boot-time IPC to populate paths, settings, RD token presence, pending list, legacy default dir, cookies status. Best-effort: every step is wrapped in its own `try/catch` (or a helper that swallows) so a partial failure still allows the rest of the UI to render.
- `onDestroy(() => flash.dispose())` clears all pending flash timers on unmount. No `$effect`. Cancellation tokens (`scrapeAbort`, `rdSendAbort`, `retryAbort`) are not torn down on unmount — fine for a top-level component but worth noting.

---

## 2. State catalog

### 2.1 Paths / theme / boot / tabs

| Var | Type | Initial | Mutated by | Read by |
|---|---|---|---|---|
| `dataDir` | `string` | `"（載入中）"` | `onMount` | markup [1809](../../../app/src/App.svelte#L1809) |
| `logDir` | `string` | `"（載入中）"` | `onMount` | markup [1811](../../../app/src/App.svelte#L1811) |
| `theme` | `Theme` | `"light"` | `loadAndApplySettings`, `toggleTheme` | `toggleTheme`, markup [1818](../../../app/src/App.svelte#L1818) |
| `settings` | `Settings \| null` | `null` | `loadAndApplySettings`, `toggleTheme` (mutates `.ui.theme`) | `toggleTheme`, `runSendBatch` (for defaults), `openSettingsEditor`, `revertSettingsDraft` |
| `statusMessage` | `string` | `""` | `onMount` (catch), `toggleTheme`, `startScrape` (guard), `copyOne`, `copySelected`, `selectRdCandidatesOnly`, `clearResults` | markup [1717](../../../app/src/App.svelte#L1717) |
| `activeTab` | `"search" \| "select" \| "rd" \| "settings"` | `"search"` | `onTabKeydown`, tab buttons [1679–1709](../../../app/src/App.svelte#L1679), `sendSelectedToRd` / `confirmSend` (bounces), in-section 前往 buttons | every `<section hidden={activeTab !== …}>` |
| `isThemeSaving` | `boolean` | `false` | `toggleTheme` (set/finally) | `settingsWriteBusy` |

### 2.2 JavDB scrape / magnet batch

| Var | Type | Initial | Mutated by | Read by |
|---|---|---|---|---|
| `urlBatch` | `string` | `"https://javdb.com/v/RkX3Rp\n"` | `bind:value` textarea [2303](../../../app/src/App.svelte#L2303) | `startScrape` |
| `magnetBatch` | `string` | `""` | `bind:value` textarea [2386](../../../app/src/App.svelte#L2386), cleared in `registerPastedMagnets` | `registerPastedMagnets` |
| `isRegistering` | `boolean` | `false` | `registerPastedMagnets` | button disabled [2395](../../../app/src/App.svelte#L2395) |
| `registerStatus` | `{kind, text} \| null` | `null` | `registerPastedMagnets` | markup [2408](../../../app/src/App.svelte#L2408) |
| `groups` | `ScrapedGroup[]` | `[]` | `startScrape` (placeholders + kept manual groups; `scrapeBatch` callback replaces the array via `applyScrapeProgressForRun`), `registerPastedMagnets`, `clearResults` | many: `groupProcessedRowsMap`, `buildSelectedSendItems`, `webGroups` and the other count/row derived values, `rdCandidates`, `rowClassByHandle`, markup [2510](../../../app/src/App.svelte#L2510) |
| `scrapeProgress` | `{done, total}` | `{0,0}` | `startScrape`, `scrapeBatch` callback, `clearResults` | markup [1683](../../../app/src/App.svelte#L1683), [2331–2332](../../../app/src/App.svelte#L2331) |
| `isScraping` | `boolean` | `false` | `startScrape` (set/finally, current run only), `cancelScrape`, `clearResults` | button disabled [2310–2317](../../../app/src/App.svelte#L2310), status bar [2330](../../../app/src/App.svelte#L2330) |
| `scrapeAbort` (plain `let`) | `AbortController \| null` | `null` | `startScrape`, `cancelScrape`, `clearResults` | `cancelScrape`, `clearResults` |
| `scrapeRunId` (plain `let`) | `number` | `0` | `startScrape` (`++`), `cancelScrape`, `clearResults` (`+= 1`) | `startScrape` callback / finally — late events from a superseded run are dropped |

### 2.3 Filter / sort / collapse / selection

| Var | Type | Initial | Mutated by | Read by |
|---|---|---|---|---|
| `filter` | `FilterState` | `defaultFilterState()` | `bind:value` inputs, `commitMinSize`, `commitMaxSize`, `setGroupPick`, `resetFilter` | `groupProcessedRowsMap` / `processedRows`, `allVisibleRows`（經 `webVisibleRows`/`manualVisibleRows`）, `rdConsideredRows`（經 `rdCandidates`：★ 首選必須與畫面同一組列） |
| `minSizeInput` | `string` | `""` | input bind [2479](../../../app/src/App.svelte#L2479), `resetFilter` | `commitMinSize` |
| `maxSizeInput` | `string` | `""` | input bind [2489](../../../app/src/App.svelte#L2489), `resetFilter` | `commitMaxSize` |
| `sortColumn` | `SortColumn \| null` | `null` | `toggleSort`, `resetFilter` | `processedRows`, `sortIndicator` |
| `sortDirection` | `SortDirection` | `"asc"` | `toggleSort`, `resetFilter` | `processedRows`, `sortIndicator` |
| `collapsed` | `Record<string, boolean>` | `{}` | `toggleCollapsed`, `clearResults` | markup [2512](../../../app/src/App.svelte#L2512) |
| `selectedHandles` | `Record<string, boolean>` | `{}` | `rememberSelectableRows`, `registerPastedMagnets` (re-checks every pasted handle), `setRowSelected`, `setRowsSelected`, `selectOnlyRows`, `selectRdCandidatesOnly`, `clearResults` | `buildSelectedSendItems`, `selectedMagnets` / `sendButtonLabel` derived, `copySelected`, `selectedInRows`, `rowSelected` (per-row checkbox [2610](../../../app/src/App.svelte#L2610)) |

`selectedHandles` is the send batch's source of truth — filters and sort only decide what is
drawn, never what gets sent. `filter` and `selectedHandles` are therefore independent: a row can
be checked and invisible at the same time. (Row added 2026-08-01; the var predates it.)

`filter.hd_only` (只顯示高清 checkbox [2470](../../../app/src/App.svelte#L2470)) **widened on
2026-08-01** without any change in this file: `magnetUtils.isHd` now means "高清/hd tag **or** a
1080p/2160p/4K/UHD token in the filename", so the checkbox keeps untagged HD releases it used to
hide. Same definition the ⚡/高清 badges use — see `frontend-lib.md` §3.3 `isHd` / §3.4 `isHdRow`.
Manual (pasted) groups are never filtered or group-picked at all — `processGroupRows` only sorts
them.

### 2.4 Ping / sidecar

| Var | Type | Initial | Mutated by | Read by |
|---|---|---|---|---|
| `pingMessage` | `string` | `""` | `pingSidecar` | markup [1831](../../../app/src/App.svelte#L1831) |

### 2.5 Real-Debrid token + user

| Var | Type | Initial | Mutated by | Read by |
|---|---|---|---|---|
| `rdHasToken` | `boolean` | `false` | `onMount`, `rdSaveToken`, `rdClearToken`, `applyLegacyImportConfirmed` | `sendSelectedToRd`, `confirmSend`, `rdRefreshUser`, markup (many gates) |
| `rdUser` | `RdUserInfo \| null` | `null` | `rdTestToken`, `rdSaveToken`, `rdClearToken`, `rdRefreshUser` | markup [1744](../../../app/src/App.svelte#L1744) |
| `rdTokenInput` | `string` | `""` | input bind [1775](../../../app/src/App.svelte#L1775), cleared in `rdSaveToken`/`rdClearToken` | `rdTestToken`, `rdSaveToken` |
| `rdShowToken` | `boolean` | `false` | checkbox bind [1781](../../../app/src/App.svelte#L1781), `rdSaveToken` (resets) | input `type` attr [1774](../../../app/src/App.svelte#L1774) |
| `rdMessage` | `string` | `""` | RD token handlers, `sendSelectedToRd`, `confirmSend`, `cancelSendPlan`, `runSendBatch`, `copyRdDownloads`, `copyRdRow`, `copyRdSingleLink` | markup [1800](../../../app/src/App.svelte#L1800) (settings tab) and [1900](../../../app/src/App.svelte#L1900) (RD tab) — the tabs are exclusive, so only one renders |

### 2.6 Real-Debrid send-batch progress

| Var | Type | Initial | Mutated by | Read by |
|---|---|---|---|---|
| `rdSendProgress` | `RdSendProgress[]` | `[]` | `runSendBatch`, `sendBatch` callback (slot replace), `retryAllPending` (via `applyRetryEventToProgressRows`) | derived counts, `rdDisplayRows`, `copyRdDownloads`, markup gate [2671](../../../app/src/App.svelte#L2671) |
| `rdSendDone` | `{done,total}` | `{0,0}` | `runSendBatch`, `sendBatch` callback | markup [1703](../../../app/src/App.svelte#L1703), [2675](../../../app/src/App.svelte#L2675) |
| `isRdSending` | `boolean` | `false` | `runSendBatch` (set/finally) | disabled gates, guards in `sendSelectedToRd` / `confirmSend` / `clearResults` / `refreshPending` / `retryAllPending` / `removePending` / `clearAllPending` |
| `isCancelingSend` | `boolean` | `false` | `cancelRdSend` (set), `runSendBatch` finally (clear) | 取消 button [2683](../../../app/src/App.svelte#L2683) |
| `rdSendAbort` (plain `let`) | `AbortController \| null` | `null` | `runSendBatch` | `cancelRdSend` |
| `lastBatchStartAt` | `string` (ISO) | `new Date().toISOString()` | `runSendBatch`, `retryAllPending` | `copyRdDownloads` (completion ordering) |
| `sendPlanOpen` | `boolean` | `false` | `sendSelectedToRd` (set when `low > 0`), `runSendBatch` (clears), `confirmSend` (clears on a failed guard), `cancelSendPlan`, `clearResults`, `startScrape` | 確認面板 `{#if}` [1870](../../../app/src/App.svelte#L1870), `confirmSend`, 送出鍵 disabled [1854](../../../app/src/App.svelte#L1854) |

`sendPlanOpen` is deliberately a bare flag, **not** a frozen snapshot of the batch. The
checkboxes stay live behind the panel (回到挑選 is not disabled), so a snapshot would let the
user confirm a batch that no longer matches what is checked — breaking the app's oldest rule,
that the send follows the checkboxes. Everything the panel displays and sends comes from
`rdSendTriage`, which is derived from the current selection. `clearResults` and `startScrape`
both close it: the former empties the selection, the latter replaces the web groups and hands
their stale handles to `forget_magnets`, so an open panel would be describing a batch that no
longer exists.

### 2.7 Pending list (RD waiting)

| Var | Type | Initial | Mutated by | Read by |
|---|---|---|---|---|
| `pendingEntries` | `PendingEntry[]` | `[]` | `reloadPendingSilently` (`onMount`, `runSendBatch` finally, `retryAllPending` finally, `applyLegacyImportConfirmed`), `refreshPending`, `removePending`, `clearAllPending` | `retryAllPending` (input), tab badge [1703](../../../app/src/App.svelte#L1703), markup gate [2804](../../../app/src/App.svelte#L2804) |
| `isRetryingPending` | `boolean` | `false` | `retryAllPending` (set/finally) | disabled gates and reentry guards (same set as `isRdSending`) |
| `retryAbort` (plain `let`) | `AbortController \| null` | `null` | `retryAllPending` | `cancelRetry` |
| `pendingMessage` | `{kind, text} \| null` | `null` | `refreshPending`, `retryAllPending`, `removePending`, `clearAllPending` | markup [2813](../../../app/src/App.svelte#L2813) |

### 2.8 Legacy import (M7a-lite)

| Var | Type | Initial | Mutated by | Read by |
|---|---|---|---|---|
| `legacyPath` | `string` | `""` | `onMount` (env default), input bind [1924](../../../app/src/App.svelte#L1924) | `previewLegacyImport`, `applyLegacyImportConfirmed` |
| `legacyPreview` | `LegacyImportPreview \| null` | `null` | `previewLegacyImport` (set/clear) | markup [1951](../../../app/src/App.svelte#L1951), apply button enable [1942](../../../app/src/App.svelte#L1942) |
| `legacyReport` | `LegacyImportReport \| null` | `null` | `previewLegacyImport` (clear), `applyLegacyImportConfirmed` | markup [1988](../../../app/src/App.svelte#L1988) |
| `legacyBusy` | `boolean` | `false` | both legacy functions (set/finally) | `settingsWriteBusy`, preview button label [1934](../../../app/src/App.svelte#L1934) |
| `legacyError` | `string` | `""` | both legacy functions | markup [1948](../../../app/src/App.svelte#L1948) |
| `legacyShown` | `boolean` | `false` | `onMount` (if env default), toggle button [1910](../../../app/src/App.svelte#L1910) | `{#if}` gate [1914](../../../app/src/App.svelte#L1914) |

### 2.9 Cookies status (M7b / M9)

| Var | Type | Initial | Mutated by | Read by |
|---|---|---|---|---|
| `cookiesStatus` | `CookiesStatus \| null` | `null` | `refreshCookiesStatus` (set/clear), `clearCookies`, `saveCookies` | markup [2157](../../../app/src/App.svelte#L2157), `createCookiesTemplate`, button gates [2240](../../../app/src/App.svelte#L2240), [2246](../../../app/src/App.svelte#L2246) |
| `cookiesShown` | `boolean` | `false` | `toggleCookiesShown` | `{#if}` gate [2152](../../../app/src/App.svelte#L2152) |
| `cookiesError` | `string` | `""` | `refreshCookiesStatus`, `toggleCookiesPaste`, `armCookiesClear`, `clearCookies`, `saveCookies`, `openDataDir`, `openLogsDir`, `createCookiesTemplate` | markup [2196](../../../app/src/App.svelte#L2196) |
| `cookiesMessage` | `{kind, text} \| null` | `null` | `toggleCookiesPaste`, `armCookiesClear`, `clearCookies`, `saveCookies`, `createCookiesTemplate` | markup [2199](../../../app/src/App.svelte#L2199) |
| `cookiesPasteOpen` | `boolean` | `false` | `toggleCookiesPaste`, `clearCookies`, `saveCookies` | `{#if}` gate [2255](../../../app/src/App.svelte#L2255), toggle label [2225](../../../app/src/App.svelte#L2225) |
| `cookiesPasteInput` | `string` | `""` | textarea bind [2269](../../../app/src/App.svelte#L2269), cleared by `toggleCookiesPaste` (on close) / `clearCookies` / `saveCookies` | `saveCookies` |
| `cookiesSaving` | `boolean` | `false` | `saveCookies` (set/finally) | disabled gates |
| `cookiesClearArmed` | `boolean` | `false` | `armCookiesClear` (set), `cancelCookiesClear` / `toggleCookiesShown` (on collapse) / `toggleCookiesPaste` / `clearCookies` (clear) | confirmation block [2202](../../../app/src/App.svelte#L2202), button swap [2227](../../../app/src/App.svelte#L2227) |
| `cookiesClearing` | `boolean` | `false` | `clearCookies` (set/finally) | 確定清除 / 取消清除 disabled |

清除 cookies is a two-click action (`cookiesClearArmed`): unlike 清除 Token, which is
re-pasteable from Real-Debrid's site, the cookie header can only be recovered by walking
DevTools again, so a stray click must not be enough.

### 2.10 Settings editor (M7c)

| Var | Type | Initial | Mutated by | Read by |
|---|---|---|---|---|
| `settingsShown` | `boolean` | `false` | toggle button [2033](../../../app/src/App.svelte#L2033), `openSettingsEditor`; `saveSettings` doesn't auto-close | `{#if}` gate [2040](../../../app/src/App.svelte#L2040) |
| `settingsDraft` | `Settings \| null` | `null` | `openSettingsEditor`, `saveSettings`, `revertSettingsDraft`, `applyLegacyImportConfirmed` (rebuilt after `env_imported` when the editor is open), `toggleTheme` (`.ui.theme` on success / rollback) + `bind:value` in form | `settingsErrors`, `saveSettings`, form binds |
| `settingsSaving` | `boolean` | `false` | `saveSettings` (set/finally) | `settingsWriteBusy`, save label [2129](../../../app/src/App.svelte#L2129) |
| `settingsMessage` | `string` | `""` | `openSettingsEditor`, `saveSettings`, `revertSettingsDraft` | markup [2137](../../../app/src/App.svelte#L2137) |
| `settingsMessageKind` | `"ok"\|"error"\|"info"` | `"info"` | mirrored with `settingsMessage` | `data-kind` attr [2138](../../../app/src/App.svelte#L2138) |

---

## 3. Functions / handlers (source order)

### 3.0 Tab navigation

#### `onTabKeydown(e: KeyboardEvent, index: number): void`  *(App.svelte:[80](../../../app/src/App.svelte#L80))*

**Purpose**: Tablist-style keyboard navigation between the four tab buttons.

**Contract**: ArrowRight / ArrowLeft wrap through `TAB_ORDER`; Home / End jump to first / last; any other key returns untouched. On a handled key: `preventDefault()`, writes `activeTab`, focuses the matching sibling `<button>`. The handler sits on the buttons, not on `<nav>`, because a keydown on a non-interactive landmark trips Svelte's a11y lint.

**Triggered by**: `onkeydown` on each tab button [1680, 1690, 1700, 1710](../../../app/src/App.svelte#L1680).

---

### 3.1 UI helpers — theme, scale, shared loaders

#### `applyTheme(t: Theme): void`  *(App.svelte:[193](../../../app/src/App.svelte#L193))*

**Purpose**: Set `document.documentElement.dataset.theme` so CSS variables switch.

**Contract**:
- Pure DOM side effect on `<html>`.
- No state read/write inside the component graph.

**Calls**: DOM `dataset` property set.

**Triggered by**: `loadAndApplySettings`, `toggleTheme` (apply + rollback).

---

#### `applyScale(raw: string): void`  *(App.svelte:[203](../../../app/src/App.svelte#L203))*

**Purpose**: Translate `settings.ui.scale` ("auto" | "0.5".."3.0") into a `--ui-scale` CSS var + root `font-size`.

**Contract**:
- `"auto"` (case-insensitive) or empty → scale = 1. Numeric strings in `[0.5, 3.0]` are used as-is; anything else (including out-of-range numbers) → 1.
- Side effect: sets CSS variable and inline root font-size (`scale * 16px`).
- No invoke calls.

**Calls**: `parseFloat`, DOM `style.setProperty`.

**Triggered by**: `loadAndApplySettings`.

---

#### `loadAndApplySettings(): Promise<Settings>`  *(App.svelte:[213](../../../app/src/App.svelte#L213))*

**Purpose**: Single "read settings from disk and apply" path shared by boot, save and legacy import.

**Contract**: Writes `settings`, `theme`; calls `applyTheme(theme)` and `applyScale(s.ui.scale)`; returns the fresh `Settings`. Errors propagate — each caller decides how to surface them.

**Calls**: `invoke('read_settings')` → `Settings`.

**Called by**: `onMount`, `saveSettings`, `applyLegacyImportConfirmed` (when `env_imported`).

---

#### `reloadPendingSilently(context = "pending_list"): Promise<void>`  *(App.svelte:[222](../../../app/src/App.svelte#L222))*

**Purpose**: Refresh `pendingEntries` from disk without touching `pendingMessage`.

**Contract**: Errors are swallowed as `console.warn(\`${context} failed:\`, e)`. Deliberately distinct from `refreshPending`, whose "已重新載入" message would overwrite a retry summary.

**Calls**: `invoke('pending_list')` → `PendingEntry[]`.

**Called by**: `onMount`, `runSendBatch` (finally), `retryAllPending` (finally, context `"pending_list after retry"`), `applyLegacyImportConfirmed` (context `"pending_list after import"`).

---

### 3.2 Initialization / boot

#### `onMount(async () => {...})`  *(App.svelte:[230](../../../app/src/App.svelte#L230))*

**Purpose**: Best-effort boot — populate paths, settings (+ apply theme/scale), RD token presence, pending list, legacy default dir, cookies status.

**Contract**:
- Async. Each IPC wrapped in its own `try/catch` (or a swallowing helper) so partial failures don't abort the rest.
- Writes: `dataDir`, `logDir`, `settings`, `theme`, `rdHasToken`, `pendingEntries`, `legacyPath`, `legacyShown`, `cookiesStatus`, plus `statusMessage` on settings failure.
- Errors: `console.error` + `statusMessage = "讀取設定失敗：…"` for settings; `console.warn` for token / pending / legacy-dir; inline `錯誤：…` text in `dataDir`/`logDir` for path failure.
- `get_legacy_default_dir` only pre-fills `legacyPath` and expands the section (`legacyShown = true`) when non-blank; it never triggers an import.

**Calls**:
- `invoke('get_paths')` → `PathInfo`
- `loadAndApplySettings()` → `invoke('read_settings')`
- `invoke('rd_has_token')` → `{present}`
- `reloadPendingSilently()` → `invoke('pending_list')`
- `invoke('get_legacy_default_dir')` → `string`
- `refreshCookiesStatus()`

**Triggered by**: Svelte mount.

---

### 3.3 Theme / sidecar quick handlers

#### `toggleTheme(): Promise<void>`  *(App.svelte:[272](../../../app/src/App.svelte#L272))*

**Purpose**: Flip light/dark, persist via `write_settings`.

**Contract**:
- Guards: returns immediately while `settingsWriteBusy` (theme save, settings save or legacy import in flight — `write_settings` is a whole-file overwrite, so interleaved writers would silently revert each other's fields); `settings === null` → `statusMessage = "設定尚未載入"` and return.
- Optimistic: sets `isThemeSaving`, `theme`, `applyTheme(newTheme)`, `settings.ui.theme` before the invoke. `settingsDraft.ui.theme` is updated only **after** `write_settings` succeeds; `statusMessage = "主題已儲存：…"`.
- Rollback on failure: restores `theme` and re-applies it, restores `settings.ui.theme` only if `settings` is still the same object, restores `settingsDraft.ui.theme` if a draft existed; `statusMessage = "儲存設定失敗：…"`.
- `isThemeSaving` released in `finally`.

**Calls**: `applyTheme`, `invoke('write_settings', { settings })`.

**Triggered by**: Markup button [1817](../../../app/src/App.svelte#L1817) (`disabled={settingsWriteBusy}`).

---

#### `pingSidecar(): Promise<void>`  *(App.svelte:[311](../../../app/src/App.svelte#L311))*

**Purpose**: Health-check sidecar; show uptime + request_id.

**Contract**: Writes `pingMessage` (`（ping 中…）`, then the result or `錯誤：…`). Flashes `ping-sidecar` on success.

**Calls**: `invoke('sidecar_ping')` → `PingResponse`.

**Triggered by**: Markup button [1826](../../../app/src/App.svelte#L1826).

---

### 3.4 JavDB scrape flow

#### `startScrape(): Promise<void>`  *(App.svelte:[322](../../../app/src/App.svelte#L322))*

**Purpose**: Parse URL textarea, release stale web handles, render placeholder slots, invoke batch scraper with abort signal.

**Contract**:
- Guard: returns early if `isScraping`.
- If `parseUrlBatch` returns empty → `statusMessage = "批次中沒有有效網址"`, returns.
- Collects the handle ids of current **web** groups that are not also shown by a surviving manual group (`survivingManualIds`, per handle, not per group — the sidecar keys handles by BTIH and `forget_magnets` has no refcount) and releases them via `forget_magnets` (best-effort, `console.warn` on failure).
- `groups` becomes `[...url placeholders (status "pending"), ...existing manual groups]` — URL slots must occupy the head because results are written by index.
- Clears `sendPlanOpen`.
- Mutates: `scrapeProgress`, `isScraping`, `scrapeAbort`, `scrapeRunId` (`++`, captured as `runId`).
- Per-URL settle: callback runs `applyScrapeProgressForRun({groups, scrapeProgress}, ev, scrapeRunId, runId)`; events from a superseded run return the same snapshot and are ignored. On a change it writes `groups` / `scrapeProgress` and calls `rememberSelectableRows` for every group with a result (new rows default to checked).
- `finally`: clears `isScraping` / `scrapeAbort` only if `scrapeRunId === runId`.

**Calls**:
- `parseUrlBatch(urlBatch)` → `string[]` ([lib/scraper.ts:145](../../../app/src/lib/scraper.ts#L145))
- `invoke('forget_magnets', { handleIds: staleIds })` (when any)
- `scrapeBatch(urls, callback, { signal })` ([lib/scraper.ts:231](../../../app/src/lib/scraper.ts#L231)) — that lib internally invokes `fetch_javdb` per URL.
- `applyScrapeProgressForRun` ([lib/scraper.ts:86](../../../app/src/lib/scraper.ts#L86)), `rememberSelectableRows`.

**Triggered by**: Markup button [2310](../../../app/src/App.svelte#L2310).

---

#### `cancelScrape(): void`  *(App.svelte:[419](../../../app/src/App.svelte#L419))*

**Purpose**: Abort in-flight scrape.

**Contract**: `scrapeAbort?.abort()`, bumps `scrapeRunId` (so late events are dropped), sets `isScraping = false`, `scrapeAbort = null` immediately.

**Triggered by**: Markup button [2313](../../../app/src/App.svelte#L2313).

---

### 3.5 Paste-magnet flow

#### `registerPastedMagnets(): Promise<void>`  *(App.svelte:[431](../../../app/src/App.svelte#L431))*

**Purpose**: Parse pasted magnet text, register via sidecar, append result rows to `groups` as a synthetic `manual://<ts>` group so downstream filter/sort/send-to-RD plumbing applies unchanged.

**Contract**:
- Guard: returns early if `isRegistering`.
- If no valid magnets, detects the JavDB-URL-misuse pattern (`/^\s*https?:\/\//im`) and produces a tailored `registerStatus` error.
- Every registered handle is (re-)checked: `selectedHandles[r.handle_id] = true` — pasting is an explicit re-selection even if the BTIH was previously unchecked.
- Rows are skipped only when the handle already lives in a **manual** group (or repeats within the batch) — counted as `skippedExisting`. A handle that also lives in a web group is NOT skipped: the pasted magnet must stay visible even when filters hide its web twin; `dedupeByHandleId` on the send/copy paths still guarantees one RD invoke per handle.
- Mutates: `isRegistering`, `registerStatus` (fragments: added / skipped / invalid, kind `ok` when rows were added else `info`; `error` on invoke failure), `selectedHandles`, `groups` (append synthetic group when `newRows.length > 0`), `magnetBatch` (cleared after a successful invoke).
- Synthetic group: `engine: "manual"`, code `"(直接貼上 N)"`; per-row `name` comes from sidecar's `dn=` extract (so each row can carry its own JAV code); `size`/`tags`/`date` empty.
- Flashes `magnet-register` when rows were added.

**Calls**:
- `parseMagnetBatch(magnetBatch)` ([lib/scraper.ts:155](../../../app/src/lib/scraper.ts#L155))
- `invoke('register_magnets', { magnets })` → `{ registered[], invalid[] }`
- `rememberSelectableRows(newRows)`, `isManualGroup`.

**Triggered by**: Markup button [2394](../../../app/src/App.svelte#L2394).

---

### 3.6 Clipboard / single-row actions

#### `copyOne(handle_id: string, label: string): Promise<void>`  *(App.svelte:[538](../../../app/src/App.svelte#L538))*

**Purpose**: Copy one magnet via sidecar (handle-id indirection — UI never sees raw magnet).

**Contract**: Writes `statusMessage` (ok or error); flashes `magnet-copy-<handle_id>` on success.

**Calls**: `invoke('copy_magnet', { handleId })`.

**Triggered by**: Per-row `複製` button [2647](../../../app/src/App.svelte#L2647), per-row `ondblclick` [2604](../../../app/src/App.svelte#L2604).

---

#### `copySelected(): Promise<void>`  *(App.svelte:[548](../../../app/src/App.svelte#L548))*

**Purpose**: Bulk-copy every **checked** handle across all groups (web and manual), deduped. (Named `copyVisible` and driven by the visible rows in earlier revisions of this document.)

**Contract**: Reads `dedupeByHandleId(allSelectableRows)` filtered by `selectedHandles`. Early return if nothing is checked. Writes `statusMessage`, reporting `result.copied` and `result.unknown` (stale handles) separately; flashes `magnet-copy-selected`.

**Calls**: `invoke('copy_magnets_bulk', { handleIds })` → `CopyBulkResult`.

**Triggered by**: Markup button 複製已勾選 [2443](../../../app/src/App.svelte#L2443).

---

### 3.7 Filter / sort / selection / collapse helpers

#### `processedRows(g: ScrapedGroup): MagnetRow[]`  *(App.svelte:[577](../../../app/src/App.svelte#L577))*

**Purpose**: Lookup into the memoised `groupProcessedRowsMap` ([569](../../../app/src/App.svelte#L569)); falls back to calling `processGroupRows` ([lib/magnetUtils.ts:207](../../../app/src/lib/magnetUtils.ts#L207)) directly with the current filter/sort state.

**Reads**: `groupProcessedRowsMap`, `filter`, `sortColumn`, `sortDirection`. **Pure** w.r.t. component state.

**Called by**: `webVisibleRows` / `manualVisibleRows` derived [768, 769](../../../app/src/App.svelte#L768)（`allVisibleRows` 由兩者組成，供三個全選/反選按鈕共用）, `rdConsideredRows`, markup `{@const rows = processedRows(g)}` [2511](../../../app/src/App.svelte#L2511). Does not feed the RD send batch (that follows `selectedHandles`) nor the bulk copy (`copySelected` reads `allSelectableRows`).

---

#### `rdConsideredRows(g: ScrapedGroup): MagnetRow[]`  *(App.svelte:[593](../../../app/src/App.svelte#L593))*

**Purpose**: The rows one group's RD candidate (★ 首選) is picked from.

**Contract**:
- Returns `processedRows(g)` — literally the rendered set (filter → group_pick → sort).
- Delegating rather than reproducing the filter half is what makes "the ★ is always on a row
  that is on screen" true by construction. Re-running only `filterRows` diverges the moment
  `group_pick` is `largest` / `smallest` / `fewest_files`, which collapse the group to one row:
  the ★ then vanishes and 只勾選 RD 優先候選 checks a magnet the user can neither see nor
  uncheck in that view.
- Feeding the result back in under `group_pick="rd_ready"` is a fixed point, not a loop:
  `pickRdCandidate` over the single surviving row returns that row with the same tier.

**Reads**: `filter`. **Pure** w.r.t. component state.

**Called by**: `rdCandidates` derived [803](../../../app/src/App.svelte#L803).

---

#### `toggleSort(col: SortColumn): void`  *(App.svelte:[597](../../../app/src/App.svelte#L597))*

**Purpose**: If same column → flip direction; else set new column + `asc`. **Writes** `sortColumn`, `sortDirection`.

**Triggered by**: Table header buttons [2570, 2575, 2580, 2585](../../../app/src/App.svelte#L2570).

---

#### `sortIndicator(col: SortColumn): string`  *(App.svelte:[606](../../../app/src/App.svelte#L606))*

**Purpose**: Returns `" ▲"`, `" ▼"`, or `""` based on whether `col` matches `sortColumn`. Used in header labels.

**Triggered by**: Markup interpolation in table headers.

---

#### Checkbox helpers  *(App.svelte:[611–632](../../../app/src/App.svelte#L611), [677–683](../../../app/src/App.svelte#L677))*

- `rememberSelectableRows(rows)` [611] — sets `selectedHandles[id] = true` only for handles not yet present in the map (new rows default to checked; an explicit uncheck survives a re-scrape). Called by `startScrape` (progress callback) and `registerPastedMagnets`.
- `setRowSelected(handleId, selected)` [619] — per-row checkbox `onchange` [2613](../../../app/src/App.svelte#L2613), `selectRdCandidatesOnly`.
- `setRowsSelected(rows, selected)` [623] — 勾選目前顯示 / 取消目前顯示 [2430, 2439](../../../app/src/App.svelte#L2430), per-group 勾選本組顯示 / 取消本組顯示 [2542, 2545](../../../app/src/App.svelte#L2542), `selectOnlyRows`, `selectRdCandidatesOnly`.
- `selectOnlyRows(rows)` [629] — unchecks every row in `allSelectableRows` (web **and** manual), then checks `rows`. 只勾選目前顯示 [2433](../../../app/src/App.svelte#L2433).
- `selectedInRows(rows): number` [677] — deduped checked count; group header 已勾 N [2539](../../../app/src/App.svelte#L2539).
- `rowSelected(handleId): boolean` [681] — `selectedHandles[handleId] === true`; per-row checkbox `checked` [2610](../../../app/src/App.svelte#L2610).

---

#### `selectRdCandidatesOnly(): void`  *(App.svelte:[645](../../../app/src/App.svelte#L645))*

**Purpose**: Collapse the checkboxes down to one row per group — the one most likely to be
cached on RD already. The button sits next to 只勾選目前顯示.

**Contract**:
- **Scoped to WEB groups on both halves.** The unchecking pass runs over web rows only (not
  `allSelectableRows`, which is what `selectOnlyRows` clears), and additionally skips any web
  row whose handle is also shown by a manual group (`manualHandleIds`) — selection is keyed by
  handle id, so unchecking a web twin would reach through the shared key and drop the pasted
  instruction. A pasted magnet is an explicit user instruction, so this must never silently drop
  one — same invariant `registerPastedMagnets` documents. Manual rows keep whatever checked state
  they had.
- Then checks every handle in `rdPickedHandles`, i.e. web-group candidates whose tier is NOT
  `no_hd_fallback`. A group whose best row is only a fallback is **skipped entirely** —
  auto-checking a row that is neither HD nor from a re-upload site would be a guess the user did
  not ask for.
- Writes `statusMessage` with three fragments: how many were checked, how many groups were
  skipped for having no HD candidate, and (when any exist) that N 手貼 rows were left untouched.
- Not gated on `isRdSending` — it only moves checkboxes, and an in-flight batch already has its
  own frozen item list.

**Reads**: `rdPickedHandles`, `rdCandidates`, `webGroups`, `groups`. **Writes**:
`selectedHandles` (via `setRowsSelected` / `setRowSelected`), `statusMessage`.

**Triggered by**: Markup button 只勾選 RD 優先候選 [2436](../../../app/src/App.svelte#L2436).

---

#### `commitMinSize(): void`  *(App.svelte:[685](../../../app/src/App.svelte#L685))*

**Purpose**: Commit `minSizeInput` (string) into `filter.min_size_gb` (number | null). `parseFloat` + finite-and-positive check; otherwise `null`.

**Triggered by**: `onchange` on min-size input [2480](../../../app/src/App.svelte#L2480).

---

#### `commitMaxSize(): void`  *(App.svelte:[690](../../../app/src/App.svelte#L690))*

**Purpose**: Symmetric to `commitMinSize` for `maxSizeInput`/`filter.max_size_gb`.

**Triggered by**: `onchange` on max-size input [2490](../../../app/src/App.svelte#L2490).

---

#### `setGroupPick(p: GroupPick): void`  *(App.svelte:[695](../../../app/src/App.svelte#L695))*

**Purpose**: Writes `filter.group_pick`. Trivial setter (could be inlined; called from the `<select>` `onchange` arrow [2497](../../../app/src/App.svelte#L2497)).

The 每組只留 select carries five options — 全部 (`all`), **RD 命中優先 (`rd_ready`)**, 最大檔
(`largest`), 最小檔 (`smallest`), 檔案最少 (`fewest_files`) [2499–2503](../../../app/src/App.svelte#L2499).
`rd_ready` sits right after 全部 and is resolved by `magnetUtils.applyGroupPick` →
`pickRdReadyRow`; the default stays `all`.

---

#### `resetFilter(): void`  *(App.svelte:[699](../../../app/src/App.svelte#L699))*

**Purpose**: Reset filter+sort+input-strings to defaults.

**Writes**: `filter`, `minSizeInput`, `maxSizeInput`, `sortColumn`, `sortDirection`.

**Triggered by**: Markup button 重置 [2506](../../../app/src/App.svelte#L2506).

---

#### `toggleCollapsed(url: string): void`  *(App.svelte:[707](../../../app/src/App.svelte#L707))*

**Purpose**: Flip `collapsed[url]` boolean (used as group card collapse state).

**Triggered by**: Per-group toggle button [2521](../../../app/src/App.svelte#L2521).

---

#### `clearResults(): Promise<void>`  *(App.svelte:[713](../../../app/src/App.svelte#L713))*

**Purpose**: Wipe `groups` (web **and** manual — the only path that removes pasted groups), abort any in-flight scrape, and tell sidecar to forget the handles.

**Contract**:
- Guard: returns while `isRdSending || isRetryingPending` (the button is disabled on the same condition).
- If `isScraping` → aborts scrape; always bumps `scrapeRunId` and clears `isScraping` / `scrapeAbort`.
- Snapshots all handle_ids before clearing `groups` (so we can pass them to `forget_magnets`).
- Always clears local UI state (`groups = []`, `scrapeProgress`, `collapsed`, `selectedHandles`) — sidecar GC failure is degraded to a `console.warn`, not surfaced as an error.
- Also clears `sendPlanOpen`: nothing is checked any more, so the panel would be reporting on an empty batch.
- `statusMessage`: `已清空 N 筆磁力 handle` on success, else `結果已清空`. Flashes `scrape-clear`.

**Calls**: `scrapeAbort?.abort()`, `invoke('forget_magnets', { handleIds })` → `number`.

**Triggered by**: Markup button 清空全部結果（含手貼） [2322](../../../app/src/App.svelte#L2322).

---

#### `rdPickTitle(tier: RdPickTier): string`  *(App.svelte:[862](../../../app/src/App.svelte#L862))*

**Purpose**: The ★ tooltip — spells out *why* a row won its group, per tier.

**Contract**: Pure mapping, total over `RdPickTier`.
- `prefix_hd` → 本組首選：常見轉載站的高清版本，RD 最可能已有快取
- `hd_earliest` → 本組首選：最早上傳的高清版本，較久的檔案較可能已被快取
- `no_hd_fallback` → 本組首選（⚠ 全組皆非高清）：只能以轉載站前綴與上傳日期推測，命中率低

**Triggered by**: `title` attribute of the ★ badge [2637](../../../app/src/App.svelte#L2637).

---

### 3.8 Real-Debrid token management

All four handlers turn a caught error into a code with `errText(e)` ([lib/errText.ts:5](../../../app/src/lib/errText.ts#L5)) and render it through `rdErrorMessage(code)` ([lib/rdSender.ts:358](../../../app/src/lib/rdSender.ts#L358)).

#### `rdTestToken(): Promise<void>`  *(App.svelte:[873](../../../app/src/App.svelte#L873))*

**Purpose**: One-shot token test that doesn't persist — calls `rd_test_token` with the trimmed typed-in token. Writes `rdUser` on success (null on failure), `rdMessage` either way; flashes `rd-test-token`. A malformed token is refused by Rust before any sidecar call (`rd_token_format_invalid` → `rdErrorMessage`: 「Real-Debrid Token 格式無效（僅限英數且長度 ≤ 255）」); an empty input yields `rd_no_token`.

**Calls**: `invoke('rd_test_token', { token })` → `RdUserInfo`.

**Triggered by**: Markup button [1785](../../../app/src/App.svelte#L1785).

---

#### `rdSaveToken(): Promise<void>`  *(App.svelte:[889](../../../app/src/App.svelte#L889))*

**Purpose**: Persist token to system credential store; immediately re-verify via `rd_check_user` (which reads from store, so the token never crosses IPC again).

**Contract**:
- Guard: empty input → `rdMessage = "請先輸入 Token"` early return.
- Writes: `rdHasToken`, `rdTokenInput` (clears), `rdShowToken` (false), `rdUser`, `rdMessage`. A failed re-verify keeps the saved token and reports `Token 已儲存，但驗證失敗：…`.
- Flashes `rd-save-token`.

**Calls**: `invoke('rd_save_token', { token })`, `invoke('rd_check_user')`.

**Triggered by**: Markup button [1792](../../../app/src/App.svelte#L1792).

---

#### `rdClearToken(): Promise<void>`  *(App.svelte:[914](../../../app/src/App.svelte#L914))*

**Purpose**: Remove token from credential store; clear `rdUser`/`rdTokenInput`/`rdHasToken`; flashes `rd-clear-token`.

**Calls**: `invoke('rd_clear_token')`.

**Triggered by**: Markup button [1737](../../../app/src/App.svelte#L1737) (rendered only when `rdHasToken`).

---

#### `rdRefreshUser(): Promise<void>`  *(App.svelte:[928](../../../app/src/App.svelte#L928))*

**Purpose**: Re-query the stored token for fresh user info (points, expiration).

**Contract**: Guard if no token (`尚未設定 Token`). Writes `rdUser`, `rdMessage`; flashes `rd-refresh-user`.

**Calls**: `invoke('rd_check_user')` → `RdUserInfo`.

**Triggered by**: Markup button [1731](../../../app/src/App.svelte#L1731) (rendered only when `rdHasToken`).

---

### 3.9 Real-Debrid send-batch flow

#### `buildSelectedSendItems(): RdSendItem[]`  *(App.svelte:[973](../../../app/src/App.svelte#L973))*

**Purpose**: Construct the `RdSendItem[]` payload from the explicitly **checked** rows of every group — web and manual alike — deduped by `handle_id`. (Named `buildVisibleSendItems` in earlier revisions of this document; filters and sort only affect what is displayed, they do not mutate a batch the user already checked.)

**Contract**:
- Pure (no state mutation).
- Code-resolution: paste groups (`url.startsWith('manual://')`) prefer the row's own `name` (sidecar's `dn=` extract) — falls back to group code, then `"(unknown)"`. JavDB groups prefer the group code, then `name`, then `"(unknown)"`. `size_label` is the row's `size`.
- Dedupe via `dedupeByHandleId` ([lib/magnetUtils.ts:232](../../../app/src/lib/magnetUtils.ts#L232)) — first occurrence wins, and group order is web-first on purpose (a manual row's metadata is degraded and would be persisted into `pending_torrents.json`).

**Reads**: `groups`, `selectedHandles`.

**Called by**: `rdSendTriage` derived (and through it `sendSelectedToRd` / `confirmSend`).

---

#### `sendSelectedToRd(): Promise<void>`  *(App.svelte:[994](../../../app/src/App.svelte#L994))*

**Purpose**: Entry point of the send flow: read the triaged batch, then either send straight through or raise the pre-send confirmation panel. (Named `sendVisibleToRd` in earlier revisions of this document.)

**Contract**:
- Guards: `isRdSending` / `isRetryingPending` reentry; `rdHasToken` (writes `rdMessage = "請先設定 RD Token"`, bounces to the settings tab because the token editor lives there); empty `rdSendTriage.items` (writes `rdMessage = "目前沒有已勾選的磁力"`, bounces to the select tab).
- **Pre-send triage** (2026-08-01): reads `rdSendTriage`, the live derivation of the checked batch.
  - `rdSendTriage.low === 0` → unchanged behavior, `runSendBatch(rdSendTriage.items)` immediately. A batch with nothing to warn about must not grow a confirmation step.
  - `rdSendTriage.low > 0` → sets `sendPlanOpen = true` and **returns without sending**. The panel takes over.
- Every likelihood number is a local guess — RD has had no cache-probe endpoint since 2024 — and the panel copy says so.

**Calls**:
- `rdSendTriage` (derived; itself calls `buildSelectedSendItems` + `summarizeRdLikelihood`)
- `runSendBatch(items)` — only on the `low === 0` path.

**Triggered by**: Markup button [1849](../../../app/src/App.svelte#L1849). That button is additionally `disabled` while `sendPlanOpen` (and while sending/retrying, with nothing checked, or without a token), so the panel is the only way forward once it is up.

---

#### `confirmSend(scope: "all" | "high"): Promise<void>`  *(App.svelte:[1021](../../../app/src/App.svelte#L1021))*

**Purpose**: Run one of the confirmation panel's two actions.

**Contract**:
- Panel closed → no-op.
- Re-checks **both** `isRdSending || isRetryingPending` and `rdHasToken`. Neither guard is inherited from `sendSelectedToRd`: the panel stays on screen while the user is free to start 全部重試 from the pending section below it, or to walk to the settings tab and clear the token. A failed `rdHasToken` closes the panel, writes `rdMessage` and bounces to 設定 — the same handling as the direct path.
- Reads `rdSendTriage` at click time, never a snapshot taken when the panel opened: `scope === "high"` → `rdSendTriage.highItems` (classes `prefix_hd` / `hd`), `"all"` → `rdSendTriage.items`. Whatever the user checked or unchecked while the panel was up is what gets sent. An empty live batch closes the panel and bounces to the select tab instead of running a zero-item send.

**Calls**: `runSendBatch(items)`.

**Triggered by**: Panel buttons 全部送出 [1881](../../../app/src/App.svelte#L1881) and 只送高機率 [1885](../../../app/src/App.svelte#L1885). The latter is `disabled` when `rdSendTriage.highItems` is empty.

---

#### `cancelSendPlan(): void`  *(App.svelte:[1046](../../../app/src/App.svelte#L1046))*

**Purpose**: Dismiss the confirmation panel without sending. Clears `sendPlanOpen` and writes `rdMessage` = 已取消送出，勾選狀態未變更 — the checkboxes are deliberately left alone so the user can adjust and retry.

**Triggered by**: Panel button 取消送出 [1891](../../../app/src/App.svelte#L1891).

---

#### `runSendBatch(items: RdSendItem[]): Promise<void>`  *(App.svelte:[1057](../../../app/src/App.svelte#L1057))*

**Purpose**: The send itself. Split out of `sendSelectedToRd` so the direct path and both confirmation actions drive the exact same lifecycle over their own subset.

**Contract**:
- Clears `sendPlanOpen` first: the panel is one-shot, and leaving it up would let a second click re-send a batch already in flight.
- Sets `lastBatchStartAt` — included here rather than in the caller because `copyRdDownloads` orders completions relative to THIS batch's start, and a stale value would sort the results wrong.
- Sets `isRdSending`; initialises `rdSendProgress` slots (one per item, status `"pending"`), `rdSendDone`, `rdSendAbort`; clears `rdMessage`.
- Per-item callback replaces `rdSendProgress[index-1]`; when the item's status is not `"sending"`, recomputes `rdSendDone.done` as the number of rows that are neither `"sending"` nor `"pending"` (so in-flight items don't tick the counter).
- `finally`: clears `isRdSending`/`isCancelingSend`/`rdSendAbort`, refreshes `pendingEntries` from disk via `reloadPendingSilently()` (Rust `rd_send_magnet` may have added entries for `in_pending` items).
- Passes `defaults: { strategy: settings.rd.file_pick, min_size_mb: settings.rd.min_size_mb, cache_wait: settings.rd.cache_wait_seconds }` when `settings` is loaded; falls back to `{}` if `settings` is null.

**Calls**:
- `sendBatch(items, callback, { signal, defaults })` ([lib/rdSender.ts:149](../../../app/src/lib/rdSender.ts#L149)) — that lib invokes `rd_send_magnet` per item.
- `reloadPendingSilently()` → `invoke('pending_list')` (in `finally`).

**Called by**: `sendSelectedToRd` (low === 0 path), `confirmSend` (both scopes).

---

#### `cancelRdSend(): void`  *(App.svelte:[1108](../../../app/src/App.svelte#L1108))*

**Purpose**: Abort the in-flight send batch. Sets `isCancelingSend = true` (button shows 取消中… and disables) then `rdSendAbort?.abort()`.

**Triggered by**: Markup button [2683](../../../app/src/App.svelte#L2683) (rendered only while `isRdSending`).

---

#### `copyRdDownloads(): Promise<void>`  *(App.svelte:[1119](../../../app/src/App.svelte#L1119))*

**Purpose**: Collect every download URL from `completed` rows and dump to clipboard via Rust bulk-copy.

**Contract**: Completed rows are ordered by `sortCompletedRowsByCompletionTime(rows, lastBatchStartAt)` ([lib/rdSender.ts:77](../../../app/src/lib/rdSender.ts#L77)); links per row via `collectDownloadLinksFromRow` ([lib/rdSender.ts:63](../../../app/src/lib/rdSender.ts#L63)). Empty lines → `rdMessage` + return. Otherwise reports `result.copied`; flashes `rd-bulk`.

**Calls**: `invoke('copy_rd_links_bulk', { links })` → `CopyRdLinksBulkResult`.

**Triggered by**: Markup button [2689](../../../app/src/App.svelte#L2689).

---

#### `copyRdRow(row: RdSendProgress): Promise<void>`  *(App.svelte:[1145](../../../app/src/App.svelte#L1145))*

**Purpose**: Copy all download URLs of one completed row. Empty → `rdMessage` (`<code> 沒有可複製的下載連結`). Writes `rdMessage`; flashes `rd-row-<handle_id>`.

**Calls**: `collectDownloadLinksFromRow(row)`, `invoke('copy_rd_links_bulk', { links })`.

**Triggered by**: Per-row 複製此筆 N 條 button [2747](../../../app/src/App.svelte#L2747) (only when the row has more than one link).

---

#### `copyRdSingleLink(rowKey: string, link: string, linkIndex: number): Promise<void>`  *(App.svelte:[1164](../../../app/src/App.svelte#L1164))*

**Purpose**: Copy one file's download URL. Blank link → `rdMessage` early return. Reports `已複製 1 條下載連結` or `複製失敗：連結為空` when Rust filtered it out; flashes `rd-link-<rowKey>-<linkIndex>` only when `copied > 0`.

**Calls**: `invoke('copy_rd_links_bulk', { links: [link] })`.

**Triggered by**: Per-link 複製 button [2779](../../../app/src/App.svelte#L2779).

---

### 3.10 Pending retry flow

#### `refreshPending(): Promise<void>`  *(App.svelte:[1189](../../../app/src/App.svelte#L1189))*

**Purpose**: Reload `pending_torrents.json` from disk. Does NOT query RD (per the explicit comment).

**Contract**: Guard: returns while `isRdSending || isRetryingPending`. Writes `pendingEntries`, `pendingMessage` (`info` on ok, `error` on failure); flashes `pending-refresh`. The explicit message exists so the button isn't "silent".

**Calls**: `invoke('pending_list')`.

**Triggered by**: Markup button 重讀本機紀錄 [2828](../../../app/src/App.svelte#L2828).

---

#### `retryAllPending(): Promise<void>`  *(App.svelte:[1203](../../../app/src/App.svelte#L1203))*

**Purpose**: Loop every pending entry through `retryPending`, reconcile any matching row in `rdSendProgress`, then auto-copy newly-completed download links to clipboard and produce a summary line.

**Contract**:
- Guards: `isRdSending || isRetryingPending` reentry, empty list early return.
- Sets `lastBatchStartAt`, `isRetryingPending`, `retryAbort`, `pendingMessage = 重試中 0/N…`.
- Per-event reconciliation:
  - `completed` → bump `completedCount`; collect download URLs; `rdSendProgress = applyRetryEventToProgressRows(rdSendProgress, ev)` ([lib/rdSender.ts:269](../../../app/src/lib/rdSender.ts#L269)) flips the matching row to `completed` with the fresh links (so the 直連 N counter and row labels update without a manual re-send).
  - `pending` → bump `stillPendingCount`.
  - `missing` → bump `missingCount`; the same helper flips the matching row to `error` with `error_code = "rd_torrent_missing"`.
  - else → bump `errorCount`, capture `error_code`.
  - Each event also writes `pendingMessage = 重試中 i/N…`.
- `finally`: clears `isRetryingPending` / `retryAbort`, then `reloadPendingSilently("pending_list after retry")` (Rust deletes completed/missing entries; updates progress on still-pending). Deliberately bypasses `refreshPending()` so the generic "已重新載入" message doesn't overwrite the retry summary.
- After loop: summary is `已取消：完成 i/N` if aborted, else `重試完成：…` fragments; appends the `copy_rd_links_bulk` result if links were collected; appends the first error code via `rdErrorMessage`. `pendingMessage.kind` is `error` if any error, else `ok` if any completed, else `info`.

**Calls**:
- `retryPending(entries, callback, { signal })` ([lib/rdSender.ts:311](../../../app/src/lib/rdSender.ts#L311)) — invokes `rd_check_pending` per entry internally.
- `reloadPendingSilently` → `invoke('pending_list')` (in `finally`).
- `invoke('copy_rd_links_bulk', { links })` if completedLinks not empty.
- `rdErrorMessage(code)` ([lib/rdSender.ts:358](../../../app/src/lib/rdSender.ts#L358)).

**Triggered by**: Markup button 全部重試（查 RD） [2819](../../../app/src/App.svelte#L2819).

---

#### `cancelRetry(): void`  *(App.svelte:[1294](../../../app/src/App.svelte#L1294))*

**Purpose**: Abort in-flight retry (`retryAbort?.abort()`). Triggered by markup button [2825](../../../app/src/App.svelte#L2825) (rendered only while `isRetryingPending`).

---

#### `removePending(torrent_id: string): Promise<void>`  *(App.svelte:[1622](../../../app/src/App.svelte#L1622))*

**Purpose**: Remove a single pending entry; Rust returns the new list. Guard: returns while `isRdSending || isRetryingPending`. Writes `pendingEntries`, `pendingMessage`.

**Calls**: `invoke('pending_remove', { torrentId })` → `PendingEntry[]`.

**Triggered by**: Per-row 「移除」 button [2865](../../../app/src/App.svelte#L2865).

---

#### `clearAllPending(): Promise<void>`  *(App.svelte:[1637](../../../app/src/App.svelte#L1637))*

**Purpose**: Wipe all pending entries.

**Contract**: Guard: returns while `isRdSending || isRetryingPending`. Sets `pendingEntries = []`, `pendingMessage`; flashes `pending-clear`.

**Calls**: `invoke('pending_clear')`.

**Triggered by**: Markup button 全部清空 [2835](../../../app/src/App.svelte#L2835).

---

### 3.11 Legacy import (M7a-lite)

#### `previewLegacyImport(): Promise<void>`  *(App.svelte:[1304](../../../app/src/App.svelte#L1304))*

**Purpose**: Read `legacyPath`, ask Rust to inspect files without applying anything. Secret values are NEVER echoed back to WebView.

**Contract**:
- Resets `legacyError`/`legacyReport`/`legacyPreview` first.
- Empty path → `legacyError`, return.
- Writes `legacyPreview` on success (flashes `legacy-preview`); `legacyError` on failure; `legacyBusy` set/finally.

**Calls**: `invoke('preview_legacy_import', { sourceDir })` → `LegacyImportPreview`.

**Triggered by**: Markup button [1930](../../../app/src/App.svelte#L1930).

---

#### `applyLegacyImportConfirmed(): Promise<void>`  *(App.svelte:[1580](../../../app/src/App.svelte#L1580))*

**Purpose**: Apply a previewed legacy import — Rust writes RD token to credential store, applies env-derived settings, copies cookies, imports pending entries. Then this function refreshes ALL dependent UI state.

**Contract**:
- Guard: returns while `settingsWriteBusy` (the import may write `settings.json`).
- Resets `legacyError` / `legacyReport` (keeps `legacyPreview`); empty path → `legacyError`, return; `legacyBusy` set/finally.
- After success, conditionally refreshes:
  - `rd_token_imported` → `rdHasToken = true`
  - `env_imported` → `const updated = await loadAndApplySettings()`; if the settings editor is open (`settingsDraft` non-null), `settingsDraft = freshSettingsDraft(updated)` so the draft shows the imported values instead of stale ones (Rust already pushed them to the sidecar). Failure only `console.warn`.
  - `pending_imported > 0` → `reloadPendingSilently("pending_list after import")`
  - `cookies_imported` → `refreshCookiesStatus()`
- Writes `legacyReport`, `legacyError`, `legacyBusy`, `settingsDraft` (conditional); flashes `legacy-apply`.

**Calls**:
- `invoke('apply_legacy_import', { sourceDir })` → `LegacyImportReport`.
- `loadAndApplySettings()` → `invoke('read_settings')` (conditional).
- `freshSettingsDraft(updated)` (conditional: `env_imported` and editor open).
- `reloadPendingSilently()` → `invoke('pending_list')` (conditional).
- `refreshCookiesStatus()` (conditional).

**Triggered by**: Markup button [1941](../../../app/src/App.svelte#L1941).

---

### 3.12 Cookies / data-dir helpers (M7b / M9)

#### `refreshCookiesStatus(): Promise<void>`  *(App.svelte:[1327](../../../app/src/App.svelte#L1327))*

**Purpose**: "重新整理 / 套用變更" — run the cookies.txt → keyring migration on demand, push any migrated value to the running sidecar, and refresh the cookies snapshot (storage, path, size, mtime — never content). With no file, or only the template scaffold, it is a cheap status read.

**Contract**: Clears `cookiesError`; writes `cookiesStatus` and flashes `cookies-refresh` on success. On failure writes `cookiesError` and falls back to a read-only `get_cookies_status` snapshot (`cookiesStatus = null` if that also fails).

**Calls**: `invoke('migrate_cookies_now')` → `CookiesStatus`; fallback `invoke('get_cookies_status')` → `CookiesStatus`.

**Triggered by**: `onMount`, `createCookiesTemplate`, `applyLegacyImportConfirmed`, markup button [2217](../../../app/src/App.svelte#L2217).

---

#### `toggleCookiesShown(): void`  *(App.svelte:[1351](../../../app/src/App.svelte#L1351))*

**Purpose**: Flip `cookiesShown`; on collapse also disarms `cookiesClearArmed` so a primed destructive button is never left behind a collapsed section.

**Triggered by**: Section toggle [2148](../../../app/src/App.svelte#L2148).

---

#### `toggleCookiesPaste(): void`  *(App.svelte:[1359](../../../app/src/App.svelte#L1359))*

**Purpose**: Open/close the paste box. Clears `cookiesMessage`, `cookiesError`, `cookiesClearArmed`; clears `cookiesPasteInput` when closing.

**Triggered by**: 貼上新 cookies / 取消輸入 [2224](../../../app/src/App.svelte#L2224), paste-box 取消 [2288](../../../app/src/App.svelte#L2288).

---

#### `armCookiesClear(): void` / `cancelCookiesClear(): void`  *(App.svelte:[1367](../../../app/src/App.svelte#L1367), [1373](../../../app/src/App.svelte#L1373))*

**Purpose**: First click of the two-click clear (`cookiesClearArmed = true`, clears `cookiesMessage`/`cookiesError`) and its cancel (`cookiesClearArmed = false`).

**Triggered by**: 清除 cookies [2239](../../../app/src/App.svelte#L2239) (disabled while saving or when `cookiesStatus` is null / `storage === "none"`) and 取消清除 [2231](../../../app/src/App.svelte#L2231).

---

#### `clearCookies(): Promise<void>`  *(App.svelte:[1377](../../../app/src/App.svelte#L1377))*

**Purpose**: Second click — delete the keyring entry and `cookies.txt`, and blank the running sidecar's cookies.

**Contract**:
- Clears `cookiesError` / `cookiesMessage`; `cookiesClearing` set/finally.
- Success: takes the post-clear `CookiesStatus` directly (calling `refreshCookiesStatus` would run `migrate_cookies_now` and could promote a surviving `cookies.txt` straight back); disarms, closes and empties the paste box; `cookiesMessage` ok; flashes `cookies-clear`.
- Error starting with `cookies_cleared_sidecar_stale`: deletion succeeded, only the sidecar push failed — same local resets, re-reads status via `get_cookies_status` (plain read, no re-migration), `cookiesMessage` kind `info` telling the user a restart completes it.
- Any other error: `cookiesMessage = { kind: "error", text: "清除失敗：<raw>" }`.

**Calls**: `invoke('clear_cookies')` → `CookiesStatus`; `invoke('get_cookies_status')` on the stale-sidecar path; `errText`.

**Triggered by**: 確定清除 [2228](../../../app/src/App.svelte#L2228) (rendered only while armed).

---

#### `saveCookies(): Promise<void>`  *(App.svelte:[1424](../../../app/src/App.svelte#L1424))*

**Purpose**: Paste flow (M9) — write the pasted cookie header to the keyring and live-update the running sidecar, no restart needed.

**Contract**: Trimmed empty input → `cookiesMessage` error, return. `cookiesSaving` set/finally. Success: writes `cookiesStatus`, clears and closes the paste box, `cookiesMessage` ok, flashes `cookies-save`. Failure maps `cookies_empty` → `cookies 為空`, `cookies_too_large` → `cookies 字串超過 64 KiB 上限`, anything else shown raw.

**Calls**: `invoke('save_cookies', { cookies })` → `CookiesStatus`; `errText`.

**Triggered by**: 儲存到認證管理員 [2278](../../../app/src/App.svelte#L2278).

---

#### `openDataDir(): Promise<void>`  *(App.svelte:[1458](../../../app/src/App.svelte#L1458))*

**Purpose**: Open the app's data dir in the OS file manager. Clears then writes `cookiesError` on failure.

**Calls**: `invoke('open_data_dir')`.

**Triggered by**: Markup button [2222](../../../app/src/App.svelte#L2222).

---

#### `openLogsDir(): Promise<void>`  *(App.svelte:[1467](../../../app/src/App.svelte#L1467))*

**Purpose**: Symmetric to `openDataDir` for the logs directory.

**Calls**: `invoke('open_logs_dir')`.

**Triggered by**: Markup button [2223](../../../app/src/App.svelte#L2223).

---

#### `createCookiesTemplate(): Promise<void>`  *(App.svelte:[1476](../../../app/src/App.svelte#L1476))*

**Purpose**: Have Rust write a placeholder `cookies.txt` so the user can fill it in. Then auto-refresh status.

**Contract**: Clears `cookiesError` / `cookiesMessage`; captures `wasInKeyring` (`cookiesStatus?.storage === "keyring"`) before creating so the success text can tell a cf_clearance refresh apart from first-time setup. Writes `cookiesMessage` (ok/error); on success calls `refreshCookiesStatus` and flashes `cookies-template`.

**Calls**: `invoke('create_cookies_template')`, `refreshCookiesStatus()`.

**Triggered by**: Markup button [2248](../../../app/src/App.svelte#L2248) (only rendered when `cookiesStatus` is set and `storage !== "file"`).

---

#### `formatBytes(n: number): string`  *(App.svelte:[1498](../../../app/src/App.svelte#L1498))*

**Purpose**: Format byte count as B / KB / MB string (no GB tier — cookies files are tiny).

**Pure**. Called by markup for `cookiesStatus.size_bytes` formatting [2178](../../../app/src/App.svelte#L2178).

---

### 3.13 Settings editor (M7c)

#### `freshSettingsDraft(s: Settings): Settings`  *(App.svelte:[1513](../../../app/src/App.svelte#L1513))*

**Purpose**: Single clone helper for the editor draft: copies `version`, shallow-copies `ui` and `rd`, and blanks `rd.api_token` (the editor never displays it).

**Pure**. Called by `openSettingsEditor`, `saveSettings`, `revertSettingsDraft`, `applyLegacyImportConfirmed` (only when `settingsDraft` is non-null).

---

#### `openSettingsEditor(): void`  *(App.svelte:[1521](../../../app/src/App.svelte#L1521))*

**Purpose**: Initialise `settingsDraft = freshSettingsDraft(settings)` and set `settingsShown = true`.

**Contract**:
- Guard: if `settings` is null, writes `settingsMessage = "設定尚未載入"` / Kind = error and returns.
- Writes `settingsDraft`, `settingsShown`, `settingsMessage` (cleared).

**Triggered by**: Toggle button [2033](../../../app/src/App.svelte#L2033) (only opens, never via direct call).

---

#### `saveSettings(): Promise<void>`  *(App.svelte:[1532](../../../app/src/App.svelte#L1532))*

**Purpose**: Persist `settingsDraft` to disk, push to sidecar for the current session, then refresh canonical `settings` + dependent UI (theme/scale).

**Contract**:
- Guards: `settingsWriteBusy` → return; no draft → return; not `settingsValid` → `請先修正紅字欄位` + return.
- Always blanks `api_token` on save (defense in depth — Rust `update_sidecar_settings` also blanks it).
- `update_sidecar_settings` failure is non-fatal (just `console.warn`).
- After save, `loadAndApplySettings()` so canonical state matches disk, then `settingsDraft = freshSettingsDraft(updated)`.
- Writes: `settingsSaving` (set/finally), `settingsMessage`, `settingsMessageKind`, `settings`, `theme`, `settingsDraft`; flashes `settings-save`.

**Calls**:
- `invoke('write_settings', { settings: toSave })`
- `invoke('update_sidecar_settings', { settings: toSave })`
- `loadAndApplySettings()` → `invoke('read_settings')` + `applyTheme` / `applyScale`.

**Triggered by**: Markup button [2125](../../../app/src/App.svelte#L2125).

---

#### `revertSettingsDraft(): void`  *(App.svelte:[1573](../../../app/src/App.svelte#L1573))*

**Purpose**: Reset `settingsDraft` to `freshSettingsDraft(settings)` (un-saved edits discarded); `settingsMessage = "已還原為已儲存值"`, kind `info`. No-op when `settings` is null.

**Triggered by**: Markup button [2135](../../../app/src/App.svelte#L2135).

---

### 3.14 Trivial inline arrow callbacks (summary)

These are inlined in markup rather than declared at the top level; they're listed for completeness:

- `() => (activeTab = "search"|"select"|"rd"|"settings")` — tab buttons [1679, 1689, 1699, 1709](../../../app/src/App.svelte#L1679); 前往挑選 Magnet [2316](../../../app/src/App.svelte#L2316), 回到挑選 [1847](../../../app/src/App.svelte#L1847), 前往「4. 設定」設定 Token [1861](../../../app/src/App.svelte#L1861), 前往 RD 下載連結 [2452](../../../app/src/App.svelte#L2452)
- `() => (legacyShown = !legacyShown)` — toggle button [1910](../../../app/src/App.svelte#L1910)
- `() => { if (!settingsShown) openSettingsEditor(); else settingsShown = false; }` — settings toggle [2033](../../../app/src/App.svelte#L2033)
- `(e) => { e.preventDefault(); openExternal('https://real-debrid.com/apitoken').catch(...) }` — external link [1763](../../../app/src/App.svelte#L1763)
- `() => setRowsSelected(allVisibleRows, true|false)` / `() => selectOnlyRows(allVisibleRows)` — selection summary [2430–2439](../../../app/src/App.svelte#L2430)
- `(e) => setGroupPick((e.currentTarget as HTMLSelectElement).value as GroupPick)` — group-pick select [2497](../../../app/src/App.svelte#L2497)
- `() => confirmSend('all')` / `() => confirmSend('high')` — pre-send confirmation panel [1881, 1885](../../../app/src/App.svelte#L1881)
- `() => toggleCollapsed(g.url)` — per-group toggle [2521](../../../app/src/App.svelte#L2521)
- `() => setRowsSelected(rows, true|false)` — per-group 勾選本組顯示 / 取消本組顯示 [2542, 2545](../../../app/src/App.svelte#L2542)
- `() => toggleSort('name'|'size'|'tags'|'date')` — table header buttons [2570–2585](../../../app/src/App.svelte#L2570)
- `() => copyOne(m.handle_id, m.name || g.result!.code)` — per-row copy [2604, 2647](../../../app/src/App.svelte#L2604)
- `(e) => setRowSelected(m.handle_id, e.currentTarget.checked)` — per-row checkbox [2613](../../../app/src/App.svelte#L2613) (click/dblclick `stopPropagation` so the row's dblclick-copy does not fire)
- `() => copyRdRow(row)` / `() => copyRdSingleLink(row.handle_id, link.download, i)` — progress table [2747, 2779](../../../app/src/App.svelte#L2747)
- `() => removePending(p.torrent_id)` — pending row remove [2865](../../../app/src/App.svelte#L2865)

---

## 4. Call graph — top user flows

### 4.1 Boot

```
Svelte mount
└── onMount [230]
    ├── invoke('get_paths')                 → sets dataDir, logDir
    ├── loadAndApplySettings() [213]
    │   ├── invoke('read_settings')         → settings, theme
    │   ├── applyTheme(theme)               [193] → <html data-theme>
    │   └── applyScale(s.ui.scale)          [203] → CSS var + font-size
    ├── invoke('rd_has_token')              → rdHasToken
    ├── reloadPendingSilently() [222]
    │   └── invoke('pending_list')          → pendingEntries
    ├── invoke('get_legacy_default_dir')    → legacyPath, legacyShown
    └── refreshCookiesStatus()              [1327]
        └── invoke('migrate_cookies_now')   → cookiesStatus
            (on error: invoke('get_cookies_status'))
```

### 4.2 "Scrape" button click

```
button.onclick [2310]
└── startScrape [322]
    ├── parseUrlBatch(urlBatch)             (lib/scraper.ts:145)
    ├── groups = [url placeholders..., ...manual groups]; sendPlanOpen = false
    ├── invoke('forget_magnets', {handleIds: staleIds})   (web handles not shared with manual rows)
    ├── (init scrapeProgress, isScraping, runId = ++scrapeRunId, scrapeAbort)
    └── scrapeBatch(urls, cb, {signal})     (lib/scraper.ts:231)
        ├── per URL: invoke('fetch_javdb', ...)
        └── cb(ev: ScrapeProgressEvent)
            └── applyScrapeProgressForRun({groups, scrapeProgress}, ev, scrapeRunId, runId)  (lib/scraper.ts:86)
                → new groups array with groups[ev.index-1] = ev.group; scrapeProgress = {ev.index, ev.total}
                → rememberSelectableRows(...) for every settled group
```

UI re-render path: `groups` mutation → `groupProcessedRowsMap` recomputed → derived `webGroups` / `okCount` / `errCount` / `totalRawMagnets` / `allVisibleRows` / `selectableMagnets` update → tab badges, status bar and group lists re-render.

### 4.3 "Send to RD" button click

```
button.onclick [1849]
└── sendSelectedToRd [994]
    ├── rdSendTriage (derived) [849]
    │   ├── buildSelectedSendItems [973]
    │   │   ├── for each group: checked rows of g.result.magnets (NOT processedRows)
    │   │   └── dedupeByHandleId (lib/magnetUtils.ts:232)
    │   └── summarizeRdLikelihood(classes via rowClassByHandle) (lib/rdPriority.ts:188)
    ├── low === 0 → runSendBatch(items)                    ← unchanged one-click path
    └── low  > 0  → sendPlanOpen = true; return
                    └── panel [1870] → confirmSend('all'|'high') [1021] → runSendBatch
                                    → cancelSendPlan [1046]
runSendBatch(items) [1057]
├── (sendPlanOpen = false; lastBatchStartAt; init rdSendProgress, rdSendDone, rdSendAbort)
└── sendBatch(items, cb, {signal, defaults}) (lib/rdSender.ts:149)
    ├── per item: invoke('rd_send_magnet', ...)
    └── cb(ev: RdSendBatchEvent)
        └── rdSendProgress[ev.index-1] = ev.item
            if ev.item.status !== "sending": rdSendDone = {settled-row count, ev.total}
finally:
└── reloadPendingSilently() → invoke('pending_list') → pendingEntries (pick up newly added in_pending)
```

### 4.4 "Paste magnet → register" flow

```
button.onclick [2394]
└── registerPastedMagnets [431]
    ├── parseMagnetBatch(magnetBatch) (lib/scraper.ts:155)
    ├── invoke('register_magnets', { magnets })
    ├── snapshot manualHandleIds from current MANUAL groups only
    ├── for each resp.registered: selectedHandles[id] = true; skip if already in a manual group
    └── (rememberSelectableRows; append synthetic group with url='manual://<ts>' to groups)
```

Downstream: visible-count derived recomputes, filter/sort table picks up new rows, and the send-to-RD button activates (assuming `rdHasToken`).

### 4.5 "Retry all pending" flow

```
button.onclick [2819]
└── retryAllPending [1203]
    ├── (init lastBatchStartAt, isRetryingPending, retryAbort, pendingMessage)
    └── retryPending(pendingEntries, cb, {signal}) (lib/rdSender.ts:311)
        ├── per entry: invoke('rd_check_pending', ...)
        └── cb(ev: RdRetryEvent)
            ├── completed → collect links + applyRetryEventToProgressRows → row "completed"
            ├── pending   → bump stillPending
            ├── missing   → applyRetryEventToProgressRows → row "error/rd_torrent_missing"
            ├── else      → bump errorCount, capture error_code
            └── pendingMessage = "重試中 N/M…"
    finally:
    └── reloadPendingSilently("pending_list after retry") → pendingEntries
    if completedLinks:
    └── invoke('copy_rd_links_bulk', {links})
    pendingMessage = final summary
```

### 4.6 "Save settings" flow

```
button.onclick [2125]
└── saveSettings [1532]
    ├── guard settingsWriteBusy; validate via $derived settingsValid
    ├── invoke('write_settings', { settings: toSave })   (api_token blanked)
    ├── invoke('update_sidecar_settings', { settings })  (non-fatal on failure)
    ├── loadAndApplySettings()                           → settings, theme, applyTheme, applyScale
    └── settingsDraft = freshSettingsDraft(updated)
```

### 4.7 "Apply legacy import" flow

```
button.onclick [1941]
└── applyLegacyImportConfirmed [1580]
    ├── guard settingsWriteBusy
    ├── invoke('apply_legacy_import', { sourceDir })   → LegacyImportReport
    ├── if rd_token_imported: rdHasToken = true
    ├── if env_imported:
    │   ├── loadAndApplySettings()                    → updated
    │   └── if settingsDraft: settingsDraft = freshSettingsDraft(updated)
    ├── if pending_imported > 0:
    │   └── reloadPendingSilently("pending_list after import")
    └── if cookies_imported:
        └── refreshCookiesStatus()
```

---

## 5. Markup-side notes

### 5.1 Top-level structure

`<main class="container">` opens with the title and a four-button tab bar (`<nav class="tabs">`
[1674–1715](../../../app/src/App.svelte#L1674): 1. 擷取 Magnet / 2. 挑選 Magnet / 3. RD 下載連結 /
4. 設定, each with a live count badge), then the global `statusMessage` line, then a sequence of
`<section>` blocks. There is **no router**, **no modal overlay**, **no nested component**. Most
sections stay mounted and are hidden with `hidden={activeTab !== "<tab>"}`; only the two RD
result tables are `{#if}`-gated on `activeTab === "rd"`.

| Section | Lines | Tab / gate | Notes |
|---|---|---|---|
| `<h1>` + subtitle | [1671–1672](../../../app/src/App.svelte#L1671) | always | header |
| Tab bar | [1674–1715](../../../app/src/App.svelte#L1674) | always | `onTabKeydown` on each button |
| Global status | [1717–1719](../../../app/src/App.svelte#L1717) | `{#if statusMessage}` | |
| Real-Debrid Token | [1721–1803](../../../app/src/App.svelte#L1721) | settings | token input, test/save; 查詢帳號 / 清除 Token only when `rdHasToken`; `rdUser` line, `rdMessage` |
| 儲存位置 (Storage paths) | [1805–1813](../../../app/src/App.svelte#L1805) | settings | shows `dataDir`, `logDir` |
| 主題 (Theme) | [1815–1820](../../../app/src/App.svelte#L1815) | settings | `toggleTheme` button |
| Sidecar | [1822–1835](../../../app/src/App.svelte#L1822) | settings | `pingSidecar` button + `pingMessage` |
| Real-Debrid (send panel) | [1837–1903](../../../app/src/App.svelte#L1837) | rd | 回到挑選 / send button (`sendButtonLabel`), no-token hint, 送出前確認 panel, `rdMessage` |
| 匯入舊版資料 (Legacy import) | [1905–2026](../../../app/src/App.svelte#L1905) | settings; `{#if legacyShown}` [1914](../../../app/src/App.svelte#L1914) | preview / apply / report inside; preview-vs-report shown by `{#if legacyPreview}` and `{#if legacyReport}` |
| 應用程式設定 (Settings editor) | [2028–2141](../../../app/src/App.svelte#L2028) | settings; `{#if settingsShown && settingsDraft}` [2040](../../../app/src/App.svelte#L2040) | two `<fieldset>`s (RD behaviour + UI). Bound via `bind:value={settingsDraft.rd.*/ui.*}`; the min-size `<input id="set-min-size" type="number" min="0" max="1000000" step="1">` ([2063](../../../app/src/App.svelte#L2063)) mirrors `MAX_MIN_SIZE_MB` / `validateMinSizeMb` |
| JavDB Cookies | [2143–2295](../../../app/src/App.svelte#L2143) | settings; `{#if cookiesShown}` [2152](../../../app/src/App.svelte#L2152) | status by `storage` (keyring / file / none), refresh / open dirs / paste / two-click clear / create template |
| 批次擷取 (Scrape) | [2297–2374](../../../app/src/App.svelte#L2297) | search | URL textarea + action row + status bar + per-URL outcome list (`{#if webGroups.length > 0}` [2341](../../../app/src/App.svelte#L2341)) + empty state |
| 直接貼磁力 (Paste magnet) | [2376–2414](../../../app/src/App.svelte#L2376) | search | magnet textarea + register button + `registerStatus` |
| 每個番號選取 Magnet (Select) | [2416–2669](../../../app/src/App.svelte#L2416) | select; `{#if groups.length > 0}` [2421](../../../app/src/App.svelte#L2421) | selection summary + filter row + **groups list rendering lives here** (checkbox table) |
| 送至 Real-Debrid 進度 (Send progress) | [2671–2802](../../../app/src/App.svelte#L2671) | `{#if activeTab === "rd" && rdSendProgress.length > 0}` | status bar, cancel (only while sending), bulk copy; per-row table over `rdDisplayRows` |
| 待處理（Real-Debrid） (Pending) | [2804–2872](../../../app/src/App.svelte#L2804) | `{#if activeTab === "rd" && pendingEntries.length > 0}` | retry-all / cancel / refresh-local / clear-all + per-row table |

**RD hit-likelihood markup (2026-08-01).**

| Block | Line | Rendered when | Notes |
|---|---|---|---|
| 送出前確認 panel | [1870–1894](../../../app/src/App.svelte#L1870) | `{#if sendPlanOpen}` | 高機率／低機率／未判定 counts + 全部送出 / 只送高機率 / 取消送出. Only appears when the batch actually contains low-likelihood rows, so a clean batch never grows an extra click. |
| 只勾選 RD 優先候選 button | [2436](../../../app/src/App.svelte#L2436) | `{#if groups.length > 0}` | Sits in the selection-summary action row next to 只勾選目前顯示. |
| `rd_ready` `<option>` | [2500](../../../app/src/App.svelte#L2500) | always (within the select tab) | 每組只留 select, placed directly after 全部. |
| Per-row RD badge | [2599–2600](../../../app/src/App.svelte#L2599), [2629–2632](../../../app/src/App.svelte#L2629) | `{#if rdMark}` | `{@const rdCls = rowClassByHandle.get(m.handle_id) ?? classifyRow(m)}` → `rdBadge(rdCls)`. The map, not a direct `classifyRow(m)`: a manual row and its web twin are one BTIH and the web row is the one carrying metadata. `data-rd={rdCls}` drives the badge colour from CSS. |
| Per-row ★ 首選 | [2633–2639](../../../app/src/App.svelte#L2633) | `{#if rdPick && rdPick.row.handle_id === m.handle_id}` | `{@const rdPick = isManualGroup(g) ? undefined : rdPickByGroup.get(g.url)}` [2516](../../../app/src/App.svelte#L2516) — per-GROUP lookup so the same BTIH in a web and a manual group cannot cross-star, and manual groups get no ★ at all (`processGroupRows` never narrows them). `title` from `rdPickTitle(tier)`. |
| ＝網頁同筆 badge | [2623–2628](../../../app/src/App.svelte#L2623) | manual row whose handle is in `webHandleIds` | Tells the user the checkbox state is shared and RD gets it once. |

### 5.2 Event binding hotspots

- **Tab bar**: [1679–1710](../../../app/src/App.svelte#L1679).
- **Settings form binds** (drives derived `settingsErrors`/`settingsValid`): [2050, 2069, 2084, 2098, 2111](../../../app/src/App.svelte#L2050).
- **Filter row** (drives `processedRows`): [2465, 2470, 2479–2480, 2489–2490, 2496–2497, 2506](../../../app/src/App.svelte#L2465).
- **Selection summary row**: [2430–2452](../../../app/src/App.svelte#L2430).
- **Group table sort header buttons**: [2570–2585](../../../app/src/App.svelte#L2570).
- **Per-row checkbox**: [2608–2617](../../../app/src/App.svelte#L2608).
- **Per-row magnet copy** (both row dblclick and per-row button): [2604, 2647](../../../app/src/App.svelte#L2604).
- **Scrape action row**: [2310–2326](../../../app/src/App.svelte#L2310).
- **Send-to-RD action row**: [1847–1861](../../../app/src/App.svelte#L1847); progress actions [2683, 2689](../../../app/src/App.svelte#L2683).
- **Cookies action row**: [2217–2252](../../../app/src/App.svelte#L2217).
- **Pending action row**: [2819–2835](../../../app/src/App.svelte#L2819).
- **Per-pending row remove**: [2865](../../../app/src/App.svelte#L2865).

### 5.3 `{#each}` lists

- `legacyPreview.warnings` [1979](../../../app/src/App.svelte#L1979)
- `legacyReport.sources` [2006](../../../app/src/App.svelte#L2006)
- `legacyReport.warnings` [2016](../../../app/src/App.svelte#L2016)
- `FILE_PICK_VALUES` / `THEME_VALUES` / `SCALE_PRESETS` `<option>` lists [2051, 2099, 2112](../../../app/src/App.svelte#L2051)
- `webGroups` keyed by `g.url` (scrape outcome list) [2346](../../../app/src/App.svelte#L2346)
- `groups` keyed by `g.url` [2510](../../../app/src/App.svelte#L2510)
- `rows` keyed by `m.handle_id` [2594](../../../app/src/App.svelte#L2594)
- `rdDisplayRows` keyed by `row.handle_id` [2712](../../../app/src/App.svelte#L2712)
- `row.links` (per `completed` row) [2756](../../../app/src/App.svelte#L2756)
- `pendingEntries` keyed by `p.torrent_id` [2856](../../../app/src/App.svelte#L2856)

### 5.4 Style

The `<style>` block ([2875–3426](../../../app/src/App.svelte#L2875)) is component-scoped (Svelte default). It uses CSS custom properties (`--color-*`, `--border`, `--ui-scale`) that `applyTheme` / `applyScale` and `index.css` are responsible for defining. No `@keyframes` and no nested selectors; there is one short button `transition` (press / `flash-ok` feedback) and one `@media (max-width: 760px)` block ([3410](../../../app/src/App.svelte#L3410)) that stacks the tab bar and the selection / send / plan panels on narrow windows.

---

## 6. Refactor hotspots

Brief and factual; final judgement is the user's. Status as of HEAD `7c877a8`.

1. **`retryAllPending` ([1203–1292](../../../app/src/App.svelte#L1203)) is ~90 lines**, mixing iteration/accumulators, per-event reconciliation, post-loop pending-list refresh, and a multi-fragment summary builder that also performs a follow-up clipboard write. The former duplicated reconciliation loops are gone — both the completed and missing branches now call `applyRetryEventToProgressRows` (lib/rdSender.ts). Remaining easy split: summary-string builder vs. thin orchestrator.

2. **Status-message state is fragmented across 9+ variables** with similar shapes: `statusMessage` (plain string), `pingMessage` (plain string), `rdMessage` (plain string), `registerStatus` ({kind,text}), `pendingMessage` ({kind,text}), `cookiesError`+`cookiesMessage`, `settingsMessage`+`settingsMessageKind`, `legacyError`. Several pieces of code write to one or another based on which section they belong to; consolidating around a single `{kind, text, scope}` discriminated union (or one-per-section helper) would also let the markup use a single inline-msg component.

3. **`registerPastedMagnets` ([431–536](../../../app/src/App.svelte#L431)) is ~105 lines** packing four steps inline: parse + heuristic error detection, sidecar invoke, manual-group dedupe with re-selection, and synthetic group construction with bespoke `name`/`code` logic. The synthetic-group code resolution rule (`name` for paste groups, group `code` for JavDB) is re-implemented in `buildSelectedSendItems` ([973–992](../../../app/src/App.svelte#L973)) via `g.url.startsWith("manual://")` rather than the `isManualGroup` helper used everywhere else in the file — the string sentinel is still not a named constant.

Adjacent smaller observations (not in the top 3, but worth listing):

- Resolved since the original pass: boot / save / legacy-import now share `loadAndApplySettings` and `reloadPendingSilently`; the draft clone is a single `freshSettingsDraft`; scrape progress no longer does per-index slot replacement on `groups` (`applyScrapeProgressForRun` returns a new array).
- `cancelScrape` / `cancelRdSend` / `cancelRetry` are no longer identical: `cancelScrape` also bumps `scrapeRunId` and resets state immediately, `cancelRdSend` sets `isCancelingSend`. Only `cancelRetry` is a bare `abort()` wrapper.
