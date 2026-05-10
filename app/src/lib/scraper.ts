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

/**
 * Random integer in [min, max] inclusive. Math.random is fine for jitter;
 * this is not a crypto-sensitive context.
 */
export function randomDelayMs(min: number, max: number): number {
  if (max <= min) return min;
  return Math.floor(min + Math.random() * (max - min + 1));
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
 * Run the batch. `onProgress` fires after every group settles (ok or error).
 * Returns the final array of groups in the order URLs were submitted.
 */
export async function scrapeBatch(
  urls: string[],
  onProgress: (ev: ScrapeProgressEvent) => void,
  opts: ScrapeOptions = {},
): Promise<ScrapedGroup[]> {
  const sleep = opts.sleep ?? realSleep;
  const fetcher = opts.fetcher ?? defaultFetcher;
  const [delayMin, delayMax] = opts.delayRange ?? [DELAY_MIN_MS, DELAY_MAX_MS];
  const [retryMin, retryMax] =
    opts.retryWaitRange ?? [RETRY_WAIT_MIN_MS, RETRY_WAIT_MAX_MS];

  const groups: ScrapedGroup[] = urls.map((url) => ({
    url,
    status: "pending",
    result: null,
    error: null,
    finished_at: null,
  }));

  for (let i = 0; i < groups.length; i++) {
    if (opts.signal?.aborted) break;

    if (i > 0) {
      await sleep(randomDelayMs(delayMin, delayMax));
      if (opts.signal?.aborted) break;
    }

    const group = groups[i];
    group.status = "fetching";

    let attempt = 0;
    // attempt 0 = first try; attempt 1 = single retry after rate-limit
    while (attempt < 2) {
      try {
        const result = await fetcher(group.url);
        group.result = result;
        group.status = "ok";
        group.error = null;
        break;
      } catch (e) {
        const message = e instanceof Error ? e.message : String(e);
        if (attempt === 0 && isRateLimitError(message) && !opts.signal?.aborted) {
          await sleep(randomDelayMs(retryMin, retryMax));
          attempt++;
          continue;
        }
        group.error = message;
        group.status = "error";
        break;
      }
    }

    group.finished_at = new Date().toISOString();
    onProgress({ index: i + 1, total: groups.length, group });
  }

  return groups;
}
