;; Sprite-font text renderer derived from the text systems used by model01,
;; DeckTower and PocketFever. The original text routines declare
;; LGPL-3.0-or-later; asset provenance and its separate licensing uncertainty
;; are recorded in docs/provenance.md.
.module fwk_text
.include "cpctelera.h.s"

.globl cpct_drawSpriteMaskedAlignedTable_asm

FWK_TEXT_FONT_WIDTH       = 2
FWK_TEXT_FONT_HEIGHT      = 9
FWK_TEXT_FONT_GLYPHS      = 51
FWK_TEXT_SMALL_WIDTH      = 2
FWK_TEXT_SMALL_HEIGHT     = 5
FWK_TEXT_SMALL_GLYPHS     = 10
FWK_TEXT_MASK_TABLE       = 0x0100

.area _DATA

_fwk_text_font:           .dw _fwk_text_default_font
_fwk_text_small_font:     .dw _fwk_text_default_small_digits
_fwk_text_color:          .db 0
_fwk_text_string:         .dw 0
_fwk_text_destination:    .dw 0
_fwk_text_blit_source:    .dw 0
_fwk_text_blit_dest:      .dw 0
_fwk_text_blit_height:    .db 0
_fwk_text_number_dest:    .dw 0
_fwk_text_number_value:   .db 0
_fwk_text_digit:          .db 0
_fwk_text_number_hundreds:.db 0
_fwk_text_number_tens:    .db 0
_fwk_text_char_buffer:    .ds 18

.area _CODE

;; fwk_text_init
;; Installs the built-in fonts and copies the aligned transparency table to
;; 0x0100. Call after fwk_system_init, while firmware remains disabled.
;; Modified: AF, BC, DE, HL.
fwk_text_init::
    ld hl, #_fwk_text_mask_table_source
    ld de, #FWK_TEXT_MASK_TABLE
    ld bc, #256
    ldir
    ld hl, #_fwk_text_default_font
    ld de, #_fwk_text_default_small_digits
    call fwk_text_set_assets
    xor a
    ld (_fwk_text_color), a
    ret

;; fwk_text_set_assets
;; In: HL=51-glyph regular font (18 bytes/glyph),
;;     DE=10-digit small font (10 bytes/digit).
;; Modified: none; both pointers are retained by the renderer.
fwk_text_set_assets::
    ld (_fwk_text_font), hl
    ld (_fwk_text_small_font), de
    ret

;; fwk_text_set_color
;; In: A=colour-table index 0..14. Out: carry set when invalid.
;; The table reproduces the foreground/shadow encoding of the original games.
fwk_text_set_color::
    cp #15
    jr c, _fwk_text_set_color_valid
    scf
    ret
_fwk_text_set_color_valid:
    ld (_fwk_text_color), a
    or a
    ret

;; Migration alias retaining the old symbol/register shape.
;; In: L=NEW colour-table index 0..14; H ignored. Old pen-number semantics do
;; not apply to the sprite font.
fwk_text_set_colors::
    ld a, l
    jp fwk_text_set_color

;; fwk_text_draw
;; In: IY=NUL-terminated string, HL=screen pointer.
;; Supported: space, !, -, /, 0..9, :, >, ?, @ and A..Z.
;; Unsupported bytes advance one glyph cell without drawing.
;; Modified: AF, BC, DE, HL, IX, IY.
fwk_text_draw::
    push iy
    pop de
    ld (_fwk_text_string), de
    ld (_fwk_text_destination), hl
_fwk_text_draw_loop:
    ld hl, (_fwk_text_string)
    ld a, (hl)
    or a
    ret z
    inc hl
    ld (_fwk_text_string), hl

    ld de, (_fwk_text_destination)
    ld hl, #2
    add hl, de
    ld (_fwk_text_destination), hl

    cp #32
    jr z, _fwk_text_draw_loop
    cp #33
    jr z, _fwk_text_map_exclamation
    cp #45
    jr z, _fwk_text_map_hyphen
    cp #47
    jr z, _fwk_text_map_slash
    cp #58
    jr z, _fwk_text_map_colon
    cp #62
    jr z, _fwk_text_map_gt
    cp #48
    jr c, _fwk_text_map_question
    cp #58
    jr c, _fwk_text_map_digit
