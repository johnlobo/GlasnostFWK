;; Clipped rectangular Mode 0 sprites with caller-owned background buffers.
.module fwk_sprite
.include "video/sprite.inc"

.globl fwk_video_get_ptr, fwk_video_width_bytes, fwk_video_height

.area _DATA
_fwk_sp_source:      .dw 0
_fwk_sp_buffer:      .dw 0
_fwk_sp_dest_y:      .dw 0
_fwk_sp_src_x:       .db 0
_fwk_sp_src_y:       .db 0
_fwk_sp_dest_x:      .db 0
_fwk_sp_width:       .db 0
_fwk_sp_height:      .db 0
_fwk_sp_stride:      .db 0
_fwk_sp_rows:        .db 0

.area _CODE

;; fwk_sprite_draw
;; In: IX=8-byte sprite descriptor.
;; Out: carry set for invalid dimensions/source span; otherwise clear. A sprite
;;      wholly outside the screen succeeds without writing.
;; Modified: AF,BC,DE,HL. IX/IY preserved. Not reentrant (internal scratch).
fwk_sprite_draw::
    call _fwk_sp_clip
    ret c
    ld a, (_fwk_sp_width)
    or a
    ret z
    ld a, (_fwk_sp_height)
    ld (_fwk_sp_rows), a
_fwk_sp_draw_row:
    call _fwk_sp_screen_ptr
    ex de, hl
    ld hl, (_fwk_sp_source)
    ld b, #0
    ld a, (_fwk_sp_width)
    ld c, a
    ldir
    ld hl, (_fwk_sp_source)
    ld a, (_fwk_sp_stride)
    ld e, a
    ld d, #0
    add hl, de
    ld (_fwk_sp_source), hl
    call _fwk_sp_next_row
    jr nz, _fwk_sp_draw_row
    or a
    ret

;; fwk_sprite_capture
;; In: IX=descriptor, DE=buffer of at least width*height bytes.
;; Out: carry as draw; IY=end of used buffer. A clipped sprite consumes only
;;      its visible byte rectangle. The buffer capacity cannot be checked.
;; Modified: AF,BC,DE,HL,IY. IX preserved. Not reentrant.
fwk_sprite_capture::
    ld (_fwk_sp_buffer), de
    call _fwk_sp_clip
    jr c, _fwk_sp_capture_invalid
    ld a, (_fwk_sp_width)
    or a
    jr z, _fwk_sp_buffer_end
    ld a, (_fwk_sp_height)
    ld (_fwk_sp_rows), a
_fwk_sp_capture_row:
    call _fwk_sp_screen_ptr
    ld de, (_fwk_sp_buffer)
    ld b, #0
    ld a, (_fwk_sp_width)
    ld c, a
    ldir
    ld (_fwk_sp_buffer), de
    call _fwk_sp_next_row
    jr nz, _fwk_sp_capture_row
_fwk_sp_buffer_end:
    ld iy, (_fwk_sp_buffer)
    or a
    ret
_fwk_sp_capture_invalid:
    scf
    ret

;; fwk_sprite_restore
;; In: IX=same descriptor geometry used by capture, HL=captured buffer.
;; Out: carry as draw; IY=end of consumed buffer.
;; Modified: AF,BC,DE,HL,IY. IX preserved. Not reentrant.
fwk_sprite_restore::
    ld (_fwk_sp_buffer), hl
    call _fwk_sp_clip
    jr c, _fwk_sp_restore_invalid
    ld a, (_fwk_sp_width)
    or a
    jr z, _fwk_sp_buffer_end
    ld a, (_fwk_sp_height)
    ld (_fwk_sp_rows), a
_fwk_sp_restore_row:
    call _fwk_sp_screen_ptr
    ex de, hl
    ld hl, (_fwk_sp_buffer)
    ld b, #0
    ld a, (_fwk_sp_width)
    ld c, a
    ldir
    ld (_fwk_sp_buffer), hl
    call _fwk_sp_next_row
    jr nz, _fwk_sp_restore_row
    jr _fwk_sp_buffer_end
_fwk_sp_restore_invalid:
    scf
    ret

;; Validate the descriptor and calculate source/destination clipped rectangles.
;; Zero visible width denotes a valid, wholly off-screen sprite.
_fwk_sp_clip:
    xor a
    ld (_fwk_sp_width), a
    ld (_fwk_sp_src_x), a
    ld (_fwk_sp_src_y), a

    ld a, FWK_SPRITE_WIDTH(ix)
    or a
    jp z, _fwk_sp_invalid
    ld (_fwk_sp_stride), a
    ld e, a
    ld d, #0
    ld a, FWK_SPRITE_HEIGHT(ix)
    or a
    jp z, _fwk_sp_invalid
    ld b, a
    ld hl, #0
