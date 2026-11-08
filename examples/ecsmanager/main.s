.module example_ecsmanager
.include "ecs_profile.inc"
.include "core/ecs_manager.inc"
.include "extensions/behavior.inc"

.globl fwk_project_init, fwk_system_wait_frame

ECSMANAGER_CAPACITY = 3
ECSMANAGER_CAD_CAPACITY = 5

;; Comprobación defensiva de carry tras una llamada al framework.
ECSMANAGER_DEBUG_CHECKS = 1
.macro ECSMANAGER_CHECK_OK
.if ECSMANAGER_DEBUG_CHECKS
    jp c, _ecsmanager_fail
.endif
.endm

.area _DATA
ecsmanager_storage:: .ds ECS_ENTITY_SIZE * ECSMANAGER_CAPACITY
FWK_ECS_MANAGER_DESCRIPTOR ecsmanager_manager, ecsmanager_storage, ECSMANAGER_CAPACITY

;; Cadence scenario: one manager with five TEST entities, run for sixteen iterations.
ecsmanager_cad_storage:: .ds ECS_ENTITY_SIZE * ECSMANAGER_CAD_CAPACITY
FWK_ECS_MANAGER_DESCRIPTOR ecsmanager_cad_manager, ecsmanager_cad_storage, ECSMANAGER_CAD_CAPACITY
ecsmanager_cad_template: .ds ECS_ENTITY_SIZE
;; Cadence bytes, (phase << 4) | (every - 1): every iteration, every 2nd from
;; phase 0, every 2nd from phase 1, every 4th from phase 3, every 16th from phase
;; 9. Over iterations 0..15 they run in {0..15}, the even ones, the odd ones,
;; {3,7,11,15} and {9}: tick sums 120, 56, 64, 36 and 9.
ecsmanager_cad_table:
    .db 0x00, 0x01, 0x11, 0x33, 0x9F
;; Cadence bytes tried on a full manager, with the error each must give: every - 1
;; that is not 2^k - 1, or a phase above every - 1, is a bad template; any valid
;; byte only finds the manager full.
ecsmanager_cad_probes:
    .db 0x02, FWK_ECS_ERR_TEMPLATE
    .db 0x04, FWK_ECS_ERR_TEMPLATE
    .db 0x05, FWK_ECS_ERR_TEMPLATE
    .db 0x06, FWK_ECS_ERR_TEMPLATE
    .db 0x0A, FWK_ECS_ERR_TEMPLATE
    .db 0x0E, FWK_ECS_ERR_TEMPLATE
    .db 0x91, FWK_ECS_ERR_TEMPLATE
    .db 0x21, FWK_ECS_ERR_TEMPLATE
    .db 0x10, FWK_ECS_ERR_TEMPLATE
    .db 0x00, FWK_ECS_ERR_FULL
    .db 0x11, FWK_ECS_ERR_FULL
    .db 0x33, FWK_ECS_ERR_FULL
    .db 0x0F, FWK_ECS_ERR_FULL
    .db 0xFF, FWK_ECS_ERR_FULL
ECSMANAGER_CAD_PROBES = 14

ecsmanager_behavior_right:
    FWK_BEHAVIOR_SET_VX 1
    FWK_BEHAVIOR_WAIT 8, ecsmanager_behavior_left
ecsmanager_behavior_left:
    FWK_BEHAVIOR_SET_VX 0xFF
    FWK_BEHAVIOR_WAIT 8, ecsmanager_behavior_right

ecsmanager_template:
    .dw ECS_C_RENDER | ECS_C_MOTION | ECS_C_BEHAVIOR | ECS_C_TEST
    .db ECS_STATUS_ACTIVE, 7, 10, 20, 2, 8, 0   ; ..., width, height, cadence
    .dw 0
    .db 0, 0, 0, 0
    .dw 0                                       ; background (renderer-owned)
    .db ECS_RENDER_VISIBLE, 0, 0
    .dw 0, 0
    .db 0, 0, 0
    .dw ecsmanager_behavior_right
    .db 0, 0

