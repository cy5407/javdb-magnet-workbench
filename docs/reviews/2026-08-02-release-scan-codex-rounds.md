# Codex 審查紀錄 — release 機密掃描

外部審查對 `07d9b93` 提出 7 項（含一個必定失敗的 release blocker）。修正後交由
`codex review` 反覆複審，直到雙方皆無異議。每一輪的 findings 都獨立重現後才修。

## 逐輪結果

| 輪次 | 命令 | findings |
|---|---|---|
| 2 | `codex review --base 07d9b93` | 2 |
| 4 | `codex review --base 07d9b93` | 2 |
| 5 | `codex review --base 07d9b93` | 2 |
| 6 | `codex review --base 07d9b93` | 2 |
| 7 | `codex review --base 07d9b93` | 3 |
| 8 | `codex review --base 07d9b93` | 1 |
| 9 | `codex review --base 07d9b93` | 1 |
| 10 | `codex review --base 07d9b93` | 0 |

## 各輪 findings 摘要

### 第 2 輪 —— 2 項
- [P0] Return source-scan metrics from the function — /home/cy5407/javdb-magnet-workbench/scripts/build-release.ps1:305-308
- [P2] Decode BOM-marked UTF-16BE source files — /home/cy5407/javdb-magnet-workbench/scripts/build-release.ps1:152-155

### 第 4 輪 —— 2 項
- [P0] Exclude the built-in cookie template from binary matches — /home/cy5407/javdb-magnet-workbench/scripts/build-release.ps1:124-127
- [P2] Deduplicate raw and percent-decoded scan variants — /home/cy5407/javdb-magnet-workbench/scripts/build-release.ps1:358-360

### 第 5 輪 —— 2 項
- [P0] Define the allowlist before scanning binaries — /home/cy5407/javdb-magnet-workbench/scripts/build-release.ps1:637-637
- [P2] Match complete cookie values before allowlisting — /home/cy5407/javdb-magnet-workbench/scripts/build-release.ps1:636-637

### 第 6 輪 —— 2 項
- [P2] Decode UTF-32 tracked text before scanning — /home/cy5407/javdb-magnet-workbench/scripts/build-release.ps1:285-292
- [P2] Validate the full binary value before allowlisting — /home/cy5407/javdb-magnet-workbench/scripts/build-release.ps1:665-666

### 第 7 輪 —— 3 項
- [P0] Return source-scan metrics from the function — /home/cy5407/javdb-magnet-workbench/scripts/build-release.ps1:305-308
- [P1] Stop cookie matches at binary string boundaries — /home/cy5407/javdb-magnet-workbench/scripts/build-release.ps1:136-136
- [P2] Decode BOM-marked UTF-16BE source files — /home/cy5407/javdb-magnet-workbench/scripts/build-release.ps1:152-155

### 第 8 輪 —— 1 項
- [P2] Avoid truncating binary cookie values before allowlisting — /home/cy5407/javdb-magnet-workbench/scripts/build-release.ps1:195-198

### 第 9 輪 —— 1 項
- [P1] Preserve accepted control bytes in binary cookie matches — /home/cy5407/javdb-magnet-workbench/scripts/build-release.ps1:200-200

### 第 10 輪 —— 無 項
（無異議）

## 收斂點

第 10 輪 findings 為 0。掃描的所有路徑都有可執行的紅測覆蓋：
`scripts/test-release-scan.ps1` 29 PASS / 0 FAIL（pwsh 7.6.4）。

> 本檔只記 findings 標題與輪次。完整正文含 Codex 自身執行的 audit-log dump，
> 屬雜訊且會觸發 release 機密掃描，故不收錄。
