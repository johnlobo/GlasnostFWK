.module example_text
.include "cpctelera.h.s"
.globl fwk_project_init, fwk_system_wait_frame
.globl fwk_input_init, fwk_input_set_bindings, fwk_input_update, fwk_input_pressed
.globl fwk_video_init, fwk_video_clear_visible, fwk_video_plot_byte, fwk_video_get_ptr
.globl fwk_text_init, fwk_text_set_color, fwk_text_draw
.globl fwk_text_draw_small_digit, fwk_text_draw_small_u8

.area _DATA
_cursor_x: .db 16
_title: .asciz "GLASNOST TEXT"
text_demo_status:: .db 0
_text_demo_color: .db 0
_bindings:
    .dw Key_CursorLeft
    .db 0x01
    .dw Key_CursorRight
    .db 0x02
    .dw 0
    .db 0

.area _CODE
;; ----------------------------------------------------------------------------
;; _main
;;   Board demo: draws a title, three small numbers and a 15-colour digit sweep, then lets
;;   the player slide a one-byte cursor along row 104 with the left and right cursor keys.
;;   In : none (program entry; no register is read).
;;   Out: none; never returns (ends in an endless loop).
;;          Memory: video RAM, _cursor_x, _text_demo_color; text_demo_status = 0xA5 once all text is drawn.
;;   Clobbers: all (never returns)
;;   Notes: Does not return, so no register is preserved. fwk_project_init disables the firmware and installs
;;          the frame IRQ (keyboard scanned once per frame). The cursor starts at x=16 and moves
;;          in steps of 8 between 8 and 72.
;; ----------------------------------------------------------------------------
_main::
    ;; System, Mode 0 and text renderer up. fwk_project_init must come first (firmware off, IRQ on).
    call fwk_project_init
    call fwk_video_init
    call fwk_text_init
    ;; Clear the visible screen to byte 0 (all pen 0), text colour index 0.
    xor a
    call fwk_video_clear_visible
    xor a
    call fwk_text_set_color
    ;; Title string at y=16, x=12 bytes. IY=string for fwk_text_draw, HL=screen address.
    ld hl, #16
    ld c, #12
    call fwk_video_get_ptr
    ld iy, #_title
    call fwk_text_draw
    ;; Three small numbers at x=28 bytes, rows y=32, 40, 48: 42 and 7 (1-2 digits, no padding) and 255.
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
    ;; Colour sweep: digit 8 drawn once per text colour 0..14, at y=56, x=28+2*colour.
    xor a
    ld (_text_demo_color), a
_text_color_loop:
    ;; A = colour index: 0 on the first pass, the incremented index left in A by the loop tail afterwards.
    call fwk_text_set_color
    ;; x byte = 28 + 2*colour (each small digit is 2 bytes wide).
    ld a, (_text_demo_color)
    add a, a
    add a, #28
    ld c, a
    ld hl, #56
    call fwk_video_get_ptr
    ld a, #8
    call fwk_text_draw_small_digit
    ;; Next colour; loop while index < 15 (the colour table has 15 entries, 0..14).
    ld a, (_text_demo_color)
    inc a
    ld (_text_demo_color), a
    cp #15
    jr c, _text_color_loop
    ;; Publish 0xA5 in text_demo_status (exported) to say that all text calls finished.
    ld a, #0xA5
    ld (text_demo_status), a
    ;; Install the key bindings: cursor left = action bit 0, cursor right = action bit 1.
    call fwk_input_init
    ld hl, #_bindings
    call fwk_input_set_bindings
_text_loop:
    ;; Per frame: erase the cursor at its old column, wait for vsync, poll keys, move, redraw.
    ld a, (_cursor_x)
    ld c, a
    ld hl, #104
    xor a
    call fwk_video_plot_byte          ;; restore synthetic text background
    call fwk_system_wait_frame
    call fwk_input_update
    ;; A = keys newly pressed this frame (edge bits, not held). Left takes priority over right.
    ld a, (fwk_input_pressed)
    bit 0, a
    jr z, _text_right
    ;; Left: x -= 8 and clamp at 8 (a result below 8 means the cursor was already at the left limit).
    ld a, (_cursor_x)
    sub #8
    cp #8
    jr nc, _text_store
    ld a, #8
    jr _text_store
_text_right:
    ;; A still holds the pressed mask (bit does not modify A).
    bit 1, a
    jr z, _text_draw
    ;; Right: x += 8 and clamp at 72 (73 and above are rejected).
    ld a, (_cursor_x)
    add #8
    cp #73
    jr c, _text_store
    ld a, #72
    ;; Common exit for both keys: A = new x.
_text_store:
    ld (_cursor_x), a
    ;; Draw the cursor (0xFF) at the stored column; reached directly when no key moved it.
_text_draw:
    ld a, (_cursor_x)
    ld c, a
    ld hl, #104
    ld a, #0xFF
    call fwk_video_plot_byte           ;; one-byte cursor sprite
    jr _text_loop
