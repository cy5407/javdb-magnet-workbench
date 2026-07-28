# 資安與邏輯缺陷修正批次（2026-07-28）

給 Agy 執行的實作規格。**逐項照做，不得自行擴張範圍。**

## 共通規則

- Workspace：`/home/cy5407/javdb-magnet-workbench`（絕對路徑）。
- 所有 shell 命令用 `run_command` 的 `Cwd` 欄位指定目錄；命令以工具名開頭，
  **不得**使用 `cd <dir> && ...` 形式（權限採整串 prefix 比對，必被拒）。
- 每一項先寫會失敗的 Red 測試，確認 Red 後再改 production code。
- 每項完成後只跑**該項的最窄測試**（下方各項有指定命令）。
  完整 gate（pytest 全套、vitest 全套、npm run check、cargo test）由委派方執行，
  **你不要跑**，也不要把命令丟背景後等待。
- 不得 `git add`／`commit`／`push`。不得新增或升級依賴。
- 不得修改 `Task.md`、`CLAUDE.md`、`docs/` 以外的文件；本批次不含文件同步。
- 完成後輸出 5 行內摘要：修改檔案清單 + 每項 done／skipped／blocked。

## 基準

修正前：pytest 321 passed、vitest 192 passed。新測試只增不減。

---

# 項目 1【高】fetch 路徑未驗證 magnet 前綴 + dedupe key 命名空間碰撞

## 問題

同一張 handle 表有兩個寫入入口，驗證強度不一致：

- `cmd_register_magnets`（`sidecar/sidecar.py:494`）有檢查
  `if not s.lower().startswith("magnet:")`。
- `cmd_fetch_javdb`（`sidecar/sidecar.py:379`）**只檢查型別與長度**：
  `if not isinstance(full, str) or len(full) > MAX_MAGNET_URI_LEN: continue`。
  值直接來自 `javdb_scraper.py:99` 的 `link_tag.get("href", "")`，即頁面 HTML。

同時 `_magnet_dedupe_key`（`sidecar/sidecar.py:283-293`）在無法解析 BTIH 時
**退回原始 trimmed 字串當 key**，與正常的 `btih:<hex>` key **共用同一個命名空間**。

兩者疊加造成可被惡意頁面利用的碰撞。已實測重現：

頁面先提供一個 `href="btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a"` 的項目
（非 magnet URI，但 fetch 路徑不擋），它以 key `btih:c12fe1c0…` 註冊 handle H。
接著真正的 `magnet:?xt=urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a&dn=REAL`
正規化後 key 同樣是 `btih:c12fe1c0…`，於是 **dedupe 到 H**。

實測輸出：

```
displayed_name='poison' redacted='<not-a-magnet>'                -> resolves='btih:c12fe1c0…88a'
displayed_name='real'   redacted='magnet:?xt=urn:btih:c12fe1c0...' -> resolves='btih:c12fe1c0…88a'
```

第二列在 UI 顯示格式正確、redaction 正常的磁力，`resolve_magnet` 卻回傳攻擊者的
字串——它會流向剪貼簿寫入路徑與 RD 的 `addMagnet` POST body
（`realdebrid.py:179`）。這破壞了整個 `magnet_redacted` UI 所依賴的不變量。

## 修正方法

### 1-A：fetch 路徑補前綴檢查

`sidecar/sidecar.py:379`，把

```python
if not isinstance(full, str) or len(full) > MAX_MAGNET_URI_LEN:
    continue   # silently drop oversized — the page itself is malicious
```

改成同時要求 `magnet:` 前綴（與 register 路徑一致）：

```python
if not isinstance(full, str) or len(full) > MAX_MAGNET_URI_LEN:
    continue   # silently drop oversized — the page itself is malicious
if not full.lower().startswith("magnet:"):
    continue   # F-xx: hostile page may serve non-magnet hrefs; the
               # register path enforces the same prefix, so both writers
               # into the handle table agree.
```

保持「靜默丟棄」語意（不回報 invalid），與既有 oversized 分支一致。

### 1-B：dedupe key fallback 加命名空間隔離

