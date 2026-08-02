# test-release-scan.ps1 — Red tests for the release source-secret scan.
#
# Why this exists: two release-breaking bugs shipped in a row because the scan
# was only ever reasoned about, never executed —
#   1. `$ManifestPath`'s assignment was deleted by an edit whose anchor happened
#      to include it. Braces still balanced; the failure only appears minutes
#      into a real release.
#   2. Extracting the scan into a function turned `$SourceHits` and its three
#      counters into function-locals, so the manifest step aborted under
#      Set-StrictMode — again only on the full release path.
# Both are invisible to reading and to `-AuditOnly` (which exits before the
# manifest). They are cheap to catch by executing.
#
# Run:
#     pwsh -File scripts\test-release-scan.ps1

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot  = Split-Path -Parent $ScriptDir
$Target    = Join-Path $ScriptDir "build-release.ps1"

# Re-invoke the SAME host that is running this suite, not a hardcoded `pwsh`.
# `npm run release` calls `powershell` (Windows PowerShell 5.1) while these
# tests were calling `pwsh` (7.x): the suite could pass under one engine while
# the shipped path ran on the other. Run this file under each host to cover
# both — see scripts/verify-windows-build.ps1, which does exactly that.
# (Get-Process -Id $PID).Path is the actual executable running this file, so it
# works identically under Windows PowerShell 5.1 and PowerShell 7 without
# branching on edition.
$PSExe = (Get-Process -Id $PID).Path
if (-not $PSExe) { $PSExe = 'pwsh' }
Write-Output ("Host: " + $PSVersionTable.PSVersion + " (" + $PSVersionTable.PSEdition + ") -> " + $PSExe)

$script:Pass = 0
$script:Fail = 0
function Check($name, $ok, $detail) {
    if ($ok) { Write-Output ("  [PASS] " + $name); $script:Pass++ }
    else     { Write-Output ("  [FAIL] " + $name + "  " + $detail); $script:Fail++ }
}

Write-Output "== 1. Parses, and every variable it reads is assigned =="
$errs = $null; $toks = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($Target, [ref]$toks, [ref]$errs)
Check "no parse errors" ($errs.Count -eq 0) ($errs | Select-Object -First 1)

# Catches the $ManifestPath class: a variable read at script scope that nothing
# ever assigns at script scope.
$assigned = @{}
$ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.AssignmentStatementAst] }, $true) |
    ForEach-Object {
        if ($_.Left -is [System.Management.Automation.Language.VariableExpressionAst]) {
            $assigned[$_.Left.VariablePath.UserPath -replace '^script:', ''] = $true
        }
    }
$ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.ForEachStatementAst] }, $true) |
    ForEach-Object { $assigned[$_.Variable.VariablePath.UserPath] = $true }
$ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.ParameterAst] }, $true) |
    ForEach-Object { $assigned[$_.Name.VariablePath.UserPath] = $true }
$builtin = '_', 'PSItem', 'true', 'false', 'null', 'LASTEXITCODE', 'ErrorActionPreference',
           'PSScriptRoot', 'MyInvocation', 'args', 'PWD', 'Error', 'Host', 'OutputEncoding',
           'PSVersionTable', 'input'
$undeclared = @()
$ast.FindAll({ param($n) $n -is [System.Management.Automation.Language.VariableExpressionAst] }, $true) |
    ForEach-Object {
        $n = $_.VariablePath.UserPath -replace '^script:', ''
        if (-not $assigned.ContainsKey($n) -and $builtin -notcontains $n -and $n -notlike 'env:*') {
            $undeclared += ($n + " (line " + $_.Extent.StartLineNumber + ")")
        }
    }
Check "no undeclared variables" ($undeclared.Count -eq 0) ($undeclared -join ', ')

