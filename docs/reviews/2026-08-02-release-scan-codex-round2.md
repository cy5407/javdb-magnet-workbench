# Codex review 紀錄 — release 機密掃描

外部審查對 07d9b93 提出 7 項（含一個 release blocker）。修正後以 Codex 複審。

## 第 2 輪：`codex review --commit 3f55ec0`

執行於 2026-08-02 17:1x。Codex 提出兩項，兩項皆成立並已修正於後續 commit：

Full review comments:

- [P0] Return source-scan metrics from the function — /home/cy5407/javdb-magnet-workbench/scripts/build-release.ps1:305-308
  On every normal release, these assignments create function-local variables in PowerShell. Once `Invoke-SourceSecretScan` returns, `$SourceHits`, `$SourceEligible`, `$SourceScanned`, and `$SourceAllowed` are undefined, so `Set-StrictMode` aborts while constructing the manifest after the expensive build and hashing steps; return the metrics or assign them explicitly in script scope.

- [P2] Decode BOM-marked UTF-16BE source files — /home/cy5407/javdb-magnet-workbench/scripts/build-release.ps1:152-155
  When a tracked text file is UTF-16BE, both configured decoders produce interleaved or byte-swapped text, so an embedded ASCII credential never reaches the regexes as a contiguous string. The previous `Get-Content` path recognized the UTF-16BE BOM, making this a regression in the promised all-text-files scan; use BOM-aware decoding or include `BigEndianUnicode`.

### 我的處置

- **P0**：與先前 `$ManifestPath` 同類——重構改變了變數綁定。四個計數改為
  `$script:` 作用域，並以 pwsh 實證函式內賦值於呼叫後不可見。
- **P2**：`$Encodings` 補上 `BigEndianUnicode`。改讀 raw bytes 雖修掉無 BOM
  UTF-16LE 的洞，卻失去 `Get-Content` 免費提供的 BOM 偵測。

兩項都新增了對應的 Red 測試，見 `scripts/test-release-scan.ps1`。

> 本檔只保留 Codex 的 findings 正文。原始 stdout 另含 Codex 自身執行的
> audit-log dump，屬雜訊且會觸發 release 機密掃描，故不收錄。
