.module example_mode1
.include "cpctelera.h.s"
.include "video/sprite.inc"
.include "assets/generated/assets.inc"

.globl fwk_project_init
.globl fwk_input_init, fwk_input_set_bindings, fwk_input_update, fwk_input_held
.globl fwk_video_init, fwk_video_configure_crtc, fwk_video_clear_visible, fwk_video_get_ptr
.globl cpct_setPalette_asm, cpct_waitVSYNCStart_asm
.globl mode1_palette, mode1_ship_pixels, mode1_star_pixels
.globl fwk_text_init, fwk_text_set_color, fwk_text_draw
.globl fwk_text_draw_small_u8

.area _DATA
mode1_bindings:
    .dw Key_O
    .db 0x01
    .dw Key_P
    .db 0x02
    .dw Key_Q
    .db 0x04
    .dw Key_A
    .db 0x08
    .dw 0
    .db 0

;; Sprite positions are video bytes (4 Mode 1 pixels), then scanlines.
FWK_SPRITE_DESCRIPTOR mode1_ship, mode1_ship_pixels, 22, 88, 4, 16
FWK_SPRITE_DESCRIPTOR mode1_star_tl, mode1_star_pixels, 1, 8, 4, 16
FWK_SPRITE_DESCRIPTOR mode1_star_tr, mode1_star_pixels, 43, 8, 4, 16
FWK_SPRITE_DESCRIPTOR mode1_star_bl, mode1_star_pixels, 1, 168, 4, 16
FWK_SPRITE_DESCRIPTOR mode1_star_br, mode1_star_pixels, 43, 168, 4, 16

mode1_status:: .db 0
mode1_title: .asciz "MODE 1 192X192"

.area _CODE

;; ----------------------------------------------------------------------------
;; mode1_border_row
;;   Draws a full-width white scanline.
;;   In : HL = visible row (0..191).
;;   Out: video RAM at that row contains pen 3.
;;   Clobbers: AF, BC, DE, HL, flags.
;;   Notes: Calls fwk_video_get_ptr with byte X = 0.
;; ----------------------------------------------------------------------------
mode1_border_row:
    ld c, #0
    call fwk_video_get_ptr
    ld b, #48
    ld a, #0xFF              ;; Four pen-3 pixels per byte.
mode1_border_row_loop:
    ld (hl), a
    inc hl
    djnz mode1_border_row_loop
    ret

;; ----------------------------------------------------------------------------
;; mode1_draw_border
;;   Marks all four edges of the 48-byte by 192-line viewport.
;;   In : none.
;;   Out: video RAM has a white border.
;;   Clobbers: AF, BC, DE, HL, flags.
;;   Notes: Writes rows 0 and 191 and the first and last bytes of inner rows.
;; ----------------------------------------------------------------------------
mode1_draw_border:
    ld hl, #0
    call mode1_border_row
    ld hl, #191
    call mode1_border_row
    ld hl, #1
mode1_border_sides:
    push hl
    ld c, #0
    call fwk_video_get_ptr
    ld a, #0xFF
    ld (hl), a
    ld de, #47
    add hl, de
    ld (hl), a
    pop hl
    inc hl
    ld a, l
    cp #191
    jr nz, mode1_border_sides
    ret

;; ----------------------------------------------------------------------------
;; mode1_erase_ship
;;   Restores the blue background beneath the moving ship.
;;   In : mode1_ship X and Y positions.
;;   Out: video RAM beneath the ship contains pen 1.
;;   Clobbers: AF, BC, DE, HL, flags.
;;   Notes: The ship stays away from the stars and border; erase only on motion.
;; ----------------------------------------------------------------------------
mode1_erase_ship:
    ld hl, (mode1_ship + FWK_SPRITE_Y)
    ld b, #16
