;; Thin Mode 0 text adapter. Font rendering remains the CPCTelera Next routine;
;; the framework only fixes and documents the assembly contract.
.module fwk_text
.include "cpctelera.h.s"
.globl cpct_setDrawCharM0_asm
.globl cpct_drawStringM0_asm

.area _CODE

;; fwk_text_set_colors
;; In: L=foreground pen 0..15, H=background pen 0..15.
;; Out: CPCtelera Mode 0 character colour table updated.
;; Modified: AF,BC,DE,HL. Self-modifying downstream routine; not ROM-safe.
fwk_text_set_colors::
    jp cpct_setDrawCharM0_asm

;; fwk_text_draw
;; In: IY=NUL-terminated ASCII string, HL=screen pointer.
;; Out: string drawn in Mode 0. Modified: AF,BC,DE,HL.
fwk_text_draw::
    jp cpct_drawStringM0_asm
