#!/usr/bin/env python3
"""Convert editable example assets into SDCC assembly.

An example opts in by shipping ``assets/assets.json``. The file lists PNG
tilesets and Tiled tilemaps; this script turns them into
``assets/generated/assets.s`` and ``assets/generated/assets.inc``.

The conversion is incremental: ``assets/generated/pipeline.json`` stores a
content hash of the configuration, palette and sources plus the hash of every
generated file. A normal ``make`` only runs ``img2cpc``, the TMX reader or the
ZX7B compressor when something actually changed.

Usage:
    python3 tools/build/import_assets.py platformer
    python3 tools/build/import_assets.py platformer --check
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ElementTree
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
try:
    from tools.build.program_catalog import program_folder
except ModuleNotFoundError:
    from program_catalog import program_folder
PIPELINE_VERSION = 1
CONFIG_NAME = "assets.json"
PALETTE_NAME = "palette.json"
GENERATED_DIR = "generated"
SOURCE_FILE = "assets.s"
INCLUDE_FILE = "assets.inc"
STATE_FILE = "pipeline.json"
SYMBOL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
VALID_COMPRESSION = {"none", "zx7b"}
FIRMWARE_TO_HARDWARE = [
    0x14, 0x04, 0x15, 0x1C, 0x18, 0x1D, 0x0C, 0x05, 0x0D,
    0x16, 0x06, 0x17, 0x1E, 0x00, 0x1F, 0x0E, 0x07, 0x0F,
    0x12, 0x02, 0x13, 0x1A, 0x19, 0x1B, 0x0A, 0x03, 0x0B,
]


def _firmware_palette_hardware(values: list[int]) -> bytes:
    return bytes(FIRMWARE_TO_HARDWARE[value] for value in values)


class AssetError(ValueError):
    """Raised when an asset source or conversion is invalid."""


def _relative_asset(assets_dir: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not relative:
        raise AssetError("asset paths must be non-empty strings")
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise AssetError(f"unsafe asset path: {relative}")
    resolved = (assets_dir / path).resolve()
    try:
        resolved.relative_to(assets_dir.resolve())
    except ValueError as error:
        raise AssetError(f"unsafe asset path: {relative}") from error
    if not resolved.is_file():
        raise AssetError(f"missing asset source: {relative}")
    return resolved


def _symbol(value: object, label: str) -> str:
    if not isinstance(value, str) or not SYMBOL.fullmatch(value):
        raise AssetError(f"invalid {label}: {value!r}")
    return value


def load_config(assets_dir: Path) -> dict:
    path = assets_dir / CONFIG_NAME
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise AssetError(f"missing asset pipeline configuration: {path}") from error
    except json.JSONDecodeError as error:
        raise AssetError(f"invalid JSON in {path}: {error}") from error
    if not isinstance(config, dict):
        raise AssetError(f"{path} must contain a JSON object")
    if config.get("version") != PIPELINE_VERSION:
        raise AssetError(
            f"{path}: unsupported version {config.get('version')!r}; "
            f"expected {PIPELINE_VERSION}"
        )

    images = config.get("images", [])
    tilemaps = config.get("tilemaps", [])
    if not isinstance(images, list) or not isinstance(tilemaps, list):
        raise AssetError(f"{path}: images and tilemaps must be lists")
    if not images and not tilemaps:
        raise AssetError(f"{path}: declare at least one image or tilemap")

    palette = config.get("palette")
    if images:
        if not isinstance(palette, str) or not palette:
            raise AssetError(f"{path}: images require a palette file")
        palette_path = _relative_asset(assets_dir, palette)
        try:
            palette_data = json.loads(palette_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise AssetError(f"invalid JSON in {palette_path}: {error}") from error
        if not isinstance(palette_data, dict) or palette_data.get("type") != "firmware":
            raise AssetError(f"{palette_path}: palette must use firmware color codes")
        palette_values = palette_data.get("values")
        if (
            not isinstance(palette_values, list)
            or len(palette_values) != 16
            or any(
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 0
                or value > 26
                for value in palette_values
            )
        ):
            raise AssetError(f"{palette_path}: palette must contain 16 firmware colors (0-26)")
    elif palette is not None:
        raise AssetError(f"{path}: palette is only used by images")

    if images and "palette_symbol" not in config:
        config["palette_symbol"] = f"{assets_dir.parent.name}_palette"

    seen: set[str] = set()

    def unique(name: str, label: str) -> str:
        key = name.upper()
        if key in seen:
            raise AssetError(f"duplicate generated symbol: {name}")
        seen.add(key)
        return name

    if images and config.get("palette_symbol") is not None:
        unique(_symbol(config["palette_symbol"], "palette_symbol"), "palette symbol")

    for index, image in enumerate(images):
        if not isinstance(image, dict):
            raise AssetError(f"{path}: images[{index}] must be an object")
        _relative_asset(assets_dir, image.get("source"))
        for field in ("width", "height"):
            value = image.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise AssetError(f"{path}: images[{index}].{field} must be a positive integer")
        if image["width"] % 2:
            raise AssetError(f"{path}: images[{index}].width must be even in Mode 0")
        if image.get("symbol") is not None:
            unique(_symbol(image["symbol"], f"images[{index}].symbol"), "symbol")
        tiles = image.get("tiles")
        if not isinstance(tiles, list) or not tiles:
            raise AssetError(f"{path}: images[{index}].tiles must be a non-empty list")
        for tile_index, name in enumerate(tiles):
            unique(_symbol(name, f"images[{index}].tiles[{tile_index}]"), "tile")

    for index, tilemap in enumerate(tilemaps):
        if not isinstance(tilemap, dict):
            raise AssetError(f"{path}: tilemaps[{index}] must be an object")
        _relative_asset(assets_dir, tilemap.get("source"))
        _symbol(tilemap.get("symbol"), f"tilemaps[{index}].symbol")
        unique(tilemap["symbol"], "tilemap")
        if not isinstance(tilemap.get("layer"), str) or not tilemap["layer"]:
            raise AssetError(f"{path}: tilemaps[{index}].layer must be a non-empty string")
        compression = tilemap.get("compression", "none")
        if compression not in VALID_COMPRESSION:
            raise AssetError(
                f"{path}: tilemaps[{index}].compression must be one of "
                f"{sorted(VALID_COMPRESSION)}"
            )
    return config


def _sources(assets_dir: Path, config: dict) -> dict[str, Path]:
    sources: dict[str, Path] = {}
    if config.get("palette"):
        sources[config["palette"]] = _relative_asset(assets_dir, config["palette"])
    for image in config.get("images", []):
        sources[image["source"]] = _relative_asset(assets_dir, image["source"])
    for tilemap in config.get("tilemaps", []):
        sources[tilemap["source"]] = _relative_asset(assets_dir, tilemap["source"])
    return sources


def pipeline_hash(assets_dir: Path, config: dict, config_bytes: bytes) -> str:
    digest = hashlib.sha256()
    digest.update(f"glasnost-assets-v{PIPELINE_VERSION}\0".encode("ascii"))
    digest.update(config_bytes)
    for name, path in sorted(_sources(assets_dir, config).items()):
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def generated_paths(assets_dir: Path) -> list[Path]:
    directory = assets_dir / GENERATED_DIR
    return [directory / SOURCE_FILE, directory / INCLUDE_FILE]


def _read_state(assets_dir: Path) -> dict | None:
    path = assets_dir / GENERATED_DIR / STATE_FILE
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return state if isinstance(state, dict) else None


def check(assets_dir: Path) -> bool:
    """Return true when every generated file matches the current sources."""
    config_path = assets_dir / CONFIG_NAME
    if not config_path.is_file():
        return False
    try:
        config = load_config(assets_dir)
        expected = pipeline_hash(assets_dir, config, config_path.read_bytes())
    except AssetError:
        return False
    state = _read_state(assets_dir)
    if not state or state.get("version") != PIPELINE_VERSION or state.get("hash") != expected:
        return False
    outputs = state.get("outputs")
    if not isinstance(outputs, dict):
        return False
    for path in generated_paths(assets_dir):
        relative = str(path.relative_to(assets_dir))
        if outputs.get(relative) != hashlib.sha256(path.read_bytes()).hexdigest():
            return False
    return True


def _tool(cpct_path: Path | None, name: str, env: str) -> Path:
    override = os.environ.get(env)
    if override:
        candidate = Path(override).expanduser()
        if candidate.is_file():
            return candidate
        raise AssetError(f"{env} does not point to an executable file: {candidate}")

    roots: list[Path] = []
    # Prefer the framework's own bundled tools (e.g. img2cpc without FreeImage).
    roots.append(Path(__file__).resolve().parents[2])
    if cpct_path is not None:
        roots.append(cpct_path)
    for variable in ("CPCT_NEXT_PATH", "CPCT_PATH"):
        value = os.environ.get(variable)
        if value:
            roots.append(Path(value))
    for root in roots:
        for candidate in (root / "tools" / name / "bin" / name, root / "tools" / name / name):
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return candidate
    searched = ", ".join(str(root) for root in roots) or "no CPCTelera path"
    raise AssetError(
        f"missing {name} (searched {searched}). Set CPCT_NEXT_PATH or {env}, "
        f"then build the tool with: make -C <cpct>/tools/{name}"
    )


def _run(command: list[str], label: str, cwd: Path | None = None) -> None:
    result = subprocess.run(command, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise AssetError(f"{label} failed ({result.returncode}): {detail}")


def read_tmx_layer(path: Path, layer_name: str) -> tuple[int, int, list[int]]:
    """Return width, height and CPCTelera-style reindexed CSV tile ids.

    CPCTelera's ``cpct_tmx2csv`` keeps empty cells as 0 and subtracts one from
    every positive Tiled gid. This reader mirrors that rule for CSV layers.
    """
    try:
        root = ElementTree.parse(path).getroot()
    except ElementTree.ParseError as error:
        raise AssetError(f"invalid TMX file {path}: {error}") from error
    if root.tag != "map":
        raise AssetError(f"{path}: root element is not <map>")
    map_width = int(root.get("width", "0"))
    map_height = int(root.get("height", "0"))
    if map_width <= 0 or map_height <= 0:
        raise AssetError(f"{path}: map width and height must be positive")

    layer = next((item for item in root.findall("layer") if item.get("name") == layer_name), None)
    if layer is None:
        available = ", ".join(item.get("name", "?") for item in root.findall("layer"))
        raise AssetError(f"{path}: layer {layer_name!r} not found (layers: {available})")
    width = int(layer.get("width", map_width))
    height = int(layer.get("height", map_height))
    if width != map_width or height != map_height:
        raise AssetError(f"{path}: layer {layer_name!r} size differs from the map")

    data = layer.find("data")
    if data is None:
        raise AssetError(f"{path}: layer {layer_name!r} has no <data>")
    encoding = data.get("encoding", "")
    if encoding != "csv":
        raise AssetError(
            f"{path}: layer {layer_name!r} uses {encoding or 'XML'} encoding; "
            "export it as CSV in Tiled"
        )
    tokens = [token.strip() for token in (data.text or "").replace("\n", ",").split(",")]
    try:
        values = [int(token) for token in tokens if token]
    except ValueError as error:
        raise AssetError(f"{path}: layer {layer_name!r} has non-numeric ids") from error
    if len(values) != width * height:
        raise AssetError(
            f"{path}: layer {layer_name!r} has {len(values)} cells, "
            f"expected {width * height}"
        )

    reindexed: list[int] = []
    for value in values:
        if value < 0 or value > 0xFFFFFFFF:
            raise AssetError(f"{path}: invalid tile id {value} in layer {layer_name!r}")
        if value & 0xE0000000:
            raise AssetError(
                f"{path}: flipped or rotated tiles are not supported "
                f"(layer {layer_name!r})"
            )
        tile = 0 if value == 0 else value - 1
        if tile > 0xFF:
            raise AssetError(
                f"{path}: tile id {tile} does not fit in a byte "
                f"(layer {layer_name!r})"
            )
        reindexed.append(tile)
    return width, height, reindexed


def _convert_image(
    assets_dir: Path,
    image: dict,
    index: int,
    work: Path,
    img2cpc: Path,
    palette: Path,
) -> list[tuple[str, bytes]]:
    source = _relative_asset(assets_dir, image["source"])
    width = image["width"]
    height = image["height"]
    base = work / f"image{index}"
    _run(
        [
            str(img2cpc),
            "-w", str(width),
            "-h", str(height),
            "-m", "0",
            "-of", "bin",
            "-nt",
            "-nm",
            "-p", str(palette),
            "-o", str(base),
            str(source),
        ],
        f"img2cpc on {image['source']}",
        cwd=work,
    )
    binary = base.with_suffix(".bin")
    if not binary.is_file():
        raise AssetError(f"img2cpc did not create {binary}")
    data = binary.read_bytes()
    tile_size = (width // 2) * height
    expected = tile_size * len(image["tiles"])
    if len(data) != expected:
        raise AssetError(
            f"{image['source']}: img2cpc returned {len(data)} bytes, "
            f"expected {expected} ({len(image['tiles'])} tiles of "
            f"{width}x{height} pixels)"
        )
    return [
        (name, data[position * tile_size:(position + 1) * tile_size])
        for position, name in enumerate(image["tiles"])
    ]


def _db_lines(data: bytes) -> list[str]:
    return [
        "    .db " + ", ".join(f"0x{byte:02X}" for byte in data[offset:offset + 16])
        for offset in range(0, len(data), 16)
    ]


def _compress(data: bytes, work: Path, zx7b: Path, name: str) -> bytes:
    source = work / f"{name}.bin"
    target = work / f"{name}.zx7"
    source.write_bytes(data)
    _run([str(zx7b), str(source), str(target)], f"zx7b on {name}")
    if not target.is_file():
        raise AssetError(f"zx7b did not create {target}")
    return target.read_bytes()


def _render(
    config: dict,
    example: str,
    images,
    tilemaps,
    palette_values: list[int] | None = None,
    palette_symbol: str | None = None,
) -> tuple[str, str]:
    lines = [
        ";; Generated by tools/build/import_assets.py from assets/assets.json.",
        ";; Do not edit: change the PNG/TMX sources and run `make assets`.",
        f".module {example}_generated_assets",
        "",
    ]
    buffers = [item for item in tilemaps if item["compression"] == "zx7b"]
    if buffers:
        lines.append(".area _DATA")
        for item in buffers:
            lines.append(f"{item['symbol']}::")
            lines.append(f"    .ds {item['width'] * item['height']}    ;; decompression buffer")
        lines.append("")
    lines.append(".area _CODE")
    if palette_values is not None and palette_symbol is not None:
        lines.append("")
        lines.append(f";; {palette_symbol} (16 hardware colour values from firmware palette)")
        lines.append(f"{palette_symbol}::")
        lines.extend(_db_lines(_firmware_palette_hardware(palette_values)))
        lines.append("")

    for image, tiles in images:
        lines.append("")
        if image.get("symbol"):
            lines.append(f"{image['symbol']}::")
        for name, data in tiles:
            lines.append(
                f";; {name} ({image['width']}x{image['height']} pixels, "
                f"{image['width'] // 2}x{image['height']} bytes)"
            )
            if name != image.get("symbol"):
                lines.append(f"{name}::")
            lines.extend(_db_lines(data))

    for item in tilemaps:
        lines.append("")
        total = item["width"] * item["height"]
        if item["compression"] == "zx7b":
            lines.append(
                f";; {item['symbol']} layer {item['layer']!r} "
                f"({item['width']}x{item['height']} cells, "
                f"zx7b {total} -> {len(item['data'])} bytes)"
            )
            lines.append(f"{item['symbol']}_packed::")
        else:
            lines.append(
                f";; {item['symbol']} layer {item['layer']!r} "
                f"({item['width']}x{item['height']} cells)"
            )
            lines.append(f"{item['symbol']}::")
        lines.extend(_db_lines(item["data"]))
    lines.append("")

    include = [
        ";; Generated by tools/build/import_assets.py from assets/assets.json.",
        ";; Do not edit: change the PNG/TMX sources and run `make assets`.",
    ]
    for item in tilemaps:
        prefix = item["symbol"].upper()
        include.extend(
            [
                f"{prefix}_WIDTH = {item['width']}",
                f"{prefix}_HEIGHT = {item['height']}",
                f"{prefix}_SIZE = {item['width'] * item['height']}",
            ]
        )
        if item["compression"] == "zx7b":
            include.append(f"{prefix}_PACKED_SIZE = {len(item['data'])}")
    if palette_symbol is not None and palette_values is not None:
        include.append(f"{palette_symbol.upper()}_SIZE = {len(palette_values)}")
    include.append("")
    return "\n".join(lines), "\n".join(include)


def _write(path: Path, text: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


def convert(assets_dir: Path, cpct_path: Path | None = None) -> list[Path]:
    """Convert every declared asset and refresh the pipeline state."""
    config_path = assets_dir / CONFIG_NAME
    config = load_config(assets_dir)
    config_bytes = config_path.read_bytes()
    sources = _sources(assets_dir, config)
    palette = sources[config["palette"]] if config.get("palette") else None
    palette_values = None
    palette_symbol = config.get("palette_symbol")
    if palette is not None:
        palette_data = json.loads(palette.read_text(encoding="utf-8"))
        palette_values = list(palette_data["values"])
        if not palette_symbol:
            palette_symbol = f"{assets_dir.parent.name}_palette"

    img2cpc = None
    if config.get("images"):
        img2cpc = _tool(cpct_path, "img2cpc", "IMG2CPC")
    need_zx7b = any(item.get("compression", "none") == "zx7b" for item in config.get("tilemaps", []))
    zx7b = _tool(cpct_path, "zx7b", "ZX7B") if need_zx7b else None

    generated = assets_dir / GENERATED_DIR
    generated.mkdir(parents=True, exist_ok=True)
    example = assets_dir.parent.name
    with tempfile.TemporaryDirectory(prefix=".assets-", dir=generated) as temporary:
        work = Path(temporary)
        images = []
        for index, image in enumerate(config.get("images", [])):
            images.append(
                (image, _convert_image(assets_dir, image, index, work, img2cpc, palette))
            )

        tilemaps = []
        for index, tilemap in enumerate(config.get("tilemaps", [])):
            width, height, values = read_tmx_layer(
                sources[tilemap["source"]], tilemap["layer"]
            )
            raw = bytes(values)
            compression = tilemap.get("compression", "none")
            data = _compress(raw, work, zx7b, f"map{index}") if compression == "zx7b" else raw
            tilemaps.append(
                {
                    "symbol": tilemap["symbol"],
                    "layer": tilemap["layer"],
                    "compression": compression,
                    "width": width,
                    "height": height,
                    "data": data,
                }
            )

        source_text, include_text = _render(
            config, example, images, tilemaps, palette_values, palette_symbol
        )
        outputs = generated_paths(assets_dir)
        _write(outputs[0], source_text)
        _write(outputs[1], include_text)

    state = {
        "version": PIPELINE_VERSION,
        "hash": pipeline_hash(assets_dir, load_config(assets_dir), config_bytes),
        "sources": {
            name: hashlib.sha256(path.read_bytes()).hexdigest()
            for name, path in sorted(sources.items())
        },
        "outputs": {
            str(path.relative_to(assets_dir)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in generated_paths(assets_dir)
        },
    }
    _write(generated / STATE_FILE, json.dumps(state, indent=2, sort_keys=True) + "\n")
    return generated_paths(assets_dir)


def ensure(example: Path, cpct_path: Path | None = None, *, force: bool = False) -> bool:
    """Convert an example's assets when needed. Returns true when it ran."""
    assets_dir = example / "assets"
    if not (assets_dir / CONFIG_NAME).is_file():
        return False
    if not force and check(assets_dir):
        print(f"[assets] {example.name}: up to date", flush=True)
        return False
    print(f"[assets] {example.name}: converting sources", flush=True)
    convert(assets_dir, cpct_path)
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("examples", nargs="+", help="example or internal validation names")
    parser.add_argument("--cpct-path", type=Path, help="CPCTelera/CPCTelera Next root")
    parser.add_argument("--force", action="store_true", help="convert even when up to date")
    parser.add_argument(
        "--check",
        action="store_true",
        help="only verify that generated files match their sources",
    )
    args = parser.parse_args(argv)

    status = 0
    for name in args.examples:
        example = program_folder(ROOT, name)
        assets_dir = example / "assets"
        if not (assets_dir / CONFIG_NAME).is_file():
            if args.check:
                print(f"[assets] {name}: no pipeline")
            continue
        if args.check:
            fresh = check(assets_dir)
            print(f"[assets] {name}: {'up to date' if fresh else 'stale'}")
            status |= 0 if fresh else 1
            continue
        ensure(example, args.cpct_path, force=args.force)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
