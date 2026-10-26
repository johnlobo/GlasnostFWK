import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from tools import package_release


class ReleasePackageTests(unittest.TestCase):
    def test_rejects_invalid_version(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "invalid release version"):
                package_release.package("v1", Path(directory))

    def test_archive_is_deterministic_and_complete(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build = root / ".build"
            examples = root / "examples"
            for example in package_release.EXAMPLES:
                (examples / example).mkdir(parents=True)
                media = ["dsk"] if example == "diskload" else ["cdt", "dsk"]
                (examples / example / "example.json").write_text(
                    '{"media": ' + str(media).replace("'", '"') + "}\n",
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
            self.assertEqual(len(names), 32)
            self.assertIn("README.txt", names)
            self.assertIn("manifest.json", names)
            self.assertIn(f"tests/{package_release.TEST_DISK}", names)
            self.assertNotIn("examples/vertical/vertical.dsk", names)
            self.assertNotIn("examples/diskload/diskload.dsk", names)
            self.assertNotIn("examples/diskload/diskload.cdt", names)


if __name__ == "__main__":
    unittest.main()
