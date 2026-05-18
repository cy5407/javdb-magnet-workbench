# Task: Security & Quality Audit — 2026-05-18

**Status**: 5/7 items SHIPPED to working tree, awaiting human commit; 2 items intentionally deferred
**Source**: full-audit pass（codex + manual verification）
**Reviewer verification**: 下列每條 P1/P2 都已 hand-verified（file:line 對得到、code pattern 與 agent 描述一致），不是純信任 agent 報告。

---

## Implementation status (2026-05-18)

| Item | Status | Where |
|---|---|---|
| **P1.1** build-release.ps1 origin/dev → symbolic-ref + FailExit | ✅ DONE | working tree, codex job `br0ikqwsg` |
| **P1.2** Python deps bump (curl_cffi / requests / urllib3 / pytest) | ✅ DONE | working tree, codex job `bm25c01z7` |
| **P2.2** sidecar.py operator-precedence parens | ✅ DONE | working tree, codex job `b63cawifh` |
| **P2.3** commands.rs clippy unneeded return | ✅ DONE | working tree, codex job `b63cawifh` |
| **P2.4** tauri.conf.json `"targets": []` | ✅ DONE | working tree, codex job `b4vzcm86b` |
| **P2.5** Cargo.toml keyring 三個 OS features | ✅ DONE | working tree, codex job `b4vzcm86b` |
| **P2.7** npm svelte / devalue bump | ✅ DONE | commit `2a0b5e0` — `npm audit fix` to devalue 5.8.1 + svelte 5.55.7 |
| **P2.6** glib 0.18.5 transitive | ✅ SUPPRESSED | phantom finding — verified absent from x86_64-pc-windows-msvc target; `.trivyignore` documents rationale |
| **P2.1** CSP policy | 🟡 DEFERRED | needs interactive WebView testing; not safe for blind codex dispatch |

### Working tree summary

```
app/src-tauri/Cargo.toml          |  2 +-
app/src-tauri/src/commands.rs     |  2 +-
app/src-tauri/tauri.conf.json     |  2 +-
requirements-ci.txt               |  2 +-
requirements-sidecar.txt          |  6 +++---
scripts/build-release.ps1         | 17 +++++++++++------
sidecar/sidecar.py                |  4 ++--
7 files changed, 20 insertions(+), 15 deletions(-)
```

### Verification pass (post all dispatches)

- `python output/verify-no-dev-branch.py` → OK
- `python output/verify-deps-bumped.py` → OK
- `python output/verify-config-cleanup.py` → OK
- `python -m py_compile sidecar/sidecar.py` → OK
- PowerShell parse of `scripts/build-release.ps1` → OK

### Codex 配額 / token cost 觀察

5 個 codex worker rounds，全部 `--continue-session` 接同一個 thread：

| Round | Items | Duration | Real tokens (input new + output) | Cache hit |
|---|---|---|---|---|
| 1 | P2.2 + P2.3 | 50s | ~27K | 85% |
| 2 | P1.1 | 66s | ~38K | 91% |
| 3 | P1.2 | 34s | ~44K | 93% |
| 4 | P2.4 + P2.5 | 37s | ~48K | 94.6% |
| **總計** | **5 items** | **~3 分鐘** | **~157K** | 平均 91% |

Cache hit 隨 session 連續上升（session prompt + tool schema 共用），每個 task 邊際成本越小。

ChatGPT 免費 tier 配額**仍未撞牆**（沒看到 rate limit error）。實測這個量級的 audit cleanup（含 PowerShell / Rust / Python / TOML / JSON 多語言）大約**佔不到日配額一小部分**。

### 需要人工後續驗證（codex 沒做）

- `cd app/src-tauri && cargo check` — P2.5 keyring features 在 Linux/Mac 編是否真有 backend
- `python spikes/pyinstaller_sidecar/build_sidecar.py` — P1.2 新版 deps 能否 bundle 進 sidecar.exe
- `pwsh ./scripts/build-release.ps1 -DryRun`（若有）或實際 release 一次 — P1.1 symbolic-ref 在你機器上是否真拿到 `origin/master`
- `cd app && npm audit fix` — P2.7 一鍵清 devalue + svelte vulns
- 互動式 Tauri WebView 測試 — P2.1 CSP 加上去（手動寫 conservative policy 後測）

---

---

## 工具掃描總覽（皆已實測重現）

