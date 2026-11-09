# Recorrido por el código de `nave`

La guía [Tu primer juego](first-game.md) construye este juego paso a paso. Este recorrido
hace lo contrario: parte del juego terminado, [`examples/nave`](../../examples/nave/), y lo
explica rutina por rutina para que puedas leerlo, cambiarlo y saber qué rompe cada cambio.

Necesitas haber ejecutado el juego una vez: construye el disco con `make` en `examples/nave` (lo deja en `build/nave/nave.dsk`)
y arráncalo con `RUN"NAVE` en un CPC o un emulador. No necesitas haber seguido la guía.

Los fragmentos de código de este texto son copias literales de
[`main.s`](../../examples/nave/main.s) y [`common.inc`](../../examples/nave/common.inc) (salvo el
esquema de cabecera de la sección 1 y los cambios de los ejercicios); una prueba
(`tests/test_nave_walkthrough.py`) comprueba que no se han separado del código.

## 0. Cinco palabras que se usan sin parar

El framework organiza el juego como un **ECS** (*entity-component-system*: entidades,
componentes y sistemas). Estas son las palabras:

- **Entidad**: un objeto del juego (la nave, un dron). Es un bloque de `ECS_ENTITY_SIZE`
  bytes con sus campos: posición, tamaño, sprite, velocidad...
- **Componente**: una capacidad que una entidad tiene o no: dibujarse, moverse, responder al
  teclado, animarse, colisionar, seguir un programa. Cada una es un bit de la **máscara de
  componentes** de la entidad (`ECS_C_RENDER`, `ECS_C_MOTION`...). Estas son las de la nave y
  las de los drones:

<!-- codigo: common.inc -->
```asm
GAME_PLAYER_COMPS = ECS_C_RENDER|ECS_C_MOTION|ECS_C_INPUT|ECS_C_ANIMATION|ECS_C_COLLISION
GAME_DRONE_COMPS  = ECS_C_RENDER|ECS_C_MOTION|ECS_C_BEHAVIOR|ECS_C_ANIMATION|ECS_C_COLLISION
```

- **Sistema**: una rutina que recorre las entidades y actúa sobre las que tienen cierto
  componente. `fwk_ecs_system_motion_u8`, por ejemplo, mueve las que tienen `ECS_C_MOTION`.
  Los sistemas propios, como `_game_steer`, son rutinas tuyas que el framework llama una vez
  por cada entidad.
- **Manager**: quien guarda las entidades, las crea y las recorre.
- **Tick**: una pasada del bucle del juego, el tiempo del juego. «Esperar 20» significa 20
  pasadas. No es lo mismo que un fotograma de pantalla (un VSYNC, 1/50 s): medido en el emulador,
  una pasada de este juego tarda dos fotogramas de pantalla (ver `PROJECT_STATUS.md`). El código
  la llama *frame* en sus comentarios; en este texto, para no confundirla con la de pantalla,
  una pasada se llama tick o pasada, y «fotograma» es siempre el de pantalla (la guía
[Tu primer juego](first-game.md) usa «fotograma» en los dos sentidos). Las imágenes de una
animación se llaman aquí *cuadros*.

Y dos cosas del proyecto: `example.json` es su manifiesto (qué módulos del framework se
enlazan y qué componentes usan las entidades) y lo que hay en `generated/` se regenera a
partir de él (y del título del proyecto) cuando cambian los componentes, los módulos o el título. Hay dos formas de trabajar con este
código: ejecutar el ejemplo tal cual (`make` en `examples/nave`; `make` no regenera `generated/`:
si cambias componentes o módulos, ejecuta desde la raíz del SDK `python3 tools/build/gen_ecs_profile.py
examples/nave/example.json --output examples/nave/generated/ecs_profile.inc`) o crear tu propio
proyecto con `glasnost new` (lo cuenta la
guía [Tu primer juego](first-game.md)) y usar `glasnost config` y `glasnost build`. Los dos
ejercicios del final no cambian componentes, así que no necesitan regenerar nada.

## 1. Cómo leer una cabecera

Cada rutina de `main.s` empieza con una cabecera. Es un contrato: lo que necesita, lo que
deja y lo que destroza.

```
;; ----------------------------------------------------------------------------
;; nombre
;;   Qué hace.
;;   In : registros y memoria que lee
;;   Out: registros, flags y memoria que deja
;;   Clobbers: registros y flags que modifica y no restaura (los de las rutinas a las que llama, incluidos)
;;   Notes: lo que un llamador debe saber
;; ----------------------------------------------------------------------------
```

`Clobbers` es la línea que más trabajo te ahorra: todo registro que aparezca ahí **no
conserva su valor** al volver. Si guardas algo en `BC` y llamas a una rutina con `BC` en
`Clobbers`, lo pierdes. Una rutina que no vuelve nunca (un bucle infinito) escribe
`all (never returns)`.

Cuando el contrato de una rutina del framework no está documentado, la lista es
conservadora: pone más registros de los que quizá cambia, nunca menos.

## 2. El mapa del fichero

`main.s` empieza incluyendo `common.inc` y `generated/project.inc`, y tiene dos zonas,
separadas por `.area`:

- `.area _DATA`: los datos: estado que cambia, textos, entidades, y tablas que solo se leen
  (la patrulla de los drones, las animaciones, las filas de aparición). Aquí no hay
  instrucciones del procesador.
- `.area _CODE`: las rutinas. Al final está `_main`, el punto de entrada.

Las constantes, las macros y las declaraciones `.globl` no están en `main.s` sino en
`common.inc`, que `main.s` incluye con `.include "common.inc"`. Es la convención del
proyecto: los `.s` tienen solo código y datos.

