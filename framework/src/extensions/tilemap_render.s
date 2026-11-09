;; CPCTelera Next tilemap renderer with a consumer-owned viewport.
.module fwk_tilemap_render
.include "extensions/tilemap_render.inc"

.globl fwk_video_get_ptr, fwk_video_width_bytes, fwk_video_height
.globl cpct_drawTileAligned2x4_f_asm, cpct_drawTileAligned2x8_f_asm
.globl cpct_drawTileAligned4x4_f_asm, cpct_drawTileAligned4x8_f_asm

.area _DATA
_fwk_tr_row:        .db 0
_fwk_tr_column:     .db 0
_fwk_tr_tile_id:    .db 0
_fwk_tr_screen_x:   .db 0
_fwk_tr_tile_area:  .dw 0
_fwk_tr_graphics:   .dw 0
_fwk_tr_screen_y:   .dw 0

.area _CODE

;; fwk_tilemap_render_view
;; In: IX=tilemap descriptor, IY=render descriptor.
;; Out: carry clear after drawing the whole viewport; carry set without writes
;;      for invalid geometry or a tile id outside the graphics table.
;; Modified: AF,BC,DE,HL. IX/IY preserved. Not reentrant (internal scratch).
fwk_tilemap_render_view::
    call _fwk_tr_validate
    ret c

    ;; Validate every selected id before the first video write.
    xor a
    ld (_fwk_tr_row), a
_fwk_tr_preflight_row:
    xor a
    ld (_fwk_tr_column), a
_fwk_tr_preflight_column:
    call _fwk_tr_get_tile
    ret c
    ld a, (_fwk_tr_column)
    inc a
    ld (_fwk_tr_column), a
    cp FWK_TILE_RENDER_VIEW_WIDTH(iy)
    jr c, _fwk_tr_preflight_column
    ld a, (_fwk_tr_row)
    inc a
    ld (_fwk_tr_row), a
    cp FWK_TILE_RENDER_VIEW_HEIGHT(iy)
    jr c, _fwk_tr_preflight_row

    xor a
    ld (_fwk_tr_row), a
_fwk_tr_render_row:
    xor a
    ld (_fwk_tr_column), a
_fwk_tr_render_column:
    call _fwk_tr_get_tile
    call _fwk_tr_draw_tile
    ld a, (_fwk_tr_column)
    inc a
    ld (_fwk_tr_column), a
    cp FWK_TILE_RENDER_VIEW_WIDTH(iy)
    jr c, _fwk_tr_render_column
    ld a, (_fwk_tr_row)
    inc a
    ld (_fwk_tr_row), a
    cp FWK_TILE_RENDER_VIEW_HEIGHT(iy)
    jr c, _fwk_tr_render_row
    or a
    ret

;; fwk_tilemap_render_cell
;; In: IX=tilemap descriptor, IY=render descriptor, B=viewport row,
;;     C=viewport column.
;; Out/modified/reentrancy: as fwk_tilemap_render_view. Only the selected tile
;; is written. Carry is set before writing when row/column/id is invalid.
fwk_tilemap_render_cell::
    ld a, b
    ld (_fwk_tr_row), a
    ld a, c
    ld (_fwk_tr_column), a
    call _fwk_tr_validate
    ret c
    ld a, (_fwk_tr_row)
    cp FWK_TILE_RENDER_VIEW_HEIGHT(iy)
    jp nc, _fwk_tr_invalid
    ld a, (_fwk_tr_column)
    cp FWK_TILE_RENDER_VIEW_WIDTH(iy)
    jp nc, _fwk_tr_invalid
    call _fwk_tr_get_tile
    ret c
    call _fwk_tr_draw_tile
    or a
    ret

;; Validate map/viewport/screen geometry and cache tile area.
_fwk_tr_validate:
    ld a, FWK_TILEMAP_WIDTH(ix)
    or a
    jp z, _fwk_tr_invalid
    ld a, FWK_TILEMAP_HEIGHT(ix)
    or a
    jp z, _fwk_tr_invalid
    ld a, FWK_TILEMAP_X_SIZE(ix)
    or a
    jp z, _fwk_tr_invalid
    ld a, FWK_TILEMAP_Y_SIZE(ix)
    or a
    jp z, _fwk_tr_invalid

    ;; CPCTelera Next exposes aligned tile primitives for exactly these four
    ;; byte geometries. Reject everything else before the first video write.
    cp #4
    jr z, _fwk_tr_geometry_width
    cp #8
    jp nz, _fwk_tr_invalid
