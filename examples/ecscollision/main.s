;; Emulator harness for fwk_ecs_collide.
;; Replays the scenario generated from tools/ecs_collision_model.py and records
;; what the routine did (result, CONTACT byte, callback arguments) in
;; ecscollision_log; tests/emulator_smoke.py compares it with the model.
.module example_ecscollision
.include "ecs_profile.inc"
.include "core/ecs_manager.inc"
.include "core/ecs_collision.inc"

.globl fwk_project_init, fwk_system_wait_frame

ECSCOLLISION_CAPACITY = 5
ECSCOLLISION_ENTITIES = 5
ECSCOLLISION_STEP_SIZE = 1 + 2 * ECSCOLLISION_ENTITIES
ECSCOLLISION_CB_ENTRY = 7
ECSCOLLISION_CB_MAX = 4
ECSCOLLISION_LOG_SIZE = 768

CMD_DESTROY    = 1
CMD_ABORT_CODE = 2
CMD_LOCK       = 3
CMD_NULL_CB    = 4
CMD_ABORT_ZERO = 5

.area _DATA
ecscollision_storage:: .ds ECS_ENTITY_SIZE * ECSCOLLISION_CAPACITY
FWK_ECS_MANAGER_DESCRIPTOR ecscollision_manager, ecscollision_storage, ECSCOLLISION_CAPACITY

ecscollision_template: .ds ECS_ENTITY_SIZE
ecscollision_entities:: .ds 2 * ECSCOLLISION_ENTITIES

.include "game/scenario.inc"

ecscollision_status:: .db 0
ecscollision_log_length:: .dw 0
ecscollision_log:: .ds ECSCOLLISION_LOG_SIZE
_ecscollision_cb: .ds ECSCOLLISION_CB_ENTRY * ECSCOLLISION_CB_MAX
_ecscollision_cb_count: .db 0
_ecscollision_cb_ptr: .dw 0
_ecscollision_cmd: .db 0
_ecscollision_kind: .db 0
_ecscollision_step_ptr: .dw 0
_ecscollision_step_index: .db 0
_ecscollision_i: .db 0
_ecscollision_result: .db 0
_ecscollision_carry: .db 0
_ecscollision_log_ptr: .dw 0
_ecscollision_t_a: .db 0
_ecscollision_t_ix: .dw 0
_ecscollision_t_iy: .dw 0
_ecscollision_t_hl: .dw 0

.area _CODE

_ecscollision_fail:
    ld (ecscollision_status), a
_ecscollision_halt:
    call fwk_system_wait_frame
    jr _ecscollision_halt

;; In: A=entity index. Out: IY=entity. Modified: AF,DE,HL.
_ecscollision_entity_ptr:
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
    ret

;; Callback contract probe: IX=manager, IY=target (0 on EXIT), HL=subject, A=type.
_ecscollision_callback:
    ld (_ecscollision_t_a), a
    ld (_ecscollision_t_hl), hl
    ld (_ecscollision_t_ix), ix
    ld (_ecscollision_t_iy), iy
    ld hl, (_ecscollision_cb_ptr)
    ld a, (_ecscollision_t_a)
    ld (hl), a
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
    ld de, (_ecscollision_t_ix)
    ld (hl), e
    inc hl
    ld (hl), d
    inc hl
    ld (_ecscollision_cb_ptr), hl
    ld hl, #_ecscollision_cb_count
    inc (hl)
    ld a, (_ecscollision_cmd)
    cp #CMD_ABORT_CODE
    jr nz, _ecscollision_cb_not_code
    ld a, #0x77
    scf
    ret
_ecscollision_cb_not_code:
    cp #CMD_ABORT_ZERO
    jr nz, _ecscollision_cb_not_zero
    xor a
    scf
    ret
_ecscollision_cb_not_zero:
    cp #CMD_DESTROY
    jr nz, _ecscollision_cb_ok
    ld a, (_ecscollision_t_a)
    cp #ECS_COLLISION_ENTER
    jr nz, _ecscollision_cb_ok
    ld ix, (_ecscollision_t_ix)     ; IX=manager, IY=target: destroy the target
    ld iy, (_ecscollision_t_iy)
    call fwk_ecs_entity_mark_destroy
    ret c
_ecscollision_cb_ok:
    xor a
    ret

