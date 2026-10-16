# 送 RD 完成但沒有任何直連 / 全部 pending

## 症狀

- 「送出已勾選 N 筆到 RD」進度跑完，**全部** row 顯示「RD 處理中」或都進待處理清單
- 「複製 N 條下載連結」按鈕的 N 是 0（狀態列「下載連結：0」）
- 之前同樣的磁力可以拿到直連、今天突然都 pending

## 常見根因

1. **磁力未被 RD 快取**（其他人沒下載過）→ RD 真的在從 BT 下載，需要 5–30 分鐘
2. `cache_wait_seconds` 設太短，**RD 還在判定就被本機放棄**
3. RD 遲遲沒把 magnet 轉成檔案清單（`magnet_conversion` 卡住，常見於 seeder 很少的磁力），cache_wait 內連選檔都來不及
4. RD Premium 過期 → 401 全失敗（但這會走 error 不是 pending；詳見 [rd-token.md](rd-token.md)）

## 檢查

### 1. 看 sidecar 怎麼判定的

```powershell
Select-String -Path "$env:LOCALAPPDATA\JavDBMagnet\logs\debug.log*" `
  -Pattern "status=|files_selected="
```

每筆在 `cache_wait_seconds` 內沒等到 `downloaded` 的磁力，都會留下一行
`=== 磁力 [<hash 前 8 碼>] 待處理 (status=<RD 狀態>, files_selected=<True|False>) ===`。關鍵欄位：

| log 訊號 | 意義 |
|---|---|
| `status=magnet_conversion` | RD 還在處理 magnet 資料（最早期） |
| `files_selected=False` | 等待期間連檔案清單都沒出來，還沒選檔（解析中） |
| `status=waiting_files_selection` | RD 已轉好等選檔；sidecar 會在等待期間依 file_pick 自動選檔 |
| `status=downloading` | RD 正在從 BT 下載（要真的等） |

同一段時間附近的 `未快取（<狀態> <進度>%），加入待處理清單` /
`解析中（<狀態>），加入待處理清單稍後重試` 是同一件事的 INFO 行。

### 2. 直接到 RD 後台確認

[real-debrid.com/torrents](https://real-debrid.com/torrents) 看 pending 的 torrent 狀態：

- `Downloading 0%` 持續 10+ 分鐘 → seeder 少，慢
- `Magnet error` → RD 那邊解析失敗（磁力本身有問題）
- `Dead torrent` → 完全沒 seeder，永遠不會完成

### 3. 設定面板看一下

「應用程式設定」展開，確認：

- `cache_wait_seconds`：預設 15，可設 5–300（設定面板擋下範圍外的值，Rust 讀設定時也會夾回這個範圍）。設成 5 這種下限值就太短了
- `min_size_mb` / `file_pick` **不會**造成 pending：smart 策略沒有檔案達門檻時會退回選最大檔（log：`smart 策略：沒有檔案 >= <N>MB，退回選最大檔`）；檔案清單為空時是錯誤（`沒有可選的檔案`），不是 pending

## 修復步驟

### 對未快取磁力（多數情況）

不用改設定，直接等：

1. 看「待處理」表格
2. 5–15 分鐘後按「**全部重試（查 RD）**」
3. 已完成 → 自動移出 pending、產生直連，並自動複製到剪貼簿
4. 還在下載 → 待處理表格的「RD 狀態」「進度」欄更新為 RD 端最新值

如果 30 分鐘還是 `downloading 0%`，那磁力大概率沒 seeder，到 RD 後台刪掉是合理動作。

### cache_wait 太短

「應用程式設定」把 `cache_wait_seconds` 設回 15（或 20）。

## 預防

- `cache_wait_seconds = 15` 是合理預設；除非你在掃大量已知熱門磁力（全已快取），否則不要往下調
- 看到 1–2 筆 pending 是正常的；全部 pending 才需要懷疑
- 對「dn= 帶冷門番號 + 沒人下過」這類磁力，pending 是正常結果而非 bug
