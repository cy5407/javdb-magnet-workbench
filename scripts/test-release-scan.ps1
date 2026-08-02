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

# Snapshot the working tree BEFORE any probe runs. Section 6 compares against
# this instead of asserting a clean tree: the suite writes payloads into real
# repo files, and the only thing it can honestly claim is that it put every one
# of them back.
#
# The snapshot is the full PATCH TEXT, not `git status` labels. Labels were the
# first attempt and they cannot see the failure they exist to catch: a file that
# is already ` M` before the run stays ` M` no matter what the suite writes into
# it, so an unrestored probe inside an in-progress edit reported success.
# `git diff HEAD` covers staged and unstaged content for tracked files;
# porcelain is kept alongside it only to catch added/removed untracked files,
# which produce no diff text.
$script:BaselineDiff = (& git -C $RepoRoot diff HEAD) -join "`n"
$script:BaselineDirty = @(& git -C $RepoRoot status --porcelain)

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
           'PSVersionTable', 'input', 'PID'
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
Write-Output "== 5f. Red test: whitespace grammar, derived from production =="
# Every earlier version of this test hand-picked a few characters (space+TAB,
# then VT/FF/NBSP) and every version left a hole — most recently U+001C-U+001F,
# which .NET's `\s` excludes but Python's str.strip() removes. Picking
# representatives cannot close a gap whose shape you do not know.
#
# So the boundary is GENERATED from the parser that actually reads cookies:
# every codepoint C where `chr(C).strip() == ''`, minus CR/LF (which must stay
# excluded, or a bare `<name>=` at end of line would swallow the next line).
# Two layers, because each alone is insufficient:
#   (a) a static parity assertion over the FULL set — exhaustive, but only
#       proves the regex class contains the characters, not that the scan uses
#       that class;
#   (b) one real scan carrying a payload for EVERY character in the set, with
#       -DumpUnmatched used to prove each one individually produced a match.
# Reading `.Source` straight off Get-Command's result throws under
# Set-StrictMode -Version Latest when the command does not exist — and the
# FIRST candidate is a Linux-layout venv path that a Windows checkout never
# has, so the suite died on the exact platform that ships. `npm run release`
# now always runs this file, so that would have aborted every Windows release.
function Resolve-FirstExecutable {
    param([string[]]$Candidates)
    foreach ($cand in $Candidates) {
        if (Test-Path -LiteralPath $cand) { return $cand }
        $cmd = Get-Command $cand -ErrorAction SilentlyContinue
        if ($null -ne $cmd -and $cmd.Source) { return $cmd.Source }
    }
    return $null
}

# Self-test the resolver before relying on it: every entry missing must yield
# $null rather than throw, and a real command must still resolve.
$resolverOk = $true
try {
    $probeNull = Resolve-FirstExecutable -Candidates @(
        (Join-Path $RepoRoot "no-such-dir/no-such-python"),
        "definitely-not-a-real-command-a7f3")
    if ($null -ne $probeNull) { $resolverOk = $false }
} catch { $resolverOk = $false }
Check "resolver returns null instead of throwing on missing candidates" $resolverOk "threw or returned a value"

$PyExe = Resolve-FirstExecutable -Candidates @(
    (Join-Path $RepoRoot ".venv/bin/python"),
    (Join-Path $RepoRoot ".venv/Scripts/python.exe"),
    "python3", "python")
Check "found a Python to derive the accept set from" ([bool]$PyExe) "no python on PATH and no .venv"

