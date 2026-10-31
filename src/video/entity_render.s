;; Selective entity renderer with caller-owned entity, work and background data.
.module fwk_entity_render
.include "cpctelera.h.s"
.include "project_config.inc"
.include "video/entity_render.inc"

.globl fwk_sprite_capture, fwk_sprite_restore, fwk_sprite_draw
.globl fwk_sprite_draw_recolor
.globl fwk_video_width_bytes, fwk_video_height
.if FWK_TRANSPARENCY_ENABLED
.globl fwk_sprite_draw_masked, fwk_sprite_draw_masked_recolor
.endif

.area _DATA
_fwk_er_list:       .dw 0
_fwk_er_entity:     .dw 0
_fwk_er_index:      .db 0
_fwk_er_slot:       .db 0
_fwk_er_key:        .dw 0
_fwk_er_sprite:     .ds 8
_fwk_er_outer:      .db 0
_fwk_er_inner:      .db 0
_fwk_er_changed:    .db 0
_fwk_er_a:          .dw 0
_fwk_er_b:          .dw 0
;; Rectangles are signed half-open x1,x2,y1,y2 intervals.
_fwk_er_rect_a:     .ds 8
_fwk_er_rect_b:     .ds 8
_fwk_er_buf_start:  .dw 0
_fwk_er_buf_end:    .dw 0

.area _CODE

;; Initialize a list before its first capture. IX/IY preserved.
fwk_entity_render_init::
    push ix
    push iy
    ld (_fwk_er_list), ix
    call _fwk_er_validate_list
    jr c, _fwk_er_init_exit
    ;; Pointer identity and declared buffer ranges are structural. Validate
    ;; every range once; the optimized frame path assumes they stay unchanged.
    ld a, #1
    ld (_fwk_er_changed), a
    call _fwk_er_validate_active_buffers
    push af
    xor a
    ld (_fwk_er_changed), a
    pop af
    jr c, _fwk_er_init_exit
    xor a
    ld FWK_ENTITY_RENDER_AFFECTED_COUNT(ix), a
    ld FWK_ENTITY_RENDER_STATE(ix), a
    ld (_fwk_er_index), a
_fwk_er_init_loop:
    call _fwk_er_next_entity
    jr z, _fwk_er_init_ok
    jr c, _fwk_er_init_loop
    push hl
    pop iy
    ld a, FWK_ENTITY_RENDER_FLAGS(iy)
    and #FWK_ENTITY_RENDER_VALID_FLAGS
    res 2, a
    bit 0, a
    jr z, _fwk_er_init_invisible
    set 1, a
    jr _fwk_er_init_flags
_fwk_er_init_invisible:
    res 1, a
_fwk_er_init_flags:
    ld FWK_ENTITY_RENDER_FLAGS(iy), a
    ld l, FWK_ENTITY_RENDER_SORT_Y(iy)
    ld h, FWK_ENTITY_RENDER_SORT_Y+1(iy)
    ld FWK_ENTITY_RENDER_PREVIOUS_SORT_Y(iy), l
    ld FWK_ENTITY_RENDER_PREVIOUS_SORT_Y+1(iy), h
    jr _fwk_er_init_loop
_fwk_er_init_ok:
    or a
_fwk_er_init_exit:
    pop iy
    pop ix
    ret

;; Revalidate a structurally changed pointer array or buffer declaration while
;; IDLE, without discarding captured backgrounds. Call after adding/replacing a
;; pointer or changing a background address/capacity.
fwk_entity_render_revalidate::
    push ix
    push iy
    ld (_fwk_er_list), ix
    ld a, FWK_ENTITY_RENDER_STATE(ix)
    or a
    jr nz, _fwk_er_revalidate_bad
    call _fwk_er_validate_list
    jr c, _fwk_er_revalidate_exit
    ld a, #1
    ld (_fwk_er_changed), a
    call _fwk_er_validate_active_buffers
    push af
    xor a
    ld (_fwk_er_changed), a
    pop af
    jr _fwk_er_revalidate_exit
_fwk_er_revalidate_bad:
    scf
_fwk_er_revalidate_exit:
    pop iy
    pop ix
    ret

;; Mark entities intersecting a caller supplied 6-byte rectangle.
;; The full overlap closure is completed by restore_dirty.
fwk_entity_render_mark_rect_dirty::
    ;; Rectangle support is completed by the same closure path: keep its
    ;; address in the sprite scratch and validate non-zero dimensions.
    push hl
    ld de, #4
    add hl, de
    ld a, (hl)
    or a
    jr z, _fwk_er_mark_bad_pop
    inc hl
    ld a, (hl)
    or a
    jr z, _fwk_er_mark_bad_pop
    pop hl
    push hl
    ld (_fwk_er_a), hl
    ld (_fwk_er_list), ix
    call _fwk_er_validate_list
    pop hl
    ret c
    ld ix, (_fwk_er_list)
    ld a, FWK_ENTITY_RENDER_STATE(ix)
    or a
    jp nz, _fwk_er_invalid
    call _fwk_er_rect_from_external
    jp _fwk_er_mark_external
_fwk_er_mark_bad_pop:
    pop hl
    jp _fwk_er_invalid

