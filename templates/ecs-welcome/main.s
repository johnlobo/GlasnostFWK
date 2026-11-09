.module game_main
;; Welcome project on GlasnostFWK ECS 2.0: a ship you move with the cursor keys
;; and three drones that patrol. It shows the pieces every game uses: a manager
;; with its entities, the input, behavior and motion systems, a selective
;; renderer with background pools, and text. Replace it with your own game.
;;
;; This file holds code and data only; .globl declarations, constants and macros
;; live in common.inc. generated/project.inc is written by `glasnost config`:
;; do not edit it.
.include "common.inc"
.include "generated/project.inc"

.area _DATA

;; ---- Public state, observable by tests and the emulator ----
game_status::  .db 0              ; 0x5A once the game is running, else the ABI error code
game_player::  .dw 0              ; address of the player entity

;; ---- Texts ----
_game_str_welcome: .asciz "WELCOME TO"
_game_str_help:    .asciz "CURSOR KEYS MOVE"

;; ---- Sprites and palette come from assets/generated/assets.s (assets/assets.json). ----

;; ---- Tilemap: types table (id -> type) and render descriptors ----
_game_types: .db 0, 0, 0, 0
game_view:
    .dw game_tileset
    .db 0, 0, 0
    .dw GAME_MAP_SCREEN_Y
    .db GAME_MAP_WIDTH, GAME_MAP_HEIGHT, 4
game_map_desc:
    .dw game_map, _game_types
    .db GAME_MAP_WIDTH, GAME_MAP_HEIGHT, 2, 3, 4, 8, 4

;; ---- Entity storage: ECS_ENTITY_SIZE-byte slots, filled in spawn order ----
_game_tpl:      .ds ECS_ENTITY_SIZE    ; template built from a spawn row, copied into the manager
game_storage::  .ds ECS_ENTITY_SIZE * GAME_CAP
FWK_ECS_MANAGER_DESCRIPTOR game_manager, game_storage, GAME_CAP

;; ---- Renderer: one pool of GAME_CAP background buffers of 32 bytes (4 x 8) ----
FWK_ECS_RENDER_POOL game_pool32, 32, GAME_CAP
_game_pools:    .dw game_pool32
_game_managers: .dw game_manager
_game_work:     .ds 8 * GAME_CAP
FWK_ECS_RENDER_SCENE game_scene, _game_managers, 1, _game_work, GAME_CAP, _game_pools, 1

;; ---- Keyboard: (key, action bit) pairs ended by a zero action ----
game_bindings:
    .dw Key_CursorLeft
    .db GAME_INPUT_LEFT
    .dw Key_CursorRight
    .db GAME_INPUT_RIGHT
    .dw Key_CursorUp
    .db GAME_INPUT_UP
    .dw Key_CursorDown
    .db GAME_INPUT_DOWN
    .dw 0
    .db 0

;; ---- Drone patrol program: right for half a leg, then left and right in full legs ----
_game_program_drone:
    FWK_BEHAVIOR_SET_VX 1
    FWK_BEHAVIOR_WAIT GAME_DRONE_FIRST_LEG, _game_program_drone_left
_game_program_drone_left:
    FWK_BEHAVIOR_SET_VX -1
    FWK_BEHAVIOR_WAIT GAME_DRONE_LEG, _game_program_drone_right
_game_program_drone_right:
    FWK_BEHAVIOR_SET_VX 1
    FWK_BEHAVIOR_WAIT GAME_DRONE_LEG, _game_program_drone_left

;; ---- Spawn rows (see GAME_ROW) ----
_game_row_player: GAME_ROW GAME_PLAYER_COMPS, GAME_T_PLAYER, 38, 170, 4, 8, game_ship_pixels, 0
_game_row_drone0: GAME_ROW GAME_DRONE_COMPS, GAME_T_DRONE, 30, 70, 4, 8, game_drone_pixels, _game_program_drone
_game_row_drone1: GAME_ROW GAME_DRONE_COMPS, GAME_T_DRONE, 40, 100, 4, 8, game_drone_pixels, _game_program_drone
_game_row_drone2: GAME_ROW GAME_DRONE_COMPS, GAME_T_DRONE, 30, 130, 4, 8, game_drone_pixels, _game_program_drone

