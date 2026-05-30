# 資安漏洞審查結果 — JavDBMagnet

**日期**：2026-05-30
**範圍**：整個專案生產程式碼(Rust 後端 + Svelte/TS 前端 + Python sidecar + 建置腳本),約 11,700 行
**方法**：
1. `/tool-scan` skill 自動化掃描(ruff / bandit / mypy / gitleaks / trivy / clippy / npm-audit / PSScriptAnalyzer)
2. `/workflow` 平行人工深度審查 —— 6 個模組群組各派一個資安稽核 agent(共 17 raw findings),每個 P0/P1 再派對抗式驗證 agent 反駁(14 agents,~1.35M tokens)
3. 主程序對頭號發現逐一手動 grep 覆核

威脅模型(嚴重度依此校準):**單機單使用者桌面 App**,無對外監聽埠。敏感資產 = 使用者的 RealDebrid API token + JavDB session cookie(含 Cloudflare `cf_clearance`)。爬取的 JavDB HTML 視為攻擊者可控。CSP 在 WebView 中為關閉狀態。

---

## 總結論

**這個 codebase 的資安狀態良好。** 沒有 P0。git log 顯示已歷經多輪稽核(`chore(audit)` 系列 + `docs/security-review-draft.md` F-01~F-09 修補),自動化工具零發現,絕大多數攻擊面已被刻意防禦(OS keyring 存密鑰、log 遮蔽、handle-id 間接化、IPC 邊界輸入驗證、入口 URL host-pin)。

人工深度審查找到 **1 個必修的 cookie 外洩問題(P1/P2)**、**4 個 agent 評為 P2 的項目**(防禦縱深 / 一致性,均未經對抗式驗證)、以及一批 P3 hardening。**只有頭號發現經過對抗式驗證**(兩個 agent 都確認 isReal,且主程序 grep 覆核屬實);其餘 P2/P3 是單一 agent 評級,請當作「待你確認的清單」而非定讞。

| 嚴重度 | 數量 | 說明 |
|---|---|---|
| P0 | 0 | — |
| **P1 / P2(已驗證)** | **1** | scraper 跟隨跨主機 redirect 時攜帶 JavDB cookie(根因單一,Rust/Python 兩處呈現) |
| **P2(agent 評級,未對抗驗證)** | **4** | RD 原始回應進錯誤訊息、pending 檔無大小上限、magnet 攝取無上限、CSP 關閉 |
| P3(hardening) | 11 | 見 §4 |
| 誤報 | 0 | (初判的 javascript: URI / 入口 SSRF 經查均已被 host-pin 或無可達 sink) |

> ⚠️ 嚴重度誠實聲明:頭號發現的兩個驗證 agent 對 **P1 vs P2** 分歧 —— Python 側評 P1(且實測 `requests` 與**主要引擎 `curl_cffi` 兩者**都會在跨主機 302 重送 cookie),Rust 側評 P2(理由:利用前提需 javdb.com 被入侵/MITM,門檻較高)。依本專案明文「javdb.com 內容視為攻擊者可控」→ 取 P1;若視 MITM 門檻為高 → P2。無論哪個,**必修、修法相同、低風險**。

---

## 1. 自動化工具掃描(tool-scan)

完整 JSON:`output/tool-scan/20260530_223502/findings.json`

| 工具 | 狀態 | 發現 | 備註 |
|---|---|---|---|
| ruff / bandit / gitleaks / trivy / clippy / npm-audit / PSScriptAnalyzer | ✓ | **0** | lint / 安全 / CVE / secret 全乾淨 |
| mypy | ⚠ | 1 | `app_logging` import-not-found —— 純路徑設定問題(sidecar 從 repo root import),非真實 bug |

→ 自動化層面乾淨,價值集中在下方人工發現。

---

## 2. 必修(已對抗式驗證)

### 🔴 P1 / P2 — scraper 跟隨跨主機 redirect 時攜帶 JavDB cookie(session 劫持)
- **ID**:SEC-py-scraper-01(= SEC-rust-commands-01 的存活向量,同一根因)
- **位置**:`javdb_scraper.py:79`(主),`legacy/javdb_magnet_gui.py:153`(legacy 同病),`realdebrid.py:36`(防禦縱深)
- **CWE**:CWE-200 / CWE-540 / CWE-441 / CWE-918
- **驗證**:isReal=true,confidence=high;主程序 grep 覆核屬實(`allow_redirects` 在整個 repo 都沒出現)

```python
# javdb_scraper.py:79
resp = session.get(url, cookies=cookies, timeout=30)   # 缺 allow_redirects=False
```

**為何天真攻擊不成立**:入口 URL **已被** `sidecar/sidecar.py` 的 `_is_javdb_host()` 守衛(L309-322,dot-anchored:`host == "javdb.com" or host.endswith(".javdb.com")`,故 `evil-javdb.com`、`javdb.com.attacker.com` 都被擋,且 L334 強制 `https://`)。所以「使用者貼/點攻擊者連結就中」**不成立** —— 這也是原報告把它寫成 P1 的字面說法被推翻的原因。