if ($PyExe) {
    # Deliberately asks production's own runtime, not a table copied into here.
    $sepCodes = @(& $PyExe -c "print(' '.join(str(c) for c in range(0x110000) if chr(c).strip()=='' and c not in (10,13)))").Trim() -split '\s+' |
        Where-Object { $_ } | ForEach-Object { [int]$_ }
    Check "derived a non-empty separator set from production" ($sepCodes.Count -gt 0) "python produced nothing"

    # (a) static parity: the scanner's class must accept every one of them.
    $targetText = Get-Content -LiteralPath $Target -Raw -Encoding utf8
    $clsMatch = [regex]::Match($targetText, "'Authorization:\[(?<cls>[^\]]+)\]")
    Check "found the separator class in build-release.ps1" ($clsMatch.Success) "pattern text changed shape"
    if ($clsMatch.Success) {
        # The class text is already regex source (`\u0009`, ranges); feed it to
        # the engine as-is rather than unescaping it into literal characters.
        $clsRx = [regex]("[" + $clsMatch.Groups['cls'].Value + "]")
        $missing = @($sepCodes | Where-Object { -not $clsRx.IsMatch([string][char]$_) })
        Check "scanner class covers every production separator" ($missing.Count -eq 0) (
            "not covered: " + (($missing | ForEach-Object { 'U+{0:X4}' -f $_ }) -join ','))
    }

    # (b) execution, one payload per character, one scan.
    $wsFile = Join-Path $RepoRoot "requirements-sidecar.txt"
    $wsOrig = [System.IO.File]::ReadAllBytes($wsFile)
    $dump = Join-Path ([System.IO.Path]::GetTempPath()) ("ws-dump-" + $PID + ".txt")
    try {
        $lines = foreach ($c in $sepCodes) {
            "# _jdb" + "_session" + [char]$c + "=" + [char]$c + "LiveSessionValue" + $c
        }
        [System.IO.File]::WriteAllBytes($wsFile, $wsOrig)
        Add-Content -LiteralPath $wsFile -Encoding utf8 -Value ($lines -join "`n")
        & $PSExe -NoProfile -File $Target -AuditOnly -DumpUnmatched $dump | Out-Null
        Check "scan blocks the generated whitespace payloads" ($LASTEXITCODE -ne 0) "scan passed but should not have"
        $dumped = if (Test-Path -LiteralPath $dump) { Get-Content -LiteralPath $dump -Raw -Encoding utf8 } else { "" }
        $uncaught = @($sepCodes | Where-Object { $dumped -notmatch ("LiveSessionValue" + $_ + '\b') })
        Check ("every one of " + $sepCodes.Count + " separators produced a match") ($uncaught.Count -eq 0) (
            "silently accepted: " + (($uncaught | ForEach-Object { 'U+{0:X4}' -f $_ }) -join ','))
    } finally {
        [System.IO.File]::WriteAllBytes($wsFile, $wsOrig)
        Remove-Item -LiteralPath $dump -Force -ErrorAction SilentlyContinue
    }
}

Write-Output ""
Write-Output "== 5h. Red test: redacted magnet exemption must not cover a trailing secret =="
# The old pattern exempted `<hash>` + ellipsis atomically, so
# `<redacted form><real secret>` scored zero hits. The exemption now lives in
# the allowlist as a complete literal, which only works if the matched value
# extends PAST the ellipsis — otherwise both strings reduce to the same value
# and the allowlist re-opens the same hole one layer down.
$mFile = Join-Path $RepoRoot "requirements-sidecar.txt"
$mOrig = [System.IO.File]::ReadAllBytes($mFile)
try {
    $redacted = "magnet:?xt=urn:bt" + "ih:0201592f..."
    [System.IO.File]::WriteAllBytes($mFile, $mOrig)
    Add-Content -LiteralPath $mFile -Encoding utf8 -Value ("# " + $redacted)
    & $PSExe -NoProfile -File $Target -AuditOnly | Out-Null
    Check "the redacted form itself still passes" ($LASTEXITCODE -eq 0) "allowlisted literal no longer matches"

    [System.IO.File]::WriteAllBytes($mFile, $mOrig)
    Add-Content -LiteralPath $mFile -Encoding utf8 -Value ("# " + $redacted + "aabbccddeeff00112233445566778899")
    & $PSExe -NoProfile -File $Target -AuditOnly | Out-Null
    Check "blocks: redacted prefix followed by a real hash" ($LASTEXITCODE -ne 0) "scan passed but should not have"
} finally {
    [System.IO.File]::WriteAllBytes($mFile, $mOrig)
}

