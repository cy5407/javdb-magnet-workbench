# Python sidecar protocol spike — RETIRED

> ⚠️ **此 spike 已退役，僅作歷史紀錄。**
>
> - **Live runtime 已 promoted** 到 [`sidecar/sidecar.py`](../../sidecar/sidecar.py)（M3 JSONL daemon）。
> - 本目錄原本的 `sidecar.py`、`driver_rust/`、`.gitignore`、`__pycache__/` 已於 M9 simplify pass 中刪除。
> - 對應的死測試 `tests/test_sidecar_cli.py` 也一併刪除；現行測試在 [`tests/test_sidecar_protocol.py`](../../tests/test_sidecar_protocol.py)。
> - 本檔以下章節描述的是**舊 argv-style CLI 介面**（`python sidecar.py fetch-javdb <url>`），它**不再存在於 repo**，也不再是 production protocol。Production daemon 的契約見 [`docs/architecture/contracts/sidecar-runtime.md`](../../docs/architecture/contracts/sidecar-runtime.md)。
>
> 保留此檔的目的是讓未來讀者理解 M1→M3 的選型脈絡（與 [reqwest spike](../rust_fetch_javdb/NOTES.md) 失敗 / [rquest spike](../rquest_fetch_javdb/NOTES.md) 棄置的關聯），不是當作 build / runtime 指南。

---

## 目的（歷史）
證明「Tauri/Rust backend 可以用穩定 JSON protocol 呼叫 Python 抓 JavDB，並取得結構化結果」，
**不開完整 UI、不重寫主程式**。這是 [reqwest spike 失敗](../rust_fetch_javdb/NOTES.md) 與
[rquest spike 因 Windows build chain 棄置](../rquest_fetch_javdb/NOTES.md) 後的選定路線可行性驗證。

## 結構（歷史；目錄已刪除）

```
python_sidecar_protocol/
├── .gitignore         # [已刪] 擋 target/、*.pdb、__pycache__/
├── NOTES.md           # 本文件（保留）
├── sidecar.py         # [已刪] argv-style CLI 入口；被 sidecar/sidecar.py 取代
└── driver_rust/       # [已刪] 模擬 Tauri backend
    ├── Cargo.toml
    └── src/main.rs
```

## Protocol 設計（歷史；不再有效）

### Sidecar 介面（舊 argv 介面，已退役）

```
python sidecar.py fetch-javdb <url>
```

- **stdout**：單一行 JSON 物件
- **stderr**：可有診斷訊息（requests warning、logging init），**不得**含 cookie / 完整 magnet
- **exit code**：成功 0；失敗 1；參數錯誤 2

### Sidecar 回傳結構

```json
{
  "ok": true,
  "command": "fetch-javdb",
  "engine": "curl_cffi",
  "url": "https://javdb.com/v/...",
  "code": "SNOS-166",
  "title": "...",
  "magnet_count": 3,
  "magnets": [
    {
      "name": "SNOS-166",
      "size": "4.36GB, 2個文件",
      "tags": ["高清"],
      "date": "2026-05-07",
      "magnet_redacted": "magnet:?xt=urn:btih:0201592f..."
    }
  ],
  "error": null
}
```

### Redaction 規則

`magnet:?xt=urn:btih:<40 位 hex>&dn=...` →
`magnet:?xt=urn:btih:<前 8 位 hex>...`

由 `redact_magnet()` 統一處理，避免 spike 紀錄 / 子程序 log 洩漏完整可下載連結。
正式整合時，sidecar 應該提供另一個命令（例如 `unrestrict-magnets`）直接把完整 magnet
丟給 RD API，**而不是把完整 magnet 跨進程往 Rust 端送**——保持「magnet 不出 Python 邊界」原則。

### Exception 處理規則

sidecar 例外路徑**不輸出完整 traceback**，避免未來新增 RD token / stdin JSON / 完整 magnet
等敏感參數時被連帶寫進 stderr。具體：

- stderr：只寫 `sidecar error: <ExceptionType>` 一行
- stdout：仍輸出合法 JSON，但 `error` 欄位只含型別 + `<redacted>`
- 偵錯需要時：呼叫端可以在受控環境臨時開啟 verbose；不在預設行為裡

