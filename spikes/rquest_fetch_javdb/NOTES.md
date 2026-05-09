# rquest fetch spike (JavDB)

## 目的
在 [reqwest spike](../rust_fetch_javdb/NOTES.md) 失敗（HTTP 403，TLS 指紋被 Cloudflare 擋）後，
驗證 [`rquest`](https://docs.rs/rquest)（reqwest fork，內建瀏覽器 TLS/HTTP2 指紋仿造）能否繞過。

結論將決定 Tauri/Rust backend 路線：
- ✅ 可行 → 純 Rust + rquest
- ❌ 不可行 → 退回 Python sidecar

**只是 spike**，不會被併入主程式 build；採 crates.io 釋出版（rquest 5.1 / rquest-util 2.2）。

## 用法

```
cd spikes/rquest_fetch_javdb
cargo run -- "https://javdb.com/v/xxxx"
```

## 依賴注意事項

- `rquest`：Apache-2.0
- **`rquest-util`：GPL-3.0**（如果未來要 vendor 進主程式，要評估授權影響）
- emulation 對齊 `Emulation::Chrome131`（curl_cffi 也是用近似的 Chrome 指紋）
- Async-only，spike 用 `tokio::main(flavor = "current_thread")` 避免拉 multi-thread runtime

## 結果欄位

```json
{
  "ok": true/false,
  "http_status": 200,
  "engine": "rquest",
  "emulation": "Chrome131",
  "title": "...",
  "code": "...",
  "magnet_count": N,
  "first_magnet_starts_with_magnet": true/false,
  "challenge_suspected": true/false,
  "error": null 或字串
}
```

## 測試結果

**測試日期**：2026-05-10
**OS**：Windows 11 Pro（10.0.26200）
**Rust 工具鏈**：rustc 1.94.1, cargo 1.94.1
**目標 URL**：`https://javdb.com/v/RkX3Rp`（使用者明確授權；尚未實際送出請求）

### Build 狀況：未通過（Windows 環境依賴）

`rquest 5.1` 透過 `boring-sys2` 內嵌編譯 BoringSSL，這是它能仿造 Chrome 真實 TLS 指紋的關鍵，但代價是要在本機編譯 BoringSSL。

| 嘗試 | 結果 |
|------|------|
| 1. 直接 `cargo build --release` | ❌ `failed to execute command: program not found  is cmake not installed?` |
| 2. `pip install cmake==4.3.2`（裝在 Python Scripts，可逆） | ✅ cmake 4.3.2 可用 |
| 3. 重跑 `cargo build --release` | ❌ `CMake Error: No CMAKE_ASM_NASM_COMPILER could be found.` |

最後 build 仍無法完成，因為 BoringSSL 的優化匯編需要 **NASM**（Netwide Assembler）。
這台機器沒裝 NASM；NASM 沒有純 pip 安裝管道，常見方式為 `winget install NASM.NASM` 或手動下載。

### 程式邏輯部分

`src/main.rs` 寫好了（async / `tokio` current_thread runtime / `Emulation::Chrome131` /
原生 cookie header），與 reqwest spike 的解析邏輯一致；只缺實際 HTTP 結果。

## 結論

**本輪不採用 rquest 作為主路線。改走 Tauri + Python sidecar 路徑。**

### 決策依據

1. **Windows build 鏈過長**：
   - `rquest 5.1` → `boring-sys2` → 內嵌編譯 BoringSSL
   - 必要工具：`cmake` + `NASM` + Visual Studio C/C++ build tools
   - 這台開發機沒裝 NASM，已用 `pip install cmake==4.3.2`（可逆）解一個依賴；
     NASM 沒有 pip 通路，要靠 `winget install NASM.NASM` 或手動下載
   - 任何協作者 / CI / 重建環境都要重複承受這個成本

2. **尚未取得 JavDB HTTP 實證**：
   - 程式碼寫到 emulation/cookie/解析齊備（見 `src/main.rs`）但 build 沒過，
     沒有實際對 JavDB 送過請求，所以無法宣稱 rquest 能繞 Cloudflare
   - 即使 build 過了，反爬蟲對抗本身是長期維護議題（Cloudflare 規則改了 emulation 也要追）

3. **授權風險**：
   - `rquest`：Apache-2.0 ✓
   - `rquest-util`（提供 `Emulation::*` 預設）：**GPL-3.0** ✗
   - 桌面工具要打包散佈給朋友，主程式裡放 GPL 元件牽涉到衍生作品授權，需法務評估

4. **Python `curl_cffi` 路徑已實證**：
   - 同 URL、同 cookie：HTTP 200，`magnet_count=3`（見 [reqwest spike NOTES](../rust_fetch_javdb/NOTES.md)）
   - 既有 Python 程式碼有 41 個 unit test 鎖定行為
   - 相對成本：Python sidecar 打包多 ~30MB，但開發 / 維護 / 法務都最低風險

### 保留物

| 檔案 | 用途 |
|------|------|
| `Cargo.toml` / `Cargo.lock` | 記錄當時的 crate 版本（rquest 5.1, rquest-util 2.2） |
| `src/main.rs` | emulation + scraper 解析邏輯，未來重啟 Rust 路線可參考 |
| `.gitignore` | 擋 `target/` 與 `*.pdb` |
| 本 `NOTES.md` | 完整失敗紀錄與決策理由 |

### 副作用 / 環境變更

- 此輪安裝了 `cmake==4.3.2`（透過 `pip install`，位於 Python `Scripts/`）。
  **未自動移除**，由使用者決定：
  - 留著：未來其他 Rust crate 可能也用得到（成本：磁碟 ~150MB）
  - 移除：`pip uninstall cmake`

### 下一步

→ 開新 spike：`spikes/python_sidecar/`
   目標：Tauri/Rust 透過穩定 JSON protocol 呼叫 Python 抓 JavDB，
   不做 UI、只證可行性。

