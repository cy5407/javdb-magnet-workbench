# Codex 審查紀錄 — release 機密掃描

## 這份紀錄能證明什麼、不能證明什麼

**能證明**：`scripts/build-release.ps1` 的 source scan 與 binary scan 兩條路徑，
在 Linux／pwsh 7.6.4 下有可執行的紅測覆蓋。第 12 輪起每一項修正都額外做了
**突變測試**——把修法逐一還原，確認對應的紅測轉紅——所以「有測試」這件事本身
也被驗過，不是靠讀測試名稱推斷。`scripts/verify-windows-build.ps1` 本輪的三處
改動也在 Linux 上實跑到（以 `python` shim 通過環境檢查後執行）。

**不能證明**：

- 正式 release 的完整路徑（PyInstaller → cargo → staging → ZIP → hash →
  manifest）**從未在本機跑過**。測試只走 `-AuditOnly` 與 `-AuditBinary`。
- **Windows PowerShell 5.1 從未執行過任何一項**。`npm run release` 走的正是
  5.1，而本機只有 pwsh 7。`scripts/verify-windows-build.ps1` 的「兩個 host 各跑
  一次」關卡本輪已改為「Windows 上缺 5.1 即失敗」，但那要在 Windows 上才跑得到；
  在 Linux 上它走的是警告分支（已實跑確認）。
- 本檔前一版曾宣稱「掃描的所有路徑都有可執行的紅測覆蓋」——那句話是錯的，
  已刪除。前一版也宣稱外部提出的 7 項「全部成立並已修正」，同樣不實：其中
  至少 4 項在下一輪被證明只修了一半或根本未修。

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
| 10 | `7983be2` | `--base 07d9b93` | 0 | 「No actionable regressions were found」——**後續兩輪外部檢查證明此結論不成立** |

各輪 findings 標題原文保留於本檔末尾。

## 第 10 輪之後：0 findings 不等於雙方無異議

第 10 輪 Codex 回報 0 findings。此後**兩輪獨立外部檢查各再提出 7 項**，兩輪都
推翻了前一輪「已修正」的宣告；第 13 輪 Codex 又在第 12 輪的修正裡找到 2 項，
其中 1 項是 P1；第 14 輪再找到 2 項，兩項都是「測試本身無法失敗」；第 15 輪再
找到 1 項 P1；第 16 輪 2 項；第 17 輪 1 項；第 18 輪 1 項；第 19 輪 0 項。這一節記錄這九輪的
內容與實際結局。findings 數依序為 7 → 7 → 2 → 2 → 1 → 2 → 1 → 1 → 0。

### 第 11 輪（對 `7983be2`）

| # | 等級 | 內容 | 這一輪的結局 |
|---|---|---|---|
| 1 | P1 | VT／FF／NBSP 被 `strip()` 接受，掃描只認 space／TAB | 改用 `[^\S\r\n]`——**仍不足**，見第 12 輪第 1 項 |
| 2 | P1 | `assume-unchanged`／`skip-worktree` 只在建置前檢查 | 建置前後各檢查一次，已修 |
| 3 | P2 | binary scan 繼承整份 source allowlist | 改為前綴過濾——**仍不足**，見第 12 輪第 5 項 |
| 4 | P2 | 無 BOM 的 UTF-32 仍漏掃 | 判準改測高位位元組，已修 |
| 5 | P2 | Bearer／magnet 長度下限仍比 production 窄 | magnet 已降到 1；**Bearer 的替換靜默失敗而我回報為已修** |
| 6 | P2 | 測試 runtime 與正式 runtime 不一致，且未接入 gate | 測試改用同 host——**gate 串接未做**，見第 12 輪第 6 項 |
| 7 | P3 | 本紀錄不足以支持其結論 | 重寫一次——**內容仍不實**，見第 12 輪第 7 項 |

### 第 12 輪（對 `c971d74`）

七項全部經**執行**重現後才修；第 7 項是本節的重寫。

