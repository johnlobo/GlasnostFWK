.module example_tilecoll
.include "extensions/platform_tilemap.inc"

.globl fwk_project_init, fwk_system_wait_frame
.globl fwk_video_init, fwk_video_clear_visible, fwk_video_plot_byte
.globl fwk_physics_platform_step, fwk_platform_tilemap_resolve
.globl cpct_setPALColour_asm

TILECOLL_STEPS = 96

.area _DATA
;; Platform state (physics_platform.inc): x=20, y=60, vx=0, vy=-8 (rising), width=2,
;; height=4, flags=airborne.
tilecoll_state::
    .db 20, 60, 0, -8, 2, 4, FWK_PLATFORM_AIRBORNE
;; Configuration: world width 80, ground y 199, gravity 1, max fall speed 8.
FWK_PLATFORM_CONFIG tilecoll_config, 80, 199, 1, 8

; Tile id -> behaviour: id 0 passable, id 1 solid, id 2 one-way.
tilecoll_types:
    .db FWK_TILE_PASSABLE, FWK_TILE_SOLID, FWK_TILE_ONE_WAY

;; 20x25 tiles, 4 bytes x 8 pixels. Ceiling row 5, wall column 15 and
;; floor row 20 are solid; everything else is passable.
tilecoll_map:
    .rept 100
        .db 0
    .endm
    .rept 16
        .db 1
    .endm
    .rept 4
        .db 0
    .endm
    .rept 14
        .rept 15
            .db 0
        .endm
        .db 1
        .rept 4
            .db 0
        .endm
    .endm
    .rept 20
        .db 1
    .endm
    .rept 80
        .db 0
    .endm

;; 20x25 tiles; shifts 2 and 3 (4 bytes x 8 scanlines per tile); 3 tile types.
FWK_TILEMAP_DESCRIPTOR tilecoll_map_descriptor, tilecoll_map, tilecoll_types, 20, 25, 2, 3, 4, 8, 3
tilecoll_steps::  .db 0          ; physics steps run so far (stops at TILECOLL_STEPS)
tilecoll_hits::   .db 0          ; OR of every FWK_PLATFORM_HIT_* mask seen
tilecoll_status:: .db 0          ; 0x5A once all steps have run

.area _CODE

;; ----------------------------------------------------------------------------
;; _draw_horizontal
;;   Draws a horizontal run of one Mode 0 byte, one byte per column, on scanline y.
;;   In : B=length in bytes (must be 1..255; 0 would draw 256), C=x byte of the
;;        first column, L=y scanline, A=packed Mode 0 byte to write.
;;   Out: A preserved. B=0, C=x+length, E=y.
;;   Clobbers: F, BC, E, HL
;;   Notes: D and A are preserved. B ends at 0 and C at x+length. fwk_video_plot_byte
;;          (AF, DE, HL) is shielded by pushing AF, BC and DE around each call; HL is
;;          not restored, so it holds the last screen address.
;; ----------------------------------------------------------------------------
_draw_horizontal:
    ld e, l                         ; E keeps y: HL is rebuilt every column
_draw_horizontal_loop:              ; one column per iteration
    push bc
    push de
    push af
    ld l, e
    ld h, #0
    call fwk_video_plot_byte
    pop af
    pop de
    pop bc
    inc c
    djnz _draw_horizontal_loop
    ret

;; ----------------------------------------------------------------------------
;; _draw_geometry
;;   Draws the level on screen to match tilecoll_map: ceiling (row 5), floor
;;   (row 20) and wall (column 15, rows 5 to 19) in byte 0xAA.
;;   In : none.
;;   Out: none.
;;   Clobbers: AF, BC, E, HL
;;   Notes: D is preserved. Positions are the map tiles times 4 bytes and 8 scanlines:
;;          ceiling y=40, x 0..63; floor y=160, x 0..79; wall x=60, y 40..159. On return
;;          A=0xAA, B=0.
;; ----------------------------------------------------------------------------
_draw_geometry:
    ld b, #64                       ; ceiling: 16 tiles x 4 bytes at y=40
    ld c, #0
    ld l, #40
    ld a, #0xAA
    call _draw_horizontal

    ld b, #80                       ; floor: full 80-byte line at y=160
    ld c, #0
    ld l, #160
    ld a, #0xAA
    call _draw_horizontal

    ld b, #120                      ; wall: 120 scanlines, x=60, from y=40
    ld c, #60
    ld e, #40
_draw_wall:                         ; one scanline per iteration, E=y
    push bc
    push de
    ld l, e
    ld h, #0
    ld a, #0xAA
    call fwk_video_plot_byte
    pop de
    pop bc
    inc e
    djnz _draw_wall
    ret

;; ----------------------------------------------------------------------------
;; _main
;;   Program entry. Sets the palette, draws the level, then each frame runs one
;;   platform physics step and tile collision resolve (for the first
;;   TILECOLL_STEPS frames) and plots the entity.
;;   In : none.
;;   Out: never returns. tilecoll_hits collects the collision masks and
;;        tilecoll_status becomes 0x5A after the last step.
;;   Clobbers: all (never returns)
;;   Notes: The entity is never erased, so it leaves a trail of 0xF0 bytes. A ceiling
;;          hit sets vx to 2 so the entity then travels right towards the wall. Calls
;;          into the platform physics and tilemap resolve routines, whose clobbers are
;;          not relied on here.
;; ----------------------------------------------------------------------------
_main::
    call fwk_project_init
    call fwk_video_init
    ;; Palette: L=pen, H=hardware colour.
    ld l, #0
    ld h, #0x14              ; HW_BLACK
    call cpct_setPALColour_asm
    ld l, #5
    ld h, #0x0A              ; HW_BRIGHT_YELLOW
    call cpct_setPALColour_asm
    ld l, #15
    ld h, #0x13              ; HW_BRIGHT_CYAN
    call cpct_setPALColour_asm
    xor a
    call fwk_video_clear_visible
    call _draw_geometry

_tilecoll_loop:                     ; one iteration per frame
    call fwk_system_wait_frame
    ld a, (tilecoll_steps)
    cp #TILECOLL_STEPS
    jr nc, _tilecoll_draw           ; all steps done: only keep drawing

    ;; Move the entity (gravity, bounds) and then push it out of solid tiles.
    ld iy, #tilecoll_state
    ld ix, #tilecoll_config
    call fwk_physics_platform_step
    ld iy, #tilecoll_state
    ld ix, #tilecoll_map_descriptor
    call fwk_platform_tilemap_resolve
    ld b, a                         ; B = hit mask of this step
    bit FWK_PLATFORM_HIT_CEILING_BIT, b
    jr z, _tilecoll_store_hits
    ld a, #2                        ; ceiling bump: start moving right
    ld (tilecoll_state+FWK_PLATFORM_VX), a
_tilecoll_store_hits:               ; accumulate every hit seen for the test
    ld a, (tilecoll_hits)
    or b
    ld (tilecoll_hits), a

    ld a, (tilecoll_steps)
    inc a
    ld (tilecoll_steps), a
    cp #TILECOLL_STEPS
    jr nz, _tilecoll_draw
    ld a, #0x5A                     ; last step done
    ld (tilecoll_status), a

_tilecoll_draw:                     ; plot the entity at its current x, y
    ld a, (tilecoll_state+FWK_PLATFORM_X)
    ld c, a
    ld a, (tilecoll_state+FWK_PLATFORM_Y)
    ld l, a
    ld h, #0
    ld a, #0xF0
    call fwk_video_plot_byte
    jr _tilecoll_loop
