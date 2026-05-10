# 剪貼簿（Clipboard）寫入路徑

> Status: M5d 起生效 / 2026-05-11 更新（加入 RD 直連批次複製的 capability）

## TL;DR

App 有 **兩條** 寫剪貼簿的路徑，刻意分開：

| 用途 | 路徑 | 實作位置 | 安全考量 |
|---|---|---|---|
| 複製單一 / 多筆磁力 | 前端 `invoke("copy_magnet")` → Rust → clipboard | `app/src-tauri/src/commands.rs::copy_magnet`、`copy_magnets_bulk` | 完整 magnet 文字只在 sidecar 記憶體；Rust 端透過 `handle_id` 反查取出短暫 String，寫完剪貼簿即 drop。**前端永遠拿不到完整 magnet。** |
| 複製 RD 直連（unrestrict link） | 前端動態 import `@tauri-apps/plugin-clipboard-manager` 直接 `writeText` | `app/src/App.svelte::copyRdDownloads` | RD 直連是公開可下載 URL（已驗證的 token 才產生），沒有 sidecar boundary 需求；前端持有沒問題。|

兩條路徑的安全模型不同 → 不適合（也不該）合併。

## 為什麼磁力走 Rust、RD 直連走前端？

### 磁力（must Rust）
M5 安全合約之一：「**完整 magnet 文字不得進前端 state**」。意思是 frontend 永遠只看得到 `handle_id` + redacted magnet。如果讓前端 `writeText(fullMagnet)`，前端就要先持有完整 magnet —— 違反合約。所以磁力複製必須走：
```
前端 invoke("copy_magnet", { handleId })
  → Rust 端用 handle_id 向 sidecar resolve full magnet
  → Rust 端 clipboard 寫入
  → Rust transient String 立即 drop
```

### RD 直連（OK 前端）
RD 的 unrestrict link 是長這樣的 URL：`https://download.real-debrid.com/d/<id>/<filename>.mp4`。它是 RD API 回傳的公開可下載 URL，**不是 secret、不是 magnet**。送 RD 成功後它本來就會塞進 `RdSendProgress.links[].download` 給 UI 顯示與表格渲染。前端既然已經拿到，再呼叫 `writeText(linksJoinedByNewline)` 沒有額外資訊外洩。

## 為什麼前端寫剪貼簿需要 capability？

Tauri 2 對前端 JS 操作 plugin 一律走 IPC + capability gate（不像 Rust 端可直呼 plugin API）。`@tauri-apps/plugin-clipboard-manager` 的 `writeText` 對應的 IPC permission 名稱是：

```
clipboard-manager:allow-write-text
```

必須加進 `app/src-tauri/capabilities/default.json` 的 `permissions` 陣列才會放行。沒加的話前端 `writeText` 會被擋掉、丟 permission denied，而且因為 `App.svelte::copyRdDownloads` 的 catch 把錯誤訊息丟到頁面頂端的 `rdMessage`，使用者按了「複製所有 RD 直連」會以為按鈕沒反應（這是 2026-05-11 修掉的 bug）。

```jsonc
// app/src-tauri/capabilities/default.json
{
  "permissions": [
    "core:default",
    "clipboard-manager:allow-write-text"
  ]
}
```

`copy_magnet` / `copy_magnets_bulk` 走 Rust 端，**不需要** 這條 permission。

## 未來若想統一（不建議，記在這裡備查）

選項：把 `copyRdDownloads` 也改成 Rust Tauri command（`copy_rd_links_bulk(lines: Vec<String>)`），然後把 capability 移除。

優點：
- 路徑一致、code style 對稱（兩個複製動作都 invoke）

缺點：
- Rust 端多一個只是「幫忙轉一下字串」的 command，沒帶來新 invariant
- IPC 多一次 round-trip 對純字串無意義
- 前端反正本來就持有 `links[].download`，分割得不明所以

**結論：保持現狀。前端能 own 的東西讓前端 own，安全合約只在「不能 own 的東西」上強制。**

## 相關測試 / Smoke

- 「複製單一磁力」、「複製選取磁力」smoke 在 M4c 加入；對應的安全合約由 `app/src-tauri/src/commands.rs` 的 handle_id resolve 路徑保證。
- 「複製所有 RD 直連」沒有自動化測試（writeText 在 jsdom 下難以信賴 mock；Tauri capability gate 需要實機驗證）。手動 smoke：送 RD 一批 → 等 N/N 完成 → 按「複製所有 RD 直連 (N)」→ 開記事本貼上 → 應看到 N 行 https URL。

## 變更紀錄

| 日期 | 變更 | Commit |
|---|---|---|
| 2026-05-11 | 新增 `clipboard-manager:allow-write-text` capability，修復「複製所有 RD 直連」沒反應的 bug | （pending）|
