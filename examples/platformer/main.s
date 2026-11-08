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

;; Background pools: the renderer saves the screen bytes each sprite covers (width
;; in bytes * height in lines) in a buffer it takes from here when the entity is
;; first drawn. Eight 4x8 sprites (4 coins, door, 3 enemies) and one 8x8 (player).
FWK_ECS_RENDER_POOL platformer_pool32, 32, 8
FWK_ECS_RENDER_POOL platformer_pool64, 64, 1
_pfe_pools: .dw platformer_pool32, platformer_pool64

;; Render scene: the manager, the renderer's work area (8 bytes per renderable
;; entity, all nine at most) and the pools.
_pfe_managers: .dw platformer_manager
_pfe_work: .ds 8 * PFE_ALL_CAP
FWK_ECS_RENDER_SCENE platformer_scene, _pfe_managers, 1, _pfe_work, PFE_ALL_CAP, _pfe_pools, 2

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
;; then left and right in legs of 23 ticks (x 32 to 54). Vertical: down and up in legs
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
;; lines, sprite, behavior program, animation, cadence byte.
;; The player spawns airborne at the left and falls to the floor; enemies patrol; coins and the door are static.
_pfe_row_player: PFE_ROW PFE_PLAYER_COMPS, PFE_T_PLAYER, 16, 184, 8, 8, platformer_player_pixels, 0, _pfe_anim_player, 0
_pfe_row_h:      PFE_ROW PFE_ENEMY_COMPS, PFE_T_ENEMY, 36, 122, 4, 8, platformer_enemy_pixels, _pfe_program_h, _pfe_anim_enemy_slow, PFE_CAD_ODD
_pfe_row_v:      PFE_ROW PFE_ENEMY_COMPS, PFE_T_ENEMY, 64, 56, 4, 8, platformer_enemy_pixels, _pfe_program_v, _pfe_anim_enemy_slow, PFE_CAD_EVEN
_pfe_row_v2:     PFE_ROW PFE_ENEMY_COMPS, PFE_T_ENEMY, 8, 56, 4, 8, platformer_enemy_pixels, _pfe_program_v, _pfe_anim_enemy, 0
_pfe_row_coin0:  PFE_ROW PFE_ITEM_COMPS, PFE_T_COIN, 16, 24, 4, 8, platformer_coin_pixels, 0, 0, 0
_pfe_row_coin1:  PFE_ROW PFE_ITEM_COMPS, PFE_T_COIN, 56, 24, 4, 8, platformer_coin_pixels, 0, 0, 0
_pfe_row_coin2:  PFE_ROW PFE_ITEM_COMPS, PFE_T_COIN, 16, 168, 4, 8, platformer_coin_pixels, 0, 0, 0
_pfe_row_coin3:  PFE_ROW PFE_ITEM_COMPS, PFE_T_COIN, 56, 168, 4, 8, platformer_coin_pixels, 0, 0, 0
_pfe_row_door:   PFE_ROW PFE_ITEM_COMPS, PFE_T_DOOR, 72, 160, 4, 8, platformer_door_pixels, 0, 0, 0

.area _CODE

;; ----------------------------------------------------------------------------
;; _pfe_fail
;;   Fatal error stop: publishes the status byte and waits frames forever.
;;   In : A=value to publish (an ABI error code from _pfe_expect_ok, or 0xEF
;;        from _pfe_hud_restore).
;;   Out: platformer_status=A. Never returns.
;;   Clobbers: all (never returns)
;;   Notes: entered by jp only, so the stack of the failing caller is abandoned.
;;           Loops on fwk_system_wait_frame with interrupts untouched. A=0 reaches here only
;;           from a framework call that returns it unnormalised (fwk_ecs_collide maps a callback's
;;           A=0 with carry to ERR_CALLBACK, 0x09); that publishes 0, same as a game not started.
;; ----------------------------------------------------------------------------
_pfe_fail:
    ld (platformer_status), a
_pfe_fail_loop:
    call fwk_system_wait_frame
    jr _pfe_fail_loop

