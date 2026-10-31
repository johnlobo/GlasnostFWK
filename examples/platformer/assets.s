.module example_platformer_assets
.include "cpctelera.h.s"
.include "video/entity_render.inc"
.include "game/game.inc"
.include "extensions/behavior.inc"

.area _DATA

.globl platformer_coin0_entity, platformer_coin1_entity
.globl platformer_coin2_entity, platformer_coin3_entity
.globl fwk_behavior_action_idle, fwk_behavior_action_wait, fwk_behavior_action_set_timer
.globl fwk_behavior_action_set_vx, fwk_behavior_action_set_vy, fwk_behavior_action_drive_vx
.globl fwk_behavior_cond_true, fwk_behavior_cond_timeout
.globl platformer_coin2_entity, platformer_coin3_entity

;; Tile behaviours: empty, solid, one-way platform and decorative/non-solid.
platformer_types:
    .db 0, 1, 2, 0

;; 20x25 cells. A CPCTelera 4x8-byte tile maps to 8x8 Mode 0 pixels, therefore
;; the viewport covers the standard 160x200 screen exactly.
platformer_map:
    .db 1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1
    .db 1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1
    .db 1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1
    .db 1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1
    .db 1,1,0,0,2,2,2,2,2,2,2,2,2,2,2,2,0,0,1,1
    .db 1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1
    .db 1,1,0,0,3,3,0,0,0,0,0,0,0,0,0,0,0,0,1,1
    .db 1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1
    .db 1,1,0,0,0,0,0,0,2,2,2,2,2,2,0,0,0,0,1,1
    .db 1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1
    .db 1,1,0,0,0,0,3,3,0,0,0,0,0,0,0,0,0,0,1,1
    .db 1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1
    .db 1,1,0,0,0,0,0,0,2,2,2,2,2,2,0,0,0,0,1,1
    .db 1,1,0,0,0,0,0,0,0,0,0,0,0,0,3,3,0,0,1,1
    .db 1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1
    .db 1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1
    .db 1,1,0,0,0,0,0,0,2,2,2,2,2,2,0,0,0,0,1,1
    .db 1,1,0,0,3,3,0,0,0,0,0,0,0,0,0,0,0,0,1,1
    .db 1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1
    .db 1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1
    .db 1,1,0,0,0,0,0,0,2,2,2,2,2,2,0,0,0,0,1,1
    .db 1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1
    .db 1,1,0,0,0,0,0,0,0,0,0,0,0,0,3,3,0,0,1,1
    .db 1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1
    .db 1,1,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,1,1

platformer_map_descriptor::
    .dw platformer_map, platformer_types
    .db 20, 25, 2, 3, 4, 8, 4

platformer_tileset:
platformer_tile_empty:
    .rept 32
        .db 0x00
    .endm

platformer_tile_solid:
    .db 0x55,0x55,0xAA,0xAA
    .db 0x55,0x55,0xAA,0xAA
    .db 0xAA,0xAA,0x55,0x55
    .db 0xAA,0xAA,0x55,0x55
    .db 0x55,0x55,0xAA,0xAA
    .db 0x55,0x55,0xAA,0xAA
    .db 0xAA,0xAA,0x55,0x55
    .db 0xAA,0xAA,0x55,0x55

platformer_tile_one_way:
    .db 0xFF,0xFF,0xFF,0xFF
    .db 0xAA,0xAA,0xAA,0xAA
    .db 0x00,0x11,0x00,0x11
    .db 0x00,0x00,0x11,0x00
    .db 0x00,0x11,0x11,0x00
    .db 0x00,0x11,0x11,0x00
    .db 0x00,0x00,0x00,0x00
    .db 0x00,0x00,0x00,0x00

platformer_tile_star:
    .db 0x00,0x00,0x00,0x00
    .db 0x00,0x30,0x30,0x00
    .db 0x30,0xFC,0xFC,0x30
    .db 0x00,0x30,0x30,0x00
    .db 0x10,0x20,0x10,0x20
    .db 0x00,0x00,0x00,0x00
    .db 0x00,0x00,0x00,0x00
    .db 0x00,0x00,0x00,0x00

platformer_view::
    .dw platformer_tileset
    .db 0, 0, 0
    .dw 0
    .db 20, 25, 4

