#!/usr/bin/env python3
"""Build the single DSK used to run every framework example."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CPCT = Path("/config/workspace/cpctelera_next/cpctelera")
DEFAULT_EXAMPLES = (
    "minimal",
    "board",
    "platform",
    "gravity",
    "physics88",
    "tilecoll",
    "tilerender",
    "spriteclip",
    "spritemask",
    "renderorder",
    "video",
    "resources128",
    "diskload",
    "audio",
    "animation",
    "window",
    "vertical",
    "perf",
    "collision",
    "tilemask",
    "experimental",
)
DISK_NAME = "GlasnostFWK-tests.dsk"
ADDRESS_RE = re.compile(
    r"^(Load Address|Run\s+Address)\s*=\s*(?:0x)?([0-9A-Fa-f]+)", re.MULTILINE
)


def amsdos_bin_name(example: str) -> str:
    stem = example.upper()
    if not stem or len(stem) > 8 or not stem.replace("_", "A").isalnum():
        stem = stem[:8]
    if not stem or not stem.replace("_", "A").isalnum():
        raise ValueError(f"cannot derive AMSDOS name from example: {example}")
    return f"{stem}.BIN"


def binary_addresses(log: Path) -> tuple[str, str]:
    if not log.is_file():
        raise FileNotFoundError(f"missing binary build log: {log}")
    values = {
        "Run Address" if label.startswith("Run") else label: f"{int(value, 16):04X}"
        for label, value in ADDRESS_RE.findall(log.read_text())
    }
    try:
        return values["Load Address"], values["Run Address"]
    except KeyError as error:
        raise ValueError(f"missing load/run address in: {log}") from error


def collect_entries(root: Path, examples: tuple[str, ...]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    names: set[str] = set()
    for example in examples:
        source = root / ".build" / example / "obj" / f"{example}.bin"
        if not source.is_file() or source.stat().st_size == 0:
            raise FileNotFoundError(f"missing example binary: {source}")
        name = amsdos_bin_name(example)
        if name in names:
            raise ValueError(f"duplicate AMSDOS filename: {name}")
        load, run = binary_addresses(source.parent / "binaryAddresses.log")
        names.add(name)
        entries.append(
            {
                "name": name,
                "source": str(source.relative_to(root)),
                "kind": "program",
                "load": load,
                "run": run,
            }
        )

        selected = root / ".build" / example / "selected-modules.json"
        if not selected.is_file():
            raise FileNotFoundError(f"missing build manifest: {selected}")
        build_manifest = json.loads(selected.read_text(encoding="utf-8"))
        for payload in build_manifest.get("disk_files", []):
            payload_name = payload["name"]
            payload_source = root / ".build" / example / "dsk" / payload_name
            if payload_name in names:
                raise ValueError(f"duplicate AMSDOS filename: {payload_name}")
            if not payload_source.is_file() or payload_source.stat().st_size == 0:
                raise FileNotFoundError(f"missing disk payload: {payload_source}")
            names.add(payload_name)
            entries.append(
                {
                    "name": payload_name,
                    "source": str(payload_source.relative_to(root)),
                    "kind": "payload",
                }
            )
    return entries


def build_test_disk(
    root: Path, cpct_path: Path, examples: tuple[str, ...], remove_individual: bool
) -> Path:
    idsk = cpct_path / "tools" / "iDSK-0.13" / "bin" / "iDSK"
    if not idsk.is_file():
        raise FileNotFoundError(f"missing iDSK: {idsk}")
    entries = collect_entries(root, examples)
    output = root / ".build" / "tests"
    stage = output / "files"
    if output.exists():
        shutil.rmtree(output)
    stage.mkdir(parents=True)
    disk = output / DISK_NAME
    subprocess.run([str(idsk), str(disk), "-n"], check=True)
    for entry in entries:
        staged = stage / entry["name"]
        shutil.copy2(root / entry["source"], staged)
        command = [str(idsk), str(disk), "-i", str(staged), "-t", "1", "-f"]
        if entry["kind"] == "program":
            command[4:4] = ["-e", entry["run"], "-c", entry["load"]]
        subprocess.run(command, check=True)
    (output / "catalog.json").write_text(
        json.dumps({"disk": DISK_NAME, "entries": entries}, indent=2) + "\n",
        encoding="utf-8",
    )
    shutil.rmtree(stage)
    if remove_individual:
        for example in examples:
            individual = root / ".build" / example / f"{example}.dsk"
            if individual.exists():
                individual.unlink()
    return disk


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("examples", nargs="*", default=list(DEFAULT_EXAMPLES))
    parser.add_argument(
        "--cpct-path",
        type=Path,
        default=Path(os.environ.get("CPCT_NEXT_PATH", DEFAULT_CPCT)),
    )
    parser.add_argument("--keep-individual", action="store_true")
    args = parser.parse_args()
    disk = build_test_disk(
        ROOT,
        args.cpct_path.resolve(),
        tuple(args.examples),
        remove_individual=not args.keep_individual,
    )
    print(disk)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