;; Validate and build the affected restore order without touching VRAM. Call
;; before VSYNC, then keep restore_dirty/draw_dirty together after VSYNC.
fwk_entity_render_prepare_dirty::
    push ix
    push iy
    ld (_fwk_er_list), ix
    ld a, FWK_ENTITY_RENDER_STATE(ix)
    or a
    jr nz, _fwk_er_prepare_invalid
    call _fwk_er_tag_original_dirty
    jr c, _fwk_er_prepare_rollback
    call _fwk_er_propagate_dirty
    jr c, _fwk_er_prepare_rollback
    call _fwk_er_preflight
    jr c, _fwk_er_prepare_rollback
    call _fwk_er_commit_dirty_tags
    ld a, #1
    call _fwk_er_build_work       ; previous_sort_y
    jr c, _fwk_er_prepare_exit
    ld ix, (_fwk_er_list)
    ld a, #FWK_ENTITY_RENDER_STATE_PREPARED
    ld FWK_ENTITY_RENDER_STATE(ix), a
    or a
    jr _fwk_er_prepare_exit
_fwk_er_prepare_invalid:
    scf
    jr _fwk_er_prepare_exit
_fwk_er_prepare_rollback:
    push af
    call _fwk_er_rollback_dirty_tags
    pop af
    scf
_fwk_er_prepare_exit:
    pop iy
    pop ix
    ret

;; Restore prepared entities in reverse previous order and enter RESTORED.
;; For compatibility, an IDLE call performs prepare_dirty first.
fwk_entity_render_restore_dirty::
    push ix
    push iy
    ld (_fwk_er_list), ix
    ld a, FWK_ENTITY_RENDER_STATE(ix)
    cp #FWK_ENTITY_RENDER_STATE_PREPARED
    jr z, _fwk_er_restore_prepared
    or a
    jr nz, _fwk_er_restore_invalid
    pop iy
    pop ix
    call fwk_entity_render_prepare_dirty
    ret c
    jp fwk_entity_render_restore_dirty
_fwk_er_restore_prepared:
    ld ix, (_fwk_er_list)
    ld a, FWK_ENTITY_RENDER_AFFECTED_COUNT(ix)
    or a
    jr z, _fwk_er_restore_done
    dec a
    ld (_fwk_er_index), a
_fwk_er_restore_loop:
    call _fwk_er_work_entity
    push hl
    pop iy
    bit 2, FWK_ENTITY_RENDER_FLAGS(iy)
    jr z, _fwk_er_restore_next
    call _fwk_er_previous_descriptor
    push iy
    ld ix, #_fwk_er_sprite
    ld l, FWK_ENTITY_RENDER_BACKGROUND(iy)
    ld h, FWK_ENTITY_RENDER_BACKGROUND+1(iy)
    call fwk_sprite_restore
    pop iy
    jr c, _fwk_er_restore_exit
    res 2, FWK_ENTITY_RENDER_FLAGS(iy)
_fwk_er_restore_next:
    ld a, (_fwk_er_index)
    or a
    jr z, _fwk_er_restore_done
    dec a
    ld (_fwk_er_index), a
    jr _fwk_er_restore_loop
_fwk_er_restore_done:
    ld ix, (_fwk_er_list)
    ld a, #FWK_ENTITY_RENDER_STATE_RESTORED
    ld FWK_ENTITY_RENDER_STATE(ix), a
    or a
    jr _fwk_er_restore_exit
_fwk_er_restore_invalid:
    scf
    jr _fwk_er_restore_exit
_fwk_er_restore_exit:
    pop iy
    pop ix
    ret

;; Capture/draw affected entities in current stable order, then return IDLE.
fwk_entity_render_draw_dirty::
    push ix
    push iy
    ld (_fwk_er_list), ix
    ld a, FWK_ENTITY_RENDER_STATE(ix)
    cp #FWK_ENTITY_RENDER_STATE_RESTORED
    jr nz, _fwk_er_draw_invalid
    xor a
    call _fwk_er_build_work       ; current sort_y
    jr c, _fwk_er_draw_exit
    xor a
    ld (_fwk_er_index), a
_fwk_er_draw_loop:
    ld ix, (_fwk_er_list)
    ld a, (_fwk_er_index)
    cp FWK_ENTITY_RENDER_AFFECTED_COUNT(ix)
    jr z, _fwk_er_draw_done
    call _fwk_er_work_entity
    push hl
    pop iy
    bit 0, FWK_ENTITY_RENDER_FLAGS(iy)
    jr z, _fwk_er_draw_clear
    call _fwk_er_visible_area
    jr c, _fwk_er_draw_exit
    ld a, b
    or c
    jr z, _fwk_er_draw_clear
    push iy
    pop ix
    ld e, FWK_ENTITY_RENDER_BACKGROUND(iy)
    ld d, FWK_ENTITY_RENDER_BACKGROUND+1(iy)
    push iy
    call fwk_sprite_capture
    pop iy
    jr c, _fwk_er_draw_exit
    call _fwk_er_draw_entity
    jr c, _fwk_er_draw_exit
    set 2, FWK_ENTITY_RENDER_FLAGS(iy)
    call _fwk_er_store_previous
_fwk_er_draw_clear:
    res 1, FWK_ENTITY_RENDER_FLAGS(iy)
    ld a, (_fwk_er_index)
    inc a
    ld (_fwk_er_index), a
    jr _fwk_er_draw_loop
_fwk_er_draw_done:
    ld ix, (_fwk_er_list)
    xor a
    ld FWK_ENTITY_RENDER_AFFECTED_COUNT(ix), a
    ld FWK_ENTITY_RENDER_STATE(ix), a
    or a
    jr _fwk_er_draw_exit
_fwk_er_draw_invalid:
    scf
_fwk_er_draw_exit:
    pop iy
    pop ix
    ret