;; Motion edge cases: x, y, vx, vy, expected x, expected y. Covers positions
;; above 127 (the old sign-flag check zeroed them), saturation at both ends,
;; underflow on each axis, and out-of-range positions moving backwards.
ecsmanager_motion_probe_table:
    .db 78, 198, 3, 3, 79, 199
    .db 2, 2, 0xFD, 0xFD, 0, 0
    .db 2, 130, 0xFD, 0xFD, 0, 127
    .db 70, 130, 1, 1, 71, 131
    .db 70, 190, 0, 5, 70, 195
    .db 200, 250, 0xFF, 0xFF, 79, 199
    .db 255, 255, 1, 1, 79, 199
    .db 79, 199, 0, 0, 79, 199
ECSMANAGER_MOTION_PROBES = 8

ecsmanager_status:: .db 0
ecsmanager_callbacks:: .db 0
ecsmanager_first_slot:: .dw 0

.area _CODE

;; ----------------------------------------------------------------------------
;; _ecsmanager_fail
;;   Test failure exit: stores the failure code in ecsmanager_status and hangs in
;;   _ecsmanager_loop. Falls through into it; never returns.
;;   In : A=failure code (0xD1..0xDD, 0xE1..0xEF, or a raw FWK_ECS_ERR_* passed on
;;          by _ecsmanager_expect_ok).
;;   Out: ecsmanager_status=A. Does not return.
;;   Clobbers: all (never returns)
;;   Notes: Entered with jp (or any path that has the code in A). The loop it ends in
;;          calls fwk_system_wait_frame, which modifies AF, BC, DE, HL on every pass.
;; ----------------------------------------------------------------------------
_ecsmanager_fail:
    ld (ecsmanager_status), a           ; publish the code for the harness
;; ----------------------------------------------------------------------------
;; _ecsmanager_loop
;;   Idle loop at the end of the test. The harness reads ecsmanager_status: 0x5A
;;   means every check passed, any other value is the failure code.
;;   In : none (A is not read).
;;   Out: none. Does not return.
;;   Clobbers: all (never returns)
;;   Notes: Reached by fall-through from _ecsmanager_fail and by jp from _main. Each
;;          pass calls fwk_system_wait_frame, which modifies AF, BC, DE, HL.
;; ----------------------------------------------------------------------------
_ecsmanager_loop:
    call fwk_system_wait_frame          ; park here, one VSYNC per pass
    jr _ecsmanager_loop

;; ----------------------------------------------------------------------------
;; _ecsmanager_expect_ok
;;   Checks the carry/A result of the framework call made just before it.
;;   Returns on success; on error aborts the whole test.
;;   In : Carry=result of the previous call (clear = ok); A=error code if set.
;;   Out: Success: returns with carry clear, A and every register untouched.
;;          Error: does not return, see Notes.
;;   Clobbers: none on the success path. On the error path it does not return to
;;             anyone (see Notes), so no register state is handed back.
;;   Notes: On error it pops its own return address (HL is overwritten), so the
;;          caller's caller is skipped, and jumps to _ecsmanager_fail with A unchanged.
;; ----------------------------------------------------------------------------
;; ----------------------------------------------------------------------------
;; _ecsmanager_callback
;;   TEST-system callback for the destroy scenario. Counts its calls in
;;   ecsmanager_callbacks. On the first call it checks that fwk_ecs_entity_disable
;;   is refused with BUSY under the traversal lock, then marks the entity PENDING_DESTROY.
;;   In : IX=manager, IY=entity being visited (from fwk_ecs_system_run).
;;   Out: 1st call: carry/A of fwk_ecs_entity_mark_destroy (carry clear, A=0 on
;;          success), or carry set with A=0xEA if disable was not refused with
;;          BUSY. Later calls: carry clear, A=call count (ignored by the caller).
;;   Clobbers: AF, BC, DE, HL (the framework calls of the first call; later calls only AF)
;;   Notes: IX and IY are preserved, as fwk_ecs_system_run requires. Increments
;;          ecsmanager_callbacks (8-bit, no wrap guard).
;; ----------------------------------------------------------------------------
_ecsmanager_callback:
    ld a, (ecsmanager_callbacks)        ; count this call
    inc a
    ld (ecsmanager_callbacks), a
    cp #1
    ret nz                              ; only the first call does work
    call fwk_ecs_entity_disable         ; must be refused: the traversal lock is held
    jr nc, _ecsmanager_callback_lock_fail   ; accepted: the lock is not working
    cp #FWK_ECS_ERR_BUSY
    jr nz, _ecsmanager_callback_lock_fail   ; refused with the wrong error
    call fwk_ecs_entity_mark_destroy    ; allowed under the traversal lock
    ret
