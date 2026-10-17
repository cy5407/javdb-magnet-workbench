---
name: wiki-distiller
description: 將除錯與實作經驗編譯為可驗證、可檢索的持久 Wiki 知識。使用者提到蒸餾、提煉、Wiki、沉澱知識或記錄踩坑時使用；也用在修好一個值得留下根因的跨層缺陷、或某個方案被否決之後。
---

# Wiki Distiller

## Trigger

值得沉澱的是下一個 session 會再踩到的東西：非顯而易見的根因、失敗過的做法、被否決的方案。例行修正不需要。

## Protocol

1. 稽核本次軌跡，辨識成功策略、失敗嘗試與測試證據。
2. 在 `.agents/wiki/patterns/<name>.md` 寫入 Description、Root Cause、逐字原始碼證據與 Actionable Fix。
3. 更新 `.agents/wiki/index.md`，並在 `.agents/wiki/skill-impact.md` 記錄 `ACCEPTED` 或 `REJECTED`；Wiki 不因 Skill 回滾而刪除。
4. 只有高頻、可執行的規則才進入 Skill，保持精簡；變更 Skill 後跑 `.venv/Scripts/python.exe -m pytest tests/ -q`，失敗則僅回滾 Skill。

## Integrity Gate

- 原始碼是事實來源；凡標註 Verbatim 的片段必須逐字存在。
- 修改被引用的原始碼或 pattern 後，執行 `.venv/Scripts/python.exe scripts/verify_wiki_citations.py`。
