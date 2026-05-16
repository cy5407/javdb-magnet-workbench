# 安全性檢查草稿（JavDBMagnet）

> 本檔為靜態 (read-only) 安全審查初稿，**未執行任何修改原始碼 / 設定 / 依賴的動作**。
> 審查日期：2026-05-16
> 審查人：Claude (Opus 4.7)
> 對應 commit：`e086859` (master)

---

## 1. 檢查範圍

採用純靜態閱讀方式（無 `git diff`、無 sandbox 執行、無 deps 安裝）覆蓋以下層面：

| 層 | 主要檔案 |
|---|---|
| Python sidecar daemon | `sidecar/sidecar.py`、`realdebrid.py`、`javdb_scraper.py`、`app_logging.py` |
| Rust Tauri 後端 | `app/src-tauri/src/{lib,commands,sidecar_manager,secret_store,legacy_import,pending,settings,path_manager}.rs` |
| 前端 (Svelte 5) | `app/src/App.svelte`、`app/src/lib/{scraper,rdSender,settingsValidation,magnetUtils}.ts` |
| Tauri 設定/能力 | `app/src-tauri/tauri.conf.json`、`app/src-tauri/capabilities/default.json` |
| 建置 / 發佈 | `scripts/build-release.ps1`、`spikes/pyinstaller_sidecar/build_sidecar.py`、`app/package.json` |
| CI / 供應鏈 | `.github/workflows/sonarcloud.yml`、`requirements-sidecar.txt`、`requirements-ci.txt`、`sonar-project.properties` |
| Repo 狀態 | `.gitignore`、`.env.example` (對比 `.env`、`cookies.txt` 是否曾被追蹤) |

範圍包含但**不修改**：機密外洩、危險命令、路徑 traversal、不安全網路請求、弱隨機/弱加密、輸入驗證、CI/workflow 供應鏈。

不在此次範圍：滲透測試、執行期動態分析、第三方套件 CVE 比對、Rust unsafe 區段內存安全、Tauri runtime CVE。

---

## 2. 風險等級定義

| 等級 | 涵義 |
|---|---|
| **Critical** | 已存在可被遠端或本地非授權者立刻利用的弱點 |
| **High** | 在合理威脅模型下能造成機密外洩 / 權限提升 / 持續性影響 |
| **Medium** | 條件式利用、需與其他弱點串接，或實作上偏離 best practice |
| **Low** | 建議性硬化、深度防禦、可降低未來迴歸機率 |
| **Info** | 已正確處理的觀察，記錄供 Codex 確認 |

---

## 3. 發現清單

### F-01 [Medium] `fetch_javdb` 僅檢查 `https://` 字首，未限制網域，可能讓 JavDB cookies 外洩至任意 HTTPS 主機

**證據**
- `sidecar/sidecar.py:259-269`（`cmd_fetch_javdb` 只檢查 `url.startswith("https://")`）
- `javdb_scraper.py:78-79`（`session.get(url, cookies=cookies, timeout=30)` 直接把 cookies dict 帶到任意 URL）
- `sidecar/sidecar.py:106-117`（`parse_cookie_string` 產出無 domain 屬性的純 dict）

**說明**
sidecar 將 `state.cookies`（包含 `_jdb_session`、`cf_clearance`）以 `cookies=` 參數傳給 `requests.Session.get`。當 `cookies` 是 dict 時，requests 不會做網域過濾——所有 cookie 都會跟著任何 URL 一起送出。
雖然前端在 `app/src/lib/scraper.ts:108` 只允許 `https?://` 開頭的字串入列，並無 javdb 網域強制；而後端只看 `https://` 字首。若使用者貼入 `https://attacker.example/`，session cookie 會直接外洩。

**威脅模型**
單機桌面 app、URL 來源是本機使用者，攻擊面有限。但：
1. 若任何路徑被攻擊者誘導（釣魚連結、剪貼簿污染、未來自動匯入）即可竊取 Cloudflare clearance + JavDB session。
2. 此屬於 CWE-200 / CWE-540 的 cookie scope leak。

**建議修法**（不要在本輪變更）
- 在 `sidecar/sidecar.py` 的 URL 驗證再加上 `urlparse(url).hostname` 比對允許清單（`javdb.com` 及其常見 mirror 子網域）。
- 或改用 `requests.cookies.RequestsCookieJar`，明確指定 `domain="javdb.com"`，讓 requests 自己依 host 決定是否附帶。

---

### F-02 [Medium] Tauri WebView 未設定 CSP（`tauri.conf.json` `csp: null`）

