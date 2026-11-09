;; ECS 2.0 selective renderer: restore and redraw only what changed, across
;; several managers, in one global Y order. Contract and budget:
;; docs/reference/ecs-abi-2.0.md, 8. It does not defend against hostile callers: no
;; search for duplicates, no buffer overlap checks.
.module fwk_ecs_render

.include "project_config.inc"
.include "ecs_profile.inc"
.include "core/ecs_manager.inc"
.include "video/ecs_render.inc"

.globl fwk_sprite_capture, fwk_sprite_restore, fwk_sprite_draw
.globl fwk_sprite_draw_recolor
.if FWK_TRANSPARENCY_ENABLED
.globl fwk_sprite_draw_masked, fwk_sprite_draw_masked_recolor
.endif

;; BUILD REQUIREMENT: u8 coordinates, and x,y,width,height (current and
;; previous) laid out contiguously: rectangles are handled as four bytes.
.if (ECS_X_FORMAT-ECS_FORMAT_U8)|(ECS_Y_FORMAT-ECS_FORMAT_U8)|(ECS_E_Y-ECS_E_X-1)|(ECS_E_WIDTH-ECS_E_X-2)|(ECS_E_HEIGHT-ECS_E_X-3)|(ECS_E_RENDER_PREVIOUS_Y-ECS_E_RENDER_PREVIOUS_X-1)|(ECS_E_RENDER_PREVIOUS_WIDTH-ECS_E_RENDER_PREVIOUS_X-2)|(ECS_E_RENDER_PREVIOUS_HEIGHT-ECS_E_RENDER_PREVIOUS_X-3)
.error 1
.endif

.area _DATA
_ecsr_scene:   .ds 2
_ecsr_work:    .ds 2             ; work array of this call
_ecsr_n:       .ds 1             ; entries in use
_ecsr_cap:     .ds 1
_ecsr_wptr:    .ds 2
_ecsr_tptr:    .ds 2
_ecsr_mleft:   .ds 1
_ecsr_i:       .ds 1
_ecsr_j:       .ds 1
_ecsr_mode:    .ds 1
_ecsr_changed: .ds 1
_ecsr_tmp:     .ds 8             ; sort scratch (one entry)
_ecsr_need:    .ds 2             ; bytes a background buffer must hold
;; Sprite descriptor handed to video/sprite.s: data, x, y (16-bit, high bytes
;; stay zero), width, height.
_ecsr_desc:    .db 0, 0, 0, 0, 0, 0, 0, 0

.area _CODE

_ecsr_err_busy:
    ld a, #FWK_ECS_ERR_BUSY
    scf
    ret
_ecsr_err_overflow:
    ld a, #FWK_ECS_ERR_OVERFLOW
    scf
    ret
_ecsr_err_render:
    ld a, #FWK_ECS_ERR_RENDER
    scf
    ret

;; Public calls: preserve IX/IY around the bodies.
fwk_ecs_render_prepare::
    push ix
    push iy
    call _ecsr_prepare
    pop iy
    pop ix
    ret
fwk_ecs_render_restore::
    push ix
    push iy
    call _ecsr_restore
    pop iy
    pop ix
    ret
fwk_ecs_render_draw::
    push ix
    push iy
    call _ecsr_draw
    pop iy
    pop ix
    ret
fwk_ecs_render_reset::
    push ix
    push iy
    call _ecsr_reset
    pop iy
    pop ix
    ret

;; ---------------------------------------------------------------- pools

;; In: IX=pool. Out: HL=flag of its first slot, DE=slot stride (bytes + 1),
;; B=slots. Modified: AF.
_ecsr_pool_first:
    ld b, FWK_ECS_POOL_COUNT(ix)
    ld e, FWK_ECS_POOL_BYTES(ix)
    ld d, FWK_ECS_POOL_BYTES+1(ix)
    inc de
    push ix
    pop hl
    inc hl
    inc hl
    inc hl                          ; FWK_ECS_POOL_FLAGS
    ret

;; fwk_ecs_render_reset body. In: IX=scene.
_ecsr_reset:
    ld a, FWK_ECS_RENDER_STATE(ix)
    or a
    jp nz, _ecsr_err_render
    ld a, FWK_ECS_RENDER_POOL_COUNT(ix)
    or a
    ret z                           ; no pools: nothing to free
    ld b, a
    ld l, FWK_ECS_RENDER_POOLS(ix)
    ld h, FWK_ECS_RENDER_POOLS+1(ix)
