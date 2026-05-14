# Sidecar — Build Pipeline & (Historical) Spike Driver

> Source files documented:
> - [`spikes/pyinstaller_sidecar/build_sidecar.py`](../../../spikes/pyinstaller_sidecar/build_sidecar.py)
> - [`spikes/pyinstaller_sidecar/driver_rust/src/main.rs`](../../../spikes/pyinstaller_sidecar/driver_rust/src/main.rs) — **historical spike harness**, see §3
>
> Intent context comes from [`spikes/pyinstaller_sidecar/NOTES.md`](../../../spikes/pyinstaller_sidecar/NOTES.md) — that document is not duplicated here.
>
> ⚠️ **Not the live protocol contract.** This file documents (a) the build pipeline and (b) an older argv-based spike driver. The live JSONL daemon protocol that the Tauri Rust backend actually speaks to `sidecar.exe` is owned by [`sidecar-runtime.md`](sidecar-runtime.md) — use that when changing runtime behavior.

---

## 1. Overview

The **sidecar** is a PyInstaller-bundled, single-file Windows executable that wraps the project's Python scraping/Real-Debrid stack (`sidecar/sidecar.py`, plus `javdb_scraper`, `realdebrid`, `app_logging`). It ships as `sidecar-x86_64-pc-windows-msvc.exe` and is placed inside the Tauri app's `externalBin` folder so Tauri 2's sidecar resolver can discover it by target-triple naming convention.

This document covers the **build pipeline** and an **older spike driver**. The live daemon protocol is documented in [`sidecar-runtime.md`](sidecar-runtime.md).

In the spike driver contract (M3 era), the sidecar:

- Received a subcommand + arguments (`fetch-javdb <url>`) as **argv** from the spike `driver_rust`.
- Performed HTTP scraping via `curl_cffi`, optionally hitting Real-Debrid.
- Wrote a single line of JSON to **stdout** containing the result; warnings/log lines to **stderr**.
- Exited with code `0` on success, non-zero otherwise.

⚠️ **M9 update**: the live runtime is no longer argv-driven. `sidecar/sidecar.py` was promoted to a JSONL daemon (handshake + per-command request/response over stdin/stdout). The §3 description below documents the spike's argv interface for historical reference only.

The Tauri wiring itself (how `tauri::api::process::Command::new_sidecar()` is invoked, command handlers, IPC types) lives elsewhere; this document only covers the **build pipeline** and the **historical driver-side contract** as expressed in the spike code.

Two facts to keep in mind while reading:

