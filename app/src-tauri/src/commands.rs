//! Tauri commands for the M3 debug pane.
//!
//! Sensitive data (full magnets) never crosses back into Rust long-lived
//! state or frontend payloads:
//!   - `fetch_javdb` returns redacted magnets + handle_id
//!   - `copy_magnet`/`copy_magnets_bulk` resolve full magnets via the
//!     sidecar, write to OS clipboard, and drop the local string before
//!     returning
//!   - The frontend receives only counts / status, never the magnet text

use serde::Serialize;
use serde_json::{json, Value};
use tauri::{AppHandle, State};
use tauri_plugin_clipboard_manager::ClipboardExt;

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
