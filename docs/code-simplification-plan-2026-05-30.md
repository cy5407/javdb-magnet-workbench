# 程式碼精簡計劃 — JavDBMagnet

**日期**：2026-05-30
**範圍**：整個專案生產程式碼(約 11,700 行)
**方法**：`/workflow` 平行審查,6 個模組群組各派一個資深工程師 agent,只找**保持行為不變**的精簡 / 去重 / 慣用寫法機會(不找 bug、不找資安,那是另一份報告)。每個 agent 都被要求遵守本專案 CLAUDE.md 的「surgical changes / 不過度抽象 / 不為單一用途加彈性」哲學。

## 總結論

**這份程式碼已經相當精簡**,沒有需要重寫的地方、沒有過度抽象、幾乎沒有 dead code。多數 agent 主動「撤回」最初疑似的 dead-code 發現(經 grep 確認其實有用)。可動的多是**重複片段抽成小 helper**,全部 behavior-preserving、多數低風險,合計約可省 **~150 行**。

> ⚠️ 注意:本計劃是**建議**,尚未動工。多個項目跨檔(如 `errText`),且部分檔案有 vitest / cargo test 覆蓋 —— **每個改動套用後請跑對應測試**。

---

## 建議執行順序(高價值低風險先)

### 階段一:Rust 後端去重(commands.rs 為主,省 ~46 行)
| ID | 檔案:行 | 類型 | 內容 | 省行 | 風險 |
|---|---|---|---|---|---|
| SIMP-rust-commands-01 | `commands.rs` 9 處 | duplication | `if !resp.get("ok")...{ return Err(_err_code(&resp)) }` 重複 9 次 → 抽 `fn ensure_ok(resp)->Result<(),String>`,各處改 `ensure_ok(&resp)?;`(錯誤字串不變) | 16 | low |
| SIMP-rust-commands-02 | `commands.rs:445-577` | duplication | `resp.get("X").and_then(as_str).unwrap_or("").to_string()` 重複 8+ 次 → 抽 `fn str_field(resp,key)->String` | 20 | low |
| SIMP-rust-commands-03 | `commands.rs:1137-1141` | duplication | `update_sidecar_settings` 內聯了已存在的 `blank_rd_api_token(&mut Value)`(812-818)→ 直接呼叫之 | 4 | low |
| SIMP-rust-commands-04 | `commands.rs:417-423` | verbose | `RdSendOptions` 全 `Option` 欄位 → `#[derive(Default)]` + `options.unwrap_or_default()` | 6 | low |

### 階段二:Rust 其餘 + Python(省 ~26 行)
| ID | 檔案:行 | 類型 | 內容 | 省行 | 風險 |
|---|---|---|---|---|---|
| SIMP-rust-sidecar-import-01 | `legacy_import.rs:219-236` | verbose | `pick_str`/`pick_f64` 的 3-arm match 其實是「主鍵→備鍵」查找 → `obj.get(k1).and_then(as_str).or_else(\|\| ...)` | 8 | low |
| SIMP-rust-sidecar-import-02 | `sidecar_manager.rs:196-216` | duplication | hello/handshake 兩段近似 ok-check → 抽 `fn require_ok(resp, what)` | 6 | low |
| SIMP-py-rd-01 | `realdebrid.py:353-358, 407-412` | duplication | 兩處重複「組 picked_files + picked_names + log」→ 抽 `_format_picked_names(files, picked)`(兩邊各保留自己的 log 字串) | 4 | low |
| SIMP-rust-storage-01 | `pending.rs:144-158` | verbose | `for ... + let mut changed` flag → `if let Some(e)=list.iter_mut().find(...)`(行為相同,有測試覆蓋 hit path) | 4 | low |
| SIMP-py-sidecar-01 | `sidecar.py:584-595` | duplication | `_resolve_int_setting` 的 int/digit 強制轉型寫了兩次 → 抽一個 local `coerce()` closure | 4 | **medium** |

