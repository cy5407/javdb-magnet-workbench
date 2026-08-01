# verify-windows-build.ps1 — Windows 建置前後的驗證關卡
#
# 這支腳本**不打包**。打包是 scripts\build-release.ps1 的工作，那條 pipeline
# 已經完整。這支補的是它沒做、而從 Linux 移植過來時最容易出事的部分：
#
#   1. 環境是否齊全（Python / Node / Rust / venv），缺什麼直接講清楚
#   2. 三個既有 gate 是否通過
#   3. **cargo test --lib** —— 2026-08-01 把 Cargo.toml 的 keyring 相依按平台
#      拆開了，那個改動只在 Linux 上驗過。若這一步失敗，把該檔的三段
#      `[target.'cfg(...)'.dependencies]` 還原成原本的單行 keyring 即可，
#      其餘變更不受影響。
#   4. 重建 sidecar.exe，並**實際用 JSON-lines 協定跟它對話**，確認
#      PyInstaller 真的把新模組打包進去了（`rd_outcome_log` 是 2026-08-01
#      新增的頂層模組）。只檢查檔案存在是不夠的——它可以存在卻少了模組。
#
# 先跑這支，全綠再跑 build-release.ps1。
#
# Run:
#     pwsh -File scripts\verify-windows-build.ps1
#     pwsh -File scripts\verify-windows-build.ps1 -SkipSlow   # 略過 cargo 與 sidecar 重建

param(
    [switch]$SkipSlow
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ScriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot    = Split-Path -Parent $ScriptDir
$AppDir      = Join-Path $RepoRoot "app"
$TauriSrcDir = Join-Path $AppDir "src-tauri"
$BinariesDir = Join-Path $TauriSrcDir "binaries"
$SidecarExe  = Join-Path $BinariesDir "sidecar-x86_64-pc-windows-msvc.exe"

$script:Failures = @()
$script:Warnings = @()

function Step($title) {
    Write-Output ""
    Write-Output "==> $title"
}
function Ok($msg)   { Write-Output "    [OK]   $msg" }
function Warn($msg) {
    Write-Output "    [WARN] $msg"
    $script:Warnings += $msg
}
function Bad($msg) {
    Write-Output "    [FAIL] $msg"
    $script:Failures += $msg
}

function Get-ToolVersion($exe, $versionArgs) {
    $cmd = Get-Command $exe -ErrorAction SilentlyContinue
    if (-not $cmd) { return $null }
    try { return (& $exe @versionArgs 2>&1 | Select-Object -First 1) } catch { return "?" }
}

# ---------------------------------------------------------------------------
# 0. 環境
# ---------------------------------------------------------------------------
Step "Checking toolchain"

$py = $null
$VenvPy = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (Test-Path $VenvPy) {
    $py = $VenvPy
    Ok ("venv python: " + (& $py --version 2>&1))
} else {
    Warn "找不到 .venv\Scripts\python.exe —— 將改用 PATH 上的 python"
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $py = "python"
        Ok ("system python: " + (& python --version 2>&1))
    } else {
        Bad "PATH 上也沒有 python。安裝 Python 3.12+ 後重跑"
    }
}

foreach ($t in @(
    @{ Name = "node";  Args = @("--version") },
    @{ Name = "npm";   Args = @("--version") },
    @{ Name = "cargo"; Args = @("--version") },
    @{ Name = "rustc"; Args = @("--version") }
)) {
    $v = Get-ToolVersion $t.Name $t.Args
    if ($null -eq $v) { Bad ($t.Name + " 不在 PATH 上") } else { Ok ($t.Name + ": " + $v) }
}

if ($script:Failures.Count -gt 0) {
    Write-Output ""
    Write-Output "[STOP] 環境不完整，先補齊上面標 FAIL 的工具"
    exit 1
}

