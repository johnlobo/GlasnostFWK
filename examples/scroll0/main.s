;; Four-way camera baseline for the 128x128 scroll experiment.
.module example_scroll
.include "cpctelera.h.s"
.include "video/sprite.inc"
.include "extensions/tilemap_render.inc"

.globl fwk_project_init, fwk_system_wait_frame
.globl fwk_input_init, fwk_input_set_bindings, fwk_input_update, fwk_input_held, fwk_input_pressed
.globl fwk_video_init, fwk_video_configure_crtc, fwk_video_clear_visible, fwk_video_get_ptr, fwk_video_line_table, fwk_video_origin_bytes
.globl fwk_tilemap_render_view, fwk_tilemap_render_cell, fwk_sprite_capture, fwk_sprite_restore, fwk_sprite_draw
.globl cpct_setPALColour_asm, cpct_setCRTCReg_asm, cpct_waitVSYNCStart_asm, cpct_isKeyPressed_asm

.if FWK_PROJECT_VIDEO_MODE
TILE_BYTE_WIDTH = 2
TILE_X_SHIFT = 1
PLAYER_STEP = 4
PLAYER_BYTE_SHIFT = 2
PLAYER_START_BYTE = 15
VIDEO_ORIGIN_R13 = 0
VIDEO_ORIGIN_ADDRESS = 0xC000
TILE_R13_STEP = 1
ROW_R13_STEP = 16
.else
TILE_BYTE_WIDTH = 4
TILE_X_SHIFT = 2
PLAYER_STEP = 2
PLAYER_BYTE_SHIFT = 1
PLAYER_START_BYTE = 30
VIDEO_ORIGIN_R13 = 0
VIDEO_ORIGIN_ADDRESS = 0xC000
TILE_R13_STEP = 2
ROW_R13_STEP = 32
.endif
VIEW_BYTE_WIDTH = 16*TILE_BYTE_WIDTH

.area _DATA
scroll_bindings:
    .dw Key_O
    .db 1
    .dw Key_P
    .db 2
    .dw Key_Q
    .db 4
    .dw Key_A
    .db 8
    .dw Key_H
    .db 16
    .dw Key_J
    .db 32
    .dw Key_K
    .db 64
    .dw Key_L
    .db 128
    .dw 0
    .db 0

scroll_tile_types: .db FWK_TILE_PASSABLE, FWK_TILE_SOLID, FWK_TILE_PASSABLE, FWK_TILE_PASSABLE
scroll_map:
    .db 3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3
    .db 3,0,0,0,2,0,0,0,2,0,0,0,2,0,0,0,2,0,0,0,2,0,0,3
    .db 3,0,0,0,2,0,0,0,2,0,0,0,2,0,0,0,2,0,0,0,2,0,0,3
    .db 3,0,0,0,2,0,0,0,2,0,0,0,2,0,0,0,2,0,0,0,2,0,0,3
    .db 3,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,3
    .db 3,0,0,0,2,0,0,0,2,0,0,0,2,0,0,0,2,0,0,0,2,0,0,3
    .db 3,0,0,0,2,0,0,0,2,0,0,0,2,0,0,0,2,0,0,0,2,0,0,3
    .db 3,0,0,0,2,0,0,0,2,0,0,0,2,0,0,0,2,0,0,0,2,0,0,3
    .db 3,2,2,2,2,2,2,2,2,2,2,2,1,2,2,2,2,2,2,2,2,2,2,3
    .db 3,0,0,0,2,0,0,0,2,0,0,0,2,0,0,0,2,0,0,0,2,0,0,3
    .db 3,0,0,0,2,0,0,0,2,0,0,0,2,0,0,0,2,0,0,0,2,0,0,3
    .db 3,0,0,0,2,0,0,0,2,0,0,0,2,0,0,0,2,0,0,0,2,0,0,3
    .db 3,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,3
    .db 3,0,0,0,2,0,0,0,2,0,0,0,2,0,0,0,2,0,0,0,2,0,0,3
    .db 3,0,0,0,2,0,0,0,2,0,0,0,2,0,0,0,2,0,0,0,2,0,0,3
    .db 3,0,0,0,2,0,0,0,2,0,0,0,2,0,0,0,2,0,0,0,2,0,0,3
    .db 3,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,3
    .db 3,0,0,0,2,0,0,0,2,0,0,0,2,0,0,0,2,0,0,0,2,0,0,3
    .db 3,0,0,0,2,0,0,0,2,0,0,0,2,0,0,0,2,0,0,0,2,0,0,3
    .db 3,0,0,0,2,0,0,0,2,0,0,0,2,0,0,0,2,0,0,0,2,0,0,3
    .db 3,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,2,3
    .db 3,0,0,0,2,0,0,0,2,0,0,0,2,0,0,0,2,0,0,0,2,0,0,3
    .db 3,0,0,0,2,0,0,0,2,0,0,0,2,0,0,0,2,0,0,0,2,0,0,3
    .db 3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3,3
FWK_TILEMAP_DESCRIPTOR scroll_map_descriptor, scroll_map, scroll_tile_types, 24, 24, TILE_X_SHIFT, 3, TILE_BYTE_WIDTH, 8, 4

scroll_tiles:
    .rept 8*TILE_BYTE_WIDTH
        .db 0x00
    .endm
    .rept 8*TILE_BYTE_WIDTH
        .db 0xAA
    .endm
    .rept TILE_BYTE_WIDTH
        .db 0xFF
    .endm
    .rept 7
        .db 0xFF
        .rept TILE_BYTE_WIDTH-1
            .db 0x00
        .endm
    .endm
    .rept 8*TILE_BYTE_WIDTH
        .db 0xFF
    .endm
scroll_tile_ptrs:
    .dw scroll_tiles, scroll_tiles+8*TILE_BYTE_WIDTH
    .dw scroll_tiles+16*TILE_BYTE_WIDTH, scroll_tiles+24*TILE_BYTE_WIDTH
FWK_TILE_RENDER_DESCRIPTOR scroll_view, scroll_tiles, 4, 4, 0, 0, 16, 16, 4

scroll_probe_pattern:
    .db 0x00,0x58,0xD6,0x42,0x34,0xC4,0xD2,0xBE,0x08,0xF0,0x7E,0x2A,0xFC,0x8C,0xFA,0xB6
    .db 0x90,0xE8,0xA6,0x92,0x24,0xB4,0x62,0xAE,0x98,0xA0,0x8E,0xDA,0xEC,0x9C,0x4A,0x06
    .db 0x20,0x38,0x76,0xA2,0x54,0x64,0x32,0x1E,0x28,0x10,0xDE,0x8A,0x1C,0xAC,0x9A,0xD6
    .db 0xB0,0x88,0x46,0x32,0x44,0x94,0xC2,0x4E,0xB8,0x80,0xEE,0xFA,0x0C,0x7C,0xEA,0x66

scroll_player_pixels:
    .rept 8*TILE_BYTE_WIDTH
        .db 0xFF
    .endm
FWK_SPRITE_DESCRIPTOR scroll_player, scroll_player_pixels, PLAYER_START_BYTE, 60, TILE_BYTE_WIDTH, 8
scroll_player_background: .ds 8*TILE_BYTE_WIDTH

