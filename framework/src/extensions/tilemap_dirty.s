;; Dirty-rectangle helper for rectangular tilemap views.
.module fwk_tilemap_dirty
.include "extensions/tilemap_dirty.inc"
.include "extensions/tilemap_render.inc"

.globl fwk_tilemap_render_cell

.area _DATA
_fwk_td_dirty:: .dw 0

.area _CODE

;; fwk_tilemap_dirty_bind
;; In: HL=dirty descriptor. Out: none.
fwk_tilemap_dirty_bind::
    ld (_fwk_td_dirty), hl
    ret

;; fwk_tilemap_dirty_init
;; In: HL=dirty descriptor. Out: count=0.
fwk_tilemap_dirty_init::
    call fwk_tilemap_dirty_bind
    ld hl, (_fwk_td_dirty)
    inc hl              ; count field
    xor a
    ld (hl), a
    ret

;; fwk_tilemap_dirty_clear
;; In: none (uses bound descriptor). Out: count=0.
fwk_tilemap_dirty_clear::
    ld hl, (_fwk_td_dirty)
    ld a, h
    or l
    ret z
    inc hl
    xor a
    ld (hl), a
    ret

;; fwk_tilemap_dirty_mark
;; In: B=row, C=col. Out: carry set if the list is full.
fwk_tilemap_dirty_mark::
    ld hl, (_fwk_td_dirty)
    ld a, h
    or l
    jr z, _fwk_td_mark_fail
    ld a, (hl)          ; capacity
    ld d, a
    inc hl
    ld a, (hl)          ; count
    cp d
    jr nc, _fwk_td_mark_fail
    inc hl
    inc hl              ; cells pointer
    ld e, (hl)
    inc hl
    ld d, (hl)
    ; DE = cells base; advance by count*2
    ld hl, (_fwk_td_dirty)
    inc hl
    ld a, (hl)          ; count
    ld l, a
    ld h, #0
    add hl, hl
    add hl, de
    ld (hl), b
    inc hl
    ld (hl), c
    ; increment count
    ld hl, (_fwk_td_dirty)
    inc hl
    ld a, (hl)
    inc a
    ld (hl), a
    or a
    ret
_fwk_td_mark_fail:
    scf
    ret

;; fwk_tilemap_dirty_flush
;; In: IX=tilemap descriptor, IY=render descriptor.
;; Out: carry as render_cell. Clears the dirty list afterwards.
fwk_tilemap_dirty_flush::
    push ix
    push iy
    ld hl, (_fwk_td_dirty)
    ld a, h
    or l
    jr z, _fwk_td_flush_done
    inc hl
    ld b, (hl)          ; count
    inc hl
    inc hl              ; cells pointer
    ld e, (hl)
    inc hl
    ld d, (hl)
    ld hl, #0
    ; iterate
_fwk_td_flush_loop:
    ld a, b
    or a
    jr z, _fwk_td_flush_clear
    ld a, (de)          ; row
    ld ( _fwk_td_row_tmp ), a
    inc de
    ld a, (de)          ; col
    ld ( _fwk_td_col_tmp ), a
    inc de
    push bc
    push de
    ld a, (_fwk_td_row_tmp)
    ld b, a
    ld a, (_fwk_td_col_tmp)
    ld c, a
    call fwk_tilemap_render_cell
    pop de
    pop bc
    jr c, _fwk_td_flush_fail
    dec b
    jr _fwk_td_flush_loop

_fwk_td_flush_clear:
    call fwk_tilemap_dirty_clear
_fwk_td_flush_done:
    pop iy
    pop ix
    or a
    ret

_fwk_td_flush_fail:
    pop iy
    pop ix
    scf
    ret

.area _DATA
_fwk_td_row_tmp:: .db 0
_fwk_td_col_tmp:: .db 0