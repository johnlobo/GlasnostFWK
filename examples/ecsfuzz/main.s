;; Differential fuzz harness for the ECS collision system.
;; tests/ecs_collision_fuzz.py writes a batch of cases into `cases` through the
;; emulator API and raises `ecsfuzz_go`; this program replays them against
;; fwk_ecs_system_collision, logs every call (result, flags, events, locks,
;; callback arguments, guard bytes around every buffer) to ecsfuzz_log, and the
;; Python model compares the log byte for byte.
.module example_ecsfuzz
.include "ecs_profile.inc"
.include "core/ecs_manager.inc"
.include "core/ecs_collision.inc"

.globl fwk_project_init, fwk_system_wait_frame, fwk_system_frame_count

GUARD = 16
GUARD_BYTE = 0xA5
LOG_SIZE = 8000
LOG_SLACK = 1700

.area _DATA
stor_a::  .ds ECS_ENTITY_SIZE * 255
stor_b::  .ds ECS_ENTITY_SIZE * 255
mgr_a::   .ds 8
mgr_b::   .ds 8
ev_pre:   .ds GUARD
events::  .ds FWK_ECS_COLLISION_EVENT_SIZE * 255
ev_post:  .ds GUARD
tb0_pre:  .ds GUARD
tb0::     .ds FWK_ECS_COLLISION_PAIR_SIZE * 255
tb0_post: .ds GUARD
tb1_pre:  .ds GUARD
tb1::     .ds FWK_ECS_COLLISION_PAIR_SIZE * 255
tb1_post: .ds GUARD
FWK_ECS_COLLISION_STATE state_tmpl, _cb, events, 0, tb0, tb1, 0
FWK_ECS_COLLISION_STATE state, _cb, events, 0, tb0, tb1, 0

cases:: .ds 8000
ecsfuzz_go:: .db 0

ecsfuzz_status:: .db 0
ecsfuzz_log_length:: .dw 0
ecsfuzz_log:: .ds LOG_SIZE
cb_log: .ds 5 * 256
na: .db 0
nb: .db 0
evcap: .db 0
paircap: .db 0
ncalls: .db 0
call_i: .db 0
case_i: .dw 0
case_ptr: .dw 0
call_ptr: .dw 0
log_ptr: .dw 0
cbmode: .db 0
abort_k: .db 0
abort_code: .db 0
nmods: .db 0
mgr_a_arg: .dw 0
mgr_b_arg: .dw 0
cb_count: .db 0
cb_ptr: .dw 0
sbits: .db 0
res: .db 0
carry: .db 0
save_ix: .dw 0
save_iy: .dw 0
lock_a: .db 0
lock_b: .db 0
t_ix: .dw 0
t_iy: .dw 0
t_hl: .dw 0
t_de: .dw 0
t_a: .db 0
tm0: .dw 0
tm_diff: .db 0
g_cap: .db 0
g_k: .db 0

.area _CODE

_fail:
    ld (ecsfuzz_status), a
_halt:
    call fwk_system_wait_frame
    jr _halt

;; In: A=count, C=multiplier. Out: HL=A*C. Modified: B, DE.
mulk:
    ld hl, #0
    or a
    ret z
    ld b, a
    ld e, c
    ld d, #0
mulk_loop:
    add hl, de
    djnz mulk_loop
    ret

;; In: HL=buffer base, A=capacity, C=item size. Out: HL=start of the tail
;; beyond capacity, BC=length up to base+255*size+GUARD.
tail_region:
    push hl
    ld (g_cap), a
    ld a, c
    ld (g_k), a
    ld a, (g_cap)
    call mulk
    pop de
    add hl, de
    push hl
    ld a, (g_cap)
    ld c, a
    ld a, #255
    sub c
    ld hl, #g_k
    ld c, (hl)
    call mulk
    ld de, #GUARD
    add hl, de
    ld b, h
    ld c, l
    pop hl
    ret

;; HL=start, BC=length (>0): fill with the guard byte.
fill:
    ld (hl), #GUARD_BYTE
    ld d, h
    ld e, l
    inc de
    dec bc
    ld a, b
    or c
    ret z
    ldir
    ret

