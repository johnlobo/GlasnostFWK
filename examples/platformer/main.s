.module example_platformer
;; Platformer on ECS 2.0: two levels, a player, four coins, three patrolling
;; enemies and a door, all in one manager. The horizontal and the right vertical
;; enemy take turns through their cadence byte (every 2nd loop iteration).
;;
;; This file holds code and data only; .globl declarations, constants and macros
;; live in common.inc.
.include "common.inc"

.area _DATA

;; ---- Public state, observable by the emulator smoke ----
platformer_status::  .db 0        ; 0x5A once the game is initialised, else the ABI error code
platformer_score::   .db 0        ; coins taken on the current level
platformer_lives::   .db PFE_LIVES_INITIAL   ; kept across levels, never below 0
platformer_won::     .db 0        ; 1 once every coin is taken: the door is enabled
platformer_level::   .db 0        ; 0 = first level, 1 = second
platformer_player::  .dw 0        ; address of the player entity (set at level start)
platformer_enemy_h:: .dw 0        ; address of the horizontal enemy
platformer_enemy_v:: .dw 0        ; address of the right vertical enemy
platformer_door::    .dw 0        ; address of the door entity
platformer_input_witness:: .db 0, 0   ; [0] actions held this frame, [1] player X velocity after the input system (for the smoke)

;; ---- Private game state ----
_pfe_map_desc:  .dw platformer_map_descriptor   ; tilemap of the active level
_pfe_all_coins:  .db 0            ; set by the coin that completes the level (wins before enemies count)
_pfe_door_hit:   .db 0            ; set when the player touches the enabled door
platformer_hud_dirty:: .db 0      ; PFE_HUD_* bits of the fields that need redrawing
_pfe_hud_pending: .db 0           ; snapshot of platformer_hud_dirty taken at the start of the HUD update
_pfe_hud_col:    .db 0            ; first tile column of the HUD field being drawn
_pfe_hud_end:    .db 0            ; tile column after the last cell of that field
_pfe_hud_x:      .db 0            ; screen byte column where its text starts (4 * first tile column)

;; ---- HUD texts (the digits are patched in place by the HUD code) ----
_pfe_str_score:  .asciz "COINS: 0/4"
_pfe_str_all:    .asciz "ALL COINS"
_pfe_str_hint:   .asciz "COLLECT ALL COINS"
_pfe_str_go:     .asciz "GO TO THE DOOR"
_pfe_str_life:   .asciz "LIFE: 10"

_pfe_anim:       .dw 0            ; scratch pointer: animation descriptor of the row being spawned
_pfe_tpl:        .ds ECS_ENTITY_SIZE   ; template entity built from a spawn row, copied into a manager

;; ---- Entity storage: ECS_ENTITY_SIZE-byte slots, filled in spawn order ----
;; 0..3 coins, 4 door, 5 player, 6 left vertical enemy, 7 horizontal enemy,
;; 8 right vertical enemy.
platformer_storage:: .ds ECS_ENTITY_SIZE * PFE_ALL_CAP
;; Manager descriptor: storage address, capacity and bookkeeping.
FWK_ECS_MANAGER_DESCRIPTOR platformer_manager, platformer_storage, PFE_ALL_CAP

;; One background buffer per entity: the renderer saves the screen bytes each
;; sprite covers (width in bytes * height in lines): player 8x8, the rest 4x8.
_pfe_bg_player: .ds 8 * 8
_pfe_bg_h:      .ds 4 * 8
_pfe_bg_v:      .ds 4 * 8
_pfe_bg_v2:     .ds 4 * 8
_pfe_bg_coin0:  .ds 4 * 8
_pfe_bg_coin1:  .ds 4 * 8
_pfe_bg_coin2:  .ds 4 * 8
_pfe_bg_coin3:  .ds 4 * 8
_pfe_bg_door:   .ds 4 * 8

;; Render scene: the manager, and the renderer's work area (8 bytes per
;; renderable entity, all nine at most).
_pfe_managers: .dw platformer_manager
_pfe_work: .ds 8 * PFE_ALL_CAP
FWK_ECS_RENDER_SCENE platformer_scene, _pfe_managers, 1, _pfe_work, PFE_ALL_CAP

