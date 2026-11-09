#!/usr/bin/env python3
"""Hand-mutation runner for examples/platformer (main.s and common.inc).

Each mutation breaks one rule of the game. A mutation is DETECTED when the host
tests (tests/test_ecs_manager.py) or the emulator smoke (tests/emulator_smoke.py,
platformer section) fail on it, and SURVIVES when both pass. The runner
always restores both files byte for byte, whatever happens.

    python3 tools/dev/mutate_platformer.py --host-only          # seconds, no emulator
    python3 tools/dev/mutate_platformer.py                      # full run, ~1.5 min each
    python3 tools/dev/mutate_platformer.py --only flash         # name filter

`tests/test_mutation_table.py` checks that every pattern below still matches exactly
once across main.s and common.inc, so the table cannot rot silently. Patterns match the
CODE lines only: comments and blank lines in the sources (and in the patterns) are ignored,
so documenting the game never breaks the table.
"""
from __future__ import annotations

import argparse
import fcntl
import re
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN = ROOT / "examples/platformer/main.s"
COMMON = ROOT / "examples/platformer/common.inc"
SOURCES = (MAIN, COMMON)


_LITERAL = re.compile(r"'(\\.|[^'\\])'")           # an assembler character literal such as '0'
_GAP = r"[ \t]*(?:;[^\n]*)?\n(?:[ \t]*(?:;[^\n]*)?\n)*"   # end of a line plus any blank or comment-only lines
_EOL = r"[ \t]*(?:;[^\n]*)?\n"


def strip_comment(line: str) -> str:
    """`line` without its `;` comment (a `;` inside a string or a character literal is kept)."""
    out, quote, i = [], None, 0
    while i < len(line):
        ch = line[i]
        if quote:
            out.append(ch)
            quote = None if ch == quote else quote
        elif ch == '"':
            quote = ch
            out.append(ch)
        elif ch == "'" and (literal := _LITERAL.match(line, i)):
            out.append(literal.group(0))
            i = literal.end() - 1
        elif ch == ";":
            break
        else:
            out.append(ch)
        i += 1
    return "".join(out).rstrip()


def code_only(text: str) -> str:
    """The source with comments and blank lines removed: what the assembler sees, line by line."""
    lines = (strip_comment(line) for line in text.split("\n"))
    return "\n".join(line for line in lines if line.strip()) + "\n"


def spans(text: str, old: str) -> list[tuple[int, int]]:
    """Where the code lines of `old` occur in `text`, ignoring comments and blank lines between
    and after them. Comments are documentation: adding one must not break a mutation."""
    tokens = [strip_comment(line) for line in old.split("\n")]
    closed = tokens[-1] == ""                              # `old` ends with a newline
    body = [t for t in tokens[:-1] if t.strip()] if closed else [t for t in tokens if t.strip()]
    if not body:
        raise ValueError("a mutation pattern needs at least one line of code")
    pattern = _GAP.join(re.escape(t) for t in body) + (_EOL if closed else "")
    return [match.span() for match in re.finditer(pattern, text)]


def locate(texts: dict, old: str):
    """The one source file that holds `old` exactly once, or None."""
    found = {path: spans(text, old) for path, text in texts.items()}
    hits = [path for path, matches in found.items() if len(matches) == 1]
    total = sum(len(matches) for matches in found.values())
    return hits[0] if len(hits) == 1 and total == 1 else None
EMULATOR = Path("/config/workspace/tools/amspirit-lite/run.sh")
LOCK = "/tmp/amspirit.lock"

