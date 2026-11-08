.module game_main
;; Welcome project on GlasnostFWK ECS 2.0: a ship you move with the cursor keys
;; and three drones that patrol. It shows the pieces every game uses: a manager
;; with its entities, the input, behavior and motion systems, a selective
;; renderer with background pools, and text. Replace it with your own game.
;;
;; This file holds code and data only; .globl declarations, constants and macros
;; live in common.inc. generated/project.inc is written by `glasnost config`:
;; do not edit it.
.include "common.inc"
.include "generated/project.inc"

.area _DATA

;; ---- Public state, observable by tests and the emulator ----
game_status::  .db 0              ; 0x5A once the game is running, else the ABI error code
game_player::  .dw 0              ; address of the player entity
game_hits::    .db 0              ; times a drone touched the player
_game_hud_dirty: .db 1            ; the score must be redrawn

;; ---- Texts ----
_game_str_welcome: .asciz "WELCOME TO"
_game_str_help:    .asciz "CURSOR KEYS MOVE"
_game_str_hits:    .asciz "HITS: 00"      ; the two digits are patched in place

;; ---- Sprites and palette come from assets/ (assets/assets.json): generated
;; ---- into assets/generated/assets.s, which the build assembles by itself.

;; ---- Entity storage: ECS_ENTITY_SIZE-byte slots, filled in spawn order ----
_game_tpl:      .ds ECS_ENTITY_SIZE    ; template built from a spawn row, copied into the manager
_game_anim:     .dw 0                  ; descriptor of the row being spawned
game_storage::  .ds ECS_ENTITY_SIZE * GAME_CAP
FWK_ECS_MANAGER_DESCRIPTOR game_manager, game_storage, GAME_CAP

;; ---- Renderer: one pool of GAME_CAP background buffers of 32 bytes (4 x 8) ----
FWK_ECS_RENDER_POOL game_pool32, 32, GAME_CAP
_game_pools:    .dw game_pool32
_game_managers: .dw game_manager
_game_work:     .ds 8 * GAME_CAP
FWK_ECS_RENDER_SCENE game_scene, _game_managers, 1, _game_work, GAME_CAP, _game_pools, 1

;; ---- Keyboard: (key, action bit) pairs ended by a zero action ----
game_bindings:
    .dw Key_CursorLeft
    .db GAME_INPUT_LEFT
    .dw Key_CursorRight
    .db GAME_INPUT_RIGHT
    .dw Key_CursorUp
    .db GAME_INPUT_UP
    .dw Key_CursorDown
    .db GAME_INPUT_DOWN
    .dw 0
    .db 0

;; ---- Drone patrol program: right for half a leg, then left and right in full legs ----
_game_program_drone:
    FWK_BEHAVIOR_SET_VX 1
    FWK_BEHAVIOR_WAIT GAME_DRONE_FIRST_LEG, _game_program_drone_left
_game_program_drone_left:
    FWK_BEHAVIOR_SET_VX -1
    FWK_BEHAVIOR_WAIT GAME_DRONE_LEG, _game_program_drone_right
_game_program_drone_right:
    FWK_BEHAVIOR_SET_VX 1
    FWK_BEHAVIOR_WAIT GAME_DRONE_LEG, _game_program_drone_left

;; ---- Animations: frame count, ticks per frame, then the frame sprites ----
_game_anim_ship:  .db 2, GAME_ANIM_TICKS
    .dw game_ship_pixels, game_ship_pixels2
_game_anim_drone: .db 2, GAME_ANIM_TICKS
    .dw game_drone_pixels, game_drone_pixels2

;; ---- Spawn rows (see GAME_ROW) ----
_game_row_player: GAME_ROW GAME_PLAYER_COMPS, GAME_T_PLAYER, 38, 170, 4, 8, game_ship_pixels, 0, _game_anim_ship
_game_row_drone0: GAME_ROW GAME_DRONE_COMPS, GAME_T_DRONE, 30, 70, 4, 8, game_drone_pixels, _game_program_drone, _game_anim_drone
_game_row_drone1: GAME_ROW GAME_DRONE_COMPS, GAME_T_DRONE, 40, 100, 4, 8, game_drone_pixels, _game_program_drone, _game_anim_drone
_game_row_drone2: GAME_ROW GAME_DRONE_COMPS, GAME_T_DRONE, 30, 130, 4, 8, game_drone_pixels, _game_program_drone, _game_anim_drone