scroll_world_x:: .db 92
scroll_world_y:: .db 92
scroll_screen_x:: .db 60
scroll_screen_y:: .db 60
scroll_camera_x:: .db 4
scroll_camera_y:: .db 4
scroll_status:: .db 0
scroll_blocked:: .db 0
scroll_step_count:: .dw 0
scroll_probe_offset:: .db 0
scroll_zone_x_min:: .db 32
scroll_zone_x_max:: .db 96
scroll_zone_y_min:: .db 32
scroll_zone_y_max:: .db 96
scroll_try_x: .db 0
scroll_try_y: .db 0
scroll_try_camera_x: .db 0
scroll_try_camera_y: .db 0
scroll_probe_y: .db 0
scroll_probe_source: .dw 0
scroll_hw_enabled:: .db 0
scroll_hw_ma:: .dw 0
scroll_hw_chars: .dw 0
scroll_hw_bank: .db 0
scroll_hw_target_ma: .dw 0
scroll_hw_target_bytes: .dw 0
scroll_hw_direction: .db 0
scroll_hw_index: .db 0
scroll_hw_old_sprite_ptrs: .ds 16
scroll_hw_ptr_cursor: .dw 0
scroll_hw_bg_cursor: .dw 0
scroll_hw_sprite_y: .db 0
scroll_hw_xbyte: .db 0
scroll_hw_tile_count: .db 0
scroll_hw_line_start: .dw 0
scroll_smooth_enabled:: .db 0
scroll_smooth_camera_x:: .db 32
scroll_smooth_camera_y:: .db 32
scroll_smooth_try_camera_x: .db 0
scroll_smooth_try_camera_y: .db 0
scroll_smooth_direction: .db 0
scroll_smooth_target_origin: .dw 0
scroll_smooth_source_origin: .dw 0
scroll_smooth_copy_y: .db 0
scroll_smooth_copy_count: .db 0
scroll_smooth_copy_src: .dw 0
scroll_smooth_fill_x: .db 0
scroll_smooth_fill_y: .db 0
scroll_smooth_fill_limit: .db 0
scroll_smooth_tile_x: .db 0
scroll_smooth_raster: .db 0
scroll_smooth_source_byte: .db 0
scroll_smooth_sprite_x: .db 0
scroll_smooth_sprite_y: .db 0
scroll_smooth_sprite_count: .db 0
scroll_smooth_bg_ptr: .dw 0

.area _CODE

;; ----------------------------------------------------------------------------
;; scroll_collision
;;   Tests the proposed 8x8 player box against the three fixture blockers.
;;   In : scroll_try_x, scroll_try_y = proposed top-left in world pixels.
;;   Out: carry set when blocked, clear when free.
;;   Clobbers: AF
;;   Notes: Hard-coded boxes: solid tile [96,104)x[64,72), object [96,112)x[128,136), character [128,136)x[96,104).
;; ----------------------------------------------------------------------------
scroll_collision:
    ;; Solid tile [96,104) x [64,72).
    ld a, (scroll_try_x)
    cp #104
    jr nc, scroll_collision_object
    add #8
    cp #97
    jr c, scroll_collision_object
    ld a, (scroll_try_y)
    cp #72
    jr nc, scroll_collision_object
    add #8
    cp #65
    jr nc, scroll_collision_blocked
scroll_collision_object:
    ;; Blocking object [96,112) x [128,136).
    ld a, (scroll_try_x)
    cp #112
    jr nc, scroll_collision_character
    add #8
    cp #97
    jr c, scroll_collision_character
    ld a, (scroll_try_y)
    cp #136
    jr nc, scroll_collision_character
    add #8
    cp #129
    jr nc, scroll_collision_blocked
scroll_collision_character:
    ;; Other character [128,136) x [96,104).
    ld a, (scroll_try_x)
    cp #136
    jr nc, scroll_collision_clear
    add #8
    cp #129
    jr c, scroll_collision_clear
    ld a, (scroll_try_y)
    cp #104
    jr nc, scroll_collision_clear
    add #8
    cp #97
    jr nc, scroll_collision_blocked
scroll_collision_clear:
    or a
    ret
scroll_collision_blocked:
    scf
    ret

;; Move the proposed camera by tiles until the player center is in the zone,
;; unless the map edge has clamped that axis.
scroll_follow:
scroll_follow_x:
    ld a, (scroll_try_camera_x)
    add a, a
    add a, a
    add a, a
    ld b, a
    ld a, (scroll_try_x)
    add #4
    sub b
    ld b, a
    ld a, (scroll_zone_x_max)
    cp b
    jr z, scroll_follow_x_inc
    jr nc, scroll_follow_x_low
scroll_follow_x_inc:
    ld a, (scroll_try_camera_x)
    cp #8
    jr z, scroll_follow_y
    inc a
    ld (scroll_try_camera_x), a
    jr scroll_follow_x
scroll_follow_x_low:
    ld a, (scroll_zone_x_min)
    cp b
    jr c, scroll_follow_y
    jr z, scroll_follow_y
    ld a, (scroll_try_camera_x)
    or a
    jr z, scroll_follow_y
    dec a
    ld (scroll_try_camera_x), a
    jr scroll_follow_x
scroll_follow_y:
    ld a, (scroll_try_camera_y)
    add a, a
    add a, a
    add a, a
    ld b, a
    ld a, (scroll_try_y)
    add #4
    sub b
    ld b, a
    ld a, (scroll_zone_y_max)
    cp b
    jr z, scroll_follow_y_inc
    jr nc, scroll_follow_y_low
scroll_follow_y_inc:
    ld a, (scroll_try_camera_y)
    cp #8
    ret z
    inc a
    ld (scroll_try_camera_y), a
    jr scroll_follow_y
scroll_follow_y_low:
    ld a, (scroll_zone_y_min)
    cp b
    ret c
    ret z
    ld a, (scroll_try_camera_y)
    or a
    ret z
    dec a
    ld (scroll_try_camera_y), a
    jr scroll_follow_y

;; ----------------------------------------------------------------------------
;; scroll_move
;;   Moves the player one step in the single held direction (O/P/Q/A), checks limits and blockers, follows with the camera and redraws.
;;   In : fwk_input_held (exactly one of bits 0..3), scroll_world_*, scroll_camera_*.
;;   Out: world, screen and camera positions updated and scroll_step_count + 1; scroll_blocked = 1 when refused; scroll_status = 0xEE when a redraw fails.
;;   Clobbers: AF, BC, DE, HL, IX, IY
;;   Notes: Several keys at once do nothing. Smooth mode continues in scroll_smooth_move; hardware mode redraws through scroll_hw_redraw, otherwise the full view is drawn.
;; ----------------------------------------------------------------------------
scroll_move:
    ld a, (scroll_world_x)
    ld (scroll_try_x), a
    ld a, (scroll_world_y)
    ld (scroll_try_y), a
    ld a, (scroll_camera_x)
    ld (scroll_try_camera_x), a
    ld a, (scroll_camera_y)
    ld (scroll_try_camera_y), a
    ld a, (fwk_input_held)
    cp #1
    jr z, scroll_move_west
    cp #2
    jr z, scroll_move_east
    cp #4
    jr z, scroll_move_north
    cp #8
    jr z, scroll_move_south
    ret
scroll_move_west:
    ld a, (scroll_try_x)
    cp #PLAYER_STEP
    jp c, scroll_move_blocked
    sub #PLAYER_STEP
    ld (scroll_try_x), a
    jr scroll_move_check
scroll_move_east:
    ld a, (scroll_try_x)
    add #PLAYER_STEP
    cp #185
    jp nc, scroll_move_blocked
    ld (scroll_try_x), a
    jr scroll_move_check
scroll_move_north:
    ld a, (scroll_try_y)
    cp #PLAYER_STEP
    jp c, scroll_move_blocked
    sub #PLAYER_STEP
    ld (scroll_try_y), a
    jr scroll_move_check