**真正的缺口**:host-pin 只檢查第一跳。`session.get` 預設跟隨 3xx,redirect 目標主機**不會**再比對 `_is_javdb_host`。cookie 經 `cookies=dict` 注入時是 domain-less,跨主機跳轉不會被 strip。驗證 agent 以本機雙伺服器 302 harness 實測:`cf_clearance` + `_jdb_session` 被原樣送到攻擊者主機 —— **`requests` 2.32.x 與 `curl_cffi` 0.13.x 兩者皆中**。`sidecar.py:312-318` docstring 其實已記載 dict-cookie 不分 host 的風險,但守衛只套在入口 URL。

**影響**:javdb.com 被入侵 / MITM 回 302 → sidecar 把 `cf_clearance` + `_jdb_session`(「絕不可外洩」資產)送給攻擊者 → JavDB session 劫持 + Cloudflare bypass token 竊取。

**建議修法**(任一):
1. `session.get(url, cookies=cookies, timeout=30, allow_redirects=False)`,3xx 視為錯誤;或
2. 逐跳跟隨,每個 redirect Location 先過 `_is_javdb_host` 才續;或
3. cookie 改綁 `RequestsCookieJar(domain='javdb.com')` 而非 domain-less dict,讓 library 跨域自動 strip。

`legacy/javdb_magnet_gui.py:153`(retired)同病;`realbrid.py` 比照(RD 用 Authorization header,`requests` 跨主機會自動 strip,風險較低)。**curl_cffi 也要驗**,它是主要引擎。

---

## 3. agent 評為 P2(未對抗式驗證,建議逐項確認)

主題:**錯誤訊息把不受控字串回灌進 log + 前端,而 CSP 又關閉** —— 形成一致的次要風險群。

### 3.1 SEC-py-rd-01 — RD 原始回應 body 進使用者可見錯誤訊息
- `realdebrid.py:107-112`:`msg = resp.json().get("error", resp.text)` / `resp.text` → 既 `logger.error` 又 `raise RealDebridError(...)`,再由 `sidecar.py`(L611/704/750)`_err(req, ..., str(e))` 原樣放進 IPC envelope 的 `message` 欄回前端。違反 sidecar docstring「envelope 須遮蔽、不帶完整內容」的承諾;CSP 關閉下是潛在 XSS 載體。**建議**:non-2xx 映射到穩定 code + 通用訊息,或至少 `_truncate` + 去控制字元,不要把 `resp.text` 放進回前端的 message。

### 3.2 SEC-py-sidecar-01 — magnet 攝取無上限(記憶體耗盡)
- `sidecar.py:360-375` / `javdb_scraper.py:95` / `register_magnets`:對攻擊者可控頁面解析出的每個 magnet 無數量 / 長度上限地 intern 進 `state.magnets`(只在 `forget_magnets` 才清)。惡意頁面塞大量 `.item` 或超長 href → 長駐 sidecar 記憶體持續成長。**建議**:每次 fetch/register 限筆數(數千)+ 限單筆長度(magnet URI ≤ ~4KB),比照 `COOKIES_MAX_BYTES`。

### 3.3 SEC-rust-storage-01 — `pending.rs` load() 無大小上限
- `pending.rs:86-97`:`fs::read_to_string` + `serde_json::from_str` 無 byte 上限,而 cookie 路徑明確有 64KiB cap。被竄改 / 超大的 `pending_torrents.json`(或社交工程誘導匯入的 legacy 檔)會整個載入記憶體。**建議**:read 前先 `fs::metadata` 比對上限(1–4MiB),比照 `migrate_cookies_refuses_oversized_file` 加 regression test。

### 3.4 SEC-build-legacy-01 — CSP 關閉(`tauri.conf.json:24` `"csp": null`)
- WebView 無 CSP backstop。**目前無可達 DOM-XSS sink**(frontend group 已 grep 確認零 `{@html}`/`innerHTML`/`eval`,本人亦覆核),所以是防禦縱深而非當下可利用 —— 但 App 會渲染攻擊者可控的爬取資料,且上面 3.1 等錯誤回灌路徑都把 CSP 當最後一道防線。**建議**:設 `default-src 'self'; script-src 'self'; object-src 'none'; frame-src 'none'`。

---

## 4. P3 — hardening(可排期)

