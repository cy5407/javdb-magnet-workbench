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
& pwsh -NoProfile -File $Target -AuditOnly | Out-Null
Check "audit-only exits 0 on a clean repo" ($LASTEXITCODE -eq 0) ("exit " + $LASTEXITCODE)

Write-Output ""
Write-Output "== 4. Red tests: each planted secret must fail the scan =="
# Every entry is a form production accepts. A regression that narrows the
# scanner shows up here as a [FAIL].
$probes = @(
    @{ n = 'plain 40-hex magnet';   f = 'README.md';                      s = 'magnet:?xt=urn:btih:ff11ee22dd33cc44bb55aa6699887766554433ff' },
    @{ n = 'upper-case MAGNET';     f = 'README.md';                      s = 'MAGNET:?XT=URN:BTIH:1234567890ABCDEF1234567890ABCDEF12345678' },
    @{ n = 'percent-encoded magnet';f = 'CLAUDE.md';                      s = 'magnet:?xt=urn%3Abtih%3Aff11ee22dd33cc44bb55aa6699887766554433ee' },
    @{ n = 'base32 v1 infohash';    f = 'CLAUDE.md';                      s = 'urn:btih:MFRGGZDFMZTWQ2LKNNWG23TPOBYXE43U' },
    @{ n = 'btmh v2 infohash';      f = 'app_logging.py';                 s = '# urn:btmh:1220abcdef0123456789abcdef0123456789abcdef0123456789abcdef01234567' },
    @{ n = '40-hex plus 2 (greedy)';f = 'rd_outcome_log.py';              s = '# urn:btih:0123456789abcdef0123456789abcdef01234567FF' },
    @{ n = 'RD token, spaces+quotes';f = 'pyproject.toml';                s = '# RD_API_TOKEN = "Zm9vYmFyYmF6cXV4MTIzNDU2Nzg5MA"' },
    @{ n = 'RD token, short';       f = 'sonar-project.properties';       s = '# RD_API_TOKEN=sh0rtTok' },
    @{ n = 'cookie with spaces';    f = 'requirements-ci.txt';            s = '# _jdb_session = LiveSessionValue123456' },
    @{ n = 'Bearer token68 charset';f = 'javdb_scraper.py';               s = '# Authorization: Bearer ab.cd~ef+gh/ij=klmnopqrst' },
    @{ n = 'secret in production rs';f = 'app/src-tauri/src/pending.rs';  s = '// cf_clearance=RealLookingClearanceValue999' }
)
foreach ($p in $probes) {
    $full = Join-Path $RepoRoot $p.f
    $orig = [System.IO.File]::ReadAllBytes($full)
    try {
        Add-Content -LiteralPath $full -Value ("`n" + $p.s) -Encoding utf8
        & pwsh -NoProfile -File $Target -AuditOnly | Out-Null
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
               "`nmagnet:?xt=urn:btih:aa11bb22cc33dd44ee55ff6677889900aabbccdd`n"
    [System.IO.File]::WriteAllBytes($u16,
        [System.Text.Encoding]::BigEndianUnicode.GetPreamble() +
        [System.Text.Encoding]::BigEndianUnicode.GetBytes($payload))
    & pwsh -NoProfile -File $Target -AuditOnly | Out-Null
    Check "blocks: secret inside a UTF-16BE file" ($LASTEXITCODE -ne 0) "scan passed but should not have"
} finally {
    [System.IO.File]::WriteAllBytes($u16, $origBytes)
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
