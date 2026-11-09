#!/usr/bin/env python3
"""Draws the PNG sheets of docs/guide/first-game from the ASCII art below.

You do not need to run this: the PNGs are committed. It exists so the art is
readable and reproducible; any pixel editor works as well as long as every
pixel uses one of the colours of PENS (the palette of assets/palette.json).

    python3 docs/guide/first-game/make_art.py        # needs Pillow
"""

from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent

# character -> RGB. The converter matches each pixel to the nearest colour of the 16 in
# assets/palette.json using its own table, so these are the RGB values it maps to the pens the
# template uses (measured with the real tool; see the guide). Do not "fix" them to what the
# firmware calls those inks.
PENS = {
    ".": (0, 0, 0),          # pen 0, transparent when drawn
    "m": (255, 0, 255),      # pen 1
    "r": (255, 128, 0),      # pen 3
    "y": (255, 255, 0),      # pen 6
    "c": (0, 0, 255),        # pen 10
    "w": (255, 255, 255),    # pen 15
}

SHIP = [
    "...cc...",
    "..cwwc..",
    "..cwwc..",
    ".cccccc.",
    "cc.cc.cc",
    "cc.cc.cc",
    "yy....yy",
    ".y....y.",
]
SHIP2 = SHIP[:6] + [SHIP[7], SHIP[6]]          # the flames swap
DRONE = [
    "..mmmm..",
    ".mmrrmm.",
    "mmrwwrmm",
    "mmrwwrmm",
    ".mmrrmm.",
    "..mmmm..",
    ".m.mm.m.",
    "m..mm..m",
]
DRONE2 = DRONE[:6] + [DRONE[7], DRONE[6]]      # the legs swap


def sheet(tiles: list[list[str]]) -> Image.Image:
    image = Image.new("RGB", (8 * len(tiles), 8))
    for index, tile in enumerate(tiles):
        for y, row in enumerate(tile):
            for x, char in enumerate(row):
                image.putpixel((index * 8 + x, y), PENS[char])
    return image


def main() -> None:
    steps = {"step1": [SHIP, DRONE], "step2": [SHIP, SHIP2, DRONE, DRONE2]}
    for step, tiles in steps.items():
        target = HERE / step / "assets" / "src"
        target.mkdir(parents=True, exist_ok=True)
        sheet(tiles).save(target / "sprites.png", optimize=True)


if __name__ == "__main__":
    main()
