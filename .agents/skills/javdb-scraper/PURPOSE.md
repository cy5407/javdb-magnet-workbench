# Purpose: javdb-scraper

## 1. Origin
本技能為 JavDB Magnet Workbench 之核心作業規範，旨在指導 Agent 正確處理 JavDB 網頁爬取、Cloudflare TLS 偽裝、Sidecar RPC 交互、Handle ID 隔離與 Real-Debrid 智慧選檔加速流程。
跨層契約的唯一真實來源（Canonical Source of Truth）為 `docs/architecture/contracts/` 與 `docs/architecture/function-contracts.md`。

## 2. Patterns Addressed
本技能直接吸收並對應下列 Wiki 持久知識庫中之踩坑模式：
- `wiki/patterns/cloudflare_challenge_bypass.md`：防範 WAF 阻擋與 TLS 指紋識別，精確處置 403 `cloudflare_block`。
- `wiki/patterns/rpc_response_shape_mismatch.md`：確保跨層 RPC 呼叫嚴格遵循 `_ok`/`_err` 信封與巢狀/平鋪回傳契約。
- `wiki/patterns/rate_limit_backoff_deadlock.md`：遵守 RD API 429 退避限制（$\le 10$s, $\le 3$ 次）與超時預算。

## 3. Evolution History
- **v1.0.0 (Iteration 0)**: 初始版本建立，規範 `fetch_javdb` 與 `rd_send_magnet` 標準 SOP。
- *(Iteration 1 的扁平化修訂提案因違反跨層契約已被 REJECTED 回滾，本技能維持 v1.0.0)*
