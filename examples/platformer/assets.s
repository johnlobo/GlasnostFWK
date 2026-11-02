.module example_platformer_assets
;; Static data for the platformer: tile behaviours, map descriptors, configuration,
;; input bindings, coin table and behaviour programs. Graphics and maps are
;; generated into assets/generated/ from the editable PNG and TMX sources.
.include "cpctelera.h.s"
.include "video/entity_render.inc"
.include "game/game.inc"
.include "extensions/behavior.inc"
.include "assets/generated/assets.inc"

.area _DATA

.globl platformer_tileset
.globl platformer_map, platformer_map2
.globl platformer_palette
.globl platformer_coin0_entity, platformer_coin1_entity
.globl platformer_coin2_entity, platformer_coin3_entity
.globl fwk_behavior_action_idle, fwk_behavior_action_wait, fwk_behavior_action_set_timer
.globl fwk_behavior_action_set_vx, fwk_behavior_action_set_vy, fwk_behavior_action_drive_vx
.globl fwk_behavior_cond_true, fwk_behavior_cond_timeout

;; Tile behaviours: empty, solid, one-way platform and decorative/non-solid.
platformer_types:
    .db 0, 1, 2, 0

;; 20x25 cells. A CPCTelera 4x8-byte tile maps to 8x8 Mode 0 pixels, therefore
;; the viewport covers the standard 160x200 screen exactly. The level itself is
;; converted from assets/src/level.tmx into generated/assets.s.
platformer_map_descriptor::
    .dw platformer_map, platformer_types
    .db PLATFORMER_MAP_WIDTH, PLATFORMER_MAP_HEIGHT, 2, 3, 4, 8, 4

platformer_view::
    .dw platformer_tileset
    .db 0, 0, 0
    .dw 0
    .db PLATFORMER_MAP_WIDTH, PLATFORMER_MAP_HEIGHT, 4

platformer_config::
    ;; Tile collision owns the visible floor; 255 is only a safety bound.
    .db 80, 255, 1, 8

platformer_bindings::
    .dw Key_CursorLeft
    .db PF_INPUT_LEFT
    .dw Key_CursorRight
    .db PF_INPUT_RIGHT
    .dw Key_CursorUp
    .db PF_INPUT_JUMP
    .dw 0
    .db 0

;; x tile, y tile, kind, render entity. Kind is reserved for variants.
platformer_coins::
    .db 4,3,1
    .dw platformer_coin0_entity
    .db 14,3,1
    .dw platformer_coin1_entity
    .db 4,21,1
    .dw platformer_coin2_entity
    .db 14,21,1
    .dw platformer_coin3_entity

;; Second screen descriptor. Both the tileset and the animated sprites live in
;; assets/generated/, converted from assets/src/*.png and level.tmx.
platformer_map2_descriptor::
    .dw platformer_map2, platformer_types
    .db PLATFORMER_MAP2_WIDTH, PLATFORMER_MAP2_HEIGHT, 2, 3, 4, 8, 4

platformer_view2::
    .dw platformer_tileset
    .db 0, 0, 0
    .dw 0
    .db PLATFORMER_MAP2_WIDTH, PLATFORMER_MAP2_HEIGHT, 4

platformer_enemy_h_program::
    FWK_BEHAVIOR_DRIVE_VX 1, 1
    FWK_BEHAVIOR_CONDITIONS_END

platformer_enemy_v_program::
    FWK_BEHAVIOR_SET_VY 2
    FWK_BEHAVIOR_WAIT 30, platformer_enemy_v_turn
platformer_enemy_v_turn::
    FWK_BEHAVIOR_SET_VY -2
    FWK_BEHAVIOR_WAIT 30, platformer_enemy_v_program

platformer_enemy_v2_program::
    FWK_BEHAVIOR_SET_VY 2
    FWK_BEHAVIOR_WAIT 20, platformer_enemy_v2_turn
platformer_enemy_v2_turn::
    FWK_BEHAVIOR_SET_VY -2
    FWK_BEHAVIOR_WAIT 20, platformer_enemy_v2_program