;; ----------------------------------------------------------------------------
;; _pfe_expect_ok
;;   Continues on success; on error stops the game with the ABI code in the
;;   status byte.
;;   In : carry and A as left by a framework call (carry set = error, A=code).
;;   Out: returns only with carry clear; A and every other register unchanged.
;;        On carry it never returns (jumps to _pfe_fail with A intact).
;;   Clobbers: none (HL is modified only on the error path, which never returns)
;;   Notes: on the error path it discards its own return address (pop hl) and does
;;           not rebalance the caller's stack. Call it right after the framework call,
;;           before any instruction that changes carry or A.
;; ----------------------------------------------------------------------------
;; ----------------------------------------------------------------------------
;; _pfe_spawn
;;   Builds a template entity from a PFE_ROW spawn row and creates it in the
;;   manager, then starts its animation if the row has one.
;;   In : IX=manager, HL=spawn row (14 bytes, layout of PFE_ROW).
;;   Out: carry clear, A=0 and IY=new entity; or carry set, A=ABI error, IY=0
;;        (fwk_ecs_entity_create contract). IX preserved.
;;   Clobbers: AF, BC, DE, HL, IY
;;   Notes: IX preserved. Overwrites _pfe_tpl and _pfe_anim. Tail-jumps to
;;           fwk_ecs_anim_set when the animation pointer is non-zero (it clobbers AF, DE,
;;           HL and preserves IX/IY). fwk_ecs_entity_create clobbers AF, BC, DE, HL. The
;;           template cadence byte must be valid or the create fails with a template
;;           error.
;; ----------------------------------------------------------------------------
_pfe_spawn:
    ; Zero the whole template: seed the first byte, then ldir it forward over itself.
    push hl
    ld hl, #_pfe_tpl
    ld de, #_pfe_tpl + 1
    ld (hl), #0
    ld bc, #ECS_ENTITY_SIZE - 1
    ldir
    pop hl                     ; HL = spawn row again
    ld iy, #_pfe_tpl
    ; Copy the row fields in PFE_ROW order, advancing HL through the row.
    ld a, (hl)                 ; component mask, low byte
    inc hl
    ld ECS_E_COMPONENTS(iy), a
    ld a, (hl)                 ; component mask, high byte
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
    ld a, (hl)                 ; sprite pointer, low byte
    inc hl
    ld ECS_E_RENDER_SPRITE(iy), a
    ld a, (hl)                 ; sprite pointer, high byte
    inc hl
    ld ECS_E_RENDER_SPRITE+1(iy), a
    ld a, (hl)                 ; behavior program pointer, low byte (0 = none)
    inc hl
    ld ECS_E_BEHAVIOR_PROGRAM(iy), a
    ld a, (hl)
    inc hl
    ld ECS_E_BEHAVIOR_PROGRAM+1(iy), a
    ; The animation descriptor is not a template field: keep it for after the create.
    ld e, (hl)
    inc hl
    ld d, (hl)
    inc hl
    ld (_pfe_anim), de
    ld a, (hl)                 ; cadence byte, last field of the row
    ld ECS_E_CADENCE(iy), a
    ld ECS_E_RENDER_FLAGS(iy), #ECS_RENDER_VISIBLE | ECS_RENDER_DIRTY
    ld ECS_E_RENDER_SORT_OFFSET_Y(iy), #8      ; sort by the feet, like the original
    ld hl, #_pfe_tpl
    call fwk_ecs_entity_create            ; IX=manager; IY = new slot on success
    ret c
    ; Start the animation on the new entity (IY), if the row named one.
    ld hl, (_pfe_anim)
    ld a, h
    or l
    ret z                      ; no animation: carry clear, A=0
    jp fwk_ecs_anim_set

