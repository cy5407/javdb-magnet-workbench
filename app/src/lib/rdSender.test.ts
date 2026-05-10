import { describe, expect, it, vi } from "vitest";
import {
  rdErrorMessage,
  retryPending,
  sendBatch,
  type RdSendBatchEvent,
  type RdSendItem,
  type RdRetryEvent,
} from "./rdSender";
import type { PendingEntry, RdCheckOutcome, RdSendOutcome } from "./types";

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
    const fetcher = vi.fn(async (_h: string) => ok("x"));
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

  it("falls through unknown codes with the raw code embedded", () => {
    expect(rdErrorMessage("zzz_unknown_code")).toContain("zzz_unknown_code");
  });
});