.area _CODE

;; ----------------------------------------------------------------------------
;; _game_fail
;;   Descripcion: detiene el juego y publica el codigo de error ABI en game_status.
;;   Entrada:     A = codigo de error (carry activo en la rutina que fallo).
;;   Salida:      ninguna (bucle infinito).
;;   Modifica:    game_status; espera un frame en cada iteracion.
;;   Notas:       Bucle infinito para que el emulador/depurador pueda leer
;;                game_status y el codigo de error.
;; ----------------------------------------------------------------------------
_game_fail:
    ld (game_status), a          ; publica el codigo de error para depuracion
_game_fail_loop:
    call fwk_system_wait_frame    ; espera al siguiente VSYNC
    jr _game_fail_loop           ; bucle infinito

;; ----------------------------------------------------------------------------
;; _game_spawn
;;   Descripcion: construye una entidad ECS a partir de una fila de spawn (GAME_ROW)
;;                y la crea en el manager indicado.
;;   Entrada:     IX = direccion del manager ECS.
;;                HL = direccion de la fila de spawn (components, type, x, y,
;;                     width, height, sprite, behavior program).
;;   Salida:      IY = direccion de la entidad creada; carry = 0 si OK.
;;   Modifica:    AF, BC, DE, HL, IY, _game_tpl (plantilla temporal).
;;   Notas:       IX se preserva. La plantilla se rellena campo a campo desde la fila.
;; ----------------------------------------------------------------------------
_game_spawn:
    push hl                          ; guarda la fila de spawn
    ld hl, #_game_tpl
    ld de, #_game_tpl + 1
    ld (hl), #0
    ld bc, #ECS_ENTITY_SIZE - 1
    ldir
    pop hl
    ld iy, #_game_tpl
    ld a, (hl)
    inc hl
    ld ECS_E_COMPONENTS(iy), a
    ld a, (hl)
    inc hl
    ld ECS_E_COMPONENTS+1(iy), a
    ld ECS_E_STATUS(iy), #ECS_STATUS_ACTIVE
    ld a, (hl)
    inc hl
    ld ECS_E_TYPE(iy), a
    ld a, (hl)
    inc hl
    ld ECS_E_X(iy), a
    ld a, (hl)
    inc hl
    ld ECS_E_Y(iy), a
    ld a, (hl)
    inc hl
    ld ECS_E_WIDTH(iy), a
    ld a, (hl)
    inc hl
    ld ECS_E_HEIGHT(iy), a
    ld a, (hl)
    inc hl
    ld ECS_E_RENDER_SPRITE(iy), a
    ld a, (hl)
    inc hl
    ld ECS_E_RENDER_SPRITE+1(iy), a
    ld a, (hl)
    inc hl
    ld ECS_E_BEHAVIOR_PROGRAM(iy), a
    ld a, (hl)
    ld ECS_E_BEHAVIOR_PROGRAM+1(iy), a
    ld ECS_E_RENDER_FLAGS(iy), #ECS_RENDER_VISIBLE | ECS_RENDER_DIRTY
    ld hl, #_game_tpl
    jp fwk_ecs_entity_create

;; ----------------------------------------------------------------------------
;; _game_text
;;   Descripcion: dibuja una cadena de texto en la columna izquierda (GAME_TEXT_X)
;;                en la scanline indicada.
;;   Entrada:     B = scanline (Y) donde dibujar.
;;                HL = puntero a la cadena terminada en 0.
;;   Salida:      ninguna.
;;   Modifica:    AF, BC, DE, HL, IY.
;;   Notas:       Tail-jump a fwk_text_draw, que retorna al llamador.
;; ----------------------------------------------------------------------------
_game_text:
    push hl                          ; guarda el puntero a la cadena
    ld l, b
    ld h, #0
    ld c, #GAME_TEXT_X
    call fwk_video_get_ptr
    pop iy
    jp fwk_text_draw


