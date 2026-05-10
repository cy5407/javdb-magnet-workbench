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

fn entry() -> Result<keyring::Entry, String> {
    keyring::Entry::new(SERVICE, ACCOUNT).map_err(|e| format!("keyring entry: {e}"))
}

/// Persist a token. Empty string is treated as "delete".
pub fn set_rd_token(token: &str) -> Result<(), String> {
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