_ecsmanager_callback_lock_fail:         ; report the lock violation as a callback error
    ld a, #0xEA
    scf
    ret

;; ----------------------------------------------------------------------------
;; _ecsmanager_cadence_callback
;;   Adds the current tick to the TYPE byte of the entity it is given, so the byte
;;   ends up as the sum of the iterations in which the entity ran.
;;   In : IY=entity being visited; fwk_ecs_tick=current iteration.
;;   Out: ECS_E_TYPE(iy) += fwk_ecs_tick (8-bit wrap); carry clear, A=0 (continue).
;;   Clobbers: AF
;;   Notes: IX and IY are preserved. Wraps modulo 256 on overflow.
;; ----------------------------------------------------------------------------
_ecsmanager_cadence_callback:
    ld a, (fwk_ecs_tick)
    add a, ECS_E_TYPE(iy)
    ld ECS_E_TYPE(iy), a
    xor a                               ; A=0, carry clear: keep walking
    ret

;; ----------------------------------------------------------------------------
;; _ecsmanager_abort_callback
;;   Callback that always aborts the traversal with carry set and A=0, to test that
;;   fwk_ecs_system_run turns that into FWK_ECS_ERR_CALLBACK and drops the lock.
;;   In : none (IX, IY are ignored).
;;   Out: Carry set, A=0.
;;   Clobbers: AF
;;   Notes: IX and IY are preserved. A=0 with carry set is deliberate: the caller turns
;;          it into FWK_ECS_ERR_CALLBACK.
;; ----------------------------------------------------------------------------
_ecsmanager_abort_callback:
    xor a                               ; A=0 with carry set must become ERR_CALLBACK
    scf
    ret

;; ----------------------------------------------------------------------------
;; _ecsmanager_motion_probe
;;   Loads one row of ecsmanager_motion_probe_table into the first entity, runs one
;;   fwk_ecs_system_motion_u8 pass and compares X and Y with the expected values.
;;   In : HL=row (x, y, vx, vy, expected x, expected y), IX=manager,
;;          ecsmanager_first_slot=entity to test.
;;   Out: Z set when both X and Y match, Z clear on the first mismatch.
;;          HL=row+5 (the expected y byte) in both cases. IY=first entity.
;;   Clobbers: AF, BC, DE, HL, IY (fwk_ecs_system_motion_u8 runs through fwk_ecs_system_run)
;;   Notes: IX preserved. The motion pass also moves every other MOTION entity. The
;;          result of the motion pass itself (carry/A) is ignored.
;; ----------------------------------------------------------------------------
_ecsmanager_motion_probe:
    ld iy, (ecsmanager_first_slot)
    ;; Load x, y, vx, vy from the row into the entity.
    ld a, (hl)
    inc hl
    ld ECS_E_X(iy), a
    ld a, (hl)
    inc hl
    ld ECS_E_Y(iy), a
    ld a, (hl)
    inc hl
    ld ECS_E_MOTION_VELOCITY_X(iy), a
    ld a, (hl)
    inc hl
    ld ECS_E_MOTION_VELOCITY_Y(iy), a
    push hl                             ; HL = row + 4 (the expected x)
    call fwk_ecs_system_motion_u8       ; moves every MOTION entity; the result is not checked
    pop hl
    ld iy, (ecsmanager_first_slot)      ; IY = first slot again
    ;; Compare against the expected x, then y. Z is the verdict.
    ld a, (hl)
    inc hl
    cp ECS_E_X(iy)
    ret nz
    ld a, (hl)
    cp ECS_E_Y(iy)
    ret

