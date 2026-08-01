# Linux 支援：需要修正的環節

**狀態**：未實作。本檔只記錄「要移植到 Linux 需要動哪些地方」，不是已完成的支援聲明。
**驗證日期**：2026-08-01，於 Linux（rustc 1.97.1 / cargo 1.97.1、Python 3.12）實測。

專案定位是 Windows-only（`app/src-tauri/src/path_manager.rs:35-36` 註解自陳
「V1 只出 Windows」）。以下每一項都經過實跑驗證，不是靜態推論。

---

## 摘要

| # | 環節 | 現況 | 阻礙等級 |
|---|---|---|---|
| 1 | `Cargo.toml` 的 keyring features | 編譯直接失敗 | **阻斷** |
| 2 | Linux sidecar binary 不存在 | build script 失敗 | **阻斷** |
| 3 | `JAVDB_LOG_DIR` 從未被設定 | 所有 Python 日誌靜默消失 | **功能失效** |
| 4 | 「打開資料夾」只實作 Windows | 回錯誤訊息，不崩 | 功能退化 |
| 5 | 憑證儲存需要 keyring daemon | 無頭環境會失敗 | 環境相依 |
| 6 | 打包腳本寫死 Windows | 無法產出 Linux 安裝檔 | 建置流程 |

實測結論：修好 1 與 2 之後 `cargo check` 通過（僅剩 1 個 dead-code warning），
`cargo test --lib` **81 passed / 0 failed**。

---

## 1. `Cargo.toml` 的 keyring features（阻斷）

**現況**（`app/src-tauri/Cargo.toml`）：

```toml
keyring = { version = "3", features = ["windows-native", "apple-native", "linux-native-async-persistent"] }
```

一行涵蓋三平台，於是**每個目標平台都被迫拉進所有後端**。其中
`linux-native-async-persistent` 展開後是 `async-secret-service` →
`dep:secret-service` + `dep:zbus`，但沒有啟用 `secret-service` 需要的
crypto／runtime feature。

**實際錯誤**：

```
error: Please enable a feature to pick a runtime (such as rt-async-io-crypto-rust
or rt-tokio-crypto-rust) for the secret-service crate
  --> secret-service-4.0.0/src/session.rs:56:9
error: could not compile `secret-service` (lib) due to 3 previous errors
```

**修法**：按平台拆開，每個目標只拉自己的後端。

```toml
[target.'cfg(windows)'.dependencies]
keyring = { version = "3", features = ["windows-native"] }

[target.'cfg(target_os = "macos")'.dependencies]
keyring = { version = "3", features = ["apple-native"] }

# sync 版（dbus-secret-service）而非 async 版：它不需要 zbus runtime feature，
# 而本專案所有 keyring 呼叫端本來就是同步的。
[target.'cfg(target_os = "linux")'.dependencies]
keyring = { version = "3", features = ["linux-native-sync-persistent", "crypto-rust"] }
```

**驗證**：套用後 `cargo check` 越過此錯誤，`cargo test --lib` 得到 81 passed。
這個修改對 Windows 是純減法（不再拉入 macOS／Linux 後端），理論上不影響現有行為，
但**尚未在 Windows 上實測**。

## 2. Linux sidecar binary（阻斷）

**現況**：`app/src-tauri/binaries/` 只有 `sidecar-x86_64-pc-windows-msvc`。
Tauri 依 `tauri.conf.json` 的 `externalBin: ["binaries/sidecar"]` 加上目標
triple 尋找，Linux 上找的是 `sidecar-x86_64-unknown-linux-gnu`。

**實際錯誤**：

```
resource path `binaries/sidecar-x86_64-unknown-linux-gnu` doesn't exist
```

**修法**：用 PyInstaller 建一份。實測可行：

```bash
python -m PyInstaller --onefile --name sidecar-x86_64-unknown-linux-gnu \
  --paths . --hidden-import curl_cffi --collect-all curl_cffi \
  sidecar/sidecar.py
```

產出 30.3 MB（Windows 版 30.3 MB），實跑 JSON-lines 協定（`hello` /
`register_magnets` / `shutdown`）回應皆正確。

注意 `spikes/pyinstaller_sidecar/` 下的 `.spec` 檔名寫死
`sidecar-x86_64-pc-windows-msvc.spec`，`build_sidecar.py` 也以該 triple 為前提；
要正式支援得讓 triple 可參數化。

## 3. `JAVDB_LOG_DIR` 從未被設定（功能失效）

