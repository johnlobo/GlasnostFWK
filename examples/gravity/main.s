.module example_gravity
.include "extensions/physics_platform.inc"
.globl fwk_project_init, fwk_system_wait_frame
.globl fwk_video_init, fwk_video_clear_visible, fwk_video_plot_byte
.globl fwk_physics_platform_step
.globl cpct_setPALColour_asm

.area _DATA
gravity_state::
    .db 75, 150, 3, -8, 4, 8, FWK_PLATFORM_AIRBORNE
FWK_PLATFORM_CONFIG gravity_config, 80, 199, 1, 8
gravity_steps:: .db 0
gravity_status:: .db 0

.area _CODE
;; ----------------------------------------------------------------------------
;; _main
;;   Platform-gravity demo: a 4x8 body starts airborne at (75,150) with vx=3, vy=-8 and is stepped
;;   by fwk_physics_platform_step for 48 frames; each frame its position is plotted as one byte.
;;   In : none (program entry; no register is read).
;;   Out: none; never returns (ends in an endless loop).
;;          Memory: gravity_state is updated each frame for the first 48 frames; gravity_steps counts them;
;;          gravity_status = 0x5A once the 48th step ran; video RAM gets one 0xF0 byte per frame (never erased,
;;          so the path stays as a trail).
;;   Clobbers: all (never returns)
;;   Notes: Does not return, so no register is preserved. IX/IY are reloaded before every physics call.
;; ----------------------------------------------------------------------------
_main::
    ;; System up (firmware off, IRQ on), Mode 0.
    call fwk_project_init
    call fwk_video_init
    ;; Do not inherit the BASIC palette: 0xF0 is pen 5 in Mode 0.
    ;; Pen 0 = black, pen 5 = bright yellow: cpct_setPALColour_asm takes L=pen, H=hardware colour.
    ld l, #0
    ld h, #0x14              ; HW_BLACK
    call cpct_setPALColour_asm
    ld l, #5
    ld h, #0x0A              ; HW_BRIGHT_YELLOW
    call cpct_setPALColour_asm
    ;; Clear to pen 0.
    xor a
    call fwk_video_clear_visible
    ;; Per frame: wait for vsync, step the physics while steps < 48, then draw.
_gravity_loop:
    call fwk_system_wait_frame
    ;; Stop stepping after 48 frames; the body then keeps being drawn where it is.
    ld a, (gravity_steps)
    cp #48
    jr nc, _gravity_draw
    ;; IY = 7-byte body state, IX = 4-byte config (world width 80, ground y 199, gravity 1, max fall 8).
    ld iy, #gravity_state
    ld ix, #gravity_config
    call fwk_physics_platform_step
    ;; Count the step; on reaching 48 publish 0x5A in gravity_status (exactly once).
    ld a, (gravity_steps)
    inc a
    ld (gravity_steps), a
    cp #48
    jr nz, _gravity_draw
    ld a, #0x5A
    ld (gravity_status), a
_gravity_draw:
    ;; Plot byte 0xF0 (pen 5 in Mode 0) at x byte / y pixel of the body: C=x, HL=y.
    ld a, (gravity_state+FWK_PLATFORM_X)
    ld c, a
    ld a, (gravity_state+FWK_PLATFORM_Y)
    ld l, a
    ld h, #0
    ld a, #0xF0
    call fwk_video_plot_byte
    jr _gravity_loop
