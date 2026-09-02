# Pattern: RPC Response Shape Mismatch & Envelope Contract

## 1. Description
呼叫端（如 Rust Tauri 或 TypeScript 前端）在解析 Sidecar RPC 回傳 JSON 時，若假設回傳結構為平鋪欄位（Flattened Shape）而非實際的巢狀結構（Nested Structure），或者遺漏了外層的 JSON-RPC 信封（Envelope），會導致 `KeyError`、`undefined` 或解析崩潰。

## 2. Root Cause
1. **信封層遺漏**：Sidecar 所有成功回應均由 `_ok()` 封裝成 `{"ok": true, "request_id": ..., **payload}`；錯誤回應均由 `_err()` 封裝成 `{"ok": false, "request_id": ..., "error": {"code": ..., "message": ..., "internal": ...}}`。
2. **巢狀層級與平鋪混淆**：在 16 個 Sidecar 命令中，僅 `fetch_javdb`（包裹於 `result` 物件）與 `rd_user`（包裹於 `user` 物件）採用雙層巢狀結構；其餘 14 個命令（如 `rd_send_magnet`, `resolve_magnet`）則將欄位平鋪於 `_ok` 信封內。若呼叫端未對齊特定命令的回傳形狀，將發生解析失敗。

## 3. Evidence & Ground Truth Code

### 3.1 基礎回應信封（Envelope）
- 位於 `sidecar/sidecar.py:222-234`：
  ```python
  def _ok(req: dict, extra: dict | None = None) -> dict:
      out = {"ok": True, "request_id": req.get("request_id")}
      if extra:
          out.update(extra)
      return out

  def _err(req: dict, code: str, message: str, internal: str = "") -> dict:
      return {
          "ok": False,
          "request_id": req.get("request_id"),
          "error": {"code": code, "message": message, "internal": internal},
      }
  ```

### 3.2 巢狀結構命令 (`fetch_javdb` 與 `rd_user`)
- **`cmd_fetch_javdb`**（`sidecar/sidecar.py:595-604`）：
  ```python
  return _ok(req, {
      "result": {
          "engine": engine,
          "url": url,
          "code": result.get("code", "") or "",
          "title": result.get("title", "") or "",
          "magnet_count": len(magnets_out),
          "magnets": magnets_out,
      }
  })
  ```
  `magnets_out` 陣列中每筆項目包含 `handle_id`, `name`, `size`, `tags`, `date`, `magnet_redacted`。
- **`cmd_rd_user`**（`sidecar/sidecar.py:974-981`）：
  ```python
  return _ok(req, {
      "user": {
          "username": info.get("username", ""),
          "type": info.get("type", ""),
          "expiration": info.get("expiration", ""),
          "points": info.get("points", 0),
      }
  })
  ```

### 3.3 平鋪結構命令 (`rd_send_magnet`, `resolve_magnet` 等)
- **`cmd_rd_send_magnet`**（`sidecar/sidecar.py:1125-1148`）：
  - `status="completed"` 時回傳：`{"ok": true, "request_id": ..., "status": "completed", "torrent_id": ..., "name": ..., "links": [...]}`
  - `status="pending"` 時回傳：`{"ok": true, "request_id": ..., "status": "pending", "torrent_id": ..., "name": ..., "rd_status": ..., "progress": ..., "files_selected": bool, "strategy": ...}`
- **`cmd_resolve_magnet`**（`sidecar/sidecar.py:617`）：回傳 `{"ok": true, "request_id": ..., "magnet": full_uri}`。

## 4. Handshake 前置條件守衛（權威對齊）
依據權威契約 `docs/architecture/contracts/sidecar-runtime.md:89-104`，僅有以下 **6 個命令** 受到 `if not state.handshake_done:` 守衛：
1. `fetch_javdb`
2. `set_cookies`
3. `rd_user`
4. `rd_set_token`
5. `rd_send_magnet`
6. `rd_check_pending`

其餘 10 個命令（如 `resolve_magnet`, `register_magnets`, `forget_magnets`, `update_settings`, `cancel`, `ping`, `hello`）無 handshake 守衛。

## 5. Action Patterns & Fix
- 呼叫端必須先驗證 `resp["ok"] === true`，若為 `false` 則從 `resp["error"]["code"]` 與 `resp["error"]["message"]` 提取錯誤。
- 讀取 `fetch_javdb` 時透過 `resp["result"]["magnets"]` 存取；讀取 `rd_user` 時透過 `resp["user"]` 存取；其餘命令直接讀取信封層欄位。
