import hashlib
import json
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class CoverageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.examples = set()
        self.modules = set()

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if "data-example" in values:
            self.examples.add(values["data-example"])
        if "data-module" in values:
            self.modules.add(values["data-module"])


class ManualTests(unittest.TestCase):
    def setUp(self):
        self.html_path = ROOT / "docs" / "manual.html"
        self.pdf_path = ROOT / "docs" / "manual.pdf"
        parser = CoverageParser()
        parser.feed(self.html_path.read_text(encoding="utf-8"))
        self.coverage = parser

    def test_manual_covers_every_example_and_framework_module(self):
        examples = {path.parent.name for path in (ROOT / "examples").glob("*/example.json")}
        modules = set()
        for path in (ROOT / "examples").glob("*/example.json"):
            manifest = json.loads(path.read_text(encoding="utf-8"))
            modules.update(manifest["modules"])
        self.assertEqual(examples, self.coverage.examples)
        self.assertEqual(modules, self.coverage.modules)

    def test_pdf_matches_current_html_source(self):
        self.assertTrue(self.pdf_path.read_bytes().startswith(b"%PDF-"))
        self.assertGreater(self.pdf_path.stat().st_size, 10_000)
        checksum = (ROOT / "docs" / "manual.sha256").read_text(encoding="ascii")
        match = re.fullmatch(r"([0-9a-f]{64})  manual\.html\n", checksum)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), hashlib.sha256(self.html_path.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
