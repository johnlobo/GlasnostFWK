;; Optional compact motion profile. It is deliberately not the framework's
;; universal entity format; games with 8.8 physics use a different extension.
.module fwk_motion_u8
.include "extensions/motion_u8.inc"

.area _CODE

;; fwk_motion_u8_step
;; In: IY=5-byte record x,y,vx,vy,flags. Signed 8-bit velocity.
;; Out: x/y advanced with saturating bounds 0..79 and 0..199.
;; Modified: AF. Reentrant and interrupt-safe if record is not shared.
fwk_motion_u8_step::
    ld a, FWK_MOTION_X(iy)
    add FWK_MOTION_VX(iy)
    jp m, _fwk_motion_x_zero
    cp #80
    jr c, _fwk_motion_x_store
    ld a, #79
    jr _fwk_motion_x_store
_fwk_motion_x_zero:
    xor a
_fwk_motion_x_store:
    ld FWK_MOTION_X(iy), a
    ld a, FWK_MOTION_Y(iy)
    add FWK_MOTION_VY(iy)
    jp m, _fwk_motion_y_zero
    cp #200
    jr c, _fwk_motion_y_store
    ld a, #199
    jr _fwk_motion_y_store
_fwk_motion_y_zero:
    xor a
_fwk_motion_y_store:
    ld FWK_MOTION_Y(iy), a
    ret
