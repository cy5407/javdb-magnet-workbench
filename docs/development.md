# 開發者文件

給要修改、測試或建置 JavDBMagnet 的人。一般使用說明見 [README](../README.md)。

---

## 架構

- 介面是 Tauri 2 + Svelte 5，後端是 Rust；JavDB 抓取與 RD API 由打包成
  `sidecar.exe` 的 Python 程式負責，兩者以 stdin/stdout 的 JSON-lines 溝通。
- 以 portable zip 發佈：不寫 Program Files、不建捷徑、不寫 installer registry。
- 版本號在 `app/package.json`、`app/src-tauri/tauri.conf.json`。

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

協定細節以 [`architecture/contracts/sidecar-runtime.md`](architecture/contracts/sidecar-runtime.md)
為準；各層契約見 [`architecture/`](architecture/)。

### JavDB 連線

`javdb_scraper.py` 優先用 `curl_cffi` 模擬 Chrome 的 TLS 指紋，裝不到時退回
`requests`。JavDB 需要登入後的 cookie（含 Cloudflare 的 `cf_clearance`）才看得到磁力。

### 去重

同一個 BTIH 不會重複送 RD（避免重複扣額度），送出前也會依 `handle_id` 再去重一次。

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
| 出貨物不夾帶機密 | 打包時掃描兩個 exe 與所有 tracked 文字檔（見[建置與發佈](#建置與發佈)） |

BTIH 前 8 碼仍可能在公開 torrent 索引上比對到，公開貼 log 前請留意。

---

## 成效日誌報表

每次送出與重試的結果寫進 `rd_outcomes.jsonl`，用 `scripts/rd_log_report.py` 檢驗
「RD 命中優先」規則是否有效：

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

## 舊版匯入對照

「匯入舊版資料」讀舊版 tkinter GUI 的資料夾，舊檔案不會被刪除：

- `.env` 的 `RD_API_TOKEN` → Credential Manager；`RD_FILE_PICK`、`RD_MIN_SIZE_MB`、
  `RD_CACHE_WAIT`、`UI_SCALE`、`UI_THEME` → `settings.json`。`RD_WAIT_TIMEOUT` 不再使用，
  會略過並提示。
- `cookies.txt` → 複製到資料目錄，之後套用時加密搬進 Credential Manager。
- `pending_torrents.json` → 匯入時移除 magnet 欄位，依 torrent id 去重。

`pending_torrents.json` 平常也不含 magnet；`cookies.txt` 只是暫存，套用後自動刪除。

---

## 開發環境

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
- 不要把 LGPL 的 `chardet` 加回來：requests 只要匯入得到它就會優先使用，會把 LGPL
  模組打包進單一檔案的 `sidecar.exe`。`build_sidecar.py` 已用 `--exclude-module chardet`
  排除，requests 會改用 charset-normalizer（MIT）。
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
- 各 gate 的目前 baseline 記在 [`CLAUDE.md`](../CLAUDE.md)。

### CI

`.github/workflows/sonarcloud.yml` 在 push 到 master 與 PR 時執行：前端
`npm run test:coverage`、Python `coverage run -m pytest`，結果送 SonarCloud。
CI 跑在 Ubuntu，不建置 Windows 產物、不跑 cargo test，也不跑機密掃描——
那只在 Windows 本機的 `verify-windows-build.ps1` 執行。

### Linux

Linux 上可以跑 pytest、vitest、svelte-check 與 Rust 測試，但不能出正式 build（沒有
Linux sidecar、打包腳本只支援 Windows）。Rust 測試要略過 sidecar 檢查，且需要可用的
D-Bus Secret Service：

```bash
cd app/src-tauri
TAURI_CONFIG='{"bundle":{"externalBin":[]}}' cargo test --no-fail-fast --tests
```

細節見 [`platform/linux-support.md`](platform/linux-support.md)。

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
4. 在 `release\JavDBMagnet\` 放 `javdbmagnet.exe`、`sidecar.exe`、`README.txt`、
   `LICENSE.txt`（repo 根目錄 `LICENSE` 的副本）與 `THIRD_PARTY_NOTICES.txt`，
   資料夾內出現其他檔案即失敗。第三方聲明由 `scripts\gen_third_party_notices.py` 產生，
   收錄 sidecar 的 Python 執行期依賴、Windows target 的 Rust 一般依賴，以及嵌進前端
   bundle 的 npm 套件，授權全文從各套件自己附的檔案讀出。
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
腳本假設 Rust 產物在預設的 `app\src-tauri\target\`，不要另外設 `CARGO_TARGET_DIR`。

其他入口（在 `app\` 執行）：

| 命令 | 用途 |
|---|---|
| `npm run release:test` | 只跑機密掃描紅測 |
| `npm run release:audit` | 只掃 tracked 原始碼，不建置 |
| `npm run tauri:build` | 用 Tauri bundler 建置（`bundle.targets` 為空，日常發佈不走這條） |

尚未實作 code signing；設 `$env:SIGN="1"` 只會印出提示，manifest 記錄 `performed: false`。
Windows 11 的 Smart App Control 可能擋掉 cargo 編出的 build script，排除方式見
[`platform/windows-build.md`](platform/windows-build.md)。

repo 根目錄的 `javdbmagnet.exe`／`sidecar.exe` 是上一次發佈建置的快照，對應版本記在
[`platform/windows-build.md`](platform/windows-build.md)；程式碼之後有改動時不代表最新。

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
