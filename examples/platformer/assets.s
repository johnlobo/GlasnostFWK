.module example_platformer_assets
.include "cpctelera.h.s"
.include "video/sprite.inc"
.include "game/game.inc"

.area _DATA

;; Tile behaviours: empty, solid, one-way platform and decorative/non-solid.
platformer_types:
    .db 0, 1, 2, 0

;; 20x25 cells. A CPCTelera 4x8-byte tile maps to 8x8 Mode 0 pixels, therefore
;; the viewport covers the standard 160x200 screen exactly.
platformer_map:
    .db 1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1
    .db 1,1,0,0,0,0,0,0,3,3,0,0,0,0,0,0,0,0,1,1
    .db 1,1,0,0,0,0,0,0,0,0,0,0,0,0,3,3,0,0,1,1
    .db 1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1
    .db 1,1,0,0,2,2,2,2,2,2,2,2,2,2,2,2,0,0,1,1
    .db 1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1
    .db 1,1,0,0,3,3,0,0,0,0,0,0,0,0,0,0,0,0,1,1
    .db 1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1
    .db 1,1,0,0,0,0,0,0,2,2,2,2,2,2,0,0,0,0,1,1
    .db 1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1
    .db 1,1,0,0,0,0,3,3,0,0,0,0,0,0,0,0,0,0,1,1
    .db 1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1
    .db 1,1,0,0,0,0,0,0,2,2,2,2,2,2,0,0,0,0,1,1
    .db 1,1,0,0,0,0,0,0,0,0,0,0,0,0,3,3,0,0,1,1
    .db 1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1
    .db 1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1
    .db 1,1,0,0,0,0,0,0,2,2,2,2,2,2,0,0,0,0,1,1
    .db 1,1,0,0,3,3,0,0,0,0,0,0,0,0,0,0,0,0,1,1
    .db 1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1
    .db 1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1
    .db 1,1,0,0,0,0,0,0,2,2,2,2,2,2,0,0,0,0,1,1
    .db 1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1
    .db 1,1,0,0,0,0,0,0,0,0,0,0,0,0,3,3,0,0,1,1
    .db 1,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,1,1
    .db 1,1,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,1,1

platformer_map_descriptor::
    .dw platformer_map, platformer_types
    .db 20, 25, 2, 3, 4, 8, 4

platformer_tileset:
platformer_tile_empty:
    .rept 32
        .db 0x00
    .endm

platformer_tile_solid:
    .db 0x55,0x55,0xAA,0xAA
    .db 0x55,0x55,0xAA,0xAA
    .db 0xAA,0xAA,0x55,0x55
    .db 0xAA,0xAA,0x55,0x55
    .db 0x55,0x55,0xAA,0xAA
    .db 0x55,0x55,0xAA,0xAA
    .db 0xAA,0xAA,0x55,0x55
    .db 0xAA,0xAA,0x55,0x55

platformer_tile_one_way:
    .db 0xFF,0xFF,0xFF,0xFF
    .db 0xAA,0xAA,0xAA,0xAA
    .db 0x00,0x11,0x00,0x11
    .db 0x00,0x00,0x11,0x00
    .db 0x00,0x11,0x11,0x00
    .db 0x00,0x11,0x11,0x00
    .db 0x00,0x00,0x00,0x00
    .db 0x00,0x00,0x00,0x00

platformer_tile_star:
    .db 0x00,0x00,0x00,0x00
    .db 0x00,0x30,0x30,0x00
    .db 0x30,0xFC,0xFC,0x30
    .db 0x00,0x30,0x30,0x00
    .db 0x10,0x20,0x10,0x20
    .db 0x00,0x00,0x00,0x00
    .db 0x00,0x00,0x00,0x00
    .db 0x00,0x00,0x00,0x00

platformer_view::
    .dw platformer_tileset
    .db 0, 0, 0
    .dw 0
    .db 20, 25, 4

;; Opaque sprites deliberately contain their own black silhouette. The player
;; still captures/restores the background every frame.
platformer_player_pixels:
    .db 0x00,0x00,0x3C,0x3C,0x3C,0x3C,0x00,0x00
    .db 0x00,0x3C,0xFF,0xFF,0xFF,0xFF,0x3C,0x00
    .db 0x00,0x3C,0xCF,0xFF,0xFF,0xCF,0x3C,0x00
    .db 0x00,0x00,0xFF,0xFF,0xFF,0xFF,0x00,0x00
    .db 0x00,0x3C,0x3C,0xFF,0xFF,0x3C,0x3C,0x00
    .db 0x3C,0x00,0x3C,0xFF,0xFF,0x3C,0x00,0x3C
    .db 0x00,0x00,0x3C,0x00,0x00,0x3C,0x00,0x00
    .db 0x00,0x3C,0x3C,0x00,0x00,0x3C,0x3C,0x00

platformer_player_sprite::
    .dw platformer_player_pixels
    .dw 0, 0
    .db PF_PLAYER_WIDTH_BYTES, PF_PLAYER_HEIGHT_PX

platformer_coin_pixels:
    .db 0x00,0xAA,0xAA,0x00
    .db 0x00,0xFF,0xFF,0x00
    .db 0xAA,0x55,0x55,0xAA
    .db 0xAA,0xFF,0xFF,0xAA
    .db 0xAA,0xFF,0xFF,0xAA
    .db 0x00,0xFF,0xFF,0x00
    .db 0x00,0xAA,0xAA,0x00
    .db 0x00,0x00,0x00,0x00

platformer_coin_sprite::
    .dw platformer_coin_pixels
    .dw 0, 0
    .db 4, 8

platformer_config::
    ;; Tile collision owns the visible floor; 255 is only a safety bound.
    .db 80, 255, 1, 8

platformer_bindings::
    .dw Key_CursorLeft
    .db PF_INPUT_LEFT
    .dw Key_CursorRight
    .db PF_INPUT_RIGHT
    .dw Key_CursorUp
    .db PF_INPUT_JUMP
    .dw 0
    .db 0

;; x tile, y tile, kind. Kind is reserved for future collectible variants.
platformer_coins::
    .db 4,3,1, 14,3,1, 4,21,1, 14,21,1
