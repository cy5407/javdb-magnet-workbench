import { describe, expect, it, vi } from "vitest";
import {
  applyRetryEventToProgressRows,
  buildRdDisplayRows,
  collectDownloadLinksFromRow,
  formatCompletedAt,
  rdErrorMessage,
  retryPending,
  sendBatch,
  sortCompletedRowsByCompletionTime,
  type RdSendBatchEvent,
  type RdSendItem,
  type RdSendOptions,
  type RdRetryEvent,
} from "./rdSender";
import type { PendingEntry, RdCheckOutcome, RdSendOutcome, RdSendProgress } from "./types";

const tauriMocks = vi.hoisted(() => ({
  invoke: vi.fn(),
}));

vi.mock("@tauri-apps/api/core", () => ({
  invoke: tauriMocks.invoke,
}));

const item = (i: number): RdSendItem => ({
  handle_id: `h-${i}`,
  code: `SNOS-${i}`,
});

const ok = (id: string): RdSendOutcome => ({
  status: "completed",
  torrent_id: `t-${id}`,
  name: `name-${id}`,
  links: [
    { original: "x", download: "y", filename: "f.mp4", filesize: 1, streamable: 0 },
  ],
});

const pending = (id: string): RdSendOutcome => ({
  status: "pending",
  torrent_id: `t-${id}`,
  name: `name-${id}`,
  rd_status: "downloading",
  progress: 30,
});

describe("sendBatch", () => {
  it("returns one progress row per item, in order", async () => {
    const fetcher = vi.fn(async (h: string) => ok(h));
    const events: RdSendBatchEvent[] = [];
    const out = await sendBatch([item(1), item(2)], (ev) => events.push(ev), {
      fetcher,
    });
    expect(out).toHaveLength(2);
    expect(out[0].status).toBe("completed");
    expect(out[1].status).toBe("completed");
    // Two events per item: sending + completed.
    expect(events.map((e) => e.item.status)).toEqual([
      "sending",
      "completed",
      "sending",
      "completed",
    ]);
    expect(fetcher.mock.calls.map((c) => c[0])).toEqual(["h-1", "h-2"]);
  });

  it("classifies pending outcome as in_pending", async () => {
    const fetcher = vi.fn(async (h: string) => pending(h));
    const out = await sendBatch([item(1)], () => {}, { fetcher });
    expect(out[0].status).toBe("in_pending");
    expect(out[0].error_code).toBeNull();
  });

  it("captures error_code on rejected fetcher", async () => {
    const fetcher = vi.fn(async () => {
      throw new Error("rd_token_invalid");
    });
    const out = await sendBatch([item(1)], () => {}, { fetcher });
    expect(out[0].status).toBe("error");
    expect(out[0].error_code).toBe("rd_token_invalid");
  });

  it("propagates options.defaults to the fetcher", async () => {
    const fetcher = vi.fn(async (_h: string, _opts: RdSendOptions) => ok("x"));
    await sendBatch([item(1)], () => {}, {
      fetcher,
      defaults: { strategy: "largest", min_size_mb: 1000, cache_wait: 5 },
    });
    expect(fetcher.mock.calls[0][1]).toMatchObject({
      strategy: "largest",
      min_size_mb: 1000,
      cache_wait: 5,
      code: "SNOS-1",
    });
  });

  it("AbortSignal stops further items", async () => {
    const ctrl = new AbortController();
    const fetcher = vi.fn(async (h: string) => {
      if (h === "h-1") ctrl.abort();
      return ok(h);
    });
    const out = await sendBatch([item(1), item(2), item(3)], () => {}, {
      fetcher,
      signal: ctrl.signal,
    });
    expect(out[0].status).toBe("completed");
    expect(out[1].status).toBe("pending"); // initial value, never sent
    expect(out[2].status).toBe("pending");
    expect(fetcher).toHaveBeenCalledTimes(1);
  });

  it("completed outcome preserves links and torrent_id", async () => {
    const fetcher = vi.fn(async (h: string) => ok(h));
    const out = await sendBatch([item(1)], () => {}, { fetcher });
    expect(out[0].status).toBe("completed");
    expect(out[0].torrent_id).toBe("t-h-1");
    expect(out[0].links).toHaveLength(1);
    expect(out[0].links[0]).toMatchObject({
      original: "x",
      download: "y",
      filename: "f.mp4",
      filesize: 1,
      streamable: 0,
    });
    expect(out[0].error_code).toBeNull();
  });

  it("stamps a UTC ISO-8601 completed_at on the first completed outcome", async () => {
    const before = new Date().toISOString();
    const out = await sendBatch([item(1)], () => {}, {
      fetcher: async (h: string) => ok(h),
    });
    expect(out[0].completed_at).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/);
    expect(out[0].completed_at! >= before).toBe(true);
  });

  it("leaves completed_at unset for pending and error outcomes", async () => {
    const stillPending = await sendBatch([item(1)], () => {}, {
      fetcher: async (h: string) => pending(h),
    });
    expect(stillPending[0].completed_at).toBeUndefined();
    const failed = await sendBatch([item(1)], () => {}, {
      fetcher: async () => {
        throw new Error("rd_api_error");
      },
    });
    expect(failed[0].completed_at).toBeUndefined();
  });

  it("pending outcome keeps torrent_id and empties links", async () => {
    const fetcher = vi.fn(async (h: string) => pending(h));
    const out = await sendBatch([item(1)], () => {}, { fetcher });
    expect(out[0].status).toBe("in_pending");
    expect(out[0].torrent_id).toBe("t-h-1");
    expect(out[0].links).toEqual([]);
    expect(out[0].error_code).toBeNull();
  });

  it("uses String(e) when fetcher rejects with a non-Error value", async () => {
    const fetcher = vi.fn(async () => {
      throw "rd_rate_limited";
    });
    const out = await sendBatch([item(1)], () => {}, { fetcher });
    expect(out[0].status).toBe("error");
    expect(out[0].error_code).toBe("rd_rate_limited");
    expect(out[0].links).toEqual([]);
  });

  it("empty items returns [] without emitting progress or calling fetcher", async () => {
    const fetcher = vi.fn(async (h: string) => ok(h));
    const events: RdSendBatchEvent[] = [];
    const out = await sendBatch([], (ev) => events.push(ev), { fetcher });
    expect(out).toEqual([]);
    expect(events).toEqual([]);
    expect(fetcher).not.toHaveBeenCalled();
  });
});

