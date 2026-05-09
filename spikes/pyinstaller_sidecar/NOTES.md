# PyInstaller sidecar packaging spike

## 目的
驗證 [`spikes/python_sidecar_protocol/sidecar.py`](../python_sidecar_protocol/sidecar.py)
能被 PyInstaller 打成單一 `sidecar.exe`，且 Rust driver 呼叫 exe 仍能取得同樣 JSON。
這是 [sidecar protocol spike](../python_sidecar_protocol/NOTES.md) 的下一步：
從「python script」→「可發布的 binary」。

## 結構

```
pyinstaller_sidecar/
├── .gitignore           # build/, dist/, *.spec, target/, *.pdb, __pycache__/
├── NOTES.md             # 本文件
├── build_sidecar.py     # PyInstaller 包裝器
└── driver_rust/         # 模擬 Tauri backend，呼叫 sidecar.exe
    ├── Cargo.toml
    └── src/main.rs
```

## 打包

```
python spikes/pyinstaller_sidecar/build_sidecar.py
```

PyInstaller 主要參數：

| 參數 | 用途 |
|------|------|
| `--onefile` | 單一 exe，方便 Tauri sidecar 機制嵌入 |
| `--console` | **保留 stdout/stderr**（不能用 `--windowed`，會失去 stdout） |
| `--name sidecar` | 產出 `sidecar.exe` |
| `--paths <repo_root>` | 讓 PyInstaller 解析 `from javdb_magnet_gui import ...` 等跨資料夾 import |
| `--collect-all curl_cffi` | curl_cffi 有 native deps，光 `--hidden-import` 不夠 |
| `--hidden-import javdb_magnet_gui / realdebrid / app_logging` | 強制收進去（避免動態 import 偵測失誤） |
| `--distpath` / `--workpath` / `--specpath` | 全部限制在 `spikes/pyinstaller_sidecar/` 內 |

不會打包進 exe：
- ❌ `.env`（無 `--add-data`）
- ❌ `cookies.txt`（同上）

## 已知 packaging issue：cookies.txt 路徑

`sidecar.py` 透過 `javdb_magnet_gui.load_cookies()` 找 `cookies.txt`，
而 `app_dir()`（`app_logging.py`）在 frozen 模式回傳 `Path(sys.executable).parent`。

→ `sidecar.exe` 會去 **exe 自己的資料夾** 找 `cookies.txt`。

對 spike 測試的影響：
- repo root 有 `cookies.txt`，但 `spikes/pyinstaller_sidecar/dist/` 沒有
- 測試前需把 repo root `cookies.txt` 複製到 `dist/`
- **這條 spike 不修主程式**；正式整合 Tauri 時要決定 cookies.txt 真實位置策略：
  1. 跟 Tauri app 同層（最簡單）
  2. `%APPDATA%/JavDBMagnet/cookies.txt`（Windows 慣例）
  3. 由 Rust 端讀取後透過 stdin 傳給 sidecar（避免 sidecar 自己讀檔）

我傾向方案 3：由 Tauri/Rust 集中管理使用者資料，sidecar 變成 **stateless** 子程序。

## 測試結果

**測試日期**：2026-05-10
**OS**：Windows 11 Pro
**PyInstaller**：6.19.0（沿用既有 GUI build.py 的版本）
**Python**：3.12.10
**Rust**：rustc 1.94.1
**目標 URL**：`https://javdb.com/v/RkX3Rp`（使用者明確授權）

### Build

```
python spikes/pyinstaller_sidecar/build_sidecar.py
```

| 指標 | 值 |
|------|----|
| Build 時間 | 約 30 秒 |
| `sidecar.exe` 大小 | **23.9 MB** |
| Hidden imports 命中 | `curl_cffi`, `curl_cffi.requests`, `javdb_magnet_gui`, `realdebrid`, `app_logging` |
| `--collect-all curl_cffi` | 必要（curl_cffi 有 native libs） |
| `--paths <repo_root>` | 必要（讓 PyInstaller 跨資料夾解析 import） |

GUI exe 也是 ~23.8 MB，sidecar 體積相當；多數體積來自 curl_cffi 的 BoringSSL/CFFI bindings + tkinter（雖然 sidecar 不用 GUI 但 PyInstaller 從 import graph 也帶了一些）。
未來可以用 `--exclude-module tkinter` 進一步壓縮，本 spike 不做。

### Sidecar.exe 直接呼叫（cookies.txt 已暫時複製到 `dist/`）

```
spikes\pyinstaller_sidecar\dist\sidecar.exe fetch-javdb https://javdb.com/v/RkX3Rp
```

stdout（單行 JSON，這裡為閱讀美化；magnet 已遮蔽）：

