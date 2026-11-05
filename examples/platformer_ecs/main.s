.module example_platformer_ecs
.include "cpctelera.h.s"
.include "ecs_profile.inc"
.include "core/ecs_manager.inc"
.include "extensions/behavior.inc"
.include "video/ecs_render.inc"
.include "extensions/tilemap_render.inc"
.include "extensions/physics_platform.inc"

.globl fwk_project_init, fwk_system_wait_frame
.globl fwk_video_init, fwk_video_clear_visible
.globl fwk_input_init, fwk_input_set_bindings, fwk_input_update
.globl fwk_input_held
.globl fwk_tilemap_render_view
.globl fwk_ecs_system_input, fwk_ecs_system_platform

PLATFORMER_ECS_CAPACITY = 3
PLATFORMER_ECS_INPUT_LEFT = 0x01
PLATFORMER_ECS_INPUT_RIGHT = 0x02
PLATFORMER_ECS_INPUT_JUMP = 0x04

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

;; Background buffers: the renderer saves what each sprite covers (6 bytes x 8 lines).
platformer_ecs_player_bg: .ds 48
platformer_ecs_enemy_h_bg: .ds 48
platformer_ecs_enemy_v_bg: .ds 48
platformer_ecs_managers: .dw platformer_ecs_manager
platformer_ecs_work: .ds 8 * PLATFORMER_ECS_CAPACITY
FWK_ECS_RENDER_SCENE platformer_ecs_scene, platformer_ecs_managers, 1, platformer_ecs_work, PLATFORMER_ECS_CAPACITY

platformer_ecs_types:
    .db FWK_TILE_PASSABLE, FWK_TILE_SOLID
platformer_ecs_map:
    .rept 24
        .db 0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0
    .endm
    .db 1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1
FWK_TILEMAP_DESCRIPTOR platformer_ecs_map_descriptor, platformer_ecs_map, platformer_ecs_types, 20, 25, 2, 3, 4, 8, 2
platformer_ecs_tileset:
    .rept 32
        .db 0x00
    .endm
    .rept 32
        .db 0xFF
    .endm
FWK_TILE_RENDER_DESCRIPTOR platformer_ecs_view, platformer_ecs_tileset, 0, 0, 0, 0, 20, 25, 2
FWK_PLATFORM_CONFIG platformer_ecs_config, 80, 255, 1, 8
platformer_ecs_bindings:
    .dw Key_CursorLeft
    .db PLATFORMER_ECS_INPUT_LEFT
    .dw Key_CursorRight
    .db PLATFORMER_ECS_INPUT_RIGHT
    .dw Key_CursorUp
    .db PLATFORMER_ECS_INPUT_JUMP
    .dw 0
    .db 0

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
    .db 16 + 8 + 2 + 1, 0
    .db ECS_STATUS_ACTIVE, 0, 10, 80, 6, 8
    .dw platformer_ecs_pixels_player
    .db 0, 0, 0, 0
    .dw platformer_ecs_player_bg, 48
    .db ECS_RENDER_VISIBLE | ECS_RENDER_DIRTY, 0, 0
    .dw 0, 0
    ;; Spawn airborne: physics_platform only applies gravity to airborne
    ;; bodies, so a grounded start would hover at the spawn height forever.
    .db 0, 0, FWK_PLATFORM_AIRBORNE
    .dw 0
    .db 0, 0
    .db PLATFORMER_ECS_INPUT_LEFT | PLATFORMER_ECS_INPUT_RIGHT | PLATFORMER_ECS_INPUT_JUMP
    .dw platformer_ecs_config, platformer_ecs_map_descriptor
platformer_ecs_enemy_h_template:
    .dw ECS_C_RENDER | ECS_C_MOTION | ECS_C_BEHAVIOR
    .db ECS_STATUS_ACTIVE, 1, 35, 120, 6, 8
    .dw platformer_ecs_pixels_enemy
    .db 0, 0, 0, 0
    .dw platformer_ecs_enemy_h_bg, 48
    .db ECS_RENDER_VISIBLE | ECS_RENDER_DIRTY, 0, 0
    .dw 0, 0
    .db 0, 0, 0
    .dw platformer_ecs_behavior_horizontal
    .db 0, 0
    .db 0
    .dw 0, 0
platformer_ecs_enemy_v_template:
    .dw ECS_C_RENDER | ECS_C_MOTION | ECS_C_BEHAVIOR
    .db ECS_STATUS_ACTIVE, 2, 65, 40, 6, 8
    .dw platformer_ecs_pixels_enemy
    .db 0, 0, 0, 0
    .dw platformer_ecs_enemy_v_bg, 48
    .db ECS_RENDER_VISIBLE | ECS_RENDER_DIRTY, 0, 0
    .dw 0, 0
    .db 0, 0, 0
    .dw platformer_ecs_behavior_vertical
    .db 0, 0
    .db 0
    .dw 0, 0

platformer_ecs_status:: .db 0
platformer_ecs_input_witness:: .db 0, 0
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

_main::
    call fwk_project_init
    call fwk_video_init
    call fwk_input_init
    ld hl, #platformer_ecs_bindings
    call fwk_input_set_bindings
    xor a
    call fwk_video_clear_visible
    ld ix, #platformer_ecs_map_descriptor
    ld iy, #platformer_ecs_view
    call fwk_tilemap_render_view
    call _platformer_ecs_expect_ok
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
    call fwk_input_update
    ld a, (fwk_input_held)
    ld (platformer_ecs_input_witness), a
    ld ix, #platformer_ecs_manager
    call fwk_ecs_system_behavior
    call _platformer_ecs_expect_ok
    ld ix, #platformer_ecs_manager
    call fwk_ecs_system_input
    call _platformer_ecs_expect_ok
    ld iy, (platformer_ecs_player)
    ld a, ECS_E_MOTION_VELOCITY_X(iy)
    ld (platformer_ecs_input_witness+1), a
    ld ix, #platformer_ecs_manager
    call fwk_ecs_system_platform
    call _platformer_ecs_expect_ok
    ld ix, #platformer_ecs_manager
    call fwk_ecs_system_motion_u8
    call _platformer_ecs_expect_ok
    ;; Selective render: find what changed before VSYNC, touch video RAM after it.
    ld ix, #platformer_ecs_scene
    call fwk_ecs_render_prepare
    call _platformer_ecs_expect_ok
    call fwk_system_wait_frame
    ld ix, #platformer_ecs_scene
    call fwk_ecs_render_restore
    call _platformer_ecs_expect_ok
    ld ix, #platformer_ecs_scene
    call fwk_ecs_render_draw
    call _platformer_ecs_expect_ok
    jr platformer_ecs_frame
