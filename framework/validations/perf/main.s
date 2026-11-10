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

;; Batch: eight 4x4 sprites; their capture buffers come from one pool.
perf_batch_sprite_pixels:
    .rept 16
        .db 0xF0
    .endm

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
FWK_ECS_RENDER_POOL perf_batch_pool, 16, PERF_BATCH_COUNT
perf_batch_pools: .dw perf_batch_pool
FWK_ECS_RENDER_SCENE perf_batch, perf_batch_managers, 1, perf_batch_work, PERF_BATCH_COUNT, perf_batch_pools, 1
perf_batch_template: .ds ECS_ENTITY_SIZE
_perf_batch_index: .db 0
_perf_batch_row:   .dw 0

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

;; ----------------------------------------------------------------------------
;; _perf_call
;;   Calls the routine whose address is in HL: the caller does call _perf_call, and the jp makes
;;   the target return straight to the caller.
;;   In : HL=address of the routine to run.
;;   Out: Whatever the target leaves.
;;   Clobbers: none of its own: it is a single jp (hl), so the clobbers are those of the target.
;;   Notes: Registers are passed through to the target unchanged. Costs one jp (hl) of overhead per
;;          iteration, included in every measurement.
;; ----------------------------------------------------------------------------
_perf_call:
    jp (hl)

;; ----------------------------------------------------------------------------
;; _perf_wait_frame_change
;;   Spins until the 16-bit fwk_system_frame_count differs from its value at entry, to start a
;;   measurement on a frame boundary.
;;   In : none. Reads fwk_system_frame_count.
;;   Out: none (HL=count at entry, DE=the new count).
;;   Clobbers: AF, DE, HL.
;;   Notes: Needs the system interrupt to be running to advance the counter; it never returns
;;          otherwise. BC, IX and IY are preserved.
;; ----------------------------------------------------------------------------
_perf_wait_frame_change:
    ld hl, (fwk_system_frame_count)
_perf_wait_frame_loop:
    ;; Compare high bytes first, then low bytes.
    ld de, (fwk_system_frame_count)
    ld a, h
    cp d
    jr nz, _perf_wait_frame_done
    ld a, l
    cp e
    jr z, _perf_wait_frame_loop
_perf_wait_frame_done:
    ret

;; ----------------------------------------------------------------------------
;; _perf_measure
;;   Runs the routine in perf_work for perf_iterations iterations and appends the elapsed frames
;;   and the iteration count to the results table.
;;   In : perf_work=address of the routine (word), perf_iterations=iteration count (word, must
;;          not be 0: 0 would run 65536 times), perf_results_ptr=where to write the next 4
;;          bytes.
;;   Out: At perf_results_ptr: elapsed frames (word, low byte first) then perf_iterations
;;          (word); perf_results_ptr advanced by 4. perf_start, perf_end and perf_remaining are
;;          updated.
;;   Clobbers: AF, BC, DE, HL, IX, IY (the measured routine may use all of them).
;;   Notes: Frames are the difference of fwk_system_frame_count (16 bit, wraps correctly) between start
;;          and end, so the loop overhead is included; scene 0 calibrates it. Interrupts must be
;;          running.
;; ----------------------------------------------------------------------------
_perf_measure:
    call _perf_wait_frame_change
    ld hl, (fwk_system_frame_count)
    ld (perf_start), hl
    ld hl, (perf_iterations)
    ld (perf_remaining), hl
_perf_measure_loop:
    ;; Run the work routine, then count down perf_remaining.
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

    ;; Elapsed frames = end - start (16 bit).
    ld hl, (perf_end)
    ld de, (perf_start)
    or a
    sbc hl, de

    ;; Append frames (low, high) and iterations (low, high) to the table.
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
;; ----------------------------------------------------------------------------
;; _perf_empty
;;   Scene 0: does nothing, so the measurement shows the loop and call overhead.
;;   In : none.
;;   Out: none.
;;   Clobbers: none.
;;   Notes: Preserves every register.
;; ----------------------------------------------------------------------------
_perf_empty:
    ret

