.module example_platformer
;; Platformer example: one-screen platform game built on the GlasnostFWK modules.
;; It demonstrates tiled maps, entity rendering, physics, coins, enemies and a door.
.include "cpctelera.h.s"
.include "video/entity_render.inc"
.include "extensions/platform_tilemap.inc"
.include "extensions/behavior.inc"
.include "game/game.inc"
.include "assets/generated/assets.inc"
.include "globals.inc"

.area _DATA

;; Public state doubles as a small observable contract for emulator tests.
platformer_status::         .db 0
platformer_score::          .db 0
platformer_lives::          .db PF_LIVES_INITIAL
platformer_last_collision:: .db 0
platformer_hud_dirty::      .db 1
platformer_enemy_contacts:: .db 0
platformer_current_level::  .db 0

_platformer_enemy_contacts_next: .db 0
_platformer_enemy_phase: .db 0

platformer_player_background::
    .ds PF_PLAYER_WIDTH_BYTES * PF_PLAYER_HEIGHT_PX
platformer_coin0_background: .ds 4 * 8
platformer_coin1_background: .ds 4 * 8
platformer_coin2_background: .ds 4 * 8
platformer_coin3_background: .ds 4 * 8
platformer_enemy_h_background: .ds PF_ENEMY_WIDTH_BYTES * PF_ENEMY_HEIGHT_PX
platformer_enemy_v_background: .ds PF_ENEMY_WIDTH_BYTES * PF_ENEMY_HEIGHT_PX
platformer_enemy_v2_background: .ds PF_ENEMY_WIDTH_BYTES * PF_ENEMY_HEIGHT_PX
platformer_door_background: .ds 4 * 8

platformer_player_entity::
platformer_player_sprite::
    FWK_ENTITY_RENDER_PREFIX platformer_player_pixels, PF_PLAYER_START_X, PF_PLAYER_START_Y, PF_PLAYER_WIDTH_BYTES, PF_PLAYER_HEIGHT_PX, PF_PLAYER_START_Y+PF_PLAYER_HEIGHT_PX, platformer_player_background, PF_PLAYER_WIDTH_BYTES*PF_PLAYER_HEIGHT_PX, FWK_ENTITY_RENDER_VISIBLE, 0, 0
platformer_player:: .ds PF_PLAYER_SIZE

platformer_coin0_entity::
    FWK_ENTITY_RENDER_PREFIX platformer_coin_pixels, 16, 24, 4, 8, 32, platformer_coin0_background, 32, FWK_ENTITY_RENDER_VISIBLE, 0, 0
platformer_coin1_entity::
    FWK_ENTITY_RENDER_PREFIX platformer_coin_pixels, 56, 24, 4, 8, 32, platformer_coin1_background, 32, FWK_ENTITY_RENDER_VISIBLE, 0, 0
platformer_coin2_entity::
    FWK_ENTITY_RENDER_PREFIX platformer_coin_pixels, 16, 168, 4, 8, 176, platformer_coin2_background, 32, FWK_ENTITY_RENDER_VISIBLE, 0, 0
platformer_coin3_entity::
    FWK_ENTITY_RENDER_PREFIX platformer_coin_pixels, 56, 168, 4, 8, 176, platformer_coin3_background, 32, FWK_ENTITY_RENDER_VISIBLE, 0, 0
platformer_enemy_h_entity::
    FWK_ENTITY_RENDER_PREFIX platformer_enemy_pixels, PF_ENEMY_H_START_X, PF_ENEMY_H_Y, PF_ENEMY_WIDTH_BYTES, PF_ENEMY_HEIGHT_PX, PF_ENEMY_H_Y+PF_ENEMY_HEIGHT_PX, platformer_enemy_h_background, PF_ENEMY_WIDTH_BYTES*PF_ENEMY_HEIGHT_PX, FWK_ENTITY_RENDER_VISIBLE, 0, 0
platformer_enemy_h_behavior::
    .db PF_ENEMY_H_START_X, PF_ENEMY_H_Y, 0, 0, 0
    .dw platformer_enemy_h_program
    .db 0
platformer_enemy_v_entity::
    FWK_ENTITY_RENDER_PREFIX platformer_enemy_pixels, PF_ENEMY_V_X, PF_ENEMY_V_START_Y, PF_ENEMY_WIDTH_BYTES, PF_ENEMY_HEIGHT_PX, PF_ENEMY_V_START_Y+PF_ENEMY_HEIGHT_PX, platformer_enemy_v_background, PF_ENEMY_WIDTH_BYTES*PF_ENEMY_HEIGHT_PX, FWK_ENTITY_RENDER_VISIBLE, 0, 0
platformer_enemy_v_behavior::
    .db PF_ENEMY_V_X, PF_ENEMY_V_START_Y, 0, 0, 0
    .dw platformer_enemy_v_program
    .db 0
platformer_enemy_v2_entity::
    FWK_ENTITY_RENDER_PREFIX platformer_enemy_pixels, PF_ENEMY_V2_X, PF_ENEMY_V_START_Y, PF_ENEMY_WIDTH_BYTES, PF_ENEMY_HEIGHT_PX, PF_ENEMY_V_START_Y+PF_ENEMY_HEIGHT_PX, platformer_enemy_v2_background, PF_ENEMY_WIDTH_BYTES*PF_ENEMY_HEIGHT_PX, FWK_ENTITY_RENDER_VISIBLE, 0, 0
