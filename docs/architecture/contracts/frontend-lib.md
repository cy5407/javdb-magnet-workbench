# Frontend Library Contracts (`app/src/lib/*` + `app/src/main.ts`)

Reference for refactoring on `codex/function-contracts-analysis`. Every exported and non-exported function in
the Svelte+TypeScript frontend library modules is documented with its contract and call trace.

Last refreshed against HEAD `7c877a8` on 2026-10-16 (line numbers and `App.svelte` call sites
re-verified against that tree).

The companion `App.svelte` (which consumes everything here) is documented separately by another
agent — wherever this file references App.svelte, treat it as "search later for the exact call
sites in `app/src/App.svelte`".

---

## 1. Overview

### 1.1 Module ownership

| File | Owns |
|------|------|
| [main.ts](app/src/main.ts) | App bootstrap. Mounts `App.svelte` into `#app` and pre-seeds `data-theme="light"`. |
| [lib/types.ts](app/src/lib/types.ts) | All shared TypeScript shapes between Rust/sidecar payloads and the WebView. Plus one runtime helper (`defaultFilterState`). |
| [lib/magnetUtils.ts](app/src/lib/magnetUtils.ts) | Pure helpers for parsing/filtering/sorting/grouping `MagnetRow[]`. Zero side effects, no Tauri, no network. |
| [lib/rdPriority.ts](app/src/lib/rdPriority.ts) | Local heuristics for "which magnet is Real-Debrid most likely to already have cached?" — per-row class, per-group pick, badge text. Owns the single definition of "HD". Pure, and the only lib module another lib module imports. |
| [lib/scraper.ts](app/src/lib/scraper.ts) | Batch driver for the JavDB scrape flow. Wraps `invoke('fetch_javdb', …)` with pacing + single-retry on rate limit. Also exposes textarea parsers and the run-id-guarded progress reducer `applyScrapeProgressForRun`. |
| [lib/rdSender.ts](app/src/lib/rdSender.ts) | Batch driver for Real-Debrid send + pending re-poll. Wraps `invoke('rd_send_magnet', …)` and `invoke('rd_check_pending', …)`. Includes the zh-Hant error-code → message mapper, the retry-event → progress-row reconciler, and the progress-table display helpers (link extraction, completion ordering, `completed_at` formatting). |
| [lib/settingsValidation.ts](app/src/lib/settingsValidation.ts) | Pure validators for the Settings editor. Returns null-or-error-string per field; aggregates into a map for the whole draft. |
| [lib/errText.ts](app/src/lib/errText.ts) | The one-line `e instanceof Error ? e.message : String(e)` idiom, factored out of every `catch (e)` site that surfaces an error to the UI. |
| [lib/flashAction.ts](app/src/lib/flashAction.ts) | Reactive controller behind every button's transient "✓" confirmation. Owns the flash-key set and the per-key debounce timers. |
| [vite-env.d.ts](app/src/vite-env.d.ts) | Ambient triple-slash references for Svelte + Vite client types. No runtime, no exports. |

### 1.2 Internal dependency graph

```
main.ts ──► App.svelte (not in scope)

App.svelte ──► lib/scraper.ts ──► lib/types.ts + lib/errText.ts
            ──► lib/magnetUtils.ts ──► lib/rdPriority.ts ──► lib/types.ts
            ──► lib/rdPriority.ts (direct) ──► lib/types.ts
            ──► lib/rdSender.ts ──► lib/types.ts + lib/errText.ts
            ──► lib/settingsValidation.ts ──► lib/types.ts
            ──► lib/flashAction.ts ──► svelte/reactivity (SvelteSet)
            ──► lib/errText.ts (direct)
            ──► lib/types.ts (direct)
```

`types.ts` is still the only shared dependency and nothing imports it cyclically, but the layer
is no longer entirely flat: `magnetUtils.ts` imports `rdPriority.ts` (for `isHdRow` and
`pickRdCandidate`), so the chain is `types.ts ← rdPriority.ts ← magnetUtils.ts ← App.svelte`.
`rdPriority.ts` is itself a leaf and **must stay one** — it deliberately does not import
`magnetUtils.ts`, which is why the same-date tie-break of `pickRdCandidate` is injected by the
caller instead of calling `parseSizeGb` directly (see §3.4). Every other lib file remains a leaf
that imports at most `types.ts` and `errText.ts` (`flashAction.ts` imports only
`svelte/reactivity`; `errText.ts` and `types.ts` import nothing). App.svelte imports `rdPriority.ts` directly as well (badges +
row classes), not only through `magnetUtils.ts`.

### 1.3 Public API surface

| Module | Runtime exports | Type-only exports |
|--------|-----------------|-------------------|
| `magnetUtils.ts` | `parseSizeGb`, `parseFileCount`, `isManualGroup`, `matchesKeyword`, `isHd`, `filterRows`, `pickRdReadyRow`, `applyGroupPick`, `sortRows`, `processGroupRows`, `dedupeByHandleId` | — (`pickRdReadyRow` returns `RdCandidate`, which is re-imported from `rdPriority.ts`, not re-exported here) |
| `rdPriority.ts` | `RD_CACHE_PREFIXES`, `hasCachePrefix`, `hasHdResolution`, `isHdRow`, `rdDateKey`, `classifyRow`, `rdBadge`, `pickRdCandidate`, `summarizeRdLikelihood` | `RdRowClass`, `RdPickTier`, `RdCandidate` |
| `scraper.ts` | `isRateLimitError`, `randomDelayMs`, `parseUrlBatch`, `parseMagnetBatch`, `applyScrapeProgressForRun`, `scrapeBatch` | `JitterFn`, `SleepFn`, `ScrapeProgressEvent`, `ScrapeUiSnapshot`, `ScrapeOptions` |
| `rdSender.ts` | `collectDownloadLinksFromRow`, `sortCompletedRowsByCompletionTime`, `buildRdDisplayRows`, `formatCompletedAt`, `sendBatch`, `applyRetryEventToProgressRows`, `retryPending`, `rdErrorMessage` | `RdSendOptions`, `RdSendItem`, `RdSendBatchEvent`, `RdSendBatchOptions`, `RdRetryEvent`, `RdRetryOptions` |
| `settingsValidation.ts` | `FILE_PICK_VALUES`, `THEME_VALUES`, `SCALE_PRESETS`, `MAX_MIN_SIZE_MB`, `validateMinSizeMb`, `validateCacheWaitSeconds`, `validateScale`, `validateFilePick`, `validateTheme`, `validateSettingsDraft` | `FilePickValue`, `ThemeValue` |
| `errText.ts` | `errText` | — |
| `flashAction.ts` | `createFlashController` | `FlashController` |
| `types.ts` | `defaultFilterState` | `Theme`, `PathInfo`, `UiSettings`, `RdSettings`, `Settings`, `MagnetRow`, `FetchResult`, `PingResponse`, `CopyBulkResult`, `CopyRdLinksBulkResult`, `LegacyImportPreview`, `CookiesStatus`, `LegacyImportReport`, `ScrapedGroup`, `GroupPick`, `FilterState`, `SortColumn`, `SortDirection`, `RdUserInfo`, `RdLink`, `RdSendOutcome`, `RdCheckOutcome`, `PendingEntry`, `RdSendProgress` |

### 1.4 Bridge to Rust

#### Tauri `invoke` calls in `lib/*`

Only three `invoke` call sites live inside `lib/*`. Every other backend call originates from
`App.svelte`.

| Command name | File:line | Payload | Return type | Wrapper function |
|--------------|-----------|---------|-------------|------------------|
| `fetch_javdb` | [scraper.ts:116](app/src/lib/scraper.ts:116) | `{ url: string, batchId: string }` | `FetchResult` | `defaultFetcher` (private) used by `scrapeBatch` (via `resolveScrapeOptions`) |
| `rd_send_magnet` | [rdSender.ts:137](app/src/lib/rdSender.ts:137) | `{ handleId: string, options: RdSendOptions }` | `RdSendOutcome` | `defaultFetcher` (private) used by `sendBatch` |
| `rd_check_pending` | [rdSender.ts:143](app/src/lib/rdSender.ts:143) | `{ torrentId: string, strategy?: string }` | `RdCheckOutcome` | `defaultCheckFetcher` (private) used by `retryPending` |

Tauri maps the camelCase payload keys onto the Rust parameters `batch_id` / `handle_id` /
`torrent_id` ([commands.rs:36](app/src-tauri/src/commands.rs:36),
[commands.rs:443](app/src-tauri/src/commands.rs:443),
[commands.rs:538](app/src-tauri/src/commands.rs:538)). All three wrappers are exposed as
injectable seams via the `fetcher` option, so tests stub them without monkey-patching
`@tauri-apps/api/core`.

#### Tauri event subscriptions in `lib/*`

**None.** No `listen('event-name', …)` calls exist in any `lib/*` module. The frontend currently
learns about backend progress purely by awaiting `invoke` calls in a loop and surfacing results
through caller-supplied `onProgress` callbacks. (App.svelte does not import
`@tauri-apps/api/event` either.)

#### Other external APIs used in `lib/*`

- `setTimeout` (via [scraper.ts:71](app/src/lib/scraper.ts:71) `realSleep`, and
  `setTimeout`/`clearTimeout` in [flashAction.ts:33-60](app/src/lib/flashAction.ts:33)).
- `crypto.getRandomValues` (via [scraper.ts:45-52](app/src/lib/scraper.ts:45) `jitterFraction`,
  the default `rng` of `randomDelayMs`). `Math.random` is deliberately not used (Sonar S2245).
- `Date.prototype.toISOString` (via [scraper.ts:257](app/src/lib/scraper.ts:257),
  [rdSender.ts:188](app/src/lib/rdSender.ts:188) and the default `completedAt` at
  [rdSender.ts:272](app/src/lib/rdSender.ts:272)); local-zone `Date` getters in
  `formatCompletedAt` ([rdSender.ts:122-131](app/src/lib/rdSender.ts:122)).
- `String.prototype.localeCompare` (via [magnetUtils.ts:186-191](app/src/lib/magnetUtils.ts:186)).
- `SvelteSet` from `svelte/reactivity` (via [flashAction.ts:11](app/src/lib/flashAction.ts:11)).
- No `fetch`, no `crypto.subtle`, no `navigator.clipboard`, no `localStorage` in `lib/*`.

---

## 2. Types (`app/src/lib/types.ts`)

`types.ts` is mostly compile-time declarations. The one runtime export is `defaultFilterState`,
documented below in §3.8. The rest are interfaces / unions / aliases. Where a Rust struct
clearly mirrors a shape, the parallel is called out — names use snake_case on both sides because
the Rust side serializes via `serde` with default field naming.

### 2.1 UI-side primitives

#### `type Theme = "light" | "dark"` *(types.ts:10)*
String literal union; the only legal values for the `data-theme` HTML attribute. Mirrored by
the Rust `Settings::ui.theme` field.

#### `interface PathInfo` *(types.ts:12-15)*
- `data_dir: string` — absolute path the sidecar writes its JSON state files into.
- `log_dir: string` — absolute path of the rolling log directory.

