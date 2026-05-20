# 全 App 按鈕點擊回饋（TDD 改造）

## TDD vs. 非 TDD 區隔（誠實標示）

| 環節 | TDD？ |
|---|---|
| `createFlashController` 設計與實作 | ✅ 真 TDD：6 個失敗測試 → 紅燈 → 實作 → 6/6 綠燈 |
| App.svelte refactor 改用 controller | ❌ 不是 TDD（純改名 / 替換 import），但被既有 127 測試守住不回歸 |
| 為每顆動作按鈕加 `class:flash-ok` + handler 呼叫 `flash.flash(key)` | ❌ 不是 TDD（純模板繫結，無可測單元） |
| CSS `:active` 下沉 + `.flash-ok` 半透明綠 | ❌ 不是 TDD（純 CSS） |

上一輪我把「事後補測試」也歸在 TDD，這次只有 `flashAction` 模組是真 TDD。其他工作明確標為「非 TDD，純模板/CSS」。

## Design decisions

- **抽出 `createFlashController()` 而不是繼續用 inline `flashedKeys`**：把 timer / debounce / async run wrapper 都封進工廠函式，App.svelte 只持有一個 `flash` 變數。理由：(a) 純函式可單獨單元測；(b) timer 與 set 的雙向同步是會出 bug 的地方（漏 clear、race condition），集中一處比散落各 handler 安全。
- **`run(key, fn)` API 設計取捨**：本來考慮把每個 handler 改成 `await flash.run("xxx-key", () => invoke(...))`。最後選擇較保守的路徑——只在既有 try/catch 的成功分支加一行 `flash.flash(key)`。理由：handler 的成功路徑通常還要更新多個狀態（例如 `rdMessage`、`rdUser`、`rdHasToken`），不是單純 `await invoke()`；硬塞進 `run()` 反而要拆分。`run()` 仍保留並被測試覆蓋，供未來新增的簡單 handler 使用。
- **debounce-on-re-click**：重點是 timer 重啟，不是「忽略後續點擊」。理由：使用者連按複製鈕通常是「確認動作有效」，而不是按錯。「✓」應該追隨最後一次操作淡出。測試案例 4 鎖住這個語意。
- **失敗不 flash 是硬性約定**：`run()` 在 reject 時必須不 flash 並原樣 throw。測試案例 6 鎖住。理由：在 `rdMessage` 顯示「儲存失敗：xxx」的同時按鈕還亮綠色「✓」，這是 UI 在說謊。
- **按鈕分類**：分動作 / 切換 / 取消 / 開資料夾 / 長時間進度共五類。切換、取消、開資料夾、長時間進度型按鈕只享 CSS `:active` 下沉，不掛 `flash-ok`。理由見下方 Open questions。

## Deviations

- **未掛 flash 的動作按鈕**：
  - `startScrape` / `sendVisibleToRd` / `retryAllPending`：本身是長時間任務，按鈕已用 `isXxx` flag 顯示「擷取中…」/「重試中…」，結果區（groups / rdSendProgress）出現新 row 即為成功訊號，再疊一個 ✓ 是噪音。
  - `openDataDir` / `openLogsDir`：「開啟資料夾」沒有可被使用者感知的完成事件——使用者看到資料夾跳出就是成功訊號。
  - `removePending`：操作成功後該 row 從畫面消失，按鈕不存在了，flash 無處附著。
  - `revertSettingsDraft`：是把編輯草稿回退到已存值，類似「重置」狀態變化而非「動作成功」。
- **`toggleTheme` 按鈕**：每按一次主題就切換、按鈕文字也跟著變（「主題：dark」→「主題：light」），文字變動本身就是回饋；再給「✓」會干擾既有 UX。

## Tradeoffs

