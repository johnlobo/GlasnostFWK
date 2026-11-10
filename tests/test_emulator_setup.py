"""`glasnost run` finds, offers, downloads and remembers a CPC emulator (tools/glasnost/emulator_setup.py).

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
sys.path[:0] = [str(ROOT / "tools" / d) for d in ("glasnost", "build", "dev")]
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
    def setUp(self):
        super().setUp()
        # Discovery fixtures must not include applications installed on the host Mac.
        patcher = mock.patch.object(emu, "MAC_APPS", ())
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_kind_of(self):
        self.assertEqual(emu.kind_of("/x/RetroVirtualMachine"), "rvm")
        self.assertEqual(emu.kind_of("C:/x/RetroVirtualMachine.exe"), "rvm")
        self.assertEqual(emu.kind_of("/Applications/BluePixel.app/Contents/MacOS/BluePixel"), "bluepixel")
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
        in_path = make_executable(self.tmp / "bin" / "bluepixel")
        downloaded = make_executable(self.root / "tools" / "emulators" / "retro-virtual-machine-x" / "RetroVirtualMachine")
        found = emu.candidates(self.root, home=self.tmp / "home", path_env=str(self.tmp / "bin"))
        self.assertEqual(found, [sibling, in_path, downloaded])

    def test_candidates_have_no_duplicates_and_skip_non_executables(self):
        make_executable(self.tmp / "bin" / "amspirit")
        (self.tmp / "bin" / "bluepixel").write_text("x")
        (self.tmp / "bin" / "bluepixel").chmod(0o644)
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


def release_json(assets, tag="v0.1.0") -> bytes:
    return json.dumps({"tag_name": tag, "assets": assets}).encode()


def asset_entry(name="BluePixel-0.1.0-macos-arm64.zip", size=10, sha="a" * 64, url="https://github.com/x/releases/download/v0.1.0/BluePixel-0.1.0-macos-arm64.zip"):
    return {"name": name, "size": size, "digest": f"sha256:{sha}", "browser_download_url": url}


class BluePixel(Temp):
    def bluepixel_zip(self) -> bytes:
        return zip_bytes({
            "BluePixel.app/Contents/MacOS/BluePixel": b"\xcf\xfa",
            "BluePixel.app/Contents/Resources/AppIcon.icns": b"i",
            "__MACOSX/BluePixel.app/Contents/MacOS/._BluePixel": b"junk",
        })

    def opener_for(self, data: bytes, assets=None):
        entry = asset_entry(size=len(data), sha=hashlib.sha256(data).hexdigest())

        def opener(url):
            if url == emu.BLUEPIXEL_API:
                return FakeResponse(release_json(assets if assets is not None else [entry]))
            if url == entry["browser_download_url"]:
                return FakeResponse(data)
            raise AssertionError(f"unexpected url {url}")

        return opener

    def test_the_latest_release_asset_for_apple_silicon_is_picked_with_its_digest(self):
        other = asset_entry(name="BluePixel-0.1.0-linux.tar.gz")
        info = emu.latest_bluepixel(lambda url: FakeResponse(release_json([other, asset_entry(sha="b" * 64)], "v0.2.0")))
        self.assertEqual((info["tag"], info["sha256"], info["name"]), ("v0.2.0", "b" * 64, "BluePixel-0.1.0-macos-arm64.zip"))

    def test_a_release_without_a_digest_is_refused(self):
        entry = asset_entry()
        del entry["digest"]
        with self.assertRaises(emu.SetupError) as raised:
            emu.latest_bluepixel(lambda url: FakeResponse(release_json([entry])))
        self.assertEqual(raised.exception.key, "emu.no_digest")

    def test_a_release_with_no_macos_zip_is_an_error(self):
        with self.assertRaises(emu.SetupError) as raised:
            emu.latest_bluepixel(lambda url: FakeResponse(release_json([asset_entry(name="notes.txt")])))
        self.assertEqual(raised.exception.key, "emu.no_bluepixel_asset")

    def test_api_failures_and_garbage_are_setup_errors(self):
        def offline(url):
            raise OSError("offline")

        for opener in (offline, lambda url: FakeResponse(b"<html>rate limited</html>")):
            with self.subTest(), self.assertRaises(emu.SetupError) as raised:
                emu.latest_bluepixel(opener)
            self.assertEqual(raised.exception.key, "emu.download_failed")

    def test_install_extracts_the_app_ignores_finder_junk_and_saves_it(self):
        data = self.bluepixel_zip()
        exe = emu.install_bluepixel(self.root, "Darwin", "arm64", opener=self.opener_for(data))
        self.assertEqual(exe.name, "BluePixel")
        self.assertIn("BluePixel.app/Contents/MacOS", str(exe))
        self.assertTrue(exe.stat().st_mode & stat.S_IXUSR)
        self.assertFalse(list(self.root.rglob("__MACOSX")))
        config = json.loads(emu.config_path(self.root).read_text())
        self.assertEqual((config["kind"], config["version"]), ("bluepixel", "v0.1.0"))
        self.assertEqual(emu.configured(self.root), exe)
        self.assertEqual(emu.kind_of(exe), "bluepixel")

    def test_a_tampered_zip_is_rejected(self):
        data = self.bluepixel_zip()
        entry = asset_entry(size=len(data), sha="0" * 64)

        def opener(url):
            return FakeResponse(release_json([entry]) if url == emu.BLUEPIXEL_API else data)

        with self.assertRaises(emu.SetupError) as raised:
            emu.install_bluepixel(self.root, "Darwin", "arm64", opener=opener)
        self.assertEqual(raised.exception.key, "emu.sha_mismatch")
        self.assertIsNone(emu.configured(self.root))
        self.assertFalse(list((self.root / "tools" / "emulators").rglob("BluePixel")))

    def test_a_second_install_does_not_download_the_zip_again(self):
        data = self.bluepixel_zip()
        first = emu.install_bluepixel(self.root, "Darwin", "arm64", opener=self.opener_for(data))
        entry_url = asset_entry()["browser_download_url"]
        api_only = self.opener_for(data)

        def opener(url):
            if url == entry_url:
                raise AssertionError("downloaded again")
            return api_only(url)

        self.assertEqual(emu.install_bluepixel(self.root, "Darwin", "arm64", opener=opener), first)

    def test_only_apple_silicon_macs_can_download_it(self):
        for system, machine in (("Linux", "x86_64"), ("Darwin", "x86_64"), ("Windows", "AMD64")):
            with self.subTest(system, machine=machine), self.assertRaises(emu.SetupError) as raised:
                emu.install_bluepixel(self.root, system, machine)
            self.assertEqual(raised.exception.key, "emu.no_bluepixel_platform")
        self.assertTrue(emu.bluepixel_supported("Darwin", "arm64"))

    def test_it_is_launched_with_autorun_and_symbols(self):
        exe = make_executable(self.root / "BluePixel.app" / "Contents" / "MacOS" / "BluePixel")
        noi = self.tmp / "build" / "a" / "obj" / "a.noi"
        noi.parent.mkdir(parents=True)
        noi.write_text("x")
        self.assertEqual(emu.build_command(str(exe), Path("/i/a.dsk"), self.tmp / "build" / "a", "a", self.root),
                         [str(exe), "/i/a.dsk", "/A", f"/SYM:{noi}"])
        self.assertEqual(emu.build_command(str(exe), Path("/i/a.cdt"), self.tmp / "build" / "zzz", "zzz", self.root),
                         [str(exe), "/i/a.cdt"])


class DefaultOpener(unittest.TestCase):
    """The real urlopen is patched: we check what would be sent, not the network."""

    def sent(self, url: str):
        with mock.patch.object(emu.urllib.request, "urlopen") as urlopen:
            emu.default_opener(url)
        return urlopen.call_args.args[0]

    def test_the_github_api_gets_its_accept_header_and_a_user_agent(self):
        request = self.sent(emu.BLUEPIXEL_API)
        self.assertEqual(request.get_header("Accept"), "application/vnd.github+json")
        self.assertTrue(request.get_header("User-agent"))

    def test_downloads_send_no_accept_header(self):
        request = self.sent("https://static.retrovm.org/release/x.zip")
        self.assertIsNone(request.get_header("Accept"))
        self.assertTrue(request.get_header("User-agent"))


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
    def rvm(self, image: str, name: str = "nave") -> list[str]:
        exe = make_executable(self.root / "RetroVirtualMachine")
        emu.save_emulator(self.root, exe, "rvm")
        return emu.build_command(str(exe), Path(image), self.tmp, name, self.root)[1:]

    def test_rvm_gets_a_dsk_the_way_cpct_rvm_launches_it(self):
        # tools/scripts/cpct_rvm: RVM -ns -b=<machine> -i= FILE -c=RUN"NAME"\n  (backslash-n is literal)
        self.assertEqual(self.rvm("/i/nave.dsk"),
                         ["-ns", "-b=cpc6128", "-i=", "/i/nave.dsk", '-c=RUN"nave"\\n'])

    def test_rvm_gets_a_cdt_with_autoplay_and_warp(self):
        self.assertEqual(self.rvm("/i/nave.cdt"),
                         ["-ns", "-b=cpc464", "-i=", "/i/nave.cdt", "-p", "-w", '-c=RUN"\\n \\n'])

    def test_rvm_gets_a_snapshot_with_no_command(self):
        self.assertEqual(self.rvm("/i/nave.sna"), ["-ns", "-b=cpc464", "-s", "/i/nave.sna"])

    def test_the_run_command_uses_the_first_eight_characters_of_the_name(self):
        self.assertEqual(self.rvm("/i/platformer.dsk", "platformer")[-1], '-c=RUN"platform"\\n')

    def test_rvm_is_not_given_a_symbols_file_because_none_is_known(self):
        noi = self.tmp / "nave" / "obj" / "nave.noi"
        noi.parent.mkdir(parents=True)
        noi.write_text("x")
        self.assertFalse([a for a in self.rvm("/i/nave.dsk") if "noi" in a.lower() or "sym" in a.lower()])

    def test_arguments_can_be_overridden_in_the_config(self):
        exe = make_executable(self.root / "RetroVirtualMachine")
        emu.save_emulator(self.root, exe, "rvm", args=["--b=cpc6128", "--i={image}", "--run={name}"])
        self.assertEqual(emu.build_command(str(exe), Path("/i/a.dsk"), self.tmp, "platformer", self.root),
                         [str(exe), "--b=cpc6128", "--i=/i/a.dsk", "--run=platform"])

    def test_any_other_emulator_gets_just_the_image(self):
        self.assertEqual(emu.build_command("/x/amspirit", Path("/i/a.cdt"), self.tmp, "a", self.root),
                         ["/x/amspirit", "/i/a.cdt"])

    def test_symbols_are_passed_to_every_emulator_that_has_an_option_for_them(self):
        noi = self.tmp / "build" / "a" / "obj" / "a.noi"
        noi.parent.mkdir(parents=True)
        noi.write_text("x")
        for name in ("BluePixel",):
            for image, autorun in (("a.dsk", True), ("a.cdt", False)):
                with self.subTest(name, image=image):
                    exe = make_executable(self.tmp / name)
                    command = emu.build_command(str(exe), Path("/i/" + image), self.tmp / "build" / "a", "a", self.root)
                    self.assertIn(f"/SYM:{noi}", command)
                    self.assertEqual("/A" in command, autorun)

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
        patcher = mock.patch.object(run_example, "BLUEPIXEL_CANDIDATES", ())
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
        # Generic menu scripts use Linux numbering; Apple-specific tests opt in explicitly.
        for patcher in (mock.patch.object(emu, "bluepixel_supported", return_value=False),
                        mock.patch.object(emu, "MAC_APPS", ())):
            patcher.start()
            self.addCleanup(patcher.stop)
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



class RunExampleFindsTheBuild(Temp):
    """`glasnost run` opened nothing in a project: it looked for build/<name>/<name>.dsk, but a
    glasnost project builds straight into build/ (commit acef7d5)."""

    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(run_example, "ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)

    def project(self, name="platform2") -> Path:
        folder = self.tmp / name
        (folder / "build" / "obj").mkdir(parents=True)
        (folder / "example.json").write_text(json.dumps({"name": name}), encoding="utf-8")
        return folder

    def test_a_project_image_is_found_in_build_directly(self):
        folder = self.project()
        for suffix in ("cdt", "dsk"):
            (folder / "build" / f"platform2.{suffix}").write_text("x")
        self.assertEqual(run_example.select_image("platform2", None, folder / "build", project=True),
                         folder / "build" / "platform2.cdt")
        self.assertEqual(run_example.select_image("platform2", "dsk", folder / "build", project=True),
                         folder / "build" / "platform2.dsk")

    def test_an_sdk_example_image_is_still_found_under_build_name(self):
        (self.root / "build" / "minimal").mkdir(parents=True)
        (self.root / "build" / "minimal" / "minimal.dsk").write_text("x")
        self.assertEqual(run_example.select_image("minimal", None), self.root / "build" / "minimal" / "minimal.dsk")

    def test_a_missing_image_tells_a_project_to_run_glasnost_build(self):
        folder = self.project()
        with self.assertRaises(SystemExit) as raised:
            run_example.select_image("platform2", None, folder / "build", project=True)
        self.assertIn("glasnost build", str(raised.exception))
        self.assertNotIn("examples/", str(raised.exception))
        with self.assertRaises(SystemExit) as raised:
            run_example.select_image("minimal", None)
        self.assertIn("examples/minimal", str(raised.exception))

    def test_running_a_project_launches_the_emulator_with_its_image_and_symbols(self):
        folder = self.project()
        (folder / "build" / "platform2.dsk").write_text("x")
        noi = folder / "build" / "obj" / "platform2.noi"
        noi.write_text("x")
        emulator = make_executable(self.tmp / "BluePixel")
        launched = []
        with mock.patch.object(sys, "argv", ["run_example.py", "--project", str(folder), "--emulator", str(emulator)]), \
                mock.patch.object(run_example.subprocess, "run", side_effect=lambda cmd: launched.append(cmd) or mock.Mock(returncode=0)), \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(run_example.main(), 0)
        self.assertEqual(launched, [[str(emulator), str(folder / "build" / "platform2.dsk"), "/A", f"/SYM:{noi}"]])


class RunExampleChoosesTheImage(Temp):
    """BluePixel got the CDT (the default) with no /A: the emulator opened and loaded nothing useful."""

    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(run_example, "ROOT", self.root)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.folder = self.tmp / "game"
        (self.folder / "build" / "obj").mkdir(parents=True)
        (self.folder / "example.json").write_text('{"name": "game"}', encoding="utf-8")
        for suffix in ("cdt", "dsk"):
            (self.folder / "build" / f"game.{suffix}").write_text("x")
        (self.folder / "build" / "obj" / "game.noi").write_text("x")

    def launch(self, emulator_name: str, *extra: str) -> tuple[list[str], str]:
        emulator = make_executable(self.tmp / "bin" / emulator_name)
        launched: list[list[str]] = []
        out = io.StringIO()
        argv = ["run_example.py", "--project", str(self.folder), "--emulator", str(emulator), *extra]
        with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(out), \
                mock.patch.object(run_example.subprocess, "run", side_effect=lambda cmd: launched.append(cmd) or mock.Mock(returncode=0)):
            self.assertEqual(run_example.main(), 0)
        return launched[0], out.getvalue()

    def test_bluepixel_gets_the_dsk_with_autorun_and_symbols(self):
        for name in ("BluePixel",):
            with self.subTest(name):
                command, _ = self.launch(name)
                self.assertEqual(command[1:], [str(self.folder / "build" / "game.dsk"), "/A",
                                               f"/SYM:{self.folder / 'build' / 'obj' / 'game.noi'}"])

    def test_rvm_gets_the_dsk_and_runs_it(self):
        command, _ = self.launch("RetroVirtualMachine")
        self.assertIn(str(self.folder / "build" / "game.dsk"), command)
        self.assertIn('-c=RUN"game"\\n', command)

    def test_an_unknown_emulator_keeps_the_cdt_default(self):
        command, _ = self.launch("amspirit")
        self.assertEqual(command[1:], [str(self.folder / "build" / "game.cdt")])

    def test_an_explicit_image_format_always_wins(self):
        command, _ = self.launch("BluePixel", "--image", "cdt")
        self.assertEqual(command[1], str(self.folder / "build" / "game.cdt"))
        self.assertNotIn("/A", command)

    def test_the_full_command_line_is_printed(self):
        command, out = self.launch("BluePixel")
        self.assertIn("/A", out)
        self.assertIn("game.dsk", out)
        self.assertIn("/SYM:", out)

    def test_a_saved_kind_decides_even_if_the_file_name_does_not_say_it(self):
        exe = make_executable(self.tmp / "bin" / "emu")
        emu.save_emulator(self.root, exe, "bluepixel")
        self.assertEqual(emu.preferred_image(str(exe), self.root), "dsk")
        self.assertIsNone(emu.preferred_image(str(exe), self.tmp))   # another SDK knows nothing about it
        self.assertIsNone(emu.preferred_image(None, self.root))


class RunAsksOnce(Harness):
    """`glasnost run` in a terminal with no emulator: ask, remember, never ask again."""

    def test_not_now_runs_without_an_emulator_and_asks_again_next_time(self):
        code, out, _, asked = self.run_cli("run", "minimal", answers=["3"])
        self.assertEqual(code, 0)
        self.assertIn("No emulator is configured", out)
        self.assertIn("Retro Virtual Machine", out)
        self.assertEqual(len(asked), 1)
        self.assertEqual(self.calls[-1][1:], ["tools/glasnost/run_example.py", "minimal"])
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
        self.assertEqual(self.calls[-1][1:], ["tools/glasnost/run_example.py", "minimal"])

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
        self.assertIn("cpct_rvm", out)   # RVM is launched like CPCtelera does; the note says it is unverified
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
        self.assertEqual(self.calls[-1][1:], ["tools/glasnost/run_example.py", "minimal"])

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
        self.assertEqual(self.calls[-1][1:], ["tools/glasnost/run_example.py", "minimal"])

    def test_nothing_is_asked_when_the_user_already_chose_one(self):
        self.run_cli("run", "minimal", "--", "--emulator", "x")
        _, _, _, asked = self.run_cli("run", "minimal", "--", "--emulator=x")
        self.assertEqual(asked, [])
        _, _, _, asked = self.run_cli("run", "minimal", env={"GLASNOST_EMULATOR": "/some/emu"})
        self.assertEqual(asked, [])

    def test_closing_the_input_does_not_crash_and_the_run_proceeds(self):
        code, _, _, _ = self.run_cli("run", "minimal", answers=[])
        self.assertEqual(code, 0)
        self.assertEqual(self.calls[-1][1:], ["tools/glasnost/run_example.py", "minimal"])

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


class RunOffersBluePixelOnApple(Harness):
    def test_the_menu_adds_bluepixel_before_skip_and_renumbers(self):
        with mock.patch.object(emu, "bluepixel_supported", return_value=True):
            _, out, _, asked = self.run_cli("run", "minimal", answers=["4"])
        self.assertIn("  3) Download the latest BluePixel (johnlobo/BluePixel on GitHub, Apple Silicon)", out)
        self.assertIn("  4) Not now", out)
        self.assertIn("  5) Do not ask again", out)
        self.assertIn("(default 4)", asked[0])

    def test_choosing_it_installs_and_saves_it(self):
        fake = make_executable(self.sdk.root / "tools" / "emulators" / "b" / "BluePixel.app" / "Contents" / "MacOS" / "BluePixel")

        def install(root, **kwargs):
            emu.save_emulator(root, fake, "bluepixel")
            return fake

        with mock.patch.object(emu, "bluepixel_supported", return_value=True), \
                mock.patch.object(emu, "install_bluepixel", side_effect=install) as installer:
            code, out, _, _ = self.run_cli("run", "minimal", answers=["3"])
        self.assertEqual(code, 0)
        installer.assert_called_once()
        self.assertEqual(emu.configured(self.sdk.root), fake)
        self.assertNotIn("cpct_rvm", out)   # only RVM carries that note

    def test_other_platforms_do_not_see_it(self):
        with mock.patch.object(emu, "bluepixel_supported", return_value=False):
            _, out, _, _ = self.run_cli("run", "minimal", answers=["3"])
        self.assertNotIn("BluePixel", out)
        self.assertIn("  3) Not now", out)

    def test_the_command_downloads_either_one(self):
        fake = make_executable(self.sdk.root / "tools" / "emulators" / "b" / "BluePixel")
        for which, target in (("bluepixel", "install_bluepixel"), ("rvm", "install_rvm")):
            with self.subTest(which), mock.patch.object(emu, target, return_value=fake) as installer:
                code, _, _, _ = self.run_cli("emulator", "--download", which, interactive=False)
            self.assertEqual(code, 0)
            installer.assert_called_once()

    def test_a_bare_download_flag_means_rvm_and_unknown_names_are_rejected(self):
        fake = make_executable(self.sdk.root / "tools" / "emulators" / "b" / "RetroVirtualMachine")
        with mock.patch.object(emu, "install_rvm", return_value=fake) as installer:
            self.run_cli("emulator", "--download", interactive=False)
        installer.assert_called_once()
        with self.assertRaises(SystemExit) as raised:
            self.run_cli("emulator", "--download", "winape", interactive=False)
        self.assertEqual(raised.exception.code, 2)


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
