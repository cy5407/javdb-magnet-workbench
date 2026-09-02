---
name: wiki-distiller
description: 知識蒸餾與經驗編譯 SOP。當對話提及「蒸餾」、「提煉」、「Wiki」、「沉澱知識」、「記錄踩坑」或需總結 Session 經驗時，將執行軌跡中的錯誤根因、失敗反例與成功策略逐步編譯為持久化 Wiki 知識庫與精簡 Skill 模組。
---

# Wiki Distiller & Knowledge Compilation Skill

> **理論基礎**：依據 Google Research 論文《WikiSkill: Compiling Agent Experience into Persistent Knowledge for Skill Evolution》（arXiv:2608.27454）。
> Agent 的執行經驗（Traces）不應作為一次性消耗品，必須編譯為結構化、單調累積、永不回滾的持久知識庫（Wiki Layer），以實現認知複利與長效避坑。

---

## 1. When to Apply（語意觸發條件）

當對話中符合以下任一條件時，**必須主動觸發本技能的工作流**：
1. **關鍵字語意匹配**：使用者指令中包含「**蒸餾**」、「**提煉**」、「**Wiki**」、「**沉澱知識**」、「**記錄踩坑經驗**」、「**總結本次經驗**」等詞彙。
2. **重大除錯與變更結束**：Session 經歷了複雜除錯、跨層修復、架構重構或解決了難纏的邊界 Bug，需要將經驗資產化。
3. **策略被否決/失敗反思**：某個方案在測試或審查中被證實無效/退化，需要沉澱為**負向約束記憶（Negative Constraints）**以防未來重複踩坑。

---

## 2. When NOT to Apply
- 單純的文件格式排版、錯字微調或無新增領域知識的瑣碎單行修改。
- 專案架構圖渲染（應使用 `archify` Skill）。

---

## 3. 三層知識架構原則 (Three-Layer Architecture)

```
[Raw Layer (不可變)]       執行軌跡、日誌、指令輸出、報錯訊息 (Write-once)
       │
       ▼ (Wiki Maintainer 根因提煉)
[Wiki Layer (持久累積)]     patterns/, index.md, skill-impact.md (Monotonic, Never Rollback)
       │
       ▼ (Skill Proposer 精簡編譯)
[Skills Layer (門控可逆)]   skills/<name>/SKILL.md (Concise, High-Density, Gated by Tests)
```

---

## 4. 四步蒸餾作業程序 (Step-by-Step Distillation Protocol)

當觸發蒸餾動作時，依序執行以下 4 個步驟：

### Step 1: Session 軌跡審計 (Trace Audit)
- 完整回溯當前 Session 內的執行歷程：
  - 執行的終端命令、測試失敗輸出（Traceback / AssertErrors）。
  - 曾嘗試過但失敗的修改（Failed / Rejected Proposals）。
  - 最終成功修復的程式碼變更與關鍵突破點。

### Step 2: 根因分析與模式提煉 (Root-Cause Analysis, RCA)
- 區分「表面症狀（What Happened）」與「底層機制（Why It Happened）」。
- 提煉標準 Pattern 四大核心要素：
  1. `Description`：問題情境與具體表現。
  2. `Root Cause`：根本原因（深入通訊協定、型別系統、競爭條件或外部 API 邊界）。
  3. `Verbatim Code Evidence`：引用精確源碼定義與調用處（必須為實際存在的程式碼，嚴禁剪裁或臆測）。
  4. `Actionable Fix`：具備精確語法的標準修正步驟或防錯模式。

### Step 3: 編譯寫入 Wiki Layer (Compounding Knowledge Base)
1. **建立/更新模式檔案**：寫入 `.agents/wiki/patterns/<pattern_name>.md`。
2. **同步更新目錄索引**：更新 `.agents/wiki/index.md`，每筆格式嚴格限制為：
   `- [pattern-name](patterns/pattern-name.md): PROBLEM + ROOT CAUSE + FIX（一至兩句話）。`
3. **記錄審計與負向約束**：寫入 `.agents/wiki/skill-impact.md`：
   - 記錄提案名稱、變更目標、驗證命令與結果。
   - **若為被拒絕/失敗的改法，明確記錄為 `REJECTED`**：失敗記錄具有不可替代的反向約束價值，防止未來的 Agent 重複提出已被證明不可行的方案（Anti-Amnesia）。
   - **Wiki 永不回滾**：即使後續技能更新被放棄，Wiki 記錄永久保留。

### Step 4: 評估與門控修訂 Skill Layer (Gated Skill Update)
1. **評估是否需更新 Skill**：判斷新提煉的經驗是否屬於高頻、通用的可執行 SOP。
2. **保持精簡**：若需修改 `skills/<name>/SKILL.md`，僅以增量 Patch 形式加入高密度規則或檢查清單，**全檔長度維持在數十行內，嚴禁塞入長篇除錯歷史**。
3. **驗證門禁（Validation Gate）**：
   - 執行專案測試命令（如 `pytest tests/ -q`）。
   - **通過** $\to$ 採納 Skill 更新。
   - **失敗** $\to$ 立即回滾 `SKILL.md`（Wiki 維持單調累積不回滾），並在 `skill-impact.md` 記錄該次 Rollback 原因。

---

## 5. 輸出規範與檢核清單

每次完成蒸餾動作後，向使用者呈報結構化交付摘要：
- [ ] **新增/更新之 Wiki Patterns**（包含問題、根因與修復方案）
- [ ] **索引目錄（`wiki/index.md`）同步狀態**
- [ ] **審計日誌（`wiki/skill-impact.md`）記錄條目**（含 Accepted / Rejected 狀態）
- [ ] **可執行技能（`SKILL.md`）是否需要 Patch 及驗證測試結果**