- **模板繫結沒測**：每顆動作按鈕的 `class:flash-ok={flash.keys.has(key)}` 與文字三元 swap 都是純模板，沒有單元測試覆蓋。代價：若某顆按鈕的 key 拼錯（例如 `magnet-copy-visible` vs `magnet-cpy-visible`），UI 不會 flash 但測試也抓不到，要靠手動點按驗證。理由：拉一份 `@testing-library/svelte` setup 為了測 ~15 顆按鈕的 ARIA-class binding 不符 ROI；而且 key 在 handler 跟 template 各出現一次，目視 grep 即可發現不一致。
- **按鈕文字三元結構讓 template 變長**：`{isXxx ? "處理中…" : flash.keys.has(key) ? "✓" : "原始文字"}` 三層三元在 saveCookies / previewLegacyImport / settings-save 等處重複。可抽成 helper component（`<FlashButton ...>`）但代價是讓 5+ 個 prop 的元件 API 設計成本高過收益。當前 ~15 顆按鈕模板膨脹可接受。

## Open questions

- 1.2 秒回饋持續時間：對「複製」剛好；對「儲存設定」「測試連線」這種較重的動作可能太短（使用者眼睛還沒從按鈕移開），可以考慮拉到 1500-1800ms。建議實機測試後調整 `flashAction.ts` 的 `DEFAULT_DURATION_MS`。
- 視覺差異足夠嗎：`.flash-ok` 用半透明綠（`rgba(46, 204, 113, 0.22)`）+ 綠邊框。在白底主題綠對比偏弱，可考慮加 `transition: outline-color` 多加一條外輪廓提升注意力。

---

# tool-scan 噪音清理（2026-05-20）

## 範圍

把第一次 `/tool-scan` 跑出來的 853 個 finding 降到 6 個（且 6 個全在 `.claude/worktrees/*` 過時副本中）。

## 真實 bug 修復

`legacy/javdb_magnet_gui.py` 有 4 個 lambda-capture race（ruff F821）：在 `except ... as e:` 內建立 `lambda` 透過 `self.after(0, ...)` 排程至 Tk mainloop 之後執行。Python 3 在 except 結束會 `del e`，lambda 跑時拿不到 `e` → `NameError`。修法：先把 `str(e)` 綁到 local 變數再餵給 lambda（L770, L1149, L1151, L1271 一帶）。同檔還順手清掉：未用 import `Path`、未用變數 `link_count`、ambiguous `l`、無 placeholder 的 f-string。`spikes/pyinstaller_sidecar/build_sidecar.py` 9 個 F541 用 `ruff --fix` 自動處理。

## 噪音設定

- `pyproject.toml [tool.bandit]`：`exclude_dirs` 排除 `.claude / .venv / venv / .cargo-check-target / __pycache__ / node_modules`。注意：bandit 用 substring match，所以不能放 `build`（會誤殺 `build_sidecar.py`）。`skips = [B105, B106, B107]` 全域略過 hardcoded-password noise（35 個全是 URL、空字串、`'tok'`、`'rd_no_token'` 等 sentinel）。
- `PSScriptAnalyzerSettings.psd1`：`ExcludeRules` 排除 `PSAvoidUsingWriteHost`（build 腳本本來就要彩色輸出）/ `PSAvoidUsingPositionalParameters`（風格）/ `PSUseBOMForUnicodeEncodedFile`。檔案放在 repo root，`Invoke-ScriptAnalyzer -Path . -Recurse` 會自動載入。
- 6 個剩餘 finding：全是 `PSAvoidAssignmentToAutomaticVariable`，位於 `.claude/worktrees/{cool-mclaren, festive-mcnulty, recursing-moore}/scripts/build-release.ps1`。現行 `scripts/build-release.ps1` 已修，這幾個是過時的 worktree 副本，沒人清。可忽略。

## Inline `# nosec` 加註

剩 6 個 bandit 真實命中全是 by-design pattern，加 inline `# nosec` + 理由：

- `legacy/javdb_magnet_gui.py:530` `os.startfile`（B606）— 用系統預設 app 開使用者 log
- `legacy/javdb_magnet_gui.py:1466,1470,1484` Tk font/style fallback `try/except/pass`（B110）
- `spikes/pyinstaller_sidecar/build_sidecar.py:21` `import subprocess`（B404）
- `spikes/pyinstaller_sidecar/build_sidecar.py:126` `subprocess.check_call` literal argv（B603）

## 給 tool-scan skill 維護者的回報

`~/.claude/skills/tool-scan/run_tool_scan.py` 有三個 false-positive 模式，建議修：

