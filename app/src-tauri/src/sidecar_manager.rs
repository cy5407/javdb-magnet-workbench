//! Long-running Python sidecar daemon manager.
//!
//! Bridges the Tauri plugin-shell `Receiver<CommandEvent>` event stream to a
//! request/response API: each public method writes one JSON line to the
//! daemon's stdin and awaits the next JSON line on stdout.
//!
//! Concurrency: a single `tokio::sync::Mutex` serializes all requests; the
//! daemon's dispatch loop is itself single-threaded synchronous (M3 contract).
//!
//! Liveness (M9 Phase 8-A1): each `request()` is bounded by `REQUEST_TIMEOUT_SECS`.
//! On timeout, EOF, or any protocol-corruption error (parse failure, request_id
//! mismatch) the manager transitions to a permanent dead state via `mark_dead`;
//! every subsequent call fails fast and the user must restart the app. No
//! auto-respawn, no cancel-bypass.

use std::sync::Arc;
use std::time::Duration;

use serde_json::{json, Value};
use tauri::{async_runtime::Mutex, AppHandle};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;
use tokio::sync::mpsc;

const PROTOCOL_VERSION: u32 = 1;
const REQUEST_TIMEOUT_SECS: u64 = 60;

pub struct SidecarManager {
    inner: Arc<Mutex<SidecarInner>>,
}

struct SidecarInner {
    child: Option<CommandChild>,
    line_rx: mpsc::UnboundedReceiver<String>,
    request_counter: u64,
    dead: Option<String>,
}

impl SidecarInner {
    /// Best-effort kill child + persist failure reason. Returns `reason` so
    /// callers can write `return Err(inner.mark_dead(...))` in one line.
    fn mark_dead(&mut self, reason: String) -> String {
        if let Some(child) = self.child.take() {
            let _ = child.kill();
        }
        self.dead = Some(reason.clone());
        reason
    }
}

impl Drop for SidecarInner {
    fn drop(&mut self) {
        if let Some(child) = self.child.take() { let _ = child.kill(); }
    }
}

fn timeout_error(cmd: &str) -> String {
    format!("sidecar request '{cmd}' timed out after {REQUEST_TIMEOUT_SECS}s; restart the app to recover")
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
                child: Some(child),
                line_rx,
                request_counter: 0,
                dead: None,
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
        if let Some(reason) = &inner.dead {
            return Err(format!("sidecar is dead: {reason}"));
        }
        inner.request_counter += 1;
        let req_id = format!("r-{}", inner.request_counter);

        let mut obj = match body {
            Value::Object(map) => map,
            Value::Null => Default::default(),
            other => return Err(format!("request body must be a JSON object or null, got {other}")),
        };
        obj.insert("cmd".to_string(), Value::String(cmd.to_string()));
        obj.insert("request_id".to_string(), Value::String(req_id.clone()));

        let line = serde_json::to_string(&Value::Object(obj))
            .map_err(|e| format!("serialize failed: {e}"))?;
        let mut bytes = line.into_bytes();
        bytes.push(b'\n');

        let write_result = match inner.child.as_mut() {
            Some(child) => child.write(&bytes),
            None => return Err(inner.mark_dead("child handle missing".to_string())),
        };
        if let Err(e) = write_result {
            return Err(inner.mark_dead(format!("stdin write failed: {e}")));
        }

        let recv = tokio::time::timeout(
            Duration::from_secs(REQUEST_TIMEOUT_SECS),
            inner.line_rx.recv(),
        )
        .await;

        // Any terminal failure here is treated as protocol-corruption: kill
        // the child and stay dead so subsequent calls fail fast (vs. queueing
        // behind a mutex held by a hung await, or desync'ing the line stream).
        let response_line = match recv {
            Err(_elapsed) => return Err(inner.mark_dead(timeout_error(cmd))),
            Ok(None) => return Err(inner.mark_dead("sidecar closed before response".to_string())),
            Ok(Some(line)) => line,
        };

        let resp: Value = match serde_json::from_str(&response_line) {
            Ok(v) => v,
            Err(e) => return Err(inner.mark_dead(format!("response parse failed: {e}"))),
        };

        let resp_id = resp.get("request_id").and_then(|v| v.as_str());
        if resp_id != Some(req_id.as_str()) {
            return Err(inner.mark_dead(format!(
                "request_id mismatch: expected {req_id}, got {resp_id:?}"
            )));
        }

        Ok(resp)
    }
}

fn error_message(resp: &Value) -> Option<&str> {
    resp.get("error")
        .and_then(|e| e.get("message"))
        .and_then(|m| m.as_str())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn mark_dead_records_reason_and_is_idempotent() {
        let (_tx, line_rx) = mpsc::unbounded_channel::<String>();
        let mut inner = SidecarInner {
            child: None, // can't construct a real CommandChild in unit test
            line_rx,
            request_counter: 0,
            dead: None,
        };
        let returned = inner.mark_dead("boom".to_string());
        assert_eq!(returned, "boom");
        assert_eq!(inner.dead.as_deref(), Some("boom"));
        // Idempotency: second call overwrites with new reason.
        let returned2 = inner.mark_dead("again".to_string());
        assert_eq!(returned2, "again");
        assert_eq!(inner.dead.as_deref(), Some("again"));
    }

    #[test]
    fn timeout_error_names_the_command() {
        let msg = timeout_error("rd_send_magnet");
        assert!(msg.contains("rd_send_magnet"), "got: {msg}");
        assert!(msg.contains("restart the app"), "got: {msg}");
    }
}
