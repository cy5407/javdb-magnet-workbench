# javdb-magnet-workbench 專案指引

## 測試與驗收 Gate

- Python：`.venv/bin/python -m pytest tests/ -q`
- 前端：`cd app && npx vitest run`
- 型別：`cd app && npm run check`（svelte-check，0 errors 0 warnings 才算過）
- Rust（Linux lib gate）：在 `app/src-tauri` 執行
  `TAURI_CONFIG='{"bundle":{"externalBin":[]}}' cargo test --lib`。覆寫只讓 lib
  unit tests 不受 Tauri 打包期的 externalBin 存在檢查阻擋；正式 build 仍必須提供
  Linux sidecar（見 [`docs/platform/linux-support.md`](docs/platform/linux-support.md) §2）。
  keyring 測試需要可用的使用者 D-Bus／Secret Service。2026-08-01 實測
  **81 passed / 0 failed**。
- 驗收以機器可比對方式核對 baseline：既有測試案例不得刪除或弱化；刻意的
  行為契約變更允許改測試，但須說明舊期待、Red 原因與新期待。

### 目前 baseline（2026-08-01）

| Gate | 結果 |
|---|---|
| `pytest tests/ -q` | 426 passed, 6 subtests |
| `npx vitest run` | 9 files / 255 tests |
| `npm run check` | 189 files, 0 errors 0 warnings |
| Linux `TAURI_CONFIG='{"bundle":{"externalBin":[]}}' cargo test --lib` | 81 passed（需可用 D-Bus keyring） |

## 契約文件同步

`docs/architecture/contracts/`（六份：`rust-backend` / `frontend-lib` /
`app-svelte` / `sidecar-runtime` / `sidecar` / `python-legacy`）與
`docs/architecture/function-contracts.md` 記載跨層契約。行為變更必須同步這些
文件：除以 `rg` 掃被移除符號外，還要逐份正面核對新契約已被記載（新增的行為靠
搜尋舊符號找不到）。

**歷史存檔不回頭改**：`docs/code-simplification-plan-*.md`、
`docs/security-audit-*.md`、`docs/sessions/`、`docs/superpowers/specs/`、
`docs/specs/*`，以及 `implementation-notes.md`／`PROGRESS.md` 這兩份執行紀錄。
它們記錄的是「當時決定了什麼」，改寫等於竄改紀錄；只在檔頭標註狀態並指向
現行來源。

**任務規格檔用完即刪**：純粹描述「要實作什麼」的任務檔（如已移除的 `Task.md`／
`docs/Task.md`）在驗收通過後刪除，只留執行紀錄。刪除前必須逐條驗證確實完成，
並把只存在於該檔的決策理由（特別是「刻意不做某事」的理由）先移進對應的契約
文件或程式碼註解——否則刪的不只是清單，是知識。

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

- **委派門檻：規格化槓桿比 ≥ 3**（預期實作行數 ÷ 規格行數，快速篩選器而非
  定律）。同一模式套用到 N 處、批量補測試（10–37×）適合委派；數個各自獨立的
  邏輯缺陷修正（實測 0.7×）應由 Claude/Codex 自己做。真正判斷式：
  `規格時間 + 驗收活躍時間 + 預期修正時間 < 自行完成時間`。
- **措辭紀律**：Agy 執行階段的速度體感尚未量化（缺同題對照）；端到端本次未
  呈現已證實的速度優勢；成本優勢來自單價但 token 為 unavailable、未量化。
  不得用 LOC 推論當速度證據。
- **並行**：正式方案是 worktree 隔離 + checkpoint pipeline（含 Admission／
  Final 兩層 gate），不是「檔案不重疊就並行」——同工作樹並行會讓驗收結果不可
  歸屬。完整規則見全域 `~/.claude/CLAUDE.md`。
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
  完整定義見全域 `~/.claude/CLAUDE.md` 與 `~/.codex/AGENTS.md`。

### 鐵律

1. 審查者 ≠ 作者，永遠。
2. 計畫詳細度與交接距離成正比：自己寫 → 粗粒度；交第三方 → 完整規格。
3. 測試也是被審對象，不是驗收的終點。

## Git 規則

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
  agy 1.1.22）：`爬蟲/GEMINI.md`、`AGENTS.md`、`.agents/rules/`、`.agent/rules/`、
  `.agents/skills/` 在 `agy -p` 下**完全不會被載入**——CLI 不做任何工作區客製化探索，
  只讀 `~/.gemini/config/rules/*.md`（需 `trigger: always_on` frontmatter）與
  `~/.gemini/GEMINI.md`。Antigravity **IDE** 則會載入開啟層的上述路徑。
  因此交給 Agy 的專案級約束沒有技術強制力，必須逐次寫進 prompt，或改用 hook。
  完整實測見 `程式語言/antigravity-rules-loading-findings.md`。
- 未經使用者要求不 commit、不 push。

## Wiki 知識沉澱與經驗蒸餾規範 (WikiSkill Distillation)

> **核心原理（WikiSkill 論文 arXiv:2608.27454）**：將 Agent 執行經驗編譯為結構化、永不回滾的持久知識庫（Wiki Layer），與可逆的程序性技能（Skills Layer）解耦共演化。

### 開工前讀取（強制）
- 每次開始實作、除錯、架構或跨層契約工作前，先讀 `.agents/wiki/index.md`。
- 索引命中任務主題時，先讀對應 pattern；其中的 `Actionable Fix` 是動手前約束，原始碼與權威契約仍為最終真實來源。
- 提交前執行 `.venv/Scripts/python.exe scripts/verify_wiki_citations.py`；引用失真時，先修 Wiki 或程式碼，不能略過校驗。

### 1. 語意觸發與自動蒸餾
- 當使用者對話提及**「蒸餾」**、**「提煉」**、**「Wiki」**、**「沉澱知識」**、**「記錄踩坑經驗」**，或當 Session 完成重大除錯/架構修正時：
- 必須**主動判斷語意為「將 Session 內的錯誤原因、失敗嘗試、成功策略編譯為持久 Wiki 知識」**，依據 `wiki-distiller` Skill 執行結構化沉澱。

### 2. 專案 Wiki 維護規範
- **模式沉澱（`.agents/wiki/patterns/<name>.md`）**：必須包含 Description、Root Cause (WHY)、Verbatim Code 證據與 Actionable Fix。
- **目錄索引（`.agents/wiki/index.md`）**：格式嚴格為 `- [name](patterns/name.md): PROBLEM + ROOT CAUSE + FIX`（一至兩句話）。
- **審計與負向約束（`.agents/wiki/skill-impact.md`）**：
  - 記錄提案、驗證命令、結果與成敗狀態（`ACCEPTED` / `REJECTED`）。**永不回滾**。
  - 被否決的方案作為負向記憶（Negative Constraints），防止後續 Agent 重複嘗試已失敗路徑。

### 3. 可執行技能（`.agents/skills/`）更新守則
- **保持精簡**：`SKILL.md` 僅保留 SOP、關鍵常數與檢查清單（數十行內），嚴禁塞入流水帳。
- **測試門控**：修訂 `SKILL.md` 必須跑通過 Gate 測試（`pytest tests/ -q`），未通過則回滾 Skill（Wiki 保持累積）。
