"""Python sidecar — Tauri/Rust 透過 stdin/argv 呼叫 Python 抓 JavDB 的協定 spike

設計原則：
- stdout 只輸出**單一** JSON 物件，不混 log
- stderr 可輸出錯誤診斷，但不輸出 cookies、不輸出完整 magnet
- 不讀也不輸出 .env / RD token
- 不複製主程式邏輯，從 javdb_magnet_gui 重用 create_session/load_cookies/fetch_magnets

CLI：
    python sidecar.py fetch-javdb <url>

回傳的 magnet 一律遮蔽：保留 `magnet:?xt=urn:btih:` + hash 前 8 碼 + `...`
"""

import json
import re
import sys
from pathlib import Path

# 把 repo root 加到 sys.path 以便 import 既有模組
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 匯入既有模組（會觸發 logging.setup_logging，但其 console handler 寫 stderr 不影響 stdout）
from javdb_magnet_gui import create_session, load_cookies, fetch_magnets  # noqa: E402


def redact_magnet(uri: str) -> str:
    """保留 magnet:?xt=urn:btih: + hash 前 8 碼，其餘截掉"""
    if not uri:
        return ""
    m = re.match(r"^(magnet:\?xt=urn:btih:)([a-fA-F0-9]+)", uri)
    if m:
        return f"{m.group(1)}{m.group(2)[:8]}..."
    return "magnet:..." if uri.startswith("magnet:") else "<not-a-magnet>"


def cmd_fetch_javdb(url: str) -> dict:
    cookies = load_cookies()
    session, engine = create_session()
    result = fetch_magnets(url, session, cookies)

    error = result.get("error", "") or None
    magnets_in = result.get("magnets", []) or []
    magnets_out = [
        {
            "name": m.get("name", ""),
            "size": m.get("size", ""),
            "tags": list(m.get("tags", [])),
            "date": m.get("date", ""),
            "magnet_redacted": redact_magnet(m.get("magnet", "")),
        }
        for m in magnets_in
    ]

    return {
        "ok": (not error) and len(magnets_out) > 0,
        "command": "fetch-javdb",
        "engine": engine,
        "url": url,
        "code": result.get("code", "") or "",
        "title": result.get("title", "") or "",
        "magnet_count": len(magnets_out),
        "magnets": magnets_out,
        "error": error,
    }


def usage():
    print("用法: python sidecar.py fetch-javdb <url>", file=sys.stderr)


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        usage()
        return 2
    cmd = argv[1]
    if cmd != "fetch-javdb":
        print(f"未支援的命令: {cmd}", file=sys.stderr)
        usage()
        return 2

    url = argv[2]
    if not url.startswith(("http://", "https://")):
        print("URL 必須以 http(s) 開頭", file=sys.stderr)
        return 2

    try:
        payload = cmd_fetch_javdb(url)
    except Exception as e:
        # 為避免 traceback 洩漏未來命令的敏感參數（cookies、tokens、完整 magnet、stdin 內容），
        # stderr 只寫例外型別，不寫 message、stack frame 或變數內容。
        # stdout 仍輸出有效 JSON，讓呼叫端能 parse。error 訊息也只保留型別。
        print(f"sidecar error: {type(e).__name__}", file=sys.stderr)
        payload = {
            "ok": False,
            "command": "fetch-javdb",
            "engine": "unknown",
            "url": url,
            "code": "",
            "title": "",
            "magnet_count": 0,
            "magnets": [],
            "error": f"{type(e).__name__}: <redacted>",
        }

    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    sys.stdout.write("\n")
    sys.stdout.flush()
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