platformer_enemy_v2_behavior::
    .db PF_ENEMY_V2_X, PF_ENEMY_V_START_Y, 0, 0, 0
    .dw platformer_enemy_v_program
    .db 0
platformer_door_entity::
    FWK_ENTITY_RENDER_PREFIX platformer_door_pixels, 72, 160, 4, 8, 168, platformer_door_background, 32, 0, 0, 0

platformer_render_entities:
    .dw platformer_player_entity, platformer_coin0_entity, platformer_coin1_entity
    .dw platformer_coin2_entity, platformer_coin3_entity
    .dw platformer_enemy_h_entity, platformer_enemy_v_entity, platformer_enemy_v2_entity, platformer_door_entity
platformer_render_work: .ds PF_RENDER_COUNT * FWK_ENTITY_RENDER_WORK_SIZE
FWK_ENTITY_RENDER_DESCRIPTOR platformer_render_list, platformer_render_entities, PF_RENDER_COUNT, platformer_render_work, PF_RENDER_COUNT

platformer_score_str:: .ascii "COINS: 0/4"
    .db 0
platformer_hint_str:: .ascii "COLLECT ALL COINS"
    .db 0
platformer_all_coins_str:: .ascii "ALL COINS"
    .db 0
platformer_score_digit_str: .ascii "0"
    .db 0
platformer_life_str:: .ascii "LIFE: 10"
    .db 0
platformer_life_digits_str: .ascii "10"
    .db 0
platformer_win_str:: .ascii "GO TO THE DOOR"
    .db 0

_platformer_hud_column: .db 0
_platformer_hud_pending: .db 0
_pf_anim_timer: .db 0
_pf_anim_frame: .db 0

.area _CODE

;; Routine: _main
;; Description: Entry point. Initialises the framework, resets the game state,
;;   renders the first frame and enters the main loop.
;; Input:  none
;; Output: none (does not return)
_main::
    call _pf_init_framework
    call _pf_reset_game
    call _pf_render_scene

;; Main game loop. One iteration equals one frame.
_platformer_loop:
    ;; 1. Sample keyboard/joystick and update the input module state.
    call fwk_input_update

    ;; 2. Advance the two-frame player animation timer.
    call _pf_update_animation

    ;; 3. Read movement/jump actions into the game state.
    call _pf_read_controls

    ;; 4. Integrate player physics (gravity, velocity, tile collision).
    call _pf_update_player

    ;; 5. Move the horizontal and vertical enemies inside their patrols.
    call _pf_update_enemies
    call _pf_update_enemy_v2

    ;; 6. Copy physics state into the render prefix and mark dirty on change.
    call _pf_sync_player_render

    ;; 7. Collect coins overlapping the player; update score, HUD and door.
    call _pf_collect_coins

    ;; 8. If the player touches the door after winning, reset the scene.
    call _pf_check_door

    ;; 9. Detect enemy/player overlaps and remove a life on the transition.
    call _pf_check_enemy_contacts

    ;; 10. Validate and close the dirty-entity set before VSYNC.
    ;;     The actual VRAM writes happen after the wait, in the shortest
    ;;     possible commit (restore first, then draw).
    call _pf_prepare_dirty
    call fwk_system_wait_frame
    call _pf_restore_dirty
    call _pf_draw_dirty

    ;; 11. Redraw only the dirty HUD cells, if any.
    ld a, (platformer_hud_dirty)
    or a
    call nz, _pf_update_hud

    ;; 12. Repeat forever.
    jp _platformer_loop

;; Framework and palette setup are kept separate from game state so the order
;; required by the text module is obvious in the tutorial.
;; Routine: _pf_decompress_levels
;; Description: Expands the two ZX7B-compressed level maps into their RAM buffers.
;; Input:  none
;; Output: platformer_map and platformer_map2 filled in RAM
_pf_decompress_levels:
    ld hl, #platformer_map_packed + PLATFORMER_MAP_PACKED_SIZE - 1
    ld de, #platformer_map + PLATFORMER_MAP_SIZE - 1
    call fwk_zx7b_unpack
    ld hl, #platformer_map2_packed + PLATFORMER_MAP2_PACKED_SIZE - 1
    ld de, #platformer_map2 + PLATFORMER_MAP2_SIZE - 1
    jp fwk_zx7b_unpack

;; Routine: _pf_init_framework
;; Description: Initialises CPCTelera, decompresses levels, video, text and input.
;; Input:  none
;; Output: framework ready; palette loaded
;; Routine: _pf_load_active_map
;; Description: Points IX/IY at the active map descriptor and view.
;; Input:  none
;; Output: IX = active map descriptor, IY = active view
_pf_load_active_map:
    ld a, (platformer_current_level)
    or a
    jr z, _pf_load_map1
    ld ix, #platformer_map2_descriptor
    ld iy, #platformer_view2
    ret
_pf_load_map1:
    ld ix, #platformer_map_descriptor
    ld iy, #platformer_view
    ret

