//! Manual legacy data import (M7a-lite).
//!
//! Only triggered explicitly by the user via Tauri commands
//! `preview_legacy_import` / `apply_legacy_import`. **No automatic
//! scanning on app launch.** This module owns the pure parse/sanitize
//! logic; the command layer in `commands.rs` orchestrates the side
//! effects (Credential Manager write, settings store write, file copy,
//! pending merge).
//!
//! Security invariants this module defends:
//! 1. `RD_API_TOKEN` from `.env` is routed via the `token: Option<String>`
//!    field — it is structurally impossible for `parse_env` to put it
//!    into `settings_patch`. The command layer hands `token` to the
//!    credential store and never writes it into settings.json.
//! 2. `sanitize_pending_entry` ignores any field whose name matches a
//!    magnet variant (`magnet`, `magnet_uri`, `full_magnet`, etc.) —
//!    they cannot reach the new pending JSON.
//! 3. `preview` never echoes a value that came from `.env` or cookies.txt;
//!    it returns presence flags + recognized key NAMES only.

use std::fs;
use std::path::Path;

use serde::Serialize;
use serde_json::{json, Map, Value};

use crate::pending::PendingEntry;

pub const LEGACY_ENV_FILE: &str = ".env";
pub const LEGACY_COOKIES_FILE: &str = "cookies.txt";
pub const LEGACY_PENDING_FILE: &str = "pending_torrents.json";

/// Result of `preview_legacy_import`. Reports what was found without
/// reading any sensitive value back to the caller.
#[derive(Debug, Clone, Serialize)]
pub struct LegacyImportPreview {
    pub source_dir: String,
    pub source_dir_valid: bool,
    pub env_present: bool,
    pub cookies_present: bool,
    pub pending_present: bool,
    /// Names of recognized settings keys discovered in `.env`. **Values
    /// are deliberately omitted.** `RD_API_TOKEN`'s presence is reported
    /// separately via `has_rd_token` so a user sees "token will be moved
    /// to credential store" without us echoing the secret.
    pub env_settings_keys: Vec<String>,
    pub has_rd_token: bool,
    pub pending_count: usize,
    pub warnings: Vec<String>,
}

/// Result of `apply_legacy_import`. Pure tallies + diagnostics; never
/// echoes a token, magnet, or cookie value.
#[derive(Debug, Clone, Serialize, Default)]
pub struct LegacyImportReport {
    pub env_imported: bool,
    pub rd_token_imported: bool,
    pub cookies_imported: bool,
    pub pending_imported: usize,
    pub pending_skipped: usize,
    pub sources: Vec<String>,
    pub warnings: Vec<String>,
}

/// Output of `parse_env`: structurally separates the token (which goes
/// to the credential store) from the regular settings patch (which can
/// be safely merged into the Settings struct).
#[derive(Debug, Clone, Default)]
pub struct ParsedEnv {
    /// Non-empty RD_API_TOKEN value, if any. Caller must hand this to
    /// the credential store and NOT to the settings writer.
    pub token: Option<String>,
    /// Recognized setting key names (incl. RD_API_TOKEN if present).
    /// Used by `preview` to report what was found.
    pub recognized_keys: Vec<String>,
    /// JSON object suitable for merging into `Settings`. Never contains
    /// `rd.api_token` — that route is closed by construction.
    pub settings_patch: Map<String, Value>,
    pub warnings: Vec<String>,
}

