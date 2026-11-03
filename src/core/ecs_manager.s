;; GlasnostFWK ECS 2.0 stable-slot entity manager.
;; The selected project must provide ecs_profile.inc.
.module fwk_ecs_manager

.include "ecs_profile.inc"
.include "core/ecs_manager.inc"

.area _CODE

;; Common successful return.
_fwk_ecs_ok:
    xor a
    ret

;; Common error exits. Carry is set and A contains the ABI error code.
_fwk_ecs_error_argument:
    ld a, #FWK_ECS_ERR_ARGUMENT
    scf
    ret
_fwk_ecs_error_manager:
    ld a, #FWK_ECS_ERR_MANAGER
    scf
    ret
_fwk_ecs_error_full:
    ld a, #FWK_ECS_ERR_FULL
    scf
    ret
_fwk_ecs_error_template:
    ld a, #FWK_ECS_ERR_TEMPLATE
    scf
    ret
_fwk_ecs_error_entity:
    ld a, #FWK_ECS_ERR_ENTITY
    scf
    ret
_fwk_ecs_error_busy:
    ld a, #FWK_ECS_ERR_BUSY
    scf
    ret
_fwk_ecs_error_transition:
    ld a, #FWK_ECS_ERR_TRANSITION
    scf
    ret
_fwk_ecs_error_mask:
    ld a, #FWK_ECS_ERR_MASK
    scf
    ret
_fwk_ecs_error_callback:
    ld a, #FWK_ECS_ERR_CALLBACK
    scf
    ret
_fwk_ecs_error_render:
    ld a, #FWK_ECS_ERR_RENDER
    scf
    ret

;; Return Z when IX is null. Modified: AF, HL.
_fwk_ecs_ix_is_null:
    push ix
    pop hl
    ld a, h
    or l
    ret

;; Validate initialized manager.
;; In: IX=manager. Out: carry clear if valid. Modified: AF, HL.
_fwk_ecs_validate_manager:
    call _fwk_ecs_ix_is_null
    jp z, _fwk_ecs_error_argument
    ld a, FWK_ECS_MANAGER_FLAGS(ix)
    cp #FWK_ECS_MANAGER_INITIALIZED
    jp nz, _fwk_ecs_error_manager
    ld a, FWK_ECS_MANAGER_CAPACITY(ix)
    or a
    jp z, _fwk_ecs_error_manager
    ld a, FWK_ECS_MANAGER_CAPACITY(ix)
    cp FWK_ECS_MANAGER_LIVE_COUNT(ix)
    jp c, _fwk_ecs_error_manager
    ld a, FWK_ECS_MANAGER_LIVE_COUNT(ix)
    cp FWK_ECS_MANAGER_ACTIVE_COUNT(ix)
    jp c, _fwk_ecs_error_manager
    ld a, FWK_ECS_MANAGER_STRIDE(ix)
    cp #ECS_ENTITY_SIZE
    jp nz, _fwk_ecs_error_manager
    or a
    jp z, _fwk_ecs_error_manager
    cp #129
    jp nc, _fwk_ecs_error_manager
    ld a, FWK_ECS_MANAGER_LOCK(ix)
    and #0xfc
    jp nz, _fwk_ecs_error_manager
    ld l, FWK_ECS_MANAGER_STORAGE(ix)
    ld h, FWK_ECS_MANAGER_STORAGE+1(ix)
    ld a, h
    or l
    jp z, _fwk_ecs_error_manager
    or a
    ret

;; Validate BC against the component mask selected by the profile.
;; Modified: AF, HL.
_fwk_ecs_validate_mask:
    ld hl, #ECS_COMPONENT_MASK
    ld a, l
    cpl
    and c
    jr nz, _fwk_ecs_mask_bad
    ld a, h
    cpl
    and b
    ret z
_fwk_ecs_mask_bad:
    jp _fwk_ecs_error_mask

;; Validate IY belongs to IX and return its status in A.
;; A linear comparison avoids division and is used only at mutation boundaries.
;; Modified: AF, BC, DE, HL.
_fwk_ecs_validate_entity:
    push iy
    pop de
    ld a, d
    or e
    jp z, _fwk_ecs_error_entity
    ld l, FWK_ECS_MANAGER_STORAGE(ix)
    ld h, FWK_ECS_MANAGER_STORAGE+1(ix)
    ld b, FWK_ECS_MANAGER_CAPACITY(ix)
    ld c, FWK_ECS_MANAGER_STRIDE(ix)
_fwk_ecs_validate_entity_loop:
    ld a, h
    cp d
    jr nz, _fwk_ecs_validate_entity_next
    ld a, l
    cp e
    jr z, _fwk_ecs_validate_entity_found