;; ----------------------------------------------------------------------------
;; _main
;;   Program entry. Runs the whole ECS manager test: lifecycle, motion, destroy and
;;   collect, mask validation, callback abort, cadence and cadence validation.
;;   In : none.
;;   Out: ecsmanager_status=0x5A when every check passed, otherwise the failure code.
;;          Does not return: ends in _ecsmanager_loop.
;;   Clobbers: all (never returns)
;;   Notes: Uses IX=manager throughout (ecsmanager_manager, later ecsmanager_cad_manager).
;;          Each check loads A with its own failure code before the jp nz to
;;          _ecsmanager_fail; the framework calls use the carry/A ABI.
;; ----------------------------------------------------------------------------
_main::
    call fwk_project_init
    ld ix, #ecsmanager_manager          ; IX stays the manager for the whole first half
    call fwk_ecs_manager_init
    ECSMANAGER_CHECK_OK

    ;; Three deterministic stable slots.
    ld hl, #ecsmanager_template
    call fwk_ecs_entity_create
    ECSMANAGER_CHECK_OK
    push iy
    pop hl
    ld (ecsmanager_first_slot), hl      ; slot 0, used by the motion checks and the reuse check
    ld hl, #ecsmanager_template
    call fwk_ecs_entity_create
    ECSMANAGER_CHECK_OK
    ld hl, #ecsmanager_template
    call fwk_ecs_entity_create
    ECSMANAGER_CHECK_OK
    ld a, FWK_ECS_MANAGER_ACTIVE_COUNT(ix)
    cp #3                               ; all three created
    ld a, #0xE1                         ; (ld leaves the flags of cp alone)
    jp nz, _ecsmanager_fail

    ;; Behavior and motion are explicit ECS systems. Four ticks move the
    ;; first entity from X=10 to X=14 and leave its generated fields coherent.
    ld b, #4
_ecsmanager_system_loop:                ; behavior sets vx, motion applies it
    push bc
    call fwk_ecs_system_behavior
    ECSMANAGER_CHECK_OK
    call fwk_ecs_system_motion_u8
    ECSMANAGER_CHECK_OK
    pop bc
    djnz _ecsmanager_system_loop
    ld iy, (ecsmanager_first_slot)
    ld a, ECS_E_X(iy)                   ; 10 + 4 ticks * vx 1
    cp #14
    ld a, #0xED
    jp nz, _ecsmanager_fail
    ld a, ECS_E_MOTION_VELOCITY_X(iy)
    cp #1
    ld a, #0xEE
    jp nz, _ecsmanager_fail

    ;; Motion arithmetic edge cases, then restore the first entity.
    ld hl, #ecsmanager_motion_probe_table
    ld b, #ECSMANAGER_MOTION_PROBES
