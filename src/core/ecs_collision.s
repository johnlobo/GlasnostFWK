;; ECS 2.0 entity collision system (AABB, ENTER/STAY/EXIT events).
;;
;; Direct slot iteration: the managers' slots are walked in place, no
;; gather step. Phases of one call (docs/ecs-abi-2.0.md 9.1):
;;   1. validate arguments, managers and locks (state untouched on failure);
;;   2. scan: every qualifying pair emits ENTER/STAY into the event buffer and
;;      is remembered in the idle pair table;
;;   3. EXIT: every pair of the previous table that no longer qualifies,
;;      judged by re-evaluating it, emits EXIT;
;;   4. publish counts/flags, flip the pair tables;
;;   5. deliver the kept events under FWK_ECS_LOCK_TRAVERSAL on both managers.
;; Phases 2-4 run no user code, so their working set lives in the scratch
;; variables below. Delivery state is also kept there: the system is not
;; re-entrant (a callback must not call it with other managers).
.module fwk_ecs_collision

.include "ecs_profile.inc"
.include "core/ecs_manager.inc"
.include "core/ecs_collision.inc"

;; BUILD REQUIREMENT of this module (the .error below fires when it is not met):
;;   * X and Y are u8 (ECS_X_FORMAT/ECS_Y_FORMAT == ECS_FORMAT_U8): the overlap
;;     test is 8-bit arithmetic with sums saturated at 255 (ABI 9.1);
;;   * entity fields are laid out Y=X+1 and HEIGHT=WIDTH+1: one axis routine
;;     serves X/WIDTH and then Y/HEIGHT by bumping IX and IY by one byte;
;;   * ECS_STATUS_ACTIVE == 1: the partner scan tests it with a single DEC A;
;;   * the code runs from RAM: it patches its own immediates (partner scan
;;     limits, roles mask, callback address), as core/ecs_manager.s already does.
;; A profile that violates this must not link this system, so the build stops
;; on the ".error" line below.
.if (ECS_X_FORMAT-ECS_FORMAT_U8)|(ECS_Y_FORMAT-ECS_FORMAT_U8)|(ECS_E_Y-ECS_E_X-1)|(ECS_E_HEIGHT-ECS_E_WIDTH-1)|(ECS_STATUS_ACTIVE-1)
.error 1
.endif

;; The component mask is 16 bits wide and the profile assigns the COLLISION bit
;; by selection order (0..15): address the byte that holds it.
ECS_COLL_BIT_BYTE    = ECS_E_COMPONENTS + (ECS_C_COLLISION_BIT / 8)
ECS_COLL_BIT_IN_BYTE = ECS_C_COLLISION_BIT & 7

.area _DATA
_ecscoll_state:  .ds 2          ; descriptor
_ecscoll_mgra:   .ds 2
_ecscoll_mgrb:   .ds 2
_ecscoll_two:    .ds 1          ; nonzero when two different managers
_ecscoll_bstore: .ds 2          ; manager B storage and capacity
_ecscoll_bcap:   .ds 1
_ecscoll_oleft:  .ds 1          ; outer slots left (including the current)
_ecscoll_ovf:    .ds 1          ; FWK_ECS_COLLISION_OVERFLOW once something dropped
_ecscoll_evptr:  .ds 2          ; next free event / events left to write
_ecscoll_evleft: .ds 1
_ecscoll_prev:   .ds 2          ; previous pair table and its pair count
_ecscoll_pcount: .ds 1
_ecscoll_new:    .ds 2          ; next free entry of the new table / room left
_ecscoll_pleft:  .ds 1
_ecscoll_cnt:    .ds 1          ; find_prev loop counter
_ecscoll_dptr:   .ds 2          ; delivery cursor / events left to deliver
_ecscoll_dleft:  .ds 1

.area _CODE

;; Shared error exits: carry set, A=code.
_ecscoll_err_argument:
    ld a, #FWK_ECS_ERR_ARGUMENT
    scf
    ret