.area _CODE

;; ----------------------------------------------------------------------------
;; _game_fail
;;   Stops the game: stores the error code and waits frames forever.
;;   In : A=ABI error code (from _game_expect_ok).
;;   Out: game_status=A. Never returns.
;;   Clobbers: all (never returns)
;;   Notes: Entered by jp only, so the stack of the failing caller is abandoned. It keeps
;;          calling fwk_system_wait_frame so the interrupts and the screen stay alive and
;;          the code stays readable in game_status.
;; ----------------------------------------------------------------------------
_game_fail:
    ld (game_status), a
_game_fail_loop:
    call fwk_system_wait_frame
    jr _game_fail_loop

;; ----------------------------------------------------------------------------
;; _game_expect_ok
;;   Error guard used after each framework call that reports errors through the carry
;;   (ECS, renderer): continues on success, stops the game on error.
;;   In : carry from the call just made (clear = ok, set = error); A=error code when set.
;;   Out: success: returns with carry clear and A untouched. Error: does not return.
;;   Clobbers: none (on the error path HL is overwritten, but that path never returns)
;;   Notes: On error it drops its own return address (pop hl) and jumps to _game_fail.
;;          Call it right after the framework call: anything in between may change the carry.
;; ----------------------------------------------------------------------------
;; ----------------------------------------------------------------------------
;; _game_spawn
;;   Builds an entity from a spawn row (GAME_ROW), creates it in the manager and,
;;   if the row names an animation, starts it.
;;   In : IX=manager, HL=spawn row (13 bytes, see GAME_ROW in common.inc).
;;   Out: success: carry clear, IY=the new entity. Failure: carry set, A=ABI error code.
;;        _game_tpl and _game_anim are overwritten.
;;   Clobbers: AF, BC, DE, HL, IY
;;   Notes: IX is preserved. The template is zeroed first, so every field the row does not
;;          set (cadence, velocity, flags) starts at 0. The row is read in order: components,
;;          type, x, y, width, height, sprite, behavior program, animation descriptor.
;; ----------------------------------------------------------------------------
_game_spawn:
    ;; Zero the template: ldir copies the first byte (0) over the rest.
    push hl
    ld hl, #_game_tpl
    ld de, #_game_tpl + 1
    ld (hl), #0
    ld bc, #ECS_ENTITY_SIZE - 1
    ldir
    pop hl
    ld iy, #_game_tpl
    ;; Copy the row into the template, field by field, in the order GAME_ROW writes it.
    ld a, (hl)
    inc hl
    ld ECS_E_COMPONENTS(iy), a      ; components: which systems act on it (low byte)
    ld a, (hl)
    inc hl
    ld ECS_E_COMPONENTS+1(iy), a    ; (high byte)
    ld ECS_E_STATUS(iy), #ECS_STATUS_ACTIVE
    ld a, (hl)
    inc hl
    ld ECS_E_TYPE(iy), a            ; type: GAME_T_PLAYER or GAME_T_DRONE
    ld a, (hl)
    inc hl
    ld ECS_E_X(iy), a               ; position: x in bytes, y in scanlines
    ld a, (hl)
    inc hl
    ld ECS_E_Y(iy), a
    ld a, (hl)
    inc hl
    ld ECS_E_WIDTH(iy), a           ; size: width in bytes, height in scanlines
    ld a, (hl)
    inc hl
    ld ECS_E_HEIGHT(iy), a
    ld a, (hl)
    inc hl
    ld ECS_E_RENDER_SPRITE(iy), a   ; sprite pixels (low byte, then high)
    ld a, (hl)
    inc hl
    ld ECS_E_RENDER_SPRITE+1(iy), a
    ld a, (hl)
    inc hl
    ld ECS_E_BEHAVIOR_PROGRAM(iy), a ; patrol program, 0 = none (low byte, then high)
    ld a, (hl)
    inc hl
    ld ECS_E_BEHAVIOR_PROGRAM+1(iy), a
    ld e, (hl)
    inc hl
    ld d, (hl)
    ld (_game_anim), de             ; animation descriptor of this row
    ld ECS_E_RENDER_FLAGS(iy), #ECS_RENDER_VISIBLE | ECS_RENDER_DIRTY   ; draw it on the first frame
    ;; Hand the finished template to the manager, which copies it into a free slot.
    ld hl, #_game_tpl
    call fwk_ecs_entity_create
    ret c                           ; manager full or bad template: carry and error in A
    ld hl, (_game_anim)
    ld a, h
    or l
    ret z                           ; no animation
    jp fwk_ecs_anim_set             ; IY = the new entity

