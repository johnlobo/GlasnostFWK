.module example_experimental
.globl fwk_project_init, fwk_system_wait_frame
.globl fwk_video_init, fwk_video_configure_crtc, fwk_video_clear_visible
.globl fwk_video_width_bytes, fwk_video_height

.area _DATA
experimental_status:: .db 0

.area _CODE

_main::
    call fwk_project_init
    call fwk_video_init
    call fwk_video_configure_crtc
    ld a, #0xAA
    call fwk_video_clear_visible
    ld a, #0x5A
    ld (experimental_status), a
_experimental_loop:
    call fwk_system_wait_frame
    jr _experimental_loop