`sidecar/sidecar.py:293`，把 `return stripped` 改為回傳帶前綴的 key，
使 fallback key 與 `btih:` key 永不可能相等：

```python
return "raw:" + stripped
```

同時更新該函式 docstring 中描述 fallback 的那句，說明加前綴的理由
（fallback key 與 btih key 必須位於不同命名空間，否則惡意輸入可偽造碰撞）。

**注意**：這會改變既有 handle 表中非 BTIH 磁力的 key 形態。這是純記憶體狀態、
每次啟動重建，無持久化，因此不需要 migration。

## 邊界與注意事項

- **不要**改 `MAX_MAGNET_URI_LEN` 或既有的長度檢查。
- **不要**把 fetch 路徑的靜默丟棄改成回報 invalid 清單——那會改變 IPC 回應
  結構，超出本項範圍。
- `_intern_magnet`、`cmd_resolve_magnet`、`cmd_forget_magnets` 的邏輯**不需要改**
  （forget 已經用 `_magnet_dedupe_key` 算 key，1-B 之後仍然對稱）。
- 前綴比對用 `.lower().startswith("magnet:")`，與 register 路徑寫法一致。

## Red 測試

寫在 `tests/test_sidecar_protocol.py`。前置狀態**必須走正式 dispatch 路徑**
（stub `sidecar.fetch_magnets` 與 `sidecar.create_session`），不得直接對
`state.magnets` / `state.magnet_to_handle` 塞值。

1. `test_fetch_javdb_drops_non_magnet_href`：stub 回傳含
   `{"magnet": "https://evil.example/pwn", ...}` 與
   `{"magnet": "javascript:alert(1)", ...}` 的項目 → 回應的 `magnets` 不含這些列，
   且 `state.magnets` 不含對應值。
2. `test_fetch_javdb_non_magnet_cannot_collide_with_real_magnet`：完整重現上述
   攻擊序列（poison 列 `btih:<hex>` 在前、真 magnet 在後）→ 斷言真 magnet 的
   handle **不等於** poison 的 handle（poison 應已被 1-A 丟棄），且
   `resolve_magnet(真 handle)` 回傳的字串以 `magnet:` 開頭。
3. `test_dedupe_key_fallback_is_namespaced`：直接呼叫 `_magnet_dedupe_key`，
   斷言非 BTIH 輸入回傳值以 `raw:` 開頭，且不等於任何 `btih:` 開頭的 key。

## 驗收命令

`Cwd=/home/cy5407/javdb-magnet-workbench`：
`.venv/bin/python -m pytest tests/test_sidecar_protocol.py -q`

---

# 項目 2【中】`settings["rd"]` 非 dict 使所有 RD 指令壞掉

## 問題

`cmd_handshake`（`sidecar.py:244`）與 `cmd_update_settings`（`sidecar.py:511`）
只驗證 `settings` **本身**是 dict，沒有驗證巢狀的 `rd`。三處取用點都假設它是 dict：

- `sidecar.py:611`：`rd_settings = (state.settings or {}).get("rd") or {}`（`_rd_client`）
- `sidecar.py:626`：同上（`_resolve_strategy`）
- `sidecar.py:652`：同上（`_resolve_int_setting`）

`or {}` 只擋 falsy 值；truthy 的非 dict（字串、list）會通過並在下一行 `.get()`
丟 `AttributeError`。已實測：

```
update_settings {"settings":{"rd":"pwn"}}  -> ok: True
rd_user                                     -> {'code': 'rd_internal', 'message': 'AttributeError: <redacted>'}
```

狀態黏著：RD 功能全毀直到下一次 `update_settings` 或重啟。

## 修正方法

新增一個模組級 helper，放在 `_rd_client` 定義之前：

```python
def _rd_settings(state: DaemonState) -> dict:
    """Nested `rd` settings, guaranteed dict.

    `settings` itself is type-guarded at the handshake/update_settings
    boundary, but the nested `rd` key is not — a truthy non-dict (string,
    list) would otherwise reach `.get()` and turn every RD command into an
    opaque `internal` envelope until settings are replaced.
    """
    settings = state.settings
    if not isinstance(settings, dict):
        return {}
    rd = settings.get("rd")
    return rd if isinstance(rd, dict) else {}
```

