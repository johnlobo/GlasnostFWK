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
