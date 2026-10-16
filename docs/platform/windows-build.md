# Windows 建置交接

寫給在 Windows 機器上接手建置的人（或 agent）。程式碼在 Linux 上開發並通過全部
gate，但有幾件事只有在 Windows 上才驗得了，這份文件說明是哪幾件、為什麼、
以及壞掉時怎麼修。

**2026-08-02 首次在 Windows 上完整跑過**：第 1 項（keyring 平台拆分）已實測
通過並降級為紀錄；第 4 項（Smart App Control）是那次才浮現的新阻擋點。

## 先跑這個

```powershell
pwsh -File scripts\verify-windows-build.ps1
```

全綠之後才跑既有的打包 pipeline：

```powershell
pwsh -File scripts\build-release.ps1
```

這條命令的 Step 0 會**先跑一次 `scripts/test-release-scan.ps1`**（機密掃描的
紅測套件），失敗即中止、不產出任何 artifact。這道關卡本來只掛在
`npm run release` 上，而本文件教的正是直接呼叫打包腳本——那條路完全繞過它。
關卡因此改放在打包腳本內部，兩個入口都會跑到。

紅測之後，打包腳本會確認工作樹乾淨（tracked 與 untracked 都算，也拒絕
assume-unchanged／skip-worktree 標記），不乾淨就拒絕建置——manifest 記錄的是
`git rev-parse HEAD`，未 commit 的變更會讓它替沒出貨的 commit 背書。建置結束後會再驗一次。

`-AuditOnly` / `-AuditBinary` 不會跑紅測：紅測本身就是用這兩個模式呼叫打包
腳本的，在那裡執行會無限遞迴。

`verify-windows-build.ps1` 不打包，它只做驗證：環境齊全性 → 三個既有 gate →
`cargo test --no-fail-fast --tests`（lib、bin 與 `tests/` 整合測試，不含 doc tests）→ release-scan 紅測
（`powershell` 與 `pwsh` 各跑一次，見第 5 項）→ 重建 sidecar 並用真的 JSON-lines 協定
（`hello` / `register_magnets` / `shutdown`）跟它對話。`-SkipSlow` 會略過 cargo test 與 sidecar
重建，但不會略過 release-scan 紅測。

---

## Windows 專屬風險

### 1. Cargo.toml 的 keyring 相依平台拆分 —— 2026-08-02 已在 Windows 實測通過

原本一行涵蓋三平台，展開後會把 `secret-service` 拉進**每個**目標並在 Linux 上
硬編譯失敗，導致 `cargo test --lib` 長期無法使用。改成：

```toml
[target.'cfg(windows)'.dependencies]
keyring = { version = "3", features = ["windows-native"] }
```

這個改動原本只在 Linux 上驗過，一度被列為本文件的最高風險項。**2026-08-02 在
Windows 11 / rustc 1.97.1 上實測 `cargo test --lib` 為 81 passed / 0 failed，
與 Linux baseline 相同——拆分成立，不需要回退。** 事前的推論也得到印證：對
Windows 是純減法（`windows-native` 本來就啟用，只是不再編譯兩個從未使用的
後端），而程式碼只用到 `Entry::new` / `set_password` / `get_password` /
`delete_credential` / `Error::NoEntry` 這幾個 backend 無關的 API。

保留備案供參：**若未來 `cargo test --lib` 失敗且錯誤與 keyring 有關**，刪掉
`app/src-tauri/Cargo.toml` 末尾那三段 `[target.'cfg(...)'.dependencies]`，
在 `[dependencies]` 內改回單行：

```toml
keyring = { version = "3", features = ["windows-native", "apple-native", "linux-native-async-persistent"] }
```

其餘所有變更與此無關，不必回退。背景見
[`linux-support.md`](linux-support.md) 第 1 節。

### 2. `binaries/` 被 gitignore，clone 下來是空的

