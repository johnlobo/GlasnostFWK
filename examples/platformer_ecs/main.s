.module example_platformer_ecs
;; Platformer on ECS 2.0, phase 10 slice 1: same level, sprites, enemies, coins
;; and door as examples/platformer, built from the same converted assets. Three
;; managers: ITEMS (coins, door), FAST (player and the left vertical enemy, every
;; frame), H and V (the horizontal and the right vertical enemy, which alternate
;; frames as in the original).
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
.globl fwk_tilemap_render_view, fwk_zx7b_unpack
.globl fwk_ecs_system_input, fwk_ecs_system_platform
.globl cpct_setPalette_asm
.globl platformer_map, platformer_map_packed, platformer_palette, platformer_tileset
.globl platformer_player_pixels, platformer_player_pixels2
.globl platformer_enemy_pixels, platformer_enemy_pixels2
.globl platformer_coin_pixels, platformer_door_pixels

PFE_INPUT_LEFT  = 0x01
PFE_INPUT_RIGHT = 0x02
PFE_INPUT_JUMP  = 0x04

PFE_LIVES_INITIAL = 10
PFE_WIN_SCORE     = 4
PFE_ANIM_TICKS    = 8

PFE_T_PLAYER = 1
PFE_T_COIN   = 2
PFE_T_ENEMY  = 3
PFE_T_DOOR   = 4

PFE_CH_FAST = 0x01
PFE_CH_H    = 0x02
PFE_CH_V    = 0x04

PFE_ENEMY_H_INITIAL_TICKS = 19
PFE_ENEMY_H_LEG_TICKS     = 23
PFE_ENEMY_V_LEG_TICKS     = 49

PFE_ITEMS_CAP = 5
PFE_FAST_CAP  = 2
PFE_ONE_CAP   = 1
PFE_ALL_CAP   = 9

.area _DATA

;; Public state, observable by the emulator smoke.
platformer_ecs_status::  .db 0
platformer_ecs_score::   .db 0
platformer_ecs_lives::   .db PFE_LIVES_INITIAL
platformer_ecs_won::     .db 0
platformer_ecs_player::  .dw 0
platformer_ecs_enemy_h:: .dw 0
platformer_ecs_enemy_v:: .dw 0
platformer_ecs_door::    .dw 0
platformer_ecs_input_witness:: .db 0, 0

_pfe_phase:      .db 0
_pfe_all_coins:  .db 0
_pfe_door_hit:   .db 0
_pfe_anim:       .dw 0
_pfe_tpl:        .ds ECS_ENTITY_SIZE

platformer_ecs_items_storage:: .ds ECS_ENTITY_SIZE * PFE_ITEMS_CAP
platformer_ecs_storage::      .ds ECS_ENTITY_SIZE * PFE_FAST_CAP
platformer_ecs_h_storage:     .ds ECS_ENTITY_SIZE * PFE_ONE_CAP
platformer_ecs_v_storage::    .ds ECS_ENTITY_SIZE * PFE_ONE_CAP
FWK_ECS_MANAGER_DESCRIPTOR platformer_ecs_items, platformer_ecs_items_storage, PFE_ITEMS_CAP
FWK_ECS_MANAGER_DESCRIPTOR platformer_ecs_manager, platformer_ecs_storage, PFE_FAST_CAP
FWK_ECS_MANAGER_DESCRIPTOR platformer_ecs_h, platformer_ecs_h_storage, PFE_ONE_CAP
FWK_ECS_MANAGER_DESCRIPTOR platformer_ecs_v, platformer_ecs_v_storage, PFE_ONE_CAP

;; One background buffer per entity: the renderer saves what each sprite covers.
_pfe_bg_player: .ds 8 * 8
_pfe_bg_h:      .ds 4 * 8
_pfe_bg_v:      .ds 4 * 8
_pfe_bg_v2:     .ds 4 * 8
_pfe_bg_coin0:  .ds 4 * 8
_pfe_bg_coin1:  .ds 4 * 8
_pfe_bg_coin2:  .ds 4 * 8
_pfe_bg_coin3:  .ds 4 * 8
_pfe_bg_door:   .ds 4 * 8

