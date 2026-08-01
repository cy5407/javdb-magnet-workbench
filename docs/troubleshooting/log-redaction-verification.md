# 確認 logs 目錄沒洩漏 magnet hash / token

## 為什麼這條 recipe 存在

M5 安全合約之一：**完整 magnet 文字（含 BTIH hash）絕不得進 log 檔**。歷史上有過一個 B1 bug：`realdebrid.py::_request` 在 DEBUG 等級記錄 `data["magnet"][:80]`，正好涵蓋完整 40 字 hash。修復 commit 是 [`1a604ae`](../../README.md)，現在 magnet key 一律記 `<redacted>`。

這條 recipe 教你怎麼自己驗證修復仍然生效，以及未來 refactor 出包時最快發現的方法。

## 掃描範圍：整個 logs 目錄，不只 debug.log

2026-08-01 起 log 目錄多了第二個檔案 `rd_outcomes.jsonl`（RD 送出成效日誌，
見 [`docs/specs/2026-08-01-rd-outcome-log.md`](../specs/2026-08-01-rd-outcome-log.md)）。
下列指令的路徑因此**從 `debug.log*` 擴大為 `logs\*`** —— 只掃 `debug.log` 會漏掉它。

該日誌在設計上就不得寫出 `magnet:?xt` / `urn:btih`：關聯鍵用裸 8 碼 hex
（`sidecar._btih8`），而不是 `redact_magnet()` 的輸出——後者的格式正好會命中本頁
第 [1] 條 pattern。寫出前另有 `rd_outcome_log._FORBIDDEN_RX` 逐行攔截作為
defense in depth。

這一點已有自動化測試守住，不必只靠手動 recipe：
`tests/test_rd_outcome_log_e2e.py::E2ERedactionGate` 會真的啟動 sidecar 子行程、
送出一筆，再用本頁第 [1] 條同樣的 pattern 掃過整個 log 目錄並斷言零命中
（含反向斷言，確保不是掃了空目錄就宣告通過）。

## 何時跑

- 每次更新版本後，跑過一次「送 RD」流程
- 看到別人擔心 magnet 洩漏到 log 想自證沒事
- M6a / RC smoke 流程的固定步驟
- 開啟 issue 想附 log 之前 —— **必跑**，確認附上去的內容沒帶 hash

## 快速驗證指令

PowerShell：

```powershell
# 1. 看 magnet:?xt / urn:btih hash 是否漏進 log
Select-String -Path "$env:LOCALAPPDATA\JavDBMagnet\logs\*" `
  -Pattern "magnet:\?xt|urn:btih"
```

**預期：無輸出**。任一命中 = 修復回退或新代碼引入新 leak path，**立刻** 開 issue + 不要把 log 貼任何地方。

```powershell
# 2. 看 redact 路徑有沒有確實在跑
Select-String -Path "$env:LOCALAPPDATA\JavDBMagnet\logs\*" `
  -Pattern "<redacted>"
```

**預期：有命中**（前提是這個 sidecar instance 有跑過送 RD）。命中行類似：

```
2026-05-11 12:34:56 [DEBUG] realdebrid: → POST /torrents/addMagnet {'data': {'magnet': '<redacted>'}}
```

無命中且你確定有跑過送 RD → 表示 `<redacted>` 那行沒被執行，可能：

- 你的 sidecar.exe 是舊版（B1 修復前 build），重 build 一次
- log level 被改成 INFO+，看不到 DEBUG（不影響安全，但驗證需要 DEBUG）

```powershell
# 3. 順便確認 RD token 沒外洩
Select-String -Path "$env:LOCALAPPDATA\JavDBMagnet\logs\*" `
  -Pattern "RD_API_TOKEN|Authorization:\s*Bearer\s+[A-Za-z0-9]"
```

**預期：無輸出**。Bearer header 應只在 `requests.Session` 內部記憶體存在，不該寫到 log。

```powershell
# 4. 確認 cookies 沒外洩
$cookiePatterns = @("cf_clearance" + "=", "_jdb_session" + "=")
Select-String -Path "$env:LOCALAPPDATA\JavDBMagnet\logs\*" `
  -Pattern $cookiePatterns
```

**預期：無輸出**。

## 一鍵跑 4 條（複製貼 PowerShell）

```powershell
$log = "$env:LOCALAPPDATA\JavDBMagnet\logs\*"
Write-Host "[1] magnet hash leak:"   -ForegroundColor Cyan
Select-String -Path $log -Pattern "magnet:\?xt|urn:btih"
Write-Host "[2] redacted hits:"      -ForegroundColor Cyan
Select-String -Path $log -Pattern "<redacted>" | Select-Object -First 3
Write-Host "[3] RD token leak:"      -ForegroundColor Cyan
Select-String -Path $log -Pattern "RD_API_TOKEN|Authorization:\s*Bearer\s+[A-Za-z0-9]"
Write-Host "[4] cookies leak:"       -ForegroundColor Cyan
$cookiePatterns = @("cf_clearance" + "=", "_jdb_session" + "=")
Select-String -Path $log -Pattern $cookiePatterns
```

四段全部「無輸出 + 第 [2] 段有 `<redacted>` 命中」 = pass。

## 萬一掃到東西

1. **不要 panic、也不要把 log 貼到任何地方**（包括 issue / Discord / 群組）
2. 把命中行的整段檔名與位置記下來
3. `cd %LOCALAPPDATA%\JavDBMagnet\logs && del debug.log*`（先把現場清掉，避免持續累積）
4. 開 issue 描述：
   - 你的版本 / commit hash
   - pattern 哪一條命中
   - 觸發步驟（送什麼樣的磁力 / 操作哪條 RD 流程）
   - **不要附整份 log**；可以附「命中行的脫敏摘要」（hash 用 `[REDACTED]` 取代）

## 自動化（可選）

如果你想每天背景跑一次自我檢查：

1. Claude Code 內：「Routines」開一個 Daily 工作（早上 8:00 之類），instructions 貼上上面那段「一鍵跑 4 條」指令 + 「若 [1][3][4] 任一有輸出立即回報，否則一句 ✓ 帶過」
2. 純 Windows：用工作排程器（taskschd.msc）+ PowerShell script + Toast 通知

固定值守可以最早抓到「我以後不小心引入 leak」這類迴歸。