然後把上述三處 `rd_settings = (state.settings or {}).get("rd") or {}`
全部改成 `rd_settings = _rd_settings(state)`。

## 邊界與注意事項

- **不要**在 `cmd_update_settings` 把非 dict 的 `rd` 改成回 `bad_request`。
  外層 `settings` 是 dict 就應接受；防線放在讀取點（設定可能來自舊版檔案，
  拒收會讓使用者無法啟動）。
- **不要**動 `_coerce_int_setting` 的 `type(value) is int` 檢查（它刻意排除 bool）。
- 只改這三處；`grep -n 'get("rd")' sidecar/sidecar.py` 確認沒有第四處遺漏。

## Red 測試

`tests/test_sidecar_settings.py`，前置狀態走 `dispatch` 的 `update_settings`：

1. `test_non_dict_rd_settings_does_not_break_rd_commands`：
   `update_settings {"settings": {"rd": "pwn"}}` 後呼叫 `rd_user`
   → 錯誤碼**不得**是 `rd_internal`／`internal`（應為 `rd_no_token`
   或正常的 token 相關錯誤，代表已走到正常邏輯）。
2. 同上，`rd` 為 `[1,2]` 的變體。
3. `test_rd_settings_helper_returns_dict`：直接單元測試 `_rd_settings`，
   涵蓋 `settings=None`、`settings` 非 dict、`rd` 非 dict、`rd` 正常四種輸入。

## 驗收命令

`.venv/bin/python -m pytest tests/test_sidecar_settings.py -q`

---

# 項目 3【中】cache_wait 值域驗證缺口與設定被靜默壓低

本項含兩個相關但獨立的缺陷，**兩個都要修**。

## 3-A：`cache_wait` 使用者設定被靜默壓成 15

### 問題

`sidecar/sidecar.py:764-769`（上一批 timeout 對齊修正引入）：

```python
req_cw_raw = req.get("cache_wait")
req_cw_base = req_cw_raw if isinstance(req_cw_raw, int) and req_cw_raw >= 1 else 15
resolved_cw = _resolve_int_setting(
    state, "cache_wait_seconds", req.get("cache_wait"), 15, min_value=1,
)
cache_wait = min(resolved_cw, req_cw_base)
```

當 request 省略 `cache_wait` 時 `req_cw_base` 為 15，於是 `min()` 把使用者設定的
`cache_wait_seconds`（例如 120）**靜默壓成 15**。目前靠 `App.svelte:824` 永遠傳
該欄位才沒出事，但這是隱性耦合：任何省略該欄位的呼叫端都會踩到。

另外 `isinstance(True, int)` 為 `True`，所以 `cache_wait: true` 會通過守衛並產生 1，
與 `_coerce_int_setting` 的 `type(value) is int`（拒收 bool）不一致。

### 修正方法

保留「Python deadline 不得超過 Rust timeout 預算」這個**正確意圖**，但改成
只在 request 真的省略時才套用 15 的上限（因為此時 Rust 端就是以 15 計算預算）；
request 有帶值時，Rust 端以該值計算預算，Python 就該尊重解析結果。

```python
req_cw_raw = req.get("cache_wait")
# `type(...) is int` (not isinstance) so bools don't slip through, matching
# _coerce_int_setting.
req_has_cw = type(req_cw_raw) is int and req_cw_raw >= 1
resolved_cw = _resolve_int_setting(
    state, "cache_wait_seconds", req.get("cache_wait"), 15, min_value=1,
)
# The Rust caller computes its timeout budget from the request payload:
# `cache_wait + 90` when present, `15 + 90` when omitted (sidecar_manager.rs
# timeout_for). Our deadline must stay inside whichever budget Rust used, so
# only clamp to 15 when the request actually omitted the field.
cache_wait = resolved_cw if req_has_cw else min(resolved_cw, 15)
```

`deadline = time.monotonic() + cache_wait + 75.0` 那行維持不變。