_fwk_tr_geometry_width:
    ld a, FWK_TILEMAP_X_SIZE(ix)
    cp #2
    jr nz, _fwk_tr_geometry_4wide
    ld a, FWK_TILEMAP_X_SHIFT(ix)
    cp #1
    jp nz, _fwk_tr_invalid
    jr _fwk_tr_geometry_height_shift
_fwk_tr_geometry_4wide:
    cp #4
    jp nz, _fwk_tr_invalid
    ld a, FWK_TILEMAP_X_SHIFT(ix)
    cp #2
    jp nz, _fwk_tr_invalid
_fwk_tr_geometry_height_shift:
    ld a, FWK_TILEMAP_Y_SIZE(ix)
    cp #4
    jr nz, _fwk_tr_geometry_8high
    ld a, FWK_TILEMAP_Y_SHIFT(ix)
    cp #2
    jp nz, _fwk_tr_invalid
    jr _fwk_tr_geometry_alignment
_fwk_tr_geometry_8high:
    ld a, FWK_TILEMAP_Y_SHIFT(ix)
    cp #3
    jp nz, _fwk_tr_invalid
_fwk_tr_geometry_alignment:
    ;; An aligned primitive must begin on its 4/8-scanline boundary.
    ld a, FWK_TILEMAP_Y_SIZE(ix)
    dec a
    ld b, a
    ld a, FWK_TILE_RENDER_SCREEN_Y(iy)
    and b
    jp nz, _fwk_tr_invalid
    ld a, FWK_TILE_RENDER_VIEW_WIDTH(iy)
    or a
    jp z, _fwk_tr_invalid
    ld a, FWK_TILE_RENDER_VIEW_HEIGHT(iy)
    or a
    jp z, _fwk_tr_invalid
    ld a, FWK_TILE_RENDER_TILE_COUNT(iy)
    or a
    jp z, _fwk_tr_invalid

    ;; Camera rectangle must fit inside the map, including overflow checks.
    ld a, FWK_TILE_RENDER_CAMERA_X(iy)
    add FWK_TILE_RENDER_VIEW_WIDTH(iy)
    jp c, _fwk_tr_invalid
    cp FWK_TILEMAP_WIDTH(ix)
    jr c, _fwk_tr_camera_y
    jp nz, _fwk_tr_invalid
_fwk_tr_camera_y:
    ld a, FWK_TILE_RENDER_CAMERA_Y(iy)
    add FWK_TILE_RENDER_VIEW_HEIGHT(iy)
    jp c, _fwk_tr_invalid
    cp FWK_TILEMAP_HEIGHT(ix)
    jr c, _fwk_tr_screen_width
    jp nz, _fwk_tr_invalid

    ;; Screen X + viewport width in bytes must fit the active profile.
_fwk_tr_screen_width:
    ld a, FWK_TILE_RENDER_SCREEN_X(iy)
    ld b, FWK_TILE_RENDER_VIEW_WIDTH(iy)
_fwk_tr_width_loop:
    add FWK_TILEMAP_X_SIZE(ix)
    jp c, _fwk_tr_invalid
    djnz _fwk_tr_width_loop
    ld b, a
    ld a, (fwk_video_width_bytes)
    cp b
    jp c, _fwk_tr_invalid

    ;; Cache tile byte area and validate the 16-bit screen bottom edge.
    ld e, FWK_TILEMAP_X_SIZE(ix)
    ld d, #0
    ld b, FWK_TILEMAP_Y_SIZE(ix)
    ld hl, #0
_fwk_tr_area_loop:
    add hl, de
    jp c, _fwk_tr_invalid
    djnz _fwk_tr_area_loop
    ld (_fwk_tr_tile_area), hl

    ;; The complete graphics table must not wrap the 16-bit address space.
    ex de, hl
    ld l, FWK_TILE_RENDER_TILESET(iy)
    ld h, FWK_TILE_RENDER_TILESET+1(iy)
    ld b, FWK_TILE_RENDER_TILE_COUNT(iy)
_fwk_tr_tileset_span_loop:
    add hl, de
    jp c, _fwk_tr_invalid
    djnz _fwk_tr_tileset_span_loop

    ld e, FWK_TILEMAP_Y_SIZE(ix)
    ld d, #0
    ld b, FWK_TILE_RENDER_VIEW_HEIGHT(iy)
    ld hl, #0
