# Vertical jugable

`examples/vertical` es la primera integración jugable de extremo a extremo del
framework. No pretende ser un juego completo ni una API universal de entidades.

## Comportamiento

- Cursores: movimiento en cuatro direcciones.
- Objetivo: recoger los tres puntos alineados a la derecha del jugador.
- Corre sobre ECS 2.0 con un solo manager de cuatro slots: el jugador (slot 0) y
  los tres puntos. Componentes `motion` y `collision`; el sistema `motion_u8`
  mueve al jugador y `fwk_ecs_collide` detecta cada punto (cajas de 1x1).
- Las posiciones y bytes gráficos están en `assets.s`, separado de `main.s` y
  declarado explícitamente en `example.json` mediante `game_sources`.
- Al tocar un punto, el callback de colisión lo marca `PENDING_DESTROY` (el
  jugador ocupa esa celda, la redibuja y la borra al avanzar); `fwk_ecs_manager_collect` libera el slot al final del
  fotograma. Al recoger los tres, `vertical_score` vale 3 y `vertical_status`
  cambia de `0xA5` a `0x5A`.

## Validación observable

`tests/emulator_smoke.py vertical` espera la inicialización del recurso, lee el
estado inicial en RAM, mantiene CursorRight mediante la matriz de teclado y
comprueba la posición del jugador, los slots activos del manager, el marcador, el
estado final y los bytes gráficos de los recursos antes y después de ganar
(los puntos recogidos no quedan en la pantalla). La versión anterior,
con un pool de registros, detectó una corrupción real en `fwk_pool_remove`
(el contador de registros a copiar se perdía al llamar a `fwk_pool_get`).

La prueba pasó en AmSpiriT-Lite 1.15.3 tanto con CPC 6128 como con CPC 464.
No demuestra todavía temporización a 50 Hz, compatibilidad con hardware real ni
comportamiento visual en todos los tipos CRTC.
