// Component tests for the four-tab shell: each tab owns a fixed set of
// sections, and the RD tab in particular must carry no credential editors.
//
// Two things are being pinned down here that no unit test can reach:
//   - each tab renders ONLY its own sections, and the RD tab in particular
//     carries no token / cookies / theme / sidecar editing;
//   - switching tabs is pure navigation — typed text, magnet selection and
//     the RD progress table all survive a round trip.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  setup,
  waitFor,
  within,
} from "@testing-library/svelte";
import App from "./App.svelte";
import type {
  CookiesStatus,
  CopyRdLinksBulkResult,
  MagnetRow,
  PathInfo,
  PendingEntry,
  RdCheckOutcome,
  RdSendOutcome,
  Settings,
} from "./lib/types";

const tauriMocks = vi.hoisted(() => ({ invoke: vi.fn(), open: vi.fn() }));
vi.mock("@tauri-apps/api/core", () => ({ invoke: tauriMocks.invoke }));
vi.mock("@tauri-apps/plugin-shell", () => ({ open: tauriMocks.open }));

type InvokeHandler = (args?: Record<string, unknown>) => unknown;

const cookies = (): CookiesStatus => ({
  present: false,
  path: "C:\\test\\data\\cookies.txt",
  modified_iso: null,
  size_bytes: 0,
  storage: "none",
});

/** What `get_cookies_status` reports once cookies live in the keyring — the
 * only state from which 清除 is a meaningful action. */
const keyringCookies = (): CookiesStatus => ({ ...cookies(), present: true, storage: "keyring" });

// `read_settings` deliberately returns an empty api_token: the send button is
// gated on the `rd_has_token` flag, and no fixture should look like a token.
const baseHandlers = (): Record<string, InvokeHandler> => ({
  get_paths: () => ({ data_dir: "C:\\test\\data", log_dir: "C:\\test\\logs" } satisfies PathInfo),
  read_settings: () =>
    ({
      version: 1,
      ui: { theme: "light", scale: "auto" },
      rd: { api_token: "", file_pick: "smart", min_size_mb: 0, cache_wait_seconds: 5 },
    }) satisfies Settings,
  rd_has_token: () => ({ present: true }),
  pending_list: () => [] as PendingEntry[],
  get_legacy_default_dir: () => "",
  migrate_cookies_now: cookies,
  get_cookies_status: cookies,
  register_magnets: () => ({
    registered: [
      {
        handle_id: "h-1",
        magnet_redacted: "magnet:?xt=urn:btih:abc\u2026",
        name: "SNOS-192",
        deduped: false,
      },
    ],
    invalid: [] as string[],
  }),
  rd_send_magnet: () =>
    ({
      status: "completed",
      torrent_id: "t-1",
      name: "SNOS-192",
      links: [
        {
          original: "magnet:?xt=urn:btih:abc",
          download: "https://rd.example/one",
          filename: "SNOS-192.mp4",
          filesize: 1,
          streamable: 0,
        },
      ],
    }) satisfies RdSendOutcome,
  copy_rd_links_bulk: (args) =>
    ({ copied: (args?.links as string[]).length }) satisfies CopyRdLinksBulkResult,
  clear_cookies: cookies,
});

let handlers: Record<string, InvokeHandler>;

beforeEach(() => {
  // @testing-library/svelte only self-registers setup/cleanup when vitest
  // `globals` is on; this project keeps globals off, so wire it up here.
  // setup() is also what installs flushSync as the event wrapper, without
  // which fireEvent would resolve before Svelte 5 has settled the DOM.
  setup();
  handlers = baseHandlers();
  tauriMocks.invoke.mockReset();
  tauriMocks.invoke.mockImplementation(async (cmd: string, args?: Record<string, unknown>) => {
    const handler = handlers[cmd];
    if (!handler) throw new Error(`unmocked invoke: ${cmd}`);
    return handler(args);
  });
  tauriMocks.open.mockReset();
});

afterEach(async () => {
  await act();
  cleanup();
});

/** Inactive tabs stay mounted behind `hidden`, so absence is not the signal.
 * A few blocks are `{#if}`-gated and really do disappear — `null` reads as
 * "not shown" so both mechanisms go through one predicate. */
const isShown = (node: Element | null): boolean =>
  node !== null && node.closest("[hidden]") === null;

const heading = (name: string | RegExp): Element | null =>
  screen.queryByRole("heading", { name, hidden: true });

/** The tab bar is a <nav> of buttons with aria-current, not an ARIA tablist. */
const tab = (label: RegExp): HTMLElement => screen.getByRole("button", { name: label });

const clickTab = async (label: RegExp): Promise<void> => {
  await fireEvent.click(tab(label));
};

const SEARCH_TAB = /^1\. 擷取 Magnet/;
const SELECT_TAB = /^2\. 挑選 Magnet/;
const RD_TAB = /^3\. RD 下載連結/;
const SETTINGS_TAB = /^4\. 設定/;

const rdPanel = (): HTMLElement => heading("Real-Debrid")!.closest("section")!;

/** Some codes appear both in the selection table and in the RD progress
 * table; only one of the two is ever on screen. */
const showsCell = (name: string): boolean =>
  screen.queryAllByRole("cell", { name, hidden: true }).some(isShown);

/** Two registered magnets whose send outcomes differ, so display order and
 * send order cannot coincide by accident. */
const registerTwo = async (): Promise<void> => {
  handlers.register_magnets = () => ({
    registered: [
      {
        handle_id: "h-1",
        magnet_redacted: "magnet:?xt=urn:btih:aaa…",
        name: "AAA-001",
        deduped: false,
      },
      {
        handle_id: "h-2",
        magnet_redacted: "magnet:?xt=urn:btih:bbb…",
        name: "BBB-002",
        deduped: false,
      },
    ],
    invalid: [] as string[],
  });
  const magnetBox = screen.getByPlaceholderText(/magnet:\?xt=urn:btih:/) as HTMLTextAreaElement;
  await fireEvent.input(magnetBox, {
    target: { value: "magnet:?xt=urn:btih:aaa\nmagnet:?xt=urn:btih:bbb" },
  });
  await fireEvent.click(screen.getByRole("button", { name: "加入結果清單" }));
  await waitFor(() => {
    expect(tauriMocks.invoke).toHaveBeenCalledWith("register_magnets", {
      magnets: ["magnet:?xt=urn:btih:aaa", "magnet:?xt=urn:btih:bbb"],
    });
  });
};

const progressRows = (): HTMLElement[] => {
  const table = heading("送至 Real-Debrid 進度")!.closest("section")!.querySelector("table")!;
  return Array.from(table.querySelectorAll("tbody tr"));
};

/** 番號 / 大小 / 狀態 / 完成時間 / 連結 — the completion time is index 3. */
const completedAtCell = (row: HTMLElement): HTMLElement =>
  within(row).getAllByRole("cell", { hidden: true })[3];

const mountApp = async (): Promise<void> => {
  render(App);
  // onMount ends with refreshCookiesStatus(); waiting on it proves the whole
  // startup invoke chain drained before the first assertion.
  await waitFor(() => {
    expect(tauriMocks.invoke).toHaveBeenCalledWith("migrate_cookies_now");
  });
};

