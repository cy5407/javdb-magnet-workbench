#!/usr/bin/env python3
"""Verify P1.2 deps bumps applied correctly."""
import sys
from pathlib import Path

sidecar = Path("requirements-sidecar.txt").read_text(encoding="utf-8")
ci = Path("requirements-ci.txt").read_text(encoding="utf-8")

errors: list[str] = []

# Sidecar must NOT contain old pins
for old in ["curl_cffi==0.14.0", "requests==2.32.5", "urllib3==2.6.3"]:
    if old in sidecar:
        errors.append(f"old pin still present in requirements-sidecar.txt: {old}")

# Sidecar must contain new pins (lower-bound form)
for new in ["curl_cffi>=0.15.0", "requests>=2.33.0", "urllib3>=2.7.0"]:
    if new not in sidecar:
        errors.append(f"new pin missing in requirements-sidecar.txt: {new}")

# CI: pytest bump
if "pytest==8.3.4" in ci:
    errors.append("old pin still present in requirements-ci.txt: pytest==8.3.4")
if "pytest>=9.0.3" not in ci:
    errors.append("new pin missing in requirements-ci.txt: pytest>=9.0.3")

if errors:
    for e in errors:
        print(f"FAIL: {e}", file=sys.stderr)
    sys.exit(1)

print("OK: all deps bumps applied correctly")
sys.exit(0)
