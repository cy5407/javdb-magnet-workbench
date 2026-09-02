# Pattern: Sidecar HTTP Pooling & Concurrency Invariants

## 1. Description & Context
專案在處理 Real-Debrid API 呼叫、多連結 Unrestrict 解析、以及前端表格過濾計算時面臨以下效能瓶頸：
1. **短連線開銷**：每次 `_rd_client` 重建 `requests.Session`，使每次 API 交互都重新進行 TCP 與 TLS 握手。
2. **多檔序列阻塞**：多檔案種子之 unrestrict 請求採序列迴圈，使 5 個檔案的解析需等待數秒。
3. **前端反覆計算**：Svelte 5 響應系統在每次局部重繪時反覆對所有群組呼叫 `processGroupRows`。
4. **測試 Fake 契約衝突**：若直接在 `RealDebrid.__init__` 強制要求 `session` 參數，會使既有單元測試（如 `test_sidecar_settings.py` 中簽名為 `_FakeClient(token, min_size_mb, deadline)` 的測試樁）引發 `TypeError`。

## 2. Root Cause
- **連線未復用**：Sidecar 雖然是常駐行程（Daemon），但客戶端工廠函式 `_rd_client` 缺乏跨請求之 `requests.Session` 儲存機制。
- **測試樁剛性契約**：測試模組採用嚴格的 Mock Class 攔截 `from realdebrid import RealDebrid`，測試樁未宣告 `**kwargs`，直接變更構造簽名將打破測試隔離邊界。
- **並行與閉包競爭**：前端整合測試模擬使用者點擊取消並驗證單一 `resolveSend` Promise，若在前端預設並行度 $>1$，第二個請求會覆蓋測試閉包中的 resolve handle 導致測試懸掛。

## 3. Verbatim Code Evidence

### 3.1 屬性注入保留測試相容性
- 位於 `sidecar/sidecar.py:928-931`：
  ```python
  if session is not None and hasattr(client, "session"):
      client.session = session
      client._shared_session = True
  return client
  ```

### 3.2 多檔連結並行 Unrestrict（保序）
- 位於 `realdebrid.py:539-544`：
  ```python
  if len(links) == 1:
      return [_unrestrict_one(links[0])]

  max_workers = min(4, len(links))
  with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
      return list(executor.map(_unrestrict_one, links))
  ```

### 3.3 前端 Worker Pool 與預設序向門禁
- 位於 `app/src/lib/rdSender.ts:211-228`：
  ```typescript
  const concurrency = Math.max(1, opts.concurrency ?? 1);
  if (concurrency <= 1) {
    for (let i = 0; i < items.length; i++) {
      if (opts.signal?.aborted) break;
      await processOne(i);
    }
  } else {
    let nextIndex = 0;
    const workerCount = Math.min(concurrency, items.length);
    const workers = Array.from({ length: workerCount }, async () => {
      while (nextIndex < items.length) {
        if (opts.signal?.aborted) break;
        const i = nextIndex++;
        await processOne(i);
      }
    });
    await Promise.all(workers);
  }
  ```

### 3.4 Svelte 5 $derived.by 表格過濾記憶化
- 位於 `app/src/App.svelte:569-575`：
  ```svelte
  let groupProcessedRowsMap = $derived.by(() => {
    const map = new Map<string, MagnetRow[]>();
    for (const g of groups) {
      map.set(g.url, processGroupRows(g, filter, sortColumn, sortDirection));
    }
    return map;
  });
  ```

## 4. Actionable Fix & Constraints
- **負向約束**：嚴禁在 `_rd_client` 強制傳遞建構參數破壞 `_FakeClient` 測試樁；應採屬性賦值（`client.session = session`）完成 Session 注入。
- **保序約束**：`_collect_links` 並行下載時，必須使用 `executor.map` 保持原始順序，嚴禁使用無序的 `as_completed`。
- **預設序向約束**：前端批次送出 `sendBatch` 必須將 `concurrency` 預設限制為 `1`，避免在 UI 整合測試環境中因共享 mock 閉包發生未處理之懸掛 Promise。