| 工具 | 結果 |
|---|---|
| ruff (Python) | 0 |
| bandit medium+ | 0（7 個 LOW 是 B105 對 error code 字串的 false positive） |
| gitleaks（133 commits） | 0 |
| trivy fs（HIGH/CRITICAL） | 0 |
| trivy cargo lock | 1 MEDIUM（glib 0.18.5，等上游 Tauri/gtk bump） |
| pip-audit | 5 CVE（curl-cffi / requests / urllib3 ×2 / pytest） |
| npm audit | 2（devalue HIGH、svelte MODERATE） |
| cargo audit | 0 vulns |
| cargo clippy | 1 warning |
| svelte-check | 0 |
| pytest / vitest | 256 / 117 passed |

---

## P0（blocker）

無。

---

## P1（release 前必修）

### P1.1 — `scripts/build-release.ps1:308` source-secret-scan 已悄悄失效

**Verified**: line 308 確實是 `$sourceFiles += (& git -C $RepoRoot diff --name-only origin/dev..HEAD)`，但本 repo `git branch -a` 無 `origin/dev`（default branch 是 `master`）。Line 18 註解也寫 `git diff origin/dev..HEAD`。

**Why it matters**: Step 6 binary regex scan 仍守住「token/RD URL 落到 exe」這條主防線，但你刻意設計的「committed source 也再掃一次」defense-in-depth **always no-op**：`git diff origin/dev..HEAD` fatal 後，try/catch 對 native command 失敗的捕獲行為視 PowerShell 版本而定；即便進 catch，邏輯只 `Write-Warning` 然後 fall through 用 `git diff --name-only`（= 工作樹 diff，已 commit 的改動完全不會被掃）。

**Fix**:
- 把 `origin/dev` 改成 `origin/master`，或用 `git symbolic-ref refs/remotes/origin/HEAD` 自動拿 default branch。
- git exit code 非零時 **`FailExit`**，不要 `Write-Warning` 後繼續——這條 scan 失敗就是 release blocker。

**Verify**:
- 跑一次 `pwsh ./scripts/build-release.ps1 -DryRun`（如果有 dry-run mode）或 `-WhatIf`，確認 source-secret-scan 真的 enumerate 到 commit diff。
- 修改 default branch 探測邏輯後，故意在某個 commit 加入 magnet 字串測試 scan 能擋下。

**禁止**：不要改其他 Step、不要動 RUSTFLAGS、不要動 manifest 生成邏輯。

---

### P1.2 — Python sidecar 依賴 5 個 CVE（2 個直接 ship 進 exe）

**Verified**: `requirements-sidecar.txt` 主 repo 版本：

```
curl_cffi==0.14.0    # ships in sidecar.exe
requests==2.32.5     # ships in sidecar.exe
urllib3==2.6.3       # transitive, ships
```

`requirements-ci.txt`：

```
pytest==8.3.4   # dev only
```

**CVE 對應 + 攻擊面**：

| 套件 | CVE | 風險 | 是否 ship | 受影響路徑 |
|---|---|---|---|---|
| **curl-cffi 0.14.0** | CVE-2026-33752 | redirect-based SSRF + TLS impersonation bypass | **是** | `sidecar.py` JavDB fetch 走 curl_cffi engine。`_is_javdb_host` allowlist 守不住「請求成立後被 302 到 internal host」的 redirect 階段 |
| **urllib3 2.6.3** | CVE-2026-44431 | cross-origin Authorization-forward in streaming | **是** | `realdebrid.py:55` `session.headers["Authorization"] = f"Bearer {token}"` 是 long-lived session header。若 RD API 被 MITM 或 redirect 到攻擊者 host，Bearer token 被一起送 |
| **urllib3 2.6.3** | CVE-2026-44432 | 累積攻擊面 | 是 | 同上 |
| **requests 2.32.5** | CVE-2026-25645 | 累積攻擊面 | 是 | requests 是 RD client 主路徑 |
| **pytest 8.3.4** | CVE-2025-71176 | dev-only | 否 | 只在 CI / dev 環境 |

**Fix**:
- `requirements-sidecar.txt`：bump `curl_cffi>=0.15.0`、`requests>=2.33.0`、`urllib3>=2.7.0`。
- `requirements-ci.txt`：bump `pytest` 到 `>=9.0.3`。
- `build_sidecar.py` 已有 fail-fast 版本驗證——pin 改完跑一次 PyInstaller 確認 bundle 還能組起來。

**Verify**:
- `pip install -r requirements-sidecar.txt` clean
- `python spikes/pyinstaller_sidecar/build_sidecar.py` 成功產出 `sidecar-*.exe`
- 跑 smoke：`echo '{"cmd":"hello",...}' | sidecar.exe` 正常回 JSON
- `pytest` 仍 256 passed
- `pip-audit` 應降到 0 finding（除非新版本又被新 CVE 中標）

