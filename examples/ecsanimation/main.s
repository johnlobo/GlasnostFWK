;; Emulator harness for the ECS animation system.
;; Replays the command table generated from tools/ecs_animation_model.py and
;; records, after every system call, each entity's frame, timer, sprite pointer
;; and render flags in ecsanimation_log; tests/emulator_smoke.py compares it
;; with the model.
.module example_ecsanimation
.include "ecs_profile.inc"
.include "core/ecs_manager.inc"
.include "core/ecs_animation.inc"

.globl fwk_project_init, fwk_system_wait_frame

ECSANIMATION_CAPACITY = 5
ECSANIMATION_TICKS = 14
ECSANIMATION_RECORD = 1 + 5 * ECSANIMATION_CAPACITY
ECSANIMATION_LOG_SIZE = ECSANIMATION_RECORD * ECSANIMATION_TICKS

.area _DATA
ecsanimation_storage:: .ds ECS_ENTITY_SIZE * ECSANIMATION_CAPACITY
FWK_ECS_MANAGER_DESCRIPTOR ecsanimation_manager, ecsanimation_storage, ECSANIMATION_CAPACITY

ecsanimation_template: .ds ECS_ENTITY_SIZE
ecsanimation_entities: .ds 2 * ECSANIMATION_CAPACITY

;; Sprite stand-ins (only their addresses matter) and shared descriptors.
ecsanimation_sprite0: .db 0
ecsanimation_sprite1: .db 0
ecsanimation_sprite2: .db 0
ecsanimation_sprite3: .db 0
ecsanimation_sprite4: .db 0
ecsanimation_sprites:: .dw ecsanimation_sprite0, ecsanimation_sprite1, ecsanimation_sprite2
                       .dw ecsanimation_sprite3, ecsanimation_sprite4
ecsanimation_desc_a: .db 3, 2
                     .dw ecsanimation_sprite0, ecsanimation_sprite1, ecsanimation_sprite2
ecsanimation_desc_b: .db 2, 1
                     .dw ecsanimation_sprite3, ecsanimation_sprite4
;; Descriptor C: 130 frames, duration 1; frame i shows sprite i % 5.
ecsanimation_desc_c: .db 130, 1
    .rept 26
    .dw ecsanimation_sprite0, ecsanimation_sprite1, ecsanimation_sprite2
    .dw ecsanimation_sprite3, ecsanimation_sprite4
    .endm
ecsanimation_desc_d: .db 1, 3
                     .dw ecsanimation_sprite0
ecsanimation_descriptors: .dw 0, ecsanimation_desc_a, ecsanimation_desc_b, ecsanimation_desc_c, ecsanimation_desc_d

.include "game/scenario.inc"

ecsanimation_status:: .db 0
ecsanimation_log_length:: .dw 0
ecsanimation_log:: .ds ECSANIMATION_LOG_SIZE
_ecsanimation_log_ptr: .dw 0
_ecsanimation_cmd_ptr: .dw 0
_ecsanimation_tick: .db 0
_ecsanimation_i: .db 0

.area _CODE

_ecsanimation_fail:
    ld (ecsanimation_status), a
_ecsanimation_halt:
    call fwk_system_wait_frame
    jr _ecsanimation_halt

;; In: A=entity index 0..2. Out: IY=entity. Modified: AF,DE,HL.
_ecsanimation_entity_ptr:
    add a, a
    ld e, a
    ld d, #0
    ld hl, #ecsanimation_entities
    add hl, de
    ld e, (hl)
    inc hl
    ld d, (hl)
    push de
    pop iy
    ret

;; In: A=descriptor code 0..2. Out: HL=descriptor address or 0.
_ecsanimation_descriptor:
    add a, a
    ld e, a
    ld d, #0
    ld hl, #ecsanimation_descriptors
    add hl, de
    ld e, (hl)
    inc hl
    ld d, (hl)
    ex de, hl
    ret

_main::
    call fwk_project_init
    ld ix, #ecsanimation_manager
    call fwk_ecs_manager_init
    ld a, #0xE1
    jp c, _ecsanimation_fail
    ld iy, #ecsanimation_template
    ld ECS_E_STATUS(iy), #ECS_STATUS_ACTIVE
    ld ECS_E_COMPONENTS(iy), #(ECS_C_RENDER | ECS_C_ANIMATION)
    ld ECS_E_COMPONENTS+1(iy), #0    ; both bits live in the low byte
    ld ECS_E_WIDTH(iy), #4
    ld ECS_E_HEIGHT(iy), #8
    xor a
    ld (_ecsanimation_i), a
