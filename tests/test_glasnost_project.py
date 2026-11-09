"""Gate tests of `glasnost new` / `glasnost config` and the project generator.

Deterministic and local. Builds that need the real CPCTelera Next toolchain are
skipped when none is available (CPCT_NEXT_PATH or a managed install); everything
else runs against recording runners and a fake toolchain.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools" / d) for d in ("glasnost", "build", "dev")]
sys.path.insert(0, str(ROOT / "tests"))

import build_examples  # noqa: E402
import glasnost  # noqa: E402
import glasnost_project as gp  # noqa: E402
import project_config  # noqa: E402
from test_glasnost import FakeSdk, quiet_runner  # noqa: E402

GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull}


def real_toolchain() -> Path | None:
    """The toolchain these tests may build with, or None."""
    override = os.environ.get("CPCT_NEXT_PATH")
    candidates = [Path(override)] if override else []
    try:
        lock = glasnost.load_lock(ROOT, "en")
        candidates.append(glasnost.managed_root(ROOT, lock) / "cpctelera")
    except glasnost.CliError:
        pass
    for candidate in candidates:
        if (candidate / "cpctelera.lib").is_file() and not glasnost.missing_files(candidate):
            return candidate
    return None


def tree(folder: Path) -> dict[str, str]:
    """Relative path -> sha256 of every file under folder (skipping .git and build)."""
    out = {}
    for path in sorted(folder.rglob("*")):
        parts = path.relative_to(folder).parts
        if path.is_file() and ".git" not in parts and "build" not in parts:
            out["/".join(parts)] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def run(argv, root, runner=quiet_runner, ask=None, interactive=False, env=None, cwd=None):
    out, err = io.StringIO(), io.StringIO()
    previous = os.getcwd()
    if cwd:
        os.chdir(cwd)
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                mock.patch.dict(os.environ, dict(GIT_ENV, **(env or {})), clear=False):
            os.environ.pop("CPCT_NEXT_PATH", None) if not (env and "CPCT_NEXT_PATH" in env) else None
            try:
                code = glasnost.main(["--lang", "en", *argv], root=root, runner=runner,
                                     ask=ask or (lambda prompt: ""), interactive=interactive)
            except SystemExit as exit_:
                code = exit_.code
    finally:
        os.chdir(previous)
    return code, out.getvalue(), err.getvalue()


class Recorder:
    """A runner that records commands and answers 0, except for `fail` prefixes."""

    def __init__(self, fail=()):
        self.calls: list[list[str]] = []
        self.fail = fail

    def __call__(self, command, **kwargs):
        if command[0] == "git":  # git is real so the repository can be inspected
            return quiet_runner(command, **kwargs)
        self.calls.append(list(command))
        code = 3 if any(command[:len(prefix)] == list(prefix) for prefix in self.fail) else 0
        return subprocess.CompletedProcess(command, code, stdout="", stderr="")


class SpecRules(unittest.TestCase):
    def test_names(self):
        for good in ("a", "demo", "my_game2", "a" * 24):
            gp.validate(gp.Spec(good, "T"))
        for bad in ("", "Demo", "2game", "_x", "my-game", "a" * 25, "ñandú", "a b", "../x", "x/y", "con."):
            with self.subTest(bad), self.assertRaises(gp.ProjectError):
                gp.validate(gp.Spec(bad, "T"))

    def test_titles_are_uppercased_squeezed_and_limited_to_the_font(self):
        self.assertEqual(gp.normalize_title("  my   demo  "), "MY DEMO")
        self.assertEqual(gp.normalize_title("go! a-b/c:d>e?f@g 123"), "GO! A-B/C:D>E?F@G 123")
        self.assertEqual(len(gp.normalize_title("x" * 30)), 30)
        for bad in ("", "   ", "x" * 31, 'say "hi"', "ñ", "a;b", "tab\t\x00", 5, None):
            with self.subTest(bad), self.assertRaises(gp.ProjectError):
                gp.normalize_title(bad)

    def test_the_title_can_never_break_out_of_the_assembly_string(self):
        for hostile in ('A"; ld a,#1', "A\\", "A\x00B", "A'B", "A\x1bB"):
            with self.assertRaises(gp.ProjectError):
                gp.validate(gp.Spec("demo", hostile))
        for odd in ("A\nB", "A\tB", "A\r\nB"):  # whitespace becomes one plain space
            self.assertEqual(gp.validate(gp.Spec("demo", odd)).title, "A B")

    def test_profile_and_flags(self):
        with self.assertRaises(gp.ProjectError):
            gp.validate(gp.Spec("demo", "T", profile="experimental"))
        with self.assertRaises(gp.ProjectError):
            gp.validate(gp.Spec("demo", "T", extended_memory="yes"))  # type: ignore[arg-type]
        with self.assertRaises(gp.ProjectError):
            gp.validate(gp.Spec("demo", "T", git=1))  # type: ignore[arg-type]

    def test_amsdos_name_follows_the_name(self):
        self.assertEqual(gp.Spec("demo", "T").amsdos_name, "DEMO")
        self.assertEqual(gp.Spec("a_long_project_name", "T").amsdos_name, "A_LONG_P")

    def test_manifest_is_strict(self):
        good = {"schema": 1, "name": "demo", "title": "hi", "profile": "standard",
                "extended_memory": True, "git": False}
        spec = gp.spec_from_manifest(good)
        self.assertEqual((spec.title, spec.extended_memory, spec.git), ("HI", True, False))
        self.assertEqual(gp.spec_from_manifest({"schema": 1, "name": "demo"}).title, "DEMO")
        for bad in ([], "x", {"schema": 2, "name": "d"}, {"name": "d"}, {"schema": 1},
                    dict(good, extra=1), dict(good, name="Bad Name"), dict(good, title="a*b")):
            with self.subTest(bad), self.assertRaises(gp.ProjectError):
                gp.spec_from_manifest(bad)


class Art(unittest.TestCase):
    @staticmethod
    def decode(byte: int) -> tuple[int, int]:
        left = sum(((byte >> bit) & 1) << index for index, bit in enumerate((7, 5, 3, 1)))
        right = sum(((byte >> bit) & 1) << index for index, bit in enumerate((6, 4, 2, 0)))
        return left, right

    def test_mode0_encoding_round_trips_every_pen_pair(self):
        for left in range(16):
            for right in range(16):
                self.assertEqual(self.decode(gp.encode_mode0(left, right)), (left, right))

    def test_known_mode0_bytes(self):
        self.assertEqual(gp.encode_mode0(0, 0), 0x00)
        self.assertEqual(gp.encode_mode0(15, 15), 0xFF)
        self.assertEqual(gp.encode_mode0(1, 0), 0x80)
        self.assertEqual(gp.encode_mode0(0, 1), 0x40)
        self.assertEqual(gp.encode_mode0(3, 3), 0xC0 | 0x30)

    def test_sprites_are_four_bytes_by_eight_lines_and_show_their_art(self):
        source = gp.sprite_source("_s", gp.SHIP_ART)
        rows = [line for line in source.splitlines() if line.startswith("    .db")]
        self.assertEqual(len(rows), 8)
        for row, art in zip(rows, gp.SHIP_ART):
            self.assertEqual(len(row.split(";")[0].split(",")), 4)
            self.assertTrue(row.endswith("; " + art))

    def test_bad_art_is_rejected(self):
        with self.assertRaises(gp.ProjectError):
            gp.sprite_source("_s", ["short"] * 8)
        with self.assertRaises(gp.ProjectError):
            gp.sprite_source("_s", ["zzzzzzzz"] * 8)


class Rendering(unittest.TestCase):
    def setUp(self):
        self.files = gp.render_project(gp.validate(gp.Spec("demo", "hello")), "9.9.9", "en")

    def test_file_set(self):
        self.assertEqual(sorted(self.files), sorted([
            ".gitignore", "README.md", "common.inc", "example.json", "generated/ecs_profile.inc",
            "generated/project.inc", "glasnost.project.json", "main.s",
            "assets/assets.json", "assets/palette.json", "assets/src/level.tmx",
            "assets/src/sprites.png", "assets/src/tiles.png", "assets/generated/assets.inc",
            "assets/generated/assets.s", "assets/generated/pipeline.json"]))

    def test_rendering_is_deterministic(self):
        again = gp.render_project(gp.Spec("demo", "hello"), "9.9.9", "en")
        self.assertEqual(self.files, again)

    def test_no_placeholder_survives_and_the_art_is_imported_not_inline(self):
        main = self.files["main.s"].decode()
        self.assertNotIn("@@", main)
        self.assertNotIn("_game_ship_pixels:", main)
        self.assertIn("game_ship_pixels", main)
        self.assertIn("game_ship_pixels:", self.files["assets/generated/assets.s"].decode())

    def test_binary_assets_are_copied_byte_for_byte(self):
        source = (ROOT / "framework" / "templates" / "ecs-welcome" / "assets" / "src" / "sprites.png").read_bytes()
        self.assertEqual(self.files["assets/src/sprites.png"], source)

    def test_minimal_template_has_no_ecs_no_tilemap_and_no_assets(self):
        files = gp.render_project(gp.validate(gp.Spec("demo", "hello", template="minimal")), "9.9.9", "en")
        example = json.loads(files["example.json"])
        self.assertNotIn("ecs", example)
        self.assertNotIn("generated/ecs_profile.inc", files)
        self.assertFalse([name for name in files if name.startswith("assets/")])
        self.assertFalse([m for m in example["modules"] if "tilemap" in m or "ecs" in m])
        self.assertNotIn("assets/generated/assets.inc", example["game_sources"])

    def test_the_welcome_manifest_links_the_tilemap_and_the_assets_include(self):
        example = json.loads(self.files["example.json"])
        self.assertIn("extensions/tilemap_render.s", example["modules"])
        self.assertIn("assets/generated/assets.inc", example["game_sources"])

    def test_metadata_files(self):
        meta = json.loads(self.files["glasnost.project.json"])
        self.assertEqual(meta, {"schema": 1, "template": "ecs-welcome", "format": 1, "framework": "9.9.9",
                                "title": "HELLO"})
        example = json.loads(self.files["example.json"])
        self.assertEqual((example["name"], example["amsdos_name"], example["extended_memory"]),
                         ("demo", "DEMO", False))
        self.assertIn("generated/project.inc", example["game_sources"])
        self.assertEqual(self.files["generated/project.inc"].decode().splitlines()[-1], 'game_title: .asciz "HELLO"')

    def test_the_generated_manifest_is_accepted_by_the_build_validations(self):
        example = json.loads(self.files["example.json"])
        profile = json.loads((ROOT / "framework" / "profiles" / example["profile"]).read_text(encoding="utf-8"))
        capabilities = project_config.parse_capabilities(example, profile["mode"])
        modules = build_examples.effective_modules("demo", example["modules"], capabilities)
        build_examples._validate_ecs_systems("demo", example, modules)  # raises when inconsistent
        for module in modules:
            self.assertTrue((ROOT / "framework" / "src" / module).is_file(), module)

    def test_generated_ecs_profile_matches_the_generator_the_build_checks(self):
        example = json.loads(self.files["example.json"])
        self.assertEqual(self.files["generated/ecs_profile.inc"].decode(), gp.ecs_profile_include(example))

    def test_readme_exists_in_both_languages(self):
        spanish = gp.render_project(gp.Spec("demo", "hello"), "9.9.9", "es")["README.md"].decode()
        self.assertIn("Proyecto creado", spanish)
        self.assertIn("Project created", self.files["README.md"].decode())

    def test_extended_memory_and_title_change_the_files(self):
        other = gp.render_project(gp.Spec("demo", "bye", extended_memory=True), "9.9.9", "en")
        self.assertNotEqual(other["example.json"], self.files["example.json"])
        self.assertIn(b"BYE", other["generated/project.inc"])
        self.assertEqual(other["main.s"], self.files["main.s"])  # code does not depend on either


class Checks(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="glasnost-proj-"))
        self.addCleanup(subprocess.run, ["rm", "-rf", str(self.tmp)])
        self.folder = self.tmp / "demo"
        for relative, content in gp.render_project(gp.Spec("demo", "hello"), "1", "en").items():
            (self.folder / relative).parent.mkdir(parents=True, exist_ok=True)
            (self.folder / relative).write_bytes(content)

    def problems(self):
        return gp.check_project(self.folder)

    def test_fresh_project_is_fine(self):
        self.assertEqual(self.problems(), [])

    def test_detects_stale_generated_files(self):
        (self.folder / "generated/project.inc").write_text('game_title: .asciz "OLD"\n')
        self.assertTrue(any("project.inc is stale" in p for p in self.problems()))
        (self.folder / "generated/project.inc").unlink()
        self.assertTrue(any("missing generated/project.inc" in p for p in self.problems()))

    def test_detects_a_stale_ecs_profile(self):
        (self.folder / "generated/ecs_profile.inc").write_text("; edited\n")
        self.assertTrue(any("ecs_profile.inc is stale" in p for p in self.problems()))

    def test_detects_missing_user_files_name_mismatch_and_bad_amsdos(self):
        (self.folder / "main.s").unlink()
        self.assertIn("missing main.s", self.problems())
        example = json.loads((self.folder / "example.json").read_text())
        example["name"] = "other"
        example["amsdos_name"] = "toolongname"
        (self.folder / "example.json").write_text(json.dumps(example))
        found = " | ".join(self.problems())
        self.assertIn("differs from the folder", found)
        self.assertIn("amsdos_name", found)

    def test_detects_unreadable_or_foreign_metadata(self):
        meta = self.folder / gp.PROJECT_FILE
        for content in ("{nope", json.dumps({"schema": 9}), json.dumps({"schema": 1, "template": "other"})):
            meta.write_text(content)
            self.assertEqual(len(self.problems()), 1, content)

    def test_find_project_walks_up(self):
        deep = self.folder / "a" / "b"
        deep.mkdir(parents=True)
        self.assertEqual(gp.find_project(deep), self.folder.resolve())
        self.assertIsNone(gp.find_project(self.tmp))


class ConfigRules(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="glasnost-cfg-"))
        self.addCleanup(subprocess.run, ["rm", "-rf", str(self.tmp)])
        self.folder = self.tmp / "demo"
        for relative, content in gp.render_project(gp.Spec("demo", "hello"), "1", "en").items():
            (self.folder / relative).parent.mkdir(parents=True, exist_ok=True)
            (self.folder / relative).write_bytes(content)

    def test_title_change_rewrites_only_glasnost_owned_files(self):
        out = gp.apply_config(self.folder, title="new title")
        self.assertEqual(sorted(out), ["example.json", "generated/ecs_profile.inc",
                                       "generated/project.inc", "glasnost.project.json"])
        self.assertNotIn("main.s", out)
        self.assertNotIn("common.inc", out)
        self.assertIn(b"NEW TITLE", out["generated/project.inc"])
        self.assertEqual(out["example.json"], (self.folder / "example.json").read_bytes())

    def test_extended_memory_changes_example_json_only_in_its_key(self):
        before = json.loads((self.folder / "example.json").read_text())
        after = json.loads(gp.apply_config(self.folder, extended_memory=True)["example.json"])
        changed = {key for key in before if before[key] != after[key]}
        self.assertEqual(changed, {"extended_memory"})

    def test_user_edits_to_example_json_survive_a_config(self):
        example = json.loads((self.folder / "example.json").read_text())
        example["modules"].append("video/sprite_masked.s")
        example["my_extra"] = {"keep": [1, 2]}
        example["ecs"]["components"].append("collision")
        (self.folder / "example.json").write_text(json.dumps(example))
        out = json.loads(gp.apply_config(self.folder, extended_memory=True)["example.json"])
        self.assertIn("video/sprite_masked.s", out["modules"])
        self.assertEqual(out["my_extra"], {"keep": [1, 2]})
        self.assertIn("collision", out["ecs"]["components"])

    def test_the_regenerated_ecs_profile_follows_user_edited_components(self):
        example = json.loads((self.folder / "example.json").read_text())
        example["ecs"]["components"].append("collision")
        (self.folder / "example.json").write_text(json.dumps(example))
        out = gp.apply_config(self.folder, title="x")
        self.assertEqual(out["generated/ecs_profile.inc"].decode(), gp.ecs_profile_include(example))

    def test_invalid_changes_raise_before_anything_is_produced(self):
        for kwargs in ({"title": "a*b"}, {"title": ""}, {"profile": "experimental"}, {"profile": "x"}):
            with self.subTest(kwargs), self.assertRaises(gp.ProjectError):
                gp.apply_config(self.folder, **kwargs)

    def test_a_project_pointing_at_a_missing_profile_is_a_project_error(self):
        example = json.loads((self.folder / "example.json").read_text())
        example["profile"] = "bogus.json"
        (self.folder / "example.json").write_text(json.dumps(example))
        with self.assertRaises(gp.ProjectError):
            gp.apply_config(self.folder, title="x")

    def test_a_project_with_an_unconfigurable_profile_is_rejected(self):
        example = json.loads((self.folder / "example.json").read_text())
        example["profile"] = "experimental-160x288.json"
        (self.folder / "example.json").write_text(json.dumps(example))
        with self.assertRaises(gp.ProjectError):
            gp.apply_config(self.folder, title="x")


class NewCommand(unittest.TestCase):
    def setUp(self):
        self.sdk = FakeSdk(self)
        self.base = self.sdk.tmp / "work"
        self.assertEqual(self.sdk.cli("install-toolchain")[0], 0)

    def new(self, *argv, **kwargs):
        return run(["new", *argv], self.sdk.root, env=dict(self.sdk.env), **kwargs)

    def test_flags_create_the_project_build_it_and_commit_it(self):
        recorder = Recorder()
        code, out, err = self.new("demo", "--title", "Hello", "--dir", str(self.base), runner=recorder)
        self.assertEqual((code, err), (0, ""), out)
        folder = self.base / "demo"
        self.assertEqual(gp.check_project(folder), [])
        self.assertIn(["--project", str(folder)], [c[-2:] for c in recorder.calls])
        log = subprocess.run(["git", "-C", str(folder), "log", "--format=%s"], capture_output=True, text=True,
                             env=dict(os.environ, **GIT_ENV))
        self.assertEqual(log.stdout.strip(), "Initial project from glasnost (template ecs-welcome)")
        self.assertEqual(subprocess.run(["git", "-C", str(folder), "status", "--porcelain"],
                                        capture_output=True, text=True).stdout, "")
        self.assertIn("RUN\"DEMO", out)

    def test_default_location_is_projects_in_the_sdk(self):
        code, _, _ = self.new("demo", "--no-build", "--no-git")
        self.assertEqual(code, 0)
        self.assertTrue((self.sdk.root / "projects" / "demo" / gp.PROJECT_FILE).is_file())

    def test_no_git_leaves_no_repository_and_git_is_the_default(self):
        self.new("plain", "--no-build", "--no-git", "--dir", str(self.base))
        self.new("versioned", "--no-build", "--dir", str(self.base))
        self.assertFalse((self.base / "plain" / ".git").exists())
        self.assertTrue((self.base / "versioned" / ".git").is_dir())

    def test_the_project_is_its_own_repository(self):
        self.new("demo", "--no-build", "--dir", str(self.base))
        top = subprocess.run(["git", "-C", str(self.base / "demo"), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True).stdout.strip()
        self.assertEqual(Path(top), (self.base / "demo").resolve())

    def test_manifest_flags_and_wizard_produce_identical_projects(self):
        manifest = self.sdk.tmp / "m.json"
        manifest.write_text(json.dumps({"schema": 1, "name": "demo", "title": "hello world",
                                        "extended_memory": True, "git": False}))
        answers = iter(["demo", "hello world", "y", "n", "y"])
        self.assertEqual(self.new("--manifest", str(manifest), "--no-build", "--dir", str(self.base / "m"))[0], 0)
        self.assertEqual(self.new("demo", "--title", "hello world", "--extended-memory", "--no-git",
                                  "--no-build", "--dir", str(self.base / "f"))[0], 0)
        code, _, err = self.new("--no-build", "--dir", str(self.base / "w"), interactive=True,
                                ask=lambda prompt: next(answers))
        self.assertEqual((code, err), (0, ""))
        reference = tree(self.base / "m" / "demo")
        self.assertEqual(tree(self.base / "f" / "demo"), reference)
        self.assertEqual(tree(self.base / "w" / "demo"), reference)
        self.assertFalse((self.base / "m" / "demo" / ".git").exists())

    def test_flags_override_the_manifest(self):
        manifest = self.sdk.tmp / "m.json"
        manifest.write_text(json.dumps({"schema": 1, "name": "demo", "title": "one"}))
        self.new("--manifest", str(manifest), "--title", "two", "--no-build", "--no-git", "--dir", str(self.base))
        self.assertEqual(json.loads((self.base / "demo" / gp.PROJECT_FILE).read_text())["title"], "TWO")

    def test_wizard_reasks_after_an_invalid_answer_and_defaults_the_title(self):
        answers = iter(["Bad Name", "demo", "", "", "", ""])
        code, out, err = self.new("--no-build", "--no-git", "--dir", str(self.base), interactive=True,
                                  ask=lambda prompt: next(answers))
        self.assertEqual(code, 0, err)
        self.assertIn("Not valid", err)
        self.assertEqual(json.loads((self.base / "demo" / gp.PROJECT_FILE).read_text())["title"], "DEMO")

    def test_wizard_aborted_by_eof_creates_nothing(self):
        def eof(prompt):
            raise EOFError

        code, _, err = self.new("--dir", str(self.base), interactive=True, ask=eof)
        self.assertEqual(code, 1)
        self.assertIn("cancelled", err)
        self.assertFalse(self.base.exists())

    def test_wizard_gives_up_after_repeated_invalid_answers(self):
        code, _, err = self.new("--dir", str(self.base), interactive=True, ask=lambda prompt: "NOPE!")
        self.assertEqual(code, 1)
        self.assertFalse(self.base.exists())

    def test_without_name_manifest_or_terminal_it_explains_itself(self):
        code, _, err = self.new("--dir", str(self.base))
        self.assertEqual(code, 1)
        self.assertIn("manifest", err)

    def test_an_existing_folder_is_never_touched(self):
        (self.base / "demo").mkdir(parents=True)
        (self.base / "demo" / "mine.txt").write_text("precious")
        code, _, err = self.new("demo", "--dir", str(self.base), "--no-build")
        self.assertEqual(code, 1)
        self.assertIn("already exists", err)
        self.assertEqual((self.base / "demo" / "mine.txt").read_text(), "precious")
        self.assertEqual(sorted(p.name for p in (self.base / "demo").iterdir()), ["mine.txt"])

    def test_an_existing_symlink_is_not_followed_or_replaced(self):
        target = self.sdk.tmp / "elsewhere"
        target.mkdir()
        self.base.mkdir()
        (self.base / "demo").symlink_to(target)
        code, _, _ = self.new("demo", "--dir", str(self.base), "--no-build")
        self.assertEqual(code, 1)
        self.assertEqual(list(target.iterdir()), [])
        self.assertTrue((self.base / "demo").is_symlink())

    def test_a_failing_build_removes_what_was_created_and_the_new_base_folder(self):
        recorder = Recorder(fail=[(sys.executable, "tools/build/build_examples.py")])
        code, _, err = self.new("demo", "--dir", str(self.base), runner=recorder)
        self.assertEqual(code, 1)
        self.assertIn("does not build", err)
        self.assertFalse(self.base.exists())

    def test_a_failing_build_keeps_a_base_folder_that_already_existed(self):
        self.base.mkdir()
        (self.base / "other.txt").write_text("x")
        recorder = Recorder(fail=[(sys.executable, "tools/build/build_examples.py")])
        self.assertEqual(self.new("demo", "--dir", str(self.base), runner=recorder)[0], 1)
        self.assertEqual(sorted(p.name for p in self.base.iterdir()), ["other.txt"])

    def test_without_a_toolchain_nothing_is_created(self):
        bare = FakeSdk(self)
        code, _, err = run(["new", "demo", "--dir", str(self.base)], bare.root, env=dict(bare.env))
        self.assertEqual(code, 1)
        self.assertIn("install-toolchain", err)
        self.assertFalse(self.base.exists())

    def test_ctrl_c_during_the_build_cleans_up(self):
        def interrupted(command, **kwargs):
            raise KeyboardInterrupt

        code, _, err = self.new("demo", "--dir", str(self.base), runner=interrupted)
        self.assertEqual((code, err.strip()), (130, "Interrupted."))
        self.assertFalse(self.base.exists())

    def test_ctrl_c_during_the_first_commit_removes_the_folder_and_new_parents(self):
        deep = self.base / "a" / "b"

        def interrupt_git(command, **kwargs):
            if command[0] == "git":
                raise KeyboardInterrupt
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        code, _, err = self.new("demo", "--dir", str(deep), runner=interrupt_git)
        self.assertEqual(code, 130)
        self.assertFalse(self.base.exists(), "intermediate folders this command created are removed too")

    def test_only_the_folders_it_created_are_removed_on_failure(self):
        (self.base / "a").mkdir(parents=True)
        (self.base / "a" / "keep.txt").write_text("x")
        recorder = Recorder(fail=[(sys.executable, "tools/build/build_examples.py")])
        self.assertEqual(self.new("demo", "--dir", str(self.base / "a" / "b" / "c"), runner=recorder)[0], 1)
        self.assertEqual(sorted(p.name for p in (self.base / "a").iterdir()), ["keep.txt"])

    def test_git_trouble_is_a_warning_not_a_failure(self):
        def no_git(command, **kwargs):
            if command[0] == "git":
                raise FileNotFoundError(2, "No such file", "git")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        code, out, err = self.new("demo", "--dir", str(self.base), runner=no_git)
        self.assertEqual(code, 0, err)
        self.assertIn("first commit could not be made", err)
        self.assertTrue((self.base / "demo" / gp.PROJECT_FILE).is_file())

    def test_invalid_input_is_reported_without_a_traceback(self):
        for argv in (["Bad"], ["demo", "--title", "a*b"], ["demo", "--title", ""]):
            with self.subTest(argv):
                code, _, err = self.new(*argv, "--dir", str(self.base), "--no-build")
                self.assertEqual(code, 1)
                self.assertNotIn("Traceback", err)
                self.assertFalse(self.base.exists())

    def test_a_bad_manifest_is_reported(self):
        manifest = self.sdk.tmp / "m.json"
        for content in ("{nope", json.dumps([1]), json.dumps({"schema": 1}), json.dumps({"schema": 1, "name": "d", "zzz": 1})):
            manifest.write_text(content)
            code, _, err = self.new("--manifest", str(manifest), "--dir", str(self.base), "--no-build")
            self.assertEqual(code, 1, content)
            self.assertNotIn("Traceback", err)
        code, _, err = self.new("--manifest", str(self.sdk.tmp / "missing.json"), "--dir", str(self.base))
        self.assertEqual(code, 1)

    def test_experimental_video_mode_is_refused(self):
        code, _, err = self.new("demo", "--profile", "experimental", "--dir", str(self.base))
        self.assertEqual(code, 2)  # not one of argparse's choices

    def test_spanish_messages(self):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                mock.patch.dict(os.environ, dict(GIT_ENV, **self.sdk.env)):
            glasnost.main(["--lang", "es", "new", "demo", "--no-build", "--no-git", "--dir", str(self.base)],
                          root=self.sdk.root)
        self.assertIn("creado", out.getvalue())


class ProjectCommands(unittest.TestCase):
    def setUp(self):
        self.sdk = FakeSdk(self)
        self.assertEqual(self.sdk.cli("install-toolchain")[0], 0)
        self.base = self.sdk.tmp / "work"
        self.assertEqual(run(["new", "demo", "--no-build", "--no-git", "--dir", str(self.base)],
                             self.sdk.root, env=dict(self.sdk.env))[0], 0)
        self.folder = self.base / "demo"
        self.cpct = str(self.sdk.checkout / "cpctelera")

    def cmd(self, *argv, runner=None, cwd=None):
        return run(list(argv), self.sdk.root, runner=runner or Recorder(), env=dict(self.sdk.env),
                   cwd=cwd or self.folder)

    # ---- build / test / run inside a project
    def test_build_inside_a_project_builds_that_project_with_the_toolchain(self):
        recorder = Recorder()
        code, _, _ = self.cmd("build", runner=recorder)
        self.assertEqual(code, 0)
        self.assertEqual(recorder.calls, [[sys.executable, "tools/build/build_examples.py", "--project", str(self.folder)]])

    def test_build_works_from_a_subfolder_and_with_the_project_flag(self):
        sub = self.folder / "deep"
        sub.mkdir()
        recorder = Recorder()
        self.assertEqual(self.cmd("build", runner=recorder, cwd=sub)[0], 0)
        self.assertEqual(recorder.calls[0][-1], str(self.folder))
        elsewhere = Recorder()
        self.assertEqual(self.cmd("build", "--project", str(self.folder), runner=elsewhere, cwd=self.sdk.tmp)[0], 0)
        self.assertEqual(elsewhere.calls[0][-1], str(self.folder))

    def test_an_explicit_project_flag_must_point_at_a_project(self):
        recorder = Recorder()
        for command in ("build", "test", "run", "config"):
            with self.subTest(command):
                code, _, err = self.cmd(command, "--project", str(self.sdk.tmp / "nope"), runner=recorder)
                self.assertEqual(code, 1)
                self.assertIn("is not a glasnost project", err)
        self.assertEqual(recorder.calls, [], "nothing may fall back to building the framework")

    def test_example_names_are_refused_inside_a_project(self):
        recorder = Recorder()
        code, _, err = self.cmd("build", "minimal", runner=recorder)
        self.assertEqual(code, 1)
        self.assertIn("takes no example names", err)
        self.assertEqual(recorder.calls, [])
        self.assertEqual(self.cmd("run", "minimal", runner=recorder)[0], 1)

    def test_build_refuses_a_stale_project_and_lists_why(self):
        (self.folder / "generated/project.inc").write_text('game_title: .asciz "OLD"\n')
        recorder = Recorder()
        code, _, err = self.cmd("build", runner=recorder)
        self.assertEqual(code, 1)
        self.assertIn("project.inc is stale", err)
        self.assertEqual(recorder.calls, [])

    def test_test_checks_then_builds_and_reports(self):
        recorder = Recorder()
        code, out, _ = self.cmd("test", runner=recorder)
        self.assertEqual(code, 0)
        self.assertIn("consistent and builds", out)
        self.assertEqual(len(recorder.calls), 1)
        failing = Recorder(fail=[(sys.executable,)])
        code, out, _ = self.cmd("test", runner=failing)
        self.assertEqual(code, 3)
        self.assertNotIn("consistent", out)

    def test_run_inside_a_project_passes_the_folder_and_options(self):
        recorder = Recorder()
        self.assertEqual(self.cmd("run", "--", "--emulator", "x", runner=recorder)[0], 0)
        self.assertEqual(recorder.calls[0][1:], ["tools/glasnost/run_example.py", "--project", str(self.folder), "--emulator", "x"])

    def test_outside_a_project_commands_keep_working_and_run_needs_an_example(self):
        recorder = Recorder()
        code, _, err = self.cmd("run", runner=recorder, cwd=self.sdk.tmp)
        self.assertEqual(code, 1)
        self.assertIn("Name an example", err)
        self.assertEqual(self.cmd("build", "minimal", runner=recorder, cwd=self.sdk.tmp)[0], 0)

    # ---- config
    def test_config_without_options_shows_the_configuration(self):
        code, out, _ = self.cmd("config")
        self.assertEqual(code, 0)
        self.assertIn("title: DEMO", out)
        self.assertIn("extended_memory: false", out)

    def test_config_changes_title_and_memory_atomically_and_leaves_code_alone(self):
        before = tree(self.folder)
        code, out, _ = self.cmd("config", "--title", "fresh", "--extended-memory")
        self.assertEqual(code, 0, out)
        after = tree(self.folder)
        changed = {path for path in after if after[path] != before.get(path)}
        self.assertEqual(changed, {"example.json", "generated/project.inc", "glasnost.project.json"})
        self.assertEqual(gp.check_project(self.folder), [])
        self.assertEqual(sorted(p.name for p in self.folder.rglob("*.glasnost-tmp")), [])
        self.assertEqual(json.loads((self.folder / "example.json").read_text())["extended_memory"], True)
        self.cmd("config", "--no-extended-memory")
        self.assertEqual(json.loads((self.folder / "example.json").read_text())["extended_memory"], False)

    def add_collision(self):
        """What a game developer does to use a framework system: edit example.json."""
        text = (self.folder / "example.json").read_text()
        example = json.loads(text)
        example["ecs"]["components"].append("collision")
        example["modules"].append("core/ecs_collision.s")
        edited = json.dumps(example)  # deliberately not the 2-space layout glasnost writes
        (self.folder / "example.json").write_text(edited)
        return edited

    def test_config_without_options_regenerates_a_stale_ecs_profile(self):
        edited = self.add_collision()
        self.assertTrue(any("ecs_profile.inc is stale" in p for p in gp.check_project(self.folder)))
        code, out, err = self.cmd("config")
        self.assertEqual((code, err), (0, ""), out)
        self.assertIn("title: DEMO", out)
        self.assertIn("regenerating generated/ecs_profile.inc", out)
        self.assertEqual(gp.check_project(self.folder), [], "build asked for `glasnost config`: it must fix it")
        self.assertIn("ECS_C_COLLISION", (self.folder / "generated" / "ecs_profile.inc").read_text())
        self.assertEqual((self.folder / "example.json").read_text(), edited, "the user's file is untouched")
        recorder = Recorder()
        self.assertEqual(self.cmd("build", runner=recorder)[0], 0)
        self.assertEqual(len(recorder.calls), 1)

    def test_config_without_options_regenerates_a_deleted_generated_file(self):
        (self.folder / "generated" / "project.inc").unlink()
        self.assertEqual(self.cmd("config")[0], 0)
        self.assertEqual(gp.check_project(self.folder), [])

    def test_config_without_options_only_writes_generated_files(self):
        self.add_collision()
        before = tree(self.folder)
        self.cmd("config")
        changed = {path for path, digest in tree(self.folder).items() if before.get(path) != digest}
        self.assertEqual(changed, {"generated/ecs_profile.inc"})

    def test_config_without_options_dry_run_previews_the_regeneration(self):
        self.add_collision()
        before = tree(self.folder)
        code, out, _ = self.cmd("config", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("regenerating generated/ecs_profile.inc", out)
        self.assertIn("Dry run", out)
        self.assertEqual(tree(self.folder), before)

    def test_config_without_options_on_a_fresh_project_writes_nothing_and_says_nothing_extra(self):
        before = tree(self.folder)
        code, out, _ = self.cmd("config")
        self.assertEqual(code, 0)
        self.assertEqual(out.strip().splitlines()[0], "title: DEMO")
        self.assertNotIn("regenerating", out)
        self.assertEqual(tree(self.folder), before)

    def test_config_never_touches_a_project_from_a_newer_format(self):
        meta = json.loads((self.folder / gp.PROJECT_FILE).read_text())
        meta["format"] = 99
        (self.folder / gp.PROJECT_FILE).write_text(json.dumps(meta))
        self.add_collision()
        before = tree(self.folder)
        for argv in ([], ["--dry-run"], ["--title", "other"], ["--extended-memory"]):
            with self.subTest(argv):
                code, _, err = self.cmd("config", *argv)
                self.assertEqual(code, 1)
                self.assertIn("this glasnost supports up to", err)
                self.assertEqual(tree(self.folder), before)

    def test_config_without_options_explains_why_it_cannot_regenerate(self):
        example = json.loads((self.folder / "example.json").read_text())
        example["ecs"]["components"].append("no_such_component")
        (self.folder / "example.json").write_text(json.dumps(example))
        before = tree(self.folder)
        code, _, err = self.cmd("config")
        self.assertEqual(code, 1)
        self.assertIn("no_such_component", err)
        self.assertEqual(tree(self.folder), before)

    def test_config_dry_run_and_noop_change_nothing(self):
        before = tree(self.folder)
        code, out, _ = self.cmd("config", "--title", "fresh", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("Dry run", out)
        self.assertEqual(tree(self.folder), before)
        code, out, _ = self.cmd("config", "--title", "demo")
        self.assertIn("Nothing to change", out)
        self.assertEqual(tree(self.folder), before)

    def test_config_with_invalid_values_leaves_every_file_untouched(self):
        before = tree(self.folder)
        for argv in (["--title", "a*b"], ["--title", ""], ["--title", "x" * 31]):
            with self.subTest(argv):
                code, _, err = self.cmd("config", *argv)
                self.assertEqual(code, 1)
                self.assertIn("Nothing changed", err)
                self.assertEqual(tree(self.folder), before)

    def test_config_outside_a_project_is_refused(self):
        code, _, err = self.cmd("config", "--title", "x", cwd=self.sdk.tmp)
        self.assertEqual(code, 1)
        self.assertIn("not inside a glasnost project", err)

    def test_a_failed_write_never_leaves_temporary_files_or_half_a_config(self):
        real_replace = os.replace
        calls = []

        def failing(source, target):
            calls.append(target)
            if len(calls) == 2:
                raise OSError(28, "No space left on device", str(target))
            return real_replace(source, target)

        with mock.patch.object(glasnost.os, "replace", failing):
            code, _, err = self.cmd("config", "--title", "fresh", "--extended-memory")
        self.assertEqual(code, 1)
        self.assertIn("System error", err)
        self.assertEqual(sorted(p.name for p in self.folder.rglob("*.glasnost-tmp")), [])


@unittest.skipUnless(real_toolchain(), "needs a CPCTelera Next toolchain")
class RealBuild(unittest.TestCase):
    """The generated project must compile with the real toolchain, in every configuration."""

    def build(self, *new_args):
        tmp = Path(tempfile.mkdtemp(prefix="glasnost-real-")).resolve()  # macOS: /var -> /private/var
        self.addCleanup(subprocess.run, ["rm", "-rf", str(tmp)])
        env = {"CPCT_NEXT_PATH": str(real_toolchain())}
        code, out, err = run(["new", "demo", "--dir", str(tmp), "--no-git", *new_args], ROOT,
                             runner=quiet_runner, env=env)
        self.assertEqual(code, 0, out + err)
        folder = tmp / "demo"
        for name in ("demo.bin", "demo.cdt", "demo.dsk"):
            self.assertTrue(any((folder / "build").rglob(name)), name)
        return folder, env

    def test_standard_project_builds_and_is_small(self):
        folder, _ = self.build()
        binary = next((folder / "build").rglob("demo.bin"))
        # 7.9 KB today: a template that grows or shrinks a lot should be a deliberate decision
        self.assertGreater(binary.stat().st_size, 5_000)
        self.assertLess(binary.stat().st_size, 9_500)

    def test_extended_memory_project_builds(self):
        self.build("--extended-memory")

    def test_config_then_build_round_trip(self):
        folder, env = self.build()
        self.assertEqual(run(["config", "--title", "back again", "--extended-memory"], ROOT, env=env, cwd=folder)[0], 0)
        code, out, err = run(["test"], ROOT, runner=quiet_runner, env=env, cwd=folder)
        self.assertEqual(code, 0, out + err)
        self.assertEqual(run(["config", "--no-extended-memory"], ROOT, env=env, cwd=folder)[0], 0)
        self.assertEqual(run(["build"], ROOT, runner=quiet_runner, env=env, cwd=folder)[0], 0)

    def test_two_creations_build_identical_binaries(self):
        first, _ = self.build()
        second, _ = self.build()
        a = next((first / "build").rglob("demo.bin")).read_bytes()
        b = next((second / "build").rglob("demo.bin")).read_bytes()
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
