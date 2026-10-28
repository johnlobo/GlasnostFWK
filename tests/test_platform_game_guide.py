import hashlib
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GuideParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.images: list[str] = []
        self.internal_links: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        values = dict(attrs)
        if "id" in values:
            self.ids.add(values["id"])
        if tag == "img" and "src" in values:
            self.images.append(values["src"])
        if tag == "a" and values.get("href", "").startswith("#"):
            self.internal_links.append(values["href"][1:])


class PlatformGameGuideTests(unittest.TestCase):
    def setUp(self) -> None:
        self.html_path = ROOT / "docs/platform-game-guide.html"
        self.pdf_path = ROOT / "docs/platform-game-guide.pdf"
        self.html = self.html_path.read_text(encoding="utf-8")
        self.parser = GuideParser()
        self.parser.feed(self.html)

    def test_links_and_five_reproducible_captures_are_present(self) -> None:
        self.assertEqual(set(self.parser.internal_links) - self.parser.ids, set())
        self.assertEqual(len(self.parser.images), 5)
        for relative in self.parser.images:
            image = self.html_path.parent / relative
            self.assertTrue(image.is_file(), image)
            self.assertTrue(image.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
            self.assertGreater(image.stat().st_size, 10_000)
        self.assertIn("generate_captures.py", self.html)
        self.assertIn("--screenshot-dir docs/images/platformer", self.html)

    def test_pdf_matches_the_current_guide_shape(self) -> None:
        self.assertTrue(self.pdf_path.read_bytes().startswith(b"%PDF-"))
        self.assertGreater(self.pdf_path.stat().st_size, 100_000)
        checksum = (ROOT / "docs/platform-game-guide.sha256").read_text(
            encoding="ascii"
        )
        match = re.fullmatch(
            r"([0-9a-f]{64})  platform-game-guide\.html\n", checksum
        )
        self.assertIsNotNone(match)
        self.assertEqual(
            match.group(1), hashlib.sha256(self.html_path.read_bytes()).hexdigest()
        )


if __name__ == "__main__":
    unittest.main()
