#!/usr/bin/env python3
import importlib.util
import json
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gen_resources", ROOT / "tools" / "gen_resources.py")
GEN = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(GEN)


class ResourceTests(unittest.TestCase):
    def base(self):
        return json.loads((ROOT / "manifests" / "resources128.json").read_text())

    def test_example_manifest_is_valid(self):
        self.assertEqual(len(GEN.validate(self.base())), 2)

    def test_rejects_bank_overlap(self):
        data = self.base()
        item = deepcopy(data["resources"][0])
        item["id"] = "overlap"
        item["bank_offset"] = "0x0010"
        item["destination"] = "0x9400"
        data["resources"].append(item)
        with self.assertRaisesRegex(ValueError, "overlaps demo_sprite"):
            GEN.validate(data)

    def test_rejects_reserved_destination(self):
        data = self.base()
        data["resources"][0]["destination"] = "0xC000"
        with self.assertRaisesRegex(ValueError, "reserved region screen"):
            GEN.validate(data)

    def test_64k_rejects_extra_bank(self):
        data = self.base()
        data["profile"] = "64k"
        with self.assertRaisesRegex(ValueError, "unavailable"):
            GEN.validate(data)


if __name__ == "__main__":
    unittest.main()
