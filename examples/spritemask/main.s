.module example_spritemask
.include "video/sprite.inc"

.globl fwk_system_init, fwk_system_wait_frame
.globl fwk_video_init, fwk_video_clear_visible, fwk_video_get_ptr
.globl cpct_setPALColour_asm

.area _DATA
;; Six bytes by eight rows. FF keeps the background and 00 replaces a full byte;
;; mixed values preserve or replace the selected bits (Mode 0: 4 bits per pixel).
spritemask_pixels:
    .db 0x00,0x00,0xAA,0xAA,0x00,0x00
    .db 0x00,0xAA,0xF0,0xF0,0xAA,0x00
    .db 0xAA,0xF0,0x00,0x00,0xF0,0xAA
    .db 0xAA,0xF0,0xAA,0xAA,0xF0,0xAA
    .db 0xAA,0xF0,0xAA,0xAA,0xF0,0xAA
    .db 0xAA,0xF0,0x00,0x00,0xF0,0xAA
    .db 0x00,0xAA,0xF0,0xF0,0xAA,0x00
    .db 0x00,0x00,0xAA,0xAA,0x00,0x00
spritemask_masks:
    .db 0xFF,0xFF,0x00,0x00,0xFF,0xFF
    .db 0xFF,0x00,0x00,0x00,0x00,0xFF
    .db 0x00,0x00,0xFF,0xFF,0x00,0x00
    .db 0x00,0x00,0x00,0x00,0x00,0x00
    .db 0x00,0x00,0x00,0x00,0x00,0x00
    .db 0x00,0x00,0xFF,0xFF,0x00,0x00
    .db 0xFF,0x00,0x00,0x00,0x00,0xFF
    .db 0xFF,0xFF,0x00,0x00,0xFF,0xFF

FWK_SPRITE_DESCRIPTOR spritemask_centre, spritemask_pixels, 20, 48, 6, 8
FWK_SPRITE_DESCRIPTOR spritemask_clipped, spritemask_pixels, 0xFFFE, 0xFFFD, 6, 8
FWK_SPRITE_DESCRIPTOR spritemask_outside, spritemask_pixels, 100, 20, 6, 8

spritemask_status:: .db 0

.area _CODE

_spritemask_fail:
    ld a, #0xEE
    ld (spritemask_status), a
_spritemask_fail_loop:
    call fwk_system_wait_frame
    jr _spritemask_fail_loop

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

    ;; Eight horizontal background bands behind the centred sprite.
    ld iy, #0
    ld b, #8
_spritemask_band_row:
    push bc
    push iy
    pop hl
    ld de, #48
    add hl, de
    ld c, #18
    call fwk_video_get_ptr
    pop bc
    ld a, b
    add a, a
    add a, #0x10
    ld c, #10
_spritemask_band_byte:
    ld (hl), a
    inc hl
    dec c
    jr nz, _spritemask_band_byte
    inc iy
    djnz _spritemask_band_row

    ;; Invalid mask span fails even though sprite data itself is valid.
    ld ix, #spritemask_centre
    ld de, #0xFFF0
    call fwk_sprite_draw_masked
    jp nc, _spritemask_fail

    ;; A wholly outside valid sprite succeeds without writing.
    ld ix, #spritemask_outside
    ld de, #spritemask_masks
    call fwk_sprite_draw_masked
    jp c, _spritemask_fail

    ;; Draw centred and clipped shapes with the same parallel mask.
    ld ix, #spritemask_centre
    ld de, #spritemask_masks
    call fwk_sprite_draw_masked
    jp c, _spritemask_fail
    ld ix, #spritemask_clipped
    ld de, #spritemask_masks
    call fwk_sprite_draw_masked
    jp c, _spritemask_fail

    ld a, #0x5A
    ld (spritemask_status), a
_spritemask_loop:
    call fwk_system_wait_frame
    jr _spritemask_loop