_fwk_ecs_validate_entity_next:
    ld a, l
    add c
    ld l, a
    jr nc, _fwk_ecs_validate_entity_no_carry
    inc h
_fwk_ecs_validate_entity_no_carry:
    djnz _fwk_ecs_validate_entity_loop
    jp _fwk_ecs_error_entity
_fwk_ecs_validate_entity_found:
    ld a, ECS_E_STATUS(iy)
    or a
    ret

;; fwk_ecs_manager_init
;; In: IX=descriptor. Initializes every slot as FREE.
;; Out: ABI result. Preserves IX/IY. Modified: AF, BC, DE, HL.
fwk_ecs_manager_init::
    call _fwk_ecs_ix_is_null
    jp z, _fwk_ecs_error_argument
    ld l, FWK_ECS_MANAGER_STORAGE(ix)
    ld h, FWK_ECS_MANAGER_STORAGE+1(ix)
    ld a, h
    or l
    jp z, _fwk_ecs_error_manager
    ld a, FWK_ECS_MANAGER_CAPACITY(ix)
    or a
    jp z, _fwk_ecs_error_manager
    ld b, a
    ld a, FWK_ECS_MANAGER_STRIDE(ix)
    cp #ECS_ENTITY_SIZE
    jp nz, _fwk_ecs_error_manager
    or a
    jp z, _fwk_ecs_error_manager
    cp #129
    jp nc, _fwk_ecs_error_manager
    ld c, a
    ;; Validate base + capacity*stride <= 0x10000.
    push hl
    ld de, #0
_fwk_ecs_init_size_loop:
    ld a, e
    add c
    ld e, a
    jr nc, _fwk_ecs_init_size_no_carry
    inc d
_fwk_ecs_init_size_no_carry:
    djnz _fwk_ecs_init_size_loop
    pop hl
    add hl, de
    jr nc, _fwk_ecs_init_bounds_ok
    ld a, h                       ;; exactly 0x10000 is valid
    or l
    jp nz, _fwk_ecs_error_manager
_fwk_ecs_init_bounds_ok:
    ld b, FWK_ECS_MANAGER_CAPACITY(ix)
    ld l, FWK_ECS_MANAGER_STORAGE(ix)
    ld h, FWK_ECS_MANAGER_STORAGE+1(ix)
_fwk_ecs_init_clear_loop:
    push hl
    ld de, #ECS_E_STATUS
    add hl, de
    ld (hl), #ECS_STATUS_FREE
    pop hl
    ld e, FWK_ECS_MANAGER_STRIDE(ix)
    ld d, #0
    add hl, de
    djnz _fwk_ecs_init_clear_loop
    xor a
    ld FWK_ECS_MANAGER_ACTIVE_COUNT(ix), a
    ld FWK_ECS_MANAGER_LIVE_COUNT(ix), a
    ld FWK_ECS_MANAGER_LOCK(ix), a
    ld a, #FWK_ECS_MANAGER_INITIALIZED
    ld FWK_ECS_MANAGER_FLAGS(ix), a
    jp _fwk_ecs_ok

;; fwk_ecs_entity_create
;; In: IX=manager, HL=complete ACTIVE template. Out: IY=slot or zero.
;; Modified: AF, BC, DE, HL. Preserves IX.
fwk_ecs_entity_create::
    push hl
    call _fwk_ecs_validate_manager
    pop hl
    jr c, _fwk_ecs_create_fail
    ld a, FWK_ECS_MANAGER_LOCK(ix)
    or a
    jr nz, _fwk_ecs_create_busy
    ld a, h
    or l
    jr z, _fwk_ecs_create_template
    push hl
    inc hl
    inc hl
    ld a, (hl)
    pop hl
    cp #ECS_STATUS_ACTIVE
    jr nz, _fwk_ecs_create_template
    ld c, (hl)
    inc hl
    ld b, (hl)
    dec hl
    push hl
    call _fwk_ecs_validate_mask
    pop hl
    jr c, _fwk_ecs_create_fail
    push hl                        ;; template
    ld e, FWK_ECS_MANAGER_STORAGE(ix)
    ld d, FWK_ECS_MANAGER_STORAGE+1(ix)
    ld b, FWK_ECS_MANAGER_CAPACITY(ix)
_fwk_ecs_create_find:
    push de
    pop iy
    ld a, ECS_E_STATUS(iy)
    or a
    jr z, _fwk_ecs_create_found
    ld a, e
    add FWK_ECS_MANAGER_STRIDE(ix)
    ld e, a
    jr nc, _fwk_ecs_create_next
    inc d
