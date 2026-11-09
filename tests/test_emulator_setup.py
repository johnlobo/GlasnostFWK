"""`glasnost run` finds, offers, downloads and remembers a CPC emulator (tools/emulator_setup.py).

No network and no emulator are needed: downloads are served by fake openers and the pinned
SHA-256 of each asset is patched to that of the fake archive.
"""

from __future__ import annotations

import contextlib
import hashlib
import http.client
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import emulator_setup as emu  # noqa: E402
import glasnost  # noqa: E402
import run_example  # noqa: E402
from test_glasnost import FakeSdk  # noqa: E402


def make_executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n", encoding="utf-8")
    path.chmod(0o755)
    return path


class FakeResponse:
    def __init__(self, data: bytes):
        self.data, self.length, self.position = data, len(data), 0

    def read(self, size: int = -1) -> bytes:
        chunk = self.data[self.position:] if size < 0 else self.data[self.position:self.position + size]
        self.position += len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def zip_bytes(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as bundle:
        for name, data in members.items():
            bundle.writestr(name, data)
    return buffer.getvalue()


def patched_assets(key: str, data: bytes):
    asset = {"file": "fake.zip", "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    return mock.patch.dict(emu.RVM_ASSETS, {key: asset})


class Temp(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="glasnost-emu-")).resolve()
        self.addCleanup(subprocess.run, ["rm", "-rf", str(self.tmp)])
        self.root = self.tmp / "sdk"
        self.root.mkdir()


class Config(Temp):
    def test_nothing_is_configured_in_a_fresh_sdk(self):
        self.assertIsNone(emu.read_config(self.root))
        self.assertIsNone(emu.configured(self.root))
        self.assertFalse(emu.declined(self.root))

    def test_a_saved_emulator_round_trips_and_is_found_again(self):
        exe = make_executable(self.tmp / "bin" / "amspirit")
        emu.save_emulator(self.root, exe)
        self.assertEqual(emu.configured(self.root), exe)
        data = json.loads(emu.config_path(self.root).read_text())
        self.assertEqual((data["version"], data["kind"], data["path"]), (1, "generic", str(exe)))

    def test_a_saved_emulator_that_disappeared_counts_as_not_configured(self):
        exe = make_executable(self.tmp / "emu")
        emu.save_emulator(self.root, exe)
        exe.unlink()
        self.assertIsNone(emu.configured(self.root))
        self.assertEqual(emu.stale_path(self.root), str(exe))

    def test_declined_is_remembered_and_reset_clears_everything(self):
        emu.save_declined(self.root)
        self.assertTrue(emu.declined(self.root))
        self.assertIsNone(emu.configured(self.root))
        self.assertTrue(emu.reset(self.root))
        self.assertFalse(emu.declined(self.root))
        self.assertFalse(emu.reset(self.root))

    def test_a_corrupt_config_file_is_ignored(self):
        emu.config_path(self.root).parent.mkdir(parents=True)
        emu.config_path(self.root).write_text("{not json", encoding="utf-8")
        self.assertIsNone(emu.configured(self.root))


class ConfigRobustness(Temp):
    def write(self, data) -> None:
        emu.config_path(self.root).parent.mkdir(parents=True, exist_ok=True)
        emu.config_path(self.root).write_text(json.dumps(data), encoding="utf-8")

    def test_fields_of_the_wrong_type_are_ignored_instead_of_crashing(self):
        for bad in ({"path": 5}, {"path": ["x"]}, {"path": "/x", "args": [1]}, {"path": "/x", "args": "--i={image}"},
                    {"kind": 3}, []):
            with self.subTest(bad):
                self.write(bad)
                self.assertIsNone(emu.configured(self.root))
                emu.stale_path(self.root)    # must not raise
                self.assertEqual(emu.build_command("/x", Path("/i/a.dsk"), self.tmp, "a", self.root),
                                 ["/x", "/i/a.dsk"])   # bad "args"/"kind" fall back to the defaults

    def test_paths_inside_the_sdk_are_stored_relative_and_survive_moving_it(self):
        exe = make_executable(self.root / "tools" / "emulators" / "x" / "RetroVirtualMachine")
        emu.save_emulator(self.root, exe, "rvm")
        self.assertEqual(json.loads(emu.config_path(self.root).read_text())["path"],
                         "tools/emulators/x/RetroVirtualMachine")
        moved = self.tmp / "moved-sdk"
        subprocess.run(["cp", "-a", str(self.root), str(moved)], check=True)
        subprocess.run(["rm", "-rf", str(self.root)], check=True)
        self.assertEqual(emu.configured(moved), moved / "tools" / "emulators" / "x" / "RetroVirtualMachine")

    def test_paths_outside_the_sdk_stay_absolute(self):
        exe = make_executable(self.tmp / "elsewhere" / "emu")
        emu.save_emulator(self.root, exe)
        self.assertEqual(json.loads(emu.config_path(self.root).read_text())["path"], str(exe))

    def test_a_relative_path_typed_by_the_user_is_made_absolute(self):
        make_executable(self.tmp / "work" / "amspirit")
        previous = Path.cwd()
        os.chdir(self.tmp / "work")
        try:
            path = emu.normalize("./amspirit")
        finally:
            os.chdir(previous)
        self.assertTrue(path.is_absolute())
        self.assertEqual(path, self.tmp / "work" / "amspirit")


class Discovery(Temp):
    def test_kind_of(self):
        self.assertEqual(emu.kind_of("/x/RetroVirtualMachine"), "rvm")
        self.assertEqual(emu.kind_of("C:/x/RetroVirtualMachine.exe"), "rvm")
        self.assertEqual(emu.kind_of("/Applications/MacAPE.app/Contents/MacOS/MacAPE"), "macape")
        self.assertEqual(emu.kind_of("/usr/bin/amspirit"), "generic")

    def test_normalize_accepts_an_executable_and_rejects_the_rest(self):
        exe = make_executable(self.tmp / "emu")
        self.assertEqual(emu.normalize(f'  "{exe}"  '), exe)
        for bad in (self.tmp / "missing", self.tmp):
            with self.subTest(bad), self.assertRaises(emu.SetupError) as raised:
                emu.normalize(str(bad))
            self.assertEqual(raised.exception.key, "emu.bad_path")
        plain = self.tmp / "plain.txt"
        plain.write_text("x")
        plain.chmod(0o644)
        with self.assertRaises(emu.SetupError):
            emu.normalize(str(plain))

    def test_normalize_resolves_a_macos_app_bundle_to_its_binary(self):
        binary = make_executable(self.tmp / "Retro Virtual Machine 2.app" / "Contents" / "MacOS" / "RetroVirtualMachine")
        self.assertEqual(emu.normalize(str(self.tmp / "Retro Virtual Machine 2.app")), binary)

    def test_candidates_find_path_commands_the_sibling_amspirit_and_downloaded_builds(self):
        sibling = make_executable(self.tmp / "tools" / "amspirit-lite" / "run.sh")
        in_path = make_executable(self.tmp / "bin" / "macape")
        downloaded = make_executable(self.root / "tools" / "emulators" / "retro-virtual-machine-x" / "RetroVirtualMachine")
        found = emu.candidates(self.root, home=self.tmp / "home", path_env=str(self.tmp / "bin"))
        self.assertEqual(found, [sibling, in_path, downloaded])

    def test_candidates_have_no_duplicates_and_skip_non_executables(self):
        make_executable(self.tmp / "bin" / "amspirit")
        (self.tmp / "bin" / "macape").write_text("x")
        (self.tmp / "bin" / "macape").chmod(0o644)
        found = emu.candidates(self.root, home=self.tmp / "home", path_env=f"{self.tmp / 'bin'}{os.pathsep}{self.tmp / 'bin'}")
        self.assertEqual(found, [self.tmp / "bin" / "amspirit"])

    def test_platform_keys(self):
        for system, machine, expected in (
                ("Linux", "x86_64", "linux-x86_64"), ("Linux", "aarch64", "linux-aarch64"),
                ("Darwin", "arm64", "macos"), ("Darwin", "x86_64", "macos"),
                ("Windows", "AMD64", "windows-x86_64"), ("Windows", "ARM64", None), ("FreeBSD", "amd64", None)):
            with self.subTest(system, machine=machine):
                self.assertEqual(emu.platform_key(system, machine), expected)

    def test_every_platform_has_a_pinned_asset(self):
        for key in ("linux-x86_64", "linux-aarch64", "windows-x86_64", "macos"):
            asset = emu.RVM_ASSETS[key]
            self.assertRegex(asset["sha256"], r"^[0-9a-f]{64}$")
            self.assertGreater(asset["size"], 1_000_000)
            self.assertIn(emu.RVM_VERSION, asset["file"])


class Download(Temp):
    def test_a_good_download_is_verified_written_and_reports_progress(self):
        data = b"x" * 3_000_000
        seen = []
        target = self.tmp / "d" / "file.zip"
        emu.download("https://h/f", target, len(data), hashlib.sha256(data).hexdigest(),
                     opener=lambda url: FakeResponse(data), progress=lambda done, total: seen.append((done, total)))
        self.assertEqual(target.read_bytes(), data)
        self.assertEqual(seen[-1], (len(data), len(data)))
        self.assertFalse(list(target.parent.glob("*.part")))

    def test_a_corrupt_download_is_rejected_and_leaves_no_file(self):
        target = self.tmp / "file.zip"
        with self.assertRaises(emu.SetupError) as raised:
            emu.download("https://h/f", target, 3, "0" * 64, opener=lambda url: FakeResponse(b"abc"))
        self.assertEqual(raised.exception.key, "emu.sha_mismatch")
        self.assertFalse(target.exists())
        self.assertFalse(list(self.tmp.glob("*.part")))

    def test_a_network_error_becomes_a_setup_error(self):
        def failing(url):
            raise OSError("no route to host")

        with self.assertRaises(emu.SetupError) as raised:
            emu.download("https://h/f", self.tmp / "f", 1, "0" * 64, opener=failing)
        self.assertEqual(raised.exception.key, "emu.download_failed")
        self.assertIn("no route", str(raised.exception.values["reason"]))


class DownloadFailures(Temp):
    def test_a_dropped_connection_is_a_setup_error_and_leaves_no_part_file(self):
        class Dropping(FakeResponse):
            def read(self, size=-1):
                if self.position:
                    raise http.client.IncompleteRead(b"x", 10)
                return super().read(5)

        with self.assertRaises(emu.SetupError) as raised:
            emu.download("https://h/f", self.tmp / "f.zip", 100, "0" * 64, opener=lambda url: Dropping(b"x" * 100))
        self.assertEqual(raised.exception.key, "emu.download_failed")
        self.assertFalse(list(self.tmp.glob("*.part")))
        self.assertFalse((self.tmp / "f.zip").exists())

    def test_ctrl_c_mid_download_leaves_no_part_file(self):
        class Interrupted(FakeResponse):
            def read(self, size=-1):
                if self.position:
                    raise KeyboardInterrupt
                return super().read(5)

        with self.assertRaises(KeyboardInterrupt):
            emu.download("https://h/f", self.tmp / "f.zip", 100, "0" * 64, opener=lambda url: Interrupted(b"x" * 100))
        self.assertFalse(list(self.tmp.glob("*.part")))


class InstallRvm(Temp):
    def test_linux_zip_is_extracted_made_executable_and_saved(self):
        data = zip_bytes({"RetroVirtualMachine": b"\x7fELF"})
        with patched_assets("linux-x86_64", data):
            logged = []
            exe = emu.install_rvm(self.root, "Linux", "x86_64", opener=lambda url: FakeResponse(data),
                                  log=lambda key, values: logged.append(key))
        self.assertTrue(exe.is_file())
        self.assertTrue(exe.stat().st_mode & stat.S_IXUSR)
        self.assertEqual(emu.configured(self.root), exe)
        config = json.loads(emu.config_path(self.root).read_text())
        self.assertEqual((config["kind"], config["version"]), ("rvm", emu.RVM_VERSION))
        self.assertTrue(config["source"].startswith("https://static.retrovm.org/release/"))
        self.assertEqual(logged, ["emu.downloading", "emu.verified", "emu.extracting"])
        self.assertTrue(exe.is_relative_to(self.root / "tools" / "emulators"))

    def test_windows_zip_yields_the_exe(self):
        data = zip_bytes({"RetroVirtualMachine.exe": b"MZ"})
        with patched_assets("windows-x86_64", data):
            exe = emu.install_rvm(self.root, "Windows", "AMD64", opener=lambda url: FakeResponse(data))
        self.assertEqual(exe.name, "RetroVirtualMachine.exe")

    def test_a_second_install_reuses_the_files_without_downloading(self):
        data = zip_bytes({"RetroVirtualMachine": b"\x7fELF"})
        with patched_assets("linux-x86_64", data):
            first = emu.install_rvm(self.root, "Linux", "x86_64", opener=lambda url: FakeResponse(data))
            emu.reset(self.root)

            def forbidden(url):
                raise AssertionError("downloaded again")

            second = emu.install_rvm(self.root, "Linux", "x86_64", opener=forbidden)
        self.assertEqual(first, second)
        self.assertEqual(emu.configured(self.root), first)

    def test_a_zip_with_a_path_escape_is_refused(self):
        data = zip_bytes({"../evil": b"x", "RetroVirtualMachine": b"x"})
        with patched_assets("linux-x86_64", data), self.assertRaises(emu.SetupError) as raised:
            emu.install_rvm(self.root, "Linux", "x86_64", opener=lambda url: FakeResponse(data))
        self.assertEqual(raised.exception.key, "emu.unsafe_archive")
        self.assertFalse(list(self.root.rglob("evil")))   # nothing escaped, wherever it would have landed
        self.assertFalse(list(self.root.rglob("RetroVirtualMachine")))   # and nothing was extracted
        self.assertFalse(list((self.root / "tools" / "emulators").glob("*.part")))
        self.assertIsNone(emu.configured(self.root))

    def test_an_archive_without_the_executable_is_an_error(self):
        data = zip_bytes({"readme.txt": b"x"})
        with patched_assets("linux-x86_64", data), self.assertRaises(emu.SetupError) as raised:
            emu.install_rvm(self.root, "Linux", "x86_64", opener=lambda url: FakeResponse(data))
        self.assertEqual(raised.exception.key, "emu.no_exe")

    def test_a_platform_without_a_build_is_an_error(self):
        with self.assertRaises(emu.SetupError) as raised:
            emu.install_rvm(self.root, "FreeBSD", "amd64")
        self.assertEqual(raised.exception.key, "emu.no_rvm_platform")

    def test_macos_dmg_is_mounted_copied_and_unmounted(self):
        data = b"fake dmg"
        calls = []

        def hdiutil(command, **kwargs):
            calls.append(command[:2])
            if command[1] == "attach":
                mount = Path(command[command.index("-mountpoint") + 1])
                make_executable(mount / "Retro Virtual Machine 2.app" / "Contents" / "MacOS" / "RetroVirtualMachine")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        with patched_assets("macos", data):
            exe = emu.install_rvm(self.root, "Darwin", "arm64", opener=lambda url: FakeResponse(data), run=hdiutil)
        self.assertEqual(calls, [["hdiutil", "attach"], ["hdiutil", "detach"]])
        self.assertEqual(exe.name, "RetroVirtualMachine")
        self.assertIn("Retro Virtual Machine 2.app", str(exe))
        self.assertTrue(exe.is_file())

    def test_an_interrupted_extraction_is_not_mistaken_for_an_install(self):
        data = zip_bytes({"RetroVirtualMachine": b"\x7fELF"})
        real = emu._safe_extract

        def interrupted(archive, target):
            real(archive, target)
            raise KeyboardInterrupt

        with patched_assets("linux-x86_64", data), mock.patch.object(emu, "_safe_extract", interrupted):
            with self.assertRaises(KeyboardInterrupt):
                emu.install_rvm(self.root, "Linux", "x86_64", opener=lambda url: FakeResponse(data))
        folder = self.root / "tools" / "emulators"
        self.assertFalse(list(folder.glob("retro-virtual-machine-*")))   # neither the final folder nor .part
        self.assertIsNone(emu.configured(self.root))
        with patched_assets("linux-x86_64", data):   # and the next try works
            exe = emu.install_rvm(self.root, "Linux", "x86_64", opener=lambda url: FakeResponse(data))
        self.assertTrue(exe.is_file())

    def test_a_dmg_that_will_not_detach_is_not_fatal(self):
        def stubborn(command, **kwargs):
            if command[1] == "attach":
                mount = Path(command[command.index("-mountpoint") + 1])
                make_executable(mount / "Retro Virtual Machine 2.app" / "Contents" / "MacOS" / "RetroVirtualMachine")
            return subprocess.CompletedProcess(command, 1 if command[1] == "detach" else 0, stdout="", stderr="busy")

        with patched_assets("macos", b"d"):
            exe = emu.install_rvm(self.root, "Darwin", "arm64", opener=lambda url: FakeResponse(b"d"), run=stubborn)
        self.assertTrue(exe.is_file())

    def test_a_failed_mount_still_reports_and_does_not_save(self):
        def failing(command, **kwargs):
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="boom")

        with patched_assets("macos", b"d"), self.assertRaises(emu.SetupError) as raised:
            emu.install_rvm(self.root, "Darwin", "arm64", opener=lambda url: FakeResponse(b"d"), run=failing)
        self.assertEqual(raised.exception.key, "emu.dmg_failed")
        self.assertIsNone(emu.configured(self.root))