_pfe_managers: .dw platformer_ecs_items, platformer_ecs_manager, platformer_ecs_h, platformer_ecs_v
_pfe_work: .ds 8 * PFE_ALL_CAP
FWK_ECS_RENDER_SCENE platformer_ecs_scene, _pfe_managers, 4, _pfe_work, PFE_ALL_CAP

_pfe_types:
    .db 0, 1, 2, 0
FWK_TILEMAP_DESCRIPTOR platformer_ecs_map_descriptor, platformer_map, _pfe_types, PLATFORMER_MAP_WIDTH, PLATFORMER_MAP_HEIGHT, 2, 3, 4, 8, 4
FWK_TILE_RENDER_DESCRIPTOR platformer_ecs_view, platformer_tileset, 0, 0, 0, 0, PLATFORMER_MAP_WIDTH, PLATFORMER_MAP_HEIGHT, 4
FWK_PLATFORM_CONFIG platformer_ecs_config, 80, 255, 1, 8

platformer_ecs_bindings:
    .dw Key_CursorLeft
    .db PFE_INPUT_LEFT
    .dw Key_CursorRight
    .db PFE_INPUT_RIGHT
    .dw Key_CursorUp
    .db PFE_INPUT_JUMP
    .dw 0
    .db 0

_pfe_anim_player: .db 2, PFE_ANIM_TICKS
    .dw platformer_player_pixels, platformer_player_pixels2
_pfe_anim_enemy: .db 2, PFE_ANIM_TICKS
    .dw platformer_enemy_pixels, platformer_enemy_pixels2

;; Same patrols as examples/platformer/assets.s.
_pfe_program_h:
    FWK_BEHAVIOR_SET_VX 1
    FWK_BEHAVIOR_WAIT PFE_ENEMY_H_INITIAL_TICKS, _pfe_program_h_left
_pfe_program_h_left:
    FWK_BEHAVIOR_SET_VX -1
    FWK_BEHAVIOR_WAIT PFE_ENEMY_H_LEG_TICKS, _pfe_program_h_right
_pfe_program_h_right:
    FWK_BEHAVIOR_SET_VX 1
    FWK_BEHAVIOR_WAIT PFE_ENEMY_H_LEG_TICKS, _pfe_program_h_left
_pfe_program_v:
    FWK_BEHAVIOR_SET_VY 2
    FWK_BEHAVIOR_WAIT PFE_ENEMY_V_LEG_TICKS, _pfe_program_v_turn
_pfe_program_v_turn:
    FWK_BEHAVIOR_SET_VY -2
    FWK_BEHAVIOR_WAIT PFE_ENEMY_V_LEG_TICKS, _pfe_program_v

;; Spawn row: components, type, x, y, width, height, sprite, background,
;; background size, behavior program, animation descriptor.
.macro PFE_ROW comps, type, x, y, w, h, sprite, bg, cap, program, anim
    .dw comps
    .db type, x, y, w, h
    .dw sprite, bg
    .db cap
    .dw program, anim
.endm
PFE_PLAYER_COMPS = ECS_C_RENDER|ECS_C_MOTION|ECS_C_INPUT|ECS_C_PLATFORM|ECS_C_COLLISION|ECS_C_ANIMATION
PFE_ENEMY_COMPS  = ECS_C_RENDER|ECS_C_MOTION|ECS_C_BEHAVIOR|ECS_C_COLLISION|ECS_C_ANIMATION
PFE_ITEM_COMPS   = ECS_C_RENDER|ECS_C_COLLISION