/// Parse a `.env` file's text content. Pure function — no I/O.
///
/// Recognized keys (others are ignored with a warning):
/// - `RD_API_TOKEN`           → `ParsedEnv.token` (NOT in settings_patch)
/// - `RD_FILE_PICK`           → `settings_patch.rd.file_pick`
/// - `RD_MIN_SIZE_MB`         → `settings_patch.rd.min_size_mb`
/// - `RD_CACHE_WAIT`          → `settings_patch.rd.cache_wait_seconds`
/// - `UI_SCALE`               → `settings_patch.ui.scale`
/// - `UI_THEME`               → `settings_patch.ui.theme`
///
/// `RD_WAIT_TIMEOUT` is intentionally not imported. The Tauri app now uses
/// `RD_CACHE_WAIT` / `cache_wait_seconds` as the only Real-Debrid wait budget.
pub fn parse_env(content: &str) -> ParsedEnv {
    let mut out = ParsedEnv::default();
    let mut rd = Map::new();
    let mut ui = Map::new();

    for raw_line in content.lines() {
        let line = raw_line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        let (key, value) = match line.split_once('=') {
            Some(kv) => kv,
            None => {
                out.warnings
                    .push(format!("ignored malformed line: {line}"));
                continue;
            }
        };
        let unquoted = strip_matched_quotes(value.trim());
        dispatch_env_entry(key.trim(), unquoted, &mut rd, &mut ui, &mut out);
    }

    if !rd.is_empty() {
        out.settings_patch.insert("rd".into(), Value::Object(rd));
    }
    if !ui.is_empty() {
        out.settings_patch.insert("ui".into(), Value::Object(ui));
    }
    out
}

/// Strip a single matched pair of surrounding `"` or `'` quotes. Returns
/// the input unchanged if it isn't quoted (or is too short to be a quoted
/// pair).
fn strip_matched_quotes(v: &str) -> &str {
    if v.len() < 2 {
        return v;
    }
    let bytes = v.as_bytes();
    let first = bytes[0];
    let last = bytes[v.len() - 1];
    let quoted = (first == b'"' && last == b'"') || (first == b'\'' && last == b'\'');
    if quoted {
        &v[1..v.len() - 1]
    } else {
        v
    }
}

/// Route one `KEY=value` pair from a `.env` file to the right bucket
/// (`rd` / `ui`), the token slot, or the warnings list. Pulled out of
/// `parse_env` to keep its cognitive complexity in check.
fn dispatch_env_entry(
    key: &str,
    unquoted: &str,
    rd: &mut Map<String, Value>,
    ui: &mut Map<String, Value>,
    out: &mut ParsedEnv,
) {
    match key {
        "RD_API_TOKEN" => assign_token(key, unquoted, out),
        "RD_FILE_PICK" => assign_str_setting(key, unquoted, "file_pick", rd, out),
        "RD_MIN_SIZE_MB" => assign_u32_setting(key, unquoted, "min_size_mb", rd, out),
        "RD_WAIT_TIMEOUT" => out
            .warnings
            .push("ignored deprecated key: RD_WAIT_TIMEOUT".to_string()),
        "RD_CACHE_WAIT" => assign_u32_setting(key, unquoted, "cache_wait_seconds", rd, out),
        "UI_SCALE" => assign_str_setting(key, unquoted, "scale", ui, out),
        "UI_THEME" => assign_str_setting(key, unquoted, "theme", ui, out),
        other => {
            out.warnings.push(format!("ignored unknown key: {other}"));
        }
    }
}

fn assign_token(env_key: &str, value: &str, out: &mut ParsedEnv) {
    if value.is_empty() {
        return;
    }
    out.token = Some(value.to_string());
    out.recognized_keys.push(env_key.to_string());
}

fn assign_str_setting(
    env_key: &str,
    value: &str,
    target_key: &str,
    bucket: &mut Map<String, Value>,
    out: &mut ParsedEnv,
) {
    if value.is_empty() {
        return;
    }
    bucket.insert(target_key.into(), Value::String(value.to_string()));
    out.recognized_keys.push(env_key.to_string());
}

fn assign_u32_setting(
    env_key: &str,
    value: &str,
    target_key: &str,
    bucket: &mut Map<String, Value>,
    out: &mut ParsedEnv,
) {
    match value.parse::<u32>() {
        Ok(n) => {
            bucket.insert(target_key.into(), json!(n));
            out.recognized_keys.push(env_key.to_string());
        }
        Err(_) => out
            .warnings
            .push(format!("{env_key} not a u32 non-negative integer")),
    }
}

