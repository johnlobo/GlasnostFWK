.include "video/sprite.inc"

FWK_SPRITE_BATCH_ENTRY_SPRITE = 0
FWK_SPRITE_BATCH_ENTRY_BUFFER = 2
FWK_SPRITE_BATCH_ENTRY_KEY = 4
FWK_SPRITE_BATCH_ENTRY_FLAGS = 5
FWK_SPRITE_BATCH_ENTRY_SIZE = 6
FWK_SPRITE_BATCH_CAPTURED = 0x01

FWK_SPRITE_BATCH_ENTRIES = 0
FWK_SPRITE_BATCH_COUNT = 2
FWK_SPRITE_BATCH_CAPACITY = 3
FWK_SPRITE_BATCH_DESCRIPTOR_SIZE = 4

.macro FWK_SPRITE_BATCH_DESCRIPTOR label, entries, capacity
label:
    .dw entries
    .db 0, capacity
.endm

.globl fwk_sprite_batch_init
.globl fwk_sprite_batch_add
.globl fwk_sprite_batch_restore
.globl fwk_sprite_batch_draw