describe("sortCompletedRowsByCompletionTime", () => {
  const row = (code: string, completed_at?: string): RdSendProgress => ({
    handle_id: `h-${code}`,
    code,
    status: "completed",
    links: [],
    error_code: null,
    completed_at,
  });

  it("preserves original order for rows with identical completed_at", () => {
    const rows = [
      row("A", "2026-05-17T01:00:00.000Z"),
      row("B", "2026-05-17T01:00:00.000Z"),
      row("C", "2026-05-17T02:00:00.000Z"),
    ];

    expect(sortCompletedRowsByCompletionTime(rows, "").map((r) => r.code)).toEqual([
      "A",
      "B",
      "C",
    ]);
  });

  it("with empty-string fallback, missing rows sort before timestamped rows while preserving their order", () => {
    const rows = [
      row("timestamped-early", "2026-05-17T01:00:00.000Z"),
      row("missing-first"),
      row("timestamped-late", "2026-05-17T02:00:00.000Z"),
      row("missing-second"),
    ];

    expect(sortCompletedRowsByCompletionTime(rows, "").map((r) => r.code)).toEqual([
      "missing-first",
      "missing-second",
      "timestamped-early",
      "timestamped-late",
    ]);
  });

  it("sortCompletedRowsByCompletionTime places missing-completed_at rows at fallback position", () => {
    const rows = [
      row("row1", "2026-01-01T00:00:00.000Z"),
      row("row2"),
      row("row3", "2026-06-01T00:00:00.000Z"),
      row("row4"),
    ];

    expect(
      sortCompletedRowsByCompletionTime(
        rows,
        "2026-03-15T00:00:00.000Z",
      ).map((r) => r.code),
    ).toEqual(["row1", "row2", "row4", "row3"]);
  });
});

