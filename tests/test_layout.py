"""The repository layout stays clean: a short first level, everything framework-specific under framework/.

Outcome of the 2026-11-09 reorganisation: `ls` at the root shows what a user needs (bin, docs, examples,
framework, projects, tests, tools) and no path in the repository still points at the old locations.
"""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TOP_DIRS = {"bin", "docs", "examples", "framework", "tests", "tools", ".github"}
TOP_FILES = {"CLAUDE.md", "Dockerfile", ".dockerignore", ".gitignore", "LICENSE", "Makefile",
             "PROJECT_STATUS.md", "README.md", "setup.sh", "toolchain.lock.json"}
FRAMEWORK_DIRS = {"src", "cfg", "profiles", "manifests", "licenses", "templates"}

# Dated history written before the move keeps the paths of its time.
HISTORY = {"PROJECT_STATUS.md", "docs/platformer-parity.md", "tests/test_layout.py"}

# A path of the old layout: framework folders at the root, as opposed to assets/src, build/<name>/src,
# examples/<name>/cfg or a user project's own folders (those have a path component before them).
OLD_PATH = re.compile(
    r"(?<![\w./$-])(?:"
    r"src/(?:core|video|ui|audio|resources|extensions)\b"
    r"|manifests/|licenses/"
    r"|profiles/(?:standard|experimental)"
    r"|templates/(?:ecs-welcome|minimal)"
    r"|cfg/(?:example\.mk|Makefile\.template|build_config\.template)"
    r"|generated/(?:standard|experimental|resources128)"
    r")")


def tracked() -> list[str]:
    return subprocess.run(["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True).stdout.split("\n")[:-1]


class Layout(unittest.TestCase):
    def test_the_first_level_is_short_and_known(self):
        top = {path.split("/")[0] for path in tracked() if "/" in path}
        self.assertEqual(top, TOP_DIRS)
        files = {path for path in tracked() if "/" not in path}
        self.assertEqual(files, TOP_FILES)

    def test_everything_framework_specific_lives_under_framework(self):
        self.assertEqual({path.split("/")[1] for path in tracked() if path.startswith("framework/")}, FRAMEWORK_DIRS)
        for old in sorted(FRAMEWORK_DIRS | {"generated"}):
            self.assertFalse((ROOT / old).is_dir() and any((ROOT / old).iterdir()), f"{old}/ is back at the root")

    def test_no_file_points_at_the_old_locations(self):
        offenders = []
        for name in tracked():
            if name in HISTORY or name.endswith((".pdf", ".png", ".dsk", ".cdt", ".bin")) or name.startswith("tools/img2cpc/"):
                continue
            try:
                text = (ROOT / name).read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for number, line in enumerate(text.splitlines(), 1):
                if OLD_PATH.search(line):
                    offenders.append(f"{name}:{number}: {line.strip()[:100]}")
        self.assertEqual(offenders, [])

    def test_the_emulator_formerly_called_mac_ape_is_only_called_bluepixel(self):
        needle = "mac" + "ape"   # built in two parts so this file does not match itself
        offenders = []
        for name in tracked():
            if name.endswith((".pdf", ".png", ".dsk", ".cdt", ".bin")) or name.startswith("tools/img2cpc/"):
                continue
            try:
                text = (ROOT / name).read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if needle in text.lower() or needle in name.lower():
                offenders.append(name)
        self.assertEqual(offenders, [])

    def test_the_install_cli_entry_stays_at_bin(self):
        """`glasnost install-cli` links to bin/glasnost; moving it would break every installed link."""
        self.assertTrue((ROOT / "bin" / "glasnost").is_file())


if __name__ == "__main__":
    unittest.main()