Un símbolo que termina en `::` es global: se ve desde otros ficheros y desde los tests (que lo
buscan por nombre en el `.noi`, el fichero de símbolos que genera la compilación); con un solo
`:` es local del fichero.

Hay cosas que `main.s` usa y define otro fichero. Ninguna se edita a mano:

- `game_title`, en `generated/project.inc`, que escribe `glasnost config` a partir del título
  del proyecto.
- `game_palette`, `GAME_PALETTE_SIZE`, `game_ship_pixels`, `game_drone_pixels`...: salen de
  `assets/`, el PNG de los sprites ya convertido.
- `ECS_ENTITY_SIZE`, `ECS_E_X`...: los genera `glasnost config` en
  `generated/ecs_profile.inc` según los componentes del manifiesto.

Dos medidas que verás en todo el código, porque el modo gráfico es Mode 0 de 160x200:

- **X va en bytes** (2 píxeles por byte): de 0 a 79.
- **Y va en líneas** (scanlines): de 0 a 199.

## 3. Los datos

### Estado público

<!-- codigo: main.s -->
```asm
game_status::  .db 0              ; 0x5A once the game is running, else the ABI error code
game_player::  .dw 0              ; address of the player entity
game_hits::    .db 0              ; times a drone touched the player
_game_hud_dirty: .db 1            ; the score must be redrawn
```

`game_status` vale `0x5A` cuando el juego ya está en marcha, o el código de error del
framework si algo falló (son los `FWK_ECS_ERR_*` de `framework/src/core/ecs_manager.inc`: por ejemplo
`0x03` es «el manager está lleno»). Los tests y el emulador esperan a ese valor antes de
hacer nada. `game_hits` es el marcador. Los símbolos con `::` son globales: se ven desde
fuera.

`_game_hud_dirty` es una bandera: vale 1 cuando el marcador cambió y hay que redibujarlo.
Arranca en 1 para que el primer `HITS: 00` se dibuje.

### Textos

<!-- codigo: main.s -->
```asm
_game_str_welcome: .asciz "WELCOME TO"
_game_str_help:    .asciz "CURSOR KEYS MOVE"
_game_str_hits:    .asciz "HITS: 00"      ; the two digits are patched in place
```

Son cadenas terminadas en cero. Las dos primeras y el título del proyecto (`game_title`) se
dibujan en estas posiciones (`GAME_TEXT_X` es la columna en bytes; las `GAME_TEXT_Y_*`, líneas); el
marcador va aparte, en `GAME_HUD_*`:

<!-- codigo: common.inc -->
```asm
GAME_TEXT_X = 4
GAME_TEXT_Y_WELCOME = 4
GAME_TEXT_Y_TITLE = 16
GAME_TEXT_Y_HELP = 28
```

 El marcador `HITS: 00` lleva los dos dígitos como
caracteres, y el código los cambia en el sitio (`_game_hud_update`). La fuente del
framework solo dibuja el espacio, `A-Z`, `0-9` y `! - / : > ? @`: nada de minúsculas ni acentos.

### Almacén de entidades y renderizador

Antes, las constantes de `common.inc` que dimensionan todo (`GAME_T_*` son los tipos de
entidad: un byte libre del juego que aquí nada lee):

<!-- codigo: common.inc -->
```asm
GAME_T_PLAYER = 1
GAME_T_DRONE  = 2

;; One manager holds the player and the three drones.
GAME_CAP = 4
```

<!-- codigo: main.s -->
```asm
_game_tpl:      .ds ECS_ENTITY_SIZE    ; template built from a spawn row, copied into the manager
_game_anim:     .dw 0                  ; descriptor of the row being spawned
game_storage::  .ds ECS_ENTITY_SIZE * GAME_CAP
FWK_ECS_MANAGER_DESCRIPTOR game_manager, game_storage, GAME_CAP

;; ---- Renderer: one pool of GAME_CAP background buffers of 32 bytes (4 x 8) ----
FWK_ECS_RENDER_POOL game_pool32, 32, GAME_CAP
_game_pools:    .dw game_pool32
_game_managers: .dw game_manager
_game_work:     .ds 8 * GAME_CAP
FWK_ECS_RENDER_SCENE game_scene, _game_managers, 1, _game_work, GAME_CAP, _game_pools, 1
```

`ECS_ENTITY_SIZE` es el tamaño en bytes de una entidad; lo calcula `glasnost config` a
partir de los componentes de `example.json` (por eso hay que ejecutarlo al añadir uno).
`game_storage` guarda `GAME_CAP` entidades (4: la nave y tres drones). El framework las
llena por orden de creación, así que la nave es la entidad 0.

`FWK_ECS_MANAGER_DESCRIPTOR` es una macro del framework que crea el descriptor del
*manager* a partir del almacén. El *manager* es quien crea, borra y recorre las entidades.

El renderizador necesita, por cada entidad que dibuja, un búfer donde guardar el fondo que
tapa su sprite (para devolverlo al moverse). `FWK_ECS_RENDER_POOL` reserva `GAME_CAP`
búferes de 32 bytes (4 x 8: el tamaño del sprite; cada uno con un byte de «en uso» delante) y `FWK_ECS_RENDER_SCENE` los junta en una escena. Sus argumentos son: la etiqueta
(`game_scene`), la tabla de *managers* a dibujar (`_game_managers`, con 1), una zona de
trabajo del renderizador (`_game_work`, 8 bytes por entidad), la capacidad (`GAME_CAP`) y la
tabla de pools (`_game_pools`, con 1).

