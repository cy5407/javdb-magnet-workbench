# Real-Debrid Token invalid / 401

## 症狀

- 「測試連線」按了顯示「測試失敗：Real-Debrid Token 無效或已過期」（error code `rd_token_invalid`）
- 「送出已勾選 N 筆到 RD」後全部 row 標「失敗」，訊息欄顯示「Real-Debrid Token 無效或已過期」或「需要 Real-Debrid Premium 帳號」
- 「查詢帳號」顯示「查詢失敗：…」
- 「儲存」顯示「儲存失敗：（其他錯誤：rd_token_format_invalid）」
- 上次明明可以，今天突然不行

## 常見根因

1. RD 帳號 **Premium 過期**（過期會降為 free，token 仍存在但無權呼叫 add magnet）→ error code 變 `rd_premium_required`
2. Token 在 RD 後台被撤銷 / 重新產生（你或 RD 安全機制觸發）
3. 複製 token 時帶到多餘字元或不完整（前後空白會自動去掉；中間夾到空白 / 換行等非英數字元、或超過 255 字，儲存時會被 `rd_token_format_invalid` 擋下；少複製幾碼則是測試時回 `rd_token_invalid`）
4. Credential Manager 條目壞掉（極罕見）

## 檢查

### 1. 看 token 是否真的存著

PowerShell：

```powershell
cmdkey /list | Select-String -Pattern "JavDBMagnet"
```

預期看到一筆 target 含 `RD_API_TOKEN.JavDBMagnet` 的條目（`keyring` crate 在 Windows 以 `<帳戶>.<服務>` 組 target name）。

無輸出 = token 沒存（app 顯示「Token：✗ 未設定」也是同一現象）。

### 2. 看 RD 後台 token 還在不在

打開 [real-debrid.com/apitoken](https://real-debrid.com/apitoken) 對照 token 字串前後幾碼。RD 後台只能看到目前生效的 token；若你看到的跟之前不同 = 已被重新產生。

### 3. 看帳號是否仍 Premium

[real-debrid.com](https://real-debrid.com) 登入後右上角看「Premium until ...」日期。過期 → 解掉就是 free 帳號。

### 4. 看 sidecar 怎麼說

`%LOCALAPPDATA%\JavDBMagnet\logs\debug.log` 內搜：

```powershell
Select-String -Path "$env:LOCALAPPDATA\JavDBMagnet\logs\debug.log*" -Pattern "HTTP 401|HTTP 403"
```

`debug.log` 不記 error code，只有 RD client 的 HTTP 回應行（`← HTTP 401 (… bytes)`）與緊接著的
ERROR 行。`HTTP 403`（下一行 `帳號權限不足`）→ 對應根因 #1（UI 為 `rd_premium_required`）；
`HTTP 401`（下一行 `API token 無效或已過期`）→ 對應根因 #2 或 #3（UI 為 `rd_token_invalid`）。

## 修復步驟

### 根因 #1（Premium 過期）

無法靠 app 解決。續訂 Premium → 等 RD 後台顯示新期限 → 重新「查詢帳號」即可（不必重設 token）。

### 根因 #2 或 #3（token 失效或複製錯）

1. 到 [real-debrid.com/apitoken](https://real-debrid.com/apitoken)
2. **不要按「Generate new token」** —— 先試直接複製目前那串看看
3. 在 app 的「4. 設定」分頁「Real-Debrid Token」區塊：
   - 「貼上新 Token 以更換」欄位貼進剛複製的 token
   - 按「**測試連線**」
   - 如果還是失敗 → 回 RD 後台按「Generate new token」產一條全新的，再貼一次
4. 「**儲存**」

儲存後 app 會：

- 把新 token 寫進 Credential Manager（舊的覆蓋）
- 立刻推到 sidecar，**不必重啟**

### 根因 #4（Credential Manager 條目壞掉）

```powershell
# 看出問題的條目
cmdkey /list | Select-String -Pattern "JavDBMagnet"

# 手動刪掉
cmdkey /delete:RD_API_TOKEN.JavDBMagnet
```

也可以直接在 app 內按「清除 Token」（有 token 時才出現），效果相同。

回 app 重新貼 token + 儲存即可。

## 預防

- 不要把 token 貼到任何別處（git commit、群組訊息、雲端筆記）
- 設一個日曆提醒看 RD Premium 到期日
- 出問題時優先看 UI 上的錯誤訊息與 `debug.log` 的 HTTP 狀態碼再對症下藥；別反射性 regenerate token
