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
#   6. Source secret scan        (same patterns, case-insensitive, over every
#                                 tracked text file; no file-level exemptions —
#                                 known fixtures are allowlisted by exact
#                                 value. Fails closed on unreadable files, on
#                                 an eligible/scanned mismatch, and on 0 files)
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

param(
    # Run ONLY the source secret scan and exit. No build, no staging, no zip.
    # Added so this gate can actually be executed and red-tested on its own:
    # a full release run costs minutes of PyInstaller + cargo before it would
    # ever reach the scan.
    [switch]$AuditOnly
)

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
# ---------------------------------------------------------------------------
# Step 0: Prepare release/ output dir
# ---------------------------------------------------------------------------

$Patterns = @(
    # Every pattern below is matched case-INSENSITIVELY (see $RxOpts). URI
    # schemes are case-insensitive per RFC 3986, and this project's own parser
    # agrees: sidecar.py lower-cases before its `startswith("magnet:")` check
    # and _REDACT_MAGNET_RX carries re.IGNORECASE. A case-sensitive scan would
    # therefore miss `MAGNET:?XT=URN:BTIH:...` — a string production happily
    # accepts and interns. Verified: register_magnets returns ok for the
    # upper-case form while the old pattern did not match it at all.
    # GREEDY `{40,}`, not `{40}` and not `{40}(?!hex)`. All three were tried:
    #   {40}            — a 42-hex value matches its first 40 chars, and if
    #                     those 40 are allowlisted the real value passes.
    #   {40}(?![hex])   — a 42-hex value then matches NOTHING AT ALL (the
    #                     lookahead fails at every start offset), which is a
    #                     bigger hole than the one it was meant to close. This
    #                     was caught by executing the red test, not by reading.
    #   {40,}           — consumes the whole run, so anything longer than an
    #                     allowlisted literal is a distinct value and fails.
    @{ name = 'urn:btih:<40+hex>';           rx = 'urn:btih:[a-fA-F0-9]{40,}' },
    # BitTorrent v1 infohashes are 40 hex OR 32 base32 (BEP 9); v2 uses a
    # different URN entirely (`urn:btmh:`, BEP 52). An earlier commit message
    # claimed "64-hex btih v2" — that form does not exist. Cover all three.
    @{ name = 'urn:btih:<32+base32>';        rx = 'urn:btih:[A-Z2-7]{32,}' },
    @{ name = 'urn:btmh: (BitTorrent v2)';   rx = 'urn:bt' + 'mh:[a-fA-F0-9]{10,}' },
    # `{16,}` rather than `+`: redact_magnet()'s output is a fixed 8 hex chars,
    # so `+` made this pattern flag the project's own CORRECTLY REDACTED form.
    # Real v1 infohashes are 40 hex (or 32 base32); 16 is a safe floor that
    # passes the 8-char redacted form and catches every real length.
    @{ name = 'magnet:?xt=';                 rx = 'magnet:\?xt=urn:bt' + '[im]h:[a-zA-Z0-9]{16,}' },
    # Length floors and separator grammar now follow what PRODUCTION accepts,
    # not what a "realistic" secret looks like. secret_store.rs takes 1-255
    # ASCII alphanumerics; legacy_import.rs trims whitespace around `=` and
    # strips surrounding quotes; parse_cookie_string trims each `k = v` pair.
    # A scanner narrower than the parser is a scanner with a documented hole,
    # so `\s*`, optional quotes and a floor of 1 are all deliberate. The cost
    # Separator is `[ \t]*`, not `\s*`: `\s` spans newlines, so a bare
    # a bare `<token-name>=` at end of line would swallow the next non-blank line as
    # its "value". parse_cookie_string drops any pair containing CR/LF outright
    # (F-05), so horizontal whitespace is also the correct grammar.
    # Value class is `[^;\r\n]`, i.e. EXACTLY what parse_cookie_string keeps:
    # it splits on `;`, drops any pair containing CR/LF, and trims. Anything
    # narrower truncates the match, and a truncated match is a bypass —
    # `<cookie-name>=<fixture>"<real-secret>` matched only the allowlisted
    # prefix, so the filter discarded the hit and the real secret rode in behind
    # a fixture. Two earlier attempts (positive class, then a narrower negated
    # class) both still stopped early; matching the complete value is the only
    # form that cannot be prefixed.
    # The other cost is that short test fixtures now match — they are listed in
    # $AllowedLiterals, which is exactly the reviewable-diff tradeoff this
    # design already makes everywhere else.
    @{ name = 'Cloudflare clearance cookie'; rx = 'cf' + '_clearance[ \t]*=[ \t]*["'']?' + '[^;\r\n]{1,}' },
    @{ name = 'Cloudflare bot cookie';       rx = '__cf' + '_bm[ \t]*=[ \t]*["'']?' + '[^;\r\n]{1,}' },
    @{ name = 'JavDB session cookie';        rx = '_jdb' + '_session[ \t]*=[ \t]*["'']?' + '[^;\r\n]{1,}' },
    @{ name = 'remember_me_token=';          rx = 'remember_me_token[ \t]*=[ \t]*["'']?' + '[^;\r\n]{1,}' },
    # token68 (RFC 7235) allows -._~+/ and trailing '='; the old [A-Za-z0-9_-]
    # stopped at the first '.' and reported a truncated match.
    @{ name = 'Authorization bearer header'; rx = 'Authorization:\s*' + 'Bearer\s+' + '[A-Za-z0-9_.~+/=-]{8,}' },
    @{ name = 'Bearer <token>';              rx = 'Bearer\s+' + '[A-Za-z0-9_.~+/=-]{16,}' },
    @{ name = 'RD_API_TOKEN=<value>';        rx = 'RD_API' + '_TOKEN[ \t]*=[ \t]*["'']?' + '[^;\r\n]{1,}' }
)

