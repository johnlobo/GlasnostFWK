;; Generic compacting fixed-capacity pool. It imposes no entity layout.
.module fwk_pool
.include "core/pool.inc"

.area _CODE

;; fwk_pool_init
;; In: IX=descriptor. Out: count=0. Modified: A.
fwk_pool_init::
    xor a
    ld FWK_POOL_COUNT(ix), a
    ret

;; fwk_pool_get
;; In: IX=descriptor, A=index. Out: HL=element, carry clear; carry set invalid.
;; Modified: AF,B,DE,HL.
fwk_pool_get::
    cp FWK_POOL_COUNT(ix)
    jr nc, _fwk_pool_invalid
    ld b, a
    ld l, FWK_POOL_BASE_LO(ix)
    ld h, FWK_POOL_BASE_HI(ix)
    ld e, FWK_POOL_ELEMENT_SIZE(ix)
    ld d, #0
_fwk_pool_get_loop:
    ld a, b
    or a
    jr z, _fwk_pool_valid
    add hl, de
    dec b
    jr _fwk_pool_get_loop
_fwk_pool_valid:
    or a
    ret
_fwk_pool_invalid:
    scf
    ret

;; fwk_pool_alloc
;; In: IX=descriptor. Out: HL=new slot and carry clear; carry set when full.
;; Slot contents are unchanged. Modified: AF,B,DE,HL.
fwk_pool_alloc::
    ld a, FWK_POOL_COUNT(ix)
    cp FWK_POOL_CAPACITY(ix)
    jr nc, _fwk_pool_invalid
    push af
    inc FWK_POOL_COUNT(ix)
    pop af
    jp fwk_pool_get

;; fwk_pool_remove
;; In: IX=descriptor, A=index. Out: carry clear, following records compacted;
;; carry set for invalid index. Modified: AF,BC,DE,HL.
fwk_pool_remove::
    ld (_fwk_pool_remove_index + 1), a
    cp FWK_POOL_COUNT(ix)
    jr nc, _fwk_pool_invalid
    dec FWK_POOL_COUNT(ix)
    ld b, FWK_POOL_COUNT(ix)
_fwk_pool_remove_index:
    ld a, #0
    sub b
    neg
    ld b, a                         ;; number of records after removed slot
    or a
    ret z
    ld a, b
    ld (_fwk_pool_records_left + 1), a
    ld a, (_fwk_pool_remove_index + 1)
    call fwk_pool_get                ;; count is now one smaller: last old index
    ;; Index can equal new count only when removing old last, already returned.
    ex de, hl                        ;; DE=destination
    ld l, e
    ld h, d
    ld a, FWK_POOL_ELEMENT_SIZE(ix)
    add a, l
    ld l, a
    jr nc, _fwk_pool_source_ready
    inc h
_fwk_pool_source_ready:
    push de
    ld c, FWK_POOL_ELEMENT_SIZE(ix)
    ld b, #0
    ld de, #0
_fwk_pool_size_loop:
_fwk_pool_records_left:
    ld a, #0
    or a
    jr z, _fwk_pool_size_done
    dec a
    ld (_fwk_pool_records_left + 1), a
    ld a, e
    add c
    ld e, a
    jr nc, _fwk_pool_size_loop
    inc d
    jr _fwk_pool_size_loop
_fwk_pool_size_done:
    ld b, d
    ld c, e                         ;; BC=bytes to move
    pop de                          ;; DE=destination, HL=source
    ldir
    or a
    ret

;; fwk_pool_foreach
;; In: IX=descriptor, DE=callback. Callback gets IY=element.
;; Out: none. Modified: AF,BC,DE,HL,IY. Callback may modify main registers.
;; Uses a self-modified CALL and is not reentrant or interrupt-safe.
fwk_pool_foreach::
    ld (_fwk_pool_callback + 1), de
    ld b, FWK_POOL_COUNT(ix)
    ld l, FWK_POOL_BASE_LO(ix)
    ld h, FWK_POOL_BASE_HI(ix)
    push hl
    pop iy
_fwk_pool_foreach_loop:
    ld a, b
    or a
    ret z
    push bc
    push ix
    push iy
_fwk_pool_callback:
    call 0
    pop iy
    pop ix
    pop bc
    ld e, FWK_POOL_ELEMENT_SIZE(ix)
    ld d, #0
    add iy, de
    dec b
    jr _fwk_pool_foreach_loop
