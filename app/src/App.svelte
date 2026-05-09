<script lang="ts">
  import { onMount } from "svelte";
  import { invoke } from "@tauri-apps/api/core";

  type Theme = "light" | "dark";

  interface PathInfo {
    data_dir: string;
    log_dir: string;
  }

  interface UiSettings {
    theme: Theme;
    scale: string;
  }

  interface RdSettings {
    api_token: string;
    file_pick: string;
    min_size_mb: number;
    cache_wait_seconds: number;
    wait_timeout_seconds: number;
  }

  interface Settings {
    version: number;
    ui: UiSettings;
    rd: RdSettings;
  }

  interface MagnetRow {
    handle_id: string;
    name: string;
    size: string;
    tags: string[];
    date: string;
    magnet_redacted: string;
  }

  interface FetchResult {
    engine: string;
    url: string;
    code: string;
    title: string;
    magnet_count: number;
    magnets: MagnetRow[];
  }

  interface PingResponse {
    ok: boolean;
    request_id: string;
    uptime_seconds: number;
  }

  interface CopyBulkResult {
    copied: number;
    unknown: number;
  }

  let dataDir = $state("(loading)");
  let logDir = $state("(loading)");
  let theme = $state<Theme>("light");
  let settings = $state<Settings | null>(null);
  let statusMessage = $state("");

  // M3 debug pane state
  let url = $state("https://javdb.com/v/RkX3Rp");
  let fetchResult = $state<FetchResult | null>(null);
  let fetchError = $state("");
  let isFetching = $state(false);
  let pingMessage = $state("");

  function applyTheme(t: Theme) {
    document.documentElement.dataset.theme = t;
  }

  onMount(async () => {
    try {
      const paths = await invoke<PathInfo>("get_paths");
      dataDir = paths.data_dir;
      logDir = paths.log_dir;
    } catch (e) {
      dataDir = `error: ${e}`;
      logDir = `error: ${e}`;
    }

    try {
      const s = await invoke<Settings>("read_settings");
      settings = s;
      theme = s.ui.theme;
      applyTheme(theme);
    } catch (e) {
      console.error("read_settings failed:", e);
      statusMessage = `read_settings error: ${e}`;
    }
  });

  async function toggleTheme() {
    if (settings === null) {
      statusMessage = "settings not loaded yet";
      return;
    }
    theme = theme === "light" ? "dark" : "light";
    applyTheme(theme);
    settings.ui.theme = theme;
    try {
      await invoke("write_settings", { settings });
      statusMessage = `theme persisted: ${theme}`;
    } catch (e) {
      console.error("write_settings failed:", e);
      statusMessage = `write_settings error: ${e}`;
    }
  }

  async function pingSidecar() {
    pingMessage = "(pinging…)";
    try {
      const resp = await invoke<PingResponse>("sidecar_ping");
      pingMessage = `ok — uptime ${resp.uptime_seconds}s, request_id ${resp.request_id}`;
    } catch (e) {
      pingMessage = `error: ${e}`;
    }
  }

  async function fetchJavdb() {
    if (!url.trim()) return;
    isFetching = true;
    fetchError = "";
    fetchResult = null;
    try {
      fetchResult = await invoke<FetchResult>("fetch_javdb", { url: url.trim() });
    } catch (e) {
      fetchError = `${e}`;
    } finally {
      isFetching = false;
    }
  }

  async function copyOne(handle_id: string, code: string) {
    try {
      await invoke("copy_magnet", { handleId: handle_id });
      statusMessage = `copied magnet for ${code}`;
    } catch (e) {
      statusMessage = `copy_magnet error: ${e}`;
    }
  }

  async function copyVisible() {
    if (!fetchResult || fetchResult.magnets.length === 0) return;
    const ids = fetchResult.magnets.map((m) => m.handle_id);
    try {
      const result = await invoke<CopyBulkResult>("copy_magnets_bulk", {
        handleIds: ids,
      });
      statusMessage =
        result.unknown > 0
          ? `copied ${result.copied}, ${result.unknown} stale`
          : `copied ${result.copied} magnets`;
    } catch (e) {
      statusMessage = `copy_magnets_bulk error: ${e}`;
    }
  }
</script>

<main class="container">
  <h1>JavDBMagnet</h1>
  <p class="subtitle">M3 — sidecar daemon wired</p>

  <section>
    <h2>Storage</h2>
    <dl>
      <dt>Data dir</dt>
      <dd>{dataDir}</dd>
      <dt>Log dir</dt>
      <dd>{logDir}</dd>
    </dl>
  </section>

  <section>
    <h2>Theme</h2>
    <button onclick={toggleTheme}>
      Theme: {theme} (click to toggle)
    </button>
    {#if statusMessage}
      <p class="status">{statusMessage}</p>
    {/if}
  </section>

  <section>
    <h2>Sidecar — debug pane (M3)</h2>

    <div class="row">
      <button onclick={pingSidecar}>Ping sidecar</button>
      {#if pingMessage}
        <span class="ping">{pingMessage}</span>
      {/if}
    </div>

    <div class="row stack">
      <label for="url-input">JavDB URL</label>
      <input
        id="url-input"
        type="text"
        bind:value={url}
        placeholder="https://javdb.com/v/..."
        spellcheck="false"
      />
      <button onclick={fetchJavdb} disabled={isFetching}>
        {isFetching ? "Fetching…" : "Fetch"}
      </button>
    </div>

    {#if fetchError}
      <p class="error">fetch error: {fetchError}</p>
    {/if}

    {#if fetchResult}
      <div class="result-meta">
        <strong>{fetchResult.code}</strong>
        — {fetchResult.title}
        <span class="muted">({fetchResult.engine}, {fetchResult.magnet_count} magnets)</span>
      </div>

      {#if fetchResult.magnets.length > 0}
        <button onclick={copyVisible} class="bulk">Copy all visible magnets</button>

        <table>
          <thead>
            <tr>
              <th>name</th>
              <th>size</th>
              <th>tags</th>
              <th>date</th>
              <th>redacted</th>
              <th>handle</th>
              <th>action</th>
            </tr>
          </thead>
          <tbody>
            {#each fetchResult.magnets as m (m.handle_id)}
              <tr>
                <td>{m.name}</td>
                <td>{m.size}</td>
                <td>{m.tags.join(", ")}</td>
                <td>{m.date}</td>
                <td class="mono small">{m.magnet_redacted}</td>
                <td class="mono small">{m.handle_id.slice(0, 12)}…</td>
                <td>
                  <button onclick={() => copyOne(m.handle_id, m.name || fetchResult.code)}>
                    copy
                  </button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
    {/if}
  </section>
</main>

<style>
  .container {
    max-width: 920px;
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
  .error {
    margin-top: 0.5rem;
    font-size: 0.9rem;
  }

  .status,
  .ping {
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
  }

  .row.stack {
    flex-wrap: wrap;
  }

  label {
    color: var(--color-muted);
    font-size: 0.9rem;
  }

  input[type="text"] {
    flex: 1;
    min-width: 18rem;
    padding: 0.4rem 0.6rem;
    border-radius: 6px;
    border: 1px solid var(--color-border);
    background: var(--color-button-bg);
    color: var(--color-fg);
    font: inherit;
  }

  .result-meta {
    margin-top: 1rem;
    padding: 0.5rem 0.75rem;
    border-left: 3px solid var(--color-border);
  }

  .muted {
    color: var(--color-muted);
    margin-left: 0.5rem;
  }

  .bulk {
    margin: 0.75rem 0;
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
</style>
