# JavDBMagnet

Windows 桌面工具：貼上 JavDB 影片頁網址，批次抓出磁力連結，挑好後送到 Real-Debrid（RD），
拿回可以直接下載的 https 連結。

個人與非商業用途可免費使用，商業用途需另行取得授權（見[授權](#授權)）。
修改、測試、建置請看[開發者文件](docs/development.md)。

---

## 怎麼用

程式有四個分頁，照順序走：

| 分頁 | 做什麼 |
|---|---|
| 1. 擷取 Magnet | 貼多個 JavDB 影片頁網址一次抓磁力；手上已經有磁力就用「直接貼上」，不經過 JavDB |
| 2. 挑選 Magnet | 每部影片一組，可依關鍵字、高清、大小篩選排序；「每組只留」可每組只保留一筆，「只勾選 RD 優先候選」會一鍵勾好推薦的那筆 |
| 3. RD 下載連結 | 送到 RD，拿回直連；可全部一次複製或單筆複製。RD 還沒處理完的會進「待處理」，之後再按重試 |
| 4. 設定 | RD Token、JavDB Cookies、選檔規則、資料位置、匯入舊版資料 |

**為什麼有「RD 優先候選」**：別人送過的磁力 RD 會立刻給連結，沒人送過的就要等 RD 下載。
RD 已經不提供「查詢是否已快取」的功能，所以程式用規則**推測**哪一筆比較可能秒回：
轉載站前綴（例如 `hhd800.com@`）＋高清 ＞ 最早上傳的高清 ＞ 全都不是高清（標 ⚠，不自動勾）。
要送的批次裡有低機率項目時，送出前會先跳摘要，可以選「只送高機率」。

同一個磁力不會重複送 RD，不會白白扣額度。

---

## 安裝

需要：Windows 10 1809 以上或 Windows 11、WebView2 Runtime（Windows 11 內建）、
Real-Debrid 帳號（只抓磁力不送 RD 就不需要）、約 30 MB 磁碟空間。

1. 到 [GitHub Releases](https://github.com/cy5407/javdb-magnet-workbench/releases) 下載
   `JavDBMagnet_<版本>_portable.zip`，解壓到任意資料夾。目前 Releases 最新是 **v0.3.0**；
   0.3.1 還沒發佈，要用請照[開發者文件](docs/development.md#建置與發佈)自行建置。
2. 雙擊資料夾裡的 `javdbmagnet.exe`。旁邊的 `sidecar.exe` 不能刪或搬走。

程式沒有數位簽章，第一次執行可能跳 SmartScreen 警告。可以先用 release 附的
`SHA256SUMS.txt` 核對檔案沒被改過，再按「更多資訊」→「仍要執行」：

```powershell
Get-FileHash -Algorithm SHA256 .\JavDBMagnet_*_portable.zip
```

---

## 第一次設定

都在「4. 設定」分頁，兩樣東西設好就能用。

**1. Real-Debrid Token**

到 <https://real-debrid.com/apitoken> 複製 token，貼進「Real-Debrid Token」，
按「測試連線」看到帳號資訊後按「儲存」。

**2. JavDB Cookies**（JavDB 要登入才看得到磁力）

按「貼上新 cookies」，貼上瀏覽器 DevTools → Network → 任一 JavDB 請求的 `Cookie:`
標頭值（不含 `Cookie: ` 這幾個字），按「儲存到認證管理員」。看到「cookies 已加密儲存」就生效。

<details>
<summary>另一種方式：用範本檔</summary>

按「建立 cookies.txt 範本」，再按「打開資料目錄」用記事本編輯 `cookies.txt`
（照檔內說明貼在最後一行，存成 UTF-8），回程式按「重新整理 / 套用變更」。
內容會加密存好，明文檔隨即刪除。
</details>

Cloudflare 的 cookie 幾小時就會過期，被擋的時候重貼一次最快。

**試跑**：在「1. 擷取 Magnet」貼一個 JavDB 影片頁網址，按「開始擷取」，有出現磁力數量就是設定成功。

Token 和 cookies 都加密存在 Windows 認證管理員，不會寫進任何純文字檔。

---

## 設定項目

「4. 設定」→「應用程式設定」，按「儲存設定」立即生效，不必重開。

| 欄位 | 預設 | 說明 |
|---|---|---|
| 選檔策略（`file_pick`） | `smart` | RD 要下載種子裡的哪些檔案：`smart` / `largest` / `video` / `all` |
| 最小檔案（`min_size_mb`） | `500` | 小於此 MB 的影片視為廣告略過（0–1,000,000） |
| 快取等待（`cache_wait_seconds`） | `15` | 等 RD 回應幾秒（5–300），超過就進待處理 |
| 主題（`theme`） | `light` | `light` / `dark` |
| 縮放（`scale`） | `auto` | `auto` 或 0.5–3.0；4K 螢幕建議 1.5–2.0 |

**從舊版 Python 程式搬過來**：「4. 設定」→「匯入舊版資料」，選舊版資料夾，先「預覽」再匯入。
Token、設定、cookies、待處理清單都會搬過來，舊檔案不會被刪除。

---

## 資料放在哪

| 內容 | 位置 |
|---|---|
| 設定 | `%APPDATA%\JavDBMagnet\settings.json` |
| 待處理清單 | `%APPDATA%\JavDBMagnet\pending_torrents.json` |
| 日誌 | `%LOCALAPPDATA%\JavDBMagnet\logs\` |
| RD Token | Windows 認證管理員：`RD_API_TOKEN.JavDBMagnet` |
| JavDB Cookies | Windows 認證管理員：`JAVDB_COOKIES.JavDBMagnet` |

「4. 設定」的「儲存位置」有按鈕可以直接打開這些資料夾。

**不要分享或同步到雲端**：`cookies.txt`（登入憑證）、`pending_torrents.json`（送過的種子）、
`logs\rd_outcomes.jsonl`（含番號與檔名，等於觀看紀錄）。

**移除**：刪掉解壓出來的資料夾即可。要連個人資料一起清掉：

```powershell
Remove-Item "$env:APPDATA\JavDBMagnet" -Recurse -Force
Remove-Item "$env:LOCALAPPDATA\JavDBMagnet" -Recurse -Force
cmdkey /delete:RD_API_TOKEN.JavDBMagnet
cmdkey /delete:JAVDB_COOKIES.JavDBMagnet
```

---

## 遇到問題

| 狀況 | 看這裡 |
|---|---|
| 抓不到 JavDB、被 Cloudflare 擋 | [`cloudflare.md`](docs/troubleshooting/cloudflare.md) |
| RD Token 顯示無效／401 | [`rd-token.md`](docs/troubleshooting/rd-token.md) |
| 送 RD 後沒有連結，全部進待處理 | [`no-pending-links.md`](docs/troubleshooting/no-pending-links.md) |
| 想確認日誌沒有洩漏磁力 | [`log-redaction-verification.md`](docs/troubleshooting/log-redaction-verification.md) |

---

## 授權

本專案採用 [PolyForm Noncommercial 1.0.0](LICENSE)：

- **可以免費使用**：個人使用、學習、研究、興趣專案，以及學校、公益團體等非營利組織。
- **需要另外取得授權**：任何商業用途，例如公司內部使用、整合進付費產品或服務。
  請在 [GitHub](https://github.com/cy5407) 聯絡作者洽談。

這不是 OSI 定義的開源授權，而是「原始碼公開」：可以看、可以改、可以非商業轉散佈，
轉散佈時要一併附上 LICENSE 檔與其中的 `Required Notice` 那一行。

程式內含的第三方元件依各自的授權散佈，portable zip 內的 `THIRD_PARTY_NOTICES.txt` 列有完整清單與授權全文。