Write-Output ""
Write-Output "== 5i. Red test: Bearer floor matches production (any non-empty token) =="
# realdebrid.py builds `Bearer ` + whatever the user pasted and imposes no
# minimum, so an 8- or 16-character floor is a grammar narrower than
# production's and a short token walks straight through.
$bFile = Join-Path $RepoRoot "requirements-sidecar.txt"
$bOrig = [System.IO.File]::ReadAllBytes($bFile)
try {
    foreach ($tok in @('x', 'ab', 'shortTok')) {
        [System.IO.File]::WriteAllBytes($bFile, $bOrig)
        Add-Content -LiteralPath $bFile -Encoding utf8 -Value ("# Authorization: " + "Bea" + "rer " + $tok)
        & $PSExe -NoProfile -File $Target -AuditOnly | Out-Null
        Check ("blocks: " + $tok.Length + "-char bearer token") ($LASTEXITCODE -ne 0) "scan passed but should not have"
    }
} finally {
    [System.IO.File]::WriteAllBytes($bFile, $bOrig)
}

Write-Output ""
Write-Output "== 5j. Red test: encoding detection must not sample only the head =="
# The heuristic probed the first 1024 bytes. A BOM-less UTF-16LE file whose
# head is CJK carries no NUL in that window, gets decoded as UTF-8, and
# everything after it is never scanned. Length here is chosen to overrun any
# fixed probe, and the payload sits at the very end.
$eFile = Join-Path $RepoRoot "requirements-sidecar.txt"
$eOrig = [System.IO.File]::ReadAllBytes($eFile)
try {
    # Pure CJK, no ASCII anywhere in the head. An earlier version wrote
    # "# " + CJK, and in UTF-16LE that "# " alone puts NULs in the first four
    # bytes — the 1024-byte probe found them and the test passed against the
    # very bug it was meant to catch. Mutation testing is what exposed that:
    # restoring the probe left this check green.
    $filler = (("中文說明填充" * 400) + "`n")
    $payload = "# _jdb" + "_session=LiveSessionValueAtTheVeryEnd`n"
    foreach ($enc in @(
        @{ n = 'UTF-16LE'; e = (New-Object System.Text.UnicodeEncoding($false, $false)) },
        @{ n = 'UTF-32LE'; e = (New-Object System.Text.UTF32Encoding($false, $false)) })) {
        [System.IO.File]::WriteAllBytes($eFile, $enc.e.GetBytes($filler + $payload))
        & $PSExe -NoProfile -File $Target -AuditOnly | Out-Null
        Check ("blocks: BOM-less " + $enc.n + " with a long non-ASCII head") ($LASTEXITCODE -ne 0) "scan passed but should not have"
    }
} finally {
    [System.IO.File]::WriteAllBytes($eFile, $eOrig)
}

