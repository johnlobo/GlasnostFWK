;; GlasnostFWK ECS 2.0 selective renderer: public ABI (docs/ecs-abi-2.0.md, 8).

;; Scene descriptor (8 bytes, project-owned).
FWK_ECS_RENDER_TABLE     = 0     ; pointer to a table of manager pointers
FWK_ECS_RENDER_COUNT     = 2     ; managers in the table
FWK_ECS_RENDER_WORK      = 3     ; work array, capacity * 8 bytes (entity, key, box)
FWK_ECS_RENDER_CAPACITY  = 5     ; entries in the work array
FWK_ECS_RENDER_AFFECTED  = 6     ; entities redrawn this frame (output)
FWK_ECS_RENDER_STATE     = 7
FWK_ECS_RENDER_SIZE      = 8

FWK_ECS_RENDER_STATE_IDLE     = 0
FWK_ECS_RENDER_STATE_PREPARED = 1
FWK_ECS_RENDER_STATE_RESTORED = 2

.macro FWK_ECS_RENDER_SCENE label, table, count, work, capacity
label:
    .dw table
    .db count
    .dw work
    .db capacity, 0, FWK_ECS_RENDER_STATE_IDLE
.endm

;; Call once per frame, in this order, with IX=scene:
;;   fwk_ecs_render_prepare   before VSYNC: find what must be redrawn, lock managers
;;   fwk_ecs_render_restore   after VSYNC: restore backgrounds, reverse of last draw
;;   fwk_ecs_render_draw      right after: capture, draw in Y order, unlock
;; Out: carry clear and A=0, or carry set and A=FWK_ECS_ERR_* (RENDER for a call
;; out of order or a sprite error, BUSY for a locked manager, OVERFLOW when the
;; work array is too small; prepare fails and leaves the scene idle and unlocked).
;; Restore and draw errors are fatal: the scene is left half done and locked.
;; List each manager once in the table. Ties in the Y key resolve by table
;; order, then slot, in both restore and draw.
;; IX/IY preserved. Not reentrant.
.globl fwk_ecs_render_prepare
.globl fwk_ecs_render_restore
.globl fwk_ecs_render_draw