/** Paste one magnet on the search tab. Registration auto-selects the handle,
 * so afterwards there is exactly one selected, sendable row. */
const pasteOneMagnet = async (): Promise<void> => {
  const magnetBox = screen.getByPlaceholderText(/magnet:\?xt=urn:btih:/) as HTMLTextAreaElement;
  await fireEvent.input(magnetBox, { target: { value: "magnet:?xt=urn:btih:abc" } });
  await fireEvent.click(screen.getByRole("button", { name: "加入結果清單" }));
  await waitFor(() => {
    expect(tauriMocks.invoke).toHaveBeenCalledWith("register_magnets", {
      magnets: ["magnet:?xt=urn:btih:abc"],
    });
  });
};

describe("tab content ownership", () => {
  it("opens on the search tab and shows only its sections", async () => {
    await mountApp();
    expect(tab(SEARCH_TAB).getAttribute("aria-current")).toBe("page");
    expect(isShown(heading("批次擷取"))).toBe(true);
    expect(isShown(heading("直接貼磁力"))).toBe(true);
    expect(isShown(heading("每個番號選取 Magnet"))).toBe(false);
    expect(isShown(heading("Real-Debrid"))).toBe(false);
    expect(isShown(heading("儲存位置"))).toBe(false);
  });

  it("shows only the selection section on the select tab", async () => {
    await mountApp();
    await clickTab(SELECT_TAB);
    expect(tab(SELECT_TAB).getAttribute("aria-current")).toBe("page");
    expect(isShown(heading("每個番號選取 Magnet"))).toBe(true);
    expect(isShown(heading("批次擷取"))).toBe(false);
    expect(isShown(heading("直接貼磁力"))).toBe(false);
    expect(isShown(heading("Real-Debrid"))).toBe(false);
    expect(isShown(heading("Sidecar"))).toBe(false);
  });

  it("shows only the preference sections on the settings tab", async () => {
    await mountApp();
    await clickTab(SETTINGS_TAB);
    expect(tab(SETTINGS_TAB).getAttribute("aria-current")).toBe("page");
    expect(isShown(heading("儲存位置"))).toBe(true);
    expect(isShown(heading("主題"))).toBe(true);
    expect(isShown(heading("Sidecar"))).toBe(true);
    expect(isShown(heading(/^JavDB Cookies/))).toBe(true);
    expect(isShown(heading(/^應用程式設定/))).toBe(true);
    expect(isShown(heading(/^匯入舊版資料/))).toBe(true);
    expect(isShown(heading("批次擷取"))).toBe(false);
    expect(isShown(heading("每個番號選取 Magnet"))).toBe(false);
    expect(isShown(heading("Real-Debrid"))).toBe(false);
  });

  it("keeps token, cookies and diagnostics off the RD tab", async () => {
    await mountApp();
    await clickTab(RD_TAB);
    expect(tab(RD_TAB).getAttribute("aria-current")).toBe("page");
    expect(isShown(heading("Real-Debrid"))).toBe(true);
    // The RD tab must not host the token editor — that belongs to 設定.
    // Anchored on the stable input id so an editor that gets re-wrapped
    // rather than actually moved still fails here.
    expect(isShown(document.getElementById("rd-token-input"))).toBe(false);
    expect(isShown(heading("Real-Debrid Token"))).toBe(false);
    expect(isShown(heading(/^JavDB Cookies/))).toBe(false);
    expect(isShown(heading("主題"))).toBe(false);
    expect(isShown(heading("Sidecar"))).toBe(false);
    expect(isShown(heading("儲存位置"))).toBe(false);
    expect(isShown(heading(/^匯入舊版資料/))).toBe(false);
    expect(isShown(heading(/^應用程式設定/))).toBe(false);
  });

  it("owns the Real-Debrid token editor on the settings tab", async () => {
    await mountApp();
    await clickTab(SETTINGS_TAB);
    // Existence is asserted separately from visibility so a deleted editor
    // can never satisfy the "not on the RD tab" case above.
    expect(document.getElementById("rd-token-input")).not.toBeNull();
    expect(isShown(document.getElementById("rd-token-input"))).toBe(true);
    expect(isShown(heading("Real-Debrid Token"))).toBe(true);
  });

  it("disables sending and offers a route to 設定 when no token is stored", async () => {
    handlers.rd_has_token = () => ({ present: false });
    await mountApp();
    // Select something first, so the disabled state can only come from the
    // missing token and not from an empty selection.
    await pasteOneMagnet();
    await clickTab(RD_TAB);
    const send = within(rdPanel()).getByRole("button", {
      name: /送出已勾選/,
    }) as HTMLButtonElement;
    expect(send.disabled).toBe(true);
    const toSettings = within(rdPanel()).getByRole("button", { name: /設定/ });
    expect(isShown(toSettings)).toBe(true);

    await fireEvent.click(toSettings);
    expect(isShown(document.getElementById("rd-token-input"))).toBe(true);
  });

  it("marks exactly one tab current and steps between them with the arrow keys", async () => {
    await mountApp();
    const bar = screen.getByRole("navigation", { name: "主要流程" });
    const buttons = within(bar).getAllByRole("button");
    expect(buttons).toHaveLength(4);
    // Native <button> is what makes Enter/Space activation work; jsdom will
    // not synthesize it for a div carrying role="tab".
    for (const b of buttons) expect(b.tagName).toBe("BUTTON");
    expect(buttons.filter((b) => b.getAttribute("aria-current") === "page")).toHaveLength(1);

    await fireEvent.keyDown(tab(SEARCH_TAB), { key: "ArrowRight" });
    expect(tab(SELECT_TAB).getAttribute("aria-current")).toBe("page");
    expect(isShown(heading("每個番號選取 Magnet"))).toBe(true);

    await fireEvent.keyDown(tab(SELECT_TAB), { key: "End" });
    expect(tab(SETTINGS_TAB).getAttribute("aria-current")).toBe("page");
    expect(isShown(heading("儲存位置"))).toBe(true);

    await fireEvent.keyDown(tab(SETTINGS_TAB), { key: "ArrowRight" });
    expect(tab(SEARCH_TAB).getAttribute("aria-current")).toBe("page");
    expect(
      within(bar)
        .getAllByRole("button")
        .filter((b) => b.getAttribute("aria-current") === "page"),
    ).toHaveLength(1);
  });
});