# All regex evaluation in this script goes through these options. See the
# comment above $Patterns for why IgnoreCase is not optional here.
# NOTE: script scope, defined BEFORE the binary scan. It lived inside
# Invoke-SourceSecretScan until the binary scan started using it too — and
# the binary scan runs FIRST, so under Set-StrictMode the release aborted
# on an undefined variable. Third instance of the same mistake: moving code
# into a function silently rebinds every name it assigns.
# Known-synthetic literals, allowlisted BY EXACT VALUE rather than by file.
#
# The previous design skipped whole files (commands.rs, legacy_import.rs,
# tests/, *.test.ts, four prose docs, and this script). That exempted ~23 text
# files INCLUDING production Rust and the gate itself: any real token later
# pasted into them would never have been seen. "Every tracked file" was not
# true.
#
# Now nothing is exempt. Every tracked text file is scanned, and a match only
# passes if its exact text appears below. Each entry is a fixture whose
# synthetic nature is self-evident (DEADBEEF / repeated nibbles / sequential
# counters / obvious placeholder session names), except the one PoC hash in the
# security-audit archive, which demonstrates a dedupe-key collision where the
# point is that the SAME arbitrary string appears twice.
#
# Adding an entry here is a visible, reviewable diff line — unlike adding a
# file to a skip list, which blinds the scanner to everything in that file
# forever. A NEW fixture will fail the build until it is listed; that is the
# intended cost.
$AllowFile = Join-Path $ScriptDir "release-scan-allowlist.txt"
if (-not (Test-Path -LiteralPath $AllowFile)) { FailExit ("Missing allowlist: " + $AllowFile) }
$AllowedLiterals = @(Get-Content -LiteralPath $AllowFile -Encoding utf8 |
    Where-Object { $_ -and -not $_.StartsWith('#') })

$RxOpts = [System.Text.RegularExpressions.RegexOptions]::IgnoreCase

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
    @{ label = 'UTF-16LE';   encoding = [System.Text.Encoding]::Unicode },
    # UTF-16BE too. Reading raw bytes fixed the BOM-less UTF-16LE hole but lost
    # what Get-Content did give us for free: BOM detection. A UTF-16BE file
    # decoded as ASCII or UTF-16LE yields interleaved or byte-swapped text, so a
    # contiguous ASCII credential never reaches the regexes.
    @{ label = 'UTF-16BE';   encoding = [System.Text.Encoding]::BigEndianUnicode },
    # UTF-32 both ways. Same failure as UTF-16BE: the NULs stay between
    # characters under every other decoder, so an ASCII credential is never
    # contiguous and matches nothing.
    @{ label = 'UTF-32LE';   encoding = [System.Text.Encoding]::UTF32 },
    @{ label = 'UTF-32BE';   encoding = (New-Object System.Text.UTF32Encoding $true, $true) }
)


