// Pure helpers for parsing/filtering/sorting/grouping magnet rows.
// All input comes from the sidecar (already redacted); these functions never
// touch network or stateful APIs, which makes them trivial to unit-test.

import type {
  FilterState,
  GroupPick,
  MagnetRow,
  ScrapedGroup,
  SortColumn,
  SortDirection,
} from "./types";

// Bounded number quantifiers keep these regexes linear: with `+` on
// `[\d.]` the engine can revisit the same bytes O(n) times across
// starting positions, which Sonar flags as super-linear (polynomial)
// backtracking. JavDB never emits sizes wider than a handful of
// digits, so a tight upper bound is both safe and behavior-preserving.
const SIZE_TB_RX = /(\d{1,12}(?:\.\d{1,12})?)\s{0,4}TB/i;
const SIZE_GB_RX = /(\d{1,12}(?:\.\d{1,12})?)\s{0,4}GB/i;
const SIZE_MB_RX = /(\d{1,12}(?:\.\d{1,12})?)\s{0,4}MB/i;
const FILE_COUNT_RX = /(\d{1,9})\s{0,4}個文件/;

/** "1.2TB" → 1228.8. "5.67GB, 5個文件" → 5.67. "512MB, 1個文件" → 0.5. unparseable → 0. */
export function parseSizeGb(size: string): number {
  if (!size) return 0;
  const tb = SIZE_TB_RX.exec(size);
  if (tb) return Number.parseFloat(tb[1]) * 1024;
  const gb = SIZE_GB_RX.exec(size);
  if (gb) return Number.parseFloat(gb[1]);
  const mb = SIZE_MB_RX.exec(size);
  if (mb) return Number.parseFloat(mb[1]) / 1024;
  return 0;
}

/** "5.67GB, 5個文件" → 5. unparseable → 999 (matches the Python tests). */
export function parseFileCount(size: string): number {
  if (!size) return 999;
  const m = FILE_COUNT_RX.exec(size);
  return m ? Number.parseInt(m[1], 10) : 999;
}

/**
 * Synthetic groups created by the paste-magnet path (App.svelte
 * `registerPastedMagnets`) use the `manual://` URL scheme. They carry
 * explicit user instructions rather than scraped candidates, so the
 * processing pipeline treats them specially — see `processGroupRows`.
 */
export function isManualGroup(group: Pick<ScrapedGroup, "url">): boolean {
  return group.url.startsWith("manual://");
}

/** Case-insensitive haystack search across name / size / tags / date. */
export function matchesKeyword(row: MagnetRow, keyword: string): boolean {
  if (!keyword) return true;
  const needle = keyword.toLowerCase();
  if (row.name.toLowerCase().includes(needle)) return true;
  if (row.size.toLowerCase().includes(needle)) return true;
  if (row.date.toLowerCase().includes(needle)) return true;
  for (const t of row.tags) {
    if (t.toLowerCase().includes(needle)) return true;
  }
  return false;
}

export function isHd(row: MagnetRow): boolean {
  // The sidecar passes the JavDB tag string verbatim. JavDB labels HD
  // releases as the literal "高清" (zh-Hant) tag.
  return row.tags.some((t) => t === "高清" || t.toLowerCase() === "hd");
}

/**
 * Apply non-grouping filters: keyword + HD + size range.
 * Returns a NEW array; never mutates input.
 */
export function filterRows(
  rows: MagnetRow[],
  filter: FilterState,
): MagnetRow[] {
  return rows.filter((row) => {
    if (!matchesKeyword(row, filter.keyword)) return false;
    if (filter.hd_only && !isHd(row)) return false;
    if (filter.min_size_gb !== null && filter.min_size_gb > 0) {
      if (parseSizeGb(row.size) < filter.min_size_gb) return false;
    }
    if (filter.max_size_gb !== null && filter.max_size_gb > 0) {
      if (parseSizeGb(row.size) > filter.max_size_gb) return false;
    }
    return true;
  });
}

/**
 * Per-group "keep N" pick. After the per-row filters above run, this picks
 * a single representative row per group based on the user's strategy.
 *   - all          → pass through (unchanged)
 *   - largest      → row with the largest parseSizeGb
 *   - smallest     → row with the smallest parseSizeGb
 *   - fewest_files → row with the fewest 個文件 (ties broken by larger size)
 *
 * Empty input → empty output. Returns a NEW array.
 */