;; ----------------------------------------------------------------------------
;; _game_text
;;   Draws a string at the left margin (GAME_TEXT_X) on a given scanline.
;;   In : B=scanline, HL=NUL-terminated string.
;;   Out: the text is drawn on the visible screen. IY is left pointing at the string.
;;   Clobbers: AF, BC, DE, HL, IX, IY
;;   Notes: Tail-jumps to fwk_text_draw, which returns to the caller. IX is listed because
;;          fwk_text_draw documents it as modified (its current body restores it). Bytes the
;;          font does not have (lowercase, for example) advance one cell without drawing.
;; ----------------------------------------------------------------------------
_game_text:
    push hl                         ; keep the string while HL carries the scanline
    ld l, b
    ld h, #0
    ld c, #GAME_TEXT_X
    call fwk_video_get_ptr          ; HL = screen address of (GAME_TEXT_X, scanline)
    pop iy                          ; IY = string, HL = where to draw it
    jp fwk_text_draw

;; ----------------------------------------------------------------------------
;; _game_drone_cb
;;   Collision callback: counts a hit when the player goes from touching no drone to
;;   touching one, not on every frame of the contact. The state is remembered per subject
;;   and channel: a drone touched while the player already touched another one in an earlier
;;   pass arrives as STAY and does not count.
;;   In : IX=manager, IY=drone (0 on EXIT), HL=player, A=ECS_COLLISION_ENTER, STAY or EXIT.
;;   Out: carry clear and A=0 (keep going). On ENTER: game_hits +1 and _game_hud_dirty=1.
;;   Clobbers: AF
;;   Notes: Touches only A and the flags (the framework does not require a collide callback to
;;          keep IX or IY). game_hits stops at 99 because the score has two digits.
;; ----------------------------------------------------------------------------
_game_drone_cb:
    cp #ECS_COLLISION_ENTER
    jr nz, _game_drone_cb_done      ; STAY and EXIT do not count
    ld a, (game_hits)
    cp #99
    jr z, _game_drone_cb_done       ; the score has two digits
    inc a
    ld (game_hits), a
    ld a, #1
    ld (_game_hud_dirty), a         ; ask _game_hud_update to redraw
_game_drone_cb_done:
    xor a                           ; carry clear, A=0: keep going
    ret

;; ----------------------------------------------------------------------------
;; _game_hud_update
;;   Redraws the score when it changed: patches the two digits into the string,
;;   clears its box and draws it.
;;   In : reads _game_hud_dirty and game_hits.
;;   Out: _game_hud_dirty cleared; the digits of _game_str_hits patched and the score drawn.
;;   Clobbers: AF, BC, DE, HL, IX, IY
;;   Notes: IX is listed because fwk_text_draw documents it as modified. When nothing changed it
;;          returns after touching only AF. The tens digit comes from
;;          repeated subtraction of 10 (game_hits <= 99). Call it after the render: the text
;;          goes over whatever the renderer left.
;; ----------------------------------------------------------------------------
_game_hud_update:
    ld a, (_game_hud_dirty)
    or a
    ret z                           ; nothing changed
    xor a
    ld (_game_hud_dirty), a
    ld a, (game_hits)
    ld b, #'0'                      ; B = tens digit, counted up by subtracting 10
