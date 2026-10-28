.module example_platformer_assets
.include "cpctelera.h.s"

.area _DATA
platformer_types:
    .db 0, 1, 2, 0

; 10x25 map (8x8-byte tiles = 160x200 Mode 0 pixels = full screen)
platformer_map:
    .db 1,1,1,1,1,1,1,1,1,1
    .db 1,0,0,0,0,0,0,0,0,1
    .db 1,0,0,0,0,0,0,0,0,1
    .db 1,0,0,0,0,0,0,0,0,1
    .db 1,0,2,2,2,2,2,2,0,1
    .db 1,0,0,0,0,0,0,0,0,1
    .db 1,0,0,0,0,0,0,0,0,1
    .db 1,0,0,0,0,0,0,0,0,1
    .db 1,0,0,0,2,2,2,0,0,1
    .db 1,0,0,0,0,0,0,0,0,1
    .db 1,0,0,0,0,0,0,0,0,1
    .db 1,0,0,0,0,0,0,0,0,1
    .db 1,0,0,0,2,2,2,0,0,1
    .db 1,0,0,0,0,0,0,0,0,1
    .db 1,0,0,0,0,0,0,0,0,1
    .db 1,0,0,0,0,0,0,0,0,1
    .db 1,0,0,0,2,2,2,0,0,1
    .db 1,0,0,0,0,0,0,0,0,1
    .db 1,0,0,0,0,0,0,0,0,1
    .db 1,0,0,0,0,0,0,0,0,1
    .db 1,0,0,0,2,2,2,0,0,1
    .db 1,0,0,0,0,0,0,0,0,1
    .db 1,0,0,0,0,0,0,0,0,1
    .db 1,0,0,0,0,0,0,0,0,1
    .db 1,2,2,2,2,2,2,2,2,1

platformer_map_descriptor::
    .dw platformer_map, platformer_types
    .db 10, 25, 3, 3, 8, 8, 4

platformer_tileset:
    .rept 64
        .db 0x00
    .endm
    .rept 64
        .db 0x55
    .endm
    .rept 64
        .db 0xF0
    .endm
    .rept 64
        .db 0x0F
    .endm

platformer_view::
    .dw platformer_tileset
    .db 0, 0, 0
    .dw 0
    .db 10, 25, 4

platformer_player_pixels:
    .rept 8
        .db 0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF,0xFF
    .endm

platformer_player_sprite::
    .dw platformer_player_pixels
    .dw 0, 0
    .db 8, 8

platformer_coin_pixels:
    .rept 8
        .db 0x00,0xAA,0xAA,0xAA,0xAA,0xAA,0xAA,0x00
    .endm

platformer_coin_sprite::
    .dw platformer_coin_pixels
    .dw 0, 0
    .db 8, 8

platformer_config::
    ;; Tile collision owns the visible floor; 255 is only the profile safety bound.
    .db 80, 255, 1, 8

platformer_bindings::
    .dw Key_CursorLeft
    .db 0x01
    .dw Key_CursorRight
    .db 0x02
    .dw Key_CursorUp
    .db 0x04
    .dw 0
    .db 0

platformer_coins::
    .db 2,3,1, 7,3,1, 2,21,1, 7,21,1