**證據**
- `app/src-tauri/tauri.conf.json:23-25`
  ```
  "security": { "csp": null }
  ```

**說明**
前端目前以 Svelte 預設轉義輸出，並未使用 `{@html ...}`、`eval`、`Function()`（已 grep 確認），短期內無立即可利用的 XSS。但：
- 若未來新增富文字渲染或第三方 widget，缺少 CSP 將失去深度防禦。
- 一旦發生 XSS，前端可透過 `invoke("copy_magnet", …)`、`invoke("rd_save_token", …)` 等命令操作 OS clipboard 與 keyring，影響面非平凡。

**建議修法**
- 評估設置 `csp: "default-src 'self'; connect-src 'self' ipc: https://ipc.localhost"`（Tauri 2 預設模板）；至少在 production build 啟用。

---

### F-03 [Medium] `cookies.txt` 以明文落地於 `%APPDATA%\JavDBMagnet\`

**證據**
- `app/src-tauri/src/secret_store.rs:14-15`（註解明確表示 cookies 暫時仍為明文，DPAPI 移轉留待 M6/M7）
- `app/src-tauri/src/commands.rs:867-907`（`get_cookies_status` 只回 metadata，不讀檔內容——這部分是好的）

**說明**
RD API token 已遷到 Windows Credential Manager（`secret_store.rs:17-18` 使用 keyring `JavDBMagnet/RD_API_TOKEN`），但 JavDB cookies（含 cf_clearance、_jdb_session）仍是明文檔。在多使用者機器、雲端同步資料夾（OneDrive 重新導向 `%APPDATA%`）、或備份洩漏情境下會直接外流。

**建議修法**
- 將 cookies.txt 內容透過 DPAPI（`CryptProtectData`）封裝後落地；或同樣以 keyring 存放（`SERVICE=JavDBMagnet`, `ACCOUNT=JAVDB_COOKIES`）。
- 至少於 README / cookies 範本中提醒不要同步雲端（目前 `commands.rs:917` 已含「勿同步雲端」字樣，good）。

---

### F-04 [Low] `rd_set_token` / `rd_save_token` 路徑未驗證 token 字串格式或長度

**證據**
- `sidecar/sidecar.py:518-528`（`cmd_rd_set_token` 只檢查型別是 `str`，未限制長度/字元集）
- `app/src-tauri/src/commands.rs:314-332`（`rd_save_token` 透傳到 keyring，未驗證）

**說明**
RD API token 為 52 字元 alnum，目前實作把任意字串吃下並寫進 keyring。理論上不致命，但若使用者誤貼入超長字串（例如整段 JSON 或一頁 HTML）會被存到 OS credential，後續 RD 端 401。建議加 length cap（例如 256）。

**建議修法**
- Rust 側在 `commands.rs:314` 接收後做 `token.len() < 256 && token.chars().all(|c| c.is_ascii_alphanumeric())` 檢查。
- 失敗時 `Err("rd_token_format_invalid")`。

---

### F-05 [Low] `parse_cookie_string` 對空白與空鍵未嚴格驗證

**證據**
- `sidecar/sidecar.py:106-117`

**說明**
分隔僅靠 `;` 與第一個 `=`，未檢查 key/value 是否含 CR/LF 或 0x00。若 cookies.txt 來源被外部寫入畸形內容，可能造成日後 HTTP header injection 風險（目前 `requests` 自身會擋掉 `\r\n`，但這屬深度防禦）。

**建議修法**
- 解析時把含 CR/LF 的 pair 丟棄或回 `bad_request`。

---

### F-06 [Low] `load_env`（Python 端）未對 dotenv 行做基本健全度檢查

**證據**
- `realdebrid.py:20-33`（`load_env`）

**說明**
此函式在 Tauri 流程中被 sidecar 跳過（M5 已改走 keyring + handshake），但 `load_env` 仍存在於模組裡，且會把含 `=` 的任意字串視為 KV。如果未來有路徑誤用此函式並餵入攻擊者控制檔案，可能造成設定汙染。低風險，但建議與 `legacy_import::parse_env` 對齊（whitelist 鍵名）。

**建議修法**
- 在 `realdebrid.py:20` 上方加註解標明僅供 M0 legacy 用，新代碼不要呼叫；或直接刪除。

---

### F-07 [Info] `apply_legacy_import` 路徑驗證合理，未見 path traversal

**證據**
- `app/src-tauri/src/commands.rs:656-674`（`validate_legacy_source` 拒絕空字串、非目錄、與 data_dir 同路徑）
- `app/src-tauri/src/legacy_import.rs:348-395`（`preview` 只在固定子檔名 `.env / cookies.txt / pending_torrents.json` 上 `source_dir.join(...)`）

