;; ECS 2.0 entity animation. Contract and budget (150 bytes of code, no data):
;; docs/ecs-abi-2.0.md, 10.
.module fwk_ecs_animation

.include "ecs_profile.inc"
.include "core/ecs_manager.inc"
.include "core/ecs_animation.inc"

;; The DIRTY flag below is set by bit number: keep it tied to the ABI constant.
.if (ECS_RENDER_DIRTY-0x02)
.error 1
.endif

.area _CODE

;; fwk_ecs_system_animation -- see core/ecs_animation.inc.
fwk_ecs_system_animation::
    ld bc, #ECS_C_ANIMATION
    ld hl, #_ecsanim_tick
    jp fwk_ecs_system_run

;; Called by fwk_ecs_system_run for every ACTIVE|ANIMATION entity (IY).
;; Must keep IX/IY; carry clear continues.
_ecsanim_tick:
    ld l, ECS_E_ANIMATION_DESCRIPTOR(iy)
    ld h, ECS_E_ANIMATION_DESCRIPTOR+1(iy)
    ld a, h
    or l
    jr z, _ecsanim_idle             ; no descriptor: nothing to do
    dec ECS_E_ANIMATION_TIMER(iy)
    jr nz, _ecsanim_idle
    inc hl
    ld a, (hl)                      ; reload the duration
    ld ECS_E_ANIMATION_TIMER(iy), a
    dec hl
    ld a, ECS_E_ANIMATION_FRAME(iy)
    inc a
    cp (hl)                         ; next frame < count ?
    jr c, _ecsanim_show
    xor a                           ; wrap to frame 0
    ;; falls into _ecsanim_show

;; In: IY=entity, HL=descriptor, A=frame. Stores the frame, points the render
;; sprite at it and marks DIRTY. Out: carry clear, A=0.
_ecsanim_show:
    ld ECS_E_ANIMATION_FRAME(iy), a
    ld e, a
    ld d, #0                        ; 16-bit index: counts above 128 are valid
    inc hl
    inc hl                          ; HL = frame pointer table
    add hl, de
    add hl, de                      ; two bytes per pointer
    ld e, (hl)
    inc hl
    ld d, (hl)
    ld ECS_E_RENDER_SPRITE(iy), e
    ld ECS_E_RENDER_SPRITE+1(iy), d
    set 1, ECS_E_RENDER_FLAGS(iy)   ; ECS_RENDER_DIRTY
_ecsanim_idle:
    xor a
    ret

;; fwk_ecs_anim_set -- see core/ecs_animation.inc.
fwk_ecs_anim_set::
    ld a, ECS_E_ANIMATION_DESCRIPTOR(iy)
    cp l
    jr nz, _ecsanim_change
    ld a, ECS_E_ANIMATION_DESCRIPTOR+1(iy)
    cp h
    jr nz, _ecsanim_change
    ld a, ECS_E_ANIMATION_TIMER(iy)
    or a
    jr z, _ecsanim_change           ; timer 0 = not started (e.g. a template): start it
    xor a                           ; already running: keep frame and timer
    ret
_ecsanim_change:
    ld ECS_E_ANIMATION_DESCRIPTOR(iy), l
    ld ECS_E_ANIMATION_DESCRIPTOR+1(iy), h
    ld a, h
    or l
    jr z, _ecsanim_stop
    inc hl
    ld a, (hl)
    ld ECS_E_ANIMATION_TIMER(iy), a
    dec hl
    xor a
    jr _ecsanim_show
_ecsanim_stop:
    ld ECS_E_ANIMATION_FRAME(iy), a ; A = 0
    ld ECS_E_ANIMATION_TIMER(iy), a
    ret
