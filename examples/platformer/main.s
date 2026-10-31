.module example_platformer
.include "cpctelera.h.s"
.include "video/entity_render.inc"
.include "extensions/platform_tilemap.inc"
.include "game/game.inc"

.globl fwk_project_init, fwk_system_wait_frame, fwk_system_frame_count
.globl fwk_video_init, fwk_video_clear_visible, fwk_video_get_ptr
.globl fwk_input_init, fwk_input_set_bindings, fwk_input_update
.globl fwk_input_held, fwk_input_pressed
.globl fwk_physics_platform_step, fwk_platform_tilemap_resolve
.globl fwk_tilemap_render_view, fwk_tilemap_render_cell
.globl fwk_entity_render_init, fwk_entity_render_prepare_dirty
.globl fwk_entity_render_restore_dirty, fwk_entity_render_draw_dirty
.globl fwk_text_init, fwk_text_set_color, fwk_text_draw
.globl cpct_setPALColour_asm
.globl platformer_map_descriptor, platformer_view, platformer_config
.globl platformer_player_pixels, platformer_player_pixels2, platformer_coin_pixels, platformer_enemy_pixels, platformer_enemy_pixels2, platformer_door_pixels
.globl platformer_bindings, platformer_coins
.globl platformer_status, platformer_score, platformer_player

.area _DATA

;; Public state doubles as a small observable contract for emulator tests.
platformer_status::         .db 0
platformer_score::          .db 0
platformer_lives::          .db PF_LIVES_INITIAL
platformer_last_collision:: .db 0
platformer_hud_dirty::      .db 1
platformer_enemy_contacts:: .db 0

_platformer_enemy_contacts_next: .db 0
_platformer_enemy_h_dx: .db 1
_platformer_enemy_v_dy: .db 1
_platformer_enemy_v2_dy: .db 1
_platformer_enemy_phase: .db 0

platformer_player_background::
    .ds PF_PLAYER_WIDTH_BYTES * PF_PLAYER_HEIGHT_PX
platformer_coin0_background: .ds 4 * 8
platformer_coin1_background: .ds 4 * 8
platformer_coin2_background: .ds 4 * 8
platformer_coin3_background: .ds 4 * 8
platformer_enemy_h_background: .ds PF_ENEMY_WIDTH_BYTES * PF_ENEMY_HEIGHT_PX
platformer_enemy_v_background: .ds PF_ENEMY_WIDTH_BYTES * PF_ENEMY_HEIGHT_PX
platformer_enemy_v2_background: .ds PF_ENEMY_WIDTH_BYTES * PF_ENEMY_HEIGHT_PX
platformer_door_background: .ds 4 * 8

platformer_player_entity::
platformer_player_sprite::
    FWK_ENTITY_RENDER_PREFIX platformer_player_pixels, PF_PLAYER_START_X, PF_PLAYER_START_Y, PF_PLAYER_WIDTH_BYTES, PF_PLAYER_HEIGHT_PX, PF_PLAYER_START_Y+PF_PLAYER_HEIGHT_PX, platformer_player_background, PF_PLAYER_WIDTH_BYTES*PF_PLAYER_HEIGHT_PX, FWK_ENTITY_RENDER_VISIBLE, 0, 0
platformer_player:: .ds PF_PLAYER_SIZE

platformer_coin0_entity::
    FWK_ENTITY_RENDER_PREFIX platformer_coin_pixels, 16, 24, 4, 8, 32, platformer_coin0_background, 32, FWK_ENTITY_RENDER_VISIBLE, 0, 0
platformer_coin1_entity::
    FWK_ENTITY_RENDER_PREFIX platformer_coin_pixels, 56, 24, 4, 8, 32, platformer_coin1_background, 32, FWK_ENTITY_RENDER_VISIBLE, 0, 0
platformer_coin2_entity::
    FWK_ENTITY_RENDER_PREFIX platformer_coin_pixels, 16, 168, 4, 8, 176, platformer_coin2_background, 32, FWK_ENTITY_RENDER_VISIBLE, 0, 0
platformer_coin3_entity::
    FWK_ENTITY_RENDER_PREFIX platformer_coin_pixels, 56, 168, 4, 8, 176, platformer_coin3_background, 32, FWK_ENTITY_RENDER_VISIBLE, 0, 0
