/// <reference types="vitest" />
import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { svelteTesting } from "@testing-library/svelte/vite";

const host = process.env.TAURI_DEV_HOST;

export default defineConfig({
  // svelteTesting() is a no-op outside `vitest`. It stops @testing-library's
  // runtime from being externalized, which would otherwise make its
  // `import { mount } from "svelte"` resolve to Svelte's SERVER build, where
  // mount() throws. The plugin's autoCleanup setup file WOULD work here
  // (it only bails when `globals` is on, and this project keeps globals
  // off) — it is disabled because App.test.ts wires setup/cleanup in the
  // test file, where the ordering against the Tauri invoke mock is visible.
  plugins: [svelte(), svelteTesting({ autoCleanup: false })],
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    host: host || false,
    hmr: host
      ? {
          protocol: "ws",
          host,
          port: 1421,
        }
      : undefined,
    watch: {
      ignored: ["**/src-tauri/**"],
    },
  },
  test: {
    // The glob spans both layers: the pure units under src/lib (parse /
    // filter / sort / group-pick / scraper / rdSender) and the App.svelte
    // component test that renders the four tabs into jsdom.
    environment: "jsdom",
    include: ["src/**/*.test.ts"],
    coverage: {
      reporter: ["text", "json", "html", "lcov"],
      include: ["src/main.ts", "src/lib/**/*.ts"],
      exclude: ["src/lib/**/*.test.ts"],
    },
  },
});
