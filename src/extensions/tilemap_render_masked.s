;; Masked rectangular Mode 0 tilemap renderer.
.module fwk_tilemap_render_masked
.include "extensions/tilemap_render_masked.inc"

.globl fwk_video_get_ptr
.globl fwk_video_width_bytes, fwk_video_height

.area _DATA
_fwk_trm_width:: .db 0
_fwk_trm_count:: .db 0
_fwk_trm_gptr:: .dw 0
_fwk_trm_mptr:: .dw 0
_fwk_trm_row::        .db 0
_fwk_trm_column::     .db 0
_fwk_trm_tile_id::    .db 0
_fwk_trm_screen_x::   .db 0
_fwk_trm_lines::      .db 0
_fwk_trm_tile_area::  .dw 0
_fwk_trm_graphics::   .dw 0
_fwk_trm_mask::       .dw 0
_fwk_trm_screen_y::   .dw 0
_fwk_trm_mask_tileset::.dw 0

.area _CODE

;; Bind the parallel mask tileset used by the masked renderers.
fwk_tilemap_render_masked_bind::
    ld (_fwk_trm_mask_tileset), hl
    ret

;; fwk_tilemap_render_view_masked
fwk_tilemap_render_view_masked::
    call _fwk_trm_validate
    ret c
    xor a
    ld (_fwk_trm_row), a
_fwk_trm_preflight_row:
    xor a
    ld (_fwk_trm_column), a
_fwk_trm_preflight_column:
    call _fwk_trm_get_tile
    ret c
    ld a, (_fwk_trm_column)
    inc a
    ld (_fwk_trm_column), a
    cp FWK_TILE_RENDER_VIEW_WIDTH(iy)
    jr c, _fwk_trm_preflight_column
    ld a, (_fwk_trm_row)
    inc a
    ld (_fwk_trm_row), a
    cp FWK_TILE_RENDER_VIEW_HEIGHT(iy)
    jr c, _fwk_trm_preflight_row

    xor a
    ld (_fwk_trm_row), a
_fwk_trm_render_row:
    xor a
    ld (_fwk_trm_column), a
_fwk_trm_render_column:
    call _fwk_trm_get_tile
    call _fwk_trm_draw_tile
    ld a, (_fwk_trm_column)
    inc a
    ld (_fwk_trm_column), a
    cp FWK_TILE_RENDER_VIEW_WIDTH(iy)
    jr c, _fwk_trm_render_column
    ld a, (_fwk_trm_row)
    inc a
    ld (_fwk_trm_row), a
    cp FWK_TILE_RENDER_VIEW_HEIGHT(iy)
    jr c, _fwk_trm_render_row
    or a
    ret

;; fwk_tilemap_render_cell_masked
fwk_tilemap_render_cell_masked::
    ld a, b
    ld (_fwk_trm_row), a
    ld a, c
    ld (_fwk_trm_column), a
    call _fwk_trm_validate
    ret c
    ld a, (_fwk_trm_row)
    cp FWK_TILE_RENDER_VIEW_HEIGHT(iy)
    jp nc, _fwk_trm_invalid
    ld a, (_fwk_trm_column)
    cp FWK_TILE_RENDER_VIEW_WIDTH(iy)
    jp nc, _fwk_trm_invalid
    call _fwk_trm_get_tile
    ret c
    call _fwk_trm_draw_tile
    or a
    ret

