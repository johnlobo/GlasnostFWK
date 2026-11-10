"""Gate tests of `glasnost update`, `rollback` and `projects` and of the migration engine.

Deterministic and local: Git is real (so branches, cleanliness and restores are the real thing),
builds go through a recording runner, with synthetic migrations for engine failure cases.
The real format-1 filename migration is exercised separately. The one test that compiles for real is skipped without a toolchain.
"""

from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools" / d) for d in ("glasnost", "build", "dev")]
sys.path.insert(0, str(ROOT / "tests"))

import glasnost  # noqa: E402
import glasnost_project as gp  # noqa: E402
import glasnost_update as gu  # noqa: E402
from test_glasnost import FakeSdk, quiet_runner  # noqa: E402
from test_glasnost_project import GIT_ENV, Recorder, real_toolchain, run, tree  # noqa: E402


def retitle(title: str, tasks=()):
    def apply(meta, example):
        meta["title"] = title
        return meta, example, list(tasks)
    return apply


def migrations(*steps) -> dict[int, gu.Migration]:
    return {step.from_format: step for step in steps}


STEP1 = gu.Migration(1, "retitle to UPDATED", retitle("UPDATED"))


def git(folder: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(folder), *args], capture_output=True, text=True,
                            env=dict(os.environ, **GIT_ENV))
    return result.stdout.strip()


