.module example_minimal
.include "cpctelera.h.s"
.globl fwk_project_init, fwk_system_wait_frame
.globl fwk_input_init, fwk_input_set_bindings, fwk_input_update
.globl fwk_input_held, fwk_video_init, fwk_video_clear_visible, fwk_video_plot_byte

.area _DATA
_bindings:
    .dw Key_O
    .db 0x01
    .dw Key_P
    .db 0x02
    .dw 0
    .db 0

.area _CODE
;; ----------------------------------------------------------------------------
;; _main
;;   Smallest input demo: binds O and P, and every frame shows the held-action mask as a
;;   pixel byte at row 100, column 40.
;;   In : none (program entry; no register is read).
;;   Out: none; never returns (ends in an endless loop).
;;          Memory: one video byte at y=100, x=40 is rewritten every frame with the held mask (0..3).
;;   Clobbers: all (never returns)
;;   Notes: Does not return, so no register is preserved.
;; ----------------------------------------------------------------------------
_main::
    ;; System up (firmware off, IRQ on), Mode 0, screen cleared to pen 0.
    call fwk_project_init
    call fwk_video_init
    xor a
    call fwk_video_clear_visible
    ;; Bind O = action bit 0 (0x01), P = action bit 1 (0x02); the table ends at mask 0.
    call fwk_input_init
    ld hl, #_bindings
    call fwk_input_set_bindings
    ;; Per frame: wait for vsync, rescan bindings, plot the held mask as the pixel byte.
_loop:
    call fwk_system_wait_frame
    call fwk_input_update
    ld a, (fwk_input_held)
    ld hl, #100
    ld c, #40
    call fwk_video_plot_byte
    jr _loop
