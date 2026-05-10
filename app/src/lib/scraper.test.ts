import { describe, expect, it, vi } from "vitest";
import {
  isRateLimitError,
  parseUrlBatch,
  randomDelayMs,
  scrapeBatch,
} from "./scraper";
import type { FetchResult } from "./types";

const fakeResult = (url: string, n = 1): FetchResult => ({
  engine: "curl_cffi",
  url,
  code: "SNOS-192",
  title: "t",
  magnet_count: n,
  magnets: Array.from({ length: n }, (_, i) => ({
    handle_id: `h-${i}`,
    name: "n",
    size: "1GB, 1個文件",
    tags: [],
    date: "",
    magnet_redacted: "magnet:?xt=urn:btih:00000000...",
  })),
});

describe("parseUrlBatch", () => {
  it("trims, dedupes, drops blanks/comments/non-http", () => {
    const raw = [
      "https://javdb.com/v/A",
      "  https://javdb.com/v/B",
      "",
      "# this is a comment",
      "https://javdb.com/v/A", // dup
      "ftp://nope",
      "javascript:alert(1)",
      "https://javdb.com/v/C",
    ].join("\n");
    expect(parseUrlBatch(raw)).toEqual([
      "https://javdb.com/v/A",
      "https://javdb.com/v/B",
      "https://javdb.com/v/C",
    ]);
  });

  it("empty input → []", () => {
    expect(parseUrlBatch("")).toEqual([]);
    expect(parseUrlBatch("   \n  \n")).toEqual([]);
  });
});

describe("isRateLimitError", () => {
  it("matches known rate-limit phrases", () => {
    expect(isRateLimitError("HTTP 429: Too Many Requests")).toBe(true);
    expect(isRateLimitError("cloudflare challenge")).toBe(true);
    expect(isRateLimitError("rate-limit hit")).toBe(true);
    expect(isRateLimitError("Rate Limited")).toBe(true);
  });
  it("does not match generic errors", () => {
    expect(isRateLimitError("404 Not Found")).toBe(false);
    expect(isRateLimitError("connection reset")).toBe(false);
    expect(isRateLimitError("")).toBe(false);
  });
});

describe("randomDelayMs", () => {
  it("min===max returns min", () => {
    expect(randomDelayMs(500, 500)).toBe(500);
  });
  it("stays within bounds", () => {
    for (let i = 0; i < 50; i++) {
      const v = randomDelayMs(100, 200);
      expect(v).toBeGreaterThanOrEqual(100);
      expect(v).toBeLessThanOrEqual(200);
    }
  });
});

describe("scrapeBatch", () => {
  const noSleep = vi.fn().mockResolvedValue(undefined);

  it("calls fetcher once per url, in order", async () => {
    const fetcher = vi.fn(async (url: string) => fakeResult(url));
    const progress = vi.fn();
    const out = await scrapeBatch(
      ["https://javdb.com/v/A", "https://javdb.com/v/B"],
      progress,
      { sleep: noSleep, fetcher, delayRange: [0, 0], retryWaitRange: [0, 0] },
    );
    expect(fetcher.mock.calls.map((c) => c[0])).toEqual([
      "https://javdb.com/v/A",
      "https://javdb.com/v/B",
    ]);
    expect(out).toHaveLength(2);
    expect(out[0].status).toBe("ok");
    expect(out[1].status).toBe("ok");
    expect(progress).toHaveBeenCalledTimes(2);
  });

  it("retries exactly once on rate-limit error", async () => {
    let attempts = 0;
    const fetcher = vi.fn(async (url: string) => {
      attempts++;
      if (attempts === 1) throw new Error("HTTP 429");
      return fakeResult(url);
    });
    const out = await scrapeBatch(
      ["https://javdb.com/v/A"],
      () => {},
      { sleep: noSleep, fetcher, delayRange: [0, 0], retryWaitRange: [0, 0] },
    );
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(out[0].status).toBe("ok");
  });

  it("does not retry on non-rate-limit errors", async () => {
    const fetcher = vi.fn(async () => {
      throw new Error("404 Not Found");
    });
    const out = await scrapeBatch(
      ["https://javdb.com/v/A"],
      () => {},
      { sleep: noSleep, fetcher, delayRange: [0, 0], retryWaitRange: [0, 0] },
    );
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(out[0].status).toBe("error");
    expect(out[0].error).toContain("404");
  });

  it("gives up after one retry on persistent rate-limit", async () => {
    const fetcher = vi.fn(async () => {
      throw new Error("HTTP 429");
    });
    const out = await scrapeBatch(
      ["https://javdb.com/v/A"],
      () => {},
      { sleep: noSleep, fetcher, delayRange: [0, 0], retryWaitRange: [0, 0] },
    );
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(out[0].status).toBe("error");
    expect(out[0].error).toContain("429");
  });

  it("AbortSignal stops further URLs", async () => {
    const ctrl = new AbortController();
    const urls = ["https://a", "https://b", "https://c"];
    const fetcher = vi.fn(async (u: string) => {
      if (u === "https://a") ctrl.abort();
      return fakeResult(u);
    });
    const out = await scrapeBatch(urls, () => {}, {
      sleep: noSleep,
      fetcher,
      delayRange: [0, 0],
      retryWaitRange: [0, 0],
      signal: ctrl.signal,
    });
    // First URL completes, the others should remain pending.
    expect(out[0].status).toBe("ok");
    expect(out[1].status).toBe("pending");
    expect(out[2].status).toBe("pending");
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("emits progress with index/total", async () => {
    const events: { index: number; total: number; status: string }[] = [];
    const fetcher = vi.fn(async (u: string) => fakeResult(u));
    await scrapeBatch(["https://x", "https://y"], (ev) => {
      events.push({ index: ev.index, total: ev.total, status: ev.group.status });
    }, { sleep: noSleep, fetcher, delayRange: [0, 0], retryWaitRange: [0, 0] });
    expect(events).toEqual([
      { index: 1, total: 2, status: "ok" },
      { index: 2, total: 2, status: "ok" },
    ]);
  });
});