_ecsr_reset_pool:
    ld e, (hl)
    inc hl
    ld d, (hl)
    inc hl
    push hl
    push bc
    push de
    pop ix                          ; IX = pool
    call _ecsr_pool_first
_ecsr_reset_slot:
    ld (hl), #0
    add hl, de
    djnz _ecsr_reset_slot
    pop bc
    pop hl
    djnz _ecsr_reset_pool
    xor a
    ret

;; In: IY=entity that must be drawn and owns no buffer. Gives it one.
;; Out: carry set when no pool has a free buffer big enough. Preserves IX, IY and
;; every register.
_ecsr_alloc:
    push af
    push bc
    push de
    push hl
    push ix
    ld hl, #0                       ; need = width * height
    ld a, ECS_E_WIDTH(iy)
    or a
    jr z, _ecsr_alloc_sized
    ld b, a
    ld e, ECS_E_HEIGHT(iy)
    ld d, #0
_ecsr_alloc_mul:
    add hl, de
    djnz _ecsr_alloc_mul
_ecsr_alloc_sized:
    ld (_ecsr_need), hl
    ld ix, (_ecsr_scene)
    ld b, FWK_ECS_RENDER_POOL_COUNT(ix)
    ld l, FWK_ECS_RENDER_POOLS(ix)
    ld h, FWK_ECS_RENDER_POOLS+1(ix)
    ld a, b
    or a
    jr z, _ecsr_alloc_fail
_ecsr_alloc_pool:
    ld e, (hl)
    inc hl
    ld d, (hl)
    inc hl
    push hl
    push bc
    push de
    pop ix                          ; IX = pool
    ld e, FWK_ECS_POOL_BYTES(ix)
    ld d, FWK_ECS_POOL_BYTES+1(ix)
    ld hl, (_ecsr_need)
    or a
    sbc hl, de                      ; need - bytes
    jr c, _ecsr_alloc_scan
    jr nz, _ecsr_alloc_next         ; the buffers of this pool are too small
_ecsr_alloc_scan:
    call _ecsr_pool_first
_ecsr_alloc_slot:
    ld a, (hl)
    or a
    jr z, _ecsr_alloc_take
    add hl, de
    djnz _ecsr_alloc_slot
_ecsr_alloc_next:
    pop bc
    pop hl
    djnz _ecsr_alloc_pool
_ecsr_alloc_fail:
    pop ix
    pop hl
    pop de
    pop bc
    pop af
    scf
    ret
_ecsr_alloc_take:
    ld (hl), #1
    inc hl                          ; the buffer follows its flag
    ld ECS_E_RENDER_BACKGROUND(iy), l
    ld ECS_E_RENDER_BACKGROUND+1(iy), h
    pop bc
    pop hl
    pop ix
    pop hl
    pop de
    pop bc
    pop af
    or a
    ret

;; In: IY=entity. Returns its background buffer to its pool (no-op without one).
;; Modified: AF, HL.
_ecsr_free:
    ld l, ECS_E_RENDER_BACKGROUND(iy)
    ld h, ECS_E_RENDER_BACKGROUND+1(iy)
    ld a, h
    or l
    ret z
    dec hl
    ld (hl), #0                     ; the flag sits just before the buffer
    xor a
    ld ECS_E_RENDER_BACKGROUND(iy), a
    ld ECS_E_RENDER_BACKGROUND+1(iy), a
    ret

;; ---------------------------------------------------------------- helpers

;; Work entry, 8 bytes: +0 entity, +2 sort key, +4 x1, +5 y1, +6 x2, +7 y2
;; (bounding box of the previous and the current rectangle).
;; A=index -> HL=entry. Modified: DE.
_ecsr_entry:
    ld l, a
    ld h, #0
    add hl, hl
    add hl, hl
    add hl, hl
    ld de, (_ecsr_work)
    add hl, de
    ret

;; A=index -> IY=entity of that entry. Modified: AF,DE,HL.
_ecsr_entity:
    call _ecsr_entry
    ld e, (hl)
    inc hl
    ld d, (hl)
    push de
    pop iy
    ret

