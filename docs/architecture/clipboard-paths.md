# 剪貼簿（Clipboard）寫入路徑

> Status: M6 follow-up（2026-05-11）起所有 clipboard 寫入都走 Rust。前端不直接呼叫 `tauri-plugin-clipboard-manager`。2026-10-16 依 HEAD `9e49603` 重新核對。

## TL;DR

| 用途 | 入口（Tauri command） | 實作位置 | 路徑說明 |
|---|---|---|---|
| 複製單一磁力 | `invoke("copy_magnet", { handleId })` | `app/src-tauri/src/commands.rs::copy_magnet`（[commands.rs:56](../../app/src-tauri/src/commands.rs#L56)） | sidecar `resolve_magnet` → full magnet → Rust transient String → clipboard → drop；回 `()` |
| 複製多筆磁力 | `invoke("copy_magnets_bulk", { handleIds })` | `commands.rs::copy_magnets_bulk`（[commands.rs:159](../../app/src-tauri/src/commands.rs#L159)） | 同上，但走 sidecar `resolve_magnets` 批次 resolve，以 `\n` join 後一次寫入；回 `{ copied, unknown }`（`unknown` = sidecar 不認得的 handle ＋ 空白/格式錯誤的項目），全部 unknown 時不寫剪貼簿 |
| 複製多筆 RD 直連 | `invoke("copy_rd_links_bulk", { links })` | `commands.rs::copy_rd_links_bulk`（[commands.rs:226](../../app/src-tauri/src/commands.rs#L226)） | 前端把已知的 download URL 陣列丟給 Rust，Rust trim + 濾掉空字串 + `\n` join + 寫剪貼簿；回 `{ copied }`，過濾後為 0 筆時不碰剪貼簿、不報錯 |

前端呼叫點（`app/src/App.svelte`）：

| 函式 | Command |
|---|---|
| `copyOne` | `copy_magnet` |
| `copySelected` | `copy_magnets_bulk`（先 `dedupeByHandleId`） |
| `copyRdDownloads`、`copyRdRow`、`copyRdSingleLink` | `copy_rd_links_bulk`（連結來自 `collectDownloadLinksFromRow`／單一 link） |
| `retryAllPending` | `copy_rd_links_bulk`（本輪重試完成的 links，寫入結果併進摘要訊息） |

統一規則：**前端永遠不直接 import `@tauri-apps/plugin-clipboard-manager`**（`app/package.json` 也不再列此相依，2026-10-16 移除）。所有 clipboard 寫入經 Rust `app.clipboard().write_text(...)`。

剪貼簿**讀取**路徑：無。前端與 Rust 都不呼叫 `readText`／`read_text`；貼上網址或磁力只靠 textarea 的原生貼上。

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
  "identifier": "default",
  "windows": ["main"],
  "permissions": [
    "core:default",
    {
      "identifier": "shell:allow-open",
      "allow": [
        { "url": "https://real-debrid.com/apitoken" }
      ]
    }
  ]
}
```

**不需要** `clipboard-manager:allow-write-text`（也沒有任何 `clipboard-manager:*` permission）。Rust 端 `app.clipboard()` 的呼叫不受 IPC permission gate 限制（Rust 對 plugin 是直呼，不走 IPC）。`shell:allow-open` 與剪貼簿無關，是前端 `openExternal` 開啟 RD API token 頁面用的。

Rust 端接線：`app/src-tauri/Cargo.toml` 相依 `tauri-plugin-clipboard-manager = "2"`；`lib.rs::run` 以 `.plugin(tauri_plugin_clipboard_manager::init())` 註冊（[lib.rs:362](../../app/src-tauri/src/lib.rs#L362)）；`commands.rs` 透過 `use tauri_plugin_clipboard_manager::ClipboardExt` 取得 `app.clipboard()`。

## 變更紀錄

| 日期 | 變更 | Commit |
|---|---|---|
| 2026-05-11（M5d 階段） | 新增 `clipboard-manager:allow-write-text` capability 解決前端 `writeText` 被擋的 bug（tactical fix） | `e42ef6d` |
| 2026-05-11（M6 follow-up） | 改架構：新增 Rust `copy_rd_links_bulk`，前端 `copyRdDownloads` / `retryAllPending` 改 invoke。收回 capability，前端不再直接持有 clipboard plugin 依賴。 | `e48c7e4` |

## 測試覆蓋

- Rust：沒有 sidecar mock。`copy_magnets_bulk` 的回應解析抽成 `resolved_magnets_from_response`，有兩個單元測試（保留 sidecar 錯誤碼、空白／格式錯誤項目計入 `unknown`；[commands.rs:1272](../../app/src-tauri/src/commands.rs#L1272)、[commands.rs:1286](../../app/src-tauri/src/commands.rs#L1286)）。`copy_magnet` 與 `copy_rd_links_bulk`（trim + filter + join + clipboard write）目前未加單元測試 —— 若日後新增 dedupe 等規則，再補。
- 前端：`App.test.ts` 以 mock `invoke` 提供 `copy_rd_links_bulk`，並斷言 `retryAllPending` 以本輪完成的 links 呼叫它；`rdSender.test.ts` 覆蓋 `collectDownloadLinksFromRow`（決定要複製哪些連結）。`copy_magnet`／`copy_magnets_bulk` 的前端呼叫沒有測試。手動 smoke 在 `docs/sessions/m6a-release-smoke.md` 步驟 6。
- jsdom 環境下 `invoke` 可以 mock，但 `app.clipboard().write_text()` 的真實寫入需要實機驗證。Tauri 沒有 fake clipboard backend。
