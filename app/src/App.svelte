<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import { createFlashController } from "./lib/flashAction";
  import { invoke } from "@tauri-apps/api/core";
  import { open as openExternal } from "@tauri-apps/plugin-shell";
  import {
    applyScrapeProgressForRun,
    parseMagnetBatch,
    parseUrlBatch,
    scrapeBatch,
    type ScrapeProgressEvent,
  } from "./lib/scraper";
  import { errText } from "./lib/errText";
  import {
    dedupeByHandleId,
    isManualGroup,
    pickRdReadyRow,
    processGroupRows,
  } from "./lib/magnetUtils";
  import {
    classifyRow,
    rdBadge,
    summarizeRdLikelihood,
    type RdCandidate,
    type RdPickTier,
    type RdRowClass,
  } from "./lib/rdPriority";
  import {
    FILE_PICK_VALUES,
    SCALE_PRESETS,
    THEME_VALUES,
    validateSettingsDraft,
  } from "./lib/settingsValidation";
  import {
    applyRetryEventToProgressRows,
    buildRdDisplayRows,
    collectDownloadLinksFromRow,
    formatCompletedAt,
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
  let activeTab = $state<"search" | "select" | "rd" | "settings">("search");
  const TAB_ORDER = ["search", "select", "rd", "settings"] as const;

  /** Left/Right steps between the tab buttons the way a tablist would. The
   * handler sits on the buttons rather than on <nav> because a keydown on a
   * non-interactive landmark trips Svelte's a11y lint. */
  function onTabKeydown(e: KeyboardEvent, index: number) {
    let next: number;
    if (e.key === "ArrowRight") next = (index + 1) % TAB_ORDER.length;
    else if (e.key === "ArrowLeft") next = (index - 1 + TAB_ORDER.length) % TAB_ORDER.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = TAB_ORDER.length - 1;
    else return;
    e.preventDefault();
    activeTab = TAB_ORDER[next];
    const buttons = (e.currentTarget as HTMLElement).parentElement
      ?.querySelectorAll<HTMLButtonElement>("button");
    buttons?.[next]?.focus();
  }

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
  let scrapeRunId = 0;

  // M4b — filter / sort / collapse state
  let filter = $state<FilterState>(defaultFilterState());
  // Bound separately because the inputs return strings; we coerce on commit.
  let minSizeInput = $state("");
  let maxSizeInput = $state("");
  let sortColumn = $state<SortColumn | null>(null);
  let sortDirection = $state<SortDirection>("asc");
  /** Per-group collapsed flag keyed by URL. Default = expanded. */
  let collapsed = $state<Record<string, boolean>>({});
  let selectedHandles = $state<Record<string, boolean>>({});

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
  let isCancelingSend = $state(false);
  let rdSendAbort: AbortController | null = null;
  /**
   * True ONLY while the pre-send summary panel is up. Deliberately a bare
   * flag rather than a frozen snapshot of the batch: the checkboxes stay live
   * behind the panel (回到挑選 is not disabled), and a snapshot would let the
   * user confirm a batch that no longer matches what is checked — breaking
   * the app's oldest rule, that the send follows the checkboxes. Everything
   * the panel displays and sends comes from `rdSendTriage`, which is derived
   * from the current selection.
   */
  let sendPlanOpen = $state(false);
  let pendingEntries = $state<PendingEntry[]>([]);
  let isRetryingPending = $state(false);
  let isThemeSaving = $state(false);
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
  // 清除 arms on the first click and only
  // invokes on the second. Unlike 清除 Token (re-pasteable from Real-Debrid's
  // site) the cookie header can only be recovered by walking DevTools again,
  // so a stray click must not be enough.
  let cookiesClearArmed = $state(false);
  let cookiesClearing = $state(false);

  // M7c: Settings editor
  let settingsShown = $state(false);
  let settingsDraft = $state<Settings | null>(null);
  let settingsSaving = $state(false);
  let settingsMessage = $state("");
  let settingsMessageKind = $state<"ok" | "error" | "info">("info");

  // Any settings.json writer excludes the others — write_settings is a
  // whole-file overwrite with no merge, so interleaved writes silently
  // revert whichever fields the loser had changed.
  let settingsWriteBusy = $derived(isThemeSaving || settingsSaving || legacyBusy);

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

  async function loadAndApplySettings(): Promise<Settings> {
    const s = await invoke<Settings>("read_settings");
    settings = s;
    theme = s.ui.theme as Theme;
    applyTheme(theme);
    applyScale(s.ui.scale);
    return s;
  }

  async function reloadPendingSilently(context = "pending_list") {
    try {
      pendingEntries = await invoke<PendingEntry[]>("pending_list");
    } catch (e) {
      console.warn(`${context} failed:`, e);
    }
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
      await loadAndApplySettings();
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
    await reloadPendingSilently();

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
    if (settingsWriteBusy) return;
    if (settings === null) {
      statusMessage = "設定尚未載入";
      return;
    }
    const oldTheme = theme;
    const oldSettingsTheme = settings.ui.theme;
    const oldDraftTheme = settingsDraft ? settingsDraft.ui.theme : undefined;
    const newTheme = theme === "light" ? "dark" : "light";
    const settingsRef = settings;

    isThemeSaving = true;
    theme = newTheme;
    applyTheme(newTheme);
    settings.ui.theme = newTheme;

    try {
      await invoke("write_settings", { settings });
      if (settingsDraft) {
        settingsDraft.ui.theme = newTheme;
      }
      statusMessage = `主題已儲存：${newTheme}`;
    } catch (e) {
      theme = oldTheme;
      if (settings === settingsRef) {
        settings.ui.theme = oldSettingsTheme;
      }
      if (settingsDraft && oldDraftTheme !== undefined) {
        settingsDraft.ui.theme = oldDraftTheme;
      }
      applyTheme(oldTheme);
      console.error("write_settings failed:", e);
      statusMessage = `儲存設定失敗：${e}`;
    } finally {
      isThemeSaving = false;
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

    // Web groups are about to be replaced — release their handles so the
    // sidecar's handle table doesn't grow across repeated scrapes. Manual
    // groups survive, so their handles must NOT be forgotten.
    //
    // "Their handles" has to be read per-HANDLE, not per-group: the sidecar
    // keys the table by BTIH, so a pasted magnet whose BTIH matches a scraped
    // one gets the SAME handle_id (that shared state is deliberate — it is
    // what the ＝網頁同筆 badge reports). Filtering only by "is this group
    // manual?" therefore releases a handle a surviving manual row is still
    // showing, and forget_magnets has no refcount to save us: the pasted row
    // stays on screen, stays checked, and fails with unknown_handle at send
    // time. The full magnet lives only in the sidecar, so the user cannot
    // recover it from the UI.
    const survivingManualIds = new Set(
      groups
        .filter(isManualGroup)
        .flatMap((g) => g.result?.magnets.map((m) => m.handle_id) ?? []),
    );
    const staleIds: string[] = [];
    for (const g of groups) {
      if (!isManualGroup(g) && g.result) {
        for (const m of g.result.magnets) {
          if (!survivingManualIds.has(m.handle_id)) staleIds.push(m.handle_id);
        }
      }
    }

    // Initialize the result slots so the UI can render placeholders before
    // any fetch completes. Manual (pasted) groups survive the scrape and
    // ride at the array TAIL — applyScrapeProgressForRun writes results by
    // index (groups[ev.index - 1]), so the URL slots MUST occupy the head.
    groups = [
      ...urls.map((url) => ({
        url,
        status: "pending" as const,
        result: null,
        error: null,
        finished_at: null,
      })),
      ...groups.filter(isManualGroup),
    ];
    // The web rows the panel was triaging are gone (and their handles are
    // about to be forgotten), so a panel left open would be describing a
    // batch that no longer exists.
    sendPlanOpen = false;
    if (staleIds.length > 0) {
      try {
        await invoke("forget_magnets", { handleIds: staleIds });
      } catch (e) {
        // Best-effort: a failed release only costs sidecar memory, and the
        // handles are already unreachable from the UI.
        console.warn("forget_magnets (stale scrape handles) failed:", e);
      }
    }
    scrapeProgress = { done: 0, total: urls.length };
    isScraping = true;
    const runId = ++scrapeRunId;
    const controller = new AbortController();
    scrapeAbort = controller;

    try {
      await scrapeBatch(
        urls,
        (ev: ScrapeProgressEvent) => {
          const current = { groups, scrapeProgress };
          const next = applyScrapeProgressForRun(
            current,
            ev,
            scrapeRunId,
            runId,
          );
          if (next !== current) {
            groups = next.groups;
            scrapeProgress = next.scrapeProgress;
            for (const g of groups) {
              if (g.result) rememberSelectableRows(g.result.magnets);
            }
          }
        },
        { signal: controller.signal },
      );
    } finally {
      if (scrapeRunId === runId) {
        isScraping = false;
        scrapeAbort = null;
      }
    }
  }

  function cancelScrape() {
    scrapeAbort?.abort();
    scrapeRunId += 1;
    isScraping = false;
    scrapeAbort = null;
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
          ? "你貼的看起來是 JavDB 網址（http/https）。請改貼到「1. 擷取 Magnet」分頁的批次擷取欄位；本欄只接受 magnet:?xt=... 開頭的磁力連結。"
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

      // Skip only handles already pasted into a manual group (or repeated
      // within this batch) so the same magnet isn't rendered as two manual
      // rows. A handle that also lives in a WEB group is NOT skipped: the
      // pasted magnet is an explicit instruction and must stay visible even
      // when filters hide or replace its web twin. dedupeByHandleId() on
      // the send/copy paths still guarantees RD is invoked once per handle.
      const manualHandleIds = new Set<string>();
      for (const g of groups) {
        if (!isManualGroup(g) || !g.result) continue;
        for (const m of g.result.magnets) manualHandleIds.add(m.handle_id);
      }

      const newRows: MagnetRow[] = [];
      let skippedExisting = 0;
      for (const r of resp.registered) {
        // Pasting a magnet is an explicit re-selection, even if this BTIH
        // was previously scraped and then unchecked, or already exists in a
        // manual group. The rendered row may be skipped, but the send intent
        // must be restored.
        selectedHandles[r.handle_id] = true;
        if (manualHandleIds.has(r.handle_id)) {
          skippedExisting += 1;
          continue;
        }
        manualHandleIds.add(r.handle_id);
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
        rememberSelectableRows(newRows);
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
        fragments.push(`已跳過 ${skippedExisting} 筆重複的手貼磁力`);
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

  async function copySelected() {
    const selected = dedupeByHandleId(allSelectableRows).filter((m) =>
      selectedHandles[m.handle_id],
    );
    const ids = selected.map((m) => m.handle_id);
    if (ids.length === 0) return;
    try {
      const result = await invoke<CopyBulkResult>("copy_magnets_bulk", {
        handleIds: ids,
      });
      statusMessage =
        result.unknown > 0
          ? `已複製 ${result.copied} 個，另有 ${result.unknown} 個過期`
          : `已複製 ${result.copied} 個磁力連結`;
      flash.flash("magnet-copy-selected");
    } catch (e) {
      statusMessage = `批次複製失敗：${e}`;
    }
  }

  // ---- M4b: filter / sort / group helpers ----------------------------
  let groupProcessedRowsMap = $derived.by(() => {
    const map = new Map<string, MagnetRow[]>();
    for (const g of groups) {
      map.set(g.url, processGroupRows(g, filter, sortColumn, sortDirection));
    }
    return map;
  });

  function processedRows(g: ScrapedGroup): MagnetRow[] {
    return groupProcessedRowsMap.get(g.url) ?? processGroupRows(g, filter, sortColumn, sortDirection);
  }

  /**
   * The rows a group's RD candidate is picked from — literally the rendered
   * set, so the ★ can never land on a row the current view is hiding and
   * 只勾選 RD 優先候選 can never check one either. Reusing processedRows is
   * what makes that true by construction; reproducing only its filterRows
   * half silently diverges the moment group_pick is largest / smallest /
   * fewest_files, which collapse the group to one row.
   *
   * Feeding the result back in under group_pick="rd_ready" is a fixed point,
   * not a problem: pickRdCandidate over the single surviving row returns that
   * same row with the same tier.
   */
  function rdConsideredRows(g: ScrapedGroup): MagnetRow[] {
    return processedRows(g);
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

  function rememberSelectableRows(rows: MagnetRow[]) {
    for (const m of rows) {
      if (!(m.handle_id in selectedHandles)) {
        selectedHandles[m.handle_id] = true;
      }
    }
  }

  function setRowSelected(handleId: string, selected: boolean) {
    selectedHandles[handleId] = selected;
  }

  function setRowsSelected(rows: MagnetRow[], selected: boolean) {
    for (const m of rows) {
      selectedHandles[m.handle_id] = selected;
    }
  }

  function selectOnlyRows(rows: MagnetRow[]) {
    setRowsSelected(allSelectableRows, false);
    setRowsSelected(rows, true);
  }

  /**
   * Collapse the scraped results down to one row per group — the one most
   * likely to be cached on RD already.
   *
   * Scoped to WEB groups on both halves. Unchecking runs over web rows only
   * (not allSelectableRows, which is what selectOnlyRows clears): a pasted
   * magnet is an explicit instruction, so this must not silently drop it —
   * see registerPastedMagnets. Checking skips any group whose best row is
   * only a no_hd_fallback, because auto-checking a row we know is neither HD
   * nor from a re-upload site would be a guess the user did not ask for.
   */
  function selectRdCandidatesOnly() {
    // Selection is keyed by handle_id, and the SAME handle can be rendered by
    // a web group and a manual group at once (sidecar keys handles by BTIH,
    // and registerPastedMagnets keeps the pasted twin visible on purpose).
    // Unchecking "every web row" would therefore reach through the shared key
    // and silently drop the pasted instruction — so twins are excluded here,
    // which is also what makes the「手貼 N 筆維持原狀」message true.
    const manualHandleIds = new Set(
      groups
        .filter(isManualGroup)
        .flatMap((g) => g.result?.magnets.map((m) => m.handle_id) ?? []),
    );
    setRowsSelected(
      webGroups
        .flatMap((g) => g.result?.magnets ?? [])
        .filter((m) => !manualHandleIds.has(m.handle_id)),
      false,
    );
    for (const handleId of rdPickedHandles) setRowSelected(handleId, true);

    const skipped = rdCandidates.filter(
      (c) => !isManualGroup(c.group) && c.candidate.tier === "no_hd_fallback",
    ).length;
    const manualCount = dedupeByHandleId(
      groups.filter(isManualGroup).flatMap((g) => g.result?.magnets ?? []),
    ).length;
    const fragments = [`已勾選 ${rdPickedHandles.size} 筆 RD 優先候選`];
    if (skipped > 0) fragments.push(`${skipped} 組因無高清候選被跳過`);
    if (manualCount > 0) fragments.push(`手貼 ${manualCount} 筆維持原狀`);
    statusMessage = fragments.join("；") + "。";
  }

  function selectedInRows(rows: MagnetRow[]): number {
    return dedupeByHandleId(rows).filter((m) => selectedHandles[m.handle_id]).length;
  }

  function rowSelected(handleId: string): boolean {
    return selectedHandles[handleId] === true;
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

  // Clears web AND manual groups alike. This is intentionally the ONLY
  // path that removes manual (pasted) groups — startScrape preserves them.
  async function clearResults() {
    if (isRdSending || isRetryingPending) return;
    if (isScraping) {
      scrapeAbort?.abort();
    }
    scrapeRunId += 1;
    isScraping = false;
    scrapeAbort = null;
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
    selectedHandles = {};
    // Nothing is checked any more, so the summary panel would be reporting on
    // an empty batch.
    sendPlanOpen = false;
    if (ids.length > 0) {
      try {
        const forgotten = await invoke<number>("forget_magnets", {
          handleIds: ids,
        });
        statusMessage = `已清空 ${forgotten} 筆磁力 handle`;
      } catch (e) {
        // Don't surface as an error — the UI is already cleared and the handles
        // are unreachable from it. The sidecar has no GC, so a failed release
        // just leaves them resident until the process exits.
        console.warn("forget_magnets failed:", e);
        statusMessage = "結果已清空";
      }
    } else {
      statusMessage = "結果已清空";
    }
    flash.flash("scrape-clear");
  }

  // ---- derived counts for status bar ---------------------------------
  // Scrape status counters cover WEB groups only: manual (pasted) groups
  // are not part of a batch-scrape run and would inflate ✓/磁力 counts
  // (e.g. "✓ 3" after scraping 2 URLs).
  let webGroups = $derived(groups.filter((g) => !isManualGroup(g)));
  let okCount = $derived(webGroups.filter((g) => g.status === "ok").length);
  let errCount = $derived(webGroups.filter((g) => g.status === "error").length);
  let totalRawMagnets = $derived(
    webGroups.reduce((acc, g) => acc + (g.result?.magnet_count ?? 0), 0),
  );
  // Visible rows per source, BEFORE handle dedupe. Rendered row count and
  // unique handle count differ when the same BTIH is visible in both a
  // web group and a manual group — the send-button breakdown surfaces
  // that gap as「重複 N 已合併」.
  let webVisibleRows = $derived(webGroups.flatMap((g) => processedRows(g)));
  let manualVisibleRows = $derived(
    groups.filter(isManualGroup).flatMap((g) => processedRows(g)),
  );
  let allVisibleRows = $derived([...webVisibleRows, ...manualVisibleRows]);
  // Web-only unique handles for the scrape status bar, so「磁力：X / Y」
  // keeps numerator and denominator in the same (web) universe — totalRawMagnets
  // deliberately excludes manual rows.
  let webVisibleMagnets = $derived(dedupeByHandleId(webVisibleRows).length);
  let allSelectableRows = $derived(
    groups.flatMap((g) => g.result?.magnets ?? []),
  );
  let webHandleIds = $derived(
    new Set(webGroups.flatMap((g) => g.result?.magnets.map((m) => m.handle_id) ?? [])),
  );
  let selectableMagnets = $derived(dedupeByHandleId(allSelectableRows).length);
  let selectedMagnets = $derived(
    dedupeByHandleId(allSelectableRows).filter((m) => selectedHandles[m.handle_id]).length,
  );
  let sendButtonLabel = $derived.by(() => {
    if (manualVisibleRows.length === 0) {
      return `送出已勾選 ${selectedMagnets} 筆到 RD`;
    }
    const selectedWeb = dedupeByHandleId(webGroups.flatMap((g) => g.result?.magnets ?? []))
      .filter((m) => selectedHandles[m.handle_id]).length;
    const selectedManual = dedupeByHandleId(groups.filter(isManualGroup).flatMap((g) => g.result?.magnets ?? []))
      .filter((m) => selectedHandles[m.handle_id]).length;
    const dup = selectedWeb + selectedManual - selectedMagnets;
    const dupPart = dup > 0 ? `，重複 ${dup} 已合併` : "";
    return `送出已勾選 ${selectedMagnets} 筆到 RD（網頁 ${selectedWeb}＋手貼 ${selectedManual}${dupPart}）`;
  });

  // ---- derived RD hit-likelihood (local heuristic, see rdPriority.ts) --
  // Every number below is a guess from the row's own metadata: RD removed
  // /torrents/instantAvailability in 2024, so there is nothing to query.
  let rdCandidates = $derived.by(() => {
    const out: { group: ScrapedGroup; candidate: RdCandidate }[] = [];
    for (const g of groups) {
      const candidate = pickRdReadyRow(rdConsideredRows(g));
      if (candidate) out.push({ group: g, candidate });
    }
    return out;
  });
  // Keyed by GROUP url rather than flattened into a Set of handle ids: the
  // same BTIH can be rendered by a web group AND a manual group at once
  // (registerPastedMagnets does not de-duplicate across them), and a flat set
  // would star the web twin of a row that only won inside its own one-row
  // manual group.
  let rdPickByGroup = $derived(
    new Map(rdCandidates.map((c) => [c.group.url, c.candidate] as const)),
  );
  // The handles 只勾選 RD 優先候選 will check — web groups only, and only
  // where the pick is backed by an actual HD row (see selectRdCandidatesOnly).
  let rdPickedHandles = $derived(
    new Set(
      rdCandidates
        .filter((c) => !isManualGroup(c.group) && c.candidate.tier !== "no_hd_fallback")
        .map((c) => c.candidate.row.handle_id),
    ),
  );
  // Class per handle over ALL rows, not just the visible ones: the send batch
  // follows the checkboxes, which filters do not touch. FIRST occurrence wins
  // and group order is web-first — the same rule buildSelectedSendItems uses
  // for code/size_label, and for the same reason: a manual row carries no
  // size/tags/date, so it would otherwise overwrite its web twin's real class
  // with `unknown`.
  let rowClassByHandle = $derived.by(() => {
    const map = new Map<string, RdRowClass>();
    for (const g of groups) {
      for (const m of g.result?.magnets ?? []) {
        if (!map.has(m.handle_id)) map.set(m.handle_id, classifyRow(m));
      }
    }
    return map;
  });
  /**
   * Live triage of whatever is checked right now — the batch that would be
   * sent, split into the high-likelihood subset, plus the low / unrated
   * counts. Derived rather than snapshotted so the summary panel and the send
   * it performs can never drift apart from the checkboxes behind it.
   */
  let rdSendTriage = $derived.by(() => {
    const items = buildSelectedSendItems();
    const classes = items.map(
      (it) => rowClassByHandle.get(it.handle_id) ?? "unknown",
    );
    const { low, unrated } = summarizeRdLikelihood(classes);
    const highItems = items.filter(
      (_, i) => classes[i] === "prefix_hd" || classes[i] === "hd",
    );
    return { items, highItems, low, unrated };
  });

  /** Why a row won its group, spelled out for the ★ tooltip. */
  function rdPickTitle(tier: RdPickTier): string {
    if (tier === "prefix_hd") {
      return "本組首選：常見轉載站的高清版本，RD 最可能已有快取";
    }
    if (tier === "hd_earliest") {
      return "本組首選：最早上傳的高清版本，較久的檔案較可能已被快取";
    }
    return "本組首選（⚠ 全組皆非高清）：只能以轉載站前綴與上傳日期推測，命中率低";
  }

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

  /** Build the send-to-RD batch from the explicitly checked rows of ALL
   * groups — web and manual alike. Filters and sort only affect what is
   * displayed in the selection tab; they do not silently mutate the send
   * batch after a user has checked a row.
   *
   * Contract:
   *   - SELECTION: every checked handle_id in any group is sent; a
   *     handle present in two groups (same BTIH pasted manually AND
   *     scraped from a JavDB page, or a JavDB re-fetch landing on the
   *     same sidecar handle) is sent to RD exactly once.
   *   - METADATA on duplicates: the FIRST occurrence wins, and group
   *     order is deliberately web-first (startScrape keeps URL slots at
   *     the array head, manual groups at the tail). JavDB rows carry the
   *     canonical 番號 and a real size_label, while a manual row's
   *     `name` is the dn= extract — possibly empty or publisher noise.
   *     code/size_label are persisted into pending_torrents.json when a
   *     send lands in pending, so a degraded label would survive
   *     restarts. Do not reorder.
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
  function buildSelectedSendItems(): RdSendItem[] {
    const raw: RdSendItem[] = [];
    for (const g of groups) {
      const rows = g.result?.magnets ?? [];
      const groupCode = g.result?.code ?? "";
      const isPasteGroup = g.url.startsWith("manual://");
      for (const m of rows) {
        if (!selectedHandles[m.handle_id]) continue;
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

  async function sendSelectedToRd() {
    if (isRdSending || isRetryingPending) return;
    if (!rdHasToken) {
      rdMessage = "請先設定 RD Token";
      // The token editor lives on the settings tab, so bounce there — staying
      // on the RD tab would leave the user with no way to fix it.
      activeTab = "settings";
      return;
    }
    if (rdSendTriage.items.length === 0) {
      rdMessage = "目前沒有已勾選的磁力";
      activeTab = "select";
      return;
    }
    // `low` counts rows whose metadata says outright "not HD and not from a
    // re-upload site" — the ones most likely to sit in RD's queue instead of
    // returning a link. A batch with none of those has nothing to warn about,
    // so it keeps the existing one-click send rather than growing a
    // confirmation step for every user.
    if (rdSendTriage.low > 0) {
      sendPlanOpen = true;
      return;
    }
    await runSendBatch(rdSendTriage.items);
  }

  /** Run one of the summary panel's two confirmations. */
  async function confirmSend(scope: "all" | "high") {
    if (!sendPlanOpen) return;
    // Both guards have to be re-checked rather than inherited from
    // sendSelectedToRd: the panel stays on screen while the user is free to
    // start a pending-retry below it or clear the token on the settings tab.
    if (isRdSending || isRetryingPending) return;
    if (!rdHasToken) {
      sendPlanOpen = false;
      rdMessage = "請先設定 RD Token";
      activeTab = "settings";
      return;
    }
    // Read through rdSendTriage, never a snapshot taken when the panel
    // opened — whatever the user checked or unchecked in the meantime is what
    // gets sent.
    const items = scope === "high" ? rdSendTriage.highItems : rdSendTriage.items;
    if (items.length === 0) {
      sendPlanOpen = false;
      rdMessage = "目前沒有已勾選的磁力";
      activeTab = "select";
      return;
    }
    await runSendBatch(items);
  }

  function cancelSendPlan() {
    sendPlanOpen = false;
    rdMessage = "已取消送出，勾選狀態未變更";
  }

  /**
   * The send itself. Split out of sendSelectedToRd so 全部送出 and 只送高機率
   * drive the exact same lifecycle over their own subset — lastBatchStartAt
   * included, since copyRdDownloads orders completions relative to THIS
   * batch's start and a stale value would sort the results wrong.
   */
  async function runSendBatch(items: RdSendItem[]) {
    // The panel is one-shot: leaving it up would let a second click re-send a
    // batch that is already in flight.
    sendPlanOpen = false;
    lastBatchStartAt = new Date().toISOString();
    isRdSending = true;
    rdSendProgress = items.map((it) => ({
      handle_id: it.handle_id,
      code: it.code,
      size_label: it.size_label,
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
            const settled = rdSendProgress.filter(
              (r) => r.status !== "sending" && r.status !== "pending",
            ).length;
            rdSendDone = { done: settled, total: ev.total };
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
      isCancelingSend = false;
      rdSendAbort = null;
      // Refresh persistent pending list — rd_send_magnet on the Rust side
      // already added pending entries to disk.
      await reloadPendingSilently();
    }
  }

  function cancelRdSend() {
    isCancelingSend = true;
    rdSendAbort?.abort();
  }

  // Reactive controller for all button post-action confirmation flashes.
  // Logic + 1.2s timer + debounce-on-re-click live in flashAction.ts and are
  // unit-tested there; this file only wires keys to templates and call sites.
  const flash = createFlashController();
  onDestroy(() => flash.dispose());

  async function copyRdDownloads() {
    const lines: string[] = [];
    const completedRows = sortCompletedRowsByCompletionTime(
      rdSendProgress.filter((row) => row.status === "completed"),
      lastBatchStartAt,
    );
    for (const row of completedRows) {
      lines.push(...collectDownloadLinksFromRow(row));
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
    if (isRdSending || isRetryingPending) return;
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
    if (isRdSending || isRetryingPending) return;
    if (pendingEntries.length === 0) return;
    lastBatchStartAt = new Date().toISOString();
    isRetryingPending = true;
    retryAbort = new AbortController();
    const abortSignal = retryAbort.signal;
    pendingMessage = { kind: "info", text: `重試中 0/${pendingEntries.length}…` };

    const completedLinks: string[] = [];
    let completedCount = 0;
    let stillPendingCount = 0;
    let missingCount = 0;
    let errorCount = 0;
    const errorCodes: string[] = [];

    const batchTotal = pendingEntries.length;
    let processedCount = 0;
    try {
      await retryPending(
        pendingEntries,
        (ev: RdRetryEvent) => {
          processedCount = ev.index;
          if (ev.result.kind === "completed") {
            completedCount += 1;
            for (const l of ev.result.links) {
              if (l.download) completedLinks.push(l.download);
            }
            // Flip row from "in_pending" → "completed" + attach links so
            // 直連 N counter and row label update without a manual refresh.
            rdSendProgress = applyRetryEventToProgressRows(rdSendProgress, ev);
          } else if (ev.result.kind === "pending") {
            stillPendingCount += 1;
          } else if (ev.result.kind === "missing") {
            missingCount += 1;
            // Mark row as error so users don't think it's still queued forever.
            rdSendProgress = applyRetryEventToProgressRows(rdSendProgress, ev);
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
      await reloadPendingSilently("pending_list after retry");
    }

    const isAborted = abortSignal.aborted;
    const parts: string[] = [];
    if (completedCount > 0) parts.push(`${completedCount} 個完成`);
    if (stillPendingCount > 0) parts.push(`${stillPendingCount} 個仍在 RD 處理中`);
    if (missingCount > 0) parts.push(`${missingCount} 個已從 RD 消失（已移除）`);
    if (errorCount > 0) parts.push(`${errorCount} 個查詢失敗`);

    let summary = isAborted
      ? `已取消：完成 ${processedCount}/${batchTotal}`
      : parts.length > 0
        ? `重試完成：${parts.join("、")}`
        : "重試完成";

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

  function toggleCookiesShown() {
    cookiesShown = !cookiesShown;
    // Never leave a primed destructive button behind a collapsed section —
    // re-expanding would put "確定清除？" one click away with no warning in
    // view.
    if (!cookiesShown) cookiesClearArmed = false;
  }

  function toggleCookiesPaste() {
    cookiesPasteOpen = !cookiesPasteOpen;
    cookiesMessage = null;
    cookiesError = "";
    cookiesClearArmed = false;
    if (!cookiesPasteOpen) cookiesPasteInput = "";
  }

  function armCookiesClear() {
    cookiesClearArmed = true;
    cookiesMessage = null;
    cookiesError = "";
  }

  function cancelCookiesClear() {
    cookiesClearArmed = false;
  }

  async function clearCookies() {
    cookiesError = "";
    cookiesMessage = null;
    cookiesClearing = true;
    try {
      // `clear_cookies` hands back the post-clear status, so take it directly.
      // refreshCookiesStatus() would run migrate_cookies_now instead, and any
      // cookies.txt that survived would be promoted straight back.
      cookiesStatus = await invoke<CookiesStatus>("clear_cookies");
      cookiesClearArmed = false;
      cookiesPasteOpen = false;
      cookiesPasteInput = "";
      cookiesMessage = {
        kind: "ok",
        text: "cookies 已清除：Credential Manager 項目與資料目錄的 cookies.txt 都已刪除，執行中的 sidecar 也已清空。重新貼上前 JavDB 擷取會被 Cloudflare 擋下。",
      };
      flash.flash("cookies-clear");
    } catch (e) {
      const raw = errText(e);
      if (raw.startsWith("cookies_cleared_sidecar_stale")) {
        // Deletion succeeded; only the push to the running sidecar failed.
        // Reporting this as 清除失敗 would tell the user their credentials are
        // still stored when they are already gone, so say what really happened
        // and re-read the status (get_cookies_status is a plain read — unlike
        // refreshCookiesStatus it won't re-migrate anything).
        cookiesClearArmed = false;
        cookiesPasteOpen = false;
        cookiesPasteInput = "";
        try {
          cookiesStatus = await invoke<CookiesStatus>("get_cookies_status");
        } catch {
          cookiesStatus = null;
        }
        cookiesMessage = {
          kind: "info",
          text: "已清除儲存的 cookies（Credential Manager 與 cookies.txt），但執行中的 sidecar 未能同步，重新啟動 app 後才會完全生效。",
        };
      } else {
        // No stable error codes on the remaining paths (unlike cookies_empty /
        // cookies_too_large) — the raw string names the file or keyring step.
        cookiesMessage = { kind: "error", text: `清除失敗：${raw}` };
      }
    } finally {
      cookiesClearing = false;
    }
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
    if (settingsWriteBusy) return;
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
      const updated = await loadAndApplySettings();
      settingsDraft = freshSettingsDraft(updated);
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
    if (settingsWriteBusy) return;
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
          await loadAndApplySettings();
        } catch (e) {
          console.warn("read_settings after import failed:", e);
        }
      }
      if (legacyReport.pending_imported > 0) {
        await reloadPendingSilently("pending_list after import");
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
    if (isRdSending || isRetryingPending) return;
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
    if (isRdSending || isRetryingPending) return;
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
  /** Display-only ordering for the progress table. `rdSendProgress` itself is
   * never reordered — the send loop writes it by original index and pending
   * retry reconciles against it. */
  let rdDisplayRows = $derived(buildRdDisplayRows(rdSendProgress));
</script>

<main class="container">
  <h1>JavDBMagnet</h1>
  <p class="subtitle">JavDB Magnet → 挑選 → Real-Debrid 下載連結</p>

  <nav class="tabs" aria-label="主要流程">
    <button
      type="button"
      class:active={activeTab === "search"}
      aria-current={activeTab === "search" ? "page" : undefined}
      onclick={() => (activeTab = "search")}
      onkeydown={(e) => onTabKeydown(e, 0)}
    >
      1. 擷取 Magnet
      <span>{okCount}/{scrapeProgress.total || webGroups.length}</span>
    </button>
    <button
      type="button"
      class:active={activeTab === "select"}
      aria-current={activeTab === "select" ? "page" : undefined}
      onclick={() => (activeTab = "select")}
      onkeydown={(e) => onTabKeydown(e, 1)}
    >
      2. 挑選 Magnet
      <span>{selectedMagnets}/{selectableMagnets}</span>
    </button>
    <button
      type="button"
      class:active={activeTab === "rd"}
      aria-current={activeTab === "rd" ? "page" : undefined}
      onclick={() => (activeTab = "rd")}
      onkeydown={(e) => onTabKeydown(e, 2)}
    >
      3. RD 下載連結
      <span>{rdSendDone.total > 0 ? `${rdCompletedCount}/${rdSendDone.total}` : `待處理 ${pendingEntries.length}`}</span>
    </button>
    <button
      type="button"
      class:active={activeTab === "settings"}
      aria-current={activeTab === "settings" ? "page" : undefined}
      onclick={() => (activeTab = "settings")}
      onkeydown={(e) => onTabKeydown(e, 3)}
    >
      4. 設定
      <span>偏好 / Cookies</span>
    </button>
  </nav>

  {#if statusMessage}
    <p class="status global-status" aria-live="polite">{statusMessage}</p>
  {/if}

  <section hidden={activeTab !== "settings"}>
    <h2>Real-Debrid Token</h2>
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

  <section hidden={activeTab !== "settings"}>
    <h2>儲存位置</h2>
    <dl>
      <dt>資料目錄</dt>
      <dd>{dataDir}</dd>
      <dt>日誌目錄</dt>
      <dd>{logDir}</dd>
    </dl>
  </section>

  <section hidden={activeTab !== "settings"}>
    <h2>主題</h2>
    <button onclick={toggleTheme} disabled={settingsWriteBusy}>
      主題：{theme}（點擊切換）
    </button>
  </section>

  <section hidden={activeTab !== "settings"}>
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

  <section hidden={activeTab !== "rd"}>
    <h2>Real-Debrid</h2>
    <div class="rd-send-panel">
      <div>
        <strong>準備送出：{selectedMagnets} 個已勾選 Magnet</strong>
        <p class="muted small">
          從「2. 挑選 Magnet」分頁勾選後再送出；重複 BTIH 會在送出前合併一次。
        </p>
      </div>
      <div class="row tight">
        <button onclick={() => (activeTab = "select")}>回到挑選</button>
        <button
          onclick={sendSelectedToRd}
          disabled={isRdSending ||
            isRetryingPending ||
            selectedMagnets === 0 ||
            !rdHasToken ||
            sendPlanOpen}
          title={rdHasToken ? "" : "請先設定 RD Token"}
        >
          {isRdSending ? "送出中…" : sendButtonLabel}
        </button>
        {#if !rdHasToken}
          <span class="muted small">尚未設定 RD Token，無法送出。</span>
          <button type="button" onclick={() => (activeTab = "settings")}>
            前往「4. 設定」設定 Token
          </button>
        {/if}
      </div>
    </div>

    <!-- Pre-send triage. Only rendered when the batch actually contains
         low-likelihood rows, so a clean batch never grows an extra click. -->
    {#if sendPlanOpen}
      <div class="rd-plan-panel">
        <div>
          <strong>送出前確認：{rdSendTriage.items.length} 筆</strong>
          <p class="muted small">
            高機率 {rdSendTriage.highItems.length}／低機率 {rdSendTriage.low}／未判定
            {rdSendTriage.unrated}。機率由本機以轉載站前綴、解析度與上傳日期推測；
            Real-Debrid 已無快取查詢端點，低機率仍可能命中。
          </p>
        </div>
        <div class="row tight">
          <button onclick={() => confirmSend("all")}>
            全部送出（{rdSendTriage.items.length}）
          </button>
          <button
            onclick={() => confirmSend("high")}
            disabled={rdSendTriage.highItems.length === 0}
            title={rdSendTriage.highItems.length === 0 ? "這批沒有高機率候選" : ""}
          >
            只送高機率（{rdSendTriage.highItems.length}）
          </button>
          <button onclick={cancelSendPlan}>取消送出</button>
        </div>
      </div>
    {/if}

    <!-- rdMessage is shared with the token editor on the settings tab; the
         tabs are mutually exclusive, so only one of the two renders is ever
         visible. Without this copy the send / copy-link feedback on this tab
         would silently go nowhere. -->
    {#if rdMessage}
      <p class="status">{rdMessage}</p>
    {/if}
  </section>

  <section hidden={activeTab !== "settings"}>
    <h2>
      匯入舊版資料
      <button
        type="button"
        onclick={() => (legacyShown = !legacyShown)}
        class="section-toggle"
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
          disabled={settingsWriteBusy}
        />
        <button
          onclick={previewLegacyImport}
          disabled={settingsWriteBusy || !legacyPath.trim()}
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
          disabled={settingsWriteBusy || !legacyPreview || !legacyPreview.source_dir_valid}
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

  <section hidden={activeTab !== "settings"}>
    <h2>
      應用程式設定
      <button
        type="button"
        onclick={() => {
          if (!settingsShown) openSettingsEditor();
          else settingsShown = false;
        }}
        class="section-toggle"
      >{settingsShown ? "▴ 收合" : "▾ 展開"}</button>
    </h2>
    {#if settingsShown && settingsDraft}
      <p class="hint">
        編輯下列欄位後按「儲存設定」。RD Token 請在本頁上方的 <strong>Real-Debrid Token</strong> 區塊管理。
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
          disabled={!settingsValid || settingsWriteBusy}
          class:flash-ok={flash.keys.has("settings-save")}
        >
          {settingsSaving
            ? "儲存中…"
            : flash.keys.has("settings-save")
              ? "已儲存 ✓"
              : "儲存設定"}
        </button>
        <button onclick={revertSettingsDraft} disabled={settingsWriteBusy}>還原</button>
      </div>
      {#if settingsMessage}
        <p class="inline-msg" data-kind={settingsMessageKind}>{settingsMessage}</p>
      {/if}
    {/if}
  </section>

  <section hidden={activeTab !== "settings"}>
    <h2>
      JavDB Cookies
      <button
        type="button"
        onclick={toggleCookiesShown}
        class="section-toggle"
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
      {#if cookiesClearArmed}
        <div class="inline-msg" data-kind="error">
          <p>
            <strong>確定要清除 cookies？</strong>
            會刪除 Credential Manager 的 <code>JavDBMagnet/JAVDB_COOKIES</code>
            與資料目錄的 <code>cookies.txt</code>，並清空執行中 sidecar 的 cookies。
          </p>
          <p class="muted small">
            無法復原：本程式從不讀取 cookies 內容，因此無法幫你備份。要恢復擷取
            只能重新從瀏覽器 DevTools 取得一份並貼回。
          </p>
        </div>
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
        {#if cookiesClearArmed}
          <button onclick={clearCookies} disabled={cookiesClearing}>
            {cookiesClearing ? "清除中…" : "確定清除"}
          </button>
          <button onclick={cancelCookiesClear} disabled={cookiesClearing}>
            取消清除
          </button>
        {:else}
          <!-- Stays mounted-but-disabled when there is nothing stored, rather
               than {#if}-gated like 清除 Token: an unmount would swallow the
               「已清除 ✓」 flash the instant the clear succeeds. -->
          <button
            onclick={armCookiesClear}
            disabled={cookiesSaving || !cookiesStatus || cookiesStatus.storage === "none"}
            class:flash-ok={flash.keys.has("cookies-clear")}
          >
            {flash.keys.has("cookies-clear") ? "已清除 ✓" : "清除 cookies"}
          </button>
        {/if}
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

  <section hidden={activeTab !== "search"}>
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
          onclick={() => (activeTab = "select")}
          disabled={isScraping || selectableMagnets === 0}
        >
          前往挑選 Magnet（{selectableMagnets}）
        </button>
        <button
          onclick={clearResults}
          disabled={isRdSending || isRetryingPending}
          class:flash-ok={flash.keys.has("scrape-clear")}
        >
          {flash.keys.has("scrape-clear") ? "已清空 ✓" : "清空全部結果（含手貼）"}
        </button>
      {/if}
    </div>
    <div class="status-bar" data-active={isScraping}>
      {#if scrapeProgress.total > 0}
        <span>{scrapeProgress.done} / {scrapeProgress.total}</span>
        <span class="ok">✓ {okCount}</span>
        <span class="err">✗ {errCount}</span>
        <span class="muted">磁力：{webVisibleMagnets} / {totalRawMagnets}</span>
      {:else}
        <span class="muted">閒置</span>
      {/if}
    </div>

    {#if webGroups.length > 0}
      <!-- Per-URL outcome only. The magnet checkbox table belongs to
           「2. 挑選 Magnet」; this is here so a failed URL names itself
           without making the user leave the scrape step. -->
      <ul class="groups outcomes">
        {#each webGroups as g, i (g.url)}
          <li class="group outcome" data-status={g.status}>
            <span class="status-dot"></span>
            <strong>
              {#if g.result}
                {g.result.code || "（無番號）"}
              {:else}
                #{i + 1}
              {/if}
            </strong>
            <span class="muted url small">{g.url}</span>
            {#if g.status === "error"}
              <span class="error small">錯誤：{g.error}</span>
            {:else if g.result}
              <span class="muted small">{g.result.magnet_count} 個磁力</span>
            {:else}
              <span class="muted small">
                {g.status === "fetching" ? "擷取中…" : "等待中…"}
              </span>
            {/if}
          </li>
        {/each}
      </ul>
    {/if}

    {#if groups.length === 0 && !isScraping}
      <p class="empty-state">尚無結果 — 在上方貼上網址後按下<strong>開始擷取</strong>。</p>
    {/if}
  </section>

  <section hidden={activeTab !== "search"}>
    <h2>直接貼磁力</h2>
    <p class="hint">
      已有 <code>magnet:?xt=...</code> 連結時可貼在這裡。加入後切到
      <strong>2. 挑選 Magnet</strong> 分頁確認勾選，再到
      <strong>3. RD 下載連結</strong> 分頁送出。
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
        手貼 magnet 會自動勾選；若同 BTIH 先前被取消，貼上會重新勾選。
      </span>
    </div>
    {#if registerStatus}
      <p
        class="inline-msg"
        data-kind={registerStatus.kind}
      >{registerStatus.text}</p>
    {/if}
  </section>

  <section hidden={activeTab !== "select"}>
    <h2>每個番號選取 Magnet</h2>
    <p class="hint">
      篩選只控制畫面顯示；RD 送出以勾選狀態為準。同一 BTIH 只會送出一次。
    </p>
    {#if groups.length > 0}
      <div class="selection-summary">
        <div>
          <strong>已勾選 {selectedMagnets} / {selectableMagnets} 個 Magnet</strong>
          <span class="muted small">
            篩選只影響畫面顯示；已勾選項目會保留到 RD 分頁送出。
          </span>
        </div>
        <div class="row tight">
          <button onclick={() => setRowsSelected(allVisibleRows, true)}>
            勾選目前顯示
          </button>
          <button onclick={() => selectOnlyRows(allVisibleRows)}>
            只勾選目前顯示
          </button>
          <button onclick={selectRdCandidatesOnly}>
            只勾選 RD 優先候選
          </button>
          <button onclick={() => setRowsSelected(allVisibleRows, false)}>
            取消目前顯示
          </button>
          <button
            onclick={copySelected}
            disabled={selectedMagnets === 0}
            class:flash-ok={flash.keys.has("magnet-copy-selected")}
          >
            {flash.keys.has("magnet-copy-selected")
              ? "已複製 ✓"
              : `複製已勾選（${selectedMagnets}）`}
          </button>
          <button
            onclick={() => (activeTab = "rd")}
            disabled={selectedMagnets === 0}
          >
            前往 RD 下載連結
          </button>
        </div>
      </div>

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
            <option value="rd_ready">RD 命中優先</option>
            <option value="largest">最大檔</option>
            <option value="smallest">最小檔</option>
            <option value="fewest_files">檔案最少</option>
          </select>
        </label>
        <button onclick={resetFilter}>重置</button>
      </div>

      <ul class="groups">
        {#each groups as g, i (g.url)}
          {@const rows = processedRows(g)}
          {@const isCollapsed = collapsed[g.url] === true}
          <!-- Manual groups get no ★: processGroupRows short-circuits them
               past applyGroupPick entirely, so marking a "首選" there would
               advertise a narrowing that RD 命中優先 never performs on them. -->
          {@const rdPick = isManualGroup(g) ? undefined : rdPickByGroup.get(g.url)}
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
                  — 顯示 {rows.length} / 共 {g.result.magnet_count} 個磁力；
                  已勾 {selectedInRows(g.result.magnets)}
                </span>
                <span class="row tight">
                  <button class="small" onclick={() => setRowsSelected(rows, true)}>
                    勾選本組顯示
                  </button>
                  <button class="small" onclick={() => setRowsSelected(rows, false)}>
                    取消本組顯示
                  </button>
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
                      <th>送 RD</th>
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
                      <!-- Class comes from the shared map, not from a direct
                           classifyRow(m): a manual row and its web twin are
                           one BTIH, and the web row is the one with the
                           metadata worth reading. -->
                      {@const rdCls = rowClassByHandle.get(m.handle_id) ?? classifyRow(m)}
                      {@const rdMark = rdBadge(rdCls)}
                      <tr
                        class="row-copyable"
                        title="雙擊複製磁力連結"
                        ondblclick={() =>
                          copyOne(m.handle_id, m.name || g.result!.code)}
                      >
                        <td>
                          <input
                            type="checkbox"
                            checked={rowSelected(m.handle_id)}
                            onclick={(e) => e.stopPropagation()}
                            ondblclick={(e) => e.stopPropagation()}
                            onchange={(e) =>
                              setRowSelected(
                                m.handle_id,
                                (e.currentTarget as HTMLInputElement).checked,
                              )}
                            aria-label={`選取 ${m.name || g.result!.code}`}
                          />
                        </td>
                        <td>
                          {m.name}
                          {#if isManualGroup(g) && webHandleIds.has(m.handle_id)}
                            <span
                              class="badge"
                              title="這個手貼 magnet 的 BTIH 已存在於網頁擷取結果；勾選狀態共用，RD 只會送一次。"
                            >＝網頁同筆</span>
                          {/if}
                          {#if rdMark}
                            <span class="badge rd-badge" data-rd={rdCls} title={rdMark.title}
                              >{rdMark.text}</span>
                          {/if}
                          {#if rdPick && rdPick.row.handle_id === m.handle_id}
                            <span
                              class="badge rd-star"
                              data-tier={rdPick.tier}
                              title={rdPickTitle(rdPick.tier)}
                            >★</span>
                          {/if}
                        </td>
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
    {:else}
      <p class="empty-state">
        尚無 Magnet 可選取 — 請先到 <strong>1. 擷取 Magnet</strong> 分頁貼上 JavDB 網址或 magnet。
      </p>
    {/if}
  </section>

  {#if activeTab === "rd" && rdSendProgress.length > 0}
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
          <button onclick={cancelRdSend} disabled={isCancelingSend}>
            {isCancelingSend ? "取消中…" : "取消"}
          </button>
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
            <th>大小</th>
            <th>狀態</th>
            <th title="本程式確認該項目完成的時間，非 Real-Debrid 伺服器實際完成下載的時刻">
              完成時間（本程式確認）
            </th>
            <th>連結 / 訊息</th>
          </tr>
        </thead>
        <tbody>
          {#each rdDisplayRows as row (row.handle_id)}
            <!-- Gated on `status`, not on the presence of completed_at: a row
                 flipped to `error` by a pending "missing" event keeps its old
                 timestamp, and showing it there would be a lie. The tooltip
                 hangs off the rendered text for the same reason — an em dash
                 must not have a full ISO timestamp hiding behind it. -->
            {@const completedText =
              row.status === "completed" ? formatCompletedAt(row.completed_at) : "—"}
            <tr>
              <td>{row.code}</td>
              <td>{row.size_label || "—"}</td>
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
              <td class="small" title={completedText === "—" ? undefined : row.completed_at}>
                {completedText}
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

  {#if activeTab === "rd" && pendingEntries.length > 0}
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
          disabled={isRdSending || isRetryingPending || pendingEntries.length === 0 || !rdHasToken}
        >
          {isRetryingPending ? "重試中…" : "全部重試（查 RD）"}
        </button>
        {#if isRetryingPending}
          <button onclick={cancelRetry}>取消</button>
        {/if}
        <button
          onclick={refreshPending}
          disabled={isRdSending || isRetryingPending}
          class:flash-ok={flash.keys.has("pending-refresh")}
        >
          {flash.keys.has("pending-refresh") ? "已重讀 ✓" : "重讀本機紀錄"}
        </button>
        <button
          onclick={clearAllPending}
          disabled={isRdSending || isRetryingPending}
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
                <button onclick={() => removePending(p.torrent_id)} disabled={isRdSending || isRetryingPending}>移除</button>
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

  .tabs {
    display: grid;
    /* 4-up while every column still fits a label; below that the bar wraps to
       2-up and finally 1-up instead of squeezing the label into the count. */
    grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr));
    gap: 0.5rem;
    margin: 1rem 0 1.25rem;
  }

  .tabs button {
    display: flex;
    justify-content: space-between;
    align-items: center;
    /* The count drops to its own line rather than colliding with the label. */
    flex-wrap: wrap;
    gap: 0.25rem 0.5rem;
    min-width: 0;
    padding: 0.65rem 0.8rem;
    text-align: left;
    font-weight: 600;
  }

  .tabs button span {
    color: var(--color-muted);
    font-size: 0.85rem;
    font-weight: 500;
    white-space: nowrap;
  }

  .tabs button.active {
    border-color: #2ecc71;
    box-shadow: inset 0 -2px 0 #2ecc71;
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

  .global-status {
    margin: 0 0 1rem;
    padding: 0.5rem 0.75rem;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    background: var(--color-button-bg);
  }

  .row {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    margin-top: 0.5rem;
    flex-wrap: wrap;
  }

  .row.tight {
    margin-top: 0;
    gap: 0.35rem;
  }

  .selection-summary,
  .rd-send-panel,
  .rd-plan-panel {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    margin-top: 1rem;
    padding: 0.75rem;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    background: var(--color-button-bg);
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

  input[type="checkbox"] {
    accent-color: #2ecc71;
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

  .badge {
    display: inline-block;
    margin-left: 0.35rem;
    padding: 0.05rem 0.35rem;
    border: 1px solid var(--color-border);
    border-radius: 999px;
    color: var(--color-muted);
    font-size: 0.75rem;
    white-space: nowrap;
  }

  /* RD hit-likelihood markers, styled off a STATIC class + a dynamic data-*
     attribute — the same shape as .inline-msg[data-kind] above. A computed
     class name (`rd-badge-${cls}`) would be pruned as an unused selector and
     break the 0-warning svelte-check gate. */
  .rd-badge[data-rd="prefix_hd"],
  .rd-star[data-tier="prefix_hd"],
  .rd-star[data-tier="hd_earliest"] {
    border-color: #2ecc71;
    color: #2ecc71;
  }

  .rd-badge[data-rd="prefix_only"],
  .rd-badge[data-rd="hd"] {
    border-color: var(--color-fg);
    color: var(--color-fg);
  }

  /* The ⚠ tier: nothing in the group is HD, so the pick rests on the
     re-upload prefix and the upload date alone. */
  .rd-star[data-tier="no_hd_fallback"] {
    border-color: #f39c12;
    color: #f39c12;
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

  /* Search-tab outcome list: same dot/border language as the selection
     groups, one line per URL instead of a collapsible block. */
  .outcomes {
    gap: 0.3rem;
  }

  .group.outcome {
    display: flex;
    align-items: baseline;
    flex-wrap: wrap;
    gap: 0.5rem;
    padding: 0.3rem 0.6rem;
  }

  /* .error carries a block-level margin-top for standalone <p>; as a flex
     item here it would drop the message off the baseline. */
  .group.outcome .error {
    margin-top: 0;
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

  .section-toggle {
    margin-left: 0.5rem;
    font-size: 0.85rem;
    padding: 0.15rem 0.5rem;
  }

  @media (max-width: 760px) {
    .container {
      padding: 1rem;
    }

    .tabs {
      grid-template-columns: 1fr;
    }

    .selection-summary,
    .rd-send-panel,
    .rd-plan-panel {
      align-items: stretch;
      flex-direction: column;
    }
  }
</style>