### Teclado

<!-- codigo: main.s -->
```asm
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
```

Una tabla de pares (tecla, bit de acción), que termina con una acción 0 (el bucle de
`fwk_input_update` se para al ver una acción de valor 0). Cuando se pulsa una tecla,
`fwk_input_update` pone su bit en `fwk_input_held`. Los bits son estos, de `common.inc`:

<!-- codigo: common.inc -->
```asm
GAME_INPUT_LEFT  = 0x01
GAME_INPUT_RIGHT = 0x02
GAME_INPUT_UP    = 0x08
GAME_INPUT_DOWN  = 0x10
```

(El bit `0x04` es la acción de salto del framework, que este juego no usa.) El framework
entiende `LEFT`, `RIGHT` y el salto (su sistema de entrada convierte los dos primeros en
velocidad horizontal); `UP` y `DOWN` los trata el código del juego en `_game_steer`, que por
eso prueba los bits 3 y 4.

### Patrulla de los drones

<!-- codigo: main.s -->
```asm
_game_program_drone:
    FWK_BEHAVIOR_SET_VX 1
    FWK_BEHAVIOR_WAIT GAME_DRONE_FIRST_LEG, _game_program_drone_left
_game_program_drone_left:
    FWK_BEHAVIOR_SET_VX -1
    FWK_BEHAVIOR_WAIT GAME_DRONE_LEG, _game_program_drone_right
_game_program_drone_right:
    FWK_BEHAVIOR_SET_VX 1
    FWK_BEHAVIOR_WAIT GAME_DRONE_LEG, _game_program_drone_left
```

Un programa de comportamiento (lo ejecuta una vez por tick `fwk_ecs_system_behavior`, que verás en
la sección 5): la instrucción `SET_VX 1` pone la velocidad horizontal a 1 (1 byte por tick),
y `WAIT n, destino` mantiene esa velocidad y salta a `destino` al acabar. El temporizador se
carga y se descuenta en el mismo tick, así que la velocidad dura en la práctica `n - 1`
ticks. El primer tramo es `GAME_DRONE_FIRST_LEG` (20, unos 19 pasos) y los siguientes
`GAME_DRONE_LEG` (40, unos 39): el dron arranca a mitad de su recorrido y luego va de un
extremo al otro sin parar. Las tres etiquetas `_game_program_drone*` son los puntos de
salto, no rutinas.

### Animaciones y filas de aparición

<!-- codigo: main.s -->
```asm
_game_anim_ship:  .db 2, GAME_ANIM_TICKS
    .dw game_ship_pixels, game_ship_pixels2
_game_anim_drone: .db 2, GAME_ANIM_TICKS
    .dw game_drone_pixels, game_drone_pixels2

;; ---- Spawn rows (see GAME_ROW) ----
_game_row_player: GAME_ROW GAME_PLAYER_COMPS, GAME_T_PLAYER, 38, 170, 4, 8, game_ship_pixels, 0, _game_anim_ship
_game_row_drone0: GAME_ROW GAME_DRONE_COMPS, GAME_T_DRONE, 30, 70, 4, 8, game_drone_pixels, _game_program_drone, _game_anim_drone
_game_row_drone1: GAME_ROW GAME_DRONE_COMPS, GAME_T_DRONE, 40, 100, 4, 8, game_drone_pixels, _game_program_drone, _game_anim_drone
_game_row_drone2: GAME_ROW GAME_DRONE_COMPS, GAME_T_DRONE, 30, 130, 4, 8, game_drone_pixels, _game_program_drone, _game_anim_drone
```

Una animación es un descriptor: cuántos cuadros, cuántos ticks dura cada uno
(`GAME_ANIM_TICKS`, que vale 8), y los punteros a sus sprites (que salen de `assets/`, ya convertidos). Una **fila de aparición**
(`GAME_ROW`, definida en `common.inc`) es el dato completo de una entidad: componentes,
tipo, posición, tamaño, sprite, programa y animación. `_game_spawn` la convierte en una
entidad. Para cambiar qué aparece no se toca `_game_spawn`: se escribe otra fila (y se llama una vez
más a `_game_spawn`, como en el ejercicio 2).

<!-- codigo: common.inc -->
```asm
;; ----------------------------------------------------------------------------
;; GAME_ROW
;;   Spawn row: the 13 bytes of data _game_spawn turns into one entity.
;;   In : comps = component mask (ECS_C_*), type = GAME_T_*, x in bytes, y in scanlines,
;;        w in bytes, h in scanlines, sprite = pixel data, program = behavior program
;;        (0 = none), anim = animation descriptor (0 = none).
;;   Out: emits .dw comps / .db type, x, y, w, h / .dw sprite / .dw program, anim.
;;   Clobbers: none (it only emits data; no code runs).
;;   Notes: _game_spawn reads these fields in exactly this order. Use it in a data area.
;; ----------------------------------------------------------------------------
.macro GAME_ROW comps, type, x, y, w, h, sprite, program, anim
    .dw comps
    .db type, x, y, w, h
    .dw sprite
    .dw program, anim
.endm
```

## 4. Las rutinas, en orden de lectura

### `_game_fail` y `GAME_CHECK_OK`: parar si algo falla

<!-- codigo: main.s -->
```asm
;; ----------------------------------------------------------------------------
;; _game_fail
;;   Stops the game: stores the error code and waits frames forever.
;;   In : A=ABI error code (from GAME_CHECK_OK).
;;   Out: game_status=A. Never returns.
;;   Clobbers: all (never returns)
;;   Notes: Entered by jp only, so the stack of the failing caller is abandoned. It keeps
;;          calling fwk_system_wait_frame so the interrupts and the screen stay alive and
;;          the code stays readable in game_status.
;; ----------------------------------------------------------------------------
_game_fail:
    ld (game_status), a
_game_fail_loop:
    call fwk_system_wait_frame
    jr _game_fail_loop
```

