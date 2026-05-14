"""Retired Python sources, kept for historical reference only.

Modules under `legacy/` are NOT part of the production runtime. The shipped
JavDBMagnet app is a Tauri/Svelte desktop with a Rust backend and a Python
sidecar daemon (`sidecar/sidecar.py`). Anything in this package was
superseded by that stack but preserved here so future readers can study
the original design without spelunking through `git log`.

Do not import from `legacy.*` in production code, build scripts, or
sidecar bundles. Tests may import from here only when verifying historical
contracts (e.g. that an older module still doesn't auto-init logging).
"""
