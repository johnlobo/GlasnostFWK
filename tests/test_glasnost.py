"""Gate tests of the glasnost CLI: deterministic, local, no network.

The install is exercised end to end against a throwaway Git repository that
mimics the layout of CPCTelera Next (tiny Makefiles that create the files the
real build produces), so the orchestration, the lockfile and the failure paths
are covered without compiling SDCC.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import glasnost  # noqa: E402
import glasnost_i18n  # noqa: E402

SHIM = ROOT / "bin" / "glasnost"


def run_cli(argv, root=ROOT, runner=glasnost.default_runner, env=None):
    """Run main() capturing stdout, stderr and the exit code."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
            mock.patch.dict(os.environ, env or {}, clear=False):
        if not (env and "CPCT_NEXT_PATH" in env):
            os.environ.pop("CPCT_NEXT_PATH", None)  # `glasnost test` exports it; tests must not inherit it
        try:
            code = glasnost.main(argv, root=root, runner=runner)
        except SystemExit as exit_:
            code = exit_.code
    return code, out.getvalue(), err.getvalue()


def quiet_runner(command, **kwargs):
    """The real runner with the build tools' own output discarded."""
    if "capture_output" not in kwargs:
        kwargs.setdefault("stdout", subprocess.DEVNULL)
        kwargs.setdefault("stderr", subprocess.DEVNULL)
    return glasnost.default_runner(command, **kwargs)


def git(*args, cwd):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd, check=True,
                   capture_output=True, text=True)


def make_fake_upstream(directory: Path, broken: str | None = None, silent: str | None = None) -> str:
    """A repo shaped like CPCTelera Next. Returns the commit hash.

    `broken` names a tools/ directory whose Makefile fails, `silent` one whose
    Makefile succeeds without producing its files.
    """
    cpct = directory / "cpctelera"
    for relative in glasnost.MAKE_STEPS:
        target = cpct if relative == "." else cpct / relative
        target.mkdir(parents=True, exist_ok=True)
        outputs = [f for f in glasnost.REQUIRED_FILES
                   if (f == "cpctelera.lib") == (relative == ".")
                   and (relative == "." or f.startswith(relative + "/"))]
        lines = ["all:"]
        if relative == broken:
            lines.append("\t@test -e ok || exit 3")  # an untracked file "ok" repairs the step
        for output in ([] if relative == silent else outputs):
            local = output if relative == "." else output[len(relative) + 1:]
            lines.append(f"\t@mkdir -p $(dir {local}) && echo built > {local} && chmod +x {local}")
        (target / "Makefile").write_text("\n".join(lines) + "\n", encoding="utf-8")
    git("init", "-q", cwd=directory)
    git("add", "-A", cwd=directory)
    git("commit", "-q", "-m", "fake cpctelera", cwd=directory)
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=directory, check=True,
                          capture_output=True, text=True).stdout.strip()


class FakeSdk:
    """A temporary SDK root with its own lockfile pointing at a fake upstream."""

    def __init__(self, test: unittest.TestCase, broken: str | None = None, silent: str | None = None):
        self.tmp = Path(tempfile.mkdtemp(prefix="glasnost-test-"))
        test.addCleanup(subprocess.run, ["rm", "-rf", str(self.tmp)])
        self.upstream = self.tmp / "upstream"
        self.upstream.mkdir()
        self.rev = make_fake_upstream(self.upstream, broken, silent)
        self.root = self.tmp / "sdk"
        (self.root / "examples" / "minimal").mkdir(parents=True)
        (self.root / "examples" / "minimal" / "example.json").write_text("{}", encoding="utf-8")
        self.write_lock(self.rev)
        self.env = {"GLASNOST_TOOLCHAIN_DIR": str(self.tmp / "tc"),
                    "GLASNOST_CPCTELERA_URL": self.upstream.resolve().as_uri()}
        self.checkout = self.tmp / "tc" / "cpctelera-next" / self.rev

    def write_lock(self, rev: str, url: str = "https://example.invalid/cpctelera.git") -> None:
        (self.root / glasnost.LOCKFILE).write_text(json.dumps(
            {"schema": 1, "cpctelera_next": {"url": url, "rev": rev}}), encoding="utf-8")

    def cli(self, *argv, runner=quiet_runner, extra_env=None):
        env = dict(self.env, **(extra_env or {}))
        env.pop("CPCT_NEXT_PATH", None)
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CPCT_NEXT_PATH", None)
            return run_cli(["--lang", "en", *argv], root=self.root, runner=runner, env=env)


