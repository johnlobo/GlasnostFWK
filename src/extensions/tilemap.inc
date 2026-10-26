FWK_TILEMAP_DATA = 0
FWK_TILEMAP_TYPES = 2
FWK_TILEMAP_WIDTH = 4
FWK_TILEMAP_HEIGHT = 5
FWK_TILEMAP_X_SHIFT = 6
FWK_TILEMAP_Y_SHIFT = 7
FWK_TILEMAP_X_SIZE = 8
FWK_TILEMAP_Y_SIZE = 9
FWK_TILEMAP_TYPE_COUNT = 10
FWK_TILEMAP_DESCRIPTOR_SIZE = 11

FWK_TILE_PASSABLE = 0
FWK_TILE_SOLID = 1
FWK_TILE_ONE_WAY = 2

.macro FWK_TILEMAP_DESCRIPTOR label, data, types, width, height, x_shift, y_shift, x_size, y_size, type_count
label:
    .dw data, types
    .db width, height, x_shift, y_shift, x_size, y_size, type_count
.endm