;; A=index -> HL=address of that entity's RENDER_FLAGS. Leaves IX/IY alone.
_ecsr_flags:
    call _ecsr_entry
    ld e, (hl)
    inc hl
    ld d, (hl)
    ld hl, #ECS_E_RENDER_FLAGS
    add hl, de
    ret

;; In: IX=scene. Loads the work pointer and the entry count of the call.
_ecsr_load_work:
    ld l, FWK_ECS_RENDER_WORK(ix)
    ld h, FWK_ECS_RENDER_WORK+1(ix)
    ld (_ecsr_work), hl
    ld a, FWK_ECS_RENDER_AFFECTED(ix)
    ld (_ecsr_n), a
    ret

;; A=value: write it to the LOCK byte of every manager of the scene.
_ecsr_set_lock:
    ld c, a
    ld ix, (_ecsr_scene)
    ld l, FWK_ECS_RENDER_TABLE(ix)
    ld h, FWK_ECS_RENDER_TABLE+1(ix)
    ld b, FWK_ECS_RENDER_COUNT(ix)
_ecsr_lock_loop:
    ld a, b
    or a
    ret z
    ld e, (hl)
    inc hl
    ld d, (hl)
    inc hl
    push de
    pop ix
    ld FWK_ECS_MANAGER_LOCK(ix), c
    dec b
    jr _ecsr_lock_loop

;; In: HL=rectangle (x,y,width,height). Fills the sprite descriptor geometry.
_ecsr_make_desc:
    ld de, #_ecsr_desc+2
    ldi
    inc de
    ldi
    inc de
    ldi
    ldi
    ret

;; ---------------------------------------------------------------- prepare

_ecsr_prepare:
    ld (_ecsr_scene), ix
    ld a, FWK_ECS_RENDER_STATE(ix)
    or a
    jp nz, _ecsr_err_render
    call _ecsr_gather
    ret c
    call _ecsr_closure
    call _ecsr_compact
    ld a, #FWK_ECS_LOCK_RENDER
    call _ecsr_set_lock
    ld ix, (_ecsr_scene)
    ld FWK_ECS_RENDER_STATE(ix), #FWK_ECS_RENDER_STATE_PREPARED
    xor a
    ret

;; Candidates: entities with RENDER that must be on screen (ACTIVE|VISIBLE) or
;; that hold a captured background. Each gets a work entry with the bounding
;; box of its previous and current rectangles, and is marked DIRTY when its
;; drawn state does not match its background state. Entities are only read
;; apart from that mark: an OVERFLOW leaves at most spurious DIRTY flags.
_ecsr_gather:
    ld ix, (_ecsr_scene)
    ld l, FWK_ECS_RENDER_WORK(ix)
    ld h, FWK_ECS_RENDER_WORK+1(ix)
    ld (_ecsr_work), hl
    ld (_ecsr_wptr), hl
    ld a, FWK_ECS_RENDER_CAPACITY(ix)
    ld (_ecsr_cap), a
    ld l, FWK_ECS_RENDER_TABLE(ix)
    ld h, FWK_ECS_RENDER_TABLE+1(ix)
    ld (_ecsr_tptr), hl
    ld a, FWK_ECS_RENDER_COUNT(ix)
    ld (_ecsr_mleft), a
    xor a
    ld (_ecsr_n), a
_ecsr_g_manager:
    ld a, (_ecsr_mleft)
    or a
    ret z
    dec a
    ld (_ecsr_mleft), a
    ld hl, (_ecsr_tptr)
    ld e, (hl)
    inc hl
    ld d, (hl)
    inc hl
    ld (_ecsr_tptr), hl
    push de
    pop ix                          ; IX = manager
    ld a, FWK_ECS_MANAGER_LOCK(ix)
    or a
    jp nz, _ecsr_err_busy
    ld l, FWK_ECS_MANAGER_STORAGE(ix)
    ld h, FWK_ECS_MANAGER_STORAGE+1(ix)
    push hl
    pop iy
    ld b, FWK_ECS_MANAGER_CAPACITY(ix)
_ecsr_g_slot:
    bit ECS_C_RENDER_BIT, ECS_E_COMPONENTS(iy)
    jr z, _ecsr_g_next
    ld a, ECS_E_STATUS(iy)
    or a
    jr z, _ecsr_g_next              ; FREE
    ld c, ECS_E_RENDER_FLAGS(iy)
    ld d, #0                        ; D = 1 when it must be on screen now
    cp #ECS_STATUS_ACTIVE
    jr nz, _ecsr_g_state
    bit 0, c
    jr z, _ecsr_g_state
    inc d
