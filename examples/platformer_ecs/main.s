.module example_platformer_ecs
.include "ecs_profile.inc"
.include "core/ecs_manager.inc"
.include "extensions/behavior.inc"
.include "video/sprite.inc"

.globl fwk_project_init, fwk_system_wait_frame
.globl fwk_video_init, fwk_video_clear_visible
.globl fwk_sprite_draw

PLATFORMER_ECS_CAPACITY = 3

.area _DATA
platformer_ecs_storage:: .ds ECS_ENTITY_SIZE * PLATFORMER_ECS_CAPACITY
FWK_ECS_MANAGER_DESCRIPTOR platformer_ecs_manager, platformer_ecs_storage, PLATFORMER_ECS_CAPACITY

platformer_ecs_pixels_player:
    .db 0x00,0xAA,0xAA,0xAA,0xAA,0x00
    .db 0xAA,0xFF,0xFF,0xFF,0xFF,0xAA
    .db 0xAA,0xFF,0x00,0x00,0xFF,0xAA
    .db 0xAA,0xFF,0xFF,0xFF,0xFF,0xAA
    .db 0xAA,0xFF,0x00,0x00,0xFF,0xAA
    .db 0xAA,0xFF,0x00,0x00,0xFF,0xAA
    .db 0xAA,0xFF,0xFF,0xFF,0xFF,0xAA
    .db 0x00,0xAA,0xAA,0xAA,0xAA,0x00
platformer_ecs_pixels_enemy:
    .db 0x00,0x55,0x55,0x55,0x55,0x00
    .db 0x55,0x00,0x00,0x00,0x00,0x55
    .db 0x55,0x00,0x55,0x55,0x00,0x55
    .db 0x55,0x00,0x00,0x00,0x00,0x55
    .db 0x55,0x00,0x55,0x55,0x00,0x55
    .db 0x55,0x00,0x00,0x00,0x00,0x55
    .db 0x55,0x55,0x55,0x55,0x55,0x55
    .db 0x00,0x55,0x55,0x55,0x55,0x00

FWK_SPRITE_DESCRIPTOR platformer_ecs_player_sprite, platformer_ecs_pixels_player, 10, 80, 6, 8
FWK_SPRITE_DESCRIPTOR platformer_ecs_enemy_h_sprite, platformer_ecs_pixels_enemy, 35, 120, 6, 8
FWK_SPRITE_DESCRIPTOR platformer_ecs_enemy_v_sprite, platformer_ecs_pixels_enemy, 65, 40, 6, 8

platformer_ecs_behavior_idle:
    FWK_BEHAVIOR_IDLE
    FWK_BEHAVIOR_GOTO platformer_ecs_behavior_idle
platformer_ecs_behavior_horizontal:
    FWK_BEHAVIOR_SET_VX 1
    FWK_BEHAVIOR_WAIT 24, platformer_ecs_behavior_horizontal_back
platformer_ecs_behavior_horizontal_back:
    FWK_BEHAVIOR_SET_VX 0xFF
    FWK_BEHAVIOR_WAIT 24, platformer_ecs_behavior_horizontal
platformer_ecs_behavior_vertical:
    FWK_BEHAVIOR_SET_VY 1
    FWK_BEHAVIOR_WAIT 24, platformer_ecs_behavior_vertical_back
platformer_ecs_behavior_vertical_back:
    FWK_BEHAVIOR_SET_VY 0xFF
    FWK_BEHAVIOR_WAIT 24, platformer_ecs_behavior_vertical

platformer_ecs_player_template:
    .dw ECS_C_RENDER | ECS_C_MOTION
    .db ECS_STATUS_ACTIVE, 0, 10, 80, 6, 8
    .dw platformer_ecs_player_sprite
    .db 0, 0, 0, 0
    .dw 0, 0
    .db ECS_RENDER_VISIBLE | ECS_RENDER_DIRTY, 0, 0
    .dw 0, 0
    .db 0, 0, 0
    .dw platformer_ecs_behavior_idle
    .db 0, 0
