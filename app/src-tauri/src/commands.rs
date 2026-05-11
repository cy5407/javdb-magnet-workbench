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

use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
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
    if !resp.get("ok").and_then(|v| v.as_bool()).unwrap_or(false) {
        let code = resp
            .get("error")
            .and_then(|e| e.get("code"))
            .and_then(|c| c.as_str())
            .unwrap_or("unknown");
        return Err(code.to_string());
    }
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
    if !resp.get("ok").and_then(|v| v.as_bool()).unwrap_or(false) {
        return Err(_err_code(&resp));
    }

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
    if !resp.get("ok").and_then(|v| v.as_bool()).unwrap_or(false) {
        return Err(_err_code(&resp));
    }
    let user = resp.get("user").cloned().unwrap_or(Value::Null);
    let info: RdUserInfo = serde_json::from_value(user).map_err(|e| e.to_string())?;
    Ok(info)
}

/// Persist a token to the credential store + push to the running sidecar.
#[tauri::command]
pub async fn rd_save_token(
    sidecar: State<'_, SidecarManager>,
    token: String,
) -> Result<(), String> {
    secret_store::set_rd_token(&token)?;
    let payload: Value = if token.is_empty() {
        json!({ "token": Value::Null })
    } else {
        json!({ "token": token })
    };
    let resp = sidecar.request("rd_set_token", payload).await?;
    if !resp.get("ok").and_then(|v| v.as_bool()).unwrap_or(false) {
        return Err(_err_code(&resp));
    }
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
    if !resp.get("ok").and_then(|v| v.as_bool()).unwrap_or(false) {
        return Err(_err_code(&resp));
    }
    Ok(())
}

/// Account snapshot for a token already saved in the credential store.
/// Returns the same shape as rd_test_token; separate command so the UI
/// can avoid sending the secret across IPC just to refresh the display.
#[tauri::command]
pub async fn rd_check_user(sidecar: State<'_, SidecarManager>) -> Result<RdUserInfo, String> {
    let resp = sidecar.request("rd_user", Value::Null).await?;
    if !resp.get("ok").and_then(|v| v.as_bool()).unwrap_or(false) {
        return Err(_err_code(&resp));
    }
    let user = resp.get("user").cloned().unwrap_or(Value::Null);
    let info: RdUserInfo = serde_json::from_value(user).map_err(|e| e.to_string())?;
    Ok(info)
}

