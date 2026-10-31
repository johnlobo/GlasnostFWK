.module example_platform
.include "core/pool.inc"
.include "extensions/motion_u8.inc"
.globl fwk_project_init, fwk_system_wait_frame
.globl fwk_pool_init, fwk_pool_alloc, fwk_pool_foreach
.globl fwk_video_init, fwk_video_clear_visible, fwk_video_plot_byte
.globl fwk_motion_u8_step

.area _DATA
_entities: .ds FWK_MOTION_RECORD_SIZE * 4
FWK_POOL_DESCRIPTOR _entity_pool, _entities, 4, FWK_MOTION_RECORD_SIZE

.area _CODE
_draw_entity:
    call fwk_motion_u8_step
    ld l, FWK_MOTION_Y(iy)
    ld h, #0
    ld c, FWK_MOTION_X(iy)
    ld a, #0xF0
    jp fwk_video_plot_byte

_main::
    call fwk_project_init
    call fwk_video_init
    ld ix, #_entity_pool
    call fwk_pool_init
    call fwk_pool_alloc
    ld (hl), #10
    inc hl
    ld (hl), #40
    inc hl
    ld (hl), #1
    inc hl
    ld (hl), #1
    call fwk_pool_alloc
    ld (hl), #70
    inc hl
    ld (hl), #160
    inc hl
    ld (hl), #-1
    inc hl
    ld (hl), #-1
_platform_loop:
    call fwk_system_wait_frame
    xor a
    call fwk_video_clear_visible
    ld ix, #_entity_pool
    ld de, #_draw_entity
    call fwk_pool_foreach
    jr _platform_loop