**說明**
所有讀檔皆以固定子檔名 `source_dir.join(LEGACY_*_FILE)`，使用者無法注入 `..`；canonicalize 比對也避免「source == data_dir」自我覆蓋。**建議 Codex 二次確認**：跨平台 (Windows symlink) 是否仍能繞過 canonicalize 等價判斷。

---

### F-08 [Info] `pending_torrents.json` 寫入採 tmp + rename 原子寫，且保證不含 magnet 文字

**證據**
- `app/src-tauri/src/pending.rs:100-116`（atomic write）
- `app/src-tauri/src/pending.rs:241-249`（單元測試確保 `magnet:` 字首與 `"magnet"` 欄位皆不存在）
- `app/src-tauri/src/legacy_import.rs:212-273`（`sanitize_pending_entry` 以 allowlist 過濾遷移欄位）

**說明**
良好實作，已將安全不變式（無 magnet、無 token）以單元測試守住。維持現狀即可。

---

### F-09 [Info] RD bearer token 不會出現在日誌

**證據**
- `realdebrid.py:44-46`（token 只放在 `self.session.headers["Authorization"]`）
- `realdebrid.py:50, 66-79`（`_redact_log_kwargs` 將 `magnet` 欄位遮蔽；Authorization header 並未透過 kwargs 流入）
- `app_logging.py:137-138`（`urllib3` / `requests` logger 強制 WARNING，避免底層把 Authorization 印出）

**說明**
與規格一致，未發現 token 透過 stderr / log 外洩的路徑。

---

### F-10 [Info] `randomDelayMs` 使用 `crypto.getRandomValues`，非為加密但已避開弱隨機 Sonar 警告

**證據**
- `app/src/lib/scraper.ts:34-51`

**說明**
雖然是反速率限制 jitter，使用 Web Crypto 為深度防禦合理選擇。Python 端的 `time.sleep(5.0)` 退避為固定值非隨機（`realdebrid.py:128`），不涉密。OK。

---

### F-11 [Info] 沒有 `subprocess(shell=True)` 或 OS Command Injection 風險

**證據**
- `spikes/pyinstaller_sidecar/build_sidecar.py:103-126`（`subprocess.check_call(cmd, cwd=REPO_ROOT)`，`cmd` 為靜態 list，無 user input）
- `app/src-tauri/src/commands.rs:986-1009`（`open_in_explorer` 用 `Command::new("explorer.exe").arg(p.as_os_str())`，path 來自 Rust state，不接 user string）
- `scripts/build-release.ps1`：所有 native exe 呼叫透過 `& <exe>` 加靜態旗標，無 `Invoke-Expression`、無動態字串拼接。

**說明**
未發現 shell injection 路徑。

---

### F-12 [Info] CI workflow 已 pin 第三方 actions 至 commit SHA、deps 用內嵌固定版號

**證據**
- `.github/workflows/sonarcloud.yml:14`（`actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5`）
- `:19, :27, :64`（`setup-node`、`setup-python`、`sonarqube-scan-action` 同樣 SHA-pinned，附 `# vX` 註解）
- `:33`（`npm ci --ignore-scripts`，已關閉 npm postinstall script）
- `:38-52`（pip install 明確列出每個套件 `name==version`，非 `-r requirements.txt`）
- `requirements-sidecar.txt:14-27`（pyinstaller / curl_cffi / requests / urllib3 / certifi 等全 pin）
- `requirements-ci.txt:7-8`（pytest / coverage pin）

**說明**
供應鏈硬化做得不錯，符合 GitHub-recommended「pin to SHA」與「`--ignore-scripts`」實踐。**建議 Codex 確認**：
1. `certifi==2026.1.4` 是否確實存在於 PyPI（年份格式可疑；若拼錯會在 CI 立即失敗，但仍值得人工驗）。
2. `SonarSource/sonarqube-scan-action@fd88...` 對應的 tag 是否仍為 v6 stable。

---

### F-13 [Info] `requests.Session().get(..., timeout=30)` 全面設定逾時，無 `verify=False`

**證據**
- `javdb_scraper.py:79`、`realdebrid.py:52`（皆指定 timeout）
- 全 repo grep `verify=False / InsecureRequest / disable_warnings` 無命中

**說明**
網路請求設計層面正確，未停用 TLS 驗證。

---

### F-14 [Low] Tauri 能力 `shell:allow-open` 將 `https://real-debrid.com/*` 與 `https://javdb.com/*` 列為允許開啟網址

