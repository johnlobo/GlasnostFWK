;; Behavior component system: the ECS adapter and the bytecode interpreter
;; in one module. The interpreter runs directly on the entity in IY, using the
;; generated ECS_E_BEHAVIOR_* and ECS_E_MOTION_* offsets, so there is no
;; compatibility record and no field copy.
.module fwk_ecs_behavior

.include "ecs_profile.inc"
.include "core/ecs_manager.inc"
.include "core/ecs_behavior.inc"

.area _DATA
_fwk_behavior_actions_left: .db 0

.area _CODE

;; fwk_ecs_system_behavior
;; In: IX=manager containing BEHAVIOR entities.
;; Out: carry/A follow fwk_ecs_system_run.
;; Runs one behavior step per due entity. IX and IY are preserved.
fwk_ecs_system_behavior::
    ld bc, #ECS_C_BEHAVIOR
    ld hl, #_fwk_ecs_behavior_callback
    jp fwk_ecs_system_run

;; _fwk_ecs_behavior_callback
;; In: IX=manager, IY=entity. Out: carry clear; IX and IY preserved.
_fwk_ecs_behavior_callback:
    push ix

    ld e, ECS_E_BEHAVIOR_PROGRAM(iy)
    ld d, ECS_E_BEHAVIOR_PROGRAM+1(iy)
    ld a, d
    or e
    jp z, _fwk_behavior_done
    ld a, #BEH_MAX_ACTIONS_PER_TICK
    ld (_fwk_behavior_actions_left), a

_fwk_behavior_dispatch:
    ld a, (_fwk_behavior_actions_left)
    or a
    jp z, _fwk_behavior_done
    dec a
    ld (_fwk_behavior_actions_left), a
    ld a, (de)
    ld l, a
    inc de
    ld a, (de)
    ld h, a
    inc de
    jp (hl)

;; _fwk_behavior_next
;; In: IY=entity, DE=new program position (0 ends behavior).
_fwk_behavior_next:
    ld a, d
    or e
    jr z, _fwk_behavior_destroy
    ld ECS_E_BEHAVIOR_PROGRAM(iy), e
    ld ECS_E_BEHAVIOR_PROGRAM+1(iy), d
    jr _fwk_behavior_dispatch

_fwk_behavior_destroy:
    xor a
    ld ECS_E_BEHAVIOR_PROGRAM(iy), a
    ld ECS_E_BEHAVIOR_PROGRAM+1(iy), a

;; Single exit: restores IX and returns carry clear to fwk_ecs_system_run.
_fwk_behavior_done:
    pop ix
    xor a
    ret

;; _fwk_behavior_check_conditions
;; In: IY=entity, DE=condition table.
_fwk_behavior_check_conditions:
    ld a, (de)
    ld l, a
    inc de
    ld a, (de)
    ld h, a
    or l
    jp z, _fwk_behavior_done
    inc de
    call _fwk_behavior_call_hl
    jr z, _fwk_behavior_cond_true
    inc de
    inc de
    jr _fwk_behavior_check_conditions

_fwk_behavior_cond_true:
    ex de, hl
    ld e, (hl)
    inc hl
    ld d, (hl)
    jr _fwk_behavior_next

;; Indirect call helper: call with HL=fn.
_fwk_behavior_call_hl:
    jp (hl)

;; Actions
fwk_behavior_action_idle::
    jp _fwk_behavior_check_conditions

fwk_behavior_action_wait::
    dec ECS_E_BEHAVIOR_TIMER(iy)
    jp _fwk_behavior_check_conditions

fwk_behavior_action_set_timer::
    ld a, (de)
    inc de
    ld ECS_E_BEHAVIOR_TIMER(iy), a
    jp _fwk_behavior_next

fwk_behavior_action_set_vx::
    ld a, (de)
    inc de
    ld ECS_E_MOTION_VELOCITY_X(iy), a
    jp _fwk_behavior_next

fwk_behavior_action_set_vy::
    ld a, (de)
    inc de
    ld ECS_E_MOTION_VELOCITY_Y(iy), a
    jp _fwk_behavior_next

fwk_behavior_action_drive_vx::
    ld a, (de)
    inc de
    ld c, a
    ld a, (de)
    inc de
    or a
    jr z, _fbdvx_apply
    dec a
    jr z, _fbdvx_apply
    ld b, a
    ld a, ECS_E_BEHAVIOR_TIMER(iy)
    or a
    jr nz, _fbdvx_tick
    ld ECS_E_BEHAVIOR_TIMER(iy), b
_fbdvx_apply:
    ld ECS_E_MOTION_VELOCITY_X(iy), c
    jr _fbdvx_done
_fbdvx_tick:
    dec a
    ld ECS_E_BEHAVIOR_TIMER(iy), a
    ld a, #0
    ld ECS_E_MOTION_VELOCITY_X(iy), a
_fbdvx_done:
    jp _fwk_behavior_check_conditions

;; Conditions
fwk_behavior_cond_true::
    xor a
    ret

fwk_behavior_cond_timeout::
    ld a, ECS_E_BEHAVIOR_TIMER(iy)
    or a
    ret
