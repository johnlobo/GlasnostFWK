#!/usr/bin/env python3
"""Stage only requested framework modules and build examples with CPCTelera Next."""

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


def stage_example(name: str, cpct_path: Path) -> Path:
    example = ROOT / "examples" / name
    if not example.is_dir():
        raise ValueError(f"unknown example: {name}")
    manifest = json.loads((example / "example.json").read_text(encoding="utf-8"))
    target = ROOT / ".build" / name
    if target.exists():
        shutil.rmtree(target)
    (target / "src" / "game").mkdir(parents=True)
    (target / "cfg").mkdir(parents=True)
    game_sources = manifest.get("game_sources", ["main.s"])
    if not game_sources or "main.s" not in game_sources:
        raise ValueError(f"{name}: game_sources must include main.s")
    for relative in game_sources:
        relative_path = Path(relative)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError(f"{name}: unsafe game source {relative}")
        source = example / relative_path
        if not source.is_file() or source.suffix not in {".s", ".inc"}:
            raise ValueError(f"{name}: invalid game source {relative}")
        destination = target / "src" / "game" / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    for relative in manifest["modules"]:
        source = ROOT / "src" / relative
        if not source.is_file():
            raise ValueError(f"{name}: missing module {relative}")
        destination = target / "src" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        include = source.with_suffix(".inc")
        if include.is_file():
            shutil.copy2(include, destination.with_suffix(".inc"))
    generated = target / "generated"
    subprocess.run(
        [
            "python3", str(ROOT / "tools" / "gen_video.py"),
            str(ROOT / "profiles" / manifest["profile"]),
            "--out-dir", str(generated),
        ],
        check=True,
    )
    profile_name = Path(manifest["profile"]).stem
    shutil.copy2(generated / f"{profile_name}.inc", target / "src" / "video_config.inc")
    makefile = (ROOT / "cfg" / "Makefile.template").read_text(encoding="utf-8")
    (target / "Makefile").write_text(makefile, encoding="utf-8")
    config = (ROOT / "cfg" / "build_config.template.mk").read_text(encoding="utf-8")
    config = re.sub(
        r"^CPCT_PATH\s*:=.*$",
        f"CPCT_PATH      := {cpct_path}/",
        config,
        flags=re.MULTILINE,
    )
    config = re.sub(r"^PROJNAME\s*:=.*$", f"PROJNAME   := {name}", config, flags=re.MULTILINE)
    config = re.sub(r"^TARGET\s*:=.*$", "TARGET  := $(CDT) $(DSK)", config, flags=re.MULTILINE)
    config = config.replace("Z80CODELOC := 0x4000", "Z80CODELOC := 0x4000")
    config = config.replace("Z80CCINCLUDE  := -I$(CPCT_SRC)", "Z80CCINCLUDE  := -I$(CPCT_SRC) -I$(SRCDIR)")
    (target / "cfg" / "build_config.mk").write_text(config, encoding="utf-8")
    (target / "selected-modules.json").write_text(
        json.dumps(
            {
                "example": name,
                "game_sources": game_sources,
                "modules": manifest["modules"],
                "cpct_path": str(cpct_path),
            },
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    return target


def build(name: str, cpct_path: Path) -> None:
    if not (cpct_path / "cpctelera.lib").is_file():
        raise ValueError(f"invalid CPCT_PATH: {cpct_path}")
    target = stage_example(name, cpct_path)
    env = os.environ.copy()
    env["CPCT_PATH"] = str(cpct_path)
    subprocess.run(["make", "--no-print-directory"], cwd=target, env=env, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("examples", nargs="*", help="example names; default: all")
    parser.add_argument("--cpct-path", type=Path, default=Path(os.environ.get("CPCT_NEXT_PATH", DEFAULT_CPCT)))
    args = parser.parse_args()
    names = args.examples or sorted(path.name for path in (ROOT / "examples").iterdir() if (path / "example.json").is_file())
    for name in names:
        print(f"== building {name} ==", flush=True)
        build(name, args.cpct_path.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
