import { describe, expect, it, vi } from "vitest";
import {
  collectDownloadLinksFromRow,
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
