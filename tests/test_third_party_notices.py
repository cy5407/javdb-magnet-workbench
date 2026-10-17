"""Release licensing: third-party notices generation and the chardet exclusion.

The portable zip must carry THIRD_PARTY_NOTICES.txt (MIT/Apache/BSD require the
copyright notices to travel with binaries), and the LGPL `chardet` must stay
out of the single-file sidecar.exe.
"""

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    # dataclasses resolves string annotations through sys.modules[cls.__module__].
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


gen = _load("gen_third_party_notices", ROOT / "scripts" / "gen_third_party_notices.py")


class RenderNotices(unittest.TestCase):
    def test_identical_license_texts_are_printed_once_and_shared(self):
        mit = "MIT License\n\nCopyright (c) Someone"
        comps = [
            gen.Component("alpha", "1.0", "MIT", "https://a", [mit]),
            gen.Component("beta", "2.0", "MIT", "https://b", [mit]),
        ]
        out = gen.render([("Python", comps)])
        self.assertEqual(out.count("Copyright (c) Someone"), 1)
        self.assertIn("- alpha 1.0 — MIT  https://a 授權全文 [1]", out)
        self.assertIn("- beta 2.0 — MIT  https://b 授權全文 [1]", out)
        self.assertIn("[1] 適用：alpha 1.0, beta 2.0", out)

    def test_component_without_text_points_to_source(self):
        out = gen.render([("Rust", [gen.Component("gamma", "0.1", "BSL-1.0", "https://g")])])
        self.assertIn("- gamma 0.1 — BSL-1.0  https://g（套件未附授權全文，條款見來源網址）", out)


class CollectPython(unittest.TestCase):
    def setUp(self):
        self.comps = {gen._norm(c.name): c for c in gen.collect_python()}

    def test_runtime_dependencies_listed_with_license_text(self):
        for name in ("requests", "beautifulsoup4", "curl-cffi", "certifi", "urllib3"):
            with self.subTest(name=name):
                self.assertIn(name, self.comps)
                self.assertTrue(self.comps[name].texts, f"{name} has no license text")

    def test_lgpl_chardet_and_build_only_tools_are_not_listed(self):
        for name in ("chardet", "pyinstaller", "altgraph", "pefile", "setuptools"):
            with self.subTest(name=name):
                self.assertNotIn(name, self.comps)

    def test_chardet_not_listed_even_if_pinned_again(self):
        # The build excludes chardet from sidecar.exe, so the notices must not
        # claim it ships even if someone re-adds the pin.
        with mock.patch.object(gen, "_requirement_roots", return_value=["requests", "chardet"]):
            names = {gen._norm(c.name) for c in gen.collect_python()}
        self.assertIn("requests", names)
        self.assertNotIn("chardet", names)

    def test_bootloader_and_interpreter_are_listed(self):
        self.assertIn("pyinstaller-bootloader", self.comps)
        self.assertIn("Bootloader-exception", self.comps["pyinstaller-bootloader"].license)
        self.assertIn("cpython", self.comps)


class MainRefusesIncompleteNotices(unittest.TestCase):
    def test_empty_section_fails_without_writing(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / "THIRD_PARTY_NOTICES.txt"
            with mock.patch.object(gen, "collect_python", return_value=[gen.Component("a", "1", "MIT")]), \
                 mock.patch.object(gen, "collect_rust", return_value=[]), \
                 mock.patch.object(gen, "collect_frontend", return_value=[gen.Component("b", "1", "MIT")]):
                rc = gen.main(["gen", str(target)])
            self.assertEqual(rc, 1)
            self.assertFalse(target.exists())


class MainRestrictsOutputPath(unittest.TestCase):
    def _run(self, allowed: Path, target: Path) -> int:
        one = [gen.Component("a", "1", "MIT")]
        with mock.patch.object(gen, "ALLOWED_OUTPUT_DIR", allowed), \
             mock.patch.object(gen, "collect_python", return_value=one), \
             mock.patch.object(gen, "collect_rust", return_value=one), \
             mock.patch.object(gen, "collect_frontend", return_value=one):
            return gen.main(["gen", str(target)])

    def test_writes_inside_release_dir(self):
        with tempfile.TemporaryDirectory() as d:
            allowed = Path(d) / "release"
            (allowed / "JavDBMagnet").mkdir(parents=True)
            target = allowed / "JavDBMagnet" / "THIRD_PARTY_NOTICES.txt"
            self.assertEqual(self._run(allowed, target), 0)
            self.assertIn("- a 1 — MIT", target.read_text(encoding="utf-8"))

    def test_refuses_path_outside_release_dir(self):
        with tempfile.TemporaryDirectory() as d:
            allowed = Path(d) / "release"
            allowed.mkdir()
            for target in (Path(d) / "elsewhere.txt", allowed / ".." / "escape.txt"):
                with self.subTest(target=str(target)):
                    self.assertEqual(self._run(allowed, target), 2)
                    self.assertFalse(target.exists())


class ChardetStaysOutOfSidecar(unittest.TestCase):
    def test_requirements_do_not_install_chardet(self):
        lines = (ROOT / "requirements-sidecar.txt").read_text(encoding="utf-8").splitlines()
        pins = [l.split("==")[0].strip().lower() for l in lines if l.strip() and not l.startswith("#")]
        self.assertNotIn("chardet", pins)

    def test_pyinstaller_argv_excludes_chardet(self):
        build_sidecar = _load("build_sidecar_under_test",
                              ROOT / "spikes" / "pyinstaller_sidecar" / "build_sidecar.py")
        with mock.patch.object(build_sidecar.subprocess, "check_call") as call:
            build_sidecar.build()
        argv = call.call_args.args[0]
        pairs = list(zip(argv, argv[1:]))
        self.assertIn(("--exclude-module", "chardet"), pairs)


if __name__ == "__main__":
    unittest.main()
