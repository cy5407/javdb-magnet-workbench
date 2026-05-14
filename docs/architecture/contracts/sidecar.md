# Sidecar — PyInstaller Build Pipeline

> Source file documented:
> - [`spikes/pyinstaller_sidecar/build_sidecar.py`](../../../spikes/pyinstaller_sidecar/build_sidecar.py)
>
> Intent context comes from [`spikes/pyinstaller_sidecar/NOTES.md`](../../../spikes/pyinstaller_sidecar/NOTES.md) — that document is not duplicated here.
>
> ⚠️ **Not the live protocol contract.** This file documents only the build pipeline. The live JSONL daemon protocol that the Tauri Rust backend speaks to `sidecar.exe` is owned by [`sidecar-runtime.md`](sidecar-runtime.md) — use that when changing runtime behavior.

---

## 1. Overview

The **sidecar** is a PyInstaller-bundled, single-file Windows executable that wraps the project's Python scraping/Real-Debrid stack (`sidecar/sidecar.py`, plus `javdb_scraper`, `realdebrid`, `app_logging`). It ships as `sidecar-x86_64-pc-windows-msvc.exe` and is placed inside the Tauri app's `externalBin` folder so Tauri 2's sidecar resolver can discover it by target-triple naming convention.

This document covers the **build pipeline** only. The runtime protocol (handshake + per-command JSONL request/response over stdin/stdout) lives in [`sidecar-runtime.md`](sidecar-runtime.md). M9 Phase 8-C removed the previous `driver_rust` argv-style spike harness — it pre-dated M3 and only spoke the obsolete `<exe> fetch-javdb <url>` argv contract, which made it actively misleading once production switched to JSONL. The Tauri-side wiring (`tauri-plugin-shell` `sidecar(...)` API, command handlers, IPC types) lives in `app/src-tauri/src/sidecar_manager.rs` and `app/src-tauri/src/commands.rs`.

Two facts to keep in mind while reading:

1. The PyInstaller `--onefile` artifact is written **directly** into the Tauri layout at `app/src-tauri/binaries/sidecar-x86_64-pc-windows-msvc.exe`. There is no separate copy step.
2. M9 Phase 8-B added [`requirements-sidecar.txt`](../../../requirements-sidecar.txt) as the exact dependency contract. `build_sidecar.py` verifies every pinned package via `importlib.metadata` and fails fast on missing/mismatched versions; it no longer auto-installs anything.

---

## 2. `build_sidecar.py`

