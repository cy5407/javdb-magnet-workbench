//! Tauri/Rust 模擬 backend：呼叫 sidecar.py，parse JSON
//!
//! 用法：
//!     cargo run -- "https://javdb.com/v/xxxx"
//!
//! 輸出：driver 自己的 JSON summary（不會輸出完整 magnet / cookie）。

use std::env;
use std::path::PathBuf;
use std::process::{Command, ExitCode, Stdio};

use serde::{Deserialize, Serialize};

/// sidecar.py 的回傳格式（只 deserialize 我們在 driver 真正用到的欄位）
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

/// driver 自己要印給呼叫端看的 summary
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

/// 找到 sidecar.py 路徑：優先用 CARGO_MANIFEST_DIR/../sidecar.py，
/// 否則往 current_exe 上層找 spikes/python_sidecar_protocol/sidecar.py
fn locate_sidecar() -> Result<PathBuf, String> {
    let mut candidates: Vec<PathBuf> = Vec::new();

    if let Ok(manifest) = env::var("CARGO_MANIFEST_DIR") {
        let mut p = PathBuf::from(manifest);
        p.pop(); // python_sidecar_protocol/
        p.push("sidecar.py");
        candidates.push(p);
    }

    if let Ok(exe) = env::current_exe() {
        let mut p = exe;
        for _ in 0..6 {
            if !p.pop() {
                break;
            }
            candidates.push(p.join("sidecar.py"));
            candidates.push(
                p.join("spikes")
                    .join("python_sidecar_protocol")
                    .join("sidecar.py"),
            );
        }
    }

    for c in &candidates {
        if c.exists() {
            return Ok(c.clone());
        }
    }
    Err(format!("找不到 sidecar.py（嘗試 {} 個位置）", candidates.len()))
}

fn run(url: &str) -> DriverSummary {
    let sidecar = match locate_sidecar() {
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

    let output = Command::new("python")
        .arg(&sidecar)
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
                error: Some(format!("無法啟動 python: {}", e)),
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
