#!/usr/bin/env python3
"""Verify scripts/build-release.ps1 no longer references origin/dev."""
import sys
from pathlib import Path

target = Path("scripts/build-release.ps1")
text = target.read_text(encoding="utf-8")
if "origin/dev" in text:
    print(f"FAIL: 'origin/dev' still present in {target}", file=sys.stderr)
    sys.exit(1)
print(f"OK: {target} no longer references origin/dev")
sys.exit(0)