describe("state across tab switches", () => {
  it("keeps typed URLs, magnet selection and RD progress across tab switches", async () => {
    await mountApp();

    // urlBatch is never cleared by an action, unlike magnetBatch, so it is
    // the honest probe for "typed text survives navigation".
    const urlBox = screen.getByPlaceholderText(/javdb\.com\/v\//) as HTMLTextAreaElement;
    await fireEvent.input(urlBox, { target: { value: "https://javdb.com/v/ABC\n" } });

    await pasteOneMagnet();

    await clickTab(RD_TAB);
    await fireEvent.click(within(rdPanel()).getByRole("button", { name: /送出已勾選/ }));
    await waitFor(() => {
      expect(isShown(heading("送至 Real-Debrid 進度"))).toBe(true);
    });
    expect(showsCell("SNOS-192")).toBe(true);

    // Leave and come back — nothing is refetched, nothing is reset.
    await clickTab(SETTINGS_TAB);
    expect(isShown(heading("送至 Real-Debrid 進度"))).toBe(false);
    await clickTab(RD_TAB);
    expect(isShown(heading("送至 Real-Debrid 進度"))).toBe(true);
    expect(showsCell("SNOS-192")).toBe(true);

    // Selection survived: the tab badge renders selectedMagnets/selectableMagnets.
    expect(tab(SELECT_TAB).textContent).toContain("1/1");

    await clickTab(SEARCH_TAB);
    expect((screen.getByPlaceholderText(/javdb\.com\/v\//) as HTMLTextAreaElement).value).toBe(
      "https://javdb.com/v/ABC\n",
    );

    expect(tauriMocks.invoke.mock.calls.filter((c) => c[0] === "rd_send_magnet")).toHaveLength(1);
  });

  it("keeps the row checked on the selection tab after switching away and back", async () => {
    await mountApp();
    await pasteOneMagnet();

    await clickTab(SELECT_TAB);
    const row = screen.getByRole("cell", { name: "SNOS-192" }).closest("tr")!;
    const check = within(row).getByRole("checkbox") as HTMLInputElement;
    expect(check.checked).toBe(true);

    await clickTab(SETTINGS_TAB);
    await clickTab(SELECT_TAB);
    const rowAgain = screen.getByRole("cell", { name: "SNOS-192" }).closest("tr")!;
    expect((within(rowAgain).getByRole("checkbox") as HTMLInputElement).checked).toBe(true);
  });
});

describe("per-URL scrape outcome on the search tab", () => {
  const URL_A = "https://javdb.com/v/AAA";

  /** Scrape exactly one URL: scrapeBatch only paces BETWEEN urls, so a
   * single-URL batch settles without the 3–6s production delay. */
  const scrapeOneUrl = async (): Promise<void> => {
    const urlBox = screen.getByPlaceholderText(/javdb\.com\/v\//) as HTMLTextAreaElement;
    await fireEvent.input(urlBox, { target: { value: `${URL_A}\n` } });
    await fireEvent.click(screen.getByRole("button", { name: "開始擷取" }));
    await waitFor(() => {
      expect(tauriMocks.invoke).toHaveBeenCalledWith("fetch_javdb", { url: URL_A });
    });
  };

  it("names the failing URL and its error without leaving the scrape tab", async () => {
    handlers.fetch_javdb = () => {
      throw new Error("javdb_parse_failed");
    };
    await mountApp();
    await scrapeOneUrl();

    // A per-URL fetch outcome must be readable on the scrape tab itself,
    // not only after switching to 「2. 挑選 Magnet」.
    // The select tab renders the same error, so "some visible" is the signal.
    await waitFor(() => {
      expect(screen.getAllByText(/javdb_parse_failed/).some(isShown)).toBe(true);
    });
    expect(screen.getAllByText(URL_A).some(isShown)).toBe(true);
    expect(isShown(heading("每個番號選取 Magnet"))).toBe(false);
  });

  it("reports the magnet count for a successful URL and keeps the picker table on tab 2", async () => {
    handlers.fetch_javdb = () => ({
      engine: "test",
      url: URL_A,
      code: "AAA-001",
      title: "t",
      magnet_count: 2,
      magnets: [],
    });
    await mountApp();
    await scrapeOneUrl();

    await waitFor(() => {
      expect(isShown(screen.getByText("2 個磁力"))).toBe(true);
    });
    // 2.2 forbids the full checkbox table here — the summary must not have
    // dragged it along.
    expect(screen.queryByRole("columnheader", { name: "送 RD", hidden: true })).toBeNull();
  });
});

describe("RD progress table completion time", () => {
  it("moves the completed row below the pending one and timestamps only it", async () => {
    // h-1 completes, h-2 stays pending: send order is [h-1, h-2] so any table
    // still iterating rdSendProgress would render them the other way round.
    handlers.rd_send_magnet = (args) =>
      args?.handleId === "h-1"
        ? ({
            status: "completed",
            torrent_id: "t-1",
            name: "AAA-001",
            links: [
              {
                original: "magnet:?xt=urn:btih:aaa",
                download: "https://rd.example/one",
                filename: "AAA-001.mp4",
                filesize: 1,
                streamable: 0,
              },
            ],
          } satisfies RdSendOutcome)
        : ({
            status: "pending",
            torrent_id: "t-2",
            name: "BBB-002",
            rd_status: "downloading",
            progress: 10,
          } satisfies RdSendOutcome);

    await mountApp();
    await registerTwo();
    await clickTab(RD_TAB);
    await fireEvent.click(within(rdPanel()).getByRole("button", { name: /送出已勾選/ }));
    await waitFor(() => {
      expect(progressRows()).toHaveLength(2);
      expect(within(progressRows()[1]).queryByText("已完成")).not.toBeNull();
    });

    const [pendingRow, completedRow] = progressRows();
    expect(within(pendingRow).getAllByRole("cell", { hidden: true })[0].textContent).toBe(
      "BBB-002",
    );
    expect(within(completedRow).getAllByRole("cell", { hidden: true })[0].textContent).toBe(
      "AAA-001",
    );

    // 1.3 — completed shows local YYYY-MM-DD HH:mm:ss with the full ISO in title.
    const done = completedAtCell(completedRow);
    expect(done.textContent!.trim()).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/);
    expect(done.getAttribute("title")).toMatch(/^\d{4}-\d{2}-\d{2}T.*Z$/);

    // 1.3 — a row that has not completed shows the em dash and hides nothing
    // behind a tooltip.
    const notDone = completedAtCell(pendingRow);
    expect(notDone.textContent!.trim()).toBe("—");
    expect(notDone.getAttribute("title")).toBeNull();
  });

  it("labels the column as the app's own confirmation time", async () => {
    await mountApp();
    await pasteOneMagnet();
    await clickTab(RD_TAB);
    await fireEvent.click(within(rdPanel()).getByRole("button", { name: /送出已勾選/ }));
    await waitFor(() => {
      expect(progressRows()).toHaveLength(1);
    });

    // completed_at is when THIS APP first confirmed completion, not when RD
    // actually finished — a pending row is only observed on retry. The column
    // wording must not imply the latter.
    const header = screen.getByRole("columnheader", { name: /完成時間/, hidden: true });
    expect(header.textContent).toContain("本程式確認");
    expect(header.getAttribute("title")).toContain("非 Real-Debrid 伺服器");
  });
});

// The pending -> retry -> completed journey, end to end.
// rdSender.test.ts already pins the two halves
// (applyRetryEventToProgressRows, buildRdDisplayRows) as pure functions; what
// only the component can show is that retryAllPending actually wires them
// together — that the row the user retried is the one that moves, and that it
// picks up a timestamp on the way.
describe("retrying a pending row through to completion", () => {
  const pending = (torrent_id: string, code: string): PendingEntry => ({
    torrent_id,
    code,
    name: code,
    size_label: "1.0 GB",
    strategy: "smart",
    added_at: "2026-01-01T00:00:00Z",
    last_progress: 10,
    last_rd_status: "downloading",
    last_checked_at: null,
  });

  /** Send two magnets that both land in RD's queue, so the progress table
   * starts with two `in_pending` rows in send order. */
  const sendTwoIntoPending = async (): Promise<void> => {
    handlers.rd_send_magnet = (args) =>
      ({
        status: "pending",
        torrent_id: args?.handleId === "h-1" ? "t-1" : "t-2",
        name: args?.handleId === "h-1" ? "AAA-001" : "BBB-002",
        rd_status: "downloading",
        progress: 10,
      }) satisfies RdSendOutcome;
    handlers.pending_list = () => [pending("t-1", "AAA-001"), pending("t-2", "BBB-002")];

    await mountApp();
    await registerTwo();
    await clickTab(RD_TAB);
    await fireEvent.click(within(rdPanel()).getByRole("button", { name: /送出已勾選/ }));
    await waitFor(() => {
      expect(progressRows()).toHaveLength(2);
    });
  };

  it("flips the retried row to 已完成, timestamps it, and drops it below the still-pending row", async () => {
    await sendTwoIntoPending();
    expect(progressRows().map((r) => within(r).getAllByRole("cell", { hidden: true })[0].textContent))
      .toEqual(["AAA-001", "BBB-002"]);

    // Only the first torrent finished. t-2 staying pending is what makes the
    // reorder observable: a table still iterating rdSendProgress would leave
    // AAA-001 on top.
    handlers.rd_check_pending = (args) =>
      args?.torrentId === "t-1"
        ? ({
            status: "completed",
            torrent_id: "t-1",
            name: "AAA-001",
            links: [
              {
                original: "magnet:?xt=urn:btih:aaa",
                download: "https://rd.example/aaa",
                filename: "AAA-001.mp4",
                filesize: 1,
                streamable: 0,
              },
            ],
          } satisfies RdCheckOutcome)
        : ({
            status: "pending",
            torrent_id: "t-2",
            name: "BBB-002",
            rd_status: "downloading",
            progress: 42,
          } satisfies RdCheckOutcome);
    // retryAllPending re-reads pending_list in its finally block; RD dropped
    // the finished torrent, so the second read must not still list t-1.
    handlers.pending_list = () => [pending("t-2", "BBB-002")];

    // 待處理 is its own section, sibling to the Real-Debrid panel.
    await fireEvent.click(screen.getByRole("button", { name: /全部重試/ }));
    await waitFor(() => {
      expect(screen.getByText(/重試完成/)).not.toBeNull();
    });

    const rows = progressRows();
    expect(rows.map((r) => within(r).getAllByRole("cell", { hidden: true })[0].textContent)).toEqual(
      ["BBB-002", "AAA-001"],
    );
    const [stillPending, justCompleted] = rows;
    expect(within(justCompleted).queryByText("已完成")).not.toBeNull();
    expect(within(stillPending).queryByText("RD 處理中")).not.toBeNull();

    // The timestamp is minted by the retry, not carried over from the send:
    // the row had none while it sat in 待處理.
    expect(completedAtCell(justCompleted).textContent!.trim()).toMatch(
      /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/,
    );
    expect(completedAtCell(stillPending).textContent!.trim()).toBe("—");

    expect(screen.getByText(/1 個完成/)).not.toBeNull();
    expect(tauriMocks.invoke).toHaveBeenCalledWith("copy_rd_links_bulk", {
      links: ["https://rd.example/aaa"],
    });
  });

  it("retryAllPending displays cancelled summary with original batch count as denominator", async () => {
    handlers.rd_has_token = () => ({ present: true });
    handlers.pending_list = () => [
      pending("t-1", "AAA-001"),
      pending("t-2", "BBB-002"),
      pending("t-3", "CCC-003"),
    ];

    await mountApp();
    await clickTab(RD_TAB);

    let callCount = 0;
    handlers.rd_check_pending = (args: any) => {
      const torrentId = String(args?.torrentId ?? "");
      callCount++;
      const cancelBtn = screen.queryByRole("button", { name: "取消" });
      if (cancelBtn) fireEvent.click(cancelBtn);
      return {
        status: "completed",
        torrent_id: torrentId,
        name: torrentId,
        rd_status: "downloaded",
        progress: 100,
        links: [{ filename: "x.mkv", download: "https://rd.example/x" }],
      };
    };
    handlers.pending_list = () => [pending("t-2", "BBB-002"), pending("t-3", "CCC-003")];

    await fireEvent.click(screen.getByRole("button", { name: /全部重試/ }));

    await waitFor(() => {
      expect(screen.getByText(/已取消：完成 \d+\/3/)).not.toBeNull();
    });
  });
});

// 清除 is the last of 新增/更換/驗證/清除 to land on the 設定 tab; all four
// credential operations belong there and nowhere else.
// These live here rather than in a lib unit test on purpose: the behaviour
// being specified IS the component's state machine (arm -> confirm -> invoke
// -> adopt the returned status). There is no pure function to extract that
// would not be a restatement of the same three assignments, and the property
// that matters most — a single click does NOT destroy anything — is only
// observable as "the click happened and no invoke followed".
describe("clearing JavDB cookies from the settings tab", () => {
  const cookiesSection = (): HTMLElement => heading(/^JavDB Cookies/)!.closest("section")!;

  /** The section is collapsed by default; every control lives behind 展開. */
  const openCookiesSection = async (): Promise<void> => {
    await clickTab(SETTINGS_TAB);
    await fireEvent.click(within(cookiesSection()).getByRole("button", { name: /展開/ }));
  };

  /** `hidden: true` so the same lookup works from another tab, where the whole
   * section is behind `hidden` — visibility is asserted with isShown instead. */
  const clearButton = (name: RegExp): HTMLButtonElement =>
    within(cookiesSection()).getByRole("button", { name, hidden: true }) as HTMLButtonElement;

  const noClearButton = (name: RegExp): boolean =>
    within(cookiesSection()).queryByRole("button", { name, hidden: true }) === null;

  const mountWithStoredCookies = async (): Promise<void> => {
    handlers.migrate_cookies_now = keyringCookies;
    handlers.get_cookies_status = keyringCookies;
    await mountApp();
    await openCookiesSection();
  };

  it("arms instead of clearing on the first click", async () => {
    await mountWithStoredCookies();
    await fireEvent.click(clearButton(/^清除 cookies$/));

    expect(tauriMocks.invoke.mock.calls.some((c) => c[0] === "clear_cookies")).toBe(false);
    expect(isShown(screen.getByText(/確定要清除 cookies/))).toBe(true);
    // The armed button must not reuse the resting label, or a double-click
    // would sail through the confirmation without it ever being read.
    expect(noClearButton(/^清除 cookies$/)).toBe(true);
  });

  it("backs out cleanly and can be armed again", async () => {
    await mountWithStoredCookies();
    await fireEvent.click(clearButton(/^清除 cookies$/));
    await fireEvent.click(clearButton(/^取消清除$/));

    expect(tauriMocks.invoke.mock.calls.some((c) => c[0] === "clear_cookies")).toBe(false);
    expect(screen.queryByText(/確定要清除 cookies/)).toBeNull();
    expect(clearButton(/^清除 cookies$/).disabled).toBe(false);
  });

  it("clears on the confirming click and shows the emptied state straight away", async () => {
    await mountWithStoredCookies();
    expect(isShown(screen.getByText(/cookies 已加密儲存/))).toBe(true);
    const migratesBefore = tauriMocks.invoke.mock.calls.filter(
      (c) => c[0] === "migrate_cookies_now",
    ).length;

    await fireEvent.click(clearButton(/^清除 cookies$/));
    await fireEvent.click(clearButton(/^確定清除$/));

    // No payload: both of the Rust command's parameters are injected state.
    await waitFor(() => {
      expect(tauriMocks.invoke).toHaveBeenCalledWith("clear_cookies");
    });
    // The returned status is adopted as-is. Re-running migrate_cookies_now
    // would promote any surviving cookies.txt back into the keyring, which is
    // exactly the resurrection the clear exists to prevent.
    expect(tauriMocks.invoke.mock.calls.filter((c) => c[0] === "migrate_cookies_now")).toHaveLength(
      migratesBefore,
    );
    await waitFor(() => {
      expect(isShown(screen.getByText(/尚未設定 cookies/))).toBe(true);
    });
    expect(screen.queryByText(/cookies 已加密儲存/)).toBeNull();
    expect(isShown(screen.getByText(/cookies 已清除/))).toBe(true);
    expect(screen.queryByText(/確定要清除 cookies/)).toBeNull();

    // flash-ok survives the clear because the button is disabled, not
    // unmounted, once there is nothing left to clear.
    const settled = clearButton(/已清除/);
    expect(settled.classList.contains("flash-ok")).toBe(true);
    expect(settled.disabled).toBe(true);
  });

  it("offers nothing to clear when no cookies are stored", async () => {
    await mountApp();
    await openCookiesSection();
    expect(clearButton(/^清除 cookies$/).disabled).toBe(true);
  });

  it("surfaces the raw backend error and stays armed-free", async () => {
    handlers.clear_cookies = () => {
      throw new Error("keyring delete: access denied");
    };
    await mountWithStoredCookies();
    await fireEvent.click(clearButton(/^清除 cookies$/));
    await fireEvent.click(clearButton(/^確定清除$/));

    await waitFor(() => {
      expect(isShown(screen.getByText(/清除失敗：keyring delete: access denied/))).toBe(true);
    });
    // A failed clear leaves the stored state visible — the UI must not claim
    // success it did not get.
    expect(isShown(screen.getByText(/cookies 已加密儲存/))).toBe(true);
    expect(noClearButton(/已清除/)).toBe(true);
  });

  it("reports a stale sidecar as a partial clear, not a failed one", async () => {
    handlers.clear_cookies = () => {
      throw new Error("cookies_cleared_sidecar_stale: sidecar is dead: exited early");
    };
    await mountWithStoredCookies();
    // The backend removed the file and the keyring entry before the push
    // failed, so a fresh read now reports an empty store.
    handlers.get_cookies_status = cookies;

    await fireEvent.click(clearButton(/^清除 cookies$/));
    await fireEvent.click(clearButton(/^確定清除$/));

    await waitFor(() => {
      expect(isShown(screen.getByText(/已清除儲存的 cookies/))).toBe(true);
    });
    // The credentials really are gone. Saying 清除失敗 would send the user
    // looking for cookies that no longer exist, and this action is one they
    // cannot undo.
    expect(screen.queryByText(/清除失敗/)).toBeNull();
    await waitFor(() => {
      expect(isShown(screen.getByText(/尚未設定 cookies/))).toBe(true);
    });
    expect(screen.queryByText(/cookies 已加密儲存/)).toBeNull();
  });

  it("keeps the clear control off the RD tab", async () => {
    await mountWithStoredCookies();
    await clickTab(RD_TAB);
    expect(isShown(clearButton(/^清除 cookies$/))).toBe(false);
  });
});

describe("Busy Mutual Exclusion", () => {
  it("disables clearResults while sending to RD and guards handler", async () => {
    let resolveSend: (val: unknown) => void = () => {};
    handlers.rd_send_magnet = () => new Promise((res) => { resolveSend = res; });
    await mountApp();
    await pasteOneMagnet();
    await clickTab(RD_TAB);

    const sendBtn = screen.getByRole("button", { name: /送出已勾選 1 筆到 RD/ });
    await fireEvent.click(sendBtn);

    await clickTab(SEARCH_TAB);
    const clearBtn = screen.getByRole("button", { name: /清空全部結果/ }) as HTMLButtonElement;
    expect(clearBtn.disabled).toBe(true);

    await fireEvent.click(clearBtn);
    expect(tauriMocks.invoke).not.toHaveBeenCalledWith("forget_magnets", expect.anything());

    resolveSend({
      status: "completed",
      torrent_id: "t-1",
      name: "SNOS-192",
      links: [],
    });
    await waitFor(() => {
      expect(clearBtn.disabled).toBe(false);
    });
  });
});

describe("Theme Management", () => {
  it("rolls back theme on write_settings failure", async () => {
    handlers.write_settings = () => {
      throw new Error("disk full");
    };
    await mountApp();
    await clickTab(SETTINGS_TAB);

    const themeBtn = screen.getByRole("button", { name: /主題：light/ });
    await fireEvent.click(themeBtn);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /主題：light/ })).not.toBeNull();
      expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    });
  });

  it("prevents rapid double clicks with isThemeSaving guard", async () => {
    let resolveWrite: (val: unknown) => void = () => {};
    let writeCount = 0;
    handlers.write_settings = () => {
      writeCount += 1;
      return new Promise((res) => { resolveWrite = res; });
    };

    await mountApp();
    await clickTab(SETTINGS_TAB);

    const themeBtn = screen.getByRole("button", { name: /主題：light/ });
    await fireEvent.click(themeBtn);
    await fireEvent.click(themeBtn);

    expect(writeCount).toBe(1);

    resolveWrite(undefined);
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /主題：dark/ })).not.toBeNull();
    });
  });

  it("prevents pending mutations (refresh/clear/remove) while busy sending or retrying", async () => {
    const pending = (torrent_id: string): PendingEntry => ({
      torrent_id,
      code: "SNOS-192",
      name: "SNOS-192",
      size_label: "1.0 GB",
      strategy: "smart",
      added_at: "2026-01-01T00:00:00Z",
      last_progress: 10,
      last_rd_status: "downloading",
      last_checked_at: null,
    });
    handlers.pending_list = () => [pending("t-1")];
    handlers.rd_has_token = () => ({ present: true });

    let resolveSend: (val: unknown) => void = () => {};
    handlers.rd_send_magnet = () => new Promise((res) => { resolveSend = res; });

    await mountApp();
    await registerTwo();
    await clickTab(RD_TAB);

    const sendBtn = screen.getByRole("button", { name: /送出已勾選 \d+ 筆到 RD/ });
    await fireEvent.click(sendBtn);

    const refreshBtn = screen.getByRole("button", { name: "重讀本機紀錄" }) as HTMLButtonElement;
    const clearBtn = screen.getByRole("button", { name: "全部清空" }) as HTMLButtonElement;
    const removeBtn = screen.getByRole("button", { name: "移除" }) as HTMLButtonElement;

    expect(refreshBtn.disabled).toBe(true);
    expect(clearBtn.disabled).toBe(true);

    tauriMocks.invoke.mockClear();
    await fireEvent.click(refreshBtn);
    await fireEvent.click(clearBtn);
    await fireEvent.click(removeBtn);

    expect(tauriMocks.invoke).not.toHaveBeenCalledWith("pending_list", expect.anything());
    expect(tauriMocks.invoke).not.toHaveBeenCalledWith("pending_clear", expect.anything());
    expect(tauriMocks.invoke).not.toHaveBeenCalledWith("pending_remove", expect.anything());

    resolveSend({ status: "completed", torrent_id: "t-1", name: "SNOS-192", links: [] });
  });

  it("shows 取消中… feedback when canceling RD send", async () => {
    handlers.rd_has_token = () => ({ present: true });
    let resolveSend: (val: unknown) => void = () => {};
    handlers.rd_send_magnet = () => new Promise((res) => { resolveSend = res; });

    await mountApp();
    await registerTwo();
    await clickTab(RD_TAB);

    await fireEvent.click(screen.getByRole("button", { name: /送出已勾選 \d+ 筆到 RD/ }));
    const cancelBtn = screen.getByRole("button", { name: "取消" });
    await fireEvent.click(cancelBtn);

    expect(screen.getByRole("button", { name: "取消中…" })).not.toBeNull();

    resolveSend({ status: "completed", torrent_id: "t-1", name: "SNOS-192", links: [] });
    await waitFor(() => {
      expect(screen.queryByRole("button", { name: "取消中…" })).toBeNull();
    });
  });
});