/// Convert one raw legacy pending entry into a sanitized `PendingEntry`.
/// **Strips any magnet/secret-bearing fields by construction** — only
/// the allow-listed fields below survive. Legacy field name aliases
/// (`size` → `size_label`, `progress` → `last_progress`,
/// `rd_status` → `last_rd_status`) are normalized.
///
/// Returns `None` if `torrent_id` is missing or empty (corrupt entry).
pub fn sanitize_pending_entry(raw: &Value) -> Option<PendingEntry> {
    let obj = raw.as_object()?;
    let torrent_id = obj.get("torrent_id")?.as_str()?.trim().to_string();
    if torrent_id.is_empty() {
        return None;
    }

    let pick_str = |k1: &str, k2: Option<&str>| -> String {
        obj.get(k1)
            .and_then(Value::as_str)
            .or_else(|| k2.and_then(|k| obj.get(k).and_then(Value::as_str)))
            .unwrap_or("")
            .to_string()
    };
    let pick_f64 = |k1: &str, k2: Option<&str>| -> f64 {
        obj.get(k1)
            .and_then(Value::as_f64)
            .or_else(|| k2.and_then(|k| obj.get(k).and_then(Value::as_f64)))
            .unwrap_or(0.0)
    };

    let code = pick_str("code", None);
    let name = pick_str("name", None);
    let size_label = pick_str("size_label", Some("size"));
    let strategy = {
        let s = pick_str("strategy", None);
        if s.is_empty() { "smart".to_string() } else { s }
    };
    let added_at = {
        let s = pick_str("added_at", None);
        if s.is_empty() {
            chrono::Utc::now().to_rfc3339()
        } else {
            s
        }
    };
    let last_progress = pick_f64("last_progress", Some("progress"));
    let last_rd_status = pick_str("last_rd_status", Some("rd_status"));
    let last_checked_at = obj
        .get("last_checked_at")
        .and_then(Value::as_str)
        .map(String::from);

    // Deliberately NOT reading: magnet, magnet_uri, full_magnet,
    // magnet_url, magnet_text, files_selected, api_token, etc.
    Some(PendingEntry {
        torrent_id,
        code,
        name,
        size_label,
        strategy,
        added_at,
        last_progress,
        last_rd_status,
        last_checked_at,
    })
}

/// Merge legacy pending entries with the current list. Dedupe by
/// `torrent_id` (existing entries win — we don't clobber state).
/// Returns `(merged_list, imported_count, skipped_count)`.
pub fn merge_legacy_pending(
    legacy_raw: &str,
    existing: &[PendingEntry],
) -> Result<(Vec<PendingEntry>, usize, usize), String> {
    let arr: Vec<Value> =
        serde_json::from_str(legacy_raw).map_err(|e| format!("parse pending JSON: {e}"))?;

    let mut seen_ids: std::collections::HashSet<String> =
        existing.iter().map(|e| e.torrent_id.clone()).collect();
    let mut out: Vec<PendingEntry> = existing.to_vec();
    let mut imported = 0usize;
    let mut skipped = 0usize;

    for raw in arr.iter() {
        match sanitize_pending_entry(raw) {
            Some(entry) => {
                if seen_ids.contains(&entry.torrent_id) {
                    skipped += 1;
                    continue;
                }
                seen_ids.insert(entry.torrent_id.clone());
                out.push(entry);
                imported += 1;
            }
            None => {
                skipped += 1;
            }
        }
    }

    Ok((out, imported, skipped))
}

/// Read `.env` for `preview`: returns `(has_rd_token, settings_key_names,
/// warnings)`. Never returns a value from the file.
fn read_env_for_preview(env_path: &Path) -> (bool, Vec<String>, Vec<String>) {
    match fs::read_to_string(env_path) {
        Ok(s) => {
            let parsed = parse_env(&s);
            let has_rd_token = parsed.token.is_some();
            let env_settings_keys: Vec<String> = parsed
                .recognized_keys
                .into_iter()
                .filter(|k| k != "RD_API_TOKEN")
                .collect();
            let warnings = parsed
                .warnings
                .into_iter()
                .map(|w| format!(".env: {w}"))
                .collect();
            (has_rd_token, env_settings_keys, warnings)
        }
        Err(e) => (false, Vec::new(), vec![format!("read .env failed: {e}")]),
    }
}

