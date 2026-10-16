# Cloudflare 阻擋 / cookies 過期

## 症狀

- 「1. 擷取 Magnet」分頁按「開始擷取」後，網址那列顯示 ✗ 與「錯誤：JavDB returned 403 / challenge」
  （sidecar error code `cloudflare_block`，對應 JavDB 回 HTTP 403）
- 或該列顯示「錯誤：HTTP <狀態碼>」（例如 `HTTP 302` 被導去登入頁、`HTTP 503` 挑戰頁）——
  抓取一律不跟隨轉址，非 200 都會以這個格式回報
- 完全抓不到磁力（所有 URL 都失敗）
- 前一天還可以、今天突然全失敗

> JavDB 抓取（`javdb_scraper.py`）不寫 `debug.log`，失敗原因只會出現在 UI 那一列的錯誤訊息；
> 到 logs 目錄搜 `403` / `cloudflare` 找不到東西是正常的。

## 常見根因

1. `cf_clearance` cookie 過期（最常見；Cloudflare 大約每 4–24 小時換一次）
2. `_jdb_session` 過期（JavDB 登入 session 失效，登出狀態看不到磁力）
3. 換了網路環境（IP 變動，Cloudflare 重新挑戰）
4. 根本沒有 cookies：Credential Manager 裡沒有 `JAVDB_COOKIES.JavDBMagnet`，或 `cookies.txt` 範本
   沒被套用（只有範本註解、或存成 UTF-16 而讀不進來）

## 檢查

在 app 內：

1. 「**4. 設定**」分頁 →「**JavDB Cookies**」展開
2. 看狀態列：
   - 「✓ cookies 已加密儲存」：cookies 在 Credential Manager。app 從不讀取內容，也不顯示存入時間——
     判斷不了新舊時，直接走下方修復步驟重貼一次最快
   - 「○ cookies.txt 已建立」（會顯示大小與修改時間）：明文範本還在、尚未搬進 Credential Manager。
     按「**重新整理 / 套用變更**」後若仍停在這個狀態，代表檔內沒有真正的 cookie 行，或檔案不是 UTF-8
   - 「✗ 尚未設定 cookies」：沒有任何 cookies，JavDB 擷取一定會被擋

PowerShell：

```powershell
# Credential Manager 裡有沒有 cookies 條目
cmdkey /list | Select-String -Pattern "JAVDB_COOKIES"

# 若還在用 cookies.txt 範本：看檔大小與修改時間（過小可能是內容被截掉）
Get-Item "$env:APPDATA\JavDBMagnet\cookies.txt" | Select-Object Length, LastWriteTime
```

範本檔最後一行應是一整行包含 `_jdb_session`、`cf_clearance`、`locale` 等 cookie 名稱的內容
（不是 `#` 開頭的註解）。

## 修復步驟

1. 用瀏覽器登入 [javdb.com](https://javdb.com)
2. F12 → **Network** → 重新整理頁面 → 點任一 request → **Request Headers** → 找 `Cookie:` 整行
3. **完整複製整行的值**（不含「Cookie: 」前綴；要包含 `_jdb_session` 與 `cf_clearance` 兩個 cookie，只有其一不夠）
4. 在 app 內「JavDB Cookies」按「**貼上新 cookies**」，貼進出現的框
5. 按「**儲存到認證管理員**」→ 看到「cookies 已加密儲存到 Credential Manager，sidecar 已即時更新（不必重啟 app）。」
6. 重試一次「開始擷取」

偏好用檔案的話：按「建立 cookies.txt 範本」→「打開資料目錄」→ 用記事本（注意：**存檔時編碼選
UTF-8 而非 UTF-16**）把 cookie 整行貼到 `cookies.txt` 最後一行 → 回 app 按「**重新整理 / 套用變更**」，
狀態變成「✓ cookies 已加密儲存」即已搬進 Credential Manager 並刪除明文檔。

## 仍然不行

- 確認沒在 Network tab 複製到別人的 cookie（多 tab 容易看錯）
- 試完整登出 javdb.com → 重新登入 → 再複製
- 換另一個瀏覽器（清除其他 cookie 干擾）試一次
- 錯誤一直是「JavDB returned 403 / challenge」表示 Cloudflare 仍在挑戰，你可能需要：
  - 在瀏覽器先把 javdb.com 開著、過完 Cloudflare 挑戰、看到正常網頁後 **才**複製 cookie
  - 不要在 incognito 模式取 cookie（很多瀏覽器 incognito 的 cf_clearance 跟一般模式不通用）