;; Validate list storage, entity flags/spans and duplicate non-null pointers.
_fwk_er_validate_list:
    ld a, FWK_ENTITY_RENDER_COUNT(ix)
    ld b, a
    ld a, FWK_ENTITY_RENDER_WORK_CAPACITY(ix)
    cp b
    jp c, _fwk_er_invalid
    ld l, b
    ld h, #0
    add hl, hl
    ld e, FWK_ENTITY_RENDER_ENTITIES(ix)
    ld d, FWK_ENTITY_RENDER_ENTITIES+1(ix)
    add hl, de
    jp c, _fwk_er_invalid
    ld l, a
    ld h, #0
    add hl, hl
    add hl, hl
    ld e, FWK_ENTITY_RENDER_WORK(ix)
    ld d, FWK_ENTITY_RENDER_WORK+1(ix)
    add hl, de
    jp c, _fwk_er_invalid
    xor a
    ld (_fwk_er_index), a
_fwk_er_validate_entities:
    call _fwk_er_next_entity
    jr z, _fwk_er_validate_duplicates
    jr c, _fwk_er_validate_entities
    push hl
    pop iy
    ld de, #FWK_ENTITY_RENDER_PREFIX_SIZE
    add hl, de
    jp c, _fwk_er_invalid
    ld a, FWK_ENTITY_RENDER_FLAGS(iy)
    and #0xE0
    jp nz, _fwk_er_invalid
.if FWK_TRANSPARENCY_ENABLED
.else
    bit 3, FWK_ENTITY_RENDER_FLAGS(iy)
    jp nz, _fwk_er_invalid
.endif
    ld a, FWK_ENTITY_RENDER_SOURCE_PEN(iy)
    and #0xF0
    jp nz, _fwk_er_invalid
    ld a, FWK_ENTITY_RENDER_REPLACEMENT_PEN(iy)
    and #0xF0
    jp nz, _fwk_er_invalid
    jr _fwk_er_validate_entities

_fwk_er_validate_duplicates:
    xor a
    ld (_fwk_er_outer), a
_fwk_er_dup_outer:
    ld a, (_fwk_er_outer)
    call _fwk_er_entity_at
    jr z, _fwk_er_validate_ok
    jr c, _fwk_er_dup_next_outer
    ld (_fwk_er_a), hl
    ld a, (_fwk_er_outer)
    inc a
    ld (_fwk_er_inner), a
_fwk_er_dup_inner:
    ld a, (_fwk_er_inner)
    call _fwk_er_entity_at
    jr z, _fwk_er_dup_next_outer
    jr c, _fwk_er_dup_next_inner
    ld de, (_fwk_er_a)
    or a
    sbc hl, de
    jp z, _fwk_er_invalid
_fwk_er_dup_next_inner:
    ld a, (_fwk_er_inner)
    inc a
    ld (_fwk_er_inner), a
    jr _fwk_er_dup_inner
_fwk_er_dup_next_outer:
    ld a, (_fwk_er_outer)
    inc a
    ld (_fwk_er_outer), a
    jr _fwk_er_dup_outer
_fwk_er_validate_ok:
    or a
    ret

;; Validate mutable render fields. Structural pointer and buffer checks are
;; performed by init/revalidate; flags and pens may legitimately change while
;; the list is running, so dirty entities are checked again every frame.
_fwk_er_validate_runtime_fields:
    ld a, FWK_ENTITY_RENDER_FLAGS(iy)
    and #0xE0
    jr nz, _fwk_er_runtime_fields_invalid
.if FWK_TRANSPARENCY_ENABLED
.else
    bit 3, FWK_ENTITY_RENDER_FLAGS(iy)
    jr nz, _fwk_er_runtime_fields_invalid
.endif
    ld a, FWK_ENTITY_RENDER_SOURCE_PEN(iy)
    and #0xF0
    jr nz, _fwk_er_runtime_fields_invalid
    ld a, FWK_ENTITY_RENDER_REPLACEMENT_PEN(iy)
    and #0xF0
    jr nz, _fwk_er_runtime_fields_invalid
    or a
    ret
_fwk_er_runtime_fields_invalid:
    scf
    ret

;; Iterate pointer array. Z=end; C=null slot; otherwise HL=entity and NZ/NC.
_fwk_er_next_entity:
    ld ix, (_fwk_er_list)
    ld a, (_fwk_er_index)
    cp FWK_ENTITY_RENDER_COUNT(ix)
    ret z
    ld l, a
    ld h, #0
    add hl, hl
    ld e, FWK_ENTITY_RENDER_ENTITIES(ix)
    ld d, FWK_ENTITY_RENDER_ENTITIES+1(ix)
    add hl, de
    ld e, (hl)
    inc hl
    ld d, (hl)
    ld a, (_fwk_er_index)
    inc a
    ld (_fwk_er_index), a
    ld a, d
    or e
    jr z, _fwk_er_null
    ex de, hl
    ld a, #1
    or a
    ret
_fwk_er_null:
    scf
    ld a, #1
    or a
    ret

;; Build stable insertion-sorted work list from DIRTY entities.
;; A=0 current sort, non-zero previous sort.
_fwk_er_build_work:
    push af
    ld ix, (_fwk_er_list)
    xor a
    ld FWK_ENTITY_RENDER_AFFECTED_COUNT(ix), a
    ld (_fwk_er_index), a
_fwk_er_build_loop:
    call _fwk_er_next_entity
    jr z, _fwk_er_build_ok
    jr c, _fwk_er_build_loop
    push hl
    pop iy
    bit 1, FWK_ENTITY_RENDER_FLAGS(iy)
    jr z, _fwk_er_build_loop
    ld (_fwk_er_entity), hl
    pop af
    push af
    or a
    jr z, _fwk_er_build_current
    ld l, FWK_ENTITY_RENDER_PREVIOUS_SORT_Y(iy)
    ld h, FWK_ENTITY_RENDER_PREVIOUS_SORT_Y+1(iy)
    jr _fwk_er_build_key
