import { describe, expect, it } from "vitest";
import {
  applyGroupPick,
  filterRows,
  isHd,
  matchesKeyword,
  parseFileCount,
  parseSizeGb,
  processGroupRows,
  sortRows,
} from "./magnetUtils";
import { defaultFilterState, type MagnetRow, type ScrapedGroup } from "./types";

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
});
