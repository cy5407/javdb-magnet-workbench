# JavDBMagnet

Windows 桌面工具：從 JavDB 影片頁批次擷取磁力連結，挑選後送到 Real-Debrid（RD），
取回 https 直連給下載器使用。

- 介面是 Tauri 2 + Svelte 5，後端是 Rust；JavDB 抓取與 RD API 由打包成
  `sidecar.exe` 的 Python 程式負責，兩者以 stdin/stdout 的 JSON-lines 溝通。
- 以 portable zip 發佈：不寫 Program Files、不建捷徑、不寫 installer registry。
- 目前版本 0.3.1（`app/package.json`、`app/src-tauri/tauri.conf.json`）。
- 私人專案，未附 license。

---

## 功能

| 分頁 | 做什麼 |
|---|---|
| 1. 擷取 Magnet | 「批次擷取」貼多個 JavDB 影片頁網址一次抓；已經有 magnet 時可「直接貼上」，略過 JavDB |
| 2. 挑選 Magnet | 每個影片頁一組；依關鍵字、高清、大小篩選並排序，「每組只留」可每組只保留一筆（含「RD 命中優先」），「只勾選 RD 優先候選」一鍵勾選推薦項 |
| 3. RD 下載連結 | 送 RD、顯示直連；可一次複製全部直連，也可在每列單獨複製；RD 還沒處理完的進「待處理」清單，稍後重試 |
| 4. 設定 | RD token、JavDB cookies、應用程式設定、儲存位置、匯入舊版資料 |

另外：

