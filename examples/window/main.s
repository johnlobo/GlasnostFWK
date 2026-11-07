.module example_window
.include "ui/window.inc"

.globl fwk_project_init, fwk_system_wait_frame
.globl fwk_video_init, fwk_video_clear_visible, fwk_video_get_ptr
.globl fwk_text_init, fwk_text_set_color, fwk_text_draw

WINDOW_WIDTH = 20
WINDOW_HEIGHT = 16
WINDOW_BUFFER_SIZE = WINDOW_WIDTH * WINDOW_HEIGHT

.area _DATA
;; Descriptor layout (ui/window.inc): x byte, y word, width, height, border byte,
;; fill byte. Sizes and positions are in Mode 0 screen bytes and scanlines.
window_descriptor::
    .db 10
    .dw 40
    .db WINDOW_WIDTH
    .db WINDOW_HEIGHT
    .db 0xFF
    .db 0x00

;; x + width = 85 is beyond the 80-byte line: must be rejected.
window_invalid_descriptor:
    .db 75
    .dw 40
    .db 10
    .db 10
    .db 0xFF
    .db 0x00

;; Y + height must not wrap the 16-bit coordinate space.
window_overflow_descriptor:
    .db 10
    .dw 0xFFFF
    .db 10
    .db 10
    .db 0xFF
    .db 0x00

window_message: .asciz "GLASNOST"
window_buffer:: .ds WINDOW_BUFFER_SIZE   ; saved background, width * height bytes
;; Command mailbox written by the emulator test: 1=close (restore), 2=reopen.
window_command:: .db 0
;; Progress marker: 0xA5 shown, 0x5A closed, 0xC3 reopened, 0xEE failure.
window_status:: .db 0

.area _CODE
;; ----------------------------------------------------------------------------
;; _main
;;   Program entry. Checks that two bad descriptors are rejected, captures the
;;   background under the real window, shows it, then serves the close and
;;   reopen commands of window_command forever.
;;   In : none.
;;   Out: never returns. window_status reports progress (see window_status).
;;   Clobbers: all (never returns)
;;   Notes: An unexpected carry from the checks, fwk_window_capture or fwk_window_restore sets
;;          window_status to 0xEE and the program keeps polling the mailbox; the carry of
;;          _window_show is not tested, so a rejected draw still reports 0xA5 or 0xC3. Window and text callees clobber AF, BC, DE, HL, IX, IY.
;; ----------------------------------------------------------------------------
_main::
    call fwk_project_init
    call fwk_video_init
    call fwk_text_init
    ld a, #0x55                     ; non-zero fill so a restored background is visible
    call fwk_video_clear_visible

    ;; Invalid geometry must be rejected without touching the screen/buffer.
    ld ix, #window_invalid_descriptor
    ld de, #window_buffer
    call fwk_window_capture
    jr nc, _window_failed

    ;; Y+height overflow is invalid even though the wrapped sum is on-screen.
    ld ix, #window_overflow_descriptor
    ld de, #window_buffer
    call fwk_window_capture
    jr nc, _window_failed

    ld ix, #window_descriptor
    ld de, #window_buffer
    call fwk_window_capture
    jr c, _window_failed            ; the valid window must be accepted
    call _window_show
    ld a, #0xA5
    ld (window_status), a

_window_loop:                       ; poll the mailbox once per frame
    call fwk_system_wait_frame
    ld a, (window_command)
    cp #1
    jr z, _window_close
    cp #2
    jr z, _window_reopen
    jr _window_loop

_window_close:                      ; command 1: put the saved background back
    xor a                           ; consume the command
    ld (window_command), a
    ld ix, #window_descriptor
    ld hl, #window_buffer
    call fwk_window_restore
    jr c, _window_failed
    ld a, #0x5A
    ld (window_status), a
    jr _window_loop

_window_reopen:                     ; command 2: draw again (no new capture needed)
    xor a                           ; consume the command
    ld (window_command), a
    call _window_show
    ld a, #0xC3
    ld (window_status), a
    jr _window_loop

;; ----------------------------------------------------------------------------
;; _window_show
;;   Draws window_descriptor (border and fill) and writes the text GLASNOST
;;   inside it with colour index 0.
;;   In : none.
;;   Out: carry set if fwk_window_draw rejected the geometry (nothing else done);
;;        otherwise the text has been drawn and carry is not meaningful.
;;   Clobbers: AF, BC, DE, HL, IX, IY
;;   Notes: IX is set to window_descriptor (fwk_window_draw preserves it) and IY to
;;          window_message; fwk_text_draw documents AF, BC, DE, HL, IX, IY. Ends with a
;;          tail jump into fwk_text_draw, which returns to the caller. On the carry-set
;;          path only AF, IX (and the callee's registers) have changed.
;; ----------------------------------------------------------------------------
_window_show:
    ld ix, #window_descriptor
    call fwk_window_draw
    ret c                           ; invalid geometry: report it to the caller
    xor a                           ; colour table index 0
    call fwk_text_set_color
    ld hl, #44                      ; y = 44 scanlines (inside the window, which starts at 40)
    ld c, #12                       ; x = 12 bytes (window starts at byte 10, border is 1 byte)
    call fwk_video_get_ptr          ; HL = screen address of that cell
    ld iy, #window_message
    jp fwk_text_draw

_window_failed:                     ; record the failure and go on polling
    ld a, #0xEE
    ld (window_status), a
    jr _window_loop
