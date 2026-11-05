;; Emulator harness for the ECS COLLISION system.
;; Replays the scenario generated from tools/ecs_collision_model.py and records
;; what the system produced (result, flags, events and callback arguments) in
;; ecscollision_log, which tests/emulator_smoke.py compares with the model.
.module example_ecscollision
.include "ecs_profile.inc"
.include "core/ecs_manager.inc"
.include "core/ecs_collision.inc"

.globl fwk_project_init, fwk_system_wait_frame

ECSCOLLISION_CAPACITY_A = 4
ECSCOLLISION_CAPACITY_B = 3
ECSCOLLISION_ENTITIES = 7
ECSCOLLISION_STEP_SIZE = 3 + 2 * ECSCOLLISION_ENTITIES
ECSCOLLISION_LOG_SIZE = 3072
ECSCOLLISION_CB_ENTRY = 9
ECSCOLLISION_CB_MAX = 8

.area _DATA
ecscollision_storage_a:: .ds ECS_ENTITY_SIZE * ECSCOLLISION_CAPACITY_A
ecscollision_storage_b:: .ds ECS_ENTITY_SIZE * ECSCOLLISION_CAPACITY_B
FWK_ECS_MANAGER_DESCRIPTOR ecscollision_manager_a, ecscollision_storage_a, ECSCOLLISION_CAPACITY_A
FWK_ECS_MANAGER_DESCRIPTOR ecscollision_manager_b, ecscollision_storage_b, ECSCOLLISION_CAPACITY_B

ecscollision_template: .ds ECS_ENTITY_SIZE
ecscollision_roles: .db 1, 2, 3, 1, 2, 1, 3
ecscollision_entities:: .ds 2 * ECSCOLLISION_ENTITIES

ecscollision_events_intra: .ds 8 * FWK_ECS_COLLISION_EVENT_SIZE
ecscollision_pairs_intra0: .ds 8 * FWK_ECS_COLLISION_PAIR_SIZE
ecscollision_pairs_intra1: .ds 8 * FWK_ECS_COLLISION_PAIR_SIZE
ecscollision_events_inter: .ds 8 * FWK_ECS_COLLISION_EVENT_SIZE
ecscollision_pairs_inter0: .ds 8 * FWK_ECS_COLLISION_PAIR_SIZE
ecscollision_pairs_inter1: .ds 8 * FWK_ECS_COLLISION_PAIR_SIZE
ecscollision_events_tiny: .ds 2 * FWK_ECS_COLLISION_EVENT_SIZE
ecscollision_pairs_tiny0: .ds 2 * FWK_ECS_COLLISION_PAIR_SIZE
ecscollision_pairs_tiny1: .ds 2 * FWK_ECS_COLLISION_PAIR_SIZE

FWK_ECS_COLLISION_STATE ecscollision_state_intra, _ecscollision_callback, ecscollision_events_intra, 8, ecscollision_pairs_intra0, ecscollision_pairs_intra1, 8
FWK_ECS_COLLISION_STATE ecscollision_state_inter, _ecscollision_callback, ecscollision_events_inter, 8, ecscollision_pairs_inter0, ecscollision_pairs_inter1, 8
FWK_ECS_COLLISION_STATE ecscollision_state_tiny, _ecscollision_callback, ecscollision_events_tiny, 2, ecscollision_pairs_tiny0, ecscollision_pairs_tiny1, 2

.include "game/scenario.inc"

ecscollision_status:: .db 0
ecscollision_log_length:: .dw 0
ecscollision_log:: .ds ECSCOLLISION_LOG_SIZE
_ecscollision_cb: .ds ECSCOLLISION_CB_ENTRY * ECSCOLLISION_CB_MAX
_ecscollision_cb_count: .db 0
_ecscollision_cb_ptr: .dw 0
_ecscollision_destroy: .db 0
_ecscollision_step_ptr: .dw 0
_ecscollision_step_index: .db 0
_ecscollision_mode: .db 0
_ecscollision_cmd: .db 0
_ecscollision_arg: .db 0
_ecscollision_i: .db 0
_ecscollision_result: .db 0
_ecscollision_carry: .db 0
_ecscollision_state: .dw 0
_ecscollision_log_ptr: .dw 0
_ecscollision_t_a: .db 0
_ecscollision_t_ix: .dw 0
_ecscollision_t_iy: .dw 0
_ecscollision_t_hl: .dw 0
_ecscollision_t_de: .dw 0

.area _CODE

_ecscollision_fail:
    ld (ecscollision_status), a
_ecscollision_halt:
    call fwk_system_wait_frame
    jr _ecscollision_halt

;; In: A=entity index 0..6. Out: IY=entity, IX=its manager. Modified: AF,DE,HL.
_ecscollision_entity_ptr:
    push af
    add a, a
    ld e, a
    ld d, #0
    ld hl, #ecscollision_entities
    add hl, de
    ld e, (hl)
    inc hl
    ld d, (hl)
    push de
    pop iy
    pop af
    cp #ECSCOLLISION_CAPACITY_A
    jr nc, _ecscollision_manager_b
    ld ix, #ecscollision_manager_a
    ret
