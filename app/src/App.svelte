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
    rdErrorMessage,
    retryPending,
    sendBatch,
    type RdRetryEvent,
    type RdSendBatchEvent,
    type RdSendItem,
  } from "./lib/rdSender";
  import {
    defaultFilterState,
    type CopyBulkResult,
    type FilterState,
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
    registerStatus = { kind: "info", text: "註冊中…" };
    try {
      const resp = await invoke<{
        registered: { handle_id: string; magnet_redacted: string; deduped: boolean }[];
        invalid: string[];
      }>("register_magnets", { magnets });

      const rows: MagnetRow[] = resp.registered.map((r) => ({
        handle_id: r.handle_id,
        name: "",
        size: "",
        tags: [],
        date: "",
        magnet_redacted: r.magnet_redacted,
      }));

      // Synthetic group: unique URL key uses a timestamp so multiple paste
      // batches don't collide. UI shows "(直接貼上)" instead of a JavDB URL.
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
            code: `(直接貼上 ${rows.length})`,
            title: "",
            magnet_count: rows.length,
            magnets: rows,
          },
        },
      ];
      magnetBatch = "";
      const skipped = resp.invalid.length;
      registerStatus = {
        kind: "ok",
        text:
          skipped > 0
            ? `已註冊 ${rows.length} 個磁力（忽略 ${skipped} 個無效輸入）。捲動到下方「結果」即可使用送 RD / 複製。`
            : `已註冊 ${rows.length} 個磁力。捲動到下方「結果」即可使用送 RD / 複製。`,
      };
    } catch (e) {
      registerStatus = { kind: "error", text: `註冊失敗：${e}` };
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
      const { writeText } = await import("@tauri-apps/plugin-clipboard-manager");
      await writeText(lines.join("\n"));
      rdMessage = `已複製 ${lines.length} 個 RD 直連到剪貼簿`;
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
        const { writeText } = await import("@tauri-apps/plugin-clipboard-manager");
        await writeText(completedLinks.join("\n"));
        rdMessage = `重試完成：${completedLinks.length} 個新連結已複製到剪貼簿`;
      } catch (e) {
        rdMessage = `重試完成 ${completedLinks.length} 個（剪貼簿寫入失敗）`;
      }
    } else {
      rdMessage = `重試完成，目前沒有新完成的連結（剩 ${pendingEntries.length} 個）`;
    }
  }

  function cancelRetry() {
    retryAbort?.abort();
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
        Token：{rdHasToken ? "✓ 已設定" : "✗ 未設定"}
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
        新增 / 更新 Token（取得：
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
          placeholder="貼上 Token"
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
          title={rdHasToken ? "" : "請先設定 Real-Debrid Token"}
        >
          送至 Real-Debrid（{visibleMagnets}）
        </button>
        <button onclick={clearResults}>清空結果</button>
      {/if}
    </div>
    {#if groups.length > 0 && !rdHasToken}
      <p class="inline-msg" data-kind="info">
        ※「送至 Real-Debrid」目前停用：請往上捲動到
        <strong>Real-Debrid</strong> 區塊貼上 Token 並按「儲存」。
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
    <h2>直接貼上磁力連結</h2>
    <p class="hint">
      不想經 JavDB 擷取，直接貼 <code>magnet:?xt=...</code> 也可以送至 Real-Debrid。
      註冊後會以「直接貼上」群組顯示，套用相同的篩選 / 排序 / 送 RD 流程。
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
        {isRegistering ? "註冊中…" : "註冊磁力"}
      </button>
      <span class="muted small">
        註冊後可在下方搭配「送至 Real-Debrid」按鈕送出。
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
          複製所有 RD 直連（{rdDownloadLinkCount}）
        </button>
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