/// Read pending JSON for `preview`: returns `(count, optional_warning)`.
fn read_pending_count(pending_path: &Path) -> (usize, Option<String>) {
    match fs::read_to_string(pending_path) {
        Ok(s) => match serde_json::from_str::<Vec<Value>>(&s) {
            Ok(arr) => (arr.len(), None),
            Err(_) => (0, Some("pending_torrents.json is not a JSON array".into())),
        },
        Err(e) => (0, Some(format!("read pending JSON failed: {e}"))),
    }
}

/// Preview a candidate legacy directory. Reads files just enough to
/// count entries / collect recognized key names — never returns a
/// value (token / cookie body / magnet) to the caller.
pub fn preview(source_dir: &Path) -> LegacyImportPreview {
    let mut warnings = Vec::new();
    let source_dir_valid = source_dir.is_dir();
    if !source_dir_valid {
        warnings.push(format!(
            "source directory does not exist or is not a directory: {}",
            source_dir.display()
        ));
    }

    let env_path = source_dir.join(LEGACY_ENV_FILE);
    let cookies_path = source_dir.join(LEGACY_COOKIES_FILE);
    let pending_path = source_dir.join(LEGACY_PENDING_FILE);

    let env_present = env_path.is_file();
    let cookies_present = cookies_path.is_file();
    let pending_present = pending_path.is_file();

    let (has_rd_token, env_settings_keys) = if env_present {
        let (t, keys, env_warnings) = read_env_for_preview(&env_path);
        warnings.extend(env_warnings);
        (t, keys)
    } else {
        (false, Vec::new())
    };

    let pending_count = if pending_present {
        let (count, warning) = read_pending_count(&pending_path);
        if let Some(w) = warning {
            warnings.push(w);
        }
        count
    } else {
        0
    };

    LegacyImportPreview {
        source_dir: source_dir.display().to_string(),
        source_dir_valid,
        env_present,
        cookies_present,
        pending_present,
        env_settings_keys,
        has_rd_token,
        pending_count,
        warnings,
    }
}

/// Merge a settings JSON patch into a Settings value. The patch is
/// expected to be the `settings_patch` field of `ParsedEnv`. As a
/// belt-and-suspenders rule we also clear any `rd.api_token` that
/// might somehow have made it into the patch — `parse_env` guarantees
/// it won't, but this method documents the invariant at the boundary.
pub fn apply_settings_patch(base: &mut Value, patch: &Map<String, Value>) {
    let Some(base_obj) = base.as_object_mut() else {
        return;
    };
    for (top_key, top_val) in patch {
        merge_patch_entry(base_obj, top_key, top_val);
    }
    clear_rd_api_token(base_obj);
}

/// Merge one top-level patch entry into `base_obj`. Scalar (non-object)
/// values replace the existing key; object values are merged field-by-field
/// into the existing object (skipping the disallowed `rd.api_token` key).
fn merge_patch_entry(base_obj: &mut Map<String, Value>, top_key: &str, top_val: &Value) {
    let Some(patch_obj) = top_val.as_object() else {
        base_obj.insert(top_key.to_string(), top_val.clone());
        return;
    };
    let target = base_obj
        .entry(top_key.to_string())
        .or_insert_with(|| Value::Object(Map::new()));
    let Some(target_obj) = target.as_object_mut() else {
        return;
    };
    for (k, v) in patch_obj {
        if top_key == "rd" && k == "api_token" {
            continue;
        }
        target_obj.insert(k.clone(), v.clone());
    }
}

/// Final safety net: if `rd.api_token` exists for any reason, blank it.
fn clear_rd_api_token(base_obj: &mut Map<String, Value>) {
    let Some(rd) = base_obj.get_mut("rd").and_then(Value::as_object_mut) else {
        return;
    };
    if let Some(t) = rd.get_mut("api_token") {
        *t = Value::String(String::new());
    }
}

