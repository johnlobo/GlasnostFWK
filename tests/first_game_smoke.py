#!/usr/bin/env python3
"""Emulator smoke of the finished game of docs/guide/first-game (step 3). Optional, like project_smoke.py:

    flock /tmp/amspirit.lock python3 tests/first_game_smoke.py \\
        --emulator /config/workspace/tools/amspirit-lite/run.sh [--model 464] [--screenshot out.png] [--example]

Creates the project with the real CLI, applies the three steps of the guide, builds it, runs it and
checks through RAM (symbols from the .noi) that:
  1. the animation works: a drone's sprite pointer alternates between two different frames;
  2. real play with the cursor keys leaves the score drawn on screen, and the imported map
     (the solid ground row) fills the last scanline;
  3. a drone touching the player adds exactly one hit, not one per frame of the contact;
  4. leaving and touching again adds another hit.

"""

from __future__ import annotations

import argparse
import contextlib
import os
import shutil
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

GUIDE = ROOT / "docs" / "guide" / "first-game"
HUD_X, HUD_Y, HUD_W, HUD_H = 60, 4, 16, 9


def constants(folder: Path, names: set[str]) -> dict[str, int]:
    values = {}
    for line in (folder / "generated" / "ecs_profile.inc").read_text(encoding="ascii").splitlines():
        parts = line.split("=")
        if len(parts) == 2 and parts[0].strip() in names:
            values[parts[0].strip()] = int(parts[1].split(";")[0], 0)
    return values


def best_screenshot() -> bytes:
    """The emulator can answer while the renderer is between erasing and redrawing a sprite.
    Take several and keep the one with the most sprite pixels in the play area."""
    import io
    from PIL import Image

    shots = []
    for _ in range(40):
        data = emu.get_bytes("/api/screenshot?crop=1")
        area = Image.open(io.BytesIO(data)).convert("RGB").crop((70, 160, 700, 470))  # below the text
        colours = area.getcolors(maxcolors=1 << 20)
        background = max(colours)[1]
        lit = sum(count for count, colour in colours if colour != background)
        shots.append((lit, data))
        time.sleep(0.03)
    print(f"screenshot candidates: sprite pixels min {min(s[0] for s in shots)} max {max(s[0] for s in shots)}")
    return max(shots, key=lambda item: item[0])[1]


