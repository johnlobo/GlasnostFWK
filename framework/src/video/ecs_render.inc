;; GlasnostFWK ECS 2.0 selective renderer: public ABI (docs/reference/ecs-abi-2.0.md, 8).

;; Scene descriptor (11 bytes, project-owned).
FWK_ECS_RENDER_TABLE     = 0     ; pointer to a table of manager pointers
FWK_ECS_RENDER_COUNT     = 2     ; managers in the table
FWK_ECS_RENDER_WORK      = 3     ; work array, capacity * 8 bytes (entity, key, box)
FWK_ECS_RENDER_CAPACITY  = 5     ; entries in the work array
FWK_ECS_RENDER_AFFECTED  = 6     ; entities redrawn this frame (output)
FWK_ECS_RENDER_STATE     = 7
FWK_ECS_RENDER_POOLS     = 8     ; pointer to a table of background pool pointers
FWK_ECS_RENDER_POOL_COUNT = 10   ; pools in the table (1..255)
FWK_ECS_RENDER_SIZE      = 11

;; Background pool (project-owned, built with FWK_ECS_RENDER_POOL): `count` slots,
;; each one a use flag byte followed by `bytes` bytes of buffer.
FWK_ECS_POOL_BYTES       = 0     ; word: size of each buffer
FWK_ECS_POOL_COUNT       = 2     ; slots in the pool (1..255)
FWK_ECS_POOL_FLAGS       = 3     ; first slot: flag, then `bytes` of buffer, and so on

FWK_ECS_RENDER_STATE_IDLE     = 0
FWK_ECS_RENDER_STATE_PREPARED = 1
FWK_ECS_RENDER_STATE_RESTORED = 2

;; pools: table of pool pointers sorted by ascending `bytes`, pool_count entries.
.macro FWK_ECS_RENDER_SCENE label, table, count, work, capacity, pools, pool_count
.if (((pool_count)-1)&0xFF00)|((pool_count)&0xFF00)
.error 1                        ; a scene has 1 to 255 pools
.endif
label:
    .dw table
    .db count
    .dw work
    .db capacity, 0, FWK_ECS_RENDER_STATE_IDLE
    .dw pools
    .db pool_count
.endm

;; One pool of `count` background buffers of `bytes` bytes. The renderer gives an
;; entity the first free buffer of the first pool (in table order) whose `bytes` is at
;; least width * height, when the entity is first drawn, and takes it back when the
;; entity is no longer drawn. Each slot is [use flag][buffer]; ECS_E_RENDER_BACKGROUND
;; points at the buffer, so its flag sits one byte before.
.macro FWK_ECS_RENDER_POOL label, bytes, count
.if (((count)-1)&0xFF00)|((count)&0xFF00)
.error 1                        ; a pool has 1 to 255 slots
.endif
label::
    .dw bytes
    .db count
    .rept count
        .db 0
        .ds bytes
    .endm
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
;; Backgrounds: the renderer owns ECS_E_RENDER_BACKGROUND; a template leaves it zero.
;; prepare allocates the buffer of an entity that has to be on screen and has none
;; (FWK_ECS_ERR_OVERFLOW if no pool has a free buffer big enough); restore returns it
;; once the entity is no longer drawn. List the pools by ascending `bytes`.
;; fwk_ecs_render_reset (IX=scene): free every buffer of every pool. Call it after
;; re-initialising the managers of the scene (a level start), when entities vanish
;; without being restored. ERR_RENDER unless the scene is IDLE.
.globl fwk_ecs_render_prepare
.globl fwk_ecs_render_reset
.globl fwk_ecs_render_restore
.globl fwk_ecs_render_draw
