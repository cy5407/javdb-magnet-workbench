//! Secret storage for the JavDB cookie blob.
//!
//! M5 moved the RD API token to the OS credential store (see
//! [`crate::secret_store`]); M9 follows up by moving the JavDB session
//! cookies (`_jdb_session` + `cf_clearance` + friends) into the same
//! backend so the plaintext `%APPDATA%\JavDBMagnet\cookies.txt` file
//! stops being a passive leak vector for:
//!   - cloud-sync redirects (OneDrive over `%APPDATA%`)
//!   - shared / multi-user machines
//!   - unencrypted backups, support-ticket screenshots
//!
//! The file remains the **user-facing edit format** — the Cloudflare /
//! JavDB cookie refresh workflow is fundamentally "open Notepad, paste
//! a Cookie header" and we don't want to break that ergonomic. Instead
//! the file is treated as a write-once scratchpad: when a real cookie
//! pair lands in it, the next handshake migrates the value into the
//! credential store and removes the plaintext file. See
//! [`crate::load_handshake_inputs`] for the migration plumbing.
//!
//! Out of scope here: format validation. Unlike the RD API token
//! (52-char ASCII alnum), a cookie header is opaque to us — JavDB
//! decides what's valid. We just enforce a generous upper bound so a
//! pasted HTML dump or log file can't balloon the credential store.

const SERVICE: &str = "JavDBMagnet";
const ACCOUNT: &str = "JAVDB_COOKIES";

/// Upper bound on what we'll accept as a cookie blob. A real JavDB
/// session header is a few hundred bytes; 64 KiB is two orders of
/// magnitude of slack. Mirrors [`crate::COOKIES_MAX_BYTES`] (the
/// handshake-time file read cap) so both sides apply the same rule.
pub const COOKIES_MAX_BYTES: usize = 64 * 1024;

/// Stable error code returned when a write exceeds [`COOKIES_MAX_BYTES`].
/// Mirrors the [`crate::secret_store::RD_TOKEN_FORMAT_ERR`] convention so
/// the frontend's error classifier can use one string everywhere.
pub const COOKIES_TOO_LARGE_ERR: &str = "cookies_too_large";

fn entry() -> Result<keyring::Entry, String> {
    keyring::Entry::new(SERVICE, ACCOUNT).map_err(|e| format!("keyring entry: {e}"))
}

/// Pure-function size check. Extracted so tests can exercise the rule
/// without touching the real OS credential store (which would otherwise
/// clobber a developer machine's actual JavDB cookies on every test run).
pub fn check_cookies_format(value: &str) -> Result<(), String> {
    if value.len() > COOKIES_MAX_BYTES {
        return Err(COOKIES_TOO_LARGE_ERR.to_string());
    }
    Ok(())
}

/// Persist a cookie blob. Empty string is treated as "delete" (mirrors
/// [`crate::secret_store::set_rd_token`]). Inputs over [`COOKIES_MAX_BYTES`]
/// are rejected BEFORE the keyring is touched so an oversized paste can
/// never overwrite a previously-good credential.
pub fn set_cookies(value: &str) -> Result<(), String> {
    check_cookies_format(value)?;
    let e = entry()?;
    if value.is_empty() {
        return delete_internal(&e);
    }
    e.set_password(value)
        .map_err(|err| format!("keyring set: {err}"))
}

/// Read the cookie blob. `Ok(None)` if no entry has been stored yet.
pub fn get_cookies() -> Result<Option<String>, String> {
    let e = entry()?;
    match e.get_password() {
        Ok(s) => Ok(Some(s)),
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(err) => Err(format!("keyring get: {err}")),
    }
}

/// Remove the keyring entry entirely. Production code never invokes this
/// directly (a "clear cookies" UI gesture would call `set_cookies("")`
/// which already delegates here), but it's pub so integration tests can
/// reset the keyring around their work — see `KeyringSandbox` in
/// `commands.rs::tests_cookies_e2e`.
#[allow(dead_code)]
pub fn delete_cookies() -> Result<(), String> {
    let e = entry()?;
    delete_internal(&e)
}

fn delete_internal(e: &keyring::Entry) -> Result<(), String> {
    match e.delete_credential() {
        Ok(_) | Err(keyring::Error::NoEntry) => Ok(()),
        Err(err) => Err(format!("keyring delete: {err}")),
    }
}

/// Does the supplied cookies.txt content look like an actual JavDB session
/// (vs. just the template scaffold)? Used by the migration path so a
/// freshly-created template — which contains only comments + an empty
/// trailing line — doesn't clobber a valid keyring entry on next launch.
///
/// Heuristic: at least one non-empty, non-comment line that contains
/// `=`. The template's only `=` lines are commented sample lines and
/// fail this check; a real `_jdb_session=...; cf_clearance=...` line
/// passes it.
pub fn file_has_real_cookies(content: &str) -> bool {
    content
        .lines()
        .map(str::trim)
        .filter(|line| !line.is_empty() && !line.starts_with('#'))
        .any(|line| line.contains('='))
}

