;; ECS 2.0 compact unsigned-coordinate movement system.
.module fwk_ecs_motion

.include "ecs_profile.inc"
.include "core/ecs_manager.inc"

.area _CODE

;; fwk_ecs_system_motion_u8
;; In: IX=manager containing MOTION entities.
;; Out: carry/A follow fwk_ecs_system_run.
;; Requires ECS_X_FORMAT/ECS_Y_FORMAT == u8. Coordinates saturate to the
;; generated video profile bounds and set render DIRTY when they change.
fwk_ecs_system_motion_u8::
    ld bc, #ECS_C_MOTION
    ld hl, #_fwk_ecs_motion_callback
    jp fwk_ecs_system_run

_fwk_ecs_motion_callback:
    push ix
    push iy

    ld a, ECS_E_X(iy)
    ld c, a
    ld a, ECS_E_MOTION_VELOCITY_X(iy)
    add c
    jp m, _fwk_ecs_motion_x_zero
    cp #ECS_X_MAX + 1
    jr c, _fwk_ecs_motion_x_clamped
    ld a, #ECS_X_MAX
_fwk_ecs_motion_x_clamped:
    ld c, a
    ld a, ECS_E_X(iy)
    cp c
    jr z, _fwk_ecs_motion_y
    ld ECS_E_X(iy), c
    call _fwk_ecs_motion_dirty
    jr _fwk_ecs_motion_y
_fwk_ecs_motion_x_zero:
    xor a
    ld c, a
    ld a, ECS_E_X(iy)
    or a
    jr z, _fwk_ecs_motion_y
    ld ECS_E_X(iy), c
    call _fwk_ecs_motion_dirty

_fwk_ecs_motion_y:
    ld a, ECS_E_Y(iy)
    ld c, a
    ld a, ECS_E_MOTION_VELOCITY_Y(iy)
    add c
    jp m, _fwk_ecs_motion_y_zero
    cp #ECS_Y_MAX + 1
    jr c, _fwk_ecs_motion_y_clamped
    ld a, #ECS_Y_MAX
_fwk_ecs_motion_y_clamped:
    ld c, a
    ld a, ECS_E_Y(iy)
    cp c
    jr z, _fwk_ecs_motion_done
    ld ECS_E_Y(iy), c
    call _fwk_ecs_motion_dirty
    jr _fwk_ecs_motion_done
_fwk_ecs_motion_y_zero:
    xor a
    ld c, a
    ld a, ECS_E_Y(iy)
    or a
    jr z, _fwk_ecs_motion_done
    ld ECS_E_Y(iy), c
    call _fwk_ecs_motion_dirty

_fwk_ecs_motion_done:
    pop iy
    pop ix
    xor a
    ret

_fwk_ecs_motion_dirty:
    ld a, ECS_E_RENDER_FLAGS(iy)
    set 1, a
    ld ECS_E_RENDER_FLAGS(iy), a
    ret
