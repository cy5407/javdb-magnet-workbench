# 送 RD 完成但沒有任何直連 / 全部 pending

## 症狀

- 「送出 N 筆到 RD」進度跑完，**全部** row 顯示「RD 處理中」或都進待處理清單
- 「複製 N 條下載直連」按鈕的 N 是 0
- 之前同樣的磁力可以拿到直連、今天突然都 pending

## 常見根因

1. **磁力未被 RD 快取**（其他人沒下載過）→ RD 真的在從 BT 下載，需要 5–30 分鐘
2. `cache_wait_seconds` 設太短，**RD 還在判定就被本機放棄**
3. RD 端的 file_pick 選不到符合大小門檻的檔案，所有檔案都被跳過
4. RD Premium 過期 → 401 全失敗（但這會走 error 不是 pending；詳見 [rd-token.md](rd-token.md)）

## 檢查

### 1. 看 sidecar 怎麼判定的

```powershell
Select-String -Path "$env:LOCALAPPDATA\JavDBMagnet\logs\debug.log*" `
  -Pattern "rd_status|cache_wait|magnet_conversion|waiting_files|downloading"
```

關鍵字串：

| log 訊號 | 意義 |
|---|---|
| `magnet_conversion` | RD 還在處理 magnet 資料（最早期） |
| `waiting_files_selection` | RD 已轉好，等你選檔（這時 file_pick 介入） |
| `downloading` | RD 正在從 BT 下載（要真的等） |
| `cache_wait timeout` | 本機等夠 cache_wait_seconds 後判定未快取，加入 pending |

### 2. 直接到 RD 後台確認

[real-debrid.com/torrents](https://real-debrid.com/torrents) 看 pending 的 torrent 狀態：

- `Downloading 0%` 持續 10+ 分鐘 → seeder 少，慢
- `Magnet error` → RD 那邊解析失敗（磁力本身有問題）
- `Dead torrent` → 完全沒 seeder，永遠不會完成

### 3. 設定面板看一下

「應用程式設定」展開，確認：

- `cache_wait_seconds`：預設 15。如果你之前手動改成 5 就太短了（M7c validation 已擋下 < 5，但舊資料可能殘留）
- `min_size_mb`：預設 500。若磁力本身只含小檔案（例如 200MB 的短片），會被全跳過
- `file_pick`：smart 是預設；改成 `all` 可以暫時繞過大小門檻看是否還是空

## 修復步驟

### 對未快取磁力（多數情況）

不用改設定，直接等：

1. 看「待處理」表格
2. 5–15 分鐘後按「**全部重試**」
3. 已完成 → 自動移出 pending、產生直連
4. 還在下載 → 顯示 RD 端 progress

如果 30 分鐘還是 `downloading 0%`，那磁力大概率沒 seeder，到 RD 後台刪掉是合理動作。

### file_pick 把所有檔案都跳過

最快驗證：把 `file_pick` 暫時改成 `all` 再送一次同樣磁力。

- 改 `all` 後成功 → 確認是 file_pick 邏輯問題；改回 `smart` 並把 `min_size_mb` 調低（例如 200）
- 改 `all` 仍 pending → 不是 file_pick 問題，回頭看根因 #1

### cache_wait 太短

「應用程式設定」把 `cache_wait_seconds` 設回 15（或 20）。

## 預防

- `cache_wait_seconds = 15` 是合理預設；除非你在掃大量已知熱門磁力（全已快取），否則不要往下調
- 看到 1–2 筆 pending 是正常的；全部 pending 才需要懷疑
- 對「dn= 帶冷門番號 + 沒人下過」這類磁力，pending 是正常結果而非 bug
