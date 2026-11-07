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

;; ----------------------------------------------------------------------------
;; _ecscollision_fail
;;   Test failure exit: stores the failure code in ecscollision_status and hangs in
;;   _ecscollision_halt. Falls through into it; never returns.
;;   In : A=failure code (0xE1, 0xE2, 0xE5, 0xE6, 0xE7).
;;   Out: ecscollision_status=A. Does not return.
;;   Clobbers: all (never returns)
;;   Notes: Entered with jp. The loop it ends in calls fwk_system_wait_frame, which
;;          modifies AF, BC, DE, HL on every pass.
;; ----------------------------------------------------------------------------
_ecscollision_fail:
    ld (ecscollision_status), a         ; publish the code for the harness
;; ----------------------------------------------------------------------------
;; _ecscollision_halt
;;   Idle loop at the end of the run. The harness reads ecscollision_status: 0x5A
;;   means the whole scenario was replayed, any other non-zero value is a failure.
;;   In : none.
;;   Out: none. Does not return.
;;   Clobbers: all (never returns)
;;   Notes: Reached by fall-through from _ecscollision_fail and by jp from _main. Each
;;          pass calls fwk_system_wait_frame, which modifies AF, BC, DE, HL.
;; ----------------------------------------------------------------------------
_ecscollision_halt:
    call fwk_system_wait_frame          ; park here, one VSYNC per pass
    jr _ecscollision_halt

;; ----------------------------------------------------------------------------
;; _ecscollision_entity_ptr
;;   Looks up entity number A (0 = subject S, 1..3 = T0..T2, 4 = T3) in the
;;   ecscollision_entities pointer table.
;;   In : A=entity index 0..4 (not range checked; the table has 5 words).
;;   Out: IY=pointer to that entity's slot.
;;   Clobbers: AF, DE, HL, IY
;;   Notes: BC and IX are preserved.
;; ----------------------------------------------------------------------------
_ecscollision_entity_ptr:
    add a, a                            ; index * 2: the table holds 16-bit pointers
    ld e, a
    ld d, #0
    ld hl, #ecscollision_entities
    add hl, de
    ld e, (hl)                          ; DE = pointer (little endian)
    inc hl
    ld d, (hl)
    push de
    pop iy
    ret

;; ----------------------------------------------------------------------------
;; _ecscollision_callback
;;   Callback given to fwk_ecs_collide. Appends one 7-byte record to _ecscollision_cb
;;   (type, IY lo/hi, HL lo/hi, IX lo/hi), counts it, then acts on _ecscollision_cmd:
;;   abort with an error code, abort with A=0, destroy the target on ENTER, or continue.
;;   In : IX=manager, IY=target (0 on EXIT), HL=subject, A=ENTER/STAY/EXIT;
;;          _ecscollision_cmd=scenario command, _ecscollision_cb_ptr=next record.
;;   Out: CMD_ABORT_CODE: carry set, A=0x77. CMD_ABORT_ZERO: carry set, A=0.
;;          CMD_DESTROY on ENTER: carry/A of fwk_ecs_entity_mark_destroy.
;;          Otherwise carry clear, A=0.
;;   Clobbers: AF, BC, DE, HL (BC only changes on the destroy path, through
;;             fwk_ecs_entity_mark_destroy)
;;   Notes: Writes _ecscollision_cb, advances _ecscollision_cb_ptr, increments
;;          _ecscollision_cb_count. No bounds check: room for ECSCOLLISION_CB_MAX (4)
;;          records per pass. IX and IY are preserved (reloaded from the values saved on
;;          entry), as the fwk_ecs_collide contract requires.
;; ----------------------------------------------------------------------------
_ecscollision_callback:
    ;; Park the arguments in memory: A, HL, IX and IY are needed as scratch below.
    ld (_ecscollision_t_a), a
    ld (_ecscollision_t_hl), hl
    ld (_ecscollision_t_ix), ix
    ld (_ecscollision_t_iy), iy
    ld hl, (_ecscollision_cb_ptr)       ; append the 7-byte record: type, IY, HL, IX
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
    ;; Behavior chosen by the scenario command.
    ld a, (_ecscollision_cmd)
    cp #CMD_ABORT_CODE
    jr nz, _ecscollision_cb_not_code
    ld a, #0x77                         ; abort with a private error code
    scf
    ret
_ecscollision_cb_not_code:
    cp #CMD_ABORT_ZERO
    jr nz, _ecscollision_cb_not_zero
    xor a                               ; abort with A=0: fwk_ecs_collide must report ERR_CALLBACK
    scf
    ret
_ecscollision_cb_not_zero:
    cp #CMD_DESTROY
    jr nz, _ecscollision_cb_ok
    ld a, (_ecscollision_t_a)
    cp #ECS_COLLISION_ENTER             ; destroy only on ENTER, never on STAY or EXIT
    jr nz, _ecscollision_cb_ok
    ld ix, (_ecscollision_t_ix)     ; IX=manager, IY=target: destroy the target
    ld iy, (_ecscollision_t_iy)
    call fwk_ecs_entity_mark_destroy
    ret c                               ; pass the error of mark_destroy on
_ecscollision_cb_ok:                    ; continue the pass
    xor a
    ret

