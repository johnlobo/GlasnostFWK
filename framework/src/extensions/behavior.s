;; GlasnostFWK optional behavior interpreter.
;; Derived from model01's behavior VM, adapted to a compact 8-byte record
;; that embeds the 5-byte motion_u8 record plus behavior state.
.module fwk_behavior

.include "extensions/behavior.inc"

.area _DATA
fwk_behavior_actions_left:: .db 0

.area _CODE

;; fwk_behavior_init
;; No-op kept for API symmetry.
fwk_behavior_init::
    ret

;; Indirect call helper: call with HL=fn.
fwk_behavior_call_hl::
    jp (hl)

;; fwk_behavior_run
;; In: IX = behavior record. DE is ignored; program pointer is read from record.
;; Out: none. Modified: AF, DE, HL.
fwk_behavior_run::
    ld e, FWK_BEHAVIOR_PROGRAM(ix)
    ld d, FWK_BEHAVIOR_PROGRAM+1(ix)
    ld a, d
    or e
    ret z
    ld a, #BEH_MAX_ACTIONS_PER_TICK
    ld (fwk_behavior_actions_left), a

fwk_behavior_run_dispatch::
    ld a, (fwk_behavior_actions_left)
    or a
    ret z
    dec a
    ld (fwk_behavior_actions_left), a
    ld a, (de)
    ld l, a
    inc de
    ld a, (de)
    ld h, a
    inc de
    jp (hl)

;; fwk_behavior_next
;; In: IX = record, DE = new program position (0 ends behavior).
;; Out: none. Modified: AF.
fwk_behavior_next::
    ld a, d
    or e
    jr z, fbn_destroy
    ld FWK_BEHAVIOR_PROGRAM(ix), e
    ld FWK_BEHAVIOR_PROGRAM+1(ix), d
    jp fwk_behavior_run_dispatch

fbn_destroy::
    xor a
    ld FWK_BEHAVIOR_PROGRAM(ix), a
    ld FWK_BEHAVIOR_PROGRAM+1(ix), a
    ret

;; fwk_behavior_check_conditions
;; In: IX = record, DE = condition table.
;; Out: none. Modified: AF, DE, HL.
fwk_behavior_check_conditions::
    ld a, (de)
    ld l, a
    inc de
    ld a, (de)
    ld h, a
    or l
    ret z
    inc de
    call fwk_behavior_call_hl
    jr z, fbcc_true
    inc de
    inc de
    jp fwk_behavior_check_conditions

fbcc_true::
    ex de, hl
    ld e, (hl)
    inc hl
    ld d, (hl)
    jp fwk_behavior_next

;; Actions
fwk_behavior_action_idle::
    jp fwk_behavior_check_conditions

fwk_behavior_action_wait::
    dec FWK_BEHAVIOR_TIMER(ix)
    jp fwk_behavior_check_conditions

fwk_behavior_action_set_timer::
    ld a, (de)
    inc de
    ld FWK_BEHAVIOR_TIMER(ix), a
    jp fwk_behavior_next

fwk_behavior_action_set_vx::
    ld a, (de)
    inc de
    ld FWK_BEHAVIOR_MOTION_VX(ix), a
    jp fwk_behavior_next

fwk_behavior_action_set_vy::
    ld a, (de)
    inc de
    ld FWK_BEHAVIOR_MOTION_VY(ix), a
    jp fwk_behavior_next

fwk_behavior_action_drive_vx::
    ld a, (de)
    inc de
    ld c, a
    ld a, (de)
    inc de
    or a
    jr z, fbdvx_apply
    dec a
    jr z, fbdvx_apply
    ld b, a
    ld a, FWK_BEHAVIOR_TIMER(ix)
    or a
    jr nz, fbdvx_tick
    ld FWK_BEHAVIOR_TIMER(ix), b
fbdvx_apply:
    ld FWK_BEHAVIOR_MOTION_VX(ix), c
    jr fbdvx_done
fbdvx_tick:
    dec a
    ld FWK_BEHAVIOR_TIMER(ix), a
    ld a, #0
    ld FWK_BEHAVIOR_MOTION_VX(ix), a
fbdvx_done:
    jp fwk_behavior_check_conditions

;; Conditions
fwk_behavior_cond_true::
    xor a
    ret

fwk_behavior_cond_timeout::
    ld a, FWK_BEHAVIOR_TIMER(ix)
    or a
    ret
