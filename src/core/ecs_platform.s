;; ECS adapter for the existing platform physics and tilemap resolver.
.module fwk_ecs_platform

.include "ecs_profile.inc"
.include "core/ecs_manager.inc"
.include "extensions/physics_platform.inc"
.include "extensions/tilemap.inc"

.globl fwk_physics_platform_step, fwk_platform_tilemap_resolve

.area _DATA
_fwk_ecs_platform_scratch:: .ds FWK_PLATFORM_STATE_SIZE

.area _CODE

;; fwk_ecs_system_platform
;; In: IX=manager. PLATFORM entities store pointers to a 4-byte physics config
;; and an 11-byte tilemap descriptor. The adapter copies the AoS entity fields
;; into the legacy state, resolves physics/collision, then copies them back.
fwk_ecs_system_platform::
    ld bc, #0x0010
    ld hl, #_fwk_ecs_platform_callback
    jp fwk_ecs_system_run

_fwk_ecs_platform_callback:
    push ix
    push iy
    ld a, ECS_E_X(iy)
    ld (_fwk_ecs_platform_scratch + FWK_PLATFORM_X), a
    ld a, ECS_E_Y(iy)
    ld (_fwk_ecs_platform_scratch + FWK_PLATFORM_Y), a
    ld a, ECS_E_MOTION_VELOCITY_X(iy)
    ld (_fwk_ecs_platform_scratch + FWK_PLATFORM_VX), a
    ld a, ECS_E_MOTION_VELOCITY_Y(iy)
    ld (_fwk_ecs_platform_scratch + FWK_PLATFORM_VY), a
    ld a, ECS_E_WIDTH(iy)
    ld (_fwk_ecs_platform_scratch + FWK_PLATFORM_WIDTH), a
    ld a, ECS_E_HEIGHT(iy)
    ld (_fwk_ecs_platform_scratch + FWK_PLATFORM_HEIGHT), a
    ld a, ECS_E_MOTION_FLAGS(iy)
    ld (_fwk_ecs_platform_scratch + FWK_PLATFORM_FLAGS), a

    ld l, 33(iy)
    ld h, 34(iy)
    push hl
    pop ix
    ld iy, #_fwk_ecs_platform_scratch
    call fwk_physics_platform_step

    pop iy
    push iy
    ld l, 35(iy)
    ld h, 36(iy)
    push hl
    pop ix
    ld iy, #_fwk_ecs_platform_scratch
    call fwk_platform_tilemap_resolve
    pop iy

    ld a, (_fwk_ecs_platform_scratch + FWK_PLATFORM_X)
    cp ECS_E_X(iy)
    jr z, _fwk_ecs_platform_store_x
    set 1, ECS_E_RENDER_FLAGS(iy)
_fwk_ecs_platform_store_x:
    ld ECS_E_X(iy), a
    ld a, (_fwk_ecs_platform_scratch + FWK_PLATFORM_Y)
    cp ECS_E_Y(iy)
    jr z, _fwk_ecs_platform_store_y
    set 1, ECS_E_RENDER_FLAGS(iy)
_fwk_ecs_platform_store_y:
    ld ECS_E_Y(iy), a
    ld a, (_fwk_ecs_platform_scratch + FWK_PLATFORM_VX)
    ld ECS_E_MOTION_VELOCITY_X(iy), a
    ld a, (_fwk_ecs_platform_scratch + FWK_PLATFORM_VY)
    ld ECS_E_MOTION_VELOCITY_Y(iy), a
    ld a, (_fwk_ecs_platform_scratch + FWK_PLATFORM_FLAGS)
    ld ECS_E_MOTION_FLAGS(iy), a
    pop ix
    xor a
    ret
