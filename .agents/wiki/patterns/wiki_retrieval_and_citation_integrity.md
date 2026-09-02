# Pattern: Wiki Retrieval Gate & Citation Integrity

## 1. Description

把除錯經驗寫入 Wiki 卻沒有在下一次工作前載入時，知識只是檔案，不會改變 Agent 行為；同樣地，標示為 Verbatim 的片段在重構後若無校驗會悄悄失真，反而引導後續實作走錯。

## 2. Root Cause

1. **只有寫入、沒有讀取**：pattern 和 audit log 不會自行進入 Agent context，依靠人工想起才查閱等同沒有可重複的行為約束。
2. **散文無漂移訊號**：程式碼行號或函式簽名改變時，Markdown 不會報錯；作者可能將記憶中的版本錯標為逐字引用。

## 3. Evidence & Ground Truth Code

- 讀取門位於 `AGENTS.md:3-7`：
  ```md
  Read `CLAUDE.md` for the project's full engineering rules.

  Before implementing, debugging, or changing an architecture or cross-layer contract, read `.agents/wiki/index.md`. When an entry matches the task, read its linked pattern before editing; treat its actionable fix as a pre-edit constraint, while live source code and `docs/architecture/contracts/` remain authoritative.

  After changing source referenced by a Wiki pattern, run `.venv/Scripts/python.exe scripts/verify_wiki_citations.py` and correct any drift before finishing.
  ```
- citation checker 的引用語法位於 `scripts/verify_wiki_citations.py:30-35`：
  ```python
  # `path:12` 或 `path:12-34`；副檔名白名單避免把 `rd_send_magnet:pending` 這類
  # 非路徑字串誤判為引用。
  CITATION_RE = re.compile(
      r"`([\w./\\-]+\.(?:py|rs|ts|tsx|svelte|md|toml|json)):(\d+)(?:-(\d+))?`"
  )
  FENCE_RE = re.compile(r"^\s*```")
  ```

## 4. Actionable Fix

1. 在任何實作、除錯、架構或跨層契約工作前讀 `wiki/index.md`；命中主題才展開完整 pattern，避免把所有歷史塞進 context。
2. 用 SessionStart hook 與各 Agent 的專案指引注入索引；將可立即執行的一行規則上移至 Skill 或 Agent 指引，完整推導保留在 Wiki。
3. 修改被 Wiki 引用的程式碼或 pattern 後，執行 `scripts/verify_wiki_citations.py`；它失敗時先修復證據，不得以舊散文覆蓋現場程式碼。
4. 可機器判定的約束寫成 contract test；文件是決策與根因的索引，測試是持續有效性的門禁。