def apply_steps(folder: Path) -> None:
    for step in ("step1", "step2", "step3"):
        shutil.copytree(GUIDE / step, folder, dirs_exist_ok=True, copy_function=shutil.copy)
    code = glasnost.main(["--lang", "en", "config", "--project", str(folder)])
    if code != 0:
        raise SystemExit(code)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--emulator", type=Path, required=True)
    parser.add_argument("--model", default="6128", choices=("464", "6128"))
    parser.add_argument("--screenshot", type=Path, help="save a PNG of the running game here")
    parser.add_argument("--example", action="store_true",
                        help="check examples/nave (built with the CLI) instead of a project made from the guide")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="glasnost-guide-") as tmp:
        if args.example:
            code = glasnost.main(["--lang", "en", "build", "nave"])
            if code != 0:
                return code
            folder, built = ROOT / "examples" / "nave", ROOT / "build" / "nave"
        else:
            code = glasnost.main(["--lang", "en", "new", "nave", "--dir", tmp, "--no-git", "--no-build"])
            if code != 0:
                return code
            folder = Path(tmp) / "nave"
            apply_steps(folder)
            code = glasnost.main(["--lang", "en", "build", "--project", str(folder)])
            if code != 0:
                return code
            built = folder / "build"
        offsets = constants(folder, {"ECS_E_X", "ECS_E_Y", "ECS_E_RENDER_SPRITE", "ECS_E_RENDER_FLAGS", "ECS_ENTITY_SIZE"})
        x_off, y_off, sprite_off, flags_off, size = (
            offsets[k] for k in ("ECS_E_X", "ECS_E_Y", "ECS_E_RENDER_SPRITE", "ECS_E_RENDER_FLAGS", "ECS_ENTITY_SIZE"))
        noi = built / "obj" / "nave.noi"
        dsk = built / "nave.dsk"
        status, storage = emu.symbol(noi, "game_status"), emu.symbol(noi, "game_storage")
        hits, frame = emu.symbol(noi, "game_hits"), emu.symbol(noi, "fwk_system_frame_count")

        try:
            if emu.get("/api/ping").get("ok"):
                raise RuntimeError("an emulator is already answering on the API port; stop it first")
        except OSError:
            pass
        process = subprocess.Popen(
            [str(args.emulator), "--web-server", "--model", args.model, "--ram", "128", str(dsk)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            emu.wait_for(lambda: emu.get("/api/ping").get("ok"), 30, "emulator API")
            time.sleep(6)
            emu.post("/api/keytype", {"text": 'run"nave\n'})
            emu.wait_for(lambda: emu.ram(status, 1) == b"\x5A", 90, "game_status 0x5A")
            before = emu.ram(frame, 2)
            time.sleep(0.5)
            if emu.ram(frame, 2) == before:
                raise RuntimeError("the frame counter does not advance")

            def entity(index: int) -> bytes:
                return emu.ram(storage + index * size, size)

            # 1. animation: the drone's sprite pointer takes two different values over time
            seen = {bytes(entity(1)[sprite_off:sprite_off + 2])}
            deadline = time.time() + 10
            while len(seen) < 2 and time.time() < deadline:
                time.sleep(0.1)
                seen.add(bytes(entity(1)[sprite_off:sprite_off + 2]))
            if len(seen) < 2:
                raise RuntimeError(f"the drone never changed frame: {seen}")

            # 2. real play: the cursor keys drive the ship up and down through the drones. The score
            #    box must hold drawn text, and the screenshot is taken now, before any RAM teleport
            #    (writing positions behind the renderer's back leaves ghost sprites on screen).
            for key, seconds in ((0xFE, 4), (0xFB, 3), (0xFE, 2)):  # CURSOR UP, DOWN, UP
                emu.set_keys(row0=key)
                time.sleep(seconds)
            emu.set_keys()
            time.sleep(1.5)
            box = b"".join(emu.ram(emu.standard_screen_address(HUD_X, y), HUD_W) for y in range(HUD_Y, HUD_Y + HUD_H))
            if not any(box):
                raise RuntimeError("nothing is drawn where the score should be")
            # The imported background: the ground row (a solid tile) fills the last scanline.
            # Guards the failure where fwk_tilemap_render_view rejects its descriptor and draws nothing.
            ground = emu.ram(emu.standard_screen_address(0, 199), 80)
            if not all(ground):
                raise RuntimeError("the background map is not drawn: the last scanline has empty bytes")
            if args.screenshot:
                args.screenshot.write_bytes(best_screenshot())

            # 3. one touch = one hit. Park the player on top of a drone that is sitting still
            #    long enough: put it exactly where the drone is for a while.
            def teleport_player(x: int, y: int) -> None:
                """Writing the position bypasses the motion system, which is what marks an entity
                dirty for the renderer: set ECS_RENDER_DIRTY (bit 1) ourselves."""
                emu.write_ram(storage + x_off, bytes([x]))
                emu.write_ram(storage + y_off, bytes([y]))
                flags = entity(0)[flags_off]
                emu.write_ram(storage + flags_off, bytes([flags | 0x02]))

            def put_player_on_drone() -> None:
                raw = entity(1)
                teleport_player(raw[x_off], raw[y_off])

            def put_player_away() -> None:
                teleport_player(4, 190)

            put_player_away()
            time.sleep(0.5)
            start = emu.ram(hits, 1)[0]
            for _ in range(25):  # stay on the drone for roughly half a second of game time
                put_player_on_drone()
                time.sleep(0.02)
            time.sleep(0.2)
            first = emu.ram(hits, 1)[0] - start
            if first != 1:
                raise RuntimeError(f"expected exactly 1 hit for one continuous touch, got {first}")

            # 4. leave and touch again
            put_player_away()
            time.sleep(0.6)
            for _ in range(25):
                put_player_on_drone()
                time.sleep(0.02)
            time.sleep(0.2)
            second = emu.ram(hits, 1)[0] - start
            if second != 2:
                raise RuntimeError(f"expected 2 hits after touching again, got {second}")

            print(f"PASS first game smoke ({args.model}): animation, one hit per touch, score drawn")
            return 0
        finally:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)


if __name__ == "__main__":
    raise SystemExit(main())