_ecsanimation_create:
    ld ix, #ecsanimation_manager
    ld hl, #ecsanimation_template
    call fwk_ecs_entity_create
    ld a, #0xE2
    jp c, _ecsanimation_fail
    ld a, (_ecsanimation_i)
    add a, a
    ld e, a
    ld d, #0
    ld hl, #ecsanimation_entities
    add hl, de
    push iy
    pop de
    ld (hl), e
    inc hl
    ld (hl), d
    ;; Entities flagged "templated" already hold descriptor B with TIMER 0, as
    ;; if copied from such a template; fwk_ecs_anim_set must still start them.
    ld a, (_ecsanimation_i)
    ld e, a
    ld d, #0
    ld hl, #ecsanimation_templated
    add hl, de
    ld a, (hl)
    or a
    jr z, _ecsanimation_initial
    ld a, #2
    call _ecsanimation_descriptor
    ld ECS_E_ANIMATION_DESCRIPTOR(iy), l
    ld ECS_E_ANIMATION_DESCRIPTOR+1(iy), h
_ecsanimation_initial:
    ;; Initial animation from the generated table, set after creation.
    ld a, (_ecsanimation_i)
    ld e, a
    ld d, #0
    ld hl, #ecsanimation_initial
    add hl, de
    ld a, (hl)
    call _ecsanimation_descriptor
    call fwk_ecs_anim_set
    ld a, #0xE3
    jp c, _ecsanimation_fail
    ;; Optional starting frame (0xFF keeps what fwk_ecs_anim_set chose).
    ld a, (_ecsanimation_i)
    ld e, a
    ld d, #0
    ld hl, #ecsanimation_initial_frame
    add hl, de
    ld a, (hl)
    cp #0xFF
    jr z, _ecsanimation_started
    ld ECS_E_ANIMATION_FRAME(iy), a
_ecsanimation_started:
    ld hl, #_ecsanimation_i
    inc (hl)
    ld a, (hl)
    cp #ECSANIMATION_CAPACITY
    jr nz, _ecsanimation_create

    ld hl, #ecsanimation_commands
    ld (_ecsanimation_cmd_ptr), hl
    ld hl, #ecsanimation_log
    ld (_ecsanimation_log_ptr), hl
    xor a
    ld (_ecsanimation_tick), a

_ecsanimation_next_tick:
    ;; Clear DIRTY on every entity so the log shows what this tick marked.
    xor a
    ld (_ecsanimation_i), a
_ecsanimation_clear:
    ld a, (_ecsanimation_i)
    call _ecsanimation_entity_ptr
    ld ECS_E_RENDER_FLAGS(iy), #0
    ld hl, #_ecsanimation_i
    inc (hl)
    ld a, (hl)
    cp #ECSANIMATION_CAPACITY
    jr nz, _ecsanimation_clear

    ;; Optional descriptor change for this tick.
    ld hl, (_ecsanimation_cmd_ptr)
    ld a, (hl)
    cp #0xFE
    jp z, _ecsanimation_finished
    inc hl
    ld c, (hl)                       ; descriptor code
    inc hl
    ld (_ecsanimation_cmd_ptr), hl
    cp #0xFF
    jr z, _ecsanimation_run
    call _ecsanimation_entity_ptr    ; IY = entity (A = index)
    ld a, c
    call _ecsanimation_descriptor
    call fwk_ecs_anim_set
    ld a, #0xE4
    jp c, _ecsanimation_fail

_ecsanimation_run:
    ld ix, #ecsanimation_manager
    call fwk_ecs_system_animation
    ld a, #0xE5
    jp c, _ecsanimation_fail

    ;; Record: tick, then frame/timer/sprite/flags of each entity.
    ld de, (_ecsanimation_log_ptr)
    ld a, (_ecsanimation_tick)
    ld (de), a
    inc de
    xor a
    ld (_ecsanimation_i), a
_ecsanimation_record:
    ld a, (_ecsanimation_i)
    push de
    call _ecsanimation_entity_ptr
    pop de
    ld a, ECS_E_ANIMATION_FRAME(iy)
    ld (de), a
    inc de
    ld a, ECS_E_ANIMATION_TIMER(iy)
    ld (de), a
    inc de
    ld a, ECS_E_RENDER_SPRITE(iy)
    ld (de), a
    inc de
    ld a, ECS_E_RENDER_SPRITE+1(iy)
    ld (de), a
    inc de
    ld a, ECS_E_RENDER_FLAGS(iy)
    ld (de), a
    inc de
    ld hl, #_ecsanimation_i
    inc (hl)
    ld a, (hl)
    cp #ECSANIMATION_CAPACITY
    jr nz, _ecsanimation_record
    ld (_ecsanimation_log_ptr), de
    ld hl, #ecsanimation_log
    or a
    ex de, hl
    sbc hl, de
    ld (ecsanimation_log_length), hl
    ld hl, #_ecsanimation_tick
    inc (hl)
    jp _ecsanimation_next_tick

_ecsanimation_finished:
    ld a, #0x5A
    ld (ecsanimation_status), a
    jp _ecsanimation_halt
