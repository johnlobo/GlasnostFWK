#!/usr/bin/env python3
"""Emulator smoke of the two exercises of docs/guide/nave-walkthrough.md. Optional, like project_smoke.py:

    flock /tmp/amspirit.lock python3 tests/nave_walkthrough_smoke.py \\
        --emulator /config/workspace/tools/amspirit-lite/run.sh

Builds examples/nave as a project, applies each exercise exactly as tests/nave_exercises.py (the
text of the walkthrough) and runs it:
  base      holding DOWN for 60 emulator frames moves the ship some lines (the game loop takes
            two frames per turn, so that is about 1 line per frame)
  exercise 1  the same with GAME_SPEED_Y = 4 moves it twice as far
  exercise 2  GAME_CAP = 5 + row + spawn: game_status 0x5A, a fifth entity of type drone that moves,
              and touching it adds hits (at least one: a drone that turns can cross the ship twice)
  exercise 2 without raising GAME_CAP: the game stops with 0x03 (FWK_ECS_ERR_FULL) in game_status
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
import nave_exercises as ex  # noqa: E402
from test_glasnost_project import real_toolchain  # noqa: E402
from test_nave_walkthrough import run  # noqa: E402

UP, DOWN = 0xFE, 0xFB              # cursor keys on matrix row 0
SIZE, TYPE_OFF, X_OFF, Y_OFF, FLAGS_OFF = 37, 3, 4, 5, 17   # nave's ecs_profile.inc


def build(tmp: Path, edit) -> tuple[Path, Path]:
    env = {"CPCT_NEXT_PATH": str(real_toolchain())}
    folder = ex.project_from_example(tmp, lambda a: run(a, env=env))
    if edit:
        edit(folder)
    for step in (["config"], ["build"]):
        code, out, err = run(step, cwd=folder, env=env)
        if code != 0:
            raise RuntimeError(out + err)
    return folder / "build" / "nave.dsk", next((folder / "build").rglob("nave.noi"))


@contextlib.contextmanager
def emulator(path: Path, dsk: Path):
    with contextlib.suppress(OSError):
        if emu.get("/api/ping").get("ok"):
            raise RuntimeError("an emulator is already answering on the API port; stop it first")
    process = subprocess.Popen([str(path), "--web-server", "--model", "6128", "--ram", "128", str(dsk)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        emu.wait_for(lambda: emu.get("/api/ping").get("ok"), 30, "emulator API")
        time.sleep(6)
        emu.post("/api/keytype", {"text": 'run"nave\n'})
        yield
    finally:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
        # run.sh leaves the emulator and its X server running after the wrapper exits: this smoke
        # starts four in a row, so make sure the port is free before the next one.
        for _ in range(20):
            try:
                emu.get("/api/ping")
            except OSError:
                break
            subprocess.run(["pkill", "-9", "-f", "amspirit-lite-sdl"], check=False)
            subprocess.run(["pkill", "-9", "-x", "Xvfb"], check=False)
            time.sleep(0.5)


def ship_travel(noi: Path) -> int:
    """Lines the ship moves in 60 frames holding DOWN, from the top limit."""
    storage = emu.symbol(noi, "game_storage")
    emu.wait_for(lambda: emu.ram(emu.symbol(noi, "game_status"), 1) == b"\x5A", 90, "game_status 0x5A")
    emu.hold_keys(row0=UP, frames=140)                 # 126 lines to the top at speed 2 = 126 frames
    top = emu.ram(storage + Y_OFF, 1)[0]
    emu.hold_keys(row0=DOWN, frames=60)      # 30 loop turns: +-1 turn is +-3% of the travel
    return emu.ram(storage + Y_OFF, 1)[0] - top


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--emulator", type=Path, required=True)
    args = parser.parse_args()
    results = {}
    with tempfile.TemporaryDirectory(prefix="glasnost-walk-smoke-") as tmp:
        tmp = Path(tmp)
        for name, edit in (("base", None), ("faster", ex.faster_ship), ("fourth", ex.fourth_drone),
                           ("nocap", lambda f: ex.fourth_drone(f, raise_cap=False))):
            (tmp / name).mkdir()
            results[name] = build(tmp / name, edit)

        travel = {}
        for name in ("base", "faster"):
            dsk, noi = results[name]
            with emulator(args.emulator, dsk):
                travel[name] = ship_travel(noi)
            print(f"{name}: the ship travelled {travel[name]} lines in 60 frames holding DOWN")
        ratio = travel["faster"] / travel["base"]
        print(f"exercise 1: GAME_SPEED_Y 2 -> 4 moves the ship {ratio:.2f}x as far")
        if not 1.8 <= ratio <= 2.2:
            raise RuntimeError(f"expected about twice the travel, got {ratio:.2f}x")

        dsk, noi = results["fourth"]
        storage, status, hits = (emu.symbol(noi, s) for s in ("game_storage", "game_status", "game_hits"))
        with emulator(args.emulator, dsk):
            emu.wait_for(lambda: emu.ram(status, 1) == b"\x5A", 90, "game_status 0x5A")
            fifth = lambda: emu.ram(storage + 4 * SIZE, SIZE)  # noqa: E731
            if fifth()[TYPE_OFF] != 2:
                raise RuntimeError(f"entity 4 is not a drone: type {fifth()[TYPE_OFF]}")
            first, second = fifth()[X_OFF], (time.sleep(0.5), fifth()[X_OFF])[1]
            if first == second:
                raise RuntimeError(f"the fifth drone does not move: x {first}")
            before = emu.ram(hits, 1)[0]
            drone = fifth()
            emu.write_ram(storage + X_OFF, bytes([drone[X_OFF]]))
            emu.write_ram(storage + Y_OFF, bytes([drone[Y_OFF]]))
            emu.write_ram(storage + FLAGS_OFF, bytes([emu.ram(storage + FLAGS_OFF, 1)[0] | 0x02]))
            time.sleep(0.3)   # long enough for the contact, short enough for the drone not to come back
            gained = emu.ram(hits, 1)[0] - before
        print(f"fourth drone: type 2, x {first} -> {second}, touching it added {gained} hit(s)")
        if gained < 1:
            raise RuntimeError("touching the fifth drone did not add a hit")

        dsk, noi = results["nocap"]
        status = emu.symbol(noi, "game_status")
        with emulator(args.emulator, dsk):
            time.sleep(12)
            code = emu.ram(status, 1)[0]
        print(f"fourth drone without GAME_CAP=5: game_status = 0x{code:02X}")
        if code != 0x03:   # FWK_ECS_ERR_FULL: the fifth entity does not fit in a manager of four
            raise RuntimeError(f"expected 0x03 (FWK_ECS_ERR_FULL) in game_status, got 0x{code:02X}")
    print("PASS nave walkthrough smoke")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
