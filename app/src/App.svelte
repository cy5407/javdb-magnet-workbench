<script lang="ts">
  import { onMount } from "svelte";
  import { invoke } from "@tauri-apps/api/core";
  import {
    parseMagnetBatch,
    parseUrlBatch,
    scrapeBatch,
    type ScrapeProgressEvent,
  } from "./lib/scraper";
  import { processGroupRows } from "./lib/magnetUtils";
  import {
    FILE_PICK_VALUES,
    SCALE_PRESETS,
    THEME_VALUES,
    validateSettingsDraft,
  } from "./lib/settingsValidation";
  import {
    rdErrorMessage,
    retryPending,
    sendBatch,
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
  let retryAbort: AbortController | null = null;

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
        registered: { handle_id: string; magnet_redacted: string; deduped: boolean }[];
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
          name: "",
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
    } catch (e) {
      statusMessage = `複製失敗：${e}`;
    }
  }

  async function copyVisible() {
    // Collect handle_ids from VISIBLE rows (after filter + group pick + sort).
    const ids: string[] = [];
    for (const g of groups) {
      for (const m of processedRows(g)) ids.push(m.handle_id);
    }
    if (ids.length === 0) return;
    try {
      const result = await invoke<CopyBulkResult>("copy_magnets_bulk", {
        handleIds: ids,
      });
      statusMessage =
        result.unknown > 0
          ? `已複製 ${result.copied} 個，另有 ${result.unknown} 個過期`
          : `已複製 ${result.copied} 個磁力連結`;
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
  }

  // ---- derived counts for status bar ---------------------------------
  let okCount = $derived(groups.filter((g) => g.status === "ok").length);
  let errCount = $derived(groups.filter((g) => g.status === "error").length);
  let totalRawMagnets = $derived(
    groups.reduce((acc, g) => acc + (g.result?.magnet_count ?? 0), 0),
  );
  let visibleMagnets = $derived(
    groups.reduce((acc, g) => acc + processedRows(g).length, 0),
  );

  // ---- M5: Real-Debrid handlers --------------------------------------
  async function rdTestToken() {
    rdMessage = "（測試中…）";
    try {
      const u = await invoke<RdUserInfo>("rd_test_token", {
        token: rdTokenInput.trim(),
      });
      rdUser = u;
      rdMessage = `測試成功：${u.username || "(無 username)"} / ${u.type} / 點數 ${u.points}`;
    } catch (e) {
      rdUser = null;
      const code = e instanceof Error ? e.message : String(e);
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
      // Refresh user info from saved token (no token sent over IPC).
      try {
        rdUser = await invoke<RdUserInfo>("rd_check_user");
      } catch (e) {
        const code = e instanceof Error ? e.message : String(e);
        rdMessage = `Token 已儲存，但驗證失敗：${rdErrorMessage(code)}`;
      }
    } catch (e) {
      const code = e instanceof Error ? e.message : String(e);
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
    } catch (e) {
      const code = e instanceof Error ? e.message : String(e);
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
    } catch (e) {
      const code = e instanceof Error ? e.message : String(e);
      rdMessage = `查詢失敗：${rdErrorMessage(code)}`;
    }
  }

  /** Build the send-to-RD batch from the currently visible (filtered+sorted+
   * group-picked) rows. */
  function buildVisibleSendItems(): RdSendItem[] {
    const out: RdSendItem[] = [];
    for (const g of groups) {
      const rows = processedRows(g);
      const code = g.result?.code ?? "";
      for (const m of rows) {
        out.push({
          handle_id: m.handle_id,
          code: code || m.name || "(unknown)",
          size_label: m.size,
        });
      }
    }
    return out;
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

  async function copyRdDownloads() {
    const lines: string[] = [];
    for (const row of rdSendProgress) {
      if (row.status === "completed") {
        for (const link of row.links) {
          if (link.download) lines.push(link.download);
        }
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
    } catch (e) {
      rdMessage = `複製失敗：${e}`;
    }
  }

  async function refreshPending() {
    try {
      pendingEntries = await invoke<PendingEntry[]>("pending_list");
    } catch (e) {
      rdMessage = `讀取待處理清單失敗：${e}`;
    }
  }

  async function retryAllPending() {
    if (isRetryingPending) return;
    if (pendingEntries.length === 0) return;
    isRetryingPending = true;
    retryAbort = new AbortController();
    const completedLinks: string[] = [];
    rdMessage = "";

    try {
      await retryPending(
        pendingEntries,
        (ev: RdRetryEvent) => {
          if (ev.result.kind === "completed") {
            for (const l of ev.result.links) {
              if (l.download) completedLinks.push(l.download);
            }
          }
        },
        { signal: retryAbort.signal },
      );
    } finally {
      isRetryingPending = false;
      retryAbort = null;
      await refreshPending();
    }

    if (completedLinks.length > 0) {
      try {
        const result = await invoke<CopyRdLinksBulkResult>(
          "copy_rd_links_bulk",
          { links: completedLinks },
        );
        rdMessage = `重試完成：已複製 ${result.copied} 條 RD 下載連結`;
      } catch (e) {
        rdMessage = `重試完成 ${completedLinks.length} 條（剪貼簿寫入失敗：${e}）`;
      }
    } else {
      rdMessage = `重試完成，目前沒有新完成的連結（剩 ${pendingEntries.length} 個）`;
    }
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
      cookiesStatus = await invoke<CookiesStatus>("get_cookies_status");
    } catch (e) {
      cookiesError = `讀取 cookies 狀態失敗：${e}`;
      cookiesStatus = null;
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
    try {
      await invoke("create_cookies_template");
      await refreshCookiesStatus();
      cookiesMessage = {
        kind: "ok",
        text: "已建立 cookies.txt 範本，請按「打開資料目錄」編輯並填入 cookie。",
      };
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

  function openSettingsEditor() {
    if (!settings) {
      settingsMessage = "設定尚未載入";
      settingsMessageKind = "error";
      return;
    }
    // Deep-ish clone so editing the draft doesn't mutate the loaded
    // copy until save.
    settingsDraft = {
      version: settings.version,
      ui: { ...settings.ui },
      rd: { ...settings.rd, api_token: "" },
    };
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
      settingsDraft = {
        version: settings.version,
        ui: { ...settings.ui },
        rd: { ...settings.rd, api_token: "" },
      };
      settingsMessage = "設定已儲存";
      settingsMessageKind = "ok";
    } catch (e) {
      settingsMessage = `儲存失敗：${e}`;
      settingsMessageKind = "error";
    } finally {
      settingsSaving = false;
    }
  }

  function revertSettingsDraft() {
    if (!settings) return;
    settingsDraft = {
      version: settings.version,
      ui: { ...settings.ui },
      rd: { ...settings.rd, api_token: "" },
    };
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
    } catch (e) {
      rdMessage = `移除失敗：${e}`;
    }
  }

  async function clearAllPending() {
    try {
      await invoke("pending_clear");
      pendingEntries = [];
      rdMessage = "待處理清單已清空";
    } catch (e) {
      rdMessage = `清空失敗：${e}`;
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
      <button onclick={pingSidecar}>Ping Sidecar</button>
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
        <button onclick={rdRefreshUser}>查詢帳號</button>
        <button onclick={rdClearToken}>清除 Token</button>
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
        <a
          href="https://real-debrid.com/apitoken"
          target="_blank"
          rel="noreferrer">real-debrid.com/apitoken</a>）
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
        <button onclick={rdTestToken} disabled={!rdTokenInput.trim()}>
          測試連線
        </button>
        <button onclick={rdSaveToken} disabled={!rdTokenInput.trim()}>
          儲存
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
        <button onclick={previewLegacyImport} disabled={legacyBusy || !legacyPath.trim()}>
          {legacyBusy ? "處理中…" : "預覽"}
        </button>
        <button
          onclick={applyLegacyImportConfirmed}
          disabled={legacyBusy || !legacyPreview || !legacyPreview.source_dir_valid}
        >
          匯入
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
        <button onclick={saveSettings} disabled={!settingsValid || settingsSaving}>
          {settingsSaving ? "儲存中…" : "儲存設定"}
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
        JavDB 抓取需要登入後的 cookies.txt。此區只顯示路徑 / 大小 / 修改時間，
        <strong>絕不讀取 cookies 內容</strong>。
      </p>
      {#if cookiesStatus}
        <div class="inline-msg" data-kind={cookiesStatus.present ? "info" : "error"}>
          {#if cookiesStatus.present}
            <p>
              <strong>✓ 已找到 cookies.txt</strong>
              ／ 大小 {formatBytes(cookiesStatus.size_bytes)}
              {#if cookiesStatus.modified_iso}
                ／ 修改時間 {cookiesStatus.modified_iso.replace("T", " ").slice(0, 19)}
              {/if}
            </p>
          {:else}
            <p><strong>✗ 尚未設定 cookies.txt</strong>，JavDB 擷取會被 Cloudflare 擋下。</p>
          {/if}
          <p class="muted small">路徑：<code>{cookiesStatus.path}</code></p>
          <p class="muted small">
            ⚠ cookies 以純文字儲存，請勿分享 <code>%APPDATA%\JavDBMagnet</code> 或將該目錄同步到雲端。
          </p>
        </div>
      {/if}
      {#if cookiesError}
        <p class="inline-msg" data-kind="error">{cookiesError}</p>
      {/if}
      {#if cookiesMessage}
        <p class="inline-msg" data-kind={cookiesMessage.kind}>{cookiesMessage.text}</p>
      {/if}
      <div class="row">
        <button onclick={refreshCookiesStatus}>重新整理</button>
        <button onclick={openDataDir}>打開資料目錄</button>
        <button onclick={openLogsDir}>打開 logs 目錄</button>
        {#if cookiesStatus && !cookiesStatus.present}
          <button onclick={createCookiesTemplate}>建立 cookies.txt 範本</button>
        {/if}
      </div>
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
        <button onclick={copyVisible} disabled={isScraping || visibleMagnets === 0}>
          複製可見磁力（{visibleMagnets}）
        </button>
        <button
          onclick={sendVisibleToRd}
          disabled={isScraping || isRdSending || visibleMagnets === 0 || !rdHasToken}
          title={rdHasToken ? "" : "請先設定 RD Token"}
        >
          送出目前可見 {visibleMagnets} 筆到 RD
        </button>
        <button onclick={clearResults}>清空結果</button>
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
      <button onclick={registerPastedMagnets} disabled={isRegistering}>
        {isRegistering ? "加入中…" : "加入結果清單"}
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
                          >
                            複製
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
        <span class="muted">直連：{rdDownloadLinkCount}</span>
      </div>
      <div class="row">
        {#if isRdSending}
          <button onclick={cancelRdSend}>取消</button>
        {/if}
        <button
          onclick={copyRdDownloads}
          disabled={isRdSending || rdDownloadLinkCount === 0}
        >
          複製 {rdDownloadLinkCount} 條下載直連
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
                  <ul class="links">
                    {#each row.links as link}
                      <li class="mono small">
                        {link.filename}
                        {#if link.filesize > 0}
                          <span class="muted">
                            （{(link.filesize / 1024 / 1024 / 1024).toFixed(2)} GB）
                          </span>
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
      </p>

      <div class="row">
        <button
          onclick={retryAllPending}
          disabled={isRetryingPending || pendingEntries.length === 0}
        >
          {isRetryingPending ? "重試中…" : "全部重試"}
        </button>
        {#if isRetryingPending}
          <button onclick={cancelRetry}>取消</button>
        {/if}
        <button onclick={refreshPending} disabled={isRetryingPending}>
          重新載入
        </button>
        <button onclick={clearAllPending} disabled={isRetryingPending}>
          全部清空
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
  }

  button:hover:not(:disabled) {
    background: var(--color-button-bg-hover);
  }

  button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
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
