;; Game-owned embedded resources for the playable vertical slice.
.module example_vertical_assets

.area _CODE

;; Count followed by x,y pairs. Kept separate from game logic so a future
;; asset generator can replace this source without changing the game loop.
vertical_pickup_spawns::
    .db 3
    .db 20, 100
    .db 30, 100
    .db 40, 100

;; Mode 0 packed bytes: player, pickup and player-after-winning.
vertical_sprite_bytes::
    .db 0xFF, 0x3C, 0xF3
