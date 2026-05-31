# Task: 修復多模型審查確認的邏輯與契約問題

目標 repo: `C:\Users\cy5407\Desktop\程式語言\爬蟲`

預期下一輪執行方式: 用 `/goal` 讀取並完成本檔，不要只提出計畫。下一輪 agent 應先讀本檔、抓 baseline `git status --short --branch`，再逐項實作、測試、回報。

## 背景

本檔彙整多個模型審查結果後，已由 Codex 逐項核對目前 checkout。不要直接相信任一模型原始摘要；以本檔列出的任務、完成條件與驗證方法為準。

已驗證的 baseline:

- `git status --short --branch` 目前只有既有未追蹤檔:
  - `?? javdbmagnet.exe`
  - `?? sidecar.exe`
- `python -m pytest -q` 目前通過: `289 passed, 6 subtests passed`
- `npm test` 目前通過: `142 passed`
- `cargo test --lib` 目前通過: `70 passed`
- `npm run build` 通過
- `cargo clippy --all-targets -- -D warnings` 通過
- `Invoke-ScriptAnalyzer -Path .\scripts -Recurse -Settings .\PSScriptAnalyzerSettings.psd1` 無診斷
- `npm run check` 目前失敗，錯在 `app/src/lib/magnetUtils.test.ts:298` 把 `defaultFilterState` 函式本身拿去 spread，少了 `()`

## 硬性邊界

- 不要碰 `javdbmagnet.exe`、`sidecar.exe`，它們是既有未追蹤產物。
- 不要擴大 JavDB host allowlist 到 `javdb\d*.com`。沒有可信官方來源前，這會增加 cookie 外洩風險。
- 不要把 `check_torrent` 的 `waiting_files_selection` no-pick retry path 改成 delete + raise。現有 pending retry 契約刻意不保存 magnet，no-pick 回 pending 是既有測試保護的行為。
- 不要做 unrelated refactor。每個 changed line 必須能對應到本檔任務或測試。
- 不要 commit / push，除非使用者另行要求。
- 若需要新增或修改 non-trivial implementation decision，更新 repo root 的 `implementation-notes.md`，只記錄「為什麼」，不要複製 diff。

## P1 必修

### P1-1. 修復 `npm run check` 失敗: `defaultFilterState()` typo

問題:

- `app/src/lib/magnetUtils.test.ts:298` 使用 `{ ...defaultFilterState, keyword: "XYZ" }`
- `defaultFilterState` 是函式，少了 `()`
- Vitest 會過，但 `svelte-check` 會報 `FilterState` 欄位缺漏

修復要求:

- 改成 `{ ...defaultFilterState(), keyword: "XYZ" }`
- 不要改測試語意，只修 typo

完成條件:

- `npm run check` 不再因 `magnetUtils.test.ts` 失敗
- `npm test -- src/lib/magnetUtils.test.ts` 通過

驗證:

```powershell
cd C:\Users\cy5407\Desktop\程式語言\爬蟲\app
npm run check
npm test -- src/lib/magnetUtils.test.ts
```

### P1-2. 修復 RD unrestrict 部分失敗時 Python/Rust DTO 不相容

問題:

- `realdebrid.py::_collect_links` 成功 entry 回傳:
  - `original`
  - `download`
  - `filename`
  - `filesize`
  - `streamable`
- 失敗 entry 目前只回:
  - `original`
  - `error`
- Rust `app/src-tauri/src/commands.rs::RdLink` 目前要求 `download` 和 `filename` 為必填 `String`
- 因此單一 unrestrict link 失敗時，Python sidecar 仍可能回 `status="completed"` 與混合 links；Rust 在 `serde_json::from_value::<Vec<RdLink>>` 時會因缺 `download` / `filename` 讓整筆 completed response 失敗，前端拿不到其他成功 link

修復方向擇一，選最小且契約最清楚的方案:

1. 讓 Python error entry 補齊 Rust DTO 必填欄位:
   - `download: ""`
   - `filename: ""`
   - `filesize: 0`
   - `streamable: 0`
   - 保留 `error`
   - 同時 Rust/TS `RdLink` 若要保留 error 顯示，補 optional `error`
2. 或讓 Rust `RdLink` 對 `download` / `filename` 加 `#[serde(default)]`，並加 optional `error`

偏好:

- 優先讓跨語言 payload 明確完整；不要只靠 Rust default 吞掉 Python 契約不一致。
- 前端若現有流程只複製 `download`，空 download 必須被既有 filter 或後續邏輯排除，不能把空行複製到 clipboard。

