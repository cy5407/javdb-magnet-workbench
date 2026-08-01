# 開發進度

> 本檔按「最新在最上」追加。早於下方 2026-05-09 的段落是 Tauri 改寫前的紀錄，
> 其中的「下一步：Rust fetch spike」已有結論——保留 Python sidecar，Rust 只做
> 殼與 IPC。歷史段落保留原樣，不回頭改寫。

## 2026-08-01

### RD 命中優先 + 送出成效日誌

送出後等待 pending 轉 https 連結是使用時最大的時間成本。這一輪做了兩件事：

1. **送出前預判命中機率**（commit `f92c33d`）。RD 已於 2024 移除
   `instantAvailability`，無法查詢快取，故以本地啟發式分級：轉載站前綴
   （`hhd800.com@` / `489155.com@`）＋高清 ＞ 最早上傳的高清 ＞ 全組皆非高清時
   標警示。新增 `app/src/lib/rdPriority.ts`（leaf 模組，避免與 magnetUtils 循環）、
   `每組只留：RD 命中優先`、每列徽章與 ★ 首選、一鍵「只勾選 RD 優先候選」、
   送出前攔截摘要。
   - 行為契約變更：`isHd` 由「只看 tag」擴充為「tag ∨ 檔名解析度」，
     `filterRows` 的 `hd_only` 一併放寬。
   - 裸數字 `1080`/`2160` 只在 `WxH` 形式承認——`259LUXU-1080`、`HEYZO-2160`
     都是真實番號，誤判高清會一路通過篩選與「高機率」桶而無人攔截。

2. **成效日誌**（commit `1cd0410`、`e77ac4d`）。sidecar 把每次送出／重試寫成
   `logs/rd_outcomes.jsonl`，`scripts/rd_log_report.py` 據以算命中率。
   - **只記觀測不記判定**：寫 `name`/`tags`/`date`/`size` 原始值而非 `rd_class`，
     所以 Python 端零啟發式規則，且規則改版後舊日誌仍可重新分析。
   - **三元標籤**：`completed` 混了「RD 早就有」與「等了 50 秒下載完」，而分界線
     由 `cache_wait` 決定，故記 `elapsed_ms` 與當下設定，標籤在分析時才判定。
     重試事件以 `torrent_id` join，把 pending 拆成「後來完成」與「始終沒有」。
   - 報表內建樣本偏斜警告與排除自造命中（同一 magnet 第二次必中，因為第一次是
     自己放進去的）。

### 平台

於 Linux 實測確認 `cargo test --lib` 這個長期被跳過的 gate **是可修的**
（keyring features 按平台拆開 + 一份 Linux sidecar binary → 81 passed）。
需要修正的環節逐項記於
[`docs/platform/linux-support.md`](docs/platform/linux-support.md)；本輪只記錄，
未實作。

### Gate（commit `e77ac4d`）

| Gate | 結果 |
|---|---|
| `pytest tests/ -q` | 394 passed, 6 subtests |
| `npx vitest run` | 9 files / 253 tests |
| `npm run check` | 189 files, 0 errors 0 warnings |
| `cargo test --lib` | 跳過（需先套用 linux-support.md 的兩項修改） |

---

## 2026-05-09

### 完成項目

#### 0. 文件 / 預設值不一致修補（dev worktree，未提交）

