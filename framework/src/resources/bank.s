;; 128K bank copy service extracted from the model01/DeckTower low-RAM stub
;; contract. Detection uses 0x4000 transiently and restores both RAM views.
.module fwk_bank

FWK_BANK_STUB = 0x0200
FWK_BANK_PATTERN = 0x0213
FWK_BANK_SAVE = 0x0214
FWK_BANK_NORMAL_SAVE = 0x0215
FWK_BANK_PROBE = 0x4000
FWK_BANK_NORMAL = 0xC0
FWK_BANK_BASE = 0xC4

.area _DATA
fwk_bank_has_128k:: .db 0

.area _CODE
_fwk_bank_stub_source:
    .db 0xF3, 0xC5, 0x01, 0x00, 0x7F, 0xED, 0x79, 0xC1, 0xED, 0xB0
    ;; NOP instead of EI: callers decide when the complete operation may
    ;; re-enable interrupts. This keeps the historical 19-byte layout.
    .db 0x3E, 0xC0, 0x01, 0x00, 0x7F, 0xED, 0x79, 0x00, 0xC9
_fwk_bank_stub_end:

;; fwk_bank_init
;; In: none. Out: A=1/NZ for independent extra RAM, A=0/Z otherwise;
;; fwk_bank_has_128k mirrors A, carry clear. Modified: AF,BC,DE,HL.
;; The temporary byte at 0x4000 is not reserved: normal RAM and bank 0 are
;; both saved and restored while interrupts remain disabled. Returns enabled.
fwk_bank_init::
    ld hl, #_fwk_bank_stub_source
    ld de, #FWK_BANK_STUB
    ld bc, #(_fwk_bank_stub_end - _fwk_bank_stub_source)
    ldir
    di
    ld a, (FWK_BANK_PROBE)
    ld (FWK_BANK_NORMAL_SAVE), a
    ld a, #FWK_BANK_BASE
    ld hl, #FWK_BANK_PROBE
    ld de, #FWK_BANK_SAVE
    ld bc, #1
    call FWK_BANK_STUB
    ld a, #0xAA
    ld (FWK_BANK_PROBE), a
    ld a, #0x55
    ld (FWK_BANK_PATTERN), a
    ld a, #FWK_BANK_BASE
    ld hl, #FWK_BANK_PATTERN
    ld de, #FWK_BANK_PROBE
    ld bc, #1
    call FWK_BANK_STUB
    ld a, (FWK_BANK_PROBE)
    cp #0xAA
    ld a, #0
    jr nz, _fwk_bank_detected
    inc a
_fwk_bank_detected:
    ld (fwk_bank_has_128k), a
    push af
    ld a, (FWK_BANK_NORMAL_SAVE)
    ld (FWK_BANK_PROBE), a
    ld a, #FWK_BANK_BASE
    ld hl, #FWK_BANK_SAVE
    ld de, #FWK_BANK_PROBE
    ld bc, #1
    call FWK_BANK_STUB
    pop af
    or a
    ei
    ret
_fwk_bank_init_end::

;; fwk_bank_copy_from
;; In: A=bank 0..3, HL=source in 0x4000..0x7FFF, DE=normal-RAM destination,
;; BC=count. Out: carry set for invalid bank, otherwise clear.
;; Modified: AF,BC,DE,HL; interrupts enabled on success.
fwk_bank_copy_from::
    cp #4
    jr nc, _fwk_bank_invalid
    add #FWK_BANK_BASE
    call FWK_BANK_STUB
    ei
    or a
    ret

;; fwk_bank_copy_to
;; Same machine contract as copy_from; HL=normal source, DE=bank-window dest.
fwk_bank_copy_to::
    cp #4
    jr nc, _fwk_bank_invalid
    add #FWK_BANK_BASE
    call FWK_BANK_STUB
    ei
    or a
    ret
_fwk_bank_invalid:
    scf
    ret