_ecscollision_init:
    ld ix, #ecscollision_manager
    call fwk_ecs_manager_init
    ld a, #0xE1
    jp c, _ecscollision_fail
    ld iy, #ecscollision_template
    ld ECS_E_STATUS(iy), #ECS_STATUS_ACTIVE
    ld ECS_E_WIDTH(iy), #4
    ld ECS_E_HEIGHT(iy), #8
    xor a
    ld (_ecscollision_i), a
_ecscollision_init_loop:
    ;; Entities 0..3 carry RENDER|COLLISION; entity 4 (T3) only RENDER.
    ld iy, #ecscollision_template
    ld ECS_E_COMPONENTS+1(iy), #0
    ld ECS_E_COMPONENTS(iy), #(ECS_C_RENDER | ECS_C_COLLISION)
    ld a, (_ecscollision_i)
    cp #4
    jr nz, _ecscollision_init_create
    ld ECS_E_COMPONENTS(iy), #ECS_C_RENDER
_ecscollision_init_create:
    ld ix, #ecscollision_manager
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
    ld (_ecscollision_cmd), a
    inc hl
    ld a, (hl)
    ld (_ecscollision_kind), a
    inc hl
    ld (_ecscollision_step_ptr), hl

    ;; Positions of the five entities.
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

    xor a
    ld (_ecscollision_cb_count), a
    ld hl, #_ecscollision_cb
    ld (_ecscollision_cb_ptr), hl

    ld ix, #ecscollision_manager
    ld a, (_ecscollision_cmd)
    cp #CMD_LOCK
    jr nz, _ecscollision_not_lock
    ld FWK_ECS_MANAGER_LOCK(ix), #FWK_ECS_LOCK_TRAVERSAL
_ecscollision_not_lock:
    xor a
    call _ecscollision_entity_ptr    ; IY = subject (entity 0); clobbers HL/DE
    ld hl, #_ecscollision_callback
    ld a, (_ecscollision_cmd)
    cp #CMD_NULL_CB
    jr nz, _ecscollision_call
    ld hl, #0
_ecscollision_call:
    ;; Pass kind 0: targets with COLLISION, channel 1; kind 1: every RENDER
    ;; entity, channel 2.
    ld bc, #ECS_C_COLLISION
    ld e, #1
    ld a, (_ecscollision_kind)
    or a
    jr z, _ecscollision_do_call
    ld bc, #ECS_C_RENDER
    ld e, #2
_ecscollision_do_call:
    call fwk_ecs_collide
    push af
    pop hl
    ld a, h
    ld (_ecscollision_result), a
    ld a, l
    and #1
    ld (_ecscollision_carry), a

    ;; fwk_ecs_collide must never leave a lock behind and must not clear a
    ;; lock it did not set (BUSY).
    ld a, (_ecscollision_cmd)
    cp #CMD_LOCK
    ld a, (ecscollision_manager + FWK_ECS_MANAGER_LOCK)
    jr nz, _ecscollision_expect_unlocked
    cp #FWK_ECS_LOCK_TRAVERSAL
    ld a, #0xE6
    jp nz, _ecscollision_fail
    xor a
    ld (ecscollision_manager + FWK_ECS_MANAGER_LOCK), a
    jr _ecscollision_lock_ok
_ecscollision_expect_unlocked:
    or a
    ld a, #0xE7
    jp nz, _ecscollision_fail
_ecscollision_lock_ok:

    ld a, (_ecscollision_cmd)
    cp #CMD_DESTROY
    jr nz, _ecscollision_log_step
    ld ix, #ecscollision_manager
    call fwk_ecs_manager_collect
    ld a, #0xE5
    jp c, _ecscollision_fail

_ecscollision_log_step:
    ;; Record: step, result, carry, CONTACT of S, callback count, callbacks.
    xor a
    call _ecscollision_entity_ptr    ; IY = S; clobbers DE, so before loading it
    ld de, (_ecscollision_log_ptr)
    ld a, (_ecscollision_step_index)
    ld (de), a
    inc de
    ld a, (_ecscollision_result)
    ld (de), a
    inc de
    ld a, (_ecscollision_carry)
    ld (de), a
    inc de
    ld a, ECS_E_COLLISION_CONTACT(iy)
    ld (de), a
    inc de
    ld a, (_ecscollision_cb_count)
    ld (de), a
    inc de
    ld l, a
    add a, a
    add a, a
    add a, a
    sub l                            ; count * 7
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
