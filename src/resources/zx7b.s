;; Thin optional adapter over CPCTelera Next's backwards ZX7 decompressor.
.module fwk_zx7b
.globl cpct_zx7b_decrunch_s_asm

.area _CODE

;; Input: HL=last compressed byte, DE=last destination byte.
;; Output: decompressed bytes ending at DE. Modified: AF,BC,DE,HL.
;; No bounds or corruption checks; source and destination ends must be exact.
fwk_zx7b_unpack::
    jp cpct_zx7b_decrunch_s_asm
