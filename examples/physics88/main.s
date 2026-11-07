.module example_physics88
.include "extensions/physics_8_8.inc"
.globl fwk_project_init, fwk_system_wait_frame
.globl fwk_video_init, fwk_video_clear_visible, fwk_video_plot_byte
.globl fwk_physics_8_8_step
.globl cpct_setPALColour_asm

.area _DATA
physics88_state::
    .dw 78*256, 70*256, 2*256, 1*256
    .db 0
FWK_PHYS88_CONFIG physics88_config, 0, 79, 0, 199, 4
physics88_steps:: .db 0
physics88_status:: .db 0

.area _CODE

;; ----------------------------------------------------------------------------
;; _main
;;   Fixed-point (8.8) physics demo: a body starts at (78,70) with velocity (2,1) px/step and friction 4,
;;   is stepped 64 frames inside the box x 0..79, y 0..199 and plotted each frame as one byte.
;;   In : none (program entry; no register is read).
;;   Out: none; never returns (ends in an endless loop).
;;          Memory: physics88_state is updated for the first 64 frames; physics88_steps counts them;
;;          physics88_status = 0x5A once the 64th step ran; video RAM gets one 0xAA byte per frame (no erase).
;;   Clobbers: all (never returns)
;;   Notes: Does not return, so no register is preserved. IX/IY are reloaded before every physics call.
;; ----------------------------------------------------------------------------
_main::
    ;; System up (firmware off, IRQ on), Mode 0.
    call fwk_project_init
    call fwk_video_init
    ;; Do not inherit the BASIC palette: 0xAA alternates pens 15 and 0.
    ;; Pen 0 = black, pen 15 = bright cyan: cpct_setPALColour_asm takes L=pen, H=hardware colour.
    ld l, #0
    ld h, #0x14              ; HW_BLACK
    call cpct_setPALColour_asm
    ld l, #15
    ld h, #0x13              ; HW_BRIGHT_CYAN
    call cpct_setPALColour_asm
    ;; Clear to pen 0.
    xor a
    call fwk_video_clear_visible
    ;; Per frame: wait for vsync, step the physics while steps < 64, then draw.
_physics88_loop:
    call fwk_system_wait_frame
    ;; Stop stepping after 64 frames; the body is then redrawn where it is.
    ld a, (physics88_steps)
    cp #64
    jr nc, _physics88_draw
    ;; IY = 9-byte 8.8 state, IX = 5-byte bounds/friction descriptor.
    ld iy, #physics88_state
    ld ix, #physics88_config
    call fwk_physics_8_8_step
    ;; Count the step; on reaching 64 publish 0x5A in physics88_status (exactly once).
    ld a, (physics88_steps)
    inc a
    ld (physics88_steps), a
    cp #64
    jr nz, _physics88_draw
    ld a, #0x5A
    ld (physics88_status), a
_physics88_draw:
    ;; Draw at the integer part: the high byte (offset +1, little endian) of the 8.8 x and y. C=x, HL=y.
    ld a, (physics88_state+FWK_PHYS88_X+1)
    ld c, a
    ld a, (physics88_state+FWK_PHYS88_Y+1)
    ld l, a
    ld h, #0
    ld a, #0xAA
    call fwk_video_plot_byte
    jr _physics88_loop
