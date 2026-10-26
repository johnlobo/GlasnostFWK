.module example_spriteclip
.include "video/sprite.inc"

.globl fwk_system_init, fwk_system_wait_frame
.globl fwk_video_init, fwk_video_clear_visible, fwk_video_get_ptr
.globl fwk_video_plot_byte
.globl cpct_setPALColour_asm

.area _DATA
;; Six Mode 0 bytes by eight scanlines, row-major and without padding.
spriteclip_pixels:
    .db 0x00,0xAA,0xAA,0xAA,0xAA,0x00
    .db 0xAA,0xF0,0xF0,0xF0,0xF0,0xAA
    .db 0xAA,0xF0,0x00,0x00,0xF0,0xAA
    .db 0xAA,0xF0,0x00,0x00,0xF0,0xAA
    .db 0xAA,0xF0,0x00,0x00,0xF0,0xAA
    .db 0xAA,0xF0,0x00,0x00,0xF0,0xAA
    .db 0xAA,0xF0,0xF0,0xF0,0xF0,0xAA
    .db 0x00,0xAA,0xAA,0xAA,0xAA,0x00

spriteclip_background:
    .db 0x11,0x22,0x33,0x44
    .db 0x55,0x66,0x77,0x88
    .db 0x99,0x12,0x23,0x34
    .db 0x45,0x56,0x67,0x78
    .db 0x89,0x9A,0xAB,0xBC

FWK_SPRITE_DESCRIPTOR spriteclip_restore_sprite, spriteclip_pixels, 0xFFFE, 0xFFFD, 6, 8
FWK_SPRITE_DESCRIPTOR spriteclip_left_sprite, spriteclip_pixels, 0xFFFE, 30, 6, 8
FWK_SPRITE_DESCRIPTOR spriteclip_top_sprite, spriteclip_pixels, 20, 0xFFFD, 6, 8
FWK_SPRITE_DESCRIPTOR spriteclip_right_sprite, spriteclip_pixels, 77, 30, 6, 8
FWK_SPRITE_DESCRIPTOR spriteclip_bottom_sprite, spriteclip_pixels, 20, 196, 6, 8
FWK_SPRITE_DESCRIPTOR spriteclip_centre_sprite, spriteclip_pixels, 35, 80, 6, 8
FWK_SPRITE_DESCRIPTOR spriteclip_outside_sprite, spriteclip_pixels, 100, 100, 6, 8
FWK_SPRITE_DESCRIPTOR spriteclip_invalid_sprite, spriteclip_pixels, 10, 10, 0, 8
FWK_SPRITE_DESCRIPTOR spriteclip_wrapped_sprite, 0xFFF0, 10, 10, 6, 8

spriteclip_buffer:                .ds 48
spriteclip_capture_used::         .dw 0
spriteclip_status::               .db 0

.area _CODE

_spriteclip_fail:
    ld a, #0xEE
    ld (spriteclip_status), a
_spriteclip_fail_loop:
    call fwk_system_wait_frame
    jr _spriteclip_fail_loop

;; Install a nonuniform 4x5 background in the visible part of (-2,-3,6,8).
_spriteclip_write_background:
    ld iy, #spriteclip_background
    ld hl, #0
    ld b, #5
_spriteclip_background_row:
    push bc
    push hl
    ld c, #0
    call fwk_video_get_ptr
    ex de, hl
    push iy
    pop hl
    ld bc, #4
    ldir
    push hl
    pop iy
    pop hl
    inc hl
    pop bc
    djnz _spriteclip_background_row
    ret

_main::
    call fwk_system_init
    call fwk_video_init
    ld l, #0
    ld h, #0x14
    call cpct_setPALColour_asm
    ld l, #5
    ld h, #0x0A
    call cpct_setPALColour_asm
    ld l, #15
    ld h, #0x13
    call cpct_setPALColour_asm
    xor a
    call fwk_video_clear_visible
    call _spriteclip_write_background

    ;; Invalid geometry fails before writing; a wholly outside sprite is valid.
    ld ix, #spriteclip_invalid_sprite
    call fwk_sprite_draw
    jp nc, _spriteclip_fail
    ld ix, #spriteclip_wrapped_sprite
    call fwk_sprite_draw
    jp nc, _spriteclip_fail
    ld hl, #100
    ld c, #79
    ld a, #0x55
    call fwk_video_plot_byte
    ld ix, #spriteclip_outside_sprite
    call fwk_sprite_draw
    jp c, _spriteclip_fail

    ;; Capture/draw/restore a sprite clipped on both top and left edges.
    ld ix, #spriteclip_restore_sprite
    ld de, #spriteclip_buffer
    call fwk_sprite_capture
    jp c, _spriteclip_fail
    push iy
    pop hl
    ld de, #spriteclip_buffer
    or a
    sbc hl, de
    ld (spriteclip_capture_used), hl
    ld a, h
    or a
    jp nz, _spriteclip_fail
    ld a, l
    cp #20
    jp nz, _spriteclip_fail
    ld ix, #spriteclip_restore_sprite
    call fwk_sprite_draw
    jp c, _spriteclip_fail
    ld ix, #spriteclip_restore_sprite
    ld hl, #spriteclip_buffer
    call fwk_sprite_restore
    jp c, _spriteclip_fail

    ;; Leave examples clipped independently on every edge plus one full sprite.
    ld ix, #spriteclip_left_sprite
    call fwk_sprite_draw
    jp c, _spriteclip_fail
    ld ix, #spriteclip_top_sprite
    call fwk_sprite_draw
    jp c, _spriteclip_fail
    ld ix, #spriteclip_right_sprite
    call fwk_sprite_draw
    jp c, _spriteclip_fail
    ld ix, #spriteclip_bottom_sprite
    call fwk_sprite_draw
    jp c, _spriteclip_fail
    ld ix, #spriteclip_centre_sprite
    call fwk_sprite_draw
    jp c, _spriteclip_fail

    ld a, #0x5A
    ld (spriteclip_status), a
_spriteclip_loop:
    call fwk_system_wait_frame
    jr _spriteclip_loop