| # | 等級 | 內容 | 重現與修法 |
|---|---|---|---|
| 1 | P1 | 空白類別漏 U+001C–U+001F：.NET `\s` 排除，Python `strip()` 移除 | 分隔符類別改為**從 production 的接受集合生成**（`chr(c).strip()==''` 扣掉 CR／LF，共 27 個字元），不再手選代表字元 |
| 2 | P2 | 原子群 + 省略號前瞻豁免過寬：`<hash>...<真實尾碼>` 得到零命中 | 移除該豁免；redacted 形式改以**完整字面量**進 allowlist，且值類別納入 `.`，否則兩者化約成同一個值、破洞只是從 regex 搬到 allowlist |
| 3 | P2 | Bearer 下限仍是 8／16——**我上一輪回報「全部降到 1」是不實陳述**，替換錨點根本不存在於檔案中，靜默失敗 | 兩條 pattern 皆改為 `{1,}`，並以突變測試確認 |
| 4 | P2 | 編碼判別只抽樣前 1024 bytes：純 CJK 開頭的 BOM-less UTF-16LE 探測窗內無 NUL | 改掃全檔。順帶移除該函式末尾一行不可達的 `return` |
| 5 | P2 | `$BinaryAllowedLiterals` 是 source 清單的前綴過濾，仍放行 23 條含原始碼語法的 fixture | allowlist 資料檔改為 `# [source]` ／ `# [binary]` 兩區；binary 區收斂到 6 條，並加入**窮舉**斷言：每條都必須出現在 `COOKIES_TEMPLATE` 內 |
| 6 | P2 | `npm run release` 未依賴 `release:test`；`-SkipSlow` 連掃描一起關掉卻只說會略過 cargo／sidecar；單 host 只警告卻仍 PASS | `release` 串接 `release:test`；掃描 gate 移出 `-SkipSlow`；Windows 上缺 5.1 改為 Bad |
| 7 | P3 | 本紀錄宣稱「全部成立並已修正」與事實矛盾、項數寫錯、`git diff --check` 不過 | 本節重寫；項數改由實跑輸出填寫；trailing whitespace 已清 |

### 第 13 輪（Codex，`codex review --uncommitted`，對第 12 輪的修正）

Codex 提出 2 項，兩項都以執行重現後才修。**兩項都是第 12 輪的修正自己引入的**
——修 bug 的動作本身就是新的變更，必須同樣被審。

| # | 等級 | 內容 | 重現與修法 |
|---|---|---|---|
| 1 | P1 | 5f 的 Python 解析器用 `(Get-Command ...).Source`，在 `Set-StrictMode -Version Latest` 下對 `$null` 取屬性會 throw。而候選清單第一項是 Linux 佈局的 `.venv/bin/python`，Windows checkout 沒有這個檔——**於是套件在正式出貨的那個平台上直接死掉**，且因為第 12 輪剛把 `release:test` 串進 `npm run release`，等於每一次 Windows release 都會中止 | 隔離重現確認 throw；改成先檢查 `$null -ne $cmd` 的 `Resolve-FirstExecutable`，並加入一條**自我測試**：全部候選都不存在時必須回傳 `$null` 而非 throw |
| 2 | P2 | dump 截斷的 `Remove-Item` 寫在 `$ErrorActionPreference = "Stop"` **之前**，刪除失敗只是 non-terminating error，接著照樣附加到舊內容上 | 移到 preference 之後並加 `-ErrorAction Stop`。實跑時另外發現更糟的一面：dump 路徑若是目錄，`Remove-Item` 會**跳出互動確認**，非互動環境下不是掛起就是死於無意義的 null reference——比它要防的 stale-append 更糟。改為明確拒絕目錄路徑並 `-Confirm:$false` |

第 2 項的實跑發現值得單獨記：Codex 指出的是「刪除失敗不會中止」，我照著修完
**跑一次**，才看到真正的行為是互動提示。只照審查意見改而不執行，會得到一個
仍然錯誤但看起來已修的版本。

這一輪的突變測試也留下一個教訓：M8（移除目錄檢查）讓測試套件卡在等待輸入，
突變工具本身沒有把被突變的檔案備份、也沒有關閉 stdin，於是逾時被移到背景、
突變殘留在工作樹裡。後續改為手動逐項執行、`</dev/null`、逐項還原後複驗。

### 第 14 輪（Codex，對第 13 輪的修正）

Codex 提出 2 項，**兩項都是「測試本身無法失敗」**——這正是「測試也是被審對象」
這條鐵律要防的東西，而兩項都是我第 13 輪新寫的測試。