Mirrors the Rust `PathInfo` struct ([settings.rs:97](app/src-tauri/src/settings.rs:97)) returned by the
`get_paths` invoke (called from App.svelte).

#### `interface UiSettings` *(types.ts:17-20)*
- `theme: Theme`
- `scale: string` — either the literal `"auto"` or a decimal 0.5–3.0 (rendered to CSS `zoom`).

Mirrors Rust `UiSettings`.

#### `interface RdSettings` *(types.ts:22-27)*
- `api_token: string` — legacy field kept for schema compatibility; Rust `without_secrets`
  ([settings.rs:87](app/src-tauri/src/settings.rs:87)) blanks it to `""` on both `read_settings`
  and `write_settings`. The real token lives in the OS credential store (written via
  `rd_save_token`); the WebView never sees plaintext on read-back.
- `file_pick: string` — one of `FILE_PICK_VALUES`.
- `min_size_mb: number`, `cache_wait_seconds: number`.

Mirrors Rust `RdSettings`. Validation rules: see [settingsValidation.ts](app/src/lib/settingsValidation.ts).

#### `interface Settings` *(types.ts:29-33)*
- `version: number`
- `ui: UiSettings`
- `rd: RdSettings`

Mirrors Rust `Settings` (the same shape `read_settings` returns and `write_settings` accepts). Rust
`clamp_rd_settings` ([settings.rs:78](app/src-tauri/src/settings.rs:78)) clamps
`rd.cache_wait_seconds` to `[5, 300]` and `rd.min_size_mb` to `≤ 1_000_000` on both read and write.

### 2.2 Magnet payloads from the sidecar

#### `interface MagnetRow` *(types.ts:35-42)*
- `handle_id: string` — sidecar-assigned opaque key. The frontend never sees the full magnet
  URI; this id is the only handle for "send to RD" / "copy magnet".
- `name: string`, `size: string` (e.g. `"5.67GB, 5個文件"`), `tags: string[]`, `date: string`.
- `magnet_redacted: string` — display-only string with the btih portion truncated
  (sidecar `redact_magnet`: `magnet:?xt=urn:btih:<first 8 hex>...`).

#### `interface FetchResult` *(types.ts:44-51)*
- `engine: string` (e.g. `"curl_cffi"`)
- `url: string` — the JavDB URL.
- `code: string` — JavDB code (e.g. `"SNOS-192"`).
- `title: string`
- `magnet_count: number`
- `magnets: MagnetRow[]`

Produced by `fetch_javdb`. There is no Rust struct for it: the Rust command returns the sidecar
response's `result` object as an untyped `serde_json::Value` passthrough, so this interface mirrors
the sidecar's `cmd_fetch_javdb` payload directly.

#### `interface ScrapedGroup` *(types.ts:128-135)*
- `url: string`
- `status: "pending" | "fetching" | "ok" | "error"`
- `result: FetchResult | null`
- `error: string | null`
- `finished_at: string | null` — ISO 8601.

Frontend-only aggregator (not a Rust shape). `error` and `result` are *mutually exclusive in
practice* but stored independently so a future retry affordance can replace `error` in place.

### 2.3 Other backend payloads

#### `interface PingResponse` *(types.ts:53-57)*
- `ok: boolean`, `request_id: string`, `uptime_seconds: number`. Returned by the `sidecar_ping`
  invoke, which passes the sidecar's raw `ping` envelope through as a `Value`.

#### `interface CopyBulkResult` *(types.ts:59-62)*
- `copied: number`, `unknown: number`. Returned by `copy_magnets_bulk`.

#### `interface CopyRdLinksBulkResult` *(types.ts:65-67)*
- `copied: number`. Returned by `copy_rd_links_bulk`.

#### `interface LegacyImportPreview` *(types.ts:77-89)*
M7a-lite. Returned by `preview_legacy_import`. Reports only counts, key NAMES, and source
paths — never the actual env values or token. Fields:
- `source_dir: string`, `source_dir_valid: boolean`
- `env_present`, `cookies_present`, `pending_present` (booleans)
- `env_settings_keys: string[]` — non-secret keys discovered in legacy `.env`.
- `has_rd_token: boolean` — true if `RD_API_TOKEN` is non-empty, but the value is **not**
  exposed.
- `pending_count: number`
- `warnings: string[]`

#### `interface CookiesStatus` *(types.ts:103-109)*
M7b. JavDB cookies file health: `present`, `path`, `modified_iso` (or `null`), `size_bytes`, and
`storage: "none" | "file" | "keyring"` (M9+: nothing configured / legacy plaintext `cookies.txt`
pending migration / OS credential store). The cookie BODY is never returned — Rust reads only
`metadata()`. Returned by `get_cookies_status`, `migrate_cookies_now`, `save_cookies` and
`clear_cookies`.

#### `interface LegacyImportReport` *(types.ts:111-119)*
Returned by `apply_legacy_import`. Reports what happened (`env_imported`, `rd_token_imported`,
`cookies_imported`, `pending_imported`, `pending_skipped`), the `sources` (list of paths read
from), and any `warnings`.

### 2.4 Filter / sort / grouping

#### `type GroupPick = "all" | "largest" | "smallest" | "fewest_files" | "rd_ready"` *(types.ts:142)*
Strategy for the "keep N per group" filter step. Semantics implemented in `applyGroupPick`.
`"rd_ready"` keeps the row most likely to be sitting in Real-Debrid's cache already — a local
heuristic (re-upload-site prefix, HD, earliest upload), never an RD lookup; see §3.4
`pickRdCandidate`. It is **not** the default: `defaultFilterState()` still returns `"all"` so
existing users see no behavior change until they pick it from the 每組只留 select.

#### `interface FilterState` *(types.ts:144-152)*
- `keyword: string`
- `hd_only: boolean`
- `min_size_gb: number | null` — null OR 0 means no lower bound.
- `max_size_gb: number | null` — null means no upper bound (0 is also treated as "no bound";
  see [magnetUtils.ts:93](app/src/lib/magnetUtils.ts:93)).
- `group_pick: GroupPick`

#### `defaultFilterState(): FilterState` *(types.ts:154-160)*
**Runtime export.** Arrow-function factory returning the initial filter state.

- Params: none.
- Returns: a fresh `FilterState` with `keyword=""`, `hd_only=false`, `min_size_gb=null`,
  `max_size_gb=null`, `group_pick="all"`.
- Side effects: none.
- Errors: none.
- Async: no.

**Calls**: none.

**Called by**:
- `App.svelte` line 112 (initial filter state) and line 700 (`resetFilter`) — search
  [App.svelte](app/src/App.svelte) for `defaultFilterState`.
- `magnetUtils.test.ts` (imported at line 16; spread into the `filterRows` / `processGroupRows`
  fixtures).

#### `type SortColumn = "size" | "tags" | "date" | "name"` *(types.ts:162)*

#### `type SortDirection = "asc" | "desc"` *(types.ts:163)*

> App holds sort state as two independent reactive vars (`sortColumn: SortColumn | null`,
> `sortDirection: SortDirection`) rather than a combined struct, so there is no exported
> `SortState` interface.

### 2.5 Real-Debrid types

#### `interface RdUserInfo` *(types.ts:169-174)*
RD account snapshot: `username`, `type` ("premium"/"free"), `expiration`, `points`. Returned
by `rd_test_token` / `rd_check_user`.

#### `interface RdLink` *(types.ts:176-183)*
- `original: string` — RD-side URL for the file.
- `download: string` — direct download URL.
- `filename: string`, `filesize: number`, `streamable: number` (0/1).
- `error?: string` — per-link failure note; Rust omits it when `None`
  (`skip_serializing_if`).

#### `type RdSendOutcome` *(types.ts:186-199)*
Discriminated union on `status`. Result of `rd_send_magnet`.
- `{ status: "completed"; torrent_id; name; links: RdLink[] }`
- `{ status: "pending"; torrent_id; name; rd_status: string; progress: number }`

Errors come back as thrown strings (Rust `String` codes) — see §3.6 `rdErrorMessage` for the
known catalogue.

#### `type RdCheckOutcome` *(types.ts:202-219)*
Discriminated union on `status`. Result of `rd_check_pending`.
- `{ status: "completed"; torrent_id; name; links: RdLink[] }`
- `{ status: "pending"; torrent_id; name; rd_status; progress }`
- `{ status: "missing"; torrent_id }` — RD no longer has the torrent.

#### `interface PendingEntry` *(types.ts:222-232)*
Persisted on disk (`pending_torrents.json`). Mirrors Rust `PendingEntry`.
- `torrent_id`, `code`, `name`, `size_label`, `strategy`, `added_at`, `last_progress`,
  `last_rd_status`, `last_checked_at: string | null`.

#### `interface RdSendProgress` *(types.ts:235-252)*
Per-row state in the UI's "send to RD" progress panel.
- `handle_id`, `code`, `size_label?: string` (display-only)
- `status: "pending" | "sending" | "completed" | "in_pending" | "error"`
- `links: RdLink[]`, `error_code: string | null`
- `completed_at?: string` — UTC ISO-8601 stamped by the frontend when the row first completes
  (`sendBatch` / `applyRetryEventToProgressRows`); drives `buildRdDisplayRows` ordering.
- `torrent_id?: string` — captured on completed *or* pending outcomes, so a later
  pending-retry can reconcile the row by `torrent_id`.

---

## 3. Per-file function contracts

### 3.1 `app/src/main.ts`

Boot entry. 12 lines, no exported functions. Side effects:
1. Imports `./app.css` (Vite injects styles).
2. Sets `document.documentElement.dataset.theme = "light"` — initial theme; App.svelte
   overrides once `read_settings` completes ([main.ts:5-6](app/src/main.ts:5)).
3. `mount(App, { target: document.getElementById("app")! })` — Svelte 5 component mount.
4. Re-exports the mounted `app` as `default` so HMR can reuse it.

No functions to contract beyond this. Consumers: the Vite/Tauri bundler, plus
`lib/mainEntry.test.ts`, which mocks `svelte.mount` / `App.svelte` / `app.css` and pins all three
side effects (theme set before mount, mount into `#app`, default export = mount result).

### 3.2 `app/src/vite-env.d.ts`

Two triple-slash directives only:
```
/// <reference types="svelte" />
/// <reference types="vite/client" />
```

No runtime, no exports. Pulls Svelte ambient types and `ImportMeta`/`import.meta.env` typing
from Vite. Nothing here participates in any call trace.

### 3.3 `app/src/lib/magnetUtils.ts`

Pure helpers; no Tauri, no DOM, no network. All return *new* arrays — never mutate inputs.

Module-level private regexes ([magnetUtils.ts:20-23](app/src/lib/magnetUtils.ts:20)), all with
bounded quantifiers so Sonar's super-linear-backtracking rule cannot fire:
`SIZE_TB_RX` / `SIZE_GB_RX` / `SIZE_MB_RX` = `/(\d{1,12}(?:\.\d{1,12})?)\s{0,4}<unit>/i` and
`FILE_COUNT_RX = /(\d{1,9})\s{0,4}個文件/`.

