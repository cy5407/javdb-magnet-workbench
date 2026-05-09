//! Resolves the on-disk paths used by the Tauri app.
//!
//! Per design spec §4 (storage layout):
//! - data dir: %APPDATA%\JavDBMagnet  (Roaming — settings, cookies, pending)
//! - log dir:  %LOCALAPPDATA%\JavDBMagnet\logs  (Local — debug logs)
//!
//! We deliberately do NOT use Tauri's `app_data_dir()` default (which is
//! `%APPDATA%\<bundle.identifier>`); the spec locks the folder name to
//! `JavDBMagnet`, not the reverse-DNS identifier.

use std::path::PathBuf;
use tauri::AppHandle;

const APP_FOLDER: &str = "JavDBMagnet";

#[derive(Debug, Clone)]
pub struct PathManager {
    pub data_dir: PathBuf,
    pub log_dir: PathBuf,
}

impl PathManager {
    #[cfg(target_os = "windows")]
    pub fn new(_app_handle: &AppHandle) -> Result<Self, Box<dyn std::error::Error>> {
        let appdata = std::env::var("APPDATA")
            .map_err(|_| "APPDATA env var not set")?;
        let local_appdata = std::env::var("LOCALAPPDATA")
            .map_err(|_| "LOCALAPPDATA env var not set")?;
        Ok(Self {
            data_dir: PathBuf::from(appdata).join(APP_FOLDER),
            log_dir: PathBuf::from(local_appdata).join(APP_FOLDER).join("logs"),
        })
    }

    /// Non-Windows fallback so `cargo check` can pass on Linux/macOS dev machines.
    /// V1 ships Windows-only; the runtime path is always the windows branch above.
    #[cfg(not(target_os = "windows"))]
    pub fn new(app_handle: &AppHandle) -> Result<Self, Box<dyn std::error::Error>> {
        use tauri::Manager;
        let data_dir = app_handle.path().app_data_dir()?;
        let log_dir = app_handle.path().app_log_dir()?;
        Ok(Self { data_dir, log_dir })
    }

    pub fn ensure_dirs(&self) -> std::io::Result<()> {
        std::fs::create_dir_all(&self.data_dir)?;
        std::fs::create_dir_all(&self.log_dir)?;
        Ok(())
    }
}
