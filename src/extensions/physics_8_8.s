;; Optional 8.8 bounded integrator. State and tuning belong to the consumer.
.module fwk_physics_8_8
.include "extensions/physics_8_8.inc"

.area _DATA
_fwk_phys88_major: .dw 0
_fwk_phys88_minor: .dw 0
_fwk_phys88_ax: .dw 0
_fwk_phys88_ay: .dw 0

.area _CODE

;; fwk_physics_8_8_step
;; In: IY=9-byte state; IX=5-byte bounds/friction descriptor.
;; Positions and velocities are signed 8.8, stored low byte first.
;; Out: friction applied along the velocity vector, position integrated and
;;      each axis clamped/bounced inside inclusive pixel bounds.
;; Modified: AF,BC,DE,HL. IX/IY preserved. Not reentrant (shared scratch).
fwk_physics_8_8_step::
    call _fwk_phys88_friction

    ld e, FWK_PHYS88_VX(iy)
    ld d, FWK_PHYS88_VX+1(iy)
    ld l, FWK_PHYS88_X(iy)
    ld h, FWK_PHYS88_X+1(iy)
    add hl, de
    bit 7, d
    jr z, _fwk_phys88_x_positive
    jr nc, _fwk_phys88_x_low
    ld a, h
    cp FWK_PHYS88_MIN_X(ix)
    jr c, _fwk_phys88_x_low
    jr _fwk_phys88_x_store
_fwk_phys88_x_positive:
    jr c, _fwk_phys88_x_high
    ld a, h
    cp FWK_PHYS88_MAX_X(ix)
    jr c, _fwk_phys88_x_store
    jr z, _fwk_phys88_x_store
_fwk_phys88_x_high:
    ld a, FWK_PHYS88_MAX_X(ix)
    jr _fwk_phys88_x_clamp
_fwk_phys88_x_low:
    ld a, FWK_PHYS88_MIN_X(ix)
_fwk_phys88_x_clamp:
    ld h, a
    ld l, #0
    call _fwk_phys88_neg_de
    ld FWK_PHYS88_VX(iy), e
    ld FWK_PHYS88_VX+1(iy), d
_fwk_phys88_x_store:
    ld FWK_PHYS88_X(iy), l
    ld FWK_PHYS88_X+1(iy), h

    ld e, FWK_PHYS88_VY(iy)
    ld d, FWK_PHYS88_VY+1(iy)
    ld l, FWK_PHYS88_Y(iy)
    ld h, FWK_PHYS88_Y+1(iy)
    add hl, de
    bit 7, d
    jr z, _fwk_phys88_y_positive
    jr nc, _fwk_phys88_y_low
    ld a, h
    cp FWK_PHYS88_MIN_Y(ix)
    jr c, _fwk_phys88_y_low
    jr _fwk_phys88_y_store
_fwk_phys88_y_positive:
    jr c, _fwk_phys88_y_high
    ld a, h
    cp FWK_PHYS88_MAX_Y(ix)
    jr c, _fwk_phys88_y_store
    jr z, _fwk_phys88_y_store
_fwk_phys88_y_high:
    ld a, FWK_PHYS88_MAX_Y(ix)
    jr _fwk_phys88_y_clamp
_fwk_phys88_y_low:
    ld a, FWK_PHYS88_MIN_Y(ix)
_fwk_phys88_y_clamp:
    ld h, a
    ld l, #0
    call _fwk_phys88_neg_de
    ld FWK_PHYS88_VY(iy), e
    ld FWK_PHYS88_VY+1(iy), d
_fwk_phys88_y_store:
    ld FWK_PHYS88_Y(iy), l
    ld FWK_PHYS88_Y+1(iy), h
    ret

