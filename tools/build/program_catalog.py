"""Discover public examples and internal CPC validations from their manifests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KINDS = {"examples": Path("examples"), "validations": Path("framework/validations")}


def program_folders(root: Path, kind: str = "all") -> list[Path]:
    kinds = KINDS if kind == "all" else {kind: KINDS[kind]}
    folders = sorted(
        (manifest.parent for relative in kinds.values()
         for manifest in (root / relative).glob("*/example.json")),
        key=lambda folder: folder.name,
    )
    names = [folder.name for folder in folders]
    if len(names) != len(set(names)):
        raise ValueError("duplicate program names across examples and validations")
    return folders


def program_names(root: Path, kind: str = "all", media: str | None = None) -> tuple[str, ...]:
    return tuple(
        folder.name for folder in program_folders(root, kind)
        if media in (None, "bin") or media in
        json.loads((folder / "example.json").read_text()).get("media", ["cdt", "dsk"])
    )


def program_folder(root: Path, name: str) -> Path:
    if not name or Path(name).name != name or name in {".", ".."}:
        raise ValueError(f"invalid program name: {name!r}")
    matches = [root / relative / name for relative in KINDS.values()
               if (root / relative / name / "example.json").is_file()]
    if len(matches) > 1:
        raise ValueError(f"duplicate program name: {name}")
    # Preserve the missing-manifest diagnostic and AMSDOS fallback of callers.
    return matches[0] if matches else root / "examples" / name


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=["all", *KINDS], nargs="?", default="all")
    parser.add_argument("--media", choices=["bin", "cdt", "dsk"])
    args = parser.parse_args()
    print(" ".join(program_names(ROOT, args.kind, args.media)))


if __name__ == "__main__":
    main()
