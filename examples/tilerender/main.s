.module example_tilerender
.include "extensions/tilemap_render.inc"
.include "extensions/tilemap_dirty.inc"

.globl fwk_project_init, fwk_system_wait_frame
.globl fwk_video_init, fwk_video_clear_visible, fwk_video_plot_byte
.globl fwk_tilemap_render_view, fwk_tilemap_render_cell
.globl fwk_tilemap_dirty_init, fwk_tilemap_dirty_mark, fwk_tilemap_dirty_flush
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

;; 8x6 map, tile types by id, shifts 2 and 3 (4 bytes x 8 scanlines per tile), 4 types.
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

;; Viewport: camera (0,0), top-left at screen byte 10 / scanline 32, 5x4 tiles, 4 graphics.
FWK_TILE_RENDER_DESCRIPTOR tilerender_view, tilerender_tileset, 0, 0, 10, 32, 5, 4, 4

tilerender_status::        .db 0   ; 0x5A all steps done, 0xEE a render call failed
tilerender_partial_count:: .db 0   ; 1 once the partial update steps have run

;; Dirty list storage: 8 cells of (row, column) = 16 bytes.
tilerender_dirty_cells:: .ds 16
FWK_TILE_DIRTY_DESCRIPTOR tilerender_dirty, tilerender_dirty_cells, 8

.area _CODE

;; ----------------------------------------------------------------------------
;; _tilerender_fail
;;   Records a failed render step in tilerender_status (0xEE) and stops there.
;;   In : none (entered by jp).
;;   Out: never returns; tilerender_status=0xEE.
;;   Clobbers: all (never returns)
;;   Notes: The loop keeps waiting for frames so the machine stays responsive. Entered
;;          by jp, so there is no return address on the stack to use.
;; ----------------------------------------------------------------------------
_tilerender_fail:
    ld a, #0xEE
    ld (tilerender_status), a
_tilerender_fail_loop:
    call fwk_system_wait_frame
    jr _tilerender_fail_loop

;; ----------------------------------------------------------------------------
;; _main
;;   Program entry. Exercises the tilemap renderer in order: a rejected
;;   out-of-viewport cell, a full viewport render, a camera move and re-render,
;;   a single damaged cell repaired with render_cell, and the same repair through
;;   the dirty list. Then idles.
;;   In : none.
;;   Out: never returns. tilerender_status=0x5A on success, 0xEE through
;;        _tilerender_fail if any call answers with the wrong carry.
;;   Clobbers: all (never returns)
;;   Notes: The byte 0x55 written at x=9, y=32 sits just left of the viewport (screen
;;          byte 10) and must survive every render: the emulator test reads it as a "no
;;          write outside" witness.
;; ----------------------------------------------------------------------------
_main::
    call fwk_project_init
    call fwk_video_init
    ;; Palette: L=pen, H=hardware colour (black, bright yellow, bright cyan).
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
    ;; Witness byte one column left of the viewport (y=32, x=9).
    ld hl, #32
    ld c, #9
    ld a, #0x55
    call fwk_video_plot_byte

    ;; Out-of-viewport partial updates must fail before touching VRAM.
    ld ix, #tilerender_map_descriptor
    ld iy, #tilerender_view
    ld b, #4                        ; row 4 does not exist (view height is 4)
    ld c, #0
    call fwk_tilemap_render_cell
    jp nc, _tilerender_fail         ; accepted: that is the failure here

    ;; Render the initial camera, then move it and redraw the same viewport.
    ld ix, #tilerender_map_descriptor
    ld iy, #tilerender_view
    call fwk_tilemap_render_view
    jp c, _tilerender_fail
    ld a, #2                        ; camera to tile (2,1)
    ld (tilerender_view+FWK_TILE_RENDER_CAMERA_X), a
    ld a, #1
    ld (tilerender_view+FWK_TILE_RENDER_CAMERA_Y), a
    ld ix, #tilerender_map_descriptor
    ld iy, #tilerender_view
    call fwk_tilemap_render_view
    jp c, _tilerender_fail

    ;; Damage one byte of viewport cell row 1/column 2, then restore only it.
    ld hl, #40                      ; y = 32 + 1 row * 8
    ld c, #18                       ; x = 10 + 2 columns * 4
    ld a, #0x55
    call fwk_video_plot_byte
    ld ix, #tilerender_map_descriptor
    ld iy, #tilerender_view
    ld b, #1                        ; B=row, C=column of the viewport cell
    ld c, #2
    call fwk_tilemap_render_cell
    jp c, _tilerender_fail

    ;; Demonstrate the dirty-rectangle helper on the same cell.
    ld hl, #tilerender_dirty
    call fwk_tilemap_dirty_init     ; empty list
    ld b, #1                        ; mark cell row 1, column 2 as dirty
    ld c, #2
    call fwk_tilemap_dirty_mark
    ld ix, #tilerender_map_descriptor
    ld iy, #tilerender_view
    call fwk_tilemap_dirty_flush
    jp c, _tilerender_fail

    ld a, #1                        ; the test reads this as "partial path ran"
    ld (tilerender_partial_count), a
    ld a, #0x5A                     ; all steps passed
    ld (tilerender_status), a

_tilerender_loop:                   ; idle, one iteration per frame
    call fwk_system_wait_frame
    jr _tilerender_loop
