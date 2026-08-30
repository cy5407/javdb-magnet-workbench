"""RD 送出成效日誌 —— 一行一次觀測的 JSONL，供事後分析啟發式的命中率。

規格：docs/specs/2026-08-01-rd-outcome-log.md

設計原則（§2）：**只記觀測，不記判定**。這裡不寫 `rd_class` / `tier` / `is_hd`
之類的衍生結論，只寫 JavDB 原樣給的 `name` / `tags` / `date` / `size` 與 RD 實際
回報的結果。三個理由：判定規則的唯一來源留在 `app/src/lib/rdPriority.ts`（Python
不複製前綴清單與解析度正則）；規則改版後舊日誌仍能整批重跑；日後想檢驗全新的
訊號也不必改格式。假設寫在 scripts/rd_log_report.py，觀測寫在這裡。

安全（§6）：本檔寫進 log 目錄，而 docs/troubleshooting/log-redaction-verification.md
與 docs/sessions/m6a-release-smoke.md 的發布 gate 會 grep 整個 log 目錄找
`magnet:\\?xt|urn:btih` 並預期零輸出。因此每一行寫出前都會過一次
`_FORBIDDEN_RX`，命中就整行丟棄 —— 這是 defense in depth，比照 pending.rs 對
落地檔做 raw-text 斷言的做法：真正的保證來自呼叫端不傳 magnet，但序列化器或
欄位被改動時，這道關卡讓既有的發布 gate 不會突然開始誤報。

本模組的任何失敗都不得讓送出失敗 —— 所有寫入路徑都吞例外。
"""

import json
import logging
import os
import re
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Optional

SCHEMA_VERSION = 1

_LOG_FILE_NAME = "rd_outcomes.jsonl"
_LOGGER_NAME = "rd_outcomes"

# 比照 app_logging.py:85-87 的 debug.log 參數。刻意不套 pending.rs 那種讀取端
# 硬上限 —— 它超過 4 MiB 就永久 Err，套在只增不減的日誌上會直接鎖死。
_MAX_BYTES = 5 * 1024 * 1024
_BACKUP_COUNT = 3

# 見 module docstring。大小寫不敏感：redact_magnet() 輸出小寫，但 JavDB 的
# `dn=` 內容與未來的欄位不保證。
_FORBIDDEN_RX = re.compile(r"urn:btih|magnet:\?xt", re.IGNORECASE)

# 狀態序列的長度上限。連續重複會先被摺疊，所以正常一筆只有 2-3 個；上限純粹
# 是避免 RD 在長 cache_wait 下反覆跳動時把單行撐大。
MAX_STATUS_TRAIL = 8

_logger: Optional[logging.Logger] = None
_configured = False
_log_path: Optional[Path] = None
# 只為測試與診斷而存在：被 _FORBIDDEN_RX 擋下的行數。
_dropped_count = 0


def is_enabled() -> bool:
    """`JAVDB_RD_LOG=0` 關閉，其餘（含未設定）皆啟用。

    預設開啟是刻意的：不開就永遠累積不到樣本，這份日誌也就沒有存在意義。
    比照 JAVDB_LOG_DIR 的環境變數慣例，不進設定檔、不進 Rust。
    """
    return os.environ.get("JAVDB_RD_LOG", "").strip() != "0"


def configure(log_dir: Optional[Path]) -> Optional[Path]:
    """建立（冪等）專用 logger 與 rotating handler，回傳實際落地路徑。

    `log_dir` 為 None（app_logging 降級成 console-only，例如 Linux/macOS 上沒有
    LOCALAPPDATA）或不可寫時，本功能靜默停用並回傳 None —— 日誌是輔助功能，
    不得因為寫不了而影響送出。
    """
    global _logger, _configured, _log_path
    if _configured:
        return _log_path
    _configured = True

    if not is_enabled() or log_dir is None:
        return None
    # Only a real path-like is acceptable. `Path(x)` will happily stringify
    # anything with a __fspath__ or a str form, and this function's next move
    # is mkdir(parents=True) — so a stray object turns into a directory tree
    # created wherever the process happens to be running. A test that mocks
    # setup_logging() and hands us the resulting MagicMock did exactly that.
    if not isinstance(log_dir, (str, Path)):
        return None

    try:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / _LOG_FILE_NAME
        handler = RotatingFileHandler(
            path, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8",
        )
        # 訊息本身就是完整的 JSON 物件，formatter 不得再加時間或層級前綴，
        # 否則每行就不是合法 JSON 了。
        handler.setFormatter(logging.Formatter("%(message)s"))
    except OSError:
        return None

    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.addHandler(handler)
    # app_logging.py 把 handler 掛在 root（:95、:105）。不切斷傳播的話，每一行
    # JSON 會同時灌進 debug.log —— 除了重複，還會把番號與檔名帶去一個沒打算
    # 承載它們的檔案。
    logger.propagate = False

    _logger = logger
    _log_path = path
    return path


