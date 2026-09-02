# JavDB Magnet Workbench Wiki Index

本目錄為專案持久知識庫（Wiki Layer）索引，記錄已編譯之踩坑模式、根本原因與標準解決方案。
專案權威契約請參閱 `docs/architecture/contracts/` 與 `docs/architecture/function-contracts.md`。

## Known Patterns
- [wiki_retrieval_and_citation_integrity](patterns/wiki_retrieval_and_citation_integrity.md): 知識只寫入但未在工作前載入，且逐字引用會隨重構漂移 + 缺少讀取觸發與機器校驗 + 以 SessionStart／AGENTS 讀取門和 citation checker 把經驗轉為可執行約束。
- [wikiskill_architecture_and_experience_compilation](patterns/wikiskill_architecture_and_experience_compilation.md): 傳統 Agent 演化造成歷史失憶與負遷移 + 知識與技能強耦合且缺乏單調累積記憶 + 採三層解耦架構（Raw/Wiki/Skill）、Wiki 永不回滾保留負向約束、Skill 保持精簡並經測試嚴格門控。
- [cloudflare_challenge_bypass](patterns/cloudflare_challenge_bypass.md): JavDB 網頁抓取遭 Cloudflare WAF 攔截 (403/Challenge) + 標準 HTTP Client TLS 指紋特徵差異與缺少 Cookie + 強制啟用 curl_cffi Chrome-124 偽裝並帶入安全解析之 Cookie，僅 403 歸類為 cloudflare_block。
- [rpc_response_shape_mismatch](patterns/rpc_response_shape_mismatch.md): 跨層調度解析 Sidecar RPC 回應出現欄位缺失或 KeyError + 遺漏 _ok/_err 信封或混淆雙層巢狀 (fetch_javdb, rd_user) 與平鋪命令 + 嚴格遵循 sidecar.py 原始信封契約與 6 個 handshake 守衛命令規範。
- [rate_limit_backoff_deadlock](patterns/rate_limit_backoff_deadlock.md): Real-Debrid API 頻繁請求觸發 HTTP 429 導致主程序超時死鎖 + 無界等待累積超過 Rust 調度預算 (cache_wait + 90s) + 限制單次退避上限 10 秒、最多重試 3 次，並結合 deadline 預算檢查與 pending 佇列異步輪詢。
- [sidecar_http_pooling_and_concurrency_invariants](patterns/sidecar_http_pooling_and_concurrency_invariants.md): HTTP 短連線開銷高且 Session 復用易遺失授權標頭 + 測試樁契約衝突、並行閉包競爭與發布門禁攔截 + 採屬性注入與標頭同步、_collect_links 線程池保序、白名單測試標籤與進程解鎖。
