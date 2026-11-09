"""Keeps docs/first-game.md honest: what the guide shows is what builds and works.

Without a toolchain the structural tests still run. With one (CPCT_NEXT_PATH or a managed install,
as `glasnost test` provides) every step is applied over a fresh project, in order, and built.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "docs" / "first-game"))

import build_examples  # noqa: E402
import glasnost  # noqa: E402
import glasnost_project as gp  # noqa: E402
import project_config  # noqa: E402
from test_glasnost import quiet_runner  # noqa: E402
from test_glasnost_project import real_toolchain  # noqa: E402

GUIDE = ROOT / "docs" / "first-game.md"
STEPS = ROOT / "docs" / "first-game"
STEP_NAMES = ("step1", "step2", "step3")
SNIPPET = re.compile(r"<!-- guia: (?P<file>[\w./]+) -->\n```\w*\n(?P<body>.*?)\n```", re.S)


def tail_runner(out):
    """Like quiet_runner, but a failing command leaves the tail of its output in `out`.

    A build that fails only on another machine (CI) is undiagnosable from "step1: " alone.
    """
    def runner(command, **kwargs):
        if "capture_output" in kwargs:
            return quiet_runner(command, **kwargs)
        result = glasnost.default_runner(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, **kwargs)
        if result.returncode:
            out.write("\n".join(["$ " + " ".join(map(str, command)), *(result.stdout or "").splitlines()[-40:]]))
        return result
    return runner


def run(argv, cwd=None, env=None):
    out, err = io.StringIO(), io.StringIO()
    previous = os.getcwd()
    if cwd:
        os.chdir(cwd)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                mock.patch.dict(os.environ, env or {}, clear=False):
            try:
                code = glasnost.main(["--lang", "en", *argv], root=ROOT, runner=tail_runner(out))
            except SystemExit as exit_:
                code = exit_.code
    finally:
        os.chdir(previous)
    return code, out.getvalue(), err.getvalue()


class GuideText(unittest.TestCase):
    def setUp(self):
        self.text = GUIDE.read_text(encoding="utf-8")
        self.snippets = [(m["file"], m["body"]) for m in SNIPPET.finditer(self.text)]

    def test_the_guide_has_a_meaningful_number_of_snippets(self):
        self.assertGreaterEqual(len(self.snippets), 15)

    def test_every_snippet_exists_verbatim_in_the_file_it_names(self):
        """The text can never drift from the code that is built.

        A snippet may show several excerpts of one file separated by a blank line; each excerpt
        must appear, contiguous and unchanged, in the file.
        """
        for name, body in self.snippets:
            path = STEPS / name
            self.assertTrue(path.is_file(), f"the guide names {name}, which does not exist")
            content = path.read_text(encoding="utf-8")
            for excerpt in body.split("\n\n"):
                with self.subTest(name, first_line=excerpt.splitlines()[0]):
                    self.assertIn(excerpt, content, f"an excerpt of the guide is not in {name}")

    def test_every_text_file_of_every_step_is_shown_in_the_guide(self):
        for step in STEP_NAMES:
            for path in sorted((STEPS / step).rglob("*")):
                if not path.is_file() or path.suffix == ".png":
                    continue
                relative = f"{step}/{path.relative_to(STEPS / step)}"
                with self.subTest(relative):
                    self.assertTrue(
                        any(name == relative for name, _ in self.snippets) or f"({'first-game/' + relative})" in self.text
                        or f"[`{relative}`]" in self.text or f"`{path.name}`" in self.text,
                        f"{relative} is not mentioned in the guide")

    def test_links_to_files_and_images_resolve(self):
        for target in re.findall(r"\]\((first-game/[^)#]+)\)", self.text):
            with self.subTest(target):
                self.assertTrue((ROOT / "docs" / target).exists(), target)

    def test_the_commands_it_teaches_exist(self):
        parser = glasnost.build_parser("en")
        shell_blocks = re.findall(r"```sh\n(.*?)\n```", self.text, re.S)
        commands = set(re.findall(r"^\s*glasnost ([a-z-]+)", "\n".join(shell_blocks), re.M))
        known = set(parser._subparsers._group_actions[0].choices)  # noqa: SLF001
        self.assertLessEqual(commands, known)
        self.assertTrue({"new", "build", "run", "config"} <= commands)


class StepFiles(unittest.TestCase):
    """Structure that needs no toolchain."""

    def test_every_step_manifest_is_accepted_by_the_build_validations(self):
        example = json.loads(gp.render_project(gp.Spec("nave", "x"), "t", "en")["example.json"])
        for step in ("step2", "step3"):
            example = json.loads((STEPS / step / "example.json").read_text())
            with self.subTest(step):
                profile = json.loads((ROOT / "framework" / "profiles" / example["profile"]).read_text())
                capabilities = project_config.parse_capabilities(example, profile["mode"])
                modules = build_examples.effective_modules("nave", example["modules"], capabilities)
                build_examples._validate_ecs_systems("nave", example, modules)  # noqa: SLF001
                for module in modules:
                    self.assertTrue((ROOT / "framework" / "src" / module).is_file(), module)

    def test_each_step_only_adds_to_the_previous_manifest(self):
        base = json.loads(gp.render_project(gp.Spec("nave", "x"), "t", "en")["example.json"])
        two = json.loads((STEPS / "step2" / "example.json").read_text())
        three = json.loads((STEPS / "step3" / "example.json").read_text())
        self.assertEqual(set(two["modules"]) - set(base["modules"]), {"core/ecs_animation.s"})
        self.assertEqual(set(three["modules"]) - set(two["modules"]), {"core/ecs_collision.s"})
        self.assertEqual(two["ecs"]["components"], base["ecs"]["components"] + ["animation"])
        self.assertEqual(three["ecs"]["components"], two["ecs"]["components"] + ["collision"])
        for key in gp.CONFIG_OWNED:
            self.assertEqual(two[key], base[key])
            self.assertEqual(three[key], base[key])

    def test_the_pngs_only_use_palette_colours_and_match_the_ascii_art(self):
        try:
            from PIL import Image
        except ModuleNotFoundError:
            self.skipTest("Pillow is not installed")
        import make_art
        self.assertEqual(make_art.SHIP, gp.SHIP_ART)    # the art of the template is the art of the guide
        self.assertEqual(make_art.DRONE, gp.DRONE_ART)
        allowed = set(make_art.PENS.values())
        for label, path, tiles in (
                ("template", ROOT / "framework" / "templates" / "ecs-welcome" / "assets" / "src" / "sprites.png",
                 [make_art.SHIP, make_art.DRONE]),
                ("step2", STEPS / "step2" / "assets" / "src" / "sprites.png",
                 [make_art.SHIP, make_art.SHIP2, make_art.DRONE, make_art.DRONE2])):
            with self.subTest(label):
                image = Image.open(path).convert("RGB")
                self.assertEqual(image.size, (8 * len(tiles), 8))
                expected = make_art.sheet(tiles)
                for y in range(8):
                    for x in range(image.size[0]):
                        self.assertIn(image.getpixel((x, y)), allowed)
                        self.assertEqual(image.getpixel((x, y)), expected.getpixel((x, y)), (x, y))

    def test_the_map_of_step1_is_a_valid_tmx_the_template_geometry_accepts(self):
        import xml.etree.ElementTree as ET
        for label, path in (("template", ROOT / "framework" / "templates" / "ecs-welcome" / "assets" / "src" / "level.tmx"),
                            ("step1", STEPS / "step1" / "assets" / "src" / "level.tmx")):
            with self.subTest(label):
                layer = ET.parse(path).getroot().find("layer")
                self.assertEqual((layer.get("name"), layer.get("width"), layer.get("height")), ("background", "20", "6"))
                ids = [int(v) for v in layer.find("data").text.replace("\n", "").split(",") if v.strip()]
                self.assertEqual(len(ids), 120)
                self.assertTrue(all(0 <= v <= 4 for v in ids))   # tiles.png has four tiles

    def test_the_palette_of_the_guide_is_the_one_the_art_assumes(self):
        values = json.loads((ROOT / "framework" / "templates" / "ecs-welcome" / "assets" / "palette.json").read_text())["values"]
        # pens used by make_art: 0 black, 1 bright magenta, 3 red, 6 bright yellow, 10 bright cyan, 15 white
        self.assertEqual([values[p] for p in (0, 1, 3, 6, 10, 15)], [0, 8, 3, 24, 20, 26])


class ExampleMatchesGuide(unittest.TestCase):
    """examples/nave is the finished game of the guide: it cannot drift from the steps."""

    EXAMPLE = ROOT / "examples" / "nave"

    def overlay(self) -> dict[str, bytes]:
        files: dict[str, bytes] = {}
        for step in STEP_NAMES:
            for path in sorted((STEPS / step).rglob("*")):
                if path.is_file():
                    files[str(path.relative_to(STEPS / step))] = path.read_bytes()
        return files

    def test_every_file_of_the_steps_is_in_the_example_unchanged(self):
        for relative, content in self.overlay().items():
            with self.subTest(relative):
                self.assertEqual((self.EXAMPLE / relative).read_bytes(), content)

    def test_the_generated_files_are_what_glasnost_generates(self):
        title = json.loads(gp.render_project(gp.Spec("nave", "mi primer juego"), "x", "es")["glasnost.project.json"])["title"]
        self.assertEqual((self.EXAMPLE / "generated" / "project.inc").read_text(), gp.project_include(title))
        example = json.loads((self.EXAMPLE / "example.json").read_text())
        self.assertEqual((self.EXAMPLE / "generated" / "ecs_profile.inc").read_text(), gp.ecs_profile_include(example))

    def test_it_has_no_files_the_guide_does_not_explain(self):
        brought_by_new = {path for path in gp.render_project(gp.Spec("nave", "x"), "t", "en")
                          if path.startswith("assets/") and "generated" not in path}
        expected = (set(self.overlay()) | brought_by_new
                    | {"Makefile", "generated/project.inc", "generated/ecs_profile.inc", "README.md"})
        found = {str(p.relative_to(self.EXAMPLE)) for p in self.EXAMPLE.rglob("*")
                 if p.is_file() and "assets/generated" not in str(p)}
        self.assertEqual(found, expected)

    def test_the_assets_that_new_brings_are_unchanged_in_the_example_unless_a_step_replaces_them(self):
        replaced = set(self.overlay())
        for path, content in gp.render_project(gp.Spec("nave", "x"), "t", "en").items():
            if path.startswith("assets/") and "generated" not in path and path not in replaced:
                with self.subTest(path):
                    self.assertEqual((self.EXAMPLE / path).read_bytes(), content)

    def test_it_is_not_a_glasnost_project(self):
        """It is an example of the framework (built by make); it carries no project metadata."""
        self.assertFalse((self.EXAMPLE / gp.PROJECT_FILE).exists())

    def test_the_converted_assets_are_committed_so_a_clean_checkout_needs_no_img2cpc(self):
        generated = self.EXAMPLE / "assets" / "generated"
        for name in ("assets.s", "assets.inc", "pipeline.json"):
            self.assertTrue((generated / name).is_file(), name)
        self.assertIn("game_ship_pixels", (generated / "assets.s").read_text())


@unittest.skipUnless(real_toolchain(), "needs a CPCTelera Next toolchain")
class StepsBuild(unittest.TestCase):
    """The reader's path, executed: new, then each step applied over the previous one, then built."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="glasnost-guide-"))
        cls.env = {"CPCT_NEXT_PATH": str(real_toolchain())}
        code, out, err = run(["new", "nave", "--dir", str(cls.tmp), "--no-git", "--title", "mi primer juego"], env=cls.env)
        assert code == 0, out + err
        cls.folder = cls.tmp / "nave"
        cls.sizes: dict[str, int] = {}
        cls.states: dict[str, dict] = {}
        for step in STEP_NAMES:
            # shutil.copy, not copy2: a reader copying a step gets fresh mtimes. Keeping the
            # old ones makes make link the stale object that `glasnost new` already built.
            shutil.copytree(STEPS / step, cls.folder, dirs_exist_ok=True, copy_function=shutil.copy)
            cls.states[step] = {"stale_before_config": gp.check_project(cls.folder)}
            code, out, err = run(["config"], cwd=cls.folder, env=cls.env)
            assert code == 0, out + err
            code, out, err = run(["build"], cwd=cls.folder, env=cls.env)
            assert code == 0, f"{step}: " + out + err
            binary = next((cls.folder / "build").rglob("nave.bin"))
            cls.sizes[step] = binary.stat().st_size
            cls.states[step]["after"] = gp.check_project(cls.folder)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_every_step_builds_and_leaves_the_project_consistent(self):
        for step in STEP_NAMES:
            with self.subTest(step):
                self.assertEqual(self.states[step]["after"], [])
                for name in ("nave.bin", "nave.cdt", "nave.dsk"):
                    self.assertTrue(any((self.folder / "build").rglob(name)), name)

    def test_changing_the_manifest_makes_the_profile_stale_until_config_runs(self):
        """What the guide tells the reader to do at steps 2 and 3 is needed, and works."""
        self.assertEqual(self.states["step1"]["stale_before_config"], [])
        for step in ("step2", "step3"):
            with self.subTest(step):
                self.assertTrue(any("ecs_profile.inc is stale" in p for p in self.states[step]["stale_before_config"]))

    def test_each_step_grows_the_binary_by_a_sensible_amount(self):
        self.assertLess(self.sizes["step1"], self.sizes["step2"])
        self.assertLess(self.sizes["step2"], self.sizes["step3"])
        self.assertLess(self.sizes["step3"], 12_000)   # with the tilemap and its tileset; far from the 64 KB limit

    def test_the_template_art_converts_to_the_bytes_the_guide_art_encodes_to(self):
        """The PNG conversion of what `glasnost new` ships reproduces the hand-encoded bytes."""
        folder = self.tmp / "step1check"
        code, out, err = run(["new", "nave", "--dir", str(folder), "--no-git", "--no-build"], env=self.env)
        self.assertEqual(code, 0, out + err)
        project = folder / "nave"
        code, out, err = run(["build"], cwd=project, env=self.env)
        self.assertEqual(code, 0, out + err)
        generated = (project / "assets" / "generated" / "assets.s").read_text()

        def symbol_bytes(name: str) -> bytes:
            match = re.search(rf"{name}::?\n((?:\s+\.db [^\n]+\n)+)", generated)
            self.assertIsNotNone(match, name)
            return bytes(int(v, 16) for v in re.findall(r"0x([0-9A-Fa-f]{2})", match.group(1)))

        def hand_written(art):
            return bytes(gp.encode_mode0(*(gp.ART_PENS[c] for c in row[i:i + 2]))
                         for row in art for i in range(0, 8, 2))

        self.assertEqual(symbol_bytes("game_ship_pixels"), hand_written(gp.SHIP_ART))
        self.assertEqual(symbol_bytes("game_drone_pixels"), hand_written(gp.DRONE_ART))

    def test_the_guide_game_has_the_public_symbols_the_smoke_test_reads(self):
        noi = next((self.folder / "build").rglob("nave.noi")).read_text()
        for symbol in ("game_status", "game_storage", "game_hits", "game_player"):
            self.assertRegex(noi, rf"DEF {symbol} 0x[0-9A-Fa-f]+")


if __name__ == "__main__":
    unittest.main()
