.module example_platformer
.include "cpctelera.h.s"
.include "video/sprite.inc"
.include "extensions/platform_tilemap.inc"

.globl fwk_system_init, fwk_system_wait_frame
.globl fwk_video_init, fwk_video_clear_visible, fwk_video_get_ptr
.globl fwk_input_init, fwk_input_set_bindings, fwk_input_update
.globl fwk_input_held, fwk_input_pressed
.globl fwk_physics_platform_step
.globl fwk_platform_tilemap_resolve
.globl fwk_tilemap_render_view, fwk_tilemap_render_cell
.globl fwk_sprite_draw, fwk_sprite_capture, fwk_sprite_restore
.globl fwk_text_init, fwk_text_set_color, fwk_text_draw
.globl cpct_setPALColour_asm
.globl platformer_map_descriptor, platformer_view, platformer_config
.globl platformer_player_sprite, platformer_coin_sprite
.globl platformer_status, platformer_score, platformer_bindings
.globl platformer_coins, platformer_player

.area _DATA
platformer_status:: .db 0
platformer_score:: .db 0
platformer_hud_dirty:: .db 1
_platformer_hud_row: .db 0
_platformer_hud_column: .db 0

platformer_player:: .ds 7
platformer_player_background:: .ds 64

platformer_score_str:: .ascii "SCORE: 0"
    .db 0
platformer_help_str:: .ascii "LEFT RIGHT  UP JUMP"
    .db 0

.area _CODE

_main::
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

    ;; Player initial state
    ld a, #16
    ld (platformer_player+0), a   ; X
    ld a, #184
    ld (platformer_player+1), a   ; Y
    xor a
    ld (platformer_player+2), a   ; VX
    ld (platformer_player+3), a   ; VY
    ld a, #8
    ld (platformer_player+4), a   ; width
    ld a, #8
    ld (platformer_player+5), a   ; height
    ld a, #0x02
    ld (platformer_player+6), a   ; grounded on the bottom row

    xor a
    ld (platformer_score), a
    ld a, #1
    ld (platformer_hud_dirty), a
    xor a
    ld (platformer_status), a

    call fwk_input_init
    ld hl, #platformer_bindings
    call fwk_input_set_bindings

    ;; Static scene: draw the full tilemap once. Moving objects restore only
    ;; their saved background, avoiding a full-screen tilemap pass per frame.
    ld ix, #platformer_map_descriptor
    ld iy, #platformer_view
    call fwk_tilemap_render_view
    call _pf_draw_coins
    call _pf_draw_hud
    call _pf_draw_player
    ld a, #0xA5
    ld (platformer_status), a

_platformer_loop:
    call fwk_system_wait_frame

    ld ix, #platformer_player_sprite
    ld hl, #platformer_player_background
    call fwk_sprite_restore

    call fwk_input_update

    ;; Horizontal movement
    ld a, (fwk_input_held)
    and #0x01
    jr z, _pf_not_left
    ld a, #-2
    ld (platformer_player+2), a
    jr _pf_input_done
_pf_not_left:
    ld a, (fwk_input_held)
    and #0x02
    jr z, _pf_not_right
    ld a, #2
    ld (platformer_player+2), a
    jr _pf_input_done
_pf_not_right:
    xor a
    ld (platformer_player+2), a
_pf_input_done:

    ;; Jump if pressed up and on ground
    ld a, (fwk_input_pressed)
    and #0x04
    jr z, _pf_no_jump
    ld a, (platformer_player+6)
    and #0x02          ; tile grounded bit
    jr z, _pf_no_jump
    ld a, #-8
    ld (platformer_player+3), a
_pf_no_jump:

    ;; Physics
    ld ix, #platformer_config
    ld iy, #platformer_player
    call fwk_physics_platform_step

    ;; Tile collision
    ld ix, #platformer_map_descriptor
    ld iy, #platformer_player
    call fwk_platform_tilemap_resolve

    ;; Coin collection
    ld hl, #platformer_coins
    ld b, #4
_pf_coin_loop:
    ld a, (hl)
    cp #0xFF
    jr z, _pf_coin_next
    push bc
    push hl
    ld a, (hl)
    sla a
    sla a
    sla a
    ld c, a            ; coin x px
    inc hl
    ld a, (hl)
    sla a
    sla a
    sla a
    ld b, a            ; coin y px
    ; player pos
    ld a, (platformer_player+0)
    sub c
    jr nc, _pf_cdx
    neg
_pf_cdx:
    cp #8
    jr nc, _pf_coin_skip
    ld a, (platformer_player+1)
    sub b
    jr nc, _pf_cdy
    neg
_pf_cdy:
    cp #8
    jr nc, _pf_coin_skip
    ; collect and restore the static tile below the removed coin
    pop hl
    ld c, (hl)
    inc hl
    ld b, (hl)
    dec hl
    ld (hl), #0xFF
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
    cp #4
    jr nz, _pf_coin_done
    ld a, #0x5A
    ld (platformer_status), a
_pf_coin_done:
_pf_coin_skip:
    pop hl
    pop bc
_pf_coin_next:
    inc hl
    inc hl
    inc hl
    djnz _pf_coin_loop

    ld a, (platformer_hud_dirty)
    or a
    call nz, _pf_draw_hud
    call _pf_draw_player
    jp _platformer_loop

_pf_draw_player:
    ld a, (platformer_player+0)
    ld (platformer_player_sprite+2), a
    ld a, (platformer_player+1)
    ld (platformer_player_sprite+4), a
    ld ix, #platformer_player_sprite
    ld de, #platformer_player_background
    call fwk_sprite_capture
    ld ix, #platformer_player_sprite
    call fwk_sprite_draw
    ret

_pf_draw_coins:
    ld hl, #platformer_coins
    ld b, #4
_pf_render_coins:
    ld a, (hl)
    cp #0xFF
    jr z, _pf_rc_next
    push bc
    push hl
    ld a, (hl)
    sla a
    sla a
    sla a
    ld (platformer_coin_sprite+2), a
    inc hl
    ld a, (hl)
    sla a
    sla a
    sla a
    ld (platformer_coin_sprite+4), a
    ld ix, #platformer_coin_sprite
    call fwk_sprite_draw
    pop hl
    pop bc
_pf_rc_next:
    inc hl
    inc hl
    inc hl
    djnz _pf_render_coins
    ret

_pf_draw_hud:
    ;; Restore the three tile rows below the masked HUD before changing text.
    ;; Otherwise transparent pixels from the previous score remain visible.
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
    cp #10
    jr c, _pf_hud_restore_column
    ld a, (_platformer_hud_row)
    inc a
    ld (_platformer_hud_row), a
    cp #3
    jr c, _pf_hud_restore_row

    ld a, (platformer_score)
    add a, #48
    ld (platformer_score_str+7), a

    ;; Draw HUD
    ld hl, #0
    ld c, #0
    call fwk_video_get_ptr
    ld iy, #platformer_score_str
    call fwk_text_draw
    ld hl, #10
    ld c, #0
    call fwk_video_get_ptr
    ld iy, #platformer_help_str
    call fwk_text_draw
    ret
