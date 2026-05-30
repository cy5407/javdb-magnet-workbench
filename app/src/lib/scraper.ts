// Batch scrape worker: per-URL fetch_javdb invoke with anti-rate-limit pacing.
//
// Behavior contract (see spec §10):
//   - Sequential: never overlap requests (sidecar already serializes, but
//     spacing avoids JavDB-side 429 pile-ups too).
//   - Random delay 3000–6000ms BETWEEN urls (not before the first).
//   - On rate-limit-flavored error, sleep 10000–15000ms and retry exactly once.
//   - Anything else (auth, parse, network) is recorded and we move on.
//   - Reports progress per-url via onProgress so the UI can update i/N.

import { invoke } from "@tauri-apps/api/core";
import { errText } from "./errText";
import type { FetchResult, ScrapedGroup } from "./types";

const DELAY_MIN_MS = 3000;
const DELAY_MAX_MS = 6000;
const RETRY_WAIT_MIN_MS = 10000;
const RETRY_WAIT_MAX_MS = 15000;

const RATE_LIMIT_PATTERNS = [
  /\b429\b/i,
  /rate[\s-]?limit/i,
  /cloudflare/i,
  /too many requests/i,
];

export function isRateLimitError(message: string): boolean {
  if (!message) return false;
  return RATE_LIMIT_PATTERNS.some((re) => re.test(message));
}

export type JitterFn = () => number;

/**
 * Non-cryptographic fractional value in [0, 1) sourced from Web Crypto.
 *
 * Sonar's S2245 ("weak cryptography") fires on every `Math.random()`
 * regardless of intent, so even though our use here is purely jitter
 * (anti-rate-limit pacing, not a security primitive) we go through
 * `crypto.getRandomValues`. All our deploy targets expose it:
 * Tauri WebView2, vitest's jsdom 22+, and Node 19+. Tests that need
 * deterministic values can inject `rng` into `randomDelayMs` instead
 * of mocking the global.
 */
function jitterFraction(): number {
  const buf = new Uint32Array(1);
  // globalThis.crypto is the W3C Web Crypto entrypoint; present in
  // browsers, WebView2, jsdom, and Node 19+.
  globalThis.crypto.getRandomValues(buf);
  // 2 ** 32 = upper bound of Uint32 range; divisor maps to [0, 1).
  return buf[0] / 2 ** 32;
}

/**
 * Random integer in [min, max] inclusive. Used for between-URL pacing
 * jitter — not crypto-sensitive, but bits come from Web Crypto so
 * Sonar's weak-crypto rule doesn't flag this path. Tests can pass a
 * deterministic `rng` (e.g. `() => 0`) without touching the global.
 */
export function randomDelayMs(
  min: number,
  max: number,
  rng: JitterFn = jitterFraction,
): number {
  if (max <= min) return min;
  return Math.floor(min + rng() * (max - min + 1));
}

export type SleepFn = (ms: number) => Promise<void>;

const realSleep: SleepFn = (ms) =>
  new Promise<void>((resolve) => setTimeout(resolve, ms));

export interface ScrapeProgressEvent {
  /** 1-based position in the batch */
  index: number;
  total: number;
  group: ScrapedGroup;
}

export interface ScrapeOptions {
  /** Abort flag the caller can flip to stop after the in-flight request */
  signal?: AbortSignal;
  /** Sleep impl (overridable for tests) */
  sleep?: SleepFn;
  /** Pacing overrides (tests use 0/0) */
  delayRange?: [number, number];
  retryWaitRange?: [number, number];
  /** Invoke override (tests inject a fake) */
  fetcher?: (url: string) => Promise<FetchResult>;
}

// Production wrapper around Tauri invoke; unit tests always inject a fake fetcher.
/* c8 ignore next 2 */
const defaultFetcher = (url: string): Promise<FetchResult> =>
  invoke<FetchResult>("fetch_javdb", { url });

/**
 * Normalize whatever the user pasted into the textarea into a deduped,
 * trimmed list of URL strings. Empty lines, comment lines (`#`),
 * and obvious garbage are dropped.
 */
export function parseUrlBatch(raw: string): string[] {
  if (!raw) return [];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    if (trimmed.startsWith("#")) continue;
    if (!/^https?:\/\//i.test(trimmed)) continue;
    if (seen.has(trimmed)) continue;
    seen.add(trimmed);
    out.push(trimmed);
  }
  return out;
}

/**
 * Parse a "paste magnets directly" textarea into a deduped list of magnet
 * URIs. Strips inline whitespace, drops blank/comment lines, rejects
 * anything that doesn't start with `magnet:`. Sidecar dedupes again on
 * its side; this dedupe is mainly UX (the user sees fewer rows).
 */
export function parseMagnetBatch(raw: string): string[] {
  if (!raw) return [];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    if (trimmed.startsWith("#")) continue;
    if (!/^magnet:/i.test(trimmed)) continue;
    if (seen.has(trimmed)) continue;
    seen.add(trimmed);
    out.push(trimmed);
  }
  return out;
}

interface ResolvedScrapeOptions {
  sleep: SleepFn;
  fetcher: (url: string) => Promise<FetchResult>;
  delayRange: [number, number];
  retryWaitRange: [number, number];
  signal?: AbortSignal;
}

function resolveScrapeOptions(opts: ScrapeOptions): ResolvedScrapeOptions {
  return {
    sleep: opts.sleep ?? realSleep,
    fetcher: opts.fetcher ?? defaultFetcher,
    delayRange: opts.delayRange ?? [DELAY_MIN_MS, DELAY_MAX_MS],
    retryWaitRange: opts.retryWaitRange ?? [RETRY_WAIT_MIN_MS, RETRY_WAIT_MAX_MS],
    signal: opts.signal,
  };
}

/**
 * Try a single URL with at most one retry after a rate-limit error.
 * Mutates `group` in place to record the outcome (status/result/error).
 */
async function fetchGroupWithRetry(
  group: ScrapedGroup,
  resolved: ResolvedScrapeOptions,
): Promise<void> {
  // attempt 0 = first try; attempt 1 = single retry after rate-limit
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      group.result = await resolved.fetcher(group.url);
      group.status = "ok";
      group.error = null;
      return;
    } catch (e) {
      const message = errText(e);
      const canRetry =
        attempt === 0 &&
        isRateLimitError(message) &&
        !resolved.signal?.aborted;
      if (!canRetry) {
        group.error = message;
        group.status = "error";
        return;
      }
      await resolved.sleep(randomDelayMs(...resolved.retryWaitRange));
    }
  }
}

/**
 * Run the batch. `onProgress` fires after every group settles (ok or error).
 * Returns the final array of groups in the order URLs were submitted.
 */
export async function scrapeBatch(
  urls: string[],
  onProgress: (ev: ScrapeProgressEvent) => void,
  opts: ScrapeOptions = {},
): Promise<ScrapedGroup[]> {
  const resolved = resolveScrapeOptions(opts);

  const groups: ScrapedGroup[] = urls.map((url) => ({
    url,
    status: "pending",
    result: null,
    error: null,
    finished_at: null,
  }));

  for (let i = 0; i < groups.length; i++) {
    if (resolved.signal?.aborted) break;

    if (i > 0) {
      await resolved.sleep(randomDelayMs(...resolved.delayRange));
      if (resolved.signal?.aborted) break;
    }

    const group = groups[i];
    group.status = "fetching";
    await fetchGroupWithRetry(group, resolved);
    group.finished_at = new Date().toISOString();
    onProgress({ index: i + 1, total: groups.length, group });
  }

  return groups;
}
