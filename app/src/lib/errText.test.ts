import { describe, expect, it } from "vitest";
import { errText } from "./errText";

describe("errText", () => {
  it("extracts message from an Error instance", () => {
    expect(errText(new Error("boom"))).toBe("boom");
  });
  it("returns plain strings unchanged", () => {
    expect(errText("raw-failure")).toBe("raw-failure");
  });
  it("stringifies numbers", () => {
    expect(errText(42)).toBe("42");
  });
  it("stringifies plain objects via String()", () => {
    expect(errText({ code: "x" })).toBe("[object Object]");
  });
});