scroll_move_south:
    ld a, (scroll_try_y)
    add #PLAYER_STEP
    cp #185
    jp nc, scroll_move_blocked
    ld (scroll_try_y), a
scroll_move_check:
    xor a
    ld (scroll_blocked), a
    call scroll_collision
    jp c, scroll_move_blocked
    ld a, (scroll_smooth_enabled)
    or a
    jp nz, scroll_smooth_move
    call scroll_follow
    ld a, (scroll_hw_enabled)
    or a
    jr z, scroll_move_restore_old
    ld a, (scroll_try_camera_x)
    ld b, a
    ld a, (scroll_camera_x)
    cp b
    jr nz, scroll_move_check_camera
    ld a, (scroll_try_camera_y)
    ld b, a
    ld a, (scroll_camera_y)
    cp b
    jr nz, scroll_move_check_camera
scroll_move_restore_old:
    ld ix, #scroll_player
    ld hl, #scroll_player_background
    call fwk_sprite_restore
scroll_move_check_camera:
    ld a, (scroll_try_camera_x)
    ld b, a
    ld a, (scroll_camera_x)
    cp b
    jr nz, scroll_move_redraw
    ld a, (scroll_try_camera_y)
    ld b, a
    ld a, (scroll_camera_y)
    cp b
    jr z, scroll_move_commit
scroll_move_redraw:
    ld a, (scroll_try_camera_x)
    ld (scroll_view+FWK_TILE_RENDER_CAMERA_X), a
    ld a, (scroll_try_camera_y)
    ld (scroll_view+FWK_TILE_RENDER_CAMERA_Y), a
    ld a, (scroll_hw_enabled)
    or a
    jr z, scroll_move_full_redraw
    call scroll_hw_redraw
    jr c, scroll_move_failed
    jr scroll_move_commit
scroll_move_full_redraw:
    ld ix, #scroll_map_descriptor
    ld iy, #scroll_view
    call fwk_tilemap_render_view
    jr c, scroll_move_failed
scroll_move_commit:
    ld a, (scroll_try_camera_x)
    ld (scroll_camera_x), a
    add a, a
    add a, a
    add a, a
    ld b, a
    ld a, (scroll_try_x)
    ld (scroll_world_x), a
    sub b
    ld (scroll_screen_x), a
.if FWK_PROJECT_VIDEO_MODE
    srl a
.endif
    srl a
    ld (scroll_player+FWK_SPRITE_X), a
    ld a, (scroll_try_camera_y)
    ld (scroll_camera_y), a
    add a, a
    add a, a
    add a, a
    ld b, a
    ld a, (scroll_try_y)
    ld (scroll_world_y), a
    sub b
    ld (scroll_screen_y), a
    ld (scroll_player+FWK_SPRITE_Y), a
    ld ix, #scroll_player
    ld de, #scroll_player_background
    call fwk_sprite_capture
    call fwk_sprite_draw
    ld hl, (scroll_step_count)
    inc hl
    ld (scroll_step_count), hl
    ret
scroll_move_failed:
    ld a, #0xEE
    ld (scroll_status), a
    ret
scroll_move_blocked:
    ld a, #1
    ld (scroll_blocked), a
    ret

;; ----------------------------------------------------------------------------
;; scroll_hw_redraw
;;   Experimental hardware scroll: draws the entering strip, then moves the CRTC start (R12/R13) by one tile on one axis.
;;   In : scroll_try_camera_* and scroll_camera_* (one tile apart on one axis), scroll_hw_ma.
;;   Out: carry clear; scroll_hw_ma, fwk_video_origin_bytes, R12 and R13 at the new origin.
;;   Clobbers: AF, BC, DE, HL, IX, IY
;;   Notes: The movement policy guarantees one camera tile on one axis per update. A horizontal step waits about 1300 loop turns so the strip is drawn outside the active display.
;; ----------------------------------------------------------------------------
scroll_hw_redraw:
    ld a, (scroll_try_camera_x)
    ld b, a
    ld a, (scroll_camera_x)
    cp b
    jr z, scroll_hw_choose_y
    jr c, scroll_hw_east
scroll_hw_west:
    ld hl, #-TILE_R13_STEP
    ld (scroll_hw_chars), hl
    ld a, #2
    jr scroll_hw_horizontal
scroll_hw_east:
    ld hl, #TILE_R13_STEP
    ld (scroll_hw_chars), hl
    ld a, #1
scroll_hw_horizontal:
    ld (scroll_hw_direction), a
    call scroll_hw_prepare_addresses
    ;; The main loop enters from VSYNC; prep now fits before active display.
    ld bc, #1300
scroll_hw_border_wait:
    dec bc
    ld a, b
    or c
    jr nz, scroll_hw_border_wait
    jr scroll_hw_draw
scroll_hw_choose_y:
    ld a, (scroll_try_camera_y)
    ld b, a
    ld a, (scroll_camera_y)
    cp b
    jr c, scroll_hw_south
scroll_hw_north:
    ld hl, #-ROW_R13_STEP
    ld (scroll_hw_chars), hl
    ld a, #4
    jr scroll_hw_vertical
scroll_hw_south:
    ld hl, #ROW_R13_STEP
    ld (scroll_hw_chars), hl
    ld a, #3
scroll_hw_vertical:
    ld (scroll_hw_direction), a
    call scroll_hw_prepare_addresses
    jr scroll_hw_draw
;; ----------------------------------------------------------------------------
;; scroll_hw_prepare_addresses
;;   Saves the old sprite addresses and computes the target CRTC origin.
;;   In : scroll_hw_ma, scroll_hw_chars (signed step in CRTC characters).
;;   Out: scroll_hw_target_ma = (scroll_hw_ma + scroll_hw_chars) AND 0x3FF, scroll_hw_target_bytes = twice that; scroll_hw_old_sprite_ptrs filled.
;;   Clobbers: AF, BC, DE, HL
;;   Notes: The 10-bit mask keeps the origin inside the 16 KiB video page.
;; ----------------------------------------------------------------------------
scroll_hw_prepare_addresses:
    call scroll_hw_save_sprite_addresses
    ld hl, (scroll_hw_ma)
    ld bc, (scroll_hw_chars)
    add hl, bc
    ld a, h
    and #3
    ld h, a
    ld (scroll_hw_target_ma), hl
    add hl, hl
    ld (scroll_hw_target_bytes), hl
    ret
scroll_hw_draw:
    call scroll_hw_draw_strip_fast
    call cpct_waitVSYNCStart_asm
    call scroll_hw_restore_old_sprite
    ld hl, (scroll_hw_target_ma)
    ld (scroll_hw_ma), hl
    ld de, (scroll_hw_target_bytes)
    ld (fwk_video_origin_bytes), de
    ld b, l
    ld c, #13
    call cpct_setCRTCReg_asm
    ld a, h
    or #0x30
    ld b, a
    ld c, #12
    call cpct_setCRTCReg_asm
    or a
    ret

;; ----------------------------------------------------------------------------
;; scroll_hw_draw_strip_fast
;;   Draws the 16 entering tiles (a column for east/west, a row for south/north) at the target origin.
;;   In : scroll_hw_direction (1 east, 2 west, 3 south, 4 north), scroll_try_camera_*, scroll_hw_target_bytes.
;;   Out: the strip written to VRAM.
;;   Clobbers: AF, BC, DE, HL, IX, IY
;;   Notes: Reads tile IDs straight from scroll_map and skips the generic renderer's sixteen descriptor validations; valid only for this fixture's four tiles.
;; ----------------------------------------------------------------------------
scroll_hw_draw_strip_fast:
    ld a, (scroll_hw_direction)
    cp #3
    jr nc, scroll_hw_fast_vertical
    ld ix, #fwk_video_line_table
    ld a, (scroll_try_camera_y)
    ld b, a
    ld a, (scroll_hw_direction)
    cp #1
    ld a, (scroll_try_camera_x)
    jr nz, scroll_hw_fast_west
    add #15
    ld c, a
    ld a, #15*TILE_BYTE_WIDTH
    jr scroll_hw_fast_horizontal_start