# sidecar 打包需要的 Python 套件（與 app 的執行期相依不同）
Step "Checking sidecar build deps"
$probe = @'
import importlib, sys
missing = [m for m in ("PyInstaller", "curl_cffi", "requests", "bs4")
           if importlib.util.find_spec(m) is None]
print(",".join(missing))
'@
$missing = (& $py -c $probe 2>&1 | Select-Object -Last 1)
if ($missing) {
    Warn ("缺少: " + $missing + " —— 執行: " + $py + " -m pip install -r requirements-sidecar.txt")
} else {
    Ok "PyInstaller / curl_cffi / requests / bs4 都在"
}

# ---------------------------------------------------------------------------
# 1-3. 既有 gate
# ---------------------------------------------------------------------------
Step "Gate: pytest"
Push-Location $RepoRoot
try {
    & $py -m pytest tests/ -q
    if ($LASTEXITCODE -ne 0) { Bad "pytest 失敗" } else { Ok "pytest 通過" }
} finally { Pop-Location }

Push-Location $AppDir
try {
    if (-not (Test-Path (Join-Path $AppDir "node_modules"))) {
        Step "Installing npm deps (node_modules 不存在)"
        & npm ci
        if ($LASTEXITCODE -ne 0) { Bad "npm ci 失敗" }
    }

    Step "Gate: vitest"
    & npx vitest run
    if ($LASTEXITCODE -ne 0) { Bad "vitest 失敗" } else { Ok "vitest 通過" }

    Step "Gate: svelte-check"
    & npm run check
    if ($LASTEXITCODE -ne 0) { Bad "svelte-check 有 error/warning（本專案要求 0/0）" }
    else { Ok "svelte-check 0 errors 0 warnings" }
} finally { Pop-Location }

# ---------------------------------------------------------------------------
# 4. cargo test —— 這是本次移植最高風險的一步
# ---------------------------------------------------------------------------
if ($SkipSlow) {
    Warn "-SkipSlow：略過 cargo test 與 sidecar 重建"
} else {
    Step "Gate: cargo test --lib  (驗 2026-08-01 的 keyring 平台拆分)"
    if (-not (Test-Path $SidecarExe)) {
        Warn "binaries\sidecar-*.exe 尚不存在；Tauri build script 需要它，先跑 sidecar 建置"
        Push-Location $AppDir
        try {
            & npm run sidecar:build
            if ($LASTEXITCODE -ne 0) { Bad "npm run sidecar:build 失敗" }
        } finally { Pop-Location }
    }
    Push-Location $TauriSrcDir
    try {
        & cargo test --lib
        if ($LASTEXITCODE -ne 0) {
            Bad @"
cargo test --lib 失敗。
若錯誤來自 keyring / secret-service / windows-native，八成是 2026-08-01 的
平台拆分在 Windows 上不成立。修法：把 app/src-tauri/Cargo.toml 末尾那三段
[target.'cfg(...)'.dependencies] 刪掉，改回 [dependencies] 內的單行：
  keyring = { version = "3", features = ["windows-native", "apple-native", "linux-native-async-persistent"] }
其餘所有變更與此無關，不必回退。
細節見 docs/platform/linux-support.md 第 1 節。
"@
        } else { Ok "cargo test --lib 通過" }
    } finally { Pop-Location }
}