;; HL=start, BC=length: Z set if every byte is intact.
check:
    ld a, (hl)
    cp #GUARD_BYTE
    jr nz, check_bad
    inc hl
    dec bc
    ld a, b
    or c
    jr nz, check
    ret
check_bad:
    ld a, #1
    or a
    ret

;; In: IX=manager descriptor. Recount live/active from the slots.
recount:
    ld l, FWK_ECS_MANAGER_STORAGE(ix)
    ld h, FWK_ECS_MANAGER_STORAGE+1(ix)
    push hl
    pop iy
    ld b, FWK_ECS_MANAGER_CAPACITY(ix)
    ld c, #0
    ld d, #0
recount_loop:
    ld a, ECS_E_STATUS(iy)
    or a
    jr z, recount_next
    inc c
    cp #ECS_STATUS_ACTIVE
    jr nz, recount_next
    inc d
recount_next:
    push de
    ld de, #ECS_ENTITY_SIZE
    add iy, de
    pop de
    djnz recount_loop
    ld FWK_ECS_MANAGER_LIVE_COUNT(ix), c
    ld FWK_ECS_MANAGER_ACTIVE_COUNT(ix), d
    ret

;; In: IX=descriptor, HL=storage, A=capacity.
init_manager:
    ld FWK_ECS_MANAGER_STORAGE(ix), l
    ld FWK_ECS_MANAGER_STORAGE+1(ix), h
    ld FWK_ECS_MANAGER_CAPACITY(ix), a
    ld FWK_ECS_MANAGER_STRIDE(ix), #ECS_ENTITY_SIZE
    xor a
    ld FWK_ECS_MANAGER_ACTIVE_COUNT(ix), a
    ld FWK_ECS_MANAGER_LIVE_COUNT(ix), a
    ld FWK_ECS_MANAGER_LOCK(ix), a
    ld FWK_ECS_MANAGER_FLAGS(ix), #FWK_ECS_MANAGER_INITIALIZED
    ret

setup_case:
    ld hl, #stor_a
    ld de, #stor_a + 1
    ld bc, #ECS_ENTITY_SIZE * 255 * 2 - 1
    ld (hl), #0
    ldir
    ld hl, #tb0
    ld de, #tb0 + 1
    ld bc, #FWK_ECS_COLLISION_PAIR_SIZE * 255 - 1
    ld (hl), #0
    ldir
    ld hl, #tb1
    ld de, #tb1 + 1
    ld bc, #FWK_ECS_COLLISION_PAIR_SIZE * 255 - 1
    ld (hl), #0
    ldir
    ld ix, #mgr_a
    ld hl, #stor_a
    ld a, (na)
    call init_manager
    ld ix, #mgr_b
    ld hl, #stor_b
    ld a, (nb)
    or a
    jr nz, setup_b_ok
    inc a
setup_b_ok:
    call init_manager
    ld hl, #mgr_a
    ld (mgr_a_arg), hl
    ld a, (nb)
    or a
    jr z, setup_same
    ld hl, #mgr_b
setup_same:
    ld (mgr_b_arg), hl
    ld hl, #state_tmpl
    ld de, #state
    ld bc, #FWK_ECS_COLLISION_STATE_SIZE
    ldir
    ld a, (evcap)
    ld (state + FWK_ECS_COLLISION_EVENT_CAPACITY), a
    ld a, (paircap)
    ld (state + FWK_ECS_COLLISION_PAIR_CAPACITY), a
    ret

;; In: HL=entity. Marks it for destruction if ACTIVE, via its own manager.
destroy_ent:
    push hl
    pop iy
    ld a, ECS_E_STATUS(iy)
    cp #ECS_STATUS_ACTIVE
    ret nz
    ld ix, #mgr_a
    ld a, (nb)
    or a
    jr z, destroy_go
    ld de, #stor_b
    or a
    sbc hl, de
    jr c, destroy_go
    ld ix, #mgr_b
destroy_go:
    jp fwk_ecs_entity_mark_destroy

clobber:
    ld bc, #0xB0B0
    ld de, #0xD0D0
    ld hl, #0xA1A1
    ld ix, #0x1111
    ld iy, #0x2222
    ret