_ecsr_g_state:
    ld a, c
    rrca
    rrca
    and #1
    ld e, a                         ; E = 1 when a background is captured
    or d
    jr z, _ecsr_g_next              ; neither: not a candidate
    ld a, e
    xor d
    jr z, _ecsr_g_take
    set 1, c                        ; drawn state differs from background state
    ld ECS_E_RENDER_FLAGS(iy), c
_ecsr_g_take:
    ld a, (_ecsr_n)
    ld hl, #_ecsr_cap
    cp (hl)
    jp nc, _ecsr_err_overflow
    ld a, d
    or a
    jr z, _ecsr_g_buffered          ; not drawn this frame: no buffer needed
    ld a, ECS_E_RENDER_BACKGROUND(iy)
    or ECS_E_RENDER_BACKGROUND+1(iy)
    jr nz, _ecsr_g_buffered         ; it already owns one
    call _ecsr_alloc
    jp c, _ecsr_err_overflow
_ecsr_g_buffered:
    ld a, (_ecsr_n)
    inc a
    ld (_ecsr_n), a
    ld hl, (_ecsr_wptr)
    push de                         ; D,E (flags) are still needed, B is the counter
    push iy
    pop de
    ld (hl), e
    inc hl
    ld (hl), d
    pop de
    inc hl
    inc hl
    inc hl                          ; HL = entry + 4
    call _ecsr_box
    ld (_ecsr_wptr), hl
_ecsr_g_next:
    ld e, FWK_ECS_MANAGER_STRIDE(ix)
    ld d, #0
    add iy, de
    djnz _ecsr_g_slot
    jp _ecsr_g_manager

;; In: HL=entry+4, IY=entity, D=1 if the current rectangle is occupied, E=1 if
;; the previous one is. Writes the bounding box x1,y1,x2,y2 and leaves HL
;; after it. With only one rectangle occupied the box is that rectangle.
;; Preserves IX/IY and B.
_ecsr_box:
    push ix
    push iy
    push bc
    push iy
    pop ix                          ; IX = rectangle A base, IY = rectangle B base
    ld bc, #ECS_E_RENDER_PREVIOUS_X - ECS_E_X   ; previous rectangle mirrors the current one
    ld a, d
    or a
    jr nz, _ecsr_box_a
    add ix, bc                      ; current not occupied: A is the previous one
_ecsr_box_a:
    ld a, e
    or a
    jr z, _ecsr_box_b
    add iy, bc                      ; previous occupied: B is the previous one
_ecsr_box_b:
    ld a, ECS_E_X(ix)               ; x1 = min
    cp ECS_E_X(iy)
    jr c, _ecsr_box_x1
    ld a, ECS_E_X(iy)
_ecsr_box_x1:
    ld (hl), a
    inc hl
    ld a, ECS_E_Y(ix)               ; y1 = min
    cp ECS_E_Y(iy)
    jr c, _ecsr_box_y1
    ld a, ECS_E_Y(iy)
_ecsr_box_y1:
    ld (hl), a
    inc hl
    ld a, ECS_E_X(ix)               ; x2 = max(x + width)
    add a, ECS_E_WIDTH(ix)
    jr nc, _ecsr_box_s1             ; saturate: a wrapped sum would shrink the box
    ld a, #255
_ecsr_box_s1:
    ld b, a
    ld a, ECS_E_X(iy)
    add a, ECS_E_WIDTH(iy)
    jr nc, _ecsr_box_s2
    ld a, #255
_ecsr_box_s2:
    cp b
    jr nc, _ecsr_box_x2
    ld a, b
_ecsr_box_x2:
    ld (hl), a
    inc hl
    ld a, ECS_E_Y(ix)               ; y2 = max(y + height)
    add a, ECS_E_HEIGHT(ix)
    jr nc, _ecsr_box_s3
    ld a, #255
_ecsr_box_s3:
    ld b, a
    ld a, ECS_E_Y(iy)
    add a, ECS_E_HEIGHT(iy)
    jr nc, _ecsr_box_s4
    ld a, #255
_ecsr_box_s4:
    cp b
    jr nc, _ecsr_box_y2
    ld a, b
