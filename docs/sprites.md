# Sprites Mode 0 con clipping, restauración y máscaras

Fecha: 2026-10-27 UTC.

`video/sprite.s` dibuja rectángulos de bytes Mode 0 y separa la imagen, la
posición y el buffer de fondo de cualquier entidad o regla de juego. Usa la
tabla de líneas del perfil activo y recorta en los cuatro bordes. El camino
opaco y el camino con máscara son rutinas separadas: `fwk_sprite_draw` no
cambia cuando se usa `fwk_sprite_draw_masked`.

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

- `fwk_sprite_draw`: `IX=descriptor`. Dibuja solamente el rectángulo visible de
  forma opaca. Devuelve carry activo si ancho/alto son cero o si
  `data + width*height` desborda el espacio de 16 bits. Un sprite completamente
  exterior es válido, devuelve carry limpio y no escribe.
- `fwk_sprite_draw_masked`: `IX=descriptor`, `DE=máscara paralela`. Dibuja el
  rectángulo visible aplicando bit a bit `(pantalla AND máscara) OR datos`.
  Devuelve carry si el descriptor, el span de datos o el span completo de la
  máscara son inválidos. También acepta sin escrituras un sprite exterior, pero
  la máscara debe ser válida.
- `fwk_sprite_capture`: `IX=descriptor`, `DE=buffer`. Copia el fondo del
  rectángulo visible y devuelve `IY` apuntando al final de los bytes usados.
- `fwk_sprite_restore`: `IX=mismo descriptor`, `HL=buffer` capturado. Restaura
  el mismo rectángulo visible y también devuelve `IY` al final del buffer.

`fwk_sprite_draw` y `fwk_sprite_draw_masked` preservan `IX` e `IY`, y alteran
`AF,BC,DE,HL`. Captura y restauración preservan `IX` y alteran `AF,BC,DE,HL,IY`.
Todas usan estado interno, por lo que no son reentrantes ni deben interrumpirse
con otra llamada al módulo.

## Máscara paralela

La máscara tiene exactamente `width*height` bytes, en el mismo orden row-major
y sin padding que los datos. Se pasa la dirección base en `DE`; el recorte
desplaza datos y máscara con el mismo `source_x/source_y`.

La composición es:

```text
resultado = (fondo AND mascara) OR datos
```

| Bit de máscara | Bit de datos | Resultado |
|---|---|---|
| 1 | debe ser 0 | conserva el fondo |
| 0 | cualquiera | escribe el bit de datos |

Por tanto, un bit 1 significa «transparente» y los bits de datos cubiertos por
un 1 deben estar a cero en el asset. Si no se cumple esa invariante, la imagen
puede quedar con bits encendidos no deseados. La operación es bit a bit: en
Mode 0 cada píxel ocupa 4 bits y cada byte contiene dos píxeles, así que una
máscara `0xF0` conserva un píxel y sustituye el otro. También se pueden
preservar bits sueltos, pero el resultado de color es responsabilidad del asset.
No hay color-key ni mezcla alfa.

Ejemplo de asset:

```asm
masked_pixels:
    .db 0x00, 0x0A, 0x00   ; datos: cero bajo los bits preservados
masked_mask:
    .db 0xFF, 0xF0, 0xFF   ; 1 conserva el fondo; F0 preserva un píxel Mode 0
```

## Ciclo de movimiento recomendado

```asm
; Antes de dibujar en la posición actual
ld ix, #player_sprite
ld de, #sprite_background
call fwk_sprite_capture
ld de, #player_mask
call fwk_sprite_draw_masked

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

- `fwk_sprite_draw` es opaco. La transparencia solo existe en
  `fwk_sprite_draw_masked`.
- `video/sprite_batch` sigue usando el camino opaco; no integra la variante
  enmascarada ni ordena capas con máscara.
- La variante enmascarada vive en el mismo `video/sprite.s`: cualquier ejemplo
  que enlace el módulo paga también su código aunque no llame a
  `fwk_sprite_draw_masked`.
- La máscara es bit a bit. En Mode 0 se puede preservar un píxel de 4 bits y
  sustituir el otro del mismo byte; no hay color-key ni mezcla alfa.
- No hay recoloreado, mezcla, ordenación automática, lista de dirty rectangles ni
  doble buffer.
- No se comprueba la capacidad del buffer aportado por el consumidor ni se
  validan punteros nulos; el asset y la máscara deben ser válidos y permanecer
  visibles en el mapeo de RAM activo.
- Ancho y alto máximos son 255; el perfil de vídeo debe tener dimensiones
  positivas que quepan en coordenadas con signo de 16 bits.
- No se han medido ciclos del camino opaco ni del enmascarado; no se promete un
  presupuesto global de 50 Hz.

`examples/spriteclip` prueba geometría inválida, span de datos con wrap, sprite
totalmente exterior, clipping independiente en los cuatro bordes y una
captura/restauración de 4x5 bytes recortada simultáneamente arriba e izquierda.
`examples/spritemask` añade una máscara paralela, comprueba la composición con
fondo no uniforme, el recorte conjunto de datos y máscara, el rechazo de un span
de máscara con wrap y un sprite exterior sin escrituras.
