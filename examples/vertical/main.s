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

;; Comprobación defensiva de carry tras una llamada al framework.
VERTICAL_DEBUG_CHECKS = 1
.macro VERTICAL_CHECK_OK
.if VERTICAL_DEBUG_CHECKS
    jp c, _vertical_fail
.endif
.endm

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

;; ----------------------------------------------------------------------------
;; _vertical_fail
;;   Stops the game: stores the ABI error code in vertical_status and then waits
;;   frames forever. The code is 1..0x0B, so the status is never READY or WON.
;;   In : A=ABI error code (FWK_ECS_ERR_*).
;;   Out: Never returns. vertical_status=A.
;;   Clobbers: all (never returns)
;;   Notes: Infinite loop. Calls fwk_system_wait_frame (documented AF, BC, DE, HL), so
;;          nothing is assumed preserved.
;; ----------------------------------------------------------------------------
_vertical_fail:
    ld (vertical_status), a          ; visible to a debugger or the test harness
_vertical_fail_loop:               ; freeze here: keep the machine alive but stop the logic
    call fwk_system_wait_frame
    jr _vertical_fail_loop

;; ----------------------------------------------------------------------------
;; _vertical_expect_ok
;;   Result check for every ECS call: continues on success, stops the game on error.
;;   In : Carry and A as returned by the last fwk_ecs_* call (carry set = error, A=code).
;;   Out: Success: carry clear, A and all other registers unchanged (plain ret nc).
;;          Error: does not return.
;;   Clobbers: none on the returning (success) path. The error path never returns.
;;   Notes: Success path is a bare ret nc, so flags stay clear-carry. On error HL is
;;          overwritten by the pop and the stack is unwound one level. May be entered by
;;          call or by jp (tail call): both work because the error path never returns to
;;          the caller.
;; ----------------------------------------------------------------------------
;; ----------------------------------------------------------------------------
;; _vertical_spawn
;;   Creates one 1x1 entity with MOTION and COLLISION in vertical_manager, built from
;;   a zeroed template.
;;   In : A=entity type, B=x (screen bytes), C=y (scanlines).
;;   Out: Success: carry clear, A=0, IY=new slot in vertical_manager.
;;          Error (manager full, bad template): does not return, game stops.
;;   Clobbers: AF, BC, DE, HL, IX, IY
;;   Notes: IX is loaded with vertical_manager (the entry IX is lost). Overwrites
;;          _vertical_template; the zeroed fields give cadence 0 (every iteration), zero
;;          velocity and no render flags. BC and AF are saved around the template
;;          zeroing but then clobbered by fwk_ecs_entity_create (AF, BC, DE, HL
;;          documented).
;; ----------------------------------------------------------------------------
_vertical_spawn:
    ;; Zero the whole template: fill byte 0, then ldir copies it onto the next
    ;; ECS_ENTITY_SIZE-1 bytes. AF/BC hold the arguments and are saved around it.
    push af
    push bc
    ld hl, #_vertical_template
    ld de, #_vertical_template + 1
    ld (hl), #0
    ld bc, #ECS_ENTITY_SIZE - 1
    ldir
    pop bc
    pop af
    ;; Fill the fields this entity needs; everything else stays 0.
    ld iy, #_vertical_template
    ld ECS_E_COMPONENTS(iy), #<(ECS_C_MOTION | ECS_C_COLLISION)
    ld ECS_E_COMPONENTS+1(iy), #>(ECS_C_MOTION | ECS_C_COLLISION)
    ld ECS_E_STATUS(iy), #ECS_STATUS_ACTIVE
    ld ECS_E_TYPE(iy), a
    ld ECS_E_X(iy), b
    ld ECS_E_Y(iy), c
    ld ECS_E_WIDTH(iy), #1
    ld ECS_E_HEIGHT(iy), #1
    ;; The manager copies the template into the first free slot (IY on return).
    ld ix, #vertical_manager
    ld hl, #_vertical_template
    call fwk_ecs_entity_create
    ret nc
    jp _vertical_fail

;; ----------------------------------------------------------------------------
;; _load_level
;;   Initializes the manager, spawns the player (slot 0, so it lands at vertical_player)
;;   and then one pickup per entry of vertical_pickup_spawns, drawing each pickup once.
;;   In : none (reads vertical_pickup_spawns: count byte, then x,y pairs; and
;;          vertical_sprite_bytes+1).
;;   Out: Entities created in vertical_manager, pickup bytes plotted on screen.
;;   Clobbers: AF, BC, DE, HL, IX, IY
;;   Notes: Any ECS error stops the game (_vertical_expect_ok). The pickup count is used
;;          as a djnz counter, so a table with count 0 would loop 256 times: keep it at
;;          1 or more. The manager holds VERTICAL_CAPACITY (4) entities, enough for 1 +
;;          VERTICAL_PICKUPS.
;; ----------------------------------------------------------------------------
_load_level:
    ld ix, #vertical_manager
    call fwk_ecs_manager_init
    VERTICAL_CHECK_OK
    ;; Player first so it takes slot 0 (vertical_player). B=x=10, C=y=100.
    ld a, #VERTICAL_ENTITY_PLAYER
    ld bc, #10 << 8 | 100
    call _vertical_spawn
    ;; B = pickup count, HL walks the x,y pairs.
    ld hl, #vertical_pickup_spawns
    ld b, (hl)
    inc hl
