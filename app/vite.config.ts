/// <reference types="vitest" />
import { defineConfig } from "vite";
import { svelte } from "@sveltejs/vite-plugin-svelte";

const host = process.env.TAURI_DEV_HOST;

export default defineConfig({
  plugins: [svelte()],
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
    // Pure unit tests for parse / filter / sort / group-pick / scraper.
    // No DOM needed for the current set, but jsdom is set up so future
    // component tests can be added without a config flip.
    environment: "jsdom",
    include: ["src/lib/**/*.test.ts"],
    coverage: {
      reporter: ["text", "json", "html", "lcov"],
      include: ["src/main.ts", "src/lib/**/*.ts"],
      exclude: ["src/lib/**/*.test.ts"],
    },
  },
});
