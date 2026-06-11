import { describe, expect, it } from "vitest";
import {
  applyGroupPick,
  dedupeByHandleId,
  filterRows,
  isHd,
  isManualGroup,
  matchesKeyword,
  parseFileCount,
  parseSizeGb,
  processGroupRows,
  sortRows,
} from "./magnetUtils";
import {
  defaultFilterState,
  type GroupPick,
  type MagnetRow,
  type ScrapedGroup,
} from "./types";

const row = (over: Partial<MagnetRow> = {}): MagnetRow => ({
  handle_id: "h1",
  name: "SNOS-192",
  size: "5.67GB, 5個文件",
  tags: ["高清"],
  date: "2026-05-09",
  magnet_redacted: "magnet:?xt=urn:btih:0201592f...",
  ...over,
});

describe("parseSizeGb", () => {
  it("parses GB", () => {
    expect(parseSizeGb("5.67GB, 5個文件")).toBeCloseTo(5.67, 5);
  });
  it("parses MB and converts to GB", () => {
    expect(parseSizeGb("512MB, 1個文件")).toBeCloseTo(0.5, 5);
  });
  it("returns 0 on garbage", () => {
    expect(parseSizeGb("無法解析")).toBe(0);
    expect(parseSizeGb("")).toBe(0);
  });
});

describe("parseFileCount", () => {
  it("parses count", () => {
    expect(parseFileCount("5.67GB, 5個文件")).toBe(5);
    expect(parseFileCount("512MB, 1個文件")).toBe(1);
  });
  it("returns 999 on missing", () => {
    expect(parseFileCount("5.67GB")).toBe(999);
    expect(parseFileCount("")).toBe(999);
  });
});

describe("matchesKeyword", () => {
  const r = row({ name: "SNOS-192", tags: ["高清"], date: "2026-05-09" });
  it("matches across name/tags/date", () => {
    expect(matchesKeyword(r, "snos")).toBe(true);
    expect(matchesKeyword(r, "高清")).toBe(true);
    expect(matchesKeyword(r, "2026-05")).toBe(true);
  });
  it("is case-insensitive", () => {
    expect(matchesKeyword(r, "SNOS-192")).toBe(true);
    expect(matchesKeyword(r, "Snos")).toBe(true);
  });
  it("empty needle matches everything", () => {
    expect(matchesKeyword(r, "")).toBe(true);
  });
  it("no-match returns false", () => {
    expect(matchesKeyword(r, "ipzz")).toBe(false);
  });
});

describe("isHd", () => {
  it("matches the 高清 tag", () => {
    expect(isHd(row({ tags: ["高清"] }))).toBe(true);
  });
  it("matches HD case-insensitive", () => {
    expect(isHd(row({ tags: ["hd"] }))).toBe(true);
    expect(isHd(row({ tags: ["HD"] }))).toBe(true);
  });
  it("returns false for missing", () => {
    expect(isHd(row({ tags: [] }))).toBe(false);
    expect(isHd(row({ tags: ["other"] }))).toBe(false);
  });
});

describe("filterRows", () => {
  const rows: MagnetRow[] = [
    row({ handle_id: "a", size: "5.67GB, 2個文件", tags: ["高清"] }),
    row({ handle_id: "b", size: "1.2GB, 7個文件", tags: [] }),
    row({ handle_id: "c", size: "200MB, 1個文件", tags: ["高清"] }),
  ];

  it("respects HD-only", () => {
    const f = { ...defaultFilterState(), hd_only: true };
    expect(filterRows(rows, f).map((r) => r.handle_id)).toEqual(["a", "c"]);
  });

  it("respects min_size_gb (>=)", () => {
    const f = { ...defaultFilterState(), min_size_gb: 2 };
    expect(filterRows(rows, f).map((r) => r.handle_id)).toEqual(["a"]);
  });

  it("respects max_size_gb (<=)", () => {
    const f = { ...defaultFilterState(), max_size_gb: 2 };
    expect(filterRows(rows, f).map((r) => r.handle_id)).toEqual(["b", "c"]);
  });

  it("does not mutate input", () => {
    const f = { ...defaultFilterState(), hd_only: true };
    const before = rows.map((r) => r.handle_id);
    filterRows(rows, f);
    expect(rows.map((r) => r.handle_id)).toEqual(before);
  });

  it("0 / null bounds are treated as 'no bound'", () => {
    const f = { ...defaultFilterState(), min_size_gb: 0, max_size_gb: null };
    expect(filterRows(rows, f)).toHaveLength(3);
  });
});

