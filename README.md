# JavDBMagnet

JavDB 磁力連結擷取 + Real-Debrid 直連產生工具（Windows 桌面版）。

- 從 JavDB 影片頁面**批次抓取**磁力連結
- **直接貼上 magnet**：已有連結時跳過 JavDB，直接送 Real-Debrid
- 篩選 / 排序 / 群組去重，一鍵送 RD
- **待處理清單**：RD 還在處理的 torrent 不卡住流程，可稍後重試
- 全部 RD 直連一鍵複製到剪貼簿（貼進 IDM / aria2 / 任何下載器）
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

JavDB 需要登入後的 cookie 才能看到磁力連結。

1. 用瀏覽器登入 [javdb.com](https://javdb.com)
2. 按 **F12** 開啟開發者工具 → **Network** → 重新整理頁面 → 點任一 request → **Request Headers** → 找到 `Cookie:` 整行
3. 複製整行內容（應包含 `_jdb_session`、`cf_clearance`、`locale` 等 cookie 名稱）
4. 在 app 內按「**JavDB Cookies**」展開 → 「打開資料目錄」
5. 在跳出的資料夾建立新檔 **`cookies.txt`**，貼上剛複製的內容
6. 回到 app 按「**重新整理**」，看到 `✓ 已找到 cookies.txt` 即可

cookies 路徑會是：`%APPDATA%\JavDBMagnet\cookies.txt`

> ⚠ **`cf_clearance` 約幾小時後過期**，看到 Cloudflare 阻擋時重新取一次即可。詳見 [troubleshooting/cloudflare.md](docs/troubleshooting/cloudflare.md)。

### 3. 試跑

把任一 JavDB 影片頁面 URL 貼到「**批次擷取**」textarea，按「開始擷取」。看到磁力出現在下方表格 = 整條鏈路（cookies → JavDB → 解析 → handle_id → UI）都通了。

---

## 資料位置

| 內容 | 路徑 |
|---|---|
| Settings | `%APPDATA%\JavDBMagnet\settings.json` |
| Cookies | `%APPDATA%\JavDBMagnet\cookies.txt` |
| Pending torrents | `%APPDATA%\JavDBMagnet\pending_torrents.json` |
| Logs（含 sidecar debug.log） | `%LOCALAPPDATA%\JavDBMagnet\logs\` |
| RD Token | Windows Credential Manager（**非檔案**） |

app 內「JavDB Cookies」區塊有「**打開資料目錄**」與「**打開 logs 目錄**」按鈕，不必手敲路徑。

### 不要 commit / 分享這些檔案

- `.env`、`.env.*`、`cookies.txt`：含登入憑證
- `pending_torrents.json`：含你曾經送過 RD 的 torrent id（可能透露你下載偏好）
- `logs/`：含 timestamped diagnostic 資料

Repo 的 `.gitignore` 已擋下以上路徑，但若你的工作目錄外另有備份 / 雲端同步，請手動排除。

---

## 從舊版 Python GUI 升級

若你有用過舊版 tkinter GUI（M1 時期），app 內「**匯入舊版資料**」區塊可以一鍵搬：

1. 展開「匯入舊版資料」
2. 路徑填舊 GUI 的資料夾（含 `.env` / `cookies.txt` / `pending_torrents.json`）
3. 按「**預覽**」確認偵測到的檔案
4. 按「**匯入**」

匯入規則（防止 token / magnet 落地的安全保證）：

- `.env` 內 `RD_API_TOKEN` → Windows Credential Manager（**不**寫入 settings.json）
- `.env` 其他設定（`RD_FILE_PICK`、`RD_MIN_SIZE_MB`、`RD_WAIT_TIMEOUT`、`RD_CACHE_WAIT`、`UI_SCALE`、`UI_THEME`）→ settings.json
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
| `cache_wait_seconds` | `15` | 等 RD 判定快取的秒數（最小 5） |
| `wait_timeout_seconds` | `300` | 整體 RD 處理超時（最小 30） |
| `theme` | `light` | `light` / `dark` |
| `scale` | `auto` | UI 縮放：`auto` 或 0.5–3.0；4K 螢幕建議 1.5–2.0 |

按「儲存設定」後立即推到 sidecar，**本次工作階段就生效**，不必重啟 app。

---

## 安全模型

| 規則 | 機制 |
|---|---|
| RD token 絕不寫純文字檔 | Windows Credential Manager（keyring crate），`settings.json` 的 `rd.api_token` 永遠空字串 |
| 完整 magnet 不外洩到 frontend / settings / pending JSON / log | sidecar 用 `handle_id` 引用；只在 Rust transient String（剪貼簿寫入時）與 RD HTTP body 短暫存在 |
| `pending_torrents.json` 不含 magnet 文字 | 由 Rust `entries_have_no_magnet_field` 單元測試守住 |
| `debug.log` 不含 BTIH hash | `realdebrid.py::_request` 對 `data["magnet"]` 永遠記 `<redacted>` |
| Clipboard 寫入集中在 Rust | frontend 不直接 import `tauri-plugin-clipboard-manager` |
| capability 最小化 | `capabilities/default.json` 只開 `core:default` |

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

```powershell
cd app
npm install
```

第一次跑 Rust 依賴會下載 + 編譯 ~5 分鐘。

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

`scripts/build-release.ps1` 會：

1. PyInstaller 打包 `sidecar.exe`
2. `npx tauri build --no-bundle`（包含 Vite 前端 build + cargo release build；
   `--no-bundle` 跳過 MSI/NSIS。走 Tauri CLI 是必要的，因為它會帶上
   `tauri/custom-protocol` feature 把 `dist/` 嵌進 binary；
   純 `cargo build --release` 不會帶這個 feature，產出的 exe 啟動時會
   試圖連 `localhost:1420`）
3. 在 `release/JavDBMagnet/` 暫存 `javdbmagnet.exe` + `sidecar.exe` + `README.txt`
4. Staging 白名單稽核（只允許上述 3 個檔；其他任何檔案 → fail）
5. 兩個 exe 內容掃 secret pattern（BTIH hash、Cloudflare cookie、Bearer token、RD token、magnet URI）→ 命中即 fail
6. 掃描本次變更的 source/docs 是否含 secret pattern
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
cd app
npm run test           # Vitest（前端）
npm run check          # svelte-check（型別）
cargo test --lib       # Rust 單元測試
# 在 repo root：
python -m unittest discover -s tests
```

### Repo 結構

```
.
├─ app/                   ← Tauri + Svelte 前端
│  ├─ src/                ← Svelte component + lib (scraper / rdSender / settingsValidation / ...)
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
├─ spikes/                ← 早期技術驗證（rust_fetch / rquest / pyinstaller_sidecar / tauri_sidecar_poc）
├─ scripts/
│  └─ build-release.ps1   ← 一條命令 release pipeline
├─ tests/                 ← Python unittest
└─ docs/
   ├─ architecture/
   ├─ sessions/
   └─ troubleshooting/
```

---

## License

私人專案，未發布 license。

---

## 提醒

`cookies.txt` 含登入憑證，請勿分享 `%APPDATA%\JavDBMagnet`、不要把該目錄同步到雲端、不要 commit 整顆資料夾。
