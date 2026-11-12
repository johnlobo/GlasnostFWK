"""Gate tests of the offline bundle (`export-bundle`, `install-toolchain --bundle`).

Deterministic, local, no network: the "upstream" is a throwaway Git repository, and the
offline machine is a second SDK whose upstream URL points at a path that does not exist,
so any attempt to download would fail the test.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "tools" / d) for d in ("glasnost", "build", "dev")]
sys.path.insert(0, str(ROOT / "tests"))

import glasnost  # noqa: E402
import glasnost_bundle as gb  # noqa: E402
from test_glasnost import FakeSdk, git  # noqa: E402

NO_NETWORK = "file:///nonexistent/glasnost-no-network"


def rev_list_count(folder: Path) -> int:
    return int(subprocess.run(["git", "-C", str(folder), "rev-list", "--count", "HEAD"],
                              check=True, capture_output=True, text=True).stdout)


def commit_objects(folder: Path) -> int:
    """Commit objects really stored in the repository, whatever the shallow marker hides."""
    kinds = subprocess.run(["git", "-C", str(folder), "cat-file", "--batch-all-objects", "--batch-check=%(objecttype)"],
                           check=True, capture_output=True, text=True).stdout.split()
    return kinds.count("commit")


def make_history(sdk: FakeSdk) -> None:
    """Give the fake upstream a second commit and pin the lockfile to it, so history exists to be left out."""
    (sdk.upstream / "cpctelera" / "NEWS").write_text("second\n", encoding="utf-8")
    git("add", "-A", cwd=sdk.upstream)
    git("commit", "-q", "-m", "second", cwd=sdk.upstream)
    sdk.rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=sdk.upstream, check=True,
                             capture_output=True, text=True).stdout.strip()
    sdk.write_lock(sdk.rev)
    sdk.checkout = sdk.tmp / "tc" / "cpctelera-next" / sdk.rev


class BundleCase(unittest.TestCase):
    def installed_sdk(self) -> FakeSdk:
        sdk = FakeSdk(self)
        make_history(sdk)
        code, out, err = sdk.cli("install-toolchain")
        self.assertEqual((code, err), (0, ""), out)
        return sdk

    def offline_sdk(self, like: FakeSdk) -> FakeSdk:
        """Another machine: same lockfile commit, empty toolchain dir, no reachable upstream."""
        sdk = FakeSdk(self)
        sdk.rev = like.rev
        sdk.write_lock(like.rev)
        sdk.env["GLASNOST_CPCTELERA_URL"] = NO_NETWORK
        sdk.checkout = sdk.tmp / "tc" / "cpctelera-next" / like.rev
        return sdk

    def export(self, sdk: FakeSdk, out: Path | None = None) -> Path:
        out = out or sdk.tmp / "out"
        code, text, err = sdk.cli("export-bundle", "--output", str(out))
        self.assertEqual((code, err), (0, ""), text)
        return out / gb.bundle_name(sdk.rev)

    def tar_with(self, members: dict[str, bytes], kind=tarfile.REGTYPE) -> Path:
        path = Path(tempfile.mkdtemp(prefix="glasnost-bundle-")) / "x.tar"
        self.addCleanup(subprocess.run, ["rm", "-rf", str(path.parent)])
        with tarfile.open(path, "w") as archive:
            for name, data in members.items():
                info = tarfile.TarInfo(name)
                info.size, info.type = len(data), kind
                archive.addfile(info, io.BytesIO(data))
        return path

    def rewrite(self, bundle: Path, change) -> Path:
        """Copy of `bundle` with members passed through `change(name, bytes) -> bytes`."""
        members = {}
        with tarfile.open(bundle) as archive:
            for member in archive.getmembers():
                members[member.name] = change(member.name, archive.extractfile(member).read())
        return self.tar_with(members)


class Export(BundleCase):
    def test_export_from_an_installed_toolchain_writes_tar_and_checksum(self):
        sdk = self.installed_sdk()
        bundle = self.export(sdk)
        self.assertTrue(bundle.is_file())
        side = bundle.with_name(bundle.name + ".sha256").read_text(encoding="ascii")
        self.assertEqual(side, f"{gb.sha256_file(bundle)}  {bundle.name}\n")
        with tarfile.open(bundle) as archive:
            self.assertEqual(archive.getnames(), [gb.MANIFEST_NAME, gb.PACK_NAME])  # fixed order
        manifest = gb.open_bundle(bundle, sdk.rev)
        self.assertEqual(manifest.rev, sdk.rev)

    def test_the_installed_checkout_is_shallow_and_still_exports_a_usable_bundle(self):
        """Regression: `git bundle create` on a --depth=1 clone succeeds silently and the file cannot be imported."""
        sdk = self.installed_sdk()
        shallow = subprocess.run(["git", "-C", str(sdk.checkout), "rev-parse", "--is-shallow-repository"],
                                 capture_output=True, text=True).stdout.strip()
        self.assertEqual(shallow, "true")
        other = self.offline_sdk(sdk)
        code, out, err = other.cli("install-toolchain", "--bundle", str(self.export(sdk)))
        self.assertEqual((code, err), (0, ""), out)

    def test_export_without_an_installed_toolchain_fetches_into_a_temporary_folder_and_cleans_it(self):
        sdk = FakeSdk(self)
        make_history(sdk)
        bundle = self.export(sdk)
        self.assertTrue(bundle.is_file())
        self.assertFalse((sdk.tmp / "tc").exists(), "the temporary checkout and the folders made for it must be gone")
        self.assertFalse(list((sdk.tmp / "out").glob(".*part")))

    def test_the_bundle_has_the_commit_and_its_tree_but_no_history(self):
        sdk = self.installed_sdk()
        other = self.offline_sdk(sdk)
        other.cli("install-toolchain", "--bundle", str(self.export(sdk)))
        self.assertEqual(rev_list_count(other.checkout), 1)
        self.assertEqual(commit_objects(other.checkout), 1)   # shallow marker hides extra commits from rev-list
        self.assertEqual((other.checkout / "cpctelera" / "NEWS").read_text(encoding="utf-8"), "second\n")

    def test_same_pack_gives_the_same_tar_bytes(self):
        sdk = self.installed_sdk()
        pack = sdk.tmp / "p.pack"
        gb.build_pack(sdk.upstream, sdk.rev, pack)
        a, b = sdk.tmp / "a.tar", sdk.tmp / "b.tar"
        sha_a = gb.write_bundle(a, "https://example.invalid/c.git", sdk.rev, pack, "t")
        sha_b = gb.write_bundle(b, "https://example.invalid/c.git", sdk.rev, pack, "t")
        self.assertEqual(sha_a, sha_b)
        self.assertEqual(a.read_bytes(), b.read_bytes())
        with tarfile.open(a) as archive:
            for member in archive.getmembers():
                self.assertEqual((member.mtime, member.uid, member.gid, member.uname, member.gname), (0, 0, 0, "", ""))

    def test_a_full_clone_as_source_also_leaves_history_out(self):
        sdk = FakeSdk(self)
        make_history(sdk)
        pack = sdk.tmp / "full.pack"
        gb.build_pack(sdk.upstream, sdk.rev, pack)   # the upstream has two commits
        target = sdk.tmp / "imported"
        gb.import_pack(target, pack, sdk.rev)
        self.assertEqual(rev_list_count(target), 1)
        self.assertEqual(commit_objects(target), 1)

    def test_a_missing_commit_is_reported_in_the_users_language(self):
        sdk = FakeSdk(self)
        sdk.write_lock("0" * 40)
        sdk.env["GLASNOST_CPCTELERA_URL"] = NO_NETWORK
        code, _, err = sdk.cli("export-bundle", "--output", str(sdk.tmp / "out"))
        self.assertNotEqual(code, 0)
        self.assertTrue(err.strip())


class OfflineInstall(BundleCase):
    def test_install_from_a_bundle_builds_verifies_and_marks_complete_without_network(self):
        sdk = self.installed_sdk()
        other = self.offline_sdk(sdk)
        code, out, err = other.cli("install-toolchain", "--bundle", str(self.export(sdk)))
        self.assertEqual((code, err), (0, ""), out)
        self.assertIn("is valid", out)
        self.assertTrue((other.checkout / glasnost.COMPLETE_MARKER).is_file())
        self.assertEqual(glasnost.missing_files(other.checkout / "cpctelera"), [])
        head = subprocess.run(["git", "-C", str(other.checkout), "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout.strip()
        self.assertEqual(head, sdk.rev)
        origin = subprocess.run(["git", "-C", str(other.checkout), "remote", "get-url", "origin"],
                                capture_output=True, text=True).stdout.strip()
        self.assertEqual(origin, NO_NETWORK, "same remote a downloaded install has")
        self.assertEqual(subprocess.run(["git", "-C", str(other.checkout), "fsck"],
                                        capture_output=True, text=True).returncode, 0)

    def test_without_the_bundle_the_same_offline_sdk_cannot_install(self):
        """Proves the fake offline setup: only the bundle makes the install possible."""
        other = self.offline_sdk(self.installed_sdk())
        code, _, _ = other.cli("install-toolchain")
        self.assertNotEqual(code, 0)

    def test_the_resulting_toolchain_is_the_one_a_normal_install_resolves(self):
        sdk = self.installed_sdk()
        other = self.offline_sdk(sdk)
        other.cli("install-toolchain", "--bundle", str(self.export(sdk)))
        env = {"GLASNOST_TOOLCHAIN_DIR": str(other.tmp / "tc")}
        with mock.patch.dict(os.environ, env):
            os.environ.pop("CPCT_NEXT_PATH", None)
            found = glasnost.resolve_toolchain(other.root, glasnost.load_lock(other.root, "en"), "en")
        self.assertEqual((found.source, found.rev), ("managed", sdk.rev))

    def test_dry_run_verifies_the_bundle_lists_the_import_step_and_changes_nothing(self):
        sdk = self.installed_sdk()
        other = self.offline_sdk(sdk)
        code, out, _ = other.cli("install-toolchain", "--bundle", str(self.export(sdk)), "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("import the bundle", out)
        self.assertNotIn("fetch ", out)
        self.assertIn("Dry run", out)
        self.assertFalse((other.tmp / "tc").exists())

    def test_dry_run_with_a_bad_bundle_fails(self):
        sdk = self.installed_sdk()
        other = self.offline_sdk(sdk)
        code, _, err = other.cli("install-toolchain", "--bundle", str(other.tmp / "missing.tar"), "--dry-run")
        self.assertNotEqual(code, 0)
        self.assertIn("Cannot read the bundle", err)

    def test_a_second_install_is_a_noop_and_force_redoes_it_from_the_bundle(self):
        sdk = self.installed_sdk()
        other = self.offline_sdk(sdk)
        bundle = str(self.export(sdk))
        other.cli("install-toolchain", "--bundle", bundle)
        _, out, _ = other.cli("install-toolchain", "--bundle", bundle)
        self.assertIn("nothing to do", out)
        code, out, err = other.cli("install-toolchain", "--bundle", bundle, "--force")
        self.assertEqual((code, err), (0, ""), out)
        self.assertIn("installed at", out)

    def test_no_temporary_pack_is_left_behind(self):
        sdk = self.installed_sdk()
        other = self.offline_sdk(sdk)
        other.cli("install-toolchain", "--bundle", str(self.export(sdk)))
        names = sorted(p.name for p in (other.tmp / "tc" / "cpctelera-next").iterdir())
        self.assertFalse([n for n in names if n.endswith(".part")], names)


class Rejection(BundleCase):
    """A bundle that is wrong must fail before the toolchain folder is touched."""

    def assert_rejected(self, sdk: FakeSdk, bundle: Path, message: str):
        code, _, err = sdk.cli("install-toolchain", "--bundle", str(bundle))
        self.assertNotEqual(code, 0)
        self.assertIn(message, err)
        self.assertFalse((sdk.tmp / "tc").exists(), "nothing may be created for a rejected bundle")

    def setUp(self):
        self.source = self.installed_sdk()
        self.bundle = self.export(self.source)
        self.other = self.offline_sdk(self.source)

    def test_bundle_of_another_commit(self):
        self.other.write_lock("1" * 40)
        self.assert_rejected(self.other, self.bundle, "the lockfile pins")

    def test_a_flipped_byte_in_the_pack(self):
        def flip(name, data):
            return data[:-1] + bytes([data[-1] ^ 0xFF]) if name == gb.PACK_NAME else data
        self.assert_rejected(self.other, self.rewrite(self.bundle, flip), "damaged or incomplete")

    def test_a_truncated_pack(self):
        self.assert_rejected(self.other, self.rewrite(
            self.bundle, lambda n, d: d[:-10] if n == gb.PACK_NAME else d), "damaged or incomplete")

    def test_a_truncated_tar(self):
        broken = self.tar_with({"x": b"y"})
        broken.write_bytes(self.bundle.read_bytes()[:2000])
        code, _, err = self.other.cli("install-toolchain", "--bundle", str(broken))
        self.assertNotEqual(code, 0)
        self.assertTrue(err.strip())
        self.assertFalse((self.other.tmp / "tc").exists())

    def test_not_a_tar_at_all(self):
        junk = self.tar_with({"x": b"y"})
        junk.write_bytes(b"this is not an archive" * 100)
        self.assert_rejected(self.other, junk, "Cannot read the bundle")

    def test_a_missing_file(self):
        self.assert_rejected(self.other, self.other.tmp / "nope.tar", "Cannot read the bundle")

    def test_extra_members_and_path_traversal_names_are_refused_not_extracted(self):
        evil = self.rewrite(self.bundle, lambda n, d: d)
        with tarfile.open(evil, "a") as archive:
            info = tarfile.TarInfo("../escaped.txt")
            info.size = 1
            archive.addfile(info, io.BytesIO(b"x"))
        self.assert_rejected(self.other, evil, "does not have the expected content")
        self.assertFalse((self.other.tmp / "escaped.txt").exists())
        self.assertFalse((self.other.tmp.parent / "escaped.txt").exists())

    def test_a_symlink_member_is_refused(self):
        path = self.tar_with({gb.MANIFEST_NAME: b"{}"})
        with tarfile.open(path, "a") as archive:
            link = tarfile.TarInfo(gb.PACK_NAME)
            link.type, link.linkname = tarfile.SYMTYPE, "/etc/passwd"
            archive.addfile(link)
        self.assert_rejected(self.other, path, "is not a plain file")

    def test_a_manifest_that_is_not_json(self):
        bad = self.rewrite(self.bundle, lambda n, d: b"{nope" if n == gb.MANIFEST_NAME else d)
        self.assert_rejected(self.other, bad, "manifest is not valid")

    def test_a_manifest_with_the_wrong_schema_or_types(self):
        for change in ({"schema": 2}, {"kind": "other"}, {"pack": {"name": gb.PACK_NAME, "size": "x", "sha256": "0" * 64}},
                       {"cpctelera_next": {"url": "u", "rev": "zz"}}):
            def edit(name, data, change=change):
                if name != gb.MANIFEST_NAME:
                    return data
                body = json.loads(data)
                body.update(change)
                return json.dumps(body).encode()
            with self.subTest(change=change):
                self.assert_rejected(self.other, self.rewrite(self.bundle, edit), "manifest is not valid")

    def test_a_manifest_that_declares_a_different_size(self):
        def edit(name, data):
            if name != gb.MANIFEST_NAME:
                return data
            body = json.loads(data)
            body["pack"]["size"] += 1
            return json.dumps(body).encode()
        self.assert_rejected(self.other, self.rewrite(self.bundle, edit), "damaged or incomplete")

    def forged_bundle(self) -> Path:
        """Manifest and SHA-256 are consistent and claim the pinned commit, but the pack holds another one."""
        other_commit = FakeSdk(self)
        pack = other_commit.tmp / "other.pack"
        gb.build_pack(other_commit.upstream, other_commit.rev, pack)
        forged = other_commit.tmp / "forged.tar"
        gb.write_bundle(forged, "https://example.invalid/c.git", self.source.rev, pack, "t")
        return forged

    def commit_only_bundle(self) -> Path:
        """Pack with the pinned commit object alone: every check but the tree check passes."""
        pack = self.source.tmp / "commit-only.pack"
        with pack.open("wb") as handle:
            subprocess.run(["git", "-C", str(self.source.upstream), "pack-objects", "--stdout", "-q"],
                           input=(self.source.rev + "\n").encode(), stdout=handle, check=True)
        path = self.source.tmp / "commit-only.tar"
        gb.write_bundle(path, "https://example.invalid/c.git", self.source.rev, pack, "t")
        return path

    def test_a_pack_that_matches_its_manifest_but_lacks_the_lockfile_commit(self):
        """The SHA-256 lives inside the file, so the commit check is what really anchors trust."""
        self.assert_rejected(self.other, self.forged_bundle(), "does not contain the lockfile commit")

    def test_a_pack_with_the_commit_but_not_its_tree_is_rejected_before_anything_is_created(self):
        self.assert_rejected(self.other, self.commit_only_bundle(), "does not contain the lockfile commit")

    def test_a_rejected_bundle_with_force_leaves_a_working_install_untouched(self):
        good = str(self.bundle)
        self.other.cli("install-toolchain", "--bundle", good)
        marker = self.other.checkout / glasnost.COMPLETE_MARKER
        before = sorted(p.name for p in (self.other.checkout / "cpctelera").iterdir())
        for bad in (self.forged_bundle(), self.commit_only_bundle()):
            with self.subTest(bad=bad.name):
                code, _, _ = self.other.cli("install-toolchain", "--bundle", str(bad), "--force")
                self.assertNotEqual(code, 0)
                self.assertTrue(marker.is_file(), "the working install lost its completion marker")
                self.assertEqual(sorted(p.name for p in (self.other.checkout / "cpctelera").iterdir()), before)
                self.assertEqual(glasnost.missing_files(self.other.checkout / "cpctelera"), [])

    def test_a_failure_while_importing_removes_the_checkout_it_created(self):
        lock = glasnost.load_lock(self.other.root, "en")
        checkout = self.other.checkout
        def half_done(folder, *args):
            (folder / ".git").mkdir(parents=True)       # a partial import: the folder exists, then it fails
            raise gb.BundleError("bundle.git_failed", command="x", detail="boom")
        with mock.patch.object(gb, "import_pack", side_effect=half_done):
            with self.assertRaises(glasnost.CliError):
                glasnost.import_bundle(self.bundle, lock, checkout, "en")
        self.assertFalse(checkout.exists())
        self.assertEqual([p.name for p in checkout.parent.iterdir() if p.name.endswith(".part") or ".import-" in p.name], [])

    def test_a_deeply_nested_manifest_is_a_translated_error_not_a_traceback(self):
        def deep(name, data):
            return (b"[" * 20000 + b"]" * 20000) if name == gb.MANIFEST_NAME else data
        code, _, err = self.other.cli("install-toolchain", "--bundle", str(self.rewrite(self.bundle, deep)), "--dry-run")
        self.assertNotEqual(code, 0)
        self.assertIn("manifest is not valid", err)
        self.assertNotIn("Traceback", err)

    def test_oversized_manifest(self):
        def pad(name, data):
            if name != gb.MANIFEST_NAME:
                return data
            body = json.loads(data)
            body["padding"] = "x" * (gb.MAX_MANIFEST + 10)
            return json.dumps(body).encode()
        self.assert_rejected(self.other, self.rewrite(self.bundle, pad), "manifest is not valid")

    def test_a_boolean_is_not_a_size(self):
        def edit(name, data):
            if name != gb.MANIFEST_NAME:
                return data
            body = json.loads(data)
            body["pack"]["size"] = True
            return json.dumps(body).encode()
        self.assert_rejected(self.other, self.rewrite(self.bundle, edit), "manifest is not valid")

    def test_hardlink_device_duplicate_and_dash_members_are_refused(self):
        def archive(*members):
            path = Path(tempfile.mkdtemp(prefix="glasnost-bundle-")) / "x.tar"
            self.addCleanup(subprocess.run, ["rm", "-rf", str(path.parent)])
            with tarfile.open(path, "w") as tar:
                for name, kind, data in members:
                    info = tarfile.TarInfo(name)
                    info.type, info.size = kind, len(data)
                    if kind == tarfile.LNKTYPE:
                        info.linkname = "/etc/passwd"
                    tar.addfile(info, io.BytesIO(data))
            return path
        manifest = (gb.MANIFEST_NAME, tarfile.REGTYPE, b"{}")
        cases = {
            "hardlink": (archive(manifest, (gb.PACK_NAME, tarfile.LNKTYPE, b"")), "is not a plain file"),
            "device": (archive(manifest, (gb.PACK_NAME, tarfile.CHRTYPE, b"")), "is not a plain file"),
            "duplicate": (archive(manifest, manifest, (gb.PACK_NAME, tarfile.REGTYPE, b"x")), "does not have the expected content"),
            "dash": (archive(manifest, ("-x", tarfile.REGTYPE, b"x")), "does not have the expected content"),
        }
        for label, (path, message) in cases.items():
            with self.subTest(label):
                self.assert_rejected(self.other, path, message)

    def bad_tree_pack(self) -> tuple[Path, str]:
        """Pack whose objects hash correctly but whose tree is unsorted (a structural error only fsck sees)."""
        repo = self.source.tmp / "bad"
        repo.mkdir()
        run = lambda *a, **k: subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True, **k)
        run("init", "-q")
        blob = run("hash-object", "-w", "--stdin", input=b"x").stdout.decode().strip()
        raw = bytes.fromhex(blob)
        tree = run("hash-object", "-t", "tree", "-w", "--literally", "--stdin",
                   input=b"100644 b\0" + raw + b"100644 a\0" + raw).stdout.decode().strip()
        commit = run("hash-object", "-t", "commit", "-w", "--literally", "--stdin",
                     input=f"tree {tree}\nauthor a <a> 0 +0000\ncommitter a <a> 0 +0000\n\nm\n".encode()).stdout.decode().strip()
        pack = self.source.tmp / "bad.pack"
        with pack.open("wb") as handle:
            subprocess.run(["git", "-C", str(repo), "pack-objects", "--stdout", "-q"], stdout=handle, check=True,
                           input=f"{commit}\n{tree}\n{blob}\n".encode())
        return pack, commit

    def test_a_structurally_bad_object_is_rejected_by_fsck_even_though_its_hash_is_right(self):
        """index-pack always checks hashes; --fsck-objects is what refuses an unsorted tree."""
        pack, commit = self.bad_tree_pack()
        bundle = self.source.tmp / "bad.tar"
        gb.write_bundle(bundle, "https://example.invalid/c.git", commit, pack, "t")
        self.other.write_lock(commit)
        self.assert_rejected(self.other, bundle, "failed")

    def test_the_import_step_has_its_own_fsck_not_only_the_verification(self):
        pack, commit = self.bad_tree_pack()
        with self.assertRaises(gb.BundleError):
            gb.import_pack(self.other.tmp / "direct", pack, commit)

    def test_a_manifest_that_names_another_pack_file_is_refused(self):
        def edit(name, data):
            if name != gb.MANIFEST_NAME:
                return data
            body = json.loads(data)
            body["pack"]["name"] = "other.pack"
            return json.dumps(body).encode()
        self.assert_rejected(self.other, self.rewrite(self.bundle, edit), "manifest is not valid")

    def test_force_with_a_good_bundle_that_fails_midway_keeps_the_working_install(self):
        """The old install is swapped only after the new one is complete."""
        self.other.cli("install-toolchain", "--bundle", str(self.bundle))
        marker = self.other.checkout / glasnost.COMPLETE_MARKER
        before = sorted(p.name for p in (self.other.checkout / "cpctelera").iterdir())

        def half_done(folder, *args):
            (folder / "junk").mkdir(parents=True)
            raise gb.BundleError("bundle.git_failed", command="x", detail="disk full")
        with mock.patch.object(gb, "import_pack", side_effect=half_done):
            code, _, err = self.other.cli("install-toolchain", "--bundle", str(self.bundle), "--force")
        self.assertNotEqual(code, 0)
        self.assertIn("disk full", err)
        self.assertTrue(marker.is_file())
        self.assertEqual(sorted(p.name for p in (self.other.checkout / "cpctelera").iterdir()), before)
        base = self.other.checkout.parent
        self.assertEqual([p.name for p in base.iterdir() if ".import-" in p.name or p.name.endswith(".part")], [])

    def test_force_with_a_good_bundle_replaces_the_install_and_leaves_no_staging_folder(self):
        self.other.cli("install-toolchain", "--bundle", str(self.bundle))
        (self.other.checkout / "cpctelera" / "stale-file").write_text("x", encoding="utf-8")
        code, out, err = self.other.cli("install-toolchain", "--bundle", str(self.bundle), "--force")
        self.assertEqual((code, err), (0, ""), out)
        self.assertFalse((self.other.checkout / "cpctelera" / "stale-file").exists())
        self.assertTrue((self.other.checkout / glasnost.COMPLETE_MARKER).is_file())
        self.assertEqual([p.name for p in self.other.checkout.parent.iterdir() if ".import-" in p.name], [])

    def test_an_incomplete_checkout_is_resumed_in_place_without_force(self):
        self.other.cli("install-toolchain", "--bundle", str(self.bundle))
        (self.other.checkout / glasnost.COMPLETE_MARKER).unlink()       # what a failed compile leaves
        kept = self.other.checkout / "cpctelera" / "built-earlier"
        kept.write_text("x", encoding="utf-8")
        code, out, err = self.other.cli("install-toolchain", "--bundle", str(self.bundle))
        self.assertEqual((code, err), (0, ""), out)
        self.assertTrue(kept.is_file(), "a resumed install keeps its partial work")
        self.assertTrue((self.other.checkout / glasnost.COMPLETE_MARKER).is_file())


class Symlinked(BundleCase):
    """A development toolchain is often a symlink to another repository: it must never be rewritten or deleted."""

    def setUp(self):
        self.source = self.installed_sdk()
        self.bundle = self.export(self.source)
        self.other = self.offline_sdk(self.source)
        self.foreign = self.other.tmp / "foreign-repo"
        (self.foreign / "cpctelera").mkdir(parents=True)
        (self.foreign / "cpctelera" / "Makefile").write_text("my local edit\n", encoding="utf-8")
        git("init", "-q", cwd=self.foreign)
        git("remote", "add", "origin", "https://example.invalid/mine.git", cwd=self.foreign)
        self.other.checkout.parent.mkdir(parents=True)
        self.other.checkout.symlink_to(self.foreign)

    def assert_untouched(self):
        self.assertEqual((self.foreign / "cpctelera" / "Makefile").read_text(encoding="utf-8"), "my local edit\n")
        self.assertFalse((self.foreign / ".glasnost-complete").exists())
        self.assertFalse((self.foreign / ".git" / "shallow").exists())
        remote = subprocess.run(["git", "-C", str(self.foreign), "remote", "get-url", "origin"],
                                capture_output=True, text=True).stdout.strip()
        self.assertEqual(remote, "https://example.invalid/mine.git")
        self.assertTrue(self.other.checkout.is_symlink())

    def test_install_from_a_bundle_refuses_a_symlinked_checkout_with_and_without_force(self):
        for extra in ([], ["--force"]):
            with self.subTest(extra=extra):
                code, _, err = self.other.cli("install-toolchain", "--bundle", str(self.bundle), *extra)
                self.assertNotEqual(code, 0)
                self.assertIn("symbolic link", err)
                self.assert_untouched()

    def test_the_download_install_refuses_it_too(self):
        for extra in ([], ["--force"]):
            with self.subTest(extra=extra):
                code, _, err = self.other.cli("install-toolchain", *extra)
                self.assertNotEqual(code, 0)
                self.assertIn("symbolic link", err)
                self.assert_untouched()


class Hardening(BundleCase):
    def test_a_link_planted_at_a_guessable_staging_name_is_never_followed(self):
        sdk = self.installed_sdk()
        other = self.offline_sdk(sdk)
        bundle = str(self.export(sdk))
        victim = other.tmp / "victim"
        victim.mkdir()
        git("init", "-q", cwd=victim)
        base = other.checkout.parent
        base.mkdir(parents=True)
        for pid in range(1, 4):      # every name an earlier version would have chosen for this or a nearby pid
            for kind in ("import", "old"):
                (base / f".{sdk.rev}.{kind}-{os.getpid() + pid - 1}").symlink_to(victim)
        (base / f".{sdk.rev}.pack.part").symlink_to(victim / "pack")
        code, out, err = other.cli("install-toolchain", "--bundle", bundle)
        self.assertEqual((code, err), (0, ""), out)
        self.assertEqual(sorted(p.name for p in victim.iterdir()), [".git"])
        remote = subprocess.run(["git", "-C", str(victim), "remote"], capture_output=True, text=True).stdout.strip()
        self.assertEqual(remote, "")
        self.assertFalse((victim / ".git" / "shallow").exists())

    def test_remove_tree_unlinks_a_symlink_and_never_changes_what_it_points_to(self):
        target = Path(tempfile.mkdtemp(prefix="glasnost-victim-"))
        self.addCleanup(subprocess.run, ["rm", "-rf", str(target)])
        target.chmod(0o755)
        link = target.parent / (target.name + "-link")
        link.symlink_to(target)
        glasnost.remove_tree(link)
        self.assertFalse(link.is_symlink())
        self.assertEqual(target.stat().st_mode & 0o777, 0o755)
        self.assertTrue(target.is_dir())

    def test_remove_tree_does_not_follow_a_symlink_inside_the_tree(self):
        outside = Path(tempfile.mkdtemp(prefix="glasnost-outside-"))
        self.addCleanup(subprocess.run, ["rm", "-rf", str(outside)])
        outside.chmod(0o755)
        tree = Path(tempfile.mkdtemp(prefix="glasnost-tree-"))
        (tree / "inner").symlink_to(outside)
        glasnost.remove_tree(tree)
        self.assertFalse(tree.exists())
        self.assertEqual(outside.stat().st_mode & 0o777, 0o755)

    def test_an_orphan_tar_is_never_left_when_something_fails_after_the_rename(self):
        sdk = self.installed_sdk()
        pack = sdk.tmp / "p.pack"
        gb.build_pack(sdk.upstream, sdk.rev, pack)
        out = sdk.tmp / "orphan"
        out.mkdir()
        real = gb.sha256_file
        calls = []

        def second_call_fails(path):
            calls.append(path)
            if len(calls) == 2 and path.name.endswith(".tar"):
                raise OSError(5, "I/O error")
            return real(path)
        with mock.patch.object(gb, "sha256_file", side_effect=second_call_fails):
            gb.write_bundle(out / "x.tar", "https://example.invalid/c.git", sdk.rev, pack, "t")
        self.assertEqual([p.name for p in out.iterdir()], ["x.tar"])   # digest is taken before the rename now: the tar is whole

    def test_a_regular_file_at_the_checkout_path_is_a_translated_refusal_for_both_install_paths(self):
        sdk = self.installed_sdk()
        other = self.offline_sdk(sdk)
        bundle = str(self.export(sdk))
        other.checkout.parent.mkdir(parents=True)
        other.checkout.write_text("not a folder", encoding="utf-8")
        for argv in (["--bundle", bundle], ["--bundle", bundle, "--force"], [], ["--force"]):
            with self.subTest(argv=argv):
                code, _, err = other.cli("install-toolchain", *argv)
                self.assertNotEqual(code, 0)
                self.assertIn("is not a folder", err)
                self.assertEqual(other.checkout.read_text(encoding="utf-8"), "not a folder")
        self.assertEqual([p.name for p in other.checkout.parent.iterdir() if ".old-" in p.name or ".import-" in p.name], [])

    def test_the_installed_folder_gets_the_permissions_a_download_would_give(self):
        sdk = self.installed_sdk()
        other = self.offline_sdk(sdk)
        other.cli("install-toolchain", "--bundle", str(self.export(sdk)))
        umask = os.umask(0)
        os.umask(umask)
        self.assertEqual(other.checkout.stat().st_mode & 0o777, 0o777 & ~umask)

    def test_a_pack_missing_a_blob_that_git_itself_checks_is_rejected_before_any_change(self):
        """.gitattributes blobs are fsck-checked: the failure comes from index-pack, not from rev-list."""
        sdk = self.installed_sdk()
        other = self.offline_sdk(sdk)
        (sdk.upstream / "cpctelera" / ".gitattributes").write_text("* text=auto\n", encoding="utf-8")
        git("add", "-A", cwd=sdk.upstream)
        git("commit", "-q", "-m", "attrs", cwd=sdk.upstream)
        rev = subprocess.run(["git", "-C", str(sdk.upstream), "rev-parse", "HEAD"], check=True,
                             capture_output=True, text=True).stdout.strip()
        blob = subprocess.run(["git", "-C", str(sdk.upstream), "rev-parse", f"{rev}:cpctelera/.gitattributes"],
                              check=True, capture_output=True, text=True).stdout.strip()
        objects = [line.split()[0] for line in subprocess.run(
            ["git", "-C", str(sdk.upstream), "rev-list", "--objects", "--no-walk", rev],
            check=True, capture_output=True, text=True).stdout.splitlines() if line.split()[0] != blob]
        pack = sdk.tmp / "noattrs.pack"
        with pack.open("wb") as handle:
            subprocess.run(["git", "-C", str(sdk.upstream), "pack-objects", "--stdout", "-q"], stdout=handle, check=True,
                           input=("\n".join(objects) + "\n").encode())
        bundle = sdk.tmp / "noattrs.tar"
        gb.write_bundle(bundle, "https://example.invalid/c.git", rev, pack, "t")
        other.write_lock(rev)
        code, _, err = other.cli("install-toolchain", "--bundle", str(bundle))
        self.assertNotEqual(code, 0)
        self.assertTrue(err.strip())
        self.assertNotIn("Traceback", err)
        self.assertFalse((other.tmp / "tc").exists())

    def test_a_missing_blob_gets_the_commit_missing_message(self):
        sdk = self.installed_sdk()
        other = self.offline_sdk(sdk)
        pack = sdk.tmp / "noblob.pack"
        listing = subprocess.run(["git", "-C", str(sdk.upstream), "rev-list", "--objects", "--no-walk", sdk.rev],
                                 check=True, capture_output=True, text=True).stdout.splitlines()
        keep = [line.split()[0] for line in listing[:2]]          # the commit and its root tree only
        with pack.open("wb") as handle:
            subprocess.run(["git", "-C", str(sdk.upstream), "pack-objects", "--stdout", "-q"], stdout=handle, check=True,
                           input=("\n".join(keep) + "\n").encode())
        bundle = sdk.tmp / "noblob.tar"
        gb.write_bundle(bundle, "https://example.invalid/c.git", sdk.rev, pack, "t")
        code, _, err = other.cli("install-toolchain", "--bundle", str(bundle))
        self.assertNotEqual(code, 0)
        self.assertIn("does not contain the lockfile commit", err)
        self.assertFalse((other.tmp / "tc").exists())


class ExportHardening(BundleCase):
    def test_links_planted_at_the_part_names_are_neither_written_through_nor_renamed_into_place(self):
        """--output defaults to the current folder, so a cloned repo could ship such links."""
        sdk = self.installed_sdk()
        out = sdk.tmp / "out"
        out.mkdir()
        victim_tar, victim_sha = sdk.tmp / "victim-tar.txt", sdk.tmp / "victim-sha.txt"
        victim_tar.write_text("precious tar", encoding="utf-8")
        victim_sha.write_text("precious sha", encoding="utf-8")
        name = gb.bundle_name(sdk.rev)
        (out / f"{name}.part").symlink_to(victim_tar)
        (out / f"{name}.sha256.part").symlink_to(victim_sha)
        (out / f".{name}.pack.part").symlink_to(victim_tar)
        code, text, err = sdk.cli("export-bundle", "--output", str(out))
        self.assertEqual((code, err), (0, ""), text)
        self.assertEqual(victim_tar.read_text(encoding="utf-8"), "precious tar")
        self.assertEqual(victim_sha.read_text(encoding="utf-8"), "precious sha")
        self.assertFalse((out / name).is_symlink())
        self.assertFalse((out / (name + ".sha256")).is_symlink())
        self.assertTrue(gb.open_bundle(out / name, sdk.rev))

    def test_the_exported_files_get_normal_not_private_permissions(self):
        sdk = self.installed_sdk()
        previous = os.umask(0o022)
        try:
            bundle = self.export(sdk)
        finally:
            os.umask(previous)
        self.assertEqual(bundle.stat().st_mode & 0o777, 0o644)     # literal on purpose: not derived from the code under test
        self.assertEqual(bundle.with_name(bundle.name + ".sha256").stat().st_mode & 0o777, 0o644)
        self.assertEqual(gb.public_mode(), 0o666 & ~previous)
        self.assertEqual(gb.public_mode(directory=True), 0o777 & ~previous)

    def test_the_default_umask_values_of_public_mode(self):
        previous = os.umask(0o027)
        try:
            self.assertEqual((gb.public_mode(), gb.public_mode(directory=True)), (0o640, 0o750))
        finally:
            os.umask(previous)

    def test_a_failure_between_creating_the_pack_temp_and_the_try_block_leaves_nothing(self):
        sdk = self.installed_sdk()
        other = self.offline_sdk(sdk)
        bundle = str(self.export(sdk))
        real = glasnost.tempfile.mkdtemp

        def staging_fails(*args, **kwargs):
            if str(kwargs.get("prefix", "")).endswith(".import-"):
                raise OSError(28, "No space left on device")
            return real(*args, **kwargs)
        with mock.patch.object(glasnost.tempfile, "mkdtemp", side_effect=staging_fails):
            code, _, err = other.cli("install-toolchain", "--bundle", bundle)
        self.assertNotEqual(code, 0)
        self.assertIn("No space left", err)
        base = other.tmp / "tc" / "cpctelera-next"
        self.assertEqual([p.name for p in base.iterdir() if p.name.endswith(".part")], [])

    def test_a_failing_mkstemp_during_export_leaves_nothing(self):
        sdk = self.installed_sdk()
        out = sdk.tmp / "out"
        out.mkdir()
        with mock.patch.object(glasnost.tempfile, "mkstemp", side_effect=OSError(28, "No space left on device")):
            code, _, err = sdk.cli("export-bundle", "--output", str(out))
        self.assertNotEqual(code, 0)
        self.assertEqual([p.name for p in out.iterdir()], [])

    def test_remove_tree_never_changes_the_permissions_of_the_folder_above_the_tree(self):
        parent = Path(tempfile.mkdtemp(prefix="glasnost-parent-"))
        self.addCleanup(subprocess.run, ["rm", "-rf", str(parent)])
        parent.chmod(0o755)
        tree = parent / "tree"
        (tree / "x").mkdir(parents=True)
        tree.chmod(0o000)                       # the root itself cannot be listed
        glasnost.remove_tree(tree)
        self.assertFalse(tree.exists())
        self.assertEqual(parent.stat().st_mode & 0o777, 0o755)

    def test_a_planted_link_at_git_shallow_is_replaced_not_written_through(self):
        sdk = self.installed_sdk()
        pack = sdk.tmp / "p.pack"
        gb.build_pack(sdk.upstream, sdk.rev, pack)
        target = sdk.tmp / "resume"
        gb.import_pack(target, pack, sdk.rev)
        victim = sdk.tmp / "victim-does-not-exist.txt"      # a link to a missing file: git itself is fine with it
        shallow = target / ".git" / "shallow"
        shallow.unlink()
        shallow.symlink_to(victim)
        gb.import_pack(target, pack, sdk.rev)       # an in-place resume
        self.assertFalse(victim.exists(), "the link must not be written through")
        self.assertFalse(shallow.is_symlink())
        self.assertEqual(shallow.read_text(encoding="ascii").split(), [sdk.rev])

    def test_remove_tree_deletes_a_folder_it_cannot_even_list(self):
        tree = Path(tempfile.mkdtemp(prefix="glasnost-tree-"))
        self.addCleanup(subprocess.run, ["rm", "-rf", str(tree)])
        (tree / "locked" / "inner").mkdir(parents=True)
        (tree / "locked" / "inner" / "f").write_text("x", encoding="utf-8")
        (tree / "locked").chmod(0o000)
        glasnost.remove_tree(tree)
        self.assertFalse(tree.exists())

    def test_the_install_lock_does_not_follow_a_planted_link(self):
        victim = Path(tempfile.mkdtemp(prefix="glasnost-lockvictim-")) / "v.txt"
        self.addCleanup(subprocess.run, ["rm", "-rf", str(victim.parent)])
        victim.write_text("precious", encoding="utf-8")
        checkout = victim.parent / "cpctelera-next" / ("a" * 40)
        checkout.parent.mkdir()
        (checkout.parent / f".{checkout.name}.lock").symlink_to(victim)
        with self.assertRaises(glasnost.CliError) as caught:
            with glasnost.install_lock(checkout, "en"):
                self.fail("must not lock through a link")
        self.assertIn("Cannot create the lock", str(caught.exception))
        self.assertEqual(victim.read_text(encoding="utf-8"), "precious")

    def test_the_installed_folder_follows_the_umask_for_other_umasks_too(self):
        sdk = self.installed_sdk()
        other = self.offline_sdk(sdk)
        bundle = str(self.export(sdk))
        previous = os.umask(0o077)
        try:
            other.cli("install-toolchain", "--bundle", bundle)
        finally:
            os.umask(previous)
        self.assertEqual(other.checkout.stat().st_mode & 0o777, 0o700)


class Quoting(BundleCase):
    def test_the_printed_next_command_is_copy_pasteable_when_the_path_has_spaces_and_quotes(self):
        import shlex
        sdk = self.installed_sdk()
        out = sdk.tmp / "out with 'spaces' and ñ"
        code, text, err = sdk.cli("export-bundle", "--output", str(out))
        self.assertEqual((code, err), (0, ""), text)
        line = next(l for l in text.splitlines() if "install-toolchain --bundle" in l)
        argv = shlex.split(line.split("ejecuta:", 1)[-1].split("run:", 1)[-1])
        self.assertEqual(argv[:3], ["glasnost", "install-toolchain", "--bundle"])
        self.assertEqual(Path(argv[3]), out / gb.bundle_name(sdk.rev))
        self.assertTrue(Path(argv[3]).is_file())


class SwapPair(BundleCase):
    """swap_pair directly: every failure point, KeyboardInterrupt included."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="glasnost-swap-"))
        self.addCleanup(subprocess.run, ["rm", "-rf", str(self.dir)])
        self.a, self.b = self.dir / "a.tar", self.dir / "a.tar.sha256"
        self.na, self.nb = self.dir / "new-a.part", self.dir / "new-b.part"
        self.na.write_bytes(b"NEW A")
        self.nb.write_bytes(b"NEW B")
        self.real = os.replace

    def names(self):
        return sorted(p.name for p in self.dir.iterdir() if not p.name.startswith("new-"))

    def run_swap(self, flaky):
        with mock.patch.object(glasnost.os, "replace", side_effect=flaky):
            glasnost.swap_pair(((self.na, self.a), (self.nb, self.b)), "en")

    def test_success_replaces_both_and_deletes_every_backup(self):
        self.a.write_bytes(b"OLD A")
        self.b.write_bytes(b"OLD B")
        glasnost.swap_pair(((self.na, self.a), (self.nb, self.b)), "en")
        self.assertEqual((self.a.read_bytes(), self.b.read_bytes()), (b"NEW A", b"NEW B"))
        self.assertEqual(self.names(), ["a.tar", "a.tar.sha256"], "no .old- backup may remain")

    def test_keyboard_interrupt_on_the_second_move_restores_everything(self):
        self.a.write_bytes(b"OLD A")
        self.b.write_bytes(b"OLD B")

        def flaky(src, dst):
            if Path(src) == self.nb:
                raise KeyboardInterrupt
            return self.real(src, dst)
        with self.assertRaises(KeyboardInterrupt):
            self.run_swap(flaky)
        self.assertEqual((self.a.read_bytes(), self.b.read_bytes()), (b"OLD A", b"OLD B"))
        self.assertEqual(self.names(), ["a.tar", "a.tar.sha256"])

    def test_an_interrupt_right_after_a_move_completed_still_removes_that_new_file(self):
        """The window between os.replace returning and the bookkeeping: nothing may survive without a backup."""
        def flaky(src, dst):
            self.real(src, dst)
            if Path(src) == self.nb:
                raise KeyboardInterrupt           # the move happened, then the interrupt
        with self.assertRaises(KeyboardInterrupt):
            self.run_swap(flaky)
        self.assertEqual(self.names(), [], "fresh output folder: no new file may survive")

    def test_a_failing_restore_does_not_abandon_the_other_backups_and_the_original_error_wins(self):
        self.a.write_bytes(b"OLD A")
        self.b.write_bytes(b"OLD B")

        def flaky(src, dst):
            if Path(src) == self.nb:
                raise OSError(28, "No space left on device")      # the real failure
            if ".old-" in str(src) and Path(dst) == self.a:
                raise OSError(5, "undo injected")                  # and the restore of the first backup fails too
            return self.real(src, dst)
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(OSError) as caught:
            self.run_swap(flaky)
        self.assertEqual(caught.exception.errno, 28, "the ORIGINAL error must propagate")
        self.assertEqual(self.b.read_bytes(), b"OLD B", "the other backup is still restored")
        kept = [p for p in self.dir.iterdir() if ".old-" in p.name]
        self.assertEqual([p.read_bytes() for p in kept], [b"OLD A"], "the unrestorable backup is kept")
        self.assertIn(str(kept[0]), err.getvalue())
        self.assertIn("previous file is kept", err.getvalue())

    def test_a_failed_rename_to_backup_leaves_no_placeholder(self):
        self.a.write_bytes(b"OLD A")

        def flaky(src, dst):
            if Path(src) == self.a:
                raise OSError(13, "Permission denied")
            return self.real(src, dst)
        with self.assertRaises(OSError):
            self.run_swap(flaky)
        self.assertEqual(self.a.read_bytes(), b"OLD A")
        self.assertEqual(self.names(), ["a.tar"])

        def interrupted(src, dst):
            if Path(src) == self.a:
                raise KeyboardInterrupt
            return self.real(src, dst)
        with self.assertRaises(KeyboardInterrupt):
            self.run_swap(interrupted)
        self.assertEqual(self.names(), ["a.tar"])

    def test_a_dangling_symlink_at_a_final_path_is_backed_up_and_restored(self):
        self.a.symlink_to(self.dir / "nowhere")

        def flaky(src, dst):
            if Path(src) == self.nb:
                raise OSError(5, "I/O error")
            return self.real(src, dst)
        with self.assertRaises(OSError):
            self.run_swap(flaky)
        self.assertTrue(self.a.is_symlink())
        self.assertEqual(os.readlink(self.a), str(self.dir / "nowhere"))
        self.assertEqual(self.names(), ["a.tar"])

    def test_a_failure_while_setting_the_second_file_aside_leaves_it_alone(self):
        self.a.write_bytes(b"OLD A")
        self.b.write_bytes(b"OLD B")
        real_mkstemp = tempfile.mkstemp

        def flaky(*args, **kwargs):
            if str(kwargs.get("prefix", "")).startswith("a.tar.sha256"):
                raise OSError(28, "No space left on device")
            return real_mkstemp(*args, **kwargs)
        with mock.patch.object(glasnost.tempfile, "mkstemp", side_effect=flaky), self.assertRaises(OSError):
            glasnost.swap_pair(((self.na, self.a), (self.nb, self.b)), "en")
        self.assertEqual((self.a.read_bytes(), self.b.read_bytes()), (b"OLD A", b"OLD B"))
        self.assertEqual(self.names(), ["a.tar", "a.tar.sha256"])