<!-- codigo: common.inc -->
```asm
;; Comprobacion defensiva de carry tras una llamada al framework.
;; Desactivada por defecto (cero ciclos). Para activarla en desarrollo:
;;   1. Pon GAME_DEBUG_CHECKS = 1
;;   2. Anade GAME_CHECK_OK justo despues de cada llamada a fwk_* que quieras comprobar.
GAME_DEBUG_CHECKS = 0
.macro GAME_CHECK_OK
.if GAME_DEBUG_CHECKS
    jp c, _game_fail
.endif
.endm
```

Las rutinas de ECS y del renderizador devuelven un resultado en el flag de acarreo: acarreo
limpio es éxito; acarreo puesto es error y `A` trae el código. El juego **no** lo comprueba:
`GAME_DEBUG_CHECKS` vale 0 y `GAME_CHECK_OK` no genera ni un byte, así que no cuesta ciclos
ni memoria. Para depurar, pon `GAME_DEBUG_CHECKS = 1` en `common.inc` y escribe
`GAME_CHECK_OK` justo después de la llamada que quieras vigilar (antes de tocar nada que
cambie el acarreo). Con la comprobación activa, un acarreo puesto salta (`jp c`) a
`_game_fail`, que guarda el código en `game_status` y se queda esperando fotogramas para
siempre. No hay manejo de errores más fino a propósito: en un juego de ejemplo, un error es
un fallo de programación y lo útil es que se vea el código. Como es un salto y no una
llamada, no toca ningún registro en el camino de éxito.

### `_game_spawn`: de una fila a una entidad

<!-- codigo: main.s -->
```asm
;; ----------------------------------------------------------------------------
;; _game_spawn
;;   Builds an entity from a spawn row (GAME_ROW), creates it in the manager and,
;;   if the row names an animation, starts it.
;;   In : IX=manager, HL=spawn row (13 bytes, see GAME_ROW in common.inc).
;;   Out: success: carry clear, IY=the new entity. Failure: carry set, A=ABI error code.
;;        _game_tpl and _game_anim are overwritten.
;;   Clobbers: AF, BC, DE, HL, IY
;;   Notes: IX is preserved. The template is zeroed first, so every field the row does not
;;          set (cadence, velocity, flags) starts at 0. The row is read in order: components,
;;          type, x, y, width, height, sprite, behavior program, animation descriptor.
;; ----------------------------------------------------------------------------
_game_spawn:
    ;; Zero the template: ldir copies the first byte (0) over the rest.
    push hl
    ld hl, #_game_tpl
    ld de, #_game_tpl + 1
    ld (hl), #0
    ld bc, #ECS_ENTITY_SIZE - 1
    ldir
    pop hl
    ld iy, #_game_tpl
    ;; Copy the row into the template, field by field, in the order GAME_ROW writes it.
    ld a, (hl)
    inc hl
    ld ECS_E_COMPONENTS(iy), a      ; components: which systems act on it (low byte)
    ld a, (hl)
    inc hl
    ld ECS_E_COMPONENTS+1(iy), a    ; (high byte)
    ld ECS_E_STATUS(iy), #ECS_STATUS_ACTIVE
    ld a, (hl)
    inc hl
    ld ECS_E_TYPE(iy), a            ; type: GAME_T_PLAYER or GAME_T_DRONE
    ld a, (hl)
    inc hl
    ld ECS_E_X(iy), a               ; position: x in bytes, y in scanlines
    ld a, (hl)
    inc hl
    ld ECS_E_Y(iy), a
    ld a, (hl)
    inc hl
    ld ECS_E_WIDTH(iy), a           ; size: width in bytes, height in scanlines
    ld a, (hl)
    inc hl
    ld ECS_E_HEIGHT(iy), a
    ld a, (hl)
    inc hl
    ld ECS_E_RENDER_SPRITE(iy), a   ; sprite pixels (low byte, then high)
    ld a, (hl)
    inc hl
    ld ECS_E_RENDER_SPRITE+1(iy), a
    ld a, (hl)
    inc hl
    ld ECS_E_BEHAVIOR_PROGRAM(iy), a ; patrol program, 0 = none (low byte, then high)
    ld a, (hl)
    inc hl
    ld ECS_E_BEHAVIOR_PROGRAM+1(iy), a
    ld e, (hl)
    inc hl
    ld d, (hl)
    ld (_game_anim), de             ; animation descriptor of this row
    ld ECS_E_RENDER_FLAGS(iy), #ECS_RENDER_VISIBLE | ECS_RENDER_DIRTY   ; draw it on the first frame
    ;; Hand the finished template to the manager, which copies it into a free slot.
    ld hl, #_game_tpl
    call fwk_ecs_entity_create
    ret c                           ; manager full or bad template: carry and error in A
    ld hl, (_game_anim)
    ld a, h
    or l
    ret z                           ; no animation
    jp fwk_ecs_anim_set             ; IY = the new entity
```

La estrategia es construir la entidad en una **plantilla** (`_game_tpl`) y pedirle al
*manager* que la copie a un hueco libre:

1. Poner la plantilla a cero. `ldir` copia el primer byte (0) sobre el resto.
2. Leer la fila campo a campo con `HL` (cada `inc hl` avanza un byte) y escribirlo en el
   campo de la plantilla con `IY`. Los nombres `ECS_E_*` son desplazamientos dentro de la
   entidad (los genera `glasnost config`).
