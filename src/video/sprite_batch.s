;; Stable ordered render passes over consumer-owned sprite descriptors/buffers.
.module fwk_sprite_batch
.include "video/sprite_batch.inc"

.globl fwk_sprite_capture, fwk_sprite_draw, fwk_sprite_restore

.area _DATA
_fwk_sb_batch:       .dw 0
_fwk_sb_sprite:      .dw 0
_fwk_sb_buffer:      .dw 0
_fwk_sb_key:         .db 0
_fwk_sb_index:       .db 0
_fwk_sb_slot:        .db 0

.area _CODE

;; fwk_sprite_batch_init
;; In: IX=4-byte batch descriptor.
;; Out: count=0 and carry clear; carry set for zero capacity or entries span
;;      wrapping 16-bit address space.
;; Modified: AF,BC,DE,HL. IX/IY preserved. Not reentrant with other batch calls.
fwk_sprite_batch_init::
    call _fwk_sb_validate_storage
    ret c
    xor a
    ld FWK_SPRITE_BATCH_COUNT(ix), a
    ret

;; fwk_sprite_batch_add
;; In: IX=batch, HL=sprite descriptor, DE=background buffer, A=sort key.
;; Out: stable ascending insertion; carry set if batch invalid/full.
;; Modified: AF,BC,DE,HL. IX/IY preserved. Uses internal scratch.
fwk_sprite_batch_add::
    ld (_fwk_sb_sprite), hl
    ld (_fwk_sb_buffer), de
    ld (_fwk_sb_key), a
    call _fwk_sb_validate
    ret c
    ld a, FWK_SPRITE_BATCH_COUNT(ix)
    cp FWK_SPRITE_BATCH_CAPACITY(ix)
    jp nc, _fwk_sb_invalid

    xor a
    ld (_fwk_sb_slot), a
_fwk_sb_find_slot:
    ld a, (_fwk_sb_slot)
    ld b, a
    ld a, FWK_SPRITE_BATCH_COUNT(ix)
    cp b
    jr z, _fwk_sb_shift
    ld a, b
    call _fwk_sb_entry_ptr
    ld de, #FWK_SPRITE_BATCH_ENTRY_KEY
    add hl, de
    ld a, (_fwk_sb_key)
    cp (hl)
    jr c, _fwk_sb_shift
    ld a, (_fwk_sb_slot)
    inc a
    ld (_fwk_sb_slot), a
    jr _fwk_sb_find_slot

    ;; Shift complete entries one position right, from tail to insertion slot.
_fwk_sb_shift:
    ld a, FWK_SPRITE_BATCH_COUNT(ix)
    ld (_fwk_sb_index), a
_fwk_sb_shift_loop:
    ld a, (_fwk_sb_index)
    ld b, a
    ld a, (_fwk_sb_slot)
    cp b
    jr z, _fwk_sb_write_candidate
    ld a, b
    dec a
    call _fwk_sb_entry_ptr
    push hl
    ld de, #FWK_SPRITE_BATCH_ENTRY_SIZE
    add hl, de
    ex de, hl
    pop hl
    ld bc, #FWK_SPRITE_BATCH_ENTRY_SIZE
    ldir
    ld a, (_fwk_sb_index)
    dec a
    ld (_fwk_sb_index), a
    jr _fwk_sb_shift_loop

_fwk_sb_write_candidate:
    ld a, (_fwk_sb_slot)
    call _fwk_sb_entry_ptr
    ld de, (_fwk_sb_sprite)
    ld (hl), e
    inc hl
    ld (hl), d
    inc hl
    ld de, (_fwk_sb_buffer)
    ld (hl), e
    inc hl
    ld (hl), d
    inc hl
    ld a, (_fwk_sb_key)
    ld (hl), a
    inc hl
    xor a
    ld (hl), a
    ld a, FWK_SPRITE_BATCH_COUNT(ix)
    inc a
    ld FWK_SPRITE_BATCH_COUNT(ix), a
    or a
    ret

;; fwk_sprite_batch_restore
;; In: IX=batch.
;; Out: captured entries restored in reverse order and flags cleared. Carry set
;;      for invalid batch or the first failing sprite; prior restores remain done.
;; Modified: AF,BC,DE,HL,IX,IY. Restores IX=batch before return. Not reentrant.
fwk_sprite_batch_restore::
    push ix
    ld (_fwk_sb_batch), ix
    call _fwk_sb_validate
    jr c, _fwk_sb_restore_exit
    ld a, FWK_SPRITE_BATCH_COUNT(ix)
    or a
    jr z, _fwk_sb_restore_ok
    dec a
    ld (_fwk_sb_index), a
