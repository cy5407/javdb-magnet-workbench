//! Tauri commands for the M3 debug pane.
//!
//! Sensitive data (full magnets) never crosses back into Rust long-lived
//! state or frontend payloads:
//!   - `fetch_javdb` returns redacted magnets + handle_id
//!   - `copy_magnet`/`copy_magnets_bulk` resolve full magnets via the
//!     sidecar, write to OS clipboard, and drop the local string before
//!     returning
//!   - The frontend receives only counts / status, never the magnet text
//!
//! Clipboard policy (M6 follow-up): all clipboard writes funnel through
//! Rust commands. The frontend never invokes `tauri-plugin-clipboard-manager`
//! directly. RD direct links (non-secret, but routed through Rust for
//! consistency with magnets) go through `copy_rd_links_bulk`.

use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};
use serde_json::{json, Map, Value};
use tauri::{AppHandle, State};
use tauri_plugin_clipboard_manager::ClipboardExt;
use tauri_plugin_store::StoreExt;

use crate::legacy_import::{self, LegacyImportPreview, LegacyImportReport};
use crate::path_manager::PathManager;
use crate::pending::{self, PendingEntry};
use crate::secret_store;
use crate::sidecar_manager::SidecarManager;

#[tauri::command]
pub async fn sidecar_ping(sidecar: State<'_, SidecarManager>) -> Result<Value, String> {
    sidecar.request("ping", Value::Null).await
}

#[tauri::command]
pub async fn fetch_javdb(
    sidecar: State<'_, SidecarManager>,
    url: String,
) -> Result<Value, String> {
    let resp = sidecar
        .request("fetch_javdb", json!({ "url": url }))
        .await?;
    if !resp.get("ok").and_then(|v| v.as_bool()).unwrap_or(false) {
        let msg = resp
            .get("error")
            .and_then(|e| e.get("message"))
            .and_then(|m| m.as_str())
            .unwrap_or("unknown error");
        return Err(msg.to_string());
    }
    Ok(resp.get("result").cloned().unwrap_or(Value::Null))
}

#[tauri::command]
pub async fn copy_magnet(
    app: AppHandle,
    sidecar: State<'_, SidecarManager>,
    handle_id: String,
) -> Result<(), String> {
    let resp = sidecar
        .request("resolve_magnet", json!({ "handle_id": handle_id }))
        .await?;
    ensure_ok(&resp)?;
    let magnet = resp
        .get("magnet")
        .and_then(|m| m.as_str())
        .ok_or("response missing magnet field")?
        .to_string();
    app.clipboard()
        .write_text(magnet)
        .map_err(|e| e.to_string())?;
    // The local `magnet` String drops here; never returned to the frontend
    // and never logged at any layer.
    Ok(())
}

