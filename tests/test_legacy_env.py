"""Tests for the legacy ``.env`` parser used by the retired tkinter GUI.

``load_env`` was originally exported from ``realdebrid.py`` so the
production module pulled it in too (F-06). Hardening moved it to
``legacy/_legacy_env.py``; these tests followed the function.
"""

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from legacy._legacy_env import load_env  # noqa: E402


class LoadEnv(unittest.TestCase):
    def test_missing_file_returns_empty(self):
        self.assertEqual(load_env(Path("/no/such/path.env")), {})

    def test_parses_pairs_and_strips_quotes(self):
        with tempfile.NamedTemporaryFile(
            "w", delete=False, suffix=".env", encoding="utf-8"
        ) as tmp:
            tmp.write("# this is a comment\n")
            tmp.write("\n")
            tmp.write("RD_API_TOKEN=abc-123\n")
            tmp.write('QUOTED="hello world"\n')
            tmp.write("SQUOTED='single'\n")
            tmp.write("no_equals_sign\n")
            tmp.write("PADDED  =   spaced   \n")
            path = Path(tmp.name)
        try:
            env = load_env(path)
        finally:
            path.unlink()
        self.assertEqual(env["RD_API_TOKEN"], "abc-123")
        self.assertEqual(env["QUOTED"], "hello world")
        self.assertEqual(env["SQUOTED"], "single")
        self.assertEqual(env["PADDED"], "spaced")
        self.assertNotIn("no_equals_sign", env)


if __name__ == "__main__":
    unittest.main(verbosity=2)
