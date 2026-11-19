.module validation_disksave
.include "resources/disk.inc"

.globl fwk_disk_init, fwk_disk_save, fwk_project_init

DISKSAVE_DATA = 0x8000                ;; inside FWK_DISK_SAVE_LOW..LIMIT
DISKSAVE_BUFFER = 0x8800
DISKSAVE_LENGTH = 300

.area _DATA
disksave_status:: .db 0

_name: .ascii "SAVED.DAT"
;; Descriptor: name, length, data, bytes, buffer, inks, mode.
_descriptor:
    .dw _name
    .db 9
    .dw DISKSAVE_DATA
    .dw DISKSAVE_LENGTH
    .dw DISKSAVE_BUFFER
    .dw _inks
    .db 0
;; Firmware colours for pens 0..15, then the border.
_inks: .db 0, 26, 6, 18, 2, 24, 8, 20, 1, 3, 9, 11, 13, 15, 17, 25, 1
;; Same file without inks (0: the firmware keeps its own).
_plain:
    .dw _name
    .db 9
    .dw DISKSAVE_DATA
    .dw DISKSAVE_LENGTH
    .dw DISKSAVE_BUFFER
    .dw 0
    .db 0
;; Same file, data below FWK_DISK_SAVE_LOW: must be refused before any write.
_outside:
    .dw _name
    .db 9
    .dw 0x3F00
    .dw DISKSAVE_LENGTH
    .dw DISKSAVE_BUFFER
    .dw 0
    .db 0

.area _CODE
;; ----------------------------------------------------------------------------
;; _main
;;   Self-test of fwk_disk_save: with the firmware off, writes SAVED.DAT twice (the second write replaces the
;;   first) and checks that a descriptor outside the allowed RAM is refused.
;;   In : none (program entry; no register is read).
;;   Out: none; never returns (ends in an endless loop).
;;          Memory: disksave_status = 0x5A pass, 0xE1 first write failed, 0xE2 second write failed,
;;          0xE3 area outside the allowed RAM accepted, 0xE4 IX not preserved. SAVED.DAT then holds
;;          bytes i*3+1 (i = 0..299); the first write (i*3) is left as SAVED.BAK by AMSDOS.
;;   Clobbers: all (never returns)
;;   Notes: Does not return, so no register is preserved. fwk_disk_init runs before fwk_project_init so it can
;;          keep the firmware interrupt entry that fwk_disk_save puts back during the write.
;; ----------------------------------------------------------------------------
_main::
    call fwk_disk_init
    call fwk_project_init

    ;; First contents: byte i = i*3.
    ld c, #0
    call _fill
    ld ix, #_descriptor
    call fwk_disk_save
    ld a, #0xE1
    jr nc, _done
    ;; IX must still point at the descriptor.
    push ix
    pop hl
    ld de, #_descriptor
    or a
    sbc hl, de
    ld a, #0xE4
    jr nz, _done

    ;; Second contents: byte i = i*3 + 1, same file name, no inks.
    ld c, #1
    call _fill
    ld ix, #_plain
    call fwk_disk_save
    ld a, #0xE2
    jr nc, _done

    ld ix, #_outside
    call fwk_disk_save
    ld a, #0xE3
    jr c, _done
    ld a, #0x5A
_done:
    ld (disksave_status), a
_spin:
    jr _spin

;; ----------------------------------------------------------------------------
;; _fill
;;   Fills the DISKSAVE_LENGTH bytes at DISKSAVE_DATA with C, C+3, C+6... (mod 256).
;;   In : C = value of byte 0.
;;   Out: memory DISKSAVE_DATA..+DISKSAVE_LENGTH-1 written.
;;   Clobbers: AF, BC, DE, HL
;;   Notes: Each test write uses a different C, so the file on disc shows which write it came from.
;; ----------------------------------------------------------------------------
_fill:
    ld hl, #DISKSAVE_DATA
    ld de, #DISKSAVE_LENGTH
_fill_loop:
    ld (hl), c
    inc hl
    ld a, c
    add a, #3
    ld c, a
    dec de
    ld a, d
    or e
    jr nz, _fill_loop
    ret
