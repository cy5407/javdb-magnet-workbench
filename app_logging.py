"""統一的 logging 設定

使用方式：
    from app_logging import setup_logging, get_logger
    setup_logging()  # 在程式開頭呼叫一次
    logger = get_logger(__name__)
    logger.info("...")
    logger.debug("...")  # 只寫入檔案，不顯示在 console

環境變數：
    DEBUG=1  → console 也輸出 DEBUG 等級訊息
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def app_dir() -> Path:
    """回傳應用程式所在目錄（支援打包後的 .exe）"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


LOG_DIR = app_dir() / "logs"
LOG_FILE = LOG_DIR / "debug.log"

_initialized = False


def setup_logging(debug: bool = False) -> Path:
    """設定 logging。回傳 log 檔案路徑。"""
    global _initialized
    if _initialized:
        return LOG_FILE

    LOG_DIR.mkdir(exist_ok=True)

    debug = debug or os.environ.get("DEBUG") == "1"

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()

    # 檔案：永遠記錄 DEBUG 等級
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    root.addHandler(file_handler)

    # Console：依 debug 旗標決定 INFO 或 DEBUG
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.DEBUG if debug else logging.INFO)
    console_handler.setFormatter(logging.Formatter(
        "[%(levelname)s] %(name)s: %(message)s",
    ))
    root.addHandler(console_handler)

    # 第三方套件降低噪音
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)

    _initialized = True
    logging.getLogger(__name__).info(f"Logging initialized. File: {LOG_FILE}")
    return LOG_FILE


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
