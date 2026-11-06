;; Emulator harness for the ECS selective renderer.
;; Replays the scenario generated from tools/ecs_render_model.py. After every
;; frame it publishes the frame number in ecsrender_done and waits for the host
;; (tests/emulator_smoke.py) to read video RAM and set ecsrender_go; the host
;; compares the screen with the model's ideal image.
.module example_ecsrender
.include "ecs_profile.inc"
.include "core/ecs_manager.inc"
.include "video/ecs_render.inc"

.globl fwk_project_init, fwk_system_wait_frame
.globl fwk_video_init

ECSRENDER_CAPACITY_A = 5
ECSRENDER_CAPACITY_B = 4
ECSRENDER_ROW = 7                       ; manager, width, height, offset(2), sprite(2)
ECSRENDER_FRAME_ROW = 3 * ECSRENDER_ENTITIES

CMD_HIDE    = 1
CMD_SHOW    = 2
CMD_DISABLE = 3
CMD_ENABLE  = 4
CMD_DESTROY = 5

.area _DATA
ecsrender_storage_a:: .ds ECS_ENTITY_SIZE * ECSRENDER_CAPACITY_A
ecsrender_storage_b:: .ds ECS_ENTITY_SIZE * ECSRENDER_CAPACITY_B
FWK_ECS_MANAGER_DESCRIPTOR ecsrender_manager_a, ecsrender_storage_a, ECSRENDER_CAPACITY_A
FWK_ECS_MANAGER_DESCRIPTOR ecsrender_manager_b, ecsrender_storage_b, ECSRENDER_CAPACITY_B
ecsrender_managers: .dw ecsrender_manager_a, ecsrender_manager_b
ecsrender_work: .ds 8 * ECSRENDER_ENTITIES
ecsrender_work_small: .ds 8 * 1
;; Background buffers by size class. The nine entities need 24, 32, 20, 24, 24, 32,
;; 30, 32 and 12 bytes: the 20 and 24 byte ones share the 24 byte class, the 30 and
;; 32 byte ones the 32 byte class, and the 12 byte one takes the 16 byte class.
FWK_ECS_RENDER_POOL ecsrender_pool16, 16, 1
FWK_ECS_RENDER_POOL ecsrender_pool24, 24, 4
FWK_ECS_RENDER_POOL ecsrender_pool32, 32, 4
ecsrender_pools: .dw ecsrender_pool16, ecsrender_pool24, ecsrender_pool32
FWK_ECS_RENDER_SCENE ecsrender_scene, ecsrender_managers, 2, ecsrender_work, ECSRENDER_ENTITIES, ecsrender_pools, 3
FWK_ECS_RENDER_SCENE ecsrender_scene_small, ecsrender_managers, 2, ecsrender_work_small, 1, ecsrender_pools, 3

;; Pool error cases on a manager of its own: two 4x8 entities (32 bytes each).
ecsrender_storage_c: .ds ECS_ENTITY_SIZE * 2
FWK_ECS_MANAGER_DESCRIPTOR ecsrender_manager_c, ecsrender_storage_c, 2
ecsrender_managers_c: .dw ecsrender_manager_c
ecsrender_work_c: .ds 8 * 2
FWK_ECS_RENDER_POOL ecsrender_pool_one, 32, 1       ; room for one entity only
FWK_ECS_RENDER_POOL ecsrender_pool_small, 16, 2     ; buffers too small for any entity
FWK_ECS_RENDER_POOL ecsrender_pool_two, 32, 1       ; the second entity spills over to this one
ecsrender_pools_spill: .dw ecsrender_pool_one, ecsrender_pool_two
ecsrender_pools_one: .dw ecsrender_pool_one
ecsrender_pools_small: .dw ecsrender_pool_small
FWK_ECS_RENDER_SCENE ecsrender_scene_one, ecsrender_managers_c, 1, ecsrender_work_c, 2, ecsrender_pools_one, 1
FWK_ECS_RENDER_SCENE ecsrender_scene_spill, ecsrender_managers_c, 1, ecsrender_work_c, 2, ecsrender_pools_spill, 2
FWK_ECS_RENDER_SCENE ecsrender_scene_toosmall, ecsrender_managers_c, 1, ecsrender_work_c, 2, ecsrender_pools_small, 1

ecsrender_template: .ds ECS_ENTITY_SIZE
ecsrender_entities:: .ds 2 * ECSRENDER_ENTITIES

.include "game/scenario.inc"