### 階段三:前端去重(省 ~48 行,跨檔)
| ID | 檔案:行 | 類型 | 內容 | 省行 | 風險 |
|---|---|---|---|---|---|
| SIMP-frontend-03 | `App.svelte` 3 處 | duplication | `openSettingsEditor`/`saveSettings`/`revertSettingsDraft` 重複建同一 settings draft literal → 抽 `freshSettingsDraft(s)` | 8 | low |
| SIMP-frontend-05 | `App.svelte:390-398, 501-507` | duplication | `copyVisible` 與 `visibleMagnets` 各自手刻 `Set<string>` 去重 → 改用既有(且已測過)的 `magnetUtils.dedupeByHandleId` | 8 | low |
| SIMP-frontend-06 | `App.svelte:797-826` | duplication | `retryAllPending` 的 completed/missing 兩分支跑相同 torrent_id 對帳迴圈 → 抽 `patchRowByTorrentId(id, patch)` | 10 | low |
| SIMP-frontend-02 | `App.svelte` + `scraper.ts` + `rdSender.ts` | duplication | `e instanceof Error ? e.message : String(e)` 重複 ~8 次 → 抽共用 `errText(e)`(跨檔,略超出單檔 surgical 邊界) | 6 | low |
| SIMP-frontend-04 | `magnetUtils.ts:97-124` | duplication | largest/smallest/fewest_files 三個 `reduce` 分支 → 一個 `isBetter` comparator + 單一 reduce;順手移除不可達的 `return rows.slice()` | 12 | **medium** |
| SIMP-frontend-07 | `types.ts:161-164` | dead-code | `SortState` interface 零引用(App 用兩個獨立 state var)→ 刪除;但 `frontend-lib.md` 合約文件有列,需一併更新 | 4 | low |

### 階段四:建置腳本(省 ~25 行)
| ID | 檔案:行 | 類型 | 內容 | 省行 | 風險 |
|---|---|---|---|---|---|
| SIMP-build-release-01 | `build-release.ps1:72-85` | better-stdlib | 手刻 `Get-Sha256Hex` → 內建 `(Get-FileHash -Algorithm SHA256).Hash`(同樣回大寫 hex) | 12 | low |
| SIMP-build-release-02 | `build-release.ps1:224-244` | redundant | 兩個連續 `foreach ($f in $StagedFiles)` 掃同一集合 → 併成一趟(leaf 只算一次) | 5 | low |
| SIMP-build-release-03 | `build-release.ps1:296-307, 371-380` | duplication | 兩處 `[regex]::Matches` per-pattern 迴圈 → 抽 `Scan-Patterns($text,$Patterns)` | 8 | **medium** |

---

## 刻意「不動」的項目(已評估,動了反而是 churn)

agent 們依專案哲學主動排除了這些「看起來像但不該改」的:

- **`secret_store.rs` ↔ `cookie_store.rs` 的 entry()/delete_internal 樣板**:兩個刻意分離的單用途模組,抽共用 generic keyring wrapper = 投機抽象(CLAUDE.md 明文禁止),且兩者 ACCOUNT 常數與驗證規則不同,耦合成本 > 省的行數。
- **`RdSendOutcome` / `RdCheckOutcome` enum**:看似重複,實為不同的 public API 合約,**不可**合併。
- **`flashAction.run`、`isRateLimitError`、`collectDownloadLinksFromRow`、`parseFileCount`、`setup_logging`、`remove_pending` 等**:初疑為 dead,grep 後確認 production + 測試都有用,**保留**。
- **`legacy/javdb_magnet_gui.py` 的去重項(SIMP-legacy-gui-01/02)**:檔案已 retired(docstring 禁止 production import),除非為別的原因動到該檔,否則不要單純為去重而 churn。
- **`_log_file_for`、`select_files` 的 str/list 分支、`strip_matched_quotes`、`drain_line`、`mark_dead`、`dispatch_env_entry`**:已是慣用 / 有文件化理由,改了只是 churn。

---

## 整體評估

- 可動項目 ~20 個,合計省 **~150 行 / 11,700 行(~1.3%)** —— 數字小正說明 codebase 本來就精實。
- 多數 effort = trivial/small、risk = low;3 個標 medium 的(SIMP-frontend-04 tie-break、SIMP-py-sidecar-01、SIMP-build-release-03)務必跑測試覆核。
- 最划算的兩組:**階段一(Rust commands 去重)** 與 **階段三(前端去重)**,各約省 46–48 行且都低風險。

> 完整逐項(含 agent 的 current vs proposed 對照)見 workflow 輸出:
> `C:\Users\cy5407\AppData\Local\Temp\claude\...\tasks\wctlo8cq1.output`
