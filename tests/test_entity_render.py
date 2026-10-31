import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class EntityRenderTests(unittest.TestCase):
    def test_replaces_sprite_batch(self):
        self.assertFalse((ROOT / "src/video/sprite_batch.s").exists())
        self.assertFalse((ROOT / "src/video/sprite_batch.inc").exists())
        self.assertTrue((ROOT / "src/video/entity_render.s").is_file())
        self.assertTrue((ROOT / "src/video/entity_render.inc").is_file())

    def test_platformer_uses_the_entity_cycle(self):
        source = (ROOT / "examples/platformer/main.s").read_text()
        manifest = json.loads((ROOT / "examples/platformer/example.json").read_text())
        self.assertIn("video/entity_render.s", manifest["modules"])
        self.assertIn("FWK_ENTITY_RENDER_DESCRIPTOR platformer_render_list", source)
        self.assertIn("call fwk_entity_render_prepare_dirty", source)
        self.assertIn("call fwk_entity_render_restore_dirty", source)
        self.assertIn("call fwk_entity_render_draw_dirty", source)
        self.assertNotIn("call fwk_sprite_capture", source)
        self.assertNotIn("call fwk_sprite_restore", source)

    def test_confirmed_layout_and_flags_are_exported(self):
        include = (ROOT / "src/video/entity_render.inc").read_text()
        expected = {
            "FWK_ENTITY_RENDER_PREFIX_SIZE": "25",
            "FWK_ENTITY_RENDER_WORK_SIZE": "4",
            "FWK_ENTITY_RENDER_DESCRIPTOR_SIZE": "8",
            "FWK_ENTITY_RENDER_VISIBLE": "0x01",
            "FWK_ENTITY_RENDER_DIRTY": "0x02",
            "FWK_ENTITY_RENDER_HAS_BACKGROUND": "0x04",
            "FWK_ENTITY_RENDER_MASKED": "0x08",
            "FWK_ENTITY_RENDER_RECOLOR": "0x10",
        }
        for name, value in expected.items():
            self.assertIn(f"{name}", include)
            self.assertIn(f"= {value}", include)

    def test_renderer_has_two_phase_and_overlap_api(self):
        source = (ROOT / "src/video/entity_render.s").read_text()
        for symbol in (
            "fwk_entity_render_init::",
            "fwk_entity_render_revalidate::",
            "fwk_entity_render_mark_rect_dirty::",
            "fwk_entity_render_prepare_dirty::",
            "fwk_entity_render_restore_dirty::",
            "fwk_entity_render_draw_dirty::",
            "_fwk_er_propagate_dirty:",
            "_fwk_er_rects_overlap:",
            "_fwk_er_validate_active_buffers:",
        ):
            self.assertIn(symbol, source)
        self.assertIn("FWK_ENTITY_RENDER_STATE_PREPARED", (ROOT / "src/video/entity_render.inc").read_text())

    def test_opaque_recolor_is_public(self):
        source = (ROOT / "src/video/sprite.s").read_text()
        include = (ROOT / "src/video/sprite.inc").read_text()
        self.assertIn("fwk_sprite_draw_recolor::", source)
        self.assertIn(".globl fwk_sprite_draw_recolor", include)


if __name__ == "__main__":
    unittest.main()