Top-level constants ([`build_sidecar.py:25-37`](../../../spikes/pyinstaller_sidecar/build_sidecar.py#L25-L37)):

| Constant | Value | Role |
|----------|-------|------|
| `SPIKE_DIR` | `<repo>/spikes/pyinstaller_sidecar/` | This script's directory. |
| `REPO_ROOT` | `<repo>/` | Two levels up. |
| `ENTRY` | `<repo>/sidecar/sidecar.py` | PyInstaller entry script (promoted in M3). |
| `DIST` | `<repo>/app/src-tauri/binaries/` | Output dir — matches Tauri `externalBin` layout. |
| `BUILD` | `<repo>/spikes/pyinstaller_sidecar/build/` | PyInstaller intermediates. |
| `APP_NAME` | `sidecar-x86_64-pc-windows-msvc` | Tauri 2 target-triple naming. |
| `SPEC` | `<SPIKE_DIR>/sidecar-x86_64-pc-windows-msvc.spec` | Generated `.spec` location. |
| `REQUIREMENTS` | `<repo>/requirements-sidecar.txt` | Pinned-deps contract verified before every build. |

### `_pinned_versions() -> dict[str, str]` ([`build_sidecar.py:40-62`](../../../spikes/pyinstaller_sidecar/build_sidecar.py#L40-L62))

**Purpose**: Parse `requirements-sidecar.txt` into `{lowercase_name: pinned_version}`. Strict: only `name==version` lines (plus blank lines / `#` comments) are accepted.

**Contract**:
- Params: none.
- Returns: ordered `dict[str, str]` keyed by lowercased package name; insertion order matches the file (preserves the order the `Pinned deps: …` line is printed in).
- Side effects: reads `REQUIREMENTS` text once.
- Errors (all via `sys.exit`, no exception):
  - File missing → `missing requirements-sidecar.txt; cannot verify build deps`
  - Any non-comment, non-blank line that doesn't match `^name==version$` (extras, markers, `>=`, URLs, …) → `requirements-sidecar.txt:N: only \`name==version\` pins are allowed, got: '<raw>'`
  - File has no pins → `requirements-sidecar.txt: no pins found`

**Calls**: `Path.exists()`, `Path.read_text(encoding="utf-8")`, `re.compile(r"^\s*([A-Za-z0-9_.\-]+)\s*==\s*(\S+)\s*$").match`, `str.lower()`, `sys.exit`.

### `ensure_pinned_deps() -> dict[str, str]` ([`build_sidecar.py:65-84`](../../../spikes/pyinstaller_sidecar/build_sidecar.py#L65-L84))

**Purpose**: Verify every package in `requirements-sidecar.txt` is installed at the exact pinned version. Fail fast otherwise. Returns the pin map so `__main__` can echo a one-line summary.

**Contract**:
- Params: none.
- Returns: the same dict produced by `_pinned_versions()` once verification passes.
- Side effects: reads installed-package metadata via `importlib.metadata.version(name)` for each pin. **Does NOT touch the host Python environment — no `pip install`, no `subprocess` call, no auto-recovery.**
- Errors (all via `sys.exit`):
  - Package missing → `<name>: not installed (pinned==<want>)\n  pip install -r requirements-sidecar.txt`
  - Version mismatch → `<name>: version mismatch (installed=<got>, pinned=<want>)\n  pip install -r requirements-sidecar.txt`

**Calls**: `_pinned_versions()`, `importlib.metadata.version(name)` (catches `PackageNotFoundError`), `sys.exit`.

### `clean()` ([`build_sidecar.py:87-94`](../../../spikes/pyinstaller_sidecar/build_sidecar.py#L87-L94))

**Purpose**: Remove previous build artifacts so each run starts from a clean state.

**Contract**:
- Params: none.
- Returns: `None`.
- Side effects: deletes (if present) `DIST/`, `BUILD/`, and the `.spec` file. Prints `已清除: <name>` to stderr for each removal.
- Errors: `OSError`/`PermissionError` propagates (no catch).

**Calls**: `Path.exists()`, `Path.is_dir()`, `shutil.rmtree(p)`, `Path.unlink()`.

**Note**: `clean()` removes the **entire** `app/src-tauri/binaries/` directory, not just the sidecar exe. If other binaries land there later, this becomes destructive — `(unverified; appears to be acceptable today because the directory only holds the sidecar)`.

### `build()` ([`build_sidecar.py:97-126`](../../../spikes/pyinstaller_sidecar/build_sidecar.py#L97-L126))

**Purpose**: Invoke PyInstaller to package `sidecar/sidecar.py` into a single-file Windows console exe.

**Contract**:
- Params: none.
- Returns: `None`.
- Preconditions: `ENTRY` must exist; otherwise prints an error and `sys.exit(1)`.
- Side effects: runs PyInstaller as a subprocess; produces `DIST/<APP_NAME>.exe`, populates `BUILD/`, writes `.spec` to `SPEC`.
- Errors: `subprocess.CalledProcessError` propagates if PyInstaller fails.

**Calls**: `Path.exists()`, `subprocess.check_call(cmd, cwd=REPO_ROOT)`.

PyInstaller command ([`build_sidecar.py:103-124`](../../../spikes/pyinstaller_sidecar/build_sidecar.py#L103-L124)):

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

### `post_build()` ([`build_sidecar.py:129-146`](../../../spikes/pyinstaller_sidecar/build_sidecar.py#L129-L146))

**Purpose**: Verify the exe was produced; print size, usage hint, and log-dir hint to stderr.

**Contract**:
- Params: none.
- Returns: `None`.
- Postconditions: exits with status `1` if `DIST/<APP_NAME>.exe` does not exist after `build()`.
- Side effects: stderr output only. Does **not** copy, sign, or move the artifact (the build step already wrote it into the final Tauri location).
- Errors: `OSError` from `stat()` propagates if the file vanishes between `exists()` and `stat()`.

**Calls**: `Path.exists()`, `Path.stat()`, `print(..., file=sys.stderr)`.

### Entry point: `if __name__ == "__main__":` ([`build_sidecar.py:149-155`](../../../spikes/pyinstaller_sidecar/build_sidecar.py#L149-L155))

Sequence:
1. `pinned = ensure_pinned_deps()` — fail fast on missing / mismatched packages.
2. Print `Pinned deps: <name>==<ver>, …` (joined from the returned dict) to stderr.
3. `clean()` — wipe previous outputs.
4. `build()` — run PyInstaller.
5. `post_build()` — verify + print usage hints.

**CLI args consumed**: none — the script takes no positional or option arguments.

**Environment variables consumed**: none directly. (`post_build()` mentions `JAVDB_LOG_DIR` and `%LOCALAPPDATA%` as **runtime** hints for the produced exe, not for the build itself.)

**Output paths produced**:
- `app/src-tauri/binaries/sidecar-x86_64-pc-windows-msvc.exe` — the artifact (ends up in the Tauri layout directly).
- `spikes/pyinstaller_sidecar/build/` — PyInstaller intermediates.
- `spikes/pyinstaller_sidecar/sidecar-x86_64-pc-windows-msvc.spec` — generated spec file.

**Files explicitly NOT bundled**: `.env`, `cookies.txt` (no `--add-data` flags). Confirmed by absence in [`build_sidecar.py:103-124`](../../../spikes/pyinstaller_sidecar/build_sidecar.py#L103-L124).

---

## 3. Build pipeline summary

End-to-end, from invocation to artifact:

1. **Invocation** — `npm run sidecar:build` (or `python spikes/pyinstaller_sidecar/build_sidecar.py` directly).
2. **Pinned-deps check** — `ensure_pinned_deps()` parses [`requirements-sidecar.txt`](../../../requirements-sidecar.txt) and verifies every `name==version` against `importlib.metadata.version(name)`. Any missing or mismatched package exits with a `pip install -r requirements-sidecar.txt` hint; no implicit `pip install` is performed.
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

## Summary

The sidecar build pipeline is a single Python script ([`build_sidecar.py`](../../../spikes/pyinstaller_sidecar/build_sidecar.py)) that verifies pinned Python deps, then shells out to PyInstaller `--onefile --console` and writes the artifact straight into the Tauri `externalBin` layout — no separate copy step, no `.env` or `cookies.txt` bundling.

The runtime protocol the Tauri backend uses to talk to the produced `sidecar.exe` is documented in [`sidecar-runtime.md`](sidecar-runtime.md), not here.

### Resolved historical issues (M9)

- ~~`driver_rust` constants (`SIDECAR_NAME = "sidecar.exe"`, `dist/...` path walker) drift from the M3 output layout.~~ **RESOLVED M9 Phase 8-C**: the entire `driver_rust/` spike harness was deleted; its argv-style contract was incompatible with the live JSONL daemon and could not smoke-test the M9 sidecar.
- ~~`ensure_pyinstaller()` performs implicit `pip install` and only pins PyInstaller, leaving other deps to ambient PyPI state.~~ **RESOLVED M9 Phase 8-B**: replaced by `ensure_pinned_deps()`, which fails fast against [`requirements-sidecar.txt`](../../../requirements-sidecar.txt) and never mutates the host environment.