scroll_hw_fast_west:
    ld c, a
    xor a
scroll_hw_fast_horizontal_start:
    ld (scroll_hw_xbyte), a
    call scroll_hw_map_ptr
    ld a, #16
    ld (scroll_hw_tile_count), a
scroll_hw_fast_horizontal_loop:
    call scroll_hw_tile_source
    call scroll_hw_copy_tile
    ld de, #24
    add iy, de
    ld a, (scroll_hw_tile_count)
    dec a
    ld (scroll_hw_tile_count), a
    jr nz, scroll_hw_fast_horizontal_loop
    ret
scroll_hw_fast_vertical:
    ld a, (scroll_hw_direction)
    cp #3
    ld a, (scroll_try_camera_y)
    jr nz, scroll_hw_fast_north
    add #15
    ld ix, #fwk_video_line_table+240
    jr scroll_hw_fast_vertical_start
scroll_hw_fast_north:
    ld ix, #fwk_video_line_table
scroll_hw_fast_vertical_start:
    ld b, a
    ld a, (scroll_try_camera_x)
    ld c, a
    call scroll_hw_map_ptr
    ld (scroll_hw_line_start), ix
    xor a
    ld (scroll_hw_xbyte), a
    ld a, #16
    ld (scroll_hw_tile_count), a
scroll_hw_fast_vertical_loop:
    ld ix, (scroll_hw_line_start)
    call scroll_hw_tile_source
    call scroll_hw_copy_tile
    inc iy
    ld a, (scroll_hw_xbyte)
    add #TILE_BYTE_WIDTH
    ld (scroll_hw_xbyte), a
    ld a, (scroll_hw_tile_count)
    dec a
    ld (scroll_hw_tile_count), a
    jr nz, scroll_hw_fast_vertical_loop
    ret

;; ----------------------------------------------------------------------------
;; scroll_hw_map_ptr
;;   Address of one cell of the 24-column fixture map.
;;   In : B = map row, C = map column (tiles).
;;   Out: IY = scroll_map + B*24 + C.
;;   Clobbers: F, B, DE, HL
;;   Notes: No bounds check: the callers keep the camera inside the map.
;; ----------------------------------------------------------------------------
scroll_hw_map_ptr:
    ld h, #0
    ld l, b
    add hl, hl
    add hl, hl
    add hl, hl
    ld d, h
    ld e, l
    add hl, hl
    add hl, de
    ld b, #0
    add hl, bc
    ld de, #scroll_map
    add hl, de
    push hl
    pop iy
    ret

;; ----------------------------------------------------------------------------
;; scroll_hw_tile_source
;;   Graphics of the tile in one map cell.
;;   In : IY = map cell.
;;   Out: HL = tile graphics from scroll_tile_ptrs.
;;   Clobbers: AF, DE, HL
;;   Notes: Tile IDs 0..3 only; no check.
;; ----------------------------------------------------------------------------
scroll_hw_tile_source:
    ld a, 0(iy)
    add a, a
    ld l, a
    ld h, #0
    ld de, #scroll_tile_ptrs
    add hl, de
    ld e, (hl)
    inc hl
    ld d, (hl)
    ex de, hl
    ret

;; ----------------------------------------------------------------------------
;; scroll_hw_copy_tile
;;   Copies one 8-line tile to the target origin, wrapping inside its 2 KiB raster bank.
;;   In : HL = tile graphics, IX = fwk_video_line_table entry of the tile's first line, scroll_hw_xbyte, scroll_hw_target_bytes.
;;   Out: tile written; IX advanced by 16 (8 line-table entries).
;;   Clobbers: AF, BC, DE, HL, IX
;;   Notes: The bank bits of each line come from the line table; only the low 11 bits move with the origin.
;; ----------------------------------------------------------------------------
scroll_hw_copy_tile:
    push hl
    ld e, 0(ix)
    ld d, 1(ix)
    ld a, d
    and #0xF8
    ld (scroll_hw_bank), a
    ex de, hl
    ld bc, (scroll_hw_target_bytes)
    add hl, bc
    ld a, (scroll_hw_xbyte)
    add l
    ld l, a
    jr nc, scroll_hw_copy_address_ready
    inc h
scroll_hw_copy_address_ready:
    ld a, h
    and #7
    ld b, a
    ld a, (scroll_hw_bank)
    or b
    ld h, a
    ex de, hl
    pop hl
    ld a, #8
scroll_hw_copy_raster:
    ld bc, #TILE_BYTE_WIDTH
    ldir
    ex de, hl
    ld bc, #0x800-TILE_BYTE_WIDTH
    add hl, bc
    ex de, hl
    dec a
    jr nz, scroll_hw_copy_raster
    ld bc, #16
    add ix, bc
    ret

;; ----------------------------------------------------------------------------
;; scroll_hw_save_sprite_addresses
;;   Records the 8 screen addresses of the player rows before the origin moves.
;;   In : scroll_player X and Y.
;;   Out: scroll_hw_old_sprite_ptrs = 8 addresses.
;;   Clobbers: AF, BC, DE, HL
;;   Notes: The old sprite stays visible while the strip is prepared; scroll_hw_restore_old_sprite removes it later.
;; ----------------------------------------------------------------------------
scroll_hw_save_sprite_addresses:
    ld hl, #scroll_hw_old_sprite_ptrs
    ld (scroll_hw_ptr_cursor), hl
    ld a, (scroll_player+FWK_SPRITE_Y)
    ld (scroll_hw_sprite_y), a
    xor a
    ld (scroll_hw_index), a
scroll_hw_save_sprite_row:
    ld a, (scroll_hw_sprite_y)
    ld l, a
    ld h, #0
    ld a, (scroll_player+FWK_SPRITE_X)
    ld c, a
    call fwk_video_get_ptr
    ex de, hl
    ld hl, (scroll_hw_ptr_cursor)
    ld (hl), e
    inc hl
    ld (hl), d
    inc hl
    ld (scroll_hw_ptr_cursor), hl
    ld a, (scroll_hw_sprite_y)
    inc a
    ld (scroll_hw_sprite_y), a
    ld a, (scroll_hw_index)
    inc a
    ld (scroll_hw_index), a
    cp #8
    jr nz, scroll_hw_save_sprite_row
    ret
;; ----------------------------------------------------------------------------
;; scroll_hw_restore_old_sprite
;;   Puts the saved background back at the 8 recorded sprite addresses.
;;   In : scroll_hw_old_sprite_ptrs, scroll_player_background.
;;   Out: the old sprite erased from VRAM.
;;   Clobbers: AF, BC, DE, HL
;;   Notes: Called just after VSYNC starts, immediately before the CRTC origin changes.
;; ----------------------------------------------------------------------------
scroll_hw_restore_old_sprite:
    ld hl, #scroll_hw_old_sprite_ptrs
    ld (scroll_hw_ptr_cursor), hl
    ld hl, #scroll_player_background
    ld (scroll_hw_bg_cursor), hl
    xor a
    ld (scroll_hw_index), a
