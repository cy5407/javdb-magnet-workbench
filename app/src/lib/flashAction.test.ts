import { beforeEach, describe, expect, it, vi } from "vitest";
import { createFlashController } from "./flashAction";

describe("createFlashController", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  it("flash() adds the key to the reactive set immediately", () => {
    const ctl = createFlashController();
    ctl.flash("save-btn");
    expect(ctl.keys.has("save-btn")).toBe(true);
  });

  it("flash() auto-removes the key after default 1200ms", () => {
    const ctl = createFlashController();
    ctl.flash("save-btn");
    expect(ctl.keys.has("save-btn")).toBe(true);

    vi.advanceTimersByTime(1199);
    expect(ctl.keys.has("save-btn")).toBe(true);

    vi.advanceTimersByTime(1);
    expect(ctl.keys.has("save-btn")).toBe(false);
  });

  it("flash() honors a custom durationMs", () => {
    const ctl = createFlashController();
    ctl.flash("save-btn", 500);
    vi.advanceTimersByTime(499);
    expect(ctl.keys.has("save-btn")).toBe(true);
    vi.advanceTimersByTime(1);
    expect(ctl.keys.has("save-btn")).toBe(false);
  });

  it("flash() called twice on the same key restarts the timer (debounce)", () => {
    // Why this matters: a user mashing the copy button should keep seeing
    // "已複製 ✓" until 1.2s after the LAST click, not the first one.
    const ctl = createFlashController();
    ctl.flash("save-btn");
    vi.advanceTimersByTime(1000);
    ctl.flash("save-btn"); // second click 1000ms in
    vi.advanceTimersByTime(1199);
    expect(ctl.keys.has("save-btn")).toBe(true); // still flashing (2199ms total)
    vi.advanceTimersByTime(1);
    expect(ctl.keys.has("save-btn")).toBe(false); // 1200ms after the 2nd click
  });

  it("run() returns the action's resolved value and flashes the key on success", async () => {
    const ctl = createFlashController();
    const promise = ctl.run("save-btn", async () => "result-value");
    await expect(promise).resolves.toBe("result-value");
    expect(ctl.keys.has("save-btn")).toBe(true);

    vi.advanceTimersByTime(1200);
    expect(ctl.keys.has("save-btn")).toBe(false);
  });

  it("run() does NOT flash and re-throws when the action rejects", async () => {
    // Why: flashing "✓" after a failed save would lie to the user. The
    // wrapper must stay quiet on failure so the caller can surface the
    // error message instead.
    const ctl = createFlashController();
    const err = new Error("boom");
    await expect(ctl.run("save-btn", async () => { throw err; })).rejects.toBe(err);
    expect(ctl.keys.has("save-btn")).toBe(false);
  });

  it("dispose() clears active timers and keys set", () => {
    const ctl = createFlashController();
    ctl.flash("btn-1");
    ctl.flash("btn-2");
    expect(ctl.keys.has("btn-1")).toBe(true);
    expect(ctl.keys.has("btn-2")).toBe(true);

    ctl.dispose();
    expect(ctl.keys.size).toBe(0);
    vi.advanceTimersByTime(1200);
    expect(ctl.keys.has("btn-1")).toBe(false);
  });
});