;; Tile types by tile id: 0 passable, 1 solid, 2 one-way platform, 0 passable.
_pfe_types:
    .db 0, 1, 2, 0
;; Tilemap of level 1 and the view that draws it (the whole map, no scrolling).
FWK_TILEMAP_DESCRIPTOR platformer_map_descriptor, platformer_map, _pfe_types, PLATFORMER_MAP_WIDTH, PLATFORMER_MAP_HEIGHT, 2, 3, 4, 8, 4
FWK_TILE_RENDER_DESCRIPTOR platformer_view, platformer_tileset, 0, 0, 0, 0, PLATFORMER_MAP_WIDTH, PLATFORMER_MAP_HEIGHT, 4
; The second map has the same size, so it is drawn with the same view.
FWK_TILEMAP_DESCRIPTOR platformer_map2_descriptor, platformer_map2, _pfe_types, PLATFORMER_MAP2_WIDTH, PLATFORMER_MAP2_HEIGHT, 2, 3, 4, 8, 4
;; Platform physics: world width (bytes), ground y (lines), gravity per tick, max fall speed.
FWK_PLATFORM_CONFIG platformer_config, 80, 255, 1, 8

;; Key bindings: (key, action bit) pairs ended by a zero key.
platformer_bindings:
    .dw Key_CursorLeft
    .db PFE_INPUT_LEFT
    .dw Key_CursorRight
    .db PFE_INPUT_RIGHT
    .dw Key_CursorUp
    .db PFE_INPUT_JUMP
    .dw 0
    .db 0

;; Animation descriptors: frame count, ticks per frame, then the frame sprites.
;; The horizontal and right vertical enemies run every 2nd iteration, so their
;; animation also advances every 2nd iteration and gets half the ticks.
_pfe_anim_player: .db 2, PFE_ANIM_TICKS
    .dw platformer_player_pixels, platformer_player_pixels2
_pfe_anim_enemy: .db 2, PFE_ANIM_TICKS
    .dw platformer_enemy_pixels, platformer_enemy_pixels2
_pfe_anim_enemy_slow: .db 2, PFE_ANIM_TICKS_SLOW
    .dw platformer_enemy_pixels, platformer_enemy_pixels2

;; Enemy patrol programs for the behavior system. Horizontal: right for 19 ticks,
;; then left and right in legs of 23 (x 36 to 54). Vertical: down and up in legs
;; of 49 ticks at 2 px per tick (y 56 to 152).
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

;; Spawn rows (see PFE_ROW): components, type, x, y, width and height in bytes and
;; lines, sprite, background buffer, buffer size, behavior program, animation,
;; cadence byte.
;; The player spawns airborne at the left and falls to the floor; enemies patrol; coins and the door are static.
_pfe_row_player: PFE_ROW PFE_PLAYER_COMPS, PFE_T_PLAYER, 16, 184, 8, 8, platformer_player_pixels, _pfe_bg_player, 64, 0, _pfe_anim_player, 0
_pfe_row_h:      PFE_ROW PFE_ENEMY_COMPS, PFE_T_ENEMY, 36, 122, 4, 8, platformer_enemy_pixels, _pfe_bg_h, 32, _pfe_program_h, _pfe_anim_enemy_slow, PFE_CAD_ODD
_pfe_row_v:      PFE_ROW PFE_ENEMY_COMPS, PFE_T_ENEMY, 64, 56, 4, 8, platformer_enemy_pixels, _pfe_bg_v, 32, _pfe_program_v, _pfe_anim_enemy_slow, PFE_CAD_EVEN
_pfe_row_v2:     PFE_ROW PFE_ENEMY_COMPS, PFE_T_ENEMY, 8, 56, 4, 8, platformer_enemy_pixels, _pfe_bg_v2, 32, _pfe_program_v, _pfe_anim_enemy, 0
_pfe_row_coin0:  PFE_ROW PFE_ITEM_COMPS, PFE_T_COIN, 16, 24, 4, 8, platformer_coin_pixels, _pfe_bg_coin0, 32, 0, 0, 0
_pfe_row_coin1:  PFE_ROW PFE_ITEM_COMPS, PFE_T_COIN, 56, 24, 4, 8, platformer_coin_pixels, _pfe_bg_coin1, 32, 0, 0, 0
_pfe_row_coin2:  PFE_ROW PFE_ITEM_COMPS, PFE_T_COIN, 16, 168, 4, 8, platformer_coin_pixels, _pfe_bg_coin2, 32, 0, 0, 0
_pfe_row_coin3:  PFE_ROW PFE_ITEM_COMPS, PFE_T_COIN, 56, 168, 4, 8, platformer_coin_pixels, _pfe_bg_coin3, 32, 0, 0, 0
_pfe_row_door:   PFE_ROW PFE_ITEM_COMPS, PFE_T_DOOR, 72, 160, 4, 8, platformer_door_pixels, _pfe_bg_door, 32, 0, 0, 0