_ecsmanager_motion_probe_loop:
    push bc
    call _ecsmanager_motion_probe       ; Z = row passed, HL = its expected y byte
    pop bc
    ld a, #0xEF
    jp nz, _ecsmanager_fail
    inc hl                              ; next row
    djnz _ecsmanager_motion_probe_loop
    ld iy, (ecsmanager_first_slot)
    ld ECS_E_X(iy), #14                 ; restore the state left by the four ticks
    ld ECS_E_Y(iy), #20
    ld ECS_E_MOTION_VELOCITY_X(iy), #1
    ld ECS_E_MOTION_VELOCITY_Y(iy), #0

    ;; Full manager must be reported without altering counts.
    ld hl, #ecsmanager_template
    call fwk_ecs_entity_create
    jp nc, _ecsmanager_fail
    cp #FWK_ECS_ERR_FULL
    jp nz, _ecsmanager_fail

    ;; Disable the middle stable slot.
    ld iy, #ecsmanager_storage + ECS_ENTITY_SIZE
    call fwk_ecs_entity_disable
    ECSMANAGER_CHECK_OK

    ;; Run TEST only for the two ACTIVE entities. First callback destroys one.
    ld iy, #0xBEEF                      ; sentinel: the system must hand IY back unchanged
    ld bc, #ECS_C_TEST
    ld hl, #_ecsmanager_callback
    call fwk_ecs_system_run
    ECSMANAGER_CHECK_OK
    push iy
    pop hl
    ld de, #0xBEEF
    or a
    sbc hl, de
    ld a, #0xE8
    jp nz, _ecsmanager_fail
    ld a, (ecsmanager_callbacks)
    cp #2
    ld a, #0xE2
    jp nz, _ecsmanager_fail
    ld a, FWK_ECS_MANAGER_ACTIVE_COUNT(ix)
    cp #1
    ld a, #0xE3
    jp nz, _ecsmanager_fail

    ;; Collection frees exactly one slot, then creation reuses index zero.
    ld iy, #0xCAFE                      ; sentinel: collect must preserve IY
    call fwk_ecs_manager_collect
    ECSMANAGER_CHECK_OK
    push iy
    pop hl
    ld de, #0xCAFE
    or a
    sbc hl, de
    ld a, #0xE9
    jp nz, _ecsmanager_fail
    ld a, b                             ; B = slots collected
    cp #1
    ld a, #0xE4
    jp nz, _ecsmanager_fail
    ld hl, #ecsmanager_template
    call fwk_ecs_entity_create
    ECSMANAGER_CHECK_OK
    push iy
    pop de
    ld hl, (ecsmanager_first_slot)
    or a
    sbc hl, de
    ld a, #0xE5
    jp nz, _ecsmanager_fail

    ;; Re-enable the middle slot: render must become dirty.
    ld iy, #ecsmanager_storage + ECS_ENTITY_SIZE
    call fwk_ecs_entity_enable
    ECSMANAGER_CHECK_OK
    bit 1, ECS_E_RENDER_FLAGS(iy)       ; bit 1 = render dirty
    ld a, #0xE6
    jp z, _ecsmanager_fail

    ;; A mask outside the selected profile is rejected and remains unchanged.
    ld bc, #0x8000                      ; bit 15 is not in this profile's component mask
    call fwk_ecs_entity_set_mask
    jp nc, _ecsmanager_fail
    cp #FWK_ECS_ERR_MASK
    jp nz, _ecsmanager_fail
    ld a, ECS_E_COMPONENTS(iy)
    cp #(ECS_C_RENDER | ECS_C_MOTION | ECS_C_BEHAVIOR | ECS_C_TEST)
    ld a, #0xE7
    jp nz, _ecsmanager_fail

    ;; Render cannot be removed until its captured background is released.
    set 2, ECS_E_RENDER_FLAGS(iy)       ; bit 2 = renderer holds a background capture
    ld bc, #ECS_C_TEST
    call fwk_ecs_entity_set_mask
    jp nc, _ecsmanager_fail
    cp #FWK_ECS_ERR_RENDER
    jp nz, _ecsmanager_fail
    res 2, ECS_E_RENDER_FLAGS(iy)       ; release the fake capture

    ;; Callback abort with A=0 is normalized and always releases the lock.
    ld iy, #0x1234                      ; sentinel: IY must survive the aborted run
    ld bc, #0                           ; empty mask: every ACTIVE entity matches
    ld hl, #_ecsmanager_abort_callback
    call fwk_ecs_system_run
    jp nc, _ecsmanager_fail
    cp #FWK_ECS_ERR_CALLBACK
    jp nz, _ecsmanager_fail
    ld a, FWK_ECS_MANAGER_LOCK(ix)      ; the lock must be released after the abort
    or a
    ld a, #0xEB
    jp nz, _ecsmanager_fail
    push iy
    pop hl
    ld de, #0x1234
    or a
    sbc hl, de
    ld a, #0xEC
    jp nz, _ecsmanager_fail

    ;; Cadence: create five entities with different periods and phases.
    ld ix, #ecsmanager_cad_manager
    call fwk_ecs_manager_init
    ECSMANAGER_CHECK_OK
    ld hl, #ecsmanager_cad_table
    ld b, #ECSMANAGER_CAD_CAPACITY
_ecsmanager_cad_create:                 ; one entity per cadence byte
    push bc
    push hl
    ld hl, #ecsmanager_template         ; copy the template to a scratch one
    ld de, #ecsmanager_cad_template
    ld bc, #ECS_ENTITY_SIZE
    ldir
    pop hl
    ld a, (hl)                          ; next cadence byte from the table
    inc hl
    push hl
    ld iy, #ecsmanager_cad_template
    ld ECS_E_CADENCE(iy), a
    ld ECS_E_TYPE(iy), #0               ; TYPE is the running tick sum
    ld hl, #ecsmanager_cad_template
    call fwk_ecs_entity_create
    ECSMANAGER_CHECK_OK
    pop hl
    pop bc
    djnz _ecsmanager_cad_create

    ;; Sixteen iterations with the tick the game would increment once per loop.
    xor a
    ld (fwk_ecs_tick), a
