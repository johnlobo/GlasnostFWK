# GlasnostFWK

[![CI](https://github.com/johnlobo/GlasnostFWK/actions/workflows/ci.yml/badge.svg)](https://github.com/johnlobo/GlasnostFWK/actions/workflows/ci.yml)

Framework modular en ensamblador Z80 para Amstrad CPC, extraído y consolidado
de `model01`, `boop`, `DeckTower` y `PocketFever`. La primera versión estable
se centra en un núcleo pequeño, entrada con flancos, vídeo Mode 0 declarativo,
colecciones sin estructura universal, perfiles separados de plataforma y
física 8.8, consulta, colisión y render de tilemaps opcionales, sprites con
clipping, restauración, máscaras opcionales y pases ordenados, texto, audio
AKG opcional y copia bancaria de 128 KB.

El framework no contiene assets ni reglas de los juegos originales. Cada
ejemplo declara sus módulos y fuentes de juego en `examples/*/example.json`;
el constructor copia únicamente esos fuentes al árbol temporal `.build/`, de
modo que excluir una funcionalidad la excluye también del enlazado.

## Dependencia fijada

- CPCTelera Next: revisión `11e61fe30175ad7b328de9bcd859c46fd61b26a5`.
- SDCC Z80: 4.5.0, build 15242, distribuido por esa revisión.
- Ruta local predeterminada: `/config/workspace/cpctelera_next/cpctelera`.

Puede elegirse otra instalación compatible con `CPCT_NEXT_PATH` o
`tools/build_examples.py --cpct-path`.

### CLI `glasnost`

```sh
bin/glasnost doctor               # herramientas, dependencias y toolchain
bin/glasnost install-toolchain    # descarga y compila el commit de toolchain.lock.json
bin/glasnost build platformer     # compila ejemplos con ese toolchain
bin/glasnost test                 # make test
bin/glasnost run platformer       # abre el ejemplo en el emulador
bin/glasnost new minave           # proyecto nuevo en projects/minave (asistente si no das nombre)
                                  # guía paso a paso: docs/first-game.md (y el recorrido del código: docs/nave-walkthrough.md)
bin/glasnost projects              # proyectos y si están al día; glasnost update los actualiza
bin/glasnost install-cli          # enlace ~/.local/bin/glasnost (sin sudo)
bin/glasnost toolchains           # toolchains instalados; clean-toolchains los limpia
```

Mensajes en castellano; `--lang en` o `GLASNOST_LANG=en` para inglés. El
toolchain vive en `.toolchain/` (fuera de Git, sin `sudo`). Detalle en
`docs/glasnost-cli.md`.

## Construcción y pruebas

```sh
make generate   # vídeo y manifiesto de recursos, deterministas
make check      # pruebas host + platformer; bucle rápido durante desarrollo
make check CHECK_EXAMPLES="spritemask ecsrender"  # solo ejemplos afectados
make examples   # veintitrés ejemplos, incluidas tres escenas jugables
make test       # pruebas host + construcción y DSK completos; cierre/commit
make report     # actualiza docs/build-sizes.md desde los mapas SDCC
make manual     # regenera docs/manual.pdf desde docs/manual.html
make release VERSION=0.1.0  # ZIP jugable y SHA256SUMS en dist/
python3 tests/emulator_smoke.py  # smoke real en AmSpiriT-Lite, si está instalado
```

Los BIN y CDT se generan en `.build/<ejemplo>/`; los veintitrés BIN de prueba se
reúnen en `.build/tests/GlasnostFWK-tests.dsk`, junto con los payloads auxiliares
que necesita `diskload`. En esa construcción global los DSK individuales usados
internamente por CPCTelera se eliminan al terminar; si compilas un ejemplo por
separado, `make` deja sus BIN, CDT y DSK también en la carpeta del ejemplo.
`make check` ejecuta toda la suite host, que es rápida, pero solo compila los
ejemplos indicados en `CHECK_EXAMPLES` y no reconstruye el DSK común. Es el
objetivo normal mientras se desarrolla. `make test` se reserva para el cierre
de una tarea o el commit y se ejecuta una sola vez. Ninguno lanza el emulador;
el smoke opcional sí y usa el DSK común para
comprobar estado de RAM, no solo que el proceso arranque.
Las versiones publicadas ofrecen los `.bin`, los CDT declarados y el DSK común
en un ZIP con checksum; el estado y la siguiente acción se mantienen en
[`PROJECT_STATUS.md`](PROJECT_STATUS.md).

### Un ejemplo por separado

Cada consumidor se construye y ejecuta solo, como un proyecto CPCtelera:

```sh
cd examples/minimal
make        # compila este ejemplo y deja BIN, CDT y DSK en la carpeta
make run    # compila y abre el CDT o el DSK en el emulador
make clean  # borra .build/minimal/ y las copias locales
```

`make` mantiene el proyecto generado en `.build/<ejemplo>/`, pero copia junto a
las fuentes `examples/<ejemplo>/<ejemplo>.bin`, `.cdt` y `.dsk` (los que existan)
para que puedas cogerlos directamente. Esas copias están ignoradas por git;
`make clean` las elimina junto con el árbol de compilación. El framework nunca
se copia al repositorio.

`make run` usa el emulador indicado en `GLASNOST_EMULATOR` o, si no se indica,
busca AmSpiriT-Lite junto al repositorio y, si no lo encuentra, MacAPE
(`/Applications/MacAPE.app` o `~/Proyectos/macape`). Para forzarlo use
`GLASNOST_EMULATOR=/ruta/a/cpct_macape`. Sin emulador imprime la ruta de la
imagen para abrirla a mano.

### Configuración CPCtelera y gráficos por ejemplo

Un ejemplo puede llevar su propia configuración de proyecto en
`cfg/build_config.mk`; si existe, el constructor la usa como base y solo
reescribe los valores que gobierna `example.json` (`CPCT_PATH`, `PROJNAME`,
`TARGET`, `Z80CODELOC` y `-I$(SRCDIR)`). Es el sitio para añadir flags,
herramientas o rutas de inclusión.

La carpeta `assets/` del ejemplo se copia a `src/assets` del proyecto generado:
sus `.s` se ensamblan sin declararlos en el manifiesto, los `.inc` se incluyen
como `assets/<archivo>.inc` y los PNG u originales quedan disponibles para las
herramientas de CPCTelera. Si el ejemplo incluye `assets/assets.json`, el
constructor convierte PNG y mapas Tiled solo cuando cambian y aplica compresión
`zx7b` si se declara. `examples/platformer` es la referencia: tiles y sprites
PNG, `level.tmx`, mapa comprimido y descompresión al iniciar. `make assets`
ejecuta solo la conversión incremental; `assets/README.md` detalla el flujo y
las herramientas.

El manual de uso completo está disponible en
[`docs/manual.html`](docs/manual.html) y [`docs/manual.pdf`](docs/manual.pdf).
Cada funcionalidad nueva debe documentarse allí y regenerar el PDF con
`make manual`; la suite comprueba cobertura y sincronización. La dependencia
de render se instala de forma aislada con
`python3 -m venv .venv-docs` y
`.venv-docs/bin/python -m pip install -r docs/requirements-manual.txt`.

La migración de la rama `ecs-v2` se gobierna por
[`docs/ecs-2.0-master-plan.md`](docs/ecs-2.0-master-plan.md). La propuesta de
ABI aprobada en G1 está en [`docs/ecs-abi-2.0.md`](docs/ecs-abi-2.0.md). La
fase 2 implementa el entity manager, la fase 3 genera su layout desde el
manifiesto y la fase 4 incorpora los sistemas ECS iniciales de behavior y
movimiento. La paridad completa con el juego de referencia queda para fases
posteriores.

## Mapa del repositorio

- `src/core`: interrupción/sincronización, entrada y sistemas ECS (manager, behavior, movimiento, entrada, plataforma, colisión y animación).
- `src/video`: direccionamiento, CRTC, limpieza, sprites con clipping y máscaras opcionales, y el renderer ECS selectivo.
- `src/ui`: fuente sprite Mode 0 recoloreable, números pequeños y ventanas con fondo restaurable.
- `src/audio`: adaptador opcional Arkos Tracker 3 AKG para el player de Next.
- `src/resources`: copia bancaria 128 KB, lectura AMSDOS y adaptador ZX7B.
- `src/extensions`: behavior, física y tilemaps optativos, sin entidad universal.
- `profiles`, `manifests`: entradas declarativas.
- `tools`: generación, validación, staging y medición.
- `examples`: veintitrés consumidores pequeños, sin copias internas del framework (`examples/nave`
  es el juego terminado de la guía `docs/first-game.md`).
- `docs`: procedencia, auditoría, arquitectura, APIs, migración y validación.

La aplicación didáctica de plataformas dispone de una guía paso a paso con
capturas reproducibles en `docs/platform-game-guide.html` y PDF equivalente.

## Vertical jugable

`examples/vertical` integra entrada, ECS (movimiento y colisión), vídeo y
recursos de juego. Mueve al jugador con los cursores y recoge los tres puntos situados a su
derecha. `assets.s` mantiene posiciones y bytes gráficos fuera de la lógica;
el manifiesto los selecciona mediante `game_sources`.

El smoke de AmSpiriT mantiene CursorRight en la matriz real del CPC y verifica
en RAM que el manager pasa de cuatro entidades a una, el marcador llega a tres y
el estado de victoria se activa. Más detalles en `docs/vertical-slice.md`.

## Física especializada

`extensions/physics_platform` conserva el perfil entero de plataformas:
velocidad byte, gravedad, caída máxima, dimensiones, límites y suelo.
`extensions/physics_8_8` mantiene aparte posición/velocidad fraccionarias,
fricción sobre el vector y rebote por eje. Los ejemplos `gravity` y `physics88`
comprueban recorridos deterministas sin compartir estructura de entidad y fijan
paletas propias para que sus trazas no dependan de los colores heredados de
BASIC. Los contratos y límites están en `docs/physics-profiles.md`.

## Tilemaps y colisión de escenario

`extensions/tilemap` consulta mapas de solo lectura propiedad del consumidor y
traduce cada id mediante una tabla de tipos. `extensions/platform_tilemap`
resuelve sólidos y plataformas de una dirección sobre el estado producido por
`physics_platform`, sin importar entidades, salas ni render. `tilecoll` muestra
automáticamente techo, pared y suelo; contratos y límites están en
`docs/tilemap-collision.md`.

`extensions/tilemap_render` dibuja un viewport desde un tileset Mode 0 mediante
las primitivas alineadas 2x4, 2x8, 4x4 y 4x8 de CPCTelera Next, con cámara y
destino propiedad del consumidor. Prevalida el render completo y permite
redibujar una celda explícita. La variante transparente usa el mismo tileset
con color clave y la tabla generada para el proyecto. `tilerender` demuestra cambio de cámara y
actualización parcial; véase `docs/tilemap-render.md`.

## Sprites con clipping y máscaras

`video/sprite` dibuja sprites rectangulares, recorta coordenadas con signo
contra los cuatro bordes y captura/restaura el fondo visible en un buffer del
consumidor. `fwk_sprite_draw` mantiene el camino opaco; `fwk_sprite_draw_masked`
usa como color clave el pen Mode 0 declarado en `transparency.pen`. La tabla de
256 bytes se genera y se instala en `0x0100` al llamar una sola vez a
`fwk_project_init`. Si el proyecto no declara transparencia, la API
enmascarada no se ensambla ni puede seleccionarse desde el manifiesto.
`fwk_sprite_draw_masked_recolor` añade la sustitución de un pen por otro durante
el dibujo sin modificar el asset y conserva el mismo clipping.
`spriteclip` comprueba los cuatro bordes y una restauración recortada;
`spritemask` demuestra composición, recoloreado, clipping y rechazo de pens y
spans inválidos. Véase
`docs/sprites.md`.

## Configuración inicial del proyecto

Todo ejemplo llama a `fwk_project_init`. El manifiesto puede declarar
`"transparency": {"pen": 0}` y/o `"extended_memory": true`. El código comienza
en `0x0200` por defecto. Al activar memoria extendida, el framework reserva en
`0x0200..0x0215` el stub y su scratch, inicia la detección una sola vez y
desplaza el código a la primera dirección libre, `0x0216`. La prueba usa
temporalmente `0x4000`, restaura
los bytes de RAM normal y banco 0 y no reserva ninguna dirección en
`0x4000..0x7FFF`.

`video/ecs_render` es el render selectivo: restaura y redibuja solo lo que
cambió, con entidades de uno o varios managers ECS, en un único orden estable
por Y. Los buffers de fondo los reparte el propio renderer desde pools que declara el proyecto. Admite dibujo
opaco, enmascarado y recoloreado. La ruta sincronizada separa
`fwk_ecs_render_prepare` (antes del VSYNC, sin tocar VRAM) de
`fwk_ecs_render_restore`/`fwk_ecs_render_draw`, que se ejecutan seguidos tras
VSYNC. `ecsrender` comprueba el ciclo completo contra un modelo Python; el
contrato está en la sección 8 de `docs/ecs-abi-2.0.md`.

La aplicación `platformer` es el juego completo sobre ECS 2.0: un manager
con cadencia por entidad, jugador, cuatro monedas, tres enemigos con behavior, puerta, dos
niveles y renderer selectivo. El HUD usa un panel interior y solo restaura el
dígito o tramo de estado que cambia. La construcción paso a paso está en
`docs/platform-game-guide.html`.

## Carga desde DSK y ZX7B

`examples/diskload` incorpora al DSK común un payload sintético crudo y el mismo
payload comprimido con ZX7B. Antes de desactivar el firmware, los carga desde
AMSDOS, descomprime el segundo y compara los 256 bytes. Este ejemplo solo
se ejecuta desde el DSK: sus archivos auxiliares no forman parte de una cinta CDT.

## Audio AKG

`examples/audio` enlaza el player AKG incluido en la revisión fijada de
CPCTelera Next y datos de demostración de Arkos Tracker con licencia MIT.
Reproduce música a 50 Hz mediante el callback de IRQ, admite SFX y expone
comandos de parada/reanudación para la prueba. El smoke comprueba ticks y
registros PSG reales en CPC 6128 y CPC 464; véase `docs/audio-akg.md`.

## Animación ECS

`core/ecs_animation` es el sistema de animación: cada entidad con el componente
`ANIMATION` lleva descriptor, frame y temporizador; el juego decide cuándo
llamar al sistema y cambia de animación con `fwk_ecs_anim_set`. El contrato
está en la sección 10 de `docs/ecs-abi-2.0.md` y `ecsanimation` lo comprueba
contra un modelo Python.

## Ventanas restaurables

`examples/window` captura un fondo propiedad del consumidor, dibuja una caja
con borde y relleno, compone texto y restaura exactamente la región anterior.
El módulo valida la geometría contra el perfil de vídeo y no contiene espera de
tecla, menús ni temporización. El smoke prueba cierre y reapertura en CPC 6128
y CPC 464; véase `docs/windows.md`.

## Estado del perfil 160x288

El modelo de memoria está comprobado automáticamente: 23.040 direcciones
visibles únicas, dos segmentos y coordenadas de 16 bits. La temporización CRTC
es una derivación explícita del overscan 96x272 de CPCTelera Next, no una
verificación en emulador ni hardware. Por ello sigue marcado como experimental.
