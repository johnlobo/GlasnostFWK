;; Dirty-rectangle helper for the tilemap renderer.
;; The caller owns the dirty cell list; this module only tracks indices.

FWK_TILE_DIRTY_CAPACITY = 0
FWK_TILE_DIRTY_COUNT = 1
FWK_TILE_DIRTY_CELLS = 2
FWK_TILE_DIRTY_DESCRIPTOR_SIZE = 2

.macro FWK_TILE_DIRTY_DESCRIPTOR label, cells, capacity
label:
    .db capacity, 0
    .dw cells
.endm

.globl fwk_tilemap_dirty_init
.globl fwk_tilemap_dirty_mark
.globl fwk_tilemap_dirty_flush
.globl fwk_tilemap_dirty_clear