_ecscollision_manager_b:
    ld ix, #ecscollision_manager_b
    ret

;; Callback contract probe: IX=A, IY=B, A=type, HL=manager A, DE=manager B.
;; Logs its arguments; on ENTER with the destroy flag it destroys entity B.
_ecscollision_callback:
    ld (_ecscollision_t_a), a
    ld (_ecscollision_t_hl), hl
    ld (_ecscollision_t_de), de
    ld (_ecscollision_t_ix), ix
    ld (_ecscollision_t_iy), iy
    ld hl, (_ecscollision_cb_ptr)
    ld a, (_ecscollision_t_a)
    ld (hl), a
    inc hl
    ld de, (_ecscollision_t_ix)
    ld (hl), e
    inc hl
    ld (hl), d
    inc hl
    ld de, (_ecscollision_t_iy)
    ld (hl), e
    inc hl
    ld (hl), d
    inc hl
    ld de, (_ecscollision_t_hl)
    ld (hl), e
    inc hl
    ld (hl), d
    inc hl
    ld de, (_ecscollision_t_de)
    ld (hl), e
    inc hl
    ld (hl), d
    inc hl
    ld (_ecscollision_cb_ptr), hl
    ld hl, #_ecscollision_cb_count
    inc (hl)
    ld a, (_ecscollision_destroy)
    or a
    jr z, _ecscollision_callback_done
    ld a, (_ecscollision_t_a)
    cp #ECS_COLLISION_ENTER
    jr nz, _ecscollision_callback_done
    ld iy, (_ecscollision_t_iy)
    ld a, ECS_E_STATUS(iy)
    cp #ECS_STATUS_ACTIVE
    jr nz, _ecscollision_callback_done
    ld ix, (_ecscollision_t_de)
    call fwk_ecs_entity_mark_destroy
    ret c
_ecscollision_callback_done:
    xor a
    ret

_ecscollision_init:
    ld ix, #ecscollision_manager_a
    call fwk_ecs_manager_init
    ld a, #0xE1
    jp c, _ecscollision_fail
    ld ix, #ecscollision_manager_b
    call fwk_ecs_manager_init
    ld a, #0xE1
    jp c, _ecscollision_fail
    ld iy, #ecscollision_template
    ;; RENDER|COLLISION occupy bits 0..1, so the high mask byte stays zero.
    ld ECS_E_COMPONENTS(iy), #(ECS_C_RENDER | ECS_C_COLLISION)
    ld ECS_E_COMPONENTS+1(iy), #0
    ld ECS_E_STATUS(iy), #ECS_STATUS_ACTIVE
    ld ECS_E_WIDTH(iy), #4
    ld ECS_E_HEIGHT(iy), #8
    xor a
    ld (_ecscollision_i), a
_ecscollision_init_loop:
    ld a, (_ecscollision_i)
    ld e, a
    ld d, #0
    ld hl, #ecscollision_roles
    add hl, de
    ld a, (hl)
    ld iy, #ecscollision_template
    ld ECS_E_COLLISION_ROLES(iy), a
    ld a, (_ecscollision_i)
    cp #ECSCOLLISION_CAPACITY_A
    jr nc, _ecscollision_init_b
    ld ix, #ecscollision_manager_a
    jr _ecscollision_init_create
_ecscollision_init_b:
    ld ix, #ecscollision_manager_b
_ecscollision_init_create:
    ld hl, #ecscollision_template
    call fwk_ecs_entity_create
    ld a, #0xE2
    jp c, _ecscollision_fail
    ld a, (_ecscollision_i)
    add a, a
    ld e, a
    ld d, #0
    ld hl, #ecscollision_entities
    add hl, de
    push iy
    pop de
    ld (hl), e
    inc hl
    ld (hl), d
    ld hl, #_ecscollision_i
    inc (hl)
    ld a, (hl)
    cp #ECSCOLLISION_ENTITIES
    jr nz, _ecscollision_init_loop
    ret

_main::
    call fwk_project_init
    call _ecscollision_init
    ld hl, #ecscollision_steps
    ld (_ecscollision_step_ptr), hl
    ld hl, #ecscollision_log
    ld (_ecscollision_log_ptr), hl
    xor a
    ld (_ecscollision_step_index), a

_ecscollision_next_step:
    ld hl, (_ecscollision_step_ptr)
    ld a, (hl)
    cp #0xFF
    jp z, _ecscollision_finished
    ld (_ecscollision_mode), a
    inc hl
    ld a, (hl)
    ld (_ecscollision_cmd), a
    inc hl
    ld a, (hl)
    ld (_ecscollision_arg), a
    inc hl
    ld (_ecscollision_step_ptr), hl

    ;; Positions of the seven entities.
    xor a
    ld (_ecscollision_i), a
