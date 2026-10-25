#!/usr/bin/env python3
"""Create a deterministic archive containing every distributable CPC artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ("minimal", "board", "platform", "gravity", "physics88", "video", "resources128", "diskload", "audio", "animation", "window", "vertical")
TEST_DISK = "GlasnostFWK-tests.dsk"
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")
ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def artifact_paths() -> list[tuple[str, Path]]:
    artifacts: list[tuple[str, Path]] = []
    for example in EXAMPLES:
        base = ROOT / ".build" / example
        manifest = json.loads(
            (ROOT / "examples" / example / "example.json").read_text(encoding="utf-8")
        )
        formats = ["bin"]
        if "cdt" in manifest.get("media", ["cdt", "dsk"]):
            formats.append("cdt")
        for suffix in formats:
            source = (
                base / "obj" / f"{example}.bin"
                if suffix == "bin"
                else base / f"{example}.{suffix}"
            )
            if not source.is_file() or source.stat().st_size == 0:
                raise FileNotFoundError(f"missing artifact: {source}")
            artifacts.append((f"examples/{example}/{example}.{suffix}", source))
    disk = ROOT / ".build" / "tests" / TEST_DISK
    if not disk.is_file() or disk.stat().st_size == 0:
        raise FileNotFoundError(f"missing artifact: {disk}")
    artifacts.append((f"tests/{TEST_DISK}", disk))
    return artifacts


def add_bytes(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    info = zipfile.ZipInfo(name, ZIP_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, data)


def package(version: str, output_dir: Path) -> tuple[Path, Path]:
    if not VERSION_RE.fullmatch(version):
        raise ValueError(f"invalid release version: {version}")

    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / f"GlasnostFWK-v{version}-cpc-artifacts.zip"
    formats_by_example = {}
    for example in EXAMPLES:
        example_manifest = json.loads(
            (ROOT / "examples" / example / "example.json").read_text(
                encoding="utf-8"
            )
        )
        formats_by_example[example] = [
            "bin",
            *(
                ["cdt"]
                if "cdt" in example_manifest.get("media", ["cdt", "dsk"])
                else []
            ),
        ]
    manifest = {
        "project": "GlasnostFWK",
        "version": version,
        "examples": list(EXAMPLES),
        "artifacts": formats_by_example,
        "test_disk": f"tests/{TEST_DISK}",
        "playable_example": "vertical",
        "run": 'RUN"VERTICAL"',
    }
    instructions = (
        "GlasnostFWK CPC examples\n"
        "========================\n\n"
        f"Load tests/{TEST_DISK} in an Amstrad CPC emulator. It contains all\n"
        "example binaries and the auxiliary diskload payloads. Run the file\n"
        "matching the example name. For the playable vertical slice use:\n\n"
        '    RUN"VERTICAL"\n\n'
        "Move with the cursor keys and collect the three dots to the right.\n"
        "The remaining examples are focused technical demonstrations.\n"
    )

    with zipfile.ZipFile(archive_path, "w") as archive:
        add_bytes(archive, "README.txt", instructions.encode("utf-8"))
        add_bytes(
            archive,
            "manifest.json",
            (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        )
        for name, source in artifact_paths():
            add_bytes(archive, name, source.read_bytes())

    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    checksums_path = output_dir / "SHA256SUMS"
    checksums_path.write_text(f"{digest}  {archive_path.name}\n", encoding="ascii")
    return archive_path, checksums_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", required=True)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    archive, checksums = package(args.version, args.output_dir)
    print(archive)
    print(checksums)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