_fwk_trm_validate:
    ; reuse tilemap_render validation by calling? It's not exported. Duplicate minimal:
    ld a, FWK_TILEMAP_WIDTH(ix)
    or a
    jp z, _fwk_trm_invalid
    ld a, FWK_TILEMAP_HEIGHT(ix)
    or a
    jp z, _fwk_trm_invalid
    ld a, FWK_TILEMAP_X_SIZE(ix)
    or a
    jp z, _fwk_trm_invalid
    ld a, FWK_TILEMAP_Y_SIZE(ix)
    or a
    jp z, _fwk_trm_invalid
    ld a, FWK_TILE_RENDER_VIEW_WIDTH(iy)
    or a
    jp z, _fwk_trm_invalid
    ld a, FWK_TILE_RENDER_VIEW_HEIGHT(iy)
    or a
    jp z, _fwk_trm_invalid
    ld a, FWK_TILE_RENDER_TILE_COUNT(iy)
    or a
    jp z, _fwk_trm_invalid
    ; camera bounds
    ld a, FWK_TILE_RENDER_CAMERA_X(iy)
    add FWK_TILE_RENDER_VIEW_WIDTH(iy)
    jp c, _fwk_trm_invalid
    cp FWK_TILEMAP_WIDTH(ix)
    jr c, _fwk_trm_cam_y
    jp nz, _fwk_trm_invalid
_fwk_trm_cam_y:
    ld a, FWK_TILE_RENDER_CAMERA_Y(iy)
    add FWK_TILE_RENDER_VIEW_HEIGHT(iy)
    jp c, _fwk_trm_invalid
    cp FWK_TILEMAP_HEIGHT(ix)
    jr c, _fwk_trm_screen_w
    jp nz, _fwk_trm_invalid
_fwk_trm_screen_w:
    ld a, FWK_TILE_RENDER_SCREEN_X(iy)
    ld b, FWK_TILE_RENDER_VIEW_WIDTH(iy)
_fwk_trm_width_loop:
    add FWK_TILEMAP_X_SIZE(ix)
    jp c, _fwk_trm_invalid
    djnz _fwk_trm_width_loop
    ld b, a
    ld a, (fwk_video_width_bytes)
    cp b
    jp c, _fwk_trm_invalid
    ; tile area
    ld e, FWK_TILEMAP_X_SIZE(ix)
    ld d, #0
    ld b, FWK_TILEMAP_Y_SIZE(ix)
    ld hl, #0
_fwk_trm_area_loop:
    add hl, de
    jp c, _fwk_trm_invalid
    djnz _fwk_trm_area_loop
    ld (_fwk_trm_tile_area), hl
    ; screen bottom
    ld e, FWK_TILEMAP_Y_SIZE(ix)
    ld d, #0
    ld b, FWK_TILE_RENDER_VIEW_HEIGHT(iy)
    ld hl, #0
_fwk_trm_height_loop:
    add hl, de
    jp c, _fwk_trm_invalid
    djnz _fwk_trm_height_loop
    ld e, FWK_TILE_RENDER_SCREEN_Y(iy)
    ld d, FWK_TILE_RENDER_SCREEN_Y+1(iy)
    add hl, de
    jp c, _fwk_trm_invalid
    ld de, (fwk_video_height)
    or a
    sbc hl, de
    jr c, _fwk_trm_valid
    jp nz, _fwk_trm_invalid
_fwk_trm_valid:
    or a
    ret
_fwk_trm_invalid:
    scf
    ret

_fwk_trm_get_tile:
    ld a, FWK_TILE_RENDER_CAMERA_Y(iy)
    ld b, a
    ld a, (_fwk_trm_row)
    add b
    ld b, a
    ld e, FWK_TILEMAP_WIDTH(ix)
    ld d, #0
    ld hl, #0
    ld a, b
    or a
    jr z, _fwk_trm_map_row_ready
_fwk_trm_map_row_loop:
    add hl, de
    djnz _fwk_trm_map_row_loop
_fwk_trm_map_row_ready:
    ld a, FWK_TILE_RENDER_CAMERA_X(iy)
    ld e, a
    ld a, (_fwk_trm_column)
    add e
    ld e, a
    ld d, #0
    add hl, de
    ld e, FWK_TILEMAP_DATA(ix)
    ld d, FWK_TILEMAP_DATA+1(ix)
    add hl, de
    ld a, (hl)
    cp FWK_TILE_RENDER_TILE_COUNT(iy)
    jp nc, _fwk_trm_invalid
    ld (_fwk_trm_tile_id), a
    or a
    ret

