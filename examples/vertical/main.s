.module example_vertical
.include "cpctelera.h.s"
.include "core/pool.inc"
.include "extensions/motion_u8.inc"

.globl fwk_system_init, fwk_system_wait_frame
.globl fwk_input_init, fwk_input_set_bindings, fwk_input_update, fwk_input_held
.globl fwk_pool_init, fwk_pool_alloc, fwk_pool_get, fwk_pool_remove, fwk_pool_foreach
.globl fwk_video_init, fwk_video_clear_visible, fwk_video_plot_byte
.globl fwk_motion_u8_step
.globl vertical_pickup_spawns, vertical_sprite_bytes

VERTICAL_ACTION_LEFT  = 0x01
VERTICAL_ACTION_RIGHT = 0x02
VERTICAL_ACTION_UP    = 0x04
VERTICAL_ACTION_DOWN  = 0x08

VERTICAL_ENTITY_PLAYER = 0x01
VERTICAL_ENTITY_PICKUP = 0x02

VERTICAL_STATUS_READY = 0xA5
VERTICAL_STATUS_WON   = 0x5A

.area _DATA
vertical_entities::
vertical_player::
    .ds FWK_MOTION_RECORD_SIZE * 4
FWK_POOL_DESCRIPTOR vertical_entity_pool, vertical_entities, 4, FWK_MOTION_RECORD_SIZE

vertical_score::  .db 0
vertical_status:: .db 0
_scan_index:      .db 0

_bindings:
    .dw Key_CursorLeft
    .db VERTICAL_ACTION_LEFT
    .dw Key_CursorRight
    .db VERTICAL_ACTION_RIGHT
    .dw Key_CursorUp
    .db VERTICAL_ACTION_UP
    .dw Key_CursorDown
    .db VERTICAL_ACTION_DOWN
    .dw 0
    .db 0

.area _CODE

;; Load the player and pickup positions from the game-owned resource table.
_load_level:
    ld ix, #vertical_entity_pool
    call fwk_pool_init

    call fwk_pool_alloc
    ld (hl), #10
    inc hl
    ld (hl), #100
    inc hl
    ld (hl), #0
    inc hl
    ld (hl), #0
    inc hl
    ld (hl), #VERTICAL_ENTITY_PLAYER

    ld hl, #vertical_pickup_spawns
    ld b, (hl)
    inc hl
_load_pickup:
    push bc
    push hl
    call fwk_pool_alloc
    pop de
    ld a, (de)
    ld (hl), a
    inc de
    inc hl
    ld a, (de)
    ld (hl), a
    inc de
    inc hl
    xor a
    ld (hl), a
    inc hl
    ld (hl), a
    inc hl
    ld (hl), #VERTICAL_ENTITY_PICKUP
    ld h, d
    ld l, e
    pop bc
    djnz _load_pickup
    ret

_erase_entity:
    ld l, FWK_MOTION_Y(iy)
    ld h, #0
    ld c, FWK_MOTION_X(iy)
    xor a
    jp fwk_video_plot_byte

_draw_entity:
    ld a, FWK_MOTION_FLAGS(iy)
    cp #VERTICAL_ENTITY_PLAYER
    jr nz, _draw_pickup
    ld a, (vertical_status)
    cp #VERTICAL_STATUS_WON
    ld a, (vertical_sprite_bytes)
    jr nz, _draw_at_entity
    ld a, (vertical_sprite_bytes + 2)
    jr _draw_at_entity
_draw_pickup:
    ld a, (vertical_sprite_bytes + 1)
_draw_at_entity:
    ld l, FWK_MOTION_Y(iy)
    ld h, #0
    ld c, FWK_MOTION_X(iy)
    jp fwk_video_plot_byte

;; Translate held actions to the signed velocity fields of the player.
_apply_input:
    xor a
    ld (vertical_player + FWK_MOTION_VX), a
    ld (vertical_player + FWK_MOTION_VY), a
    ld a, (fwk_input_held)
    bit 0, a
    jr z, _input_right
    ld a, #-1
    ld (vertical_player + FWK_MOTION_VX), a
_input_right:
    ld a, (fwk_input_held)
    bit 1, a
    jr z, _input_up
    ld a, #1
    ld (vertical_player + FWK_MOTION_VX), a
_input_up:
    ld a, (fwk_input_held)
    bit 2, a
    jr z, _input_down
    ld a, #-1
    ld (vertical_player + FWK_MOTION_VY), a
_input_down:
    ld a, (fwk_input_held)
    bit 3, a
    ret z
    ld a, #1
    ld (vertical_player + FWK_MOTION_VY), a
    ret

;; Remove pickups occupying the player's byte coordinate. Pool compaction is
;; intentional: after a removal the same index points at the next pickup.
_collect_pickups:
    ld a, #1
    ld (_scan_index), a
_collect_loop:
    ld a, FWK_POOL_COUNT(ix)
    ld b, a
    ld a, (_scan_index)
    cp b
    ret nc
    call fwk_pool_get
    ld a, (vertical_player + FWK_MOTION_X)
    cp (hl)
    jr nz, _collect_next
    inc hl
    ld a, (vertical_player + FWK_MOTION_Y)
    cp (hl)
    jr nz, _collect_next
    ld a, (_scan_index)
    call fwk_pool_remove
    ld a, (vertical_score)
    inc a
    ld (vertical_score), a
    cp #3
    jr nz, _collect_loop
    ld a, #VERTICAL_STATUS_WON
    ld (vertical_status), a
    jr _collect_loop
_collect_next:
    ld a, (_scan_index)
    inc a
    ld (_scan_index), a
    jr _collect_loop

_main::
    call fwk_system_init
    call fwk_video_init
    xor a
    call fwk_video_clear_visible
    call fwk_input_init
    ld hl, #_bindings
    call fwk_input_set_bindings
    call _load_level
    xor a
    ld (vertical_score), a
    ld a, #VERTICAL_STATUS_READY
    ld (vertical_status), a

_vertical_loop:
    call fwk_system_wait_frame
    ld ix, #vertical_entity_pool
    ld de, #_erase_entity
    call fwk_pool_foreach
    call fwk_input_update
    call _apply_input
    ld iy, #vertical_player
    call fwk_motion_u8_step
    ld ix, #vertical_entity_pool
    call _collect_pickups
    ld de, #_draw_entity
    call fwk_pool_foreach
    jr _vertical_loop