platformer_enemy_h_entity::
    FWK_ENTITY_RENDER_PREFIX platformer_enemy_pixels, PF_ENEMY_H_START_X, PF_ENEMY_H_Y, PF_ENEMY_WIDTH_BYTES, PF_ENEMY_HEIGHT_PX, PF_ENEMY_H_Y+PF_ENEMY_HEIGHT_PX, platformer_enemy_h_background, PF_ENEMY_WIDTH_BYTES*PF_ENEMY_HEIGHT_PX, FWK_ENTITY_RENDER_VISIBLE, 0, 0
platformer_enemy_v_entity::
    FWK_ENTITY_RENDER_PREFIX platformer_enemy_pixels, PF_ENEMY_V_X, PF_ENEMY_V_START_Y, PF_ENEMY_WIDTH_BYTES, PF_ENEMY_HEIGHT_PX, PF_ENEMY_V_START_Y+PF_ENEMY_HEIGHT_PX, platformer_enemy_v_background, PF_ENEMY_WIDTH_BYTES*PF_ENEMY_HEIGHT_PX, FWK_ENTITY_RENDER_VISIBLE, 0, 0
platformer_enemy_v2_entity::
    FWK_ENTITY_RENDER_PREFIX platformer_enemy_pixels, 8, PF_ENEMY_V_START_Y, PF_ENEMY_WIDTH_BYTES, PF_ENEMY_HEIGHT_PX, PF_ENEMY_V_START_Y+PF_ENEMY_HEIGHT_PX, platformer_enemy_v2_background, PF_ENEMY_WIDTH_BYTES*PF_ENEMY_HEIGHT_PX, FWK_ENTITY_RENDER_VISIBLE, 0, 0
platformer_door_entity::
    FWK_ENTITY_RENDER_PREFIX platformer_door_pixels, 144, 160, 4, 8, 168, platformer_door_background, 32, 0, 0, 0

platformer_render_entities:
    .dw platformer_player_entity, platformer_coin0_entity, platformer_coin1_entity
    .dw platformer_coin2_entity, platformer_coin3_entity
    .dw platformer_enemy_h_entity, platformer_enemy_v_entity, platformer_enemy_v2_entity, platformer_door_entity
platformer_render_work: .ds PF_RENDER_COUNT * FWK_ENTITY_RENDER_WORK_SIZE
FWK_ENTITY_RENDER_DESCRIPTOR platformer_render_list, platformer_render_entities, PF_RENDER_COUNT, platformer_render_work, PF_RENDER_COUNT

platformer_score_str:: .ascii "COINS: 0/4"
    .db 0
platformer_score_digit_str: .ascii "0"
    .db 0
platformer_life_str:: .ascii "LIFE: 10"
    .db 0
platformer_life_digits_str: .ascii "10"
    .db 0
platformer_win_str:: .ascii "ALL COINS! YOU WIN"
    .db 0

_platformer_hud_column: .db 0
_platformer_hud_pending: .db 0
_pf_anim_timer: .db 0
_pf_anim_frame: .db 0
platformer_fps:: .db 0
platformer_fps_frames:: .db 0
platformer_fps_last_count:: .dw 0

.area _CODE

_main::
    call _pf_init_framework
    call _pf_reset_game
    call _pf_render_scene

_platformer_loop:
    call fwk_input_update
    ld a, (_pf_anim_timer)
    inc a
    cp #8
    jr c, _pf_anim_store
    xor a
    ld (_pf_anim_timer), a
    ld a, (_pf_anim_frame)
    xor #1
    ld (_pf_anim_frame), a
    jr _pf_anim_done
_pf_anim_store:
    ld (_pf_anim_timer), a
_pf_anim_done:
    call _pf_read_controls
    call _pf_update_player
    call _pf_update_enemies
    call _pf_update_enemy_v2
    call _pf_sync_player_render
    call _pf_collect_coins
    call _pf_check_door
    call _pf_check_enemy_contacts

    ;; Validate, close overlaps and build the restore order before VSYNC. The
    ;; post-VSYNC section is the shortest possible VRAM commit.
    call _pf_prepare_dirty
    call fwk_system_wait_frame
    call _pf_restore_dirty
    call _pf_draw_dirty
    ld a, (platformer_fps_frames)
    inc a
    ld (platformer_fps_frames), a
    ld hl, (fwk_system_frame_count)
    ld de, (platformer_fps_last_count)
    or a
    sbc hl, de
    ld a, h
    or a
    jr nz, _pf_fps_update
    ld a, l
    cp #50
    jr c, _pf_fps_skip