class Messages(unittest.TestCase):
    def test_both_languages_have_the_same_keys(self):
        es, en = glasnost_i18n.MESSAGES["es"], glasnost_i18n.MESSAGES["en"]
        self.assertEqual(sorted(es), sorted(en))

    def test_both_languages_use_the_same_placeholders(self):
        for key, spanish in glasnost_i18n.MESSAGES["es"].items():
            english = glasnost_i18n.MESSAGES["en"][key]
            self.assertEqual(sorted(re.findall(r"{(\w+)}", spanish)),
                             sorted(re.findall(r"{(\w+)}", english)), key)

    def test_no_message_is_empty(self):
        for lang, table in glasnost_i18n.MESSAGES.items():
            for key, text in table.items():
                self.assertTrue(text.strip(), f"{lang}:{key}")

    def test_language_order_flag_then_environment_then_spanish(self):
        pick = glasnost_i18n.pick_language
        self.assertEqual(pick(None, {}), "es")
        self.assertEqual(pick(None, {"GLASNOST_LANG": "en"}), "en")
        self.assertEqual(pick("es", {"GLASNOST_LANG": "en"}), "es")
        self.assertEqual(pick("en", {}), "en")
        self.assertEqual(pick(None, {"GLASNOST_LANG": "en_US.UTF-8"}), "en")
        self.assertEqual(pick("fr", {"GLASNOST_LANG": "xx"}), "es")

    def test_default_output_is_spanish(self):
        code, out, _ = run_cli(["install-toolchain", "--dry-run"], env={"GLASNOST_LANG": ""})
        self.assertEqual(code, 0)
        self.assertIn("Simulación", out)


