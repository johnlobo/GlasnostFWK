.module example_collision
.include "extensions/collision_bodies.inc"

.globl fwk_project_init, fwk_system_wait_frame
.globl fwk_collision_aabb

.area _DATA
collision_entity_a:: .db 10, 20, 8, 8
collision_entity_b:: .db 14, 24, 8, 8
collision_status:: .db 0

.area _CODE

_main::
    call fwk_project_init
    ld hl, #collision_entity_a
    ld de, #collision_entity_b
    ld b, #0
    ld c, #1
    ld d, #2
    ld e, #3
    call fwk_collision_aabb
    jr nc, _collision_fail
    ld a, #0x5A
    ld (collision_status), a
_collision_loop:
    call fwk_system_wait_frame
    jr _collision_loop
_collision_fail:
    ld a, #0xEE
    ld (collision_status), a
    jr _collision_loop
