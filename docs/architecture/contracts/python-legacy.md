# Python core modules — function contracts

> Reference for the Python modules in the repo, split by their current status after M9 Phase 5-B:
>
> - **LIVE in `sidecar.exe`** (loaded by the JSONL daemon): `app_logging.py`, `realdebrid.py`, `javdb_scraper.py`. These three modules are bundled by `spikes/pyinstaller_sidecar/build_sidecar.py` and have first-class contract documentation here.
> - **RETIRED, kept under `legacy/`**: `legacy/javdb_magnet_gui.py` (the pre-Tauri Tk desktop app). Documented as an overview only — the live source is the canonical reference; this doc just orients readers.
> - **REMOVED in M9**: `javdb_magnet.py` (standalone CLI, was never imported by anything; deleted in Phase 2). `build.py` (legacy Tk PyInstaller build; replaced by `scripts/build-release.ps1` + `build_sidecar.py`; deleted in Phase 2).
>
> Cross-language flows (e.g. how `cmd_fetch_javdb` in `sidecar/sidecar.py` reaches `javdb_scraper.fetch_magnets` from the Rust backend) are documented in [`../function-contracts.md`](../function-contracts.md). This file documents the Python side only.

---

## 1. Overview

### 1.1 Module dependency graph (M9)

```
                     ┌──────────────────┐
                     │  app_logging.py  │  LIVE; stdlib only
                     └────────▲─────────┘
                              │
                ┌─────────────┴─────────┐
                │                       │
        ┌───────┴──────┐        ┌───────┴─────────────┐
        │ realdebrid   │ LIVE   │ javdb_scraper.py    │ LIVE (M9 Phase 5-A;
        │     .py      │        │  HTTP+parse only,    │  extracted from the
        └──────▲───────┘        │  no Tk/app_logging)  │  retired Tk GUI)
               │                └─────────▲────────────┘
               └────────────────┬─────────┘
                                │
                        ┌───────┴──────┐
                        │ sidecar/     │  Tauri-callable JSONL daemon
                        │  sidecar.py  │  (entry for sidecar.exe)
                        └──────────────┘


                     ┌──────────────────────────────┐
                     │ legacy/javdb_magnet_gui.py   │  RETIRED M9 Phase 5-B
                     │   (Tk desktop app; main      │  - no production importer
                     │    window + dialogs + DPI)   │  - only test_app_logging.py
                     └──────────────────────────────┘     touches it via importlib
```

Imports observed (M9 state):

- `app_logging.py` — stdlib only. Used by `realdebrid.py` and `sidecar/sidecar.py`. Lazy `setup_logging()` (no I/O at import time).
- `javdb_scraper.py` — `requests`, `curl_cffi.requests` (optional), `bs4.BeautifulSoup`, `re`. No internal deps. **Zero `app_logging` / `realdebrid` / `tkinter` imports** — pure library.
- `realdebrid.py` — `requests`; imports `app_logging.get_logger`.
- `sidecar/sidecar.py` — `from javdb_scraper import create_session, fetch_magnets` (M9; was `javdb_magnet_gui` pre-M9); also `from app_logging import setup_logging` and `from realdebrid import RealDebrid, RealDebridError`.
- `legacy/javdb_magnet_gui.py` — historical: imports `tkinter`, `requests`, `curl_cffi.requests` (optional), `bs4`, optional `sv_ttk`, `app_logging.{setup_logging,get_logger,app_dir,get_log_file}`, `realdebrid.{RealDebrid,RealDebridError,load_env}`. Not imported by any production module.

### 1.2 Entry points

| Entry | Trigger |
| --- | --- |
| `sidecar/sidecar.py` `if __name__ == "__main__"` | The JSONL daemon spawned by Tauri. See [`sidecar-runtime.md`](sidecar-runtime.md). |
| [`legacy/javdb_magnet_gui.py` ~line 1485](../../../legacy/javdb_magnet_gui.py) `if __name__ == "__main__"` | Tkinter desktop app boot. **Retired** — kept for historical reference. |

### 1.3 What ships where (M9)

| File | Bundled into `sidecar.exe` (current) | Notes |
| --- | --- | --- |
| `app_logging.py` | ✅ | `setup_logging()` is lazy. |
| `realdebrid.py` | ✅ | `RealDebrid` + `RealDebridError` + `load_env` used by `cmd_rd_*`. |
| `javdb_scraper.py` | ✅ | Provides `create_session`, `fetch_magnets`, `parse_size_gb`, `parse_file_count` for `cmd_fetch_javdb`. |
| `legacy/javdb_magnet_gui.py` | ❌ | M9 Phase 5-A removed the `--hidden-import` for it; PyInstaller no longer drags Tk/ttk/messagebox into the bundle (-3.02 MiB). |

The retired Tk path used to ship as `JavDBMagnet.exe` via `build.py`; both that build script and the standalone CLI `javdb_magnet.py` were deleted in Phase 2.

### 1.4 Disk artifacts touched at runtime

