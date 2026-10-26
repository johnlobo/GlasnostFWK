# Render de tilemaps

Fecha: 2026-10-26 UTC.

`extensions/tilemap_render.s` dibuja un rectángulo de un mapa row-major usando
gráficos Mode 0 de tamaño fijo. Consume el mismo descriptor de solo lectura que
la consulta de colisión, pero mantiene cámara, destino y tileset en un
descriptor separado propiedad del consumidor.

## Datos y descriptor

Cada gráfico ocupa exactamente `x_size * y_size` bytes: `x_size` bytes Mode 0
por scanline y `y_size` scanlines, sin padding. Los gráficos se concatenan por
id en el tileset.

```asm
FWK_TILEMAP_DESCRIPTOR level_map, map_data, collision_types, 32, 20, 2, 3, 4, 8, 16

FWK_TILE_RENDER_DESCRIPTOR level_view, tileset, 0, 0, 10, 24, 12, 10, 16
; tileset, camera_x, camera_y, screen_x, screen_y,
; viewport_width, viewport_height, tile_count
```

La cámara y el viewport se expresan en tiles. `screen_x` está en bytes Mode 0
y `screen_y` es una palabra de 16 bits, por lo que el módulo usa la geometría
del perfil activo mediante `fwk_video_get_ptr` y también admite el modelo de
direcciones verticales del perfil experimental. Esto no valida la señal CRTC
experimental.

## Render completo

```asm
ld ix, #level_map
ld iy, #level_view
call fwk_tilemap_render_view
jr c, invalid_view
```

Antes de escribir VRAM valida dimensiones no nulas, cámara dentro del mapa,
viewport dentro de la pantalla, tileset sin wrap de 16 bits y todos los ids de
la región contra `tile_count`. Si falla, devuelve carry activo sin escrituras.
Si pasa, dibuja el viewport completo y devuelve carry limpio.

## Actualización parcial

```asm
ld ix, #level_map
ld iy, #level_view
ld b, #row_in_view
ld c, #column_in_view
call fwk_tilemap_render_cell
```

`B` y `C` son coordenadas relativas al viewport, no al mapa ni a pantalla. La
rutina valida geometría, celda e id antes de escribir y redibuja solo el tile
seleccionado. El juego decide cuándo cambia la cámara y si necesita render
completo o parcial.

Ambas rutinas preservan `IX/IY`, alteran `AF,BC,DE,HL` y no son reentrantes
porque comparten scratch interno. No deben anidarse ni ejecutarse desde una IRQ
que pueda interrumpir otra llamada.

## Límites confirmados

- Mapas, cámara y viewport usan contadores de tiles de 8 bits.
- El tile es rectangular, sin transparencia ni clipping parcial.
- El tileset debe ser contiguo y permanecer visible; no hay bancos automáticos.
- No hay scroll sub-tile, doble buffer, dirty rectangles automáticos ni
  conversión de formatos gráficos.
- El módulo no modifica el mapa y no interpreta tipos de colisión.
- Habitaciones, portales, animación de tiles y política de cámara pertenecen al
  juego.

`examples/tilerender` dibuja un viewport de 5x4 tiles, mueve la cámara de
`(0,0)` a `(2,1)`, daña un byte de una celda y la restaura con la actualización
parcial. El smoke comprueba cámara, contador parcial, patrones y un testigo
exterior que debe permanecer intacto.
