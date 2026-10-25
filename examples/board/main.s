.module example_board
.include "cpctelera.h.s"
.globl fwk_system_init, fwk_system_wait_frame
.globl fwk_input_init, fwk_input_set_bindings, fwk_input_update, fwk_input_pressed
.globl fwk_video_init, fwk_video_clear_visible, fwk_video_plot_byte, fwk_video_get_ptr
.globl fwk_text_set_colors, fwk_text_draw

.area _DATA
_cursor_x: .db 16
_title: .asciz "GLASNOST BOARD"
_bindings:
    .dw Key_CursorLeft
    .db 0x01
    .dw Key_CursorRight
    .db 0x02
    .dw 0
    .db 0

.area _CODE
_main::
    call fwk_system_init
    call fwk_video_init
    xor a
    call fwk_video_clear_visible
    ld hl, #0x000F
    call fwk_text_set_colors
    ld hl, #16
    ld c, #12
    call fwk_video_get_ptr
    ld iy, #_title
    call fwk_text_draw
    call fwk_input_init
    ld hl, #_bindings
    call fwk_input_set_bindings
_board_loop:
    ld a, (_cursor_x)
    ld c, a
    ld hl, #104
    xor a
    call fwk_video_plot_byte          ;; restore synthetic board background
    call fwk_system_wait_frame
    call fwk_input_update
    ld a, (fwk_input_pressed)
    bit 0, a
    jr z, _board_right
    ld a, (_cursor_x)
    sub #8
    cp #8
    jr nc, _board_store
    ld a, #8
    jr _board_store
_board_right:
    bit 1, a
    jr z, _board_draw
    ld a, (_cursor_x)
    add #8
    cp #73
    jr c, _board_store
    ld a, #72
_board_store:
    ld (_cursor_x), a
_board_draw:
    ld a, (_cursor_x)
    ld c, a
    ld hl, #104
    ld a, #0xFF
    call fwk_video_plot_byte           ;; one-byte cursor sprite
    jr _board_loop
