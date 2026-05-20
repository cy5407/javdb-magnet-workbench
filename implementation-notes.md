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