```json
{
  "ok": true,
  "command": "fetch-javdb",
  "engine": "curl_cffi",
  "code": "SNOS-166",
  "magnet_count": 3,
  "magnets": [
    {"name": "SNOS-166", "size": "4.36GB, 2個文件", "tags": ["高清"], "magnet_redacted": "magnet:?xt=urn:btih:0201592f..."},
    {"name": "snos-166", "size": "5.62GB, 7個文件", "tags": ["高清"], "magnet_redacted": "magnet:?xt=urn:btih:a8736d7a..."},
    {"name": "SNOS-166", "size": "1.45GB, 2個文件", "tags": [],     "magnet_redacted": "magnet:?xt=urn:btih:7b1d1d93..."}
  ],
  "error": null
}
```

stderr（節錄）：
```
RequestsDependencyWarning: urllib3 ... doesn't match a supported version!
[INFO] app_logging: Logging initialized. File: ...\dist\logs\debug.log
```

只有套件警告 + logging 初始化訊息，不含 cookie / 完整 magnet。Exit code = 0。

### Rust driver 對 sidecar.exe

```
cargo run --release -- "https://javdb.com/v/RkX3Rp"
```

```json
{
  "ok": true,
  "sidecar_exit": 0,
  "parsed_json": true,
  "magnet_count": 3,
  "first_magnet_redacted_present": true,
  "stderr_nonempty": true,
  "error": null
}
```

✅ 與 Python 直跑、與 [`spikes/python_sidecar_protocol/`](../python_sidecar_protocol/) 跑出來的 magnet_count、結構完全一致。

### 既有測試

- `python -m unittest discover -s tests -v` → `Ran 41 tests in 0.001s OK`
- `py_compile`（含 `sidecar.py` + `build_sidecar.py`）→ ✓

### 額外觀察：frozen 模式的 logs/ 寫入

sidecar.exe 啟動時 `app_logging.setup_logging()` 在 `dist/logs/debug.log` 建立 log 檔（因為 `app_dir()` 在 frozen 時回傳 `Path(sys.executable).parent`）。

對 spike 沒影響，但對未來打包要注意：
- Tauri app 旁產生 `logs/` 子目錄（除非另設 `LOG_DIR`）
- 若部署到 `Program Files`，可能因權限不足寫不進 → 應改寫 `%LOCALAPPDATA%\JavDBMagnet\logs\`

### 安全檢查

- 測試結束已執行 `rm dist/cookies.txt`
- `[ -f dist/cookies.txt ]` 確認 → `CONFIRMED DELETED`
- `dist/` 已被 `.gitignore` 排除

## 結論

✅ **PyInstaller sidecar packaging 路線可行**：
- exe 端對端能取得 `magnet_count=3`，與 source 模式行為一致
- Rust driver 透過 `std::process::Command` 呼叫 exe 完全可行（不需 Python interpreter）
- 體積 23.9 MB 合理（Tauri 主程式 + sidecar 約 25–35 MB 範圍）

### 對下一步 Tauri 整合的建議

1. **Cookies 與 logs 路徑要重新設計**（packaging issue）：
   - 不再依賴 `app_dir()` 找 cookies
   - 由 Rust 端從 `%APPDATA%\JavDBMagnet\` 讀，並以 stdin 傳給 sidecar；或 sidecar 接受 `--cookies-file <path>` 參數
   - logs 改寫到 `%LOCALAPPDATA%\JavDBMagnet\logs\`

2. **改用常駐 sidecar (long-running daemon)**：
   - 目前每呼叫一次 `fetch-javdb` 都要重啟 sidecar（首次啟動 ~1-2 秒，之後啟動仍有 spawn 成本）
   - Tauri command handler 應該維持一個 sidecar 子程序，透過 stdin 換行 JSON 來傳請求
   - 這也呼應 [python_sidecar_protocol/NOTES.md 的後續建議](../python_sidecar_protocol/NOTES.md#後續若進-tauri-sidecar-command-可以如何對應成-tauri-command)

3. **sidecar.exe 體積優化（選擇性）**：
   - `--exclude-module tkinter`（sidecar 用不到 GUI）
   - 預估省下 5–8 MB

4. **Tauri sidecar 機制**：
   - `tauri.conf.json` → `bundle.externalBin` 加入打包好的 `sidecar.exe`
   - 路徑 conventions：[Tauri sidecar guide](https://tauri.app/v1/guides/building/sidecar)

### 路線總圖

```
[Tauri UI - WebView]                  ← 新建（Rust + svelte/react/vue 任選）
        ↕ Tauri command (Rust)
[Rust backend]                        ← 新建（command handlers + 設定/路徑管理）
        ↕ stdin/stdout JSON
[sidecar.exe (PyInstaller)]           ← 本 spike 已驗證可行
        ↕ HTTP (curl_cffi)
[JavDB / Real-Debrid]
```

下一步建議：建立最小 Tauri PoC（一個按鈕、一個輸入框、一個結果區），把 sidecar.exe 接進去，
驗證 `tauri.conf.json` 的 sidecar 機制能正確找到 binary 並轉送 JSON。