Write-Output ""
Write-Output "== 5k. Every binary-allowlist entry must be something the exe embeds =="
# The binary list used to be a prefix filter over the source list, which
# admitted 23 entries including source-only fixtures — anything whose text
# merely began with a cookie name, trailing source punctuation and all.
# Splitting the data file fixed the mechanism but nothing stopped the same
# mistake being re-made by hand, so the criterion is now asserted: the ONLY
# thing an artifact legitimately embeds is COOKIES_TEMPLATE, therefore every
# entry must appear inside it as the binary scan decodes it (ASCII, each
# non-ASCII byte rendered as '?'). Exhaustive over the section, not a sample.
$allowLines = Get-Content -LiteralPath (Join-Path $ScriptDir "release-scan-allowlist.txt") -Encoding utf8
$binSection = @()
$inBin = $false
foreach ($l in $allowLines) {
    if ($l -cmatch '^#\s*\[binary\]\s*$') { $inBin = $true; continue }
    if ($l -cmatch '^#\s*\[source\]\s*$') { $inBin = $false; continue }
    if ($inBin -and $l -and -not $l.StartsWith('#')) { $binSection += $l }
}
Check "binary allowlist section is non-empty" ($binSection.Count -gt 0) "section missing or empty"
if ($binSection.Count -gt 0 -and $m.Success) {
    $tplRaw = $m.Groups[1].Value -replace '\\n', "`n"
    $tplRaw = $tplRaw -replace '\\"', '"'
    $tplBytes = [System.Text.Encoding]::UTF8.GetBytes($tplRaw)
    $tplAscii = -join ($tplBytes | ForEach-Object { if ($_ -lt 128) { [char]$_ } else { '?' } })
    $notEmbedded = @($binSection | Where-Object { -not $tplAscii.Contains($_) })
    Check ("all " + $binSection.Count + " binary entries appear in COOKIES_TEMPLATE") ($notEmbedded.Count -eq 0) (
        "not embedded: " + ($notEmbedded -join ' | '))
    # The converse direction of the original bug — a source fixture must not be
    # exempt inside a binary — needs to be checked by BEHAVIOUR, not by set
    # arithmetic over the same file both lists come from. The first attempt did
    # the latter and was vacuous: it removed every binary value from the source
    # set and then searched that remainder for binary values, so it could not
    # return a non-empty result under any input.
    #
    # This is a SAMPLE, not exhaustive: one source-only entry per pattern
    # family, chosen deterministically. Running all of them would mean one
    # process launch each. The count actually covered is printed so a reader is
    # not left assuming full coverage.
    $srcOnly = @($allowLines | Where-Object { $_ -and -not $_.StartsWith('#') -and $binSection -cnotcontains $_ })
    $samples = @()
    # Split so this file does not become a scan hit itself — same convention the
    # payloads above use. Spelling the cookie names out here made the source
    # scan flag this very line.
    $sampleRx = @(
        '^magnet:\?xt=',
        '^_jdb' + '_session=',
        '^cf' + '_clearance=',
        '^[Bb]ea' + 'rer ')
    foreach ($rx in $sampleRx) {
        $pick = @($srcOnly | Where-Object { $_ -cmatch $rx }) | Select-Object -First 1
        if ($pick) { $samples += $pick }
    }
    Write-Output ("  (binary 拒絕抽樣：" + $samples.Count + " / " + $srcOnly.Count + " 條 source-only 條目)")
    foreach ($sample in $samples) {
        $sbin = Join-Path ([System.IO.Path]::GetTempPath()) ("relscan-s-" + [guid]::NewGuid().ToString("N") + ".bin")
        try {
            [System.IO.File]::WriteAllBytes($sbin,
                ([byte[]](0,1,77,90)) + [System.Text.Encoding]::UTF8.GetBytes($sample) + ([byte[]](0)))
            & $PSExe -NoProfile -File $Target -AuditBinary $sbin | Out-Null
            Check ("binary scan rejects source-only fixture: " + $sample.Substring(0, [Math]::Min(28, $sample.Length))) (
                $LASTEXITCODE -ne 0) "scan passed but should not have"
        } finally {
            Remove-Item -LiteralPath $sbin -Force -ErrorAction SilentlyContinue
        }
    }
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
Write-Output "== 5n. -DumpUnmatched must fail closed, never append to stale content =="
# The dump is what a maintainer reads before adding literals to the allowlist,
# so a line in it that came from a PREVIOUS run is a bad decision waiting to
# happen. Truncation used to run before $ErrorActionPreference = "Stop", so a
# failed delete was a non-terminating error and the run appended anyway.
$dumpDir = Join-Path ([System.IO.Path]::GetTempPath()) ("dump-dir-" + $PID)
try {
    New-Item -ItemType Directory -Path $dumpDir -Force | Out-Null
    Set-Content -LiteralPath (Join-Path $dumpDir "stale.txt") -Value "stale" -Encoding utf8
    $out = & $PSExe -NoProfile -File $Target -AuditOnly -DumpUnmatched $dumpDir 2>&1 | Out-String
    Check "a directory as the dump path aborts" ($LASTEXITCODE -ne 0) ("exit " + $LASTEXITCODE)
    Check "and says why, without prompting" (
        ($out -clike '*must be a file path*') -and ($out -cnotlike '*Are you sure*')) $out.Trim()
} finally {
    Remove-Item -LiteralPath $dumpDir -Recurse -Force -ErrorAction SilentlyContinue
}

# And the happy path really does truncate rather than append.
$dumpFile = Join-Path ([System.IO.Path]::GetTempPath()) ("dump-file-" + $PID + ".txt")
try {
    Set-Content -LiteralPath $dumpFile -Value "StaleValueFromAPreviousRun" -Encoding utf8
    & $PSExe -NoProfile -File $Target -AuditOnly -DumpUnmatched $dumpFile | Out-Null
    $after = if (Test-Path -LiteralPath $dumpFile) { Get-Content -LiteralPath $dumpFile -Raw -Encoding utf8 } else { "" }
    Check "previous run's contents are gone" ($after -cnotlike '*StaleValueFromAPreviousRun*') $after
} finally {
    Remove-Item -LiteralPath $dumpFile -Force -ErrorAction SilentlyContinue
}

Write-Output ""
Write-Output "== 5p. The allowlist must contain no dead exemptions =="
# An entry that matches nothing is a standing permission for a value the repo
# no longer has. It costs nothing until the day that exact string comes back as
# a real secret, at which point it is a pre-approved hole. 79 of them had
# accumulated across earlier rounds — every time the value class widened, the
# previously-recorded (shorter) values stopped matching and nobody noticed,
# because -DumpUnmatched only ever reported what to ADD.
#
# Two checks, not one. Asserting only "the run reports nothing stale" is
# satisfied just as well by a detector that reports nothing ever — mutation
# testing confirmed exactly that: disabling the warning left this section green.
# So the positive control runs first: inject an entry that cannot possibly
# match anything and require it to be named.
$allowPath = Join-Path $ScriptDir "release-scan-allowlist.txt"
$allowOrig = [System.IO.File]::ReadAllBytes($allowPath)
# Two canaries, because they fail differently.
#   plain — nothing resembling it exists anywhere; catches a detector that is
#           simply switched off.
#   case  — an UPPER-CASE variant of an entry that IS still matched. Usage was
#           tracked in a case-insensitive hashtable while matching used
#           `-ccontains`, so the live lower-case value marked this variant as
#           used and it stayed silently pre-approved. The plain canary cannot
#           see that class at all.
$canaries = @(
    @{ n = 'plain'; v = '_jdb' + '_session=CanaryThatMatchesNothingAnywhere' },
    @{ n = 'case-variant'; v = ('_jdb' + '_session=XXX').ToUpperInvariant() })
$canary = $canaries[0].v
try {
    # Insert by LINE, not by searching for "`n# [binary]`n". A Windows checkout
    # with core.autocrlf=true stores this file with CRLF, that literal never
    # matched, and the canary landed AFTER the binary header — where the source
    # detector correctly ignores it. The positive control then failed, and since
    # release:test is now mandatory, that failure blocked every `npm run release`
    # on a CRLF checkout. Reproduced by converting the file and re-running:
    # PASS 66 / FAIL 1.
    $allowText = [System.Text.Encoding]::UTF8.GetString($allowOrig)
    $allowSplit = [regex]::Split($allowText, "`r?`n")
    $binIdx = -1
    for ($i = 0; $i -lt $allowSplit.Count; $i++) {
        if ($allowSplit[$i] -cmatch '^#\s*\[binary\]\s*$') { $binIdx = $i; break }
    }
    $injectedLines = if ($binIdx -ge 0) {
        @($allowSplit[0..($binIdx - 1)]) + @($canary) + @($allowSplit[$binIdx..($allowSplit.Count - 1)])
    } else {
        @($allowSplit) + @($canary)
    }
    [System.IO.File]::WriteAllBytes($allowPath,
        [System.Text.Encoding]::UTF8.GetBytes(($injectedLines -join "`n")))
    $canaryOut = & $PSExe -NoProfile -File $Target -AuditOnly 2>&1 | Out-String
    # The report deliberately prints line + digest, never the literal, so match
    # on the digest. Asserting on the value would force the scanner to echo
    # allowlist contents into build logs — the exact thing that report avoids.
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $canaryDigest = [BitConverter]::ToString(
            $sha.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($canary))).Replace('-', '').Substring(0, 12)
    } finally { $sha.Dispose() }
    Check "stale-entry detection actually fires" ($canaryOut -clike ('*' + $canaryDigest + '*')) (
        "injected a never-matching entry and the audit did not name its digest")
    Check "stale-entry report does not echo the value" ($canaryOut -cnotlike ('*' + $canary + '*')) (
        "the allowlist literal was printed to the console")
} finally {
    [System.IO.File]::WriteAllBytes($allowPath, $allowOrig)
}