function Get-SourceText {
    <#
      Decode one tracked text file ONCE, correctly.

      Scanning every candidate encoding (what this used to do) is right for a
      binary, which carries no encoding metadata — but for text it is actively
      harmful: a file containing non-ASCII decodes differently under each
      decoder, so the same fixture yields several different "complete values"
      and the exact-value allowlist can never cover them all. commands.rs
      (Chinese help text) hit exactly that and could not be allowlisted.

      BOM wins when present. Otherwise interleaved NULs are the tell for a
      BOM-less UTF-16/32 file — the case that made reading bytes necessary in
      the first place — and everything else is UTF-8.
    #>
    param([byte[]]$Bytes)
    if ($Bytes.Length -ge 4 -and $Bytes[0] -eq 0xFF -and $Bytes[1] -eq 0xFE -and $Bytes[2] -eq 0 -and $Bytes[3] -eq 0) {
        return [System.Text.Encoding]::UTF32.GetString($Bytes, 4, $Bytes.Length - 4)
    }
    if ($Bytes.Length -ge 4 -and $Bytes[0] -eq 0 -and $Bytes[1] -eq 0 -and $Bytes[2] -eq 0xFE -and $Bytes[3] -eq 0xFF) {
        return (New-Object System.Text.UTF32Encoding $true, $true).GetString($Bytes, 4, $Bytes.Length - 4)
    }
    if ($Bytes.Length -ge 2 -and $Bytes[0] -eq 0xFF -and $Bytes[1] -eq 0xFE) {
        return [System.Text.Encoding]::Unicode.GetString($Bytes, 2, $Bytes.Length - 2)
    }
    if ($Bytes.Length -ge 2 -and $Bytes[0] -eq 0xFE -and $Bytes[1] -eq 0xFF) {
        return [System.Text.Encoding]::BigEndianUnicode.GetString($Bytes, 2, $Bytes.Length - 2)
    }
    if ($Bytes.Length -ge 3 -and $Bytes[0] -eq 0xEF -and $Bytes[1] -eq 0xBB -and $Bytes[2] -eq 0xBF) {
        return [System.Text.Encoding]::UTF8.GetString($Bytes, 3, $Bytes.Length - 3)
    }
    # No BOM. Sample the head for NULs; real UTF-8 source never contains them.
    $probe = [Math]::Min(512, $Bytes.Length)
    $nulEven = 0; $nulOdd = 0
    for ($i = 0; $i -lt $probe; $i++) {
        if ($Bytes[$i] -eq 0) { if ($i % 2 -eq 0) { $nulEven++ } else { $nulOdd++ } }
    }
    if (($nulEven + $nulOdd) -gt ($probe / 8)) {
        if ($nulOdd -ge $nulEven) { return [System.Text.Encoding]::Unicode.GetString($Bytes) }
        return [System.Text.Encoding]::BigEndianUnicode.GetString($Bytes)
    }
    return [System.Text.Encoding]::UTF8.GetString($Bytes)
}

