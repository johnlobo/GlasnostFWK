#!/usr/bin/env python3
"""Measure a running game in AmSpiriT-Lite: frames per iteration and T-states.

Method (no change to the game):

* A breakpoint on the entry of `cpct_waitVSYNC_asm` fires once per game-loop
  iteration, another on its `ret` fires when the wait ends. At every hit the
  emulator is paused, so `emu.frames` and the CRT beam position give an exact
  timestamp: T = frames * 79872 + (beam_y - 25) * 256 + beam_x / 4. The frame
  counter increments when the beam wraps from line 337 to 25, so one frame is
  312 lines of 256 T-states. Timestamp error is about 4 T-states.
* iteration = entry(k+1) - entry(k); idle = exit(k) - entry(k);
  work = entry(k+1) - exit(k). Work includes the 300 Hz interrupt handler and
  the keyboard scan, which both games share.
* With `--routines`, a breakpoint on each routine entry plus one on its return
  address (read from the stack) times every call, nested ones included. A routine
  entered with `jp` is timed until it returns to whoever called the jumper.

    python3 tools/measure_game.py platformer_ecs --scenarios idle,right,jump
    python3 tools/measure_game.py platformer --routines profile --json /tmp/o.json

Scenarios hold cursor keys through the keyboard matrix while the iterations are
measured. Run `python3 tools/build_test_disk.py platformer platformer_ecs` first.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
import statistics
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import emulator_smoke as smoke  # noqa: E402  (shared emulator HTTP helpers)

FRAME_T = 79872
LINE_T = 256
FIRST_LINE = 25
API = "http://127.0.0.1:6128"
EMULATOR = Path("/config/workspace/tools/amspirit-lite/run.sh")

GAMES = {
    "platformer": {"run": "PLATGAME", "status": "platformer_status", "ready": 0xA5},
    "platformer_ecs": {"run": "PECS", "status": "platformer_ecs_status", "ready": 0x5A},
}
# Cursor keys are active low: row 0 bit 0 = up, bit 1 = right; row 1 bit 0 = left.
SCENARIOS = {
    "idle": {},
    "right": {"row0": 0xFD},
    "left": {"row1": 0xFE},
    "jump": {"row0": 0xFE},
    "jump_right": {"row0": 0xFC},
}
PROFILES = {
    "platformer": [
        "fwk_input_update", "_pf_update_animation", "_pf_read_controls", "_pf_update_player",
        "_pf_update_enemies", "_pf_update_enemy_v2", "_pf_sync_player_render", "_pf_collect_coins",
        "_pf_check_door", "_pf_check_enemy_contacts", "_pf_prepare_dirty", "_pf_restore_dirty",
        "_pf_draw_dirty",
    ],
    "platformer_ecs": [
        "fwk_input_update", "fwk_ecs_system_behavior", "fwk_ecs_system_input", "fwk_ecs_system_platform",
        "fwk_ecs_system_motion_u8", "fwk_ecs_system_animation", "_pfe_collisions", "_pfe_apply_events",
        "fwk_ecs_render_prepare", "fwk_ecs_render_restore", "fwk_ecs_render_draw",
        "fwk_ecs_manager_collect", "_pfe_hud_update",
    ],
}


def eval_lua(code: str) -> dict:
    request = urllib.request.Request(API + "/api/eval", data=code.encode(), method="POST")
    seq = json.load(urllib.request.urlopen(request, timeout=10))["seq"]
    for _ in range(400):
        outcome = smoke.get(f"/api/eval?seq={seq}")
        if outcome.get("done"):
            return outcome
        time.sleep(0.005)
    raise RuntimeError("eval did not finish")


def set_breakpoints(addresses) -> None:
    body = ",".join(hex(a) for a in sorted(addresses)).encode()
    urllib.request.urlopen(urllib.request.Request(API + "/api/z80_bp", data=body, method="POST"), timeout=5).read()


def label_table(example: str) -> dict[str, int]:
    """Every label (global and local) with its final address, from the listings."""
    labels: dict[str, int] = {}
    pattern = re.compile(r"^\s+([0-9A-F]{8})\s+\d+\s+([A-Za-z_][\w$]*)::?\s*$")
    for listing in sorted((ROOT / ".build" / example / "obj").rglob("*.rst")):
        for line in listing.read_text(errors="replace").splitlines():
            match = pattern.match(line)
            if match:
                labels.setdefault(match.group(2), int(match.group(1), 16))
    return labels


class Session:
    def __init__(self, example: str, emulator: Path, model: str = "6128"):
        self.example, self.emulator, self.model = example, emulator, model
        self.noi = ROOT / ".build" / example / "obj" / f"{example}.noi"
        self.process = None

    def __enter__(self):
        dsk = ROOT / ".build" / "tests" / "GlasnostFWK-tests.dsk"
        self.process = subprocess.Popen(
            [str(self.emulator), "--web-server", "--model", self.model, "--ram", "128", str(dsk)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
        )
        smoke.wait_for(lambda: smoke.get("/api/ping").get("ok"), 30, "emulator API")
        time.sleep(6)
        game = GAMES[self.example]
        smoke.post("/api/keytype", {"text": f'run"{game["run"]}"\n'})
        status = smoke.symbol(self.noi, game["status"])
        smoke.wait_for(lambda: smoke.ram(status, 1) == bytes((game["ready"],)), 30, "game initialization")
        time.sleep(1)
        return self

    def __exit__(self, *_):
        try:
            set_breakpoints([])
            smoke.post("/api/quit", {})
        except OSError:
            pass
        try:
            self.process.wait(timeout=10)
        except Exception:
            os.killpg(self.process.pid, signal.SIGKILL)

    def snapshot(self) -> tuple[int, int, int] | None:
        """(T-states, pc, sp) of the paused machine, or None if it was not stable.

        Read twice: only a machine that stayed paused with the same registers, frame
        and beam position in both reads is a real stop (a read that straddles a
        resume would mix two moments).
        """
        first_state, first_beam = smoke.get("/api/state"), smoke.get("/api/beam")
        second_state, second_beam = smoke.get("/api/state"), smoke.get("/api/beam")
        if not (first_state["emu"]["paused"] and second_state["emu"]["paused"]):
            return None
        if first_state["z80"] != second_state["z80"] or first_state["emu"]["frames"] != second_state["emu"]["frames"]:
            return None
        if (first_beam["x"], first_beam["y"]) != (second_beam["x"], second_beam["y"]):
            return None
        t = first_state["emu"]["frames"] * FRAME_T + (first_beam["y"] - FIRST_LINE) * LINE_T + first_beam["x"] // 4
        return t, first_state["z80"]["PC"], first_state["z80"]["SP"]

    def wait_paused(self, timeout: float = 5.0) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if smoke.get("/api/ping")["emu"]["paused"]:
                return
        raise RuntimeError("no breakpoint hit")

    def next_hit(self, previous: tuple[int, int] | None, timeout: float = 5.0) -> tuple[int, int, int]:
        """(T, pc, sp) of the next breakpoint stop after `previous` = (pc, T).

        Right after a resume the `paused` flag can still read true for an instant, so
        the same stop would be read again; a genuine new stop differs in PC or in time.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            reading = self.snapshot()
            if reading is not None and (reading[1], reading[0]) != previous:
                return reading
        raise RuntimeError("no breakpoint hit")

    def measure(self, iterations: int, routines: list[str]) -> dict:
        labels = label_table(self.example)
        globals_ = {m: int(a, 16) for m, a in re.findall(r"^DEF (\S+) 0x([0-9A-Fa-f]+)", self.noi.read_text(), re.M)}
        # Sanity: the listings carry final addresses (data modules may not, so only
        # code labels used here are compared).
        for name in ("_main", *[r for r in routines if r in globals_]):
            if labels.get(name, globals_[name]) != globals_[name]:
                raise RuntimeError(f"listing and map disagree on {name}")
        wait_entry = globals_["cpct_waitVSYNC_asm"]
        wait_exit = wait_entry + bytes(smoke.ram(wait_entry, 16)).index(b"\xC9")
        entries = {labels[name]: name for name in routines}
        pending: dict[int, list[tuple[str, int]]] = {}
        set_breakpoints({wait_entry, wait_exit, *entries})
        eval_lua("cpc.pause(false)")  # nothing yet: first hit is the next wait entry
        events = []  # (kind, t)
        calls: list[tuple[int, str, int]] = []  # (iteration index, name, duration)
        iteration = -1
        entry_hits = 0
        previous = None
        while entry_hits < iterations + 1:
            t, pc, sp = self.next_hit(previous)
            previous = (pc, t)
            if pc == wait_entry:
                events.append(("entry", t))
                entry_hits += 1
                iteration += 1
            elif pc == wait_exit:
                events.append(("exit", t))
            elif pc in pending and pending[pc]:
                name, start = pending[pc].pop()
                calls.append((max(iteration, 0), name, t - start))
                if not pending[pc]:
                    del pending[pc]
            elif pc in entries:
                return_address = int.from_bytes(smoke.ram(sp, 2), "little")
                pending.setdefault(return_address, []).append((entries[pc], t))
            set_breakpoints({wait_entry, wait_exit, *entries, *pending})
            eval_lua("cpc.pause(false)")
        set_breakpoints([])
        eval_lua("cpc.pause(false)")
        return summarize(events, calls, routines)


