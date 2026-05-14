# Frontend Library Contracts (`app/src/lib/*` + `app/src/main.ts`)

Reference for refactoring on `codex/function-contracts-analysis`. Every exported and non-exported function in
the Svelte+TypeScript frontend library modules is documented with its contract and call trace.

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
| [lib/scraper.ts](app/src/lib/scraper.ts) | Batch driver for the JavDB scrape flow. Wraps `invoke('fetch_javdb', …)` with pacing + single-retry on rate limit. Also exposes textarea parsers. |
| [lib/rdSender.ts](app/src/lib/rdSender.ts) | Batch driver for Real-Debrid send + pending re-poll. Wraps `invoke('rd_send_magnet', …)` and `invoke('rd_check_pending', …)`. Includes the zh-Hant error-code → message mapper. |
| [lib/settingsValidation.ts](app/src/lib/settingsValidation.ts) | Pure validators for the Settings editor. Returns null-or-error-string per field; aggregates into a map for the whole draft. |
| [vite-env.d.ts](app/src/vite-env.d.ts) | Ambient triple-slash references for Svelte + Vite client types. No runtime, no exports. |

### 1.2 Internal dependency graph

```
main.ts ──► App.svelte (not in scope)

App.svelte ──► lib/scraper.ts ──► lib/types.ts
            ──► lib/magnetUtils.ts ──► lib/types.ts
            ──► lib/rdSender.ts ──► lib/types.ts
            ──► lib/settingsValidation.ts ──► lib/types.ts
            ──► lib/types.ts (direct)
```

No lib module imports another lib module — `types.ts` is the only shared dependency, and
nothing imports it cyclically. Each lib file is a leaf that pairs with `types.ts`.

### 1.3 Public API surface

| Module | Runtime exports | Type-only exports |
|--------|-----------------|-------------------|
| `magnetUtils.ts` | `parseSizeGb`, `parseFileCount`, `matchesKeyword`, `isHd`, `filterRows`, `applyGroupPick`, `sortRows`, `processGroupRows`, `dedupeByHandleId` | — |
| `scraper.ts` | `isRateLimitError`, `randomDelayMs`, `parseUrlBatch`, `parseMagnetBatch`, `scrapeBatch` | `SleepFn`, `ScrapeProgressEvent`, `ScrapeOptions` |
| `rdSender.ts` | `sendBatch`, `retryPending`, `rdErrorMessage` | `RdSendOptions`, `RdSendItem`, `RdSendBatchEvent`, `RdSendBatchOptions`, `RdRetryEvent`, `RdRetryOptions` |
| `settingsValidation.ts` | `FILE_PICK_VALUES`, `THEME_VALUES`, `SCALE_PRESETS`, `validateMinSizeMb`, `validateCacheWaitSeconds`, `validateWaitTimeoutSeconds`, `validateScale`, `validateFilePick`, `validateTheme`, `validateSettingsDraft` | `FilePickValue`, `ThemeValue` |
| `types.ts` | `defaultFilterState` | `Theme`, `PathInfo`, `UiSettings`, `RdSettings`, `Settings`, `MagnetRow`, `FetchResult`, `PingResponse`, `CopyBulkResult`, `CopyRdLinksBulkResult`, `LegacyImportPreview`, `CookiesStatus`, `LegacyImportReport`, `ScrapedGroup`, `GroupPick`, `FilterState`, `SortColumn`, `SortDirection`, `SortState`, `RdUserInfo`, `RdLink`, `RdSendOutcome`, `RdCheckOutcome`, `PendingEntry`, `RdSendProgress` |

### 1.4 Bridge to Rust

#### Tauri `invoke` calls in `lib/*`

Only two `invoke` call sites live inside `lib/*`. Every other backend call originates from
`App.svelte`.

| Command name | File:line | Payload | Return type | Wrapper function |
|--------------|-----------|---------|-------------|------------------|
| `fetch_javdb` | [scraper.ts:65](app/src/lib/scraper.ts:65) | `{ url: string }` | `FetchResult` | `defaultFetcher` (private) used by `scrapeBatch` |
| `rd_send_magnet` | [rdSender.ts:58](app/src/lib/rdSender.ts:58) | `{ handleId: string, options: RdSendOptions }` | `RdSendOutcome` | `defaultFetcher` (private) used by `sendBatch` |
| `rd_check_pending` | [rdSender.ts:64](app/src/lib/rdSender.ts:64) | `{ torrentId: string, strategy?: string }` | `RdCheckOutcome` | `defaultCheckFetcher` (private) used by `retryPending` |

Both wrappers are exposed as injectable seams via the `fetcher` option, so tests stub them
without monkey-patching `@tauri-apps/api/core`.

#### Tauri event subscriptions in `lib/*`

**None.** No `listen('event-name', …)` calls exist in any `lib/*` module. The frontend currently
learns about backend progress purely by awaiting `invoke` calls in a loop and surfacing results
through caller-supplied `onProgress` callbacks. (App.svelte may register event listeners
separately — out of scope here.)

#### Other external APIs used in `lib/*`