_fwk_text_map_question:
    cp #63
    jr z, _fwk_text_map_question_mark
    cp #64
    jr z, _fwk_text_map_at
    cp #65
    jr c, _fwk_text_draw_loop
    cp #91
    jr nc, _fwk_text_draw_loop
    sub #44                       ;; A..Z -> 21..46
    jr _fwk_text_draw_glyph
_fwk_text_map_question_mark:
    ld a, #19
    jr _fwk_text_draw_glyph
_fwk_text_map_at:
    ld a, #20
    jr _fwk_text_draw_glyph
_fwk_text_map_digit:
    sub #39                       ;; 0..9 -> 9..18
    jr _fwk_text_draw_glyph
_fwk_text_map_exclamation:
    xor a
    jr _fwk_text_draw_glyph
_fwk_text_map_colon:
    ld a, #47
    jr _fwk_text_draw_glyph
_fwk_text_map_slash:
    ld a, #48
    jr _fwk_text_draw_glyph
_fwk_text_map_hyphen:
    ld a, #49
    jr _fwk_text_draw_glyph
_fwk_text_map_gt:
    ld a, #50

_fwk_text_draw_glyph:
    ld hl, (_fwk_text_font)
    ld bc, #18
    or a
    jr z, _fwk_text_draw_glyph_ready
_fwk_text_glyph_offset:
    add hl, bc
    dec a
    jr nz, _fwk_text_glyph_offset
_fwk_text_draw_glyph_ready:
    ld a, #FWK_TEXT_FONT_HEIGHT
    ld c, #18
    call _fwk_text_recolor_and_draw
    jr _fwk_text_draw_loop

;; fwk_text_draw_small_digit
;; In: A=digit 0..9, HL=screen pointer. Out: carry set when invalid.
;; Modified: AF, BC, DE, HL, IX, IY.
fwk_text_draw_small_digit::
    cp #10
    jr c, _fwk_text_small_valid
    scf
    ret
_fwk_text_small_valid:
    ld (_fwk_text_digit), a
    ld (_fwk_text_number_dest), hl
    ld hl, (_fwk_text_small_font)
    ld bc, #10
    ld a, (_fwk_text_digit)
    or a
    jr z, _fwk_text_small_ready
_fwk_text_small_offset:
    add hl, bc
    dec a
    jr nz, _fwk_text_small_offset
_fwk_text_small_ready:
    ld de, (_fwk_text_number_dest)
    ld a, #FWK_TEXT_SMALL_HEIGHT
    ld c, #10
    call _fwk_text_recolor_and_draw
    or a
    ret

;; fwk_text_draw_small_u8
;; In: A=value 0..255, HL=screen pointer. Draws unpadded decimal digits.
;; Modified: AF, BC, DE, HL, IX, IY.
fwk_text_draw_small_u8::
    ld (_fwk_text_number_dest), hl
    ld b, #0
_fwk_text_hundreds_loop:
    cp #100
    jr c, _fwk_text_hundreds_done
    sub #100
    inc b
    jr _fwk_text_hundreds_loop
_fwk_text_hundreds_done:
    ld (_fwk_text_number_value), a
    ld a, b
    ld (_fwk_text_number_hundreds), a

    ld a, (_fwk_text_number_value)
    ld b, #0
_fwk_text_tens_loop:
    cp #10
    jr c, _fwk_text_tens_done
    sub #10
    inc b
    jr _fwk_text_tens_loop
_fwk_text_tens_done:
    ld (_fwk_text_number_value), a
    ld a, b
    ld (_fwk_text_number_tens), a

    ld a, (_fwk_text_number_hundreds)
    or a
    jr z, _fwk_text_maybe_tens
    call _fwk_text_draw_number_digit
