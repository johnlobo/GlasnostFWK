;; Optional bounded platform profile using signed byte velocities.
.module fwk_physics_platform
.include "extensions/physics_platform.inc"

.area _CODE

;; fwk_physics_platform_step
;; In: IY=7-byte state; IX=4-byte configuration.
;; Out: horizontal bounds, gravity, ceiling and floor applied. The floor is an
;;      inclusive Y coordinate; width/height belong to the consumer record.
;; Modified: AF,BC. IX/IY preserved. Reentrant if state is not shared.
fwk_physics_platform_step::
    ld a, FWK_PLATFORM_VX(iy)
    or a
    jr z, _fwk_platform_vertical
    add FWK_PLATFORM_X(iy)
    bit 7, FWK_PLATFORM_VX(iy)
    jr z, _fwk_platform_x_positive
    jr nc, _fwk_platform_x_zero
    jr _fwk_platform_x_candidate
_fwk_platform_x_positive:
    jr c, _fwk_platform_x_max
_fwk_platform_x_candidate:
    ld c, a
    add FWK_PLATFORM_WIDTH(iy)
    jr c, _fwk_platform_x_max
    cp FWK_PLATFORM_WORLD_WIDTH(ix)
    jr c, _fwk_platform_x_store_c
    jr z, _fwk_platform_x_store_c
_fwk_platform_x_max:
    ld a, FWK_PLATFORM_WORLD_WIDTH(ix)
    sub FWK_PLATFORM_WIDTH(iy)
    ld FWK_PLATFORM_VX(iy), #0
    jr _fwk_platform_x_store
_fwk_platform_x_zero:
    xor a
    ld FWK_PLATFORM_VX(iy), #0
    jr _fwk_platform_x_store
_fwk_platform_x_store_c:
    ld a, c
_fwk_platform_x_store:
    ld FWK_PLATFORM_X(iy), a

_fwk_platform_vertical:
    bit FWK_PLATFORM_AIRBORNE_BIT, FWK_PLATFORM_FLAGS(iy)
    jr z, _fwk_platform_grounded
    ld a, FWK_PLATFORM_VY(iy)
    add FWK_PLATFORM_GRAVITY(ix)
    bit 7, a
    jr nz, _fwk_platform_gravity_store
    cp FWK_PLATFORM_MAX_FALL(ix)
    jr c, _fwk_platform_gravity_store
    ld a, FWK_PLATFORM_MAX_FALL(ix)
_fwk_platform_gravity_store:
    ld FWK_PLATFORM_VY(iy), a
    jr _fwk_platform_move_y

_fwk_platform_grounded:
    ld a, FWK_PLATFORM_VY(iy)
    bit 7, a
    jr z, _fwk_platform_floor_hold
    set FWK_PLATFORM_AIRBORNE_BIT, FWK_PLATFORM_FLAGS(iy)
    res FWK_PLATFORM_TILE_GROUNDED_BIT, FWK_PLATFORM_FLAGS(iy)
    jr _fwk_platform_move_y
_fwk_platform_floor_hold:
    xor a
    ld FWK_PLATFORM_VY(iy), a
    ret

_fwk_platform_move_y:
    ld a, FWK_PLATFORM_VY(iy)
    or a
    ret z
    add FWK_PLATFORM_Y(iy)
    bit 7, FWK_PLATFORM_VY(iy)
    jr z, _fwk_platform_fall
    jr nc, _fwk_platform_ceiling
    ld FWK_PLATFORM_Y(iy), a
    ret
_fwk_platform_ceiling:
    xor a
    ld FWK_PLATFORM_Y(iy), a
    ld FWK_PLATFORM_VY(iy), a
    ret

_fwk_platform_fall:
    ld c, a
    add FWK_PLATFORM_HEIGHT(iy)
    dec a
    cp FWK_PLATFORM_GROUND_Y(ix)
    jr c, _fwk_platform_y_store_c
    jr z, _fwk_platform_land_exact
    ld a, FWK_PLATFORM_GROUND_Y(ix)
    sub FWK_PLATFORM_HEIGHT(iy)
    inc a
    jr _fwk_platform_land
_fwk_platform_land_exact:
    ld a, c
_fwk_platform_land:
    ld FWK_PLATFORM_Y(iy), a
    xor a
    ld FWK_PLATFORM_VY(iy), a
    res FWK_PLATFORM_AIRBORNE_BIT, FWK_PLATFORM_FLAGS(iy)
    res FWK_PLATFORM_TILE_GROUNDED_BIT, FWK_PLATFORM_FLAGS(iy)
    ret
_fwk_platform_y_store_c:
    ld a, c
    ld FWK_PLATFORM_Y(iy), a
    ret
