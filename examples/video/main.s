.module example_video
.globl fwk_project_init, fwk_video_init, fwk_video_clear_visible, fwk_video_plot_byte

.area _CODE
_main::
    call fwk_project_init
    call fwk_video_init
    ld hl, #0xC7D0
    ld (hl), #0xA5                    ;; witness in first standard-screen hole
    ld a, #0x33
    call fwk_video_clear_visible
    ld a, (0xC7D0)
    cp #0xA5
    jr nz, _failed
    ld hl, #0
    ld c, #0
    ld a, #0xFF
    call fwk_video_plot_byte
    ld hl, #199
    ld c, #79
    call fwk_video_plot_byte
_passed:
    ld bc, #0x7F10
    out (c), c
    jr _passed
_failed:
    ld bc, #0x7F4C
    out (c), c
    jr _failed
