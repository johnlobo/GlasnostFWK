.include "extensions/tilemap.inc"

FWK_TILE_RENDER_TILESET = 0
FWK_TILE_RENDER_CAMERA_X = 2
FWK_TILE_RENDER_CAMERA_Y = 3
FWK_TILE_RENDER_SCREEN_X = 4
FWK_TILE_RENDER_SCREEN_Y = 5
FWK_TILE_RENDER_VIEW_WIDTH = 7
FWK_TILE_RENDER_VIEW_HEIGHT = 8
FWK_TILE_RENDER_TILE_COUNT = 9
FWK_TILE_RENDER_DESCRIPTOR_SIZE = 10

.macro FWK_TILE_RENDER_DESCRIPTOR label, tileset, camera_x, camera_y, screen_x, screen_y, view_width, view_height, tile_count
label:
    .dw tileset
    .db camera_x, camera_y, screen_x
    .dw screen_y
    .db view_width, view_height, tile_count
.endm
