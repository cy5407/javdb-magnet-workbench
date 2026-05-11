# Cloudflare 阻擋 / cookies 過期

## 症狀

- 「批次擷取」按下後群組 row 顯示「失敗」
- log 內出現 `403 Forbidden`、`cloudflare`、`Just a moment...`、`Attention Required` 或類似字串
- 完全抓不到磁力（所有 URL 都失敗）
- 前一天還可以、今天突然全失敗

## 常見根因

1. `cf_clearance` cookie 過期（最常見；Cloudflare 大約每 4–24 小時換一次）
2. `_jdb_session` 過期（JavDB 登入 session 失效，登出狀態看不到磁力）
3. 換了網路環境（IP 變動，Cloudflare 重新挑戰）
4. cookies.txt 整個被刪 / 沒放對位置 / 編碼是 UTF-16

## 檢查

在 app 內：

1. 「**JavDB Cookies**」展開
2. 看「修改時間」是否在過去 24 小時內 —— 太久遠就一定要換
3. 按「**打開資料目錄**」確認 cookies.txt 真的在那邊

PowerShell：

```powershell
# 看檔大小（過小可能是內容被截掉）
Get-Item "$env:APPDATA\JavDBMagnet\cookies.txt" | Select-Object Length, LastWriteTime

# 看內容前幾行（檢查格式，不會洩漏完整 cookie value 到對話 — 你自己看就好）
Get-Content "$env:APPDATA\JavDBMagnet\cookies.txt" | Select-Object -First 2
```

預期看到一行包含 `_jdb_session`、`cf_clearance`、`locale` 等 cookie 名稱。

## 修復步驟

1. 用瀏覽器登入 [javdb.com](https://javdb.com)
2. F12 → **Network** → 重新整理頁面 → 點任一 request → **Request Headers** → 找 `Cookie:` 整行
3. **完整複製整行**（要包含 `_jdb_session` 與 `cf_clearance` 兩個 cookie；只有其一不夠）
4. 在 app 內「JavDB Cookies」按「打開資料目錄」
5. 用記事本（注意：**存檔時編碼選 UTF-8 而非 UTF-16**）開 `cookies.txt`，整個覆蓋成新內容
6. 回 app 按「**重新整理**」 → 修改時間應更新
7. 重試一次「批次擷取」

## 仍然不行

- 確認沒在 Network tab 複製到別人的 cookie（多 tab 容易看錯）
- 試完整登出 javdb.com → 重新登入 → 再複製
- 換另一個瀏覽器（清除其他 cookie 干擾）試一次
- log 看到 `Just a moment...` 表示 Cloudflare 仍在挑戰，你可能需要：
  - 在瀏覽器先把 javdb.com 開著、過完 Cloudflare 挑戰、看到正常網頁後 **才**複製 cookie
  - 不要在 incognito 模式取 cookie（很多瀏覽器 incognito 的 cf_clearance 跟一般模式不通用）