_fwk_sp_area_loop:
    add hl, de
    jp c, _fwk_sp_invalid
    djnz _fwk_sp_area_loop
    ld e, FWK_SPRITE_DATA(ix)
    ld d, FWK_SPRITE_DATA+1(ix)
    add hl, de
    jp c, _fwk_sp_invalid

    ;; Horizontal clipping. X is a signed 16-bit byte coordinate.
    ld l, FWK_SPRITE_X(ix)
    ld h, FWK_SPRITE_X+1(ix)
    bit 7, h
    jr nz, _fwk_sp_x_negative
    ld a, h
    or a
    jp nz, _fwk_sp_empty
    ld a, (fwk_video_width_bytes)
    cp l
    jp c, _fwk_sp_empty
    jp z, _fwk_sp_empty
    ld a, l
    ld (_fwk_sp_dest_x), a
    ld b, a
    ld a, (fwk_video_width_bytes)
    sub b
    ld b, a
    ld a, FWK_SPRITE_WIDTH(ix)
    cp b
    jr c, _fwk_sp_x_full
    jr z, _fwk_sp_x_full
    ld a, b
_fwk_sp_x_full:
    ld (_fwk_sp_width), a
    jr _fwk_sp_clip_y

_fwk_sp_x_negative:
    ld a, h
    cp #0xFF
    jp nz, _fwk_sp_empty
    ld a, l
    or a
    jp z, _fwk_sp_empty
    cpl
    inc a
    ld b, a
    cp FWK_SPRITE_WIDTH(ix)
    jp nc, _fwk_sp_empty
    ld (_fwk_sp_src_x), a
    xor a
    ld (_fwk_sp_dest_x), a
    ld a, FWK_SPRITE_WIDTH(ix)
    sub b
    ld (_fwk_sp_width), a

    ;; Vertical clipping. Y is a signed 16-bit scanline coordinate.
_fwk_sp_clip_y:
    ld l, FWK_SPRITE_Y(ix)
    ld h, FWK_SPRITE_Y+1(ix)
    bit 7, h
    jr nz, _fwk_sp_y_negative
    ld de, (fwk_video_height)
    push hl
    or a
    sbc hl, de
    pop hl
    jp nc, _fwk_sp_empty
    ld (_fwk_sp_dest_y), hl
    ex de, hl
    or a
    sbc hl, de
    ld a, h
    or a
    jr nz, _fwk_sp_y_full
    ld b, l
    ld a, FWK_SPRITE_HEIGHT(ix)
    cp b
    jr c, _fwk_sp_y_store
    jr z, _fwk_sp_y_store
    ld a, b
    jr _fwk_sp_y_store
_fwk_sp_y_full:
    ld a, FWK_SPRITE_HEIGHT(ix)
_fwk_sp_y_store:
    ld (_fwk_sp_height), a
    jr _fwk_sp_source_ptr

_fwk_sp_y_negative:
    ld a, h
    cp #0xFF
    jp nz, _fwk_sp_empty
    ld a, l
    or a
    jp z, _fwk_sp_empty
    cpl
    inc a
    ld b, a
    cp FWK_SPRITE_HEIGHT(ix)
    jp nc, _fwk_sp_empty
    ld (_fwk_sp_src_y), a
    ld hl, #0
    ld (_fwk_sp_dest_y), hl
    ld a, FWK_SPRITE_HEIGHT(ix)
    sub b
    ld (_fwk_sp_height), a

_fwk_sp_source_ptr:
    ld l, FWK_SPRITE_DATA(ix)
    ld h, FWK_SPRITE_DATA+1(ix)
    ld a, (_fwk_sp_src_y)
    or a
    jr z, _fwk_sp_source_x
    ld b, a
    ld a, (_fwk_sp_stride)
    ld e, a
    ld d, #0
_fwk_sp_source_row:
    add hl, de
    djnz _fwk_sp_source_row
_fwk_sp_source_x:
    ld a, (_fwk_sp_src_x)
    ld e, a
    ld d, #0
    add hl, de
    ld (_fwk_sp_source), hl
    or a
    ret

_fwk_sp_empty:
    xor a
    ld (_fwk_sp_width), a
    ld (_fwk_sp_height), a
    ret

_fwk_sp_invalid:
    scf
    ret

_fwk_sp_screen_ptr:
    ld hl, (_fwk_sp_dest_y)
    ld a, (_fwk_sp_dest_x)
    ld c, a
    jp fwk_video_get_ptr

;; Increment screen Y, decrement rows and return Z after the last row.
_fwk_sp_next_row:
    ld hl, (_fwk_sp_dest_y)
    inc hl
    ld (_fwk_sp_dest_y), hl
    ld a, (_fwk_sp_rows)
    dec a
    ld (_fwk_sp_rows), a
    ret