;; ----------------------------------------------------------------------------
;; _pfe_spawn_to
;;   Spawns the row in HL into the manager in IX and stores the entity address
;;   in the 16-bit variable at (DE).
;;   In : IX=manager, HL=spawn row, DE=address of a 16-bit variable.
;;   Out: carry clear. (DE as given) holds the entity address, low byte first.
;;        IY=new entity, DE=entity address, HL=variable address + 1.
;;   Clobbers: AF, BC, DE, HL, IY
;;   Notes: IX preserved. Does not return on a create error (goes through
;;           _pfe_expect_ok to _pfe_fail).
;; ----------------------------------------------------------------------------
_pfe_spawn_to:
    push de                    ; keep the destination across the spawn
    call _pfe_spawn
    PFE_CHECK_OK
    pop hl                     ; HL = destination variable
    push iy
    pop de                     ; DE = entity address (IY cannot be stored directly)
    ld (hl), e
    inc hl
    ld (hl), d
    ret

;; ----------------------------------------------------------------------------
;; _pfe_items_cb
;;   Collision callback for the player against every collidable entity: takes a
;;   coin (score, HUD, win flag) or records a touch of the door. Other entities
;;   (the enemies also carry the collision component) are ignored.
;;   In : IX=manager, IY=target entity (0 on EXIT), HL=subject (unused),
;;        A=ECS_COLLISION_ENTER/STAY/EXIT.
;;   Out: carry clear and A=0 to keep walking; carry set and A=error code when
;;        marking the coin for destruction fails (stops the pass).
;;        IX and IY preserved.
;;   Clobbers: AF, BC, DE, HL (only AF on the EXIT, enemy and door paths)
;;   Notes: IX and IY preserved (pushed around fwk_ecs_entity_mark_destroy). Sets
;;           bit 0 (score) of platformer_hud_dirty per coin, sets _pfe_all_coins when the
;;           coin count reaches PFE_WIN_SCORE, sets _pfe_door_hit on the door. Runs inside
;;           a traversal, so it only marks the coin for destruction.
;; ----------------------------------------------------------------------------
_pfe_items_cb:
    cp #ECS_COLLISION_EXIT
    jr z, _pfe_cb_ok           ; EXIT carries no target (IY=0): nothing to do
    ld a, ECS_E_TYPE(iy)
    cp #PFE_T_DOOR
    jr z, _pfe_cb_door
    cp #PFE_T_COIN
    jr nz, _pfe_cb_ok          ; an enemy or any other type: not handled here
    ; Coin: destroy it (the callback must keep IX/IY, the framework call may not).
    push ix
    push iy
    call fwk_ecs_entity_mark_destroy
    pop iy
    pop ix
    ret c                      ; error: A=code, stop the pass
    ld a, (platformer_score)
    inc a
    ld (platformer_score), a
    ld hl, #platformer_hud_dirty
    set 0, (hl)                ; PFE_HUD_SCORE
    cp #PFE_WIN_SCORE
    jr nz, _pfe_cb_ok
    ld (_pfe_all_coins), a     ; last coin: any non-zero value flags the win
_pfe_cb_ok:
    xor a                      ; carry clear, A=0: continue
    ret
_pfe_cb_door:
    ld a, #1
    ld (_pfe_door_hit), a      ; the door is only ACTIVE (hence visited) once enabled
    xor a
    ret

;; ----------------------------------------------------------------------------
;; _pfe_enemy_cb
;;   Collision callback for the player against the enemies: costs one life when
;;   the contact starts and flags the HUD and the border flash.
;;   In : A=ECS_COLLISION_ENTER/STAY/EXIT. IX=manager, IY=target (0 on EXIT) and
;;        HL=subject are not used.
;;   Out: carry clear and A=0 always. IX, IY, BC and DE preserved.
;;   Clobbers: AF, HL (only AF unless a life is lost)
;;   Notes: IX, IY, BC and DE preserved. Only ENTER counts, so a continued contact
;;           costs nothing. Lives stop at 0 (no change, no flash). Sets bits 1 (lives) and
;;           3 (flash) of platformer_hud_dirty.
;; ----------------------------------------------------------------------------
_pfe_enemy_cb:
    cp #ECS_COLLISION_ENTER
    jr nz, _pfe_cb_ok
    ld a, (platformer_lives)
    or a
    jr z, _pfe_cb_ok           ; already at 0: never go below
    dec a
    ld (platformer_lives), a
    ld hl, #platformer_hud_dirty
    set 1, (hl)                ; PFE_HUD_LIVES
    set 3, (hl)                ; PFE_HUD_FLASH
    xor a
    ret

