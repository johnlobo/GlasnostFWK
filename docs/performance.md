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

| Escena | Frames | Llamadas | T-estados/llamada | Frames/llamada |
|---|---:|---:|---:|---:|
| Bucle vacío (sobrecarga) | 32 | 20000 | 128 | 0,0016 |
| Limpieza completa de vídeo | 1080 | 100 | 862618 | 10,80 |
| Sprite opaco 6x8 | 312 | 4000 | 6230 | 0,078 |
| Sprite enmascarado 6x8 | 345 | 2500 | 11022 | 0,138 |
| Captura 6x8 | 292 | 4000 | 5831 | 0,073 |
| Restauración 6x8 | 291 | 4000 | 5811 | 0,073 |
| Lote de 8 sprites 4x4 (dibujo+restauración) | 589 | 500 | 94089 | 1,18 |
| Tilemap completo 5x4 tiles | 248 | 300 | 66028 | 0,83 |
| Actualización de una celda | 291 | 5000 | 4649 | 0,058 |

## Presupuesto de frame

Un frame a 50 Hz son `79872` T-estados. Referencias útiles:

- Limpiar toda la pantalla cuesta ~10,8 frames; no conviene hacerlo cada frame.
- Un sprite opaco 6x8 cuesta ~0,08 frames; un enmascarado equivalente ~0,14 frames.
- Un tilemap completo 5x4 cuesta ~0,83 frames; una celda ~0,06 frames.
- El lote de 8 sprites 4x4 (captura + dibujo + restauración) cuesta ~1,18 frames.

## Decisión sobre `sprite_batch`

- `fwk_sprite_draw_masked` sigue siendo una API separada del camino opaco.
- El lote ordenado (`sprite_batch`) sigue siendo solo opaco: la máscara bit a bit
  exige leer y escribir cada byte y cuesta ~1,77× el camino opaco, por lo que
  integrarla en el mismo lote mezclaría rutas con costes muy distintos.
- Si se necesita ordenar sprites enmascarados, se añadirá un lote específico o
  un modo explícito en una fase posterior, con sus propias mediciones.
- No se promete 50 Hz para escenas arbitrarias; la decisión se toma con estas
  cifras, no con estimaciones.