.area _CODE

_pfe_fail:
    ld (platformer_status), a
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
    inc hl
    ld (_pfe_anim), de
    ld a, (hl)
    ld ECS_E_CADENCE(iy), a
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
    ld a, (platformer_score)
    inc a
    ld (platformer_score), a
    ld hl, #platformer_hud_dirty
    set 0, (hl)
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
    ld a, (platformer_lives)
    or a
    jr z, _pfe_cb_ok
    dec a
    ld (platformer_lives), a
    ld hl, #platformer_hud_dirty
    set 1, (hl)
    set 3, (hl)
    xor a
    ret

;; Player against the coins and the door, then against the enemies. Enemies are
;; the BEHAVIOR entities and share one contact channel, so a life is lost when
;; the player starts touching an enemy, not every frame. Once all coins are
;; taken enemies stop hurting.
_pfe_collisions:
    ld iy, (platformer_player)
    ld ix, #platformer_manager
    ld bc, #ECS_C_COLLISION
    ld hl, #_pfe_items_cb
    ld e, #0
    call fwk_ecs_collide
    call _pfe_expect_ok
    ;; The last coin wins before enemies are checked, as in the original: no life
    ;; is lost in the frame that takes it (_pfe_all_coins is not yet in `won`).
    ld a, (platformer_won)
    ld hl, #_pfe_all_coins
    or (hl)
    ret nz
    ld iy, (platformer_player)
    ld ix, #platformer_manager
    ld bc, #ECS_C_COLLISION | ECS_C_BEHAVIOR
    ld hl, #_pfe_enemy_cb
    ld e, #PFE_CH_ENEMY
    call fwk_ecs_collide
    jp _pfe_expect_ok

;; Rules that change entity states cannot run inside a traversal: they are
;; applied here, after the collision passes.
_pfe_apply_events:
    ld a, (_pfe_all_coins)
    or a
    jr z, _pfe_no_win
    xor a
    ld (_pfe_all_coins), a
    inc a
    ld (platformer_won), a
    ld hl, #platformer_hud_dirty
    set 0, (hl)
    set 2, (hl)
    ld ix, #platformer_manager
    ld iy, (platformer_door)
    call fwk_ecs_entity_enable
    call _pfe_expect_ok
_pfe_no_win:
    ld a, (_pfe_door_hit)
    or a
    ret z
    ld a, (platformer_level)
    or a
    jr nz, _pfe_door_end
    inc a
    ld (platformer_level), a
    ld hl, #platformer_map2_descriptor
    ld (_pfe_map_desc), hl
    ld hl, #platformer_map2_packed + PLATFORMER_MAP2_PACKED_SIZE - 1
    ld de, #platformer_map2 + PLATFORMER_MAP2_SIZE - 1
    call fwk_zx7b_unpack
    jp _pfe_start_level                    ; same reset as the first start
_pfe_door_end:
    xor a
    ld (_pfe_door_hit), a
    ld (platformer_won), a
    ld ix, #platformer_manager
    ld iy, (platformer_door)
    call fwk_ecs_entity_disable
    jp _pfe_expect_ok

