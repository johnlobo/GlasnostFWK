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
.ifdef ECS_C_PLATFORM
    ;; PLATFORM entities own their movement: fwk_ecs_system_platform already
    ;; integrated velocity and resolved collisions, so integrating it again
    ;; here would double the speed and tunnel through solid tiles.
    ld a, ECS_E_COMPONENTS(iy)
    and #ECS_C_PLATFORM
    jr nz, _fwk_ecs_motion_done
.endif

    ld c, ECS_E_X(iy)
    ld a, ECS_E_MOTION_VELOCITY_X(iy)
    ld b, #ECS_X_MAX
    call _fwk_ecs_motion_axis
    cp ECS_E_X(iy)
    jr z, _fwk_ecs_motion_y
    ld ECS_E_X(iy), a
    call _fwk_ecs_motion_dirty

_fwk_ecs_motion_y:
    ld c, ECS_E_Y(iy)
    ld a, ECS_E_MOTION_VELOCITY_Y(iy)
    ld b, #ECS_Y_MAX
    call _fwk_ecs_motion_axis
    cp ECS_E_Y(iy)
    jr z, _fwk_ecs_motion_done
    ld ECS_E_Y(iy), a
    call _fwk_ecs_motion_dirty

_fwk_ecs_motion_done:
    pop iy
    pop ix
    xor a
    ret

;; _fwk_ecs_motion_axis
;; In: C=unsigned position, A=signed velocity, B=maximum position.
;; Out: A=position+velocity saturated to 0..B (also when the incoming
;;      position was already above B).
;; The sum is checked through carry, never through the sign flag: a valid
;; unsigned position above 127 would otherwise read as negative.
;; Modified: AF,D.
_fwk_ecs_motion_axis:
    ld d, a
    add c
    bit 7, d
    jr z, _fwk_ecs_motion_axis_forward
    jr nc, _fwk_ecs_motion_axis_zero    ; backwards underflow
    jr _fwk_ecs_motion_axis_clamp
_fwk_ecs_motion_axis_forward:
    jr c, _fwk_ecs_motion_axis_max      ; forwards overflow
_fwk_ecs_motion_axis_clamp:
    cp b
    ret c
    ret z
_fwk_ecs_motion_axis_max:
    ld a, b
    ret
_fwk_ecs_motion_axis_zero:
    xor a
    ret

_fwk_ecs_motion_dirty:
    ld a, ECS_E_RENDER_FLAGS(iy)
    set 1, a
    ld ECS_E_RENDER_FLAGS(iy), a
    ret
