"""JavDB 磁力連結擷取工具 - GUI 版 — RETIRED (M9).

⚠️ 此檔已退役，僅作歷史參考，不在 production runtime 中執行。

Production runtime 是 Tauri / Svelte / Rust + sidecar daemon：

| 舊 (本檔) | 新 |
|---|---|
| `create_session` / `fetch_magnets` / `parse_size_gb` / `parse_file_count` | `javdb_scraper.py` (字面相同) |
| `load_pending` / `save_pending` / `add_pending` / `remove_pending` | Rust `app/src-tauri/src/pending.rs` |
| `load_cookies` + `COOKIE_FILE` | Rust `commands.rs::cookies_status` + sidecar `cmd_handshake` |
| `write_env` + `ENV_FILE` | Rust `app/src-tauri/src/settings.rs` |
| `class App` (主視窗 / 篩選 / 排序 / 清單) | Svelte `app/src/App.svelte` |
| `class RDInputDialog` | Svelte App.svelte paste-magnet flow |
| `class RDDialog` (批次送 RD + 進度) | Svelte App.svelte sendBatch + `lib/rdSender.ts` |
| `class SettingsDialog` | Svelte App.svelte settings 區塊 + `lib/settingsValidation.ts` |
| `class RetryDialog` | Svelte App.svelte retryAllPending + `lib/magnetUtils.ts::retryPending` |
| `_enable_dpi_awareness` / `_setup_fonts` 等 DPI/font helpers | WebView native handling |

保留本檔的目的是讓未來讀者能直接看到 pre-Tauri 的 Tk 設計（widget 排版、
dialog 流程、retry / settings UX），不必去翻 git log 還原。請勿 import
本檔到 production code、build script 或 sidecar bundle。
"""

import json
import re
import sys
import threading
import time
import webbrowser
from datetime import datetime
from secrets import randbelow
import tkinter as tk
from tkinter import ttk, messagebox

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

from app_logging import setup_logging, get_logger, app_dir, get_log_file
from realdebrid import RealDebrid, RealDebridError
from legacy._legacy_env import load_env

logger = get_logger(__name__)

# TODO(M7): legacy paths next to the exe — migration moves these to
#           %APPDATA%\JavDBMagnet\ as part of milestone M7. Until then,
#           the tkinter app keeps the original behavior.
COOKIE_FILE = app_dir() / "cookies.txt"
ENV_FILE = app_dir() / ".env"
PENDING_FILE = app_dir() / "pending_torrents.json"


def load_pending() -> list[dict]:
    if not PENDING_FILE.exists():
        return []
    try:
        return json.loads(PENDING_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"載入待處理清單失敗: {e}")
        return []