;; Routine: _pf_active_map_descriptor
;; Description: Returns the active map descriptor in IX.
;; Input:  none
;; Output: IX = active map descriptor
_pf_active_map_descriptor:
    call _pf_load_active_map
    ;; IX already set; discard IY by reselecting? keep simple: reload ix
    ld a, (platformer_current_level)
    or a
    jr z, _pf_amd1
    ld ix, #platformer_map2_descriptor
    ret
_pf_amd1:
    ld ix, #platformer_map_descriptor
    ret

_pf_init_framework:
    call fwk_project_init
    ;; Levels are stored compressed in ROM and expanded once into their RAM
    ;; buffers before anything reads the tilemap descriptors.
    call _pf_decompress_levels
    call fwk_video_init
    call fwk_text_init

    ;; Load the palette generated from assets/palette.json (firmware codes).
    ld hl, #platformer_palette
    ld de, #PLATFORMER_PALETTE_SIZE
    call cpct_setPalette_asm
    xor a
    call fwk_text_set_color
    xor a
    call fwk_video_clear_visible

    call fwk_input_init
    ld hl, #platformer_bindings
    jp fwk_input_set_bindings

;; Reset the player and HUD to the initial state of a new game.
;; Routine: _pf_reset_game
;; Description: Resets player, enemies and HUD to the initial state of a new game.
;; Input:  none
;; Output: game state reset
_pf_reset_game:
    ld a, #PF_PLAYER_START_X
    ld (platformer_player+PF_PLAYER_X), a
    ld a, #PF_PLAYER_START_Y
    ld (platformer_player+PF_PLAYER_Y), a
    xor a
    ld (platformer_player+PF_PLAYER_VX), a
    ld (platformer_player+PF_PLAYER_VY), a
    ld (platformer_last_collision), a
    ld (platformer_score), a
    ld (platformer_status), a
    ld (platformer_enemy_contacts), a
    ld (_platformer_enemy_contacts_next), a
    ld a, #PF_LIVES_INITIAL
    ld (platformer_lives), a
    ld a, #PF_PLAYER_WIDTH_BYTES
    ld (platformer_player+PF_PLAYER_WIDTH), a
    ld a, #PF_PLAYER_HEIGHT_PX
    ld (platformer_player+PF_PLAYER_HEIGHT), a
    ld a, #PF_TILE_GROUNDED
    ld (platformer_player+PF_PLAYER_FLAGS), a
    ld a, #PF_HUD_DIRTY_SCORE|PF_HUD_DIRTY_LIVES
    ld (platformer_hud_dirty), a
    call _pf_reset_enemies
    call _pf_reset_render_flags
    call _pf_sync_player_render
    ret

;; Draw the initial scene: map, HUD and entities, then prepare the first frame.
;; Routine: _pf_render_scene
;; Description: Draws the initial map, HUD and entities, then prepares the first frame.
;; Input:  none
;; Output: initial scene on screen
_pf_render_scene:
    ;; The tilemap is static. Only dirty cells, the HUD and the moving player
    ;; are restored/redrawn after this initial full pass.
    call _pf_load_active_map
    call fwk_tilemap_render_view
    call _pf_draw_hud_initial
    ld ix, #platformer_render_list
    call fwk_entity_render_init
    jp c, _pf_render_fail
    call _pf_prepare_dirty
    call _pf_restore_dirty
    call _pf_draw_dirty
    ld a, #PF_STATUS_READY
    ld (platformer_status), a
    ret

_pf_render_fail:
    ld a, #0xEE
    ld (platformer_status), a
_pf_render_fail_loop:
    call fwk_system_wait_frame
    jr _pf_render_fail_loop

;; Routine: _pf_prepare_dirty
;; Description: Validates and prepares dirty entities before VSYNC without VRAM writes.
;; Input:  IX = render list
;; Output: carry set on failure
_pf_prepare_dirty:
    ld ix, #platformer_render_list
    call fwk_entity_render_prepare_dirty
    jp c, _pf_render_fail
    ret

;; Routine: _pf_restore_dirty
;; Description: Restores captured backgrounds of dirty entities (prepares first if needed).
;; Input:  IX = render list
;; Output: carry set on failure
_pf_restore_dirty:
    ld ix, #platformer_render_list
    call fwk_entity_render_restore_dirty
    jp c, _pf_render_fail
    ret

;; Routine: _pf_draw_dirty
;; Description: Captures and redraws dirty entities in Y order, then returns to IDLE.
;; Input:  IX = render list
;; Output: carry set on failure
_pf_draw_dirty:
    ld ix, #platformer_render_list
    call fwk_entity_render_draw_dirty
    jp c, _pf_render_fail
    ret

;; Read the configured input bindings into the game action flags.
;; Routine: _pf_update_animation
;; Description: Advances the two-frame player animation timer (0..7) and toggles
;;   the active animation frame every 8 frames.
;; Input:  none
;; Output: _pf_anim_timer and _pf_anim_frame updated
_pf_update_animation:
    ld a, (_pf_anim_timer)
    inc a
    cp #8
    jr c, _pf_update_animation_store
    xor a
    ld (_pf_anim_timer), a
    ld a, (_pf_anim_frame)
    xor #1
    ld (_pf_anim_frame), a
    ret
_pf_update_animation_store:
    ld (_pf_anim_timer), a
    ret

