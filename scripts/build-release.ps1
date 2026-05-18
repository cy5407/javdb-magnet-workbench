# build-release.ps1 — portable release pipeline
#
# Produces a portable ZIP that ships javdbmagnet.exe + sidecar.exe in a
# single folder. End-users extract the zip and double-click the exe —
# no installer, no Program Files, no Start Menu entry, no registry.
#
# Pipeline:
#   1. Build sidecar.exe         (npm run sidecar:build → app/src-tauri/binaries/...)
#   2. Build frontend + Rust exe (npx tauri build --no-bundle from app/)
#                                 — single CLI call enables the
#                                 `tauri/custom-protocol` feature so the
#                                 release binary embeds dist/ instead of
#                                 reaching for the dev server
#   3. Stage release/JavDBMagnet/ (javdbmagnet.exe + sidecar.exe + README.txt)
#   4. Audit staging dir         (whitelist: exe + exe + README.txt; nothing else)
#   5. Binary content scan       (tokens / magnets / Cloudflare cookies must NOT
#                                 appear in either exe)
#   6. Source diff secret scan   (same patterns over `git diff <origin/HEAD>..HEAD`
#                                 + working-tree diff)
#   7. Compress-Archive → release/JavDBMagnet_<version>_portable.zip
#   8. SHA256 for zip + 2 exes  → release/SHA256SUMS.txt
#   9. Write release/release-manifest.json
#  10. Print final paths
#
# Any audit / scan failure → exit 1. Half-baked staging stays for inspection.
#
# Code signing is NOT performed. $env:SIGN -eq "1" emits a placeholder
# warning; wire signtool / osslsigncode here once a cert exists.
#
# Run:
#     pwsh -File scripts\build-release.ps1
# Or from app/:
#     npm run release

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
$ScriptDir     = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot      = Split-Path -Parent $ScriptDir
$AppDir        = Join-Path $RepoRoot "app"
$TauriSrcDir   = Join-Path $AppDir "src-tauri"
$CargoOutDir   = Join-Path $TauriSrcDir "target\release"
$BinariesDir   = Join-Path $TauriSrcDir "binaries"
$ReleaseOutDir = Join-Path $RepoRoot "release"

# Sidecar artifact path produced by build_sidecar.py
$SidecarSource = Join-Path $BinariesDir "sidecar-x86_64-pc-windows-msvc.exe"

# Read version straight from app/package.json so the zip name follows it.
$PkgJsonPath = Join-Path $AppDir "package.json"
$pkgJson = Get-Content $PkgJsonPath -Raw | ConvertFrom-Json
$Version = $pkgJson.version
$PortableFolderName = "JavDBMagnet"
$StagingDir = Join-Path $ReleaseOutDir $PortableFolderName
$ZipName    = "JavDBMagnet_${Version}_portable.zip"
$ZipPath    = Join-Path $ReleaseOutDir $ZipName

function Step($title) {
    Write-Output ""
    Write-Output "==> $title"
}
function Ok($msg)   { Write-Output "    [OK]   $msg" }
function Warn($msg) { Write-Output "    [WARN] $msg" }
function FailExit($msg) {
    Write-Output ""
    Write-Output "[FAIL] $msg"
    exit 1
}
function Get-Sha256Hex($path) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $stream = [System.IO.File]::OpenRead($path)
        try {
            $hash = $sha.ComputeHash($stream)
            return (($hash | ForEach-Object { $_.ToString("x2") }) -join "").ToUpperInvariant()
        } finally {
            $stream.Dispose()
        }
    } finally {
        $sha.Dispose()
    }
}