3. Marcar la entidad como activa (`ECS_STATUS_ACTIVE`: `fwk_ecs_entity_create` rechaza
   plantillas que no lo estén) y como visible y sucia para que se dibuje en la primera pasada.
4. `fwk_ecs_entity_create` la copia al almacén y devuelve en `IY` la entidad real.
5. Si la fila trae descriptor de animación, `fwk_ecs_anim_set` lo asigna. Es un `jp`, así
   que su resultado es el de `_game_spawn`.

Fíjate en `Out`: en éxito, `IY` es la entidad nueva. Por eso `_main` (más
abajo) hace `ld (game_player), iy` justo después de crear la nave.

### `_game_text`: escribir en pantalla

<!-- codigo: main.s -->
```asm
;; ----------------------------------------------------------------------------
;; _game_text
;;   Draws a string at the left margin (GAME_TEXT_X) on a given scanline.
;;   In : B=scanline, HL=NUL-terminated string.
;;   Out: the text is drawn on the visible screen. IY is left pointing at the string.
;;   Clobbers: AF, BC, DE, HL, IX, IY
;;   Notes: Tail-jumps to fwk_text_draw, which returns to the caller. IX is listed because
;;          fwk_text_draw documents it as modified (its current body restores it). Bytes the
;;          font does not have (lowercase, for example) advance one cell without drawing.
;; ----------------------------------------------------------------------------
_game_text:
    push hl                         ; keep the string while HL carries the scanline
    ld l, b
    ld h, #0
    ld c, #GAME_TEXT_X
    call fwk_video_get_ptr          ; HL = screen address of (GAME_TEXT_X, scanline)
    pop iy                          ; IY = string, HL = where to draw it
    jp fwk_text_draw
```

`fwk_text_draw` quiere un puntero a la pantalla en `HL` y la cadena en `IY`. Esta rutina
convierte «scanline + margen izquierdo» en esa dirección con `fwk_video_get_ptr` y salta a
`fwk_text_draw`. Guarda la cadena en la pila porque `HL` hace de scanline un momento.

### `_game_drone_cb`: contar un golpe

En `fwk_ecs_collide` hay un **sujeto** (la entidad que se comprueba: la nave) y unos
**objetivos** (con los que se compara: los drones). El **canal** es un bit del campo de contacto
del sujeto (`ECS_E_COLLISION_CONTACT`) donde el framework guarda si ya tocaba algo.
`_game_drone_cb` es la función que se llama cuando la nave toca a un dron:

<!-- codigo: main.s -->
```asm
;; ----------------------------------------------------------------------------
;; _game_drone_cb
;;   Collision callback: counts a hit when the player goes from touching no drone to
;;   touching one, not on every frame of the contact. The state is remembered per subject
;;   and channel: a drone touched while the player already touched another one in an earlier
;;   pass arrives as STAY and does not count.
;;   In : IX=manager, IY=drone (0 on EXIT), HL=player, A=ECS_COLLISION_ENTER, STAY or EXIT.
;;   Out: carry clear and A=0 (keep going). On ENTER: game_hits +1 and _game_hud_dirty=1.
;;   Clobbers: AF
;;   Notes: Touches only A and the flags (the framework does not require a collide callback to
;;          keep IX or IY). game_hits stops at 99 because the score has two digits.
;; ----------------------------------------------------------------------------
_game_drone_cb:
    cp #ECS_COLLISION_ENTER
    jr nz, _game_drone_cb_done      ; STAY and EXIT do not count
    ld a, (game_hits)
    cp #99
    jr z, _game_drone_cb_done       ; the score has two digits
    inc a
    ld (game_hits), a
    ld a, #1
    ld (_game_hud_dirty), a         ; ask _game_hud_update to redraw
_game_drone_cb_done:
    xor a                           ; carry clear, A=0: keep going
    ret
```

`A` dice el estado
del contacto, que el framework recuerda **por nave y por canal, no por pareja**: `ENTER` (la
nave pasa de no tocar a ningún dron a tocar alguno), `STAY` (sigue tocando) o `EXIT` (deja de
tocar a todos; entonces `IY` vale 0, porque ya no hay dron al que apuntar). Solo `ENTER`
cuenta: un contacto largo vale un golpe, no uno por pasada. Consecuencia: el estado se
mira una vez al empezar la pasada. Si la nave ya tocaba un dron en una pasada anterior y
llega un segundo, ese segundo llega como `STAY` y no suma; pero si dos drones empiezan a
tocarla en la misma pasada, los dos llegan como `ENTER` y suman dos golpes. Devuelve `A=0` con
acarreo limpio para que el recorrido continúe, y solo usa `A`.

### `_game_hud_update`: dibujar el marcador