#[derive(Serialize)]
pub struct CopyBulkResult {
    pub copied: usize,
    pub unknown: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RegisteredMagnet {
    pub handle_id: String,
    pub magnet_redacted: String,
    /// Display name extracted from the magnet's `dn=` parameter
    /// (e.g. "[javdb.com]SNOS-192"). Empty when the magnet had no
    /// `dn=`. Used by the frontend to populate `MagnetRow.name` so
    /// the paste-magnet flow can show per-row JAV codes instead of
    /// falling back to the synthetic group code "(直接貼上 N)".
    #[serde(default)]
    pub name: String,
    #[serde(default)]
    pub deduped: bool,
}

#[derive(Debug, Clone, Serialize)]
pub struct RegisterMagnetsResult {
    pub registered: Vec<RegisteredMagnet>,
    pub invalid: Vec<String>,
}

/// Register raw magnet URIs into the sidecar's handle table. The frontend
/// uses this for the "paste magnet → send to RD" path (no JavDB scrape
/// involved). Returns one redacted handle per input magnet plus a list of
/// inputs that didn't start with `magnet:`.
///
/// Full magnet text only crosses the IPC boundary in the inbound direction;
/// nothing in the response carries a complete magnet URI.
#[tauri::command]
pub async fn register_magnets(
    sidecar: State<'_, SidecarManager>,
    magnets: Vec<String>,
) -> Result<RegisterMagnetsResult, String> {
    let resp = sidecar
        .request("register_magnets", json!({ "magnets": magnets }))
        .await?;
    ensure_ok(&resp)?;

    let registered = resp
        .get("registered")
        .cloned()
        .unwrap_or(json!([]));
    let invalid = resp.get("invalid").cloned().unwrap_or(json!([]));

    let registered: Vec<RegisteredMagnet> =
        serde_json::from_value(registered).map_err(|e| e.to_string())?;
    let invalid: Vec<String> =
        serde_json::from_value(invalid).map_err(|e| e.to_string())?;

    Ok(RegisterMagnetsResult { registered, invalid })
}

/// Drop the sidecar's magnet handle table for the given ids (or all of
/// them when called with `None`). Used when the UI clears the result tree
/// so the sidecar doesn't pile up stale handles for entries the frontend
/// can never address again.
#[tauri::command]
pub async fn forget_magnets(
    sidecar: State<'_, SidecarManager>,
    handle_ids: Option<Vec<String>>,
) -> Result<u64, String> {
    let payload = match handle_ids {
        Some(ids) => json!({ "handle_ids": ids }),
        None => Value::Null,
    };
    let resp = sidecar.request("forget_magnets", payload).await?;
    Ok(resp
        .get("forgot")
        .or_else(|| resp.get("forgotten"))
        .and_then(|n| n.as_u64())
        .unwrap_or(0))
}

#[tauri::command]
pub async fn copy_magnets_bulk(
    app: AppHandle,
    sidecar: State<'_, SidecarManager>,
    handle_ids: Vec<String>,
) -> Result<CopyBulkResult, String> {
    let resp = sidecar
        .request("resolve_magnets", json!({ "handle_ids": handle_ids }))
        .await?;
    if !resp.get("ok").and_then(|v| v.as_bool()).unwrap_or(false) {
        return Err("resolve_magnets failed".to_string());
    }

    let magnets_arr = resp
        .get("magnets")
        .and_then(|m| m.as_array())
        .cloned()
        .unwrap_or_default();
    let unknown_arr = resp
        .get("unknown")
        .and_then(|u| u.as_array())
        .cloned()
        .unwrap_or_default();

    let lines: Vec<String> = magnets_arr
        .iter()
        .filter_map(|m| m.get("magnet").and_then(|s| s.as_str()).map(String::from))
        .collect();
    let copied = lines.len();
    let unknown = unknown_arr.len();

    if !lines.is_empty() {
        let joined = lines.join("\n");
        app.clipboard()
            .write_text(joined)
            .map_err(|e| e.to_string())?;
    }
    // `lines` and `joined` drop here; never returned, never logged.

    Ok(CopyBulkResult { copied, unknown })
}

/// Result of `copy_rd_links_bulk`. Only `copied` is exposed — Rust filters
/// out empty/whitespace-only entries silently so callers see the post-filter
/// count, which is what the UI status message wants.
#[derive(Serialize)]
pub struct CopyRdLinksBulkResult {
    pub copied: usize,
}

/// Write a batch of Real-Debrid direct-download URLs to the OS clipboard,
/// one per line. Mirrors `copy_magnets_bulk` so the frontend never needs
/// to import `tauri-plugin-clipboard-manager` directly. RD direct links
/// are not secrets (the frontend already holds them in `RdSendProgress`),
/// but routing through Rust keeps the capability surface minimal and the
/// "frontend doesn't touch clipboard plugins" invariant intact.
///
/// Empty input is a no-op: returns `copied = 0` without error so the UI
/// can present a "nothing to copy" message uniformly. Links are NOT logged.
#[tauri::command]
pub async fn copy_rd_links_bulk(
    app: AppHandle,
    links: Vec<String>,
) -> Result<CopyRdLinksBulkResult, String> {
    let filtered: Vec<String> = links
        .into_iter()
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .collect();
    let copied = filtered.len();
    if copied == 0 {
        return Ok(CopyRdLinksBulkResult { copied: 0 });
    }
    let joined = filtered.join("\n");
    app.clipboard()
        .write_text(joined)
        .map_err(|e| e.to_string())?;
    // `filtered` and `joined` drop here.
    Ok(CopyRdLinksBulkResult { copied })
}

// ===========================================================================
// M5: Real-Debrid commands
//
// Token storage:
//   - The token lives in the OS credential store (see secret_store.rs).
//   - rd_save_token writes the credential AND pushes it to the sidecar via
//     rd_set_token, so a sidecar restart isn't required.
//   - The frontend never gets the token back; it only sees rd_has_token's
//     boolean and rd_check_user's account snapshot.
//
// Pending state:
//   - <data_dir>/pending_torrents.json (see pending.rs).
//   - Magnet text NEVER persisted (security model).
// ===========================================================================

fn _err_code(resp: &Value) -> String {
    resp.get("error")
        .and_then(|e| e.get("code"))
        .and_then(|c| c.as_str())
        .unwrap_or("unknown")
        .to_string()
}

/// Guard for the standard `{"ok": bool, ...}` sidecar response shape.
/// Returns `Ok(())` when `ok == true`, otherwise propagates the sidecar's
/// error code via [`_err_code`]. Error string is byte-identical to the
/// inlined `return Err(_err_code(&resp))` it replaces.
fn ensure_ok(resp: &Value) -> Result<(), String> {
    if resp.get("ok").and_then(|v| v.as_bool()).unwrap_or(false) {
        Ok(())
    } else {
        Err(_err_code(resp))
    }
}

/// Read a string field off a sidecar response with the codebase's standard
/// fallback (`""` when missing or not a string). Mirrors the inlined
/// `resp.get(key).and_then(|s| s.as_str()).unwrap_or("").to_string()` chain.
fn str_field(resp: &Value, key: &str) -> String {
    resp.get(key).and_then(|v| v.as_str()).unwrap_or("").to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RdUserInfo {
    #[serde(default)]
    pub username: String,
    #[serde(default, rename = "type")]
    pub r#type: String,
    #[serde(default)]
    pub expiration: String,
    #[serde(default)]
    pub points: i64,
}

#[derive(Serialize)]
pub struct RdHasTokenResult {
    pub present: bool,
}

#[tauri::command]
pub async fn rd_has_token() -> Result<RdHasTokenResult, String> {
    let present = secret_store::get_rd_token()?.is_some();
    Ok(RdHasTokenResult { present })
}

/// Validate a candidate token without persisting it. Used by the settings
/// dialog's "test connection" affordance.
#[tauri::command]
pub async fn rd_test_token(
    sidecar: State<'_, SidecarManager>,
    token: String,
) -> Result<RdUserInfo, String> {
    if token.is_empty() {
        return Err("rd_no_token".to_string());
    }
    let resp = sidecar
        .request("rd_user", json!({ "token": token }))
        .await?;
    ensure_ok(&resp)?;
    let user = resp.get("user").cloned().unwrap_or(Value::Null);
    let info: RdUserInfo = serde_json::from_value(user).map_err(|e| e.to_string())?;
    Ok(info)
}

/// Persist a token to the credential store + push to the running sidecar.
///
/// Format validation lives in [`secret_store::is_valid_rd_token`] so every
/// path that writes the credential store applies the same rule (F-04).
/// We pre-check here for an immediate user-facing error code; `set_rd_token`
/// itself also revalidates as a belt-and-suspenders guard.
#[tauri::command]
pub async fn rd_save_token(
    sidecar: State<'_, SidecarManager>,
    token: String,
) -> Result<(), String> {
    if !token.is_empty() && !secret_store::is_valid_rd_token(&token) {
        return Err(secret_store::RD_TOKEN_FORMAT_ERR.to_string());
    }
    secret_store::set_rd_token(&token)?;
    let payload: Value = if token.is_empty() {
        json!({ "token": Value::Null })
    } else {
        json!({ "token": token })
    };
    let resp = sidecar.request("rd_set_token", payload).await?;
    ensure_ok(&resp)?;
    // The local `token` String drops here; the only persisted copy is in
    // the credential store and the sidecar's in-memory state.
    Ok(())
}

#[tauri::command]
pub async fn rd_clear_token(sidecar: State<'_, SidecarManager>) -> Result<(), String> {
    secret_store::delete_rd_token()?;
    let resp = sidecar
        .request("rd_set_token", json!({ "token": Value::Null }))
        .await?;
    ensure_ok(&resp)?;
    Ok(())
}

/// Account snapshot for a token already saved in the credential store.
/// Returns the same shape as rd_test_token; separate command so the UI
/// can avoid sending the secret across IPC just to refresh the display.
#[tauri::command]
pub async fn rd_check_user(sidecar: State<'_, SidecarManager>) -> Result<RdUserInfo, String> {
    let resp = sidecar.request("rd_user", Value::Null).await?;
    ensure_ok(&resp)?;
    let user = resp.get("user").cloned().unwrap_or(Value::Null);
    let info: RdUserInfo = serde_json::from_value(user).map_err(|e| e.to_string())?;
    Ok(info)
}

#[derive(Default, Deserialize)]
pub struct RdSendOptions {
    pub strategy: Option<String>,
    pub min_size_mb: Option<u32>,
    pub cache_wait: Option<u32>,
    /// Display-only metadata so a "pending" outcome can be persisted with
    /// the JavDB code/size label (sidecar doesn't know these).
    pub code: Option<String>,
    pub size_label: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RdLink {
    pub original: String,
    pub download: String,
    pub filename: String,
    #[serde(default)]
    pub filesize: i64,
    #[serde(default)]
    pub streamable: i64,
}

#[derive(Serialize)]
#[serde(tag = "status", rename_all = "snake_case")]
pub enum RdSendOutcome {
    Completed {
        torrent_id: String,
        name: String,
        links: Vec<RdLink>,
    },
    Pending {
        torrent_id: String,
        name: String,
        rd_status: String,
        progress: f64,
    },
}

/// Send one magnet (by handle_id) to RD. Returns either the unrestricted
/// links (cache hit / quick cache) or a Pending outcome. In the pending
/// case the entry is also persisted to pending_torrents.json so the
/// frontend's "retry" loop can find it on next launch.
#[tauri::command]
pub async fn rd_send_magnet(
    sidecar: State<'_, SidecarManager>,
    path_manager: State<'_, PathManager>,
    handle_id: String,
    options: Option<RdSendOptions>,
) -> Result<RdSendOutcome, String> {
    let opts = options.unwrap_or_default();

    let mut payload = json!({ "handle_id": handle_id });
    if let Some(s) = &opts.strategy {
        payload["strategy"] = json!(s);
    }
    if let Some(n) = opts.min_size_mb {
        payload["min_size_mb"] = json!(n);
    }
    if let Some(n) = opts.cache_wait {
        payload["cache_wait"] = json!(n);
    }

    let resp = sidecar.request("rd_send_magnet", payload).await?;
    ensure_ok(&resp)?;

    let status = resp
        .get("status")
        .and_then(|s| s.as_str())
        .unwrap_or("");
    let torrent_id = str_field(&resp, "torrent_id");
    let name = str_field(&resp, "name");

    if status == "completed" {
        let links_val = resp.get("links").cloned().unwrap_or(json!([]));
        let links: Vec<RdLink> =
            serde_json::from_value(links_val).map_err(|e| e.to_string())?;
        return Ok(RdSendOutcome::Completed {
            torrent_id,
            name,
            links,
        });
    }

    // Pending: persist to disk so the frontend can rebuild its retry
    // queue on next launch.
    let rd_status = str_field(&resp, "rd_status");
    let progress = resp
        .get("progress")
        .and_then(|n| n.as_f64())
        .unwrap_or(0.0);
    let strategy_used = resp
        .get("strategy")
        .and_then(|s| s.as_str())
        .unwrap_or("smart")
        .to_string();

    let mut entry = PendingEntry::new(
        torrent_id.clone(),
        opts.code.unwrap_or_default(),
        name.clone(),
        opts.size_label.unwrap_or_default(),
        strategy_used,
    );
    entry.last_rd_status = rd_status.clone();
    entry.last_progress = progress;
    pending::add(&path_manager.data_dir, entry)?;

    Ok(RdSendOutcome::Pending {
        torrent_id,
        name,
        rd_status,
        progress,
    })
}

#[derive(Serialize)]
#[serde(tag = "status", rename_all = "snake_case")]
pub enum RdCheckOutcome {
    Completed {
        torrent_id: String,
        name: String,
        links: Vec<RdLink>,
    },
    Pending {
        torrent_id: String,
        name: String,
        rd_status: String,
        progress: f64,
    },
    Missing {
        torrent_id: String,
    },
}

/// Re-poll a previously-pending torrent. Always updates pending_torrents.json:
///   - on `completed` or `missing` → entry removed.
///   - on `pending` → entry's last_progress / last_rd_status / last_checked_at refreshed.
#[tauri::command]
pub async fn rd_check_pending(
    sidecar: State<'_, SidecarManager>,
    path_manager: State<'_, PathManager>,
    torrent_id: String,
    strategy: Option<String>,
) -> Result<RdCheckOutcome, String> {
    let mut payload = json!({ "torrent_id": torrent_id });
    if let Some(s) = strategy {
        payload["strategy"] = json!(s);
    }
    let resp = sidecar.request("rd_check_pending", payload).await?;
    ensure_ok(&resp)?;

    let status = resp.get("status").and_then(|s| s.as_str()).unwrap_or("");
    if status == "completed" {
        // Persisted entry no longer needed.
        pending::remove(&path_manager.data_dir, &torrent_id)?;
        let name = str_field(&resp, "name");
        let links_val = resp.get("links").cloned().unwrap_or(json!([]));
        let links: Vec<RdLink> =
            serde_json::from_value(links_val).map_err(|e| e.to_string())?;
        return Ok(RdCheckOutcome::Completed {
            torrent_id,
            name,
            links,
        });
    }
    if status == "missing" {
        pending::remove(&path_manager.data_dir, &torrent_id)?;
        return Ok(RdCheckOutcome::Missing { torrent_id });
    }

    // pending — refresh persisted snapshot
    let name = str_field(&resp, "name");
    let rd_status = str_field(&resp, "rd_status");
    let progress = resp
        .get("progress")
        .and_then(|n| n.as_f64())
        .unwrap_or(0.0);
    pending::update_status(&path_manager.data_dir, &torrent_id, &rd_status, progress)?;
    Ok(RdCheckOutcome::Pending {
        torrent_id,
        name,
        rd_status,
        progress,
    })
}

#[tauri::command]
pub async fn pending_list(
    path_manager: State<'_, PathManager>,
) -> Result<Vec<PendingEntry>, String> {
    pending::load(&path_manager.data_dir)
}

#[tauri::command]
pub async fn pending_remove(
    path_manager: State<'_, PathManager>,
    torrent_id: String,
) -> Result<Vec<PendingEntry>, String> {
    pending::remove(&path_manager.data_dir, &torrent_id)
}

#[tauri::command]
pub async fn pending_clear(path_manager: State<'_, PathManager>) -> Result<(), String> {
    pending::clear(&path_manager.data_dir)
}

// ===========================================================================
// M7a-lite: Manual legacy data import
//
// Both commands require an explicit `source_dir` from the user. There is
// NO auto-discovery on app launch. The `get_legacy_default_dir` command
// exists purely so dev/test runs can pre-fill the input via the
// JAVDB_LEGACY_IMPORT_DIR environment variable; the value is never read
// without an explicit user action ("preview" / "apply" button).
// ===========================================================================

/// Returns the value of `JAVDB_LEGACY_IMPORT_DIR` if set, else empty
/// string. Used by the frontend to pre-fill the legacy-import path
/// input during dev/test. No file I/O.
#[tauri::command]
pub fn get_legacy_default_dir() -> String {
    std::env::var("JAVDB_LEGACY_IMPORT_DIR").unwrap_or_default()
}

#[tauri::command]
pub fn preview_legacy_import(source_dir: String) -> Result<LegacyImportPreview, String> {
    let trimmed = source_dir.trim();
    if trimmed.is_empty() {
        return Err("source_dir is empty".to_string());
    }
    Ok(legacy_import::preview(std::path::Path::new(trimmed)))
}

#[tauri::command]
pub async fn apply_legacy_import(
    app: AppHandle,
    path_manager: State<'_, PathManager>,
    sidecar: State<'_, SidecarManager>,
    source_dir: String,
) -> Result<LegacyImportReport, String> {
    let src = validate_legacy_source(&source_dir, &path_manager.data_dir)?;

    let mut report = LegacyImportReport::default();
    let preview = legacy_import::preview(&src);
    report.warnings.extend(preview.warnings.clone());

    if preview.env_present {
        import_env_block(&app, &path_manager.data_dir, &sidecar, &src, &mut report).await;
    }
    if preview.cookies_present {
        import_cookies_block(&path_manager.data_dir, &src, &mut report);
    }
    if preview.pending_present {
        import_pending_block(&path_manager.data_dir, &src, &mut report);
    }

    Ok(report)
}

/// Validate `source_dir` for `apply_legacy_import`: non-empty, a real
/// directory, and not the app data dir (which would degenerate into a
/// self-copy).
fn validate_legacy_source(source_dir: &str, data_dir: &Path) -> Result<PathBuf, String> {
    let trimmed = source_dir.trim();
    if trimmed.is_empty() {
        return Err("source_dir is empty".to_string());
    }
    let src = Path::new(trimmed);
    if !src.is_dir() {
        return Err(format!("source_dir is not a directory: {}", src.display()));
    }
    let same_as_data = src
        .canonicalize()
        .ok()
        .and_then(|s| data_dir.canonicalize().ok().map(|d| s == d))
        .unwrap_or(false);
    if same_as_data {
        return Err("source_dir must not be the app data directory".to_string());
    }
    Ok(src.to_path_buf())
}

/// Read `.env` from `src`, parse it, then route the optional RD token to
/// the credential store / sidecar and the non-secret settings patch to
/// the tauri-plugin-store. All failures are appended to `report.warnings`.
async fn import_env_block(
    app: &AppHandle,
    data_dir: &Path,
    sidecar: &SidecarManager,
    src: &Path,
    report: &mut LegacyImportReport,
) {
    let raw = match std::fs::read_to_string(src.join(legacy_import::LEGACY_ENV_FILE)) {
        Ok(s) => s,
        Err(e) => {
            report.warnings.push(format!("read .env failed: {e}"));
            return;
        }
    };
    let parsed = legacy_import::parse_env(&raw);
    report
        .warnings
        .extend(parsed.warnings.iter().map(|w| format!(".env: {w}")));

    if let Some(token) = parsed.token.as_deref() {
        import_rd_token(sidecar, src, token, report).await;
    }
    if !parsed.settings_patch.is_empty() {
        import_env_settings_patch(app, data_dir, src, &parsed.settings_patch, report);
    }
}

/// Pre-validation for a legacy RD token before any side effect. Returns
/// `Ok(())` if the value matches the Real-Debrid token format, otherwise
/// the warning string that should land in [`LegacyImportReport::warnings`].
/// Pure function — testable without touching the credential store or
/// sidecar.
pub(crate) fn validate_legacy_rd_token(token: &str) -> Result<(), String> {
    if secret_store::is_valid_rd_token(token) {
        Ok(())
    } else {
        Err(
            "ignored legacy RD_API_TOKEN: value does not match the Real-Debrid \
             API token format (expected ≤255 ASCII alphanumeric chars); \
             credential store and sidecar left untouched"
                .to_string(),
        )
    }
}

/// Hand a recovered `RD_API_TOKEN` to the credential store and ask the
/// running sidecar to use it. Never written into settings.json.
///
/// A malformed value short-circuits BEFORE the credential store or
/// sidecar see it: otherwise we'd end up in a half-success state where
/// the keyring held a dirty token but `rd_token_imported` stayed
/// `false`, and the next sidecar restart would pick up the dirty value
/// from the keyring at handshake time (F-04 cross-path leak).
async fn import_rd_token(
    sidecar: &SidecarManager,
    src: &Path,
    token: &str,
    report: &mut LegacyImportReport,
) {
    if let Err(msg) = validate_legacy_rd_token(token) {
        report.warnings.push(msg);
        // rd_token_imported stays at its default `false`; do not append
        // to `sources` since nothing was imported.
        return;
    }
    if let Err(e) = secret_store::set_rd_token(token) {
        report.warnings.push(format!("credential store: {e}"));
        return;
    }
    let resp = match sidecar.request("rd_set_token", json!({ "token": token })).await {
        Ok(r) => r,
        Err(e) => {
            report.warnings.push(format!("sidecar: {e}"));
            return;
        }
    };
    if resp.get("ok").and_then(Value::as_bool).unwrap_or(false) {
        report.rd_token_imported = true;
        report
            .sources
            .push(format!("{}/.env (RD_API_TOKEN)", src.display()));
    } else {
        report
            .warnings
            .push(format!("sidecar rd_set_token: {}", _err_code(&resp)));
    }
}

/// Merge a non-secret `.env` settings patch into the tauri-plugin-store
/// settings.json. Always blanks `rd.api_token` belt-and-suspenders.
fn import_env_settings_patch(
    app: &AppHandle,
    data_dir: &Path,
    src: &Path,
    patch: &Map<String, Value>,
    report: &mut LegacyImportReport,
) {
    let store_path = data_dir.join(crate::STORE_FILE);
    let store = match app.store(&store_path) {
        Ok(s) => s,
        Err(e) => {
            report.warnings.push(format!("settings store: {e}"));
            return;
        }
    };
    let mut base = store.get("settings").unwrap_or_else(|| {
        serde_json::to_value(crate::settings::Settings::default()).unwrap_or(Value::Null)
    });
    legacy_import::apply_settings_patch(&mut base, patch);
    blank_rd_api_token(&mut base);
    store.set("settings", base);
    if let Err(e) = store.save() {
        report.warnings.push(format!("settings save: {e}"));
        return;
    }
    report.env_imported = true;
    report
        .sources
        .push(format!("{}/.env (settings)", src.display()));
}

/// Force `settings.rd.api_token` to an empty string in-place, regardless
/// of whether the field was present before. Used as a defensive sweep
/// before we save settings.json so a future patch can never reintroduce
/// the token into the on-disk settings.
fn blank_rd_api_token(settings: &mut Value) {
    if let Some(rd) = settings.get_mut("rd").and_then(Value::as_object_mut) {
        if let Some(t) = rd.get_mut("api_token") {
            *t = Value::String(String::new());
        }
    }
}

/// Copy `cookies.txt` from `src` into the data dir, refusing to copy a
/// file onto itself when the user pointed at data_dir.
fn import_cookies_block(data_dir: &Path, src: &Path, report: &mut LegacyImportReport) {
    let src_cookies = src.join(legacy_import::LEGACY_COOKIES_FILE);
    let dst_cookies = data_dir.join(legacy_import::LEGACY_COOKIES_FILE);
    if let Err(e) = std::fs::create_dir_all(data_dir) {
        report.warnings.push(format!("mkdir data_dir: {e}"));
    }
    let same = src_cookies
        .canonicalize()
        .ok()
        .and_then(|s| dst_cookies.canonicalize().ok().map(|d| s == d))
        .unwrap_or(false);
    if same {
        report
            .warnings
            .push("cookies.txt: source and destination are the same path".into());
        return;
    }
    match std::fs::copy(&src_cookies, &dst_cookies) {
        Ok(_) => {
            report.cookies_imported = true;
            // The running sidecar received its cookies during the
            // startup handshake and does not re-read cookies.txt.
            // Keep this as an explicit report warning instead of
            // silently implying the new JavDB session is live now.
            report.warnings.push(
                "cookies.txt imported; restart the app before JavDB fetch uses the new cookies"
                    .into(),
            );
            report
                .sources
                .push(format!("{}/cookies.txt", src.display()));
        }
        Err(e) => report.warnings.push(format!("cookies copy: {e}")),
    }
}

/// Read the legacy `pending_torrents.json`, merge it against the current
/// pending store, and persist the result. Each step is an early-return
/// on error so the function stays flat.
fn import_pending_block(data_dir: &Path, src: &Path, report: &mut LegacyImportReport) {
    let src_pending = src.join(legacy_import::LEGACY_PENDING_FILE);
    let raw = match std::fs::read_to_string(&src_pending) {
        Ok(r) => r,
        Err(e) => {
            report.warnings.push(format!("read pending JSON failed: {e}"));
            return;
        }
    };
    let existing = match pending::load(data_dir) {
        Ok(e) => e,
        Err(e) => {
            report.warnings.push(format!("pending load (existing): {e}"));
            return;
        }
    };
    let (merged, imported, skipped) = match legacy_import::merge_legacy_pending(&raw, &existing) {
        Ok(tuple) => tuple,
        Err(e) => {
            report.warnings.push(format!("pending merge: {e}"));
            return;
        }
    };
    match pending::save(data_dir, &merged) {
        Ok(_) => {
            report.pending_imported = imported;
            report.pending_skipped = skipped;
            report
                .sources
                .push(format!("{}/pending_torrents.json", src.display()));
        }
        Err(e) => report.warnings.push(format!("pending save: {e}")),
    }
}

// ===========================================================================
// M7b: Cookies status + data/logs dir helpers
//
// Cookies are stored plaintext at <data_dir>/cookies.txt. The UI must be
// able to surface presence / size / mtime so the user knows whether the
// app has any session at all — but the cookie BODY must never leave Rust
// (don't read the file contents, don't echo to logs).
// ===========================================================================

const COOKIES_FILE_NAME: &str = "cookies.txt";

#[derive(Debug, Clone, Serialize)]
pub struct CookiesStatus {
    pub present: bool,
    pub path: String,
    /// ISO-8601 UTC string. `None` if the cookies live in the credential
    /// store, the file is missing, or the OS doesn't give us mtime (e.g.
    /// exotic filesystem).
    pub modified_iso: Option<String>,
    pub size_bytes: u64,
    /// Where the cookies actually live.
    ///
    /// - `"none"` — nothing configured; UI shows "create template".
    /// - `"file"` — plaintext `cookies.txt` present (legacy; will be
    ///   migrated to the credential store on next handshake).
    /// - `"keyring"` — Windows Credential Manager (post-migration steady state).
    pub storage: String,
}

/// Pure helper — reports cookies.txt status WITHOUT reading the file
/// contents (only `metadata`). Used by both the Tauri command and the
/// unit tests. The cookie BODY never crosses this boundary.
///
/// Reporting precedence:
///   1. File exists → `storage: "file"` with size + mtime. This is the
///      transient state after a user just pasted cookies; the next
///      handshake migrates it to the credential store.
///   2. `in_keyring == true` → `storage: "keyring"`, `present: true`,
///      no mtime/size (the OS keyring doesn't expose them).
///   3. Neither → `storage: "none"`, `present: false`.
///
/// `in_keyring` is passed in as a bool so unit tests don't have to touch
/// the real OS credential store (which would otherwise see real cookies
/// from a developer machine and break test determinism). The public
/// [`cookies_status_for`] wrapper queries the keyring for production
/// callers.
pub(crate) fn cookies_status_with_keyring(
    data_dir: &std::path::Path,
    in_keyring: bool,
) -> CookiesStatus {
    let path = data_dir.join(COOKIES_FILE_NAME);
    let path_display = path.display().to_string();

    if let Ok(meta) = std::fs::metadata(&path) {
        let modified_iso = meta
            .modified()
            .ok()
            .map(|st| chrono::DateTime::<chrono::Utc>::from(st).to_rfc3339());
        return CookiesStatus {
            present: true,
            path: path_display,
            modified_iso,
            size_bytes: meta.len(),
            storage: "file".to_string(),
        };
    }

    CookiesStatus {
        present: in_keyring,
        path: path_display,
        modified_iso: None,
        size_bytes: 0,
        storage: if in_keyring { "keyring".to_string() } else { "none".to_string() },
    }
}

pub(crate) fn cookies_status_for(data_dir: &std::path::Path) -> CookiesStatus {
    // A keyring backend error is treated the same as "no entry": we never
    // want a transient credential-store failure to hide the fact that the
    // user can still create a fresh template.
    let in_keyring = matches!(
        crate::cookie_store::get_cookies(),
        Ok(Some(ref s)) if !s.is_empty()
    );
    cookies_status_with_keyring(data_dir, in_keyring)
}

#[tauri::command]
pub fn get_cookies_status(path_manager: State<PathManager>) -> CookiesStatus {
    cookies_status_for(&path_manager.data_dir)
}

/// "重新整理 / 套用變更" — run the same file→keyring→delete migration
/// that happens at startup, but on demand and with a live push to the
/// running sidecar (no app restart needed for the new cookies to take
/// effect on the next JavDB fetch).
///
/// Returns the post-migration [`CookiesStatus`] so the UI can re-render
/// directly without a second IPC round-trip.
///
/// Behaviour matrix:
///   - file with real cookie content → keyring write + file delete + sidecar push
///   - file with only the template scaffold → unchanged; status stays `"file"`
///   - file > 64 KiB → rejected (still left on disk for the user to inspect)
///   - no file → falls through to the credential-store snapshot
///
/// Errors from keyring write surface to the caller, but a successful
/// keyring write followed by a failed sidecar push is also reported as
/// an error so the user knows the running session is stale; the file is
/// already deleted by that point so a follow-up "重新整理" will report
/// `storage: "keyring"` and the user can decide whether to restart.
#[tauri::command]
pub async fn migrate_cookies_now(
    sidecar: State<'_, SidecarManager>,
    path_manager: State<'_, PathManager>,
) -> Result<CookiesStatus, String> {
    let cookies_path = path_manager.data_dir.join(COOKIES_FILE_NAME);
    if let Some(migrated) = crate::migrate_cookies_from_file(&cookies_path) {
        push_cookies_to_sidecar(&sidecar, &migrated).await?;
    }
    Ok(cookies_status_for(&path_manager.data_dir))
}

/// Pure validation for [`save_cookies`]. Returns the trimmed value on
/// success or a stable error code:
///   - `"cookies_empty"` — whitespace-only / empty input (the UI's paste
///     box can't infer intent from blank text; refuse here so the caller
///     gets a deterministic error instead of a silent no-op).
///   - [`cookie_store::COOKIES_TOO_LARGE_ERR`] — over the 64 KiB cap.
///
/// Extracted so tests can exercise the rule without touching the OS
/// credential store or the sidecar (which would otherwise need a full
/// Tauri State harness to instantiate).
pub(crate) fn validate_cookies_input(cookies: &str) -> Result<String, String> {
    let trimmed = cookies.trim().to_string();
    if trimmed.is_empty() {
        return Err("cookies_empty".to_string());
    }
    crate::cookie_store::check_cookies_format(&trimmed)?;
    Ok(trimmed)
}

/// Pure helper for [`save_cookies`]: runs validation, persists to the
/// keyring, and removes any stale `cookies.txt` next to the credential
/// store. Returns the trimmed value that was actually stored.
///
/// Extracted so integration tests can verify the keyring + file
/// invariants without standing up a [`SidecarManager`] (which would
/// need a live Tauri app harness). The sidecar push is the caller's
/// responsibility — see [`save_cookies`].
pub(crate) fn save_cookies_local(
    data_dir: &Path,
    cookies: &str,
) -> Result<String, String> {
    let trimmed = validate_cookies_input(cookies)?;
    crate::cookie_store::set_cookies(&trimmed)?;
    // Best-effort: nuke any stale plaintext so the next startup doesn't
    // re-migrate an older file over our fresh keyring value.
    let stale = data_dir.join(COOKIES_FILE_NAME);
    let _ = std::fs::remove_file(&stale);
    Ok(trimmed)
}

/// Direct paste path: take a cookie header string from the UI, validate
/// length, write to the credential store, scrub any stale `cookies.txt`,
/// and push to the running sidecar so the new value is live immediately.
///
/// Empty / whitespace input is rejected (no silent clears via this
/// command; use a dedicated clear gesture if one is ever needed).
#[tauri::command]
pub async fn save_cookies(
    sidecar: State<'_, SidecarManager>,
    path_manager: State<'_, PathManager>,
    cookies: String,
) -> Result<CookiesStatus, String> {
    let trimmed = save_cookies_local(&path_manager.data_dir, &cookies)?;
    push_cookies_to_sidecar(&sidecar, &trimmed).await?;
    Ok(cookies_status_for(&path_manager.data_dir))
}

/// Shared helper: push a cookie header to the running sidecar via the
/// `set_cookies` protocol command. Surfaces the sidecar's error code on
/// failure so the UI can show a stable string.
async fn push_cookies_to_sidecar(
    sidecar: &SidecarManager,
    value: &str,
) -> Result<(), String> {
    let resp = sidecar
        .request("set_cookies", json!({ "cookies": value }))
        .await?;
    ensure_ok(&resp)?;
    Ok(())
}

/// Body of the generated cookies.txt scaffold. Inline instructions
/// only — no real cookies, ever. Stored as a Rust constant so the
/// audit (and the no-secret-in-source scan) sees it.
const COOKIES_TEMPLATE: &str = "# JavDBMagnet cookies.txt\n# ================================================\n#\n# 把你的 JavDB 登入 cookie 貼到本檔最後一行，存檔時請選 UTF-8 編碼。\n# 至少要包含這 2 個 cookie:\n#   _jdb_session=...   (登入 session)\n#   cf_clearance=...   (Cloudflare 通行證)\n#\n# === 方法 A: 瀏覽器 DevTools Network 分頁 (推薦) ===\n#   1. 用瀏覽器 (Edge / Chrome / Firefox 都可) 登入 https://javdb.com\n#   2. 按 F12 開啟 DevTools\n#   3. 切換到「Network」(網路) 分頁\n#   4. 按 F5 重新整理頁面\n#   5. 點清單最上面那筆 request (網址通常是 javdb.com/)\n#   6. 右側找到「Request Headers」找到 \"Cookie:\" 那行\n#   7. 複製整行值 (不要包含 \"Cookie: \" 前綴), 貼到本檔最後一行\n#\n# === 方法 B: Application 分頁 (更直觀但要拼接) ===\n#   1. F12 → Application → Storage → Cookies → https://javdb.com\n#   2. 找出 _jdb_session 與 cf_clearance 兩個欄位的 Value\n#   3. 自行拼成: _jdb_session=...; cf_clearance=...; locale=zh\n#\n# === 範例 (請把 XXX 換成你的真實值, 不要直接貼這行) ===\n# _jdb_session=XXX; cf_clearance=XXX; locale=zh\n#\n# === 安全提醒 ===\n#   - cookies.txt 含登入憑證, 請勿分享, 勿同步雲端\n#   - cf_clearance 約幾小時過期 → 重做上面任一方法更新即可\n#   - 失效徵兆: app 內按「開始擷取」看到「Cloudflare 阻擋」訊息\n#\n# === 在下面貼上你的 cookie 整行 ===\n\n";

/// Write a freshly-instructed cookies.txt scaffold into the data dir
/// so new users have something concrete to edit (instead of having to
/// know the schema). Refuses to overwrite an existing file — losing a
/// working cookies.txt would be far worse than failing the create
/// action. Caller is expected to refresh `get_cookies_status` after.
///
/// File is written UTF-8 without BOM so Cloudflare's parser doesn't
/// trip on a leading BOM byte.
pub(crate) fn write_cookies_template_to(data_dir: &std::path::Path) -> Result<(), String> {
    let path = data_dir.join(COOKIES_FILE_NAME);
    if path.exists() {
        return Err(
            "cookies.txt 已存在，建立範本前請先在資料目錄手動移除".to_string(),
        );
    }
    std::fs::create_dir_all(data_dir)
        .map_err(|e| format!("mkdir {}: {e}", data_dir.display()))?;
    // Bytes path: no BOM, ASCII+UTF-8 content as-is.
    std::fs::write(&path, COOKIES_TEMPLATE.as_bytes())
        .map_err(|e| format!("write {}: {e}", path.display()))?;
    Ok(())
}

#[tauri::command]
pub fn create_cookies_template(path_manager: State<PathManager>) -> Result<(), String> {
    write_cookies_template_to(&path_manager.data_dir)
}

/// Push the latest persisted settings to the running sidecar so this
/// session reflects the change without an app restart. Caller is the
/// frontend's settings editor; the settings have already been validated
/// + saved via `write_settings`. We always force `rd.api_token` to ""
/// in the outgoing payload as a belt-and-suspenders rule even though
/// `write_settings`/`read_settings` already enforce it.
#[tauri::command]
pub async fn update_sidecar_settings(
    sidecar: State<'_, SidecarManager>,
    settings: Value,
) -> Result<(), String> {
    let mut sanitized = settings;
    blank_rd_api_token(&mut sanitized);
    let resp = sidecar
        .request("update_settings", json!({ "settings": sanitized }))
        .await?;
    ensure_ok(&resp)?;
    Ok(())
}

/// Open the configured data directory in the OS file manager. Uses
/// `explorer.exe` directly so we don't need a new IPC capability for
/// `tauri-plugin-shell.open` — the call is Rust-side only.
#[tauri::command]
pub fn open_data_dir(path_manager: State<PathManager>) -> Result<(), String> {
    open_in_explorer(&path_manager.data_dir)
}

#[tauri::command]
pub fn open_logs_dir(path_manager: State<PathManager>) -> Result<(), String> {
    open_in_explorer(&path_manager.log_dir)
}

fn open_in_explorer(p: &std::path::Path) -> Result<(), String> {
    if !p.exists() {
        // Best-effort: create the dir so explorer has something to open.
        std::fs::create_dir_all(p)
            .map_err(|e| format!("mkdir {}: {e}", p.display()))?;
    }
    // `explorer.exe <path>` on Windows. Quoting is handled by the OS;
    // we pass the path as a single arg.
    #[cfg(target_os = "windows")]
    {
        std::process::Command::new("explorer.exe")
            .arg(p.as_os_str())
            .spawn()
            .map_err(|e| format!("spawn explorer: {e}"))?;
        Ok(())
    }
    #[cfg(not(target_os = "windows"))]
    {
        // Fallback for dev cross-checks. M7 targets Windows only.
        Err(format!(
            "open_in_explorer not implemented for this OS: {}",
            p.display()
        ))
    }
}

#[cfg(test)]
mod tests_m7b {
    use super::*;
    use std::env;
    use std::fs;
    use std::sync::atomic::{AtomicUsize, Ordering};

    fn temp_dir() -> std::path::PathBuf {
        static COUNTER: AtomicUsize = AtomicUsize::new(0);
        let id = COUNTER.fetch_add(1, Ordering::SeqCst);
        let dir = env::temp_dir().join(format!(
            "javdbmagnet-cookies-test-{}-{}",
            std::process::id(),
            id
        ));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    #[test]
    fn cookies_status_missing_file_and_no_keyring() {
        // Drive the keyring-injected helper so tests are deterministic on
        // a developer machine that has a real entry stored.
        let d = temp_dir();
        let s = cookies_status_with_keyring(&d, false);
        assert!(!s.present);
        assert_eq!(s.size_bytes, 0);
        assert!(s.modified_iso.is_none());
        assert_eq!(s.storage, "none");
        // path is still echoed so the UI can show "expected at ..."
        assert!(s.path.contains("cookies.txt"));
    }

    #[test]
    fn cookies_status_missing_file_but_keyring_populated() {
        // File migrated to the credential store, plaintext removed. The
        // status must still report present=true so the UI doesn't tell the
        // user to re-paste cookies they already have.
        let d = temp_dir();
        let s = cookies_status_with_keyring(&d, true);
        assert!(s.present);
        assert_eq!(s.storage, "keyring");
        assert!(s.modified_iso.is_none(), "keyring entries have no mtime");
        assert_eq!(s.size_bytes, 0);
    }

    #[test]
    fn cookies_status_file_overrides_keyring() {
        // If both file and keyring have cookies (e.g. user just pasted
        // fresh cookies before the next migration), report the file —
        // that's the user's most recent intent and the next handshake
        // will migrate it.
        let d = temp_dir();
        let path = d.join(COOKIES_FILE_NAME);
        fs::write(&path, "_jdb_session=new; cf_clearance=fresh\n").unwrap();
        let s = cookies_status_with_keyring(&d, true);
        assert!(s.present);
        assert_eq!(s.storage, "file");
        assert!(s.size_bytes > 0);
    }

    #[test]
    fn cookies_status_present_file() {
        let d = temp_dir();
        let path = d.join(COOKIES_FILE_NAME);
        fs::write(&path, "# domain\tdummy\tplaceholder=1\n").unwrap();
        let s = cookies_status_with_keyring(&d, false);
        assert!(s.present);
        assert_eq!(s.storage, "file");
        assert!(s.size_bytes > 0);
        // mtime is best-effort; accept None on exotic filesystems but
        // assert that an OK Some() looks like an ISO-8601 date.
        if let Some(iso) = &s.modified_iso {
            assert!(iso.len() >= 19, "iso too short: {iso}");
            assert!(iso.contains('T') || iso.contains(' '), "iso shape: {iso}");
        }
    }

    #[test]
    fn cookies_status_does_not_leak_body() {
        // Defense in depth: serializing the status should never contain
        // the cookies.txt body, even if a future refactor accidentally
        // adds it to the struct.
        let d = temp_dir();
        let path = d.join(COOKIES_FILE_NAME);
        fs::write(&path, "SECRET_COOKIE_VALUE_DO_NOT_LEAK\n").unwrap();
        let s = cookies_status_with_keyring(&d, false);
        let raw = serde_json::to_string(&s).unwrap();
        assert!(
            !raw.contains("SECRET_COOKIE_VALUE_DO_NOT_LEAK"),
            "cookies body leaked into status: {raw}"
        );
    }

    #[test]
    fn create_cookies_template_writes_utf8_no_bom() {
        let d = temp_dir();
        write_cookies_template_to(&d).expect("template write must succeed");
        let bytes = fs::read(d.join(COOKIES_FILE_NAME)).unwrap();
        // No UTF-8 BOM (Cloudflare's parser would trip on a leading BOM).
        assert!(bytes.len() >= 3);
        assert_ne!(
            &bytes[..3],
            &[0xEF, 0xBB, 0xBF],
            "template must not start with a UTF-8 BOM"
        );
        let text = String::from_utf8(bytes).expect("template must be valid UTF-8");
        // Inline-instructions sanity: the comment headers we promise to
        // ship must actually appear in the file.
        assert!(text.contains("JavDBMagnet cookies.txt"));
        assert!(text.contains("方法 A"));
        assert!(text.contains("方法 B"));
        assert!(text.contains("_jdb_session"));
        assert!(text.contains("cf_clearance"));
        // No real-looking secret pattern (XXX placeholder is fine).
        assert!(text.contains("_jdb_session=XXX"));
    }

    #[test]
    fn validate_legacy_rd_token_passes_valid_value() {
        // Sanity: the 52-char ASCII-alphanumeric shape that
        // `secret_store::is_valid_rd_token` accepts must also clear
        // the legacy-import gate.
        assert!(super::validate_legacy_rd_token(&"A".repeat(52)).is_ok());
    }

    #[test]
    fn validate_legacy_rd_token_rejects_with_warning_text() {
        // A malformed legacy token must produce a warning string that
        // names the field and tells the user nothing was written. The
        // exact wording is checked here so future refactors can't
        // accidentally drop the "credential store ... untouched"
        // promise that callers (and the report.warnings vec) rely on.
        let err =
            super::validate_legacy_rd_token("abc-123").expect_err("dash must fail");
        assert!(err.contains("RD_API_TOKEN"), "got: {err}");
        assert!(err.contains("credential store"), "got: {err}");
        assert!(err.contains("untouched"), "got: {err}");
        // And neither the dirty value nor any hint of its bytes leaks.
        assert!(!err.contains("abc-123"), "warning echoed dirty value: {err}");
    }

    #[test]
    fn validate_legacy_rd_token_rejects_overlong_and_non_ascii() {
        assert!(super::validate_legacy_rd_token(&"a".repeat(256)).is_err());
        assert!(super::validate_legacy_rd_token("ＡＢＣ123").is_err());
        // Empty also fails — caller in import_rd_token only ever invokes
        // us with a non-empty token (parse_env filters empty), but we
        // still encode the rule.
        assert!(super::validate_legacy_rd_token("").is_err());
    }

    #[test]
    fn validate_cookies_input_rejects_empty() {
        // The paste box can't infer intent from blank text — refuse with a
        // stable code instead of silently doing nothing.
        let err = super::validate_cookies_input("").expect_err("must reject empty");
        assert_eq!(err, "cookies_empty");
        let err = super::validate_cookies_input("   \n\t  ")
            .expect_err("must reject whitespace-only");
        assert_eq!(err, "cookies_empty");
    }

    #[test]
    fn validate_cookies_input_rejects_oversized() {
        // Mirrors check_cookies_format's contract — the >64KiB cap fires
        // before any keyring or sidecar touch can happen.
        use crate::cookie_store::{COOKIES_MAX_BYTES, COOKIES_TOO_LARGE_ERR};
        let huge = "a".repeat(COOKIES_MAX_BYTES + 1);
        let err = super::validate_cookies_input(&huge)
            .expect_err("must reject oversized cookies");
        assert_eq!(err, COOKIES_TOO_LARGE_ERR);
    }

    #[test]
    fn validate_cookies_input_trims_whitespace_around_real_value() {
        // Users frequently copy a Cookie: header with trailing newline or
        // padding spaces from DevTools. The validator must strip those
        // before pushing to keyring + sidecar so two visually-identical
        // pastes don't end up as different entries.
        let v = super::validate_cookies_input(
            "\n  _jdb_session=abc; cf_clearance=xyz  \n",
        )
        .expect("realistic paste must pass");
        assert_eq!(v, "_jdb_session=abc; cf_clearance=xyz");
    }

    #[test]
    fn create_cookies_template_refuses_overwrite() {
        let d = temp_dir();
        let existing_body = "ORIGINAL_USER_COOKIES_KEEP_INTACT";
        fs::write(d.join(COOKIES_FILE_NAME), existing_body).unwrap();

        let err = write_cookies_template_to(&d).expect_err("must refuse overwrite");
        assert!(
            err.contains("已存在"),
            "error should explain cookies.txt already exists; got: {err}"
        );
        // Original content untouched.
        let after = fs::read_to_string(d.join(COOKIES_FILE_NAME)).unwrap();
        assert_eq!(after, existing_body);
    }
}

// ---------------------------------------------------------------------------
// End-to-end keyring tests (Goal 1/2/3 acceptance)
//
// These tests touch the **real** OS credential store. To avoid clobbering a
// developer machine's actual `JavDBMagnet/JAVDB_COOKIES` entry we:
//   1. Serialise all keyring-touching tests behind a single Mutex
//      (cargo runs tests on multiple threads by default).
//   2. Snapshot the user's pre-test value, clear it, run the test, then
//      restore the snapshot in `Drop` so even a panicking test leaves the
//      keyring in the user's original state.
//
// A keyring backend that's missing (e.g. CI without a session) will surface
// as `set_cookies`/`get_cookies` errors — the sandbox propagates those so
// the test is recorded as failing rather than silently passing.
// ---------------------------------------------------------------------------

#[cfg(test)]
mod tests_cookies_e2e {
    use super::*;
    use std::env;
    use std::fs;
    use std::sync::atomic::{AtomicUsize, Ordering};
    use std::sync::{Mutex, MutexGuard, OnceLock};

    /// One global mutex so concurrent keyring tests don't race over the
    /// shared `JavDBMagnet/JAVDB_COOKIES` entry.
    fn keyring_lock() -> MutexGuard<'static, ()> {
        static LOCK: OnceLock<Mutex<()>> = OnceLock::new();
        LOCK.get_or_init(|| Mutex::new(()))
            .lock()
            .unwrap_or_else(|poisoned| poisoned.into_inner())
    }

    /// RAII guard that snapshots the user's pre-test cookies and restores
    /// them on drop. Holds the global keyring lock for the test's lifetime.
    struct KeyringSandbox {
        _guard: MutexGuard<'static, ()>,
        saved: Option<String>,
    }

    impl KeyringSandbox {
        fn new() -> Self {
            let guard = keyring_lock();
            let saved = crate::cookie_store::get_cookies()
                .ok()
                .flatten()
                .filter(|s| !s.is_empty());
            // Start from a known-empty state. Backend failure is benign here
            // because tests using the sandbox call `set_cookies` themselves
            // and will fail loudly if the backend's broken.
            let _ = crate::cookie_store::delete_cookies();
            Self { _guard: guard, saved }
        }
    }

    impl Drop for KeyringSandbox {
        fn drop(&mut self) {
            let _ = crate::cookie_store::delete_cookies();
            if let Some(saved) = &self.saved {
                let _ = crate::cookie_store::set_cookies(saved);
            }
        }
    }

    fn temp_dir() -> std::path::PathBuf {
        static COUNTER: AtomicUsize = AtomicUsize::new(0);
        let id = COUNTER.fetch_add(1, Ordering::SeqCst);
        let dir = env::temp_dir().join(format!(
            "javdbmagnet-cookies-e2e-{}-{}",
            std::process::id(),
            id
        ));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    // -----------------------------------------------------------------
    // Goal 1: refresh / startup migration — file→keyring→delete
    // -----------------------------------------------------------------

    #[test]
    fn goal_1_migration_writes_keyring_and_removes_file() {
        let _sb = KeyringSandbox::new();

        let d = temp_dir();
        let path = d.join(COOKIES_FILE_NAME);
        let test_cookies =
            "_jdb_session=e2e_jdb_session; cf_clearance=e2e_cf_clearance; locale=zh";
        fs::write(&path, test_cookies).unwrap();

        let migrated = crate::migrate_cookies_from_file(&path)
            .expect("real-content file must yield a migration");
        assert_eq!(migrated, test_cookies, "migration must surface trimmed value");

        // File invariant: deleted (the entire point of the migration).
        assert!(
            !path.exists(),
            "cookies.txt must be removed after a successful migration",
        );

        // Keyring invariant: the value is now persisted in the credential
        // store. This is the half that was previously untested — without
        // this assertion we couldn't claim Goal 1 ("Cookie 會被存入 windows
        // 認證器") was actually satisfied at runtime.
        let stored = crate::cookie_store::get_cookies()
            .expect("keyring read must succeed")
            .expect("keyring must hold the migrated value");
        assert_eq!(stored, test_cookies);
    }

    #[test]
    fn goal_1_oversized_template_migrates_just_the_cookie_line() {
        // Regression for the real-user bug: a cookies.txt that's the template
        // scaffold + one real cookie line at the bottom is ~2.5 KiB total
        // (the template's Chinese instructions alone are ~1.8 KiB). Windows
        // Credential Manager rejects generic-credential blobs that large, so
        // writing the raw file content fails — silently when launched from
        // Explorer because stderr has nowhere to go. After the
        // `extract_cookie_lines` filter, only the real cookie line is
        // written, which is well within the Windows blob cap.
        let _sb = KeyringSandbox::new();
        let d = temp_dir();
        let path = d.join(COOKIES_FILE_NAME);
        let real_cookies =
            "_jdb_session=regress_session; cf_clearance=regress_cf; locale=zh";
        // Reproduce the structure the production template generator emits:
        // a wall of `#`-prefixed comment lines, then the user's pasted line.
        let mut bloat = String::new();
        for i in 0..120 {
            bloat.push_str(&format!(
                "# line {i:03} 把你的 JavDB 登入 cookie 貼到本檔最後一行\n",
            ));
        }
        bloat.push_str(real_cookies);
        bloat.push('\n');
        assert!(
            bloat.len() > 1500,
            "fixture must exceed the conservative Windows cap to exercise the bug",
        );
        fs::write(&path, &bloat).unwrap();

        let migrated = crate::migrate_cookies_from_file(&path)
            .expect("migration must succeed despite an oversized raw file");
        assert_eq!(
            migrated, real_cookies,
            "migration must store only the cookie pairs, not the comments",
        );
        assert!(
            !path.exists(),
            "file must be removed after a successful migration",
        );
        let stored = crate::cookie_store::get_cookies()
            .expect("keyring read")
            .expect("keyring must hold the migrated cookie pairs");
        assert_eq!(stored, real_cookies);
    }

    #[test]
    fn goal_1_template_only_file_leaves_keyring_untouched() {
        // Symmetric guarantee: a freshly-created template (no real cookies
        // yet) MUST NOT migrate. Otherwise users would lose their good
        // keyring entry the moment they clicked "create template" then
        // restarted.
        let _sb = KeyringSandbox::new();
        let preexisting =
            "_jdb_session=preexisting_session; cf_clearance=preexisting_cf";
        crate::cookie_store::set_cookies(preexisting)
            .expect("seed keyring with a pre-existing value");

        let d = temp_dir();
        let template_only = "# JavDBMagnet cookies.txt\n\
                             # ====\n\
                             # _jdb_session=XXX; cf_clearance=XXX; locale=zh\n\
                             # === 在下面貼上你的 cookie 整行 ===\n\n";
        fs::write(d.join(COOKIES_FILE_NAME), template_only).unwrap();

        let result = crate::migrate_cookies_from_file(&d.join(COOKIES_FILE_NAME));
        assert!(result.is_none(), "template-only file must not migrate");

        // Keyring value untouched.
        let kept = crate::cookie_store::get_cookies()
            .expect("keyring read")
            .expect("keyring value must remain");
        assert_eq!(kept, preexisting);
        // File still on disk so user can edit it.
        assert!(d.join(COOKIES_FILE_NAME).exists());
    }

    // -----------------------------------------------------------------
    // Goal 2: three storage labels reflect real state
    // -----------------------------------------------------------------

    #[test]
    fn goal_2_status_reports_none_when_neither_file_nor_keyring() {
        let _sb = KeyringSandbox::new(); // keyring is empty after sandbox setup
        let d = temp_dir(); // no file
        let s = cookies_status_for(&d);
        assert_eq!(s.storage, "none", "no file + no keyring → storage=none");
        assert!(!s.present);
        assert!(s.modified_iso.is_none());
        assert_eq!(s.size_bytes, 0);
    }

    #[test]
    fn goal_2_status_reports_keyring_when_only_keyring_has_value() {
        let _sb = KeyringSandbox::new();
        crate::cookie_store::set_cookies(
            "_jdb_session=label_test; cf_clearance=label_test_cf",
        )
        .expect("seed keyring");
        let d = temp_dir(); // no file
        let s = cookies_status_for(&d);
        assert_eq!(
            s.storage, "keyring",
            "keyring-only state must surface storage=keyring so the UI shows the right label",
        );
        assert!(s.present);
        assert!(s.modified_iso.is_none(), "keyring has no mtime");
        assert_eq!(s.size_bytes, 0, "keyring has no on-disk size");
    }

    #[test]
    fn goal_2_status_reports_file_when_file_present_regardless_of_keyring() {
        // File "wins" because it's the user's most recent intent (they
        // just pasted new cookies). The next migration runs the
        // file→keyring promotion.
        let _sb = KeyringSandbox::new();
        crate::cookie_store::set_cookies("_jdb_session=older_keyring_value")
            .expect("seed keyring");

        let d = temp_dir();
        fs::write(
            d.join(COOKIES_FILE_NAME),
            "_jdb_session=brand_new; cf_clearance=brand_new",
        )
        .unwrap();

        let s = cookies_status_for(&d);
        assert_eq!(s.storage, "file", "file presence must win even when keyring is populated");
        assert!(s.present);
        assert!(s.size_bytes > 0);
    }

    // -----------------------------------------------------------------
    // Goal 3: paste UI path — save_cookies_local
    // -----------------------------------------------------------------

    #[test]
    fn goal_3_paste_path_writes_keyring_and_removes_stale_file() {
        let _sb = KeyringSandbox::new();

        let d = temp_dir();
        // Pretend an older cookies.txt is still sitting in the data dir
        // (e.g. user edited it but is now using the paste UI instead).
        fs::write(d.join(COOKIES_FILE_NAME), "stale legacy contents").unwrap();

        let saved = save_cookies_local(
            &d,
            "  _jdb_session=paste_session; cf_clearance=paste_cf  \n",
        )
        .expect("paste with realistic value must succeed");

        assert_eq!(
            saved,
            "_jdb_session=paste_session; cf_clearance=paste_cf",
            "value must be trimmed before persisting",
        );

        // Keyring invariant
        let in_keyring = crate::cookie_store::get_cookies()
            .expect("keyring read")
            .expect("keyring must hold the pasted value");
        assert_eq!(in_keyring, saved);

        // File invariant: stale plaintext is gone so the next startup
        // can't re-migrate older content over the fresh paste.
        assert!(
            !d.join(COOKIES_FILE_NAME).exists(),
            "stale cookies.txt must be removed by the paste path",
        );

        // And after the paste, cookies_status_for must report keyring.
        let s = cookies_status_for(&d);
        assert_eq!(s.storage, "keyring");
        assert!(s.present);
    }

    #[test]
    fn goal_3_paste_path_rejects_empty_without_touching_keyring() {
        // Defense in depth: the validator runs before any keyring write,
        // so a bug that lets empty input through still can't blank a
        // real entry. We seed a value, attempt an empty paste, and
        // verify the value survives.
        let _sb = KeyringSandbox::new();
        let preexisting = "_jdb_session=keep_me_alive";
        crate::cookie_store::set_cookies(preexisting).expect("seed");

        let d = temp_dir();
        let err = save_cookies_local(&d, "   \n\t").expect_err("empty must error");
        assert_eq!(err, "cookies_empty");

        let still_there = crate::cookie_store::get_cookies()
            .expect("keyring read")
            .expect("keyring must still hold pre-paste value");
        assert_eq!(still_there, preexisting);
    }

    #[test]
    fn goal_3_paste_path_rejects_oversized_without_touching_keyring() {
        let _sb = KeyringSandbox::new();
        let preexisting = "_jdb_session=keep_me_alive";
        crate::cookie_store::set_cookies(preexisting).expect("seed");

        let d = temp_dir();
        let huge = "a".repeat(crate::cookie_store::COOKIES_MAX_BYTES + 1);
        let err = save_cookies_local(&d, &huge).expect_err("oversized must error");
        assert_eq!(err, crate::cookie_store::COOKIES_TOO_LARGE_ERR);

        let still_there = crate::cookie_store::get_cookies()
            .expect("keyring read")
            .expect("keyring must still hold pre-paste value");
        assert_eq!(still_there, preexisting);
    }
}