## 測試結果

**測試日期**：2026-05-10
**目標 URL**：`https://javdb.com/v/RkX3Rp`（使用者明確授權）
**OS**：Windows 11 Pro
**Python**：3.12（curl_cffi 0.14.0）
**Rust**：rustc 1.94.1

### Sidecar 直接呼叫

```
python sidecar.py fetch-javdb https://javdb.com/v/RkX3Rp
```

stdout（節錄，magnet 已遮蔽）：

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

stderr：

```
RequestsDependencyWarning: urllib3 ... doesn't match a supported version!
[INFO] app_logging: Logging initialized. ...
```

只有套件警告與 logging 初始化，符合「不洩漏 cookie/magnet」要求。

### Rust driver 對 sidecar 的呼叫

```
cargo run --release -- "https://javdb.com/v/RkX3Rp"
```

driver 自己的 summary：

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

Rust 端確認：
- ✅ sidecar exit code 0
- ✅ stdout 為合法 JSON，serde_json 直接解析成 typed struct
- ✅ `magnet_count == 3`，與 Python 直跑結果一致
- ✅ 第一筆 `magnet_redacted` 通過格式檢查（以 `magnet:?xt=urn:btih:` 開頭、含 `...`、長度 < 64）
- ⚠️ stderr 非空（套件警告），driver 未把它當失敗

### 既有測試

- `python -m unittest discover -s tests -v` → `Ran 41 tests in 0.002s OK`
- `python -m py_compile app_logging.py build.py javdb_magnet.py javdb_magnet_gui.py realdebrid.py spikes/python_sidecar_protocol/sidecar.py` → ✓

無回歸。

## 對比 rquest 路線

| 維度 | Tauri + Python sidecar | Tauri + 純 Rust + rquest |
|------|----------------------|--------------------------|
| 反爬蟲 | ✅ 已實證 200 + 3 magnets | ❓ build 卡 BoringSSL，未實證 |
| 開發機環境 | Python 3.12 + curl_cffi | cmake + NASM + MSVC（每位協作者） |
| 授權 | 主程式 MIT/Apache 風格 | rquest-util GPL-3.0 風險 |
| 打包大小 | +Python runtime ≈ 30 MB | 純 Rust 約 5–10 MB |
| 維護成本 | 沿用既有 41 個 unit test | Cloudflare 規則改 → emulation 要追 |
| 啟動延遲 | spawn Python ≈ 100–300 ms / 次 | 無額外進程 |

**Sidecar 路線唯一明顯劣勢是體積與每次呼叫的 spawn 延遲**；對這個工具的批次操作場景（一次 N 個磁力）影響有限。

## 後續若進 Tauri，sidecar command 對應到 Tauri command

```
Tauri command (Rust)       →  sidecar.py CLI
─────────────────────────     ─────────────────────────────
fetch_javdb(url)            →  python sidecar.py fetch-javdb <url>
send_to_rd(magnets, opts)   →  python sidecar.py send-rd --strategy ... [stdin: magnets json]
retry_pending()             →  python sidecar.py retry-pending
get_user_info()             →  python sidecar.py rd-user
update_settings(env)        →  純 Rust 端寫 .env，無需 sidecar
```

實作建議（非本 spike 範圍）：
1. **長啟動 → 改 stdin 雙向 stream**：避免每次重啟 Python，把 sidecar 變常駐 daemon。
   每個 request 一行 JSON，每個 response 一行 JSON。`std::process::Command` + `stdin/stdout` pipes 即可。
2. **完整 magnet 不過界**：上面 `send_to_rd` 直接把處理留在 Python 端；Rust 只看到 RD 回傳的 unrestricted https 連結。
3. **打包**：用 PyInstaller 把 sidecar 打成 `sidecar.exe`，Tauri 用 [tauri sidecar](https://tauri.app/v1/guides/building/sidecar) 機制嵌入。

## 結論

✅ **Python sidecar protocol 可行**。建議作為 Tauri 重寫的後端架構基線。
下一步應該做「打包策略 spike」：用 PyInstaller 產 `sidecar.exe`，驗證
Tauri 能在 release build 找到並啟動它，且 BSON/JSON 通訊延遲可接受。