| # | 等級 | 內容 | 重現與修法 |
|---|---|---|---|
| 1 | P2 | 「repo restored」用 `git status --porcelain` 標籤比對。已經是 ` M` 的檔案內容再怎麼變，標籤還是 ` M`——**探針寫進一個正在編輯中的檔案而未還原時，檢查會回報成功** | 以 `README.md`（當時本來就 dirty）實測：porcelain 前後完全相同，`git diff HEAD` 內容不同。改為快照 patch 全文，porcelain 只留著抓 untracked 檔案的增減 |
| 2 | P3 | 5k 的「no source-only fixture sits in the binary section」先把 binary 區的值全部從 source 集合濾掉，再到剩下的集合裡找 binary 區的值——**恆為空，任何輸入都不可能失敗** | 隔離重現確認恆為空。改為行為抽樣：每個 pattern family 各取一條 source-only 條目，實際寫進假 binary 並要求被拒；抽樣數與母體數印在輸出裡，不讓讀者誤以為窮舉 |

**第 2 項的修法立刻抓到兩個原本看不見的問題**，這是空斷言換成真斷言的直接收益：

1. 新測試碼裡直接拼出兩個 cookie 名稱的賦值字面量，讓 source scan 命中測試檔
   自己。依既有 payload 拆分慣例改寫。（本檔改寫時又犯了同一個錯一次——寫下
   那兩個字面量當例子，掃描立刻轉紅。這類文件只能敘述、不能舉字面量為例。）
2. allowlist 裡有一條 `Bearer ␣`（尾隨空白）是現行 pattern 產不出來的**失效條目**。

第 2 點揭露一個更大的維護缺口：`-DumpUnmatched` 只找「該加什麼」，**沒有任何
機制找「該刪什麼」**。失效條目是永久豁免，日後同名真值出現就會被直接放行。
加上死條目偵測後，一次報出 **79 條**失效條目——多為早期輪次值類別較窄時記下
的短值，類別放寬後匹配結果變長，舊條目再也對不上而無人察覺。全部移除後掃描
仍為 307 條命中、`[PASS]`，證實確實是死重。

死條目斷言第一版**也是假綠**：它只讀掃描器的輸出，突變測試把偵測器關掉之後
斷言照樣通過。加上正控制（注入一條保證匹配不到的條目，必須被指名報出）才殺
得掉這個突變。

### 第 15 輪（Codex，對第 14 輪的修正）

1 項，P1，同樣是我新寫的測試造成的，而且同樣**只在正式出貨平台上發作**。

| # | 等級 | 內容 | 重現與修法 |
|---|---|---|---|
| 1 | P1 | 死條目偵測的正控制用 `"`n# [binary]`n"` 這個硬編 LF 標記找插入點。Windows 常見的 `core.autocrlf=true` checkout 下這個檔是 CRLF，標記永遠找不到，canary 被附加到 binary 區之後——source 偵測器正確地忽略它，於是正控制失敗。因為 `release:test` 已是必跑關卡，**這會擋掉 CRLF checkout 上的每一次 `npm run release`** | 把 allowlist 整份轉成 CRLF 後重跑，得到 PASS 66 / FAIL 1，與 Codex 描述一致。改為以「行」為單位定位 `# [binary]` 區並插入，不依賴任何行尾字元；另加 5q 一節，把整份 allowlist 轉 CRLF 後要求掃描、死條目偵測與區段標頭辨識三者行為不變 |

值得注意的是這與第 13 輪的 P1 是**同一類**缺陷：本機（Linux／LF）跑得好好的
測試，在正式出貨的平台上必定失敗，而且是因為第 12 輪把 `release:test` 串進
`npm run release` 才變成 release blocker。把測試接進出貨路徑提高了它的價值，
也提高了它自身缺陷的代價——這一點在做那個串接時沒有被考慮到。

### 第 16 輪（Codex，對第 15 輪的修正）

2 項，都成立。第 1 項揭露我上一輪的關卡串接**放錯層級**。