_cb:
    ld (t_ix), ix
    ld (t_iy), iy
    ld (t_hl), hl
    ld (t_de), de
    ld (t_a), a
    ld hl, (t_hl)
    ld de, (mgr_a_arg)
    or a
    sbc hl, de
    jr nz, cb_badarg
    ld hl, (t_de)
    ld de, (mgr_b_arg)
    or a
    sbc hl, de
    jr z, cb_args_ok
cb_badarg:
    ld hl, #sbits
    set 5, (hl)
cb_args_ok:
    ld a, (mgr_a + FWK_ECS_MANAGER_LOCK)
    cp #FWK_ECS_LOCK_TRAVERSAL
    jr nz, cb_badlock
    ld hl, (mgr_b_arg)
    ld de, #FWK_ECS_MANAGER_LOCK
    add hl, de
    ld a, (hl)
    cp #FWK_ECS_LOCK_TRAVERSAL
    jr z, cb_lock_ok
cb_badlock:
    ld hl, #sbits
    set 4, (hl)
cb_lock_ok:
    ld hl, (cb_ptr)
    ld a, (t_a)
    ld (hl), a
    inc hl
    ld de, (t_ix)
    ld (hl), e
    inc hl
    ld (hl), d
    inc hl
    ld de, (t_iy)
    ld (hl), e
    inc hl
    ld (hl), d
    inc hl
    ld (cb_ptr), hl
    ld hl, #cb_count
    inc (hl)
    ld a, (cbmode)
    bit 0, a
    jr z, cb_no_a
    ld hl, (t_ix)
    call destroy_ent
cb_no_a:
    ld a, (cbmode)
    bit 1, a
    jr z, cb_no_b
    ld hl, (t_iy)
    call destroy_ent
cb_no_b:
    ld a, (abort_k)
    or a
    jr z, cb_ok
    ld hl, #cb_count
    cp (hl)
    jr nz, cb_ok
    call clobber
    ld a, (abort_code)
    scf
    ret
cb_ok:
    call clobber
    xor a
    ret


;; Compare the callback log with the first cb_count events (A,B,type order).
cb_verify:
    ld a, (cb_count)
    or a
    ret z
    ld b, a
    ld hl, #cb_log
    ld de, #events
cbv_loop:
    ld a, (hl)           ; type
    inc hl
    push hl
    ld hl, #4
    add hl, de
    cp (hl)
    pop hl
    jr nz, cbv_bad
    ld a, (de)
    cp (hl)
    jr nz, cbv_bad
    inc hl
    inc de
    ld a, (de)
    cp (hl)
    jr nz, cbv_bad
    inc hl
    inc de
    ld a, (de)
    cp (hl)
    jr nz, cbv_bad
    inc hl
    inc de
    ld a, (de)
    cp (hl)
    jr nz, cbv_bad
    inc hl
    inc de
    inc de
    djnz cbv_loop
    ret
cbv_bad:
    ld hl, #sbits
    set 3, (hl)
    ret

do_call:
    ld hl, (call_ptr)
    ld a, (hl)
    inc hl
    ld (cbmode), a
    ld a, (hl)
    inc hl
    ld (abort_k), a
    ld a, (hl)
    inc hl
    ld (abort_code), a
    ld a, (hl)
    inc hl
    ld (nmods), a
    ld (call_ptr), hl
mod_loop:
    ld a, (nmods)
    or a
    jr z, mods_done
    dec a
    ld (nmods), a
    ld hl, (call_ptr)
    ld a, (hl)
    inc hl
    ld de, #stor_a
    or a
    jr z, mod_base
    ld de, #stor_b
mod_base:
    ld a, (hl)
    inc hl
    push hl
    ex de, hl
    ld de, #ECS_ENTITY_SIZE
    or a
    jr z, mod_addr
    ld b, a
mod_mul:
    add hl, de
    djnz mod_mul
mod_addr:
    push hl
    pop iy
    pop hl
    ld a, (hl)
    inc hl
    ld ECS_E_STATUS(iy), a
    ld a, (hl)
    inc hl
    ld c, a
    and #0x7f
    ld ECS_E_COLLISION_ROLES(iy), a
    ld a, #3
    bit 7, c
    jr z, mod_comp
    ld a, #1
