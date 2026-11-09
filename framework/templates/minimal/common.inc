;; Common definitions of this project, imported by every .s file.
.include "cpctelera.h.s"

.globl fwk_project_init, fwk_system_wait_frame
.globl fwk_video_init, fwk_video_clear_visible, fwk_video_get_ptr
.globl fwk_text_init, fwk_text_draw
.globl cpct_setPalette_asm

;; Text positions (byte column, scanline).
MINIMAL_TEXT_X = 4
MINIMAL_TEXT_Y_WELCOME = 80
MINIMAL_TEXT_Y_HELP = 100