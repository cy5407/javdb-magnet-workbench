# JavDBMagnet

JavDB 磁力連結擷取 + Real-Debrid 直連產生工具（Windows 桌面版）。

- 從 JavDB 影片頁面**批次抓取**磁力連結
- **直接貼上 magnet**：已有連結時跳過 JavDB，直接送 Real-Debrid
- 篩選 / 排序 / 群組去重，一鍵送 RD
- **待處理清單**：RD 還在處理的 torrent 不卡住流程，可稍後重試
- RD 直連既可**一鍵批次複製**全部到剪貼簿（貼進 IDM / aria2 / 任何下載器），也可在每筆完成的 row 內**單獨挑選**任一連結複製（每條 URL 都是可選取的欄位 + 各自的「複製」鈕）
- 所有動作按鈕都有**點擊回饋**：按下時下沉、成功後 1.2 秒內按鈕變綠並顯示「已X ✓」確認文字
- 設定面板（檔案策略、大小門檻、超時、主題、UI 縮放）
- 從**舊版 Python GUI** 一鍵匯入 `.env` / `cookies.txt` / `pending_torrents.json`

---

## 系統需求

- **Windows 10 1809+ 或 Windows 11**
- **WebView2 Runtime**（Windows 11 已內建；Windows 10 大多也有，缺則 Tauri 安裝時會自動補裝）
- **Real-Debrid 帳號**（送 RD 必要；只想抓磁力連結不送 RD 則不必）
- 磁碟空間 ~40 MB（含 sidecar.exe）

---

## 安裝 / 使用（Portable）

本專案以 **portable zip** 形式發布 —— 不寫 Program Files、不建捷徑、不碰 registry。

1. 從 GitHub Release 下載 `JavDBMagnet_<version>_portable.zip`
2. 解壓到任意資料夾，例如：
   ```
   C:\Tools\JavDBMagnet\
   ```
3. 雙擊資料夾內：
   ```
   javdbmagnet.exe
   ```
4. **不要把 `sidecar.exe` 刪掉或搬走** —— 它是 JavDB / Real-Debrid HTTP sidecar，缺一不可。

### 系統狀態

此版本**不會**：

- 寫入 `Program Files`
- 建立開始選單 / 桌面捷徑
- 寫入 Windows installer registry（不會出現在「新增或移除程式」清單）

但仍會在以下位置寫使用者資料（見下方「資料位置」）：

- `%APPDATA%\JavDBMagnet`
- `%LOCALAPPDATA%\JavDBMagnet`
- Windows Credential Manager（target name `JavDBMagnet/RD_API_TOKEN`）

### 移除方式

刪除解壓後的 JavDBMagnet 資料夾即可移除程式本體。

要連同個人資料一起清掉：

```powershell
Remove-Item "$env:APPDATA\JavDBMagnet" -Recurse -Force
Remove-Item "$env:LOCALAPPDATA\JavDBMagnet" -Recurse -Force
cmdkey /delete:JavDBMagnet/RD_API_TOKEN
cmdkey /delete:JavDBMagnet/JAVDB_COOKIES
```

### Windows SmartScreen / Defender 警告

第一次執行可能跳「Windows 已保護你的電腦」藍色警告 —— exe **未做 code signing**（個人專案、無 cert）。先比對 SHA256（每個 release 都附 `SHA256SUMS.txt`），再按：

1. 「**更多資訊**」
2. 「**仍要執行**」

```powershell
# 比對 zip 與兩個 exe 的 SHA256
Get-FileHash -Algorithm SHA256 .\JavDBMagnet_*_portable.zip
Get-FileHash -Algorithm SHA256 .\JavDBMagnet\javdbmagnet.exe
Get-FileHash -Algorithm SHA256 .\JavDBMagnet\sidecar.exe
```

---

## 第一次使用

### 1. 設定 Real-Debrid Token

