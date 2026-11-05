.module example_animation
.include "extensions/animation.inc"

.globl fwk_project_init, fwk_system_wait_frame
.globl fwk_video_init, fwk_video_clear_visible, fwk_video_plot_byte
.globl animation_descriptor

.area _DATA
animation_state:: .ds FWK_ANIM_STATE_SIZE
animation_enabled:: .db 1
animation_changes:: .dw 0
animation_ticks:: .dw 0
animation_frame_value:: .db 0
animation_last_change:: .dw 0
animation_status:: .db 0xA5

;; Regression for descriptors with more than 128 frames: after 128 ticks of a
;; duration-1 animation the cursor must be on frame 128 (an 8-bit frame * 2
;; index wrapped back to frame 0). Frames 0..127 point at wide_low, 128..129
;; at wide_high, so the two cases are told apart by the returned pointer.
animation_wide_status:: .db 0xA5
animation_wide_state: .ds FWK_ANIM_STATE_SIZE
animation_wide_low: .db 0
animation_wide_high: .db 0
animation_wide_descriptor: .db 130, 1
    .rept 128
    .dw animation_wide_low
    .endm
    .dw animation_wide_high, animation_wide_high

.area _CODE
_main::
    call fwk_project_init
    call fwk_video_init
    xor a
    call fwk_video_clear_visible

    call _animation_wide_check

    ld ix, #animation_state
    call fwk_anim_clear
    ld hl, #animation_descriptor
    call fwk_anim_set
    call _animation_draw

_animation_loop:
    call fwk_system_wait_frame
    ld a, (animation_enabled)
    or a
    jr z, _animation_loop

    ld hl, (animation_ticks)
    inc hl
    ld (animation_ticks), hl
    ld ix, #animation_state
    ld hl, #animation_descriptor
    call fwk_anim_set
    call fwk_anim_tick
    jr nc, _animation_loop
    push hl

    ld hl, (animation_ticks)
    ld de, (animation_last_change)
    or a
    sbc hl, de
    ld a, h
    or a
    jr nz, _animation_bad_period
    ld a, l
    cp #4
    jr nz, _animation_bad_period
    ld hl, (animation_ticks)
    ld (animation_last_change), hl

    ld hl, (animation_changes)
    inc hl
    ld (animation_changes), hl
    ld a, h
    or a
    jr nz, _animation_validated
    ld a, l
    cp #4
    jr c, _animation_draw_changed
_animation_validated:
    ld a, #0x5A
    ld (animation_status), a
_animation_draw_changed:
    pop hl
    call _animation_draw
    jr _animation_loop

_animation_bad_period:
    ld a, #0xEE
    ld (animation_status), a
    pop hl
    jr _animation_loop

_animation_wide_check:
    ld ix, #animation_wide_state
    call fwk_anim_clear
    ld hl, #animation_wide_descriptor
    call fwk_anim_set
    ld b, #128
_animation_wide_loop:
    push bc
    ld ix, #animation_wide_state
    call fwk_anim_tick
    pop bc
    djnz _animation_wide_loop
    ld de, #animation_wide_high      ; HL = frame 128 pointer after 128 ticks
    or a
    sbc hl, de
    ld a, #0x5A
    jr z, _animation_wide_done
    ld a, #0xEE
_animation_wide_done:
    ld (animation_wide_status), a
    ret

_animation_draw:
    ld a, (hl)
    ld (animation_frame_value), a
    ld hl, #80
    ld c, #20
    jp fwk_video_plot_byte