Write-Output ""
Write-Output "== 2. Scan metrics survive the function call =="
# The manifest reads these AFTER Invoke-SourceSecretScan returns. Assigning
# them without `$script:` inside the function makes them locals, and the whole
# release dies at the manifest step. Assert the names are script-scoped.
$src = Get-Content -LiteralPath $Target -Raw
foreach ($v in 'SourceHits', 'SourceEligible', 'SourceScanned', 'SourceAllowed') {
    $localAssign = [regex]::Matches($src, '(?m)^\s*\$' + $v + '\s*=')
    Check ("`$$v is script-scoped, not function-local") ($localAssign.Count -eq 0) `
        ("found " + $localAssign.Count + " unscoped assignment(s)")
}

Write-Output ""
Write-Output "== 3. Clean-tree run passes =="
& $PSExe -NoProfile -File $Target -AuditOnly | Out-Null
Check "audit-only exits 0 on a clean repo" ($LASTEXITCODE -eq 0) ("exit " + $LASTEXITCODE)

Write-Output ""
Write-Output "== 4. Red tests: each planted secret must fail the scan =="
# Every entry is a form production accepts. A regression that narrows the
# scanner shows up here as a [FAIL].
#
# Each payload is SPLIT across a `+` in source so this file's own text does not
# contain a contiguous secret-shaped literal — otherwise the scan flags this
# file, and "fix" would mean allowlisting the payloads, which would stop the
# red tests from ever failing. Same technique build-release.ps1 uses for its
# own $Patterns. The runtime value is unchanged.
$probes = @(
    @{ n = 'plain 40-hex magnet';   f = 'README.md';                      s = 'magnet:?xt=urn:bt' + 'ih:ff11ee22dd33cc44bb55aa6699887766554433ff' },
    @{ n = 'upper-case MAGNET';     f = 'README.md';                      s = 'MAGNET:?XT=URN:BT' + 'IH:1234567890ABCDEF1234567890ABCDEF12345678' },
    @{ n = 'percent-encoded magnet';f = 'CLAUDE.md';                      s = 'magnet:?xt=urn%3Abt' + 'ih%3Aff11ee22dd33cc44bb55aa6699887766554433ee' },
    @{ n = 'base32 v1 infohash';    f = 'CLAUDE.md';                      s = 'urn:bt' + 'ih:MFRGGZDFMZTWQ2LKNNWG23TPOBYXE43U' },
    @{ n = 'btmh v2 infohash';      f = 'app_logging.py';                 s = '# urn:bt' + 'mh:1220abcdef0123456789abcdef0123456789abcdef0123456789abcdef01234567' },
    @{ n = '40-hex plus 2 (greedy)';f = 'rd_outcome_log.py';              s = '# urn:bt' + 'ih:0123456789abcdef0123456789abcdef01234567FF' },
    @{ n = 'RD token, spaces+quotes';f = 'pyproject.toml';                s = '# RD_API' + '_TOKEN = "Zm9vYmFyYmF6cXV4MTIzNDU2Nzg5MA"' },
    @{ n = 'RD token, short';       f = 'sonar-project.properties';       s = '# RD_API' + '_TOKEN=sh0rtTok' },
    @{ n = 'cookie with spaces';    f = 'requirements-ci.txt';            s = '# _jdb' + '_session = LiveSessionValue123456' },
    @{ n = 'Bearer token68 charset';f = 'javdb_scraper.py';               s = '# Authorization: ' + 'Bea' + 'rer ab.cd~ef+gh/ij=klmnopqrst' },
    @{ n = 'secret in production rs';f = 'app/src-tauri/src/pending.rs';  s = '// cf' + '_clearance=RealLookingClearanceValue999' },
    # Prefix bypass: the value STARTS with an allowlisted fixture and continues
    # with a character a positive charset would not know. A regex that stops
    # early returns only the allowlisted prefix and the filter drops the hit,
    # taking the real secret with it. parse_cookie_string accepts this value.
    @{ n = 'allowlisted prefix + secret'; f = 'requirements-sidecar.txt';    s = '# _jdb' + '_session=paste_session' + [char]33 + 'RealSecretRidesAlong' },
    # Same shape one layer up: a whole extra line whose value merely begins
    # like a fixture.
    @{ n = 'fixture-prefixed cf value';   f = 'PSScriptAnalyzerSettings.psd1'; s = '# cf' + '_clearance=XXX' + [char]33 + 'ActualClearanceValue' }
)
foreach ($p in $probes) {
    $full = Join-Path $RepoRoot $p.f
    $orig = [System.IO.File]::ReadAllBytes($full)
    try {
        Add-Content -LiteralPath $full -Value ("`n" + $p.s) -Encoding utf8
        & $PSExe -NoProfile -File $Target -AuditOnly | Out-Null
        Check ("blocks: " + $p.n) ($LASTEXITCODE -ne 0) "scan passed but should not have"
    } finally {
        [System.IO.File]::WriteAllBytes($full, $orig)
    }
}