mod_comp:
    ld ECS_E_COMPONENTS(iy), a
    ld ECS_E_COMPONENTS+1(iy), #0
    ld a, (hl)
    inc hl
    ld ECS_E_X(iy), a
    ld a, (hl)
    inc hl
    ld ECS_E_Y(iy), a
    ld a, (hl)
    inc hl
    ld ECS_E_WIDTH(iy), a
    ld a, (hl)
    inc hl
    ld ECS_E_HEIGHT(iy), a
    ld (call_ptr), hl
    jr mod_loop
mods_done:
    ld ix, #mgr_a
    call recount
    ld ix, #mgr_b
    call recount

    ;; lock / uninitialized modes
    ld a, (cbmode)
    bit 7, a
    jr z, mode_no_lock_a
    ld hl, #mgr_a + FWK_ECS_MANAGER_LOCK
    ld a, (hl)
    or #FWK_ECS_LOCK_TRAVERSAL
    ld (hl), a
mode_no_lock_a:
    ld a, (cbmode)
    bit 6, a
    jr z, mode_no_lock_b
    ld hl, (mgr_b_arg)
    ld de, #FWK_ECS_MANAGER_LOCK
    add hl, de
    ld a, (hl)
    or #FWK_ECS_LOCK_RENDER
    ld (hl), a
mode_no_lock_b:
    ld a, (cbmode)
    bit 4, a
    jr z, mode_no_uninit
    ld hl, (mgr_b_arg)
    ld de, #FWK_ECS_MANAGER_FLAGS
    add hl, de
    ld (hl), #0
mode_no_uninit:

    ;; guards
    ld hl, #ev_pre
    ld bc, #GUARD
    call fill
    ld hl, #tb0_pre
    ld bc, #GUARD
    call fill
    ld hl, #tb1_pre
    ld bc, #GUARD
    call fill
    ld hl, #events
    ld a, (evcap)
    ld c, #FWK_ECS_COLLISION_EVENT_SIZE
    call tail_region
    call fill
    ld hl, #tb0
    ld a, (paircap)
    ld c, #FWK_ECS_COLLISION_PAIR_SIZE
    call tail_region
    call fill
    ld hl, #tb1
    ld a, (paircap)
    ld c, #FWK_ECS_COLLISION_PAIR_SIZE
    call tail_region
    call fill

    xor a
    ld (cb_count), a
    ld (sbits), a
    ld hl, #cb_log
    ld (cb_ptr), hl
    ld hl, (log_ptr)
    ld de, #ecsfuzz_log + LOG_SIZE - LOG_SLACK
    or a
    sbc hl, de
    ld a, #0xE9
    jp nc, _fail

    ld hl, (fwk_system_frame_count)
    ld (tm0), hl
    ld iy, #0x1357
    ld ix, #state
    ld hl, (mgr_a_arg)
    ld de, (mgr_b_arg)
    ld a, (cbmode)
    bit 5, a
    jr z, call_go
    ld hl, #0
call_go:
    call fwk_ecs_system_collision
    ld (save_ix), ix
    ld (save_iy), iy
    push af
    ld hl, (fwk_system_frame_count)
    ld de, (tm0)
    or a
    sbc hl, de
    ld a, l
    inc h
    dec h
    jr z, tm_ok
    ld a, #255
tm_ok:
    ld (tm_diff), a
    pop af
    push af
    pop hl
    ld a, h
    ld (res), a
    ld a, l
    and #1
    ld (carry), a
    ld hl, (save_iy)
    ld de, #0x1357
    or a
    sbc hl, de
    jr z, iy_ok
    ld hl, #sbits
    set 1, (hl)
iy_ok:
    ld hl, (save_ix)
    ld de, #state
    or a
    sbc hl, de
    jr z, ix_ok
    ld hl, #sbits
    set 2, (hl)