class Swap(BundleCase):
    def test_force_over_an_install_with_a_read_only_folder_still_swaps_and_keeps_nothing_behind(self):
        sdk = self.installed_sdk()
        other = self.offline_sdk(sdk)
        bundle = str(self.export(sdk))
        other.cli("install-toolchain", "--bundle", bundle)
        locked = other.checkout / "cpctelera" / "tools" / "2cdt"
        locked.chmod(0o555)
        self.addCleanup(lambda: locked.exists() and locked.chmod(0o755))
        code, out, err = other.cli("install-toolchain", "--bundle", bundle, "--force")
        self.assertEqual((code, err), (0, ""), out)
        self.assertEqual(glasnost.missing_files(other.checkout / "cpctelera"), [])
        self.assertEqual([p.name for p in other.checkout.parent.iterdir() if ".old-" in p.name or ".import-" in p.name], [])

    def test_if_even_the_first_move_fails_no_empty_aside_folder_is_left(self):
        sdk = self.installed_sdk()
        other = self.offline_sdk(sdk)
        bundle = str(self.export(sdk))
        other.cli("install-toolchain", "--bundle", bundle)
        real = os.replace

        def refuse_first(src, dst):
            if str(src) == str(other.checkout):
                raise OSError(13, "Permission denied")
            return real(src, dst)
        with mock.patch.object(glasnost.os, "replace", side_effect=refuse_first):
            code, _, _ = other.cli("install-toolchain", "--bundle", bundle, "--force")
        self.assertNotEqual(code, 0)
        self.assertTrue((other.checkout / glasnost.COMPLETE_MARKER).is_file())
        self.assertEqual([p.name for p in other.checkout.parent.iterdir() if ".old-" in p.name or ".import-" in p.name], [])

    def test_if_the_final_move_fails_the_old_install_is_put_back(self):
        sdk = self.installed_sdk()
        other = self.offline_sdk(sdk)
        bundle = str(self.export(sdk))
        other.cli("install-toolchain", "--bundle", bundle)
        real = os.replace
        calls = []

        def flaky(src, dst):
            calls.append((str(src), str(dst)))
            if ".import-" in str(src):
                raise OSError(5, "I/O error")
            return real(src, dst)
        with mock.patch.object(glasnost.os, "replace", side_effect=flaky):
            code, _, err = other.cli("install-toolchain", "--bundle", bundle, "--force")
        self.assertNotEqual(code, 0)
        self.assertTrue((other.checkout / glasnost.COMPLETE_MARKER).is_file(), "the old install must come back")
        self.assertEqual(glasnost.missing_files(other.checkout / "cpctelera"), [])
        self.assertEqual([p.name for p in other.checkout.parent.iterdir() if ".old-" in p.name or ".import-" in p.name], [])