`app/src-tauri/binaries/` 在 `.gitignore` 內，所以 Tauri 的 build script 會直接
報 `resource path binaries/sidecar-x86_64-pc-windows-msvc.exe doesn't exist`。

這是設計如此，不是漏檔：sidecar 由 `npm run sidecar:build`（PyInstaller）在
建置時產生，`build-release.ps1` 的 Step 1 就是它。驗證腳本也會先建。

需要 `pip install -r requirements-sidecar.txt`（PyInstaller / curl_cffi /
requests / beautifulsoup4，皆已釘版本）。

### 3. 日誌目錄（已由 `sidecar_manager.rs` 顯式注入 `JAVDB_LOG_DIR`）

`app_logging.py` 的候選順序是 `%JAVDB_LOG_DIR%` → `%LOCALAPPDATA%\JavDBMagnet\logs`
→ console-only。先前 Rust 端未設定 `JAVDB_LOG_DIR`，僅靠繼承 `%LOCALAPPDATA%` 巧合運作；
現已於 `sidecar_manager.rs` 的 `sidecar_command` 以 `.envs(sidecar_env(&paths))`
在 spawn 子行程時顯式帶入 `JAVDB_LOG_DIR`（值為 `PathManager.log_dir`）。

守住這條接線的測試在 `app/src-tauri/tests/sidecar_command.rs`（整合測試，
`cargo test --test sidecar_command`），它要建 mock App。mock App 會連結 comctl32
的 `TaskDialogIndirect`（只有 Common Controls v6 有），而 tauri-build 只替正式
執行檔嵌入 v6 manifest；沒有 manifest 的測試執行檔載入時會以
`STATUS_ENTRYPOINT_NOT_FOUND`（0xC0000139）失敗。`build.rs` 因此以
`cargo:rustc-link-arg-tests` 只替測試目標嵌入 v6 manifest，正式執行檔不受影響。
Cargo 在 package 沒有任何測試目標時會以 `invalid instruction` 拒絕這個參數，
所以 `build.rs` 只在 `tests/` 底下有 `*.rs` 或 `*/main.rs` 時才輸出它。這個判斷放在
`app/src-tauri/build_support.rs`，lib 單元測試會一併編譯並測它（`build_support::tests`）。
同一個原因，這類測試不能放在 lib 單元測試裡：`-tests` 連結參數不作用於
`cargo test --lib` 的執行檔。

### 4. Smart App Control 會擋掉 cargo 的 build script（2026-08-02 實遇）

Windows 11 的「智慧型應用程式控制」（Smart App Control，SAC）逐檔查雲端信譽，
會封鎖未簽章且無信譽紀錄的執行檔。cargo 每次編譯都會產生全新的
`build-script-build.exe`，正好落在這個範疇：

```
could not execute process `...\target\release\build\icu_normalizer_data-<hash>\build-script-build`
應用程式控制原則已封鎖此檔案。 (os error 4551)
```

**判別方式**（前者是政策狀態，後者是實際封鎖事件）：

```powershell
(Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\CI\Policy').VerifiedAndReputablePolicyState
Get-WinEvent -LogName 'Microsoft-Windows-CodeIntegrity/Operational' -MaxEvents 20
```

`VerifiedAndReputablePolicyState` 為 `1` 代表強制執行、`2` 為評估模式、`0` 為
關閉。事件 ID **3118**（Smart App Control Block）與 **3077** 會指名被擋的檔案。

**注意這不是確定性的**：同一台機器上，改動 `Cargo.toml` 之前的建置可以完全成功，
改動後產生的新二進位卻被擋——因為信譽是逐檔查的，不是逐專案。所以「昨天還能建」
不能用來排除這個原因。

**唯一解法是關閉 SAC**，它沒有例外清單或白名單機制。**這是單向操作：關閉後除非
重灌 Windows 否則無法再開啟**，且整台機器對未簽章執行檔的防護會永久失效。路徑是
設定 → 隱私權與安全性 → Windows 安全性 → 應用程式與瀏覽器控制 → 智慧型應用程式
控制。這個取捨要由機器的擁有者決定，不該由 agent 代為執行。

