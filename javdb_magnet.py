"""
JavDB 磁力連結擷取工具

Cookie 取得方式：
1. 用瀏覽器開啟 JavDB 並登入
2. 按 F12 開啟開發者工具 → Application → Cookies
3. 複製所有 cookie 值，貼到同目錄下的 cookies.txt
4. 格式為瀏覽器複製出的原始字串，例如：
   _jdb_session=xxxxx; cf_clearance=xxxxx; locale=zh; ...
"""

import sys
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from curl_cffi import requests as cffi_requests
    HAS_CURL_CFFI = True
except ImportError:
    cffi_requests = None
    HAS_CURL_CFFI = False

import requests
from bs4 import BeautifulSoup

COOKIE_FILE = Path(__file__).parent / "cookies.txt"


def load_cookies() -> dict[str, str]:
    if not COOKIE_FILE.exists():
        return {}
    raw = COOKIE_FILE.read_text(encoding="utf-8").strip()
    if not raw:
        return {}
    cookies = {}
    for pair in raw.split(";"):
        pair = pair.strip()
        if "=" in pair:
            key, value = pair.split("=", 1)
            cookies[key.strip()] = value.strip()
    return cookies


def get_magnets(url: str):
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

    cookies = load_cookies()
    if cookies:
        print(f"已載入 {len(cookies)} 個 cookie")
    else:
        print("未找到 cookies.txt，將不帶 cookie 請求（磁力連結可能需要登入）")

    if HAS_CURL_CFFI:
        session = cffi_requests.Session(impersonate="chrome124", headers=headers, timeout=30.0)
        resp = session.get(url, cookies=cookies)
        print("使用 curl_cffi（模擬瀏覽器 TLS 指紋）")
    else:
        headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        resp = requests.get(url, headers=headers, cookies=cookies, timeout=30)
        print("使用 requests（建議安裝 curl_cffi: pip install curl_cffi）")

    if resp.status_code != 200:
        print(f"請求失敗，狀態碼: {resp.status_code}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")

    title_tag = soup.select_one("h2.title.is-4 .current-title")
    title = title_tag.text.strip() if title_tag else "未知"

    code_tag = soup.select_one(".panel-block .value a")
    code = ""
    if code_tag:
        parent = code_tag.parent
        code = parent.get_text(strip=True) if parent else code_tag.text.strip()

    print()
    print(f"番號: {code}")
    print(f"標題: {title}")
    print("=" * 60)

    items = soup.select("#magnets-content .item")
    if not items:
        print("找不到磁力連結（可能需要登入，請確認 cookies.txt）")
        return []

    magnets = []
    for i, item in enumerate(items, 1):
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

        magnets.append({
            "name": name,
            "size": meta,
            "tags": tags,
            "date": date,
            "magnet": magnet_url,
        })

        tag_str = f"  [{', '.join(tags)}]" if tags else ""
        print(f"\n#{i} {name}  {meta}{tag_str}  ({date})")
        print(f"   {magnet_url}")

    print(f"\n共找到 {len(magnets)} 個磁力連結")
    return magnets


if __name__ == "__main__":
    url = input("請輸入 JavDB 影片頁面網址: ").strip()
    if url:
        get_magnets(url)
