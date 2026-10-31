.module example_tilemask
.include "extensions/tilemap_render_masked.inc"

.globl fwk_project_init, fwk_system_wait_frame
.globl fwk_video_init, fwk_video_clear_visible
.globl fwk_tilemap_render_view_masked
.globl cpct_setPALColour_asm

.area _DATA
tilemask_types:
    .db FWK_TILE_PASSABLE, FWK_TILE_SOLID
tilemask_map:
    .db 0,1,0,1,0
    .db 1,0,1,0,1
FWK_TILEMAP_DESCRIPTOR tilemask_map_descriptor, tilemask_map, tilemask_types, 5, 2, 2, 2, 4, 4, 2
tilemask_tileset:
    .rept 16
        .db 0xAA
    .endm
    .rept 16
        .db 0x00
    .endm
FWK_TILE_RENDER_DESCRIPTOR tilemask_view, tilemask_tileset, 0, 0, 10, 20, 5, 2, 2
tilemask_status:: .db 0

.area _CODE

_main::
    call fwk_project_init
    call fwk_video_init
    xor a
    call fwk_video_clear_visible

    ld ix, #tilemask_map_descriptor
    ld iy, #tilemask_view
    call fwk_tilemap_render_view_masked
    jp c, _tilemask_fail
    ld a, #0x5A
    ld (tilemask_status), a
_tilemask_loop:
    call fwk_system_wait_frame
    jr _tilemask_loop
_tilemask_fail:
    ld a, #0xEE
    ld (tilemask_status), a
    jr _tilemask_loop