;; ----------------------------------------------------------------------------
;; _pfe_collisions
;;   Player against the coins and the door, then against the enemies. Enemies
;;   are the BEHAVIOR entities and share one contact channel, so a life is lost
;;   when the player starts touching an enemy, not every frame. Once all coins
;;   are taken enemies stop hurting.
;;   In : none. Reads platformer_player, platformer_won, _pfe_all_coins.
;;   Out: carry clear. Side effects of the callbacks: platformer_score,
;;        platformer_lives, platformer_hud_dirty, _pfe_all_coins, _pfe_door_hit.
;;   Clobbers: AF, BC, DE, HL, IX, IY
;;   Notes: does not return on a framework error (via _pfe_expect_ok). The enemy
;;           pass is skipped when the level is won or the last coin was just taken.
;; ----------------------------------------------------------------------------
_pfe_collisions:
    ; Pass 1: every collidable entity as a target, no contact channel (E=0).
    ld iy, (platformer_player)
    ld ix, #platformer_manager
    ld bc, #ECS_C_COLLISION
    ld hl, #_pfe_items_cb
    ld e, #0
    call fwk_ecs_collide
    PFE_CHECK_OK
    ;; The last coin wins before enemies are checked, as in the original: no life
    ;; is lost in the frame that takes it (_pfe_all_coins is not yet in `won`).
    ld a, (platformer_won)
    ld hl, #_pfe_all_coins
    or (hl)
    ret nz                     ; carry clear (or clears it): skip the enemy pass
    ; Pass 2: only BEHAVIOR entities (the enemies), on their own contact channel
    ; so ENTER fires once per touch.
    ld iy, (platformer_player)
    ld ix, #platformer_manager
    ld bc, #ECS_C_COLLISION | ECS_C_BEHAVIOR
    ld hl, #_pfe_enemy_cb
    ld e, #PFE_CH_ENEMY
    call fwk_ecs_collide
    ret nc
    jp _pfe_fail

;; ----------------------------------------------------------------------------
;; _pfe_apply_events
;;   Applies the rules that change entity states and cannot run inside a
;;   traversal: they are applied here, after the collision passes. A won level
;;   enables the door; touching the door starts level 2 or, on level 2, hides it.
;;   In : none. Reads _pfe_all_coins, _pfe_door_hit, platformer_level,
;;        platformer_door.
;;   Out: carry clear. May change platformer_won, platformer_level,
;;        _pfe_map_desc, platformer_map2 (unpacked), platformer_hud_dirty, and clears
;;        _pfe_all_coins and _pfe_door_hit; through _pfe_start_level, the whole level state.
;;   Clobbers: AF, BC, DE, HL, IX, IY
;;   Notes: does not return on a framework error. Tail-jumps to _pfe_start_level
;;           for the level change. fwk_zx7b_unpack clobbers AF, BC, DE, HL.
;; ----------------------------------------------------------------------------
_pfe_apply_events:
    ; Level won: consume the flag, show the door and ask for the HUD hint and score.
    ld a, (_pfe_all_coins)
    or a
    jr z, _pfe_no_win
    xor a
    ld (_pfe_all_coins), a
    inc a                      ; A = 1
    ld (platformer_won), a
    ld hl, #platformer_hud_dirty
    set 0, (hl)                ; PFE_HUD_SCORE
    set 2, (hl)                ; PFE_HUD_HINT
    ld ix, #platformer_manager
    ld iy, (platformer_door)
    call fwk_ecs_entity_enable
    PFE_CHECK_OK
