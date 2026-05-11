import { describe, expect, it } from "vitest";
import {
  validateCacheWaitSeconds,
  validateFilePick,
  validateMinSizeMb,
  validateScale,
  validateSettingsDraft,
  validateTheme,
  validateWaitTimeoutSeconds,
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
    wait_timeout_seconds: 300,
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
  it("rejects non-integer", () => {
    expect(validateCacheWaitSeconds(15.5)).toMatch(/整數/);
  });
});

describe("validateWaitTimeoutSeconds", () => {
  it("rejects 29 (below floor)", () => {
    expect(validateWaitTimeoutSeconds(29)).toMatch(/30/);
  });
  it("accepts 30", () => {
    expect(validateWaitTimeoutSeconds(30)).toBeNull();
  });
  it("accepts 300", () => {
    expect(validateWaitTimeoutSeconds(300)).toBeNull();
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
  it("empty rejected", () => {
    expect(validateScale("")).toMatch(/空/);
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
        wait_timeout_seconds: 1,
      },
    });
    const errs = validateSettingsDraft(bad);
    expect(Object.keys(errs).sort()).toEqual([
      "rd.cache_wait_seconds",
      "rd.file_pick",
      "rd.min_size_mb",
      "rd.wait_timeout_seconds",
      "ui.scale",
      "ui.theme",
    ]);
  });
  it("ignores api_token (frontend never validates it here)", () => {
    // api_token must remain empty on save; the editor never carries
    // a value. If something put a value in, validateSettingsDraft
    // should still not flag it (the Rust side will clear it).
    const odd = draft({ rd: { api_token: "leaked", file_pick: "smart",
      min_size_mb: 0, cache_wait_seconds: 5, wait_timeout_seconds: 30 } });
    expect(validateSettingsDraft(odd)).toEqual({});
  });
});
