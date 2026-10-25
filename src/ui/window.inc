;; Immutable window descriptor. Coordinates and sizes are expressed in
;; Mode-0 screen bytes/scanlines, not pixels.
FWK_WINDOW_X = 0
FWK_WINDOW_Y = 1
FWK_WINDOW_WIDTH = 3
FWK_WINDOW_HEIGHT = 4
FWK_WINDOW_BORDER = 5
FWK_WINDOW_FILL = 6
FWK_WINDOW_DESCRIPTOR_SIZE = 7

.globl fwk_window_capture
.globl fwk_window_draw
.globl fwk_window_restore