describe("Settings Write Exclusion & Theme Rollback (Item 4)", () => {
  it("settingsWriteBusy blocks concurrent settings writers", async () => {
    let resolveWrite: (val: unknown) => void = () => {};
    let writeCount = 0;
    handlers.write_settings = () => {
      writeCount += 1;
      return new Promise((res) => { resolveWrite = res; });
    };

    await mountApp();
    await clickTab(SETTINGS_TAB);

    // 1. Trigger toggleTheme -> starts theme saving
    const themeBtn = screen.getByRole("button", { name: /主題：light/ });
    await fireEvent.click(themeBtn);
    expect(writeCount).toBe(1);

    // Expand settings section while busy
    const expandBtns = screen.getAllByRole("button", { name: /展開/ });
    // Expand legacy section (first expand button)
    await fireEvent.click(expandBtns[0]);

    // Input in legacy section should be disabled by settingsWriteBusy
    const legacyInput = screen.getByPlaceholderText(/程式語言/) as HTMLInputElement;
    expect(legacyInput.disabled).toBe(true);

    resolveWrite(undefined);
  });

  it("does not mutate new settings object on theme rollback after reference replacement", async () => {
    let rejectWrite: (err: Error) => void = () => {};
    handlers.write_settings = () => new Promise((_, rej) => { rejectWrite = rej; });

    await mountApp();
    await clickTab(SETTINGS_TAB);

    const themeBtn = screen.getByRole("button", { name: /主題：light/ });
    await fireEvent.click(themeBtn);

    // Simulate concurrent reload replacing settings object with a new object (e.g. theme "dark")
    const newSettings: Settings = {
      version: 1,
      ui: { theme: "dark", scale: "auto" },
      rd: { api_token: "", file_pick: "smart", min_size_mb: 0, cache_wait_seconds: 5 },
    };
    handlers.read_settings = () => newSettings;

    // Trigger write failure
    rejectWrite(new Error("write failed"));

    await waitFor(() => {
      // canonical newSettings should remain "dark", not rolled back to "light"
      expect(newSettings.ui.theme).toBe("dark");
    });
  });
});

