;; GlasnostFWK ECS 2.0 entity-manager public ABI.

FWK_ECS_MANAGER_STORAGE       = 0
FWK_ECS_MANAGER_CAPACITY      = 2
FWK_ECS_MANAGER_STRIDE        = 3
FWK_ECS_MANAGER_ACTIVE_COUNT  = 4
FWK_ECS_MANAGER_LIVE_COUNT    = 5
FWK_ECS_MANAGER_LOCK          = 6
FWK_ECS_MANAGER_FLAGS         = 7
FWK_ECS_MANAGER_SIZE          = 8

FWK_ECS_LOCK_TRAVERSAL        = 0x01
FWK_ECS_LOCK_RENDER           = 0x02
FWK_ECS_MANAGER_INITIALIZED   = 0x01

FWK_ECS_OK                    = 0x00
FWK_ECS_ERR_ARGUMENT          = 0x01
FWK_ECS_ERR_MANAGER           = 0x02
FWK_ECS_ERR_FULL              = 0x03
FWK_ECS_ERR_TEMPLATE          = 0x04
FWK_ECS_ERR_ENTITY            = 0x05
FWK_ECS_ERR_BUSY              = 0x06
FWK_ECS_ERR_TRANSITION        = 0x07
FWK_ECS_ERR_MASK              = 0x08
FWK_ECS_ERR_CALLBACK          = 0x09
FWK_ECS_ERR_OVERFLOW          = 0x0A
FWK_ECS_ERR_RENDER            = 0x0B

ECS_STATUS_FREE               = 0
ECS_STATUS_ACTIVE             = 1
ECS_STATUS_PENDING_DESTROY    = 2
ECS_STATUS_DISABLED           = 3

ECS_RENDER_VISIBLE            = 0x01
ECS_RENDER_DIRTY              = 0x02
ECS_RENDER_HAS_BACKGROUND     = 0x04
ECS_RENDER_MASKED             = 0x08
ECS_RENDER_RECOLOR            = 0x10

.macro FWK_ECS_MANAGER_DESCRIPTOR name, storage, capacity
name::
    .dw storage
    .db capacity
    .db ECS_ENTITY_SIZE
    .db 0, 0, 0, 0
.endm

.globl fwk_ecs_manager_init, fwk_ecs_entity_create
.globl fwk_ecs_entity_mark_destroy, fwk_ecs_entity_disable
.globl fwk_ecs_entity_enable, fwk_ecs_entity_set_mask
.globl fwk_ecs_system_run, fwk_ecs_manager_collect
.globl fwk_ecs_system_behavior, fwk_ecs_system_motion_u8