_ecsr_box_y2:
    ld (hl), a
    inc hl
    pop bc
    pop iy
    pop ix
    ret

;; ---------------------------------------------------------------- closure

;; Mark as DIRTY everything whose bounding box overlaps a DIRTY entity's, until
;; nothing changes (a redrawn entity can uncover or cover another one).
_ecsr_closure:
    xor a
    ld (_ecsr_changed), a
    ld (_ecsr_i), a
_ecsr_cl_outer:
    ld a, (_ecsr_i)
    ld hl, #_ecsr_n
    cp (hl)
    jr z, _ecsr_cl_pass_done
    call _ecsr_flags
    bit 1, (hl)
    jr z, _ecsr_cl_outer_next
    ld a, (_ecsr_i)
    call _ecsr_entry
    push hl
    pop ix                          ; IX = entry of the dirty entity
    xor a
    ld (_ecsr_j), a
_ecsr_cl_inner:
    ld a, (_ecsr_j)
    ld hl, #_ecsr_n
    cp (hl)
    jr z, _ecsr_cl_outer_next
    inc a
    ld (_ecsr_j), a
    dec a
    call _ecsr_flags
    bit 1, (hl)
    jr nz, _ecsr_cl_inner           ; already dirty (this includes the entity itself)
    push hl                         ; flags of the candidate
    ld a, (_ecsr_j)
    dec a
    call _ecsr_entry
    push hl
    pop iy                          ; IY = entry of the candidate
    ld a, 4(ix)                     ; boxes overlap when each starts before the other ends
    cp 6(iy)
    jr nc, _ecsr_cl_no
    ld a, 4(iy)
    cp 6(ix)
    jr nc, _ecsr_cl_no
    ld a, 5(ix)
    cp 7(iy)
    jr nc, _ecsr_cl_no
    ld a, 5(iy)
    cp 7(ix)
    jr nc, _ecsr_cl_no
    pop hl
    set 1, (hl)
    ld a, #1
    ld (_ecsr_changed), a
    jr _ecsr_cl_inner
_ecsr_cl_no:
    pop hl
    jr _ecsr_cl_inner
_ecsr_cl_outer_next:
    ld hl, #_ecsr_i
    inc (hl)
    jr _ecsr_cl_outer
_ecsr_cl_pass_done:
    ld a, (_ecsr_changed)
    or a
    jr nz, _ecsr_closure
    ret

;; Keep only the DIRTY entries, in place, and publish their count.
_ecsr_compact:
    xor a
    ld (_ecsr_i), a
    ld (_ecsr_j), a
_ecsr_c_loop:
    ld a, (_ecsr_i)
    ld hl, #_ecsr_n
    cp (hl)
    jr z, _ecsr_c_done
    call _ecsr_flags
    bit 1, (hl)
    jr z, _ecsr_c_next
    ld a, (_ecsr_i)
    call _ecsr_entry
    push hl                         ; source entry
    ld a, (_ecsr_j)
    call _ecsr_entry
    ex de, hl                       ; DE = destination entry
    pop hl
    ld bc, #8
    ldir
    dec de
    dec de
    dec de
    dec de
    ld a, (_ecsr_j)
    ld (de), a                      ; entry+4 = gather index: the tie-break of both sorts
    ld hl, #_ecsr_j
    inc (hl)
_ecsr_c_next:
    ld hl, #_ecsr_i
    inc (hl)
    jr _ecsr_c_loop
_ecsr_c_done:
    ld a, (_ecsr_j)
    ld (_ecsr_n), a
    ld ix, (_ecsr_scene)
    ld FWK_ECS_RENDER_AFFECTED(ix), a
    ret

;; ---------------------------------------------------------------- ordering

;; A=0: key = Y + SORT_OFFSET_Y (current); A=1: PREVIOUS_SORT_Y. The key is
;; stored with its sign bit flipped so an unsigned compare orders signed keys.
_ecsr_set_keys:
    ld (_ecsr_mode), a
    xor a
    ld (_ecsr_i), a
_ecsr_k_loop:
    ld a, (_ecsr_i)
    ld hl, #_ecsr_n
    cp (hl)
    ret z
    call _ecsr_entity
    ld a, (_ecsr_mode)
    or a
    jr nz, _ecsr_k_previous
    ld l, ECS_E_RENDER_SORT_OFFSET_Y(iy)
    ld h, ECS_E_RENDER_SORT_OFFSET_Y+1(iy)
    ld e, ECS_E_Y(iy)
    ld d, #0
    add hl, de
    jr _ecsr_k_store
