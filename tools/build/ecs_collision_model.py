#!/usr/bin/env python3
"""Reference model and scenario for fwk_ecs_collide (ABI 2.0, section 9).

Single source of truth for the emulator scenario run by examples/ecscollision:
``--output`` renders the step table as an include, ``--check`` verifies a
committed copy, and tests/emulator_smoke.py replays the same model to know
what the Z80 routine must have logged.

Entity ids: 0 is the subject S; 1..4 are targets T0..T3. T3 has no COLLISION
component, so the component mask must filter it out.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

ENTER, STAY, EXIT = 1, 2, 3
ERR_BUSY, ERR_CALLBACK = 0x06, 0x09
ABORT_CODE = 0x77
WIDTH, HEIGHT = 4, 8

(CMD_NONE, CMD_DESTROY, CMD_ABORT_CODE, CMD_LOCK, CMD_NULL_CALLBACK, CMD_ABORT_ZERO) = range(6)

HAS_COLLISION = (True, True, True, True, False)
PARK = ((0, 0), (20, 40), (40, 80), (60, 120), (10, 160))


# Pass kinds: channel (state bit) and target set.
KIND_COLLISION, KIND_RENDER = 0, 1
CHANNEL = {KIND_COLLISION: 0x01, KIND_RENDER: 0x02}


@dataclass(frozen=True)
class Step:
    positions: tuple
    cmd: int = CMD_NONE
    note: str = ""
    kind: int = KIND_COLLISION


def _at(**moves: tuple) -> tuple:
    names = ("s", "t0", "t1", "t2", "t3")
    unknown = set(moves) - set(names)
    if unknown:
        raise ValueError(f"unknown entity override {unknown}")
    return tuple(moves.get(name, PARK[i]) for i, name in enumerate(names))


SCENARIO = (
    Step(_at(), note="parked: nothing touches"),
    Step(_at(s=(20, 40)), note="S reaches T0: ENTER"),
    Step(_at(s=(20, 40)), note="still touching: STAY"),
    Step(_at(s=(22, 40), t1=(24, 40)), note="two targets, slot order, both STAY"),
    Step(_at(), note="S leaves: one EXIT without target"),
    Step(_at(), note="nothing, no second EXIT"),
    Step(_at(s=(10, 160)), note="T3 has no COLLISION component: ignored"),
    Step(_at(s=(16, 40)), note="edge contact only: no overlap"),
    Step(_at(s=(60, 120)), CMD_DESTROY, "callback destroys T2 on contact, then collect"),
    Step(_at(s=(60, 120)), note="T2 is gone: EXIT"),
    Step(_at(s=(20, 40), t1=(22, 40)), CMD_ABORT_CODE, "callback aborts: error, CONTACT untouched"),
    Step(_at(s=(20, 40), t1=(22, 40)), note="same pass again: still ENTER for both"),
    Step(_at(s=(20, 40), t1=(22, 40)), CMD_LOCK, "manager locked: BUSY, CONTACT untouched"),
    Step(_at(s=(20, 40), t1=(22, 40)), CMD_NULL_CALLBACK, "null callback: CALLBACK error"),
    Step(_at(), note="S leaves: EXIT"),
    Step(_at(s=(20, 40)), note="touch again: ENTER"),
    Step(_at(), CMD_ABORT_ZERO, "EXIT callback fails with A=0: CALLBACK, CONTACT cleared"),
    Step(_at(s=(20, 40), t3=(22, 40)), note="channel 1: only T0 has COLLISION: ENTER"),
    Step(_at(s=(20, 40), t3=(22, 40)), note="channel 2 (all RENDER entities): its own ENTER x2",
         kind=KIND_RENDER),
    Step(_at(s=(20, 40), t3=(22, 40)), note="channel 1 again: STAY, not disturbed by channel 2"),
    Step(_at(s=(20, 40), t3=(22, 40)), note="channel 2 again: STAY x2", kind=KIND_RENDER),
    Step(_at(), note="away, channel 1: EXIT, channel 2 state survives"),
    Step(_at(), note="away, channel 2: its own EXIT", kind=KIND_RENDER),
    Step(_at(s=(20, 40)), CMD_DESTROY, "callback destroys T0 on ENTER, then collect"),
    Step(_at(s=(20, 40), t1=(22, 40)), note="a NEW target while the channel is set arrives as STAY"),
    Step(_at(), note="away: EXIT"),
)


@dataclass
class StepRecord:
    index: int
    result: int
    carry: int
    contact: int
    callbacks: list  # (type, target id or None, subject id)


@dataclass
class Model:
    status: dict = field(default_factory=lambda: {i: "active" for i in range(5)})
    contact: int = 0

    def overlaps(self, a, b, pos) -> bool:
        (ax, ay), (bx, by) = pos[a], pos[b]
        return (
            ax < bx + WIDTH and bx < ax + WIDTH and ay < by + HEIGHT and by < ay + HEIGHT
        )

    def run(self, index: int, step: Step) -> StepRecord:
        pos = dict(enumerate(step.positions))
        if step.cmd == CMD_LOCK:
            return StepRecord(index, ERR_BUSY, 1, self.contact, [])
        if step.cmd == CMD_NULL_CALLBACK:
            return StepRecord(index, ERR_CALLBACK, 1, self.contact, [])
        callbacks: list = []
        channel = CHANNEL[step.kind]
        prev = self.contact & channel
        hits = 0
        for target in (1, 2, 3, 4):
            if step.kind == KIND_COLLISION and not HAS_COLLISION[target]:
                continue
            if self.status[target] != "active":
                continue
            if not self.overlaps(0, target, pos):
                continue
            hits += 1
            kind = STAY if prev else ENTER
            callbacks.append((kind, target, 0))
            if step.cmd == CMD_ABORT_CODE:
                return StepRecord(index, ABORT_CODE, 1, self.contact, callbacks)
            if step.cmd == CMD_DESTROY:
                self.status[target] = "pending"
        if step.cmd == CMD_DESTROY:
            for ident, status in self.status.items():
                if status == "pending":
                    self.status[ident] = "free"
        self.contact = (self.contact | channel) if hits else (self.contact & ~channel)
        if not hits and prev:
            callbacks.append((EXIT, None, 0))
            if step.cmd == CMD_ABORT_ZERO:
                return StepRecord(index, ERR_CALLBACK, 1, self.contact, callbacks)
        return StepRecord(index, 0, 0, self.contact, callbacks)


def simulate() -> list[StepRecord]:
    model = Model()
    return [model.run(index, step) for index, step in enumerate(SCENARIO)]


def _word(value: int) -> bytes:
    return bytes((value & 0xFF, value >> 8))


def expected_log(pointers: list[int], manager: int) -> bytes:
    """Bytes the harness must have written to ecscollision_log.

    Record: step, result, carry, contact byte of S, callback count, then per
    callback type, IY (target, 0 on EXIT), HL (subject), IX (manager).
    """
    out = bytearray()
    for record in simulate():
        out += bytes((record.index, record.result, record.carry, record.contact,
                      len(record.callbacks)))
        for kind, target, subject in record.callbacks:
            out += (bytes((kind,)) + _word(0 if target is None else pointers[target])
                    + _word(pointers[subject]) + _word(manager))
    return bytes(out)


def describe_log(log: bytes, pointers: list[int]) -> list[str]:
    names = {pointer: ("S", "T0", "T1", "T2", "T3")[i] for i, pointer in enumerate(pointers)}
    kinds = {ENTER: "ENTER", STAY: "STAY", EXIT: "EXIT"}
    lines, pos = [], 0
    while pos + 5 <= len(log):
        index, result, carry, contact, count = log[pos:pos + 5]
        pos += 5
        calls = []
        for _ in range(count):
            iy = int.from_bytes(log[pos + 1:pos + 3], "little")
            calls.append(f"{kinds.get(log[pos], log[pos])}({names.get(iy, hex(iy))})")
            pos += 7
        lines.append(f"step {index}: result={result:#04x} carry={carry} "
                     f"contact={contact} callbacks=[{' '.join(calls)}]")
    return lines


def render_include() -> str:
    lines = [
        ";; Generated by tools/build/ecs_collision_model.py. Do not edit.",
        ";; Step: command, pass kind, then x,y of S, T0, T1, T2, T3.",
        "ecscollision_steps:",
    ]
    for index, step in enumerate(SCENARIO):
        values = [step.cmd, step.kind]
        for x, y in step.positions:
            values += [x, y]
        lines.append("    .db " + ", ".join(str(v) for v in values) + f"  ; {index}: {step.note}")
    lines.append("    .db 0xFF")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = render_include()
    if args.check:
        if not args.output.is_file() or args.output.read_text() != text:
            print(f"{args.output} is stale; run without --check", file=sys.stderr)
            return 1
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