def save_pending(items: list[dict]):
    try:
        PENDING_FILE.write_text(
            json.dumps(items, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        logger.error(f"儲存待處理清單失敗: {e}")


def add_pending(item: dict):
    items = load_pending()
    # 用 torrent_id 去重
    items = [x for x in items if x.get("torrent_id") != item.get("torrent_id")]
    items.append(item)
    save_pending(items)


def remove_pending(torrent_id: str):
    items = load_pending()
    items = [x for x in items if x.get("torrent_id") != torrent_id]
    save_pending(items)


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
        return cffi_requests.Session(impersonate="chrome124", headers=headers, timeout=30.0), "curl_cffi"
    headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    session = requests.Session()
    session.headers.update(headers)
    return session, "requests"


def parse_size_gb(size_str: str) -> float:
    """從 '5.67GB, 5個文件' 這類字串中解析出 GB 數值"""
    m = re.search(r"([\d.]+)\s*GB", size_str, re.IGNORECASE)
    if m:
        return float(m.group(1))
    m = re.search(r"([\d.]+)\s*MB", size_str, re.IGNORECASE)
    if m:
        return float(m.group(1)) / 1024
    return 0.0


def parse_file_count(size_str: str) -> int:
    """從 '5.67GB, 5個文件' 這類字串中解析出文件數量"""
    m = re.search(r"(\d+)\s*個文件", size_str)
    if m:
        return int(m.group(1))
    return 999


def fetch_magnets(url: str, session, cookies: dict) -> dict:
    resp = session.get(url, cookies=cookies, timeout=30)
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


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("JavDB 磁力連結擷取工具")
        root.geometry("900x700")
        root.minsize(700, 550)

        style = ttk.Style()
        style.configure("TButton", padding=4)

        # --- 上方：URL 輸入區 ---
        input_frame = ttk.LabelFrame(root, text="貼上網址（每行一個）", padding=8)
        input_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        self.url_text = tk.Text(input_frame, height=5, font=("Consolas", 10))
        self.url_text.pack(fill=tk.X)

        # --- 按鈕列 ---
        btn_frame = ttk.Frame(root, padding=(10, 4))
        btn_frame.pack(fill=tk.X)

        self.btn_start = ttk.Button(btn_frame, text="開始擷取", command=self.start_scrape)
        self.btn_start.pack(side=tk.LEFT)

        self.btn_copy_all = ttk.Button(btn_frame, text="複製篩選後的磁力連結", command=self.copy_all_magnets)
        self.btn_copy_all.pack(side=tk.LEFT, padx=(8, 0))

        self.btn_clear = ttk.Button(btn_frame, text="清空結果", command=self.clear_results)
        self.btn_clear.pack(side=tk.LEFT, padx=(8, 0))

        self.btn_send_rd = ttk.Button(btn_frame, text="送至 Real-Debrid", command=self.send_to_realdebrid)
        self.btn_send_rd.pack(side=tk.LEFT, padx=(8, 0))

        self.btn_retry = ttk.Button(btn_frame, text="重試待處理", command=self.open_retry)
        self.btn_retry.pack(side=tk.LEFT, padx=(8, 0))

        self.btn_log = ttk.Button(btn_frame, text="查看日誌", command=self.open_log)
        self.btn_log.pack(side=tk.LEFT, padx=(8, 0))

        self.btn_settings = ttk.Button(btn_frame, text="設定", command=self.open_settings)
        self.btn_settings.pack(side=tk.LEFT, padx=(8, 0))

        self.btn_theme = ttk.Button(btn_frame, text="🌙", width=3, command=self.toggle_theme)
        self.btn_theme.pack(side=tk.LEFT, padx=(8, 0))

        self.status_var = tk.StringVar(value="就緒")
        ttk.Label(btn_frame, textvariable=self.status_var).pack(side=tk.RIGHT)

        # --- 篩選列 ---
        filter_frame = ttk.LabelFrame(root, text="篩選", padding=8)
        filter_frame.pack(fill=tk.X, padx=10, pady=(0, 5))

        # 第一列
        filter_row1 = ttk.Frame(filter_frame)
        filter_row1.pack(fill=tk.X)

        # 關鍵字
        ttk.Label(filter_row1, text="關鍵字:").pack(side=tk.LEFT)
        self.filter_keyword = tk.StringVar()
        self.filter_keyword.trace_add("write", lambda *_: self.apply_filter())
        keyword_entry = ttk.Entry(filter_row1, textvariable=self.filter_keyword, width=20)
        keyword_entry.pack(side=tk.LEFT, padx=(4, 12))

        # 只顯示高清
        self.filter_hd = tk.BooleanVar(value=False)
        self.filter_hd.trace_add("write", lambda *_: self.apply_filter())
        ttk.Checkbutton(filter_row1, text="只顯示高清", variable=self.filter_hd).pack(side=tk.LEFT, padx=(0, 12))

        # 最小檔案大小
        ttk.Label(filter_row1, text="最小大小 (GB):").pack(side=tk.LEFT)
        self.filter_min_size = tk.StringVar(value="0")
        self.filter_min_size.trace_add("write", lambda *_: self.apply_filter())
        min_size_entry = ttk.Entry(filter_row1, textvariable=self.filter_min_size, width=6)
        min_size_entry.pack(side=tk.LEFT, padx=(4, 12))

        # 最大檔案大小
        ttk.Label(filter_row1, text="最大大小 (GB):").pack(side=tk.LEFT)
        self.filter_max_size = tk.StringVar(value="")
        self.filter_max_size.trace_add("write", lambda *_: self.apply_filter())
        max_size_entry = ttk.Entry(filter_row1, textvariable=self.filter_max_size, width=6)
        max_size_entry.pack(side=tk.LEFT, padx=(4, 12))

        # 重置篩選
        ttk.Button(filter_row1, text="重置", command=self.reset_filter).pack(side=tk.RIGHT)

        # 第二列：群組篩選
        filter_row2 = ttk.Frame(filter_frame)
        filter_row2.pack(fill=tk.X, pady=(6, 0))

        ttk.Label(filter_row2, text="每組只留:").pack(side=tk.LEFT)
        self.filter_pick = tk.StringVar(value="全部顯示")
        self.filter_pick.trace_add("write", lambda *_: self.apply_filter())
        pick_combo = ttk.Combobox(filter_row2, textvariable=self.filter_pick, state="readonly", width=18,
                                  values=["全部顯示", "檔案最大的", "檔案最小的", "檔案數量最少的"])
        pick_combo.pack(side=tk.LEFT, padx=(4, 0))

        # --- 下方：結果區 ---
        result_frame = ttk.LabelFrame(root, text="擷取結果", padding=8)
        result_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        columns = ("番號", "大小", "標籤", "日期", "磁力連結")
        self.tree = ttk.Treeview(result_frame, columns=columns, show="tree headings", selectmode="extended")
        self.tree.heading("#0", text="影片", anchor=tk.W, command=lambda: self.sort_column("#0"))
        self.tree.column("#0", width=220, minwidth=150)
        for col in columns:
            self.tree.heading(col, text=col, command=lambda c=col: self.sort_column(c))
        self.tree.column("番號", width=90, minwidth=70)
        self.tree.column("大小", width=100, minwidth=70)
        self.tree.column("標籤", width=60, minwidth=40)
        self.tree.column("日期", width=90, minwidth=70)
        self.tree.column("磁力連結", width=300, minwidth=200)
        self.sort_reverse: dict[str, bool] = {}

        scrollbar = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<Double-1>", self.on_double_click)

        # 原始資料儲存（篩選用）
        self.raw_results: list[dict] = []

    def start_scrape(self):
        raw = self.url_text.get("1.0", tk.END).strip()
        if not raw:
            messagebox.showwarning("提示", "請輸入至少一個網址")
            return

        urls = [line.strip() for line in raw.splitlines() if line.strip()]
        if not urls:
            return

        self.btn_start.config(state=tk.DISABLED)
        self.status_var.set(f"擷取中... 0/{len(urls)}")
        threading.Thread(target=self.scrape_worker, args=(urls,), daemon=True).start()

    def scrape_worker(self, urls: list[str]):
        cookies = load_cookies()
        session, engine = create_session()

        for i, url in enumerate(urls):
            # 第二個請求開始加隨機延遲（3~6 秒），避免觸發 429
            if i > 0:
                delay = 3.0 + (randbelow(3000) / 1000.0)
                self.root.after(0, self.status_var.set, f"等待 {delay:.1f}s... {i + 1}/{len(urls)}  ({engine})")
                time.sleep(delay)

            self.root.after(0, self.status_var.set, f"擷取中... {i + 1}/{len(urls)}  ({engine})")
            try:
                result = fetch_magnets(url, session, cookies)
                # 遇到 429 自動等待重試
                if result.get("error", "").endswith("429"):
                    retry_delay = 10.0 + (randbelow(5000) / 1000.0)
                    self.root.after(0, self.status_var.set, f"被限流，等待 {retry_delay:.0f}s 後重試... {i + 1}/{len(urls)}")
                    time.sleep(retry_delay)
                    result = fetch_magnets(url, session, cookies)
            except Exception as e:
                result = {"url": url, "code": "", "title": "", "magnets": [], "error": str(e)}
            self.root.after(0, self.store_result, result)

        self.root.after(0, self.on_scrape_done, len(urls))

    def store_result(self, result: dict):
        self.raw_results.append(result)
        self.apply_filter()

    def on_scrape_done(self, count: int):
        self.btn_start.config(state=tk.NORMAL)
        total = sum(len(r["magnets"]) for r in self.raw_results)
        visible = self._count_visible_magnets()
        self.status_var.set(f"完成！{count} 個網址，共 {total} 個磁力連結（顯示 {visible} 個）")

    def apply_filter(self):
        keyword = self.filter_keyword.get().strip().lower()
        hd_only = self.filter_hd.get()
        pick_mode = self.filter_pick.get()

        try:
            min_size = float(self.filter_min_size.get()) if self.filter_min_size.get().strip() else 0.0
        except ValueError:
            min_size = 0.0
        try:
            max_size = float(self.filter_max_size.get()) if self.filter_max_size.get().strip() else 0.0
        except ValueError:
            max_size = 0.0

        self.tree.delete(*self.tree.get_children(""))

        for result in self.raw_results:
            code = result.get("code", "")
            title = result.get("title", "")
            error = result.get("error", "")
            magnets = result.get("magnets", [])

            display = f"{code}  {title}" if code else result.get("url", "")
            if error:
                display = f"[錯誤] {result.get('url', '')} - {error}"

            filtered = []
            for m in magnets:
                if hd_only and "高清" not in m["tags"]:
                    continue

                size_gb = parse_size_gb(m["size"])
                if min_size > 0 and size_gb < min_size:
                    continue
                if max_size > 0 and size_gb > max_size:
                    continue

                if keyword:
                    searchable = f"{m['name']} {m['size']} {' '.join(m['tags'])} {m['date']}".lower()
                    if keyword not in searchable and keyword not in display.lower():
                        continue

                filtered.append(m)

            # 群組篩選：每組只留一個
            if filtered and pick_mode != "全部顯示":
                if pick_mode == "檔案最大的":
                    filtered = [max(filtered, key=lambda m: parse_size_gb(m["size"]))]
                elif pick_mode == "檔案最小的":
                    filtered = [min(filtered, key=lambda m: parse_size_gb(m["size"]))]
                elif pick_mode == "檔案數量最少的":
                    filtered = [min(filtered, key=lambda m: parse_file_count(m["size"]))]

            if not filtered and not error:
                if keyword and keyword not in display.lower():
                    continue
                if magnets and (hd_only or min_size > 0 or max_size > 0):
                    continue

            parent = self.tree.insert("", tk.END, text=display, open=True)

            if not filtered and not error:
                self.tree.insert(parent, tk.END, values=("", "", "", "", "無符合條件的磁力連結"))
            elif error:
                pass
            else:
                for m in filtered:
                    tag_str = ", ".join(m["tags"]) if m["tags"] else ""
                    self.tree.insert(parent, tk.END, values=(m["name"], m["size"], tag_str, m["date"], m["magnet"]))

        visible = self._count_visible_magnets()
        total = sum(len(r["magnets"]) for r in self.raw_results)
        if total > 0:
            self.status_var.set(f"共 {total} 個磁力連結（顯示 {visible} 個）")

    def _count_visible_magnets(self) -> int:
        count = 0
        for parent_id in self.tree.get_children(""):
            for child_id in self.tree.get_children(parent_id):
                vals = self.tree.item(child_id, "values")
                if vals and vals[4] and vals[4].startswith("magnet:"):
                    count += 1
        return count

    def reset_filter(self):
        self.filter_keyword.set("")
        self.filter_hd.set(False)
        self.filter_min_size.set("0")
        self.filter_max_size.set("")
        self.filter_pick.set("全部顯示")

    def copy_all_magnets(self):
        magnets = []
        for parent_id in self.tree.get_children(""):
            for child_id in self.tree.get_children(parent_id):
                vals = self.tree.item(child_id, "values")
                if vals and vals[4] and vals[4].startswith("magnet:"):
                    magnets.append(vals[4])
        if not magnets:
            messagebox.showinfo("提示", "沒有磁力連結可複製")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append("\n".join(magnets))
        self.status_var.set(f"已複製 {len(magnets)} 個磁力連結到剪貼簿")

    def on_double_click(self, event):
        item = self.tree.focus()
        if not item:
            return
        values = self.tree.item(item, "values")
        if values and values[4] and values[4].startswith("magnet:"):
            self.root.clipboard_clear()
            self.root.clipboard_append(values[4])
            self.status_var.set(f"已複製: {values[0]} 的磁力連結")

    def sort_column(self, col: str):
        reverse = self.sort_reverse.get(col, False)

        top_items = []
        for parent_id in self.tree.get_children(""):
            children = []
            for child_id in self.tree.get_children(parent_id):
                children.append((self.tree.item(child_id, "values"),))
            parent_text = self.tree.item(parent_id, "text")
            parent_open = self.tree.item(parent_id, "open")

            if col == "#0":
                sort_key = parent_text.lower()
            elif col == "大小":
                col_vals = [self.tree.set(c, col) for c in self.tree.get_children(parent_id)]
                sort_key = parse_size_gb(col_vals[0]) if col_vals else 0.0
            else:
                col_vals = [self.tree.set(c, col) for c in self.tree.get_children(parent_id)]
                sort_key = col_vals[0].lower() if col_vals else ""
            top_items.append((sort_key, parent_text, parent_open, children))

        top_items.sort(key=lambda x: x[0], reverse=reverse)

        self.tree.delete(*self.tree.get_children(""))
        for _, parent_text, parent_open, children in top_items:
            pid = self.tree.insert("", tk.END, text=parent_text, open=parent_open)
            for (vals,) in children:
                self.tree.insert(pid, tk.END, values=vals)

        self.sort_reverse[col] = not reverse
        arrow = " ▼" if reverse else " ▲"
        display = "影片" if col == "#0" else col
        if col == "#0":
            self.tree.heading(col, text=display + arrow, command=lambda: self.sort_column(col))
        else:
            self.tree.heading(col, text=display + arrow, command=lambda c=col: self.sort_column(c))

    def clear_results(self):
        self.tree.delete(*self.tree.get_children())
        self.raw_results.clear()
        self.status_var.set("已清空")

    def open_log(self):
        """在系統預設編輯器開啟 log 檔"""
        import os
        log_file = get_log_file()
        try:
            if log_file is None or not log_file.exists():
                messagebox.showinfo("日誌", "尚未產生日誌檔")
                return
            os.startfile(str(log_file))  # nosec B606 — intentional: open user's log with system default app
        except Exception as e:
            logger.exception("無法開啟 log 檔")
            messagebox.showerror("日誌", f"無法開啟: {e}\n\n路徑: {log_file}")

    def open_settings(self):
        SettingsDialog(self.root)

    def toggle_theme(self):
        try:
            import sv_ttk
            current = sv_ttk.get_theme()
            new_theme = "dark" if current == "light" else "light"
            sv_ttk.set_theme(new_theme)
            self.btn_theme.config(text="☀️" if new_theme == "dark" else "🌙")
            logger.info(f"切換主題為: {new_theme}")
        except ImportError:
            messagebox.showinfo("主題", "sv-ttk 未安裝")

    def send_to_realdebrid(self):
        env = load_env(ENV_FILE)
        token = env.get("RD_API_TOKEN", "").strip()
        if not token:
            messagebox.showerror("Real-Debrid",
                                 "RD_API_TOKEN 未設定。\n\n請編輯 .env 檔案並貼上 token：\n"
                                 "https://real-debrid.com/apitoken")
            return

        # 收集目前可見的磁力連結（從擷取結果）
        scraped_magnets = []
        for parent_id in self.tree.get_children(""):
            for child_id in self.tree.get_children(parent_id):
                vals = self.tree.item(child_id, "values")
                if vals and vals[4] and vals[4].startswith("magnet:"):
                    scraped_magnets.append({"code": vals[0], "size": vals[1], "magnet": vals[4]})

        strategy = env.get("RD_FILE_PICK", "smart")
        try:
            cache_wait = int(env.get("RD_CACHE_WAIT", "15"))
        except ValueError:
            cache_wait = 15
        try:
            min_size_mb = int(env.get("RD_MIN_SIZE_MB", "500"))
        except ValueError:
            min_size_mb = 500

        RDInputDialog(self.root, token, scraped_magnets, strategy, cache_wait, min_size_mb)

    def open_retry(self):
        env = load_env(ENV_FILE)
        token = env.get("RD_API_TOKEN", "").strip()
        if not token:
            messagebox.showerror("Real-Debrid", "RD_API_TOKEN 未設定，請編輯 .env 檔案")
            return
        try:
            min_size_mb = int(env.get("RD_MIN_SIZE_MB", "500"))
        except ValueError:
            min_size_mb = 500
        RetryDialog(self.root, token, min_size_mb)


class RDInputDialog(tk.Toplevel):
    """選擇要送出的磁力連結 - 可使用擷取結果或自行貼上"""

    def __init__(self, parent, token, scraped_magnets, strategy, cache_wait, min_size_mb=500):
        super().__init__(parent)
        self.title("送出磁力連結到 Real-Debrid")
        self.geometry("760x600")
        self.minsize(600, 450)
        self.transient(parent)
        self.grab_set()

        self.token = token
        self.scraped_magnets = scraped_magnets
        self.strategy = strategy
        self.cache_wait = cache_wait
        self.min_size_mb = min_size_mb

        # 來源選擇（最上）
        source_frame = ttk.LabelFrame(self, text="磁力來源", padding=10)
        source_frame.pack(fill=tk.X, padx=10, pady=(10, 5), side=tk.TOP)

        self.source = tk.StringVar(value="scraped" if scraped_magnets else "manual")
        ttk.Radiobutton(
            source_frame,
            text=f"使用擷取結果（{len(scraped_magnets)} 個）",
            variable=self.source,
            value="scraped",
            state=(tk.NORMAL if scraped_magnets else tk.DISABLED),
            command=self.on_source_change,
        ).pack(side=tk.LEFT)
        ttk.Radiobutton(
            source_frame,
            text="自行貼上磁力連結",
            variable=self.source,
            value="manual",
            command=self.on_source_change,
        ).pack(side=tk.LEFT, padx=(20, 0))

        # 按鈕列（最下，先 pack 確保空間保留）
        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)

        ttk.Button(btn_frame, text="送出", command=self.submit).pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="取消", command=self.destroy).pack(side=tk.RIGHT, padx=(0, 8))

        # 選項列（在按鈕上方）
        options_frame = ttk.Frame(self, padding=(10, 5))
        options_frame.pack(fill=tk.X, side=tk.BOTTOM)

        ttk.Label(options_frame, text="檔案選擇策略:").pack(side=tk.LEFT)
        self.strategy_var = tk.StringVar(value=strategy)
        strategy_combo = ttk.Combobox(
            options_frame, textvariable=self.strategy_var, state="readonly", width=12,
            values=["smart", "largest", "video", "all"],
        )
        strategy_combo.pack(side=tk.LEFT, padx=(4, 12))

        ttk.Label(options_frame, text=f"smart 門檻: {min_size_mb}MB").pack(side=tk.LEFT)

        # 文字區（填滿剩餘空間）
        text_frame = ttk.LabelFrame(self, text="磁力連結（每行一個 magnet:?xt=... 連結）", padding=8)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))

        self.text = tk.Text(text_frame, font=("Consolas", 9), wrap=tk.NONE)
        text_scroll_y = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.text.yview)
        text_scroll_x = ttk.Scrollbar(text_frame, orient=tk.HORIZONTAL, command=self.text.xview)
        self.text.configure(yscrollcommand=text_scroll_y.set, xscrollcommand=text_scroll_x.set)

        text_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        text_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.text.pack(fill=tk.BOTH, expand=True)

        self.on_source_change()

    def on_source_change(self):
        self.text.delete("1.0", tk.END)
        if self.source.get() == "scraped":
            for m in self.scraped_magnets:
                self.text.insert(tk.END, m["magnet"] + "\n")
            self.text.config(state=tk.NORMAL)  # 仍可編輯，方便刪除不需要的

    def submit(self):
        raw = self.text.get("1.0", tk.END).strip()
        if not raw:
            messagebox.showwarning("提示", "請至少貼上一個磁力連結", parent=self)
            return

        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        magnets = []
        invalid = 0
        for line in lines:
            if not line.startswith("magnet:"):
                invalid += 1
                continue
            # 嘗試從擷取結果找到對應的 code/size
            matched = next((m for m in self.scraped_magnets if m["magnet"] == line), None)
            if matched:
                magnets.append(matched)
            else:
                # 從 dn= 參數抓名稱當 code
                m = re.search(r"dn=([^&]+)", line)
                code = m.group(1) if m else line[:40] + "..."
                magnets.append({"code": code, "size": "", "magnet": line})

        if not magnets:
            messagebox.showerror("錯誤", "沒有有效的磁力連結（必須以 magnet: 開頭）", parent=self)
            return

        if invalid:
            if not messagebox.askyesno("確認", f"忽略 {invalid} 個無效連結，送出 {len(magnets)} 個有效連結？", parent=self):
                return

        self.destroy()
        RDDialog(self.master, self.token, magnets, self.strategy_var.get(), self.cache_wait, self.min_size_mb)


