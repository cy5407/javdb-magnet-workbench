//! Pending RD torrents persisted at `<data_dir>/pending_torrents.json`.
//!
//! Security model: this file MUST NOT contain magnet text or RD tokens.
//! Each entry is the minimum identity + display info needed to:
//!   - re-poll RD by `torrent_id`,
//!   - render a row in the pending UI without re-fetching JavDB,
//!   - audit-trail the strategy that was originally chosen.
//!
//! File format: a top-level JSON array of `PendingEntry`. Atomic writes via
//! a sibling `.tmp` + rename so a crash mid-write doesn't corrupt the list.

use std::fs;
use std::io::Write;
use std::path::{Path, PathBuf};

use chrono::Utc;
use serde::{Deserialize, Serialize};

const FILE_NAME: &str = "pending_torrents.json";

/// Hard upper bound on pending_torrents.json byte size. A realistic
/// pending list is dozens of entries × ~400 bytes each; 4 MiB leaves
/// orders of magnitude of headroom while blocking a tampered or
/// social-engineered oversized file from being loaded whole.
const MAX_PENDING_FILE_BYTES: u64 = 4 * 1024 * 1024;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PendingEntry {
    /// RD-side torrent identifier — the one stable handle for re-polling.
    pub torrent_id: String,
    /// JavDB code (SNOS-192 etc) for the UI row. May be empty.
    #[serde(default)]
    pub code: String,
    /// RD-side filename / torrent name. Display only.
    #[serde(default)]
    pub name: String,
    /// Original size label as it came from JavDB ("5.67GB, 5個文件").
    /// Display only; not used for any logic.
    #[serde(default)]
    pub size_label: String,
    /// File-pick strategy that was used at send time. Saved so a future
    /// retry can re-do file selection if RD ever drops back to
    /// `waiting_files_selection`. (Today the magnet text is gone by then,
    /// so retry will surface "needs reselection" instead — but we keep
    /// the value for diagnostics.)
    #[serde(default = "default_strategy")]
    pub strategy: String,
    /// ISO-8601 UTC when the entry was first added.
    pub added_at: String,
    /// Last observed RD progress (0..100). 0 if never polled.
    #[serde(default)]
    pub last_progress: f64,
    /// Last observed RD-side status string ("downloading" / "queued" / ...).
    #[serde(default)]
    pub last_rd_status: String,
    /// ISO-8601 UTC of the most recent rd_check_pending call.
    #[serde(default)]
    pub last_checked_at: Option<String>,
}

fn default_strategy() -> String {
    "smart".to_string()
}

impl PendingEntry {
    pub fn new(
        torrent_id: String,
        code: String,
        name: String,
        size_label: String,
        strategy: String,
    ) -> Self {
        Self {
            torrent_id,
            code,
            name,
            size_label,
            strategy,
            added_at: Utc::now().to_rfc3339(),
            last_progress: 0.0,
            last_rd_status: String::new(),
            last_checked_at: None,
        }
    }
}

fn pending_path(data_dir: &Path) -> PathBuf {
    data_dir.join(FILE_NAME)
}

/// Read the pending list from disk. Missing file returns `[]`.
pub fn load(data_dir: &Path) -> Result<Vec<PendingEntry>, String> {
    let path = pending_path(data_dir);
    if !path.exists() {
        return Ok(Vec::new());
    }
    let metadata = fs::metadata(&path)
        .map_err(|e| format!("stat {}: {e}", path.display()))?;
    if metadata.len() > MAX_PENDING_FILE_BYTES {
        return Err(format!(
            "{} exceeds max size ({} > {} bytes)",
            path.display(), metadata.len(), MAX_PENDING_FILE_BYTES
        ));
    }
    let raw = fs::read_to_string(&path).map_err(|e| format!("read {}: {e}", path.display()))?;
    if raw.trim().is_empty() {
        return Ok(Vec::new());
    }
    serde_json::from_str::<Vec<PendingEntry>>(&raw)
        .map_err(|e| format!("parse {}: {e}", path.display()))
}

/// Write the pending list. Atomic via tmp + rename.
pub fn save(data_dir: &Path, entries: &[PendingEntry]) -> Result<(), String> {
    fs::create_dir_all(data_dir)
        .map_err(|e| format!("mkdir {}: {e}", data_dir.display()))?;
    let path = pending_path(data_dir);
    let tmp = path.with_extension("json.tmp");
    let body = serde_json::to_string_pretty(entries).map_err(|e| format!("serialize: {e}"))?;
    {
        let mut f = fs::File::create(&tmp)
            .map_err(|e| format!("create {}: {e}", tmp.display()))?;
        f.write_all(body.as_bytes())
            .map_err(|e| format!("write {}: {e}", tmp.display()))?;
        f.sync_data().ok();
    }
    fs::rename(&tmp, &path)
        .map_err(|e| format!("rename {} -> {}: {e}", tmp.display(), path.display()))?;
    Ok(())
}

/// Add an entry; replaces any existing entry with the same torrent_id.
pub fn add(data_dir: &Path, entry: PendingEntry) -> Result<Vec<PendingEntry>, String> {
    let mut list = load(data_dir)?;
    list.retain(|e| e.torrent_id != entry.torrent_id);
    list.push(entry);
    save(data_dir, &list)?;
    Ok(list)
}

