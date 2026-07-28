//! Settings storage backed by tauri-plugin-store.
//!
//! Schema follows design spec §4.1. Field defaults match the legacy GUI's
//! .env defaults so the M7 importer can map values 1:1.

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, State};
use tauri_plugin_store::StoreExt;

use crate::path_manager::PathManager;
use crate::sidecar_manager::{MAX_RD_CACHE_WAIT_SECS, MIN_RD_CACHE_WAIT_SECS};

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
}

impl Default for RdSettings {
    fn default() -> Self {
        Self {
            api_token: String::new(),
            file_pick: "smart".to_string(),
            min_size_mb: 500,
            cache_wait_seconds: 15,
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

/// Clamp persisted RD numerics into the range the send path accepts.
/// The frontend validates too, but legacy import and hand-edited
/// settings.json bypass it — and an out-of-range value silently breaks
/// every RD send at `timeout_for` with an unrelated-looking error.
fn clamp_rd_settings(mut s: Settings) -> Settings {
    s.rd.cache_wait_seconds = s.rd.cache_wait_seconds.clamp(
        MIN_RD_CACHE_WAIT_SECS as u32,
        MAX_RD_CACHE_WAIT_SECS as u32,
    );
    s.rd.min_size_mb = s.rd.min_size_mb.min(1_000_000);
    s
}

fn without_secrets(mut settings: Settings) -> Settings {
    // M5 moved RD token storage to the OS credential store. Keep the legacy
    // field in the schema for migration compatibility, but never return it
    // to the WebView and never persist a new plaintext value through this
    // command surface.
    settings.rd.api_token.clear();
    settings
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
        Some(v) => serde_json::from_value::<Settings>(v)
            .map(without_secrets)
            .map_err(|e| e.to_string()),
        None => Ok(without_secrets(Settings::default())),
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
    let value = serde_json::to_value(without_secrets(clamp_rd_settings(settings)))
        .map_err(|e| e.to_string())?;
    store.set(SETTINGS_KEY, value);
    store.save().map_err(|e| e.to_string())?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn without_secrets_clears_legacy_rd_token_field() {
        let mut settings = Settings::default();
        settings.rd.api_token = "SECRET_TOKEN_SHOULD_NOT_CROSS_WEBVIEW".to_string();

        let sanitized = without_secrets(settings);

        assert_eq!(sanitized.rd.api_token, "");
    }

    #[test]
    fn clamp_rd_settings_clamps_out_of_bounds_values() {
        let mut s = Settings::default();
        s.rd.cache_wait_seconds = 1;
        s.rd.min_size_mb = 5_000_000;
        let clamped = clamp_rd_settings(s);
        assert_eq!(clamped.rd.cache_wait_seconds, 5);
        assert_eq!(clamped.rd.min_size_mb, 1_000_000);

        let mut s2 = Settings::default();
        s2.rd.cache_wait_seconds = 9999;
        let clamped2 = clamp_rd_settings(s2);
        assert_eq!(clamped2.rd.cache_wait_seconds, 300);

        let mut s3 = Settings::default();
        s3.rd.cache_wait_seconds = 15;
        s3.rd.min_size_mb = 500;
        let clamped3 = clamp_rd_settings(s3);
        assert_eq!(clamped3.rd.cache_wait_seconds, 15);
        assert_eq!(clamped3.rd.min_size_mb, 500);
    }
}
