#!/usr/bin/env python3
"""Verify P2.4 + P2.5 config cleanup applied correctly."""
import re
import sys
from pathlib import Path

errors: list[str] = []

cargo = Path("app/src-tauri/Cargo.toml").read_text(encoding="utf-8")
# All three features should be present in the keyring line. Parse line-by-line
# instead of one big regex over the full file — keeps the inner pattern
# bounded to a single line and avoids the .* + later-anchor shape that
# SonarCloud flags as polynomial-backtracking (S5852).
keyring_line = next(
    (ln for ln in cargo.splitlines() if ln.lstrip().startswith("keyring")),
    "",
)
m = re.search(r"features\s*=\s*\[([^\]]*)\]", keyring_line)
if not m:
    errors.append("Cargo.toml: keyring features array not found")
else:
    feats = m.group(1)
    for needed in ("windows-native", "apple-native", "linux-native-async-persistent"):
        if needed not in feats:
            errors.append(f"Cargo.toml keyring features missing: {needed}")

tauri = Path("app/src-tauri/tauri.conf.json").read_text(encoding="utf-8")
# targets should be empty array
if re.search(r'"targets"\s*:\s*\[\s*"msi"\s*\]', tauri):
    errors.append('tauri.conf.json still has "targets": ["msi"]')
if not re.search(r'"targets"\s*:\s*\[\s*\]', tauri):
    errors.append('tauri.conf.json "targets": [] not found')

if errors:
    for e in errors:
        print(f"FAIL: {e}", file=sys.stderr)
    sys.exit(1)

print("OK: keyring features + tauri targets cleaned up")
sys.exit(0)
