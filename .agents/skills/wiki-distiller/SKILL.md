---
name: wiki-distiller
description: 將除錯、實作與架構決策經驗編譯為可驗證、可檢索的持久 Wiki 知識。
---

# Wiki Distiller

## Trigger

使用者要求 `/wiki`、沉澱或提煉已發生的經驗時使用。只有調查或一般修正時，不因提到 Wiki 就擴張成寫入任務。

## Protocol

1. **稽核軌跡**：回顧對話或任務歷程，辨識關鍵成功策略、失敗嘗試（逾時、報錯、無效路徑）與測試終端證據。
2. **沉澱 Pattern**：在 `wiki/patterns/<name>.md` 寫入：
   - 模式名稱與簡述（Description）
   - 問題根因（Root Cause - WHY）
   - 逐字原始碼或終端命令證據（Verbatim Source / Command Proof）
   - 處置與防範對策（Actionable Fix & Prevention）
   - 適用條件、反例、未驗證範圍；來源 repo/commit、runner、shell 與去識別化輸入輸出。無來源不能標 VERIFIED。
3. **維護索引與衝擊日誌**：
   - 在 `wiki/index.md` 新增單行索引（格式：`- [name](patterns/name.md): PROBLEM + ROOT CAUSE + FIX`）。
   - Wiki 採收與資產晉升分開：未評測標 `DRAFT` / `NOT_VERIFIED`，不可直接標 `ACCEPTED`。晉升由評測工具寫入結果與雜湊；拒絕與負向約束同樣保留。
4. **不可變原則（Anti-Amnesia）**：
   - 保留歷史與被否決原因，但可以更正現行結論，舊結論標 `SUPERSEDED` 並連到替代證據；不可讓已推翻內容繼續充當有效規則。
   - 只有高頻、可執行的通用 SOP 才提煉為 Skill。

## Integrity Gate

- 原始碼與命令輸出是事實來源；凡標註 Verbatim 的片段必須逐字真實存在。
- 若專案內建 `verify_wiki_citations.py`，完成編輯後執行驗證引用完整性。
- 零引用、零案例、缺少依賴都不是通過。機械引用驗證只證明檔案／範圍／片段，不證明根因。

## 提煉出口

- 需要情境判斷的 SOP → Skill；确定性的工具事件攔截 → runtime Hook；批次引用或測試 → CLI/CI gate，不硬塞進每次工具呼叫。
- 在中央庫使用 `scripts/promote-asset.mjs prepare` 建候選，補證據、適用邊界、負向約束，再做 baseline/candidate 同題比較。工具不存在時保留提案，不能宣稱已晉升。
- Skill 須測觸發／不觸發與未用於修正的 held-out 題；Hook 須測 allow／deny／畸形輸入、逾時、設定錯誤與 runner 載入。自測全綠不等於實際 host 有執行。
- 評測規格先獨立審查，再顯式 evaluate/promote；檢查腳本不能自證 SOP 有效。不得因收集授權自行部署到全域或其他專案。