class Engine(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="glasnost-upd-"))
        self.addCleanup(subprocess.run, ["rm", "-rf", str(self.tmp)])
        self.folder = self.tmp / "demo"
        for relative, content in gp.render_project(gp.Spec("demo", "hello"), "old", "en").items():
            (self.folder / relative).parent.mkdir(parents=True, exist_ok=True)
            (self.folder / relative).write_bytes(content)
        meta = json.loads((self.folder / gp.PROJECT_FILE).read_text())
        meta["format"] = 1
        (self.folder / gp.PROJECT_FILE).write_text(gp.dump_json(meta))

    def plan(self, migration_map, target=2, framework="new"):
        return gu.plan_update(self.folder, framework, migration_map, target)

    def test_registry_is_consistent_with_the_current_format(self):
        """Bumping FORMAT without adding the migration must fail here, not in a user's project."""
        for number in range(1, gp.FORMAT):
            self.assertIn(number, gu.MIGRATIONS, f"no migration {number} -> {number + 1}")
            self.assertEqual(gu.MIGRATIONS[number].from_format, number)

    def test_a_project_at_the_current_format_has_nothing_to_do(self):
        meta = json.loads((self.folder / gp.PROJECT_FILE).read_text())
        meta["format"] = gp.FORMAT
        (self.folder / gp.PROJECT_FILE).write_text(gp.dump_json(meta))
        plan = gu.plan_update(self.folder, "new")
        self.assertTrue(plan.empty)
        self.assertEqual((plan.steps, plan.changed, plan.tasks, plan.files), ((), (), (), {}))

    def test_a_missing_format_key_means_format_one(self):
        meta = json.loads((self.folder / gp.PROJECT_FILE).read_text())
        del meta["format"]
        (self.folder / gp.PROJECT_FILE).write_text(json.dumps(meta))
        self.assertEqual(self.plan(migrations(STEP1)).from_format, 1)

    def test_one_step_migrates_documents_and_regenerates(self):
        plan = self.plan(migrations(STEP1))
        self.assertEqual((plan.from_format, plan.to_format, len(plan.steps)), (1, 2, 1))
        meta = json.loads(plan.files[gp.PROJECT_FILE])
        self.assertEqual((meta["format"], meta["framework"], meta["title"]), (2, "new", "UPDATED"))
        self.assertIn(b'game_title: .asciz "UPDATED"', plan.files["generated/project.inc"])
        self.assertIn(gp.PROJECT_FILE, plan.changed)
        self.assertIn("generated/project.inc", plan.changed)
        self.assertNotIn("glasnost.manifest.json", plan.changed)  # untouched documents are not rewritten

    def test_planning_writes_nothing_and_never_offers_user_code(self):
        before = tree(self.folder)
        plan = self.plan(migrations(STEP1))
        self.assertEqual(tree(self.folder), before)
        self.assertEqual(sorted(plan.files), sorted(
            [gp.PROJECT_FILE, "glasnost.manifest.json", "generated/ecs_profile.inc", "generated/project.inc"]))
        self.assertTrue({"main.s", "common.inc", "README.md"}.isdisjoint(plan.files))

    def test_steps_are_consecutive_and_run_in_order(self):
        seen = []

        def first(meta, example):
            seen.append(("first", copy.deepcopy(meta["format"])))
            meta["title"] = "ONE"
            return meta, example, ["rename sprite A"]

        def second(meta, example):
            seen.append(("second", meta["title"]))
            meta["title"] = "TWO"
            return meta, example, ["rename sprite B"]

        plan = self.plan(migrations(gu.Migration(1, "one", first), gu.Migration(2, "two", second)), target=3)
        self.assertEqual(seen, [("first", 1), ("second", "ONE")])
        self.assertEqual(json.loads(plan.files[gp.PROJECT_FILE])["format"], 3)
        self.assertEqual(plan.tasks, ("format 1 to 2: rename sprite A", "format 2 to 3: rename sprite B"))

    def test_a_gap_is_an_error_and_nothing_is_skipped(self):
        with self.assertRaisesRegex(gu.UpdateError, "none may be skipped"):
            self.plan(migrations(gu.Migration(2, "two", retitle("X"))), target=3)

    def test_a_migration_registered_under_the_wrong_number_is_rejected(self):
        with self.assertRaisesRegex(gu.UpdateError, "says it starts at"):
            self.plan({1: gu.Migration(7, "lies", retitle("X"))})

    def test_a_newer_project_is_never_downgraded(self):
        meta = json.loads((self.folder / gp.PROJECT_FILE).read_text())
        meta["format"] = 9
        (self.folder / gp.PROJECT_FILE).write_text(json.dumps(meta))
        with self.assertRaisesRegex(gu.UpdateError, "newer"):
            self.plan(migrations(STEP1))

    def test_invalid_formats_in_the_project_file_are_rejected(self):
        for bad in (0, -1, "2", 1.5, True, None, [1]):
            meta = json.loads((self.folder / gp.PROJECT_FILE).read_text())
            meta["format"] = bad
            (self.folder / gp.PROJECT_FILE).write_text(json.dumps(meta))
            with self.subTest(bad), self.assertRaises(gu.UpdateError):
                self.plan(migrations(STEP1))

    def test_misbehaving_migrations_are_caught_before_anything_is_written(self):
        def boom(meta, example):
            raise RuntimeError("bug")

        def renames(meta, example):
            example["name"] = "other"
            return meta, example, []

        def sets_format(meta, example):
            meta["format"] = 5
            return meta, example, []

        cases = {
            "raises": boom,
            "not documents": lambda m, e: (None, e, []),
            "bad tasks": lambda m, e: (m, e, "do it"),
            "empty task": lambda m, e: (m, e, [" "]),
            "rename": renames,
            "sets format": sets_format,
            "wrong arity": lambda m, e: (m, e),
            "invalid result": lambda m, e: (m, dict(e, profile="bogus.json"), []),
        }
        before = tree(self.folder)
        for name, function in cases.items():
            with self.subTest(name), self.assertRaises(gu.UpdateError):
                self.plan(migrations(gu.Migration(1, name, function)))
        self.assertEqual(tree(self.folder), before)

    def test_a_migration_gets_copies_and_cannot_corrupt_the_next_plan(self):
        def mutates_then_fails(meta, example):
            meta["title"] = "CHANGED"
            example["modules"].append("x.s")
            raise RuntimeError("late")

        with self.assertRaises(gu.UpdateError):
            self.plan(migrations(gu.Migration(1, "x", mutates_then_fails)))
        plan = self.plan(migrations(STEP1))
        self.assertNotIn("x.s", json.loads(plan.files["glasnost.manifest.json"])["modules"])

    def test_migrations_may_edit_example_json_for_renamed_modules(self):
        def rename_module(meta, example):
            example["modules"] = [m.replace("video/sprite.s", "video/sprite.s") for m in example["modules"]]
            example["modules"].append("extensions/tilemap.s")
            return meta, example, []

        plan = self.plan(migrations(gu.Migration(1, "modules", rename_module)))
        self.assertIn("extensions/tilemap.s", json.loads(plan.files["glasnost.manifest.json"])["modules"])
        self.assertIn("glasnost.manifest.json", plan.changed)

    def test_check_project_rejects_bad_formats_too(self):
        for bad in (0, -3, "1", True, 2.5):
            meta = json.loads((self.folder / gp.PROJECT_FILE).read_text())
            meta["format"] = bad
            (self.folder / gp.PROJECT_FILE).write_text(json.dumps(meta))
            with self.subTest(bad):
                self.assertTrue(gp.check_project(self.folder), "a bad format must be reported")

    def test_planning_is_deterministic(self):
        self.assertEqual(self.plan(migrations(STEP1)).files, self.plan(migrations(STEP1)).files)

    def test_the_engine_does_not_use_the_network_or_git(self):
        source = (ROOT / "tools" / "glasnost" / "glasnost_update.py").read_text(encoding="utf-8")
        code = "\n".join(line for line in source.splitlines() if not line.lstrip().startswith(("#", '"""')))
        for forbidden in ("import socket", "urllib", "http.client", "requests", "subprocess", "import ssl"):
            self.assertNotIn(forbidden, code)


