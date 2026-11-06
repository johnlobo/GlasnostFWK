.module example_perf
.include "video/sprite.inc"
.include "ecs_profile.inc"
.include "core/ecs_manager.inc"
.include "video/ecs_render.inc"
.include "extensions/tilemap_render.inc"

.globl fwk_project_init, fwk_system_wait_frame
.globl fwk_system_frame_count
.globl fwk_video_init, fwk_video_clear_visible
.globl fwk_sprite_draw, fwk_sprite_draw_masked
.globl fwk_sprite_capture, fwk_sprite_restore
.globl fwk_tilemap_render_view, fwk_tilemap_render_cell
.globl cpct_setPALColour_asm

.area _DATA
;; Small opaque and masked sprite.
perf_sprite_pixels:
    .rept 48
        .db 0xAA
    .endm
FWK_SPRITE_DESCRIPTOR perf_sprite, perf_sprite_pixels, 20, 40, 6, 8

;; Batch: eight 4x4 sprites and their capture buffers.
perf_batch_sprite_pixels:
    .rept 16
        .db 0xF0
    .endm
perf_batch_buffers:
    .ds 8 * 16

;; One ECS manager with eight render entities at the same spot; row = extra render
;; flags (8 MASKED, 0x10 RECOLOR), source pen, replacement pen.
PERF_BATCH_COUNT = 8
perf_batch_rows:
    .db 0, 0, 0
    .db 8, 0, 0
    .db 0x10, 5, 15
    .db 8 | 0x10, 5, 15
    .db 0, 0, 0
    .db 0, 0, 0
    .db 0, 0, 0
    .db 0, 0, 0
perf_batch_storage: .ds ECS_ENTITY_SIZE * PERF_BATCH_COUNT
FWK_ECS_MANAGER_DESCRIPTOR perf_batch_manager, perf_batch_storage, PERF_BATCH_COUNT
perf_batch_managers: .dw perf_batch_manager
perf_batch_work: .ds 8 * PERF_BATCH_COUNT
FWK_ECS_RENDER_SCENE perf_batch, perf_batch_managers, 1, perf_batch_work, PERF_BATCH_COUNT
perf_batch_template: .ds ECS_ENTITY_SIZE
_perf_batch_index: .db 0
_perf_batch_row:   .dw 0
_perf_batch_bg:    .dw 0

;; Tilemap fixture: 8x6 map, 4x4 tiles, 5x4 viewport.
perf_tilemap_types:
    .db FWK_TILE_PASSABLE, FWK_TILE_SOLID, FWK_TILE_ONE_WAY, FWK_TILE_PASSABLE
perf_tilemap_map:
    .db 0,1,2,3,0,1,2,3
    .db 1,2,3,0,1,2,3,0
    .db 2,3,0,1,2,3,0,1
    .db 3,0,1,2,3,0,1,2
    .db 0,1,2,3,0,1,2,3
    .db 1,2,3,0,1,2,3,0
FWK_TILEMAP_DESCRIPTOR perf_tilemap, perf_tilemap_map, perf_tilemap_types, 8, 6, 2, 2, 4, 4, 4
perf_tileset:
    .rept 4 * 16
        .db 0xAA
    .endm
FWK_TILE_RENDER_DESCRIPTOR perf_view, perf_tileset, 0, 0, 12, 20, 5, 4, 4

;; Measurement state.
perf_work::       .dw 0
perf_iterations:: .dw 0
perf_remaining::  .dw 0
perf_start::      .dw 0
perf_end::        .dw 0
perf_results_ptr::.dw 0
perf_status::     .db 0

;; 9 scenes x 4 bytes: frames (2), iterations (2).
perf_results::    .ds 9 * 4

;; Buffers for sprite capture/restore.
perf_sprite_buffer:: .ds 48

.area _CODE

;; Indirect call to the routine whose address is in HL.
_perf_call:
    jp (hl)

