mod path_manager;
mod settings;

use tauri::Manager;

use path_manager::PathManager;

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
            app.manage(path_manager);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            settings::get_paths,
            settings::read_settings,
            settings::write_settings,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
