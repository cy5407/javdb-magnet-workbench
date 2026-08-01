import { describe, expect, it } from "vitest";
import {
  RD_CACHE_PREFIXES,
  classifyRow,
  hasCachePrefix,
  hasHdResolution,
  isHdRow,
  pickRdCandidate,
  rdBadge,
  rdDateKey,
  summarizeRdLikelihood,
  type RdRowClass,
} from "./rdPriority";
import type { MagnetRow } from "./types";

// Baseline row is deliberately "plain": no cache prefix, no HD marker, but
// it DOES carry metadata (tags array is checked for emptiness, date is set),
// so it classifies as `plain` rather than `unknown` unless a test strips it.
const row = (over: Partial<MagnetRow> = {}): MagnetRow => ({
  handle_id: "h1",
  name: "ABC-123",
  size: "5GB, 1個文件",
  tags: ["無碼"],
  date: "2026-05-09",
  magnet_redacted: "magnet:?xt=urn:btih:0201592f...",
  ...over,
});

// Stand-in for the "larger file wins" comparator magnetUtils injects. Kept
// local so this test never imports magnetUtils (which would hide the very
// layering the injection point exists to protect).
const gb = (r: MagnetRow) => Number.parseFloat(r.size) || 0;
const preferBigger = (a: MagnetRow, b: MagnetRow) => gb(b) - gb(a);

describe("RD_CACHE_PREFIXES", () => {
  it("is the hardcoded two-site list", () => {
    expect([...RD_CACHE_PREFIXES]).toEqual(["hhd800.com@", "489155.com@"]);
  });
});

describe("hasCachePrefix", () => {
  it("matches a lower-case prefix at the start of the name", () => {
    expect(hasCachePrefix(row({ name: "hhd800.com@ABC-123" }))).toBe(true);
    expect(hasCachePrefix(row({ name: "489155.com@ABC-123" }))).toBe(true);
  });

  it("is case-insensitive", () => {
    expect(hasCachePrefix(row({ name: "HHD800.COM@ABC-123" }))).toBe(true);
    expect(hasCachePrefix(row({ name: "Hhd800.Com@ABC-123" }))).toBe(true);
  });

  it("matches an EMBEDDED prefix (JavDB renders [javdb.com] in front)", () => {
    // The whole reason the check is `includes`, not `startsWith`.
    expect(hasCachePrefix(row({ name: "[javdb.com]HHD800.com@ABC-123" }))).toBe(true);
  });

  it("false for names without any known prefix", () => {
    expect(hasCachePrefix(row({ name: "ABC-123 1080p" }))).toBe(false);
    expect(hasCachePrefix(row({ name: "" }))).toBe(false);
  });
});

describe("hasHdResolution", () => {
  it("matches resolution tokens", () => {
    expect(hasHdResolution("ABC-123 1080p.mkv")).toBe(true);
    expect(hasHdResolution("ABC-123 1080P")).toBe(true);
    expect(hasHdResolution("ABC-123-2160p")).toBe(true);
    expect(hasHdResolution("SSIS-123.4K.mkv")).toBe(true);
    expect(hasHdResolution("ABC-123 UHD rip")).toBe(true);
    expect(hasHdResolution("abc-123 uhd")).toBe(true);
  });

  it("matches a bare resolution number ONLY inside a WxH spelling", () => {
    expect(hasHdResolution("ABC-123 1920x1080")).toBe(true);
    expect(hasHdResolution("ABC-123 3840X2160")).toBe(true);
  });

  it("does NOT read a JAV serial ending in 1080 / 2160 as a resolution", () => {
    // Real labels. A bare trailing number is a serial far more often than a
    // resolution, and a genuinely-HD row still has JavDB's 高清 tag to fall
    // back on — whereas a false HD row would pass hd_only, wear the badge and
    // land in the pre-send "high likelihood" bucket with nothing to catch it.
    expect(hasHdResolution("259LUXU-1080.mp4")).toBe(false);
    expect(hasHdResolution("HEYZO-2160")).toBe(false);
    expect(hasHdResolution("hhd800.com@300MIUM-1080.mp4")).toBe(false);
    expect(hasHdResolution("ABC-123 1080")).toBe(false);
  });

  it("does NOT treat a size as a resolution (the 1080MB trap)", () => {
    expect(hasHdResolution("ABC-123 1080MB")).toBe(false);
    expect(hasHdResolution("ABC-123 2160MB, 3個文件")).toBe(false);
    expect(hasHdResolution("ABC-123 4KB")).toBe(false);
  });

  it("false for low-res / unrelated names", () => {
    expect(hasHdResolution("ABC-123 480p")).toBe(false);
    expect(hasHdResolution("ABC-123")).toBe(false);
    expect(hasHdResolution("")).toBe(false);
  });
});

