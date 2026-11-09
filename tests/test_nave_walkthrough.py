"""docs/nave-walkthrough.md cannot drift from the code it explains.

Fast checks (no toolchain): every code block is a literal copy of examples/nave, every routine
of main.s is explained, the links resolve, the exercises' text is the code in nave_exercises.py.
With a CPCTelera Next toolchain it also builds the two exercises as a reader would.
"""

from __future__ import annotations

import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path[:0] = [str(ROOT / "tools" / d) for d in ("glasnost", "build", "dev")]

import glasnost  # noqa: E402
import nave_exercises as ex  # noqa: E402
from test_glasnost_project import real_toolchain as toolchain  # noqa: E402

DOC = ROOT / "docs" / "nave-walkthrough.md"
NAVE = ROOT / "examples" / "nave"
BLOCK = re.compile(r"<!-- codigo: (?P<file>[\w./]+) -->\n```\w*\n(?P<body>.*?)\n```", re.S)


def run(args, cwd=None, env=None):
    out, err = io.StringIO(), io.StringIO()
    previous, saved = Path.cwd(), dict(os.environ)
    try:
        if cwd:
            os.chdir(cwd)
        os.environ.update(env or {})
        with redirect_stdout(out), redirect_stderr(err):
            try:
                code = glasnost.main(["--lang", "en", *args])
            except SystemExit as exit_:
                code = exit_.code
    finally:
        os.chdir(previous)
        os.environ.clear()
        os.environ.update(saved)
    return code, out.getvalue(), err.getvalue()


class WalkthroughText(unittest.TestCase):
    def setUp(self):
        self.text = DOC.read_text(encoding="utf-8")
        self.blocks = [(m["file"], m["body"]) for m in BLOCK.finditer(self.text)]

    def test_it_has_a_meaningful_number_of_code_blocks(self):
        self.assertGreaterEqual(len(self.blocks), 15)

    def test_every_block_is_a_literal_copy_of_the_example(self):
        for name, body in self.blocks:
            content = (NAVE / name).read_text(encoding="utf-8")
            for excerpt in body.split("\n\n"):
                with self.subTest(first_line=excerpt.splitlines()[0]):
                    self.assertIn(excerpt, content)

    def test_every_routine_of_main_s_is_explained(self):
        shown = "\n".join(body for name, body in self.blocks if name == "main.s")
        main = (NAVE / "main.s").read_text(encoding="utf-8")
        routines = re.findall(r"^;; (_\w+)\n;;   [A-Z]", main, re.M)
        self.assertGreaterEqual(len(routines), 8)
        for routine in routines:
            with self.subTest(routine):
                self.assertRegex(shown, rf"(?m)^;; {re.escape(routine)}$")

    def test_the_relative_links_resolve(self):
        for target in re.findall(r"\]\(((?!https?:|#)[^)\s]+)\)", self.text):
            path = (DOC.parent / target.split("#")[0]).resolve()
            with self.subTest(target):
                self.assertTrue(path.exists(), f"{target} does not exist")

    def test_the_exercises_are_the_edits_that_were_built(self):
        for snippet in (ex.SPEED_OLD, ex.SPEED_NEW, ex.CAP_NEW, ex.ROW_LINE, ex.SPAWN_BLOCK):
            with self.subTest(snippet.splitlines()[0]):
                self.assertIn(snippet, self.text)

    def test_the_tables_name_only_real_routines(self):
        main = (NAVE / "main.s").read_text(encoding="utf-8")
        for name in set(re.findall(r"`(fwk_\w+|_game_\w+)`", self.text)):
            with self.subTest(name):
                known = name in main or any(name in p.read_text(errors="ignore")
                                            for p in (ROOT / "framework" / "src").rglob("*.s"))
                self.assertTrue(known, f"{name} is not defined anywhere")

    def test_the_header_example_matches_the_project_format(self):
        sample = self.text.split("## 1. Cómo leer una cabecera", 1)[1].split("```", 2)[1]
        for key in ("In :", "Out:", "Clobbers:", "Notes:"):
            self.assertIn(f";;   {key}", sample)


@unittest.skipUnless(toolchain(), "needs a CPCTelera Next toolchain")
class ExercisesBuild(unittest.TestCase):
    def build(self, edit):
        tmp = Path(tempfile.mkdtemp(prefix="glasnost-walk-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        env = {"CPCT_NEXT_PATH": str(toolchain())}
        folder = ex.project_from_example(tmp, lambda a: run(a, env=env))
        if edit:
            edit(folder)
        for step in (["config"], ["build"]):
            code, out, err = run(step, cwd=folder, env=env)
            self.assertEqual(code, 0, out + err)
        return next((folder / "build").rglob("nave.bin")).stat().st_size

    def test_the_example_as_a_project_builds_to_the_example_binary(self):
        built = self.build(None)
        reference = ROOT / "build" / "nave" / "obj" / "nave.bin"
        if not reference.is_file():   # `make test` builds the examples only after the tests: a clean CI checkout has none yet
            subprocess.run([sys.executable, str(ROOT / "tools" / "build" / "build_examples.py"), "nave"], cwd=ROOT, check=True,
                           env=dict(os.environ, CPCT_NEXT_PATH=str(toolchain())), stdout=subprocess.DEVNULL)
        self.assertEqual(built, reference.stat().st_size)

    def test_exercise_1_builds(self):
        self.assertGreater(self.build(ex.faster_ship), 0)

    def test_exercise_2_builds_and_is_bigger(self):
        base = self.build(None)
        self.assertGreater(self.build(ex.fourth_drone), base)

    def test_exercise_2_without_raising_the_cap_still_builds(self):
        """The failure is at run time (manager full), not at build time: the text says so."""
        self.assertGreater(self.build(lambda f: ex.fourth_drone(f, raise_cap=False)), 0)


if __name__ == "__main__":
    unittest.main()
