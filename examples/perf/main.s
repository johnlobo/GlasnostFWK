.module example_perf
.include "video/entity_render.inc"
.include "extensions/tilemap_render.inc"

.globl fwk_project_init, fwk_system_wait_frame
.globl fwk_system_frame_count
.globl fwk_video_init, fwk_video_clear_visible
.globl fwk_sprite_draw, fwk_sprite_draw_masked
.globl fwk_sprite_capture, fwk_sprite_restore
.globl fwk_entity_render_init, fwk_entity_render_restore_dirty
.globl fwk_entity_render_draw_dirty
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
perf_entity0: FWK_ENTITY_RENDER_PREFIX perf_batch_sprite_pixels,10,30,4,4,0,perf_batch_buffers+0,16,FWK_ENTITY_RENDER_VISIBLE,0,0
perf_entity1: FWK_ENTITY_RENDER_PREFIX perf_batch_sprite_pixels,10,30,4,4,1,perf_batch_buffers+16,16,FWK_ENTITY_RENDER_VISIBLE|FWK_ENTITY_RENDER_MASKED,0,0
perf_entity2: FWK_ENTITY_RENDER_PREFIX perf_batch_sprite_pixels,10,30,4,4,2,perf_batch_buffers+32,16,FWK_ENTITY_RENDER_VISIBLE|FWK_ENTITY_RENDER_RECOLOR,5,15
perf_entity3: FWK_ENTITY_RENDER_PREFIX perf_batch_sprite_pixels,10,30,4,4,3,perf_batch_buffers+48,16,FWK_ENTITY_RENDER_VISIBLE|FWK_ENTITY_RENDER_MASKED|FWK_ENTITY_RENDER_RECOLOR,5,15
perf_entity4: FWK_ENTITY_RENDER_PREFIX perf_batch_sprite_pixels,10,30,4,4,4,perf_batch_buffers+64,16,FWK_ENTITY_RENDER_VISIBLE,0,0
perf_entity5: FWK_ENTITY_RENDER_PREFIX perf_batch_sprite_pixels,10,30,4,4,5,perf_batch_buffers+80,16,FWK_ENTITY_RENDER_VISIBLE,0,0
perf_entity6: FWK_ENTITY_RENDER_PREFIX perf_batch_sprite_pixels,10,30,4,4,6,perf_batch_buffers+96,16,FWK_ENTITY_RENDER_VISIBLE,0,0
perf_entity7: FWK_ENTITY_RENDER_PREFIX perf_batch_sprite_pixels,10,30,4,4,7,perf_batch_buffers+112,16,FWK_ENTITY_RENDER_VISIBLE,0,0
perf_batch_entities: .dw perf_entity0,perf_entity1,perf_entity2,perf_entity3,perf_entity4,perf_entity5,perf_entity6,perf_entity7
perf_batch_entries:
    .ds 8 * FWK_ENTITY_RENDER_WORK_SIZE
FWK_ENTITY_RENDER_DESCRIPTOR perf_batch, perf_batch_entities, 8, perf_batch_entries, 8

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
    ld hl, #perf_entity0+FWK_ENTITY_RENDER_FLAGS
    ld de, #FWK_ENTITY_RENDER_PREFIX_SIZE
    ld b, #8
_perf_batch_dirty:
    set 1, (hl)
    add hl, de
    djnz _perf_batch_dirty
    ld ix, #perf_batch
    call fwk_entity_render_restore_dirty
    ld ix, #perf_batch
    call fwk_entity_render_draw_dirty
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

    ;; Prepare the entity render list.
    ld ix, #perf_batch
    call fwk_entity_render_init

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

    ;; Scene 6: batch of eight (draw + restore).
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
