;; Optional compact motion profile. It is deliberately not the framework's
;; universal entity format; games with 8.8 physics use a different extension.
.module fwk_motion_u8
.include "extensions/motion_u8.inc"

.area _CODE

;; fwk_motion_u8_step
;; In: IY=5-byte record x,y,vx,vy,flags. Signed 8-bit velocity.
;; Out: x/y advanced with saturating bounds 0..79 and 0..199.
;; Modified: AF,BC. Reentrant and interrupt-safe if record is not shared.
;; The position is unsigned and the velocity signed, so the sum is saturated
;; from the carry and the velocity sign, not from the sign of the result (that
;; would treat every position from 128 up as negative and send it to zero).
fwk_motion_u8_step::
    ld a, FWK_MOTION_VX(iy)
    ld c, a
    ld a, FWK_MOTION_X(iy)
    ld b, #80
    call _fwk_motion_axis
    ld FWK_MOTION_X(iy), a
    ld a, FWK_MOTION_VY(iy)
    ld c, a
    ld a, FWK_MOTION_Y(iy)
    ld b, #200
    call _fwk_motion_axis
    ld FWK_MOTION_Y(iy), a
    ret

;; In: A=position, C=signed velocity, B=limit (exclusive). Out: A in 0..B-1.
_fwk_motion_axis:
    add a, c
    jr c, _fwk_motion_axis_carry
    bit 7, c
    jr z, _fwk_motion_axis_limit            ; moved forward, no overflow
    xor a                                   ; moved back below zero
    ret
_fwk_motion_axis_carry:
    bit 7, c
    jr z, _fwk_motion_axis_high             ; moved forward past 255
_fwk_motion_axis_limit:
    cp b                                    ; in range, or moved back with carry
    ret c
_fwk_motion_axis_high:
    ld a, b
    dec a
    ret
