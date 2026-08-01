# RD 送出成效日誌規格

日期：2026-08-01　狀態：**已實作**（commit `1cd0410`，修正 `e77ac4d`）。
現行行為以程式碼為準：`rd_outcome_log.py`、`sidecar/sidecar.py::cmd_rd_send_magnet`、
`scripts/rd_log_report.py`；契約見 `docs/architecture/contracts/sidecar-runtime.md` §1。
本檔為歷史存檔，只補「實作偏離」段（§12），不回頭改寫正文。

## 1. 目的

`docs/specs/2026-08-01-rd-hit-priority.md` 的啟發式（轉載站前綴／最早高清）是**推測**，
無任何實證。本規格新增一份磁碟日誌，累積真實送出結果，讓那套規則能被**證偽與調整**。

## 2. 核心設計原則：只記觀測，不記判定

日誌**不得**寫入 `rd_class` / `tier` / `is_hd` 等衍生判定，只寫原始觀測值
（`name` / `tags` / `date` / `size`）。三個理由：

1. **零規則重複**：判定規則的唯一來源仍是 `app/src/lib/rdPriority.ts`；Python 端不複製
   前綴清單與解析度正則。
2. **舊資料可重新分析**：規則改版後（本專案今天才剛收緊過一次 1080/2160 正則），
   記死判定的舊列會永遠鎖在舊規則下；記原始值則可整批重跑。
3. **可測新假設**：發布組名稱、副檔名、檔案數等尚未納入規則的訊號，日後不必改
   日誌格式就能檢驗。

假設寫在報表腳本，觀測寫在日誌——分工不得混淆。

## 3. 標籤設計：三元，不是二元

現行 `completed` 混了兩種對使用者完全不同的現象，且分界線由設定值決定：

- `deadline = time.time() + cache_wait`（`realdebrid.py:327`），迴圈輪詢到 deadline
  為止（`:333`）。**同一 magnet 在 `cache_wait=5` 與 `=60` 下會得到不同 outcome。**
- 迴圈內的 429 退避 sleep（`realdebrid.py:106-124`）會吃掉同一份 wall-clock 預算，
  一次速率風暴可以把本來會命中的送出擠成 pending。
- `_raise_if_terminal_failure`（`:372-379`）**只處理 `magnet_error` 與 `error`**；
  `dead` / `virus` 等終態會一路輪詢到逾時後偽裝成 pending。

因此**必須**記錄 `elapsed_ms` 與當下的 `cache_wait`，標籤才可跨時間比較。三元標籤在
**分析時**由耗時門檻決定，不在寫入時固化：

| 標籤 | 判定（報表腳本） |
|---|---|
| 快取命中 | `outcome=completed` 且 `elapsed_ms` < 門檻（預設 5000） |
| 未快取但下載快 | `outcome=completed` 且 `elapsed_ms` ≥ 門檻，或 pending 後被 check 事件翻成 completed |
| 沒人有 | 始終 pending / 終態失敗 |

## 4. 落地層：純 sidecar（Python），零 Rust

理由：

- **只有 Python 這層能取得真實耗時與 RD 狀態轉移**；Rust 只看得到整趟往返。
- **Rust 在本機無法驗證**：`cargo check` exit 101（`secret-service` 未啟用 runtime
  feature）。動 Rust 等於交付無法驗證的程式碼。
- 因為只記原始觀測（§2），sidecar **不需要前端傳任何新欄位下來**，免動
  `RdSendOptions` → Rust struct → payload 這條 4–7 處的鏈。

## 5. 檔案與開關

- 檔名 `rd_outcomes.jsonl`，位置＝`debug.log` 同目錄（`app_logging.get_log_file().parent`）。
  logging 若降級為 console-only（Linux/macOS 無 `LOCALAPPDATA` 時會發生），本功能靜默停用。
- 輪替：`RotatingFileHandler(maxBytes=5*1024*1024, backupCount=3)`，比照
  `app_logging.py:85-87`。**不得**照抄 `pending.rs` 的 4 MiB 讀取硬上限——它超過即永久
  `Err`，套在只增不減的日誌上會鎖死。
