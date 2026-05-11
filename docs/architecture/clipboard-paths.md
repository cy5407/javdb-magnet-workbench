# 剪貼簿（Clipboard）寫入路徑

> Status: M6 follow-up（2026-05-11）起所有 clipboard 寫入都走 Rust。前端不直接呼叫 `tauri-plugin-clipboard-manager`。

## TL;DR

| 用途 | 入口（Tauri command） | 實作位置 | 路徑說明 |
|---|---|---|---|
| 複製單一磁力 | `invoke("copy_magnet", { handleId })` | `app/src-tauri/src/commands.rs::copy_magnet` | sidecar resolve full magnet → Rust transient String → clipboard → drop |
| 複製多筆磁力 | `invoke("copy_magnets_bulk", { handleIds })` | `commands.rs::copy_magnets_bulk` | 同上，但批次 resolve |
| 複製多筆 RD 直連 | `invoke("copy_rd_links_bulk", { links })` | `commands.rs::copy_rd_links_bulk` | 前端把已知的 download URL 陣列丟給 Rust，Rust filter + join + 寫剪貼簿 |

統一規則：**前端永遠不直接 import `@tauri-apps/plugin-clipboard-manager`**。所有 clipboard 寫入經 Rust `app.clipboard().write_text(...)`。

## 為什麼磁力的 boundary 是嚴格的？

M5 安全合約之一：「**完整 magnet 文字不得進前端 state**」。Frontend 只看 `handle_id` + redacted magnet。所以磁力複製不能讓前端 `writeText(fullMagnet)` —— 前端那行如果存在，就要先持有完整 magnet，違反合約。流程：

```
前端 invoke("copy_magnet", { handleId })
  → Rust 用 handle_id 向 sidecar resolve full magnet
  → Rust 端 clipboard 寫入
  → Rust transient String 立即 drop
```

## RD 直連為什麼也走 Rust（M6 follow-up 收斂）

RD 的 unrestrict link（`https://download.real-debrid.com/d/<id>/<filename>.mp4`）**不是 secret** —— 是 RD API 回傳的公開可下載 URL，送 RD 成功後本來就塞進 `RdSendProgress.links[].download` 讓 UI 顯示。技術上前端 `writeText(...)` 沒有違反任何 secret invariant。

但「前端不該直接動 plugin」這條架構約束有更廣的好處：

1. **Capability surface 最小化** —— 不需要在 `capabilities/default.json` 加 `clipboard-manager:allow-write-text`。前端 JS 的 IPC 路徑全部走 `invoke(...)` 與 Rust commands，不直接觸碰 plugin。
2. **錯誤處理一致** —— Rust 端 `app.clipboard().write_text()` 失敗會丟 String error，frontend `invoke` 接到 Promise reject，跟其他 `copy_*` command 一樣。
3. **單一入口好維護** —— 將來想加「自動換行」、「URL encode」、「避免重複寫入」之類的剪貼簿側邊邏輯，只改 Rust 一處。
4. **測試**面變窄 —— 前端 mock invoke 即可，不需要去 mock `@tauri-apps/plugin-clipboard-manager` 的 dynamic import。

## Capability 設定

```jsonc
// app/src-tauri/capabilities/default.json
{
  "permissions": [
    "core:default"
  ]
}
```

**不需要** `clipboard-manager:allow-write-text`。Rust 端 `app.clipboard()` 的呼叫不受 IPC permission gate 限制（Rust 對 plugin 是直呼，不走 IPC）。

## 變更紀錄

| 日期 | 變更 | Commit |
|---|---|---|
| 2026-05-11（M5d 階段） | 新增 `clipboard-manager:allow-write-text` capability 解決前端 `writeText` 被擋的 bug（tactical fix） | `a56425c` |
| 2026-05-11（M6 follow-up） | 改架構：新增 Rust `copy_rd_links_bulk`，前端 `copyRdDownloads` / `retryAllPending` 改 invoke。收回 capability，前端不再直接持有 clipboard plugin 依賴。 | （pending）|

## 測試覆蓋

- Rust：`copy_magnets_bulk` 在 commands.rs 有路徑單元測試（在 sidecar mock 下）。`copy_rd_links_bulk` 邏輯極簡（filter + join + clipboard write），目前未加單元測試 —— 若日後新增 trim / dedupe 規則，再補。
- 前端：`magnetUtils.test.ts` / `rdSender.test.ts` 不覆蓋 clipboard 路徑。手動 smoke 在 `docs/sessions/m6a-release-smoke.md` 步驟 6。
- jsdom 環境下 `invoke` 可以 mock，但 `app.clipboard().write_text()` 的真實寫入需要實機驗證。Tauri 沒有 fake clipboard backend。
