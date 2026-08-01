// Local heuristics for "which magnet is Real-Debrid most likely to already
// have cached?".
//
// This CANNOT be an API lookup: RD removed /torrents/instantAvailability in
// 2024 and the sidecar's realdebrid.py has no cache-probe endpoint. Every
// value produced here is a guess derived from the JavDB row's own metadata
// (re-upload-site prefix in the filename, HD markers, upload date) — a hint
// for the user, never a promise that the send will hit cache.
//
// Layering: this module is a LEAF and imports only ./types. magnetUtils.ts
// imports IT (for isHd / pickRdReadyRow), so importing magnetUtils back from
// here would close an import cycle. That is exactly why the same-date
// tie-break is injected into `pickRdCandidate` as a parameter instead of
// calling magnetUtils' parseSizeGb directly.

import type { MagnetRow } from "./types";

/**
 * Re-upload sites whose releases are, empirically, the ones already sitting
 * in RD's cache. Matched with `includes` on the lower-cased name rather than
 * `startsWith`: JavDB sometimes renders the row as
 * "[javdb.com]hhd800.com@ABC-123", where a prefix test would silently miss.
 *
 * Hardcoded on purpose — a user-editable list would need a settings
 * round-trip through Rust and the sidecar, which this feature does not touch.
 */
export const RD_CACHE_PREFIXES: readonly string[] = ["hhd800.com@", "489155.com@"];

// Resolution tokens embedded in the release name. Every alternative is a
// fixed-width literal and the lookbehind is bounded, so there is no unbounded
// repetition to backtrack over — the super-linear (polynomial) backtracking
// that bounded magnetUtils' SIZE_*_RX cannot arise here.
//
// Two boundaries carry the whole rule:
//   - trailing `(?![a-z0-9])`, without which "1080MB" (a size) reads as HD;
//   - a BARE "1080"/"2160" only counts inside a WxH spelling (`1920x1080`).
//     Without that, JAV codes whose serial happens to end in those digits —
//     "259LUXU-1080", "HEYZO-2160", "300MIUM-1080" are all real labels — get
//     classified as HD, which is the worse error of the two: a missed HD row
//     is still caught by JavDB's 高清 tag, while a false HD row survives the
//     hd_only filter, wears the badge, and lands in the pre-send "high
//     likelihood" bucket with nothing left to catch it.
// The lookbehind is deliberately fixed-width (`\dx`, not `\d{1,4}x`): Python's
// `re` rejects variable-width lookbehind, and scripts/rd_log_report.py has to
// carry a behaviourally identical copy of this rule to score the outcome log.
// Only the two characters before the number decide the match anyway.
const HD_RESOLUTION_RX = /(?:2160p|1080p|4k|uhd|(?<=\dx)(?:2160|1080))(?![a-z0-9])/i;

/**
 * Sentinel date key for rows with no upload date. It has to sort AFTER every
 * real ISO date: a raw "" compares as smaller than "2019-01-01", so without
 * this a pasted magnet (no date at all) would win "earliest upload" in every
 * single group.
 */
const NO_DATE_KEY = "9999-99-99";

/** Per-row RD-likelihood class. See spec §2.3 for the full table. */
export type RdRowClass = "prefix_hd" | "prefix_only" | "hd" | "unknown" | "plain";

/** Which rule produced the group's pick — drives the ⚠ hint on the fallback. */
export type RdPickTier = "prefix_hd" | "hd_earliest" | "no_hd_fallback";

export interface RdCandidate {
  row: MagnetRow;
  tier: RdPickTier;
}

/** Returns <0 when `a` is the better of two rows that share a date key. */
type RdTieBreak = (a: MagnetRow, b: MagnetRow) => number;

export function hasCachePrefix(row: MagnetRow): boolean {
  const name = row.name.toLowerCase();
  return RD_CACHE_PREFIXES.some((p) => name.includes(p));
}

/** True when the release NAME advertises 1080p/2160p/4K/UHD. */
export function hasHdResolution(name: string): boolean {
  if (!name) return false;
  return HD_RESOLUTION_RX.test(name);
}

/**
 * HD by tag OR by filename. This is the single definition of "HD" for the
 * whole frontend — magnetUtils' `isHd` (and therefore the hd_only filter)
 * delegates here so the badge and the filter can never disagree.
 */
