#!/usr/bin/env python3
"""Optional AmSpiriT-Lite smoke test using the shared test DSK."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.build_test_disk import program_bin_name
DEFAULT_EMULATOR = ROOT.parent / "tools" / "amspirit-lite" / "run.sh"
API = "http://127.0.0.1:6128"


def get(path: str):
    with urllib.request.urlopen(API + path, timeout=5) as reply:
        return json.load(reply)


def get_bytes(path: str) -> bytes:
    with urllib.request.urlopen(API + path, timeout=10) as reply:
        return reply.read()


def post(path: str, data: dict):
    request = urllib.request.Request(
        API + path,
        data=json.dumps(data).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=5) as reply:
        return json.load(reply)


def post_text(path: str, data: str):
    request = urllib.request.Request(
        API + path,
        data=data.encode(),
        method="POST",
        headers={"Content-Type": "text/plain"},
    )
    with urllib.request.urlopen(request, timeout=5) as reply:
        return json.load(reply)


def write_ram(address: int, data: bytes) -> None:
    post("/api/ram", {"addr": address, "data": data.hex()})


def ram(address: int, length: int) -> bytes:
    return bytes.fromhex(get(f"/api/ram?addr={address}&len={length}")["hex"])


def standard_screen_address(x: int, y: int) -> int:
    return 0xC000 + (y & 7) * 0x800 + (y >> 3) * 80 + x


# SHA-256 prefixes (16 hex) of the HUD fields as drawn by examples/platformer
# for each state, captured from the original game in the emulator. The ECS
# port must draw the same pixels. Fields: score x=0..19, hint x=24..59,
# lives x=64..79, scanlines 8..23.
PLATFORMER_HUD_GOLDEN = {
    "score": {
        0: "607d3e8dc479cc70",
        1: "98a7f1b81e2a4f85",
        2: "ccb4bf7a44abd5a7",
        3: "10bcff8b921e5f70",
        4: "46476f15b93c33b4",  # original drawn from a clean state (0 -> 4)
    },
    "hint": {"collect": "7ece9d60ac964357", "go": "caa420c76c5a55ef"},
    "lives": {
        10: "94c72e01fe622897",
        9: "98bfe8aeef324501",
        8: "895a2b856aa2ffce",
        7: "b6bf0249fbb687d9",
        6: "4ae06a4c6acb2312",
        5: "1441684c88eeeaf0",
        4: "b603fb28053bc410",
        3: "c9e713042a7188f5",
        2: "8fae2ed039ebbdba",
        1: "5b3cc668b27326e9",
        0: "c77da37b7a8aa21b",
    },
}
PLATFORMER_HUD_FIELDS = {"score": (0, 20), "hint": (24, 36), "lives": (64, 16)}


def hud_field_hash(field: str) -> str:
    x0, width = PLATFORMER_HUD_FIELDS[field]
    data = b"".join(ram(standard_screen_address(x0, y), width) for y in range(8, 24))
    return hashlib.sha256(data).hexdigest()[:16]


# Screen bands (y0, y1, x0, x1) that no entity ever crosses, hashed (SHA-256, 16 hex)
# as examples/platformer draws them on each level. Captured from the original in
# the emulator (level 2 reached through the door).
PLATFORMER_BANDS = {"A": (40, 56, 0, 80), "B": (64, 80, 12, 64), "C": (96, 112, 12, 64), "D": (136, 152, 12, 64)}
PLATFORMER_BAND_GOLDEN = {
    0: {"A": "aacf1deffa3d11f9", "B": "a259b7483b1637e6", "C": "3852c28a157a0406", "D": "b19bb908d872e650"},
    1: {"A": "9b1f189d3b4fa8f0", "B": "f9ae611cee4c42f1", "C": "c880bebb5720285a", "D": "e0084b66cb4a03e2"},
}


def band_hash(key: str) -> str:
    y0, y1, x0, x1 = PLATFORMER_BANDS[key]
    data = b"".join(ram(standard_screen_address(x0, y), x1 - x0) for y in range(y0, y1))
    return hashlib.sha256(data).hexdigest()[:16]


def tmx_layer(layer: str) -> bytes:
    """Tile ids minus one for a layer of examples/platformer_ecs/assets/src/level.tmx."""
    text = (ROOT / "examples/platformer_ecs/assets/src/level.tmx").read_text()
    match = re.search(rf'<layer[^>]*name="{layer}"[^>]*>\s*<data encoding="csv">(.*?)</data>', text, re.S)
    return bytes(int(v) - 1 for v in match.group(1).replace("\n", "").split(",") if v.strip())


def symbol(noi: Path, name: str) -> int:
    table = dict(re.findall(r"^DEF (\S+) 0x([0-9A-Fa-f]+)", noi.read_text(), re.MULTILINE))
    return int(table[name], 16)


def asm_hex_bytes_between(path: Path, start: str, end: str | None) -> bytes:
    source = path.read_text(encoding="ascii").split(start, 1)[1]
    if end is not None:
        source = source.split(end, 1)[0]
    return bytes(int(value, 16) for value in re.findall(r"0x([0-9A-Fa-f]{2})", source))


def wait_for(predicate, timeout: float, label: str):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            value = predicate()
            if value:
                return value
        except OSError:
            pass
        time.sleep(0.25)
    raise RuntimeError(f"timeout waiting for {label}")


def hold_keys(*, row0: int = 0xFF, row1: int = 0xFF, frames: int, after: int = 2) -> None:
    pressed = [row0, row1] + [0xFF] * 14
    released = [0xFF] * 16
    marker = f"GLASNOST_INPUT_DONE_{time.monotonic_ns()}"
    script = (
        f"keyboard_write({','.join(map(str, pressed))})\n"
        f"wait_frames({frames - 1})\n"
        f"keyboard_write({','.join(map(str, released))})\n"
        f"wait_frames({after})\n"
        f'print("{marker}")\n'
    )
    post_text("/api/script?lang=lua", script)
    wait_for(
        lambda: (status := get("/api/script"))["running"] is False and marker in status["output"],
        15,
        "held keyboard input",
    )


def hold_cursor_right(frames: int) -> None:
    hold_keys(row0=0xFD, frames=frames)


def set_keys(*, row0: int = 0xFF, row1: int = 0xFF) -> None:
    values = [row0, row1] + [0xFF] * 14
    marker = f"GLASNOST_KEYS_SET_{time.monotonic_ns()}"
    post_text(
        "/api/script?lang=lua",
        f"keyboard_write({','.join(map(str, values))})\nprint(\"{marker}\")\n",
    )
    wait_for(
        lambda: (status := get("/api/script"))["running"] is False
        and marker in status["output"],
        5,
        "keyboard state update",
    )


def hold_keys_until(
    predicate,
    *,
    row0: int = 0xFF,
    row1: int = 0xFF,
    timeout: float,
    label: str,
) -> None:
    """Hold a matrix state until observable game state reaches a target."""
    set_keys(row0=row0, row1=row1)
    try:
        wait_for(predicate, timeout, label)
    finally:
        set_keys()


def run_example(
    name: str,
    emulator: Path,
    model: str,
    screenshot_dir: Path | None = None,
    platformer_regressions_only: bool = False,
) -> None:
    directory = ROOT / ".build" / name
    dsk = ROOT / ".build" / "tests" / "GlasnostFWK-tests.dsk"
    noi = directory / "obj" / f"{name}.noi"
    frame = symbol(noi, "fwk_system_frame_count")
    process = subprocess.Popen(
        [str(emulator), "--web-server", "--model", model, "--ram", "128", str(dsk)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        wait_for(lambda: get("/api/ping").get("ok"), 30, "emulator API")
        time.sleep(6)  # ROM/AMSDOS boot; sending RUN earlier is nondeterministic
        run_name = Path(program_bin_name(ROOT, name)).stem
        post("/api/keytype", {"text": f'run"{run_name}\n'})
        wait_for(lambda: int.from_bytes(ram(frame, 2), "little") > 2, 30, f"{name} frame loop")
        if name == "board":
            status = symbol(noi, "board_text_status")
            wait_for(lambda: ram(status, 1) == b"\xA5", 5, "sprite-font rendering")
            if ram(0x0100, 16) != bytes.fromhex(
                "ffaa5500aaaa00005500550000000000"
            ):
                raise RuntimeError("text transparency table was not installed at 0x0100")
            title = b"".join(
                ram(standard_screen_address(12, y), 26) for y in range(16, 25)
            )
            number_42 = b"".join(
                ram(standard_screen_address(28, y), 4) for y in range(32, 37)
            )
            number_7 = b"".join(
                ram(standard_screen_address(28, y), 2) for y in range(40, 45)
            )
            number_255 = b"".join(
                ram(standard_screen_address(28, y), 6) for y in range(48, 53)
            )
            colorized_8s = b"".join(
                ram(standard_screen_address(28, y), 30) for y in range(56, 61)
            )
            if not any(title):
                raise RuntimeError("regular sprite-font title is absent from video RAM")
            expected_42 = bytes.fromhex(
                "aaaaffaa aaaa00aa ffaaffaa 00aaaa00 00aaffaa".replace(" ", "")
            )
            expected_7 = bytes.fromhex("ffaa00aa00aa00aa00aa")
            expected_255 = bytes.fromhex(
                "ffaaffaaffaa 00aaaa00aa00 ffaaffaaffaa "
                "aa0000aa00aa ffaaffaaffaa".replace(" ", "")
            )
            small = asm_hex_bytes_between(
                ROOT / "src/ui/text.inc",
                "_fwk_text_default_small_digits:",
                None,
            )
            color_table = asm_hex_bytes_between(
                ROOT / "src/ui/text.s", "_fwk_text_swap_colors:", '.include "ui/text.inc"'
            )
            digit_8 = small[8 * 10 : 9 * 10]
            expected_colorized_8s = bytearray()
            for row in range(5):
                source_pair = digit_8[row * 2 : row * 2 + 2]
                for color in range(15):
                    replacements = color_table[color * 4 : color * 4 + 4]
                    mapping = dict(zip((0x55, 0xBF, 0xFF, 0xAA), replacements))
                    expected_colorized_8s.extend(mapping.get(value, value) for value in source_pair)
            if (
                number_42 != expected_42
                or number_7 != expected_7
                or number_255 != expected_255
                or colorized_8s != expected_colorized_8s
            ):
                raise RuntimeError(
                    "small sprite-font numbers differ from their source pixels: "
                    f"42={number_42.hex()} 7={number_7.hex()} "
                    f"255={number_255.hex()} colors/8={colorized_8s.hex()}"
                )
        if name == "video" and ram(0xC7D0, 1) != b"\xA5":
            raise RuntimeError("video hole witness was overwritten")
        if name == "resources128":
            bank_flag = symbol(noi, "fwk_bank_has_128k")
            if model == "6128":
                if ram(bank_flag, 1) != b"\x01" or ram(0x9008, 8) != b"GLASNOST":
                    raise RuntimeError("128K bank detection/roundtrip failed")
            elif ram(bank_flag, 1) != b"\x00":
                raise RuntimeError("64K profile was incorrectly reported as 128K")
        if name == "diskload":
            status = symbol(noi, "diskload_status")
            raw_length = symbol(noi, "diskload_raw_length")
            packed_length = symbol(noi, "diskload_packed_length")
            result = ram(status, 1)
            if result != b"\x5A":
                raise RuntimeError(f"disk/ZX7 validation failed with status {result.hex()}")
            if int.from_bytes(ram(raw_length, 2), "little") != 256:
                raise RuntimeError("AMSDOS raw payload length is not 256")
            if int.from_bytes(ram(packed_length, 2), "little") != 23:
                raise RuntimeError("AMSDOS ZX7 payload length is not 23")
            witness = bytes.fromhex("004c41534e4f53542d4449534b2d5a58") * 16
            if ram(0x9000, 256) != witness:
                raise RuntimeError("raw payload read from DSK differs from source")
            if ram(0x9400, 256) != witness:
                raise RuntimeError("ZX7 decompressed payload differs from source")
        if name == "ecsmanager":
            status = symbol(noi, "ecsmanager_status")
            wait_for(lambda: ram(status, 1) == b"\x5A", 5, "ECS manager lifecycle")
            manager = symbol(noi, "ecsmanager_manager")
            storage = symbol(noi, "ecsmanager_storage")
            descriptor = ram(manager, 8)
            if descriptor[2:] != bytes((3, 32, 3, 3, 0, 1)):
                raise RuntimeError(
                    "ECS manager capacity/stride/counts/lock/flags differ: "
                    f"{descriptor.hex()}"
                )
            slots = ram(storage, 96)
            if any(slots[offset : offset + 3] != b"\x0F\x00\x01" for offset in (0, 32, 64)):
                raise RuntimeError("ECS stable slots do not retain mask/status")
            if not slots[32 + 18] & 0x02:
                raise RuntimeError("ECS enable did not mark render dirty")
        if name == "ecscollision":
            sys.path.insert(0, str(ROOT / "tools"))
            import ecs_collision_model as collision_model

            status = symbol(noi, "ecscollision_status")
            wait_for(lambda: ram(status, 1) != b"\x00", 20, "ECS collision scenario")
            if ram(status, 1) != b"\x5A":
                raise RuntimeError(f"ECS collision harness failed with status {ram(status, 1).hex()}")
            pointers = [
                int.from_bytes(ram(symbol(noi, "ecscollision_entities") + 2 * i, 2), "little")
                for i in range(5)
            ]
            length = int.from_bytes(ram(symbol(noi, "ecscollision_log_length"), 2), "little")
            actual = ram(symbol(noi, "ecscollision_log"), length)
            expected = collision_model.expected_log(pointers, symbol(noi, "ecscollision_manager"))
            if actual != expected:
                import difflib

                diff = "\n".join(
                    difflib.unified_diff(
                        collision_model.describe_log(expected, pointers),
                        collision_model.describe_log(actual, pointers),
                        "expected",
                        "actual",
                        lineterm="",
                    )
                )
                raise RuntimeError(f"ECS collision log differs from the model:\n{diff}")
        if name == "ecsanimation":
            sys.path.insert(0, str(ROOT / "tools"))
            import ecs_animation_model as animation_model

            status = symbol(noi, "ecsanimation_status")
            wait_for(lambda: ram(status, 1) != b"\x00", 20, "ECS animation scenario")
            if ram(status, 1) != b"\x5A":
                raise RuntimeError(f"ECS animation harness failed with status {ram(status, 1).hex()}")
            sprites = [
                int.from_bytes(ram(symbol(noi, "ecsanimation_sprites") + 2 * i, 2), "little")
                for i in range(5)
            ]
            length = int.from_bytes(ram(symbol(noi, "ecsanimation_log_length"), 2), "little")
            actual = ram(symbol(noi, "ecsanimation_log"), length)
            expected = animation_model.expected_log(sprites)
            if actual != expected:
                import difflib

                diff = "\n".join(
                    difflib.unified_diff(
                        animation_model.describe_log(expected, sprites),
                        animation_model.describe_log(actual, sprites),
                        "expected",
                        "actual",
                        lineterm="",
                    )
                )
                raise RuntimeError(f"ECS animation log differs from the model:\n{diff}")
        if name == "ecsrender":
            sys.path.insert(0, str(ROOT / "tools"))
            import ecs_render_model as render_model

            status = symbol(noi, "ecsrender_status")
            done = symbol(noi, "ecsrender_done")
            go = symbol(noi, "ecsrender_go")
            ideal = render_model.ideal_frames()
            for index, expected in enumerate(ideal):
                wait_for(
                    lambda: ram(done, 1)[0] == index + 1 or ram(status, 1) not in (b"\x00", b"\x5A"),
                    30,
                    f"ECS render frame {index}",
                )
                if ram(status, 1) not in (b"\x00", b"\x5A"):
                    raise RuntimeError(
                        f"ECS render harness failed with status {ram(status, 1).hex()} before frame {index}"
                    )
                vram = ram(0xC000, 0x4000)
                actual = b"".join(
                    vram[80 * (y // 8) + 2048 * (y % 8):][:80] for y in range(200)
                )
                if actual != expected:
                    lines = render_model.describe_diff(expected, actual)
                    raise RuntimeError(
                        f"ECS render frame {index} differs from the ideal image "
                        f"({sum(a != b for a, b in zip(expected, actual))} bytes):\n" + "\n".join(lines)
                    )
                write_ram(go, b"\x01")
            wait_for(lambda: ram(status, 1) == b"\x5A", 10, "ECS render checks")
            if ram(symbol(noi, "ecsrender_check_overflow"), 1) != bytes((0x0A,)):
                raise RuntimeError("a too small work array did not return FWK_ECS_ERR_OVERFLOW")
            if ram(symbol(noi, "ecsrender_check_order"), 1) != bytes((0x0B,)):
                raise RuntimeError("draw on an IDLE scene did not return FWK_ECS_ERR_RENDER")
        if name == "platformer_ecs":
            status = symbol(noi, "platformer_ecs_status")
            player = symbol(noi, "platformer_ecs_player")
            enemy_h = symbol(noi, "platformer_ecs_enemy_h")
            enemy_v = symbol(noi, "platformer_ecs_enemy_v")
            score = symbol(noi, "platformer_ecs_score")
            lives = symbol(noi, "platformer_ecs_lives")
            won = symbol(noi, "platformer_ecs_won")
            door = symbol(noi, "platformer_ecs_door")
            wait_for(lambda: ram(status, 1) == b"\x5A", 5, "ECS platformer initialization")
            storage = symbol(noi, "platformer_ecs_storage")
            if ram(storage + 2, 1) != b"\x01":
                raise RuntimeError("ECS platformer player slot is not ACTIVE")
            enemy_h_slot = int.from_bytes(ram(enemy_h, 2), "little")
            enemy_v_slot = int.from_bytes(ram(enemy_v, 2), "little")
            initial_h = ram(enemy_h_slot + 4, 2)
            initial_v = ram(enemy_v_slot + 4, 2)
            wait_for(
                lambda: ram(enemy_h_slot + 4, 1)[0] != initial_h[0]
                and ram(enemy_v_slot + 4, 2)[1] != initial_v[1],
                5,
                "ECS platformer behavior/motion of both enemy groups",
            )
            player_slot = int.from_bytes(ram(player, 2), "little")
            enemy_v2_slot = storage + 42
            door_slot = int.from_bytes(ram(door, 2), "little")
            items = symbol(noi, "platformer_ecs_items_storage")
            if ram(lives, 1) != b"\x0A" or ram(score, 1) != b"\x00" or ram(won, 1) != b"\x00":
                raise RuntimeError("ECS platformer initial lives/score/won are invalid")
            hud_dirty = symbol(noi, "platformer_ecs_hud_dirty")

            def check_hud(score_key, hint_key, lives_key, label):
                wait_for(lambda: ram(hud_dirty, 1) == b"\x00", 5, f"ECS platformer HUD drawn ({label})")
                time.sleep(0.2)
                for field, key in (("score", score_key), ("hint", hint_key), ("lives", lives_key)):
                    if key is None:
                        continue
                    got, want = hud_field_hash(field), PLATFORMER_HUD_GOLDEN[field][key]
                    if got != want:
                        raise RuntimeError(
                            f"ECS platformer HUD {field} differs from the original at {label}: "
                            f"{got} != {want} (state {key})"
                        )

            check_hud(0, "collect", 10, "start")
            level = symbol(noi, "platformer_ecs_level")

            def check_level_screen(level_index, label):
                for key, want in PLATFORMER_BAND_GOLDEN[level_index].items():
                    if band_hash(key) != want:
                        raise RuntimeError(
                            f"ECS platformer screen band {key} differs from the original at {label} "
                            f"(level {level_index + 1}): {band_hash(key)} != {want}"
                        )

            check_level_screen(0, "start")
            if ram(door_slot + 2, 1) != b"\x03":
                raise RuntimeError("ECS platformer door is not hidden (DISABLED) before the win")
            # Enemies patrol inside the original limits and animate.
            h_x, v_y, v2_y, h_sprites = [], [], [], set()
            deadline = time.time() + 3.0
            while time.time() < deadline:
                h_x.append(ram(enemy_h_slot + 4, 1)[0])
                v_y.append(ram(enemy_v_slot + 5, 1)[0])
                v2_y.append(ram(enemy_v2_slot + 5, 1)[0])
                h_sprites.add(ram(enemy_h_slot + 8, 2))
            if not (32 <= min(h_x) and max(h_x) <= 54 and max(h_x) - min(h_x) >= 8):
                raise RuntimeError(f"ECS platformer horizontal patrol out of limits: {min(h_x)}..{max(h_x)}")
            for label, ys in (("right vertical", v_y), ("left vertical", v2_y)):
                if not (56 <= min(ys) and max(ys) <= 152 and max(ys) - min(ys) >= 16):
                    raise RuntimeError(f"ECS platformer {label} patrol out of limits: {min(ys)}..{max(ys)}")
            if len(h_sprites) < 2:
                raise RuntimeError("ECS platformer enemy animation never changed the sprite")

            def player_state():
                state = ram(player_slot, 42)
                return {"x": state[4], "y": state[5], "vx": state[25], "vy": state[26], "flags": state[27]}

            def grounded() -> bool:
                return player_state()["flags"] & 0x03 == 0x02

            wait_for(
                lambda: ram(standard_screen_address(0, 192), 1) != b"\x00",
                30,
                "ECS platformer tilemap floor render",
            )
            # The player spawns at (16, 184) airborne and settles on the floor.
            wait_for(lambda: player_state()["y"] == 184 and grounded(), 10, "ECS platformer settles")
            for _ in range(4):
                resting = player_state()
                if resting["y"] != 184 or resting["vy"] != 0 or not grounded():
                    raise RuntimeError(f"ECS platformer does not rest on the floor: {resting}")
                time.sleep(0.25)

            # Same walkthrough as the original platformer smoke: it must collect
            # the four coins and win with the same inputs.
            set_keys(row0=0xFE)
            wait_for(lambda: player_state()["y"] < 184, 5, "ECS platformer first jump")
            set_keys()
            wait_for(lambda: player_state()["y"] == 184 and grounded(), 5, "ECS platformer first landing")
            if ram(score, 1) != b"\x01":
                raise RuntimeError("ECS platformer did not collect the lower-left coin and land")
            # Walking right is covered below; the jump under the lower-right coin
            # is made from an exact spot, clear of the one-way platform above
            # (its right end is at x=52) and within 4 bytes of the 4x8 coin.
            hold_keys_until(
                lambda: player_state()["x"] >= 24,
                row0=0xFD,
                timeout=10,
                label="ECS platformer right approach",
            )
            write_ram(player_slot + 4, bytes((56, 184)))
            wait_for(lambda: player_state()["x"] == 56, 5, "ECS platformer positioned under the coin")
            set_keys(row0=0xFE)
            wait_for(lambda: player_state()["y"] < 184, 5, "ECS platformer second jump")
            set_keys()
            try:
                wait_for(lambda: player_state()["y"] == 184 and grounded(), 5, "ECS platformer second landing")
            except RuntimeError as error:
                raise RuntimeError(f"{error}: player={player_state()}") from None
            if ram(score, 1) != b"\x02":
                raise RuntimeError(f"ECS platformer did not collect the lower-right coin: {player_state()}")
            check_hud(2, "collect", ram(lives, 1)[0], "two coins")
            hold_keys_until(
                lambda: player_state()["x"] <= 44,
                row1=0xFE,
                timeout=10,
                label="ECS platformer platform approach",
            )
            if not 32 <= player_state()["x"] <= 48:
                raise RuntimeError(f"ECS platformer platform approach ended at x={player_state()['x']}")
            for landing_y in (152, 120, 88, 56, 24):
                start_y = player_state()["y"]
                set_keys(row0=0xFE)
                wait_for(lambda: player_state()["y"] < start_y, 5, f"ECS platformer jump towards y={landing_y}")
                set_keys()
                try:
                    wait_for(
                        lambda: player_state()["y"] == landing_y and grounded(),
                        5,
                        f"ECS platformer landing at y={landing_y}",
                    )
                except RuntimeError as error:
                    raise RuntimeError(f"{error}: player={player_state()} start_y={start_y}") from None
            # On the top platform the coins sit at its ends. Walking into them
            # by key press overshoots with the emulator latency (the player
            # falls off the edge), so place the player next to each one.
            write_ram(player_slot + 4, bytes((18, 24)))
            wait_for(lambda: ram(score, 1) == b"\x03", 5, "ECS platformer upper-left coin")
            if ram(won, 1) != b"\x00" or ram(door_slot + 2, 1) != b"\x03":
                raise RuntimeError("ECS platformer won or showed the door with only three coins")
            # The last coin and an enemy meet on the same frame: the original
            # wins first and checks no enemy, so no life is lost.
            lives_at_win = ram(lives, 1)[0]
            write_ram(enemy_h_slot + 4, bytes((50, 24)))
            write_ram(player_slot + 4, bytes((50, 24)))
            try:
                wait_for(lambda: ram(score, 1) == b"\x04", 5, "ECS platformer upper-right coin")
            except RuntimeError as error:
                items = symbol(noi, "platformer_ecs_items_storage")
                coins = [ram(items + 42 * i + 2, 4).hex() for i in range(5)]
                raise RuntimeError(
                    f"{error}: player={player_state()} score={ram(score, 1).hex()} "
                    f"items(status,type,x,y)={coins}"
                ) from None
            wait_for(lambda: ram(won, 1) == b"\x01", 5, "ECS platformer win state")
            wait_for(lambda: ram(door_slot + 2, 1) == b"\x01", 5, "ECS platformer door appears")
            if ram(lives, 1)[0] != lives_at_win:
                raise RuntimeError("ECS platformer lost a life in the frame of the last coin")
            check_hud(4, "go", ram(lives, 1)[0], "all coins")
            # Every lives value draws the original's pixels (forced with write_ram,
            # safe here because enemies are harmless after the win).
            real_lives = ram(lives, 1)[0]
            for forced in range(10, -1, -1):
                write_ram(lives, bytes((forced,)))
                write_ram(hud_dirty, b"\x02")
                check_hud(None, None, forced, f"forced lives {forced}")
            write_ram(lives, bytes((real_lives,)))
            write_ram(hud_dirty, b"\x02")
            check_hud(None, None, real_lives, "lives restored")
            for slot in range(4):
                if ram(items + 42 * slot + 2, 1) != b"\x00":
                    raise RuntimeError(f"ECS platformer coin slot {slot} was not freed after collection")
            for coin_x in (16, 56):
                cell = b"".join(ram(standard_screen_address(coin_x, y), 4) for y in range(168, 176))
                if cell != bytes(32):
                    raise RuntimeError(f"ECS platformer left pixels in a collected coin cell x={coin_x}: {cell.hex()}")
            # After the win enemies stop hurting (as in the original).
            lives_before = ram(lives, 1)[0]
            ex, ey = ram(enemy_v2_slot + 4, 2)
            write_ram(player_slot + 4, bytes((ex, ey)))
            time.sleep(0.6)
            if ram(lives, 1)[0] != lives_before:
                raise RuntimeError("ECS platformer enemy cost a life after the win")
            # Fixed lives before the door, so "lives kept" does not depend on whether
            # an enemy happened to hit the player earlier. (The original redraws a
            # static "LIFE: 10" after the door; ECS shows the real count.)
            write_ram(lives, b"\x07")
            write_ram(hud_dirty, b"\x02")
            check_hud(None, None, 7, "lives before the door")
            lives_before = 7

            # Touching the door ends the win state and hides the door again.
            def touch_door():
                # The player falls while standing at the door: place it again
                # until a game frame sees the overlap.
                # Only while the door is visible: once the game reacted (new level
                # or hidden door) writing again would move the restarted player.
                if ram(won, 1) == b"\x01":
                    write_ram(player_slot + 4, bytes((72, 160)))
                return ram(won, 1) == b"\x00" and ram(door_slot + 2, 1) == b"\x03"

            wait_for(touch_door, 5, "ECS platformer door touch")
            # The door leads to the second level: same reset as at boot, new map,
            # lives kept.
            wait_for(lambda: ram(level, 1) == b"\x01", 5, "ECS platformer second level")
            # Everything starts from the row table: enemies at (or just past) their
            # start, not left where the first level ended.
            if not 36 <= ram(enemy_h_slot + 4, 1)[0] <= 55:
                raise RuntimeError(f"ECS platformer level 2 horizontal enemy not at its start: x={ram(enemy_h_slot + 4, 1)[0]}")
            for label, slot in (("left vertical", enemy_v2_slot), ("right vertical", enemy_v_slot)):
                if not 56 <= ram(slot + 5, 1)[0] <= 130:
                    raise RuntimeError(f"ECS platformer level 2 {label} enemy not at its start: y={ram(slot + 5, 1)[0]}")
            lives_kept = ram(lives, 1)[0]
            time.sleep(0.5)
            if lives_kept != lives_before:
                raise RuntimeError(f"ECS platformer door changed lives: {lives_before} -> {lives_kept}")
            if ram(score, 1) != b"\x00" or ram(won, 1) != b"\x00" or ram(door_slot + 2, 1) != b"\x03":
                raise RuntimeError("ECS platformer level 2 did not reset score, won and the hidden door")
            for slot in range(4):
                if ram(items + 42 * slot + 2, 1) != b"\x01":
                    raise RuntimeError(f"ECS platformer coin slot {slot} was not respawned on level 2")
            if (
                int.from_bytes(ram(player, 2), "little") != player_slot
                or int.from_bytes(ram(enemy_h, 2), "little") != enemy_h_slot
                or int.from_bytes(ram(enemy_v, 2), "little") != enemy_v_slot
            ):
                raise RuntimeError("ECS platformer level 2 moved the player or enemy slots")
            if ram(symbol(noi, "platformer_map2"), 500) != tmx_layer("level2"):
                raise RuntimeError("ECS platformer level 2 map in RAM differs from the level2 layer of the TMX")
            check_hud(0, "collect", lives_kept, "level 2 start")
            check_level_screen(1, "level 2 start")
            if (player_state()["x"], player_state()["y"]) != (16, 184):
                raise RuntimeError(f"ECS platformer player not at the start of level 2: {player_state()}")
            # Physics use the second map: from above, x=48 lands on the platform
            # at y=96 (stand y=88); on the first map it would stop at y=56.
            write_ram(player_slot + 4, bytes((48, 40)))
            try:
                wait_for(lambda: player_state()["y"] == 88 and grounded(), 5, "ECS platformer level 2 landing")
            except RuntimeError as error:
                raise RuntimeError(f"{error}: player={player_state()}") from None
            # Each enemy costs exactly one life per contact.
            for label, slot in (("left vertical", enemy_v2_slot), ("horizontal", enemy_h_slot), ("right vertical", enemy_v_slot)):
                lives_before = ram(lives, 1)[0]
                # The enemy keeps moving between reading it and the next game
                # frame, so a single placement can miss: retry from a clear spot.
                # Each attempt is a fresh contact (the player leaves first).
                flashed = False
                for _attempt in range(6):
                    write_ram(player_slot + 4, bytes((24, 100)))
                    time.sleep(0.3)
                    write_ram(player_slot + 4, ram(slot + 4, 2))
                    # Losing a life flashes the border red (hardware colour 0x1C)
                    # three times and leaves it black (0x14), as the original.
                    poll_until = time.time() + 0.6
                    while time.time() < poll_until:
                        flashed = flashed or get("/api/state")["ga"]["border_idx"] == 0x1C
                    if ram(lives, 1)[0] != lives_before:
                        break
                time.sleep(0.4)
                if ram(lives, 1)[0] != lives_before - 1:
                    raise RuntimeError(
                        f"ECS platformer {label} contact did not cost exactly one life: "
                        f"{lives_before} -> {ram(lives, 1)[0]}"
                    )
                if not flashed:
                    raise RuntimeError(f"ECS platformer {label} contact did not flash the border red")
                if get("/api/state")["ga"]["border_idx"] != 0x14:
                    raise RuntimeError(f"ECS platformer {label} flash left the border at {get('/api/state')['ga']['border_idx']:#x}")
                check_hud(ram(score, 1)[0], "collect", lives_before - 1, f"{label} contact")
            # Without lives a contact costs nothing and does not flash.
            write_ram(lives, b"\x00")
            write_ram(hud_dirty, b"\x02")
            check_hud(None, None, 0, "no lives")
            saw_red = False
            for _attempt in range(4):
                write_ram(player_slot + 4, bytes((24, 100)))
                time.sleep(0.3)
                write_ram(player_slot + 4, ram(enemy_v2_slot + 4, 2))
                poll_until = time.time() + 0.6
                while time.time() < poll_until:
                    saw_red = saw_red or get("/api/state")["ga"]["border_idx"] == 0x1C
            if ram(lives, 1) != b"\x00":
                raise RuntimeError(f"ECS platformer lives wrapped below zero: {ram(lives, 1).hex()}")
            if saw_red:
                raise RuntimeError("ECS platformer flashed the border with no lives left")
            # Win the second level: take the four coins, then the door ends the game
            # (it hides again and the level does not change).
            def take_coins():
                # Coins an enemy contact already made the player fall through are
                # gone; visit every spot until the game says all four are taken.
                for px, py in ((18, 24), (50, 24), (16, 168), (56, 168)):
                    write_ram(player_slot + 4, bytes((px, py)))
                    time.sleep(0.25)
                return ram(won, 1) == b"\x01"

            try:
                wait_for(take_coins, 15, "ECS platformer level 2 coins")
            except RuntimeError as error:
                raise RuntimeError(
                    f"{error}: status={ram(status, 1).hex()} score={ram(score, 1).hex()} "
                    f"player={player_state()} items(status,type,x,y)="
                    f"{[ram(items + 42 * i + 2, 4).hex() for i in range(5)]}"
                ) from None
            wait_for(lambda: ram(won, 1) == b"\x01", 5, "ECS platformer level 2 win state")
            wait_for(lambda: ram(door_slot + 2, 1) == b"\x01", 5, "ECS platformer level 2 door appears")
            check_hud(4, "go", 0, "level 2 all coins")
            wait_for(touch_door, 5, "ECS platformer level 2 door touch")
            time.sleep(0.5)
            if ram(level, 1) != b"\x01" or ram(won, 1) != b"\x00" or ram(door_slot + 2, 1) != b"\x03":
                raise RuntimeError("ECS platformer final door did not just hide the door on level 2")
            if ram(score, 1) != b"\x04" or any(ram(items + 42 * i + 2, 1) != b"\x00" for i in range(4)):
                raise RuntimeError("ECS platformer final door restarted level 2 instead of just hiding the door")
        if name == "audio":
            active = symbol(noi, "fwk_audio_active")
            ticks = symbol(noi, "fwk_audio_tick_count")
            sfx_count = symbol(noi, "fwk_audio_sfx_count")
            command = symbol(noi, "audio_command")
            command_ack = symbol(noi, "audio_command_ack")

            initial_ticks = int.from_bytes(ram(ticks, 2), "little")
            wait_for(
                lambda: int.from_bytes(ram(ticks, 2), "little") > initial_ticks + 3,
                5,
                "AKG playback ticks",
            )
            wait_for(
                lambda: any(get("/api/state")["psg"][key] for key in ("vol_a", "vol_b", "vol_c")),
                5,
                "audible PSG volume",
            )

            write_ram(command, b"\x02")
            wait_for(lambda: ram(command_ack, 1) == b"\x02", 5, "audio stop acknowledgement")
            stopped_ticks = int.from_bytes(ram(ticks, 2), "little")
            time.sleep(0.5)
            if ram(active, 1) != b"\x00" or int.from_bytes(ram(ticks, 2), "little") != stopped_ticks:
                raise RuntimeError("AKG playback continued after stop")
            stopped_psg = get("/api/state")["psg"]
            if any(stopped_psg[key] for key in ("vol_a", "vol_b", "vol_c")):
                raise RuntimeError(f"PSG volumes are not silent after stop: {stopped_psg}")

            write_ram(command, b"\x03")
            wait_for(lambda: ram(command_ack, 1) == b"\x03", 5, "audio start acknowledgement")
            wait_for(
                lambda: int.from_bytes(ram(ticks, 2), "little") > stopped_ticks + 3,
                5,
                "AKG playback restart",
            )

            write_ram(command, b"\x01")
            wait_for(lambda: ram(command_ack, 1) == b"\x01", 5, "sound-effect acknowledgement")
            wait_for(lambda: ram(sfx_count, 1) == b"\x01", 5, "sound-effect request")
            deadline = time.time() + 2
            heard_sfx = False
            while time.time() < deadline:
                psg = get("/api/state")["psg"]
                if psg["vol_b"] and psg["period_b"]:
                    heard_sfx = True
                    break
                time.sleep(0.01)
            if not heard_sfx:
                raise RuntimeError("sound effect did not produce an observable PSG channel B signal")
        if name == "animation":
            enabled = symbol(noi, "animation_enabled")
            changes = symbol(noi, "animation_changes")
            ticks = symbol(noi, "animation_ticks")
            frame_value = symbol(noi, "animation_frame_value")
            status = symbol(noi, "animation_status")
            wait_for(lambda: ram(status, 1) == b"\x5A", 5, "four exact animation periods")
            if ram(symbol(noi, "animation_wide_status"), 1) != b"\x5A":
                raise RuntimeError(
                    "descriptor with more than 128 frames returned the wrong frame "
                    "(16-bit frame index regression)"
                )
            if ram(frame_value, 1) not in {b"\xF0", b"\x0F", b"\xAA"}:
                raise RuntimeError("animation selected a frame outside its descriptor")
            wait_for(
                lambda: ram(standard_screen_address(20, 80), 1) == ram(frame_value, 1),
                5,
                "animation frame pointer rendering",
            )

            write_ram(enabled, b"\x00")
            time.sleep(0.15)
            paused_ticks = ram(ticks, 2)
            paused_changes = ram(changes, 2)
            paused_frame = ram(frame_value, 1)
            time.sleep(0.35)
            if (
                ram(ticks, 2) != paused_ticks
                or ram(changes, 2) != paused_changes
                or ram(frame_value, 1) != paused_frame
            ):
                raise RuntimeError("caller-owned animation pause policy did not freeze state")

            write_ram(enabled, b"\x01")
            paused_tick_value = int.from_bytes(paused_ticks, "little")
            paused_change_value = int.from_bytes(paused_changes, "little")
            wait_for(
                lambda: int.from_bytes(ram(ticks, 2), "little") > paused_tick_value + 4
                and int.from_bytes(ram(changes, 2), "little") > paused_change_value,
                5,
                "animation resume",
            )
        if name == "gravity":
            state = symbol(noi, "gravity_state")
            status = symbol(noi, "gravity_status")
            wait_for(lambda: ram(status, 1) == b"\x5A", 5, "48 platform physics steps")
            result = ram(state, 7)
            expected = bytes((76, 192, 0, 0, 4, 8, 0))
            if result != expected:
                raise RuntimeError(
                    f"platform physics state is {result.hex()}, expected {expected.hex()}"
                )
            inks = get("/api/state")["ga"]["ink_idx"]
            if inks[0] != 0x14 or inks[5] != 0x0A:
                raise RuntimeError(f"gravity palette is not black/yellow: {inks}")
            if ram(standard_screen_address(76, 192), 1) != b"\xF0":
                raise RuntimeError("gravity final position is not visible in video RAM")
        if name == "physics88":
            state = symbol(noi, "physics88_state")
            status = symbol(noi, "physics88_status")
            wait_for(lambda: ram(status, 1) == b"\x5A", 5, "64 fixed-point physics steps")
            result = ram(state, 9)
            expected = bytes.fromhex("dc0bc0750001800000")
            if result != expected:
                raise RuntimeError(
                    f"8.8 physics state is {result.hex()}, expected {expected.hex()}"
                )
            inks = get("/api/state")["ga"]["ink_idx"]
            if inks[0] != 0x14 or inks[15] != 0x13:
                raise RuntimeError(f"physics88 palette is not black/cyan: {inks}")
            if ram(standard_screen_address(11, 117), 1) != b"\xAA":
                raise RuntimeError("physics88 final position is not visible in video RAM")
        if name == "tilecoll":
            state = symbol(noi, "tilecoll_state")
            hits = symbol(noi, "tilecoll_hits")
            status = symbol(noi, "tilecoll_status")
            wait_for(lambda: ram(status, 1) == b"\x5A", 5, "96 tile collision steps")
            result = ram(state, 7)
            expected = bytes.fromhex("3a9c0000020402")
            if result != expected or ram(hits, 1) != b"\x0E":
                raise RuntimeError(
                    f"tile collision state/hits are {result.hex()}/{ram(hits, 1).hex()}, "
                    f"expected {expected.hex()}/0e"
                )
            inks = get("/api/state")["ga"]["ink_idx"]
            if inks[0] != 0x14 or inks[5] != 0x0A or inks[15] != 0x13:
                raise RuntimeError(f"tilecoll palette is not black/yellow/cyan: {inks}")
            if ram(standard_screen_address(58, 156), 1) != b"\xF0":
                raise RuntimeError("tilecoll final entity position is not visible in VRAM")
            for x, y in ((0, 40), (60, 100), (0, 160)):
                if ram(standard_screen_address(x, y), 1) != b"\xAA":
                    raise RuntimeError(f"tilecoll geometry witness missing at {(x, y)}")
        if name == "tilerender":
            view = symbol(noi, "tilerender_view")
            status = symbol(noi, "tilerender_status")
            partial_count = symbol(noi, "tilerender_partial_count")
            wait_for(lambda: ram(status, 1) == b"\x5A", 5, "tilemap viewport render")
            if ram(view + 2, 2) != bytes((2, 1)):
                raise RuntimeError("tilerender camera did not move to (2,1)")
            if ram(partial_count, 1) != b"\x01":
                raise RuntimeError("tilerender partial update was not executed")
            witnesses = {
                (10, 32): b"\xAA",
                (14, 32): b"\x00",
                (18, 40): b"\xF0",
                (26, 56): b"\xF0",
                (9, 32): b"\x55",
            }
            for (x, y), expected in witnesses.items():
                actual = ram(standard_screen_address(x, y), 1)
                if actual != expected:
                    raise RuntimeError(
                        f"tilerender VRAM witness {(x, y)} is {actual.hex()}, "
                        f"expected {expected.hex()}"
                    )
        if name == "spriteclip":
            status = symbol(noi, "spriteclip_status")
            used = symbol(noi, "spriteclip_capture_used")
            wait_for(lambda: ram(status, 1) == b"\x5A", 5, "clipped sprite render")
            if ram(used, 2) != bytes((20, 0)):
                raise RuntimeError("spriteclip did not capture the 4x5 visible rectangle")
            restored = (
                bytes.fromhex("11223344"),
                bytes.fromhex("55667788"),
                bytes.fromhex("99122334"),
                bytes.fromhex("45566778"),
                bytes.fromhex("899aabbc"),
            )
            for y, expected in enumerate(restored):
                if ram(standard_screen_address(0, y), 4) != expected:
                    raise RuntimeError(f"spriteclip background restore failed on row {y}")
            witnesses = {
                (0, 30): b"\xAA",
                (3, 30): b"\x00",
                (20, 0): b"\xAA",
                (22, 0): b"\x00",
                (77, 30): b"\x00",
                (79, 30): b"\xAA",
                (20, 196): b"\x00",
                (20, 199): b"\xAA",
                (35, 80): b"\x00",
                (36, 80): b"\xAA",
                (79, 100): b"\x55",
            }
            for (x, y), expected in witnesses.items():
                actual = ram(standard_screen_address(x, y), 1)
                if actual != expected:
                    raise RuntimeError(
                        f"spriteclip VRAM witness {(x, y)} is {actual.hex()}, "
                        f"expected {expected.hex()}"
                    )
        if name == "spritemask":
            status = symbol(noi, "spritemask_status")
            wait_for(lambda: ram(status, 1) == b"\x5A", 5, "masked sprite render")
            witnesses = {
                (20, 48): b"\x20",
                (22, 48): b"\xAA",
                (20, 49): b"\x1E",
                (21, 49): b"\xAA",
                (22, 50): b"\x1C",
                (20, 50): b"\xAA",
                (0, 0): b"\xAA",
                (2, 0): b"\xF0",
                (0, 2): b"\x00",
                (79, 20): b"\x00",
            }
            for (x, y), expected in witnesses.items():
                actual = ram(standard_screen_address(x, y), 1)
                if actual != expected:
                    raise RuntimeError(
                        f"spritemask VRAM witness {(x, y)} is {actual.hex()}, "
                        f"expected {expected.hex()}"
                    )
        if name == "renderorder":
            status = symbol(noi, "renderorder_status")
            command = symbol(noi, "renderorder_command")
            batch = symbol(noi, "renderorder_batch")
            entries = symbol(noi, "renderorder_entries")
            wait_for(lambda: ram(status, 1) == b"\xA5", 5, "ordered sprite draw")
            if ram(batch + 2, 1) != b"\x02":
                raise RuntimeError("renderorder batch count is not two")
            if ram(entries + 4, 1) != b"\x0A" or ram(entries + 10, 1) != b"\x14":
                raise RuntimeError("renderorder keys are not stably sorted")
            if ram(entries + 5, 1) != b"\x01" or ram(entries + 11, 1) != b"\x01":
                raise RuntimeError("renderorder entries were not marked captured")
            if ram(standard_screen_address(22, 42), 1) != b"\xAA":
                raise RuntimeError("renderorder lower layer is not visible")
            if ram(standard_screen_address(24, 44), 1) != b"\xF0":
                raise RuntimeError("renderorder upper layer did not win the overlap")

            write_ram(command, b"\x01")
            wait_for(lambda: ram(status, 1) == b"\x5A", 5, "reverse sprite restore")
            patterns = bytes.fromhex("112233445566778899122334")
            for y, pattern in enumerate(patterns, start=40):
                if ram(standard_screen_address(20, y), 12) != bytes((pattern,)) * 12:
                    raise RuntimeError(f"renderorder background restore failed on row {y}")
            if ram(entries + 5, 1) != b"\x00" or ram(entries + 11, 1) != b"\x00":
                raise RuntimeError("renderorder captured flags survived restoration")

            write_ram(command, b"\x02")
            wait_for(lambda: ram(status, 1) == b"\xC3", 5, "sprite move and redraw")
            if ram(standard_screen_address(23, 43), 1) != b"\x55":
                raise RuntimeError("renderorder background update was lost")
            if ram(standard_screen_address(30, 60), 1) != b"\xAA":
                raise RuntimeError("renderorder moved lower layer is not visible")
            if ram(standard_screen_address(32, 62), 1) != b"\xF0":
                raise RuntimeError("renderorder moved upper layer did not win the overlap")

            write_ram(command, b"\x03")
            wait_for(lambda: ram(status, 1) == b"\x3C", 5, "final sprite restore")
            for y in range(60, 68):
                if ram(standard_screen_address(30, y), 6) != b"\x00" * 6:
                    raise RuntimeError(f"renderorder moved background restore failed on row {y}")
            if ram(standard_screen_address(23, 43), 1) != b"\x55":
                raise RuntimeError("renderorder persistent background update changed")
        if name == "window":
            command = symbol(noi, "window_command")
            status = symbol(noi, "window_status")
            buffer = symbol(noi, "window_buffer")
            wait_for(lambda: ram(status, 1) == b"\xA5", 5, "window shown")
            if ram(buffer, 20 * 16) != b"\x55" * (20 * 16):
                raise RuntimeError("window background capture differs from the original pattern")

            top = standard_screen_address(10, 40)
            middle = standard_screen_address(10, 41)
            if ram(top, 20) != b"\xFF" * 20:
                raise RuntimeError("window top border has invalid geometry")
            if ram(middle, 20) != b"\xFF" + b"\x00" * 18 + b"\xFF":
                raise RuntimeError("window border/fill row has invalid geometry")
            if ram(standard_screen_address(9, 41), 1) != b"\x55" or ram(
                standard_screen_address(30, 41), 1
            ) != b"\x55":
                raise RuntimeError("window draw modified bytes outside its descriptor")

            write_ram(command, b"\x01")
            wait_for(lambda: ram(status, 1) == b"\x5A", 5, "window background restore")
            for y in range(40, 56):
                if ram(standard_screen_address(10, y), 20) != b"\x55" * 20:
                    raise RuntimeError(f"window restore failed on row {y}")

            write_ram(command, b"\x02")
            wait_for(lambda: ram(status, 1) == b"\xC3", 5, "window redraw")
            if ram(top, 20) != b"\xFF" * 20 or ram(middle, 20) != (
                b"\xFF" + b"\x00" * 18 + b"\xFF"
            ):
                raise RuntimeError("window did not redraw after restoration")
        if name == "vertical":
            player = symbol(noi, "vertical_player")
            pool = symbol(noi, "vertical_entity_pool")
            score = symbol(noi, "vertical_score")
            status = symbol(noi, "vertical_status")
            wait_for(
                lambda: ram(status, 1) in {b"\xA5", b"\x5A"},
                10,
                "vertical resource initialization",
            )
            initial_player = ram(player, 5)
            initial_count = ram(pool + 4, 1)
            initial_score = ram(score, 1)
            if initial_player[:2] != bytes((10, 100)):
                raise RuntimeError(f"vertical player initial state is {initial_player.hex()}, expected 0a64000001")
            if initial_count != b"\x04" or initial_score != b"\x00":
                raise RuntimeError(
                    "vertical entity resource did not create player plus three pickups: "
                    f"count={initial_count.hex()} score={initial_score.hex()}"
                )
            wait_for(
                lambda: ram(standard_screen_address(10, 100), 1) == b"\xFF"
                and all(
                    ram(standard_screen_address(x, 100), 1) == b"\x3C"
                    for x in (20, 30, 40)
                ),
                5,
                "vertical resource rendering",
            )
            hold_cursor_right(180)
            final_score = ram(score, 1)
            final_count = ram(pool + 4, 1)
            final_player = ram(player, 5)
            if final_score != b"\x03" or final_count != b"\x01":
                raise RuntimeError(
                    "vertical input did not collect all three pickups: "
                    f"player={final_player.hex()} count={final_count.hex()} score={final_score.hex()}"
                )
            if ram(status, 1) != b"\x5A" or ram(player, 1)[0] <= 40:
                raise RuntimeError("vertical slice did not reach its won state")
            wait_for(
                lambda: ram(standard_screen_address(final_player[0], final_player[1]), 1)
                == b"\xF3",
                5,
                "vertical won sprite rendering",
            )
        if name == "platformer":
            player = symbol(noi, "platformer_player")
            score = symbol(noi, "platformer_score")
            status = symbol(noi, "platformer_status")
            lives = symbol(noi, "platformer_lives")
            door = symbol(noi, "platformer_door_entity")
            enemy_h = symbol(noi, "platformer_enemy_h_entity")
            enemy_h_behavior = symbol(noi, "platformer_enemy_h_behavior")
            enemy_v = symbol(noi, "platformer_enemy_v_entity")
            enemy_v_behavior = symbol(noi, "platformer_enemy_v_behavior")
            enemy_v2 = symbol(noi, "platformer_enemy_v2_entity")
            enemy_v2_behavior = symbol(noi, "platformer_enemy_v2_behavior")
            contacts = symbol(noi, "platformer_enemy_contacts")
            hud_dirty = symbol(noi, "platformer_hud_dirty")
            wait_for(
                lambda: ram(status, 1) in {b"\xA5", b"\x5A"},
                20,
                "platformer scene initialization",
            )
            state = ram(player, 7)
            if state != bytes((16, 184, 0, 0, 8, 8, 2)):
                raise RuntimeError(f"platformer initial state is invalid: {state.hex()}")
            if (
                ram(score, 1) != b"\x00"
                or ram(status, 1) != b"\xA5"
                or ram(lives, 1) != b"\x0A"
            ):
                raise RuntimeError("platformer initial score/status/lives are invalid")
            if ram(door + 20, 1) != b"\x00":
                raise RuntimeError("platformer door is visible before collecting all coins")
            # The vertical enemies patrol y=56..154. fwk_motion_u8_step used to read
            # a sum of 128 or more as negative and sent them to y=0.
            v_ys = []
            deadline = time.time() + 6.0
            while time.time() < deadline:
                v_ys.append(ram(enemy_v_behavior + 1, 1)[0])
                v_ys.append(ram(enemy_v2_behavior + 1, 1)[0])
            if min(v_ys) < 56 or max(v_ys) < 140:
                raise RuntimeError(f"platformer vertical enemies left their patrol: y {min(v_ys)}..{max(v_ys)}")
            if platformer_regressions_only:
                enemy_specs = (
                    ("horizontal", enemy_h, enemy_h_behavior),
                    ("vertical", enemy_v, enemy_v_behavior),
                    ("left vertical", enemy_v2, enemy_v2_behavior),
                )
                behavior_before = {}
                for label, entity, behavior in enemy_specs:
                    offset = behavior - entity
                    snapshot = ram(entity, offset + 8)
                    behavior_before[label] = snapshot[offset : offset + 8]
                hold_keys(frames=4, after=0)
                for label, entity, behavior in enemy_specs:
                    offset = behavior - entity
                    snapshot = ram(entity, offset + 8)
                    before = behavior_before[label]
                    after = snapshot[offset : offset + 8]
                    if (
                        int.from_bytes(before[5:7], "little") == 0
                        or after[:2] == before[:2]
                        or snapshot[2] != after[0]
                        or snapshot[4] != after[1]
                    ):
                        raise RuntimeError(
                            f"platformer {label} enemy is not driven by behavior/motion: "
                            f"before={before.hex()} after={after.hex()}"
                        )
                old_wrong_hud_cell = b"".join(
                    ram(standard_screen_address(44, y), 4) for y in range(10, 19)
                )
                old_life_digits = b"".join(
                    ram(standard_screen_address(76, y), 4) for y in range(10, 19)
                )
                # Use an open part of the map so tile resolution cannot move
                # the injected player away before the contact check.
                write_ram(enemy_v2 + 2, bytes((16, 0, 100, 0)))
                write_ram(enemy_v2_behavior, bytes((24, 100)))
                write_ram(
                    player,
                    bytes((16, 100, 0, 0, 8, 8, 0)),
                )
                hold_keys(frames=2, after=0)
                contact_lives = ram(lives, 1)
                if contact_lives != b"\x09":
                    raise RuntimeError(
                        "platformer third-enemy overlap did not remove exactly one life: "
                        f"player={ram(player, 7).hex()} "
                        f"enemy={ram(enemy_v2 + 2, 4).hex()} "
                        f"contacts={ram(contacts, 1).hex()} lives={contact_lives.hex()}"
                    )
                wait_for(
                    lambda: ram(hud_dirty, 1)[0] & 0x02 == 0,
                    5,
                    "platformer life HUD update",
                )
                new_wrong_hud_cell = b"".join(
                    ram(standard_screen_address(44, y), 4) for y in range(10, 19)
                )
                new_life_digits = b"".join(
                    ram(standard_screen_address(76, y), 4) for y in range(10, 19)
                )
                if new_wrong_hud_cell != old_wrong_hud_cell:
                    raise RuntimeError(
                        "platformer life update corrupted the central HUD text"
                    )
                if new_life_digits == old_life_digits:
                    raise RuntimeError("platformer life digits did not change in video RAM")
                print(
                    f"ok - platformer enemy behaviors, contact, door and HUD ({model})"
                )
                return
            if screenshot_dir is not None:
                screenshot_dir.mkdir(parents=True, exist_ok=True)
                (screenshot_dir / f"platformer-{model}-start.png").write_bytes(
                    get_bytes("/api/screenshot?crop=1")
                )
            set_keys(row0=0xFE)
            wait_for(lambda: ram(player, 7)[1] < 184, 5, "platformer first jump")
            set_keys()
            wait_for(
                lambda: ram(player, 7)[1] == 184 and ram(player, 7)[6] == 0x02,
                5,
                "platformer first landing",
            )
            if ram(score, 1) != b"\x01":
                raise RuntimeError("platformer did not collect the lower-left coin and land")
            # Rendering cost is allowed to make a game-loop pass span more
            # than one video frame. Drive the walkthrough by observable game
            # state instead of assuming 20 emulator frames == 20 updates.
            hold_keys_until(
                lambda: ram(player, 1)[0] >= 56,
                row0=0xFD,
                timeout=10,
                label="platformer right approach",
            )
            if not 48 <= ram(player, 1)[0] < 64:
                raise RuntimeError(
                    f"platformer right approach ended outside its target: "
                    f"x={ram(player, 1)[0]}"
                )
            set_keys(row0=0xFE)
            wait_for(lambda: ram(player, 7)[1] < 184, 5, "platformer second jump")
            set_keys()
            wait_for(
                lambda: ram(player, 7)[1] == 184 and ram(player, 7)[6] == 0x02,
                5,
                "platformer second landing",
            )
            if ram(score, 1) != b"\x02":
                raise RuntimeError(
                    "platformer did not collect the lower-right coin: "
                    f"player={ram(player, 7).hex()} score={ram(score, 1).hex()}"
                )
            font = asm_hex_bytes_between(
                ROOT / "src/ui/text.inc",
                "_fwk_text_default_font:",
                "_fwk_text_default_small_digits:",
            )
            expected_score_two = font[11 * 18 : 12 * 18]
            actual_score_two = b"".join(
                ram(standard_screen_address(14, y), 2) for y in range(10, 19)
            )
            if actual_score_two != expected_score_two:
                raise RuntimeError(
                    "platformer HUD was not restored before score redraw: "
                    f"actual={actual_score_two.hex()} "
                    f"expected={expected_score_two.hex()}"
                )
            hold_keys_until(
                lambda: ram(player, 1)[0] <= 44,
                row1=0xFE,
                timeout=10,
                label="platformer platform approach",
            )
            if not 32 <= ram(player, 1)[0] <= 48:
                raise RuntimeError(
                    f"platformer platform approach ended outside its target: "
                    f"x={ram(player, 1)[0]}"
                )
            expected_y = (152, 120, 88, 56, 24)
            for landing_y in expected_y:
                start_y = ram(player, 7)[1]
                set_keys(row0=0xFE)
                wait_for(
                    lambda: ram(player, 7)[1] < start_y,
                    5,
                    f"platformer jump towards y={landing_y}",
                )
                set_keys()
                wait_for(
                    lambda: ram(player, 7)[1] == landing_y
                    and ram(player, 7)[6] == 0x02,
                    5,
                    f"platformer landing at y={landing_y}",
                )
                climbed = ram(player, 7)
                if climbed[1] != landing_y or climbed[6] != 0x02:
                    raise RuntimeError(
                        f"platformer did not land at y={landing_y}: {climbed.hex()}"
                    )
            set_keys(row1=0xFE)
            wait_for(lambda: ram(score, 1) == b"\x03", 5, "platformer upper-left coin")
            set_keys()
            set_keys(row0=0xFD)
            wait_for(lambda: ram(score, 1) == b"\x04", 5, "platformer upper-right coin")
            set_keys()
            if ram(score, 1) != b"\x04" or ram(status, 1) != b"\x5A":
                raise RuntimeError("platformer did not collect all coins and win")
            for coin_x in (16, 56):
                restored_coin_cell = b"".join(
                    ram(standard_screen_address(coin_x, y), 4)
                    for y in range(168, 176)
                )
                if restored_coin_cell != bytes(32):
                    raise RuntimeError(
                        "platformer left pixels in a collected lower coin cell: "
                        f"x={coin_x} data={restored_coin_cell.hex()}"
                    )
            if screenshot_dir is not None:
                (screenshot_dir / f"platformer-{model}-victory.png").write_bytes(
                    get_bytes("/api/screenshot?crop=1")
                )
        print(f"ok - {name} executes and advances frames ({model})")
    finally:
        try:
            post("/api/quit", {})
        except OSError:
            pass
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "examples",
        nargs="*",
        default=["minimal", "board", "platform", "gravity", "physics88", "tilecoll", "tilerender", "spriteclip", "spritemask", "renderorder", "video", "resources128", "diskload", "audio", "animation", "window", "vertical", "perf", "collision", "tilemask", "experimental", "platformer", "ecsmanager", "ecscollision", "ecsanimation", "ecsrender", "platformer_ecs"],
    )
    parser.add_argument("--emulator", type=Path, default=DEFAULT_EMULATOR)
    parser.add_argument("--model", choices=["464", "6128"], default="6128")
    parser.add_argument(
        "--screenshot-dir",
        type=Path,
        help="guarda capturas PNG del inicio y victoria de platformer",
    )
    parser.add_argument(
        "--platformer-regressions-only",
        action="store_true",
        help="comprueba contactos, puerta y estado inicial sin recorrer el nivel",
    )
    args = parser.parse_args()
    if args.platformer_regressions_only and args.examples != ["platformer"]:
        parser.error("--platformer-regressions-only requiere solo el ejemplo platformer")
    try:
        get("/api/ping")
        raise SystemExit("port 6128 is already occupied")
    except OSError:
        pass
    for name in args.examples:
        run_example(
            name,
            args.emulator,
            args.model,
            args.screenshot_dir,
            args.platformer_regressions_only,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
