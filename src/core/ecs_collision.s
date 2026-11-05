;; ECS 2.0 entity collision system (AABB, ENTER/STAY/EXIT events).
.module fwk_ecs_collision

.include "ecs_profile.inc"
.include "core/ecs_manager.inc"
.include "core/ecs_collision.inc"

.area _CODE

;; fwk_ecs_system_collision -- STUB: the real system replaces this routine.
fwk_ecs_system_collision::
    ld a, #FWK_ECS_ERR_ARGUMENT
    scf
    ret