#[derive(Deserialize)]
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
    let opts = options.unwrap_or(RdSendOptions {
        strategy: None,
        min_size_mb: None,
        cache_wait: None,
        code: None,
        size_label: None,
    });

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
    if !resp.get("ok").and_then(|v| v.as_bool()).unwrap_or(false) {
        return Err(_err_code(&resp));
    }

    let status = resp
        .get("status")
        .and_then(|s| s.as_str())
        .unwrap_or("");
    let torrent_id = resp
        .get("torrent_id")
        .and_then(|s| s.as_str())
        .unwrap_or("")
        .to_string();
    let name = resp
        .get("name")
        .and_then(|s| s.as_str())
        .unwrap_or("")
        .to_string();

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
    let rd_status = resp
        .get("rd_status")
        .and_then(|s| s.as_str())
        .unwrap_or("")
        .to_string();
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
    if !resp.get("ok").and_then(|v| v.as_bool()).unwrap_or(false) {
        return Err(_err_code(&resp));
    }

    let status = resp.get("status").and_then(|s| s.as_str()).unwrap_or("");
    if status == "completed" {
        // Persisted entry no longer needed.
        pending::remove(&path_manager.data_dir, &torrent_id)?;
        let name = resp
            .get("name")
            .and_then(|s| s.as_str())
            .unwrap_or("")
            .to_string();
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
    let name = resp
        .get("name")
        .and_then(|s| s.as_str())
        .unwrap_or("")
        .to_string();
    let rd_status = resp
        .get("rd_status")
        .and_then(|s| s.as_str())
        .unwrap_or("")
        .to_string();
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
    use std::path::Path;

    let trimmed = source_dir.trim();
    if trimmed.is_empty() {
        return Err("source_dir is empty".to_string());
    }
    let src = Path::new(trimmed);
    if !src.is_dir() {
        return Err(format!(
            "source_dir is not a directory: {}",
            src.display()
        ));
    }
    // Refuse to import from our own data dir — would degenerate into a
    // self-copy and confuse the report.
    if src
        .canonicalize()
        .ok()
        .and_then(|s| path_manager.data_dir.canonicalize().ok().map(|d| s == d))
        .unwrap_or(false)
    {
        return Err("source_dir must not be the app data directory".to_string());
    }

    let mut report = LegacyImportReport::default();
    let preview = legacy_import::preview(src);
    report.warnings.extend(preview.warnings.clone());

    // ---- .env import ----
    if preview.env_present {
        match std::fs::read_to_string(src.join(legacy_import::LEGACY_ENV_FILE)) {
            Ok(s) => {
                let parsed = legacy_import::parse_env(&s);
                report.warnings.extend(
                    parsed
                        .warnings
                        .iter()
                        .map(|w| format!(".env: {w}")),
                );

                // RD token → credential store + propagate to sidecar.
                // NEVER written to settings.json.
                if let Some(token) = parsed.token.as_deref() {
                    if let Err(e) = secret_store::set_rd_token(token) {
                        report.warnings.push(format!("credential store: {e}"));
                    } else {
                        let payload = json!({ "token": token });
                        match sidecar.request("rd_set_token", payload).await {
                            Ok(resp) => {
                                if resp
                                    .get("ok")
                                    .and_then(Value::as_bool)
                                    .unwrap_or(false)
                                {
                                    report.rd_token_imported = true;
                                    report
                                        .sources
                                        .push(format!("{}/.env (RD_API_TOKEN)", src.display()));
                                } else {
                                    report.warnings.push(format!(
                                        "sidecar rd_set_token: {}",
                                        _err_code(&resp)
                                    ));
                                }
                            }
                            Err(e) => report.warnings.push(format!("sidecar: {e}")),
                        }
                    }
                }

                // Non-secret settings → patch + save via tauri-plugin-store.
                if !parsed.settings_patch.is_empty() {
                    let store_path = path_manager.data_dir.join(crate::STORE_FILE);
                    match app.store(&store_path) {
                        Ok(store) => {
                            // Start from current settings JSON (or defaults).
                            let mut base = store.get("settings").unwrap_or_else(|| {
                                serde_json::to_value(crate::settings::Settings::default())
                                    .unwrap_or(Value::Null)
                            });
                            legacy_import::apply_settings_patch(&mut base, &parsed.settings_patch);
                            // Belt + suspenders: confirm api_token blank.
                            if let Some(rd) =
                                base.get_mut("rd").and_then(Value::as_object_mut)
                            {
                                if let Some(t) = rd.get_mut("api_token") {
                                    *t = Value::String(String::new());
                                }
                            }
                            store.set("settings", base);
                            if let Err(e) = store.save() {
                                report.warnings.push(format!("settings save: {e}"));
                            } else {
                                report.env_imported = true;
                                report
                                    .sources
                                    .push(format!("{}/.env (settings)", src.display()));
                            }
                        }
                        Err(e) => report.warnings.push(format!("settings store: {e}")),
                    }
                }
            }
            Err(e) => report.warnings.push(format!("read .env failed: {e}")),
        }
    }

    // ---- cookies.txt import ----
    if preview.cookies_present {
        let src_cookies = src.join(legacy_import::LEGACY_COOKIES_FILE);
        let dst_cookies = path_manager
            .data_dir
            .join(legacy_import::LEGACY_COOKIES_FILE);
        if let Err(e) = std::fs::create_dir_all(&path_manager.data_dir) {
            report.warnings.push(format!("mkdir data_dir: {e}"));
        }
        // Refuse to copy onto itself if the user pointed at data_dir.
        let same = src_cookies
            .canonicalize()
            .ok()
            .and_then(|s| dst_cookies.canonicalize().ok().map(|d| s == d))
            .unwrap_or(false);
        if same {
            report
                .warnings
                .push("cookies.txt: source and destination are the same path".into());
        } else {
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
    }

    // ---- pending_torrents.json import ----
    if preview.pending_present {
        let src_pending = src.join(legacy_import::LEGACY_PENDING_FILE);
        match std::fs::read_to_string(&src_pending) {
            Ok(raw) => match pending::load(&path_manager.data_dir) {
                Ok(existing) => match legacy_import::merge_legacy_pending(&raw, &existing) {
                    Ok((merged, imported, skipped)) => {
                        match pending::save(&path_manager.data_dir, &merged) {
                            Ok(_) => {
                                report.pending_imported = imported;
                                report.pending_skipped = skipped;
                                report.sources.push(format!(
                                    "{}/pending_torrents.json",
                                    src.display()
                                ));
                            }
                            Err(e) => report.warnings.push(format!("pending save: {e}")),
                        }
                    }
                    Err(e) => report.warnings.push(format!("pending merge: {e}")),
                },
                Err(e) => report.warnings.push(format!("pending load (existing): {e}")),
            },
            Err(e) => report.warnings.push(format!("read pending JSON failed: {e}")),
        }
    }

    Ok(report)
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
    /// ISO-8601 UTC string. `None` if the file is missing or the OS
    /// doesn't give us mtime (e.g. exotic filesystem).
    pub modified_iso: Option<String>,
    pub size_bytes: u64,
}

/// Pure helper — takes a data dir path and reports the cookies.txt
/// status without reading the file contents. Used by both the Tauri
/// command and the unit tests.
pub(crate) fn cookies_status_for(data_dir: &std::path::Path) -> CookiesStatus {
    let path = data_dir.join(COOKIES_FILE_NAME);
    let path_display = path.display().to_string();
    let meta = match std::fs::metadata(&path) {
        Ok(m) => m,
        Err(_) => {
            return CookiesStatus {
                present: false,
                path: path_display,
                modified_iso: None,
                size_bytes: 0,
            };
        }
    };
    let size_bytes = meta.len();
    let modified_iso = meta
        .modified()
        .ok()
        .map(|st| chrono::DateTime::<chrono::Utc>::from(st).to_rfc3339());
    CookiesStatus {
        present: true,
        path: path_display,
        modified_iso,
        size_bytes,
    }
}

#[tauri::command]
pub fn get_cookies_status(path_manager: State<PathManager>) -> CookiesStatus {
    cookies_status_for(&path_manager.data_dir)
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
    if let Some(rd) = sanitized.get_mut("rd").and_then(Value::as_object_mut) {
        if let Some(t) = rd.get_mut("api_token") {
            *t = Value::String(String::new());
        }
    }
    let resp = sidecar
        .request("update_settings", json!({ "settings": sanitized }))
        .await?;
    if !resp.get("ok").and_then(Value::as_bool).unwrap_or(false) {
        return Err(_err_code(&resp));
    }
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
        return Ok(());
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
    fn cookies_status_missing_file() {
        let d = temp_dir();
        let s = cookies_status_for(&d);
        assert!(!s.present);
        assert_eq!(s.size_bytes, 0);
        assert!(s.modified_iso.is_none());
        // path is still echoed so the UI can show "expected at ..."
        assert!(s.path.contains("cookies.txt"));
    }

    #[test]
    fn cookies_status_present_file() {
        let d = temp_dir();
        let path = d.join(COOKIES_FILE_NAME);
        fs::write(&path, "# domain\tdummy\tplaceholder=1\n").unwrap();
        let s = cookies_status_for(&d);
        assert!(s.present);
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
        let s = cookies_status_for(&d);
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