1. The `driver_rust` crate is a **dev-time test harness** that simulated what the production Tauri backend would do **in the M3 argv era**. It is explicitly not the production path — see the module-level comment in [`driver_rust/src/main.rs:1-11`](../../../spikes/pyinstaller_sidecar/driver_rust/src/main.rs#L1-L11). M9 production uses JSONL daemon mode; the driver does **not** speak that protocol.
2. The PyInstaller `--onefile` artifact is written **directly** into the Tauri layout at `app/src-tauri/binaries/sidecar-x86_64-pc-windows-msvc.exe`. There is no separate copy step.

---

## 2. `build_sidecar.py`

Top-level constants ([`build_sidecar.py:22-31`](../../../spikes/pyinstaller_sidecar/build_sidecar.py#L22-L31)):

| Constant | Value | Role |
|----------|-------|------|
| `SPIKE_DIR` | `<repo>/spikes/pyinstaller_sidecar/` | This script's directory. |
| `REPO_ROOT` | `<repo>/` | Two levels up. |
| `ENTRY` | `<repo>/sidecar/sidecar.py` | PyInstaller entry script (promoted in M3). |
| `DIST` | `<repo>/app/src-tauri/binaries/` | Output dir — matches Tauri `externalBin` layout. |
| `BUILD` | `<repo>/spikes/pyinstaller_sidecar/build/` | PyInstaller intermediates. |
| `APP_NAME` | `sidecar-x86_64-pc-windows-msvc` | Tauri 2 target-triple naming. |
| `SPEC` | `<SPIKE_DIR>/sidecar-x86_64-pc-windows-msvc.spec` | Generated `.spec` location. |

### `ensure_pyinstaller()` ([`build_sidecar.py:34-42`](../../../spikes/pyinstaller_sidecar/build_sidecar.py#L34-L42))

**Purpose**: Make sure PyInstaller is importable; install via pip into the current interpreter if not.

**Contract**:
- Params: none.
- Returns: `str` — either `"already-installed"` (import succeeded) or `"installed-via-pip"` (had to install).
- Side effects: may run `pip install pyinstaller` against the active Python interpreter; prints status to stderr.
- Errors: `subprocess.CalledProcessError` propagates if `pip install` fails (no catch).

**Calls**: `import PyInstaller`, `subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])`.

### `clean()` ([`build_sidecar.py:45-52`](../../../spikes/pyinstaller_sidecar/build_sidecar.py#L45-L52))

**Purpose**: Remove previous build artifacts so each run starts from a clean state.

**Contract**:
- Params: none.
- Returns: `None`.
- Side effects: deletes (if present) `DIST/`, `BUILD/`, and the `.spec` file. Prints `已清除: <name>` to stderr for each removal.
- Errors: `OSError`/`PermissionError` propagates (no catch).

**Calls**: `Path.exists()`, `Path.is_dir()`, `shutil.rmtree(p)`, `Path.unlink()`.

**Note**: `clean()` removes the **entire** `app/src-tauri/binaries/` directory, not just the sidecar exe. If other binaries land there later, this becomes destructive — `(unverified; appears to be acceptable today because the directory only holds the sidecar)`.

### `build()` ([`build_sidecar.py:55-82`](../../../spikes/pyinstaller_sidecar/build_sidecar.py#L55-L82))

**Purpose**: Invoke PyInstaller to package `sidecar/sidecar.py` into a single-file Windows console exe.

**Contract**:
- Params: none.
- Returns: `None`.
- Preconditions: `ENTRY` must exist; otherwise prints an error and `sys.exit(1)`.
- Side effects: runs PyInstaller as a subprocess; produces `DIST/<APP_NAME>.exe`, populates `BUILD/`, writes `.spec` to `SPEC`.
- Errors: `subprocess.CalledProcessError` propagates if PyInstaller fails.

**Calls**: `Path.exists()`, `subprocess.check_call(cmd, cwd=REPO_ROOT)`.

PyInstaller command ([`build_sidecar.py:61-81`](../../../spikes/pyinstaller_sidecar/build_sidecar.py#L61-L81)):

```
<python> -m PyInstaller
    --onefile
    --console
    --name sidecar-x86_64-pc-windows-msvc
    --clean
    --distpath  <repo>/app/src-tauri/binaries
    --workpath  <repo>/spikes/pyinstaller_sidecar/build
    --specpath  <repo>/spikes/pyinstaller_sidecar
    --paths     <repo>                       # so PyInstaller can resolve cross-folder imports
    --hidden-import curl_cffi
    --hidden-import curl_cffi.requests
    --collect-all   curl_cffi                # curl_cffi has native deps; --hidden-import alone is insufficient
    --hidden-import javdb_scraper          # M9: replaces javdb_magnet_gui (Tk no longer bundled)
    --hidden-import realdebrid
    --hidden-import app_logging
    <repo>/sidecar/sidecar.py
```

`cwd=REPO_ROOT` is set so relative imports resolve from the repo root.

### `post_build()` ([`build_sidecar.py:85-102`](../../../spikes/pyinstaller_sidecar/build_sidecar.py#L85-L102))

**Purpose**: Verify the exe was produced; print size, usage hint, and log-dir hint to stderr.

**Contract**:
- Params: none.
- Returns: `None`.
- Postconditions: exits with status `1` if `DIST/<APP_NAME>.exe` does not exist after `build()`.
- Side effects: stderr output only. Does **not** copy, sign, or move the artifact (the build step already wrote it into the final Tauri location).
- Errors: `OSError` from `stat()` propagates if the file vanishes between `exists()` and `stat()`.

**Calls**: `Path.exists()`, `Path.stat()`, `print(..., file=sys.stderr)`.

### Entry point: `if __name__ == "__main__":` ([`build_sidecar.py:105-110`](../../../spikes/pyinstaller_sidecar/build_sidecar.py#L105-L110))

Sequence:
1. `ensure_pyinstaller()` — install if missing.
2. Print PyInstaller strategy to stderr.
3. `clean()` — wipe previous outputs.
4. `build()` — run PyInstaller.
5. `post_build()` — verify + print usage hints.

**CLI args consumed**: none — the script takes no positional or option arguments.

**Environment variables consumed**: none directly. (`post_build()` mentions `JAVDB_LOG_DIR` and `%LOCALAPPDATA%` as **runtime** hints for the produced exe, not for the build itself.)

**Output paths produced**:
- `app/src-tauri/binaries/sidecar-x86_64-pc-windows-msvc.exe` — the artifact (ends up in the Tauri layout directly).
- `spikes/pyinstaller_sidecar/build/` — PyInstaller intermediates.
- `spikes/pyinstaller_sidecar/sidecar-x86_64-pc-windows-msvc.spec` — generated spec file.

**Files explicitly NOT bundled**: `.env`, `cookies.txt` (no `--add-data` flags). Confirmed by absence in [`build_sidecar.py:61-81`](../../../spikes/pyinstaller_sidecar/build_sidecar.py#L61-L81).

---

## 3. `driver_rust/src/main.rs`

This crate is a **dev-time harness** that simulates the Tauri backend's invocation of the sidecar. The module-level doc-comment ([`main.rs:1-11`](../../../spikes/pyinstaller_sidecar/driver_rust/src/main.rs#L1-L11)) is explicit: production must use `tauri::api::process::Command::new_sidecar()` instead of the path-walking discovery this driver performs.

### Constants

- [`SIDECAR_NAME`](../../../spikes/pyinstaller_sidecar/driver_rust/src/main.rs#L20-L23) — `"sidecar.exe"` on Windows, `"sidecar"` elsewhere. Platform-gated via `#[cfg(windows)]`.
- [`SIDECAR_EXE_ENV`](../../../spikes/pyinstaller_sidecar/driver_rust/src/main.rs#L26) — `"SIDECAR_EXE"`, env var name for explicit path override.

> **Note**: the constants encode `"sidecar.exe"`, but `build_sidecar.py` actually produces `sidecar-x86_64-pc-windows-msvc.exe`. The path-walking code below will only succeed when run against a manually renamed exe **or** via the `SIDECAR_EXE` env var. `(unverified; appears to be a known spike-vs-M3 drift — the build script was updated to Tauri-target-triple naming after the driver was written.)`

### Structs

#### `SidecarResponse` ([`main.rs:28-35`](../../../spikes/pyinstaller_sidecar/driver_rust/src/main.rs#L28-L35))

Deserialize-only. Models the JSON the sidecar writes to stdout.

| Field | Type | Notes |
|-------|------|-------|
| `ok` | `bool` | Sidecar's self-reported success flag. |
| `magnet_count` | `usize` | Number of magnets parsed. |
| `magnets` | `Vec<SidecarMagnet>` | Per-magnet entries (only `magnet_redacted` is captured). |
| `error` | `Option<String>` | `#[serde(default)]` — defaults to `None` if absent. |

Fields the sidecar emits but the driver **ignores**: `command`, `engine`, `code`, plus per-magnet `name`, `size`, `tags` (visible in [`NOTES.md` §測試結果](../../../spikes/pyinstaller_sidecar/NOTES.md)).

#### `SidecarMagnet` ([`main.rs:37-40`](../../../spikes/pyinstaller_sidecar/driver_rust/src/main.rs#L37-L40))

Deserialize-only. Single field captured:
- `magnet_redacted: String` — the truncated/elided magnet link.

#### `DriverSummary` ([`main.rs:42-51`](../../../spikes/pyinstaller_sidecar/driver_rust/src/main.rs#L42-L51))

Serialize-only. The driver's own report, printed to stdout on completion.

| Field | Type | Meaning |
|-------|------|---------|
| `ok` | `bool` | `resp.ok && exit_code == 0`. |
| `sidecar_exit` | `i32` | Exit code of the sidecar (or `-1` if it never started). |
| `parsed_json` | `bool` | Whether the driver could decode stdout as `SidecarResponse`. |
| `magnet_count` | `usize` | Echoed from `resp.magnet_count`. |
| `first_magnet_redacted_present` | `bool` | Whether the first magnet's redacted form passes a shape check (see `run()` below). |
| `stderr_nonempty` | `bool` | Whether the sidecar emitted any stderr. |
| `error` | `Option<String>` | Either the sidecar's reported error, a launch error, or a JSON-parse error. |

### Functions

#### `locate_sidecar_exe() -> Result<PathBuf, String>` ([`main.rs:62-104`](../../../spikes/pyinstaller_sidecar/driver_rust/src/main.rs#L62-L104))

**Purpose**: Find the sidecar binary on disk.

**Contract**:
- Params: none.
- Returns: `Ok(PathBuf)` for the first existing candidate, else `Err(String)` describing how many locations were tried.
- Side effects: reads `SIDECAR_EXE` and `CARGO_MANIFEST_DIR` env vars; calls `current_exe()`.
- Errors: never panics; everything is funnelled into the `Err` string.

**Lookup priority**:
1. `$SIDECAR_EXE` if set — for CI / tests / containers.
2. `$CARGO_MANIFEST_DIR/../dist/<SIDECAR_NAME>` — `cargo run` from source tree.
3. Walk up from `current_exe()` up to 6 levels, probing `dist/<SIDECAR_NAME>` and `spikes/pyinstaller_sidecar/dist/<SIDECAR_NAME>` at each level.

**Calls**: `env::var`, `PathBuf::from`, `Path::pop`, `Path::push`, `Path::exists`, `env::current_exe`.

**Note**: This walker looks under `dist/`, but `build_sidecar.py` no longer writes to `dist/`. See the constants note above.

#### `run(url: &str) -> DriverSummary` ([`main.rs:106-183`](../../../spikes/pyinstaller_sidecar/driver_rust/src/main.rs#L106-L183))

**Purpose**: Locate the sidecar, spawn it with `fetch-javdb <url>`, decode its stdout JSON, and produce a `DriverSummary`.

**Contract**:
- Params: `url: &str` — the JavDB URL to scrape. Already validated by the caller as `http(s)`-prefixed.
- Returns: `DriverSummary` (never panics; failure modes all map to fields).
- Side effects:
  - Spawns the sidecar with `stdin = null`, `stdout = piped`, `stderr = piped`.
  - Reads all of stdout/stderr into memory (no streaming).
- Errors handled internally:
  - `locate_sidecar_exe()` failure → `sidecar_exit = -1`, `ok = false`, `error = Some(<lookup error>)`.
  - Spawn failure → `sidecar_exit = -1`, `error = Some("無法啟動 ...")`.
  - JSON parse failure → `parsed_json = false`, `error = Some("無法解析 sidecar JSON: ...")`, `sidecar_exit` still reflects the real exit code.

**Calls**: `locate_sidecar_exe()`, `Command::new(...).arg("fetch-javdb").arg(url).stdin(Stdio::null()).stdout(Stdio::piped()).stderr(Stdio::piped()).output()`, `serde_json::from_str`.

**Subprocess invocation** ([`main.rs:122-129`](../../../spikes/pyinstaller_sidecar/driver_rust/src/main.rs#L122-L129)):

```text
<sidecar.exe> fetch-javdb <url>
```

No timeout. The comment at [`main.rs:122`](../../../spikes/pyinstaller_sidecar/driver_rust/src/main.rs#L122) explicitly flags this as a spike-only omission.

**Redacted-magnet shape check** ([`main.rs:153-161`](../../../spikes/pyinstaller_sidecar/driver_rust/src/main.rs#L153-L161)): the first magnet's `magnet_redacted` field is considered well-formed iff:
- starts with `magnet:?xt=urn:btih:`,
- contains the literal `...` (elision marker),
- is shorter than 64 chars.

This is the driver's assertion that the sidecar is in fact redacting magnets, not leaking them.

#### `main() -> ExitCode` ([`main.rs:185-208`](../../../spikes/pyinstaller_sidecar/driver_rust/src/main.rs#L185-L208))

**Purpose**: Parse argv, call `run()`, print the summary as pretty JSON.

**Contract**:
- argv: requires exactly one positional argument — the URL. URL must start with `http`.
- stdout: pretty-printed JSON of `DriverSummary`.
- stderr: usage message on missing/invalid argv; serialization-failure message if `serde_json::to_string_pretty` fails.
- Exit codes:
  - `2` — missing argv or URL doesn't start with `http`.
  - `0` — `summary.ok == true`.
  - `1` — `summary.ok == false`.

**Calls**: `env::args`, `serde_json::to_string_pretty`, `run`.

### Driver-side contract summary

- **Argv it sends to the sidecar**: `["fetch-javdb", <url>]`. No flags, no environment forwarding, no stdin payload.
- **What it reads from the sidecar**: a single JSON document on stdout (whole-buffer parse, no line framing — `serde_json::from_str(stdout.trim())` at [`main.rs:149`](../../../spikes/pyinstaller_sidecar/driver_rust/src/main.rs#L149)).
- **What it expects in that JSON**: at minimum `ok: bool`, `magnet_count: usize`, `magnets: [{ magnet_redacted: String }, ...]`; optionally `error: String`.
- **What it does with stderr**: only inspects whether it's non-empty (`stderr_nonempty` flag). Never echoes content.
- **What it does with the exit code**: records it; does not re-derive success from it (the `ok` field in `DriverSummary` requires **both** `resp.ok == true` and `exit_code == 0`).

---

## 4. Build pipeline summary

End-to-end, from invocation to artifact:

1. **Invocation** — `npm run sidecar:build` (or equivalent). `(unverified; the npm script wiring is not in the files read, but the user's brief says this is the entry point.)` In practice the script body runs:
   ```
   python spikes/pyinstaller_sidecar/build_sidecar.py
   ```
2. **PyInstaller bootstrap** — `ensure_pyinstaller()` imports `PyInstaller`; if absent, runs `pip install pyinstaller` against the active interpreter.
3. **Clean** — `clean()` removes:
   - `app/src-tauri/binaries/` (entire directory)
   - `spikes/pyinstaller_sidecar/build/`
   - `spikes/pyinstaller_sidecar/sidecar-x86_64-pc-windows-msvc.spec`
4. **Build** — PyInstaller is invoked with the command shown in §2 / `build()`. Key inputs:
   - Entry: `<repo>/sidecar/sidecar.py`
   - Search path: `<repo>` (for cross-package imports like `javdb_scraper`)
   - Hidden imports: `curl_cffi`, `curl_cffi.requests`, `javdb_scraper`, `realdebrid`, `app_logging` *(M9: `javdb_magnet_gui` → `javdb_scraper`; Tk no longer bundled)*
   - Collected: `curl_cffi` (`--collect-all`, required for native deps)
   - Mode: `--onefile --console`
   - Working dir: `<repo>` (`cwd=REPO_ROOT`)
5. **Output** — `app/src-tauri/binaries/sidecar-x86_64-pc-windows-msvc.exe`. PyInstaller writes there directly via `--distpath`. There is no rename or copy step after the build.
6. **Verify** — `post_build()` checks the exe exists, prints size and usage hints to stderr. Exits with status `1` if the artifact is missing.

**Final artifact location** (what Tauri's `externalBin` consumes):

```
<repo>/app/src-tauri/binaries/sidecar-x86_64-pc-windows-msvc.exe
```

**Files NOT bundled into the exe** (must be staged at runtime by the caller / installer):
- `.env`
- `cookies.txt`

(See [`build_sidecar.py:9-12`](../../../spikes/pyinstaller_sidecar/build_sidecar.py#L9-L12) and the comment block in `build()`.)

---

## 5. Sidecar stdio contract (as inferred from `driver_rust`)

The driver_rust code is the source-of-truth surface this document can verify; the sidecar's full surface is in `sidecar/sidecar.py` (not read here). From the driver alone:

### Protocol shape

- **Transport**: process spawn + argv + stdout/stderr. **No HTTP**, **no port**, **no stdin payload** (the driver explicitly sets `stdin = Stdio::null()` at [`main.rs:126`](../../../spikes/pyinstaller_sidecar/driver_rust/src/main.rs#L126)).
- **Framing**: whole-buffer JSON on stdout — `serde_json::from_str(stdout.trim())` at [`main.rs:149`](../../../spikes/pyinstaller_sidecar/driver_rust/src/main.rs#L149). One JSON document per process invocation. **Not** JSON-Lines, **not** length-prefixed.
- **Lifetime**: one-shot per invocation. The sidecar exits after writing the response. (NOTES.md mentions a future daemon mode, but the current contract is one-shot.)

### Commands

Only one command is exercised by the driver:

| Command (argv[0]) | Args | Response shape |
|-------------------|------|----------------|
| `fetch-javdb` | `<url>` (positional) | `{ ok: bool, magnet_count: usize, magnets: [{ magnet_redacted: String, ... }], error?: String, ... }` |

Additional fields seen in `NOTES.md` testing output (`command`, `engine`, `code`, plus per-magnet `name`/`size`/`tags`) exist in the actual response but are not part of the driver-consumed contract.

### Exit codes (as observed/handled by driver)

- `0` — success (paired with `ok: true` in JSON).
- Non-zero — failure; driver still attempts to parse stdout JSON to capture the `error` field.
- `-1` — synthetic value the driver uses when the sidecar never launched.

### Stderr

Free-form. The driver only checks `is_empty()`. Per `NOTES.md`, real-world stderr contains `RequestsDependencyWarning` from urllib3 plus `app_logging` init lines.

### Magnet redaction invariant

Asserted by the driver at [`main.rs:153-161`](../../../spikes/pyinstaller_sidecar/driver_rust/src/main.rs#L153-L161): each `magnet_redacted` string must
- start with `magnet:?xt=urn:btih:`,
- contain `...`,
- be shorter than 64 characters.

This is the driver's encoded expectation that the sidecar never returns full magnet URIs over stdout.

---

## Summary

The sidecar contract, as visible from the spike code, is: **spawn `sidecar-x86_64-pc-windows-msvc.exe` with argv `["fetch-javdb", "<url>"]`, read a single JSON document from stdout, ignore stderr (except for liveness), and check that `ok == true` plus `exit_code == 0`.** The build pipeline is a single Python script (`build_sidecar.py`) that shells out to PyInstaller `--onefile --console` and writes the artifact straight into the Tauri `externalBin` layout — no separate copy step, no `.env` or `cookies.txt` bundling.

**Surprising findings**:
1. The `driver_rust` constants still encode `SIDECAR_NAME = "sidecar.exe"` and probe under `dist/`, but `build_sidecar.py` writes to `app/src-tauri/binaries/sidecar-x86_64-pc-windows-msvc.exe`. The driver's auto-discovery is therefore stale; in practice it only works via the `SIDECAR_EXE` env var or after a manual rename. This is unflagged in the source.
2. `clean()` removes the **entire** `app/src-tauri/binaries/` directory rather than just the sidecar exe — fine today (single-artifact directory), but a footgun the day another binary lands there.
