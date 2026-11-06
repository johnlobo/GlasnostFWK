;; ECS adapter from the framework input state to compact platform motion.
.module fwk_ecs_input

.include "ecs_profile.inc"
.include "core/ecs_manager.inc"
.include "extensions/physics_platform.inc"

.globl fwk_input_held, fwk_input_pressed

FWK_ECS_INPUT_LEFT  = 0x01
FWK_ECS_INPUT_RIGHT = 0x02
FWK_ECS_INPUT_JUMP  = 0x04
FWK_ECS_INPUT_SPEED = 2
FWK_ECS_INPUT_JUMP_SPEED = 0xF8
.area _CODE

;; fwk_ecs_system_input
;; In: IX=manager. Input entities use action_mask to opt into the standard
;; left/right/jump actions. The callback preserves IX/IY for system traversal.
fwk_ecs_system_input::
    ;; SDASZ80's short symbol mode can alias long component names; the
    ;; generated profile remains normative, while the mask is encoded here
    ;; explicitly for this adapter.
    ld bc, #0x0008
    ld hl, #_fwk_ecs_input_callback
    jp fwk_ecs_system_run

_fwk_ecs_input_callback:
    push ix
    push iy
    ;; Offsets mirror the generated profile. Keeping these two long symbols
    ;; numeric avoids SDASZ80's legacy short-symbol aliasing.
    ld a, 32(iy)
    ld c, a

    ld a, (fwk_input_held)
    and c
    bit 0, a
    jr z, _fwk_ecs_input_right
    ld ECS_E_MOTION_VELOCITY_X(iy), #-FWK_ECS_INPUT_SPEED
    jr _fwk_ecs_input_jump
_fwk_ecs_input_right:
    bit 1, a
    jr z, _fwk_ecs_input_stop
    ld ECS_E_MOTION_VELOCITY_X(iy), #FWK_ECS_INPUT_SPEED
    jr _fwk_ecs_input_jump
_fwk_ecs_input_stop:
    ld ECS_E_MOTION_VELOCITY_X(iy), #0

_fwk_ecs_input_jump:
    ld a, (fwk_input_pressed)
    and c
    bit 2, a
    jr z, _fwk_ecs_input_done
    bit FWK_PLATFORM_TILE_GROUNDED_BIT, ECS_E_MOTION_FLAGS(iy)
    jr z, _fwk_ecs_input_done
    ld ECS_E_MOTION_VELOCITY_Y(iy), #FWK_ECS_INPUT_JUMP_SPEED
    ;; Only the velocity: the platform step (grounded branch) raises AIRBORNE and
    ;; applies the first -8 move before gravity, like the original platformer.
    set 1, ECS_E_RENDER_FLAGS(iy)
_fwk_ecs_input_done:
    pop iy
    pop ix
    xor a
    ret
