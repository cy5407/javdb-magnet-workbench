# Pattern: WikiSkill 三層解耦架構與經驗編譯準則 (WikiSkill Architecture & Experience Compilation)

> **文檔定位**：本條目為「經驗蒸餾（Distillation）與知識編譯（Compilation）」之全域範例與標準架構指引。任何 LLM / Agent 閱讀本檔後，即可完全掌握如何將執行經驗轉化為永續資產，以及如何避免歷史失憶、重複踩坑與模型負遷移。

---

## 1. Description（現象與問題描述）

在傳統的 AI Agent 自我演化與提示工程（Prompt Optimization）中，系統普遍存在以下兩大核心瓶頸：
1. **經驗短暫性與歷史失憶（Ephemerality & Amnesia）**：
   - 傳統框架（如 EvoSkill, Trace2Skill, SkillOpt）直接將執行日誌（Traces）消耗於修改技能（Skill）。
   - 當候選技能在驗證集（Validation Set）上評分未提升而被**回滾（Rollback）**時，該輪從失敗軌跡中觀察到的所有寶貴根因（如 API 邊界條件、失敗嘗試）會隨之一併被物理拋棄，導致 Agent 在後續迭代中**反覆嘗試已被證明無效的修改（Oscillation & Deadlock）**。
2. **技能污染與負遷移（Negative Transfer & Prompt Pollution）**：
   - 將所有除錯流水帳、特例代碼與碎片化防禦指令直接塞入 `SKILL.md`，導致 Prompt 膨脹、注意力漂移。
   - 小模型演化出的碎片化指令（如逐行打印、低階字串轉換）遷移給強大模型（如 Gemini Flash）時，會強迫強模型放棄高效端到端向量化代碼，引發高達 **-32.4%** 的災難性負遷移。

---

## 2. Root Cause（根本因果機制）

1. **知識與行為過度耦合（Coupling of Knowledge & Execution）**：
   - 未區分「背景認知圖譜（Knowledge）」與「可執行程序規範（Skill）」。技能必須嚴格門控且追求無副作用，但知識應當單調累積。
2. **缺乏單調持久層（Absence of Monotonic Storage）**：
   - 缺乏一個「即使技能回滾也永不重置」的持久記憶底座（Persistent Wiki），使得失敗經驗無法轉化為**負向約束記憶（Negative Constraints）**。
3. **推論環境與學習環境混淆（Information Leakage during Rollout）**：
   - 若在訓練期允許推論 Agent 查詢 Wiki，Agent 會將 Wiki 當作特例小抄直接作弊，產生的軌跡無法暴露技能本身的缺失，嚴重破壞後續維護者的根因診斷。

---

## 3. Architecture & Core Schema（三層解耦架構實體）

```
+===================================================================================================+
|                                    Three-Layer Knowledge Architecture                              |
+===================================================================================================+
|  [Skills Layer (skills/)]        Active Procedural Skills (SKILL.md, PURPOSE.md)                   |
|                                  ==> 假設性、可逆性 (Reversible, 經 Gating 驗證決定接受或 Rollback)       |
+---------------------------------------------------------------------------------------------------+
|  [Wiki Layer (wiki/)]            Persistent Compounding Knowledge (patterns/, index, logs, impact) |
|                                  ==> 累積性、永不重置 (Monotonic Compounding, Never Reset / Rollback)  |
+---------------------------------------------------------------------------------------------------+
|  [Raw Layer (raw/)]              Execution Traces (raw/traces/<task_id>)                           |
|                                  ==> 原始日誌、不可變 (Immutable, Write-Once)                          |
+===================================================================================================+
```

### 3.1 各層權限與數學性質矩陣

| 層級 (Layer) | 儲存實體 | 讀取權限 (Read) | 寫入/修訂權限 (Write) | 生命週期與數學性質 |
| :--- | :--- | :--- | :--- | :--- |
| **Raw Layer** (`raw/`) | 完整執行日誌（CoT 推理、工具呼叫、環境輸出、最終答案） | Wiki Maintainer, Skill Proposer（按需調閱） | Inference Agent（僅訓練 Rollout 時寫入一次） | **永久不變（Immutable / Write-once）** |
| **Wiki Layer** (`wiki/`) | `patterns/`（根因與修復）、`index.md`（索引）、`skill-impact.md`（審計日誌） | Skill Proposer（提案前必讀） | Wiki Maintainer（RCA 增量修訂）、外層 Harness（審計追加） | **單調累積、永不回滾（Monotonic / Never Reset）** |
| **Skills Layer** (`skills/`) | `SKILL.md`（高密度 SOP）、`PURPOSE.md`（模式映射與起源） | Inference Agent（推論時全量注入）、Skill Proposer | Skill Proposer（提出原子 Proposal） | **假設性、嚴格門控、可回滾（Reversible / Gated）** |