# UTF-16BE with BOM: Get-Content used to detect this for free; reading raw bytes
# does not, so the encoding list has to cover it explicitly.
Write-Output ""
Write-Output "== 5. Red test: UTF-16BE-encoded secret =="
$u16 = Join-Path $RepoRoot "docs/troubleshooting/rd-token.md"
$origBytes = [System.IO.File]::ReadAllBytes($u16)
try {
    $payload = ([System.Text.Encoding]::UTF8.GetString($origBytes)) +
               "`nmagnet:?xt=urn:bt" + "ih:aa11bb22cc33dd44ee55ff6677889900aabbccdd`n"
    [System.IO.File]::WriteAllBytes($u16,
        [System.Text.Encoding]::BigEndianUnicode.GetPreamble() +
        [System.Text.Encoding]::BigEndianUnicode.GetBytes($payload))
    & $PSExe -NoProfile -File $Target -AuditOnly | Out-Null
    Check "blocks: secret inside a UTF-16BE file" ($LASTEXITCODE -ne 0) "scan passed but should not have"
} finally {
    [System.IO.File]::WriteAllBytes($u16, $origBytes)
}

Write-Output ""
Write-Output "== 5b. Red test: UTF-32LE-encoded secret =="
# Same class as UTF-16BE. Get-SourceText picks the encoding from the BOM;
# a regression that drops a branch shows up here.
$u32 = Join-Path $RepoRoot "docs/troubleshooting/no-pending-links.md"
$origU32 = [System.IO.File]::ReadAllBytes($u32)
try {
    $payload32 = ([System.Text.Encoding]::UTF8.GetString($origU32)) +
                 "`nmagnet:?xt=urn:bt" + "ih:bb22cc33dd44ee55ff6677889900aabbccddeeff`n"
    [System.IO.File]::WriteAllBytes($u32,
        [System.Text.Encoding]::UTF32.GetPreamble() +
        [System.Text.Encoding]::UTF32.GetBytes($payload32))
    & $PSExe -NoProfile -File $Target -AuditOnly | Out-Null
    Check "blocks: secret inside a UTF-32LE file" ($LASTEXITCODE -ne 0) "scan passed but should not have"
} finally {
    [System.IO.File]::WriteAllBytes($u32, $origU32)
}

Write-Output ""
Write-Output "== 5c. Red test: quote-prefixed bypass =="
# The shape that survived two narrower value classes: value starts with an
# allowlisted fixture and continues after a quote.
$qf = Join-Path $RepoRoot "requirements-ci.txt"
$origQ = [System.IO.File]::ReadAllBytes($qf)
try {
    Add-Content -LiteralPath $qf -Value ("`n# _jdb" + "_session=paste_session" + [char]34 + "RealSecretAfterQuote") -Encoding utf8
    & $PSExe -NoProfile -File $Target -AuditOnly | Out-Null
    Check "blocks: quote-prefixed bypass" ($LASTEXITCODE -ne 0) "scan passed but should not have"
} finally {
    [System.IO.File]::WriteAllBytes($qf, $origQ)
}

