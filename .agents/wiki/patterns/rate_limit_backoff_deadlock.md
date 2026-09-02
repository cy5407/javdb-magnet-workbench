# Pattern: Rate Limit Backoff & Timeout Deadlock

## 1. Description
在向 Real-Debrid API 發送大量種子或頻繁輪詢狀態時，若觸發 HTTP 429 (Too Many Requests)，未妥善處理 `Retry-After` 或未設定嚴格 Deadline，會導致請求阻塞、重試風暴或主程序超時斷線（Timeout Deadlock）。

## 2. Root Cause
1. **無界等待與未對齊超時預算**：Rust 端 IPC 調度設定了 `timeout_for = cache_wait + 90` 秒（`sidecar_manager.rs`）。若 Python 端 429 重試等待時間累計超過外部調度預算，Rust 會強制終止請求，導致 Sidecar 狀態與前端脫節。
2. **429 重試次數失控**：無限制重試會耗盡連線池並觸發 RD 伺服器進一步封鎖。

## 3. Evidence & Ground Truth Code

### 3.1 429 退避限制與重試預算（Verbatim Code）
- 位於 `realdebrid.py:20` 與 `realdebrid.py:106-124`：
  ```python
  MAX_RETRY_AFTER_SECONDS = 10

  def _retry_after_rate_limit(self, resp, method: str, path: str, retry_count: int, kwargs: dict, deadline: Optional[float] = None):
      """429 自動重試（最多 3 次）"""
      if retry_count >= 3:
          logger.error("429 重試 3 次仍失敗")
          raise RealDebridError("HTTP 429: 請求頻率過高，請稍後再試")
      dl = deadline if deadline is not None else self.deadline
      parsed = self._parse_retry_after(resp)
      wait = min(max(parsed, 0.0), float(MAX_RETRY_AFTER_SECONDS))
      if dl is not None:
          remaining = dl - time.monotonic()
          if remaining <= 0:
              raise RealDebridError("HTTP 429: 請求超過時間預算")
          wait = min(wait, max(0.0, remaining))
      if wait > 0:
          logger.warning(f"429 速率限制，等待 {wait}s 後重試（第 {retry_count + 1}/3 次）")
          time.sleep(wait)
      else:
          logger.warning(f"429 速率限制，立即重試（第 {retry_count + 1}/3 次）")
      return self._request(method, path, _retry_count=retry_count + 1, deadline=dl, **kwargs)
  ```

### 3.2 邊界常數定義
- 位於 `sidecar/sidecar.py:67-68`：
  ```python
  MIN_RD_CACHE_WAIT_SECS = 5
  MAX_RD_CACHE_WAIT_SECS = 300
  ```
- `cmd_rd_send_magnet` 內部計算 deadline（`sidecar/sidecar.py:1088`）：
  ```python
  deadline = time.monotonic() + cache_wait + 75.0
  ```
  確保與 Rust 外層調度器預算（`cache_wait + 90.0`）保持 15 秒的安全餘裕。

## 4. Action Patterns & Fix
- **硬性上限約束**：單次 429 退避等待時間以 `MAX_RETRY_AFTER_SECONDS = 10` 為上限，重試次數嚴格限制 $\le 3$ 次。
- **動態 Deadline 計算**：每個 HTTP 請求均帶入 `deadline` 參數，計算 `remaining = dl - time.monotonic()`；一旦超時立即拋出例外，終止無效等待。
- **排入待處理佇列**：若磁力非秒回且未在 `cache_wait` 內完成，轉為 `status="pending"` 並由 Rust 寫入 `pending_torrents.json` 待後續異步重試，絕不阻塞主執行緒。
