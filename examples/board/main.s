.module example_board
.include "cpctelera.h.s"
.globl fwk_system_init, fwk_system_wait_frame
.globl fwk_input_init, fwk_input_set_bindings, fwk_input_update, fwk_input_pressed
.globl fwk_video_init, fwk_video_clear_visible, fwk_video_plot_byte, fwk_video_get_ptr
.globl fwk_text_init, fwk_text_set_color, fwk_text_draw
.globl fwk_text_draw_small_digit, fwk_text_draw_small_u8

.area _DATA
_cursor_x: .db 16
_title: .asciz "GLASNOST BOARD"
board_text_status:: .db 0
_board_text_color: .db 0
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
    call fwk_text_init
    xor a
    call fwk_video_clear_visible
    xor a
    call fwk_text_set_color
    ld hl, #16
    ld c, #12
    call fwk_video_get_ptr
    ld iy, #_title
    call fwk_text_draw
    ld hl, #32
    ld c, #28
    call fwk_video_get_ptr
    ld a, #42
    call fwk_text_draw_small_u8
    ld hl, #40
    ld c, #28
    call fwk_video_get_ptr
    ld a, #7
    call fwk_text_draw_small_u8
    ld hl, #48
    ld c, #28
    call fwk_video_get_ptr
    ld a, #255
    call fwk_text_draw_small_u8
    xor a
    ld (_board_text_color), a
_board_color_loop:
    call fwk_text_set_color
    ld a, (_board_text_color)
    add a, a
    add a, #28
    ld c, a
    ld hl, #56
    call fwk_video_get_ptr
    ld a, #8
    call fwk_text_draw_small_digit
    ld a, (_board_text_color)
    inc a
    ld (_board_text_color), a
    cp #15
    jr c, _board_color_loop
    ld a, #0xA5
    ld (board_text_status), a
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