describe("isHdRow", () => {
  it("true on the 高清 / hd tags (case-insensitive)", () => {
    expect(isHdRow(row({ tags: ["高清"] }))).toBe(true);
    expect(isHdRow(row({ tags: ["hd"] }))).toBe(true);
    expect(isHdRow(row({ tags: ["HD"] }))).toBe(true);
  });

  it("true on a filename resolution token even with no tags", () => {
    expect(isHdRow(row({ name: "ABC-123 1080p", tags: [] }))).toBe(true);
  });

  it("false when neither tag nor filename says HD", () => {
    expect(isHdRow(row({ name: "ABC-123 1080MB", tags: [] }))).toBe(false);
    expect(isHdRow(row({ tags: ["無碼"] }))).toBe(false);
  });
});

describe("rdDateKey", () => {
  it("passes a real date through untouched", () => {
    expect(rdDateKey(row({ date: "2026-05-09" }))).toBe("2026-05-09");
  });

  it("normalizes empty / whitespace dates to the far-future sentinel", () => {
    // Without this, "" lexically sorts BEFORE every real date and a pasted
    // row with no metadata would win "earliest upload" every single time.
    expect(rdDateKey(row({ date: "" }))).toBe("9999-99-99");
    expect(rdDateKey(row({ date: "   " }))).toBe("9999-99-99");
  });

  it("trims surrounding whitespace", () => {
    expect(rdDateKey(row({ date: " 2026-05-09 " }))).toBe("2026-05-09");
  });
});

describe("classifyRow", () => {
  it("prefix + HD → prefix_hd", () => {
    expect(classifyRow(row({ name: "hhd800.com@ABC-123 1080p", tags: [] }))).toBe("prefix_hd");
    expect(classifyRow(row({ name: "hhd800.com@ABC-123", tags: ["高清"] }))).toBe("prefix_hd");
  });

  it("prefix without HD → prefix_only", () => {
    expect(classifyRow(row({ name: "489155.com@ABC-123", tags: ["無碼"] }))).toBe("prefix_only");
  });

  it("HD without prefix → hd", () => {
    expect(classifyRow(row({ name: "ABC-123 4K", tags: [] }))).toBe("hd");
  });

  it("no tags AND no date → unknown (pasted magnet, not 'low quality')", () => {
    expect(classifyRow(row({ name: "ABC-123", tags: [], date: "" }))).toBe("unknown");
    expect(classifyRow(row({ name: "ABC-123", tags: [], date: "  " }))).toBe("unknown");
  });

  it("has metadata but is definitely not HD → plain", () => {
    expect(classifyRow(row({ name: "ABC-123", tags: ["無碼"], date: "2026-05-09" }))).toBe("plain");
    // Partial metadata is still metadata: a date alone rules out `unknown`.
    expect(classifyRow(row({ name: "ABC-123", tags: [], date: "2026-05-09" }))).toBe("plain");
    expect(classifyRow(row({ name: "ABC-123", tags: ["無碼"], date: "" }))).toBe("plain");
  });
});

describe("rdBadge", () => {
  it("labels the three positive classes", () => {
    expect(rdBadge("prefix_hd")?.text).toBe("⚡高清");
    expect(rdBadge("prefix_only")?.text).toBe("⚡");
    expect(rdBadge("hd")?.text).toBe("高清");
  });

  it("every badge carries a non-empty title explaining the reason", () => {
    for (const cls of ["prefix_hd", "prefix_only", "hd"] as RdRowClass[]) {
      expect(rdBadge(cls)?.title.length).toBeGreaterThan(0);
    }
  });

  it("no badge for unknown / plain", () => {
    expect(rdBadge("unknown")).toBeNull();
    expect(rdBadge("plain")).toBeNull();
  });
});

