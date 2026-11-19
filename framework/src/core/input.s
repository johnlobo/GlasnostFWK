;; Configurable held/pressed/released input state, based on the table dispatch
;; found in model01 and the explicit debounce work in boop.
.module fwk_input

.include "cpctelera.h.s"
.globl cpct_isKeyPressed_asm

.area _DATA
fwk_input_held::     .db 0
fwk_input_pressed::  .db 0
fwk_input_released:: .db 0
fwk_input_repeat::   .db 0
_fwk_input_repeat_delay:    .db 15
_fwk_input_repeat_interval: .db 4
_fwk_input_repeat_counter:  .db 0
_fwk_input_previous: .db 0
_fwk_input_work:     .db 0
_fwk_input_bindings: .dw 0

.area _CODE

;; fwk_input_init
;; In: none. Out: state cleared (repeat timing kept). Modified: AF.
fwk_input_init::
    xor a
    ld (fwk_input_repeat), a
    ld (fwk_input_held), a
    ld (fwk_input_pressed), a
    ld (fwk_input_released), a
    ld (_fwk_input_previous), a
    ret

;; fwk_input_set_bindings
;; In: HL=table of [.dw CPCtelera key, .db action mask], terminated by mask 0.
;; Out: none. Modified: none. Table must persist and define at most 8 actions.
fwk_input_set_bindings::
    ld (_fwk_input_bindings), hl
    ret

;; fwk_input_set_repeat
;; In: B=delay, C=interval, both in fwk_input_update calls (frames), 1..255
;; (0 acts as 256).
;; Default 15 and 4. Out: none. Modified: A.
fwk_input_set_repeat::
    ld a, b
    ld (_fwk_input_repeat_delay), a
    ld a, c
    ld (_fwk_input_repeat_interval), a
    ret

;; fwk_input_update
;; In: keyboard buffer previously scanned by fwk_system's IRQ.
;; Out: fwk_input_held/pressed/released updated. Modified: AF,BC,DE,HL,IY.
;; pressed=(held xor previous)&held; released=(held xor previous)&previous.
;; repeat=pressed on a new press; while actions stay held with no new press,
;; repeat=held once after `delay` updates and then every `interval` updates;
;; 0 otherwise. Typical use: move a cursor on fwk_input_repeat.
fwk_input_update::
    xor a
    ld (_fwk_input_work), a
    ld iy, (_fwk_input_bindings)
_fwk_input_loop:
    ld a, 2(iy)
    or a
    jr z, _fwk_input_finish
    ld l, 0(iy)
    ld h, 1(iy)
    push iy
    call cpct_isKeyPressed_asm
    pop iy
    jr z, _fwk_input_next
    ld a, (_fwk_input_work)
    or 2(iy)
    ld (_fwk_input_work), a
_fwk_input_next:
    ld de, #3
    add iy, de
    jr _fwk_input_loop
_fwk_input_finish:
    ld a, (fwk_input_held)
    ld (_fwk_input_previous), a
    ld b, a
    ld a, (_fwk_input_work)
    ld (fwk_input_held), a
    xor b
    ld c, a
    ld a, (_fwk_input_work)
    and c
    ld (fwk_input_pressed), a
    ld a, (_fwk_input_previous)
    and c
    ld (fwk_input_released), a

    ;; Key repeat: one counter for the whole held set.
    ld a, (fwk_input_pressed)
    or a
    jr nz, _fwk_input_repeat_press
    ld a, (fwk_input_held)
    or a
    jr z, _fwk_input_repeat_store
    ld hl, #_fwk_input_repeat_counter
    dec (hl)
    ld a, #0                      ;; ld keeps the flags of dec
    jr nz, _fwk_input_repeat_store
    ld a, (_fwk_input_repeat_interval)
    ld (hl), a
    ld a, (fwk_input_held)
    jr _fwk_input_repeat_store
_fwk_input_repeat_press:
    ld a, (_fwk_input_repeat_delay)
    ld (_fwk_input_repeat_counter), a
    ld a, (fwk_input_pressed)
_fwk_input_repeat_store:
    ld (fwk_input_repeat), a
    ret