class Failures(BundleCase):
    def test_export_with_an_unreachable_upstream_leaves_no_temporary_checkout(self):
        sdk = FakeSdk(self)
        sdk.env["GLASNOST_CPCTELERA_URL"] = NO_NETWORK
        code, _, err = sdk.cli("export-bundle", "--output", str(sdk.tmp / "out"))
        self.assertNotEqual(code, 0)
        self.assertIn("the attempt is discarded", err)
        self.assertNotIn("resumes", err)      # the install message promises a partial work that export does not keep
        self.assertFalse((sdk.tmp / "tc").exists(), "a failed export must not leave the folders it created")

    def test_export_keeps_folders_it_did_not_create(self):
        sdk = FakeSdk(self)
        sdk.env["GLASNOST_CPCTELERA_URL"] = NO_NETWORK
        (sdk.tmp / "tc" / "cpctelera-next").mkdir(parents=True)
        (sdk.tmp / "tc" / "cpctelera-next" / "mine.txt").write_text("x", encoding="utf-8")
        sdk.cli("export-bundle", "--output", str(sdk.tmp / "out"))
        self.assertEqual([p.name for p in (sdk.tmp / "tc" / "cpctelera-next").iterdir()], ["mine.txt"])

    def test_a_write_failure_midway_leaves_no_part_files_in_the_output_folder(self):
        sdk = self.installed_sdk()
        out = sdk.tmp / "out"
        out.mkdir()          # existing on purpose: the point is that no .part file survives in it
        with mock.patch.object(tarfile.TarFile, "addfile", side_effect=[None, OSError(28, "No space left on device")]):
            code, _, err = sdk.cli("export-bundle", "--output", str(out))
        self.assertNotEqual(code, 0)
        self.assertIn("No space left", err)
        self.assertEqual([p.name for p in out.iterdir()], [])

    def test_a_checksum_file_that_cannot_be_written_removes_the_tar_too(self):
        sdk = self.installed_sdk()
        out = sdk.tmp / "out"
        (out / (gb.bundle_name(sdk.rev) + ".sha256")).mkdir(parents=True)     # a folder where the file must go
        code, _, err = sdk.cli("export-bundle", "--output", str(out))
        self.assertNotEqual(code, 0)
        self.assertNotIn("Traceback", err)
        self.assertEqual(sorted(p.name for p in out.iterdir()), [gb.bundle_name(sdk.rev) + ".sha256"])

    def test_a_failed_export_never_destroys_a_bundle_that_was_already_there(self):
        sdk = self.installed_sdk()
        out = sdk.tmp / "out"
        out.mkdir()
        old = out / gb.bundle_name(sdk.rev)
        old.write_bytes(b"OLD USER BUNDLE")
        (out / (old.name + ".sha256")).mkdir()          # makes the checksum step fail
        code, _, err = sdk.cli("export-bundle", "--output", str(out))
        self.assertNotEqual(code, 0)
        self.assertEqual(old.read_bytes(), b"OLD USER BUNDLE")
        self.assertEqual(sorted(p.name for p in out.iterdir()), sorted([old.name, old.name + ".sha256"]))

    def test_a_failure_on_the_second_move_restores_the_old_bundle_and_checksum_and_leaves_no_new_files(self):
        sdk = self.installed_sdk()
        out = sdk.tmp / "out"
        out.mkdir()
        old_tar, old_sha = out / gb.bundle_name(sdk.rev), out / (gb.bundle_name(sdk.rev) + ".sha256")
        old_tar.write_bytes(b"OLD USER BUNDLE")
        old_sha.write_text("OLD SHA\n", encoding="ascii")
        real = os.replace
        for failing in ("tar", "sha"):
            with self.subTest(failing=failing):
                def flaky(src, dst, failing=failing):
                    if str(src).endswith(".part") and str(dst) == str(old_sha if failing == "sha" else old_tar):
                        raise OSError(5, "I/O error")
                    return real(src, dst)
                with mock.patch.object(glasnost.os, "replace", side_effect=flaky):
                    code, _, err = sdk.cli("export-bundle", "--output", str(out))
                self.assertNotEqual(code, 0)
                self.assertEqual(old_tar.read_bytes(), b"OLD USER BUNDLE")
                self.assertEqual(old_sha.read_text(encoding="ascii"), "OLD SHA\n")
                self.assertEqual(sorted(p.name for p in out.iterdir()), sorted([old_tar.name, old_sha.name]))

    def test_a_failure_on_the_first_export_leaves_no_new_files_at_all(self):
        sdk = self.installed_sdk()
        out = sdk.tmp / "out"
        out.mkdir()
        real = os.replace

        def flaky(src, dst):
            if str(src).endswith(".part") and str(dst).endswith(".sha256"):
                raise OSError(5, "I/O error")
            return real(src, dst)
        with mock.patch.object(glasnost.os, "replace", side_effect=flaky):
            code, _, _ = sdk.cli("export-bundle", "--output", str(out))
        self.assertNotEqual(code, 0)
        self.assertEqual([p.name for p in out.iterdir()], [], "the new tar must not survive without its checksum")

    def test_a_failure_while_setting_the_second_file_aside_does_not_touch_it(self):
        sdk = self.installed_sdk()
        out = sdk.tmp / "out"
        out.mkdir()
        old_tar, old_sha = out / gb.bundle_name(sdk.rev), out / (gb.bundle_name(sdk.rev) + ".sha256")
        old_tar.write_bytes(b"OLD USER BUNDLE")
        old_sha.write_text("OLD SHA\n", encoding="ascii")
        real = glasnost.tempfile.mkstemp

        def flaky(*args, **kwargs):
            if str(kwargs.get("prefix", "")).endswith(".sha256.old-"):
                raise OSError(28, "No space left on device")
            return real(*args, **kwargs)
        with mock.patch.object(glasnost.tempfile, "mkstemp", side_effect=flaky):
            code, _, _ = sdk.cli("export-bundle", "--output", str(out))
        self.assertNotEqual(code, 0)
        self.assertEqual(old_tar.read_bytes(), b"OLD USER BUNDLE")
        self.assertEqual(old_sha.read_text(encoding="ascii"), "OLD SHA\n")
        self.assertEqual(sorted(p.name for p in out.iterdir()), sorted([old_tar.name, old_sha.name]))

    def test_a_good_export_replaces_an_older_bundle_and_checksum(self):
        sdk = self.installed_sdk()
        out = sdk.tmp / "out"
        out.mkdir()
        (out / gb.bundle_name(sdk.rev)).write_bytes(b"OLD")
        (out / (gb.bundle_name(sdk.rev) + ".sha256")).write_text("OLD\n", encoding="ascii")
        code, text, err = sdk.cli("export-bundle", "--output", str(out))
        self.assertEqual((code, err), (0, ""), text)
        bundle = out / gb.bundle_name(sdk.rev)
        self.assertEqual(sorted(p.name for p in out.iterdir()), [bundle.name, bundle.name + ".sha256"],
                         "no backup or temporary file may remain after a replacing export")
        self.assertTrue(gb.open_bundle(bundle, sdk.rev))
        self.assertEqual((out / (bundle.name + ".sha256")).read_text(encoding="ascii"), f"{gb.sha256_file(bundle)}  {bundle.name}\n")

    def test_a_file_where_the_output_folder_should_be_gives_a_translated_message(self):
        sdk = self.installed_sdk()
        blocker = sdk.tmp / "blocker"
        blocker.write_text("x", encoding="utf-8")
        code, _, err = sdk.cli("export-bundle", "--output", str(blocker))
        self.assertNotEqual(code, 0)
        self.assertIn("System error", err)
        self.assertNotIn("Traceback", err)