| Path | Producer / Consumer | Notes |
| --- | --- | --- |
| `app_dir()/cookies.txt` | Historically read by `legacy/javdb_magnet_gui.py::load_cookies`. **The live sidecar reads cookies from the `cmd_handshake` JSONL message instead**, not from disk — the cookies file is owned by the Rust backend (`commands.rs::cookies_status` + `secret_store.rs`). |
| `app_dir()/.env` | Historically read by `realdebrid.load_env`; written by `legacy/javdb_magnet_gui.py::write_env`. **The live sidecar receives settings via `cmd_handshake` / `cmd_update_settings`** — settings file is owned by Rust (`settings.rs`). `realdebrid.load_env` is still in `realdebrid.py` but only called by the retired GUI. |
| `app_dir()/pending_torrents.json` | Historically read/written by the retired GUI. **Pending state is now Rust-owned** (`pending.rs`). |
| `${JAVDB_LOG_DIR}` or `%LOCALAPPDATA%\JavDBMagnet\logs\debug.log` | `RotatingFileHandler` from `setup_logging` | 5 MB × 3 backups. Falls back to console-only if all candidates fail. Live in both Rust path discovery and sidecar process. |

---

## 2. `app_logging.py`

Centralized logging setup with **lazy initialization** (M1 A-blocker fix: no mkdir / no file open at import time).

### `app_dir() -> Path`  *([app_logging.py:23](../../../app_logging.py#L23))*

**Purpose**: Return the directory the app is "installed" in — next to the `.exe` when frozen, else next to the source file.

**Contract**:
- Params: none.
- Returns: `pathlib.Path` to the application directory.
- Side effects: none.
- Raises: none in normal use.
- Threading: thread-safe (pure function over module-level state).

**Calls**: `sys.executable`, `Path(__file__).parent`.