_fwk_er_build_current:
    ld l, FWK_ENTITY_RENDER_SORT_Y(iy)
    ld h, FWK_ENTITY_RENDER_SORT_Y+1(iy)
_fwk_er_build_key:
    ld (_fwk_er_key), hl
    call _fwk_er_work_insert
    jr c, _fwk_er_build_fail
    jr _fwk_er_build_loop
_fwk_er_build_ok:
    pop af
    or a
    ret
_fwk_er_build_fail:
    pop af
    scf
    ret

_fwk_er_work_insert:
    ld ix, (_fwk_er_list)
    ld a, FWK_ENTITY_RENDER_AFFECTED_COUNT(ix)
    cp FWK_ENTITY_RENDER_WORK_CAPACITY(ix)
    jp nc, _fwk_er_invalid
    ld (_fwk_er_slot), a
_fwk_er_find_slot:
    ld a, (_fwk_er_slot)
    or a
    jr z, _fwk_er_insert_shift_done
    dec a
    call _fwk_er_work_ptr
    inc hl
    inc hl
    ld e, (hl)
    inc hl
    ld d, (hl)
    ld hl, (_fwk_er_key)
    ;; signed key < previous key: compare biased high bytes, then low.
    ld a, h
    xor #0x80
    ld b, a
    ld a, d
    xor #0x80
    cp b
    jr c, _fwk_er_insert_shift_done
    jr nz, _fwk_er_insert_shift
    ld a, e
    cp l
    jr c, _fwk_er_insert_shift_done
    jr z, _fwk_er_insert_shift_done
_fwk_er_insert_shift:
    ld a, (_fwk_er_slot)
    dec a
    call _fwk_er_work_ptr
    push hl
    ld de, #FWK_ENTITY_RENDER_WORK_SIZE
    add hl, de
    ex de, hl
    pop hl
    ld bc, #FWK_ENTITY_RENDER_WORK_SIZE
    ldir
    ld a, (_fwk_er_slot)
    dec a
    ld (_fwk_er_slot), a
    jr _fwk_er_find_slot
_fwk_er_insert_shift_done:
    ld a, (_fwk_er_slot)
    call _fwk_er_work_ptr
    ld de, (_fwk_er_entity)
    ld (hl), e
    inc hl
    ld (hl), d
    inc hl
    ld de, (_fwk_er_key)
    ld (hl), e
    inc hl
    ld (hl), d
    ld ix, (_fwk_er_list)
    inc FWK_ENTITY_RENDER_AFFECTED_COUNT(ix)
    or a
    ret

_fwk_er_work_ptr:
    ld l, a
    ld h, #0
    add hl, hl
    add hl, hl
    ld ix, (_fwk_er_list)
    ld e, FWK_ENTITY_RENDER_WORK(ix)
    ld d, FWK_ENTITY_RENDER_WORK+1(ix)
    add hl, de
    ret

_fwk_er_work_entity:
    ld a, (_fwk_er_index)
    call _fwk_er_work_ptr
    ld e, (hl)
    inc hl
    ld d, (hl)
    ex de, hl
    ret

_fwk_er_previous_descriptor:
    ld l, FWK_ENTITY_RENDER_SPRITE_DATA(iy)
    ld h, FWK_ENTITY_RENDER_SPRITE_DATA+1(iy)
    ld (_fwk_er_sprite), hl
    ld l, FWK_ENTITY_RENDER_PREVIOUS_X(iy)
    ld h, FWK_ENTITY_RENDER_PREVIOUS_X+1(iy)
    ld (_fwk_er_sprite+2), hl
    ld l, FWK_ENTITY_RENDER_PREVIOUS_Y(iy)
    ld h, FWK_ENTITY_RENDER_PREVIOUS_Y+1(iy)
    ld (_fwk_er_sprite+4), hl
    ld a, FWK_ENTITY_RENDER_PREVIOUS_WIDTH(iy)
    ld (_fwk_er_sprite+6), a
    ld a, FWK_ENTITY_RENDER_PREVIOUS_HEIGHT(iy)
    ld (_fwk_er_sprite+7), a
    ret

_fwk_er_store_previous:
    ld l, FWK_ENTITY_RENDER_X(iy)
    ld h, FWK_ENTITY_RENDER_X+1(iy)
    ld FWK_ENTITY_RENDER_PREVIOUS_X(iy), l
    ld FWK_ENTITY_RENDER_PREVIOUS_X+1(iy), h
    ld l, FWK_ENTITY_RENDER_Y(iy)
    ld h, FWK_ENTITY_RENDER_Y+1(iy)
    ld FWK_ENTITY_RENDER_PREVIOUS_Y(iy), l
    ld FWK_ENTITY_RENDER_PREVIOUS_Y+1(iy), h
    ld a, FWK_ENTITY_RENDER_WIDTH(iy)
    ld FWK_ENTITY_RENDER_PREVIOUS_WIDTH(iy), a
    ld a, FWK_ENTITY_RENDER_HEIGHT(iy)
    ld FWK_ENTITY_RENDER_PREVIOUS_HEIGHT(iy), a
    ld l, FWK_ENTITY_RENDER_SORT_Y(iy)
    ld h, FWK_ENTITY_RENDER_SORT_Y+1(iy)
    ld FWK_ENTITY_RENDER_PREVIOUS_SORT_Y(iy), l
    ld FWK_ENTITY_RENDER_PREVIOUS_SORT_Y+1(iy), h
    ret

