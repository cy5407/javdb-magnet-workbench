mod commands;
mod path_manager;
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

    let rd_token = settings_value
        .get("rd")
        .and_then(|r| r.get("api_token"))
        .and_then(|t| t.as_str())
        .filter(|s| !s.is_empty())
        .map(String::from);

    (cookies, rd_token, settings_value)
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
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