# The case-variant canary, injected and checked the same way.
try {
    $caseCanary = $canaries[1].v
    $allowText2 = [System.Text.Encoding]::UTF8.GetString($allowOrig)
    $split2 = [regex]::Split($allowText2, "`r?`n")
    $binIdx2 = -1
    for ($i = 0; $i -lt $split2.Count; $i++) {
        if ($split2[$i] -cmatch '^#\s*\[binary\]\s*$') { $binIdx2 = $i; break }
    }
    $lines2 = if ($binIdx2 -ge 0) {
        @($split2[0..($binIdx2 - 1)]) + @($caseCanary) + @($split2[$binIdx2..($split2.Count - 1)])
    } else { @($split2) + @($caseCanary) }
    [System.IO.File]::WriteAllBytes($allowPath,
        [System.Text.Encoding]::UTF8.GetBytes(($lines2 -join "`n")))
    $caseOut = & $PSExe -NoProfile -File $Target -AuditOnly 2>&1 | Out-String
    $sha2 = [System.Security.Cryptography.SHA256]::Create()
    try {
        $caseDigest = [BitConverter]::ToString(
            $sha2.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($caseCanary))).Replace('-', '').Substring(0, 12)
    } finally { $sha2.Dispose() }
    Check "stale detection is case-sensitive" ($caseOut -clike ('*' + $caseDigest + '*')) (
        "an upper-case variant of a live entry was treated as used")
} finally {
    [System.IO.File]::WriteAllBytes($allowPath, $allowOrig)
}