describe("pickRdCandidate", () => {
  it("empty input → null", () => {
    expect(pickRdCandidate([])).toBeNull();
  });

  it("tier 1: prefix_hd wins over plain hd, earliest date inside the tier", () => {
    const rows = [
      row({ handle_id: "hd-only", name: "ABC-123 1080p", date: "2020-01-01" }),
      row({ handle_id: "prefix-late", name: "hhd800.com@ABC-123 1080p", date: "2026-05-09" }),
      row({ handle_id: "prefix-early", name: "hhd800.com@ABC-123 1080p", date: "2025-01-02" }),
    ];
    const picked = pickRdCandidate(rows);
    expect(picked?.row.handle_id).toBe("prefix-early");
    expect(picked?.tier).toBe("prefix_hd");
  });

  it("tier 2: no prefix_hd → earliest HD row", () => {
    const rows = [
      row({ handle_id: "hd-late", name: "ABC-123 1080p", date: "2026-05-09" }),
      row({ handle_id: "hd-early", name: "ABC-123", tags: ["高清"], date: "2024-03-03" }),
      row({ handle_id: "prefix-plain", name: "hhd800.com@ABC-123", tags: ["無碼"], date: "2019-01-01" }),
    ];
    const picked = pickRdCandidate(rows);
    expect(picked?.row.handle_id).toBe("hd-early");
    expect(picked?.tier).toBe("hd_earliest");
  });

  it("a dateless row must NOT be treated as the earliest upload", () => {
    // The regression this whole rdDateKey sentinel exists for: raw ""
    // compares as smaller than any real date.
    const rows = [
      row({ handle_id: "no-date", name: "ABC-123 1080p", tags: [], date: "" }),
      row({ handle_id: "dated", name: "ABC-123 1080p", tags: [], date: "2026-05-09" }),
    ];
    const picked = pickRdCandidate(rows);
    expect(picked?.row.handle_id).toBe("dated");
    expect(picked?.tier).toBe("hd_earliest");
  });

  it("falls back to the dateless row when it is the only candidate", () => {
    const rows = [row({ handle_id: "no-date", name: "ABC-123 1080p", tags: [], date: "" })];
    expect(pickRdCandidate(rows)?.row.handle_id).toBe("no-date");
  });

  it("tier 3: no HD anywhere → prefixed row first, then earliest date", () => {
    const rows = [
      row({ handle_id: "plain-early", name: "ABC-123", date: "2019-01-01" }),
      row({ handle_id: "prefix-late", name: "489155.com@ABC-123", date: "2026-05-09" }),
      row({ handle_id: "prefix-mid", name: "489155.com@ABC-123", date: "2022-02-02" }),
    ];
    const picked = pickRdCandidate(rows);
    expect(picked?.row.handle_id).toBe("prefix-mid");
    expect(picked?.tier).toBe("no_hd_fallback");
  });

  it("tier 3 with no prefixes either → earliest date overall", () => {
    const rows = [
      row({ handle_id: "late", date: "2026-05-09" }),
      row({ handle_id: "early", date: "2019-01-01" }),
    ];
    const picked = pickRdCandidate(rows);
    expect(picked?.row.handle_id).toBe("early");
    expect(picked?.tier).toBe("no_hd_fallback");
  });

  it("same-date tie defaults to input order", () => {
    const rows = [
      row({ handle_id: "first", name: "ABC-123 1080p", size: "1GB", date: "2026-05-09" }),
      row({ handle_id: "second", name: "ABC-123 1080p", size: "9GB", date: "2026-05-09" }),
    ];
    expect(pickRdCandidate(rows)?.row.handle_id).toBe("first");
  });

  it("same-date tie is decided by the injected comparator", () => {
    const rows = [
      row({ handle_id: "small", name: "ABC-123 1080p", size: "1GB", date: "2026-05-09" }),
      row({ handle_id: "big", name: "ABC-123 1080p", size: "9GB", date: "2026-05-09" }),
    ];
    expect(pickRdCandidate(rows, preferBigger)?.row.handle_id).toBe("big");
  });

  it("the injected comparator never overrides the date ordering", () => {
    const rows = [
      row({ handle_id: "small-early", name: "ABC-123 1080p", size: "1GB", date: "2019-01-01" }),
      row({ handle_id: "big-late", name: "ABC-123 1080p", size: "9GB", date: "2026-05-09" }),
    ];
    expect(pickRdCandidate(rows, preferBigger)?.row.handle_id).toBe("small-early");
  });

  it("does not mutate the input array", () => {
    const rows = [
      row({ handle_id: "a", name: "ABC-123 1080p", date: "2026-05-09" }),
      row({ handle_id: "b", name: "hhd800.com@ABC-123 1080p", date: "2019-01-01" }),
    ];
    const before = rows.map((r) => r.handle_id);
    pickRdCandidate(rows, preferBigger);
    expect(rows.map((r) => r.handle_id)).toEqual(before);
  });
});

describe("summarizeRdLikelihood", () => {
  it("buckets the five classes into high / low / unrated", () => {
    const classes: RdRowClass[] = [
      "prefix_hd",
      "hd",
      "plain",
      "plain",
      "prefix_only",
      "unknown",
    ];
    expect(summarizeRdLikelihood(classes)).toEqual({ high: 2, low: 2, unrated: 2 });
  });

  it("empty input → all zeros", () => {
    expect(summarizeRdLikelihood([])).toEqual({ high: 0, low: 0, unrated: 0 });
  });

  it("counts a single-class list", () => {
    expect(summarizeRdLikelihood(["plain", "plain", "plain"])).toEqual({
      high: 0,
      low: 3,
      unrated: 0,
    });
  });
});
