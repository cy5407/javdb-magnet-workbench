//! Guards the sidecar spawn wiring, not just the `sidecar_env` helper: the
//! command `spawn_and_handshake` runs must carry `JAVDB_LOG_DIR`, because the
//! sidecar configures logging before it reads the handshake's `paths.log_dir`.
//! Dropping `.envs(...)` from `sidecar_command` turns this red.
//!
//! An integration test rather than a lib unit test: building a mock App links
//! comctl32's `TaskDialogIndirect`, which needs the Common Controls v6
//! manifest. build.rs embeds it into test-target executables only.

use javdbmagnet_lib::sidecar_command;
use serde_json::json;
use tauri::test::{mock_builder, mock_context, noop_assets, MockRuntime};
use tauri_plugin_shell::process::Command;

fn mock_app_with_shell() -> tauri::App<MockRuntime> {
    mock_builder()
        .plugin(tauri_plugin_shell::init())
        .build(mock_context(noop_assets()))
        .expect("mock app")
}

fn command_env(cmd: Command) -> Vec<(String, Option<String>)> {
    let std_cmd: std::process::Command = cmd.into();
    std_cmd
        .get_envs()
        .map(|(k, v)| {
            (
                k.to_string_lossy().into_owned(),
                v.map(|v| v.to_string_lossy().into_owned()),
            )
        })
        .collect()
}

#[test]
fn sidecar_command_carries_javdb_log_dir() {
    let app = mock_app_with_shell();
    let cmd = sidecar_command(app.handle(), &json!({"log_dir": "/tmp/logs"}))
        .expect("sidecar command");
    assert_eq!(
        command_env(cmd),
        vec![("JAVDB_LOG_DIR".to_string(), Some("/tmp/logs".to_string()))],
    );
}

#[test]
fn sidecar_command_sets_no_env_without_log_dir() {
    let app = mock_app_with_shell();
    let cmd = sidecar_command(app.handle(), &json!({})).expect("sidecar command");
    assert!(command_env(cmd).is_empty());
}