_pfe_row_player: PFE_ROW PFE_PLAYER_COMPS, PFE_T_PLAYER, 16, 184, 8, 8, platformer_player_pixels, _pfe_bg_player, 64, 0, _pfe_anim_player
_pfe_row_h:      PFE_ROW PFE_ENEMY_COMPS, PFE_T_ENEMY, 36, 122, 4, 8, platformer_enemy_pixels, _pfe_bg_h, 32, _pfe_program_h, _pfe_anim_enemy
_pfe_row_v:      PFE_ROW PFE_ENEMY_COMPS, PFE_T_ENEMY, 64, 56, 4, 8, platformer_enemy_pixels, _pfe_bg_v, 32, _pfe_program_v, _pfe_anim_enemy
_pfe_row_v2:     PFE_ROW PFE_ENEMY_COMPS, PFE_T_ENEMY, 8, 56, 4, 8, platformer_enemy_pixels, _pfe_bg_v2, 32, _pfe_program_v, _pfe_anim_enemy
_pfe_row_coin0:  PFE_ROW PFE_ITEM_COMPS, PFE_T_COIN, 16, 24, 4, 8, platformer_coin_pixels, _pfe_bg_coin0, 32, 0, 0
_pfe_row_coin1:  PFE_ROW PFE_ITEM_COMPS, PFE_T_COIN, 56, 24, 4, 8, platformer_coin_pixels, _pfe_bg_coin1, 32, 0, 0
_pfe_row_coin2:  PFE_ROW PFE_ITEM_COMPS, PFE_T_COIN, 16, 168, 4, 8, platformer_coin_pixels, _pfe_bg_coin2, 32, 0, 0
_pfe_row_coin3:  PFE_ROW PFE_ITEM_COMPS, PFE_T_COIN, 56, 168, 4, 8, platformer_coin_pixels, _pfe_bg_coin3, 32, 0, 0
_pfe_row_door:   PFE_ROW PFE_ITEM_COMPS, PFE_T_DOOR, 72, 160, 4, 8, platformer_door_pixels, _pfe_bg_door, 32, 0, 0

.area _CODE

_pfe_fail:
    ld (platformer_ecs_status), a
_pfe_fail_loop:
    call fwk_system_wait_frame
    jr _pfe_fail_loop

;; Continue on success; on error stop the game with the ABI code in the status.
_pfe_expect_ok:
    ret nc
    pop hl
    jp _pfe_fail

;; In: IX=manager, HL=spawn row. Out: IY=entity. Builds a template from the row.
_pfe_spawn:
    push hl
    ld hl, #_pfe_tpl
    ld de, #_pfe_tpl + 1
    ld (hl), #0
    ld bc, #ECS_ENTITY_SIZE - 1
    ldir
    pop hl
    ld iy, #_pfe_tpl
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
    ld ECS_E_RENDER_BACKGROUND(iy), a
    ld a, (hl)
    inc hl
    ld ECS_E_RENDER_BACKGROUND+1(iy), a
    ld a, (hl)
    inc hl
    ld ECS_E_RENDER_BACKGROUND_CAP(iy), a
    ld a, (hl)
    inc hl
    ld ECS_E_BEHAVIOR_PROGRAM(iy), a
    ld a, (hl)
    inc hl
    ld ECS_E_BEHAVIOR_PROGRAM+1(iy), a
    ld e, (hl)
    inc hl
    ld d, (hl)
    ld (_pfe_anim), de
    ld ECS_E_RENDER_FLAGS(iy), #ECS_RENDER_VISIBLE | ECS_RENDER_DIRTY
    ld ECS_E_RENDER_SORT_OFFSET_Y(iy), #8      ; sort by the feet, like the original
    ld hl, #_pfe_tpl
    call fwk_ecs_entity_create
    ret c
    ld hl, (_pfe_anim)
    ld a, h
    or l
    ret z
    jp fwk_ecs_anim_set

;; Spawns the row in HL into the manager in IX and stores the entity in (DE).
_pfe_spawn_to:
    push de
    call _pfe_spawn
    call _pfe_expect_ok
    pop hl
    push iy
    pop de
    ld (hl), e
    inc hl
    ld (hl), d
    ret

;; Collision callbacks: IX=manager, IY=target, HL=subject, A=ENTER/STAY/EXIT.
_pfe_items_cb:
    cp #ECS_COLLISION_EXIT
    jr z, _pfe_cb_ok
    ld a, ECS_E_TYPE(iy)
    cp #PFE_T_DOOR
    jr z, _pfe_cb_door
    cp #PFE_T_COIN
    jr nz, _pfe_cb_ok
    push ix
    push iy
    call fwk_ecs_entity_mark_destroy
    pop iy
    pop ix
    ret c
    ld a, (platformer_ecs_score)
    inc a
    ld (platformer_ecs_score), a
    cp #PFE_WIN_SCORE
    jr nz, _pfe_cb_ok
    ld (_pfe_all_coins), a
_pfe_cb_ok:
    xor a
    ret
