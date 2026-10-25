;; GlasnostFWK system core. Derived from the six-interrupt structure shared by
;; model01, boop, DeckTower and PocketFever; rewritten to remove audio/game deps.
.module fwk_system

.include "cpctelera.h.s"
.globl cpct_disableFirmware_asm
.globl cpct_waitVSYNC_asm
.globl cpct_setInterruptHandler_asm
.globl cpct_scanKeyboard_if_asm

.area _DATA
fwk_system_irq_count:: .db 0
fwk_system_frame_count:: .dw 0
fwk_system_irq_callback:: .dw 0

.area _CODE

;; fwk_system_set_irq_callback
;; In: HL=callback or 0. Callback runs once per 6 CPC interrupts.
;; Out: none. Modified: none. Non-reentrant setter; call with interrupts off
;; when replacing a live callback.
fwk_system_set_irq_callback::
    ld (fwk_system_irq_callback), hl
    ret

;; Internal indirect call. The callback may alter all main registers.
_fwk_system_call_callback:
    ld hl, #_fwk_system_callback_return
    push hl
    ld hl, (fwk_system_irq_callback)
    jp (hl)
_fwk_system_callback_return:
    ret

;; Interrupt handler installed through CPCtelera. Keyboard state is refreshed
;; once per frame. A registered callback is then invoked (audio is one user).
_fwk_system_irq:
    ld a, (fwk_system_irq_count)
    inc a
    cp #6
    jr c, _fwk_system_store_irq
    xor a
    ld (fwk_system_irq_count), a
    ld hl, (fwk_system_frame_count)
    inc hl
    ld (fwk_system_frame_count), hl
    call cpct_scanKeyboard_if_asm
    ld hl, (fwk_system_irq_callback)
    ld a, h
    or l
    ret z
    jp _fwk_system_call_callback
_fwk_system_store_irq:
    ld (fwk_system_irq_count), a
    ret

;; fwk_system_init
;; In: none. Out: none. Modified: AF,BC,DE,HL.
;; Disables firmware and installs the 300 Hz handler. Callback remains unset.
fwk_system_init::
    call cpct_disableFirmware_asm
    xor a
    ld (fwk_system_irq_count), a
    ld (fwk_system_irq_callback), a
    ld (fwk_system_irq_callback + 1), a
    ld hl, #0
    ld (fwk_system_frame_count), hl
    call cpct_waitVSYNC_asm
    ld hl, #_fwk_system_irq
    jp cpct_setInterruptHandler_asm

;; fwk_system_wait_frame
;; In: none. Out: none. Modified: AF,BC,DE,HL.
;; Waits for the next vertical synchronization through CPCtelera.
fwk_system_wait_frame::
    jp cpct_waitVSYNC_asm
