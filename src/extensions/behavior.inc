;; Optional behavior interpreter for GlasnostFWK.
;; The record embeds the 5-byte motion_u8 record followed by behavior state.
FWK_BEHAVIOR_MOTION_X = 0
FWK_BEHAVIOR_MOTION_Y = 1
FWK_BEHAVIOR_MOTION_VX = 2
FWK_BEHAVIOR_MOTION_VY = 3
FWK_BEHAVIOR_MOTION_FLAGS = 4
FWK_BEHAVIOR_PROGRAM = 5
FWK_BEHAVIOR_TIMER = 7
FWK_BEHAVIOR_RECORD_SIZE = 8

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
