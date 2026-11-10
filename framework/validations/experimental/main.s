.module example_experimental
.globl fwk_project_init, fwk_system_wait_frame
.globl fwk_video_init, fwk_video_configure_crtc, fwk_video_clear_visible
.globl fwk_video_width_bytes, fwk_video_height

.area _DATA
experimental_status:: .db 0

.area _CODE

;; ----------------------------------------------------------------------------
;; _main
;;   Experimental-profile smoke test: initialises the system and video, applies the generated CRTC
;;   register table, fills the visible screen with 0xAA and idles.
;;   In : none (program entry; no register is read).
;;   Out: none; never returns (ends in an endless loop).
;;          Memory: visible video RAM = 0xAA; experimental_status = 0x5A once the fill is done.
;;   Clobbers: all (never returns)
;;   Notes: Does not return, so no register is preserved. CRTC timing of experimental profiles is unverified
;;          (see fwk_video_configure_crtc), so the fill is the only visible evidence.
;; ----------------------------------------------------------------------------
_main::
    ;; System up (firmware off, IRQ on), Mode 0 selected.
    call fwk_project_init
    call fwk_video_init
    ;; Program the generated CRTC registers (and page command, if the profile has one).
    call fwk_video_configure_crtc
    ;; Fill the visible regions with 0xAA; then publish 0x5A in experimental_status as the done marker.
    ld a, #0xAA
    call fwk_video_clear_visible
    ld a, #0x5A
    ld (experimental_status), a
_experimental_loop:
    ;; Idle forever, one pass per frame.
    call fwk_system_wait_frame
    jr _experimental_loop