### 邊界

- **不要**移除 clamp 邏輯本身——它防的是「Rust 用 15+90 算預算、Python 卻用
  300+75 執行」導致 Rust 先殺 sidecar 的真實 bug。
- **不要**改 Rust 端 `timeout_for`。
- 上限 `MAX_RD_CACHE_WAIT_SECS = 300` 由 Rust 端把關，本項不重複實作。

### Red 測試

`tests/test_sidecar_protocol.py`（既有 deadline 測試附近）：

1. `test_cache_wait_from_settings_respected_when_request_provides_value`：
   settings `cache_wait_seconds=120`、request 帶 `cache_wait=120`
   → `process_magnet` 收到的 `cache_wait` 為 120，deadline 預算 ≈ 195s。
2. `test_cache_wait_clamped_to_15_when_request_omits_field`：
   settings `cache_wait_seconds=300`、request **不帶** `cache_wait`
   → 收到 15、deadline ≤ 91s（既有測試已涵蓋，確認仍綠）。
3. `test_cache_wait_bool_not_treated_as_int`：request 帶 `cache_wait: True`
   → 不得被當成 1；走省略分支。

## 3-B：`write_settings` 無值域驗證，且註解謊稱有

### 問題

`app/src-tauri/src/settings.rs:114-126` 的 `write_settings` **對
`cache_wait_seconds` / `min_size_mb` 零值域驗證**，`without_secrets` 只清空
`api_token`。

但 `app/src/lib/settingsValidation.ts:8-10` 的註解寫著：

> The Rust side enforces the same shape on persist via `Settings`'s
> deserializer + `without_secrets` — frontend validation is just an early gate

**這是錯的**。後果：越界值（例如 legacy import 寫入的 `RD_CACHE_WAIT=1`）持久化後，
`sidecar_manager.rs` 的 `timeout_for` 會在碰 sidecar 前直接回 `Err`，
每次 RD 送出都失敗且訊息與設定值毫無關聯。

### 修正方法

在 Rust 端補上持久化時的 clamp（**不是**拒絕——拒絕會讓既有越界檔案無法載入）。
在 `settings.rs` 的 `write_settings` 中，`without_secrets(settings)` 之前先 clamp：

```rust
/// Clamp persisted RD numerics into the range the send path accepts.
/// The frontend validates too, but legacy import and hand-edited
/// settings.json bypass it — and an out-of-range value silently breaks
/// every RD send at `timeout_for` with an unrelated-looking error.
fn clamp_rd_settings(mut s: Settings) -> Settings {
    s.rd.cache_wait_seconds = s.rd.cache_wait_seconds.clamp(5, 300);
    s.rd.min_size_mb = s.rd.min_size_mb.min(1_000_000);
    s
}
```

在 `write_settings` 中改成
`serde_json::to_value(without_secrets(clamp_rd_settings(settings)))`。

**型別注意**：`RdSettings` 的 `min_size_mb` / `cache_wait_seconds` 是 `u32`
（`settings.rs:34-35`），但 `sidecar_manager.rs:47,53` 的
`MAX_RD_CACHE_WAIT_SECS` / `MIN_RD_CACHE_WAIT_SECS` 是 `u64`。
**不要**為了對齊而改動任一邊的型別；在 clamp 處做明確轉換即可
（例如 `MIN_RD_CACHE_WAIT_SECS as u32`），並確認轉換無截斷風險（5 與 300 皆遠小於
`u32::MAX`）。若那兩個常數目前非 `pub`，可將其改為 `pub(crate)` 以便匯入——
這是本項允許的唯一額外改動；**不要**在 `settings.rs` 重新定義字面值 5／300。
動手前先讀那兩個常數的實際值確認，不要照抄本文件的數字。

同時修正 `settingsValidation.ts:8-10` 的註解，改成描述實際行為：

```
// The Rust side clamps RD numerics on persist (`clamp_rd_settings` in
// settings.rs) and blanks `api_token` via `without_secrets`; frontend
// validation is the early gate that surfaces a friendly message before
// the value is silently clamped.
```