One lib-internal import: `./rdPriority` (`isHdRow`, `pickRdCandidate`, type `RdCandidate`) at
[magnetUtils.ts:5](app/src/lib/magnetUtils.ts:5). The direction is one-way and must stay that
way — `rdPriority.ts` never imports back from here (§1.2).

---

#### `parseSizeGb(size: string): number` *(magnetUtils.ts:26)*

**Purpose**: Parse the size label (e.g. `"5.67GB, 5個文件"`) into a GB-numeric value.

**Contract**:
- Params: `size: string` — the human-readable size column from `MagnetRow.size`. Empty string
  treated as 0.
- Returns: `number` — GB value. Units are tried TB → GB → MB: `"1.2TB"` → `1.2*1024`,
  `"512MB, …"` → `512/1024`. Falsy / unparseable → `0`.
- Side effects: none.
- Errors: none thrown; bad input collapses to `0`.
- Async: no.

**Calls**:
- `RegExp.prototype.exec` (`SIZE_TB_RX`, `SIZE_GB_RX`, `SIZE_MB_RX`).
- `Number.parseFloat`.

**Called by**:
- `filterRows` — [magnetUtils.ts:91, 94](app/src/lib/magnetUtils.ts:91)
- `applyGroupPick` — [magnetUtils.ts:144, 147, 155](app/src/lib/magnetUtils.ts:144)
- `pickRdReadyRow` (injected tie-break) — [magnetUtils.ts:133](app/src/lib/magnetUtils.ts:133)
- `sortRows` — [magnetUtils.ts:184](app/src/lib/magnetUtils.ts:184)
- `magnetUtils.test.ts` (direct unit tests).

---

#### `parseFileCount(size: string): number` *(magnetUtils.ts:38)*

**Purpose**: Parse the file-count portion of the size label (`"… 5個文件"`).

**Contract**:
- Params: `size: string` — same input as `parseSizeGb`.
- Returns: `number` — file count. Empty input → `999`. Match-fail → `999` (sentinel for "very
  many files, deprioritize"; matches the Python reference implementation).
- Side effects: none.
- Errors: none.
- Async: no.

**Calls**:
- `RegExp.prototype.exec` (`FILE_COUNT_RX`), `Number.parseInt(…, 10)`.

**Called by**:
- `applyGroupPick` (`fewest_files` branch) — [magnetUtils.ts:151-152](app/src/lib/magnetUtils.ts:151)
- `magnetUtils.test.ts`.

---

#### `isManualGroup(group: Pick<ScrapedGroup, "url">): boolean` *(magnetUtils.ts:50)*

**Purpose**: True for the synthetic groups created by the paste-magnet path (App.svelte
`registerPastedMagnets`), which use the `manual://` URL scheme.

**Contract**:
- Params: `group` — only `url` is read.
- Returns: `boolean` — `group.url.startsWith("manual://")` (case-sensitive).
- Side effects: none.
- Errors: none.
- Async: no.

**Calls**:
- `String.prototype.startsWith`.

**Called by**:
- `processGroupRows` — [magnetUtils.ts:214](app/src/lib/magnetUtils.ts:214)
- `App.svelte` — web/manual group partitioning in `startScrape`, `registerPastedMagnets`,
  `selectRdCandidatesOnly`, the `webGroups` / `rdPickedHandles` deriveds and the ★ markup — search
  [App.svelte](app/src/App.svelte) for `isManualGroup`.
- `magnetUtils.test.ts`.

---

#### `matchesKeyword(row: MagnetRow, keyword: string): boolean` *(magnetUtils.ts:55)*

**Purpose**: Case-insensitive substring search across `name`/`size`/`date`/`tags`.

**Contract**:
- Params:
  - `row: MagnetRow` — non-null.
  - `keyword: string` — empty string short-circuits to `true` (no filter).
- Returns: `boolean` — true if keyword appears in any haystack field.
- Side effects: none.
- Errors: none.
- Async: no.

**Calls**:
- `String.prototype.toLowerCase`, `String.prototype.includes`.

**Called by**:
- `filterRows` — [magnetUtils.ts:88](app/src/lib/magnetUtils.ts:88)
- `magnetUtils.test.ts`.

---

#### `isHd(row: MagnetRow): boolean` *(magnetUtils.ts:75)*

**Purpose**: True if the row is HD by **tag OR by filename** — the JavDB `"高清"` tag (or
lowercase `"hd"`) **or** a resolution token (`2160p?` / `1080p?` / `4k` / `uhd`) in `row.name`.

> **Widened contract (2026-08-01, deliberate).** This used to be tag-only. JavDB regularly ships
> a 1080p/4K release without the 高清 tag, and the old rule silently dropped those. Because
> `filterRows` calls this helper, the **`hd_only` filter changes behavior with it**: a row named
> `…1080p…` with no 高清 tag now passes 只顯示高清 where it previously did not. Nothing else
> about `filterRows` changed. The rule itself lives in `rdPriority.isHdRow` (§3.4) so the filter,
> the per-row badge and the per-group RD pick can never disagree about what "HD" means; this
> function is now a one-line delegation kept for its existing call sites.

**Contract**:
- Params: `row: MagnetRow`.
- Returns: `boolean` — exactly `isHdRow(row)`.
- Side effects: none.
- Errors: none.
- Async: no.

**Calls**:
- `isHdRow` ([rdPriority.ts:87](app/src/lib/rdPriority.ts:87)) — which in turn calls
  `hasHdResolution`.

**Called by**:
- `filterRows` (`hd_only` branch) — [magnetUtils.ts:89](app/src/lib/magnetUtils.ts:89)
- `magnetUtils.test.ts`.

---

#### `filterRows(rows: MagnetRow[], filter: FilterState): MagnetRow[]` *(magnetUtils.ts:83)*

**Purpose**: Apply non-grouping filters (keyword + hd_only + size range).

**Contract**:
- Params:
  - `rows: MagnetRow[]` — source list.
  - `filter: FilterState` — see [types.ts:144](app/src/lib/types.ts:144). `min_size_gb`/`max_size_gb`
    skip when null OR `<= 0`.
- Returns: `MagnetRow[]` — a NEW array; never mutates input.
- Side effects: none.
- Errors: none.
- Async: no.

**Notes**: `hd_only` follows whatever `isHd` means, and `isHd` was widened to "tag OR resolution
token in the name" (see the entry above) — so this filter now keeps untagged 1080p/4K rows that
it used to drop. Deliberate; no other branch changed.

**Calls**:
- `matchesKeyword`, `isHd`, `parseSizeGb`, `Array.prototype.filter`.

**Called by**:
- `processGroupRows` — [magnetUtils.ts:217](app/src/lib/magnetUtils.ts:217)
- `magnetUtils.test.ts`.

---

#### `pickRdReadyRow(rows: MagnetRow[]): RdCandidate | null` *(magnetUtils.ts:132)*

**Purpose**: The group's best Real-Debrid-cache bet, with the tier that justified it. Thin
binding of `rdPriority.pickRdCandidate` to this module's size parser.

**Contract**:
- Params: `rows: MagnetRow[]` — candidate rows for ONE group (already keyword/size filtered by
  the caller). Empty input → `null`.
- Returns: `RdCandidate | null` — `{ row, tier }` where `tier` is
  `"prefix_hd" | "hd_earliest" | "no_hd_fallback"`. Selection semantics live in
  `pickRdCandidate` (§3.4) — this function only supplies the same-date tie-break.
- Tie-break: `(a, b) => parseSizeGb(b.size) - parseSizeGb(a.size)` — larger file wins a
  same-date tie (same release day, the bigger file is usually the higher-bitrate rip rather than
  a sample). It runs ONLY between rows sharing a date key, so it can never override the primary
  earliest-upload ordering.
- Side effects: none.
- Errors: none.
- Async: no.

**Notes**: the tie-break is injected here rather than living inside `rdPriority.ts` precisely so
that module stays a leaf — importing `parseSizeGb` from this file would close an import cycle
(§1.2).

**Calls**:
- `pickRdCandidate` ([rdPriority.ts:156](app/src/lib/rdPriority.ts:156)), `parseSizeGb`.

**Called by**:
- `applyGroupPick` (`rd_ready` branch) — [magnetUtils.ts:161](app/src/lib/magnetUtils.ts:161)
- `App.svelte` `rdCandidates` derived (per-group ★ + 只勾選 RD 優先候選) — search
  [App.svelte](app/src/App.svelte) for `pickRdReadyRow`.
- `magnetUtils.test.ts`.

---

#### `pickBy(rows, isBetter): MagnetRow[]` *(magnetUtils.ts:116)* — private

**Purpose**: Single-best pick via a comparator, shared by the three size-based `applyGroupPick`
strategies.

**Contract**:
- Params: `rows: MagnetRow[]`; `isBetter(cur, acc): boolean` — true when `cur` is strictly better.
- Returns: `MagnetRow[]` — `[]` for empty input, else a one-element array. Strict comparison keeps
  leftmost-on-tie (the original `>`/`<` reduce semantics).
- Side effects: none. Errors: none. Async: no.

**Calls**: `Array.prototype.reduce`.

**Called by**: `applyGroupPick` (`largest` / `smallest` / `fewest_files`) —
[magnetUtils.ts:144, 147, 150](app/src/lib/magnetUtils.ts:144).

---

#### `applyGroupPick(rows: MagnetRow[], pick: GroupPick): MagnetRow[]` *(magnetUtils.ts:136)*

**Purpose**: After per-row filtering, collapse a group down to a single representative based
on the user's strategy.

**Contract**:
- Params:
  - `rows: MagnetRow[]` — already filtered rows for one group. Empty input → empty output.
  - `pick: GroupPick`:
    - `"all"` → pass-through copy.
    - `"largest"` → row with the maximum `parseSizeGb`.
    - `"smallest"` → row with the minimum `parseSizeGb`.
    - `"fewest_files"` → row with the smallest `parseFileCount`; ties broken by larger
      `parseSizeGb`.
    - `"rd_ready"` → `pickRdReadyRow(rows).row` as a one-element array: the row most likely to
      be cached on RD (prefix+HD → earliest HD → non-HD fallback). Unlike the three size-based
      strategies this one reads `tags`/`date`/`name`, not just `size`. The `null` arm is
      unreachable (`rows` is non-empty past the guard) and only narrows the type.
    - Anything else → pass-through copy (defensive fallback).
- Returns: `MagnetRow[]` — always a new array. Single-element except in `"all"` mode or empty
  input.
- Side effects: none.
- Errors: none.
- Async: no.

**Calls**:
- `Array.prototype.slice`, `pickBy`, `parseSizeGb`, `parseFileCount`, `pickRdReadyRow`.

**Called by**:
- `processGroupRows` — [magnetUtils.ts:218](app/src/lib/magnetUtils.ts:218)
- `magnetUtils.test.ts`.

---

#### `sortRows(rows, column, direction): MagnetRow[]` *(magnetUtils.ts:174)*

**Purpose**: Sort by one of `size`/`tags`/`date`/`name`. Stable (WebView2 Array.sort is
stable per ES2019).

**Contract**:
- Params:
  - `rows: MagnetRow[]`.
  - `column: SortColumn | null` — null short-circuits to a cloned input (no sort).
  - `direction: SortDirection` — `"asc"` (1) or `"desc"` (-1).
- Returns: `MagnetRow[]` — new array (input cloned via `.slice()` before sort).
- Side effects: none.
- Errors: none.
- Async: no.

**Notes**: `"name"` compares on `row.name`. The former `"code"` member of `SortColumn` was
removed (M9 Phase 3) — it was dead code that shared the name-compare branch and had no UI caller.

**Calls**:
- `Array.prototype.slice`, `Array.prototype.sort`, `parseSizeGb`,
  `String.prototype.localeCompare`, `Array.prototype.join`.

**Called by**:
- `processGroupRows` — [magnetUtils.ts:215, 219](app/src/lib/magnetUtils.ts:215)
- `magnetUtils.test.ts`.

---

#### `processGroupRows(group, filter, sortColumn, sortDirection): MagnetRow[]` *(magnetUtils.ts:207)*

**Purpose**: Compose `filterRows → applyGroupPick → sortRows` for one `ScrapedGroup`.

**Contract**:
- Params:
  - `group: ScrapedGroup`. If `group.result` is null (fetch errored or still pending) → `[]`.
  - `filter: FilterState` — fed to `filterRows` and used for `filter.group_pick`.
  - `sortColumn: SortColumn | null`, `sortDirection: SortDirection`.
- Returns: `MagnetRow[]` — new array per call; empty when group has no result or every row was
  filtered out.
- Side effects: none.
- Errors: none.
- Async: no.

**Notes**: manual (pasted) groups — `isManualGroup(group)`, i.e. `url` starts with `manual://` —
skip `filterRows` AND `applyGroupPick` entirely and only get sorted. That is why a `"rd_ready"`
group-pick never collapses a pasted magnet, and why App.svelte does not put the ★ 首選 marker on
manual rows: no narrowing happens there to justify one.

**Calls**:
- `filterRows`, `applyGroupPick`, `sortRows`, `isManualGroup`.

**Called by**:
- `App.svelte` lines 572 (`groupProcessedRowsMap` derived) and 578 (`processedRows` fallback) —
  search [App.svelte](app/src/App.svelte) for `processGroupRows`.
- `magnetUtils.test.ts`.

---

#### `dedupeByHandleId<T extends { handle_id: string }>(rows: T[]): T[]` *(magnetUtils.ts:232)*

**Purpose**: Order-preserving dedupe by `handle_id`. Second-line defense before clipboard
write / RD send.

**Contract**:
- Params: `rows: T[]` where `T` has a `handle_id: string`. Generic so the helper works for
  both `MagnetRow` and `RdSendProgress` (anything with a `handle_id`).
- Returns: `T[]` — new array; first occurrence's metadata wins.
- Side effects: none.
- Errors: none.
- Async: no.

**Calls**:
- `new Set<string>()`, `Set.has`/`Set.add`.

**Called by**:
- `App.svelte` — `copySelected` (line 549), `buildSelectedSendItems` (line 991) and the
  selection / visible-count deriveds (lines 668–793) — search [App.svelte](app/src/App.svelte) for
  `dedupeByHandleId`.
- `magnetUtils.test.ts`.

---

### 3.4 `app/src/lib/rdPriority.ts`

Local heuristics for "which magnet is Real-Debrid most likely to already have cached?". Pure;
no Tauri, no DOM, no network — and a LEAF: it imports only `./types`, never `./magnetUtils`
(§1.2).

**This cannot be an API lookup.** RD removed `/torrents/instantAvailability` in 2024 and the
sidecar's `realdebrid.py` has no cache-probe endpoint, so every value produced here is a guess
derived from the JavDB row's own metadata (re-upload-site prefix in the filename, HD markers,
upload date). It is a hint for the user, never a promise that the send will hit cache — the UI
strings say so too.

