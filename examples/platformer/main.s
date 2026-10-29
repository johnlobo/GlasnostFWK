.module example_platformer
.include "cpctelera.h.s"
.include "video/sprite.inc"
.include "extensions/platform_tilemap.inc"
.include "game/game.inc"

.globl fwk_system_init, fwk_system_wait_frame
.globl fwk_video_init, fwk_video_clear_visible, fwk_video_get_ptr
.globl fwk_input_init, fwk_input_set_bindings, fwk_input_update
.globl fwk_input_held, fwk_input_pressed
.globl fwk_physics_platform_step, fwk_platform_tilemap_resolve
.globl fwk_tilemap_render_view, fwk_tilemap_render_cell
.globl fwk_sprite_draw, fwk_sprite_capture, fwk_sprite_restore
.globl fwk_text_init, fwk_text_set_color, fwk_text_draw
.globl cpct_setPALColour_asm
.globl platformer_map_descriptor, platformer_view, platformer_config
.globl platformer_player_sprite, platformer_coin_sprite
.globl platformer_bindings, platformer_coins
.globl platformer_status, platformer_score, platformer_player

.area _DATA

;; Public state doubles as a small observable contract for emulator tests.
platformer_status::         .db 0
platformer_score::          .db 0
platformer_last_collision:: .db 0
platformer_hud_dirty::      .db 1

platformer_player:: .ds PF_PLAYER_SIZE
platformer_player_background::
    .ds PF_PLAYER_WIDTH_BYTES * PF_PLAYER_HEIGHT_PX

platformer_score_str:: .ascii "COINS: 0/4"
    .db 0
platformer_help_str:: .ascii "CURSORS  UP JUMPS"
    .db 0
platformer_win_str:: .ascii "ALL COINS! YOU WIN"
    .db 0

_platformer_hud_row:    .db 0
_platformer_hud_column: .db 0

.area _CODE

_main::
    call _pf_init_framework
    call _pf_reset_game
    call _pf_render_scene

_platformer_loop:
    call fwk_system_wait_frame
    call _pf_erase_player
    call fwk_input_update
    call _pf_read_controls
    call _pf_update_player
    call _pf_collect_coins

    ld a, (platformer_hud_dirty)
    or a
    call nz, _pf_draw_hud
    call _pf_draw_player
    jp _platformer_loop

;; Framework and palette setup are kept separate from game state so the order
;; required by the text module is obvious in the tutorial.
_pf_init_framework:
    call fwk_system_init
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
    ld a, #PF_PLAYER_WIDTH_BYTES
    ld (platformer_player+PF_PLAYER_WIDTH), a
    ld a, #PF_PLAYER_HEIGHT_PX
    ld (platformer_player+PF_PLAYER_HEIGHT), a
    ld a, #PF_TILE_GROUNDED
    ld (platformer_player+PF_PLAYER_FLAGS), a
    ld a, #1
    ld (platformer_hud_dirty), a
    ret

_pf_render_scene:
    ;; The tilemap is static. Only dirty cells, the HUD and the moving player
    ;; are restored/redrawn after this initial full pass.
    ld ix, #platformer_map_descriptor
    ld iy, #platformer_view
    call fwk_tilemap_render_view
    call _pf_draw_coins
    call _pf_draw_hud
    call _pf_draw_player
    ld a, #PF_STATUS_READY
    ld (platformer_status), a
    ret

_pf_erase_player:
    ld ix, #platformer_player_sprite
    ld hl, #platformer_player_background
    jp fwk_sprite_restore

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

    ;; Mark the coin inactive, then redraw exactly the tile it occupied.
    pop hl
    ld c, (hl)
    inc hl
    ld b, (hl)
    dec hl
    ld (hl), #PF_COIN_REMOVED
    push hl
    ld ix, #platformer_map_descriptor
    ld iy, #platformer_view
    call fwk_tilemap_render_cell

    ld a, (platformer_score)
    inc a
    ld (platformer_score), a
    ld a, #1
    ld (platformer_hud_dirty), a
    ld a, (platformer_score)
    cp #PF_WIN_SCORE
    jr nz, _pf_coin_miss
    ld a, #PF_STATUS_WON
    ld (platformer_status), a

_pf_coin_miss:
    pop hl
    pop bc
_pf_coin_next:
    ld de, #PF_COIN_STRIDE
    add hl, de
    djnz _pf_coin_loop
    ret

_pf_draw_player:
    ld a, (platformer_player+PF_PLAYER_X)
    ld (platformer_player_sprite+FWK_SPRITE_X), a
    ld a, (platformer_player+PF_PLAYER_Y)
    ld (platformer_player_sprite+FWK_SPRITE_Y), a
    ld ix, #platformer_player_sprite
    ld de, #platformer_player_background
    call fwk_sprite_capture
    ld ix, #platformer_player_sprite
    jp fwk_sprite_draw

_pf_draw_coins:
    ld hl, #platformer_coins
    ld b, #PF_COIN_COUNT
_pf_coin_draw_loop:
    ld a, (hl)
    cp #PF_COIN_REMOVED
    jr z, _pf_coin_draw_next
    push bc
    push hl
    ld a, (hl)
    sla a
    sla a
    ld (platformer_coin_sprite+FWK_SPRITE_X), a
    inc hl
    ld a, (hl)
    sla a
    sla a
    sla a
    ld (platformer_coin_sprite+FWK_SPRITE_Y), a
    ld ix, #platformer_coin_sprite
    call fwk_sprite_draw
    pop hl
    pop bc
_pf_coin_draw_next:
    ld de, #PF_COIN_STRIDE
    add hl, de
    djnz _pf_coin_draw_loop
    ret

_pf_draw_hud:
    ;; Masked text cannot erase its previous opaque pixels. Restore the three
    ;; tile rows under the HUD before drawing the new score or victory line.
    xor a
    ld (platformer_hud_dirty), a
    ld (_platformer_hud_row), a
_pf_hud_restore_row:
    xor a
    ld (_platformer_hud_column), a
_pf_hud_restore_column:
    ld a, (_platformer_hud_row)
    ld b, a
    ld a, (_platformer_hud_column)
    ld c, a
    ld ix, #platformer_map_descriptor
    ld iy, #platformer_view
    call fwk_tilemap_render_cell
    ld a, (_platformer_hud_column)
    inc a
    ld (_platformer_hud_column), a
    cp #PF_MAP_COLUMNS
    jr c, _pf_hud_restore_column
    ld a, (_platformer_hud_row)
    inc a
    ld (_platformer_hud_row), a
    cp #PF_HUD_ROWS
    jr c, _pf_hud_restore_row

    ld a, (platformer_score)
    add a, #48
    ld (platformer_score_str+7), a
    ld hl, #0
    ld c, #0
    call fwk_video_get_ptr
    ld iy, #platformer_score_str
    call fwk_text_draw

    ld hl, #10
    ld c, #0
    call fwk_video_get_ptr
    ld a, (platformer_status)
    cp #PF_STATUS_WON
    ld iy, #platformer_help_str
    jr nz, _pf_draw_hud_line
    ld iy, #platformer_win_str
_pf_draw_hud_line:
    jp fwk_text_draw
