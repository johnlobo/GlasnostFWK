.module example_renderorder
.include "video/entity_render.inc"

.globl fwk_project_init, fwk_system_wait_frame
.globl fwk_video_init, fwk_video_clear_visible, fwk_video_get_ptr
.globl fwk_video_plot_byte
.globl cpct_setPALColour_asm
.globl renderorder_batch, renderorder_entries
.globl renderorder_lower, renderorder_upper

.area _DATA
renderorder_lower_pixels:
    .rept 24
        .db 0xAA
    .endm
renderorder_upper_pixels:
    .rept 24
        .db 0xF0
    .endm

renderorder_row_patterns:
    .db 0x11,0x22,0x33,0x44,0x55,0x66
    .db 0x77,0x88,0x99,0x12,0x23,0x34

renderorder_lower_buffer: .ds 24
renderorder_upper_buffer: .ds 24
renderorder_lower:
    FWK_ENTITY_RENDER_PREFIX renderorder_lower_pixels, 22, 42, 4, 6, 10, renderorder_lower_buffer, 24, FWK_ENTITY_RENDER_VISIBLE, 0, 0
renderorder_upper:
    FWK_ENTITY_RENDER_PREFIX renderorder_upper_pixels, 24, 44, 4, 6, 20, renderorder_upper_buffer, 24, FWK_ENTITY_RENDER_VISIBLE, 0, 0
renderorder_entities: .dw renderorder_upper, renderorder_lower
renderorder_entries: .ds 2 * FWK_ENTITY_RENDER_WORK_SIZE
FWK_ENTITY_RENDER_DESCRIPTOR renderorder_batch, renderorder_entities, 2, renderorder_entries, 2

renderorder_command:: .db 0
renderorder_status::  .db 0

.area _CODE

_renderorder_fail:
    ld a, #0xEE
    ld (renderorder_status), a
_renderorder_fail_loop:
    call fwk_system_wait_frame
    jr _renderorder_fail_loop

;; Nonuniform 12x12 backdrop used to prove exact reverse-order restoration.
_renderorder_background:
    ld iy, #renderorder_row_patterns
    ld hl, #40
    ld b, #12
_renderorder_background_row:
    push bc
    push hl
    ld c, #20
    call fwk_video_get_ptr
    ld a, 0(iy)
    ld c, #12
_renderorder_background_byte:
    ld (hl), a
    inc hl
    dec c
    jr nz, _renderorder_background_byte
    inc iy
    pop hl
    inc hl
    pop bc
    djnz _renderorder_background_row
    ret

_renderorder_restore:
    ld ix, #renderorder_batch
    call fwk_entity_render_restore_dirty
    jp c, _renderorder_fail
    ret

_renderorder_draw:
    ld ix, #renderorder_batch
    call fwk_entity_render_draw_dirty
    jp c, _renderorder_fail
    ret

_main::
    call fwk_project_init
    call fwk_video_init
    ld l, #0
    ld h, #0x14
    call cpct_setPALColour_asm
    ld l, #5
    ld h, #0x0A
    call cpct_setPALColour_asm
    ld l, #15
    ld h, #0x13
    call cpct_setPALColour_asm
    xor a
    call fwk_video_clear_visible
    call _renderorder_background

    ld ix, #renderorder_batch
    call fwk_entity_render_init
    jp c, _renderorder_fail

    call _renderorder_restore
    call _renderorder_draw
    ld ix, #renderorder_batch
    call fwk_entity_render_draw_dirty
    jp nc, _renderorder_fail

    ld a, #0xA5
    ld (renderorder_status), a

_renderorder_loop:
    call fwk_system_wait_frame
    ld a, (renderorder_command)
    cp #1
    jr z, _renderorder_command_restore
    cp #2
    jr z, _renderorder_command_move
    cp #3
    jr z, _renderorder_command_final_restore
    jr _renderorder_loop

_renderorder_command_restore:
    ;; Update all render data before restore; both sprites are explicit seeds.
    ld hl, #30
    ld (renderorder_lower+FWK_SPRITE_X), hl
    ld hl, #60
    ld (renderorder_lower+FWK_SPRITE_Y), hl
    ld hl, #renderorder_lower+FWK_ENTITY_RENDER_FLAGS
    set 1, (hl)
    ;; Upper is not marked: overlap closure must propagate DIRTY to it.
    call _renderorder_restore
    xor a
    ld (renderorder_command), a
    ld a, #0x5A
    ld (renderorder_status), a
    jr _renderorder_loop

_renderorder_command_move:
    ;; This background update deliberately occurs between restore and recapture.
    ld hl, #43
    ld c, #23
    ld a, #0x55
    call fwk_video_plot_byte
    call _renderorder_draw
    xor a
    ld (renderorder_command), a
    ld a, #0xC3
    ld (renderorder_status), a
    jr _renderorder_loop

_renderorder_command_final_restore:
    ld hl, #renderorder_lower+FWK_ENTITY_RENDER_FLAGS
    res 0, (hl)
    set 1, (hl)
    ld hl, #renderorder_upper+FWK_ENTITY_RENDER_FLAGS
    res 0, (hl)
    set 1, (hl)
    call _renderorder_restore
    xor a
    ld (renderorder_command), a
    ld a, #0x3C
    ld (renderorder_status), a
    jr _renderorder_loop
