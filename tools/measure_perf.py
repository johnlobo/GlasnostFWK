#!/usr/bin/env python3
"""Measure GlasnostFWK performance scenes in AmSpiriT-Lite.

Boots perf.BIN from the shared test DSK, waits for the benchmark to finish,
reads its measured frame/iteration counts and prints cycles per call.
"""
import argparse
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
DEFAULT_EMULATOR = ROOT.parent / "tools" / "amspirit-lite" / "run.sh"
API = "http://127.0.0.1:6128"
CYCLES_PER_FRAME = 79872

SCENES = [
    "empty (loop overhead)",
    "video_clear (160x200)",
    "sprite_draw (6x8 opaque)",
    "sprite_draw_masked (6x8)",
    "sprite_capture (6x8)",
    "sprite_restore (6x8)",
    "entity_render (8 x 4x4, restore+draw)",
    "tilemap_render_view (5x4 tiles)",
    "tilemap_render_cell (one tile)",
]


def get(path):
    with urllib.request.urlopen(API + path, timeout=5) as reply:
        return json.load(reply)


def post(path, body, content_type="application/json"):
    request = urllib.request.Request(API + path, data=body.encode(), method="POST",
                                     headers={"Content-Type": content_type})
    with urllib.request.urlopen(request, timeout=5) as reply:
        return json.load(reply)


def ram(address, length):
    return bytes.fromhex(get(f"/api/ram?addr={address}&len={length}")["hex"])


def symbol(noi, name):
    table = dict(re.findall(r"^DEF (\S+) 0x([0-9A-Fa-f]+)", noi.read_text(), re.MULTILINE))
    return int(table[name], 16)


def boot(emulator):
    try:
        get("/api/ping")
        raise SystemExit("port 6128 is already occupied")
    except OSError:
        pass
    process = subprocess.Popen([str(emulator), "--web-server", "--model", "6128",
                                "--ram", "128", str(ROOT / ".build" / "tests" / "GlasnostFWK-tests.dsk")],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               start_new_session=True)
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            if get("/api/ping").get("ok"):
                break
        except OSError:
            pass
        time.sleep(0.5)
    else:
        raise SystemExit("emulator did not start")
    time.sleep(6)
    import json
    post("/api/keytype", json.dumps({"text": 'run"perf\n'}))
    return process


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--keep-emulator", action="store_true")
    parser.add_argument("--emulator", type=Path, default=DEFAULT_EMULATOR)
    args = parser.parse_args()

    noi = ROOT / ".build" / "perf" / "obj" / "perf.noi"
    status_addr = symbol(noi, "perf_status")
    results_addr = symbol(noi, "perf_results")

    emulator = boot(args.emulator)
    try:
        deadline = time.time() + 180
        while time.time() < deadline:
            try:
                if ram(status_addr, 1) == b"\x5A":
                    break
            except OSError:
                pass
            time.sleep(1)
        else:
            raise SystemExit("perf benchmark did not finish in 180 s")

        data = ram(results_addr, len(SCENES) * 4)
        print("scene                                     frames  iters   cyc/call  +/-1 frame")
        overhead = None
        for index, name in enumerate(SCENES):
            frames = int.from_bytes(data[index * 4:index * 4 + 2], "little")
            iters = int.from_bytes(data[index * 4 + 2:index * 4 + 4], "little")
            cyc = CYCLES_PER_FRAME * frames / iters
            if index == 0:
                overhead = cyc
            adjusted = cyc - (overhead if index > 0 else 0)
            err = CYCLES_PER_FRAME / iters
            print(f"{name:40} {frames:6} {iters:6} {cyc:9.1f} {err:8.1f}")
        print()
        print("cycles/call incluye el bucle de medida; la primera fila es la")
        print("sobrecarga del bucle y puede restarse para aislar la rutina.")
    finally:
        if not args.keep_emulator:
            try:
                post("/api/quit", "{}")
            except OSError:
                pass
            try:
                emulator.wait(10)
            except subprocess.TimeoutExpired:
                os.killpg(emulator.pid, signal.SIGKILL)
    return 0


if __name__ == "__main__":
    sys.exit(main())