;; ---- HUD -------------------------------------------------------------------
;; In: B=first tile column, C=column after the last, IY=string. Restores the map
;; under the two tile rows of the text, then draws the string at byte x=4*B.
_pfe_hud_field:
    ld a, b
    ld (_pfe_hud_col), a
    add a, a
    add a, a
    ld (_pfe_hud_x), a
    ld a, c
    ld (_pfe_hud_end), a
    push iy
_pfe_hud_cell:
    ld b, #1
    call _pfe_hud_restore
    ld b, #2
    call _pfe_hud_restore
    ld hl, #_pfe_hud_col
    inc (hl)
    ld a, (_pfe_hud_end)
    cp (hl)
    jr nz, _pfe_hud_cell
    ld hl, #PFE_HUD_Y
    ld a, (_pfe_hud_x)
    ld c, a
    call fwk_video_get_ptr
    pop iy
    jp fwk_text_draw

;; In: B=tile row; the column is _pfe_hud_col.
_pfe_hud_restore:
    ld ix, (_pfe_map_desc)
    ld iy, #platformer_view            ; both maps are 20x25
    ld a, (_pfe_hud_col)
    ld c, a
    call fwk_tilemap_render_cell
    ret nc
    ld a, #0xEF
    jp _pfe_fail

_pfe_hud_score:
    ld iy, #_pfe_str_all
    ld a, (platformer_score)
    cp #PFE_WIN_SCORE
    jr z, _pfe_hud_score_draw
    add a, #'0'
    ld (_pfe_str_score + 7), a
    ld iy, #_pfe_str_score
_pfe_hud_score_draw:
    ld bc, #0x0005
    jr _pfe_hud_field

_pfe_hud_hint:
    ld iy, #_pfe_str_hint
    ld a, (platformer_won)
    or a
    jr z, _pfe_hud_hint_draw
    ld iy, #_pfe_str_go
_pfe_hud_hint_draw:
    ld bc, #0x060F
    jr _pfe_hud_field

_pfe_hud_lives:
    ld a, (platformer_lives)
    ld b, #'0'
    cp #10
    jr c, _pfe_hud_lives_units
    ld b, #'1'
    sub #10
_pfe_hud_lives_units:
    add a, #'0'
    ld (_pfe_str_life + 7), a
    ld a, b
    ld (_pfe_str_life + 6), a
    ld iy, #_pfe_str_life
    ld bc, #0x1014
    jp _pfe_hud_field

;; Redraws the fields flagged in platformer_hud_dirty. Losing a life also flashes the
;; border red three times, as in the original (blocking, about 0.2 s).
_pfe_hud_update:
    ld a, (platformer_hud_dirty)
    ld (_pfe_hud_pending), a
    or a
    ret z
    xor a
    ld (platformer_hud_dirty), a
    ld a, (_pfe_hud_pending)
    bit 0, a
    call nz, _pfe_hud_score
    ld a, (_pfe_hud_pending)
    bit 2, a
    call nz, _pfe_hud_hint
    ld a, (_pfe_hud_pending)
    bit 1, a
    call nz, _pfe_hud_lives
    ld a, (_pfe_hud_pending)
    bit 3, a
    ret z
    ld b, #PFE_FLASH_COUNT
_pfe_flash:
    push bc
    ld h, #PFE_BORDER_RED
    call _pfe_border
    ld h, #PFE_BORDER_BLACK
    call _pfe_border
    pop bc
    djnz _pfe_flash
    ret

;; In: H=hardware colour. Sets the border, then waits.
_pfe_border:
    ld l, #PFE_BORDER_PEN
    call cpct_setPALColour_asm
    ld de, #PFE_FLASH_DELAY
_pfe_border_wait:
    dec de
    ld a, d
    or e
    jr nz, _pfe_border_wait
    ret

