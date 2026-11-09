;; Firmware-backed DSK loader. Call before fwk_system_init disables firmware.
.module fwk_disk
.include "resources/disk.inc"

.area _CODE

;; Reconnect AMSDOS after BASIC RUN" has reset the CAS vectors to cassette.
;; Input: none. Output: none. Modified: AF,B,C,DE,HL.
;; Interrupts are enabled. Not safe after fwk_system_init.
fwk_disk_init::
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