class LaunchCommand(Temp):
    def test_rvm_defaults_to_the_image_as_its_only_argument(self):
        exe = make_executable(self.root / "RetroVirtualMachine")
        emu.save_emulator(self.root, exe, "rvm")
        self.assertEqual(emu.build_command(str(exe), Path("/i/a.dsk"), self.tmp, "a", self.root),
                         [str(exe), "/i/a.dsk"])

    def test_arguments_can_be_overridden_in_the_config(self):
        exe = make_executable(self.root / "RetroVirtualMachine")
        emu.save_emulator(self.root, exe, "rvm", args=["--b=cpc6128", "--i={image}"])
        self.assertEqual(emu.build_command(str(exe), Path("/i/a.dsk"), self.tmp, "a", self.root),
                         [str(exe), "--b=cpc6128", "--i=/i/a.dsk"])

    def test_macape_keeps_its_special_arguments(self):
        exe = make_executable(self.tmp / "MacAPE")
        noi = self.tmp / "build" / "a" / "obj" / "a.noi"
        noi.parent.mkdir(parents=True)
        noi.write_text("x")
        command = emu.build_command(str(exe), Path("/i/a.dsk"), self.tmp / "build", "a", self.root)
        self.assertEqual(command, [str(exe), "/i/a.dsk", "/A", f"/SYM:{noi}"])

    def test_any_other_emulator_gets_just_the_image(self):
        self.assertEqual(emu.build_command("/x/amspirit", Path("/i/a.cdt"), self.tmp, "a", self.root),
                         ["/x/amspirit", "/i/a.cdt"])

    def test_the_config_of_another_emulator_does_not_leak_its_arguments(self):
        saved = make_executable(self.tmp / "saved")
        emu.save_emulator(self.root, saved, "rvm", args=["--odd={image}"])
        self.assertEqual(emu.build_command("/other/emu", Path("/i/a.dsk"), self.tmp, "a", self.root),
                         ["/other/emu", "/i/a.dsk"])


