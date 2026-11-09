# Rendimiento medible y presupuesto de frame

## Método

- Arnés: `examples/perf`, construido como el resto de ejemplos (`perf.BIN`,
  incluido en el DSK común como `PERF.BIN`).
- Medición por frames emulados, no por ciclos del emulador: cada escena ejecuta
  un número fijo de llamadas, mide `fwk_system_frame_count` antes y después y
  convierte con `79872` T-estados/frame (CPC 6128, 50 Hz, 312 líneas × 64 µs).
- La primera escena (`empty`) mide la sobrecarga del bucle de medida y puede
  restarse para aislar la rutina.
- Incertidumbre: ±1 frame completo en cada escena, es decir
  `79872 / iteraciones` T-estados por llamada. Las escenas rápidas usan miles de
  iteraciones para bajar ese error por debajo del 1 %.
- Los resultados incluyen la sobrecarga IRQ de 300 Hz del framework y del bucle
  de medida; no son ciclos puros de la rutina.

## Resultados (CPC 6128, perfil estándar 160x200)

> **Medido el 2026-11-06** con `tools/dev/measure_perf.py` sobre el código actual
> (CPC 6128). Sustituye a la serie histórica anterior al render CPCTelera Next:
> el tilemap usa las rutas `cpct_drawTileAligned*_f_asm`, el enmascarado usa la
> transparencia configurable de color clave y el lote usa `ecs_render`.

| Escena | Frames | Llamadas | T-estados/llamada | Frames/llamada |
|---|---:|---:|---:|---:|
| Bucle vacío (sobrecarga) | 32 | 20000 | 128 | 0,0016 |
| Limpieza completa de vídeo | 1080 | 100 | 862618 | 10,80 |
| Sprite opaco 6x8 | 312 | 4000 | 6230 | 0,078 |
| Sprite enmascarado 6x8 | 402 | 2500 | 12843 | 0,161 |
| Captura 6x8 | 292 | 4000 | 5831 | 0,073 |
| Restauración 6x8 | 291 | 4000 | 5811 | 0,073 |
| Lote de 8 sprites 4x4 apilados, `ecs_render` (prepare+restauración+dibujo) | 1080 | 500 | 172524 | 2,16 |
| Tilemap completo 5x4 tiles | 166 | 300 | 44196 | 0,55 |
| Actualización de una celda | 239 | 5000 | 3818 | 0,048 |

## Presupuesto de frame

Un frame a 50 Hz son `79872` T-estados. Referencias útiles:

- Limpiar toda la pantalla cuesta ~10,8 frames; no conviene hacerlo cada frame.
- Un sprite opaco 6x8 cuesta ~0,08 frames; un enmascarado equivalente ~0,16 frames.
- Un tilemap completo 5x4 cuesta ~0,55 frames; una celda ~0,05 frames.
- El lote de 8 sprites 4x4 con `ecs_render` (prepare + restauración + dibujo) cuesta ~2,16 frames
  con los ocho apilados en el mismo punto, el peor caso del cierre de solapes. La
  cifra anterior (94.089 T, ~1,18 frames) se midió con el módulo anterior
  (`entity_render`, ya eliminado) y no es comparable: medía otra implementación
  y otro caso.

## Decisiones vigentes sobre sprites

- `fwk_sprite_draw_masked` sigue siendo una API separada del camino opaco y usa
  el color clave configurado para el proyecto.
- `fwk_sprite_draw_masked_recolor` es también una ruta separada. Su coste aún
  no se ha medido y no debe inferirse de la cifra histórica del enmascarado.
- `ecs_render` selecciona por flags de entidad las rutas opaca, enmascarada,
  recoloreada y enmascarada-recoloreada; su coste medido es el del lote de ocho
  de la tabla.
- Histórico, medido con el módulo anterior (`entity_render`), ya eliminado: la
  ruta preparada validaba identidades en `init` y pasó, en `platformer` con tres
  monedas visibles, de 10 a 20 actualizaciones durante una entrada programada de
  19 frames. Era una observación de cadencia, no una medición de T-estados, y no
  describe al renderer actual.
- No se promete 50 Hz para escenas arbitrarias; la decisión se toma con estas
  cifras, no con estimaciones.

## Spike: fondo por repintado de tiles frente a captura y restauración

Pregunta: ¿puede `ecs_render` dejar de guardar un buffer de fondo por entidad y
repintar en su lugar los tiles que tocó cada sprite que se movió (cola de tiles
sucios con deduplicación, `fwk_tilemap_render_cell` por tile)? Medido el
2026-11-06 con `tools/dev/measure_perf.py` (CPC 6128, 500 llamadas por escena), con
los cuatro sprites móviles de `platformer` (uno de 8x8 y tres de 4x8) sobre un
mapa de tiles de 4 bytes x 8 líneas. El parche del spike no está en el
repositorio; se conserva fuera de él como `spike-tile-repaint.patch`.

| Escena (4 sprites) | Tiles repintados | T-estados/llamada |
|---|---:|---:|
| Captura + restauración (hoy) | no aplica | 44089 |
| Repintado de tiles, sprites fuera de la rejilla | 17 | 97124 |
| Repintado de tiles, sprites sobre la rejilla | 5 | 29393 |

- El repintado cuesta 5700 a 5900 T por tile en cola, frente a 3818 T de una
  celda aislada: unos 1900 T van a la cola, la deduplicación y el borrado de
  marcas. Una versión afinada podría ahorrar parte, sin medir.
- En `platformer` los sprites casi nunca están alineados: un 4x8 se mueve 1 byte
  por frame en X (alineado 1 de cada 4) y el jugador cae en cualquier línea.
  Estimación de tiles por frame: unos 15 (jugador 5,2 y enemigos 3,2 cada uno),
  es decir unos 84000 T, **40000 T más que hoy** (sin medir en el juego).
  El trabajo de `platformer` pasaría de unos 111000 T a unos 151000 T, al borde
  del presupuesto de 2 frames (159744 T) antes de contar el cierre de solapes,
  que crece con el área repintada.
- Umbral fijado antes de medir: como mucho +15000 T para `platformer`. No se
  cumple. Decisión: el repintado por tile completo **no se adopta**.
- Lo que sí enseña la medida: captura y restauración de los cuatro sprites son
  ya 44000 T (más de un tercio del trabajo de `platformer`). Una alternativa sin
  medir es repintar solo el rectángulo del sprite desde el tilemap (bloques
  parciales de tile, sin captura), con un coste estimado de unos 30000 T.