### 邊界

- **不要**改 `Settings` 的 serde deserializer 或欄位型別。
- **不要**讓 `write_settings` 在越界時回 `Err`——會讓使用者卡在無法儲存。
- **不要**動 `without_secrets` 的 token 清除邏輯。
- 本機 `cargo test --lib` 在 Linux 編不過（缺 Linux sidecar binary、
  `secret-service` feature）。**寫測試但不要執行**，於摘要註明 skipped。

### Red 測試

`app/src-tauri/src/settings.rs` 的 `#[cfg(test)] mod tests`：
`clamp_rd_settings` 對 `cache_wait_seconds` 為 1／9999、`min_size_mb` 為極大值時
的 clamp 結果，以及正常值不被改動。

### 驗收命令

3-A：`.venv/bin/python -m pytest tests/test_sidecar_protocol.py -q`
3-B：不執行（見上）。

---

# 項目 4【中】前端設定寫入無互斥 + theme rollback 參照捕獲

## 問題

三個路徑都會整包覆寫 `settings.json`，但彼此**不互斥**：

- `toggleTheme`（`App.svelte:244-278`）只擋 `isThemeSaving`
- `saveSettings`（`App.svelte:1263-1301`）只靠 `settingsSaving`
- `applyLegacyImportConfirmed`（`App.svelte:1310-1346`）只靠 `legacyBusy`

Rust 端 `write_settings` 是整包覆寫、無合併（`settings.rs:115-126`），
所以交錯時 last-writer-wins：`saveSettings` 寫入含新 RD 設定的 draft →
`toggleTheme` 的寫入後落地（含**舊** RD 設定 + 新 theme）→ 使用者剛儲存的
`min_size_mb`／`cache_wait` 被靜默還原，UI 卻顯示「設定已儲存」。

另有參照捕獲 bug：`toggleTheme` 在 `await`（`App.svelte:261`）期間，若
`saveSettings`／`applyLegacyImportConfirmed` 透過 `loadAndApplySettings()`
（`App.svelte:187`）把 `settings` 換成**新物件**，則 catch 分支的
`settings.ui.theme = oldSettingsTheme`（`App.svelte:268`）會把舊 theme 寫進新物件，
造成磁碟與記憶體分歧。

## 修正方法

### 4-A：單一 settings-write busy flag

新增一個 `$derived`，放在三個 flag 宣告之後：

```ts
// Any settings.json writer excludes the others — write_settings is a
// whole-file overwrite with no merge, so interleaved writes silently
// revert whichever fields the loser had changed.
let settingsWriteBusy = $derived(isThemeSaving || settingsSaving || legacyBusy);
```

三個 handler 的入口 guard 全部改用它：

- `toggleTheme`：`if (isThemeSaving) return;` → `if (settingsWriteBusy) return;`
- `saveSettings`：入口補 `if (settingsWriteBusy) return;`（目前只靠按鈕 disabled）
- `applyLegacyImportConfirmed`：入口補 `if (settingsWriteBusy) return;`

對應的按鈕 `disabled` 也改用 `settingsWriteBusy`（主題切換鈕、儲存設定鈕、
legacy import 相關鈕）——**逐一 grep 確認**目前綁 `isThemeSaving` /
`settingsSaving` / `legacyBusy` 的所有 `disabled`，全部換成 `settingsWriteBusy`。
各 handler 內部**仍然要**繼續設定自己的原 flag（顯示「儲存中…」等文案需要）。

### 4-B：theme rollback 不再依賴 `settings` 參照

`toggleTheme` 的 catch 分支改成先檢查 `settings` 是否仍是同一個物件：

在 `isThemeSaving = true;` 之前捕獲參照：

```ts
const settingsRef = settings;
```

catch 分支把 `settings.ui.theme = oldSettingsTheme;` 改成：

```ts
// Only roll back if `settings` is still the object we mutated — a
// concurrent reload may have replaced it, in which case the new object
// already carries the canonical on-disk value.
if (settings === settingsRef) {
  settings.ui.theme = oldSettingsTheme;
}
```

