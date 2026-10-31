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

## Construcción y pruebas

```sh
make generate   # vídeo y manifiesto de recursos, deterministas
make examples   # veintidós ejemplos, incluidas dos escenas jugables
make test       # pruebas host + construcción completa
make report     # actualiza docs/build-sizes.md desde los mapas SDCC
make manual     # regenera docs/manual.pdf desde docs/manual.html
make release VERSION=0.1.0  # ZIP jugable y SHA256SUMS en dist/
python3 tests/emulator_smoke.py  # smoke real en AmSpiriT-Lite, si está instalado
```

Los BIN y CDT quedan en `.build/<ejemplo>/`; los veintidós BIN de prueba se reúnen
en `.build/tests/GlasnostFWK-tests.dsk`, junto con los payloads auxiliares que
necesita `diskload`. Los DSK individuales usados internamente por CPCTelera se
eliminan al terminar. `make test` no lanza emulador; el smoke opcional sí y usa
ese único DSK para comprobar estado de RAM, no solo que el proceso arranque.
Las versiones publicadas ofrecen los `.bin`, los CDT declarados y el DSK común
en un ZIP con checksum; el estado y la siguiente acción se mantienen en
[`PROJECT_STATUS.md`](PROJECT_STATUS.md).

El manual de uso completo está disponible en
[`docs/manual.html`](docs/manual.html) y [`docs/manual.pdf`](docs/manual.pdf).
Cada funcionalidad nueva debe documentarse allí y regenerar el PDF con
`make manual`; la suite comprueba cobertura y sincronización. La dependencia
de render se instala de forma aislada con
`python3 -m venv .venv-docs` y
`.venv-docs/bin/python -m pip install -r docs/requirements-manual.txt`.

## Mapa del repositorio

- `src/core`: interrupción/sincronización, entrada y pool genérico.
- `src/video`: direccionamiento, CRTC, limpieza y sprites con clipping, máscaras opcionales y orden.
- `src/ui`: fuente sprite Mode 0 recoloreable, números pequeños y ventanas con fondo restaurable.
- `src/audio`: adaptador opcional Arkos Tracker 3 AKG para el player de Next.
- `src/resources`: copia bancaria 128 KB, lectura AMSDOS y adaptador ZX7B.
- `src/extensions`: movimiento, física, animación y tilemaps optativos, sin entidad universal.
- `profiles`, `manifests`: entradas declarativas.
- `tools`: generación, validación, staging y medición.
- `examples`: veintidós consumidores pequeños, sin copias internas del framework.
- `docs`: procedencia, auditoría, arquitectura, APIs, migración y validación.

La aplicación didáctica de plataformas dispone de una guía paso a paso con
capturas reproducibles en `docs/platform-game-guide.html` y PDF equivalente.

## Vertical jugable

`examples/vertical` integra entrada, pool, movimiento, vídeo y recursos de
juego. Mueve al jugador con los cursores y recoge los tres puntos situados a su
derecha. `assets.s` mantiene posiciones y bytes gráficos fuera de la lógica;
el manifiesto los selecciona mediante `game_sources`.

El smoke de AmSpiriT mantiene CursorRight en la matriz real del CPC y verifica
en RAM que el pool pasa de cuatro entidades a una, el marcador llega a tres y
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

`video/entity_render` añade render selectivo de entidades: orden estable por Y,
restauración inversa y captura/dibujo directo para que varios sprites
solapados mantengan un orden explícito. Los buffers continúan en manos del
consumidor; solo se normaliza un prefijo de render de 25 bytes. Admite dibujo
opaco, enmascarado y recoloreado. `renderorder` comprueba el ciclo completo; véase
`docs/render-order.md`.

La ruta sincronizada separa `fwk_entity_render_prepare_dirty` —validación,
cierre y orden sin tocar VRAM— de `restore_dirty`/`draw_dirty`, que pueden
ejecutarse consecutivamente tras VSYNC. Las identidades y rangos de buffer se
validan en `init` o `revalidate`, fuera de la sección crítica.

La aplicación `platformer` usa este renderer para el jugador y las cuatro
monedas: mantiene el estado compacto de física detrás del prefijo y oculta
coleccionables mediante `VISIBLE|DIRTY`. El HUD usa un panel interior y solo
restaura el dígito o tramo de estado que cambia. La construcción paso a paso está en
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

## Animación reutilizable

`examples/animation` recorre tres frames sintéticos cada cuatro ticks. El
módulo solo mantiene descriptor, índice y temporizador: el juego decide cuándo
llamarlo y cómo dibujar. El smoke comprueba el periodo exacto, los punteros de
frame, el byte renderizado y que una pausa impuesta por el consumidor congela
el estado en CPC 6128 y CPC 464. Detalles en `docs/animation.md`.

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
