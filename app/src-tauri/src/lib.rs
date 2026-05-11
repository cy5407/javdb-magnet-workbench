mod commands;
mod path_manager;
mod pending;
mod legacy_import;
mod secret_store;
mod settings;
mod sidecar_manager;

use serde_json::{json, Value};
use tauri::Manager;

use path_manager::PathManager;
use sidecar_manager::SidecarManager;

const STORE_FILE: &str = "settings.json";

/// Read on-disk handshake inputs from the data dir. Missing files are not
/// errors — the sidecar accepts empty cookies (subsequent fetch_javdb will
/// surface a cloudflare_block) and an empty settings/token snapshot.
///
/// Token sourcing in M5+:
///   1. OS credential store (preferred)
///   2. Legacy `settings.rd.api_token` field — kept ONLY for the M4→M5
///      migration. If found, we copy it into the credential store and
///      blank the JSON field, so subsequent reads come from the secure
///      backend. The value is never returned to the frontend.
fn load_handshake_inputs(path_manager: &PathManager) -> (String, Option<String>, Value) {
    let cookies_path = path_manager.data_dir.join("cookies.txt");
    let cookies = std::fs::read_to_string(&cookies_path)
        .map(|s| s.trim().to_string())
        .unwrap_or_default();

    let settings_path = path_manager.data_dir.join(STORE_FILE);
    let settings_value = std::fs::read_to_string(&settings_path)
        .ok()
        .and_then(|s| serde_json::from_str::<Value>(&s).ok())
        .and_then(|v| v.get("settings").cloned())
        .unwrap_or(Value::Object(Default::default()));

    // Token: credential store first; otherwise migrate from legacy JSON.
    let rd_token = match secret_store::get_rd_token() {
        Ok(Some(t)) if !t.is_empty() => Some(t),
        _ => migrate_legacy_token(path_manager, &settings_value),
    };

    (cookies, rd_token, settings_value)
}

/// One-shot migration: pull `settings.rd.api_token` (legacy plaintext) into
/// the credential store, then rewrite the JSON file with the field cleared.
/// Returns the migrated token (so the first sidecar handshake still has
/// it) or None if there was nothing to migrate.
fn migrate_legacy_token(path_manager: &PathManager, settings_value: &Value) -> Option<String> {
    let token = settings_value
        .get("rd")
        .and_then(|r| r.get("api_token"))
        .and_then(|t| t.as_str())
        .filter(|s| !s.is_empty())?
        .to_string();

    if let Err(e) = secret_store::set_rd_token(&token) {
        eprintln!("[migrate] keyring write failed, leaving plaintext: {e}");
        return Some(token);
    }
    // Best-effort scrub of the on-disk plaintext copy. tauri-plugin-store
    // owns the file format so we re-read the wrapper, blank the field,
    // and write the wrapper back.
    let store_path = path_manager.data_dir.join(STORE_FILE);
    if let Ok(raw) = std::fs::read_to_string(&store_path) {
        if let Ok(mut wrapper) = serde_json::from_str::<Value>(&raw) {
            if let Some(s) = wrapper
                .get_mut("settings")
                .and_then(|v| v.get_mut("rd"))
                .and_then(|r| r.get_mut("api_token"))
            {
                *s = Value::String(String::new());
                if let Ok(body) = serde_json::to_string_pretty(&wrapper) {
                    let _ = std::fs::write(&store_path, body);
                }
            }
        }
    }
    Some(token)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_store::Builder::new().build())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_clipboard_manager::init())
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            let path_manager = PathManager::new(app.handle())?;
            path_manager.ensure_dirs()?;

            let (cookies, rd_token, settings_value) = load_handshake_inputs(&path_manager);
            let paths = json!({
                "data_dir": path_manager.data_dir.to_string_lossy().to_string(),
                "log_dir": path_manager.log_dir.to_string_lossy().to_string(),
            });

            let app_handle = app.handle().clone();
            app.manage(path_manager);

            // Spawn sidecar synchronously during setup so all subsequent
            // Tauri commands can rely on State<SidecarManager> being present.
            // Failures here surface as setup errors (window doesn't open).
            let manager = tauri::async_runtime::block_on(
                SidecarManager::spawn_and_handshake(
                    &app_handle,
                    cookies,
                    rd_token,
                    settings_value,
                    paths,
                ),
            )
            .map_err(|e| -> Box<dyn std::error::Error> { e.into() })?;
            app.manage(manager);

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            settings::get_paths,
            settings::read_settings,
            settings::write_settings,
            commands::sidecar_ping,
            commands::fetch_javdb,
            commands::copy_magnet,
            commands::copy_magnets_bulk,
            commands::copy_rd_links_bulk,
            commands::forget_magnets,
            commands::register_magnets,
            commands::rd_has_token,
            commands::rd_test_token,
            commands::rd_save_token,
            commands::rd_clear_token,
            commands::rd_check_user,
            commands::rd_send_magnet,
            commands::rd_check_pending,
            commands::pending_list,
            commands::pending_remove,
            commands::pending_clear,
            commands::get_legacy_default_dir,
            commands::preview_legacy_import,
            commands::apply_legacy_import,
            commands::get_cookies_status,
            commands::open_data_dir,
            commands::open_logs_dir,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