$auditOut = & $PSExe -NoProfile -File $Target -AuditOnly 2>&1 | Out-String
Check "audit run reports no stale allowlist entries" (
    $auditOut -cnotlike '*matched nothing this run*') (
    ($auditOut -split "`n" | Where-Object { $_ -clike '*matched nothing*' }) -join '')

Write-Output ""
Write-Output "== 5q. A CRLF checkout must behave identically =="
# `core.autocrlf=true` is the default on many Windows clones, and `npm run
# release` runs this suite there. Line-ending assumptions in the suite itself
# have already broken that path once (the stale-entry canary was inserted by
# searching for an LF-delimited marker and landed in the wrong section).
$crlfPath = Join-Path $ScriptDir "release-scan-allowlist.txt"
$crlfOrig = [System.IO.File]::ReadAllBytes($crlfPath)
try {
    $asText = [System.Text.Encoding]::UTF8.GetString($crlfOrig)
    $asCrlf = ([regex]::Split($asText, "`r?`n")) -join "`r`n"
    [System.IO.File]::WriteAllBytes($crlfPath, [System.Text.Encoding]::UTF8.GetBytes($asCrlf))

    $crlfAudit = & $PSExe -NoProfile -File $Target -AuditOnly 2>&1 | Out-String
    Check "CRLF allowlist still scans clean" ($LASTEXITCODE -eq 0) ("exit " + $LASTEXITCODE)
    Check "CRLF allowlist reports no stale entries" (
        $crlfAudit -cnotlike '*matched nothing this run*') "entries stopped matching under CRLF"

    # Same section-splitting logic the canary uses, exercised against CRLF.
    $crlfLines = Get-Content -LiteralPath $crlfPath -Encoding utf8
    $binHdr = @($crlfLines | Where-Object { $_ -cmatch '^#\s*\[binary\]\s*$' })
    Check "binary section header is still found under CRLF" ($binHdr.Count -eq 1) (
        "found " + $binHdr.Count + " binary headers")
} finally {
    [System.IO.File]::WriteAllBytes($crlfPath, $crlfOrig)
}

