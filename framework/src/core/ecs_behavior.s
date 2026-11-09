;; ECS 2.0 adapter for the existing behavior bytecode interpreter.
.module fwk_ecs_behavior

.include "ecs_profile.inc"
.include "core/ecs_manager.inc"
.include "extensions/behavior.inc"

.area _DATA
_fwk_ecs_behavior_scratch:: .ds FWK_BEHAVIOR_RECORD_SIZE

.area _CODE

;; fwk_ecs_system_behavior
;; In: IX=manager containing BEHAVIOR entities.
;; Out: carry/A follow fwk_ecs_system_run.
;; The legacy VM runs against a private compatibility record; all mutable
;; behavior/motion fields are copied back to the entity before return.
fwk_ecs_system_behavior::
    ld bc, #ECS_C_BEHAVIOR
    ld hl, #_fwk_ecs_behavior_callback
    jp fwk_ecs_system_run

_fwk_ecs_behavior_callback:
    push ix
    push iy

    ld a, ECS_E_X(iy)
    ld (_fwk_ecs_behavior_scratch + FWK_BEHAVIOR_MOTION_X), a
    ld a, ECS_E_Y(iy)
    ld (_fwk_ecs_behavior_scratch + FWK_BEHAVIOR_MOTION_Y), a
    ld a, ECS_E_MOTION_VELOCITY_X(iy)
    ld (_fwk_ecs_behavior_scratch + FWK_BEHAVIOR_MOTION_VX), a
    ld a, ECS_E_MOTION_VELOCITY_Y(iy)
    ld (_fwk_ecs_behavior_scratch + FWK_BEHAVIOR_MOTION_VY), a
    ld a, ECS_E_MOTION_FLAGS(iy)
    ld (_fwk_ecs_behavior_scratch + FWK_BEHAVIOR_MOTION_FLAGS), a
    ld l, ECS_E_BEHAVIOR_PROGRAM(iy)
    ld h, ECS_E_BEHAVIOR_PROGRAM+1(iy)
    ld (_fwk_ecs_behavior_scratch + FWK_BEHAVIOR_PROGRAM), hl
    ld a, ECS_E_BEHAVIOR_TIMER(iy)
    ld (_fwk_ecs_behavior_scratch + FWK_BEHAVIOR_TIMER), a

    ld ix, #_fwk_ecs_behavior_scratch
    call fwk_behavior_run

    ld a, FWK_BEHAVIOR_MOTION_VX(ix)
    ld ECS_E_MOTION_VELOCITY_X(iy), a
    ld a, FWK_BEHAVIOR_MOTION_VY(ix)
    ld ECS_E_MOTION_VELOCITY_Y(iy), a
    ld a, FWK_BEHAVIOR_MOTION_FLAGS(ix)
    ld ECS_E_MOTION_FLAGS(iy), a
    ld l, FWK_BEHAVIOR_PROGRAM(ix)
    ld h, FWK_BEHAVIOR_PROGRAM+1(ix)
    ld ECS_E_BEHAVIOR_PROGRAM(iy), l
    ld ECS_E_BEHAVIOR_PROGRAM+1(iy), h
    ld a, FWK_BEHAVIOR_TIMER(ix)
    ld ECS_E_BEHAVIOR_TIMER(iy), a

    pop iy
    pop ix
    xor a
    ret