# ---------------------------------------------------------------------------
# 5. sidecar 重建 + 協定實證
# ---------------------------------------------------------------------------
if (-not $SkipSlow) {
    Step "Rebuilding sidecar.exe"
    Push-Location $AppDir
    try {
        & npm run sidecar:build
        if ($LASTEXITCODE -ne 0) { Bad "npm run sidecar:build 失敗" }
    } finally { Pop-Location }

    if (-not (Test-Path $SidecarExe)) {
        Bad ("sidecar.exe 沒產生在 " + $SidecarExe)
    } else {
        $size = [math]::Round((Get-Item $SidecarExe).Length / 1MB, 1)
        Ok ("sidecar.exe 產生, " + $size + " MB")

        # 檔案存在不代表模組打包進去了。用真的協定跟它講話，並確認
        # rd_outcome_log 有作用（會產生 rd_outcomes.jsonl）。
        Step "Smoke: 用 JSON-lines 協定實跑 sidecar.exe"
        $tmpLog = Join-Path ([System.IO.Path]::GetTempPath()) ("javdb-verify-" + [guid]::NewGuid().ToString("N"))
        New-Item -ItemType Directory -Force -Path $tmpLog | Out-Null
        $prevLogDir = $env:JAVDB_LOG_DIR
        $env:JAVDB_LOG_DIR = $tmpLog
        try {
            $magnet = "magnet:?xt=urn:btih:0201592fdeadbeef0201592fdeadbeef02015920&dn=VERIFY-001"
            $lines = @(
                '{"cmd":"hello","request_id":"h0","protocol_version":1}',
                ('{"cmd":"register_magnets","request_id":"r1","magnets":["' + $magnet + '"]}'),
                '{"cmd":"shutdown","request_id":"s1"}'
            ) -join "`n"
            $out = $lines | & $SidecarExe --daemon 2>&1

            if ($out -match '"ok":\s*true' -and $out -match 'handle_id') {
                Ok "協定往返正常（hello / register_magnets / shutdown）"
            } else {
                Bad ("sidecar.exe 沒有正確回應協定。輸出前 300 字: " + ($out -join " ").Substring(0, [Math]::Min(300, ($out -join " ").Length)))
            }

            # debug.log 一定要有；rd_outcomes.jsonl 只在有送 RD 時才寫，
            # 但 rd_outcome_log.configure() 會在啟動時就把檔案建出來。
            if (Test-Path (Join-Path $tmpLog "debug.log")) {
                Ok "logging 落地正常（debug.log）"
            } else {
                Bad "沒有產生 debug.log —— app_logging 沒被打包，或 JAVDB_LOG_DIR 沒生效"
            }
            if (Test-Path (Join-Path $tmpLog "rd_outcomes.jsonl")) {
                Ok "rd_outcome_log 已打包並初始化（rd_outcomes.jsonl）"
            } else {
                Bad @"
沒有產生 rd_outcomes.jsonl —— rd_outcome_log 很可能沒被 PyInstaller 打包進去。
確認 spikes/pyinstaller_sidecar/build_sidecar.py 的 --hidden-import 清單含
rd_outcome_log，然後刪掉 spikes/pyinstaller_sidecar/build/ 重建。
"@
            }

            # 落地檔案不得觸發既有的 redaction gate
            $hit = Get-ChildItem $tmpLog -File -Recurse |
                Select-String -Pattern 'magnet:\?xt|urn:btih' -ErrorAction SilentlyContinue
            if ($hit) {
                Bad ("log 目錄觸發了 redaction gate: " + ($hit | Select-Object -First 1))
            } else {
                Ok "redaction gate 乾淨（logs 內無完整 magnet / BTIH marker）"
            }
        } finally {
            $env:JAVDB_LOG_DIR = $prevLogDir
            Remove-Item $tmpLog -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

# ---------------------------------------------------------------------------
# 總結
# ---------------------------------------------------------------------------
Write-Output ""
Write-Output "======================================================"
if ($script:Warnings.Count -gt 0) {
    Write-Output ("警告 " + $script:Warnings.Count + " 項：")
    $script:Warnings | ForEach-Object { Write-Output ("  - " + $_) }
}
if ($script:Failures.Count -gt 0) {
    Write-Output ("失敗 " + $script:Failures.Count + " 項：")
    $script:Failures | ForEach-Object { Write-Output ("  - " + $_) }
    Write-Output ""
    Write-Output "[FAIL] 先修上面的問題，不要進 build-release.ps1"
    exit 1
}
Write-Output "[PASS] 全部通過。可以跑： pwsh -File scripts\build-release.ps1"
Write-Output "======================================================"
exit 0