def frames_between(t_a: int, t_b: int) -> int:
    """Whole frames between two wait exits. Both sit on the VSYNC, so the gap is an integer."""
    return round((t_b - t_a) / FRAME_T)


def summarize(events, calls, routines) -> dict:
    entries = [t for kind, t in events if kind == "entry"]
    exits = [t for kind, t in events if kind == "exit"]
    # Pair every entry with the exit that follows it.
    iterations, works, idles = [], [], []
    exit_index = 0
    for k in range(len(entries) - 1):
        while exit_index < len(exits) and exits[exit_index] < entries[k]:
            exit_index += 1
        if exit_index >= len(exits):
            break
        iterations.append(entries[k + 1] - entries[k])
        idles.append(exits[exit_index] - entries[k])
        works.append(entries[k + 1] - exits[exit_index])
    gaps = [frames_between(a, b) for a, b in zip(exits, exits[1:])]
    per_routine = {}
    for name in routines:
        durations = [d for _i, n, d in calls if n == name]
        count = len(iterations) or 1
        per_routine[name] = {
            "calls_per_iteration": round(len(durations) / count, 2),
            "t_per_call": round(statistics.mean(durations)) if durations else 0,
            "t_per_iteration": round(sum(durations) / count),
        }

    def stats(values):
        values = sorted(values)
        return {
            "mean": round(statistics.mean(values)), "median": round(statistics.median(values)),
            "p95": values[int(0.95 * (len(values) - 1))], "min": values[0], "max": values[-1],
        }

    return {
        "iterations": len(iterations),
        # Exact: wait exits fall on the VSYNC, so each gap is a whole number of frames.
        "frames_per_iteration": round(statistics.mean(gaps), 3) if gaps else 0,
        "frames_histogram": {str(n): gaps.count(n) for n in sorted(set(gaps))},
        "iteration_t": stats(iterations),
        "work_t": stats(works),
        "idle_t": stats(idles),
        "routines": per_routine,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("example", choices=sorted(GAMES))
    parser.add_argument("--scenarios", default="idle,right,jump", help=f"comma list of {', '.join(SCENARIOS)}")
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--routines", default="", help="'profile' or a comma list of routine labels")
    parser.add_argument("--model", default="6128")
    parser.add_argument("--emulator", type=Path, default=EMULATOR)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    routines = PROFILES[args.example] if args.routines == "profile" else [r for r in args.routines.split(",") if r]
    result = {"example": args.example, "model": args.model, "scenarios": {}}
    lock = open("/tmp/amspirit.lock", "w")
    import fcntl
    fcntl.flock(lock, fcntl.LOCK_EX)
    for scenario in args.scenarios.split(","):
        with Session(args.example, args.emulator, args.model) as session:
            smoke.set_keys(**SCENARIOS[scenario])
            time.sleep(0.5)
            result["scenarios"][scenario] = session.measure(args.iterations, routines)
        data = result["scenarios"][scenario]
        print(f"{args.example} / {scenario}: {data['iterations']} iterations, "
              f"{data['frames_per_iteration']} frames/iteration {data['frames_histogram']}, "
              f"work {data['work_t']['mean']} T (median {data['work_t']['median']}, p95 {data['work_t']['p95']}, "
              f"max {data['work_t']['max']}), idle {data['idle_t']['mean']} T")
        for name, row in data["routines"].items():
            print(f"    {name:32s} {row['calls_per_iteration']:5.2f} calls  {row['t_per_call']:7d} T/call  {row['t_per_iteration']:7d} T/iteration")
    if args.json:
        args.json.write_text(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
