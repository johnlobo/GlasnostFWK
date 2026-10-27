;; AABB collision helpers for entity pools with caller-defined field offsets.
.module fwk_collision_bodies
.include "core/pool.inc"
.include "extensions/collision_bodies.inc"

.globl fwk_pool_get

.area _DATA
_fwk_collision_a:: .dw 0
_fwk_collision_b:: .dw 0
_fwk_collision_cb:: .dw 0
_fwk_collision_xoff:: .db 0
_fwk_collision_yoff:: .db 0
_fwk_collision_wooff:: .db 0
_fwk_collision_hoff:: .db 0
_fca_ax:: .db 0
_fca_ay:: .db 0
_fca_aw:: .db 0
_fca_ah:: .db 0
_fca_bx:: .db 0
_fca_by:: .db 0
_fca_bw:: .db 0
_fca_bh:: .db 0

.area _CODE

;; Helper: read byte at base HL + offset A -> A.
_fwk_collision_read::
    add a, l
    ld l, a
    jr nc, _fcr_ready
    inc h
_fcr_ready:
    ld a, (hl)
    ret

;; fwk_collision_aabb
;; In: HL=entity A, DE=entity B, B=xoff, C=yoff, D=woff, E=hoff.
;; Out: carry set if the two AABBs overlap.
;; Modified: AF, (temp globals).
fwk_collision_aabb::
    push de
    push bc
    push hl              ; A base

    ; Read A fields.
    ld a, b
    pop hl
    push hl
    call _fwk_collision_read
    ld (_fca_ax), a

    ld a, c
    pop hl
    push hl
    call _fwk_collision_read
    ld (_fca_ay), a

    ld a, d
    pop hl
    push hl
    call _fwk_collision_read
    ld (_fca_aw), a

    ld a, e
    pop hl
    push hl
    call _fwk_collision_read
    ld (_fca_ah), a

    ; Read B fields.
    pop hl              ; discard A base
    pop bc
    pop de
    push de
    push bc

    ld a, b
    ex de, hl
    call _fwk_collision_read
    ld (_fca_bx), a

    ld a, c
    ex de, hl
    push de
    ex de, hl
    call _fwk_collision_read
    ld (_fca_by), a
    pop de

    ld a, d
    ex de, hl
    call _fwk_collision_read
    ld (_fca_bw), a

    ld a, e
    ex de, hl
    call _fwk_collision_read
    ld (_fca_bh), a

    pop bc
    pop de

    ; Overlap test (unsigned 8-bit, small entities).
    ; if ax + aw <= bx -> no
    ld a, (_fca_ax)
    ld hl, #_fca_aw
    add a, (hl)
    jr c, _fca_check2     ; overflow means overlap possible
    ld hl, #_fca_bx
    cp (hl)
    jr z, _fca_no
    jr c, _fca_no
_fca_check2:
    ; if bx + bw <= ax -> no
    ld a, (_fca_bx)
    ld hl, #_fca_bw
    add a, (hl)
    jr c, _fca_check3
    ld hl, #_fca_ax
    cp (hl)
    jr z, _fca_no
    jr c, _fca_no
_fca_check3:
    ; if ay + ah <= by -> no
    ld a, (_fca_ay)
    ld hl, #_fca_ah
    add a, (hl)
    jr c, _fca_check4
    ld hl, #_fca_by
    cp (hl)
    jr z, _fca_no
    jr c, _fca_no
_fca_check4:
    ; if by + bh <= ay -> no
    ld a, (_fca_by)
    ld hl, #_fca_bh
    add a, (hl)
    jr c, _fca_yes
    ld hl, #_fca_ay
    cp (hl)
    jr z, _fca_no
    jr c, _fca_no
_fca_yes:
    scf
    ret
_fca_no:
    or a
    ret

;; fwk_collision_pool
;; In: IX=pool descriptor, B=xoff, C=yoff, D=woff, E=hoff, HL=callback.
;;     Callback is called with IY=first entity and DE=second entity when a pair
;;     overlaps (carry set from fwk_collision_aabb). The callback may modify
;;     main registers.
;; Out: none.
fwk_collision_pool::
    ld (_fwk_collision_xoff), bc  ; store xoff,yoff (B,C) -- careful: bc has xoff,yoff
    ; Actually store separately:
    ld a, b
    ld (_fwk_collision_xoff), a
    ld a, c
    ld (_fwk_collision_yoff), a
    ld a, d
    ld (_fwk_collision_wooff), a
    ld a, e
    ld (_fwk_collision_hoff), a
    ld (_fwk_collision_cb), hl

    ld a, FWK_POOL_COUNT(ix)
    cp #2
    jr c, _fcp_done
    ld (_fcp_outer_limit + 1), a

    ld b, #0
_fcp_outer:
    ld a, b
_fcp_outer_limit:
    cp #0
    jr nc, _fcp_done
    ; i = b
    push bc
    ld a, b
    call fwk_pool_get
    jr c, _fcp_outer_next
    push hl
    pop iy                ; IY = entity i
    ld (_fwk_collision_a), hl

    ld a, (_fcp_outer_limit + 1)
    ld c, a
    pop bc
    push bc
    ld a, b
    inc a
    ld d, a               ; j start
_fcp_inner:
    ld a, d
    cp c
    jr nc, _fcp_outer_next2
    push bc
    push de
    ld a, d
    call fwk_pool_get
    jr c, _fcp_inner_next
    ld (_fwk_collision_b), hl
    ; test aabb
    ld hl, (_fwk_collision_a)
    ex de, hl             ; DE = A? Wait fwk_collision_aabb expects HL=A, DE=B
    ; We have A in _fwk_collision_a, B in _fwk_collision_b (hl). Set HL=A, DE=B.
    ld hl, (_fwk_collision_a)
    ld de, (_fwk_collision_b)
    ld a, (_fwk_collision_xoff)
    ld b, a
    ld a, (_fwk_collision_yoff)
    ld c, a
    ld a, (_fwk_collision_wooff)
    ld d, a
    ld a, (_fwk_collision_hoff)
    ld e, a
    call fwk_collision_aabb
    jr nc, _fcp_inner_next
    ; collision: call callback with IY=A, DE=B
    ld hl, (_fwk_collision_cb)
    ld a, h
    or l
    jr z, _fcp_inner_next
    ld de, (_fwk_collision_b)
    push iy
    pop hl
    ex de, hl             ; DE=B, HL=A? callback expects IY=A, DE=B
    push de
    ex de, hl
    push hl
    pop iy
    pop de
    ld hl, (_fwk_collision_cb)
    call _fwk_collision_call
_fcp_inner_next:
    pop de
    pop bc
    inc d
    jr _fcp_inner

_fcp_outer_next2:
    pop bc
_fcp_outer_next:
    pop bc
    inc b
    jr _fcp_outer

_fcp_done:
    ret

_fwk_collision_call::
    jp (hl)