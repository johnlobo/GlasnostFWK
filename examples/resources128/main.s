.module example_resources128
.globl fwk_project_init, fwk_bank_copy_to, fwk_bank_copy_from

.area _ASSETNORMAL (ABS)
.org 0x9000
_source: .db 0x47, 0x4C, 0x41, 0x53, 0x4E, 0x4F, 0x53, 0x54
_result: .ds 8

.area _CODE
;; ----------------------------------------------------------------------------
;; _main
;;   Bank-copy test for 128K machines: copies 8 bytes ("GLASNOST") into extra RAM bank 0 (window 0x4000),
;;   reads them back to _result and compares. The outcome is signalled through the Gate Array.
;;   In : none (program entry; no register is read).
;;   Out: none; never returns (ends in an endless loop).
;;          Memory: _result = copy read back from bank 0; bank 0 offset 0 = copy of _source.
;;          Gate Array: pass writes 0x10 (select the border pen); no 128K writes colour 0x4B (hardware colour 0x0B,
;;          bright white); data mismatch writes colour 0x4C (0x0C, bright red). A colour write goes to the pen
;;          last selected, which this example does not set.
;;   Clobbers: all (never returns)
;;   Notes: Does not return, so no register is preserved. Depends on this project having extended_memory enabled:
;;          the generated fwk_project_init then ends with fwk_bank_init, so Z after the call means no 128K.
;; ----------------------------------------------------------------------------
_main::
    ;; System up and 128K probe done. Z set = no independent extra RAM (flags come from fwk_bank_init).
    call fwk_project_init
    jr z, _no_128k
    ;; Copy 8 bytes: A = bank 0, HL = _source (normal RAM), DE = 0x4000 (bank window), BC = 8.
    xor a
    ld hl, #_source
    ld de, #0x4000
    ld bc, #8
    call fwk_bank_copy_to
    ;; Read them back: A = bank 0, HL = 0x4000, DE = _result, BC = 8.
    xor a
    ld hl, #0x4000
    ld de, #_result
    ld bc, #8
    call fwk_bank_copy_from
    ;; Compare _source (HL) with _result (DE) over 8 bytes.
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
    ;; Pass: Gate Array pen select, value 0x10 (border pen). Spin forever.
_passed:
    ld bc, #0x7F10
    out (c), c
    jr _passed
    ;; No 128K RAM: Gate Array colour write 0x4B. Spin forever.
_no_128k:
    ld bc, #0x7F4B
    out (c), c
    jr _no_128k
    ;; Mismatch: Gate Array colour write 0x4C. Spin forever.
_failed:
    ld bc, #0x7F4C
    out (c), c
    jr _failed
