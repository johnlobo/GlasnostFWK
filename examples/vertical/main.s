.module example_vertical
;; Vertical slice on ECS 2.0: the smallest playable game. One manager holds the
;; player and three pickups; `motion` moves the player, `collision` picks the
;; pickups up. Sprites are single bytes drawn with fwk_video_plot_byte.
.include "cpctelera.h.s"
.include "ecs_profile.inc"
.include "core/ecs_manager.inc"
.include "core/ecs_collision.inc"

.globl fwk_project_init, fwk_system_wait_frame
.globl fwk_input_init, fwk_input_set_bindings, fwk_input_update, fwk_input_held
.globl fwk_video_init, fwk_video_clear_visible, fwk_video_plot_byte
.globl fwk_ecs_system_motion_u8
.globl vertical_pickup_spawns, vertical_sprite_bytes

VERTICAL_ACTION_LEFT  = 0x01
VERTICAL_ACTION_RIGHT = 0x02
VERTICAL_ACTION_UP    = 0x04
VERTICAL_ACTION_DOWN  = 0x08

VERTICAL_ENTITY_PLAYER = 0x01
VERTICAL_ENTITY_PICKUP = 0x02
VERTICAL_CAPACITY      = 4
VERTICAL_PICKUPS       = 3

VERTICAL_STATUS_READY = 0xA5
VERTICAL_STATUS_WON   = 0x5A

.area _DATA
;; Slot 0 is the player, so vertical_player is also the start of the storage.
vertical_player::
vertical_storage:: .ds ECS_ENTITY_SIZE * VERTICAL_CAPACITY
FWK_ECS_MANAGER_DESCRIPTOR vertical_manager, vertical_storage, VERTICAL_CAPACITY

_vertical_template: .ds ECS_ENTITY_SIZE

vertical_score::  .db 0
vertical_status:: .db 0

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

;; Stop the game with the ABI error code in the status (never READY or WON).
_vertical_fail:
    ld (vertical_status), a
_vertical_fail_loop:
    call fwk_system_wait_frame
    jr _vertical_fail_loop

;; Continue on success; on error stop with the code in A.
_vertical_expect_ok:
    ret nc
    pop hl
    jp _vertical_fail

;; In: A=type, B=x, C=y. Creates a 1x1 motion+collision entity in the manager.
_vertical_spawn:
    push af
    push bc
    ld hl, #_vertical_template
    ld de, #_vertical_template + 1
    ld (hl), #0
    ld bc, #ECS_ENTITY_SIZE - 1
    ldir
    pop bc
    pop af
    ld iy, #_vertical_template
    ld ECS_E_COMPONENTS(iy), #<(ECS_C_MOTION | ECS_C_COLLISION)
    ld ECS_E_COMPONENTS+1(iy), #>(ECS_C_MOTION | ECS_C_COLLISION)
    ld ECS_E_STATUS(iy), #ECS_STATUS_ACTIVE
    ld ECS_E_TYPE(iy), a
    ld ECS_E_X(iy), b
    ld ECS_E_Y(iy), c
    ld ECS_E_WIDTH(iy), #1
    ld ECS_E_HEIGHT(iy), #1
    ld ix, #vertical_manager
    ld hl, #_vertical_template
    call fwk_ecs_entity_create
    jp _vertical_expect_ok

;; Create the player and the pickups of the game-owned resource table, and draw
;; the pickups once (they never move).
_load_level:
    ld ix, #vertical_manager
    call fwk_ecs_manager_init
    call _vertical_expect_ok
    ld a, #VERTICAL_ENTITY_PLAYER
    ld bc, #10 << 8 | 100
    call _vertical_spawn
    ld hl, #vertical_pickup_spawns
    ld b, (hl)
    inc hl
_load_pickup:
    push bc
    push hl
    ld b, (hl)
    inc hl
    ld c, (hl)
    ld a, #VERTICAL_ENTITY_PICKUP
    push bc
    call _vertical_spawn
    pop bc
    ld l, c
    ld h, #0
    ld c, b
    ld a, (vertical_sprite_bytes + 1)
    call fwk_video_plot_byte
    pop hl
    inc hl
    inc hl
    pop bc
    djnz _load_pickup
    ret

;; Draw the player, or erase it with A=0 (HL=y, C=x are read from the entity).
_plot_player:
    ld l, ECS_E_Y(iy)
    ld h, #0
    ld c, ECS_E_X(iy)
    jp fwk_video_plot_byte

_erase_player:
    ld iy, #vertical_player
    xor a
    jr _plot_player

_draw_player:
    ld iy, #vertical_player
    ld a, (vertical_status)
    cp #VERTICAL_STATUS_WON
    ld a, (vertical_sprite_bytes)
    jr nz, _plot_player
    ld a, (vertical_sprite_bytes + 2)
    jr _plot_player

;; Translate held actions to the signed velocity fields of the player.
_apply_input:
    ld iy, #vertical_player
    xor a
    ld ECS_E_MOTION_VELOCITY_X(iy), a
    ld ECS_E_MOTION_VELOCITY_Y(iy), a
    ld a, (fwk_input_held)
    ld c, a
    bit 0, c
    jr z, _input_right
    ld ECS_E_MOTION_VELOCITY_X(iy), #-1
_input_right:
    bit 1, c
    jr z, _input_up
    ld ECS_E_MOTION_VELOCITY_X(iy), #1
_input_up:
    bit 2, c
    jr z, _input_down
    ld ECS_E_MOTION_VELOCITY_Y(iy), #-1
_input_down:
    bit 3, c
    ret z
    ld ECS_E_MOTION_VELOCITY_Y(iy), #1
    ret

;; Collision callback (IX=manager, IY=target, HL=subject, A=event): a pickup the
;; player touches is removed and counts towards the win. Its byte on screen needs
;; no erasing: the player stands on that cell, draws over it and erases it when it
;; moves on.
_pickup_cb:
    ld a, ECS_E_TYPE(iy)
    cp #VERTICAL_ENTITY_PICKUP
    jr nz, _pickup_ignore
    push ix
    push iy
    call fwk_ecs_entity_mark_destroy
    pop iy
    pop ix
    ret c
    ld a, (vertical_score)
    inc a
    ld (vertical_score), a
    cp #VERTICAL_PICKUPS
    jr nz, _pickup_ignore
    ld a, #VERTICAL_STATUS_WON
    ld (vertical_status), a
_pickup_ignore:
    xor a
    ret

_collect_pickups:
    ld iy, #vertical_player
    ld ix, #vertical_manager
    ld bc, #ECS_C_COLLISION
    ld hl, #_pickup_cb
    ld e, #0
    call fwk_ecs_collide
    jp _vertical_expect_ok

_main::
    call fwk_project_init
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
    call _erase_player
    call fwk_input_update
    call _apply_input
    ld ix, #vertical_manager
    call fwk_ecs_system_motion_u8
    call _vertical_expect_ok
    call _collect_pickups
    ld ix, #vertical_manager
    call fwk_ecs_manager_collect
    call _vertical_expect_ok
    call _draw_player
    jr _vertical_loop
