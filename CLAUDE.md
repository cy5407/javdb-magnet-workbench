# javdb-magnet-workbench 專案指引

## 測試與驗收 Gate

- Python：`.venv/bin/python -m pytest tests/ -q`
- 前端：`cd app && npx vitest run`
- 型別：`cd app && npm run check`（svelte-check，0 errors 0 warnings 才算過）
- Rust：`cd app/src-tauri && cargo test --lib` —— **目前本機編不過**（baseline
  即失敗：缺 Linux sidecar binary，且 `secret-service` 4.0.0 未啟用 runtime
  feature，在 rustc 1.97.1 下編譯失敗）。修好前 Rust 端變更以人工細審代替，
  並在回報中註明此 gate 被跳過。
- 驗收以機器可比對方式核對 baseline：既有測試案例不得刪除或弱化；刻意的
  行為契約變更允許改測試，但須說明舊期待、Red 原因與新期待。

## 契約文件同步

`docs/architecture/contracts/`（五份）與 `docs/architecture/function-contracts.md`
記載跨層契約。行為變更必須同步這些文件：除以 `rg` 掃被移除符號外，還要
逐份正面核對新契約已被記載（新增的行為靠搜尋舊符號找不到）。
`docs/code-simplification-plan-*.md` 等日期戳記檔案是歷史存檔，不回頭改。

## 多代理工作流

核心原則：審查強度跟著「錯誤會在哪一層被自動抓住」走。

### 第 0 步：分流

| 類型 | 特徵 | 流程 |
|---|---|---|
| T1 小修 | 單檔、意圖明確、測試現成 | 直接做，跑最窄測試，不開審查 |
| T2 標準任務 | 跨模組、觸碰契約邊界 | 四階段（下述） |
| T3 批量雜活 | 可完整規格化、驗收可機器判定 | 規格 → Agy 執行 → 機器驗收 |

### T2 四階段

1. **探索式審查（1 輪即止）**：subagents 掃目標區域 + Codex 全 repo 對抗式
   審查。指令必須含「檢查變更觸碰的每條契約的另一端」（Rust↔Python↔TS）。
   產出 v2 粒度計畫即停。若第 2 輪仍發現設計級錯誤 → 重切範圍，不磨紙面。
2. **實作（Claude 或 Codex 一方）**：Red 測試先行、邊寫邊跑最窄測試。範圍外
   發現只記錄不修。
3. **獨立 diff 審查（非作者一方，1 輪）**：(a) 逐一驗證 diff 觸碰契約的兩端；
   (b) 對抗式檢查測試本身——測試是否複製了實作的假設？換一種方式建立
   前置狀態還過嗎？作者永不審自己的 diff。
4. **驗收與收尾（Claude）**：完整 gate + baseline 比對 + 文件同步 + commit。

### T3（Agy 專用）

- 規格必須含機器可判定的驗收（一條命令、一個預期輸出）。
- **Agy 不做完整 gate 與最終報告**：它只在實作中跑最窄測試（Red→Green
  回饋迴路），完成即宣告 + 5 行摘要（改檔清單 + done/skipped）。完整
  gate、baseline 比對與最終驗收全歸 Claude/Codex——Agy 的 gate 數字一律
  不採信，親自重跑。
- **切片原則**：任務切成 5 分鐘級的精確片段（函式級修法描述），每片完成
  即由委派方檢查點驗收，`--print-timeout` 用 10m；不發 30 分鐘大包。
- 用既有 allow 清單跑，**永不帶 `--dangerously-skip-permissions`**。
- 給 Agy 的 prompt 一律用 `Cwd=` 指定工作目錄，命令不得寫 `cd <dir> && ...`
  形式（會被權限 prefix 比對整場拒絕）。
- 驗收＝跑驗收命令 + 抽樣讀 diff + 範圍核對，不逐行讀。
- T2 等級的跨模組任務不交給 Agy（交接保真度損耗 + 驗收成本不減）。

### 鐵律

1. 審查者 ≠ 作者，永遠。
2. 計畫詳細度與交接距離成正比：自己寫 → 粗粒度；交第三方 → 完整規格。
3. 測試也是被審對象，不是驗收的終點。

## Git 規則

- `git add`／`commit`／`push` 只由 Claude／Codex 執行；Agy 由全域 hooks
  （`~/.gemini/config/hooks/pre_tool_guard.py`）硬性阻擋 git 變更與整個 gh CLI。
- 未經使用者要求不 commit、不 push。