;; ----------------------------------------------------------------------------
;; _ecscollision_init
;;   Initializes the manager and creates the five test entities (4 wide, 8 high).
;;   Entities 0..3 get RENDER|COLLISION, entity 4 (T3) only RENDER. Their slot
;;   pointers go to ecscollision_entities.
;;   In : none.
;;   Out: ecscollision_manager initialized, five ACTIVE entities, ecscollision_entities
;;          filled. Carry/A on return are not meaningful.
;;   Clobbers: AF, BC, DE, HL, IX, IY
;;   Notes: On any framework error it jumps to _ecscollision_fail (0xE1 init, 0xE2 create)
;;          and does not return. Overwrites _ecscollision_i. Relies on
;;          ecscollision_template starting as zero (.ds).
;; ----------------------------------------------------------------------------
_ecscollision_init:
    ld ix, #ecscollision_manager
    call fwk_ecs_manager_init
    ld a, #0xE1                         ; (ld keeps the carry of init)
    jp c, _ecscollision_fail
    ;; Template: ACTIVE, 4 wide, 8 high; components are set per entity below.
    ld iy, #ecscollision_template
    ld ECS_E_STATUS(iy), #ECS_STATUS_ACTIVE
    ld ECS_E_WIDTH(iy), #4
    ld ECS_E_HEIGHT(iy), #8
    xor a
    ld (_ecscollision_i), a             ; entity counter 0..4
_ecscollision_init_loop:
    ;; Entities 0..3 carry RENDER|COLLISION; entity 4 (T3) only RENDER.
    ld iy, #ecscollision_template
    ld ECS_E_COMPONENTS+1(iy), #0
    ld ECS_E_COMPONENTS(iy), #(ECS_C_RENDER | ECS_C_COLLISION)
    ld a, (_ecscollision_i)
    cp #4
    jr nz, _ecscollision_init_create
    ld ECS_E_COMPONENTS(iy), #ECS_C_RENDER
_ecscollision_init_create:              ; create the entity and remember its slot
    ld ix, #ecscollision_manager
    ld hl, #ecscollision_template
    call fwk_ecs_entity_create
    ld a, #0xE2
    jp c, _ecscollision_fail
    ld a, (_ecscollision_i)             ; store IY (the new slot) at entities[i]
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

;; ----------------------------------------------------------------------------
;; _main
;;   Program entry. Replays ecscollision_steps from game/scenario.inc: for each step
;;   places the five entities, calls fwk_ecs_collide as subject S, checks the lock and
;;   appends a record to ecscollision_log.
;;   In : none (the scenario is the data in scenario.inc).
;;   Out: ecscollision_log, ecscollision_log_length filled; ecscollision_status=0x5A at
;;          the end. Does not return: ends in _ecscollision_halt.
;;   Clobbers: all (never returns)
;;   Notes: A step is cmd, pass kind, then x,y of S, T0..T3 as
;;          in the scenario file, ended by cmd 0xFF. Failure codes: 0xE5 collect failed,
;;          0xE6 lock not left set on CMD_LOCK, 0xE7 lock left set otherwise.
;; ----------------------------------------------------------------------------
_main::
    call fwk_project_init
    call _ecscollision_init
    ld hl, #ecscollision_steps          ; read cursor into the scenario
    ld (_ecscollision_step_ptr), hl
    ld hl, #ecscollision_log
    ld (_ecscollision_log_ptr), hl      ; write cursor into the log
    xor a
    ld (_ecscollision_step_index), a

_ecscollision_next_step:                ; one scenario step per pass
    ld hl, (_ecscollision_step_ptr)
    ld a, (hl)
    cp #0xFF                            ; end marker
    jp z, _ecscollision_finished
    ld (_ecscollision_cmd), a           ; byte 0: command
    inc hl
    ld a, (hl)
    ld (_ecscollision_kind), a          ; byte 1: pass kind
    inc hl
    ld (_ecscollision_step_ptr), hl

    ;; Positions of the five entities.
    xor a
    ld (_ecscollision_i), a
_ecscollision_position_loop:
    ld a, (_ecscollision_i)
    call _ecscollision_entity_ptr       ; IY = entity i; clobbers HL, so load the cursor after
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

    ;; Reset the callback record buffer for this step.
    xor a
    ld (_ecscollision_cb_count), a
    ld hl, #_ecscollision_cb
    ld (_ecscollision_cb_ptr), hl

    ld ix, #ecscollision_manager
    ld a, (_ecscollision_cmd)
    cp #CMD_LOCK
    jr nz, _ecscollision_not_lock
    ld FWK_ECS_MANAGER_LOCK(ix), #FWK_ECS_LOCK_TRAVERSAL   ; simulate a traversal in progress: expect BUSY
_ecscollision_not_lock:
    xor a
    call _ecscollision_entity_ptr    ; IY = subject (entity 0); clobbers HL/DE
    ld hl, #_ecscollision_callback
    ld a, (_ecscollision_cmd)
    cp #CMD_NULL_CB
    jr nz, _ecscollision_call
    ld hl, #0                           ; null callback: expect ERR_CALLBACK
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
    push af                             ; capture A and the carry flag together
    pop hl                              ; H = A, L = flags
    ld a, h
    ld (_ecscollision_result), a
    ld a, l
    and #1                              ; bit 0 of F is carry
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
    xor a                               ; the lock was ours: release it for the next step
    ld (ecscollision_manager + FWK_ECS_MANAGER_LOCK), a
    jr _ecscollision_lock_ok
_ecscollision_expect_unlocked:
    or a
    ld a, #0xE7
    jp nz, _ecscollision_fail
_ecscollision_lock_ok:

    ;; A destroy step marked an entity PENDING_DESTROY: free its slot now.
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
    ld a, (_ecscollision_step_index)    ; DE = log write cursor
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
    ld l, a                             ; copy count * 7 bytes of callback records
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
    ld hl, #ecscollision_log            ; log length = write cursor - log base
    or a
    ex de, hl
    sbc hl, de
    ld (ecscollision_log_length), hl
    ld hl, #_ecscollision_step_index
    inc (hl)                            ; next step number
    jp _ecscollision_next_step

_ecscollision_finished:                 ; scenario fully replayed
    ld a, #0x5A
    ld (ecscollision_status), a
    jp _ecscollision_halt
