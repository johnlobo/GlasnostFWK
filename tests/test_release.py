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
            for example in package_release.EXAMPLES:
                (build / example / "obj").mkdir(parents=True)
                (build / example / "obj" / f"{example}.bin").write_bytes(
                    f"{example}-bin".encode()
                )
                (build / example / f"{example}.cdt").write_bytes(
                    f"{example}-cdt".encode()
                )
                (build / example / f"{example}.dsk").write_bytes(
                    f"{example}-dsk".encode()
                )

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
            self.assertEqual(len(names), 20)
            self.assertIn("README.txt", names)
            self.assertIn("manifest.json", names)
            self.assertIn("examples/vertical/vertical.dsk", names)


if __name__ == "__main__":
    unittest.main()
