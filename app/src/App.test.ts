// Component tests for the four-tab shell (Task.md 2.1 / 2.4 / 2.5).
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
  PathInfo,
  PendingEntry,
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
    // Task.md 2.4 — anchored on the stable input id so an editor that gets
    // re-wrapped rather than moved still fails here.
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

    // Task.md 2.2 — the outcome must be readable on tab 1, not only after
    // switching to 「2. 挑選 Magnet」.
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

    // Task.md 1.3: the wording must not imply RD's real finish time.
    const header = screen.getByRole("columnheader", { name: /完成時間/, hidden: true });
    expect(header.textContent).toContain("本程式確認");
    expect(header.getAttribute("title")).toContain("非 Real-Debrid 伺服器");
  });
});
