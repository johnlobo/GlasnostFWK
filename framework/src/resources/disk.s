;; Firmware-backed DSK loader and writer. fwk_disk_init runs before fwk_system_init disables firmware.
.module fwk_disk
.include "resources/disk.inc"
.globl _cpct_mode_rom_status

.area _CODE

;; Reconnect AMSDOS after BASIC RUN" has reset the CAS vectors to cassette,
;; and keep the firmware interrupt entry for fwk_disk_save.
;; Input: none. Output: none. Modified: AF,B,C,DE,HL.
;; Interrupts are enabled. Not safe after fwk_system_init.
fwk_disk_init::
    ld hl, #FWK_DISK_IRQ_VECTOR
    ld de, #_fwk_disk_firmware_vector
    ld bc, #3
    ldir
    ld a, #1
    ld (_fwk_disk_ready), a
    ei
    ld c, #FWK_DISK_AMSDOS_ROM
    ld de, #FWK_DISK_POOL_LOW
    ld hl, #FWK_DISK_POOL_HIGH
    call 0xBCCE                    ;; KL INIT BACK
    ret

;; Open, load and close one AMSDOS file.
;; Input: HL=filename, B=filename length, DE=destination.
;; Output: carry set and BC=logical file length when OPEN succeeded;
;;         carry clear when OPEN failed. Modified: AF,DE,HL.
;; Uses 0xF800..0xFFFF as the firmware header buffer and is not reentrant.
fwk_disk_load::
    push de                        ;; destination survives CAS IN OPEN
    ld de, #FWK_DISK_HEADER_BUFFER
    call 0xBC77                    ;; CAS IN OPEN
    jr nc, _open_failed
    pop hl                         ;; destination for CAS IN DIRECT
    push bc                        ;; preserve logical length for caller
    call 0xBC83                    ;; CAS IN DIRECT
    call 0xBC7A                    ;; CAS IN CLOSE; also stops motor
    pop bc
    scf
    ret
_open_failed:
    pop de
    or a                           ;; explicit carry clear
    ret

;; ----------------------------------------------------------------------------
;; Writing a file while the game runs. fwk_system_init only replaces the JP at
;; 0x0038; the firmware RAM above FWK_DISK_SAVE_LIMIT stays intact, so putting
;; the firmware interrupt back for the duration of the write is enough for
;; AMSDOS. fwk_disk_init keeps that firmware entry.
;; ----------------------------------------------------------------------------
.area _DATA
_fwk_disk_firmware_vector: .ds 3
_fwk_disk_game_vector:     .ds 3
_fwk_disk_save_copy:       .ds FWK_DISK_SAVE_SIZE
_fwk_disk_messages:        .db 0
_fwk_disk_result:          .db 0
_fwk_disk_ready:           .db 0     ;; 1 once fwk_disk_init kept the vector

.area _CODE