<!-- codigo: main.s -->
```asm
;; ----------------------------------------------------------------------------
;; _game_hud_update
;;   Redraws the score when it changed: patches the two digits into the string,
;;   clears its box and draws it.
;;   In : reads _game_hud_dirty and game_hits.
;;   Out: _game_hud_dirty cleared; the digits of _game_str_hits patched and the score drawn.
;;   Clobbers: AF, BC, DE, HL, IX, IY
;;   Notes: IX is listed because fwk_text_draw documents it as modified. When nothing changed it
;;          returns after touching only AF. The tens digit comes from
;;          repeated subtraction of 10 (game_hits <= 99). Call it after the render: the text
;;          goes over whatever the renderer left.
;; ----------------------------------------------------------------------------
_game_hud_update:
    ld a, (_game_hud_dirty)
    or a
    ret z                           ; nothing changed
    xor a
    ld (_game_hud_dirty), a
    ld a, (game_hits)
    ld b, #'0'                      ; B = tens digit, counted up by subtracting 10
_game_hud_tens:
    cp #10
    jr c, _game_hud_units
    sub #10
    inc b
    jr _game_hud_tens
_game_hud_units:
    add a, #'0'                     ; A = units digit
    ld (_game_str_hits + 7), a      ; "HITS: 00": units at offset 7, tens at offset 6
    ld a, b
    ld (_game_str_hits + 6), a
    ld hl, #GAME_HUD_Y
    ld c, #GAME_HUD_X
    call fwk_video_get_ptr
    ex de, hl
    ld b, #GAME_HUD_H
    ld c, #GAME_HUD_W
    xor a
    call cpct_drawSolidBox_asm       ; black box over the old digits
    ld hl, #GAME_HUD_Y
    ld c, #GAME_HUD_X
    call fwk_video_get_ptr
    ld iy, #_game_str_hits
    jp fwk_text_draw
```

Su caja viene de estas constantes (`common.inc`): empieza en la columna `GAME_HUD_X` y la
línea `GAME_HUD_Y`, y mide `GAME_HUD_W` bytes (los 8 caracteres de `HITS: 00`, a 2 bytes cada
uno) por `GAME_HUD_H` líneas (la altura del texto).

<!-- codigo: common.inc -->
```asm
GAME_HUD_X = 60
GAME_HUD_Y = 4
GAME_HUD_W = 16
GAME_HUD_H = 9
```

Si no hay cambios, sale enseguida (tres instrucciones). Si los hay, calcula los dos dígitos
(restando 10 hasta que quepa), los escribe dentro de la cadena `HITS: 00`, borra el
rectángulo del marcador con `cpct_drawSolidBox_asm` y dibuja la cadena encima. Se llama
**después** del renderizador: el texto va sobre lo que el renderizador dejó.

### `_game_steer` y `_game_clamp`: dos sistemas propios

<!-- codigo: main.s -->
```asm
;; ----------------------------------------------------------------------------
;; _game_steer
;;   Steering system, run before motion: UP and DOWN set the vertical velocity of
;;   every entity with the INPUT component.
;;   In : IX=manager, IY=entity (fwk_ecs_system_run callback); reads fwk_input_held.
;;   Out: carry clear and A=0. ECS_E_MOTION_VELOCITY_Y(iy) = -GAME_SPEED_Y (UP), +GAME_SPEED_Y (DOWN) or 0.
;;   Clobbers: AF, C
;;   Notes: IX and IY are saved and restored: the traversal requires it. If both keys are held,
;;          DOWN wins.
;; ----------------------------------------------------------------------------
_game_steer:
    push ix
    push iy
    ld a, (fwk_input_held)
    ld c, a
    xor a
    bit 3, c                         ; GAME_INPUT_UP
    jr z, _game_steer_down
    ld a, #-GAME_SPEED_Y
_game_steer_down:
    bit 4, c                         ; GAME_INPUT_DOWN
    jr z, _game_steer_set
    ld a, #GAME_SPEED_Y
_game_steer_set:
    ld ECS_E_MOTION_VELOCITY_Y(iy), a
    pop iy
    pop ix
    xor a
    ret
```

<!-- codigo: main.s -->
```asm
;; ----------------------------------------------------------------------------
;; _game_clamp
;;   Keeps the entity inside the play area, run after motion: X within 0..GAME_X_MAX,
;;   Y within GAME_Y_MIN..GAME_Y_MAX.
;;   In : IX=manager, IY=entity (fwk_ecs_system_run callback).
;;   Out: carry clear and A=0. ECS_E_X(iy) and ECS_E_Y(iy) are inside the limits.
;;   Clobbers: AF
;;   Notes: Positions are unsigned bytes, but fwk_ecs_system_motion_u8 already saturates at 0, so
;;          with it the X >= 200 test never fires; it only guards a position that wrapped to
;;          254. IX and IY are saved and restored.
;; ----------------------------------------------------------------------------
_game_clamp:
    push ix
    push iy
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
```

El framework recorre las entidades con `fwk_ecs_system_run`: le das el *manager* (`IX`), una
máscara de componentes (`BC`) y una rutina (`HL`), y la llama una vez por cada entidad activa que
tenga todos esos componentes (y a la que su cadencia no salte; en `nave` todas son 0), con `IX` el
*manager* e `IY` la entidad. La rutina debe devolver `IX` e `IY` como los recibió (por eso
las dos hacen `push` y `pop`) y acarreo limpio para seguir.

`_game_steer` va **antes** del movimiento y traduce `UP` y `DOWN` en velocidad vertical (la
velocidad es un byte con signo: `-GAME_SPEED_Y` se guarda en complemento a dos).
`_game_clamp` va **después** y corrige la posición a los límites del *juego*, que salen de
`common.inc`:

<!-- codigo: common.inc -->
```asm
GAME_X_MAX = 76
GAME_Y_MIN = 44
GAME_Y_MAX = 192
GAME_SPEED_Y = 2
```

X llega hasta 76 (el sprite mide 4 bytes y la pantalla tiene 80) e Y va de 44 a 192 (200 líneas
menos las 8 del sprite): las
líneas de arriba las ocupan los textos (`GAME_TEXT_*`, de la línea 4 a la 28 más su altura). El sistema de movimiento ya satura las coordenadas a 0 y a los límites del vídeo
(79 y 199), así que ir a la izquierda se queda en 0 y no da la vuelta. Por eso el primer test
de X (todo X mayor o igual que 200 se pone a 0) solo protege de una posición que hubiera dado
la vuelta con otro sistema de movimiento (0 menos 2 en un byte sin signo es 254); con este
esa rama nunca se ejecuta.