_pfe_no_win:
    ; Door touched? Level 1 continues into level 2, level 2 only hides the door.
    ld a, (_pfe_door_hit)
    or a
    ret z
    ld a, (platformer_level)
    or a
    jr nz, _pfe_door_end
    inc a                      ; A = 1: second level
    ld (platformer_level), a
    ld hl, #platformer_map2_descriptor
    ld (_pfe_map_desc), hl
    ; ZX7B unpacks backwards: HL and DE point at the LAST byte of source and destination.
    ld hl, #platformer_map2_packed + PLATFORMER_MAP2_PACKED_SIZE - 1
    ld de, #platformer_map2 + PLATFORMER_MAP2_SIZE - 1
    call fwk_zx7b_unpack
    jp _pfe_start_level                    ; same reset as the first start
_pfe_door_end:
    ; Level 2 door: clear the flags (not restarting) and hide the door again.
    xor a
    ld (_pfe_door_hit), a
    ld (platformer_won), a
    ld ix, #platformer_manager
    ld iy, (platformer_door)
    call fwk_ecs_entity_disable
    ret nc
    jp _pfe_fail

;; ---- HUD -------------------------------------------------------------------
;; ----------------------------------------------------------------------------
;; _pfe_hud_field
;;   Restores the map under the two tile rows of the text, then draws the
;;   string at byte x=4*B.
;;   In : B=first tile column, C=column after the last, IY=NUL-terminated
;;        string. The field must satisfy B < C (the loop runs at least once).
;;   Out: none. Tail-jumps to fwk_text_draw, which returns to the caller.
;;   Clobbers: AF, BC, DE, HL, IX, IY
;;   Notes: fwk_text_draw documents AF, BC, DE, HL, IX, IY. Uses _pfe_hud_col,
;;           _pfe_hud_end and _pfe_hud_x as scratch. Does not return on a tile render
;;           error (_pfe_hud_restore).
;; ----------------------------------------------------------------------------
_pfe_hud_field:
    ld a, b
    ld (_pfe_hud_col), a
    add a, a
    add a, a                   ; 4 bytes per tile column
    ld (_pfe_hud_x), a
    ld a, c
    ld (_pfe_hud_end), a
    push iy                    ; the tile redraw clobbers IY; the string is needed later
_pfe_hud_cell:
    ; Redraw the map tile of this column in tile rows 1 and 2 (the text rows).
    ld b, #1
    call _pfe_hud_restore
    ld b, #2
    call _pfe_hud_restore
    ld hl, #_pfe_hud_col
    inc (hl)
    ld a, (_pfe_hud_end)
    cp (hl)
    jr nz, _pfe_hud_cell       ; until column == end
    ld hl, #PFE_HUD_Y          ; y in scanlines
    ld a, (_pfe_hud_x)
    ld c, a                    ; x in bytes
    call fwk_video_get_ptr
    pop iy                     ; IY = string, HL = screen address
    jp fwk_text_draw

;; ----------------------------------------------------------------------------
;; _pfe_hud_restore
;;   Redraws one map tile of the active level, wiping the HUD text under it.
;;   In : B=tile row. Reads _pfe_hud_col (tile column) and _pfe_map_desc.
;;   Out: carry clear; the tile is drawn on the visible screen.
;;   Clobbers: AF, BC, DE, HL, IX, IY
;;   Notes: fwk_tilemap_render_cell preserves IX/IY, but this routine reloads them.
;;           A render error stops the game with status 0xEF (jp _pfe_fail), so it never
;;           returns then.
;; ----------------------------------------------------------------------------
_pfe_hud_restore:
    ld ix, (_pfe_map_desc)
    ld iy, #platformer_view            ; both maps are 20x25
    ld a, (_pfe_hud_col)
    ld c, a
    call fwk_tilemap_render_cell
    ret nc
    ld a, #0xEF                ; status code for a failed HUD tile redraw
    jp _pfe_fail

