# Codex review 紀錄 — release 機密掃描（第 2 輪）

命令：`codex review --commit 3f55ec0`　執行時間：2026-08-02T17:11:26+08:00

```
OpenAI Codex v0.146.0
--------
workdir: /home/cy5407/javdb-magnet-workbench
model: gpt-5.6-sol
provider: openai
approval: on-request
sandbox: workspace-write [workdir, /tmp, $TMPDIR]
reasoning effort: high
reasoning summaries: none
session id: 019fc1be-12ac-7361-bbed-9357005c9b26
--------
user
commit 3f55ec0: release blocker + 七項掃描缺口修正
exec
/bin/bash -lc "cat /home/cy5407/.codex/skills/subagent-orchestration/SKILL.md && printf '\\n---RULE FILES---\\n' && find .. -name AGENTS.md -o -name AGENTS.override.md | sort && printf '\\n---STATUS---\\n' && git status --short && printf '\\n---COMMIT---\\n' && git show --stat --oneline --decorate --no-renames 3f55ec0 && printf '\\n---FILES---\\n' && git diff-tree --no-commit-id --name-status -r 3f55ec0" in /home/cy5407/javdb-magnet-workbench
 succeeded in 654ms:
../.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/zerocopy-0.8.48/AGENTS.md
../.cargo/registry/src/index.crates.io-1949cf8c6b5b557f/zerocopy-0.8.50/AGENTS.md
../.codex/.tmp/plugins/plugins/build-web-apps/skills/react-best-practices/AGENTS.md
../.codex/.tmp/plugins/plugins/build-web-apps/skills/supabase-best-practices/AGENTS.md
../.codex/.tmp/plugins/plugins/zoom/AGENTS.md
../.codex/AGENTS.md
../.local/share/agent-audit/backups/install-20260728T112059+0800/.codex/AGENTS.md
../Desktop/程式語言/PornActressDB-Rust/AGENTS.md
../PornActressDB-Rust/AGENTS.md
../exec-bench/AGENTS.md
../exec-bench/benchmark-standard/template/AGENTS.md
../exec-bench/experiments/ledger-round2-claude-opus5-high-rep1-20260729/AGENTS.md
../exec-bench/experiments/ledger-round2-claude-opus5-high-rep2-20260729/AGENTS.md
../exec-bench/experiments/ledger-round2-claude-opus5-high-rep3-20260729/AGENTS.md
../exec-bench/experiments/ledger-round2-claude-opus5-high-rep4-20260729/AGENTS.md
../exec-bench/experiments/ledger-round2-claude-opus5-high-rep5-20260729/AGENTS.md
../exec-bench/experiments/ledger-round2-claude-opus5-high-workflow8-rep1-20260730/AGENTS.md
../exec-bench/experiments/ledger-round2-claude-opus5-high-xhigh-20260729/AGENTS.md
../exec-bench/experiments/ledger-round2-codex-luna-20260729/AGENTS.md
../exec-bench/experiments/ledger-round2-codex-luna-max-20260729/AGENTS.md
../exec-bench/experiments/ledger-round2-codex-sol-high-rep1-20260729/AGENTS.md
../exec-bench/experiments/ledger-round2-codex-sol-high-rep2-20260729/AGENTS.md
../exec-bench/experiments/ledger-round2-codex-sol-high-rep3-20260729/AGENTS.md
../exec-bench/experiments/ledger-round2-codex-sol-high-rep4-20260729/AGENTS.md
../exec-bench/experiments/ledger-round2-codex-sol-high-rep5-20260729/AGENTS.md
../exec-bench/experiments/ledger-round2-codex-terra-high-20260729/AGENTS.md
../exec-bench/experiments/ledger-round2-codex-terra-high-rep2-20260729/AGENTS.md
../exec-bench/experiments/ledger-round2-codex-terra-high-rep3-20260729/AGENTS.md
../exec-bench/experiments/ledger-round2-codex-terra-high-rep4-20260729/AGENTS.md
../exec-bench/experiments/ledger-round2-codex-terra-high-rep5-20260729/AGENTS.md
../exec-bench/experiments/ledger-round2-gemini31pro-high-autonomous-20260729/AGENTS.md
../exec-bench/experiments/ledger-round2-strengthened-20260730/AGENTS.md
../exec-bench/experiments/ledger-strengthened-claude-opus5-high-rep1-20260730/AGENTS.md
../exec-bench/experiments/ledger-strengthened-claude-opus5-high-rep2-20260730/AGENTS.md
../exec-bench/experiments/ledger-strengthened-codex-sol-high-rep1-20260730/AGENTS.md
../exec-bench/experiments/ledger-strengthened-codex-sol-high-rep2-20260730/AGENTS.md
../exec-bench/experiments/ledger-strengthened-codex-terra-high-rep1-20260730/AGENTS.md
../exec-bench/experiments/ledger-strengthened-codex-terra-high-rep2-20260730/AGENTS.md
../exec-bench/experiments/ledger-strengthened-isolated-claude-opus5-high-rep1-20260730/AGENTS.md
../exec-bench/experiments/ledger-strengthened-isolated-claude-opus5-high-rep2-20260730/AGENTS.md
../exec-bench/experiments/ledger-strengthened-isolated-claude-opus5-high-retry1-20260730/AGENTS.md
../exec-bench/experiments/ledger-strengthened-isolated-codex-sol-high-rep1-20260730/AGENTS.md
../exec-bench/experiments/ledger-strengthened-isolated-codex-sol-high-rep2-20260730/AGENTS.md
../exec-bench/experiments/ledger-strengthened-isolated-codex-terra-high-rep1-20260730/AGENTS.md
../exec-bench/experiments/ledger-strengthened-isolated-codex-terra-high-rep2-20260730/AGENTS.md
../exec-bench/experiments/ledger-strengthened-terra-repair-pass2-paired-20260730/AGENTS.md

---STATUS---
?? docs/reviews/

---COMMIT---
3f55ec0 (HEAD -> master) fix: 修復 release blocker 與七項掃描缺口，並讓這道 gate 首次可實際執行
 scripts/build-release.ps1 | 572 ++++++++++++++++++++++++++++------------------
 1 file changed, 346 insertions(+), 226 deletions(-)

---FILES---
M	scripts/build-release.ps1

  → 讀取 commit diff、release 契約與適用規則
  • 逐段驗證 PowerShell 路徑、失敗模式與跨腳本呼叫端
  • 執行可用的靜態/動態檢查並核實候選問題
  • 依 JSON schema 輸出去重後 findings
exec
/bin/bash -lc "printf '%s\\n' '---ROOT LIST---'; ls -la; printf '%s\\n' '---LOCAL RULES---'; for f in AGENTS.override.md AGENTS.md scripts/AGENTS.override.md scripts/AGENTS.md; do if [ -f \""'$f" ]; then echo "### $f"; nl -ba "$f"; fi; done; printf '"'%s\\n' '---DIFF---'; git diff 3f55ec0"'^ 3f55ec0 -- scripts/build-release.ps1; printf '"'%s\\n' '---CURRENT NUMBERED---'; nl -ba scripts/build-release.ps1" in /home/cy5407/javdb-magnet-workbench
 succeeded in 0ms:
---ROOT LIST---
total 64844
drwxrwxr-x 19 cy5407 cy5407     4096 Aug  1 15:30 .
drwxr-x--- 36 cy5407 cy5407     4096 Aug  2 12:35 ..
dr-xr-xr-x  2 cy5407 cy5407       40 Aug  2 17:11 .agents
drwxrwxr-x  2 cy5407 cy5407     4096 Jul 27 21:45 .claude
dr-xr-xr-x  2 cy5407 cy5407       40 Aug  2 17:11 .codex
-rw-rw-r--  1 cy5407 cy5407     1213 Jul 27 01:04 .env.example
drwxrwxr-x  7 cy5407 cy5407     4096 Aug  2 17:11 .git
drwxrwxr-x  3 cy5407 cy5407     4096 Jul 27 01:04 .github
-rw-rw-r--  1 cy5407 cy5407      653 Jul 27 01:04 .gitignore
drwxrwxr-x  3 cy5407 cy5407     4096 Jul 27 21:45 .pytest_cache
-rw-rw-r--  1 cy5407 cy5407      648 Jul 27 01:04 .trivyignore
drwxrwxr-x  4 cy5407 cy5407     4096 Jul 27 01:05 .venv
-rw-rw-r--  1 cy5407 cy5407     6594 Aug  2 17:09 CLAUDE.md
-rw-rw-r--  1 cy5407 cy5407     9803 Aug  1 15:28 PROGRESS.md
-rw-rw-r--  1 cy5407 cy5407      591 Jul 27 01:04 PSScriptAnalyzerSettings.psd1
-rw-rw-r--  1 cy5407 cy5407    18370 Aug  2 17:09 README.md
drwxrwxr-x  2 cy5407 cy5407     4096 Aug  2 17:10 __pycache__
drwxrwxr-x  6 cy5407 cy5407     4096 Jul 27 01:06 app
-rw-rw-r--  1 cy5407 cy5407     5178 Aug  2 17:09 app_logging.py
drwxrwxr-x  9 cy5407 cy5407     4096 Aug  2 17:11 docs
-rw-rw-r--  1 cy5407 cy5407    23673 Aug  1 15:28 implementation-notes.md
-rw-rw-r--  1 cy5407 cy5407     4419 Aug  2 17:09 javdb_scraper.py
-rw-rw-r--  1 cy5407 cy5407  5334016 Jul 27 01:04 javdbmagnet.exe
drwxrwxr-x  3 cy5407 cy5407     4096 Jul 27 21:45 legacy
drwxrwxr-x  2 cy5407 cy5407     4096 Jul 27 01:04 output
drwxrwxr-x  2 cy5407 cy5407     4096 Jul 28 12:28 prompt
-rw-rw-r--  1 cy5407 cy5407     1109 Aug  2 17:09 pyproject.toml
-rw-rw-r--  1 cy5407 cy5407     9629 Aug  2 17:10 rd_outcome_log.py
-rw-rw-r--  1 cy5407 cy5407    21989 Aug  1 14:02 realdebrid.py
-rw-rw-r--  1 cy5407 cy5407      475 Aug  2 17:09 requirements-ci.txt
-rw-rw-r--  1 cy5407 cy5407     1373 Jul 27 01:04 requirements-sidecar.txt
drwxrwxr-x  3 cy5407 cy5407     4096 Aug  2 15:33 scripts
drwxrwxr-x  3 cy5407 cy5407     4096 Aug  1 14:43 sidecar
-rw-rw-r--  1 cy5407 cy5407 60841441 Jul 27 01:04 sidecar.exe
-rw-rw-r--  1 cy5407 cy5407     1708 Aug  2 17:09 sonar-project.properties
drwxrwxr-x  4 cy5407 cy5407     4096 Jul 27 01:04 spikes
drwxrwxr-x  3 cy5407 cy5407     4096 Aug  2 15:23 tests
---LOCAL RULES---
---DIFF---
diff --git a/scripts/build-release.ps1 b/scripts/build-release.ps1
index daf1416..d2f0de9 100644
--- a/scripts/build-release.ps1
+++ b/scripts/build-release.ps1
@@ -35,6 +35,14 @@
 # Or from app/:
 #     npm run release
 
+param(
+    # Run ONLY the source secret scan and exit. No build, no staging, no zip.
+    # Added so this gate can actually be executed and red-tested on its own:
+    # a full release run costs minutes of PyInstaller + cargo before it would
+    # ever reach the scan.
+    [switch]$AuditOnly
+)
+
 $ErrorActionPreference = "Stop"
 Set-StrictMode -Version Latest
 
@@ -75,6 +83,312 @@ function FailExit($msg) {
 # ---------------------------------------------------------------------------
 # Step 0: Prepare release/ output dir
 # ---------------------------------------------------------------------------
+
+$Patterns = @(
+    # Every pattern below is matched case-INSENSITIVELY (see $RxOpts). URI
+    # schemes are case-insensitive per RFC 3986, and this project's own parser
+    # agrees: sidecar.py lower-cases before its `startswith("magnet:")` check
+    # and _REDACT_MAGNET_RX carries re.IGNORECASE. A case-sensitive scan would
+    # therefore miss `MAGNET:?XT=URN:BTIH:...` — a string production happily
+    # accepts and interns. Verified: register_magnets returns ok for the
+    # upper-case form while the old pattern did not match it at all.
+    # GREEDY `{40,}`, not `{40}` and not `{40}(?!hex)`. All three were tried:
+    #   {40}            — a 42-hex value matches its first 40 chars, and if
+    #                     those 40 are allowlisted the real value passes.
+    #   {40}(?![hex])   — a 42-hex value then matches NOTHING AT ALL (the
+    #                     lookahead fails at every start offset), which is a
+    #                     bigger hole than the one it was meant to close. This
+    #                     was caught by executing the red test, not by reading.
+    #   {40,}           — consumes the whole run, so anything longer than an
+    #                     allowlisted literal is a distinct value and fails.
+    @{ name = 'urn:btih:<40+hex>';           rx = 'urn:btih:[a-fA-F0-9]{40,}' },
+    # BitTorrent v1 infohashes are 40 hex OR 32 base32 (BEP 9); v2 uses a
+    # different URN entirely (`urn:btmh:`, BEP 52). An earlier commit message
+    # claimed "64-hex btih v2" — that form does not exist. Cover all three.
+    @{ name = 'urn:btih:<32+base32>';        rx = 'urn:btih:[A-Z2-7]{32,}' },
+    @{ name = 'urn:btmh: (BitTorrent v2)';   rx = 'urn:bt' + 'mh:[a-fA-F0-9]{10,}' },
+    # `{16,}` rather than `+`: redact_magnet()'s output is a fixed 8 hex chars,
+    # so `+` made this pattern flag the project's own CORRECTLY REDACTED form.
+    # Real v1 infohashes are 40 hex (or 32 base32); 16 is a safe floor that
+    # passes the 8-char redacted form and catches every real length.
+    @{ name = 'magnet:?xt=';                 rx = 'magnet:\?xt=urn:bt' + '[im]h:[a-zA-Z0-9]{16,}' },
+    # Length floors and separator grammar now follow what PRODUCTION accepts,
+    # not what a "realistic" secret looks like. secret_store.rs takes 1-255
+    # ASCII alphanumerics; legacy_import.rs trims whitespace around `=` and
+    # strips surrounding quotes; parse_cookie_string trims each `k = v` pair.
+    # A scanner narrower than the parser is a scanner with a documented hole,
+    # so `\s*`, optional quotes and a floor of 1 are all deliberate. The cost
+    # is that short test fixtures now match — they are listed in
+    # $AllowedLiterals, which is exactly the reviewable-diff tradeoff this
+    # design already makes everywhere else.
+    @{ name = 'Cloudflare clearance cookie'; rx = 'cf' + '_clearance\s*=\s*["'']?' + '[A-Za-z0-9_.~+/=-]{1,}' },
+    @{ name = 'Cloudflare bot cookie';       rx = '__cf' + '_bm\s*=\s*["'']?' + '[A-Za-z0-9_.~+/=-]{1,}' },
+    @{ name = 'JavDB session cookie';        rx = '_jdb' + '_session\s*=\s*["'']?' + '[A-Za-z0-9_.~+/=-]{1,}' },
+    @{ name = 'remember_me_token=';          rx = 'remember_me_token\s*=\s*["'']?' + '[A-Za-z0-9_.~+/=-]{1,}' },
+    # token68 (RFC 7235) allows -._~+/ and trailing '='; the old [A-Za-z0-9_-]
+    # stopped at the first '.' and reported a truncated match.
+    @{ name = 'Authorization bearer header'; rx = 'Authorization:\s*' + 'Bearer\s+' + '[A-Za-z0-9_.~+/=-]{8,}' },
+    @{ name = 'Bearer <token>';              rx = 'Bearer\s+' + '[A-Za-z0-9_.~+/=-]{16,}' },
+    @{ name = 'RD_API_TOKEN=<value>';        rx = 'RD_API' + '_TOKEN\s*=\s*["'']?' + '[A-Za-z0-9_-]{1,}' }
+)
+
+# All regex evaluation in this script goes through these options. See the
+# comment above $Patterns for why IgnoreCase is not optional here.
+$RxOpts = [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
+
+$ScanFail = $false
+$BinaryHitCount = 0
+# We decode the binary bytes both as ASCII *and* UTF-16LE because PE
+# images routinely embed strings in both encodings:
+#   - ASCII / UTF-8 covers Rust &str literals, format!() output, and
+#     anything wired through libc-style APIs.
+#   - UTF-16LE covers strings handed to the Win32 wide API (e.g. a
+#     `let path = format!("HKCU\\...\\{}", token);` later passed to
+#     `RegOpenKeyExW`), which would otherwise sail past an ASCII-only
+#     scan even though the secret material is plainly readable in a
+#     hex dump.
+# Running both passes is cheap (two regex sweeps over the same byte
+# blob); failing to do it would silently halve the scan's coverage.
+$Encodings = @(
+    @{ label = 'ASCII';      encoding = [System.Text.Encoding]::ASCII },
+    @{ label = 'UTF-16LE';   encoding = [System.Text.Encoding]::Unicode }
+)
+
+function Invoke-SourceSecretScan {
+
+    # ---------------------------------------------------------------------------
+    # Step 7: Source secret scan — over EVERY tracked file
+    #
+    # This used to derive its file list from `git diff <origin/HEAD>..HEAD` plus
+    # the working-tree diff. That made coverage depend on where HEAD happened to
+    # sit: cutting a release from an already-pushed master left both diffs empty,
+    # so the scan walked ZERO files and still wrote `source_secret_hits: 0` into
+    # the manifest — a vacuous pass that read exactly like a real one. It was
+    # found the hard way: a magnet literal sat in verify-windows-build.ps1 from
+    # the commit that introduced it and was never once scanned, until an
+    # unrelated edit to that file finally pulled it into the diff.
+    #
+    # The file list now comes from `git ls-files`, so coverage is a property of
+    # the repo rather than of the branch topology. Content is read from disk, so
+    # uncommitted edits to tracked files are scanned as they actually are.
+    # Untracked files are deliberately out of scope: they are neither committed
+    # nor shipped inside the portable zip.
+    # ---------------------------------------------------------------------------
+    Step "Source secret scan (all tracked text files)"
+    # -z + NUL split: without it git quotes paths containing non-ASCII or control
+    # characters ("\303\251.md"), and the quoted name matches nothing on disk — the
+    # file is then silently dropped from the scan.
+    # Windows PowerShell 5.1 decodes native-command output using the console code
+    # page, not UTF-8. A tracked filename with non-ASCII characters would come back
+    # mangled, Test-Path would then fail to resolve it, and the entry would vanish
+    # from the scan. Force UTF-8 for the duration of the git call.
+    $prevOutEnc = [Console]::OutputEncoding
+    try {
+        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
+        $lsRaw = & git -C $RepoRoot ls-files -z
+        $lsExit = $LASTEXITCODE
+    } finally {
+        [Console]::OutputEncoding = $prevOutEnc
+    }
+    if ($lsExit -ne 0) {
+        Write-Error "FATAL: source-secret-scan git ls-files failed (exit $lsExit). Refusing to ship a release without a source scan."
+        exit 1
+    }
+    $sourceFiles = @(($lsRaw -join "") -split "`0" | Where-Object { $_ } | Sort-Object -Unique)
+    $skipExt = @('.exe', '.msi', '.zip', '.7z', '.png', '.ico', '.icns', '.dll')
+
+    # Known-synthetic literals, allowlisted BY EXACT VALUE rather than by file.
+    #
+    # The previous design skipped whole files (commands.rs, legacy_import.rs,
+    # tests/, *.test.ts, four prose docs, and this script). That exempted ~23 text
+    # files INCLUDING production Rust and the gate itself: any real token later
+    # pasted into them would never have been seen. "Every tracked file" was not
+    # true.
+    #
+    # Now nothing is exempt. Every tracked text file is scanned, and a match only
+    # passes if its exact text appears below. Each entry is a fixture whose
+    # synthetic nature is self-evident (DEADBEEF / repeated nibbles / sequential
+    # counters / obvious placeholder session names), except the one PoC hash in the
+    # security-audit archive, which demonstrates a dedupe-key collision where the
+    # point is that the SAME arbitrary string appears twice.
+    #
+    # Adding an entry here is a visible, reviewable diff line — unlike adding a
+    # file to a skip list, which blinds the scanner to everything in that file
+    # forever. A NEW fixture will fail the build until it is listed; that is the
+    # intended cost.
+    $AllowedLiterals = @(
+        'urn:btih:0201592fDEADBEEF0201592fDEADBEEF02015920',
+        'urn:btih:0201592fdeadbeef0201592fdeadbeef02015920',
+        'urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF',
+        'urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEF',
+        'urn:btih:0201592f00000000000000000000000000000001',
+        'urn:btih:0201592f00000000000000000000000000000002',
+        'urn:btih:0000000000000000000000000000000000000001',
+        'urn:btih:0000000000000000000000000000000000000002',
+        'urn:btih:0000000000000000000000000000000000000003',
+        'urn:btih:0123456789abcdef0123456789abcdef01234567',
+        'urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
+        'urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
+        'urn:btih:cccccccccccccccccccccccccccccccccccccccc',
+        'urn:btih:ABCDEF0123456789ABCDEF0123456789ABCDEF01',
+        'urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
+        'urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
+        'urn:btih:cccccccccccccccccccccccccccccccc',
+        # Dedupe-key collision PoC (prompt/security-audit-fixes-2026-07-28.md).
+        'urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a',
+        'magnet:?xt=urn:btih:0201592fDEADBEEF0201592fDEADBEEF02015920',
+        'magnet:?xt=urn:btih:0201592fdeadbeef0201592fdeadbeef02015920',
+        'magnet:?xt=urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF',
+        'magnet:?xt=urn:btih:0201592f00000000000000000000000000000001',
+        'magnet:?xt=urn:btih:0201592f00000000000000000000000000000002',
+        'magnet:?xt=urn:btih:0000000000000000000000000000000000000001',
+        'magnet:?xt=urn:btih:0000000000000000000000000000000000000002',
+        'magnet:?xt=urn:btih:0000000000000000000000000000000000000003',
+        'magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567',
+        'magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
+        'magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
+        'magnet:?xt=urn:btih:cccccccccccccccccccccccccccccccccccccccc',
+        'magnet:?xt=urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a',
+        'magnet:?xt=urn:btih:0123456789abcdef',
+        'magnet:?xt=urn:btih:ABCDEF0123456789',
+        'MAGNET:?xt=urn:btih:ABCDEF0123456789',
+        'MAGNET:?xt=urn:btih:ABCDEF0123456789ABCDEF0123456789ABCDEF01',
+        'magnet:?xt=urn:btih:fedcba9876543210',
+        # Cookie / token fixtures. These only started matching once the patterns
+    # were widened to production's grammar (floor of 1 char, optional quotes
+    # and whitespace around `=`). Every value here is self-evidently a
+    # placeholder — XXX, `...`, brand_new, clear_me — and lives in a test or
+    # in documentation showing the cookie format.
+    'RD_API_TOKEN=abc-123',
+    '_jdb_session=...',
+    '_jdb_session=XXX',
+    '_jdb_session=abc',
+    '_jdb_session=abc123',
+    '_jdb_session=brand_new',
+    '_jdb_session=clear_me',
+    '_jdb_session=e2e_jdb_session',
+    '_jdb_session=keep_me_alive',
+    '_jdb_session=keyring_only',
+    '_jdb_session=label_test',
+    '_jdb_session=new',
+    '_jdb_session=older_keyring_value',
+    '_jdb_session=paste_session',
+    '_jdb_session=preexisting_session',
+    '_jdb_session=regress_session',
+    '_jdb_session=resurrect_me',
+    '_jdb_session=xyz',
+    'cf_clearance=...',
+    'cf_clearance=XXX',
+    'cf_clearance=brand_new',
+    'cf_clearance=clear_cf',
+    'cf_clearance=e2e_cf_clearance',
+    'cf_clearance=fresh',
+    'cf_clearance=label_test_cf',
+    'cf_clearance=paste_cf',
+    'cf_clearance=preexisting_cf',
+    'cf_clearance=regress_cf',
+    'cf_clearance=resurrect_cf',
+    'cf_clearance=xyz',
+    'cf_clearance=xyz789',
+    # Placeholder cookie values in the Rust cookie-store tests.
+        '_jdb_session=paste_session',
+        '_jdb_session=keep_me_alive',
+        '_jdb_session=e2e_jdb_session',
+        '_jdb_session=regress_session',
+        '_jdb_session=preexisting_session',
+        '_jdb_session=label_test',
+        '_jdb_session=older_keyring_value',
+        '_jdb_session=keyring_only',
+        '_jdb_session=resurrect_me'
+    )
+
+    $SourceHits    = @()
+    $SourceEligible = 0   # tracked, non-binary, i.e. in scope
+    $SourceScanned  = 0   # actually read and regexed
+    $SourceAllowed  = 0   # matched but present in $AllowedLiterals
+    foreach ($rel in $sourceFiles) {
+        $full = Join-Path $RepoRoot $rel
+        if ($skipExt -contains ([System.IO.Path]::GetExtension($rel).ToLowerInvariant())) { continue }
+        $SourceEligible++
+        # -LiteralPath: a tracked file called `notes[1].md` is a valid wildcard to
+        # Test-Path, which would report it missing.
+        #
+        # Fail CLOSED here, and count the entry as eligible BEFORE testing it. The
+        # earlier version skipped unresolvable paths before incrementing, so the
+        # eligible-equals-scanned invariant could never detect them — the exact
+        # blind spot that invariant was added to close. The working tree is
+        # verified clean at Step 0, so every index entry must exist on disk; one
+        # that does not means the path came back mangled (encoding) or something
+        # changed underneath the build.
+        if (-not (Test-Path -LiteralPath $full -PathType Leaf)) {
+            FailExit ("Source secret scan could not resolve tracked path: " + $rel + " — refusing to ship a partial scan.")
+        }
+        # Fail CLOSED on read errors. The old code used -ErrorAction SilentlyContinue
+        # and `continue`d on $null, so an unreadable file vanished from the scan
+        # while the run still reported success — a file the scanner could not read
+        # is exactly the file worth worrying about.
+        # Read BYTES, not text. Get-Content -Raw picks an encoding for you, and the
+        # default differs between Windows PowerShell 5.1 and PowerShell 7: a
+        # BOM-less UTF-16LE file decodes into ASCII interleaved with NULs, so a
+        # perfectly readable secret matches nothing while I/O "succeeds" and
+        # eligible still equals scanned.
+        try {
+            $bytes = [System.IO.File]::ReadAllBytes($full)
+        } catch {
+            FailExit ("Source secret scan could not read " + $rel + ": " + $_.Exception.Message)
+        }
+        $SourceScanned++
+        # Same two-encoding sweep the binary scan does, plus a percent-decoded pass
+        # of each: production normalises `magnet:?xt=urn%3Abtih%3A<hash>` back to
+        # `btih:<hash>` (verified via _magnet_dedupe_key) and interns it, so a scan
+        # that only sees the raw bytes misses an escaped magnet entirely.
+        $variants = New-Object System.Collections.Generic.List[string]
+        foreach ($enc in $Encodings) {
+            $decoded = $enc.encoding.GetString($bytes)
+            $variants.Add($decoded)
+            try { $variants.Add([System.Uri]::UnescapeDataString($decoded)) } catch { }
+        }
+        foreach ($text in $variants) {
+            foreach ($p in $Patterns) {
+                foreach ($m in [regex]::Matches($text, $p.rx, $RxOpts)) {
+                    if ($AllowedLiterals -ccontains $m.Value) { $SourceAllowed++; continue }
+                    $SourceHits += ("      " + $rel + "  [" + $p.name + "]")
+                }
+            }
+        }
+    }
+    if ($SourceHits.Count -gt 0) {
+        Write-Host "    Source secret scan LEAK:" -ForegroundColor Red
+        # File + pattern only, never the matched text (same reasoning as the binary
+        # scan above).
+        $SourceHits | Sort-Object -Unique | ForEach-Object { Write-Host $_ -ForegroundColor Red }
+        Write-Host "    If a hit is a synthetic fixture, add its exact value to `$AllowedLiterals." -ForegroundColor Red
+        FailExit "Source secret scan failed"
+    }
+    # A scan that walked nothing must never report success — that is the exact
+    # failure mode this step was rewritten to eliminate, so assert it explicitly
+    # instead of trusting the file list to be non-empty.
+    if ($SourceScanned -eq 0) {
+        FailExit "Source secret scan walked 0 files — the scan is not covering anything. Check git ls-files and skipExt."
+    }
+    if ($SourceScanned -ne $SourceEligible) {
+        FailExit ("Source secret scan read " + $SourceScanned + " of " + $SourceEligible + " eligible files; refusing to ship a partial scan.")
+    }
+    Ok ("No unexpected source secrets (" + $SourceScanned + " text files scanned, " + $SourceAllowed + " allowlisted fixture matches)")
+}
+
+# --------------------------------------------------------------------------
+# -AuditOnly: run just the scan and exit. The clean-tree gate is skipped on
+# this path ON PURPOSE — red-testing the scanner means planting a secret,
+# which necessarily dirties the tree. Never use this mode to ship.
+# --------------------------------------------------------------------------
+if ($AuditOnly) {
+    Write-Output "== AUDIT ONLY: source secret scan, no build =="
+    Invoke-SourceSecretScan
+    Write-Output "[PASS] audit-only scan clean"
+    exit 0
+}
+
 Step "Verifying working tree is clean"
 # The build reads the WORKING TREE (npm/cargo/PyInstaller all compile what is on
 # disk), but the manifest records `git rev-parse HEAD`. With uncommitted edits
@@ -88,8 +402,21 @@ Step "Verifying working tree is clean"
 # file" is not the same as scanning every build input.
 $BuildStartHead = (& git -C $RepoRoot rev-parse HEAD).Trim()
 if ($LASTEXITCODE -ne 0) { FailExit "git rev-parse HEAD failed; refusing to build" }
-$treeStatus = & git -C $RepoRoot status --porcelain
+# --untracked-files=all explicitly: `status.showUntrackedFiles=no` in any
+# config layer would otherwise hide untracked files entirely, and untracked
+# top-level modules CAN be pulled into sidecar.exe by PyInstaller.
+$treeStatus = & git -C $RepoRoot status --porcelain --untracked-files=all
 if ($LASTEXITCODE -ne 0) { FailExit "git status failed (exit $LASTEXITCODE); refusing to build" }
+# assume-unchanged (h) and skip-worktree (S) make git report a clean tree while
+# the file on disk differs from the index — the build would compile content
+# that neither git status nor the source scan ever sees.
+$maskedEntries = & git -C $RepoRoot ls-files -v
+if ($LASTEXITCODE -ne 0) { FailExit "git ls-files -v failed; refusing to build" }
+$masked = @($maskedEntries | Where-Object { $_ -cmatch '^[a-z]' -or $_ -cmatch '^S ' })
+if ($masked.Count -gt 0) {
+    $masked | ForEach-Object { Write-Output ("      " + $_) }
+    FailExit "Tracked files are marked assume-unchanged/skip-worktree; git cannot vouch for their contents. Clear with: git update-index --no-assume-unchanged --no-skip-worktree <path>"
+}
 if ($treeStatus) {
     Write-Output "    Working tree is not clean:"
     $treeStatus | ForEach-Object { Write-Output ("      " + $_) }
@@ -265,62 +592,17 @@ $ScanTargets = @(
     (Join-Path $StagingDir "javdbmagnet.exe"),
     (Join-Path $StagingDir "sidecar.exe")
 )
-
-$Patterns = @(
-    # Every pattern below is matched case-INSENSITIVELY (see $RxOpts). URI
-    # schemes are case-insensitive per RFC 3986, and this project's own parser
-    # agrees: sidecar.py lower-cases before its `startswith("magnet:")` check
-    # and _REDACT_MAGNET_RX carries re.IGNORECASE. A case-sensitive scan would
-    # therefore miss `MAGNET:?XT=URN:BTIH:...` — a string production happily
-    # accepts and interns. Verified: register_magnets returns ok for the
-    # upper-case form while the old pattern did not match it at all.
-    @{ name = 'urn:btih:<40hex>';            rx = 'urn:btih:[a-fA-F0-9]{40}' },
-    # BitTorrent v1 infohashes are 40 hex OR 32 base32 (BEP 9); v2 uses a
-    # different URN entirely (`urn:btmh:`, BEP 52). An earlier commit message
-    # claimed "64-hex btih v2" — that form does not exist. Cover all three.
-    @{ name = 'urn:btih:<32base32>';         rx = 'urn:btih:[A-Z2-7]{32}' },
-    @{ name = 'urn:btmh: (BitTorrent v2)';   rx = 'urn:bt' + 'mh:[a-fA-F0-9]{10,}' },
-    # `{16,}` rather than `+`: redact_magnet()'s output is a fixed 8 hex chars,
-    # so `+` made this pattern flag the project's own CORRECTLY REDACTED form.
-    # Real v1 infohashes are 40 hex (or 32 base32); 16 is a safe floor that
-    # passes the 8-char redacted form and catches every real length.
-    @{ name = 'magnet:?xt=';                 rx = 'magnet:\?xt=urn:bt' + '[im]h:[a-zA-Z0-9]{16,}' },
-    @{ name = 'Cloudflare clearance cookie'; rx = 'cf' + '_clearance=' + '[A-Za-z0-9_.-]{20,}' },
-    @{ name = 'Cloudflare bot cookie';       rx = '__cf' + '_bm=' + '[A-Za-z0-9_.-]{20,}' },
-    @{ name = 'JavDB session cookie';        rx = '_jdb' + '_session=' + '[A-Za-z0-9_.-]{10,}' },
-    @{ name = 'remember_me_token=';          rx = 'remember_me_token=[A-Za-z0-9_.-]{10,}' },
-    @{ name = 'Authorization bearer header'; rx = 'Authorization:\s*' + 'Bearer\s+' + '[A-Za-z0-9_-]{20,}' },
-    @{ name = 'Bearer <30+ char token>';     rx = 'Bearer ' + '[A-Za-z0-9_-]{30,}' },
-    @{ name = 'RD_API_TOKEN=<value>';        rx = 'RD_API' + '_TOKEN=' + '[A-Za-z0-9_-]{20,}' }
-)
-
-# All regex evaluation in this script goes through these options. See the
-# comment above $Patterns for why IgnoreCase is not optional here.
-$RxOpts = [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
-
-$ScanFail = $false
-$BinaryHitCount = 0
-# We decode the binary bytes both as ASCII *and* UTF-16LE because PE
-# images routinely embed strings in both encodings:
-#   - ASCII / UTF-8 covers Rust &str literals, format!() output, and
-#     anything wired through libc-style APIs.
-#   - UTF-16LE covers strings handed to the Win32 wide API (e.g. a
-#     `let path = format!("HKCU\\...\\{}", token);` later passed to
-#     `RegOpenKeyExW`), which would otherwise sail past an ASCII-only
-#     scan even though the secret material is plainly readable in a
-#     hex dump.
-# Running both passes is cheap (two regex sweeps over the same byte
-# blob); failing to do it would silently halve the scan's coverage.
-$Encodings = @(
-    @{ label = 'ASCII';      encoding = [System.Text.Encoding]::ASCII },
-    @{ label = 'UTF-16LE';   encoding = [System.Text.Encoding]::Unicode }
-)
 foreach ($exe in $ScanTargets) {
     $name = Split-Path $exe -Leaf
     $bytes = [System.IO.File]::ReadAllBytes($exe)
     $hits = @()
     foreach ($enc in $Encodings) {
-        $text = $enc.encoding.GetString($bytes)
+        $decoded = $enc.encoding.GetString($bytes)
+        # Percent-decoded pass for the same reason as the source scan: an
+        # escaped magnet is still a magnet by the time production sees it.
+        $texts = @($decoded)
+        try { $texts += [System.Uri]::UnescapeDataString($decoded) } catch { }
+        foreach ($text in $texts) {
         foreach ($p in $Patterns) {
             $regexMatches = [regex]::Matches($text, $p.rx, $RxOpts)
             if ($regexMatches.Count -gt 0) {
@@ -333,6 +615,7 @@ foreach ($exe in $ScanTargets) {
                 $BinaryHitCount += $regexMatches.Count
             }
         }
+        }
     }
     if ($hits.Count -gt 0) {
         Write-Host "    [$name] LEAK:" -ForegroundColor Red
@@ -343,174 +626,7 @@ foreach ($exe in $ScanTargets) {
     }
 }
 if ($ScanFail) { FailExit "Binary content scan failed" }
-
-# ---------------------------------------------------------------------------
-# Step 7: Source secret scan — over EVERY tracked file
-#
-# This used to derive its file list from `git diff <origin/HEAD>..HEAD` plus
-# the working-tree diff. That made coverage depend on where HEAD happened to
-# sit: cutting a release from an already-pushed master left both diffs empty,
-# so the scan walked ZERO files and still wrote `source_secret_hits: 0` into
-# the manifest — a vacuous pass that read exactly like a real one. It was
-# found the hard way: a magnet literal sat in verify-windows-build.ps1 from
-# the commit that introduced it and was never once scanned, until an
-# unrelated edit to that file finally pulled it into the diff.
-#
-# The file list now comes from `git ls-files`, so coverage is a property of
-# the repo rather than of the branch topology. Content is read from disk, so
-# uncommitted edits to tracked files are scanned as they actually are.
-# Untracked files are deliberately out of scope: they are neither committed
-# nor shipped inside the portable zip.
-# ---------------------------------------------------------------------------
-Step "Source secret scan (all tracked text files)"
-# -z + NUL split: without it git quotes paths containing non-ASCII or control
-# characters ("\303\251.md"), and the quoted name matches nothing on disk — the
-# file is then silently dropped from the scan.
-# Windows PowerShell 5.1 decodes native-command output using the console code
-# page, not UTF-8. A tracked filename with non-ASCII characters would come back
-# mangled, Test-Path would then fail to resolve it, and the entry would vanish
-# from the scan. Force UTF-8 for the duration of the git call.
-$prevOutEnc = [Console]::OutputEncoding
-try {
-    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
-    $lsRaw = & git -C $RepoRoot ls-files -z
-    $lsExit = $LASTEXITCODE
-} finally {
-    [Console]::OutputEncoding = $prevOutEnc
-}
-if ($lsExit -ne 0) {
-    Write-Error "FATAL: source-secret-scan git ls-files failed (exit $lsExit). Refusing to ship a release without a source scan."
-    exit 1
-}
-$sourceFiles = @(($lsRaw -join "") -split "`0" | Where-Object { $_ } | Sort-Object -Unique)
-$skipExt = @('.exe', '.msi', '.zip', '.7z', '.png', '.ico', '.icns', '.dll')
-
-# Known-synthetic literals, allowlisted BY EXACT VALUE rather than by file.
-#
-# The previous design skipped whole files (commands.rs, legacy_import.rs,
-# tests/, *.test.ts, four prose docs, and this script). That exempted ~23 text
-# files INCLUDING production Rust and the gate itself: any real token later
-# pasted into them would never have been seen. "Every tracked file" was not
-# true.
-#
-# Now nothing is exempt. Every tracked text file is scanned, and a match only
-# passes if its exact text appears below. Each entry is a fixture whose
-# synthetic nature is self-evident (DEADBEEF / repeated nibbles / sequential
-# counters / obvious placeholder session names), except the one PoC hash in the
-# security-audit archive, which demonstrates a dedupe-key collision where the
-# point is that the SAME arbitrary string appears twice.
-#
-# Adding an entry here is a visible, reviewable diff line — unlike adding a
-# file to a skip list, which blinds the scanner to everything in that file
-# forever. A NEW fixture will fail the build until it is listed; that is the
-# intended cost.
-$AllowedLiterals = @(
-    'urn:btih:0201592fDEADBEEF0201592fDEADBEEF02015920',
-    'urn:btih:0201592fdeadbeef0201592fdeadbeef02015920',
-    'urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF',
-    'urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEF',
-    'urn:btih:0201592f00000000000000000000000000000001',
-    'urn:btih:0201592f00000000000000000000000000000002',
-    'urn:btih:0000000000000000000000000000000000000001',
-    'urn:btih:0000000000000000000000000000000000000002',
-    'urn:btih:0000000000000000000000000000000000000003',
-    'urn:btih:0123456789abcdef0123456789abcdef01234567',
-    'urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
-    'urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
-    'urn:btih:cccccccccccccccccccccccccccccccccccccccc',
-    'urn:btih:ABCDEF0123456789ABCDEF0123456789ABCDEF01',
-    'urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
-    'urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
-    'urn:btih:cccccccccccccccccccccccccccccccc',
-    # Dedupe-key collision PoC (prompt/security-audit-fixes-2026-07-28.md).
-    'urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a',
-    'magnet:?xt=urn:btih:0201592fDEADBEEF0201592fDEADBEEF02015920',
-    'magnet:?xt=urn:btih:0201592fdeadbeef0201592fdeadbeef02015920',
-    'magnet:?xt=urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF',
-    'magnet:?xt=urn:btih:0201592f00000000000000000000000000000001',
-    'magnet:?xt=urn:btih:0201592f00000000000000000000000000000002',
-    'magnet:?xt=urn:btih:0000000000000000000000000000000000000001',
-    'magnet:?xt=urn:btih:0000000000000000000000000000000000000002',
-    'magnet:?xt=urn:btih:0000000000000000000000000000000000000003',
-    'magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567',
-    'magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
-    'magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
-    'magnet:?xt=urn:btih:cccccccccccccccccccccccccccccccccccccccc',
-    'magnet:?xt=urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a',
-    'magnet:?xt=urn:btih:0123456789abcdef',
-    'magnet:?xt=urn:btih:ABCDEF0123456789',
-    'MAGNET:?xt=urn:btih:ABCDEF0123456789',
-    'MAGNET:?xt=urn:btih:ABCDEF0123456789ABCDEF0123456789ABCDEF01',
-    'magnet:?xt=urn:btih:fedcba9876543210',
-    # Placeholder cookie values in the Rust cookie-store tests.
-    '_jdb_session=paste_session',
-    '_jdb_session=keep_me_alive',
-    '_jdb_session=e2e_jdb_session',
-    '_jdb_session=regress_session',
-    '_jdb_session=preexisting_session',
-    '_jdb_session=label_test',
-    '_jdb_session=older_keyring_value',
-    '_jdb_session=keyring_only',
-    '_jdb_session=resurrect_me'
-)
-
-$SourceHits    = @()
-$SourceEligible = 0   # tracked, non-binary, i.e. in scope
-$SourceScanned  = 0   # actually read and regexed
-$SourceAllowed  = 0   # matched but present in $AllowedLiterals
-foreach ($rel in $sourceFiles) {
-    $full = Join-Path $RepoRoot $rel
-    if ($skipExt -contains ([System.IO.Path]::GetExtension($rel).ToLowerInvariant())) { continue }
-    $SourceEligible++
-    # -LiteralPath: a tracked file called `notes[1].md` is a valid wildcard to
-    # Test-Path, which would report it missing.
-    #
-    # Fail CLOSED here, and count the entry as eligible BEFORE testing it. The
-    # earlier version skipped unresolvable paths before incrementing, so the
-    # eligible-equals-scanned invariant could never detect them — the exact
-    # blind spot that invariant was added to close. The working tree is
-    # verified clean at Step 0, so every index entry must exist on disk; one
-    # that does not means the path came back mangled (encoding) or something
-    # changed underneath the build.
-    if (-not (Test-Path -LiteralPath $full -PathType Leaf)) {
-        FailExit ("Source secret scan could not resolve tracked path: " + $rel + " — refusing to ship a partial scan.")
-    }
-    # Fail CLOSED on read errors. The old code used -ErrorAction SilentlyContinue
-    # and `continue`d on $null, so an unreadable file vanished from the scan
-    # while the run still reported success — a file the scanner could not read
-    # is exactly the file worth worrying about.
-    try {
-        $text = Get-Content -LiteralPath $full -Raw -ErrorAction Stop
-    } catch {
-        FailExit ("Source secret scan could not read " + $rel + ": " + $_.Exception.Message)
-    }
-    if ($null -eq $text) { $text = "" }   # legitimately empty file
-    $SourceScanned++
-    foreach ($p in $Patterns) {
-        foreach ($m in [regex]::Matches($text, $p.rx, $RxOpts)) {
-            if ($AllowedLiterals -ccontains $m.Value) { $SourceAllowed++; continue }
-            $SourceHits += ("      " + $rel + "  [" + $p.name + "]")
-        }
-    }
-}
-if ($SourceHits.Count -gt 0) {
-    Write-Host "    Source secret scan LEAK:" -ForegroundColor Red
-    # File + pattern only, never the matched text (same reasoning as the binary
-    # scan above).
-    $SourceHits | Sort-Object -Unique | ForEach-Object { Write-Host $_ -ForegroundColor Red }
-    Write-Host "    If a hit is a synthetic fixture, add its exact value to `$AllowedLiterals." -ForegroundColor Red
-    FailExit "Source secret scan failed"
-}
-# A scan that walked nothing must never report success — that is the exact
-# failure mode this step was rewritten to eliminate, so assert it explicitly
-# instead of trusting the file list to be non-empty.
-if ($SourceScanned -eq 0) {
-    FailExit "Source secret scan walked 0 files — the scan is not covering anything. Check git ls-files and skipExt."
-}
-if ($SourceScanned -ne $SourceEligible) {
-    FailExit ("Source secret scan read " + $SourceScanned + " of " + $SourceEligible + " eligible files; refusing to ship a partial scan.")
-}
-Ok ("No unexpected source secrets (" + $SourceScanned + " text files scanned, " + $SourceAllowed + " allowlisted fixture matches)")
+Invoke-SourceSecretScan
 
 # ---------------------------------------------------------------------------
 # Step 8: Compress staging dir to release/JavDBMagnet_<v>_portable.zip
@@ -559,12 +675,13 @@ Ok ("Wrote " + $SumsPath)
 # hardcoding `working_tree_clean = true`, would make the field an assertion
 # about the past rather than about the artifact.
 Step "Re-verifying source snapshot after build"
+$ManifestPath = Join-Path $ReleaseOutDir "release-manifest.json"
 $gitCommit = (& git -C $RepoRoot rev-parse HEAD).Trim()
 if ($LASTEXITCODE -ne 0) { FailExit "git rev-parse HEAD failed after build" }
 if ($gitCommit -ne $BuildStartHead) {
     FailExit ("HEAD moved during the build (" + $BuildStartHead + " -> " + $gitCommit + "); the artifacts do not match either commit.")
 }
-$treeStatusAfter = & git -C $RepoRoot status --porcelain
+$treeStatusAfter = & git -C $RepoRoot status --porcelain --untracked-files=all
 if ($LASTEXITCODE -ne 0) { FailExit "git status failed after build" }
 if ($treeStatusAfter) {
     $treeStatusAfter | ForEach-Object { Write-Output ("      " + $_) }
@@ -599,12 +716,15 @@ $manifest = [ordered]@{
         source_files_eligible    = $SourceEligible
         source_files_scanned     = $SourceScanned
         source_allowlisted_hits  = $SourceAllowed
-        # Asserted BEFORE the build and re-verified AFTER it (HEAD unchanged
-        # and porcelain still empty), so git_commit really does identify the
-        # source that was compiled and scanned — not merely what HEAD was when
-        # the run started.
+        # Checked before the build and re-checked after it. This does NOT prove
+        # the compiler observed exactly this snapshot: an edit made and reverted
+        # mid-build leaves both checks clean while an artifact was produced from
+        # transient source. The field is named for what is actually verified.
+        # Proving the stronger property requires building from an immutable
+        # checkout (git archive / a throwaway worktree), which this pipeline
+        # does not yet do.
         working_tree_clean       = $true
-        source_snapshot_verified = "before_and_after_build"
+        source_snapshot_verified = "pre_and_post_build_clean"
     }
     signing     = @{
         requested = ($env:SIGN -eq "1")
---CURRENT NUMBERED---
     1	# build-release.ps1 — portable release pipeline
     2	#
     3	# Produces a portable ZIP that ships javdbmagnet.exe + sidecar.exe in a
     4	# single folder. End-users extract the zip and double-click the exe —
     5	# no installer, no Program Files, no Start Menu entry, no registry.
     6	#
     7	# Pipeline:
     8	#   1. Build sidecar.exe         (npm run sidecar:build → app/src-tauri/binaries/...)
     9	#   2. Build frontend + Rust exe (npx tauri build --no-bundle from app/)
    10	#                                 — single CLI call enables the
    11	#                                 `tauri/custom-protocol` feature so the
    12	#                                 release binary embeds dist/ instead of
    13	#                                 reaching for the dev server
    14	#   3. Stage release/JavDBMagnet/ (javdbmagnet.exe + sidecar.exe + README.txt)
    15	#   4. Audit staging dir         (whitelist: exe + exe + README.txt; nothing else)
    16	#   5. Binary content scan       (tokens / magnets / Cloudflare cookies must NOT
    17	#                                 appear in either exe)
    18	#   6. Source secret scan        (same patterns, case-insensitive, over every
    19	#                                 tracked text file; no file-level exemptions —
    20	#                                 known fixtures are allowlisted by exact
    21	#                                 value. Fails closed on unreadable files, on
    22	#                                 an eligible/scanned mismatch, and on 0 files)
    23	#   7. Compress-Archive → release/JavDBMagnet_<version>_portable.zip
    24	#   8. SHA256 for zip + 2 exes  → release/SHA256SUMS.txt
    25	#   9. Write release/release-manifest.json
    26	#  10. Print final paths
    27	#
    28	# Any audit / scan failure → exit 1. Half-baked staging stays for inspection.
    29	#
    30	# Code signing is NOT performed. $env:SIGN -eq "1" emits a placeholder
    31	# warning; wire signtool / osslsigncode here once a cert exists.
    32	#
    33	# Run:
    34	#     pwsh -File scripts\build-release.ps1
    35	# Or from app/:
    36	#     npm run release
    37	
    38	param(
    39	    # Run ONLY the source secret scan and exit. No build, no staging, no zip.
    40	    # Added so this gate can actually be executed and red-tested on its own:
    41	    # a full release run costs minutes of PyInstaller + cargo before it would
    42	    # ever reach the scan.
    43	    [switch]$AuditOnly
    44	)
    45	
    46	$ErrorActionPreference = "Stop"
    47	Set-StrictMode -Version Latest
    48	
    49	# ---------------------------------------------------------------------------
    50	# Paths
    51	# ---------------------------------------------------------------------------
    52	$ScriptDir     = Split-Path -Parent $MyInvocation.MyCommand.Path
    53	$RepoRoot      = Split-Path -Parent $ScriptDir
    54	$AppDir        = Join-Path $RepoRoot "app"
    55	$TauriSrcDir   = Join-Path $AppDir "src-tauri"
    56	$CargoOutDir   = Join-Path $TauriSrcDir "target\release"
    57	$BinariesDir   = Join-Path $TauriSrcDir "binaries"
    58	$ReleaseOutDir = Join-Path $RepoRoot "release"
    59	
    60	# Sidecar artifact path produced by build_sidecar.py
    61	$SidecarSource = Join-Path $BinariesDir "sidecar-x86_64-pc-windows-msvc.exe"
    62	
    63	# Read version straight from app/package.json so the zip name follows it.
    64	$PkgJsonPath = Join-Path $AppDir "package.json"
    65	$pkgJson = Get-Content $PkgJsonPath -Raw | ConvertFrom-Json
    66	$Version = $pkgJson.version
    67	$PortableFolderName = "JavDBMagnet"
    68	$StagingDir = Join-Path $ReleaseOutDir $PortableFolderName
    69	$ZipName    = "JavDBMagnet_${Version}_portable.zip"
    70	$ZipPath    = Join-Path $ReleaseOutDir $ZipName
    71	
    72	function Step($title) {
    73	    Write-Output ""
    74	    Write-Output "==> $title"
    75	}
    76	function Ok($msg)   { Write-Output "    [OK]   $msg" }
    77	function Warn($msg) { Write-Output "    [WARN] $msg" }
    78	function FailExit($msg) {
    79	    Write-Output ""
    80	    Write-Output "[FAIL] $msg"
    81	    exit 1
    82	}
    83	# ---------------------------------------------------------------------------
    84	# Step 0: Prepare release/ output dir
    85	# ---------------------------------------------------------------------------
    86	
    87	$Patterns = @(
    88	    # Every pattern below is matched case-INSENSITIVELY (see $RxOpts). URI
    89	    # schemes are case-insensitive per RFC 3986, and this project's own parser
    90	    # agrees: sidecar.py lower-cases before its `startswith("magnet:")` check
    91	    # and _REDACT_MAGNET_RX carries re.IGNORECASE. A case-sensitive scan would
    92	    # therefore miss `MAGNET:?XT=URN:BTIH:...` — a string production happily
    93	    # accepts and interns. Verified: register_magnets returns ok for the
    94	    # upper-case form while the old pattern did not match it at all.
    95	    # GREEDY `{40,}`, not `{40}` and not `{40}(?!hex)`. All three were tried:
    96	    #   {40}            — a 42-hex value matches its first 40 chars, and if
    97	    #                     those 40 are allowlisted the real value passes.
    98	    #   {40}(?![hex])   — a 42-hex value then matches NOTHING AT ALL (the
    99	    #                     lookahead fails at every start offset), which is a
   100	    #                     bigger hole than the one it was meant to close. This
   101	    #                     was caught by executing the red test, not by reading.
   102	    #   {40,}           — consumes the whole run, so anything longer than an
   103	    #                     allowlisted literal is a distinct value and fails.
   104	    @{ name = 'urn:btih:<40+hex>';           rx = 'urn:btih:[a-fA-F0-9]{40,}' },
   105	    # BitTorrent v1 infohashes are 40 hex OR 32 base32 (BEP 9); v2 uses a
   106	    # different URN entirely (`urn:btmh:`, BEP 52). An earlier commit message
   107	    # claimed "64-hex btih v2" — that form does not exist. Cover all three.
   108	    @{ name = 'urn:btih:<32+base32>';        rx = 'urn:btih:[A-Z2-7]{32,}' },
   109	    @{ name = 'urn:btmh: (BitTorrent v2)';   rx = 'urn:bt' + 'mh:[a-fA-F0-9]{10,}' },
   110	    # `{16,}` rather than `+`: redact_magnet()'s output is a fixed 8 hex chars,
   111	    # so `+` made this pattern flag the project's own CORRECTLY REDACTED form.
   112	    # Real v1 infohashes are 40 hex (or 32 base32); 16 is a safe floor that
   113	    # passes the 8-char redacted form and catches every real length.
   114	    @{ name = 'magnet:?xt=';                 rx = 'magnet:\?xt=urn:bt' + '[im]h:[a-zA-Z0-9]{16,}' },
   115	    # Length floors and separator grammar now follow what PRODUCTION accepts,
   116	    # not what a "realistic" secret looks like. secret_store.rs takes 1-255
   117	    # ASCII alphanumerics; legacy_import.rs trims whitespace around `=` and
   118	    # strips surrounding quotes; parse_cookie_string trims each `k = v` pair.
   119	    # A scanner narrower than the parser is a scanner with a documented hole,
   120	    # so `\s*`, optional quotes and a floor of 1 are all deliberate. The cost
   121	    # is that short test fixtures now match — they are listed in
   122	    # $AllowedLiterals, which is exactly the reviewable-diff tradeoff this
   123	    # design already makes everywhere else.
   124	    @{ name = 'Cloudflare clearance cookie'; rx = 'cf' + '_clearance\s*=\s*["'']?' + '[A-Za-z0-9_.~+/=-]{1,}' },
   125	    @{ name = 'Cloudflare bot cookie';       rx = '__cf' + '_bm\s*=\s*["'']?' + '[A-Za-z0-9_.~+/=-]{1,}' },
   126	    @{ name = 'JavDB session cookie';        rx = '_jdb' + '_session\s*=\s*["'']?' + '[A-Za-z0-9_.~+/=-]{1,}' },
   127	    @{ name = 'remember_me_token=';          rx = 'remember_me_token\s*=\s*["'']?' + '[A-Za-z0-9_.~+/=-]{1,}' },
   128	    # token68 (RFC 7235) allows -._~+/ and trailing '='; the old [A-Za-z0-9_-]
   129	    # stopped at the first '.' and reported a truncated match.
   130	    @{ name = 'Authorization bearer header'; rx = 'Authorization:\s*' + 'Bearer\s+' + '[A-Za-z0-9_.~+/=-]{8,}' },
   131	    @{ name = 'Bearer <token>';              rx = 'Bearer\s+' + '[A-Za-z0-9_.~+/=-]{16,}' },
   132	    @{ name = 'RD_API_TOKEN=<value>';        rx = 'RD_API' + '_TOKEN\s*=\s*["'']?' + '[A-Za-z0-9_-]{1,}' }
   133	)
   134	
   135	# All regex evaluation in this script goes through these options. See the
   136	# comment above $Patterns for why IgnoreCase is not optional here.
   137	$RxOpts = [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
   138	
   139	$ScanFail = $false
   140	$BinaryHitCount = 0
   141	# We decode the binary bytes both as ASCII *and* UTF-16LE because PE
   142	# images routinely embed strings in both encodings:
   143	#   - ASCII / UTF-8 covers Rust &str literals, format!() output, and
   144	#     anything wired through libc-style APIs.
   145	#   - UTF-16LE covers strings handed to the Win32 wide API (e.g. a
   146	#     `let path = format!("HKCU\\...\\{}", token);` later passed to
   147	#     `RegOpenKeyExW`), which would otherwise sail past an ASCII-only
   148	#     scan even though the secret material is plainly readable in a
   149	#     hex dump.
   150	# Running both passes is cheap (two regex sweeps over the same byte
   151	# blob); failing to do it would silently halve the scan's coverage.
   152	$Encodings = @(
   153	    @{ label = 'ASCII';      encoding = [System.Text.Encoding]::ASCII },
   154	    @{ label = 'UTF-16LE';   encoding = [System.Text.Encoding]::Unicode }
   155	)
   156	
   157	function Invoke-SourceSecretScan {
   158	
   159	    # ---------------------------------------------------------------------------
   160	    # Step 7: Source secret scan — over EVERY tracked file
   161	    #
   162	    # This used to derive its file list from `git diff <origin/HEAD>..HEAD` plus
   163	    # the working-tree diff. That made coverage depend on where HEAD happened to
   164	    # sit: cutting a release from an already-pushed master left both diffs empty,
   165	    # so the scan walked ZERO files and still wrote `source_secret_hits: 0` into
   166	    # the manifest — a vacuous pass that read exactly like a real one. It was
   167	    # found the hard way: a magnet literal sat in verify-windows-build.ps1 from
   168	    # the commit that introduced it and was never once scanned, until an
   169	    # unrelated edit to that file finally pulled it into the diff.
   170	    #
   171	    # The file list now comes from `git ls-files`, so coverage is a property of
   172	    # the repo rather than of the branch topology. Content is read from disk, so
   173	    # uncommitted edits to tracked files are scanned as they actually are.
   174	    # Untracked files are deliberately out of scope: they are neither committed
   175	    # nor shipped inside the portable zip.
   176	    # ---------------------------------------------------------------------------
   177	    Step "Source secret scan (all tracked text files)"
   178	    # -z + NUL split: without it git quotes paths containing non-ASCII or control
   179	    # characters ("\303\251.md"), and the quoted name matches nothing on disk — the
   180	    # file is then silently dropped from the scan.
   181	    # Windows PowerShell 5.1 decodes native-command output using the console code
   182	    # page, not UTF-8. A tracked filename with non-ASCII characters would come back
   183	    # mangled, Test-Path would then fail to resolve it, and the entry would vanish
   184	    # from the scan. Force UTF-8 for the duration of the git call.
   185	    $prevOutEnc = [Console]::OutputEncoding
   186	    try {
   187	        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
   188	        $lsRaw = & git -C $RepoRoot ls-files -z
   189	        $lsExit = $LASTEXITCODE
   190	    } finally {
   191	        [Console]::OutputEncoding = $prevOutEnc
   192	    }
   193	    if ($lsExit -ne 0) {
   194	        Write-Error "FATAL: source-secret-scan git ls-files failed (exit $lsExit). Refusing to ship a release without a source scan."
   195	        exit 1
   196	    }
   197	    $sourceFiles = @(($lsRaw -join "") -split "`0" | Where-Object { $_ } | Sort-Object -Unique)
   198	    $skipExt = @('.exe', '.msi', '.zip', '.7z', '.png', '.ico', '.icns', '.dll')
   199	
   200	    # Known-synthetic literals, allowlisted BY EXACT VALUE rather than by file.
   201	    #
   202	    # The previous design skipped whole files (commands.rs, legacy_import.rs,
   203	    # tests/, *.test.ts, four prose docs, and this script). That exempted ~23 text
   204	    # files INCLUDING production Rust and the gate itself: any real token later
   205	    # pasted into them would never have been seen. "Every tracked file" was not
   206	    # true.
   207	    #
   208	    # Now nothing is exempt. Every tracked text file is scanned, and a match only
   209	    # passes if its exact text appears below. Each entry is a fixture whose
   210	    # synthetic nature is self-evident (DEADBEEF / repeated nibbles / sequential
   211	    # counters / obvious placeholder session names), except the one PoC hash in the
   212	    # security-audit archive, which demonstrates a dedupe-key collision where the
   213	    # point is that the SAME arbitrary string appears twice.
   214	    #
   215	    # Adding an entry here is a visible, reviewable diff line — unlike adding a
   216	    # file to a skip list, which blinds the scanner to everything in that file
   217	    # forever. A NEW fixture will fail the build until it is listed; that is the
   218	    # intended cost.
   219	    $AllowedLiterals = @(
   220	        'urn:btih:0201592fDEADBEEF0201592fDEADBEEF02015920',
   221	        'urn:btih:0201592fdeadbeef0201592fdeadbeef02015920',
   222	        'urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF',
   223	        'urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEF',
   224	        'urn:btih:0201592f00000000000000000000000000000001',
   225	        'urn:btih:0201592f00000000000000000000000000000002',
   226	        'urn:btih:0000000000000000000000000000000000000001',
   227	        'urn:btih:0000000000000000000000000000000000000002',
   228	        'urn:btih:0000000000000000000000000000000000000003',
   229	        'urn:btih:0123456789abcdef0123456789abcdef01234567',
   230	        'urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
   231	        'urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
   232	        'urn:btih:cccccccccccccccccccccccccccccccccccccccc',
   233	        'urn:btih:ABCDEF0123456789ABCDEF0123456789ABCDEF01',
   234	        'urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
   235	        'urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
   236	        'urn:btih:cccccccccccccccccccccccccccccccc',
   237	        # Dedupe-key collision PoC (prompt/security-audit-fixes-2026-07-28.md).
   238	        'urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a',
   239	        'magnet:?xt=urn:btih:0201592fDEADBEEF0201592fDEADBEEF02015920',
   240	        'magnet:?xt=urn:btih:0201592fdeadbeef0201592fdeadbeef02015920',
   241	        'magnet:?xt=urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF',
   242	        'magnet:?xt=urn:btih:0201592f00000000000000000000000000000001',
   243	        'magnet:?xt=urn:btih:0201592f00000000000000000000000000000002',
   244	        'magnet:?xt=urn:btih:0000000000000000000000000000000000000001',
   245	        'magnet:?xt=urn:btih:0000000000000000000000000000000000000002',
   246	        'magnet:?xt=urn:btih:0000000000000000000000000000000000000003',
   247	        'magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567',
   248	        'magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
   249	        'magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
   250	        'magnet:?xt=urn:btih:cccccccccccccccccccccccccccccccccccccccc',
   251	        'magnet:?xt=urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a',
   252	        'magnet:?xt=urn:btih:0123456789abcdef',
   253	        'magnet:?xt=urn:btih:ABCDEF0123456789',
   254	        'MAGNET:?xt=urn:btih:ABCDEF0123456789',
   255	        'MAGNET:?xt=urn:btih:ABCDEF0123456789ABCDEF0123456789ABCDEF01',
   256	        'magnet:?xt=urn:btih:fedcba9876543210',
   257	        # Cookie / token fixtures. These only started matching once the patterns
   258	    # were widened to production's grammar (floor of 1 char, optional quotes
   259	    # and whitespace around `=`). Every value here is self-evidently a
   260	    # placeholder — XXX, `...`, brand_new, clear_me — and lives in a test or
   261	    # in documentation showing the cookie format.
   262	    'RD_API_TOKEN=abc-123',
   263	    '_jdb_session=...',
   264	    '_jdb_session=XXX',
   265	    '_jdb_session=abc',
   266	    '_jdb_session=abc123',
   267	    '_jdb_session=brand_new',
   268	    '_jdb_session=clear_me',
   269	    '_jdb_session=e2e_jdb_session',
   270	    '_jdb_session=keep_me_alive',
   271	    '_jdb_session=keyring_only',
   272	    '_jdb_session=label_test',
   273	    '_jdb_session=new',
   274	    '_jdb_session=older_keyring_value',
   275	    '_jdb_session=paste_session',
   276	    '_jdb_session=preexisting_session',
   277	    '_jdb_session=regress_session',
   278	    '_jdb_session=resurrect_me',
   279	    '_jdb_session=xyz',
   280	    'cf_clearance=...',
   281	    'cf_clearance=XXX',
   282	    'cf_clearance=brand_new',
   283	    'cf_clearance=clear_cf',
   284	    'cf_clearance=e2e_cf_clearance',
   285	    'cf_clearance=fresh',
   286	    'cf_clearance=label_test_cf',
   287	    'cf_clearance=paste_cf',
   288	    'cf_clearance=preexisting_cf',
   289	    'cf_clearance=regress_cf',
   290	    'cf_clearance=resurrect_cf',
   291	    'cf_clearance=xyz',
   292	    'cf_clearance=xyz789',
   293	    # Placeholder cookie values in the Rust cookie-store tests.
   294	        '_jdb_session=paste_session',
   295	        '_jdb_session=keep_me_alive',
   296	        '_jdb_session=e2e_jdb_session',
   297	        '_jdb_session=regress_session',
   298	        '_jdb_session=preexisting_session',
   299	        '_jdb_session=label_test',
   300	        '_jdb_session=older_keyring_value',
   301	        '_jdb_session=keyring_only',
   302	        '_jdb_session=resurrect_me'
   303	    )
   304	
   305	    $SourceHits    = @()
   306	    $SourceEligible = 0   # tracked, non-binary, i.e. in scope
   307	    $SourceScanned  = 0   # actually read and regexed
   308	    $SourceAllowed  = 0   # matched but present in $AllowedLiterals
   309	    foreach ($rel in $sourceFiles) {
   310	        $full = Join-Path $RepoRoot $rel
   311	        if ($skipExt -contains ([System.IO.Path]::GetExtension($rel).ToLowerInvariant())) { continue }
   312	        $SourceEligible++
   313	        # -LiteralPath: a tracked file called `notes[1].md` is a valid wildcard to
   314	        # Test-Path, which would report it missing.
   315	        #
   316	        # Fail CLOSED here, and count the entry as eligible BEFORE testing it. The
   317	        # earlier version skipped unresolvable paths before incrementing, so the
   318	        # eligible-equals-scanned invariant could never detect them — the exact
   319	        # blind spot that invariant was added to close. The working tree is
   320	        # verified clean at Step 0, so every index entry must exist on disk; one
   321	        # that does not means the path came back mangled (encoding) or something
   322	        # changed underneath the build.
   323	        if (-not (Test-Path -LiteralPath $full -PathType Leaf)) {
   324	            FailExit ("Source secret scan could not resolve tracked path: " + $rel + " — refusing to ship a partial scan.")
   325	        }
   326	        # Fail CLOSED on read errors. The old code used -ErrorAction SilentlyContinue
   327	        # and `continue`d on $null, so an unreadable file vanished from the scan
   328	        # while the run still reported success — a file the scanner could not read
   329	        # is exactly the file worth worrying about.
   330	        # Read BYTES, not text. Get-Content -Raw picks an encoding for you, and the
   331	        # default differs between Windows PowerShell 5.1 and PowerShell 7: a
   332	        # BOM-less UTF-16LE file decodes into ASCII interleaved with NULs, so a
   333	        # perfectly readable secret matches nothing while I/O "succeeds" and
   334	        # eligible still equals scanned.
   335	        try {
   336	            $bytes = [System.IO.File]::ReadAllBytes($full)
   337	        } catch {
   338	            FailExit ("Source secret scan could not read " + $rel + ": " + $_.Exception.Message)
   339	        }
   340	        $SourceScanned++
   341	        # Same two-encoding sweep the binary scan does, plus a percent-decoded pass
   342	        # of each: production normalises `magnet:?xt=urn%3Abtih%3A<hash>` back to
   343	        # `btih:<hash>` (verified via _magnet_dedupe_key) and interns it, so a scan
   344	        # that only sees the raw bytes misses an escaped magnet entirely.
   345	        $variants = New-Object System.Collections.Generic.List[string]
   346	        foreach ($enc in $Encodings) {
   347	            $decoded = $enc.encoding.GetString($bytes)
   348	            $variants.Add($decoded)
   349	            try { $variants.Add([System.Uri]::UnescapeDataString($decoded)) } catch { }
   350	        }
   351	        foreach ($text in $variants) {
   352	            foreach ($p in $Patterns) {
   353	                foreach ($m in [regex]::Matches($text, $p.rx, $RxOpts)) {
   354	                    if ($AllowedLiterals -ccontains $m.Value) { $SourceAllowed++; continue }
   355	                    $SourceHits += ("      " + $rel + "  [" + $p.name + "]")
   356	                }
   357	            }
   358	        }
   359	    }
   360	    if ($SourceHits.Count -gt 0) {
   361	        Write-Host "    Source secret scan LEAK:" -ForegroundColor Red
   362	        # File + pattern only, never the matched text (same reasoning as the binary
   363	        # scan above).
   364	        $SourceHits | Sort-Object -Unique | ForEach-Object { Write-Host $_ -ForegroundColor Red }
   365	        Write-Host "    If a hit is a synthetic fixture, add its exact value to `$AllowedLiterals." -ForegroundColor Red
   366	        FailExit "Source secret scan failed"
   367	    }
   368	    # A scan that walked nothing must never report success — that is the exact
   369	    # failure mode this step was rewritten to eliminate, so assert it explicitly
   370	    # instead of trusting the file list to be non-empty.
   371	    if ($SourceScanned -eq 0) {
   372	        FailExit "Source secret scan walked 0 files — the scan is not covering anything. Check git ls-files and skipExt."
   373	    }
   374	    if ($SourceScanned -ne $SourceEligible) {
   375	        FailExit ("Source secret scan read " + $SourceScanned + " of " + $SourceEligible + " eligible files; refusing to ship a partial scan.")
   376	    }
   377	    Ok ("No unexpected source secrets (" + $SourceScanned + " text files scanned, " + $SourceAllowed + " allowlisted fixture matches)")
   378	}
   379	
   380	# --------------------------------------------------------------------------
   381	# -AuditOnly: run just the scan and exit. The clean-tree gate is skipped on
   382	# this path ON PURPOSE — red-testing the scanner means planting a secret,
   383	# which necessarily dirties the tree. Never use this mode to ship.
   384	# --------------------------------------------------------------------------
   385	if ($AuditOnly) {
   386	    Write-Output "== AUDIT ONLY: source secret scan, no build =="
   387	    Invoke-SourceSecretScan
   388	    Write-Output "[PASS] audit-only scan clean"
   389	    exit 0
   390	}
   391	
   392	Step "Verifying working tree is clean"
   393	# The build reads the WORKING TREE (npm/cargo/PyInstaller all compile what is on
   394	# disk), but the manifest records `git rev-parse HEAD`. With uncommitted edits
   395	# those two describe different code, and the manifest silently vouches for a
   396	# commit that was never what shipped.
   397	#
   398	# Untracked files matter just as much and are easy to miss: `git ls-files` does
   399	# not see them, so the source scan skips them entirely — yet PyInstaller
   400	# resolves the sidecar's dependency graph from the repo root, so an untracked
   401	# top-level module CAN be pulled into sidecar.exe. Scanning "every tracked
   402	# file" is not the same as scanning every build input.
   403	$BuildStartHead = (& git -C $RepoRoot rev-parse HEAD).Trim()
   404	if ($LASTEXITCODE -ne 0) { FailExit "git rev-parse HEAD failed; refusing to build" }
   405	# --untracked-files=all explicitly: `status.showUntrackedFiles=no` in any
   406	# config layer would otherwise hide untracked files entirely, and untracked
   407	# top-level modules CAN be pulled into sidecar.exe by PyInstaller.
   408	$treeStatus = & git -C $RepoRoot status --porcelain --untracked-files=all
   409	if ($LASTEXITCODE -ne 0) { FailExit "git status failed (exit $LASTEXITCODE); refusing to build" }
   410	# assume-unchanged (h) and skip-worktree (S) make git report a clean tree while
   411	# the file on disk differs from the index — the build would compile content
   412	# that neither git status nor the source scan ever sees.
   413	$maskedEntries = & git -C $RepoRoot ls-files -v
   414	if ($LASTEXITCODE -ne 0) { FailExit "git ls-files -v failed; refusing to build" }
   415	$masked = @($maskedEntries | Where-Object { $_ -cmatch '^[a-z]' -or $_ -cmatch '^S ' })
   416	if ($masked.Count -gt 0) {
   417	    $masked | ForEach-Object { Write-Output ("      " + $_) }
   418	    FailExit "Tracked files are marked assume-unchanged/skip-worktree; git cannot vouch for their contents. Clear with: git update-index --no-assume-unchanged --no-skip-worktree <path>"
   419	}
   420	if ($treeStatus) {
   421	    Write-Output "    Working tree is not clean:"
   422	    $treeStatus | ForEach-Object { Write-Output ("      " + $_) }
   423	    FailExit "Refusing to build: commit or stash everything first, so git_commit describes what actually ships."
   424	}
   425	Ok "Working tree clean (tracked + untracked)"
   426	
   427	Step "Preparing release output directory"
   428	if (-not (Test-Path $ReleaseOutDir)) { New-Item -ItemType Directory -Force -Path $ReleaseOutDir | Out-Null }
   429	# Clean previous run's artifacts under release/ (zip, sums, manifest, staging).
   430	# We do NOT touch anything outside release/.
   431	Get-ChildItem -Path $ReleaseOutDir -File -ErrorAction SilentlyContinue |
   432	    Where-Object {
   433	        $_.Extension -in @(".zip", ".msi", ".exe") `
   434	            -or $_.Name -eq "SHA256SUMS.txt" `
   435	            -or $_.Name -eq "release-manifest.json"
   436	    } |
   437	    Remove-Item -Force
   438	if (Test-Path $StagingDir) { Remove-Item $StagingDir -Recurse -Force }
   439	Ok ("Output dir: " + $ReleaseOutDir)
   440	
   441	# ---------------------------------------------------------------------------
   442	# Step 1: Build sidecar.exe via PyInstaller
   443	# ---------------------------------------------------------------------------
   444	Step "Building sidecar.exe (npm run sidecar:build)"
   445	Push-Location $AppDir
   446	try {
   447	    & npm run sidecar:build
   448	    if ($LASTEXITCODE -ne 0) { FailExit "npm run sidecar:build exited with code $LASTEXITCODE" }
   449	} finally {
   450	    Pop-Location
   451	}
   452	if (-not (Test-Path $SidecarSource)) {
   453	    FailExit "sidecar.exe not produced at expected path: $SidecarSource"
   454	}
   455	Ok ("sidecar.exe at " + $SidecarSource)
   456	
   457	# ---------------------------------------------------------------------------
   458	# Step 2 + 3: Build frontend + Rust release exe via Tauri CLI.
   459	#
   460	# Plain `cargo build --release` doesn't pass the `tauri/custom-protocol`
   461	# feature flag, so the resulting binary still tries to load from
   462	# devUrl (http://localhost:1420) instead of the embedded dist/. Going
   463	# through `tauri build --no-bundle` handles three things in one call:
   464	#   - runs beforeBuildCommand (= `npm run build`) for fresh dist/
   465	#   - enables tauri/custom-protocol so the release binary loads from
   466	#     embedded assets
   467	#   - skips MSI / NSIS bundling so no installer artifacts leak in
   468	# ---------------------------------------------------------------------------
   469	Step "Building Rust release binary (npx tauri build --no-bundle)"
   470	# Scrub the build-host user path out of the binary. Rust's `file!()`
   471	# macro and panic strings bake the absolute path of every compiled
   472	# source file into the output, so without remapping the user's
   473	# Windows username + .cargo / project layout would be visible to
   474	# anyone strings(1)-ing the exe. `--remap-path-prefix` rewrites
   475	# those embedded paths at compile time. Three remaps cover the
   476	# usual suspects:
   477	#   - %USERPROFILE%\.cargo  → ~/.cargo            (dependency crates)
   478	#   - %USERPROFILE%\.rustup → ~/.rustup           (stdlib sources)
   479	#   - <repo root>           → <project>           (this project's own files)
   480	# Note: changing RUSTFLAGS invalidates the entire build cache, so
   481	# the first run after toggling this is a full cold compile
   482	# (~3-5 min on a warm dependency tree).
   483	$remapFlags = @(
   484	    "--remap-path-prefix=$($env:USERPROFILE)\.cargo=~/.cargo",
   485	    "--remap-path-prefix=$($env:USERPROFILE)\.rustup=~/.rustup",
   486	    "--remap-path-prefix=$RepoRoot=<project>"
   487	) -join ' '
   488	Ok ("RUSTFLAGS scrub: " + $remapFlags)
   489	$prevRustflags = $env:RUSTFLAGS
   490	$env:RUSTFLAGS = if ($prevRustflags) { "$prevRustflags $remapFlags" } else { $remapFlags }
   491	Push-Location $AppDir
   492	try {
   493	    & npx tauri build --no-bundle
   494	    if ($LASTEXITCODE -ne 0) { FailExit "tauri build exited with code $LASTEXITCODE" }
   495	} finally {
   496	    Pop-Location
   497	    # Restore prior RUSTFLAGS so subsequent processes (other cargo
   498	    # invocations in this shell session) aren't sticky-configured.
   499	    $env:RUSTFLAGS = $prevRustflags
   500	}
   501	$MainExeSource = Join-Path $CargoOutDir "javdbmagnet.exe"
   502	if (-not (Test-Path $MainExeSource)) { FailExit "javdbmagnet.exe missing: $MainExeSource" }
   503	Ok ("javdbmagnet.exe at " + $MainExeSource)
   504	
   505	# ---------------------------------------------------------------------------
   506	# Step 4: Stage portable folder under release/JavDBMagnet/
   507	# ---------------------------------------------------------------------------
   508	Step "Staging portable folder"
   509	New-Item -ItemType Directory -Force -Path $StagingDir | Out-Null
   510	
   511	Copy-Item -LiteralPath $MainExeSource -Destination (Join-Path $StagingDir "javdbmagnet.exe") -Force
   512	# Sidecar is named with target-triple in build/output; rename to plain
   513	# sidecar.exe so users see one clear sibling file.
   514	Copy-Item -LiteralPath $SidecarSource -Destination (Join-Path $StagingDir "sidecar.exe") -Force
   515	
   516	$ReadmeContent = @"
   517	JavDBMagnet $Version — Portable Edition
   518	=======================================
   519	
   520	USAGE
   521	-----
   522	雙擊 javdbmagnet.exe 即可啟動。**請保留 sidecar.exe 在同一個資料夾**，
   523	它是 JavDB / Real-Debrid HTTP sidecar，缺一不可。
   524	
   525	DATA LOCATIONS
   526	--------------
   527	Settings / cookies / pending:  %APPDATA%\JavDBMagnet\
   528	Logs:                          %LOCALAPPDATA%\JavDBMagnet\logs\
   529	RD API token:                  Windows Credential Manager (target: JavDBMagnet/RD_API_TOKEN)
   530	
   531	REMOVAL
   532	-------
   533	- 刪除這個 JavDBMagnet 資料夾即可移除程式本體（不會留 registry 殘渣）
   534	- 想清掉個人資料：
   535	    rmdir /s /q %APPDATA%\JavDBMagnet
   536	    rmdir /s /q %LOCALAPPDATA%\JavDBMagnet
   537	    cmdkey /delete:JavDBMagnet/RD_API_TOKEN
   538	
   539	SMARTSCREEN
   540	-----------
   541	首次啟動可能跳 SmartScreen 警告（未做 code signing）。比對 SHA256 後
   542	按「更多資訊 → 仍要執行」即可。
   543	
   544	詳見 repo 內 README.md / docs/troubleshooting/。
   545	"@
   546	Set-Content -Path (Join-Path $StagingDir "README.txt") -Value $ReadmeContent -Encoding utf8
   547	
   548	$StagedFiles = Get-ChildItem $StagingDir -Recurse -File | Select-Object FullName, Length
   549	Write-Host "    Staged files (" $StagedFiles.Count "):" -ForegroundColor Gray
   550	$StagedFiles | ForEach-Object {
   551	    $rel = $_.FullName.Substring($StagingDir.Length).TrimStart('\','/')
   552	    Write-Host ("      {0,10} bytes  {1}" -f $_.Length, $rel) -ForegroundColor Gray
   553	}
   554	
   555	# ---------------------------------------------------------------------------
   556	# Step 5: Audit staging folder — strict whitelist
   557	# ---------------------------------------------------------------------------
   558	Step "Auditing portable folder (whitelist)"
   559	$AllowedNames = @('javdbmagnet.exe', 'sidecar.exe', 'README.txt')
   560	# Explicitly verify none of the forbidden names slipped in even if the
   561	# whitelist somehow expanded.
   562	$ForbiddenNames = @('.env','.gitignore','cookies.txt','pending_torrents.json','magnet.txt')
   563	$StagingViolations = @()
   564	foreach ($f in $StagedFiles) {
   565	    $rel = $f.FullName.Substring($StagingDir.Length).TrimStart('\','/')
   566	    $leaf = Split-Path $f.FullName -Leaf
   567	    # No subdirectories allowed.
   568	    if ($rel -match '[\\/]') {
   569	        $StagingViolations += "subdir entry: $rel"
   570	        continue
   571	    }
   572	    if ($AllowedNames -notcontains $leaf) {
   573	        $StagingViolations += "unexpected file: $rel"
   574	    }
   575	    if ($ForbiddenNames -contains $leaf) { $StagingViolations += "forbidden: $leaf" }
   576	    if ($leaf -like '.env.*' -or $leaf -like '*.log' -or $leaf -like '*.token' -or $leaf -like '*.spec') {
   577	        $StagingViolations += "forbidden pattern: $leaf"
   578	    }
   579	}
   580	if ($StagingViolations.Count -gt 0) {
   581	    Write-Host "    Staging violations:" -ForegroundColor Red
   582	    $StagingViolations | ForEach-Object { Write-Host ("      " + $_) -ForegroundColor Red }
   583	    FailExit "Portable folder audit failed"
   584	}
   585	Ok "Portable folder contains only allowed artifacts"
   586	
   587	# ---------------------------------------------------------------------------
   588	# Step 6: Binary content scan — secrets must NOT be baked in
   589	# ---------------------------------------------------------------------------
   590	Step "Binary content scan for embedded secrets"
   591	$ScanTargets = @(
   592	    (Join-Path $StagingDir "javdbmagnet.exe"),
   593	    (Join-Path $StagingDir "sidecar.exe")
   594	)
   595	foreach ($exe in $ScanTargets) {
   596	    $name = Split-Path $exe -Leaf
   597	    $bytes = [System.IO.File]::ReadAllBytes($exe)
   598	    $hits = @()
   599	    foreach ($enc in $Encodings) {
   600	        $decoded = $enc.encoding.GetString($bytes)
   601	        # Percent-decoded pass for the same reason as the source scan: an
   602	        # escaped magnet is still a magnet by the time production sees it.
   603	        $texts = @($decoded)
   604	        try { $texts += [System.Uri]::UnescapeDataString($decoded) } catch { }
   605	        foreach ($text in $texts) {
   606	        foreach ($p in $Patterns) {
   607	            $regexMatches = [regex]::Matches($text, $p.rx, $RxOpts)
   608	            if ($regexMatches.Count -gt 0) {
   609	                # Artifact + pattern + count ONLY. Never echo the matched value:
   610	                # the whole point of this step is that a secret reached a binary,
   611	                # and printing it would copy that secret into the build log —
   612	                # which, once this runs in CI, is a persistent artifact of its
   613	                # own. Reproduce locally if you need to see the value.
   614	                $hits += "      [$($enc.label)] $($p.name)  count=$($regexMatches.Count)"
   615	                $BinaryHitCount += $regexMatches.Count
   616	            }
   617	        }
   618	        }
   619	    }
   620	    if ($hits.Count -gt 0) {
   621	        Write-Host "    [$name] LEAK:" -ForegroundColor Red
   622	        $hits | ForEach-Object { Write-Host $_ -ForegroundColor Red }
   623	        $ScanFail = $true
   624	    } else {
   625	        Ok ("[$name] no leak patterns (ASCII + UTF-16LE)")
   626	    }
   627	}
   628	if ($ScanFail) { FailExit "Binary content scan failed" }
   629	Invoke-SourceSecretScan
   630	
   631	# ---------------------------------------------------------------------------
   632	# Step 8: Compress staging dir to release/JavDBMagnet_<v>_portable.zip
   633	# ---------------------------------------------------------------------------
   634	Step "Creating portable zip"
   635	if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
   636	# Pass the directory itself (not its contents) so the zip root is
   637	# "JavDBMagnet/<files>", matching the spec.
   638	Compress-Archive -Path $StagingDir -DestinationPath $ZipPath -CompressionLevel Optimal
   639	if (-not (Test-Path $ZipPath)) { FailExit "Compress-Archive did not produce $ZipPath" }
   640	Ok ("Wrote " + $ZipPath)
   641	
   642	# ---------------------------------------------------------------------------
   643	# Step 9: SHA256 for zip + 2 exes
   644	# ---------------------------------------------------------------------------
   645	Step "Computing SHA256"
   646	$HashTargets = @(
   647	    @{ label = "portable.zip"; path = $ZipPath },
   648	    @{ label = "exe.app";      path = (Join-Path $StagingDir "javdbmagnet.exe") },
   649	    @{ label = "exe.sidecar";  path = (Join-Path $StagingDir "sidecar.exe") }
   650	)
   651	$Hashes = @{}
   652	foreach ($t in $HashTargets) {
   653	    $h = ((Get-FileHash -Path $t.path -Algorithm SHA256).Hash)
   654	    $size = (Get-Item $t.path).Length
   655	    $Hashes[$t.label] = @{ path = $t.path; sha256 = $h; bytes = $size }
   656	    Write-Host ("    {0,-13} {1}  ({2:N0} bytes)  {3}" -f $t.label, $h, $size, (Split-Path $t.path -Leaf)) -ForegroundColor Gray
   657	}
   658	
   659	# ---------------------------------------------------------------------------
   660	# Step 10: Write SHA256SUMS.txt + manifest
   661	# ---------------------------------------------------------------------------
   662	Step "Writing release manifest"
   663	$SumsPath = Join-Path $ReleaseOutDir "SHA256SUMS.txt"
   664	$sumsLines = $HashTargets | ForEach-Object {
   665	    $h = $Hashes[$_.label]
   666	    "$($h.sha256)  $(Split-Path $h.path -Leaf)"
   667	}
   668	Set-Content -Path $SumsPath -Value $sumsLines -Encoding utf8
   669	Ok ("Wrote " + $SumsPath)
   670	
   671	# Re-verify the snapshot. The clean-tree assertion at Step 0 is minutes old by
   672	# now: PyInstaller, cargo and the two scans all ran in between, and any edit or
   673	# checkout during that window would leave the manifest vouching for a commit
   674	# that is not what was compiled and scanned. Checking only at the start, then
   675	# hardcoding `working_tree_clean = true`, would make the field an assertion
   676	# about the past rather than about the artifact.
   677	Step "Re-verifying source snapshot after build"
   678	$ManifestPath = Join-Path $ReleaseOutDir "release-manifest.json"
   679	$gitCommit = (& git -C $RepoRoot rev-parse HEAD).Trim()
   680	if ($LASTEXITCODE -ne 0) { FailExit "git rev-parse HEAD failed after build" }
   681	if ($gitCommit -ne $BuildStartHead) {
   682	    FailExit ("HEAD moved during the build (" + $BuildStartHead + " -> " + $gitCommit + "); the artifacts do not match either commit.")
   683	}
   684	$treeStatusAfter = & git -C $RepoRoot status --porcelain --untracked-files=all
   685	if ($LASTEXITCODE -ne 0) { FailExit "git status failed after build" }
   686	if ($treeStatusAfter) {
   687	    $treeStatusAfter | ForEach-Object { Write-Output ("      " + $_) }
   688	    FailExit "Working tree changed during the build; the scanned source is not what shipped."
   689	}
   690	Ok ("Snapshot unchanged through build: " + $gitCommit)
   691	$manifest = [ordered]@{
   692	    name        = $pkgJson.name
   693	    version     = $Version
   694	    git_commit  = $gitCommit
   695	    built_at    = (Get-Date).ToUniversalTime().ToString("o")
   696	    bundle      = "portable-zip"
   697	    artifacts   = @(
   698	        $HashTargets | ForEach-Object {
   699	            $h = $Hashes[$_.label]
   700	            [ordered]@{
   701	                label      = $_.label
   702	                name       = (Split-Path $h.path -Leaf)
   703	                sha256     = $h.sha256
   704	                size_bytes = $h.bytes
   705	            }
   706	        }
   707	    )
   708	    audit       = @{
   709	        portable_forbidden_files = 0
   710	        binary_secret_hits       = $BinaryHitCount
   711	        source_secret_hits       = $SourceHits.Count
   712	        # Denominators, so `source_secret_hits: 0` is interpretable: without
   713	        # them a scan that covered nothing is indistinguishable from one that
   714	        # covered the whole repo and found nothing. `eligible` vs `scanned`
   715	        # must be equal — a gap means files were dropped.
   716	        source_files_eligible    = $SourceEligible
   717	        source_files_scanned     = $SourceScanned
   718	        source_allowlisted_hits  = $SourceAllowed
   719	        # Checked before the build and re-checked after it. This does NOT prove
   720	        # the compiler observed exactly this snapshot: an edit made and reverted
   721	        # mid-build leaves both checks clean while an artifact was produced from
   722	        # transient source. The field is named for what is actually verified.
   723	        # Proving the stronger property requires building from an immutable
   724	        # checkout (git archive / a throwaway worktree), which this pipeline
   725	        # does not yet do.
   726	        working_tree_clean       = $true
   727	        source_snapshot_verified = "pre_and_post_build_clean"
   728	    }
   729	    signing     = @{
   730	        requested = ($env:SIGN -eq "1")
   731	        performed = $false
   732	    }
   733	}
   734	$manifestJson = $manifest | ConvertTo-Json -Depth 6
   735	Set-Content -Path $ManifestPath -Value $manifestJson -Encoding utf8
   736	Ok ("Wrote " + $ManifestPath)
   737	
   738	# ---------------------------------------------------------------------------
   739	# Step 11: Final summary
   740	# ---------------------------------------------------------------------------
   741	if ($env:SIGN -eq "1") {
   742	    Warn "SIGN=1 placeholder — code signing is not implemented in this script."
   743	    Warn "Wire your signtool / osslsigncode call here once you have a cert."
   744	}
   745	
   746	Write-Host ""
   747	Write-Host "==> RELEASE READY (portable)" -ForegroundColor Green
   748	Write-Host ("    Portable zip   : " + $ZipPath) -ForegroundColor Green
   749	Write-Host ("    javdbmagnet.exe: " + (Join-Path $StagingDir "javdbmagnet.exe")) -ForegroundColor Green
   750	Write-Host ("    sidecar.exe    : " + (Join-Path $StagingDir "sidecar.exe")) -ForegroundColor Green
   751	Write-Host ("    SHA256SUMS     : " + $SumsPath) -ForegroundColor Green
   752	Write-Host ("    Manifest       : " + $ManifestPath) -ForegroundColor Green
   753	Write-Host ""
   754	exit 0

exec
/bin/bash -lc "printf '%s\\n' '---CURRENT 1-390---'; sed -n '1,390p' scripts/build-release.ps1 | nl -ba; printf '%s\\n' '---DIFF HUNKS---'; git diff --unified=12 3f55ec0"'^ 3f55ec0 -- scripts/build-release.ps1; printf '"'%s\\n' '---RELATED CALLERS---'; rg -n \"build-release|AuditOnly|source_secret|release-manifest|SHA256SUMS\" --glob '"'!scripts/build-release.ps1'"' ." in /home/cy5407/javdb-magnet-workbench
 succeeded in 0ms:
---CURRENT 1-390---
     1	# build-release.ps1 — portable release pipeline
     2	#
     3	# Produces a portable ZIP that ships javdbmagnet.exe + sidecar.exe in a
     4	# single folder. End-users extract the zip and double-click the exe —
     5	# no installer, no Program Files, no Start Menu entry, no registry.
     6	#
     7	# Pipeline:
     8	#   1. Build sidecar.exe         (npm run sidecar:build → app/src-tauri/binaries/...)
     9	#   2. Build frontend + Rust exe (npx tauri build --no-bundle from app/)
    10	#                                 — single CLI call enables the
    11	#                                 `tauri/custom-protocol` feature so the
    12	#                                 release binary embeds dist/ instead of
    13	#                                 reaching for the dev server
    14	#   3. Stage release/JavDBMagnet/ (javdbmagnet.exe + sidecar.exe + README.txt)
    15	#   4. Audit staging dir         (whitelist: exe + exe + README.txt; nothing else)
    16	#   5. Binary content scan       (tokens / magnets / Cloudflare cookies must NOT
    17	#                                 appear in either exe)
    18	#   6. Source secret scan        (same patterns, case-insensitive, over every
    19	#                                 tracked text file; no file-level exemptions —
    20	#                                 known fixtures are allowlisted by exact
    21	#                                 value. Fails closed on unreadable files, on
    22	#                                 an eligible/scanned mismatch, and on 0 files)
    23	#   7. Compress-Archive → release/JavDBMagnet_<version>_portable.zip
    24	#   8. SHA256 for zip + 2 exes  → release/SHA256SUMS.txt
    25	#   9. Write release/release-manifest.json
    26	#  10. Print final paths
    27	#
    28	# Any audit / scan failure → exit 1. Half-baked staging stays for inspection.
    29	#
    30	# Code signing is NOT performed. $env:SIGN -eq "1" emits a placeholder
    31	# warning; wire signtool / osslsigncode here once a cert exists.
    32	#
    33	# Run:
    34	#     pwsh -File scripts\build-release.ps1
    35	# Or from app/:
    36	#     npm run release
    37	
    38	param(
    39	    # Run ONLY the source secret scan and exit. No build, no staging, no zip.
    40	    # Added so this gate can actually be executed and red-tested on its own:
    41	    # a full release run costs minutes of PyInstaller + cargo before it would
    42	    # ever reach the scan.
    43	    [switch]$AuditOnly
    44	)
    45	
    46	$ErrorActionPreference = "Stop"
    47	Set-StrictMode -Version Latest
    48	
    49	# ---------------------------------------------------------------------------
    50	# Paths
    51	# ---------------------------------------------------------------------------
    52	$ScriptDir     = Split-Path -Parent $MyInvocation.MyCommand.Path
    53	$RepoRoot      = Split-Path -Parent $ScriptDir
    54	$AppDir        = Join-Path $RepoRoot "app"
    55	$TauriSrcDir   = Join-Path $AppDir "src-tauri"
    56	$CargoOutDir   = Join-Path $TauriSrcDir "target\release"
    57	$BinariesDir   = Join-Path $TauriSrcDir "binaries"
    58	$ReleaseOutDir = Join-Path $RepoRoot "release"
    59	
    60	# Sidecar artifact path produced by build_sidecar.py
    61	$SidecarSource = Join-Path $BinariesDir "sidecar-x86_64-pc-windows-msvc.exe"
    62	
    63	# Read version straight from app/package.json so the zip name follows it.
    64	$PkgJsonPath = Join-Path $AppDir "package.json"
    65	$pkgJson = Get-Content $PkgJsonPath -Raw | ConvertFrom-Json
    66	$Version = $pkgJson.version
    67	$PortableFolderName = "JavDBMagnet"
    68	$StagingDir = Join-Path $ReleaseOutDir $PortableFolderName
    69	$ZipName    = "JavDBMagnet_${Version}_portable.zip"
    70	$ZipPath    = Join-Path $ReleaseOutDir $ZipName
    71	
    72	function Step($title) {
    73	    Write-Output ""
    74	    Write-Output "==> $title"
    75	}
    76	function Ok($msg)   { Write-Output "    [OK]   $msg" }
    77	function Warn($msg) { Write-Output "    [WARN] $msg" }
    78	function FailExit($msg) {
    79	    Write-Output ""
    80	    Write-Output "[FAIL] $msg"
    81	    exit 1
    82	}
    83	# ---------------------------------------------------------------------------
    84	# Step 0: Prepare release/ output dir
    85	# ---------------------------------------------------------------------------
    86	
    87	$Patterns = @(
    88	    # Every pattern below is matched case-INSENSITIVELY (see $RxOpts). URI
    89	    # schemes are case-insensitive per RFC 3986, and this project's own parser
    90	    # agrees: sidecar.py lower-cases before its `startswith("magnet:")` check
    91	    # and _REDACT_MAGNET_RX carries re.IGNORECASE. A case-sensitive scan would
    92	    # therefore miss `MAGNET:?XT=URN:BTIH:...` — a string production happily
    93	    # accepts and interns. Verified: register_magnets returns ok for the
    94	    # upper-case form while the old pattern did not match it at all.
    95	    # GREEDY `{40,}`, not `{40}` and not `{40}(?!hex)`. All three were tried:
    96	    #   {40}            — a 42-hex value matches its first 40 chars, and if
    97	    #                     those 40 are allowlisted the real value passes.
    98	    #   {40}(?![hex])   — a 42-hex value then matches NOTHING AT ALL (the
    99	    #                     lookahead fails at every start offset), which is a
   100	    #                     bigger hole than the one it was meant to close. This
   101	    #                     was caught by executing the red test, not by reading.
   102	    #   {40,}           — consumes the whole run, so anything longer than an
   103	    #                     allowlisted literal is a distinct value and fails.
   104	    @{ name = 'urn:btih:<40+hex>';           rx = 'urn:btih:[a-fA-F0-9]{40,}' },
   105	    # BitTorrent v1 infohashes are 40 hex OR 32 base32 (BEP 9); v2 uses a
   106	    # different URN entirely (`urn:btmh:`, BEP 52). An earlier commit message
   107	    # claimed "64-hex btih v2" — that form does not exist. Cover all three.
   108	    @{ name = 'urn:btih:<32+base32>';        rx = 'urn:btih:[A-Z2-7]{32,}' },
   109	    @{ name = 'urn:btmh: (BitTorrent v2)';   rx = 'urn:bt' + 'mh:[a-fA-F0-9]{10,}' },
   110	    # `{16,}` rather than `+`: redact_magnet()'s output is a fixed 8 hex chars,
   111	    # so `+` made this pattern flag the project's own CORRECTLY REDACTED form.
   112	    # Real v1 infohashes are 40 hex (or 32 base32); 16 is a safe floor that
   113	    # passes the 8-char redacted form and catches every real length.
   114	    @{ name = 'magnet:?xt=';                 rx = 'magnet:\?xt=urn:bt' + '[im]h:[a-zA-Z0-9]{16,}' },
   115	    # Length floors and separator grammar now follow what PRODUCTION accepts,
   116	    # not what a "realistic" secret looks like. secret_store.rs takes 1-255
   117	    # ASCII alphanumerics; legacy_import.rs trims whitespace around `=` and
   118	    # strips surrounding quotes; parse_cookie_string trims each `k = v` pair.
   119	    # A scanner narrower than the parser is a scanner with a documented hole,
   120	    # so `\s*`, optional quotes and a floor of 1 are all deliberate. The cost
   121	    # is that short test fixtures now match — they are listed in
   122	    # $AllowedLiterals, which is exactly the reviewable-diff tradeoff this
   123	    # design already makes everywhere else.
   124	    @{ name = 'Cloudflare clearance cookie'; rx = 'cf' + '_clearance\s*=\s*["'']?' + '[A-Za-z0-9_.~+/=-]{1,}' },
   125	    @{ name = 'Cloudflare bot cookie';       rx = '__cf' + '_bm\s*=\s*["'']?' + '[A-Za-z0-9_.~+/=-]{1,}' },
   126	    @{ name = 'JavDB session cookie';        rx = '_jdb' + '_session\s*=\s*["'']?' + '[A-Za-z0-9_.~+/=-]{1,}' },
   127	    @{ name = 'remember_me_token=';          rx = 'remember_me_token\s*=\s*["'']?' + '[A-Za-z0-9_.~+/=-]{1,}' },
   128	    # token68 (RFC 7235) allows -._~+/ and trailing '='; the old [A-Za-z0-9_-]
   129	    # stopped at the first '.' and reported a truncated match.
   130	    @{ name = 'Authorization bearer header'; rx = 'Authorization:\s*' + 'Bearer\s+' + '[A-Za-z0-9_.~+/=-]{8,}' },
   131	    @{ name = 'Bearer <token>';              rx = 'Bearer\s+' + '[A-Za-z0-9_.~+/=-]{16,}' },
   132	    @{ name = 'RD_API_TOKEN=<value>';        rx = 'RD_API' + '_TOKEN\s*=\s*["'']?' + '[A-Za-z0-9_-]{1,}' }
   133	)
   134	
   135	# All regex evaluation in this script goes through these options. See the
   136	# comment above $Patterns for why IgnoreCase is not optional here.
   137	$RxOpts = [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
   138	
   139	$ScanFail = $false
   140	$BinaryHitCount = 0
   141	# We decode the binary bytes both as ASCII *and* UTF-16LE because PE
   142	# images routinely embed strings in both encodings:
   143	#   - ASCII / UTF-8 covers Rust &str literals, format!() output, and
   144	#     anything wired through libc-style APIs.
   145	#   - UTF-16LE covers strings handed to the Win32 wide API (e.g. a
   146	#     `let path = format!("HKCU\\...\\{}", token);` later passed to
   147	#     `RegOpenKeyExW`), which would otherwise sail past an ASCII-only
   148	#     scan even though the secret material is plainly readable in a
   149	#     hex dump.
   150	# Running both passes is cheap (two regex sweeps over the same byte
   151	# blob); failing to do it would silently halve the scan's coverage.
   152	$Encodings = @(
   153	    @{ label = 'ASCII';      encoding = [System.Text.Encoding]::ASCII },
   154	    @{ label = 'UTF-16LE';   encoding = [System.Text.Encoding]::Unicode }
   155	)
   156	
   157	function Invoke-SourceSecretScan {
   158	
   159	    # ---------------------------------------------------------------------------
   160	    # Step 7: Source secret scan — over EVERY tracked file
   161	    #
   162	    # This used to derive its file list from `git diff <origin/HEAD>..HEAD` plus
   163	    # the working-tree diff. That made coverage depend on where HEAD happened to
   164	    # sit: cutting a release from an already-pushed master left both diffs empty,
   165	    # so the scan walked ZERO files and still wrote `source_secret_hits: 0` into
   166	    # the manifest — a vacuous pass that read exactly like a real one. It was
   167	    # found the hard way: a magnet literal sat in verify-windows-build.ps1 from
   168	    # the commit that introduced it and was never once scanned, until an
   169	    # unrelated edit to that file finally pulled it into the diff.
   170	    #
   171	    # The file list now comes from `git ls-files`, so coverage is a property of
   172	    # the repo rather than of the branch topology. Content is read from disk, so
   173	    # uncommitted edits to tracked files are scanned as they actually are.
   174	    # Untracked files are deliberately out of scope: they are neither committed
   175	    # nor shipped inside the portable zip.
   176	    # ---------------------------------------------------------------------------
   177	    Step "Source secret scan (all tracked text files)"
   178	    # -z + NUL split: without it git quotes paths containing non-ASCII or control
   179	    # characters ("\303\251.md"), and the quoted name matches nothing on disk — the
   180	    # file is then silently dropped from the scan.
   181	    # Windows PowerShell 5.1 decodes native-command output using the console code
   182	    # page, not UTF-8. A tracked filename with non-ASCII characters would come back
   183	    # mangled, Test-Path would then fail to resolve it, and the entry would vanish
   184	    # from the scan. Force UTF-8 for the duration of the git call.
   185	    $prevOutEnc = [Console]::OutputEncoding
   186	    try {
   187	        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
   188	        $lsRaw = & git -C $RepoRoot ls-files -z
   189	        $lsExit = $LASTEXITCODE
   190	    } finally {
   191	        [Console]::OutputEncoding = $prevOutEnc
   192	    }
   193	    if ($lsExit -ne 0) {
   194	        Write-Error "FATAL: source-secret-scan git ls-files failed (exit $lsExit). Refusing to ship a release without a source scan."
   195	        exit 1
   196	    }
   197	    $sourceFiles = @(($lsRaw -join "") -split "`0" | Where-Object { $_ } | Sort-Object -Unique)
   198	    $skipExt = @('.exe', '.msi', '.zip', '.7z', '.png', '.ico', '.icns', '.dll')
   199	
   200	    # Known-synthetic literals, allowlisted BY EXACT VALUE rather than by file.
   201	    #
   202	    # The previous design skipped whole files (commands.rs, legacy_import.rs,
   203	    # tests/, *.test.ts, four prose docs, and this script). That exempted ~23 text
   204	    # files INCLUDING production Rust and the gate itself: any real token later
   205	    # pasted into them would never have been seen. "Every tracked file" was not
   206	    # true.
   207	    #
   208	    # Now nothing is exempt. Every tracked text file is scanned, and a match only
   209	    # passes if its exact text appears below. Each entry is a fixture whose
   210	    # synthetic nature is self-evident (DEADBEEF / repeated nibbles / sequential
   211	    # counters / obvious placeholder session names), except the one PoC hash in the
   212	    # security-audit archive, which demonstrates a dedupe-key collision where the
   213	    # point is that the SAME arbitrary string appears twice.
   214	    #
   215	    # Adding an entry here is a visible, reviewable diff line — unlike adding a
   216	    # file to a skip list, which blinds the scanner to everything in that file
   217	    # forever. A NEW fixture will fail the build until it is listed; that is the
   218	    # intended cost.
   219	    $AllowedLiterals = @(
   220	        'urn:btih:0201592fDEADBEEF0201592fDEADBEEF02015920',
   221	        'urn:btih:0201592fdeadbeef0201592fdeadbeef02015920',
   222	        'urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF',
   223	        'urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEF',
   224	        'urn:btih:0201592f00000000000000000000000000000001',
   225	        'urn:btih:0201592f00000000000000000000000000000002',
   226	        'urn:btih:0000000000000000000000000000000000000001',
   227	        'urn:btih:0000000000000000000000000000000000000002',
   228	        'urn:btih:0000000000000000000000000000000000000003',
   229	        'urn:btih:0123456789abcdef0123456789abcdef01234567',
   230	        'urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
   231	        'urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
   232	        'urn:btih:cccccccccccccccccccccccccccccccccccccccc',
   233	        'urn:btih:ABCDEF0123456789ABCDEF0123456789ABCDEF01',
   234	        'urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
   235	        'urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
   236	        'urn:btih:cccccccccccccccccccccccccccccccc',
   237	        # Dedupe-key collision PoC (prompt/security-audit-fixes-2026-07-28.md).
   238	        'urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a',
   239	        'magnet:?xt=urn:btih:0201592fDEADBEEF0201592fDEADBEEF02015920',
   240	        'magnet:?xt=urn:btih:0201592fdeadbeef0201592fdeadbeef02015920',
   241	        'magnet:?xt=urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF',
   242	        'magnet:?xt=urn:btih:0201592f00000000000000000000000000000001',
   243	        'magnet:?xt=urn:btih:0201592f00000000000000000000000000000002',
   244	        'magnet:?xt=urn:btih:0000000000000000000000000000000000000001',
   245	        'magnet:?xt=urn:btih:0000000000000000000000000000000000000002',
   246	        'magnet:?xt=urn:btih:0000000000000000000000000000000000000003',
   247	        'magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567',
   248	        'magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
   249	        'magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
   250	        'magnet:?xt=urn:btih:cccccccccccccccccccccccccccccccccccccccc',
   251	        'magnet:?xt=urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a',
   252	        'magnet:?xt=urn:btih:0123456789abcdef',
   253	        'magnet:?xt=urn:btih:ABCDEF0123456789',
   254	        'MAGNET:?xt=urn:btih:ABCDEF0123456789',
   255	        'MAGNET:?xt=urn:btih:ABCDEF0123456789ABCDEF0123456789ABCDEF01',
   256	        'magnet:?xt=urn:btih:fedcba9876543210',
   257	        # Cookie / token fixtures. These only started matching once the patterns
   258	    # were widened to production's grammar (floor of 1 char, optional quotes
   259	    # and whitespace around `=`). Every value here is self-evidently a
   260	    # placeholder — XXX, `...`, brand_new, clear_me — and lives in a test or
   261	    # in documentation showing the cookie format.
   262	    'RD_API_TOKEN=abc-123',
   263	    '_jdb_session=...',
   264	    '_jdb_session=XXX',
   265	    '_jdb_session=abc',
   266	    '_jdb_session=abc123',
   267	    '_jdb_session=brand_new',
   268	    '_jdb_session=clear_me',
   269	    '_jdb_session=e2e_jdb_session',
   270	    '_jdb_session=keep_me_alive',
   271	    '_jdb_session=keyring_only',
   272	    '_jdb_session=label_test',
   273	    '_jdb_session=new',
   274	    '_jdb_session=older_keyring_value',
   275	    '_jdb_session=paste_session',
   276	    '_jdb_session=preexisting_session',
   277	    '_jdb_session=regress_session',
   278	    '_jdb_session=resurrect_me',
   279	    '_jdb_session=xyz',
   280	    'cf_clearance=...',
   281	    'cf_clearance=XXX',
   282	    'cf_clearance=brand_new',
   283	    'cf_clearance=clear_cf',
   284	    'cf_clearance=e2e_cf_clearance',
   285	    'cf_clearance=fresh',
   286	    'cf_clearance=label_test_cf',
   287	    'cf_clearance=paste_cf',
   288	    'cf_clearance=preexisting_cf',
   289	    'cf_clearance=regress_cf',
   290	    'cf_clearance=resurrect_cf',
   291	    'cf_clearance=xyz',
   292	    'cf_clearance=xyz789',
   293	    # Placeholder cookie values in the Rust cookie-store tests.
   294	        '_jdb_session=paste_session',
   295	        '_jdb_session=keep_me_alive',
   296	        '_jdb_session=e2e_jdb_session',
   297	        '_jdb_session=regress_session',
   298	        '_jdb_session=preexisting_session',
   299	        '_jdb_session=label_test',
   300	        '_jdb_session=older_keyring_value',
   301	        '_jdb_session=keyring_only',
   302	        '_jdb_session=resurrect_me'
   303	    )
   304	
   305	    $SourceHits    = @()
   306	    $SourceEligible = 0   # tracked, non-binary, i.e. in scope
   307	    $SourceScanned  = 0   # actually read and regexed
   308	    $SourceAllowed  = 0   # matched but present in $AllowedLiterals
   309	    foreach ($rel in $sourceFiles) {
   310	        $full = Join-Path $RepoRoot $rel
   311	        if ($skipExt -contains ([System.IO.Path]::GetExtension($rel).ToLowerInvariant())) { continue }
   312	        $SourceEligible++
   313	        # -LiteralPath: a tracked file called `notes[1].md` is a valid wildcard to
   314	        # Test-Path, which would report it missing.
   315	        #
   316	        # Fail CLOSED here, and count the entry as eligible BEFORE testing it. The
   317	        # earlier version skipped unresolvable paths before incrementing, so the
   318	        # eligible-equals-scanned invariant could never detect them — the exact
   319	        # blind spot that invariant was added to close. The working tree is
   320	        # verified clean at Step 0, so every index entry must exist on disk; one
   321	        # that does not means the path came back mangled (encoding) or something
   322	        # changed underneath the build.
   323	        if (-not (Test-Path -LiteralPath $full -PathType Leaf)) {
   324	            FailExit ("Source secret scan could not resolve tracked path: " + $rel + " — refusing to ship a partial scan.")
   325	        }
   326	        # Fail CLOSED on read errors. The old code used -ErrorAction SilentlyContinue
   327	        # and `continue`d on $null, so an unreadable file vanished from the scan
   328	        # while the run still reported success — a file the scanner could not read
   329	        # is exactly the file worth worrying about.
   330	        # Read BYTES, not text. Get-Content -Raw picks an encoding for you, and the
   331	        # default differs between Windows PowerShell 5.1 and PowerShell 7: a
   332	        # BOM-less UTF-16LE file decodes into ASCII interleaved with NULs, so a
   333	        # perfectly readable secret matches nothing while I/O "succeeds" and
   334	        # eligible still equals scanned.
   335	        try {
   336	            $bytes = [System.IO.File]::ReadAllBytes($full)
   337	        } catch {
   338	            FailExit ("Source secret scan could not read " + $rel + ": " + $_.Exception.Message)
   339	        }
   340	        $SourceScanned++
   341	        # Same two-encoding sweep the binary scan does, plus a percent-decoded pass
   342	        # of each: production normalises `magnet:?xt=urn%3Abtih%3A<hash>` back to
   343	        # `btih:<hash>` (verified via _magnet_dedupe_key) and interns it, so a scan
   344	        # that only sees the raw bytes misses an escaped magnet entirely.
   345	        $variants = New-Object System.Collections.Generic.List[string]
   346	        foreach ($enc in $Encodings) {
   347	            $decoded = $enc.encoding.GetString($bytes)
   348	            $variants.Add($decoded)
   349	            try { $variants.Add([System.Uri]::UnescapeDataString($decoded)) } catch { }
   350	        }
   351	        foreach ($text in $variants) {
   352	            foreach ($p in $Patterns) {
   353	                foreach ($m in [regex]::Matches($text, $p.rx, $RxOpts)) {
   354	                    if ($AllowedLiterals -ccontains $m.Value) { $SourceAllowed++; continue }
   355	                    $SourceHits += ("      " + $rel + "  [" + $p.name + "]")
   356	                }
   357	            }
   358	        }
   359	    }
   360	    if ($SourceHits.Count -gt 0) {
   361	        Write-Host "    Source secret scan LEAK:" -ForegroundColor Red
   362	        # File + pattern only, never the matched text (same reasoning as the binary
   363	        # scan above).
   364	        $SourceHits | Sort-Object -Unique | ForEach-Object { Write-Host $_ -ForegroundColor Red }
   365	        Write-Host "    If a hit is a synthetic fixture, add its exact value to `$AllowedLiterals." -ForegroundColor Red
   366	        FailExit "Source secret scan failed"
   367	    }
   368	    # A scan that walked nothing must never report success — that is the exact
   369	    # failure mode this step was rewritten to eliminate, so assert it explicitly
   370	    # instead of trusting the file list to be non-empty.
   371	    if ($SourceScanned -eq 0) {
   372	        FailExit "Source secret scan walked 0 files — the scan is not covering anything. Check git ls-files and skipExt."
   373	    }
   374	    if ($SourceScanned -ne $SourceEligible) {
   375	        FailExit ("Source secret scan read " + $SourceScanned + " of " + $SourceEligible + " eligible files; refusing to ship a partial scan.")
   376	    }
   377	    Ok ("No unexpected source secrets (" + $SourceScanned + " text files scanned, " + $SourceAllowed + " allowlisted fixture matches)")
   378	}
   379	
   380	# --------------------------------------------------------------------------
   381	# -AuditOnly: run just the scan and exit. The clean-tree gate is skipped on
   382	# this path ON PURPOSE — red-testing the scanner means planting a secret,
   383	# which necessarily dirties the tree. Never use this mode to ship.
   384	# --------------------------------------------------------------------------
   385	if ($AuditOnly) {
   386	    Write-Output "== AUDIT ONLY: source secret scan, no build =="
   387	    Invoke-SourceSecretScan
   388	    Write-Output "[PASS] audit-only scan clean"
   389	    exit 0
   390	}
---DIFF HUNKS---
diff --git a/scripts/build-release.ps1 b/scripts/build-release.ps1
index daf1416..d2f0de9 100644
--- a/scripts/build-release.ps1
+++ b/scripts/build-release.ps1
@@ -26,24 +26,32 @@
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
 
+param(
+    # Run ONLY the source secret scan and exit. No build, no staging, no zip.
+    # Added so this gate can actually be executed and red-tested on its own:
+    # a full release run costs minutes of PyInstaller + cargo before it would
+    # ever reach the scan.
+    [switch]$AuditOnly
+)
+
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
@@ -66,39 +74,358 @@ function Step($title) {
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
+
+$Patterns = @(
+    # Every pattern below is matched case-INSENSITIVELY (see $RxOpts). URI
+    # schemes are case-insensitive per RFC 3986, and this project's own parser
+    # agrees: sidecar.py lower-cases before its `startswith("magnet:")` check
+    # and _REDACT_MAGNET_RX carries re.IGNORECASE. A case-sensitive scan would
+    # therefore miss `MAGNET:?XT=URN:BTIH:...` — a string production happily
+    # accepts and interns. Verified: register_magnets returns ok for the
+    # upper-case form while the old pattern did not match it at all.
+    # GREEDY `{40,}`, not `{40}` and not `{40}(?!hex)`. All three were tried:
+    #   {40}            — a 42-hex value matches its first 40 chars, and if
+    #                     those 40 are allowlisted the real value passes.
+    #   {40}(?![hex])   — a 42-hex value then matches NOTHING AT ALL (the
+    #                     lookahead fails at every start offset), which is a
+    #                     bigger hole than the one it was meant to close. This
+    #                     was caught by executing the red test, not by reading.
+    #   {40,}           — consumes the whole run, so anything longer than an
+    #                     allowlisted literal is a distinct value and fails.
+    @{ name = 'urn:btih:<40+hex>';           rx = 'urn:btih:[a-fA-F0-9]{40,}' },
+    # BitTorrent v1 infohashes are 40 hex OR 32 base32 (BEP 9); v2 uses a
+    # different URN entirely (`urn:btmh:`, BEP 52). An earlier commit message
+    # claimed "64-hex btih v2" — that form does not exist. Cover all three.
+    @{ name = 'urn:btih:<32+base32>';        rx = 'urn:btih:[A-Z2-7]{32,}' },
+    @{ name = 'urn:btmh: (BitTorrent v2)';   rx = 'urn:bt' + 'mh:[a-fA-F0-9]{10,}' },
+    # `{16,}` rather than `+`: redact_magnet()'s output is a fixed 8 hex chars,
+    # so `+` made this pattern flag the project's own CORRECTLY REDACTED form.
+    # Real v1 infohashes are 40 hex (or 32 base32); 16 is a safe floor that
+    # passes the 8-char redacted form and catches every real length.
+    @{ name = 'magnet:?xt=';                 rx = 'magnet:\?xt=urn:bt' + '[im]h:[a-zA-Z0-9]{16,}' },
+    # Length floors and separator grammar now follow what PRODUCTION accepts,
+    # not what a "realistic" secret looks like. secret_store.rs takes 1-255
+    # ASCII alphanumerics; legacy_import.rs trims whitespace around `=` and
+    # strips surrounding quotes; parse_cookie_string trims each `k = v` pair.
+    # A scanner narrower than the parser is a scanner with a documented hole,
+    # so `\s*`, optional quotes and a floor of 1 are all deliberate. The cost
+    # is that short test fixtures now match — they are listed in
+    # $AllowedLiterals, which is exactly the reviewable-diff tradeoff this
+    # design already makes everywhere else.
+    @{ name = 'Cloudflare clearance cookie'; rx = 'cf' + '_clearance\s*=\s*["'']?' + '[A-Za-z0-9_.~+/=-]{1,}' },
+    @{ name = 'Cloudflare bot cookie';       rx = '__cf' + '_bm\s*=\s*["'']?' + '[A-Za-z0-9_.~+/=-]{1,}' },
+    @{ name = 'JavDB session cookie';        rx = '_jdb' + '_session\s*=\s*["'']?' + '[A-Za-z0-9_.~+/=-]{1,}' },
+    @{ name = 'remember_me_token=';          rx = 'remember_me_token\s*=\s*["'']?' + '[A-Za-z0-9_.~+/=-]{1,}' },
+    # token68 (RFC 7235) allows -._~+/ and trailing '='; the old [A-Za-z0-9_-]
+    # stopped at the first '.' and reported a truncated match.
+    @{ name = 'Authorization bearer header'; rx = 'Authorization:\s*' + 'Bearer\s+' + '[A-Za-z0-9_.~+/=-]{8,}' },
+    @{ name = 'Bearer <token>';              rx = 'Bearer\s+' + '[A-Za-z0-9_.~+/=-]{16,}' },
+    @{ name = 'RD_API_TOKEN=<value>';        rx = 'RD_API' + '_TOKEN\s*=\s*["'']?' + '[A-Za-z0-9_-]{1,}' }
+)
+
+# All regex evaluation in this script goes through these options. See the
+# comment above $Patterns for why IgnoreCase is not optional here.
+$RxOpts = [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
+
+$ScanFail = $false
+$BinaryHitCount = 0
+# We decode the binary bytes both as ASCII *and* UTF-16LE because PE
+# images routinely embed strings in both encodings:
+#   - ASCII / UTF-8 covers Rust &str literals, format!() output, and
+#     anything wired through libc-style APIs.
+#   - UTF-16LE covers strings handed to the Win32 wide API (e.g. a
+#     `let path = format!("HKCU\\...\\{}", token);` later passed to
+#     `RegOpenKeyExW`), which would otherwise sail past an ASCII-only
+#     scan even though the secret material is plainly readable in a
+#     hex dump.
+# Running both passes is cheap (two regex sweeps over the same byte
+# blob); failing to do it would silently halve the scan's coverage.
+$Encodings = @(
+    @{ label = 'ASCII';      encoding = [System.Text.Encoding]::ASCII },
+    @{ label = 'UTF-16LE';   encoding = [System.Text.Encoding]::Unicode }
+)
+
+function Invoke-SourceSecretScan {
+
+    # ---------------------------------------------------------------------------
+    # Step 7: Source secret scan — over EVERY tracked file
+    #
+    # This used to derive its file list from `git diff <origin/HEAD>..HEAD` plus
+    # the working-tree diff. That made coverage depend on where HEAD happened to
+    # sit: cutting a release from an already-pushed master left both diffs empty,
+    # so the scan walked ZERO files and still wrote `source_secret_hits: 0` into
+    # the manifest — a vacuous pass that read exactly like a real one. It was
+    # found the hard way: a magnet literal sat in verify-windows-build.ps1 from
+    # the commit that introduced it and was never once scanned, until an
+    # unrelated edit to that file finally pulled it into the diff.
+    #
+    # The file list now comes from `git ls-files`, so coverage is a property of
+    # the repo rather than of the branch topology. Content is read from disk, so
+    # uncommitted edits to tracked files are scanned as they actually are.
+    # Untracked files are deliberately out of scope: they are neither committed
+    # nor shipped inside the portable zip.
+    # ---------------------------------------------------------------------------
+    Step "Source secret scan (all tracked text files)"
+    # -z + NUL split: without it git quotes paths containing non-ASCII or control
+    # characters ("\303\251.md"), and the quoted name matches nothing on disk — the
+    # file is then silently dropped from the scan.
+    # Windows PowerShell 5.1 decodes native-command output using the console code
+    # page, not UTF-8. A tracked filename with non-ASCII characters would come back
+    # mangled, Test-Path would then fail to resolve it, and the entry would vanish
+    # from the scan. Force UTF-8 for the duration of the git call.
+    $prevOutEnc = [Console]::OutputEncoding
+    try {
+        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
+        $lsRaw = & git -C $RepoRoot ls-files -z
+        $lsExit = $LASTEXITCODE
+    } finally {
+        [Console]::OutputEncoding = $prevOutEnc
+    }
+    if ($lsExit -ne 0) {
+        Write-Error "FATAL: source-secret-scan git ls-files failed (exit $lsExit). Refusing to ship a release without a source scan."
+        exit 1
+    }
+    $sourceFiles = @(($lsRaw -join "") -split "`0" | Where-Object { $_ } | Sort-Object -Unique)
+    $skipExt = @('.exe', '.msi', '.zip', '.7z', '.png', '.ico', '.icns', '.dll')
+
+    # Known-synthetic literals, allowlisted BY EXACT VALUE rather than by file.
+    #
+    # The previous design skipped whole files (commands.rs, legacy_import.rs,
+    # tests/, *.test.ts, four prose docs, and this script). That exempted ~23 text
+    # files INCLUDING production Rust and the gate itself: any real token later
+    # pasted into them would never have been seen. "Every tracked file" was not
+    # true.
+    #
+    # Now nothing is exempt. Every tracked text file is scanned, and a match only
+    # passes if its exact text appears below. Each entry is a fixture whose
+    # synthetic nature is self-evident (DEADBEEF / repeated nibbles / sequential
+    # counters / obvious placeholder session names), except the one PoC hash in the
+    # security-audit archive, which demonstrates a dedupe-key collision where the
+    # point is that the SAME arbitrary string appears twice.
+    #
+    # Adding an entry here is a visible, reviewable diff line — unlike adding a
+    # file to a skip list, which blinds the scanner to everything in that file
+    # forever. A NEW fixture will fail the build until it is listed; that is the
+    # intended cost.
+    $AllowedLiterals = @(
+        'urn:btih:0201592fDEADBEEF0201592fDEADBEEF02015920',
+        'urn:btih:0201592fdeadbeef0201592fdeadbeef02015920',
+        'urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF',
+        'urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEF',
+        'urn:btih:0201592f00000000000000000000000000000001',
+        'urn:btih:0201592f00000000000000000000000000000002',
+        'urn:btih:0000000000000000000000000000000000000001',
+        'urn:btih:0000000000000000000000000000000000000002',
+        'urn:btih:0000000000000000000000000000000000000003',
+        'urn:btih:0123456789abcdef0123456789abcdef01234567',
+        'urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
+        'urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
+        'urn:btih:cccccccccccccccccccccccccccccccccccccccc',
+        'urn:btih:ABCDEF0123456789ABCDEF0123456789ABCDEF01',
+        'urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
+        'urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
+        'urn:btih:cccccccccccccccccccccccccccccccc',
+        # Dedupe-key collision PoC (prompt/security-audit-fixes-2026-07-28.md).
+        'urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a',
+        'magnet:?xt=urn:btih:0201592fDEADBEEF0201592fDEADBEEF02015920',
+        'magnet:?xt=urn:btih:0201592fdeadbeef0201592fdeadbeef02015920',
+        'magnet:?xt=urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF',
+        'magnet:?xt=urn:btih:0201592f00000000000000000000000000000001',
+        'magnet:?xt=urn:btih:0201592f00000000000000000000000000000002',
+        'magnet:?xt=urn:btih:0000000000000000000000000000000000000001',
+        'magnet:?xt=urn:btih:0000000000000000000000000000000000000002',
+        'magnet:?xt=urn:btih:0000000000000000000000000000000000000003',
+        'magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567',
+        'magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
+        'magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
+        'magnet:?xt=urn:btih:cccccccccccccccccccccccccccccccccccccccc',
+        'magnet:?xt=urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a',
+        'magnet:?xt=urn:btih:0123456789abcdef',
+        'magnet:?xt=urn:btih:ABCDEF0123456789',
+        'MAGNET:?xt=urn:btih:ABCDEF0123456789',
+        'MAGNET:?xt=urn:btih:ABCDEF0123456789ABCDEF0123456789ABCDEF01',
+        'magnet:?xt=urn:btih:fedcba9876543210',
+        # Cookie / token fixtures. These only started matching once the patterns
+    # were widened to production's grammar (floor of 1 char, optional quotes
+    # and whitespace around `=`). Every value here is self-evidently a
+    # placeholder — XXX, `...`, brand_new, clear_me — and lives in a test or
+    # in documentation showing the cookie format.
+    'RD_API_TOKEN=abc-123',
+    '_jdb_session=...',
+    '_jdb_session=XXX',
+    '_jdb_session=abc',
+    '_jdb_session=abc123',
+    '_jdb_session=brand_new',
+    '_jdb_session=clear_me',
+    '_jdb_session=e2e_jdb_session',
+    '_jdb_session=keep_me_alive',
+    '_jdb_session=keyring_only',
+    '_jdb_session=label_test',
+    '_jdb_session=new',
+    '_jdb_session=older_keyring_value',
+    '_jdb_session=paste_session',
+    '_jdb_session=preexisting_session',
+    '_jdb_session=regress_session',
+    '_jdb_session=resurrect_me',
+    '_jdb_session=xyz',
+    'cf_clearance=...',
+    'cf_clearance=XXX',
+    'cf_clearance=brand_new',
+    'cf_clearance=clear_cf',
+    'cf_clearance=e2e_cf_clearance',
+    'cf_clearance=fresh',
+    'cf_clearance=label_test_cf',
+    'cf_clearance=paste_cf',
+    'cf_clearance=preexisting_cf',
+    'cf_clearance=regress_cf',
+    'cf_clearance=resurrect_cf',
+    'cf_clearance=xyz',
+    'cf_clearance=xyz789',
+    # Placeholder cookie values in the Rust cookie-store tests.
+        '_jdb_session=paste_session',
+        '_jdb_session=keep_me_alive',
+        '_jdb_session=e2e_jdb_session',
+        '_jdb_session=regress_session',
+        '_jdb_session=preexisting_session',
+        '_jdb_session=label_test',
+        '_jdb_session=older_keyring_value',
+        '_jdb_session=keyring_only',
+        '_jdb_session=resurrect_me'
+    )
+
+    $SourceHits    = @()
+    $SourceEligible = 0   # tracked, non-binary, i.e. in scope
+    $SourceScanned  = 0   # actually read and regexed
+    $SourceAllowed  = 0   # matched but present in $AllowedLiterals
+    foreach ($rel in $sourceFiles) {
+        $full = Join-Path $RepoRoot $rel
+        if ($skipExt -contains ([System.IO.Path]::GetExtension($rel).ToLowerInvariant())) { continue }
+        $SourceEligible++
+        # -LiteralPath: a tracked file called `notes[1].md` is a valid wildcard to
+        # Test-Path, which would report it missing.
+        #
+        # Fail CLOSED here, and count the entry as eligible BEFORE testing it. The
+        # earlier version skipped unresolvable paths before incrementing, so the
+        # eligible-equals-scanned invariant could never detect them — the exact
+        # blind spot that invariant was added to close. The working tree is
+        # verified clean at Step 0, so every index entry must exist on disk; one
+        # that does not means the path came back mangled (encoding) or something
+        # changed underneath the build.
+        if (-not (Test-Path -LiteralPath $full -PathType Leaf)) {
+            FailExit ("Source secret scan could not resolve tracked path: " + $rel + " — refusing to ship a partial scan.")
+        }
+        # Fail CLOSED on read errors. The old code used -ErrorAction SilentlyContinue
+        # and `continue`d on $null, so an unreadable file vanished from the scan
+        # while the run still reported success — a file the scanner could not read
+        # is exactly the file worth worrying about.
+        # Read BYTES, not text. Get-Content -Raw picks an encoding for you, and the
+        # default differs between Windows PowerShell 5.1 and PowerShell 7: a
+        # BOM-less UTF-16LE file decodes into ASCII interleaved with NULs, so a
+        # perfectly readable secret matches nothing while I/O "succeeds" and
+        # eligible still equals scanned.
+        try {
+            $bytes = [System.IO.File]::ReadAllBytes($full)
+        } catch {
+            FailExit ("Source secret scan could not read " + $rel + ": " + $_.Exception.Message)
+        }
+        $SourceScanned++
+        # Same two-encoding sweep the binary scan does, plus a percent-decoded pass
+        # of each: production normalises `magnet:?xt=urn%3Abtih%3A<hash>` back to
+        # `btih:<hash>` (verified via _magnet_dedupe_key) and interns it, so a scan
+        # that only sees the raw bytes misses an escaped magnet entirely.
+        $variants = New-Object System.Collections.Generic.List[string]
+        foreach ($enc in $Encodings) {
+            $decoded = $enc.encoding.GetString($bytes)
+            $variants.Add($decoded)
+            try { $variants.Add([System.Uri]::UnescapeDataString($decoded)) } catch { }
+        }
+        foreach ($text in $variants) {
+            foreach ($p in $Patterns) {
+                foreach ($m in [regex]::Matches($text, $p.rx, $RxOpts)) {
+                    if ($AllowedLiterals -ccontains $m.Value) { $SourceAllowed++; continue }
+                    $SourceHits += ("      " + $rel + "  [" + $p.name + "]")
+                }
+            }
+        }
+    }
+    if ($SourceHits.Count -gt 0) {
+        Write-Host "    Source secret scan LEAK:" -ForegroundColor Red
+        # File + pattern only, never the matched text (same reasoning as the binary
+        # scan above).
+        $SourceHits | Sort-Object -Unique | ForEach-Object { Write-Host $_ -ForegroundColor Red }
+        Write-Host "    If a hit is a synthetic fixture, add its exact value to `$AllowedLiterals." -ForegroundColor Red
+        FailExit "Source secret scan failed"
+    }
+    # A scan that walked nothing must never report success — that is the exact
+    # failure mode this step was rewritten to eliminate, so assert it explicitly
+    # instead of trusting the file list to be non-empty.
+    if ($SourceScanned -eq 0) {
+        FailExit "Source secret scan walked 0 files — the scan is not covering anything. Check git ls-files and skipExt."
+    }
+    if ($SourceScanned -ne $SourceEligible) {
+        FailExit ("Source secret scan read " + $SourceScanned + " of " + $SourceEligible + " eligible files; refusing to ship a partial scan.")
+    }
+    Ok ("No unexpected source secrets (" + $SourceScanned + " text files scanned, " + $SourceAllowed + " allowlisted fixture matches)")
+}
+
+# --------------------------------------------------------------------------
+# -AuditOnly: run just the scan and exit. The clean-tree gate is skipped on
+# this path ON PURPOSE — red-testing the scanner means planting a secret,
+# which necessarily dirties the tree. Never use this mode to ship.
+# --------------------------------------------------------------------------
+if ($AuditOnly) {
+    Write-Output "== AUDIT ONLY: source secret scan, no build =="
+    Invoke-SourceSecretScan
+    Write-Output "[PASS] audit-only scan clean"
+    exit 0
+}
+
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
-$treeStatus = & git -C $RepoRoot status --porcelain
+# --untracked-files=all explicitly: `status.showUntrackedFiles=no` in any
+# config layer would otherwise hide untracked files entirely, and untracked
+# top-level modules CAN be pulled into sidecar.exe by PyInstaller.
+$treeStatus = & git -C $RepoRoot status --porcelain --untracked-files=all
 if ($LASTEXITCODE -ne 0) { FailExit "git status failed (exit $LASTEXITCODE); refusing to build" }
+# assume-unchanged (h) and skip-worktree (S) make git report a clean tree while
+# the file on disk differs from the index — the build would compile content
+# that neither git status nor the source scan ever sees.
+$maskedEntries = & git -C $RepoRoot ls-files -v
+if ($LASTEXITCODE -ne 0) { FailExit "git ls-files -v failed; refusing to build" }
+$masked = @($maskedEntries | Where-Object { $_ -cmatch '^[a-z]' -or $_ -cmatch '^S ' })
+if ($masked.Count -gt 0) {
+    $masked | ForEach-Object { Write-Output ("      " + $_) }
+    FailExit "Tracked files are marked assume-unchanged/skip-worktree; git cannot vouch for their contents. Clear with: git update-index --no-assume-unchanged --no-skip-worktree <path>"
+}
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
@@ -256,270 +583,59 @@ if ($StagingViolations.Count -gt 0) {
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
-
-$Patterns = @(
-    # Every pattern below is matched case-INSENSITIVELY (see $RxOpts). URI
-    # schemes are case-insensitive per RFC 3986, and this project's own parser
-    # agrees: sidecar.py lower-cases before its `startswith("magnet:")` check
-    # and _REDACT_MAGNET_RX carries re.IGNORECASE. A case-sensitive scan would
-    # therefore miss `MAGNET:?XT=URN:BTIH:...` — a string production happily
-    # accepts and interns. Verified: register_magnets returns ok for the
-    # upper-case form while the old pattern did not match it at all.
-    @{ name = 'urn:btih:<40hex>';            rx = 'urn:btih:[a-fA-F0-9]{40}' },
-    # BitTorrent v1 infohashes are 40 hex OR 32 base32 (BEP 9); v2 uses a
-    # different URN entirely (`urn:btmh:`, BEP 52). An earlier commit message
-    # claimed "64-hex btih v2" — that form does not exist. Cover all three.
-    @{ name = 'urn:btih:<32base32>';         rx = 'urn:btih:[A-Z2-7]{32}' },
-    @{ name = 'urn:btmh: (BitTorrent v2)';   rx = 'urn:bt' + 'mh:[a-fA-F0-9]{10,}' },
-    # `{16,}` rather than `+`: redact_magnet()'s output is a fixed 8 hex chars,
-    # so `+` made this pattern flag the project's own CORRECTLY REDACTED form.
-    # Real v1 infohashes are 40 hex (or 32 base32); 16 is a safe floor that
-    # passes the 8-char redacted form and catches every real length.
-    @{ name = 'magnet:?xt=';                 rx = 'magnet:\?xt=urn:bt' + '[im]h:[a-zA-Z0-9]{16,}' },
-    @{ name = 'Cloudflare clearance cookie'; rx = 'cf' + '_clearance=' + '[A-Za-z0-9_.-]{20,}' },
-    @{ name = 'Cloudflare bot cookie';       rx = '__cf' + '_bm=' + '[A-Za-z0-9_.-]{20,}' },
-    @{ name = 'JavDB session cookie';        rx = '_jdb' + '_session=' + '[A-Za-z0-9_.-]{10,}' },
-    @{ name = 'remember_me_token=';          rx = 'remember_me_token=[A-Za-z0-9_.-]{10,}' },
-    @{ name = 'Authorization bearer header'; rx = 'Authorization:\s*' + 'Bearer\s+' + '[A-Za-z0-9_-]{20,}' },
-    @{ name = 'Bearer <30+ char token>';     rx = 'Bearer ' + '[A-Za-z0-9_-]{30,}' },
-    @{ name = 'RD_API_TOKEN=<value>';        rx = 'RD_API' + '_TOKEN=' + '[A-Za-z0-9_-]{20,}' }
-)
-
-# All regex evaluation in this script goes through these options. See the
-# comment above $Patterns for why IgnoreCase is not optional here.
-$RxOpts = [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
-
-$ScanFail = $false
-$BinaryHitCount = 0
-# We decode the binary bytes both as ASCII *and* UTF-16LE because PE
-# images routinely embed strings in both encodings:
-#   - ASCII / UTF-8 covers Rust &str literals, format!() output, and
-#     anything wired through libc-style APIs.
-#   - UTF-16LE covers strings handed to the Win32 wide API (e.g. a
-#     `let path = format!("HKCU\\...\\{}", token);` later passed to
-#     `RegOpenKeyExW`), which would otherwise sail past an ASCII-only
-#     scan even though the secret material is plainly readable in a
-#     hex dump.
-# Running both passes is cheap (two regex sweeps over the same byte
-# blob); failing to do it would silently halve the scan's coverage.
-$Encodings = @(
-    @{ label = 'ASCII';      encoding = [System.Text.Encoding]::ASCII },
-    @{ label = 'UTF-16LE';   encoding = [System.Text.Encoding]::Unicode }
-)
 foreach ($exe in $ScanTargets) {
     $name = Split-Path $exe -Leaf
     $bytes = [System.IO.File]::ReadAllBytes($exe)
     $hits = @()
     foreach ($enc in $Encodings) {
-        $text = $enc.encoding.GetString($bytes)
+        $decoded = $enc.encoding.GetString($bytes)
+        # Percent-decoded pass for the same reason as the source scan: an
+        # escaped magnet is still a magnet by the time production sees it.
+        $texts = @($decoded)
+        try { $texts += [System.Uri]::UnescapeDataString($decoded) } catch { }
+        foreach ($text in $texts) {
         foreach ($p in $Patterns) {
             $regexMatches = [regex]::Matches($text, $p.rx, $RxOpts)
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
+        }
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
-
-# ---------------------------------------------------------------------------
-# Step 7: Source secret scan — over EVERY tracked file
-#
-# This used to derive its file list from `git diff <origin/HEAD>..HEAD` plus
-# the working-tree diff. That made coverage depend on where HEAD happened to
-# sit: cutting a release from an already-pushed master left both diffs empty,
-# so the scan walked ZERO files and still wrote `source_secret_hits: 0` into
-# the manifest — a vacuous pass that read exactly like a real one. It was
-# found the hard way: a magnet literal sat in verify-windows-build.ps1 from
-# the commit that introduced it and was never once scanned, until an
-# unrelated edit to that file finally pulled it into the diff.
-#
-# The file list now comes from `git ls-files`, so coverage is a property of
-# the repo rather than of the branch topology. Content is read from disk, so
-# uncommitted edits to tracked files are scanned as they actually are.
-# Untracked files are deliberately out of scope: they are neither committed
-# nor shipped inside the portable zip.
-# ---------------------------------------------------------------------------
-Step "Source secret scan (all tracked text files)"
-# -z + NUL split: without it git quotes paths containing non-ASCII or control
-# characters ("\303\251.md"), and the quoted name matches nothing on disk — the
-# file is then silently dropped from the scan.
-# Windows PowerShell 5.1 decodes native-command output using the console code
-# page, not UTF-8. A tracked filename with non-ASCII characters would come back
-# mangled, Test-Path would then fail to resolve it, and the entry would vanish
-# from the scan. Force UTF-8 for the duration of the git call.
-$prevOutEnc = [Console]::OutputEncoding
-try {
-    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
-    $lsRaw = & git -C $RepoRoot ls-files -z
-    $lsExit = $LASTEXITCODE
-} finally {
-    [Console]::OutputEncoding = $prevOutEnc
-}
-if ($lsExit -ne 0) {
-    Write-Error "FATAL: source-secret-scan git ls-files failed (exit $lsExit). Refusing to ship a release without a source scan."
-    exit 1
-}
-$sourceFiles = @(($lsRaw -join "") -split "`0" | Where-Object { $_ } | Sort-Object -Unique)
-$skipExt = @('.exe', '.msi', '.zip', '.7z', '.png', '.ico', '.icns', '.dll')
-
-# Known-synthetic literals, allowlisted BY EXACT VALUE rather than by file.
-#
-# The previous design skipped whole files (commands.rs, legacy_import.rs,
-# tests/, *.test.ts, four prose docs, and this script). That exempted ~23 text
-# files INCLUDING production Rust and the gate itself: any real token later
-# pasted into them would never have been seen. "Every tracked file" was not
-# true.
-#
-# Now nothing is exempt. Every tracked text file is scanned, and a match only
-# passes if its exact text appears below. Each entry is a fixture whose
-# synthetic nature is self-evident (DEADBEEF / repeated nibbles / sequential
-# counters / obvious placeholder session names), except the one PoC hash in the
-# security-audit archive, which demonstrates a dedupe-key collision where the
-# point is that the SAME arbitrary string appears twice.
-#
-# Adding an entry here is a visible, reviewable diff line — unlike adding a
-# file to a skip list, which blinds the scanner to everything in that file
-# forever. A NEW fixture will fail the build until it is listed; that is the
-# intended cost.
-$AllowedLiterals = @(
-    'urn:btih:0201592fDEADBEEF0201592fDEADBEEF02015920',
-    'urn:btih:0201592fdeadbeef0201592fdeadbeef02015920',
-    'urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF',
-    'urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEF',
-    'urn:btih:0201592f00000000000000000000000000000001',
-    'urn:btih:0201592f00000000000000000000000000000002',
-    'urn:btih:0000000000000000000000000000000000000001',
-    'urn:btih:0000000000000000000000000000000000000002',
-    'urn:btih:0000000000000000000000000000000000000003',
-    'urn:btih:0123456789abcdef0123456789abcdef01234567',
-    'urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
-    'urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
-    'urn:btih:cccccccccccccccccccccccccccccccccccccccc',
-    'urn:btih:ABCDEF0123456789ABCDEF0123456789ABCDEF01',
-    'urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
-    'urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
-    'urn:btih:cccccccccccccccccccccccccccccccc',
-    # Dedupe-key collision PoC (prompt/security-audit-fixes-2026-07-28.md).
-    'urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a',
-    'magnet:?xt=urn:btih:0201592fDEADBEEF0201592fDEADBEEF02015920',
-    'magnet:?xt=urn:btih:0201592fdeadbeef0201592fdeadbeef02015920',
-    'magnet:?xt=urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF',
-    'magnet:?xt=urn:btih:0201592f00000000000000000000000000000001',
-    'magnet:?xt=urn:btih:0201592f00000000000000000000000000000002',
-    'magnet:?xt=urn:btih:0000000000000000000000000000000000000001',
-    'magnet:?xt=urn:btih:0000000000000000000000000000000000000002',
-    'magnet:?xt=urn:btih:0000000000000000000000000000000000000003',
-    'magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567',
-    'magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
-    'magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
-    'magnet:?xt=urn:btih:cccccccccccccccccccccccccccccccccccccccc',
-    'magnet:?xt=urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a',
-    'magnet:?xt=urn:btih:0123456789abcdef',
-    'magnet:?xt=urn:btih:ABCDEF0123456789',
-    'MAGNET:?xt=urn:btih:ABCDEF0123456789',
-    'MAGNET:?xt=urn:btih:ABCDEF0123456789ABCDEF0123456789ABCDEF01',
-    'magnet:?xt=urn:btih:fedcba9876543210',
-    # Placeholder cookie values in the Rust cookie-store tests.
-    '_jdb_session=paste_session',
-    '_jdb_session=keep_me_alive',
-    '_jdb_session=e2e_jdb_session',
-    '_jdb_session=regress_session',
-    '_jdb_session=preexisting_session',
-    '_jdb_session=label_test',
-    '_jdb_session=older_keyring_value',
-    '_jdb_session=keyring_only',
-    '_jdb_session=resurrect_me'
-)
-
-$SourceHits    = @()
-$SourceEligible = 0   # tracked, non-binary, i.e. in scope
-$SourceScanned  = 0   # actually read and regexed
-$SourceAllowed  = 0   # matched but present in $AllowedLiterals
-foreach ($rel in $sourceFiles) {
-    $full = Join-Path $RepoRoot $rel
-    if ($skipExt -contains ([System.IO.Path]::GetExtension($rel).ToLowerInvariant())) { continue }
-    $SourceEligible++
-    # -LiteralPath: a tracked file called `notes[1].md` is a valid wildcard to
-    # Test-Path, which would report it missing.
-    #
-    # Fail CLOSED here, and count the entry as eligible BEFORE testing it. The
-    # earlier version skipped unresolvable paths before incrementing, so the
-    # eligible-equals-scanned invariant could never detect them — the exact
-    # blind spot that invariant was added to close. The working tree is
-    # verified clean at Step 0, so every index entry must exist on disk; one
-    # that does not means the path came back mangled (encoding) or something
-    # changed underneath the build.
-    if (-not (Test-Path -LiteralPath $full -PathType Leaf)) {
-        FailExit ("Source secret scan could not resolve tracked path: " + $rel + " — refusing to ship a partial scan.")
-    }
-    # Fail CLOSED on read errors. The old code used -ErrorAction SilentlyContinue
-    # and `continue`d on $null, so an unreadable file vanished from the scan
-    # while the run still reported success — a file the scanner could not read
-    # is exactly the file worth worrying about.
-    try {
-        $text = Get-Content -LiteralPath $full -Raw -ErrorAction Stop
-    } catch {
-        FailExit ("Source secret scan could not read " + $rel + ": " + $_.Exception.Message)
-    }
-    if ($null -eq $text) { $text = "" }   # legitimately empty file
-    $SourceScanned++
-    foreach ($p in $Patterns) {
-        foreach ($m in [regex]::Matches($text, $p.rx, $RxOpts)) {
-            if ($AllowedLiterals -ccontains $m.Value) { $SourceAllowed++; continue }
-            $SourceHits += ("      " + $rel + "  [" + $p.name + "]")
-        }
-    }
-}
-if ($SourceHits.Count -gt 0) {
-    Write-Host "    Source secret scan LEAK:" -ForegroundColor Red
-    # File + pattern only, never the matched text (same reasoning as the binary
-    # scan above).
-    $SourceHits | Sort-Object -Unique | ForEach-Object { Write-Host $_ -ForegroundColor Red }
-    Write-Host "    If a hit is a synthetic fixture, add its exact value to `$AllowedLiterals." -ForegroundColor Red
-    FailExit "Source secret scan failed"
-}
-# A scan that walked nothing must never report success — that is the exact
-# failure mode this step was rewritten to eliminate, so assert it explicitly
-# instead of trusting the file list to be non-empty.
-if ($SourceScanned -eq 0) {
-    FailExit "Source secret scan walked 0 files — the scan is not covering anything. Check git ls-files and skipExt."
-}
-if ($SourceScanned -ne $SourceEligible) {
-    FailExit ("Source secret scan read " + $SourceScanned + " of " + $SourceEligible + " eligible files; refusing to ship a partial scan.")
-}
-Ok ("No unexpected source secrets (" + $SourceScanned + " text files scanned, " + $SourceAllowed + " allowlisted fixture matches)")
+Invoke-SourceSecretScan
 
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
 
@@ -550,30 +666,31 @@ $sumsLines = $HashTargets | ForEach-Object {
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
+$ManifestPath = Join-Path $ReleaseOutDir "release-manifest.json"
 $gitCommit = (& git -C $RepoRoot rev-parse HEAD).Trim()
 if ($LASTEXITCODE -ne 0) { FailExit "git rev-parse HEAD failed after build" }
 if ($gitCommit -ne $BuildStartHead) {
     FailExit ("HEAD moved during the build (" + $BuildStartHead + " -> " + $gitCommit + "); the artifacts do not match either commit.")
 }
-$treeStatusAfter = & git -C $RepoRoot status --porcelain
+$treeStatusAfter = & git -C $RepoRoot status --porcelain --untracked-files=all
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
@@ -590,30 +707,33 @@ $manifest = [ordered]@{
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
-        # Asserted BEFORE the build and re-verified AFTER it (HEAD unchanged
-        # and porcelain still empty), so git_commit really does identify the
-        # source that was compiled and scanned — not merely what HEAD was when
-        # the run started.
+        # Checked before the build and re-checked after it. This does NOT prove
+        # the compiler observed exactly this snapshot: an edit made and reverted
+        # mid-build leaves both checks clean while an artifact was produced from
+        # transient source. The field is named for what is actually verified.
+        # Proving the stronger property requires building from an immutable
+        # checkout (git archive / a throwaway worktree), which this pipeline
+        # does not yet do.
         working_tree_clean       = $true
-        source_snapshot_verified = "before_and_after_build"
+        source_snapshot_verified = "pre_and_post_build_clean"
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
---RELATED CALLERS---
./output/task-p1-1-build-release-dev-branch.md:1:# Task: P1.1 — 修 build-release.ps1 origin/dev → origin/master + git error fatal
./output/task-p1-1-build-release-dev-branch.md:6:- `scripts/build-release.ps1`
./output/task-p1-1-build-release-dev-branch.md:12:`scripts/build-release.ps1` 的「Step 6 source-secret-scan」依賴 `git diff origin/dev..HEAD` 抓 committed diff 掃 token / magnet / cookie 字串。但本 repo default branch 是 `master`，`origin/dev` **不存在**。
./output/task-p1-1-build-release-dev-branch.md:83:- 不要動 RUSTFLAGS / SHA256SUMS / manifest 邏輯
./output/task-p1-1-build-release-dev-branch.md:90:完成後 `scripts/build-release.ps1` 應該：
./output/task-p1-1-build-release-dev-branch.md:97:不需要實際跑 `pwsh ./scripts/build-release.ps1` —— reviewer 後續手動 dry-run 驗。
./output/task-p1-1-build-release-dev-branch.md:101:只動 `scripts/build-release.ps1`、0 commit。
./output/verify-no-dev-branch.py:2:"""Verify scripts/build-release.ps1 no longer references origin/dev."""
./output/verify-no-dev-branch.py:6:target = Path("scripts/build-release.ps1")
./README.md:69:第一次執行可能跳「Windows 已保護你的電腦」藍色警告 —— exe **未做 code signing**（個人專案、無 cert）。先比對 SHA256（每個 release 都附 `SHA256SUMS.txt`），再按：
./README.md:295:`scripts/build-release.ps1` 會：
./README.md:309:8. 算 SHA256（portable.zip / javdbmagnet.exe / sidecar.exe），寫入 `release/SHA256SUMS.txt`
./README.md:310:9. 寫 release manifest 到 `release/release-manifest.json`（`"bundle": "portable-zip"`）
./README.md:363:│  ├─ build-release.ps1   ← 一條命令 release pipeline
./scripts/verify-windows-build.ps1:3:# 這支腳本**不打包**。打包是 scripts\build-release.ps1 的工作，那條 pipeline
./scripts/verify-windows-build.ps1:17:# 先跑這支，全綠再跑 build-release.ps1。
./scripts/verify-windows-build.ps1:207:            # 合成的假 BTIH，不是真資料。字串刻意拆成兩段：build-release.ps1
./scripts/verify-windows-build.ps1:271:    Write-Output "[FAIL] 先修上面的問題，不要進 build-release.ps1"
./scripts/verify-windows-build.ps1:274:Write-Output "[PASS] 全部通過。可以跑： pwsh -File scripts\build-release.ps1"
./implementation-notes.md:62:- 6 個剩餘 finding：全是 `PSAvoidAssignmentToAutomaticVariable`，位於 `.claude/worktrees/{cool-mclaren, festive-mcnulty, recursing-moore}/scripts/build-release.ps1`。現行 `scripts/build-release.ps1` 已修，這幾個是過時的 worktree 副本，沒人清。可忽略。
./implementation-notes.md:139:- **未動 P3 hardening 清單**（SEC-rust-commands-02 / sidecar_manager.rs buffer 上限 / legacy_import.rs warning 內含原始 .env 值 / scraper.ts 前端 host 驗證 / build-release.ps1 secret 掃描範圍 …）：本次只動 P1 + P2，P3 留排期。
./app/package.json:18:    "release": "powershell -ExecutionPolicy Bypass -File ../scripts/build-release.ps1"
./prompt/security-audit-fixes-2026-07-28.md:576:- `scripts/build-release.ps1:311` 原始碼機密掃描比對 `origin/HEAD..HEAD` 導致
./PSScriptAnalyzerSettings.psd1:4:    # point (scripts/build-release.ps1), which intentionally:
./docs/platform/windows-build.md:19:pwsh -File scripts\build-release.ps1
./docs/platform/windows-build.md:63:建置時產生，`build-release.ps1` 的 Step 1 就是它。驗證腳本也會先建。
./docs/platform/linux-support.md:151:- `scripts/build-release.ps1` 是 PowerShell，Linux 無法直接跑。
./docs/security-audit-2026-05-30.md:104:| SEC-build-legacy-03 | `scripts/build-release.ps1` | Step 7 secret 掃描只掃 diff,已 commit 的 secret 會漏(Step 5 仍掃兩個 exe,風險低)→ 改掃 `git ls-files` 或全歷史 |
./docs/superpowers/specs/2026-05-10-tauri-rewrite-design.md:978:.\build-release.ps1
./docs/code-simplification-plan-2026-05-30.md:47:| SIMP-build-release-01 | `build-release.ps1:72-85` | better-stdlib | 手刻 `Get-Sha256Hex` → 內建 `(Get-FileHash -Algorithm SHA256).Hash`(同樣回大寫 hex) | 12 | low |
./docs/code-simplification-plan-2026-05-30.md:48:| SIMP-build-release-02 | `build-release.ps1:224-244` | redundant | 兩個連續 `foreach ($f in $StagedFiles)` 掃同一集合 → 併成一趟(leaf 只算一次) | 5 | low |
./docs/code-simplification-plan-2026-05-30.md:49:| SIMP-build-release-03 | `build-release.ps1:296-307, 371-380` | duplication | 兩處 `[regex]::Matches` per-pattern 迴圈 → 抽 `Scan-Patterns($text,$Patterns)` | 8 | **medium** |
./docs/code-simplification-plan-2026-05-30.md:68:- 多數 effort = trivial/small、risk = low;3 個標 medium 的(SIMP-frontend-04 tie-break、SIMP-py-sidecar-01、SIMP-build-release-03)務必跑測試覆核。
./docs/architecture/contracts/python-legacy.md:7:> - **REMOVED in M9**: `javdb_magnet.py` (standalone CLI, was never imported by anything; deleted in Phase 2). `build.py` (legacy Tk PyInstaller build; replaced by `scripts/build-release.ps1` + `build_sidecar.py`; deleted in Phase 2).
./docs/architecture/contracts/python-legacy.md:704:- **Build pipeline** (was `build.py`): `scripts/build-release.ps1` + `spikes/pyinstaller_sidecar/build_sidecar.py`. The old build script was deleted in M9 Phase 2.
./docs/architecture/function-contracts.md:59:| Release pipeline | `scripts/build-release.ps1` | Self-documenting; sequenced in the README of [`contracts/sidecar.md`](contracts/sidecar.md) |
./docs/architecture/function-contracts.md:72:- `build.py` — legacy Tk PyInstaller build script, replaced by `scripts/build-release.ps1` + `spikes/pyinstaller_sidecar/build_sidecar.py`; deleted in Phase 2

exec
/bin/bash -lc "sed -n '300,440p' scripts/build-release.ps1 | nl -ba -v300; printf '\\n--- PARENT 1-450 ---\\n'; git show 3f55ec0"'^:scripts/build-release.ps1 | sed -n '"'1,450p' | nl -ba; printf '\\n--- POWERSHELL ---\\n'; command -v pwsh || true; pwsh -NoProfile -Command '"'$ErrorActionPreference="Stop"; Set-StrictMode -Version Latest; function f { $x=1 }; f; try { $x } catch { $_.Exception.Message; exit 23 }'"'; echo \"pwsh_status="'$?"' in /home/cy5407/javdb-magnet-workbench
 succeeded in 0ms:
   300	        '_jdb_session=older_keyring_value',
   301	        '_jdb_session=keyring_only',
   302	        '_jdb_session=resurrect_me'
   303	    )
   304	
   305	    $SourceHits    = @()
   306	    $SourceEligible = 0   # tracked, non-binary, i.e. in scope
   307	    $SourceScanned  = 0   # actually read and regexed
   308	    $SourceAllowed  = 0   # matched but present in $AllowedLiterals
   309	    foreach ($rel in $sourceFiles) {
   310	        $full = Join-Path $RepoRoot $rel
   311	        if ($skipExt -contains ([System.IO.Path]::GetExtension($rel).ToLowerInvariant())) { continue }
   312	        $SourceEligible++
   313	        # -LiteralPath: a tracked file called `notes[1].md` is a valid wildcard to
   314	        # Test-Path, which would report it missing.
   315	        #
   316	        # Fail CLOSED here, and count the entry as eligible BEFORE testing it. The
   317	        # earlier version skipped unresolvable paths before incrementing, so the
   318	        # eligible-equals-scanned invariant could never detect them — the exact
   319	        # blind spot that invariant was added to close. The working tree is
   320	        # verified clean at Step 0, so every index entry must exist on disk; one
   321	        # that does not means the path came back mangled (encoding) or something
   322	        # changed underneath the build.
   323	        if (-not (Test-Path -LiteralPath $full -PathType Leaf)) {
   324	            FailExit ("Source secret scan could not resolve tracked path: " + $rel + " — refusing to ship a partial scan.")
   325	        }
   326	        # Fail CLOSED on read errors. The old code used -ErrorAction SilentlyContinue
   327	        # and `continue`d on $null, so an unreadable file vanished from the scan
   328	        # while the run still reported success — a file the scanner could not read
   329	        # is exactly the file worth worrying about.
   330	        # Read BYTES, not text. Get-Content -Raw picks an encoding for you, and the
   331	        # default differs between Windows PowerShell 5.1 and PowerShell 7: a
   332	        # BOM-less UTF-16LE file decodes into ASCII interleaved with NULs, so a
   333	        # perfectly readable secret matches nothing while I/O "succeeds" and
   334	        # eligible still equals scanned.
   335	        try {
   336	            $bytes = [System.IO.File]::ReadAllBytes($full)
   337	        } catch {
   338	            FailExit ("Source secret scan could not read " + $rel + ": " + $_.Exception.Message)
   339	        }
   340	        $SourceScanned++
   341	        # Same two-encoding sweep the binary scan does, plus a percent-decoded pass
   342	        # of each: production normalises `magnet:?xt=urn%3Abtih%3A<hash>` back to
   343	        # `btih:<hash>` (verified via _magnet_dedupe_key) and interns it, so a scan
   344	        # that only sees the raw bytes misses an escaped magnet entirely.
   345	        $variants = New-Object System.Collections.Generic.List[string]
   346	        foreach ($enc in $Encodings) {
   347	            $decoded = $enc.encoding.GetString($bytes)
   348	            $variants.Add($decoded)
   349	            try { $variants.Add([System.Uri]::UnescapeDataString($decoded)) } catch { }
   350	        }
   351	        foreach ($text in $variants) {
   352	            foreach ($p in $Patterns) {
   353	                foreach ($m in [regex]::Matches($text, $p.rx, $RxOpts)) {
   354	                    if ($AllowedLiterals -ccontains $m.Value) { $SourceAllowed++; continue }
   355	                    $SourceHits += ("      " + $rel + "  [" + $p.name + "]")
   356	                }
   357	            }
   358	        }
   359	    }
   360	    if ($SourceHits.Count -gt 0) {
   361	        Write-Host "    Source secret scan LEAK:" -ForegroundColor Red
   362	        # File + pattern only, never the matched text (same reasoning as the binary
   363	        # scan above).
   364	        $SourceHits | Sort-Object -Unique | ForEach-Object { Write-Host $_ -ForegroundColor Red }
   365	        Write-Host "    If a hit is a synthetic fixture, add its exact value to `$AllowedLiterals." -ForegroundColor Red
   366	        FailExit "Source secret scan failed"
   367	    }
   368	    # A scan that walked nothing must never report success — that is the exact
   369	    # failure mode this step was rewritten to eliminate, so assert it explicitly
   370	    # instead of trusting the file list to be non-empty.
   371	    if ($SourceScanned -eq 0) {
   372	        FailExit "Source secret scan walked 0 files — the scan is not covering anything. Check git ls-files and skipExt."
   373	    }
   374	    if ($SourceScanned -ne $SourceEligible) {
   375	        FailExit ("Source secret scan read " + $SourceScanned + " of " + $SourceEligible + " eligible files; refusing to ship a partial scan.")
   376	    }
   377	    Ok ("No unexpected source secrets (" + $SourceScanned + " text files scanned, " + $SourceAllowed + " allowlisted fixture matches)")
   378	}
   379	
   380	# --------------------------------------------------------------------------
   381	# -AuditOnly: run just the scan and exit. The clean-tree gate is skipped on
   382	# this path ON PURPOSE — red-testing the scanner means planting a secret,
   383	# which necessarily dirties the tree. Never use this mode to ship.
   384	# --------------------------------------------------------------------------
   385	if ($AuditOnly) {
   386	    Write-Output "== AUDIT ONLY: source secret scan, no build =="
   387	    Invoke-SourceSecretScan
   388	    Write-Output "[PASS] audit-only scan clean"
   389	    exit 0
   390	}
   391	
   392	Step "Verifying working tree is clean"
   393	# The build reads the WORKING TREE (npm/cargo/PyInstaller all compile what is on
   394	# disk), but the manifest records `git rev-parse HEAD`. With uncommitted edits
   395	# those two describe different code, and the manifest silently vouches for a
   396	# commit that was never what shipped.
   397	#
   398	# Untracked files matter just as much and are easy to miss: `git ls-files` does
   399	# not see them, so the source scan skips them entirely — yet PyInstaller
   400	# resolves the sidecar's dependency graph from the repo root, so an untracked
   401	# top-level module CAN be pulled into sidecar.exe. Scanning "every tracked
   402	# file" is not the same as scanning every build input.
   403	$BuildStartHead = (& git -C $RepoRoot rev-parse HEAD).Trim()
   404	if ($LASTEXITCODE -ne 0) { FailExit "git rev-parse HEAD failed; refusing to build" }
   405	# --untracked-files=all explicitly: `status.showUntrackedFiles=no` in any
   406	# config layer would otherwise hide untracked files entirely, and untracked
   407	# top-level modules CAN be pulled into sidecar.exe by PyInstaller.
   408	$treeStatus = & git -C $RepoRoot status --porcelain --untracked-files=all
   409	if ($LASTEXITCODE -ne 0) { FailExit "git status failed (exit $LASTEXITCODE); refusing to build" }
   410	# assume-unchanged (h) and skip-worktree (S) make git report a clean tree while
   411	# the file on disk differs from the index — the build would compile content
   412	# that neither git status nor the source scan ever sees.
   413	$maskedEntries = & git -C $RepoRoot ls-files -v
   414	if ($LASTEXITCODE -ne 0) { FailExit "git ls-files -v failed; refusing to build" }
   415	$masked = @($maskedEntries | Where-Object { $_ -cmatch '^[a-z]' -or $_ -cmatch '^S ' })
   416	if ($masked.Count -gt 0) {
   417	    $masked | ForEach-Object { Write-Output ("      " + $_) }
   418	    FailExit "Tracked files are marked assume-unchanged/skip-worktree; git cannot vouch for their contents. Clear with: git update-index --no-assume-unchanged --no-skip-worktree <path>"
   419	}
   420	if ($treeStatus) {
   421	    Write-Output "    Working tree is not clean:"
   422	    $treeStatus | ForEach-Object { Write-Output ("      " + $_) }
   423	    FailExit "Refusing to build: commit or stash everything first, so git_commit describes what actually ships."
   424	}
   425	Ok "Working tree clean (tracked + untracked)"
   426	
   427	Step "Preparing release output directory"
   428	if (-not (Test-Path $ReleaseOutDir)) { New-Item -ItemType Directory -Force -Path $ReleaseOutDir | Out-Null }
   429	# Clean previous run's artifacts under release/ (zip, sums, manifest, staging).
   430	# We do NOT touch anything outside release/.
   431	Get-ChildItem -Path $ReleaseOutDir -File -ErrorAction SilentlyContinue |
   432	    Where-Object {
   433	        $_.Extension -in @(".zip", ".msi", ".exe") `
   434	            -or $_.Name -eq "SHA256SUMS.txt" `
   435	            -or $_.Name -eq "release-manifest.json"
   436	    } |
   437	    Remove-Item -Force
   438	if (Test-Path $StagingDir) { Remove-Item $StagingDir -Recurse -Force }
   439	Ok ("Output dir: " + $ReleaseOutDir)
   440	

--- PARENT 1-450 ---
     1	# build-release.ps1 — portable release pipeline
     2	#
     3	# Produces a portable ZIP that ships javdbmagnet.exe + sidecar.exe in a
     4	# single folder. End-users extract the zip and double-click the exe —
     5	# no installer, no Program Files, no Start Menu entry, no registry.
     6	#
     7	# Pipeline:
     8	#   1. Build sidecar.exe         (npm run sidecar:build → app/src-tauri/binaries/...)
     9	#   2. Build frontend + Rust exe (npx tauri build --no-bundle from app/)
    10	#                                 — single CLI call enables the
    11	#                                 `tauri/custom-protocol` feature so the
    12	#                                 release binary embeds dist/ instead of
    13	#                                 reaching for the dev server
    14	#   3. Stage release/JavDBMagnet/ (javdbmagnet.exe + sidecar.exe + README.txt)
    15	#   4. Audit staging dir         (whitelist: exe + exe + README.txt; nothing else)
    16	#   5. Binary content scan       (tokens / magnets / Cloudflare cookies must NOT
    17	#                                 appear in either exe)
    18	#   6. Source secret scan        (same patterns, case-insensitive, over every
    19	#                                 tracked text file; no file-level exemptions —
    20	#                                 known fixtures are allowlisted by exact
    21	#                                 value. Fails closed on unreadable files, on
    22	#                                 an eligible/scanned mismatch, and on 0 files)
    23	#   7. Compress-Archive → release/JavDBMagnet_<version>_portable.zip
    24	#   8. SHA256 for zip + 2 exes  → release/SHA256SUMS.txt
    25	#   9. Write release/release-manifest.json
    26	#  10. Print final paths
    27	#
    28	# Any audit / scan failure → exit 1. Half-baked staging stays for inspection.
    29	#
    30	# Code signing is NOT performed. $env:SIGN -eq "1" emits a placeholder
    31	# warning; wire signtool / osslsigncode here once a cert exists.
    32	#
    33	# Run:
    34	#     pwsh -File scripts\build-release.ps1
    35	# Or from app/:
    36	#     npm run release
    37	
    38	$ErrorActionPreference = "Stop"
    39	Set-StrictMode -Version Latest
    40	
    41	# ---------------------------------------------------------------------------
    42	# Paths
    43	# ---------------------------------------------------------------------------
    44	$ScriptDir     = Split-Path -Parent $MyInvocation.MyCommand.Path
    45	$RepoRoot      = Split-Path -Parent $ScriptDir
    46	$AppDir        = Join-Path $RepoRoot "app"
    47	$TauriSrcDir   = Join-Path $AppDir "src-tauri"
    48	$CargoOutDir   = Join-Path $TauriSrcDir "target\release"
    49	$BinariesDir   = Join-Path $TauriSrcDir "binaries"
    50	$ReleaseOutDir = Join-Path $RepoRoot "release"
    51	
    52	# Sidecar artifact path produced by build_sidecar.py
    53	$SidecarSource = Join-Path $BinariesDir "sidecar-x86_64-pc-windows-msvc.exe"
    54	
    55	# Read version straight from app/package.json so the zip name follows it.
    56	$PkgJsonPath = Join-Path $AppDir "package.json"
    57	$pkgJson = Get-Content $PkgJsonPath -Raw | ConvertFrom-Json
    58	$Version = $pkgJson.version
    59	$PortableFolderName = "JavDBMagnet"
    60	$StagingDir = Join-Path $ReleaseOutDir $PortableFolderName
    61	$ZipName    = "JavDBMagnet_${Version}_portable.zip"
    62	$ZipPath    = Join-Path $ReleaseOutDir $ZipName
    63	
    64	function Step($title) {
    65	    Write-Output ""
    66	    Write-Output "==> $title"
    67	}
    68	function Ok($msg)   { Write-Output "    [OK]   $msg" }
    69	function Warn($msg) { Write-Output "    [WARN] $msg" }
    70	function FailExit($msg) {
    71	    Write-Output ""
    72	    Write-Output "[FAIL] $msg"
    73	    exit 1
    74	}
    75	# ---------------------------------------------------------------------------
    76	# Step 0: Prepare release/ output dir
    77	# ---------------------------------------------------------------------------
    78	Step "Verifying working tree is clean"
    79	# The build reads the WORKING TREE (npm/cargo/PyInstaller all compile what is on
    80	# disk), but the manifest records `git rev-parse HEAD`. With uncommitted edits
    81	# those two describe different code, and the manifest silently vouches for a
    82	# commit that was never what shipped.
    83	#
    84	# Untracked files matter just as much and are easy to miss: `git ls-files` does
    85	# not see them, so the source scan skips them entirely — yet PyInstaller
    86	# resolves the sidecar's dependency graph from the repo root, so an untracked
    87	# top-level module CAN be pulled into sidecar.exe. Scanning "every tracked
    88	# file" is not the same as scanning every build input.
    89	$BuildStartHead = (& git -C $RepoRoot rev-parse HEAD).Trim()
    90	if ($LASTEXITCODE -ne 0) { FailExit "git rev-parse HEAD failed; refusing to build" }
    91	$treeStatus = & git -C $RepoRoot status --porcelain
    92	if ($LASTEXITCODE -ne 0) { FailExit "git status failed (exit $LASTEXITCODE); refusing to build" }
    93	if ($treeStatus) {
    94	    Write-Output "    Working tree is not clean:"
    95	    $treeStatus | ForEach-Object { Write-Output ("      " + $_) }
    96	    FailExit "Refusing to build: commit or stash everything first, so git_commit describes what actually ships."
    97	}
    98	Ok "Working tree clean (tracked + untracked)"
    99	
   100	Step "Preparing release output directory"
   101	if (-not (Test-Path $ReleaseOutDir)) { New-Item -ItemType Directory -Force -Path $ReleaseOutDir | Out-Null }
   102	# Clean previous run's artifacts under release/ (zip, sums, manifest, staging).
   103	# We do NOT touch anything outside release/.
   104	Get-ChildItem -Path $ReleaseOutDir -File -ErrorAction SilentlyContinue |
   105	    Where-Object {
   106	        $_.Extension -in @(".zip", ".msi", ".exe") `
   107	            -or $_.Name -eq "SHA256SUMS.txt" `
   108	            -or $_.Name -eq "release-manifest.json"
   109	    } |
   110	    Remove-Item -Force
   111	if (Test-Path $StagingDir) { Remove-Item $StagingDir -Recurse -Force }
   112	Ok ("Output dir: " + $ReleaseOutDir)
   113	
   114	# ---------------------------------------------------------------------------
   115	# Step 1: Build sidecar.exe via PyInstaller
   116	# ---------------------------------------------------------------------------
   117	Step "Building sidecar.exe (npm run sidecar:build)"
   118	Push-Location $AppDir
   119	try {
   120	    & npm run sidecar:build
   121	    if ($LASTEXITCODE -ne 0) { FailExit "npm run sidecar:build exited with code $LASTEXITCODE" }
   122	} finally {
   123	    Pop-Location
   124	}
   125	if (-not (Test-Path $SidecarSource)) {
   126	    FailExit "sidecar.exe not produced at expected path: $SidecarSource"
   127	}
   128	Ok ("sidecar.exe at " + $SidecarSource)
   129	
   130	# ---------------------------------------------------------------------------
   131	# Step 2 + 3: Build frontend + Rust release exe via Tauri CLI.
   132	#
   133	# Plain `cargo build --release` doesn't pass the `tauri/custom-protocol`
   134	# feature flag, so the resulting binary still tries to load from
   135	# devUrl (http://localhost:1420) instead of the embedded dist/. Going
   136	# through `tauri build --no-bundle` handles three things in one call:
   137	#   - runs beforeBuildCommand (= `npm run build`) for fresh dist/
   138	#   - enables tauri/custom-protocol so the release binary loads from
   139	#     embedded assets
   140	#   - skips MSI / NSIS bundling so no installer artifacts leak in
   141	# ---------------------------------------------------------------------------
   142	Step "Building Rust release binary (npx tauri build --no-bundle)"
   143	# Scrub the build-host user path out of the binary. Rust's `file!()`
   144	# macro and panic strings bake the absolute path of every compiled
   145	# source file into the output, so without remapping the user's
   146	# Windows username + .cargo / project layout would be visible to
   147	# anyone strings(1)-ing the exe. `--remap-path-prefix` rewrites
   148	# those embedded paths at compile time. Three remaps cover the
   149	# usual suspects:
   150	#   - %USERPROFILE%\.cargo  → ~/.cargo            (dependency crates)
   151	#   - %USERPROFILE%\.rustup → ~/.rustup           (stdlib sources)
   152	#   - <repo root>           → <project>           (this project's own files)
   153	# Note: changing RUSTFLAGS invalidates the entire build cache, so
   154	# the first run after toggling this is a full cold compile
   155	# (~3-5 min on a warm dependency tree).
   156	$remapFlags = @(
   157	    "--remap-path-prefix=$($env:USERPROFILE)\.cargo=~/.cargo",
   158	    "--remap-path-prefix=$($env:USERPROFILE)\.rustup=~/.rustup",
   159	    "--remap-path-prefix=$RepoRoot=<project>"
   160	) -join ' '
   161	Ok ("RUSTFLAGS scrub: " + $remapFlags)
   162	$prevRustflags = $env:RUSTFLAGS
   163	$env:RUSTFLAGS = if ($prevRustflags) { "$prevRustflags $remapFlags" } else { $remapFlags }
   164	Push-Location $AppDir
   165	try {
   166	    & npx tauri build --no-bundle
   167	    if ($LASTEXITCODE -ne 0) { FailExit "tauri build exited with code $LASTEXITCODE" }
   168	} finally {
   169	    Pop-Location
   170	    # Restore prior RUSTFLAGS so subsequent processes (other cargo
   171	    # invocations in this shell session) aren't sticky-configured.
   172	    $env:RUSTFLAGS = $prevRustflags
   173	}
   174	$MainExeSource = Join-Path $CargoOutDir "javdbmagnet.exe"
   175	if (-not (Test-Path $MainExeSource)) { FailExit "javdbmagnet.exe missing: $MainExeSource" }
   176	Ok ("javdbmagnet.exe at " + $MainExeSource)
   177	
   178	# ---------------------------------------------------------------------------
   179	# Step 4: Stage portable folder under release/JavDBMagnet/
   180	# ---------------------------------------------------------------------------
   181	Step "Staging portable folder"
   182	New-Item -ItemType Directory -Force -Path $StagingDir | Out-Null
   183	
   184	Copy-Item -LiteralPath $MainExeSource -Destination (Join-Path $StagingDir "javdbmagnet.exe") -Force
   185	# Sidecar is named with target-triple in build/output; rename to plain
   186	# sidecar.exe so users see one clear sibling file.
   187	Copy-Item -LiteralPath $SidecarSource -Destination (Join-Path $StagingDir "sidecar.exe") -Force
   188	
   189	$ReadmeContent = @"
   190	JavDBMagnet $Version — Portable Edition
   191	=======================================
   192	
   193	USAGE
   194	-----
   195	雙擊 javdbmagnet.exe 即可啟動。**請保留 sidecar.exe 在同一個資料夾**，
   196	它是 JavDB / Real-Debrid HTTP sidecar，缺一不可。
   197	
   198	DATA LOCATIONS
   199	--------------
   200	Settings / cookies / pending:  %APPDATA%\JavDBMagnet\
   201	Logs:                          %LOCALAPPDATA%\JavDBMagnet\logs\
   202	RD API token:                  Windows Credential Manager (target: JavDBMagnet/RD_API_TOKEN)
   203	
   204	REMOVAL
   205	-------
   206	- 刪除這個 JavDBMagnet 資料夾即可移除程式本體（不會留 registry 殘渣）
   207	- 想清掉個人資料：
   208	    rmdir /s /q %APPDATA%\JavDBMagnet
   209	    rmdir /s /q %LOCALAPPDATA%\JavDBMagnet
   210	    cmdkey /delete:JavDBMagnet/RD_API_TOKEN
   211	
   212	SMARTSCREEN
   213	-----------
   214	首次啟動可能跳 SmartScreen 警告（未做 code signing）。比對 SHA256 後
   215	按「更多資訊 → 仍要執行」即可。
   216	
   217	詳見 repo 內 README.md / docs/troubleshooting/。
   218	"@
   219	Set-Content -Path (Join-Path $StagingDir "README.txt") -Value $ReadmeContent -Encoding utf8
   220	
   221	$StagedFiles = Get-ChildItem $StagingDir -Recurse -File | Select-Object FullName, Length
   222	Write-Host "    Staged files (" $StagedFiles.Count "):" -ForegroundColor Gray
   223	$StagedFiles | ForEach-Object {
   224	    $rel = $_.FullName.Substring($StagingDir.Length).TrimStart('\','/')
   225	    Write-Host ("      {0,10} bytes  {1}" -f $_.Length, $rel) -ForegroundColor Gray
   226	}
   227	
   228	# ---------------------------------------------------------------------------
   229	# Step 5: Audit staging folder — strict whitelist
   230	# ---------------------------------------------------------------------------
   231	Step "Auditing portable folder (whitelist)"
   232	$AllowedNames = @('javdbmagnet.exe', 'sidecar.exe', 'README.txt')
   233	# Explicitly verify none of the forbidden names slipped in even if the
   234	# whitelist somehow expanded.
   235	$ForbiddenNames = @('.env','.gitignore','cookies.txt','pending_torrents.json','magnet.txt')
   236	$StagingViolations = @()
   237	foreach ($f in $StagedFiles) {
   238	    $rel = $f.FullName.Substring($StagingDir.Length).TrimStart('\','/')
   239	    $leaf = Split-Path $f.FullName -Leaf
   240	    # No subdirectories allowed.
   241	    if ($rel -match '[\\/]') {
   242	        $StagingViolations += "subdir entry: $rel"
   243	        continue
   244	    }
   245	    if ($AllowedNames -notcontains $leaf) {
   246	        $StagingViolations += "unexpected file: $rel"
   247	    }
   248	    if ($ForbiddenNames -contains $leaf) { $StagingViolations += "forbidden: $leaf" }
   249	    if ($leaf -like '.env.*' -or $leaf -like '*.log' -or $leaf -like '*.token' -or $leaf -like '*.spec') {
   250	        $StagingViolations += "forbidden pattern: $leaf"
   251	    }
   252	}
   253	if ($StagingViolations.Count -gt 0) {
   254	    Write-Host "    Staging violations:" -ForegroundColor Red
   255	    $StagingViolations | ForEach-Object { Write-Host ("      " + $_) -ForegroundColor Red }
   256	    FailExit "Portable folder audit failed"
   257	}
   258	Ok "Portable folder contains only allowed artifacts"
   259	
   260	# ---------------------------------------------------------------------------
   261	# Step 6: Binary content scan — secrets must NOT be baked in
   262	# ---------------------------------------------------------------------------
   263	Step "Binary content scan for embedded secrets"
   264	$ScanTargets = @(
   265	    (Join-Path $StagingDir "javdbmagnet.exe"),
   266	    (Join-Path $StagingDir "sidecar.exe")
   267	)
   268	
   269	$Patterns = @(
   270	    # Every pattern below is matched case-INSENSITIVELY (see $RxOpts). URI
   271	    # schemes are case-insensitive per RFC 3986, and this project's own parser
   272	    # agrees: sidecar.py lower-cases before its `startswith("magnet:")` check
   273	    # and _REDACT_MAGNET_RX carries re.IGNORECASE. A case-sensitive scan would
   274	    # therefore miss `MAGNET:?XT=URN:BTIH:...` — a string production happily
   275	    # accepts and interns. Verified: register_magnets returns ok for the
   276	    # upper-case form while the old pattern did not match it at all.
   277	    @{ name = 'urn:btih:<40hex>';            rx = 'urn:btih:[a-fA-F0-9]{40}' },
   278	    # BitTorrent v1 infohashes are 40 hex OR 32 base32 (BEP 9); v2 uses a
   279	    # different URN entirely (`urn:btmh:`, BEP 52). An earlier commit message
   280	    # claimed "64-hex btih v2" — that form does not exist. Cover all three.
   281	    @{ name = 'urn:btih:<32base32>';         rx = 'urn:btih:[A-Z2-7]{32}' },
   282	    @{ name = 'urn:btmh: (BitTorrent v2)';   rx = 'urn:bt' + 'mh:[a-fA-F0-9]{10,}' },
   283	    # `{16,}` rather than `+`: redact_magnet()'s output is a fixed 8 hex chars,
   284	    # so `+` made this pattern flag the project's own CORRECTLY REDACTED form.
   285	    # Real v1 infohashes are 40 hex (or 32 base32); 16 is a safe floor that
   286	    # passes the 8-char redacted form and catches every real length.
   287	    @{ name = 'magnet:?xt=';                 rx = 'magnet:\?xt=urn:bt' + '[im]h:[a-zA-Z0-9]{16,}' },
   288	    @{ name = 'Cloudflare clearance cookie'; rx = 'cf' + '_clearance=' + '[A-Za-z0-9_.-]{20,}' },
   289	    @{ name = 'Cloudflare bot cookie';       rx = '__cf' + '_bm=' + '[A-Za-z0-9_.-]{20,}' },
   290	    @{ name = 'JavDB session cookie';        rx = '_jdb' + '_session=' + '[A-Za-z0-9_.-]{10,}' },
   291	    @{ name = 'remember_me_token=';          rx = 'remember_me_token=[A-Za-z0-9_.-]{10,}' },
   292	    @{ name = 'Authorization bearer header'; rx = 'Authorization:\s*' + 'Bearer\s+' + '[A-Za-z0-9_-]{20,}' },
   293	    @{ name = 'Bearer <30+ char token>';     rx = 'Bearer ' + '[A-Za-z0-9_-]{30,}' },
   294	    @{ name = 'RD_API_TOKEN=<value>';        rx = 'RD_API' + '_TOKEN=' + '[A-Za-z0-9_-]{20,}' }
   295	)
   296	
   297	# All regex evaluation in this script goes through these options. See the
   298	# comment above $Patterns for why IgnoreCase is not optional here.
   299	$RxOpts = [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
   300	
   301	$ScanFail = $false
   302	$BinaryHitCount = 0
   303	# We decode the binary bytes both as ASCII *and* UTF-16LE because PE
   304	# images routinely embed strings in both encodings:
   305	#   - ASCII / UTF-8 covers Rust &str literals, format!() output, and
   306	#     anything wired through libc-style APIs.
   307	#   - UTF-16LE covers strings handed to the Win32 wide API (e.g. a
   308	#     `let path = format!("HKCU\\...\\{}", token);` later passed to
   309	#     `RegOpenKeyExW`), which would otherwise sail past an ASCII-only
   310	#     scan even though the secret material is plainly readable in a
   311	#     hex dump.
   312	# Running both passes is cheap (two regex sweeps over the same byte
   313	# blob); failing to do it would silently halve the scan's coverage.
   314	$Encodings = @(
   315	    @{ label = 'ASCII';      encoding = [System.Text.Encoding]::ASCII },
   316	    @{ label = 'UTF-16LE';   encoding = [System.Text.Encoding]::Unicode }
   317	)
   318	foreach ($exe in $ScanTargets) {
   319	    $name = Split-Path $exe -Leaf
   320	    $bytes = [System.IO.File]::ReadAllBytes($exe)
   321	    $hits = @()
   322	    foreach ($enc in $Encodings) {
   323	        $text = $enc.encoding.GetString($bytes)
   324	        foreach ($p in $Patterns) {
   325	            $regexMatches = [regex]::Matches($text, $p.rx, $RxOpts)
   326	            if ($regexMatches.Count -gt 0) {
   327	                # Artifact + pattern + count ONLY. Never echo the matched value:
   328	                # the whole point of this step is that a secret reached a binary,
   329	                # and printing it would copy that secret into the build log —
   330	                # which, once this runs in CI, is a persistent artifact of its
   331	                # own. Reproduce locally if you need to see the value.
   332	                $hits += "      [$($enc.label)] $($p.name)  count=$($regexMatches.Count)"
   333	                $BinaryHitCount += $regexMatches.Count
   334	            }
   335	        }
   336	    }
   337	    if ($hits.Count -gt 0) {
   338	        Write-Host "    [$name] LEAK:" -ForegroundColor Red
   339	        $hits | ForEach-Object { Write-Host $_ -ForegroundColor Red }
   340	        $ScanFail = $true
   341	    } else {
   342	        Ok ("[$name] no leak patterns (ASCII + UTF-16LE)")
   343	    }
   344	}
   345	if ($ScanFail) { FailExit "Binary content scan failed" }
   346	
   347	# ---------------------------------------------------------------------------
   348	# Step 7: Source secret scan — over EVERY tracked file
   349	#
   350	# This used to derive its file list from `git diff <origin/HEAD>..HEAD` plus
   351	# the working-tree diff. That made coverage depend on where HEAD happened to
   352	# sit: cutting a release from an already-pushed master left both diffs empty,
   353	# so the scan walked ZERO files and still wrote `source_secret_hits: 0` into
   354	# the manifest — a vacuous pass that read exactly like a real one. It was
   355	# found the hard way: a magnet literal sat in verify-windows-build.ps1 from
   356	# the commit that introduced it and was never once scanned, until an
   357	# unrelated edit to that file finally pulled it into the diff.
   358	#
   359	# The file list now comes from `git ls-files`, so coverage is a property of
   360	# the repo rather than of the branch topology. Content is read from disk, so
   361	# uncommitted edits to tracked files are scanned as they actually are.
   362	# Untracked files are deliberately out of scope: they are neither committed
   363	# nor shipped inside the portable zip.
   364	# ---------------------------------------------------------------------------
   365	Step "Source secret scan (all tracked text files)"
   366	# -z + NUL split: without it git quotes paths containing non-ASCII or control
   367	# characters ("\303\251.md"), and the quoted name matches nothing on disk — the
   368	# file is then silently dropped from the scan.
   369	# Windows PowerShell 5.1 decodes native-command output using the console code
   370	# page, not UTF-8. A tracked filename with non-ASCII characters would come back
   371	# mangled, Test-Path would then fail to resolve it, and the entry would vanish
   372	# from the scan. Force UTF-8 for the duration of the git call.
   373	$prevOutEnc = [Console]::OutputEncoding
   374	try {
   375	    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
   376	    $lsRaw = & git -C $RepoRoot ls-files -z
   377	    $lsExit = $LASTEXITCODE
   378	} finally {
   379	    [Console]::OutputEncoding = $prevOutEnc
   380	}
   381	if ($lsExit -ne 0) {
   382	    Write-Error "FATAL: source-secret-scan git ls-files failed (exit $lsExit). Refusing to ship a release without a source scan."
   383	    exit 1
   384	}
   385	$sourceFiles = @(($lsRaw -join "") -split "`0" | Where-Object { $_ } | Sort-Object -Unique)
   386	$skipExt = @('.exe', '.msi', '.zip', '.7z', '.png', '.ico', '.icns', '.dll')
   387	
   388	# Known-synthetic literals, allowlisted BY EXACT VALUE rather than by file.
   389	#
   390	# The previous design skipped whole files (commands.rs, legacy_import.rs,
   391	# tests/, *.test.ts, four prose docs, and this script). That exempted ~23 text
   392	# files INCLUDING production Rust and the gate itself: any real token later
   393	# pasted into them would never have been seen. "Every tracked file" was not
   394	# true.
   395	#
   396	# Now nothing is exempt. Every tracked text file is scanned, and a match only
   397	# passes if its exact text appears below. Each entry is a fixture whose
   398	# synthetic nature is self-evident (DEADBEEF / repeated nibbles / sequential
   399	# counters / obvious placeholder session names), except the one PoC hash in the
   400	# security-audit archive, which demonstrates a dedupe-key collision where the
   401	# point is that the SAME arbitrary string appears twice.
   402	#
   403	# Adding an entry here is a visible, reviewable diff line — unlike adding a
   404	# file to a skip list, which blinds the scanner to everything in that file
   405	# forever. A NEW fixture will fail the build until it is listed; that is the
   406	# intended cost.
   407	$AllowedLiterals = @(
   408	    'urn:btih:0201592fDEADBEEF0201592fDEADBEEF02015920',
   409	    'urn:btih:0201592fdeadbeef0201592fdeadbeef02015920',
   410	    'urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF',
   411	    'urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEF',
   412	    'urn:btih:0201592f00000000000000000000000000000001',
   413	    'urn:btih:0201592f00000000000000000000000000000002',
   414	    'urn:btih:0000000000000000000000000000000000000001',
   415	    'urn:btih:0000000000000000000000000000000000000002',
   416	    'urn:btih:0000000000000000000000000000000000000003',
   417	    'urn:btih:0123456789abcdef0123456789abcdef01234567',
   418	    'urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
   419	    'urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
   420	    'urn:btih:cccccccccccccccccccccccccccccccccccccccc',
   421	    'urn:btih:ABCDEF0123456789ABCDEF0123456789ABCDEF01',
   422	    'urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
   423	    'urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
   424	    'urn:btih:cccccccccccccccccccccccccccccccc',
   425	    # Dedupe-key collision PoC (prompt/security-audit-fixes-2026-07-28.md).
   426	    'urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a',
   427	    'magnet:?xt=urn:btih:0201592fDEADBEEF0201592fDEADBEEF02015920',
   428	    'magnet:?xt=urn:btih:0201592fdeadbeef0201592fdeadbeef02015920',
   429	    'magnet:?xt=urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF',
   430	    'magnet:?xt=urn:btih:0201592f00000000000000000000000000000001',
   431	    'magnet:?xt=urn:btih:0201592f00000000000000000000000000000002',
   432	    'magnet:?xt=urn:btih:0000000000000000000000000000000000000001',
   433	    'magnet:?xt=urn:btih:0000000000000000000000000000000000000002',
   434	    'magnet:?xt=urn:btih:0000000000000000000000000000000000000003',
   435	    'magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567',
   436	    'magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
   437	    'magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
   438	    'magnet:?xt=urn:btih:cccccccccccccccccccccccccccccccccccccccc',
   439	    'magnet:?xt=urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a',
   440	    'magnet:?xt=urn:btih:0123456789abcdef',
   441	    'magnet:?xt=urn:btih:ABCDEF0123456789',
   442	    'MAGNET:?xt=urn:btih:ABCDEF0123456789',
   443	    'MAGNET:?xt=urn:btih:ABCDEF0123456789ABCDEF0123456789ABCDEF01',
   444	    'magnet:?xt=urn:btih:fedcba9876543210',
   445	    # Placeholder cookie values in the Rust cookie-store tests.
   446	    '_jdb_session=paste_session',
   447	    '_jdb_session=keep_me_alive',
   448	    '_jdb_session=e2e_jdb_session',
   449	    '_jdb_session=regress_session',
   450	    '_jdb_session=preexisting_session',

--- POWERSHELL ---
/bin/bash: line 1: pwsh: command not found
pwsh_status=127

exec
/bin/bash -lc 'git diff --unified=3 3f55ec0''^ 3f55ec0 -- scripts/build-release.ps1 > /tmp/review.diff; wc -l /tmp/review.diff; grep -n '"'"'^@@'"' /tmp/review.diff; sed -n '1,240p' /tmp/review.diff; sed -n '241,520p' /tmp/review.diff; sed -n '521,800p' /tmp/review.diff" in /home/cy5407/javdb-magnet-workbench
 succeeded in 0ms:
644 /tmp/review.diff
5:@@ -35,6 +35,14 @@
20:@@ -75,6 +83,312 @@ function FailExit($msg) {
333:@@ -88,8 +402,21 @@ Step "Verifying working tree is clean"
356:@@ -265,62 +592,17 @@ $ScanTargets = @(
425:@@ -333,6 +615,7 @@ foreach ($exe in $ScanTargets) {
433:@@ -343,174 +626,7 @@ foreach ($exe in $ScanTargets) {
609:@@ -559,12 +675,13 @@ Ok ("Wrote " + $SumsPath)
624:@@ -599,12 +716,15 @@ $manifest = [ordered]@{
diff --git a/scripts/build-release.ps1 b/scripts/build-release.ps1
index daf1416..d2f0de9 100644
--- a/scripts/build-release.ps1
+++ b/scripts/build-release.ps1
@@ -35,6 +35,14 @@
 # Or from app/:
 #     npm run release
 
+param(
+    # Run ONLY the source secret scan and exit. No build, no staging, no zip.
+    # Added so this gate can actually be executed and red-tested on its own:
+    # a full release run costs minutes of PyInstaller + cargo before it would
+    # ever reach the scan.
+    [switch]$AuditOnly
+)
+
 $ErrorActionPreference = "Stop"
 Set-StrictMode -Version Latest
 
@@ -75,6 +83,312 @@ function FailExit($msg) {
 # ---------------------------------------------------------------------------
 # Step 0: Prepare release/ output dir
 # ---------------------------------------------------------------------------
+
+$Patterns = @(
+    # Every pattern below is matched case-INSENSITIVELY (see $RxOpts). URI
+    # schemes are case-insensitive per RFC 3986, and this project's own parser
+    # agrees: sidecar.py lower-cases before its `startswith("magnet:")` check
+    # and _REDACT_MAGNET_RX carries re.IGNORECASE. A case-sensitive scan would
+    # therefore miss `MAGNET:?XT=URN:BTIH:...` — a string production happily
+    # accepts and interns. Verified: register_magnets returns ok for the
+    # upper-case form while the old pattern did not match it at all.
+    # GREEDY `{40,}`, not `{40}` and not `{40}(?!hex)`. All three were tried:
+    #   {40}            — a 42-hex value matches its first 40 chars, and if
+    #                     those 40 are allowlisted the real value passes.
+    #   {40}(?![hex])   — a 42-hex value then matches NOTHING AT ALL (the
+    #                     lookahead fails at every start offset), which is a
+    #                     bigger hole than the one it was meant to close. This
+    #                     was caught by executing the red test, not by reading.
+    #   {40,}           — consumes the whole run, so anything longer than an
+    #                     allowlisted literal is a distinct value and fails.
+    @{ name = 'urn:btih:<40+hex>';           rx = 'urn:btih:[a-fA-F0-9]{40,}' },
+    # BitTorrent v1 infohashes are 40 hex OR 32 base32 (BEP 9); v2 uses a
+    # different URN entirely (`urn:btmh:`, BEP 52). An earlier commit message
+    # claimed "64-hex btih v2" — that form does not exist. Cover all three.
+    @{ name = 'urn:btih:<32+base32>';        rx = 'urn:btih:[A-Z2-7]{32,}' },
+    @{ name = 'urn:btmh: (BitTorrent v2)';   rx = 'urn:bt' + 'mh:[a-fA-F0-9]{10,}' },
+    # `{16,}` rather than `+`: redact_magnet()'s output is a fixed 8 hex chars,
+    # so `+` made this pattern flag the project's own CORRECTLY REDACTED form.
+    # Real v1 infohashes are 40 hex (or 32 base32); 16 is a safe floor that
+    # passes the 8-char redacted form and catches every real length.
+    @{ name = 'magnet:?xt=';                 rx = 'magnet:\?xt=urn:bt' + '[im]h:[a-zA-Z0-9]{16,}' },
+    # Length floors and separator grammar now follow what PRODUCTION accepts,
+    # not what a "realistic" secret looks like. secret_store.rs takes 1-255
+    # ASCII alphanumerics; legacy_import.rs trims whitespace around `=` and
+    # strips surrounding quotes; parse_cookie_string trims each `k = v` pair.
+    # A scanner narrower than the parser is a scanner with a documented hole,
+    # so `\s*`, optional quotes and a floor of 1 are all deliberate. The cost
+    # is that short test fixtures now match — they are listed in
+    # $AllowedLiterals, which is exactly the reviewable-diff tradeoff this
+    # design already makes everywhere else.
+    @{ name = 'Cloudflare clearance cookie'; rx = 'cf' + '_clearance\s*=\s*["'']?' + '[A-Za-z0-9_.~+/=-]{1,}' },
+    @{ name = 'Cloudflare bot cookie';       rx = '__cf' + '_bm\s*=\s*["'']?' + '[A-Za-z0-9_.~+/=-]{1,}' },
+    @{ name = 'JavDB session cookie';        rx = '_jdb' + '_session\s*=\s*["'']?' + '[A-Za-z0-9_.~+/=-]{1,}' },
+    @{ name = 'remember_me_token=';          rx = 'remember_me_token\s*=\s*["'']?' + '[A-Za-z0-9_.~+/=-]{1,}' },
+    # token68 (RFC 7235) allows -._~+/ and trailing '='; the old [A-Za-z0-9_-]
+    # stopped at the first '.' and reported a truncated match.
+    @{ name = 'Authorization bearer header'; rx = 'Authorization:\s*' + 'Bearer\s+' + '[A-Za-z0-9_.~+/=-]{8,}' },
+    @{ name = 'Bearer <token>';              rx = 'Bearer\s+' + '[A-Za-z0-9_.~+/=-]{16,}' },
+    @{ name = 'RD_API_TOKEN=<value>';        rx = 'RD_API' + '_TOKEN\s*=\s*["'']?' + '[A-Za-z0-9_-]{1,}' }
+)
+
+# All regex evaluation in this script goes through these options. See the
+# comment above $Patterns for why IgnoreCase is not optional here.
+$RxOpts = [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
+
+$ScanFail = $false
+$BinaryHitCount = 0
+# We decode the binary bytes both as ASCII *and* UTF-16LE because PE
+# images routinely embed strings in both encodings:
+#   - ASCII / UTF-8 covers Rust &str literals, format!() output, and
+#     anything wired through libc-style APIs.
+#   - UTF-16LE covers strings handed to the Win32 wide API (e.g. a
+#     `let path = format!("HKCU\\...\\{}", token);` later passed to
+#     `RegOpenKeyExW`), which would otherwise sail past an ASCII-only
+#     scan even though the secret material is plainly readable in a
+#     hex dump.
+# Running both passes is cheap (two regex sweeps over the same byte
+# blob); failing to do it would silently halve the scan's coverage.
+$Encodings = @(
+    @{ label = 'ASCII';      encoding = [System.Text.Encoding]::ASCII },
+    @{ label = 'UTF-16LE';   encoding = [System.Text.Encoding]::Unicode }
+)
+
+function Invoke-SourceSecretScan {
+
+    # ---------------------------------------------------------------------------
+    # Step 7: Source secret scan — over EVERY tracked file
+    #
+    # This used to derive its file list from `git diff <origin/HEAD>..HEAD` plus
+    # the working-tree diff. That made coverage depend on where HEAD happened to
+    # sit: cutting a release from an already-pushed master left both diffs empty,
+    # so the scan walked ZERO files and still wrote `source_secret_hits: 0` into
+    # the manifest — a vacuous pass that read exactly like a real one. It was
+    # found the hard way: a magnet literal sat in verify-windows-build.ps1 from
+    # the commit that introduced it and was never once scanned, until an
+    # unrelated edit to that file finally pulled it into the diff.
+    #
+    # The file list now comes from `git ls-files`, so coverage is a property of
+    # the repo rather than of the branch topology. Content is read from disk, so
+    # uncommitted edits to tracked files are scanned as they actually are.
+    # Untracked files are deliberately out of scope: they are neither committed
+    # nor shipped inside the portable zip.
+    # ---------------------------------------------------------------------------
+    Step "Source secret scan (all tracked text files)"
+    # -z + NUL split: without it git quotes paths containing non-ASCII or control
+    # characters ("\303\251.md"), and the quoted name matches nothing on disk — the
+    # file is then silently dropped from the scan.
+    # Windows PowerShell 5.1 decodes native-command output using the console code
+    # page, not UTF-8. A tracked filename with non-ASCII characters would come back
+    # mangled, Test-Path would then fail to resolve it, and the entry would vanish
+    # from the scan. Force UTF-8 for the duration of the git call.
+    $prevOutEnc = [Console]::OutputEncoding
+    try {
+        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
+        $lsRaw = & git -C $RepoRoot ls-files -z
+        $lsExit = $LASTEXITCODE
+    } finally {
+        [Console]::OutputEncoding = $prevOutEnc
+    }
+    if ($lsExit -ne 0) {
+        Write-Error "FATAL: source-secret-scan git ls-files failed (exit $lsExit). Refusing to ship a release without a source scan."
+        exit 1
+    }
+    $sourceFiles = @(($lsRaw -join "") -split "`0" | Where-Object { $_ } | Sort-Object -Unique)
+    $skipExt = @('.exe', '.msi', '.zip', '.7z', '.png', '.ico', '.icns', '.dll')
+
+    # Known-synthetic literals, allowlisted BY EXACT VALUE rather than by file.
+    #
+    # The previous design skipped whole files (commands.rs, legacy_import.rs,
+    # tests/, *.test.ts, four prose docs, and this script). That exempted ~23 text
+    # files INCLUDING production Rust and the gate itself: any real token later
+    # pasted into them would never have been seen. "Every tracked file" was not
+    # true.
+    #
+    # Now nothing is exempt. Every tracked text file is scanned, and a match only
+    # passes if its exact text appears below. Each entry is a fixture whose
+    # synthetic nature is self-evident (DEADBEEF / repeated nibbles / sequential
+    # counters / obvious placeholder session names), except the one PoC hash in the
+    # security-audit archive, which demonstrates a dedupe-key collision where the
+    # point is that the SAME arbitrary string appears twice.
+    #
+    # Adding an entry here is a visible, reviewable diff line — unlike adding a
+    # file to a skip list, which blinds the scanner to everything in that file
+    # forever. A NEW fixture will fail the build until it is listed; that is the
+    # intended cost.
+    $AllowedLiterals = @(
+        'urn:btih:0201592fDEADBEEF0201592fDEADBEEF02015920',
+        'urn:btih:0201592fdeadbeef0201592fdeadbeef02015920',
+        'urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF',
+        'urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEF',
+        'urn:btih:0201592f00000000000000000000000000000001',
+        'urn:btih:0201592f00000000000000000000000000000002',
+        'urn:btih:0000000000000000000000000000000000000001',
+        'urn:btih:0000000000000000000000000000000000000002',
+        'urn:btih:0000000000000000000000000000000000000003',
+        'urn:btih:0123456789abcdef0123456789abcdef01234567',
+        'urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
+        'urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
+        'urn:btih:cccccccccccccccccccccccccccccccccccccccc',
+        'urn:btih:ABCDEF0123456789ABCDEF0123456789ABCDEF01',
+        'urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
+        'urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
+        'urn:btih:cccccccccccccccccccccccccccccccc',
+        # Dedupe-key collision PoC (prompt/security-audit-fixes-2026-07-28.md).
+        'urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a',
+        'magnet:?xt=urn:btih:0201592fDEADBEEF0201592fDEADBEEF02015920',
+        'magnet:?xt=urn:btih:0201592fdeadbeef0201592fdeadbeef02015920',
+        'magnet:?xt=urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF',
+        'magnet:?xt=urn:btih:0201592f00000000000000000000000000000001',
+        'magnet:?xt=urn:btih:0201592f00000000000000000000000000000002',
+        'magnet:?xt=urn:btih:0000000000000000000000000000000000000001',
+        'magnet:?xt=urn:btih:0000000000000000000000000000000000000002',
+        'magnet:?xt=urn:btih:0000000000000000000000000000000000000003',
+        'magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567',
+        'magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
+        'magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
+        'magnet:?xt=urn:btih:cccccccccccccccccccccccccccccccccccccccc',
+        'magnet:?xt=urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a',
+        'magnet:?xt=urn:btih:0123456789abcdef',
+        'magnet:?xt=urn:btih:ABCDEF0123456789',
+        'MAGNET:?xt=urn:btih:ABCDEF0123456789',
+        'MAGNET:?xt=urn:btih:ABCDEF0123456789ABCDEF0123456789ABCDEF01',
+        'magnet:?xt=urn:btih:fedcba9876543210',
+        # Cookie / token fixtures. These only started matching once the patterns
+    # were widened to production's grammar (floor of 1 char, optional quotes
+    # and whitespace around `=`). Every value here is self-evidently a
+    # placeholder — XXX, `...`, brand_new, clear_me — and lives in a test or
+    # in documentation showing the cookie format.
+    'RD_API_TOKEN=abc-123',
+    '_jdb_session=...',
+    '_jdb_session=XXX',
+    '_jdb_session=abc',
+    '_jdb_session=abc123',
+    '_jdb_session=brand_new',
+    '_jdb_session=clear_me',
+    '_jdb_session=e2e_jdb_session',
+    '_jdb_session=keep_me_alive',
+    '_jdb_session=keyring_only',
+    '_jdb_session=label_test',
+    '_jdb_session=new',
+    '_jdb_session=older_keyring_value',
+    '_jdb_session=paste_session',
+    '_jdb_session=preexisting_session',
+    '_jdb_session=regress_session',
+    '_jdb_session=resurrect_me',
+    '_jdb_session=xyz',
+    'cf_clearance=...',
+    'cf_clearance=XXX',
+    'cf_clearance=brand_new',
+    'cf_clearance=clear_cf',
+    'cf_clearance=e2e_cf_clearance',
+    'cf_clearance=fresh',
+    'cf_clearance=label_test_cf',
+    'cf_clearance=paste_cf',
+    'cf_clearance=preexisting_cf',
+    'cf_clearance=regress_cf',
+    'cf_clearance=resurrect_cf',
+    'cf_clearance=xyz',
+    'cf_clearance=xyz789',
+    # Placeholder cookie values in the Rust cookie-store tests.
+        '_jdb_session=paste_session',
+        '_jdb_session=keep_me_alive',
+        '_jdb_session=e2e_jdb_session',
+        '_jdb_session=regress_session',
+        '_jdb_session=preexisting_session',
+        '_jdb_session=label_test',
+        '_jdb_session=older_keyring_value',
+        '_jdb_session=keyring_only',
+        '_jdb_session=resurrect_me'
+    )
+
+    $SourceHits    = @()
+    $SourceEligible = 0   # tracked, non-binary, i.e. in scope
+    $SourceScanned  = 0   # actually read and regexed
+    $SourceAllowed  = 0   # matched but present in $AllowedLiterals
+    foreach ($rel in $sourceFiles) {
+        $full = Join-Path $RepoRoot $rel
+        if ($skipExt -contains ([System.IO.Path]::GetExtension($rel).ToLowerInvariant())) { continue }
+        $SourceEligible++
+        # -LiteralPath: a tracked file called `notes[1].md` is a valid wildcard to
+        # Test-Path, which would report it missing.
+        #
+        # Fail CLOSED here, and count the entry as eligible BEFORE testing it. The
+        # earlier version skipped unresolvable paths before incrementing, so the
+        # eligible-equals-scanned invariant could never detect them — the exact
+        # blind spot that invariant was added to close. The working tree is
+        # verified clean at Step 0, so every index entry must exist on disk; one
+        # that does not means the path came back mangled (encoding) or something
+        # changed underneath the build.
+        if (-not (Test-Path -LiteralPath $full -PathType Leaf)) {
+            FailExit ("Source secret scan could not resolve tracked path: " + $rel + " — refusing to ship a partial scan.")
+        }
+        # Fail CLOSED on read errors. The old code used -ErrorAction SilentlyContinue
+        # and `continue`d on $null, so an unreadable file vanished from the scan
+        # while the run still reported success — a file the scanner could not read
+        # is exactly the file worth worrying about.
+        # Read BYTES, not text. Get-Content -Raw picks an encoding for you, and the
+        # default differs between Windows PowerShell 5.1 and PowerShell 7: a
+        # BOM-less UTF-16LE file decodes into ASCII interleaved with NULs, so a
+        # perfectly readable secret matches nothing while I/O "succeeds" and
+        # eligible still equals scanned.
+        try {
+            $bytes = [System.IO.File]::ReadAllBytes($full)
+        } catch {
+            FailExit ("Source secret scan could not read " + $rel + ": " + $_.Exception.Message)
+        }
+        $SourceScanned++
+        # Same two-encoding sweep the binary scan does, plus a percent-decoded pass
+        # of each: production normalises `magnet:?xt=urn%3Abtih%3A<hash>` back to
+        # `btih:<hash>` (verified via _magnet_dedupe_key) and interns it, so a scan
+        # that only sees the raw bytes misses an escaped magnet entirely.
+        $variants = New-Object System.Collections.Generic.List[string]
+        foreach ($enc in $Encodings) {
+            $decoded = $enc.encoding.GetString($bytes)
+            $variants.Add($decoded)
+            try { $variants.Add([System.Uri]::UnescapeDataString($decoded)) } catch { }
+        }
+        foreach ($text in $variants) {
+            foreach ($p in $Patterns) {
+                foreach ($m in [regex]::Matches($text, $p.rx, $RxOpts)) {
+                    if ($AllowedLiterals -ccontains $m.Value) { $SourceAllowed++; continue }
+                    $SourceHits += ("      " + $rel + "  [" + $p.name + "]")
+                }
+            }
+        }
+    }
+    if ($SourceHits.Count -gt 0) {
+        Write-Host "    Source secret scan LEAK:" -ForegroundColor Red
+        # File + pattern only, never the matched text (same reasoning as the binary
+        # scan above).
+        $SourceHits | Sort-Object -Unique | ForEach-Object { Write-Host $_ -ForegroundColor Red }
+        Write-Host "    If a hit is a synthetic fixture, add its exact value to `$AllowedLiterals." -ForegroundColor Red
+        FailExit "Source secret scan failed"
+    }
+    # A scan that walked nothing must never report success — that is the exact
+    # failure mode this step was rewritten to eliminate, so assert it explicitly
+    # instead of trusting the file list to be non-empty.
+    if ($SourceScanned -eq 0) {
+        FailExit "Source secret scan walked 0 files — the scan is not covering anything. Check git ls-files and skipExt."
+    }
+    if ($SourceScanned -ne $SourceEligible) {
+        FailExit ("Source secret scan read " + $SourceScanned + " of " + $SourceEligible + " eligible files; refusing to ship a partial scan.")
+    }
+    Ok ("No unexpected source secrets (" + $SourceScanned + " text files scanned, " + $SourceAllowed + " allowlisted fixture matches)")
+}
+
+# --------------------------------------------------------------------------
+# -AuditOnly: run just the scan and exit. The clean-tree gate is skipped on
+# this path ON PURPOSE — red-testing the scanner means planting a secret,
+# which necessarily dirties the tree. Never use this mode to ship.
+# --------------------------------------------------------------------------
+if ($AuditOnly) {
+    Write-Output "== AUDIT ONLY: source secret scan, no build =="
+    Invoke-SourceSecretScan
+    Write-Output "[PASS] audit-only scan clean"
+    exit 0
+}
+
 Step "Verifying working tree is clean"
 # The build reads the WORKING TREE (npm/cargo/PyInstaller all compile what is on
 # disk), but the manifest records `git rev-parse HEAD`. With uncommitted edits
@@ -88,8 +402,21 @@ Step "Verifying working tree is clean"
 # file" is not the same as scanning every build input.
 $BuildStartHead = (& git -C $RepoRoot rev-parse HEAD).Trim()
 if ($LASTEXITCODE -ne 0) { FailExit "git rev-parse HEAD failed; refusing to build" }
-$treeStatus = & git -C $RepoRoot status --porcelain
+# --untracked-files=all explicitly: `status.showUntrackedFiles=no` in any
+# config layer would otherwise hide untracked files entirely, and untracked
+# top-level modules CAN be pulled into sidecar.exe by PyInstaller.
+$treeStatus = & git -C $RepoRoot status --porcelain --untracked-files=all
 if ($LASTEXITCODE -ne 0) { FailExit "git status failed (exit $LASTEXITCODE); refusing to build" }
+# assume-unchanged (h) and skip-worktree (S) make git report a clean tree while
+# the file on disk differs from the index — the build would compile content
+# that neither git status nor the source scan ever sees.
+$maskedEntries = & git -C $RepoRoot ls-files -v
+if ($LASTEXITCODE -ne 0) { FailExit "git ls-files -v failed; refusing to build" }
+$masked = @($maskedEntries | Where-Object { $_ -cmatch '^[a-z]' -or $_ -cmatch '^S ' })
+if ($masked.Count -gt 0) {
+    $masked | ForEach-Object { Write-Output ("      " + $_) }
+    FailExit "Tracked files are marked assume-unchanged/skip-worktree; git cannot vouch for their contents. Clear with: git update-index --no-assume-unchanged --no-skip-worktree <path>"
+}
 if ($treeStatus) {
     Write-Output "    Working tree is not clean:"
     $treeStatus | ForEach-Object { Write-Output ("      " + $_) }
@@ -265,62 +592,17 @@ $ScanTargets = @(
     (Join-Path $StagingDir "javdbmagnet.exe"),
     (Join-Path $StagingDir "sidecar.exe")
 )
-
-$Patterns = @(
-    # Every pattern below is matched case-INSENSITIVELY (see $RxOpts). URI
-    # schemes are case-insensitive per RFC 3986, and this project's own parser
-    # agrees: sidecar.py lower-cases before its `startswith("magnet:")` check
-    # and _REDACT_MAGNET_RX carries re.IGNORECASE. A case-sensitive scan would
-    # therefore miss `MAGNET:?XT=URN:BTIH:...` — a string production happily
-    # accepts and interns. Verified: register_magnets returns ok for the
-    # upper-case form while the old pattern did not match it at all.
-    @{ name = 'urn:btih:<40hex>';            rx = 'urn:btih:[a-fA-F0-9]{40}' },
-    # BitTorrent v1 infohashes are 40 hex OR 32 base32 (BEP 9); v2 uses a
-    # different URN entirely (`urn:btmh:`, BEP 52). An earlier commit message
-    # claimed "64-hex btih v2" — that form does not exist. Cover all three.
-    @{ name = 'urn:btih:<32base32>';         rx = 'urn:btih:[A-Z2-7]{32}' },
-    @{ name = 'urn:btmh: (BitTorrent v2)';   rx = 'urn:bt' + 'mh:[a-fA-F0-9]{10,}' },
-    # `{16,}` rather than `+`: redact_magnet()'s output is a fixed 8 hex chars,
-    # so `+` made this pattern flag the project's own CORRECTLY REDACTED form.
-    # Real v1 infohashes are 40 hex (or 32 base32); 16 is a safe floor that
-    # passes the 8-char redacted form and catches every real length.
-    @{ name = 'magnet:?xt=';                 rx = 'magnet:\?xt=urn:bt' + '[im]h:[a-zA-Z0-9]{16,}' },
-    @{ name = 'Cloudflare clearance cookie'; rx = 'cf' + '_clearance=' + '[A-Za-z0-9_.-]{20,}' },
-    @{ name = 'Cloudflare bot cookie';       rx = '__cf' + '_bm=' + '[A-Za-z0-9_.-]{20,}' },
-    @{ name = 'JavDB session cookie';        rx = '_jdb' + '_session=' + '[A-Za-z0-9_.-]{10,}' },
-    @{ name = 'remember_me_token=';          rx = 'remember_me_token=[A-Za-z0-9_.-]{10,}' },
-    @{ name = 'Authorization bearer header'; rx = 'Authorization:\s*' + 'Bearer\s+' + '[A-Za-z0-9_-]{20,}' },
-    @{ name = 'Bearer <30+ char token>';     rx = 'Bearer ' + '[A-Za-z0-9_-]{30,}' },
-    @{ name = 'RD_API_TOKEN=<value>';        rx = 'RD_API' + '_TOKEN=' + '[A-Za-z0-9_-]{20,}' }
-)
-
-# All regex evaluation in this script goes through these options. See the
-# comment above $Patterns for why IgnoreCase is not optional here.
-$RxOpts = [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
-
-$ScanFail = $false
-$BinaryHitCount = 0
-# We decode the binary bytes both as ASCII *and* UTF-16LE because PE
-# images routinely embed strings in both encodings:
-#   - ASCII / UTF-8 covers Rust &str literals, format!() output, and
-#     anything wired through libc-style APIs.
-#   - UTF-16LE covers strings handed to the Win32 wide API (e.g. a
-#     `let path = format!("HKCU\\...\\{}", token);` later passed to
-#     `RegOpenKeyExW`), which would otherwise sail past an ASCII-only
-#     scan even though the secret material is plainly readable in a
-#     hex dump.
-# Running both passes is cheap (two regex sweeps over the same byte
-# blob); failing to do it would silently halve the scan's coverage.
-$Encodings = @(
-    @{ label = 'ASCII';      encoding = [System.Text.Encoding]::ASCII },
-    @{ label = 'UTF-16LE';   encoding = [System.Text.Encoding]::Unicode }
-)
 foreach ($exe in $ScanTargets) {
     $name = Split-Path $exe -Leaf
     $bytes = [System.IO.File]::ReadAllBytes($exe)
     $hits = @()
     foreach ($enc in $Encodings) {
-        $text = $enc.encoding.GetString($bytes)
+        $decoded = $enc.encoding.GetString($bytes)
+        # Percent-decoded pass for the same reason as the source scan: an
+        # escaped magnet is still a magnet by the time production sees it.
+        $texts = @($decoded)
+        try { $texts += [System.Uri]::UnescapeDataString($decoded) } catch { }
+        foreach ($text in $texts) {
         foreach ($p in $Patterns) {
             $regexMatches = [regex]::Matches($text, $p.rx, $RxOpts)
             if ($regexMatches.Count -gt 0) {
@@ -333,6 +615,7 @@ foreach ($exe in $ScanTargets) {
                 $BinaryHitCount += $regexMatches.Count
             }
         }
+        }
     }
     if ($hits.Count -gt 0) {
         Write-Host "    [$name] LEAK:" -ForegroundColor Red
@@ -343,174 +626,7 @@ foreach ($exe in $ScanTargets) {
     }
 }
 if ($ScanFail) { FailExit "Binary content scan failed" }
-
-# ---------------------------------------------------------------------------
-# Step 7: Source secret scan — over EVERY tracked file
-#
-# This used to derive its file list from `git diff <origin/HEAD>..HEAD` plus
-# the working-tree diff. That made coverage depend on where HEAD happened to
-# sit: cutting a release from an already-pushed master left both diffs empty,
-# so the scan walked ZERO files and still wrote `source_secret_hits: 0` into
-# the manifest — a vacuous pass that read exactly like a real one. It was
-# found the hard way: a magnet literal sat in verify-windows-build.ps1 from
-# the commit that introduced it and was never once scanned, until an
-# unrelated edit to that file finally pulled it into the diff.
-#
-# The file list now comes from `git ls-files`, so coverage is a property of
-# the repo rather than of the branch topology. Content is read from disk, so
-# uncommitted edits to tracked files are scanned as they actually are.
-# Untracked files are deliberately out of scope: they are neither committed
-# nor shipped inside the portable zip.
-# ---------------------------------------------------------------------------
-Step "Source secret scan (all tracked text files)"
-# -z + NUL split: without it git quotes paths containing non-ASCII or control
-# characters ("\303\251.md"), and the quoted name matches nothing on disk — the
-# file is then silently dropped from the scan.
-# Windows PowerShell 5.1 decodes native-command output using the console code
-# page, not UTF-8. A tracked filename with non-ASCII characters would come back
-# mangled, Test-Path would then fail to resolve it, and the entry would vanish
-# from the scan. Force UTF-8 for the duration of the git call.
-$prevOutEnc = [Console]::OutputEncoding
-try {
-    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
-    $lsRaw = & git -C $RepoRoot ls-files -z
-    $lsExit = $LASTEXITCODE
-} finally {
-    [Console]::OutputEncoding = $prevOutEnc
-}
-if ($lsExit -ne 0) {
-    Write-Error "FATAL: source-secret-scan git ls-files failed (exit $lsExit). Refusing to ship a release without a source scan."
-    exit 1
-}
-$sourceFiles = @(($lsRaw -join "") -split "`0" | Where-Object { $_ } | Sort-Object -Unique)
-$skipExt = @('.exe', '.msi', '.zip', '.7z', '.png', '.ico', '.icns', '.dll')
-
-# Known-synthetic literals, allowlisted BY EXACT VALUE rather than by file.
-#
-# The previous design skipped whole files (commands.rs, legacy_import.rs,
-# tests/, *.test.ts, four prose docs, and this script). That exempted ~23 text
-# files INCLUDING production Rust and the gate itself: any real token later
-# pasted into them would never have been seen. "Every tracked file" was not
-# true.
-#
-# Now nothing is exempt. Every tracked text file is scanned, and a match only
-# passes if its exact text appears below. Each entry is a fixture whose
-# synthetic nature is self-evident (DEADBEEF / repeated nibbles / sequential
-# counters / obvious placeholder session names), except the one PoC hash in the
-# security-audit archive, which demonstrates a dedupe-key collision where the
-# point is that the SAME arbitrary string appears twice.
-#
-# Adding an entry here is a visible, reviewable diff line — unlike adding a
-# file to a skip list, which blinds the scanner to everything in that file
-# forever. A NEW fixture will fail the build until it is listed; that is the
-# intended cost.
-$AllowedLiterals = @(
-    'urn:btih:0201592fDEADBEEF0201592fDEADBEEF02015920',
-    'urn:btih:0201592fdeadbeef0201592fdeadbeef02015920',
-    'urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF',
-    'urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEF',
-    'urn:btih:0201592f00000000000000000000000000000001',
-    'urn:btih:0201592f00000000000000000000000000000002',
-    'urn:btih:0000000000000000000000000000000000000001',
-    'urn:btih:0000000000000000000000000000000000000002',
-    'urn:btih:0000000000000000000000000000000000000003',
-    'urn:btih:0123456789abcdef0123456789abcdef01234567',
-    'urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
-    'urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
-    'urn:btih:cccccccccccccccccccccccccccccccccccccccc',
-    'urn:btih:ABCDEF0123456789ABCDEF0123456789ABCDEF01',
-    'urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
-    'urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
-    'urn:btih:cccccccccccccccccccccccccccccccc',
-    # Dedupe-key collision PoC (prompt/security-audit-fixes-2026-07-28.md).
-    'urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a',
-    'magnet:?xt=urn:btih:0201592fDEADBEEF0201592fDEADBEEF02015920',
-    'magnet:?xt=urn:btih:0201592fdeadbeef0201592fdeadbeef02015920',
-    'magnet:?xt=urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF',
-    'magnet:?xt=urn:btih:0201592f00000000000000000000000000000001',
-    'magnet:?xt=urn:btih:0201592f00000000000000000000000000000002',
-    'magnet:?xt=urn:btih:0000000000000000000000000000000000000001',
-    'magnet:?xt=urn:btih:0000000000000000000000000000000000000002',
-    'magnet:?xt=urn:btih:0000000000000000000000000000000000000003',
-    'magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567',
-    'magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
-    'magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
-    'magnet:?xt=urn:btih:cccccccccccccccccccccccccccccccccccccccc',
-    'magnet:?xt=urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a',
-    'magnet:?xt=urn:btih:0123456789abcdef',
-    'magnet:?xt=urn:btih:ABCDEF0123456789',
-    'MAGNET:?xt=urn:btih:ABCDEF0123456789',
-    'MAGNET:?xt=urn:btih:ABCDEF0123456789ABCDEF0123456789ABCDEF01',
-    'magnet:?xt=urn:btih:fedcba9876543210',
-    # Placeholder cookie values in the Rust cookie-store tests.
-    '_jdb_session=paste_session',
-    '_jdb_session=keep_me_alive',
-    '_jdb_session=e2e_jdb_session',
-    '_jdb_session=regress_session',
-    '_jdb_session=preexisting_session',
-    '_jdb_session=label_test',
-    '_jdb_session=older_keyring_value',
-    '_jdb_session=keyring_only',
-    '_jdb_session=resurrect_me'
-)
-
-$SourceHits    = @()
-$SourceEligible = 0   # tracked, non-binary, i.e. in scope
-$SourceScanned  = 0   # actually read and regexed
-$SourceAllowed  = 0   # matched but present in $AllowedLiterals
-foreach ($rel in $sourceFiles) {
-    $full = Join-Path $RepoRoot $rel
-    if ($skipExt -contains ([System.IO.Path]::GetExtension($rel).ToLowerInvariant())) { continue }
-    $SourceEligible++
-    # -LiteralPath: a tracked file called `notes[1].md` is a valid wildcard to
-    # Test-Path, which would report it missing.
-    #
-    # Fail CLOSED here, and count the entry as eligible BEFORE testing it. The
-    # earlier version skipped unresolvable paths before incrementing, so the
-    # eligible-equals-scanned invariant could never detect them — the exact
-    # blind spot that invariant was added to close. The working tree is
-    # verified clean at Step 0, so every index entry must exist on disk; one
-    # that does not means the path came back mangled (encoding) or something
-    # changed underneath the build.
-    if (-not (Test-Path -LiteralPath $full -PathType Leaf)) {
-        FailExit ("Source secret scan could not resolve tracked path: " + $rel + " — refusing to ship a partial scan.")
-    }
-    # Fail CLOSED on read errors. The old code used -ErrorAction SilentlyContinue
-    # and `continue`d on $null, so an unreadable file vanished from the scan
-    # while the run still reported success — a file the scanner could not read
-    # is exactly the file worth worrying about.
-    try {
-        $text = Get-Content -LiteralPath $full -Raw -ErrorAction Stop
-    } catch {
-        FailExit ("Source secret scan could not read " + $rel + ": " + $_.Exception.Message)
-    }
-    if ($null -eq $text) { $text = "" }   # legitimately empty file
-    $SourceScanned++
-    foreach ($p in $Patterns) {
-        foreach ($m in [regex]::Matches($text, $p.rx, $RxOpts)) {
-            if ($AllowedLiterals -ccontains $m.Value) { $SourceAllowed++; continue }
-            $SourceHits += ("      " + $rel + "  [" + $p.name + "]")
-        }
-    }
-}
-if ($SourceHits.Count -gt 0) {
-    Write-Host "    Source secret scan LEAK:" -ForegroundColor Red
-    # File + pattern only, never the matched text (same reasoning as the binary
-    # scan above).
-    $SourceHits | Sort-Object -Unique | ForEach-Object { Write-Host $_ -ForegroundColor Red }
-    Write-Host "    If a hit is a synthetic fixture, add its exact value to `$AllowedLiterals." -ForegroundColor Red
-    FailExit "Source secret scan failed"
-}
-# A scan that walked nothing must never report success — that is the exact
-# failure mode this step was rewritten to eliminate, so assert it explicitly
-# instead of trusting the file list to be non-empty.
-if ($SourceScanned -eq 0) {
-    FailExit "Source secret scan walked 0 files — the scan is not covering anything. Check git ls-files and skipExt."
-}
-if ($SourceScanned -ne $SourceEligible) {
-    FailExit ("Source secret scan read " + $SourceScanned + " of " + $SourceEligible + " eligible files; refusing to ship a partial scan.")
-}
-Ok ("No unexpected source secrets (" + $SourceScanned + " text files scanned, " + $SourceAllowed + " allowlisted fixture matches)")
+Invoke-SourceSecretScan
 
 # ---------------------------------------------------------------------------
 # Step 8: Compress staging dir to release/JavDBMagnet_<v>_portable.zip
@@ -559,12 +675,13 @@ Ok ("Wrote " + $SumsPath)
 # hardcoding `working_tree_clean = true`, would make the field an assertion
 # about the past rather than about the artifact.
 Step "Re-verifying source snapshot after build"
+$ManifestPath = Join-Path $ReleaseOutDir "release-manifest.json"
 $gitCommit = (& git -C $RepoRoot rev-parse HEAD).Trim()
 if ($LASTEXITCODE -ne 0) { FailExit "git rev-parse HEAD failed after build" }
 if ($gitCommit -ne $BuildStartHead) {
     FailExit ("HEAD moved during the build (" + $BuildStartHead + " -> " + $gitCommit + "); the artifacts do not match either commit.")
 }
-$treeStatusAfter = & git -C $RepoRoot status --porcelain
+$treeStatusAfter = & git -C $RepoRoot status --porcelain --untracked-files=all
 if ($LASTEXITCODE -ne 0) { FailExit "git status failed after build" }
 if ($treeStatusAfter) {
     $treeStatusAfter | ForEach-Object { Write-Output ("      " + $_) }
@@ -599,12 +716,15 @@ $manifest = [ordered]@{
         source_files_eligible    = $SourceEligible
         source_files_scanned     = $SourceScanned
         source_allowlisted_hits  = $SourceAllowed
-        # Asserted BEFORE the build and re-verified AFTER it (HEAD unchanged
-        # and porcelain still empty), so git_commit really does identify the
-        # source that was compiled and scanned — not merely what HEAD was when
-        # the run started.
+        # Checked before the build and re-checked after it. This does NOT prove
+        # the compiler observed exactly this snapshot: an edit made and reverted
+        # mid-build leaves both checks clean while an artifact was produced from
+        # transient source. The field is named for what is actually verified.
+        # Proving the stronger property requires building from an immutable
+        # checkout (git archive / a throwaway worktree), which this pipeline
+        # does not yet do.
         working_tree_clean       = $true
-        source_snapshot_verified = "before_and_after_build"
+        source_snapshot_verified = "pre_and_post_build_clean"
     }
     signing     = @{
         requested = ($env:SIGN -eq "1")

exec
/bin/bash -lc "python3 - <<'PY'
import subprocess,re,urllib.parse,pathlib
root=pathlib.Path('.').resolve()
raw=subprocess.check_output(['git','ls-files','-z'])
files=raw.decode().split('\\0')[:-1]
patterns=[
('hex',r'urn:btih:[a-fA-F0-9]{40,}'),('b32',r'urn:btih:[A-Z2-7]{32,}'),('btmh',r'urn:btmh:[a-fA-F0-9]{10,}'),('magnet',r'magnet:\\?xt=urn:bt[im]h:[a-zA-Z0-9]{16,}'),
('cf',r'cf_clearance\\s*=\\s*[\"\\']?[A-Za-z0-9_.~+/=-]{1,}'),('bm',r'__cf_bm\\s*=\\s*[\"\\']?[A-Za-z0-9_.~+/=-]{1,}'),('jdb',r'_jdb_session\\s*=\\s*[\"\\']?[A-Za-z0-9_.~+/=-]{1,}'),('rem',r'remember_me_token\\s*=\\s*[\"\\']?[A-Za-z0-9_.~+/=-]{1,}'),('auth',r'Authorization:\\s*Bearer\\s+[A-Za-z0-9_.~+/=-]{8,}'),('bear',r'Bearer\\s+[A-Za-z0-9_.~+/=-]{16,}'),('rd',r'RD_API_TOKEN\\s*=\\s*[\"\\']?[A-Za-z0-9_-]{1,}')]
skips={'.exe','.msi','.zip','.7z','.png','.ico','.icns','.dll'}
hits=[]
for f in files:
 p=root/f
 if p.suffix.lower() in skips:continue
 b=p.read_bytes()
 variants=[]
 variants += [b.decode('ascii','replace')]
 variants += [b.decode('utf-16le','replace')]
 variants += [urllib.parse.unquote(x) for x in list(variants)]
 for vi,t in enumerate(variants):
  for name,pat in patterns:
   for m in re.finditer(pat,t,re.I):
    hits.append((f,vi,name,m.group(0)))
from collections import Counter
print('files',len(files),'hits',len(hits),'unique',len(set(hits)))
for f,vi,name,val in hits:
 print(f,vi,name,repr(val[:100]))
PY" in /home/cy5407/javdb-magnet-workbench
 succeeded in 90ms:
files 129 hits 426 unique 314
README.md 0 cf 'cf_clearance=XXX'
README.md 0 jdb '_jdb_session=XXX'
README.md 2 cf 'cf_clearance=XXX'
README.md 2 jdb '_jdb_session=XXX'
app/src-tauri/src/commands.rs 0 cf 'cf_clearance=...'
app/src-tauri/src/commands.rs 0 cf 'cf_clearance=...'
app/src-tauri/src/commands.rs 0 cf 'cf_clearance=XXX'
app/src-tauri/src/commands.rs 0 cf 'cf_clearance=fresh'
app/src-tauri/src/commands.rs 0 cf 'cf_clearance=xyz'
app/src-tauri/src/commands.rs 0 cf 'cf_clearance=xyz'
app/src-tauri/src/commands.rs 0 cf 'cf_clearance=e2e_cf_clearance'
app/src-tauri/src/commands.rs 0 cf 'cf_clearance=regress_cf'
app/src-tauri/src/commands.rs 0 cf 'cf_clearance=preexisting_cf'
app/src-tauri/src/commands.rs 0 cf 'cf_clearance=XXX'
app/src-tauri/src/commands.rs 0 cf 'cf_clearance=label_test_cf'
app/src-tauri/src/commands.rs 0 cf 'cf_clearance=brand_new'
app/src-tauri/src/commands.rs 0 cf 'cf_clearance=paste_cf'
app/src-tauri/src/commands.rs 0 cf 'cf_clearance=paste_cf'
app/src-tauri/src/commands.rs 0 cf 'cf_clearance=clear_cf'
app/src-tauri/src/commands.rs 0 cf 'cf_clearance=clear_cf'
app/src-tauri/src/commands.rs 0 cf 'cf_clearance=XXX'
app/src-tauri/src/commands.rs 0 cf 'cf_clearance=resurrect_cf'
app/src-tauri/src/commands.rs 0 jdb '_jdb_session=...'
app/src-tauri/src/commands.rs 0 jdb '_jdb_session=...'
app/src-tauri/src/commands.rs 0 jdb '_jdb_session=XXX'
app/src-tauri/src/commands.rs 0 jdb '_jdb_session=new'
app/src-tauri/src/commands.rs 0 jdb '_jdb_session=XXX'
app/src-tauri/src/commands.rs 0 jdb '_jdb_session=abc'
app/src-tauri/src/commands.rs 0 jdb '_jdb_session=abc'
app/src-tauri/src/commands.rs 0 jdb '_jdb_session=e2e_jdb_session'
app/src-tauri/src/commands.rs 0 jdb '_jdb_session=regress_session'
app/src-tauri/src/commands.rs 0 jdb '_jdb_session=preexisting_session'
app/src-tauri/src/commands.rs 0 jdb '_jdb_session=XXX'
app/src-tauri/src/commands.rs 0 jdb '_jdb_session=label_test'
app/src-tauri/src/commands.rs 0 jdb '_jdb_session=older_keyring_value'
app/src-tauri/src/commands.rs 0 jdb '_jdb_session=brand_new'
app/src-tauri/src/commands.rs 0 jdb '_jdb_session=paste_session'
app/src-tauri/src/commands.rs 0 jdb '_jdb_session=paste_session'
app/src-tauri/src/commands.rs 0 jdb '_jdb_session=keep_me_alive'
app/src-tauri/src/commands.rs 0 jdb '_jdb_session=keep_me_alive'
app/src-tauri/src/commands.rs 0 jdb '_jdb_session=clear_me'
app/src-tauri/src/commands.rs 0 jdb '_jdb_session=clear_me'
app/src-tauri/src/commands.rs 0 jdb '_jdb_session=keyring_only'
app/src-tauri/src/commands.rs 0 jdb '_jdb_session=XXX'
app/src-tauri/src/commands.rs 0 jdb '_jdb_session=resurrect_me'
app/src-tauri/src/commands.rs 2 cf 'cf_clearance=...'
app/src-tauri/src/commands.rs 2 cf 'cf_clearance=...'
app/src-tauri/src/commands.rs 2 cf 'cf_clearance=XXX'
app/src-tauri/src/commands.rs 2 cf 'cf_clearance=fresh'
app/src-tauri/src/commands.rs 2 cf 'cf_clearance=xyz'
app/src-tauri/src/commands.rs 2 cf 'cf_clearance=xyz'
app/src-tauri/src/commands.rs 2 cf 'cf_clearance=e2e_cf_clearance'
app/src-tauri/src/commands.rs 2 cf 'cf_clearance=regress_cf'
app/src-tauri/src/commands.rs 2 cf 'cf_clearance=preexisting_cf'
app/src-tauri/src/commands.rs 2 cf 'cf_clearance=XXX'
app/src-tauri/src/commands.rs 2 cf 'cf_clearance=label_test_cf'
app/src-tauri/src/commands.rs 2 cf 'cf_clearance=brand_new'
app/src-tauri/src/commands.rs 2 cf 'cf_clearance=paste_cf'
app/src-tauri/src/commands.rs 2 cf 'cf_clearance=paste_cf'
app/src-tauri/src/commands.rs 2 cf 'cf_clearance=clear_cf'
app/src-tauri/src/commands.rs 2 cf 'cf_clearance=clear_cf'
app/src-tauri/src/commands.rs 2 cf 'cf_clearance=XXX'
app/src-tauri/src/commands.rs 2 cf 'cf_clearance=resurrect_cf'
app/src-tauri/src/commands.rs 2 jdb '_jdb_session=...'
app/src-tauri/src/commands.rs 2 jdb '_jdb_session=...'
app/src-tauri/src/commands.rs 2 jdb '_jdb_session=XXX'
app/src-tauri/src/commands.rs 2 jdb '_jdb_session=new'
app/src-tauri/src/commands.rs 2 jdb '_jdb_session=XXX'
app/src-tauri/src/commands.rs 2 jdb '_jdb_session=abc'
app/src-tauri/src/commands.rs 2 jdb '_jdb_session=abc'
app/src-tauri/src/commands.rs 2 jdb '_jdb_session=e2e_jdb_session'
app/src-tauri/src/commands.rs 2 jdb '_jdb_session=regress_session'
app/src-tauri/src/commands.rs 2 jdb '_jdb_session=preexisting_session'
app/src-tauri/src/commands.rs 2 jdb '_jdb_session=XXX'
app/src-tauri/src/commands.rs 2 jdb '_jdb_session=label_test'
app/src-tauri/src/commands.rs 2 jdb '_jdb_session=older_keyring_value'
app/src-tauri/src/commands.rs 2 jdb '_jdb_session=brand_new'
app/src-tauri/src/commands.rs 2 jdb '_jdb_session=paste_session'
app/src-tauri/src/commands.rs 2 jdb '_jdb_session=paste_session'
app/src-tauri/src/commands.rs 2 jdb '_jdb_session=keep_me_alive'
app/src-tauri/src/commands.rs 2 jdb '_jdb_session=keep_me_alive'
app/src-tauri/src/commands.rs 2 jdb '_jdb_session=clear_me'
app/src-tauri/src/commands.rs 2 jdb '_jdb_session=clear_me'
app/src-tauri/src/commands.rs 2 jdb '_jdb_session=keyring_only'
app/src-tauri/src/commands.rs 2 jdb '_jdb_session=XXX'
app/src-tauri/src/commands.rs 2 jdb '_jdb_session=resurrect_me'
app/src-tauri/src/cookie_store.rs 0 cf 'cf_clearance=...'
app/src-tauri/src/cookie_store.rs 0 cf 'cf_clearance=XXX'
app/src-tauri/src/cookie_store.rs 0 cf 'cf_clearance=XXX'
app/src-tauri/src/cookie_store.rs 0 cf 'cf_clearance=xyz'
app/src-tauri/src/cookie_store.rs 0 cf 'cf_clearance=xyz'
app/src-tauri/src/cookie_store.rs 0 cf 'cf_clearance=xyz789'
app/src-tauri/src/cookie_store.rs 0 cf 'cf_clearance=XXX'
app/src-tauri/src/cookie_store.rs 0 cf 'cf_clearance=xyz'
app/src-tauri/src/cookie_store.rs 0 cf 'cf_clearance=xyz'
app/src-tauri/src/cookie_store.rs 0 cf 'cf_clearance=XXX'
app/src-tauri/src/cookie_store.rs 0 jdb '_jdb_session=...'
app/src-tauri/src/cookie_store.rs 0 jdb '_jdb_session=XXX'
app/src-tauri/src/cookie_store.rs 0 jdb '_jdb_session=XXX'
app/src-tauri/src/cookie_store.rs 0 jdb '_jdb_session=abc'
app/src-tauri/src/cookie_store.rs 0 jdb '_jdb_session=abc'
app/src-tauri/src/cookie_store.rs 0 jdb '_jdb_session=abc123'
app/src-tauri/src/cookie_store.rs 0 jdb '_jdb_session=XXX'
app/src-tauri/src/cookie_store.rs 0 jdb '_jdb_session=abc'
app/src-tauri/src/cookie_store.rs 0 jdb '_jdb_session=abc'
app/src-tauri/src/cookie_store.rs 0 jdb '_jdb_session=XXX'
app/src-tauri/src/cookie_store.rs 2 cf 'cf_clearance=...'
app/src-tauri/src/cookie_store.rs 2 cf 'cf_clearance=XXX'
app/src-tauri/src/cookie_store.rs 2 cf 'cf_clearance=XXX'
app/src-tauri/src/cookie_store.rs 2 cf 'cf_clearance=xyz'
app/src-tauri/src/cookie_store.rs 2 cf 'cf_clearance=xyz'
app/src-tauri/src/cookie_store.rs 2 cf 'cf_clearance=xyz789'
app/src-tauri/src/cookie_store.rs 2 cf 'cf_clearance=XXX'
app/src-tauri/src/cookie_store.rs 2 cf 'cf_clearance=xyz'
app/src-tauri/src/cookie_store.rs 2 cf 'cf_clearance=xyz'
app/src-tauri/src/cookie_store.rs 2 cf 'cf_clearance=XXX'
app/src-tauri/src/cookie_store.rs 2 jdb '_jdb_session=...'
app/src-tauri/src/cookie_store.rs 2 jdb '_jdb_session=XXX'
app/src-tauri/src/cookie_store.rs 2 jdb '_jdb_session=XXX'
app/src-tauri/src/cookie_store.rs 2 jdb '_jdb_session=abc'
app/src-tauri/src/cookie_store.rs 2 jdb '_jdb_session=abc'
app/src-tauri/src/cookie_store.rs 2 jdb '_jdb_session=abc123'
app/src-tauri/src/cookie_store.rs 2 jdb '_jdb_session=XXX'
app/src-tauri/src/cookie_store.rs 2 jdb '_jdb_session=abc'
app/src-tauri/src/cookie_store.rs 2 jdb '_jdb_session=abc'
app/src-tauri/src/cookie_store.rs 2 jdb '_jdb_session=XXX'
app/src-tauri/src/lib.rs 0 cf 'cf_clearance=XXX'
app/src-tauri/src/lib.rs 0 jdb '_jdb_session=XXX'
app/src-tauri/src/lib.rs 2 cf 'cf_clearance=XXX'
app/src-tauri/src/lib.rs 2 jdb '_jdb_session=XXX'
app/src/App.svelte 0 cf 'cf_clearance=...'
app/src/App.svelte 0 jdb '_jdb_session=...'
app/src/App.svelte 2 cf 'cf_clearance=...'
app/src/App.svelte 2 jdb '_jdb_session=...'
prompt/security-audit-fixes-2026-07-28.md 0 hex 'urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a'
prompt/security-audit-fixes-2026-07-28.md 0 magnet 'magnet:?xt=urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a'
prompt/security-audit-fixes-2026-07-28.md 2 hex 'urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a'
prompt/security-audit-fixes-2026-07-28.md 2 magnet 'magnet:?xt=urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a'
scripts/build-release.ps1 0 hex 'urn:btih:0201592fDEADBEEF0201592fDEADBEEF02015920'
scripts/build-release.ps1 0 hex 'urn:btih:0201592fdeadbeef0201592fdeadbeef02015920'
scripts/build-release.ps1 0 hex 'urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF'
scripts/build-release.ps1 0 hex 'urn:btih:0201592f00000000000000000000000000000001'
scripts/build-release.ps1 0 hex 'urn:btih:0201592f00000000000000000000000000000002'
scripts/build-release.ps1 0 hex 'urn:btih:0000000000000000000000000000000000000001'
scripts/build-release.ps1 0 hex 'urn:btih:0000000000000000000000000000000000000002'
scripts/build-release.ps1 0 hex 'urn:btih:0000000000000000000000000000000000000003'
scripts/build-release.ps1 0 hex 'urn:btih:0123456789abcdef0123456789abcdef01234567'
scripts/build-release.ps1 0 hex 'urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
scripts/build-release.ps1 0 hex 'urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
scripts/build-release.ps1 0 hex 'urn:btih:cccccccccccccccccccccccccccccccccccccccc'
scripts/build-release.ps1 0 hex 'urn:btih:ABCDEF0123456789ABCDEF0123456789ABCDEF01'
scripts/build-release.ps1 0 hex 'urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a'
scripts/build-release.ps1 0 hex 'urn:btih:0201592fDEADBEEF0201592fDEADBEEF02015920'
scripts/build-release.ps1 0 hex 'urn:btih:0201592fdeadbeef0201592fdeadbeef02015920'
scripts/build-release.ps1 0 hex 'urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF'
scripts/build-release.ps1 0 hex 'urn:btih:0201592f00000000000000000000000000000001'
scripts/build-release.ps1 0 hex 'urn:btih:0201592f00000000000000000000000000000002'
scripts/build-release.ps1 0 hex 'urn:btih:0000000000000000000000000000000000000001'
scripts/build-release.ps1 0 hex 'urn:btih:0000000000000000000000000000000000000002'
scripts/build-release.ps1 0 hex 'urn:btih:0000000000000000000000000000000000000003'
scripts/build-release.ps1 0 hex 'urn:btih:0123456789abcdef0123456789abcdef01234567'
scripts/build-release.ps1 0 hex 'urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
scripts/build-release.ps1 0 hex 'urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
scripts/build-release.ps1 0 hex 'urn:btih:cccccccccccccccccccccccccccccccccccccccc'
scripts/build-release.ps1 0 hex 'urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a'
scripts/build-release.ps1 0 hex 'urn:btih:ABCDEF0123456789ABCDEF0123456789ABCDEF01'
scripts/build-release.ps1 0 b32 'urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF'
scripts/build-release.ps1 0 b32 'urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEF'
scripts/build-release.ps1 0 b32 'urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
scripts/build-release.ps1 0 b32 'urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
scripts/build-release.ps1 0 b32 'urn:btih:cccccccccccccccccccccccccccccccccccccccc'
scripts/build-release.ps1 0 b32 'urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
scripts/build-release.ps1 0 b32 'urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
scripts/build-release.ps1 0 b32 'urn:btih:cccccccccccccccccccccccccccccccc'
scripts/build-release.ps1 0 b32 'urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF'
scripts/build-release.ps1 0 b32 'urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
scripts/build-release.ps1 0 b32 'urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
scripts/build-release.ps1 0 b32 'urn:btih:cccccccccccccccccccccccccccccccccccccccc'
scripts/build-release.ps1 0 magnet 'magnet:?xt=urn:btih:0201592fDEADBEEF0201592fDEADBEEF02015920'
scripts/build-release.ps1 0 magnet 'magnet:?xt=urn:btih:0201592fdeadbeef0201592fdeadbeef02015920'
scripts/build-release.ps1 0 magnet 'magnet:?xt=urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF'
scripts/build-release.ps1 0 magnet 'magnet:?xt=urn:btih:0201592f00000000000000000000000000000001'
scripts/build-release.ps1 0 magnet 'magnet:?xt=urn:btih:0201592f00000000000000000000000000000002'
scripts/build-release.ps1 0 magnet 'magnet:?xt=urn:btih:0000000000000000000000000000000000000001'
scripts/build-release.ps1 0 magnet 'magnet:?xt=urn:btih:0000000000000000000000000000000000000002'
scripts/build-release.ps1 0 magnet 'magnet:?xt=urn:btih:0000000000000000000000000000000000000003'
scripts/build-release.ps1 0 magnet 'magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567'
scripts/build-release.ps1 0 magnet 'magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
scripts/build-release.ps1 0 magnet 'magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
scripts/build-release.ps1 0 magnet 'magnet:?xt=urn:btih:cccccccccccccccccccccccccccccccccccccccc'
scripts/build-release.ps1 0 magnet 'magnet:?xt=urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a'
scripts/build-release.ps1 0 magnet 'magnet:?xt=urn:btih:0123456789abcdef'
scripts/build-release.ps1 0 magnet 'magnet:?xt=urn:btih:ABCDEF0123456789'
scripts/build-release.ps1 0 magnet 'MAGNET:?xt=urn:btih:ABCDEF0123456789'
scripts/build-release.ps1 0 magnet 'MAGNET:?xt=urn:btih:ABCDEF0123456789ABCDEF0123456789ABCDEF01'
scripts/build-release.ps1 0 magnet 'magnet:?xt=urn:btih:fedcba9876543210'
scripts/build-release.ps1 0 cf 'cf_clearance=...'
scripts/build-release.ps1 0 cf 'cf_clearance=XXX'
scripts/build-release.ps1 0 cf 'cf_clearance=brand_new'
scripts/build-release.ps1 0 cf 'cf_clearance=clear_cf'
scripts/build-release.ps1 0 cf 'cf_clearance=e2e_cf_clearance'
scripts/build-release.ps1 0 cf 'cf_clearance=fresh'
scripts/build-release.ps1 0 cf 'cf_clearance=label_test_cf'
scripts/build-release.ps1 0 cf 'cf_clearance=paste_cf'
scripts/build-release.ps1 0 cf 'cf_clearance=preexisting_cf'
scripts/build-release.ps1 0 cf 'cf_clearance=regress_cf'
scripts/build-release.ps1 0 cf 'cf_clearance=resurrect_cf'
scripts/build-release.ps1 0 cf 'cf_clearance=xyz'
scripts/build-release.ps1 0 cf 'cf_clearance=xyz789'
scripts/build-release.ps1 0 jdb '_jdb_session=...'
scripts/build-release.ps1 0 jdb '_jdb_session=XXX'
scripts/build-release.ps1 0 jdb '_jdb_session=abc'
scripts/build-release.ps1 0 jdb '_jdb_session=abc123'
scripts/build-release.ps1 0 jdb '_jdb_session=brand_new'
scripts/build-release.ps1 0 jdb '_jdb_session=clear_me'
scripts/build-release.ps1 0 jdb '_jdb_session=e2e_jdb_session'
scripts/build-release.ps1 0 jdb '_jdb_session=keep_me_alive'
scripts/build-release.ps1 0 jdb '_jdb_session=keyring_only'
scripts/build-release.ps1 0 jdb '_jdb_session=label_test'
scripts/build-release.ps1 0 jdb '_jdb_session=new'
scripts/build-release.ps1 0 jdb '_jdb_session=older_keyring_value'
scripts/build-release.ps1 0 jdb '_jdb_session=paste_session'
scripts/build-release.ps1 0 jdb '_jdb_session=preexisting_session'
scripts/build-release.ps1 0 jdb '_jdb_session=regress_session'
scripts/build-release.ps1 0 jdb '_jdb_session=resurrect_me'
scripts/build-release.ps1 0 jdb '_jdb_session=xyz'
scripts/build-release.ps1 0 jdb '_jdb_session=paste_session'
scripts/build-release.ps1 0 jdb '_jdb_session=keep_me_alive'
scripts/build-release.ps1 0 jdb '_jdb_session=e2e_jdb_session'
scripts/build-release.ps1 0 jdb '_jdb_session=regress_session'
scripts/build-release.ps1 0 jdb '_jdb_session=preexisting_session'
scripts/build-release.ps1 0 jdb '_jdb_session=label_test'
scripts/build-release.ps1 0 jdb '_jdb_session=older_keyring_value'
scripts/build-release.ps1 0 jdb '_jdb_session=keyring_only'
scripts/build-release.ps1 0 jdb '_jdb_session=resurrect_me'
scripts/build-release.ps1 0 rd 'RD_API_TOKEN=abc-123'
scripts/build-release.ps1 2 hex 'urn:btih:0201592fDEADBEEF0201592fDEADBEEF02015920'
scripts/build-release.ps1 2 hex 'urn:btih:0201592fdeadbeef0201592fdeadbeef02015920'
scripts/build-release.ps1 2 hex 'urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF'
scripts/build-release.ps1 2 hex 'urn:btih:0201592f00000000000000000000000000000001'
scripts/build-release.ps1 2 hex 'urn:btih:0201592f00000000000000000000000000000002'
scripts/build-release.ps1 2 hex 'urn:btih:0000000000000000000000000000000000000001'
scripts/build-release.ps1 2 hex 'urn:btih:0000000000000000000000000000000000000002'
scripts/build-release.ps1 2 hex 'urn:btih:0000000000000000000000000000000000000003'
scripts/build-release.ps1 2 hex 'urn:btih:0123456789abcdef0123456789abcdef01234567'
scripts/build-release.ps1 2 hex 'urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
scripts/build-release.ps1 2 hex 'urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
scripts/build-release.ps1 2 hex 'urn:btih:cccccccccccccccccccccccccccccccccccccccc'
scripts/build-release.ps1 2 hex 'urn:btih:ABCDEF0123456789ABCDEF0123456789ABCDEF01'
scripts/build-release.ps1 2 hex 'urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a'
scripts/build-release.ps1 2 hex 'urn:btih:0201592fDEADBEEF0201592fDEADBEEF02015920'
scripts/build-release.ps1 2 hex 'urn:btih:0201592fdeadbeef0201592fdeadbeef02015920'
scripts/build-release.ps1 2 hex 'urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF'
scripts/build-release.ps1 2 hex 'urn:btih:0201592f00000000000000000000000000000001'
scripts/build-release.ps1 2 hex 'urn:btih:0201592f00000000000000000000000000000002'
scripts/build-release.ps1 2 hex 'urn:btih:0000000000000000000000000000000000000001'
scripts/build-release.ps1 2 hex 'urn:btih:0000000000000000000000000000000000000002'
scripts/build-release.ps1 2 hex 'urn:btih:0000000000000000000000000000000000000003'
scripts/build-release.ps1 2 hex 'urn:btih:0123456789abcdef0123456789abcdef01234567'
scripts/build-release.ps1 2 hex 'urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
scripts/build-release.ps1 2 hex 'urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
scripts/build-release.ps1 2 hex 'urn:btih:cccccccccccccccccccccccccccccccccccccccc'
scripts/build-release.ps1 2 hex 'urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a'
scripts/build-release.ps1 2 hex 'urn:btih:ABCDEF0123456789ABCDEF0123456789ABCDEF01'
scripts/build-release.ps1 2 b32 'urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF'
scripts/build-release.ps1 2 b32 'urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEF'
scripts/build-release.ps1 2 b32 'urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
scripts/build-release.ps1 2 b32 'urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
scripts/build-release.ps1 2 b32 'urn:btih:cccccccccccccccccccccccccccccccccccccccc'
scripts/build-release.ps1 2 b32 'urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
scripts/build-release.ps1 2 b32 'urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
scripts/build-release.ps1 2 b32 'urn:btih:cccccccccccccccccccccccccccccccc'
scripts/build-release.ps1 2 b32 'urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF'
scripts/build-release.ps1 2 b32 'urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
scripts/build-release.ps1 2 b32 'urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
scripts/build-release.ps1 2 b32 'urn:btih:cccccccccccccccccccccccccccccccccccccccc'
scripts/build-release.ps1 2 magnet 'magnet:?xt=urn:btih:0201592fDEADBEEF0201592fDEADBEEF02015920'
scripts/build-release.ps1 2 magnet 'magnet:?xt=urn:btih:0201592fdeadbeef0201592fdeadbeef02015920'
scripts/build-release.ps1 2 magnet 'magnet:?xt=urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF'
scripts/build-release.ps1 2 magnet 'magnet:?xt=urn:btih:0201592f00000000000000000000000000000001'
scripts/build-release.ps1 2 magnet 'magnet:?xt=urn:btih:0201592f00000000000000000000000000000002'
scripts/build-release.ps1 2 magnet 'magnet:?xt=urn:btih:0000000000000000000000000000000000000001'
scripts/build-release.ps1 2 magnet 'magnet:?xt=urn:btih:0000000000000000000000000000000000000002'
scripts/build-release.ps1 2 magnet 'magnet:?xt=urn:btih:0000000000000000000000000000000000000003'
scripts/build-release.ps1 2 magnet 'magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567'
scripts/build-release.ps1 2 magnet 'magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
scripts/build-release.ps1 2 magnet 'magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
scripts/build-release.ps1 2 magnet 'magnet:?xt=urn:btih:cccccccccccccccccccccccccccccccccccccccc'
scripts/build-release.ps1 2 magnet 'magnet:?xt=urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a'
scripts/build-release.ps1 2 magnet 'magnet:?xt=urn:btih:0123456789abcdef'
scripts/build-release.ps1 2 magnet 'magnet:?xt=urn:btih:ABCDEF0123456789'
scripts/build-release.ps1 2 magnet 'MAGNET:?xt=urn:btih:ABCDEF0123456789'
scripts/build-release.ps1 2 magnet 'MAGNET:?xt=urn:btih:ABCDEF0123456789ABCDEF0123456789ABCDEF01'
scripts/build-release.ps1 2 magnet 'magnet:?xt=urn:btih:fedcba9876543210'
scripts/build-release.ps1 2 cf 'cf_clearance=...'
scripts/build-release.ps1 2 cf 'cf_clearance=XXX'
scripts/build-release.ps1 2 cf 'cf_clearance=brand_new'
scripts/build-release.ps1 2 cf 'cf_clearance=clear_cf'
scripts/build-release.ps1 2 cf 'cf_clearance=e2e_cf_clearance'
scripts/build-release.ps1 2 cf 'cf_clearance=fresh'
scripts/build-release.ps1 2 cf 'cf_clearance=label_test_cf'
scripts/build-release.ps1 2 cf 'cf_clearance=paste_cf'
scripts/build-release.ps1 2 cf 'cf_clearance=preexisting_cf'
scripts/build-release.ps1 2 cf 'cf_clearance=regress_cf'
scripts/build-release.ps1 2 cf 'cf_clearance=resurrect_cf'
scripts/build-release.ps1 2 cf 'cf_clearance=xyz'
scripts/build-release.ps1 2 cf 'cf_clearance=xyz789'
scripts/build-release.ps1 2 jdb '_jdb_session=...'
scripts/build-release.ps1 2 jdb '_jdb_session=XXX'
scripts/build-release.ps1 2 jdb '_jdb_session=abc'
scripts/build-release.ps1 2 jdb '_jdb_session=abc123'
scripts/build-release.ps1 2 jdb '_jdb_session=brand_new'
scripts/build-release.ps1 2 jdb '_jdb_session=clear_me'
scripts/build-release.ps1 2 jdb '_jdb_session=e2e_jdb_session'
scripts/build-release.ps1 2 jdb '_jdb_session=keep_me_alive'
scripts/build-release.ps1 2 jdb '_jdb_session=keyring_only'
scripts/build-release.ps1 2 jdb '_jdb_session=label_test'
scripts/build-release.ps1 2 jdb '_jdb_session=new'
scripts/build-release.ps1 2 jdb '_jdb_session=older_keyring_value'
scripts/build-release.ps1 2 jdb '_jdb_session=paste_session'
scripts/build-release.ps1 2 jdb '_jdb_session=preexisting_session'
scripts/build-release.ps1 2 jdb '_jdb_session=regress_session'
scripts/build-release.ps1 2 jdb '_jdb_session=resurrect_me'
scripts/build-release.ps1 2 jdb '_jdb_session=xyz'
scripts/build-release.ps1 2 jdb '_jdb_session=paste_session'
scripts/build-release.ps1 2 jdb '_jdb_session=keep_me_alive'
scripts/build-release.ps1 2 jdb '_jdb_session=e2e_jdb_session'
scripts/build-release.ps1 2 jdb '_jdb_session=regress_session'
scripts/build-release.ps1 2 jdb '_jdb_session=preexisting_session'
scripts/build-release.ps1 2 jdb '_jdb_session=label_test'
scripts/build-release.ps1 2 jdb '_jdb_session=older_keyring_value'
scripts/build-release.ps1 2 jdb '_jdb_session=keyring_only'
scripts/build-release.ps1 2 jdb '_jdb_session=resurrect_me'
scripts/build-release.ps1 2 rd 'RD_API_TOKEN=abc-123'
tests/test_legacy_env.py 0 rd 'RD_API_TOKEN=abc-123'
tests/test_legacy_env.py 2 rd 'RD_API_TOKEN=abc-123'
tests/test_rd_outcome_log.py 0 hex 'urn:btih:0201592fDEADBEEF0201592fDEADBEEF02015920'
tests/test_rd_outcome_log.py 0 magnet 'magnet:?xt=urn:btih:0201592fDEADBEEF0201592fDEADBEEF02015920'
tests/test_rd_outcome_log.py 0 magnet 'magnet:?xt=urn:btih:ABCDEF0123456789'
tests/test_rd_outcome_log.py 2 hex 'urn:btih:0201592fDEADBEEF0201592fDEADBEEF02015920'
tests/test_rd_outcome_log.py 2 magnet 'magnet:?xt=urn:btih:0201592fDEADBEEF0201592fDEADBEEF02015920'
tests/test_rd_outcome_log.py 2 magnet 'magnet:?xt=urn:btih:ABCDEF0123456789'
tests/test_rd_outcome_log_e2e.py 0 hex 'urn:btih:0201592fdeadbeef0201592fdeadbeef02015920'
tests/test_rd_outcome_log_e2e.py 0 magnet 'magnet:?xt=urn:btih:0201592fdeadbeef0201592fdeadbeef02015920'
tests/test_rd_outcome_log_e2e.py 2 hex 'urn:btih:0201592fdeadbeef0201592fdeadbeef02015920'
tests/test_rd_outcome_log_e2e.py 2 magnet 'magnet:?xt=urn:btih:0201592fdeadbeef0201592fdeadbeef02015920'
tests/test_realdebrid_logging.py 0 hex 'urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF'
tests/test_realdebrid_logging.py 0 b32 'urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF'
tests/test_realdebrid_logging.py 0 magnet 'magnet:?xt=urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF'
tests/test_realdebrid_logging.py 0 jdb '_jdb_session=xyz'
tests/test_realdebrid_logging.py 2 hex 'urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF'
tests/test_realdebrid_logging.py 2 b32 'urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF'
tests/test_realdebrid_logging.py 2 magnet 'magnet:?xt=urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF'
tests/test_realdebrid_logging.py 2 jdb '_jdb_session=xyz'
tests/test_realdebrid_request.py 0 magnet 'magnet:?xt=urn:btih:0123456789abcdef'
tests/test_realdebrid_request.py 2 magnet 'magnet:?xt=urn:btih:0123456789abcdef'
tests/test_sidecar_protocol.py 0 hex 'urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a'
tests/test_sidecar_protocol.py 0 hex 'urn:btih:0201592f00000000000000000000000000000001'
tests/test_sidecar_protocol.py 0 hex 'urn:btih:0201592f00000000000000000000000000000002'
tests/test_sidecar_protocol.py 0 hex 'urn:btih:0000000000000000000000000000000000000001'
tests/test_sidecar_protocol.py 0 hex 'urn:btih:0000000000000000000000000000000000000002'
tests/test_sidecar_protocol.py 0 hex 'urn:btih:0000000000000000000000000000000000000003'
tests/test_sidecar_protocol.py 0 hex 'urn:btih:0123456789abcdef0123456789abcdef01234567'
tests/test_sidecar_protocol.py 0 hex 'urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
tests/test_sidecar_protocol.py 0 hex 'urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
tests/test_sidecar_protocol.py 0 hex 'urn:btih:cccccccccccccccccccccccccccccccccccccccc'
tests/test_sidecar_protocol.py 0 hex 'urn:btih:ABCDEF0123456789ABCDEF0123456789ABCDEF01'
tests/test_sidecar_protocol.py 0 b32 'urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
tests/test_sidecar_protocol.py 0 b32 'urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
tests/test_sidecar_protocol.py 0 b32 'urn:btih:cccccccccccccccccccccccccccccccccccccccc'
tests/test_sidecar_protocol.py 0 magnet 'magnet:?xt=urn:btih:0123456789abcdef'
tests/test_sidecar_protocol.py 0 magnet 'MAGNET:?xt=urn:btih:ABCDEF0123456789'
tests/test_sidecar_protocol.py 0 magnet 'magnet:?xt=urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a'
tests/test_sidecar_protocol.py 0 magnet 'magnet:?xt=urn:btih:0201592f00000000000000000000000000000001'
tests/test_sidecar_protocol.py 0 magnet 'magnet:?xt=urn:btih:0201592f00000000000000000000000000000002'
tests/test_sidecar_protocol.py 0 magnet 'magnet:?xt=urn:btih:0123456789abcdef'
tests/test_sidecar_protocol.py 0 magnet 'magnet:?xt=urn:btih:fedcba9876543210'
tests/test_sidecar_protocol.py 0 magnet 'magnet:?xt=urn:btih:0123456789abcdef'
tests/test_sidecar_protocol.py 0 magnet 'magnet:?xt=urn:btih:0000000000000000000000000000000000000001'
tests/test_sidecar_protocol.py 0 magnet 'magnet:?xt=urn:btih:0000000000000000000000000000000000000002'
tests/test_sidecar_protocol.py 0 magnet 'magnet:?xt=urn:btih:0000000000000000000000000000000000000003'
tests/test_sidecar_protocol.py 0 magnet 'magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567'
tests/test_sidecar_protocol.py 0 magnet 'magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
tests/test_sidecar_protocol.py 0 magnet 'magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
tests/test_sidecar_protocol.py 0 magnet 'magnet:?xt=urn:btih:cccccccccccccccccccccccccccccccccccccccc'
tests/test_sidecar_protocol.py 0 magnet 'MAGNET:?xt=urn:btih:ABCDEF0123456789ABCDEF0123456789ABCDEF01'
tests/test_sidecar_protocol.py 0 cf 'cf_clearance=xyz'
tests/test_sidecar_protocol.py 0 cf 'cf_clearance=fresh'
tests/test_sidecar_protocol.py 0 jdb '_jdb_session=abc'
tests/test_sidecar_protocol.py 0 jdb '_jdb_session=new'
tests/test_sidecar_protocol.py 0 jdb '_jdb_session=abc'
tests/test_sidecar_protocol.py 2 hex 'urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a'
tests/test_sidecar_protocol.py 2 hex 'urn:btih:0201592f00000000000000000000000000000001'
tests/test_sidecar_protocol.py 2 hex 'urn:btih:0201592f00000000000000000000000000000002'
tests/test_sidecar_protocol.py 2 hex 'urn:btih:0000000000000000000000000000000000000001'
tests/test_sidecar_protocol.py 2 hex 'urn:btih:0000000000000000000000000000000000000002'
tests/test_sidecar_protocol.py 2 hex 'urn:btih:0000000000000000000000000000000000000003'
tests/test_sidecar_protocol.py 2 hex 'urn:btih:0123456789abcdef0123456789abcdef01234567'
tests/test_sidecar_protocol.py 2 hex 'urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
tests/test_sidecar_protocol.py 2 hex 'urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
tests/test_sidecar_protocol.py 2 hex 'urn:btih:cccccccccccccccccccccccccccccccccccccccc'
tests/test_sidecar_protocol.py 2 hex 'urn:btih:ABCDEF0123456789ABCDEF0123456789ABCDEF01'
tests/test_sidecar_protocol.py 2 b32 'urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
tests/test_sidecar_protocol.py 2 b32 'urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
tests/test_sidecar_protocol.py 2 b32 'urn:btih:cccccccccccccccccccccccccccccccccccccccc'
tests/test_sidecar_protocol.py 2 magnet 'magnet:?xt=urn:btih:0123456789abcdef'
tests/test_sidecar_protocol.py 2 magnet 'MAGNET:?xt=urn:btih:ABCDEF0123456789'
tests/test_sidecar_protocol.py 2 magnet 'magnet:?xt=urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a'
tests/test_sidecar_protocol.py 2 magnet 'magnet:?xt=urn:btih:0201592f00000000000000000000000000000001'
tests/test_sidecar_protocol.py 2 magnet 'magnet:?xt=urn:btih:0201592f00000000000000000000000000000002'
tests/test_sidecar_protocol.py 2 magnet 'magnet:?xt=urn:btih:0123456789abcdef'
tests/test_sidecar_protocol.py 2 magnet 'magnet:?xt=urn:btih:fedcba9876543210'
tests/test_sidecar_protocol.py 2 magnet 'magnet:?xt=urn:btih:0123456789abcdef'
tests/test_sidecar_protocol.py 2 magnet 'magnet:?xt=urn:btih:0000000000000000000000000000000000000001'
tests/test_sidecar_protocol.py 2 magnet 'magnet:?xt=urn:btih:0000000000000000000000000000000000000002'
tests/test_sidecar_protocol.py 2 magnet 'magnet:?xt=urn:btih:0000000000000000000000000000000000000003'
tests/test_sidecar_protocol.py 2 magnet 'magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567'
tests/test_sidecar_protocol.py 2 magnet 'magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
tests/test_sidecar_protocol.py 2 magnet 'magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'
tests/test_sidecar_protocol.py 2 magnet 'magnet:?xt=urn:btih:cccccccccccccccccccccccccccccccccccccccc'
tests/test_sidecar_protocol.py 2 magnet 'MAGNET:?xt=urn:btih:ABCDEF0123456789ABCDEF0123456789ABCDEF01'
tests/test_sidecar_protocol.py 2 cf 'cf_clearance=xyz'
tests/test_sidecar_protocol.py 2 cf 'cf_clearance=fresh'
tests/test_sidecar_protocol.py 2 jdb '_jdb_session=abc'
tests/test_sidecar_protocol.py 2 jdb '_jdb_session=new'
tests/test_sidecar_protocol.py 2 jdb '_jdb_session=abc'

exec
/bin/bash -lc "python3 - <<'PY'
from pathlib import Path
import re, subprocess, urllib.parse
s=Path('scripts/build-release.ps1').read_text()
block=s[s.index('"'$AllowedLiterals = @('"'):s.index('\\n    )',s.index('"'$AllowedLiterals = @('"'))]
allowed=[]
for line in block.splitlines()[1:]:
 m=re.match(r\"\\s*'((?:["'^'"']|'')*)'\\s*,?\",line)
 if m: allowed.append(m.group(1).replace(\"''\", \"'\"))
print('allow entries',len(allowed),'unique',len(set(allowed)))
root=Path('.').resolve(); files=subprocess.check_output(['git','ls-files','-z']).decode().split('\\0')[:-1]
patterns=[r'urn:btih:[a-fA-F0-9]{40,}',r'urn:btih:[A-Z2-7]{32,}',r'urn:btmh:[a-fA-F0-9]{10,}',r'magnet:\\?xt=urn:bt[im]h:[a-zA-Z0-9]{16,}',r'cf_clearance\\s*=\\s*[\"\\']?[A-Za-z0-9_.~+/=-]{1,}',r'__cf_bm\\s*=\\s*[\"\\']?[A-Za-z0-9_.~+/=-]{1,}',r'_jdb_session\\s*=\\s*[\"\\']?[A-Za-z0-9_.~+/=-]{1,}',r'remember_me_token\\s*=\\s*[\"\\']?[A-Za-z0-9_.~+/=-]{1,}',r'Authorization:\\s*Bearer\\s+[A-Za-z0-9_.~+/=-]{8,}',r'Bearer\\s+[A-Za-z0-9_.~+/=-]{16,}',r'RD_API_TOKEN\\s*=\\s*[\"\\']?[A-Za-z0-9_-]{1,}']
skips={'.exe','.msi','.zip','.7z','.png','.ico','.icns','.dll'}
un=[]
for f in files:
 p=root/f
 if p.suffix.lower() in skips:continue
 b=p.read_bytes()
 for codec in ('ascii','utf-16le'):
  raw=b.decode(codec,'replace')
  for t in (raw,urllib.parse.unquote(raw)):
   for pat in patterns:
    for m in re.finditer(pat,t,re.I):
     if m.group(0) not in allowed: un.append((f,m.group(0)))
print('unexpected',len(un))
for x in sorted(set(un)):print(x)
PY
printf '\\n--- PATTERN CONSUMERS / PRODUCTION GRAMMAR ---\\n'
rg -n \"cf_clearance|__cf_bm|_jdb_session|remember_me_token|RD_API_TOKEN|Authorization|Bearer|magnet:|urn:btih|urn:btmh\" app sidecar realdebrid.py javdb_scraper.py tests --glob '*.{rs,py,ts,svelte}' | head -n 300" in /home/cy5407/javdb-magnet-workbench
 succeeded in 136ms:
allow entries 76 unique 67
unexpected 0

--- PATTERN CONSUMERS / PRODUCTION GRAMMAR ---
realdebrid.py:30:            raise RealDebridError("RD_API_TOKEN 未設定，請編輯 .env 檔案貼上 token")
realdebrid.py:32:        self.session.headers["Authorization"] = f"Bearer {token}"
realdebrid.py:91:        """產生 debug log 用的 kwargs；magnet / Authorization 全遮蔽，其餘欄位 80 字截斷。
realdebrid.py:94:        Bearer token 平時掛在 ``self.session.headers["Authorization"]``，不會出現
realdebrid.py:96:        ``headers=`` per-request override，這條 defense-in-depth 確保 Authorization
realdebrid.py:97:        值不會洩進 debug log（F-09 / Authorization redaction）。
realdebrid.py:177:    def add_magnet(self, magnet: str) -> str:
realdebrid.py:201:    def _extract_code(magnet: str) -> str | None:
realdebrid.py:205:        if not magnet:
realdebrid.py:231:    def pick_files(self, files: list[dict], strategy: str = "smart", magnet: str = "") -> list[int]:
realdebrid.py:255:    def _pick_smart(self, files: list[dict], magnet: str) -> list[int]:
realdebrid.py:300:        magnet: str,
realdebrid.py:380:    def _extract_magnet_hash(magnet: str) -> str:
realdebrid.py:406:        self, torrent_id: str, info: dict, strategy: str, magnet: str,
realdebrid.py:447:    def check_torrent(self, torrent_id: str, strategy: str = "smart", magnet: str = "") -> dict:
tests/test_javdb_scraper_fetch.py:38:          <a href="magnet:?xt=urn:btih:AAAA1111&dn=SNOS-192">
tests/test_javdb_scraper_fetch.py:51:          <a href="magnet:?xt=urn:btih:BBBB2222&dn=other">
tests/test_javdb_scraper_fetch.py:110:        self.assertTrue(m0["magnet"].startswith("magnet:?xt=urn:btih:AAAA1111"))
tests/test_javdb_scraper_fetch.py:116:        self.assertTrue(m1["magnet"].startswith("magnet:?xt=urn:btih:BBBB2222"))
tests/test_javdb_scraper_fetch.py:150:    and leak cf_clearance / _jdb_session cookies to the redirect target.
tests/test_javdb_scraper_fetch.py:201:                <a href="magnet:?xt=urn:btih:CAFEBABE"></a>
tests/test_javdb_scraper_fetch.py:216:        self.assertTrue(m["magnet"].startswith("magnet:?xt=urn:btih:CAFEBABE"))
tests/test_realdebrid_request.py:57:        self.assertEqual(rd.session.headers["Authorization"], "Bearer tok-xyz")
tests/test_realdebrid_request.py:206:        # of redirect-following so Authorization can't be auto-replayed to a
tests/test_realdebrid_request.py:207:        # rogue Location host. (requests strips Authorization on cross-host
tests/test_realdebrid_request.py:303:            self.assertEqual(self.rd.add_magnet("magnet:?xt=urn:btih:abc"), "TID-1")
tests/test_realdebrid_request.py:315:                    self.rd.add_magnet("magnet:?xt=urn:btih:abc")
tests/test_realdebrid_request.py:502:    SAMPLE_MAGNET = "magnet:?xt=urn:btih:0123456789abcdef&dn=SNOS-192"
tests/test_realdebrid_request.py:648:            out = self.rd.process_magnet("magnet:?xt=urn:sha1:zz&dn=no-btih")
tests/test_sidecar_protocol.py:45:        full = "magnet:?xt=urn:btih:0123456789abcdef&dn=test"
tests/test_sidecar_protocol.py:47:                         "magnet:?xt=urn:btih:01234567...")
tests/test_sidecar_protocol.py:50:        full = "MAGNET:?xt=urn:btih:ABCDEF0123456789&dn=test"
tests/test_sidecar_protocol.py:52:                         "magnet:?xt=urn:btih:ABCDEF01...")
tests/test_sidecar_protocol.py:58:        self.assertEqual(sd.redact_magnet("magnet:?xt=urn:other"), "magnet:...")
tests/test_sidecar_protocol.py:59:        self.assertEqual(sd.redact_magnet("MAGNET:?xt=urn:other"), "magnet:...")
tests/test_sidecar_protocol.py:68:            sd.extract_magnet_dn("magnet:?xt=urn:btih:abc&dn=SNOS-192"),
tests/test_sidecar_protocol.py:74:            sd.extract_magnet_dn("magnet:?xt=urn:btih:abc&dn=%5Bjavdb.com%5DSNOS-192"),
tests/test_sidecar_protocol.py:82:            sd.extract_magnet_dn("magnet:?xt=urn:btih:abc&dn=Hello+World"),
tests/test_sidecar_protocol.py:89:            sd.extract_magnet_dn("magnet:?dn=ABCD-123&xt=urn:btih:abc&tr=udp://t"),
tests/test_sidecar_protocol.py:95:            sd.extract_magnet_dn("magnet:?xt=urn:btih:abc&tr=udp://t"),
tests/test_sidecar_protocol.py:411:        # any HTTPS URL the caller supplies would leak `_jdb_session`
tests/test_sidecar_protocol.py:412:        # and `cf_clearance`. Reject anything that isn't javdb.com or
tests/test_sidecar_protocol.py:468:            "magnet:?xt=urn:btih:"
tests/test_sidecar_protocol.py:498:                         "magnet:?xt=urn:btih:01234567...")
tests/test_sidecar_protocol.py:586:        real_magnet = "magnet:?xt=urn:btih:c12fe1c06bba254a9dc9f519b335aa7c1367a88a&dn=REAL"
tests/test_sidecar_protocol.py:612:        self.assertTrue(resolve_resp["magnet"].startswith("magnet:"))
tests/test_sidecar_protocol.py:618:        btih_key = sd._magnet_dedupe_key("magnet:?xt=urn:btih:some-non-btih-string")
tests/test_sidecar_protocol.py:632:            "magnet:?xt=urn:btih:"
tests/test_sidecar_protocol.py:659:        self.state.magnets["h-1"] = "magnet:?xt=urn:btih:aaaa1111&dn=a"
tests/test_sidecar_protocol.py:660:        self.state.magnets["h-2"] = "magnet:?xt=urn:btih:bbbb2222&dn=b"
tests/test_sidecar_protocol.py:716:        m1 = "magnet:?xt=urn:btih:0201592f00000000000000000000000000000001"
tests/test_sidecar_protocol.py:717:        m2 = "magnet:?xt=urn:btih:0201592f00000000000000000000000000000002"
tests/test_sidecar_protocol.py:1168:    """Cookies live-update path. M9 added this so a cf_clearance refresh
tests/test_sidecar_protocol.py:1183:            "cookies": "_jdb_session=abc; cf_clearance=xyz; locale=zh",
tests/test_sidecar_protocol.py:1187:        self.assertEqual(state.cookies["_jdb_session"], "abc")
tests/test_sidecar_protocol.py:1188:        self.assertEqual(state.cookies["cf_clearance"], "xyz")
tests/test_sidecar_protocol.py:1193:        # cf_clearance overwrites the previous one cleanly.
tests/test_sidecar_protocol.py:1195:        state.cookies = {"_jdb_session": "old", "cf_clearance": "stale"}
tests/test_sidecar_protocol.py:1198:            "cookies": "_jdb_session=new; cf_clearance=fresh",
tests/test_sidecar_protocol.py:1202:            "_jdb_session": "new",
tests/test_sidecar_protocol.py:1203:            "cf_clearance": "fresh",
tests/test_sidecar_protocol.py:1208:        state.cookies = {"_jdb_session": "old"}
tests/test_sidecar_protocol.py:1218:        state.cookies = {"_jdb_session": "old"}
tests/test_sidecar_protocol.py:1243:            "cookies": "_jdb_session=abc",
tests/test_sidecar_protocol.py:1264:        state.magnets["h-1"] = "magnet:?xt=urn:btih:abc&dn=test"
tests/test_sidecar_protocol.py:1563:        m1 = "magnet:?xt=urn:btih:0123456789abcdef&dn=A"
tests/test_sidecar_protocol.py:1564:        m2 = "magnet:?xt=urn:btih:fedcba9876543210&dn=B"
tests/test_sidecar_protocol.py:1579:            resp["registered"][0]["magnet_redacted"].startswith("magnet:?xt=urn:btih:01234567")
tests/test_sidecar_protocol.py:1598:        m = "magnet:?xt=urn:btih:0123456789abcdef&dn=Same"
tests/test_sidecar_protocol.py:1617:        m_ok = "magnet:?xt=urn:btih:abc&dn=X"
tests/test_sidecar_protocol.py:1632:            "magnets": "magnet:?xt=urn:btih:abc",
tests/test_sidecar_protocol.py:1658:                "magnet:?xt=urn:btih:0000000000000000000000000000000000000001&dn=ABC-123",
tests/test_sidecar_protocol.py:1659:                "magnet:?xt=urn:btih:0000000000000000000000000000000000000002&dn=%5Bjavdb.com%5DDEF-456",
tests/test_sidecar_protocol.py:1660:                "magnet:?xt=urn:btih:0000000000000000000000000000000000000003",  # no dn
tests/test_sidecar_protocol.py:1674:        m = "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&dn=Cross"
tests/test_sidecar_protocol.py:1694:        magnet: existing returns its prior handle with deduped=True; new
tests/test_sidecar_protocol.py:1697:        m_old = "magnet:?xt=urn:btih:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa&dn=Old"
tests/test_sidecar_protocol.py:1698:        m_new = "magnet:?xt=urn:btih:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb&dn=New"
tests/test_sidecar_protocol.py:1729:        m_a = f"magnet:?xt=urn:btih:{hash40}&dn=Title-A"
tests/test_sidecar_protocol.py:1730:        m_b = f"magnet:?xt=urn:btih:{hash40}&dn=Title-B"
tests/test_sidecar_protocol.py:1755:        m_lo = f"magnet:?xt=urn:btih:{lower}&dn=lo"
tests/test_sidecar_protocol.py:1756:        m_up = f"magnet:?xt=urn:btih:{upper}&dn=up"
tests/test_sidecar_protocol.py:1775:            "magnets": [f"magnet:?xt=urn:btih:{h}&dn=N&tr=udp://t1"],
tests/test_sidecar_protocol.py:1779:            "magnets": [f"magnet:?dn=N&tr=udp://t1&xt=urn:btih:{h}"],
tests/test_sidecar_protocol.py:1792:            "magnets": [f"magnet:?xt=urn:btih:{h}&dn=lower"],
tests/test_sidecar_protocol.py:1796:            "magnets": [f"MAGNET:?xt=urn:btih:{h.upper()}&dn=upper"],
tests/test_sidecar_protocol.py:1808:        register an unusual magnet:?xt=urn:sha1:... etc."""
tests/test_sidecar_protocol.py:1811:            sd._magnet_dedupe_key("magnet:?xt=urn:btih:DEADBEEF&dn=A"),
tests/test_sidecar_protocol.py:1816:            sd._magnet_dedupe_key("  magnet:?xt=urn:sha1:abc  "),
tests/test_sidecar_protocol.py:1817:            "raw:magnet:?xt=urn:sha1:abc",
tests/test_sidecar_protocol.py:1828:        m = "magnet:?xt=urn:btih:cccccccccccccccccccccccccccccccccccccccc&dn=Recycle"
tests/test_sidecar_protocol.py:1859:        payload = ["magnet:?xt=urn:btih:abc"] * (sd.MAX_REGISTER_MAGNETS + 1)
tests/test_sidecar_protocol.py:1867:        long_uri = "magnet:?xt=urn:btih:abc&dn=" + "x" * (sd.MAX_MAGNET_URI_LEN + 10)
tests/test_sidecar_protocol.py:1869:                                               "magnets": [long_uri, "magnet:?xt=urn:btih:def"]})
tests/test_sidecar_protocol.py:1880:            "MAGNET:?xt=urn:btih:ABCDEF0123456789ABCDEF0123456789ABCDEF01"
tests/test_sidecar_protocol.py:1895:            "magnet:?xt=urn:btih:ABCDEF01...",
tests/test_sidecar_protocol.py:1908:        magnets = [{"magnet": f"magnet:?xt=urn:btih:{i:040x}",
tests/test_sidecar_protocol.py:1925:        short = "magnet:?xt=urn:btih:" + "a" * 40
tests/test_sidecar_protocol.py:1926:        long_ = "magnet:?xt=urn:btih:" + "a" * 40 + "&dn=" + "y" * (sd.MAX_MAGNET_URI_LEN + 100)
tests/test_sidecar_protocol.py:1951:        s.magnets["h-1"] = "magnet:?xt=urn:btih:" + "a" * 40
tests/test_rd_outcome_log_e2e.py:27:MAGNET = ("magnet:?xt=urn:btih:0201592fdeadbeef0201592fdeadbeef02015920"
tests/test_rd_outcome_log_e2e.py:164:def _register(sc: _Sidecar, magnet: str = MAGNET) -> str:
tests/test_rd_outcome_log_e2e.py:289:            gate = re.compile(r"magnet:\?xt|urn:btih", re.IGNORECASE)
tests/test_rd_outcome_log_e2e.py:316:        self.assertNotIn("Bearer", blob)
tests/test_sidecar_settings.py:387:    """Settings precedence flowing through cmd_rd_send_magnet:
tests/test_sidecar_settings.py:406:        state.magnets["h-1"] = "magnet:?xt=urn:btih:abc&dn=Y"
tests/test_legacy_env.py:30:            tmp.write("RD_API_TOKEN=abc-123\n")
tests/test_legacy_env.py:40:        self.assertEqual(env["RD_API_TOKEN"], "abc-123")
tests/test_core_logic.py:85:        magnet = "magnet:?xt=urn:btih:abc&dn=%5Bjavdb.com%5DSNOS-192"
tests/test_core_logic.py:89:        magnet = "magnet:?xt=urn:btih:abc&dn=snos192"
tests/test_core_logic.py:93:        magnet = "magnet:?xt=urn:btih:abc&dn=ipzz_851"
tests/test_core_logic.py:97:        magnet = "magnet:?xt=urn:btih:abc&dn=ipzz-851"
tests/test_core_logic.py:101:        magnet = "magnet:?xt=urn:btih:abc&dn=Some Random Anime Episode"
tests/test_core_logic.py:105:        magnet = "magnet:?xt=urn:btih:abc"
tests/test_core_logic.py:113:        magnet = "magnet:?xt=urn:btih:abc&dn=%5Bjavdb.com%5DABF-350.torrent"
tests/test_core_logic.py:221:        magnet = "magnet:?xt=urn:btih:abc&dn=%5Bjavdb.com%5DSNOS-192"
tests/test_core_logic.py:233:        magnet = "magnet:?xt=urn:btih:abc&dn=ABF-350"
tests/test_core_logic.py:244:        magnet = "magnet:?xt=urn:btih:abc&dn=SNOS-192"
tests/test_core_logic.py:254:        magnet = "magnet:?xt=urn:btih:abc&dn=Some Random Anime Episode 01.mkv"
tests/test_core_logic.py:265:        magnet = "magnet:?xt=urn:btih:abc&dn=SNOS-192"
tests/test_rd_outcome_log.py:7:     `magnet:\\?xt|urn:btih` 並預期零輸出。寫出那種字串會讓一條既有的驗收
tests/test_rd_outcome_log.py:27:FULL_MAGNET = "magnet:?xt=urn:btih:0201592fDEADBEEF0201592fDEADBEEF02015920&dn=SNOS-192"
tests/test_rd_outcome_log.py:113:        """redact_magnet() 的輸出本身就含 urn:btih，一樣會觸發既有 gate。"""
tests/test_rd_outcome_log.py:115:                                meta={"name": "magnet:?xt=urn:btih:0201592f..."})
tests/test_rd_outcome_log.py:142:        self.assertNotIn("urn:btih", "\n".join(captured).lower())
tests/test_rd_outcome_log.py:151:        self.assertNotRegex(self.raw(), r"(?i)urn:btih|magnet:\?xt")
tests/test_rd_outcome_log.py:597:M1 = "magnet:?xt=urn:btih:" + "1" * 40
tests/test_rd_outcome_log.py:598:M2 = "magnet:?xt=urn:btih:" + "2" * 40
tests/test_rd_outcome_log.py:599:M3 = "magnet:?xt=urn:btih:" + "3" * 40
tests/test_rd_outcome_log.py:846:        self.assertEqual(sd._btih8("magnet:?xt=urn:btih:ABCDEF0123456789"), "abcdef01")
tests/test_rd_outcome_log.py:850:        self.assertNotRegex(sd._btih8(M1), r"(?i)urn:btih|magnet:\?xt")
app/src-tauri/src/cookie_store.rs:5://! cookies (`_jdb_session` + `cf_clearance` + friends) into the same
app/src-tauri/src/cookie_store.rs:105:/// fail this check; a real `_jdb_session=...; cf_clearance=...` line
app/src-tauri/src/cookie_store.rs:151:                        # _jdb_session=XXX; cf_clearance=XXX; locale=zh\n\
app/src-tauri/src/cookie_store.rs:163:                      # _jdb_session=XXX; cf_clearance=XXX; locale=zh\n\
app/src-tauri/src/cookie_store.rs:165:                      _jdb_session=abc; cf_clearance=xyz; locale=zh\n";
app/src-tauri/src/cookie_store.rs:200:        assert!(check_cookies_format("_jdb_session=abc; cf_clearance=xyz").is_ok());
app/src-tauri/src/cookie_store.rs:210:        let real_paste = "_jdb_session=abc123; cf_clearance=xyz789; locale=zh";
app/src-tauri/src/cookie_store.rs:217:             # _jdb_session=XXX; cf_clearance=XXX; locale=zh\n\
app/src-tauri/src/cookie_store.rs:233:        let content = "_jdb_session=abc\ncf_clearance=xyz\nlocale=zh";
app/src-tauri/src/cookie_store.rs:236:            "_jdb_session=abc; cf_clearance=xyz; locale=zh",
app/src-tauri/src/cookie_store.rs:249:                             # _jdb_session=XXX; cf_clearance=XXX\n\
app/src-tauri/src/sidecar_manager.rs:110:                format!("rd_send_magnet: cache_wait must be a non-negative integer, got {n}")
app/src-tauri/src/sidecar_manager.rs:115:                "rd_send_magnet: cache_wait must be a non-negative integer, got {other}"
app/src-tauri/src/sidecar_manager.rs:121:            "rd_send_magnet: cache_wait={cache_wait} below floor {MIN_RD_CACHE_WAIT_SECS}s"
app/src-tauri/src/sidecar_manager.rs:126:            "rd_send_magnet: cache_wait={cache_wait} above ceiling {MAX_RD_CACHE_WAIT_SECS}s"
app/src-tauri/src/lib.rs:63:///      cf_clearance" path.
app/src-tauri/src/lib.rs:318:             # _jdb_session=XXX; cf_clearance=XXX; locale=zh\n\
app/src-tauri/src/secret_store.rs:4://! Credential, target name `JavDBMagnet/RD_API_TOKEN`). The `keyring` crate
app/src-tauri/src/secret_store.rs:18:const ACCOUNT: &str = "RD_API_TOKEN";
app/src-tauri/src/legacy_import.rs:11://! 1. `RD_API_TOKEN` from `.env` is routed via the `token: Option<String>`
app/src-tauri/src/legacy_import.rs:43:    /// are deliberately omitted.** `RD_API_TOKEN`'s presence is reported
app/src-tauri/src/legacy_import.rs:70:    /// Non-empty RD_API_TOKEN value, if any. Caller must hand this to
app/src-tauri/src/legacy_import.rs:73:    /// Recognized setting key names (incl. RD_API_TOKEN if present).
app/src-tauri/src/legacy_import.rs:85:/// - `RD_API_TOKEN`           → `ParsedEnv.token` (NOT in settings_patch)
app/src-tauri/src/legacy_import.rs:154:        "RD_API_TOKEN" => assign_token(key, unquoted, out),
app/src-tauri/src/legacy_import.rs:320:                .filter(|k| k != "RD_API_TOKEN")
app/src-tauri/src/legacy_import.rs:570:            "magnet": "magnet:?xt=urn:btih:DEADBEEF",
app/src-tauri/src/legacy_import.rs:571:            "magnet_uri": "magnet:?xt=urn:btih:CAFEBABE",
app/src-tauri/src/legacy_import.rs:572:            "full_magnet": "magnet:?xt=urn:btih:0001",
app/src-tauri/src/legacy_import.rs:587:        assert!(!serialized.contains("urn:btih"), "leak: {serialized}");
app/src-tauri/src/legacy_import.rs:601:            {"torrent_id": "A", "code": "X-1", "magnet": "magnet:?xt=urn:btih:aaa"},
app/src-tauri/src/legacy_import.rs:602:            {"torrent_id": "B", "code": "X-2", "magnet": "magnet:?xt=urn:btih:bbb"},
app/src-tauri/src/legacy_import.rs:612:        assert!(!raw.contains("magnet:"), "leak: {raw}");
app/src-tauri/src/legacy_import.rs:614:        assert!(!raw.contains("urn:btih"), "leak: {raw}");
app/src-tauri/src/legacy_import.rs:668:                {"torrent_id": "T1", "magnet": "magnet:?xt=urn:btih:LEAKABLE"}
app/src-tauri/src/legacy_import.rs:688:        assert!(!raw.contains("urn:btih"), "{raw}");
app/src-tauri/src/legacy_import.rs:689:        assert!(!raw.contains("magnet:"), "{raw}");
sidecar/sidecar.py:80:    r"^magnet:\?xt=urn:btih:([a-fA-F0-9]{1,128})",
sidecar/sidecar.py:86:    """Keep `magnet:?xt=urn:btih:` + first 8 hex chars + `...`; drop the rest."""
sidecar/sidecar.py:91:        return f"magnet:?xt=urn:btih:{m.group(1)[:8]}..."
sidecar/sidecar.py:92:    return "magnet:..." if uri.lower().startswith("magnet:") else "<not-a-magnet>"
sidecar/sidecar.py:99:    output: that returns `magnet:?xt=urn:btih:<8hex>...`, and the release
sidecar/sidecar.py:101:    grep the whole log directory for exactly `magnet:\\?xt|urn:btih` expecting
sidecar/sidecar.py:192:        # urn:btih:<hex>, otherwise the trimmed full string. This makes
sidecar/sidecar.py:304:_BTIH_PREFIX = "urn:btih:"
sidecar/sidecar.py:315:      - parameter order — `magnet:?dn=...&xt=urn:btih:HASH` vs
sidecar/sidecar.py:316:        `magnet:?xt=urn:btih:HASH&dn=...`
sidecar/sidecar.py:322:    super-linear), find an `xt` value of the form `urn:btih:<hex>`,
sidecar/sidecar.py:324:    parsed (e.g. v2 `urn:btmh:` or a malformed string that somehow
sidecar/sidecar.py:373:    would leak `_jdb_session` + `cf_clearance` to the attacker's
sidecar/sidecar.py:549:        if not full.lower().startswith("magnet:"):
sidecar/sidecar.py:653:    Each input must start with `magnet:`; non-magnets are returned in
sidecar/sidecar.py:679:        if not s.lower().startswith("magnet:"):
sidecar/sidecar.py:726:    """Update state.cookies at runtime so a cf_clearance refresh doesn't
sidecar/sidecar.py:885:        raise RealDebridError("RD_API_TOKEN not configured")
app/src/lib/magnetUtils.test.ts:28:  magnet_redacted: "magnet:?xt=urn:btih:0201592f...",
app/src/lib/scraper.test.ts:24:    magnet_redacted: "magnet:?xt=urn:btih:00000000...",
app/src/lib/scraper.test.ts:63:      "magnet:?xt=urn:btih:abc&dn=A",
app/src/lib/scraper.test.ts:64:      "  magnet:?xt=urn:btih:def&dn=B",
app/src/lib/scraper.test.ts:67:      "magnet:?xt=urn:btih:abc&dn=A", // dup
app/src/lib/scraper.test.ts:72:      "magnet:?xt=urn:btih:abc&dn=A",
app/src/lib/scraper.test.ts:73:      "magnet:?xt=urn:btih:def&dn=B",
app/src/lib/scraper.test.ts:78:    expect(parseMagnetBatch("MAGNET:?xt=urn:btih:abc")).toEqual([
app/src/lib/scraper.test.ts:79:      "MAGNET:?xt=urn:btih:abc",
app/src/lib/types.ts:85:  /** True if .env contains a non-empty RD_API_TOKEN. Value is NOT exposed. */
tests/test_realdebrid_logging.py:8:`data["magnet"][:80]`, which always covers `magnet:?xt=urn:btih:` (20 chars)
tests/test_realdebrid_logging.py:51:        "magnet:?xt=urn:btih:DEADBEEFDEADBEEFDEADBEEFDEADBEEFDEADBEEF"
tests/test_realdebrid_logging.py:81:        self.assertNotIn("urn:btih", log_text)
tests/test_realdebrid_logging.py:129:    The Bearer token normally lives on ``session.headers["Authorization"]`` so
tests/test_realdebrid_logging.py:132:    still mask ``Authorization`` / ``Proxy-Authorization`` / ``Cookie`` so the
tests/test_realdebrid_logging.py:137:    SESSION_COOKIE = "SECRETSESSION_DO_NOT_LEAK_jdb_session=xyz"
tests/test_realdebrid_logging.py:143:            "headers": {"Authorization": f"Bearer {self.BEARER_TOKEN}"},
tests/test_realdebrid_logging.py:147:        self.assertEqual(out, {"headers": {"Authorization": "<redacted>"}})
tests/test_realdebrid_logging.py:153:                "Proxy-Authorization": "Basic SECRETPROXYCREDS_DO_NOT_LEAK",
tests/test_realdebrid_logging.py:161:        self.assertEqual(out["headers"]["Proxy-Authorization"], "<redacted>")
tests/test_realdebrid_logging.py:169:            "headers": {"authorization": f"Bearer {self.BEARER_TOKEN}"},
tests/test_realdebrid_logging.py:177:            "data": {"magnet": "magnet:?xt=urn:btih:DEAD", "files": "all"},
tests/test_realdebrid_logging.py:178:            "headers": {"Authorization": "Bearer LEAKABLE"},
tests/test_realdebrid_logging.py:182:        self.assertEqual(out["headers"]["Authorization"], "<redacted>")
app/src/lib/rdPriority.test.ts:25:  magnet_redacted: "magnet:?xt=urn:btih:0201592f...",
app/src/lib/scraper.ts:152: * anything that doesn't start with `magnet:`. Sidecar dedupes again on
app/src/lib/scraper.ts:156:  return parseBatchWithFilter(raw, /^magnet:/i);
app/src/lib/rdSender.test.ts:744:    original: "magnet:?xt=urn:btih:abc",
app/src/App.svelte:440:          ? "你貼的看起來是 JavDB 網址（http/https）。請改貼到「1. 擷取 Magnet」分頁的批次擷取欄位；本欄只接受 magnet:?xt=... 開頭的磁力連結。"
app/src/App.svelte:441:          : "未偵測到有效磁力連結（必須以 magnet: 開頭）",
app/src/App.svelte:1321:      // to the running sidecar, so a cf_clearance refresh takes effect
app/src/App.svelte:1470:    // cf_clearance, not setting up for the first time).
app/src/App.svelte:1947:                  ／RD_API_TOKEN：{legacyPreview.has_rd_token ? "✓（會移入憑證管理員）" : "（無）"}
app/src/App.svelte:2155:              cf_clearance 過期時：點下方「建立 cookies.txt 範本」→ 編輯範本貼入新 cookie →
app/src/App.svelte:2257:            placeholder="_jdb_session=...; cf_clearance=...; locale=zh"
app/src/App.svelte:2364:      已有 <code>magnet:?xt=...</code> 連結時可貼在這裡。加入後切到
app/src/App.svelte:2374:      placeholder="magnet:?xt=urn:btih:...&#10;magnet:?xt=urn:btih:..."
app/src-tauri/src/commands.rs:108:/// inputs that didn't start with `magnet:`.
app/src-tauri/src/commands.rs:704:            "ignored legacy RD_API_TOKEN: value does not match the Real-Debrid \
app/src-tauri/src/commands.rs:712:/// Hand a recovered `RD_API_TOKEN` to the credential store and ask the
app/src-tauri/src/commands.rs:747:            .push(format!("{}/.env (RD_API_TOKEN)", src.display()));
app/src-tauri/src/commands.rs:1148:const COOKIES_TEMPLATE: &str = "# JavDBMagnet cookies.txt\n# ================================================\n#\n# 把你的 JavDB 登入 cookie 貼到本檔最後一行，存檔時請選 UTF-8 編碼。\n# 至少要包含這 2 個 cookie:\n#   _jdb_session=...   (登入 session)\n#   cf_clearance=...   (Cloudflare 通行證)\n#\n# === 方法 A: 瀏覽器 DevTools Network 分頁 (推薦) ===\n#   1. 用瀏覽器 (Edge / Chrome / Firefox 都可) 登入 https://javdb.com\n#   2. 按 F12 開啟 DevTools\n#   3. 切換到「Network」(網路) 分頁\n#   4. 按 F5 重新整理頁面\n#   5. 點清單最上面那筆 request (網址通常是 javdb.com/)\n#   6. 右側找到「Request Headers」找到 \"Cookie:\" 那行\n#   7. 複製整行值 (不要包含 \"Cookie: \" 前綴), 貼到本檔最後一行\n#\n# === 方法 B: Application 分頁 (更直觀但要拼接) ===\n#   1. F12 → Application → Storage → Cookies → https://javdb.com\n#   2. 找出 _jdb_session 與 cf_clearance 兩個欄位的 Value\n#   3. 自行拼成: _jdb_session=...; cf_clearance=...; locale=zh\n#\n# === 範例 (請把 XXX 換成你的真實值, 不要直接貼這行) ===\n# _jdb_session=XXX; cf_clearance=XXX; locale=zh\n#\n# === 安全提醒 ===\n#   - cookies.txt 含登入憑證, 請勿分享, 勿同步雲端\n#   - cf_clearance 約幾小時過期 → 重做上面任一方法更新即可\n#   - 失效徵兆: app 內按「開始擷取」看到「Cloudflare 阻擋」訊息\n#\n# === 在下面貼上你的 cookie 整行 ===\n\n";
app/src-tauri/src/commands.rs:1290:                {"handle_id": "h-1", "magnet": "magnet:?xt=urn:btih:aaa"},
app/src-tauri/src/commands.rs:1299:        assert_eq!(lines, vec!["magnet:?xt=urn:btih:aaa".to_string()]);
app/src-tauri/src/commands.rs:1359:        fs::write(&path, "_jdb_session=new; cf_clearance=fresh\n").unwrap();
app/src-tauri/src/commands.rs:1417:        assert!(text.contains("_jdb_session"));
app/src-tauri/src/commands.rs:1418:        assert!(text.contains("cf_clearance"));
app/src-tauri/src/commands.rs:1420:        assert!(text.contains("_jdb_session=XXX"));
app/src-tauri/src/commands.rs:1440:        assert!(err.contains("RD_API_TOKEN"), "got: {err}");
app/src-tauri/src/commands.rs:1486:            "\n  _jdb_session=abc; cf_clearance=xyz  \n",
app/src-tauri/src/commands.rs:1489:        assert_eq!(v, "_jdb_session=abc; cf_clearance=xyz");
app/src-tauri/src/commands.rs:1597:            "_jdb_session=e2e_jdb_session; cf_clearance=e2e_cf_clearance; locale=zh";
app/src-tauri/src/commands.rs:1634:            "_jdb_session=regress_session; cf_clearance=regress_cf; locale=zh";
app/src-tauri/src/commands.rs:1675:            "_jdb_session=preexisting_session; cf_clearance=preexisting_cf";
app/src-tauri/src/commands.rs:1682:                             # _jdb_session=XXX; cf_clearance=XXX; locale=zh\n\
app/src-tauri/src/commands.rs:1717:            "_jdb_session=label_test; cf_clearance=label_test_cf",
app/src-tauri/src/commands.rs:1737:        crate::cookie_store::set_cookies("_jdb_session=older_keyring_value")
app/src-tauri/src/commands.rs:1743:            "_jdb_session=brand_new; cf_clearance=brand_new",
app/src-tauri/src/commands.rs:1768:            "  _jdb_session=paste_session; cf_clearance=paste_cf  \n",
app/src-tauri/src/commands.rs:1774:            "_jdb_session=paste_session; cf_clearance=paste_cf",
app/src-tauri/src/commands.rs:1804:        let preexisting = "_jdb_session=keep_me_alive";
app/src-tauri/src/commands.rs:1820:        let preexisting = "_jdb_session=keep_me_alive";
app/src-tauri/src/commands.rs:1846:        crate::cookie_store::set_cookies("_jdb_session=clear_me; cf_clearance=clear_cf")
app/src-tauri/src/commands.rs:1852:            "_jdb_session=clear_me; cf_clearance=clear_cf",
app/src-tauri/src/commands.rs:1881:        crate::cookie_store::set_cookies("_jdb_session=keyring_only").expect("seed");
app/src-tauri/src/commands.rs:1902:                             # _jdb_session=XXX; cf_clearance=XXX; locale=zh\n\
app/src-tauri/src/commands.rs:1925:        let secret = "_jdb_session=resurrect_me; cf_clearance=resurrect_cf";
app/src/App.test.ts:70:        magnet_redacted: "magnet:?xt=urn:btih:abc\u2026",
app/src/App.test.ts:77:  rd_send_magnet: () =>
app/src/App.test.ts:84:          original: "magnet:?xt=urn:btih:abc",
app/src/App.test.ts:155:        magnet_redacted: "magnet:?xt=urn:btih:aaa…",
app/src/App.test.ts:161:        magnet_redacted: "magnet:?xt=urn:btih:bbb…",
app/src/App.test.ts:168:  const magnetBox = screen.getByPlaceholderText(/magnet:\?xt=urn:btih:/) as HTMLTextAreaElement;
app/src/App.test.ts:170:    target: { value: "magnet:?xt=urn:btih:aaa\nmagnet:?xt=urn:btih:bbb" },
app/src/App.test.ts:175:      magnets: ["magnet:?xt=urn:btih:aaa", "magnet:?xt=urn:btih:bbb"],
app/src/App.test.ts:201:  const magnetBox = screen.getByPlaceholderText(/magnet:\?xt=urn:btih:/) as HTMLTextAreaElement;
app/src/App.test.ts:202:  await fireEvent.input(magnetBox, { target: { value: "magnet:?xt=urn:btih:abc" } });
app/src/App.test.ts:206:      magnets: ["magnet:?xt=urn:btih:abc"],
app/src/App.test.ts:441:                original: "magnet:?xt=urn:btih:aaa",
app/src/App.test.ts:561:                original: "magnet:?xt=urn:btih:aaa",
app/src/App.test.ts:992:        { handle_id: "web-h-1", name: "ABC-123", size: "1 GB", tags: ["HD"], date: "2026-01-01", magnet_redacted: "magnet:?xt=urn:btih:web1…" },
app/src/App.test.ts:1047:          magnet_redacted: "magnet:?xt=urn:btih:abc…",
app/src/App.test.ts:1062:        tags: [], date: "2026-01-01", magnet_redacted: "magnet:?xt=urn:btih:abc…",
app/src/App.test.ts:1154:    magnet_redacted: "magnet:?xt=urn:btih:rd…",
app/src/App.test.ts:1280:          magnet_redacted: "magnet:?xt=urn:btih:rd…",
app/src-tauri/src/pending.rs:254:        assert!(!raw.contains("magnet:"), "pending file leaked magnet: prefix");

exec
/bin/bash -lc "sed -n '80,135p' app/src-tauri/src/cookie_store.rs | nl -ba -v80; sed -n '125,180p' app/src-tauri/src/legacy_import.rs | nl -ba -v125; sed -n '1,90p' app/src-tauri/src/secret_store.rs | nl -ba; sed -n '285,355p' sidecar/sidecar.py | nl -ba -v285; printf '\\n--- COMMIT MESSAGE ---\\n'; git show -s --format=fuller 3f55ec0; printf '\\n--- RECENT HISTORY ---\\n'; git log --oneline --decorate -8" in /home/cy5407/javdb-magnet-workbench
 succeeded in 0ms:
    80	/// `KeyringSandbox` in `commands.rs::tests_cookies_e2e`.
    81	///
    82	/// This is only HALF of a clear. The plaintext `cookies.txt` must go too:
    83	/// [`crate::migrate_cookies_from_file`] promotes any surviving file back
    84	/// into the keyring on the next handshake, so a keyring-only delete
    85	/// silently undoes itself. `clear_cookies` owns that ordering.
    86	pub fn delete_cookies() -> Result<(), String> {
    87	    let e = entry()?;
    88	    delete_internal(&e)
    89	}
    90	
    91	fn delete_internal(e: &keyring::Entry) -> Result<(), String> {
    92	    match e.delete_credential() {
    93	        Ok(_) | Err(keyring::Error::NoEntry) => Ok(()),
    94	        Err(err) => Err(format!("keyring delete: {err}")),
    95	    }
    96	}
    97	
    98	/// Does the supplied cookies.txt content look like an actual JavDB session
    99	/// (vs. just the template scaffold)? Used by the migration path so a
   100	/// freshly-created template — which contains only comments + an empty
   101	/// trailing line — doesn't clobber a valid keyring entry on next launch.
   102	///
   103	/// Heuristic: at least one non-empty, non-comment line that contains
   104	/// `=`. The template's only `=` lines are commented sample lines and
   105	/// fail this check; a real `_jdb_session=...; cf_clearance=...` line
   106	/// passes it.
   107	pub fn file_has_real_cookies(content: &str) -> bool {
   108	    content
   109	        .lines()
   110	        .map(str::trim)
   111	        .filter(|line| !line.is_empty() && !line.starts_with('#'))
   112	        .any(|line| line.contains('='))
   113	}
   114	
   115	/// Pull the actual cookie pairs out of a cookies.txt that may also contain
   116	/// the template scaffold's comment headers.
   117	///
   118	/// Windows Credential Manager caps generic-credential blobs at roughly
   119	/// 2.5 KiB — a real-world cookies.txt with all of the template's Chinese
   120	/// instructions is ~2.5 KiB by itself, so writing the raw file content
   121	/// to the keyring deterministically fails on real user installs (silently,
   122	/// because `eprintln!` from a window-mode exe goes nowhere visible).
   123	/// We avoid the cliff entirely by storing ONLY the lines that look like
   124	/// cookie pairs (non-empty, non-comment, contains `=`), joined with the
   125	/// header-style `"; "` separator so `parse_cookie_string` on the sidecar
   126	/// side sees the same shape it would from a fresh `Cookie:` header paste.
   127	///
   128	/// Returns an empty string if no real cookie lines are present (caller
   129	/// should already have gated on [`file_has_real_cookies`], but the empty
   130	/// fallback keeps the contract clean).
   131	pub fn extract_cookie_lines(content: &str) -> String {
   132	    content
   133	        .lines()
   134	        .map(str::trim)
   135	        .filter(|line| !line.is_empty() && !line.starts_with('#') && line.contains('='))
   125	/// Strip a single matched pair of surrounding `"` or `'` quotes. Returns
   126	/// the input unchanged if it isn't quoted (or is too short to be a quoted
   127	/// pair).
   128	fn strip_matched_quotes(v: &str) -> &str {
   129	    if v.len() < 2 {
   130	        return v;
   131	    }
   132	    let bytes = v.as_bytes();
   133	    let first = bytes[0];
   134	    let last = bytes[v.len() - 1];
   135	    let quoted = (first == b'"' && last == b'"') || (first == b'\'' && last == b'\'');
   136	    if quoted {
   137	        &v[1..v.len() - 1]
   138	    } else {
   139	        v
   140	    }
   141	}
   142	
   143	/// Route one `KEY=value` pair from a `.env` file to the right bucket
   144	/// (`rd` / `ui`), the token slot, or the warnings list. Pulled out of
   145	/// `parse_env` to keep its cognitive complexity in check.
   146	fn dispatch_env_entry(
   147	    key: &str,
   148	    unquoted: &str,
   149	    rd: &mut Map<String, Value>,
   150	    ui: &mut Map<String, Value>,
   151	    out: &mut ParsedEnv,
   152	) {
   153	    match key {
   154	        "RD_API_TOKEN" => assign_token(key, unquoted, out),
   155	        "RD_FILE_PICK" => assign_str_setting(key, unquoted, "file_pick", rd, out),
   156	        "RD_MIN_SIZE_MB" => assign_u32_setting(key, unquoted, "min_size_mb", rd, out),
   157	        "RD_WAIT_TIMEOUT" => out
   158	            .warnings
   159	            .push("ignored deprecated key: RD_WAIT_TIMEOUT".to_string()),
   160	        "RD_CACHE_WAIT" => assign_u32_setting(key, unquoted, "cache_wait_seconds", rd, out),
   161	        "UI_SCALE" => assign_str_setting(key, unquoted, "scale", ui, out),
   162	        "UI_THEME" => assign_str_setting(key, unquoted, "theme", ui, out),
   163	        other => {
   164	            out.warnings.push(format!("ignored unknown key: {other}"));
   165	        }
   166	    }
   167	}
   168	
   169	fn assign_token(env_key: &str, value: &str, out: &mut ParsedEnv) {
   170	    if value.is_empty() {
   171	        return;
   172	    }
   173	    out.token = Some(value.to_string());
   174	    out.recognized_keys.push(env_key.to_string());
   175	}
   176	
   177	fn assign_str_setting(
   178	    env_key: &str,
   179	    value: &str,
   180	    target_key: &str,
     1	//! Secret storage for the RD API token.
     2	//!
     3	//! On Windows the token lives in the Windows Credential Manager (Generic
     4	//! Credential, target name `JavDBMagnet/RD_API_TOKEN`). The `keyring` crate
     5	//! routes the same calls to the right backend on macOS / Linux so the rest
     6	//! of the app stays platform-agnostic.
     7	//!
     8	//! Why a credential store, not `settings.json`:
     9	//! - settings.json is plaintext + cloud-syncable + likely to be screenshotted
    10	//!   in support tickets;
    11	//! - the OS credential store is the well-trodden path for Windows desktop
    12	//!   apps, plays nicely with corporate policy, and survives an app reinstall.
    13	//!
    14	//! Out of scope here: JavDB cookies (still plaintext at
    15	//! `<data_dir>/cookies.txt` for M5; DPAPI move tracked for M6/M7).
    16	
    17	const SERVICE: &str = "JavDBMagnet";
    18	const ACCOUNT: &str = "RD_API_TOKEN";
    19	
    20	/// Real-Debrid API tokens are short ASCII-alphanumeric strings (52 chars
    21	/// at time of writing). Cap at 255 chars so a paste of surrounding HTML,
    22	/// a stray newline, or a stale OAuth blob never reaches the credential
    23	/// store (F-04). Owned by this module so every caller — `rd_save_token`,
    24	/// `import_rd_token`, `migrate_legacy_token` — applies the same rule and
    25	/// no path can pollute the keyring with a malformed value.
    26	///
    27	/// !!! KEEP IN SYNC with the Python sidecar's `_RD_TOKEN_MAX_LEN`
    28	/// (`sidecar/sidecar.py`). Same rule applied on both sides of the IPC.
    29	pub const RD_TOKEN_MAX_LEN: usize = 255;
    30	
    31	/// Pure-function format check. Empty strings are not valid here; callers
    32	/// that want to support "clear" must check `is_empty()` themselves before
    33	/// asking — `set_rd_token("")` is the documented clear gesture.
    34	///
    35	/// !!! KEEP IN SYNC with the Python sidecar's `_is_valid_rd_token`
    36	/// (`sidecar/sidecar.py`). The two implementations MUST accept and
    37	/// reject exactly the same strings — handshake (Python) and credential
    38	/// store (Rust) both gate on this rule, and drift would let a token
    39	/// pass one side but fail the other (silent UX breakage where the
    40	/// keyring holds a value the sidecar then drops at handshake time, or
    41	/// vice versa). If you change the rule, update both files in the same
    42	/// commit and re-run both test suites.
    43	pub fn is_valid_rd_token(token: &str) -> bool {
    44	    !token.is_empty()
    45	        && token.len() <= RD_TOKEN_MAX_LEN
    46	        && token.chars().all(|c| c.is_ascii_alphanumeric())
    47	}
    48	
    49	/// Stable error code returned when a non-empty token fails `is_valid_rd_token`.
    50	/// Mirrors the sidecar's bad_request envelope so the frontend's error
    51	/// classifier can use one string everywhere.
    52	pub const RD_TOKEN_FORMAT_ERR: &str = "rd_token_format_invalid";
    53	
    54	fn entry() -> Result<keyring::Entry, String> {
    55	    keyring::Entry::new(SERVICE, ACCOUNT).map_err(|e| format!("keyring entry: {e}"))
    56	}
    57	
    58	/// Persist a token. Empty string is treated as "delete". Non-empty input
    59	/// is validated against `is_valid_rd_token` BEFORE the keyring is touched
    60	/// so a malformed value can never overwrite a previously-good credential.
    61	/// Returns `Err(RD_TOKEN_FORMAT_ERR.into())` if validation fails.
    62	pub fn set_rd_token(token: &str) -> Result<(), String> {
    63	    if !token.is_empty() && !is_valid_rd_token(token) {
    64	        return Err(RD_TOKEN_FORMAT_ERR.to_string());
    65	    }
    66	    let e = entry()?;
    67	    if token.is_empty() {
    68	        return delete_internal(&e);
    69	    }
    70	    e.set_password(token).map_err(|err| format!("keyring set: {err}"))
    71	}
    72	
    73	/// Read the token. `Ok(None)` if no entry has been stored yet.
    74	pub fn get_rd_token() -> Result<Option<String>, String> {
    75	    let e = entry()?;
    76	    match e.get_password() {
    77	        Ok(s) => Ok(Some(s)),
    78	        Err(keyring::Error::NoEntry) => Ok(None),
    79	        Err(err) => Err(format!("keyring get: {err}")),
    80	    }
    81	}
    82	
    83	pub fn delete_rd_token() -> Result<(), String> {
    84	    let e = entry()?;
    85	    delete_internal(&e)
    86	}
    87	
    88	fn delete_internal(e: &keyring::Entry) -> Result<(), String> {
    89	    match e.delete_credential() {
    90	        Ok(_) | Err(keyring::Error::NoEntry) => Ok(()),
   285	        warnings.append(dict(_HANDSHAKE_TOKEN_WARNING))
   286	        rd_token = ""
   287	    state.rd_token = rd_token
   288	
   289	    settings_raw = req.get("settings")
   290	    state.settings = _normalize_runtime_settings(settings_raw)
   291	
   292	    paths_raw = req.get("paths")
   293	    state.paths = paths_raw if isinstance(paths_raw, dict) else {}
   294	
   295	    state.handshake_done = True
   296	    extra = {"warnings": warnings} if warnings else None
   297	    return _ok(req, extra)
   298	
   299	
   300	def cmd_ping(state: DaemonState, req: dict) -> dict:
   301	    return _ok(req, {"uptime_seconds": int(time.time() - state.start_time)})
   302	
   303	
   304	_BTIH_PREFIX = "urn:btih:"
   305	_HEX_CHARS = frozenset("0123456789abcdef")
   306	
   307	
   308	def _magnet_dedupe_key(full: str) -> str:
   309	    """Identity key for magnet dedupe.
   310	
   311	    Two magnet URIs that point at the same BitTorrent v1 content should
   312	    hash to the same key even if they differ in:
   313	      - `dn=` (display name) — JavDB sometimes serves different `dn`s
   314	        for the same hash
   315	      - parameter order — `magnet:?dn=...&xt=urn:btih:HASH` vs
   316	        `magnet:?xt=urn:btih:HASH&dn=...`
   317	      - tracker (`tr=`) list — different mirrors of the same content
   318	      - hash case — some sources emit uppercase hex
   319	
   320	    Strategy: parse the magnet URI with stdlib `urllib.parse` (avoids
   321	    unbounded regex over the raw string, which Sonar flags as
   322	    super-linear), find an `xt` value of the form `urn:btih:<hex>`,
   323	    lowercase the hex and return `btih:<hex>`. If no BTIH can be
   324	    parsed (e.g. v2 `urn:btmh:` or a malformed string that somehow
   325	    slipped past upstream validation), fall back to `raw:` + trimmed full
   326	    string so fallback key and btih key live in different namespaces and
   327	    hostile non-btih inputs cannot forge collisions.
   328	    """
   329	    stripped = full.strip()
   330	    parsed = urllib.parse.urlparse(stripped)
   331	    for xt in urllib.parse.parse_qs(
   332	        parsed.query, keep_blank_values=True
   333	    ).get("xt", []):
   334	        lower = xt.lower()
   335	        if not lower.startswith(_BTIH_PREFIX):
   336	            continue
   337	        hash_hex = lower[len(_BTIH_PREFIX):]
   338	        if hash_hex and all(c in _HEX_CHARS for c in hash_hex):
   339	            return "btih:" + hash_hex
   340	    return "raw:" + stripped if stripped else ""
   341	
   342	
   343	
   344	
   345	def _intern_magnet(state: DaemonState, full: str) -> tuple[str, bool]:
   346	    """Look up `full` in the reverse table (keyed by the normalized
   347	    dedupe key, not the raw string); reuse the existing handle_id if
   348	    found, otherwise allocate a new one. Returns `(handle_id, deduped)`.
   349	    Updates BOTH the forward (`state.magnets`) and reverse
   350	    (`state.magnet_to_handle`) maps so every caller sees the same
   351	    identity.
   352	    """
   353	    key = _magnet_dedupe_key(full)
   354	    existing = state.magnet_to_handle.get(key)
   355	    if existing is not None:

--- COMMIT MESSAGE ---
commit 3f55ec090baf2c2c1c937c105a5f355c759d1014
Author:     cy5407 <cy5407@gmail.com>
AuthorDate: Sun Aug 2 17:11:09 2026 +0800
Commit:     cy5407 <cy5407@gmail.com>
CommitDate: Sun Aug 2 17:11:09 2026 +0800

    fix: 修復 release blocker 與七項掃描缺口，並讓這道 gate 首次可實際執行
    
    外部審查指出 07d9b93 含一個必定失敗的 blocker。七項全部成立。最重要的改變不是
    逐項修補，而是**裝了 pwsh 7.6.4，讓這支腳本第一次被真正執行過**——先前所有
    PowerShell 改動都只做過括號配對與 Python 等價模型，那擋不住語意錯誤。
    
    P1 blocker：$ManifestPath 宣告被我刪掉
      07d9b93 插入建置後驗證時，替換錨點含該宣告而新內容沒放回。腳本開了
      Set-StrictMode，於是 PyInstaller、cargo、掃描、zip、hash 全跑完之後才在寫
      manifest 時炸掉。已放回，並用 pwsh 的 AST 走訪確認全檔無未宣告變數。
    
    P1 percent-encoded magnet 穿透
      production 把 `magnet:?xt=urn%3Abtih%3A<40hex>` 正規化成 `btih:<hash>` 並
      intern（實跑 _magnet_dedupe_key 確認），掃描則零命中。source 與 binary 兩處
      都補上 percent-decoded 掃描 pass。
    
    P1 scanner grammar 比 production 窄
      secret_store.rs 接受 1–255 ASCII 英數；legacy_import.rs 會 trim `=` 兩側空白
      並去引號；parse_cookie_string 對每組 `k = v` 做 trim。掃描原本要求 20 字元、
      不容空白與引號、Bearer 字元集漏掉 token68 的 .~+/=。全部對齊到 production
      的 grammar，長度下限降到 1。代價是 31 個短 fixture 開始命中——已逐一列入
      allowlist（全是 XXX / ... / brand_new / clear_me 這類佔位符）。
      這裡刻意不自訂「比較合理」的長度門檻：掃描器比 parser 窄，就是有紀錄的洞。
    
    P1 clean-tree guard 可被 git 設定繞過
      status.showUntrackedFiles=no 會讓 untracked 檔完全消失，而未追蹤的頂層模組
      可以被 PyInstaller 收進 exe。改為顯式 --untracked-files=all。
      另檢查 git ls-files -v 的 assume-unchanged / skip-worktree 標記，有即拒絕
      ——那些檔案磁碟內容可與 index 不同而 status 仍為空。
    
    P1 「前後各驗一次」不等於 immutable snapshot
      中途修改再還原，兩端都乾淨、HEAD 也沒動，但 artifact 已來自 transient
      source。manifest 欄位由 before_and_after_build 改為 pre_and_post_build_clean，
      並註明證明更強的性質需要從 immutable checkout 建置，本 pipeline 尚未做到。
      這是把宣稱降到與實際驗證相符，不是修掉該問題。
    
    P2 讀檔成功不等於解碼成功
      Get-Content -Raw 由執行環境決定編碼，且 PS 5.1 與 7 預設不同；無 BOM 的
      UTF-16LE 會解成字元間夾 NUL，I/O 成功、eligible=scanned，而 regex 看不到
      連續 ASCII。改為讀 bytes，比照 binary scan 以 UTF-8 與 UTF-16LE 兩種解碼掃描。
    
    P3 bare URN 缺右邊界 —— 我第一次的修法是錯的，靠實跑才發現
      先用 `{40}(?![a-fA-F0-9])`，結果 42 碼字串變成**完全不匹配**（lookahead 在
      每個起點都失敗），比原本「匹配前 40 碼」更糟。改為貪婪 `{40,}`：整段被吃掉，
      凡長於 allowlist 字面量者即為相異值而失敗。base32 同理。
      這個錯誤讀程式碼看不出來，是 Red 測試跑出來的。
    
    新增 -AuditOnly：只跑 source scan 即結束，不建置。審查者建議的 audit-only
    模式，也是我唯一能對這道 gate 做 Red 測試的方法（完整 release 要先花數分鐘
    建置才會走到掃描）。掃描邏輯抽成 Invoke-SourceSecretScan，定義前移。
    
    實測（pwsh 7.6.4，本輪首次真正執行）：
    - 正向：111 檔掃描、426 個 allowlisted 命中、exit 0
    - 反向：10 種繞過形式各植入一次，10/10 全數攔下——percent-encoded、大寫
      MAGNET、base32、btmh、帶空白引號的 RD token、短 token、帶空白 cookie、
      token68 Bearer、40hex+2、以及 production 檔案內的 cookie
    - 每次紅測後還原並複驗掃描回到乾淨
    
    Gate 不變：pytest 415、vitest 255、svelte-check 189 files 0/0。
    
    Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>

--- RECENT HISTORY ---
3f55ec0 (HEAD -> master) fix: 修復 release blocker 與七項掃描缺口，並讓這道 gate 首次可實際執行
07d9b93 (origin/master, origin/HEAD) fix: 修正 Codex review 指出的兩項殘留缺口
2b4c2c5 fix: 修正 release 機密掃描的七項可繞過路徑
a9a1c83 fix: 收緊 magnet 掃描 pattern，讓三份文件不必再整檔豁免
80d5880 (origin/fix/source-secret-scan-coverage) fix: 原始碼機密掃描改為全量掃描，消除空掃描仍回報通過的缺陷
3991662 fix: 修正 Windows 上的測試 teardown 與驗證腳本缺陷，同步建置文件
f33dc75 build: 新增 Windows 建置驗證腳本與交接文件
84e811e fix: 修正跨批次 metadata 與設定邊界

exec
/bin/bash -lc "rg -n \"def parse_cookie_string|parse_cookie_string\" sidecar/sidecar.py && sed -n '210,270p' sidecar/sidecar.py | nl -ba -v210; rg -n \"_is_valid_rd_token|RD_TOKEN\" sidecar/sidecar.py | head -30; sed -n '190,230p' sidecar/sidecar.py | nl -ba -v190; printf '\\n--- REGEX PREFIX COUNTEREXAMPLES (.NET-compatible via Python) ---\\n'; python3 - <<'PY'
import re
cases={
'cookie':(r'cf_clearance\\s*=\\s*[\"\\']?[A-Za-z0-9_.~+/=-]{1,}','cf_clearance=XXX%REALSECRET'),
'rd':(r'RD_API_TOKEN\\s*=\\s*[\"\\']?[A-Za-z0-9_-]{1,}','RD_API_TOKEN=abc-123.EXTRA'),
'bearer':(r'Bearer\\s+[A-Za-z0-9_.~+/=-]{16,}','Bearer AAAAAAAAAAAAAAAA%REAL'),
}
for n,(p,s) in cases.items():
 m=re.search(p,s,re.I);print(n,repr(m.group(0)) if m else None)
PY
printf '\\n--- MASK SCOPE PROBE VIA STATIC AST-LIKE EXTRACT ---\\n'; python3 - <<'PY'
from pathlib import Path
s=Path('scripts/build-release.ps1').read_text()
for v in ('SourceHits','SourceEligible','SourceScanned','SourceAllowed'):
 print(v,[i+1 for i,l in enumerate(s.splitlines()) if '"'$'"'+v in l])
PY" in /home/cy5407/javdb-magnet-workbench
 succeeded in 0ms:
147:def parse_cookie_string(s: str) -> dict[str, str]:
270:        state.cookies = parse_cookie_string(cookies_raw)
733:      - parsing reuses ``parse_cookie_string`` (already drops CR/LF
737:    beyond what ``parse_cookie_string`` already enforces because the
752:    state.cookies = parse_cookie_string(cookies)
   210	        # Monotonic per-session counter so two fetches of the same JAV code
   211	        # stay distinguishable in the log.
   212	        self.fetch_seq = 0
   213	        self.start_time = time.time()
   214	
   215	
   216	# ---------------------------------------------------------------------------
   217	# Envelopes
   218	# ---------------------------------------------------------------------------
   219	
   220	def _ok(req: dict, extra: dict | None = None) -> dict:
   221	    out = {"ok": True, "request_id": req.get("request_id")}
   222	    if extra:
   223	        out.update(extra)
   224	    return out
   225	
   226	
   227	def _err(req: dict, code: str, message: str, internal: str = "") -> dict:
   228	    return {
   229	        "ok": False,
   230	        "request_id": req.get("request_id"),
   231	        "error": {"code": code, "message": message, "internal": internal},
   232	    }
   233	
   234	
   235	# ---------------------------------------------------------------------------
   236	# Command handlers
   237	# ---------------------------------------------------------------------------
   238	
   239	def cmd_hello(state: DaemonState, req: dict) -> dict:
   240	    requested = req.get("protocol_version")
   241	    if requested != PROTOCOL_VERSION:
   242	        return _err(
   243	            req,
   244	            "protocol_mismatch",
   245	            f"sidecar v{PROTOCOL_VERSION} vs requested v{requested}",
   246	        )
   247	    return _ok(req, {
   248	        "protocol_version": PROTOCOL_VERSION,
   249	        "sidecar_version": SIDECAR_VERSION,
   250	        "engine": "curl_cffi",
   251	    })
   252	
   253	
   254	_HANDSHAKE_TOKEN_WARNING = {
   255	    "code": "rd_token_format_invalid",
   256	    # Generic message — never echoes the dirty value (M1). Covers both
   257	    # the wrong-type case (e.g. hand-crafted handshake with rd_token=123)
   258	    # and the wrong-shape case (e.g. dirty keyring blob with punctuation).
   259	    "message": (
   260	        "rd_token from handshake was not a well-formed Real-Debrid "
   261	        "token (expected a string of <=255 ASCII alphanumeric chars); "
   262	        "the value has been dropped and no token is configured"
   263	    ),
   264	}
   265	
   266	
   267	def cmd_handshake(state: DaemonState, req: dict) -> dict:
   268	    cookies_raw = req.get("cookies")
   269	    if isinstance(cookies_raw, str):
   270	        state.cookies = parse_cookie_string(cookies_raw)
280:    elif isinstance(raw, str) and _is_valid_rd_token(raw):
963:# !!! KEEP IN SYNC with the Rust `secret_store::RD_TOKEN_MAX_LEN`
966:_RD_TOKEN_MAX_LEN = 255
969:def _is_valid_rd_token(token: str) -> bool:
985:        0 < len(token) <= _RD_TOKEN_MAX_LEN
1007:    if not _is_valid_rd_token(token):
   190	        # Reverse table: dedupe_key -> handle_id. The dedupe key is
   191	        # `btih:<lowercase-hash>` when the magnet has a parseable
   192	        # urn:btih:<hex>, otherwise the trimmed full string. This makes
   193	        # two magnets with the same BTIH but different `dn=`, parameter
   194	        # order, or hash case map to the SAME handle — without it, the
   195	        # "send to RD" path could still double-bill for cosmetically
   196	        # different but semantically identical magnets.
   197	        self.magnet_to_handle: dict[str, str] = {}
   198	        # handle_id -> the JavDB row as scraped (name/size/tags/date/code) plus
   199	        # its rank inside the group it came from. Kept ONLY so the outcome log
   200	        # can record what the row looked like at send time; nothing in the
   201	        # protocol reads it back. Group ranks have to be computed here at fetch
   202	        # time because only the rows the user actually sends reach the log —
   203	        # the group can never be reconstructed afterwards.
   204	        self.magnet_meta: dict[str, dict] = {}
   205	        # Manual rows can share a BTIH/handle with a JavDB row. Keep their
   206	        # sparse metadata separately so starting a new web batch can downgrade
   207	        # a surviving manual-only handle after the old web groups disappear.
   208	        self.manual_meta: dict[str, dict] = {}
   209	        self.active_scrape_batch_id: str | None = None
   210	        # Monotonic per-session counter so two fetches of the same JAV code
   211	        # stay distinguishable in the log.
   212	        self.fetch_seq = 0
   213	        self.start_time = time.time()
   214	
   215	
   216	# ---------------------------------------------------------------------------
   217	# Envelopes
   218	# ---------------------------------------------------------------------------
   219	
   220	def _ok(req: dict, extra: dict | None = None) -> dict:
   221	    out = {"ok": True, "request_id": req.get("request_id")}
   222	    if extra:
   223	        out.update(extra)
   224	    return out
   225	
   226	
   227	def _err(req: dict, code: str, message: str, internal: str = "") -> dict:
   228	    return {
   229	        "ok": False,
   230	        "request_id": req.get("request_id"),

--- REGEX PREFIX COUNTEREXAMPLES (.NET-compatible via Python) ---
cookie 'cf_clearance=XXX'
rd 'RD_API_TOKEN=abc-123'
bearer 'Bearer AAAAAAAAAAAAAAAA'

--- MASK SCOPE PROBE VIA STATIC AST-LIKE EXTRACT ---
SourceHits [305, 355, 360, 364, 711]
SourceEligible [306, 312, 374, 375, 716]
SourceScanned [307, 340, 371, 374, 375, 377, 717]
SourceAllowed [308, 354, 377, 718]

exec
/bin/bash -lc "sed -n '135,175p' sidecar/sidecar.py | nl -ba -v135; sed -n '720,765p' sidecar/sidecar.py | nl -ba -v720; sed -n '955,995p' sidecar/sidecar.py | nl -ba -v955; git ls-files -v | awk '"'$1 ~ /''^[a-z]$/ || $1=="S" {print}'"' | head -20; git check-ignore -v release docs/reviews 2>/dev/null || true" in /home/cy5407/javdb-magnet-workbench
 succeeded in 0ms:
   135	    """
   136	    if not uri:
   137	        return ""
   138	    parsed = urllib.parse.urlparse(uri)
   139	    values = urllib.parse.parse_qs(
   140	        parsed.query, keep_blank_values=True
   141	    ).get("dn")
   142	    if not values:
   143	        return ""
   144	    return values[0]
   145	
   146	
   147	def parse_cookie_string(s: str) -> dict[str, str]:
   148	    """Parse `k=v; k=v` cookie header into dict. Empty/whitespace returns {}.
   149	
   150	    Pairs containing CR or LF are dropped: a stray newline inside a
   151	    cookie value is the classic shape for HTTP-header injection / response
   152	    splitting (CWE-93). The desktop app never legitimately needs a
   153	    multi-line cookie, so refusing is safer than escaping (F-05).
   154	    """
   155	    if not s or not s.strip():
   156	        return {}
   157	    out: dict[str, str] = {}
   158	    for pair in s.split(";"):
   159	        pair = pair.strip()
   160	        if "=" not in pair:
   161	            continue
   162	        if "\r" in pair or "\n" in pair:
   163	            continue
   164	        key, value = pair.split("=", 1)
   165	        out[key.strip()] = value.strip()
   166	    return out
   167	
   168	
   169	# ---------------------------------------------------------------------------
   170	# State
   171	# ---------------------------------------------------------------------------
   172	
   173	class DaemonState:
   174	    """In-memory state for a sidecar daemon process.
   175	
   720	    if new_settings is not None:
   721	        state.settings = _normalize_runtime_settings(new_settings)
   722	    return _ok(req)
   723	
   724	
   725	def cmd_set_cookies(state: DaemonState, req: dict) -> dict:
   726	    """Update state.cookies at runtime so a cf_clearance refresh doesn't
   727	    require an app restart.
   728	
   729	    Mirrors ``cmd_rd_set_token``:
   730	      - handshake gate (F-17): refuse until handshake is established.
   731	      - ``cookies`` may be ``null`` / ``""`` to clear, or a non-empty
   732	        ``Cookie:``-header-style string (``k=v; k=v``) to set.
   733	      - parsing reuses ``parse_cookie_string`` (already drops CR/LF
   734	        pairs per F-05).
   735	
   736	    The full cookies blob is opaque text — we don't size-validate here
   737	    beyond what ``parse_cookie_string`` already enforces because the
   738	    Rust caller (``save_cookies`` / ``migrate_cookies_now``) applies
   739	    the [`cookie_store::COOKIES_MAX_BYTES`] cap before crossing IPC.
   740	    """
   741	    if not state.handshake_done:
   742	        return _err(req, "bad_request", "handshake required before set_cookies")
   743	    cookies = req.get("cookies")
   744	    if cookies is None:
   745	        state.cookies = {}
   746	        return _ok(req, {"set": False})
   747	    if not isinstance(cookies, str):
   748	        return _err(req, "bad_request", "cookies must be a string when provided")
   749	    if not cookies.strip():
   750	        state.cookies = {}
   751	        return _ok(req, {"set": False})
   752	    state.cookies = parse_cookie_string(cookies)
   753	    return _ok(req, {"set": bool(state.cookies)})
   754	
   755	
   756	def cmd_cancel(state: DaemonState, req: dict) -> dict:
   757	    # M3 sidecar processes commands synchronously; nothing is "in flight"
   758	    # that an out-of-band cancel could interrupt. Acknowledge so the Rust
   759	    # caller's protocol-level cancel path does not error. Real cancellation
   760	    # arrives with a future async-aware refactor.
   761	    return _ok(req)
   762	
   763	
   764	# ---------------------------------------------------------------------------
   765	# M5: Real-Debrid commands
   955	            "username": info.get("username", ""),
   956	            "type": info.get("type", ""),
   957	            "expiration": info.get("expiration", ""),
   958	            "points": info.get("points", 0),
   959	        }
   960	    })
   961	
   962	
   963	# !!! KEEP IN SYNC with the Rust `secret_store::RD_TOKEN_MAX_LEN`
   964	# (`app/src-tauri/src/secret_store.rs`). Same rule applied on both
   965	# sides of the IPC.
   966	_RD_TOKEN_MAX_LEN = 255
   967	
   968	
   969	def _is_valid_rd_token(token: str) -> bool:
   970	    """Real-Debrid API tokens are 52 ASCII alphanumeric characters at
   971	    time of writing. Bound to <=255 chars / ASCII-alnum so a paste of
   972	    surrounding HTML, a stray newline, or a stale OAuth blob can't be
   973	    stored as a token (F-04).
   974	
   975	    !!! KEEP IN SYNC with the Rust ``secret_store::is_valid_rd_token``
   976	    (``app/src-tauri/src/secret_store.rs``). The two implementations
   977	    MUST accept and reject exactly the same strings — handshake
   978	    (Python) and credential store (Rust) both gate on this rule, and
   979	    drift would let a token pass one side but fail the other (silent
   980	    UX breakage where the keyring holds a value the sidecar then drops
   981	    at handshake time, or vice versa). If you change the rule, update
   982	    both files in the same commit and re-run both test suites.
   983	    """
   984	    return (
   985	        0 < len(token) <= _RD_TOKEN_MAX_LEN
   986	        and all(c.isascii() and c.isalnum() for c in token)
   987	    )
   988	
   989	
   990	def cmd_rd_set_token(state: DaemonState, req: dict) -> dict:
   991	    """Update state.rd_token at runtime. Used by the settings UI after the
   992	    user pastes / changes a token, so a sidecar restart isn't needed."""
   993	    # F-17: align with cmd_rd_send_magnet — require handshake first so a
   994	    # caller cannot push tokens before the protocol is established.
   995	    if not state.handshake_done:

exec
/bin/bash -lc "sed -n '280,325p' README.md | nl -ba -v280; sed -n '1,90p' docs/platform/windows-build.md | nl -ba; cat app/package.json; printf '\\n--- FILE ENCODINGS / LARGE FILES ---\\n'; git ls-files -z | xargs -0 file --mime | sed -n '1,160p'; printf '\\n--- largest tracked non-skipped ---\\n'; git ls-files -z | xargs -0 stat -c '%s %n' | sort -nr | head -30" in /home/cy5407/javdb-magnet-workbench
 succeeded in 5ms:
60841441 sidecar.exe
5334016 javdbmagnet.exe
144711 app/src-tauri/Cargo.lock
116905 app/src/App.svelte
106073 app/package-lock.json
98451 app/src-tauri/icons/icon.icns
91866 tests/test_sidecar_protocol.py
86642 app/src-tauri/icons/icon.ico
83005 docs/architecture/contracts/rust-backend.md
75298 app/src-tauri/src/commands.rs
64676 docs/architecture/contracts/app-svelte.md
63963 legacy/javdb_magnet_gui.py
62270 docs/architecture/contracts/frontend-lib.md
60176 docs/superpowers/specs/2026-05-10-tauri-rewrite-design.md
54949 app/src/App.test.ts
53691 sidecar/sidecar.py
40295 tests/test_rd_outcome_log.py
38753 docs/architecture/contracts/python-legacy.md
38703 scripts/build-release.ps1
33125 tests/test_realdebrid_request.py
27717 docs/architecture/contracts/sidecar-runtime.md
27594 docs/architecture/function-contracts.md
26520 tests/test_sidecar_settings.py
26457 app/src-tauri/src/legacy_import.rs
25192 app/src/lib/rdSender.test.ts
24798 prompt/security-audit-fixes-2026-07-28.md
23673 implementation-notes.md
21989 realdebrid.py
18370 README.md
18102 tests/test_rd_outcome_log_e2e.py

exec
/bin/bash -lc 'git diff --check 3f55ec0''^ 3f55ec0; python3 -m pytest -q tests/test_sidecar_protocol.py -q' in /home/cy5407/javdb-magnet-workbench
 exited 1 in 0ms:
/usr/bin/python3: No module named pytest

exec
/bin/bash -lc ".venv/bin/python - <<'PY'
import re
from sidecar.sidecar import parse_cookie_string
print(parse_cookie_string('cf_clearance=XXX%actual-secret'))
secret='RD_API_TOKEN=SECRETTOKEN'
b=b'\\xfe\\xff'+secret.encode('utf-16-be')
pat=re.compile(r'RD_API_TOKEN\\s*=\\s*[\"\\']?[A-Za-z0-9_-]{1,}',re.I)
for label,enc in [('ASCII','ascii'),('UTF-16LE','utf-16-le'),('UTF-16BE','utf-16-be')]:
 text=b.decode(enc,errors='replace')
 print(label, bool(pat.search(text)), repr(text[:30]))
PY
printf '\\n--- changed line anchors ---\\n'; nl -ba scripts/build-release.ps1 | sed -n '146,160p;300,312p;624,632p;704,721p'; printf '\\n--- status unchanged ---\\n'; git status --short" in /home/cy5407/javdb-magnet-workbench
 succeeded in 40ms:
{'cf_clearance': 'XXX%actual-secret'}
ASCII False '��\x00R\x00D\x00_\x00A\x00P\x00I\x00_\x00T\x00O\x00K\x00E\x00N\x00=\x00S'
UTF-16LE False '\ufffe刀䐀开䄀倀䤀开吀伀䬀䔀一㴀匀䔀䌀刀䔀吀吀伀䬀䔀一'
UTF-16BE True '\ufeffRD_API_TOKEN=SECRETTOKEN'

--- changed line anchors ---
   146	#     `let path = format!("HKCU\\...\\{}", token);` later passed to
   147	#     `RegOpenKeyExW`), which would otherwise sail past an ASCII-only
   148	#     scan even though the secret material is plainly readable in a
   149	#     hex dump.
   150	# Running both passes is cheap (two regex sweeps over the same byte
   151	# blob); failing to do it would silently halve the scan's coverage.
   152	$Encodings = @(
   153	    @{ label = 'ASCII';      encoding = [System.Text.Encoding]::ASCII },
   154	    @{ label = 'UTF-16LE';   encoding = [System.Text.Encoding]::Unicode }
   155	)
   156	
   157	function Invoke-SourceSecretScan {
   158	
   159	    # ---------------------------------------------------------------------------
   160	    # Step 7: Source secret scan — over EVERY tracked file
   300	        '_jdb_session=older_keyring_value',
   301	        '_jdb_session=keyring_only',
   302	        '_jdb_session=resurrect_me'
   303	    )
   304	
   305	    $SourceHits    = @()
   306	    $SourceEligible = 0   # tracked, non-binary, i.e. in scope
   307	    $SourceScanned  = 0   # actually read and regexed
   308	    $SourceAllowed  = 0   # matched but present in $AllowedLiterals
   309	    foreach ($rel in $sourceFiles) {
   310	        $full = Join-Path $RepoRoot $rel
   311	        if ($skipExt -contains ([System.IO.Path]::GetExtension($rel).ToLowerInvariant())) { continue }
   312	        $SourceEligible++
   624	    } else {
   625	        Ok ("[$name] no leak patterns (ASCII + UTF-16LE)")
   626	    }
   627	}
   628	if ($ScanFail) { FailExit "Binary content scan failed" }
   629	Invoke-SourceSecretScan
   630	
   631	# ---------------------------------------------------------------------------
   632	# Step 8: Compress staging dir to release/JavDBMagnet_<v>_portable.zip
   704	                size_bytes = $h.bytes
   705	            }
   706	        }
   707	    )
   708	    audit       = @{
   709	        portable_forbidden_files = 0
   710	        binary_secret_hits       = $BinaryHitCount
   711	        source_secret_hits       = $SourceHits.Count
   712	        # Denominators, so `source_secret_hits: 0` is interpretable: without
   713	        # them a scan that covered nothing is indistinguishable from one that
   714	        # covered the whole repo and found nothing. `eligible` vs `scanned`
   715	        # must be equal — a gap means files were dropped.
   716	        source_files_eligible    = $SourceEligible
   717	        source_files_scanned     = $SourceScanned
   718	        source_allowlisted_hits  = $SourceAllowed
   719	        # Checked before the build and re-checked after it. This does NOT prove
   720	        # the compiler observed exactly this snapshot: an edit made and reverted
   721	        # mid-build leaves both checks clean while an artifact was produced from

--- status unchanged ---
?? docs/reviews/

已完成 diff、PowerShell 作用域、掃描編碼與 production parser 契約核對；因環境未安裝 pwsh，改以語言作用域規則與等價解碼反例驗證，且未修改工作樹。
  ✓ 讀取 commit diff、release 契約與適用規則
  ✓ 逐段驗證 PowerShell 路徑、失敗模式與跨腳本呼叫端
  ✓ 執行可用的靜態/動態檢查並核實候選問題
  → 依 JSON schema 輸出去重後 findings
exec
/bin/bash -lc "python3 - <<'PY'
from pathlib import Path
p=Path('/home/cy5407/.local/state/agent-audit/events.jsonl')
lines=p.read_text(errors='replace').splitlines()
for line in lines[-20:]: print(line)
PY" in /home/cy5407/javdb-magnet-workbench
 succeeded in 0ms:
{"event": "PostToolUse", "has_error": false, "monotonic_ns": 146307923139603, "permission_mode": "bypassPermissions", "provider": "codex", "schema_version": 1, "session_id": "019fc1be-12ac-7361-bbed-9357005c9b26", "timestamp_taipei": "2026-08-02T17:12:15.477+08:00", "timestamp_utc": "2026-08-02T09:12:15.477Z", "tool_name": "Bash", "turn_id": "019fc1be-13e2-7a33-bbf5-608d9504aab0"}
{"event": "PreToolUse", "has_error": false, "monotonic_ns": 146352664815637, "permission_mode": "bypassPermissions", "provider": "codex", "schema_version": 1, "session_id": "019fc1be-12ac-7361-bbed-9357005c9b26", "timestamp_taipei": "2026-08-02T17:13:00.218+08:00", "timestamp_utc": "2026-08-02T09:13:00.218Z", "tool_name": "Bash", "turn_id": "019fc1be-13e2-7a33-bbf5-608d9504aab0"}
{"event": "PostToolUse", "has_error": false, "monotonic_ns": 146352944526239, "permission_mode": "bypassPermissions", "provider": "codex", "schema_version": 1, "session_id": "019fc1be-12ac-7361-bbed-9357005c9b26", "timestamp_taipei": "2026-08-02T17:13:00.498+08:00", "timestamp_utc": "2026-08-02T09:13:00.498Z", "tool_name": "Bash", "turn_id": "019fc1be-13e2-7a33-bbf5-608d9504aab0"}
{"event": "PreToolUse", "has_error": false, "monotonic_ns": 146382914368086, "permission_mode": "bypassPermissions", "provider": "codex", "schema_version": 1, "session_id": "019fc1be-12ac-7361-bbed-9357005c9b26", "timestamp_taipei": "2026-08-02T17:13:30.468+08:00", "timestamp_utc": "2026-08-02T09:13:30.468Z", "tool_name": "Bash", "turn_id": "019fc1be-13e2-7a33-bbf5-608d9504aab0"}
{"event": "PostToolUse", "has_error": false, "monotonic_ns": 146383248706329, "permission_mode": "bypassPermissions", "provider": "codex", "schema_version": 1, "session_id": "019fc1be-12ac-7361-bbed-9357005c9b26", "timestamp_taipei": "2026-08-02T17:13:30.802+08:00", "timestamp_utc": "2026-08-02T09:13:30.802Z", "tool_name": "Bash", "turn_id": "019fc1be-13e2-7a33-bbf5-608d9504aab0"}
{"event": "PreToolUse", "has_error": false, "monotonic_ns": 146399315993364, "permission_mode": "bypassPermissions", "provider": "codex", "schema_version": 1, "session_id": "019fc1be-12ac-7361-bbed-9357005c9b26", "timestamp_taipei": "2026-08-02T17:13:46.869+08:00", "timestamp_utc": "2026-08-02T09:13:46.869Z", "tool_name": "Bash", "turn_id": "019fc1be-13e2-7a33-bbf5-608d9504aab0"}
{"event": "PostToolUse", "has_error": false, "monotonic_ns": 146399443873576, "permission_mode": "bypassPermissions", "provider": "codex", "schema_version": 1, "session_id": "019fc1be-12ac-7361-bbed-9357005c9b26", "timestamp_taipei": "2026-08-02T17:13:46.997+08:00", "timestamp_utc": "2026-08-02T09:13:46.997Z", "tool_name": "Bash", "turn_id": "019fc1be-13e2-7a33-bbf5-608d9504aab0"}
{"event": "PreToolUse", "has_error": false, "monotonic_ns": 146411938488234, "permission_mode": "bypassPermissions", "provider": "codex", "schema_version": 1, "session_id": "019fc1be-12ac-7361-bbed-9357005c9b26", "timestamp_taipei": "2026-08-02T17:13:59.492+08:00", "timestamp_utc": "2026-08-02T09:13:59.492Z", "tool_name": "Bash", "turn_id": "019fc1be-13e2-7a33-bbf5-608d9504aab0"}
{"event": "PostToolUse", "has_error": false, "monotonic_ns": 146412084431722, "permission_mode": "bypassPermissions", "provider": "codex", "schema_version": 1, "session_id": "019fc1be-12ac-7361-bbed-9357005c9b26", "timestamp_taipei": "2026-08-02T17:13:59.638+08:00", "timestamp_utc": "2026-08-02T09:13:59.638Z", "tool_name": "Bash", "turn_id": "019fc1be-13e2-7a33-bbf5-608d9504aab0"}
{"event": "PreToolUse", "has_error": false, "monotonic_ns": 146417042371949, "permission_mode": "bypassPermissions", "provider": "codex", "schema_version": 1, "session_id": "019fc1be-12ac-7361-bbed-9357005c9b26", "timestamp_taipei": "2026-08-02T17:14:04.596+08:00", "timestamp_utc": "2026-08-02T09:14:04.596Z", "tool_name": "Bash", "turn_id": "019fc1be-13e2-7a33-bbf5-608d9504aab0"}
{"event": "PostToolUse", "has_error": false, "monotonic_ns": 146417159903197, "permission_mode": "bypassPermissions", "provider": "codex", "schema_version": 1, "session_id": "019fc1be-12ac-7361-bbed-9357005c9b26", "timestamp_taipei": "2026-08-02T17:14:04.713+08:00", "timestamp_utc": "2026-08-02T09:14:04.713Z", "tool_name": "Bash", "turn_id": "019fc1be-13e2-7a33-bbf5-608d9504aab0"}
{"event": "PreToolUse", "has_error": false, "monotonic_ns": 146519077198341, "permission_mode": "bypassPermissions", "provider": "codex", "schema_version": 1, "session_id": "019fc1be-12ac-7361-bbed-9357005c9b26", "timestamp_taipei": "2026-08-02T17:15:46.631+08:00", "timestamp_utc": "2026-08-02T09:15:46.631Z", "tool_name": "Bash", "turn_id": "019fc1be-13e2-7a33-bbf5-608d9504aab0"}
{"event": "PostToolUse", "has_error": false, "monotonic_ns": 146519271324656, "permission_mode": "bypassPermissions", "provider": "codex", "schema_version": 1, "session_id": "019fc1be-12ac-7361-bbed-9357005c9b26", "timestamp_taipei": "2026-08-02T17:15:46.825+08:00", "timestamp_utc": "2026-08-02T09:15:46.825Z", "tool_name": "Bash", "turn_id": "019fc1be-13e2-7a33-bbf5-608d9504aab0"}
{"event": "PreToolUse", "has_error": false, "monotonic_ns": 146532685681488, "permission_mode": "bypassPermissions", "provider": "codex", "schema_version": 1, "session_id": "019fc1be-12ac-7361-bbed-9357005c9b26", "timestamp_taipei": "2026-08-02T17:16:00.239+08:00", "timestamp_utc": "2026-08-02T09:16:00.239Z", "tool_name": "Bash", "turn_id": "019fc1be-13e2-7a33-bbf5-608d9504aab0"}
{"event": "PostToolUse", "has_error": false, "monotonic_ns": 146532803080943, "permission_mode": "bypassPermissions", "provider": "codex", "schema_version": 1, "session_id": "019fc1be-12ac-7361-bbed-9357005c9b26", "timestamp_taipei": "2026-08-02T17:16:00.356+08:00", "timestamp_utc": "2026-08-02T09:16:00.356Z", "tool_name": "Bash", "turn_id": "019fc1be-13e2-7a33-bbf5-608d9504aab0"}
{"event": "PreToolUse", "has_error": false, "monotonic_ns": 146568698267859, "permission_mode": "bypassPermissions", "provider": "codex", "schema_version": 1, "session_id": "019fc1be-12ac-7361-bbed-9357005c9b26", "timestamp_taipei": "2026-08-02T17:16:36.252+08:00", "timestamp_utc": "2026-08-02T09:16:36.252Z", "tool_name": "Bash", "turn_id": "019fc1be-13e2-7a33-bbf5-608d9504aab0"}
{"event": "PostToolUse", "has_error": false, "monotonic_ns": 146568929932963, "permission_mode": "bypassPermissions", "provider": "codex", "schema_version": 1, "session_id": "019fc1be-12ac-7361-bbed-9357005c9b26", "timestamp_taipei": "2026-08-02T17:16:36.483+08:00", "timestamp_utc": "2026-08-02T09:16:36.483Z", "tool_name": "Bash", "turn_id": "019fc1be-13e2-7a33-bbf5-608d9504aab0"}
{"event": "PreToolUse", "has_error": false, "monotonic_ns": 146578394845807, "permission_mode": "bypassPermissions", "provider": "codex", "schema_version": 1, "session_id": "019fc1be-12ac-7361-bbed-9357005c9b26", "timestamp_taipei": "2026-08-02T17:16:45.948+08:00", "timestamp_utc": "2026-08-02T09:16:45.948Z", "tool_name": "update_plan", "turn_id": "019fc1be-13e2-7a33-bbf5-608d9504aab0"}
{"event": "PostToolUse", "has_error": false, "monotonic_ns": 146578424942684, "permission_mode": "bypassPermissions", "provider": "codex", "schema_version": 1, "session_id": "019fc1be-12ac-7361-bbed-9357005c9b26", "timestamp_taipei": "2026-08-02T17:16:45.978+08:00", "timestamp_utc": "2026-08-02T09:16:45.978Z", "tool_name": "update_plan", "turn_id": "019fc1be-13e2-7a33-bbf5-608d9504aab0"}
{"event": "PreToolUse", "has_error": false, "monotonic_ns": 146578458494558, "permission_mode": "bypassPermissions", "provider": "codex", "schema_version": 1, "session_id": "019fc1be-12ac-7361-bbed-9357005c9b26", "timestamp_taipei": "2026-08-02T17:16:46.012+08:00", "timestamp_utc": "2026-08-02T09:16:46.012Z", "tool_name": "Bash", "turn_id": "019fc1be-13e2-7a33-bbf5-608d9504aab0"}

  ✓ 讀取 commit diff、release 契約與適用規則
  ✓ 逐段驗證 PowerShell 路徑、失敗模式與跨腳本呼叫端
  ✓ 執行可用的靜態/動態檢查並核實候選問題
  ✓ 依 JSON schema 輸出去重後 findings
codex
[結束｜時間未取得｜Asia/Taipei UTC+08:00] The default release path universally fails while writing its manifest because the extracted scan function does not preserve its metrics. The new byte-decoding implementation also creates a narrower encoding blind spot.

Full review comments:

- [P0] Return source-scan metrics from the function — /home/cy5407/javdb-magnet-workbench/scripts/build-release.ps1:305-308
  On every normal release, these assignments create function-local variables in PowerShell. Once `Invoke-SourceSecretScan` returns, `$SourceHits`, `$SourceEligible`, `$SourceScanned`, and `$SourceAllowed` are undefined, so `Set-StrictMode` aborts while constructing the manifest after the expensive build and hashing steps; return the metrics or assign them explicitly in script scope.

- [P2] Decode BOM-marked UTF-16BE source files — /home/cy5407/javdb-magnet-workbench/scripts/build-release.ps1:152-155
  When a tracked text file is UTF-16BE, both configured decoders produce interleaved or byte-swapped text, so an embedded ASCII credential never reaches the regexes as a contiguous string. The previous `Get-Content` path recognized the UTF-16BE BOM, making this a regression in the promised all-text-files scan; use BOM-aware decoding or include `BigEndianUnicode`.
[結束｜時間未取得｜Asia/Taipei UTC+08:00] The default release path universally fails while writing its manifest because the extracted scan function does not preserve its metrics. The new byte-decoding implementation also creates a narrower encoding blind spot.

Full review comments:

- [P0] Return source-scan metrics from the function — /home/cy5407/javdb-magnet-workbench/scripts/build-release.ps1:305-308
  On every normal release, these assignments create function-local variables in PowerShell. Once `Invoke-SourceSecretScan` returns, `$SourceHits`, `$SourceEligible`, `$SourceScanned`, and `$SourceAllowed` are undefined, so `Set-StrictMode` aborts while constructing the manifest after the expensive build and hashing steps; return the metrics or assign them explicitly in script scope.

- [P2] Decode BOM-marked UTF-16BE source files — /home/cy5407/javdb-magnet-workbench/scripts/build-release.ps1:152-155
  When a tracked text file is UTF-16BE, both configured decoders produce interleaved or byte-swapped text, so an embedded ASCII credential never reaches the regexes as a contiguous string. The previous `Get-Content` path recognized the UTF-16BE BOM, making this a regression in the promised all-text-files scan; use BOM-aware decoding or include `BigEndianUnicode`.
```