mode1_erase_row:
    push bc
    push hl
    ld a, (mode1_ship + FWK_SPRITE_X)
    ld c, a
    call fwk_video_get_ptr
    ld a, #0xF0
    ld (hl), a
    inc hl
    ld (hl), a
    inc hl
    ld (hl), a
    inc hl
    ld (hl), a
    pop hl
    inc hl
    pop bc
    djnz mode1_erase_row
    ret

;; ----------------------------------------------------------------------------
;; mode1_move_ship
;;   Moves the ship one step according to held O/P/Q/A keys.
;;   In : fwk_input_held and mode1_ship X and Y positions.
;;   Out: updated ship position in its descriptor.
;;   Clobbers: AF, BC, HL, flags.
;;   Notes: X advances by four pixels and Y by one scanline within the inner area.
;; ----------------------------------------------------------------------------
mode1_move_ship:
    ld a, (fwk_input_held)
    ld b, a
    bit 0, b
    jr z, mode1_move_right
    ld hl, #mode1_ship + FWK_SPRITE_X
    ld a, (hl)
    cp #5
    jr z, mode1_move_right
    dec (hl)
mode1_move_right:
    bit 1, b
    jr z, mode1_move_up
    ld hl, #mode1_ship + FWK_SPRITE_X
    ld a, (hl)
    cp #39
    jr z, mode1_move_up
    inc (hl)
mode1_move_up:
    bit 2, b
    jr z, mode1_move_down
    ld hl, #mode1_ship + FWK_SPRITE_Y
    ld a, (hl)
    cp #24
    jr z, mode1_move_down
    dec (hl)
mode1_move_down:
    bit 3, b
    ret z
    ld hl, #mode1_ship + FWK_SPRITE_Y
    ld a, (hl)
    cp #151
    ret z
    inc (hl)
    ret

mode1_fail:
    ld a, #0xEE
    ld (mode1_status), a
mode1_fail_loop:
    call cpct_waitVSYNCStart_asm
    jr mode1_fail_loop

_main::
    call fwk_project_init
    call fwk_video_init
    call fwk_video_configure_crtc
    ld hl, #mode1_palette
    ld de, #MODE1_PALETTE_SIZE
    call cpct_setPalette_asm
    call fwk_input_init
    ld hl, #mode1_bindings
    call fwk_input_set_bindings
    call fwk_text_init

    ld a, #0xF0              ;; Four pen-1 (blue) pixels per byte.
    call fwk_video_clear_visible
    call mode1_draw_border
    ld ix, #mode1_star_tl
    call fwk_sprite_draw_masked
    jp c, mode1_fail
    ld ix, #mode1_star_tr
    call fwk_sprite_draw_masked
    jp c, mode1_fail
    ld ix, #mode1_star_bl
    call fwk_sprite_draw_masked
    jp c, mode1_fail
    ld ix, #mode1_star_br
    call fwk_sprite_draw_masked
    jp c, mode1_fail

    ;; Static HUD stays below the ship's movement range and between the stars.
    ld a, #3                 ;; White foreground pen.
    call fwk_text_set_color
    jp c, mode1_fail
    ld hl, #174
    ld c, #17
    call fwk_video_get_ptr
    ld iy, #mode1_title
    call fwk_text_draw
    ld a, #2                 ;; Yellow small digits.
    call fwk_text_set_color
    jp c, mode1_fail
    ld hl, #184
    ld c, #23
    call fwk_video_get_ptr
    ld a, #255
    call fwk_text_draw_small_u8

    ld ix, #mode1_ship
    call fwk_sprite_draw_masked
    jp c, mode1_fail
    ld a, #0x5A
    ld (mode1_status), a

mode1_frame:
    ;; Wait for the start of a new VSYNC, even if the previous one is still
    ;; active. This gives each update a consistent raster position.
    call cpct_waitVSYNCStart_asm
    call fwk_input_update
    ld a, (fwk_input_held)
    and #0x0F
    jr z, mode1_frame
    call mode1_erase_ship
    call mode1_move_ship
    ld ix, #mode1_ship
    call fwk_sprite_draw_masked
    jp c, mode1_fail
    jr mode1_frame
