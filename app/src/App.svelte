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

  let dataDir = $state("(loading)");
  let logDir = $state("(loading)");
  let theme = $state<Theme>("light");
  let settings = $state<Settings | null>(null);
  let statusMessage = $state("");

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
</script>

<main class="container">
  <h1>JavDBMagnet</h1>
  <p class="subtitle">M2 skeleton — paths verified, settings round-trip working</p>

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
</main>

<style>
  .container {
    max-width: 720px;
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
    padding: 0.5rem 1rem;
    border-radius: 6px;
    border: 1px solid var(--color-border);
    background: var(--color-button-bg);
    color: var(--color-fg);
    cursor: pointer;
    font: inherit;
  }

  button:hover {
    background: var(--color-button-bg-hover);
  }

  .status {
    margin-top: 0.5rem;
    color: var(--color-muted);
    font-size: 0.9rem;
  }
</style>
