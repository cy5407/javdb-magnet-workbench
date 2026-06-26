// Batch driver for the M5 send-to-RD flow.
//
// Frontend calls `rd_send_magnet` once per handle_id (Rust command name).
// Each call may take up to `cache_wait` seconds because the sidecar waits
// for RD to either cache-hit or settle into pending. We update an
// `RdSendProgress[]` array between awaits so the UI shows live progress
// without needing event emit.
//
// Errors come back as Rust-side `String` codes (e.g. "rd_token_invalid",
// "rd_no_token", "rd_premium_required", "rd_rate_limited", "unknown_handle").
// We don't translate them here — the UI does, so unit tests stay
// language-agnostic.

import { invoke } from "@tauri-apps/api/core";
import { errText } from "./errText";
import type {
  PendingEntry,
  RdCheckOutcome,
  RdLink,
  RdSendOutcome,
  RdSendProgress,
} from "./types";

export interface RdSendOptions {
  strategy?: string;
  min_size_mb?: number;
  cache_wait?: number;
  /** Display-only metadata persisted to pending_torrents.json on a pending outcome. */
  code?: string;
  size_label?: string;
}

export interface RdSendItem {
  handle_id: string;
  /** Display label for the progress row; usually the JavDB code. */
  code: string;
  /** Display-only — sidecar doesn't see this. */
  size_label?: string;
}

export interface RdSendBatchEvent {
  index: number;
  total: number;
  item: RdSendProgress;
}

export interface RdSendBatchOptions {
  signal?: AbortSignal;
  /** Default options applied to every item in the batch. */
  defaults?: RdSendOptions;
  /** Test seam — replace the Tauri invoke for unit tests. */
  fetcher?: (handle_id: string, opts: RdSendOptions) => Promise<RdSendOutcome>;
}

/**
 * Pure extractor: given one progress row, return the list of RD direct
 * download URLs that should land on the clipboard for THIS row. Returns
 * `[]` for any non-completed status so callers can wire up a per-row
 * "copy" affordance without having to re-check status at the call site.
 */
export function collectDownloadLinksFromRow(row: RdSendProgress): string[] {
  if (row.status !== "completed") return [];
  return row.links
    .map((l) => l.download)
    .filter((d): d is string => typeof d === "string" && d.trim().length > 0);
}

/**
 * Stable sort by `completed_at` ascending. Rows missing `completed_at` are
 * placed using `missingCompletedAtFallback` as their sort key — caller MUST
 * pass this explicitly so the "missing row" position is always an
 * intentional choice (e.g. `lastBatchStartAt` in the UI; `""` to push them
 * before all timestamped rows).
 */
export function sortCompletedRowsByCompletionTime<T extends { completed_at?: string }>(
  rows: T[],
  missingCompletedAtFallback: string,
): T[] {
  return rows
    .map((row, index) => ({
      row,
      index,
      completedAt: row.completed_at ?? missingCompletedAtFallback,
    }))
    .sort((a, b) => {
      if (a.completedAt < b.completedAt) return -1;
      if (a.completedAt > b.completedAt) return 1;
      return a.index - b.index;
    })
    .map((entry) => entry.row);
}

const defaultFetcher = (
  handle_id: string,
  opts: RdSendOptions,
): Promise<RdSendOutcome> =>
  invoke<RdSendOutcome>("rd_send_magnet", { handleId: handle_id, options: opts });

const defaultCheckFetcher = (
  torrent_id: string,
  strategy?: string,
): Promise<RdCheckOutcome> =>
  invoke<RdCheckOutcome>("rd_check_pending", { torrentId: torrent_id, strategy });

/**
 * Run a send-to-RD batch. Returns the final progress array; also emits
 * progress events between awaits so the caller can update the UI live.
 */
export async function sendBatch(
  items: RdSendItem[],
  onProgress: (ev: RdSendBatchEvent) => void,
  opts: RdSendBatchOptions = {},
): Promise<RdSendProgress[]> {
  const fetcher = opts.fetcher ?? defaultFetcher;
  const defaults = opts.defaults ?? {};

  const rows: RdSendProgress[] = items.map((it) => ({
    handle_id: it.handle_id,
    code: it.code,
    size_label: it.size_label,
    status: "pending",
    links: [],
    error_code: null,
  }));

  for (let i = 0; i < items.length; i++) {
    if (opts.signal?.aborted) break;
    const item = items[i];

    rows[i] = { ...rows[i], status: "sending" };
    onProgress({ index: i + 1, total: items.length, item: rows[i] });

    const callOpts: RdSendOptions = {
      ...defaults,
      code: item.code,
      size_label: item.size_label,
    };

    let next: RdSendProgress;
    try {
      const outcome = await fetcher(item.handle_id, callOpts);
      if (outcome.status === "completed") {
        next = {
          ...rows[i],
          status: "completed",
          links: outcome.links,
          error_code: null,
          completed_at: new Date().toISOString(),
          torrent_id: outcome.torrent_id,
        };
      } else {
        next = {
          ...rows[i],
          status: "in_pending",
          links: [],
          error_code: null,
          // Capture torrent_id so a later pending-retry can reconcile
          // this row when it transitions to completed / missing.
          torrent_id: outcome.torrent_id,
        };
      }
    } catch (e) {
      const code = errText(e);
      next = { ...rows[i], status: "error", links: [], error_code: code };
    }

    rows[i] = next;
    onProgress({ index: i + 1, total: items.length, item: next });
  }

  return rows;
}