scroll_hw_restore_sprite_row:
    ld hl, (scroll_hw_ptr_cursor)
    ld e, (hl)
    inc hl
    ld d, (hl)
    inc hl
    ld (scroll_hw_ptr_cursor), hl
    ld hl, (scroll_hw_bg_cursor)
    ld bc, #TILE_BYTE_WIDTH
    ldir
    ld (scroll_hw_bg_cursor), hl
    ld a, (scroll_hw_index)
    inc a
    ld (scroll_hw_index), a
    cp #8
    jr nz, scroll_hw_restore_sprite_row
    ret

;; ----------------------------------------------------------------------------
;; scroll_toggle_probe
;;   H key: enters or leaves the drawing-free R13+1 display-start probe.
;;   In : scroll_probe_offset (0 = no probe).
;;   Out: entering: first scanline = scroll_probe_pattern, R13 = origin + 1, scroll_probe_offset = 1; leaving: R12/R13 restored, map and player redrawn, scroll_probe_offset = 0.
;;   Clobbers: AF, BC, DE, HL, IX, IY
;;   Notes: No fixed-origin drawing routine runs while the shifted origin is active.
;; ----------------------------------------------------------------------------
scroll_toggle_probe:
    ld a, (scroll_probe_offset)
    or a
    jr nz, scroll_probe_stop
    ld ix, #scroll_player
    ld hl, #scroll_player_background
    call fwk_sprite_restore
    ;; Address-distinct first scanline lets the emulator measure displacement.
    ld hl, #scroll_probe_pattern
    ld de, #VIDEO_ORIGIN_ADDRESS
    ld bc, #16*TILE_BYTE_WIDTH
    ldir
    ld b, #VIDEO_ORIGIN_R13+1
    ld c, #13
    call cpct_setCRTCReg_asm
    ld a, #1
    ld (scroll_probe_offset), a
    ret
scroll_probe_stop:
    ld b, #VIDEO_ORIGIN_R13
    ld c, #13
    call cpct_setCRTCReg_asm
    ld b, #48
    ld c, #12
    call cpct_setCRTCReg_asm
    xor a
    ld (scroll_probe_offset), a
    ld ix, #scroll_map_descriptor
    ld iy, #scroll_view
    call fwk_tilemap_render_view
    ld ix, #scroll_player
    ld de, #scroll_player_background
    call fwk_sprite_capture
    jp fwk_sprite_draw

;; ----------------------------------------------------------------------------
;; scroll_probe_east
;;   J key: experimental one-tile east shift of the display start.
;;   In : scroll_probe_offset (does nothing unless 0).
;;   Out: entering column drawn, R13 = origin + TILE_R13_STEP, scroll_probe_offset = 1 (Mode 1) or 2 (Mode 0).
;;   Clobbers: AF, BC, DE, HL, IX, IY
;;   Notes: Waits about 51200 T (1765 loop turns) after VSYNC so the column is written after the 128-line active display; H restores the baseline.
;; ----------------------------------------------------------------------------
scroll_probe_east:
    ld a, (scroll_probe_offset)
    or a
    ret nz
    ld ix, #scroll_player
    ld hl, #scroll_player_background
    call fwk_sprite_restore
    call cpct_waitVSYNCStart_asm
    ;; R7=30, R4=38 and R9=7: about 200 scanlines from VSYNC to the end of
    ;; the next 128-line active display. 1765 loop turns are about 51200 T.
    ld bc, #1765
scroll_probe_border_wait:
    dec bc
    ld a, b
    or c
    jr nz, scroll_probe_border_wait
    ld hl, #scroll_tiles + 16*TILE_BYTE_WIDTH
    ld (scroll_probe_source), hl
    xor a
    ld (scroll_probe_y), a
scroll_probe_fill_row:
    ld a, (scroll_probe_y)
    ld l, a
    ld h, #0
    ld c, #16*TILE_BYTE_WIDTH
    call fwk_video_get_ptr
    ex de, hl
    ld hl, (scroll_probe_source)
    ld bc, #TILE_BYTE_WIDTH
    ldir
    ld (scroll_probe_source), hl
    ld a, (scroll_probe_y)
    inc a
    cp #128
    jr z, scroll_probe_commit
    ld (scroll_probe_y), a
    and #7
    jr nz, scroll_probe_fill_row
    ld hl, #scroll_tiles + 16*TILE_BYTE_WIDTH
    ld (scroll_probe_source), hl
    jr scroll_probe_fill_row
scroll_probe_commit:
    ld b, #VIDEO_ORIGIN_R13+TILE_R13_STEP
    ld c, #13
    call cpct_setCRTCReg_asm
.if FWK_PROJECT_VIDEO_MODE
    ld a, #1
.else
    ld a, #2
.endif
    ld (scroll_probe_offset), a
    ret

;; ----------------------------------------------------------------------------
;; scroll_probe_south
;;   K key: experimental one-character-row south shift of the display start.
;;   In : scroll_probe_offset (does nothing unless 0).
;;   Out: entering 8 lines filled with 0xFF, R13 = origin + ROW_R13_STEP, scroll_probe_offset = ROW_R13_STEP.
;;   Clobbers: AF, BC, DE, HL, IX, IY
;;   Notes: The entering lines are outside the current display, so they are written before the R13 switch.
;; ----------------------------------------------------------------------------
scroll_probe_south:
    ld a, (scroll_probe_offset)
    or a
    ret nz
    ld ix, #scroll_player
    ld hl, #scroll_player_background
    call fwk_sprite_restore
    ld a, #120
    ld (scroll_probe_y), a
scroll_probe_south_row:
    ld a, (scroll_probe_y)
    ld l, a
    ld h, #0
    ld c, #0
    call fwk_video_get_ptr
    ld de, #16*TILE_BYTE_WIDTH
    add hl, de
    ld b, #16*TILE_BYTE_WIDTH
scroll_probe_south_byte:
    ld (hl), #0xFF
    inc hl
    djnz scroll_probe_south_byte
    ld a, (scroll_probe_y)
    inc a
    ld (scroll_probe_y), a
    cp #128
    jr nz, scroll_probe_south_row
    ld b, #VIDEO_ORIGIN_R13+ROW_R13_STEP
    ld c, #13
    call cpct_setCRTCReg_asm
    ld a, #ROW_R13_STEP
    ld (scroll_probe_offset), a
    ret

;; ----------------------------------------------------------------------------
;; scroll_probe_west
;;   L key: experimental one-tile west shift of the display start.
;;   In : scroll_probe_offset (does nothing unless 0).
;;   Out: entering column drawn, R12 = 0x33, R13 = 256 - TILE_R13_STEP, scroll_probe_offset = the same.
;;   Clobbers: AF, BC, DE, HL, IX, IY
;;   Notes: R12 = 0x33 keeps the same 16 KiB page while the 10-bit address wraps backwards inside each raster bank.
;; ----------------------------------------------------------------------------
scroll_probe_west:
    ld a, (scroll_probe_offset)
    or a
    ret nz
    ld ix, #scroll_player
    ld hl, #scroll_player_background
    call fwk_sprite_restore
    call cpct_waitVSYNCStart_asm
    ld bc, #1765
scroll_probe_west_wait:
    dec bc
    ld a, b
    or c
    jr nz, scroll_probe_west_wait
    ld hl, #scroll_tiles + 16*TILE_BYTE_WIDTH
    ld (scroll_probe_source), hl
    xor a
    ld (scroll_probe_y), a
