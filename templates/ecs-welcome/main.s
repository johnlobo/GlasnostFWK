.module game_main
;; Welcome project on GlasnostFWK ECS 2.0: a ship you move with the cursor keys
;; and three drones that patrol. It shows the pieces every game uses: a manager
;; with its entities, the input, behavior and motion systems, a selective
;; renderer with background pools, and text. Replace it with your own game.
;;
;; This file holds code and data only; .globl declarations, constants and macros
;; live in common.inc. generated/project.inc is written by `glasnost config`:
;; do not edit it.
.include "common.inc"
.include "generated/project.inc"

.area _DATA

;; ---- Public state, observable by tests and the emulator ----
game_status::  .db 0              ; 0x5A once the game is running, else the ABI error code
game_player::  .dw 0              ; address of the player entity

;; ---- Texts ----
_game_str_welcome: .asciz "WELCOME TO"
_game_str_help:    .asciz "CURSOR KEYS MOVE"

;; ---- Sprites come from assets/generated/assets.s (PNG -> Mode 0 bytes). ----

;; ---- Palette comes from assets/generated/assets.s (assets/palette.json). ----

;; ---- Tilemap: types table (id -> type) and render descriptors ----
_game_types: .db 0, 0, 0, 0
game_view:
    .dw game_tileset
    .db 0, 0, 0
    .dw GAME_MAP_SCREEN_Y
    .db GAME_MAP_WIDTH, GAME_MAP_HEIGHT, 4
game_map_desc:
    .dw game_map, _game_types
    .db GAME_MAP_WIDTH, GAME_MAP_HEIGHT, 2, 3, 4, 8, 4

;; ---- Entity storage: ECS_ENTITY_SIZE-byte slots, filled in spawn order ----
_game_tpl:      .ds ECS_ENTITY_SIZE    ; template built from a spawn row, copied into the manager
game_storage::  .ds ECS_ENTITY_SIZE * GAME_CAP
FWK_ECS_MANAGER_DESCRIPTOR game_manager, game_storage, GAME_CAP

;; ---- Renderer: one pool of GAME_CAP background buffers of 32 bytes (4 x 8) ----
FWK_ECS_RENDER_POOL game_pool32, 32, GAME_CAP
_game_pools:    .dw game_pool32
_game_managers: .dw game_manager
_game_work:     .ds 8 * GAME_CAP
FWK_ECS_RENDER_SCENE game_scene, _game_managers, 1, _game_work, GAME_CAP, _game_pools, 1

;; ---- Keyboard: (key, action bit) pairs ended by a zero key ----
game_bindings:
    .dw Key_CursorLeft
    .db GAME_INPUT_LEFT
    .dw Key_CursorRight
    .db GAME_INPUT_RIGHT
    .dw Key_CursorUp
    .db GAME_INPUT_UP
    .dw Key_CursorDown
    .db GAME_INPUT_DOWN
    .dw 0
    .db 0

;; ---- Drone patrol program: right for half a leg, then left and right in full legs ----
_game_program_drone:
    FWK_BEHAVIOR_SET_VX 1
    FWK_BEHAVIOR_WAIT GAME_DRONE_FIRST_LEG, _game_program_drone_left
_game_program_drone_left:
    FWK_BEHAVIOR_SET_VX -1
    FWK_BEHAVIOR_WAIT GAME_DRONE_LEG, _game_program_drone_right
_game_program_drone_right:
    FWK_BEHAVIOR_SET_VX 1
    FWK_BEHAVIOR_WAIT GAME_DRONE_LEG, _game_program_drone_left

;; ---- Spawn rows (see GAME_ROW) ----
_game_row_player: GAME_ROW GAME_PLAYER_COMPS, GAME_T_PLAYER, 38, 170, 4, 8, game_ship_pixels, 0
_game_row_drone0: GAME_ROW GAME_DRONE_COMPS, GAME_T_DRONE, 30, 70, 4, 8, game_drone_pixels, _game_program_drone
_game_row_drone1: GAME_ROW GAME_DRONE_COMPS, GAME_T_DRONE, 40, 100, 4, 8, game_drone_pixels, _game_program_drone
_game_row_drone2: GAME_ROW GAME_DRONE_COMPS, GAME_T_DRONE, 30, 130, 4, 8, game_drone_pixels, _game_program_drone

.area _CODE

;; Stops the game with the ABI error code in game_status.
_game_fail:
    ld (game_status), a
_game_fail_loop:
    call fwk_system_wait_frame
    jr _game_fail_loop

;; Continues on success; on error stops the game.
_game_expect_ok:
    ret nc
    pop hl
    jp _game_fail

;; In: IX=manager, HL=spawn row. Out: IY=entity. Builds a template from the row.
_game_spawn:
    push hl
    ld hl, #_game_tpl
    ld de, #_game_tpl + 1
    ld (hl), #0
    ld bc, #ECS_ENTITY_SIZE - 1
    ldir
    pop hl
    ld iy, #_game_tpl
    ld a, (hl)
    inc hl
    ld ECS_E_COMPONENTS(iy), a
    ld a, (hl)
    inc hl
    ld ECS_E_COMPONENTS+1(iy), a
    ld ECS_E_STATUS(iy), #ECS_STATUS_ACTIVE
    ld a, (hl)
    inc hl
    ld ECS_E_TYPE(iy), a
    ld a, (hl)
    inc hl
    ld ECS_E_X(iy), a
    ld a, (hl)
    inc hl
    ld ECS_E_Y(iy), a
    ld a, (hl)
    inc hl
    ld ECS_E_WIDTH(iy), a
    ld a, (hl)
    inc hl
    ld ECS_E_HEIGHT(iy), a
    ld a, (hl)
    inc hl
    ld ECS_E_RENDER_SPRITE(iy), a
    ld a, (hl)
    inc hl
    ld ECS_E_RENDER_SPRITE+1(iy), a
    ld a, (hl)
    inc hl
    ld ECS_E_BEHAVIOR_PROGRAM(iy), a
    ld a, (hl)
    ld ECS_E_BEHAVIOR_PROGRAM+1(iy), a
    ld ECS_E_RENDER_FLAGS(iy), #ECS_RENDER_VISIBLE | ECS_RENDER_DIRTY
    ld hl, #_game_tpl
    jp fwk_ecs_entity_create

