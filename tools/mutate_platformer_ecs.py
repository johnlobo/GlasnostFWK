#!/usr/bin/env python3
"""Hand-mutation runner for examples/platformer_ecs/main.s.

Each mutation breaks one rule of the game. A mutation is DETECTED when the host
tests (tests/test_ecs_manager.py) or the emulator smoke (tests/emulator_smoke.py,
platformer_ecs section) fail on it, and SURVIVES when both pass. The runner
always restores main.s byte for byte, whatever happens.

    python3 tools/mutate_platformer_ecs.py --host-only          # seconds, no emulator
    python3 tools/mutate_platformer_ecs.py                      # full run, ~1.5 min each
    python3 tools/mutate_platformer_ecs.py --only flash         # name filter

`tests/test_ecs_manager.py` checks that every pattern below still matches exactly
once, so the table cannot rot silently when main.s changes.
"""
from __future__ import annotations

import argparse
import fcntl
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "examples/platformer_ecs/main.s"
EMULATOR = Path("/config/workspace/tools/amspirit-lite/run.sh")
LOCK = "/tmp/amspirit.lock"

# (name, text to replace, replacement). Patterns match exactly once.
MUTATIONS: list[tuple[str, str, str]] = [
    # Entities and rules
    ("door hit ignored", "    ld a, #1\n    ld (_pfe_door_hit), a", "    ld a, #0\n    ld (_pfe_door_hit), a"),
    ("win at 3 coins", "PFE_WIN_SCORE     = 4", "PFE_WIN_SCORE     = 3"),
    ("H enemy harmless", "    ld e, #PFE_CH_H\n    call fwk_ecs_collide", "    ld e, #PFE_CH_H\n    xor a"),
    ("collect removed", "    call fwk_ecs_manager_collect", "    xor a"),
    ("initial lives 3", "PFE_LIVES_INITIAL = 10", "PFE_LIVES_INITIAL = 3"),
    ("enemy animation removed",
     "    ld ix, #platformer_ecs_h\n    call fwk_ecs_system_animation",
     "    ld ix, #platformer_ecs_h\n    xor a"),
    # HUD and flash
    ("no flash", "    bit 3, a\n    ret z\n    ld b, #PFE_FLASH_COUNT", "    ret\n    ld b, #PFE_FLASH_COUNT"),
    ("hint not updated on win", "    set 0, (hl)\n    set 2, (hl)", "    set 0, (hl)"),
    ("lives digits swapped",
     "    ld (_pfe_str_life + 7), a\n    ld a, b\n    ld (_pfe_str_life + 6), a",
     "    ld (_pfe_str_life + 6), a\n    ld a, b\n    ld (_pfe_str_life + 7), a"),
    ("score digit never patched", "    ld (_pfe_str_score + 7), a", "    xor a"),
    ("border stays red", "PFE_BORDER_BLACK   = 0x14", "PFE_BORDER_BLACK   = 0x1C"),
    ("lives HUD not dirty", "    set 1, (hl)\n    set 3, (hl)", "    set 3, (hl)"),
    ("HUD row 2 not restored", "    ld b, #2\n    call _pfe_hud_restore", "    nop"),
    ("flash only once (constant)", "PFE_FLASH_COUNT    = 3", "PFE_FLASH_COUNT    = 1"),
    ("flash only once (loop)", "    ld b, #PFE_FLASH_COUNT\n_pfe_flash:", "    ld b, #1\n_pfe_flash:"),
    ("lives guard removed",
     "    ld a, (platformer_ecs_lives)\n    or a\n    jr z, _pfe_cb_ok\n",
     "    ld a, (platformer_ecs_lives)\n"),
    ("win-frame guard removed", "    ld hl, #_pfe_all_coins\n    or (hl)\n    ret nz", "    or a\n    ret nz"),
    # Second level
    ("map2 never unpacked", "    call fwk_zx7b_unpack\n    jp _pfe_start_level", "    jp _pfe_start_level"),
    ("score not reset on level start",
     "    ld (platformer_ecs_score), a\n    ld (platformer_ecs_won), a\n    ld (_pfe_all_coins), a",
     "    ld (platformer_ecs_won), a\n    ld (_pfe_all_coins), a"),
    ("lives reset on level start",
     "    ld a, #PFE_HUD_SCORE | PFE_HUD_LIVES | PFE_HUD_HINT\n    ld (platformer_ecs_hud_dirty), a",
     "    ld a, #PFE_LIVES_INITIAL\n    ld (platformer_ecs_lives), a\n    ld a, #PFE_HUD_SCORE | PFE_HUD_LIVES | PFE_HUD_HINT\n    ld (platformer_ecs_hud_dirty), a"),
    ("lives reset by the door",
     "    call fwk_zx7b_unpack\n    jp _pfe_start_level",
     "    call fwk_zx7b_unpack\n    ld a, #PFE_LIVES_INITIAL\n    ld (platformer_ecs_lives), a\n    jp _pfe_start_level"),
    ("player keeps map 1 physics",
     "    ld hl, (_pfe_map_desc)\n    ld ECS_E_PLATFORM_TILEMAP(iy), l",
     "    ld hl, #platformer_ecs_map_descriptor\n    ld ECS_E_PLATFORM_TILEMAP(iy), l"),
    ("map 1 drawn on level 2",
     "    ld ix, (_pfe_map_desc)\n    ld iy, #platformer_ecs_view            ; both maps are 20x25\n    call fwk_tilemap_render_view",
     "    ld ix, #platformer_ecs_map_descriptor\n    ld iy, #platformer_ecs_view            ; both maps are 20x25\n    call fwk_tilemap_render_view"),
    ("level 2 door restarts again",
     "    ld a, (platformer_ecs_level)\n    or a\n    jr nz, _pfe_door_end",
     "    ld a, (platformer_ecs_level)\n    xor a\n    or a\n    jr nz, _pfe_door_end"),
    ("door never leaves level 1", "    inc a\n    ld (platformer_ecs_level), a", "    inc a"),
    ("enemy phase not reset", "    ld (_pfe_door_hit), a\n    ld (_pfe_phase), a", "    ld (_pfe_door_hit), a"),
    ("H enemy starts elsewhere", "PFE_ROW PFE_ENEMY_COMPS, PFE_T_ENEMY, 36, 122,", "PFE_ROW PFE_ENEMY_COMPS, PFE_T_ENEMY, 34, 122,"),
]


