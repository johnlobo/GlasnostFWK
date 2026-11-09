#!/usr/bin/env python3
"""Validate an ECS project profile and emit its deterministic Z80 ABI include."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PORTFOLIO = ROOT / "framework" / "manifests" / "ecs-components.json"
NAME = re.compile(r"^[a-z][a-z0-9_]*$")
BYTES = re.compile(r"^bytes\[([1-9][0-9]*)\]$")
FORMAT_IDS = {"u8": 1, "u16": 2, "fixed_8_8": 3}
FIXED_SIZES = {
    "u8": 1,
    "i8": 1,
    "u16": 2,
    "i16": 2,
    "fixed_8_8": 2,
    "pointer": 2,
}
RESERVED_FIELDS = {"components", "status", "type", "x", "y", "width", "height", "cadence"}


@dataclass(frozen=True)
class Field:
    name: str
    type_name: str
    size: int


@dataclass(frozen=True)
class Component:
    name: str
    dependencies: tuple[str, ...]
    fields: tuple[Field, ...]
    required: bool = False


@dataclass(frozen=True)
class GeneratedProfile:
    include: str
    preview: dict


def _object(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _name(value: object, label: str) -> str:
    if not isinstance(value, str) or not NAME.fullmatch(value):
        raise ValueError(f"{label} must match {NAME.pattern}")
    return value


def _type_size(type_name: object, x_format: str, y_format: str, label: str) -> tuple[str, int]:
    if not isinstance(type_name, str):
        raise ValueError(f"{label} type must be a string")
    velocity_x = {"u8": "i8", "u16": "i16", "fixed_8_8": "fixed_8_8"}[x_format]
    velocity_y = {"u8": "i8", "u16": "i16", "fixed_8_8": "fixed_8_8"}[y_format]
    resolved = {
        "x_format": x_format,
        "y_format": y_format,
        "velocity_x": velocity_x,
        "velocity_y": velocity_y,
    }.get(type_name, type_name)
    if resolved in FIXED_SIZES:
        return resolved, FIXED_SIZES[resolved]
    match = BYTES.fullmatch(resolved)
    if match is None:
        raise ValueError(f"{label} has unsupported type {type_name!r}")
    size = int(match.group(1))
    if size > 128:
        raise ValueError(f"{label} byte array exceeds the 128-byte entity limit")
    return resolved, size


def _fields(value: object, x_format: str, y_format: str, label: str) -> tuple[Field, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{label} fields must be a list")
    result: list[Field] = []
    seen: set[str] = set()
    for index, raw in enumerate(value):
        item = _object(raw, f"{label} field {index}")
        if set(item) != {"name", "type"}:
            raise ValueError(f"{label} field {index} must contain only name and type")
        name = _name(item["name"], f"{label} field {index} name")
        if name in seen:
            raise ValueError(f"{label} has duplicate field {name}")
        seen.add(name)
        resolved, size = _type_size(item["type"], x_format, y_format, f"{label}.{name}")
        result.append(Field(name, resolved, size))
    return tuple(result)


def _component(raw: object, x_format: str, y_format: str, label: str, *, portfolio: bool) -> Component:
    item = _object(raw, label)
    allowed = {"name", "dependencies", "fields"} | ({"required"} if portfolio else set())
    if set(item) - allowed or not {"name", "fields"} <= set(item):
        raise ValueError(f"{label} has invalid keys")
    name = _name(item["name"], f"{label} name")
    dependencies = item.get("dependencies", [])
    if not isinstance(dependencies, list):
        raise ValueError(f"{label} dependencies must be a list")
    resolved_dependencies = tuple(
        _name(value, f"{label} dependency") for value in dependencies
    )
    if len(set(resolved_dependencies)) != len(resolved_dependencies):
        raise ValueError(f"{label} has duplicate dependencies")
    required = item.get("required", False)
    if not isinstance(required, bool):
        raise ValueError(f"{label} required must be boolean")
    return Component(
        name,
        resolved_dependencies,
        _fields(item["fields"], x_format, y_format, label),
        required,
    )


def _load_portfolio(data: dict, x_format: str, y_format: str) -> tuple[int, int, list[Component]]:
    if set(data) != {"abi", "components"}:
        raise ValueError("component portfolio must contain abi and components")
    abi = _object(data["abi"], "portfolio abi")
    if set(abi) != {"major", "minor"}:
        raise ValueError("portfolio abi must contain major and minor")
    major, minor = abi["major"], abi["minor"]
    if (
        isinstance(major, bool)
        or isinstance(minor, bool)
        or not isinstance(major, int)
        or not isinstance(minor, int)
        or major < 0
        or minor < 0
    ):
        raise ValueError("portfolio ABI versions must be non-negative integers")
    raw_components = data["components"]
    if not isinstance(raw_components, list):
        raise ValueError("portfolio components must be a list")
    components = [
        _component(raw, x_format, y_format, f"portfolio component {index}", portfolio=True)
        for index, raw in enumerate(raw_components)
    ]
    return major, minor, components


def _coordinate_format(value: object, axis: str) -> str:
    if value not in FORMAT_IDS:
        raise ValueError(f"{axis}_format must be u8, u16 or fixed_8_8")
    return str(value)


def _validate_video_range(x_format: str, y_format: str, video_profile: dict | None) -> None:
    if video_profile is None:
        return
    width = video_profile.get("width_bytes")
    height = video_profile.get("height_lines")
    if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
        raise ValueError("video profile has invalid width_bytes or height_lines")
    if x_format != "u16" and width - 1 > 255:
        raise ValueError(f"{x_format} X cannot represent {width} screen-byte columns")
    if y_format != "u16" and height - 1 > 255:
        raise ValueError(f"{y_format} Y cannot represent {height} scanlines")


def generate(manifest: dict, portfolio: dict, video_profile: dict | None = None) -> GeneratedProfile:
    ecs = _object(manifest.get("ecs"), "ecs")
    allowed = {"x_format", "y_format", "components", "custom_components", "fields"}
    if set(ecs) - allowed or not {"x_format", "y_format", "components"} <= set(ecs):
        raise ValueError("ecs must define x_format, y_format and components")
    x_format = _coordinate_format(ecs["x_format"], "x")
    y_format = _coordinate_format(ecs["y_format"], "y")
    _validate_video_range(x_format, y_format, video_profile)
    major, minor, builtins = _load_portfolio(portfolio, x_format, y_format)
    custom_raw = ecs.get("custom_components", [])
    if not isinstance(custom_raw, list):
        raise ValueError("ecs custom_components must be a list")
    custom = [
        _component(raw, x_format, y_format, f"custom component {index}", portfolio=False)
        for index, raw in enumerate(custom_raw)
    ]
    definitions: dict[str, Component] = {}
    for component in builtins + custom:
        if component.name in definitions:
            raise ValueError(f"duplicate component definition: {component.name}")
        definitions[component.name] = component
    for component in definitions.values():
        for dependency in component.dependencies:
            if dependency not in definitions:
                raise ValueError(
                    f"component {component.name} has unknown dependency {dependency}"
                )
    dependency_state: dict[str, int] = {}

    def validate_dependencies(name: str) -> None:
        state = dependency_state.get(name, 0)
        if state == 1:
            raise ValueError(f"component dependency cycle at {name}")
        if state == 2:
            return
        dependency_state[name] = 1
        for dependency in definitions[name].dependencies:
            validate_dependencies(dependency)
        dependency_state[name] = 2

    for name in definitions:
        validate_dependencies(name)
    required = [component.name for component in builtins if component.required]
    if required != ["render"]:
        raise ValueError("ABI 2.0 portfolio must define render as its only required component")
    requested_raw = ecs["components"]
    if not isinstance(requested_raw, list):
        raise ValueError("ecs components must be a list")
    requested = [_name(value, "ecs component") for value in requested_raw]
    if len(set(requested)) != len(requested):
        raise ValueError("ecs components contains duplicates")

    resolved: list[str] = []
    inserted: list[str] = []
    visiting: set[str] = set()

    def add(name: str, explicit: bool) -> None:
        if name in resolved:
            return
        if name in visiting:
            raise ValueError(f"component dependency cycle at {name}")
        component = definitions.get(name)
        if component is None:
            raise ValueError(f"unknown ECS component: {name}")
        visiting.add(name)
        for dependency in component.dependencies:
            add(dependency, False)
        visiting.remove(name)
        if name not in resolved:
            resolved.append(name)
            if not explicit and name not in required and name not in requested:
                inserted.append(name)

    for name in required:
        add(name, False)
    for name in requested:
        add(name, True)
    if len(resolved) > 16:
        raise ValueError("ECS profile exceeds the 16-component mask")
    if not resolved or resolved[0] != "render":
        raise ValueError("render must occupy component bit 0")

    universal_fields = _fields(ecs.get("fields", []), x_format, y_format, "ecs")
    for field in universal_fields:
        if field.name in RESERVED_FIELDS or field.name.startswith("render_"):
            raise ValueError(f"universal field name is reserved: {field.name}")

    offsets: list[tuple[str, int, int, str]] = [
        ("COMPONENTS", 0, 2, "u16"),
        ("STATUS", 2, 1, "u8"),
        ("TYPE", 3, 1, "u8"),
    ]
    offset = 4
    for symbol, format_name in (("X", x_format), ("Y", y_format)):
        size = FIXED_SIZES[format_name]
        offsets.append((symbol, offset, size, format_name))
        offset += size
    offsets.extend((
        ("WIDTH", offset, 1, "u8"),
        ("HEIGHT", offset + 1, 1, "u8"),
        ("CADENCE", offset + 2, 1, "u8"),
    ))
    offset += 3
    emitted_symbols = {symbol for symbol, _, _, _ in offsets}
    component_preview: list[dict] = []
    for bit, name in enumerate(resolved):
        component = definitions[name]
        start = offset
        for field in component.fields:
            symbol = f"{name}_{field.name}".upper()
            if symbol in emitted_symbols:
                raise ValueError(f"duplicate generated field symbol: ECS_E_{symbol}")
            emitted_symbols.add(symbol)
            offsets.append((symbol, offset, field.size, field.type_name))
            offset += field.size
        component_preview.append(
            {"name": name, "bit": bit, "mask": 1 << bit, "offset": start, "size": offset - start}
        )
    for field in universal_fields:
        symbol = field.name.upper()
        if symbol in emitted_symbols:
            raise ValueError(f"duplicate generated field symbol: ECS_E_{symbol}")
        emitted_symbols.add(symbol)
        offsets.append((symbol, offset, field.size, field.type_name))
        offset += field.size
    if offset > 128:
        raise ValueError(f"ECS entity size {offset} exceeds the 128-byte ABI limit")

    valid_mask = (1 << len(resolved)) - 1
    lines = [
        ";; Generated by tools/build/gen_ecs_profile.py. Do not edit.",
        f";; Resolved components: {', '.join(name.upper() for name in resolved)}",
        f";; Inserted dependencies: {', '.join(name.upper() for name in inserted) or 'none'}",
        f"ECS_ABI_MAJOR = {major}",
        f"ECS_ABI_MINOR = {minor}",
        "ECS_FORMAT_U8 = 1",
        "ECS_FORMAT_U16 = 2",
        "ECS_FORMAT_FIXED_8_8 = 3",
        f"ECS_X_FORMAT = {FORMAT_IDS[x_format]}",
        f"ECS_X_SIZE = {FIXED_SIZES[x_format]}",
        f"ECS_Y_FORMAT = {FORMAT_IDS[y_format]}",
        f"ECS_Y_SIZE = {FIXED_SIZES[y_format]}",
        "",
    ]
    for bit, name in enumerate(resolved):
        upper = name.upper()
        lines.extend((f"ECS_C_{upper}_BIT = {bit}", f"ECS_C_{upper} = 0x{1 << bit:04X}"))
    lines.extend((f"ECS_COMPONENT_VALID_MASK = 0x{valid_mask:04X}", ""))
    if video_profile is not None:
        lines.extend(
            (
                f"ECS_X_MAX = {video_profile['width_bytes'] - 1}",
                f"ECS_Y_MAX = {video_profile['height_lines'] - 1}",
                "",
            )
        )
    for symbol, field_offset, _, _ in offsets:
        lines.append(f"ECS_E_{symbol} = {field_offset}")
    lines.append(f"ECS_ENTITY_SIZE = {offset}")
    include = "\n".join(lines) + "\n"
    preview = {
        "abi": {"major": major, "minor": minor},
        "x_format": x_format,
        "y_format": y_format,
        "components": component_preview,
        "inserted_dependencies": inserted,
        "fields": [
            {"symbol": f"ECS_E_{symbol}", "offset": field_offset, "size": size, "type": type_name}
            for symbol, field_offset, size, type_name in offsets
        ],
        "entity_size": offset,
        "valid_mask": valid_mask,
    }
    return GeneratedProfile(include, preview)


def _read_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return _object(data, str(path))


def _constants(source: str) -> dict[str, int]:
    result: dict[str, int] = {}
    for name, value in re.findall(
        r"(?m)^([A-Z][A-Z0-9_]*)\s*=\s*(0x[0-9A-Fa-f]+|[0-9]+)$", source
    ):
        result[name] = int(value, 0)
    return result


def layout_changes(previous: str | None, current: str) -> dict:
    before = _constants(previous or "")
    after = _constants(current)
    added = {name: after[name] for name in sorted(after.keys() - before.keys())}
    removed = {name: before[name] for name in sorted(before.keys() - after.keys())}
    changed = {
        name: {"from": before[name], "to": after[name]}
        for name in sorted(before.keys() & after.keys())
        if before[name] != after[name]
    }
    return {
        "layout_changed": bool(added or removed or changed),
        "added": added,
        "removed": removed,
        "changed": changed,
    }


def video_profile_for_manifest(manifest: dict) -> dict | None:
    name = manifest.get("profile")
    if not isinstance(name, str):
        return None
    path = ROOT / "framework" / "profiles" / name
    return _read_json(path) if path.is_file() else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--portfolio", type=Path, default=DEFAULT_PORTFOLIO)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.output is None and not args.preview:
        parser.error("--output is required unless --preview is used")
    if args.preview and args.check:
        parser.error("--preview and --check are mutually exclusive")
    manifest = _read_json(args.manifest)
    generated = generate(
        manifest,
        _read_json(args.portfolio),
        video_profile_for_manifest(manifest),
    )
    if args.preview:
        previous = None
        if args.output is not None and args.output.is_file():
            previous = args.output.read_text(encoding="ascii")
        preview = dict(generated.preview)
        preview["changes"] = layout_changes(previous, generated.include)
        print(json.dumps(preview, indent=2))
    if args.output is not None and not args.preview:
        if args.check:
            if not args.output.is_file() or args.output.read_text(encoding="ascii") != generated.include:
                raise SystemExit(f"stale ECS profile: regenerate {args.output}")
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(generated.include, encoding="ascii")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
