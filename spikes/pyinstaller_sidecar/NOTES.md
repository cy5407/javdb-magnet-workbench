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

---

## 已知 packaging issues（commit 後須處理）

三條同源缺陷都是「路徑硬綁 `app_dir()`」造成，但**綁定用途與嚴重度差很多**，分開列：

- Issue 1 綁的是**寫入路徑**（`mkdir logs/` + 開 file handler）→ 唯讀部署 import-time crash
- Issue 2/3 綁的是**讀取路徑**（找 `cookies.txt` / `.env`）→ 本 spike 的 `fetch-javdb` 路徑不會 import-time crash，但檔案要放對位置才讀得到；後續若加 RD/其他命令，缺檔會變成功能失敗

對應的 fix 契約也不同：Issue 1 要解的是「import-time side effect 不可要求 exe 目錄可寫」；Issue 2/3 要解的是「設定 / 憑證檔位置不應硬綁 `<exe_dir>`，需提供 caller-controlled path」。

### Issue 1（A 級，blocker — 唯讀部署會 import-time crash）：frozen logs/ 寫入

`javdb_magnet_gui.py:31` 在 **module import 時**就呼叫 `setup_logging()`。
而 `app_logging.py` 的 `app_dir()` 在 frozen 模式回傳 `Path(sys.executable).parent`。

→ `sidecar.exe` 一被 import，立刻 `mkdir <exe_dir>/logs/` + 開 `debug.log` 的 file handler。

**為什麼是 blocker**：
- 部署到 `Program Files\JavDBMagnet\`（Windows 程式預設裝在這）→ 該目錄不可寫
- mkdir 或 open 拋例外 → import-time 崩潰 → sidecar **連回應 JSON 都做不到**
- 沒有 fallback path、沒有 graceful degrade

**spike 期間為什麼沒爆**：`dist/` 是 spike 自己 build 出來的可寫資料夾，碰巧能寫。

**真正修法（commit 後另開 issue）**：
- `app_logging` 改 lazy setup（第一次寫 log 時才 mkdir）
- 加 `JAVDB_LOG_DIR` env override
- mkdir 失敗 fallback 到 `%LOCALAPPDATA%\JavDBMagnet\logs\`，再失敗 graceful degrade 成 console-only
- acceptance：sidecar.exe 在唯讀目錄能完成 import 並回 JSON

### Issue 2（B 級，部署可繞過）：cookies.txt 路徑綁 `app_dir()`

`sidecar.py` 透過 `javdb_magnet_gui.load_cookies()` 找 `cookies.txt`，路徑為 `app_dir() / "cookies.txt"` → frozen 時是 `<exe_dir>/cookies.txt`。

**嚴重度為何比 Issue 1 低**：cookies 不需要寫，只需要讀。Tauri 部署可以把 cookies 從 `%APPDATA%` 預先複製到 exe 旁；spike 期間直接 `cp cookies.txt dist/` 就能繞。

**真正修法（commit 後另開 issue）** — 兩階段 migration：
1. **第一階段**：`sidecar.py` 加 `--cookies-file <path>` CLI flag。Rust driver 從 `%APPDATA%\JavDBMagnet\cookies.txt` 讀路徑後傳給 sidecar
2. **第二階段（搭配 daemon spike）**：cookies 改透過 stdin 首次握手傳一次。**stdin 不走 argv** 是安全約束（argv 在 Windows 會出現在 process list / event log）

### Issue 3（B 級，本命令未觸發）：.env / RD token 同源缺陷

`javdb_magnet_gui.py:35` 的 `ENV_FILE = app_dir() / ".env"` 把 RD token 路徑綁在 `<exe_dir>`（`realdebrid.load_env(path)` 本身 path-agnostic，綁定發生在 caller）。同 Issue 2 的根因。

**為何標 B 而非 A**：本 spike 只驗 `fetch-javdb` 命令，不走 RD path。但若未來加 `--command rd-fetch` 之類，會踩到。

**修法**：跟 Issue 2 一起處理，sidecar 加 `--env-file <path>` flag。

---

## 額外 packaging 風險

### Bootloader 解壓殘留

`--onefile` 模式啟動時 bootloader 會把 archive 解壓到 `%TEMP%\_MEIxxxxxx\`，正常結束會清理，**異常結束（SIGKILL、藍屏、斷電）會殘留**。

對 spike 影響：無。
對 production 影響：使用者 `%TEMP%` 會慢慢累積殘留資料夾。
**這也是把 sidecar 改 daemon 化的論據之一**：常駐子程序少 spawn = 少解壓 = 少殘留。

### Code signing / SmartScreen

未簽章的 `--onefile` exe 在 Windows 會被 Defender / SmartScreen 攔（「未知發行者」警告，部分企業 GPO 直接 block）。

**Tauri 整合前必須規劃 code signing pipeline**：
- 取得 code signing 憑證（OV / EV）
- CI 加簽章步驟
- Tauri bundle 與 sidecar 同憑證簽

### `--collect-all curl_cffi` 範圍稽核

`--collect-all` 範圍很寬，會把 curl_cffi 的所有 data files、所有 binary deps、所有 submodule import 全收進來。**目前沒列基線**，下次升 curl_cffi 體積跳多少不會被注意到。

**建議**：build 後跑 `pyi-archive_viewer dist/sidecar.exe` 列出 collected items 存成 baseline，或在 `build_sidecar.py` 加 `--log-level INFO` 留下 PyInstaller 收檔清單。

### Driver timeout（spike 不修，production 必加）

目前 `driver_rust` 用 `Command::output()` 同步等 sidecar，**沒設 timeout**。spike OK，production 必須加 — sidecar hang 會直接拖垮 Tauri command thread。

---

## 測試結果

**測試日期**：2026-05-10
**OS**：Windows 11 Pro
**PyInstaller**：6.19.0
**Python**：3.12.10
**Rust toolchain**：rustc 1.94.1
**curl_cffi 版本**：0.14.0
**目標 URL**：`https://javdb.com/v/RkX3Rp`（使用者明確授權）

