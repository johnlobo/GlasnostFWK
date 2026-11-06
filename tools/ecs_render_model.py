#!/usr/bin/env python3
"""Oracle for the ECS selective renderer (ABI 2.0, section 8).

The renderer restores and redraws only what changed. Its result must equal a
full recomposition: the background with every ACTIVE and VISIBLE entity drawn
in stable global Y order. This file generates a deterministic scenario, renders
that ideal image frame by frame, and emits the scenario as an include for
examples/ecsrender. tests/emulator_smoke.py compares video RAM with the ideal
image after every frame.

Entities 0..4 live in manager A (slots 0..4), 5..8 in manager B (slots 0..3).
"""

from __future__ import annotations

import argparse
import random
import sys
from dataclasses import dataclass
from pathlib import Path

SCREEN_WIDTH, SCREEN_HEIGHT = 80, 200
VRAM_BASE = 0xC000

(CMD_NONE, CMD_HIDE, CMD_SHOW, CMD_DISABLE, CMD_ENABLE, CMD_DESTROY) = range(6)

# (manager, width bytes, height lines, sort offset)
ENTITIES = (
    (0, 3, 8, 0), (0, 4, 8, 0), (0, 2, 10, 0), (0, 4, 6, 0), (0, 3, 8, 0),
    (1, 4, 8, 0), (1, 3, 10, 0), (1, 4, 8, 12), (1, 2, 6, 0),
)
FRAMES = 36
SEED = 20261105

# Forced overlaps in frames 1..3 (every entity is still ACTIVE and VISIBLE
# there). Frames 1 and 3 hold equal keys (same manager and across managers),
# frame 2 separates them again: ties must resolve by manager, then slot, and
# the restore must undo exactly what the previous draw did. Slot order differs from Y order, across both managers, and entity 7
# has a sort offset of 12. Frame 2 and 3 swap the Y order of some pairs.
FORCED = {
    (1, 0): (20, 60), (1, 1): (22, 60), (1, 2): (21, 64), (1, 5): (21, 60), (1, 7): (23, 50),
    (2, 0): (20, 60), (2, 1): (22, 68), (2, 2): (21, 64), (2, 5): (21, 58), (2, 7): (23, 50),
    (3, 0): (20, 72), (3, 1): (22, 72), (3, 2): (21, 64), (3, 5): (21, 72), (3, 7): (23, 50),
}

ACTIVE, DISABLED, PENDING, FREE = "active", "disabled", "pending", "free"


def background_byte(address: int) -> int:
    return (5 * (address & 0xFF) + (address >> 8)) & 0xFF