**證據**
- `app/src-tauri/capabilities/default.json:7-15`

**說明**
範圍合理，無 `**` 萬用。可考慮進一步限制為 `https://real-debrid.com/apitoken` 單一 path（前端目前只用此 URL），降低未來誤用。

---

### F-15 [Low] `withGlobalTauri: false` 已關閉，但 `app.security.csp` 仍為 null

見 F-02；列此確認 `withGlobalTauri` 已正確 false（`tauri.conf.json:13`），降低 window 全域注入面，但 CSP 仍建議補上。

---

### F-16 [Info] `sidecar_manager.rs` 有 per-command timeout、protocol-corruption → `mark_dead` 防呆

**證據**
- `app/src-tauri/src/sidecar_manager.rs:34-130`、`:222-285`

**說明**
良好的 fail-fast 設計，避免攻擊者透過餵畸形 JSON-line 造成同步點 deadlock。

---

### F-17 [Low] `rd_set_token` (sidecar 命令) 不要求 `handshake_done`

**證據**
- `sidecar/sidecar.py:518-528`（`cmd_rd_set_token` 直接設 `state.rd_token`，無 handshake gate）
- 對比 `:541`（`cmd_rd_send_magnet` 需要 handshake）

**說明**
若 IPC 通道被他者搶先寫入（在桌面 app 場景幾乎不可能，因為 stdin/stdout pipe 由 Tauri spawn 獨佔），可越過 handshake 直接灌入 token。**屬於深度防禦**：建議在 `cmd_rd_set_token` 加上 `if not state.handshake_done: return _err(...)`。

---

## 4. 需要 Codex 複查的問題

> 以下項目我在靜態審查無法 100% 確定，請 Codex 用 grep + reasoning 二次驗證。

1. **F-01 是否屬於真實 cookie 外洩風險**：
   - 確認 `requests.Session.get(url, cookies=<dict>)` 在 v2.32.5 是否依 host 過濾。
   - 若 requests 本身已過濾，本條可降為 Low/Info。
2. **F-07 跨平台 path traversal**：
   - Windows symbolic / junction link 是否會讓 `Path::canonicalize()` 等價判斷被繞過，造成 source 與 data_dir 互覆蓋。
3. **F-02 CSP 開啟對既有功能的衝擊**：
   - 目前 frontend 是否有任何 inline `<style>` / 動態 `data:` URL 會被預設 CSP 擋掉。
4. **F-12 供應鏈版本實在性**：
   - `certifi==2026.1.4`、`charset-normalizer==3.4.4`、`urllib3==2.6.3` 是否在 PyPI 上確實存在且未被惡意 typosquatting（用 `pip index versions <name>` 確認）。
5. **`legacy_import::parse_env` 對 BOM / CRLF 邊界**：
   - 是否能讓 `RD_API_TOKEN` 在 `parse_env` 中被視為 `﻿RD_API_TOKEN`，繞過 token routing 改落入 `settings_patch`？
6. **`scripts/build-release.ps1` 的 binary 機密掃描覆蓋率**：
   - 確認 Step 6 的 regex 列表是否能在 strings 切割中被 PE base64 區段繞過（例如 UTF-16LE 字串），目前掃描只做 ASCII decode（`build-release.ps1:278`）。
7. **`sidecar_manager` 對 stderr 的處理**：
   - `sidecar_manager.rs:176-180` 把 stderr 丟棄但寫了 TODO 接 log；確認此 TODO 不會在後續 commit 中改為「直接轉發到前端」造成洩漏。
8. **`legacy_import.rs:264` 的 PendingEntry 反序列化**：
   - 確認新增的合法欄位不會因 `serde(default)` 而把舊版本的 `magnet` 偷渡進來（單元測試在 `pending.rs:241` 已守住寫入端，但建議 Codex 驗 import 端）。

---

## 5. 整體結論

- 此專案在敏感資料分層 (RD token → keyring；pending JSON → 不含 magnet；sidecar IPC redaction) 與供應鏈硬化 (SHA-pinned actions、pinned pip、`--ignore-scripts`) 上實作品質高。
- 主要殘留風險集中在：
  1. **F-01** JavDB cookie 對 host 未過濾（Medium）。
  2. **F-02** Tauri WebView 缺少 CSP（Medium）。
  3. **F-03** cookies.txt 仍為明文（Medium，已有 roadmap）。
- 其餘為低風險深度防禦建議，可在後續 milestone 一併處理。

**未對任何檔案做修改**；本檔為 `docs/security-review-draft.md` 草稿，後續是否上交給 Codex 複查由維護者決定。
