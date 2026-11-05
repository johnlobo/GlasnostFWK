;; GlasnostFWK ECS 2.0 entity collision system: public ABI (docs/ecs-abi-2.0.md, 9 and 9.1).

ECS_COLLISION_COLLIDER        = 0x01
ECS_COLLISION_COLLISIONABLE   = 0x02

ECS_COLLISION_ENTER           = 1
ECS_COLLISION_STAY            = 2
ECS_COLLISION_EXIT            = 3

FWK_ECS_COLLISION_CALLBACK       = 0
FWK_ECS_COLLISION_EVENTS         = 2
FWK_ECS_COLLISION_EVENT_CAPACITY = 4
FWK_ECS_COLLISION_EVENT_COUNT    = 5
FWK_ECS_COLLISION_FLAGS          = 6
FWK_ECS_COLLISION_PAIR_COUNT     = 7
FWK_ECS_COLLISION_PAIR_CAPACITY  = 8
;; Private to core/ecs_collision.s: pointers to the two pair tables and the
;; index (0/1) of the table that holds the previous call's pairs.
FWK_ECS_COLLISION_PRIVATE_TABLE0 = 9
FWK_ECS_COLLISION_PRIVATE_TABLE1 = 11
FWK_ECS_COLLISION_PRIVATE_ACTIVE = 13
FWK_ECS_COLLISION_PRIVATE_SPARE  = 14
FWK_ECS_COLLISION_STATE_SIZE     = 15

FWK_ECS_COLLISION_OVERFLOW       = 0x01

FWK_ECS_COLLISION_EVENT_SIZE     = 5   ; entity A, entity B, type
FWK_ECS_COLLISION_PAIR_SIZE      = 4   ; entity A, entity B

;; Describes one collision system instance. The caller allocates:
;;   events  : event_capacity * FWK_ECS_COLLISION_EVENT_SIZE bytes
;;   table0/1: pair_capacity  * FWK_ECS_COLLISION_PAIR_SIZE bytes each
;; callback receives IX=entity A, IY=entity B, A=type, HL=manager A,
;; DE=manager B and may clobber every register except SP.
.macro FWK_ECS_COLLISION_STATE name, callback, events, event_capacity, table0, table1, pair_capacity
name::
    .dw callback
    .dw events
    .db event_capacity
    .db 0
    .db 0
    .db 0
    .db pair_capacity
    .dw table0
    .dw table1
    .db 0
    .db 0
.endm

;; In: IX=state, HL=manager A, DE=manager B (equal for a single manager).
;; Out: carry clear and A=0, or carry set and A=FWK_ECS_ERR_*. Preserves IX/IY.
.globl fwk_ecs_system_collision