# ---------------------------------------------------------------------------
# Step 0: Prepare release/ output dir
# ---------------------------------------------------------------------------
Step "Preparing release output directory"
if (-not (Test-Path $ReleaseOutDir)) { New-Item -ItemType Directory -Force -Path $ReleaseOutDir | Out-Null }
# Clean previous run's artifacts under release/ (zip, sums, manifest, staging).
# We do NOT touch anything outside release/.
Get-ChildItem -Path $ReleaseOutDir -File -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Extension -in @(".zip", ".msi", ".exe") `
            -or $_.Name -eq "SHA256SUMS.txt" `
            -or $_.Name -eq "release-manifest.json"
    } |
    Remove-Item -Force
if (Test-Path $StagingDir) { Remove-Item $StagingDir -Recurse -Force }
Ok ("Output dir: " + $ReleaseOutDir)

# ---------------------------------------------------------------------------
# Step 1: Build sidecar.exe via PyInstaller
# ---------------------------------------------------------------------------
Step "Building sidecar.exe (npm run sidecar:build)"
Push-Location $AppDir
try {
    & npm run sidecar:build
    if ($LASTEXITCODE -ne 0) { FailExit "npm run sidecar:build exited with code $LASTEXITCODE" }
} finally {
    Pop-Location
}
if (-not (Test-Path $SidecarSource)) {
    FailExit "sidecar.exe not produced at expected path: $SidecarSource"
}
Ok ("sidecar.exe at " + $SidecarSource)

# ---------------------------------------------------------------------------
# Step 2 + 3: Build frontend + Rust release exe via Tauri CLI.
#
# Plain `cargo build --release` doesn't pass the `tauri/custom-protocol`
# feature flag, so the resulting binary still tries to load from
# devUrl (http://localhost:1420) instead of the embedded dist/. Going
# through `tauri build --no-bundle` handles three things in one call:
#   - runs beforeBuildCommand (= `npm run build`) for fresh dist/
#   - enables tauri/custom-protocol so the release binary loads from
#     embedded assets
#   - skips MSI / NSIS bundling so no installer artifacts leak in
# ---------------------------------------------------------------------------
Step "Building Rust release binary (npx tauri build --no-bundle)"
# Scrub the build-host user path out of the binary. Rust's `file!()`
# macro and panic strings bake the absolute path of every compiled
# source file into the output, so without remapping the user's
# Windows username + .cargo / project layout would be visible to
# anyone strings(1)-ing the exe. `--remap-path-prefix` rewrites
# those embedded paths at compile time. Three remaps cover the
# usual suspects:
#   - %USERPROFILE%\.cargo  → ~/.cargo            (dependency crates)
#   - %USERPROFILE%\.rustup → ~/.rustup           (stdlib sources)
#   - <repo root>           → <project>           (this project's own files)
# Note: changing RUSTFLAGS invalidates the entire build cache, so
# the first run after toggling this is a full cold compile
# (~3-5 min on a warm dependency tree).
$remapFlags = @(
    "--remap-path-prefix=$($env:USERPROFILE)\.cargo=~/.cargo",
    "--remap-path-prefix=$($env:USERPROFILE)\.rustup=~/.rustup",
    "--remap-path-prefix=$RepoRoot=<project>"
) -join ' '
Ok ("RUSTFLAGS scrub: " + $remapFlags)
$prevRustflags = $env:RUSTFLAGS
$env:RUSTFLAGS = if ($prevRustflags) { "$prevRustflags $remapFlags" } else { $remapFlags }
Push-Location $AppDir
try {
    & npx tauri build --no-bundle
    if ($LASTEXITCODE -ne 0) { FailExit "tauri build exited with code $LASTEXITCODE" }
} finally {
    Pop-Location
    # Restore prior RUSTFLAGS so subsequent processes (other cargo
    # invocations in this shell session) aren't sticky-configured.
    $env:RUSTFLAGS = $prevRustflags
}
$MainExeSource = Join-Path $CargoOutDir "javdbmagnet.exe"
if (-not (Test-Path $MainExeSource)) { FailExit "javdbmagnet.exe missing: $MainExeSource" }
Ok ("javdbmagnet.exe at " + $MainExeSource)

