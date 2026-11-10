.module example_video
.globl fwk_project_init, fwk_video_init, fwk_video_clear_visible, fwk_video_plot_byte

.area _CODE
;; ----------------------------------------------------------------------------
;; _main
;;   Video smoke test: checks that fwk_video_clear_visible leaves the unused gap at 0xC7D0 alone,
;;   then plots one byte at the top-left and one at the bottom-right of the 80x200 area.
;;   In : none (program entry; no register is read).
;;   Out: none; never returns (ends in an endless loop).
;;          Memory: 0xC7D0 = 0xA5 (gap witness); visible video RAM = 0x33 except the plotted bytes;
;;          (x=0,y=0) and (x=79,y=199) = 0xFF. Gate Array: pass writes 0x10 (border pen select);
;;          a changed witness writes 0x4C (colour 0x0C, bright red) to the currently selected pen.
;;   Clobbers: all (never returns)
;;   Notes: Does not return, so no register is preserved. The second plot reuses A=0xFF without reloading it: that
;;          works because fwk_video_plot_byte restores AF (push af / pop af) around its pointer lookup.
;; ----------------------------------------------------------------------------
_main::
    ;; System up (firmware off, IRQ on), Mode 0.
    call fwk_project_init
    call fwk_video_init
    ld hl, #0xC7D0
    ld (hl), #0xA5                    ;; witness in first standard-screen hole
    ;; Fill the visible regions with 0x33; the witness byte in the screen gap must be untouched.
    ld a, #0x33
    call fwk_video_clear_visible
    ld a, (0xC7D0)
    cp #0xA5
    jr nz, _failed
    ;; Corner pixels: (y=0, x=0) then (y=199, x=79); A=0xFF survives the first call.
    ld hl, #0
    ld c, #0
    ld a, #0xFF
    call fwk_video_plot_byte
    ld hl, #199
    ld c, #79
    call fwk_video_plot_byte
    ;; Pass: Gate Array pen select, value 0x10. Spin forever.
_passed:
    ld bc, #0x7F10
    out (c), c
    jr _passed
    ;; Witness overwritten: Gate Array colour write 0x4C. Spin forever.
_failed:
    ld bc, #0x7F4C
    out (c), c
    jr _failed