describe("buildRdDisplayRows", () => {
  const row = (
    code: string,
    status: RdSendProgress["status"],
    completed_at?: string,
  ): RdSendProgress => ({
    handle_id: `h-${code}`,
    code,
    status,
    links: [],
    error_code: null,
    completed_at,
  });
  const done = (code: string, completed_at?: string): RdSendProgress =>
    row(code, "completed", completed_at);

  const T1 = "2026-05-17T01:00:00.000Z";
  const T2 = "2026-05-17T02:00:00.000Z";
  const T3 = "2026-05-17T03:00:00.000Z";

  it("keeps incomplete rows above completed rows in their original order", () => {
    const rows = [
      done("A", T2),
      row("B", "in_pending"),
      row("C", "error"),
      done("D", T1),
      row("E", "sending"),
      row("F", "pending"),
    ];

    expect(buildRdDisplayRows(rows).map((r) => r.code)).toEqual([
      "B",
      "C",
      "E",
      "F",
      "D",
      "A",
    ]);
  });

  it("orders completed rows oldest first so the newest completion lands last", () => {
    const rows = [done("mid", T2), done("newest", T3), done("oldest", T1)];

    expect(buildRdDisplayRows(rows).map((r) => r.code)).toEqual([
      "oldest",
      "mid",
      "newest",
    ]);
  });

  it("falls back to the original order for completed rows sharing a completed_at", () => {
    expect(
      buildRdDisplayRows([done("A", T1), done("B", T1), done("C", T2)]).map(
        (r) => r.code,
      ),
    ).toEqual(["A", "B", "C"]);
    // Same pair fed the other way round — a non-stable sort would pass only one.
    expect(
      buildRdDisplayRows([done("B", T1), done("A", T1), done("C", T2)]).map(
        (r) => r.code,
      ),
    ).toEqual(["B", "A", "C"]);
  });

  it("places completed rows without completed_at before timestamped ones", () => {
    const rows = [done("t1", T1), done("m1"), done("t2", T2), done("m2")];

    expect(buildRdDisplayRows(rows).map((r) => r.code)).toEqual([
      "m1",
      "m2",
      "t1",
      "t2",
    ]);
  });

  it("returns a new array without mutating or reordering the input", () => {
    const rows = [done("A", T2), row("B", "pending"), done("C", T1)];
    const original = rows.map((r) => r.code);

    const out = buildRdDisplayRows(rows);

    expect(out).not.toBe(rows);
    expect(rows.map((r) => r.code)).toEqual(original);
    // Row identity must survive: the table keys on handle_id and per-row
    // actions operate on the same objects held by the source array.
    expect(out[0]).toBe(rows[1]);
    expect(out[1]).toBe(rows[2]);
    expect(out[2]).toBe(rows[0]);
  });

  it("returns [] for an empty batch", () => {
    expect(buildRdDisplayRows([])).toEqual([]);
  });
});

describe("formatCompletedAt", () => {
  it("renders a stored UTC timestamp as local YYYY-MM-DD HH:mm:ss", () => {
    // Built from local parts so the expectation holds in any TZ the suite
    // happens to run in — the point is the format, not the offset.
    const local = new Date(2026, 6, 26, 13, 45, 12, 345);
    expect(formatCompletedAt(local.toISOString())).toBe("2026-07-26 13:45:12");
  });

  it("zero-pads single-digit month, day and time parts", () => {
    const local = new Date(2026, 0, 2, 3, 4, 5);
    expect(formatCompletedAt(local.toISOString())).toBe("2026-01-02 03:04:05");
  });

  it("renders an em dash for a legacy row carrying no completed_at", () => {
    // Rows created before completed_at existed must display safely — an
    // em dash, never "Invalid Date".
    expect(formatCompletedAt(undefined)).toBe("—");
    expect(formatCompletedAt("")).toBe("—");
  });

  it("renders an em dash rather than Invalid Date for an unparsable value", () => {
    expect(formatCompletedAt("not-a-timestamp")).toBe("—");
  });
});

