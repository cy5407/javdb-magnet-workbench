# Python core modules — function contracts

> Reference for the Python modules in the repo, split by their current status after M9 Phase 5-B:
>
> - **LIVE in `sidecar.exe`** (loaded by the JSONL daemon): `app_logging.py`, `rd_outcome_log.py`, `realdebrid.py`, `javdb_scraper.py`. These four modules are bundled by `spikes/pyinstaller_sidecar/build_sidecar.py` and have first-class contract documentation here.
> - **RETIRED, kept under `legacy/`**: `legacy/javdb_magnet_gui.py` (the pre-Tauri Tk desktop app) and its private helper `legacy/_legacy_env.py` (`load_env`, moved out of `realdebrid.py` by F-06). Documented as an overview only — the live source is the canonical reference; this doc just orients readers.
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

(`rd_outcome_log.py` — stdlib only, imported only by `sidecar/sidecar.py` — is omitted from the graph.)

Imports observed (current state):

- `app_logging.py` — stdlib only. Used by `realdebrid.py` (`get_logger`), `sidecar/sidecar.py` (`setup_logging`, imported inside `main`), and the retired GUI. Lazy `setup_logging()` (no I/O at import time).
- `rd_outcome_log.py` — stdlib only (`json`, `logging`, `os`, `re`, `datetime`). Used only by `sidecar/sidecar.py`. No I/O until `configure()`.
- `javdb_scraper.py` — `requests`, `curl_cffi.requests` (optional), `bs4.BeautifulSoup`, `re`. No internal deps. **Zero `app_logging` / `realdebrid` / `tkinter` imports** — pure library.
- `realdebrid.py` — `requests`; imports `app_logging.get_logger`.
- `sidecar/sidecar.py` — top level: `from javdb_scraper import create_session, fetch_magnets, parse_size_gb` (M9; was `javdb_magnet_gui` pre-M9) and `import rd_outcome_log`; lazy: `from app_logging import setup_logging` (in `main`), `from realdebrid import RealDebrid, RealDebridError` (in `_rd_client` / RD handlers), `import requests` (shared RD session).
- `legacy/javdb_magnet_gui.py` — historical: imports `tkinter`, `requests`, `curl_cffi.requests` (optional), `bs4`, optional `sv_ttk`, `app_logging.{setup_logging,get_logger,app_dir,get_log_file}`, `realdebrid.{RealDebrid,RealDebridError}`, `legacy._legacy_env.load_env`. Not imported by any production module.

### 1.2 Entry points

