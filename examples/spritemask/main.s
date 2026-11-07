.module example_spritemask
.include "video/sprite.inc"

.globl fwk_project_init, fwk_system_wait_frame
.globl fwk_video_init, fwk_video_clear_visible, fwk_video_get_ptr
.globl cpct_setPALColour_asm

.area _DATA
;; Six bytes by eight rows. Project pen 3 is transparent (0xCC encodes two
;; pen-3 pixels in Mode 0); every other packed pen is opaque.
spritemask_pixels:
    .db 0xCC,0xCC,0xAA,0xAA,0xCC,0xCC
    .db 0xCC,0xAA,0xF0,0xF0,0xAA,0xCC
    .db 0xAA,0xF0,0xCC,0xCC,0xF0,0xAA
    .db 0xAA,0xF0,0xAA,0xAA,0xF0,0xAA
    .db 0xAA,0xF0,0xAA,0xAA,0xF0,0xAA
    .db 0xAA,0xF0,0xCC,0xCC,0xF0,0xAA
    .db 0xCC,0xAA,0xF0,0xF0,0xAA,0xCC
    .db 0xCC,0xCC,0xAA,0xAA,0xCC,0xCC

FWK_SPRITE_DESCRIPTOR spritemask_centre, spritemask_pixels, 20, 48, 6, 8
FWK_SPRITE_DESCRIPTOR spritemask_recolor, spritemask_pixels, 32, 48, 6, 8
FWK_SPRITE_DESCRIPTOR spritemask_opaque_recolor, spritemask_pixels, 44, 48, 6, 8
FWK_SPRITE_DESCRIPTOR spritemask_clipped, spritemask_pixels, 0xFFFE, 0xFFFD, 6, 8
FWK_SPRITE_DESCRIPTOR spritemask_outside, spritemask_pixels, 100, 20, 6, 8
FWK_SPRITE_DESCRIPTOR spritemask_invalid, 0xFFF0, 20, 48, 6, 8

spritemask_status:: .db 0

.area _CODE

;; ----------------------------------------------------------------------------
;; _spritemask_fail
;;   Failure sink for the masked-sprite test: records the failure code and idles forever.
;;   In : none (reached by jp from _main, not by call).
;;   Out: none; never returns (ends in an endless loop).
;;          Memory: spritemask_status = 0xEE.
;;   Clobbers: all (never returns)
;;   Notes: Does not return. Entered only by jp, so there is no return address on the stack to use.
;; ----------------------------------------------------------------------------
_spritemask_fail:
    ld a, #0xEE
    ld (spritemask_status), a
    ;; Idle forever so the harness can read spritemask_status.
_spritemask_fail_loop:
    call fwk_system_wait_frame
    jr _spritemask_fail_loop

;; ----------------------------------------------------------------------------
;; _main
;;   Colour-key sprite test: paints eight background bands, checks that bad sprites and bad recolour
;;   pens are rejected, then draws centred, clipped, recoloured and opaque-recoloured sprites.
;;   In : none (program entry; no register is read).
;;   Out: none; never returns (ends in an endless loop).
;;          Memory: spritemask_status = 0x5A when every check passed, 0xEE (via _spritemask_fail) on the first
;;          failed check; video RAM holds the bands and sprites.
;;   Clobbers: all (never returns)
;;   Notes: Does not return, so no register is preserved. Carry convention: fwk_sprite_* return carry set for
;;          invalid input. Needs project transparency enabled.
;; ----------------------------------------------------------------------------
_main::
    ;; System up (firmware off, IRQ on), Mode 0.
    call fwk_project_init
    call fwk_video_init
    ;; Pens 0, 5, 15 = black, bright yellow, bright cyan (L=pen, H=hardware colour).
    ld l, #0
    ld h, #0x14
    call cpct_setPALColour_asm
    ld l, #5
    ld h, #0x0A
    call cpct_setPALColour_asm
    ld l, #15
    ld h, #0x13
    call cpct_setPALColour_asm
    ;; Clear to pen 0.
    xor a
    call fwk_video_clear_visible

    ;; Eight horizontal background bands behind the centred sprite.
    ;; IY = band index 0..7 (added to y), B = bands left. Band i is the row y=48+i, bytes 18..39.
    ld iy, #0
    ld b, #8
_spritemask_band_row:
    push bc
    ;; HL = 48 + IY (y), C = 18 (x byte): start of this band's row.
    push iy
    pop hl
    ld de, #48
    add hl, de
    ld c, #18
    call fwk_video_get_ptr
    pop bc
    ;; Fill byte = 2*B + 0x10, so each row gets a different pattern; C = 22 bytes wide.
    ld a, b
    add a, a
    add a, #0x10
    ld c, #22
_spritemask_band_byte:
    ld (hl), a
    inc hl
    dec c
    jr nz, _spritemask_band_byte
    ;; Next row; djnz uses the B restored by pop bc.
    inc iy
    djnz _spritemask_band_row

    ;; Invalid source span is rejected before drawing.
    ld ix, #spritemask_invalid
    call fwk_sprite_draw_masked
    jp nc, _spritemask_fail

    ;; A wholly outside valid sprite succeeds without writing.
    ld ix, #spritemask_outside
    call fwk_sprite_draw_masked
    jp c, _spritemask_fail

    ;; Invalid recolour pens are rejected before touching video memory.
    ld ix, #spritemask_recolor
    ld d, #16
    ld e, #15
    call fwk_sprite_draw_masked_recolor
    jp nc, _spritemask_fail

    ;; Draw centred and clipped colour-key shapes with the shared table.
    ld ix, #spritemask_centre
    call fwk_sprite_draw_masked
    jp c, _spritemask_fail
    ld ix, #spritemask_clipped
    call fwk_sprite_draw_masked
    jp c, _spritemask_fail


    ;; Reuse the same asset and replace pen 5 (0xF0) with pen 15 (0xFF)
    ;; while retaining project pen 3 as the colour key.
    ld ix, #spritemask_recolor
    ld d, #5
    ld e, #15
    call fwk_sprite_draw_masked_recolor
    jp c, _spritemask_fail

    ;; The opaque recolour route replaces the same pen without colour-keying.
    ld ix, #spritemask_opaque_recolor
    ld d, #5
    ld e, #15
    call fwk_sprite_draw_recolor
    jp c, _spritemask_fail

    ld a, #0x5A
    ld (spritemask_status), a
_spritemask_loop:
    call fwk_system_wait_frame
    jr _spritemask_loop
