#!/usr/bin/env python3
"""Reference model and scenario for the ECS animation system (ABI 2.0, 10).

Single source of truth for the emulator scenario run by examples/ecsanimation:
``--output`` renders the command table as an include, ``--check`` verifies a
committed copy, and tests/emulator_smoke.py replays the same model to know
what the Z80 code must have logged.

Entities 0..2 all carry RENDER|ANIMATION. Sprite ids: 0..2 are the frames of
descriptor A (count 3, duration 2), 3..4 those of descriptor B (count 2,
duration 1); id 5 means a null sprite pointer.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

DESCRIPTORS = {
    "A": {"count": 3, "duration": 2, "frames": (0, 1, 2)},
    "B": {"count": 2, "duration": 1, "frames": (3, 4)},
    "C": {"count": 130, "duration": 1, "frames": tuple(i % 5 for i in range(130))},
    "D": {"count": 1, "duration": 3, "frames": (0,)},
}
ENTITY_COUNT = 5
NO_SPRITE = 5
DESC_CODE = {None: 0, "A": 1, "B": 2, "C": 3, "D": 4}

# Initial animations (applied with fwk_ecs_anim_set after creation).
INITIAL = ("A", "B", None, "C", "B")
# E3 starts at frame 127 so the first ticks cross the 128 boundary.
INITIAL_FRAME = (None, None, None, 127, None)
# E4 mimics an entity created from a template that already holds descriptor B
# with TIMER 0: fwk_ecs_anim_set(B) must still start it.
TEMPLATE_STARTED = (False, False, False, False, True)

# Per tick: optional (entity, descriptor) change applied before the system call.
COMMANDS = (
    None,            # t0
    None,            # t1
    None,            # t2
    (0, "B"),        # t3  E0 switches to B: restart
    None,            # t4
    (0, "B"),        # t5  same descriptor: nothing restarts
    (1, None),       # t6  E1 stops, keeps its sprite
    (0, "A"),        # t7  E0 back to A: restart
    None,            # t8
    (0, "A"),        # t9  same descriptor mid-cycle (A, frame 1): must NOT restart
    (2, "D"),        # t10 E2 gets a single-frame animation (count 1, duration 3)
    None,            # t11
    (1, "B"),        # t12 E1 (stopped at t6) is re-selected: restarts
    None,            # t13
)

DIRTY = 0x02


@dataclass
class Entity:
    desc: str | None = None
    frame: int = 0
    timer: int = 0
    sprite: int = NO_SPRITE
    flags: int = 0


@dataclass
class TickRecord:
    index: int
    entities: list  # (frame, timer, sprite id, flags) per entity


def anim_set(entity: Entity, desc: str | None) -> None:
    if entity.desc == desc and entity.timer != 0:
        return
    entity.desc = desc
    if desc is None:
        entity.frame = 0
        entity.timer = 0
        return
    entity.timer = DESCRIPTORS[desc]["duration"]
    entity.frame = 0
    entity.sprite = DESCRIPTORS[desc]["frames"][0]
    entity.flags |= DIRTY


def system(entities: list) -> None:
    for entity in entities:
        if entity.desc is None:
            continue
        entity.timer -= 1
        if entity.timer != 0:
            continue
        descriptor = DESCRIPTORS[entity.desc]
        entity.timer = descriptor["duration"]
        entity.frame = (entity.frame + 1) % descriptor["count"]
        entity.sprite = descriptor["frames"][entity.frame]
        entity.flags |= DIRTY


def simulate() -> list[TickRecord]:
    entities = [Entity() for _ in range(ENTITY_COUNT)]
    for entity, desc, frame, templated in zip(entities, INITIAL, INITIAL_FRAME, TEMPLATE_STARTED):
        if templated:
            entity.desc = desc      # descriptor already in the template, timer 0
        anim_set(entity, desc)
        if frame is not None:
            entity.frame = frame
    records = []
    for index, command in enumerate(COMMANDS):
        for entity in entities:
            entity.flags = 0          # the harness clears DIRTY before each tick
        if command is not None:
            anim_set(entities[command[0]], command[1])
        system(entities)
        records.append(TickRecord(index, [(e.frame, e.timer, e.sprite, e.flags) for e in entities]))
    return records


def expected_log(sprites: list[int]) -> bytes:
    """sprites[i] is the address of sprite id i (ids 0..4); id 5 is address 0.

    Record per tick: index, then per entity frame, timer, sprite (2 bytes), flags.
    """
    table = list(sprites) + [0]
    out = bytearray()
    for record in simulate():
        out.append(record.index)
        for frame, timer, sprite, flags in record.entities:
            out += bytes((frame, timer, table[sprite] & 0xFF, table[sprite] >> 8, flags))
    return bytes(out)


def describe_log(log: bytes, sprites: list[int]) -> list[str]:
    names = {address: f"s{i}" for i, address in enumerate(sprites)}
    names[0] = "none"
    lines, pos = [], 0
    size = 1 + 5 * ENTITY_COUNT
    while pos + size <= len(log):
        parts = []
        for entity in range(ENTITY_COUNT):
            frame, timer, lo, hi, flags = log[pos + 1 + entity * 5:pos + 6 + entity * 5]
            address = lo | hi << 8
            parts.append(f"E{entity}[f{frame} t{timer} {names.get(address, hex(address))} "
                         f"{'D' if flags & DIRTY else '-'}]")
        lines.append(f"tick {log[pos]}: " + " ".join(parts))
        pos += size
    return lines


def render_include() -> str:
    lines = [
        ";; Generated by tools/ecs_animation_model.py. Do not edit.",
        ";; Per tick: entity (0xFF = no change), descriptor (0 none, 1 A, 2 B).",
        "ecsanimation_commands:",
    ]
    for index, command in enumerate(COMMANDS):
        entity, desc = (0xFF, 0) if command is None else (command[0], DESC_CODE[command[1]])
        lines.append(f"    .db {entity}, {desc}  ; t{index}")
    lines.append("    .db 0xFE, 0")
    initial = ", ".join(str(DESC_CODE[d]) for d in INITIAL)
    frames = ", ".join("0xFF" if f is None else str(f) for f in INITIAL_FRAME)
    templated = ", ".join("1" if t else "0" for t in TEMPLATE_STARTED)
    lines.append(f"ecsanimation_initial: .db {initial}")
    lines.append(f"ecsanimation_initial_frame: .db {frames}  ; 0xFF = keep what anim_set chose")
    lines.append(f"ecsanimation_templated: .db {templated}  ; 1 = template already holds the descriptor, TIMER 0")
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
