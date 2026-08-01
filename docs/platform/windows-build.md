# Windows 建置交接

寫給在 Windows 機器上接手建置的人（或 agent）。程式碼在 Linux 上開發並通過全部
gate，但**有三件事只有在 Windows 上才驗得了**，這份文件說明是哪三件、為什麼、
以及壞掉時怎麼修。

## 先跑這個

```powershell
pwsh -File scripts\verify-windows-build.ps1
```

全綠之後才跑既有的打包 pipeline：

```powershell
pwsh -File scripts\build-release.ps1
```

`verify-windows-build.ps1` 不打包，它只做驗證：環境齊全性 → 三個既有 gate →
`cargo test --lib` → 重建 sidecar 並用真的 JSON-lines 協定跟它對話。

---

## 三個 Windows 專屬風險

### 1. Cargo.toml 的 keyring 相依在 2026-08-01 被按平台拆開（最高風險）

原本一行涵蓋三平台，展開後會把 `secret-service` 拉進**每個**目標並在 Linux 上
硬編譯失敗，導致 `cargo test --lib` 長期無法使用。改成：

```toml
[target.'cfg(windows)'.dependencies]
keyring = { version = "3", features = ["windows-native"] }
```

**這個改動只在 Linux 上驗過。** 對 Windows 理論上是純減法（`windows-native`
本來就啟用，只是不再編譯兩個從未使用的後端），而程式碼只用到
`Entry::new` / `set_password` / `get_password` / `delete_credential` /
`Error::NoEntry` 這幾個 backend 無關的 API——但理論不等於實測。

**若 `cargo test --lib` 失敗且錯誤與 keyring 有關**：刪掉
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

### 3. 日誌目錄靠環境變數巧合

`app_logging.py` 的候選順序是 `%JAVDB_LOG_DIR%` → `%LOCALAPPDATA%\JavDBMagnet\logs`
→ console-only。而 **Rust 端從未設定 `JAVDB_LOG_DIR`**（`sidecar_manager.rs` 的
spawn 沒有 `.env(...)`），Windows 純粹靠繼承的 `%LOCALAPPDATA%` 恰好等於
`PathManager.log_dir` 才會動。

實務上 Windows 會動，但這是巧合不是契約。若使用者回報「logs 目錄空的」，
先查 `%LOCALAPPDATA%` 是否存在。長期修法見 `linux-support.md` 第 3 節。

---

## repo 內那三個 .exe 是舊的

| 檔案 | 狀態 |
|---|---|
| `javdbmagnet.exe`（root，有進 git） | 2026-07-27 建的，**沒有任何 08-01 的功能** |
| `sidecar.exe`（root，有進 git） | 同上，落後約 800 行 Python 變更 |
| `app/src-tauri/binaries/sidecar-*.exe` | 未進 git，需重建 |

**不要直接雙擊 repo 裡的 `javdbmagnet.exe` 來測試新功能**——那是舊版。
一定要重新建置。

---

## 08-01 新增的功能，建置後值得手動確認

1. **送出前預判**：挑選分頁的「每組只留」下拉多了「RD 命中優先」，列上會有
   `⚡高清` / `高清` 徽章與 ★ 首選標記；旁邊有「只勾選 RD 優先候選」按鈕。
2. **送出前攔截**：批次含低機率列時，按送出會先出現摘要面板
   （高機率／低機率／未判定），可選「只送高機率」。
3. **成效日誌**：送出後 `%LOCALAPPDATA%\JavDBMagnet\logs\rd_outcomes.jsonl`
   應該多出一行。分析用 `python scripts\rd_log_report.py`。
   設 `JAVDB_RD_LOG=0` 可關閉。

最有價值的手動驗收仍是完整走一次
**pending → 全部重試（查 RD）→ completed**，確認完成時間欄與排序正確。

---

## 附帶

Rust 端的 `cargo test --lib` 目前是 81 passed。這個 gate 在 2026-08-01 之前
一直被記載為「本機編不過、只能人工細審」，現在可用了——動 Rust 前請跑它。