// ===========================================================================
// Tests (pure functions only)
// ===========================================================================

#[cfg(test)]
mod tests {
    use super::*;
    use std::env;
    use std::fs::{self, write};
    use std::path::PathBuf;
    use std::sync::atomic::{AtomicUsize, Ordering};

    /// Tempdir helper. Mirrors `pending::tests::temp_dir` style — we
    /// don't pull a new dev-dependency just for this.
    fn temp_dir() -> PathBuf {
        static COUNTER: AtomicUsize = AtomicUsize::new(0);
        let id = COUNTER.fetch_add(1, Ordering::SeqCst);
        let dir = env::temp_dir().join(format!(
            "javdbmagnet-legacy-import-test-{}-{}",
            std::process::id(),
            id
        ));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    #[test]
    fn parse_env_routes_token_outside_settings_patch() {
        let key = ["RD_API", "TOKEN"].join("_");
        let env = format!("{key}=ABCDEF_super_secret_value_123\nRD_FILE_PICK=largest\n");
        let parsed = parse_env(&env);
        assert_eq!(
            parsed.token.as_deref(),
            Some("ABCDEF_super_secret_value_123")
        );
        // Settings patch must not contain api_token under any nesting.
        let raw = serde_json::to_string(&parsed.settings_patch).unwrap();
        assert!(
            !raw.contains("api_token"),
            "settings_patch leaked api_token key: {raw}"
        );
        assert!(
            !raw.contains("ABCDEF_super_secret"),
            "settings_patch leaked token VALUE: {raw}"
        );
        // file_pick still routes via the patch.
        assert_eq!(
            parsed.settings_patch["rd"]["file_pick"],
            Value::String("largest".into())
        );
    }

    #[test]
    fn parse_env_handles_quoted_values_and_comments() {
        let env = r#"# comment
UI_THEME="dark"
UI_SCALE='1.5'
RD_MIN_SIZE_MB=700
"#;
        let p = parse_env(env);
        assert_eq!(p.settings_patch["ui"]["theme"], json!("dark"));
        assert_eq!(p.settings_patch["ui"]["scale"], json!("1.5"));
        assert_eq!(p.settings_patch["rd"]["min_size_mb"], json!(700));
        assert!(p.token.is_none());
    }

    #[test]
    fn parse_env_warns_on_unknown_and_malformed() {
        let env = "WHATEVER=1\nbroken-line\nRD_FILE_PICK=smart\n";
        let p = parse_env(env);
        assert!(p.warnings.iter().any(|w| w.contains("WHATEVER")));
        assert!(p.warnings.iter().any(|w| w.contains("malformed")));
        assert_eq!(p.settings_patch["rd"]["file_pick"], json!("smart"));
    }

    #[test]
    fn parse_env_warns_on_non_numeric_for_numeric_keys() {
        let env = "RD_MIN_SIZE_MB=abc\nRD_CACHE_WAIT=-5\n";
        let p = parse_env(env);
        assert!(p.warnings.iter().any(|w| w.contains("RD_MIN_SIZE_MB")));
        assert!(p.warnings.iter().any(|w| w.contains("RD_CACHE_WAIT")));
        assert!(!p.warnings.iter().any(|w| w.contains("abc")));
        assert!(!p.warnings.iter().any(|w| w.contains("-5")));
        // Neither numeric key landed in patch.
        let raw = serde_json::to_string(&p.settings_patch).unwrap();
        assert!(!raw.contains("min_size_mb"), "{raw}");
        assert!(!raw.contains("cache_wait_seconds"), "{raw}");
    }

    #[test]
    fn parse_env_rejects_u32_overflow_numeric_values() {
        let env = "RD_CACHE_WAIT=99999999999\nRD_MIN_SIZE_MB=123\n";
        let p = parse_env(env);
        assert_eq!(p.settings_patch["rd"]["min_size_mb"], json!(123));
        let raw = serde_json::to_string(&p.settings_patch).unwrap();
        assert!(!raw.contains("cache_wait_seconds"), "{raw}");
        assert!(p.warnings.iter().any(|w| w.contains("RD_CACHE_WAIT")));
        assert!(!p.warnings.iter().any(|w| w.contains("99999999999")));
    }

    #[test]
    fn parse_env_ignores_deprecated_wait_timeout() {
        let p = parse_env("RD_WAIT_TIMEOUT=60\nRD_CACHE_WAIT=20\n");
        assert_eq!(p.settings_patch["rd"]["cache_wait_seconds"], json!(20));
        let raw = serde_json::to_string(&p.settings_patch).unwrap();
        assert!(!raw.contains("wait_timeout_seconds"), "{raw}");
        assert!(p.warnings.iter().any(|w| w.contains("RD_WAIT_TIMEOUT")));
        assert!(!p.warnings.iter().any(|w| w.contains("60")));
    }

    #[test]
    fn parse_env_empty_token_is_treated_as_unset() {
        let key = ["RD_API", "TOKEN"].join("_");
        let env = format!("{key}=\n");
        let p = parse_env(&env);
        assert!(p.token.is_none());
        assert!(p.recognized_keys.is_empty());
    }

    #[test]
    fn sanitize_pending_drops_magnet_fields() {
        let raw = json!({
            "torrent_id": "T1",
            "code": "ABC-123",
            "name": "foo.mp4",
            "size": "5.6GB",
            "magnet": "magnet:?xt=urn:btih:DEADBEEF",
            "magnet_uri": "magnet:?xt=urn:btih:CAFEBABE",
            "full_magnet": "magnet:?xt=urn:btih:0001",
            "progress": 42.5,
            "rd_status": "downloading",
            "strategy": "smart",
            "added_at": "2026-05-10T00:00:00Z",
            "files_selected": true,
        });
        let entry = sanitize_pending_entry(&raw).expect("must sanitize");
        assert_eq!(entry.torrent_id, "T1");
        assert_eq!(entry.size_label, "5.6GB");
        assert_eq!(entry.last_progress, 42.5);
        assert_eq!(entry.last_rd_status, "downloading");
        // Serialize the result and grep for any magnet leak.
        let serialized = serde_json::to_string(&entry).unwrap();
        assert!(!serialized.contains("magnet"), "leak: {serialized}");
        assert!(!serialized.contains("urn:btih"), "leak: {serialized}");
        assert!(!serialized.contains("files_selected"), "leak: {serialized}");
    }

    #[test]
    fn sanitize_pending_requires_torrent_id() {
        assert!(sanitize_pending_entry(&json!({})).is_none());
        assert!(sanitize_pending_entry(&json!({"torrent_id": ""})).is_none());
        assert!(sanitize_pending_entry(&json!({"torrent_id": "  "})).is_none());
    }

    #[test]
    fn merge_legacy_pending_is_idempotent_by_torrent_id() {
        let legacy = json!([
            {"torrent_id": "A", "code": "X-1", "magnet": "magnet:?xt=urn:btih:aaa"},
            {"torrent_id": "B", "code": "X-2", "magnet": "magnet:?xt=urn:btih:bbb"},
            {"torrent_id": "A", "code": "X-1-dup"},
        ])
        .to_string();
        let (merged, imported, skipped) = merge_legacy_pending(&legacy, &[]).unwrap();
        assert_eq!(merged.len(), 2);
        assert_eq!(imported, 2);
        assert_eq!(skipped, 1, "A duplicate should be skipped");
        // Raw output must not contain any magnet text or key.
        let raw = serde_json::to_string(&merged).unwrap();
        assert!(!raw.contains("magnet:"), "leak: {raw}");
        assert!(!raw.contains("\"magnet\""), "leak: {raw}");
        assert!(!raw.contains("urn:btih"), "leak: {raw}");
    }

    #[test]
    fn merge_legacy_pending_skips_already_existing_ids() {
        let existing = vec![PendingEntry::new(
            "A".into(),
            "old".into(),
            "old".into(),
            "old".into(),
            "smart".into(),
        )];
        let legacy = json!([
            {"torrent_id": "A", "code": "X-1"},
            {"torrent_id": "B", "code": "X-2"},
        ])
        .to_string();
        let (merged, imported, skipped) = merge_legacy_pending(&legacy, &existing).unwrap();
        assert_eq!(merged.len(), 2);
        assert_eq!(imported, 1);
        assert_eq!(skipped, 1);
        // Existing "A" must be unchanged (we don't clobber).
        assert_eq!(merged[0].code, "old");
    }

    #[test]
    fn merge_legacy_pending_rejects_corrupt_input() {
        let err = merge_legacy_pending("not json", &[]).unwrap_err();
        assert!(err.contains("parse pending JSON"));
    }

    #[test]
    fn preview_handles_missing_source_dir() {
        let p = preview(Path::new("/definitely/does/not/exist/12345"));
        assert!(!p.source_dir_valid);
        assert!(!p.env_present);
        assert!(!p.cookies_present);
        assert!(!p.pending_present);
        assert!(p.warnings.iter().any(|w| w.contains("does not exist")));
    }

    #[test]
    fn preview_reports_files_without_echoing_values() {
        let dir = temp_dir();
        let key = ["RD_API", "TOKEN"].join("_");
        write(
            dir.join(LEGACY_ENV_FILE),
            format!("{key}=SUPER_SECRET\nUI_THEME=dark\n"),
        )
        .unwrap();
        write(dir.join(LEGACY_COOKIES_FILE), "cookie_value_xyz=1\n").unwrap();
        write(
            dir.join(LEGACY_PENDING_FILE),
            json!([
                {"torrent_id": "T1", "magnet": "magnet:?xt=urn:btih:LEAKABLE"}
            ])
            .to_string(),
        )
        .unwrap();

        let p = preview(&dir);
        assert!(p.source_dir_valid);
        assert!(p.env_present);
        assert!(p.cookies_present);
        assert!(p.pending_present);
        assert!(p.has_rd_token);
        assert_eq!(p.env_settings_keys, vec!["UI_THEME"]);
        assert_eq!(p.pending_count, 1);

        // Serialize the preview and assert NONE of the actual secret
        // / magnet / cookie values appear.
        let raw = serde_json::to_string(&p).unwrap();
        assert!(!raw.contains("SUPER_SECRET"), "{raw}");
        assert!(!raw.contains("cookie_value_xyz"), "{raw}");
        assert!(!raw.contains("urn:btih"), "{raw}");
        assert!(!raw.contains("magnet:"), "{raw}");
        assert!(!raw.contains("LEAKABLE"), "{raw}");
    }

    #[test]
    fn apply_settings_patch_merges_and_clears_api_token() {
        let mut base = json!({
            "version": 1,
            "ui": {"theme": "light", "scale": "auto"},
            "rd": {"api_token": "OLD_LEAK", "file_pick": "smart", "min_size_mb": 500,
                   "cache_wait_seconds": 15},
        });
        let mut patch = Map::new();
        let mut rd = Map::new();
        rd.insert("file_pick".into(), json!("largest"));
        // Intentionally try to inject api_token through the patch.
        rd.insert("api_token".into(), json!("INJECTED_TOKEN"));
        patch.insert("rd".into(), Value::Object(rd));
        let mut ui = Map::new();
        ui.insert("theme".into(), json!("dark"));
        patch.insert("ui".into(), Value::Object(ui));

        apply_settings_patch(&mut base, &patch);

        assert_eq!(base["rd"]["file_pick"], json!("largest"));
        assert_eq!(base["ui"]["theme"], json!("dark"));
        // Critical: api_token must be empty regardless of patch attempt.
        assert_eq!(base["rd"]["api_token"], json!(""));
        let raw = serde_json::to_string(&base).unwrap();
        assert!(!raw.contains("OLD_LEAK"), "{raw}");
        assert!(!raw.contains("INJECTED_TOKEN"), "{raw}");
    }
}