function Invoke-SourceSecretScan {

    # ---------------------------------------------------------------------------
    # Step 7: Source secret scan — over EVERY tracked file
    #
    # This used to derive its file list from `git diff <origin/HEAD>..HEAD` plus
    # the working-tree diff. That made coverage depend on where HEAD happened to
    # sit: cutting a release from an already-pushed master left both diffs empty,
    # so the scan walked ZERO files and still wrote `source_secret_hits: 0` into
    # the manifest — a vacuous pass that read exactly like a real one. It was
    # found the hard way: a magnet literal sat in verify-windows-build.ps1 from
    # the commit that introduced it and was never once scanned, until an
    # unrelated edit to that file finally pulled it into the diff.
    #
    # The file list now comes from `git ls-files`, so coverage is a property of
    # the repo rather than of the branch topology. Content is read from disk, so
    # uncommitted edits to tracked files are scanned as they actually are.
    # Untracked files are deliberately out of scope: they are neither committed
    # nor shipped inside the portable zip.
    # ---------------------------------------------------------------------------
    Step "Source secret scan (all tracked text files)"
    # -z + NUL split: without it git quotes paths containing non-ASCII or control
    # characters ("\303\251.md"), and the quoted name matches nothing on disk — the
    # file is then silently dropped from the scan.
    # Windows PowerShell 5.1 decodes native-command output using the console code
    # page, not UTF-8. A tracked filename with non-ASCII characters would come back
    # mangled, Test-Path would then fail to resolve it, and the entry would vanish
    # from the scan. Force UTF-8 for the duration of the git call.
    $prevOutEnc = [Console]::OutputEncoding
    try {
        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
        $lsRaw = & git -C $RepoRoot ls-files -z
        $lsExit = $LASTEXITCODE
    } finally {
        [Console]::OutputEncoding = $prevOutEnc
    }
    if ($lsExit -ne 0) {
        Write-Error "FATAL: source-secret-scan git ls-files failed (exit $lsExit). Refusing to ship a release without a source scan."
        exit 1
    }
    $sourceFiles = @(($lsRaw -join "") -split "`0" | Where-Object { $_ } | Sort-Object -Unique)
    $skipExt = @('.exe', '.msi', '.zip', '.7z', '.png', '.ico', '.icns', '.dll')


    # $script: scope, not function-local. The manifest at the end of the run
    # reads these, and a plain `$SourceHits = @()` inside a function creates a
    # local that evaporates on return — under Set-StrictMode the manifest step
    # then aborts AFTER the whole build and hashing has already run. Same class
    # of mistake as dropping the $ManifestPath assignment: extracting code into
    # a function silently changed a binding.
    $script:SourceHits     = @()
    $script:SourceEligible = 0   # tracked, non-binary, i.e. in scope
    $script:SourceScanned  = 0   # actually read and regexed
    $script:SourceAllowed  = 0   # matched but present in $AllowedLiterals
    foreach ($rel in $sourceFiles) {
        $full = Join-Path $RepoRoot $rel
        if ($skipExt -contains ([System.IO.Path]::GetExtension($rel).ToLowerInvariant())) { continue }
        # The allowlist data file is the one and only exclusion. See its header.
        if ($rel -eq 'scripts/release-scan-allowlist.txt') { continue }
        $script:SourceEligible++
        # -LiteralPath: a tracked file called `notes[1].md` is a valid wildcard to
        # Test-Path, which would report it missing.
        #
        # Fail CLOSED here, and count the entry as eligible BEFORE testing it. The
        # earlier version skipped unresolvable paths before incrementing, so the
        # eligible-equals-scanned invariant could never detect them — the exact
        # blind spot that invariant was added to close. The working tree is
        # verified clean at Step 0, so every index entry must exist on disk; one
        # that does not means the path came back mangled (encoding) or something
        # changed underneath the build.
        if (-not (Test-Path -LiteralPath $full -PathType Leaf)) {
            FailExit ("Source secret scan could not resolve tracked path: " + $rel + " — refusing to ship a partial scan.")
        }
        # Fail CLOSED on read errors. The old code used -ErrorAction SilentlyContinue
        # and `continue`d on $null, so an unreadable file vanished from the scan
        # while the run still reported success — a file the scanner could not read
        # is exactly the file worth worrying about.
        # Read BYTES, not text. Get-Content -Raw picks an encoding for you, and the
        # default differs between Windows PowerShell 5.1 and PowerShell 7: a
        # BOM-less UTF-16LE file decodes into ASCII interleaved with NULs, so a
        # perfectly readable secret matches nothing while I/O "succeeds" and
        # eligible still equals scanned.
        try {
            $bytes = [System.IO.File]::ReadAllBytes($full)
        } catch {
            FailExit ("Source secret scan could not read " + $rel + ": " + $_.Exception.Message)
        }
        $script:SourceScanned++
        # Same two-encoding sweep the binary scan does, plus a percent-decoded pass
        # of each: production normalises `magnet:?xt=urn%3Abtih%3A<hash>` back to
        # `btih:<hash>` (verified via _magnet_dedupe_key) and interns it, so a scan
        # that only sees the raw bytes misses an escaped magnet entirely.
        # One correct decode, plus a percent-decoded pass: production
        # normalises `magnet:?xt=urn%3Abtih%3A<hash>` back to `btih:<hash>`
        # before interning it, so an escaped magnet must not slip past.
        $decoded = Get-SourceText -Bytes $bytes
        $variants = New-Object System.Collections.Generic.List[string]
        $variants.Add($decoded)
        try {
            $unescaped = [System.Uri]::UnescapeDataString($decoded)
            if ($unescaped -cne $decoded) { $variants.Add($unescaped) }
        } catch { }
        foreach ($text in $variants) {
            foreach ($p in $Patterns) {
                foreach ($m in [regex]::Matches($text, $p.rx, $RxOpts)) {
                    if ($AllowedLiterals -ccontains $m.Value) { $script:SourceAllowed++; continue }
                    $script:SourceHits += ("      " + $rel + "  [" + $p.name + "]")
                }
            }
        }
    }
    if ($script:SourceHits.Count -gt 0) {
        Write-Host "    Source secret scan LEAK:" -ForegroundColor Red
        # File + pattern only, never the matched text (same reasoning as the binary
        # scan above).
        $script:SourceHits | Sort-Object -Unique | ForEach-Object { Write-Host $_ -ForegroundColor Red }
        Write-Host "    If a hit is a synthetic fixture, add its exact value to `$AllowedLiterals." -ForegroundColor Red
        FailExit "Source secret scan failed"
    }
    # A scan that walked nothing must never report success — that is the exact
    # failure mode this step was rewritten to eliminate, so assert it explicitly
    # instead of trusting the file list to be non-empty.
    if ($script:SourceScanned -eq 0) {
        FailExit "Source secret scan walked 0 files — the scan is not covering anything. Check git ls-files and skipExt."
    }
    if ($script:SourceScanned -ne $script:SourceEligible) {
        FailExit ("Source secret scan read " + $script:SourceScanned + " of " + $script:SourceEligible + " eligible files; refusing to ship a partial scan.")
    }
    Ok ("No unexpected source secrets (" + $script:SourceScanned + " text files scanned, " + $script:SourceAllowed + " allowlisted fixture matches)")
}