;; Keeps the player inside the play area, run after motion. Positions are
;; unsigned bytes, but fwk_ecs_system_motion_u8 already saturates at 0, so with it the
;; first test never fires: it only guards a position that wrapped to 254.
;; ----------------------------------------------------------------------------
;; _game_clamp
;;   Descripcion: mantiene la entidad dentro del area de juego (clamp de X e Y).
;;   Entrada:     IX = manager (se preserva).
;;                IY = entidad actual (se preserva).
;;   Salida:      A = 0, carry limpio (contrato de fwk_ecs_system_run).
;;   Modifica:    A (restaura IX e IY).
;;   Notas:       Posiciones unsigned; fwk_ecs_system_motion_u8 ya satura en 0.
;; ----------------------------------------------------------------------------
_game_clamp:
    push ix                          ; preserva el manager
    push iy                          ; preserva la entidad
    ld a, ECS_E_X(iy)
    cp #200
    jr c, _game_clamp_x_max
    xor a
    jr _game_clamp_x_set
_game_clamp_x_max:
    cp #GAME_X_MAX + 1
    jr c, _game_clamp_y
    ld a, #GAME_X_MAX
_game_clamp_x_set:
    ld ECS_E_X(iy), a
_game_clamp_y:
    ld a, ECS_E_Y(iy)
    cp #GAME_Y_MIN
    jr nc, _game_clamp_y_max
    ld a, #GAME_Y_MIN
    jr _game_clamp_y_set
_game_clamp_y_max:
    cp #GAME_Y_MAX + 1
    jr c, _game_clamp_done
    ld a, #GAME_Y_MAX
_game_clamp_y_set:
    ld ECS_E_Y(iy), a
_game_clamp_done:
    pop iy
    pop ix
    xor a
    ret

;; ----------------------------------------------------------------------------
;; _main
;;   Descripcion: punto de entrada. Inicializa el framework, dibuja el HUD de
;;                bienvenida, crea el manager y las entidades, y entra en el
;;                bucle principal game_frame.
;;   Entrada:     ninguna (arranque en 0x0200).
;;   Salida:      ninguna (bucle infinito).
;;   Modifica:    todo el estado del juego y del framework.
;;   Notas:       game_status vale 0x5A si todo arranco; otro valor es codigo de error.
;; ----------------------------------------------------------------------------
_main::
    call fwk_project_init            ; inicializa el proyecto (transparencia, bancos)
    call fwk_video_init             ; inicializa el subsistema de video
    call fwk_text_init              ; inicializa la fuente de texto Mode 0
    ld hl, #game_palette            ; HL = paleta de 16 colores (assets/palette.json)
    ld de, #GAME_PALETTE_SIZE       ; DE = numero de colores
    call cpct_setPalette_asm        ; instala la paleta en el Gate Array
    call fwk_input_init             ; inicializa el sistema de entrada
    ld hl, #game_bindings           ; HL = tabla de teclas/acciones
    call fwk_input_set_bindings     ; registra los bindings de teclado
    xor a                           ; A = 0
    call fwk_video_clear_visible    ; limpia la pantalla visible

    ;; Fondo: descomprime el mapa (ZX7B, copia hacia atras) y lo dibuja pegado al borde inferior.
    ld hl, #game_map_packed + GAME_MAP_PACKED_SIZE - 1   ; HL = ultimo byte del mapa comprimido
    ld de, #game_map + GAME_MAP_SIZE - 1                 ; DE = ultimo byte del buffer de destino
    call fwk_zx7b_unpack            ; descomprime el mapa
    ld ix, #game_map_desc           ; IX = descriptor del mapa
    ld iy, #game_view               ; IY = descriptor de la vista
    call fwk_tilemap_render_view    ; dibuja el fondo
    GAME_CHECK_OK                   ; carry = geometria invalida: nada se dibujo

    ld b, #GAME_TEXT_Y_WELCOME      ; B = scanline del titulo de bienvenida
    ld hl, #_game_str_welcome       ; HL = "WELCOME TO"
    call _game_text                 ; dibuja el texto
    ld b, #GAME_TEXT_Y_TITLE        ; B = scanline del titulo del juego
    ld hl, #game_title              ; HL = titulo (de common.inc)
    call _game_text                 ; dibuja el titulo
    ld b, #GAME_TEXT_Y_HELP         ; B = scanline de la ayuda
    ld hl, #_game_str_help          ; HL = "CURSOR KEYS MOVE"
    call _game_text                 ; dibuja la ayuda

    ld ix, #game_manager            ; IX = manager ECS
    call fwk_ecs_manager_init       ; inicializa el manager
    ld ix, #game_scene              ; IX = escena de render
    call fwk_ecs_render_reset       ; inicializa el renderer selectivo

    ld ix, #game_manager            ; IX = manager ECS
    ld hl, #_game_row_player        ; HL = fila de spawn del jugador
    call _game_spawn                ; crea la entidad jugador
    ld (game_player), iy            ; guarda la direccion del jugador
    ld ECS_E_INPUT_ACTION_MASK(iy), #GAME_INPUT_LEFT | GAME_INPUT_RIGHT | GAME_INPUT_UP | GAME_INPUT_DOWN
    ld ix, #game_manager            ; IX = manager ECS
    ld hl, #_game_row_drone0        ; HL = fila de spawn del dron 0
    call _game_spawn                ; crea el dron 0
    ld ix, #game_manager            ; IX = manager ECS
    ld hl, #_game_row_drone1        ; HL = fila de spawn del dron 1
    call _game_spawn                ; crea el dron 1
    ld ix, #game_manager            ; IX = manager ECS
    ld hl, #_game_row_drone2        ; HL = fila de spawn del dron 2
    call _game_spawn                ; crea el dron 2

    ld a, #0x5A
    ld (game_status), a             ; 0x5A = OK; any other value is an ABI error code.
    ;; If the game stops at startup, read game_status in the emulator debugger:
    ;; 0x5A means everything started; otherwise the value is the error code of
    ;; the failing fwk_* call. See docs/ecs-abi-2.0.md for the code list.