scroll_probe_west_row:
    ld a, (scroll_probe_y)
    ld l, a
    ld h, #0
    ld c, #0
    call fwk_video_get_ptr
    ld de, #TILE_BYTE_WIDTH
    or a
    sbc hl, de
    ld a, (scroll_probe_y)
    cp #8
    jr nc, scroll_probe_west_address_ready
    ld de, #0x800
    add hl, de
scroll_probe_west_address_ready:
    ex de, hl
    ld hl, (scroll_probe_source)
    ld bc, #TILE_BYTE_WIDTH
    ldir
    ld (scroll_probe_source), hl
    ld a, (scroll_probe_y)
    inc a
    cp #128
    jr z, scroll_probe_west_commit
    ld (scroll_probe_y), a
    and #7
    jr nz, scroll_probe_west_row
    ld hl, #scroll_tiles + 16*TILE_BYTE_WIDTH
    ld (scroll_probe_source), hl
    jr scroll_probe_west_row
scroll_probe_west_commit:
    ld b, #0x33
    ld c, #12
    call cpct_setCRTCReg_asm
    ld b, #256-TILE_R13_STEP
    ld c, #13
    call cpct_setCRTCReg_asm
    ld a, #256-TILE_R13_STEP
    ld (scroll_probe_offset), a
    ret

;; ----------------------------------------------------------------------------
;; scroll_probe_north
;;   I key: experimental one-character-row north shift of the display start.
;;   In : scroll_probe_offset (does nothing unless 0).
;;   Out: entering 8 lines filled with 0xFF, R12 = 0x33, R13 = 256 - ROW_R13_STEP, scroll_probe_offset = the same.
;;   Clobbers: AF, BC, DE, HL, IX, IY
;;   Notes: The entering row is outside the initial image.
;; ----------------------------------------------------------------------------
scroll_probe_north:
    ld a, (scroll_probe_offset)
    or a
    ret nz
    ld ix, #scroll_player
    ld hl, #scroll_player_background
    call fwk_sprite_restore
    xor a
    ld (scroll_probe_y), a
scroll_probe_north_row:
    ld a, (scroll_probe_y)
    ld l, a
    ld h, #0
    ld c, #0
    call fwk_video_get_ptr
    ld de, #16*TILE_BYTE_WIDTH
    or a
    sbc hl, de
    ld de, #0x800
    add hl, de
    ld b, #16*TILE_BYTE_WIDTH
scroll_probe_north_byte:
    ld (hl), #0xFF
    inc hl
    djnz scroll_probe_north_byte
    ld a, (scroll_probe_y)
    inc a
    ld (scroll_probe_y), a
    cp #8
    jr nz, scroll_probe_north_row
    ld b, #0x33
    ld c, #12
    call cpct_setCRTCReg_asm
    ld b, #256-ROW_R13_STEP
    ld c, #13
    call cpct_setCRTCReg_asm
    ld a, #256-ROW_R13_STEP
    ld (scroll_probe_offset), a
    ret

;; ----------------------------------------------------------------------------
;; scroll_enable_hardware
;;   T key: turns on the experimental hardware scroll path.
;;   In : scroll_probe_offset, scroll_smooth_enabled.
;;   Out: scroll_hw_enabled = 1 unless a probe or smooth mode is active.
;;   Clobbers: AF
;;   Notes: Once on it stays on; the full redraw remains the baseline.
;; ----------------------------------------------------------------------------
scroll_enable_hardware:
    ld a, (scroll_probe_offset)
    or a
    ret nz
    ld a, (scroll_smooth_enabled)
    or a
    ret nz
    ld a, #1
    ld (scroll_hw_enabled), a
    ret

;; ----------------------------------------------------------------------------
;; scroll_enable_smooth
;;   S key: turns on the byte-step (smooth) camera.
;;   In : scroll_probe_offset, scroll_hw_enabled, scroll_camera_*.
;;   Out: scroll_smooth_enabled = 1 and scroll_smooth_camera_* = tile camera * 8, unless a probe or hardware mode is active.
;;   Clobbers: AF
;;   Notes: Does nothing when smooth mode is already on.
;; ----------------------------------------------------------------------------
scroll_enable_smooth:
    ld a, (scroll_probe_offset)
    or a
    ret nz
    ld a, (scroll_hw_enabled)
    or a
    ret nz
    ld a, (scroll_smooth_enabled)
    or a
    ret nz
    ld a, (scroll_camera_x)
    add a, a
    add a, a
    add a, a
    ld (scroll_smooth_camera_x), a
    ld a, (scroll_camera_y)
    add a, a
    add a, a
    add a, a
    ld (scroll_smooth_camera_y), a
    ld a, #1
    ld (scroll_smooth_enabled), a
    ret

;; Experimental byte-step camera. The next 128-line picture is assembled in
;; the other 1 KiB half of each raster bank, then selected at VSYNC.
scroll_smooth_move:
    ld a, (scroll_smooth_camera_x)
    ld (scroll_smooth_try_camera_x), a
    ld b, a
    ld a, (scroll_try_x)
    add #4
    sub b
    ld b, a
    ld a, (scroll_zone_x_max)
    cp b
    jr c, scroll_smooth_follow_x_high
    jr nz, scroll_smooth_follow_x_low
scroll_smooth_follow_x_high:
    ld a, (scroll_smooth_try_camera_x)
    cp #64
    jr z, scroll_smooth_follow_y
    add #PLAYER_STEP
    ld (scroll_smooth_try_camera_x), a
    jr scroll_smooth_follow_y
scroll_smooth_follow_x_low:
    ld a, (scroll_zone_x_min)
    cp b
    jr c, scroll_smooth_follow_y
    jr z, scroll_smooth_follow_y
    ld a, (scroll_smooth_try_camera_x)
    or a
    jr z, scroll_smooth_follow_y
    sub #PLAYER_STEP
    ld (scroll_smooth_try_camera_x), a
scroll_smooth_follow_y:
    ld a, (scroll_smooth_camera_y)
    ld (scroll_smooth_try_camera_y), a
    ld b, a
    ld a, (scroll_try_y)
    add #4
    sub b
    ld b, a
    ld a, (scroll_zone_y_max)
    cp b
    jr c, scroll_smooth_follow_y_high
    jr nz, scroll_smooth_follow_y_low
scroll_smooth_follow_y_high:
    ld a, (scroll_smooth_try_camera_y)
    cp #64
    jr z, scroll_smooth_choose
    add #PLAYER_STEP
    ld (scroll_smooth_try_camera_y), a
    jr scroll_smooth_choose
scroll_smooth_follow_y_low:
    ld a, (scroll_zone_y_min)
    cp b
    jr c, scroll_smooth_choose
    jr z, scroll_smooth_choose
    ld a, (scroll_smooth_try_camera_y)
    or a
    jr z, scroll_smooth_choose
    sub #PLAYER_STEP
    ld (scroll_smooth_try_camera_y), a
scroll_smooth_choose:
    xor a
    ld (scroll_smooth_direction), a
    ld a, (scroll_smooth_try_camera_x)
    ld b, a
    ld a, (scroll_smooth_camera_x)
    cp b
    jr z, scroll_smooth_choose_y
    ld a, #1
    jr c, scroll_smooth_shift
    ld a, #2
    jr scroll_smooth_shift
scroll_smooth_choose_y:
    ld a, (scroll_smooth_try_camera_y)
    ld b, a
    ld a, (scroll_smooth_camera_y)
    cp b
    jr z, scroll_smooth_sprite_only
    ld a, #3
    jr c, scroll_smooth_shift
    ld a, #4
