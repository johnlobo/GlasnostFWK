.module example_window
.include "ui/window.inc"

.globl fwk_system_init, fwk_system_wait_frame
.globl fwk_video_init, fwk_video_clear_visible, fwk_video_get_ptr
.globl fwk_text_set_colors, fwk_text_draw

WINDOW_WIDTH = 20
WINDOW_HEIGHT = 16
WINDOW_BUFFER_SIZE = WINDOW_WIDTH * WINDOW_HEIGHT

.area _DATA
window_descriptor::
    .db 10
    .dw 40
    .db WINDOW_WIDTH
    .db WINDOW_HEIGHT
    .db 0xFF
    .db 0x00

window_invalid_descriptor:
    .db 75
    .dw 40
    .db 10
    .db 10
    .db 0xFF
    .db 0x00

;; Y + height must not wrap the 16-bit coordinate space.
window_overflow_descriptor:
    .db 10
    .dw 0xFFFF
    .db 10
    .db 10
    .db 0xFF
    .db 0x00

window_message: .asciz "GLASNOST"
window_buffer:: .ds WINDOW_BUFFER_SIZE
window_command:: .db 0
window_status:: .db 0

.area _CODE
_main::
    call fwk_system_init
    call fwk_video_init
    ld a, #0x55
    call fwk_video_clear_visible

    ;; Invalid geometry must be rejected without touching the screen/buffer.
    ld ix, #window_invalid_descriptor
    ld de, #window_buffer
    call fwk_window_capture
    jr nc, _window_failed

    ;; Y+height overflow is invalid even though the wrapped sum is on-screen.
    ld ix, #window_overflow_descriptor
    ld de, #window_buffer
    call fwk_window_capture
    jr nc, _window_failed

    ld ix, #window_descriptor
    ld de, #window_buffer
    call fwk_window_capture
    jr c, _window_failed
    call _window_show
    ld a, #0xA5
    ld (window_status), a

_window_loop:
    call fwk_system_wait_frame
    ld a, (window_command)
    cp #1
    jr z, _window_close
    cp #2
    jr z, _window_reopen
    jr _window_loop

_window_close:
    xor a
    ld (window_command), a
    ld ix, #window_descriptor
    ld hl, #window_buffer
    call fwk_window_restore
    jr c, _window_failed
    ld a, #0x5A
    ld (window_status), a
    jr _window_loop

_window_reopen:
    xor a
    ld (window_command), a
    call _window_show
    ld a, #0xC3
    ld (window_status), a
    jr _window_loop

_window_show:
    ld ix, #window_descriptor
    call fwk_window_draw
    ret c
    ld l, #15
    ld h, #0
    call fwk_text_set_colors
    ld hl, #44
    ld c, #12
    call fwk_video_get_ptr
    ld iy, #window_message
    jp fwk_text_draw

_window_failed:
    ld a, #0xEE
    ld (window_status), a
    jr _window_loop