;; Routine: _pf_read_controls
;; Description: Reads configured input bindings into the game action flags.
;; Input:  none
;; Output: input state updated
_pf_read_controls:
    ;; Left wins if both horizontal directions are held. Releasing both stops
    ;; immediately; acceleration belongs to a larger game, not this example.
    ld a, (fwk_input_held)
    and #PF_INPUT_LEFT
    jr z, _pf_try_right
    ld a, #-PF_SPEED
    ld (platformer_player+PF_PLAYER_VX), a
    jr _pf_try_jump
_pf_try_right:
    ld a, (fwk_input_held)
    and #PF_INPUT_RIGHT
    jr z, _pf_stop_horizontal
    ld a, #PF_SPEED
    ld (platformer_player+PF_PLAYER_VX), a
    jr _pf_try_jump
_pf_stop_horizontal:
    xor a
    ld (platformer_player+PF_PLAYER_VX), a

_pf_try_jump:
    ld a, (fwk_input_pressed)
    and #PF_INPUT_JUMP
    ret z
    ld a, (platformer_player+PF_PLAYER_FLAGS)
    and #PF_TILE_GROUNDED
    ret z
    ld a, #PF_JUMP_SPEED
    ld (platformer_player+PF_PLAYER_VY), a
    ret

;; Apply player physics and keep the render prefix in sync with the player state.
;; Routine: _pf_update_player
;; Description: Applies player physics and keeps the render prefix in sync.
;; Input:  none
;; Output: player state updated
_pf_update_player:
    ld ix, #platformer_config
    ld iy, #platformer_player
    call fwk_physics_platform_step
    call _pf_active_map_descriptor
    ld iy, #platformer_player
    call fwk_platform_tilemap_resolve
    ld (platformer_last_collision), a
    ret

;; Enemy movement is synchronized with the standard render prefix. All three
;; patrols stay inside fixed, documented limits and mark only their own entity
;; dirty when their logical position changes.
;; Alternate the two slower enemies. Their behavior programs own direction and
;; duration; this scheduler preserves the original one-update-every-two-frames
;; cadence. The left vertical enemy is updated separately every frame.
;; Routine: _pf_update_enemies
;; Description: Dispatches one of the two half-rate behavior enemies.
;; Input:  none
;; Output: enemy state updated
_pf_update_enemies:
    ld a, (_platformer_enemy_phase)
    xor #1
    ld (_platformer_enemy_phase), a
    jr z, _pf_update_enemy_v
    ld ix, #platformer_enemy_h_behavior
    ld iy, #platformer_enemy_h_entity
    jp _pf_update_behavior_enemy

;; Update the first vertical patrolling enemy.
;; Routine: _pf_update_enemy_v
;; Description: Updates the first vertical patrolling enemy.
;; Input:  none
;; Output: enemy state updated
_pf_update_enemy_v:
    ld ix, #platformer_enemy_v_behavior
    ld iy, #platformer_enemy_v_entity
    jp _pf_update_behavior_enemy

;; Second vertical enemy on the left side, controlled by the behavior VM.
;; Routine: _pf_update_enemy_v2
;; Description: Runs its behavior, applies compact motion and syncs render state.
;; Input:  none
;; Output: enemy state updated
_pf_update_enemy_v2:
    ld ix, #platformer_enemy_v2_behavior
    ld iy, #platformer_enemy_v2_entity
    ;; Fall through to the shared behavior/motion/render adapter.

;; In: IX = 8-byte behavior record, IY = entity render prefix.
;; Runs behavior and motion, then falls through to the shared synchronizer.
_pf_update_behavior_enemy:
    call fwk_behavior_run
    push iy
    push ix
    pop iy
    call fwk_motion_u8_step
    pop iy

;; In: IX = behavior record, IY = entity render prefix.
;; Copies compact coordinates and animation into the renderer.
_pf_sync_behavior_enemy:
    ld a, FWK_BEHAVIOR_MOTION_X(ix)
    ld b, a
    ld a, FWK_ENTITY_RENDER_X(iy)
    cp b
    jr nz, _pf_behavior_enemy_changed
    ld a, FWK_BEHAVIOR_MOTION_Y(ix)
    ld b, a
    ld a, FWK_ENTITY_RENDER_Y(iy)
    cp b
    jr z, _pf_behavior_enemy_store
_pf_behavior_enemy_changed:
    set 1, FWK_ENTITY_RENDER_FLAGS(iy)
_pf_behavior_enemy_store:
    ld a, FWK_BEHAVIOR_MOTION_X(ix)
    ld FWK_ENTITY_RENDER_X(iy), a
    xor a
    ld FWK_ENTITY_RENDER_X+1(iy), a
    ld a, FWK_BEHAVIOR_MOTION_Y(ix)
    ld FWK_ENTITY_RENDER_Y(iy), a
    ld b, a
    xor a
    ld FWK_ENTITY_RENDER_Y+1(iy), a
    ld a, b
    add a, #PF_ENEMY_HEIGHT_PX
    ld FWK_ENTITY_RENDER_SORT_Y(iy), a
    xor a
    ld FWK_ENTITY_RENDER_SORT_Y+1(iy), a
    ld a, (_pf_anim_frame)
    or a
    jr z, _pf_behavior_enemy_sprite0
    ld hl, #platformer_enemy_pixels2
    jr _pf_behavior_enemy_sprite_set
