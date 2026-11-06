;; Common definitions of the platformer project, imported by every .s file:
;; framework headers, .globl declarations, constants and macros. The .s files
;; hold only code and data.
.include "cpctelera.h.s"
.include "ecs_profile.inc"
.include "core/ecs_manager.inc"
.include "core/ecs_collision.inc"
.include "core/ecs_animation.inc"
.include "extensions/behavior.inc"
.include "video/ecs_render.inc"
.include "extensions/tilemap_render.inc"
.include "extensions/physics_platform.inc"
.include "assets/generated/assets.inc"

.globl fwk_project_init, fwk_system_wait_frame
.globl fwk_video_init, fwk_video_clear_visible
.globl fwk_input_init, fwk_input_set_bindings, fwk_input_update
.globl fwk_input_held
.globl fwk_tilemap_render_view, fwk_tilemap_render_cell, fwk_zx7b_unpack
.globl fwk_text_init, fwk_text_draw, fwk_video_get_ptr
.globl fwk_ecs_system_input, fwk_ecs_system_platform
.globl cpct_setPalette_asm, cpct_setPALColour_asm
.globl platformer_map, platformer_map_packed, platformer_palette, platformer_tileset
.globl platformer_map2, platformer_map2_packed
.globl platformer_player_pixels, platformer_player_pixels2
.globl platformer_enemy_pixels, platformer_enemy_pixels2
.globl platformer_coin_pixels, platformer_door_pixels

PFE_INPUT_LEFT  = 0x01
PFE_INPUT_RIGHT = 0x02
PFE_INPUT_JUMP  = 0x04

PFE_LIVES_INITIAL = 10
PFE_WIN_SCORE     = 4
PFE_ANIM_TICKS    = 8
PFE_ANIM_TICKS_SLOW = 4          ; enemies that run every 2nd iteration: same real time

PFE_T_PLAYER = 1
PFE_T_COIN   = 2
PFE_T_ENEMY  = 3
PFE_T_DOOR   = 4

PFE_CH_ENEMY = 0x01              ; contact channel shared by the three enemies

;; HUD: text row at scanline 10 (tile rows 1 and 2), fields as in the original.
PFE_HUD_Y          = 10
PFE_HUD_SCORE      = 0x01
PFE_HUD_LIVES      = 0x02
PFE_HUD_HINT       = 0x04
PFE_HUD_FLASH      = 0x08
PFE_BORDER_PEN     = 16
PFE_BORDER_RED     = 0x1C
PFE_BORDER_BLACK   = 0x14
PFE_FLASH_COUNT    = 3
PFE_FLASH_DELAY    = 0x1000

PFE_ENEMY_H_INITIAL_TICKS = 19
PFE_ENEMY_H_LEG_TICKS     = 23
PFE_ENEMY_V_LEG_TICKS     = 49

PFE_ALL_CAP = 9                  ; 4 coins, door, player, 3 enemies in one manager

;; Cadence bytes, (phase << 4) | (every - 1): the horizontal enemy moves on odd
;; loop iterations and the right vertical one on even iterations.
PFE_CAD_ODD  = 0x11
PFE_CAD_EVEN = 0x01

;; Spawn row: components, type, x, y, width, height, sprite, background,
;; background size, behavior program, animation descriptor, cadence byte.
.macro PFE_ROW comps, type, x, y, w, h, sprite, bg, cap, program, anim, cadence
    .dw comps
    .db type, x, y, w, h
    .dw sprite, bg
    .db cap
    .dw program, anim
    .db cadence
.endm
PFE_PLAYER_COMPS = ECS_C_RENDER|ECS_C_MOTION|ECS_C_INPUT|ECS_C_PLATFORM|ECS_C_COLLISION|ECS_C_ANIMATION
PFE_ENEMY_COMPS  = ECS_C_RENDER|ECS_C_MOTION|ECS_C_BEHAVIOR|ECS_C_COLLISION|ECS_C_ANIMATION
PFE_ITEM_COMPS   = ECS_C_RENDER|ECS_C_COLLISION
