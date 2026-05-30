<script lang="ts">
  import { onMount } from "svelte";
  import { createFlashController } from "./lib/flashAction";
  import { invoke } from "@tauri-apps/api/core";
  import { open as openExternal } from "@tauri-apps/plugin-shell";
  import {
    parseMagnetBatch,
    parseUrlBatch,
    scrapeBatch,
    type ScrapeProgressEvent,
  } from "./lib/scraper";
  import { errText } from "./lib/errText";
  import { dedupeByHandleId, processGroupRows } from "./lib/magnetUtils";
  import {
    FILE_PICK_VALUES,
    SCALE_PRESETS,
    THEME_VALUES,
    validateSettingsDraft,
  } from "./lib/settingsValidation";
  import {
    collectDownloadLinksFromRow,
    rdErrorMessage,
    retryPending,
    sendBatch,
    sortCompletedRowsByCompletionTime,
    type RdRetryEvent,
    type RdSendBatchEvent,
    type RdSendItem,
  } from "./lib/rdSender";
  import {
    defaultFilterState,
    type CookiesStatus,
    type CopyBulkResult,
    type CopyRdLinksBulkResult,
    type FilterState,
    type LegacyImportPreview,
    type LegacyImportReport,
    type GroupPick,
    type MagnetRow,
    type PathInfo,
    type PendingEntry,
    type PingResponse,
    type RdSendProgress,
    type RdUserInfo,
    type ScrapedGroup,
    type Settings,
    type SortColumn,
    type SortDirection,
    type Theme,
  } from "./lib/types";

  let dataDir = $state("（載入中）");
  let logDir = $state("（載入中）");
  let theme = $state<Theme>("light");
  let settings = $state<Settings | null>(null);
  let statusMessage = $state("");

  // M4a — batch scrape state
  let urlBatch = $state("https://javdb.com/v/RkX3Rp\n");
  let magnetBatch = $state("");
  let isRegistering = $state(false);
  /** Inline status for the "register pasted magnets" section. Kept separate
   * from the global `statusMessage` so the user sees the result next to the
   * button they just clicked, not at the top of the page. */
  let registerStatus = $state<{ kind: "info" | "error" | "ok"; text: string } | null>(null);
  let groups = $state<ScrapedGroup[]>([]);
  let scrapeProgress = $state<{ done: number; total: number }>({
    done: 0,
    total: 0,
  });
  let isScraping = $state(false);
  let scrapeAbort: AbortController | null = null;

  // M4b — filter / sort / collapse state
  let filter = $state<FilterState>(defaultFilterState());
  // Bound separately because the inputs return strings; we coerce on commit.
  let minSizeInput = $state("");
  let maxSizeInput = $state("");
  let sortColumn = $state<SortColumn | null>(null);
  let sortDirection = $state<SortDirection>("asc");
  /** Per-group collapsed flag keyed by URL. Default = expanded. */
  let collapsed = $state<Record<string, boolean>>({});

  let pingMessage = $state("");

  // M5 — Real-Debrid state
  let rdHasToken = $state(false);
  let rdUser = $state<RdUserInfo | null>(null);
  let rdTokenInput = $state("");
  let rdShowToken = $state(false);
  let rdMessage = $state("");
  let rdSendProgress = $state<RdSendProgress[]>([]);
  let rdSendDone = $state<{ done: number; total: number }>({ done: 0, total: 0 });
  let isRdSending = $state(false);
  let rdSendAbort: AbortController | null = null;
  let pendingEntries = $state<PendingEntry[]>([]);
  let isRetryingPending = $state(false);
  let lastBatchStartAt = $state(new Date().toISOString());
  let retryAbort: AbortController | null = null;
  // Inline status for the pending section, rendered right under the
  // section header so feedback is visible without scrolling back up
  // to the Real-Debrid block (where rdMessage lives).
  let pendingMessage = $state<{ kind: "ok" | "info" | "error"; text: string } | null>(null);

  // M7a-lite: Manual legacy data import
  let legacyPath = $state("");
  let legacyPreview = $state<LegacyImportPreview | null>(null);
  let legacyReport = $state<LegacyImportReport | null>(null);
  let legacyBusy = $state(false);
  let legacyError = $state("");
  let legacyShown = $state(false);

  // M7b: Cookies / data-dir status
  let cookiesStatus = $state<CookiesStatus | null>(null);
  let cookiesShown = $state(false);
  let cookiesError = $state("");
  let cookiesMessage = $state<{ kind: "ok" | "info" | "error"; text: string } | null>(null);
  // M9: Direct paste flow — alternative to "create template + edit file +
  // restart". Pasting a cookie header here writes the keyring + live-
  // updates the running sidecar, so no restart is needed.
  let cookiesPasteOpen = $state(false);
  let cookiesPasteInput = $state("");
  let cookiesSaving = $state(false);

  // M7c: Settings editor
  let settingsShown = $state(false);
  let settingsDraft = $state<Settings | null>(null);
  let settingsSaving = $state(false);
  let settingsMessage = $state("");
  let settingsMessageKind = $state<"ok" | "error" | "info">("info");

  function applyTheme(t: Theme) {
    document.documentElement.dataset.theme = t;
  }

  /**
   * Apply settings.ui.scale as a CSS variable that index.css can hook into
   * via `font-size: calc(... * var(--ui-scale, 1))` if it wants. We also
   * scale the root font-size directly so default `rem` units track DPI.
   * Accepts "auto" → 1.0; numeric strings 0.5–3.0 clamp; everything else → 1.
   */
  function applyScale(raw: string) {
    let scale = 1;
    if (raw && raw.toLowerCase() !== "auto") {
      const v = parseFloat(raw);
      if (isFinite(v) && v >= 0.5 && v <= 3.0) scale = v;
    }
    document.documentElement.style.setProperty("--ui-scale", String(scale));
    document.documentElement.style.fontSize = `${scale * 16}px`;
  }

  onMount(async () => {
    try {
      const paths = await invoke<PathInfo>("get_paths");
      dataDir = paths.data_dir;
      logDir = paths.log_dir;
    } catch (e) {
      dataDir = `錯誤：${e}`;
      logDir = `錯誤：${e}`;
    }

    try {
      const s = await invoke<Settings>("read_settings");
      settings = s;
      theme = s.ui.theme;
      applyTheme(theme);
      applyScale(s.ui.scale);
    } catch (e) {
      console.error("read_settings failed:", e);
      statusMessage = `讀取設定失敗：${e}`;
    }

    // RD token presence + pending list. Both are best-effort on startup.
    try {
      const r = await invoke<{ present: boolean }>("rd_has_token");
      rdHasToken = r.present;
    } catch (e) {
      console.warn("rd_has_token failed:", e);
    }
    try {
      pendingEntries = await invoke<PendingEntry[]>("pending_list");
    } catch (e) {
      console.warn("pending_list failed:", e);
    }

    // M7a-lite: pre-fill legacy import path from env var if dev/test set it.
    // The env var itself NEVER triggers an import; only pre-fills the input.
    try {
      const def = await invoke<string>("get_legacy_default_dir");
      if (def && def.trim().length > 0) {
        legacyPath = def;
        legacyShown = true;
      }
    } catch (e) {
      console.warn("get_legacy_default_dir failed:", e);
    }

    // M7b: cookies status snapshot. Best-effort.
    await refreshCookiesStatus();
  });

  async function toggleTheme() {
    if (settings === null) {
      statusMessage = "設定尚未載入";
      return;
    }
    theme = theme === "light" ? "dark" : "light";
    applyTheme(theme);
    settings.ui.theme = theme;
    try {
      await invoke("write_settings", { settings });
      statusMessage = `主題已儲存：${theme}`;
    } catch (e) {
      console.error("write_settings failed:", e);
      statusMessage = `儲存設定失敗：${e}`;
    }
  }

  async function pingSidecar() {
    pingMessage = "（ping 中…）";
    try {
      const resp = await invoke<PingResponse>("sidecar_ping");
      pingMessage = `回應正常 — 已執行 ${resp.uptime_seconds} 秒，request_id ${resp.request_id}`;
      flash.flash("ping-sidecar");
    } catch (e) {
      pingMessage = `錯誤：${e}`;
    }
  }

  async function startScrape() {
    if (isScraping) return;
    const urls = parseUrlBatch(urlBatch);
    if (urls.length === 0) {
      statusMessage = "批次中沒有有效網址";
      return;
    }

    // Initialize the result slots so the UI can render placeholders before
    // any fetch completes.
    groups = urls.map((url) => ({
      url,
      status: "pending" as const,
      result: null,
      error: null,
      finished_at: null,
    }));
    scrapeProgress = { done: 0, total: urls.length };
    isScraping = true;
    scrapeAbort = new AbortController();

    try {
      await scrapeBatch(
        urls,
        (ev: ScrapeProgressEvent) => {
          // Replace the slot with the settled group so Svelte 5 fine-grained
          // reactivity picks up the change.
          groups[ev.index - 1] = ev.group;
          scrapeProgress = { done: ev.index, total: ev.total };
        },
        { signal: scrapeAbort.signal },
      );
    } finally {
      isScraping = false;
      scrapeAbort = null;
    }
  }

  function cancelScrape() {
    scrapeAbort?.abort();
  }

  /**
   * "Paste magnet → register" path. Sidecar deduces and assigns handle_ids;
   * the result becomes a synthetic group in `groups[]` so all the existing
   * filter / sort / send-to-RD plumbing applies unchanged.
   */
  async function registerPastedMagnets() {
    if (isRegistering) return;
    const magnets = parseMagnetBatch(magnetBatch);
    if (magnets.length === 0) {
      // Detect a common user mistake: pasting JavDB URLs into the magnet box.
      const looksLikeUrls = /^\s*https?:\/\//im.test(magnetBatch);
      registerStatus = {
        kind: "error",
        text: looksLikeUrls
          ? "你貼的看起來是 JavDB 網址（http/https）。請改貼到上方「批次擷取」按「開始擷取」；本欄只接受 magnet:?xt=... 開頭的磁力連結。"
          : "未偵測到有效磁力連結（必須以 magnet: 開頭）",
      };
      return;
    }
    isRegistering = true;
    registerStatus = { kind: "info", text: "加入中…" };
    try {
      const resp = await invoke<{
        registered: { handle_id: string; magnet_redacted: string; name: string; deduped: boolean }[];
        invalid: string[];
      }>("register_magnets", { magnets });

      // Build the set of handle_ids already shown in any existing group
      // so we can skip rows whose sidecar handle is reused from a prior
      // scrape / paste — they'd otherwise appear twice in the UI and
      // double-bill RD on send.
      const existingHandleIds = new Set<string>();
      for (const g of groups) {
        if (g.result) {
          for (const m of g.result.magnets) existingHandleIds.add(m.handle_id);
        }
      }

      const newRows: MagnetRow[] = [];
      let skippedExisting = 0;
      for (const r of resp.registered) {
        if (r.deduped && existingHandleIds.has(r.handle_id)) {
          skippedExisting += 1;
          continue;
        }
        newRows.push({
          handle_id: r.handle_id,
          // Use the `dn=` extract returned by sidecar so this row
          // can display its own JAV code (e.g. "SNOS-192") in the
          // result table and the 送 RD 進度 番號 column. Empty when
          // the magnet had no dn parameter.
          name: r.name,
          size: "",
          tags: [],
          date: "",
          magnet_redacted: r.magnet_redacted,
        });
      }

      if (newRows.length > 0) {
        // Synthetic group: unique URL key uses a timestamp so multiple
        // paste batches don't collide. UI shows "(直接貼上)" instead of
        // a JavDB URL.
        const syntheticUrl = `manual://${Date.now()}`;
        groups = [
          ...groups,
          {
            url: syntheticUrl,
            status: "ok" as const,
            finished_at: new Date().toISOString(),
            error: null,
            result: {
              engine: "manual",
              url: syntheticUrl,
              code: `(直接貼上 ${newRows.length})`,
              title: "",
              magnet_count: newRows.length,
              magnets: newRows,
            },
          },
        ];
      }

      magnetBatch = "";
      const invalidCount = resp.invalid.length;
      const fragments: string[] = [];
      if (newRows.length > 0) fragments.push(`已加入 ${newRows.length} 筆到下方結果清單`);
      if (skippedExisting > 0)
        fragments.push(`已跳過 ${skippedExisting} 筆已存在於現有群組的磁力`);
      if (invalidCount > 0) fragments.push(`忽略 ${invalidCount} 個無效輸入`);
      registerStatus = {
        kind: newRows.length > 0 ? "ok" : "info",
        text: fragments.length > 0
          ? fragments.join("；") + "。"
          : "沒有可加入的磁力連結。",
      };
      if (newRows.length > 0) flash.flash("magnet-register");
    } catch (e) {
      registerStatus = { kind: "error", text: `加入失敗：${e}` };
    } finally {
      isRegistering = false;
    }
  }

  async function copyOne(handle_id: string, label: string) {
    try {
      await invoke("copy_magnet", { handleId: handle_id });
      statusMessage = `已複製 ${label} 的磁力連結`;
      flash.flash(`magnet-copy-${handle_id}`);
    } catch (e) {
      statusMessage = `複製失敗：${e}`;
    }
  }

  async function copyVisible() {
    // Collect handle_ids from VISIBLE rows (after filter + group pick + sort).
    // Dedupe across groups in case the UI happens to render the same
    // handle in two cards — clipboard should never contain duplicate
    // magnet URIs even if the sidecar would silently coalesce them.
    const visible = groups.flatMap((g) => processedRows(g));
    const ids = dedupeByHandleId(visible).map((m) => m.handle_id);
    if (ids.length === 0) return;
    try {
      const result = await invoke<CopyBulkResult>("copy_magnets_bulk", {
        handleIds: ids,
      });
      statusMessage =
        result.unknown > 0
          ? `已複製 ${result.copied} 個，另有 ${result.unknown} 個過期`
          : `已複製 ${result.copied} 個磁力連結`;
      flash.flash("magnet-copy-visible");
    } catch (e) {
      statusMessage = `批次複製失敗：${e}`;
    }
  }

  // ---- M4b: filter / sort / group helpers ----------------------------
  function processedRows(g: ScrapedGroup): MagnetRow[] {
    return processGroupRows(g, filter, sortColumn, sortDirection);
  }

  function toggleSort(col: SortColumn) {
    if (sortColumn === col) {
      sortDirection = sortDirection === "asc" ? "desc" : "asc";
    } else {
      sortColumn = col;
      sortDirection = "asc";
    }
  }

  function sortIndicator(col: SortColumn): string {
    if (sortColumn !== col) return "";
    return sortDirection === "asc" ? " ▲" : " ▼";
  }

  function commitMinSize() {
    const v = parseFloat(minSizeInput);
    filter.min_size_gb = isFinite(v) && v > 0 ? v : null;
  }

  function commitMaxSize() {
    const v = parseFloat(maxSizeInput);
    filter.max_size_gb = isFinite(v) && v > 0 ? v : null;
  }

  function setGroupPick(p: GroupPick) {
    filter.group_pick = p;
  }

  function resetFilter() {
    filter = defaultFilterState();
    minSizeInput = "";
    maxSizeInput = "";
    sortColumn = null;
    sortDirection = "asc";
  }

  function toggleCollapsed(url: string) {
    collapsed[url] = !collapsed[url];
  }

  async function clearResults() {
    if (isScraping) {
      scrapeAbort?.abort();
    }
    // Snapshot handle ids before nuking the array so the sidecar can drop them.
    const ids: string[] = [];
    for (const g of groups) {
      if (g.result) {
        for (const m of g.result.magnets) ids.push(m.handle_id);
      }
    }
    groups = [];
    scrapeProgress = { done: 0, total: 0 };
    collapsed = {};
    if (ids.length > 0) {
      try {
        const forgotten = await invoke<number>("forget_magnets", {
          handleIds: ids,
        });
        statusMessage = `已清空 ${forgotten} 筆磁力 handle`;
      } catch (e) {
        // Don't surface as an error — UI is already cleared, sidecar will GC
        // stale handles on its own eventually.
        console.warn("forget_magnets failed:", e);
        statusMessage = "結果已清空（sidecar 之後會自動 GC）";
      }
    } else {
      statusMessage = "結果已清空";
    }
    flash.flash("scrape-clear");
  }

  // ---- derived counts for status bar ---------------------------------
  let okCount = $derived(groups.filter((g) => g.status === "ok").length);
  let errCount = $derived(groups.filter((g) => g.status === "error").length);
  let totalRawMagnets = $derived(
    groups.reduce((acc, g) => acc + (g.result?.magnet_count ?? 0), 0),
  );
  // Counts unique handle_ids across all visible (filtered/sorted/grouped)
  // rows, so the action-row button labels match what
  // `buildVisibleSendItems` / `copyVisible` will actually do after
  // their handle_id dedupe.
  let visibleMagnets = $derived.by(() => {
    const visible = groups.flatMap((g) => processedRows(g));
    return dedupeByHandleId(visible).length;
  });

  // ---- M5: Real-Debrid handlers --------------------------------------
  async function rdTestToken() {
    rdMessage = "（測試中…）";
    try {
      const u = await invoke<RdUserInfo>("rd_test_token", {
        token: rdTokenInput.trim(),
      });
      rdUser = u;
      rdMessage = `測試成功：${u.username || "(無 username)"} / ${u.type} / 點數 ${u.points}`;
      flash.flash("rd-test-token");
    } catch (e) {
      rdUser = null;
      const code = errText(e);
      rdMessage = `測試失敗：${rdErrorMessage(code)}`;
    }
  }

  async function rdSaveToken() {
    if (!rdTokenInput.trim()) {
      rdMessage = "請先輸入 Token";
      return;
    }
    try {
      await invoke("rd_save_token", { token: rdTokenInput.trim() });
      rdHasToken = true;
      rdTokenInput = "";
      rdShowToken = false;
      rdMessage = "Token 已儲存到系統憑證管理員";
      flash.flash("rd-save-token");
      // Refresh user info from saved token (no token sent over IPC).
      try {
        rdUser = await invoke<RdUserInfo>("rd_check_user");
      } catch (e) {
        const code = errText(e);
        rdMessage = `Token 已儲存，但驗證失敗：${rdErrorMessage(code)}`;
      }
    } catch (e) {
      const code = errText(e);
      rdMessage = `儲存失敗：${rdErrorMessage(code)}`;
    }
  }

  async function rdClearToken() {
    try {
      await invoke("rd_clear_token");
      rdHasToken = false;
      rdUser = null;
      rdTokenInput = "";
      rdMessage = "Token 已清除";
      flash.flash("rd-clear-token");
    } catch (e) {
      const code = errText(e);
      rdMessage = `清除失敗：${rdErrorMessage(code)}`;
    }
  }

  async function rdRefreshUser() {
    if (!rdHasToken) {
      rdMessage = "尚未設定 Token";
      return;
    }
    rdMessage = "（查詢中…）";
    try {
      rdUser = await invoke<RdUserInfo>("rd_check_user");
      rdMessage = `已連線：${rdUser.username || "(無 username)"} / ${rdUser.type}`;
      flash.flash("rd-refresh-user");
    } catch (e) {
      const code = errText(e);
      rdMessage = `查詢失敗：${rdErrorMessage(code)}`;
    }
  }

  /** Build the send-to-RD batch from the currently visible (filtered+sorted+
   * group-picked) rows. Dedupes by `handle_id` so a magnet that
   * happens to be rendered in two groups (e.g. JavDB re-fetch landing
   * on the same sidecar handle) is sent to RD exactly once. The
   * `code` of the first occurrence wins.
   *
   * Code-resolution priority:
   *   - For paste-magnet "synthetic" groups (url starts with
   *     `manual://`), prefer the row's own `name` (sidecar's `dn=`
   *     extract, e.g. "SNOS-192") so the 番號 column shows a real
   *     code per row instead of the synthetic group code
   *     "(直接貼上 N)". Falls back to group code if `dn=` was empty.
   *   - For JavDB-fetched groups, the group code (e.g. "SNOS-166")
   *     is the right level — all rows under that page share the
   *     same JAV code, while their `name` is the magnet filename.
   */
  function buildVisibleSendItems(): RdSendItem[] {
    const raw: RdSendItem[] = [];
    for (const g of groups) {
      const rows = processedRows(g);
      const groupCode = g.result?.code ?? "";
      const isPasteGroup = g.url.startsWith("manual://");
      for (const m of rows) {
        const code = isPasteGroup
          ? (m.name || groupCode || "(unknown)")
          : (groupCode || m.name || "(unknown)");
        raw.push({
          handle_id: m.handle_id,
          code,
          size_label: m.size,
        });
      }
    }
    return dedupeByHandleId(raw);
  }

  async function sendVisibleToRd() {
    if (isRdSending) return;
    if (!rdHasToken) {
      rdMessage = "請先到「Real-Debrid」區塊設定 Token";
      return;
    }
    const items = buildVisibleSendItems();
    if (items.length === 0) {
      rdMessage = "目前沒有可送出的磁力";
      return;
    }
    lastBatchStartAt = new Date().toISOString();
    isRdSending = true;
    rdSendProgress = items.map((it) => ({
      handle_id: it.handle_id,
      code: it.code,
      status: "pending",
      links: [],
      error_code: null,
    }));
    rdSendDone = { done: 0, total: items.length };
    rdSendAbort = new AbortController();
    rdMessage = "";

    try {
      await sendBatch(
        items,
        (ev: RdSendBatchEvent) => {
          rdSendProgress[ev.index - 1] = ev.item;
          if (ev.item.status !== "sending") {
            rdSendDone = { done: ev.index, total: ev.total };
          }
        },
        {
          signal: rdSendAbort.signal,
          defaults: settings
            ? {
                strategy: settings.rd.file_pick,
                min_size_mb: settings.rd.min_size_mb,
                cache_wait: settings.rd.cache_wait_seconds,
              }
            : {},
        },
      );
    } finally {
      isRdSending = false;
      rdSendAbort = null;
      // Refresh persistent pending list — rd_send_magnet on the Rust side
      // already added pending entries to disk.
      try {
        pendingEntries = await invoke<PendingEntry[]>("pending_list");
      } catch (e) {
        console.warn("pending_list failed:", e);
      }
    }
  }

  function cancelRdSend() {
    rdSendAbort?.abort();
  }

  // Reactive controller for all button post-action confirmation flashes.
  // Logic + 1.2s timer + debounce-on-re-click live in flashAction.ts and are
  // unit-tested there; this file only wires keys to templates and call sites.
  const flash = createFlashController();

  async function copyRdDownloads() {
    const lines: string[] = [];
    const completedRows = sortCompletedRowsByCompletionTime(
      rdSendProgress.filter((row) => row.status === "completed"),
      lastBatchStartAt,
    );
    for (const row of completedRows) {
      for (const link of row.links) {
        if (link.download) lines.push(link.download);
      }
    }
    if (lines.length === 0) {
      rdMessage = "目前沒有可複製的下載連結";
      return;
    }
    try {
      const result = await invoke<CopyRdLinksBulkResult>(
        "copy_rd_links_bulk",
        { links: lines },
      );
      rdMessage = `已複製 ${result.copied} 條 RD 下載連結`;
      flash.flash("rd-bulk");
    } catch (e) {
      rdMessage = `複製失敗：${e}`;
    }
  }

  /** Copy ALL download URLs for one completed row. */
  async function copyRdRow(row: RdSendProgress): Promise<void> {
    const lines = collectDownloadLinksFromRow(row);
    if (lines.length === 0) {
      rdMessage = `${row.code} 沒有可複製的下載連結`;
      return;
    }
    try {
      const result = await invoke<CopyRdLinksBulkResult>(
        "copy_rd_links_bulk",
        { links: lines },
      );
      rdMessage = `已複製 ${row.code} 的 ${result.copied} 條下載連結`;
      flash.flash(`rd-row-${row.handle_id}`);
    } catch (e) {
      rdMessage = `複製失敗：${e}`;
    }
  }

  /** Copy a SINGLE download URL (one file inside a row). */
  async function copyRdSingleLink(rowKey: string, link: string, linkIndex: number): Promise<void> {
    if (!link || !link.trim()) {
      rdMessage = "此檔案沒有可複製的下載連結";
      return;
    }
    try {
      const result = await invoke<CopyRdLinksBulkResult>(
        "copy_rd_links_bulk",
        { links: [link] },
      );
      rdMessage =
        result.copied > 0
          ? "已複製 1 條下載連結"
          : "複製失敗：連結為空";
      if (result.copied > 0) flash.flash(`rd-link-${rowKey}-${linkIndex}`);
    } catch (e) {
      rdMessage = `複製失敗：${e}`;
    }
  }

  /** Re-read pending_torrents.json from disk. NOTE: this does NOT
   * query RD — it just refreshes the local snapshot. The visible
   * effect is usually nil unless another app instance / external
   * editor modified the file. We surface this as an explicit
   * `pendingMessage` so the button is no longer "silent". */
  async function refreshPending() {
    try {
      pendingEntries = await invoke<PendingEntry[]>("pending_list");
      pendingMessage = {
        kind: "info",
        text: `已重新載入本機紀錄（${pendingEntries.length} 筆）。需要查 RD 端最新狀態請按「全部重試」。`,
      };
      flash.flash("pending-refresh");
    } catch (e) {
      pendingMessage = { kind: "error", text: `讀取待處理清單失敗：${e}` };
    }
  }

  async function retryAllPending() {
    if (isRetryingPending) return;
    if (pendingEntries.length === 0) return;
    lastBatchStartAt = new Date().toISOString();
    isRetryingPending = true;
    retryAbort = new AbortController();
    pendingMessage = { kind: "info", text: `重試中 0/${pendingEntries.length}…` };

    const completedLinks: string[] = [];
    let completedCount = 0;
    let stillPendingCount = 0;
    let missingCount = 0;
    let errorCount = 0;
    const errorCodes: string[] = [];

    // Reconcile the corresponding "送至 Real-Debrid 進度" row when a
    // pending entry resolves to completed/missing. torrent_id is unique
    // per row, so this patches at most one entry.
    const patchRowByTorrentId = (id: string, patch: Partial<RdSendProgress>) => {
      rdSendProgress = rdSendProgress.map((r) =>
        r.torrent_id === id ? { ...r, ...patch } : r,
      );
    };

    try {
      await retryPending(
        pendingEntries,
        (ev: RdRetryEvent) => {
          if (ev.result.kind === "completed") {
            completedCount += 1;
            for (const l of ev.result.links) {
              if (l.download) completedLinks.push(l.download);
            }
            // Flip row from "in_pending" → "completed" + attach links so
            // 直連 N counter and row label update without a manual refresh.
            patchRowByTorrentId(ev.torrent_id, {
              status: "completed",
              links: ev.result.links,
              error_code: null,
              completed_at: new Date().toISOString(),
            });
          } else if (ev.result.kind === "pending") {
            stillPendingCount += 1;
          } else if (ev.result.kind === "missing") {
            missingCount += 1;
            // Mark row as error so users don't think it's still queued forever.
            patchRowByTorrentId(ev.torrent_id, {
              status: "error",
              links: [],
              error_code: "rd_torrent_missing",
            });
          } else {
            errorCount += 1;
            errorCodes.push(ev.result.error_code);
          }
          pendingMessage = {
            kind: "info",
            text: `重試中 ${ev.index}/${ev.total}…`,
          };
        },
        { signal: retryAbort.signal },
      );
    } finally {
      isRetryingPending = false;
      retryAbort = null;
      // Re-read disk so the table reflects sidecar-side mutations
      // (entries removed on completed/missing; status/progress
      // updated for still-pending entries). We DON'T call the
      // refresh helper because that would overwrite pendingMessage
      // with a generic "已重新載入" line — we want the retry summary.
      try {
        pendingEntries = await invoke<PendingEntry[]>("pending_list");
      } catch (e) {
        console.warn("pending_list after retry failed:", e);
      }
    }

    // Build the summary fragments.
    const parts: string[] = [];
    if (completedCount > 0) parts.push(`${completedCount} 個完成`);
    if (stillPendingCount > 0) parts.push(`${stillPendingCount} 個仍在 RD 處理中`);
    if (missingCount > 0) parts.push(`${missingCount} 個已從 RD 消失（已移除）`);
    if (errorCount > 0) parts.push(`${errorCount} 個查詢失敗`);

    let summary = parts.length > 0 ? `重試完成：${parts.join("、")}` : "重試完成";

    if (completedLinks.length > 0) {
      try {
        const result = await invoke<CopyRdLinksBulkResult>(
          "copy_rd_links_bulk",
          { links: completedLinks },
        );
        summary += `；已複製 ${result.copied} 條 RD 下載連結到剪貼簿`;
      } catch (e) {
        summary += `；剪貼簿寫入失敗：${e}`;
      }
    }

    if (errorCount > 0 && errorCodes.length > 0) {
      // Surface the first error code so the user can act on it
      // (e.g. rd_token_invalid -> re-paste token).
      summary += `\n第一個失敗原因：${rdErrorMessage(errorCodes[0])}（code: ${errorCodes[0]}）`;
    }

    pendingMessage = {
      kind: errorCount > 0 ? "error" : (completedCount > 0 ? "ok" : "info"),
      text: summary,
    };
  }

  function cancelRetry() {
    retryAbort?.abort();
  }

  // ---- M7a-lite: Manual legacy data import ----------------------------
  // User-triggered only. Preview reads files but never echoes secret
  // values back to the WebView. Apply writes through Rust commands
  // (credential store + tauri-plugin-store + pending JSON) and reports
  // counts only.

  async function previewLegacyImport() {
    legacyError = "";
    legacyReport = null;
    legacyPreview = null;
    const dir = legacyPath.trim();
    if (!dir) {
      legacyError = "請先輸入 legacy 資料夾路徑";
      return;
    }
    legacyBusy = true;
    try {
      legacyPreview = await invoke<LegacyImportPreview>("preview_legacy_import", {
        sourceDir: dir,
      });
      flash.flash("legacy-preview");
    } catch (e) {
      legacyError = `預覽失敗：${e}`;
    } finally {
      legacyBusy = false;
    }
  }

  // ---- M7b: Cookies / data-dir helpers --------------------------------
  async function refreshCookiesStatus() {
    cookiesError = "";
    try {
      // M9: "重新整理 / 套用變更" runs the file→keyring migration on demand
      // (was previously a startup-only path) AND pushes the migrated value
      // to the running sidecar, so a cf_clearance refresh takes effect
      // without an app restart. If no file exists or only the template
      // scaffold is present, this is a cheap status read with no side
      // effects.
      cookiesStatus = await invoke<CookiesStatus>("migrate_cookies_now");
      flash.flash("cookies-refresh");
    } catch (e) {
      cookiesError = `更新 cookies 狀態失敗：${e}`;
      try {
        // Fallback: at least show a read-only snapshot if the migrate path
        // surfaced an error (e.g. sidecar transient issue) so the UI
        // doesn't drop to "null" and lose all state.
        cookiesStatus = await invoke<CookiesStatus>("get_cookies_status");
      } catch {
        cookiesStatus = null;
      }
    }
  }

  function toggleCookiesPaste() {
    cookiesPasteOpen = !cookiesPasteOpen;
    cookiesMessage = null;
    cookiesError = "";
    if (!cookiesPasteOpen) cookiesPasteInput = "";
  }

  async function saveCookies() {
    const value = cookiesPasteInput.trim();
    if (!value) {
      cookiesMessage = { kind: "error", text: "請貼上 cookie 字串再儲存。" };
      return;
    }
    cookiesSaving = true;
    cookiesError = "";
    cookiesMessage = null;
    try {
      cookiesStatus = await invoke<CookiesStatus>("save_cookies", {
        cookies: value,
      });
      cookiesPasteInput = "";
      cookiesPasteOpen = false;
      cookiesMessage = {
        kind: "ok",
        text: "cookies 已加密儲存到 Credential Manager，sidecar 已即時更新（不必重啟 app）。",
      };
      flash.flash("cookies-save");
    } catch (e) {
      const code = errText(e);
      const friendly =
        code === "cookies_empty"
          ? "cookies 為空"
          : code === "cookies_too_large"
            ? "cookies 字串超過 64 KiB 上限"
            : code;
      cookiesMessage = { kind: "error", text: `儲存失敗：${friendly}` };
    } finally {
      cookiesSaving = false;
    }
  }

  async function openDataDir() {
    cookiesError = "";
    try {
      await invoke("open_data_dir");
    } catch (e) {
      cookiesError = `打開資料目錄失敗：${e}`;
    }
  }

  async function openLogsDir() {
    cookiesError = "";
    try {
      await invoke("open_logs_dir");
    } catch (e) {
      cookiesError = `打開 logs 目錄失敗：${e}`;
    }
  }

  async function createCookiesTemplate() {
    cookiesError = "";
    cookiesMessage = null;
    // Capture pre-create state so the success message can mention restart
    // only when keyring already holds cookies (= user is refreshing
    // cf_clearance, not setting up for the first time).
    const wasInKeyring = cookiesStatus?.storage === "keyring";
    try {
      await invoke("create_cookies_template");
      await refreshCookiesStatus();
      cookiesMessage = {
        kind: "ok",
        text: wasInKeyring
          ? "已建立新 cookies.txt 範本：編輯填入新 cookie 後，重啟 app 即會自動加密寫回 Credential Manager 並刪除明文檔。"
          : "已建立 cookies.txt 範本，請按「打開資料目錄」編輯並填入 cookie。填好後重啟 app 即會自動加密儲存。",
      };
      flash.flash("cookies-template");
    } catch (e) {
      cookiesMessage = { kind: "error", text: `建立範本失敗：${e}` };
    }
  }

  function formatBytes(n: number): string {
    if (n < 1024) return `${n} B`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
    return `${(n / 1024 / 1024).toFixed(1)} MB`;
  }

  // ---- M7c: Settings editor -------------------------------------------
  let settingsErrors = $derived<Record<string, string>>(
    settingsDraft ? validateSettingsDraft(settingsDraft) : {},
  );
  let settingsValid = $derived(Object.keys(settingsErrors).length === 0);

  // Deep-ish clone of `settings` for the editor draft. The `api_token`
  // is always blanked — backend re-blanks it on save, but we don't want
  // the draft to even appear to carry one.
  function freshSettingsDraft(s: Settings): Settings {
    return {
      version: s.version,
      ui: { ...s.ui },
      rd: { ...s.rd, api_token: "" },
    };
  }

  function openSettingsEditor() {
    if (!settings) {
      settingsMessage = "設定尚未載入";
      settingsMessageKind = "error";
      return;
    }
    settingsDraft = freshSettingsDraft(settings);
    settingsShown = true;
    settingsMessage = "";
  }

  async function saveSettings() {
    if (!settingsDraft) return;
    if (!settingsValid) {
      settingsMessage = "請先修正紅字欄位";
      settingsMessageKind = "error";
      return;
    }
    settingsSaving = true;
    settingsMessage = "";
    try {
      // Always blank api_token on save — the backend also blanks it
      // but we don't want the draft to even appear to carry one.
      const toSave: Settings = {
        ...settingsDraft,
        rd: { ...settingsDraft.rd, api_token: "" },
      };
      await invoke("write_settings", { settings: toSave });
      // Push to sidecar so this session reflects new values without
      // an app restart.
      try {
        await invoke("update_sidecar_settings", { settings: toSave });
      } catch (e) {
        console.warn("update_sidecar_settings failed:", e);
        // Non-fatal: the disk copy is saved; next launch will use new
        // values regardless.
      }
      // Refresh canonical settings + dependent UI state.
      settings = await invoke<Settings>("read_settings");
      theme = settings.ui.theme as Theme;
      applyTheme(theme);
      applyScale(settings.ui.scale);
      settingsDraft = freshSettingsDraft(settings);
      settingsMessage = "設定已儲存";
      settingsMessageKind = "ok";
      flash.flash("settings-save");
    } catch (e) {
      settingsMessage = `儲存失敗：${e}`;
      settingsMessageKind = "error";
    } finally {
      settingsSaving = false;
    }
  }

  function revertSettingsDraft() {
    if (!settings) return;
    settingsDraft = freshSettingsDraft(settings);
    settingsMessage = "已還原為已儲存值";
    settingsMessageKind = "info";
  }

  async function applyLegacyImportConfirmed() {
    legacyError = "";
    legacyReport = null;
    const dir = legacyPath.trim();
    if (!dir) {
      legacyError = "請先輸入 legacy 資料夾路徑";
      return;
    }
    legacyBusy = true;
    try {
      legacyReport = await invoke<LegacyImportReport>("apply_legacy_import", {
        sourceDir: dir,
      });
      // Refresh derived UI state that may have changed.
      if (legacyReport.rd_token_imported) {
        rdHasToken = true;
      }
      if (legacyReport.env_imported) {
        try {
          settings = await invoke<Settings>("read_settings");
          if (settings) {
            theme = settings.ui.theme as Theme;
            applyTheme(theme);
            applyScale(settings.ui.scale);
          }
        } catch (e) {
          console.warn("read_settings after import failed:", e);
        }
      }
      if (legacyReport.pending_imported > 0) {
        try {
          pendingEntries = await invoke<PendingEntry[]>("pending_list");
        } catch (e) {
          console.warn("pending_list after import failed:", e);
        }
      }
      if (legacyReport.cookies_imported) {
        await refreshCookiesStatus();
      }
      flash.flash("legacy-apply");
    } catch (e) {
      legacyError = `匯入失敗：${e}`;
    } finally {
      legacyBusy = false;
    }
  }

  async function removePending(torrent_id: string) {
    try {
      pendingEntries = await invoke<PendingEntry[]>("pending_remove", {
        torrentId: torrent_id,
      });
      pendingMessage = {
        kind: "ok",
        text: `已移除 1 筆，剩 ${pendingEntries.length} 筆`,
      };
    } catch (e) {
      pendingMessage = { kind: "error", text: `移除失敗：${e}` };
    }
  }

  async function clearAllPending() {
    try {
      await invoke("pending_clear");
      pendingEntries = [];
      pendingMessage = { kind: "ok", text: "待處理清單已清空" };
      flash.flash("pending-clear");
    } catch (e) {
      pendingMessage = { kind: "error", text: `清空失敗：${e}` };
    }
  }

  let rdCompletedCount = $derived(
    rdSendProgress.filter((r) => r.status === "completed").length,
  );
  let rdPendingCount = $derived(
    rdSendProgress.filter((r) => r.status === "in_pending").length,
  );
  let rdErrorCount = $derived(
    rdSendProgress.filter((r) => r.status === "error").length,
  );
  let rdDownloadLinkCount = $derived(
    rdSendProgress.reduce(
      (acc, r) => acc + (r.status === "completed" ? r.links.filter((l) => l.download).length : 0),
      0,
    ),
  );