**這是最容易被忽略、但實際影響最大的一項。**

`app_logging.py:36-51` 的候選目錄順序是
`$JAVDB_LOG_DIR` → `%LOCALAPPDATA%/JavDBMagnet/logs` → console-only。
而 `app/src-tauri/src/sidecar_manager.rs:154-159` 的 spawn **沒有 `.env(...)`**，
全 repo 亦無任何 `.rs` 提及 `JAVDB_LOG_DIR`。

Windows 上靠繼承的 `%LOCALAPPDATA%` 恰好等於 `PathManager.log_dir`，所以「剛好會動」。
Linux 上兩個候選都不存在 → logging 降級 console-only；而
`sidecar_manager.rs:176-180` 又把 sidecar 的 stderr **直接丟棄**。

**後果**：Linux 上 `debug.log` 與 `rd_outcomes.jsonl` 都不會產生，
且使用者看不到任何錯誤——診斷能力歸零。

**實測**：

```
$ env -u LOCALAPPDATA -u JAVDB_LOG_DIR ./sidecar-x86_64-unknown-linux-gnu --daemon
[WARNING] app_logging: All log dir candidates failed; running console-only.

$ env -u LOCALAPPDATA JAVDB_LOG_DIR=/tmp/x ./sidecar-... --daemon
$ ls /tmp/x
debug.log  rd_outcomes.jsonl
```

**修法**：spawn 時明示傳入，Rust 端已經握有 `path_manager.log_dir`。
這在 Windows 上也是改善——目前的正確性是靠環境變數巧合，而非契約。

相關：sidecar 已於 2026-08-01 修正「console-only 時不得在工作目錄自行建檔」
（commit `e77ac4d`），該缺陷正是 Linux 上每次啟動都會觸發的。

## 4. 「打開資料夾」只實作 Windows（功能退化）

`app/src-tauri/src/commands.rs:1198-1219` 的 `open_in_explorer` 只有
`#[cfg(target_os = "windows")]` 分支呼叫 `explorer.exe`，其他平台回
`open_in_explorer not implemented for this OS`。

不會崩潰，但 UI 上「打開資料目錄／打開 logs 目錄」兩顆按鈕在 Linux 失效。
補一個 `xdg-open` 分支即可。

## 5. 憑證儲存需要 keyring daemon（環境相依）

RD token 與 JavDB cookies 存在 OS keyring（`secret_store.rs` / `cookie_store.rs`）。
Linux 走 D-Bus Secret Service，需要 GNOME Keyring 或 KWallet 在跑。
無頭／容器環境沒有 daemon 時 `keyring::Entry` 會失敗，且**目前沒有降級路徑**。

## 6. 打包與發布腳本（建置流程）

- `scripts/build-release.ps1` 是 PowerShell，Linux 無法直接跑。
- `spikes/pyinstaller_sidecar/build_sidecar.py` 與其 `.spec` 以 Windows triple 為前提。
- `tauri.conf.json` 的 `bundle.targets` 為 `[]`（由平台預設決定），Linux 會嘗試
  產 deb/appimage，需要額外系統相依。

## 系統相依（GUI）

Tauri v2 在 Linux 需要 WebKitGTK。本次驗證機器上皆已具備：

| 套件 | 版本 |
|---|---|
| `webkit2gtk-4.1` | 2.52.3 |
| `javascriptcoregtk-4.1` | 2.52.3 |
| `libsoup-3.0` | 3.6.6 |
| `gtk+-3.0` | 3.24.52 |

---

## 未驗證的部分（誠實標示）

- **GUI 實際啟動與操作**：只做到 `cargo check` / `cargo test --lib` 與 sidecar
  協定 smoke，**沒有真的把視窗開起來點過**。
- **Windows 迴歸**：第 1 項的 Cargo.toml 修改未在 Windows 上實測。
- **keyring 在 Linux 的實際讀寫**：只確認編譯通過，未實跑存取憑證。
- **打包產出**：未實際產生 Linux 安裝檔。

## 若決定支援 Linux，建議順序

1. 先修第 3 項（`JAVDB_LOG_DIR`）——它同時改善 Windows 的正確性，且與平台移植無關。
2. 再修第 1 項，讓 `cargo test --lib` 這個 gate 在 Linux 開發機上可用
   （目前 CLAUDE.md 記載此 gate 被跳過，Rust 端變更只能人工細審）。
3. 第 2、4、5、6 項屬於「真的要出 Linux 版」才需要，不必為了開發便利而做。
