#!/usr/bin/env python3
"""Report linked code/data sizes without confusing sparse ABS examples with RAM."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def area_size(map_text: str, area: str) -> int:
    match = re.search(rf"^{re.escape(area)}\s+[0-9A-F]+\s+([0-9A-F]+)", map_text, re.MULTILINE)
    return int(match.group(1), 16) if match else 0


def main() -> int:
    rows = []
    for manifest in sorted((ROOT / "examples").glob("*/example.json")):
        name = manifest.parent.name
        obj = ROOT / ".build" / name / "obj"
        map_path = obj / f"{name}.map"
        bin_path = obj / f"{name}.bin"
        if not map_path.is_file() or not bin_path.is_file():
            raise SystemExit(f"build {name} first")
        text = map_path.read_text(errors="replace")
        rows.append((name, area_size(text, "_CODE"), area_size(text, "_DATA"), bin_path.stat().st_size))
    out = [
        "# Example build sizes", "",
        "Generated from SDCC linker maps. Binary size may include sparse absolute-address padding.", "",
        "| Example | Linked code | Linked data | BIN bytes |", "|---|---:|---:|---:|",
    ]
    out += [f"| {name} | {code} | {data} | {binary} |" for name, code, data, binary in rows]
    out += ["", "No cycle/frame-rate value is reported: no emulator timing run was completed.", ""]
    destination = ROOT / "docs" / "build-sizes.md"
    destination.write_text("\n".join(out), encoding="utf-8")
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
