# Codex 審查紀錄 — release 機密掃描

## 這份紀錄能證明什麼、不能證明什麼

**能證明**：`scripts/build-release.ps1` 的 source scan 與 binary scan 兩條路徑，
在 Linux／pwsh 7.6.4 下有可執行的紅測覆蓋，且每一項發現都經獨立重現後才修。

**不能證明**：

- 正式 release 的完整路徑（PyInstaller → cargo → staging → ZIP → hash →
  manifest）**從未在本機跑過**。測試只走 `-AuditOnly` 與 `-AuditBinary`。
- **Windows PowerShell 5.1 從未執行過任何一項**。`npm run release` 走的正是
  5.1，而本機只有 pwsh 7。`scripts/verify-windows-build.ps1` 已加入「兩個 host
  各跑一次」的關卡，但那要在 Windows 上才跑得到。
- 本檔前一版曾宣稱「掃描的所有路徑都有可執行的紅測覆蓋」——那句話是錯的，
  已刪除。

Windows 最終驗收仍須實跑一次真正的 `build-release.ps1`。

---

## 起點

外部審查對 `07d9b93` 提出 7 項，含一個必定失敗的 release blocker
（`$ManifestPath` 宣告在一次替換中被連帶刪除）。修正後交由 `codex review`
反覆複審。

## 逐輪紀錄

「findings」為該輪 Codex 回報的相異 P0–P3 項數。第 5–9 輪當時未逐一記下被審
SHA，只能標為「中間 commit」——這是本紀錄被要求重寫的原因之一。

| 輪 | 被審 SHA | 命令 | findings | 主要內容 |
|---|---|---|---|---|
| 2 | `3f55ec0` | `--commit` | 2 | P0 掃描計數變函式區域變數；P2 UTF-16BE 未涵蓋 |
| 3 | `b5481f5` | `--commit` | 0 | 測試 payload 拆分後掃描器不再自我命中 |
| 4 | `87ea17e` | `--base 07d9b93` | 2 | P0 binary scan 對 exe 自身範本失敗；P2 變體重複計數 |
| 5 | 中間 commit | `--base 07d9b93` | 2 | P0 `$AllowedLiterals` 定義在函式內；P2 allowlist 前綴繞過 |
| 6 | 中間 commit | `--base 07d9b93` | 2 | P2 引號版前綴繞過；P2 UTF-32 未涵蓋 |
| 7 | 中間 commit | `--base 07d9b93` | 1 | P1 binary 值類別吃掉相鄰位元組 |
| 8 | 中間 commit | `--base 07d9b93` | 1 | P2 binary 空白終止重開前綴繞過 |
| 9 | 中間 commit | `--base 07d9b93` | 1 | P1 TAB 被 production 接受但被掃描排除 |
| 10 | `7983be2` | `--base 07d9b93` | 0 | 「No actionable regressions were found」 |

各輪 findings 標題原文保留於本檔末尾。

## 第 10 輪之後：0 findings 不等於雙方無異議

第 10 輪 Codex 回報 0 findings，但隨後一輪獨立檢查又提出 7 項（2 項 P1），
**全部成立並已修正**：

| # | 等級 | 內容 | 重現方式 |
|---|---|---|---|
| 1 | P1 | VT／FF／NBSP 被 `strip()`／`trim()` 接受，掃描只認 space／TAB | 直接呼叫 `parse_cookie_string` 三種空白皆解析成功 |
| 2 | P1 | `assume-unchanged`／`skip-worktree` 只在建置前檢查 | 建置中途設旗標後 porcelain 仍空 |
| 3 | P2 | binary scan 繼承整份 source allowlist | 把 allowlist 內的 40-hex magnet 寫入假 binary，`-AuditBinary` exit 0 |
| 4 | P2 | 無 BOM 的 UTF-32 仍漏掃 | 無 BOM UTF-32LE 檔內植 magnet，`-AuditOnly` exit 0 |
| 5 | P2 | Bearer／magnet 長度下限仍比 production 窄 | `register_magnets` 接受 3 碼 infohash，掃描 exit 0 |
| 6 | P2 | 測試 runtime 與正式 runtime 不一致，且未接入 gate | 測試呼叫 `pwsh`，`npm run release` 呼叫 `powershell` |
| 7 | P3 | 本紀錄不足以支持其結論 | 本次重寫 |

這一輪的教訓比修正本身重要：**單一審查者回報 0 findings，不足以支持「沒有
問題」的結論**。其中「掃描器的 grammar 不得窄於 production parser」這條原則，
前面十輪都只被部分套用——每次只補了當下被指出的那一種字元或長度。

## 我自己造成的缺陷

這些不是外部發現的，是修正過程中我自己引入的，一併記錄因為它們有共同模式：

| 缺陷 | 模式 |
|---|---|
| `$ManifestPath` 宣告被替換錨點連帶刪除 | 編輯錨點含了不該動的行 |
| 掃描計數變函式區域變數 | **重構改變變數綁定** |
| `$AllowedLiterals` 同上（第二次） | 同上 |
| binary scan 未實際改用 `$BinaryAllowedLiterals` | **替換靜默失敗，未驗證就宣告完成** |
| `{40}(?!hex)` 讓 42 碼**完全不匹配** | 修補反而擴大破洞 |
| Python `unicode_escape` 往返破壞產生錯誤 allowlist | **用壞掉的工具驗證** |
| UTF-32 判準用低位位元組，對 CJK 失效 | 啟發式只在 ASCII 樣本上想過 |

共同點是「推理或重構未經執行驗證」。本機在此期間安裝了 pwsh 7.6.4；之後每一項
修正都以實跑驗證，上表有數個是紅測自己抓到的，Codex 並未提及。

## 現況

- `scripts/test-release-scan.ps1`：37 項，pwsh 7.6.4 下全綠
- 掃描覆蓋：113 個受追蹤文字檔；整檔豁免 1 個（allowlist 資料檔本身）
- 維護：`-DumpUnmatched <path>` 可精確重建 allowlist，不必猜測
- gate：`verify-windows-build.ps1` 於 `powershell` 與 `pwsh` 兩個 host 各跑一次
  測試；`npm run release:test` / `release:audit` 可單獨執行

---

## 附錄：各輪 findings 標題原文

### 第 2 輪
- [P0] Return source-scan metrics from the function
- [P2] Decode BOM-marked UTF-16BE source files

### 第 4 輪
- [P0] Exclude the built-in cookie template from binary matches
- [P2] Deduplicate raw and percent-decoded scan variants

### 第 5 輪
- [P0] Define the allowlist before scanning binaries
- [P2] Match complete cookie values before allowlisting

### 第 6 輪
- [P2] Decode UTF-32 tracked text before scanning
- [P2] Validate the full binary value before allowlisting

### 第 7 輪
- [P1] Stop cookie matches at binary string boundaries

### 第 8 輪
- [P2] Avoid truncating binary cookie values before allowlisting

### 第 9 輪
- [P1] Preserve accepted control bytes in binary cookie matches

### 第 10 輪
（無 findings）

> 只記標題與位置。Codex 的完整 stdout 另含它自身執行的 audit-log dump，屬雜訊
> 且會觸發 release 機密掃描，故不收錄。
