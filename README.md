# GlasnostFWK

Framework modular en ensamblador Z80 para Amstrad CPC, extraído y consolidado
de `model01`, `boop`, `DeckTower` y `PocketFever`. La primera versión estable
se centra en un núcleo pequeño, entrada con flancos, vídeo Mode 0 declarativo,
colecciones sin estructura universal, texto, audio AKG opcional y copia
bancaria de 128 KB.

El framework no contiene assets ni reglas de los juegos originales. Cada
ejemplo declara sus módulos en `examples/*/example.json`; el constructor copia
únicamente esos fuentes al árbol temporal `.build/`, de modo que excluir una
funcionalidad la excluye también del enlazado.

## Dependencia fijada

- CPCTelera Next: revisión `11e61fe30175ad7b328de9bcd859c46fd61b26a5`.
- SDCC Z80: 4.5.0, build 15242, distribuido por esa revisión.
- Ruta local predeterminada: `/config/workspace/cpctelera_next/cpctelera`.

Puede elegirse otra instalación compatible con `CPCT_NEXT_PATH` o
`tools/build_examples.py --cpct-path`.

## Construcción y pruebas

```sh
make generate   # vídeo y manifiesto de recursos, deterministas
make examples   # minimal, board, platform, video y resources128
make test       # pruebas host + construcción completa
make report     # actualiza docs/build-sizes.md desde los mapas SDCC
python3 tests/emulator_smoke.py  # smoke real en AmSpiriT-Lite, si está instalado
```

Los artefactos quedan en `.build/<ejemplo>/`. `make test` no lanza emulador;
el smoke opcional sí y comprueba estado de RAM, no solo que el proceso arranque.

## Mapa del repositorio

- `src/core`: interrupción/sincronización, entrada y pool genérico.
- `src/video`: direccionamiento, CRTC generado y limpieza visible.
- `src/ui`: adaptador de texto Mode 0.
- `src/audio`: adaptador opcional Arkos Tracker 3 AKG.
- `src/resources`: copia bancaria 128 KB.
- `src/extensions`: perfiles de entidad/movimiento optativos.
- `profiles`, `manifests`: entradas declarativas.
- `tools`: generación, validación, staging y medición.
- `examples`: cinco consumidores pequeños, sin copias internas del framework.
- `docs`: procedencia, auditoría, arquitectura, APIs, migración y validación.

## Estado del perfil 160x288

El modelo de memoria está comprobado automáticamente: 23.040 direcciones
visibles únicas, dos segmentos y coordenadas de 16 bits. La temporización CRTC
es una derivación explícita del overscan 96x272 de CPCTelera Next, no una
verificación en emulador ni hardware. Por ello sigue marcado como experimental.