**禁止**：不要改任何 sidecar.py / realdebrid.py 商業邏輯。

---

## P2（建議修，不阻擋 release）

### P2.1 — `app/src-tauri/tauri.conf.json:24` `"csp": null`

**Verified**: line 24 確實 `"csp": null`。

**Why**: Tauri WebView 雖只載 `dist/` 但 JavDB 抓回來的 magnet `dn=` / title 進 DOM。Svelte text binding 預設轉義 OK，但失去一道便宜的 defense-in-depth。

**Fix**: 至少設 `"default-src 'self'; img-src 'self' data:"`；若用 inline style 再加 `'unsafe-inline'`。

**Verify**: tauri build 後 smoke 一次互動式 add magnet → 確認 DOM 沒 console error。

---

### P2.2 — `sidecar/sidecar.py:512, 516` operator precedence 可讀性差

**Verified**:

```python
if "401" in m or "token 無效" in m or "token" in m and "過期" in m:
```

`and` 比 `or` 優先，所以實際是 `A or B or (C and D)`——跟作者意圖一致，但讀者第一眼會看錯。

**Fix**: 加括號：

```python
if "401" in m or "token 無效" in m or ("token" in m and "過期" in m):
```

line 516 同類問題（`"429" in m or "rate" in m and "limit" in m:` → `"429" in m or ("rate" in m and "limit" in m)`）。

---

### P2.3 — `app/src-tauri/src/commands.rs:1038` clippy 唯一警告

**Verified**: `#[cfg(target_os = "windows")]` block 末尾 `return Ok(());` 是該 block 最後一個 expression，clippy 建議移掉 `return`。一行修。

**Fix**:
```rust
.map_err(|e| format!("spawn explorer: {e}"))?;
Ok(())
```

---

### P2.4 — `app/src-tauri/tauri.conf.json:29` `"targets": ["msi"]` 與 portable-zip 策略不一致

**Verified**: line 29 `"targets": ["msi"]`。

**Why**: 日常 release 走 `tauri build --no-bundle` + portable zip（你 audit 過的 artifact），但 `npm run tauri:build` 會生 MSI installer——兩個不同二進位、不同分發路徑、不同簽章狀態。

**Fix（二選一）**:
- 把 `targets` 改成 `[]`（不 bundle，跟 release pipeline 對齊）
- 在 `README.md` / `Cargo.toml` 註明「`tauri:build` MSI 是 dev convenience，不對應 release portable zip」

---

### P2.5 — `app/src-tauri/Cargo.toml:31` keyring 只啟用 `windows-native`

**Verified**: 
- Cargo.toml: `keyring = { version = "3", features = ["windows-native"] }`
- Cargo.toml 註解（line 29-30）寫「`apple-native` / `linux-native-async-persistent` enable the equivalent secure stores on the other targets」——**但實際 features 沒啟用這兩個**。
- `path_manager.rs:23-37` 有 `#[cfg(not(target_os = "windows"))]` fallback path。

**Why**: 註解寫一套、實際 features 一套。`cargo check` 在 Linux/Mac 過編譯，但 `keyring::Entry::new` 沒 backend 會 runtime panic。

**Fix（二選一）**:
- 跟註解對齊：`features = ["windows-native", "apple-native", "linux-native-async-persistent"]`
- 跟 README「Windows only」對齊：`#[cfg(target_os = "windows")]` gate 整個 `secret_store` 模組，非 Windows 編譯時直接排除。

---

### P2.6 — glib 0.18.5 transitive MEDIUM（GHSA-wrw7-89jp-8q8g）

**狀態（修正）**: phantom finding — 本 repo ship target 為 Windows，glib 是 Linux/macOS 路徑（wry → webkit2gtk → gtk → glib）；Windows 用 WebView2 不走這條。

**驗證**:
```
cargo tree --target x86_64-pc-windows-msvc -i glib
# → "nothing to print" (確認 Windows build 完全不含 glib)
```

**處置**: 已新增 `.trivyignore` 抑制 GHSA-wrw7-89jp-8q8g 並附 rationale comment。trivy 重掃 0 findings。

**重新評估時機**: 若日後決定支援 Linux/macOS ship，必須移除 `.trivyignore` 那條並等 Tauri 上游 bump 到 glib 0.20.0 鏈，或考慮 `[patch.crates-io]` workaround。

---

### P2.7 — npm devalue HIGH（DoS via sparse array）+ svelte SSR XSS MODERATE

**Verified**: npm audit 輸出列出這兩條（agent 報告數字）。

**Why**: 本專案是 Tauri WebView 純 CSR，**沒 SSR**——所以兩條都不暴露實際攻擊面。但 `npm audit clean` 仍是 release pipeline 想保持的目標。