| ID | 位置 | 說明 |
|---|---|---|
| SEC-rust-commands-02 | `commands.rs`(register/forget/copy_*) | 前端傳入的 `Vec<String>` 跨進 sidecar 前無數量/長度上限(與 3.2 同類,Rust 邊界) |
| SEC-rust-sidecar-03 | `sidecar_manager.rs:165-174` | stdout line buffer 無上限、JSON parse 無上限(信任的 sidecar 才觸發) |
| SEC-rust-import-01 | `legacy_import.rs:106,201` | `.env` 原始行/值被 echo 進 Serialize 的 warning 回前端,違反模組「只回 key 名不回值」不變式(目前只流非密鑰數值/junk,無實際 secret) |
| SEC-rust-sidecar-02 | `sidecar_manager.rs:236-240` | `request()` 對 non-object body 把整個 body 內插進錯誤字串(目前無 caller 觸發;未來 footgun) |
| SEC-py-sidecar-02 | `sidecar.py:353-358` | fetch_javdb 網路錯誤把上游 error 原樣回 envelope(目前只是固定 HTTP-status 字串) |
| SEC-rust-storage-02 | `path_manager.rs:24-33` | 直接信任 `APPDATA`/`LOCALAPPDATA` env var(無驗證);改寫需已具使用者權限,僅 hardening |
| SEC-frontend-01 | `scraper.ts:110` | `parseUrlBatch` 接受任何 http/https host(非僅 javdb.com)就轉給 `fetch_javdb`;SSRF 安全現全靠 sidecar host-pin |
| SEC-frontend-02 | `scraper.ts:102,124` | 貼上批次無筆數/長度/總量上限就跨 IPC(與 3.2 / SEC-rust-commands-02 同類,前端邊界) |
| SEC-build-legacy-02 | `legacy/javdb_magnet_gui.py` | retired scraper 無 host 驗證 + 預設跟隨 redirect(= §2 的 legacy 版;未出貨) |
| SEC-build-legacy-03 | `scripts/build-release.ps1` | Step 7 secret 掃描只掃 diff,已 commit 的 secret 會漏(Step 5 仍掃兩個 exe,風險低)→ 改掃 `git ls-files` 或全歷史 |
| SEC-build-legacy-04 | `legacy/javdb_magnet_gui.py` | `os.startfile` 開 app 控制的 log 路徑;無注入。retired,未出貨 |

> **跨邊界主題**:輸入上限缺失同時出現在前端(SEC-frontend-02)、Rust IPC(SEC-rust-commands-02)、Python sidecar(SEC-py-sidecar-01)三層 —— 建議在 sidecar 那層設一道權威上限即可一次覆蓋,其餘為防禦縱深。

---

## 5. 經審查確認乾淨的區塊

- **密鑰儲存**(`secret_store.rs` / `cookie_store.rs`):OS keyring;寫入前先驗格式/大小(token = ASCII alnum ≤255;cookie ≤64KiB),malformed 不覆蓋既有憑證;明文 `cookies.txt` 是 migration-only,寫入 keyring 後即刪。
- **入口 URL host-pin**(`sidecar.py` `_is_javdb_host`):https-only + dot-anchored allow-list,擋下天真 SSRF(原 F-01 已修;唯 redirect 缺口見 §2)。
- **sidecar 生命週期**(`sidecar_manager.rs`):Tauri sidecar API spawn(無 shell、無使用者可控 argv);mutex 序列化;per-command timeout + `cache_wait` 邊界驗證;協定錯誤即永久 dead-state。
- **log 遮蔽**(`realdebrid.py` `_redact_log_kwargs`):magnet / Authorization / Cookie header 全遮蔽;token 不入 log。
- **settings / 前端邊界**:`without_secrets()` 在 read 與 write 兩路都清掉 `rd.api_token` 才跨 WebView;serde 顯式 default(無不安全反序列化)。
- **前端渲染**:零 `{@html}`/`innerHTML`/`eval`/`Function`;爬取資料只走 Svelte 自動跳脫的文字插值。唯一綁 href 的爬取值是 magnet URI,只進 magnet pipeline / 剪貼簿(故初判的 javascript: URI XSS 為**無可達 sink**)。

---

## 6. 行動建議(優先序)

1. **(必修)** `javdb_scraper.py:79` redirect:`allow_redirects=False` 或逐跳 host 驗證;`legacy` 與 `realdebrid.py` 比照,**curl_cffi 一併驗**。
2. **(P2)** `realdebrid.py` 錯誤訊息不要回灌 `resp.text` 到前端 message。
3. **(P2)** sidecar 設一道權威輸入上限(magnet 筆數/長度),覆蓋前端+Rust+Python 三層攝取。
4. **(P2)** `pending.rs` load() 加檔案大小上限。
5. **(P2)** `tauri.conf.json` 設嚴格 CSP(關閉次要錯誤回灌路徑的 XSS 風險)。
6. **(P3)** 其餘錯誤字串遮蔽一致化、build 腳本掃全部追蹤檔。

> 完整逐項(含 agent 對抗式驗證 reasoning、實測 redirect harness 細節)見 workflow 輸出:
> `C:\Users\cy5407\AppData\Local\Temp\claude\...\tasks\wctlo8cq1.output`
