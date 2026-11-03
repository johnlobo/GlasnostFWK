;; Shared constants for the platformer tutorial example.

;; Offsets inside the compact 7-byte player state.
PF_PLAYER_X       = 0
PF_PLAYER_Y       = 1
PF_PLAYER_VX      = 2
PF_PLAYER_VY      = 3
PF_PLAYER_WIDTH   = 4
PF_PLAYER_HEIGHT  = 5
PF_PLAYER_FLAGS   = 6
PF_PLAYER_SIZE    = 7

;; Player size in bytes and pixels, plus the spawn position.
PF_PLAYER_WIDTH_BYTES = 8
PF_PLAYER_HEIGHT_PX   = 8
PF_PLAYER_START_X     = 16
PF_PLAYER_START_Y     = 184

;; Enemy sprite size and patrol limits.
PF_ENEMY_WIDTH_BYTES  = 4
PF_ENEMY_HEIGHT_PX    = 8
PF_ENEMY_H_START_X    = 36
PF_ENEMY_H_Y          = 122
PF_ENEMY_H_MIN_X      = 32
PF_ENEMY_H_MAX_X      = 54
;; WAIT switches direction on its terminal tick, before motion is applied.
PF_ENEMY_H_INITIAL_TICKS = 19  ;; 18 moves: initial X 36 -> right edge 54
PF_ENEMY_H_LEG_TICKS     = 23  ;; 22 moves: complete 32 <-> 54 leg
PF_ENEMY_V_X          = 64
PF_ENEMY_V2_X         = 8
PF_ENEMY_V_START_Y    = 56
PF_ENEMY_V_MIN_Y      = 56
PF_ENEMY_V_MAX_Y      = 152
;; 49 ticks therefore produce 48 movements of two pixels: 56 <-> 152.
PF_ENEMY_V_LEG_TICKS = 49
PF_LIVES_INITIAL      = 10
PF_RENDER_COUNT       = 9

;; Input action bits and tile-grounded flag.
PF_INPUT_LEFT     = 0x01
PF_INPUT_RIGHT    = 0x02
PF_INPUT_JUMP     = 0x04
PF_TILE_GROUNDED = 0x02

;; Physics and coin tuning.
PF_SPEED          = 2
PF_JUMP_SPEED     = -8
PF_COIN_COUNT     = 4
PF_COIN_ENTITY    = 3
PF_COIN_STRIDE    = 5
PF_COIN_REMOVED   = 0xFF
PF_WIN_SCORE      = 4

;; HUD vertical position in scanlines (top of the text row).
PF_HUD_Y          = 10

;; HUD text positions (byte column and scanline row).
PF_HUD_COINS_X    = 0
PF_HUD_COINS_Y    = PF_HUD_Y
PF_HUD_HINT_X     = 24
PF_HUD_HINT_Y     = PF_HUD_Y
PF_HUD_LIVES_X    = 64
PF_HUD_LIVES_Y    = PF_HUD_Y
PF_STATUS_READY   = 0xA5
PF_STATUS_WON     = 0x5A

PF_HUD_DIRTY_SCORE = 0x01
PF_HUD_DIRTY_LIVES = 0x02
