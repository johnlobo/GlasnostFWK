#!/usr/bin/env python3
"""Optional AmSpiriT-Lite smoke test for built DSKs (not part of default make test)."""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EMULATOR = ROOT.parent / "tools" / "amspirit-lite" / "run.sh"
API = "http://127.0.0.1:6128"


def get(path: str):
    with urllib.request.urlopen(API + path, timeout=5) as reply:
        return json.load(reply)


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


def ram(address: int, length: int) -> bytes:
    return bytes.fromhex(get(f"/api/ram?addr={address}&len={length}")["hex"])


def standard_screen_address(x: int, y: int) -> int:
    return 0xC000 + (y & 7) * 0x800 + (y >> 3) * 80 + x


def symbol(noi: Path, name: str) -> int:
    table = dict(re.findall(r"^DEF (\S+) 0x([0-9A-Fa-f]+)", noi.read_text(), re.MULTILINE))
    return int(table[name], 16)


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


def hold_cursor_right(frames: int) -> None:
    pressed = [0xFD] + [0xFF] * 15  # Key_CursorRight: row 0, bit 1, active low
    released = [0xFF] * 16
    marker = f"GLASNOST_INPUT_DONE_{time.monotonic_ns()}"
    script = (
        f"keyboard_write({','.join(map(str, pressed))})\n"
        f"wait_frames({frames - 1})\n"
        f"keyboard_write({','.join(map(str, released))})\n"
        "wait_frames(2)\n"
        f'print("{marker}")\n'
    )
    post_text("/api/script?lang=lua", script)
    wait_for(
        lambda: (status := get("/api/script"))["running"] is False and marker in status["output"],
        15,
        "held CursorRight input",
    )


def run_example(name: str, emulator: Path, model: str) -> None:
    directory = ROOT / ".build" / name
    dsk = directory / f"{name}.dsk"
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
        post("/api/keytype", {"text": f'run"{name[:8]}\n'})
        wait_for(lambda: int.from_bytes(ram(frame, 2), "little") > 2, 30, f"{name} frame loop")
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
            if ram(standard_screen_address(final_player[0], final_player[1]), 1) != b"\xF3":
                raise RuntimeError("vertical won sprite resource was not rendered")
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
        default=["minimal", "board", "platform", "video", "resources128", "diskload", "vertical"],
    )
    parser.add_argument("--emulator", type=Path, default=DEFAULT_EMULATOR)
    parser.add_argument("--model", choices=["464", "6128"], default="6128")
    args = parser.parse_args()
    try:
        get("/api/ping")
        raise SystemExit("port 6128 is already occupied")
    except OSError:
        pass
    for name in args.examples:
        run_example(name, args.emulator, args.model)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
