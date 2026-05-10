// Shared types for the JavDB workbench frontend.
//
// Magnet payloads from the sidecar are always redacted; full magnet text
// only ever exists in:
//   1. the sidecar process
//   2. a transient String inside the Rust copy_magnet/copy_magnets_bulk
//      command, dropped immediately after writing to the OS clipboard.
// The frontend never receives full magnet URIs.

export type Theme = "light" | "dark";

export interface PathInfo {
  data_dir: string;
  log_dir: string;
}

export interface UiSettings {
  theme: Theme;
  scale: string;
}

export interface RdSettings {
  api_token: string;
  file_pick: string;
  min_size_mb: number;
  cache_wait_seconds: number;
  wait_timeout_seconds: number;
}

export interface Settings {
  version: number;
  ui: UiSettings;
  rd: RdSettings;
}

export interface MagnetRow {
  handle_id: string;
  name: string;
  size: string;
  tags: string[];
  date: string;
  magnet_redacted: string;
}

export interface FetchResult {
  engine: string;
  url: string;
  code: string;
  title: string;
  magnet_count: number;
  magnets: MagnetRow[];
}

export interface PingResponse {
  ok: boolean;
  request_id: string;
  uptime_seconds: number;
}

export interface CopyBulkResult {
  copied: number;
  unknown: number;
}

/**
 * One scraped JavDB page = one group in the results tree.
 * `error` populated when the fetch failed; `result` populated on success.
 * Both are mutually exclusive in practice but kept independent so a future
 * "retry just this group" affordance can replace `error` without touching
 * the rest of the structure.
 */
export interface ScrapedGroup {
  url: string;
  status: "pending" | "fetching" | "ok" | "error";
  result: FetchResult | null;
  error: string | null;
  /** ISO 8601 timestamp when this fetch attempt finished */
  finished_at: string | null;
}

export type GroupPick = "all" | "largest" | "smallest" | "fewest_files";

export interface FilterState {
  keyword: string;
  hd_only: boolean;
  /** GB; null/0 = no lower bound */
  min_size_gb: number | null;
  /** GB; null = no upper bound */
  max_size_gb: number | null;
  group_pick: GroupPick;
}

export const defaultFilterState = (): FilterState => ({
  keyword: "",
  hd_only: false,
  min_size_gb: null,
  max_size_gb: null,
  group_pick: "all",
});

export type SortColumn = "code" | "size" | "tags" | "date" | "name";
export type SortDirection = "asc" | "desc";

export interface SortState {
  column: SortColumn | null;
  direction: SortDirection;
}

// ---------------------------------------------------------------------------
// M5: Real-Debrid integration
// ---------------------------------------------------------------------------

export interface RdUserInfo {
  username: string;
  type: string;
  expiration: string;
  points: number;
}

export interface RdLink {
  original: string;
  download: string;
  filename: string;
  filesize: number;
  streamable: number;
}

/** Result of `rd_send_magnet`. Discriminated union on `status`. */
export type RdSendOutcome =
  | {
      status: "completed";
      torrent_id: string;
      name: string;
      links: RdLink[];
    }
  | {
      status: "pending";
      torrent_id: string;
      name: string;
      rd_status: string;
      progress: number;
    };

/** Result of `rd_check_pending`. */
export type RdCheckOutcome =
  | {
      status: "completed";
      torrent_id: string;
      name: string;
      links: RdLink[];
    }
  | {
      status: "pending";
      torrent_id: string;
      name: string;
      rd_status: string;
      progress: number;
    }
  | {
      status: "missing";
      torrent_id: string;
    };

/** Persisted pending entry shape (matches the Rust `PendingEntry`). */
export interface PendingEntry {
  torrent_id: string;
  code: string;
  name: string;
  size_label: string;
  strategy: string;
  added_at: string;
  last_progress: number;
  last_rd_status: string;
  last_checked_at: string | null;
}

/** Per-row state inside the "send to RD" progress UI. */
export interface RdSendProgress {
  handle_id: string;
  code: string;
  status: "pending" | "sending" | "completed" | "in_pending" | "error";
  links: RdLink[];
  error_code: string | null;
}