ecsrender_status:: .db 0
ecsrender_done:: .db 0
ecsrender_go:: .db 0
ecsrender_check_overflow:: .db 0xFF      ; result of a prepare with a too small work array
ecsrender_check_order:: .db 0xFF         ; result of draw called while IDLE
ecsrender_check_size:: .db 0xFF          ; prepare with buffers smaller than the sprite
ecsrender_check_pool:: .db 0xFF          ; prepare with one buffer for two sprites
ecsrender_check_reset:: .db 0xFF         ; flags left set after fwk_ecs_render_reset
ecsrender_check_args:: .db 0xFF          ; reset of a scene that is not IDLE
ecsrender_check_spill:: .db 0xFF         ; prepare when the first pool is full: must succeed
ecsrender_check_spill_used:: .db 0xFF    ; flags set in the two pools afterwards: 2
_ecsrender_frame_ptr: .dw 0
_ecsrender_frame: .db 0
_ecsrender_i: .db 0
_ecsrender_cmd: .db 0

.area _CODE

_ecsrender_fail:
    ld (ecsrender_status), a
_ecsrender_halt:
    call fwk_system_wait_frame
    jr _ecsrender_halt

;; In: A=entity index. Out: IY=entity, HL=its entity-table row. Modified: AF,BC,DE.
_ecsrender_entity:
    ld c, a
    add a, a
    ld e, a
    ld d, #0
    ld hl, #ecsrender_entities
    add hl, de
    ld e, (hl)
    inc hl
    ld d, (hl)
    push de
    pop iy
    ld a, c
    add a, a
    add a, a
    add a, a
    sub c                           ; 7 * index (ECSRENDER_ROW)
    ld e, a
    ld d, #0
    ld hl, #ecsrender_entity_table
    add hl, de
    ret

;; In: A=manager index (0/1). Out: IX=manager.
_ecsrender_manager:
    ld ix, #ecsrender_manager_a
    or a
    ret z
    ld ix, #ecsrender_manager_b
    ret

_main::
    call fwk_project_init
    call fwk_video_init
    ;; Background: byte = 5 * low + high of its own address, over the whole 16 KB.
    ld hl, #0xC000
_ecsrender_fill:
    ld a, l
    add a, a
    add a, a
    add a, l
    add a, h
    ld (hl), a
    inc hl
    ld a, h
    or l
    jr nz, _ecsrender_fill

    ld ix, #ecsrender_manager_a
    call fwk_ecs_manager_init
    ld a, #0xE1
    jp c, _ecsrender_fail
    ld ix, #ecsrender_manager_b
    call fwk_ecs_manager_init
    ld a, #0xE1
    jp c, _ecsrender_fail
    xor a
    ld (_ecsrender_i), a
_ecsrender_create:
    ld a, (_ecsrender_i)
    ld iy, #ecsrender_template
    ld ECS_E_COMPONENTS(iy), #ECS_C_RENDER
    ld ECS_E_COMPONENTS+1(iy), #0
    ld ECS_E_STATUS(iy), #ECS_STATUS_ACTIVE
    ld ECS_E_RENDER_FLAGS(iy), #3           ; VISIBLE | DIRTY
    call _ecsrender_row                      ; HL = row, A = manager index
    push hl
    call _ecsrender_manager
    pop hl
    inc hl
    ld a, (hl)
    ld ECS_E_WIDTH(iy), a
    inc hl
    ld a, (hl)
    ld ECS_E_HEIGHT(iy), a
    inc hl
    ld a, (hl)
    ld ECS_E_RENDER_SORT_OFFSET_Y(iy), a
    inc hl
    ld a, (hl)
    ld ECS_E_RENDER_SORT_OFFSET_Y+1(iy), a
    inc hl
    ld a, (hl)
    ld ECS_E_RENDER_SPRITE(iy), a
    inc hl
    ld a, (hl)
    ld ECS_E_RENDER_SPRITE+1(iy), a
    ld hl, #ecsrender_template
    call fwk_ecs_entity_create
    ld a, #0xE2
    jp c, _ecsrender_fail
    ld a, (_ecsrender_i)
    add a, a
    ld e, a
    ld d, #0
    ld hl, #ecsrender_entities
    add hl, de
    push iy
    pop de
    ld (hl), e
    inc hl
    ld (hl), d
    ld hl, #_ecsrender_i
    inc (hl)
    ld a, (hl)
    cp #ECSRENDER_ENTITIES
    jr nz, _ecsrender_create

    call _ecsrender_checks           ; error codes, while all nine entities are candidates

    ld hl, #ecsrender_frames
    ld (_ecsrender_frame_ptr), hl
    xor a
    ld (_ecsrender_frame), a