;; ----------------------------------------------------------------------------
;; _pfe_hud_score
;;   Draws the score field: "COINS: n/4", or "ALL COINS" once the score is
;;   PFE_WIN_SCORE.
;;   In : none. Reads platformer_score.
;;   Out: none. Patches the digit of _pfe_str_score in place.
;;   Clobbers: AF, BC, DE, HL, IX, IY
;;   Notes: jumps to _pfe_hud_field, which returns to the caller.
;; ----------------------------------------------------------------------------
_pfe_hud_score:
    ld iy, #_pfe_str_all
    ld a, (platformer_score)
    cp #PFE_WIN_SCORE
    jr z, _pfe_hud_score_draw
    add a, #'0'
    ld (_pfe_str_score + 7), a ; offset 7 is the digit in "COINS: 0/4"
    ld iy, #_pfe_str_score
_pfe_hud_score_draw:
    ld bc, #0x0005             ; tile columns 0..4 (B=0 first, C=5 end)
    jr _pfe_hud_field

;; ----------------------------------------------------------------------------
;; _pfe_hud_hint
;;   Draws the hint field: "COLLECT ALL COINS", or "GO TO THE DOOR" once the
;;   level is won.
;;   In : none. Reads platformer_won.
;;   Out: none.
;;   Clobbers: AF, BC, DE, HL, IX, IY
;;   Notes: jumps to _pfe_hud_field, which returns to the caller.
;; ----------------------------------------------------------------------------
_pfe_hud_hint:
    ld iy, #_pfe_str_hint
    ld a, (platformer_won)
    or a
    jr z, _pfe_hud_hint_draw
    ld iy, #_pfe_str_go
_pfe_hud_hint_draw:
    ld bc, #0x060F             ; tile columns 6..14
    jr _pfe_hud_field

;; ----------------------------------------------------------------------------
;; _pfe_hud_lives
;;   Draws the lives field "LIFE: nn".
;;   In : none. Reads platformer_lives (0..19: the tens digit is only '0' or '1').
;;   Out: none. Patches both digits of _pfe_str_life in place.
;;   Clobbers: AF, BC, DE, HL, IX, IY
;;   Notes: jumps to _pfe_hud_field, which returns to the caller.
;; ----------------------------------------------------------------------------
_pfe_hud_lives:
    ld a, (platformer_lives)
    ld b, #'0'                 ; tens digit
    cp #10
    jr c, _pfe_hud_lives_units
    ld b, #'1'
    sub #10
_pfe_hud_lives_units:
    add a, #'0'
    ld (_pfe_str_life + 7), a  ; units digit ("LIFE: 10", offset 7)
    ld a, b
    ld (_pfe_str_life + 6), a  ; tens digit
    ld iy, #_pfe_str_life
    ld bc, #0x1014             ; tile columns 16..19
    jp _pfe_hud_field

;; ----------------------------------------------------------------------------
;; _pfe_hud_update
;;   Redraws the fields flagged in platformer_hud_dirty. Losing a life also
;;   flashes the border red three times, as in the original (blocking, about
;;   0.2 s).
;;   In : none. Reads platformer_hud_dirty (PFE_HUD_* bits).
;;   Out: none. platformer_hud_dirty cleared; _pfe_hud_pending holds the bits
;;        that were handled.
;;   Clobbers: AF, BC, DE, HL, IX, IY (only AF when nothing is dirty)
;;   Notes: returns at once when nothing is dirty. The flag byte is cleared before
;;           drawing, so a draw cannot lose a bit set meanwhile. Border flash is a busy
;;           wait of 6 delay loops.
;; ----------------------------------------------------------------------------
_pfe_hud_update:
    ld a, (platformer_hud_dirty)
    ld (_pfe_hud_pending), a   ; work on a snapshot, the callees clobber A
    or a
    ret z
    xor a
    ld (platformer_hud_dirty), a
    ld a, (_pfe_hud_pending)
    bit 0, a                   ; PFE_HUD_SCORE
    call nz, _pfe_hud_score
    ld a, (_pfe_hud_pending)
    bit 2, a                   ; PFE_HUD_HINT
    call nz, _pfe_hud_hint
    ld a, (_pfe_hud_pending)
    bit 1, a                   ; PFE_HUD_LIVES
    call nz, _pfe_hud_lives
    ld a, (_pfe_hud_pending)
    bit 3, a                   ; PFE_HUD_FLASH
    ret z
    ld b, #PFE_FLASH_COUNT
