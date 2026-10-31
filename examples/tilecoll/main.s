.module example_tilecoll
.include "extensions/platform_tilemap.inc"

.globl fwk_project_init, fwk_system_wait_frame
.globl fwk_video_init, fwk_video_clear_visible, fwk_video_plot_byte
.globl fwk_physics_platform_step, fwk_platform_tilemap_resolve
.globl cpct_setPALColour_asm

TILECOLL_STEPS = 96

.area _DATA
tilecoll_state::
    .db 20, 60, 0, -8, 2, 4, FWK_PLATFORM_AIRBORNE
FWK_PLATFORM_CONFIG tilecoll_config, 80, 199, 1, 8

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

FWK_TILEMAP_DESCRIPTOR tilecoll_map_descriptor, tilecoll_map, tilecoll_types, 20, 25, 2, 3, 4, 8, 3
tilecoll_steps::  .db 0
tilecoll_hits::   .db 0
tilecoll_status:: .db 0

.area _CODE

_draw_horizontal:
    ;; In: B=length, C=x, L=y, A=packed Mode 0 byte. BC preserved by plot.
    ld e, l
_draw_horizontal_loop:
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

_draw_geometry:
    ld b, #64
    ld c, #0
    ld l, #40
    ld a, #0xAA
    call _draw_horizontal

    ld b, #80
    ld c, #0
    ld l, #160
    ld a, #0xAA
    call _draw_horizontal

    ld b, #120
    ld c, #60
    ld e, #40
_draw_wall:
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

_main::
    call fwk_project_init
    call fwk_video_init
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

_tilecoll_loop:
    call fwk_system_wait_frame
    ld a, (tilecoll_steps)
    cp #TILECOLL_STEPS
    jr nc, _tilecoll_draw

    ld iy, #tilecoll_state
    ld ix, #tilecoll_config
    call fwk_physics_platform_step
    ld iy, #tilecoll_state
    ld ix, #tilecoll_map_descriptor
    call fwk_platform_tilemap_resolve
    ld b, a
    bit FWK_PLATFORM_HIT_CEILING_BIT, b
    jr z, _tilecoll_store_hits
    ld a, #2
    ld (tilecoll_state+FWK_PLATFORM_VX), a
_tilecoll_store_hits:
    ld a, (tilecoll_hits)
    or b
    ld (tilecoll_hits), a

    ld a, (tilecoll_steps)
    inc a
    ld (tilecoll_steps), a
    cp #TILECOLL_STEPS
    jr nz, _tilecoll_draw
    ld a, #0x5A
    ld (tilecoll_status), a

_tilecoll_draw:
    ld a, (tilecoll_state+FWK_PLATFORM_X)
    ld c, a
    ld a, (tilecoll_state+FWK_PLATFORM_Y)
    ld l, a
    ld h, #0
    ld a, #0xF0
    call fwk_video_plot_byte
    jr _tilecoll_loop