/**
 * Single-best pick via a comparator. The comparator returns true when
 * `cur` is strictly better than `acc`, so leftmost-on-tie is preserved
 * (matches the original `>`/`<` reduce semantics).
 */
function pickBy(
  rows: MagnetRow[],
  isBetter: (cur: MagnetRow, acc: MagnetRow) => boolean,
): MagnetRow[] {
  return [rows.reduce((acc, cur) => (isBetter(cur, acc) ? cur : acc))];
}

export function applyGroupPick(
  rows: MagnetRow[],
  pick: GroupPick,
): MagnetRow[] {
  if (rows.length === 0) return [];
  if (pick === "all") return rows.slice();

  if (pick === "largest") {
    return pickBy(rows, (a, b) => parseSizeGb(a.size) > parseSizeGb(b.size));
  }
  if (pick === "smallest") {
    return pickBy(rows, (a, b) => parseSizeGb(a.size) < parseSizeGb(b.size));
  }
  if (pick === "fewest_files") {
    return pickBy(rows, (a, b) => {
      const ac = parseFileCount(a.size);
      const bc = parseFileCount(b.size);
      if (ac !== bc) return ac < bc;
      // tie-break: prefer larger file size (more likely to be the main video)
      return parseSizeGb(a.size) > parseSizeGb(b.size);
    });
  }
  // Defensive fallback for runtime-only `pick` values (e.g. older
  // settings file with an unknown enum). Test-only path today.
  return rows.slice();
}

/**
 * Sort rows by column. Stable for equal keys (Array.prototype.sort is not
 * guaranteed stable on every JS engine pre-2019 but Chromium-based WebView2
 * IS stable, which matches our deployment target).
 */
export function sortRows(
  rows: MagnetRow[],
  column: SortColumn | null,
  direction: SortDirection,
): MagnetRow[] {
  if (column === null) return rows.slice();
  const dir = direction === "asc" ? 1 : -1;
  return rows.slice().sort((a, b) => {
    let cmp = 0;
    if (column === "size") {
      cmp = parseSizeGb(a.size) - parseSizeGb(b.size);
    } else if (column === "name") {
      cmp = a.name.localeCompare(b.name);
    } else if (column === "tags") {
      cmp = a.tags.join(",").localeCompare(b.tags.join(","));
    } else {
      // SortColumn type ensures the remaining value is "date".
      cmp = a.date.localeCompare(b.date);
    }
    return cmp * dir;
  });
}

/**
 * Compose filter → group_pick → sort. Returns a fresh array per group;
 * empty groups (after filtering) yield [] so the UI can show "no rows".
 *
 * Manual (pasted) groups skip the filter and group-pick stages entirely:
 * a pasted magnet is an explicit instruction, not a candidate to narrow
 * down — and its rows carry no size/tags/date for the filters to read
 * (group_pick="largest" would otherwise collapse them to one arbitrary
 * row, since every manual row parses to 0 GB). Sorting still applies.
 */
export function processGroupRows(
  group: ScrapedGroup,
  filter: FilterState,
  sortColumn: SortColumn | null,
  sortDirection: SortDirection,
): MagnetRow[] {
  if (!group.result) return [];
  if (isManualGroup(group)) {
    return sortRows(group.result.magnets, sortColumn, sortDirection);
  }
  const filtered = filterRows(group.result.magnets, filter);
  const picked = applyGroupPick(filtered, filter.group_pick);
  return sortRows(picked, sortColumn, sortDirection);
}

/**
 * Order-preserving dedupe by `handle_id`. Used as a second line of
 * defense before sending magnets to RD or writing to the clipboard:
 * the sidecar's BTIH-keyed handle table already prevents a magnet from
 * having two handles, but if the UI somehow renders the same handle in
 * two groups (e.g. user re-fetched the same JavDB URL), we still don't
 * want to invoke RD twice or paste duplicates into the clipboard.
 *
 * Keeps the first occurrence's metadata (code / size / etc).
 */
export function dedupeByHandleId<T extends { handle_id: string }>(rows: T[]): T[] {
  const seen = new Set<string>();
  const out: T[] = [];
  for (const r of rows) {
    if (seen.has(r.handle_id)) continue;
    seen.add(r.handle_id);
    out.push(r);
  }
  return out;
}
