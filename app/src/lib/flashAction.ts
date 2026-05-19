// Generic "button just did something — show ✓ briefly" controller.
//
// Owns a reactive `SvelteSet<string>` of flash keys, plus per-key timers so
// rapid re-clicks debounce (timer restarts) rather than truncate the visible
// confirmation.
//
// `run(key, fn)` is the success-only wrapper: on resolve it flashes + returns
// the value; on reject it re-throws WITHOUT flashing, so the UI never lies
// about a successful action when the underlying invoke / fetch failed.

import { SvelteSet } from "svelte/reactivity";

const DEFAULT_DURATION_MS = 1200;

export interface FlashController {
  /** Reactive set of currently-flashing keys. Templates call `.has(key)`. */
  readonly keys: SvelteSet<string>;
  /** Add `key` to the set; auto-remove after `durationMs` (default 1200). */
  flash(key: string, durationMs?: number): void;
  /**
   * Run an async action; flash `key` on resolve, no flash on reject. Returns
   * the resolved value or re-throws the rejection unchanged.
   */
  run<T>(key: string, fn: () => Promise<T>, durationMs?: number): Promise<T>;
}

export function createFlashController(): FlashController {
  const keys = new SvelteSet<string>();
  const timers = new Map<string, ReturnType<typeof setTimeout>>();

  function flash(key: string, durationMs: number = DEFAULT_DURATION_MS): void {
    const existing = timers.get(key);
    if (existing !== undefined) clearTimeout(existing);
    keys.add(key);
    const handle = setTimeout(() => {
      keys.delete(key);
      timers.delete(key);
    }, durationMs);
    timers.set(key, handle);
  }

  async function run<T>(
    key: string,
    fn: () => Promise<T>,
    durationMs?: number,
  ): Promise<T> {
    const value = await fn();
    flash(key, durationMs);
    return value;
  }

  return { keys, flash, run };
}