class RDDialog(tk.Toplevel):
    def __init__(self, parent, token: str, magnets: list[dict], strategy: str, cache_wait: int, min_size_mb: int = 500):
        super().__init__(parent)
        self.title("Real-Debrid 處理進度")
        self.geometry("900x600")
        self.transient(parent)

        self.token = token
        self.magnets = magnets
        self.strategy = strategy
        self.cache_wait = cache_wait
        self.min_size_mb = min_size_mb
        self.results: list[dict] = []
        self.pending_count = 0
        self.cancelled = False

        # 進度標籤
        self.progress_var = tk.StringVar(value=f"準備處理 {len(magnets)} 個磁力連結...")
        ttk.Label(self, textvariable=self.progress_var, padding=10).pack(fill=tk.X)

        # 結果樹
        result_frame = ttk.Frame(self, padding=(10, 0))
        result_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("檔名", "大小", "狀態", "下載連結")
        self.tree = ttk.Treeview(result_frame, columns=columns, show="tree headings", selectmode="extended")
        self.tree.heading("#0", text="番號")
        self.tree.column("#0", width=140, minwidth=100)
        self.tree.heading("檔名", text="檔名")
        self.tree.column("檔名", width=240, minwidth=150)
        self.tree.heading("大小", text="大小")
        self.tree.column("大小", width=80, minwidth=60)
        self.tree.heading("狀態", text="狀態")
        self.tree.column("狀態", width=120, minwidth=80)
        self.tree.heading("下載連結", text="下載連結")
        self.tree.column("下載連結", width=300, minwidth=200)

        scrollbar = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<Double-1>", self.on_double_click)

        # 按鈕
        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.pack(fill=tk.X)

        self.btn_copy = ttk.Button(btn_frame, text="複製全部下載連結", command=self.copy_all, state=tk.DISABLED)
        self.btn_copy.pack(side=tk.LEFT)

        ttk.Button(btn_frame, text="關閉", command=self.on_close).pack(side=tk.RIGHT)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # 開始處理
        threading.Thread(target=self.worker, daemon=True).start()

    def worker(self):
        logger.info(f"開始批次處理 {len(self.magnets)} 個磁力，策略={self.strategy}, 等待={self.cache_wait}s, 門檻={self.min_size_mb}MB")
        try:
            rd = RealDebrid(self.token, min_size_mb=self.min_size_mb)
        except RealDebridError as e:
            err = str(e)
            logger.error(f"RD 初始化失敗: {err}")
            self.after(0, lambda: messagebox.showerror("Real-Debrid", err, parent=self))
            return

        for i, item in enumerate(self.magnets):
            if self.cancelled:
                logger.info("使用者取消處理")
                break

            # 第二個磁力開始加 1 秒間隔，避免短時間內塞太多 API 呼叫觸發 429
            if i > 0:
                time.sleep(1.0)

            code = item["code"]
            magnet = item["magnet"]
            logger.info(f"--- [{i + 1}/{len(self.magnets)}] {code} ---")

            self.after(0, self.progress_var.set, f"[{i + 1}/{len(self.magnets)}] {code} - 處理中...")
            parent_id = None

            def add_status(text: str):
                nonlocal parent_id
                if parent_id is None:
                    parent_id = self.tree.insert("", tk.END, text=code, values=("", item["size"], text, ""), open=True)
                else:
                    self.tree.set(parent_id, "狀態", text)

            self.after(0, add_status, "開始")

            try:
                result = rd.process_magnet(
                    magnet,
                    strategy=self.strategy,
                    cache_wait=self.cache_wait,
                    progress=lambda msg: self.after(0, lambda m=msg: add_status(m) if parent_id else None),
                )
                if result.get("status") == "completed":
                    self.after(0, self.add_success, code, item["size"], result)
                else:  # pending
                    add_pending({
                        "torrent_id": result["torrent_id"],
                        "code": code,
                        "magnet": magnet,
                        "size": item["size"],
                        "name": result.get("name", ""),
                        "added_at": datetime.now().isoformat(timespec="seconds"),
                        "progress": result.get("progress", 0),
                        "rd_status": result.get("rd_status", ""),
                        "files_selected": result.get("files_selected", False),
                        "strategy": self.strategy,
                    })
                    self.pending_count += 1
                    self.after(0, self.add_pending_row, code, item["size"], result)
            except RealDebridError as e:
                logger.error(f"[{code}] RD 處理失敗: {e}")
                self.after(0, self.add_error, code, item["size"], str(e))
            except Exception as e:
                logger.exception(f"[{code}] 未預期錯誤")
                self.after(0, self.add_error, code, item["size"], f"未預期錯誤: {e}")

        logger.info(f"批次完成：{len(self.results)} 個成功 / {self.pending_count} 個待處理 / {len(self.magnets)} 個磁力")
        self.after(0, self.on_done)

    def add_success(self, code: str, size: str, result: dict):
        # 移除暫時的「處理中」項目（如果有）
        for child in self.tree.get_children(""):
            if self.tree.item(child, "text") == code and not self.tree.get_children(child):
                self.tree.delete(child)
                break

        parent = self.tree.insert("", tk.END, text=code, values=("", size, "完成", ""), open=True)
        for link in result["links"]:
            if "error" in link:
                self.tree.insert(parent, tk.END, values=(link.get("filename", ""), "", f"錯誤: {link['error']}", ""))
            else:
                size_gb = link["filesize"] / 1024**3 if link["filesize"] else 0
                size_str = f"{size_gb:.2f}GB" if size_gb > 0 else ""
                self.tree.insert(parent, tk.END, values=(link["filename"], size_str, "OK", link["download"]))
                self.results.append(link)

    def add_error(self, code: str, size: str, error: str):
        for child in self.tree.get_children(""):
            if self.tree.item(child, "text") == code and not self.tree.get_children(child):
                self.tree.delete(child)
                break
        self.tree.insert("", tk.END, text=code, values=("", size, f"失敗: {error}", ""))

    def add_pending_row(self, code: str, size: str, result: dict):
        for child in self.tree.get_children(""):
            if self.tree.item(child, "text") == code and not self.tree.get_children(child):
                self.tree.delete(child)
                break
        progress = result.get("progress", 0)
        rd_status = result.get("rd_status", "")
        msg = f"待處理（{rd_status} {progress}%）"
        self.tree.insert("", tk.END, text=code, values=("", size, msg, ""))

    def on_done(self):
        success = len(self.results)
        total = len(self.magnets)
        msg = f"完成！{success} 個下載連結 / {self.pending_count} 個待處理 / 共 {total} 個磁力"
        self.progress_var.set(msg)
        if self.results:
            self.btn_copy.config(state=tk.NORMAL)
        if self.pending_count:
            messagebox.showinfo(
                "待處理提示",
                f"有 {self.pending_count} 個磁力 RD 還在下載中。\n"
                "稍後可按主視窗「重試待處理」按鈕查看進度並取得連結。",
                parent=self,
            )

    def copy_all(self):
        links = [r["download"] for r in self.results if r.get("download")]
        if not links:
            return
        self.clipboard_clear()
        self.clipboard_append("\n".join(links))
        self.progress_var.set(f"已複製 {len(links)} 個下載連結到剪貼簿")

    def on_double_click(self, event):
        item = self.tree.focus()
        if not item:
            return
        values = self.tree.item(item, "values")
        if values and len(values) >= 4 and values[3].startswith("http"):
            self.clipboard_clear()
            self.clipboard_append(values[3])
            self.progress_var.set(f"已複製: {values[0]}")

    def on_close(self):
        self.cancelled = True
        self.destroy()