# ---------------------------------------------------------------------------
# Step 4: Stage portable folder under release/JavDBMagnet/
# ---------------------------------------------------------------------------
Step "Staging portable folder"
New-Item -ItemType Directory -Force -Path $StagingDir | Out-Null

Copy-Item -LiteralPath $MainExeSource -Destination (Join-Path $StagingDir "javdbmagnet.exe") -Force
# Sidecar is named with target-triple in build/output; rename to plain
# sidecar.exe so users see one clear sibling file.
Copy-Item -LiteralPath $SidecarSource -Destination (Join-Path $StagingDir "sidecar.exe") -Force

$ReadmeContent = @"
JavDBMagnet $Version — Portable Edition
=======================================

USAGE
-----
雙擊 javdbmagnet.exe 即可啟動。**請保留 sidecar.exe 在同一個資料夾**，
它是 JavDB / Real-Debrid HTTP sidecar，缺一不可。

DATA LOCATIONS
--------------
Settings / cookies / pending:  %APPDATA%\JavDBMagnet\
Logs:                          %LOCALAPPDATA%\JavDBMagnet\logs\
RD API token:                  Windows Credential Manager (target: JavDBMagnet/RD_API_TOKEN)

REMOVAL
-------
- 刪除這個 JavDBMagnet 資料夾即可移除程式本體（不會留 registry 殘渣）
- 想清掉個人資料：
    rmdir /s /q %APPDATA%\JavDBMagnet
    rmdir /s /q %LOCALAPPDATA%\JavDBMagnet
    cmdkey /delete:JavDBMagnet/RD_API_TOKEN

SMARTSCREEN
-----------
首次啟動可能跳 SmartScreen 警告（未做 code signing）。比對 SHA256 後
按「更多資訊 → 仍要執行」即可。

詳見 repo 內 README.md / docs/troubleshooting/。
"@
Set-Content -Path (Join-Path $StagingDir "README.txt") -Value $ReadmeContent -Encoding utf8