_pfe_cb_door:
    ld a, #1
    ld (_pfe_door_hit), a
    xor a
    ret

_pfe_enemy_cb:
    cp #ECS_COLLISION_ENTER
    jr nz, _pfe_cb_ok
    ld a, (platformer_ecs_lives)
    or a
    jr z, _pfe_cb_ok
    dec a
    ld (platformer_ecs_lives), a
    xor a
    ret

;; Player against the items and each enemy group. Every enemy has its own
;; contact channel, so a life is lost when the player starts touching an enemy,
;; not every frame. Once all coins are taken enemies stop hurting, as in the
;; original.
_pfe_collisions:
    ld iy, (platformer_ecs_player)
    ld ix, #platformer_ecs_items
    ld bc, #ECS_C_COLLISION
    ld hl, #_pfe_items_cb
    ld e, #0
    call fwk_ecs_collide
    call _pfe_expect_ok
    ld a, (platformer_ecs_won)
    or a
    ret nz
    ld iy, (platformer_ecs_player)
    ld ix, #platformer_ecs_manager
    ld bc, #ECS_C_COLLISION
    ld hl, #_pfe_enemy_cb
    ld e, #PFE_CH_FAST
    call fwk_ecs_collide
    call _pfe_expect_ok
    ld iy, (platformer_ecs_player)
    ld ix, #platformer_ecs_h
    ld bc, #ECS_C_COLLISION
    ld hl, #_pfe_enemy_cb
    ld e, #PFE_CH_H
    call fwk_ecs_collide
    call _pfe_expect_ok
    ld iy, (platformer_ecs_player)
    ld ix, #platformer_ecs_v
    ld bc, #ECS_C_COLLISION
    ld hl, #_pfe_enemy_cb
    ld e, #PFE_CH_V
    call fwk_ecs_collide
    call _pfe_expect_ok
    ret

;; Rules that change entity states cannot run inside a traversal: they are
;; applied here, after the collision passes.
_pfe_apply_events:
    ld a, (_pfe_all_coins)
    or a
    jr z, _pfe_no_win
    xor a
    ld (_pfe_all_coins), a
    inc a
    ld (platformer_ecs_won), a
    ld ix, #platformer_ecs_items
    ld iy, (platformer_ecs_door)
    call fwk_ecs_entity_enable
    call _pfe_expect_ok
_pfe_no_win:
    ld a, (_pfe_door_hit)
    or a
    ret z
    xor a
    ld (_pfe_door_hit), a
    ld (platformer_ecs_won), a
    ld ix, #platformer_ecs_items
    ld iy, (platformer_ecs_door)
    call fwk_ecs_entity_disable
    jp _pfe_expect_ok

;; In: IX=the manager whose turn it is. Behavior, then motion.
_pfe_enemy_turn:
    push ix
    call fwk_ecs_system_behavior
    call _pfe_expect_ok
    pop ix
    call fwk_ecs_system_motion_u8
    jp _pfe_expect_ok