- `setTimeout` (via [scraper.ts:43](app/src/lib/scraper.ts:43) `realSleep`).
- `Math.random` (via [scraper.ts:37](app/src/lib/scraper.ts:37) `randomDelayMs`).
- `Date.prototype.toISOString` (via [scraper.ts:166](app/src/lib/scraper.ts:166)).
- `String.prototype.localeCompare` (via [magnetUtils.ts:133-138](app/src/lib/magnetUtils.ts:133)).
- No `fetch`, no `crypto.subtle`, no `navigator.clipboard`, no `localStorage` in `lib/*`.

---

## 2. Types (`app/src/lib/types.ts`)

`types.ts` is mostly compile-time declarations. The one runtime export is `defaultFilterState`,
documented below in §3.7. The rest are interfaces / unions / aliases. Where a Rust struct
clearly mirrors a shape, the parallel is called out — names use snake_case on both sides because
the Rust side serializes via `serde` with default field naming.

### 2.1 UI-side primitives

#### `type Theme = "light" | "dark"` *(types.ts:10)*
String literal union; the only legal values for the `data-theme` HTML attribute. Mirrored by
the Rust `Settings::ui.theme` field.

#### `interface PathInfo` *(types.ts:12-15)*
- `data_dir: string` — absolute path the sidecar writes its JSON state files into.
- `log_dir: string` — absolute path of the rolling log directory.

Mirrors the Rust `PathInfo` struct returned by the `paths` invoke (called from App.svelte).

#### `interface UiSettings` *(types.ts:17-20)*
- `theme: Theme`
- `scale: string` — either the literal `"auto"` or a decimal 0.5–3.0 (rendered to CSS `zoom`).

Mirrors Rust `UiSettings`.

#### `interface RdSettings` *(types.ts:22-28)*
- `api_token: string` — write-only from the frontend perspective; Rust returns `""` here (the
  on-disk file uses an encrypted store; the WebView never sees plaintext on read-back).
- `file_pick: string` — one of `FILE_PICK_VALUES`.
- `min_size_mb: number`, `cache_wait_seconds: number`, `wait_timeout_seconds: number`.

Mirrors Rust `RdSettings`. Validation rules: see [settingsValidation.ts](app/src/lib/settingsValidation.ts).

#### `interface Settings` *(types.ts:30-34)*
- `version: number`
- `ui: UiSettings`
- `rd: RdSettings`

Mirrors Rust `Settings` (the same shape `read_settings` returns and `save_settings` accepts).

### 2.2 Magnet payloads from the sidecar

#### `interface MagnetRow` *(types.ts:36-43)*
- `handle_id: string` — sidecar-assigned opaque key. The frontend never sees the full magnet
  URI; this id is the only handle for "send to RD" / "copy magnet".
- `name: string`, `size: string` (e.g. `"5.67GB, 5個文件"`), `tags: string[]`, `date: string`.
- `magnet_redacted: string` — display-only string with the btih portion truncated.

#### `interface FetchResult` *(types.ts:45-52)*
- `engine: string` (e.g. `"curl_cffi"`)
- `url: string` — the JavDB URL.
- `code: string` — JavDB code (e.g. `"SNOS-192"`).
- `title: string`
- `magnet_count: number`
- `magnets: MagnetRow[]`

Mirrors Rust `FetchResult`; produced by `fetch_javdb`.

#### `interface ScrapedGroup` *(types.ts:122-129)*
- `url: string`
- `status: "pending" | "fetching" | "ok" | "error"`
- `result: FetchResult | null`
- `error: string | null`
- `finished_at: string | null` — ISO 8601.

Frontend-only aggregator (not a Rust shape). `error` and `result` are *mutually exclusive in
practice* but stored independently so a future retry affordance can replace `error` in place.

### 2.3 Other backend payloads

#### `interface PingResponse` *(types.ts:54-58)*
- `ok: boolean`, `request_id: string`, `uptime_seconds: number`. Returned by the `ping` invoke.

#### `interface CopyBulkResult` *(types.ts:60-63)*
- `copied: number`, `unknown: number`. Returned by `copy_magnets_bulk`.

#### `interface CopyRdLinksBulkResult` *(types.ts:65-68)*
- `copied: number`. Returned by `copy_rd_links_bulk`.

#### `interface LegacyImportPreview` *(types.ts:78-90)*
M7a-lite. Returned by `preview_legacy_import`. Reports only counts, key NAMES, and source
paths — never the actual env values or token. Fields:
- `source_dir: string`, `source_dir_valid: boolean`
- `env_present`, `cookies_present`, `pending_present` (booleans)
- `env_settings_keys: string[]` — non-secret keys discovered in legacy `.env`.
- `has_rd_token: boolean` — true if `RD_API_TOKEN` is non-empty, but the value is **not**
  exposed.
- `pending_count: number`
- `warnings: string[]`

#### `interface CookiesStatus` *(types.ts:98-103)*
M7b. JavDB cookies file health: `present`, `path`, `modified_iso` (or `null`), `size_bytes`.
The cookie BODY is never returned — Rust reads only `metadata()`.

#### `interface LegacyImportReport` *(types.ts:105-113)*
Returned by `apply_legacy_import`. Reports what happened (`env_imported`, `rd_token_imported`,
`cookies_imported`, `pending_imported`, `pending_skipped`), the `sources` (list of paths read
from), and any `warnings`.

### 2.4 Filter / sort / grouping