_pf_behavior_enemy_sprite0:
    ld hl, #platformer_enemy_pixels
_pf_behavior_enemy_sprite_set:
    ld FWK_ENTITY_RENDER_SPRITE_DATA(iy), l
    ld FWK_ENTITY_RENDER_SPRITE_DATA+1(iy), h
    ret

;; Routine: _pf_reset_enemies
;; Description: Resets all behavior records and synchronizes their entities.
;; Input:  none
;; Output: enemy state reset
_pf_reset_enemies:
    xor a
    ld (_platformer_enemy_phase), a
    ld ix, #platformer_enemy_h_behavior
    ld b, #PF_ENEMY_H_START_X
    ld c, #PF_ENEMY_H_Y
    ld hl, #platformer_enemy_h_program
    call _pf_reset_behavior_enemy
    ld iy, #platformer_enemy_h_entity
    call _pf_sync_behavior_enemy
    ld ix, #platformer_enemy_v_behavior
    ld b, #PF_ENEMY_V_X
    ld c, #PF_ENEMY_V_START_Y
    ld hl, #platformer_enemy_v_program
    call _pf_reset_behavior_enemy
    ld iy, #platformer_enemy_v_entity
    call _pf_sync_behavior_enemy
    ld ix, #platformer_enemy_v2_behavior
    ld b, #PF_ENEMY_V2_X
    ld c, #PF_ENEMY_V_START_Y
    ld hl, #platformer_enemy_v_program
    call _pf_reset_behavior_enemy
    ld iy, #platformer_enemy_v2_entity
    jp _pf_sync_behavior_enemy

;; In: IX = behavior record, B/C = initial X/Y, HL = program.
_pf_reset_behavior_enemy:
    ld FWK_BEHAVIOR_MOTION_X(ix), b
    ld FWK_BEHAVIOR_MOTION_Y(ix), c
    xor a
    ld FWK_BEHAVIOR_MOTION_VX(ix), a
    ld FWK_BEHAVIOR_MOTION_VY(ix), a
    ld FWK_BEHAVIOR_MOTION_FLAGS(ix), a
    ld FWK_BEHAVIOR_TIMER(ix), a
    ld FWK_BEHAVIOR_PROGRAM(ix), l
    ld FWK_BEHAVIOR_PROGRAM+1(ix), h
    ret

;; Copy the compact physics state into the render prefix. Only a real position
;; change marks the player dirty; sort_y is its bottom scanline.
;; Copy the compact physics state into the render prefix; mark dirty only on change.
;; Routine: _pf_sync_player_render
;; Description: Copies compact physics state into the render prefix; marks dirty on change.
;; Input:  none
;; Output: render prefix updated
_pf_sync_player_render:
    ld a, (platformer_player+PF_PLAYER_X)
    ld b, a
    ld a, (platformer_player_entity+FWK_ENTITY_RENDER_X)
    cp b
    jr nz, _pf_player_render_changed
    ld a, (platformer_player+PF_PLAYER_Y)
    ld b, a
    ld a, (platformer_player_entity+FWK_ENTITY_RENDER_Y)
    cp b
    jr z, _pf_player_render_store
_pf_player_render_changed:
    ld hl, #platformer_player_entity+FWK_ENTITY_RENDER_FLAGS
    set 1, (hl)
_pf_player_render_store:
    ld a, (platformer_player+PF_PLAYER_X)
    ld (platformer_player_entity+FWK_ENTITY_RENDER_X), a
    xor a
    ld (platformer_player_entity+FWK_ENTITY_RENDER_X+1), a
    ld a, (platformer_player+PF_PLAYER_Y)
    ld (platformer_player_entity+FWK_ENTITY_RENDER_Y), a
    ld l, a
    ld h, #0
    xor a
    ld (platformer_player_entity+FWK_ENTITY_RENDER_Y+1), a
    ld de, #PF_PLAYER_HEIGHT_PX
    add hl, de
    ld (platformer_player_entity+FWK_ENTITY_RENDER_SORT_Y), hl
    ld a, (_pf_anim_frame)
    or a
    jr z, _pf_player_sprite0
    ld hl, #platformer_player_pixels2
    jr _pf_player_sprite_set
_pf_player_sprite0:
    ld hl, #platformer_player_pixels
_pf_player_sprite_set:
    ld (platformer_player_entity+FWK_ENTITY_RENDER_SPRITE_DATA), hl
    ret

_pf_reset_render_flags:
    ld hl, #platformer_render_entities
    ld b, #PF_RENDER_COUNT
_pf_reset_render_loop:
    ld e, (hl)
    inc hl
    ld d, (hl)
    inc hl
    push hl
    push de
    pop iy
    ld FWK_ENTITY_RENDER_FLAGS(iy), #FWK_ENTITY_RENDER_VISIBLE
    pop hl
    djnz _pf_reset_render_loop
    ;; The exit is unlocked only after collecting all four coins.
    ld hl, #platformer_door_entity+FWK_ENTITY_RENDER_FLAGS
    ld (hl), #0
    ret

