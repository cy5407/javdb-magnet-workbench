"""JavDB 抓取核心：HTTP session + magnet 解析 + size/count parsers.

從 javdb_magnet_gui.py 抽出，讓 sidecar/sidecar.py 與測試不必 import
整個 1494-line Tkinter GUI 檔案。本模組沒有 logging / app_logging /
realdebrid / tkinter 依賴，可被 PyInstaller 乾淨打包進 sidecar.exe
而不會把 Tk 拖進來。

Source-of-truth note:
- M9 起 sidecar 使用本檔；javdb_magnet_gui.py 仍保留同名函數（legacy
  GUI 內部用），但 sidecar.exe 不再 bundle javdb_magnet_gui。
- stdout encoding 不在這裡處理 —— 那是 daemon entry (sidecar/sidecar.py)
  的責任，本檔是純 library。
"""

import re

try:
    from curl_cffi import requests as cffi_requests
    HAS_CURL_CFFI = True
except ImportError:  # pragma: no cover — env-dependent fallback (curl_cffi missing)
    cffi_requests = None
    HAS_CURL_CFFI = False

import requests
from bs4 import BeautifulSoup


def create_session():
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,ja;q=0.8,en-US;q=0.7,en;q=0.6",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }
    if HAS_CURL_CFFI:
        return cffi_requests.Session(impersonate="chrome124", headers=headers), "curl_cffi"
    headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    session = requests.Session()
    session.headers.update(headers)
    return session, "requests"


# Bounded number quantifiers keep the size/count regexes linear: with `+`
# on `[\d.]` the engine can revisit the same bytes O(n) times across
# starting positions, which Sonar flags as super-linear (polynomial)
# backtracking. JavDB never emits sizes wider than a handful of digits,
# so a tight upper bound is both safe and behavior-preserving.
_SIZE_GB_RX = re.compile(r"(\d{1,12}(?:\.\d{1,12})?)\s{0,4}GB", re.IGNORECASE)
_SIZE_MB_RX = re.compile(r"(\d{1,12}(?:\.\d{1,12})?)\s{0,4}MB", re.IGNORECASE)
_FILE_COUNT_RX = re.compile(r"(\d{1,9})\s{0,4}個文件")


def parse_size_gb(size_str: str) -> float:
    """從 '5.67GB, 5個文件' 這類字串中解析出 GB 數值"""
    m = _SIZE_GB_RX.search(size_str)
    if m:
        return float(m.group(1))
    m = _SIZE_MB_RX.search(size_str)
    if m:
        return float(m.group(1)) / 1024
    return 0.0


def parse_file_count(size_str: str) -> int:
    """從 '5.67GB, 5個文件' 這類字串中解析出文件數量"""
    m = _FILE_COUNT_RX.search(size_str)
    if m:
        return int(m.group(1))
    return 999


def fetch_magnets(url: str, session, cookies: dict) -> dict:
    resp = session.get(url, cookies=cookies, timeout=30, allow_redirects=False)
    if resp.status_code != 200:
        return {"url": url, "error": f"HTTP {resp.status_code}", "code": "", "title": "", "magnets": []}

    soup = BeautifulSoup(resp.text, "html.parser")

    title_tag = soup.select_one("h2.title.is-4 .current-title")
    title = title_tag.text.strip() if title_tag else "未知"

    code_tag = soup.select_one(".panel-block .value a")
    code = ""
    if code_tag:
        parent = code_tag.parent
        code = parent.get_text(strip=True) if parent else code_tag.text.strip()

    magnets = []
    for item in soup.select("#magnets-content .item"):
        link_tag = item.select_one(".magnet-name a")
        if not link_tag:
            continue
        magnet_url = link_tag.get("href", "")
        name = ""
        name_tag = link_tag.select_one(".name")
        if name_tag:
            name = name_tag.text.strip()
        meta = ""
        meta_tag = link_tag.select_one(".meta")
        if meta_tag:
            meta = meta_tag.text.strip()
        tags = [t.text.strip() for t in link_tag.select(".tag")]
        date = ""
        date_tag = item.select_one(".date .time")
        if date_tag:
            date = date_tag.text.strip()
        magnets.append({"name": name, "size": meta, "tags": tags, "date": date, "magnet": magnet_url})

    return {"url": url, "code": code, "title": title, "magnets": magnets, "error": ""}
