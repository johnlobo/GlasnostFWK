#!/usr/bin/env python3
"""Prueba real de nave con el adaptador stdio de BluePixel, sin esperas de reloj."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/glasnost"))
sys.path.insert(0, str(ROOT / "tools/build"))
from bluepixel_adapter import BluePixel
from build_test_disk import program_bin_name


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def run_once(binary: Path, rom_dir: Path, disk: Path, symbols: Path):
    started = time.perf_counter()
    with BluePixel(binary, rom_dir) as emu:
        emu.load(disk, symbols)
        emu.boot('run"' + program_bin_name(ROOT, "nave"), "game_status", 0x5A)
        boot_seconds = time.perf_counter() - started
        frame = emu.read("fwk_system_frame_count", 2)
        drone = emu.read("game_storage + 37", 37)
        emu.run(60)
        require(emu.read("fwk_system_frame_count", 2) != frame, "El contador del juego no avanza")
        require(emu.read("game_storage + 37", 37) != drone, "El drone no se mueve/anima")

        # Inspect the background before moving the ship onto y=192: its 8-line
        # sprite then overlaps scanline 199 and may legitimately draw zero bytes.
        ground = emu.read(0xC000 + (199 & 7) * 0x800 + (199 >> 3) * 80, 80)
        require(all(ground), f"El mapa no dibuja el suelo en la última línea: {ground.hex()}")

        def boundary(row, mask, axis, target, limit):
            emu.key(row, mask, True)
            try:
                for _ in range(0, limit, 5):
                    emu.run(5)
                    if emu.read(f"game_storage + {axis}")[0] == target:
                        emu.run(15)
                        require(emu.read(f"game_storage + {axis}")[0] == target, "La nave rebasa el límite")
                        return
                raise RuntimeError(f"No alcanza el límite {target} del eje {axis}")
            finally:
                emu.key(row, mask, False)

        # Entity layout and limits belong to examples/nave/common.inc and its ECS profile.
        boundary(0, 0xFD, 4, 76, 450)
        boundary(1, 0xFE, 4, 0, 450)
        boundary(0, 0xFE, 5, 44, 450)
        boundary(0, 0xFB, 5, 192, 450)
        hud = b"".join(emu.read(0xC000 + (y & 7) * 0x800 + (y >> 3) * 80 + 60, 16) for y in range(4, 13))
        require(any(hud), "El HUD está vacío")
        require(emu.read("game_status") == b"\x5a", "El juego deja de estar activo")
        image = emu.capture()
        rgba = base64.b64decode(image["data_base64"], validate=True)
        require(len(rgba) == image["width"] * image["height"] * 4, "Captura RGBA inválida")
        require(len(set(rgba)) > 2, "Captura vacía")
        state = emu.save()
        saved_hash = emu.state_hash()
        emu.key(0, 0xFE, True)
        emu.run(100)
        continued = emu.state_hash()
        emu.restore(state)
        require(emu.state_hash() == saved_hash, "Restauración inexacta")
        emu.key(0, 0xFE, True)
        emu.run(100)
        require(emu.state_hash() == continued, "Continuación inexacta tras restaurar")
        emu.key(0, 0xFE, False)
        elapsed = time.perf_counter() - started
        return {
            "hash": emu.state_hash(), "screen_sha256": hashlib.sha256(rgba).hexdigest(),
            "frames": emu.frames, "wall_seconds": elapsed, "boot_seconds": boot_seconds,
            "realtime_factor_50hz": emu.frames / 50 / elapsed,
            "method_seconds": dict(emu.method_seconds), "api_version": emu.session["api_version"],
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--rom-dir", type=Path, required=True)
    parser.add_argument("--disk", type=Path, default=ROOT / "build/tests/GlasnostFWK-tests.dsk")
    parser.add_argument("--symbols", type=Path, default=ROOT / "build/nave/obj/nave.noi")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    if args.runs < 2:
        parser.error("--runs requiere al menos 2 arranques independientes")
    samples = [run_once(args.emulator, args.rom_dir, args.disk, args.symbols) for _ in range(args.runs)]
    require(len({(s["hash"], s["screen_sha256"], s["frames"]) for s in samples}) == 1, "Los arranques independientes difieren")
    report = {
        "schema": 1, "scenario": "glasnost-nave-bluepixel-v1", "platform": platform.platform(),
        "glasnost_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "emulator_version": subprocess.check_output([str(args.emulator.resolve()), "--version"], text=True).strip(),
        "sha256": {name: hashlib.sha256(file.read_bytes()).hexdigest() for name, file in
                   (("disk", args.disk), ("symbols", args.symbols), ("emulator", args.emulator), ("rom_manifest", args.rom_dir / "roms.json"))},
        "samples": samples, "median_realtime_factor_50hz": statistics.median(s["realtime_factor_50hz"] for s in samples),
    }
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2) + "\n")
    print(f"nave: {args.runs} arranques idénticos; {samples[0]['frames']} fotogramas/arranque; "
          f"mediana {report['median_realtime_factor_50hz']:.2f}x; hash {samples[0]['hash']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
