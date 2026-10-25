;; Entity-independent looping animation cursor, extracted from model01's
;; descriptor/timer mechanism. Movement and render policy stay in the caller.
.module fwk_animation
.include "extensions/animation.inc"

.area _CODE

;; fwk_anim_clear
;; In: IX=state. Out: HL=0, carry clear. Modified: AF,HL.
fwk_anim_clear::
    xor a
    ld FWK_ANIM_STATE_DESCRIPTOR(ix), a
    ld FWK_ANIM_STATE_DESCRIPTOR+1(ix), a
    ld FWK_ANIM_STATE_FRAME(ix), a
    ld FWK_ANIM_STATE_REMAINING(ix), a
    ld hl, #0
    ret

;; Internal: returns the current frame pointer for descriptor HL and state IX.
;; Modified: AF,BC,DE,HL. Carry clear.
_fwk_anim_current:
    ld a, FWK_ANIM_STATE_FRAME(ix)
    add a, a
    ld e, a
    ld d, #0
    ld bc, #FWK_ANIM_DESC_FRAMES
    add hl, bc
    add hl, de
    ld e, (hl)
    inc hl
    ld d, (hl)
    ex de, hl
    or a
    ret

;; fwk_anim_set
;; In: IX=state, HL=descriptor or 0.
;; Out: HL=current frame pointer or 0; carry set only when descriptor changed.
;; Re-selecting the active descriptor preserves its frame and timer.
;; Modified: AF,BC,DE,HL. Descriptor count/duration must both be non-zero.
fwk_anim_set::
    ld a, FWK_ANIM_STATE_DESCRIPTOR(ix)
    cp l
    jr nz, _fwk_anim_set_change
    ld a, FWK_ANIM_STATE_DESCRIPTOR+1(ix)
    cp h
    jr nz, _fwk_anim_set_change
    ld a, h
    or l
    ret z
    jp _fwk_anim_current

_fwk_anim_set_change:
    ld FWK_ANIM_STATE_DESCRIPTOR(ix), l
    ld FWK_ANIM_STATE_DESCRIPTOR+1(ix), h
    xor a
    ld FWK_ANIM_STATE_FRAME(ix), a
    ld a, h
    or l
    jr z, _fwk_anim_set_null
    inc hl
    ld a, (hl)
    ld FWK_ANIM_STATE_REMAINING(ix), a
    dec hl
    call _fwk_anim_current
    scf
    ret

_fwk_anim_set_null:
    ld FWK_ANIM_STATE_REMAINING(ix), a
    ld hl, #0
    scf
    ret

;; fwk_anim_tick
;; In: IX=state.
;; Out: HL=current frame pointer or 0; carry set only when frame advanced.
;; One call is one policy-defined tick; this routine has no VSYNC dependency.
;; Modified: AF,BC,DE,HL.
fwk_anim_tick::
    ld l, FWK_ANIM_STATE_DESCRIPTOR(ix)
    ld h, FWK_ANIM_STATE_DESCRIPTOR+1(ix)
    ld a, h
    or l
    ret z

    ld a, FWK_ANIM_STATE_REMAINING(ix)
    dec a
    ld FWK_ANIM_STATE_REMAINING(ix), a
    jp nz, _fwk_anim_current

    push hl
    inc hl
    ld a, (hl)
    ld FWK_ANIM_STATE_REMAINING(ix), a
    pop hl

    ld a, FWK_ANIM_STATE_FRAME(ix)
    inc a
    ld b, (hl)
    cp b
    jr c, _fwk_anim_tick_store
    xor a
_fwk_anim_tick_store:
    ld FWK_ANIM_STATE_FRAME(ix), a
    call _fwk_anim_current
    scf
    ret