class RunExampleFindsTheSavedEmulator(Temp):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(run_example, "ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(run_example, "DEFAULT_EMULATOR", self.tmp / "none" / "run.sh")
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(run_example, "EMULATOR_COMMANDS", ())
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.object(run_example, "MACAPE_CANDIDATES", ())
        patcher.start()
        self.addCleanup(patcher.stop)
        patcher = mock.patch.dict(os.environ, {"GLASNOST_EMULATOR": ""})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_the_saved_emulator_is_used_without_any_flag(self):
        exe = make_executable(self.tmp / "emu")
        emu.save_emulator(self.root, exe)
        self.assertEqual(run_example.find_emulator(None), str(exe))

    def test_the_flag_and_the_environment_win_over_the_saved_one(self):
        saved, flag, env = (make_executable(self.tmp / name) for name in ("saved", "flag", "env"))
        emu.save_emulator(self.root, saved)
        self.assertEqual(run_example.find_emulator(str(flag)), str(flag))
        with mock.patch.dict(os.environ, {"GLASNOST_EMULATOR": str(env)}):
            self.assertEqual(run_example.find_emulator(None), str(env))

    def test_declining_the_question_does_not_stop_unattended_discovery(self):
        emu.save_declined(self.root)
        found = make_executable(self.tmp / "none" / "run.sh")
        self.assertEqual(run_example.find_emulator(None), str(found))

    def test_nothing_configured_nothing_found(self):
        self.assertIsNone(run_example.find_emulator(None))


class Harness(unittest.TestCase):
    """A fake SDK and a way to drive main() with scripted answers."""

    def setUp(self):
        self.sdk = FakeSdk(self)
        self.assertEqual(self.sdk.cli("install-toolchain")[0], 0)
        self.calls: list[list[str]] = []
        self.addCleanup(subprocess.run, ["rm", "-rf", str(self.sdk.root / "tools" / "emulators")])

        def recorder(command, **kwargs):
            self.calls.append(list(command))
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

        self.recorder = recorder
        self.home = Path(tempfile.mkdtemp(prefix="glasnost-home-"))
        self.addCleanup(subprocess.run, ["rm", "-rf", str(self.home)])

    def run_cli(self, *argv, answers=(), interactive=True, env=None):
        replies = iter(answers)
        asked: list[str] = []

        def ask(prompt: str) -> str:
            asked.append(prompt)
            try:
                return next(replies)
            except StopIteration:
                raise EOFError from None

        out, err = io.StringIO(), io.StringIO()
        environment = dict(self.sdk.env, GLASNOST_EMULATOR="", PATH=str(self.home))
        environment.update(env or {})
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                mock.patch.dict(os.environ, environment), \
                mock.patch.object(emu.Path, "home", return_value=self.home):
            os.environ.pop("CPCT_NEXT_PATH", None)
            code = glasnost.main(["--lang", "en", *argv], root=self.sdk.root, runner=self.recorder,
                                 ask=ask, interactive=interactive)
        return code, out.getvalue(), err.getvalue(), asked



class RunAsksOnce(Harness):
    """`glasnost run` in a terminal with no emulator: ask, remember, never ask again."""

    def test_not_now_runs_without_an_emulator_and_asks_again_next_time(self):
        code, out, _, asked = self.run_cli("run", "minimal", answers=["3"])
        self.assertEqual(code, 0)
        self.assertIn("No emulator is configured", out)
        self.assertIn("Retro Virtual Machine", out)
        self.assertEqual(len(asked), 1)
        self.assertEqual(self.calls[-1][1:], ["tools/run_example.py", "minimal"])
        self.assertIsNone(emu.read_config(self.sdk.root))
        _, _, _, asked_again = self.run_cli("run", "minimal", answers=["3"])
        self.assertEqual(len(asked_again), 1)

    def test_picking_one_from_this_machine_saves_it_and_the_next_run_is_silent(self):
        exe = make_executable(self.home / "amspirit")
        code, out, _, asked = self.run_cli("run", "minimal", answers=["1", "1"])
        self.assertEqual(code, 0)
        self.assertIn(str(exe), out)
        self.assertIn("uses it by itself", out)
        self.assertEqual(emu.configured(self.sdk.root), exe)
        _, out2, _, asked2 = self.run_cli("run", "minimal", answers=[])
        self.assertEqual(asked2, [])
        self.assertNotIn("No emulator", out2)
        self.assertEqual(self.calls[-1][1:], ["tools/run_example.py", "minimal"])

    def test_typing_a_path_and_a_macos_app_are_accepted(self):
        binary = make_executable(self.tmp_app() / "Contents" / "MacOS" / "BluePixel")
        self.run_cli("run", "minimal", answers=["1", str(binary.parents[2])])
        self.assertEqual(emu.configured(self.sdk.root), binary)

    def tmp_app(self) -> Path:
        return self.home / "Apps" / "BluePixel.app"

    def test_a_wrong_path_is_explained_and_asked_again(self):
        exe = make_executable(self.home / "good")
        _, _, err, asked = self.run_cli("run", "minimal", answers=["1", "/no/such", str(exe)])
        self.assertIn("Not a valid executable: /no/such", err)
        self.assertEqual(emu.configured(self.sdk.root), exe)
        self.assertEqual(len(asked), 3)

    def test_choosing_to_download_installs_rvm_and_saves_it(self):
        fake = make_executable(self.sdk.root / "tools" / "emulators" / "x" / "RetroVirtualMachine")

        def install(root, **kwargs):
            kwargs["log"]("emu.downloading", {"url": "https://u"})
            kwargs["progress"](50, 100)
            kwargs["progress"](100, 100)
            emu.save_emulator(root, fake, "rvm")
            return fake

        with mock.patch.object(emu, "platform_key", return_value="linux-x86_64"), \
                mock.patch.object(emu, "install_rvm", side_effect=install):
            code, out, _, _ = self.run_cli("run", "minimal", answers=["2"])
        self.assertEqual(code, 0)
        self.assertIn("Downloading https://u", out)
        self.assertIn("50%", out)
        self.assertIn("unverified", out)   # the launch arguments of RVM are not verified
        self.assertEqual(emu.configured(self.sdk.root), fake)

    def test_a_failed_download_goes_back_to_the_menu_and_run_still_proceeds(self):
        error = emu.SetupError("emu.download_failed", url="https://u", reason="offline")
        with mock.patch.object(emu, "platform_key", return_value="linux-x86_64"), \
                mock.patch.object(emu, "install_rvm", side_effect=error):
            code, _, err, asked = self.run_cli("run", "minimal", answers=["2", "3"])
        self.assertEqual(code, 0)
        self.assertIn("Could not download https://u: offline", err)
        self.assertEqual(len(asked), 2)
        self.assertIsNone(emu.read_config(self.sdk.root))
        self.assertEqual(self.calls[-1][1:], ["tools/run_example.py", "minimal"])

    def test_never_ask_again_is_remembered(self):
        _, out, _, _ = self.run_cli("run", "minimal", answers=["4"])
        self.assertIn("will not ask again", out)
        self.assertTrue(emu.declined(self.sdk.root))
        _, _, _, asked = self.run_cli("run", "minimal", answers=[])
        self.assertEqual(asked, [])

    def test_nothing_is_asked_without_a_terminal(self):
        code, out, _, asked = self.run_cli("run", "minimal", interactive=False)
        self.assertEqual((code, asked), (0, []))
        self.assertNotIn("No emulator", out)
        self.assertEqual(self.calls[-1][1:], ["tools/run_example.py", "minimal"])

    def test_nothing_is_asked_when_the_user_already_chose_one(self):
        self.run_cli("run", "minimal", "--", "--emulator", "x")
        _, _, _, asked = self.run_cli("run", "minimal", "--", "--emulator=x")
        self.assertEqual(asked, [])
        _, _, _, asked = self.run_cli("run", "minimal", env={"GLASNOST_EMULATOR": "/some/emu"})
        self.assertEqual(asked, [])

    def test_closing_the_input_does_not_crash_and_the_run_proceeds(self):
        code, _, _, _ = self.run_cli("run", "minimal", answers=[])
        self.assertEqual(code, 0)
        self.assertEqual(self.calls[-1][1:], ["tools/run_example.py", "minimal"])

    def test_an_invalid_menu_answer_asks_again(self):
        _, _, err, asked = self.run_cli("run", "minimal", answers=["9", "3"])
        self.assertIn("Not a valid choice: 9", err)
        self.assertEqual(len(asked), 2)

    def test_a_vanished_emulator_is_reported_and_offered_again(self):
        gone = make_executable(self.home / "gone")
        emu.save_emulator(self.sdk.root, gone)
        gone.unlink()
        _, out, _, asked = self.run_cli("run", "minimal", answers=["3"])
        self.assertIn(f"no longer exists: {gone}", out)
        self.assertEqual(len(asked), 1)

    def test_run_in_a_project_also_asks(self):
        project = self.sdk.tmp / "proj"
        project.mkdir()
        (project / "glasnost.project.json").write_text(json.dumps(
            {"schema": 1, "template": "ecs-welcome", "format": 1, "framework": "x", "title": "T"}), encoding="utf-8")
        (project / "example.json").write_text('{"name": "proj"}', encoding="utf-8")
        _, out, _, asked = self.run_cli("run", "--project", str(project), answers=["3"])
        self.assertIn("No emulator is configured", out)
        self.assertEqual(len(asked), 1)


class EmulatorCommand(Harness):
    def test_status_without_a_terminal_changes_nothing(self):
        _, out, _, asked = self.run_cli("emulator", interactive=False)
        self.assertIn("none configured", out)
        self.assertEqual(asked, [])

    def test_set_saves_and_reports(self):
        exe = make_executable(self.home / "emu")
        code, out, _, _ = self.run_cli("emulator", "--set", str(exe), interactive=False)
        self.assertEqual(code, 0)
        self.assertEqual(emu.configured(self.sdk.root), exe)
        self.assertIn("Emulator saved", out)
        _, status, _, _ = self.run_cli("emulator", interactive=False)
        self.assertIn(str(exe), status)

    def test_set_with_a_bad_path_fails(self):
        code, _, err, _ = self.run_cli("emulator", "--set", "/no/such", interactive=False)
        self.assertEqual(code, 1)
        self.assertIn("Not a valid executable", err)

    def test_reset_clears_it(self):
        emu.save_declined(self.sdk.root)
        _, out, _, _ = self.run_cli("emulator", "--reset", interactive=False)
        self.assertIn("cleared", out)
        self.assertIsNone(emu.read_config(self.sdk.root))
        _, out, _, _ = self.run_cli("emulator", "--reset", interactive=False)
        self.assertIn("no emulator configuration", out)

    def test_download_flag_installs_without_asking(self):
        fake = make_executable(self.sdk.root / "tools" / "emulators" / "x" / "RetroVirtualMachine")

        def install(root, **kwargs):
            emu.save_emulator(root, fake, "rvm")
            return fake

        with mock.patch.object(emu, "install_rvm", side_effect=install):
            code, _, _, asked = self.run_cli("emulator", "--download", interactive=False)
        self.assertEqual((code, asked), (0, []))
        self.assertEqual(emu.configured(self.sdk.root), fake)

    def test_download_flag_failure_exits_1(self):
        with mock.patch.object(emu, "install_rvm", side_effect=emu.SetupError("emu.no_rvm_platform", platform="x")):
            code, _, err, _ = self.run_cli("emulator", "--download", interactive=False)
        self.assertEqual(code, 1)
        self.assertIn("no Retro Virtual Machine for x", err)

    def test_with_an_emulator_saved_the_menu_never_offers_to_forget_it(self):
        kept = make_executable(self.home / "kept")
        emu.save_emulator(self.sdk.root, kept)
        _, out, _, _ = self.run_cli("emulator", answers=["4", "3"])
        self.assertNotIn("Do not ask again", out)
        self.assertIn("Leave it as it is", out)
        self.assertIn("No changes.", out)
        self.assertEqual(emu.configured(self.sdk.root), kept)
        self.assertFalse(emu.declined(self.sdk.root))

    def test_in_a_terminal_it_shows_the_current_emulator_and_lets_you_change_it(self):
        old = make_executable(self.home / "old")
        new = make_executable(self.home / "new")
        emu.save_emulator(self.sdk.root, old)
        _, out, _, _ = self.run_cli("emulator", answers=["1", str(new)])
        self.assertIn(f"Emulator: {old}", out)
        self.assertEqual(emu.configured(self.sdk.root), new)


if __name__ == "__main__":
    unittest.main()