describe("applyGroupPick", () => {
  const rows: MagnetRow[] = [
    row({ handle_id: "small", size: "200MB, 1個文件" }),
    row({ handle_id: "big", size: "5.67GB, 5個文件" }),
    row({ handle_id: "few", size: "4GB, 2個文件" }),
  ];

  it("all returns input unchanged (but copy)", () => {
    const out = applyGroupPick(rows, "all");
    expect(out).toEqual(rows);
    expect(out).not.toBe(rows); // new array
  });

  it("largest picks the biggest by GB", () => {
    expect(applyGroupPick(rows, "largest").map((r) => r.handle_id)).toEqual(["big"]);
  });

  it("smallest picks the lowest GB", () => {
    expect(applyGroupPick(rows, "smallest").map((r) => r.handle_id)).toEqual(["small"]);
  });

  it("fewest_files prefers fewer files; ties broken by larger size", () => {
    const tied: MagnetRow[] = [
      row({ handle_id: "tie-small", size: "1GB, 2個文件" }),
      row({ handle_id: "tie-big", size: "4GB, 2個文件" }),
      row({ handle_id: "many", size: "10GB, 7個文件" }),
    ];
    expect(applyGroupPick(tied, "fewest_files").map((r) => r.handle_id)).toEqual([
      "tie-big",
    ]);
  });

  it("empty input → empty output", () => {
    expect(applyGroupPick([], "largest")).toEqual([]);
  });

  it("unknown pick value falls through to a defensive copy of rows", () => {
    // Cast through unknown so we can exercise the default branch even
    // though the type system would normally rule this out.
    const out = applyGroupPick(rows, "weird" as unknown as GroupPick);
    expect(out).toEqual(rows);
    expect(out).not.toBe(rows);
  });
});

describe("sortRows", () => {
  const rows: MagnetRow[] = [
    row({ handle_id: "a", name: "AAA", size: "1GB, 1個文件", date: "2026-01-01", tags: ["x"] }),
    row({ handle_id: "b", name: "BBB", size: "5.67GB, 5個文件", date: "2026-05-09", tags: ["y"] }),
    row({ handle_id: "c", name: "CCC", size: "300MB, 2個文件", date: "2026-03-01", tags: ["a"] }),
  ];

  it("size column uses parseSizeGb (numeric, not lex)", () => {
    // Lex sort would put "1GB" < "300MB" < "5.67GB". Numeric sort: 0.29 < 1 < 5.67.
    const out = sortRows(rows, "size", "asc").map((r) => r.handle_id);
    expect(out).toEqual(["c", "a", "b"]);
  });

  it("desc reverses asc", () => {
    const asc = sortRows(rows, "size", "asc");
    const desc = sortRows(rows, "size", "desc");
    expect(desc.map((r) => r.handle_id)).toEqual(asc.map((r) => r.handle_id).reverse());
  });

  it("name sorts lexicographically", () => {
    const out = sortRows(rows, "name", "asc").map((r) => r.handle_id);
    expect(out).toEqual(["a", "b", "c"]);
  });

  it("date sorts lexicographically (ISO 8601)", () => {
    const out = sortRows(rows, "date", "asc").map((r) => r.handle_id);
    expect(out).toEqual(["a", "c", "b"]);
  });

  it("null column returns input order (copy)", () => {
    const out = sortRows(rows, null, "asc");
    expect(out.map((r) => r.handle_id)).toEqual(["a", "b", "c"]);
    expect(out).not.toBe(rows);
  });

  it("tags column sorts by joined tag list", () => {
    // rows above have tags ["x"], ["y"], ["a"] — asc order is a < x < y.
    const out = sortRows(rows, "tags", "asc").map((r) => r.handle_id);
    expect(out).toEqual(["c", "a", "b"]);
    const desc = sortRows(rows, "tags", "desc").map((r) => r.handle_id);
    expect(desc).toEqual(["b", "a", "c"]);
  });
});