scroll_smooth_shift:
    ld (scroll_smooth_direction), a
    ld hl, (fwk_video_origin_bytes)
    ld (scroll_smooth_source_origin), hl
    ld a, h
    xor #4
    ld h, a
    ld (scroll_smooth_target_origin), hl
    call scroll_smooth_copy_picture
    call scroll_smooth_fill_edge
    call scroll_smooth_restore_sprite_in_target
    call scroll_smooth_commit_player
    ld de, (scroll_smooth_target_origin)
    ld (fwk_video_origin_bytes), de
    ld ix, #scroll_player
    ld de, #scroll_player_background
    call fwk_sprite_capture
    call fwk_sprite_draw
    call cpct_waitVSYNCStart_asm
    ld b, #0
    ld c, #13
    call cpct_setCRTCReg_asm
    ld hl, (scroll_smooth_target_origin)
    ld a, h
    srl a
    or #0x30
    ld b, a
    ld c, #12
    call cpct_setCRTCReg_asm
    jr scroll_smooth_count_step
scroll_smooth_sprite_only:
    ld ix, #scroll_player
    ld hl, #scroll_player_background
    call fwk_sprite_restore
    call scroll_smooth_commit_player
    ld ix, #scroll_player
    ld de, #scroll_player_background
    call fwk_sprite_capture
    call fwk_sprite_draw
scroll_smooth_count_step:
    ld hl, (scroll_step_count)
    inc hl
    ld (scroll_step_count), hl
    ret

;; ----------------------------------------------------------------------------
;; scroll_smooth_commit_player
;;   Commits the candidate pixel camera and the player position.
;;   In : scroll_smooth_try_camera_*, scroll_try_*.
;;   Out: scroll_smooth_camera_*, scroll_camera_* (pixels / 8), scroll_world_*, scroll_screen_* and scroll_player X/Y.
;;   Clobbers: AF, B
;;   Notes: Player X in bytes is the screen X divided by 2 (Mode 0) or 4 (Mode 1).
;; ----------------------------------------------------------------------------
scroll_smooth_commit_player:
    ld a, (scroll_smooth_try_camera_x)
    ld (scroll_smooth_camera_x), a
    ld b, a
    srl a
    srl a
    srl a
    ld (scroll_camera_x), a
    ld a, (scroll_try_x)
    ld (scroll_world_x), a
    sub b
    ld (scroll_screen_x), a
.if FWK_PROJECT_VIDEO_MODE
    srl a
.endif
    srl a
    ld (scroll_player+FWK_SPRITE_X), a
    ld a, (scroll_smooth_try_camera_y)
    ld (scroll_smooth_camera_y), a
    ld b, a
    srl a
    srl a
    srl a
    ld (scroll_camera_y), a
    ld a, (scroll_try_y)
    ld (scroll_world_y), a
    sub b
    ld (scroll_screen_y), a
    ld (scroll_player+FWK_SPRITE_Y), a
    ret

;; ----------------------------------------------------------------------------
;; scroll_smooth_copy_picture
;;   Copies the visible picture into the other 1 KiB half, shifted one step in scroll_smooth_direction.
;;   In : scroll_smooth_direction (1 east, 2 west: one byte; 3 south, 4 north: PLAYER_STEP lines), scroll_smooth_source_origin, scroll_smooth_target_origin.
;;   Out: VRAM of the target half; fwk_video_origin_bytes = target origin.
;;   Clobbers: AF, BC, DE, HL
;;   Notes: fwk_video_origin_bytes is switched between source and target for every line.
;; ----------------------------------------------------------------------------
scroll_smooth_copy_picture:
    xor a
    ld (scroll_smooth_copy_y), a
    ld a, (scroll_smooth_direction)
    cp #3
    ld a, #128
    jr c, scroll_smooth_copy_limit
    sub #PLAYER_STEP
scroll_smooth_copy_limit:
    ld (scroll_smooth_copy_count), a
scroll_smooth_copy_loop:
    ld de, (scroll_smooth_source_origin)
    ld (fwk_video_origin_bytes), de
    ld a, (scroll_smooth_copy_y)
    ld b, a
    ld a, (scroll_smooth_direction)
    cp #3
    jr nz, scroll_smooth_copy_src_y_ready
    ld a, b
    add #PLAYER_STEP
    ld b, a
scroll_smooth_copy_src_y_ready:
    ld l, b
    ld h, #0
    ld c, #0
    ld a, (scroll_smooth_direction)
    cp #1
    jr nz, scroll_smooth_copy_src_x_ready
    inc c
scroll_smooth_copy_src_x_ready:
    call fwk_video_get_ptr
    ld (scroll_smooth_copy_src), hl
    ld de, (scroll_smooth_target_origin)
    ld (fwk_video_origin_bytes), de
    ld a, (scroll_smooth_copy_y)
    ld b, a
    ld a, (scroll_smooth_direction)
    cp #4
    jr nz, scroll_smooth_copy_dst_y_ready
    ld a, b
    add #PLAYER_STEP
    ld b, a
scroll_smooth_copy_dst_y_ready:
    ld l, b
    ld h, #0
    ld c, #0
    ld a, (scroll_smooth_direction)
    cp #2
    jr nz, scroll_smooth_copy_dst_x_ready
    inc c
scroll_smooth_copy_dst_x_ready:
    call fwk_video_get_ptr
    ex de, hl
    ld hl, (scroll_smooth_copy_src)
    ld a, (scroll_smooth_direction)
    cp #3
    ld bc, #VIEW_BYTE_WIDTH
    jr nc, scroll_smooth_copy_run
    dec bc
scroll_smooth_copy_run:
    ldir
    ld a, (scroll_smooth_copy_y)
    inc a
    ld (scroll_smooth_copy_y), a
    ld b, a
    ld a, (scroll_smooth_copy_count)
    cp b
    jr nz, scroll_smooth_copy_loop
    ret

;; ----------------------------------------------------------------------------
;; scroll_smooth_fill_edge
;;   Draws the entering edge of the target picture from the map: one byte column (east/west) or PLAYER_STEP rows (south/north).
;;   In : scroll_smooth_direction, scroll_smooth_try_camera_*, scroll_smooth_target_origin.
;;   Out: the edge written to VRAM.
;;   Clobbers: AF, BC, DE, HL, IY
;;   Notes: One scroll_smooth_fill_one call per byte.
;; ----------------------------------------------------------------------------
scroll_smooth_fill_edge:
    ld a, (scroll_smooth_direction)
    cp #3
    jr nc, scroll_smooth_fill_horizontal_row
    xor a
    ld (scroll_smooth_fill_x), a
    ld a, (scroll_smooth_direction)
    cp #2
    jr z, scroll_smooth_fill_column_start
    ld a, #VIEW_BYTE_WIDTH-1
    ld (scroll_smooth_fill_x), a
scroll_smooth_fill_column_start:
    xor a
    ld (scroll_smooth_fill_y), a
scroll_smooth_fill_column_loop:
    call scroll_smooth_fill_one
    ld a, (scroll_smooth_fill_y)
    inc a
    ld (scroll_smooth_fill_y), a
    cp #128
    jr nz, scroll_smooth_fill_column_loop
    ret
scroll_smooth_fill_horizontal_row:
    xor a
    ld (scroll_smooth_fill_y), a
    ld a, (scroll_smooth_direction)
    cp #4
    jr z, scroll_smooth_fill_row_start
    ld a, #128-PLAYER_STEP
    ld (scroll_smooth_fill_y), a
scroll_smooth_fill_row_start:
    ld a, #PLAYER_STEP
    ld (scroll_smooth_fill_limit), a
