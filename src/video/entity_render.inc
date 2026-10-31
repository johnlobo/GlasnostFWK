;; Standard 25-byte render prefix. It must start at entity offset 0.
.include "video/sprite.inc"
FWK_ENTITY_RENDER_SPRITE_DATA       = 0
FWK_ENTITY_RENDER_X                 = 2
FWK_ENTITY_RENDER_Y                 = 4
FWK_ENTITY_RENDER_WIDTH             = 6
FWK_ENTITY_RENDER_HEIGHT            = 7
FWK_ENTITY_RENDER_SORT_Y            = 8
FWK_ENTITY_RENDER_BACKGROUND        = 10
FWK_ENTITY_RENDER_BACKGROUND_CAP    = 12
FWK_ENTITY_RENDER_PREVIOUS_X        = 14
FWK_ENTITY_RENDER_PREVIOUS_Y        = 16
FWK_ENTITY_RENDER_PREVIOUS_WIDTH    = 18
FWK_ENTITY_RENDER_PREVIOUS_HEIGHT   = 19
FWK_ENTITY_RENDER_FLAGS             = 20
FWK_ENTITY_RENDER_SOURCE_PEN        = 21
FWK_ENTITY_RENDER_REPLACEMENT_PEN   = 22
FWK_ENTITY_RENDER_PREVIOUS_SORT_Y   = 23
FWK_ENTITY_RENDER_PREFIX_SIZE       = 25

FWK_ENTITY_RENDER_VISIBLE           = 0x01
FWK_ENTITY_RENDER_DIRTY             = 0x02
FWK_ENTITY_RENDER_HAS_BACKGROUND    = 0x04
FWK_ENTITY_RENDER_MASKED            = 0x08
FWK_ENTITY_RENDER_RECOLOR           = 0x10
FWK_ENTITY_RENDER_VALID_FLAGS       = 0x1F

FWK_ENTITY_RENDER_WORK_ENTITY       = 0
FWK_ENTITY_RENDER_WORK_SORT_Y       = 2
FWK_ENTITY_RENDER_WORK_SIZE         = 4

FWK_ENTITY_RENDER_ENTITIES          = 0
FWK_ENTITY_RENDER_COUNT             = 2
FWK_ENTITY_RENDER_WORK              = 3
FWK_ENTITY_RENDER_WORK_CAPACITY     = 5
FWK_ENTITY_RENDER_AFFECTED_COUNT    = 6
FWK_ENTITY_RENDER_STATE             = 7
FWK_ENTITY_RENDER_DESCRIPTOR_SIZE   = 8

FWK_ENTITY_RENDER_STATE_IDLE        = 0
FWK_ENTITY_RENDER_STATE_RESTORED    = 1
FWK_ENTITY_RENDER_STATE_PREPARED    = 2

.macro FWK_ENTITY_RENDER_DESCRIPTOR label, entities, count, work, capacity
label:
    .dw entities
    .db count
    .dw work
    .db capacity, 0, FWK_ENTITY_RENDER_STATE_IDLE
.endm

.macro FWK_ENTITY_RENDER_PREFIX data, x, y, width, height, sort_y, background, capacity, flags, source_pen, replacement_pen
    .dw data, x, y
    .db width, height
    .dw sort_y, background, capacity
    .dw x, y
    .db width, height, flags, source_pen, replacement_pen
    .dw sort_y
.endm

.globl fwk_entity_render_init
.globl fwk_entity_render_revalidate
.globl fwk_entity_render_mark_rect_dirty
.globl fwk_entity_render_prepare_dirty
.globl fwk_entity_render_restore_dirty
.globl fwk_entity_render_draw_dirty