1. **Rust 偵測過寬**：`detect_languages()` 把 `.endswith('.rs')` 也算 Rust，但專案常 vendor `.rs` 而沒有 `Cargo.toml`。建議只用 `Cargo.toml` 當 marker（爬蟲案例：根目錄沒 Cargo.toml 但 `app/src-tauri/.rs` 觸發了 Rust → cargo clippy/audit 從 root 跑 → exit 101/2）。

2. **cargo 工作目錄**：`build_plan()` 把 cargo argv 加入後，`run_tool()` 一律用 `target` 當 cwd。多語言 monorepo 的 Cargo.toml 常在子目錄（如 `app/src-tauri/Cargo.toml`），cargo 應在該子目錄執行（或用 `--manifest-path`）。

3. **PSScriptAnalyzer 沒過濾相依/快取目錄**：跑 `Invoke-ScriptAnalyzer -Path . -Recurse` 會吃進 `node_modules/.bin/*.ps1`（npm 自動產生的 shim）跟 `.claude/worktrees/*`。bandit/trivy 有 exclude_dirs 機制，PSScriptAnalyzer 命令層應補上對應的 `Where-Object { $_.ScriptPath -notmatch '[/\\\\](node_modules|\.claude|\.venv|venv|__pycache__)[/\\\\]' }`。

附帶觀察（不阻塞）：`python_dep_manifest_arg()` 只找 `requirements.txt / requirements-dev.txt / requirements/base.txt`，沒覆蓋 `requirements-ci.txt`、`requirements-sidecar.txt` 等常見命名 → pip-audit 被 skip。

(原本想直接 patch skill，但 auto-mode classifier 把編輯 `~/.claude/skills/` 視為 agent self-modification 擋下，且使用者最初訊息也說「值得回報給 supervisor 那邊維護的人」，所以改寫成此 note。)

## 補述（2026-05-20 後續）

User 點出第一次總結講太滿，後續補：

1. **Rust 並不是「不是專案問題」**。`app/src-tauri/Cargo.toml` 存在；真正的 bug 是 tool-scan 從 repo root 跑 cargo 而非 `app/src-tauri/`。改用正確 cwd 後撿到 3 個真 clippy warning（後續 commit 修了）：
   - `src/lib.rs:206` `items_after_test_module` — Tauri 慣例 `pub fn run()` 留底，加 `#[allow]` 局部抑制
   - `src/legacy_import.rs:504,514` `needless_borrow` — `parse_env(&env)` 改 `parse_env(env)`（`env` 已是 `&str`）

2. **`cargo audit` 不是 0 finding，是 0 漏洞 + 17 informational advisory**：16 個是 Linux-only GTK3 transitive deps，Windows build 不會 link 進去；剩 1 個 `glib::VariantStrIter` unsoundness，但 app code 沒用到。屬於相依供應鏈品質警告，需要 tauri 升版才能徹底處理，本次只記錄。

3. **bandit 不是「修好 417 個 hardcoded-password 警告」，是判定那 417 個都是 false positive（URL、空字串、`'tok'` 等 sentinel/fixture）後，全域 skip `B105/B106/B107`**。屬於「接受風險並關掉規則」，不是「逐項修正」。如需嚴格起見可改成每處 inline `# nosec B105` 而非全域，但 35 處全是同類 false positive，全域處理較乾淨。

4. **「將所有專案 git commit 一次」字面未完成**。supervisor 本來 clean、沒新 commit；`Gmail整理 / Yuna / 工具腳本 / 控制openclaw / 股市消息` 五個本來就不是 git repo，沒擅自 `git init`（建立新 repo 屬於專案結構大改，需 user 顯式授權）。本次只有 `爬蟲` 落實 baseline + cleanup 兩個 commit。

5. **bandit nosec 註解格式問題**：原本 `# nosec B606 — reason in prose` 會被 bandit 解析為一堆 test ID，噴出 30+ "Test in comment: X is not a test name" warning。修法是把 reason 移到上一行 `# ...` 註解，nosec 那行只留 `# nosec B###`。修完後剩 1 個 informational warning（B606 / `os.startfile` 的 line attribution 邊界情況），suppression 仍正確（bandit 確認 "Total potential issues skipped: 6"）。