def reset_for_tests() -> None:
    """丟棄模組狀態，讓測試能對不同 log_dir 重新 configure。"""
    global _logger, _configured, _log_path, _dropped_count
    if _logger is not None:
        for h in _logger.handlers:
            try:
                h.close()
            except Exception:
                pass
        _logger.handlers.clear()
    _logger = None
    _configured = False
    _log_path = None
    _dropped_count = 0


def dropped_count() -> int:
    """被 redaction 關卡擋下的行數（測試與診斷用）。"""
    return _dropped_count


def get_log_path() -> Optional[Path]:
    return _log_path


def _now_iso() -> str:
    """本地時間 + 毫秒 + 時區位移。

    毫秒是必要的：`elapsed_ms` 量的是單筆送出，而 send 與後續 check 事件要靠
    時間差推算「pending 之後多久才完成」，秒級精度會把快取命中壓成 0。
    （debug.log 的 formatter 是秒級且無時區 —— 本檔刻意不沿用。）
    """
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def _emit(payload: dict) -> None:
    global _dropped_count
    if _logger is None:
        return
    try:
        line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        return
    if _FORBIDDEN_RX.search(line):
        # 整行丟棄。刻意不把 payload 寫進任何其他 logger —— 那等於把剛剛判定
        # 為不該落地的內容換個檔案寫出去。
        _dropped_count += 1
        return
    try:
        _logger.info(line)
    except Exception:
        # 磁碟滿、檔案被鎖、輪替失敗 —— 一律吞掉。
        pass


def _clean_status_trail(trail: Any) -> list:
    """摺疊連續重複並截斷。非 list 或非字串元素一律丟棄。"""
    if not isinstance(trail, list):
        return []
    out: list = []
    for s in trail:
        if not isinstance(s, str) or not s:
            continue
        if out and out[-1] == s:
            continue
        out.append(s)
        if len(out) >= MAX_STATUS_TRAIL:
            break
    return out


def log_send(
    *,
    outcome: str,
    elapsed_ms: int,
    btih8: str = "",
    torrent_id: str = "",
    rd_status: str = "",
    status_trail: Any = None,
    progress: Any = 0,
    files_selected: bool = False,
    link_count: int = 0,
    error_code: Optional[str] = None,
    meta: Optional[dict] = None,
    cache_wait: Optional[int] = None,
    file_pick: str = "",
    min_size_mb: Optional[int] = None,
) -> None:
    """記一次送出觀測。

    `meta` 是 fetch 當下留存的 JavDB 列資訊（name/size/tags/date/code 與群組排名）；
    手貼磁力只會有 name，其餘為空 —— 缺 metadata 不是低品質的證據，分析時要當
    「未知」處理而不是「非高清」。

    註：`cache_wait` / `file_pick` / `min_size_mb` 必須以 keyword-only 具名參數
    存在，嚴禁收進 `**kwargs`。具名參數能保證呼叫端若打錯欄位名稱時立刻拋出
    TypeError；本模組是觀測資料的唯一來源，靜默吞掉欄位將導致分析資料失真且難以察覺。
    SonarCloud 的「參數數量不超過 13 個」規則在此刻意不遵守。
    """
    meta = meta or {}
    payload = {
        "v": SCHEMA_VERSION,
        "ts": _now_iso(),
        "event": "send",
        "btih8": btih8,
        "torrent_id": torrent_id,
        "outcome": outcome,
        "elapsed_ms": elapsed_ms,
        "rd_status": rd_status,
        "status_trail": _clean_status_trail(status_trail),
        "progress": progress,
        "files_selected": bool(files_selected),
        "link_count": link_count,
        "error_code": error_code,
        # ---- fetch 當下的原始觀測（不含任何判定）----
        "code": meta.get("code", ""),
        "name": meta.get("name", ""),
        "size": meta.get("size", ""),
        "tags": list(meta.get("tags", []) or []),
        "date": meta.get("date", ""),
        "source": meta.get("source", ""),
        "group_seq": meta.get("group_seq"),
        "group_size": meta.get("group_size"),
        "date_rank": meta.get("date_rank"),
        "size_rank": meta.get("size_rank"),
        # ---- 混淆變數：沒有它們就無法跨時間比較 ----
        "cache_wait": cache_wait,
        "file_pick": file_pick,
        "min_size_mb": min_size_mb,
    }
    _emit(payload)


def log_check(
    *,
    outcome: str,
    elapsed_ms: int,
    torrent_id: str = "",
    rd_status: str = "",
    progress: Any = 0,
    link_count: int = 0,
    error_code: Optional[str] = None,
) -> None:
    """記一次重試觀測，以 `torrent_id` 與 send 事件 join。

    這是把「pending」從單一標籤拆成「四分鐘後完成」與「三天後仍沒有」的唯一
    依據 —— 少了它，所有 pending 在分析時長得一模一樣。
    """
    _emit({
        "v": SCHEMA_VERSION,
        "ts": _now_iso(),
        "event": "check",
        "torrent_id": torrent_id,
        "outcome": outcome,
        "elapsed_ms": elapsed_ms,
        "rd_status": rd_status,
        "progress": progress,
        "link_count": link_count,
        "error_code": error_code,
    })