_main::
    call fwk_project_init
    ld hl, #platformer_map_packed + PLATFORMER_MAP_PACKED_SIZE - 1
    ld de, #platformer_map + PLATFORMER_MAP_SIZE - 1
    call fwk_zx7b_unpack
    call fwk_video_init
    ld hl, #platformer_palette
    ld de, #PLATFORMER_PALETTE_SIZE
    call cpct_setPalette_asm
    call fwk_input_init
    ld hl, #platformer_ecs_bindings
    call fwk_input_set_bindings
    xor a
    call fwk_video_clear_visible
    ld ix, #platformer_ecs_map_descriptor
    ld iy, #platformer_ecs_view
    call fwk_tilemap_render_view
    call _pfe_expect_ok

    ld ix, #platformer_ecs_items
    call fwk_ecs_manager_init
    call _pfe_expect_ok
    ld ix, #platformer_ecs_manager
    call fwk_ecs_manager_init
    call _pfe_expect_ok
    ld ix, #platformer_ecs_h
    call fwk_ecs_manager_init
    call _pfe_expect_ok
    ld ix, #platformer_ecs_v
    call fwk_ecs_manager_init
    call _pfe_expect_ok

    ld ix, #platformer_ecs_items
    ld hl, #_pfe_row_coin0
    call _pfe_spawn
    call _pfe_expect_ok
    ld hl, #_pfe_row_coin1
    call _pfe_spawn
    call _pfe_expect_ok
    ld hl, #_pfe_row_coin2
    call _pfe_spawn
    call _pfe_expect_ok
    ld hl, #_pfe_row_coin3
    call _pfe_spawn
    call _pfe_expect_ok
    ld hl, #_pfe_row_door
    ld de, #platformer_ecs_door
    call _pfe_spawn_to
    ld iy, (platformer_ecs_door)
    call fwk_ecs_entity_disable            ; the door appears after the last coin
    call _pfe_expect_ok

    ld ix, #platformer_ecs_manager
    ld hl, #_pfe_row_player
    ld de, #platformer_ecs_player
    call _pfe_spawn_to
    ld iy, (platformer_ecs_player)
    ld ECS_E_INPUT_ACTION_MASK(iy), #PFE_INPUT_LEFT | PFE_INPUT_RIGHT | PFE_INPUT_JUMP
    ld ECS_E_PLATFORM_CONFIG(iy), #<platformer_ecs_config
    ld ECS_E_PLATFORM_CONFIG+1(iy), #>platformer_ecs_config
    ld ECS_E_PLATFORM_TILEMAP(iy), #<platformer_ecs_map_descriptor
    ld ECS_E_PLATFORM_TILEMAP+1(iy), #>platformer_ecs_map_descriptor
    ld ECS_E_MOTION_FLAGS(iy), #FWK_PLATFORM_AIRBORNE
    ld hl, #_pfe_row_v2
    call _pfe_spawn
    call _pfe_expect_ok
    ld ix, #platformer_ecs_h
    ld hl, #_pfe_row_h
    ld de, #platformer_ecs_enemy_h
    call _pfe_spawn_to
    ld ix, #platformer_ecs_v
    ld hl, #_pfe_row_v
    ld de, #platformer_ecs_enemy_v
    call _pfe_spawn_to

    ld a, #0x5A
    ld (platformer_ecs_status), a

platformer_ecs_frame:
    call fwk_input_update
    ld a, (fwk_input_held)
    ld (platformer_ecs_input_witness), a
    ld ix, #platformer_ecs_manager
    call fwk_ecs_system_behavior
    call _pfe_expect_ok
    ld ix, #platformer_ecs_manager
    call fwk_ecs_system_input
    call _pfe_expect_ok
    ld iy, (platformer_ecs_player)
    ld a, ECS_E_MOTION_VELOCITY_X(iy)
    ld (platformer_ecs_input_witness+1), a
    ld ix, #platformer_ecs_manager
    call fwk_ecs_system_platform
    call _pfe_expect_ok
    ld ix, #platformer_ecs_manager
    call fwk_ecs_system_motion_u8
    call _pfe_expect_ok
    ;; The horizontal and the right vertical enemy take turns, one per frame.
    ld a, (_pfe_phase)
    xor #1
    ld (_pfe_phase), a
    ld ix, #platformer_ecs_v
    jr z, _pfe_turn
    ld ix, #platformer_ecs_h
_pfe_turn:
    call _pfe_enemy_turn
    ld ix, #platformer_ecs_manager
    call fwk_ecs_system_animation
    call _pfe_expect_ok
    ld ix, #platformer_ecs_h
    call fwk_ecs_system_animation
    call _pfe_expect_ok
    ld ix, #platformer_ecs_v
    call fwk_ecs_system_animation
    call _pfe_expect_ok
    call _pfe_collisions
    call _pfe_apply_events
    ;; Selective render: find what changed before VSYNC, touch video RAM after it.
    ld ix, #platformer_ecs_scene
    call fwk_ecs_render_prepare
    call _pfe_expect_ok
    call fwk_system_wait_frame
    ld ix, #platformer_ecs_scene
    call fwk_ecs_render_restore
    call _pfe_expect_ok
    ld ix, #platformer_ecs_scene
    call fwk_ecs_render_draw
    call _pfe_expect_ok
    ;; Coins taken this frame have been erased: free their slots.
    ld ix, #platformer_ecs_items
    call fwk_ecs_manager_collect
    call _pfe_expect_ok
    jp platformer_ecs_frame