;; In: B=scanline, HL=string. Draws it at the left margin.
_game_text:
    push hl
    ld l, b
    ld h, #0
    ld c, #GAME_TEXT_X
    call fwk_video_get_ptr
    pop iy
    jp fwk_text_draw

;; Steering system, run before motion: UP and DOWN set the vertical velocity.
;; Callbacks of fwk_ecs_system_run get IX=manager, IY=entity and must keep both.
_game_steer:
    push ix
    push iy
    ld a, (fwk_input_held)
    ld c, a
    xor a
    bit 3, c                         ; GAME_INPUT_UP
    jr z, _game_steer_down
    ld a, #-GAME_SPEED_Y
_game_steer_down:
    bit 4, c                         ; GAME_INPUT_DOWN
    jr z, _game_steer_set
    ld a, #GAME_SPEED_Y
_game_steer_set:
    ld ECS_E_MOTION_VELOCITY_Y(iy), a
    pop iy
    pop ix
    xor a
    ret

;; Keeps the player inside the play area, run after motion. Positions are
;; unsigned bytes: going left past 0 wraps to 254, which the first test catches.
_game_clamp:
    push ix
    push iy
    ld a, ECS_E_X(iy)
    cp #200
    jr c, _game_clamp_x_max
    xor a
    jr _game_clamp_x_set
_game_clamp_x_max:
    cp #GAME_X_MAX + 1
    jr c, _game_clamp_y
    ld a, #GAME_X_MAX
_game_clamp_x_set:
    ld ECS_E_X(iy), a
_game_clamp_y:
    ld a, ECS_E_Y(iy)
    cp #GAME_Y_MIN
    jr nc, _game_clamp_y_max
    ld a, #GAME_Y_MIN
    jr _game_clamp_y_set
_game_clamp_y_max:
    cp #GAME_Y_MAX + 1
    jr c, _game_clamp_done
    ld a, #GAME_Y_MAX
_game_clamp_y_set:
    ld ECS_E_Y(iy), a
_game_clamp_done:
    pop iy
    pop ix
    xor a
    ret

_main::
    call fwk_project_init
    call fwk_video_init
    call fwk_text_init
    ld hl, #game_palette
    ld de, #GAME_PALETTE_SIZE
    call cpct_setPalette_asm
    call fwk_input_init
    ld hl, #game_bindings
    call fwk_input_set_bindings
    xor a
    call fwk_video_clear_visible

    ;; Unpack and draw the background tilemap.
    ld hl, #game_map_packed + GAME_MAP_PACKED_SIZE - 1
    ld de, #game_map + GAME_MAP_SIZE - 1
    call fwk_zx7b_unpack
    ld ix, #game_map_desc
    ld iy, #game_view
    call fwk_tilemap_render_view
    call _game_expect_ok

    ld b, #GAME_TEXT_Y_WELCOME
    ld hl, #_game_str_welcome
    call _game_text
    ld b, #GAME_TEXT_Y_TITLE
    ld hl, #game_title
    call _game_text
    ld b, #GAME_TEXT_Y_HELP
    ld hl, #_game_str_help
    call _game_text

    ld ix, #game_manager
    call fwk_ecs_manager_init
    call _game_expect_ok
    ld ix, #game_scene
    call fwk_ecs_render_reset
    call _game_expect_ok

    ld ix, #game_manager
    ld hl, #_game_row_player
    call _game_spawn
    call _game_expect_ok
    ld (game_player), iy
    ld ECS_E_INPUT_ACTION_MASK(iy), #GAME_INPUT_LEFT | GAME_INPUT_RIGHT
    ld ix, #game_manager
    ld hl, #_game_row_drone0
    call _game_spawn
    call _game_expect_ok
    ld ix, #game_manager
    ld hl, #_game_row_drone1
    call _game_spawn
    call _game_expect_ok
    ld ix, #game_manager
    ld hl, #_game_row_drone2
    call _game_spawn
    call _game_expect_ok

    ld a, #0x5A
    ld (game_status), a

game_frame:
    call fwk_input_update
    ld ix, #game_manager
    call fwk_ecs_system_behavior
    call _game_expect_ok
    ld ix, #game_manager
    call fwk_ecs_system_input        ; LEFT and RIGHT set the horizontal velocity
    call _game_expect_ok
    ld ix, #game_manager
    ld bc, #ECS_C_INPUT
    ld hl, #_game_steer              ; UP and DOWN set the vertical velocity
    call fwk_ecs_system_run
    call _game_expect_ok
    ld ix, #game_manager
    call fwk_ecs_system_motion_u8    ; velocity moves every entity
    call _game_expect_ok
    ld ix, #game_manager
    ld bc, #ECS_C_INPUT
    ld hl, #_game_clamp
    call fwk_ecs_system_run
    call _game_expect_ok
    ;; Selective render: find what changed before VSYNC, touch video RAM after it.
    ld ix, #game_scene
    call fwk_ecs_render_prepare
    call _game_expect_ok
    call fwk_system_wait_frame
    ld ix, #game_scene
    call fwk_ecs_render_restore
    call _game_expect_ok
    ld ix, #game_scene
    call fwk_ecs_render_draw
    call _game_expect_ok
    jp game_frame
