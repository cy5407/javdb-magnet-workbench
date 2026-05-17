# Task: 完成順序排序 — pending 重試後可分辨新完成的下載連結

Date: 2026-05-17
Status: 計畫待確認，未開工

## 問題（使用者描述）

> 我先送出 10 個磁力給 RD，當下完成 5 個，另外 5 個進入待處理清單。
> 我按「全部重試」，重試後系統給我 10 個連結，但是照送出順序排列，
> 所以我無法分辨剛剛這 5 個新完成的下載連結是哪 5 個。
> 希望可以重新排序，照著完成順序提供給使用者。

## 現況拆解（已驗證）

**「10 個連結」實際上有兩條路徑：**

1. **「複製全部已完成」按鈕** — `app/src/App.svelte:660-666` 的 `copyAllCompletedLinks()`，
   走 `rdSendProgress[]` 陣列順序（**= 送出順序**），把所有 `status==="completed"` 的 row
   依序展開成連結陣列。
2. **「全部重試」流程結束時** — `app/src/App.svelte:706-797` 的 `retryAllPending()`，
   收集 `completedLinks`（= 本輪新完成的）並直接寫剪貼簿。**這一條本來就只包含新完成的**，
   不是使用者抱怨的對象。

**為什麼路徑 1 看不出哪些是剛完成的：**
重試流程內，當某個 pending row 完成時，會「原地」改 `rdSendProgress[i]` 為 completed（line 727-737）。
所以「複製全部已完成」之後拿到的 10 個連結，按 `rdSendProgress[]` 陣列順序排列（= 原始送出順序），
新舊完成的混在一起，視覺與順序上無法區分。

**`rdSendProgress` row 沒有完成時間欄位：** 無法事後排序。

**pending 端有時間欄位：** `app/src-tauri/src/pending.rs:21-53` 的 `PendingEntry`
有 `added_at` / `last_checked_at`，但「初次送出當下就完成」的 5 個從未進 pending，因此沒有
任何時間紀錄。

## 期望行為

「複製全部下載連結」與「顯示」流程應該能依**完成時間升序**排列：
- 最早完成的（通常是初次送出就成功的）在前
- 最近一輪剛完成的在最後 — 使用者一眼看到「最後幾個就是這次重試補上的」

## 提議實作（最小變更路徑）

### 1. 在 `RdSendProgressRow` 加 `completed_at` 欄位

`app/src/lib/types.ts` 的 `RdSendProgressRow`（或同等型別）加：
```ts
completed_at?: string;  // ISO-8601 UTC，僅在 status === "completed" 時設置
```

### 2. 在所有「row → completed」的轉換點寫入時間戳

- **初次送出完成路徑** — `App.svelte` 處理 `rd_send_magnet` 回傳的「完成」row 時，
  在轉成 `rdSendProgress` row 前 `completed_at: new Date().toISOString()`。
  找：`rd_send_magnet` 相關回呼處理。
- **重試完成路徑** — `App.svelte:727-737` 原地改寫 row 為 completed 時，加
  `completed_at: new Date().toISOString()`。
- **任何其他可能讓 row 轉 completed 的路徑** — 需 grep `status: "completed"` 在
  `app/src/` 與相關 lib 內全找一次。

### 3. 修改「複製全部」與顯示排序

在 `copyAllCompletedLinks()`（`App.svelte:653` 附近）展開連結前，先把
`rdSendProgress[]` 中 `status === "completed"` 的 row **依 `completed_at` 升序穩定排序**
後再展開。沒有 `completed_at` 的 row（理論上不該出現）排到最後並保持原相對順序。

**不修改 `rdSendProgress` 陣列本身的順序** — 表格顯示維持送出順序（這是 UI 預期；
「複製連結」與「呈現結果」採用 completion order）。

### 4. 顯示層提示（可選，本任務可不做但要在 PR 描述提到）

