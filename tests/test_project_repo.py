"""A project has its own Git repository and can never reach (or be pointed at) the framework's remote."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools" / d) for d in ("glasnost", "build", "dev")]
sys.path.insert(0, str(ROOT / "tests"))

import glasnost  # noqa: E402
from test_glasnost import FakeSdk, quiet_runner  # noqa: E402

FRAMEWORK = "https://github.com/johnlobo/GlasnostFWK.git"


def git(folder: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(folder), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                          check=True, capture_output=True, text=True).stdout.strip()


class CanonicalRemote(unittest.TestCase):
    def test_every_spelling_of_one_repository_compares_equal(self):
        same = [FRAMEWORK, "https://github.com/johnlobo/GlasnostFWK", "https://github.com/johnlobo/GlasnostFWK/",
                "git@github.com:johnlobo/GlasnostFWK.git", "ssh://git@github.com/johnlobo/GlasnostFWK.git",
                "ssh://git@github.com:22/johnlobo/GlasnostFWK.git", "HTTPS://GitHub.com/JohnLobo/glasnostfwk.GIT",
                "https://user:token@github.com/johnlobo/GlasnostFWK.git", "git://github.com/johnlobo/GlasnostFWK.git"]
        self.assertEqual({glasnost.canonical_remote(url) for url in same}, {"github.com/johnlobo/glasnostfwk"})

    def test_different_repositories_stay_different(self):
        urls = {glasnost.canonical_remote(u) for u in (
            "https://github.com/johnlobo/GlasnostFWK.git", "https://github.com/johnlobo/other.git",
            "https://github.com/someone/GlasnostFWK.git", "https://gitlab.com/johnlobo/GlasnostFWK.git",
            "/srv/git/mygame.git")}
        self.assertEqual(len(urls), 5)


class Harness(unittest.TestCase):
    def setUp(self):
        self.sdk = FakeSdk(self)
        self.calls: list[list[str]] = []

        def recorder(command, **kwargs):
            self.calls.append(list(command))
            return quiet_runner(command, **kwargs)

        self.recorder = recorder
        git(self.sdk.root, "init", "-q", "-b", "main")
        git(self.sdk.root, "remote", "add", "origin", FRAMEWORK)

    def new(self, name="mygame", *extra):
        return self.sdk.cli("new", name, "--no-build", "--title", "x", *extra, runner=self.recorder)

    def project(self, name="mygame") -> Path:
        return self.sdk.root / "projects" / name

    def make_repoless_project(self, name="mygame") -> Path:
        """A project inside the SDK checkout with its .git removed: git would reach the framework."""
        self.assertEqual(self.new(name)[0], 0)
        subprocess.run(["rm", "-rf", str(self.project(name) / ".git")], check=True)
        return self.project(name)

    def network_verbs(self) -> list[list[str]]:
        return [c for c in self.calls if c[0] == "git" and any(v in c for v in ("push", "fetch", "pull", "ls-remote", "clone"))]


class CheckProjectRemote(Harness):
    def check(self, url):
        return glasnost.check_project_remote(url, self.sdk.root, "en")

    def test_the_framework_remote_is_refused_in_every_spelling(self):
        for url in (FRAMEWORK, "git@github.com:johnlobo/GlasnostFWK.git", "https://github.com/johnlobo/glasnostfwk/"):
            with self.subTest(url), self.assertRaises(glasnost.CliError) as raised:
                self.check(url)
            self.assertIn("framework's repository", str(raised.exception))

    def test_the_cpctelera_url_of_the_lockfile_is_refused_too(self):
        with self.assertRaises(glasnost.CliError) as raised:
            self.check("https://example.invalid/cpctelera.git")
        self.assertIn("lockfile", str(raised.exception))

    def test_any_remote_the_framework_checkout_has_is_refused(self):
        git(self.sdk.root, "remote", "add", "upstream", "git@example.org:team/fwk.git")
        with self.assertRaises(glasnost.CliError):
            self.check("https://example.org/team/fwk")

    def test_garbage_is_rejected_before_it_reaches_git(self):
        for url in ("", "   ", "--upload-pack=evil", "-x", "a b", "https://h/r\nx", "x" * 3000):
            with self.subTest(url[:20]), self.assertRaises(glasnost.CliError) as raised:
                self.check(url)
            self.assertIn("Not a valid remote URL", str(raised.exception))

    def test_an_own_repository_is_accepted_as_written(self):
        for url in ("https://github.com/me/mygame.git", "git@github.com:me/mygame.git", "/srv/git/mygame.git"):
            self.assertEqual(self.check(f"  {url} "), url)


class NewNoGit(Harness):
    def test_no_git_inside_a_checkout_is_refused_and_creates_nothing(self):
        code, _, err = self.new("mygame", "--no-git")
        self.assertEqual(code, 1)
        self.assertIn("--no-git", err)
        self.assertIn(str(self.sdk.root), err)
        self.assertFalse(self.project().exists())

    def test_no_git_outside_any_repository_is_fine(self):
        outside = self.sdk.tmp / "elsewhere"
        code, _, err = self.new("mygame", "--no-git", "--dir", str(outside))
        self.assertEqual((code, err), (0, ""))
        self.assertFalse((outside / "mygame" / ".git").exists())

    def test_the_default_still_makes_an_independent_repository_without_a_remote(self):
        self.assertEqual(self.new()[0], 0)
        folder = self.project()
        self.assertEqual(Path(git(folder, "rev-parse", "--show-toplevel")).resolve(), folder.resolve())
        self.assertEqual(git(folder, "remote"), "")
        self.assertEqual(git(folder, "branch", "--show-current"), "main")

    def test_a_manifest_with_git_false_is_held_to_the_same_rule(self):
        manifest = self.sdk.tmp / "m.json"
        manifest.write_text(json.dumps({"schema": 1, "name": "mygame", "title": "x", "git": False}), encoding="utf-8")
        code, _, err = self.sdk.cli("new", "--manifest", str(manifest), "--no-build", runner=self.recorder)
        self.assertEqual(code, 1)
        self.assertIn("--no-git", err)


class NewRemote(Harness):
    def test_remote_is_set_as_origin_and_nothing_is_pushed(self):
        code, out, _ = self.new("mygame", "--remote", "https://github.com/me/mygame.git")
        self.assertEqual(code, 0)
        self.assertEqual(git(self.project(), "remote", "get-url", "origin"), "https://github.com/me/mygame.git")
        self.assertIn("Nothing was pushed", out)
        self.assertEqual(self.network_verbs(), [])

    def test_the_framework_url_is_refused_before_anything_is_created(self):
        code, _, err = self.new("mygame", "--remote", FRAMEWORK)
        self.assertEqual(code, 1)
        self.assertIn("framework's repository", err)
        self.assertFalse(self.project().exists())

    def test_remote_cannot_be_combined_with_no_git(self):
        code, _, err = self.new("mygame", "--remote", "https://github.com/me/mygame.git", "--no-git",
                                "--dir", str(self.sdk.tmp / "out"))
        self.assertEqual(code, 1)
        self.assertIn("--remote", err)

    def test_a_remote_is_not_set_on_the_framework_repository_when_the_project_has_no_repo_of_its_own(self):
        """If the project's git init failed, `remote add` must not land in the enclosing framework repo."""
        real = quiet_runner

        def breaking(command, **kwargs):
            self.calls.append(list(command))
            if command[:1] == ["git"] and "init" in command:
                return subprocess.CompletedProcess(command, 1, stdout="", stderr="")
            return real(command, **kwargs)

        code, _, _ = self.sdk.cli("new", "mygame", "--no-build", "--title", "x", "--remote",
                                  "https://github.com/me/mygame.git", runner=breaking)
        self.assertEqual(code, 0)
        self.assertEqual(git(self.sdk.root, "remote", "get-url", "origin"), FRAMEWORK)
        self.assertEqual(git(self.sdk.root, "remote"), "origin")


