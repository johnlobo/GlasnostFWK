.module game_main
;; Minimal project on GlasnostFWK: only the main loop and a welcome message.
;; Replace this with your own game.
.include "common.inc"
.include "generated/project.inc"

.area _DATA
game_status::  .db 0              ; 0x5A once the game is running, else the ABI error code

_game_str_welcome: .asciz "WELCOME"
_game_str_help:    .asciz "START CODING!"

;; Palette: 16 hardware colours.
_game_palette:
    .db 0x14, 0x0A, 0x00, 0x1C, 0x0C, 0x0E, 0x0A, 0x07, 0x16, 0x1E, 0x13, 0x1F, 0x15, 0x18, 0x04, 0x0B

.area _CODE

_main::
    call fwk_project_init
    call fwk_video_init
    call fwk_text_init
    ld hl, #_game_palette
    ld de, #16
    call cpct_setPalette_asm
    xor a
    call fwk_video_clear_visible

    ;; Draw the welcome message.
    ld b, #MINIMAL_TEXT_Y_WELCOME
    ld hl, #_game_str_welcome
    call _minimal_text
    ld b, #MINIMAL_TEXT_Y_HELP
    ld hl, #_game_str_help
    call _minimal_text

    ld a, #0x5A
    ld (game_status), a             ; 0x5A = OK; any other value is an ABI error code.

game_frame:
    call fwk_system_wait_frame
    jp game_frame

;; In: B=scanline, HL=string. Draws it at the left margin.
_minimal_text:
    push hl
    ld l, b
    ld h, #0
    ld c, #MINIMAL_TEXT_X
    call fwk_video_get_ptr
    pop iy
    jp fwk_text_draw