;; fwk_disk_save
;; In: IX=descriptor (FWK_DISK_SAVE_* in disk.inc). fwk_disk_init must have run
;;     at boot. Interrupts end enabled.
;; Out: carry set when the whole file was written; carry clear when
;;      fwk_disk_init never ran, data or buffer fall outside
;;      FWK_DISK_SAVE_LOW..FWK_DISK_SAVE_LIMIT-1, or AMSDOS failed (no disc,
;;      disc full, write protected). AMSDOS error prompts are turned off, so a
;;      failure never waits for a key. An existing file becomes .BAK (AMSDOS).
;; Modified: AF,BC,DE,HL. IX and IY preserved.
;; The game's interrupt (music, frame counter) stops during the write; the
;; firmware keeps the descriptor's mode and inks so the screen does not change.
;; Not reentrant. Mode 0..2 and the ROMs-off state are set on the Gate Array
;; (and in CPCtelera's _cpct_mode_rom_status) on return. fwk_disk_init must run
;; while the firmware is on, before fwk_project_init. Data and buffer must not
;; overlap. Firmware entries are the RAM jumpblock: they map the ROMs
;; themselves, so the call works with both ROMs off.
fwk_disk_save::
    push ix
    push iy
    push ix
    pop hl
    ld de, #_fwk_disk_save_copy
    ld bc, #FWK_DISK_SAVE_SIZE
    ldir
    ld a, (_fwk_disk_ready)
    or a
    jp z, _save_refused
    ld hl, (_fwk_disk_save_copy + FWK_DISK_SAVE_DATA)
    ld de, (_fwk_disk_save_copy + FWK_DISK_SAVE_LENGTH)
    call _fwk_disk_check_area
    jp nc, _save_refused
    ld hl, (_fwk_disk_save_copy + FWK_DISK_SAVE_BUFFER)
    ld de, #FWK_DISK_BUFFER_SIZE
    call _fwk_disk_check_area
    jp nc, _save_refused

    di
    ld hl, #FWK_DISK_IRQ_VECTOR
    ld de, #_fwk_disk_game_vector
    ld bc, #3
    ldir
    ld hl, #_fwk_disk_firmware_vector
    ld de, #FWK_DISK_IRQ_VECTOR
    ld bc, #3
    ldir
    ei
    ld a, (FWK_DISK_AMSDOS_MESSAGES)
    ld (_fwk_disk_messages), a
    ld a, #0xFF
    ld (FWK_DISK_AMSDOS_MESSAGES), a
    xor a
    ld (_fwk_disk_result), a

    ;; The firmware interrupt re-applies its own mode and inks: give it the
    ;; game's ones first.
    ld a, (_fwk_disk_save_copy + FWK_DISK_SAVE_MODE)
    call 0xBD1C                    ;; MC SET MODE (screen not cleared)
    ld hl, (_fwk_disk_save_copy + FWK_DISK_SAVE_INKS)
    ld a, h
    or l
    jr z, _save_open
    xor a
_save_ink:
    push af
    push hl
    ld b, (hl)
    ld c, b
    call 0xBC32                    ;; SCR SET INK: A=pen, B=C=colour
    pop hl
    pop af
    inc hl
    inc a
    cp #16
    jr nz, _save_ink
    ld b, (hl)
    ld c, b
    call 0xBC38                    ;; SCR SET BORDER

_save_open:
    ld hl, (_fwk_disk_save_copy + FWK_DISK_SAVE_NAME)
    ld a, (_fwk_disk_save_copy + FWK_DISK_SAVE_NAME_LENGTH)
    ld b, a
    ld de, (_fwk_disk_save_copy + FWK_DISK_SAVE_BUFFER)
    call 0xBC8C                    ;; CAS OUT OPEN
    jr nc, _save_restore
    ld hl, (_fwk_disk_save_copy + FWK_DISK_SAVE_DATA)
    ld de, (_fwk_disk_save_copy + FWK_DISK_SAVE_LENGTH)
    ld bc, #0                      ;; entry address: data file
    ld a, #2                       ;; binary
    call 0xBC98                    ;; CAS OUT DIRECT
    jr nc, _save_abandon
    call 0xBC8F                    ;; CAS OUT CLOSE
    jr nc, _save_restore
    ld a, #1
    ld (_fwk_disk_result), a
    jr _save_restore
_save_abandon:
    call 0xBC92                    ;; CAS OUT ABANDON

_save_restore:
    ld a, (_fwk_disk_messages)
    ld (FWK_DISK_AMSDOS_MESSAGES), a
    di
    ld hl, #_fwk_disk_game_vector
    ld de, #FWK_DISK_IRQ_VECTOR
    ld bc, #3
    ldir
    ;; Gate Array: mode, both ROMs off (the firmware may leave them on).
    ld a, (_fwk_disk_save_copy + FWK_DISK_SAVE_MODE)
    and #3
    or #0x8C
    ld (_cpct_mode_rom_status), a  ;; keep CPCtelera's copy in step
    ld bc, #0x7F00
    out (c), a
    ei
    pop iy
    pop ix
    ld a, (_fwk_disk_result)
    rrca                           ;; bit 0 to carry
    ret

_save_refused:
    pop iy
    pop ix
    or a
    ret

;; In: HL=start, DE=length. Out: carry set when start >= FWK_DISK_SAVE_LOW and
;; start + length <= FWK_DISK_SAVE_LIMIT. Modified: AF,DE,HL.
_fwk_disk_check_area:
    ld a, h
    cp #>FWK_DISK_SAVE_LOW
    jr c, _area_outside
    add hl, de
    jr c, _area_outside
    ld de, #FWK_DISK_SAVE_LIMIT + 1
    or a
    sbc hl, de                     ;; carry when end < LIMIT + 1
    ret
_area_outside:
    or a
    ret
