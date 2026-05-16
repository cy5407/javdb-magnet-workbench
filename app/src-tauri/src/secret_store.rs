//! Secret storage for the RD API token.
//!
//! On Windows the token lives in the Windows Credential Manager (Generic
//! Credential, target name `JavDBMagnet/RD_API_TOKEN`). The `keyring` crate
//! routes the same calls to the right backend on macOS / Linux so the rest
//! of the app stays platform-agnostic.
//!
//! Why a credential store, not `settings.json`:
//! - settings.json is plaintext + cloud-syncable + likely to be screenshotted
//!   in support tickets;
//! - the OS credential store is the well-trodden path for Windows desktop
//!   apps, plays nicely with corporate policy, and survives an app reinstall.
//!
//! Out of scope here: JavDB cookies (still plaintext at
//! `<data_dir>/cookies.txt` for M5; DPAPI move tracked for M6/M7).

const SERVICE: &str = "JavDBMagnet";
const ACCOUNT: &str = "RD_API_TOKEN";

/// Real-Debrid API tokens are short ASCII-alphanumeric strings (52 chars
/// at time of writing). Cap at 255 chars so a paste of surrounding HTML,
/// a stray newline, or a stale OAuth blob never reaches the credential
/// store (F-04). Owned by this module so every caller — `rd_save_token`,
/// `import_rd_token`, `migrate_legacy_token` — applies the same rule and
/// no path can pollute the keyring with a malformed value.
///
/// !!! KEEP IN SYNC with the Python sidecar's `_RD_TOKEN_MAX_LEN`
/// (`sidecar/sidecar.py`). Same rule applied on both sides of the IPC.
pub const RD_TOKEN_MAX_LEN: usize = 255;

/// Pure-function format check. Empty strings are not valid here; callers
/// that want to support "clear" must check `is_empty()` themselves before
/// asking — `set_rd_token("")` is the documented clear gesture.
///
/// !!! KEEP IN SYNC with the Python sidecar's `_is_valid_rd_token`
/// (`sidecar/sidecar.py`). The two implementations MUST accept and
/// reject exactly the same strings — handshake (Python) and credential
/// store (Rust) both gate on this rule, and drift would let a token
/// pass one side but fail the other (silent UX breakage where the
/// keyring holds a value the sidecar then drops at handshake time, or
/// vice versa). If you change the rule, update both files in the same
/// commit and re-run both test suites.
pub fn is_valid_rd_token(token: &str) -> bool {
    !token.is_empty()
        && token.len() <= RD_TOKEN_MAX_LEN
        && token.chars().all(|c| c.is_ascii_alphanumeric())
}

/// Stable error code returned when a non-empty token fails `is_valid_rd_token`.
/// Mirrors the sidecar's bad_request envelope so the frontend's error
/// classifier can use one string everywhere.
pub const RD_TOKEN_FORMAT_ERR: &str = "rd_token_format_invalid";

fn entry() -> Result<keyring::Entry, String> {
    keyring::Entry::new(SERVICE, ACCOUNT).map_err(|e| format!("keyring entry: {e}"))
}

/// Persist a token. Empty string is treated as "delete". Non-empty input
/// is validated against `is_valid_rd_token` BEFORE the keyring is touched
/// so a malformed value can never overwrite a previously-good credential.
/// Returns `Err(RD_TOKEN_FORMAT_ERR.into())` if validation fails.
pub fn set_rd_token(token: &str) -> Result<(), String> {
    if !token.is_empty() && !is_valid_rd_token(token) {
        return Err(RD_TOKEN_FORMAT_ERR.to_string());
    }
    let e = entry()?;
    if token.is_empty() {
        return delete_internal(&e);
    }
    e.set_password(token).map_err(|err| format!("keyring set: {err}"))
}

/// Read the token. `Ok(None)` if no entry has been stored yet.
pub fn get_rd_token() -> Result<Option<String>, String> {
    let e = entry()?;
    match e.get_password() {
        Ok(s) => Ok(Some(s)),
        Err(keyring::Error::NoEntry) => Ok(None),
        Err(err) => Err(format!("keyring get: {err}")),
    }
}

pub fn delete_rd_token() -> Result<(), String> {
    let e = entry()?;
    delete_internal(&e)
}

fn delete_internal(e: &keyring::Entry) -> Result<(), String> {
    match e.delete_credential() {
        Ok(_) | Err(keyring::Error::NoEntry) => Ok(()),
        Err(err) => Err(format!("keyring delete: {err}")),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn is_valid_rd_token_accepts_realistic_shape() {
        // RD tokens are 52-char ASCII-alphanumeric in practice; accept
        // that and reasonable variations within the bound.
        assert!(is_valid_rd_token(&"A".repeat(52)));
        assert!(is_valid_rd_token(&"a".repeat(52)));
        assert!(is_valid_rd_token(&"0".repeat(52)));
        assert!(is_valid_rd_token(
            "AbCdEf0123456789AbCdEf0123456789AbCdEf0123456789AbCd"
        ));
        // Boundary: exactly RD_TOKEN_MAX_LEN.
        assert!(is_valid_rd_token(&"a".repeat(RD_TOKEN_MAX_LEN)));
    }

    #[test]
    fn is_valid_rd_token_rejects_format_violations() {
        // F-04: refuse anything that doesn't look like the RD token
        // shape so a paste of surrounding HTML, a stray newline, or a
        // stale OAuth blob never reaches the credential store.
        assert!(!is_valid_rd_token("")); // empty
        assert!(!is_valid_rd_token("abc-123")); // punctuation
        assert!(!is_valid_rd_token("abc 123")); // whitespace
        assert!(!is_valid_rd_token("abc\n")); // newline
        assert!(!is_valid_rd_token("abc\tdef")); // tab
        // Non-ASCII alnum (fullwidth digits are unicode-alnum).
        assert!(!is_valid_rd_token("ＡＢＣ123"));
        // 1 char over the bound.
        assert!(!is_valid_rd_token(&"a".repeat(RD_TOKEN_MAX_LEN + 1)));
    }

    #[test]
    fn set_rd_token_rejects_invalid_before_touching_keyring() {
        // The validator runs BEFORE `entry()`, so even on a CI host
        // without a usable secret service backend, a malformed token
        // must return the format error rather than a backend error.
        // This is the contract that protects every caller — if a future
        // path forgets to pre-validate, set_rd_token still refuses.
        let cases: [String; 5] = [
            "abc-123".to_string(),
            "abc 123".to_string(),
            "abc\n".to_string(),
            "ＡＢＣ123".to_string(),
            "a".repeat(RD_TOKEN_MAX_LEN + 1),
        ];
        for bad in &cases {
            let err = set_rd_token(bad).expect_err(&format!("must reject: {bad:?}"));
            assert_eq!(err, RD_TOKEN_FORMAT_ERR, "unexpected err for {bad:?}: {err}");
        }
    }
}