RD_TOKEN_URL = "https://real-debrid.com/apitoken"


def write_env(values: dict):
    """寫入 .env 檔，保留註解結構"""
    template = (
        "# Real-Debrid API Token\n"
        "# 取得方式：登入後到 https://real-debrid.com/apitoken 複製 token\n"
        "RD_API_TOKEN={RD_API_TOKEN}\n"
        "\n"
        "# 自動選擇檔案的策略\n"
        "# smart   = 番號比對 + size 門檻雙重過濾（推薦）\n"
        "# largest = 只選最大的影片檔（一片一檔時用）\n"
        "# video   = 所有影片副檔名（不過濾廣告短片）\n"
        "# all     = 全部選取\n"
        "RD_FILE_PICK={RD_FILE_PICK}\n"
        "\n"
        "# smart 策略的最小檔案大小門檻（MB）\n"
        "RD_MIN_SIZE_MB={RD_MIN_SIZE_MB}\n"
        "\n"
        "# 等待 torrent 處理的最長秒數\n"
        "RD_WAIT_TIMEOUT={RD_WAIT_TIMEOUT}\n"
        "\n"
        "# 等待快取判定的秒數，超過視為未快取進入待處理清單\n"
        "RD_CACHE_WAIT={RD_CACHE_WAIT}\n"
        "\n"
        "# UI 縮放：auto = 依系統 DPI；或指定倍率如 1.5、2.0\n"
        "UI_SCALE={UI_SCALE}\n"
        "\n"
        "# UI 主題：light 或 dark\n"
        "UI_THEME={UI_THEME}\n"
    )
    content = template.format(**values)
    ENV_FILE.write_text(content, encoding="utf-8")