_ecscoll_err_manager:
    ld a, #FWK_ECS_ERR_MANAGER
    scf
    ret
_ecscoll_err_busy:
    ld a, #FWK_ECS_ERR_BUSY
    scf
    ret
_ecscoll_err_callback:
    ld a, #FWK_ECS_ERR_CALLBACK
    scf
    ret

;; Initialized, consistent manager (the checks of the manager module).
;; In: IX=manager (non-null). Out: carry+A on error. Modified: AF, HL.
_ecscoll_validate:
    ld a, FWK_ECS_MANAGER_FLAGS(ix)
    cp #FWK_ECS_MANAGER_INITIALIZED
    jr nz, _ecscoll_err_manager
    ld a, FWK_ECS_MANAGER_CAPACITY(ix)
    or a
    jr z, _ecscoll_err_manager
    cp FWK_ECS_MANAGER_LIVE_COUNT(ix)
    jr c, _ecscoll_err_manager
    ld a, FWK_ECS_MANAGER_LIVE_COUNT(ix)
    cp FWK_ECS_MANAGER_ACTIVE_COUNT(ix)
    jr c, _ecscoll_err_manager
    ld a, FWK_ECS_MANAGER_STRIDE(ix)
    cp #ECS_ENTITY_SIZE
    jr nz, _ecscoll_err_manager
    ld a, FWK_ECS_MANAGER_LOCK(ix)
    and #0xfc
    jr nz, _ecscoll_err_manager
    ld l, FWK_ECS_MANAGER_STORAGE(ix)
    ld h, FWK_ECS_MANAGER_STORAGE+1(ix)
    ld a, h
    or l
    jr z, _ecscoll_err_manager
    ret                         ; OR cleared carry

;; In: A=capacity, HL=buffer. Out: ARGUMENT error if capacity!=0 and HL==0.
_ecscoll_check_buffer:
    or a
    ret z
    ld a, h
    or l
    ret nz
    jr _ecscoll_err_argument

;; fwk_ecs_system_collision
;; In: IX=state, HL=manager A, DE=manager B (HL==DE: single manager).
;; Out: carry clear and A=0, or carry set and A=FWK_ECS_ERR_*. Preserves IX/IY.
fwk_ecs_system_collision::
    push ix
    push iy
    call _ecscoll_run
    pop iy                      ; POP and RET leave AF untouched
    pop ix
    ret

;; The call is a pipeline of stages. Only check can fail, and it fails before
;; anything in the state is touched.
_ecscoll_run:
    call _ecscoll_check
    ret c
    call _ecscoll_setup
    call _ecscoll_scan
    call _ecscoll_exit_sweep
    call _ecscoll_publish
    jp _ecscoll_deliver

;; Stage 1: arguments, managers, locks, state buffers.
;; In: IX=state, HL=manager A, DE=manager B. Out: carry+A on error.
_ecscoll_check:
    push ix
    pop bc
    ld a, b
    or c
    jp z, _ecscoll_err_argument
    ld a, h
    or l
    jp z, _ecscoll_err_argument
    ld a, d
    or e
    jp z, _ecscoll_err_argument
    ld (_ecscoll_state), ix
    ld (_ecscoll_mgra), hl
    ld (_ecscoll_mgrb), de
    or a
    sbc hl, de
    ld a, h
    or l
    ld (_ecscoll_two), a

    ;; Managers valid, then neither may be locked.
    ld ix, (_ecscoll_mgra)
    call _ecscoll_validate
    ret c
    ld ix, (_ecscoll_mgrb)
    call _ecscoll_validate
    ret c
    ld a, FWK_ECS_MANAGER_LOCK(ix)
    ld ix, (_ecscoll_mgra)
    or FWK_ECS_MANAGER_LOCK(ix)
    jp nz, _ecscoll_err_busy

    ;; State: callback, and a non-null buffer for every non-zero capacity.
    ld ix, (_ecscoll_state)
    ld a, FWK_ECS_COLLISION_CALLBACK(ix)
    or FWK_ECS_COLLISION_CALLBACK+1(ix)
    jp z, _ecscoll_err_callback
    ld l, FWK_ECS_COLLISION_EVENTS(ix)
    ld h, FWK_ECS_COLLISION_EVENTS+1(ix)
    ld a, FWK_ECS_COLLISION_EVENT_CAPACITY(ix)
    call _ecscoll_check_buffer
    ret c
    ld l, FWK_ECS_COLLISION_PRIVATE_TABLE0(ix)
    ld h, FWK_ECS_COLLISION_PRIVATE_TABLE0+1(ix)
    ld a, FWK_ECS_COLLISION_PAIR_CAPACITY(ix)
    call _ecscoll_check_buffer
    ret c
    ld l, FWK_ECS_COLLISION_PRIVATE_TABLE1(ix)
    ld h, FWK_ECS_COLLISION_PRIVATE_TABLE1+1(ix)
    ld a, FWK_ECS_COLLISION_PAIR_CAPACITY(ix)
    jp _ecscoll_check_buffer

