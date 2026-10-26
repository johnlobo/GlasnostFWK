;; Read-only tilemap queries with consumer-owned data and collision types.
.module fwk_tilemap
.include "extensions/tilemap.inc"

.area _CODE

;; fwk_tilemap_query
;; In: IX=11-byte descriptor, B=world Y, C=world X.
;; Out: A=consumer collision type and carry clear for a valid tile. A=0 and
;;      carry set for coordinates outside the map or a tile id outside the
;;      declared type table. Z follows A.
;; Modified: AF,DE,HL. BC and IX/IY preserved. Reentrant for immutable data.
fwk_tilemap_query::
    push bc

    ld a, FWK_TILEMAP_WIDTH(ix)
    or a
    jr z, _fwk_tilemap_invalid
    ld a, FWK_TILEMAP_HEIGHT(ix)
    or a
    jr z, _fwk_tilemap_invalid
    ld a, FWK_TILEMAP_X_SIZE(ix)
    or a
    jr z, _fwk_tilemap_invalid
    ld a, FWK_TILEMAP_Y_SIZE(ix)
    or a
    jr z, _fwk_tilemap_invalid
    ld a, FWK_TILEMAP_TYPE_COUNT(ix)
    or a
    jr z, _fwk_tilemap_invalid

    ld a, FWK_TILEMAP_Y_SHIFT(ix)
    cp #8
    jr nc, _fwk_tilemap_invalid
    ld d, a
_fwk_tilemap_shift_y:
    ld a, d
    or a
    jr z, _fwk_tilemap_y_ready
    srl b
    dec d
    jr _fwk_tilemap_shift_y
_fwk_tilemap_y_ready:
    ld a, b
    cp FWK_TILEMAP_HEIGHT(ix)
    jr nc, _fwk_tilemap_invalid

    ld a, FWK_TILEMAP_X_SHIFT(ix)
    cp #8
    jr nc, _fwk_tilemap_invalid
    ld d, a
_fwk_tilemap_shift_x:
    ld a, d
    or a
    jr z, _fwk_tilemap_x_ready
    srl c
    dec d
    jr _fwk_tilemap_shift_x
_fwk_tilemap_x_ready:
    ld a, c
    cp FWK_TILEMAP_WIDTH(ix)
    jr nc, _fwk_tilemap_invalid

    ;; HL = row * width + column.
    ld a, b
    ld de, #0
    ld e, FWK_TILEMAP_WIDTH(ix)
    ld hl, #0
    or a
    jr z, _fwk_tilemap_row_ready
    ld b, a
_fwk_tilemap_row_loop:
    add hl, de
    djnz _fwk_tilemap_row_loop
_fwk_tilemap_row_ready:
    ld e, c
    ld d, #0
    add hl, de
    ld e, FWK_TILEMAP_DATA(ix)
    ld d, FWK_TILEMAP_DATA+1(ix)
    add hl, de

    ld a, (hl)
    cp FWK_TILEMAP_TYPE_COUNT(ix)
    jr nc, _fwk_tilemap_invalid
    ld e, a
    ld d, #0
    ld l, FWK_TILEMAP_TYPES(ix)
    ld h, FWK_TILEMAP_TYPES+1(ix)
    add hl, de
    ld a, (hl)
    pop bc
    or a
    ret

_fwk_tilemap_invalid:
    pop bc
    xor a
    scf
    ret
