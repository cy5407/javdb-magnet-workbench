# Rust fetch spike (JavDB)

## 目的
驗證能否用純 `reqwest`（rustls）+ `scraper` 抓 JavDB 影片頁並解析磁力連結。
結論決定 Rust/Tauri 重寫的後端架構：
- ✅ 可行 → 純 Rust backend
- ❌ 不可行 → 需要 curl-impersonate / Python sidecar / Tauri 直接用瀏覽器 webview

**只是 spike**，不會被 commit；未連動到專案 build。

## 用法

```
cd spikes/rust_fetch_javdb
cargo run -- "https://javdb.com/v/xxxx"
```

從 repo root 的 `cookies.txt` 讀 cookie。
**不會** 印出 cookie 值或完整 magnet 連結。

## 對照組
- Rust 版：本 spike
- Python 版：`fetch_magnets()` in `javdb_magnet.py` 或 `javdb_magnet_gui.py`（curl_cffi）

## 結果欄位

```json
{
  "ok": true/false,
  "http_status": 200,
  "engine": "reqwest",
  "title": "...",
  "code": "...",
  "magnet_count": N,
  "first_magnet_starts_with_magnet": true/false,
  "challenge_suspected": true/false,
  "error": null 或字串
}
```

`challenge_suspected` 為 true 表示 200 但找不到 `#magnets-content`，
且 body 含 `Just a moment` / `cf_clearance` / `challenge` 字串，
代表可能被 Cloudflare 或登入牆擋。

## 測試結果

**測試日期**：2026-05-10
**測試 URL**：`https://javdb.com/v/RkX3Rp`（使用者明確授權）
**cookies.txt**：使用者既有的 JavDB session（含 `_jdb_session` / `cf_clearance` / `locale`）

### Rust spike (reqwest + rustls)

```json
{
  "ok": false,
  "http_status": 403,
  "engine": "reqwest",
  "title": "",
  "code": "",
  "magnet_count": 0,
  "first_magnet_starts_with_magnet": false,
  "challenge_suspected": true,
  "error": "HTTP 403"
}
```

### Python 對照組 (`fetch_magnets` via `create_session`)

```json
{
  "engine": "curl_cffi",
  "has_error": false,
  "error": "",
  "has_title": true,
  "has_code": true,
  "magnet_count": 3,
  "first_starts_with_magnet": true
}
```

### 同 URL、同 cookie、同分鐘內

| 維度 | Rust (reqwest+rustls) | Python (curl_cffi) |
|------|----------------------|--------------------|
| HTTP status | **403** | 200 |
| magnet_count | **0** | **3** |
| 取到 title/code | 否 | 是 |
| 被偵測為 challenge | 是 | 否 |

## 結論

**純 reqwest 不可行**。差異不在 cookie，也不在 headers（兩邊發的 headers 幾乎一樣），
是 **TLS / HTTP/2 指紋**。Cloudflare 在 TLS 握手階段就拒絕 rustls 預設 ClientHello，
直接回 403。`curl_cffi` 之所以成功，是因為它替換 BoringSSL/curl 並仿造 Chrome 124 的
TLS extension 順序與 fingerprint。

### 後續架構的可行路線

1. **Rust + curl-impersonate 系列 crate**
   - 候選：`rquest`（`reqwest` fork，內建 Chrome/Firefox/Safari 指紋）、
     `impit`、直接 FFI `curl-impersonate`
   - 優點：純 Rust binary，能對齊 Python 行為
   - 風險：crate 還在 alpha；Windows 下打包 BoringSSL 較痛
   - **這是首選**

2. **Tauri / Rust 主體 + Python sidecar 處理 HTTP**
   - Tauri 啟動時把 Python interpreter（或 PyInstaller 產出的小 binary）作為 sidecar
     呼叫，沿用現有 `realdebrid.py` / `fetch_magnets`
   - 優點：100% 復用現成 Python 程式，最低風險
   - 缺點：app 體積增加（~30MB Python runtime + curl_cffi）

3. **Tauri webview 拉 HTML，前端 JS 解析**
   - 利用 webview 內的 Chromium TLS（自然能過 Cloudflare）
   - 缺點：跨進程通訊複雜、cookies 同步麻煩、解析寫在 JS 不方便共用測試

### 建議

採用方案 1（rquest）做下一輪 spike。失敗（碰到 BoringSSL 編譯/打包問題）才退回方案 2（sidecar）。
**禁止** 為了讓純 reqwest 過 Cloudflare 而手動湊 TLS 參數，那是死路。

