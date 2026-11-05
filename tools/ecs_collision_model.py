#!/usr/bin/env python3
"""Reference model and scenario for the ECS COLLISION system (ABI 2.0, 9 and 9.1).

This file is the single source of truth for the emulator scenario run by
``examples/ecscollision``: ``--output`` renders the step table as an include,
``--check`` verifies a committed copy, and ``tests/emulator_smoke.py`` replays
the same model to know what the Z80 system must have logged.

Entity ids are 0..3 for manager A slots and 4..6 for manager B slots.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

COLLIDER = 0x01
COLLISIONABLE = 0x02

ENTER, STAY, EXIT = 1, 2, 3
ERR_OVERFLOW = 0x0A

WIDTH, HEIGHT = 4, 8

# Roles of A0..A3 and B0..B2.
ROLES = (COLLIDER, COLLISIONABLE, COLLIDER | COLLISIONABLE, COLLIDER,
         COLLISIONABLE, COLLIDER, COLLIDER | COLLISIONABLE)
A_IDS = (0, 1, 2, 3)
B_IDS = (4, 5, 6)

MODE_INTRA, MODE_INTER, MODE_TINY, MODE_EDGE = 0, 1, 2, 3
(CMD_NONE, CMD_DISABLE, CMD_ENABLE, CMD_DESTROY_ON_ENTER, CMD_WIDTH_ZERO, CMD_WIDTH_RESTORE,
 CMD_HEIGHT_ZERO, CMD_HEIGHT_RESTORE, CMD_LOCK, CMD_NULL_MANAGER, CMD_ABORT_ZERO,
 CMD_ABORT_CODE) = range(12)
ERR_ARGUMENT, ERR_BUSY, ERR_CALLBACK, ABORT_CODE = 0x01, 0x06, 0x09, 0x77

# (event capacity, pair capacity) per mode. Mode 2 is deliberately tiny.
CAPACITY = {MODE_INTRA: (8, 8), MODE_INTER: (8, 8), MODE_TINY: (2, 2), MODE_EDGE: (8, 8)}

PARK = ((0, 0), (20, 40), (40, 80), (60, 120), (10, 160), (30, 180), (50, 190))


@dataclass(frozen=True)
class Step:
    mode: int
    positions: tuple
    cmd: int = CMD_NONE
    arg: int = 0
    note: str = ""


def _at(**moves: tuple) -> tuple:
    """PARK with overrides, e.g. _at(a0=(20, 40), b1=(20, 40))."""
    names = ("a0", "a1", "a2", "a3", "b0", "b1", "b2")
    unknown = set(moves) - set(names)
    if unknown:
        raise ValueError(f"unknown entity override {unknown}")
    return tuple(moves.get(name, PARK[index]) for index, name in enumerate(names))


SCENARIO = (
    Step(MODE_INTRA, _at(), note="all parked: no contact"),
    Step(MODE_INTRA, _at(a0=(20, 40)), note="A0 collider reaches A1: ENTER"),
    Step(MODE_INTRA, _at(a0=(20, 40)), note="still touching: STAY"),
    Step(MODE_INTRA, _at(a0=(20, 40), a2=(20, 40)), note="A2 joins: ENTER pairs, order by slot"),
    Step(MODE_INTRA, _at(a2=(20, 40)), note="A0 leaves: EXIT after STAY"),
    Step(MODE_INTRA, _at(a2=(20, 40), a3=(24, 40)), note="edge touch only: no overlap"),
    Step(MODE_INTRA, _at(a2=(20, 40), a3=(23, 40)), note="one column of overlap"),
    Step(MODE_INTRA, _at(a2=(20, 40), a3=(23, 40)), CMD_DISABLE, 2, "A2 disabled: EXIT"),
    Step(MODE_INTRA, _at(a2=(20, 40), a3=(23, 40)), CMD_ENABLE, 2, "A2 enabled: ENTER again"),
    Step(MODE_INTRA, _at(a2=(20, 40), a3=(0, 100)), note="A3 leaves"),
    Step(MODE_INTRA, _at(a2=(20, 40), a3=(23, 40)), CMD_DESTROY_ON_ENTER, 0,
         "callback destroys A3 on ENTER, then collect"),
    Step(MODE_INTRA, _at(a2=(20, 40), a3=(23, 40)), note="A3 freed: EXIT with a FREE slot"),
    Step(MODE_INTER, _at(), note="inter-manager: nothing touching"),
    Step(MODE_INTER, _at(b1=(20, 40)), note="B1 collider onto A1: ENTER"),
    Step(MODE_INTER, _at(b0=(0, 0), b1=(20, 40)), note="B0 onto A0 collider"),
    Step(MODE_INTER, _at(b0=(0, 0), b2=(40, 80)), note="both-role pair reported once; EXIT last"),
    Step(MODE_INTER, _at(b0=(0, 0), b2=(40, 80)), CMD_DISABLE, 6, "B2 disabled: EXIT"),
    Step(MODE_TINY, _at(a0=(20, 40), a1=(20, 40), a2=(20, 40)), note="3 pairs, caps 2: OVERFLOW"),
    Step(MODE_TINY, _at(a0=(20, 40), a1=(20, 40), a2=(20, 40)), note="untracked pair stays dropped"),
    Step(MODE_TINY, _at(a1=(20, 40), a2=(20, 40)), note="EXIT dropped by a full event buffer"),
    Step(MODE_TINY, _at(), note="remaining tracked pair exits cleanly"),
    Step(MODE_EDGE, _at(), note="edge state starts empty"),
    Step(MODE_EDGE, _at(a0=(254, 40), a1=(253, 40)), note="x sums saturate at 255: still overlap"),
    Step(MODE_EDGE, _at(a0=(254, 40), a1=(253, 40)), CMD_WIDTH_ZERO, 1, "zero width never overlaps"),
    Step(MODE_EDGE, _at(a0=(254, 40), a1=(253, 40)), CMD_WIDTH_RESTORE, 1, "width back: ENTER"),
    Step(MODE_EDGE, _at(a0=(254, 40), a1=(253, 40)), CMD_HEIGHT_ZERO, 0, "zero height never overlaps"),
    Step(MODE_EDGE, _at(a0=(254, 40), a1=(253, 40)), CMD_HEIGHT_RESTORE, 0, "height back: ENTER"),
    Step(MODE_EDGE, _at(), note="parked: EXIT"),
    Step(MODE_EDGE, _at(a0=(40, 252), a1=(40, 251)), note="y sums saturate at 255: overlap"),
    Step(MODE_EDGE, _at(a0=(40, 252), a1=(40, 251)), CMD_LOCK, 0, "locked manager: BUSY, state untouched"),
    Step(MODE_EDGE, _at(a0=(40, 252), a1=(40, 251)), CMD_NULL_MANAGER, 0, "null manager: ARGUMENT, state untouched"),
    Step(MODE_EDGE, _at(), CMD_ABORT_ZERO, 0, "callback aborts with A=0: CALLBACK, pairs committed"),
    Step(MODE_EDGE, _at(a0=(20, 40), a1=(20, 40)), CMD_ABORT_CODE, 0, "callback aborts with A=0x77, kept"),
    Step(MODE_EDGE, _at(a0=(20, 40), a1=(20, 40)), note="pair was committed before delivery: STAY"),
    Step(MODE_EDGE, _at(), note="final EXIT"),
)

STATUS_ACTIVE, STATUS_DISABLED, STATUS_PENDING, STATUS_FREE = "active", "disabled", "pending", "free"


@dataclass
class StepRecord:
    index: int
    carry: int
    result: int
    flags: int
    pair_count: int
    events: list  # (a_id, b_id, type)
    callbacks: list  # (type, a_id, b_id)


@dataclass
class Model:
    status: dict = field(default_factory=lambda: {i: STATUS_ACTIVE for i in range(7)})
    pos: dict = field(default_factory=dict)
    pairs: dict = field(default_factory=lambda: {m: [] for m in CAPACITY})
    last: dict = field(default_factory=lambda: {m: ([], 0) for m in CAPACITY})
    size: dict = field(default_factory=lambda: {i: [WIDTH, HEIGHT] for i in range(7)})

    def active(self, ident: int) -> bool:
        return self.status[ident] == STATUS_ACTIVE

    def overlaps(self, a: int, b: int) -> bool:
        ax, ay = self.pos[a]
        bx, by = self.pos[b]
        (aw, ah), (bw, bh) = self.size[a], self.size[b]
        if 0 in (aw, ah, bw, bh):
            return False
        return (
            ax < min(255, bx + bw)
            and bx < min(255, ax + aw)
            and ay < min(255, by + bh)
            and by < min(255, ay + ah)
        )

    def in_contact(self, a: int, b: int) -> bool:
        if not (self.active(a) and self.active(b)):
            return False
        ra, rb = ROLES[a], ROLES[b]
        if not ((ra & COLLIDER and rb & COLLISIONABLE) or (rb & COLLIDER and ra & COLLISIONABLE)):
            return False
        return self.overlaps(a, b)

    def scan_order(self, mode: int):
        if mode == MODE_INTER:
            return [(a, b) for a in A_IDS for b in B_IDS]
        return [(a, b) for a in A_IDS for b in A_IDS if b > a]

    def run(self, index: int, step: Step) -> StepRecord:
        for ident, position in enumerate(step.positions):
            self.pos[ident] = position
        if step.cmd == CMD_DISABLE:
            assert self.status[step.arg] == STATUS_ACTIVE
            self.status[step.arg] = STATUS_DISABLED
        elif step.cmd == CMD_ENABLE:
            assert self.status[step.arg] == STATUS_DISABLED
            self.status[step.arg] = STATUS_ACTIVE

        elif step.cmd == CMD_WIDTH_ZERO:
            self.size[step.arg][0] = 0
        elif step.cmd == CMD_WIDTH_RESTORE:
            self.size[step.arg][0] = WIDTH
        elif step.cmd == CMD_HEIGHT_ZERO:
            self.size[step.arg][1] = 0
        elif step.cmd == CMD_HEIGHT_RESTORE:
            self.size[step.arg][1] = HEIGHT

        if step.cmd in (CMD_LOCK, CMD_NULL_MANAGER):
            # Validation errors leave the whole state untouched: the log shows
            # the previous call's events and flags and no callbacks.
            events, flags = self.last[step.mode]
            return StepRecord(
                index=index, carry=1,
                result=ERR_BUSY if step.cmd == CMD_LOCK else ERR_ARGUMENT,
                flags=flags, pair_count=len(self.pairs[step.mode]),
                events=list(events), callbacks=[],
            )

        event_cap, pair_cap = CAPACITY[step.mode]
        previous = self.pairs[step.mode]
        current: list = []
        events: list = []
        overflow = False
        contact = []
        for pair in self.scan_order(step.mode):
            if not self.in_contact(*pair):
                continue
            contact.append(pair)
            kind = STAY if pair in previous else ENTER
            if len(events) < event_cap:
                events.append((pair[0], pair[1], kind))
            else:
                overflow = True
            if len(current) < pair_cap:
                current.append(pair)
            else:
                overflow = True
        for pair in previous:
            if pair in contact:
                continue
            if len(events) < event_cap:
                events.append((pair[0], pair[1], EXIT))
            else:
                overflow = True
        self.pairs[step.mode] = current

        self.last[step.mode] = (list(events), 1 if overflow else 0)
        if step.cmd in (CMD_ABORT_ZERO, CMD_ABORT_CODE):
            # The callback stops delivery at the first event.
            return StepRecord(
                index=index, carry=1,
                result=ERR_CALLBACK if step.cmd == CMD_ABORT_ZERO else ABORT_CODE,
                flags=1 if overflow else 0, pair_count=len(current), events=events,
                callbacks=[(events[0][2], events[0][0], events[0][1])],
            )
        callbacks = []
        for a, b, kind in events:
            callbacks.append((kind, a, b))
            if step.cmd == CMD_DESTROY_ON_ENTER and kind == ENTER and self.active(b):
                self.status[b] = STATUS_PENDING
        if step.cmd == CMD_DESTROY_ON_ENTER:
            for ident, status in self.status.items():
                if status == STATUS_PENDING:
                    self.status[ident] = STATUS_FREE
        return StepRecord(
            index=index,
            carry=1 if overflow else 0,
            result=ERR_OVERFLOW if overflow else 0,
            flags=1 if overflow else 0,
            pair_count=len(current),
            events=events,
            callbacks=callbacks,
        )


def simulate() -> list[StepRecord]:
    model = Model()
    return [model.run(index, step) for index, step in enumerate(SCENARIO)]

def _word(value: int) -> bytes:
    return bytes((value & 0xFF, value >> 8))


def expected_log(pointers: list[int], manager_a: int, manager_b: int) -> bytes:
    """Bytes ``examples/ecscollision`` must have written to ecscollision_log.

    Record: step, result, carry, flags, pair count, event count, events
    (entity A, entity B, type), callback count, callbacks (type, IX, IY, HL, DE).
    """
    out = bytearray()
    for record, step in zip(simulate(), SCENARIO):
        out += bytes((record.index, record.result, record.carry, record.flags,
                      record.pair_count, len(record.events)))
        for a, b, kind in record.events:
            out += _word(pointers[a]) + _word(pointers[b]) + bytes((kind,))
        out += bytes((len(record.callbacks),))
        second = manager_b if step.mode == MODE_INTER else manager_a
        for kind, a, b in record.callbacks:
            out += (bytes((kind,)) + _word(pointers[a]) + _word(pointers[b])
                    + _word(manager_a) + _word(second))
    return bytes(out)


def describe_log(log: bytes, pointers: list[int]) -> list[str]:
    """Readable per-step view of a log, for assertion messages."""
    names = {pointer: ("A", "A", "A", "A", "B", "B", "B")[i] + str(i if i < 4 else i - 4)
             for i, pointer in enumerate(pointers)}
    kinds = {ENTER: "ENTER", STAY: "STAY", EXIT: "EXIT"}
    lines, pos = [], 0
    while pos + 6 <= len(log):
        index, result, carry, flags, pairs, count = log[pos:pos + 6]
        pos += 6
        events = []
        for _ in range(count):
            a = int.from_bytes(log[pos:pos + 2], "little")
            b = int.from_bytes(log[pos + 2:pos + 4], "little")
            events.append(f"{kinds.get(log[pos + 4], log[pos + 4])}({names.get(a, hex(a))},{names.get(b, hex(b))})")
            pos += 5
        callbacks = log[pos] if pos < len(log) else 0
        pos += 1 + 9 * callbacks
        lines.append(f"step {index}: result={result:#04x} carry={carry} flags={flags} "
                     f"pairs={pairs} events=[{' '.join(events)}] callbacks={callbacks}")
    return lines


def render_include() -> str:
    lines = [
        ";; Generated by tools/ecs_collision_model.py. Do not edit.",
        ";; Step: mode, command, argument, then x,y for A0..A3 and B0..B2.",
        "ecscollision_steps:",
    ]
    for index, step in enumerate(SCENARIO):
        values = [step.mode, step.cmd, step.arg]
        for x, y in step.positions:
            values += [x, y]
        lines.append("    .db " + ", ".join(str(v) for v in values) + f"  ; {index}: {step.note}")
    lines.append("    .db 0xFF")
    lines.append(f"ECSCOLLISION_STEP_COUNT = {len(SCENARIO)}")
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