/// Pull the actual cookie pairs out of a cookies.txt that may also contain
/// the template scaffold's comment headers.
///
/// Windows Credential Manager caps generic-credential blobs at roughly
/// 2.5 KiB — a real-world cookies.txt with all of the template's Chinese
/// instructions is ~2.5 KiB by itself, so writing the raw file content
/// to the keyring deterministically fails on real user installs (silently,
/// because `eprintln!` from a window-mode exe goes nowhere visible).
/// We avoid the cliff entirely by storing ONLY the lines that look like
/// cookie pairs (non-empty, non-comment, contains `=`), joined with the
/// header-style `"; "` separator so `parse_cookie_string` on the sidecar
/// side sees the same shape it would from a fresh `Cookie:` header paste.
///
/// Returns an empty string if no real cookie lines are present (caller
/// should already have gated on [`file_has_real_cookies`], but the empty
/// fallback keeps the contract clean).
pub fn extract_cookie_lines(content: &str) -> String {
    content
        .lines()
        .map(str::trim)
        .filter(|line| !line.is_empty() && !line.starts_with('#') && line.contains('='))
        .collect::<Vec<&str>>()
        .join("; ")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn file_has_real_cookies_rejects_template_only() {
        // Approximation of the scaffold body in commands::COOKIES_TEMPLATE:
        // comments + sample lines that start with `#`. The user has NOT
        // edited it yet — migration must NOT fire.
        let template = "# JavDBMagnet cookies.txt\n\
                        # ====\n\
                        # _jdb_session=XXX; cf_clearance=XXX; locale=zh\n\
                        # === 在下面貼上你的 cookie 整行 ===\n\
                        \n";
        assert!(!file_has_real_cookies(template));
    }

    #[test]
    fn file_has_real_cookies_accepts_edited_template() {
        // After the user pastes a real cookie line at the bottom of the
        // scaffold, migration must fire.
        let edited = "# JavDBMagnet cookies.txt\n\
                      # ====\n\
                      # _jdb_session=XXX; cf_clearance=XXX; locale=zh\n\
                      # === 在下面貼上你的 cookie 整行 ===\n\
                      _jdb_session=abc; cf_clearance=xyz; locale=zh\n";
        assert!(file_has_real_cookies(edited));
    }

    #[test]
    fn file_has_real_cookies_rejects_empty_and_whitespace() {
        assert!(!file_has_real_cookies(""));
        assert!(!file_has_real_cookies("   \n\n\t\n"));
    }

    #[test]
    fn file_has_real_cookies_rejects_comments_with_equals() {
        // A commented-out line containing `=` is not a real cookie pair.
        assert!(!file_has_real_cookies("# foo=bar\n# baz=qux\n"));
    }

    #[test]
    fn check_cookies_format_rejects_oversized() {
        // Pure rule check — does NOT touch the keyring (so a dev box's real
        // JavDB cookies cannot be accidentally overwritten by the test
        // suite). The contract: anything past COOKIES_MAX_BYTES must
        // produce COOKIES_TOO_LARGE_ERR before set_cookies even tries to
        // construct a keyring entry.
        let huge = "a".repeat(COOKIES_MAX_BYTES + 1);
        let err = check_cookies_format(&huge)
            .expect_err("must reject oversized cookies");
        assert_eq!(err, COOKIES_TOO_LARGE_ERR);
    }

    #[test]
    fn check_cookies_format_accepts_at_cap_and_smaller() {
        // Boundary: the check is strict `>`, so a value exactly at the cap
        // is allowed. Also covers a realistic-size sample to lock down the
        // "small inputs pass" branch.
        assert!(check_cookies_format(&"a".repeat(COOKIES_MAX_BYTES)).is_ok());
        assert!(check_cookies_format("_jdb_session=abc; cf_clearance=xyz").is_ok());
        assert!(check_cookies_format("").is_ok()); // empty is "clear", not "invalid format"
    }

    #[test]
    fn extract_cookie_lines_strips_template_comments() {
        // The migration's job: a cookies.txt that's mostly the template
        // scaffold's Chinese instructions PLUS one real cookie line at the
        // bottom (~2.5 KiB total, over Windows Credential Manager's blob
        // cap) must reduce down to just the cookie line that fits.
        let real_paste = "_jdb_session=abc123; cf_clearance=xyz789; locale=zh";
        let messy = format!(
            "# JavDBMagnet cookies.txt\n\
             # ====\n\
             # 把你的 JavDB 登入 cookie 貼到本檔最後一行\n\
             #\n\
             # 範例 (不要直接貼這行):\n\
             # _jdb_session=XXX; cf_clearance=XXX; locale=zh\n\
             # === 在下面貼上你的 cookie 整行 ===\n\
             \n\
             {real_paste}\n",
        );
        assert_eq!(extract_cookie_lines(&messy), real_paste);
        // And the extracted size is far below the Windows credential cap,
        // even when the source file is well past it.
        assert!(extract_cookie_lines(&messy).len() < 256);
    }

    #[test]
    fn extract_cookie_lines_joins_multi_line_cookie_blocks() {
        // A user who pastes one cookie per line (some browsers' "copy as
        // cookies" output is structured this way) still produces a single
        // semicolon-separated string the sidecar's parser understands.
        let content = "_jdb_session=abc\ncf_clearance=xyz\nlocale=zh";
        assert_eq!(
            extract_cookie_lines(content),
            "_jdb_session=abc; cf_clearance=xyz; locale=zh",
        );
    }

    #[test]
    fn extract_cookie_lines_template_only_yields_empty_string() {
        // Symmetric with `file_has_real_cookies`: a freshly-created
        // template (no edits yet) has zero real cookie lines, so the
        // extraction is empty. Caller should never reach this branch in
        // practice — `file_has_real_cookies` gates the migration first —
        // but the empty-output contract keeps the function safe to use.
        let template_only = "# JavDBMagnet cookies.txt\n\
                             # ====\n\
                             # _jdb_session=XXX; cf_clearance=XXX\n\
                             # === 在下面貼上你的 cookie 整行 ===\n\n";
        assert_eq!(extract_cookie_lines(template_only), "");
    }
}