_pf_fps_update:
    ld a, (platformer_fps_frames)
    ld (platformer_fps), a
    xor a
    ld (platformer_fps_frames), a
    ld hl, (fwk_system_frame_count)
    ld (platformer_fps_last_count), hl
_pf_fps_skip:
    ld a, (platformer_hud_dirty)
    or a
    call nz, _pf_update_hud
    jp _platformer_loop

;; Framework and palette setup are kept separate from game state so the order
;; required by the text module is obvious in the tutorial.
_pf_init_framework:
    call fwk_project_init
    call fwk_video_init
    call fwk_text_init

    ld l, #0
    ld h, #0x14
    call cpct_setPALColour_asm
    ld l, #5
    ld h, #0x0A
    call cpct_setPALColour_asm
    ld l, #10
    ld h, #0x18
    call cpct_setPALColour_asm
    ld l, #15
    ld h, #0x13
    call cpct_setPALColour_asm
    xor a
    call fwk_text_set_color
    xor a
    call fwk_video_clear_visible

    call fwk_input_init
    ld hl, #platformer_bindings
    jp fwk_input_set_bindings

_pf_reset_game:
    ld a, #PF_PLAYER_START_X
    ld (platformer_player+PF_PLAYER_X), a
    ld a, #PF_PLAYER_START_Y
    ld (platformer_player+PF_PLAYER_Y), a
    xor a
    ld (platformer_player+PF_PLAYER_VX), a
    ld (platformer_player+PF_PLAYER_VY), a
    ld (platformer_last_collision), a
    ld (platformer_score), a
    ld (platformer_status), a
    ld (platformer_enemy_contacts), a
    ld (_platformer_enemy_contacts_next), a
    ld a, #PF_LIVES_INITIAL
    ld (platformer_lives), a
    ld a, #1
    ld (_platformer_enemy_h_dx), a
    ld (_platformer_enemy_v_dy), a
    ld (_platformer_enemy_v2_dy), a
    xor a
    ld (_platformer_enemy_phase), a
    ld a, #PF_PLAYER_WIDTH_BYTES
    ld (platformer_player+PF_PLAYER_WIDTH), a
    ld a, #PF_PLAYER_HEIGHT_PX
    ld (platformer_player+PF_PLAYER_HEIGHT), a
    ld a, #PF_TILE_GROUNDED
    ld (platformer_player+PF_PLAYER_FLAGS), a
    ld a, #PF_HUD_DIRTY_SCORE|PF_HUD_DIRTY_LIVES
    ld (platformer_hud_dirty), a
    xor a
    ld (platformer_fps), a
    ld (platformer_fps_frames), a
    ld hl, (fwk_system_frame_count)
    ld (platformer_fps_last_count), hl
    call _pf_reset_enemies
    call _pf_reset_render_flags
    call _pf_sync_player_render
    ret

_pf_render_scene:
    ;; The tilemap is static. Only dirty cells, the HUD and the moving player
    ;; are restored/redrawn after this initial full pass.
    ld ix, #platformer_map_descriptor
    ld iy, #platformer_view
    call fwk_tilemap_render_view
    call _pf_draw_hud_initial
    ld ix, #platformer_render_list
    call fwk_entity_render_init
    jp c, _pf_render_fail
    call _pf_prepare_dirty
    call _pf_restore_dirty
    call _pf_draw_dirty
    ld a, #PF_STATUS_READY
    ld (platformer_status), a
    ret

_pf_render_fail:
    ld a, #0xEE
    ld (platformer_status), a
_pf_render_fail_loop:
    call fwk_system_wait_frame
    jr _pf_render_fail_loop

_pf_prepare_dirty:
    ld ix, #platformer_render_list
    call fwk_entity_render_prepare_dirty
    jp c, _pf_render_fail
    ret

_pf_restore_dirty:
    ld ix, #platformer_render_list
    call fwk_entity_render_restore_dirty
    jp c, _pf_render_fail
    ret

_pf_draw_dirty:
    ld ix, #platformer_render_list
    call fwk_entity_render_draw_dirty
    jp c, _pf_render_fail
    ret

_pf_read_controls:
    ;; Left wins if both horizontal directions are held. Releasing both stops
    ;; immediately; acceleration belongs to a larger game, not this example.
    ld a, (fwk_input_held)
    and #PF_INPUT_LEFT
    jr z, _pf_try_right
    ld a, #-PF_SPEED
    ld (platformer_player+PF_PLAYER_VX), a
    jr _pf_try_jump