;; Starts the current level: draws its map and HUD, clears the managers and
;; spawns every entity from the rows. Used at boot and when the door leads to
;; the second level, so both begin in exactly the same state. Lives are kept.
_pfe_start_level:
    ld ix, (_pfe_map_desc)
    ld iy, #platformer_view            ; both maps are 20x25
    call fwk_tilemap_render_view
    call _pfe_expect_ok
    xor a
    ld (platformer_score), a
    ld (platformer_won), a
    ld (_pfe_all_coins), a
    ld (_pfe_door_hit), a
    ld (fwk_ecs_tick), a
    ld a, #PFE_HUD_SCORE | PFE_HUD_LIVES | PFE_HUD_HINT
    ld (platformer_hud_dirty), a
    call _pfe_hud_update

    ld ix, #platformer_manager
    call fwk_ecs_manager_init
    call _pfe_expect_ok

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
    ld de, #platformer_door
    call _pfe_spawn_to
    ld iy, (platformer_door)
    call fwk_ecs_entity_disable            ; the door appears after the last coin
    call _pfe_expect_ok

    ld hl, #_pfe_row_player
    ld de, #platformer_player
    call _pfe_spawn_to
    ld iy, (platformer_player)
    ld ECS_E_INPUT_ACTION_MASK(iy), #PFE_INPUT_LEFT | PFE_INPUT_RIGHT | PFE_INPUT_JUMP
    ld ECS_E_PLATFORM_CONFIG(iy), #<platformer_config
    ld ECS_E_PLATFORM_CONFIG+1(iy), #>platformer_config
    ld hl, (_pfe_map_desc)
    ld ECS_E_PLATFORM_TILEMAP(iy), l
    ld ECS_E_PLATFORM_TILEMAP+1(iy), h
    ld ECS_E_MOTION_FLAGS(iy), #FWK_PLATFORM_AIRBORNE
    ld hl, #_pfe_row_v2
    call _pfe_spawn
    call _pfe_expect_ok
    ld hl, #_pfe_row_h
    ld de, #platformer_enemy_h
    call _pfe_spawn_to
    ld hl, #_pfe_row_v
    ld de, #platformer_enemy_v
    call _pfe_spawn_to

    ld a, #0x5A
    ld (platformer_status), a
    ret

_main::
    call fwk_project_init
    ld hl, #platformer_map_packed + PLATFORMER_MAP_PACKED_SIZE - 1
    ld de, #platformer_map + PLATFORMER_MAP_SIZE - 1
    call fwk_zx7b_unpack
    call fwk_video_init
    call fwk_text_init
    ld hl, #platformer_palette
    ld de, #PLATFORMER_PALETTE_SIZE
    call cpct_setPalette_asm
    call fwk_input_init
    ld hl, #platformer_bindings
    call fwk_input_set_bindings
    xor a
    call fwk_video_clear_visible
    call _pfe_start_level

platformer_frame:
    ld hl, #fwk_ecs_tick               ; one tick per loop iteration, for the cadence bytes
    inc (hl)
    call fwk_input_update
    ld a, (fwk_input_held)
    ld (platformer_input_witness), a
    ld ix, #platformer_manager
    call fwk_ecs_system_behavior
    call _pfe_expect_ok
    ld ix, #platformer_manager
    call fwk_ecs_system_input
    call _pfe_expect_ok
    ld iy, (platformer_player)
    ld a, ECS_E_MOTION_VELOCITY_X(iy)
    ld (platformer_input_witness+1), a
    ld ix, #platformer_manager
    call fwk_ecs_system_platform
    call _pfe_expect_ok
    ld ix, #platformer_manager
    call fwk_ecs_system_motion_u8
    call _pfe_expect_ok
    ld ix, #platformer_manager
    call fwk_ecs_system_animation
    call _pfe_expect_ok
    call _pfe_collisions
    call _pfe_apply_events
    ;; Selective render: find what changed before VSYNC, touch video RAM after it.
    ld ix, #platformer_scene
    call fwk_ecs_render_prepare
    call _pfe_expect_ok
    call fwk_system_wait_frame
    ld ix, #platformer_scene
    call fwk_ecs_render_restore
    call _pfe_expect_ok
    ld ix, #platformer_scene
    call fwk_ecs_render_draw
    call _pfe_expect_ok
    ;; Coins taken this frame have been erased: free their slots.
    ld ix, #platformer_manager
    call fwk_ecs_manager_collect
    call _pfe_expect_ok
    call _pfe_hud_update
    jp platformer_frame