_game_hud_tens:
    cp #10
    jr c, _game_hud_units
    sub #10
    inc b
    jr _game_hud_tens
_game_hud_units:
    add a, #'0'                     ; A = units digit
    ld (_game_str_hits + 7), a      ; "HITS: 00": units at offset 7, tens at offset 6
    ld a, b
    ld (_game_str_hits + 6), a
    ld hl, #GAME_HUD_Y
    ld c, #GAME_HUD_X
    call fwk_video_get_ptr
    ex de, hl
    ld b, #GAME_HUD_H
    ld c, #GAME_HUD_W
    xor a
    call cpct_drawSolidBox_asm       ; black box over the old digits
    ld hl, #GAME_HUD_Y
    ld c, #GAME_HUD_X
    call fwk_video_get_ptr
    ld iy, #_game_str_hits
    jp fwk_text_draw

;; ----------------------------------------------------------------------------
;; _game_steer
;;   Steering system, run before motion: UP and DOWN set the vertical velocity of
;;   every entity with the INPUT component.
;;   In : IX=manager, IY=entity (fwk_ecs_system_run callback); reads fwk_input_held.
;;   Out: carry clear and A=0. ECS_E_MOTION_VELOCITY_Y(iy) = -GAME_SPEED_Y (UP), +GAME_SPEED_Y (DOWN) or 0.
;;   Clobbers: AF, C
;;   Notes: IX and IY are saved and restored: the traversal requires it. If both keys are held,
;;          DOWN wins.
;; ----------------------------------------------------------------------------
_game_steer:
    push ix
    push iy
    ld a, (fwk_input_held)
    ld c, a
    xor a
    bit 3, c                         ; GAME_INPUT_UP
    jr z, _game_steer_down
    ld a, #-GAME_SPEED_Y
_game_steer_down:
    bit 4, c                         ; GAME_INPUT_DOWN
    jr z, _game_steer_set
    ld a, #GAME_SPEED_Y
_game_steer_set:
    ld ECS_E_MOTION_VELOCITY_Y(iy), a
    pop iy
    pop ix
    xor a
    ret

;; ----------------------------------------------------------------------------
;; _game_clamp
;;   Keeps the entity inside the play area, run after motion: X within 0..GAME_X_MAX,
;;   Y within GAME_Y_MIN..GAME_Y_MAX.
;;   In : IX=manager, IY=entity (fwk_ecs_system_run callback).
;;   Out: carry clear and A=0. ECS_E_X(iy) and ECS_E_Y(iy) are inside the limits.
;;   Clobbers: AF
;;   Notes: Positions are unsigned bytes, but fwk_ecs_system_motion_u8 already saturates at 0, so
;;          with it the X >= 200 test never fires; it only guards a position that wrapped to
;;          254. IX and IY are saved and restored.
;; ----------------------------------------------------------------------------
_game_clamp:
    push ix
    push iy
    ld a, ECS_E_X(iy)
    cp #200
    jr c, _game_clamp_x_max
    xor a
    jr _game_clamp_x_set
_game_clamp_x_max:
    cp #GAME_X_MAX + 1
    jr c, _game_clamp_y
    ld a, #GAME_X_MAX
_game_clamp_x_set:
    ld ECS_E_X(iy), a
_game_clamp_y:
    ld a, ECS_E_Y(iy)
    cp #GAME_Y_MIN
    jr nc, _game_clamp_y_max
    ld a, #GAME_Y_MIN
    jr _game_clamp_y_set
_game_clamp_y_max:
    cp #GAME_Y_MAX + 1
    jr c, _game_clamp_done
    ld a, #GAME_Y_MAX
_game_clamp_y_set:
    ld ECS_E_Y(iy), a
_game_clamp_done:
    pop iy
    pop ix
    xor a
    ret