class SettingsDialog(tk.Toplevel):
    """設定畫面：編輯 .env，包含 RD token 與其他選項"""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("設定")
        self.geometry("680x520")
        self.minsize(560, 460)
        self.transient(parent)
        self.grab_set()

        env = load_env(ENV_FILE)

        # 按鈕列（最下，先 pack）
        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)

        ttk.Button(btn_frame, text="儲存", command=self.save).pack(side=tk.RIGHT)
        ttk.Button(btn_frame, text="取消", command=self.destroy).pack(side=tk.RIGHT, padx=(0, 8))
        ttk.Button(btn_frame, text="測試連線", command=self.test_connection).pack(side=tk.LEFT)

        # 主內容
        main = ttk.Frame(self, padding=15)
        main.pack(fill=tk.BOTH, expand=True)

        # === Real-Debrid ===
        rd_frame = ttk.LabelFrame(main, text="Real-Debrid", padding=12)
        rd_frame.pack(fill=tk.X, pady=(0, 10))

        # Token 列
        token_row = ttk.Frame(rd_frame)
        token_row.pack(fill=tk.X)
        ttk.Label(token_row, text="API Token:", width=14, anchor=tk.W).pack(side=tk.LEFT)
        self.token_var = tk.StringVar(value=env.get("RD_API_TOKEN", ""))
        self.token_entry = ttk.Entry(token_row, textvariable=self.token_var, show="*")
        self.token_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.show_token_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(token_row, text="顯示", variable=self.show_token_var,
                        command=self.toggle_token_visibility).pack(side=tk.LEFT, padx=(8, 0))

        # 取得 token 連結
        link_row = ttk.Frame(rd_frame)
        link_row.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(link_row, text="").pack(side=tk.LEFT, padx=(0, 80))
        link = ttk.Label(
            link_row, text="🔗 點此取得 / 重設 Token（在瀏覽器開啟）",
            foreground="blue", cursor="hand2",
        )
        link.pack(side=tk.LEFT)
        link.bind("<Button-1>", lambda e: webbrowser.open(RD_TOKEN_URL))

        ttk.Label(rd_frame, text=f"({RD_TOKEN_URL})",
                  foreground="gray", font=("TkDefaultFont", 8)).pack(anchor=tk.W, padx=(94, 0))

        # === 檔案選擇策略 ===
        pick_frame = ttk.LabelFrame(main, text="檔案選擇策略", padding=12)
        pick_frame.pack(fill=tk.X, pady=(0, 10))

        strategy_row = ttk.Frame(pick_frame)
        strategy_row.pack(fill=tk.X)
        ttk.Label(strategy_row, text="策略:", width=14, anchor=tk.W).pack(side=tk.LEFT)
        self.strategy_var = tk.StringVar(value=env.get("RD_FILE_PICK", "smart"))
        strategy_combo = ttk.Combobox(
            strategy_row, textvariable=self.strategy_var, state="readonly", width=12,
            values=["smart", "largest", "video", "all"],
        )
        strategy_combo.pack(side=tk.LEFT)
        strategy_combo.bind("<<ComboboxSelected>>", lambda e: self.update_strategy_help())

        self.strategy_help = ttk.Label(pick_frame, text="", foreground="gray",
                                       font=("TkDefaultFont", 8), wraplength=600, justify=tk.LEFT)
        self.strategy_help.pack(fill=tk.X, pady=(6, 0))

        # 門檻
        size_row = ttk.Frame(pick_frame)
        size_row.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(size_row, text="最小檔案 (MB):", width=14, anchor=tk.W).pack(side=tk.LEFT)
        self.min_size_var = tk.StringVar(value=env.get("RD_MIN_SIZE_MB", "500"))
        ttk.Entry(size_row, textvariable=self.min_size_var, width=10).pack(side=tk.LEFT)
        ttk.Label(size_row, text="（smart 策略用，低於此值的檔案會被視為廣告跳過）",
                  foreground="gray", font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=(8, 0))

        # === 介面 ===
        ui_frame = ttk.LabelFrame(main, text="介面", padding=12)
        ui_frame.pack(fill=tk.X, pady=(0, 10))

        scale_row = ttk.Frame(ui_frame)
        scale_row.pack(fill=tk.X)
        ttk.Label(scale_row, text="UI 縮放:", width=14, anchor=tk.W).pack(side=tk.LEFT)
        self.ui_scale_var = tk.StringVar(value=env.get("UI_SCALE", "auto"))
        ui_scale_combo = ttk.Combobox(
            scale_row, textvariable=self.ui_scale_var, width=10,
            values=["auto", "1.0", "1.25", "1.5", "1.75", "2.0", "2.5", "3.0"],
        )
        ui_scale_combo.pack(side=tk.LEFT)
        ttk.Label(scale_row, text="（4K 螢幕建議 1.5-2.0；修改後重新啟動程式生效）",
                  foreground="gray", font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=(8, 0))

        theme_row = ttk.Frame(ui_frame)
        theme_row.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(theme_row, text="主題:", width=14, anchor=tk.W).pack(side=tk.LEFT)
        self.ui_theme_var = tk.StringVar(value=env.get("UI_THEME", "light"))
        ttk.Combobox(theme_row, textvariable=self.ui_theme_var, state="readonly", width=10,
                     values=["light", "dark"]).pack(side=tk.LEFT)
        ttk.Label(theme_row, text="（修改後重新啟動程式生效）",
                  foreground="gray", font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=(8, 0))

        # === 處理時間設定 ===
        time_frame = ttk.LabelFrame(main, text="處理時間", padding=12)
        time_frame.pack(fill=tk.X, pady=(0, 10))

        cache_row = ttk.Frame(time_frame)
        cache_row.pack(fill=tk.X)
        ttk.Label(cache_row, text="快取等待 (秒):", width=14, anchor=tk.W).pack(side=tk.LEFT)
        self.cache_wait_var = tk.StringVar(value=env.get("RD_CACHE_WAIT", "15"))
        ttk.Entry(cache_row, textvariable=self.cache_wait_var, width=10).pack(side=tk.LEFT)
        ttk.Label(cache_row, text="（超過此時間還在下載 → 進入待處理清單）",
                  foreground="gray", font=("TkDefaultFont", 8)).pack(side=tk.LEFT, padx=(8, 0))

        wait_row = ttk.Frame(time_frame)
        wait_row.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(wait_row, text="超時時間 (秒):", width=14, anchor=tk.W).pack(side=tk.LEFT)
        self.wait_timeout_var = tk.StringVar(value=env.get("RD_WAIT_TIMEOUT", "300"))
        ttk.Entry(wait_row, textvariable=self.wait_timeout_var, width=10).pack(side=tk.LEFT)

        self.update_strategy_help()

    def toggle_token_visibility(self):
        self.token_entry.config(show="" if self.show_token_var.get() else "*")

    def update_strategy_help(self):
        helps = {
            "smart": "推薦：先用磁力番號（如 SNOS-192）比對檔名選擇，找不到番號則退回最小大小門檻。會自動跳過廣告 mp4 與 .url 檔案。",
            "largest": "只選最大的影片檔。適合一片一檔但無法處理多段切割的影片。",
            "video": "選所有影片副檔名的檔案，不過濾大小。可能會把廣告短片也選進來。",
            "all": "下載 torrent 內所有檔案（包含 .url、廣告 mp4、txt 等）。",
        }
        self.strategy_help.config(text=helps.get(self.strategy_var.get(), ""))

    def _validate(self) -> dict | None:
        token = self.token_var.get().strip()
        if not token:
            messagebox.showerror("錯誤", "請輸入 API Token", parent=self)
            return None
        try:
            min_size = int(self.min_size_var.get())
            if min_size < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("錯誤", "最小檔案大小必須是非負整數", parent=self)
            return None
        try:
            cache_wait = int(self.cache_wait_var.get())
            if cache_wait < 5:
                raise ValueError
        except ValueError:
            messagebox.showerror("錯誤", "快取等待秒數必須是 ≥ 5 的整數", parent=self)
            return None
        try:
            wait_timeout = int(self.wait_timeout_var.get())
            if wait_timeout < 30:
                raise ValueError
        except ValueError:
            messagebox.showerror("錯誤", "超時時間必須是 ≥ 30 的整數", parent=self)
            return None
        ui_scale = self.ui_scale_var.get().strip().lower() or "auto"
        if ui_scale != "auto":
            try:
                v = float(ui_scale)
                if not 0.5 <= v <= 5.0:
                    raise ValueError
                ui_scale = str(v)
            except ValueError:
                messagebox.showerror("錯誤", "UI 縮放必須是 auto 或 0.5~5.0 之間的數字", parent=self)
                return None

        return {
            "RD_API_TOKEN": token,
            "RD_FILE_PICK": self.strategy_var.get(),
            "RD_MIN_SIZE_MB": str(min_size),
            "RD_CACHE_WAIT": str(cache_wait),
            "RD_WAIT_TIMEOUT": str(wait_timeout),
            "UI_SCALE": ui_scale,
            "UI_THEME": self.ui_theme_var.get().strip() or "light",
        }

    def test_connection(self):
        values = self._validate()
        if not values:
            return

        def worker():
            try:
                rd = RealDebrid(values["RD_API_TOKEN"])
                user = rd._request("GET", "/user")
                username = user.get("username", "(未知)")
                user_type = user.get("type", "")
                expiration = user.get("expiration", "")
                points = user.get("points", "")
                msg = (
                    f"✅ 連線成功！\n\n"
                    f"帳號: {username}\n"
                    f"類型: {user_type}\n"
                    f"到期: {expiration}\n"
                    f"點數: {points}"
                )
                self.after(0, lambda: messagebox.showinfo("測試連線", msg, parent=self))
            except RealDebridError as e:
                err = str(e)
                self.after(0, lambda: messagebox.showerror("測試連線失敗", err, parent=self))
            except Exception as e:
                logger.exception("測試連線異常")
                err = f"未預期錯誤: {e}"
                self.after(0, lambda: messagebox.showerror("測試連線失敗", err, parent=self))

        threading.Thread(target=worker, daemon=True).start()

    def save(self):
        values = self._validate()
        if not values:
            return
        try:
            write_env(values)
            logger.info(f"設定已儲存到 {ENV_FILE}")
            messagebox.showinfo("儲存", "設定已儲存", parent=self)
            self.destroy()
        except Exception as e:
            logger.exception("儲存設定失敗")
            messagebox.showerror("儲存失敗", str(e), parent=self)


