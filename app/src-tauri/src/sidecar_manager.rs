//! Long-running Python sidecar daemon manager.
//!
//! Bridges the Tauri plugin-shell `Receiver<CommandEvent>` event stream to a
//! request/response API: each public method writes one JSON line to the
//! daemon's stdin and awaits the next JSON line on stdout.
//!
//! Concurrency model: a single `tokio::sync::Mutex` serializes all requests.
//! The daemon itself is single-threaded synchronous (M3 contract), so this
//! matches its dispatch loop. Multiple concurrent Tauri commands queue
//! behind the lock — fine for the M3 fetch/copy workload.

use std::sync::Arc;

use serde_json::{json, Value};
use tauri::{async_runtime::Mutex, AppHandle};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;
use tokio::sync::mpsc;

const PROTOCOL_VERSION: u32 = 1;

pub struct SidecarManager {
    inner: Arc<Mutex<SidecarInner>>,
}

struct SidecarInner {
    child: CommandChild,
    line_rx: mpsc::UnboundedReceiver<String>,
    request_counter: u64,
}

impl SidecarManager {
    /// Spawn the bundled `sidecar` binary, complete `hello` + `handshake`,
    /// and return a manager ready to serve requests.
    pub async fn spawn_and_handshake(
        app: &AppHandle,
        cookies: String,
        rd_token: Option<String>,
        settings: Value,
        paths: Value,
    ) -> Result<Self, String> {
        let (mut rx, child) = app
            .shell()
            .sidecar("sidecar")
            .map_err(|e| format!("sidecar resolve failed: {e}"))?
            .spawn()
            .map_err(|e| format!("sidecar spawn failed: {e}"))?;

        // Background task: drain stdout chunks, accumulate, emit complete
        // newline-delimited lines into a tokio mpsc channel.
        let (line_tx, line_rx) = mpsc::unbounded_channel::<String>();
        tauri::async_runtime::spawn(async move {
            let mut buffer: Vec<u8> = Vec::new();
            while let Some(event) = rx.recv().await {
                match event {
                    CommandEvent::Stdout(bytes) => {
                        buffer.extend_from_slice(&bytes);
                        while let Some(idx) = buffer.iter().position(|b| *b == b'\n') {
                            let mut line_bytes: Vec<u8> = buffer.drain(..=idx).collect();
                            // Drop trailing \n and \r
                            line_bytes.pop();
                            if line_bytes.last() == Some(&b'\r') {
                                line_bytes.pop();
                            }
                            let line = String::from_utf8_lossy(&line_bytes).to_string();
                            if line_tx.send(line).is_err() {
                                return;
                            }
                        }
                    }
                    CommandEvent::Stderr(_) => {
                        // Per spec §5.3 stderr never carries cookies / token /
                        // full magnet, but we still don't forward it to the
                        // frontend. M6 wires log forwarding to the file.
                    }
                    CommandEvent::Terminated(_) => return,
                    _ => {}
                }
            }
        });

        let manager = Self {
            inner: Arc::new(Mutex::new(SidecarInner {
                child,
                line_rx,
                request_counter: 0,
            })),
        };

        // hello
        let hello = manager
            .request("hello", json!({ "protocol_version": PROTOCOL_VERSION }))
            .await?;
        if !hello.get("ok").and_then(|v| v.as_bool()).unwrap_or(false) {
            let msg = error_message(&hello).unwrap_or("hello failed");
            return Err(format!("sidecar hello failed: {msg}"));
        }

        // handshake
        let handshake_body = json!({
            "cookies": cookies,
            "rd_token": rd_token,
            "settings": settings,
            "paths": paths,
        });
        let handshake = manager.request("handshake", handshake_body).await?;
        if !handshake.get("ok").and_then(|v| v.as_bool()).unwrap_or(false) {
            let msg = error_message(&handshake).unwrap_or("handshake failed");
            return Err(format!("sidecar handshake failed: {msg}"));
        }

        Ok(manager)
    }

    /// Send one JSON-line request, await one JSON-line response.
    pub async fn request(&self, cmd: &str, body: Value) -> Result<Value, String> {
        let mut inner = self.inner.lock().await;
        inner.request_counter += 1;
        let req_id = format!("r-{}", inner.request_counter);

        let mut obj = match body {
            Value::Object(map) => map,
            Value::Null => Default::default(),
            other => {
                return Err(format!(
                    "request body must be a JSON object or null, got {}",
                    other
                ));
            }
        };
        obj.insert("cmd".to_string(), Value::String(cmd.to_string()));
        obj.insert("request_id".to_string(), Value::String(req_id.clone()));

        let line = serde_json::to_string(&Value::Object(obj))
            .map_err(|e| format!("serialize failed: {e}"))?;
        let mut bytes = line.into_bytes();
        bytes.push(b'\n');

        inner
            .child
            .write(&bytes)
            .map_err(|e| format!("stdin write failed: {e}"))?;

        let response_line = inner
            .line_rx
            .recv()
            .await
            .ok_or_else(|| "sidecar closed before response".to_string())?;

        let resp: Value = serde_json::from_str(&response_line)
            .map_err(|e| format!("response parse failed: {e}"))?;

        // Verify request_id correlation. Since we serialize all requests
        // behind the mutex, mismatches indicate a protocol bug.
        let resp_id = resp.get("request_id").and_then(|v| v.as_str());
        if resp_id != Some(req_id.as_str()) {
            return Err(format!(
                "request_id mismatch: expected {}, got {:?}",
                req_id, resp_id
            ));
        }

        Ok(resp)
    }
}

fn error_message(resp: &Value) -> Option<&str> {
    resp.get("error")
        .and_then(|e| e.get("message"))
        .and_then(|m| m.as_str())
}