若不願關閉，替代方案是改在 CI（GitHub Actions `windows-latest`）上建置——
runner 預設不啟用 SAC。repo 目前只有 `sonarcloud.yml`，需要另外新增 workflow。

### 5. Windows PowerShell 5.1 讀不懂沒有 BOM 的 UTF-8（2026-10-15 實遇）

`npm run release`／`release:test`／`release:audit` 呼叫的是 `powershell`
（Windows PowerShell 5.1），不是 pwsh 7。5.1 讀取**沒有 BOM** 的腳本或用
`Get-Content` 讀檔（沒給 `-Encoding`）時，用的是系統 ANSI 編碼（這台是 cp950）。
中文註解與字串因此被讀壞：

- `test-release-scan.ps1`、`verify-windows-build.ps1` 直接 `ParserError`（5 與 20 個），
  在 pwsh 上卻完全正常——只在 pwsh 驗證的人看不到。
- `test-release-scan.ps1` 讀 `commands.rs` 時沒給 `-Encoding`，`COOKIES_TEMPLATE`
  被讀成亂碼，5.1 下多出兩個 binary allowlist 失敗。

規則：含非 ASCII 的 `.ps1` 一律存成 **UTF-8 with BOM**（`tests/test_ps1_encoding.py`
會擋）；`Get-Content` 讀任何可能含非 ASCII 的檔案都要寫 `-Encoding utf8`。
`verify-windows-build.ps1` 會在兩個 host 各跑一次 release-scan 測試，兩邊都要過。

---

## repo 內的 .exe 對應哪一版

| 檔案 | 狀態 |
|---|---|
| `javdbmagnet.exe`（root，有進 git） | 0.3.1，`build-release.ps1` 從 `b6857c6` 建出（2026-10-15） |
| `sidecar.exe`（root，有進 git） | 同一次建置的 release sidecar（24.8 MB）。之前那份 60.8 MB 是 2026-06 的 spike 建置，落後約 1000 行 Python 變更 |
| `app/src-tauri/binaries/sidecar-*.exe` | 未進 git，建置時重建 |

這兩個 exe 只是「上一次發布」的快照：root 下的版本對應 commit 寫在同一個 commit
的訊息裡，正式產物以 `release\release-manifest.json` 的 `git_commit` 為準。
程式碼在那之後若有改動，**不要直接雙擊 repo 裡的 exe 測試新功能**——先重新建置。

---

## 08-01 新增的功能，建置後值得手動確認

1. **送出前預判**：挑選分頁的「每組只留」下拉多了「RD 命中優先」，列上會有
   `⚡高清` / `⚡` / `高清` 徽章與 ★ 首選標記；旁邊有「只勾選 RD 優先候選」按鈕。
2. **送出前攔截**：批次含低機率列時，按送出會先出現摘要面板
   （高機率／低機率／未判定），可選「只送高機率」。
3. **成效日誌**：送出後 `%LOCALAPPDATA%\JavDBMagnet\logs\rd_outcomes.jsonl`
   應該多出一行。分析用 `python scripts\rd_log_report.py`。
   設 `JAVDB_RD_LOG=0` 可關閉。

最有價值的手動驗收仍是完整走一次
**pending → 全部重試（查 RD）→ completed**，確認完成時間欄與排序正確。

---

## 附帶

Rust 端的 lib 單元測試目前共 96 個（2026-10-16 Linux 實測 lib 96、`sidecar_command` 整合測試 2，全過；
2026-10-14 在 Windows 上 `cargo test --tests` 實測時為 lib 89，之後 PR #11 新增 7 個）。這個 gate 在 2026-08-01 之前
一直被記載為「本機編不過、只能人工細審」，現在可用了——動 Rust 前請跑它。
