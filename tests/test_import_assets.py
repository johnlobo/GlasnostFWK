import re
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ElementTree
from pathlib import Path

from tools import import_assets

ROOT = Path(__file__).resolve().parents[1]
PLATFORMER = ROOT / "examples" / "platformer"


def _db_block(text: str, label: str) -> bytes:
    match = re.search(rf"^{label}::?\s*$", text, re.MULTILINE)
    if match is None:
        raise AssertionError(f"missing label {label}")
    values: list[int] = []
    for line in text[match.end():].splitlines():
        line = line.strip()
        if not line or line.startswith(";;"):
            continue
        if line.startswith(".db"):
            values.extend(int(token, 0) for token in line[3:].split(","))
            continue
        break
    return bytes(values)


def _dzx7b(blob: bytes) -> bytes:
    """Decode the backwards ZX7 stream written by CPCTelera's zx7b tool."""
    stream = blob[::-1]
    position = 0
    mask = 0
    byte = 0
    output = bytearray()

    def read_bit() -> int:
        nonlocal position, mask, byte
        mask >>= 1
        if mask == 0:
            mask = 0x80
            byte = stream[position]
            position += 1
        return 1 if byte & mask else 0

    output.append(stream[position])
    position += 1
    while True:
        if read_bit() == 0:
            output.append(stream[position])
            position += 1
            continue
        value = 1
        while read_bit() == 0:
            value = (value << 1) | read_bit()
        if value & 0xFF == 0xFF:
            break
        length = value + 1
        code = stream[position]
        position += 1
        if code < 128:
            offset = code
        else:
            extra = 0
            for _ in range(4):
                extra = (extra << 1) | read_bit()
            offset = (code & 0x7F | extra << 7) + 128
        offset += 1
        for _ in range(length):
            output.append(output[-offset])
    return bytes(output[::-1])


def _tmx_layer(path: Path, name: str) -> bytes:
    root = ElementTree.parse(path).getroot()
    layer = next(item for item in root.findall("layer") if item.get("name") == name)
    data = layer.find("data").text.replace("\n", ",").split(",")
    return bytes(0 if int(token) == 0 else int(token) - 1 for token in data if token.strip())