_ecscollision_position_loop:
    ld a, (_ecscollision_i)
    call _ecscollision_entity_ptr
    ld hl, (_ecscollision_step_ptr)
    ld a, (hl)
    inc hl
    ld ECS_E_X(iy), a
    ld a, (hl)
    inc hl
    ld ECS_E_Y(iy), a
    ld (_ecscollision_step_ptr), hl
    ld hl, #_ecscollision_i
    inc (hl)
    ld a, (hl)
    cp #ECSCOLLISION_ENTITIES
    jr nz, _ecscollision_position_loop

    ;; Command: 1 disable, 2 enable, 3 destroy-on-enter for this step.
    ld a, (_ecscollision_cmd)
    or a
    jr z, _ecscollision_command_done
    cp #3
    jr z, _ecscollision_command_destroy
    ld a, (_ecscollision_arg)
    call _ecscollision_entity_ptr
    ld a, (_ecscollision_cmd)
    cp #1
    jr z, _ecscollision_command_disable
    call fwk_ecs_entity_enable
    ld a, #0xE3
    jp c, _ecscollision_fail
    jr _ecscollision_command_done
_ecscollision_command_disable:
    call fwk_ecs_entity_disable
    ld a, #0xE4
    jp c, _ecscollision_fail
    jr _ecscollision_command_done
_ecscollision_command_destroy:
    ld a, #1
    ld (_ecscollision_destroy), a
_ecscollision_command_done:

    xor a
    ld (_ecscollision_cb_count), a
    ld hl, #_ecscollision_cb
    ld (_ecscollision_cb_ptr), hl

    ;; Select the collision state and managers by mode.
    ld a, (_ecscollision_mode)
    ld hl, #ecscollision_manager_a
    ld de, #ecscollision_manager_a
    or a
    jr nz, _ecscollision_mode_not_intra
    ld ix, #ecscollision_state_intra
    jr _ecscollision_run
_ecscollision_mode_not_intra:
    cp #1
    jr nz, _ecscollision_mode_tiny
    ld de, #ecscollision_manager_b
    ld ix, #ecscollision_state_inter
    jr _ecscollision_run
_ecscollision_mode_tiny:
    ld ix, #ecscollision_state_tiny
_ecscollision_run:
    ld (_ecscollision_state), ix
    call fwk_ecs_system_collision
    push af
    pop hl
    ld a, h
    ld (_ecscollision_result), a
    ld a, l
    and #1
    ld (_ecscollision_carry), a

    ;; Destroy step: free the entities the callback marked.
    ld a, (_ecscollision_cmd)
    cp #3
    jr nz, _ecscollision_log_step
    xor a
    ld (_ecscollision_destroy), a
    ld ix, #ecscollision_manager_a
    call fwk_ecs_manager_collect
    ld a, #0xE5
    jp c, _ecscollision_fail
    ld ix, #ecscollision_manager_b
    call fwk_ecs_manager_collect
    ld a, #0xE5
    jp c, _ecscollision_fail

_ecscollision_log_step:
    ;; Record: index, result, carry, flags, pair count, event count, events,
    ;; callback count, callback entries.
    ld de, (_ecscollision_log_ptr)
    ld ix, (_ecscollision_state)
    ld a, (_ecscollision_step_index)
    ld (de), a
    inc de
    ld a, (_ecscollision_result)
    ld (de), a
    inc de
    ld a, (_ecscollision_carry)
    ld (de), a
    inc de
    ld a, FWK_ECS_COLLISION_FLAGS(ix)
    ld (de), a
    inc de
    ld a, FWK_ECS_COLLISION_PAIR_COUNT(ix)
    ld (de), a
    inc de
    ld a, FWK_ECS_COLLISION_EVENT_COUNT(ix)
    ld (de), a
    inc de
    ld l, a
    add a, a
    add a, a
    add a, l
    jr z, _ecscollision_no_events
    ld c, a
    ld b, #0
    ld l, FWK_ECS_COLLISION_EVENTS(ix)
    ld h, FWK_ECS_COLLISION_EVENTS+1(ix)
    ldir
_ecscollision_no_events:
    ld a, (_ecscollision_cb_count)
    ld (de), a
    inc de
    ld l, a
    add a, a
    add a, a
    add a, a
    add a, l
    jr z, _ecscollision_no_callbacks
    ld c, a
    ld b, #0
    ld hl, #_ecscollision_cb
    ldir
_ecscollision_no_callbacks:
    ld (_ecscollision_log_ptr), de
    ld hl, #ecscollision_log
    or a
    ex de, hl
    sbc hl, de
    ld (ecscollision_log_length), hl
    ld hl, #_ecscollision_step_index
    inc (hl)
    jp _ecscollision_next_step

_ecscollision_finished:
    ld a, #0x5A
    ld (ecscollision_status), a
    jp _ecscollision_halt
