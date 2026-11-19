;; Firmware/AMSDOS workspace used by resources/disk.s during boot.
FWK_DISK_AMSDOS_ROM = 7
FWK_DISK_POOL_LOW = 0x0040
FWK_DISK_POOL_HIGH = 0xABFF
FWK_DISK_HEADER_BUFFER = 0xF800
;; fwk_disk_save: firmware entry kept by fwk_disk_init, and the descriptor
;; passed in IX (12 bytes, see docs/reference/architecture-and-api.md).
FWK_DISK_IRQ_VECTOR = 0x0038
FWK_DISK_AMSDOS_MESSAGES = 0xBE78  ;; 0xFF: AMSDOS reports errors without asking
FWK_DISK_SAVE_NAME = 0             ;; .dw file name (no NUL needed)
FWK_DISK_SAVE_NAME_LENGTH = 2      ;; .db length of the name
FWK_DISK_SAVE_DATA = 3             ;; .dw first byte to write
FWK_DISK_SAVE_LENGTH = 5           ;; .dw bytes to write
FWK_DISK_SAVE_BUFFER = 7           ;; .dw FWK_DISK_BUFFER_SIZE bytes for AMSDOS
FWK_DISK_SAVE_INKS = 9             ;; .dw 16 pens + border as firmware colours, or 0
FWK_DISK_SAVE_MODE = 11            ;; .db screen mode 0..2
FWK_DISK_SAVE_SIZE = 12
FWK_DISK_BUFFER_SIZE = 2048
FWK_DISK_SAVE_LOW = 0x4000         ;; data and buffer must lie in LOW..LIMIT-1
FWK_DISK_SAVE_LIMIT = 0xA700       ;; AMSDOS and firmware RAM start here
