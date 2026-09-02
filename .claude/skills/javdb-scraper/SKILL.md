---
name: javdb-scraper
description: JavDB 網頁爬取、TLS 偽裝、Sidecar RPC 通信與 Real-Debrid 雲端快取整合 SOP
---

# JavDB Scraper & Real-Debrid Acceleration Skill

## 1. When to Apply
- 處理 JavDB 網址解析、番號提取、磁力清單抓取等爬蟲邏輯。
- 呼叫或擴充 Python Sidecar Daemon RPC 命令（如 `fetch_javdb`, `rd_send_magnet`, `rd_check_pending` 等）。
- 與 Real-Debrid API 進行互動（帳號查詢、新增磁力、智慧選檔、快取判定、待處理佇列排程）。

## 2. When NOT to Apply
- 純粹的前端 UI 樣式微調（無涉及 IPC 資料流或後端交互）。
- Archify 架構圖引擎維護（應使用 `archify` 專用 Skill）。

## 3. Data Flow Architecture
本專案遵循三層式架構與單向資料流（參考 `architecture.html` 與 `workflow.html`，跨層契約以 `docs/architecture/contracts/` 為唯一真實來源）：
1. **前端表現層 (Svelte 5)**：使用者輸入 URL/Magnet，由 `scraper.ts` / `rdSender.ts` / `rdPriority.ts` 發起非同步請求。
2. **後端控制層 (Rust Tauri 2.0)**：`commands.rs` 接收 IPC 呼叫，透過 `sidecar_manager.rs` 以 Stdio JSONL 調度 Python 進程；敏感 Token 經 `secret_store.rs` 存取 Windows Credential Manager。
3. **運算與資料層 (Python Sidecar)**：
   - `javdb_scraper.py`：透過 `curl_cffi` (Chrome-124 偽裝) 抓取網頁並解析磁力。
   - `sidecar.py`：維護 `MagnetHandleTable` 記憶體映射，杜絕明文 Magnet 暴露於外部。
   - `realdebrid.py`：執行智慧選檔、429 退避與快取秒回判定。

## 4. Operational Invariants & Code Contracts

### 4.1 基礎 JSON-RPC 回應信封
所有 Sidecar 回應均遵循以下信封格式（`sidecar/sidecar.py:222-234`）：
- **成功**：`{"ok": true, "request_id": str|null, ...payload}`
- **失敗**：`{"ok": false, "request_id": str|null, "error": {"code": str, "message": str, "internal": str}}`；`internal` 一律存在，未提供時為空字串。

### 4.2 命令回傳結構契約
- 呼叫端先判斷 `ok`；`fetch_javdb` 從 `result`、`rd_user` 從 `user` 讀取，其餘成功欄位都在信封層，禁止假設單一平鋪或巢狀形狀。
- **`fetch_javdb` (雙層巢狀)**：
  `{"ok": true, "request_id": ..., "result": {"engine": str, "url": str, "code": str, "title": str, "magnet_count": int, "magnets": [{"handle_id": str, "name": str, "size": str, "tags": list[str], "date": str, "magnet_redacted": str}]}}`
- **`rd_user` (雙層巢狀)**：
  `{"ok": true, "request_id": ..., "user": {"username": str, "type": str, "expiration": str, "points": int}}`
- **`rd_send_magnet` (信封層平鋪)**：
  - `status="completed"`：`{"ok": true, "request_id": ..., "status": "completed", "torrent_id": str, "name": str, "links": list[str]}`
  - `status="pending"`：`{"ok": true, "request_id": ..., "status": "pending", "torrent_id": str, "name": str, "rd_status": str, "progress": int, "files_selected": bool, "strategy": str}`
- **`resolve_magnet` (信封層平鋪)**：`{"ok": true, "request_id": ..., "magnet": str}`

### 4.3 前置條件守衛（Handshake Guard）
依據 `docs/architecture/contracts/sidecar-runtime.md`，僅以下 6 個命令受 `handshake_done` 守衛：
`fetch_javdb`、`set_cookies`、`rd_user`、`rd_set_token`、`rd_send_magnet`、`rd_check_pending`。

### 4.4 邊界限制常數
- `MAX_FETCH_MAGNETS = 1000`（單次抓取上限）
- `MAX_REGISTER_MAGNETS = 1000`（單次註冊上限）
- `MAX_MAGNET_URI_LEN = 4096`（單一磁力字元長度上限）
- `MIN_RD_CACHE_WAIT_SECS = 5`, `MAX_RD_CACHE_WAIT_SECS = 300`
- `MAX_RETRY_AFTER_SECONDS = 10`

### 4.5 錯誤碼與 429 退避規範
- **核心錯誤碼**：`bad_request`, `network`, `cloudflare_block`（僅 403 觸發）, `unknown_handle`, `rd_token_missing`, `rd_token_invalid`, `rd_permission_denied`, `rd_api_error`, `internal`。
- **429 速率限制**：單次退避上限為 10 秒，最多重試 3 次，且必須受 `deadline`（`monotonic() + cache_wait + 75.0`）預算約束。
- **隱私安全**：日誌嚴禁記錄完整 Magnet URI 或 Token，一律經 `redact_magnet()` 或保留 8 碼 BTIH 前綴。
