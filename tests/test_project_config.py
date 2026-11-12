import json
import unittest
from pathlib import Path

from tools.build.build_examples import effective_modules
from tools.build.project_config import (
    BANKED_CODE_START,
    BANK_PROBE,
    BANK_STUB_END,
    DEFAULT_CODE_START,
    ProjectCapabilities,
    generate_include,
    generate_source,
    mode0_mask_table,
    mode1_mask_table,
    parse_capabilities,
)

ROOT = Path(__file__).resolve().parents[1]


class ProjectConfigTests(unittest.TestCase):
    def test_default_project_has_no_transparency_and_starts_at_0200(self) -> None:
        config = parse_capabilities({}, 0)
        self.assertEqual(config, ProjectCapabilities(None, False))
        self.assertEqual(config.code_start, DEFAULT_CODE_START)
        self.assertNotIn("_fwk_transparency_init", generate_source(config))

    def test_extended_memory_starts_immediately_after_bank_scratch(self) -> None:
        config = parse_capabilities({"extended_memory": True}, 0)
        self.assertEqual(config.code_start, BANKED_CODE_START)
        source = generate_source(config)
        self.assertIn("call fwk_bank_init", source)
        self.assertEqual(BANK_STUB_END, 0x0215)
        self.assertEqual(BANKED_CODE_START, 0x0216)
        self.assertEqual(BANK_PROBE, 0x4000)

    def test_bank_probe_is_transient_and_not_an_absolute_area(self) -> None:
        source = (ROOT / "framework/src/resources/bank.s").read_text(encoding="ascii")
        self.assertNotIn("_BANKTEST", source)
        self.assertNotIn(".org 0x7FF0", source)
        self.assertIn("FWK_BANK_PROBE = 0x4000", source)
        self.assertIn("ld (FWK_BANK_NORMAL_SAVE), a", source)
        self.assertIn("ld hl, #FWK_BANK_SAVE", source)

    def test_mode0_pen_zero_matches_cpctelera_reference_prefix(self) -> None:
        table = mode0_mask_table(0)
        self.assertEqual(len(table), 256)
        self.assertEqual(table[:16], bytes.fromhex("ffaa5500aaaa00005500550000000000"))

    def test_every_pen_preserves_only_matching_packed_pixels(self) -> None:
        for pen in range(16):
            table = mode0_mask_table(pen)
            self.assertEqual(sum(mask == 0xFF for mask in table), 1)
            self.assertEqual(sum(mask == 0xAA for mask in table), 15)
            self.assertEqual(sum(mask == 0x55 for mask in table), 15)

    def test_mode1_mask_matches_each_of_four_packed_pixels(self) -> None:
        # CPCtelera's Mode 1 pattern for pens 0,1,2,3 in order is 0x35.
        self.assertEqual([mode1_mask_table(pen)[0x35] for pen in range(4)],
                         [0x88, 0x22, 0x44, 0x11])
        self.assertEqual(mode1_mask_table(1)[0xF0], 0xFF)
        self.assertEqual(mode1_mask_table(2)[0x0F], 0xFF)
        self.assertEqual(mode1_mask_table(3)[0xFF], 0xFF)
        pixel_bits = ((7, 3), (6, 2), (5, 1), (4, 0))
        for pen in range(4):
            table = mode1_mask_table(pen)
            self.assertEqual(len(table), 256)
            for source in range(256):
                expected = 0
                for high, low in pixel_bits:
                    pixel = ((source >> high) & 1) | (((source >> low) & 1) << 1)
                    if pixel == pen:
                        expected |= (1 << high) | (1 << low)
                self.assertEqual(table[source], expected)

    def test_mode1_transparency_range_and_generated_table(self) -> None:
        for pen in range(4):
            capabilities = parse_capabilities({"transparency": {"pen": pen}}, 1)
            self.assertEqual(capabilities.video_mode, 1)
            self.assertIn("FWK_PROJECT_VIDEO_MODE = 1", generate_include(capabilities))
            self.assertIn("call _fwk_transparency_init", generate_source(capabilities))
        for pen in (-1, 4, 15, True):
            with self.assertRaisesRegex(ValueError, "Mode 1 transparency pen"):
                parse_capabilities({"transparency": {"pen": pen}}, 1)

    def test_invalid_transparency_config_is_rejected(self) -> None:
        for value in (True, -1, 16, "0"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_capabilities({"transparency": {"pen": value}}, 0)
        with self.assertRaises(ValueError):
            parse_capabilities({"transparency": {"pen": 0, "address": 0x100}}, 0)

    def test_generated_contract_exposes_no_table_when_disabled(self) -> None:
        disabled = generate_include(ProjectCapabilities(None, False))
        enabled = generate_include(ProjectCapabilities(7, False))
        self.assertIn("FWK_TRANSPARENCY_ENABLED = 0", disabled)
        self.assertNotIn("FWK_TRANSPARENCY_TABLE", disabled)
        self.assertIn("FWK_TRANSPARENCY_TABLE = 0x0100", enabled)
        self.assertIn("FWK_TRANSPARENCY_PEN = 7", enabled)

    def test_capability_modules_are_added_or_rejected(self) -> None:
        transparent = ProjectCapabilities(3, False)
        banked = ProjectCapabilities(None, True)
        self.assertIn("video/transparency.s", effective_modules("demo", [], transparent))
        self.assertIn("resources/bank.s", effective_modules("demo", [], banked))
        with self.assertRaisesRegex(ValueError, "transparency must be configured"):
            effective_modules(
                "demo", ["extensions/tilemap_render_masked.s"], ProjectCapabilities(None, False)
            )
        with self.assertRaisesRegex(ValueError, "requires extended_memory=true"):
            effective_modules(
                "demo", ["resources/bank.s"], ProjectCapabilities(None, False)
            )

    def test_builtin_text_rejects_nonzero_transparent_pen(self) -> None:
        with self.assertRaisesRegex(ValueError, "require transparency pen 0"):
            effective_modules("demo", ["ui/text.s"], ProjectCapabilities(3, False))
        with self.assertRaisesRegex(ValueError, "require transparency pen 0"):
            effective_modules("demo", ["ui/text_mode1.s"], ProjectCapabilities(2, False, 1))

    def test_mode1_example_links_both_tile_renderers(self) -> None:
        manifest = json.loads((ROOT / "examples/mode1/glasnost.manifest.json").read_text())
        modules = effective_modules("mode1", manifest["modules"], ProjectCapabilities(0, False, 1))
        for module in ("extensions/tilemap_render.s", "extensions/tilemap_render_masked.s"):
            self.assertIn(module, modules)

    def test_mode1_rejects_mode0_text_but_accepts_sprites_and_tiles(self) -> None:
        mode1 = ProjectCapabilities(0, False, 1)
        with self.assertRaisesRegex(ValueError, "Mode 1 does not support ui/text.s"):
            effective_modules("demo", ["ui/text.s"], mode1)
        for module in ("extensions/tilemap_render.s", "extensions/tilemap_render_masked.s"):
            with self.subTest(module=module):
                self.assertIn(module, effective_modules("demo", [module], mode1))
        self.assertIn("video/sprite.s", effective_modules("demo", ["video/sprite.s"], mode1))
        modules = effective_modules("demo", ["ui/text_mode1.s"], mode1)
        self.assertIn("ui/text_mode1.s", modules)
        self.assertIn("video/transparency.s", modules)
        with self.assertRaisesRegex(ValueError, "Mode 0 does not support"):
            effective_modules("demo", ["ui/text_mode1.s"], ProjectCapabilities(0, False))


if __name__ == "__main__":
    unittest.main()
