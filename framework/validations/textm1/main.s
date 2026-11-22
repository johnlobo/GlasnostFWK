.module validation_textm1
.include "cpctelera.h.s"

.globl fwk_project_init, fwk_video_init, fwk_video_configure_crtc
.globl fwk_text_init, fwk_text_draw, fwk_text_draw_big
.globl fwk_text_draw_small_u8, fwk_text_draw_small_u8_big

TEXTM1_ROW_NORMAL = 0xC000          ;; scanline 0: "AB", normal height
TEXTM1_ROW_BIG = 0xC0A0             ;; scanline 16: "AB", double height
TEXTM1_ROW_U8 = 0xC1E0              ;; scanline 48: 123 in small digits
TEXTM1_ROW_U8_BIG = 0xC280          ;; scanline 64: 123, double height
TEXTM1_ROW_U8_ZERO = 0xC3C0         ;; scanline 96: 0 in small digits (123 must differ)

.area _DATA
textm1_ready:: .db 0
_text: .asciz "AB"

.area _CODE
;; ----------------------------------------------------------------------------
;; _main
;;   Mode 1 text self-test: the same string and number at normal and at double
;;   height, so the smoke can check that every line of the _big drawing is a
;;   normal line twice.
;;   In : none (program entry; no register is read).
;;   Out: none; never returns.
;;          Memory: textm1_ready = 0x5A once everything is drawn.
;;          VRAM: "AB" at scanline 0 (9 lines) and 16 (18 lines); 123 in small
;;          digits at 48 (5 lines) and 64 (10 lines); 0 at 96.
;;   Clobbers: all (never returns)
;;   Notes: Does not return, so no register is preserved.
;; ----------------------------------------------------------------------------
_main::
    call fwk_project_init
    call fwk_video_init
    call fwk_video_configure_crtc
    call fwk_text_init
    ld iy, #_text
    ld hl, #TEXTM1_ROW_NORMAL
    call fwk_text_draw
    ld iy, #_text
    ld hl, #TEXTM1_ROW_BIG
    call fwk_text_draw_big
    ld a, #123
    ld hl, #TEXTM1_ROW_U8
    call fwk_text_draw_small_u8
    ld a, #123
    ld hl, #TEXTM1_ROW_U8_BIG
    call fwk_text_draw_small_u8_big
    xor a
    ld hl, #TEXTM1_ROW_U8_ZERO
    call fwk_text_draw_small_u8
    ld a, #0x5A
    ld (textm1_ready), a
_textm1_idle:
    jr _textm1_idle