describe("processGroupRows", () => {
  const group: ScrapedGroup = {
    url: "https://javdb.com/v/x",
    status: "ok",
    finished_at: null,
    error: null,
    result: {
      engine: "curl_cffi",
      url: "https://javdb.com/v/x",
      code: "SNOS-192",
      title: "t",
      magnet_count: 3,
      magnets: [
        row({ handle_id: "big", size: "5.67GB, 5個文件", tags: ["高清"] }),
        row({ handle_id: "small", size: "200MB, 1個文件", tags: ["高清"] }),
        row({ handle_id: "no-hd", size: "2GB, 2個文件", tags: [] }),
      ],
    },
  };

  it("filter → group_pick=largest → sort", () => {
    const f = { ...defaultFilterState(), hd_only: true, group_pick: "largest" as const };
    const out = processGroupRows(group, f, null, "asc");
    expect(out.map((r) => r.handle_id)).toEqual(["big"]);
  });

  it("returns [] when result is null", () => {
    const empty: ScrapedGroup = { ...group, result: null };
    expect(processGroupRows(empty, defaultFilterState(), null, "asc")).toEqual([]);
  });

  it("filter rules out everything → empty", () => {
    const f = { ...defaultFilterState(), min_size_gb: 999 };
    expect(processGroupRows(group, f, null, "asc")).toEqual([]);
  });

  // Manual (pasted) groups: rows have no size/tags/date, and represent
  // explicit user intent — the filter and group-pick stages must not
  // touch them, only sorting.
  const manualGroup: ScrapedGroup = {
    url: "manual://1718000000000",
    status: "ok",
    finished_at: null,
    error: null,
    result: {
      engine: "manual",
      url: "manual://1718000000000",
      code: "(直接貼上 2)",
      title: "",
      magnet_count: 2,
      magnets: [
        row({ handle_id: "m1", name: "BBB-222", size: "", tags: [], date: "" }),
        row({ handle_id: "m2", name: "AAA-111", size: "", tags: [], date: "" }),
      ],
    },
  };

  it("manual groups bypass keyword/HD/size filters and group-pick", () => {
    const f = {
      ...defaultFilterState(),
      keyword: "no-such-code",
      hd_only: true,
      min_size_gb: 5,
      group_pick: "largest" as const,
    };
    const out = processGroupRows(manualGroup, f, null, "asc");
    expect(out.map((r) => r.handle_id)).toEqual(["m1", "m2"]);
  });

  it("manual groups still honor sorting", () => {
    const out = processGroupRows(manualGroup, defaultFilterState(), "name", "asc");
    expect(out.map((r) => r.handle_id)).toEqual(["m2", "m1"]);
  });
});

describe("isManualGroup", () => {
  it("true for manual:// synthetic groups", () => {
    expect(isManualGroup({ url: "manual://1718000000000" })).toBe(true);
  });
  it("false for scraped https groups", () => {
    expect(isManualGroup({ url: "https://javdb.com/v/x" })).toBe(false);
  });
});

describe("dedupeByHandleId", () => {
  it("returns input unchanged when all handle_ids are unique", () => {
    const rows = [
      { handle_id: "h1", code: "A" },
      { handle_id: "h2", code: "B" },
      { handle_id: "h3", code: "C" },
    ];
    expect(dedupeByHandleId(rows)).toEqual(rows);
  });

  it("drops later rows with a repeated handle_id (keeps first occurrence)", () => {
    const rows = [
      { handle_id: "h1", code: "first-A" },
      { handle_id: "h2", code: "B" },
      { handle_id: "h1", code: "second-A" },
      { handle_id: "h2", code: "second-B" },
    ];
    expect(dedupeByHandleId(rows)).toEqual([
      { handle_id: "h1", code: "first-A" },
      { handle_id: "h2", code: "B" },
    ]);
  });

  it("empty input → empty output", () => {
    expect(dedupeByHandleId([])).toEqual([]);
  });

  it("preserves original order of first occurrences", () => {
    const rows = [
      { handle_id: "c", n: 1 },
      { handle_id: "a", n: 2 },
      { handle_id: "b", n: 3 },
      { handle_id: "a", n: 4 },
      { handle_id: "c", n: 5 },
    ];
    expect(dedupeByHandleId(rows).map((r) => r.handle_id)).toEqual(["c", "a", "b"]);
  });
});

