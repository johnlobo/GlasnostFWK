.module example_resources128
.globl fwk_system_init, fwk_bank_init, fwk_bank_copy_to, fwk_bank_copy_from

.area _ASSETNORMAL (ABS)
.org 0x9000
_source: .db 0x47, 0x4C, 0x41, 0x53, 0x4E, 0x4F, 0x53, 0x54
_result: .ds 8

.area _CODE
_main::
    call fwk_system_init
    call fwk_bank_init
    jr z, _no_128k
    xor a
    ld hl, #_source
    ld de, #0x4000
    ld bc, #8
    call fwk_bank_copy_to
    xor a
    ld hl, #0x4000
    ld de, #_result
    ld bc, #8
    call fwk_bank_copy_from
    ld hl, #_source
    ld de, #_result
    ld b, #8
_compare:
    ld a, (de)
    cp (hl)
    jr nz, _failed
    inc de
    inc hl
    djnz _compare
_passed:
    ld bc, #0x7F10
    out (c), c
    jr _passed
_no_128k:
    ld bc, #0x7F4B
    out (c), c
    jr _no_128k
_failed:
    ld bc, #0x7F4C
    out (c), c
    jr _failed