class Cycle(unittest.TestCase):
    """update / rollback / projects against real Git repositories."""

    def setUp(self):
        self.sdk = FakeSdk(self)
        self.assertEqual(self.sdk.cli("install-toolchain")[0], 0)
        self.base = self.sdk.tmp / "work"
        with mock.patch.object(gp, "FORMAT", 1):
            code, _, err = run(["new", "demo", "--no-build", "--dir", str(self.base)], self.sdk.root,
                               env=dict(self.sdk.env))
        self.assertEqual((code, err), (0, ""))
        self.folder = self.base / "demo"
        self.main = git(self.folder, "branch", "--show-current")
        self.original = tree(self.folder)
        # the SDK now speaks format 2, with one synthetic migration from 1
        for patcher in (mock.patch.object(gp, "FORMAT", 2),
                        mock.patch.object(gu, "MIGRATIONS", migrations(STEP1))):
            patcher.start()
            self.addCleanup(patcher.stop)

    def cmd(self, *argv, runner=None, cwd=None, env=None):
        return run(list(argv), self.sdk.root, runner=runner or Recorder(),
                   env=dict(self.sdk.env, **(env or {})), cwd=cwd or self.folder)

    def head(self, branch=None):
        return git(self.folder, "rev-parse", branch or "HEAD")

    # ---- planning only
    def test_dry_run_shows_the_plan_and_changes_nothing(self):
        code, out, _ = self.cmd("update", "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("format 1 to 2", out)
        self.assertIn("retitle to UPDATED", out)
        self.assertIn("rewriting generated/project.inc", out)
        self.assertIn("Dry run", out)
        self.assertEqual(tree(self.folder), self.original)
        self.assertEqual(git(self.folder, "branch", "--list"), f"* {self.main}")

    def test_dry_run_needs_neither_git_nor_a_clean_tree_nor_a_toolchain(self):
        (self.folder / "main.s").write_text("dirty")
        bare = FakeSdk(self)
        code, out, _ = run(["update", "--dry-run"], bare.root, runner=Recorder(), env=dict(bare.env), cwd=self.folder)
        self.assertEqual(code, 0, out)

    def test_up_to_date_projects_say_so(self):
        with mock.patch.object(gp, "FORMAT", 1), mock.patch.object(gu, "MIGRATIONS", {}):
            code, out, _ = self.cmd("update")
        self.assertEqual(code, 0)
        self.assertIn("already up to date", out)
        self.assertEqual(git(self.folder, "branch", "--list"), f"* {self.main}")

    # ---- the real thing
    def test_update_migrates_on_a_branch_builds_and_commits(self):
        recorder = Recorder()
        main_before = self.head()
        code, out, err = self.cmd("update", runner=recorder)
        self.assertEqual((code, err), (0, ""), out)
        branch = "glasnost-update-1-to-2"
        self.assertEqual(git(self.folder, "branch", "--show-current"), branch)
        self.assertEqual(self.head(self.main), main_before, "the original branch is untouched")
        self.assertEqual(git(self.folder, "status", "--porcelain"), "")
        self.assertEqual(git(self.folder, "log", "-1", "--format=%s"), "glasnost update: project format 1 to 2")
        self.assertIn("retitle to UPDATED", git(self.folder, "log", "-1", "--format=%b"))
        meta = json.loads((self.folder / gp.PROJECT_FILE).read_text())
        self.assertEqual((meta["format"], meta["title"]), (2, "UPDATED"))
        self.assertEqual(gp.check_project(self.folder), [])
        self.assertEqual([c[-2:] for c in recorder.calls], [["--project", str(self.folder)]])
        self.assertEqual(git(self.folder, "config", "--get", f"branch.{branch}.glasnostBase"), self.main)
        self.assertIn("glasnost rollback", out)

    def test_user_code_is_never_touched(self):
        (self.folder / "main.s").write_text((self.folder / "main.s").read_text() + "; mine\n")
        git(self.folder, "commit", "-qam", "my change")
        before = {p: h for p, h in tree(self.folder).items() if p in ("main.s", "common.inc", "README.md")}
        self.assertEqual(self.cmd("update")[0], 0)
        after = {p: h for p, h in tree(self.folder).items() if p in before}
        self.assertEqual(after, before)

    def test_the_second_update_is_a_noop_on_the_update_branch(self):
        self.cmd("update")
        code, out, _ = self.cmd("update")
        self.assertEqual(code, 0)
        self.assertIn("already up to date", out)

    # ---- refusals: nothing may be touched
    def refused(self, *argv, **kwargs):
        before_tree, before_branches = tree(self.folder), git(self.folder, "branch", "--list")
        code, _, err = self.cmd(*argv, **kwargs)
        self.assertEqual(code, 1, err)
        self.assertEqual(tree(self.folder), before_tree)
        self.assertEqual(git(self.folder, "branch", "--list"), before_branches)
        return err

    def test_a_dirty_tree_is_refused_whether_modified_or_untracked(self):
        (self.folder / "main.s").write_text("changed")
        self.assertIn("uncommitted changes", self.refused("update"))
        git(self.folder, "checkout", "--", "main.s")
        (self.folder / "new_file.txt").write_text("x")
        self.assertIn("uncommitted changes", self.refused("update"))

    def new_legacy(self, name: str, directory: Path, *flags: str) -> Path:
        """A format-1 project, made while the SDK still spoke format 1."""
        with mock.patch.object(gp, "FORMAT", 1):
            code, _, err = run(["new", name, "--no-build", "--dir", str(directory), *flags], self.sdk.root,
                               env=dict(self.sdk.env))
        self.assertEqual((code, err), (0, ""))
        return directory / name

    def test_a_project_without_its_own_repository_is_refused(self):
        folder = self.new_legacy("plain", self.base / "plain", "--no-git")
        code, _, err = self.cmd("update", cwd=folder)
        self.assertEqual(code, 1)
        self.assertIn("own Git repository", err)

    def test_a_project_inside_someone_elses_repository_is_refused(self):
        outer = self.sdk.tmp / "outer"
        outer.mkdir()
        git(outer, "init", "-q")
        inner = self.new_legacy("inner", outer)   # `new --no-git` inside a repository is refused now
        subprocess.run(["rm", "-rf", str(inner / ".git")], check=True)
        code, _, err = self.cmd("update", cwd=inner)
        self.assertEqual(code, 1)
        self.assertIn("own Git repository", err)

    def test_a_detached_head_is_refused(self):
        git(self.folder, "checkout", "-q", "--detach")
        self.assertIn("detached HEAD", self.refused("update"))

    def test_an_existing_update_branch_is_refused(self):
        git(self.folder, "branch", "glasnost-update-1-to-2")
        self.assertIn("already exists", self.refused("update"))

    def test_without_a_toolchain_nothing_is_touched(self):
        bare = FakeSdk(self)
        code, _, err = run(["update"], bare.root, runner=Recorder(), env=dict(bare.env), cwd=self.folder)
        self.assertEqual(code, 1)
        self.assertIn("install-toolchain", err)
        self.assertEqual(git(self.folder, "branch", "--list"), f"* {self.main}")

    def test_a_project_from_a_newer_glasnost_is_refused_everywhere(self):
        meta = json.loads((self.folder / gp.PROJECT_FILE).read_text())
        meta["format"] = 7
        (self.folder / gp.PROJECT_FILE).write_text(json.dumps(meta))
        git(self.folder, "commit", "-qam", "from the future")
        self.assertIn("newer", self.refused("update"))
        for command in ("build", "test"):
            code, _, err = self.cmd(command)
            self.assertEqual(code, 1)
            self.assertIn("supports up to 2", err)

    # ---- failures restore the project exactly
    def assert_restored(self):
        self.assertEqual(git(self.folder, "branch", "--show-current"), self.main)
        self.assertEqual(git(self.folder, "branch", "--list"), f"* {self.main}")
        self.assertEqual(tree(self.folder), self.original)
        self.assertEqual(git(self.folder, "status", "--porcelain"), "")

    def test_a_failing_build_restores_the_starting_branch_and_removes_the_update_branch(self):
        failing = Recorder(fail=[(sys.executable, "tools/build/build_examples.py")])
        code, _, err = self.cmd("update", runner=failing)
        self.assertEqual(code, 1)
        self.assertIn("does not build", err)
        self.assert_restored()

    def test_files_the_update_had_to_create_do_not_outlive_a_failed_update(self):
        (self.folder / "generated" / "project.inc").unlink()
        git(self.folder, "commit", "-qam", "lost a generated file")
        self.original = tree(self.folder)
        failing = Recorder(fail=[(sys.executable, "tools/build/build_examples.py")])
        code, _, _ = self.cmd("update", runner=failing)
        self.assertEqual(code, 1)
        self.assertFalse((self.folder / "generated" / "project.inc").exists())
        self.assert_restored()

    def test_ctrl_c_during_add_or_commit_restores_everything(self):
        for verb in ("add", "commit"):
            def interrupted(command, **kwargs):
                if command[0] == "git" and verb in command:
                    raise KeyboardInterrupt
                return Recorder()(command, **kwargs)

            with self.subTest(verb):
                code, _, err = self.cmd("update", runner=interrupted)
                self.assertEqual((code, err.strip()), (130, "Interrupted."))
                self.assert_restored()

    def test_a_failing_pre_commit_hook_restores_everything(self):
        hook = self.folder / ".git" / "hooks" / "pre-commit"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        code, _, err = self.cmd("update")
        self.assertEqual(code, 1)
        self.assertIn("could not be made", err)
        self.assert_restored()

    def test_gitignored_generated_files_come_back_byte_for_byte(self):
        (self.folder / ".gitignore").write_text("build/\ngenerated/\n")
        git(self.folder, "rm", "-rq", "--cached", "generated")
        git(self.folder, "add", ".gitignore")
        git(self.folder, "commit", "-qm", "ignore generated")
        self.original = tree(self.folder)  # generated/ is on disk, untracked and ignored
        failing = Recorder(fail=[(sys.executable, "tools/build/build_examples.py")])
        self.assertEqual(self.cmd("update", runner=failing)[0], 1)
        self.assertEqual(git(self.folder, "branch", "--show-current"), self.main)
        self.assertEqual(tree(self.folder), self.original)

    def test_a_directory_the_update_had_to_create_does_not_outlive_a_failed_update(self):
        git(self.folder, "rm", "-rq", "generated")
        git(self.folder, "commit", "-qm", "no generated at all")
        self.original = tree(self.folder)
        failing = Recorder(fail=[(sys.executable, "tools/build/build_examples.py")])
        self.assertEqual(self.cmd("update", runner=failing)[0], 1)
        self.assertFalse((self.folder / "generated").exists())
        self.assert_restored()

    def test_a_failure_to_record_the_base_branch_restores_everything(self):
        def no_config(command, **kwargs):
            if command[0] == "git" and "config" in command:
                return subprocess.CompletedProcess(command, 1, stdout="", stderr="")
            return Recorder()(command, **kwargs)

        code, _, err = self.cmd("update", runner=no_config)
        self.assertEqual(code, 1)
        self.assertIn('"config"', err)
        self.assert_restored()

    def test_a_restore_that_fails_is_never_reported_as_success(self):
        def broken_restore(command, **kwargs):
            if command[0] == "git" and "-f" in command:
                return subprocess.CompletedProcess(command, 1, stdout="", stderr="")
            return Recorder(fail=[(sys.executable, "tools/build/build_examples.py")])(command, **kwargs)

        code, _, err = self.cmd("update", runner=broken_restore)
        self.assertEqual(code, 1)
        self.assertIn("could not be put back", err)

    def test_base_branches_with_slashes_work_and_rollback_delete_cleans_up(self):
        git(self.folder, "branch", "-m", self.main, "feature/x")
        self.main = "feature/x"
        self.original = tree(self.folder)
        self.assertEqual(self.cmd("update")[0], 0)
        self.assertEqual(self.cmd("rollback", "--delete")[0], 0)
        self.assertEqual(git(self.folder, "branch", "--list"), "* feature/x")

    def test_rollback_delete_refuses_to_drop_the_users_own_commits(self):
        self.cmd("update")
        (self.folder / "main.s").write_text((self.folder / "main.s").read_text() + "; my work\n")
        git(self.folder, "commit", "-qam", "work done on the update branch")
        code, _, err = self.cmd("rollback", "--delete")
        self.assertEqual(code, 1)
        self.assertIn("1 commit(s) of yours", err)
        self.assertEqual(git(self.folder, "branch", "--show-current"), self.main)
        self.assertIn("glasnost-update-1-to-2", git(self.folder, "branch", "--list"))
        self.assertIn("my work", git(self.folder, "show", "glasnost-update-1-to-2:main.s"))

    def test_ctrl_c_during_the_build_restores_everything(self):
        def interrupted(command, **kwargs):
            if command[0] == "git":
                return quiet_runner(command, **kwargs)
            raise KeyboardInterrupt

        code, _, err = self.cmd("update", runner=interrupted)
        self.assertEqual((code, err.strip()), (130, "Interrupted."))
        self.assert_restored()

    def test_a_write_failure_midway_restores_everything(self):
        real_replace = os.replace
        calls = []

        def failing(source, target):
            calls.append(target)
            if len(calls) == 2:
                raise OSError(28, "No space left on device", str(target))
            return real_replace(source, target)

        with mock.patch.object(glasnost.os, "replace", failing):
            code, _, err = self.cmd("update")
        self.assertEqual(code, 1)
        self.assertIn("System error", err)
        self.assert_restored()

    def test_a_commit_that_cannot_be_made_restores_everything(self):
        code, _, err = self.cmd("update", env={"GIT_AUTHOR_NAME": "", "GIT_COMMITTER_NAME": ""})
        self.assertEqual(code, 1)
        self.assertIn("could not be made", err)
        self.assert_restored()

    def test_manual_tasks_keep_the_update_even_if_the_build_needs_them(self):
        step = gu.Migration(1, "needs your help", retitle("UPDATED", ["rename player sprite in main.s"]))
        failing = Recorder(fail=[(sys.executable, "tools/build/build_examples.py")])
        with mock.patch.object(gu, "MIGRATIONS", migrations(step)):
            code, out, _ = self.cmd("update", runner=failing)
        self.assertEqual(code, 3)
        self.assertIn("MANUAL TASK", out)
        self.assertIn("1 manual task(s)", out)
        self.assertEqual(git(self.folder, "branch", "--show-current"), "glasnost-update-1-to-2")
        self.assertIn("rename player sprite in main.s", git(self.folder, "log", "-1", "--format=%b"))

    def test_manual_tasks_with_a_building_project_exit_zero_but_are_reported(self):
        step = gu.Migration(1, "needs your help", retitle("UPDATED", ["check the HUD text"]))
        with mock.patch.object(gu, "MIGRATIONS", migrations(step)):
            code, out, _ = self.cmd("update")
        self.assertEqual(code, 0)
        self.assertIn("check the HUD text", out)

    def test_updating_uses_no_network(self):
        def no_sockets(*args, **kwargs):
            raise AssertionError("the update tried to open a socket")

        with mock.patch.object(socket, "socket", no_sockets), \
                mock.patch.object(socket, "create_connection", no_sockets):
            self.assertEqual(self.cmd("update")[0], 0)

    # ---- rollback
    def test_rollback_returns_to_the_start_and_keeps_the_branch(self):
        self.cmd("update")
        code, out, _ = self.cmd("rollback")
        self.assertEqual(code, 0)
        self.assertIn("Back on", out)
        self.assertEqual(git(self.folder, "branch", "--show-current"), self.main)
        self.assertEqual(tree(self.folder), self.original)
        self.assertIn("glasnost-update-1-to-2", git(self.folder, "branch", "--list"))
        # the work is still reachable: the update can be inspected or merged later
        self.assertEqual(git(self.folder, "show", "glasnost-update-1-to-2:glasnost.project.json").count('"format": 2'), 1)

    def test_rollback_delete_removes_the_branch(self):
        self.cmd("update")
        self.assertEqual(self.cmd("rollback", "--delete")[0], 0)
        self.assertEqual(git(self.folder, "branch", "--list"), f"* {self.main}")

    def test_rollback_outside_an_update_branch_does_nothing(self):
        self.assertIn("not an update branch", self.refused("rollback"))
        git(self.folder, "switch", "-q", "-c", "glasnost-update-9-to-10")  # looks like one, is not ours
        self.assertIn("not an update branch", self.refused("rollback"))

    def test_rollback_never_loses_uncommitted_work(self):
        self.cmd("update")
        (self.folder / "main.s").write_text("my unsaved work")
        code, _, err = self.cmd("rollback")
        self.assertEqual(code, 1)
        self.assertIn("uncommitted changes", err)
        self.assertEqual((self.folder / "main.s").read_text(), "my unsaved work")
        self.assertEqual(git(self.folder, "branch", "--show-current"), "glasnost-update-1-to-2")

    def test_rollback_reports_a_vanished_base_branch(self):
        self.cmd("update")
        git(self.folder, "branch", "-m", self.main, "renamed")
        code, _, err = self.cmd("rollback")
        self.assertEqual(code, 1)
        self.assertIn("no longer exists", err)
        self.assertEqual(git(self.folder, "branch", "--show-current"), "glasnost-update-1-to-2")

    # ---- projects
    def test_projects_lists_status_branch_and_dirtiness(self):
        run(["new", "second", "--no-build", "--dir", str(self.base)], self.sdk.root, env=dict(self.sdk.env))
        with mock.patch.object(gp, "FORMAT", 1), mock.patch.object(gu, "MIGRATIONS", {}):
            run(["new", "legacy", "--no-build", "--dir", str(self.base)], self.sdk.root, env=dict(self.sdk.env))
        (self.base / "second" / "main.s").write_text("edited")
        (self.base / "stray_folder").mkdir()
        (self.base / "link").symlink_to(self.base / "second")
        code, out, _ = self.cmd("projects", "--dir", str(self.base), cwd=self.sdk.tmp)
        self.assertEqual(code, 0)
        rows = {line.split()[0]: line for line in out.splitlines()}
        self.assertEqual(sorted(rows), ["demo", "legacy", "second"])
        self.assertIn("outdated (format 1, this glasnost uses 2)", rows["demo"])
        self.assertIn("*", rows["second"])
        self.assertNotIn("*", rows["demo"])
        self.assertIn(self.main, rows["demo"])

    def test_projects_marks_newer_and_invalid_ones(self):
        meta = json.loads((self.folder / gp.PROJECT_FILE).read_text())
        meta["format"] = 8
        (self.folder / gp.PROJECT_FILE).write_text(json.dumps(meta))
        (self.base / "broken").mkdir()
        (self.base / "broken" / gp.PROJECT_FILE).write_text("{nope")
        _, out, _ = self.cmd("projects", "--dir", str(self.base), cwd=self.sdk.tmp)
        self.assertIn("made by a newer glasnost", out)
        self.assertIn("not valid", out)

    def test_projects_with_nothing_says_so(self):
        _, out, _ = self.cmd("projects", "--dir", str(self.sdk.tmp / "empty"), cwd=self.sdk.tmp)
        self.assertIn("No projects", out)

    def test_spanish_messages(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), mock.patch.dict(os.environ, dict(GIT_ENV, **self.sdk.env)):
            os.chdir(self.folder)
            glasnost.main(["--lang", "es", "update", "--dry-run"], root=self.sdk.root, runner=Recorder())
            os.chdir(ROOT)
        self.assertIn("Actualización de demo", out.getvalue())

    def test_an_explicit_project_flag_works_from_anywhere(self):
        code, out, _ = self.cmd("update", "--project", str(self.folder), "--dry-run", cwd=self.sdk.tmp)
        self.assertEqual(code, 0)
        self.assertIn("format 1 to 2", out)
        code, _, err = self.cmd("update", "--project", str(self.sdk.tmp / "nope"), cwd=self.sdk.tmp)
        self.assertEqual(code, 1)
        self.assertIn("is not a glasnost project", err)


class FilenameMigration(unittest.TestCase):
    """The real legacy filename upgrade, with local Git and failure recovery."""

    def setUp(self):
        self.sdk = FakeSdk(self)
        self.assertEqual(self.sdk.cli("install-toolchain")[0], 0)
        with mock.patch.object(gp, "FORMAT", 1):
            code, out, err = run(["new", "demo", "--no-build", "--dir", str(self.sdk.tmp / "games")],
                                 self.sdk.root, env=dict(self.sdk.env))
        self.assertEqual(code, 0, out + err)
        self.folder = self.sdk.tmp / "games/demo"
        self.current = self.folder / gp.MANIFEST_FILE
        self.legacy = self.folder / gp.LEGACY_MANIFEST_FILE
        data = json.loads(self.current.read_text())
        data["custom_extension"] = {"numbers": [1, 2, 3]}
        self.raw = (json.dumps(data, indent=4) + "\n\n").encode()
        self.current.unlink()
        self.legacy.write_bytes(self.raw)
        git(self.folder, "add", "-A")
        git(self.folder, "commit", "-qm", "legacy project")
        self.base = git(self.folder, "branch", "--show-current")
        self.before = tree(self.folder)

    def cmd(self, *args, runner=None):
        return run(list(args), self.sdk.root, runner=runner or Recorder(),
                   env=dict(self.sdk.env), cwd=self.folder)

    def test_dry_run_reports_rename_and_preserves_all_bytes(self):
        plan = gu.plan_update(self.folder, "next")
        self.assertEqual((plan.from_format, plan.to_format), (1, 2))
        self.assertEqual(plan.removed, (gp.LEGACY_MANIFEST_FILE,))
        self.assertEqual(plan.files[gp.MANIFEST_FILE], self.raw)
        code, out, err = self.cmd("update", "--dry-run")
        self.assertEqual(code, 0, err)
        self.assertIn("removing example.json", out)
        self.assertEqual(tree(self.folder), self.before)

    def test_old_build_and_config_work_before_explicit_update(self):
        self.assertEqual(self.cmd("build")[0], 0)
        self.assertEqual(self.cmd("config")[0], 0)
        self.assertEqual(tree(self.folder), self.before)
        self.assertEqual(self.cmd("config", "--extended-memory")[0], 0)
        self.assertFalse(self.current.exists())
        self.assertTrue(json.loads(self.legacy.read_text())["extended_memory"])
        self.assertEqual(json.loads((self.folder / gp.PROJECT_FILE).read_text())["format"], 1)

    def test_update_and_rollback_preserve_manifest_and_user_sources(self):
        code, out, err = self.cmd("update")
        self.assertEqual(code, 0, out + err)
        self.assertFalse(self.legacy.exists())
        self.assertEqual(self.current.read_bytes(), self.raw)
        self.assertEqual(json.loads((self.folder / gp.PROJECT_FILE).read_text())["format"], 2)
        self.assertEqual(git(self.folder, "status", "--porcelain"), "")
        for name in ("main.s", "common.inc", "README.md"):
            self.assertEqual(tree(self.folder)[name], self.before[name])
        self.assertEqual(self.cmd("update")[0], 0)
        self.assertEqual(self.cmd("rollback")[0], 0)
        self.assertEqual(tree(self.folder), self.before)
        self.assertEqual(git(self.folder, "branch", "--show-current"), self.base)

    def test_build_failure_restores_deleted_legacy_file(self):
        failing = Recorder(fail=[(sys.executable, "tools/build/build_examples.py")])
        code, out, err = self.cmd("update", runner=failing)
        self.assertEqual(code, 1, out + err)
        self.assertEqual(tree(self.folder), self.before)
        self.assertFalse(self.current.exists())
        self.assertEqual(self.legacy.read_bytes(), self.raw)
        self.assertEqual(git(self.folder, "status", "--porcelain"), "")
        self.assertEqual(git(self.folder, "branch", "--show-current"), self.base)

    def test_conflicting_files_and_invalid_v2_are_never_silently_accepted(self):
        self.current.write_bytes(self.raw)
        before = tree(self.folder)
        code, out, err = self.cmd("update", "--dry-run")
        self.assertEqual(code, 1, out + err)
        self.assertIn("ambiguous manifests", err)
        self.assertEqual(tree(self.folder), before)
        self.current.unlink()
        meta = json.loads((self.folder / gp.PROJECT_FILE).read_text())
        meta["format"] = 2
        (self.folder / gp.PROJECT_FILE).write_text(gp.dump_json(meta))
        self.assertTrue(any("requires glasnost.manifest.json" in error
                            for error in gp.check_project(self.folder)))


@unittest.skipUnless(real_toolchain(), "needs a CPCTelera Next toolchain")
class RealBuild(unittest.TestCase):
    def test_update_with_a_real_build_then_rollback(self):
        tmp = Path(tempfile.mkdtemp(prefix="glasnost-real-upd-"))
        self.addCleanup(subprocess.run, ["rm", "-rf", str(tmp)])
        env = {"CPCT_NEXT_PATH": str(real_toolchain())}
        with mock.patch.object(gp, "FORMAT", 1):
            code, out, err = run(["new", "demo", "--dir", str(tmp)], ROOT, runner=quiet_runner, env=env)
        self.assertEqual(code, 0, out + err)
        folder = tmp / "demo"
        (folder / gp.MANIFEST_FILE).rename(folder / gp.LEGACY_MANIFEST_FILE)
        git(folder, "add", "-A")
        git(folder, "commit", "-qm", "legacy filename")
        self.assertEqual(run(["build"], ROOT, runner=quiet_runner, env=env, cwd=folder)[0], 0)
        original = tree(folder)
        step = gu.MIGRATIONS[1]
        with mock.patch.object(gp, "FORMAT", 2), mock.patch.object(gu, "MIGRATIONS", migrations(step)):
            code, out, err = run(["update"], ROOT, runner=quiet_runner, env=env, cwd=folder)
            self.assertEqual(code, 0, out + err)
            self.assertEqual(json.loads((folder / gp.PROJECT_FILE).read_text())["format"], 2)
            self.assertTrue(any((folder / "build").rglob("demo.dsk")))
            code, out, err = run(["test"], ROOT, runner=quiet_runner, env=env, cwd=folder)
            self.assertEqual(code, 0, out + err)
            self.assertEqual(run(["rollback"], ROOT, env=env, cwd=folder)[0], 0)
        self.assertEqual(tree(folder), original)


if __name__ == "__main__":
    unittest.main()
