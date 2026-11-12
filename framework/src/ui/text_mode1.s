;; One-byte-wide Mode 1 sprite font. The bundled 4x9 glyphs come from
;; DeckHero/assets/font_chars_1.png; see docs/design/provenance.md.
.module fwk_text_mode1
.include "cpctelera.h.s"
.include "project_config.inc"

.globl fwk_transparency_draw

FWK_TEXT_M1_GLYPH_HEIGHT = 9
FWK_TEXT_M1_GLYPHS = 43
FWK_TEXT_M1_SMALL_HEIGHT = 5

.area _DATA
_fwk_m1_font:          .dw _fwk_m1_default_font
_fwk_m1_small_font:    .dw _fwk_m1_default_small_digits
_fwk_m1_color:         .db 3
_fwk_m1_string:        .dw 0
_fwk_m1_destination:   .dw 0
_fwk_m1_source:        .dw 0
_fwk_m1_blit_dest:     .dw 0
_fwk_m1_height:        .db 0
_fwk_m1_number_dest:   .dw 0
_fwk_m1_number_value:  .db 0
_fwk_m1_hundreds:      .db 0
_fwk_m1_tens:          .db 0
_fwk_m1_digit:         .db 0
_fwk_m1_char_buffer:   .ds 9

.area _CODE

;; fwk_text_init
;; Installs the bundled Mode 1 font and selects pen 3. Requires project pen 0
;; as the transparency key, installed by fwk_project_init.
fwk_text_init::
    ld hl, #_fwk_m1_default_font
    ld de, #_fwk_m1_default_small_digits
    call fwk_text_set_assets
    ld a, #3
    ld (_fwk_m1_color), a
    ret

;; fwk_text_set_assets
;; In: HL=43 regular glyphs, 9 bytes each; DE=10 small digits, 5 bytes each.
fwk_text_set_assets::
    ld (_fwk_m1_font), hl
    ld (_fwk_m1_small_font), de
    ret

;; fwk_text_set_color
;; In: A=foreground pen 1..3; pen 0 is reserved for transparency.
;; Out: carry set for an invalid pen, clear on success.
fwk_text_set_color::
    or a
    jr z, _fwk_m1_color_invalid
    cp #4
    jr nc, _fwk_m1_color_invalid
    ld (_fwk_m1_color), a
    or a
    ret
_fwk_m1_color_invalid:
    scf
    ret

;; Migration alias: L=foreground pen 1..3, H ignored.
fwk_text_set_colors::
    ld a, l
    jp fwk_text_set_color

;; fwk_text_draw
;; In: IY=NUL-terminated ASCII, HL=screen pointer. One byte (4 pixels) per
;; glyph; supports space, !, comma, -, ., 0..9, :, ?, @ and A..Z.
;; Unsupported characters leave a blank glyph cell.
;; Modified: AF, BC, DE, HL; IX/IY preserved.
fwk_text_draw::
    push iy
    pop de
    ld (_fwk_m1_string), de
    ld (_fwk_m1_destination), hl
_fwk_m1_draw_loop:
    ld hl, (_fwk_m1_string)
    ld a, (hl)
    or a
    ret z
    inc hl
    ld (_fwk_m1_string), hl
    ld de, (_fwk_m1_destination)
    ld hl, #1
    add hl, de
    ld (_fwk_m1_destination), hl

    cp #32
    jr z, _fwk_m1_draw_loop
    cp #33
    jr z, _fwk_m1_exclamation
    cp #44
    jr z, _fwk_m1_comma
    cp #45
    jr z, _fwk_m1_hyphen
    cp #46
    jr z, _fwk_m1_period
    cp #58
    jr z, _fwk_m1_colon
    cp #63
    jr z, _fwk_m1_question
    cp #64
    jr z, _fwk_m1_at
    cp #48
    jr c, _fwk_m1_draw_loop
    cp #58
    jr c, _fwk_m1_digit_glyph
    cp #65
    jr c, _fwk_m1_draw_loop
    cp #91
    jr nc, _fwk_m1_draw_loop
    sub #48                    ;; A..Z -> 17..42
    jr _fwk_m1_draw_glyph
_fwk_m1_digit_glyph:
    sub #44                    ;; 0..9 -> 4..13
    jr _fwk_m1_draw_glyph
_fwk_m1_exclamation:
    xor a
    jr _fwk_m1_draw_glyph
_fwk_m1_comma:
    ld a, #1
    jr _fwk_m1_draw_glyph
_fwk_m1_hyphen:
    ld a, #2
    jr _fwk_m1_draw_glyph
_fwk_m1_period:
    ld a, #3
    jr _fwk_m1_draw_glyph
_fwk_m1_colon:
    ld a, #14
    jr _fwk_m1_draw_glyph
_fwk_m1_question:
    ld a, #15
    jr _fwk_m1_draw_glyph
_fwk_m1_at:
    ld a, #16
_fwk_m1_draw_glyph:
    ld hl, (_fwk_m1_font)
    ld bc, #9
    or a
    jr z, _fwk_m1_glyph_ready