_load_pickup:                      ; one iteration per pickup
    push bc                        ; save the loop counter and the table cursor
    push hl
    ld b, (hl)                     ; B=x
    inc hl
    ld c, (hl)                     ; C=y
    ld a, #VERTICAL_ENTITY_PICKUP
    push bc                        ; spawn clobbers BC; keep x,y for the plot
    call _vertical_spawn
    pop bc
    ld l, c                        ; plot wants HL=y, C=x
    ld h, #0
    ld c, b
    ld a, (vertical_sprite_bytes + 1)
    call fwk_video_plot_byte
    pop hl                         ; back on the x of this pair: skip x and y
    inc hl
    inc hl
    pop bc
    djnz _load_pickup
    ret

;; ----------------------------------------------------------------------------
;; _plot_player
;;   Writes the byte in A at the screen position stored in the entity.
;;   In : IY=entity (reads ECS_E_X as x byte and ECS_E_Y as y scanline), A=Mode 0 byte
;;          to draw (0 erases).
;;   Out: The byte is written to video memory.
;;   Clobbers: C, DE, HL
;;   Notes: Tail-jumps to fwk_video_plot_byte, so it returns to the caller of
;;          _plot_player. A, F, B, IX and IY are unchanged: plot_byte saves AF around
;;          its pointer lookup and fwk_video_get_ptr leaves B and C alone.
;; ----------------------------------------------------------------------------
_plot_player:
    ld l, ECS_E_Y(iy)
    ld h, #0
    ld c, ECS_E_X(iy)
    jp fwk_video_plot_byte

;; ----------------------------------------------------------------------------
;; _erase_player
;;   Clears the screen byte under the player.
;;   In : none (uses vertical_player).
;;   Out: IY=vertical_player. The byte at the player's position is set to 0.
;;   Clobbers: AF, C, DE, HL, IY
;;   Notes: Leaves the entity data untouched. Wipes whatever was in that cell, including
;;          a pickup byte the player is standing on. On return A=0 and the flags are
;;          those of xor a. Reaches _plot_player through jr, so it returns to its own
;;          caller.
;; ----------------------------------------------------------------------------
_erase_player:
    ld iy, #vertical_player
    xor a                            ; byte 0 = background
    jr _plot_player

;; ----------------------------------------------------------------------------
;; _draw_player
;;   Draws the player with the normal sprite byte, or with the winning byte once
;;   vertical_status is VERTICAL_STATUS_WON.
;;   In : none (reads vertical_status and vertical_sprite_bytes).
;;   Out: IY=vertical_player. The sprite byte is written at the player's position.
;;   Clobbers: AF, C, DE, HL, IY
;;   Notes: Reaches _plot_player through jr (never falls through), so it returns to its
;;          own caller. On return A is the byte that was drawn.
;; ----------------------------------------------------------------------------
_draw_player:
    ld iy, #vertical_player
    ld a, (vertical_status)
    cp #VERTICAL_STATUS_WON          ; Z = game won (the loads below keep the flags)
    ld a, (vertical_sprite_bytes)    ; normal player sprite
    jr nz, _plot_player
    ld a, (vertical_sprite_bytes + 2) ; won: player-after-winning sprite
    jr _plot_player

;; ----------------------------------------------------------------------------
;; _apply_input
;;   Translates the held actions of this frame into the player's signed velocity
;;   (-1, 0 or +1 per axis).
;;   In : none (reads fwk_input_held; bit 0 left, 1 right, 2 up, 3 down, matching
;;          the VERTICAL_ACTION_* values of _bindings).
;;   Out: IY=vertical_player. ECS_E_MOTION_VELOCITY_X/Y set in the entity.
;;   Clobbers: AF, C, IY
;;   Notes: If opposite keys are held, right beats left and down beats up (the later
;;          write wins). B, DE and HL are preserved.
;; ----------------------------------------------------------------------------
_apply_input:
    ld iy, #vertical_player
    xor a                            ; no key held = no movement
    ld ECS_E_MOTION_VELOCITY_X(iy), a
    ld ECS_E_MOTION_VELOCITY_Y(iy), a
    ld a, (fwk_input_held)
    ld c, a                          ; C = action mask, tested bit by bit
    bit 0, c                         ; LEFT
    jr z, _input_right
    ld ECS_E_MOTION_VELOCITY_X(iy), #-1