Write-Output ""
Write-Output "== 5r. Direct build invocation must run the red tests too =="
# `npm run release` chaining release:test only covers the npm entry point.
# docs/platform/windows-build.md documents `pwsh -File scripts\build-release.ps1`
# directly, and that produced artifacts without ever running this suite.
# Executing a real build here would take minutes, so this is a structural
# assertion on the build script plus a behavioural one that audit modes do NOT
# recurse into the suite.
$buildText = Get-Content -LiteralPath $Target -Raw -Encoding utf8
Check "build script invokes the red-test suite" (
    $buildText -clike '*test-release-scan.ps1*') "no reference to this suite in build-release.ps1"
Check "build script aborts when the red tests fail" (
    $buildText -cmatch 'Scanner red tests failed') "no failure branch after the invocation"
$auditRun = & $PSExe -NoProfile -File $Target -AuditOnly 2>&1 | Out-String
Check "audit modes do not recurse into the suite" (
    $auditRun -cnotlike '*Step 0: scanner red tests*') "audit mode ran the red tests; that recurses"

Write-Output ""
Write-Output "== 5m. The shipping path must run this suite =="
# This file passing proves nothing if nothing runs it. The gate lives in
# build-release.ps1's Step 0 (asserted in 5r) rather than in the npm wrapper,
# because `pwsh -File scripts\build-release.ps1` is a documented entry point and
# a wrapper-level gate does not cover it. The wrapper therefore must NOT chain
# release:test as well — that ran this whole suite twice on the primary path
# for no additional coverage.
$pkg = Get-Content -LiteralPath (Join-Path $RepoRoot "app/package.json") -Raw -Encoding utf8 | ConvertFrom-Json
$relCmd = $pkg.scripts.release
Check "npm run release invokes build-release.ps1" ($relCmd -clike '*build-release.ps1*') ("release = " + $relCmd)
Check "npm run release does not also chain release:test" ($relCmd -cnotlike '*release:test*') (
    "the suite would run twice; the gate is already inside the build script")
Check "release:test still exists for standalone runs" (
    [bool]$pkg.scripts.'release:test') "no release:test script"
# Same host as the shipping command, so a standalone run exercises the engine
# that will actually do the scanning.
Check "release:test runs on the same host as release" (
    ($pkg.scripts.'release:test' -clike 'powershell *') -and ($relCmd -clike 'powershell -ExecutionPolicy*')) (
    "release:test = " + $pkg.scripts.'release:test')

Write-Output ""
Write-Output "== 6. Repo restored =="
$nowDiff = (& git -C $RepoRoot diff HEAD) -join "`n"
$nowDirty = @(& git -C $RepoRoot status --porcelain)
$introduced = @($nowDirty | Where-Object { $script:BaselineDirty -cnotcontains $_ })
Check "no probe left behind (file contents)" ($nowDiff -ceq $script:BaselineDiff) (
    "working-tree content differs from the pre-run snapshot; a probe was not restored")
Check "no probe left behind (untracked files)" ($introduced.Count -eq 0) ($introduced -join '; ')

Write-Output ""
Write-Output ("=" * 50)
Write-Output ("PASS " + $script:Pass + " / FAIL " + $script:Fail)
if ($script:Fail -gt 0) { exit 1 }
exit 0