_fwk_text_maybe_tens:
    ld a, (_fwk_text_number_hundreds)
    or a
    jr nz, _fwk_text_draw_tens
    ld a, (_fwk_text_number_tens)
    or a
    jr z, _fwk_text_draw_ones
_fwk_text_draw_tens:
    ld a, (_fwk_text_number_tens)
    call _fwk_text_draw_number_digit
_fwk_text_draw_ones:
    ld a, (_fwk_text_number_value)
    call _fwk_text_draw_number_digit
    ret

_fwk_text_draw_number_digit:
    ld hl, (_fwk_text_number_dest)
    push af
    call fwk_text_draw_small_digit
    pop af
    ld hl, (_fwk_text_number_dest)
    inc hl
    inc hl
    ld (_fwk_text_number_dest), hl
    ret

;; Recolour an original sprite into the scratch buffer and draw it masked.
;; In: HL=source, DE=destination, A=height, C=byte count (10 or 18).
_fwk_text_recolor_and_draw:
    ld (_fwk_text_blit_source), hl
    ld (_fwk_text_blit_dest), de
    ld (_fwk_text_blit_height), a
    push ix
    push iy

    ld a, (_fwk_text_color)
    add a, a
    add a, a
    ld hl, #_fwk_text_swap_colors
    ld e, a
    ld d, #0
    add hl, de
    push hl
    pop ix

    ld hl, (_fwk_text_blit_source)
    ld de, #_fwk_text_char_buffer
    ld b, #0
_fwk_text_recolor_loop:
    ld a, (hl)
    cp #0x55
    jr z, _fwk_text_color_0c
    cp #0xBF
    jr z, _fwk_text_color_sc
    cp #0xFF
    jr z, _fwk_text_color_cc
    cp #0xAA
    jr z, _fwk_text_color_c0
    jr _fwk_text_store_byte
_fwk_text_color_0c:
    ld a, 0(ix)
    jr _fwk_text_store_byte
_fwk_text_color_sc:
    ld a, 1(ix)
    jr _fwk_text_store_byte
_fwk_text_color_cc:
    ld a, 2(ix)
    jr _fwk_text_store_byte
_fwk_text_color_c0:
    ld a, 3(ix)
_fwk_text_store_byte:
    ld (de), a
    inc hl
    inc de
    dec c
    jr nz, _fwk_text_recolor_loop

    ld bc, #_fwk_text_char_buffer
    ld de, (_fwk_text_blit_dest)
    ld a, (_fwk_text_blit_height)
    cp #FWK_TEXT_SMALL_HEIGHT
    jr z, _fwk_text_small_dimensions
    ld ix, #0x0902
    jr _fwk_text_dimensions_ready
_fwk_text_small_dimensions:
    ld ix, #0x0502
_fwk_text_dimensions_ready:
    ld hl, #FWK_TEXT_MASK_TABLE
    call cpct_drawSpriteMaskedAlignedTable_asm
    pop iy
    pop ix
    ret

;; Original colour substitutions. Pen 14 is the fixed shadow component.
_fwk_text_swap_colors:
    .db 0x55,0xBF,0xFF,0xAA, 0x14,0x3D,0x3C,0x28
    .db 0x50,0xB5,0xF0,0xA0, 0x04,0x1D,0x0C,0x08
    .db 0x10,0x35,0x30,0x20, 0x45,0x9F,0xCF,0x8A
    .db 0x41,0x97,0xC3,0x82, 0x05,0x1F,0x0F,0x0A
    .db 0x01,0x17,0x03,0x02, 0x11,0x37,0x33,0x22
    .db 0x51,0xB7,0xF3,0xA2, 0x00,0x15,0x00,0x00
    .db 0x40,0x95,0xC0,0x80, 0x44,0x9D,0xCC,0x88
    .db 0x54,0xBD,0xFC,0xA8

;; Generated byte data retained in the same-stem include so example staging
;; automatically carries the default assets together with this module.
.include "ui/text.inc"