_pfe_flash:
    push bc                    ; _pfe_border clobbers B
    ld h, #PFE_BORDER_RED
    call _pfe_border
    ld h, #PFE_BORDER_BLACK
    call _pfe_border
    pop bc
    djnz _pfe_flash
    ret

;; ----------------------------------------------------------------------------
;; _pfe_border
;;   Sets the border colour, then waits a fixed busy-wait delay.
;;   In : H=hardware colour for the border pen.
;;   Out: border pen PFE_BORDER_PEN set to H. Returns after PFE_FLASH_DELAY
;;        loop iterations.
;;   Clobbers: AF, B, DE, L
;;   Notes: H and C preserved (cpct_setPALColour_asm documents AF, B destroyed).
;;           The delay does not depend on VSYNC.
;; ----------------------------------------------------------------------------
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

;; ----------------------------------------------------------------------------
;; _pfe_start_level
;;   Starts the current level: draws its map and HUD, clears the managers and
;;   spawns every entity from the rows. Used at boot and when the door leads to
;;   the second level, so both begin in exactly the same state. Lives are kept.
;;   In : none. Reads _pfe_map_desc (active tilemap).
;;   Out: carry clear. Score, won, _pfe_all_coins, _pfe_door_hit and
;;        fwk_ecs_tick reset to 0; HUD redrawn; four coins, the door (disabled),
;;        the player and three enemies created; platformer_player, _door,
;;        _enemy_h and _enemy_v set; platformer_status=0x5A.
;;   Clobbers: AF, BC, DE, HL, IX, IY
;;   Notes: does not return on a framework error (via _pfe_expect_ok). Leaves
;;           platformer_lives and platformer_level untouched. Draws on the visible screen
;;           (blocking). It overwrites platformer_hud_dirty with SCORE|LIVES|HINT, so no border
;;           flash happens here and any pending FLASH bit is dropped.
;; ----------------------------------------------------------------------------
_pfe_start_level:
    ; Draw the map of the active level over the whole screen (wipes old sprites).
    ld ix, (_pfe_map_desc)
    ld iy, #platformer_view            ; both maps are 20x25
    call fwk_tilemap_render_view
    PFE_CHECK_OK
    ; Reset the state of the level; A=0 is also stored in the cadence tick.
    xor a
    ld (platformer_score), a
    ld (platformer_won), a
    ld (_pfe_all_coins), a
    ld (_pfe_door_hit), a
    ld (fwk_ecs_tick), a
    ld a, #PFE_HUD_SCORE | PFE_HUD_LIVES | PFE_HUD_HINT
    ld (platformer_hud_dirty), a
    call _pfe_hud_update

    ; Empty the manager and give the renderer's background buffers back.
    ld ix, #platformer_manager
    call fwk_ecs_manager_init
    PFE_CHECK_OK
    ld ix, #platformer_scene               ; the old entities vanished unrestored:
    call fwk_ecs_render_reset              ; give their background buffers back
    PFE_CHECK_OK
    ld ix, #platformer_manager             ; the spawns below take IX=manager

    ; Spawn in storage order: 0..3 coins, 4 door, 5 player, 6 left vertical
    ; enemy, 7 horizontal enemy, 8 right vertical enemy.
    ld hl, #_pfe_row_coin0
    call _pfe_spawn
    PFE_CHECK_OK
    ld hl, #_pfe_row_coin1
    call _pfe_spawn
    PFE_CHECK_OK
    ld hl, #_pfe_row_coin2
    call _pfe_spawn
    PFE_CHECK_OK
    ld hl, #_pfe_row_coin3
    call _pfe_spawn
    PFE_CHECK_OK
    ld hl, #_pfe_row_door
    ld de, #platformer_door
    call _pfe_spawn_to
    ld iy, (platformer_door)
    call fwk_ecs_entity_disable            ; the door appears after the last coin
    PFE_CHECK_OK

    ; Player: the row cannot hold the platform fields, so set them on the new entity.
    ld hl, #_pfe_row_player
    ld de, #platformer_player
    call _pfe_spawn_to
    ld iy, (platformer_player)
    ld ECS_E_INPUT_ACTION_MASK(iy), #PFE_INPUT_LEFT | PFE_INPUT_RIGHT | PFE_INPUT_JUMP
    ld ECS_E_PLATFORM_CONFIG(iy), #<platformer_config
    ld ECS_E_PLATFORM_CONFIG+1(iy), #>platformer_config
    ld hl, (_pfe_map_desc)                 ; physics collides with the active map
    ld ECS_E_PLATFORM_TILEMAP(iy), l
    ld ECS_E_PLATFORM_TILEMAP+1(iy), h
    ld ECS_E_MOTION_FLAGS(iy), #FWK_PLATFORM_AIRBORNE   ; starts in the air and falls
    ; Enemies. The left vertical one needs no pointer; the other two are tracked.
    ld hl, #_pfe_row_v2
    call _pfe_spawn
    PFE_CHECK_OK
    ld hl, #_pfe_row_h
    ld de, #platformer_enemy_h
    call _pfe_spawn_to
    ld hl, #_pfe_row_v
    ld de, #platformer_enemy_v
    call _pfe_spawn_to

    ld a, #0x5A                ; smoke marker: the level is ready
    ld (platformer_status), a
    ret

