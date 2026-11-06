.module example_ecsmanager
.include "ecs_profile.inc"
.include "core/ecs_manager.inc"
.include "extensions/behavior.inc"

.globl fwk_project_init, fwk_system_wait_frame

ECSMANAGER_CAPACITY = 3
ECSMANAGER_CAD_CAPACITY = 5

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
    .dw 0, 0
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

_ecsmanager_fail:
    ld (ecsmanager_status), a
_ecsmanager_loop:
    call fwk_system_wait_frame
    jr _ecsmanager_loop

_ecsmanager_expect_ok:
    ret nc
    pop hl
    jp _ecsmanager_fail

_ecsmanager_callback:
    ld a, (ecsmanager_callbacks)
    inc a
    ld (ecsmanager_callbacks), a
    cp #1
    ret nz
    call fwk_ecs_entity_disable
    jr nc, _ecsmanager_callback_lock_fail
    cp #FWK_ECS_ERR_BUSY
    jr nz, _ecsmanager_callback_lock_fail
    call fwk_ecs_entity_mark_destroy
    ret
_ecsmanager_callback_lock_fail:
    ld a, #0xEA
    scf
    ret

;; Adds the current tick to the TYPE byte of the entity it is given, so the byte
;; ends up as the sum of the iterations in which the entity ran.
_ecsmanager_cadence_callback:
    ld a, (fwk_ecs_tick)
    add a, ECS_E_TYPE(iy)
    ld ECS_E_TYPE(iy), a
    xor a
    ret

_ecsmanager_abort_callback:
    xor a
    scf
    ret

;; In: HL=probe row, IX=manager. Out: Z when motion produced the expected
;; position; HL points at the expected y byte.
_ecsmanager_motion_probe:
    ld iy, (ecsmanager_first_slot)
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
    push hl
    call fwk_ecs_system_motion_u8
    pop hl
    ld iy, (ecsmanager_first_slot)
    ld a, (hl)
    inc hl
    cp ECS_E_X(iy)
    ret nz
    ld a, (hl)
    cp ECS_E_Y(iy)
    ret

_main::
    call fwk_project_init
    ld ix, #ecsmanager_manager
    call fwk_ecs_manager_init
    call _ecsmanager_expect_ok

    ;; Three deterministic stable slots.
    ld hl, #ecsmanager_template
    call fwk_ecs_entity_create
    call _ecsmanager_expect_ok
    push iy
    pop hl
    ld (ecsmanager_first_slot), hl
    ld hl, #ecsmanager_template
    call fwk_ecs_entity_create
    call _ecsmanager_expect_ok
    ld hl, #ecsmanager_template
    call fwk_ecs_entity_create
    call _ecsmanager_expect_ok
    ld a, FWK_ECS_MANAGER_ACTIVE_COUNT(ix)
    cp #3
    ld a, #0xE1
    jp nz, _ecsmanager_fail

    ;; Behavior and motion are explicit ECS systems. Four ticks move the
    ;; first entity from X=10 to X=14 and leave its generated fields coherent.
    ld b, #4
