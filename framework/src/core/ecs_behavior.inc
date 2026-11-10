;; Behavior component system for GlasnostFWK.
;; The runtime lives next to this header in core/ecs_behavior.s: it executes
;; the bytecode directly on the ECS entity (IY), using the generated
;; ECS_E_BEHAVIOR_* and ECS_E_MOTION_* offsets. This header only provides the
;; authoring macros for behavior programs.
BEH_MAX_ACTIONS_PER_TICK = 16
DESTROY_BEHAVIOR = 0

.macro FWK_BEHAVIOR_ACTION _fn
    .dw _fn
.endm

.macro FWK_BEHAVIOR_CONDITION_ENTRY _fn, _target
    .dw _fn, _target
.endm

.macro FWK_BEHAVIOR_IDLE
    .dw fwk_behavior_action_idle
.endm

.macro FWK_BEHAVIOR_CONDITIONS_END
    .dw #0
.endm

.macro FWK_BEHAVIOR_CONDITION _cond, _target
    FWK_BEHAVIOR_CONDITION_ENTRY fwk_behavior_cond_'_cond, _target
.endm

.macro FWK_BEHAVIOR_GOTO _target
    FWK_BEHAVIOR_IDLE
    FWK_BEHAVIOR_CONDITION true, _target
.endm

.macro FWK_BEHAVIOR_WAIT _ticks, _next
    FWK_BEHAVIOR_SET_TIMER _ticks
    .dw fwk_behavior_action_wait
    FWK_BEHAVIOR_CONDITION timeout, _next
    FWK_BEHAVIOR_CONDITIONS_END
.endm

.macro FWK_BEHAVIOR_SET_TIMER _ticks
    .dw fwk_behavior_action_set_timer
    .db _ticks
.endm

.macro FWK_BEHAVIOR_SET_VX _vx
    .dw fwk_behavior_action_set_vx
    .db _vx
.endm

.macro FWK_BEHAVIOR_SET_VY _vy
    .dw fwk_behavior_action_set_vy
    .db _vy
.endm

.macro FWK_BEHAVIOR_DRIVE_VX _vx, _stride
    .dw fwk_behavior_action_drive_vx
    .db _vx, _stride
.endm

.globl fwk_behavior_action_idle, fwk_behavior_action_wait
.globl fwk_behavior_action_set_timer, fwk_behavior_action_set_vx
.globl fwk_behavior_action_set_vy, fwk_behavior_action_drive_vx
.globl fwk_behavior_cond_true, fwk_behavior_cond_timeout
