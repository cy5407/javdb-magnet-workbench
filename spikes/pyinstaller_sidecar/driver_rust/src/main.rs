//! Rust driver — 呼叫 PyInstaller 打包後的 sidecar.exe
//!
//! 用法：
//!     cargo run -- "https://javdb.com/v/xxxx"
//!
//! 不會輸出完整 magnet / cookie / token，sidecar 的 stdout/stderr 也不會原樣轉印。
//!
//! ⚠️ **僅供 dev / spike harness。** Production（Tauri 整合）應改用
//! `tauri::api::process::Command::new_sidecar()`，由 Tauri sidecar 機制負責
//! binary 解析、權限、路徑與 process lifecycle；此檔的 `locate_sidecar_exe()`
//! 走法只在本 spike 與 cargo run 場景成立。

use std::env;
use std::path::PathBuf;
use std::process::{Command, ExitCode, Stdio};

use serde::{Deserialize, Serialize};

/// sidecar binary 名稱（依平台選副檔名，避免硬寫 `.exe` 造成非 Windows 永遠找不到）。
#[cfg(windows)]
const SIDECAR_NAME: &str = "sidecar.exe";
#[cfg(not(windows))]
const SIDECAR_NAME: &str = "sidecar";

/// env 短路：若使用者顯式指定 sidecar 路徑（測試/CI/容器場景），優先採用。
const SIDECAR_EXE_ENV: &str = "SIDECAR_EXE";

#[derive(Debug, Deserialize)]
struct SidecarResponse {
    ok: bool,
    magnet_count: usize,
    magnets: Vec<SidecarMagnet>,
    #[serde(default)]
    error: Option<String>,
}

#[derive(Debug, Deserialize)]
struct SidecarMagnet {
    magnet_redacted: String,
}

#[derive(Debug, Serialize)]
struct DriverSummary {
    ok: bool,
    sidecar_exit: i32,
    parsed_json: bool,
    magnet_count: usize,
    first_magnet_redacted_present: bool,
    stderr_nonempty: bool,
    error: Option<String>,
}

/// 找 sidecar binary。
///
/// 優先序：
/// 1. `SIDECAR_EXE` 環境變數（顯式指定，給 CI/測試/容器用）
/// 2. `CARGO_MANIFEST_DIR/../dist/<SIDECAR_NAME>`（cargo run 在 source tree）
/// 3. `current_exe()` 往上 6 層找 `dist/<SIDECAR_NAME>` 或
///    `spikes/pyinstaller_sidecar/dist/<SIDECAR_NAME>`
///
/// 注意：第 3 條是 spike harness 走法，production 應改走 Tauri sidecar 機制。
fn locate_sidecar_exe() -> Result<PathBuf, String> {
    let mut candidates: Vec<PathBuf> = Vec::new();

    if let Ok(p) = env::var(SIDECAR_EXE_ENV) {
        candidates.push(PathBuf::from(p));
    }

    if let Ok(manifest) = env::var("CARGO_MANIFEST_DIR") {
        let mut p = PathBuf::from(manifest);
        p.pop(); // pyinstaller_sidecar/
        p.push("dist");
        p.push(SIDECAR_NAME);
        candidates.push(p);
    }

    if let Ok(exe) = env::current_exe() {
        let mut p = exe;
        for _ in 0..6 {
            if !p.pop() {
                break;
            }
            candidates.push(p.join("dist").join(SIDECAR_NAME));
            candidates.push(
                p.join("spikes")
                    .join("pyinstaller_sidecar")
                    .join("dist")
                    .join(SIDECAR_NAME),
            );
        }
    }

    for c in &candidates {
        if c.exists() {
            return Ok(c.clone());
        }
    }
    Err(format!(
        "找不到 {}；請先執行 `python spikes/pyinstaller_sidecar/build_sidecar.py`，或設定 {} 環境變數（已嘗試 {} 個位置）",
        SIDECAR_NAME,
        SIDECAR_EXE_ENV,
        candidates.len()
    ))
}

fn run(url: &str) -> DriverSummary {
    let exe = match locate_sidecar_exe() {
        Ok(p) => p,
        Err(e) => {
            return DriverSummary {
                ok: false,
                sidecar_exit: -1,
                parsed_json: false,
                magnet_count: 0,
                first_magnet_redacted_present: false,
                stderr_nonempty: false,
                error: Some(e),
            }
        }
    };

    // Spike 不加 timeout；production driver 必須加（避免 sidecar hang 拖垮 Tauri command）。
    let output = Command::new(&exe)
        .arg("fetch-javdb")
        .arg(url)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output();

    let output = match output {
        Ok(o) => o,
        Err(e) => {
            return DriverSummary {
                ok: false,
                sidecar_exit: -1,
                parsed_json: false,
                magnet_count: 0,
                first_magnet_redacted_present: false,
                stderr_nonempty: false,
                error: Some(format!("無法啟動 {}: {}", SIDECAR_NAME, e)),
            }
        }
    };

    let exit_code = output.status.code().unwrap_or(-1);
    let stderr_nonempty = !output.stderr.is_empty();
    let stdout = String::from_utf8_lossy(&output.stdout);
    let parsed: Result<SidecarResponse, _> = serde_json::from_str(stdout.trim());

    match parsed {
        Ok(resp) => {
            let first_redacted_ok = resp
                .magnets
                .first()
                .map(|m| {
                    m.magnet_redacted.starts_with("magnet:?xt=urn:btih:")
                        && m.magnet_redacted.contains("...")
                        && m.magnet_redacted.len() < 64
                })
                .unwrap_or(false);

            DriverSummary {
                ok: resp.ok && exit_code == 0,
                sidecar_exit: exit_code,
                parsed_json: true,
                magnet_count: resp.magnet_count,
                first_magnet_redacted_present: first_redacted_ok,
                stderr_nonempty,
                error: resp.error,
            }
        }
        Err(e) => DriverSummary {
            ok: false,
            sidecar_exit: exit_code,
            parsed_json: false,
            magnet_count: 0,
            first_magnet_redacted_present: false,
            stderr_nonempty,
            error: Some(format!("無法解析 sidecar JSON: {}", e)),
        },
    }
}

fn main() -> ExitCode {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        eprintln!("用法: cargo run -- \"https://javdb.com/v/xxxx\"");
        return ExitCode::from(2);
    }
    let url = &args[1];
    if !url.starts_with("http") {
        eprintln!("URL 必須以 http(s) 開頭");
        return ExitCode::from(2);
    }

    let summary = run(url);
    match serde_json::to_string_pretty(&summary) {
        Ok(s) => println!("{}", s),
        Err(e) => eprintln!("序列化 summary 失敗: {}", e),
    }

    if summary.ok {
        ExitCode::SUCCESS
    } else {
        ExitCode::from(1)
    }
}