_fwk_tr_height_loop:
    add hl, de
    jp c, _fwk_tr_invalid
    djnz _fwk_tr_height_loop
    ld e, FWK_TILE_RENDER_SCREEN_Y(iy)
    ld d, FWK_TILE_RENDER_SCREEN_Y+1(iy)
    add hl, de
    jp c, _fwk_tr_invalid
    ld de, (fwk_video_height)
    or a
    sbc hl, de
    jr c, _fwk_tr_valid
    jp nz, _fwk_tr_invalid
_fwk_tr_valid:
    or a
    ret

_fwk_tr_invalid:
    scf
    ret

;; Resolve the current viewport row/column to an id. Carry marks invalid id.
_fwk_tr_get_tile:
    ld a, FWK_TILE_RENDER_CAMERA_Y(iy)
    ld b, a
    ld a, (_fwk_tr_row)
    add b
    ld b, a
    ld e, FWK_TILEMAP_WIDTH(ix)
    ld d, #0
    ld hl, #0
    ld a, b
    or a
    jr z, _fwk_tr_map_row_ready
_fwk_tr_map_row_loop:
    add hl, de
    djnz _fwk_tr_map_row_loop
_fwk_tr_map_row_ready:
    ld a, FWK_TILE_RENDER_CAMERA_X(iy)
    ld e, a
    ld a, (_fwk_tr_column)
    add e
    ld e, a
    ld d, #0
    add hl, de
    ld e, FWK_TILEMAP_DATA(ix)
    ld d, FWK_TILEMAP_DATA+1(ix)
    add hl, de
    ld a, (hl)
    cp FWK_TILE_RENDER_TILE_COUNT(iy)
    jp nc, _fwk_tr_invalid
    ld (_fwk_tr_tile_id), a
    or a
    ret

;; Draw the current valid tile id at the current viewport row/column.
_fwk_tr_draw_tile:
    ld l, FWK_TILE_RENDER_TILESET(iy)
    ld h, FWK_TILE_RENDER_TILESET+1(iy)
    ld de, (_fwk_tr_tile_area)
    ld a, (_fwk_tr_tile_id)
    or a
    jr z, _fwk_tr_graphics_ready
    ld b, a
_fwk_tr_graphics_loop:
    add hl, de
    djnz _fwk_tr_graphics_loop
_fwk_tr_graphics_ready:
    ld (_fwk_tr_graphics), hl

    ld a, FWK_TILE_RENDER_SCREEN_X(iy)
    ld e, FWK_TILEMAP_X_SIZE(ix)
    ld a, (_fwk_tr_column)
    ld b, a
    ld a, FWK_TILE_RENDER_SCREEN_X(iy)
    inc b
    dec b
    jr z, _fwk_tr_x_ready
_fwk_tr_x_loop:
    add e
    djnz _fwk_tr_x_loop
_fwk_tr_x_ready:
    ld (_fwk_tr_screen_x), a

    ld l, FWK_TILE_RENDER_SCREEN_Y(iy)
    ld h, FWK_TILE_RENDER_SCREEN_Y+1(iy)
    ld e, FWK_TILEMAP_Y_SIZE(ix)
    ld d, #0
    ld a, (_fwk_tr_row)
    ld b, a
    inc b
    dec b
    jr z, _fwk_tr_y_ready
_fwk_tr_y_loop:
    add hl, de
    djnz _fwk_tr_y_loop
_fwk_tr_y_ready:
    ld (_fwk_tr_screen_y), hl
    ;; Resolve the destination once, then let CPCTelera copy the complete tile.
    ld hl, (_fwk_tr_screen_y)
    ld a, (_fwk_tr_screen_x)
    ld c, a
    call fwk_video_get_ptr
    ex de, hl
    ld hl, (_fwk_tr_graphics)

    ;; Dispatch only to CPCTelera Next's aligned, unrolled primitives.
    ld a, FWK_TILEMAP_X_SIZE(ix)
    cp #2
    jr nz, _fwk_tr_draw_4wide
    ld a, FWK_TILEMAP_Y_SIZE(ix)
    cp #4
    jp z, cpct_drawTileAligned2x4_f_asm
    jp cpct_drawTileAligned2x8_f_asm
_fwk_tr_draw_4wide:
    ld a, FWK_TILEMAP_Y_SIZE(ix)
    cp #4
    jp z, cpct_drawTileAligned4x4_f_asm
    jp cpct_drawTileAligned4x8_f_asm