Write-Output ""
Write-Output "== 5d. Binary scan: the app's own template must not fail it =="
# The binary scan had NO coverage until now — -AuditOnly never reaches it — and
# that is precisely where the last release blocker hid: the exe embeds
# COOKIES_TEMPLATE, and a value class that ran past whitespace turned the app's
# own help text into a non-allowlistable match, failing every release.
$tplSrc = Get-Content -LiteralPath (Join-Path $RepoRoot "app/src-tauri/src/commands.rs") -Raw
$m = [regex]::Match($tplSrc, 'const COOKIES_TEMPLATE: &str = "(.*?)";', 'Singleline')
Check "found COOKIES_TEMPLATE in commands.rs" ($m.Success) "constant not found; update this test"
if ($m.Success) {
    $tpl = $m.Groups[1].Value -replace '\\n', "`n"
    $blob = Join-Path ([System.IO.Path]::GetTempPath()) ("relscan-" + [guid]::NewGuid().ToString("N") + ".bin")
    try {
        [System.IO.File]::WriteAllBytes($blob,
            ([byte[]](0,1,77,90)) + [System.Text.Encoding]::UTF8.GetBytes($tpl) + ([byte[]](0,0)))
        & $PSExe -NoProfile -File $Target -AuditBinary $blob | Out-Null
        Check "binary scan passes on the embedded template" ($LASTEXITCODE -eq 0) ("exit " + $LASTEXITCODE)

        # ...and still catches a real one sitting right next to it.
        [System.IO.File]::WriteAllBytes($blob,
            ([byte[]](0,1,77,90)) + [System.Text.Encoding]::UTF8.GetBytes($tpl) +
            ([byte[]](0)) + [System.Text.Encoding]::UTF8.GetBytes('_jdb' + '_session=RealLeakedSessionValue999') + ([byte[]](0)))
        & $PSExe -NoProfile -File $Target -AuditBinary $blob | Out-Null
        Check "binary scan blocks a real embedded cookie" ($LASTEXITCODE -ne 0) "scan passed but should not have"

        # Prefix bypass in the binary path: value begins with an allowlisted
        # fixture and continues after a space. A whitespace-terminated class
        # returned only the fixture and dropped the hit.
        [System.IO.File]::WriteAllBytes($blob,
            ([byte[]](0,1,77,90)) + [System.Text.Encoding]::UTF8.GetBytes($tpl) +
            ([byte[]](0)) + [System.Text.Encoding]::UTF8.GetBytes('_jdb' + '_session=paste_session RealSecretRidesAlong') + ([byte[]](0)))
        & $PSExe -NoProfile -File $Target -AuditBinary $blob | Out-Null
        Check "binary scan blocks a fixture-prefixed cookie" ($LASTEXITCODE -ne 0) "scan passed but should not have"

        # TAB is accepted by parse_cookie_string, so excluding C0 bytes from the
        # binary class truncated the value here and let the secret through.
        [System.IO.File]::WriteAllBytes($blob,
            ([byte[]](0,1,77,90)) + [System.Text.Encoding]::UTF8.GetBytes($tpl) +
            ([byte[]](0)) + [System.Text.Encoding]::UTF8.GetBytes('_jdb' + '_session=paste_session' + [char]9 + 'RealSecretAfterTab') + ([byte[]](0)))
        & $PSExe -NoProfile -File $Target -AuditBinary $blob | Out-Null
        Check "binary scan blocks a TAB-separated bypass" ($LASTEXITCODE -ne 0) "scan passed but should not have"
    } finally {
        Remove-Item -LiteralPath $blob -Force -ErrorAction SilentlyContinue
    }
}

Write-Output ""
Write-Output "== 5e. Red test: BOM-less wide encodings =="
# Every one of these was missed at some point. The UTF-32 pair survived two
# heuristics because the earlier rule tested low-order byte residues, which CJK
# text populates.
$encFile = Join-Path $RepoRoot "docs/troubleshooting/rd-token.md"
$encOrig = [System.IO.File]::ReadAllBytes($encFile)
$encText = [System.Text.Encoding]::UTF8.GetString($encOrig) +
           "`nmagnet:?xt=urn:bt" + "ih:cc33dd44ee55ff6677889900aabbccddeeff1122`n"
