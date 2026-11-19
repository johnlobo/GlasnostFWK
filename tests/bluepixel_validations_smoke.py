#!/usr/bin/env python3
"""Validaciones disksave y uiinput en el adaptador stdio de BluePixel.

disksave: fwk_disk_save escribe SAVED.DAT con el firmware apagado; el disco exportado
se lee aquí y se comprueba byte a byte (y que AMSDOS dejó la versión anterior en .BAK).
uiinput: fwk_text_draw_centered / fwk_text_draw_clear en VRAM y los intervalos de
fwk_input_repeat con una tecla mantenida.

    python3 tests/bluepixel_validations_smoke.py --emulator BIN --rom-dir DIR
"""
from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/glasnost"))
from bluepixel_adapter import BluePixel


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def amsdos_files(image: bytes) -> dict[str, bytes]:
    """Files of a DATA format DSK (standard or EXTENDED), as stored (128-byte records)."""
    extended = image[:8] == b"EXTENDED"
    require(extended or image[:8] == b"MV - CPC", "no es una imagen DSK")
    tracks, sides = image[0x30], image[0x31]
    fixed = image[0x32] | image[0x33] << 8
    sectors: dict[tuple[int, int], int] = {}
    offset = 0x100
    for index in range(tracks * sides):
        size = image[0x34 + index] * 256 if extended else fixed
        if not size:
            continue
        track, side, count = image[offset + 0x10], image[offset + 0x11], image[offset + 0x15]
        data = offset + 0x100
        for s in range(count):
            info = offset + 0x18 + s * 8
            length = (image[info + 6] | image[info + 7] << 8) if extended else 128 << image[info + 3]
            if side == 0:
                sectors[(track, image[info + 2])] = data
            data += length
        offset += size

    def sector(n: int) -> bytes:
        at = sectors[(n // 9, 0xC1 + n % 9)]
        return image[at:at + 512]

    directory = b"".join(sector(n) for n in range(4))
    extents: dict[str, list[tuple[int, int, list[int]]]] = {}
    for i in range(64):
        entry = directory[i * 32:(i + 1) * 32]
        if entry[0] > 15:
            continue
        base = bytes(c & 0x7F for c in entry[1:9]).decode().strip()
        ext = bytes(c & 0x7F for c in entry[9:12]).decode().strip()
        name = f"{base}.{ext}" if ext else base
        extents.setdefault(name, []).append((entry[12] | entry[14] << 5, entry[15], [b for b in entry[16:] if b]))
    files = {}
    for name, parts in extents.items():
        data = b""
        for _, records, blocks in sorted(parts):
            chunk = b"".join(sector(b * 2) + sector(b * 2 + 1) for b in blocks)
            data += chunk[:records * 128]
        files[name] = data
    return files


def run_until(emu: BluePixel, address: str, codes: set[int], *, limit: int = 4000) -> int:
    """Waits for one of the program's status codes (the RAM holds BASIC data before the load)."""
    for _ in range(0, limit, 10):
        emu.run(10)
        value = emu.read(address)[0]
        if value in codes:
            return value
    raise RuntimeError(f"{address} sin código de estado tras {limit} fotogramas")


def disksave(emulator: Path, rom_dir: Path) -> None:
    build = ROOT / "build/disksave"
    with BluePixel(emulator, rom_dir) as emu:
        emu.load(build / "disksave.dsk", build / "obj/disksave.noi")
        emu.run(150)
        emu.call("input.text", {"text": 'run"disksave\n'})
        status = run_until(emu, "disksave_status", {0x5A, 0xE1, 0xE2, 0xE3, 0xE4})
        require(status == 0x5A, f"disksave_status = 0x{status:02X}")
        image = base64.b64decode(emu.call("disc.export", {"drive": 0})["data_base64"])
    files = amsdos_files(image)
    for name, first in (("SAVED.DAT", 1), ("SAVED.BAK", 0)):
        require(name in files, f"falta {name}: {sorted(files)}")
        data = files[name]
        header, body = data[:128], data[128:128 + 300]
        require(sum(header[:67]) & 0xFFFF == header[67] | header[68] << 8, f"{name}: cabecera AMSDOS no válida")
        require(header[18] == 2 and header[64] | header[65] << 8 == 300, f"{name}: tipo o longitud")
        expected = bytes((i * 3 + first) & 0xFF for i in range(300))
        require(body == expected, f"{name}: contenido distinto")
    print("disksave: ok")


def screen(emu: BluePixel, x: int, y: int, length: int) -> bytes:
    return emu.read(0xC000 + (y & 7) * 0x800 + (y >> 3) * 80 + x, length)


def uiinput(emulator: Path, rom_dir: Path) -> None:
    build = ROOT / "build/uiinput"
    with BluePixel(emulator, rom_dir) as emu:
        emu.load(build / "uiinput.dsk", build / "obj/uiinput.noi")
        emu.boot('run"uiinput', "uiinput_ready", 0x5A)
        rows = [screen(emu, 0, y, 80) for y in range(9)]
        require(any(any(row[38:42]) for row in rows), '"AB" no está en los bytes 38..41')
        require(not any(any(row[:38]) or any(row[42:]) for row in rows), '"AB" fuera de los bytes 38..41')
        rows = [screen(emu, 0, 16 + y, 80) for y in range(9)]
        require(any(any(row[0:2]) for row in rows), '"A" no se dibujó')
        require(not any(any(row[2:]) for row in rows), "fwk_text_draw_clear dejó restos de WXYZ")

        emu.run(5)
        require(emu.read("uiinput_log_count")[0] == 0, "repetición sin tecla")
        emu.key(0, 0xFD, True)                 # Key_CursorRight: fila 0, bit 1 a 0
        emu.run(40)
        emu.key(0, 0xFD, False)
        emu.run(20)
        count = emu.read("uiinput_log_count")[0]
        require(count, "fwk_input_repeat nunca distinto de 0")
        log = emu.read("uiinput_log", count)
    gaps = [(b - a) & 0xFF for a, b in zip(log, log[1:])]
    # 40 frames held: the press (frame 0), then 15, 19, 23, 27, 31, 35 and 39.
    require(gaps == [15, 4, 4, 4, 4, 4, 4], f"intervalos de repetición {gaps}")
    print("uiinput: ok")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom-dir", type=Path, required=True)
    parser.add_argument("programs", nargs="*", default=["disksave", "uiinput"])
    args = parser.parse_args()
    for name in args.programs:
        {"disksave": disksave, "uiinput": uiinput}[name](args.emulator, args.rom_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