| Entry | Trigger |
| --- | --- |
| `sidecar/sidecar.py` `if __name__ == "__main__"` | The JSONL daemon spawned by Tauri. See [`sidecar-runtime.md`](sidecar-runtime.md). |
| [`legacy/javdb_magnet_gui.py` ~line 1492](../../../legacy/javdb_magnet_gui.py#L1492) `if __name__ == "__main__"` | Tkinter desktop app boot. **Retired** — kept for historical reference. |

### 1.3 What ships where (M9)

| File | Bundled into `sidecar.exe` (current) | Notes |
| --- | --- | --- |
| `app_logging.py` | ✅ | `setup_logging()` is lazy. |
| `rd_outcome_log.py` | ✅ | Outcome log for `cmd_rd_send_magnet` / `cmd_rd_check_pending`. |
| `realdebrid.py` | ✅ | `RealDebrid` + `RealDebridError` used by `cmd_rd_*`. (`load_env` no longer lives here — see `legacy/_legacy_env.py`.) |
| `javdb_scraper.py` | ✅ | Provides `create_session` + `fetch_magnets` for `cmd_fetch_javdb` and `parse_size_gb` for `_record_group_meta`; `parse_file_count` is bundled but only exercised by tests. |
| `legacy/javdb_magnet_gui.py` | ❌ | M9 Phase 5-A removed the `--hidden-import` for it; PyInstaller no longer drags Tk/ttk/messagebox into the bundle (-3.02 MiB). |
| `legacy/_legacy_env.py` | ❌ | Only imported by the retired GUI and `tests/test_legacy_env.py`. |

The retired Tk path used to ship as `JavDBMagnet.exe` via `build.py`; both that build script and the standalone CLI `javdb_magnet.py` were deleted in Phase 2.

### 1.4 Disk artifacts touched at runtime

| Path | Producer / Consumer | Notes |
| --- | --- | --- |
| `app_dir()/cookies.txt` | Historically read by `legacy/javdb_magnet_gui.py::load_cookies`. **The live sidecar reads cookies from the `cmd_handshake` / `cmd_set_cookies` JSONL messages instead**, not from disk — cookie storage is owned by the Rust backend (`cookie_store.rs` keyring + `cookies.txt` migration in `lib.rs::migrate_cookies_from_file`; status via `commands.rs::get_cookies_status`). |
| `app_dir()/.env` | Historically read by `legacy/_legacy_env.py::load_env` (formerly `realdebrid.load_env`); written by `legacy/javdb_magnet_gui.py::write_env`. **The live sidecar receives settings via `cmd_handshake` / `cmd_update_settings`** — settings file is owned by Rust (`settings.rs`). |
| `app_dir()/pending_torrents.json` | Historically read/written by the retired GUI. **Pending state is now Rust-owned** (`pending.rs`). |
| `${JAVDB_LOG_DIR}/debug.log` or `%LOCALAPPDATA%\JavDBMagnet\logs\debug.log` | `RotatingFileHandler` from `setup_logging` | 5 MB × 3 backups. Falls back to console-only if all candidates fail. Rust sets `JAVDB_LOG_DIR` from the handshake `paths.log_dir` when spawning the sidecar (`sidecar_manager.rs::sidecar_env`). |
| `<debug.log dir>/rd_outcomes.jsonl` | `rd_outcome_log.configure` / `log_send` / `log_check` | 5 MB × 3 backups. Only when `debug.log` is actually file-backed and `JAVDB_RD_LOG` ≠ `0`. Nothing reads it at runtime; analyzed offline by `scripts/rd_log_report.py`. |

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
- [legacy/javdb_magnet_gui.py:58-60](../../../legacy/javdb_magnet_gui.py#L58) at module load to compute `COOKIE_FILE`, `ENV_FILE`, `PENDING_FILE`.
- Not used by `sidecar/sidecar.py` and not used for log-dir resolution.

---

### `_candidate_log_dirs() -> list[Path]`  *([app_logging.py:36](../../../app_logging.py#L36))*

**Purpose**: Return ordered fallback list of log directories: `JAVDB_LOG_DIR` env override → `%LOCALAPPDATA%\JavDBMagnet\logs`.

**Contract**:
- Params: none.
- Returns: list of candidate `Path`s (env values are `.strip()`ped; empty values skipped). May be empty (then logging is console-only).
- Side effects: reads env vars only. Deliberately **excludes** `app_dir()/logs` to avoid the A-blocker on read-only deploys.
- Raises: none.
- Threading: safe (read-only).

**Calls**: `os.environ.get`.

**Called by**: `_resolve_log_dir`.

---

### `_try_make_dir(p) -> Path | None`  *([app_logging.py:54](../../../app_logging.py#L54))*

**Purpose**: `mkdir -p` then probe-write `.write_probe` to confirm directory is actually writable.

**Contract**:
- Params: `p: Path` candidate dir.
- Returns: `p` if writable, else `None`.
- Side effects: creates dir; writes & deletes `.write_probe` file.
- Raises: catches `OSError` and returns `None`.
- Threading: safe (no shared state).

**Calls**: `Path.mkdir`, `Path.write_text`, `Path.unlink`.

**Called by**: `_resolve_log_dir`.

---

### `_resolve_log_dir() -> tuple[Path | None, Path | None]`  *([app_logging.py:66](../../../app_logging.py#L66))*

**Purpose**: Walk `_candidate_log_dirs()` in order and return `(chosen_dir, last_attempted)`; `chosen_dir` is the first dir `_try_make_dir` accepts, else `None`.

**Called by**: `setup_logging`.

### `_log_file_for(dir_) -> Path`  *([app_logging.py:77](../../../app_logging.py#L77))*

**Purpose**: Diagnostic path when no writable dir was secured: `dir_/debug.log`, or bare `Path("debug.log")` when `dir_` is `None`.

### `_attach_file_handler(root, log_file) -> bool`  *([app_logging.py:82](../../../app_logging.py#L82))*

**Purpose**: Attach a `RotatingFileHandler(maxBytes=5 MiB, backupCount=3, encoding="utf-8")` at `DEBUG` with format `%(asctime)s [%(levelname)s] %(name)s: %(message)s`; return `False` (attach nothing) if opening raises `OSError`.

### `_attach_console_handler(root, debug) -> None`  *([app_logging.py:99](../../../app_logging.py#L99))*

**Purpose**: Attach a `StreamHandler(sys.stderr)` at `DEBUG` when `debug`, else `INFO`.

---

### `setup_logging(debug: bool = False) -> Path`  *([app_logging.py:108](../../../app_logging.py#L108))*

**Purpose**: Initialize root logger with rotating file handler + stderr console handler. Idempotent.

**Contract**:
- Params: `debug: bool` — also accepts env `DEBUG=1`. Raises console handler level to `DEBUG`.
- Returns: resolved log-file `Path`. When no candidate is usable (or the file handler cannot open) it degrades to console-only and returns `_log_file_for(last_attempted)` — i.e. the **last attempted** `<dir>/debug.log`, or `Path("debug.log")` when there were no candidates. A truthy return value therefore does not prove a file is being written (the sidecar checks the root logger for a `FileHandler` instead). Once initialized, later calls return the cached path without touching handlers.
- Side effects:
  - Mutates global `_initialized` / `_resolved_log_file`.
  - Clears root logger handlers and re-adds them.
  - Creates log directory + file (`debug.log`).
  - Downgrades `urllib3` / `requests` loggers to WARNING.
- Raises: none — `OSError` from directory probing / handler opening is caught; degrades to console-only (logs a WARNING naming the last attempted dir).
- Threading: **not safely re-entrant** (mutates globals + root logger handlers). Should be called once at startup before threads are spawned.

**Calls**:
- internal: `_resolve_log_dir()`, `_log_file_for()`, `_attach_file_handler()`, `_attach_console_handler()`.
- external: `logging.getLogger`, `os.environ.get("DEBUG")`.

**Called by**:
- [legacy/javdb_magnet_gui.py:1494](../../../legacy/javdb_magnet_gui.py#L1494) main entry.
- `sidecar/sidecar.py::main` startup (before `run_daemon`).
- `tests/test_app_logging.py`.

---

### `get_logger(name: str) -> logging.Logger`  *([app_logging.py:151](../../../app_logging.py#L151))*

**Purpose**: Thin wrapper for `logging.getLogger`.

**Contract**:
- Params: `name: str` — usually `__name__`.
- Returns: `logging.Logger`.
- Side effects: none beyond stdlib's logger registry lookup.
- Raises: none.
- Threading: safe.

**Calls**: `logging.getLogger(name)`.

**Called by**: top of [realdebrid.py:14](../../../realdebrid.py#L14), [legacy/javdb_magnet_gui.py:53](../../../legacy/javdb_magnet_gui.py#L53). (`sidecar/sidecar.py` does not call it.)

---

### `get_log_file() -> Path | None`  *([app_logging.py:155](../../../app_logging.py#L155))*

**Purpose**: Retrieve the resolved log file path (after `setup_logging` ran).

**Contract**:
- Params: none.
- Returns: `Path` or `None` (if `setup_logging` not yet called).
- Side effects: none.
- Raises: none.
- Threading: safe.

**Calls**: reads module-level `_resolved_log_file`.

**Called by**: `App.open_log` (in retired GUI, [legacy/javdb_magnet_gui.py:525](../../../legacy/javdb_magnet_gui.py#L525); "查看日誌" button); `tests/test_app_logging.py`.

---

## 3. `rd_outcome_log.py`

RD send-outcome log: one JSONL observation per line in `rd_outcomes.jsonl`, for offline hit-rate analysis (`scripts/rd_log_report.py`). Spec: [`docs/specs/2026-08-01-rd-outcome-log.md`](../../specs/2026-08-01-rd-outcome-log.md). Design rule: **record observations, never verdicts** — no `rd_class` / `tier` / `is_hd`; the heuristic's single source of truth stays in `app/src/lib/rdPriority.ts`. Every write path swallows its own failures: the log must never fail a send.

### Module-level

- `SCHEMA_VERSION = 1` (written as `"v"`).
- `_LOG_FILE_NAME = "rd_outcomes.jsonl"`, logger name `"rd_outcomes"`.
- `_MAX_BYTES = 5 MiB`, `_BACKUP_COUNT = 3` (same as `debug.log`; deliberately no read-side cap like `pending.rs`, which would lock an append-only log).
- `_FORBIDDEN_RX = urn:btih|magnet:\?xt` (case-insensitive) — any serialized line matching it is dropped whole (defense in depth for the release redaction gates that grep the log directory).
- `MAX_STATUS_TRAIL = 8`.

### `is_enabled() -> bool`  *([rd_outcome_log.py:55](../../../rd_outcome_log.py#L55))*

`False` only when env `JAVDB_RD_LOG` (stripped) is `"0"`; enabled by default.

### `configure(log_dir) -> Path | None`  *([rd_outcome_log.py:64](../../../rd_outcome_log.py#L64))*

**Purpose**: Idempotently create the dedicated logger + `RotatingFileHandler` (formatter `%(message)s`, `propagate = False` so lines never also land in `debug.log`).

**Contract**:
- Params: `log_dir` — `str` / `Path`, or `None`.
- Returns: the log file path, or `None` (and the feature stays off) when disabled, `log_dir` is `None` / not a `str`/`Path`, or mkdir / handler open raises `OSError`. Only the first call has effect.
- Side effects: `mkdir(parents=True)` on `log_dir`; opens the file.

**Called by**: `sidecar/sidecar.py::main` with `log_file.parent` only when `debug.log` is file-backed, else `None`.

### `log_send(*, outcome, elapsed_ms, btih8="", torrent_id="", rd_status="", status_trail=None, progress=0, files_selected=False, link_count=0, error_code=None, meta=None, cache_wait=None, file_pick="", min_size_mb=None) -> None`  *([rd_outcome_log.py:184](../../../rd_outcome_log.py#L184))*

**Purpose**: Append one `event:"send"` row: `v, ts, event, btih8, torrent_id, outcome, elapsed_ms, rd_status, status_trail, progress, files_selected, link_count, error_code`, then the fetch-time fields copied from `meta` by an explicit allowlist (`code, name, size, tags, date, source, group_seq, group_size, date_rank, size_rank` — internal keys like `_batch_id` never reach the log), then the confounders `cache_wait, file_pick, min_size_mb`. All parameters are keyword-only on purpose (a misspelled field must raise `TypeError`, not vanish into `**kwargs`).

**Called by**: `sidecar/sidecar.py::cmd_rd_send_magnet` (completed / pending / error).

### `log_check(*, outcome, elapsed_ms, torrent_id="", rd_status="", progress=0, link_count=0, error_code=None) -> None`  *([rd_outcome_log.py:246](../../../rd_outcome_log.py#L246))*

**Purpose**: Append one `event:"check"` row (`v, ts, event, torrent_id, outcome, elapsed_ms, rd_status, progress, link_count, error_code`), joined to the send row by `torrent_id`.

**Called by**: `sidecar/sidecar.py::cmd_rd_check_pending` (completed / missing / pending / error).

### Internal helpers

- `_now_iso()` ([:138](../../../rd_outcome_log.py#L138)) — local time with milliseconds and UTC offset.
- `_emit(payload)` ([:148](../../../rd_outcome_log.py#L148)) — no-op until configured; `json.dumps(ensure_ascii=False, separators=(",", ":"))`; drops the line (incrementing `_dropped_count`) on `_FORBIDDEN_RX` match; swallows write errors.
- `_clean_status_trail(trail)` ([:168](../../../rd_outcome_log.py#L168)) — non-list → `[]`; drops non-string / empty items, collapses consecutive duplicates, stops at `MAX_STATUS_TRAIL`.
- Test / diagnostic accessors: `reset_for_tests()`, `dropped_count()`, `get_log_path()`.

---

## 4. `realdebrid.py`

Real-Debrid REST client. All HTTP calls go through `RealDebrid._request`.

### Module-level

- `API_BASE = "https://api.real-debrid.com/rest/1.0"`.
- `VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".wmv", ".mov", ".m4v", ".ts", ".webm"}` — used by `pick_files`.
- `MAX_RETRY_AFTER_SECONDS = 10` — ceiling on a single 429 back-off.
- `logger = get_logger(__name__)`.

### `load_env` — moved to `legacy/_legacy_env.py`

`load_env(path: Path) -> dict[str, str]` ([legacy/_legacy_env.py:14](../../../legacy/_legacy_env.py#L14)) is no longer exported by `realdebrid.py` (F-06: a production module should not carry a generic dotenv parser). Behaviour unchanged: missing file → `{}`; blank lines, `#` comments and lines without `=` skipped; values stripped of surrounding quotes. Only callers: the retired GUI (`App.send_to_realdebrid`, `App.open_retry`, `SettingsDialog`, the `__main__` boot for `UI_SCALE` / `UI_THEME`) and `tests/test_legacy_env.py`. The live sidecar never reads `.env`.

---

### `class RealDebridError(Exception)`  *([realdebrid.py:23](../../../realdebrid.py#L23))*

Tagged exception for all RD client failures (auth, permission, rate-limit, budget exhaustion, HTTP error, missing files, etc.).

---

### `class RealDebrid`  *([realdebrid.py:27](../../../realdebrid.py#L27))*

#### `__init__(self, token: str, min_size_mb: int = 500, deadline: float | None = None, session: requests.Session | None = None)`  *([realdebrid.py:28](../../../realdebrid.py#L28))*

**Purpose**: Stash bearer token on a `requests.Session`; remember the smart-strategy size threshold and the optional request deadline.

**Contract**:
- Params:
  - `token: str` — required, non-empty. Empty → `RealDebridError("RD_API_TOKEN 未設定，請編輯 .env 檔案貼上 token")`.
  - `min_size_mb: int = 500` — minimum video file size for `smart` strategy.
  - `deadline: float | None` — `time.monotonic()` instant shared by every `_request` of this client.
  - `session: requests.Session | None` — reuse a caller-owned session (`_shared_session = True`, so `close()` leaves it open); else a private session is created.
- Returns: `RealDebrid` instance.
- Side effects: sets `Authorization: Bearer <token>` on the session.
- Raises: `RealDebridError` if token empty.
- Threading: `requests.Session` is **not** safe to share across threads (per upstream docs). Each thread should own its `RealDebrid`; `_collect_links` is the one internal exception (parallel unrestricts).

**Called by**: GUI dialogs (`RDDialog.worker` (in retired GUI), `RetryDialog.check_worker` (in retired GUI), `SettingsDialog.test_connection` (in retired GUI)) and `sidecar/sidecar.py::_rd_client` (which passes `deadline` and then swaps in the shared `state.rd_session` itself rather than using `session=`).

---

#### `_request(self, method, path, _retry_count=0, deadline=None, **kwargs)`  *([realdebrid.py:55](../../../realdebrid.py#L55))*

**Purpose**: Single chokepoint for every RD HTTP call. Adds deadline-aware timeout（`min(30s, remaining budget)`，deadline 由 sidecar 以 `time.monotonic()` 設定並貫穿整個 command；未設定 deadline 時固定 30s）, 429 handling（單次 Retry-After 退避受 `MAX_RETRY_AFTER_SECONDS = 10` 與剩餘預算夾制）, status mapping, JSON decode, and debug logging with redaction.

**Contract**:
- Params:
  - `method: str` — HTTP verb.
  - `path: str` — joined onto `API_BASE`.
  - `_retry_count: int` — internal counter for 429 retries (max 3).
  - `deadline: float | None` — per-call override of `self.deadline`.
  - `**kwargs` — forwarded to `session.request` (e.g. `data={...}`). Always sent with `allow_redirects=False`.
- Returns: parsed JSON object/list, or `None` on 204 or empty body.
- Side effects: network. Logs at DEBUG via `_redact_log_kwargs`: `data["magnet"]` → `<redacted>`, `Authorization` / `Proxy-Authorization` / `Cookie` headers → `<redacted>`, other values truncated to 80 chars. `torrent_info`-shaped responses get a one-line status summary.
- Raises:
  - `RealDebridError("HTTP 429: 請求超過時間預算")` when the deadline is already exhausted (before sending, or before a 429 retry).
  - `RealDebridError("API token 無效或已過期")` on 401.
  - `RealDebridError("帳號權限不足（需要 Premium 會員）")` on 403.
  - `RealDebridError("HTTP {code}: unexpected redirect")` on 3xx.
  - `RealDebridError("HTTP 429: 請求頻率過高，請稍後再試")` after 3 retries on 429.
  - `RealDebridError(f"HTTP {code}: {msg}")` on other non-2xx, `msg` = body `error` string (≤80 chars) or `"API error"`.
- Threading: depends on per-instance `requests.Session` — keep one RD instance per thread.

**Calls**:
- internal: `_redact_log_kwargs()`, `_retry_after_rate_limit()` (429), `_raise_for_status()`, `_log_torrent_info_summary()`.
- external: `requests.Session.request`, `time.monotonic`, `resp.json`.

**Called by**: every public method on `RealDebrid` (`user`, `add_magnet`, `torrent_info`, `select_files`, `delete_torrent`, `unrestrict_link`), `_retry_after_rate_limit` (re-entry), and `SettingsDialog.test_connection` (in retired GUI) (calls `_request("GET", "/user")` directly).

---

#### `_retry_after_rate_limit(self, resp, method, path, retry_count, kwargs, deadline=None)`  *([realdebrid.py:118](../../../realdebrid.py#L118))*

**Purpose**: 429 back-off: after 3 retries raise `HTTP 429: 請求頻率過高，請稍後再試`; else wait `min(Retry-After, 10)` further capped by the remaining deadline (raise `HTTP 429: 請求超過時間預算` if none left), then re-enter `_request` with `retry_count + 1`.

**Calls**: `_parse_retry_after`, `time.sleep`, `_request`.

#### `_raise_for_status(resp)`  *([realdebrid.py:139](../../../realdebrid.py#L139), staticmethod)*

**Purpose**: Map non-2xx responses to the `RealDebridError` messages listed under `_request`.

---

#### `_parse_retry_after(resp) -> float`  *([realdebrid.py:178](../../../realdebrid.py#L178), staticmethod)*

**Purpose**: Read `Retry-After` header; default 5.0s.

**Contract**:
- Params: `resp` — a `requests.Response`.
- Returns: seconds to wait.
- Side effects: none.
- Raises: none (catches `ValueError`).
- Threading: pure.

**Called by**: `_retry_after_rate_limit` on 429.

---

#### `close(self)`  *([realdebrid.py:47](../../../realdebrid.py#L47))*

**Purpose**: Close the underlying `requests.Session` — unless it is shared (`_shared_session`), in which case the owner closes it.

#### `user(self) -> dict`  *([realdebrid.py:51](../../../realdebrid.py#L51))*

**Purpose**: Public method to retrieve account metadata via `GET /user`. Used by sidecar `cmd_rd_user`.

#### `add_magnet(self, magnet: str) -> str`  *([realdebrid.py:189](../../../realdebrid.py#L189))*

**Purpose**: POST `/torrents/addMagnet` → return torrent id.

**Contract**:
- Params: `magnet: str` — full magnet URI.
- Returns: `str` torrent id.
- Raises: `RealDebridError("RD API 回傳無效的 torrent id")` if response result is non-dict or `id` is missing/empty/non-string, or any `RealDebridError` from `_request`.

**Called by**: [`process_magnet`](#process_magnetself-magnet-strategysmart-cache_wait15-progressnone-observernone---dict--realdebridpy310).

---

#### `torrent_info(self, torrent_id: str) -> dict`  *([realdebrid.py:196](../../../realdebrid.py#L196))*

**Purpose**: GET `/torrents/info/{id}`.

**Contract**: Returns RD's status dict (`status`, `progress`, `files`, `links`, `filename`, …). Raises from `_request`.

**Called by**: [`process_magnet`](#process_magnetself-magnet-strategysmart-cache_wait15-progressnone-observernone---dict--realdebridpy310), [`check_torrent`](#check_torrentself-torrent_id-strategysmart-magnet---dict--realdebridpy462).

---

#### `select_files(self, torrent_id, file_ids="all")`  *([realdebrid.py:199](../../../realdebrid.py#L199))*

**Purpose**: POST `/torrents/selectFiles/{id}` with comma-joined ids (or literal `"all"`).

**Contract**:
- Params: `file_ids: list[int] | str = "all"` — list → joined; a string passes through.
- Returns: `None` (204).
- Side effects: network; mutates RD-side torrent state.
- Raises: from `_request`.

**Called by**: `_select_files_during_wait` (inside `process_magnet`), [`check_torrent`](#check_torrentself-torrent_id-strategysmart-magnet---dict--realdebridpy462).

---

#### `delete_torrent(self, torrent_id)`  *([realdebrid.py:203](../../../realdebrid.py#L203))*

**Purpose**: DELETE `/torrents/delete/{id}`; swallows errors.

**Contract**: Never raises (catches `RealDebridError`, logs a WARNING). Used on `magnet_error` / `error` / nothing-to-pick submissions.

**Called by**: `_raise_if_terminal_failure` and `_select_files_during_wait` (both inside `process_magnet`).

---

#### `unrestrict_link(self, link: str) -> dict`  *([realdebrid.py:209](../../../realdebrid.py#L209))*

**Purpose**: POST `/unrestrict/link` — converts a hoster link into a direct download URL.

**Contract**: Returns dict with `download`, `filename`, `filesize`, `streamable`. Raises from `_request`.

**Called by**: [`_collect_links`](#_collect_linksself-info-dict---listdict--realdebridpy509).

---

#### `_extract_code(magnet: str) -> str | None`  *([realdebrid.py:213](../../../realdebrid.py#L213), staticmethod)*

**Purpose**: Pull JAV product code (e.g. `SNOS-192`, `IPZZ-851`) from the `dn=` parameter of a magnet URI.

**Contract**:
- Params: `magnet: str` (may be `""` / `None` — treated as no match).
- Returns: normalized code `LETTERS-NUMBERS` uppercased, or `None` if no `dn=` or no match.
- Side effects: none.
- Raises: none.
- Threading: pure.

**Regex**: `r"\b([A-Za-z]{2,6})[-_]?(\d{3,5})\b"` against the first `dn=` value as decoded by `urllib.parse.parse_qs` (`+` / `%XX`). Accepts 2-6 letters + 3-5 digits, optionally separated by `-`/`_`.

**Tested by**: `tests/test_core_logic.py` (`ExtractCode` cases). Behavioral contract: returns uppercase `ABCD-1234`; no match → `None`.

**Called by**: `_pick_smart` (via [`pick_files`](#pick_filesself-files-strategysmart-magnet---listint--realdebridpy243)) for `smart` strategy.

---

#### `_filename_matches_code(filename, code) -> bool`  *([realdebrid.py:234](../../../realdebrid.py#L234), staticmethod)*

**Purpose**: Tolerant containment check — case-insensitive, `_`/`-` interchangeable, separator-optional.

**Contract**:
- Params: `filename: str`, `code: str`.
- Returns: `True` if code (or its no-dash form) appears in the filename (also normalized to dash form); empty `code` → `False`.
- Side effects: none.

**Tested by**: `tests/test_core_logic.py` (`FilenameMatchesCode` cases).

**Called by**: `_smart_code_match` (smart strategy).

---

#### `pick_files(self, files, strategy="smart", magnet="") -> list[int]`  *([realdebrid.py:243](../../../realdebrid.py#L243))*

**Purpose**: Decide which files inside a torrent to download.

**Contract**:
- Params:
  - `files: list[dict]` — RD's file list. Each dict has `id`, `path`, `bytes`.
  - `strategy: "all" | "video" | "largest" | "smart"` — any other value is treated as `largest`.
  - `magnet: str` — used only by `smart` for `_extract_code`.
- Returns: `list[int]` of file ids. Empty `files` → `[]`.
- Side effects: logs at INFO/DEBUG/WARNING.
- Raises: none.

**Decision tree** (helpers: `_pick_video` :256, `_pick_largest` :261, `_pick_smart` :267 → `_smart_code_match` :283 / `_smart_size_filter` :300):

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

**Called by**: `_select_files_during_wait` (inside `process_magnet`), [`check_torrent`](#check_torrentself-torrent_id-strategysmart-magnet---dict--realdebridpy462).

---

#### `process_magnet(self, magnet, strategy="smart", cache_wait=15, progress=None, observer=None) -> dict`  *([realdebrid.py:310](../../../realdebrid.py#L310))*

**Purpose**: End-to-end flow: add magnet → poll until `waiting_files_selection` → call `pick_files`+`select_files` → poll until the `cache_wait` budget (wall clock, `time.time()`) is exhausted. If RD returns `downloaded`, collect unrestricted links. Otherwise, leave the torrent on RD and return `pending`.

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
  - Sleeps 0.8 s, then 1.5 s, then 3 s between subsequent polls (no sleep right after selecting files); the loop runs for up to `cache_wait` seconds plus the in-flight request (each request is additionally bounded by `self.deadline`).
  - Logs `=== 開始處理磁力 [<btih first 8>] ===` … `=== … 已快取/待處理 ===`.
- Raises:
  - `RealDebridError("磁力解析失敗: <filename>")` on `status=="magnet_error"` (after `delete_torrent`).
  - `RealDebridError("下載失敗")` on `status=="error"` (after `delete_torrent`).
  - `RealDebridError("沒有可選的檔案")` if `pick_files` returns empty (after `delete_torrent`).
  - Pass-through from sub-calls.
- Threading: blocking; called from worker threads in GUI.

**Calls**:
- internal: `_extract_magnet_hash` (:395), `add_magnet`, `torrent_info`, `_raise_if_terminal_failure` (:403 → `delete_torrent`), `_select_files_during_wait` (:420 → `pick_files`, `select_files`, `delete_torrent`, `_format_picked_names`), `_collect_links`, `_build_pending_result` (:440).
- external: `time.time`, `time.sleep`.

**Called by**: `RDDialog.worker` (in retired GUI); sidecar's `cmd_rd_send_magnet` (passes `observer=trail.append`, no `progress`).

---

#### `check_torrent(self, torrent_id, strategy="smart", magnet="") -> dict`  *([realdebrid.py:462](../../../realdebrid.py#L462))*

**Purpose**: Re-poll a previously-pending torrent. If still `waiting_files_selection`, auto-pick & re-select.

> **Deliberate contract — do not "fix" this.** When the retry finds nothing to pick, this path
> returns `pending`; it does **not** `delete_torrent` + raise the way `process_magnet` does. A
> review round proposed making the two paths symmetric and it was rejected: the pending-retry
> contract deliberately does not persist the magnet (`pending_torrents.json` must never contain
> magnet text), so a deleted torrent could never be re-sent — the user's only copy of that magnet
> may already be gone from the UI. Returning `pending` keeps the torrent recoverable. Existing
> tests pin this behaviour.

**Contract**:
- Params:
  - `torrent_id: str`.
  - `strategy: str` — for late selection.
  - `magnet: str = ""` — enables `smart` strategy's number match on retry. The sidecar always passes `""` (pending records never store the magnet), so live retries fall back to the size threshold.
- Returns:
  - completed → `{"status": "completed", "name", "torrent_id", "links": [...]}`
  - pending → `{"status": "pending", "name", "torrent_id", "progress", "rd_status"}`
  - missing → `{"status": "missing", "torrent_id"}` (the first `torrent_info` raised a `RealDebridError` whose message contains `"404"`)
- Side effects: network; when `waiting_files_selection` and `pick_files` returns ids, calls `select_files` then re-queries `torrent_info` once. Logs `重試時補選檔案 …`.
- Raises: passes through non-404 `RealDebridError`.
- Threading: blocking.

**Calls**: `torrent_info`, `pick_files`, `select_files`, `_collect_links`.

**Called by**: `RetryDialog.check_worker` (in retired GUI); sidecar's `cmd_rd_check_pending`.

---

#### `_collect_links(self, info: dict) -> list[dict]`  *([realdebrid.py:509](../../../realdebrid.py#L509))*

**Purpose**: Unrestrict every link on a completed torrent and aggregate results (one row per file).

**Contract**:
- Params: `info: dict` from `torrent_info`.
- Returns: `list[dict]` in the same order as `info["links"]` (empty when there are none), each either
  - `{"original", "download", "filename", "filesize", "streamable"}`, or
  - `{"original", "download": "", "filename": "", "filesize": 0, "streamable": 0, "error": "<msg>"}` if unrestrict failed.
- Side effects: N network calls (one per link) — a single link runs inline, more run on a `ThreadPoolExecutor(max_workers=min(4, N))` via `executor.map` (order preserved); logs each result.
- Raises: per-link `RealDebridError`s are caught and converted to error entries — the loop is best-effort.

**Called by**: `process_magnet`, `check_torrent`.

---

## 5. `javdb_scraper.py` (LIVE — M9 Phase 5-A)

Pure JavDB scraping core: HTTP session creation, magnet panel parsing, and the two size/file-count parsers. Extracted verbatim from the retired Tk GUI in M9 Phase 5-A so the sidecar daemon can import it without dragging tkinter into the bundle. Zero `app_logging` / `realdebrid` / `tkinter` deps — pure library.

### Module scope

- `HAS_CURL_CFFI: bool` — set at import time after `try: from curl_cffi import requests as cffi_requests` (`cffi_requests = None` on `ImportError`). Falls back to vanilla `requests`.
- `_SIZE_GB_RX`, `_SIZE_MB_RX`, `_FILE_COUNT_RX` — precompiled, bounded-quantifier regexes (`\d{1,12}(?:\.\d{1,12})?\s{0,4}GB|MB`, case-insensitive; `\d{1,9}\s{0,4}個文件`) so Sonar's super-linear-backtracking rule stays quiet.
- No other globals. No file paths. No logger.
- **Note**: `sys.stdout.reconfigure(...)` is NOT in this file (it's in `sidecar/sidecar.py` as a daemon-boundary responsibility).

### `create_session() -> tuple[Session, str]`  *([javdb_scraper.py:28](../../../javdb_scraper.py#L28))*

**Purpose**: Build an HTTP session with browser-impersonating headers, plus a label identifying which engine is in use.

**Contract**:
- Params: none.
- Returns: `(session, engine)` where `engine` is `"curl_cffi"` or `"requests"`.
- Side effects: none beyond the constructor calls.
- Raises: none under normal operation.

**Calls**: `cffi_requests.Session(impersonate="chrome124", headers=headers)` if `HAS_CURL_CFFI`; else `requests.Session()` + `headers.update(headers)` with an added Chrome 124 `User-Agent`.

**Called by**: [`sidecar.py::cmd_fetch_javdb`](../../../sidecar/sidecar.py).

### `parse_size_gb(size_str: str) -> float`  *([javdb_scraper.py:59](../../../javdb_scraper.py#L59))*

**Purpose**: Parse `"5.67GB, 5個文件"` → `5.67`. Falls back through `MB / 1024`. Returns `0.0` on no-match.

**Contract**: pure regex parse. Side-effect-free. Behavioral spec lives in `tests/test_core_logic.py::ParseSizeGB` (6 cases).

**Called by**: `sidecar/sidecar.py::_record_group_meta` (size rank for the outcome log); tests.

### `parse_file_count(size_str: str) -> int`  *([javdb_scraper.py:70](../../../javdb_scraper.py#L70))*

**Purpose**: Parse `"5.67GB, 5個文件"` → `5`. Returns sentinel `999` on no-match (used as "many files; deprioritize").

**Contract**: pure regex parse. Behavioral spec in `tests/test_core_logic.py::ParseFileCount` (4 cases). Not called by the sidecar.

### `fetch_magnets(url: str, session, cookies: dict) -> dict`  *([javdb_scraper.py:78](../../../javdb_scraper.py#L78))*

**Purpose**: Fetch a JavDB video page and parse the magnet panel + title + JAV code.

**Contract**:
- Params: `url`, `session` (returned by `create_session`), `cookies` dict.
- Returns: `{"url", "code", "title", "magnets": [...], "error": ""}`. `magnets` items each have `name / size / tags / date / magnet`. A non-200 status returns `{"url", "error": "HTTP <code>", "code": "", "title": "", "magnets": []}` instead of raising (the sidecar maps an error containing `403` to `cloudflare_block`, anything else to `network`). Missing title → `"未知"`.
- Side effects: **network** GET (`cookies=cookies`, timeout 30s, `allow_redirects=False`); no file I/O; no logging.
- Raises: lets `requests`/`curl_cffi` exceptions propagate. The sidecar's `cmd_fetch_javdb` catches them in its own `try` and returns `network` / `fetch failed: <ExceptionType>`.

**Calls**: `session.get`, `BeautifulSoup(html, "html.parser")`, soup `.find` / `.find_all` / `.select_one`.

**Called by**: [`sidecar.py::cmd_fetch_javdb`](../../../sidecar/sidecar.py).

**Selectors (data contract with JavDB HTML)**:
- Title: first `h2` with class `title`, then its `.current-title` descendant.
- Code: `.panel-block .value a` (then `parent.get_text(strip=True)` to include the prefix like `番號:`).
- Magnet rows: `#magnets-content` → `.item`, each with `.magnet-name a[href]` (rows without it are skipped), and inside that link `.name`, `.meta` (→ `size`), every `.tag`; the date comes from the item's `.date .time`.

---

## 6. `legacy/javdb_magnet_gui.py` (RETIRED — M9 Phase 5-B)

Pre-Tauri Tkinter desktop application. **No production importer** after M9 Phase 5-A; moved to `legacy/` in Phase 5-B. Kept under version control so future readers can study the original Tk UX without spelunking through `git log`. The actual source file is the canonical reference; this section is just an orientation map.

### File at a glance

Line ranges below refer to the **current** `legacy/javdb_magnet_gui.py` (offsets shifted from the pre-M9 root-path version because Phase 5-B added a RETIRED docstring banner at the top).

| Range | Section | Replaced by |
|---|---|---|
| `~49-51` | imports incl. `from legacy._legacy_env import load_env` (moved out of `realdebrid.py`, F-06) | n/a |
| `~58-60` | `COOKIE_FILE / ENV_FILE / PENDING_FILE` constants (`app_dir()/...`) | Rust `path_manager.rs` + `%APPDATA%\JavDBMagnet\` |
| `~63-94` | `load_pending / save_pending / add_pending / remove_pending` | Rust `pending.rs` |
| `~97-109` | `load_cookies` (file-based) | Rust `cookie_store.rs` (keyring) + `commands.rs::get_cookies_status` + sidecar `cmd_handshake` / `cmd_set_cookies` JSONL messages |
| `~112-189` | `create_session / parse_size_gb / parse_file_count / fetch_magnets` | **`javdb_scraper.py`** (extracted in M9 Phase 5-A; see §5 above) |
| `~192-590` | `class App` — Tk root window (toolbar, scrape form, magnet list, filter/sort/clipboard) | Svelte `app/src/App.svelte` (the entire SPA UI) |
| `~592-706` | `class RDInputDialog` — RD source picker dialog | Svelte App.svelte paste-magnet flow |
| `~708-905` | `class RDDialog` — batch send to RD with progress | Svelte App.svelte `sendBatch` + `lib/rdSender.ts` |
| `~907` | `RD_TOKEN_URL` constant | Svelte App.svelte settings panel "open RD token page" button |
| `~910-941` | `write_env(values)` — rewrite `.env` from settings dict | Rust `settings.rs::write_settings` (Tauri command) |
| `~943-1173` | `class SettingsDialog` — env editor with validation + RD probe | Svelte App.svelte settings section + `lib/settingsValidation.ts` |
| `~1174-1385` | `class RetryDialog` — re-poll pending torrents from disk | Svelte App.svelte `retryAllPending` + `lib/rdSender.ts::retryPending` |
| `~1386-1490` | DPI / font helpers (`_enable_dpi_awareness`, `_get_dpi_scale`, `_apply_dpi_scaling`, `_pick_font`, `_setup_fonts`, `_apply_ttk_font`) | WebView native handling — Tauri does not need these |
| `~1492-1523` | `__main__` boot block | n/a; the file is no longer an entry point |

### Why the file still exists in the repo

Three reasons, in priority order:

1. **`tests/test_app_logging.py::JavdbGuiImportSideEffects`** still imports it (`importlib.import_module("legacy.javdb_magnet_gui")`, stubbing `tkinter` when unavailable) to verify the lazy-logging contract: importing a module that does `from app_logging import get_logger` at top-level must NOT trigger `setup_logging()`. The module is the canary; if a future change adds an import-time side effect, the test fails.
2. **Historical reference**: the full pre-Tauri UX design (widget layout, dialog flow, retry/settings UX) lives in this file. git log can show the source but not navigate it; keeping the file in `legacy/` makes it browsable.
3. **Migration baseline**: any time the Tauri rewrite needs to confirm "what did the old GUI do here", the source is one click away.

### Why it's not in `sidecar.exe` (M9)

`spikes/pyinstaller_sidecar/build_sidecar.py` had `--hidden-import javdb_magnet_gui` until Phase 5-A; this was switched to `--hidden-import javdb_scraper` and the sidecar entry's `from javdb_magnet_gui import ...` was changed to `from javdb_scraper import ...`. With nothing in production importing the GUI module, PyInstaller no longer pulls tkinter / ttk / messagebox / DPI helpers into the bundle (-3.02 MiB).


## 7. Cross-file call graph (live sidecar paths)

The Python-side flows below are the ones still executed at runtime. The Tauri-side wiring (Svelte → Rust → JSONL → Python) is documented end-to-end in [`../function-contracts.md`](../function-contracts.md); this section only shows what happens **inside the sidecar process** once a JSONL command arrives.

### 7.1 Sidecar boot

```
sidecar/sidecar.py: import                    [sys.stdout.reconfigure(encoding="utf-8")]
sidecar/sidecar.py: __main__ → main(argv)
  └─ app_logging.setup_logging()             [lazy; respects JAVDB_LOG_DIR]
  └─ rd_outcome_log.configure(log dir | None) [None unless debug.log is file-backed]
  └─ run_daemon(stdin, stdout)
       └─ for each line on stdin:
            └─ dispatch(state, json.loads(line))
                 └─ cmd_<name>(state, req)
```

### 7.2 `cmd_fetch_javdb` (JavDB scrape)

```
cmd_fetch_javdb(state, req)
  ├─ _validate_batch_id → _begin_scrape_meta_batch → _validate_javdb_url (https + *.javdb.com)
  ├─ javdb_scraper.create_session()                [curl_cffi or requests]
  ├─ javdb_scraper.fetch_magnets(url, session, state.cookies)
  │    └─ session.get(url) → BeautifulSoup parse
  ├─ _process_scraped_magnets → _intern_magnet / redact_magnet
  ├─ _record_group_meta (javdb_scraper.parse_size_gb for size rank)
  └─ envelope: {ok, request_id, result: {engine, url, code, title, magnet_count,
                 magnets:[{handle_id, name, size, tags, date, magnet_redacted}]}}
```

(Cookies arrive earlier via `cmd_handshake` / `cmd_set_cookies`, not from disk.)

### 7.3 `cmd_rd_send_magnet` (single magnet to RD)

```
cmd_rd_send_magnet(state, req)
  ├─ _rd_client(state, min_size_mb, deadline) → RealDebrid(token, min_size_mb, deadline=…)
  │                                              + shared state.rd_session
  ├─ rd.process_magnet(magnet, strategy, cache_wait, observer=trail.append)
  │    ├─ rd.add_magnet()                  → POST /torrents/addMagnet
  │    ├─ loop (until time.time() + cache_wait):
  │    │    rd.torrent_info()              → GET  /torrents/info/{id}
  │    │    if status == magnet_error/error:
  │    │      rd.delete_torrent()          → DELETE /torrents/delete/{id}
  │    │      raise RealDebridError
  │    │    if status == waiting_files_selection (first time):
  │    │      rd.pick_files(files, strategy, magnet)
  │    │        └─ _extract_code / _filename_matches_code  [smart strategy]
  │    │      rd.select_files()            → POST /torrents/selectFiles/{id}
  │    │    if status == downloaded:
  │    │      rd._collect_links(info)
  │    │        └─ rd.unrestrict_link(...) → POST /unrestrict/link
  │    │    time.sleep(0.8 → 1.5 → 3)
  │    └─ timeout → pending dict
  ├─ rd.close()                            [finally]
  ├─ rd_outcome_log.log_send(...)          [every exit path]
  └─ envelope: {ok, status:"completed", torrent_id, name, links}
             | {ok, status:"pending", torrent_id, name, rd_status, progress, files_selected, strategy}
```

(Pending state lives in Rust `pending.rs`; the sidecar does not write the pending JSON file.)

### 7.4 `cmd_rd_check_pending` (re-poll one pending torrent)

```
cmd_rd_check_pending(state, req)
  ├─ _rd_client(state, deadline=monotonic()+50) → RealDebrid(token, min_size_mb, deadline=…)
  ├─ rd.check_torrent(torrent_id, strategy=req.strategy | settings | "smart", magnet="")
  │    ├─ rd.torrent_info()
  │    ├─ if waiting_files_selection: rd.pick_files / rd.select_files / re-query
  │    ├─ if downloaded: rd._collect_links → unrestrict_link*
  │    └─ if 404: {status: "missing"}
  ├─ rd_outcome_log.log_check(...)         [every exit path]
  └─ envelope: {ok, status: completed | missing | pending, torrent_id, …}
```

(The frontend's `rdSender.ts::retryPending` invokes Rust `rd_check_pending` once per pending entry; orchestration lives in `App.svelte::retryAllPending`.)

### 7.5 `cmd_rd_user` and `cmd_rd_set_token` (settings panel "test RD" + token write)

```
cmd_rd_user(state, req)
  └─ _rd_client(state, token_override, deadline=monotonic()+50).user()
       └─ _request("GET", "/user") → {user: {username, type, expiration, points}}

cmd_rd_set_token(state, req)
  ├─ null / "" → clear; invalid format → bad_request "rd_token_format_invalid"
  ├─ token changed → close + drop state.rd_session
  └─ state.rd_token = req["token"]   [in-memory only; persistence is Rust-side]
```

The retired GUI's "settings → save" flow (`SettingsDialog.save` → `write_env(values)`) does not exist in the live runtime; settings are written by the Rust Tauri command `settings.rs::write_settings`.

---

## 8. What survives, M9 edition

### Live in `sidecar.exe`

| Module | Role |
| --- | --- |
| `app_logging.py` | Sidecar `main` calls `setup_logging`; `realdebrid.py` uses `get_logger`. Log dir controlled via `JAVDB_LOG_DIR` (set by Rust at spawn). |
| `rd_outcome_log.py` | Sidecar `main` calls `configure`; `cmd_rd_send_magnet` / `cmd_rd_check_pending` call `log_send` / `log_check`. |
| `realdebrid.py` | Sidecar's `rd_*` commands call `RealDebrid.user` / `process_magnet` / `check_torrent` (which use `pick_files` internally). 401/403 mapping inherited; 429 retry is now capped (`MAX_RETRY_AFTER_SECONDS`, 3 retries) and every request is bounded by the sidecar's `time.monotonic()` deadline. |
| `javdb_scraper.py` | `cmd_fetch_javdb` calls `create_session` + `fetch_magnets`; `_record_group_meta` uses `parse_size_gb`; `tests/test_core_logic.py` exercises `parse_size_gb` + `parse_file_count`. M9 Phase 5-A; replaced the import from `javdb_magnet_gui`. |

PyInstaller hidden-imports for the live sidecar build are exactly: `curl_cffi`, `curl_cffi.requests`, `javdb_scraper`, `realdebrid`, `app_logging`, `rd_outcome_log` (plus `--collect-all curl_cffi`). No `javdb_magnet_gui`, no `tkinter`.

### Replaced by other layers (no longer Python-side)

- **Settings persistence** (was `load_env` / `write_env`): Rust `settings.rs` (`read_settings` / `write_settings` Tauri commands). `load_env` itself survives only as `legacy/_legacy_env.py`.
- **Pending-queue file** (was `load_pending`/`save_pending`/`add_pending`/`remove_pending`): Rust `pending.rs`.
- **Cookies file read** (was `javdb_magnet_gui.load_cookies`): Rust `cookie_store.rs` + `commands.rs::get_cookies_status` / `save_cookies` / `clear_cookies` + sidecar `cmd_handshake` / `cmd_set_cookies` JSONL handoff.
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