_fwk_er_draw_entity:
    ld a, FWK_ENTITY_RENDER_FLAGS(iy)
    bit 4, a
    jr z, _fwk_er_draw_no_recolor
    ld d, FWK_ENTITY_RENDER_SOURCE_PEN(iy)
    ld e, FWK_ENTITY_RENDER_REPLACEMENT_PEN(iy)
    bit 3, a
.if FWK_TRANSPARENCY_ENABLED
    jp nz, fwk_sprite_draw_masked_recolor
.else
    jp nz, _fwk_er_invalid
.endif
    jp fwk_sprite_draw_recolor
_fwk_er_draw_no_recolor:
    bit 3, a
.if FWK_TRANSPARENCY_ENABLED
    jp nz, fwk_sprite_draw_masked
.else
    jp nz, _fwk_er_invalid
.endif
    jp fwk_sprite_draw

;; Return B=visible width, C=visible height using sprite.s clipping rules.
_fwk_er_visible_area:
    ld a, FWK_ENTITY_RENDER_WIDTH(iy)
    or a
    jp z, _fwk_er_invalid
    ld b, a
    ld a, FWK_ENTITY_RENDER_HEIGHT(iy)
    or a
    jp z, _fwk_er_invalid
    ld c, a
    ld l, FWK_ENTITY_RENDER_X(iy)
    ld h, FWK_ENTITY_RENDER_X+1(iy)
    bit 7, h
    jr nz, _fwk_er_area_x_negative
    ld a, h
    or a
    jr nz, _fwk_er_area_empty
    ld a, (fwk_video_width_bytes)
    cp l
    jr c, _fwk_er_area_empty
    jr z, _fwk_er_area_empty
    sub l
    cp b
    jr nc, _fwk_er_area_y
    ld b, a
    jr _fwk_er_area_y
_fwk_er_area_x_negative:
    ld a, h
    cp #0xFF
    jr nz, _fwk_er_area_empty
    ld a, l
    or a
    jr z, _fwk_er_area_empty
    cpl
    inc a
    cp b
    jr nc, _fwk_er_area_empty
    ld l, a
    ld a, b
    sub l
    ld b, a
_fwk_er_area_y:
    ld l, FWK_ENTITY_RENDER_Y(iy)
    ld h, FWK_ENTITY_RENDER_Y+1(iy)
    bit 7, h
    jr nz, _fwk_er_area_y_negative
    ld de, (fwk_video_height)
    push hl
    or a
    sbc hl, de
    pop hl
    jr nc, _fwk_er_area_empty
    ex de, hl
    or a
    sbc hl, de                    ; remaining screen height
    ld a, h
    or a
    jr nz, _fwk_er_area_ok
    ld a, l
    cp c
    jr nc, _fwk_er_area_ok
    ld c, a
    jr _fwk_er_area_ok
_fwk_er_area_y_negative:
    ld a, h
    cp #0xFF
    jr nz, _fwk_er_area_empty
    ld a, l
    or a
    jr z, _fwk_er_area_empty
    cpl
    inc a
    cp c
    jr nc, _fwk_er_area_empty
    ld l, a
    ld a, c
    sub l
    ld c, a
_fwk_er_area_ok:
    or a
    ret
_fwk_er_area_empty:
    ld b, #0
    ld c, #0
    or a
    ret

_fwk_er_capacity_ok:
    ld h, #0
    ld l, #0
    ld a, c
_fwk_er_capacity_loop:
    or a
    jr z, _fwk_er_capacity_compare
    ld e, b
    ld d, #0
    add hl, de
    jp c, _fwk_er_invalid
    dec a
    jr _fwk_er_capacity_loop
_fwk_er_capacity_compare:
    ld e, FWK_ENTITY_RENDER_BACKGROUND_CAP(iy)
    ld d, FWK_ENTITY_RENDER_BACKGROUND_CAP+1(iy)
    ex de, hl
    or a
    sbc hl, de
    jp c, _fwk_er_invalid
    or a
    ret

;; Validate every affected restore/capture before the first VRAM write.
_fwk_er_preflight:
    xor a
    ld (_fwk_er_inner), a
_fwk_er_preflight_loop:
    ld a, (_fwk_er_inner)
    call _fwk_er_entity_at
    jr z, _fwk_er_preflight_ok
    jr c, _fwk_er_preflight_next
    push hl
    pop iy
    bit 1, FWK_ENTITY_RENDER_FLAGS(iy)
    jr z, _fwk_er_preflight_next
    bit 2, FWK_ENTITY_RENDER_FLAGS(iy)
    jr z, _fwk_er_preflight_current
    call _fwk_er_previous_descriptor
    push iy
    ld iy, #_fwk_er_sprite
    call _fwk_er_sprite_span_ok
    jr c, _fwk_er_preflight_previous_bad
    call _fwk_er_visible_area
_fwk_er_preflight_previous_bad:
    pop iy
    ret c
    ld a, b
    or c
    jr z, _fwk_er_preflight_current
    call _fwk_er_capacity_ok
    ret c
_fwk_er_preflight_current:
    bit 0, FWK_ENTITY_RENDER_FLAGS(iy)
    jr z, _fwk_er_preflight_next
    call _fwk_er_sprite_span_ok
    ret c
    call _fwk_er_visible_area
    ret c
    ld a, b
    or c
    jr z, _fwk_er_preflight_next
    call _fwk_er_capacity_ok
    ret c
