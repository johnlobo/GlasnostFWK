.module example_diskload
.include "disk_files.inc"

.globl fwk_disk_init, fwk_disk_load, fwk_zx7b_unpack
.globl fwk_system_init, fwk_system_wait_frame

DISKLOAD_RAW_ADDR = 0x9000
DISKLOAD_PACKED_ADDR = 0x9200
DISKLOAD_UNPACKED_ADDR = 0x9400

.area _DATA
diskload_status:: .db 0
diskload_raw_length:: .dw 0
diskload_packed_length:: .dw 0

_raw_name: .ascii "RAWDATA.BIN"
_packed_name: .ascii "PACKDATA.ZX7"
_pattern: .db 0x00, 0x4C, 0x41, 0x53, 0x4E, 0x4F, 0x53, 0x54
          .db 0x2D, 0x44, 0x49, 0x53, 0x4B, 0x2D, 0x5A, 0x58

.area _CODE

_main::
    call fwk_disk_init

    ld hl, #_raw_name
    ld b, #11
    ld de, #DISKLOAD_RAW_ADDR
    call fwk_disk_load
    jr nc, _failed_open_raw
    ld (diskload_raw_length), bc
    ld hl, #FWK_DISK_RAW_SIZE
    or a
    sbc hl, bc
    jr nz, _failed_length

    ld hl, #_packed_name
    ld b, #12
    ld de, #DISKLOAD_PACKED_ADDR
    call fwk_disk_load
    jr nc, _failed_open_packed
    ld (diskload_packed_length), bc
    ld hl, #FWK_DISK_PACKED_SIZE
    or a
    sbc hl, bc
    jr nz, _failed_length

    ld hl, #DISKLOAD_PACKED_ADDR + FWK_DISK_PACKED_SIZE - 1
    ld de, #DISKLOAD_UNPACKED_ADDR + FWK_DISK_PACKED_UNPACKED_SIZE - 1
    call fwk_zx7b_unpack

    ;; The raw file and decompressed file must match byte for byte.
    ld hl, #DISKLOAD_RAW_ADDR
    ld de, #DISKLOAD_UNPACKED_ADDR
    ld bc, #FWK_DISK_RAW_SIZE
_compare_loaded:
    ld a, (de)
    cp (hl)
    jr nz, _failed_compare
    inc de
    inc hl
    dec bc
    ld a, b
    or c
    jr nz, _compare_loaded

    ;; Also check the independent 16-byte witness pattern from the manifest.
    ld hl, #DISKLOAD_RAW_ADDR
    ld de, #_pattern
    ld b, #16
_compare_pattern:
    ld a, (de)
    cp (hl)
    jr nz, _failed_compare
    inc de
    inc hl
    djnz _compare_pattern

    ld a, #0x5A
    ld (diskload_status), a
    jr _start_runtime

_failed_open_raw:
    ld a, #0xE1
    jr _record_failure
_failed_open_packed:
    ld a, #0xE2
    jr _record_failure
_failed_length:
    ld a, #0xE3
    jr _record_failure
_failed_compare:
    ld a, #0xE4
_record_failure:
    ld (diskload_status), a

_start_runtime:
    call fwk_system_init
_loop:
    call fwk_system_wait_frame
    jr _loop
