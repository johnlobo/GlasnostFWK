.module example_ecsmanager
.include "ecs_profile.inc"
.include "core/ecs_manager.inc"
.include "extensions/behavior.inc"

.globl fwk_project_init, fwk_system_wait_frame

ECSMANAGER_CAPACITY = 3

.area _DATA
ecsmanager_storage:: .ds ECS_ENTITY_SIZE * ECSMANAGER_CAPACITY
FWK_ECS_MANAGER_DESCRIPTOR ecsmanager_manager, ecsmanager_storage, ECSMANAGER_CAPACITY

ecsmanager_behavior_right:
    FWK_BEHAVIOR_SET_VX 1
    FWK_BEHAVIOR_WAIT 8, ecsmanager_behavior_left
ecsmanager_behavior_left:
    FWK_BEHAVIOR_SET_VX 0xFF
    FWK_BEHAVIOR_WAIT 8, ecsmanager_behavior_right

ecsmanager_template:
    .dw ECS_C_RENDER | ECS_C_MOTION | ECS_C_BEHAVIOR | ECS_C_TEST
    .db ECS_STATUS_ACTIVE, 7, 10, 20, 2, 8
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

    ld a, #0x5A
    ld (ecsmanager_status), a
    jp _ecsmanager_loop
