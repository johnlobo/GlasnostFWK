;; Project-configured Mode 0 colour-key transparency.
.module fwk_transparency
.include "cpctelera.h.s"
.include "project_config.inc"

.if FWK_TRANSPARENCY_ENABLED

.area _DATA
_fwk_transparency_width: .db 0

.area _CODE

;; fwk_transparency_draw
;; In: BC=source, DE=screen, IXL=width bytes, IXH=height scanlines.
;; Uses the project table at FWK_TRANSPARENCY_TABLE implicitly. The configured
;; pen is removed from the source before composition, so pens 0..15 work.
;; Width and height must be non-zero; there is no clipping or span validation.
;; Modified: AF,BC,DE,HL,IX. Not reentrant (one-byte scratch).
fwk_transparency_draw::
    ld__a_ixl
    ld (_fwk_transparency_width), a
_fwk_transparency_row:
    push de
_fwk_transparency_byte:
    ld a, (bc)
    ld l, a
    ld h, #(FWK_TRANSPARENCY_TABLE >> 8)
    ld a, (de)
    and (hl)
    push af
    ld a, (hl)
    cpl
    and l
    ld h, a
    pop af
    or h
    ld (de), a
    inc bc
    inc de
    dec__ixl
    jr nz, _fwk_transparency_byte

    pop de
    dec__ixh
    ret z
    ld a, (_fwk_transparency_width)
    ld__ixl_a
    ld a, d
    add #0x08
    ld d, a
    and #0x38
    jr nz, _fwk_transparency_row
    ld a, e
    add #0x50
    ld e, a
    ld a, d
    adc #0xC0
    ld d, a
    jr _fwk_transparency_row

.endif