scroll_smooth_fill_row_loop:
    xor a
    ld (scroll_smooth_fill_x), a
scroll_smooth_fill_byte_loop:
    call scroll_smooth_fill_one
    ld a, (scroll_smooth_fill_x)
    inc a
    ld (scroll_smooth_fill_x), a
    cp #VIEW_BYTE_WIDTH
    jr nz, scroll_smooth_fill_byte_loop
    ld a, (scroll_smooth_fill_y)
    inc a
    ld (scroll_smooth_fill_y), a
    ld a, (scroll_smooth_fill_limit)
    dec a
    ld (scroll_smooth_fill_limit), a
    jr nz, scroll_smooth_fill_row_loop
    ret

;; ----------------------------------------------------------------------------
;; scroll_smooth_fill_one
;;   Writes one byte of map graphics at the candidate pixel camera into the target picture.
;;   In : scroll_smooth_fill_x (byte), scroll_smooth_fill_y (line), scroll_smooth_try_camera_*, scroll_smooth_target_origin.
;;   Out: one VRAM byte; fwk_video_origin_bytes = target origin.
;;   Clobbers: AF, BC, DE, HL, IY
;;   Notes: Uses scroll_hw_map_ptr and scroll_hw_tile_source, so only this fixture's four tiles.
;; ----------------------------------------------------------------------------
scroll_smooth_fill_one:
    ld a, (scroll_smooth_try_camera_x)
.if FWK_PROJECT_VIDEO_MODE
    srl a
.endif
    srl a
    ld b, a
    ld a, (scroll_smooth_fill_x)
    add b
    ld b, a
    and #(TILE_BYTE_WIDTH-1)
    ld (scroll_smooth_tile_x), a
    ld a, b
    .rept TILE_X_SHIFT
        srl a
    .endm
    ld c, a
    ld a, (scroll_smooth_try_camera_y)
    ld b, a
    ld a, (scroll_smooth_fill_y)
    add b
    ld b, a
    and #7
    ld (scroll_smooth_raster), a
    ld a, b
    srl a
    srl a
    srl a
    ld b, a
    call scroll_hw_map_ptr
    call scroll_hw_tile_source
    ld a, (scroll_smooth_raster)
.if FWK_PROJECT_VIDEO_MODE
    add a, a
.else
    add a, a
    add a, a
.endif
    ld b, a
    ld a, (scroll_smooth_tile_x)
    add b
    ld e, a
    ld d, #0
    add hl, de
    ld a, (hl)
    ld (scroll_smooth_source_byte), a
    ld de, (scroll_smooth_target_origin)
    ld (fwk_video_origin_bytes), de
    ld a, (scroll_smooth_fill_y)
    ld l, a
    ld h, #0
    ld a, (scroll_smooth_fill_x)
    ld c, a
    call fwk_video_get_ptr
    ld a, (scroll_smooth_source_byte)
    ld (hl), a
    ret

;; ----------------------------------------------------------------------------
;; scroll_smooth_restore_sprite_in_target
;;   Erases the player from the target picture where the shifted copy moved it.
;;   In : scroll_player X/Y, scroll_smooth_direction, scroll_player_background.
;;   Out: 8 background rows written to the target picture.
;;   Clobbers: AF, BC, DE, HL
;;   Notes: The copy shifted the old sprite by one byte or PLAYER_STEP lines; this undoes it at that place.
;; ----------------------------------------------------------------------------
scroll_smooth_restore_sprite_in_target:
    ld a, (scroll_player+FWK_SPRITE_X)
    ld b, a
    ld a, (scroll_smooth_direction)
    cp #1
    jr nz, scroll_smooth_sprite_not_east
    dec b
scroll_smooth_sprite_not_east:
    cp #2
    jr nz, scroll_smooth_sprite_x_ready
    inc b
scroll_smooth_sprite_x_ready:
    ld a, b
    ld (scroll_smooth_sprite_x), a
    ld a, (scroll_player+FWK_SPRITE_Y)
    ld b, a
    ld a, (scroll_smooth_direction)
    cp #3
    jr nz, scroll_smooth_sprite_not_south
    ld a, b
    sub #PLAYER_STEP
    ld b, a
scroll_smooth_sprite_not_south:
    ld a, (scroll_smooth_direction)
    cp #4
    jr nz, scroll_smooth_sprite_y_ready
    ld a, b
    add #PLAYER_STEP
    ld b, a
scroll_smooth_sprite_y_ready:
    ld a, b
    ld (scroll_smooth_sprite_y), a
    ld hl, #scroll_player_background
    ld (scroll_smooth_bg_ptr), hl
    ld a, #8
    ld (scroll_smooth_sprite_count), a
scroll_smooth_sprite_row:
    ld a, (scroll_smooth_sprite_y)
    ld l, a
    ld h, #0
    ld a, (scroll_smooth_sprite_x)
    ld c, a
    call fwk_video_get_ptr
    ex de, hl
    ld hl, (scroll_smooth_bg_ptr)
    ld bc, #TILE_BYTE_WIDTH
    ldir
    ld (scroll_smooth_bg_ptr), hl
    ld a, (scroll_smooth_sprite_y)
    inc a
    ld (scroll_smooth_sprite_y), a
    ld a, (scroll_smooth_sprite_count)
    dec a
    ld (scroll_smooth_sprite_count), a
    jr nz, scroll_smooth_sprite_row
    ret


;; Initial fixed-origin map and player display.
_main::
    call fwk_project_init
    call fwk_video_init
    call fwk_video_configure_crtc
    ld b, #VIDEO_ORIGIN_R13
    ld c, #13
    call cpct_setCRTCReg_asm
    call fwk_input_init
    ld hl, #scroll_bindings
    call fwk_input_set_bindings
    ld l, #0
    ld h, #0x14
    call cpct_setPALColour_asm
    ld l, #15
    ld h, #0x0A
    call cpct_setPALColour_asm
    xor a
    call fwk_video_clear_visible
    ld ix, #scroll_map_descriptor
    ld iy, #scroll_view
    call fwk_tilemap_render_view
    jr c, scroll_main_fail
    ld ix, #scroll_player
    ld de, #scroll_player_background
    call fwk_sprite_capture
    call fwk_sprite_draw
    ld a, #0x5A
    ld (scroll_status), a
scroll_main_loop:
    call fwk_system_wait_frame
    call fwk_input_update
    ld hl, #Key_S
    call cpct_isKeyPressed_asm
    call nz, scroll_enable_smooth
    ld hl, #Key_T
    call cpct_isKeyPressed_asm
    call nz, scroll_enable_hardware
    ld a, (scroll_hw_enabled)
    or a
    jr nz, scroll_main_move
    ld a, (scroll_smooth_enabled)
    or a
    jr nz, scroll_main_move
    ld a, (fwk_input_pressed)
    and #16
    call nz, scroll_toggle_probe
    ld a, (fwk_input_pressed)
    and #32
    call nz, scroll_probe_east
    ld a, (fwk_input_pressed)
    and #64
    call nz, scroll_probe_south
    ld a, (fwk_input_pressed)
    and #128
    call nz, scroll_probe_west
    ld hl, #Key_I
    call cpct_isKeyPressed_asm
    call nz, scroll_probe_north
scroll_main_move:
    ld a, (scroll_probe_offset)
    or a
    jr nz, scroll_main_loop
    call scroll_move
    jr scroll_main_loop
scroll_main_fail:
    ld a, #0xEE
    ld (scroll_status), a
scroll_fail_loop:
    call fwk_system_wait_frame
    jr scroll_fail_loop