_fwk_er_preflight_next:
    ld a, (_fwk_er_inner)
    inc a
    ld (_fwk_er_inner), a
    jr _fwk_er_preflight_loop
_fwk_er_preflight_ok:
    or a
    ret

;; Reject wrapping and overlapping declared ranges for simultaneous captures.
_fwk_er_validate_active_buffers:
    xor a
    ld (_fwk_er_outer), a
_fwk_er_buffers_outer:
    ld a, (_fwk_er_outer)
    call _fwk_er_entity_at
    jp z, _fwk_er_buffers_ok
    jp c, _fwk_er_buffers_next_outer
    push hl
    pop iy
    call _fwk_er_buffer_active
    jp nc, _fwk_er_buffers_next_outer
    ld l, FWK_ENTITY_RENDER_BACKGROUND(iy)
    ld h, FWK_ENTITY_RENDER_BACKGROUND+1(iy)
    ld (_fwk_er_buf_start), hl
    ld e, FWK_ENTITY_RENDER_BACKGROUND_CAP(iy)
    ld d, FWK_ENTITY_RENDER_BACKGROUND_CAP+1(iy)
    add hl, de
    jr c, _fwk_er_buffers_bad
    ld (_fwk_er_buf_end), hl
    ld a, (_fwk_er_outer)
    inc a
    ld (_fwk_er_inner), a
_fwk_er_buffers_inner:
    ld a, (_fwk_er_inner)
    call _fwk_er_entity_at
    jp z, _fwk_er_buffers_next_outer
    jp c, _fwk_er_buffers_next_inner
    push hl
    pop iy
    call _fwk_er_buffer_active
    jp nc, _fwk_er_buffers_next_inner
    ld l, FWK_ENTITY_RENDER_BACKGROUND(iy)
    ld h, FWK_ENTITY_RENDER_BACKGROUND+1(iy)
    ld e, FWK_ENTITY_RENDER_BACKGROUND_CAP(iy)
    ld d, FWK_ENTITY_RENDER_BACKGROUND_CAP+1(iy)
    push hl
    add hl, de                    ; B end
    jr c, _fwk_er_buffers_bad_pop
    ld de, (_fwk_er_buf_start)    ; A start < B end
    or a
    sbc hl, de
    pop hl                        ; B start
    jp c, _fwk_er_buffers_next_inner
    jp z, _fwk_er_buffers_next_inner
    ld de, (_fwk_er_buf_end)      ; B start < A end
    or a
    sbc hl, de
    jp nc, _fwk_er_buffers_next_inner
    jr _fwk_er_buffers_bad
_fwk_er_buffers_bad_pop:
    pop hl
_fwk_er_buffers_bad:
    scf
    ret

;; Bit 7 is a private temporary marker used to make closure validation atomic.
_fwk_er_tag_original_dirty:
    xor a
    ld (_fwk_er_inner), a
_fwk_er_tag_loop:
    ld a, (_fwk_er_inner)
    call _fwk_er_entity_at
    ret z
    jr c, _fwk_er_tag_next
    push hl
    pop iy
    bit 1, FWK_ENTITY_RENDER_FLAGS(iy)
    jr z, _fwk_er_tag_next
    ;; Validate before setting the private bit-7 closure marker.
    call _fwk_er_validate_runtime_fields
    ret c
    set 7, FWK_ENTITY_RENDER_FLAGS(iy)
_fwk_er_tag_next:
    ld a, (_fwk_er_inner)
    inc a
    ld (_fwk_er_inner), a
    jr _fwk_er_tag_loop

_fwk_er_commit_dirty_tags:
    ld a, #1
    jr _fwk_er_finish_tags
_fwk_er_rollback_dirty_tags:
    xor a
_fwk_er_finish_tags:
    ld (_fwk_er_changed), a
    xor a
    ld (_fwk_er_inner), a
_fwk_er_finish_tag_loop:
    ld a, (_fwk_er_inner)
    call _fwk_er_entity_at
    ret z
    jr c, _fwk_er_finish_tag_next
    push hl
    pop iy
    bit 7, FWK_ENTITY_RENDER_FLAGS(iy)
    jr nz, _fwk_er_finish_was_original
    ld a, (_fwk_er_changed)
    or a
    jr nz, _fwk_er_finish_tag_next
    res 1, FWK_ENTITY_RENDER_FLAGS(iy)
    jr _fwk_er_finish_tag_next
_fwk_er_finish_was_original:
    res 7, FWK_ENTITY_RENDER_FLAGS(iy)
_fwk_er_finish_tag_next:
    ld a, (_fwk_er_inner)
    inc a
    ld (_fwk_er_inner), a
    jr _fwk_er_finish_tag_loop
_fwk_er_buffers_next_inner:
    ld a, (_fwk_er_inner)
    inc a
    ld (_fwk_er_inner), a
    jp _fwk_er_buffers_inner
_fwk_er_buffers_next_outer:
    ld a, (_fwk_er_outer)
    inc a
    ld (_fwk_er_outer), a
    jp _fwk_er_buffers_outer
_fwk_er_buffers_ok:
    or a
    ret

;; Carry when the entity currently owns or will capture a non-empty buffer.
_fwk_er_buffer_active:
    ld a, (_fwk_er_changed)
    or a
    jr nz, _fwk_er_buffer_yes
    bit 2, FWK_ENTITY_RENDER_FLAGS(iy)
    jr nz, _fwk_er_buffer_yes
    bit 1, FWK_ENTITY_RENDER_FLAGS(iy)
    jr z, _fwk_er_buffer_no
    bit 0, FWK_ENTITY_RENDER_FLAGS(iy)
    jr z, _fwk_er_buffer_no
    call _fwk_er_visible_area
    jr c, _fwk_er_buffer_no
    ld a, b
    or c
    jr z, _fwk_er_buffer_no
