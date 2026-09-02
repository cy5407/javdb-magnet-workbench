# Skill Impact Tracker & Audit Log

本文件為技能演化審計日誌，單調累積記錄所有技能提案（Proposals）、變更依據、驗證結果與接受/拒絕狀態（永不回滾）。
專案跨層契約之單一真實來源為 `docs/architecture/contracts/` 與 `docs/architecture/function-contracts.md`。

---

## Evolution History

### Iteration 0: Baseline Skill Setup
- **Target Skill**: `javdb-scraper`
- **Action**: `create`
- **Proposal Rationale**: 建立基礎爬取與 RD 加速呼叫規範，封裝三層式架構資料流（Svelte $\to$ Tauri Rust $\to$ Python Sidecar）。
- **Validation Command**: `.venv/Scripts/python.exe -m pytest tests/ -q` (422 passed, 6 subtests)
- **Validation Outcome**: `ACCEPTED`
- **Summary**: 確立了 `fetch_javdb` 巢狀回傳解析、Handle ID 安全隔離機制、與 RD 429 退避約束。

### Iteration 1: Reject Flattened RPC Refactor Attempt
- **Target Skill**: `javdb-scraper`
- **Action**: `patch`
- **Proposal Rationale**: 嘗試將 RPC 回傳扁平化為單層字典以簡化前端代碼。
- **Validation Outcome**: `REJECTED` (Skill 不升版，維持 v1.0.0)
- **Rejection Reason**: 破壞了 `sidecar.py` 與 `commands.rs` 的跨層型別契約（`fetch_javdb` 必須在 `result` 下包含 `engine`、`code`、`magnets` 等）。被拒絕的變更已記錄於 `patterns/rpc_response_shape_mismatch.md`，未來禁止再次嘗試抹平 RPC 巢狀結構。

### Iteration 2: Knowledge Distillation & WikiSkill Meta-Pattern
- **Target Skill**: `wiki-distiller`
- **Action**: `create`
- **Proposal Rationale**: 依據 WikiSkill 論文（arXiv:2608.27454）與 Claude Code 對抗式審查成果，建立全域知識蒸餾 SOP 與專案元架構 Pattern。
- **Validation Command**: `.venv/Scripts/python.exe -m pytest tests/ -q` (422 passed, 6 subtests)
- **Validation Outcome**: `ACCEPTED`
- **Summary**: 建立了 `wiki-distiller` 專屬 Skill，並沉澱了 `patterns/wikiskill_architecture_and_experience_compilation.md` 作為所有 Agent 的全景經驗編譯指引。

### Iteration 3: Retrieval Gate & Citation Integrity
- **Target Skill**: `wiki-distiller`
- **Action**: `patch`
- **Proposal Rationale**: 稽核發現 Wiki 只有寫入迴路，沒有讓後續 Agent 動工前讀取的機制；且標註為 Verbatim 的 `_ok` / `_err` 已與現場源碼漂移。
- **Validation Command**: `C:\\Users\\cy5407\\AppData\\Local\\Programs\\Python\\Python313\\python.exe -m pytest tests/ -q` (426 passed, 6 subtests)；`... scripts/verify_wiki_citations.py` (5 patterns, 0 findings)
- **Validation Outcome**: `ACCEPTED`
- **Summary**: 以 `.claude/settings.json` 的 SessionStart hook、根目錄 `AGENTS.md` 與 `.claude/skills/wiki-distiller/` 接上讀取與觸發；新增 citation checker 與測試，並將 RPC 命令數校正為 16（6 guarded / 10 unguarded）、同步修正 `_ok` / `_err` 信封與 Python baseline。