_ecsr_k_previous:
    ld l, ECS_E_RENDER_PREVIOUS_SORT_Y(iy)
    ld h, ECS_E_RENDER_PREVIOUS_SORT_Y+1(iy)
_ecsr_k_store:
    ld a, h
    xor #0x80
    ld h, a
    push hl
    ld a, (_ecsr_i)
    call _ecsr_entry
    inc hl
    inc hl
    pop de
    ld (hl), e
    inc hl
    ld (hl), d
    ld hl, #_ecsr_i
    inc (hl)
    jr _ecsr_k_loop

;; Stable insertion sort of the work entries by ascending key.
_ecsr_sort:
    ld a, #1
    ld (_ecsr_i), a
_ecsr_s_next:
    ld a, (_ecsr_i)
    ld hl, #_ecsr_n
    cp (hl)
    ret nc
    call _ecsr_entry
    ld de, #_ecsr_tmp
    ld bc, #8
    ldir                            ; tmp = entry i
    ld a, (_ecsr_i)
    ld (_ecsr_j), a
_ecsr_s_scan:
    ld a, (_ecsr_j)
    or a
    jr z, _ecsr_s_place
    dec a
    call _ecsr_entry                ; HL = entry j-1
    push hl
    inc hl
    inc hl
    ld e, (hl)
    inc hl
    ld d, (hl)                      ; DE = its key
    ld hl, (_ecsr_tmp+2)
    or a
    sbc hl, de                      ; carry when tmp.key < key(j-1): shift it up
    pop hl
    jr c, _ecsr_s_shift
    jr nz, _ecsr_s_place
    inc hl
    inc hl
    inc hl
    inc hl                          ; equal keys: the lower gather index goes first
    ld a, (_ecsr_tmp+4)
    cp (hl)
    dec hl
    dec hl
    dec hl
    dec hl
    jr nc, _ecsr_s_place
_ecsr_s_shift:
    ld a, (_ecsr_j)
    push hl
    call _ecsr_entry
    ex de, hl                       ; DE = entry j
    pop hl
    ld bc, #8
    ldir                            ; entry j = entry j-1
    ld hl, #_ecsr_j
    dec (hl)
    jr _ecsr_s_scan
_ecsr_s_place:
    ld a, (_ecsr_j)
    call _ecsr_entry
    ex de, hl
    ld hl, #_ecsr_tmp
    ld bc, #8
    ldir
    ld hl, #_ecsr_i
    inc (hl)
    jr _ecsr_s_next

;; ---------------------------------------------------------------- restore

_ecsr_restore:
    ld (_ecsr_scene), ix
    ld a, FWK_ECS_RENDER_STATE(ix)
    cp #FWK_ECS_RENDER_STATE_PREPARED
    jp nz, _ecsr_err_render
    call _ecsr_load_work
    ld a, #1
    call _ecsr_set_keys
    call _ecsr_sort
    ld a, (_ecsr_n)
    ld (_ecsr_i), a
_ecsr_r_loop:
    ld a, (_ecsr_i)
    or a
    jr z, _ecsr_r_done
    dec a
    ld (_ecsr_i), a
    call _ecsr_entity
    bit 2, ECS_E_RENDER_FLAGS(iy)
    jr z, _ecsr_r_loop              ; nothing captured for this one
    push iy
    pop hl
    ld de, #ECS_E_RENDER_PREVIOUS_X
    add hl, de
    call _ecsr_make_desc
    ld ix, #_ecsr_desc
    ld l, ECS_E_RENDER_BACKGROUND(iy)
    ld h, ECS_E_RENDER_BACKGROUND+1(iy)
    push iy
    call fwk_sprite_restore         ; clobbers IY
    pop iy
    jp c, _ecsr_err_render
    res 2, ECS_E_RENDER_FLAGS(iy)
    xor a
    ld ECS_E_RENDER_PREVIOUS_WIDTH(iy), a
    ld a, ECS_E_STATUS(iy)
    cp #ECS_STATUS_ACTIVE
    jr nz, _ecsr_r_release
    bit 0, ECS_E_RENDER_FLAGS(iy)
    jr nz, _ecsr_r_loop             ; still drawn: keeps its buffer