;; ----------------------------------------------------------------------------
;; _perf_video_clear
;;   Scene 1: fills every visible video region with the byte 0.
;;   In : none.
;;   Out: Visible regions cleared; hole regions are kept.
;;   Clobbers: AF, BC, DE, HL, IX (fwk_video_clear_visible).
;;   Notes: IY is preserved.
;; ----------------------------------------------------------------------------
_perf_video_clear:
    ;; Fill value 0: black.
    xor a
    call fwk_video_clear_visible
    ret

;; ----------------------------------------------------------------------------
;; _perf_sprite_opaque
;;   Scene 2: draws perf_sprite (6 by 8 bytes at x=20, y=40) with fwk_sprite_draw.
;;   In : none.
;;   Out: Carry set if the descriptor is invalid, clear otherwise (the result of
;;          fwk_sprite_draw).
;;   Clobbers: AF, BC, DE, HL, IX.
;;   Notes: IY is preserved by fwk_sprite_draw.
;; ----------------------------------------------------------------------------
_perf_sprite_opaque:
    ld ix, #perf_sprite
    call fwk_sprite_draw
    ret

;; ----------------------------------------------------------------------------
;; _perf_sprite_masked
;;   Scene 3: draws perf_sprite with fwk_sprite_draw_masked, using the project transparency
;;   table.
;;   In : none.
;;   Out: Carry set if the descriptor is invalid, clear otherwise.
;;   Clobbers: AF, BC, DE, HL, IX.
;;   Notes: Always assembles, but links only when the project enables transparency (fwk_sprite_draw_masked
;;          is defined under that flag; perf/glasnost.manifest.json sets transparency pen 0). IY is preserved.
;; ----------------------------------------------------------------------------
_perf_sprite_masked:
    ld ix, #perf_sprite
    call fwk_sprite_draw_masked
    ret

;; ----------------------------------------------------------------------------
;; _perf_sprite_capture
;;   Scene 4: copies the screen area under perf_sprite into perf_sprite_buffer.
;;   In : none.
;;   Out: Carry as fwk_sprite_capture (clear on success); IY=end of the bytes written.
;;   Clobbers: AF, BC, DE, HL, IX, IY.
;;   Notes: The buffer holds 48 bytes, exactly width * height of the unclipped sprite.
;; ----------------------------------------------------------------------------
_perf_sprite_capture:
    ld ix, #perf_sprite
    ld de, #perf_sprite_buffer
    call fwk_sprite_capture
    ret

;; ----------------------------------------------------------------------------
;; _perf_sprite_restore
;;   Scene 5: writes perf_sprite_buffer back over the screen area of perf_sprite.
;;   In : none. Reads perf_sprite_buffer.
;;   Out: Carry as fwk_sprite_restore (clear on success); IY=end of the bytes read.
;;   Clobbers: AF, BC, DE, HL, IX, IY.
;;   Notes: Reads the 48 bytes that _perf_sprite_capture wrote.
;; ----------------------------------------------------------------------------
_perf_sprite_restore:
    ld ix, #perf_sprite
    ld hl, #perf_sprite_buffer
    call fwk_sprite_restore
    ret

;; ----------------------------------------------------------------------------
;; _perf_batch8
;;   Scene 6: one render frame of the eight-entity batch. Marks every entity DIRTY, then
;;   prepare, restore and draw on scene perf_batch.
;;   In : none. Needs _perf_batch_setup to have created the entities.
;;   Out: Carry clear on success (the last result of fwk_ecs_render_draw). On any error it jumps
;;          to _perf_fail and never returns.
;;   Clobbers: AF, BC, DE, HL, IX, IY.
;;   Notes: DIRTY is set by hand each call, which forces all eight entities through the restore and
;;          draw phases every time.
;; ----------------------------------------------------------------------------
_perf_batch8:
    ld iy, #perf_batch_storage
    ld de, #ECS_ENTITY_SIZE
    ld b, #PERF_BATCH_COUNT