;; Wait until the 16-bit frame counter changes once.
_perf_wait_frame_change:
    ld hl, (fwk_system_frame_count)
_perf_wait_frame_loop:
    ld de, (fwk_system_frame_count)
    ld a, h
    cp d
    jr nz, _perf_wait_frame_done
    ld a, l
    cp e
    jr z, _perf_wait_frame_loop
_perf_wait_frame_done:
    ret

;; Run the routine in perf_work for perf_iterations iterations and store
;; frames/iterations in perf_results through perf_results_ptr.
_perf_measure:
    call _perf_wait_frame_change
    ld hl, (fwk_system_frame_count)
    ld (perf_start), hl
    ld hl, (perf_iterations)
    ld (perf_remaining), hl
_perf_measure_loop:
    ld hl, (perf_work)
    call _perf_call
    ld hl, (perf_remaining)
    dec hl
    ld (perf_remaining), hl
    ld a, h
    or l
    jr nz, _perf_measure_loop
    ld hl, (fwk_system_frame_count)
    ld (perf_end), hl

    ld hl, (perf_end)
    ld de, (perf_start)
    or a
    sbc hl, de

    ld de, (perf_results_ptr)
    ld a, l
    ld (de), a
    inc de
    ld a, h
    ld (de), a
    inc de
    ld hl, (perf_iterations)
    ld a, l
    ld (de), a
    inc de
    ld a, h
    ld (de), a
    inc de
    ld (perf_results_ptr), de
    ret

;; Scene routines.
_perf_empty:
    ret

_perf_video_clear:
    xor a
    call fwk_video_clear_visible
    ret

_perf_sprite_opaque:
    ld ix, #perf_sprite
    call fwk_sprite_draw
    ret

_perf_sprite_masked:
    ld ix, #perf_sprite
    call fwk_sprite_draw_masked
    ret

_perf_sprite_capture:
    ld ix, #perf_sprite
    ld de, #perf_sprite_buffer
    call fwk_sprite_capture
    ret

_perf_sprite_restore:
    ld ix, #perf_sprite
    ld hl, #perf_sprite_buffer
    call fwk_sprite_restore
    ret

_perf_batch8:
    ld iy, #perf_batch_storage
    ld de, #ECS_ENTITY_SIZE
    ld b, #PERF_BATCH_COUNT
_perf_batch_dirty:
    set 1, ECS_E_RENDER_FLAGS(iy)
    add iy, de
    djnz _perf_batch_dirty
    ld ix, #perf_batch
    call fwk_ecs_render_prepare
    jp c, _perf_fail
    ld ix, #perf_batch
    call fwk_ecs_render_restore
    jp c, _perf_fail
    ld ix, #perf_batch
    call fwk_ecs_render_draw
    jp c, _perf_fail
    ret

;; Stop with the ABI error code in perf_status (never 0x5A).
_perf_fail:
    ld (perf_status), a
_perf_fail_loop:
    call fwk_system_wait_frame
    jr _perf_fail_loop

;; Create the eight entities from perf_batch_rows.
_perf_batch_setup:
    ld ix, #perf_batch_manager
    call fwk_ecs_manager_init
    jp c, _perf_fail
    xor a
    ld (_perf_batch_index), a
    ld hl, #perf_batch_rows
    ld (_perf_batch_row), hl
    ld hl, #perf_batch_buffers
    ld (_perf_batch_bg), hl
