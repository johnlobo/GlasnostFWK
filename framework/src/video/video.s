;; Geometry-driven Mode 0/1 addressing and visible-region clearing.
.module fwk_video

.include "cpctelera.h.s"
FWK_VIDEO_EMIT_TABLES = 1
.include "video_config.inc"
.globl cpct_setVideoMode_asm
.globl cpct_setCRTCReg_asm
.globl cpct_setVideoMemoryPage_asm

.area _DATA
fwk_video_width_bytes:: .db FWK_VIDEO_WIDTH_BYTES
fwk_video_height:: .dw FWK_VIDEO_HEIGHT
.if FWK_VIDEO_RASTER_BANK_WRAP_2K
;; Physical byte offset within each 2 KiB raster bank. Set only at a CRTC
;; origin commit; the generated line table stays at its fixed profile base.
fwk_video_origin_bytes:: .dw 0
.endif

.area _CODE

;; fwk_video_init
;; In: none. Out: profile video mode selected. Modified: AF,BC,DE,HL.
;; CRTC timing is intentionally configured separately for experimental profiles.
fwk_video_init::
    ld c, #FWK_VIDEO_MODE
    jp cpct_setVideoMode_asm

;; fwk_video_configure_crtc
;; In: none. Out: generated CRTC registers/page command applied.
;; Modified: AF,BC,DE,HL,IX. Experimental timing remains explicitly unverified.
fwk_video_configure_crtc::
    ld ix, #fwk_video_crtc_table
    ld a, #FWK_VIDEO_CRTC_REG_COUNT
    or a
    jr z, _fwk_video_crtc_page
_fwk_video_crtc_loop:
    push af
    ld c, 0(ix)
    ld b, 1(ix)
    call cpct_setCRTCReg_asm
    ld de, #2
    add ix, de
    pop af
    dec a
    jr nz, _fwk_video_crtc_loop
_fwk_video_crtc_page:
    .if FWK_VIDEO_HAS_PAGE_COMMAND
    ld l, #FWK_VIDEO_PAGE_COMMAND
    jp cpct_setVideoMemoryPage_asm
    .else
    ret
    .endif

;; fwk_video_get_ptr
;; In: HL=y (16 bit), C=x byte. Out: HL=screen address.
;; Modified: AF,DE,HL. Caller must keep x/y inside generated geometry.
fwk_video_get_ptr::
    add hl, hl
    ld de, #fwk_video_line_table
    add hl, de
    ld e, (hl)
    inc hl
    ld d, (hl)
.if FWK_VIDEO_RASTER_BANK_WRAP_2K
    ld a, d
    and #0xF8
    push af
    ex de, hl
    push bc
    ld bc, (fwk_video_origin_bytes)
    add hl, bc
    pop bc
    ld a, l
    add c
    ld l, a
    jr nc, _fwk_video_ptr_wrap
    inc h
_fwk_video_ptr_wrap:
    pop af
    ld d, a
    ld a, h
    and #7
    or d
    ld h, a
    ret
.else
    ld a, e
    add c
    ld e, a
    jr nc, _fwk_video_ptr_ready
    inc d
_fwk_video_ptr_ready:
    ex de, hl
    ret
.endif

;; fwk_video_plot_byte
;; In: HL=y, C=x byte, A=packed video byte. Out: byte written.
;; Modified: AF,DE,HL.
fwk_video_plot_byte::
    push af
    call fwk_video_get_ptr
    pop af
    ld (hl), a
    ret

;; fwk_video_clear_visible
;; In: A=fill byte. Out: only generated visible regions changed; holes kept.
;; Modified: AF,BC,DE,HL,IX. Not interrupt-sensitive.
fwk_video_clear_visible::
    ld ix, #fwk_video_visible_regions
_fwk_video_clear_region:
    ld l, 0(ix)
    ld h, 1(ix)
    ld c, 2(ix)
    ld b, 3(ix)
    ld e, a
    ld a, b
    or c
    ret z
    ld a, e
_fwk_video_clear_loop:
    ld (hl), a
    inc hl
    dec bc
    ld d, a
    ld a, b
    or c
    ld a, d
    jr nz, _fwk_video_clear_loop
    ld de, #4
    add ix, de
    jr _fwk_video_clear_region