必加測試:

- Python: 擴充 `tests/test_realdebrid_request.py::test_unrestrict_failure_recorded_as_error_entry`，確認失敗 entry 仍含 `download=""`、`filename=""`、`filesize=0`、`streamable=0`，並保留 `error`
- Rust: 增加或擴充 `commands.rs` 測試，確認含 error entry 的 completed payload 可 deserialize 成 `RdLink`，不會讓整筆 response 失敗
- TS 若改 `RdLink` 型別，更新對應型別或測試

完成條件:

- 單一 link unrestrict 失敗不會讓整筆 completed response 在 Rust DTO deserialize 階段失敗
- 成功 link 仍照常回傳並可被前端複製
- error entry 不會產生可複製的空下載連結

驗證:

```powershell
cd C:\Users\cy5407\Desktop\程式語言\爬蟲
python -m pytest tests/test_realdebrid_request.py -q
cd app\src-tauri
cargo test --lib
```

### P1-3. 修復 `copy_magnets_bulk` 吞掉 sidecar 錯誤碼

問題:

- `app/src-tauri/src/commands.rs::copy_magnets_bulk` 對 `resolve_magnets` 失敗時回固定字串 `"resolve_magnets failed"`
- 同檔其他 command 多數使用 `ensure_ok(&resp)?`，會傳遞 sidecar 穩定 error code
- 現況會讓前端失去 `unknown_handle` / `bad_request` / sidecar error code 等診斷資訊

修復要求:

- 將手寫 `if !ok { return Err("resolve_magnets failed".to_string()) }` 改成 `ensure_ok(&resp)?;`
- 補 Rust 測試，mock sidecar 回 `{ ok:false, error:{ code:"unknown_handle", ... } }` 時，`copy_magnets_bulk` 對外錯誤字串是 `unknown_handle`，不是通用字串

完成條件:

- `copy_magnets_bulk` 和其他 Rust command 的 error propagation 一致
- 批次 copy 的成功路徑行為不變

驗證:

```powershell
cd C:\Users\cy5407\Desktop\程式語言\爬蟲\app\src-tauri
cargo test --lib
```

## P2 應修

### P2-1. 修復 legacy `.env` 數值匯入 `u64` → `u32` 毒化設定

問題:

- `app/src-tauri/src/legacy_import.rs::assign_u64_setting` 對 `RD_MIN_SIZE_MB` / `RD_WAIT_TIMEOUT` / `RD_CACHE_WAIT` parse `u64`
- `app/src-tauri/src/settings.rs::RdSettings` 對應欄位是 `u32`
- 若 legacy `.env` 有超過 `u32::MAX` 的值，匯入會成功寫進 `settings.json`，之後 `read_settings` 反序列化可能整包失敗

修復要求:

- 將 numeric legacy setting parse 限制到 `u32`
- 超界或負值都進 `warnings`，不要寫入 `settings_patch`
- warning 文字要包含 env key，但不要回灌秘密值；這些欄位不是 secret，但維持低回顯比較一致

必加測試:

- `RD_CACHE_WAIT=99999999999` 或類似超界值不寫入 patch，並產生 warning
- 合法值仍寫入原欄位

驗證:

```powershell
cd C:\Users\cy5407\Desktop\程式語言\爬蟲\app\src-tauri
cargo test --lib legacy_import
cargo test --lib
```

### P2-2. 處理 `wait_timeout_seconds` 死設定

問題:

- UI 顯示 `wait_timeout_seconds` 欄位
- `Settings` / legacy import / validation 都有此欄位
- 送 RD 時前端只傳 `file_pick`、`min_size_mb`、`cache_wait`
- Rust `sidecar_manager::timeout_for` 只用 `cache_wait + slack`
- Python sidecar / `RealDebrid.process_magnet` 也只用 `cache_wait`
- 使用者調整 `wait_timeout_seconds` 不會影響實際行為

決策要求:

- 在實作前先讀現有設計註解與測試，選其中一條路:
  1. 讓 `wait_timeout_seconds` 真正控制某個等待/timeout budget；或
  2. 若它已被 `cache_wait_seconds` 取代，移除 UI/validation/legacy import 或改文案，避免使用者以為有效

偏好:

- 不要同時保留兩個語意重疊但行為不同的等待設定。
- 若保留 `cache_wait_seconds` 作唯一實際等待值，應清楚移除或降級 `wait_timeout_seconds`，不要留下死欄位。

完成條件:

- 沒有「可設定但完全不影響任何行為」的 `wait_timeout_seconds`
- 對應 docs/tests/type 都一致

驗證:

```powershell
cd C:\Users\cy5407\Desktop\程式語言\爬蟲\app
npm test -- src/lib/settingsValidation.test.ts src/lib/rdSender.test.ts
npm run check
cd src-tauri
cargo test --lib
```

### P2-3. 修復 `min_size_mb=0` 前後端契約衝突，並排除 bool

問題:

- 前端 `validateMinSizeMb` 允許 `0`
- UI input `min="0"`
- Python sidecar `_resolve_int_setting` 只接受 `int > 0`，所以 `min_size_mb=0` 會 fallback 到 500
- 同 helper 也會把 Python `True` 當 `1`，因為 `bool` 是 `int` 子類

修復要求:

- 不要用同一條 `>0` 規則處理所有 int settings
- `min_size_mb` 應接受 `0` 和正整數，拒絕負數、bool、非整數、髒字串
- `cache_wait_seconds` 應保持現有 floor 語意，不允許 `0`
- 若 string digit 有既有支援，保留合理行為；是否接受 `" 12 "` 要尊重現有測試或明確改測試

必加/改測試:

- `min_size_mb=0` setting 解析為 0，不 fallback 500
- `cache_wait_seconds=0` 仍 fallback 或被拒，不能變合法
- `True` / `False` 不被當作 1 / 0
- `cmd_rd_send_magnet` 使用 settings 中 `min_size_mb=0` 時，傳給 `_rd_client(..., min_size_mb=0)`

驗證:

```powershell
cd C:\Users\cy5407\Desktop\程式語言\爬蟲
python -m pytest tests/test_sidecar_settings.py tests/test_sidecar_protocol.py -q
cd app
npm test -- src/lib/settingsValidation.test.ts
```

### P2-4. 統一直接貼 magnet 的大小寫契約

問題:

- 前端 `parseMagnetBatch` 用 `/^magnet:/i`，接受 `MAGNET:`
- `app/src/lib/scraper.test.ts` 明確測試接受 `MAGNET:`
- Python sidecar `cmd_register_magnets` 用 case-sensitive `s.startswith("magnet:")`
- 目前最小重現: `MAGNET:?xt=urn:btih:abc` 會得到 `registered: []`、`invalid: ["MAGNET:?xt=urn:btih:abc"]`

修復方向擇一:

1. 前端 normalize scheme 成小寫 `magnet:` 再送 sidecar；或
2. sidecar 檢查改成 case-insensitive，並決定保存原始 text 或 canonical text

偏好:

- 保留 magnet URI 原始 query body，不要改動 `xt` / `dn` / tracker 內容。
- 只 canonicalize scheme 或只在 sidecar 判斷時 lower prefix。
- dedupe key 行為不得退化。

必加測試:

- sidecar `register_magnets` 接受 `MAGNET:?xt=...`
- 前端既有 `parseMagnetBatch("MAGNET:...")` 測試仍通過
- 若有 redaction / dedupe key 受影響，補相關測試

驗證:

```powershell
cd C:\Users\cy5407\Desktop\程式語言\爬蟲
python -m pytest tests/test_sidecar_protocol.py -q
cd app
npm test -- src/lib/scraper.test.ts
```

### P2-5. 修復清空結果後 in-flight scrape callback 復活 UI 的競態

問題:

- `App.svelte::startScrape` progress callback 直接寫 `groups[ev.index - 1] = ev.group`
- `clearResults` abort 後立刻 `groups = []`
- in-flight `fetch_javdb` 不一定被真正中斷；若稍後 callback 回來，可能把已清空的結果寫回 UI

修復要求:

- 使用 generation/run id 或等效 guard:
  - 每次 startScrape 產生 scrape run id
  - clearResults 或 cancel 後使目前 run id 失效
  - progress callback / finally 只允許目前 run id 寫 UI state
- 不要只靠 `AbortController.abort()`，因為底層 invoke 不保證已取消

必加測試:

- 優先抽出可測 helper；若直接測 Svelte component 成本太高，至少把 scrape state reconciliation guard 抽成小函式測試
- 測試「clear 後 late progress event 不會寫回 groups」

完成條件:

- 清空結果後，舊 scrape 的 late callback 不會復活結果
- 正常 scrape progress 仍更新 groups / scrapeProgress

驗證:

```powershell
cd C:\Users\cy5407\Desktop\程式語言\爬蟲\app
npm test
npm run check
```

## P3 小修 / 防禦式補強

