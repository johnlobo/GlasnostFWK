#!/usr/bin/env python3
"""Compare full redraw and opt-in CRTC camera paths on BluePixel CPC 6128.

The four-direction route checks final pixels and game state. Timing and
physical hardware remain separate validation gates in docs/design/validation.md.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/glasnost"))
sys.path.insert(0, str(ROOT / "tools/build"))
from bluepixel_adapter import BluePixel
from video_model import address_at_origin

KEYS = {"west": (4, 0xFB), "east": (3, 0xF7), "north": (8, 0xF7), "south": (8, 0xDF)}


def png(width: int, height: int, rgba: bytes) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    rows = b"".join(b"\0" + rgba[y * width * 4:(y + 1) * width * 4] for y in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def state(emu: BluePixel) -> tuple[int, ...]:
    return tuple(emu.read("scroll_world_x", 6))


def hold(emu: BluePixel, direction: str, frames: int = 300) -> None:
    row, mask = KEYS[direction]
    emu.key(row, mask, True)
    try:
        emu.run(frames)
    finally:
        emu.key(row, mask, False)
    emu.run(5)


def check(emu: BluePixel, label: str, expected: tuple[int, ...], out: Path) -> dict:
    actual = state(emu)
    if actual != expected:
        raise RuntimeError(f"{label}: world/screen/camera {actual} != {expected}")
    if emu.read("scroll_status") != b"\x5a":
        raise RuntimeError(f"{label}: game status is {emu.read('scroll_status').hex()}")
    shot = emu.capture()
    regs = shot["metadata"]["crtc_registers"]
    if (regs[1], regs[6], regs[9], regs[12], regs[13]) not in ((32, 16, 7, 48, 0), (16, 16, 7, 48, 0)):
        raise RuntimeError(f"{label}: CRTC profile changed unexpectedly: {regs}")
    rgba = base64.b64decode(shot["data_base64"], validate=True)
    if len(rgba) != shot["width"] * shot["height"] * 4:
        raise RuntimeError(f"{label}: invalid screenshot length")
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{label}.png").write_bytes(png(shot["width"], shot["height"], rgba))
    return {"case": label, "world_screen_camera": actual, "steps": int.from_bytes(emu.read("scroll_step_count", 2), "little"),
            "crtc": {"R1": regs[1], "R6": regs[6], "R9": regs[9], "R12": regs[12], "R13": regs[13]},
            "screenshot_sha256": hashlib.sha256(rgba).hexdigest(), "frame": emu.frames}


def check_crtc_probe(emu: BluePixel, name: str, out: Path) -> dict:
    """Show that changing R13 moves pixels while a known VRAM row stays put."""
    width_bytes = 64 if name == "scroll0" else 32
    start_r13 = 0
    start_address = 0xC000
    pattern = bytes(((i * 73) ^ (i * i * 17)) & 0xFF for i in range(width_bytes))
    for offset, value in enumerate(pattern):
        emu.write(start_address + offset, value)
    emu.run(2)
    before = emu.capture()
    emu.key(5, 0xEF, True)  # H
    emu.run(3)
    emu.key(5, 0xEF, False)
    emu.run(5)
    after = emu.capture()
    if emu.read("scroll_probe_offset") != b"\x01" or after["metadata"]["crtc_registers"][13] != start_r13 + 1:
        raise RuntimeError(f"{name}: R13 probe did not start")
    if emu.read(start_address, width_bytes) != pattern:
        raise RuntimeError(f"{name}: probe changed the backing pattern")
    a = base64.b64decode(after["data_base64"], validate=True)
    b = base64.b64decode(before["data_base64"], validate=True)
    screen_width = before["width"]
    # BluePixel's 768x270 RGBA capture places the first displayed scanline at
    # y=35. Compare its interior at candidate displacements of 0..32 pixels.
    def mismatch(dx: int) -> int:
        return sum(a[(35 * screen_width + x) * 4:(35 * screen_width + x) * 4 + 3]
                   != b[(35 * screen_width + x + dx) * 4:(35 * screen_width + x + dx) * 4 + 3]
                   for x in range(192, 400, 4))

    scores = {dx: mismatch(dx) for dx in range(0, 33, 4)}
    if min(scores, key=scores.get) != 16 or scores[16] > 8:
        raise RuntimeError(f"{name}: R13=1 did not move the pattern by 16 output pixels: {scores}")
    out.mkdir(parents=True, exist_ok=True)
    (out / "probe-r13-1.png").write_bytes(png(after["width"], after["height"], a))
    emu.key(5, 0xEF, True)
    emu.run(5)
    emu.key(5, 0xEF, False)
    emu.run(5)
    if emu.read("scroll_probe_offset") != b"\x00" or emu.capture()["metadata"]["crtc_registers"][13] != start_r13:
        raise RuntimeError(f"{name}: R13 probe did not restore the baseline")
    return {"case": "crtc_r13_probe", "observed_output_shift_pixels": 16,
            "backing_pattern_unchanged": True, "r13_before": start_r13,
            "r13_during": start_r13 + 1, "r13_after": start_r13}


def check_border_fill_probe(emu: BluePixel, name: str, out: Path) -> dict:
    """One east tile using CRTC start and a strip filled after active scanout."""
    mode1 = name == "scroll1"
    tile_width = 2 if mode1 else 4
    expected_r13 = 1 if mode1 else 2
    start_r13 = 0
    expected_output_shift = 16 if mode1 else 32
    profile = json.loads((ROOT / f"framework/profiles/scroll-mode{1 if mode1 else 0}-128x128.json").read_text())
    first = emu.capture()
    original = base64.b64decode(first["data_base64"], validate=True)
    width, height = first["width"], first["height"]

    def unchanged_outside_player(rgba: bytes) -> bool:
        for y in range(height):
            row = y * width * 4
            if 75 <= y < 125:
                if rgba[row:row + 320 * 4] != original[row:row + 320 * 4]:
                    return False
                if rgba[row + 440 * 4:row + width * 4] != original[row + 440 * 4:row + width * 4]:
                    return False
            elif rgba[row:row + width * 4] != original[row:row + width * 4]:
                return False
        return True

    emu.key(5, 0xDF, True)  # J
    frames_before_switch = 0
    try:
        for _ in range(8):
            emu.run(1)
            shot = emu.capture()
            if shot["metadata"]["crtc_registers"][13] == start_r13 + expected_r13:
                break
            frames_before_switch += 1
            if not unchanged_outside_player(base64.b64decode(shot["data_base64"], validate=True)):
                raise RuntimeError(f"{name}: visible map changed before the CRTC switch")
        else:
            raise RuntimeError(f"{name}: timed border-fill probe did not switch R13")
    finally:
        emu.key(5, 0xDF, False)
    emu.run(2)
    shifted = emu.capture()
    after = base64.b64decode(shifted["data_base64"], validate=True)
    if emu.read("scroll_probe_offset") != bytes((expected_r13,)):
        raise RuntimeError(f"{name}: probe origin mirror is wrong")

    # The overlapping interior must be the old pixels translated by one tile.
    # The player is deliberately absent in this sprite-free probe.
    for y in range(40, 160, 4):
        if 85 <= y <= 115:
            continue
        for x in range(300, 450, 4):
            dest = (y * width + x) * 4
            source = (y * width + x + expected_output_shift) * 4
            if after[dest:dest + 3] != original[source:source + 3]:
                raise RuntimeError(f"{name}: interior did not shift by one tile at ({x},{y})")

    # The entering column is a known tile-2 cross, including all eight raster
    # lines. This checks every physical row, not only its first byte.
    for y in range(128):
        address = address_at_origin(profile, profile["width_bytes"] - tile_width, y, tile_width)
        expected = b"\xff" * tile_width if y % 8 == 0 else b"\xff" + b"\x00" * (tile_width - 1)
        if emu.read(address, tile_width) != expected:
            raise RuntimeError(f"{name}: entering column differs at scanline {y}, address {address:#06x}")
    out.mkdir(parents=True, exist_ok=True)
    (out / "probe-east-tile.png").write_bytes(png(width, height, after))
    emu.key(5, 0xEF, True)  # H returns to fixed-origin baseline
    emu.run(5)
    emu.key(5, 0xEF, False)
    emu.run(5)
    if emu.read("scroll_probe_offset") != b"\x00" or emu.capture()["metadata"]["crtc_registers"][13] != start_r13:
        raise RuntimeError(f"{name}: tile probe did not restore the baseline")
    return {"case": "border_fill_east_tile", "r13": start_r13 + expected_r13,
            "observed_output_shift_pixels": expected_output_shift,
            "frames_before_switch": frames_before_switch, "rows_checked": 128,
            "visible_map_unchanged_before_switch": True}


def check_south_probe(emu: BluePixel, name: str, out: Path) -> dict:
    """Check one vertical character-row shift and its eight incoming scanlines."""
    mode1 = name == "scroll1"
    row_width = 32 if mode1 else 64
    r13_step = row_width // 2
    profile = json.loads((ROOT / f"framework/profiles/scroll-mode{1 if mode1 else 0}-128x128.json").read_text())
    before = emu.capture()
    original = base64.b64decode(before["data_base64"], validate=True)
    emu.key(4, 0xDF, True)  # K
    emu.run(5)
    emu.key(4, 0xDF, False)
    emu.run(3)
    after_shot = emu.capture()
    after = base64.b64decode(after_shot["data_base64"], validate=True)
    if emu.read("scroll_probe_offset") != bytes((r13_step,)):
        raise RuntimeError(f"{name}: south probe did not set its origin mirror")
    if after_shot["metadata"]["crtc_registers"][13] != r13_step:
        raise RuntimeError(f"{name}: south probe did not switch R13")
    for y in range(120, 128):
        address = address_at_origin(profile, 0, y, row_width)
        if emu.read(address, row_width) != b"\xff" * row_width:
            raise RuntimeError(f"{name}: entering south row differs at y={y}")
    width = before["width"]
    def mismatches(dy: int) -> int:
        return sum(after[(y * width + x) * 4:(y * width + x) * 4 + 3]
                   != original[((y + dy) * width + x) * 4:((y + dy) * width + x) * 4 + 3]
                   for y in range(40, 145, 3) for x in range(300, 450, 5))
    scores = {dy: mismatches(dy) for dy in range(0, 17)}
    if min(scores, key=scores.get) != 8:
        raise RuntimeError(f"{name}: south probe did not shift one row: {scores}")
    out.mkdir(parents=True, exist_ok=True)
    (out / "probe-south-row.png").write_bytes(png(after_shot["width"], after_shot["height"], after))
    emu.key(5, 0xEF, True)  # H restores the baseline
    emu.run(5)
    emu.key(5, 0xEF, False)
    emu.run(5)
    if emu.read("scroll_probe_offset") != b"\x00" or emu.capture()["metadata"]["crtc_registers"][13] != 0:
        raise RuntimeError(f"{name}: south probe did not restore baseline")
    return {"case": "south_row_probe", "r13": r13_step, "observed_shift_scanlines": 8,
            "incoming_scanlines_checked": 8}


def check_reverse_probe(emu: BluePixel, name: str, direction: str, out: Path) -> dict:
    """Verify a backward CRTC step across the 2 KiB raster-bank boundary."""
    mode1 = name == "scroll1"
    tile_width = 2 if mode1 else 4
    row_width = 32 if mode1 else 64
    offset = -tile_width if direction == "west" else -row_width
    r13 = 256 + offset // 2
    key_mask = 0xEF if direction == "west" else 0xF7  # L or I, row 4
    profile = json.loads((ROOT / f"framework/profiles/scroll-mode{1 if mode1 else 0}-128x128.json").read_text())
    first = emu.capture()
    original = base64.b64decode(first["data_base64"], validate=True)
    emu.key(4, key_mask, True)
    frames_before_switch = 0
    try:
        if direction == "west":
            for _ in range(8):
                emu.run(1)
                pending = emu.capture()
                if pending["metadata"]["crtc_registers"][13] == r13:
                    break
                frames_before_switch += 1
                rgba = base64.b64decode(pending["data_base64"], validate=True)
                width = pending["width"]
                for y in range(pending["height"]):
                    row = y * width * 4
                    if 75 <= y < 125:
                        unchanged = (rgba[row:row + 320 * 4] == original[row:row + 320 * 4]
                                     and rgba[row + 440 * 4:row + width * 4] == original[row + 440 * 4:row + width * 4])
                    else:
                        unchanged = rgba[row:row + width * 4] == original[row:row + width * 4]
                    if not unchanged:
                        raise RuntimeError(f"{name} west: visible map changed before CRTC switch at y={y}")
            else:
                raise RuntimeError(f"{name} west: CRTC switch did not occur")
        else:
            emu.run(6)
    finally:
        emu.key(4, key_mask, False)
    emu.run(3)
    shot = emu.capture()
    after = base64.b64decode(shot["data_base64"], validate=True)
    regs = shot["metadata"]["crtc_registers"]
    if (regs[12], regs[13]) != (0x33, r13) or emu.read("scroll_probe_offset") != bytes((r13,)):
        raise RuntimeError(f"{name} {direction}: origin not set: R12/R13={regs[12:14]}")
    if direction == "west":
        for y in range(128):
            address = address_at_origin(profile, 0, y, offset)
            expected = b"\xff" * tile_width if y % 8 == 0 else b"\xff" + b"\x00" * (tile_width - 1)
            if emu.read(address, tile_width) != expected:
                raise RuntimeError(f"{name} west: entering strip differs at y={y}, {address:#06x}")
    else:
        for y in range(8):
            address = address_at_origin(profile, 0, y, offset)
            if emu.read(address, row_width) != b"\xff" * row_width:
                raise RuntimeError(f"{name} north: entering row differs at y={y}, {address:#06x}")
    width = shot["width"]
    def mismatches(dx: int, dy: int) -> int:
        return sum(after[(y * width + x) * 4:(y * width + x) * 4 + 3]
                   != original[((y + dy) * width + x + dx) * 4:((y + dy) * width + x + dx) * 4 + 3]
                   for y in range(40, 145, 3) if not 75 <= y <= 125
                   for x in range(300, 450, 5))
    shift = 16 if mode1 else 32
    scores = ({dx: mismatches(dx, 0) for dx in range(-40, 9, 4)} if direction == "west"
              else {dy: mismatches(0, dy) for dy in range(-16, 5)})
    expected_shift = -shift if direction == "west" else -8
    if min(scores, key=scores.get) != expected_shift:
        raise RuntimeError(f"{name} {direction}: displayed shift differs: {scores}")
    out.mkdir(parents=True, exist_ok=True)
    (out / f"probe-{direction}.png").write_bytes(png(shot["width"], shot["height"], after))
    emu.key(5, 0xEF, True)  # H restores both CRTC registers
    emu.run(5)
    emu.key(5, 0xEF, False)
    emu.run(5)
    restored = emu.capture()["metadata"]["crtc_registers"]
    if emu.read("scroll_probe_offset") != b"\x00" or (restored[12], restored[13]) != (48, 0):
        raise RuntimeError(f"{name} {direction}: origin not restored")
    return {"case": f"{direction}_probe", "r12": 0x33, "r13": r13,
            "observed_output_shift": expected_shift, "incoming_lines_checked": 128 if direction == "west" else 8,
            "frames_before_switch": frames_before_switch}


def check_hardware_route(emu: BluePixel, initial: bytes, name: str, out: Path) -> dict:
    """Compare real player/camera movement against the full redraw at all edges."""
    route = (
        ("west", (0, 92, 0, 60, 0, 4)),
        ("north", (0, 0, 0, 0, 0, 0)),
        ("east", (184, 0, 120, 0, 8, 0)),
        ("south", (184, 184, 120, 120, 8, 8)),
    )
    tile_width = 2 if name == "scroll1" else 4
    row_width = 32 if name == "scroll1" else 64
    captures: dict[tuple[bool, str], bytes] = {}
    observations = []
    for hardware in (False, True):
        emu.restore(initial)
        if hardware:
            emu.key(6, 0xF7, True)  # T enables the hardware camera path
            emu.run(5)
            emu.key(6, 0xF7, False)
            emu.run(5)
            if emu.read("scroll_hw_enabled") != b"\x01":
                raise RuntimeError(f"{name}: hardware path did not enable")
        for direction, expected in route:
            row, mask = KEYS[direction]
            emu.key(row, mask, True)
            try:
                for frame in range(800):
                    emu.run(1)
                    if emu.read("scroll_status") != b"\x5a":
                        raise RuntimeError(f"{name} {direction}: program data corrupted")
                    if state(emu) == expected and emu.read("scroll_blocked") == b"\x01":
                        break
                else:
                    raise RuntimeError(f"{name} {direction}: edge timeout at {state(emu)}")
            finally:
                emu.key(row, mask, False)
            emu.run(5)
            if state(emu) != expected:
                raise RuntimeError(f"{name} {direction}: unstable edge state {state(emu)}")
            shot = emu.capture()
            rgba = base64.b64decode(shot["data_base64"], validate=True)
            captures[hardware, direction] = rgba
            regs = shot["metadata"]["crtc_registers"]
            if hardware:
                offset = (expected[4] - 4) * tile_width + (expected[5] - 4) * row_width
                ma = (offset // 2) & 0x3FF
                if (regs[12], regs[13]) != (0x30 | (ma >> 8), ma & 0xFF):
                    raise RuntimeError(f"{name} {direction}: wrong CRTC origin {regs[12:14]}")
                pointer_origin = int.from_bytes(emu.read("fwk_video_origin_bytes", 2), "little")
                if pointer_origin != ma * 2:
                    raise RuntimeError(f"{name} {direction}: pointer origin {pointer_origin} != {ma * 2}")
                if rgba != captures[False, direction]:
                    different = sum(rgba[i:i + 3] != captures[False, direction][i:i + 3]
                                    for i in range(0, len(rgba), 4))
                    raise RuntimeError(f"{name} {direction}: {different} pixels differ from full redraw")
                out.mkdir(parents=True, exist_ok=True)
                (out / f"hardware-{direction}-edge.png").write_bytes(
                    png(shot["width"], shot["height"], rgba))
            observations.append({"direction": direction, "hardware": hardware, "frames_to_edge": frame + 1,
                                 "state": expected, "r12": regs[12], "r13": regs[13]})
    return {"case": "hardware_four_edges", "exact_pixel_matches": 4,
            "observations": observations}


def check_hardware_cadence(emu: BluePixel, initial: bytes, name: str) -> dict:
    """Measure pauses at four westward camera changes in the opt-in path."""
    emu.restore(initial)
    emu.key(6, 0xF7, True)  # T
    emu.run(5)
    emu.key(6, 0xF7, False)
    emu.run(5)
    old_steps = int.from_bytes(emu.read("scroll_step_count", 2), "little")
    old_camera = state(emu)[4]
    last_move_frame = 0
    gaps = []
    row, mask = KEYS["west"]
    emu.key(row, mask, True)
    try:
        for frame in range(120):
            emu.run(1)
            steps = int.from_bytes(emu.read("scroll_step_count", 2), "little")
            camera = state(emu)[4]
            if steps != old_steps:
                if camera != old_camera:
                    gaps.append(frame - last_move_frame)
                    if camera != 4 - len(gaps):
                        raise RuntimeError(f"{name}: camera skipped a westward tile")
                old_steps = steps
                old_camera = camera
                last_move_frame = frame
            if len(gaps) == 4:
                break
        else:
            raise RuntimeError(f"{name}: westward camera cadence timed out")
    finally:
        emu.key(row, mask, False)
    if any(gap > 2 for gap in gaps):
        raise RuntimeError(f"{name}: camera pause exceeded two frames: {gaps}")
    return {"case": "hardware_west_cadence", "camera_step_gaps_frames": gaps}


def check_smooth_route(emu: BluePixel, initial: bytes, name: str, out: Path) -> dict:
    """Check byte-sized camera steps and exact edge images in both modes."""
    step = 4 if name == "scroll1" else 2
    route = (
        ("west", (0, 92, 0, 60, 0, 4)),
        ("north", (0, 0, 0, 0, 0, 0)),
        ("east", (184, 0, 120, 0, 8, 0)),
        ("south", (184, 184, 120, 120, 8, 8)),
    )
    emu.restore(initial)
    before = emu.capture()
    original = base64.b64decode(before["data_base64"], validate=True)
    emu.key(7, 0xEF, True)  # S enables the software byte-step camera
    emu.run(1)
    emu.key(7, 0xEF, False)
    emu.run(3)
    if emu.read("scroll_smooth_enabled") != b"\x01":
        raise RuntimeError(f"{name}: smooth path did not enable")
    row, mask = KEYS["west"]
    emu.key(row, mask, True)
    try:
        for _ in range(100):
            emu.run(1)
            if emu.read("scroll_smooth_camera_x")[0] < 32:
                break
        else:
            raise RuntimeError(f"{name}: first smooth camera step timed out")
    finally:
        emu.key(row, mask, False)
    emu.run(3)
    if emu.read("scroll_smooth_camera_x")[0] != 32 - step:
        raise RuntimeError(f"{name}: first west step was not one video byte")
    shifted_shot = emu.capture()
    shifted = base64.b64decode(shifted_shot["data_base64"], validate=True)
    width = before["width"]
    # The emulator renders one video byte as eight output pixels in both modes.
    # Avoid the newly exposed left byte and the player's old/new rectangle.
    for y in range(44, 150, 4):
        if 92 <= y < 106:
            continue
        for x in range(264, 450, 4):
            source = (y * width + x - 8) * 4
            target = (y * width + x) * 4
            if original[source:source + 3] != shifted[target:target + 3]:
                raise RuntimeError(f"{name}: first smooth west step differs at ({x},{y})")

    captures: dict[tuple[bool, str], bytes] = {}
    observations = []
    for smooth in (False, True):
        emu.restore(initial)
        if smooth:
            emu.key(7, 0xEF, True)
            emu.run(1)
            emu.key(7, 0xEF, False)
            emu.run(3)
        for direction, expected in route:
            row, mask = KEYS[direction]
            emu.key(row, mask, True)
            try:
                for frame in range(1000):
                    emu.run(1)
                    if state(emu) == expected and emu.read("scroll_blocked") == b"\x01":
                        break
                else:
                    raise RuntimeError(f"{name} smooth {direction}: edge timeout at {state(emu)}")
            finally:
                emu.key(row, mask, False)
            emu.run(4)
            if emu.read("scroll_status") != b"\x5a" or state(emu) != expected:
                raise RuntimeError(f"{name} smooth {direction}: state changed after reaching edge")
            shot = emu.capture()
            rgba = base64.b64decode(shot["data_base64"], validate=True)
            captures[smooth, direction] = rgba
            if smooth:
                camera_px = emu.read("scroll_smooth_camera_x")[0], emu.read("scroll_smooth_camera_y")[0]
                if camera_px != (expected[4] * 8, expected[5] * 8):
                    raise RuntimeError(f"{name} smooth {direction}: camera pixel position {camera_px}")
                if rgba != captures[False, direction]:
                    different = sum(rgba[i:i + 3] != captures[False, direction][i:i + 3]
                                    for i in range(0, len(rgba), 4))
                    raise RuntimeError(f"{name} smooth {direction}: {different} pixels differ at the edge")
                out.mkdir(parents=True, exist_ok=True)
                (out / f"smooth-{direction}-edge.png").write_bytes(png(shot["width"], shot["height"], rgba))
            observations.append({"direction": direction, "smooth": smooth, "frames_to_edge": frame + 1})
    return {"case": "smooth_byte_step_four_edges", "camera_step_pixels": step,
            "first_step_screen_shift_output_pixels": 8, "exact_pixel_matches": 4,
            "observations": observations}


def run_mode(emu_binary: Path, rom_dir: Path, name: str, out: Path) -> list[dict]:
    disk = ROOT / f"build/{name}/{name}.dsk"
    symbols = ROOT / f"build/{name}/obj/{name}.noi"
    if not disk.exists() or not symbols.exists():
        raise RuntimeError(f"build {name} before running the smoke test")
    with BluePixel(emu_binary, rom_dir) as emu:
        emu.load(disk, symbols)
        emu.boot(f'run"{name}', "scroll_status", 0x5A)
        initial = emu.save()
        rows = [check(emu, "initial", (92, 92, 60, 60, 4, 4), out)]

        scenarios = (
            ("solid_north", ("north",), (92, 72, 60, 40, 4, 4)),
            ("object_south", ("south",), (92, 120, 60, 88, 4, 4)),
            ("character_east", ("east",), (120, 92, 88, 60, 4, 4)),
            ("west_edge", ("west",), (0, 92, 0, 60, 0, 4)),
            ("east_edge", ("south", "east"), (184, 120, 120, 88, 8, 4)),
            ("north_edge", ("west", "north"), (0, 0, 0, 0, 0, 0)),
            ("south_edge", ("west", "south"), (0, 184, 0, 120, 0, 8)),
        )
        for label, directions, expected in scenarios:
            emu.restore(initial)
            for direction in directions:
                hold(emu, direction)
            rows.append(check(emu, label, expected, out))
            if emu.read("scroll_blocked") != b"\x01":
                raise RuntimeError(f"{label}: expected a blocked final move")
        emu.restore(initial)
        rows.append(check_crtc_probe(emu, name, out))
        emu.restore(initial)
        rows.append(check_border_fill_probe(emu, name, out))
        emu.restore(initial)
        rows.append(check_south_probe(emu, name, out))
        for direction in ("west", "north"):
            emu.restore(initial)
            rows.append(check_reverse_probe(emu, name, direction, out))
        rows.append(check_hardware_route(emu, initial, name, out))
        rows.append(check_hardware_cadence(emu, initial, name))
        rows.append(check_smooth_route(emu, initial, name, out))
        return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emulator", type=Path, default=ROOT.parent / "bluepixel/build/bluepixel-headless")
    parser.add_argument("--rom-dir", type=Path, default=ROOT.parent / "bluepixel/web/roms")
    parser.add_argument("--out", type=Path, default=ROOT / "build/scroll-evidence")
    args = parser.parse_args()
    results = {name: run_mode(args.emulator, args.rom_dir, name, args.out / "6128" / name)
               for name in ("scroll0", "scroll1")}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "baseline-6128.json").write_text(json.dumps(results, indent=2) + "\n")
    print("scroll: Mode 0/1, baseline, four-direction probes, hardware route and byte-step route passed on BluePixel CPC 6128")


if __name__ == "__main__":
    main()