describe("retryPending", () => {
  const entry = (id: string): PendingEntry => ({
    torrent_id: id,
    code: `SNOS-${id}`,
    name: "n",
    size_label: "5GB",
    strategy: "smart",
    added_at: "2026-05-10T00:00:00Z",
    last_progress: 0,
    last_rd_status: "",
    last_checked_at: null,
  });

  it("emits one event per entry, in order, with kind discriminator", async () => {
    const fetcher = vi.fn(
      async (id: string): Promise<RdCheckOutcome> =>
        id === "A"
          ? { status: "completed", torrent_id: id, name: "n", links: [] }
          : id === "B"
            ? {
                status: "pending",
                torrent_id: id,
                name: "n",
                rd_status: "downloading",
                progress: 50,
              }
            : { status: "missing", torrent_id: id },
    );
    const events: RdRetryEvent[] = [];
    await retryPending(
      [entry("A"), entry("B"), entry("C")],
      (ev) => events.push(ev),
      { fetcher },
    );
    expect(events).toHaveLength(3);
    expect(events[0].result.kind).toBe("completed");
    expect(events[1].result.kind).toBe("pending");
    expect(events[2].result.kind).toBe("missing");
  });

  it("captures fetcher errors as kind=error", async () => {
    const fetcher = vi.fn(async () => {
      throw new Error("rd_token_invalid");
    });
    const events: RdRetryEvent[] = [];
    await retryPending([entry("A")], (ev) => events.push(ev), { fetcher });
    expect(events[0].result.kind).toBe("error");
    if (events[0].result.kind === "error") {
      expect(events[0].result.error_code).toBe("rd_token_invalid");
    }
  });

  it("stringifies non-Error throws via String(e)", async () => {
    const fetcher = vi.fn(async () => {
      // Bypass the e.message branch by throwing a plain string.
      throw "raw-rejection";
    });
    const events: RdRetryEvent[] = [];
    await retryPending([entry("A")], (ev) => events.push(ev), { fetcher });
    expect(events[0].result.kind).toBe("error");
    if (events[0].result.kind === "error") {
      expect(events[0].result.error_code).toBe("raw-rejection");
    }
  });

  it("passes saved strategy to fetcher", async () => {
    const fetcher = vi.fn(
      async (id: string, strategy?: string): Promise<RdCheckOutcome> => ({
        status: "missing",
        torrent_id: id,
      }),
    );
    const e = entry("A");
    e.strategy = "largest";
    await retryPending([e], () => {}, { fetcher });
    expect(fetcher.mock.calls[0][1]).toBe("largest");
  });

  it("AbortSignal stops further items", async () => {
    const ctrl = new AbortController();
    const fetcher = vi.fn(async (id: string): Promise<RdCheckOutcome> => {
      ctrl.abort();
      return { status: "missing", torrent_id: id };
    });
    const events: RdRetryEvent[] = [];
    await retryPending(
      [entry("A"), entry("B"), entry("C")],
      (ev) => events.push(ev),
      { fetcher, signal: ctrl.signal },
    );
    expect(events).toHaveLength(1);
  });

  it("pending outcome event carries rd_status, progress, and name", async () => {
    const fetcher = vi.fn(
      async (id: string): Promise<RdCheckOutcome> => ({
        status: "pending",
        torrent_id: id,
        name: "movie-name",
        rd_status: "downloading",
        progress: 42,
      }),
    );
    const events: RdRetryEvent[] = [];
    await retryPending([entry("A")], (ev) => events.push(ev), { fetcher });
    expect(events[0].result.kind).toBe("pending");
    if (events[0].result.kind === "pending") {
      expect(events[0].result.rd_status).toBe("downloading");
      expect(events[0].result.progress).toBe(42);
      expect(events[0].result.name).toBe("movie-name");
    }
  });

  it("completed outcome event carries links and name", async () => {
    const fetcher = vi.fn(
      async (id: string): Promise<RdCheckOutcome> => ({
        status: "completed",
        torrent_id: id,
        name: "complete-name",
        links: [
          {
            original: "o",
            download: "d",
            filename: "f.mp4",
            filesize: 123,
            streamable: 1,
          },
        ],
      }),
    );
    const events: RdRetryEvent[] = [];
    await retryPending([entry("A")], (ev) => events.push(ev), { fetcher });
    expect(events[0].result.kind).toBe("completed");
    if (events[0].result.kind === "completed") {
      expect(events[0].result.name).toBe("complete-name");
      expect(events[0].result.links).toHaveLength(1);
      expect(events[0].result.links[0]).toMatchObject({
        filename: "f.mp4",
        filesize: 123,
        streamable: 1,
      });
    }
  });
});