export function isHdRow(row: MagnetRow): boolean {
  // The sidecar passes the JavDB tag string verbatim. JavDB labels HD
  // releases as the literal "高清" (zh-Hant) tag.
  if (row.tags.some((t) => t === "高清" || t.toLowerCase() === "hd")) return true;
  return hasHdResolution(row.name);
}

/** Sortable upload-date key; missing dates normalize to `NO_DATE_KEY`. */
export function rdDateKey(row: MagnetRow): string {
  const date = row.date.trim();
  return date === "" ? NO_DATE_KEY : date;
}

export function classifyRow(row: MagnetRow): RdRowClass {
  const prefixed = hasCachePrefix(row);
  const hd = isHdRow(row);
  if (prefixed && hd) return "prefix_hd";
  if (prefixed) return "prefix_only";
  if (hd) return "hd";
  // No metadata at all (pasted magnets) is NOT evidence of low quality, so
  // it gets its own class instead of being lumped in with `plain` — showing
  // "low likelihood" for a row we know nothing about would be a fake signal.
  if (row.tags.length === 0 && row.date.trim() === "") return "unknown";
  return "plain";
}

/** Row badge + tooltip, or null for classes that carry no signal. */
export function rdBadge(cls: RdRowClass): { text: string; title: string } | null {
  if (cls === "prefix_hd") {
    return { text: "⚡高清", title: "常見轉載站 + 高清：RD 最可能已有快取" };
  }
  if (cls === "prefix_only") {
    return { text: "⚡", title: "常見轉載站：命中率高，但畫質未確認" };
  }
  if (cls === "hd") {
    return { text: "高清", title: "高清但非常見轉載站：以最早上傳推測命中率" };
  }
  return null;
}

/**
 * Earliest-upload pick inside one already-classified bucket. `tieBreak` runs
 * ONLY when two rows share a date key, so a caller-supplied "bigger file
 * wins" comparator can never override the primary date ordering. The
 * replacement is strict (`< 0`), which keeps leftmost-on-tie — the same
 * semantics as magnetUtils' pickBy.
 */
function earliestBy(rows: MagnetRow[], tieBreak: RdTieBreak): MagnetRow {
  return rows.reduce((acc, cur) => {
    const accKey = rdDateKey(acc);
    const curKey = rdDateKey(cur);
    if (curKey !== accKey) return curKey < accKey ? cur : acc;
    return tieBreak(cur, acc) < 0 ? cur : acc;
  });
}

/**
 * The group's single most-likely-cached row, plus the tier that justified
 * it. Tiers are tried in order and the first non-empty bucket wins:
 *   1. prefix_hd     → re-upload site AND HD
 *   2. hd_earliest   → HD anywhere, oldest first (more time to get cached)
 *   3. no_hd_fallback→ nothing is HD; prefer a prefixed row, else oldest
 * Empty input → null.
 */
export function pickRdCandidate(
  rows: MagnetRow[],
  tieBreak: RdTieBreak = () => 0,
): RdCandidate | null {
  if (rows.length === 0) return null;

  const prefixHd = rows.filter((r) => classifyRow(r) === "prefix_hd");
  if (prefixHd.length > 0) {
    return { row: earliestBy(prefixHd, tieBreak), tier: "prefix_hd" };
  }

  // prefixHd is empty here, so every HD row necessarily classifies as `hd`.
  const hd = rows.filter((r) => isHdRow(r));
  if (hd.length > 0) {
    return { row: earliestBy(hd, tieBreak), tier: "hd_earliest" };
  }

  // Tier 3: the whole group is non-HD. Prefixed rows still carry the better
  // cache odds, so they form the pool when present; otherwise everything is.
  const prefixed = rows.filter((r) => hasCachePrefix(r));
  return {
    row: earliestBy(prefixed.length > 0 ? prefixed : rows, tieBreak),
    tier: "no_hd_fallback",
  };
}

/**
 * Bucket counts for the pre-send summary panel. `unrated` deliberately holds
 * both `prefix_only` (good odds, unverified quality) and `unknown` (no
 * metadata) — neither belongs in "low", which must mean "we have metadata
 * and it says this is not what you want".
 */
export function summarizeRdLikelihood(classes: RdRowClass[]): {
  high: number;
  low: number;
  unrated: number;
} {
  let high = 0;
  let low = 0;
  let unrated = 0;
  for (const cls of classes) {
    if (cls === "prefix_hd" || cls === "hd") high += 1;
    else if (cls === "plain") low += 1;
    else unrated += 1;
  }
  return { high, low, unrated };
}