;; ----------------------------------------------------------------------------
;; _main
;;   Program entry: starts the framework, draws the texts, creates the manager, the
;;   renderer and the four entities, then runs the frame loop forever.
;;   In : none.
;;   Out: never returns. game_status=0x5A once the game runs, or an ABI error code.
;;   Clobbers: all (never returns)
;;   Notes: Each frame runs, in order: input, behavior, input system, steering, motion,
;;          animation, clamp, collisions, then the selective render around the VSYNC wait,
;;          then the score.
;; ----------------------------------------------------------------------------
_main::
    ;; System up (firmware off, interrupts on), Mode 0, text, palette, keyboard, clear screen.
    call fwk_project_init
    call fwk_video_init
    call fwk_text_init
    ld hl, #game_palette
    ld de, #GAME_PALETTE_SIZE
    call cpct_setPalette_asm
    call fwk_input_init
    ld hl, #game_bindings
    call fwk_input_set_bindings
    xor a
    call fwk_video_clear_visible

    ;; The three static texts: welcome, the project title, the help line.
    ld b, #GAME_TEXT_Y_WELCOME
    ld hl, #_game_str_welcome
    call _game_text
    ld b, #GAME_TEXT_Y_TITLE
    ld hl, #game_title
    call _game_text
    ld b, #GAME_TEXT_Y_HELP
    ld hl, #_game_str_help
    call _game_text

    ;; Empty manager and renderer, then spawn the player and the three drones.
    ld ix, #game_manager
    call fwk_ecs_manager_init
    GAME_CHECK_OK
    ld ix, #game_scene
    call fwk_ecs_render_reset
    GAME_CHECK_OK

    ld ix, #game_manager
    ld hl, #_game_row_player
    call _game_spawn
    GAME_CHECK_OK
    ld (game_player), iy            ; the collision pass needs the player's address
    ld ECS_E_INPUT_ACTION_MASK(iy), #GAME_INPUT_LEFT | GAME_INPUT_RIGHT   ; LEFT/RIGHT steer it
    ld ix, #game_manager
    ld hl, #_game_row_drone0
    call _game_spawn
    GAME_CHECK_OK
    ld ix, #game_manager
    ld hl, #_game_row_drone1
    call _game_spawn
    GAME_CHECK_OK
    ld ix, #game_manager
    ld hl, #_game_row_drone2
    call _game_spawn
    GAME_CHECK_OK

    ld a, #0x5A
    ld (game_status), a             ; running: tests and the emulator wait for this

    ;; ---- One game frame ----
game_frame:
    call fwk_input_update           ; read the keys once per frame
    ld ix, #game_manager
    call fwk_ecs_system_behavior
    GAME_CHECK_OK
    ld ix, #game_manager
    call fwk_ecs_system_input        ; LEFT and RIGHT set the horizontal velocity
    GAME_CHECK_OK
    ld ix, #game_manager
    ld bc, #ECS_C_INPUT
    ld hl, #_game_steer              ; UP and DOWN set the vertical velocity
    call fwk_ecs_system_run
    GAME_CHECK_OK
    ld ix, #game_manager
    call fwk_ecs_system_motion_u8    ; velocity moves every entity
    GAME_CHECK_OK
    ld ix, #game_manager
    call fwk_ecs_system_animation    ; every animation counts down and changes frame
    GAME_CHECK_OK
    ld ix, #game_manager
    ld bc, #ECS_C_INPUT
    ld hl, #_game_clamp
    call fwk_ecs_system_run
    GAME_CHECK_OK
    ld ix, #game_manager             ; the player against every drone (collision + behavior)
    ld iy, (game_player)
    ld bc, #ECS_C_COLLISION | ECS_C_BEHAVIOR
    ld hl, #_game_drone_cb
    ld e, #GAME_CH_DRONE
    call fwk_ecs_collide
    GAME_CHECK_OK
    ;; Selective render: find what changed before VSYNC, touch video RAM after it.
    ld ix, #game_scene
    call fwk_ecs_render_prepare
    GAME_CHECK_OK
    call fwk_system_wait_frame
    ld ix, #game_scene
    call fwk_ecs_render_restore
    GAME_CHECK_OK
    ld ix, #game_scene
    call fwk_ecs_render_draw
    GAME_CHECK_OK
    call _game_hud_update            ; after the render: text goes over what it left
    jp game_frame