;; Stage 2: validation passed, from here the state is ours. Clears FLAGS and
;; loads the working set (event cursor, previous/new pair tables, manager B).
_ecscoll_setup:
    ld ix, (_ecscoll_state)
    xor a
    ld FWK_ECS_COLLISION_FLAGS(ix), a
    ld (_ecscoll_ovf), a
    ld l, FWK_ECS_COLLISION_EVENTS(ix)
    ld h, FWK_ECS_COLLISION_EVENTS+1(ix)
    ld (_ecscoll_evptr), hl
    ld a, FWK_ECS_COLLISION_EVENT_CAPACITY(ix)
    ld (_ecscoll_evleft), a
    ld a, FWK_ECS_COLLISION_PAIR_CAPACITY(ix)
    ld (_ecscoll_pleft), a
    ld c, a
    ld a, FWK_ECS_COLLISION_PAIR_COUNT(ix)
    cp c                        ; never trust a count above the capacity
    jr c, _ecscoll_count_ok
    ld a, c
_ecscoll_count_ok:
    ld (_ecscoll_pcount), a
    ld l, FWK_ECS_COLLISION_PRIVATE_TABLE0(ix)
    ld h, FWK_ECS_COLLISION_PRIVATE_TABLE0+1(ix)
    ld e, FWK_ECS_COLLISION_PRIVATE_TABLE1(ix)
    ld d, FWK_ECS_COLLISION_PRIVATE_TABLE1+1(ix)
    bit 0, FWK_ECS_COLLISION_PRIVATE_ACTIVE(ix)
    jr z, _ecscoll_tables
    ex de, hl                   ; ACTIVE=1: table 1 holds the previous pairs
_ecscoll_tables:
    ld (_ecscoll_prev), hl
    ld (_ecscoll_new), de
    ld ix, (_ecscoll_mgrb)
    ld l, FWK_ECS_MANAGER_STORAGE(ix)
    ld h, FWK_ECS_MANAGER_STORAGE+1(ix)
    ld (_ecscoll_bstore), hl
    ld a, FWK_ECS_MANAGER_CAPACITY(ix)
    ld (_ecscoll_bcap), a
    ret

;; Stage 3: scan. IY walks manager A. Per A slot, ONCE: the participant test,
;; the role swap and the box limits are computed and patched as immediates
;; into the partner test below (an A that cannot overlap anything, such as zero
;; width/height or X/Y == 255, skips its partner loop altogether). The partner
;; loop (HL on the partner status byte, B partners left, DE the stride)
;; rejects anything that is not ACTIVE with one load and one compare; an
;; ACTIVE partner runs the cheapest-first test in _ecscoll_candidate.
_ecscoll_scan:
    ld ix, (_ecscoll_mgra)
    ld l, FWK_ECS_MANAGER_STORAGE(ix)
    ld h, FWK_ECS_MANAGER_STORAGE+1(ix)
    push hl
    pop iy
    ld a, FWK_ECS_MANAGER_CAPACITY(ix)
    ld (_ecscoll_oleft), a
