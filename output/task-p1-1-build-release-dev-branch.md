# Task: P1.1 — 修 build-release.ps1 origin/dev → origin/master + git error fatal

## 修改範圍

只允許修改：
- `scripts/build-release.ps1`

**禁止**修改其他檔。**禁止** `git commit` / `add` / `push` / `reset` / `checkout` / `stash`。

## 問題

`scripts/build-release.ps1` 的「Step 6 source-secret-scan」依賴 `git diff origin/dev..HEAD` 抓 committed diff 掃 token / magnet / cookie 字串。但本 repo default branch 是 `master`，`origin/dev` **不存在**。

結果：git fatal → try/catch（依 PowerShell 版本捕獲行為不一）→ 即便 catch 觸發只 `Write-Warning` 然後 fall through 用 `git diff --name-only`（工作樹 diff，**已 commit 的改動完全不會被掃**）。這條 defense-in-depth always no-op。

## 要做的兩件事

### A. Line 18 + Line 308：origin/dev → 動態偵測 default remote branch

定位這兩處：

**Line 18（comment）**：
```powershell
#   6. Source diff secret scan   (same patterns over `git diff origin/dev..HEAD`
```

**Line 308（實際 git 呼叫）**：
```powershell
$sourceFiles += (& git -C $RepoRoot diff --name-only origin/dev..HEAD)
```

改法：

**推薦做法**——用 `git symbolic-ref` 動態拿 default remote branch（適應未來 default branch 變動）：

在 line 308 上方加：
```powershell
    $defaultBranch = (& git -C $RepoRoot symbolic-ref --short refs/remotes/origin/HEAD 2>$null)
    if (-not $defaultBranch) {
        $defaultBranch = "origin/master"  # fallback
    }
```

然後 line 308 改為：
```powershell
    $sourceFiles += (& git -C $RepoRoot diff --name-only "$defaultBranch..HEAD")
```

Line 18 comment 同步改：
```powershell
#   6. Source diff secret scan   (same patterns over `git diff <origin/HEAD>..HEAD`
```

### B. git exit non-zero 視為 fatal（不要 fall through 到工作樹 diff）

定位現有 try/catch 區段（line 308 上下）。原邏輯應該類似：

```powershell
try {
    $sourceFiles += (& git -C $RepoRoot diff --name-only origin/dev..HEAD)
} catch {
    Write-Warning "..."
    $sourceFiles += (& git -C $RepoRoot diff --name-only)  # ← 退回工作樹 diff
}
```

改成**檢查 `$LASTEXITCODE` 並 FailExit**：

```powershell
$diffOutput = & git -C $RepoRoot diff --name-only "$defaultBranch..HEAD"
if ($LASTEXITCODE -ne 0) {
    Write-Error "FATAL: source-secret-scan git diff failed (exit $LASTEXITCODE). Refusing to ship a release without committed-diff scan."
    exit 1
}
$sourceFiles += $diffOutput
```

不允許 Write-Warning 後 fall through，這條 scan 失敗就應該擋住 release。

### C. 嚴格不做的事

- 不要動 Step 1-5、Step 7+ 其他 phase
- 不要動 RUSTFLAGS / SHA256SUMS / manifest 邏輯
- 不要動 binary regex scan（Step 6 後半）
- 不要 reformat 整支 ps1
- 不要新增 `Write-Warning` / `Write-Host` 美化訊息

## 驗證

完成後 `scripts/build-release.ps1` 應該：

1. PowerShell parse OK（沒 syntax error）
2. Line 308 附近含 `symbolic-ref` 或對應的 default branch 偵測
3. Line 308 附近含 `$LASTEXITCODE -ne 0` 的 fatal check
4. 不再含字串 `origin/dev`

不需要實際跑 `pwsh ./scripts/build-release.ps1` —— reviewer 後續手動 dry-run 驗。

## 範圍提醒

只動 `scripts/build-release.ps1`、0 commit。
