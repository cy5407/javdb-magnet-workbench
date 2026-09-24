#!/usr/bin/env python3
"""薄殼：把引用閘門轉給中央庫部署下來的那一份。

為什麼是殼而不是副本：2026-09-22 量到這裡原本放著一份 185 行的舊副本，而
`.agent-hooks/verify_wiki_citations.py` 是中央庫部署的 273 行正典。AGENTS.md
與 CLAUDE.md 叫人跑的是**這個路徑**，所以大家跑的一直是舊版——對同一份 wiki，
舊版回報「0 個問題」，正典回報 5 個。那 5 個是真的：兩筆行號漂掉、三筆把兩段
不連續的程式塞進同一個區塊。

形狀與 .agents/wiki/patterns/central_catalog_and_preflight_deployment.md 講的同類：
好的那一份部署了但沒人叫它，大家叫的那一份是舊的。副本留著就會再漂一次，
所以這裡不留副本。

正典由中央庫的 preflight/assemble 管理，要改請改
my-codex-guides/catalog/hooks/wiki-citation-gate/。
"""
import importlib.util
import sys
from pathlib import Path

CANON = Path(__file__).resolve().parent.parent / ".agent-hooks" / "verify_wiki_citations.py"

if not CANON.is_file():
    sys.exit(f"找不到引用閘門正典：{CANON}\n"
             "  請先從中央庫部署："
             "node scripts/assemble.mjs --profile javdb-magnet-workbench")

_spec = importlib.util.spec_from_file_location("_wiki_citation_gate_canon", CANON)
_canon = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_canon)

# 轉出正典的公開介面，讓 `import verify_wiki_citations as verifier` 照舊可用。
CITATION_RE = _canon.CITATION_RE
FENCE_RE = _canon.FENCE_RE
LOOKBACK_LINES = _canon.LOOKBACK_LINES
Citation = _canon.Citation
Finding = _canon.Finding
parse_citations = _canon.parse_citations
check_document = _canon.check_document
resolve_wiki = _canon.resolve_wiki
main = _canon.main

if __name__ == "__main__":
    sys.exit(main())
