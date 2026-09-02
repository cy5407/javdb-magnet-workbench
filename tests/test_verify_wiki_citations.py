"""Contract tests for scripts/verify_wiki_citations.py."""

import sys
import tempfile
import unittest
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import verify_wiki_citations as verifier  # noqa: E402


class VerifyWikiCitations(unittest.TestCase):
    def test_retrieval_gate_is_present_in_each_agent_entrypoint(self):
        for path in (ROOT / "AGENTS.md", ROOT / "CLAUDE.md"):
            self.assertIn(".agents/wiki/index.md", path.read_text(encoding="utf-8"))

        settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
        session_hooks = settings["hooks"]["SessionStart"]
        command = session_hooks[0]["hooks"][0]["command"]
        self.assertIn(".agents/wiki/index.md", command)

        skill = ROOT / ".claude" / "skills" / "wiki-distiller" / "SKILL.md"
        self.assertTrue(skill.is_file())
        self.assertIn("verify_wiki_citations.py", skill.read_text(encoding="utf-8"))

    def test_project_patterns_match_live_source(self):
        self.assertEqual(verifier.main(["--root", str(ROOT)]), 0)

    def test_signature_drift_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "wiki" / "patterns").mkdir(parents=True)
            (root / "source.py").write_text(
                "def response(extra: dict | None = None) -> dict:\n    return {}\n",
                encoding="utf-8",
            )
            (root / "wiki" / "patterns" / "drift.md").write_text(
                "- `source.py:1-2`:\n```python\ndef response(payload: dict) -> dict:\n    return {}\n```\n",
                encoding="utf-8",
            )
            findings = verifier.check_document(root / "wiki" / "patterns" / "drift.md", root)
        self.assertTrue(any(f.kind == "snippet_not_found" for f in findings))