#### `type GroupPick = "all" | "largest" | "smallest" | "fewest_files"` *(types.ts:131)*
Strategy for the "keep N per group" filter step. Semantics implemented in `applyGroupPick`.

#### `interface FilterState` *(types.ts:133-141)*
- `keyword: string`
- `hd_only: boolean`
- `min_size_gb: number | null` — null OR 0 means no lower bound.
- `max_size_gb: number | null` — null means no upper bound (0 is also treated as "no bound";
  see [magnetUtils.ts:64](app/src/lib/magnetUtils.ts:64)).
- `group_pick: GroupPick`

#### `defaultFilterState(): FilterState` *(types.ts:143-149)*
**Runtime export.** Arrow-function factory returning the initial filter state.

- Params: none.
- Returns: a fresh `FilterState` with `keyword=""`, `hd_only=false`, `min_size_gb=null`,
  `max_size_gb=null`, `group_pick="all"`.
- Side effects: none.
- Errors: none.
- Async: no.

**Calls**: none.

**Called by**:
- `App.svelte` line 71 (initial filter state) and line 434 (reset action) — search
  [App.svelte](app/src/App.svelte) for `defaultFilterState`.
- `magnetUtils.test.ts` (line 13) and `settingsValidation.test.ts` use it indirectly via the
  `draft()` helper.

#### `type SortColumn = "code" | "size" | "tags" | "date" | "name"` *(types.ts:151)*
Note: `"code"` and `"name"` are sorted identically (both compare `row.name`) — see
[magnetUtils.ts:132](app/src/lib/magnetUtils.ts:132).

#### `type SortDirection = "asc" | "desc"` *(types.ts:152)*

#### `interface SortState` *(types.ts:154-157)*
- `column: SortColumn | null` (null = unsorted, preserve input order)
- `direction: SortDirection`

### 2.5 Real-Debrid types

#### `interface RdUserInfo` *(types.ts:163-168)*
RD account snapshot: `username`, `type` ("premium"/"free"), `expiration`, `points`. Returned
by `rd_test_token` / `rd_user_info`.

#### `interface RdLink` *(types.ts:170-176)*
- `original: string` — RD-side URL for the file.
- `download: string` — direct download URL.
- `filename: string`, `filesize: number`, `streamable: number` (0/1).

#### `type RdSendOutcome` *(types.ts:179-192)*
Discriminated union on `status`. Result of `rd_send_magnet`.
- `{ status: "completed"; torrent_id; name; links: RdLink[] }`
- `{ status: "pending"; torrent_id; name; rd_status: string; progress: number }`

Errors come back as thrown strings (Rust `String` codes) — see §3.4 `rdErrorMessage` for the
known catalogue.

#### `type RdCheckOutcome` *(types.ts:195-212)*
Discriminated union on `status`. Result of `rd_check_pending`.
- `{ status: "completed"; torrent_id; name; links: RdLink[] }`
- `{ status: "pending"; torrent_id; name; rd_status; progress }`
- `{ status: "missing"; torrent_id }` — RD no longer has the torrent.

#### `interface PendingEntry` *(types.ts:215-225)*
Persisted on disk (`pending_torrents.json`). Mirrors Rust `PendingEntry`.
- `torrent_id`, `code`, `name`, `size_label`, `strategy`, `added_at`, `last_progress`,
  `last_rd_status`, `last_checked_at: string | null`.

#### `interface RdSendProgress` *(types.ts:228-242)*
Per-row state in the UI's "send to RD" progress panel.
- `handle_id`, `code`
- `status: "pending" | "sending" | "completed" | "in_pending" | "error"`
- `links: RdLink[]`, `error_code: string | null`
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

No functions to contract beyond this. Consumers: the Vite/Tauri bundler only.

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

---

#### `parseSizeGb(size: string): number` *(magnetUtils.ts:15)*

**Purpose**: Parse the size label (e.g. `"5.67GB, 5個文件"`) into a GB-numeric value.

**Contract**:
- Params: `size: string` — the human-readable size column from `MagnetRow.size`. Empty string
  treated as 0.
- Returns: `number` — GB value. `"512MB, …"` → `512/1024`. Falsy / unparseable → `0`.
- Side effects: none.
- Errors: none thrown; bad input collapses to `0`.
- Async: no.

**Calls**:
- `String.prototype.match` (regex `([\d.]+)\s*GB/i`, `([\d.]+)\s*MB/i`).
- `parseFloat`.

**Called by**:
- `filterRows` — [magnetUtils.ts:62-65](app/src/lib/magnetUtils.ts:62)
- `applyGroupPick` — [magnetUtils.ts:91, 98, 109](app/src/lib/magnetUtils.ts:91)
- `sortRows` — [magnetUtils.ts:131](app/src/lib/magnetUtils.ts:131)
- `magnetUtils.test.ts` (direct unit tests).

---

#### `parseFileCount(size: string): number` *(magnetUtils.ts:25)*

**Purpose**: Parse the file-count portion of the size label (`"… 5個文件"`).