_pf_try_right:
    ld a, (fwk_input_held)
    and #PF_INPUT_RIGHT
    jr z, _pf_stop_horizontal
    ld a, #PF_SPEED
    ld (platformer_player+PF_PLAYER_VX), a
    jr _pf_try_jump
_pf_stop_horizontal:
    xor a
    ld (platformer_player+PF_PLAYER_VX), a

_pf_try_jump:
    ld a, (fwk_input_pressed)
    and #PF_INPUT_JUMP
    ret z
    ld a, (platformer_player+PF_PLAYER_FLAGS)
    and #PF_TILE_GROUNDED
    ret z
    ld a, #PF_JUMP_SPEED
    ld (platformer_player+PF_PLAYER_VY), a
    ret

_pf_update_player:
    ld ix, #platformer_config
    ld iy, #platformer_player
    call fwk_physics_platform_step
    ld ix, #platformer_map_descriptor
    ld iy, #platformer_player
    call fwk_platform_tilemap_resolve
    ld (platformer_last_collision), a
    ret

;; Enemy movement writes directly to the standard render prefix. Both patrols
;; stay inside fixed, documented limits and mark only their own entity dirty.
_pf_update_enemies:
    ld a, (_platformer_enemy_phase)
    xor #1
    ld (_platformer_enemy_phase), a
    jr z, _pf_update_enemy_v
    ld a, (_platformer_enemy_h_dx)
    bit 7, a
    jr nz, _pf_enemy_h_left
    ld hl, #platformer_enemy_h_entity+FWK_ENTITY_RENDER_X
    inc (hl)
    ld a, (hl)
    cp #PF_ENEMY_H_MAX_X
    jr c, _pf_enemy_h_dirty
    ld (hl), #PF_ENEMY_H_MAX_X
    ld a, #-1
    ld (_platformer_enemy_h_dx), a
    jr _pf_enemy_h_dirty
_pf_enemy_h_left:
    ld hl, #platformer_enemy_h_entity+FWK_ENTITY_RENDER_X
    dec (hl)
    ld a, (hl)
    cp #PF_ENEMY_H_MIN_X
    jr nc, _pf_enemy_h_dirty
    ld (hl), #PF_ENEMY_H_MIN_X
    ld a, #1
    ld (_platformer_enemy_h_dx), a
_pf_enemy_h_dirty:
    ld a, (_pf_anim_frame)
    or a
    jr z, _pf_enemy_h_sprite0
    ld hl, #platformer_enemy_pixels2
    jr _pf_enemy_h_sprite_set
_pf_enemy_h_sprite0:
    ld hl, #platformer_enemy_pixels
_pf_enemy_h_sprite_set:
    ld (platformer_enemy_h_entity+FWK_ENTITY_RENDER_SPRITE_DATA), hl
    ld hl, #platformer_enemy_h_entity+FWK_ENTITY_RENDER_FLAGS
    set 1, (hl)
    ret

_pf_update_enemy_v:
    ld a, (_platformer_enemy_v_dy)
    bit 7, a
    jr nz, _pf_enemy_v_up
    ld hl, #platformer_enemy_v_entity+FWK_ENTITY_RENDER_Y
    ld a, (hl)
    add a, #2
    ld (hl), a
    cp #PF_ENEMY_V_MAX_Y
    jr c, _pf_enemy_v_store
    ld (hl), #PF_ENEMY_V_MAX_Y
    ld a, #-1
    ld (_platformer_enemy_v_dy), a
    jr _pf_enemy_v_store
_pf_enemy_v_up:
    ld hl, #platformer_enemy_v_entity+FWK_ENTITY_RENDER_Y
    ld a, (hl)
    sub #2
    ld (hl), a
    cp #PF_ENEMY_V_MIN_Y
    jr nc, _pf_enemy_v_store
    ld (hl), #PF_ENEMY_V_MIN_Y
    ld a, #1
    ld (_platformer_enemy_v_dy), a
_pf_enemy_v_store:
    ld a, (platformer_enemy_v_entity+FWK_ENTITY_RENDER_Y)
    add a, #PF_ENEMY_HEIGHT_PX
    ld (platformer_enemy_v_entity+FWK_ENTITY_RENDER_SORT_Y), a
    xor a
    ld (platformer_enemy_v_entity+FWK_ENTITY_RENDER_SORT_Y+1), a
    ld a, (_pf_anim_frame)
    or a
    jr z, _pf_enemy_v_sprite0
    ld hl, #platformer_enemy_pixels2
    jr _pf_enemy_v_sprite_set
