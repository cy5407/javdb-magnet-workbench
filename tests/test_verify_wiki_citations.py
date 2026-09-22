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
        """本專案的每一筆引用都還對得上現場程式碼。

        斷言的是「零個 finding」，不是「exit 0」。正典的 exit 2 代表「至少有一份
        pattern 完全沒有引用」——那是覆蓋率訊號，跟「現有引用漂掉了」是兩件事。
        混成一個斷言的代價是：為了讓純敘述的 pattern 過關，會有人去補假引用。
        """
        docs = sorted((ROOT / ".agents" / "wiki" / "patterns").glob("*.md"))
        self.assertTrue(docs, "找不到任何 pattern，閘門不能把空集合讀成通過")
        findings = [f for doc in docs for f in verifier.check_document(doc, ROOT)]
        self.assertEqual(findings, [], f"引用漂移：{findings}")

    def test_uncited_patterns_are_an_explicit_allowlist(self):
        """沒有程式碼證據的 pattern 要逐篇列名，新增一篇沒引用的就要紅。

        允許清單裡的是純架構敘述，本來就沒有可引用的程式碼；硬補引用只會製造
        假證據。但清單必須是明示的，否則「零引用」會靜悄悄地變成常態。
        """
        prose_only = {"wikiskill_architecture_and_experience_compilation.md"}
        docs = sorted((ROOT / ".agents" / "wiki" / "patterns").glob("*.md"))
        uncited = {d.name for d in docs
                   if not verifier.parse_citations(d.read_text(encoding="utf-8"))}
        self.assertEqual(uncited, prose_only)

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
        self.assertTrue(any(f.kind == "snippet_not_contiguous" for f in findings))