$StagedFiles = Get-ChildItem $StagingDir -Recurse -File | Select-Object FullName, Length
Write-Host "    Staged files (" $StagedFiles.Count "):" -ForegroundColor Gray
$StagedFiles | ForEach-Object {
    $rel = $_.FullName.Substring($StagingDir.Length).TrimStart('\','/')
    Write-Host ("      {0,10} bytes  {1}" -f $_.Length, $rel) -ForegroundColor Gray
}

# ---------------------------------------------------------------------------
# Step 5: Audit staging folder — strict whitelist
# ---------------------------------------------------------------------------
Step "Auditing portable folder (whitelist)"
$AllowedNames = @('javdbmagnet.exe', 'sidecar.exe', 'README.txt')
$StagingViolations = @()
foreach ($f in $StagedFiles) {
    $rel = $f.FullName.Substring($StagingDir.Length).TrimStart('\','/')
    # No subdirectories allowed.
    if ($rel -match '[\\/]') {
        $StagingViolations += "subdir entry: $rel"
        continue
    }
    if ($AllowedNames -notcontains (Split-Path $f.FullName -Leaf)) {
        $StagingViolations += "unexpected file: $rel"
    }
}
# Explicitly verify none of the forbidden names slipped in even if the
# whitelist somehow expanded.
$ForbiddenNames = @('.env','.gitignore','cookies.txt','pending_torrents.json','magnet.txt')
foreach ($f in $StagedFiles) {
    $name = Split-Path $f.FullName -Leaf
    if ($ForbiddenNames -contains $name) { $StagingViolations += "forbidden: $name" }
    if ($name -like '.env.*' -or $name -like '*.log' -or $name -like '*.token' -or $name -like '*.spec') {
        $StagingViolations += "forbidden pattern: $name"
    }
}
if ($StagingViolations.Count -gt 0) {
    Write-Host "    Staging violations:" -ForegroundColor Red
    $StagingViolations | ForEach-Object { Write-Host ("      " + $_) -ForegroundColor Red }
    FailExit "Portable folder audit failed"
}
Ok "Portable folder contains only allowed artifacts"

# ---------------------------------------------------------------------------
# Step 6: Binary content scan — secrets must NOT be baked in
# ---------------------------------------------------------------------------
Step "Binary content scan for embedded secrets"
$ScanTargets = @(
    (Join-Path $StagingDir "javdbmagnet.exe"),
    (Join-Path $StagingDir "sidecar.exe")
)

$Patterns = @(
    @{ name = 'urn:btih:<40hex>';            rx = 'urn:btih:[a-fA-F0-9]{40}' },
    @{ name = 'magnet:?xt=urn:btih:';        rx = 'magnet:\?xt=urn:btih:' + '[a-fA-F0-9]+' },
    @{ name = 'Cloudflare clearance cookie'; rx = 'cf' + '_clearance=' + '[A-Za-z0-9_.-]{20,}' },
    @{ name = 'Cloudflare bot cookie';       rx = '__cf' + '_bm=' + '[A-Za-z0-9_.-]{20,}' },
    @{ name = 'JavDB session cookie';        rx = '_jdb' + '_session=' + '[A-Za-z0-9_.-]{10,}' },
    @{ name = 'remember_me_token=';          rx = 'remember_me_token=[A-Za-z0-9_.-]{10,}' },
    @{ name = 'Authorization bearer header'; rx = 'Authorization:\s*' + 'Bearer\s+' + '[A-Za-z0-9_-]{20,}' },
    @{ name = 'Bearer <30+ char token>';     rx = 'Bearer ' + '[A-Za-z0-9_-]{30,}' },
    @{ name = 'RD_API_TOKEN=<value>';        rx = 'RD_API' + '_TOKEN=' + '[A-Za-z0-9_-]{20,}' }
)

$ScanFail = $false
$BinaryHitCount = 0
# We decode the binary bytes both as ASCII *and* UTF-16LE because PE
# images routinely embed strings in both encodings:
#   - ASCII / UTF-8 covers Rust &str literals, format!() output, and
#     anything wired through libc-style APIs.
#   - UTF-16LE covers strings handed to the Win32 wide API (e.g. a
#     `let path = format!("HKCU\\...\\{}", token);` later passed to
#     `RegOpenKeyExW`), which would otherwise sail past an ASCII-only
#     scan even though the secret material is plainly readable in a
#     hex dump.
# Running both passes is cheap (two regex sweeps over the same byte
# blob); failing to do it would silently halve the scan's coverage.
$Encodings = @(
    @{ label = 'ASCII';      encoding = [System.Text.Encoding]::ASCII },
    @{ label = 'UTF-16LE';   encoding = [System.Text.Encoding]::Unicode }
)
foreach ($exe in $ScanTargets) {
    $name = Split-Path $exe -Leaf
    $bytes = [System.IO.File]::ReadAllBytes($exe)
    $hits = @()
    foreach ($enc in $Encodings) {
        $text = $enc.encoding.GetString($bytes)
        foreach ($p in $Patterns) {
            $regexMatches = [regex]::Matches($text, $p.rx)
            if ($regexMatches.Count -gt 0) {
                $hits += "      [$($enc.label)] $($p.name)  count=$($regexMatches.Count)"
                $regexMatches | Select-Object -First 1 | ForEach-Object {
                    $sample = $_.Value
                    if ($sample.Length -gt 70) { $sample = $sample.Substring(0,70) + "..." }
                    $hits += "        sample: $sample"
                }
                $BinaryHitCount += $regexMatches.Count
            }
        }
    }
    if ($hits.Count -gt 0) {
        Write-Host "    [$name] LEAK:" -ForegroundColor Red
        $hits | ForEach-Object { Write-Host $_ -ForegroundColor Red }
        $ScanFail = $true
    } else {
        Ok ("[$name] no leak patterns (ASCII + UTF-16LE)")
    }
}
if ($ScanFail) { FailExit "Binary content scan failed" }

# ---------------------------------------------------------------------------
# Step 7: Source diff secret scan — over committed + working-tree diffs
# ---------------------------------------------------------------------------
Step "Source diff secret scan"
$sourceFiles = @()
$defaultBranch = (& git -C $RepoRoot symbolic-ref --short refs/remotes/origin/HEAD 2>$null)
if (-not $defaultBranch) {
    $defaultBranch = "origin/master"  # fallback
}
$diffOutput = & git -C $RepoRoot diff --name-only "$defaultBranch..HEAD"
if ($LASTEXITCODE -ne 0) {
    Write-Error "FATAL: source-secret-scan git diff failed (exit $LASTEXITCODE). Refusing to ship a release without committed-diff scan."
    exit 1
}
$sourceFiles += $diffOutput
$sourceFiles += (& git -C $RepoRoot diff --name-only)
$sourceFiles = $sourceFiles |
    Where-Object { $_ -and (Test-Path (Join-Path $RepoRoot $_) -PathType Leaf) } |
    Sort-Object -Unique
$skipExt = @('.exe', '.msi', '.zip', '.7z', '.png', '.ico', '.icns', '.dll')
# Files / paths whose job is to CONTAIN the patterns we're scanning for:
#   - legacy_import.rs has secret-bearing test fixtures inline
#   - build-release.ps1 has the regex literals themselves
#   - tests/        Python unittest fixtures (BTIH hex sentinels, etc.)
#   - *.test.ts     Vitest fixtures (redacted magnet samples)
# Skipping by exact path for the two one-offs and by prefix/suffix for
# the test directories keeps the rule resilient to new test files.
$skipFiles = @(
    'app/src-tauri/src/legacy_import.rs',
    'scripts/build-release.ps1'
)
$skipPrefixes = @('tests/')
$skipSuffixes = @('.test.ts', '.test.js', '.test.tsx', '.spec.ts')
$SourceHits = @()
foreach ($rel in $sourceFiles) {
    if ($skipFiles -contains $rel) { continue }
    $relForward = $rel.Replace('\', '/')
    $skipThis = $false
    foreach ($p in $skipPrefixes) { if ($relForward.StartsWith($p)) { $skipThis = $true; break } }
    if ($skipThis) { continue }
    foreach ($s in $skipSuffixes) { if ($relForward.EndsWith($s)) { $skipThis = $true; break } }
    if ($skipThis) { continue }
    $full = Join-Path $RepoRoot $rel
    if ($skipExt -contains ([System.IO.Path]::GetExtension($full).ToLowerInvariant())) { continue }
    $text = Get-Content -LiteralPath $full -Raw -ErrorAction SilentlyContinue
    if ($null -eq $text) { continue }
    foreach ($p in $Patterns) {
        $regexMatches = [regex]::Matches($text, $p.rx)
        if ($regexMatches.Count -gt 0) {
            $SourceHits += [pscustomobject]@{
                File = $rel
                Pattern = $p.name
                Count = $regexMatches.Count
            }
        }
    }
}
if ($SourceHits.Count -gt 0) {
    Write-Host "    SOURCE secret pattern hits:" -ForegroundColor Red
    $SourceHits | ForEach-Object {
        Write-Host ("      {0}  {1}  count={2}" -f $_.File, $_.Pattern, $_.Count) -ForegroundColor Red
    }
    FailExit "Source secret scan failed"
}
Ok "No source secret patterns in changed files"

# ---------------------------------------------------------------------------
# Step 8: Compress staging dir to release/JavDBMagnet_<v>_portable.zip
# ---------------------------------------------------------------------------
Step "Creating portable zip"
if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
# Pass the directory itself (not its contents) so the zip root is
# "JavDBMagnet/<files>", matching the spec.
Compress-Archive -Path $StagingDir -DestinationPath $ZipPath -CompressionLevel Optimal
if (-not (Test-Path $ZipPath)) { FailExit "Compress-Archive did not produce $ZipPath" }
Ok ("Wrote " + $ZipPath)

# ---------------------------------------------------------------------------
# Step 9: SHA256 for zip + 2 exes
# ---------------------------------------------------------------------------
Step "Computing SHA256"
$HashTargets = @(
    @{ label = "portable.zip"; path = $ZipPath },
    @{ label = "exe.app";      path = (Join-Path $StagingDir "javdbmagnet.exe") },
    @{ label = "exe.sidecar";  path = (Join-Path $StagingDir "sidecar.exe") }
)
$Hashes = @{}
foreach ($t in $HashTargets) {
    $h = Get-Sha256Hex $t.path
    $size = (Get-Item $t.path).Length
    $Hashes[$t.label] = @{ path = $t.path; sha256 = $h; bytes = $size }
    Write-Host ("    {0,-13} {1}  ({2:N0} bytes)  {3}" -f $t.label, $h, $size, (Split-Path $t.path -Leaf)) -ForegroundColor Gray
}

# ---------------------------------------------------------------------------
# Step 10: Write SHA256SUMS.txt + manifest
# ---------------------------------------------------------------------------
Step "Writing release manifest"
$SumsPath = Join-Path $ReleaseOutDir "SHA256SUMS.txt"
$sumsLines = $HashTargets | ForEach-Object {
    $h = $Hashes[$_.label]
    "$($h.sha256)  $(Split-Path $h.path -Leaf)"
}
Set-Content -Path $SumsPath -Value $sumsLines -Encoding utf8
Ok ("Wrote " + $SumsPath)

$ManifestPath = Join-Path $ReleaseOutDir "release-manifest.json"
$gitCommit = (& git -C $RepoRoot rev-parse HEAD).Trim()
$manifest = [ordered]@{
    name        = $pkgJson.name
    version     = $Version
    git_commit  = $gitCommit
    built_at    = (Get-Date).ToUniversalTime().ToString("o")
    bundle      = "portable-zip"
    artifacts   = @(
        $HashTargets | ForEach-Object {
            $h = $Hashes[$_.label]
            [ordered]@{
                label      = $_.label
                name       = (Split-Path $h.path -Leaf)
                sha256     = $h.sha256
                size_bytes = $h.bytes
            }
        }
    )
    audit       = @{
        portable_forbidden_files = 0
        binary_secret_hits       = $BinaryHitCount
        source_secret_hits       = $SourceHits.Count
    }
    signing     = @{
        requested = ($env:SIGN -eq "1")
        performed = $false
    }
}
$manifestJson = $manifest | ConvertTo-Json -Depth 6
Set-Content -Path $ManifestPath -Value $manifestJson -Encoding utf8
Ok ("Wrote " + $ManifestPath)

# ---------------------------------------------------------------------------
# Step 11: Final summary
# ---------------------------------------------------------------------------
if ($env:SIGN -eq "1") {
    Warn "SIGN=1 placeholder — code signing is not implemented in this script."
    Warn "Wire your signtool / osslsigncode call here once you have a cert."
}

Write-Host ""
Write-Host "==> RELEASE READY (portable)" -ForegroundColor Green
Write-Host ("    Portable zip   : " + $ZipPath) -ForegroundColor Green
Write-Host ("    javdbmagnet.exe: " + (Join-Path $StagingDir "javdbmagnet.exe")) -ForegroundColor Green
Write-Host ("    sidecar.exe    : " + (Join-Path $StagingDir "sidecar.exe")) -ForegroundColor Green
Write-Host ("    SHA256SUMS     : " + $SumsPath) -ForegroundColor Green
Write-Host ("    Manifest       : " + $ManifestPath) -ForegroundColor Green
Write-Host ""
exit 0