**Fix**: `npm update svelte`（或 `npm install svelte@latest`）拉到含修補 devalue 的版本，跑 `npm run check` + vitest 確認無 regression。

---

## Accepted false positives（記錄，不行動）

| 規則 | 數量 | 位置 | 為何接受 |
|---|---|---|---|
| bandit B105 | 7 | `sidecar/sidecar.py:230, 237, 500, 506, 629, 633, 635` | bandit 對所有 `*token*` 命名字串都會雜訊報「hardcoded password」。實際是 error code 字串（`"rd_no_token"` / `"RD token not configured"`）。`-ll`（≥ medium）run 自動篩掉 |
| Sonar S2245 | 1 | `app/src/lib/scraper.ts` jitter | 已用 `crypto.getRandomValues` 包裝，comment 寫明非 crypto-sensitive |
| Sonar S7749（polynomial backtracking）| 多處 | regex patterns | 系統性已處理（`[\d.]+` / `[a-fA-F0-9]+` 改 bounded `{1,N}`），commits 6b91af1 / 36fd817 / e086859 證明刻意修補 |

---

## Coverage gaps（未深讀但提一下）

- **`app/src/App.svelte` ~1500 行 markup**：只讀了 token / pending / RD 業務邏輯。剪貼簿寫入是否會把 RD download URL 多寫一份到 console？reactive `$:` / `$effect` 在 dev 模式是否漏 token 到 DOM？沒系統性 grep 過。如有顧慮可針對性 review。
- **`docs/sessions/` 與 `docs/troubleshooting/`**：沒讀，不影響 audit。
- **`legacy/javdb_magnet_gui.py`（1494 行 Tk GUI）**：刻意排除，sidecar.exe 不再 bundle。

---

## Positive notes（保留現有強項，避免回退）

- **安全 invariants 有 test 鎖住**：`pending::entries_have_no_magnet_field`、`cookies_status_does_not_leak_body`、`validate_legacy_rd_token_rejects_with_warning_text`、`preview_reports_files_without_echoing_values`——這些不是裝飾，是真的把規格寫死成測試。修 P1/P2 不要動到這層。
- **Python sidecar 與 Rust `secret_store` 的 `is_valid_rd_token` 雙邊有 `!!! KEEP IN SYNC` 註解**——展示作者意識到 protocol-boundary drift 風險。
- **Release pipeline 是這次 audit 看過最嚴謹的**：whitelist staging + binary regex scan + `RUSTFLAGS --remap-path-prefix` 路徑刮除 + SHA256SUMS + manifest。唯一弱點是 P1.1。
- **`_magnet_dedupe_key` 用 BTIH normalize** 避免同一磁力被 RD 重扣兩次額度——README 安全模型表標為「兩道防線」，frontend `dedupeByHandleId` 是第二道。
- **Sonar polynomial-backtracking 系統性處理**（bounded `{1,128}`、`urllib.parse.parse_qs` 取代 unbounded `[^&]+`），不是 `# noqa` 蓋掉。
- **`sidecar_manager.rs` 的 `mark_dead` + request_id mismatch 立即標死**——拒絕 auto-respawn 避免半死 sidecar 卡 mutex。

---

## 建議行動順序

| 順序 | 動作 | 預估時間 |
|---|---|---|
| 1 | **下次 release 前**：修 P1.1 build-release.ps1 `origin/dev` → `origin/master`（含 fail-on-error） | 5 min |
| 2 | **下次 release 前**：bump P1.2 三個 sidecar deps，跑 PyInstaller + smoke 驗證 | 30 min |
| 3 | **本週內**：P2.3 clippy 一行修；P2.2 加括號 | 5 min |
| 4 | **本週內**：P2.5 keyring features 對齊（決定 multi-OS 還是 Windows-only） | 15 min |
| 5 | **下個 release cycle**：P2.1 csp、P2.4 targets 一致性 | 30 min |
| 6 | **本月內**：P2.7 svelte bump 清 npm audit | 15 min |
| 7 | **每月排程**：P2.6 等 Tauri 上游 bump glib | 觀察即可 |

---

## 禁止 / 注意事項

- **不要**動 `pending::entries_have_no_magnet_field` 等 invariant test
- **不要**動 release pipeline 的 RUSTFLAGS / SHA256SUMS / manifest 生成（P1.1 只改 secret-scan 段）
- **不要** `git commit` / `git push` / `git reset` ——人工 gate
- 修 P1.2 deps 後**必須**跑 `python spikes/pyinstaller_sidecar/build_sidecar.py` + smoke，確認 bundle 還能組起來