;; ----------------------------------------------------------------------------
;; _main
;;   Program entry. Initialises the framework, video, text, palette and input,
;;   starts level 1 and runs the frame loop forever.
;;   In : none.
;;   Out: none. Never returns.
;;   Clobbers: all (never returns)
;;   Notes: the frame loop (platformer_frame) runs one tick per iteration: input,
;;           behavior, input system, platform physics, motion, animation, collisions,
;;           events, then the selective render (prepare before VSYNC, restore and draw
;;           after it), slot collection and the HUD. platformer_input_witness is written
;;           for the emulator smoke.
;; ----------------------------------------------------------------------------
_main::
    call fwk_project_init
    ; Level 1 map: unpack the ZX7B data into its RAM buffer (backwards, ends first).
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

    ; ---- Frame loop: one iteration per game frame, never leaves ----
platformer_frame:
    ld hl, #fwk_ecs_tick               ; one tick per loop iteration, for the cadence bytes
    inc (hl)
    call fwk_input_update
    ld a, (fwk_input_held)
    ld (platformer_input_witness), a   ; actions held, for the smoke
    ; Systems in order: behavior (enemy programs), input, physics, motion, animation.
    ld ix, #platformer_manager
    call fwk_ecs_system_behavior
    PFE_CHECK_OK
    ld ix, #platformer_manager
    call fwk_ecs_system_input
    PFE_CHECK_OK
    ld iy, (platformer_player)
    ld a, ECS_E_MOTION_VELOCITY_X(iy)
    ld (platformer_input_witness+1), a ; player X velocity after the input system
    ld ix, #platformer_manager
    call fwk_ecs_system_platform
    PFE_CHECK_OK
    ld ix, #platformer_manager
    call fwk_ecs_system_motion_u8
    PFE_CHECK_OK
    ld ix, #platformer_manager
    call fwk_ecs_system_animation
    PFE_CHECK_OK
    ; Game rules on the new positions.
    call _pfe_collisions
    call _pfe_apply_events
    ;; Selective render: find what changed before VSYNC, touch video RAM after it.
    ld ix, #platformer_scene
    call fwk_ecs_render_prepare
    PFE_CHECK_OK
    call fwk_system_wait_frame
    ld ix, #platformer_scene
    call fwk_ecs_render_restore
    PFE_CHECK_OK
    ld ix, #platformer_scene
    call fwk_ecs_render_draw
    PFE_CHECK_OK
    ;; Coins taken this frame have been erased: free their slots.
    ld ix, #platformer_manager
    call fwk_ecs_manager_collect
    PFE_CHECK_OK
    call _pfe_hud_update
    jp platformer_frame