_ecscoll_outer:
    call _ecscoll_participant
    jr nc, _ecscoll_outer_next
    call _ecscoll_swap
    and #ECS_COLLISION_COLLIDER|ECS_COLLISION_COLLISIONABLE ; drop the shifted-out bit: roles(B) may carry reserved bits
    ld (_ecscoll_p_swap+1), a
    ;; X: partner must satisfy bx < sat(ax+aw) and sat(bx+bw) >= ax+1.
    ld a, ECS_E_WIDTH(iy)
    or a
    jr z, _ecscoll_outer_next   ; zero width never overlaps
    add a, ECS_E_X(iy)
    jr nc, _ecscoll_ax_end
    ld a, #255
_ecscoll_ax_end:
    ld (_ecscoll_p_axe+1), a
    ld a, ECS_E_X(iy)
    inc a
    jr z, _ecscoll_outer_next   ; ax == 255: nothing can lie beyond it
    ld (_ecscoll_p_ax1+1), a
    ;; Y: same with Y/HEIGHT.
    ld a, ECS_E_HEIGHT(iy)
    or a
    jr z, _ecscoll_outer_next
    add a, ECS_E_Y(iy)
    jr nc, _ecscoll_ay_end
    ld a, #255
_ecscoll_ay_end:
    ld (_ecscoll_p_aye+1), a
    ld a, ECS_E_Y(iy)
    inc a
    jr z, _ecscoll_outer_next
    ld (_ecscoll_p_ay1+1), a
    ld a, (_ecscoll_two)
    or a
    jr z, _ecscoll_single
    ld hl, (_ecscoll_bstore)    ; two managers: every slot of B
    ld a, (_ecscoll_bcap)
    jr _ecscoll_inner_start
_ecscoll_single:                ; one manager: only the slots after IY
    push iy
    pop hl
    ld de, #ECS_ENTITY_SIZE
    add hl, de
    ld a, (_ecscoll_oleft)
    dec a
    jr z, _ecscoll_outer_next
_ecscoll_inner_start:
    ld b, a
    ld de, #ECS_E_STATUS
    add hl, de
    ld de, #ECS_ENTITY_SIZE
_ecscoll_inner:
    ld a, (hl)
    dec a                       ; ACTIVE == 1 (checked by the build guard)
    jr z, _ecscoll_candidate
_ecscoll_inner_next:
    add hl, de
    djnz _ecscoll_inner
_ecscoll_outer_next:
    ld de, #ECS_ENTITY_SIZE
    add iy, de
    ld hl, #_ecscoll_oleft
    dec (hl)
    jr nz, _ecscoll_outer
    ret

;; ACTIVE partner whose status byte is at HL. Same predicate as
;; _ecscoll_pair_ok minus the parts hoisted per A, rejecting as early as
;; possible; the operands marked "patched" are written by the outer loop.
;; Uses only A and IX until a hit, so HL, B and DE survive a rejection.
_ecscoll_candidate:
    push hl
    pop ix
    .rept ECS_E_STATUS
    dec ix                      ; IX=partner slot
    .endm
    ld a, ECS_E_X(ix)
_ecscoll_p_axe:
    cp #0                       ; patched: sat(ax+aw)
    jr nc, _ecscoll_inner_next  ; bx >= end of a
    bit ECS_COLL_BIT_IN_BYTE, ECS_COLL_BIT_BYTE(ix)
    jr z, _ecscoll_inner_next
    ld a, ECS_E_COLLISION_ROLES(ix)