_ecsmanager_system_loop:
    push bc
    call fwk_ecs_system_behavior
    call _ecsmanager_expect_ok
    call fwk_ecs_system_motion_u8
    call _ecsmanager_expect_ok
    pop bc
    djnz _ecsmanager_system_loop
    ld iy, (ecsmanager_first_slot)
    ld a, ECS_E_X(iy)
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
    call _ecsmanager_motion_probe
    pop bc
    ld a, #0xEF
    jp nz, _ecsmanager_fail
    inc hl
    djnz _ecsmanager_motion_probe_loop
    ld iy, (ecsmanager_first_slot)
    ld ECS_E_X(iy), #14
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
    call _ecsmanager_expect_ok

    ;; Run TEST only for the two ACTIVE entities. First callback destroys one.
    ld iy, #0xBEEF
    ld bc, #ECS_C_TEST
    ld hl, #_ecsmanager_callback
    call fwk_ecs_system_run
    call _ecsmanager_expect_ok
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
    ld iy, #0xCAFE
    call fwk_ecs_manager_collect
    call _ecsmanager_expect_ok
    push iy
    pop hl
    ld de, #0xCAFE
    or a
    sbc hl, de
    ld a, #0xE9
    jp nz, _ecsmanager_fail
    ld a, b
    cp #1
    ld a, #0xE4
    jp nz, _ecsmanager_fail
    ld hl, #ecsmanager_template
    call fwk_ecs_entity_create
    call _ecsmanager_expect_ok
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
    call _ecsmanager_expect_ok
    bit 1, ECS_E_RENDER_FLAGS(iy)
    ld a, #0xE6
    jp z, _ecsmanager_fail

    ;; A mask outside the selected profile is rejected and remains unchanged.
    ld bc, #0x8000
    call fwk_ecs_entity_set_mask
    jp nc, _ecsmanager_fail
    cp #FWK_ECS_ERR_MASK
    jp nz, _ecsmanager_fail
    ld a, ECS_E_COMPONENTS(iy)
    cp #(ECS_C_RENDER | ECS_C_MOTION | ECS_C_BEHAVIOR | ECS_C_TEST)
    ld a, #0xE7
    jp nz, _ecsmanager_fail

    ;; Render cannot be removed until its captured background is released.
    set 2, ECS_E_RENDER_FLAGS(iy)
    ld bc, #ECS_C_TEST
    call fwk_ecs_entity_set_mask
    jp nc, _ecsmanager_fail
    cp #FWK_ECS_ERR_RENDER
    jp nz, _ecsmanager_fail
    res 2, ECS_E_RENDER_FLAGS(iy)

    ;; Callback abort with A=0 is normalized and always releases the lock.
    ld iy, #0x1234
    ld bc, #0
    ld hl, #_ecsmanager_abort_callback
    call fwk_ecs_system_run
    jp nc, _ecsmanager_fail
    cp #FWK_ECS_ERR_CALLBACK
    jp nz, _ecsmanager_fail
    ld a, FWK_ECS_MANAGER_LOCK(ix)
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

    ;; Cadence: create four entities with different periods and phases.
    ld ix, #ecsmanager_cad_manager
    call fwk_ecs_manager_init
    call _ecsmanager_expect_ok
    ld hl, #ecsmanager_cad_table
    ld b, #ECSMANAGER_CAD_CAPACITY
_ecsmanager_cad_create:
    push bc
    push hl
    ld hl, #ecsmanager_template
    ld de, #ecsmanager_cad_template
    ld bc, #ECS_ENTITY_SIZE
    ldir
    pop hl
    ld a, (hl)
    inc hl
    push hl
    ld iy, #ecsmanager_cad_template
    ld ECS_E_CADENCE(iy), a
    ld ECS_E_TYPE(iy), #0
    ld hl, #ecsmanager_cad_template
    call fwk_ecs_entity_create
    call _ecsmanager_expect_ok
    pop hl
    pop bc
    djnz _ecsmanager_cad_create

    ;; Sixteen iterations with the tick the game would increment once per loop.
    xor a
    ld (fwk_ecs_tick), a
_ecsmanager_cad_tick:
    ld ix, #ecsmanager_cad_manager
    ld bc, #ECS_C_TEST
    ld hl, #_ecsmanager_cadence_callback
    call fwk_ecs_system_run
    call _ecsmanager_expect_ok
    ld hl, #fwk_ecs_tick
    inc (hl)
    ld a, (hl)
    cp #16
    jr nz, _ecsmanager_cad_tick
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
    call _ecsmanager_expect_ok
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
    call _ecsmanager_expect_ok
    ld a, (ecsmanager_cad_storage + ECS_ENTITY_SIZE + ECS_E_TYPE)
    cp #57                                  ; every 2nd from phase 0: not due at tick 1
    ld a, #0xDB
    jp nz, _ecsmanager_fail

    ;; Creation validates the cadence byte. The manager is full, so a valid byte
    ;; reports FULL and an invalid one reports TEMPLATE: the two are told apart.
    ld hl, #ecsmanager_cad_probes
    ld b, #ECSMANAGER_CAD_PROBES
_ecsmanager_cad_probe:
    push bc
    push hl
    ld iy, #ecsmanager_cad_template
    ld a, (hl)
    ld ECS_E_CADENCE(iy), a
    ld hl, #ecsmanager_cad_template
    call fwk_ecs_entity_create
    pop hl
    pop bc
    jr c, _ecsmanager_cad_probe_error
    ld a, #0xDD                             ; creating must fail either way
    jp _ecsmanager_fail
_ecsmanager_cad_probe_error:
    inc hl
    cp (hl)
    ld a, #0xDC
    jp nz, _ecsmanager_fail
    inc hl
    djnz _ecsmanager_cad_probe

    ld a, #0x5A
    ld (ecsmanager_status), a
    jp _ecsmanager_loop