class TmxTests(unittest.TestCase):
    def _write_tmx(self, directory: Path, encoding: str = "csv") -> Path:
        path = directory / "level.tmx"
        path.write_text(
            f"""<?xml version="1.0" encoding="UTF-8"?>
<map version="1.10" orientation="orthogonal" width="3" height="2" tilewidth="8" tileheight="8">
 <layer id="1" name="level" width="3" height="2">
  <data encoding="{encoding}">
0,1,5,
2,0,3
</data>
 </layer>
</map>
""",
            encoding="utf-8",
        )
        return path

    def test_reindexes_positive_gids_and_keeps_empty_cells(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._write_tmx(Path(directory))
            width, height, values = import_assets.read_tmx_layer(path, "level")
            self.assertEqual((width, height), (3, 2))
            self.assertEqual(values, [0, 0, 4, 1, 0, 2])

    def test_rejects_non_csv_layers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._write_tmx(Path(directory), encoding="base64")
            with self.assertRaisesRegex(import_assets.AssetError, "export it as CSV"):
                import_assets.read_tmx_layer(path, "level")

    def test_rejects_missing_layer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._write_tmx(Path(directory))
            with self.assertRaisesRegex(import_assets.AssetError, "not found"):
                import_assets.read_tmx_layer(path, "other")


class ConfigTests(unittest.TestCase):
    def _assets(self, directory: Path) -> Path:
        assets = directory / "example" / "assets"
        (assets / "src").mkdir(parents=True)
        (assets / "palette.json").write_text('{"type":"firmware","values":[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15]}', encoding="utf-8")
        (assets / "src" / "tiles.png").write_bytes(b"png")
        config = {
            "version": 1,
            "palette": "palette.json",
            "images": [
                {
                    "source": "src/tiles.png",
                    "width": 8,
                    "height": 8,
                    "symbol": "tiles",
                    "tiles": ["tile_a"],
                }
            ],
            "tilemaps": [],
        }
        import json

        (assets / "assets.json").write_text(json.dumps(config), encoding="utf-8")
        return assets

    def test_detects_stale_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            assets = self._assets(Path(directory))
            self.assertFalse(import_assets.check(assets))
            generated = assets / "generated"
            generated.mkdir()
            (generated / "assets.s").write_text("data", encoding="utf-8")
            (generated / "assets.inc").write_text("size = 1\n", encoding="utf-8")
            config = import_assets.load_config(assets)
            import hashlib
            import json

            state = {
                "version": import_assets.PIPELINE_VERSION,
                "hash": import_assets.pipeline_hash(
                    assets, config, (assets / "assets.json").read_bytes()
                ),
                "outputs": {
                    "generated/assets.s": hashlib.sha256(b"data").hexdigest(),
                    "generated/assets.inc": hashlib.sha256(b"size = 1\n").hexdigest(),
                },
            }
            (generated / "pipeline.json").write_text(json.dumps(state), encoding="utf-8")
            self.assertTrue(import_assets.check(assets))
            (assets / "src" / "tiles.png").write_bytes(b"changed")
            self.assertFalse(import_assets.check(assets))

    def test_rejects_paths_outside_the_assets_folder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            assets = self._assets(Path(directory))
            text = (assets / "assets.json").read_text(encoding="utf-8")
            (assets / "assets.json").write_text(
                text.replace('"src/tiles.png"', '"../tiles.png"'), encoding="utf-8"
            )
            with self.assertRaisesRegex(import_assets.AssetError, "unsafe asset path"):
                import_assets.load_config(assets)

    def test_rejects_duplicate_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            assets = self._assets(Path(directory))
            text = (assets / "assets.json").read_text(encoding="utf-8")
            (assets / "assets.json").write_text(
                text.replace('"tile_a"', '"tiles"'), encoding="utf-8"
            )
            with self.assertRaisesRegex(import_assets.AssetError, "duplicate generated symbol"):
                import_assets.load_config(assets)

    def test_example_without_configuration_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            example = Path(directory) / "plain"
            example.mkdir()
            self.assertFalse(import_assets.ensure(example))


class PlatformerAssetsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assets = PLATFORMER / "assets"
        self.generated = self.assets / "generated"
        self.source = (self.generated / "assets.s").read_text(encoding="utf-8")
        self.include = (self.generated / "assets.inc").read_text(encoding="utf-8")

    def test_pipeline_is_current(self) -> None:
        self.assertTrue(import_assets.check(self.assets))

    def test_generated_symbols_and_sizes_are_complete(self) -> None:
        for symbol in (
            "platformer_tileset",
            "platformer_tile_empty",
            "platformer_tile_solid",
            "platformer_player_pixels",
            "platformer_player_pixels2",
            "platformer_coin_pixels",
            "platformer_enemy_pixels",
            "platformer_enemy_pixels2",
            "platformer_door_pixels",
            "platformer_map_packed",
            "platformer_map2_packed",
            "platformer_palette",
        ):
            self.assertIn(f"{symbol}::", self.source)
        self.assertIn("PLATFORMER_MAP_SIZE = 500", self.include)
        self.assertIn("PLATFORMER_MAP2_SIZE = 500", self.include)
        self.assertIn("PLATFORMER_PALETTE_SIZE = 16", self.include)

    def test_image_data_matches_the_declared_tile_size(self) -> None:
        tiles = sum(
            len(_db_block(self.source, symbol))
            for symbol in (
                "platformer_tile_empty",
                "platformer_tile_solid",
                "platformer_tile_one_way",
                "platformer_tile_star",
            )
        )
        self.assertEqual(tiles, 4 * 32)
        self.assertEqual(len(_db_block(self.source, "platformer_player_pixels")), 64)
        self.assertEqual(len(_db_block(self.source, "platformer_player_pixels2")), 64)
        for symbol in (
            "platformer_coin_pixels",
            "platformer_enemy_pixels",
            "platformer_enemy_pixels2",
            "platformer_door_pixels",
        ):
            self.assertEqual(len(_db_block(self.source, symbol)), 32)

    def test_compressed_levels_unpack_to_the_tmx_layers(self) -> None:
        tmx = self.assets / "src" / "level.tmx"
        for layer, symbol in (("level", "platformer_map"), ("level2", "platformer_map2")):
            packed = _db_block(self.source, f"{symbol}_packed")
            self.assertEqual(_dzx7b(packed), _tmx_layer(tmx, layer))

    def test_generated_files_are_reproducible_without_tools(self) -> None:
        # A stale hash must be detected without invoking img2cpc or zx7b.
        with tempfile.TemporaryDirectory() as directory:
            copy = Path(directory) / "platformer"
            shutil.copytree(PLATFORMER, copy)
            self.assertTrue(import_assets.check(copy / "assets"))
            (copy / "assets" / "src" / "level.tmx").write_text(
                (copy / "assets" / "src" / "level.tmx").read_text(encoding="utf-8")
                + "\n",
                encoding="utf-8",
            )
            self.assertFalse(import_assets.check(copy / "assets"))


if __name__ == "__main__":
    unittest.main()