_perf_batch_dirty:
    ;; Force a redraw of all eight entities: set DIRTY (bit 1 of RENDER_FLAGS).
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

;; ----------------------------------------------------------------------------
;; _perf_fail
;;   Stops the measurement run with the ABI error code, so the host sees a status that is never
;;   0x5A.
;;   In : A=ABI error code from a failed render or ECS call.
;;   Out: perf_status = A. Never returns.
;;   Clobbers: all (never returns).
;;   Notes: Idles with fwk_system_wait_frame, one vsync per pass.
;; ----------------------------------------------------------------------------
_perf_fail:
    ld (perf_status), a
_perf_fail_loop:
    ;; Idle forever, one vsync per pass.
    call fwk_system_wait_frame
    jr _perf_fail_loop

;; ----------------------------------------------------------------------------
;; _perf_batch_setup
;;   Initializes perf_batch_manager and creates the eight batch entities at (10, 30), 4x4 bytes,
;;   from the rows of perf_batch_rows.
;;   In : none. Reads perf_batch_rows (extra render flags, source pen, replacement pen per
;;          entity).
;;   Out: Eight ACTIVE|RENDER entities in the manager, carry clear. On an ECS error it jumps to
;;          _perf_fail and never returns.
;;   Clobbers: AF, BC, DE, HL, IX, IY.
;;   Notes: Zeroes perf_batch_template before every entity, so the background pointer starts at 0 and
;;          the pool provides the buffers. Updates _perf_batch_index and _perf_batch_row.
;; ----------------------------------------------------------------------------
_perf_batch_setup:
    ld ix, #perf_batch_manager
    call fwk_ecs_manager_init
    jp c, _perf_fail
    xor a
    ld (_perf_batch_index), a
    ld hl, #perf_batch_rows
    ld (_perf_batch_row), hl
_perf_batch_create:
    ;; Zero the template, then fill it for the next row.
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
    ;; Row bytes: extra render flags (OR 3 = VISIBLE | DIRTY), source pen, replacement pen.
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

;; ----------------------------------------------------------------------------
;; _perf_tilemap_full
;;   Scene 7: draws the whole 5x4 tile viewport perf_view of perf_tilemap.
;;   In : none.
;;   Out: Carry as fwk_tilemap_render_view (clear on success).
;;   Clobbers: AF, BC, DE, HL, IX, IY.
;;   Notes: IX and IY are loaded here; fwk_tilemap_render_view itself preserves them.
;; ----------------------------------------------------------------------------
_perf_tilemap_full:
    ld ix, #perf_tilemap
    ld iy, #perf_view
    call fwk_tilemap_render_view
    ret

;; ----------------------------------------------------------------------------
;; _perf_tilemap_cell
;;   Scene 8: redraws the single tile at viewport row 1, column 2.
;;   In : none.
;;   Out: Carry as fwk_tilemap_render_cell (clear on success).
;;   Clobbers: AF, BC, DE, HL, IX, IY.
;;   Notes: B and C are loaded here with row and column; IX and IY are loaded here and preserved by
;;          fwk_tilemap_render_cell.
;; ----------------------------------------------------------------------------
_perf_tilemap_cell:
    ld ix, #perf_tilemap
    ld iy, #perf_view
    ld b, #1
    ld c, #2
    call fwk_tilemap_render_cell
    ret

;; ----------------------------------------------------------------------------
;; _main
;;   Program entry. Sets up the batch entities, then measures nine scenes in order and leaves
;;   the results in perf_results for the host.
;;   In : none.
;;   Out: perf_results holds 9 entries of (frames, iterations), word each; perf_status = 0x5A
;;          when done. Never returns: it idles in _perf_idle (or in _perf_fail).
;;   Clobbers: all (never returns).
;;   Notes: Ends in the _perf_idle loop (or _perf_fail).
;; ----------------------------------------------------------------------------
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

    ;; Measurements finished: idle forever; the host reads perf_results and perf_status.
_perf_idle:
    call fwk_system_wait_frame
    jr _perf_idle