class RemoteCommand(Harness):
    def setUp(self):
        super().setUp()
        self.assertEqual(self.new()[0], 0)

    def remote(self, *args):
        return self.sdk.cli("remote", "--project", str(self.project()), *args, runner=self.recorder)

    def test_without_a_url_it_lists_the_remotes(self):
        code, out, _ = self.remote()
        self.assertEqual(code, 0)
        self.assertIn("has no remotes", out)
        git(self.project(), "remote", "add", "origin", "https://github.com/me/mygame.git")
        _, out, _ = self.remote()
        self.assertIn("origin  https://github.com/me/mygame.git", out)

    def test_it_sets_origin_then_changes_it(self):
        code, out, _ = self.remote("https://github.com/me/mygame.git")
        self.assertEqual(code, 0)
        self.assertIn("git push -u origin main", out)
        self.assertEqual(git(self.project(), "remote", "get-url", "origin"), "https://github.com/me/mygame.git")
        self.remote("git@github.com:me/renamed.git")
        self.assertEqual(git(self.project(), "remote", "get-url", "origin"), "git@github.com:me/renamed.git")
        self.assertEqual(git(self.project(), "remote").split(), ["origin"])

    def test_another_remote_name_can_be_used(self):
        self.remote("--name", "backup", "https://example.org/me/backup.git")
        self.assertEqual(git(self.project(), "remote").split(), ["backup"])

    def test_the_framework_url_is_refused_and_the_project_is_untouched(self):
        code, _, err = self.remote(FRAMEWORK)
        self.assertEqual(code, 1)
        self.assertIn("framework's repository", err)
        self.assertEqual(git(self.project(), "remote"), "")

    def test_it_refuses_a_project_whose_git_would_reach_the_framework(self):
        folder = self.make_repoless_project("loose")
        code, _, err = self.sdk.cli("remote", "https://github.com/me/loose.git", "--project", str(folder),
                                    runner=self.recorder)
        self.assertEqual(code, 1)
        self.assertIn("no Git repository of its own", err)
        self.assertEqual(git(self.sdk.root, "remote", "get-url", "origin"), FRAMEWORK)
        self.assertEqual(git(self.sdk.root, "remote"), "origin")

    def test_it_never_uses_the_network(self):
        self.remote("https://github.com/me/mygame.git")
        self.remote()
        self.assertEqual(self.network_verbs(), [])

    def test_outside_a_project_it_says_so(self):
        code, _, err = self.sdk.cli("remote", runner=self.recorder)
        self.assertEqual(code, 1)
        self.assertIn("project", err.lower())


