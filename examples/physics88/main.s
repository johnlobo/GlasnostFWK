.module example_physics88
.include "extensions/physics_8_8.inc"
.globl fwk_system_init, fwk_system_wait_frame
.globl fwk_video_init, fwk_video_clear_visible, fwk_video_plot_byte
.globl fwk_physics_8_8_step

.area _DATA
physics88_state::
    .dw 78*256, 70*256, 2*256, 1*256
    .db 0
FWK_PHYS88_CONFIG physics88_config, 0, 79, 0, 199, 4
physics88_steps:: .db 0
physics88_status:: .db 0

.area _CODE
_main::
    call fwk_system_init
    call fwk_video_init
    xor a
    call fwk_video_clear_visible
_physics88_loop:
    call fwk_system_wait_frame
    ld a, (physics88_steps)
    cp #64
    jr nc, _physics88_draw
    ld iy, #physics88_state
    ld ix, #physics88_config
    call fwk_physics_8_8_step
    ld a, (physics88_steps)
    inc a
    ld (physics88_steps), a
    cp #64
    jr nz, _physics88_draw
    ld a, #0x5A
    ld (physics88_status), a
_physics88_draw:
    ld a, (physics88_state+FWK_PHYS88_X+1)
    ld c, a
    ld a, (physics88_state+FWK_PHYS88_Y+1)
    ld l, a
    ld h, #0
    ld a, #0xAA
    call fwk_video_plot_byte
    jr _physics88_loop
