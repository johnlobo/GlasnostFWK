;; Profile-aware window geometry and caller-owned background capture.
;; Text, input, timing and buffer allocation remain game policy.
.module fwk_window
.include "ui/window.inc"

.globl fwk_video_get_ptr, fwk_video_width_bytes, fwk_video_height

.area _CODE

;; Internal descriptor validation.
;; In: IX=descriptor. Out: carry set if invalid, clear if drawable.
;; Modified: AF,DE,HL.
_fwk_window_validate:
    ld a, FWK_WINDOW_WIDTH(ix)
    cp #2
    jr c, _fwk_window_invalid
    ld e, a
    ld a, FWK_WINDOW_X(ix)
    add e
    jr c, _fwk_window_invalid
    ld e, a
    ld a, (fwk_video_width_bytes)
    cp e
    jr c, _fwk_window_invalid

    ld a, FWK_WINDOW_HEIGHT(ix)
    cp #2
    jr c, _fwk_window_invalid
    ld e, a
    ld d, #0
    ld l, FWK_WINDOW_Y(ix)
    ld h, FWK_WINDOW_Y+1(ix)
    add hl, de
    ld de, (fwk_video_height)
    or a
    sbc hl, de
    jr c, _fwk_window_valid
    ret z
    jr _fwk_window_invalid
_fwk_window_valid:
    or a
    ret

_fwk_window_invalid:
    scf
    ret

;; fwk_window_capture
;; In: IX=descriptor, DE=buffer of width*height bytes.
;; Out: carry set for invalid geometry, otherwise clear; IY=end of buffer.
;; Modified: AF,BC,DE,HL,IY. IX preserved. Not safe if buffer is too small.
fwk_window_capture::
    push de
    call _fwk_window_validate
    jr c, _fwk_window_capture_invalid
    pop de
    push de
    pop iy
    ld l, FWK_WINDOW_Y(ix)
    ld h, FWK_WINDOW_Y+1(ix)
    ld b, FWK_WINDOW_HEIGHT(ix)
_fwk_window_capture_row:
    push bc
    push hl
    ld c, FWK_WINDOW_X(ix)
    call fwk_video_get_ptr
    ld c, FWK_WINDOW_WIDTH(ix)
_fwk_window_capture_byte:
    ld a, (hl)
    ld 0(iy), a
    inc hl
    inc iy
    dec c
    jr nz, _fwk_window_capture_byte
    pop hl
    inc hl
    pop bc
    djnz _fwk_window_capture_row
    or a
    ret
_fwk_window_capture_invalid:
    pop de
    scf
    ret

;; fwk_window_restore
;; In: IX=descriptor, HL=buffer previously filled by capture.
;; Out: carry set for invalid geometry, otherwise clear; IY=end of buffer.
;; Modified: AF,BC,DE,HL,IY. IX preserved. Geometry must match the capture.
fwk_window_restore::
    push hl
    call _fwk_window_validate
    jr c, _fwk_window_restore_invalid
    pop hl
    push hl
    pop iy
    ld l, FWK_WINDOW_Y(ix)
    ld h, FWK_WINDOW_Y+1(ix)
    ld b, FWK_WINDOW_HEIGHT(ix)
_fwk_window_restore_row:
    push bc
    push hl
    ld c, FWK_WINDOW_X(ix)
    call fwk_video_get_ptr
    ld c, FWK_WINDOW_WIDTH(ix)
_fwk_window_restore_byte:
    ld a, 0(iy)
    ld (hl), a
    inc iy
    inc hl
    dec c
    jr nz, _fwk_window_restore_byte
    pop hl
    inc hl
    pop bc
    djnz _fwk_window_restore_row
    or a
    ret
_fwk_window_restore_invalid:
    pop hl
    scf
    ret

;; fwk_window_draw
;; In: IX=descriptor.
;; Out: carry set for invalid geometry, otherwise clear.
;; Draws a one-byte border and fills the interior.
;; Modified: AF,BC,DE,HL. IX preserved.
fwk_window_draw::
    call _fwk_window_validate
    ret c
    ld l, FWK_WINDOW_Y(ix)
    ld h, FWK_WINDOW_Y+1(ix)
    ld b, FWK_WINDOW_HEIGHT(ix)
_fwk_window_draw_row:
    push bc
    push hl
    ld c, FWK_WINDOW_X(ix)
    call fwk_video_get_ptr
    ld a, b
    cp FWK_WINDOW_HEIGHT(ix)
    jr z, _fwk_window_draw_border_row
    cp #1
    jr z, _fwk_window_draw_border_row

    ld a, FWK_WINDOW_BORDER(ix)
    ld (hl), a
    inc hl
    ld c, FWK_WINDOW_WIDTH(ix)
    dec c
    dec c
    jr z, _fwk_window_draw_last_border
    ld a, FWK_WINDOW_FILL(ix)
_fwk_window_draw_fill:
    ld (hl), a
    inc hl
    dec c
    jr nz, _fwk_window_draw_fill
_fwk_window_draw_last_border:
    ld a, FWK_WINDOW_BORDER(ix)
    ld (hl), a
    jr _fwk_window_draw_next

_fwk_window_draw_border_row:
    ld c, FWK_WINDOW_WIDTH(ix)
    ld a, FWK_WINDOW_BORDER(ix)
_fwk_window_draw_border_byte:
    ld (hl), a
    inc hl
    dec c
    jr nz, _fwk_window_draw_border_byte

_fwk_window_draw_next:
    pop hl
    inc hl
    pop bc
    djnz _fwk_window_draw_row
    or a
    ret