`theme`、`settingsDraft`、`applyTheme(oldTheme)` 的 rollback 維持不變。

## 邊界

- **不要**把三個 flag 合併成單一 `$state`——各自的文案與 finally 清除邏輯依賴
  獨立 flag。只新增 `$derived` 聚合。
- **不要**改 `loadAndApplySettings` 或 Rust `write_settings`。
- **不要**把 `toggleTheme` 改成部分更新（只寫 theme 欄位）——那是更大的
  設計變更，不在本批次。
- 4-A 之後 4-B 的競態實務上已不可達，但仍要做（防禦深度，且 legacy import
  的 reload 路徑不完全受 flag 保護）。

## Red 測試

`app/src/App.test.ts`（沿用既有 invoke mock 模式）：

1. `test`：`isThemeSaving`／`settingsSaving`／`legacyBusy` 任一為 true 時，
   呼叫另外兩個 handler **完全不觸發** `write_settings` invoke（零 invoke）。
2. `test`：`toggleTheme` 的 `write_settings` 失敗且期間 `settings` 被替換成新物件
   → 新物件的 `ui.theme` **不被**改寫（rollback 不污染新物件）。

## 驗收命令

`Cwd=/home/cy5407/javdb-magnet-workbench/app`：`npx vitest run src/App.test.ts`

---

# 項目 5【中】補回被刪除的 429 retry cap 測試

## 問題

commit `ef075ae` 刪除了 `tests/test_realdebrid_request.py` 的
`test_429_gives_up_after_3_retries`，導致 `_retry_after_rate_limit`
（`realdebrid.py:108-111`）的 `retry_count >= 3` 放棄路徑**零覆蓋**。

這違反 `CLAUDE.md` 的「既有測試不得刪除或弱化」規範。該檔案現存的 429 測試只有
`test_429_then_200_retries_and_succeeds`、`test_429_uses_default_5s_when_no_retry_after`、
`test_429_negative_retry_after_retries_immediately_if_remaining_budget`。

## 修正方法

**只加測試，不改 production code。**

在 `tests/test_realdebrid_request.py` 的 `RequestRateLimit` class 中新增
`test_429_gives_up_after_3_retries`，沿用該 class 既有寫法
（`mock.patch.object(self.rd.session, "request", side_effect=[...])` +
`mock.patch("realdebrid.time.sleep")`）：

- `side_effect` 給 4 個連續 429 回應（初次 + 3 次重試）。
- 斷言拋出 `RealDebridError`，訊息含 `HTTP 429`。
- 斷言 `mock_req.call_count == 4`（初次 + 3 次重試，不多不少）。
- 斷言 `mock_sleep.call_count == 3`。

## 邊界

- **不要**改 `realdebrid.py` 的任何一行。
- **不要**改既有三個 429 測試。
- 重試次數上限是 3（`retry_count >= 3`），對應總請求數 4——寫測試前先讀
  `realdebrid.py` 的 `_retry_after_rate_limit` 確認，不要照抄本文件的數字。

## 驗收命令

`.venv/bin/python -m pytest tests/test_realdebrid_request.py -q`

---

# 項目 6【中】startScrape 未 forget 舊 handle，孤兒 handle 累積

## 問題

`clearResults`（`App.svelte:590-608`）會呼叫 `forget_magnets` 清掉舊 handle，
但 `startScrape`（`App.svelte:303-312`）重建 `groups` 時**直接丟棄**舊的 web group
（只保留 manual group），**沒有** forget 那些 handle。

`App.svelte:601-602` 的 catch 註解宣稱：

```
// Don't surface as an error — UI is already cleared, sidecar will GC
// stale handles on its own eventually.
```

**這個 GC 不存在**。sidecar 端 `_intern_magnet`（`sidecar.py:296-311`）從不 evict，
`cmd_forget_magnets` 是唯一移除路徑，`MAX_FETCH_MAGNETS` / `MAX_REGISTER_MAGNETS`
都只是**單次呼叫**上限。反覆擷取會讓 `state.magnets` 與 `state.magnet_to_handle`
一路長到 process 結束。