</script>

<main class="container">
  <h1>JavDBMagnet</h1>
  <p class="subtitle">M5 — 批次擷取 + Real-Debrid</p>

  <section>
    <h2>儲存位置</h2>
    <dl>
      <dt>資料目錄</dt>
      <dd>{dataDir}</dd>
      <dt>日誌目錄</dt>
      <dd>{logDir}</dd>
    </dl>
  </section>

  <section>
    <h2>主題</h2>
    <button onclick={toggleTheme}>
      主題：{theme}（點擊切換）
    </button>
    {#if statusMessage}
      <p class="status">{statusMessage}</p>
    {/if}
  </section>

  <section>
    <h2>Sidecar</h2>
    <div class="row">
      <button
        onclick={pingSidecar}
        class:flash-ok={flash.keys.has("ping-sidecar")}
      >
        {flash.keys.has("ping-sidecar") ? "✓ Pong" : "Ping Sidecar"}
      </button>
      {#if pingMessage}
        <span class="ping">{pingMessage}</span>
      {/if}
    </div>
  </section>

  <section>
    <h2>Real-Debrid</h2>
    <div class="row">
      <span class="muted">
        Token：{rdHasToken
          ? "✓ 已設定（保留現狀即可，下方欄位僅在想更換時使用）"
          : "✗ 未設定"}
      </span>
      {#if rdHasToken}
        <button
          onclick={rdRefreshUser}
          class:flash-ok={flash.keys.has("rd-refresh-user")}
        >
          {flash.keys.has("rd-refresh-user") ? "已更新 ✓" : "查詢帳號"}
        </button>
        <button
          onclick={rdClearToken}
          class:flash-ok={flash.keys.has("rd-clear-token")}
        >
          {flash.keys.has("rd-clear-token") ? "已清除 ✓" : "清除 Token"}
        </button>
      {/if}
    </div>
    {#if rdUser}
      <p class="muted small">
        {rdUser.username || "(無 username)"} ／ {rdUser.type} ／ 點數 {rdUser.points}
        {#if rdUser.expiration}
          ／ 到期 {rdUser.expiration}
        {/if}
      </p>
    {/if}

    <div class="row stack">
      <label class="grow" for="rd-token-input">
        {rdHasToken ? "更換 Token" : "設定 Token"}（取得：
        <!-- `target="_blank"` alone does nothing in a Tauri WebView; we
             also intercept the click and hand the URL to tauri-plugin-shell's
             `open()` so it actually opens in the user's default browser.
             The capability is scoped to specific JavDB / RD domains in
             `capabilities/default.json`. -->
        <a
          href="https://real-debrid.com/apitoken"
          onclick={(e) => {
            e.preventDefault();
            openExternal("https://real-debrid.com/apitoken").catch((err) =>
              console.warn("openExternal failed:", err),
            );
          }}
        >real-debrid.com/apitoken</a>）
      </label>
      <div class="row">
        <input
          id="rd-token-input"
          type={rdShowToken ? "text" : "password"}
          bind:value={rdTokenInput}
          placeholder={rdHasToken ? "貼上新 Token 以更換" : "貼上 RD API Token"}
          spellcheck="false"
          autocomplete="off"
        />
        <label class="check small">
          <input type="checkbox" bind:checked={rdShowToken} />
          顯示
        </label>
        <button
          onclick={rdTestToken}
          disabled={!rdTokenInput.trim()}
          class:flash-ok={flash.keys.has("rd-test-token")}
        >
          {flash.keys.has("rd-test-token") ? "已測試 ✓" : "測試連線"}
        </button>
        <button
          onclick={rdSaveToken}
          disabled={!rdTokenInput.trim()}
          class:flash-ok={flash.keys.has("rd-save-token")}
        >
          {flash.keys.has("rd-save-token") ? "已儲存 ✓" : "儲存"}
        </button>
      </div>
    </div>
    {#if rdMessage}
      <p class="status">{rdMessage}</p>
    {/if}
  </section>

  <section>
    <h2>
      匯入舊版資料
      <button
        type="button"
        onclick={() => (legacyShown = !legacyShown)}
        style="margin-left: 0.5rem; font-size: 0.85rem; padding: 0.15rem 0.5rem;"
      >{legacyShown ? "▴ 收合" : "▾ 展開"}</button>
    </h2>
    {#if legacyShown}
      <p class="hint">
        從舊版 Python GUI 目錄匯入 <code>.env</code> / <code>cookies.txt</code> /
        <code>pending_torrents.json</code>。RD token 會放進系統憑證管理員、不寫入 settings.json；
        pending 匯入時會自動移除舊的 magnet 欄位。**舊檔不會被刪除**，匯入完成後你可自行刪除。
      </p>
      <div class="row">
        <input
          type="text"
          class="grow"
          bind:value={legacyPath}
          placeholder="例如：C:\Users\you\Desktop\程式語言\爬蟲"
          spellcheck="false"
          disabled={legacyBusy}
        />
        <button
          onclick={previewLegacyImport}
          disabled={legacyBusy || !legacyPath.trim()}
          class:flash-ok={flash.keys.has("legacy-preview")}
        >
          {legacyBusy
            ? "處理中…"
            : flash.keys.has("legacy-preview")
              ? "已預覽 ✓"
              : "預覽"}
        </button>
        <button
          onclick={applyLegacyImportConfirmed}
          disabled={legacyBusy || !legacyPreview || !legacyPreview.source_dir_valid}
          class:flash-ok={flash.keys.has("legacy-apply")}
        >
          {flash.keys.has("legacy-apply") ? "已匯入 ✓" : "匯入"}
        </button>
      </div>
      {#if legacyError}
        <p class="inline-msg" data-kind="error">{legacyError}</p>
      {/if}
      {#if legacyPreview}
        <div class="inline-msg" data-kind={legacyPreview.source_dir_valid ? "info" : "error"}>
          <strong>預覽：{legacyPreview.source_dir}</strong>
          {#if !legacyPreview.source_dir_valid}
            <p>路徑不存在或不是資料夾。</p>
          {:else}
            <ul>
              <li>
                .env：{legacyPreview.env_present ? "存在" : "（無）"}
                {#if legacyPreview.env_present}
                  ／RD_API_TOKEN：{legacyPreview.has_rd_token ? "✓（會移入憑證管理員）" : "（無）"}
                  ／可匯入設定鍵：{legacyPreview.env_settings_keys.length > 0
                    ? legacyPreview.env_settings_keys.join(", ")
                    : "（無）"}
                {/if}
              </li>
              <li>cookies.txt：{legacyPreview.cookies_present ? "存在（會複製到 app 資料目錄）" : "（無）"}</li>
              <li>
                pending_torrents.json：
                {legacyPreview.pending_present
                  ? `存在（${legacyPreview.pending_count} 筆；magnet 欄位會被移除）`
                  : "（無）"}
              </li>
            </ul>
            {#if legacyPreview.warnings.length > 0}
              <details>
                <summary>⚠ {legacyPreview.warnings.length} 條警告</summary>
                <ul>
                  {#each legacyPreview.warnings as w}
                    <li>{w}</li>
                  {/each}
                </ul>
              </details>
            {/if}
          {/if}
        </div>
      {/if}
      {#if legacyReport}
        <div class="inline-msg" data-kind="ok">
          <strong>匯入完成</strong>
          <ul>
            <li>RD Token：{legacyReport.rd_token_imported ? "✓ 已存入憑證管理員" : "（未匯入）"}</li>
            <li>.env 設定：{legacyReport.env_imported ? "✓ 已套用" : "（未匯入）"}</li>
            <li>cookies.txt：{legacyReport.cookies_imported ? "✓ 已複製" : "（未匯入）"}</li>
            <li>
              pending：匯入 {legacyReport.pending_imported} 筆
              {#if legacyReport.pending_skipped > 0}
                （略過 {legacyReport.pending_skipped} 筆已存在或無效）
              {/if}
            </li>
          </ul>
          {#if legacyReport.sources.length > 0}
            <details>
              <summary>來源檔（{legacyReport.sources.length}）</summary>
              <ul>
                {#each legacyReport.sources as s}
                  <li><code>{s}</code></li>
                {/each}
              </ul>
            </details>
          {/if}
          {#if legacyReport.warnings.length > 0}
            <details>
              <summary>⚠ {legacyReport.warnings.length} 條警告</summary>
              <ul>
                {#each legacyReport.warnings as w}
                  <li>{w}</li>
                {/each}
              </ul>
            </details>
          {/if}
          <p class="muted small">舊檔仍保留在來源位置，你可自行刪除。</p>
        </div>
      {/if}
    {/if}
  </section>

  <section>
    <h2>
      應用程式設定
      <button
        type="button"
        onclick={() => {
          if (!settingsShown) openSettingsEditor();
          else settingsShown = false;
        }}
        style="margin-left: 0.5rem; font-size: 0.85rem; padding: 0.15rem 0.5rem;"
      >{settingsShown ? "▴ 收合" : "▾ 展開"}</button>
    </h2>
    {#if settingsShown && settingsDraft}
      <p class="hint">
        編輯下列欄位後按「儲存設定」。RD Token 不在這裡管理 — 請到上方 <strong>Real-Debrid</strong> 區塊。
      </p>

      <fieldset style="border: 1px solid var(--border, #ccc); padding: 0.75rem; margin-bottom: 0.75rem;">
        <legend>Real-Debrid 行為</legend>
        <div class="row stack">
          <label class="grow" for="set-file-pick">
            檔案選擇策略（file_pick）
            <select id="set-file-pick" bind:value={settingsDraft.rd.file_pick}>
              {#each FILE_PICK_VALUES as v}
                <option value={v}>{v}</option>
              {/each}
            </select>
            {#if settingsErrors["rd.file_pick"]}
              <span class="err small">{settingsErrors["rd.file_pick"]}</span>
            {/if}
          </label>
        </div>
        <div class="row stack">
          <label class="grow" for="set-min-size">
            最小檔案大小（MB；&lt; 此值的影片視為廣告/雜訊跳過）
            <input
              id="set-min-size"
              type="number"
              min="0"
              step="1"
              bind:value={settingsDraft.rd.min_size_mb}
            />
            {#if settingsErrors["rd.min_size_mb"]}
              <span class="err small">{settingsErrors["rd.min_size_mb"]}</span>
            {/if}
          </label>
        </div>
        <div class="row stack">
          <label class="grow" for="set-cache-wait">
            快取判定等待秒數（cache_wait_seconds；≥ 5）
            <input
              id="set-cache-wait"
              type="number"
              min="5"
              step="1"
              bind:value={settingsDraft.rd.cache_wait_seconds}
            />
            {#if settingsErrors["rd.cache_wait_seconds"]}
              <span class="err small">{settingsErrors["rd.cache_wait_seconds"]}</span>
            {/if}
          </label>
        </div>
        <div class="row stack">
          <label class="grow" for="set-wait-timeout">
            最長等待秒數（wait_timeout_seconds；≥ 30）
            <input
              id="set-wait-timeout"
              type="number"
              min="30"
              step="1"
              bind:value={settingsDraft.rd.wait_timeout_seconds}
            />
            {#if settingsErrors["rd.wait_timeout_seconds"]}
              <span class="err small">{settingsErrors["rd.wait_timeout_seconds"]}</span>
            {/if}
          </label>
        </div>
      </fieldset>

      <fieldset style="border: 1px solid var(--border, #ccc); padding: 0.75rem; margin-bottom: 0.75rem;">
        <legend>介面</legend>
        <div class="row stack">
          <label class="grow" for="set-theme">
            主題
            <select id="set-theme" bind:value={settingsDraft.ui.theme}>
              {#each THEME_VALUES as v}
                <option value={v}>{v}</option>
              {/each}
            </select>
            {#if settingsErrors["ui.theme"]}
              <span class="err small">{settingsErrors["ui.theme"]}</span>
            {/if}
          </label>
        </div>
        <div class="row stack">
          <label class="grow" for="set-scale">
            縮放（scale；auto 或 0.5–3.0）
            <select id="set-scale" bind:value={settingsDraft.ui.scale}>
              {#each SCALE_PRESETS as v}
                <option value={v}>{v}</option>
              {/each}
            </select>
            {#if settingsErrors["ui.scale"]}
              <span class="err small">{settingsErrors["ui.scale"]}</span>
            {/if}
          </label>
        </div>
      </fieldset>

      <div class="row">
        <button
          onclick={saveSettings}
          disabled={!settingsValid || settingsSaving}
          class:flash-ok={flash.keys.has("settings-save")}
        >
          {settingsSaving
            ? "儲存中…"
            : flash.keys.has("settings-save")
              ? "已儲存 ✓"
              : "儲存設定"}
        </button>
        <button onclick={revertSettingsDraft} disabled={settingsSaving}>還原</button>
      </div>
      {#if settingsMessage}
        <p class="inline-msg" data-kind={settingsMessageKind}>{settingsMessage}</p>
      {/if}
    {/if}
  </section>

  <section>
    <h2>
      JavDB Cookies
      <button
        type="button"
        onclick={() => (cookiesShown = !cookiesShown)}
        style="margin-left: 0.5rem; font-size: 0.85rem; padding: 0.15rem 0.5rem;"
      >{cookiesShown ? "▴ 收合" : "▾ 展開"}</button>
    </h2>
    {#if cookiesShown}
      <p class="hint">
        JavDB 抓取需要登入後的 cookies。此區只顯示儲存位置 / 大小 / 修改時間，
        <strong>絕不讀取 cookies 內容</strong>。
      </p>
      {#if cookiesStatus}
        {#if cookiesStatus.storage === "keyring"}
          <div class="inline-msg" data-kind="info">
            <p>
              <strong>✓ cookies 已加密儲存</strong>
              ／ Windows Credential Manager
            </p>
            <p class="muted small">
              位置：<code>JavDBMagnet/JAVDB_COOKIES</code>（按 Win+R →
              <code>control /name Microsoft.CredentialManager</code> →
              「Windows 認證」可檢視）
            </p>
            <p class="muted small">
              cf_clearance 過期時：點下方「建立 cookies.txt 範本」→ 編輯範本貼入新 cookie →
              <strong>重啟 app</strong> 即會自動把新值加密寫回 Credential Manager 並刪除明文檔。
            </p>
          </div>
        {:else if cookiesStatus.storage === "file"}
          <div class="inline-msg" data-kind="info">
            <p>
              <strong>○ cookies.txt 已建立</strong>
              ／ 大小 {formatBytes(cookiesStatus.size_bytes)}
              {#if cookiesStatus.modified_iso}
                ／ 修改時間 {cookiesStatus.modified_iso.replace("T", " ").slice(0, 19)}
              {/if}
            </p>
            <p class="muted small">路徑：<code>{cookiesStatus.path}</code></p>
            <p class="muted small">
              ⚠ 目前是純文字儲存。<strong>重啟 app</strong> 後若檔案內含真實 cookie 行，
              會自動加密搬到 Credential Manager 並刪除此檔；只有空模板的話則維持不動。
            </p>
          </div>
        {:else}
          <div class="inline-msg" data-kind="error">
            <p><strong>✗ 尚未設定 cookies</strong>，JavDB 擷取會被 Cloudflare 擋下。</p>
            <p class="muted small">預期路徑：<code>{cookiesStatus.path}</code></p>
          </div>
        {/if}
      {/if}
      {#if cookiesError}
        <p class="inline-msg" data-kind="error">{cookiesError}</p>
      {/if}
      {#if cookiesMessage}
        <p class="inline-msg" data-kind={cookiesMessage.kind}>{cookiesMessage.text}</p>
      {/if}
      <div class="row">
        <button
          onclick={refreshCookiesStatus}
          class:flash-ok={flash.keys.has("cookies-refresh")}
        >
          {flash.keys.has("cookies-refresh") ? "已重整 ✓" : "重新整理 / 套用變更"}
        </button>
        <button onclick={openDataDir}>打開資料目錄</button>
        <button onclick={openLogsDir}>打開 logs 目錄</button>
        <button onclick={toggleCookiesPaste} disabled={cookiesSaving}>
          {cookiesPasteOpen ? "取消輸入" : "貼上新 cookies"}
        </button>
        {#if cookiesStatus && cookiesStatus.storage !== "file"}
          <button
            onclick={createCookiesTemplate}
            class:flash-ok={flash.keys.has("cookies-template")}
          >
            {flash.keys.has("cookies-template") ? "已建立 ✓" : "建立 cookies.txt 範本"}
          </button>
        {/if}
      </div>
      {#if cookiesPasteOpen}
        <div class="paste-cookies" style="margin-top: 0.75rem;">
          <p class="hint">
            把瀏覽器 DevTools → Network → Request Headers → 「<code>Cookie:</code>」
            那行整段內容（<strong>不包含「Cookie: 」前綴</strong>）貼到下方框內，
            按「儲存到認證管理員」即會：
          </p>
          <ul class="hint" style="margin: 0.25rem 0 0.5rem 1.25rem;">
            <li>立即加密寫入 Windows Credential Manager
              (<code>JavDBMagnet/JAVDB_COOKIES</code>)</li>
            <li>把新 cookies 推送到正在跑的 sidecar，<strong>不必重啟 app</strong></li>
            <li>順手清掉資料目錄裡任何過舊的 <code>cookies.txt</code></li>
          </ul>
          <textarea
            bind:value={cookiesPasteInput}
            rows="3"
            spellcheck="false"
            placeholder="_jdb_session=...; cf_clearance=...; locale=zh"
            style="width: 100%; font-family: monospace; font-size: 0.85rem;"
            disabled={cookiesSaving}
          ></textarea>
          <div class="row" style="margin-top: 0.5rem;">
            <button
              onclick={saveCookies}
              disabled={cookiesSaving || !cookiesPasteInput.trim()}
              class:flash-ok={flash.keys.has("cookies-save")}
            >
              {cookiesSaving
                ? "儲存中…"
                : flash.keys.has("cookies-save")
                  ? "已儲存 ✓"
                  : "儲存到認證管理員"}
            </button>
            <button onclick={toggleCookiesPaste} disabled={cookiesSaving}>
              取消
            </button>
          </div>
        </div>
      {/if}
    {/if}
  </section>

  <section>
    <h2>批次擷取</h2>
    <p class="hint">貼上 JavDB 網址，每行一個。以 <code>#</code> 開頭或非 http(s) 的行會被忽略。</p>

    <textarea
      class="url-batch"
      bind:value={urlBatch}
      rows="6"
      spellcheck="false"
      placeholder="https://javdb.com/v/...&#10;https://javdb.com/v/..."
    ></textarea>

    <div class="row">
      <button onclick={startScrape} disabled={isScraping}>
        {isScraping ? "擷取中…" : "開始擷取"}
      </button>
      <button onclick={cancelScrape} disabled={!isScraping}>取消</button>
      {#if groups.length > 0}
        <button
          onclick={copyVisible}
          disabled={isScraping || visibleMagnets === 0}
          class:flash-ok={flash.keys.has("magnet-copy-visible")}
        >
          {flash.keys.has("magnet-copy-visible")
            ? "已複製 ✓"
            : `複製可見磁力（${visibleMagnets}）`}
        </button>
        <button
          onclick={sendVisibleToRd}
          disabled={isScraping || isRdSending || visibleMagnets === 0 || !rdHasToken}
          title={rdHasToken ? "" : "請先設定 RD Token"}
        >
          送出目前可見 {visibleMagnets} 筆到 RD
        </button>
        <button
          onclick={clearResults}
          class:flash-ok={flash.keys.has("scrape-clear")}
        >
          {flash.keys.has("scrape-clear") ? "已清空 ✓" : "清空結果"}
        </button>
      {/if}
    </div>
    {#if groups.length > 0 && !rdHasToken}
      <p class="inline-msg" data-kind="info">
        ※「送出到 RD」目前停用 — 請先設定 RD Token（往上捲動到 <strong>Real-Debrid</strong> 區塊貼上 Token 並按「儲存」）。
      </p>
    {/if}

    <div class="status-bar" data-active={isScraping}>
      {#if scrapeProgress.total > 0}
        <span>{scrapeProgress.done} / {scrapeProgress.total}</span>
        <span class="ok">✓ {okCount}</span>
        <span class="err">✗ {errCount}</span>
        <span class="muted">磁力：{visibleMagnets} / {totalRawMagnets}</span>
      {:else}
        <span class="muted">閒置</span>
      {/if}
    </div>

    {#if groups.length > 0}
      <div class="filter-row">
        <label>
          關鍵字
          <input
            type="text"
            bind:value={filter.keyword}
            placeholder="番號 / 大小 / 標籤 / 日期"
          />
        </label>
        <label class="check">
          <input type="checkbox" bind:checked={filter.hd_only} />
          只顯示高清
        </label>
        <label>
          最小 GB
          <input
            type="number"
            min="0"
            step="0.1"
            bind:value={minSizeInput}
            onchange={commitMinSize}
          />
        </label>
        <label>
          最大 GB
          <input
            type="number"
            min="0"
            step="0.1"
            bind:value={maxSizeInput}
            onchange={commitMaxSize}
          />
        </label>
        <label>
          每組只留
          <select
            value={filter.group_pick}
            onchange={(e) => setGroupPick((e.currentTarget as HTMLSelectElement).value as GroupPick)}
          >
            <option value="all">全部</option>
            <option value="largest">最大檔</option>
            <option value="smallest">最小檔</option>
            <option value="fewest_files">檔案最少</option>
          </select>
        </label>
        <button onclick={resetFilter}>重置</button>
      </div>
    {/if}

    {#if groups.length === 0 && !isScraping}
      <p class="empty-state">尚無結果 — 在上方貼上網址後按下<strong>開始擷取</strong>。</p>
    {/if}
  </section>

  <section>
    <h2>直接貼磁力</h2>
    <p class="hint">
      已有 <code>magnet:?xt=...</code> 連結時可貼在這裡，系統會加入下方<strong>結果清單</strong>，
      之後可送至 Real-Debrid 或複製。
    </p>

    <textarea
      class="url-batch"
      bind:value={magnetBatch}
      rows="4"
      spellcheck="false"
      placeholder="magnet:?xt=urn:btih:...&#10;magnet:?xt=urn:btih:..."
    ></textarea>

    <div class="row">
      <button
        onclick={registerPastedMagnets}
        disabled={isRegistering}
        class:flash-ok={flash.keys.has("magnet-register")}
      >
        {isRegistering
          ? "加入中…"
          : flash.keys.has("magnet-register")
            ? "已加入 ✓"
            : "加入結果清單"}
      </button>
      <span class="muted small">
        加入後可用下方「結果」區塊內的篩選 / 送 RD / 複製。
      </span>
    </div>
    {#if registerStatus}
      <p
        class="inline-msg"
        data-kind={registerStatus.kind}
      >{registerStatus.text}</p>
    {/if}

    {#if groups.length > 0}
      <ul class="groups">
        {#each groups as g, i (g.url)}
          {@const rows = processedRows(g)}
          {@const isCollapsed = collapsed[g.url] === true}
          <li class="group" data-status={g.status}>
            <header>
              <button
                class="toggle"
                onclick={() => toggleCollapsed(g.url)}
                aria-label={isCollapsed ? "展開" : "收合"}
                disabled={!g.result}
              >
                {isCollapsed ? "▶" : "▼"}
              </button>
              <span class="status-dot"></span>
              <strong>
                {#if g.result}
                  {g.result.code || "（無番號）"}
                {:else}
                  #{i + 1}
                {/if}
              </strong>
              <span class="muted url">{g.url}</span>
              {#if g.result}
                <span class="muted">
                  — 顯示 {rows.length} / 共 {g.result.magnet_count} 個磁力
                </span>
              {/if}
            </header>

            {#if g.status === "fetching"}
              <p class="muted">擷取中…</p>
            {:else if g.status === "error"}
              <p class="error">錯誤：{g.error}</p>
            {:else if g.result && !isCollapsed}
              {#if g.result.title}
                <p class="title">{g.result.title}</p>
              {/if}
              {#if g.result.magnets.length === 0}
                <p class="muted">（此組沒有磁力）</p>
              {:else if rows.length === 0}
                <p class="muted">（沒有符合篩選條件的磁力）</p>
              {:else}
                <table>
                  <thead>
                    <tr>
                      <th>
                        <button class="th-sort" onclick={() => toggleSort("name")}>
                          番號{sortIndicator("name")}
                        </button>
                      </th>
                      <th>
                        <button class="th-sort" onclick={() => toggleSort("size")}>
                          大小{sortIndicator("size")}
                        </button>
                      </th>
                      <th>
                        <button class="th-sort" onclick={() => toggleSort("tags")}>
                          標籤{sortIndicator("tags")}
                        </button>
                      </th>
                      <th>
                        <button class="th-sort" onclick={() => toggleSort("date")}>
                          日期{sortIndicator("date")}
                        </button>
                      </th>
                      <th>遮蔽磁力</th>
                      <th>動作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {#each rows as m (m.handle_id)}
                      <tr
                        class="row-copyable"
                        title="雙擊複製磁力連結"
                        ondblclick={() =>
                          copyOne(m.handle_id, m.name || g.result!.code)}
                      >
                        <td>{m.name}</td>
                        <td>{m.size}</td>
                        <td>{m.tags.join(", ")}</td>
                        <td>{m.date}</td>
                        <td class="mono small">{m.magnet_redacted}</td>
                        <td>
                          <button
                            onclick={() => copyOne(m.handle_id, m.name || g.result!.code)}
                            class:flash-ok={flash.keys.has(`magnet-copy-${m.handle_id}`)}
                          >
                            {flash.keys.has(`magnet-copy-${m.handle_id}`)
                              ? "已複製 ✓"
                              : "複製"}
                          </button>
                        </td>
                      </tr>
                    {/each}
                  </tbody>
                </table>
              {/if}
            {/if}
          </li>
        {/each}
      </ul>
    {/if}
  </section>

  {#if rdSendProgress.length > 0}
    <section>
      <h2>送至 Real-Debrid 進度</h2>
      <div class="status-bar">
        <span>{rdSendDone.done} / {rdSendDone.total}</span>
        <span class="ok">✓ 完成 {rdCompletedCount}</span>
        <span class="muted">⏳ 待處理 {rdPendingCount}</span>
        <span class="err">✗ 錯誤 {rdErrorCount}</span>
        <span class="muted">下載連結：{rdDownloadLinkCount}</span>
      </div>
      <div class="row">
        {#if isRdSending}
          <button onclick={cancelRdSend}>取消</button>
        {/if}
        <button
          class:flash-ok={flash.keys.has("rd-bulk")}
          onclick={copyRdDownloads}
          disabled={isRdSending || rdDownloadLinkCount === 0}
        >
          {flash.keys.has("rd-bulk")
            ? "已複製 ✓"
            : `複製 ${rdDownloadLinkCount} 條下載連結`}
        </button>
        <span class="muted small">可貼到下載器，每行一個 URL</span>
      </div>

      <table>
        <thead>
          <tr>
            <th>番號</th>
            <th>狀態</th>
            <th>連結 / 訊息</th>
          </tr>
        </thead>
        <tbody>
          {#each rdSendProgress as row (row.handle_id)}
            <tr>
              <td>{row.code}</td>
              <td>
                {#if row.status === "pending"}
                  待送出
                {:else if row.status === "sending"}
                  送出中…
                {:else if row.status === "completed"}
                  <span class="status-ok">已完成</span>
                {:else if row.status === "in_pending"}
                  <span class="status-warn">RD 處理中</span>
                {:else if row.status === "error"}
                  <span class="status-err">失敗</span>
                {/if}
              </td>
              <td>
                {#if row.status === "completed"}
                  {@const rowLinks = collectDownloadLinksFromRow(row)}
                  {#if rowLinks.length > 1}
                    <div class="row-bulk-copy">
                      <button
                        class="small"
                        class:flash-ok={flash.keys.has(`rd-row-${row.handle_id}`)}
                        onclick={() => copyRdRow(row)}
                      >
                        {flash.keys.has(`rd-row-${row.handle_id}`)
                          ? "已複製 ✓"
                          : `複製此筆 ${rowLinks.length} 條`}
                      </button>
                    </div>
                  {/if}
                  <ul class="links">
                    {#each row.links as link, i}
                      <li class="link-item">
                        <div class="link-meta mono small">
                          {link.filename}
                          {#if link.filesize > 0}
                            <span class="muted">
                              （{(link.filesize / 1024 / 1024 / 1024).toFixed(2)} GB）
                            </span>
                          {/if}
                        </div>
                        {#if link.download}
                          <div class="link-row">
                            <input
                              type="text"
                              class="link-url mono small"
                              readonly
                              value={link.download}
                              onfocus={(e) => (e.currentTarget as HTMLInputElement).select()}
                              onclick={(e) => (e.currentTarget as HTMLInputElement).select()}
                            />
                            <button
                              class="small"
                              class:flash-ok={flash.keys.has(`rd-link-${row.handle_id}-${i}`)}
                              onclick={() => copyRdSingleLink(row.handle_id, link.download, i)}
                              aria-label={`複製 ${link.filename} 的下載連結`}
                            >
                              {flash.keys.has(`rd-link-${row.handle_id}-${i}`)
                                ? "已複製 ✓"
                                : "複製"}
                            </button>
                          </div>
                        {/if}
                      </li>
                    {/each}
                  </ul>
                {:else if row.status === "in_pending"}
                  <span class="muted small">已加入待處理清單，可稍後重試</span>
                {:else if row.status === "error"}
                  <span class="small">{rdErrorMessage(row.error_code ?? "")}</span>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </section>
  {/if}

  {#if pendingEntries.length > 0}
    <section>
      <h2>待處理（Real-Debrid）</h2>
      <p class="hint">
        這些 torrent RD 尚未完成下載。重試時不需要原始磁力（不存在 sidecar 之外）。
        「全部重試」會逐筆查 RD 最新狀態；「重讀本機紀錄」只重讀 pending_torrents.json，
        不查 RD。
      </p>

      {#if pendingMessage}
        <p class="inline-msg" data-kind={pendingMessage.kind} style="white-space: pre-line;">{pendingMessage.text}</p>
      {/if}

      <div class="row">
        <button
          onclick={retryAllPending}
          disabled={isRetryingPending || pendingEntries.length === 0}
        >
          {isRetryingPending ? "重試中…" : "全部重試（查 RD）"}
        </button>
        {#if isRetryingPending}
          <button onclick={cancelRetry}>取消</button>
        {/if}
        <button
          onclick={refreshPending}
          disabled={isRetryingPending}
          class:flash-ok={flash.keys.has("pending-refresh")}
        >
          {flash.keys.has("pending-refresh") ? "已重讀 ✓" : "重讀本機紀錄"}
        </button>
        <button
          onclick={clearAllPending}
          disabled={isRetryingPending}
          class:flash-ok={flash.keys.has("pending-clear")}
        >
          {flash.keys.has("pending-clear") ? "已清空 ✓" : "全部清空"}
        </button>
      </div>

      <table>
        <thead>
          <tr>
            <th>番號</th>
            <th>大小</th>
            <th>RD 狀態</th>
            <th>進度</th>
            <th>策略</th>
            <th>新增</th>
            <th>動作</th>
          </tr>
        </thead>
        <tbody>
          {#each pendingEntries as p (p.torrent_id)}
            <tr>
              <td>{p.code || "（無）"}</td>
              <td>{p.size_label}</td>
              <td>{p.last_rd_status || "—"}</td>
              <td>{p.last_progress.toFixed(0)}%</td>
              <td>{p.strategy}</td>
              <td class="small muted">{p.added_at.slice(0, 10)}</td>
              <td>
                <button onclick={() => removePending(p.torrent_id)}>移除</button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </section>
  {/if}
</main>

<style>
  .container {
    max-width: 1100px;
    margin: 0 auto;
    padding: 2rem;
  }

  h1 {
    margin: 0 0 0.25rem;
    font-size: 2rem;
  }

  h2 {
    margin: 1.5rem 0 0.5rem;
    font-size: 1.1rem;
    color: var(--color-muted);
  }

  .subtitle {
    color: var(--color-muted);
    margin: 0;
  }

  dl {
    display: grid;
    grid-template-columns: 8rem 1fr;
    gap: 0.5rem 1rem;
    margin: 0;
  }

  dt {
    font-weight: 600;
    color: var(--color-muted);
  }

  dd {
    margin: 0;
    word-break: break-all;
    font-family: ui-monospace, "Cascadia Mono", "Consolas", monospace;
    font-size: 0.9rem;
  }

  button {
    padding: 0.4rem 0.9rem;
    border-radius: 6px;
    border: 1px solid var(--color-border);
    background: var(--color-button-bg);
    color: var(--color-fg);
    cursor: pointer;
    font: inherit;
    transition: transform 70ms ease, box-shadow 70ms ease, background-color 120ms ease;
  }

  button:hover:not(:disabled) {
    background: var(--color-button-bg-hover);
  }

  button:active:not(:disabled) {
    transform: translateY(1px);
    box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.18);
  }

  button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  /* Brief post-copy confirmation: green tint + pulse. The button text
     itself is swapped to "已X ✓" from script for ~1.2s — see flash controller.
     Uses a translucent green so it reads correctly in both light + dark. */
  button.flash-ok {
    background: rgba(46, 204, 113, 0.22);
    border-color: #2ecc71;
    color: #2ecc71;
    font-weight: 600;
  }

  .status,
  .ping,
  .error,
  .hint {
    margin-top: 0.5rem;
    font-size: 0.9rem;
  }

  .status,
  .ping,
  .hint {
    color: var(--color-muted);
  }

  .error {
    color: #c0392b;
  }

  .row {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    margin-top: 0.5rem;
    flex-wrap: wrap;
  }

  .url-batch {
    width: 100%;
    box-sizing: border-box;
    padding: 0.5rem 0.75rem;
    border-radius: 6px;
    border: 1px solid var(--color-border);
    background: var(--color-button-bg);
    color: var(--color-fg);
    font-family: ui-monospace, "Cascadia Mono", "Consolas", monospace;
    font-size: 0.9rem;
    resize: vertical;
  }

  .filter-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem 1rem;
    align-items: end;
    padding: 0.6rem 0.75rem;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    margin-top: 0.5rem;
  }

  .filter-row label {
    display: flex;
    flex-direction: column;
    font-size: 0.75rem;
    color: var(--color-muted);
    gap: 0.2rem;
  }

  .filter-row label.check {
    flex-direction: row;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.9rem;
    color: var(--color-fg);
  }

  .filter-row input[type="text"],
  .filter-row input[type="number"],
  .filter-row select {
    padding: 0.3rem 0.5rem;
    border-radius: 4px;
    border: 1px solid var(--color-border);
    background: var(--color-button-bg);
    color: var(--color-fg);
    font: inherit;
    font-size: 0.9rem;
  }

  .filter-row input[type="number"] {
    width: 5.5rem;
  }

  .filter-row input[type="text"] {
    width: 14rem;
  }

  .toggle {
    padding: 0 0.4rem;
    border: none;
    background: transparent;
    color: var(--color-muted);
    cursor: pointer;
  }

  .toggle:disabled {
    opacity: 0.3;
    cursor: default;
  }

  .th-sort {
    padding: 0;
    border: none;
    background: transparent;
    color: inherit;
    cursor: pointer;
    font: inherit;
    font-weight: 600;
    text-align: left;
  }

  .th-sort:hover {
    color: var(--color-fg);
  }

  .row-copyable {
    cursor: copy;
  }

  .row-copyable:hover {
    background: var(--color-button-bg-hover);
  }

  .empty-state {
    margin-top: 1.5rem;
    padding: 1.5rem;
    border: 1px dashed var(--color-border);
    border-radius: 6px;
    text-align: center;
    color: var(--color-muted);
  }

  .inline-msg {
    margin: 0.5rem 0 0;
    padding: 0.5rem 0.75rem;
    border-radius: 6px;
    font-size: 0.9rem;
    line-height: 1.4;
    border: 1px solid var(--color-border);
    background: var(--color-button-bg);
  }

  .inline-msg[data-kind="error"] {
    border-color: #c0392b;
    color: #c0392b;
  }

  .inline-msg[data-kind="ok"] {
    border-color: #2ecc71;
    color: #1f8b4c;
  }

  .inline-msg[data-kind="info"] {
    color: var(--color-muted);
  }

  .grow {
    flex: 1;
  }

  .links {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .link-item {
    margin-bottom: 0.5rem;
  }

  .link-item:last-child {
    margin-bottom: 0;
  }

  .link-meta {
    margin-bottom: 0.15rem;
  }

  .link-row {
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }

  .link-url {
    flex: 1;
    min-width: 0;
    padding: 0.25rem 0.4rem;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    background: var(--color-button-bg);
    color: var(--color-fg);
  }

  .link-url:focus {
    outline: 1px solid #2ecc71;
    outline-offset: -1px;
  }

  .row-bulk-copy {
    margin-bottom: 0.4rem;
  }

  .status-ok {
    color: #2ecc71;
    font-weight: 600;
  }

  .status-warn {
    color: #f39c12;
    font-weight: 600;
  }

  .status-err {
    color: #c0392b;
    font-weight: 600;
  }

  a {
    color: var(--color-fg);
    text-decoration: underline;
  }

  .status-bar {
    display: flex;
    gap: 1rem;
    margin: 0.75rem 0;
    padding: 0.4rem 0.6rem;
    border-radius: 6px;
    background: var(--color-button-bg);
    font-size: 0.9rem;
    align-items: center;
  }

  .status-bar[data-active="true"] {
    border: 1px solid var(--color-border);
  }

  .status-bar .ok {
    color: #2ecc71;
  }

  .status-bar .err {
    color: #c0392b;
  }

  .muted {
    color: var(--color-muted);
  }

  .groups {
    list-style: none;
    padding: 0;
    margin: 1rem 0 0;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .group {
    border: 1px solid var(--color-border);
    border-radius: 6px;
    padding: 0.6rem 0.75rem;
  }

  .group header {
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .status-dot {
    width: 0.55rem;
    height: 0.55rem;
    border-radius: 50%;
    background: var(--color-muted);
    display: inline-block;
  }

  .group[data-status="fetching"] .status-dot {
    background: #f39c12;
  }

  .group[data-status="ok"] .status-dot {
    background: #2ecc71;
  }

  .group[data-status="error"] .status-dot {
    background: #c0392b;
  }

  .group .url {
    word-break: break-all;
  }

  .title {
    margin: 0.25rem 0 0.5rem;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 0.5rem;
  }

  th,
  td {
    padding: 0.35rem 0.5rem;
    border-bottom: 1px solid var(--color-border);
    text-align: left;
    vertical-align: top;
  }

  th {
    font-size: 0.85rem;
    color: var(--color-muted);
    font-weight: 600;
  }

  .mono {
    font-family: ui-monospace, "Cascadia Mono", "Consolas", monospace;
  }

  .small {
    font-size: 0.85rem;
  }

  code {
    font-family: ui-monospace, "Cascadia Mono", "Consolas", monospace;
    font-size: 0.85em;
  }
</style>