describe("applyRetryEventToProgressRows", () => {
  const progress = (overrides: Partial<RdSendProgress>): RdSendProgress => ({
    handle_id: "h-1",
    code: "DSOD-032",
    status: "in_pending",
    links: [],
    error_code: null,
    ...overrides,
  });

  const entry = (overrides: Partial<PendingEntry> = {}): PendingEntry => ({
    torrent_id: "tid-dsod",
    code: "DSOD-032",
    name: "DSOD-032",
    size_label: "7.00GB, 5個文件",
    strategy: "smart",
    added_at: "2026-06-19T00:00:00Z",
    last_progress: 0,
    last_rd_status: "downloading",
    last_checked_at: null,
    ...overrides,
  });

  const completedEvent = (
    overrides: Partial<RdRetryEvent> = {},
  ): RdRetryEvent => ({
    index: 1,
    total: 1,
    torrent_id: "tid-dsod",
    entry: entry(),
    result: {
      kind: "completed",
      name: "DSOD-032",
      links: [
        {
          original: "o",
          download: "https://rd.example/dsod",
          filename: "DSOD-032.mp4",
          filesize: 1,
          streamable: 0,
        },
      ],
    },
    ...overrides,
  });

  it("marks the matching torrent_id progress row completed and attaches links", () => {
    const rows = [
      progress({ code: "OTHER-001", torrent_id: "tid-other" }),
      progress({ torrent_id: "tid-dsod" }),
    ];

    const out = applyRetryEventToProgressRows(
      rows,
      completedEvent(),
      "2026-06-19T01:02:03.000Z",
    );

    expect(out[0]).toBe(rows[0]);
    expect(out[1]).toMatchObject({
      status: "completed",
      torrent_id: "tid-dsod",
      completed_at: "2026-06-19T01:02:03.000Z",
      links: [{ download: "https://rd.example/dsod" }],
    });
  });

  it("falls back to the only matching in-pending code when old progress rows lack torrent_id", () => {
    const rows = [progress({ torrent_id: undefined })];

    const out = applyRetryEventToProgressRows(
      rows,
      completedEvent(),
      "2026-06-19T01:02:03.000Z",
    );

    expect(out[0]).toMatchObject({
      status: "completed",
      torrent_id: "tid-dsod",
      links: [{ download: "https://rd.example/dsod" }],
    });
  });

  it("does not guess when multiple old in-pending rows share the same code", () => {
    const rows = [
      progress({ handle_id: "h-a", torrent_id: undefined }),
      progress({ handle_id: "h-b", torrent_id: undefined }),
    ];

    const out = applyRetryEventToProgressRows(rows, completedEvent());

    expect(out).toBe(rows);
    expect(out.every((row) => row.status === "in_pending")).toBe(true);
  });

  const FIRST_COMPLETED_AT = "2026-06-19T01:02:03.000Z";

  it("keeps the original completed_at when a repeat completed event arrives", () => {
    const rows = [
      progress({
        torrent_id: "tid-dsod",
        status: "completed",
        completed_at: FIRST_COMPLETED_AT,
      }),
    ];

    const out = applyRetryEventToProgressRows(
      rows,
      completedEvent(),
      "2026-06-20T09:00:00.000Z",
    );

    expect(out[0].completed_at).toBe(FIRST_COMPLETED_AT);
    expect(out[0].links).toEqual([
      {
        original: "o",
        download: "https://rd.example/dsod",
        filename: "DSOD-032.mp4",
        filesize: 1,
        streamable: 0,
      },
    ]);
  });

  it("leaves an already-completed row untouched when the retry still reports pending", () => {
    const rows = [
      progress({
        torrent_id: "tid-dsod",
        status: "completed",
        completed_at: FIRST_COMPLETED_AT,
      }),
    ];

    const out = applyRetryEventToProgressRows(
      rows,
      completedEvent({
        result: {
          kind: "pending",
          rd_status: "downloading",
          progress: 40,
          name: "DSOD-032",
        },
      }),
      "2026-06-20T09:00:00.000Z",
    );

    expect(out).toBe(rows);
    expect(out[0].completed_at).toBe(FIRST_COMPLETED_AT);
  });

  it("keeps completed_at when the torrent later reports missing", () => {
    const rows = [
      progress({
        torrent_id: "tid-dsod",
        status: "completed",
        completed_at: FIRST_COMPLETED_AT,
      }),
    ];

    const out = applyRetryEventToProgressRows(
      rows,
      completedEvent({ result: { kind: "missing" } }),
      "2026-06-20T09:00:00.000Z",
    );

    expect(out[0].status).toBe("error");
    expect(out[0].error_code).toBe("rd_torrent_missing");
    expect(out[0].completed_at).toBe(FIRST_COMPLETED_AT);
  });
});

describe("rdErrorMessage", () => {
  it("maps known codes to localized strings", () => {
    expect(rdErrorMessage("rd_no_token")).toContain("尚未設定");
    expect(rdErrorMessage("rd_token_invalid")).toContain("Token 無效");
    expect(rdErrorMessage("rd_premium_required")).toContain("Premium");
    expect(rdErrorMessage("rd_rate_limited")).toContain("速率限制");
    expect(rdErrorMessage("rd_magnet_error")).toContain("磁力解析失敗");
    expect(rdErrorMessage("rd_torrent_missing")).toContain("找不到");
    expect(rdErrorMessage("unknown_handle")).toContain("handle");
  });

  it("maps rd_download_failed / rd_api_error / rd_internal", () => {
    expect(rdErrorMessage("rd_download_failed")).toContain("下載失敗");
    expect(rdErrorMessage("rd_api_error")).toContain("API");
    expect(rdErrorMessage("rd_internal")).toContain("sidecar");
  });

  it("falls through unknown codes with the raw code embedded", () => {
    expect(rdErrorMessage("zzz_unknown_code")).toContain("zzz_unknown_code");
  });
});