**Contract**:
- Params: `size: string` — same input as `parseSizeGb`.
- Returns: `number` — file count. Empty input → `999`. Match-fail → `999` (sentinel for "very
  many files, deprioritize"; matches the Python reference implementation).
- Side effects: none.
- Errors: none.
- Async: no.

**Calls**:
- `String.prototype.match` (regex `(\d+)\s*個文件`), `parseInt`.

**Called by**:
- `applyGroupPick` (`fewest_files` branch) — [magnetUtils.ts:105-106](app/src/lib/magnetUtils.ts:105)
- `magnetUtils.test.ts`.

---

#### `matchesKeyword(row: MagnetRow, keyword: string): boolean` *(magnetUtils.ts:32)*

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
- `filterRows` — [magnetUtils.ts:59](app/src/lib/magnetUtils.ts:59)
- `magnetUtils.test.ts`.

---

#### `isHd(row: MagnetRow): boolean` *(magnetUtils.ts:44)*

**Purpose**: True if the row carries the JavDB `"高清"` tag (or lowercase `"hd"`).

**Contract**:
- Params: `row: MagnetRow`.
- Returns: `boolean`.
- Side effects: none.
- Errors: none.
- Async: no.

**Calls**:
- `Array.prototype.some`, `String.prototype.toLowerCase`.

**Called by**:
- `filterRows` — [magnetUtils.ts:60](app/src/lib/magnetUtils.ts:60)
- `magnetUtils.test.ts`.

---

#### `filterRows(rows: MagnetRow[], filter: FilterState): MagnetRow[]` *(magnetUtils.ts:54)*

**Purpose**: Apply non-grouping filters (keyword + hd_only + size range).

**Contract**:
- Params:
  - `rows: MagnetRow[]` — source list.
  - `filter: FilterState` — see [types.ts:133](app/src/lib/types.ts:133). `min_size_gb`/`max_size_gb`
    skip when null OR `<= 0`.
- Returns: `MagnetRow[]` — a NEW array; never mutates input.
- Side effects: none.
- Errors: none.
- Async: no.

**Calls**:
- `matchesKeyword`, `isHd`, `parseSizeGb`, `Array.prototype.filter`.

**Called by**:
- `processGroupRows` — [magnetUtils.ts:154](app/src/lib/magnetUtils.ts:154)
- `magnetUtils.test.ts`.

---

#### `applyGroupPick(rows: MagnetRow[], pick: GroupPick): MagnetRow[]` *(magnetUtils.ts:81)*

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
    - Anything else → pass-through copy (defensive fallback).
- Returns: `MagnetRow[]` — always a new array. Single-element except in `"all"` mode or empty
  input.
- Side effects: none.
- Errors: none.
- Async: no.

**Calls**:
- `Array.prototype.slice`, `Array.prototype.reduce`, `parseSizeGb`, `parseFileCount`.

**Called by**:
- `processGroupRows` — [magnetUtils.ts:155](app/src/lib/magnetUtils.ts:155)
- `magnetUtils.test.ts`.

---

#### `sortRows(rows, column, direction): MagnetRow[]` *(magnetUtils.ts:121)*

**Purpose**: Sort by one of `code`/`size`/`tags`/`date`/`name`. Stable (WebView2 Array.sort is
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

**Notes**: `"code"` and `"name"` compare on `row.name` (not on a separate `code` field —
`MagnetRow` doesn't have one).

**Calls**:
- `Array.prototype.slice`, `Array.prototype.sort`, `parseSizeGb`,
  `String.prototype.localeCompare`, `Array.prototype.join`.

**Called by**:
- `processGroupRows` — [magnetUtils.ts:156](app/src/lib/magnetUtils.ts:156)
- `magnetUtils.test.ts`.

---

#### `processGroupRows(group, filter, sortColumn, sortDirection): MagnetRow[]` *(magnetUtils.ts:147)*

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

**Calls**:
- `filterRows`, `applyGroupPick`, `sortRows`.

**Called by**:
- `App.svelte` line 402 (per-group derived rows) — search [App.svelte](app/src/App.svelte) for
  `processGroupRows`.
- `magnetUtils.test.ts`.

---

#### `dedupeByHandleId<T extends { handle_id: string }>(rows: T[]): T[]` *(magnetUtils.ts:169)*

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
- `App.svelte` line 595 (deduplicating the selection before RD send / bulk copy) — search
  [App.svelte](app/src/App.svelte) for `dedupeByHandleId`.
- `magnetUtils.test.ts`.

---

### 3.4 `app/src/lib/scraper.ts`

Batch driver for `fetch_javdb`. Sequential, paced, single-retry on rate-limit-flavored errors.

Module-level constants ([scraper.ts:14-24](app/src/lib/scraper.ts:14)):
- `DELAY_MIN_MS = 3000`, `DELAY_MAX_MS = 6000` — between-request jitter range.
- `RETRY_WAIT_MIN_MS = 10000`, `RETRY_WAIT_MAX_MS = 15000` — back-off range after a 429.
- `RATE_LIMIT_PATTERNS` — regex array (`\b429\b`, `rate-limit`, `cloudflare`, `too many requests`).

Module-level private values:
- `realSleep: SleepFn` at [scraper.ts:42](app/src/lib/scraper.ts:42) — `setTimeout`-based.
- `defaultFetcher` at [scraper.ts:64](app/src/lib/scraper.ts:64) — wraps the `fetch_javdb` invoke.

---

#### `isRateLimitError(message: string): boolean` *(scraper.ts:26)*

**Purpose**: Decide whether an error message looks like a rate-limit (so `scrapeBatch` should
back off and retry once).

**Contract**:
- Params: `message: string` — `error.message` or `String(error)`.
- Returns: `boolean` — true iff any pattern in `RATE_LIMIT_PATTERNS` matches. Empty string →
  `false`.
- Side effects: none.
- Errors: none.
- Async: no.

**Calls**:
- `Array.prototype.some`, `RegExp.test`.

**Called by**:
- `scrapeBatch` — [scraper.ts:155](app/src/lib/scraper.ts:155)
- `scraper.test.ts`.

---

#### `randomDelayMs(min: number, max: number): number` *(scraper.ts:35)*

**Purpose**: Random integer in `[min, max]` inclusive. Used for both jitter between requests
and back-off after rate limits.

**Contract**:
- Params: `min: number`, `max: number`. If `max <= min`, returns `min` (defensive — tests use
  `[0, 0]` to disable pacing).
- Returns: `number` — integer.
- Side effects: none.
- Errors: none.
- Async: no.

**Calls**:
- `Math.random`, `Math.floor`.

**Called by**:
- `scrapeBatch` (twice) — [scraper.ts:137, 156](app/src/lib/scraper.ts:137)
- `scraper.test.ts`.

---

#### `type SleepFn = (ms: number) => Promise<void>` *(scraper.ts:40)*

Type alias for the test-injectable sleep function.

---

#### `parseUrlBatch(raw: string): string[]` *(scraper.ts:72)*

**Purpose**: Normalize a multi-line textarea into a deduped, trimmed list of HTTP(S) URLs.

**Contract**:
- Params: `raw: string` — textarea contents (may contain `\r\n` or `\n`). Falsy → `[]`.
- Returns: `string[]` — order-preserving dedupe; drops blank lines, `#`-prefixed comment lines,
  and any line not starting with `http://` or `https://` (case-insensitive).
- Side effects: none.
- Errors: none.
- Async: no.

**Calls**:
- `String.prototype.split` (`/\r?\n/`), `trim`, `startsWith`, regex test, `Set`.

**Called by**:
- `App.svelte` line 220 (scrape button handler) — search [App.svelte](app/src/App.svelte) for
  `parseUrlBatch`.
- `scraper.test.ts`.

---

#### `parseMagnetBatch(raw: string): string[]` *(scraper.ts:94)*

**Purpose**: Normalize a "paste magnets directly" textarea into a deduped list of `magnet:` URIs.

**Contract**:
- Params: `raw: string`. Falsy → `[]`.
- Returns: `string[]` — order-preserving dedupe; drops blanks, `#`-comments, anything not
  matching `^magnet:`.
- Side effects: none. (Sidecar dedupes again on its side; this is mainly UX.)
- Errors: none.
- Async: no.

**Calls**:
- Same primitives as `parseUrlBatch`.

**Called by**:
- `App.svelte` line 267 (register-pasted-magnets handler) — search [App.svelte](app/src/App.svelte)
  for `parseMagnetBatch`.
- `scraper.test.ts`.

---

#### `scrapeBatch(urls, onProgress, opts?): Promise<ScrapedGroup[]>` *(scraper.ts:114)*

**Purpose**: Drive the JavDB batch scrape. Calls `fetch_javdb` once per URL, paced and with a
single retry on rate-limit-flavored errors.

**Contract**:
- Params:
  - `urls: string[]` — caller is expected to have already passed input through `parseUrlBatch`.
  - `onProgress: (ev: ScrapeProgressEvent) => void` — fires AFTER each group settles (ok or
    error). Receives `{ index: 1-based, total, group }`.
  - `opts?: ScrapeOptions`:
    - `signal?: AbortSignal` — checked at top of each iteration and after each sleep; once
      aborted, the loop breaks and returns the partially-populated groups.
    - `sleep?: SleepFn` — defaults to `realSleep`. Tests inject a no-op.
    - `delayRange?: [number, number]` — between-request range. Defaults `[3000, 6000]`.
    - `retryWaitRange?: [number, number]` — defaults `[10000, 15000]`.
    - `fetcher?: (url) => Promise<FetchResult>` — defaults to `invoke('fetch_javdb', { url })`.
- Returns: `Promise<ScrapedGroup[]>` — the final groups array in the input order. Each group
  has its `status` set to `ok` | `error` | `pending` (only if aborted before its turn) | rare
  `fetching` if aborted mid-flight. `finished_at` is set whenever the loop body ran for that
  group.
- Side effects: invokes `fetch_javdb` (one Tauri command per URL); calls `setTimeout` via
  `realSleep`; reads system clock via `new Date().toISOString()`.
- Errors: never throws. All per-URL errors are captured into `group.error` (string) and
  `group.status = "error"`. The Promise only rejects if the caller's `onProgress` callback
  itself throws.
- Async: yes. Resolves only after every URL has settled (or `signal.aborted` becomes true).

**Retry rule**: A first-attempt failure whose message matches `isRateLimitError` triggers one
back-off + retry. A second failure is recorded as `error`. Non-rate-limit errors are recorded
immediately (no retry).

**Calls**:
- `@tauri-apps/api/core::invoke('fetch_javdb', { url })` via `defaultFetcher` — [scraper.ts:65](app/src/lib/scraper.ts:65)
- `randomDelayMs` (both pacing and retry-wait)
- `isRateLimitError`
- `realSleep` / injected `sleep`
- `Date.prototype.toISOString`

**Called by**:
- `App.svelte` line 240 (scrape button handler) — search [App.svelte](app/src/App.svelte) for
  `scrapeBatch`.
- `scraper.test.ts`.

---

#### Interface `ScrapeProgressEvent` *(scraper.ts:45-50)*
- `index: number` (1-based), `total: number`, `group: ScrapedGroup`.

#### Interface `ScrapeOptions` *(scraper.ts:52-62)*
Documented above as part of `scrapeBatch` params.

---

### 3.5 `app/src/lib/rdSender.ts`

Two batch drivers + a zh-Hant error-message mapper. No event listeners — the UI polls via the
caller's `onProgress` callback between awaits.

Module-level private wrappers:
- `defaultFetcher` at [rdSender.ts:54-58](app/src/lib/rdSender.ts:54) — wraps
  `invoke<RdSendOutcome>('rd_send_magnet', { handleId, options })`.
- `defaultCheckFetcher` at [rdSender.ts:60-64](app/src/lib/rdSender.ts:60) — wraps
  `invoke<RdCheckOutcome>('rd_check_pending', { torrentId, strategy })`.

---

#### `sendBatch(items, onProgress, opts?): Promise<RdSendProgress[]>` *(rdSender.ts:70)*

**Purpose**: Send a list of magnet handles to Real-Debrid sequentially. Update each row to
`sending` → (`completed` | `in_pending` | `error`) and emit progress between awaits.

**Contract**:
- Params:
  - `items: RdSendItem[]` — each `{ handle_id, code, size_label? }`. `handle_id` is the
    sidecar handle; the others are display-only.
  - `onProgress: (ev: RdSendBatchEvent) => void` — fires TWICE per item: once when the row
    transitions to `sending` (before await), once when it settles. Event shape:
    `{ index: 1-based, total, item: RdSendProgress }`.
  - `opts?: RdSendBatchOptions`:
    - `signal?: AbortSignal` — checked at top of each iteration only (not mid-await — an
      in-flight `rd_send_magnet` runs to completion).
    - `defaults?: RdSendOptions` — `{ strategy?, min_size_mb?, cache_wait?, code?, size_label? }`;
      `code` and `size_label` per-item override the defaults.
    - `fetcher?` — test seam (default = `defaultFetcher`).
- Returns: `Promise<RdSendProgress[]>` — final array (same length as `items`).
- Side effects: invokes `rd_send_magnet` once per item.
- Errors: never throws (per-item errors are captured into `row.error_code`).
- Async: yes.

**Status transitions**:
- Initial: `{ status: "pending", links: [], error_code: null }`.
- Before await: `status: "sending"`.
- After success with `outcome.status === "completed"`: `status: "completed"`,
  `links: outcome.links`, `torrent_id: outcome.torrent_id`.
- After success with `outcome.status === "pending"`: `status: "in_pending"`, `links: []`,
  `torrent_id: outcome.torrent_id` (kept so a later retry can reconcile by torrent_id).
- After thrown error: `status: "error"`, `error_code: e.message` (or `String(e)`).

**Calls**:
- `@tauri-apps/api/core::invoke('rd_send_magnet', { handleId, options })` via `defaultFetcher`
  or the injected `fetcher`.

**Called by**:
- `App.svelte` line 622 — search [App.svelte](app/src/App.svelte) for `sendBatch`.
- `rdSender.test.ts`.

---

#### `retryPending(entries, onProgress, opts?): Promise<void>` *(rdSender.ts:155)*

**Purpose**: Re-poll a list of persisted `PendingEntry` rows. Emit one event per entry with
the latest outcome — caller is responsible for rebuilding any in-memory list via a separate
`pending_list` invoke.

**Contract**:
- Params:
  - `entries: PendingEntry[]` — each carries `torrent_id` and `strategy` (the strategy the
    row was originally sent with).
  - `onProgress: (ev: RdRetryEvent) => void` — fires once per entry with a discriminated
    union on `ev.result.kind`:
    - `"completed"` → `{ kind, links, name }`
    - `"pending"` → `{ kind, rd_status, progress, name }`
    - `"missing"` → `{ kind }`
    - `"error"` → `{ kind, error_code }`
  - `opts?: RdRetryOptions`:
    - `signal?: AbortSignal` — checked at top of each iteration.
    - `fetcher?` — default = `defaultCheckFetcher`.
- Returns: `Promise<void>` — resolves after every entry has been polled (or the signal aborts).
- Side effects: invokes `rd_check_pending` once per entry.
- Errors: never throws (per-entry errors become `result: { kind: "error", error_code }`).
- Async: yes.

**Calls**:
- `@tauri-apps/api/core::invoke('rd_check_pending', { torrentId, strategy })` via
  `defaultCheckFetcher` or injected `fetcher`.

**Called by**:
- `App.svelte` line 714 — search [App.svelte](app/src/App.svelte) for `retryPending`.
- `rdSender.test.ts`.

---

#### `rdErrorMessage(code: string): string` *(rdSender.ts:216)*

**Purpose**: Map a Rust-side RD error code to a Traditional Chinese user-facing message. Pure;
unknown codes fall through to a generic `「（其他錯誤：${code}）」` so support can still see
the raw code.

**Contract**:
- Params: `code: string` — e.g. `"rd_no_token"`, `"rd_token_invalid"`, `"rd_premium_required"`,
  `"rd_rate_limited"`, `"rd_magnet_error"`, `"rd_download_failed"`, `"rd_torrent_missing"`,
  `"rd_api_error"`, `"unknown_handle"`, `"rd_internal"`.
- Returns: `string` — zh-Hant message.
- Side effects: none.
- Errors: none.
- Async: no.

**Known codes & messages** (verbatim, [rdSender.ts:217-239](app/src/lib/rdSender.ts:217)):

| Code | Message |
|------|---------|
| `rd_no_token` | 尚未設定 Real-Debrid Token |
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
- `App.svelte` lines 506, 526, 530, 543, 558, 806, 1749 — search [App.svelte](app/src/App.svelte)
  for `rdErrorMessage`.
- `rdSender.test.ts`.

---

#### Interfaces

- `RdSendOptions` [rdSender.ts:23-30](app/src/lib/rdSender.ts:23) — passed verbatim as
  `options` to `rd_send_magnet`. `code` / `size_label` are display-only metadata that the
  sidecar persists to `pending_torrents.json` on a pending outcome.
- `RdSendItem` [rdSender.ts:32-38](app/src/lib/rdSender.ts:32) — one row of the batch
  (`handle_id` + display fields).
- `RdSendBatchEvent` [rdSender.ts:40-44](app/src/lib/rdSender.ts:40) — `{ index, total, item }`.
- `RdSendBatchOptions` [rdSender.ts:46-52](app/src/lib/rdSender.ts:46) — `signal`, `defaults`,
  `fetcher`.
- `RdRetryEvent` [rdSender.ts:133-143](app/src/lib/rdSender.ts:133) — discriminated by
  `result.kind`.
- `RdRetryOptions` [rdSender.ts:145-148](app/src/lib/rdSender.ts:145).

---

### 3.6 `app/src/lib/settingsValidation.ts`

Pure validators. Every validator returns `null` on success, or a zh-Hant error string on
failure. No Tauri, no DOM. Rust enforces the same shape on persist; this is the early gate
that drives `Save` button enablement + inline messages.

Module-level constants:
- `FILE_PICK_VALUES = ["smart", "largest", "video", "all"] as const` —
  [settingsValidation.ts:14](app/src/lib/settingsValidation.ts:14). Type alias
  `FilePickValue = (typeof FILE_PICK_VALUES)[number]`.
- `THEME_VALUES = ["light", "dark"] as const` —
  [settingsValidation.ts:17](app/src/lib/settingsValidation.ts:17). Type alias `ThemeValue`.
- `SCALE_PRESETS = ["auto", "1.0", "1.25", "1.5", "1.75", "2.0", "2.5", "3.0"] as const` —
  [settingsValidation.ts:20](app/src/lib/settingsValidation.ts:20). UI dropdown options.
- Private: `SCALE_MIN = 0.5`, `SCALE_MAX = 3.0` —
  [settingsValidation.ts:31-32](app/src/lib/settingsValidation.ts:31).

---

#### `validateMinSizeMb(value: number): string | null` *(settingsValidation.ts:35)*

**Purpose**: Non-negative integer check for `rd.min_size_mb`.

**Contract**:
- Params: `value: number`.
- Returns: `null` if integer ≥ 0, else `「必須是數字」`/`「必須是整數」`/`「不能為負」`.
- Side effects: none. Errors: none. Async: no.

**Calls**: `Number.isFinite`, `Number.isInteger`.

**Called by**: `validateSettingsDraft`, `settingsValidation.test.ts`.

---

#### `validateCacheWaitSeconds(value: number): string | null` *(settingsValidation.ts:43)*

**Purpose**: Integer ≥ 5 check for `rd.cache_wait_seconds`.

**Contract**: Returns `「最小為 5 秒（避免 RD 端尚未判定快取就放棄）」` when `< 5`. Else integer
checks identical to `validateMinSizeMb`.

**Calls**: `Number.isFinite`, `Number.isInteger`.

**Called by**: `validateSettingsDraft`, `settingsValidation.test.ts`.

---

#### `validateWaitTimeoutSeconds(value: number): string | null` *(settingsValidation.ts:51)*

**Purpose**: Integer ≥ 30 check for `rd.wait_timeout_seconds`. Error string at 30 boundary:
`「最小為 30 秒（未快取的磁力會比較久）」`.

**Calls**: `Number.isFinite`, `Number.isInteger`.

**Called by**: `validateSettingsDraft`, `settingsValidation.test.ts`.

---

#### `validateScale(value: string): string | null` *(settingsValidation.ts:59)*

**Purpose**: Validate `ui.scale` — must be `"auto"` (literal) OR a decimal in `[0.5, 3.0]`.

**Contract**:
- Params: `value: string`. Non-string → `「必須是字串」` (runtime defensive — TS forbids it).
- Returns: `null` if `"auto"` (after trim) or parseable finite number in `[SCALE_MIN, SCALE_MAX]`.
- Empty trimmed → `「不能為空」`. Non-finite parse → `「必須是 auto 或 0.5–3.0 之間的數字」`.
- Out of range → `「必須在 0.5–3 之間」`.
- Side effects: none. Errors: none. Async: no.

**Calls**: `String.prototype.trim`, `Number(...)`, `Number.isFinite`.

**Called by**: `validateSettingsDraft`, `settingsValidation.test.ts`.

---

#### `validateFilePick(value: string): string | null` *(settingsValidation.ts:73)*

**Purpose**: Membership check against `FILE_PICK_VALUES`.

**Contract**: Returns null on hit, else `「必須是 smart / largest / video / all 之一」` (joined
from the tuple).

**Calls**: `Array.prototype.includes`.

**Called by**: `validateSettingsDraft`, `settingsValidation.test.ts`.

---

#### `validateTheme(value: string): string | null` *(settingsValidation.ts:81)*

**Purpose**: Membership check against `THEME_VALUES`.

**Contract**: null on hit, else `「必須是 light / dark 之一」`.

**Calls**: `Array.prototype.includes`.

**Called by**: `validateSettingsDraft`, `settingsValidation.test.ts`.

---

#### `validateSettingsDraft(draft: Settings): Record<string, string>` *(settingsValidation.ts:98)*

**Purpose**: Aggregate every per-field validator into a `field-id → error-message` map. Empty
map means the draft is valid.

**Contract**:
- Params: `draft: Settings` — the full editor state.
- Returns: `Record<string, string>` — keys are stable UI ids: `"rd.file_pick"`,
  `"rd.min_size_mb"`, `"rd.cache_wait_seconds"`, `"rd.wait_timeout_seconds"`, `"ui.theme"`,
  `"ui.scale"`. Missing key = that field is valid.
- Note: `rd.api_token` is **not** validated here (the field is intentionally write-only and
  may be empty meaning "leave as-is"; the Rust side handles its semantics).
- Side effects: none. Errors: none. Async: no.

**Calls**: `validateFilePick`, `validateMinSizeMb`, `validateCacheWaitSeconds`,
`validateWaitTimeoutSeconds`, `validateTheme`, `validateScale`.

**Called by**:
- `App.svelte` line 898 (derived state controlling the Save button) — search
  [App.svelte](app/src/App.svelte) for `validateSettingsDraft`.
- `settingsValidation.test.ts`.

---

### 3.7 `app/src/lib/types.ts` — runtime exports

The only runtime export is `defaultFilterState` — already documented in §2.4. Everything else
in `types.ts` is erased at compile time.

---

## 4. Cross-cutting concerns

### 4.1 Error handling pattern

- **Validators** (`settingsValidation.ts`) use a "Result-lite" pattern: return `null` or a
  human-readable string. Never throw.
- **Batch drivers** (`scraper.ts`, `rdSender.ts`) **never reject** the outer promise. Per-item
  errors are caught inside the loop and attached to the per-item state object
  (`group.error` / `row.error_code`). The caller's only failure mode is its own
  `onProgress` callback throwing — that propagates.
- **Pure helpers** (`magnetUtils.ts`) never throw; bad input collapses to safe defaults
  (`parseSizeGb("") → 0`, `parseFileCount("") → 999`).
- **Tauri `invoke`** rejects with the Rust-side error string. Both `scrapeBatch` and
  `sendBatch` extract via `e instanceof Error ? e.message : String(e)`. For RD, the result is
  fed into `rdErrorMessage` at the UI layer for translation.

### 4.2 State management

- **No Svelte stores in `lib/*`.** All lib modules are stateless function libraries.
- **Per-call state** lives in the array passed back via `onProgress` (e.g. `RdSendProgress[]`
  for sendBatch; `ScrapedGroup[]` for scrapeBatch). The driver mutates indexes of this array
  in place between awaits, then re-emits the row to the caller — the caller is responsible for
  any reactive state binding (Svelte `$state` in App.svelte).
- **Abort cancellation** is propagated via standard `AbortSignal` — checked at iteration
  boundaries only; an in-flight invoke is allowed to run to completion (its result is then
  discarded by the loop break).
- **No `localStorage` writes anywhere in `lib/*`** — persistence is delegated to Rust
  (`save_settings`, `pending_torrents.json`, etc.).

### 4.3 How does the frontend learn about backend events?

- **It polls.** No `listen('event-name', …)` subscriptions exist in any `lib/*` module. The
  pattern is uniformly:
  1. Caller invokes a Rust command (`fetch_javdb`, `rd_send_magnet`, `rd_check_pending`).
  2. Rust runs synchronously (from the WebView's POV — the actual sidecar work may be async
     internally, but the command resolves only when settled).
  3. Frontend awaits in a sequential loop and emits progress between iterations.
- This implies App.svelte may register its own `listen(...)` calls (e.g. for log streaming,
  paths/secrets, or auto-update events), but those are out of scope for this document.
- The `signal: AbortSignal` pattern is how the UI requests cancellation; there is no
  backend-initiated event push into the lib layer.

### 4.4 Test-injection pattern

All three batch drivers expose an injectable `fetcher` (and `scrapeBatch` also injects
`sleep`) so that unit tests can run without a Tauri runtime. The default fetcher is a closed-over
arrow function that calls `invoke(...)` — production code paths do not see the seam, and the
seams have no side effect other than the `invoke` call itself.
