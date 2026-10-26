# Sprites Mode 0 con clipping y restauración

Fecha: 2026-10-26 UTC.

`video/sprite.s` dibuja rectángulos de bytes Mode 0 y separa la imagen, la
posición y el buffer de fondo de cualquier entidad o regla de juego. Usa la
tabla de líneas del perfil activo y recorta en los cuatro bordes.

## Descriptor

Incluya `video/sprite.inc` y declare un descriptor mutable de ocho bytes:

```asm
sprite_pixels:
    ; width*height bytes, por filas y sin padding

FWK_SPRITE_DESCRIPTOR player_sprite, sprite_pixels, 20, 40, 6, 8
sprite_background: .ds 6 * 8
```

Los campos son puntero a datos, X con signo de 16 bits en bytes Mode 0, Y con
signo de 16 bits en scanlines, ancho y alto de 8 bits. Las coordenadas negativas
permiten que una imagen entre o salga parcialmente por arriba o por la izquierda.
El ancho se expresa en bytes, no en píxeles: en Mode 0 cada byte contiene dos
píxeles.

## API

- `fwk_sprite_draw`: `IX=descriptor`. Dibuja solamente el rectángulo visible.
  Devuelve carry activo si ancho/alto son cero o si `data + width*height`
  desborda el espacio de 16 bits. Un sprite completamente exterior es válido,
  devuelve carry limpio y no escribe.
- `fwk_sprite_capture`: `IX=descriptor`, `DE=buffer`. Copia el fondo del
  rectángulo visible y devuelve `IY` apuntando al final de los bytes usados.
- `fwk_sprite_restore`: `IX=mismo descriptor`, `HL=buffer capturado`. Restaura
  el mismo rectángulo visible y también devuelve `IY` al final del buffer.

Las tres rutinas preservan `IX`. Dibujo preserva `IY` y altera
`AF,BC,DE,HL`; captura y restauración alteran además `IY`. Usan estado interno,
por lo que no son reentrantes ni deben interrumpirse con otra llamada al módulo.

## Ciclo de movimiento recomendado

```asm
; Antes de dibujar en la posición actual
ld ix, #player_sprite
ld de, #sprite_background
call fwk_sprite_capture
call fwk_sprite_draw

; Antes de cambiar X/Y
ld ix, #player_sprite
ld hl, #sprite_background
call fwk_sprite_restore
; actualizar coordenadas, capturar el nuevo fondo y volver a dibujar
```

El buffer debe reservar al menos `width*height` bytes. El recorte puede usar
menos, pero captura y restauración deben recibir la misma geometría y el mismo
contenido de buffer. Si se mueve el descriptor antes de restaurar, el fondo se
copiará en una posición distinta.

## Límites confirmados

- Los datos son opacos: no hay máscara, transparencia, mezcla ni recoloreado.
- No hay ordenación de entidades, lista de dirty rectangles ni doble buffer.
- El módulo no comprueba la capacidad del buffer aportado por el consumidor.
- Ancho y alto máximos son 255; el perfil de vídeo debe tener dimensiones
  positivas que quepan en coordenadas con signo de 16 bits.
- Los datos y el buffer deben permanecer visibles en el mapeo de RAM activo.
- No se han medido ciclos ni se promete un presupuesto global de 50 Hz.

`examples/spriteclip` prueba geometría inválida, span de datos con wrap,
sprite totalmente exterior, clipping independiente en los cuatro bordes y una
captura/restauración de 4x5 bytes recortada simultáneamente arriba e izquierda.