describe("default Tauri invoke wrappers", () => {
  it("sendBatch without fetcher invokes rd_send_magnet via @tauri-apps/api/core", async () => {
    tauriMocks.invoke.mockReset();
    tauriMocks.invoke.mockResolvedValueOnce(ok("h-1"));
    const out = await sendBatch([item(1)], () => {});
    expect(tauriMocks.invoke).toHaveBeenCalledTimes(1);
    const [cmd, args] = tauriMocks.invoke.mock.calls[0];
    expect(cmd).toBe("rd_send_magnet");
    expect(args).toMatchObject({
      handleId: "h-1",
      options: { code: "SNOS-1" },
    });
    expect(out[0].status).toBe("completed");
    expect(out[0].torrent_id).toBe("t-h-1");
  });

  it("retryPending without fetcher invokes rd_check_pending with strategy", async () => {
    tauriMocks.invoke.mockReset();
    tauriMocks.invoke.mockResolvedValueOnce({
      status: "missing",
      torrent_id: "tid-1",
    } satisfies RdCheckOutcome);

    const entry: PendingEntry = {
      torrent_id: "tid-1",
      code: "SNOS-1",
      name: "n",
      size_label: "5GB",
      strategy: "largest",
      added_at: "2026-05-10T00:00:00Z",
      last_progress: 0,
      last_rd_status: "",
      last_checked_at: null,
    };
    const events: RdRetryEvent[] = [];
    await retryPending([entry], (ev) => events.push(ev));

    expect(tauriMocks.invoke).toHaveBeenCalledTimes(1);
    const [cmd, args] = tauriMocks.invoke.mock.calls[0];
    expect(cmd).toBe("rd_check_pending");
    expect(args).toMatchObject({ torrentId: "tid-1", strategy: "largest" });
    expect(events).toHaveLength(1);
    expect(events[0].result.kind).toBe("missing");
  });
});

describe("collectDownloadLinksFromRow", () => {
  const link = (download: string, filename = "f.mp4"): RdSendProgress["links"][number] => ({
    original: "magnet:?xt=urn:btih:abc",
    download,
    filename,
    filesize: 0,
    streamable: 0,
  });

  const row = (overrides: Partial<RdSendProgress> = {}): RdSendProgress => ({
    handle_id: "h-1",
    code: "ABC-001",
    status: "completed",
    links: [],
    error_code: null,
    ...overrides,
  });

  it("returns all download URLs for a completed row, in original order", () => {
    const out = collectDownloadLinksFromRow(
      row({
        links: [
          link("https://rd.example/a"),
          link("https://rd.example/b"),
          link("https://rd.example/c"),
        ],
      }),
    );
    expect(out).toEqual([
      "https://rd.example/a",
      "https://rd.example/b",
      "https://rd.example/c",
    ]);
  });

  it("filters out links whose download is empty / whitespace-only", () => {
    const out = collectDownloadLinksFromRow(
      row({
        links: [
          link("https://rd.example/a"),
          link(""),
          link("   "),
          link("https://rd.example/d"),
        ],
      }),
    );
    expect(out).toEqual(["https://rd.example/a", "https://rd.example/d"]);
  });

  it("returns [] for a non-completed row even if links field is populated", () => {
    // Defensive: in_pending / error rows should never leak links into a copy
    // action — the UI must not surface stale link state from a prior attempt.
    expect(
      collectDownloadLinksFromRow(
        row({ status: "in_pending", links: [link("https://rd.example/leaked")] }),
      ),
    ).toEqual([]);
    expect(
      collectDownloadLinksFromRow(
        row({ status: "error", links: [link("https://rd.example/leaked")] }),
      ),
    ).toEqual([]);
    expect(
      collectDownloadLinksFromRow(
        row({ status: "sending", links: [link("https://rd.example/leaked")] }),
      ),
    ).toEqual([]);
    expect(
      collectDownloadLinksFromRow(
        row({ status: "pending", links: [link("https://rd.example/leaked")] }),
      ),
    ).toEqual([]);
  });

  it("returns [] when completed row has no links at all", () => {
    expect(collectDownloadLinksFromRow(row({ links: [] }))).toEqual([]);
  });
});
