import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from tools.dev import package_release


class ReleasePackageTests(unittest.TestCase):
    def test_rejects_invalid_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "invalid release version"):
                package_release.package("v1", Path(directory))

    def test_archive_is_deterministic_and_complete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build = root / "build"
            examples = root / "examples"
            for example in package_release.PROGRAMS:
                source_root = examples if example in package_release.EXAMPLES else root / "framework" / "validations"
                (source_root / example).mkdir(parents=True)
                media = ["dsk"] if example in {"diskload", "perf"} else ["cdt", "dsk"]
                example_manifest = {"media": media}
                if example == "platformer":
                    example_manifest["amsdos_name"] = "PLATGAME"
                (source_root / example / "example.json").write_text(
                    json.dumps(example_manifest) + "\n",
                    encoding="utf-8",
                )
                (build / example / "obj").mkdir(parents=True)
                (build / example / "obj" / f"{example}.bin").write_bytes(
                    f"{example}-bin".encode()
                )
                if "cdt" in media:
                    (build / example / f"{example}.cdt").write_bytes(
                        f"{example}-cdt".encode()
                    )
            (build / "tests").mkdir()
            (build / "tests" / package_release.TEST_DISK).write_bytes(b"shared-dsk")

            first = root / "first"
            second = root / "second"
            with patch.object(package_release, "ROOT", root):
                archive1, sums1 = package_release.package("1.2.3", first)
                archive2, _ = package_release.package("1.2.3", second)

            self.assertEqual(archive1.read_bytes(), archive2.read_bytes())
            digest = hashlib.sha256(archive1.read_bytes()).hexdigest()
            self.assertEqual(
                sums1.read_text(encoding="ascii"),
                f"{digest}  {archive1.name}\n",
            )
            with zipfile.ZipFile(archive1) as archive:
                names = archive.namelist()
                release_manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(len(names), 45)
            self.assertIn("README.txt", names)
            self.assertIn("manifest.json", names)
            self.assertIn(f"tests/{package_release.TEST_DISK}", names)
            self.assertEqual(release_manifest["run_names"]["platformer"], "PLATGAME")
            self.assertEqual(release_manifest["examples"], list(package_release.EXAMPLES))
            self.assertEqual(release_manifest["validations"], list(package_release.VALIDATIONS))
            self.assertFalse(any("vertical" in name for name in names))
            self.assertIn("framework/validations/ecsrender/ecsrender.bin", names)
            self.assertNotIn("examples/ecsrender/ecsrender.bin", names)
            self.assertNotIn("examples/diskload/diskload.dsk", names)
            self.assertNotIn("examples/diskload/diskload.cdt", names)
            self.assertNotIn("framework/validations/perf/perf.cdt", names)


if __name__ == "__main__":
    unittest.main()