### P3-1. retry backoff sleep 後再次檢查 abort

問題:

- `app/src/lib/scraper.ts::fetchGroupWithRetry` rate-limit 後 `await sleep(...)`
- sleep 後沒有再次檢查 `signal.aborted`，會直接進下一輪 retry
- 使用者若在 10-15 秒 backoff 期間取消，仍可能多送一次 retry request

修復要求:

- 在 retry sleep 後、下一輪 fetch 前檢查 abort
- 若已 abort，保持 group 為 pending 或標記為取消，需和既有 abort 行為一致

必加測試:

- `scrapeBatch` 第一次 fetch 丟 429，sleep callback 內 abort，確認 fetcher 不會被呼叫第二次

驗證:

```powershell
cd C:\Users\cy5407\Desktop\程式語言\爬蟲\app
npm test -- src/lib/scraper.test.ts
```

### P3-2. 前端 URL parser 提早拒絕 `http://`

問題:

- `parseUrlBatch` 接受 `http://`
- sidecar `fetch_javdb` 強制 `https://`
- 現況會讓錯誤到 sidecar 才出現

修復要求:

- 若產品決策維持 JavDB fetch 僅允許 HTTPS，前端 `parseUrlBatch` 應只接受 `https://`
- 更新測試命名，避免 `non-http` 誤導；加入 `http://` 被 drop 的測試

驗證:

```powershell
cd C:\Users\cy5407\Desktop\程式語言\爬蟲\app
npm test -- src/lib/scraper.test.ts
```

### P3-3. 低風險 hardening，可視時間處理

這些不是主線完成條件；若做，必須補測試，不要只改 code:

- `realdebrid.py::_redact_log_kwargs` 對非 dict `data` / `headers` 不要 `AttributeError`
- `app/src-tauri/src/commands.rs::import_cookies_block` 在 `create_dir_all` 失敗後早退，避免雙重 warning
- `app_logging.py::_try_make_dir` 把 `probe.unlink()` 放進獨立 cleanup guard，避免 unlink 失敗時把可寫目錄判成不可寫
- `realdebrid.py::pick_files` 對 RD file schema 缺鍵的策略需先決定。不要無腦改 `f.get(...)` 後默默選錯檔；若 schema 異常，fail fast 可能更安全

## 明確不做

- 不處理 Gemini 建議的 `javdb\d*.com` 數字鏡像 allowlist。
- 不處理 Gemini 建議的 `check_torrent` no-pick delete + raise。
- 不為 malformed `magnet:xt=...` 加 `parsed.path` fallback，除非另開 UX 容錯任務並同步測 dedupe canonicalization。

## 全量驗證 Gate

完成 P1/P2 後，至少跑:

```powershell
cd C:\Users\cy5407\Desktop\程式語言\爬蟲
python -m compileall -q realdebrid.py javdb_scraper.py app_logging.py sidecar legacy tests
python -m pytest -q

cd app
npm test
npm run check
npm run build

cd src-tauri
cargo test --lib
cargo clippy --all-targets -- -D warnings

cd C:\Users\cy5407\Desktop\程式語言\爬蟲
Invoke-ScriptAnalyzer -Path .\scripts -Recurse -Settings .\PSScriptAnalyzerSettings.psd1
```

再跑工具掃描。Codex 全域已安裝 `tool-scan` skill；若 slash command 可用，使用 `/tool-scan`。若 slash command 不可用，直接跑:

```powershell
python C:\Users\cy5407\.codex\skills\tool-scan\run_tool_scan.py --target C:\Users\cy5407\Desktop\程式語言\爬蟲 --scope full
```

完成條件:

- 上述 verification gate 全部通過，或任何失敗都必須明確分類為 pre-existing / environment blocker，並附上實際輸出摘要
- `npm run check` 必須變綠，不能列為 blocker
- `git diff --name-only` 只包含本任務需要的檔案
- 最終回報要列出:
  - 修改檔案
  - 每個 P1/P2/P3 項目是否完成
  - 實際跑過的驗證命令與結果
  - 若有未完成項目，說明原因與剩餘風險

## 建議 /goal 啟動文字

```text
/goal 請在 C:\Users\cy5407\Desktop\程式語言\爬蟲 完成 docs/Task.md。請先讀 Task.md，抓 baseline git status，依 P1 → P2 → P3 順序修復。不要碰既有未追蹤 exe，不要 commit/push。每個修復都要補或更新測試，最後跑 Task.md 的全量驗證 Gate，並回報實際命令結果。
```