- 同一個 BTIH 不會重複送 RD（避免重複扣額度），送出前也會依 `handle_id` 再去重一次。
- 每次送出與重試的結果寫進成效日誌 `rd_outcomes.jsonl`，可用 `scripts/rd_log_report.py`
  檢驗「RD 命中優先」規則是否真的有效（見[成效日誌](#rd-命中優先與成效日誌)）。

---

## 架構

```
┌──────────────────────────────┐
│ Svelte 前端（WebView2）       │  app/src/
│ 畫面狀態；磁力以 handle_id 引用 │
└──────────────┬───────────────┘
               │ Tauri IPC（invoke）
┌──────────────▼───────────────┐
│ Rust 後端                     │  app/src-tauri/src/
│ 設定、pending、剪貼簿、        │  settings.rs / pending.rs / commands.rs
│ Credential Manager、sidecar 管理│  secret_store.rs / cookie_store.rs / sidecar_manager.rs
└──────────────┬───────────────┘
               │ stdin/stdout JSON-lines（tauri-plugin-shell sidecar）
┌──────────────▼───────────────┐
│ Python sidecar（sidecar.exe） │  sidecar/sidecar.py
│ JavDB 抓取、RD API、成效日誌   │  javdb_scraper.py / realdebrid.py / rd_outcome_log.py
└──────────────────────────────┘
```

### Sidecar JSON-lines 協定

- 每行一個 UTF-8 JSON 物件。請求以 `cmd` 指定命令，回應帶 `ok`、`request_id`；
  失敗時帶 `error: {code, message, internal}`。
- 指令：`hello`、`handshake`、`ping`、`fetch_javdb`、`resolve_magnet(s)`、
  `forget_magnets`、`register_magnets`、`update_settings`、`set_cookies`、`cancel`、
  `shutdown`、`rd_user`、`rd_set_token`、`rd_send_magnet`、`rd_check_pending`。
- stderr 只放診斷訊息；cookie、RD token、完整 magnet 與完整 traceback 都不會
  出現在 stdout／stderr。未預期的例外在 dispatch 邊界轉成遮蔽過的錯誤回應。
- 完整 magnet 存在 sidecar 的 handle 表；擷取結果回給前端的是 `handle_id`，Rust 只在
  寫入剪貼簿時短暫取用完整 magnet。

協定細節以 [`docs/architecture/contracts/sidecar-runtime.md`](docs/architecture/contracts/sidecar-runtime.md)
為準；各層契約見 [`docs/architecture/`](docs/architecture/)。

### JavDB 連線

`javdb_scraper.py` 優先用 `curl_cffi` 模擬 Chrome 的 TLS 指紋，裝不到時退回
`requests`。JavDB 需要登入後的 cookie（含 Cloudflare 的 `cf_clearance`）才看得到磁力。

---

## 取得與使用

### 系統需求

- Windows 10 1809 以上或 Windows 11
- WebView2 Runtime（Windows 11 內建；portable zip 不會自動安裝）
- Real-Debrid 帳號（只抓磁力不送 RD 則不需要）
- 約 30 MB 磁碟空間（`javdbmagnet.exe` 約 5 MB、`sidecar.exe` 約 25 MB）

### 下載

[GitHub Releases](https://github.com/cy5407/javdb-magnet-workbench/releases) 目前最新的是
**v0.3.0**，0.3.1 尚未發佈到 Releases。要用 0.3.1 請照[建置與發佈](#建置與發佈)自行建置。
（repo 根目錄的 `javdbmagnet.exe`／`sidecar.exe` 是上一次發佈建置的快照，對應版本記在
[`docs/platform/windows-build.md`](docs/platform/windows-build.md)；程式碼之後有改動時不代表最新。）

1. 下載 `JavDBMagnet_<version>_portable.zip`，解壓到任意資料夾。
2. 雙擊資料夾內的 `javdbmagnet.exe`。
3. `sidecar.exe` 必須和 `javdbmagnet.exe` 放在同一個資料夾，不能刪或搬走。

exe 沒有 code signing，第一次執行可能跳 SmartScreen 警告。先用 release 附的
`SHA256SUMS.txt` 比對，再按「更多資訊」→「仍要執行」：

```powershell
Get-FileHash -Algorithm SHA256 .\JavDBMagnet_*_portable.zip
Get-FileHash -Algorithm SHA256 .\JavDBMagnet\javdbmagnet.exe
Get-FileHash -Algorithm SHA256 .\JavDBMagnet\sidecar.exe
```

### 第一次設定

都在「4. 設定」分頁。

**Real-Debrid Token**

1. 到 <https://real-debrid.com/apitoken> 複製 token。
2. 在「Real-Debrid Token」區塊貼上，按「測試連線」確認帳號資訊，再按「儲存」。

token 存在 Windows Credential Manager，不會寫進 `settings.json` 或任何純文字檔。

**JavDB Cookies**（兩種方式擇一，都會加密存進 Credential Manager）

- **方式 A：直接貼上（建議）**——按「貼上新 cookies」，貼上瀏覽器 DevTools →
  Network → 任一 JavDB 請求的 `Cookie:` 標頭值（不含 `Cookie: ` 前綴），按
  「儲存到認證管理員」。看到「cookies 已加密儲存」即生效，不必重啟。
- **方式 B：編輯範本檔**——按「建立 cookies.txt 範本」，再按「打開資料目錄」用記事本
  編輯 `cookies.txt`（照檔內說明貼在最後一行，存成 UTF-8），回 app 按
  「重新整理 / 套用變更」。內容會加密寫進 Credential Manager，明文檔隨即刪除。

`cf_clearance` 幾小時就會過期，遇到 Cloudflare 阻擋時用方式 A 重貼最快。
見 [`docs/troubleshooting/cloudflare.md`](docs/troubleshooting/cloudflare.md)。

**試跑**：在「1. 擷取 Magnet」的「批次擷取」貼一個 JavDB 影片頁網址，按「開始擷取」，
該列出現磁力數量即代表 cookies → JavDB → 解析整條路通了。

### 應用程式設定

「4. 設定」→「應用程式設定」，按「儲存設定」後立即推給 sidecar，不必重啟。

| 欄位 | 預設 | 說明 |
|---|---|---|
| `file_pick` | `smart` | RD 端選檔策略：`smart` / `largest` / `video` / `all` |
| `min_size_mb` | `500` | 小於此值的影片視為廣告略過（0–1,000,000） |
| `cache_wait_seconds` | `15` | 等 RD 判定是否已快取的秒數（5–300），逾時就進待處理清單 |
| `theme` | `light` | `light` / `dark` |
| `scale` | `auto` | UI 縮放：`auto` 或 0.5–3.0；4K 螢幕建議 1.5–2.0 |

### 資料位置

| 內容 | 位置 |
|---|---|
| 設定 | `%APPDATA%\JavDBMagnet\settings.json` |
| 待處理清單 | `%APPDATA%\JavDBMagnet\pending_torrents.json`（不含 magnet） |
| cookies 範本（暫存） | `%APPDATA%\JavDBMagnet\cookies.txt`（套用後自動刪除） |
| 日誌 | `%LOCALAPPDATA%\JavDBMagnet\logs\`（`debug.log`、`rd_outcomes.jsonl`） |
| RD token | Windows Credential Manager，target `RD_API_TOKEN.JavDBMagnet` |
| JavDB cookies | Windows Credential Manager，target `JAVDB_COOKIES.JavDBMagnet` |

「4. 設定」的「儲存位置」區塊會列出實際路徑，也有「打開資料目錄」「打開 logs 目錄」按鈕。

不要分享或同步到雲端：`cookies.txt`（登入憑證）、`pending_torrents.json`（送過的
torrent id）、`logs/rd_outcomes.jsonl`（含番號與檔名，等於觀看紀錄）。

### 移除

刪掉解壓出來的資料夾即移除程式。連個人資料一起清除：

```powershell
Remove-Item "$env:APPDATA\JavDBMagnet" -Recurse -Force
Remove-Item "$env:LOCALAPPDATA\JavDBMagnet" -Recurse -Force
cmdkey /delete:RD_API_TOKEN.JavDBMagnet
cmdkey /delete:JAVDB_COOKIES.JavDBMagnet
```

### 從舊版 Python GUI 匯入

「4. 設定」→「匯入舊版資料」，填入舊版 tkinter GUI 的資料夾，按「預覽」確認後再匯入：

- `.env` 的 `RD_API_TOKEN` → Credential Manager；`RD_FILE_PICK`、`RD_MIN_SIZE_MB`、
  `RD_CACHE_WAIT`、`UI_SCALE`、`UI_THEME` → `settings.json`。`RD_WAIT_TIMEOUT` 不再使用，
  會略過並提示。
- `cookies.txt` → 複製到資料目錄，之後套用時加密搬進 Credential Manager。
- `pending_torrents.json` → 匯入時移除 magnet 欄位，依 torrent id 去重。

舊檔案不會被刪除。

---

## RD 命中優先與成效日誌

別人已經上傳過的磁力，RD 會立刻回直連；沒有的就得等 RD 下載。RD 已移除查詢快取的
`instantAvailability` 端點，所以 app 在送出前用本地規則**推測**命中機率：

轉載站前綴（`hhd800.com@`、`489155.com@`）＋高清 ＞ 最早上傳的高清 ＞ 全組都不是高清
（標 ⚠、不自動勾選）。批次含低機率項目時，送出前會先顯示摘要，可選「只送高機率」。

規則準不準用日誌驗證：

```powershell
python scripts\rd_log_report.py
python scripts\rd_log_report.py --log <log 目錄內的 rd_outcomes.jsonl> --threshold-ms 5000 --min-n 10
```

- 報表把結果分成「秒回」「慢但完成」「沒人有」三類；`--threshold-ms` 是秒回的分界。
- `--log` 只接受 log 目錄（`JAVDB_LOG_DIR` 或 `%LOCALAPPDATA%\JavDBMagnet\logs`）內的路徑。
- 預設只計每個磁力的第一次送出（第二次一定命中，因為是自己放進去的），
  `--include-repeats` 可保留。只送推薦項目會缺少對照組，報表會提出警告。

設環境變數 `JAVDB_RD_LOG=0` 可完全停用成效日誌（`debug.log` 不受影響）。

---

## 安全設計

| 規則 | 做法 |
|---|---|
| RD token、JavDB cookies 不落純文字 | 存 Windows Credential Manager（`keyring` crate）；`settings.json` 的 `rd.api_token` 永遠是空字串 |
| 完整 magnet 不存進設定檔、pending 檔、日誌，也不回傳給前端 | sidecar 以 `handle_id` 代替；`realdebrid.py` 記錄請求時把 magnet 記成 `<redacted>`；日誌只保留 BTIH 前 8 碼當關聯鍵 |
| `pending_torrents.json` 不含 magnet | Rust 單元測試 `entries_have_no_magnet_field` |
| 日誌不含完整 magnet／BTIH | `rd_outcome_log.py` 寫出前逐行過濾；`tests/test_rd_outcome_log_e2e.py` 實際掃描 |
| 剪貼簿只由 Rust 寫入 | 前端不直接用 clipboard plugin |
| Tauri capability 最小化 | `capabilities/default.json` 只開 `core:default`，加上只允許開啟 `https://real-debrid.com/apitoken` 的 `shell:allow-open` |
| 出貨物不夾帶機密 | 打包時掃描兩個 exe 與所有 tracked 文字檔（見下節） |

BTIH 前 8 碼仍可能在公開 torrent 索引上比對到，公開貼 log 前請留意。

---

## 開發

### 需求

- Windows 10/11（主要開發與發佈平台）
- Python 3.12（CI 用 3.12）
- Node 20 以上與 npm
- Rust stable + MSVC toolchain
- PowerShell（`npm run release` 走 Windows PowerShell 5.1；驗證腳本會同時用 `powershell` 和 `pwsh` 跑機密掃描紅測）

### 安裝依賴

```powershell
# repo 根目錄
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-sidecar.txt -r requirements-ci.txt

cd app
npm ci
```

- `requirements-sidecar.txt`：sidecar 執行與 PyInstaller 打包的固定版本。
  `build_sidecar.py` 打包前會核對已安裝版本，不符就直接失敗。
- `requirements-ci.txt`：pytest 與 coverage。
- `npm run sidecar:build` 用的是 PATH 上的 `python`，所以要先啟用 venv。

### 開發模式

```powershell
cd app
npm run tauri:dev
```

會先打包 sidecar，再啟動 Vite（`http://localhost:1420`）與 Tauri 視窗。前端修改會自動
重新載入；改 Python 或 Rust 要停掉重跑。

### 測試

```powershell
# repo 根目錄：Python（sidecar、RD client、成效日誌、腳本）
python -m pytest tests/ -q

cd app
npx vitest run          # 前端單元測試（等同 npm run test）
npm run check           # svelte-check，要求 0 errors 0 warnings
npm run sidecar:build   # cargo 測試前需要 binaries\ 裡有 sidecar

cd src-tauri
cargo test --no-fail-fast --tests   # Rust lib 單元測試＋ tests\ 整合測試
```

- `cargo` 要在 `app\src-tauri` 執行，`Cargo.toml` 在那裡。
- `app\src-tauri\binaries\` 不進 git；沒先建 sidecar，Tauri 的 build script 會報
  `binaries/sidecar-x86_64-pc-windows-msvc.exe doesn't exist`。
- 改到 `.agents/wiki/` 引用的程式碼時，跑 `python scripts\verify_wiki_citations.py` 檢查引用。
- 各 gate 的目前 baseline 記在 [`CLAUDE.md`](CLAUDE.md)。

### CI

`.github/workflows/sonarcloud.yml` 在 push 到 master 與 PR 時執行：前端
`npm run test:coverage`、Python `coverage run -m pytest`，結果送 SonarCloud。
CI 跑在 Ubuntu，不建置 Windows 產物、不跑 cargo test。

### Linux

Linux 上可以跑 pytest、vitest、svelte-check 與 Rust 測試，但不能出正式 build（沒有
Linux sidecar、打包腳本只支援 Windows）。Rust 測試要略過 sidecar 檢查，且需要可用的
D-Bus Secret Service：

```bash
cd app/src-tauri
TAURI_CONFIG='{"bundle":{"externalBin":[]}}' cargo test --no-fail-fast --tests
```

細節見 [`docs/platform/linux-support.md`](docs/platform/linux-support.md)。

---

## 建置與發佈

兩支腳本，先驗證再打包：

```powershell
pwsh -File scripts\verify-windows-build.ps1
pwsh -File scripts\build-release.ps1      # 或 cd app; npm run release
```

**`scripts\verify-windows-build.ps1`**（不打包）：檢查 Python／Node／Rust／venv →
pytest、vitest、svelte-check → `cargo test --no-fail-fast --tests` → 機密掃描紅測 →
重建 sidecar 並實際用 JSON-lines 協定跟它對話。`-SkipSlow` 略過 cargo 與 sidecar 重建，
但不略過機密掃描紅測。

**`scripts\build-release.ps1`**：

1. 先跑 `scripts\test-release-scan.ps1`（機密掃描紅測），失敗就中止。
2. 要求工作樹乾淨（含 untracked，並拒絕 assume-unchanged／skip-worktree），建完再驗一次；
   因為 manifest 記錄的是 `git rev-parse HEAD`。
3. PyInstaller 打包 sidecar → `npx tauri build --no-bundle` 建出 `javdbmagnet.exe`
   （必須走 Tauri CLI，前端才會嵌進 exe）。
4. 在 `release\JavDBMagnet\` 放 `javdbmagnet.exe`、`sidecar.exe`、`README.txt`，
   資料夾內出現其他檔案即失敗。
5. 掃描兩個 exe 與所有 tracked 文字檔有無 BTIH、magnet、Cloudflare／JavDB cookie、
   Authorization 標頭與 RD token 設定值；已知測試假資料以完整字面值列在
   `scripts\release-scan-allowlist.txt`。
6. 產出到 `release\`（不進 git）：

| 檔案 | 內容 |
|---|---|
| `JavDBMagnet_<version>_portable.zip` | zip 根目錄為 `JavDBMagnet\` |
| `SHA256SUMS.txt` | zip 與兩個 exe 的 SHA256 |
| `release-manifest.json` | 版本、`git_commit`、建置時間、各產物 SHA256 與大小、掃描統計、是否簽章 |

任一關失敗即 exit 1。版本號取自 `app\package.json`。建置前先關掉執行中的
`javdbmagnet.exe`／`sidecar.exe`，否則 Windows 檔案鎖會讓 staging 清理失敗。

其他入口（在 `app\` 執行）：

| 命令 | 用途 |
|---|---|
| `npm run release:test` | 只跑機密掃描紅測 |
| `npm run release:audit` | 只掃 tracked 原始碼，不建置 |
| `npm run tauri:build` | 用 Tauri bundler 建置（`bundle.targets` 為空，日常發佈不走這條） |

尚未實作 code signing；設 `$env:SIGN="1"` 只會印出提示，manifest 記錄 `performed: false`。
Windows 11 的 Smart App Control 可能擋掉 cargo 編出的 build script，排除方式見
[`docs/platform/windows-build.md`](docs/platform/windows-build.md)。

---

## 目錄結構

```
.
├─ app/                        Tauri + Svelte
│  ├─ src/                     Svelte 介面（App.svelte）與 lib/（scraper、rdSender、rdPriority…）
│  └─ src-tauri/               Rust 後端
│     ├─ src/                  commands、settings、pending、secret/cookie store、sidecar_manager、legacy_import
│     ├─ tests/                整合測試（sidecar_command.rs）
│     ├─ capabilities/         Tauri 權限
│     └─ tauri.conf.json
├─ sidecar/sidecar.py          JSON-lines daemon 入口
├─ javdb_scraper.py            JavDB 抓取與 HTML 解析
├─ realdebrid.py               RD API client
├─ rd_outcome_log.py           成效日誌
├─ app_logging.py              日誌初始化與目錄解析
├─ spikes/pyinstaller_sidecar/ sidecar 打包腳本（build_sidecar.py）
├─ scripts/                    build-release / verify-windows-build / test-release-scan / rd_log_report
├─ tests/                      Python 測試（pytest）
├─ legacy/                     已退役的 tkinter GUI，只供參考
├─ vendor/                     wayland-scanner 安全修補（Cargo [patch]）
└─ docs/
   ├─ architecture/            跨層契約（現行行為的權威來源）
   ├─ platform/                Windows 建置、Linux 支援
   ├─ troubleshooting/         疑難排解
   └─ specs/ sessions/ reviews/ 歷史紀錄
```

---

## 疑難排解

| 症狀 | 文件 |
|---|---|
| 抓 JavDB 失敗、被 Cloudflare 擋 | [`cloudflare.md`](docs/troubleshooting/cloudflare.md) |
| RD token 顯示 invalid／401 | [`rd-token.md`](docs/troubleshooting/rd-token.md) |
| 送 RD 後沒有直連、全部進待處理 | [`no-pending-links.md`](docs/troubleshooting/no-pending-links.md) |
| 確認 log 沒洩漏 magnet | [`log-redaction-verification.md`](docs/troubleshooting/log-redaction-verification.md) |