_fwk_sb_restore_loop:
    call _fwk_sb_current_entry
    ld de, #FWK_SPRITE_BATCH_ENTRY_FLAGS
    add hl, de
    bit 0, (hl)
    jr z, _fwk_sb_restore_next
    call _fwk_sb_current_entry
    ld e, (hl)
    inc hl
    ld d, (hl)
    push de
    pop ix
    inc hl
    ld e, (hl)
    inc hl
    ld d, (hl)
    ex de, hl
    call fwk_sprite_restore
    jr c, _fwk_sb_restore_exit
    call _fwk_sb_current_entry
    ld de, #FWK_SPRITE_BATCH_ENTRY_FLAGS
    add hl, de
    res 0, (hl)
_fwk_sb_restore_next:
    ld a, (_fwk_sb_index)
    or a
    jr z, _fwk_sb_restore_ok
    dec a
    ld (_fwk_sb_index), a
    jr _fwk_sb_restore_loop
_fwk_sb_restore_ok:
    or a
_fwk_sb_restore_exit:
    pop ix
    ret

;; fwk_sprite_batch_draw
;; In: IX=batch.
;; Out: requires every captured flag clear, then captures and draws entries in
;;      stable ascending key order. Carry marks invalid/state/sprite failure;
;;      earlier entries may already be drawn and flagged on a sprite failure.
;; Modified: AF,BC,DE,HL,IX,IY. Restores IX=batch before return. Not reentrant.
fwk_sprite_batch_draw::
    push ix
    ld (_fwk_sb_batch), ix
    call _fwk_sb_validate
    jr c, _fwk_sb_draw_exit
    xor a
    ld (_fwk_sb_index), a

    ;; Reject double capture before the first screen or buffer write.
_fwk_sb_draw_preflight:
    ld ix, (_fwk_sb_batch)
    ld a, (_fwk_sb_index)
    ld b, a
    ld a, FWK_SPRITE_BATCH_COUNT(ix)
    cp b
    jr z, _fwk_sb_draw_start
    call _fwk_sb_current_entry
    ld de, #FWK_SPRITE_BATCH_ENTRY_FLAGS
    add hl, de
    bit 0, (hl)
    jr nz, _fwk_sb_draw_state_error
    ld a, (_fwk_sb_index)
    inc a
    ld (_fwk_sb_index), a
    jr _fwk_sb_draw_preflight
_fwk_sb_draw_state_error:
    scf
    jr _fwk_sb_draw_exit

_fwk_sb_draw_start:
    xor a
    ld (_fwk_sb_index), a
_fwk_sb_draw_loop:
    ld ix, (_fwk_sb_batch)
    ld a, (_fwk_sb_index)
    ld b, a
    ld a, FWK_SPRITE_BATCH_COUNT(ix)
    cp b
    jr z, _fwk_sb_draw_ok
    call _fwk_sb_current_entry
    ld e, (hl)
    inc hl
    ld d, (hl)
    push de
    pop ix
    inc hl
    ld e, (hl)
    inc hl
    ld d, (hl)
    call fwk_sprite_capture
    jr c, _fwk_sb_draw_exit
    call fwk_sprite_draw
    jr c, _fwk_sb_draw_exit
    call _fwk_sb_current_entry
    ld de, #FWK_SPRITE_BATCH_ENTRY_FLAGS
    add hl, de
    set 0, (hl)
    ld a, (_fwk_sb_index)
    inc a
    ld (_fwk_sb_index), a
    jr _fwk_sb_draw_loop
_fwk_sb_draw_ok:
    or a
_fwk_sb_draw_exit:
    pop ix
    ret

;; Validate storage pointer/capacity span without reading count.
_fwk_sb_validate_storage:
    ld a, FWK_SPRITE_BATCH_CAPACITY(ix)
    or a
    jr z, _fwk_sb_invalid
    ld l, a
    ld h, #0
    ld e, l
    ld d, h
    add hl, hl
    add hl, de
    add hl, hl
    ld e, FWK_SPRITE_BATCH_ENTRIES(ix)
    ld d, FWK_SPRITE_BATCH_ENTRIES+1(ix)
    add hl, de
    jr c, _fwk_sb_invalid
    or a
    ret

;; Validate storage and count <= capacity.
_fwk_sb_validate:
    call _fwk_sb_validate_storage
    ret c
    ld a, FWK_SPRITE_BATCH_CAPACITY(ix)
    cp FWK_SPRITE_BATCH_COUNT(ix)
    jr c, _fwk_sb_invalid
    or a
    ret

_fwk_sb_invalid:
    scf
    ret

;; In: A=index, IX=batch. Out: HL=entry pointer. Modified: AF,DE,HL.
_fwk_sb_entry_ptr:
    ld l, a
    ld h, #0
    ld e, l
    ld d, h
    add hl, hl
    add hl, de
    add hl, hl
    ld e, FWK_SPRITE_BATCH_ENTRIES(ix)
    ld d, FWK_SPRITE_BATCH_ENTRIES+1(ix)
    add hl, de
    ret

;; Out: HL=current entry, using saved batch/index. Modified: AF,DE,HL,IX.
_fwk_sb_current_entry:
    ld ix, (_fwk_sb_batch)
    ld a, (_fwk_sb_index)
    jp _fwk_sb_entry_ptr
