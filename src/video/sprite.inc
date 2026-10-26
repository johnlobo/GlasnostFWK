FWK_SPRITE_DATA = 0
FWK_SPRITE_X = 2
FWK_SPRITE_Y = 4
FWK_SPRITE_WIDTH = 6
FWK_SPRITE_HEIGHT = 7
FWK_SPRITE_DESCRIPTOR_SIZE = 8

.macro FWK_SPRITE_DESCRIPTOR label, data, x, y, width, height
label:
    .dw data
    .dw x
    .dw y
    .db width, height
.endm

.globl fwk_sprite_draw
.globl fwk_sprite_draw_masked
.globl fwk_sprite_capture
.globl fwk_sprite_restore