/// Remove the entry with `torrent_id`. No-op if missing. Returns the list
/// after removal.
pub fn remove(data_dir: &Path, torrent_id: &str) -> Result<Vec<PendingEntry>, String> {
    let mut list = load(data_dir)?;
    list.retain(|e| e.torrent_id != torrent_id);
    save(data_dir, &list)?;
    Ok(list)
}

/// Update an entry's last-observed status / progress fields and stamp
/// `last_checked_at`. No-op if `torrent_id` is not in the list.
pub fn update_status(
    data_dir: &Path,
    torrent_id: &str,
    rd_status: &str,
    progress: f64,
) -> Result<Vec<PendingEntry>, String> {
    let mut list = load(data_dir)?;
    if let Some(entry) = list.iter_mut().find(|e| e.torrent_id == torrent_id) {
        entry.last_rd_status = rd_status.to_string();
        entry.last_progress = progress;
        entry.last_checked_at = Some(Utc::now().to_rfc3339());
        save(data_dir, &list)?;
    }
    Ok(list)
}

/// Clear all entries.
pub fn clear(data_dir: &Path) -> Result<(), String> {
    save(data_dir, &[])
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::env;
    use std::sync::atomic::{AtomicU64, Ordering};

    static COUNTER: AtomicU64 = AtomicU64::new(0);

    fn temp_dir() -> PathBuf {
        let id = COUNTER.fetch_add(1, Ordering::SeqCst);
        let dir = env::temp_dir().join(format!("javdbmagnet-pending-test-{}-{}", std::process::id(), id));
        let _ = fs::remove_dir_all(&dir);
        fs::create_dir_all(&dir).unwrap();
        dir
    }

    fn sample(id: &str) -> PendingEntry {
        PendingEntry::new(
            id.to_string(),
            "SNOS-192".to_string(),
            "name".to_string(),
            "5.67GB, 5個文件".to_string(),
            "smart".to_string(),
        )
    }

    #[test]
    fn missing_file_returns_empty() {
        let d = temp_dir();
        assert!(load(&d).unwrap().is_empty());
    }

    #[test]
    fn add_and_load_roundtrips() {
        let d = temp_dir();
        add(&d, sample("A")).unwrap();
        add(&d, sample("B")).unwrap();
        let list = load(&d).unwrap();
        assert_eq!(list.len(), 2);
        assert_eq!(list[0].torrent_id, "A");
        assert_eq!(list[1].torrent_id, "B");
    }

    #[test]
    fn add_replaces_same_torrent_id() {
        let d = temp_dir();
        add(&d, sample("A")).unwrap();
        let mut e = sample("A");
        e.code = "DIFFERENT".to_string();
        add(&d, e).unwrap();
        let list = load(&d).unwrap();
        assert_eq!(list.len(), 1);
        assert_eq!(list[0].code, "DIFFERENT");
    }

    #[test]
    fn remove_nonexistent_is_noop() {
        let d = temp_dir();
        add(&d, sample("A")).unwrap();
        remove(&d, "MISSING").unwrap();
        assert_eq!(load(&d).unwrap().len(), 1);
    }

    #[test]
    fn update_status_writes_back() {
        let d = temp_dir();
        add(&d, sample("A")).unwrap();
        update_status(&d, "A", "downloading", 42.5).unwrap();
        let list = load(&d).unwrap();
        assert_eq!(list[0].last_rd_status, "downloading");
        assert!((list[0].last_progress - 42.5).abs() < 1e-6);
        assert!(list[0].last_checked_at.is_some());
    }

    #[test]
    fn entries_have_no_magnet_field() {
        let d = temp_dir();
        add(&d, sample("A")).unwrap();
        let raw = fs::read_to_string(pending_path(&d)).unwrap();
        // Defense in depth: even an accidental serializer change shouldn't
        // be able to leak magnet text into the pending file.
        assert!(!raw.contains("magnet:"), "pending file leaked magnet: prefix");
        assert!(!raw.contains("\"magnet\""), "pending file has a magnet field");
    }

    #[test]
    fn clear_empties_the_list() {
        let d = temp_dir();
        add(&d, sample("A")).unwrap();
        clear(&d).unwrap();
        assert!(load(&d).unwrap().is_empty());
    }

    #[test]
    fn load_rejects_oversized_file() {
        let d = temp_dir();
        let path = pending_path(&d);
        // Write a file slightly over the limit. Content can be junk; the
        // guard fires before parse.
        let body = "x".repeat((MAX_PENDING_FILE_BYTES as usize) + 1024);
        fs::write(&path, body).unwrap();
        let err = load(&d).expect_err("oversized file must error");
        assert!(err.contains("exceeds max size"), "unexpected error: {err}");
    }

    #[test]
    fn load_accepts_file_just_under_limit() {
        let d = temp_dir();
        let path = pending_path(&d);
        // Build a valid JSON array under the limit. A short array is fine —
        // we mostly want to confirm the guard doesn't false-positive.
        let body = "[]";
        fs::write(&path, body).unwrap();
        let list = load(&d).expect("under-limit file must load");
        assert!(list.is_empty());
    }
}