;; Linear friction preserves the direction of diagonal motion. A zero value in
;; the descriptor disables friction. The fractional remainder is state-owned.
_fwk_phys88_friction:
    ld a, FWK_PHYS88_VX(iy)
    or FWK_PHYS88_VX+1(iy)
    or FWK_PHYS88_VY(iy)
    or FWK_PHYS88_VY+1(iy)
    ret z
    ld a, FWK_PHYS88_FRICTION(ix)
    or a
    ret z

    ld l, FWK_PHYS88_VX(iy)
    ld h, FWK_PHYS88_VX+1(iy)
    call _fwk_phys88_abs_hl
    ld (_fwk_phys88_ax), hl
    ld l, FWK_PHYS88_VY(iy)
    ld h, FWK_PHYS88_VY+1(iy)
    call _fwk_phys88_abs_hl
    ld (_fwk_phys88_ay), hl
    ld de, (_fwk_phys88_ax)
    or a
    sbc hl, de
    jr c, _fwk_phys88_x_major
    jr z, _fwk_phys88_x_major
    ld hl, (_fwk_phys88_ay)
    ld de, (_fwk_phys88_ax)
    call _fwk_phys88_reduce
    ld (_fwk_phys88_ay), hl
    ld (_fwk_phys88_ax), de
    jr _fwk_phys88_friction_store
_fwk_phys88_x_major:
    ld hl, (_fwk_phys88_ax)
    ld de, (_fwk_phys88_ay)
    call _fwk_phys88_reduce
    ld (_fwk_phys88_ax), hl
    ld (_fwk_phys88_ay), de
_fwk_phys88_friction_store:
    ld hl, (_fwk_phys88_ax)
    bit 7, FWK_PHYS88_VX+1(iy)
    call nz, _fwk_phys88_neg_hl
    ld FWK_PHYS88_VX(iy), l
    ld FWK_PHYS88_VX+1(iy), h
    ld hl, (_fwk_phys88_ay)
    bit 7, FWK_PHYS88_VY+1(iy)
    call nz, _fwk_phys88_neg_hl
    ld FWK_PHYS88_VY(iy), l
    ld FWK_PHYS88_VY+1(iy), h
    ret

_fwk_phys88_abs_hl:
    bit 7, h
    ret z
_fwk_phys88_neg_hl:
    ld a, l
    cpl
    ld l, a
    ld a, h
    cpl
    ld h, a
    inc hl
    ret

;; In: HL=major magnitude (>0), DE=minor magnitude (<=major).
;; Out: HL=reduced major, DE=reduced minor.
_fwk_phys88_reduce:
    ld (_fwk_phys88_major), hl
    ld (_fwk_phys88_minor), de
    or a
    sbc hl, de
    jr nz, _fwk_phys88_divide
    ld h, FWK_PHYS88_FRICTION(ix)
    ld l, #0
    jr _fwk_phys88_share
_fwk_phys88_divide:
    ld hl, (_fwk_phys88_minor)
    ld de, (_fwk_phys88_major)
    ld bc, #0x0800
_fwk_phys88_div_loop:
    add hl, hl
    or a
    sbc hl, de
    jr nc, _fwk_phys88_div_one
    add hl, de
    sla c
    jr _fwk_phys88_div_next
_fwk_phys88_div_one:
    scf
    rl c
_fwk_phys88_div_next:
    djnz _fwk_phys88_div_loop
    ld e, c
    ld d, #0
    ld hl, #0
    ld b, FWK_PHYS88_FRICTION(ix)
_fwk_phys88_mul:
    add hl, de
    djnz _fwk_phys88_mul
_fwk_phys88_share:
    ld e, FWK_PHYS88_FRACTION(iy)
    ld d, #0
    add hl, de
    ld FWK_PHYS88_FRACTION(iy), l
    ld e, h
    ld d, #0
    ld hl, (_fwk_phys88_minor)
    or a
    sbc hl, de
    jr nc, _fwk_phys88_minor_ok
    ld hl, #0
_fwk_phys88_minor_ok:
    ld (_fwk_phys88_minor), hl
    ld hl, (_fwk_phys88_major)
    ld e, FWK_PHYS88_FRICTION(ix)
    ld d, #0
    or a
    sbc hl, de
    jr c, _fwk_phys88_stop
    jr z, _fwk_phys88_stop
    ld de, (_fwk_phys88_minor)
    ret
_fwk_phys88_stop:
    ld hl, #0
    ld de, #0
    ld FWK_PHYS88_FRACTION(iy), #0
    ret

_fwk_phys88_neg_de:
    ld a, e
    cpl
    ld e, a
    ld a, d
    cpl
    ld d, a
    inc de
    ret