ix_ok:
    ld a, (mgr_a + FWK_ECS_MANAGER_LOCK)
    ld (lock_a), a
    ld hl, (mgr_b_arg)
    ld de, #FWK_ECS_MANAGER_LOCK
    add hl, de
    ld a, (hl)
    ld (lock_b), a
    ;; guard check
    ld hl, #ev_pre
    ld bc, #GUARD
    call check
    jr nz, guard_bad
    ld hl, #tb0_pre
    ld bc, #GUARD
    call check
    jr nz, guard_bad
    ld hl, #tb1_pre
    ld bc, #GUARD
    call check
    jr nz, guard_bad
    ld hl, #events
    ld a, (evcap)
    ld c, #FWK_ECS_COLLISION_EVENT_SIZE
    call tail_region
    call check
    jr nz, guard_bad
    ld hl, #tb0
    ld a, (paircap)
    ld c, #FWK_ECS_COLLISION_PAIR_SIZE
    call tail_region
    call check
    jr nz, guard_bad
    ld hl, #tb1
    ld a, (paircap)
    ld c, #FWK_ECS_COLLISION_PAIR_SIZE
    call tail_region
    call check
    jr z, guard_ok
guard_bad:
    ld hl, #sbits
    set 0, (hl)
guard_ok:
    ;; undo the lock/uninit modes, then collect destroyed entities
    ld a, #0
    ld (mgr_a + FWK_ECS_MANAGER_LOCK), a
    ld (mgr_b + FWK_ECS_MANAGER_LOCK), a
    ld a, #FWK_ECS_MANAGER_INITIALIZED
    ld (mgr_a + FWK_ECS_MANAGER_FLAGS), a
    ld (mgr_b + FWK_ECS_MANAGER_FLAGS), a
    ld ix, #mgr_a
    call fwk_ecs_manager_collect
    ld ix, #mgr_b
    call fwk_ecs_manager_collect

    ;; record
    ld de, (log_ptr)
    ld a, (tm_diff)
    ld (de), a
    inc de
    ld a, (call_i)
    ld (de), a
    inc de
    ld a, (res)
    ld (de), a
    inc de
    ld a, (carry)
    ld (de), a
    inc de
    ld a, (state + FWK_ECS_COLLISION_FLAGS)
    ld (de), a
    inc de
    ld a, (state + FWK_ECS_COLLISION_EVENT_COUNT)
    ld (de), a
    inc de
    ld a, (state + FWK_ECS_COLLISION_PAIR_COUNT)
    ld (de), a
    inc de
    ld a, (lock_a)
    ld (de), a
    inc de
    ld a, (lock_b)
    ld (de), a
    inc de
    ld a, (sbits)
    ld (de), a
    inc de
    ld a, (state + FWK_ECS_COLLISION_EVENT_COUNT)
    or a
    jr z, rec_no_events
    ld l, a
    ld h, #0
    ld c, l
    ld b, h
    add hl, hl
    add hl, hl
    add hl, bc
    ld b, h
    ld c, l
    ld hl, #events
    ldir
rec_no_events:
    ld a, (cb_count)
    ld (de), a
    inc de
    push de
    call cb_verify
    pop de
rec_no_cb:
    ld (log_ptr), de
    ld hl, #ecsfuzz_log
    ex de, hl
    or a
    sbc hl, de
    ld (ecsfuzz_log_length), hl
    ret

_main::
    call fwk_project_init
wait_go:
    call fwk_system_wait_frame
    ld a, (ecsfuzz_go)
    or a
    jr z, wait_go
    xor a
    ld (ecsfuzz_go), a
    ld hl, #cases
    ld (case_ptr), hl
    ld hl, #ecsfuzz_log
    ld (log_ptr), hl
    ld hl, #0
    ld (case_i), hl
next_case:
    ld hl, (case_ptr)
    ld a, (hl)
    or a
    jp z, finished
    ld (na), a
    inc hl
    ld a, (hl)
    ld (nb), a
    inc hl
    ld a, (hl)
    ld (evcap), a
    inc hl
    ld a, (hl)
    ld (paircap), a
    inc hl
    ld a, (hl)
    ld (ncalls), a
    inc hl
    ld (call_ptr), hl
    call setup_case
    xor a
    ld (call_i), a
call_loop:
    ld a, (call_i)
    ld hl, #ncalls
    cp (hl)
    jr z, case_done
    call do_call
    ld hl, #call_i
    inc (hl)
    jr call_loop
case_done:
    ld hl, (call_ptr)
    ld (case_ptr), hl
    ld hl, (case_i)
    inc hl
    ld (case_i), hl
    jp next_case
finished:
    ld a, #0x5A
    ld (ecsfuzz_status), a
    jr wait_go
