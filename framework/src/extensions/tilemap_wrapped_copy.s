;; Optional raster-bank-safe tile copy for shifted classic CPC origins.
.module fwk_tilemap_wrapped_copy
.globl fwk_video_get_ptr

.area _DATA
_fwk_tw_source: .dw 0
_fwk_tw_y: .dw 0
_fwk_tw_x: .db 0
_fwk_tw_width: .db 0
_fwk_tw_rows: .db 0

.area _CODE
;; In: HL=graphics, DE=screen y, A=screen x byte, B=width, C=height.
;; Out: carry clear. Modified: AF,BC,DE,HL. IX/IY preserved.
fwk_tilemap_copy_wrapped::
    ld (_fwk_tw_source), hl
    ld (_fwk_tw_y), de
    ld (_fwk_tw_x), a
    ld a, b
    ld (_fwk_tw_width), a
    ld a, c
    ld (_fwk_tw_rows), a
_fwk_tw_row:
    ld hl, (_fwk_tw_y)
    ld a, (_fwk_tw_x)
    ld c, a
    call fwk_video_get_ptr
    ex de, hl
    ld hl, (_fwk_tw_source)
    ld a, (_fwk_tw_width)
    ld c, a
    ld b, #0
    ldir
    ld (_fwk_tw_source), hl
    ld hl, (_fwk_tw_y)
    inc hl
    ld (_fwk_tw_y), hl
    ld a, (_fwk_tw_rows)
    dec a
    ld (_fwk_tw_rows), a
    jr nz, _fwk_tw_row
    or a
    ret