;; ----------------------------------------------------------------------------
;; game_frame
;;   Descripcion: bucle principal. Procesa entrada, ejecuta los sistemas ECS
;;                (behavior, input 4 dir, motion, clamp), prepara el render antes
;;                de VSYNC y restaura/dibuja despues.
;;   Entrada:     ninguna.
;;   Salida:      ninguna (bucle infinito).
;;   Modifica:    estado del juego y VRAM.
;; ----------------------------------------------------------------------------
game_frame:
    call fwk_input_update           ; actualiza el estado del teclado
    ld ix, #game_manager            ; IX = manager ECS
    call fwk_ecs_system_behavior    ; ejecuta los programas de behavior (drones)
    ld ix, #game_manager            ; IX = manager ECS
    call fwk_ecs_system_input       ; LEFT/RIGHT/UP/DOWN fijan las velocidades (4 dir)
    ld ix, #game_manager            ; IX = manager ECS
    call fwk_ecs_system_motion_u8   ; integra velocidad -> posicion (u8)
    ld ix, #game_manager            ; IX = manager ECS
    ld bc, #ECS_C_INPUT             ; BC = mascara de componentes (input)
    ld hl, #_game_clamp             ; HL = callback de clamp de posicion
    call fwk_ecs_system_run         ; ejecuta _game_clamp sobre entidades con input
    ;; Selective render: find what changed before VSYNC, touch video RAM after it.
    ld ix, #game_scene              ; IX = escena de render
    call fwk_ecs_render_prepare     ; prepara dirty (sin tocar VRAM) antes de VSYNC
    call fwk_system_wait_frame      ; espera al VSYNC
    ld ix, #game_scene              ; IX = escena de render
    call fwk_ecs_render_restore     ; restaura fondos sucios (tras VSYNC)
    ld ix, #game_scene              ; IX = escena de render
    call fwk_ecs_render_draw        ; dibuja entidades sucias (tras VSYNC)
    jp game_frame                   ; siguiente frame
