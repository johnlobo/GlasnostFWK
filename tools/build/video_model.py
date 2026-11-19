#!/usr/bin/env python3
"""Independent, deterministic CPC video-address model used by generator/tests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


def number(value: int | str) -> int:
    return value if isinstance(value, int) else int(value, 0)


@dataclass(frozen=True)
class Segment:
    y_start: int
    height: int
    base: int
    row_bytes: int
    raster_stride: int

    @classmethod
    def from_dict(cls, raw: dict) -> "Segment":
        return cls(
            y_start=raw["y_start"],
            height=raw["height"],
            base=number(raw["base"]),
            row_bytes=raw["row_bytes"],
            raster_stride=number(raw["raster_stride"]),
        )

    def address(self, x_byte: int, y: int) -> int:
        local_y = y - self.y_start
        if not 0 <= local_y < self.height:
            raise ValueError(f"y={y} is outside segment {self.y_start}..{self.y_start + self.height - 1}")
        if not 0 <= x_byte < self.row_bytes:
            raise ValueError(f"x_byte={x_byte} is outside 0..{self.row_bytes - 1}")
        return self.base + (local_y & 7) * self.raster_stride + (local_y >> 3) * self.row_bytes + x_byte


def segments(profile: dict) -> list[Segment]:
    return [Segment.from_dict(raw) for raw in profile["segments"]]


def address(profile: dict, x_byte: int, y: int) -> int:
    for segment in segments(profile):
        if segment.y_start <= y < segment.y_start + segment.height:
            return segment.address(x_byte, y)
    raise ValueError(f"y={y} has no segment")


def visible_addresses(profile: dict) -> set[int]:
    width = profile["width_bytes"]
    height = profile["height_lines"]
    return {address(profile, x, y) for y in range(height) for x in range(width)}


def contiguous_runs(values: Iterable[int]) -> list[tuple[int, int]]:
    ordered = sorted(set(values))
    if not ordered:
        return []
    runs: list[tuple[int, int]] = []
    start = previous = ordered[0]
    for value in ordered[1:]:
        if value != previous + 1:
            runs.append((start, previous))
            start = value
        previous = value
    runs.append((start, previous))
    return runs


def window_addresses(profile: dict) -> set[int]:
    result: set[int] = set()
    for window in profile["memory_windows"]:
        result.update(range(number(window["start"]), number(window["end"]) + 1))
    return result


def address_at_origin(profile: dict, x_byte: int, y: int, byte_offset: int) -> int:
    """Candidate classic-CPC CRTC origin in one 16 KiB video page.

    The CRTC advances the character address within each 2 KiB raster bank;
    crossing that bank wraps inside the same bank. ``byte_offset`` is physical
    bytes, not an R13 value. Register programming needs a visible probe.
    """
    windows = profile["memory_windows"]
    if len(windows) != 1:
        raise ValueError("origin model requires one video window")
    start = number(windows[0]["start"])
    end = number(windows[0]["end"])
    original = address(profile, x_byte, y)
    if end - start + 1 != 0x4000:
        raise ValueError("origin model requires a 16 KiB video page")
    if not start <= original <= end:
        raise ValueError("base address falls outside video window")
    relative = original - start
    return start + (relative & ~0x7FF) + ((relative & 0x7FF) + byte_offset) % 0x800


def visible_at_origin(profile: dict, byte_offset: int) -> set[int]:
    """Physical bytes read for every visible byte at a candidate origin."""
    return {
        address_at_origin(profile, x, y, byte_offset)
        for y in range(profile["height_lines"])
        for x in range(profile["width_bytes"])
    }


def entering_strip(
    profile: dict, next_offset: int, direction: str, tile_width_bytes: int, tile_height: int = 8
) -> set[int]:
    """Physical addresses for the row or column entering after one tile step."""
    width = profile["width_bytes"]
    height = profile["height_lines"]
    if not 0 < tile_width_bytes <= width or not 0 < tile_height <= height:
        raise ValueError("tile size is outside visible geometry")
    if direction == "east":
        xs, ys = range(width - tile_width_bytes, width), range(height)
    elif direction == "west":
        xs, ys = range(tile_width_bytes), range(height)
    elif direction == "south":
        xs, ys = range(width), range(height - tile_height, height)
    elif direction == "north":
        xs, ys = range(width), range(tile_height)
    else:
        raise ValueError(f"unknown direction: {direction}")
    return {address_at_origin(profile, x, y, next_offset) for y in ys for x in xs}


def unsafe_pre_switch_fill(
    profile: dict, current_offset: int, next_offset: int,
    direction: str, tile_width_bytes: int, tile_height: int = 8,
) -> set[int]:
    """Entering bytes that are still visible before a candidate origin switch."""
    return visible_at_origin(profile, current_offset) & entering_strip(
        profile, next_offset, direction, tile_width_bytes, tile_height
    )
