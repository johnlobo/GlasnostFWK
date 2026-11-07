.module example_spriteclip
.include "video/sprite.inc"

.globl fwk_project_init, fwk_system_wait_frame
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

;; ----------------------------------------------------------------------------
;; _spriteclip_fail
;;   Failure sink for the sprite-clip test: records the failure code and idles forever.
;;   In : none (reached by jp from _main, not by call).
;;   Out: none; never returns (ends in an endless loop).
;;          Memory: spriteclip_status = 0xEE.
;;   Clobbers: all (never returns)
;;   Notes: Does not return. Entered only by jp, so there is no return address on the stack to use.
;; ----------------------------------------------------------------------------
_spriteclip_fail:
    ld a, #0xEE
    ld (spriteclip_status), a
    ;; Idle forever so the harness can read spriteclip_status.
_spriteclip_fail_loop:
    call fwk_system_wait_frame
    jr _spriteclip_fail_loop

;; ----------------------------------------------------------------------------
;; _spriteclip_write_background
;;   Writes a nonuniform 4x5-byte background into the visible part of the sprite at
;;   (-2,-3) size 6x8, i.e. columns 0..3 of rows 0..4, so a restore can be told apart from a redraw.
;;   In : none (source is spriteclip_background, 20 bytes).
;;   Out: IY = end of spriteclip_background; B = 0; HL = 5; video RAM rows 0..4, bytes 0..3 written.
;;   Clobbers: AF, B, DE, HL, IY
;;   Notes: C and IX are preserved (C is restored by pop bc, so only B ends changed). Calls fwk_video_get_ptr
;;          (modifies AF, DE, HL), so the row counter in BC and the y in HL are saved on the stack around it.
;; ----------------------------------------------------------------------------
_spriteclip_write_background:
    ;; IY = source cursor, HL = row y (16 bit), B = rows left.
    ld iy, #spriteclip_background
    ld hl, #0
    ld b, #5
_spriteclip_background_row:
    ;; Row loop; BC is saved because ldir zeroes it and C is reused as the x argument.
    push bc
    push hl
    ;; Screen address of (x=0, y=row).
    ld c, #0
    call fwk_video_get_ptr
    ;; DE = destination; HL = source; copy one 4-byte row and carry the advanced source back into IY.
    ex de, hl
    push iy
    pop hl
    ld bc, #4
    ldir
    push hl
    pop iy
    pop hl
    ;; Next row, restore the row counter.
    inc hl
    pop bc
    djnz _spriteclip_background_row
    ret

;; ----------------------------------------------------------------------------
;; _main
;;   Sprite-clipping test: validates that bad descriptors are rejected, captures, draws and restores a
;;   sprite clipped at the top-left corner, then leaves one sprite per clipped edge plus a full one.
;;   In : none (program entry; no register is read).
;;   Out: none; never returns (ends in an endless loop).
;;          Memory: spriteclip_status = 0x5A when every check passed, 0xEE (via _spriteclip_fail) on the first
;;          failed check; spriteclip_capture_used = bytes the capture consumed (expected 20).
;;   Clobbers: all (never returns)
;;   Notes: Does not return, so no register is preserved. Carry convention: fwk_sprite_* return carry set for
;;          invalid geometry or data span; the checks below use jp nc / jp c to _spriteclip_fail.
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
    ;; Clear to pen 0 and install the 4x5 background in the top-left corner.
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
    ;; Guard byte 0x55 at the last column of row 100 (the row of the off-screen sprite).
    ;; It is never read back here; it stays on screen for whoever inspects the result.
    ld hl, #100
    ld c, #79
    ld a, #0x55
    call fwk_video_plot_byte
    ;; Wholly off-screen but valid: must succeed (carry clear) and draw nothing.
    ld ix, #spriteclip_outside_sprite
    call fwk_sprite_draw
    jp c, _spriteclip_fail

    ;; Capture/draw/restore a sprite clipped on both top and left edges.
    ld ix, #spriteclip_restore_sprite
    ld de, #spriteclip_buffer
    call fwk_sprite_capture
    jp c, _spriteclip_fail
    ;; IY = end of captured data. Used = IY - buffer; it must be exactly 20 (4 columns x 5 rows).
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
    ;; Draw over the background, then restore it from the buffer.
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

    ;; All checks passed.
    ld a, #0x5A
    ld (spriteclip_status), a
    ;; Idle forever.
_spriteclip_loop:
    call fwk_system_wait_frame
    jr _spriteclip_loop