回應前一輪 [PROGRESS.md 不一致項目 A–E](#文件-vs-實作不一致建議修補) 的修補。
**位置**：`<repo>-dev`（dev worktree；master worktree 未動）。

| # | 檔案 | 修改 |
|---|------|------|
| A | `.env.example` line 7 | `smart` 描述補完整：番號比對 + size 門檻、退回 size 門檻、退回最大檔 |
| B | `.env.example` 末尾 | 新增 `UI_SCALE=auto` 和 `UI_THEME=light` 兩項與註解 |
| C | `README.md` 第 22–31 行 | 「執行後自動產生」改為精確描述：`.env` 在儲存後產生、`cookies.txt` 需手動建立、`logs/` 與 `pending_torrents.json` 為執行時產生 |
| D | `README.md` 第 41–47 行 | 設定畫面清單補上「UI 縮放」「主題」 |
| E | `realdebrid.py:214` | `process_magnet(strategy="largest")` → `strategy="smart"`（與 GUI/README/.env.example 一致） |

**驗證**：
- `python -m unittest discover -s tests -v` → `Ran 41 tests in 0.001s OK`
- `python -m py_compile app_logging.py build.py javdb_magnet.py javdb_magnet_gui.py realdebrid.py` → ✓ syntax OK
- 沒有改測試邏輯（`tests/test_core_logic.py` 未動）
- 沒有動 master worktree

#### 1. fallback session headers 修正（commit `3116a69`）
- **檔案**：`javdb_magnet_gui.py` `create_session()`
- **修改**：當 `curl_cffi` 不可用時，原本回傳 `requests.Session()` 沒套 headers；
  改為先 `session.headers.update(headers)` 再回傳，與 `curl_cffi` 路徑行為一致。

#### 2. 核心邏輯回歸測試（unittest，純 stdlib）

**新增**：`tests/test_core_logic.py`

**覆蓋函式**：
| 模組 | 函式 | 測試類別 | 測試數 |
|------|------|---------|--------|
| `javdb_magnet_gui` | `parse_size_gb` | `ParseSizeGB` | 6 |
| `javdb_magnet_gui` | `parse_file_count` | `ParseFileCount` | 4 |
| `realdebrid.RealDebrid` | `_extract_code` | `ExtractCode` | 8 |
| `realdebrid.RealDebrid` | `_filename_matches_code` | `FilenameMatchesCode` | 9 |
| `realdebrid.RealDebrid` | `pick_files` (all/video/largest/smart) | `PickFiles*` | 14 |
| **合計** | | | **41** |

**執行結果**：
```
Ran 41 tests in 0.001s
OK
```

**特性**：
- 不連網、不讀 `.env` / `cookies.txt`、不打 RD/JavDB API
- `RealDebrid` 透過 `__new__()` 建立，跳過 token 驗證
- 涵蓋 smart 策略全部分支：
  - 番號比對 + size 門檻
  - 番號全匹配但都低於門檻 → 仍保留番號匹配
  - 番號比對失敗 → 退回 size 門檻
  - size 門檻全失敗 → 退回最大檔
  - 多段切割（兩段都選到）

**`py_compile` 通過**：`app_logging.py`, `build.py`, `javdb_magnet.py`, `javdb_magnet_gui.py`, `realdebrid.py`

---

### 文件 vs 實作不一致（建議修補）

#### A. `.env.example` 的 smart 策略描述過時
**位置**：`.env.example` line 7
**現況**：
```
# smart   = 所有影片副檔名且 >= RD_MIN_SIZE_MB 的檔案（推薦，可過濾廣告並支援多段影片）
```
**實際行為**（已被 `tests/test_core_logic.py` 鎖定）：
1. 先從 magnet 的 `dn=` 抽出番號（如 `SNOS-192`）
2. 番號匹配的影片檔 + size 門檻
3. 沒命中時退回單純 size 門檻
4. 仍空時退回最大檔

`README.md` 第 116-134 行有正確的兩階段描述；`.env.example` 應同步更新。

#### B. `.env.example` 缺 UI 設定欄位
**現況**：`.env.example` 只列 `RD_*` 五項
**實際行為**：`SettingsDialog` 儲存時會寫入 `UI_SCALE` 和 `UI_THEME`（見 `write_env()` 模板）
**建議**：在 `.env.example` 加上 `UI_SCALE=auto` 和 `UI_THEME=light` 兩行

#### C. `README.md` 沒提 UI 縮放與主題
**位置**：README.md line 41-45「設定畫面也可以調整」
**現況**：列了 4 項（策略 / 最小檔案 / 快取等待 / 超時）
**缺漏**：UI 縮放（4K 螢幕重要）、主題切換（light / dark）

#### D. README.md 自動產生的檔案描述
**位置**：README.md line 27
**現況**：
```
└── (執行後會自動產生 .env / cookies.txt / logs/ / pending_torrents.json)
```
**問題**：
- `.env` 只有透過「設定」按鈕儲存才會產生（程式啟動不會自動建）
- `cookies.txt` 完全需要使用者手動建立（程式不會產生）

#### E. `realdebrid.process_magnet` 預設 strategy 不一致
**位置**：`realdebrid.py` line 214
**現況**：`def process_magnet(self, magnet, strategy: str = "largest", ...)`
**問題**：實際使用流程都用 `smart`（GUI 一律從 `.env` 讀取後傳入）
**影響**：函式預設值是 dead default，不影響執行；但維護時容易誤導
**建議**：改成 `strategy: str = "smart"` 與其他地方一致

---

### 下一步：Rust fetch spike

確認 `reqwest` 能否成功抓 JavDB 影片頁面的磁力連結。重點：
- TLS 指紋是否需要 `rustls` + `cloudflarebreak` 之類客製化
- cookie 處理（傳同樣的 `_jdb_session` / `cf_clearance` 是否能繞 Cloudflare）
- HTML 解析（用 `scraper` 或 `select`）
- 結果決定後續架構：純 Rust backend / 保留 Python sidecar / 混合

---

## 後續更新

新進度請追加在這個檔案下方（最新在最上）。