_fwk_er_buffer_yes:
    scf
    ret
_fwk_er_buffer_no:
    or a
    ret

_fwk_er_sprite_span_ok:
    ld a, FWK_ENTITY_RENDER_WIDTH(iy)
    or a
    jr z, _fwk_er_span_bad
    ld e, a
    ld d, #0
    ld a, FWK_ENTITY_RENDER_HEIGHT(iy)
    or a
    jr z, _fwk_er_span_bad
    ld b, a
    ld hl, #0
_fwk_er_span_loop:
    add hl, de
    jr c, _fwk_er_span_bad
    djnz _fwk_er_span_loop
    ld e, FWK_ENTITY_RENDER_SPRITE_DATA(iy)
    ld d, FWK_ENTITY_RENDER_SPRITE_DATA+1(iy)
    add hl, de
    jr c, _fwk_er_span_bad
    or a
    ret
_fwk_er_span_bad:
    scf
    ret

_fwk_er_propagate_dirty:
    ld a, #1
    ld (_fwk_er_changed), a
_fwk_er_closure_pass:
    xor a
    ld (_fwk_er_changed), a
    ld (_fwk_er_outer), a
_fwk_er_closure_outer:
    ld a, (_fwk_er_outer)
    call _fwk_er_entity_at
    jr z, _fwk_er_closure_done_outer
    jr c, _fwk_er_closure_next_outer
    push hl
    pop iy
    bit 1, FWK_ENTITY_RENDER_FLAGS(iy)
    jr z, _fwk_er_closure_next_outer
    ld (_fwk_er_a), hl
    xor a
    ld (_fwk_er_inner), a
_fwk_er_closure_inner:
    ld a, (_fwk_er_inner)
    call _fwk_er_entity_at
    jr z, _fwk_er_closure_next_outer
    jr c, _fwk_er_closure_next_inner
    ld (_fwk_er_b), hl
    ld de, (_fwk_er_a)
    or a
    sbc hl, de
    jr z, _fwk_er_closure_next_inner
    push de
    pop iy
    ld hl, (_fwk_er_b)
    push hl
    pop ix
    bit 1, FWK_ENTITY_RENDER_FLAGS(ix)
    jr nz, _fwk_er_closure_next_inner
    ld a, FWK_ENTITY_RENDER_FLAGS(ix)
    and #(FWK_ENTITY_RENDER_VISIBLE | FWK_ENTITY_RENDER_HAS_BACKGROUND)
    jr z, _fwk_er_closure_next_inner
    call _fwk_er_entities_overlap
    jr nc, _fwk_er_closure_next_inner
    ld ix, (_fwk_er_b)
    set 1, FWK_ENTITY_RENDER_FLAGS(ix)
    ld a, #1
    ld (_fwk_er_changed), a
_fwk_er_closure_next_inner:
    ld a, (_fwk_er_inner)
    inc a
    ld (_fwk_er_inner), a
    jr _fwk_er_closure_inner
_fwk_er_closure_next_outer:
    ld a, (_fwk_er_outer)
    inc a
    ld (_fwk_er_outer), a
    jr _fwk_er_closure_outer
_fwk_er_closure_done_outer:
    ld a, (_fwk_er_changed)
    or a
    jr nz, _fwk_er_closure_pass
    or a
    ret

_fwk_er_mark_external:
    xor a
    ld (_fwk_er_inner), a
_fwk_er_mark_loop:
    ld a, (_fwk_er_inner)
    call _fwk_er_entity_at
    jr z, _fwk_er_mark_done
    jr c, _fwk_er_mark_next
    ld (_fwk_er_b), hl
    push hl
    pop ix
    ld a, FWK_ENTITY_RENDER_FLAGS(ix)
    and #(FWK_ENTITY_RENDER_VISIBLE | FWK_ENTITY_RENDER_HAS_BACKGROUND)
    jr z, _fwk_er_mark_next
    call _fwk_er_external_overlaps_entity
    jr nc, _fwk_er_mark_next
    ld ix, (_fwk_er_b)
    set 1, FWK_ENTITY_RENDER_FLAGS(ix)
_fwk_er_mark_next:
    ld a, (_fwk_er_inner)
    inc a
    ld (_fwk_er_inner), a
    jr _fwk_er_mark_loop
_fwk_er_mark_done:
    or a
    ret

;; A=index -> HL=entity, Z=end, C=null.
_fwk_er_entity_at:
    ld ix, (_fwk_er_list)
    cp FWK_ENTITY_RENDER_COUNT(ix)
    ret z
    ld l, a
    ld h, #0
    add hl, hl
    ld e, FWK_ENTITY_RENDER_ENTITIES(ix)
    ld d, FWK_ENTITY_RENDER_ENTITIES+1(ix)
    add hl, de
    ld e, (hl)
    inc hl
    ld d, (hl)
    ld a, d
    or e
    jr z, _fwk_er_entity_at_null
    ex de, hl
    ld a, #1
    or a
    ret
_fwk_er_entity_at_null:
    scf
    ld a, #1
    or a
    ret

;; Carry if any previous/current rectangle of A overlaps any occupied B rect.
_fwk_er_entities_overlap:
    ;; IY=A, IX=B.
    bit 2, FWK_ENTITY_RENDER_FLAGS(iy)
    jr z, _fwk_er_overlap_a_current
    push ix
    push iy
    pop ix
    ld hl, #_fwk_er_rect_a
    ld a, #1
    call _fwk_er_rect_from_entity
    pop ix
    call _fwk_er_rect_a_against_b
    ret c
