;; ECS 2.0 entity collision: one subject against the targets of a manager.
;; Contract and budget (300 bytes of code, no tables): docs/ecs-abi-2.0.md, 9.
.module fwk_ecs_collision

.include "ecs_profile.inc"
.include "core/ecs_manager.inc"
.include "core/ecs_collision.inc"

;; BUILD REQUIREMENT: X and Y are u8 (the overlap test is 8-bit arithmetic on
;; single-byte fields). With u16 or fixed 8.8 coordinates it would silently
;; compare the wrong byte, so the build stops on the ".error" below.
.if (ECS_X_FORMAT-ECS_FORMAT_U8)|(ECS_Y_FORMAT-ECS_FORMAT_U8)
.error 1
.endif

.area _DATA
_ecscoll_subject: .ds 2          ; subject entity
_ecscoll_mgr:     .ds 2          ; manager of the targets
_ecscoll_chan:    .ds 1          ; state bit (channel) of this pass
_ecscoll_prev:    .ds 1          ; that bit before this pass (0 or the bit)
_ecscoll_hits:    .ds 1          ; contacts found in this pass (0 or not)

.area _CODE

;; fwk_ecs_collide -- see core/ecs_collision.inc.
;; The traversal, validation and lock come from fwk_ecs_system_run, so the
;; callback may mark targets for destruction. Self-modifying: the callback
;; address is patched into the call below (RAM only), like fwk_ecs_system_run.
fwk_ecs_collide::
    ld a, h
    or l
    jr nz, _ecscoll_callback_ok     ; fwk_ecs_system_run only sees our own probe
    ld a, #FWK_ECS_ERR_CALLBACK
    scf
    ret
_ecscoll_callback_ok:
    ld (_ecscoll_call_site+1), hl
    ld (_ecscoll_subject), iy
    ld (_ecscoll_mgr), ix
    ld a, e
    ld (_ecscoll_chan), a
    and ECS_E_COLLISION_CONTACT(iy)
    ld (_ecscoll_prev), a
    xor a
    ld (_ecscoll_hits), a
    ld hl, #_ecscoll_probe
    call fwk_ecs_system_run
    ret c                           ; an error leaves CONTACT untouched
    ld a, (_ecscoll_hits)
    or a
    ld a, (_ecscoll_chan)
    jr z, _ecscoll_clear
    or ECS_E_COLLISION_CONTACT(iy)  ; set this pass's bit
    ld ECS_E_COLLISION_CONTACT(iy), a
    xor a
    ret
_ecscoll_clear:
    cpl
    and ECS_E_COLLISION_CONTACT(iy) ; clear this pass's bit
    ld ECS_E_COLLISION_CONTACT(iy), a
    ld a, (_ecscoll_prev)
    or a
    ret z                           ; was not touching: nothing to report
    ;; It was touching and now is not: one EXIT call without a target.
    push ix
    push iy
    push iy
    pop hl                          ; HL = subject
    ld iy, #0
    ld a, #ECS_COLLISION_EXIT
    call _ecscoll_call_site
    pop iy                          ; the callback may clobber IX/IY
    pop ix
    jr c, _ecscoll_exit_error
    xor a
    ret
_ecscoll_exit_error:
    or a
    ret nz                          ; the callback's own error code
    ld a, #FWK_ECS_ERR_CALLBACK     ; carry with A=0 means CALLBACK, as in a pass
    scf
    ret

;; Called by fwk_ecs_system_run for every ACTIVE target matching the mask:
;; IX=manager, IY=target. Must preserve IX/IY; carry set aborts the pass.
_ecscoll_probe:
    push ix
    push iy
    ld ix, (_ecscoll_subject)       ; IX = subject while testing
    push ix
    pop hl
    push iy
    pop de
    or a
    sbc hl, de
    jr z, _ecscoll_miss             ; the subject never hits itself
    ;; subject.x < target.x + target.w
    ld a, ECS_E_X(iy)
    add a, ECS_E_WIDTH(iy)
    ld b, a
    ld a, ECS_E_X(ix)
    cp b
    jr nc, _ecscoll_miss
    ;; target.x < subject.x + subject.w
    ld a, ECS_E_X(ix)
    add a, ECS_E_WIDTH(ix)
    ld b, a
    ld a, ECS_E_X(iy)
    cp b
    jr nc, _ecscoll_miss
    ;; subject.y < target.y + target.h
    ld a, ECS_E_Y(iy)
    add a, ECS_E_HEIGHT(iy)
    ld b, a
    ld a, ECS_E_Y(ix)
    cp b
    jr nc, _ecscoll_miss
    ;; target.y < subject.y + subject.h
    ld a, ECS_E_Y(ix)
    add a, ECS_E_HEIGHT(ix)
    ld b, a
    ld a, ECS_E_Y(iy)
    cp b
    jr nc, _ecscoll_miss
    ;; Contact.
    ld hl, #_ecscoll_hits
    inc (hl)
    ld a, (_ecscoll_prev)
    or a
    ld a, #ECS_COLLISION_ENTER
    jr z, _ecscoll_report
    ld a, #ECS_COLLISION_STAY
_ecscoll_report:
    ld hl, (_ecscoll_subject)
    ld ix, (_ecscoll_mgr)
    call _ecscoll_call_site
    jr _ecscoll_out
_ecscoll_miss:
    xor a                           ; carry clear: keep walking
_ecscoll_out:
    pop iy
    pop ix
    ret

_ecscoll_call_site:
    call 0                          ; patched with the callback by fwk_ecs_collide
    ret
