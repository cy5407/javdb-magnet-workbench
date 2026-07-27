import { describe, expect, it } from "vitest";
import {
  validateCacheWaitSeconds,
  validateFilePick,
  validateMinSizeMb,
  validateScale,
  validateSettingsDraft,
  validateTheme,
} from "./settingsValidation";
import type { Settings } from "./types";

const draft = (over: Partial<Settings> = {}): Settings => ({
  version: 1,
  ui: { theme: "light", scale: "auto", ...(over.ui ?? {}) },
  rd: {
    api_token: "",
    file_pick: "smart",
    min_size_mb: 500,
    cache_wait_seconds: 15,
    ...(over.rd ?? {}),
  },
});

describe("validateMinSizeMb", () => {
  it("rejects negative", () => {
    expect(validateMinSizeMb(-1)).toMatch(/不能為負/);
  });
  it("accepts 0", () => {
    expect(validateMinSizeMb(0)).toBeNull();
  });
  it("accepts 500", () => {
    expect(validateMinSizeMb(500)).toBeNull();
  });
  it("rejects non-integer", () => {
    expect(validateMinSizeMb(1.5)).toMatch(/整數/);
  });
  it("rejects NaN", () => {
    expect(validateMinSizeMb(NaN)).toMatch(/數字/);
  });
});

describe("validateCacheWaitSeconds", () => {
  it("rejects 4 (below floor)", () => {
    expect(validateCacheWaitSeconds(4)).toMatch(/5/);
  });
  it("accepts 5", () => {
    expect(validateCacheWaitSeconds(5)).toBeNull();
  });
  it("accepts 30", () => {
    expect(validateCacheWaitSeconds(30)).toBeNull();
  });
  it("accepts 300 (ceiling)", () => {
    expect(validateCacheWaitSeconds(300)).toBeNull();
  });
  it("rejects 301 (above ceiling)", () => {
    expect(validateCacheWaitSeconds(301)).toMatch(/300/);
  });
  it("rejects non-integer", () => {
    expect(validateCacheWaitSeconds(15.5)).toMatch(/整數/);
  });
  it("rejects NaN / Infinity (not finite)", () => {
    expect(validateCacheWaitSeconds(NaN)).toMatch(/數字/);
    expect(validateCacheWaitSeconds(Infinity)).toMatch(/數字/);
  });
});

describe("validateScale", () => {
  it("auto is valid", () => {
    expect(validateScale("auto")).toBeNull();
  });
  it("1.0 is valid", () => {
    expect(validateScale("1.0")).toBeNull();
  });
  it("1.5 is valid", () => {
    expect(validateScale("1.5")).toBeNull();
  });
  it("3.0 is valid", () => {
    expect(validateScale("3.0")).toBeNull();
  });
  it("0.1 below floor", () => {
    expect(validateScale("0.1")).toMatch(/0\.5/);
  });
  it("9 above ceiling", () => {
    expect(validateScale("9")).toMatch(/3/);
  });
  it("abc rejected", () => {
    expect(validateScale("abc")).toMatch(/auto|數字/);
  });
  it("rejects non-standard number formats like 1e0, .5, +1, 0x2", () => {
    expect(validateScale("1e0")).not.toBeNull();
    expect(validateScale(".5")).not.toBeNull();
    expect(validateScale("+1")).not.toBeNull();
    expect(validateScale("0x2")).not.toBeNull();
    expect(validateScale("1")).toBeNull();
    expect(validateScale("1.5")).toBeNull();
  });
  it("empty rejected", () => {
    expect(validateScale("")).toMatch(/空/);
  });
  it("non-string rejected (defensive guard for malformed drafts)", () => {
    // Cast through unknown to mimic a malformed draft where scale is a
    // number rather than a string — the guard rejects it before parsing.
    expect(validateScale(1.5 as unknown as string)).toMatch(/字串/);
    expect(validateScale(null as unknown as string)).toMatch(/字串/);
  });
});

describe("validateFilePick", () => {
  it("smart valid", () => expect(validateFilePick("smart")).toBeNull());
  it("largest valid", () => expect(validateFilePick("largest")).toBeNull());
  it("video valid", () => expect(validateFilePick("video")).toBeNull());
  it("all valid", () => expect(validateFilePick("all")).toBeNull());
  it("unknown rejected", () => {
    expect(validateFilePick("medium")).toMatch(/smart/);
  });
});

describe("validateTheme", () => {
  it("light valid", () => expect(validateTheme("light")).toBeNull());
  it("dark valid", () => expect(validateTheme("dark")).toBeNull());
  it("unknown rejected", () => {
    expect(validateTheme("solarized")).toMatch(/light/);
  });
});

describe("validateSettingsDraft", () => {
  it("valid draft has no errors", () => {
    expect(validateSettingsDraft(draft())).toEqual({});
  });
  it("collects errors from every bad field at once", () => {
    const bad = draft({
      ui: { theme: "neon", scale: "huge" },
      rd: {
        api_token: "",
        file_pick: "weird",
        min_size_mb: -1,
        cache_wait_seconds: 1,
      },
    } as unknown as Partial<Settings>);
    const errs = validateSettingsDraft(bad);
    expect(Object.keys(errs).sort()).toEqual([
      "rd.cache_wait_seconds",
      "rd.file_pick",
      "rd.min_size_mb",
      "ui.scale",
      "ui.theme",
    ]);
  });
  it("ignores api_token (frontend never validates it here)", () => {
    // api_token must remain empty on save; the editor never carries
    // a value. If something put a value in, validateSettingsDraft
    // should still not flag it (the Rust side will clear it).
    const odd = draft({ rd: { api_token: "leaked", file_pick: "smart",
      min_size_mb: 0, cache_wait_seconds: 5 } });
    expect(validateSettingsDraft(odd)).toEqual({});
  });
});