Module-level constants ([rdPriority.ts:27-55](app/src/lib/rdPriority.ts:27)):
- `RD_CACHE_PREFIXES: readonly string[]` = `["hhd800.com@", "489155.com@"]` — **exported**.
  Re-upload sites whose releases are empirically the ones already in RD's cache. Matched with
  `includes` on the lower-cased name, *not* `startsWith`: JavDB sometimes renders a row as
  `"[javdb.com]hhd800.com@ABC-123"`, where a prefix test would silently miss. Hardcoded on
  purpose — a user-editable list would need a settings round-trip through Rust + sidecar.
- `HD_RESOLUTION_RX = /(?:2160p|1080p|4k|uhd|(?<=\dx)(?:2160|1080))(?![a-z0-9])/i` —
  private. The lookbehind is fixed-width on purpose: Python's `re` rejects the variable-width
  form, and `scripts/rd_log_report.py` must carry a behaviourally identical copy to
  score the RD outcome log. Only the two characters before the number decide the
  match, so `\dx` and `\d{1,4}x` are equivalent here. Every alternative is a fixed-width literal and the lookbehind is bounded, so there is
  no unbounded repetition to backtrack over (same Sonar super-linear-backtracking concern that
  bounded magnetUtils' `SIZE_*_RX`). Two boundaries carry the rule:
  - trailing `(?![a-z0-9])` — without it `"1080MB"`, a size, would count as HD;
  - a BARE `1080` / `2160` only counts inside a `WxH` spelling (`"1920x1080"`). Without that
    restriction, JAV serials that happen to end in those digits — `259LUXU-1080`, `HEYZO-2160`,
    `300MIUM-1080` are all real labels — classify as HD. That is the worse of the two errors: a
    missed HD row is still caught by JavDB's `高清` tag, whereas a false HD row passes `hd_only`,
    wears the badge, and lands in the pre-send "high likelihood" bucket with nothing left to
    catch it.
- `NO_DATE_KEY = "9999-99-99"` — private sentinel sorting AFTER every real ISO date. A raw `""`
  compares as smaller than `"2019-01-01"`, so without it a pasted magnet (no date at all) would
  win "earliest upload" in every single group.

Exported types:
- `type RdRowClass = "prefix_hd" | "prefix_only" | "hd" | "unknown" | "plain"`
  *(rdPriority.ts:58)* — per-row likelihood class; see `classifyRow` for the table.
- `type RdPickTier = "prefix_hd" | "hd_earliest" | "no_hd_fallback"` *(rdPriority.ts:61)* —
  which rule produced a group's pick. Drives the ⚠ wording on the fallback tier and is what
  App.svelte checks before auto-checking a candidate.
- `interface RdCandidate { row: MagnetRow; tier: RdPickTier }` *(rdPriority.ts:63-66)*.

Private type:
- `type RdTieBreak = (a: MagnetRow, b: MagnetRow) => number` *(rdPriority.ts:69)* — returns `<0`
  when `a` is the better of two rows that share a date key.

---

#### `hasCachePrefix(row: MagnetRow): boolean` *(rdPriority.ts:71)*

**Purpose**: True when the release name contains one of `RD_CACHE_PREFIXES` anywhere.

**Contract**:
- Params: `row: MagnetRow` — only `row.name` is read.
- Returns: `boolean`. Case-insensitive (name is lower-cased first); substring match, so an
  embedded prefix like `"[javdb.com]hhd800.com@ABC-123"` counts.
- Side effects: none.
- Errors: none.
- Async: no.

**Calls**:
- `String.prototype.toLowerCase`, `Array.prototype.some`, `String.prototype.includes`.

**Called by**:
- `classifyRow` — [rdPriority.ts:101](app/src/lib/rdPriority.ts:101)
- `pickRdCandidate` (tier-3 pool) — [rdPriority.ts:175](app/src/lib/rdPriority.ts:175)
- `rdPriority.test.ts`.

---

#### `hasHdResolution(name: string): boolean` *(rdPriority.ts:77)*

**Purpose**: True when the release NAME advertises 1080p / 2160p / 4K / UHD.

**Contract**:
- Params: `name: string` — the raw filename. Empty/falsy → `false` (short-circuit before the
  regex).
- Returns: `boolean` — `HD_RESOLUTION_RX.test(name)`, case-insensitive.
- Boundary cases: `"1080MB"` / `"2160MB"` / `"4KB"` → `false` (trailing `(?![a-z0-9])`);
  `"259LUXU-1080.mp4"` / `"HEYZO-2160"` / `"ABC-123 1080"` → `false` (a bare number is a serial,
  not a resolution); `"1920x1080"`, `"3840X2160"`, `"1080p"`, `"4K"`, `"UHD"` → `true`.
- Side effects: none.
- Errors: none.
- Async: no.

**Calls**:
- `RegExp.prototype.test`.

**Called by**:
- `isHdRow` — [rdPriority.ts:91](app/src/lib/rdPriority.ts:91)
- `rdPriority.test.ts`.

---

#### `isHdRow(row: MagnetRow): boolean` *(rdPriority.ts:87)*

**Purpose**: The single definition of "HD" for the whole frontend: tag **OR** filename.

**Contract**:
- Params: `row: MagnetRow` — reads `tags` then `name`.
- Returns: `boolean` — `true` if any tag is exactly `"高清"` or lower-cases to `"hd"`; otherwise
  `hasHdResolution(row.name)`.
- Side effects: none.
- Errors: none.
- Async: no.

**Notes**: `magnetUtils.isHd` (and therefore the `hd_only` filter) delegates here, so the badge,
the per-group candidate pick and the filter can never disagree. The filename half is the
2026-08-01 widening — see §3.3 `isHd` for the behavior-contract note.

**Calls**:
- `Array.prototype.some`, `String.prototype.toLowerCase`, `hasHdResolution`.

**Called by**:
- `classifyRow` — [rdPriority.ts:102](app/src/lib/rdPriority.ts:102)
- `pickRdCandidate` (tier-2 bucket) — [rdPriority.ts:168](app/src/lib/rdPriority.ts:168)
- `magnetUtils.isHd` — [magnetUtils.ts:76](app/src/lib/magnetUtils.ts:76)
- `rdPriority.test.ts`.

---

#### `rdDateKey(row: MagnetRow): string` *(rdPriority.ts:95)*

**Purpose**: Sortable upload-date key with missing dates pushed to the END of the ordering.

**Contract**:
- Params: `row: MagnetRow` — reads `row.date`.
- Returns: `string` — `row.date.trim()`, or `NO_DATE_KEY` (`"9999-99-99"`) when that is empty.
  Whitespace-only dates normalize the same way as `""`.
- Side effects: none.
- Errors: none.
- Async: no.

**Notes**: this is the single most error-prone rule in the feature. Plain string comparison puts
`""` before every real ISO date, so skipping the normalization makes a metadata-less pasted row
win "earliest upload" in every group. `rdPriority.test.ts` guards it explicitly.

**Calls**:
- `String.prototype.trim`.

**Called by**:
- `earliestBy` — [rdPriority.ts:141-142](app/src/lib/rdPriority.ts:141)
- `rdPriority.test.ts`.

---

#### `classifyRow(row: MagnetRow): RdRowClass` *(rdPriority.ts:100)*

**Purpose**: Per-row likelihood class — what the badge shows and what the pre-send summary
counts.

**Contract**:
- Params: `row: MagnetRow`.
- Returns: `RdRowClass`, first match wins:

  | Class | Condition | Meaning |
  |---|---|---|
  | `prefix_hd` | cache prefix ∧ HD | RD most likely already has it |
  | `prefix_only` | cache prefix ∧ not HD | good odds, quality unverified |
  | `hd` | no prefix ∧ HD | judged by earliest upload |
  | `unknown` | neither, and `tags` empty **and** `date` blank | no metadata to judge (pasted magnets) |
  | `plain` | everything else (has metadata, explicitly not HD) | low odds and wrong quality |

- Side effects: none.
- Errors: none.
- Async: no.

**Notes**: `unknown` exists so a pasted magnet is not reported as *low* likelihood — missing
metadata is not evidence of low quality, and showing "low" for a row we know nothing about would
be a fake signal. `summarizeRdLikelihood` therefore files it under `unrated`, not `low`.

**Calls**:
- `hasCachePrefix`, `isHdRow`, `String.prototype.trim`.

**Called by**:
- `pickRdCandidate` (tier-1 bucket) — [rdPriority.ts:162](app/src/lib/rdPriority.ts:162)
- `App.svelte` — `rowClassByHandle` derived + the per-row badge fallback in markup.
- `rdPriority.test.ts`.

---

#### `rdBadge(cls: RdRowClass): { text: string; title: string } | null` *(rdPriority.ts:114)*

**Purpose**: Badge label + tooltip for a class, or nothing when the class carries no signal.

**Contract**:
- Params: `cls: RdRowClass`.
- Returns:
  - `prefix_hd` → `{ text: "⚡高清", title: "常見轉載站 + 高清：RD 最可能已有快取" }`
  - `prefix_only` → `{ text: "⚡", title: "常見轉載站：命中率高，但畫質未確認" }`
  - `hd` → `{ text: "高清", title: "高清但非常見轉載站：以最早上傳推測命中率" }`
  - `unknown` / `plain` → `null` — deliberately no badge. `plain` would be a "this is bad" mark
    on the majority of rows, and `unknown` has nothing to report.
- Side effects: none.
- Errors: none.
- Async: no.

**Calls**: none.

**Called by**:
- `App.svelte` — per-row 番號 column badge.
- `rdPriority.test.ts`.

---

#### `earliestBy(rows: MagnetRow[], tieBreak: RdTieBreak): MagnetRow` *(rdPriority.ts:134)* — private

**Purpose**: Earliest-upload pick inside one already-classified bucket.

**Contract**:
- Params: `rows: MagnetRow[]` — must be NON-empty (callers guarantee it; an explicit guard
  fails fast if a refactor ever breaks that invariant). `tieBreak: RdTieBreak`.
- Returns: `MagnetRow` — smallest `rdDateKey`; `tieBreak` runs ONLY when two rows share a date
  key, so a caller-supplied "bigger file wins" comparator can never override the primary date
  ordering.
- The replacement test is strict (`< 0`), which keeps leftmost-on-tie — the same semantics as
  magnetUtils' `pickBy`.
- Side effects: none.
- Errors: throws `Error("earliestBy: rows must not be empty")` on an empty array (unreachable via
  the exported API; `pickRdCandidate([])` returns `null` first).
- Async: no.

**Calls**:
- `Array.prototype.reduce` (seeded with `rows[0]`), `rdDateKey`, the injected `tieBreak`.

**Called by**:
- `pickRdCandidate` (all three tiers) — [rdPriority.ts:164, 170, 177](app/src/lib/rdPriority.ts:164).

---

#### `pickRdCandidate(rows: MagnetRow[], tieBreak?: RdTieBreak): RdCandidate | null` *(rdPriority.ts:156)*

**Purpose**: The group's single most-likely-cached row, plus the tier that justified it.

**Contract**:
- Params:
  - `rows: MagnetRow[]` — one group's rows. Empty input → `null`.
  - `tieBreak?: RdTieBreak` — defaults to `() => 0`, i.e. input order wins a same-date tie.
    `magnetUtils.pickRdReadyRow` injects "larger `parseSizeGb` first"; the parameter exists so
    this module never has to import `magnetUtils` (§1.2).
- Returns: `RdCandidate | null`. Tiers are tried in order, first non-empty bucket wins:
  1. `prefix_hd` — rows classifying as `prefix_hd` (re-upload site AND HD) → tier `"prefix_hd"`.
  2. `hd_earliest` — any `isHdRow` row → tier `"hd_earliest"`. (Tier 1 was empty here, so every
     HD row necessarily classifies as `hd`.) Oldest first: more time to have been cached.
  3. `no_hd_fallback` — nothing in the group is HD. Prefixed rows still carry the better odds so
     they form the pool when present; otherwise the pool is every row. ⚠ This tier is a weak
     guess, which is why App.svelte refuses to auto-check it.
  Within every tier the winner is `earliestBy` — earliest `rdDateKey`, `tieBreak` only on ties.
- Side effects: none.
- Errors: none.
- Async: no.

**Calls**:
- `Array.prototype.filter`, `classifyRow`, `isHdRow`, `hasCachePrefix`, `earliestBy`.

**Called by**:
- `magnetUtils.pickRdReadyRow` — [magnetUtils.ts:133](app/src/lib/magnetUtils.ts:133)
- `rdPriority.test.ts`.

---

#### `summarizeRdLikelihood(classes: RdRowClass[]): { high, low, unrated }` *(rdPriority.ts:188)*

**Purpose**: Bucket counts for the pre-send summary panel.

**Contract**:
- Params: `classes: RdRowClass[]` — one entry per row about to be sent. Empty input →
  `{ high: 0, low: 0, unrated: 0 }`.
- Returns: `{ high: number; low: number; unrated: number }` where
  - `high` = `prefix_hd` + `hd`
  - `low` = `plain` only
  - `unrated` = `prefix_only` + `unknown`
  The three always sum to `classes.length`.
- Side effects: none.
- Errors: none.
- Async: no.

**Notes**: `unrated` deliberately holds both `prefix_only` (good odds, unverified quality) and
`unknown` (no metadata). Neither belongs in `low`, which must mean "we have metadata and it says
this is not what you want" — App.svelte only interrupts a send when `low > 0`, so mis-filing
either class would nag the user about batches with nothing wrong with them.

**Calls**: none (plain `for…of`).

**Called by**:
- `App.svelte` `rdSendTriage` derived — pre-send triage; `sendSelectedToRd` opens the summary
  panel when its `low > 0`.
- `rdPriority.test.ts`.

---

### 3.5 `app/src/lib/scraper.ts`

Batch driver for `fetch_javdb`. Sequential, paced, single-retry on rate-limit-flavored errors.
Imports `invoke`, `./errText` and types from `./types`.

Module-level constants ([scraper.ts:15-25](app/src/lib/scraper.ts:15)):
- `DELAY_MIN_MS = 3000`, `DELAY_MAX_MS = 6000` — between-request jitter range.
- `RETRY_WAIT_MIN_MS = 10000`, `RETRY_WAIT_MAX_MS = 15000` — back-off range after a 429.
- `RATE_LIMIT_PATTERNS` — case-insensitive regex array (`\b429\b`, `rate[\s-]?limit`,
  `cloudflare`, `too many requests`).

Module-level private values:
- `jitterFraction()` ([scraper.ts:45-52](app/src/lib/scraper.ts:45)) — `[0, 1)` fraction from
  `globalThis.crypto.getRandomValues(new Uint32Array(1)) / 2**32`. Not a security primitive; it
  goes through Web Crypto only so Sonar S2245 does not flag `Math.random`.
- `realSleep: SleepFn` ([scraper.ts:71](app/src/lib/scraper.ts:71)) — `setTimeout`-based.
- `defaultFetcher` ([scraper.ts:115-116](app/src/lib/scraper.ts:115)) — wraps the `fetch_javdb`
  invoke.
- `nextScrapeBatchId` ([scraper.ts:123](app/src/lib/scraper.ts:123)) — process-local monotonic
  counter. One id (`"scrape-<n>"`) is shared by every URL/retry in a `scrapeBatch` call; the next
  call receives a fresh id so sidecar metadata ownership follows the currently visible web batch
  rather than the lifetime of a deduped handle.

---

#### `isRateLimitError(message: string): boolean` *(scraper.ts:27)*

**Purpose**: Decide whether an error message looks like a rate-limit (so `scrapeBatch` should
back off and retry once).

**Contract**:
- Params: `message: string` — `errText(e)` of the rejected fetch.
- Returns: `boolean` — true iff any pattern in `RATE_LIMIT_PATTERNS` matches. Empty string →
  `false`.
- Side effects: none.
- Errors: none.
- Async: no.

**Calls**:
- `Array.prototype.some`, `RegExp.test`.

**Called by**:
- `fetchGroupWithRetry` — [scraper.ts:209](app/src/lib/scraper.ts:209)
- `scraper.test.ts`.

---

#### `type JitterFn = () => number` *(scraper.ts:32)*

Type alias for the injectable `[0, 1)` random source of `randomDelayMs`.

---

#### `randomDelayMs(min: number, max: number, rng?: JitterFn): number` *(scraper.ts:60)*

**Purpose**: Random integer in `[min, max]` inclusive. Used for both jitter between requests
and back-off after rate limits.

**Contract**:
- Params: `min: number`, `max: number`. If `max <= min`, returns `min` (defensive — tests use
  `[0, 0]` to disable pacing). `rng: JitterFn = jitterFraction` — tests pass a deterministic
  source (e.g. `() => 0`) instead of mocking the global.
- Returns: `number` — integer, `Math.floor(min + rng() * (max - min + 1))`.
- Side effects: none beyond the default `rng` reading Web Crypto.
- Errors: none.
- Async: no.

**Calls**:
- `rng` (default `jitterFraction` → `crypto.getRandomValues`), `Math.floor`.

**Called by**:
- `scrapeBatch` (between-URL pacing) — [scraper.ts:250](app/src/lib/scraper.ts:250)
- `fetchGroupWithRetry` (retry wait) — [scraper.ts:216](app/src/lib/scraper.ts:216)
- `scraper.test.ts`.

---

#### `type SleepFn = (ms: number) => Promise<void>` *(scraper.ts:69)*

Type alias for the test-injectable sleep function.

---

#### `parseBatchWithFilter(raw: string, filterRe: RegExp): string[]` *(scraper.ts:125)* — private

Shared body of the two textarea parsers: split on `/\r?\n/`, trim, drop blanks and `#`-prefixed
comment lines, keep lines matching `filterRe`, order-preserving dedupe via `Set`. Falsy `raw` →
`[]`.

---

#### `parseUrlBatch(raw: string): string[]` *(scraper.ts:145)*

**Purpose**: Normalize a multi-line textarea into a deduped, trimmed list of HTTPS URLs.

**Contract**:
- Params: `raw: string` — textarea contents (may contain `\r\n` or `\n`). Falsy → `[]`.
- Returns: `string[]` — order-preserving dedupe; drops blank lines, `#`-prefixed comment lines,
  and any line not starting with `https://` (case-insensitive).
- Side effects: none.
- Errors: none.
- Async: no.

**Calls**:
- `parseBatchWithFilter(raw, /^https:\/\//i)`.

**Called by**:
- `App.svelte` line 324 (`startScrape`) — search [App.svelte](app/src/App.svelte) for
  `parseUrlBatch`.
- `scraper.test.ts`.

---

#### `parseMagnetBatch(raw: string): string[]` *(scraper.ts:155)*

**Purpose**: Normalize a "paste magnets directly" textarea into a deduped list of `magnet:` URIs.

**Contract**:
- Params: `raw: string`. Falsy → `[]`.
- Returns: `string[]` — order-preserving dedupe; drops blanks, `#`-comments, anything not
  matching `/^magnet:/i`.
- Side effects: none. (Sidecar dedupes again on its side; this is mainly UX.)
- Errors: none.
- Async: no.

**Calls**:
- `parseBatchWithFilter(raw, /^magnet:/i)`.

**Called by**:
- `App.svelte` line 433 (`registerPastedMagnets`) — search [App.svelte](app/src/App.svelte)
  for `parseMagnetBatch`.
- `scraper.test.ts`.

---

#### `applyScrapeProgressForRun(state, ev, activeRunId, eventRunId): ScrapeUiSnapshot` *(scraper.ts:86)*

**Purpose**: Pure reducer that folds one `ScrapeProgressEvent` into the UI snapshot, but only if
the event belongs to the scrape run that is still active — so a stale batch (superseded by a
newer 擷取 or a clear) can never write into the current `groups`.

**Contract**:
- Params:
  - `state: ScrapeUiSnapshot` — `{ groups, scrapeProgress: { done, total } }`.
  - `ev: ScrapeProgressEvent`.
  - `activeRunId: number`, `eventRunId: number`.
- Returns: the SAME `state` object (identity) when `activeRunId !== eventRunId`; otherwise a new
  snapshot whose `groups` is a copy with `groups[ev.index - 1] = ev.group` and
  `scrapeProgress = { done: ev.index, total: ev.total }`. Callers compare identity to detect
  "no change".
- Side effects: none (input arrays are not mutated).
- Errors: none.
- Async: no.

**Calls**: `Array.prototype.slice`.

**Called by**:
- `App.svelte` `startScrape` `onProgress` callback (line 395) — search
  [App.svelte](app/src/App.svelte) for `applyScrapeProgressForRun`.
- `scraper.test.ts`.

---

#### `resolveScrapeOptions(opts: ScrapeOptions): ResolvedScrapeOptions` *(scraper.ts:168)* — private

Fills defaults (`realSleep`, `defaultFetcher`, `[3000, 6000]`, `[10000, 15000]`) and allocates
the batch id `` `scrape-${++nextScrapeBatchId}` `` — so every `scrapeBatch` call consumes exactly
one id. `ResolvedScrapeOptions` ([scraper.ts:159-166](app/src/lib/scraper.ts:159)) is the
private, all-required shape.

---

#### `fetchGroupWithRetry(group, resolved): Promise<boolean>` *(scraper.ts:183)* — private

**Purpose**: Try one URL with at most one retry after a rate-limit error. Mutates `group` in
place (`status` / `result` / `error`).

**Contract**:
- Returns `true` when the group settled (`ok` or `error`) and `false` when the run was aborted
  mid-flight, in which case the group is reset to `status: "pending"`, `error: null` (and
  `result: null` if the fetch had resolved).
- `signal.aborted` is re-checked after the fetch resolves, after it rejects, and after the
  retry wait.
- A first-attempt failure whose `errText(e)` matches `isRateLimitError` sleeps
  `randomDelayMs(...retryWaitRange)` and retries once; any other failure, or a second failure,
  records `error = message`, `status = "error"`.

**Calls**: injected `fetcher`, `errText`, `isRateLimitError`, `randomDelayMs`, injected `sleep`.

**Called by**: `scrapeBatch` — [scraper.ts:255](app/src/lib/scraper.ts:255).

---

#### `scrapeBatch(urls, onProgress, opts?): Promise<ScrapedGroup[]>` *(scraper.ts:231)*

**Purpose**: Drive the JavDB batch scrape. Calls `fetch_javdb` once per URL, paced and with a
single retry on rate-limit-flavored errors.

**Contract**:
- Params:
  - `urls: string[]` — caller is expected to have already passed input through `parseUrlBatch`.
  - `onProgress: (ev: ScrapeProgressEvent) => void` — fires AFTER each group settles (ok or
    error). Receives `{ index: 1-based, total, group }`. Not fired for a group whose fetch was
    abandoned by an abort.
  - `opts?: ScrapeOptions`:
    - `signal?: AbortSignal` — checked at top of each iteration, after each pacing sleep, and
      inside `fetchGroupWithRetry` (after the fetch settles and after the retry wait); once
      aborted, the loop breaks and returns the partially-populated groups.
    - `sleep?: SleepFn` — defaults to `realSleep`. Tests inject a no-op.
    - `delayRange?: [number, number]` — between-request range. Defaults `[3000, 6000]`. No
      delay before the first URL.
    - `retryWaitRange?: [number, number]` — defaults `[10000, 15000]`.
    - `fetcher?: (url, batchId) => Promise<FetchResult>` — defaults to
      `invoke('fetch_javdb', { url, batchId })`.
- Returns: `Promise<ScrapedGroup[]>` — the final groups array in the input order. Each group
  has its `status` set to `ok` | `error` | `pending` (if aborted before or during its turn).
  If `signal` is aborted after `fetcher` resolves, the result is dropped; `status` stays `pending`
  and `finished_at` stays `null`. `finished_at` is set only when the group successfully settles to `ok` or `error`.
- Side effects: invokes `fetch_javdb` (one Tauri command per attempt, all sharing one
  `batchId`); calls `setTimeout` via `realSleep`; reads system clock via
  `new Date().toISOString()`; increments `nextScrapeBatchId`.
- Errors: never throws for per-URL failures. All per-URL errors are captured into
  `group.error` (string) and `group.status = "error"`. The Promise only rejects if the caller's
  `onProgress` callback itself throws (or the pacing / retry `sleep`, which runs outside any
  `try`, rejects).
- Async: yes. Resolves only after every URL has settled (or `signal.aborted` becomes true).

**Retry rule**: A first-attempt failure whose message matches `isRateLimitError` triggers one
back-off + retry. A second failure is recorded as `error`. Non-rate-limit errors are recorded
immediately (no retry).

**Calls**:
- `resolveScrapeOptions`, `fetchGroupWithRetry`.
- `@tauri-apps/api/core::invoke('fetch_javdb', { url, batchId })` via `defaultFetcher`.
- `randomDelayMs` (pacing here; retry-wait inside `fetchGroupWithRetry`)
- `isRateLimitError`, `errText` (inside `fetchGroupWithRetry`)
- `realSleep` / injected `sleep`
- `Date.prototype.toISOString`

**Called by**:
- `App.svelte` line 391 (`startScrape`) — search [App.svelte](app/src/App.svelte) for
  `scrapeBatch`.
- `scraper.test.ts`.

---

#### Interface `ScrapeProgressEvent` *(scraper.ts:74-79)*
- `index: number` (1-based), `total: number`, `group: ScrapedGroup`.

#### Interface `ScrapeUiSnapshot` *(scraper.ts:81-84)*
- `groups: ScrapedGroup[]`, `scrapeProgress: { done: number; total: number }` — the slice of
  App.svelte state `applyScrapeProgressForRun` reduces over.

#### Interface `ScrapeOptions` *(scraper.ts:101-111)*
Documented above as part of `scrapeBatch` params.

---

### 3.6 `app/src/lib/rdSender.ts`

Two batch drivers, a retry-event reconciler, progress-table display helpers and a zh-Hant
error-message mapper. No event listeners — the UI polls via the caller's `onProgress` callback
between awaits. Imports `invoke`, `./errText` and types from `./types`.

Module-level private wrappers:
- `defaultFetcher` at [rdSender.ts:133-137](app/src/lib/rdSender.ts:133) — wraps
  `invoke<RdSendOutcome>('rd_send_magnet', { handleId, options })`.
- `defaultCheckFetcher` at [rdSender.ts:139-143](app/src/lib/rdSender.ts:139) — wraps
  `invoke<RdCheckOutcome>('rd_check_pending', { torrentId, strategy })`.

---

#### `collectDownloadLinksFromRow(row: RdSendProgress): string[]` *(rdSender.ts:63)*

**Purpose**: The RD direct-download URLs that should land on the clipboard for one progress row.

**Contract**:
- Params: `row: RdSendProgress`.
- Returns: `string[]` — `[]` for any status other than `"completed"` (even if `links` is
  populated); otherwise `row.links.map(l => l.download)` in original order, dropping
  non-string / empty / whitespace-only values.
- Side effects: none. Errors: none. Async: no.

**Called by**:
- `App.svelte` `copyRdDownloads` (line 1126), `copyRdRow` (line 1146) and the per-row link list
  in markup (line 2741).
- `rdSender.test.ts`.

---

#### `sortCompletedRowsByCompletionTime<T extends { completed_at?: string }>(rows, missingCompletedAtFallback): T[]` *(rdSender.ts:77)*

**Purpose**: Stable ascending sort by `completed_at`.

**Contract**:
- Params: `rows: T[]`; `missingCompletedAtFallback: string` — REQUIRED sort key for rows
  without `completed_at`, so their position is always an explicit choice (`""` puts them before
  every timestamped row; App.svelte passes the batch start time).
- Returns: `T[]` — new array; equal keys keep input order (index tie-break). Plain string
  comparison, so keys must be ISO-8601.
- Side effects: none. Errors: none. Async: no.

**Called by**:
- `buildRdDisplayRows` (fallback `""`) — [rdSender.ts:112](app/src/lib/rdSender.ts:112)
- `App.svelte` `copyRdDownloads` (line 1121).
- `rdSender.test.ts`.

---

#### `buildRdDisplayRows(rows: RdSendProgress[]): RdSendProgress[]` *(rdSender.ts:103)*

**Purpose**: Display ordering for the RD progress table.

**Contract**:
- Returns: a new array — every non-`completed` row (pending / sending / in_pending / error) first,
  in original order, then the `completed` rows oldest-completion-first (via
  `sortCompletedRowsByCompletionTime(completed, "")`), so the row that just completed lands at the
  bottom and legacy rows without `completed_at` sit above timestamped ones.
- Display-only: send order, `handle_id` / `torrent_id` mapping and pending reconciliation keep
  using the source array. Input is not mutated.
- Side effects: none. Errors: none. Async: no.

**Called by**:
- `App.svelte` `rdDisplayRows` derived (line 1664).
- `rdSender.test.ts`.

---

#### `formatCompletedAt(iso: string | undefined): string` *(rdSender.ts:122)*

**Purpose**: Render `completed_at` for the progress table in the LOCAL time zone.

**Contract**:
- Returns: `"YYYY-MM-DD HH:mm:ss"` (zero-padded, local zone); `"—"` (em dash) when `iso` is
  absent or unparsable — never `"Invalid Date"`.
- Side effects: none (reads the host time zone). Errors: none. Async: no.

**Called by**:
- `App.svelte` progress table markup (line 2719), only for `completed` rows.
- `rdSender.test.ts`.

---

#### `sendBatch(items, onProgress, opts?): Promise<RdSendProgress[]>` *(rdSender.ts:149)*

**Purpose**: Send a list of magnet handles to Real-Debrid. Update each row to
`sending` → (`completed` | `in_pending` | `error`) and emit progress between awaits.

**Contract**:
- Params:
  - `items: RdSendItem[]` — each `{ handle_id, code, size_label? }`. `handle_id` is the
    sidecar handle; the others are display-only.
  - `onProgress: (ev: RdSendBatchEvent) => void` — fires TWICE per item: once when the row
    transitions to `sending` (before await), once when it settles. Event shape:
    `{ index: 1-based, total, item: RdSendProgress }`.
  - `opts?: RdSendBatchOptions`:
    - `signal?: AbortSignal` — checked before each item starts only (not mid-await — an
      in-flight `rd_send_magnet` runs to completion and its outcome IS recorded and emitted).
    - `defaults?: RdSendOptions` — `{ strategy?, min_size_mb?, cache_wait?, code?, size_label? }`;
      every call spreads `defaults` then sets `code` / `size_label` from the item, so the
      per-item values always win.
    - `fetcher?` — test seam (default = `defaultFetcher`).
    - `concurrency?: number` — default `1` (strictly sequential, in order). `>= 2` runs a pool of
      `min(concurrency, items.length)` workers pulling the next index; rows still land at their
      own index. App.svelte does not pass it (sequential).
- Returns: `Promise<RdSendProgress[]>` — final array (same length and order as `items`).
- Side effects: invokes `rd_send_magnet` once per started item.
- Errors: never throws (per-item errors are captured into `row.error_code`).
- Async: yes.

**Status transitions**:
- Initial: `{ handle_id, code, size_label, status: "pending", links: [], error_code: null }`.
- Before await: `status: "sending"`.
- After success with `outcome.status === "completed"`: `status: "completed"`,
  `links: outcome.links`, `error_code: null`, `completed_at: new Date().toISOString()`,
  `torrent_id: outcome.torrent_id`.
- After success with `outcome.status === "pending"`: `status: "in_pending"`, `links: []`,
  `error_code: null`, `torrent_id: outcome.torrent_id` (kept so a later retry can reconcile by
  torrent_id).
- After thrown error: `status: "error"`, `links: []`, `error_code: errText(e)`.

**Calls**:
- `@tauri-apps/api/core::invoke('rd_send_magnet', { handleId, options })` via `defaultFetcher`
  or the injected `fetcher`; `errText`.

**Called by**:
- `App.svelte` `runSendBatch` (line 1076) — search [App.svelte](app/src/App.svelte) for `sendBatch`.
- `rdSender.test.ts`.

---

#### `retryPending(entries, onProgress, opts?): Promise<void>` *(rdSender.ts:311)*

**Purpose**: Re-poll a list of persisted `PendingEntry` rows. Emit one event per entry with
the latest outcome — caller is responsible for rebuilding any in-memory list via a separate
`pending_list` invoke.

**Contract**:
- Params:
  - `entries: PendingEntry[]` — each carries `torrent_id` and `strategy` (the strategy the
    row was originally sent with).
  - `onProgress: (ev: RdRetryEvent) => void` — fires once per entry with
    `{ index: 1-based, total, torrent_id, entry, result }`, `result` discriminated on
    `result.kind`:
    - `"completed"` → `{ kind, links, name }`
    - `"pending"` → `{ kind, rd_status, progress, name }`
    - `"missing"` → `{ kind }`
    - `"error"` → `{ kind, error_code }`
  - `opts?: RdRetryOptions`:
    - `signal?: AbortSignal` — checked at top of each iteration.
    - `fetcher?` — default = `defaultCheckFetcher`.
- Returns: `Promise<void>` — resolves after every entry has been polled (or the signal aborts).
- Side effects: invokes `rd_check_pending` once per entry (Rust updates / removes the
  `pending_torrents.json` entry as a side effect).
- Errors: never throws (per-entry errors become `result: { kind: "error", error_code }`).
- Async: yes. Strictly sequential.

**Calls**:
- `@tauri-apps/api/core::invoke('rd_check_pending', { torrentId, strategy })` via
  `defaultCheckFetcher` or injected `fetcher`; `errText`.

**Called by**:
- `App.svelte` `retryAllPending` (line 1222) — search [App.svelte](app/src/App.svelte) for
  `retryPending`.
- `rdSender.test.ts`.

---

#### `applyRetryEventToProgressRows(rows, ev, completedAt?): RdSendProgress[]` *(rdSender.ts:269)*

**Purpose**: Reconcile one `RdRetryEvent` into the "send to RD" progress rows so a row that was
`in_pending` flips to its final state without a manual refresh.

**Contract**:
- Params: `rows: RdSendProgress[]`; `ev: RdRetryEvent`; `completedAt = new Date().toISOString()`
  (injectable for tests).
- Row lookup (private `findRetryProgressIndex`, [rdSender.ts:251](app/src/lib/rdSender.ts:251)):
  first a row with `torrent_id === ev.torrent_id`; otherwise, for legacy rows without
  `torrent_id`, the in_pending row whose `code === ev.entry.code` — but only when exactly ONE
  such row exists (never guesses between duplicates).
- Returns:
  - `kind: "completed"` → new array with that row set to `status: "completed"`,
    `links: ev.result.links`, `error_code: null`, `torrent_id`, and `completed_at` kept if
    already set (a repeat retry pass never rewrites the first-confirmed timestamp), else
    `completedAt`.
  - `kind: "missing"` → new array with that row set to `status: "error"`, `links: []`,
    `error_code: "rd_torrent_missing"`, `torrent_id` (existing `completed_at` is kept).
  - `"pending"` / `"error"` events, or no matching row → the SAME `rows` array (identity).
- Side effects: none (input not mutated). Errors: none. Async: no.

**Called by**:
- `App.svelte` `retryAllPending` `onProgress` (lines 1233, 1239).
- `rdSender.test.ts`.

---

#### `rdErrorMessage(code: string): string` *(rdSender.ts:358)*

**Purpose**: Map a Rust-side RD error code to a Traditional Chinese user-facing message. Pure;
unknown codes fall through to a generic `「（其他錯誤：${code}）」` so support can still see
the raw code.

**Contract**:
- Params: `code: string` — e.g. `"rd_no_token"`, `"rd_token_format_invalid"` (Rust
  `secret_store::RD_TOKEN_FORMAT_ERR`, from `rd_save_token` / `rd_test_token`),
  `"rd_token_invalid"`, `"rd_premium_required"`,
  `"rd_rate_limited"`, `"rd_magnet_error"`, `"rd_download_failed"`, `"rd_torrent_missing"`,
  `"rd_api_error"`, `"unknown_handle"`, `"rd_internal"`.
- Returns: `string` — zh-Hant message.
- Side effects: none.
- Errors: none.
- Async: no.

**Known codes & messages** (verbatim, [rdSender.ts:359-384](app/src/lib/rdSender.ts:359)):

| Code | Message |
|------|---------|
| `rd_no_token` | 尚未設定 Real-Debrid Token |
| `rd_token_format_invalid` | Real-Debrid Token 格式無效（僅限英數且長度 ≤ 255） |
| `rd_token_invalid` | Real-Debrid Token 無效或已過期 |
| `rd_premium_required` | 需要 Real-Debrid Premium 帳號 |
| `rd_rate_limited` | Real-Debrid 速率限制，請稍後再試 |
| `rd_magnet_error` | 磁力解析失敗（RD 無法處理此磁力） |
| `rd_download_failed` | Real-Debrid 下載失敗 |
| `rd_torrent_missing` | RD 上找不到此 torrent（可能已被刪除） |
| `rd_api_error` | Real-Debrid API 錯誤 |
| `unknown_handle` | 磁力 handle 過期，請重新擷取 |
| `rd_internal` | sidecar 內部錯誤 |
| _other_ | `（其他錯誤：${code}）` |

**Calls**: none.

**Called by**:
- `App.svelte` lines 885, 906, 910, 924, 940 (token test / save / clear / user refresh), 1285
  (pending-retry summary) and 2794 (progress-row error cell) — search
  [App.svelte](app/src/App.svelte) for `rdErrorMessage`.
- `rdSender.test.ts`.

---

#### Interfaces

- `RdSendOptions` [rdSender.ts:24-31](app/src/lib/rdSender.ts:24) — passed verbatim as
  `options` to `rd_send_magnet` (Rust `RdSendOptions`,
  [commands.rs:399](app/src-tauri/src/commands.rs:399)). `code` / `size_label` are display-only
  metadata that Rust persists to `pending_torrents.json` on a pending outcome.
- `RdSendItem` [rdSender.ts:33-39](app/src/lib/rdSender.ts:33) — one row of the batch
  (`handle_id` + display fields).
- `RdSendBatchEvent` [rdSender.ts:41-45](app/src/lib/rdSender.ts:41) — `{ index, total, item }`.
- `RdSendBatchOptions` [rdSender.ts:47-55](app/src/lib/rdSender.ts:47) — `signal`, `defaults`,
  `fetcher`, `concurrency`.
- `RdRetryEvent` [rdSender.ts:233-244](app/src/lib/rdSender.ts:233) — `index`, `total`,
  `torrent_id`, `entry: PendingEntry`, `result` discriminated by `result.kind`.
- `RdRetryOptions` [rdSender.ts:246-249](app/src/lib/rdSender.ts:246) — `signal`, `fetcher`.

---

### 3.7 `app/src/lib/settingsValidation.ts`

Pure validators. Every validator returns `null` on success, or a zh-Hant error string on
failure. No Tauri, no DOM. Rust clamps the RD numerics on read and write (`clamp_rd_settings`,
[settings.rs:78](app/src-tauri/src/settings.rs:78)) and blanks `api_token` (`without_secrets`);
this is the early gate that drives `Save` button enablement + inline messages before a value
would be silently clamped.

Module-level constants:
- `FILE_PICK_VALUES = ["smart", "largest", "video", "all"] as const` —
  [settingsValidation.ts:15](app/src/lib/settingsValidation.ts:15). Type alias
  `FilePickValue = (typeof FILE_PICK_VALUES)[number]`.
- `THEME_VALUES = ["light", "dark"] as const` —
  [settingsValidation.ts:18](app/src/lib/settingsValidation.ts:18). Type alias `ThemeValue`.
- `SCALE_PRESETS = ["auto", "1.0", "1.25", "1.5", "1.75", "2.0", "2.5", "3.0"] as const` —
  [settingsValidation.ts:21-30](app/src/lib/settingsValidation.ts:21). UI dropdown options.
- Private: `SCALE_MIN = 0.5`, `SCALE_MAX = 3` —
  [settingsValidation.ts:32-33](app/src/lib/settingsValidation.ts:32).
- `MAX_MIN_SIZE_MB = 1_000_000` — [settingsValidation.ts:34](app/src/lib/settingsValidation.ts:34).
  Ceiling for `rd.min_size_mb`; same value as Rust `clamp_rd_settings` and sidecar
  `MAX_RD_MIN_SIZE_MB`. `App.svelte`'s min-size `<input>` carries the matching `max="1000000"`.

---

#### `validateMinSizeMb(value: number): string | null` *(settingsValidation.ts:37)*

**Purpose**: Integer check for `rd.min_size_mb` within `[0, MAX_MIN_SIZE_MB]` (1,000,000 — the
same ceiling as Rust `clamp_rd_settings` and sidecar `MAX_RD_MIN_SIZE_MB`), so the UI reports an
out-of-range value instead of letting the backend clamp it silently.

**Contract**:
- Params: `value: number`.
- Returns: `null` if integer in `[0, 1_000_000]`, else `「必須是數字」`/`「必須是整數」`/`「不能為負」`/`「最大為 1,000,000 MB」`.
- Side effects: none. Errors: none. Async: no.

**Calls**: `Number.isFinite`, `Number.isInteger`.

**Called by**: `validateSettingsDraft`, `settingsValidation.test.ts`.

---

#### `validateCacheWaitSeconds(value: number): string | null` *(settingsValidation.ts:54)*

**Purpose**: Integer in `[5, 300]` check for `rd.cache_wait_seconds`.

**Contract**: Same `「必須是數字」` / `「必須是整數」` checks as `validateMinSizeMb`, then
`「最小為 5 秒（避免 RD 端尚未判定快取就放棄）」` when `< 5` and
`「最大為 300 秒（避免單一磁力長時間鎖住 sidecar）」` when `> 300`. The bounds mirror Rust
`MIN_RD_CACHE_WAIT_SECS` / `MAX_RD_CACHE_WAIT_SECS`
([sidecar_manager.rs:47-53](app/src-tauri/src/sidecar_manager.rs:47)): the sidecar request
timeout for `rd_send_magnet` is `cache_wait + 90s`, and Rust rejects a value outside `[5, 300]`.

**Calls**: `Number.isFinite`, `Number.isInteger`.

**Called by**: `validateSettingsDraft`, `settingsValidation.test.ts`.

---

#### `validateScale(value: string): string | null` *(settingsValidation.ts:63)*

**Purpose**: Validate `ui.scale` — must be `"auto"` (literal) OR a decimal in `[0.5, 3.0]`.

**Contract**:
- Params: `value: string`. Non-string → `「必須是字串」` (runtime defensive — TS forbids it).
- Returns: `null` if `"auto"` (after trim) or a plain decimal in `[SCALE_MIN, SCALE_MAX]`.
- Empty trimmed → `「不能為空」`. Anything not matching `/^\d+(\.\d+)?$/` (signs, exponents,
  `"1."`, …) or a non-finite parse → `「必須是 auto 或 0.5–3.0 之間的數字」`.
- Out of range → `` `必須在 ${SCALE_MIN}–${SCALE_MAX} 之間` `` = `「必須在 0.5–3 之間」`.
- Side effects: none. Errors: none. Async: no.

**Calls**: `String.prototype.trim`, `RegExp.prototype.test`, `Number.parseFloat`, `Number.isFinite`.

**Called by**: `validateSettingsDraft`, `settingsValidation.test.ts`.

---

#### `validateFilePick(value: string): string | null` *(settingsValidation.ts:80)*

**Purpose**: Membership check against `FILE_PICK_VALUES`.

**Contract**: Returns null on hit, else `「必須是 smart / largest / video / all 之一」` (joined
from the tuple).

**Calls**: `Array.prototype.includes`.

**Called by**: `validateSettingsDraft`, `settingsValidation.test.ts`.

---

#### `validateTheme(value: string): string | null` *(settingsValidation.ts:88)*

**Purpose**: Membership check against `THEME_VALUES`.

**Contract**: null on hit, else `「必須是 light / dark 之一」` (joined from the tuple).

**Calls**: `Array.prototype.includes`.

**Called by**: `validateSettingsDraft`, `settingsValidation.test.ts`.

---

#### `validateSettingsDraft(draft: Settings): Record<string, string>` *(settingsValidation.ts:104)*

**Purpose**: Aggregate every per-field validator into a `field-id → error-message` map. Empty
map means the draft is valid.

**Contract**:
- Params: `draft: Settings` — the full editor state.
- Returns: `Record<string, string>` — keys are stable UI ids: `"rd.file_pick"`,
  `"rd.min_size_mb"`, `"rd.cache_wait_seconds"`, `"ui.theme"`,
  `"ui.scale"`. Missing key = that field is valid.
- Note: `rd.api_token` is **not** validated here (the field is intentionally write-only and
  may be empty meaning "leave as-is"; the Rust side handles its semantics).
- Side effects: none. Errors: none. Async: no.

**Calls**: `validateFilePick`, `validateMinSizeMb`, `validateCacheWaitSeconds`,
`validateTheme`, `validateScale`.

**Called by**:
- `App.svelte` line 1506 (`settingsErrors` derived, controlling the Save button) — search
  [App.svelte](app/src/App.svelte) for `validateSettingsDraft`.
- `settingsValidation.test.ts`.

---

### 3.8 `app/src/lib/types.ts` — runtime exports

The only runtime export is `defaultFilterState` — already documented in §2.4. Everything else
in `types.ts` is erased at compile time.

---

### 3.9 `app/src/lib/errText.ts`

#### `errText(e: unknown): string` *(errText.ts:5)*

**Purpose**: The `e instanceof Error ? e.message : String(e)` idiom, factored out of every
`catch (e)` site that surfaces an error to the UI.

**Contract**:
- Params: `e` — anything a `catch` can bind.
- Returns: `e.message` for `Error` instances, `String(e)` otherwise. Never throws.
- Side effects: none. No imports at all — like `types.ts`, a lib module with zero dependencies.

**Why it matters**: Tauri rejects `invoke()` with a plain `String`, not an `Error`. Both shapes
therefore reach the same `catch`, and a bare `e.message` would render `undefined` for the Rust
side while `String(e)` would render `Error: …` noise for the JS side.

**Called by**: `scraper.ts` (`fetchGroupWithRetry`), `rdSender.ts` (`sendBatch`, `retryPending`),
and `App.svelte` at every `invoke` call site.

---

### 3.10 `app/src/lib/flashAction.ts`

Reactive controller behind every button's transient "✓" confirmation.

#### `interface FlashController` *(flashAction.ts:15-27)*

- `readonly keys: SvelteSet<string>` — reactive set of currently-flashing keys; templates call
  `.has(key)`.
- `flash(key, durationMs = 1200): void` — default is the private `DEFAULT_DURATION_MS = 1200`
  ([flashAction.ts:13](app/src/lib/flashAction.ts:13)).
- `run<T>(key, fn, durationMs?): Promise<T>`
- `dispose(): void`

#### `createFlashController(): FlashController` *(flashAction.ts:29)*

**Contract**:
- `flash` **restarts** an in-flight timer for the same key rather than letting the original
  expiry truncate the new flash — a rapid re-click debounces instead of blinking out early.
- `run` flashes **only on resolve**; a rejection re-throws unchanged with no flash. This is the
  load-bearing part: without it the UI would show "✓ 已複製" for an `invoke` that actually failed.
- `dispose` clears every pending timer and empties the set. `App.svelte` calls it from
  `onDestroy`; skipping it would leave `setTimeout` callbacks writing into a destroyed component.
- Uses `SvelteSet` from `svelte/reactivity` (not a plain `Set`) so mutation is tracked by Svelte 5
  runes — a plain `Set` would mutate without re-rendering.

**Called by**: `App.svelte` line 1116 — one shared controller instance, keyed per button
(`magnet-copy-selected`, `rd-bulk`, `scrape-clear`, `rd-clear-token`, …). App.svelte uses only
`flash(…)`, `keys.has(…)` and `dispose()` today; `run` is exercised by `flashAction.test.ts` only.

---

## 4. Cross-cutting concerns

### 4.1 Error handling pattern

- **Validators** (`settingsValidation.ts`) use a "Result-lite" pattern: return `null` or a
  human-readable string. Never throw.
- **Batch drivers** (`scraper.ts`, `rdSender.ts`) **never reject** the outer promise for per-item
  failures. Per-item
  errors are caught inside the loop and attached to the per-item state object
  (`group.error` / `row.error_code`). The caller's only failure mode is its own
  `onProgress` callback throwing — that propagates.
- **Pure helpers** (`magnetUtils.ts`, `rdPriority.ts`) never throw; bad input collapses to safe
  defaults (`parseSizeGb("") → 0`, `parseFileCount("") → 999`, `pickRdCandidate([]) → null`,
  `rdDateKey` on a blank date → the `"9999-99-99"` sentinel). The only `throw` is `earliestBy`'s
  empty-input guard, which the exported API cannot reach.
- **Tauri `invoke`** rejects with the Rust-side error string. `scrapeBatch` (inside
  `fetchGroupWithRetry`), `sendBatch` and `retryPending` all extract it via `errText(e)`
  (`e instanceof Error ? e.message : String(e)`). For RD, the result is
  fed into `rdErrorMessage` at the UI layer for translation.

### 4.2 State management

- **No Svelte stores in `lib/*`.** The lib modules are function libraries; the only state is
  `scraper.ts`'s module-level `nextScrapeBatchId` counter and the per-instance `SvelteSet` +
  timer map that each `createFlashController()` closes over.
- **Per-call state** lives in the array passed back via `onProgress` (e.g. `RdSendProgress[]`
  for sendBatch; `ScrapedGroup[]` for scrapeBatch). Between awaits `sendBatch` replaces
  `rows[i]` with a new object and `scrapeBatch` mutates the group object in place, then the row
  is re-emitted to the caller — the caller is responsible for
  any reactive state binding (Svelte `$state` in App.svelte).
- **Abort cancellation** is propagated via standard `AbortSignal` — checked at iteration
  boundaries; an in-flight invoke is allowed to run to completion. `scrapeBatch` then discards
  that result (group reset to `pending`, no `onProgress`), whereas `sendBatch` / `retryPending`
  still record and emit the in-flight item's outcome and stop before the next one.
- **No `localStorage` writes anywhere in `lib/*`** — persistence is delegated to Rust
  (`write_settings`, `pending_torrents.json`, etc.).

### 4.3 How does the frontend learn about backend events?

- **It polls.** No `listen('event-name', …)` subscriptions exist in any `lib/*` module. The
  pattern is uniformly:
  1. Caller invokes a Rust command (`fetch_javdb`, `rd_send_magnet`, `rd_check_pending`).
  2. Rust runs synchronously (from the WebView's POV — the actual sidecar work may be async
     internally, but the command resolves only when settled).
  3. Frontend awaits in a sequential loop and emits progress between iterations.
- App.svelte registers no `listen(...)` calls either (it does not import
  `@tauri-apps/api/event`).
- The `signal: AbortSignal` pattern is how the UI requests cancellation; there is no
  backend-initiated event push into the lib layer.

### 4.4 Test-injection pattern

All three batch drivers expose an injectable `fetcher` (and `scrapeBatch` also injects
`sleep`; `randomDelayMs` takes an injectable `rng`; `applyRetryEventToProgressRows` takes an
injectable `completedAt`) so that unit tests can run without a Tauri runtime. The default fetcher is a closed-over
arrow function that calls `invoke(...)` — production code paths do not see the seam, and the
seams have no side effect other than the `invoke` call itself.