def vram_address(x: int, y: int) -> int:
    return VRAM_BASE + 80 * (y // 8) + 2048 * (y % 8) + x


def sprite_bytes(entity: int) -> bytes:
    _, width, height, _ = ENTITIES[entity]
    return bytes(((entity + 1) * 23 + i * 7 + 1) & 0xFF for i in range(width * height))


@dataclass(frozen=True)
class Frame:
    commands: tuple   # per entity: (cmd, x, y)


def _scenario() -> tuple:
    rng = random.Random(SEED)
    positions = [(rng.randrange(0, 70), rng.randrange(0, 180)) for _ in ENTITIES]
    state = [ACTIVE] * len(ENTITIES)
    visible = [True] * len(ENTITIES)
    frames = []
    for index in range(FRAMES):
        row = []
        for e in range(len(ENTITIES)):
            x, y = positions[e]
            cmd = CMD_NONE
            roll = rng.random()
            if state[e] == FREE:
                row.append((CMD_NONE, x, y))
                continue
            if index > 0 and roll < 0.62:
                x = max(0, min(78, x + rng.randrange(-6, 7)))
                y = max(0, min(196, y + rng.randrange(-9, 10)))
            elif index > 0 and roll < 0.70:
                x, y = rng.randrange(0, 79), rng.randrange(0, 197)   # a jump
            elif index > 2:
                if state[e] == ACTIVE and visible[e] and roll < 0.76:
                    cmd = CMD_HIDE
                elif state[e] == ACTIVE and not visible[e] and roll < 0.86:
                    cmd = CMD_SHOW
                elif state[e] == ACTIVE and roll < 0.90:
                    cmd = CMD_DISABLE
                elif state[e] == DISABLED and roll < 0.92:
                    cmd = CMD_ENABLE
            if index == 4 and e == 0:
                x, y = 78, 196           # clipped at the right and bottom edges
            if (index, e) in ((20, 3), (27, 8)):
                cmd = CMD_DESTROY        # one ACTIVE or DISABLED entity per manager
            if (index, e) in FORCED:
                x, y = FORCED[(index, e)]
                cmd = CMD_NONE
            positions[e] = (x, y)
            if cmd == CMD_HIDE:
                visible[e] = False
            elif cmd == CMD_SHOW:
                visible[e] = True
            elif cmd == CMD_DISABLE:
                state[e] = DISABLED
            elif cmd == CMD_ENABLE:
                state[e] = ACTIVE
            elif cmd == CMD_DESTROY:
                state[e] = FREE
            row.append((cmd, x, y))
        frames.append(Frame(tuple(row)))
    return tuple(frames)


SCENARIO = _scenario()


def ideal_frames() -> list[bytes]:
    """Per frame, the visible 80x200 screen as bytes indexed y*80+x."""
    base = bytearray(SCREEN_WIDTH * SCREEN_HEIGHT)
    for y in range(SCREEN_HEIGHT):
        for x in range(SCREEN_WIDTH):
            base[y * SCREEN_WIDTH + x] = background_byte(vram_address(x, y))
    state = [ACTIVE] * len(ENTITIES)
    visible = [True] * len(ENTITIES)
    pos = [(0, 0)] * len(ENTITIES)
    sprites = [sprite_bytes(e) for e in range(len(ENTITIES))]
    result = []
    for frame in SCENARIO:
        for e, (cmd, x, y) in enumerate(frame.commands):
            pos[e] = (x, y)
            if cmd == CMD_HIDE:
                visible[e] = False
            elif cmd == CMD_SHOW:
                visible[e] = True
            elif cmd == CMD_DISABLE:
                state[e] = DISABLED
            elif cmd == CMD_ENABLE:
                state[e] = ACTIVE
            elif cmd == CMD_DESTROY:
                state[e] = FREE
        image = bytearray(base)
        order = sorted(
            (e for e in range(len(ENTITIES)) if state[e] == ACTIVE and visible[e]),
            key=lambda e: pos[e][1] + ENTITIES[e][3],   # stable: manager then slot order
        )
        for e in order:
            _, width, height, _ = ENTITIES[e]
            x, y = pos[e]
            for row in range(height):
                for col in range(width):
                    if x + col < SCREEN_WIDTH and y + row < SCREEN_HEIGHT:
                        image[(y + row) * SCREEN_WIDTH + x + col] = sprites[e][row * width + col]
        result.append(bytes(image))
    return result


def describe_diff(expected: bytes, actual: bytes, limit: int = 12) -> list[str]:
    lines = []
    for index, (a, b) in enumerate(zip(expected, actual)):
        if a != b:
            lines.append(f"x={index % SCREEN_WIDTH} y={index // SCREEN_WIDTH}: "
                         f"expected {a:02x} actual {b:02x}")
            if len(lines) >= limit:
                break
    return lines


def render_include() -> str:
    lines = [
        ";; Generated by tools/ecs_render_model.py. Do not edit.",
        ";; Entity table: manager (0=A,1=B), width, height, sort offset (word), sprite.",
        "ecsrender_entity_table:",
    ]
    for e, (manager, width, height, offset) in enumerate(ENTITIES):
        lines.append(f"    .db {manager}, {width}, {height}")
        lines.append(f"    .dw {offset}, ecsrender_sprite_{e}  ; entity {e}")
    lines.append(";; Per frame, per entity: command, x, y.")
    lines.append("ecsrender_frames:")
    for index, frame in enumerate(SCENARIO):
        cells = ", ".join(f"{cmd}, {x}, {y}" for cmd, x, y in frame.commands)
        lines.append(f"    .db {cells}  ; frame {index}")
    for e, (_, width, height, _) in enumerate(ENTITIES):
        data = ", ".join(str(b) for b in sprite_bytes(e))
        lines.append(f"ecsrender_sprite_{e}: .db {data}")
    lines.append(f"ECSRENDER_FRAMES = {FRAMES}")
    lines.append(f"ECSRENDER_ENTITIES = {len(ENTITIES)}")
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