### Build

```
python spikes/pyinstaller_sidecar/build_sidecar.py
```

| 指標 | 值 |
|------|----|
| Build 時間 | 約 30 秒 |
| `sidecar.exe` 大小 | **23.9 MB** |
| `sidecar.exe` SHA256 | `b05f40bf050935d3c4867cae21af8bdc7db242086394aa76ee5bc5c31d41bcae` |
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

### 安全檢查

- 測試結束已執行 `rm dist/cookies.txt`
- `[ -f dist/cookies.txt ]` 確認 → `CONFIRMED DELETED`
- `dist/` 已被 `.gitignore` 排除

---

## 結論

✅ **PyInstaller sidecar packaging 路線可行，但有 1 個 A 級 blocker 須在第一個正式 release 前修掉**：
- exe 端對端能取得 `magnet_count=3`，與 source 模式行為一致
- Rust driver 透過 `std::process::Command` 呼叫 exe 完全可行（不需 Python interpreter）
- 體積 23.9 MB 合理（Tauri 主程式 + sidecar 約 25–35 MB 範圍）
- ⚠️ Issue 1（import-time logs/ 寫入）會讓唯讀部署 import 失敗，必修

### 對下一步 Tauri 整合的建議

1. **修 Issue 1（A blocker）後再做 Tauri PoC**
   - 先解掉 `app_logging` lazy setup + env override
   - 否則 PoC 跑得起來但一打包到 `Program Files` 就崩

2. **改用常駐 sidecar（long-running daemon）**
   - 目前每次 `fetch-javdb` 都 spawn 一個新 sidecar.exe（~1-2 秒首啟）
   - 也順帶解掉 bootloader 解壓殘留問題
   - cookies / token 改透過首次握手用 stdin 傳一次（不走 argv，避免 process list 洩漏）
   - 與 [python_sidecar_protocol/NOTES.md 的後續建議](../python_sidecar_protocol/NOTES.md) 合併

3. **sidecar.exe 體積優化（選擇性）**
   - `--exclude-module tkinter` 預估省 5–8 MB
   - 排在 PoC 之後，量化效果再決定

4. **Tauri sidecar 機制**
   - `tauri.conf.json` → `bundle.externalBin` 加入打包好的 `sidecar.exe`
   - 路徑 conventions：[Tauri sidecar guide](https://tauri.app/v1/guides/building/sidecar)
   - **driver_rust/ 是 spike harness，production 走 `tauri::api::process::Command::new_sidecar()`**

5. **Code signing pipeline**
   - 第一個正式 release 前必須備好憑證
   - 否則 SmartScreen / Defender 警告會勸退使用者

### 路線總圖

```
[Tauri UI - WebView]                  ← 新建（Rust + svelte/react/vue 任選）
        ↕ Tauri command (Rust)
[Rust backend]                        ← 新建（command handlers + 設定/路徑管理）
        ↕ stdin/stdout JSON
[sidecar.exe (PyInstaller)]           ← 本 spike 已驗證可行（修完 Issue 1 後）
        ↕ HTTP (curl_cffi)
[JavDB / Real-Debrid]
```

### Follow-up issues（commit 後另開）

1. **A blocker**：`app_logging` lazy setup + `JAVDB_LOG_DIR` env override + mkdir fallback
2. **B**：`sidecar.py` 加 `--cookies-file` / `--env-file` CLI flag（第一階段）
3. **B/feature**：daemon 化 sidecar protocol（stdin 握手，cookies 第二階段 migration）
4. **C**：`--collect-all curl_cffi` collected items baseline（pyi-archive_viewer 或 build log）
5. **C**：driver timeout / production sidecar resolver（不在本 driver scope，Tauri new_sidecar 取代）
6. **D**：體積優化（`--exclude-module tkinter` 量化）
7. **D**：Code signing pipeline（OV/EV 憑證取得 + CI 加簽章 + Tauri bundle 與 sidecar 同憑證）