class SharedRepoWarning(Harness):
    def setUp(self):
        super().setUp()
        self.assertEqual(self.sdk.cli("install-toolchain")[0], 0)

    def test_commands_warn_when_the_project_has_no_repository_of_its_own(self):
        folder = self.make_repoless_project()
        for argv in (["config"], ["build"], ["test"], ["run"]):
            with self.subTest(argv):
                _, _, err = self.sdk.cli(*argv, "--project", str(folder), runner=self.recorder) \
                    if argv[0] != "run" else self.sdk.cli("run", "--project", str(folder), runner=self.recorder)
                self.assertIn("no Git repository of its own", err)
                self.assertIn(str(self.sdk.root), err)
                self.assertIn(FRAMEWORK, err)

    def test_no_warning_for_a_project_with_its_own_repository(self):
        self.assertEqual(self.new()[0], 0)
        _, _, err = self.sdk.cli("config", "--project", str(self.project()), runner=self.recorder)
        self.assertNotIn("Git repository of its own", err)

    def test_no_warning_when_there_is_no_repository_anywhere(self):
        outside = self.sdk.tmp / "plain"
        self.assertEqual(self.new("mygame", "--no-git", "--dir", str(outside))[0], 0)
        _, _, err = self.sdk.cli("config", "--project", str(outside / "mygame"), runner=self.recorder)
        self.assertNotIn("Git repository of its own", err)

    def test_the_warning_does_not_add_commands_to_the_ones_the_command_runs(self):
        folder = self.make_repoless_project()
        self.calls.clear()
        self.sdk.cli("run", "--project", str(folder), runner=self.recorder)
        self.assertEqual([c[0] for c in self.calls if c[0] == "git"], [])


class ProjectsListing(Harness):
    def test_a_project_without_its_own_repository_is_flagged_instead_of_showing_the_framework_branch(self):
        self.make_repoless_project("loose")
        self.assertEqual(self.new("proper")[0], 0)
        code, out, _ = self.sdk.cli("projects", runner=self.recorder)
        self.assertEqual(code, 0)
        loose = next(line for line in out.splitlines() if line.strip().startswith("loose"))
        proper = next(line for line in out.splitlines() if line.strip().startswith("proper"))
        self.assertIn("no repository of its own", loose)
        self.assertNotIn("main", loose)
        self.assertIn("main", proper)


class UpdateStaysLocal(Harness):
    def test_update_refuses_a_project_that_would_use_the_framework_repository(self):
        git(self.sdk.root, "commit", "-q", "--allow-empty", "-m", "framework")
        folder = self.make_repoless_project()
        # an old format makes `update` try to act; the guard must stop it on the framework repo
        meta = json.loads((folder / "glasnost.project.json").read_text())
        meta["format"] = 0
        (folder / "glasnost.project.json").write_text(json.dumps(meta), encoding="utf-8")
        code, _, err = self.sdk.cli("update", "--project", str(folder), runner=self.recorder)
        self.assertNotEqual(code, 0)
        self.assertEqual(self.network_verbs(), [])
        self.assertEqual(git(self.sdk.root, "branch", "--list").replace("*", "").split(), ["main"])


if __name__ == "__main__":
    unittest.main()