_fwk_er_overlap_a_current:
    bit 0, FWK_ENTITY_RENDER_FLAGS(iy)
    jr z, _fwk_er_no_overlap
    push ix
    push iy
    pop ix
    ld hl, #_fwk_er_rect_a
    xor a
    call _fwk_er_rect_from_entity
    pop ix
    jp _fwk_er_rect_a_against_b

_fwk_er_external_overlaps_entity:
    ld ix, (_fwk_er_b)
    jp _fwk_er_rect_a_against_b

;; IX=B; rect A already populated. Carry on overlap.
_fwk_er_rect_a_against_b:
    bit 2, FWK_ENTITY_RENDER_FLAGS(ix)
    jr z, _fwk_er_overlap_b_current
    push ix
    ld hl, #_fwk_er_rect_b
    ld a, #1
    call _fwk_er_rect_from_entity
    pop ix
    call _fwk_er_rects_overlap
    ret c
_fwk_er_overlap_b_current:
    bit 0, FWK_ENTITY_RENDER_FLAGS(ix)
    jr z, _fwk_er_no_overlap
    push ix
    ld hl, #_fwk_er_rect_b
    xor a
    call _fwk_er_rect_from_entity
    pop ix
    jp _fwk_er_rects_overlap
_fwk_er_no_overlap:
    or a
    ret

;; IX=entity, HL=destination, A=0 current/nonzero previous.
_fwk_er_rect_from_entity:
    push hl
    or a
    jr z, _fwk_er_rect_current
    ld e, FWK_ENTITY_RENDER_PREVIOUS_X(ix)
    ld d, FWK_ENTITY_RENDER_PREVIOUS_X+1(ix)
    ld b, FWK_ENTITY_RENDER_PREVIOUS_WIDTH(ix)
    ld l, FWK_ENTITY_RENDER_PREVIOUS_Y(ix)
    ld h, FWK_ENTITY_RENDER_PREVIOUS_Y+1(ix)
    ld c, FWK_ENTITY_RENDER_PREVIOUS_HEIGHT(ix)
    jr _fwk_er_rect_fields
_fwk_er_rect_current:
    ld e, FWK_ENTITY_RENDER_X(ix)
    ld d, FWK_ENTITY_RENDER_X+1(ix)
    ld b, FWK_ENTITY_RENDER_WIDTH(ix)
    ld l, FWK_ENTITY_RENDER_Y(ix)
    ld h, FWK_ENTITY_RENDER_Y+1(ix)
    ld c, FWK_ENTITY_RENDER_HEIGHT(ix)
_fwk_er_rect_fields:
    ex (sp), hl                  ; stack=y, HL=destination
    ld (hl), e                  ; x1
    inc hl
    ld (hl), d
    inc hl
    ld a, e
    add b
    ld (hl), a                  ; x2
    inc hl
    ld a, d
    adc #0
    ld (hl), a
    inc hl
    pop de                      ; y
    ld (hl), e                  ; y1
    inc hl
    ld (hl), d
    inc hl
    ld a, e
    add c
    ld (hl), a                  ; y2
    inc hl
    ld a, d
    adc #0
    ld (hl), a
    ret

;; HL points at external x,y,width,height.
_fwk_er_rect_from_external:
    ld e, (hl)
    inc hl
    ld d, (hl)
    inc hl
    push de                     ; x
    ld e, (hl)
    inc hl
    ld d, (hl)
    inc hl
    ld b, (hl)
    inc hl
    ld c, (hl)
    ld hl, #_fwk_er_rect_a
    pop ix
    ld__a_ixl
    ld (hl), a
    inc hl
    ld__a_ixh
    ld (hl), a
    inc hl
    ld__a_ixl
    add b
    ld (hl), a
    inc hl
    ld__a_ixh
    adc #0
    ld (hl), a
    inc hl
    ld (hl), e
    inc hl
    ld (hl), d
    inc hl
    ld a, e
    add c
    ld (hl), a
    inc hl
    ld a, d
    adc #0
    ld (hl), a
    ret

;; Carry iff rect A and B overlap on both signed axes; touching edges do not.
_fwk_er_rects_overlap:
    ld hl, (_fwk_er_rect_a)       ; ax1 < bx2
    ld de, (_fwk_er_rect_b+2)
    call _fwk_er_signed_lt
    ret nc
    ld hl, (_fwk_er_rect_b)       ; bx1 < ax2
    ld de, (_fwk_er_rect_a+2)
    call _fwk_er_signed_lt
    ret nc
    ld hl, (_fwk_er_rect_a+4)     ; ay1 < by2
    ld de, (_fwk_er_rect_b+6)
    call _fwk_er_signed_lt
    ret nc
    ld hl, (_fwk_er_rect_b+4)     ; by1 < ay2
    ld de, (_fwk_er_rect_a+6)
    jp _fwk_er_signed_lt

;; Carry iff signed HL < signed DE.
_fwk_er_signed_lt:
    ld a, h
    xor #0x80
    ld b, a
    ld a, d
    xor #0x80
    cp b
    jr c, _fwk_er_lt_false
    jr nz, _fwk_er_lt_true
    ld a, l
    cp e
    jr c, _fwk_er_lt_true
_fwk_er_lt_false:
    or a
    ret
_fwk_er_lt_true:
    scf
    ret

_fwk_er_invalid:
    scf
    ret