_fwk_trm_draw_tile:
    ; data graphics
    ld l, FWK_TILE_RENDER_TILESET(iy)
    ld h, FWK_TILE_RENDER_TILESET+1(iy)
    ld de, (_fwk_trm_tile_area)
    ld a, (_fwk_trm_tile_id)
    or a
    jr z, _fwk_trm_graphics_ready
    ld b, a
_fwk_trm_graphics_loop:
    add hl, de
    djnz _fwk_trm_graphics_loop
_fwk_trm_graphics_ready:
    ld (_fwk_trm_graphics), hl

    ; mask graphics (parallel tileset)
    ld hl, (_fwk_trm_mask_tileset)
    ld de, (_fwk_trm_tile_area)
    ld a, (_fwk_trm_tile_id)
    or a
    jr z, _fwk_trm_mask_ready
    ld b, a
_fwk_trm_mask_loop:
    add hl, de
    djnz _fwk_trm_mask_loop
_fwk_trm_mask_ready:
    ld (_fwk_trm_mask), hl

    ; screen x
    ld a, FWK_TILE_RENDER_SCREEN_X(iy)
    ld e, FWK_TILEMAP_X_SIZE(ix)
    ld a, (_fwk_trm_column)
    ld b, a
    ld a, FWK_TILE_RENDER_SCREEN_X(iy)
    inc b
    dec b
    jr z, _fwk_trm_x_ready
_fwk_trm_x_loop:
    add e
    djnz _fwk_trm_x_loop
_fwk_trm_x_ready:
    ld (_fwk_trm_screen_x), a

    ; screen y
    ld l, FWK_TILE_RENDER_SCREEN_Y(iy)
    ld h, FWK_TILE_RENDER_SCREEN_Y+1(iy)
    ld e, FWK_TILEMAP_Y_SIZE(ix)
    ld d, #0
    ld a, (_fwk_trm_row)
    ld b, a
    inc b
    dec b
    jr z, _fwk_trm_y_ready
_fwk_trm_y_loop:
    add hl, de
    djnz _fwk_trm_y_loop
_fwk_trm_y_ready:
    ld (_fwk_trm_screen_y), hl
    ld a, FWK_TILEMAP_Y_SIZE(ix)
    ld (_fwk_trm_lines), a

_fwk_trm_line_loop:
    ld hl, (_fwk_trm_screen_y)
    ld a, (_fwk_trm_screen_x)
    ld c, a
    call fwk_video_get_ptr
    ex de, hl
    ld hl, (_fwk_trm_graphics)
    ld (_fwk_trm_gptr), hl
    ld hl, (_fwk_trm_mask)
    ld (_fwk_trm_mptr), hl
    ld a, FWK_TILEMAP_X_SIZE(ix)
    ld (_fwk_trm_width), a
    ld (_fwk_trm_count), a

_fwk_trm_byte_loop:
    ld a, (_fwk_trm_count)
    or a
    jr z, _fwk_trm_line_done
    ld hl, (_fwk_trm_mptr)
    ld a, (hl)
    ld b, a
    ld a, (de)
    and b
    ld c, a
    ld hl, (_fwk_trm_gptr)
    ld a, (hl)
    or c
    ld (de), a
    ld hl, (_fwk_trm_gptr)
    inc hl
    ld (_fwk_trm_gptr), hl
    ld hl, (_fwk_trm_mptr)
    inc hl
    ld (_fwk_trm_mptr), hl
    inc de
    ld a, (_fwk_trm_count)
    dec a
    ld (_fwk_trm_count), a
    jr _fwk_trm_byte_loop

_fwk_trm_line_done:
    ld hl, (_fwk_trm_screen_y)
    inc hl
    ld (_fwk_trm_screen_y), hl
    ld a, (_fwk_trm_lines)
    dec a
    ld (_fwk_trm_lines), a
    jr nz, _fwk_trm_line_loop
    or a
    ret