考慮在 `rdSendProgress` 表格的 completed row 旁邊顯示完成時間（mm:ss 相對或絕對），
讓使用者直接從 UI 看出順序差異。

## 開放決策（請使用者拍板）

| # | 決策 | 預設提案 | 替代方案 |
|---|---|---|---|
| D1 | 排序方向 | 升序：最早完成在前、最新完成在後 | 降序：最新完成置頂 |
| D2 | `completed_at` 何處時鐘 | 前端 `new Date()`（簡單，與真正完成時間有 ms 級延遲） | 後端 sidecar 設置（更準但要改 Rust/Python） |
| D3 | 套用範圍 | 只改「複製全部下載連結」 | 同時改「複製」與表格顯示順序 |
| D4 | App restart 持久性 | 不持久化 — 重啟後 `rdSendProgress` 本來就會清空 | 寫入 `completed_torrents.json` 歷史檔（超出本任務） |
| D5 | 第一輪 5 個無時間戳 row 如何處理 | 全部視為「批次起點」=送出當下時間 | 拒絕排序、保留送出順序 |

預設值我會建議 **D1 升序、D2 前端、D3 只改複製、D4 不持久化、D5 批次起點**。
這條路最小、不動 Rust/Python，2-3 小時工。

## 影響範圍

- `app/src/App.svelte`（主要）
- `app/src/lib/types.ts`（型別欄位）
- `app/src/lib/rdSender.ts`（可能要在 `RdSendProgressRow` 工廠加 `completed_at`）

**不需動：**
- `app/src-tauri/src/`（Rust 後端）
- `sidecar/sidecar.py`、`realdebrid.py`（Python）
- `app/src-tauri/src/pending.rs`（pending store）

## 驗收條件

1. 送 10 個磁力、5 立即完成、5 進 pending、重試後 5 個完成：
   按「複製全部下載連結」拿到的 10 條順序符合：[初始 5 完成 → 重試 5 完成]，
   各自批次內維持送出/完成觸發順序。
2. `app/src/lib/rdSender.test.ts` 既有 38 個測試維持通過。
3. 新增至少 2 個前端純函式測試：
   - 排序穩定性（兩個 `completed_at` 相同的 row 維持送出順序）
   - 缺欄位處理（無 `completed_at` 的 row 排到最後並穩定）
4. 手動測試（描述步驟在 PR）：模擬上述 10 個情境，目視確認剪貼簿順序。
5. `npm run check`（svelte-check）無新 type error。
6. `tsc --noEmit`（若 CI 有）通過。

## 不做（明確排除）

- 不引入 `completed_at` 到後端 sidecar 與 RD layer（D2 預設選前端）。
- 不寫歷史檔（D4 預設不持久化）。
- 不改「全部重試」剪貼簿輸出（路徑 2 — 那條本來就只含本輪新完成的，沒有混淆問題）。
- 不改表格 row 顯示順序（D3 預設不動）。
- 不重構 `rdSendProgress` 為 `Map` 或其他結構（變更面太大）。

## 任務 prompt（給 AI worker 用）

完成上述決策確認後，給 worker 的 prompt 草稿（待 D1-D5 拍板後填空）：

```
在 C:\Users\cy5407\Desktop\程式語言\爬蟲 內實作 Task.md 的「完成順序排序」任務。

決策參數：
- D1 排序方向：<升序/降序>
- D2 時鐘：前端 `new Date().toISOString()`
- D3 套用範圍：只改 copyAllCompletedLinks 的展開順序
- D4 持久性：無
- D5 缺時間戳：視為批次起點時間

只能修改：
- app/src/App.svelte
- app/src/lib/types.ts
- app/src/lib/rdSender.ts（若需要）
- app/src/lib/rdSender.test.ts（新增測試）

驗收：
- 既有 38 個 vitest 通過
- 新增 ≥2 個排序測試
- svelte-check 無新 type error

禁止：
- 動 src-tauri 或 sidecar
- git commit / reset / checkout / push / clean / restore
```