1. 打開 [real-debrid.com/apitoken](https://real-debrid.com/apitoken)，登入後複製 token
2. 在 app 內 **Real-Debrid** 區塊，輸入欄填入 token
3. 按「**測試連線**」確認（會顯示帳號 / 到期日 / 點數）
4. 按「**儲存**」

Token 會存進 **Windows Credential Manager**（target name `JavDBMagnet/RD_API_TOKEN`），**絕不會寫入 `settings.json` 或任何純文字檔**。下次啟動自動載入。

### 2. 取得 JavDB cookies

JavDB 需要登入後的 cookie 才能看到磁力連結。展開「**JavDB Cookies**」區塊後有**兩種**方式設定，**推薦方式 A**（refresh `cf_clearance` 時不必重啟 app）。

兩種方式都同樣會把 cookie **加密儲存到 Windows Credential Manager**（target `JavDBMagnet/JAVDB_COOKIES`），絕不長期落在純文字檔。

#### 方式 A：直接貼上（推薦）

1. 展開「**JavDB Cookies**」區塊，按「**貼上新 cookies**」
2. 瀏覽器 DevTools → Network → 任一個 JavDB 請求 → Request Headers → 找 `Cookie:` 那行 → **不含「Cookie: 」前綴**整段複製
3. 貼到出現的 textarea，按「**儲存到認證管理員**」
4. 看到 `✓ cookies 已加密儲存` = 成功；sidecar **即時更新**，可以馬上開始抓 JavDB，**不必重啟**

#### 方式 B：編輯 cookies.txt 範本（第一次設定 / 喜歡用檔案）

1. 若顯示「✗ 尚未設定 cookies」→ 按「**建立 cookies.txt 範本**」（此按鈕僅在尚未設定時出現）
2. 按「**打開資料目錄**」會跳出 `%APPDATA%\JavDBMagnet\`，用記事本打開剛建立的 `cookies.txt`
3. 範本內已寫好兩種取得方式的步驟（F12 → Network → Request Headers 那條最直接），照做複製
4. 把整行 cookie 內容貼到範本檔最後一行（**存檔時記得選 UTF-8**），覆蓋掉 `_jdb_session=XXX; cf_clearance=XXX; locale=zh` 那行
5. 回到 app 按「**重新整理 / 套用變更**」→ 看到 `✓ cookies 已加密儲存` 即會自動把範本檔內容加密寫入 Credential Manager 並刪除明文檔

> ⚠ **`cf_clearance` 約幾小時後過期**，看到 Cloudflare 阻擋時用方式 A 重貼一次最快（不必重啟）。詳見 [troubleshooting/cloudflare.md](docs/troubleshooting/cloudflare.md)。
>
> 範本檔以 UTF-8（**不含 BOM**）寫入，避免 Cloudflare 的 cookie parser 因 BOM 失敗。

### 3. 試跑

把任一 JavDB 影片頁面 URL 貼到「**批次擷取**」textarea，按「開始擷取」。看到磁力出現在下方表格 = 整條鏈路（cookies → JavDB → 解析 → handle_id → UI）都通了。

---

## 資料位置

| 內容 | 路徑 |
|---|---|
| Settings | `%APPDATA%\JavDBMagnet\settings.json` |
| JavDB Cookies | Windows Credential Manager（**非檔案**，target `JavDBMagnet/JAVDB_COOKIES`） |
| Cookies 範本（過渡用） | `%APPDATA%\JavDBMagnet\cookies.txt`（只在方式 B 流程暫存；migration 後自動刪除） |
| Pending torrents | `%APPDATA%\JavDBMagnet\pending_torrents.json`（**不含 magnet 文字**） |
| Logs（含 sidecar debug.log） | `%LOCALAPPDATA%\JavDBMagnet\logs\` |
| RD Token | Windows Credential Manager（**非檔案**，target `JavDBMagnet/RD_API_TOKEN`） |

app 內「JavDB Cookies」區塊有「**打開資料目錄**」與「**打開 logs 目錄**」按鈕，不必手敲路徑。

### 不要 commit / 分享這些檔案

- `.env`、`.env.*`、`cookies.txt`：含登入憑證
- `pending_torrents.json`：含你曾經送過 RD 的 torrent id（可能透露你下載偏好）
- `logs/`：含 timestamped diagnostic 資料
- `logs/rd_outcomes.jsonl`：**送出成效日誌**。累積型，每送出一筆就多一行，含番號、
  檔名與上傳日期——比 `pending_torrents.json` 更完整地反映你的觀看紀錄。設
  `JAVDB_RD_LOG=0` 可完全關閉（見下節）。

Repo 的 `.gitignore` 已擋下以上路徑，但若你的工作目錄外另有備份 / 雲端同步，請手動排除。

---

## RD 命中優先與成效日誌

送到 RD 的磁力若別人已上傳過，RD 會立刻回快取並產生 https 直連；否則落入 pending，
得反覆等待重試。app 在**送出前**用本地規則預判命中機率——RD 已於 2024 移除
`instantAvailability` 端點，所以這是啟發式推測，不是查詢。

規則優先序：轉載站前綴（`hhd800.com@` / `489155.com@`）＋高清 ＞ 最早上傳的高清
＞ 全組皆非高清時標 ⚠ 且不自動勾選。挑選分頁的「每組只留：RD 命中優先」與
「只勾選 RD 優先候選」按鈕會依此收斂；送出前若批次含低機率列會先顯示摘要。

### 這套規則準不準？用日誌自己驗

每次送出與重試的結果會寫進 `logs/rd_outcomes.jsonl`（一行一次觀測）。跑報表：

```bash
python scripts/rd_log_report.py                     # 自動尋找 log 目錄
python scripts/rd_log_report.py --log <path> --threshold-ms 5000
```

報表把結果分成三類而不是成功／失敗兩類：**秒回**（RD 本來就有）、**慢但完成**
（RD 在你等待期間才下載完，或 pending 後重試才好）、**沒人有**。這個區分是必要的
——`completed` 本身混了前兩者，而分界線取決於你的 `cache_wait` 設定。

報表另有兩道防呆：

- **樣本偏斜警告**：一鍵勾選會把送出收斂到推薦那筆。若你只送推薦的，日誌裡就
  沒有對照組，命中率再漂亮也**無法證明規則有效**。偶爾走「全部送出」而不是
  「只送高機率」，才會累積到對照樣本。
- **排除自造命中**：同一磁力送第二次必定命中——因為第一次是你自己放進 RD 的。
  預設只採計每個磁力的首次觀測（`--include-repeats` 可保留）。

### 關閉

設環境變數 `JAVDB_RD_LOG=0`，sidecar 就完全不寫這個檔（`debug.log` 不受影響）。

---

## 從舊版 Python GUI 升級

若你有用過舊版 tkinter GUI（M1 時期），app 內「**匯入舊版資料**」區塊可以一鍵搬：

1. 展開「匯入舊版資料」
2. 路徑填舊 GUI 的資料夾（含 `.env` / `cookies.txt` / `pending_torrents.json`）
3. 按「**預覽**」確認偵測到的檔案
4. 按「**匯入**」

匯入規則（防止 token / magnet 落地的安全保證）：

- `.env` 內 `RD_API_TOKEN` → Windows Credential Manager（**不**寫入 settings.json）
- `.env` 其他設定（`RD_FILE_PICK`、`RD_MIN_SIZE_MB`、`RD_CACHE_WAIT`、`UI_SCALE`、`UI_THEME`）→ settings.json
- legacy `.env` 若仍有 `RD_WAIT_TIMEOUT`，匯入時會忽略並產生 warning；它不會寫進 settings.json。
- `cookies.txt` → 複製到 app 資料目錄
- `pending_torrents.json` → 匯入並**自動移除 magnet 欄位**，依 torrent_id 去重

舊檔案不會被刪除，匯入完你可以手動清掉。

---

## 設定

「**應用程式設定**」展開後可編：

| 欄位 | 預設 | 說明 |
|---|---|---|
| `file_pick` | `smart` | RD 端檔案選擇策略：smart / largest / video / all |
| `min_size_mb` | `500` | 小於此值的影片視為廣告/雜訊跳過 |
| `cache_wait_seconds` | `15` | 等 RD 判定快取的秒數（最小 5、最大 300） |
| `theme` | `light` | `light` / `dark` |
| `scale` | `auto` | UI 縮放：`auto` 或 0.5–3.0；4K 螢幕建議 1.5–2.0 |

按「儲存設定」後立即推到 sidecar，**本次工作階段就生效**，不必重啟 app。

---

## 安全模型

| 規則 | 機制 |
|---|---|
| RD token 絕不寫純文字檔 | Windows Credential Manager（keyring crate），`settings.json` 的 `rd.api_token` 永遠空字串 |
| JavDB cookies 絕不長期落純文字 | Windows Credential Manager（target `JavDBMagnet/JAVDB_COOKIES`）；`cookies.txt` 只是過渡用範本檔，下次 app 啟動 / 按「重新整理」後自動加密寫回 keyring 並刪除明文 |
| 完整 magnet 不外洩到 frontend / settings / pending JSON / log | sidecar 用 `handle_id` 引用；只在 Rust transient String（剪貼簿寫入時）與 RD HTTP body 短暫存在 |
| `pending_torrents.json` 不含 magnet 文字 | 由 Rust `entries_have_no_magnet_field` 單元測試守住 |
| `logs/` 全目錄不含**完整** magnet 與**完整** BTIH | **兩份日誌都刻意保留 BTIH 前 8 碼作為關聯鍵**（`debug.log` 由 `realdebrid.py::_extract_magnet_hash`、`rd_outcomes.jsonl` 由 `sidecar._btih8`），完整 hash 與完整 magnet 則永不寫入：`realdebrid.py::_request` 對 `data["magnet"]` 記 `<redacted>`，`rd_outcomes.jsonl` 另在寫出前逐行過 `_FORBIDDEN_RX`。由 `tests/test_rd_outcome_log_e2e.py::E2ERedactionGate` 實跑掃描守住。注意 8 碼前綴仍可在公開 torrent 索引上被搜尋比對——附 log 到公開場合前請一併考量 |
| Clipboard 寫入集中在 Rust | frontend 不直接 import `tauri-plugin-clipboard-manager` |
| capability 最小化 | `capabilities/default.json` 只開 `core:default` |
| 同一 magnet 不重複送 RD（防雙扣額度） | **兩道防線**：sidecar 維護 normalized BTIH（`btih:<lowercase-hex>`）→ handle 反查表，同 hash 不同 `dn`/大小寫/參數順序皆共用 handle；frontend 送 RD 前再依 `handle_id` 去重（`dedupeByHandleId` helper） |

詳細的 release 階段 audit 見 [docs/sessions/m6a-release-smoke.md](docs/sessions/m6a-release-smoke.md)。

---

## 疑難排解

每條 recipe 一頁，列出**症狀** / **常見根因** / **檢查指令** / **修復步驟**。

| 症狀 | recipe |
|---|---|
| 抓 JavDB 失敗、Cloudflare 阻擋 | [cloudflare.md](docs/troubleshooting/cloudflare.md) |
| RD token 顯示 invalid / 401 | [rd-token.md](docs/troubleshooting/rd-token.md) |
| 送 RD 完了沒有任何直連 / 全部 pending | [no-pending-links.md](docs/troubleshooting/no-pending-links.md) |
| 想確認 `debug.log` 沒洩漏 magnet hash | [log-redaction-verification.md](docs/troubleshooting/log-redaction-verification.md) |

---

## 開發 / 自行 build

### 環境

- Windows 10/11
- Node 20+ / npm
- Rust stable + MSVC toolchain
- Python 3.12（sidecar 用 PyInstaller 打包，所以需要 Python 來執行 build script；end-user 的 portable zip 內 `sidecar.exe` 已是 standalone，**執行**不需要 Python）

### 安裝依賴

從 repo root 安裝 Python sidecar 的 pinned deps（PyInstaller / curl_cffi / requests / bs4 / 5 個 transitive），然後進 `app/` 安裝 npm deps：

```powershell
# repo root
pip install -r requirements-sidecar.txt

# 進 app 目錄
cd app
npm install
```

`requirements-sidecar.txt` 是 sidecar build 的 exact pin；`build_sidecar.py` 會在 build 前用 `importlib.metadata` 驗版本，**不符就 fail-fast**（不再隱式 `pip install`）。第一次跑 Rust 依賴會下載 + 編譯 ~5 分鐘。

### Dev 模式（hot reload）

```powershell
cd app
npm run tauri:dev
```

會打包 sidecar → 啟動 Vite → 起 Tauri WebView。前端改檔自動 reload，sidecar / Rust 改要 Ctrl-C 後重跑。

### 出 portable zip（一條命令）

```powershell
cd app
npm run release
```

打包腳本的 Step 0 會**先跑一次 `scripts/test-release-scan.ps1`**（機密掃描的
紅測套件），失敗即中止、不產出任何 artifact。這道關卡放在腳本內部而非 npm
script 裡，因為直接呼叫 `pwsh -File scripts/build-release.ps1` 也是文件記載的
用法，掛在 wrapper 上的關卡會被那條路徑整個繞過。

接著 `scripts/build-release.ps1` 會：

1. PyInstaller 打包 `sidecar.exe`
2. `npx tauri build --no-bundle`（包含 Vite 前端 build + cargo release build；
   `--no-bundle` 跳過 MSI/NSIS。走 Tauri CLI 是必要的，因為它會帶上
   `tauri/custom-protocol` feature 把 `dist/` 嵌進 binary；
   純 `cargo build --release` 不會帶這個 feature，產出的 exe 啟動時會
   試圖連 `localhost:1420`）
3. 在 `release/JavDBMagnet/` 暫存 `javdbmagnet.exe` + `sidecar.exe` + `README.txt`
4. Staging 白名單稽核（只允許上述 3 個檔；其他任何檔案 → fail）
5. 兩個 exe 內容掃 secret pattern（BTIH hash、Cloudflare cookie、Bearer token、RD token、magnet URI）→ 命中即 fail
6. 掃描**全部受追蹤文字檔**是否含 secret pattern（大小寫不敏感；無整檔豁免，
   已知測試 fixture 以完整字面量列入 allowlist）→ 命中即 fail
7. `Compress-Archive` 產 `release/JavDBMagnet_<version>_portable.zip`（zip root 為 `JavDBMagnet/`）
8. 算 SHA256（portable.zip / javdbmagnet.exe / sidecar.exe），寫入 `release/SHA256SUMS.txt`
9. 寫 release manifest 到 `release/release-manifest.json`（`"bundle": "portable-zip"`）
10. 最後列印所有 artifact 路徑

任何 audit / scan 失敗 → script exit 1。

> Code signing 尚未實作。設 `$env:SIGN="1"` 跑 script 會看到 placeholder 提示；要實際簽章需在 script 內串你的 `signtool.exe` / `osslsigncode`。
>
> 想直接用 Tauri bundler 出 MSI 做測試 → `npm run tauri:build`（仍依 `tauri.conf.json` 內 `bundle.targets`）。日常 release 不走這條。

### 測試

```powershell
# 在 repo root：
python -m pytest tests/ -q                   # Python（sidecar / RD client / 成效日誌）

cd app
npm run test                                 # Vitest（前端）
npm run check                                # svelte-check（型別，0 errors 0 warnings 才算過）

cd app/src-tauri
cargo test --lib                             # Rust 單元測試
```

> `cargo test --lib` 必須在 `app/src-tauri` 下跑——`Cargo.toml` 在那裡，不在 `app/`。
>
> **在 Linux 開發機上這條預設編不過**（keyring 的 `secret-service` 未啟用 runtime
> feature，且缺 Linux sidecar binary）。修法與逐步驗證見
> [`docs/platform/linux-support.md`](docs/platform/linux-support.md)；套用後為 81 passed。

### Repo 結構

```
.
├─ app/                   ← Tauri + Svelte 前端
│  ├─ src/                ← Svelte component + lib (scraper / rdSender / rdPriority / settingsValidation / ...)
│  ├─ src-tauri/          ← Rust 後端
│  │  ├─ src/
│  │  │  ├─ commands.rs       ← Tauri IPC commands
│  │  │  ├─ legacy_import.rs  ← M7a 舊資料匯入
│  │  │  ├─ secret_store.rs   ← keyring wrapper
│  │  │  ├─ pending.rs        ← pending_torrents.json
│  │  │  └─ ...
│  │  ├─ capabilities/
│  │  └─ tauri.conf.json
│  └─ package.json
├─ sidecar/               ← Python sidecar daemon（JavDB 抓取 + RD API）
│  └─ sidecar.py
├─ realdebrid.py          ← RD API client（被 sidecar import）
├─ javdb_scraper.py       ← JavDB HTTP + HTML 解析（純 library）
├─ app_logging.py         ← logging 初始化與 log 目錄解析
├─ rd_outcome_log.py      ← RD 送出成效日誌（rd_outcomes.jsonl）
├─ spikes/                ← 保留的歷史 spike notes + sidecar build pipeline（pyinstaller_sidecar / python_sidecar_protocol）
├─ scripts/
│  ├─ build-release.ps1   ← 一條命令 release pipeline
│  ├─ verify-windows-build.ps1 ← 建置前驗證（先跑這個）
│  └─ rd_log_report.py    ← 成效日誌分析報表
├─ tests/                 ← Python unittest
└─ docs/
   ├─ architecture/       ← 跨層契約（現行行為的權威來源）
   ├─ platform/           ← 平台移植記錄（linux-support.md）
   ├─ specs/              ← 各輪功能規格（歷史存檔）
   ├─ sessions/
   └─ troubleshooting/
```

---

## License

私人專案，未發布 license。

---

## 提醒

`cookies.txt` 含登入憑證，請勿分享 `%APPDATA%\JavDBMagnet`、不要把該目錄同步到雲端、不要 commit 整顆資料夾。