export interface RdRetryEvent {
  index: number;
  total: number;
  /** Identical fields as the persisted PendingEntry, plus the latest outcome. */
  torrent_id: string;
  entry: PendingEntry;
  result:
    | { kind: "completed"; links: RdLink[]; name: string }
    | { kind: "pending"; rd_status: string; progress: number; name: string }
    | { kind: "missing" }
    | { kind: "error"; error_code: string };
}

export interface RdRetryOptions {
  signal?: AbortSignal;
  fetcher?: (torrent_id: string, strategy?: string) => Promise<RdCheckOutcome>;
}

function findRetryProgressIndex(
  rows: RdSendProgress[],
  ev: RdRetryEvent,
): number {
  const torrentIndex = rows.findIndex((row) => row.torrent_id === ev.torrent_id);
  if (torrentIndex >= 0) return torrentIndex;

  const codeMatches = rows
    .map((row, index) => ({ row, index }))
    .filter(
      ({ row }) =>
        !row.torrent_id &&
        row.status === "in_pending" &&
        row.code === ev.entry.code,
    );
  return codeMatches.length === 1 ? codeMatches[0].index : -1;
}

export function applyRetryEventToProgressRows(
  rows: RdSendProgress[],
  ev: RdRetryEvent,
  completedAt = new Date().toISOString(),
): RdSendProgress[] {
  const index = findRetryProgressIndex(rows, ev);
  if (index < 0) return rows;

  const row = rows[index];
  let next: RdSendProgress | null = null;
  if (ev.result.kind === "completed") {
    next = {
      ...row,
      status: "completed",
      links: ev.result.links,
      error_code: null,
      completed_at: completedAt,
      torrent_id: ev.torrent_id,
    };
  } else if (ev.result.kind === "missing") {
    next = {
      ...row,
      status: "error",
      links: [],
      error_code: "rd_torrent_missing",
      torrent_id: ev.torrent_id,
    };
  }
  if (!next) return rows;

  const out = rows.slice();
  out[index] = next;
  return out;
}

/**
 * Re-poll a list of pending entries. Yields one event per item with the
 * up-to-date outcome. Caller can rebuild its in-memory pending list from
 * a separate `pending_list` invoke after the batch finishes.
 */
export async function retryPending(
  entries: PendingEntry[],
  onProgress: (ev: RdRetryEvent) => void,
  opts: RdRetryOptions = {},
): Promise<void> {
  const fetcher = opts.fetcher ?? defaultCheckFetcher;
  for (let i = 0; i < entries.length; i++) {
    if (opts.signal?.aborted) break;
    const entry = entries[i];
    let event: RdRetryEvent;
    try {
      const outcome = await fetcher(entry.torrent_id, entry.strategy);
      if (outcome.status === "completed") {
        event = {
          index: i + 1,
          total: entries.length,
          torrent_id: entry.torrent_id,
          entry,
          result: {
            kind: "completed",
            links: outcome.links,
            name: outcome.name,
          },
        };
      } else if (outcome.status === "missing") {
        event = {
          index: i + 1,
          total: entries.length,
          torrent_id: entry.torrent_id,
          entry,
          result: { kind: "missing" },
        };
      } else {
        event = {
          index: i + 1,
          total: entries.length,
          torrent_id: entry.torrent_id,
          entry,
          result: {
            kind: "pending",
            rd_status: outcome.rd_status,
            progress: outcome.progress,
            name: outcome.name,
          },
        };
      }
    } catch (e) {
      const code = errText(e);
      event = {
        index: i + 1,
        total: entries.length,
        torrent_id: entry.torrent_id,
        entry,
        result: { kind: "error", error_code: code },
      };
    }
    onProgress(event);
  }
}

/**
 * Map a Rust-side error string to a Traditional Chinese user-facing message.
 * Pure function, easy to unit test. Unknown codes fall through to a generic
 * "(其他錯誤: ...)" message that includes the raw code so support can debug.
 */
export function rdErrorMessage(code: string): string {
  switch (code) {
    case "rd_no_token":
      return "尚未設定 Real-Debrid Token";
    case "rd_token_invalid":
      return "Real-Debrid Token 無效或已過期";
    case "rd_premium_required":
      return "需要 Real-Debrid Premium 帳號";
    case "rd_rate_limited":
      return "Real-Debrid 速率限制，請稍後再試";
    case "rd_magnet_error":
      return "磁力解析失敗（RD 無法處理此磁力）";
    case "rd_download_failed":
      return "Real-Debrid 下載失敗";
    case "rd_torrent_missing":
      return "RD 上找不到此 torrent（可能已被刪除）";
    case "rd_api_error":
      return "Real-Debrid API 錯誤";
    case "unknown_handle":
      return "磁力 handle 過期，請重新擷取";
    case "rd_internal":
      return "sidecar 內部錯誤";
    default:
      return `（其他錯誤：${code}）`;
  }
}
