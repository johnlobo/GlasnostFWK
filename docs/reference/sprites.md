# Sprites Mode 0 y Mode 1 con clipping, restauración, transparencia y recoloreado

Fecha: 2026-10-29 UTC.

`video/sprite.s` dibuja rectángulos Mode 0 y Mode 1, usa la tabla de líneas del perfil y
recorta en los cuatro bordes. El camino opaco y el transparente son rutinas
separadas. La transparencia es una capacidad del proyecto, no una máscara que
se pase en cada dibujo.

## Configuración

Declare el pen transparente en el manifiesto:

```json
"transparency": {"pen": 3}
```

El pen debe estar entre 0 y 15 en Mode 0 o entre 0 y 3 en Mode 1. La construcción añade
`video/transparency.s`, genera su tabla de 256 bytes y `fwk_project_init` la
copia una sola vez a `0x0100`. Sin esta propiedad, `fwk_sprite_draw_masked` no
se ensambla y seleccionar un módulo que dependa de transparencia produce un
error de construcción.

Cada byte del asset contiene dos píxeles Mode 0 o cuatro Mode 1. Los píxeles que usen el pen
configurado conservan el fondo; los demás reemplazan su píxel completo. No hay
mezcla alfa ni una máscara paralela.

## Descriptor y API

```asm
.include "video/sprite.inc"

sprite_pixels:
    ; width*height bytes, por filas y sin padding

FWK_SPRITE_DESCRIPTOR player_sprite, sprite_pixels, 20, 40, 6, 8
sprite_background: .ds 6 * 8
```

El descriptor mutable tiene ocho bytes: puntero a datos, X/Y con signo de 16
bits, ancho en bytes y alto en scanlines.

- `fwk_sprite_draw`: `IX=descriptor`; dibujo opaco.
- `fwk_sprite_draw_recolor`: `IX=descriptor`, `D=pen origen` y
  `E=pen sustituto`; dibujo opaco con recoloreado.
- `fwk_sprite_draw_masked`: `IX=descriptor`; dibujo con el pen transparente
  configurado y la tabla implícita de `0x0100`.
- `fwk_sprite_draw_masked_recolor`: `IX=descriptor`, `D=pen origen` y
  `E=pen sustituto`; reemplaza un pen durante el dibujo y aplica después el
  color clave configurado. Ambos pens deben estar entre 0 y 15 en Mode 0 o
  entre 0 y 3 en Mode 1.
- `fwk_sprite_capture`: `IX=descriptor`, `DE=buffer`; guarda el fondo visible y
  devuelve `IY` al final de los bytes utilizados.
- `fwk_sprite_restore`: `IX=mismo descriptor`, `HL=buffer`; restaura el fondo y
  devuelve `IY` al final.

Los dibujos preservan `IX/IY` y alteran `AF,BC,DE,HL`. Captura y restauración
preservan `IX` y alteran también `IY`. Carry indica ancho/alto cero o un span de
datos que desborda 16 bits. Un sprite totalmente exterior es válido y no
escribe. El módulo usa scratch interno y no es reentrante.

En Mode 1, X y el ancho se indican en bytes de cuatro píxeles. El asset debe
estar empaquetado en el formato CPC Mode 1. `fwk_project_init` debe ejecutarse
antes de usar las variantes enmascaradas para instalar la tabla en `0x0100`.

El importador convierte PNG a ese formato si `assets/assets.json` declara
`"mode": 1` y `assets/palette.json` contiene cuatro colores de firmware:

```json
{"version": 1, "mode": 1, "palette": "palette.json",
 "images": [{"source": "src/sprites.png", "width": 8, "height": 8,
             "tiles": ["sprite_a", "sprite_b"]}]}
```

El ancho de cada sprite debe ser múltiplo de cuatro píxeles. El manifiesto del
juego debe seleccionar un perfil Mode 1, como `mode1-192x192.json`; el build
rechaza un `assets.json` cuyo modo no coincida. Si falta `mode`, se conserva
Mode 0 por compatibilidad con los proyectos existentes.

## Ciclo recomendado

```asm
ld ix, #player_sprite
ld de, #sprite_background
call fwk_sprite_capture
call fwk_sprite_draw_masked

; La misma imagen, sustituyendo pen 5 por pen 15 sin modificar el asset:
ld ix, #player_sprite
ld d, #5
ld e, #15
call fwk_sprite_draw_masked_recolor

; Antes de cambiar X/Y:
ld ix, #player_sprite
ld hl, #sprite_background
call fwk_sprite_restore
```

El buffer debe reservar al menos `width*height` bytes. Descriptor y buffer deben
conservarse entre captura y restauración.

## Límites comprobados

- `ecs_render` selecciona las cuatro combinaciones de opacidad/máscara y
  recoloreado mediante flags de la entidad.
- El recoloreado sustituye un único pen por llamada; no es una remap completa
  de los 16 pens Mode 0 ni de los cuatro pens Mode 1. Se realiza antes de la transparencia: sustituir por el color
  clave oculta esos píxeles y sustituir el color clave por otro pen los vuelve
  opacos.
- La rutina usa la conversión de pens del modo activo de CPCtelera Next y una composición
  propia porque su camino rápido alineado presupone pen transparente 0; el
  framework debe admitir cualquier `transparency.pen`.
- No hay mezcla alfa ni doble buffer; los dirty rectangles se propagan por
  rectángulos completos, no por píxeles opacos individuales.
- No se valida la capacidad del buffer ni un puntero nulo; los datos deben
  permanecer visibles en el mapeo activo.
- El coste publicado en `docs/design/performance.md` es histórico: la implementación
  transparente ha cambiado y debe volver a medirse antes de atribuirle esas cifras.

`examples/spriteclip` prueba clipping y restauración. `examples/spritemask`
configura el pen 3, comprueba la tabla generada, la composición sobre un fondo
no uniforme, el recorte, el rechazo de pens y spans inválidos, un sprite
exterior y el reemplazo de pen 5 por pen 15.