_ecsrender_next_frame:
    ld a, (_ecsrender_frame)
    cp #ECSRENDER_FRAMES
    jp z, _ecsrender_finished
    ;; Apply this frame's commands, like a game's movement and state systems.
    xor a
    ld (_ecsrender_i), a
_ecsrender_apply:
    ld a, (_ecsrender_i)
    call _ecsrender_entity           ; IY = entity, HL = row
    ld a, (hl)                       ; manager index
    ld hl, (_ecsrender_frame_ptr)
    ld c, (hl)                       ; command
    inc hl
    ld d, (hl)                       ; x
    inc hl
    ld e, (hl)                       ; y
    inc hl
    ld (_ecsrender_frame_ptr), hl
    ld b, a                          ; B = manager index
    ld a, c
    ld (_ecsrender_cmd), a
    ld a, ECS_E_X(iy)                ; position change marks DIRTY
    cp d
    jr nz, _ecsrender_moved
    ld a, ECS_E_Y(iy)
    cp e
    jr z, _ecsrender_same_position
_ecsrender_moved:
    ld ECS_E_X(iy), d
    ld ECS_E_Y(iy), e
    set 1, ECS_E_RENDER_FLAGS(iy)
_ecsrender_same_position:
    ld a, (_ecsrender_cmd)
    or a
    jr z, _ecsrender_apply_next
    cp #CMD_HIDE
    jr nz, _ecsrender_not_hide
    res 0, ECS_E_RENDER_FLAGS(iy)
    set 1, ECS_E_RENDER_FLAGS(iy)
    jr _ecsrender_apply_next
_ecsrender_not_hide:
    cp #CMD_SHOW
    jr nz, _ecsrender_api
    set 0, ECS_E_RENDER_FLAGS(iy)
    set 1, ECS_E_RENDER_FLAGS(iy)
    jr _ecsrender_apply_next
_ecsrender_api:
    ld a, b
    call _ecsrender_manager          ; IX = manager
    ld a, (_ecsrender_cmd)
    cp #CMD_DISABLE
    jr nz, _ecsrender_not_disable
    call fwk_ecs_entity_disable
    jr _ecsrender_api_done
_ecsrender_not_disable:
    cp #CMD_ENABLE
    jr nz, _ecsrender_destroy
    call fwk_ecs_entity_enable
    jr _ecsrender_api_done
_ecsrender_destroy:
    call fwk_ecs_entity_mark_destroy
_ecsrender_api_done:
    ld a, #0xE3
    jp c, _ecsrender_fail
_ecsrender_apply_next:
    ld hl, #_ecsrender_i
    inc (hl)
    ld a, (hl)
    cp #ECSRENDER_ENTITIES
    jr nz, _ecsrender_apply

    ld ix, #ecsrender_scene
    call fwk_ecs_render_prepare
    ld a, #0xE4
    jp c, _ecsrender_fail
    call fwk_system_wait_frame
    ld ix, #ecsrender_scene
    call fwk_ecs_render_restore
    ld a, #0xE5
    jp c, _ecsrender_fail
    ld ix, #ecsrender_scene
    call fwk_ecs_render_draw
    ld a, #0xE6
    jp c, _ecsrender_fail
    ld ix, #ecsrender_manager_a             ; collect what was destroyed this frame
    call fwk_ecs_manager_collect
    ld a, #0xE7
    jp c, _ecsrender_fail
    ld ix, #ecsrender_manager_b
    call fwk_ecs_manager_collect
    ld a, #0xE7
    jp c, _ecsrender_fail

    ld a, (_ecsrender_frame)                 ; publish the frame and wait for the host
    inc a
    ld (_ecsrender_frame), a
    ld (ecsrender_done), a
_ecsrender_wait_host:
    ld a, (ecsrender_go)
    or a
    jr z, _ecsrender_wait_host
    xor a
    ld (ecsrender_go), a
    jp _ecsrender_next_frame