class Lockfile(unittest.TestCase):
    def load(self, payload) -> glasnost.Lock:
        with tempfile.TemporaryDirectory() as tmp:
            text = payload if isinstance(payload, str) else json.dumps(payload)
            (Path(tmp) / glasnost.LOCKFILE).write_text(text, encoding="utf-8")
            return glasnost.load_lock(Path(tmp), "en")

    GOOD = {"schema": 1, "cpctelera_next": {"url": "https://x.test/c.git", "rev": "a" * 40}}

    def test_real_lockfile_is_valid(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GLASNOST_CPCTELERA_URL", None)
            lock = glasnost.load_lock(ROOT, "en")
        self.assertRegex(lock.rev, r"^[0-9a-f]{40}$")
        self.assertTrue(lock.url.startswith("https://"))

    def test_release_workflow_pins_the_same_commit(self):
        workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        pinned = re.findall(r"CPCTELERA_REV:\s*([0-9a-f]{40})", workflow)
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GLASNOST_CPCTELERA_URL", None)
            self.assertEqual(pinned, [glasnost.load_lock(ROOT, "en").rev])

    def test_valid_lock_loads(self):
        self.assertEqual(self.load(self.GOOD).rev, "a" * 40)

    def test_invalid_locks_are_rejected_with_a_translated_message(self):
        bad = {
            "wrong schema": dict(self.GOOD, schema=2),
            "no schema": {"cpctelera_next": self.GOOD["cpctelera_next"]},
            "short rev": {"schema": 1, "cpctelera_next": {"url": "https://x.test/c.git", "rev": "abc123"}},
            "branch name": {"schema": 1, "cpctelera_next": {"url": "https://x.test/c.git", "rev": "main"}},
            "uppercase rev": {"schema": 1, "cpctelera_next": {"url": "https://x.test/c.git", "rev": "A" * 40}},
            "http url": {"schema": 1, "cpctelera_next": {"url": "http://x.test/c.git", "rev": "a" * 40}},
            "missing entry": {"schema": 1},
            "not an object": [1, 2],
            "not json": "{nope",
        }
        for name, payload in bad.items():
            with self.subTest(name), self.assertRaises(glasnost.CliError) as caught:
                self.load(payload)
            self.assertIn("toolchain.lock.json is not valid", str(caught.exception), name)

    def test_missing_lockfile_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(glasnost.CliError):
            glasnost.load_lock(Path(tmp), "en")


class Install(unittest.TestCase):
    def test_dry_run_lists_every_step_and_changes_nothing(self):
        sdk = FakeSdk(self)
        code, out, _ = sdk.cli("install-toolchain", "--dry-run")
        self.assertEqual(code, 0)
        steps = re.findall(r"\[(\d+)/(\d+)\]", out)
        self.assertEqual(len(steps), 3 + len(glasnost.MAKE_STEPS))
        self.assertEqual({total for _, total in steps}, {str(3 + len(glasnost.MAKE_STEPS))})
        self.assertIn("Dry run", out)
        self.assertFalse((sdk.tmp / "tc").exists())

    def test_install_builds_verifies_and_marks_complete(self):
        sdk = FakeSdk(self)
        code, out, err = sdk.cli("install-toolchain")
        self.assertEqual((code, err), (0, ""), out)
        self.assertTrue((sdk.checkout / glasnost.COMPLETE_MARKER).is_file())
        self.assertEqual(glasnost.missing_files(sdk.checkout / "cpctelera"), [])
        head = subprocess.run(["git", "-C", str(sdk.checkout), "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout.strip()
        self.assertEqual(head, sdk.rev)
        self.assertIn("installed at", out)

    def test_second_install_is_a_noop_and_force_redoes_it(self):
        sdk = FakeSdk(self)
        self.assertEqual(sdk.cli("install-toolchain")[0], 0)
        marker = sdk.checkout / glasnost.COMPLETE_MARKER
        before = marker.stat().st_mtime_ns
        code, out, _ = sdk.cli("install-toolchain")
        self.assertEqual(code, 0)
        self.assertIn("already installed", out)
        self.assertEqual(marker.stat().st_mtime_ns, before)
        (sdk.checkout / "stale.txt").write_text("x", encoding="utf-8")
        self.assertEqual(sdk.cli("install-toolchain", "--force")[0], 0)
        self.assertFalse((sdk.checkout / "stale.txt").exists(), "--force starts from a clean tree")
        self.assertTrue(marker.is_file())

    def test_a_failing_build_step_leaves_no_marker_and_names_the_step(self):
        sdk = FakeSdk(self, broken="tools/2cdt")
        code, out, err = sdk.cli("install-toolchain")
        self.assertEqual(code, 1)
        self.assertIn("tools/2cdt", err)
        self.assertFalse((sdk.checkout / glasnost.COMPLETE_MARKER).exists())
        self.assertNotIn("installed at", out)
        # the toolchain stays unusable until an install completes
        code, _, err = sdk.cli("path")
        self.assertEqual(code, 1)
        self.assertIn("not installed", err)

    def test_a_build_that_succeeds_without_its_files_is_not_marked_complete(self):
        sdk = FakeSdk(self, silent="tools/zx7b")
        code, out, err = sdk.cli("install-toolchain")
        self.assertEqual(code, 1)
        self.assertIn("tools/zx7b/bin/zx7b", err)
        self.assertFalse((sdk.checkout / glasnost.COMPLETE_MARKER).exists())
        self.assertNotIn("installed at", out)

    def test_retry_after_failure_resumes_from_the_partial_checkout(self):
        sdk = FakeSdk(self, broken="tools/2cdt")
        self.assertEqual(sdk.cli("install-toolchain")[0], 1)
        built = sdk.checkout / "cpctelera" / "tools" / "sdcc-4.5.0" / "bin" / "sdcc"
        self.assertTrue(built.is_file(), "steps before the failure are kept")
        # a missing dependency gets installed between attempts: the step now works
        (sdk.checkout / "cpctelera" / "tools" / "2cdt" / "ok").write_text("", encoding="utf-8")
        code, out, err = sdk.cli("install-toolchain")
        self.assertEqual((code, err), (0, ""), out)
        self.assertTrue((sdk.checkout / glasnost.COMPLETE_MARKER).is_file())

    def test_retry_restores_modified_tracked_files_to_the_pinned_commit(self):
        sdk = FakeSdk(self, broken="tools/2cdt")
        self.assertEqual(sdk.cli("install-toolchain")[0], 1)
        makefile = sdk.checkout / "cpctelera" / "tools" / "2cdt" / "Makefile"
        original = makefile.read_text(encoding="utf-8")
        makefile.write_text("all:\n\t@mkdir -p bin && echo x > bin/2cdt && chmod +x bin/2cdt\n", encoding="utf-8")
        self.assertEqual(sdk.cli("install-toolchain")[0], 1, "the edit must not survive the retry")
        self.assertEqual(makefile.read_text(encoding="utf-8"), original)

    def test_a_stale_marker_is_removed_when_a_reinstall_starts(self):
        sdk = FakeSdk(self)
        self.assertEqual(sdk.cli("install-toolchain")[0], 0)
        marker = sdk.checkout / glasnost.COMPLETE_MARKER
        (sdk.checkout / "cpctelera" / "tools" / "zx7b" / "bin" / "zx7b").unlink()  # incomplete, marker stays

        def make_fails(command, **kwargs):
            if command[0] == "make":
                return subprocess.CompletedProcess(command, 2)
            return quiet_runner(command, **kwargs)

        self.assertEqual(sdk.cli("install-toolchain", runner=make_fails)[0], 1)
        self.assertFalse(marker.exists(), "a failed reinstall must not keep the old marker")

    def test_two_installs_of_the_same_commit_cannot_run_together(self):
        import fcntl
        sdk = FakeSdk(self)
        lock_dir = sdk.tmp / "tc" / "cpctelera-next"
        lock_dir.mkdir(parents=True)
        with open(lock_dir / f".{sdk.rev}.lock", "w") as held:
            fcntl.flock(held, fcntl.LOCK_EX)
            code, _, err = sdk.cli("install-toolchain")
        self.assertEqual(code, 1)
        self.assertIn("Another install", err)
        self.assertEqual(sdk.cli("install-toolchain")[0], 0, "released lock allows the install")

    def test_fetched_tree_with_the_wrong_commit_is_refused(self):
        sdk = FakeSdk(self)

        def lying_runner(command, **kwargs):
            result = quiet_runner(command, **kwargs)
            if "rev-parse" in command:
                result.stdout = "0" * 40 + "\n"
            return result

        code, _, err = sdk.cli("install-toolchain", runner=lying_runner)
        self.assertEqual(code, 1)
        self.assertIn("lockfile pins", err)
        self.assertFalse((sdk.checkout / glasnost.COMPLETE_MARKER).exists())

    def test_missing_build_tools_stop_before_touching_anything(self):
        sdk = FakeSdk(self)
        with mock.patch.object(glasnost.shutil, "which", return_value=None):
            code, _, err = sdk.cli("install-toolchain")
        self.assertEqual(code, 1)
        self.assertIn("Missing build tools", err)
        for tool in glasnost.BUILD_TOOLS:
            self.assertIn(tool, err)
        self.assertFalse((sdk.tmp / "tc").exists())

    def test_missing_boost_is_reported(self):
        sdk = FakeSdk(self)
        with mock.patch.object(glasnost, "BOOST_HEADER", sdk.tmp / "no-boost.hpp"):
            code, _, err = sdk.cli("install-toolchain")
        self.assertEqual(code, 1)
        self.assertIn("libboost-dev", err)

    def test_installing_changes_nothing_in_the_sdk_root_home_cwd_or_upstream(self):
        sdk = FakeSdk(self)
        home, cwd = sdk.tmp / "home", sdk.tmp / "cwd"
        home.mkdir()
        cwd.mkdir()
        watched = (sdk.root, home, cwd, sdk.upstream)
        before = [{p: p.stat().st_mtime_ns for p in w.rglob("*")} for w in watched]
        previous = os.getcwd()
        os.chdir(cwd)
        try:
            code, _, _ = sdk.cli("install-toolchain", extra_env={"HOME": str(home)})
        finally:
            os.chdir(previous)
        self.assertEqual(code, 0)
        after = [{p: p.stat().st_mtime_ns for p in w.rglob("*")} for w in watched]
        self.assertEqual(after, before)
        self.assertTrue(any((sdk.tmp / "tc").rglob("*")))

    def test_untrusted_repository_urls_are_refused(self):
        sdk = FakeSdk(self)
        for url in ("--upload-pack=touch /tmp/pwned", "ext::sh -c id", "http://x.test/c.git",
                    "git://x.test/c.git", "ssh://x.test/c.git", "", "/tmp/local", "https://a b"):
            with self.subTest(url):
                code, _, err = sdk.cli("install-toolchain", extra_env={"GLASNOST_CPCTELERA_URL": url})
                self.assertEqual(code, 1)
                self.assertIn("GLASNOST_CPCTELERA_URL", err)
                self.assertFalse((sdk.tmp / "tc").exists())

    def test_operating_system_errors_become_translated_messages(self):
        sdk = FakeSdk(self)
        blocker = sdk.tmp / "blocker"
        blocker.write_text("a file, not a directory", encoding="utf-8")
        code, _, err = sdk.cli("install-toolchain", extra_env={"GLASNOST_TOOLCHAIN_DIR": str(blocker)})
        self.assertEqual(code, 1)
        self.assertIn("System error", err)
        self.assertNotIn("Traceback", err)
        code, _, err = run_cli(["--lang", "es", "install-toolchain"], root=sdk.root,
                               env=dict(sdk.env, GLASNOST_TOOLCHAIN_DIR=str(blocker)))
        self.assertIn("Error del sistema", err)

    def test_a_missing_build_binary_is_reported_not_raised(self):
        sdk = FakeSdk(self)

        def no_git(command, **kwargs):
            raise FileNotFoundError(2, "No such file or directory", command[0])

        code, _, err = sdk.cli("install-toolchain", runner=no_git)
        self.assertEqual(code, 1)
        self.assertIn("System error", err)
        self.assertIn("git", err)

    def test_ctrl_c_exits_130_with_a_message(self):
        sdk = FakeSdk(self)

        def interrupted(command, **kwargs):
            raise KeyboardInterrupt

        code, _, err = sdk.cli("install-toolchain", runner=interrupted)
        self.assertEqual((code, err.strip()), (130, "Interrupted."))


class Resolution(unittest.TestCase):
    def test_env_override_beats_the_managed_toolchain(self):
        sdk = FakeSdk(self)
        self.assertEqual(sdk.cli("install-toolchain")[0], 0)
        other = sdk.tmp / "other" / "cpctelera"
        for relative in glasnost.REQUIRED_FILES:
            file = other / relative
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text("x", encoding="utf-8")
            file.chmod(0o755)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                mock.patch.dict(os.environ, dict(sdk.env, CPCT_NEXT_PATH=str(other))):
            code = glasnost.main(["--lang", "en", "path"], root=sdk.root)
        self.assertEqual((code, out.getvalue().strip()), (0, str(other)))

    def test_env_override_that_is_incomplete_is_rejected(self):
        sdk = FakeSdk(self)
        empty = sdk.tmp / "empty"
        empty.mkdir()
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                mock.patch.dict(os.environ, dict(sdk.env, CPCT_NEXT_PATH=str(empty))):
            code = glasnost.main(["--lang", "en", "path"], root=sdk.root)
        self.assertEqual(code, 1)
        self.assertIn("incomplete", err.getvalue())
        self.assertIn("cpctelera.lib", err.getvalue())

    def test_managed_install_with_a_deleted_tool_is_incomplete(self):
        sdk = FakeSdk(self)
        self.assertEqual(sdk.cli("install-toolchain")[0], 0)
        (sdk.checkout / "cpctelera" / "tools" / "zx7b" / "bin" / "zx7b").unlink()
        code, _, err = sdk.cli("path")
        self.assertEqual(code, 1)
        self.assertIn("zx7b", err)

    def test_a_tool_that_is_not_executable_counts_as_missing(self):
        sdk = FakeSdk(self)
        self.assertEqual(sdk.cli("install-toolchain")[0], 0)
        sdk_bin = sdk.checkout / "cpctelera" / "tools" / "sdcc-4.5.0" / "bin" / "sdcc"
        sdk_bin.chmod(sdk_bin.stat().st_mode & ~(stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))
        self.assertEqual(glasnost.missing_files(sdk.checkout / "cpctelera"), ["tools/sdcc-4.5.0/bin/sdcc"])

    def test_an_empty_library_counts_as_missing(self):
        sdk = FakeSdk(self)
        self.assertEqual(sdk.cli("install-toolchain")[0], 0)
        (sdk.checkout / "cpctelera" / "cpctelera.lib").write_text("", encoding="utf-8")
        self.assertEqual(glasnost.missing_files(sdk.checkout / "cpctelera"), ["cpctelera.lib"])

    def test_a_partial_checkout_without_the_marker_is_not_a_toolchain(self):
        sdk = FakeSdk(self)
        self.assertEqual(sdk.cli("install-toolchain")[0], 0)
        (sdk.checkout / glasnost.COMPLETE_MARKER).unlink()
        code, _, err = sdk.cli("path")
        self.assertEqual(code, 1)
        self.assertIn("not installed", err)


class Doctor(unittest.TestCase):
    def test_doctor_passes_with_a_complete_toolchain(self):
        sdk = FakeSdk(self)
        self.assertEqual(sdk.cli("install-toolchain")[0], 0)
        code, out, _ = sdk.cli("doctor")
        self.assertEqual(code, 0, out)
        self.assertIn("All set.", out)
        self.assertIn("CPCTelera Next", out)

    def test_doctor_fails_and_counts_what_is_missing(self):
        sdk = FakeSdk(self)
        with mock.patch.object(glasnost.shutil, "which", return_value=None):
            code, out, _ = sdk.cli("doctor")
        self.assertEqual(code, 1)
        missing = len(glasnost.BUILD_TOOLS) + 1  # build tools + toolchain
        self.assertEqual(out.count("MISSING"), missing)
        self.assertIn(f"{missing} item(s) missing", out)

    def test_doctor_reports_missing_boost_with_the_fix(self):
        sdk = FakeSdk(self)
        with mock.patch.object(glasnost, "BOOST_HEADER", sdk.tmp / "none.hpp"):
            _, out, _ = sdk.cli("doctor")
        self.assertIn("apt install libboost-dev", out)

    def test_doctor_in_spanish(self):
        sdk = FakeSdk(self)
        env = dict(sdk.env)
        env.pop("CPCT_NEXT_PATH", None)
        code, out, _ = run_cli(["--lang", "es", "doctor"], root=sdk.root, env=env)
        self.assertEqual(code, 1)
        self.assertIn("diagnóstico", out)
        self.assertIn("FALTA", out)

    def test_network_check_is_opt_in(self):
        sdk = FakeSdk(self)
        calls = []

        def spy(command, **kwargs):
            calls.append(list(command))
            return quiet_runner(command, **kwargs)

        sdk.cli("doctor", runner=spy)
        self.assertFalse([c for c in calls if "ls-remote" in c])
        _, out, _ = sdk.cli("doctor", "--network", runner=spy)
        self.assertTrue([c for c in calls if "ls-remote" in c])
        self.assertIn("network", out)

    def test_network_failure_counts_as_missing_only_when_asked(self):
        sdk = FakeSdk(self)

        def offline(command, **kwargs):
            if "ls-remote" in command:
                raise subprocess.TimeoutExpired(command, 1)
            return quiet_runner(command, **kwargs)

        with mock.patch.object(glasnost, "BOOST_HEADER", glasnost.BOOST_HEADER):
            _, out, _ = sdk.cli("doctor", "--network", runner=offline)
        self.assertIn("MISSING  network", out)


class Commands(unittest.TestCase):
    """build, test and run only compose commands; a recording runner checks them."""

    def setUp(self):
        self.sdk = FakeSdk(self)
        self.assertEqual(self.sdk.cli("install-toolchain")[0], 0)
        self.calls: list[tuple[list[str], dict]] = []

        def recorder(command, **kwargs):
            self.calls.append((list(command), kwargs))
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        self.recorder = recorder
        self.cpct = str(self.sdk.checkout / "cpctelera")

    def test_build_generates_then_builds_the_named_examples_with_the_managed_toolchain(self):
        code, _, _ = self.sdk.cli("build", "minimal", runner=self.recorder)
        self.assertEqual(code, 0)
        self.assertEqual(self.calls[0][0][:3], ["make", "--no-print-directory", "generate"])
        self.assertEqual(self.calls[1][0][1:], ["tools/build_examples.py", "minimal"])
        for _, kwargs in self.calls:
            self.assertEqual(kwargs["env"]["CPCT_NEXT_PATH"], self.cpct)
            self.assertEqual(kwargs["cwd"], self.sdk.root)

    def test_build_stops_when_generation_fails(self):
        def failing(command, **kwargs):
            self.calls.append((list(command), kwargs))
            return subprocess.CompletedProcess(command, 7)

        code, _, _ = self.sdk.cli("build", runner=failing)
        self.assertEqual(code, 7)
        self.assertEqual(len(self.calls), 1)

    def test_build_rejects_unknown_examples_before_running_anything(self):
        code, _, err = self.sdk.cli("build", "nope", runner=self.recorder)
        self.assertEqual(code, 1)
        self.assertIn('no example "nope"', err)
        self.assertIn("minimal", err)
        self.assertEqual(self.calls, [])

    def test_test_runs_make_test_with_the_toolchain(self):
        code, _, _ = self.sdk.cli("test", runner=self.recorder)
        self.assertEqual(code, 0)
        self.assertEqual(self.calls[0][0][:2], ["make", "test"])
        self.assertEqual(self.calls[0][1]["env"]["CPCT_NEXT_PATH"], self.cpct)

    def test_run_passes_the_example_and_emulator_options(self):
        code, _, _ = self.sdk.cli("run", "minimal", "--", "--emulator", "x", runner=self.recorder)
        self.assertEqual(code, 0)
        self.assertEqual(self.calls[0][0][1:], ["tools/run_example.py", "minimal", "--emulator", "x"])

    def test_only_the_leading_double_dash_is_dropped_from_run_arguments(self):
        self.sdk.cli("run", "minimal", "--", "--", "--flag", runner=self.recorder)
        self.assertEqual(self.calls[-1][0][1:], ["tools/run_example.py", "minimal", "--", "--flag"])
        self.sdk.cli("run", "minimal", runner=self.recorder)
        self.assertEqual(self.calls[-1][0][1:], ["tools/run_example.py", "minimal"])

    def test_commands_exit_with_the_exit_code_of_the_underlying_tool(self):
        def failing(command, **kwargs):
            return subprocess.CompletedProcess(command, 5)

        self.assertEqual(self.sdk.cli("test", runner=failing)[0], 5)
        self.assertEqual(self.sdk.cli("run", "minimal", runner=failing)[0], 5)

    def test_without_a_toolchain_build_test_and_run_explain_what_to_do(self):
        empty = FakeSdk(self)
        for argv in (["build"], ["test"], ["run", "minimal"], ["path"]):
            with self.subTest(argv):
                code, _, err = empty.cli(*argv, runner=self.recorder)
                self.assertEqual(code, 1)
                self.assertIn("install-toolchain", err)
        self.assertEqual(self.calls, [])


class RelativePaths(unittest.TestCase):
    def test_relative_toolchain_dir_and_cpct_path_are_resolved_against_the_caller(self):
        sdk = FakeSdk(self)
        elsewhere = sdk.tmp / "elsewhere"
        elsewhere.mkdir()
        previous = os.getcwd()
        os.chdir(elsewhere)
        try:
            env = dict(sdk.env, GLASNOST_TOOLCHAIN_DIR="rel-tc")
            code, _, _ = run_cli(["--lang", "en", "install-toolchain"], root=sdk.root,
                                 runner=quiet_runner, env=env)
            self.assertEqual(code, 0)
            self.assertTrue((elsewhere / "rel-tc" / "cpctelera-next" / sdk.rev / glasnost.COMPLETE_MARKER).is_file())
            calls = []

            def recorder(command, **kwargs):
                calls.append(kwargs)
                return subprocess.CompletedProcess(command, 0)

            code, out, _ = run_cli(["--lang", "en", "path"], root=sdk.root, runner=recorder, env=env)
            self.assertEqual(out.strip(), str(elsewhere / "rel-tc" / "cpctelera-next" / sdk.rev / "cpctelera"))
            run_cli(["test"], root=sdk.root, runner=recorder, env=env)
            self.assertTrue(Path(calls[0]["env"]["CPCT_NEXT_PATH"]).is_absolute())
            self.assertNotEqual(Path(calls[0]["cwd"]), elsewhere, "commands still run in the SDK root")
            override = dict(sdk.env, CPCT_NEXT_PATH="rel-tc/cpctelera-next/%s/cpctelera" % sdk.rev)
            code, out, _ = run_cli(["path"], root=sdk.root, runner=recorder, env=override)
            self.assertTrue(Path(out.strip()).is_absolute())
        finally:
            os.chdir(previous)


class Shim(unittest.TestCase):
    """The real bin/glasnost, as a user runs it."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.toolchain_dir = tmp.name  # a mutated or broken CLI must never touch .toolchain/

    def run_shim(self, *argv, env=None):
        clean = {k: v for k, v in os.environ.items() if k not in ("CPCT_NEXT_PATH", "GLASNOST_LANG")}
        clean["GLASNOST_TOOLCHAIN_DIR"] = self.toolchain_dir
        return subprocess.run([str(SHIM), *argv], capture_output=True, text=True,
                              env=dict(clean, **(env or {})), cwd="/")

    def test_shim_is_executable_and_runs_from_any_directory(self):
        self.assertTrue(os.access(SHIM, os.X_OK))
        result = self.run_shim("version")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.strip())

    def test_shim_follows_a_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            link = Path(tmp) / "glasnost"
            link.symlink_to(SHIM)
            result = subprocess.run([str(link), "--lang", "en", "install-toolchain", "--dry-run"],
                                    capture_output=True, text=True, cwd="/",
                                    env=dict(os.environ, GLASNOST_TOOLCHAIN_DIR=self.toolchain_dir))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Dry run", result.stdout)

    def test_usage_error_exits_two(self):
        self.assertEqual(self.run_shim("frobnicate").returncode, 2)
        self.assertEqual(self.run_shim().returncode, 2)

    def test_help_is_translated(self):
        spanish = self.run_shim("--help").stdout
        english = self.run_shim("--lang", "en", "--help").stdout
        self.assertIn("Interfaz única", spanish)
        self.assertIn("Single interface", english)
        for command in ("doctor", "install-toolchain", "build", "test", "run", "path", "version"):
            self.assertIn(command, spanish)

    def test_language_from_environment(self):
        result = self.run_shim("install-toolchain", "--dry-run", env={"GLASNOST_LANG": "en"})
        self.assertIn("Dry run", result.stdout)

    def test_toolchain_dir_is_ignored_by_git(self):
        ignored = subprocess.run(["git", "check-ignore", ".toolchain/cpctelera-next/x", "projects/p"],
                                 cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(sorted(ignored.stdout.split()), [".toolchain/cpctelera-next/x", "projects/p"])


if __name__ == "__main__":
    unittest.main()
