#!/usr/bin/env python3
"""Open the image built for one example in an external CPC emulator.

The emulator is never bundled: pick it with --emulator, with the
GLASNOST_EMULATOR environment variable, with `make run GLASNOST_EMULATOR=...`
or let the tool find AmSpiriT-Lite next to the repository, as the optional
smoke test does. When no emulator is available the image path is printed so it
can be opened by hand.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import emulator_setup  # noqa: E402
sys.path.insert(0, str(ROOT / "tools" / "build"))
from program_catalog import program_folder  # noqa: E402
DEFAULT_EMULATOR = ROOT.parent / "tools" / "amspirit-lite" / "run.sh"
EMULATOR_COMMANDS = ("amspirit-lite", "amspirit", "bluepixel")
BLUEPIXEL_CANDIDATES = (
    Path("/Applications/BluePixel.app/Contents/MacOS/BluePixel"),
    Path.home() / "Applications" / "BluePixel.app" / "Contents" / "MacOS" / "BluePixel",
)


def project_name(example: str, folder: Path | None = None) -> str:
    manifest = (folder or program_folder(ROOT, example)) / "example.json"
    if not manifest.is_file():
        raise SystemExit(f"No existe el ejemplo {example}: falta {manifest}")
    return json.loads(manifest.read_text(encoding="utf-8"))["name"]


def example_images(name: str, build_dir: Path | None = None) -> list[Path]:
    """The CDT and DSK of `name`. `build_dir` is the folder that holds them: build/<name> for an
    example of the SDK, <project>/build for a glasnost project (which builds straight into build/)."""
    build = build_dir or ROOT / "build" / name
    return [build / f"{name}.cdt", build / f"{name}.dsk"]


def select_image(name: str, requested: str | None, build_dir: Path | None = None, project: bool = False,
                 prefer: str | None = None) -> Path:
    """The image to open: the requested format, else `prefer`, else the CDT, else the DSK."""
    build_dir = build_dir or ROOT / "build" / name
    how = "ejecute `glasnost build`" if project else f"ejecute `make` en {program_folder(ROOT, name)}"
    images = example_images(name, build_dir)
    if prefer == "dsk":
        images.reverse()
    available = [path for path in images if path.is_file()]
    if not available:
        raise SystemExit(f"No hay imagen construida para {name}: {how}.")
    if requested is not None:
        wanted = build_dir / f"{name}.{requested}"
        if not wanted.is_file():
            formats = ", ".join(path.suffix.lstrip(".") for path in available)
            raise SystemExit(f"No hay imagen .{requested} construida para {name}; disponibles: {formats}. {how.capitalize()}.")
        return wanted
    # CDT first unless the emulator starts discs by itself: the tape made by 2cdt autoruns, while a
    # DSK needs RUN" typed by hand, which BluePixel (/A) and RVM (-c=RUN"...") do for us.
    return available[0]


def find_emulator(explicit: str | None) -> str | None:
    """--emulator, GLASNOST_EMULATOR, the emulator saved by `glasnost run`/`glasnost emulator`,
    then whatever can be found on this machine (so `make run` keeps working unattended)."""
    candidate = explicit or os.environ.get("GLASNOST_EMULATOR", "").strip()
    if candidate:
        path = Path(candidate).expanduser()
        if not path.is_file():
            raise SystemExit(f"El emulador indicado no existe: {path}")
        return str(path)
    saved = emulator_setup.configured(ROOT)
    if saved:
        return str(saved)
    if DEFAULT_EMULATOR.is_file():
        return str(DEFAULT_EMULATOR)
    for command in EMULATOR_COMMANDS:
        found = shutil.which(command)
        if found:
            return found
    for candidate in BLUEPIXEL_CANDIDATES:
        if candidate.is_file():
            return str(candidate)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("example", nargs="?", help="nombre del ejemplo, por ejemplo minimal")
    parser.add_argument("--project", type=Path, help="carpeta de un proyecto glasnost en vez de un ejemplo")
    parser.add_argument("--emulator", help="ejecutable del emulador a usar")
    parser.add_argument(
        "--image",
        choices=("cdt", "dsk"),
        help="formato a abrir; por defecto CDT si existe y DSK si no",
    )
    parser.add_argument(
        "--print-path",
        action="store_true",
        help="solo mostrar la imagen seleccionada, sin abrir emulador",
    )
    args = parser.parse_args()

    if args.project:
        folder = args.project.resolve()
        build_dir = folder / "build"
        name = project_name(folder.name, folder)
    elif args.example:
        folder = None
        name = project_name(args.example)
        build_dir = ROOT / "build" / name
    else:
        parser.error("indique un ejemplo o --project")
    emulator = find_emulator(args.emulator)
    image = select_image(name, args.image, build_dir, project=folder is not None,
                         prefer=emulator_setup.preferred_image(emulator, ROOT))

    if args.print_path or emulator is None:
        if emulator is None and not args.print_path:
            print(
                "No se encontró ningún emulador. Abra la imagen anterior, configure uno con "
                "`glasnost emulator` o indique uno con `make run GLASNOST_EMULATOR=/ruta/al/emulador`.",
                file=sys.stderr,
            )
        print(image)
        return 0

    command = emulator_setup.build_command(emulator, image, build_dir, name, ROOT)
    print(shlex.join(command))   # the full command line, so a launch that does nothing can be debugged
    return subprocess.run(command).returncode


if __name__ == "__main__":
    raise SystemExit(main())