class RetryDialog(tk.Toplevel):
    """檢查待處理 torrents 的目前狀態，已完成的取得連結並從清單移除"""

    def __init__(self, parent, token: str, min_size_mb: int = 500):
        super().__init__(parent)
        self.title("重試待處理 torrents")
        self.geometry("960x600")
        self.minsize(700, 450)
        self.transient(parent)

        self.token = token
        self.min_size_mb = min_size_mb
        self.completed_links: list[dict] = []
        self.cancelled = False

        # 進度標籤
        self.progress_var = tk.StringVar(value="準備中...")
        ttk.Label(self, textvariable=self.progress_var, padding=10).pack(fill=tk.X)

        # 按鈕列（固定在底部）
        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.btn_retry_all = ttk.Button(btn_frame, text="重新檢查全部", command=self.start_check)
        self.btn_retry_all.pack(side=tk.LEFT)

        self.btn_remove_selected = ttk.Button(btn_frame, text="移除選取項目", command=self.remove_selected)
        self.btn_remove_selected.pack(side=tk.LEFT, padx=(8, 0))

        self.btn_copy = ttk.Button(btn_frame, text="複製本次完成連結", command=self.copy_completed, state=tk.DISABLED)
        self.btn_copy.pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(btn_frame, text="關閉", command=self.on_close).pack(side=tk.RIGHT)

        # 結果樹
        result_frame = ttk.Frame(self, padding=(10, 0, 10, 5))
        result_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("torrent_id", "大小", "RD 狀態", "進度", "下載連結")
        self.tree = ttk.Treeview(result_frame, columns=columns, show="tree headings", selectmode="extended")
        self.tree.heading("#0", text="番號")
        self.tree.column("#0", width=140, minwidth=100)
        self.tree.heading("torrent_id", text="Torrent ID")
        self.tree.column("torrent_id", width=140, minwidth=100)
        self.tree.heading("大小", text="原始大小")
        self.tree.column("大小", width=80, minwidth=60)
        self.tree.heading("RD 狀態", text="RD 狀態")
        self.tree.column("RD 狀態", width=120, minwidth=80)
        self.tree.heading("進度", text="進度")
        self.tree.column("進度", width=70, minwidth=50)
        self.tree.heading("下載連結", text="下載連結")
        self.tree.column("下載連結", width=300, minwidth=200)

        scrollbar = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<Double-1>", self.on_double_click)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.refresh_list()
        # 自動開始檢查一次
        self.after(300, self.start_check)

    def refresh_list(self):
        """從 pending_torrents.json 載入清單到 treeview"""
        self.tree.delete(*self.tree.get_children())
        items = load_pending()
        if not items:
            self.progress_var.set("待處理清單是空的")
            return
        for item in items:
            self.tree.insert(
                "", tk.END,
                text=item.get("code", ""),
                values=(
                    item.get("torrent_id", ""),
                    item.get("size", ""),
                    "（待檢查）",
                    f"{item.get('progress', 0)}%",
                    "",
                ),
            )
        self.progress_var.set(f"待處理: {len(items)} 個")

    def start_check(self):
        items = load_pending()
        if not items:
            messagebox.showinfo("提示", "待處理清單是空的", parent=self)
            return
        self.btn_retry_all.config(state=tk.DISABLED)
        self.completed_links.clear()
        threading.Thread(target=self.check_worker, args=(items,), daemon=True).start()

    def check_worker(self, items: list[dict]):
        logger.info(f"開始重試 {len(items)} 個待處理 torrents")
        try:
            rd = RealDebrid(self.token, min_size_mb=self.min_size_mb)
        except RealDebridError as e:
            err = str(e)
            self.after(0, lambda: messagebox.showerror("Real-Debrid", err, parent=self))
            self.after(0, lambda: self.btn_retry_all.config(state=tk.NORMAL))
            return

        for i, item in enumerate(items):
            if self.cancelled:
                break
            torrent_id = item.get("torrent_id", "")
            code = item.get("code", "")
            self.after(0, self.progress_var.set, f"[{i + 1}/{len(items)}] 檢查 {code}...")

            strategy = item.get("strategy", "smart")
            magnet = item.get("magnet", "")
            try:
                result = rd.check_torrent(torrent_id, strategy=strategy, magnet=magnet)
            except RealDebridError as e:
                logger.warning(f"檢查 {code} 失敗: {e}")
                self.after(0, self.update_row, code, torrent_id, {"status": "error", "error": str(e)})
                continue

            self.after(0, self.update_row, code, torrent_id, result)

            if result["status"] == "completed":
                remove_pending(torrent_id)
                self.completed_links.extend(result.get("links", []))
            elif result["status"] == "missing":
                remove_pending(torrent_id)

        self.after(0, self.on_check_done)

    def update_row(self, code: str, torrent_id: str, result: dict):
        # 找到對應的 row
        target = None
        for child in self.tree.get_children():
            vals = self.tree.item(child, "values")
            if vals and vals[0] == torrent_id:
                target = child
                break

        if not target:
            return

        status = result.get("status", "")
        if status == "completed":
            links = result.get("links", [])
            self.tree.set(target, "RD 狀態", "✓ 完成")
            self.tree.set(target, "進度", "100%")
            self.tree.item(target, open=True)
            # 加入子項目顯示連結
            for link in links:
                if "error" in link:
                    self.tree.insert(target, tk.END, values=("", "", "", "", f"錯誤: {link['error']}"))
                else:
                    size_gb = link["filesize"] / 1024**3 if link["filesize"] else 0
                    size_str = f"{size_gb:.2f}GB" if size_gb > 0 else ""
                    self.tree.insert(
                        target, tk.END,
                        values=("", size_str, "OK", "", link["download"]),
                    )
        elif status == "pending":
            self.tree.set(target, "RD 狀態", result.get("rd_status", "處理中"))
            self.tree.set(target, "進度", f"{result.get('progress', 0)}%")
        elif status == "missing":
            self.tree.set(target, "RD 狀態", "✗ RD 上不存在（已從清單移除）")
        elif status == "error":
            self.tree.set(target, "RD 狀態", f"錯誤: {result.get('error', '')}")

    def on_check_done(self):
        self.btn_retry_all.config(state=tk.NORMAL)
        remaining = len(load_pending())
        completed = len(self.completed_links)
        self.progress_var.set(f"檢查完成！{completed} 個新完成 / 還剩 {remaining} 個待處理")
        if self.completed_links:
            self.btn_copy.config(state=tk.NORMAL)

    def remove_selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("提示", "請先選取要移除的項目", parent=self)
            return
        if not messagebox.askyesno("確認", f"確定要從待處理清單移除 {len(selected)} 個項目嗎？\n（不會刪除 RD 上的 torrent）", parent=self):
            return
        for item_id in selected:
            vals = self.tree.item(item_id, "values")
            if vals and vals[0]:
                remove_pending(vals[0])
        self.refresh_list()

    def copy_completed(self):
        links = [link["download"] for link in self.completed_links if link.get("download")]
        if not links:
            return
        self.clipboard_clear()
        self.clipboard_append("\n".join(links))
        self.progress_var.set(f"已複製 {len(links)} 個本次完成的連結")

    def on_double_click(self, event):
        item = self.tree.focus()
        if not item:
            return
        values = self.tree.item(item, "values")
        if values and len(values) >= 5 and values[4] and values[4].startswith("http"):
            self.clipboard_clear()
            self.clipboard_append(values[4])
            self.progress_var.set("已複製連結")

    def on_close(self):
        self.cancelled = True
        self.destroy()