- 開關：環境變數 `JAVDB_RD_LOG`，預設開；`"0"` 關閉。比照既有 `JAVDB_LOG_DIR` 慣例。
- 專用 logger 且 **`propagate = False`**：`app_logging.py` 把 handler 掛在 root
  （`:95`、`:105`），不切斷傳播的話每行 JSON 會同時灌進 `debug.log`。

## 6. 紅線（違反即破壞既有發布 gate）

- **不得寫入 `magnet_redacted` 或任何 `magnet:?xt=` / `urn:btih:` 字串。**
  `docs/troubleshooting/log-redaction-verification.md:23` 與
  `docs/sessions/m6a-release-smoke.md:53-54` 會 grep 整個 log 目錄找該 pattern 並預期
  零輸出，而 `redact_magnet()` 的輸出正好長那樣。關聯鍵用**裸 8 碼 hex**
  （`realdebrid.py:363 _extract_magnet_hash` 既有格式，debug.log 已在用）。
- 不得寫入 RD token、`Authorization`、cookie、完整 traceback、RD 回應 raw body。
- 不得寫入 `handle_id`——它是 session 內 UUID（`sidecar.py:311`），落地後語意會變成
  跨 session 的持久識別碼。

使用者已核准記錄 `code`（番號）、`name`、`tags`、`date`、`size`。前三者已屬既有暴露類別
（`pending_torrents.json` 的 `code`/`name`；`debug.log` 的 `realdebrid.py:282/399/494`）；
`tags`/`date` 為新增，`completed` 案例落地亦為新增（目前只有 pending 寫檔）。

## 7. 事件格式（JSONL，一行一物件）

### send
```json
{"v":1,"ts":"2026-08-01T13:55:02.123+08:00","event":"send",
 "btih8":"0201592f","torrent_id":"XYZ123","outcome":"completed",
 "elapsed_ms":1840,"rd_status":"downloaded","first_status":"waiting_files_selection",
 "progress":0,"files_selected":true,"link_count":2,"error_code":null,
 "code":"SNOS-192","name":"hhd800.com@SNOS-192-1080p.mp4","size":"5.4GB, 1個文件",
 "tags":["高清"],"date":"2026-06-18",
 "group_seq":3,"group_size":5,"date_rank":2,"size_rank":1,
 "cache_wait":15,"file_pick":"smart","min_size_mb":500}
```

- `outcome` ∈ `completed` / `pending` / `error`。
- `error_code` 用 sidecar 既有分類（`sidecar.py:590-603`）。註記：`rd_rate_limited`
  同時涵蓋真 429 與時間預算耗盡（`realdebrid.py:48/117` 都以 `HTTP 429:` 開頭），
  報表不得把它一律當速率限制。
- `first_status`：selectFiles 之後第一次觀測到的 RD 狀態，用來區分 RD 端排隊
  （`queued`）與實際下載（`downloading`）。
- `group_seq` / `group_size` / `date_rank` / `size_rank`：**必須在 fetch 時算好**，
  因為只有被送出的列會進日誌，事後無法重建群組。`size_rank` 用既有
  `javdb_scraper.parse_size_gb`（不新增解析邏輯）。
- **不記 `age_days`**：由 `ts − date` 在分析時算，避免固化。

### check（重試路徑）
```json
{"v":1,"ts":"...","event":"check","torrent_id":"XYZ123","outcome":"completed",
 "elapsed_ms":320,"rd_status":"downloaded","progress":100,"link_count":2,"error_code":null}
```

以 `torrent_id` 與 send 事件 join。這是把「pending」從單一標籤拆成
「四分鐘後完成」與「三天後仍沒有」的唯一依據。
註記：`check_torrent` 不呼叫 `_raise_if_terminal_failure`（`realdebrid.py:431-476`），
所以重試看到 `magnet_error` 會回報 pending 而非錯誤——報表需自行辨識。

## 8. 實作範圍

1. **新檔 `rd_outcome_log.py`**（repo root，與 `app_logging.py` 同層，供 PyInstaller
   打包）：logger + rotating handler 建構、`propagate=False`、開關判定、
   `log_send(...)` / `log_check(...)` 兩個寫入函式、寫入失敗一律吞掉（日誌絕不能
   讓送出失敗）。