**Called by**:
- [legacy/javdb_magnet_gui.py:36-38](../../../legacy/javdb_magnet_gui.py#L36) at module load to compute `COOKIE_FILE`, `ENV_FILE`, `PENDING_FILE`.
- `sidecar/sidecar.py` for resolving paths in the handshake.

---

### `_candidate_log_dirs() -> list[Path]`  *([app_logging.py:34](../../../app_logging.py#L34))*

**Purpose**: Return ordered fallback list of log directories: `JAVDB_LOG_DIR` env override → `%LOCALAPPDATA%\JavDBMagnet\logs`.

**Contract**:
- Params: none.
- Returns: list of candidate `Path`s. May be empty (then logging is console-only).
- Side effects: reads env vars only. Deliberately **excludes** `app_dir()/logs` to avoid the A-blocker on read-only deploys.
- Raises: none.
- Threading: safe (read-only).

**Calls**: `os.environ.get`.

**Called by**: [`setup_logging`](#setup_loggingdebug-bool--false---path-app_loggingpy64).

---

### `_try_make_dir(p) -> Path | None`  *([app_logging.py:52](../../../app_logging.py#L52))*

**Purpose**: `mkdir -p` then probe-write `.write_probe` to confirm directory is actually writable.

**Contract**:
- Params: `p: Path` candidate dir.
- Returns: `p` if writable, else `None`.
- Side effects: creates dir; writes & deletes `.write_probe` file.
- Raises: catches `OSError` and returns `None`.
- Threading: safe (no shared state).

**Calls**: `Path.mkdir`, `Path.write_text`, `Path.unlink`.

**Called by**: [`setup_logging`](#setup_loggingdebug-bool--false---path-app_loggingpy64).

---

### `setup_logging(debug: bool = False) -> Path`  *([app_logging.py:64](../../../app_logging.py#L64))*

**Purpose**: Initialize root logger with rotating file handler + stderr console handler. Idempotent.

**Contract**:
- Params: `debug: bool` — also accepts env `DEBUG=1`. Raises console handler level to `DEBUG`.
- Returns: resolved log-file `Path`. Falls back to `Path("debug.log")` if all candidates fail (console-only mode still active).
- Side effects:
  - Mutates global `_initialized` / `_resolved_log_file`.
  - Clears root logger handlers and re-adds them.
  - Creates log directory + file (`debug.log`).
  - Downgrades `urllib3` / `requests` loggers to WARNING.
- Raises: none — all I/O exceptions caught; degrades to console-only.
- Threading: **not safely re-entrant** (mutates globals + root logger handlers). Should be called once at startup before threads are spawned.

**Calls**:
- internal: `_candidate_log_dirs()`, `_try_make_dir()`.
- external: `logging.getLogger`, `RotatingFileHandler(maxBytes=5 MiB, backupCount=3)`, `logging.StreamHandler(sys.stderr)`, `logging.Formatter`.

**Called by**:
- [legacy/javdb_magnet_gui.py:1465](../../../legacy/javdb_magnet_gui.py#L1465) main entry.
- `sidecar/sidecar.py` startup.
- `tests/test_app_logging.py`.

---

### `get_logger(name: str) -> logging.Logger`  *([app_logging.py:129](../../../app_logging.py#L129))*

**Purpose**: Thin wrapper for `logging.getLogger`.

**Contract**:
- Params: `name: str` — usually `__name__`.
- Returns: `logging.Logger`.
- Side effects: none beyond stdlib's logger registry lookup.
- Raises: none.
- Threading: safe.

**Calls**: `logging.getLogger(name)`.

**Called by**: top of [realdebrid.py:14](../../../realdebrid.py#L14), [legacy/javdb_magnet_gui.py:31](../../../legacy/javdb_magnet_gui.py#L31), `sidecar/sidecar.py`.

---

### `get_log_file() -> Path | None`  *([app_logging.py:133](../../../app_logging.py#L133))*

**Purpose**: Retrieve the resolved log file path (after `setup_logging` ran).

**Contract**:
- Params: none.
- Returns: `Path` or `None` (if `setup_logging` not yet called).
- Side effects: none.
- Raises: none.
- Threading: safe.

**Calls**: reads module-level `_resolved_log_file`.

**Called by**: `App.open_log` (in retired GUI) in the GUI ("查看日誌" button).

---

## 4. `realdebrid.py`

Real-Debrid REST client. All HTTP calls go through `RealDebrid._request`.

### Module-level

- `API_BASE = "https://api.real-debrid.com/rest/1.0"`.
- `VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".wmv", ".mov", ".m4v", ".ts", ".webm"}` — used by `pick_files`.
- `logger = get_logger(__name__)`.

### `load_env(path: Path) -> dict[str, str]`  *([realdebrid.py:20](../../../realdebrid.py#L20))*

**Purpose**: Minimal `.env` parser. Comments (`#`) and blank lines ignored. Quotes stripped.

**Contract**:
- Params: `path: Path` — absolute path to `.env`.
- Returns: `dict[str, str]`. Empty if missing.
- Side effects: reads `path`.
- Raises: would propagate `UnicodeDecodeError` on malformed file.
- Threading: safe.

**Calls**: `Path.exists`, `Path.read_text`, `str.split`, `str.strip`.

**Called by**:
- `App.send_to_realdebrid` (in retired GUI), `App.open_retry` (in retired GUI).
- `SettingsDialog.__init__` (in retired GUI).
- [`__main__` boot](../../../legacy/javdb_magnet_gui.py#L1471) for `UI_SCALE`/`UI_THEME`.
- `sidecar/sidecar.py` for token/strategy lookup.

---

### `class RealDebridError(Exception)`  *([realdebrid.py:36](../../../realdebrid.py#L36))*

Tagged exception for all RD client failures (auth, permission, rate-limit, HTTP error, missing files, etc.).

---

### `class RealDebrid`  *([realdebrid.py:40](../../../realdebrid.py#L40))*

#### `__init__(self, token: str, min_size_mb: int = 500)`  *([realdebrid.py:41](../../../realdebrid.py#L41))*

**Purpose**: Stash bearer token in a `requests.Session`; remember the smart-strategy size threshold.

**Contract**:
- Params:
  - `token: str` — required, non-empty. Empty → `RealDebridError`.
  - `min_size_mb: int = 500` — minimum video file size for `smart` strategy.
- Returns: `RealDebrid` instance.
- Side effects: creates `requests.Session()`; sets `Authorization` header.
- Raises: `RealDebridError` if token empty.
- Threading: instance is not goroutine-safe; `requests.Session` is **not** safe to share across threads (per upstream docs). Each thread should own its `RealDebrid`.

**Called by**: GUI dialogs (`RDDialog.worker` (in retired GUI), `RetryDialog.check_worker` (in retired GUI), `SettingsDialog.test_connection` (in retired GUI)) and `sidecar/sidecar.py`.

---

#### `_request(self, method, path, _retry_count=0, **kwargs)`  *([realdebrid.py:48](../../../realdebrid.py#L48))*

**Purpose**: Single chokepoint for every RD HTTP call. Adds deadline-aware timeout（`min(30s, remaining budget)`，deadline 由 sidecar 以 `time.monotonic()` 設定並貫穿整個 command）, 401/403/429 handling（單次 Retry-After 退避受 `MAX_RETRY_AFTER_SECONDS = 10` 與剩餘預算夾制）, JSON decode, and debug logging with magnet redaction.

**Contract**:
- Params:
  - `method: str` — HTTP verb.
  - `path: str` — joined onto `API_BASE`.
  - `_retry_count: int` — internal counter for 429 retries (max 3).
  - `**kwargs` — forwarded to `session.request` (e.g. `data={...}`).
- Returns: parsed JSON object/list, or `None` on 204 or empty body.
- Side effects: network. Logs at DEBUG with `magnet` field always `<redacted>`; other `data` fields truncated to 80 chars.
- Raises:
  - `RealDebridError("API token 無效或已過期")` on 401.
  - `RealDebridError("帳號權限不足（需要 Premium 會員）")` on 403.
  - `RealDebridError("HTTP 429: 請求頻率過高，請稍後再試")` after 3 retries on 429.
  - `RealDebridError(f"HTTP {code}: {msg}")` on other 4xx/5xx.
- Threading: depends on per-instance `requests.Session` — keep one RD instance per thread.

**Calls**:
- internal: `_parse_retry_after()` (static).
- external: `requests.Session.request`, `time.sleep`, `resp.json`.

**Called by**: every public method on `RealDebrid` + `SettingsDialog.test_connection` (in retired GUI) (calls `_request("GET", "/user")`).

---

#### `_parse_retry_after(resp) -> float`  *([realdebrid.py:103](../../../realdebrid.py#L103), staticmethod)*

**Purpose**: Read `Retry-After` header; default 5.0s.

**Contract**:
- Params: `resp` — a `requests.Response`.
- Returns: seconds to wait.
- Side effects: none.
- Raises: none (catches `ValueError`).
- Threading: pure.

**Called by**: `_request` on 429.

---

#### `close(self)`

**Purpose**: Close the underlying `requests.Session`.

#### `user(self) -> dict`

**Purpose**: Public method to retrieve account metadata via `GET /user`.

#### `add_magnet(self, magnet: str) -> str`

**Purpose**: POST `/torrents/addMagnet` → return torrent id.

**Contract**:
- Params: `magnet: str` — full magnet URI.
- Returns: `str` torrent id.
- Raises: `RealDebridError("RD API 回傳無效的 torrent id")` if response result is non-dict or `id` is missing/empty/non-string, or any `RealDebridError` from `_request`.

**Called by**: [`process_magnet`](#process_magnetself-magnet-strategy--smart-cache_wait--15-progressnone---dict-realdebridpy215).

---

#### `torrent_info(self, torrent_id: str) -> dict`  *([realdebrid.py:120](../../../realdebrid.py#L120))*

**Purpose**: GET `/torrents/info/{id}`.

**Contract**: Returns RD's status dict (`status`, `progress`, `files`, `links`, `filename`, …). Raises from `_request`.

**Called by**: [`process_magnet`](#process_magnetself-magnet-strategy--smart-cache_wait--15-progressnone---dict-realdebridpy215), [`check_torrent`](#check_torrentself-torrent_id-strategy--smart-magnet----dict-realdebridpy309).

---

#### `select_files(self, torrent_id, file_ids)`  *([realdebrid.py:123](../../../realdebrid.py#L123))*

**Purpose**: POST `/torrents/selectFiles/{id}` with comma-joined ids (or literal `"all"`).

**Contract**:
- Params: `file_ids: list[int] | str` — list → joined; `"all"` passes through.
- Returns: `None` (204).
- Side effects: network; mutates RD-side torrent state.
- Raises: from `_request`.

**Called by**: [`process_magnet`](#process_magnetself-magnet-strategy--smart-cache_wait--15-progressnone---dict-realdebridpy215), [`check_torrent`](#check_torrentself-torrent_id-strategy--smart-magnet----dict-realdebridpy309).

---

#### `delete_torrent(self, torrent_id)`  *([realdebrid.py:127](../../../realdebrid.py#L127))*

**Purpose**: DELETE `/torrents/delete/{id}`; swallows errors.

**Contract**: Never raises (catches `RealDebridError`). Used on `magnet_error` / aborted submissions.

**Called by**: [`process_magnet`](#process_magnetself-magnet-strategy--smart-cache_wait--15-progressnone---dict-realdebridpy215) on hard errors.

---

#### `unrestrict_link(self, link: str) -> dict`  *([realdebrid.py:133](../../../realdebrid.py#L133))*

**Purpose**: POST `/unrestrict/link` — converts a hoster link into a direct download URL.

**Contract**: Returns dict with `download`, `filename`, `filesize`, `streamable`. Raises from `_request`.

**Called by**: [`_collect_links`](#_collect_linksself-info-dict---listdict-realdebridpy359).

---

#### `_extract_code(magnet: str) -> str | None`  *([realdebrid.py:137](../../../realdebrid.py#L137), staticmethod)*

**Purpose**: Pull JAV product code (e.g. `SNOS-192`, `IPZZ-851`) from the `dn=` parameter of a magnet URI.

**Contract**:
- Params: `magnet: str` (may be `""` / `None` — treated as no match).
- Returns: normalized code `LETTERS-NUMBERS` uppercased, or `None` if no `dn=` or no match.
- Side effects: none.
- Raises: none.
- Threading: pure.

**Regex**: `r"\b([A-Za-z]{2,6})[-_]?(\d{3,5})\b"` against URL-unquoted `dn=`. Accepts 2-6 letters + 3-5 digits, optionally separated by `-`/`_`.

**Tested by**: `tests/test_core_logic.py` (`ExtractCode` cases). Behavioral contract: returns uppercase `ABCD-1234`; no match → `None`.

**Called by**: [`pick_files`](#pick_filesself-files-strategy--smart-magnet----listint-realdebridpy161) for `smart` strategy.

---

#### `_filename_matches_code(filename, code) -> bool`  *([realdebrid.py:151](../../../realdebrid.py#L151), staticmethod)*

**Purpose**: Tolerant containment check — case-insensitive, `_`/`-` interchangeable, separator-optional.

**Contract**:
- Params: `filename: str`, `code: str`.
- Returns: `True` if code (or its no-dash form) appears in the filename (also normalized to dash form).
- Side effects: none.

**Tested by**: `tests/test_core_logic.py` (`FilenameMatchesCode` cases).

**Called by**: `pick_files` (smart strategy).

---

#### `pick_files(self, files, strategy="smart", magnet="") -> list[int]`  *([realdebrid.py:161](../../../realdebrid.py#L161))*

**Purpose**: Decide which files inside a torrent to download.

**Contract**:
- Params:
  - `files: list[dict]` — RD's file list. Each dict has `id`, `path`, `bytes`.
  - `strategy: "all" | "video" | "largest" | "smart"`.
  - `magnet: str` — used only by `smart` for `_extract_code`.
- Returns: `list[int]` of file ids. Empty `files` → `[]`.
- Side effects: logs at INFO/DEBUG/WARNING.
- Raises: none.

**Decision tree**:

- **`all`** → every file id.
- **`video`** → all files whose suffix ∈ `VIDEO_EXTS`. If none, fall back to single largest file.
- **`largest`** → single largest file among videos (or all files if no video extensions).
- **`smart`** (default):
  1. If `_extract_code(magnet)` returns a code:
     - Collect videos whose filename matches the code.
     - If any match → apply the `min_size_mb` filter; if survivors → return them, **else return the unfiltered code matches** (avoid returning empty on small-but-valid file).
     - Logs `番號 {code} 匹配 N 個影片檔，套用 {min_size_mb}MB 門檻後保留 M 個`.
  2. If no code or no code match: filter to videos with `bytes >= min_size_mb * 1024 * 1024`.
  3. If still empty: WARN and return single largest file.

**Tested by**: `tests/test_core_logic.py` (`PickFilesSmart`, `PickFilesLargest`, `PickFilesAll`, `PickFilesVideo`, plus regression cases covering "番號 match + below threshold").

**Called by**: [`process_magnet`](#process_magnetself-magnet-strategy--smart-cache_wait--15-progressnone---dict-realdebridpy215), [`check_torrent`](#check_torrentself-torrent_id-strategy--smart-magnet----dict-realdebridpy309).

---

#### `process_magnet(self, magnet, strategy="smart", cache_wait=15, progress=None, observer=None) -> dict`  *([realdebrid.py:215](../../../realdebrid.py#L215))*

**Purpose**: End-to-end flow: add magnet → poll until `waiting_files_selection` → call `pick_files`+`select_files` → poll until `cache_wait` budget exhausted. If RD returns `downloaded`, collect unrestricted links. Otherwise, leave the torrent on RD and return `pending`.

**Contract**:
- Params:
  - `magnet: str` — magnet URI.
  - `strategy: str` — forwarded to `pick_files`.
  - `cache_wait: int = 15` — max seconds to wait for a `downloaded` verdict.
  - `progress: Optional[Callable[[str], None]]` — UI status callback (also gets `logger.info`).
  - `observer: Optional[Callable[[str], None]]` — pure-observation callback fired with the raw RD `status` on every poll, so a caller can record the transition trail. Added for `rd_outcome_log`: the returned dict only carries the terminal status, which cannot distinguish "queued behind other downloads" from "actively downloading". Deliberately a callback rather than an extra return field — the return value crosses sidecar → Rust's tagged `RdSendOutcome` enum, and Rust cannot be compiled on the dev machine, so changing that shape would mean shipping something unverifiable. Exceptions raised by `observer` are swallowed: recording must never fail a send.
- Returns: dict with shape
  - completed → `{"status": "completed", "name", "torrent_id", "links": [...]}`
  - pending → `{"status": "pending", "name", "torrent_id", "progress", "rd_status", "files_selected"}`
- Side effects:
  - Network: `add_magnet`, repeated `torrent_info`, `select_files`, `unrestrict_link`s.
  - Calls `progress(msg)` from the same thread.
  - `time.sleep(3)` between polls; the function blocks for up to `cache_wait + epsilon` seconds.
  - Logs `=== 開始處理磁力 [btih:8] ===` … `=== … 已快取/待處理 ===`.
- Raises:
  - `RealDebridError("磁力解析失敗: …")` on `status=="magnet_error"` (after `delete_torrent`).
  - `RealDebridError("下載失敗")` on `status=="error"` (after `delete_torrent`).
  - `RealDebridError("沒有可選的檔案")` if `pick_files` returns empty (after `delete_torrent`).
  - Pass-through from sub-calls.
- Threading: blocking; called from worker threads in GUI.

**Calls**:
- internal: `add_magnet`, `torrent_info`, `pick_files`, `select_files`, `_collect_links`, `delete_torrent`.
- external: `time.time`, `time.sleep`, `re.search` for `btih:`, `Path` for `name`.

**Called by**: `RDDialog.worker` (in retired GUI); sidecar's `rd_send_magnet`.

---

#### `check_torrent(self, torrent_id, strategy="smart", magnet="") -> dict`  *([realdebrid.py:309](../../../realdebrid.py#L309))*

**Purpose**: Re-poll a previously-pending torrent. If still `waiting_files_selection`, auto-pick & re-select.

**Contract**:
- Params:
  - `torrent_id: str`.
  - `strategy: str` — for late selection.
  - `magnet: str = ""` — required for `smart` strategy's number match on retry.
- Returns:
  - completed → `{"status": "completed", "name", "torrent_id", "links": [...]}`
  - pending → `{"status": "pending", "name", "torrent_id", "progress", "rd_status"}`
  - missing → `{"status": "missing", "torrent_id"}` (RD returned 404)
- Side effects: network; may call `select_files`. Logs `重試時補選檔案 …`.
- Raises: passes through non-404 `RealDebridError`.
- Threading: blocking.

**Calls**: `torrent_info`, `pick_files`, `select_files`, `_collect_links`.

**Called by**: `RetryDialog.check_worker` (in retired GUI); sidecar's `rd_check_pending`.

---

#### `_collect_links(self, info: dict) -> list[dict]`  *([realdebrid.py:359](../../../realdebrid.py#L359))*

**Purpose**: Unrestrict every link on a completed torrent and aggregate results (one row per file).

**Contract**:
- Params: `info: dict` from `torrent_info`.
- Returns: `list[dict]`, each either
  - `{"original", "download", "filename", "filesize", "streamable"}`, or
  - `{"original", "error": "<msg>"}` if unrestrict failed.
- Side effects: N network calls (one per link); logs each result.
- Raises: per-link `RealDebridError`s are caught and converted to error entries — the loop is best-effort.

**Called by**: `process_magnet`, `check_torrent`.

---

## 5. `javdb_scraper.py` (LIVE — M9 Phase 5-A)

Pure JavDB scraping core: HTTP session creation, magnet panel parsing, and the two size/file-count parsers. Extracted verbatim from the retired Tk GUI in M9 Phase 5-A so the sidecar daemon can import it without dragging tkinter into the bundle. Zero `app_logging` / `realdebrid` / `tkinter` deps — pure library.

### Module scope

- `HAS_CURL_CFFI: bool` — set at import time after `try: from curl_cffi import requests as cffi_requests`. Falls back to vanilla `requests`.
- No globals beyond the curl_cffi import flag. No file paths. No logger.
- **Note**: `sys.stdout.reconfigure(...)` is NOT in this file (it's in `sidecar/sidecar.py` as a daemon-boundary responsibility).

### `create_session() -> tuple[Session, str]`  *([javdb_scraper.py:30](../../../javdb_scraper.py#L30))*

**Purpose**: Build an HTTP session with browser-impersonating headers, plus a label identifying which engine is in use.

**Contract**:
- Params: none.
- Returns: `(session, engine)` where `engine` is `"curl_cffi"` or `"requests"`.
- Side effects: none beyond the constructor calls.
- Raises: none under normal operation.

**Calls**: `cffi_requests.Session(impersonate="chrome124", ...)` if `HAS_CURL_CFFI`; else `requests.Session()` + `headers.update`.

**Called by**: [`sidecar.py::cmd_fetch_javdb`](../../../sidecar/sidecar.py).

### `parse_size_gb(size_str: str) -> float`  *([javdb_scraper.py:51](../../../javdb_scraper.py#L51))*

**Purpose**: Parse `"5.67GB, 5個文件"` → `5.67`. Falls back through `MB / 1024`. Returns `0.0` on no-match.

**Contract**: pure regex parse. Side-effect-free. Behavioral spec lives in `tests/test_core_logic.py::ParseSizeGB` (6 cases).

### `parse_file_count(size_str: str) -> int`  *([javdb_scraper.py:60](../../../javdb_scraper.py#L60))*

**Purpose**: Parse `"5.67GB, 5個文件"` → `5`. Returns sentinel `999` on no-match (used as "many files; deprioritize").

**Contract**: pure regex parse. Behavioral spec in `tests/test_core_logic.py::ParseFileCount` (4 cases).

### `fetch_magnets(url: str, session, cookies: dict) -> dict`  *([javdb_scraper.py:69](../../../javdb_scraper.py#L69))*

**Purpose**: Fetch a JavDB video page and parse the magnet panel + title + JAV code.

**Contract**:
- Params: `url`, `session` (returned by `create_session`), `cookies` dict.
- Returns: `{"url", "code", "title", "magnets": [...], "error"}`. `magnets` items each have `name / size / tags / date / magnet`.
- Side effects: **network** GET (timeout 30s); no file I/O; no logging.
- Raises: lets `requests`/`curl_cffi` exceptions propagate. The sidecar's `cmd_fetch_javdb` envelope catches them at the dispatch boundary.

**Calls**: `session.get`, `BeautifulSoup(html, "html.parser")`, soup `.select_one` / `.select`.

**Called by**: [`sidecar.py::cmd_fetch_javdb`](../../../sidecar/sidecar.py).

**Selectors (data contract with JavDB HTML)**:
- Title: `h2.title.is-4 .current-title`.
- Code: `.panel-block .value a` (then `parent.get_text(strip=True)` to include the prefix like `番號:`).
- Magnet rows: `#magnets-content .item`, each with `.magnet-name a[href]`, `.name`, `.meta`, `.tag*`, sibling `.date .time`.

---

## 6. `legacy/javdb_magnet_gui.py` (RETIRED — M9 Phase 5-B)

Pre-Tauri Tkinter desktop application. **No production importer** after M9 Phase 5-A; moved to `legacy/` in Phase 5-B. Kept under version control so future readers can study the original Tk UX without spelunking through `git log`. The actual source file is the canonical reference; this section is just an orientation map.

### File at a glance

Line ranges below refer to the **current** `legacy/javdb_magnet_gui.py` (offsets shifted from the pre-M9 root-path version because Phase 5-B added a RETIRED docstring banner at the top).

| Range | Section | Replaced by |
|---|---|---|
| `~58-60` | `COOKIE_FILE / ENV_FILE / PENDING_FILE` constants (`app_dir()/...`) | Rust `path_manager.rs` + `%APPDATA%\JavDBMagnet\` |
| `~63-94` | `load_pending / save_pending / add_pending / remove_pending` | Rust `pending.rs` |
| `~97-109` | `load_cookies` (file-based) | Rust `commands.rs::cookies_status` + sidecar `cmd_handshake` JSONL message |
| `~112-189` | `create_session / parse_size_gb / parse_file_count / fetch_magnets` | **`javdb_scraper.py`** (extracted in M9 Phase 5-A; see §5 above) |
| `~192-590` | `class App` — Tk root window (toolbar, scrape form, magnet list, filter/sort/clipboard) | Svelte `app/src/App.svelte` (the entire SPA UI) |
| `~591-706` | `class RDInputDialog` — RD source picker dialog | Svelte App.svelte paste-magnet flow |
| `~707-904` | `class RDDialog` — batch send to RD with progress | Svelte App.svelte `sendBatch` + `lib/rdSender.ts` |
| `~905` | `RD_TOKEN_URL` constant | Svelte App.svelte settings panel "open RD token page" button |
| `~908-939` | `write_env(values)` — rewrite `.env` from settings dict | Rust `commands.rs::write_settings` → `settings.rs::write_settings` |
| `~941-1169` | `class SettingsDialog` — env editor with validation + RD probe | Svelte App.svelte settings section + `lib/settingsValidation.ts` |
| `~1170-1381` | `class RetryDialog` — re-poll pending torrents from disk | Svelte App.svelte `retryAllPending` + `lib/magnetUtils.ts::retryPending` |
| `~1382-1484` | DPI / font helpers (`_enable_dpi_awareness`, `_get_dpi_scale`, `_apply_dpi_scaling`, `_pick_font`, `_setup_fonts`, `_apply_ttk_font`) | WebView native handling — Tauri does not need these |
| `~1485-1516` | `__main__` boot block | n/a; the file is no longer an entry point |

### Why the file still exists in the repo

Three reasons, in priority order:

1. **`tests/test_app_logging.py::JavdbGuiImportSideEffects`** still imports it via `importlib.util` to verify the lazy-logging contract: importing a module that does `from app_logging import get_logger` at top-level must NOT trigger `setup_logging()`. The module is the canary; if a future change adds an import-time side effect, the test fails.
2. **Historical reference**: the full pre-Tauri UX design (widget layout, dialog flow, retry/settings UX) lives in this file. git log can show the source but not navigate it; keeping the file in `legacy/` makes it browsable.
3. **Migration baseline**: any time the Tauri rewrite needs to confirm "what did the old GUI do here", the source is one click away.

### Why it's not in `sidecar.exe` (M9)

`spikes/pyinstaller_sidecar/build_sidecar.py` had `--hidden-import javdb_magnet_gui` until Phase 5-A; this was switched to `--hidden-import javdb_scraper` and the sidecar entry's `from javdb_magnet_gui import ...` was changed to `from javdb_scraper import ...`. With nothing in production importing the GUI module, PyInstaller no longer pulls tkinter / ttk / messagebox / DPI helpers into the bundle (-3.02 MiB).


## 7. Cross-file call graph (live sidecar paths)

The Python-side flows below are the ones still executed at runtime. The Tauri-side wiring (Svelte → Rust → JSONL → Python) is documented end-to-end in [`../function-contracts.md`](../function-contracts.md); this section only shows what happens **inside the sidecar process** once a JSONL command arrives.

### 7.1 Sidecar boot

```
sidecar/sidecar.py: __main__
  └─ app_logging.setup_logging()             [lazy; respects JAVDB_LOG_DIR]
  └─ run_daemon(stdin, stdout)
       └─ for each line on stdin:
            └─ dispatch(state, json.loads(line))
                 └─ cmd_<name>(state, req)
```

### 7.2 `cmd_fetch_javdb` (JavDB scrape)

```
cmd_fetch_javdb(state, req)
  ├─ javdb_scraper.create_session()                [curl_cffi or requests]
  ├─ javdb_scraper.fetch_magnets(url, session, state.cookies)
  │    └─ session.get(url) → BeautifulSoup parse
  └─ envelope: {ok, magnets:[{name, size, tags, date, magnet_redacted}], code, title}
```

(Cookies arrive earlier via `cmd_handshake`, not from disk.)

### 7.3 `cmd_rd_send_magnet` (single magnet to RD)

```
cmd_rd_send_magnet(state, req)
  ├─ _rd_client(state, ...) → RealDebrid(token, min_size_mb)
  └─ rd.process_magnet(magnet, strategy, cache_wait, progress=...)
       ├─ rd.add_magnet()                  → POST /torrents/addMagnet
       ├─ loop:
       │    rd.torrent_info()              → GET  /torrents/info/{id}
       │    if status == waiting_files_selection:
       │      rd.pick_files(files, strategy, magnet)
       │        └─ _extract_code / _filename_matches_code  [smart strategy]
       │      rd.select_files()            → POST /torrents/selectFiles/{id}
       │    if status == downloaded:
       │      rd._collect_links(info)
       │        └─ rd.unrestrict_link(...) → POST /unrestrict/link
       │    if status == magnet_error/error:
       │      rd.delete_torrent()          → DELETE /torrents/delete/{id}
       │      raise RealDebridError
       │    time.sleep(3)
       └─ envelope: {ok, status, links | pending}
```

(Pending state lives in Rust `pending.rs`; the sidecar does not write the pending JSON file.)

### 7.4 `cmd_rd_check_pending` (re-poll one pending torrent)

```
cmd_rd_check_pending(state, req)
  ├─ _rd_client(state, ...) → RealDebrid(token, min_size_mb)
  └─ rd.check_torrent(torrent_id, strategy=item.strategy, magnet=item.magnet)
       ├─ rd.torrent_info()
       ├─ if waiting_files_selection: rd.pick_files / rd.select_files / re-query
       ├─ if downloaded: rd._collect_links → unrestrict_link*
       └─ if 404: envelope {status: "missing"}
```

(Rust calls this once per pending entry; reconciliation lives in `App.svelte::retryAllPending`.)

### 7.5 `cmd_rd_user` and `cmd_rd_set_token` (settings panel "test RD" + token write)

```
cmd_rd_user(state, req)
  └─ RealDebrid(token)._request("GET", "/user") → {username, type, expiration, points}

cmd_rd_set_token(state, req)
  └─ state.rd_token = req["token"]   [in-memory only; persistence is Rust-side]
```

The retired GUI's "settings → save" flow (`SettingsDialog.save` → `write_env(values)`) does not exist in the live runtime; settings are written by Rust `commands.rs::write_settings`.

---

## 8. What survives, M9 edition

### Live in `sidecar.exe`

| Module | Role |
| --- | --- |
| `app_logging.py` | Sidecar uses `setup_logging` + `get_logger`. Log dir controlled via `JAVDB_LOG_DIR`. |
| `realdebrid.py` | Sidecar's `rd_*` commands wrap `RealDebrid.process_magnet` / `check_torrent` / `pick_files`. Retry policy and 401/403/429 handling inherited unchanged. |
| `javdb_scraper.py` | `cmd_fetch_javdb` calls `create_session` + `fetch_magnets`; `tests/test_core_logic.py` exercises `parse_size_gb` + `parse_file_count`. M9 Phase 5-A; replaced the import from `javdb_magnet_gui`. |

PyInstaller hidden-imports for the live sidecar build are exactly: `curl_cffi`, `curl_cffi.requests`, `javdb_scraper`, `realdebrid`, `app_logging`. No `javdb_magnet_gui`, no `tkinter`.

### Replaced by other layers (no longer Python-side)

- **Settings persistence** (was `load_env` / `write_env`): Rust `commands.rs::write_settings` + `settings.rs`.
- **Pending-queue file** (was `load_pending`/`save_pending`/`add_pending`/`remove_pending`): Rust `pending.rs`.
- **Cookies file read** (was `javdb_magnet_gui.load_cookies`): Rust `commands.rs::cookies_status` + sidecar `cmd_handshake` JSONL handoff.
- **Filter/sort logic** (was `apply_filter`, `sort_column`): Svelte UI in `app/src/App.svelte` + `app/src/lib/magnetUtils.ts`.
- **Clipboard** (was `copy_all_magnets`, `copy_all`, `copy_completed`): Tauri clipboard plugin via `App.svelte` handlers.
- **All Tk dialogs** (`App`, `RDInputDialog`, `RDDialog`, `SettingsDialog`, `RetryDialog`): Svelte components in `App.svelte` + `lib/{rdSender,settingsValidation,magnetUtils}.ts`.
- **DPI / font handling** (was `_enable_dpi_awareness`, `_setup_fonts`, etc.): Tauri WebView / OS-native.
- **Tk theming** (was `sv_ttk`): Svelte CSS variables.
- **Build pipeline** (was `build.py`): `scripts/build-release.ps1` + `spikes/pyinstaller_sidecar/build_sidecar.py`. The old build script was deleted in M9 Phase 2.

### Behavioral contract that `tests/test_core_logic.py` pins down

When porting / refactoring the Python core, the following must remain true (unit tests are the source of truth):

- `_extract_code("magnet:?...&dn=SNOS-192&...") == "SNOS-192"` (uppercase, hyphenated). Variants `SNOS_192`, `snos192` also normalize to `SNOS-192`. Non-matching `dn=` → `None`.
- `_filename_matches_code("[XXX] SNOS-192 1080p.mp4", "SNOS-192") == True`; tolerant to `_`/`-`/missing-separator and case.
- `pick_files`:
  - `all` returns every id.
  - `largest` returns single largest **video** (or largest overall if no videos).
  - `video` returns all video files; if none, single largest overall.
  - `smart` with code match: returns code-matching videos passing `min_size_mb`; if none pass, returns the code matches anyway (avoid empty result).
  - `smart` without code match: applies `min_size_mb` filter to videos; if empty, falls back to single largest file.
- `parse_size_gb` and `parse_file_count` (now imported from `javdb_scraper`): the same regex contract documented in §5 above. Test classes `ParseSizeGB` (6 cases) and `ParseFileCount` (4 cases).