;; One life is lost on the transition from separated to overlapping for each
;; enemy. A sustained overlap does not drain one life per frame.
;; When all coins are collected, show the door and reset the scene on contact.
;; Routine: _pf_check_door
;; Description: When all coins are collected, shows the door and resets on contact.
;; Input:  none
;; Output: may reset the scene
_pf_check_door:
    ld a, (platformer_status)
    cp #PF_STATUS_WON
    ret nz
    ld a, (platformer_player_entity+FWK_ENTITY_RENDER_X)
    add a, #PF_PLAYER_WIDTH_BYTES
    ld b, a
    ld a, (platformer_door_entity+FWK_ENTITY_RENDER_X)
    cp b
    jp nc, _pf_door_no
    add a, #4
    ld b, a
    ld a, (platformer_player_entity+FWK_ENTITY_RENDER_X)
    cp b
    jp nc, _pf_door_no
    ld a, (platformer_player_entity+FWK_ENTITY_RENDER_Y)
    add a, #PF_PLAYER_HEIGHT_PX
    ld b, a
    ld a, (platformer_door_entity+FWK_ENTITY_RENDER_Y)
    cp b
    jp nc, _pf_door_no
    add a, #8
    ld b, a
    ld a, (platformer_player_entity+FWK_ENTITY_RENDER_Y)
    cp b
    jp nc, _pf_door_no
    ;; Transition: move to the second level when the door is reached on level 1.
    ld a, (platformer_current_level)
    or a
    jr nz, _pf_door_win
    ;; Switch to level 2: restore coins, reset player/enemies and render map 2.
    ld a, #1
    ld (platformer_current_level), a
    ;; Restore coin table entries.
    ld hl, #platformer_coins
    ld (hl), #4
    inc hl
    ld (hl), #3
    inc hl
    inc hl
    inc hl
    inc hl
    ld (hl), #14
    inc hl
    ld (hl), #3
    inc hl
    inc hl
    inc hl
    inc hl
    ld (hl), #4
    inc hl
    ld (hl), #21
    inc hl
    inc hl
    inc hl
    inc hl
    ld (hl), #14
    inc hl
    ld (hl), #21
    ;; Restore coin entities visibility.
    ld hl, #platformer_coin0_entity+FWK_ENTITY_RENDER_FLAGS
    ld (hl), #FWK_ENTITY_RENDER_VISIBLE|FWK_ENTITY_RENDER_DIRTY
    ld hl, #platformer_coin1_entity+FWK_ENTITY_RENDER_FLAGS
    ld (hl), #FWK_ENTITY_RENDER_VISIBLE|FWK_ENTITY_RENDER_DIRTY
    ld hl, #platformer_coin2_entity+FWK_ENTITY_RENDER_FLAGS
    ld (hl), #FWK_ENTITY_RENDER_VISIBLE|FWK_ENTITY_RENDER_DIRTY
    ld hl, #platformer_coin3_entity+FWK_ENTITY_RENDER_FLAGS
    ld (hl), #FWK_ENTITY_RENDER_VISIBLE|FWK_ENTITY_RENDER_DIRTY
    ;; Reset score and player.
    xor a
    ld (platformer_score), a
    ld a, #PF_HUD_DIRTY_SCORE|PF_HUD_DIRTY_LIVES
    ld (platformer_hud_dirty), a
    ld a, #PF_PLAYER_START_X
    ld (platformer_player+PF_PLAYER_X), a
    ld a, #PF_PLAYER_START_Y
    ld (platformer_player+PF_PLAYER_Y), a
    xor a
    ld (platformer_player+PF_PLAYER_VX), a
    ld (platformer_player+PF_PLAYER_VY), a
    ld a, #PF_TILE_GROUNDED
    ld (platformer_player+PF_PLAYER_FLAGS), a
    call _pf_reset_enemies
    call _pf_sync_player_render
    ;; Render the second map.
    call _pf_load_active_map
    call fwk_tilemap_render_view
    call _pf_draw_hud_initial
    ld a, #PF_STATUS_READY
    ld (platformer_status), a
    ld hl, #platformer_door_entity+FWK_ENTITY_RENDER_FLAGS
    ld (hl), #0
    ret
_pf_door_win:
    ;; Final win: hide the door.
    ld a, #PF_STATUS_READY
    ld (platformer_status), a
    ld hl, #platformer_door_entity+FWK_ENTITY_RENDER_FLAGS
    ld (hl), #0
    ret
_pf_door_no:
    ret

;; Detect enemy/player overlaps and remove one life on the transition.
;; Routine: _pf_check_enemy_contacts
;; Description: Detects enemy/player overlaps and removes one life on transition.
;; Input:  none
;; Output: may update lives and status
_pf_check_enemy_contacts:
    ld a, (platformer_status)
    cp #PF_STATUS_WON
    ret z
    xor a
    ld (_platformer_enemy_contacts_next), a
    ld ix, #platformer_enemy_h_entity
    call _pf_player_touches_enemy
    jr nc, _pf_enemy_h_separate
    ld hl, #_platformer_enemy_contacts_next
    set 0, (hl)
    ld a, (platformer_enemy_contacts)
    bit 0, a
    call z, _pf_lose_life