;; Two 4x8 entities in manager C, still without a background buffer.
_ecsrender_make_c:
    ld ix, #ecsrender_manager_c
    call fwk_ecs_manager_init
    ret c
    ld iy, #ecsrender_template
    ld ECS_E_COMPONENTS(iy), #ECS_C_RENDER
    ld ECS_E_COMPONENTS+1(iy), #0
    ld ECS_E_STATUS(iy), #ECS_STATUS_ACTIVE
    ld ECS_E_RENDER_FLAGS(iy), #3
    ld ECS_E_WIDTH(iy), #4
    ld ECS_E_HEIGHT(iy), #8
    xor a
    ld ECS_E_RENDER_BACKGROUND(iy), a
    ld ECS_E_RENDER_BACKGROUND+1(iy), a
    ld hl, #ecsrender_template
    call fwk_ecs_entity_create
    ret c
    ld hl, #ecsrender_template
    jp fwk_ecs_entity_create

;; Background pool error cases. Each stores the A of the call (0 when it succeeded).
_ecsrender_pool_checks:
    call _ecsrender_make_c
    ld a, #0xE8
    jp c, _ecsrender_fail
    ld ix, #ecsrender_scene_toosmall         ; 16 byte buffers for 32 byte sprites
    call fwk_ecs_render_prepare
    ld (ecsrender_check_size), a
    ld ix, #ecsrender_scene_one              ; one buffer for two sprites
    call fwk_ecs_render_prepare
    ld (ecsrender_check_pool), a
    ld ix, #ecsrender_scene_one
    call fwk_ecs_render_reset
    ld a, #0xE9
    jp c, _ecsrender_fail
    ld a, (ecsrender_pool_one + FWK_ECS_POOL_FLAGS)
    ld (ecsrender_check_reset), a            ; 0 when reset freed the buffer
    ld ix, #ecsrender_scene_one              ; a scene that is not IDLE cannot be reset
    ld FWK_ECS_RENDER_STATE(ix), #FWK_ECS_RENDER_STATE_PREPARED
    call fwk_ecs_render_reset
    ld (ecsrender_check_args), a             ; FWK_ECS_ERR_RENDER
    ld ix, #ecsrender_scene_one
    ld FWK_ECS_RENDER_STATE(ix), #FWK_ECS_RENDER_STATE_IDLE
    ;; Spill: fresh entities, the first pool holds one buffer, the second one more.
    call _ecsrender_make_c
    ld a, #0xE8
    jp c, _ecsrender_fail
    ld ix, #ecsrender_scene_spill
    call fwk_ecs_render_prepare
    ld (ecsrender_check_spill), a
    ld a, (ecsrender_pool_one + FWK_ECS_POOL_FLAGS)
    ld hl, #ecsrender_pool_two + FWK_ECS_POOL_FLAGS
    add a, (hl)
    ld (ecsrender_check_spill_used), a
    ld ix, #ecsrender_scene_spill            ; leave it IDLE and unlocked, then free its buffers
    ld FWK_ECS_RENDER_STATE(ix), #FWK_ECS_RENDER_STATE_IDLE
    ld ix, #ecsrender_manager_c
    ld FWK_ECS_MANAGER_LOCK(ix), #0
    ld ix, #ecsrender_scene_spill
    call fwk_ecs_render_reset
    ld a, #0xE9
    jp c, _ecsrender_fail
    ret

_ecsrender_checks:
    call _ecsrender_pool_checks
    ld ix, #ecsrender_scene_small            ; nine candidates do not fit in 1 entry
    call fwk_ecs_render_prepare
    jr nc, _ecsrender_check_missing
    ld (ecsrender_check_overflow), a
    jr _ecsrender_check_order
_ecsrender_check_missing:
    xor a
    ld (ecsrender_check_overflow), a
_ecsrender_check_order:
    ld ix, #ecsrender_scene                  ; IDLE scene: draw is out of order
    call fwk_ecs_render_draw
    jr nc, _ecsrender_order_missing
    ld (ecsrender_check_order), a
    ret
_ecsrender_order_missing:
    xor a
    ld (ecsrender_check_order), a
    ret

_ecsrender_finished:
    ld a, #0x5A
    ld (ecsrender_status), a
    jp _ecsrender_halt

;; In: A=entity index. Out: HL=entity-table row, A=its manager index.
;; Row address = table + index * ECSRENDER_ROW, with ECSRENDER_ROW = 7 (8 - 1).
.if ECSRENDER_ROW-7
.error 1
.endif
_ecsrender_row:
    ld c, a
    add a, a
    add a, a
    add a, a
    sub c
    ld e, a
    ld d, #0
    ld hl, #ecsrender_entity_table
    add hl, de
    ld a, (hl)
    ret