describe("Stale Handle Forget on Scrape (Item 6)", () => {
  it("forgets ONLY web group handles on startScrape, excluding manual group handles", async () => {
    let forgetArgs: { handleIds: string[] } | null = null;
    handlers.forget_magnets = (args) => {
      forgetArgs = args as { handleIds: string[] };
      return (args?.handleIds as string[]).length;
    };
    handlers.fetch_javdb = (args) => ({
      engine: "javdb",
      url: (args?.url as string) || "https://javdb.com/v/ABC123",
      code: "ABC-123",
      title: "Title",
      magnet_count: 1,
      magnets: [
        { handle_id: "web-h-1", name: "ABC-123", size: "1 GB", tags: ["HD"], date: "2026-01-01", magnet_redacted: "magnet:?xt=urn:btih:web1…" },
      ],
    });

    await mountApp();
    // Register 1 manual magnet -> manual group with h-1
    await pasteOneMagnet();

    // 1st scrape: web URL
    const urlBox = screen.getByPlaceholderText(/https:\/\/javdb/);
    await fireEvent.input(urlBox, { target: { value: "https://javdb.com/v/ABC123" } });
    await fireEvent.click(screen.getByRole("button", { name: "開始擷取" }));

    await waitFor(() => {
      expect(tauriMocks.invoke).toHaveBeenCalledWith("fetch_javdb", expect.anything());
    });



    // Reset forgetArgs before 2nd scrape
    forgetArgs = null;

    // 2nd scrape: another web URL
    await fireEvent.input(urlBox, { target: { value: "https://javdb.com/v/XYZ789" } });
    await fireEvent.click(screen.getByRole("button", { name: "開始擷取" }));

    await waitFor(() => {
      expect(forgetArgs).not.toBeNull();
      expect(forgetArgs!.handleIds).toEqual(["web-h-1"]);
      expect(forgetArgs!.handleIds).not.toContain("h-1");
    });
  });

  /**
   * The case above uses disjoint handles (web-h-1 vs h-1), so it only proves
   * the GROUP-level filter works. The sidecar keys handles by BTIH, so a
   * pasted magnet whose BTIH matches a scraped one shares the handle — and a
   * per-group filter releases it while the manual row is still on screen.
   * Without this case the aliasing bug passes every existing assertion.
   */
  it("keeps a handle a surviving manual group still shows, even across a scrape", async () => {
    // Collected into an array rather than a nullable single value: TS narrows
    // a `let x = null` that is only reassigned inside a callback back to
    // `null`, and the property read then fails svelte-check.
    const forgotten: string[] = [];
    handlers.forget_magnets = (args) => {
      const ids = (args?.handleIds as string[]) ?? [];
      forgotten.push(...ids);
      return ids.length;
    };
    // Same BTIH on both sides → sidecar hands back the same handle_id.
    handlers.register_magnets = () => ({
      registered: [
        {
          handle_id: "h-shared",
          magnet_redacted: "magnet:?xt=urn:btih:abc…",
          name: "SHARED-001",
          deduped: true,
        },
      ],
      invalid: [] as string[],
    });
    handlers.fetch_javdb = (args) => ({
      engine: "test",
      url: (args?.url as string) ?? "",
      code: "SHARED-001",
      title: "T",
      magnet_count: 1,
      magnets: [{
        handle_id: "h-shared", name: "SHARED-001.mp4", size: "1 GB",
        tags: [], date: "2026-01-01", magnet_redacted: "magnet:?xt=urn:btih:abc…",
      }],
    });

    await mountApp();
    const urlBox = screen.getByPlaceholderText(/https:\/\/javdb/);
    await fireEvent.input(urlBox, { target: { value: "https://javdb.com/v/ABC123" } });
    await fireEvent.click(screen.getByRole("button", { name: "開始擷取" }));
    await waitFor(() => {
      expect(tauriMocks.invoke).toHaveBeenCalledWith("fetch_javdb", expect.anything());
    });
    await pasteOneMagnet();

    forgotten.length = 0;
    await fireEvent.input(urlBox, { target: { value: "https://javdb.com/v/XYZ789" } });
    await fireEvent.click(screen.getByRole("button", { name: "開始擷取" }));

    await waitFor(() => {
      expect(tauriMocks.invoke).toHaveBeenCalledWith("fetch_javdb", { url: "https://javdb.com/v/XYZ789" });
    });
    // Releasing it would leave the still-rendered, still-checked pasted row
    // pointing at a dead handle — unrecoverable, since the full magnet only
    // ever existed inside the sidecar.
    expect(forgotten).not.toContain("h-shared");
  });

  it("does not call forget_magnets when there are no web groups", async () => {
    let forgetCalled = false;
    handlers.forget_magnets = () => {
      forgetCalled = true;
      return 0;
    };

    await mountApp();
    await pasteOneMagnet(); // only manual group

    const urlBox = screen.getByPlaceholderText(/https:\/\/javdb/);
    await fireEvent.input(urlBox, { target: { value: "https://javdb.com/v/ABC123" } });
    await fireEvent.click(screen.getByRole("button", { name: "開始擷取" }));

    expect(forgetCalled).toBe(false);
  });

  it("proceeds with scrape even if forget_magnets throws", async () => {
    handlers.forget_magnets = () => {
      throw new Error("RPC error");
    };
    let fetchCalled = false;
    handlers.fetch_javdb = (args) => {
      fetchCalled = true;
      return {
        engine: "javdb",
        url: (args?.url as string) || "https://javdb.com/v/ABC123",
        code: "ABC-123",
        title: "T",
        magnet_count: 1,
        magnets: [{ handle_id: "w-1", name: "A", size: "1 GB", tags: [], date: "2026-01-01", magnet_redacted: "m" }],
      };
    };

    await mountApp();
    const urlBox = screen.getByPlaceholderText(/https:\/\/javdb/);
    await fireEvent.input(urlBox, { target: { value: "https://javdb.com/v/ABC123" } });
    await fireEvent.click(screen.getByRole("button", { name: "開始擷取" }));
    await waitFor(() => { expect(fetchCalled).toBe(true); });

    // Scrape again
    fetchCalled = false;
    await fireEvent.input(urlBox, { target: { value: "https://javdb.com/v/XYZ789" } });
    await fireEvent.click(screen.getByRole("button", { name: "開始擷取" }));
    await waitFor(() => { expect(fetchCalled).toBe(true); });
  });
});