_pf_enemy_v_sprite0:
    ld hl, #platformer_enemy_pixels
_pf_enemy_v_sprite_set:
    ld (platformer_enemy_v_entity+FWK_ENTITY_RENDER_SPRITE_DATA), hl
    ld hl, #platformer_enemy_v_entity+FWK_ENTITY_RENDER_FLAGS
    set 1, (hl)
    ret

;; Second vertical enemy on the left side, used to measure FPS impact.
_pf_update_enemy_v2:
    ld a, (_platformer_enemy_v2_dy)
    bit 7, a
    jr nz, _pf_enemy_v2_up
    ld hl, #platformer_enemy_v2_entity+FWK_ENTITY_RENDER_Y
    ld a, (hl)
    add a, #2
    ld (hl), a
    cp #PF_ENEMY_V_MAX_Y
    jr c, _pf_enemy_v2_store
    ld (hl), #PF_ENEMY_V_MAX_Y
    ld a, #-1
    ld (_platformer_enemy_v2_dy), a
    jr _pf_enemy_v2_store
_pf_enemy_v2_up:
    ld hl, #platformer_enemy_v2_entity+FWK_ENTITY_RENDER_Y
    ld a, (hl)
    sub #2
    ld (hl), a
    cp #PF_ENEMY_V_MIN_Y
    jr nc, _pf_enemy_v2_store
    ld (hl), #PF_ENEMY_V_MIN_Y
    ld a, #1
    ld (_platformer_enemy_v2_dy), a
_pf_enemy_v2_store:
    ld a, (platformer_enemy_v2_entity+FWK_ENTITY_RENDER_Y)
    add a, #PF_ENEMY_HEIGHT_PX
    ld (platformer_enemy_v2_entity+FWK_ENTITY_RENDER_SORT_Y), a
    xor a
    ld (platformer_enemy_v2_entity+FWK_ENTITY_RENDER_SORT_Y+1), a
    ld a, (_pf_anim_frame)
    or a
    jr z, _pf_enemy_v2_sprite0
    ld hl, #platformer_enemy_pixels2
    jr _pf_enemy_v2_sprite_set
_pf_enemy_v2_sprite0:
    ld hl, #platformer_enemy_pixels
_pf_enemy_v2_sprite_set:
    ld (platformer_enemy_v2_entity+FWK_ENTITY_RENDER_SPRITE_DATA), hl
    ld hl, #platformer_enemy_v2_entity+FWK_ENTITY_RENDER_FLAGS
    set 1, (hl)
    ret

_pf_reset_enemies:
    ld a, #PF_ENEMY_H_START_X
    ld (platformer_enemy_h_entity+FWK_ENTITY_RENDER_X), a
    xor a
    ld (platformer_enemy_h_entity+FWK_ENTITY_RENDER_X+1), a
    ld a, #PF_ENEMY_H_Y
    ld (platformer_enemy_h_entity+FWK_ENTITY_RENDER_Y), a
    xor a
    ld (platformer_enemy_h_entity+FWK_ENTITY_RENDER_Y+1), a
    ld a, #PF_ENEMY_H_Y+PF_ENEMY_HEIGHT_PX
    ld (platformer_enemy_h_entity+FWK_ENTITY_RENDER_SORT_Y), a
    xor a
    ld (platformer_enemy_h_entity+FWK_ENTITY_RENDER_SORT_Y+1), a
    ld a, #PF_ENEMY_V_X
    ld (platformer_enemy_v_entity+FWK_ENTITY_RENDER_X), a
    xor a
    ld (platformer_enemy_v_entity+FWK_ENTITY_RENDER_X+1), a
    ld a, #PF_ENEMY_V_START_Y
    ld (platformer_enemy_v_entity+FWK_ENTITY_RENDER_Y), a
    xor a
    ld (platformer_enemy_v_entity+FWK_ENTITY_RENDER_Y+1), a
    ld a, #PF_ENEMY_V_START_Y+PF_ENEMY_HEIGHT_PX
    ld (platformer_enemy_v_entity+FWK_ENTITY_RENDER_SORT_Y), a
    xor a
    ld (platformer_enemy_v_entity+FWK_ENTITY_RENDER_SORT_Y+1), a
    ld a, #8
    ld (platformer_enemy_v2_entity+FWK_ENTITY_RENDER_X), a
    xor a
    ld (platformer_enemy_v2_entity+FWK_ENTITY_RENDER_X+1), a
    ld a, #PF_ENEMY_V_START_Y
    ld (platformer_enemy_v2_entity+FWK_ENTITY_RENDER_Y), a
    xor a
    ld (platformer_enemy_v2_entity+FWK_ENTITY_RENDER_Y+1), a
    ld a, #PF_ENEMY_V_START_Y+PF_ENEMY_HEIGHT_PX
    ld (platformer_enemy_v2_entity+FWK_ENTITY_RENDER_SORT_Y), a
    xor a
    ld (platformer_enemy_v2_entity+FWK_ENTITY_RENDER_SORT_Y+1), a
    ret

