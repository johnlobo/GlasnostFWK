.module example_gravity
.include "extensions/physics_platform.inc"
.globl fwk_system_init, fwk_system_wait_frame
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
_main::
    call fwk_system_init
    call fwk_video_init
    ;; Do not inherit the BASIC palette: 0xF0 is pen 5 in Mode 0.
    ld l, #0
    ld h, #0x14              ; HW_BLACK
    call cpct_setPALColour_asm
    ld l, #5
    ld h, #0x0A              ; HW_BRIGHT_YELLOW
    call cpct_setPALColour_asm
    xor a
    call fwk_video_clear_visible
_gravity_loop:
    call fwk_system_wait_frame
    ld a, (gravity_steps)
    cp #48
    jr nc, _gravity_draw
    ld iy, #gravity_state
    ld ix, #gravity_config
    call fwk_physics_platform_step
    ld a, (gravity_steps)
    inc a
    ld (gravity_steps), a
    cp #48
    jr nz, _gravity_draw
    ld a, #0x5A
    ld (gravity_status), a
_gravity_draw:
    ld a, (gravity_state+FWK_PLATFORM_X)
    ld c, a
    ld a, (gravity_state+FWK_PLATFORM_Y)
    ld l, a
    ld h, #0
    ld a, #0xF0
    call fwk_video_plot_byte
    jr _gravity_loop