def run(command: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=ROOT, capture_output=True, text=True, errors="replace", **kwargs)


def host_tests_pass() -> bool:
    return run([sys.executable, "-m", "unittest", "tests.test_ecs_manager"]).returncode == 0


def smoke_passes(emulator: Path) -> bool:
    run(["rm", "-rf", ".build/platformer_ecs/obj"])
    if run([sys.executable, "tools/build_examples.py", "platformer_ecs"]).returncode != 0:
        return False  # a mutation that does not build is reported, not counted as detected
    run([sys.executable, "tools/build_test_disk.py", "platformer_ecs"])
    with open(LOCK, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        result = run(
            [sys.executable, "tests/emulator_smoke.py", "--emulator", str(emulator), "platformer_ecs"],
            timeout=600,
        )
    return result.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host-only", action="store_true", help="skip the emulator smoke")
    parser.add_argument("--only", help="run the mutations whose name contains this text")
    parser.add_argument("--emulator", type=Path, default=EMULATOR)
    args = parser.parse_args()

    original = MAIN.read_bytes()
    text = original.decode()
    survivors = []
    try:
        for name, old, new in MUTATIONS:
            if args.only and args.only not in name:
                continue
            if text.count(old) != 1:
                print(f"{name}: PATTERN NOT FOUND exactly once, update tools/mutate_platformer_ecs.py")
                survivors.append(name)
                continue
            MAIN.write_text(text.replace(old, new, 1))
            if not host_tests_pass():
                verdict = "detected by the host tests"
            elif args.host_only:
                verdict = "SURVIVED the host tests (not run in the emulator)"
                survivors.append(name)
            elif not smoke_passes(args.emulator):
                verdict = "detected by the smoke"
            else:
                verdict = "SURVIVED host tests and smoke"
                survivors.append(name)
            print(f"{name}: {verdict}", flush=True)
    finally:
        MAIN.write_bytes(original)
    if MAIN.read_bytes() != original:
        print("main.s was NOT restored", file=sys.stderr)
        return 2
    if not args.host_only:
        run(["rm", "-rf", ".build/platformer_ecs/obj"])
        run([sys.executable, "tools/build_examples.py", "platformer_ecs"])
    print(f"\n{len(survivors)} not detected" if survivors else "\nall detected")
    return 1 if survivors and not args.host_only else 0


if __name__ == "__main__":
    raise SystemExit(main())