describe("coverage gap fillers", () => {
  // matchesKeyword: keyword found in `size` (not in name/date/tags).
  it("matchesKeyword finds needle in size", () => {
    const r = row({ name: "ABC-123", size: "5.67GB, 5個文件", tags: ["x"], date: "2026-01-01" });
    expect(matchesKeyword(r, "GB")).toBe(true);
  });

  // filterRows: keyword that matches NO row gets dropped (false branch on L68).
  it("filterRows drops rows that don't match keyword", () => {
    const r1 = row({ name: "ABC-001", handle_id: "h1" });
    const r2 = row({ name: "XYZ-999", handle_id: "h2" });
    const out = filterRows([r1, r2], { ...defaultFilterState(), keyword: "XYZ" });
    expect(out.map((r) => r.handle_id)).toEqual(["h2"]);
  });

  // applyGroupPick "smallest": reduce path picks the row with the lowest size.
  // Order matters — start with the largest so the `<` branch fires twice.
  it("applyGroupPick smallest returns the smallest row", () => {
    const big = row({ handle_id: "big", size: "5GB, 5個文件" });
    const mid = row({ handle_id: "mid", size: "3GB, 3個文件" });
    const small = row({ handle_id: "small", size: "1GB, 1個文件" });
    const out = applyGroupPick([big, mid, small], "smallest" as GroupPick);
    expect(out).toHaveLength(1);
    expect(out[0].handle_id).toBe("small");
  });

  // applyGroupPick "fewest_files": non-tie path → pick row with strictly fewer files.
  it("applyGroupPick fewest_files picks by file count when not tied", () => {
    const many = row({ handle_id: "many", size: "1GB, 10個文件" });
    const few = row({ handle_id: "few", size: "1GB, 2個文件" });
    const out = applyGroupPick([many, few], "fewest_files" as GroupPick);
    expect(out).toHaveLength(1);
    expect(out[0].handle_id).toBe("few");
  });

  // applyGroupPick "fewest_files": file-count tie → break on size (prefer larger).
  it("applyGroupPick fewest_files breaks ties by larger size", () => {
    const small = row({ handle_id: "small", size: "1GB, 3個文件" });
    const large = row({ handle_id: "large", size: "10GB, 3個文件" });
    const out = applyGroupPick([small, large], "fewest_files" as GroupPick);
    expect(out).toHaveLength(1);
    expect(out[0].handle_id).toBe("large");
  });

  // sortRows "tags" column joins tags with comma and compares.
  it("sortRows orders by tags string", () => {
    const a = row({ handle_id: "a", tags: ["b-tag"] });
    const b = row({ handle_id: "b", tags: ["a-tag"] });
    const sorted = sortRows([a, b], "tags", "asc");
    expect(sorted.map((r) => r.handle_id)).toEqual(["b", "a"]);
  });

  // sortRows "date" column branch.
  it("sortRows orders by date string", () => {
    const a = row({ handle_id: "a", date: "2026-05-01" });
    const b = row({ handle_id: "b", date: "2026-01-15" });
    const sorted = sortRows([a, b], "date", "asc");
    expect(sorted.map((r) => r.handle_id)).toEqual(["b", "a"]);
  });

  // sortRows "code" column shares the name-compare branch with "name" but
  // exercises a different SortColumn discriminant.
  it("sortRows orders by code (same path as name)", () => {
    const a = row({ handle_id: "a", name: "ZZZ-999" });
    const b = row({ handle_id: "b", name: "AAA-111" });
    const sorted = sortRows([a, b], "code", "asc");
    expect(sorted.map((r) => r.handle_id)).toEqual(["b", "a"]);
  });
});