;; Copy the compact physics state into the render prefix. Only a real position
;; change marks the player dirty; sort_y is its bottom scanline.
_pf_sync_player_render:
    ld a, (platformer_player+PF_PLAYER_X)
    ld b, a
    ld a, (platformer_player_entity+FWK_ENTITY_RENDER_X)
    cp b
    jr nz, _pf_player_render_changed
    ld a, (platformer_player+PF_PLAYER_Y)
    ld b, a
    ld a, (platformer_player_entity+FWK_ENTITY_RENDER_Y)
    cp b
    jr z, _pf_player_render_store
_pf_player_render_changed:
    ld hl, #platformer_player_entity+FWK_ENTITY_RENDER_FLAGS
    set 1, (hl)
_pf_player_render_store:
    ld a, (platformer_player+PF_PLAYER_X)
    ld (platformer_player_entity+FWK_ENTITY_RENDER_X), a
    xor a
    ld (platformer_player_entity+FWK_ENTITY_RENDER_X+1), a
    ld a, (platformer_player+PF_PLAYER_Y)
    ld (platformer_player_entity+FWK_ENTITY_RENDER_Y), a
    ld l, a
    ld h, #0
    xor a
    ld (platformer_player_entity+FWK_ENTITY_RENDER_Y+1), a
    ld de, #PF_PLAYER_HEIGHT_PX
    add hl, de
    ld (platformer_player_entity+FWK_ENTITY_RENDER_SORT_Y), hl
    ld a, (_pf_anim_frame)
    or a
    jr z, _pf_player_sprite0
    ld hl, #platformer_player_pixels2
    jr _pf_player_sprite_set
_pf_player_sprite0:
    ld hl, #platformer_player_pixels
_pf_player_sprite_set:
    ld (platformer_player_entity+FWK_ENTITY_RENDER_SPRITE_DATA), hl
    ret

_pf_reset_render_flags:
    ld hl, #platformer_render_entities
    ld b, #PF_RENDER_COUNT
_pf_reset_render_loop:
    ld e, (hl)
    inc hl
    ld d, (hl)
    inc hl
    push hl
    push de
    pop iy
    ld FWK_ENTITY_RENDER_FLAGS(iy), #FWK_ENTITY_RENDER_VISIBLE
    pop hl
    djnz _pf_reset_render_loop
    ret

;; One life is lost on the transition from separated to overlapping for each
;; enemy. A sustained overlap does not drain one life per frame.
_pf_check_door:
    ld a, (platformer_status)
    cp #PF_STATUS_WON
    ret nz
    ld a, (platformer_player_entity+FWK_ENTITY_RENDER_X)
    add a, #PF_PLAYER_WIDTH_BYTES
    ld b, a
    ld a, (platformer_door_entity+FWK_ENTITY_RENDER_X)
    cp b
    jr nc, _pf_door_no
    add a, #4
    ld b, a
    ld a, (platformer_player_entity+FWK_ENTITY_RENDER_X)
    cp b
    jr nc, _pf_door_no
    ld a, (platformer_player_entity+FWK_ENTITY_RENDER_Y)
    add a, #PF_PLAYER_HEIGHT_PX
    ld b, a
    ld a, (platformer_door_entity+FWK_ENTITY_RENDER_Y)
    cp b
    jr nc, _pf_door_no
    add a, #8
    ld b, a
    ld a, (platformer_player_entity+FWK_ENTITY_RENDER_Y)
    cp b
    jr nc, _pf_door_no
    ;; Transition: reset player and enemies, hide door
    ld a, #PF_PLAYER_START_X
    ld (platformer_player+PF_PLAYER_X), a
    ld a, #PF_PLAYER_START_Y
    ld (platformer_player+PF_PLAYER_Y), a
    xor a
    ld (platformer_player+PF_PLAYER_VX), a
    ld (platformer_player+PF_PLAYER_VY), a
    ld a, #PF_TILE_GROUNDED
    ld (platformer_player+PF_PLAYER_FLAGS), a
    call _pf_reset_enemies
    call _pf_sync_player_render
    ld a, #PF_STATUS_READY
    ld (platformer_status), a
    ld hl, #platformer_door_entity+FWK_ENTITY_RENDER_FLAGS
    ld (hl), #0
    ret