_perf_batch_create:
    ld hl, #perf_batch_template
    ld de, #perf_batch_template + 1
    ld (hl), #0
    ld bc, #ECS_ENTITY_SIZE - 1
    ldir
    ld iy, #perf_batch_template
    ld ECS_E_COMPONENTS(iy), #<ECS_C_RENDER
    ld ECS_E_COMPONENTS+1(iy), #>ECS_C_RENDER
    ld ECS_E_STATUS(iy), #ECS_STATUS_ACTIVE
    ld ECS_E_X(iy), #10
    ld ECS_E_Y(iy), #30
    ld ECS_E_WIDTH(iy), #4
    ld ECS_E_HEIGHT(iy), #4
    ld ECS_E_RENDER_SPRITE(iy), #<perf_batch_sprite_pixels
    ld ECS_E_RENDER_SPRITE+1(iy), #>perf_batch_sprite_pixels
    ld hl, (_perf_batch_bg)
    ld ECS_E_RENDER_BACKGROUND(iy), l
    ld ECS_E_RENDER_BACKGROUND+1(iy), h
    ld de, #16
    add hl, de
    ld (_perf_batch_bg), hl
    ld ECS_E_RENDER_BACKGROUND_CAP(iy), #16
    ld hl, (_perf_batch_row)
    ld a, (hl)
    or #3                                   ; VISIBLE | DIRTY
    ld ECS_E_RENDER_FLAGS(iy), a
    inc hl
    ld a, (hl)
    ld ECS_E_RENDER_SOURCE_PEN(iy), a
    inc hl
    ld a, (hl)
    ld ECS_E_RENDER_REPLACEMENT_PEN(iy), a
    inc hl
    ld (_perf_batch_row), hl
    ld ix, #perf_batch_manager
    ld hl, #perf_batch_template
    call fwk_ecs_entity_create
    jp c, _perf_fail
    ld hl, #_perf_batch_index
    inc (hl)
    ld a, (hl)
    cp #PERF_BATCH_COUNT
    jr nz, _perf_batch_create
    ret

_perf_tilemap_full:
    ld ix, #perf_tilemap
    ld iy, #perf_view
    call fwk_tilemap_render_view
    ret

_perf_tilemap_cell:
    ld ix, #perf_tilemap
    ld iy, #perf_view
    ld b, #1
    ld c, #2
    call fwk_tilemap_render_cell
    ret

_main::
    call fwk_project_init
    call fwk_video_init

    ;; Create the render entities.
    call _perf_batch_setup

    ;; Results start at the beginning of the table.
    ld hl, #perf_results
    ld (perf_results_ptr), hl

    ;; Scene 0: empty loop calibration.
    ld hl, #_perf_empty
    ld (perf_work), hl
    ld hl, #20000
    ld (perf_iterations), hl
    call _perf_measure

    ;; Scene 1: full visible clear.
    ld hl, #_perf_video_clear
    ld (perf_work), hl
    ld hl, #100
    ld (perf_iterations), hl
    call _perf_measure

    ;; Scene 2: opaque sprite.
    ld hl, #_perf_sprite_opaque
    ld (perf_work), hl
    ld hl, #4000
    ld (perf_iterations), hl
    call _perf_measure

    ;; Scene 3: masked sprite.
    ld hl, #_perf_sprite_masked
    ld (perf_work), hl
    ld hl, #2500
    ld (perf_iterations), hl
    call _perf_measure

    ;; Scene 4: capture.
    ld hl, #_perf_sprite_capture
    ld (perf_work), hl
    ld hl, #4000
    ld (perf_iterations), hl
    call _perf_measure

    ;; Scene 5: restore.
    ld hl, #_perf_sprite_restore
    ld (perf_work), hl
    ld hl, #4000
    ld (perf_iterations), hl
    call _perf_measure

    ;; Scene 6: batch of eight (prepare + restore + draw).
    ld hl, #_perf_batch8
    ld (perf_work), hl
    ld hl, #500
    ld (perf_iterations), hl
    call _perf_measure

    ;; Scene 7: full tilemap viewport.
    ld hl, #_perf_tilemap_full
    ld (perf_work), hl
    ld hl, #300
    ld (perf_iterations), hl
    call _perf_measure

    ;; Scene 8: single tile update.
    ld hl, #_perf_tilemap_cell
    ld (perf_work), hl
    ld hl, #5000
    ld (perf_iterations), hl
    call _perf_measure

    ld a, #0x5A
    ld (perf_status), a

_perf_idle:
    call fwk_system_wait_frame
    jr _perf_idle