| # | 等級 | 內容 | 重現與修法 |
|---|---|---|---|
| 1 | P1 | 關卡掛在 `npm run release` 這個 wrapper 上，但 `docs/platform/windows-build.md` 教的正是直接跑 `pwsh -File scripts\build-release.ps1`——**那條路完全繞過紅測**。被文件記載的入口能繞過的東西不算關卡 | 關卡改放進打包腳本本身（Step 0），兩個入口都會跑到；`-AuditOnly` / `-AuditBinary` 排除在外，因為紅測本身就是用這兩個模式呼叫該腳本，會無限遞迴（已實測確認 audit 模式不出現 Step 0）。README 與 windows-build.md 同步更新 |
| 2 | P2 | 失效條目報告把完整值印進 console／CI log。我原本的註解寫「匹配不到就不在 repo 裡，可以安全印出」——但「已經不在 repo 裡」正好是**誤加進 allowlist 後又被移除的真憑證**的形狀 | 改為只印「行號 + sha256 前 12 碼」。以一條假憑證實測：輸出 0 次包含該值。同時加斷言「報告不得回顯值本身」 |

第 1 項與第 12 輪第 6 項是同一個問題的兩層：那一輪我把關卡從「沒有」升級成
「掛在 wrapper 上」，就宣告修好了。**驗收時只驗了 npm 這條路，沒有列舉所有
產出 artifact 的入口。**

### 第 17 輪（Codex，對第 16 輪的修正）

1 項，P2。**我上一輪新加的偵測器本身有一個它偵測不到的缺陷類別。**

| # | 等級 | 內容 | 重現與修法 |
|---|---|---|---|
| 1 | P2 | 死條目偵測用一般的 PowerShell hashtable 記錄「哪些 allowlist 條目被用到」，而 hashtable 預設**大小寫不敏感**；比對本身卻用 `-ccontains`（大小寫敏感）。於是只有大小寫不同的兩條，只要其中一條還在被匹配，另一條就被當成「已使用」，永遠不會被報為失效——而這份 allowlist 本來就刻意存有數組大小寫變體（`magnet:` 與 `MAGNET:`） | 實地重現：加入一條只有大小寫不同的失效條目，警告數為 0。改用 `StringComparer::Ordinal` 的 `HashSet`；`$AllowLineNumbers` 也一併改（兩個變體撞 key 會報出錯誤行號） |

值得記的是**紅測為什麼沒抓到**：5p 的 canary 是一條「repo 裡完全不存在的值」，
它只能證明偵測器有在運作，證明不了偵測器的比較語意正確。補上第二個 canary
（某條仍在被匹配的條目的大寫變體）之後才涵蓋到這一類。一個正控制不等於
覆蓋——控制組要跟著缺陷的形狀走。

### 第 18 輪（Codex，對第 17 輪的修正）

1 項，P2。是第 16 輪修法的殘留。

| # | 等級 | 內容 | 修法 |
|---|---|---|---|
| 1 | P2 | 第 16 輪把關卡搬進 `build-release.ps1` 的 Step 0，卻沒有把 `npm run release` 上的舊串接拿掉，於是主要出貨路徑把整套 75 項**跑了兩次**，沒有換到任何額外覆蓋 | 移除 wrapper 層串接（`release:test` 保留供單獨執行）。5m 的斷言隨之反轉：從「必須串接」改為「不得串接，且關卡在腳本內」 |

搬移一道關卡不是只把它加到新位置，還要把舊位置拆掉；我上一輪只做了前半。

### 第 19 輪（Codex）：0 findings —— 以及為什麼不把它當結論

Codex 回報「No actionable defects found」。第 10 輪也是 0，隨後兩輪各再出現
7 項，所以這裡只記錄事實，不宣告「沒有問題」。

程式碼在第 12–18 輪之間改動很大（掃描器、測試套件、allowlist 資料格式、gate
位置都動過），早先逐項驗過的守護有可能在後續改動中悄悄失效——而這是逐輪 diff
review 天生看不到的：每一輪的 diff 都是對的，守護卻可能在累積過程中被架空。

因此另外做了一次**全突變回歸**：把第 12–18 輪的 14 項修法逐一還原，確認對應
紅測仍會轉紅。