_pf_door_no:
    ret

_pf_check_enemy_contacts:
    ld a, (platformer_status)
    cp #PF_STATUS_WON
    ret z
    xor a
    ld (_platformer_enemy_contacts_next), a
    ld ix, #platformer_enemy_h_entity
    call _pf_player_touches_enemy
    jr nc, _pf_enemy_h_separate
    ld hl, #_platformer_enemy_contacts_next
    set 0, (hl)
    ld a, (platformer_enemy_contacts)
    bit 0, a
    call z, _pf_lose_life
_pf_enemy_h_separate:
    ld ix, #platformer_enemy_v_entity
    call _pf_player_touches_enemy
    jr nc, _pf_enemy_v_separate
    ld hl, #_platformer_enemy_contacts_next
    set 1, (hl)
    ld a, (platformer_enemy_contacts)
    bit 1, a
    call z, _pf_lose_life
    ld ix, #platformer_enemy_v2_entity
    call _pf_player_touches_enemy
    jr nc, _pf_enemy_v_separate
    ld a, (platformer_enemy_contacts)
    bit 2, a
    call z, _pf_lose_life
_pf_enemy_v_separate:
    ld a, (_platformer_enemy_contacts_next)
    ld (platformer_enemy_contacts), a
    ret

_pf_lose_life:
    ld a, (platformer_lives)
    or a
    ret z
    dec a
    ld (platformer_lives), a
    ld hl, #platformer_hud_dirty
    set 1, (hl)
    ret

;; Half-open AABB test using the synchronized player render prefix and IX enemy.
;; Carry is set only when both axes overlap.
_pf_player_touches_enemy:
    ld a, (platformer_player_entity+FWK_ENTITY_RENDER_X)
    add a, #PF_PLAYER_WIDTH_BYTES
    ld b, a
    ld a, FWK_ENTITY_RENDER_X(ix)
    cp b
    jr nc, _pf_enemy_no_contact
    add a, #PF_ENEMY_WIDTH_BYTES
    ld b, a
    ld a, (platformer_player_entity+FWK_ENTITY_RENDER_X)
    cp b
    jr nc, _pf_enemy_no_contact
    ld a, (platformer_player_entity+FWK_ENTITY_RENDER_Y)
    add a, #PF_PLAYER_HEIGHT_PX
    ld b, a
    ld a, FWK_ENTITY_RENDER_Y(ix)
    cp b
    jr nc, _pf_enemy_no_contact
    add a, #PF_ENEMY_HEIGHT_PX
    ld b, a
    ld a, (platformer_player_entity+FWK_ENTITY_RENDER_Y)
    cp b
    jr nc, _pf_enemy_no_contact
    scf
    ret
_pf_enemy_no_contact:
    or a
    ret

_pf_collect_coins:
    ld hl, #platformer_coins
    ld b, #PF_COIN_COUNT
_pf_coin_loop:
    ld a, (hl)
    cp #PF_COIN_REMOVED
    jr z, _pf_coin_next
    push bc
    push hl

    ;; Coin coordinates are stored as tile coordinates and converted to the
    ;; byte/pixel coordinate system used by the compact platform state.
    ld a, (hl)
    sla a
    sla a
    ld c, a
    inc hl
    ld a, (hl)
    sla a
    sla a
    sla a
    ld b, a

    ld a, (platformer_player+PF_PLAYER_X)
    sub c
    jr nc, _pf_coin_dx_positive
    neg
_pf_coin_dx_positive:
    cp #8
    jr nc, _pf_coin_miss
    ld a, (platformer_player+PF_PLAYER_Y)
    sub b
    jr nc, _pf_coin_dy_positive
    neg