$encCases = @(
    @{ n = 'UTF-32LE, no BOM'; b = [System.Text.Encoding]::UTF32.GetBytes($encText) },
    @{ n = 'UTF-32BE, no BOM'; b = (New-Object System.Text.UTF32Encoding $true, $false).GetBytes($encText) },
    @{ n = 'UTF-16LE, no BOM'; b = [System.Text.Encoding]::Unicode.GetBytes($encText) },
    @{ n = 'UTF-16BE, no BOM'; b = [System.Text.Encoding]::BigEndianUnicode.GetBytes($encText) }
)
try {
    foreach ($c in $encCases) {
        [System.IO.File]::WriteAllBytes($encFile, $c.b)
        & $PSExe -NoProfile -File $Target -AuditOnly | Out-Null
        Check ("blocks: secret in " + $c.n) ($LASTEXITCODE -ne 0) "scan passed but should not have"
    }
} finally {
    [System.IO.File]::WriteAllBytes($encFile, $encOrig)
}

Write-Output ""
Write-Output "== 5f. Red test: whitespace grammar =="
# str.strip() / str::trim() drop VT, FF and NBSP too, all verified accepted by
# parse_cookie_string. A scanner that only knows space and TAB truncates here.
$wsFile = Join-Path $RepoRoot "requirements-sidecar.txt"
$wsOrig = [System.IO.File]::ReadAllBytes($wsFile)
try {
    foreach ($w in @(@{n='VT';c=11}, @{n='FF';c=12}, @{n='NBSP';c=160})) {
        [System.IO.File]::WriteAllBytes($wsFile, $wsOrig)
        Add-Content -LiteralPath $wsFile -Encoding utf8 -Value (
            "# _jdb" + "_session" + [char]$w.c + "=" + [char]$w.c + "LiveSessionValue123456")
        & $PSExe -NoProfile -File $Target -AuditOnly | Out-Null
        Check ("blocks: " + $w.n + "-separated cookie") ($LASTEXITCODE -ne 0) "scan passed but should not have"
    }
} finally {
    [System.IO.File]::WriteAllBytes($wsFile, $wsOrig)
}

Write-Output ""
Write-Output "== 5g. Red test: binary must not inherit source fixtures =="
# A magnet fixture in a test file is expected; the same 40-hex compiled into
# javdbmagnet.exe is not. Sharing one allowlist made the binary scan exempt
# every source fixture.
$srcFixture = (Get-Content -LiteralPath (Join-Path $ScriptDir "release-scan-allowlist.txt") -Encoding utf8 |
    Where-Object { $_ -cmatch '^magnet:\?xt=urn:btih:[a-fA-F0-9]{40}$' } | Select-Object -First 1)
Check "found a 40-hex magnet fixture to test with" ($null -ne $srcFixture) "allowlist shape changed; update this test"
if ($srcFixture) {
    $bin2 = Join-Path ([System.IO.Path]::GetTempPath()) ("relscan-" + [guid]::NewGuid().ToString("N") + ".bin")
    try {
        [System.IO.File]::WriteAllBytes($bin2,
            ([byte[]](0,1,77,90)) + [System.Text.Encoding]::UTF8.GetBytes($srcFixture) + ([byte[]](0)))
        & $PSExe -NoProfile -File $Target -AuditBinary $bin2 | Out-Null
        Check "binary scan blocks a source-only fixture" ($LASTEXITCODE -ne 0) "scan passed but should not have"
    } finally {
        Remove-Item -LiteralPath $bin2 -Force -ErrorAction SilentlyContinue
    }
}

Write-Output ""
Write-Output "== 6. Repo restored =="
$dirty = & git -C $RepoRoot status --porcelain -- . ':(exclude)scripts/*'
Check "no probe left behind" (-not $dirty) ($dirty -join '; ')

Write-Output ""
Write-Output ("=" * 50)
Write-Output ("PASS " + $script:Pass + " / FAIL " + $script:Fail)
if ($script:Fail -gt 0) { exit 1 }
exit 0
