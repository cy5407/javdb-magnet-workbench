mod commands;
mod cookie_store;
mod path_manager;
mod pending;
mod legacy_import;
mod secret_store;
mod settings;
mod sidecar_manager;

use serde_json::{json, Value};
use tauri::Manager;

use path_manager::PathManager;
use sidecar_manager::SidecarManager;

const STORE_FILE: &str = "settings.json";

/// Upper bound on `cookies.txt` we'll load into memory at handshake.
/// A real JavDB cookie blob is a few hundred bytes; 64 KiB is two orders of
/// magnitude of slack. Anything past this is either a corrupted file or an
/// accidental paste of the wrong content (HTML page dump, log output, etc.)
/// and refusing it keeps the sidecar handshake from ballooning a multi-MB
/// string into the Python process for no benefit.
const COOKIES_MAX_BYTES: u64 = 64 * 1024;

/// Read on-disk handshake inputs from the data dir. Missing files are not
/// errors — the sidecar accepts empty cookies (subsequent fetch_javdb will
/// surface a cloudflare_block) and an empty settings/token snapshot.
///
/// Token sourcing in M5+:
///
/// 1. OS credential store (preferred)
/// 2. Legacy `settings.rd.api_token` field — kept ONLY for the M4→M5
///    migration. If found, we copy it into the credential store and
///    blank the JSON field, so subsequent reads come from the secure
///    backend. The value is never returned to the frontend.
fn load_handshake_inputs(path_manager: &PathManager) -> (String, Option<String>, Value) {
    let cookies = load_cookies(path_manager);

    let settings_path = path_manager.data_dir.join(STORE_FILE);
    let settings_value = std::fs::read_to_string(&settings_path)
        .ok()
        .and_then(|s| serde_json::from_str::<Value>(&s).ok())
        .and_then(|v| v.get("settings").cloned())
        .unwrap_or(Value::Object(Default::default()));

    // Token: credential store first; otherwise migrate from legacy JSON.
    let rd_token = match secret_store::get_rd_token() {
        Ok(Some(t)) if !t.is_empty() => Some(t),
        _ => migrate_legacy_token(path_manager, &settings_value),
    };

    (cookies, rd_token, settings_value)
}

/// Resolve cookies for the sidecar handshake.
///
/// Source-of-truth precedence:
///   1. If `cookies.txt` exists AND contains a real cookie pair (not just
///      the template scaffold) → take that as the authoritative value,
///      write it to the OS credential store via [`cookie_store::set_cookies`],
///      and remove the plaintext file. This is the "user just refreshed
///      cf_clearance" path.
///   2. Else → fall back to the credential store. This is the steady-state
///      after the one-shot migration above.
///   3. Else → empty cookies. Sidecar surfaces `cloudflare_block` on the
///      first JavDB fetch, which is the right user-facing signal.
///
/// Failures are logged to stderr but do not abort the handshake — losing
/// JavDB cookies degrades to "needs re-paste", not "app unusable".
fn load_cookies(path_manager: &PathManager) -> String {
    let cookies_path = path_manager.data_dir.join("cookies.txt");

    if let Some(migrated) = migrate_cookies_from_file(&cookies_path) {
        return migrated;
    }

    cookie_store::get_cookies()
        .unwrap_or_else(|e| {
            eprintln!("[handshake] cookie keyring read failed: {e}");
            None
        })
        .unwrap_or_default()
}

/// Read `cookies.txt`, refuse files larger than [`COOKIES_MAX_BYTES`],
/// and — if the content has a real (non-template) cookie pair — migrate
/// it into the credential store + remove the plaintext file. Returns the
/// migrated cookie value, or `None` if nothing was migrated (caller falls
/// back to the credential store).
///
/// File deletion is best-effort: keyring write success is what matters for
/// the security invariant. If the OS refuses the delete (FS busy, AV lock,
/// read-only mount), the keyring already has the value and the next
/// handshake will re-migrate idempotently.
///
/// Visible to the `commands` module (and tests) so the "重新整理 / 套用變更"
/// Tauri command can re-run this without the user having to restart the app.
pub(crate) fn migrate_cookies_from_file(cookies_path: &std::path::Path) -> Option<String> {
    let meta = std::fs::metadata(cookies_path).ok()?;
    if meta.len() > COOKIES_MAX_BYTES {
        eprintln!(
            "[handshake] cookies.txt at {} is {} bytes (> {} cap); refusing to load",
            cookies_path.display(),
            meta.len(),
            COOKIES_MAX_BYTES,
        );
        return None;
    }

    let raw = std::fs::read_to_string(cookies_path).ok()?;
    if !cookie_store::file_has_real_cookies(&raw) {
        // File is still just the template scaffold (or otherwise comment-only).
        // Leave it in place; nothing to migrate.
        return None;
    }
    // Pull just the cookie pairs out of the file — the template's Chinese
    // comment header alone is ~2 KiB, and Windows Credential Manager caps
    // generic-credential blobs around 2.5 KiB. Without this extraction step
    // a real user install reproducibly fails the keyring write, silently
    // leaves cookies.txt on disk, and the UI stays stuck in `"file"` state.
    let extracted = cookie_store::extract_cookie_lines(&raw);
    if extracted.is_empty() {
        // Belt-and-suspenders: file_has_real_cookies should have caught
        // this, but if a future refactor desyncs the two checks, refuse
        // to write an empty string (which delete_cookies would treat as
        // a clear gesture and wipe a previously-good entry).
        return None;
    }

    if let Err(e) = cookie_store::set_cookies(&extracted) {
        eprintln!(
            "[handshake] keyring write for cookies failed ({e}); falling back to file"
        );
        // We still want the sidecar to function this session — return the
        // file value so JavDB fetch works while the user fixes the keyring.
        return Some(extracted);
    }

    if let Err(e) = std::fs::remove_file(cookies_path) {
        // Keyring already has the value; on next launch the file's still
        // here so we'll re-migrate. Idempotent.
        eprintln!(
            "[handshake] cookies migrated to keyring but file delete failed: {e}"
        );
    }
    Some(extracted)
}