platformer_ecs_enemy_h_template:
    .dw ECS_C_RENDER | ECS_C_MOTION | ECS_C_BEHAVIOR
    .db ECS_STATUS_ACTIVE, 1, 35, 120, 6, 8
    .dw platformer_ecs_enemy_h_sprite
    .db 0, 0, 0, 0
    .dw 0, 0
    .db ECS_RENDER_VISIBLE | ECS_RENDER_DIRTY, 0, 0
    .dw 0, 0
    .db 0, 0, 0
    .dw platformer_ecs_behavior_horizontal
    .db 0, 0
platformer_ecs_enemy_v_template:
    .dw ECS_C_RENDER | ECS_C_MOTION | ECS_C_BEHAVIOR
    .db ECS_STATUS_ACTIVE, 2, 65, 40, 6, 8
    .dw platformer_ecs_enemy_v_sprite
    .db 0, 0, 0, 0
    .dw 0, 0
    .db ECS_RENDER_VISIBLE | ECS_RENDER_DIRTY, 0, 0
    .dw 0, 0
    .db 0, 0, 0
    .dw platformer_ecs_behavior_vertical
    .db 0, 0

platformer_ecs_status:: .db 0
platformer_ecs_player:: .dw 0
platformer_ecs_enemy_h:: .dw 0
platformer_ecs_enemy_v:: .dw 0

.area _CODE

_platformer_ecs_fail:
    ld (platformer_ecs_status), a
_platformer_ecs_loop:
    call fwk_system_wait_frame
    jr _platformer_ecs_loop

_platformer_ecs_expect_ok:
    ret nc
    pop hl
    jp _platformer_ecs_fail

;; Phase 5 bridge: use the ECS entity's render pointer and coordinates to call
;; the existing sprite primitive. Full dirty/background render systems arrive
;; in a later migration phase; this bridge deliberately renders every entity.
_platformer_ecs_render_entity:
    push ix
    ld l, ECS_E_RENDER_SPRITE(iy)
    ld h, ECS_E_RENDER_SPRITE+1(iy)
    push hl
    pop ix
    ld a, ECS_E_X(iy)
    ld 2(ix), a
    xor a
    ld 3(ix), a
    ld a, ECS_E_Y(iy)
    ld 4(ix), a
    xor a
    ld 5(ix), a
    call fwk_sprite_draw
    or a
    pop ix
    ret

_main::
    call fwk_project_init
    call fwk_video_init
    xor a
    call fwk_video_clear_visible
    ld ix, #platformer_ecs_manager
    call fwk_ecs_manager_init
    call _platformer_ecs_expect_ok

    ld hl, #platformer_ecs_player_template
    call fwk_ecs_entity_create
    call _platformer_ecs_expect_ok
    push iy
    pop hl
    ld (platformer_ecs_player), hl
    ld hl, #platformer_ecs_enemy_h_template
    call fwk_ecs_entity_create
    call _platformer_ecs_expect_ok
    push iy
    pop hl
    ld (platformer_ecs_enemy_h), hl
    ld hl, #platformer_ecs_enemy_v_template
    call fwk_ecs_entity_create
    call _platformer_ecs_expect_ok
    push iy
    pop hl
    ld (platformer_ecs_enemy_v), hl
    ld a, #0x5A
    ld (platformer_ecs_status), a

platformer_ecs_frame:
    call fwk_system_wait_frame
    ld ix, #platformer_ecs_manager
    call fwk_ecs_system_behavior
    call _platformer_ecs_expect_ok
    ld ix, #platformer_ecs_manager
    call fwk_ecs_system_motion_u8
    call _platformer_ecs_expect_ok
    xor a
    call fwk_video_clear_visible
    ld bc, #ECS_C_RENDER
    ld hl, #_platformer_ecs_render_entity
    ld ix, #platformer_ecs_manager
    call fwk_ecs_system_run
    call _platformer_ecs_expect_ok
    jr platformer_ecs_frame
