# Real-Debrid Token invalid / 401

## 症狀

- 「測試連線」按了顯示「Token 無效」或 `rd_token_invalid`
- 「送出 N 筆到 RD」失敗，全部 row 標 `失敗`，error code 顯示 `rd_token_invalid`
- 「查詢帳號」失敗
- 上次明明可以，今天突然不行

## 常見根因

1. RD 帳號 **Premium 過期**（過期會降為 free，token 仍存在但無權呼叫 add magnet）→ error code 變 `rd_premium_required`
2. Token 在 RD 後台被撤銷 / 重新產生（你或 RD 安全機制觸發）
3. 複製 token 時前後帶到空白 / 換行 / 不完整
4. Credential Manager 條目壞掉（極罕見）

## 檢查

### 1. 看 token 是否真的存著

PowerShell：

```powershell
cmdkey /list | Select-String -Pattern "JavDBMagnet"
```

預期看到：

```
    Target: JavDBMagnet/RD_API_TOKEN
    Type:   Generic
```

無輸出 = token 沒存（app 顯示「✗ 未設定」也是同一現象）。

### 2. 看 RD 後台 token 還在不在

打開 [real-debrid.com/apitoken](https://real-debrid.com/apitoken) 對照 token 字串前後幾碼。RD 後台只能看到目前生效的 token；若你看到的跟之前不同 = 已被重新產生。

### 3. 看帳號是否仍 Premium

[real-debrid.com](https://real-debrid.com) 登入後右上角看「Premium until ...」日期。過期 → 解掉就是 free 帳號。

### 4. 看 sidecar 怎麼說

`%LOCALAPPDATA%\JavDBMagnet\logs\debug.log` 內搜：

```powershell
Select-String -Path "$env:LOCALAPPDATA\JavDBMagnet\logs\debug.log*" -Pattern "rd_token_invalid|rd_premium_required|HTTP 401|HTTP 403"
```

`rd_premium_required` → 對應根因 #1；`rd_token_invalid` → 對應根因 #2 或 #3。

## 修復步驟

### 根因 #1（Premium 過期）

無法靠 app 解決。續訂 Premium → 等 RD 後台顯示新期限 → 重新「查詢帳號」即可（不必重設 token）。

### 根因 #2 或 #3（token 失效或複製錯）

1. 到 [real-debrid.com/apitoken](https://real-debrid.com/apitoken)
2. **不要按「Generate new token」** —— 先試直接複製目前那串看看
3. 在 app 內「Real-Debrid」區塊：
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
cmdkey /list:JavDBMagnet*

# 手動刪掉
cmdkey /delete:JavDBMagnet/RD_API_TOKEN
```

回 app 重新貼 token + 儲存即可。

## 預防

- 不要把 token 貼到任何別處（git commit、群組訊息、雲端筆記）
- 設一個日曆提醒看 RD Premium 到期日
- 出問題時優先看 `debug.log` 的 error code 再對症下藥；別反射性 regenerate token
