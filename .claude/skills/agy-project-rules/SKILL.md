---
name: agy-project-rules
description: 本專案（javdb-magnet-workbench）委派 Agy 執行 T3 任務時的完整規則與實測結論——委派門檻判斷式、措辭紀律、worktree 並行、規格驗收、切片、Cwd 寫法、耗時三區間量測，以及 Agy 權限層／hook 層／規則檔載入的實測限制。呼叫 agy 或撰寫給 Agy 的 prompt 前載入，並同時載入 agy-delegation skill。
---

# 本專案的 Agy 委派規則

從 CLAUDE.md 搬出（2026-10-16），內容原文保留。CLAUDE.md 仍保留門檻、T2 不委派、
遞迴刪除禁令與兩條安全結論；這裡是委派時才需要的細節。

## T3（Agy 專用）

- **委派門檻：規格化槓桿比 ≥ 3**（預期實作行數 ÷ 規格行數，快速篩選器而非
  定律）。同一模式套用到 N 處、批量補測試（10–37×）適合委派；數個各自獨立的
  邏輯缺陷修正（實測 0.7×）應由 Claude/Codex 自己做。真正判斷式：
  `規格時間 + 驗收活躍時間 + 預期修正時間 < 自行完成時間`。
- **措辭紀律**：Agy 執行階段的速度體感尚未量化（缺同題對照）；端到端本次未
  呈現已證實的速度優勢；成本優勢來自單價但 token 為 unavailable、未量化。
  不得用 LOC 推論當速度證據。
- **並行**：正式方案是 worktree 隔離 + checkpoint pipeline（含 Admission／
  Final 兩層 gate），不是「檔案不重疊就並行」——同工作樹並行會讓驗收結果不可
  歸屬。完整規則見 `agy-delegation` skill。
- 規格必須含機器可判定的驗收（一條命令、一個預期輸出）。
- **Agy 不做完整 gate 與最終報告**：它只在實作中跑最窄測試（Red→Green
  回饋迴路），完成即宣告 + 5 行摘要（改檔清單 + done/skipped）。完整
  gate、baseline 比對與最終驗收全歸 Claude/Codex——Agy 的 gate 數字一律
  不採信，親自重跑。
- **切片原則**：任務切成 5 分鐘級的精確片段（函式級修法描述），每片完成
  即由委派方檢查點驗收，`--print-timeout` 用 10m；不發 30 分鐘大包。
- **權限與危險指令防護**：允許使用 `--dangerously-skip-permissions`，但**嚴禁發出遞迴刪除指令**（如 `rm -rf`, `Remove-Item -Recurse`, `rmdir /s`, `shutil.rmtree` 等）；檔案清理必須**單檔逐一刪除**。全域 Hooks（`~/.gemini/config/hooks/pre_tool_guard.py`）會硬性阻擋任何遞迴刪除嘗試。
- 給 Agy 的 prompt 一律用 `Cwd=` 指定工作目錄，命令不得寫 `cd <dir> && ...`
  形式（會被權限 prefix 比對整場拒絕）。
- 驗收＝跑驗收命令 + 抽樣讀 diff + 範圍核對，不逐行讀。
- T2 等級的跨模組任務不交給 Agy（交接保真度損耗 + 驗收成本不減）。
- **耗時量測三區間**（Claude 與 Codex 同標準）：A 執行方內部
  （`agy_metrics_report.py` 的 `elapsed_seconds`）、B 呼叫 wall-clock
  （output 檔 `stat -c '%W %Y'`）、C 端到端委派成本（`events.jsonl` 本方
  provider 的 `PreToolUse`→`Stop`，`monotonic_ns` 相減）。三個都要報。
  禁用被委派方自報的分鐘級標記；比較速度必須附 diff 規模；品質指標
  （修正輪數、摘要交付率、被拒後行為、測試路徑）才是主要依據。
  完整定義見 `agy-delegation` skill。

## Agy 的 Git 阻擋與規則檔載入（實測）

- `git add`／`commit`／`push` 只由 Claude／Codex 執行。Agy 的阻擋分兩層，兩層
  的涵蓋範圍不同，不要混談：
  - **permissions 層**（`~/.gemini/antigravity-cli/settings.json` 的 `deny`）：
    擋 `git push`／`commit`／`reset`／`clean`／`checkout`／`restore`／
    `worktree remove`、`rm`／`del`／`rmdir`／`Remove-Item`、`sudo`。
    (a) `trustedWorkspaces` 不含本專案，但 2026-08-30 實測顯示**在本專案執行
    `agy -p` 時該 deny 清單仍被完整載入**（`cli.log` 的
    `cli_setting_manager.go:92] CLI settings initialized: permissions=...Deny:[...]`）；
    「被載入」不等於「會擋住」，實際攔截行為未測。
    (b) `--dangerously-skip-permissions` 是否會整層跳過**仍未實測**——若會，這層
    等於不存在。
  - **hook 層**（`~/.gemini/config/hooks/pre_tool_guard.py`）：只攔遞迴刪除，
    fail-closed。`gh` CLI **兩層都沒有涵蓋**，純屬 prompt 級約束。
  在 (b) 未實測確認之前，不要把 permissions 層當成 `--dangerously-skip-permissions`
  之下仍然成立的技術護欄。
- **本專案目錄下的規則檔對 `agy` CLI 一律無效**（2026-08-30 指紋探針實測，
  agy 1.1.22）：`javdb-magnet-workbench/GEMINI.md`、`AGENTS.md`、`.agents/rules/`、`.agent/rules/`、
  `.agents/skills/` 在 `agy -p` 下**完全不會被載入**——CLI 不做任何工作區客製化探索，
  只讀 `~/.gemini/config/rules/*.md`（需 `trigger: always_on` frontmatter）與
  `~/.gemini/GEMINI.md`。Antigravity **IDE** 則會載入開啟層的上述路徑。
  因此交給 Agy 的專案級約束沒有技術強制力，必須逐次寫進 prompt，或改用 hook。
  完整實測見 `程式語言/antigravity-rules-loading-findings.md`。
