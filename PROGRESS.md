# 開發進度

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
