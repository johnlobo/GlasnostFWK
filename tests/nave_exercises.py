"""The two exercises of docs/nave-walkthrough.md as code, shared by the host test and the smoke.

The text of the walkthrough must contain exactly these edits (test_nave_walkthrough checks it),
so what the reader types is what was built and run.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAVE = ROOT / "examples" / "nave"

SPEED_OLD, SPEED_NEW = "GAME_SPEED_Y = 2", "GAME_SPEED_Y = 4"
CAP_OLD, CAP_NEW = "GAME_CAP = 4", "GAME_CAP = 5"
ROW_LINE = ("_game_row_drone3: GAME_ROW GAME_DRONE_COMPS, GAME_T_DRONE, 40, 160, 4, 8, "
            "game_drone_pixels, _game_program_drone, _game_anim_drone")
SPAWN_BLOCK = ("    ld ix, #game_manager\n"
               "    ld hl, #_game_row_drone3\n"
               "    call _game_spawn\n"
               "    call _game_expect_ok\n")
ROW_ANCHOR = "_game_row_drone2:"
SPAWN_ANCHOR = "    ld a, #0x5A\n    ld (game_status), a"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text()
    assert text.count(old) == 1, f"{path.name}: {old!r} found {text.count(old)} times"
    path.write_text(text.replace(old, new))


def faster_ship(folder: Path) -> None:
    replace_once(folder / "common.inc", SPEED_OLD, SPEED_NEW)


def fourth_drone(folder: Path, *, raise_cap: bool = True) -> None:
    if raise_cap:
        replace_once(folder / "common.inc", CAP_OLD, CAP_NEW)
    main = folder / "main.s"
    text = main.read_text()
    line_end = text.index("\n", text.index(ROW_ANCHOR))
    text = text[:line_end + 1] + ROW_LINE + "\n" + text[line_end + 1:]
    assert text.count(SPAWN_ANCHOR) == 1
    text = text.replace(SPAWN_ANCHOR, SPAWN_BLOCK + "\n" + SPAWN_ANCHOR)
    main.write_text(text)


def project_from_example(parent: Path, run) -> Path:
    """A real glasnost project whose game files are examples/nave, ready to edit, config and build."""
    code, out, err = run(["new", "nave", "--dir", str(parent), "--no-git", "--no-build", "--title", "mi primer juego"])
    assert code == 0, out + err
    folder = parent / "nave"
    for name in ("main.s", "common.inc", "example.json"):
        shutil.copy2(NAVE / name, folder / name)
    shutil.copytree(NAVE / "assets", folder / "assets", dirs_exist_ok=True)
    return folder