class Truncation(BundleCase):
    """A tar cut anywhere before its two closing zero blocks is a truncated file, even if all content is there."""

    def setUp(self):
        self.source = self.installed_sdk()
        self.bundle = self.export(self.source)
        self.other = self.offline_sdk(self.source)
        with tarfile.open(self.bundle) as archive:
            self.data_end = max(m.offset_data + -(-m.size // 512) * 512 for m in archive.getmembers())

    def cut(self, size: int) -> Path:
        path = self.other.tmp / f"cut-{size}.tar"
        path.write_bytes(self.bundle.read_bytes()[:size])
        return path

    def test_every_cut_before_the_end_marker_is_rejected_including_inside_the_padding(self):
        for size in (self.data_end - 100, self.data_end - 1, self.data_end, self.data_end + 1, self.data_end + 511,
                     self.data_end + 512, self.data_end + 1023):
            with self.subTest(size=size):
                code, _, err = self.other.cli("install-toolchain", "--bundle", str(self.cut(size)), "--dry-run")
                self.assertNotEqual(code, 0)
                self.assertTrue(err.strip())
                self.assertFalse((self.other.tmp / "tc").exists())

    def test_trailing_bytes_and_altered_closing_blocks_are_rejected_with_the_right_message(self):
        original = self.bundle.read_bytes()
        cases = {
            "one extra byte": original + b"x",
            "extra zero byte (not a multiple of 512)": original + b"\0",
            "extra non-zero block": original + b"x" * 512,
            "flip inside the closing blocks": original[:self.data_end + 5] + b"\1" + original[self.data_end + 6:],
            "flip in the record padding": original[:self.data_end + 2000] + b"\1" + original[self.data_end + 2001:],
        }
        for label, data in cases.items():
            with self.subTest(label):
                path = self.other.tmp / "x.tar"
                path.write_bytes(data)
                code, _, err = self.other.cli("install-toolchain", "--bundle", str(path), "--dry-run")
                self.assertNotEqual(code, 0)
                self.assertIn("not valid", err)
                self.assertNotIn("cut short", err, "nothing is missing: the message must not say it is")
                self.assertFalse((self.other.tmp / "tc").exists())

    def test_a_flipped_byte_in_the_padding_between_members_is_rejected(self):
        original = bytearray(self.bundle.read_bytes())
        with tarfile.open(self.bundle) as archive:
            first = min(archive.getmembers(), key=lambda m: m.offset_data)
            pad_at = first.offset_data + first.size
            self.assertGreater(-(-first.size // 512) * 512 - first.size, 0, "fixture needs padding to flip")
        original[pad_at] = 1
        path = self.other.tmp / "padflip.tar"
        path.write_bytes(bytes(original))
        code, _, err = self.other.cli("install-toolchain", "--bundle", str(path), "--dry-run")
        self.assertNotEqual(code, 0)
        self.assertIn("padding that follows a member", err)
        self.assertNotIn("after the last member", err, "this padding is not after the last member")

    def test_json_true_is_not_the_schema_number_one(self):
        def edit(name, data):
            if name != gb.MANIFEST_NAME:
                return data
            body = json.loads(data)
            body["schema"] = True
            return json.dumps(body).encode()
        code, _, err = self.other.cli("install-toolchain", "--bundle", str(self.rewrite(self.bundle, edit)), "--dry-run")
        self.assertNotEqual(code, 0)
        self.assertIn("manifest is not valid", err)

    def test_any_amount_of_zero_record_padding_is_valid(self):
        original = self.bundle.read_bytes()[:self.data_end]
        for blocks in (2, 3, 20, 40):
            with self.subTest(blocks=blocks):
                path = self.other.tmp / f"pad{blocks}.tar"
                path.write_bytes(original + b"\0" * 512 * blocks)
                code, out, err = self.other.cli("install-toolchain", "--bundle", str(path), "--dry-run")
                self.assertEqual((code, err), (0, ""), out)

    def test_a_tar_with_exactly_the_two_closing_zero_blocks_is_valid(self):
        code, out, err = self.other.cli("install-toolchain", "--bundle", str(self.cut(self.data_end + 1024)), "--dry-run")
        self.assertEqual((code, err), (0, ""), out)

    def test_the_message_says_the_file_is_cut_short(self):
        _, _, err = self.other.cli("install-toolchain", "--bundle", str(self.cut(self.data_end + 100)), "--dry-run")
        self.assertIn("cut short", err)


class OutputFolders(BundleCase):
    def test_a_failed_export_removes_the_nested_output_folders_it_created_but_a_good_one_keeps_them(self):
        sdk = FakeSdk(self)
        sdk.env["GLASNOST_CPCTELERA_URL"] = NO_NETWORK
        nested = sdk.tmp / "a" / "b" / "c"
        code, _, _ = sdk.cli("export-bundle", "--output", str(nested))
        self.assertNotEqual(code, 0)
        self.assertFalse((sdk.tmp / "a").exists(), "folders created for the output must be taken back on failure")
        good = self.installed_sdk()
        nested_ok = good.tmp / "x" / "y"
        code, _, err = good.cli("export-bundle", "--output", str(nested_ok))
        self.assertEqual((code, err), (0, ""))
        self.assertTrue((nested_ok / gb.bundle_name(good.rev)).is_file())

    def test_an_output_folder_that_already_existed_survives_a_failed_export(self):
        sdk = FakeSdk(self)
        sdk.env["GLASNOST_CPCTELERA_URL"] = NO_NETWORK
        existing = sdk.tmp / "existing"
        existing.mkdir()
        sdk.cli("export-bundle", "--output", str(existing / "sub"))
        self.assertTrue(existing.is_dir())
        self.assertFalse((existing / "sub").exists())

    def test_control_codes_in_member_names_never_reach_the_terminal_raw(self):
        evil = self.tar_with({"\x1b[31mevil\x07": b"x"})
        sdk = self.installed_sdk()
        other = self.offline_sdk(sdk)
        code, _, err = other.cli("install-toolchain", "--bundle", str(evil), "--dry-run")
        self.assertNotEqual(code, 0)
        self.assertNotIn("\x1b", err)
        self.assertNotIn("\x07", err)


class MakeDirs(BundleCase):
    def test_a_failure_midway_removes_the_folders_it_had_already_made(self):
        base = Path(tempfile.mkdtemp(prefix="glasnost-mk-"))
        self.addCleanup(subprocess.run, ["rm", "-rf", str(base)])
        real = Path.mkdir
        calls = []

        def second_fails(self_path, *args, **kwargs):
            calls.append(self_path)
            if len(calls) == 2:
                raise PermissionError(13, "Permission denied")
            return real(self_path, *args, **kwargs)
        with mock.patch.object(Path, "mkdir", second_fails):
            with self.assertRaises(PermissionError):
                glasnost.make_dirs(base / "m1" / "m2" / "m3")
        self.assertFalse((base / "m1").exists(), "the chain it started must be taken back")

    def test_it_returns_only_what_it_created_deepest_first(self):
        base = Path(tempfile.mkdtemp(prefix="glasnost-mk-"))
        self.addCleanup(subprocess.run, ["rm", "-rf", str(base)])
        (base / "keep").mkdir()
        made = glasnost.make_dirs(base / "keep" / "a" / "b")
        self.assertEqual(made, [base / "keep" / "a" / "b", base / "keep" / "a"])

    def test_a_dangling_link_in_the_way_raises_and_creates_nothing_behind_it(self):
        base = Path(tempfile.mkdtemp(prefix="glasnost-mk-"))
        self.addCleanup(subprocess.run, ["rm", "-rf", str(base)])
        (base / "link").symlink_to(base / "nowhere")
        with self.assertRaises(FileExistsError):
            glasnost.make_dirs(base / "link" / "x")
        self.assertFalse((base / "nowhere").exists())

    def test_a_failing_export_with_a_half_made_output_chain_leaves_none_of_it(self):
        sdk = FakeSdk(self)
        real = Path.mkdir
        calls = []

        def second_fails(self_path, *args, **kwargs):
            if str(self_path).startswith(str(sdk.tmp / "o1")):
                calls.append(self_path)
                if len(calls) == 2:
                    raise PermissionError(13, "Permission denied")
            return real(self_path, *args, **kwargs)
        with mock.patch.object(Path, "mkdir", second_fails):
            code, _, err = sdk.cli("export-bundle", "--output", str(sdk.tmp / "o1" / "o2" / "o3"))
        self.assertNotEqual(code, 0)
        self.assertNotIn("Traceback", err)
        self.assertFalse((sdk.tmp / "o1").exists())

    def test_sparse_and_other_non_plain_members_are_refused_as_layout_not_called_truncated(self):
        import shutil as _shutil
        if not _shutil.which("tar"):
            self.skipTest("no tar")
        work = Path(tempfile.mkdtemp(prefix="glasnost-sparse-"))
        self.addCleanup(subprocess.run, ["rm", "-rf", str(work)])
        (work / gb.MANIFEST_NAME).write_text("{}", encoding="utf-8")
        with (work / gb.PACK_NAME).open("wb") as handle:
            handle.write(b"head")
            handle.seek(1 << 20)                    # a real hole
            handle.write(b"tail")
        archive = work / "sparse.tar"
        subprocess.run(["tar", "--format=gnu", "-S", "-cf", str(archive), "-C", str(work), gb.MANIFEST_NAME, gb.PACK_NAME],
                       check=True)
        sdk = self.installed_sdk()
        other = self.offline_sdk(sdk)
        code, _, err = other.cli("install-toolchain", "--bundle", str(archive), "--dry-run")
        self.assertNotEqual(code, 0)
        self.assertIn("is not a plain file", err)
        self.assertNotIn("cut short", err)

    def test_a_pax_sparse_member_is_refused_too(self):
        import shutil as _shutil
        if not _shutil.which("tar"):
            self.skipTest("no tar")
        work = Path(tempfile.mkdtemp(prefix="glasnost-paxsparse-"))
        self.addCleanup(subprocess.run, ["rm", "-rf", str(work)])
        (work / gb.MANIFEST_NAME).write_text("{}", encoding="utf-8")
        with (work / gb.PACK_NAME).open("wb") as handle:
            handle.write(b"head")
            handle.seek(1 << 20)
            handle.write(b"tail")
        archive = work / "pax.tar"
        subprocess.run(["tar", "--format=posix", "-S", "-cf", str(archive), "-C", str(work), gb.MANIFEST_NAME, gb.PACK_NAME],
                       check=True)
        with tarfile.open(archive) as handle:
            self.assertTrue(any(m.sparse is not None for m in handle.getmembers()), "fixture must really be sparse")
        sdk = self.installed_sdk()
        other = self.offline_sdk(sdk)
        code, _, err = other.cli("install-toolchain", "--bundle", str(archive), "--dry-run")
        self.assertNotEqual(code, 0)
        self.assertIn("is not a plain file", err)


class HiddenHeaders(BundleCase):
    """tarfile consumes extended headers silently; the scan must see them."""

    def setUp(self):
        self.source = self.installed_sdk()
        self.bundle = self.export(self.source)
        self.other = self.offline_sdk(self.source)
        with tarfile.open(self.bundle) as archive:
            self.manifest = archive.extractfile(gb.MANIFEST_NAME).read()
            self.pack = archive.extractfile(gb.PACK_NAME).read()

    def tar_of(self, members) -> Path:
        path = self.other.tmp / "hidden.tar"
        with tarfile.open(path, "w", format=tarfile.USTAR_FORMAT) as tar:
            for name, kind, data in members:
                info = tarfile.TarInfo(name)
                info.type, info.size = kind, len(data)
                tar.addfile(info, io.BytesIO(data))
        return path

    @staticmethod
    def pax_record(key: str, value: str) -> bytes:
        body = f" {key}={value}\n".encode()
        length = len(body) + 1
        while len(str(length).encode()) + len(body) != length:
            length += 1
        return str(length).encode() + body

    def test_the_plain_two_member_tar_built_here_is_valid(self):
        path = self.tar_of([(gb.MANIFEST_NAME, tarfile.REGTYPE, self.manifest), (gb.PACK_NAME, tarfile.REGTYPE, self.pack)])
        code, out, err = self.other.cli("install-toolchain", "--bundle", str(path), "--dry-run")
        self.assertEqual((code, err), (0, ""), out)

    def test_a_pax_header_between_the_members_is_refused(self):
        path = self.tar_of([(gb.MANIFEST_NAME, tarfile.REGTYPE, self.manifest),
                            ("PaxHeader", tarfile.XHDTYPE, self.pax_record("comment", "hidden payload")),
                            (gb.PACK_NAME, tarfile.REGTYPE, self.pack)])
        with tarfile.open(path) as archive:
            self.assertEqual([m.name for m in archive.getmembers()], [gb.MANIFEST_NAME, gb.PACK_NAME],
                             "fixture: tarfile really hides the extended header")
        code, _, err = self.other.cli("install-toolchain", "--bundle", str(path), "--dry-run")
        self.assertNotEqual(code, 0)
        self.assertIn("is not a plain file", err)
        self.assertFalse((self.other.tmp / "tc").exists())

    def test_a_gnu_long_name_header_and_a_global_pax_header_are_refused(self):
        for label, kind in (("long name", tarfile.GNUTYPE_LONGNAME), ("global pax", tarfile.XGLTYPE)):
            with self.subTest(label):
                data = b"x" * 10 if kind == tarfile.GNUTYPE_LONGNAME else self.pax_record("comment", "g")
                path = self.tar_of([("hdr", kind, data), (gb.MANIFEST_NAME, tarfile.REGTYPE, self.manifest),
                                    (gb.PACK_NAME, tarfile.REGTYPE, self.pack)])
                code, _, err = self.other.cli("install-toolchain", "--bundle", str(path), "--dry-run")
                self.assertNotEqual(code, 0)
                self.assertFalse((self.other.tmp / "tc").exists())

    def test_size_fields_with_signs_underscores_spaces_or_base256_are_refused(self):
        two = self.tar_of([(gb.MANIFEST_NAME, tarfile.REGTYPE, self.manifest), (gb.PACK_NAME, tarfile.REGTYPE, self.pack)])
        original = two.read_bytes()
        digits = f"{len(self.manifest):011o}".encode()
        for label, field in (("plus", b"+" + digits[1:]), ("underscore", digits[:3] + b"_" + digits[4:]),
                             ("inner space", digits[:3] + b" " + digits[4:]), ("empty", b"\0" * 12),
                             ("base256", b"\x80" + b"\0" * 10 + bytes([len(self.manifest) & 255]))):
            with self.subTest(label):
                block = bytearray(original[:512])
                block[124:136] = field.ljust(12, b"\0")[:12]
                block[148:156] = b"        "
                block[148:156] = f"{sum(block):06o}\0 ".encode()          # keep the header checksum valid
                path = self.other.tmp / f"size-{label}.tar"
                path.write_bytes(bytes(block) + original[512:])
                code, _, err = self.other.cli("install-toolchain", "--bundle", str(path), "--dry-run")
                self.assertNotEqual(code, 0)
                self.assertFalse((self.other.tmp / "tc").exists())

    def test_a_member_header_with_a_wrong_checksum_is_refused_by_the_scan_itself(self):
        two = self.tar_of([(gb.MANIFEST_NAME, tarfile.REGTYPE, self.manifest), (gb.PACK_NAME, tarfile.REGTYPE, self.pack)])
        data = bytearray(two.read_bytes())
        data[110] ^= 0x01                                   # inside the uid field: name intact, checksum no longer matches
        path = self.other.tmp / "badsum-member.tar"
        path.write_bytes(bytes(data))
        with self.assertRaises(gb.BundleError) as caught:
            gb.scan_tar(path)
        self.assertEqual(caught.exception.key, "bundle.unreadable")

    def test_bytes_hiding_after_the_nul_of_the_name_field_are_refused(self):
        two = self.tar_of([(gb.MANIFEST_NAME, tarfile.REGTYPE, self.manifest), (gb.PACK_NAME, tarfile.REGTYPE, self.pack)])
        original = bytearray(two.read_bytes())
        original[len(gb.MANIFEST_NAME) + 3] = ord("j")                   # "manifest.json\0\0\0j..."
        original[148:156] = b"        "
        original[148:156] = f"{sum(original[:512]):06o}\0 ".encode()
        path = self.other.tmp / "nulname.tar"
        path.write_bytes(bytes(original))
        with self.assertRaises(gb.BundleError) as caught:
            gb.scan_tar(path)
        self.assertEqual(caught.exception.key, "bundle.bad_layout")

    def test_a_third_valid_member_is_a_layout_error_and_garbage_after_the_members_is_a_bad_end(self):
        three = self.tar_of([(gb.MANIFEST_NAME, tarfile.REGTYPE, self.manifest), (gb.PACK_NAME, tarfile.REGTYPE, self.pack),
                             ("extra.txt", tarfile.REGTYPE, b"x")])
        _, _, err = self.other.cli("install-toolchain", "--bundle", str(three), "--dry-run")
        self.assertIn("does not have the expected content", err)
        two = self.tar_of([(gb.MANIFEST_NAME, tarfile.REGTYPE, self.manifest), (gb.PACK_NAME, tarfile.REGTYPE, self.pack)])
        data = two.read_bytes()
        with tarfile.open(two) as archive:
            end = max(m.offset_data + -(-m.size // 512) * 512 for m in archive.getmembers())
        broken = self.other.tmp / "garbage.tar"
        broken.write_bytes(data[:end] + b"\x01" + data[end + 1:])
        _, _, err = self.other.cli("install-toolchain", "--bundle", str(broken), "--dry-run")
        self.assertIn("not valid", err)

    def test_a_block_that_looks_like_a_header_but_has_a_wrong_checksum_is_altered_bytes_not_a_member(self):
        two = self.tar_of([(gb.MANIFEST_NAME, tarfile.REGTYPE, self.manifest), (gb.PACK_NAME, tarfile.REGTYPE, self.pack)])
        with tarfile.open(two) as archive:
            end = max(m.offset_data + -(-m.size // 512) * 512 for m in archive.getmembers())
        info = tarfile.TarInfo("extra.txt")
        block = bytearray(info.tobuf(tarfile.USTAR_FORMAT)[:512])
        self.assertTrue(gb._valid_header(bytes(block)), "fixture: a genuine header first")
        block[0] ^= 0x01                                   # same octal checksum text, now wrong
        self.assertFalse(gb._valid_header(bytes(block)))
        broken = self.other.tmp / "badsum.tar"
        broken.write_bytes(two.read_bytes()[:end] + bytes(block) + b"\0" * 1024)
        _, _, err = self.other.cli("install-toolchain", "--bundle", str(broken), "--dry-run")
        self.assertIn("not valid", err)
        self.assertNotIn("does not have the expected content", err)


class SpanishMessages(BundleCase):
    """Reasons are translated keys, not raw Python or tarfile text."""

    def setUp(self):
        self.source = self.installed_sdk()
        self.bundle = self.export(self.source)
        self.other = self.offline_sdk(self.source)

    def run_es(self, bundle: Path) -> str:
        env = dict(self.other.env)
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CPCT_NEXT_PATH", None)
            import io as _io
            import contextlib as _ctx
            out, err = _io.StringIO(), _io.StringIO()
            with _ctx.redirect_stdout(out), _ctx.redirect_stderr(err), mock.patch.dict(os.environ, env):
                try:
                    glasnost.main(["--lang", "es", "install-toolchain", "--bundle", str(bundle), "--dry-run"],
                                  root=self.other.root, runner=glasnost.default_runner, interactive=False)
                except SystemExit:
                    pass
            return err.getvalue()

    def test_no_python_exception_names_in_spanish_errors(self):
        def garbage(n, d): return b"\xff\xfe not utf8" if n == gb.MANIFEST_NAME else d
        def notjson(n, d): return b"{nope" if n == gb.MANIFEST_NAME else d
        def wrong(n, d): return b'{"schema": 9}' if n == gb.MANIFEST_NAME else d
        def huge(n, d): return b"x" * (gb.MAX_MANIFEST + 1) if n == gb.MANIFEST_NAME else d
        junk = self.other.tmp / "junk.tar"
        junk.write_bytes(b"not a tar" * 100)
        cases = {"utf8": self.rewrite(self.bundle, garbage), "json": self.rewrite(self.bundle, notjson),
                 "fields": self.rewrite(self.bundle, wrong), "large": self.rewrite(self.bundle, huge), "junk": junk,
                 "missing": self.other.tmp / "nope.tar"}
        for label, path in cases.items():
            with self.subTest(label):
                text = self.run_es(path)
                self.assertTrue(text.strip())
                for leaked in ("Error:", "Exception", "codec", "field types", "schema or kind", "manifest too large",
                               "could not be opened", "Traceback"):
                    self.assertNotIn(leaked, text)
                self.assertRegex(text, r"(manifiesto|bundle)")


class Messages(unittest.TestCase):
    def test_every_bundle_message_exists_in_both_languages_with_the_same_placeholders(self):
        import glasnost_i18n as i18n
        import re
        keys = [k for k in i18n.MESSAGES["es"] if k.startswith("bundle.") or k in
                ("toolchain.step_import", "help.install_bundle", "help.export_bundle", "help.export_output")]
        self.assertGreaterEqual(len(keys), 14)
        for key in keys:
            with self.subTest(key=key):
                self.assertIn(key, i18n.MESSAGES["en"])
                self.assertEqual(set(re.findall(r"{(\w+)}", i18n.MESSAGES["es"][key])),
                                 set(re.findall(r"{(\w+)}", i18n.MESSAGES["en"][key])))

    def test_every_error_key_the_module_can_raise_is_translated(self):
        import glasnost_i18n as i18n
        source = (ROOT / "tools" / "glasnost" / "glasnost_bundle.py").read_text(encoding="utf-8")
        import re
        for key in set(re.findall(r'BundleError\(\s*"(bundle\.\w+)"', source)):
            with self.subTest(key=key):
                self.assertIn(key, i18n.MESSAGES["es"])
                self.assertIn(key, i18n.MESSAGES["en"])


if __name__ == "__main__":
    unittest.main()
