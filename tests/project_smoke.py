#!/usr/bin/env python3
"""Emulator smoke of a project made by `glasnost new`: it boots, it reacts to keys, it stays in bounds.

Optional, like tests/emulator_smoke.py (needs an emulator exposing the AmSpiriT web API):

    flock /tmp/amspirit.lock python3 tests/project_smoke.py \\
        --emulator /config/workspace/tools/amspirit-lite/run.sh [--model 464] [--extended-memory]

It creates a throwaway project with the real CLI, builds it with the toolchain the CLI
resolves, runs it, and checks through RAM (symbols from the project's .noi):
  1. game_status is 0x5A and the three drones move (their X changes);
  2. holding CURSOR RIGHT moves the player right until it stops at GAME_X_MAX;
  3. holding CURSOR LEFT stops at 0 (the u8 wrap never shows);
  4. UP stops at GAME_Y_MIN and DOWN at GAME_Y_MAX;
  5. the imported background map is drawn (the ground row fills the last scanline).
"""

from __future__ import annotations

import argparse
import contextlib
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path[:0] = [str(ROOT / "tools" / d) for d in ("glasnost", "build", "dev")]

import emulator_smoke as emu  # noqa: E402
import glasnost  # noqa: E402

X_MAX, Y_MIN, Y_MAX = 76, 44, 192


def profile_offsets(folder: Path) -> tuple[int, int, int]:
    values = {}
    for line in (folder / "generated" / "ecs_profile.inc").read_text(encoding="ascii").splitlines():
        parts = line.split("=")
        if len(parts) == 2 and parts[0].strip() in {"ECS_E_X", "ECS_E_Y", "ECS_ENTITY_SIZE"}:
            values[parts[0].strip()] = int(parts[1].split(";")[0], 0)
    return values["ECS_E_X"], values["ECS_E_Y"], values["ECS_ENTITY_SIZE"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--model", default="6128", choices=("464", "6128"))
    parser.add_argument("--extended-memory", action="store_true")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="glasnost-smoke-") as tmp:
        extra = ["--extended-memory"] if args.extended_memory else []
        code = glasnost.main(["--lang", "en", "new", "smoke", "--dir", tmp, "--no-git", *extra])
        if code != 0:
            return code
        folder = Path(tmp) / "smoke"
        x_off, y_off, size = profile_offsets(folder)
        noi = folder / "build" / "obj" / "smoke.noi"
        dsk = folder / "build" / "smoke.dsk"
        status, storage = emu.symbol(noi, "game_status"), emu.symbol(noi, "game_storage")
        frame = emu.symbol(noi, "fwk_system_frame_count")

        try:
            if emu.get("/api/ping").get("ok"):
                raise RuntimeError("an emulator is already answering on the API port; stop it first")
        except OSError:
            pass  # nothing listening: good
        process = subprocess.Popen(
            [str(args.emulator), "--web-server", "--model", args.model, "--ram", "128", str(dsk)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            emu.wait_for(lambda: emu.get("/api/ping").get("ok"), 30, "emulator API")
            time.sleep(6)
            emu.post("/api/keytype", {"text": 'run"smoke\n'})
            # The loop counter holds firmware garbage before the game loads (slow on a 464), so wait
            # for the game's own status byte, then prove the loop is alive.
            emu.wait_for(lambda: emu.ram(status, 1) == b"\x5A", 90, "game_status 0x5A")
            before = emu.ram(frame, 2)
            time.sleep(0.5)
            if emu.ram(frame, 2) == before:
                raise RuntimeError("the frame counter does not advance: the game loop is not running")

            def entity(index: int) -> tuple[int, int]:
                raw = emu.ram(storage + index * size, size)
                return raw[x_off], raw[y_off]

            first = [entity(i)[0] for i in (1, 2, 3)]
            time.sleep(0.5)
            second = [entity(i)[0] for i in (1, 2, 3)]
            if any(a == b for a, b in zip(first, second)):
                raise RuntimeError(f"a drone does not move: {first} -> {second}")

            # The imported background: the solid ground row fills the last scanline. Catches a
            # tilemap descriptor that fwk_tilemap_render_view rejects (it then draws nothing).
            if not all(emu.ram(emu.standard_screen_address(0, 199), 80)):
                raise RuntimeError("the background map is not drawn: the last scanline has empty bytes")

            held = emu.symbol(noi, "fwk_input_held")

            def hold_until(row0: int, row1: int, done, label: str) -> None:
                try:
                    emu.hold_keys_until(done, row0=row0, row1=row1, timeout=15, label=label)
                except RuntimeError as error:
                    raise RuntimeError(f"{error} (player {entity(0)}, held actions 0x{emu.ram(held, 1)[0]:02X})") from error

            # Cursor keys sit on matrix row 0: right = bit 1, left = bit 0, up = bit 0 of row 0 is
            # CURSOR UP (0xFE) and down is bit 2 (0xFB); left is row 1 bit 0 (0xFE), right row 0 bit 1.
            hold_until(0xFD, 0xFF, lambda: entity(0)[0] == X_MAX, "player at the right edge")
            time.sleep(0.3)
            if entity(0)[0] != X_MAX:
                raise RuntimeError(f"player left the right edge: x={entity(0)[0]}")
            hold_until(0xFF, 0xFE, lambda: entity(0)[0] == 0, "player at the left edge")
            time.sleep(0.3)
            if entity(0)[0] != 0:
                raise RuntimeError(f"player did not stop at 0: x={entity(0)[0]}")
            hold_until(0xFE, 0xFF, lambda: entity(0)[1] == Y_MIN, "player at the top limit")
            time.sleep(0.3)
            if entity(0)[1] != Y_MIN:
                raise RuntimeError(f"player passed the top limit: y={entity(0)[1]}")
            hold_until(0xFB, 0xFF, lambda: entity(0)[1] == Y_MAX, "player at the bottom limit")
            time.sleep(0.3)
            if entity(0)[1] != Y_MAX:
                raise RuntimeError(f"player passed the bottom limit: y={entity(0)[1]}")
            print(f"PASS project smoke ({args.model}{', extended memory' if args.extended_memory else ''})")
            return 0
        finally:
            # run.sh starts the emulator and an X server as children: stop the whole group
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)


if __name__ == "__main__":
    raise SystemExit(main())