/// One-shot migration: pull `settings.rd.api_token` (legacy plaintext) into
/// the credential store, then rewrite the JSON file with the field cleared.
/// Returns the migrated token (so the first sidecar handshake still has
/// it) or None if there was nothing to migrate.
///
/// A malformed legacy value (anything that fails
/// [`secret_store::is_valid_rd_token`]) is left in place untouched: we do
/// NOT write it to the keyring and we do NOT blank the JSON field, so
/// the user can see what was rejected and fix it. Returning a malformed
/// token here would have it flow into the first sidecar handshake and
/// straight into a Real-Debrid API call (F-04 cross-path leak); the
/// sidecar's handshake-side guard will also drop it, but defence in
/// depth keeps the dirty value out of the credential store on the next
/// run as well.
fn migrate_legacy_token(path_manager: &PathManager, settings_value: &Value) -> Option<String> {
    let token = settings_value
        .get("rd")
        .and_then(|r| r.get("api_token"))
        .and_then(|t| t.as_str())
        .filter(|s| !s.is_empty())?
        .to_string();

    if !secret_store::is_valid_rd_token(&token) {
        eprintln!(
            "[migrate] legacy settings.rd.api_token does not match Real-Debrid \
             token format; leaving the plaintext field intact and skipping the \
             keyring write so the dirty value cannot reach the sidecar"
        );
        return None;
    }

    if let Err(e) = secret_store::set_rd_token(&token) {
        eprintln!("[migrate] keyring write failed, leaving plaintext: {e}");
        return Some(token);
    }
    // Best-effort scrub of the on-disk plaintext copy. tauri-plugin-store
    // owns the file format so we re-read the wrapper, blank the field,
    // and write the wrapper back.
    let store_path = path_manager.data_dir.join(STORE_FILE);
    if let Ok(raw) = std::fs::read_to_string(&store_path) {
        if let Ok(mut wrapper) = serde_json::from_str::<Value>(&raw) {
            if let Some(s) = wrapper
                .get_mut("settings")
                .and_then(|v| v.get_mut("rd"))
                .and_then(|r| r.get_mut("api_token"))
            {
                *s = Value::String(String::new());
                if let Ok(body) = serde_json::to_string_pretty(&wrapper) {
                    let _ = std::fs::write(&store_path, body);
                }
            }
        }
    }
    Some(token)
}

// Test module is declared here (before `pub fn run()` at file end) because
// the Tauri entry point conventionally sits last. Suppress the clippy lint
// that prefers tests-at-bottom.
#[allow(clippy::items_after_test_module)]
#[cfg(test)]
mod tests {
    use super::*;
    use std::env;
    use std::fs;
    use std::sync::atomic::{AtomicUsize, Ordering};

    fn temp_data_dir() -> PathManager {
        static COUNTER: AtomicUsize = AtomicUsize::new(0);
        let id = COUNTER.fetch_add(1, Ordering::SeqCst);
        let root = env::temp_dir().join(format!(
            "javdbmagnet-migrate-test-{}-{}",
            std::process::id(),
            id
        ));
        let _ = fs::remove_dir_all(&root);
        let data_dir = root.join("data");
        let log_dir = root.join("logs");
        fs::create_dir_all(&data_dir).unwrap();
        fs::create_dir_all(&log_dir).unwrap();
        PathManager { data_dir, log_dir }
    }

    /// Build a settings-wrapper JSON whose `rd.api_token` is `token` and
    /// drop it into `<data_dir>/settings.json`. Returns the parsed
    /// `settings` value (what `load_handshake_inputs` would feed to
    /// `migrate_legacy_token`).
    fn write_wrapper(pm: &PathManager, token: &str) -> Value {
        let wrapper = json!({
            "settings": {
                "rd": {"api_token": token, "file_pick": "smart"},
                "ui": {"theme": "dark"},
            }
        });
        fs::write(
            pm.data_dir.join(STORE_FILE),
            serde_json::to_string_pretty(&wrapper).unwrap(),
        )
        .unwrap();
        wrapper.get("settings").cloned().unwrap()
    }

