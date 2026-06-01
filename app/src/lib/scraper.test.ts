import { describe, expect, it, vi } from "vitest";
import {
  applyScrapeProgressForRun,
  isRateLimitError,
  parseMagnetBatch,
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
  it("trims, dedupes, drops blanks/comments/non-https", () => {
    const raw = [
      "https://javdb.com/v/A",
      "  https://javdb.com/v/B",
      "",
      "# this is a comment",
      "https://javdb.com/v/A", // dup
      "http://javdb.com/v/plaintext",
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

  it("drops http URLs before they reach the HTTPS-only sidecar command", () => {
    expect(parseUrlBatch("http://javdb.com/v/A\nhttps://javdb.com/v/B")).toEqual([
      "https://javdb.com/v/B",
    ]);
  });
});

describe("parseMagnetBatch", () => {
  it("trims, dedupes, drops blanks/comments/non-magnets", () => {
    const raw = [
      "magnet:?xt=urn:btih:abc&dn=A",
      "  magnet:?xt=urn:btih:def&dn=B",
      "",
      "# comment",
      "magnet:?xt=urn:btih:abc&dn=A", // dup
      "https://javdb.com/v/x",         // wrong scheme
      "not a magnet",
    ].join("\n");
    expect(parseMagnetBatch(raw)).toEqual([
      "magnet:?xt=urn:btih:abc&dn=A",
      "magnet:?xt=urn:btih:def&dn=B",
    ]);
  });

  it("MAGNET: prefix is case-insensitive for parsing", () => {
    expect(parseMagnetBatch("MAGNET:?xt=urn:btih:abc")).toEqual([
      "MAGNET:?xt=urn:btih:abc",
    ]);
  });

  it("empty input → []", () => {
    expect(parseMagnetBatch("")).toEqual([]);
    expect(parseMagnetBatch("   \n  \n")).toEqual([]);
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

describe("applyScrapeProgressForRun", () => {
  it("applies progress only for the active run", () => {
    const original = {
      groups: [],
      scrapeProgress: { done: 0, total: 0 },
    };
    const group = {
      url: "https://javdb.com/v/A",
      status: "ok" as const,
      result: fakeResult("https://javdb.com/v/A"),
      error: null,
      finished_at: "2026-06-01T00:00:00.000Z",
    };

    const applied = applyScrapeProgressForRun(
      original,
      { index: 1, total: 1, group },
      7,
      7,
    );
    expect(applied.groups).toEqual([group]);
    expect(applied.scrapeProgress).toEqual({ done: 1, total: 1 });

    const stale = applyScrapeProgressForRun(
      { groups: [], scrapeProgress: { done: 0, total: 0 } },
      { index: 1, total: 1, group },
      8,
      7,
    );
    expect(stale.groups).toEqual([]);
    expect(stale.scrapeProgress).toEqual({ done: 0, total: 0 });
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

  it("aborting during retry backoff prevents the retry request", async () => {
    const ctrl = new AbortController();
    const sleep = vi.fn(async () => {
      ctrl.abort();
    });
    const progress = vi.fn();
    const fetcher = vi.fn(async () => {
      throw new Error("HTTP 429");
    });

    const out = await scrapeBatch(
      ["https://javdb.com/v/A"],
      progress,
      {
        sleep,
        fetcher,
        delayRange: [0, 0],
        retryWaitRange: [10, 10],
        signal: ctrl.signal,
      },
    );

    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(sleep).toHaveBeenCalledTimes(1);
    expect(out[0].status).toBe("pending");
    expect(out[0].finished_at).toBeNull();
    expect(progress).not.toHaveBeenCalled();
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

  it("does not sleep before the first url, sleeps once between two urls", async () => {
    const sleep = vi.fn().mockResolvedValue(undefined);
    const fetcher = vi.fn(async (url: string) => fakeResult(url));
    await scrapeBatch(
      ["https://javdb.com/v/A", "https://javdb.com/v/B"],
      () => {},
      { sleep, fetcher, delayRange: [10, 10], retryWaitRange: [0, 0] },
    );
    expect(sleep).toHaveBeenCalledTimes(1);
    expect(sleep).toHaveBeenCalledWith(10);
    expect(fetcher).toHaveBeenCalledTimes(2);
    const [firstFetch, secondFetch] = fetcher.mock.invocationCallOrder;
    const [sleepCall] = sleep.mock.invocationCallOrder;
    expect(firstFetch).toBeLessThan(sleepCall);
    expect(sleepCall).toBeLessThan(secondFetch);
  });

  it("aborting during between-url sleep leaves the second url pending", async () => {
    const ctrl = new AbortController();
    const sleep = vi.fn(async () => {
      ctrl.abort();
    });
    const fetcher = vi.fn(async (u: string) => fakeResult(u));
    const out = await scrapeBatch(
      ["https://javdb.com/v/A", "https://javdb.com/v/B"],
      () => {},
      {
        sleep,
        fetcher,
        delayRange: [10, 10],
        retryWaitRange: [0, 0],
        signal: ctrl.signal,
      },
    );
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(fetcher).toHaveBeenCalledWith("https://javdb.com/v/A");
    expect(sleep).toHaveBeenCalledTimes(1);
    expect(out[0].status).toBe("ok");
    expect(out[1].status).toBe("pending");
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

  it("falls back to real setTimeout-based sleep when no sleep override is given", async () => {
    // Cover the default realSleep path. delayRange [0,0] keeps the
    // setTimeout interval at 0ms so the test completes immediately
    // (the wall-clock cost is one event-loop turn, not a real delay).
    const fetcher = vi.fn(async (u: string) => fakeResult(u));
    const out = await scrapeBatch(
      ["https://javdb.com/v/A", "https://javdb.com/v/B"],
      () => {},
      { fetcher, delayRange: [0, 0], retryWaitRange: [0, 0] },
    );
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(out[0].status).toBe("ok");
    expect(out[1].status).toBe("ok");
  });

  // Cover the `?? defaultFetcher` / `?? [DELAY...]` / `?? [RETRY...]` right-hand
  // sides in resolveScrapeOptions. With urls=[] the default fetcher is never
  // actually invoked (no Tauri runtime needed in vitest), but the option
  // resolution branch is exercised.
  it("uses default fetcher/delays/retry when options are omitted", async () => {
    const out = await scrapeBatch([], () => {});
    expect(out).toEqual([]);
  });

  // Cover the catch branch `e instanceof Error ? e.message : String(e)` — the
  // String(e) side fires only when something non-Error is thrown.
  it("stringifies non-Error throws in fetcher", async () => {
    const fetcher = vi.fn(async () => {
      // Throwing a plain string is legal but bypasses the Error path.
      throw "raw-string-failure";
    });
    const out = await scrapeBatch(
      ["https://javdb.com/v/A"],
      () => {},
      { sleep: noSleep, fetcher, delayRange: [0, 0], retryWaitRange: [0, 0] },
    );
    expect(out[0].status).toBe("error");
    expect(out[0].error).toBe("raw-string-failure");
  });
});
