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

> **Medido el 2026-11-06** con `tools/measure_perf.py` sobre el código actual
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
  cifra anterior (94.089 T, ~1,18 frames) era del módulo `entity_render`, que ya
  no existe, y no es comparable: medía otra implementación y otro caso.

## Decisión sobre `entity_render`

- `fwk_sprite_draw_masked` sigue siendo una API separada del camino opaco y usa
  el color clave configurado para el proyecto.
- `fwk_sprite_draw_masked_recolor` es también una ruta separada. Su coste aún
  no se ha medido y no debe inferirse de la cifra histórica del enmascarado.
- `entity_render` selecciona por flags las rutas opaca, enmascarada, recoloreada
  y enmascarada-recoloreada. La cifra histórica del lote ya no mide este módulo
  y debe repetirse antes de usarla para presupuestar un frame.
- La ruta preparada valida identidades y rangos estructurales en `init` o
  `revalidate`; por frame calcula cierre/preflight/orden antes del VSYNC y deja
  consecutivas restauración y captura/dibujo. En `platformer`, con tres monedas
  visibles, pasó de 10 a 20 actualizaciones durante una entrada programada de
  19 frames (el frame de activación añade una actualización). Es una observación
  de cadencia, no una medición de T-estados.
- No se promete 50 Hz para escenas arbitrarias; la decisión se toma con estas
  cifras, no con estimaciones.