_input_right:                      ; RIGHT
    bit 1, c
    jr z, _input_up
    ld ECS_E_MOTION_VELOCITY_X(iy), #1
_input_up:                         ; UP
    bit 2, c
    jr z, _input_down
    ld ECS_E_MOTION_VELOCITY_Y(iy), #-1
_input_down:                       ; DOWN
    bit 3, c
    ret z
    ld ECS_E_MOTION_VELOCITY_Y(iy), #1
    ret

;; ----------------------------------------------------------------------------
;; _pickup_cb
;;   Collision callback for fwk_ecs_collide: destroys a pickup the player touches and
;;   counts it; the last one sets vertical_status to VERTICAL_STATUS_WON. Its byte on
;;   screen needs no erasing: the player stands on that cell, draws over it and erases
;;   it when it moves on.
;;   In : IX=manager, IY=target entity, HL=subject (unused), A=event (unused).
;;   Out: Continue: carry clear, A=0. Error from mark_destroy: carry set, A=code (aborts the
;;          collision pass). IX and IY preserved. vertical_score and vertical_status may change.
;;   Clobbers: AF, BC, DE, HL
;;   Notes: IX and IY are saved around fwk_ecs_entity_mark_destroy and restored, as the
;;          collide ABI requires. It ignores the event and does not handle EXIT (IY=0):
;;          that is safe only because _collect_pickups passes channel E=0, which never
;;          reports STAY or EXIT. Non-pickup targets return at once with only AF
;;          changed.
;; ----------------------------------------------------------------------------
_pickup_cb:
    ld a, ECS_E_TYPE(iy)
    cp #VERTICAL_ENTITY_PICKUP
    jr nz, _pickup_ignore            ; only pickups count (the player is a target too)
    push ix                          ; the ABI preserves IX/IY; saved anyway because
    push iy                          ; the collide loop must get them back intact
    call fwk_ecs_entity_mark_destroy ; freed later by fwk_ecs_manager_collect
    pop iy
    pop ix
    ret c                            ; error: carry set, A=code aborts the pass
    ld a, (vertical_score)
    inc a
    ld (vertical_score), a
    cp #VERTICAL_PICKUPS
    jr nz, _pickup_ignore
    ld a, #VERTICAL_STATUS_WON
    ld (vertical_status), a
_pickup_ignore:                    ; also the normal exit: carry clear, A=0
    xor a
    ret

;; ----------------------------------------------------------------------------
;; _collect_pickups
;;   Tests the player against every entity with COLLISION and runs _pickup_cb on each
;;   contact.
;;   In : none (uses vertical_player and vertical_manager).
;;   Out: Success: carry clear, A=0. Error: does not return, game stops.
;;   Clobbers: AF, BC, DE, HL, IX, IY
;;   Notes: IX and IY are set to the manager and the player on entry; fwk_ecs_collide
;;          preserves both. Channel E=0: no contact state is kept, every contact is
;;          reported as ENTER. Tail-jumps to _vertical_expect_ok.
;; ----------------------------------------------------------------------------
_collect_pickups:
    ld iy, #vertical_player          ; subject
    ld ix, #vertical_manager         ; targets live here
    ld bc, #ECS_C_COLLISION          ; only entities with the COLLISION component
    ld hl, #_pickup_cb
    ld e, #0                         ; channel 0: no ENTER/STAY/EXIT state kept
    call fwk_ecs_collide
    ret nc
    jp _vertical_fail

;; ----------------------------------------------------------------------------
;; _main
;;   Program entry: initializes the framework, input and level, then runs the game loop
;;   forever (erase, input, motion, collision, collect, draw).
;;   In : none.
;;   Out: Never returns.
;;   Clobbers: all (never returns)
;;   Notes: Per frame order matters: the player is erased before it moves, drawn after
;;          collision so the final position and win sprite show, and destroyed pickups
;;          are freed by fwk_ecs_manager_collect at the end of the logic.
;; ----------------------------------------------------------------------------
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
    ld a, #VERTICAL_STATUS_READY     ; READY marks "level loaded" for the harness
    ld (vertical_status), a

_vertical_loop:                    ; one iteration per frame
    call fwk_system_wait_frame
    call _erase_player               ; erase at the old position before it moves
    call fwk_input_update
    call _apply_input
    ld ix, #vertical_manager
    call fwk_ecs_system_motion_u8    ; integrate velocity, clamped to the screen
    VERTICAL_CHECK_OK
    call _collect_pickups
    ld ix, #vertical_manager
    call fwk_ecs_manager_collect     ; free the pickups destroyed this frame
    VERTICAL_CHECK_OK
    call _draw_player
    jr _vertical_loop
