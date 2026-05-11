# M6a — Release Smoke Checklist

> Run this against the installed app (MSI install or copied `target/release/` folder) to confirm M5 functionality survived the release build path. Each ❑ is a single step; tick as you go.

## Pre-flight

- Path to artifact: `app/src-tauri/target/release/javdbmagnet.exe` (+ `sidecar.exe` next to it)
- MSI installer (if built): `app/src-tauri/target/release/bundle/msi/*.msi`
- Settings file: `%APPDATA%\com.javdbmagnet.app\settings.json`
- Pending file: `%APPDATA%\com.javdbmagnet.app\pending_torrents.json`
- Log dir: `%LOCALAPPDATA%\JavDBMagnet\logs\`

## 1. Cold start

- ❑ Launch `javdbmagnet.exe` (or installed shortcut). Window opens within ~3s.
- ❑ Sidecar ping section reports `✓ pong`.
- ❑ No console window flashes alongside the WebView.

## 2. RD token persistence

- ❑ On first launch the Token row shows `✓ 已設定` (or `✗ 未設定` if fresh install).
- ❑ Close and reopen the app. Token state preserved (✓ stays ✓).

## 3. JavDB fetch (one URL)

- ❑ Paste a JavDB URL into 批次擷取. Click 開始擷取.
- ❑ Within 10–30s the row turns 成功. Magnets table populates.
- ❑ Each magnet row displays `magnet:?xt=urn:btih:<8-char-hash>...` (redacted form), not full hash.

## 4. Paste magnet → register

- ❑ Paste 2–3 raw magnets into 直接貼上磁力連結.
- ❑ Click 註冊磁力. Inline confirmation appears beneath the button: `已註冊 N 個磁力`.
- ❑ A `(直接貼上 N)` group shows in the 結果 section.

## 5. Send to RD (small batch)

- ❑ With RD token set, click 送至 Real-Debrid (N) (or the per-group button).
- ❑ Progress bar advances `N/N` → 完成 N.
- ❑ At least one row shows `已完成` with a `<provider>@<filename>.<ext>` label.

## 6. Copy RD direct links

- ❑ After send-to-RD finishes, click 複製所有 RD 直連 (N).
- ❑ Paste into Notepad — N lines of `https://download.real-debrid.com/d/...` URLs.

## 7. Security invariants (log + persisted files)

Run from PowerShell after exercising steps 3–6:

```powershell
# 7a. Log must not contain full magnet text
Select-String -Path "$env:LOCALAPPDATA\JavDBMagnet\logs\debug.log*" `
  -Pattern "magnet:\?xt|urn:btih"
# Expected: no output.

# 7b. Pending file must not contain magnet or token
$pending = "$env:APPDATA\com.javdbmagnet.app\pending_torrents.json"
if (Test-Path $pending) {
  Get-Content $pending | Select-String -Pattern "magnet:|urn:btih|api_token|Bearer"
}
# Expected: no output.

# 7c. settings.json must keep rd.api_token blanked
$settings = "$env:APPDATA\com.javdbmagnet.app\settings.json"
if (Test-Path $settings) {
  Get-Content $settings | Select-String -Pattern '"api_token"\s*:\s*"[^"]+"'
}
# Expected: no output (only empty-string values allowed).
```

- ❑ 7a passes: no `magnet:?xt` or `urn:btih` in any log file.
- ❑ 7b passes: pending JSON has neither magnet text nor RD token.
- ❑ 7c passes: `rd.api_token` is `""` or absent in settings.

## 8. Bundle audit (run once per build, before distributing)

Confirms the MSI / copied folder has no leaked secrets baked in.

```powershell
# Replace with the directory you installed/copied to:
$bundle = "$env:USERPROFILE\Desktop\JavDBMagnet"
Get-ChildItem $bundle -Recurse | ForEach-Object {
  if ($_.Name -in @(".env", "cookies.txt", "pending_torrents.json") `
      -or $_.Name -like "*.log" -or $_.FullName -like "*\logs\*") {
    Write-Output "FORBIDDEN: $($_.FullName)"
  }
}
```

- ❑ No `FORBIDDEN:` output.
- ❑ Bundle contains `javdbmagnet.exe` and `sidecar.exe` (or `sidecar-x86_64-pc-windows-msvc.exe` for raw target dir).

## 9. Clean shutdown

- ❑ Close the WebView window. No leftover `javdbmagnet.exe` / `sidecar.exe` in Task Manager within 5s.

---

## Pass/Fail

If every ❑ is checked, this release is M6a-pass. Otherwise note the failed step in the corresponding GitHub Issue / follow-up commit.