def _enable_dpi_awareness():
    """在 Windows 啟用 Per-Monitor DPI 感知，解決字型模糊問題"""
    if sys.platform != "win32":
        return
    try:
        from ctypes import windll
        try:
            windll.user32.SetProcessDpiAwarenessContext(-4)  # PER_MONITOR_AWARE_V2
        except Exception:
            try:
                windll.shcore.SetProcessDpiAwareness(2)  # Per-Monitor
            except Exception:
                windll.user32.SetProcessDPIAware()  # 系統 DPI（最低保險）
    except Exception as e:
        logger.warning(f"啟用 DPI 感知失敗: {e}")


def _get_dpi_scale() -> float:
    """取得主螢幕 DPI 縮放倍率（96 DPI = 1.0, 144 = 1.5, 192 = 2.0）"""
    if sys.platform != "win32":
        return 1.0
    try:
        from ctypes import windll
        dc = windll.user32.GetDC(0)
        dpi = windll.gdi32.GetDeviceCaps(dc, 88)  # LOGPIXELSX
        windll.user32.ReleaseDC(0, dc)
        if dpi <= 0:
            return 1.0
        return dpi / 96.0
    except Exception as e:
        logger.warning(f"取得 DPI 失敗: {e}")
        return 1.0


def _apply_dpi_scaling(root: tk.Tk, override: float | None = None) -> float:
    """設定 Tk 縮放。override 不為 None 時使用該倍率，否則依系統 DPI"""
    if override is not None and override > 0:
        scale = override
        logger.info(f"使用手動 UI 縮放: {scale:.2f}x")
    else:
        scale = _get_dpi_scale()
        logger.info(f"自動偵測 DPI: {scale * 96:.0f} ({scale:.2f}x)")
    tk_scaling = scale * 96 / 72
    root.tk.call("tk", "scaling", tk_scaling)
    logger.info(f"Tk scaling: {tk_scaling:.3f}")
    return scale