### `_main`: arrancar y repetir

<!-- codigo: main.s -->
```asm
;; ----------------------------------------------------------------------------
;; _main
;;   Program entry: starts the framework, draws the texts, creates the manager, the
;;   renderer and the four entities, then runs the frame loop forever.
;;   In : none.
;;   Out: never returns. game_status=0x5A once the game runs, or an ABI error code.
;;   Clobbers: all (never returns)
;;   Notes: Each frame runs, in order: input, behavior, input system, steering, motion,
;;          animation, clamp, collisions, then the selective render around the VSYNC wait,
;;          then the score.
;; ----------------------------------------------------------------------------
_main::
    ;; System up (firmware off, interrupts on), Mode 0, text, palette, keyboard, clear screen.
    call fwk_project_init
    call fwk_video_init
    call fwk_text_init
    ld hl, #game_palette
    ld de, #GAME_PALETTE_SIZE
    call cpct_setPalette_asm
    call fwk_input_init
    ld hl, #game_bindings
    call fwk_input_set_bindings
    xor a
    call fwk_video_clear_visible

    ;; The three static texts: welcome, the project title, the help line.
    ld b, #GAME_TEXT_Y_WELCOME
    ld hl, #_game_str_welcome
    call _game_text
    ld b, #GAME_TEXT_Y_TITLE
    ld hl, #game_title
    call _game_text
    ld b, #GAME_TEXT_Y_HELP
    ld hl, #_game_str_help
    call _game_text

    ;; Empty manager and renderer, then spawn the player and the three drones.
    ld ix, #game_manager
    call fwk_ecs_manager_init
    ld ix, #game_scene
    call fwk_ecs_render_reset

    ld ix, #game_manager
    ld hl, #_game_row_player
    call _game_spawn
    ld (game_player), iy            ; the collision pass needs the player's address
    ld ECS_E_INPUT_ACTION_MASK(iy), #GAME_INPUT_LEFT | GAME_INPUT_RIGHT   ; LEFT/RIGHT steer it
    ld ix, #game_manager
    ld hl, #_game_row_drone0
    call _game_spawn
    ld ix, #game_manager
    ld hl, #_game_row_drone1
    call _game_spawn
    ld ix, #game_manager
    ld hl, #_game_row_drone2
    call _game_spawn

    ld a, #0x5A
    ld (game_status), a             ; running: tests and the emulator wait for this
```

Dos detalles de `_main` antes de leerlo. Tras crear la nave, `ld (game_player), iy` guarda su
dirección, porque la pasada de colisiones necesita saber quién es el sujeto. Y
`ld ECS_E_INPUT_ACTION_MASK(iy), #GAME_INPUT_LEFT | GAME_INPUT_RIGHT` es la máscara con la que
la entidad elige qué acciones del teclado aplica `fwk_ecs_system_input`: sin ella la nave tendría
el componente de entrada pero no se movería de lado. `UP` y `DOWN` no van en la máscara porque
ese sistema solo entiende izquierda, derecha y salto; a ellas las trata `_game_steer`. La máscara
no es un campo de `GAME_ROW`: la plantilla de `_game_spawn` se pone a cero, así que se escribe a
mano tras crear la entidad.

`_main` hace todo el arranque una vez: sistema, vídeo, texto, paleta, teclado, pantalla
negra, los tres textos, el *manager* y el renderizador vacíos, y las cuatro entidades.
Las llamadas del framework que pueden fallar (las de ECS y las del renderizador) no se
comprueban por defecto; si quieres vigilarlas, pon `GAME_CHECK_OK` tras ellas (sección 4).
Las de arranque (`fwk_video_init`, `fwk_text_init`...) y `fwk_input_update` no
devuelven error. Cuando termina, escribe `0x5A`
en `game_status`. Lo que sigue (el bucle) está en la sección 5.

## 5. Una pasada del bucle

<!-- codigo: main.s -->
```asm
    ;; ---- One game frame ----
game_frame:
    call fwk_input_update           ; read the keys once per frame
    ld ix, #game_manager
    call fwk_ecs_system_behavior
    ld ix, #game_manager
    call fwk_ecs_system_input        ; LEFT and RIGHT set the horizontal velocity
    ld ix, #game_manager
    ld bc, #ECS_C_INPUT
    ld hl, #_game_steer              ; UP and DOWN set the vertical velocity
    call fwk_ecs_system_run
    ld ix, #game_manager
    call fwk_ecs_system_motion_u8    ; velocity moves every entity
    ld ix, #game_manager
    call fwk_ecs_system_animation    ; every animation counts down and changes frame
    ld ix, #game_manager
    ld bc, #ECS_C_INPUT
    ld hl, #_game_clamp
    call fwk_ecs_system_run
    ld ix, #game_manager             ; the player against every drone (collision + behavior)
    ld iy, (game_player)
    ld bc, #ECS_C_COLLISION | ECS_C_BEHAVIOR
    ld hl, #_game_drone_cb
    ld e, #GAME_CH_DRONE
    call fwk_ecs_collide
    ;; Selective render: find what changed before VSYNC, touch video RAM after it.
    ld ix, #game_scene
    call fwk_ecs_render_prepare
    call fwk_system_wait_frame
    ld ix, #game_scene
    call fwk_ecs_render_restore
    ld ix, #game_scene
    call fwk_ecs_render_draw
    call _game_hud_update            ; after the render: text goes over what it left
    jp game_frame
```