# (name, text to replace, replacement). Patterns match exactly once.
MUTATIONS: list[tuple[str, str, str]] = [
    # Entities and rules
    ("door hit ignored", "    ld a, #1\n    ld (_pfe_door_hit), a", "    ld a, #0\n    ld (_pfe_door_hit), a"),
    ("win at 3 coins", "PFE_WIN_SCORE     = 4", "PFE_WIN_SCORE     = 3"),
    ("enemies harmless", "    ld e, #PFE_CH_ENEMY\n    call fwk_ecs_collide", "    ld e, #PFE_CH_ENEMY\n    xor a"),
    ("enemy pass sees coins", "    ld bc, #ECS_C_COLLISION | ECS_C_BEHAVIOR", "    ld bc, #ECS_C_COLLISION"),
    ("H enemy runs every iteration", "PFE_ROW PFE_ENEMY_COMPS, PFE_T_ENEMY, 36, 122, 4, 8, platformer_enemy_pixels, _pfe_program_h, _pfe_anim_enemy_slow, PFE_CAD_ODD",
     "PFE_ROW PFE_ENEMY_COMPS, PFE_T_ENEMY, 36, 122, 4, 8, platformer_enemy_pixels, _pfe_program_h, _pfe_anim_enemy_slow, 0"),
    ("H and V share the iteration", "PFE_CAD_ODD  = 0x11", "PFE_CAD_ODD  = 0x01"),
    ("tick never advances", "    ld hl, #fwk_ecs_tick               ; one tick per loop iteration, for the cadence bytes\n    inc (hl)\n", ""),
    ("collect removed", "    call fwk_ecs_manager_collect", "    xor a"),
    ("initial lives 3", "PFE_LIVES_INITIAL = 10", "PFE_LIVES_INITIAL = 3"),
    ("animation removed",
     "    ld ix, #platformer_manager\n    call fwk_ecs_system_animation",
     "    ld ix, #platformer_manager\n    xor a"),
    ("slow enemies animate at full speed", "PFE_ANIM_TICKS_SLOW = 4", "PFE_ANIM_TICKS_SLOW = 8"),
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
     "    ld a, (platformer_lives)\n    or a\n    jr z, _pfe_cb_ok\n",
     "    ld a, (platformer_lives)\n"),
    ("win-frame guard removed", "    ld hl, #_pfe_all_coins\n    or (hl)\n    ret nz", "    or a\n    ret nz"),
    # Second level
    ("map2 never unpacked", "    call fwk_zx7b_unpack\n    jp _pfe_start_level", "    jp _pfe_start_level"),
    ("score not reset on level start",
     "    ld (platformer_score), a\n    ld (platformer_won), a\n    ld (_pfe_all_coins), a",
     "    ld (platformer_won), a\n    ld (_pfe_all_coins), a"),
    ("lives reset on level start",
     "    ld a, #PFE_HUD_SCORE | PFE_HUD_LIVES | PFE_HUD_HINT\n    ld (platformer_hud_dirty), a",
     "    ld a, #PFE_LIVES_INITIAL\n    ld (platformer_lives), a\n    ld a, #PFE_HUD_SCORE | PFE_HUD_LIVES | PFE_HUD_HINT\n    ld (platformer_hud_dirty), a"),
    ("lives reset by the door",
     "    call fwk_zx7b_unpack\n    jp _pfe_start_level",
     "    call fwk_zx7b_unpack\n    ld a, #PFE_LIVES_INITIAL\n    ld (platformer_lives), a\n    jp _pfe_start_level"),
    ("player keeps map 1 physics",
     "    ld hl, (_pfe_map_desc)\n    ld ECS_E_PLATFORM_TILEMAP(iy), l",
     "    ld hl, #platformer_map_descriptor\n    ld ECS_E_PLATFORM_TILEMAP(iy), l"),
    ("map 1 drawn on level 2",
     "    ld ix, (_pfe_map_desc)\n    ld iy, #platformer_view            ; both maps are 20x25\n    call fwk_tilemap_render_view",
     "    ld ix, #platformer_map_descriptor\n    ld iy, #platformer_view            ; both maps are 20x25\n    call fwk_tilemap_render_view"),
    ("level 2 door restarts again",
     "    ld a, (platformer_level)\n    or a\n    jr nz, _pfe_door_end",
     "    ld a, (platformer_level)\n    xor a\n    or a\n    jr nz, _pfe_door_end"),
    ("door never leaves level 1", "    inc a\n    ld (platformer_level), a", "    inc a"),
    ("tick not reset on level start", "    ld (_pfe_door_hit), a\n    ld (fwk_ecs_tick), a", "    ld (_pfe_door_hit), a"),
    ("H enemy starts elsewhere", "PFE_ROW PFE_ENEMY_COMPS, PFE_T_ENEMY, 36, 122,", "PFE_ROW PFE_ENEMY_COMPS, PFE_T_ENEMY, 34, 122,"),
]


def run(command: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=ROOT, capture_output=True, text=True, errors="replace", **kwargs)


def host_tests_pass() -> bool:
    return run([sys.executable, "-m", "unittest", "tests.test_ecs_manager"]).returncode == 0


def smoke_passes(emulator: Path) -> bool:
    run(["rm", "-rf", "build/platformer/obj"])
    if run([sys.executable, "tools/build/build_examples.py", "platformer"]).returncode != 0:
        return False  # a mutation that does not build is reported, not counted as detected
    run([sys.executable, "tools/build/build_test_disk.py", "platformer"])
    with open(LOCK, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        result = run(
            [sys.executable, "tests/emulator_smoke.py", "--emulator", str(emulator), "platformer"],
            timeout=600,
        )
    return result.returncode == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host-only", action="store_true", help="skip the emulator smoke")
    parser.add_argument("--only", help="run the mutations whose name contains this text")
    parser.add_argument("--emulator", type=Path, default=EMULATOR)
    args = parser.parse_args()

    # The sources are restored in `finally`: make sure a closed pipe (`| head`) or a
    # SIGTERM unwinds the stack instead of killing the process mid-mutation.
    signal.signal(signal.SIGPIPE, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    originals = {path: path.read_bytes() for path in SOURCES}
    texts = {path: data.decode() for path, data in originals.items()}
    survivors = []
    try:
        for name, old, new in MUTATIONS:
            if args.only and args.only not in name:
                continue
            target = locate(texts, old)
            if target is None:
                print(f"{name}: PATTERN NOT FOUND exactly once, update tools/dev/mutate_platformer.py")
                survivors.append(name)
                continue
            for path, data in originals.items():
                path.write_bytes(data)
            start, end = spans(texts[target], old)[0]
            target.write_text(texts[target][:start] + new + texts[target][end:])
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
        for path, data in originals.items():
            path.write_bytes(data)
    if any(path.read_bytes() != data for path, data in originals.items()):
        print("sources were NOT restored", file=sys.stderr)
        return 2
    if not args.host_only:
        run(["rm", "-rf", "build/platformer/obj"])
        run([sys.executable, "tools/build/build_examples.py", "platformer"])
    print(f"\n{len(survivors)} not detected" if survivors else "\nall detected")
    return 1 if survivors and not args.host_only else 0


if __name__ == "__main__":
    raise SystemExit(main())
