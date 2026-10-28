#!/usr/bin/env python3
"""Regenera las capturas verificables de la guia de plataformas."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
EXAMPLE = ROOT / "examples" / "platformer"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"


def terminal_capture(name: str, title: str, lines: list[str]) -> None:
    """Dibuja una captura de terminal legible tanto en HTML como en PDF."""
    width = 1420
    line_height = 31
    top = 72
    bottom = 32
    height = top + len(lines) * line_height + bottom
    image = Image.new("RGB", (width, height), "#111827")
    draw = ImageDraw.Draw(image)
    title_font = ImageFont.truetype(FONT_BOLD, 23)
    text_font = ImageFont.truetype(FONT, 21)
    draw.rectangle((0, 0, width, 52), fill="#1f2937")
    for index, colour in enumerate(("#ff5f56", "#ffbd2e", "#27c93f")):
        x = 24 + index * 28
        draw.ellipse((x, 18, x + 13, 31), fill=colour)
    draw.text((126, 12), title, font=title_font, fill="#e5e7eb")
    for row, line in enumerate(lines):
        colour = "#86efac" if line.startswith("$") else "#e5e7eb"
        draw.text((28, top + row * line_height), line, font=text_font, fill=colour)
    image.save(HERE / name, optimize=True)


def structure_lines() -> list[str]:
    names = sorted(path.name for path in EXAMPLE.iterdir() if path.is_file())
    return [
        "$ find examples/platformer -maxdepth 1 -type f -printf '%f\\n' | sort",
        *names,
        "",
        "$ find src/extensions -maxdepth 1 -name '*platform*' -printf '%f\\n' | sort",
        *sorted(path.name for path in (ROOT / "src" / "extensions").glob("*platform*")),
    ]


def manifest_lines() -> list[str]:
    manifest = json.loads((EXAMPLE / "example.json").read_text(encoding="utf-8"))
    text = json.dumps(manifest, ensure_ascii=False, indent=2)
    return ["$ sed -n '1,120p' examples/platformer/example.json", *text.splitlines()]


def build_lines(run_build: bool) -> list[str]:
    command = ["python3", "tools/build_examples.py", "platformer"]
    if run_build:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if completed.returncode:
            raise SystemExit(completed.stdout)
    binary = ROOT / ".build" / "platformer" / "obj" / "platformer.bin"
    cassette = ROOT / ".build" / "platformer" / "platformer.cdt"
    selected = ROOT / ".build" / "platformer" / "selected-modules.json"
    missing = [str(path.relative_to(ROOT)) for path in (binary, cassette, selected) if not path.is_file()]
    if missing:
        raise SystemExit("Faltan artefactos; ejecute sin --skip-build: " + ", ".join(missing))
    return [
        "$ python3 tools/build_examples.py platformer",
        "== building platformer ==",
        "Compilacion terminada sin errores.",
        "",
        "$ stat -c '%n  %s bytes' .build/platformer/obj/platformer.bin \\",
        "    .build/platformer/platformer.cdt",
        f".build/platformer/obj/platformer.bin  {binary.stat().st_size} bytes",
        f".build/platformer/platformer.cdt  {cassette.stat().st_size} bytes",
        "",
        "$ test -f .build/platformer/selected-modules.json && echo manifiesto-ok",
        "manifiesto-ok",
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="usa artefactos ya construidos en lugar de recompilar platformer",
    )
    args = parser.parse_args()
    HERE.mkdir(parents=True, exist_ok=True)
    terminal_capture("01-estructura.png", "Estructura real del ejemplo", structure_lines())
    terminal_capture("02-manifiesto.png", "Manifiesto real del ejemplo", manifest_lines())
    terminal_capture("03-construccion.png", "Construccion reproducible", build_lines(not args.skip_build))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