_ecsmanager_cad_tick:                   ; ticks 0..15
    ld ix, #ecsmanager_cad_manager
    ld bc, #ECS_C_TEST
    ld hl, #_ecsmanager_cadence_callback
    call fwk_ecs_system_run
    ECSMANAGER_CHECK_OK
    ld hl, #fwk_ecs_tick
    inc (hl)                            ; the game loop would do this once per frame
    ld a, (hl)
    cp #16
    jr nz, _ecsmanager_cad_tick
    ;; Expected sums per entity, see the comment on ecsmanager_cad_table.
    ld a, (ecsmanager_cad_storage + ECS_E_TYPE)
    cp #120
    ld a, #0xD1
    jp nz, _ecsmanager_fail
    ld a, (ecsmanager_cad_storage + ECS_ENTITY_SIZE + ECS_E_TYPE)
    cp #56
    ld a, #0xD2
    jp nz, _ecsmanager_fail
    ld a, (ecsmanager_cad_storage + 2 * ECS_ENTITY_SIZE + ECS_E_TYPE)
    cp #64
    ld a, #0xD3
    jp nz, _ecsmanager_fail
    ld a, (ecsmanager_cad_storage + 3 * ECS_ENTITY_SIZE + ECS_E_TYPE)
    cp #36
    ld a, #0xD4
    jp nz, _ecsmanager_fail
    ld a, (ecsmanager_cad_storage + 4 * ECS_ENTITY_SIZE + ECS_E_TYPE)
    cp #9
    ld a, #0xD5
    jp nz, _ecsmanager_fail

    ;; fwk_ecs_system_run_any ignores the cadence: at tick 1 it must add 1 to the
    ;; sum of all five entities, although only two of them are due then.
    ld a, #1
    ld (fwk_ecs_tick), a
    ld ix, #ecsmanager_cad_manager
    ld bc, #ECS_C_TEST
    ld hl, #_ecsmanager_cadence_callback
    call fwk_ecs_system_run_any
    ECSMANAGER_CHECK_OK
    ld a, (ecsmanager_cad_storage + ECS_E_TYPE)
    cp #121
    ld a, #0xD6
    jp nz, _ecsmanager_fail
    ld a, (ecsmanager_cad_storage + ECS_ENTITY_SIZE + ECS_E_TYPE)
    cp #57
    ld a, #0xD7
    jp nz, _ecsmanager_fail
    ld a, (ecsmanager_cad_storage + 2 * ECS_ENTITY_SIZE + ECS_E_TYPE)
    cp #65
    ld a, #0xD8
    jp nz, _ecsmanager_fail
    ld a, (ecsmanager_cad_storage + 3 * ECS_ENTITY_SIZE + ECS_E_TYPE)
    cp #37
    ld a, #0xD9
    jp nz, _ecsmanager_fail
    ld a, (ecsmanager_cad_storage + 4 * ECS_ENTITY_SIZE + ECS_E_TYPE)
    cp #10
    ld a, #0xDA
    jp nz, _ecsmanager_fail
    ;; The next plain run honours the cadence again (the mode is set per call).
    ld ix, #ecsmanager_cad_manager
    ld bc, #ECS_C_TEST
    ld hl, #_ecsmanager_cadence_callback
    call fwk_ecs_system_run
    ECSMANAGER_CHECK_OK
    ld a, (ecsmanager_cad_storage + ECS_ENTITY_SIZE + ECS_E_TYPE)
    cp #57                                  ; every 2nd from phase 0: not due at tick 1
    ld a, #0xDB
    jp nz, _ecsmanager_fail

    ;; Creation validates the cadence byte. The manager is full, so a valid byte
    ;; reports FULL and an invalid one reports TEMPLATE: the two are told apart.
    ld hl, #ecsmanager_cad_probes
    ld b, #ECSMANAGER_CAD_PROBES
_ecsmanager_cad_probe:                  ; one (cadence byte, expected error) row per pass
    push bc
    push hl
    ld iy, #ecsmanager_cad_template
    ld a, (hl)
    ld ECS_E_CADENCE(iy), a             ; patch the probe byte into the template
    ld hl, #ecsmanager_cad_template
    call fwk_ecs_entity_create
    pop hl
    pop bc
    jr c, _ecsmanager_cad_probe_error
    ld a, #0xDD                             ; creating must fail either way
    jp _ecsmanager_fail
_ecsmanager_cad_probe_error:            ; A = error code returned by create
    inc hl
    cp (hl)                             ; must equal the expected error
    ld a, #0xDC
    jp nz, _ecsmanager_fail
    inc hl
    djnz _ecsmanager_cad_probe

    ld a, #0x5A                         ; all checks passed
    ld (ecsmanager_status), a
    jp _ecsmanager_loop