| 突變 | 還原的修法 | 結果 |
|---|---|---|
| M1 | 分隔符改回 .NET `[^\S\r\n]`（13 處） | 轉紅，指名 U+001C–001F |
| M2 | magnet 值類別移除 `.` | 轉紅 |
| M3 | Bearer 下限改回 `{16,}`（2 處） | 轉紅（3 項） |
| M4 | 編碼偵測改回 1024 抽樣 | 轉紅 |
| M5 | binary allowlist 改回繼承 source | 轉紅（6 項） |
| M7 | resolver 改回直接取 `.Source` | 轉紅 |
| M8 | dump 目錄檢查移除 | 轉紅 |
| M9 | 5f 探針不還原 | 轉紅（內容快照與 untracked 兩項都抓到） |
| M10 | 死條目偵測關閉 | 轉紅（2 項） |
| M11 | CRLF 區段標頭比對改為永不匹配 | 轉紅 |
| M12 | Step 0 失敗分支移除 | 轉紅 |
| M13 | 失效條目改印完整值 | 轉紅 |
| M14 | usage 追蹤改回大小寫不敏感 | 轉紅 |
| M15 | npm wrapper 把串接加回 | 轉紅 |

14 / 14 全部被察覺。這證明的是「這些守護目前有效」，不是「沒有其他缺陷」。

### 這兩輪的教訓

前十一輪反覆出現同一個失效模式：**每次只補當下被指出的那一個字元或那一個長度**。
第 12 輪第 1、3、5 項全都是同一條原則的重犯——掃描器的 grammar 不得窄於
production parser。因此這一輪不再逐點補洞，改成讓邊界由 production 自己生成
（見 `scripts/test-release-scan.ps1` 的 5f 節）。

另一個教訓針對我自己：第 11 輪第 5 項的「已修正」是我在**未執行驗證**下作出的
回報，而替換其實靜默失敗。這一輪每一項修正都做了突變測試——把修法逐一還原，
確認對應的紅測轉紅。過程中抓到兩個假綠：

- 5j（編碼探測）原本用 `"# " + CJK` 當填充，而 `"# "` 在 UTF-16LE 下自己就在
  前四個位元組放了 NUL，1024 探測窗照樣命中——這個測試對它要抓的 bug 完全無效。
  改成純 CJK 後才真的轉紅。
- M3 第一次突變只改到兩條 Bearer pattern 中的一條，另一條仍攔得住，看起來像
  「無測試察覺」。兩條都改才顯示三項紅測轉紅。

單一審查者回報 0 findings，不足以支持「沒有問題」的結論；我自己回報「已修正」
而未執行驗證，同樣不足以。

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

以下數字取自實跑輸出，非估計：

- `scripts/test-release-scan.ps1`：**76 項，pwsh 7.6.4 下 PASS 76 / FAIL 0**；
  把 allowlist 整份轉成 CRLF 後重跑同樣全綠
- 突變測試：第 12–18 輪共 14 項修法，在**所有修正完成後**一次性全部還原重驗，
  14 / 14 皆被紅測察覺（M1–M15，M6 已被 M12／M15 取代）。
  其中 M8、M10 第一次執行時未被察覺，追查後分別發現突變工具沒關 stdin、以及
  死條目斷言缺正控制——**突變測試自己也需要被驗證**
- 掃描覆蓋：113 個受追蹤文字檔；整檔豁免 1 個（allowlist 資料檔本身）
- allowlist：`# [source]` 區為原始碼 fixture（已剔除 79 條失效條目）；`# [binary]`
  區 6 條，全部經斷言確認出現在 `COOKIES_TEMPLATE` 內
- 新增死條目偵測：任何匹配不到東西的 allowlist 條目會被列名警告，並由帶正控制
  的測試守住
- 專案 gate：pytest 415 passed、vitest 255 passed、svelte-check 0 errors 0 warnings
- gate 位置：紅測跑在 `build-release.ps1` 的 Step 0，**任何**產出 artifact 的
  入口都會經過，且只跑一次；`npm run release:test` 保留供單獨執行；audit 模式
  排除以免遞迴
- 維護：`-DumpUnmatched <path>` 可精確重建 allowlist；該檔在每次執行開頭會被
  截斷，先前是附加寫入，會把上一次的舊值混進待審清單

### 降低下限的代價，須明說

Bearer 下限降到 1 之後，文件與註解裡任何「Bearer <單字>」的英文散文都會成為
命中，必須進 allowlist（本輪就新增了 `Bearer token`、`Bearer floor` 等數條）。
這是與 production grammar 對齊的必然代價，不是缺陷；但它讓 allowlist 會隨文件
增長，且**新寫的說明文字可能讓掃描轉紅**。遇到時的正確處置是改寫該段文字或
加入 allowlist，不是把下限調回去。

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
