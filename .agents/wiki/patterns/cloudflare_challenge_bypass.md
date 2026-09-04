# Pattern: Cloudflare Challenge Bypass & Session Handling

## 1. Description
當 Agent 或爬蟲嘗試訪問 JavDB 網頁時，可能會遇到 Cloudflare WAF 攔截，回傳 HTTP 403 或 JavaScript / CAPTCHA Challenge 頁面，導致無法解析影片標題與磁力清單。

## 2. Root Cause
1. **TLS / HTTP2 指紋識別**：標準 Python `requests` 或 `urllib` 的 TLS Client Hello 指紋（Cipher Suites, Extensions 等）與真實瀏覽器存在特徵差異，直接觸發 Cloudflare Bot Management 攔截。
2. **過期或缺少 Cookie**：JavDB 需要合法的 Cloudflare Clear Clearance Cookie（`cf_clearance`）或登入 session cookie（`_jdb_session` 等）；若未帶 Cookie 或 Cookie 已失效，將收到 HTTP 403。

## 3. Evidence & Ground Truth Code
- 位於 `javdb_scraper.py:28-46`：
  ```python
  def create_session():
      headers = {
          "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
          "Accept-Language": "zh-TW,zh;q=0.9,ja;q=0.8,en-US;q=0.7,en;q=0.6",
          "Accept-Encoding": "gzip, deflate, br",
          "Connection": "keep-alive",
          "Upgrade-Insecure-Requests": "1",
          "Sec-Fetch-Dest": "document",
          "Sec-Fetch-Mode": "navigate",
          "Sec-Fetch-Site": "none",
          "Sec-Fetch-User": "?1",
          "Cache-Control": "max-age=0",
      }
      if HAS_CURL_CFFI:
          return cffi_requests.Session(impersonate="chrome124", headers=headers), "curl_cffi"
      headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
      session = requests.Session()
      session.headers.update(headers)
      return session, "requests"
  ```
- 位於 `sidecar/sidecar.py:578-584`（錯誤分類邏輯）：
  ```python
  error = result.get("error", "") or ""
  if error:
      if "403" in error:
          return _err(req, "cloudflare_block",
                      "JavDB returned 403 / challenge")
      return _err(req, "network", error)
  ```
- 位於 `sidecar/sidecar.py:149-169`（安全 Cookie 解析與 CWE-93 防護）：
  ```python
  def parse_cookie_string(s: str) -> dict[str, str]:
      """Parse `k=v; k=v` cookie header into dict. Empty/whitespace returns {}.

      Pairs containing CR or LF are dropped: a stray newline inside a
      cookie value is the classic shape for HTTP-header injection / response
      splitting (CWE-93). The desktop app never legitimately needs a
      multi-line cookie, so refusing is safer than escaping (F-05).
      """
      if not s or not s.strip():
          return {}
      out: dict[str, str] = {}
      for pair in s.split(";"):
          pair = pair.strip()
          if "=" not in pair:
              continue
          if "\r" in pair or "\n" in pair:
              continue
          key, value = pair.split("=", 1)
          out[key.strip()] = value.strip()
      return out
  ```

## 4. 偵測邊界與行為限制（Accurate Boundaries）
- **403 觸發 `cloudflare_block`**：目前 Sidecar 僅在 `error` 包含 `"403"` 時將錯誤碼歸類為 `cloudflare_block`。
- **503 歸類為 `network`**：若 Cloudflare 回傳 503，將歸類為 `network` 錯誤。
- **200 JS Challenge**：若 Cloudflare 以 200 回傳靜態挑戰頁面，HTML 解析器無法找到標籤，會回傳成功回應但 `magnet_count: 0`。

## 5. Action Patterns & Fix
- **優先使用 `curl_cffi` 偽裝**：強制啟用 `curl_cffi` 並指定 `impersonate="chrome124"`，模擬真實 Chrome 瀏覽器之 TLS / JA3 / HTTP2 指紋。
- **Cookie 帶入與安全解析**：透過 `parse_cookie_string()` 安全過濾 CR/LF 後帶入 `session.get(url, cookies=cookies)`。
- **錯誤碼精確處置**：遇 `cloudflare_block` 時提示使用者於設定介面更新 JavDB Cookies，不進行盲目重試。