_ecscoll_p_swap:
    and #0                      ; patched: swapped roles of A (bits 0-1 only)
    jr z, _ecscoll_inner_next
    ld a, ECS_E_WIDTH(ix)
    or a
    jr z, _ecscoll_inner_next
    add a, ECS_E_X(ix)
    jr nc, _ecscoll_bx_end
    ld a, #255
_ecscoll_bx_end:
_ecscoll_p_ax1:
    cp #0                       ; patched: ax+1
    jr c, _ecscoll_inner_next   ; sat(bx+bw) <= ax
    ld a, ECS_E_HEIGHT(ix)
    or a
    jr z, _ecscoll_inner_next
    add a, ECS_E_Y(ix)
    jr nc, _ecscoll_by_end
    ld a, #255
_ecscoll_by_end:
_ecscoll_p_ay1:
    cp #0                       ; patched: ay+1
    jr c, _ecscoll_inner_next
    ld a, ECS_E_Y(ix)
_ecscoll_p_aye:
    cp #0                       ; patched: sat(ay+ah)
    jr nc, _ecscoll_inner_next
    push bc                     ; hit
    push hl
    call _ecscoll_contact
    pop hl
    pop bc
    ld de, #ECS_ENTITY_SIZE
    jr _ecscoll_inner_next

;; Stage 4: EXIT for every previous pair that no longer qualifies, judged by
;; re-evaluating it live (status, component, roles, overlap), in table order.
_ecscoll_exit_sweep:
    ld a, (_ecscoll_pcount)
    or a
    ret z
    ld b, a
    ld hl, (_ecscoll_prev)
_ecscoll_exit_loop:
    ld e, (hl)
    inc hl
    ld d, (hl)
    inc hl
    push de
    pop iy
    ld e, (hl)
    inc hl
    ld d, (hl)
    inc hl
    push de
    pop ix
    push hl
    call _ecscoll_pair_ok
    jr c, _ecscoll_exit_next
    ld a, #ECS_COLLISION_EXIT
    call _ecscoll_emit
_ecscoll_exit_next:
    pop hl
    djnz _ecscoll_exit_loop
    ret

;; Stage 5: publish counts and flags, flip the pair tables, arm delivery.
_ecscoll_publish:
    ld ix, (_ecscoll_state)
    ld a, FWK_ECS_COLLISION_EVENT_CAPACITY(ix)
    ld hl, #_ecscoll_evleft
    sub (hl)
    ld FWK_ECS_COLLISION_EVENT_COUNT(ix), a
    ld (_ecscoll_dleft), a
    ld a, FWK_ECS_COLLISION_PAIR_CAPACITY(ix)
    ld hl, #_ecscoll_pleft
    sub (hl)
    ld FWK_ECS_COLLISION_PAIR_COUNT(ix), a
    ld a, FWK_ECS_COLLISION_PRIVATE_ACTIVE(ix)
    xor #1
    ld FWK_ECS_COLLISION_PRIVATE_ACTIVE(ix), a
    ld a, (_ecscoll_ovf)
    ld FWK_ECS_COLLISION_FLAGS(ix), a
    ld l, FWK_ECS_COLLISION_EVENTS(ix)
    ld h, FWK_ECS_COLLISION_EVENTS+1(ix)
    ld (_ecscoll_dptr), hl
    ld l, FWK_ECS_COLLISION_CALLBACK(ix)
    ld h, FWK_ECS_COLLISION_CALLBACK+1(ix)
    ld (_ecscoll_callback+1), hl
    ret

;; Stage 6: deliver the kept events under the traversal lock (taken once per
;; distinct manager, always released). Callback gets IX=A IY=B A=type HL=mgr A
;; DE=mgr B. Out: ABI result (CALLBACK, OVERFLOW or OK).
_ecscoll_deliver:
    ld d, #FWK_ECS_LOCK_TRAVERSAL
    call _ecscoll_set_lock
