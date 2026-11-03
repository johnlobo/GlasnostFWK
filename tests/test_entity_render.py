import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class EntityRenderTests(unittest.TestCase):
    @staticmethod
    def _routine(source: str, start: str, end: str) -> str:
        return source.split(start, 1)[1].split(end, 1)[0]

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

    def test_platformer_contact_door_and_hud_regressions(self):
        source = (ROOT / "examples/platformer/main.s").read_text()

        reset = self._routine(source, "_pf_reset_render_flags:", ";; One life")
        self.assertIn(
            "ld hl, #platformer_door_entity+FWK_ENTITY_RENDER_FLAGS\n"
            "    ld (hl), #0",
            reset,
        )

        contacts = self._routine(
            source, "_pf_check_enemy_contacts:", "_pf_lose_life:"
        )
        self.assertIn("jr nc, _pf_enemy_v2_check", contacts)
        self.assertIn("_pf_enemy_v2_check:", contacts)
        self.assertIn("set 2, (hl)", contacts)

        score = self._routine(source, "_pf_update_hud_score:", "_pf_draw_win_status:")
        self.assertIn("ld c, #0", score)
        self.assertIn("cp #5", score)
        self.assertEqual(score.count("ld c, #3"), 2)

        status = self._routine(source, "_pf_draw_win_status:", "_pf_update_hud_lives:")
        self.assertIn("ld a, #6", status)
        self.assertIn("cp #15", status)

        lives = self._routine(source, "_pf_update_hud_lives:", ";; Routine: _pf_restore_hud_cell")
        self.assertEqual(lives.count("ld c, #19"), 2)

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
