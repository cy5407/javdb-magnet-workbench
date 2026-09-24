# Wiki Knowledge Read Gate

Read `CLAUDE.md` for the project's full engineering rules.

Before implementing, debugging, or changing an architecture or cross-layer contract, read `.agents/wiki/index.md`. When an entry matches the task, read its linked pattern before editing; treat its actionable fix as a pre-edit constraint, while live source code and `docs/architecture/contracts/` remain authoritative.

After changing source referenced by a Wiki pattern, run the citation gate (`.venv/bin/python scripts/verify_wiki_citations.py` on Linux/macOS, `.venv\Scripts\python.exe scripts\verify_wiki_citations.py` on Windows) and correct any drift before finishing.