_pf_enemy_h_separate:
    ld ix, #platformer_enemy_v_entity
    call _pf_player_touches_enemy
    jr nc, _pf_enemy_v2_check
    ld hl, #_platformer_enemy_contacts_next
    set 1, (hl)
    ld a, (platformer_enemy_contacts)
    bit 1, a
    call z, _pf_lose_life
_pf_enemy_v2_check:
    ld ix, #platformer_enemy_v2_entity
    call _pf_player_touches_enemy
    jr nc, _pf_enemy_v_separate
    ld hl, #_platformer_enemy_contacts_next
    set 2, (hl)
    ld a, (platformer_enemy_contacts)
    bit 2, a
    call z, _pf_lose_life
_pf_enemy_v_separate:
    ld a, (_platformer_enemy_contacts_next)
    ld (platformer_enemy_contacts), a
    ret

_pf_lose_life:
    ld a, (platformer_lives)
    or a
    ret z
    dec a
    ld (platformer_lives), a
    ld hl, #platformer_hud_dirty
    set 1, (hl)
    ;; Flash the border red three times.
    ld b, #3
_pf_lose_life_flash:
    push bc
    ld l, #16
    ld h, #0x1C
    call cpct_setPALColour_asm
    pop bc
    ld de, #0x1000
_pf_lose_life_delay_red:
    dec de
    ld a, d
    or e
    jr nz, _pf_lose_life_delay_red
    push bc
    ld l, #16
    ld h, #0x14
    call cpct_setPALColour_asm
    pop bc
    ld de, #0x1000
_pf_lose_life_delay_black:
    dec de
    ld a, d
    or e
    jr nz, _pf_lose_life_delay_black
    djnz _pf_lose_life_flash
    ret

;; Half-open AABB test using the synchronized player render prefix and IX enemy.
;; Carry is set only when both axes overlap.
_pf_player_touches_enemy:
    ld a, (platformer_player_entity+FWK_ENTITY_RENDER_X)
    add a, #PF_PLAYER_WIDTH_BYTES
    ld b, a
    ld a, FWK_ENTITY_RENDER_X(ix)
    cp b
    jr nc, _pf_enemy_no_contact
    add a, #PF_ENEMY_WIDTH_BYTES
    ld b, a
    ld a, (platformer_player_entity+FWK_ENTITY_RENDER_X)
    cp b
    jr nc, _pf_enemy_no_contact
    ld a, (platformer_player_entity+FWK_ENTITY_RENDER_Y)
    add a, #PF_PLAYER_HEIGHT_PX
    ld b, a
    ld a, FWK_ENTITY_RENDER_Y(ix)
    cp b
    jr nc, _pf_enemy_no_contact
    add a, #PF_ENEMY_HEIGHT_PX
    ld b, a
    ld a, (platformer_player_entity+FWK_ENTITY_RENDER_Y)
    cp b
    jr nc, _pf_enemy_no_contact
    scf
    ret
_pf_enemy_no_contact:
    or a
    ret

;; Collect coins overlapping the player and update score, HUD and door state.
;; Routine: _pf_collect_coins
;; Description: Collects coins overlapping the player; updates score, HUD and door.
;; Input:  none
;; Output: score/HUD/door may update
_pf_collect_coins:
    ld hl, #platformer_coins
    ld b, #PF_COIN_COUNT
_pf_coin_loop:
    ld a, (hl)
    cp #PF_COIN_REMOVED
    jr z, _pf_coin_next
    push bc
    push hl

    ;; Coin coordinates are stored as tile coordinates and converted to the
    ;; byte/pixel coordinate system used by the compact platform state.
    ld a, (hl)
    sla a
    sla a
    ld c, a
    inc hl
    ld a, (hl)
    sla a
    sla a
    sla a
    ld b, a

    ld a, (platformer_player+PF_PLAYER_X)
    sub c
    jr nc, _pf_coin_dx_positive
    neg
_pf_coin_dx_positive:
    cp #8
    jr nc, _pf_coin_miss
    ld a, (platformer_player+PF_PLAYER_Y)
    sub b
    jr nc, _pf_coin_dy_positive
    neg
_pf_coin_dy_positive:
    cp #8
    jr nc, _pf_coin_miss

    ;; Hide the render entity. restore_dirty recovers its captured tile before
    ;; draw_dirty omits it from the next frame.
    pop hl
    ld (hl), #PF_COIN_REMOVED
    push hl
    ld de, #PF_COIN_ENTITY
    add hl, de
    ld e, (hl)
    inc hl
    ld d, (hl)
    push de
    pop iy
    res 0, FWK_ENTITY_RENDER_FLAGS(iy)
    set 1, FWK_ENTITY_RENDER_FLAGS(iy)

    ld a, (platformer_score)
    inc a
    ld (platformer_score), a
    ld hl, #platformer_hud_dirty
    set 0, (hl)
    ld a, (platformer_score)
    cp #PF_WIN_SCORE
    jr nz, _pf_coin_miss
    ld a, #PF_STATUS_WON
    ld (platformer_status), a
    ld hl, #platformer_door_entity+FWK_ENTITY_RENDER_FLAGS
    ld (hl), #FWK_ENTITY_RENDER_VISIBLE|FWK_ENTITY_RENDER_DIRTY