El orden importa. Cada línea es un paso, y esto es lo que hace cada uno:

| Paso | Qué hace | Por qué en este punto |
|---|---|---|
| `fwk_input_update` | lee las teclas una vez | todo lo que sigue usa las mismas teclas |
| `fwk_ecs_system_behavior` | ejecuta el programa de patrulla de cada dron | pone su velocidad horizontal |
| `fwk_ecs_system_input` | `LEFT`/`RIGHT` pasan a velocidad horizontal de la nave | antes del movimiento |
| `_game_steer` | `UP`/`DOWN` pasan a velocidad vertical | antes del movimiento |
| `fwk_ecs_system_motion_u8` | suma la velocidad a la posición de cada entidad | aquí se mueve todo |
| `fwk_ecs_system_animation` | descuenta el temporizador de cada animación y cambia de cuadro al acabar (cada `GAME_ANIM_TICKS` pasadas) | — |
| `_game_clamp` | mantiene la nave dentro del área | después de moverla |
| `fwk_ecs_collide` | compara la nave con los drones, llama a `_game_drone_cb` | con las posiciones ya finales |
| `fwk_ecs_render_prepare` | calcula qué hay que borrar y dibujar | **antes** de VSYNC: no toca la pantalla |
| `fwk_system_wait_frame` | espera al VSYNC | — |
| `fwk_ecs_render_restore` / `_draw` | devuelve el fondo y dibuja los sprites | **después** de VSYNC: el haz acaba de volver arriba |
| `_game_hud_update` | redibuja el marcador si cambió | encima de lo dibujado |

La llamada a `fwk_ecs_collide` lleva tres datos: `IY` es el *sujeto* (la nave); `BC = ECS_C_COLLISION
| ECS_C_BEHAVIOR` elige los *objetivos*: los que tienen colisión **y** comportamiento, o sea los
drones; y `E = GAME_CH_DRONE` es el canal (un solo bit del campo de contacto) donde el framework
guarda si el sujeto ya tocaba (para distinguir
`ENTER` de `STAY` y `EXIT`). Con `E = 0` no recordaría nada y todo contacto sería `ENTER`.

Una nota honesta sobre el renderizador: borra y vuelve a dibujar justo después del VSYNC y
el haz del monitor puede alcanzar esas líneas antes de que acabe, así que un sprite puede
parpadear. Es un efecto conocido, aún sin medir, y [`PROJECT_STATUS.md`](../../PROJECT_STATUS.md)
deja abierto si lo corrige el renderizador o la plantilla.

## 6. Dos ejercicios

Los dos están compilados y ejecutados en un emulador tal como se describen aquí
(`tests/nave_walkthrough_smoke.py`, que construye un proyecto de glasnost con los ficheros de
`examples/nave` y les aplica estos cambios; los resultados medidos están en `PROJECT_STATUS.md`).
Con `GAME_SPEED_Y = 4` la nave recorre casi el doble de líneas que con 2 en los mismos 60
fotogramas de pantalla (cociente de 1,93 a 2,00); con el cuarto dron el juego llega a `0x5A`, la quinta entidad es un dron que se
mueve y, al colocar la nave encima (el smoke escribe su posición en la RAM), suma al menos un
golpe.

### Ejercicio 1: una nave más rápida

En `common.inc` (el de `examples/nave` si lo ejecutas con `make`, o el de tu proyecto si lo
construyes con `glasnost build`), cambia

```
GAME_SPEED_Y = 2
```

por `GAME_SPEED_Y = 4`, recompila, mantén `UP` hasta que la nave llegue arriba y suéltala;
después mantén `DOWN`: baja el doble de rápido (la nave nace cerca del suelo, así que si no
subes antes casi no se nota). Es
una constante que usa `_game_steer`; nada más cambia.

### Ejercicio 2: un cuarto dron

Tres cambios:

1. En `common.inc`: `GAME_CAP = 5` (hueco para otra entidad; el almacén y el renderizador
   se dimensionan con ella).
2. En `main.s`, junto a las otras filas, una fila nueva:

```
_game_row_drone3: GAME_ROW GAME_DRONE_COMPS, GAME_T_DRONE, 40, 160, 4, 8, game_drone_pixels, _game_program_drone, _game_anim_drone
```

3. En `_main`, tras crear el tercer dron, otra creación igual:

```
    ld ix, #game_manager
    ld hl, #_game_row_drone3
    call _game_spawn
```

Los comentarios de `main.s` y `common.inc` que hablan de «cuatro entidades» o «tres drones»
quedan desfasados; actualízalos si quieres. Compila y ejecuta: hay un dron más, a la altura de la línea 160, y cada vez que empieza a
tocar la nave suma un golpe. Si olvidas el paso 1, la quinta llamada a `_game_spawn` falla con
el acarreo puesto y el juego se para con `0x03` en `game_status` (`FWK_ECS_ERR_FULL`: el
*manager* está lleno); así lo midió el emulador.

## 7. Dónde seguir

- [Tu primer juego](first-game.md): cómo se construyó esto, paso a paso, desde
  `glasnost new`.
- [`docs/reference/ecs-abi-2.0.md`](../reference/ecs-abi-2.0.md): el contrato del ECS (`fwk_ecs_*`), y
  [`docs/reference/architecture-and-api.md`](../reference/architecture-and-api.md) para vídeo, texto, entrada y el resto.
- `examples/platformer`: un juego mayor con la misma estructura (dos niveles, enemigos,
  puerta, vidas).