_pf_coin_dy_positive:
    cp #8
    jr nc, _pf_coin_miss

    ;; Hide the render entity. restore_dirty recovers its captured tile before
    ;; draw_dirty omits it from the next frame.
    pop hl
    ld (hl), #PF_COIN_REMOVED
    push hl
    ld de, #PF_COIN_ENTITY
    add hl, de
    ld e, (hl)
    inc hl
    ld d, (hl)
    push de
    pop iy
    res 0, FWK_ENTITY_RENDER_FLAGS(iy)
    set 1, FWK_ENTITY_RENDER_FLAGS(iy)

    ld a, (platformer_score)
    inc a
    ld (platformer_score), a
    ld hl, #platformer_hud_dirty
    set 0, (hl)
    ld a, (platformer_score)
    cp #PF_WIN_SCORE
    jr nz, _pf_coin_miss
    ld a, #PF_STATUS_WON
    ld (platformer_status), a
    ld hl, #platformer_door_entity+FWK_ENTITY_RENDER_FLAGS
    ld (hl), #FWK_ENTITY_RENDER_VISIBLE|FWK_ENTITY_RENDER_DIRTY

_pf_coin_miss:
    pop hl
    pop bc
_pf_coin_next:
    ld de, #PF_COIN_STRIDE
    add hl, de
    djnz _pf_coin_loop
    ret

_pf_draw_hud_initial:
    xor a
    ld (platformer_hud_dirty), a
    ld hl, #8
    ld c, #8
    call fwk_video_get_ptr
    ld iy, #platformer_score_str
    call fwk_text_draw
    ld hl, #8
    ld c, #32
    call fwk_video_get_ptr
    ld iy, #platformer_life_str
    jp fwk_text_draw

;; Normal score changes restore two tile cells and redraw one glyph. Only the
;; final transition replaces the status text, using its exact tile span.
_pf_update_hud:
    ld a, (platformer_hud_dirty)
    ld (_platformer_hud_pending), a
    xor a
    ld (platformer_hud_dirty), a
    ld a, (_platformer_hud_pending)
    bit 0, a
    call nz, _pf_update_hud_score
    ld a, (platformer_status)
    cp #PF_STATUS_WON
    jp z, _pf_draw_win_status
    ld a, (_platformer_hud_pending)
    bit 1, a
    ret z
    jp _pf_update_hud_lives

_pf_update_hud_score:
    ld b, #1
    ld c, #5
    call _pf_restore_hud_cell
    ld b, #2
    ld c, #5
    call _pf_restore_hud_cell
    ld a, (platformer_score)
    add a, #48
    ld (platformer_score_digit_str), a
    ld hl, #8
    ld c, #22
    call fwk_video_get_ptr
    ld iy, #platformer_score_digit_str
    call fwk_text_draw
    ret

_pf_draw_win_status:
    ld a, #8
    ld (_platformer_hud_column), a
_pf_hud_restore_status:
    ld b, #1
    ld a, (_platformer_hud_column)
    ld c, a
    call _pf_restore_hud_cell
    ld b, #2
    ld a, (_platformer_hud_column)
    ld c, a
    call _pf_restore_hud_cell
    ld a, (_platformer_hud_column)
    inc a
    ld (_platformer_hud_column), a
    cp #17
    jr c, _pf_hud_restore_status
    ld hl, #8
    ld c, #32
    call fwk_video_get_ptr
    ld iy, #platformer_win_str
    jp fwk_text_draw

_pf_update_hud_lives:
    ld b, #1
    ld c, #11
    call _pf_restore_hud_cell
    ld b, #2
    ld c, #11
    call _pf_restore_hud_cell
    ld a, (platformer_lives)
    cp #10
    jr nz, _pf_life_single_digit
    ld a, #48+1
    ld (platformer_life_digits_str), a
    ld a, #48
    jr _pf_life_store_units
_pf_life_single_digit:
    ld b, a
    ld a, #48
    ld (platformer_life_digits_str), a
    ld a, b
    add a, #48
_pf_life_store_units:
    ld (platformer_life_digits_str+1), a
    ld hl, #8
    ld c, #44
    call fwk_video_get_ptr
    ld iy, #platformer_life_digits_str
    jp fwk_text_draw

_pf_restore_hud_cell:
    push bc
    ld ix, #platformer_map_descriptor
    ld iy, #platformer_view
    call fwk_tilemap_render_cell
    pop bc
    jp c, _pf_render_fail
    ret