    #[test]
    fn migrate_legacy_token_skips_invalid_value_and_keeps_settings_intact() {
        // A malformed legacy token (here: a dash, which is the canonical
        // bad-paste shape) must NOT be migrated. The keyring must not be
        // touched and settings.json must be left exactly as we wrote it
        // so the user can see the dirty value and fix it. Otherwise a
        // future `load_handshake_inputs` call would still try to feed
        // the dirty value through `migrate_legacy_token` again — by
        // leaving it intact we keep the invariant local.
        let pm = temp_data_dir();
        let bad = "abc-123";
        let before = write_wrapper(&pm, bad);
        let raw_before = fs::read_to_string(pm.data_dir.join(STORE_FILE)).unwrap();

        let result = migrate_legacy_token(&pm, &before);
        assert!(
            result.is_none(),
            "invalid token must NOT be returned to the sidecar handshake; got {result:?}"
        );

        let raw_after = fs::read_to_string(pm.data_dir.join(STORE_FILE)).unwrap();
        assert_eq!(
            raw_before, raw_after,
            "settings.json must be byte-identical when migration is skipped"
        );
        // And the dirty token must still be on disk for the user to fix
        // (i.e. we did NOT blank it).
        assert!(
            raw_after.contains(bad),
            "expected dirty token '{bad}' to remain in settings.json; got: {raw_after}"
        );
    }

    #[test]
    fn migrate_legacy_token_no_token_returns_none_without_modifying_settings() {
        // Empty / absent api_token is the steady-state for a fresh
        // install; must be a no-op (no warning, no I/O on settings.json).
        let pm = temp_data_dir();
        let before = write_wrapper(&pm, "");
        let raw_before = fs::read_to_string(pm.data_dir.join(STORE_FILE)).unwrap();
        assert!(migrate_legacy_token(&pm, &before).is_none());
        let raw_after = fs::read_to_string(pm.data_dir.join(STORE_FILE)).unwrap();
        assert_eq!(raw_before, raw_after);
    }

    #[test]
    fn migrate_cookies_no_file_returns_none() {
        // No cookies.txt → migration is a no-op, caller falls back to
        // the credential store (or empty cookies if neither has it).
        let pm = temp_data_dir();
        let result = migrate_cookies_from_file(&pm.data_dir.join("cookies.txt"));
        assert!(result.is_none());
    }

    #[test]
    fn migrate_cookies_template_only_file_is_not_migrated() {
        // The "create template" button writes a scaffold containing only
        // comments + an empty trailing line. Migration MUST NOT fire on
        // this — otherwise the first app launch after creating the
        // template would clobber a perfectly good keyring value.
        let pm = temp_data_dir();
        let path = pm.data_dir.join("cookies.txt");
        fs::write(
            &path,
            "# JavDBMagnet cookies.txt\n\
             # ====\n\
             # _jdb_session=XXX; cf_clearance=XXX; locale=zh\n\
             # === 在下面貼上你的 cookie 整行 ===\n\
             \n",
        )
        .unwrap();
        assert!(migrate_cookies_from_file(&path).is_none());
        // And the file must still be on disk so the user can edit it.
        assert!(path.exists());
    }

    #[test]
    fn migrate_cookies_refuses_oversized_file() {
        // > COOKIES_MAX_BYTES — refused. File stays in place so the user
        // can inspect and shrink it; sidecar gets empty cookies and the
        // first fetch surfaces cloudflare_block.
        let pm = temp_data_dir();
        let path = pm.data_dir.join("cookies.txt");
        let oversized = "x".repeat((COOKIES_MAX_BYTES + 1) as usize);
        fs::write(&path, &oversized).unwrap();
        assert!(migrate_cookies_from_file(&path).is_none());
        assert!(
            path.exists(),
            "oversized file must remain so the user can fix it"
        );
    }
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
            commands::copy_rd_links_bulk,
            commands::forget_magnets,
            commands::register_magnets,
            commands::rd_has_token,
            commands::rd_test_token,
            commands::rd_save_token,
            commands::rd_clear_token,
            commands::rd_check_user,
            commands::rd_send_magnet,
            commands::rd_check_pending,
            commands::pending_list,
            commands::pending_remove,
            commands::pending_clear,
            commands::get_legacy_default_dir,
            commands::preview_legacy_import,
            commands::apply_legacy_import,
            commands::get_cookies_status,
            commands::migrate_cookies_now,
            commands::save_cookies,
            commands::create_cookies_template,
            commands::open_data_dir,
            commands::open_logs_dir,
            commands::update_sidecar_settings,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