def _pick_font(root: tk.Tk, preferences: list[str]) -> str:
    """從偏好清單回傳第一個系統有安裝的字型，找不到時回傳清單最後一個"""
    from tkinter import font as tkfont
    available = set(tkfont.families(root))
    for name in preferences:
        if name in available:
            return name
    return preferences[-1]


def _setup_fonts(root: tk.Tk, base_size: int = 10):
    """設定預設字型 + ttk 樣式字型（蓋過 sv-ttk）"""
    from tkinter import font as tkfont

    ui_font = _pick_font(root, [
        "Noto Sans TC",
        "Noto Sans CJK TC",
        "Microsoft JhengHei UI",
        "Microsoft JhengHei",
        "Segoe UI",
    ])
    mono_font = _pick_font(root, [
        "Cascadia Mono",
        "JetBrains Mono",
        "Consolas",
        "Courier New",
    ])
    logger.info(f"UI 字型: {ui_font}, 等寬字型: {mono_font}, 基礎大小: {base_size}pt")

    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont",
                 "TkHeadingFont", "TkCaptionFont", "TkSmallCaptionFont", "TkIconFont"):
        try:
            tkfont.nametofont(name).configure(family=ui_font, size=base_size)
        except Exception:
            pass  # nosec B110 — Tk named font may not exist on this platform; fall back silently
    try:
        tkfont.nametofont("TkFixedFont").configure(family=mono_font, size=base_size)
    except Exception:
        pass  # nosec B110 — same as above for the fixed-width font

    return ui_font, mono_font, base_size


def _apply_ttk_font(root: tk.Tk, ui_font: str, base_size: int = 10):
    """蓋掉 sv-ttk 對 ttk widgets 的字型設定（要在 set_theme 之後呼叫）"""
    style = ttk.Style(root)
    for s in ("TButton", "TLabel", "TEntry", "TCombobox", "TCheckbutton",
              "TRadiobutton", "TMenubutton", "TLabelframe.Label",
              "TNotebook.Tab", "Treeview", "Treeview.Heading"):
        try:
            style.configure(s, font=(ui_font, base_size))
        except Exception:
            pass  # nosec B110 — sv-ttk may not define every style; skip missing ones


if __name__ == "__main__":
    # Initialize logging before any GUI work (deferred from module scope in M1).
    setup_logging()

    _enable_dpi_awareness()
    root = tk.Tk()

    # 從 .env 讀 UI 縮放（auto 或具體倍率）
    env = load_env(ENV_FILE)
    ui_scale_setting = env.get("UI_SCALE", "auto").strip().lower()
    if ui_scale_setting in ("", "auto"):
        override = None
    else:
        try:
            override = float(ui_scale_setting)
        except ValueError:
            override = None
    _apply_dpi_scaling(root, override=override)

    ui_font, mono_font, base_size = _setup_fonts(root, base_size=10)
    try:
        import sv_ttk
        theme = env.get("UI_THEME", "light").strip().lower()
        if theme not in ("light", "dark"):
            theme = "light"
        sv_ttk.set_theme(theme)
        logger.info(f"已套用 sv-ttk 主題: {theme}")
    except ImportError:
        logger.warning("sv-ttk 未安裝，使用預設 ttk 主題")
    _apply_ttk_font(root, ui_font, base_size)
    App(root)
    root.mainloop()