## 修正方法

### 6-A：`startScrape` 丟棄舊 web group 前先 forget

在 `App.svelte:303` 重建 `groups` **之前**，收集即將被丟棄的 web group 的
handle id，重建之後 best-effort forget（不阻擋擷取流程）：

```ts
// Web groups are about to be replaced — release their handles so the
// sidecar's handle table doesn't grow across repeated scrapes. Manual
// groups survive, so their handles must NOT be forgotten.
const staleIds: string[] = [];
for (const g of groups) {
  if (!isManualGroup(g) && g.result) {
    for (const m of g.result.magnets) staleIds.push(m.handle_id);
  }
}
```

在 `groups = [...]` 重建之後、`isScraping = true` 之前插入：

```ts
if (staleIds.length > 0) {
  try {
    await invoke("forget_magnets", { handleIds: staleIds });
  } catch (e) {
    // Best-effort: a failed release only costs sidecar memory, and the
    // handles are already unreachable from the UI.
    console.warn("forget_magnets (stale scrape handles) failed:", e);
  }
}
```

**關鍵**：`staleIds` 只能包含 web group 的 handle。manual group 存活，
forget 掉它們的 handle 會讓手貼列變成 `unknown_handle`。

### 6-B：修正說謊的註解

`App.svelte:601-602` 的註解改成不宣稱有 GC：

```ts
// Don't surface as an error — the UI is already cleared and the handles
// are unreachable from it. The sidecar has no GC, so a failed release
// just leaves them resident until the process exits.
```

`App.svelte:604` 的 `statusMessage = "結果已清空（sidecar 之後會自動 GC）"`
同樣要改（它對使用者說了同一個謊），改為 `"結果已清空"`。

## 邊界

- **不要**在 sidecar 端實作 GC 或 LRU——那是設計變更，不在本批次。
- **不要**改 `clearResults` 的 forget 呼叫本身（它是對的）。
- **不要**讓 forget 失敗阻止擷取開始。
- 注意 `startScrape` 已是 `async`，可直接 `await`；但 forget 必須在
  `groups` 重建**之後**才送出，避免失敗時 UI 與 sidecar 狀態不一致。
- 若有測試斷言 `"sidecar 之後會自動 GC"` 這段文案，一併更新。

## Red 測試

`app/src/App.test.ts`：

1. `test`：既有 web group（含 handle）+ manual group 的狀態下呼叫 `startScrape`
   → `forget_magnets` 被呼叫**一次**，且 `handleIds` **只含** web group 的 handle、
   **不含** manual group 的 handle。
2. `test`：無既有 web group 時呼叫 `startScrape` → 完全不呼叫 `forget_magnets`。
3. `test`：`forget_magnets` 拋錯時，擷取流程仍正常進行（`fetch_javdb` 仍被呼叫）。

## 驗收命令

`Cwd=/home/cy5407/javdb-magnet-workbench/app`：`npx vitest run src/App.test.ts`

---

# 明確的非目標（本批次不做）

以下項目已知存在，但**不在本批次範圍**，不要順手修：

- `docs/architecture/contracts/` 的文件漂移（`rd_user` 握手閘、`update_settings`
  錯誤路徑、`_emit` 的 EPIPE `sys.exit(0)`、`_rd_client` 簽章）。
- `scripts/build-release.ps1:311` 原始碼機密掃描比對 `origin/HEAD..HEAD` 導致
  掃 0 檔案的盲點。
- legacy import 的任意路徑讀取／symlink 追隨／`.env` 內容回傳前端
  （`commands.rs:605,614`）。
- RD 下載連結無 scheme 驗證即上剪貼簿（`rdSender.ts:61`）。
- `torrent_id` / token override 未做 charset 驗證（`realdebrid.py:185`）。
- restricted link 洩漏到 stderr（`realdebrid.py:496`）。
- base32 BTIH 不正規化導致 dedupe 失效。
- `pending_torrents.json` / `settings.json` 非原子寫入。
- sidecar handle 表的全域上限或 LRU。
- 任何與上述無關的重構、格式化、依賴更新。
