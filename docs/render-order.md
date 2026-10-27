# Orden explícito de render de sprites

`video/sprite_batch.s` coordina varios descriptores de `video/sprite.s` sin
introducir una entidad universal. Cada entrada conserva un puntero al sprite,
un buffer de fondo propiedad del consumidor, una clave de orden de 8 bits y
un flag interno de captura.

## Estructuras y alta

Cada entrada ocupa seis bytes. El descriptor de lote contiene el puntero al
array, el número actual de entradas y su capacidad:

```asm
render_entries: .ds 8 * FWK_SPRITE_BATCH_ENTRY_SIZE
FWK_SPRITE_BATCH_DESCRIPTOR render_batch, render_entries, 8
```

1. Llame a `fwk_sprite_batch_init` con `IX=lote`.
2. Para cada sprite, use `IX=lote`, `HL=descriptor`, `DE=buffer` y `A=clave`,
   y llame a `fwk_sprite_batch_add`.
3. Las entradas quedan ordenadas de menor a mayor clave. Dos claves iguales
   conservan el orden de alta.

La inicialización rechaza capacidad cero y arrays cuyo span de 16 bits haga
wrap. `add` devuelve carry si el descriptor es inválido o está lleno, sin
alterar las entradas existentes.

## Ciclo por frame

```text
fwk_sprite_batch_restore     ; capas superiores primero
actualizar fondo/tilemap     ; política del juego
actualizar posiciones        ; política del juego
fwk_sprite_batch_draw        ; capas inferiores primero
```

`restore` recorre el lote en orden inverso, repone cada captura y limpia su
flag. Así, la restauración de una capa inferior no borra una superior que ya
se hubiera vuelto a dibujar. Después de actualizar el mundo, `draw` recorre el
orden directo; para cada entrada captura el fondo y dibuja el sprite. Una clave
mayor queda visualmente encima en las zonas solapadas.

`draw` exige que todos los flags estén limpios. Una segunda llamada sin
`restore` devuelve carry antes de modificar buffers o VRAM. Si una rutina de
sprite falla durante un pase, las entradas anteriores ya pueden haberse
procesado; el llamador debe tratarlo como un fallo parcial. `restore` se puede
repetir: ignora las entradas que no estén marcadas como capturadas.

## Límites

- Los buffers y descriptores siguen perteneciendo al consumidor y deben vivir
  mientras el lote los use.
- No cambie la geometría de un sprite entre su captura y restauración.
- El lote usa scratch interno y no es reentrante ni apto para una IRQ que pueda
  interrumpir otro pase.
- No asigna memoria, elimina entradas ni decide claves, cámara o sincronización.
- Usa el camino opaco de `video/sprite`: no integra
  `fwk_sprite_draw_masked`, transparencia, recoloreado ni dirty rectangles
  automáticos.
- Mediciones en `docs/performance.md`: lote de 8 sprites 4x4 (captura + dibujo +
  restauración) ≈ 94089 T-estados (≈1,18 frames). No se promete 50 Hz para
  escenas arbitrarias.

`examples/renderorder` añade primero la capa superior para demostrar la
ordenación estable, comprueba capacidad y doble captura, restaura un fondo no
uniforme, modifica un byte del escenario entre pases y vuelve a dibujar dos
sprites solapados.