_fwk_ecs_create_next:
    djnz _fwk_ecs_create_find
    pop hl
    jp _fwk_ecs_create_full
_fwk_ecs_create_found:
    ex de, hl                      ;; HL=slot
    ex (sp), hl                    ;; HL=template, stack=slot
    pop de                         ;; DE=slot
    ld c, FWK_ECS_MANAGER_STRIDE(ix)
    ld b, #0
    ldir
    inc FWK_ECS_MANAGER_ACTIVE_COUNT(ix)
    inc FWK_ECS_MANAGER_LIVE_COUNT(ix)
    jp _fwk_ecs_ok
_fwk_ecs_create_busy:
    call _fwk_ecs_zero_iy
    jp _fwk_ecs_error_busy
_fwk_ecs_create_template:
    call _fwk_ecs_zero_iy
    jp _fwk_ecs_error_template
_fwk_ecs_create_full:
    call _fwk_ecs_zero_iy
    jp _fwk_ecs_error_full
_fwk_ecs_create_fail:
    push af
    call _fwk_ecs_zero_iy
    pop af
    ret
_fwk_ecs_zero_iy:
    ld iy, #0
    ret

;; fwk_ecs_entity_mark_destroy
;; ACTIVE/DISABLED -> PENDING_DESTROY. Allowed under traversal lock only.
fwk_ecs_entity_mark_destroy::
    call _fwk_ecs_validate_manager
    ret c
    ld a, FWK_ECS_MANAGER_LOCK(ix)
    and #FWK_ECS_LOCK_RENDER
    jp nz, _fwk_ecs_error_busy
    call _fwk_ecs_validate_entity
    ret c
    cp #ECS_STATUS_ACTIVE
    jr z, _fwk_ecs_destroy_active
    cp #ECS_STATUS_DISABLED
    jp nz, _fwk_ecs_error_transition
    ld ECS_E_STATUS(iy), #ECS_STATUS_PENDING_DESTROY
    jp _fwk_ecs_ok
_fwk_ecs_destroy_active:
    ld ECS_E_STATUS(iy), #ECS_STATUS_PENDING_DESTROY
    dec FWK_ECS_MANAGER_ACTIVE_COUNT(ix)
    jp _fwk_ecs_ok

;; fwk_ecs_entity_disable -- ACTIVE -> DISABLED between traversals.
fwk_ecs_entity_disable::
    call _fwk_ecs_validate_manager
    ret c
    ld a, FWK_ECS_MANAGER_LOCK(ix)
    or a
    jp nz, _fwk_ecs_error_busy
    call _fwk_ecs_validate_entity
    ret c
    cp #ECS_STATUS_ACTIVE
    jp nz, _fwk_ecs_error_transition
    ld ECS_E_STATUS(iy), #ECS_STATUS_DISABLED
    dec FWK_ECS_MANAGER_ACTIVE_COUNT(ix)
    jp _fwk_ecs_ok

;; fwk_ecs_entity_enable -- DISABLED -> ACTIVE and mark render dirty.
fwk_ecs_entity_enable::
    call _fwk_ecs_validate_manager
    ret c
    ld a, FWK_ECS_MANAGER_LOCK(ix)
    or a
    jp nz, _fwk_ecs_error_busy
    call _fwk_ecs_validate_entity
    ret c
    cp #ECS_STATUS_DISABLED
    jp nz, _fwk_ecs_error_transition
    ld ECS_E_STATUS(iy), #ECS_STATUS_ACTIVE
    inc FWK_ECS_MANAGER_ACTIVE_COUNT(ix)
    bit ECS_C_RENDER_BIT, ECS_E_COMPONENTS(iy)
    jr z, _fwk_ecs_enable_done
    set 1, ECS_E_RENDER_FLAGS(iy)
_fwk_ecs_enable_done:
    jp _fwk_ecs_ok

;; fwk_ecs_entity_set_mask
;; In: BC=new component mask. Removing render with a live background is rejected
;; because it would make the capture unreachable to the render cleanup phase.
fwk_ecs_entity_set_mask::
    call _fwk_ecs_validate_manager
    ret c
    ld a, FWK_ECS_MANAGER_LOCK(ix)
    or a
    jp nz, _fwk_ecs_error_busy
    call _fwk_ecs_validate_mask
    ret c
    push bc
    call _fwk_ecs_validate_entity
    pop bc
    ret c
    cp #ECS_STATUS_ACTIVE
    jr z, _fwk_ecs_set_mask_live
    cp #ECS_STATUS_DISABLED
    jp nz, _fwk_ecs_error_transition