2. **`sidecar/sidecar.py`**：
   - `cmd_fetch_javdb` 時保存每個 handle 的 metadata（name/size/tags/date/group_seq/
     group_size/date_rank/size_rank）到新的 `state.magnet_meta`，比照
     `state.magnets` 的既有上限與 `forget_magnets` / clear 清除路徑。
   - `cmd_rd_send_magnet`：用 `time.monotonic()` 量測 `process_magnet` 全程，
     成功與失敗兩條路徑都寫 log。
   - `cmd_rd_check_pending`：寫 check 事件。
3. **`realdebrid.py`**：`process_magnet` 新增 optional `observer` 參數回報狀態轉移
   （取 `first_status`）。**不得改動回傳 dict 的既有欄位**——Rust 端
   `RdSendOutcome` 是 tagged enum，本機無法編譯驗證，不冒這個險。
4. **新檔 `scripts/rd_log_report.py`**：讀 JSONL、join send/check、套三元標籤、
   輸出各訊號的命中率表。
5. **測試**：`tests/test_rd_outcome_log.py`（新）＋ 既有 sidecar 測試不得回歸。

## 9. 報表腳本必須內建的兩道防呆

這兩點是使用者提出後確認要做進設計的：

1. **樣本偏斜警告**：新功能會把勾選收斂到 ★ 首選，若使用者只送推薦的那筆，日誌裡
   幾乎不會有 `plain` 類樣本，命中率表就**永遠無法證偽推薦規則**。報表必須逐類
   印出樣本數，且 n 低於門檻（預設 10）時明確標示「樣本不足，不下結論」。
2. **排除自造命中**：同一 `btih8` 送第二次必定命中——因為第一次是使用者自己放進
   RD 的。報表預設只採計每個 `btih8` 的**首次**觀測，並回報排除了幾筆。

## 10. 驗收

```
.venv/bin/python -m pytest tests/ -q          # 全綠，330 passed 不得減少
cd app && npx vitest run                      # 253 passed 不變（本輪不動前端）
cd app && npm run check                       # 0 errors 0 warnings 不變
```

Rust gate 跳過（baseline 即編不過，本輪不動 Rust）。

額外驗收：對既有 redaction gate 的 pattern 實跑一次，證明新日誌不觸發：
```
grep -nE 'magnet:\?xt|urn:btih' <log_dir>/rd_outcomes.jsonl   # 預期無輸出
```

## 11. 非目標

- 不動 Rust、前端、`RdSendOptions` 傳遞鏈。
- 不在 Python 複製任何啟發式規則。
- 不做設定頁 UI 開關（用環境變數）。
- 不自動上傳、不做遙測外送——純本機檔案。

## 12. 實作偏離本規格之處（事後補記，2026-08-01）

1. **§7／§8.3 的 `first_status` 未落地，實作為 `status_trail`**：`observer` 每輪都拿得到
   status，只留第一個會丟掉「queued → downloading → downloaded」這種轉移序列，而那正是
   區分「RD 端排隊」與「實際在下載」的訊息。改記摺疊連續重複、上限 8 筆的序列。
   釘住此欄位的測試：`tests/test_rd_outcome_log.py::StatusTrailTest`、
   `tests/test_rd_outcome_log_e2e.py::E2ECachedHit`。

2. **§3 的標籤定義曾未被報表完整實作**：規格寫「沒人有 = 始終 pending／終態失敗」，
   但初版 `rd_log_report.py` 把**所有** error 排除於分母，包含 `rd_magnet_error` 這類
   磁力終態失敗——會系統性高估命中率。已修正為終態失敗歸 `miss`、環境錯誤
   （token／429／API）維持排除並單獨報數。

3. **§2「不在 Python 複製任何啟發式規則」的範圍澄清**：該條約束的是**日誌寫入端**
   （sidecar 只記原始觀測）。`scripts/rd_log_report.py` 持有一份分析用的 prefix 清單與
   解析度正則，是 §2 尾句與 §3 表頭「判定（報表腳本）」刻意設計的分工——假設寫在報表、
   觀測寫在日誌，才能不改格式就重跑舊資料檢驗新規則。這不是偏離，是規格意圖，
   但原文措辭容易被讀成「整個 Python 都不得有規則」，在此澄清。