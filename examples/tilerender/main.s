.module example_tilerender
.include "extensions/tilemap_render.inc"

.globl fwk_system_init, fwk_system_wait_frame
.globl fwk_video_init, fwk_video_clear_visible, fwk_video_plot_byte
.globl fwk_tilemap_render_view, fwk_tilemap_render_cell
.globl cpct_setPALColour_asm
.globl tilerender_view

.area _DATA
tilerender_types:
    .db FWK_TILE_PASSABLE, FWK_TILE_SOLID, FWK_TILE_ONE_WAY, FWK_TILE_PASSABLE

;; 8x6 read-only map. Rows rotate ids 0..3 so camera movement is observable.
tilerender_map:
    .db 0,1,2,3,0,1,2,3
    .db 1,2,3,0,1,2,3,0
    .db 2,3,0,1,2,3,0,1
    .db 3,0,1,2,3,0,1,2
    .db 0,1,2,3,0,1,2,3
    .db 1,2,3,0,1,2,3,0

FWK_TILEMAP_DESCRIPTOR tilerender_map_descriptor, tilerender_map, tilerender_types, 8, 6, 2, 3, 4, 8, 4

;; Four graphics, each 4 Mode 0 bytes x 8 scanlines (32 bytes).
tilerender_tileset:
    .rept 32
        .db 0x00
    .endm
    .rept 32
        .db 0xAA
    .endm
    .rept 4
        .db 0xF0,0x00,0xF0,0x00, 0x00,0xF0,0x00,0xF0
    .endm
    .rept 4
        .db 0xAA,0x00,0xAA,0x00, 0x00,0xAA,0x00,0xAA
    .endm

FWK_TILE_RENDER_DESCRIPTOR tilerender_view, tilerender_tileset, 0, 0, 10, 32, 5, 4, 4

tilerender_status::        .db 0
tilerender_partial_count:: .db 0

.area _CODE

_tilerender_fail:
    ld a, #0xEE
    ld (tilerender_status), a
_tilerender_fail_loop:
    call fwk_system_wait_frame
    jr _tilerender_fail_loop

_main::
    call fwk_system_init
    call fwk_video_init
    ld l, #0
    ld h, #0x14
    call cpct_setPALColour_asm
    ld l, #5
    ld h, #0x0A
    call cpct_setPALColour_asm
    ld l, #15
    ld h, #0x13
    call cpct_setPALColour_asm
    xor a
    call fwk_video_clear_visible
    ld hl, #32
    ld c, #9
    ld a, #0x55
    call fwk_video_plot_byte

    ;; Out-of-viewport partial updates must fail before touching VRAM.
    ld ix, #tilerender_map_descriptor
    ld iy, #tilerender_view
    ld b, #4
    ld c, #0
    call fwk_tilemap_render_cell
    jp nc, _tilerender_fail

    ;; Render the initial camera, then move it and redraw the same viewport.
    ld ix, #tilerender_map_descriptor
    ld iy, #tilerender_view
    call fwk_tilemap_render_view
    jp c, _tilerender_fail
    ld a, #2
    ld (tilerender_view+FWK_TILE_RENDER_CAMERA_X), a
    ld a, #1
    ld (tilerender_view+FWK_TILE_RENDER_CAMERA_Y), a
    ld ix, #tilerender_map_descriptor
    ld iy, #tilerender_view
    call fwk_tilemap_render_view
    jp c, _tilerender_fail

    ;; Damage one byte of viewport cell row 1/column 2, then restore only it.
    ld hl, #40
    ld c, #18
    ld a, #0x55
    call fwk_video_plot_byte
    ld ix, #tilerender_map_descriptor
    ld iy, #tilerender_view
    ld b, #1
    ld c, #2
    call fwk_tilemap_render_cell
    jp c, _tilerender_fail
    ld a, #1
    ld (tilerender_partial_count), a
    ld a, #0x5A
    ld (tilerender_status), a

_tilerender_loop:
    call fwk_system_wait_frame
    jr _tilerender_loop
