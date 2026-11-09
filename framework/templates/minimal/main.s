.module game_main
;; Minimal project on GlasnostFWK: only the main loop and a welcome message.
;; Replace this with your own game.
.include "common.inc"
.include "generated/project.inc"

.area _DATA
game_status::  .db 0              ; 0x5A once the game is running, else the ABI error code

_game_str_welcome: .asciz "WELCOME"
_game_str_help:    .asciz "START CODING!"

;; Palette: 16 hardware colours.
_game_palette:
    .db 0x14, 0x0A, 0x00, 0x1C, 0x0C, 0x0E, 0x0A, 0x07, 0x16, 0x1E, 0x13, 0x1F, 0x15, 0x18, 0x04, 0x0B

.area _CODE

;; ----------------------------------------------------------------------------
;; _main
;;   Descripcion: punto de entrada. Inicializa el framework, dibuja el mensaje de
;;                bienvenida y entra en el bucle principal game_frame.
;;   Entrada:     ninguna (arranque en 0x0200).
;;   Salida:      ninguna (bucle infinito).
;;   Modifica:    todo el estado del juego y del framework.
;;   Notas:       game_status vale 0x5A si todo arranco; otro valor es codigo de error.
;; ----------------------------------------------------------------------------
_main::
    call fwk_project_init            ; inicializa el proyecto (transparencia, bancos)
    call fwk_video_init             ; inicializa el subsistema de video
    call fwk_text_init              ; inicializa la fuente de texto Mode 0
    ld hl, #_game_palette           ; HL = paleta de 16 colores
    ld de, #16                      ; DE = numero de colores
    call cpct_setPalette_asm        ; instala la paleta en el Gate Array
    xor a                           ; A = 0
    call fwk_video_clear_visible    ; limpia la pantalla visible

    ;; Draw the welcome message.
    ld b, #MINIMAL_TEXT_Y_WELCOME   ; B = scanline del titulo
    ld hl, #_game_str_welcome       ; HL = "WELCOME"
    call _minimal_text              ; dibuja el texto
    ld b, #MINIMAL_TEXT_Y_HELP      ; B = scanline de la ayuda
    ld hl, #_game_str_help          ; HL = "START CODING!"
    call _minimal_text              ; dibuja la ayuda

    ld a, #0x5A
    ld (game_status), a             ; 0x5A = OK; any other value is an ABI error code.

;; ----------------------------------------------------------------------------
;; game_frame
;;   Descripcion: bucle principal. Espera un frame y repite.
;;   Entrada:     ninguna.
;;   Salida:      ninguna (bucle infinito).
;;   Modifica:    estado del framework.
;; ----------------------------------------------------------------------------
game_frame:
    call fwk_system_wait_frame      ; espera al VSYNC
    jp game_frame                   ; siguiente frame

;; ----------------------------------------------------------------------------
;; _minimal_text
;;   Descripcion: dibuja una cadena de texto en la columna izquierda.
;;   Entrada:     B = scanline (Y) donde dibujar.
;;                HL = puntero a la cadena terminada en 0.
;;   Salida:      ninguna.
;;   Modifica:    AF, BC, DE, HL, IY.
;;   Notas:       Tail-jump a fwk_text_draw, que retorna al llamador.
;; ----------------------------------------------------------------------------
_minimal_text:
    push hl                          ; guarda el puntero a la cadena
    ld l, b
    ld h, #0
    ld c, #MINIMAL_TEXT_X
    call fwk_video_get_ptr           ; HL = direccion de pantalla
    pop iy                           ; IY = cadena
    jp fwk_text_draw                 ; dibuja la cadena
    ld l, b
    ld h, #0
    ld c, #MINIMAL_TEXT_X
    call fwk_video_get_ptr
    pop iy
    jp fwk_text_draw