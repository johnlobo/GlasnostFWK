# GlasnostFWK

[![CI](https://github.com/johnlobo/GlasnostFWK/actions/workflows/ci.yml/badge.svg)](https://github.com/johnlobo/GlasnostFWK/actions/workflows/ci.yml)

Framework modular en ensamblador Z80 para Amstrad CPC, extraído y consolidado
de `model01`, `boop`, `DeckTower` y `PocketFever`. La primera versión estable
se centra en un núcleo pequeño, entrada con flancos, vídeo Mode 0 declarativo,
colecciones sin estructura universal, texto, audio AKG opcional y copia
bancaria de 128 KB.

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
make examples   # diez ejemplos: vertical, disco, audio, animación y ventanas
make test       # pruebas host + construcción completa
make report     # actualiza docs/build-sizes.md desde los mapas SDCC
make manual     # regenera docs/manual.pdf desde docs/manual.html
make release VERSION=0.1.0  # ZIP jugable y SHA256SUMS en dist/
python3 tests/emulator_smoke.py  # smoke real en AmSpiriT-Lite, si está instalado
```

Los artefactos quedan en `.build/<ejemplo>/`. `make test` no lanza emulador;
el smoke opcional sí y comprueba estado de RAM, no solo que el proceso arranque.
Las versiones publicadas ofrecen los `.bin` y los medios declarados por cada
ejemplo en un ZIP con checksum; el estado y la siguiente acción se mantienen en
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
- `src/video`: direccionamiento, CRTC generado y limpieza visible.
- `src/ui`: texto Mode 0 y ventanas con fondo restaurable.
- `src/audio`: adaptador opcional Arkos Tracker 3 AKG para el player de Next.
- `src/resources`: copia bancaria 128 KB, lectura AMSDOS y adaptador ZX7B.
- `src/extensions`: movimiento y animación optativos, sin entidad universal.
- `profiles`, `manifests`: entradas declarativas.
- `tools`: generación, validación, staging y medición.
- `examples`: diez consumidores pequeños, sin copias internas del framework.
- `docs`: procedencia, auditoría, arquitectura, APIs, migración y validación.

## Vertical jugable

`examples/vertical` integra entrada, pool, movimiento, vídeo y recursos de
juego. Mueve al jugador con los cursores y recoge los tres puntos situados a su
derecha. `assets.s` mantiene posiciones y bytes gráficos fuera de la lógica;
el manifiesto los selecciona mediante `game_sources`.

El smoke de AmSpiriT mantiene CursorRight en la matriz real del CPC y verifica
en RAM que el pool pasa de cuatro entidades a una, el marcador llega a tres y
el estado de victoria se activa. Más detalles en `docs/vertical-slice.md`.

## Carga desde DSK y ZX7B

`examples/diskload` incorpora al DSK un payload sintético crudo y el mismo
payload comprimido con ZX7B. Antes de desactivar el firmware, los carga desde
AMSDOS, descomprime el segundo y compara los 256 bytes. Este ejemplo solo
produce DSK: sus archivos auxiliares no forman parte de una cinta CDT.

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
