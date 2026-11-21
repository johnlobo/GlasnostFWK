.module validation_uiinput
.include "cpctelera.h.s"

.globl fwk_project_init, fwk_system_frame_count, fwk_system_wait_frame
.globl fwk_input_init, fwk_input_set_bindings, fwk_input_update, fwk_input_repeat
.globl fwk_text_init, fwk_text_draw, fwk_text_draw_centered, fwk_text_draw_clear

UIINPUT_ROW_CENTRED = 0xC000           ;; scanline 0
UIINPUT_ROW_CLEARED = 0xC0A0           ;; scanline 16
UIINPUT_LOG_SIZE = 16

.area _DATA
uiinput_ready:: .db 0
uiinput_log_count:: .db 0
;; Low byte of fwk_system_frame_count at each update with fwk_input_repeat != 0.
uiinput_log:: .ds UIINPUT_LOG_SIZE

_centred: .asciz "AB"
_long: .asciz "WXYZ"
_short: .asciz "A"
_bindings:
    .dw Key_CursorRight
    .db 0x01
    .dw 0
    .db 0

.area _CODE
;; ----------------------------------------------------------------------------
;; _main
;;   Text and key-repeat self-test: draws "AB" centred on scanline 0, "WXYZ" then a cleared "A" over it on
;;   scanline 16, and logs the frames where fwk_input_repeat is non-zero while the test holds a key.
;;   In : none (program entry; no register is read).
;;   Out: none; never returns (main loop).
;;          Memory: uiinput_ready = 0x5A once the text is drawn; uiinput_log holds the frame-counter low
;;          byte of each repeat event (first UIINPUT_LOG_SIZE events), uiinput_log_count how many.
;;          VRAM: "AB" at bytes 38..41 of scanline 0..8; only "A" (bytes 0..1) left on scanline 16..24.
;;   Clobbers: all (never returns)
;;   Notes: Does not return, so no register is preserved. One fwk_input_update per frame (frame counter), so the repeat
;;          delay and interval are in frames (defaults 15 and 4).
;; ----------------------------------------------------------------------------
_main::
    call fwk_project_init
    call fwk_text_init
    ld iy, #_centred
    ld hl, #UIINPUT_ROW_CENTRED
    call fwk_text_draw_centered
    ld iy, #_long
    ld hl, #UIINPUT_ROW_CLEARED
    call fwk_text_draw
    ld iy, #_short
    ld hl, #UIINPUT_ROW_CLEARED
    ld b, #4
    ld c, #0
    call fwk_text_draw_clear

    call fwk_input_init
    ld hl, #_bindings
    call fwk_input_set_bindings
    ld a, #0x5A
    ld (uiinput_ready), a
_loop:
    ;; One update per frame: fwk_system_wait_frame returns once per frame
    ;; however short the loop (the smoke checks the repeat gaps in frames).
    call fwk_system_wait_frame
    call fwk_input_update
    ld a, (fwk_input_repeat)
    or a
    jr z, _loop
    ld a, (uiinput_log_count)
    cp #UIINPUT_LOG_SIZE
    jr nc, _loop
    ld e, a
    ld d, #0
    inc a
    ld (uiinput_log_count), a
    ld hl, #uiinput_log
    add hl, de
    ld a, (fwk_system_frame_count)
    ld (hl), a
    jr _loop