---

## 4. Operational Protocols（標準作業程序與契約規則）

### 4.1 四步蒸餾作業流程（Distillation Protocol）
1. **Step 1: Session 軌跡審計（Trace Audit）**：
   - 提取 Session 中的報錯資訊、失敗改法嘗試（Rejected Proposals）與最終成功的修復代碼。
2. **Step 2: 根因分析（Root-Cause Analysis）**：
   - 嚴格提煉四大要素：`Description` + `Root Cause (WHY)` + `Verbatim Code Evidence` + `Actionable Fix`。
3. **Step 3: 編譯寫入 Wiki Layer（永不回滾）**：
   - 寫入 `wiki/patterns/<name>.md`。
   - 更新 `wiki/index.md`（格式：`- [name](patterns/name.md): PROBLEM + ROOT CAUSE + FIX`）。
   - 寫入 `wiki/skill-impact.md`：記錄所有嘗試。被否決者標記為 `REJECTED` 作為負向避坑記憶。
4. **Step 4: 門控修訂 Skill Layer（Gated Update）**：
   - 若屬高頻通用規則，增量 Patch 至 `skills/<name>/SKILL.md`（保持數十行精簡，嚴禁流水帳）。
   - 執行測試驗證（Gate Command）：通過則接受，未通過立即回滾 `SKILL.md`（Wiki 永久保留）。

---

## 5. Adversarial Audit Case Study（對抗式審查踩坑實錄）

在本次建構中，透過獨立審查者（Claude Code）進行對抗式驗證，成功攔截並修正了以下典型認知偏差：

```
[偏差 1: 過度歸納 Handshake 守衛]
  ❌ 宣稱：「所有業務 RPC 均受 handshake_done 守衛」
  ✅ 源碼真相：16 個命令中僅 6 個受守衛 (fetch_javdb, set_cookies, rd_user, rd_set_token, rd_send_magnet, rd_check_pending)，其餘 10 個無守衛。
  💡 教訓：安全與邊界宣稱必須逐條核對 handler 進入點的 guard 語句，不得憑常理推斷。

[偏差 2: 抹平與過度巢狀的二元混淆]
  ❌ 宣稱：「所有 RPC 均為雙層巢狀結構」
  ✅ 源碼真相：僅 fetch_javdb (result) 與 rd_user (user) 為雙層巢狀；其餘命令（如 rd_send_magnet, resolve_magnet）欄位均平鋪於 _ok 信封內。
  💡 教訓：嚴格區分外層信封 ({"ok": true, "request_id": ...}) 與內層 payload 形狀，避免呼叫端產生 KeyError。

[偏差 3: 演化歷史與版本號矛盾]
  ❌ 瑕疵：PURPOSE.md 標記 v1.0.1 成功升版，但 skill-impact.md 將該 Iteration 記錄為 REJECTED。
  ✅ 修正：被否決的提案嚴禁推進 Skill 版本號，Skill 維持 v1.0.0，審計日誌保留 REJECTED 記錄以發揮負向約束力。
```

---

## 6. Actionable Takeaways for LLMs（其他模型閱讀後的直接行動指引）

1. **不要在 `SKILL.md` 堆砌歷史**：`SKILL.md` 是給推論端看的「執行手冊」，維持極致精煉；所有「為什麼這樣改」、「曾經試過什麼失敗了」一律寫入 `wiki/patterns/` 與 `wiki/skill-impact.md`。
2. **失敗也是最高價值的資產**：當你的修改被使用者拒絕或測試失敗時，不要默默刪除；將該方案與失敗原因寫入 `skill-impact.md`（標註 `REJECTED`），防止下一個 Agent 重蹈覆轍。
3. **查證以程式碼為唯一真實**：在提煉 Pattern 時，程式碼片段必須逐字引用定義處，嚴禁由外部 HTTP 狀態碼或註解臆測錯誤碼與邊界值。
