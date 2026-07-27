// M7c — Pure validation for the Settings editor.
//
// Each validator returns `null` for "OK" or a Traditional Chinese error
// string for "not OK". `validateSettingsDraft` aggregates per-field
// errors keyed by a stable id the UI uses to render inline messages.
//
// These functions are deliberately pure: no Tauri imports, no DOM, no
// side effects. The Rust side enforces the same shape on persist via
// `Settings`'s deserializer + `without_secrets` — frontend validation
// is just an early gate to disable Save and surface a friendly message.

import type { Settings } from "./types";

export const FILE_PICK_VALUES = ["smart", "largest", "video", "all"] as const;
export type FilePickValue = (typeof FILE_PICK_VALUES)[number];

export const THEME_VALUES = ["light", "dark"] as const;
export type ThemeValue = (typeof THEME_VALUES)[number];

export const SCALE_PRESETS = [
  "auto",
  "1.0",
  "1.25",
  "1.5",
  "1.75",
  "2.0",
  "2.5",
  "3.0",
] as const;

const SCALE_MIN = 0.5;
const SCALE_MAX = 3;

/** min_size_mb: non-negative integer. */
export function validateMinSizeMb(value: number): string | null {
  if (!Number.isFinite(value)) return "必須是數字";
  if (!Number.isInteger(value)) return "必須是整數";
  if (value < 0) return "不能為負";
  return null;
}

/** cache_wait_seconds: integer in [5, 300].
 *
 * The 300s ceiling mirrors `MAX_RD_CACHE_WAIT_SECS` in Rust
 * `sidecar_manager.rs`: the per-request sidecar timeout for
 * `rd_send_magnet` is `cache_wait + 90s` (slack), and we cap the budget
 * so a single hung magnet can't lock the manager for an arbitrary
 * duration. Settings the user can pick must agree with what the Rust
 * side will actually accept.
 */
export function validateCacheWaitSeconds(value: number): string | null {
  if (!Number.isFinite(value)) return "必須是數字";
  if (!Number.isInteger(value)) return "必須是整數";
  if (value < 5) return "最小為 5 秒（避免 RD 端尚未判定快取就放棄）";
  if (value > 300) return "最大為 300 秒（避免單一磁力長時間鎖住 sidecar）";
  return null;
}

/** scale: literal "auto" or a decimal in [0.5, 3.0]. */
export function validateScale(value: string): string | null {
  if (typeof value !== "string") return "必須是字串";
  const trimmed = value.trim();
  if (trimmed.length === 0) return "不能為空";
  if (trimmed === "auto") return null;
  if (!/^\d+(\.\d+)?$/.test(trimmed)) {
    return "必須是 auto 或 0.5–3.0 之間的數字";
  }
  const n = Number.parseFloat(trimmed);
  if (!Number.isFinite(n)) return "必須是 auto 或 0.5–3.0 之間的數字";
  if (n < SCALE_MIN || n > SCALE_MAX) {
    return `必須在 ${SCALE_MIN}–${SCALE_MAX} 之間`;
  }
  return null;
}

/** file_pick: must be one of FILE_PICK_VALUES. */
export function validateFilePick(value: string): string | null {
  if (!FILE_PICK_VALUES.includes(value as FilePickValue)) {
    return `必須是 ${FILE_PICK_VALUES.join(" / ")} 之一`;
  }
  return null;
}

/** theme: must be one of THEME_VALUES. */
export function validateTheme(value: string): string | null {
  if (!THEME_VALUES.includes(value as ThemeValue)) {
    return `必須是 ${THEME_VALUES.join(" / ")} 之一`;
  }
  return null;
}

/**
 * Validate the full draft. Keys in the returned map mirror UI field ids:
 *   - "rd.file_pick"
 *   - "rd.min_size_mb"
 *   - "rd.cache_wait_seconds"
 *   - "ui.theme"
 *   - "ui.scale"
 * Empty map means draft is valid.
 */
export function validateSettingsDraft(draft: Settings): Record<string, string> {
  const errs: Record<string, string> = {};
  const fp = validateFilePick(draft.rd.file_pick);
  if (fp) errs["rd.file_pick"] = fp;
  const mn = validateMinSizeMb(draft.rd.min_size_mb);
  if (mn) errs["rd.min_size_mb"] = mn;
  const cw = validateCacheWaitSeconds(draft.rd.cache_wait_seconds);
  if (cw) errs["rd.cache_wait_seconds"] = cw;
  const th = validateTheme(draft.ui.theme);
  if (th) errs["ui.theme"] = th;
  const sc = validateScale(draft.ui.scale);
  if (sc) errs["ui.scale"] = sc;
  return errs;
}
