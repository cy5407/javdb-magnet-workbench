//! Settings storage backed by tauri-plugin-store.
//!
//! Schema follows design spec §4.1. Field defaults match the legacy GUI's
//! .env defaults so the M7 importer can map values 1:1.

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, State};
use tauri_plugin_store::StoreExt;

use crate::path_manager::PathManager;

const STORE_FILE: &str = "settings.json";
const SETTINGS_KEY: &str = "settings";

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct UiSettings {
    pub theme: String,
    pub scale: String,
}

impl Default for UiSettings {
    fn default() -> Self {
        Self {
            theme: "light".to_string(),
            scale: "auto".to_string(),
        }
    }
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct RdSettings {
    pub api_token: String,
    pub file_pick: String,
    pub min_size_mb: u32,
    pub cache_wait_seconds: u32,
    pub wait_timeout_seconds: u32,
}

impl Default for RdSettings {
    fn default() -> Self {
        Self {
            api_token: String::new(),
            file_pick: "smart".to_string(),
            min_size_mb: 500,
            cache_wait_seconds: 15,
            wait_timeout_seconds: 300,
        }
    }
}

fn default_version() -> u32 {
    1
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Settings {
    #[serde(default = "default_version")]
    pub version: u32,
    #[serde(default)]
    pub ui: UiSettings,
    #[serde(default)]
    pub rd: RdSettings,
}

impl Default for Settings {
    fn default() -> Self {
        Self {
            version: 1,
            ui: UiSettings::default(),
            rd: RdSettings::default(),
        }
    }
}

#[derive(Debug, Serialize)]
pub struct PathInfo {
    pub data_dir: String,
    pub log_dir: String,
}

#[tauri::command]
pub fn get_paths(path_manager: State<PathManager>) -> PathInfo {
    PathInfo {
        data_dir: path_manager.data_dir.display().to_string(),
        log_dir: path_manager.log_dir.display().to_string(),
    }
}

#[tauri::command]
pub fn read_settings(
    app: AppHandle,
    path_manager: State<PathManager>,
) -> Result<Settings, String> {
    // Use an absolute path so tauri-plugin-store does NOT resolve under
    // BaseDirectory::AppData (which would land in %APPDATA%\<identifier>\,
    // not the spec's %APPDATA%\JavDBMagnet\).
    let store_path = path_manager.data_dir.join(STORE_FILE);
    let store = app.store(store_path).map_err(|e| e.to_string())?;
    match store.get(SETTINGS_KEY) {
        Some(v) => serde_json::from_value::<Settings>(v).map_err(|e| e.to_string()),
        None => Ok(Settings::default()),
    }
}

#[tauri::command]
pub fn write_settings(
    app: AppHandle,
    path_manager: State<PathManager>,
    settings: Settings,
) -> Result<(), String> {
    let store_path = path_manager.data_dir.join(STORE_FILE);
    let store = app.store(store_path).map_err(|e| e.to_string())?;
    let value = serde_json::to_value(&settings).map_err(|e| e.to_string())?;
    store.set(SETTINGS_KEY, value);
    store.save().map_err(|e| e.to_string())?;
    Ok(())
}