_ecscoll_deliver_loop:
    ld a, (_ecscoll_dleft)
    or a
    jr z, _ecscoll_deliver_done
    dec a
    ld (_ecscoll_dleft), a
    ld hl, (_ecscoll_dptr)
    ld e, (hl)
    inc hl
    ld d, (hl)
    inc hl
    push de
    ld e, (hl)
    inc hl
    ld d, (hl)
    inc hl
    push de
    ld a, (hl)
    inc hl
    ld (_ecscoll_dptr), hl
    pop iy                      ; entity B
    pop ix                      ; entity A
    ld hl, (_ecscoll_mgra)
    ld de, (_ecscoll_mgrb)
_ecscoll_callback:
    call 0
    jr nc, _ecscoll_deliver_loop
    ld d, #0                    ; callback aborted: release, normalize A==0
    call _ecscoll_set_lock
    or a
    jp z, _ecscoll_err_callback
    scf
    ret
_ecscoll_deliver_done:
    ld d, #0
    call _ecscoll_set_lock
    ld a, (_ecscoll_ovf)
    or a
    ret z                       ; A=0, carry clear
    ld a, #FWK_ECS_ERR_OVERFLOW
    scf
    ret

;; In: D=lock value. Writes it to manager A and, if different, manager B.
;; Preserves AF and D. Modified: IX.
_ecscoll_set_lock:
    ld ix, (_ecscoll_mgra)
    ld FWK_ECS_MANAGER_LOCK(ix), d
    ld ix, (_ecscoll_mgrb)
    ld FWK_ECS_MANAGER_LOCK(ix), d
    ret


;; In: IY=entity. Out: carry set and A=roles&3 if it takes part (ACTIVE, has
;; the COLLISION component and at least one role). Modified: AF.
_ecscoll_participant:
    ld a, ECS_E_STATUS(iy)
    cp #ECS_STATUS_ACTIVE
    jr nz, _ecscoll_no
    bit ECS_COLL_BIT_IN_BYTE, ECS_COLL_BIT_BYTE(iy)
    jr z, _ecscoll_no
    ld a, ECS_E_COLLISION_ROLES(iy)
    and #ECS_COLLISION_COLLIDER|ECS_COLLISION_COLLISIONABLE
    jr z, _ecscoll_no
    scf
    ret
_ecscoll_no:
    or a                        ; carry clear
    ret

;; In: A=roles&3. Out: A with COLLIDER and COLLISIONABLE swapped (bit 2 may be
;; set; the user masks). A pair is valid iff swapped(roles A) & roles B != 0.
;; Modified: AF, C.
_ecscoll_swap:
    ld c, a
    srl c
    add a, a
    or c
    ret

;; Full live test of the pair {IY,IX}: both take part, roles compatible,
;; boxes strictly overlap. Used by the EXIT sweep.
;; Out: carry set if it qualifies. Preserves IX/IY/B. Modified: AF, C.
_ecscoll_pair_ok:
    call _ecscoll_participant
    ret nc
    call _ecscoll_swap
    ld c, a
    ld a, ECS_E_STATUS(ix)
    cp #ECS_STATUS_ACTIVE
    jr nz, _ecscoll_no
    ld a, c

;; Rest of the pair test once IY is known to take part and IX is ACTIVE,
;; cheapest rejection first (component bit, roles, then the two axes).
;; In: A=_ecscoll_swap(roles of IY). Out: carry set if the pair qualifies.
;; Preserves IX/IY/B. Modified: AF, C.
_ecscoll_pair_rest:
    ld c, a
    bit ECS_COLL_BIT_IN_BYTE, ECS_COLL_BIT_BYTE(ix)
    jr z, _ecscoll_no
    ld a, ECS_E_COLLISION_ROLES(ix)
    and c
    and #ECS_COLLISION_COLLIDER|ECS_COLLISION_COLLISIONABLE
    jr z, _ecscoll_no
    call _ecscoll_axis          ; X
    ret nc
    inc iy
    inc ix
    call _ecscoll_axis          ; Y
    dec iy                      ; 16-bit INC/DEC keep the carry
    dec ix
    ret