;; Opaque sprites deliberately contain their own black silhouette. The player
;; still captures/restores the background every frame.
platformer_player_pixels::
    .db 0x00,0x00,0x3C,0x3C,0x3C,0x3C,0x00,0x00
    .db 0x00,0x3C,0xFF,0xFF,0xFF,0xFF,0x3C,0x00
    .db 0x00,0x3C,0xCF,0xFF,0xFF,0xCF,0x3C,0x00
    .db 0x00,0x00,0xFF,0xFF,0xFF,0xFF,0x00,0x00
    .db 0x00,0x3C,0x3C,0xFF,0xFF,0x3C,0x3C,0x00
    .db 0x3C,0x00,0x3C,0xFF,0xFF,0x3C,0x00,0x3C
    .db 0x00,0x00,0x3C,0x00,0x00,0x3C,0x00,0x00
    .db 0x00,0x3C,0x3C,0x00,0x00,0x3C,0x3C,0x00

platformer_coin_pixels::
    .db 0x00,0x55,0x55,0x00
    .db 0x00,0x55,0x55,0x00
    .db 0x55,0x55,0x55,0x55
    .db 0x55,0x55,0x55,0x55
    .db 0x55,0x55,0x55,0x55
    .db 0x00,0x55,0x55,0x00
    .db 0x00,0x55,0x55,0x00
    .db 0x00,0x00,0x00,0x00

;; Shared opaque enemy asset (2 bytes x 6 scanlines). Avoiding a colour-key
;; composition keeps the two moving patrols inside the example's frame budget.
platformer_enemy_pixels::
    .db 0x3C,0x3C,0x3C,0x3C
    .db 0xFF,0xFF,0xFF,0xFF
    .db 0xCF,0xCF,0xCF,0xCF
    .db 0xFF,0xFF,0xFF,0xFF
    .db 0xF0,0xF0,0xF0,0xF0
    .db 0x55,0x55,0x55,0x55
    .db 0xAA,0xAA,0xAA,0xAA
    .db 0x00,0x00,0x00,0x00

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

platformer_player_pixels2::
    .db 0x00,0x3C,0x3C,0x00,0x00,0x3C,0x3C,0x00
    .db 0x00,0xFF,0xFF,0x00,0x00,0xFF,0xFF,0x00
    .db 0x3C,0x55,0x55,0x3C,0x3C,0x55,0x55,0x3C
    .db 0x3C,0xFF,0xFF,0x3C,0x3C,0xFF,0xFF,0x3C
    .db 0x3C,0xFF,0xFF,0x3C,0x3C,0xFF,0xFF,0x3C
    .db 0x00,0xFF,0xFF,0x00,0x00,0xFF,0xFF,0x00
    .db 0x00,0xAA,0xAA,0x00,0x00,0xAA,0xAA,0x00
    .db 0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00

platformer_enemy_pixels2::
    .db 0x3C,0x3C,0x3C,0x3C
    .db 0xFF,0xFF,0xFF,0xFF
    .db 0xF0,0xF0,0xF0,0xF0
    .db 0xFF,0xFF,0xFF,0xFF
    .db 0xCF,0xCF,0xCF,0xCF
    .db 0x55,0x55,0x55,0x55
    .db 0xAA,0xAA,0xAA,0xAA
    .db 0x00,0x00,0x00,0x00

platformer_door_pixels::
    .db 0xFF,0xFF,0xFF,0xFF
    .db 0x80,0x00,0x00,0x01
    .db 0x80,0x00,0x00,0x01
    .db 0x80,0x00,0x00,0x01
    .db 0x80,0x00,0x00,0x01
    .db 0x80,0x00,0x00,0x01
    .db 0x80,0x00,0x00,0x01
    .db 0xFF,0xFF,0xFF,0xFF

;; Second screen map (copy, can be edited)
platformer_map2:
    .db 1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1
    .db 1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1
    .db 1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1
    .db 1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1
    .db 1,0,0,0,2,2,2,2,2,2,2,2,2,2,2,2,0,0,0,1
    .db 1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1
    .db 1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1
    .db 1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1
    .db 1,0,0,0,0,0,0,0,2,2,2,2,2,2,0,0,0,0,0,1
    .db 1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1
    .db 1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1
    .db 1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1
    .db 1,0,0,0,0,0,0,0,2,2,2,2,2,2,0,0,0,0,0,1
    .db 1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1
    .db 1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1
    .db 1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1
    .db 1,0,0,0,0,0,0,0,2,2,2,2,2,2,0,0,0,0,0,1
    .db 1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1
    .db 1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1
    .db 1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1
    .db 1,0,0,0,0,0,0,0,2,2,2,2,2,2,0,0,0,0,0,1
    .db 1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1
    .db 1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1
    .db 1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1
    .db 1,1,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,1

platformer_map2_descriptor::
    .dw platformer_map2, platformer_types
    .db 20, 25, 2, 3, 4, 8, 4

platformer_view2::
    .dw platformer_tileset
    .db 0, 0, 0
    .dw 0
    .db 20, 25, 4


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