// docs/specs/2026-08-01-rd-hit-priority.md §3.4 / §4.
//
// The heuristic itself is pinned in rdPriority.test.ts. What only the
// component can show is the wiring: that the one-click narrowing honours the
// "a pasted magnet is an explicit instruction" invariant, and that the
// pre-send triage changes which handles actually reach rd_send_magnet — a
// panel that merely rendered a warning would pass a DOM-only assertion.
describe("RD hit-priority narrowing and pre-send triage", () => {
  const RD_URL = "https://javdb.com/v/RD001";

  const webRow = (over: Partial<MagnetRow> & { handle_id: string }): MagnetRow => ({
    name: "RD-001.mp4",
    size: "3.0GB, 1個文件",
    tags: [],
    date: "2026-01-02",
    magnet_redacted: "magnet:?xt=urn:btih:rd…",
    ...over,
  });

  /** Re-upload prefix AND 1080p in the name → prefix_hd, the top tier. */
  const PREFIX_HD = webRow({
    handle_id: "w-prefix",
    name: "hhd800.com@RD-001-1080p.mp4",
    date: "2026-01-03",
  });
  /** 高清 tag without a prefix → hd. Also high likelihood. */
  const TAGGED_HD = webRow({
    handle_id: "w-hd",
    name: "RD-001-full.mkv",
    tags: ["高清"],
  });
  /** Carries metadata and none of it says HD → plain, the ONLY class that
   * trips the confirmation. */
  const PLAIN = webRow({
    handle_id: "w-plain",
    name: "RD-001-sd.mp4",
    tags: ["中文字幕"],
    date: "2026-01-01",
  });

  /** One scraped group. A single URL settles immediately — scrapeBatch only
   * paces BETWEEN urls. */
  const scrapeRows = async (magnets: MagnetRow[]): Promise<void> => {
    handlers.fetch_javdb = () => ({
      engine: "test",
      url: RD_URL,
      code: "RD-001",
      title: "t",
      magnet_count: magnets.length,
      magnets,
    });
    const urlBox = screen.getByPlaceholderText(/javdb\.com\/v\//) as HTMLTextAreaElement;
    await fireEvent.input(urlBox, { target: { value: `${RD_URL}\n` } });
    await fireEvent.click(screen.getByRole("button", { name: "開始擷取" }));
    await waitFor(() => {
      expect(tauriMocks.invoke).toHaveBeenCalledWith("fetch_javdb", { url: RD_URL });
    });
  };

  /** Anchored on the checkbox's `選取 <name>` label rather than the 番號 cell:
   * the badges render inside that cell and would change its accessible name. */
  const rowCheck = (name: string): HTMLInputElement =>
    screen.getByRole("checkbox", { name: `選取 ${name}`, hidden: true }) as HTMLInputElement;

  const sentHandles = (): string[] =>
    tauriMocks.invoke.mock.calls
      .filter((c) => c[0] === "rd_send_magnet")
      .map((c) => (c[1] as { handleId: string }).handleId);

  it("checks only the web candidates and leaves pasted rows exactly as they were", async () => {
    await mountApp();
    await pasteOneMagnet();
    await scrapeRows([PREFIX_HD, PLAIN]);
    await clickTab(SELECT_TAB);

    // Scraping and pasting both auto-check their rows, so the button can only
    // be observed by what it UNchecks.
    expect(rowCheck("SNOS-192").checked).toBe(true);
    expect(rowCheck("RD-001-sd.mp4").checked).toBe(true);

    await fireEvent.click(screen.getByRole("button", { name: "只勾選 RD 優先候選" }));

    expect(rowCheck("hhd800.com@RD-001-1080p.mp4").checked).toBe(true);
    expect(rowCheck("RD-001-sd.mp4").checked).toBe(false);
    // The invariant this test exists for: a pasted magnet is an explicit
    // instruction (registerPastedMagnets), so a web-side narrowing must not
    // reach it — selectOnlyRows, which clears every selectable row, would.
    expect(rowCheck("SNOS-192").checked).toBe(true);
    expect(isShown(screen.getByText(/手貼 1 筆維持原狀/))).toBe(true);
  });

  it("holds a batch containing low-likelihood rows and then sends only the high ones", async () => {
    await mountApp();
    await scrapeRows([PREFIX_HD, PLAIN]);
    await clickTab(RD_TAB);

    await fireEvent.click(within(rdPanel()).getByRole("button", { name: /送出已勾選/ }));
    // Nothing reached RD — the click opened the summary instead of sending.
    expect(sentHandles()).toEqual([]);
    expect(isShown(screen.getByText(/送出前確認/))).toBe(true);

    await fireEvent.click(within(rdPanel()).getByRole("button", { name: /只送高機率/ }));
    await waitFor(() => {
      expect(sentHandles()).toEqual(["w-prefix"]);
    });
    // The panel is one-shot: leaving it up would let a second click re-send.
    expect(screen.queryByText(/送出前確認/)).toBeNull();
  });

  it("sends straight through when no checked row is a low-likelihood one", async () => {
    await mountApp();
    await scrapeRows([PREFIX_HD, TAGGED_HD]);
    await clickTab(RD_TAB);

    await fireEvent.click(within(rdPanel()).getByRole("button", { name: /送出已勾選/ }));
    await waitFor(() => {
      expect(sentHandles()).toEqual(["w-prefix", "w-hd"]);
    });
    // A batch with nothing to warn about keeps its existing one-click send.
    expect(screen.queryByText(/送出前確認/)).toBeNull();
  });

  /**
   * The web narrowing and the pasted row share ONE handle here. The sidecar
   * keys handles by BTIH, so pasting a magnet that a scrape already returned
   * yields the same handle_id — and `selectedHandles` is keyed by handle, so
   * "uncheck every web row" reaches straight through into the manual group.
   * The test above cannot see this: its pasted handle is disjoint.
   */
  it("keeps a pasted magnet checked when a scraped row shares its handle", async () => {
    await mountApp();
    await scrapeRows([PREFIX_HD, PLAIN]);
    handlers.register_magnets = () => ({
      // Same handle as the scraped PLAIN row; distinct display name so the
      // two rows' checkboxes stay individually addressable.
      registered: [
        {
          handle_id: "w-plain",
          magnet_redacted: "magnet:?xt=urn:btih:rd…",
          name: "RD-001-pasted-twin",
          deduped: true,
        },
      ],
      invalid: [] as string[],
    });
    await pasteOneMagnet();
    await clickTab(SELECT_TAB);
    expect(rowCheck("RD-001-pasted-twin").checked).toBe(true);

    await fireEvent.click(screen.getByRole("button", { name: "只勾選 RD 優先候選" }));

    expect(rowCheck("hhd800.com@RD-001-1080p.mp4").checked).toBe(true);
    // Still checked: the user pasted this exact magnet, and the message the
    // same click prints says so.
    expect(rowCheck("RD-001-pasted-twin").checked).toBe(true);
    expect(isShown(screen.getByText(/手貼 1 筆維持原狀/))).toBe(true);
  });

  /**
   * 每組只留 = 最大檔 collapses the group to one row before it is rendered.
   * If the candidate were picked from the merely-filtered rows instead of the
   * rendered ones, the ★ would vanish and the one-click narrowing would check
   * a magnet that is not on screen — leaving the user with a non-zero
   * selection they can neither see nor uncheck in that view.
   */
  it("picks from the rows actually on screen when 每組只留 collapses the group", async () => {
    await mountApp();
    await scrapeRows([
      PREFIX_HD,
      webRow({
        handle_id: "w-big",
        name: "RD-001-big.mkv",
        size: "8.0GB, 1個文件",
        tags: ["高清"],
      }),
    ]);
    await clickTab(SELECT_TAB);
    await fireEvent.change(screen.getByLabelText(/每組只留/), {
      target: { value: "largest" },
    });

    await fireEvent.click(screen.getByRole("button", { name: "只勾選 RD 優先候選" }));

    // The single rendered row is the one that got checked. Under the old
    // behavior the invisible w-prefix row won instead and this went false.
    expect(rowCheck("RD-001-big.mkv").checked).toBe(true);
    await clickTab(RD_TAB);
    expect(isShown(screen.getByText(/送出已勾選 1 筆到 RD/))).toBe(true);
  });

  it("sends what is checked NOW, not what was checked when the panel opened", async () => {
    await mountApp();
    await scrapeRows([PREFIX_HD, PLAIN]);
    await clickTab(RD_TAB);
    await fireEvent.click(within(rdPanel()).getByRole("button", { name: /送出已勾選/ }));
    expect(isShown(screen.getByText(/送出前確認：2 筆/))).toBe(true);

    // 回到挑選 is not disabled while the panel is up, so the checkboxes stay
    // live behind it. Sending a row the user has since unchecked would break
    // the rule that the batch follows the checkboxes.
    await clickTab(SELECT_TAB);
    await fireEvent.click(rowCheck("hhd800.com@RD-001-1080p.mp4"));
    await clickTab(RD_TAB);
    expect(isShown(screen.getByText(/送出前確認：1 筆/))).toBe(true);

    await fireEvent.click(within(rdPanel()).getByRole("button", { name: /全部送出/ }));
    await waitFor(() => {
      expect(sentHandles()).toEqual(["w-plain"]);
    });
  });

  it("drops the panel when a new scrape forgets the handles it was triaging", async () => {
    await mountApp();
    await scrapeRows([PREFIX_HD, PLAIN]);
    await clickTab(RD_TAB);
    await fireEvent.click(within(rdPanel()).getByRole("button", { name: /送出已勾選/ }));
    expect(isShown(screen.getByText(/送出前確認/))).toBe(true);

    // startScrape hands the old web handles to forget_magnets; a panel left
    // open would offer to send handles the sidecar no longer knows.
    await clickTab(SEARCH_TAB);
    await scrapeRows([TAGGED_HD]);
    await clickTab(RD_TAB);

    expect(screen.queryByText(/送出前確認/)).toBeNull();
    expect(sentHandles()).toEqual([]);
  });

  it("re-checks the token guard on the panel's own send button", async () => {
    await mountApp();
    await scrapeRows([PREFIX_HD, PLAIN]);
    await clickTab(RD_TAB);
    await fireEvent.click(within(rdPanel()).getByRole("button", { name: /送出已勾選/ }));
    expect(isShown(screen.getByText(/送出前確認/))).toBe(true);

    // The panel outlives a trip to 設定, where the token can be cleared.
    handlers.rd_clear_token = () => null;
    await clickTab(SETTINGS_TAB);
    await fireEvent.click(screen.getByRole("button", { name: "清除 Token" }));
    await waitFor(() => {
      expect(tauriMocks.invoke).toHaveBeenCalledWith("rd_clear_token");
    });
    await clickTab(RD_TAB);
    await fireEvent.click(within(rdPanel()).getByRole("button", { name: /全部送出/ }));

    expect(sentHandles()).toEqual([]);
    expect(screen.queryAllByText(/請先設定 RD Token/).some(isShown)).toBe(true);
  });
});
