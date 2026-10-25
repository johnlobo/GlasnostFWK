# Vertical jugable

`examples/vertical` es la primera integración jugable de extremo a extremo del
framework. No pretende ser un juego completo ni una API universal de entidades.

## Comportamiento

- Cursores: movimiento en cuatro direcciones.
- Objetivo: recoger los tres puntos alineados a la derecha del jugador.
- El jugador y los puntos son registros `motion_u8` almacenados en un pool de
  cuatro elementos.
- Las posiciones y bytes gráficos están en `assets.s`, separado de `main.s` y
  declarado explícitamente en `example.json` mediante `game_sources`.
- Al recoger un punto, `fwk_pool_remove` compacta el pool. Al recoger los tres,
  `vertical_score` vale 3 y `vertical_status` cambia de `0xA5` a `0x5A`.

## Validación observable

`tests/emulator_smoke.py vertical` espera la inicialización del recurso, lee el
estado inicial en RAM, mantiene CursorRight mediante la matriz de teclado y
comprueba jugador, contador del pool, marcador, estado final y los bytes
gráficos de los recursos antes y después de ganar. Esta prueba detectó una
corrupción real en `fwk_pool_remove`: el número de registros que debía copiarse
se perdía al llamar a `fwk_pool_get`. La rutina conserva ahora ese contador
antes de la llamada.

La prueba pasó en AmSpiriT-Lite 1.15.3 tanto con CPC 6128 como con CPC 464.
No demuestra todavía temporización a 50 Hz, compatibilidad con hardware real ni
comportamiento visual en todos los tipos CRTC.
