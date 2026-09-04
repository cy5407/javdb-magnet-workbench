# Pattern: Central Catalog & Preflight Deployment Gates (跨專案資產總庫與三方部署閘門)

## 1. Description & Context

在多個專案與多種 AI Agent 工具（Codex, Claude Code, Gemini CLI）協同開發時，工程準則、防禦 Rules 與可執行 Skills 面臨以下維護挑戰：
1. **專案孤島與知識分岔（Siloing & Divergence）**：各專案手動複製貼上規範文件，導致同一套 SOP 出現多個版本。專案端在實戰中獲得的修復（如連線池標頭同步、測試 Token 白名單）無法回流，新專案亦無法享用。
2. **工具目錄契約歧異**：Codex 與 Gemini CLI 主要讀取 `.agents/`，而 Claude Code 讀取 `.claude/`。手動維護雙重目錄極易遺漏同步（如 `.claude/skills/javdb-scraper/SKILL.md` 落後於 `.agents/skills/`）。
3. **盲目覆寫的滅頂風險**：傳統的兩方檔案比對（中央庫 vs 專案端）僅能回答「內容是否一致」，無法判斷「究竟是誰做的修改」。若中央庫執行無保護覆寫，專案端未回寫的現場修改將在瞬間遭到物理性滅失。

## 2. Root Cause

1. **缺乏中央宣告式裝配機制**：未將跨專案可重用資產收斂為中央目錄（`catalog/`），且缺乏依專案需求客製的宣告式清單（`profiles/*.json`）。
2. **兩方比對的資訊不對稱**：中央庫前進時應當安全覆寫，專案端局部修改時覆寫則會毀滅資料；兩者處置完全相反，但雙方 diff 無法區分兩者。
3. **非強制性注意力的不可靠性**：單靠文字 Prompt 告誡模型不得進行破壞性操作（如遞迴刪除或宣稱零風險），無法保證 100% 遵守，必須有執行期硬性護欄（Hooks）。

## 3. Verbatim Code Evidence

### 3.1 執行期命令硬性阻擋護欄
- 位於 `.agent-hooks/recursive-delete-guard.mjs:33-39`：
  ```javascript
  export function blockedReason(command) {
    for (const [label, pattern] of blockedPatterns) {
      if (pattern.test(command)) {
        return `Blocked ${label}. Review and run the command manually if intentional.`;
      }
    }
    return null;
  }
  ```

### 3.2 零風險宣告禁令與標準隔離 SOP
- 位於 `.agents/rules/no-false-zero-risk.md:8-15`：
  ```markdown
  ## 1. 零風險宣告禁令
  - 嚴禁對任何會抹除工作區的指令宣稱「零風險」。
  - 涉及重設、強制還原或清理工作區時，必須先執行狀態檢查。若有未提交修改或未追蹤檔案，任何未保護的操作皆為「高風險／破壞性」操作。

  ## 2. 標準防破壞隔離 SOP (Stash-Before-Reset Invariant)
  - 凡涉及分支切換、歷史覆蓋或清理工作區，唯一合法的保全指令是：
    git stash push -u -m "pre-op-backup: [description]"
  - 必須帶 -u（--include-untracked），否則未追蹤檔案仍會被毀滅。
  ```

### 3.3 禁止遞迴刪除核心規則
- 位於 `.agents/rules/prohibit-recursive-rm.md:8-10`：
  ```markdown
  ## 核心規則
  禁止遞迴刪除，允許單檔逐一刪除。
  ```

## 4. Actionable Fix & Constraints

1. **單一事實來源（Single Source of Truth）**：
   - 所有跨專案共用資產以 `my-codex-guides/catalog/` 為中央基準；專案端依 `profiles/<name>.json` 動態裝配，`.claude/` 鏡像一律由腳本自動生成，禁止手動分流維護。
2. **三方比對部署閘門（3-Way Preflight Gate）**：
   - 部署至專案端前，必須透過 `scripts/preflight-deploy.mjs` 比對「Catalog 期望樹」、「專案端現況」與「上次部署基準線（`.deploy-state/<profile>.json`）」。
   - **負向約束**：凡出現 `local-edit`（專案端有未回寫修改）、`conflict`（兩端皆修改）、`untracked`（無基準線且相異）時，必須 Fail-Closed 立即中止，嚴禁盲目覆寫。
3. **採收回饋義務（Harvest Invariant）**：
   - 當專案端有新的模式修訂或技巧沉澱時，在重新部署前必須先以 `node scripts/harvest.mjs --bundle <profile>` 採收回中央庫。
4. **部署基準線更新門禁**：
   - 部署完成後，必須立即執行 `node scripts/preflight-deploy.mjs --profile <profile> --record` 登記當前快照雜湊，確保後續比對基底健全。
5. **程式化硬性攔截（Runtime Guard）**：
   - 針對破壞性操作（遞迴刪除、Wiki 引用偽造），必須在專案根目錄部署 `.agent-hooks/`，以 Fail-closed 機制在執行前直接 deny，不依賴模型的注意力自律。