# --------------------------------------------------------------------------
# -AuditOnly: run just the scan and exit. The clean-tree gate is skipped on
# this path ON PURPOSE — red-testing the scanner means planting a secret,
# which necessarily dirties the tree. Never use this mode to ship.
# --------------------------------------------------------------------------
if ($AuditOnly) {
    Write-Output "== AUDIT ONLY: source secret scan, no build =="
    Invoke-SourceSecretScan
    Write-Output "[PASS] audit-only scan clean"
    exit 0
}

Step "Verifying working tree is clean"
# The build reads the WORKING TREE (npm/cargo/PyInstaller all compile what is on
# disk), but the manifest records `git rev-parse HEAD`. With uncommitted edits
# those two describe different code, and the manifest silently vouches for a
# commit that was never what shipped.
#
# Untracked files matter just as much and are easy to miss: `git ls-files` does
# not see them, so the source scan skips them entirely — yet PyInstaller
# resolves the sidecar's dependency graph from the repo root, so an untracked
# top-level module CAN be pulled into sidecar.exe. Scanning "every tracked
# file" is not the same as scanning every build input.
$BuildStartHead = (& git -C $RepoRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { FailExit "git rev-parse HEAD failed; refusing to build" }
# --untracked-files=all explicitly: `status.showUntrackedFiles=no` in any
# config layer would otherwise hide untracked files entirely, and untracked
# top-level modules CAN be pulled into sidecar.exe by PyInstaller.
$treeStatus = & git -C $RepoRoot status --porcelain --untracked-files=all
if ($LASTEXITCODE -ne 0) { FailExit "git status failed (exit $LASTEXITCODE); refusing to build" }
# assume-unchanged (h) and skip-worktree (S) make git report a clean tree while
# the file on disk differs from the index — the build would compile content
# that neither git status nor the source scan ever sees.
$maskedEntries = & git -C $RepoRoot ls-files -v
if ($LASTEXITCODE -ne 0) { FailExit "git ls-files -v failed; refusing to build" }
$masked = @($maskedEntries | Where-Object { $_ -cmatch '^[a-z]' -or $_ -cmatch '^S ' })
if ($masked.Count -gt 0) {
    $masked | ForEach-Object { Write-Output ("      " + $_) }
    FailExit "Tracked files are marked assume-unchanged/skip-worktree; git cannot vouch for their contents. Clear with: git update-index --no-assume-unchanged --no-skip-worktree <path>"
}
if ($treeStatus) {
    Write-Output "    Working tree is not clean:"
    $treeStatus | ForEach-Object { Write-Output ("      " + $_) }
    FailExit "Refusing to build: commit or stash everything first, so git_commit describes what actually ships."
}
Ok "Working tree clean (tracked + untracked)"

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
# Explicitly verify none of the forbidden names slipped in even if the
# whitelist somehow expanded.
$ForbiddenNames = @('.env','.gitignore','cookies.txt','pending_torrents.json','magnet.txt')
$StagingViolations = @()
foreach ($f in $StagedFiles) {
    $rel = $f.FullName.Substring($StagingDir.Length).TrimStart('\','/')
    $leaf = Split-Path $f.FullName -Leaf
    # No subdirectories allowed.
    if ($rel -match '[\\/]') {
        $StagingViolations += "subdir entry: $rel"
        continue
    }
    if ($AllowedNames -notcontains $leaf) {
        $StagingViolations += "unexpected file: $rel"
    }
    if ($ForbiddenNames -contains $leaf) { $StagingViolations += "forbidden: $leaf" }
    if ($leaf -like '.env.*' -or $leaf -like '*.log' -or $leaf -like '*.token' -or $leaf -like '*.spec') {
        $StagingViolations += "forbidden pattern: $leaf"
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
foreach ($exe in $ScanTargets) {
    $name = Split-Path $exe -Leaf
    $bytes = [System.IO.File]::ReadAllBytes($exe)
    $hits = @()
    foreach ($enc in $Encodings) {
        $decoded = $enc.encoding.GetString($bytes)
        # Percent-decoded pass for the same reason as the source scan: an
        # escaped magnet is still a magnet by the time production sees it.
        $texts = @($decoded)
        try {
            $u = [System.Uri]::UnescapeDataString($decoded)
            if ($u -cne $decoded) { $texts += $u }
        } catch { }
        foreach ($text in $texts) {
        foreach ($p in $Patterns) {
            # Allowlist applies here too, and it has to: the app EMBEDS its own
            # cookies.txt template (commands.rs COOKIES_TEMPLATE) containing
            # the cookies.txt example line (session + clearance placeholders). Once
            # the patterns were widened to production's grammar, the binary scan
            # started flagging javdbmagnet.exe against its own help text — every
            # release would have failed. Matching is per-VALUE, not per-file or
            # per-line, so a real secret elsewhere in the same binary is a
            # different match and still fails.
            $regexMatches = @([regex]::Matches($text, $p.rx, $RxOpts) |
                Where-Object { $AllowedLiterals -cnotcontains $_.Value })
            if ($regexMatches.Count -gt 0) {
                # Artifact + pattern + count ONLY. Never echo the matched value:
                # the whole point of this step is that a secret reached a binary,
                # and printing it would copy that secret into the build log —
                # which, once this runs in CI, is a persistent artifact of its
                # own. Reproduce locally if you need to see the value.
                $hits += "      [$($enc.label)] $($p.name)  count=$($regexMatches.Count)"
                $BinaryHitCount += $regexMatches.Count
            }
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
Invoke-SourceSecretScan

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
    $h = ((Get-FileHash -Path $t.path -Algorithm SHA256).Hash)
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

# Re-verify the snapshot. The clean-tree assertion at Step 0 is minutes old by
# now: PyInstaller, cargo and the two scans all ran in between, and any edit or
# checkout during that window would leave the manifest vouching for a commit
# that is not what was compiled and scanned. Checking only at the start, then
# hardcoding `working_tree_clean = true`, would make the field an assertion
# about the past rather than about the artifact.
Step "Re-verifying source snapshot after build"
$ManifestPath = Join-Path $ReleaseOutDir "release-manifest.json"
$gitCommit = (& git -C $RepoRoot rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { FailExit "git rev-parse HEAD failed after build" }
if ($gitCommit -ne $BuildStartHead) {
    FailExit ("HEAD moved during the build (" + $BuildStartHead + " -> " + $gitCommit + "); the artifacts do not match either commit.")
}
$treeStatusAfter = & git -C $RepoRoot status --porcelain --untracked-files=all
if ($LASTEXITCODE -ne 0) { FailExit "git status failed after build" }
if ($treeStatusAfter) {
    $treeStatusAfter | ForEach-Object { Write-Output ("      " + $_) }
    FailExit "Working tree changed during the build; the scanned source is not what shipped."
}
Ok ("Snapshot unchanged through build: " + $gitCommit)
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
        # Denominators, so `source_secret_hits: 0` is interpretable: without
        # them a scan that covered nothing is indistinguishable from one that
        # covered the whole repo and found nothing. `eligible` vs `scanned`
        # must be equal — a gap means files were dropped.
        source_files_eligible    = $SourceEligible
        source_files_scanned     = $SourceScanned
        source_allowlisted_hits  = $SourceAllowed
        # Checked before the build and re-checked after it. This does NOT prove
        # the compiler observed exactly this snapshot: an edit made and reverted
        # mid-build leaves both checks clean while an artifact was produced from
        # transient source. The field is named for what is actually verified.
        # Proving the stronger property requires building from an immutable
        # checkout (git archive / a throwaway worktree), which this pipeline
        # does not yet do.
        working_tree_clean       = $true
        source_snapshot_verified = "pre_and_post_build_clean"
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