_ecsr_r_release:
    call _ecsr_free
    jr _ecsr_r_loop
_ecsr_r_done:
    ld ix, (_ecsr_scene)
    ld FWK_ECS_RENDER_STATE(ix), #FWK_ECS_RENDER_STATE_RESTORED
    xor a
    ret

;; ---------------------------------------------------------------- draw

_ecsr_draw:
    ld (_ecsr_scene), ix
    ld a, FWK_ECS_RENDER_STATE(ix)
    cp #FWK_ECS_RENDER_STATE_RESTORED
    jp nz, _ecsr_err_render
    call _ecsr_load_work
    xor a
    call _ecsr_set_keys
    call _ecsr_sort
    xor a
    ld (_ecsr_i), a
_ecsr_d_loop:
    ld a, (_ecsr_i)
    ld hl, #_ecsr_n
    cp (hl)
    jp z, _ecsr_d_done
    inc a
    ld (_ecsr_i), a
    dec a
    call _ecsr_entity
    ld a, ECS_E_STATUS(iy)
    cp #ECS_STATUS_ACTIVE
    jp nz, _ecsr_d_clear
    bit 0, ECS_E_RENDER_FLAGS(iy)
    jp z, _ecsr_d_clear
    push iy
    pop hl
    ld de, #ECS_E_X
    add hl, de
    call _ecsr_make_desc
    ld a, ECS_E_RENDER_SPRITE(iy)
    ld (_ecsr_desc), a
    ld a, ECS_E_RENDER_SPRITE+1(iy)
    ld (_ecsr_desc+1), a
    ld ix, #_ecsr_desc
    ld e, ECS_E_RENDER_BACKGROUND(iy)
    ld d, ECS_E_RENDER_BACKGROUND+1(iy)
    push iy
    call fwk_sprite_capture         ; clobbers IY
    pop iy
    jp c, _ecsr_err_render
    ld a, ECS_E_RENDER_FLAGS(iy)
    ld hl, #fwk_sprite_draw
    bit 4, a
    jr z, _ecsr_d_plain
    ld d, ECS_E_RENDER_SOURCE_PEN(iy)
    ld e, ECS_E_RENDER_REPLACEMENT_PEN(iy)
    ld hl, #fwk_sprite_draw_recolor
.if FWK_TRANSPARENCY_ENABLED
    bit 3, a
    jr z, _ecsr_d_go
    ld hl, #fwk_sprite_draw_masked_recolor
    jr _ecsr_d_go
_ecsr_d_plain:
    bit 3, a
    jr z, _ecsr_d_go
    ld hl, #fwk_sprite_draw_masked
.else
_ecsr_d_plain:
    bit 3, a
    jp nz, _ecsr_err_render         ; masked sprites need project transparency
.endif
_ecsr_d_go:
    push iy
    call _ecsr_jp_hl
    pop iy
    jp c, _ecsr_err_render
    set 2, ECS_E_RENDER_FLAGS(iy)   ; this frame's rectangle becomes the previous one
    push iy
    pop hl
    ld de, #ECS_E_X
    add hl, de
    push iy
    pop de
    ld bc, #ECS_E_RENDER_PREVIOUS_X
    ex de, hl
    add hl, bc
    ex de, hl
    ld bc, #ECS_E_HEIGHT + 1 - ECS_E_X          ; x, y, width, height
    ldir
    ld l, ECS_E_RENDER_SORT_OFFSET_Y(iy)
    ld h, ECS_E_RENDER_SORT_OFFSET_Y+1(iy)
    ld e, ECS_E_Y(iy)
    ld d, #0
    add hl, de
    ld ECS_E_RENDER_PREVIOUS_SORT_Y(iy), l
    ld ECS_E_RENDER_PREVIOUS_SORT_Y+1(iy), h
_ecsr_d_clear:
    res 1, ECS_E_RENDER_FLAGS(iy)
    jp _ecsr_d_loop
_ecsr_d_done:
    xor a
    call _ecsr_set_lock
    ld ix, (_ecsr_scene)
    xor a
    ld FWK_ECS_RENDER_AFFECTED(ix), a
    ld FWK_ECS_RENDER_STATE(ix), a
    ret

_ecsr_jp_hl:
    jp (hl)