_fwk_ecs_set_mask_live:
    bit ECS_C_RENDER_BIT, ECS_E_COMPONENTS(iy)
    jr z, _fwk_ecs_set_mask_store
    bit ECS_C_RENDER_BIT, c
    jr nz, _fwk_ecs_set_mask_store
    bit 2, ECS_E_RENDER_FLAGS(iy)
    jp nz, _fwk_ecs_error_render
_fwk_ecs_set_mask_store:
    ld ECS_E_COMPONENTS(iy), c
    ld ECS_E_COMPONENTS+1(iy), b
    bit ECS_C_RENDER_BIT, c
    jr z, _fwk_ecs_set_mask_done
    set 1, ECS_E_RENDER_FLAGS(iy)
_fwk_ecs_set_mask_done:
    jp _fwk_ecs_ok

;; fwk_ecs_system_run
;; In: IX=manager, BC=required mask, HL=callback.
;; Callback gets IX/IY, must preserve both, and returns carry clear to continue.
fwk_ecs_system_run::
    ld a, h
    or l
    jp z, _fwk_ecs_error_callback
    ld (_fwk_ecs_system_callback+1), hl
    call _fwk_ecs_validate_manager
    ret c
    ld a, FWK_ECS_MANAGER_LOCK(ix)
    or a
    jp nz, _fwk_ecs_error_busy
    call _fwk_ecs_validate_mask
    ret c
    ld a, c
    ld (_fwk_ecs_system_mask_lo+1), a
    ld a, b
    ld (_fwk_ecs_system_mask_hi+1), a
    ld FWK_ECS_MANAGER_LOCK(ix), #FWK_ECS_LOCK_TRAVERSAL
    push iy
    ld l, FWK_ECS_MANAGER_STORAGE(ix)
    ld h, FWK_ECS_MANAGER_STORAGE+1(ix)
    push hl
    pop iy
    ld b, FWK_ECS_MANAGER_CAPACITY(ix)
_fwk_ecs_system_loop:
    ld a, ECS_E_STATUS(iy)
    cp #ECS_STATUS_ACTIVE
    jr nz, _fwk_ecs_system_next
_fwk_ecs_system_mask_lo:
    ld a, #0
    and ECS_E_COMPONENTS(iy)
    ld c, a
_fwk_ecs_system_mask_lo_required:
    ld a, (_fwk_ecs_system_mask_lo+1)
    cp c
    jr nz, _fwk_ecs_system_next
_fwk_ecs_system_mask_hi:
    ld a, #0
    and ECS_E_COMPONENTS+1(iy)
    ld c, a
    ld a, (_fwk_ecs_system_mask_hi+1)
    cp c
    jr nz, _fwk_ecs_system_next
    push bc
_fwk_ecs_system_callback:
    call 0
    pop bc
    jr c, _fwk_ecs_system_abort
_fwk_ecs_system_next:
    ld e, FWK_ECS_MANAGER_STRIDE(ix)
    ld d, #0
    add iy, de
    djnz _fwk_ecs_system_loop
    ld FWK_ECS_MANAGER_LOCK(ix), #0
    pop iy
    jp _fwk_ecs_ok
_fwk_ecs_system_abort:
    ld FWK_ECS_MANAGER_LOCK(ix), #0
    pop iy
    or a
    jp z, _fwk_ecs_error_callback
    scf
    ret

;; fwk_ecs_manager_collect
;; Converts all PENDING_DESTROY slots to FREE. Out: B=number collected.
fwk_ecs_manager_collect::
    call _fwk_ecs_validate_manager
    ret c
    ld a, FWK_ECS_MANAGER_LOCK(ix)
    or a
    jp nz, _fwk_ecs_error_busy
    push iy
    ld l, FWK_ECS_MANAGER_STORAGE(ix)
    ld h, FWK_ECS_MANAGER_STORAGE+1(ix)
    push hl
    pop iy
    ld c, FWK_ECS_MANAGER_CAPACITY(ix)
    ld b, #0
_fwk_ecs_collect_loop:
    ld a, ECS_E_STATUS(iy)
    cp #ECS_STATUS_PENDING_DESTROY
    jr nz, _fwk_ecs_collect_next
    ld ECS_E_STATUS(iy), #ECS_STATUS_FREE
    dec FWK_ECS_MANAGER_LIVE_COUNT(ix)
    inc b
_fwk_ecs_collect_next:
    ld e, FWK_ECS_MANAGER_STRIDE(ix)
    ld d, #0
    add iy, de
    dec c
    jr nz, _fwk_ecs_collect_loop
    pop iy
    jp _fwk_ecs_ok