_fwk_m1_glyph_offset:
    add hl, bc
    dec a
    jr nz, _fwk_m1_glyph_offset
_fwk_m1_glyph_ready:
    ld de, (_fwk_m1_destination)
    dec de
    ld a, #FWK_TEXT_M1_GLYPH_HEIGHT
    call _fwk_m1_recolor_and_draw
    jr _fwk_m1_draw_loop

;; fwk_text_draw_small_digit
;; In: A=0..9, HL=screen pointer. Out: carry set if A is invalid.
;; Modified: AF, BC, DE, HL; IX/IY preserved.
fwk_text_draw_small_digit::
    cp #10
    jr c, _fwk_m1_small_valid
    scf
    ret
_fwk_m1_small_valid:
    ld (_fwk_m1_digit), a
    ld (_fwk_m1_number_dest), hl
    ld hl, (_fwk_m1_small_font)
    ld bc, #5
    ld a, (_fwk_m1_digit)
    or a
    jr z, _fwk_m1_small_ready
_fwk_m1_small_offset:
    add hl, bc
    dec a
    jr nz, _fwk_m1_small_offset
_fwk_m1_small_ready:
    ld de, (_fwk_m1_number_dest)
    ld a, #FWK_TEXT_M1_SMALL_HEIGHT
    call _fwk_m1_recolor_and_draw
    or a
    ret

;; fwk_text_draw_small_u8
;; In: A=0..255, HL=screen pointer. Draws unpadded 1-byte-wide digits.
;; Modified: AF, BC, DE, HL; IX/IY preserved.
fwk_text_draw_small_u8::
    ld (_fwk_m1_number_dest), hl
    ld b, #0
_fwk_m1_hundreds_loop:
    cp #100
    jr c, _fwk_m1_hundreds_done
    sub #100
    inc b
    jr _fwk_m1_hundreds_loop
_fwk_m1_hundreds_done:
    ld (_fwk_m1_number_value), a
    ld a, b
    ld (_fwk_m1_hundreds), a
    ld a, (_fwk_m1_number_value)
    ld b, #0
_fwk_m1_tens_loop:
    cp #10
    jr c, _fwk_m1_tens_done
    sub #10
    inc b
    jr _fwk_m1_tens_loop
_fwk_m1_tens_done:
    ld (_fwk_m1_number_value), a
    ld a, b
    ld (_fwk_m1_tens), a
    ld a, (_fwk_m1_hundreds)
    or a
    jr z, _fwk_m1_maybe_tens
    call _fwk_m1_draw_number_digit
_fwk_m1_maybe_tens:
    ld a, (_fwk_m1_hundreds)
    or a
    jr nz, _fwk_m1_draw_tens
    ld a, (_fwk_m1_tens)
    or a
    jr z, _fwk_m1_draw_ones
_fwk_m1_draw_tens:
    ld a, (_fwk_m1_tens)
    call _fwk_m1_draw_number_digit
_fwk_m1_draw_ones:
    ld a, (_fwk_m1_number_value)
    call _fwk_m1_draw_number_digit
    ret

_fwk_m1_draw_number_digit:
    ld hl, (_fwk_m1_number_dest)
    call fwk_text_draw_small_digit
    ld hl, (_fwk_m1_number_dest)
    inc hl
    ld (_fwk_m1_number_dest), hl
    ret

;; Draw one 1-byte-wide glyph. The original DeckHero glyphs use pen 1 in the
;; high nibble; shift/copy it to the selected pen while keeping pen 0 clear.
;; In: HL=source, DE=screen pointer, A=height 5 or 9.
_fwk_m1_recolor_and_draw:
    ld (_fwk_m1_source), hl
    ld (_fwk_m1_blit_dest), de
    ld (_fwk_m1_height), a
    push ix
    push iy
    ld c, a
    ld de, #_fwk_m1_char_buffer
_fwk_m1_recolor_loop:
    ld a, (hl)
    ld b, a
    ld a, (_fwk_m1_color)
    cp #1
    jr z, _fwk_m1_recolor_copy
    cp #2
    jr z, _fwk_m1_recolor_low
    ld a, b
    rrca
    rrca
    rrca
    rrca
    or b
    jr _fwk_m1_recolor_store
_fwk_m1_recolor_low:
    ld a, b
    rrca
    rrca
    rrca
    rrca
    jr _fwk_m1_recolor_store
_fwk_m1_recolor_copy:
    ld a, b
_fwk_m1_recolor_store:
    ld (de), a
    inc hl
    inc de
    dec c
    jr nz, _fwk_m1_recolor_loop

    ld bc, #_fwk_m1_char_buffer
    ld de, (_fwk_m1_blit_dest)
    ld a, (_fwk_m1_height)
    ld ix, #0x0901
    cp #5
    jr nz, _fwk_m1_dimensions_ready
    ld ix, #0x0501
_fwk_m1_dimensions_ready:
    call fwk_transparency_draw
    pop iy
    pop ix
    ret

.include "ui/text_mode1.inc"