;; One axis of the strict test with saturated sums and non-zero extents:
;;   a < min(255, b+bw) and b < min(255, a+aw).
;; In: IY, IX at the X (or Y) field offset. Out: carry set if they overlap.
;; Modified: AF, C.
_ecscoll_axis:
    ld a, ECS_E_WIDTH(ix)
    or a
    ret z
    add a, ECS_E_X(ix)
    jr nc, _ecscoll_axis_1
    ld a, #255
_ecscoll_axis_1:
    ld c, a
    ld a, ECS_E_X(iy)
    cp c
    ret nc                      ; a >= end of b
    ld a, ECS_E_WIDTH(iy)
    or a
    ret z
    add a, ECS_E_X(iy)
    jr nc, _ecscoll_axis_2
    ld a, #255
_ecscoll_axis_2:
    ld c, a
    ld a, ECS_E_X(ix)
    cp c                        ; carry iff b < end of a
    ret

;; A qualifying pair {IY,IX} was scanned: ENTER/STAY event, remember the pair.
;; Preserves IX/IY only (the scan saves BC/HL around it).
_ecscoll_contact:
    call _ecscoll_find_prev
    ld a, #ECS_COLLISION_ENTER
    jr nc, _ecscoll_contact_type
    ld a, #ECS_COLLISION_STAY
_ecscoll_contact_type:
    call _ecscoll_emit
    ld a, (_ecscoll_pleft)
    or a
    jr z, _ecscoll_overflow
    dec a
    ld (_ecscoll_pleft), a
    ld hl, (_ecscoll_new)
    call _ecscoll_put_pair
    ld (_ecscoll_new), hl
    ret

;; Is {IY,IX} in the previous table? Out: carry set if found.
;; Preserves IX/IY. Modified: AF, BC, DE, HL.
_ecscoll_find_prev:
    ld a, (_ecscoll_pcount)
    or a
    ret z
    ld (_ecscoll_cnt), a
    push iy
    pop de
    push ix
    pop bc
    ld hl, (_ecscoll_prev)
_ecscoll_find_loop:
    ld a, (hl)
    inc hl
    cp e
    jr nz, _ecscoll_find_skip3
    ld a, (hl)
    inc hl
    cp d
    jr nz, _ecscoll_find_skip2
    ld a, (hl)
    inc hl
    cp c
    jr nz, _ecscoll_find_skip1
    ld a, (hl)
    cp b
    jr nz, _ecscoll_find_skip1
    scf
    ret
_ecscoll_find_skip3:
    inc hl
_ecscoll_find_skip2:
    inc hl
_ecscoll_find_skip1:
    inc hl
    ld a, (_ecscoll_cnt)
    dec a
    ld (_ecscoll_cnt), a
    jr nz, _ecscoll_find_loop
    or a                        ; not found: carry clear (A is 0 here)
    ret

;; Append event {IY,IX,A} if there is room; otherwise raise OVERFLOW.
;; Preserves IX/IY/B. Modified: AF, C, DE, HL.
_ecscoll_emit:
    ld c, a
    ld a, (_ecscoll_evleft)
    or a
    jr z, _ecscoll_overflow
    dec a
    ld (_ecscoll_evleft), a
    ld hl, (_ecscoll_evptr)
    call _ecscoll_put_pair
    ld (hl), c
    inc hl
    ld (_ecscoll_evptr), hl
    ret
_ecscoll_overflow:
    ld a, #FWK_ECS_COLLISION_OVERFLOW
    ld (_ecscoll_ovf), a
    ret

;; Write the entity pointers IY, IX at (HL); HL advances 4. Modified: DE, HL.
_ecscoll_put_pair:
    push iy
    pop de
    ld (hl), e
    inc hl
    ld (hl), d
    inc hl
    push ix
    pop de
    ld (hl), e
    inc hl
    ld (hl), d
    inc hl
    ret