_pf_coin_miss:
    pop hl
    pop bc
_pf_coin_next:
    ld de, #PF_COIN_STRIDE
    add hl, de
    djnz _pf_coin_loop
    ret

;; Routine: _pf_draw_hud_initial
;; Description: Draws the initial HUD text and digits.
;; Input:  none
;; Output: HUD on screen
_pf_draw_hud_initial:
    xor a
    ld (platformer_hud_dirty), a
    ld hl, #PF_HUD_COINS_Y
    ld c, #PF_HUD_COINS_X
    call fwk_video_get_ptr
    ld iy, #platformer_score_str
    call fwk_text_draw
    ld hl, #PF_HUD_HINT_Y
    ld c, #PF_HUD_HINT_X
    call fwk_video_get_ptr
    ld iy, #platformer_hint_str
    call fwk_text_draw
    ld hl, #PF_HUD_LIVES_Y
    ld c, #PF_HUD_LIVES_X
    call fwk_video_get_ptr
    ld iy, #platformer_life_str
    jp fwk_text_draw

;; Normal score changes restore two tile cells and redraw one glyph. Only the
;; final transition replaces the status text, using its exact tile span.
;; Routine: _pf_update_hud
;; Description: Restores and redraws dirty HUD cells.
;; Input:  none
;; Output: HUD updated
_pf_update_hud:
    ld a, (platformer_hud_dirty)
    ld (_platformer_hud_pending), a
    xor a
    ld (platformer_hud_dirty), a
    ld a, (_platformer_hud_pending)
    bit 0, a
    call nz, _pf_update_hud_score
    ld a, (platformer_status)
    cp #PF_STATUS_WON
    jp z, _pf_draw_win_status
    ld a, (_platformer_hud_pending)
    bit 1, a
    ret z
    jp _pf_update_hud_lives

_pf_update_hud_score:
    ld a, (platformer_score)
    cp #PF_WIN_SCORE
    jr nz, _pf_update_hud_score_normal
    ;; All coins collected: replace "COINS: 4/4" with "ALL COINS".
    ld b, #1
    ld c, #0
_pf_all_coins_restore_row1:
    call _pf_restore_hud_cell
    inc c
    ld a, c
    cp #5
    jr c, _pf_all_coins_restore_row1
    ld b, #2
    ld c, #0
_pf_all_coins_restore_row2:
    call _pf_restore_hud_cell
    inc c
    ld a, c
    cp #5
    jr c, _pf_all_coins_restore_row2
    ld hl, #PF_HUD_COINS_Y
    ld c, #PF_HUD_COINS_X
    call fwk_video_get_ptr
    ld iy, #platformer_all_coins_str
    jp fwk_text_draw
_pf_update_hud_score_normal:
    ld b, #1
    ld c, #3
    call _pf_restore_hud_cell
    ld b, #2
    ld c, #3
    call _pf_restore_hud_cell
    ld a, (platformer_score)
    add a, #48
    ld (platformer_score_digit_str), a
    ld hl, #PF_HUD_COINS_Y
    ld c, #PF_HUD_COINS_X+14
    call fwk_video_get_ptr
    ld iy, #platformer_score_digit_str
    call fwk_text_draw
    ret

_pf_draw_win_status:
    ;; Clear the complete previous hint (x=24..57), not only the shorter
    ;; replacement text. At four bytes per tile this is columns 6..14.
    ld a, #6
    ld (_platformer_hud_column), a
_pf_hud_restore_status:
    ld b, #1
    ld a, (_platformer_hud_column)
    ld c, a
    call _pf_restore_hud_cell
    ld b, #2
    ld a, (_platformer_hud_column)
    ld c, a
    call _pf_restore_hud_cell
    ld a, (_platformer_hud_column)
    inc a
    ld (_platformer_hud_column), a
    cp #15
    jr c, _pf_hud_restore_status
    ld hl, #PF_HUD_HINT_Y
    ld c, #PF_HUD_HINT_X
    call fwk_video_get_ptr
    ld iy, #platformer_win_str
    jp fwk_text_draw

_pf_update_hud_lives:
    ld b, #1
    ld c, #19
    call _pf_restore_hud_cell
    ld b, #2
    ld c, #19
    call _pf_restore_hud_cell
    ld a, (platformer_lives)
    cp #10
    jr nz, _pf_life_single_digit
    ld a, #48+1
    ld (platformer_life_digits_str), a
    ld a, #48
    jr _pf_life_store_units
_pf_life_single_digit:
    ld b, a
    ld a, #48
    ld (platformer_life_digits_str), a
    ld a, b
    add a, #48
_pf_life_store_units:
    ld (platformer_life_digits_str+1), a
    ld hl, #PF_HUD_LIVES_Y
    ld c, #PF_HUD_LIVES_X+12
    call fwk_video_get_ptr
    ld iy, #platformer_life_digits_str
    jp fwk_text_draw

;; Routine: _pf_restore_hud_cell
;; Description: Restores a single HUD tile cell from the map.
;; Input:  B = row, C = column
;; Output: cell restored
_pf_restore_hud_cell:
    push bc
    call _pf_load_active_map
    call fwk_tilemap_render_cell
    pop bc
    jp c, _pf_render_fail
    ret
