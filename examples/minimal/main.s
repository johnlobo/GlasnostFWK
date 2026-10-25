.module example_minimal
.include "cpctelera.h.s"
.globl fwk_system_init, fwk_system_wait_frame
.globl fwk_input_init, fwk_input_set_bindings, fwk_input_update
.globl fwk_input_held, fwk_video_init, fwk_video_clear_visible, fwk_video_plot_byte

.area _DATA
_bindings:
    .dw Key_O
    .db 0x01
    .dw Key_P
    .db 0x02
    .dw 0
    .db 0

.area _CODE
_main::
    call fwk_system_init
    call fwk_video_init
    xor a
    call fwk_video_clear_visible
    call fwk_input_init
    ld hl, #_bindings
    call fwk_input_set_bindings
_loop:
    call fwk_system_wait_frame
    call fwk_input_update
    ld a, (fwk_input_held)
    ld hl, #100
    ld c, #40
    call fwk_video_plot_byte
    jr _loop
