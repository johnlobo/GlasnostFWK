# Render selectivo de entidades

`video/entity_render.s` reemplaza al antiguo `sprite_batch`. Trabaja con un
array contado de punteros a entidades; los punteros nulos son huecos válidos y
los duplicados son error. Cada entidad comienza con el prefijo estándar de 25
bytes definido en `video/entity_render.inc`.

```asm
entity_ptrs: .dw player, enemy, 0, effect
render_work: .ds 4 * FWK_ENTITY_RENDER_WORK_SIZE
FWK_ENTITY_RENDER_DESCRIPTOR render_list, entity_ptrs, 4, render_work, 4
```

El prefijo contiene el descriptor de sprite compatible en sus primeros ocho
bytes, `sort_y` signed de 16 bits, buffer y capacidad, geometría y orden
anteriores, flags y los pens de recoloreado. Los flags públicos son `VISIBLE`,
`DIRTY`, `MASKED` y `RECOLOR`; `HAS_BACKGROUND` pertenece al renderer.

Flujo por frame:

```asm
; actualizar entidades y activar DIRTY
ld ix, #render_list
call fwk_entity_render_prepare_dirty ; validacion/cierre/orden, sin tocar VRAM
call fwk_system_wait_frame
ld ix, #render_list
call fwk_entity_render_restore_dirty
; aquí puede redibujarse el fondo ya marcado
ld ix, #render_list
call fwk_entity_render_draw_dirty
```

`prepare_dirty` calcula el cierre transitivo de solapamientos usando la unión
de los rectángulos anterior y actual, prevalida y construye el orden anterior
sin escribir VRAM. Deja el descriptor en `PREPARED`. Tras el VSYNC,
`restore_dirty` restaura de delante hacia atrás y entra en `RESTORED`;
`draw_dirty` ordena establemente por `sort_y`, captura y dibuja de atrás hacia
delante, actualiza los campos anteriores y vuelve a `IDLE`. Los empates
conservan el orden del array. Llamar directamente a `restore_dirty` desde
`IDLE` sigue siendo compatible, pero ejecuta internamente la preparación y no
ofrece la ventana crítica corta.

Para cambiar fondo bajo sprites, marque primero un rectángulo de seis bytes
(`x dw`, `y dw`, `width_bytes db`, `height db`):

```asm
ld ix, #render_list
ld hl, #changed_rect
call fwk_entity_render_mark_rect_dirty
call fwk_entity_render_prepare_dirty
call fwk_system_wait_frame
call fwk_entity_render_restore_dirty
; redibujar tiles/HUD
ld ix, #render_list
call fwk_entity_render_draw_dirty
```

Desde `prepare_dirty` hasta `draw_dirty` no se pueden modificar el descriptor,
los bloques de render, sus flags ni el array auxiliar. Las identidades de los
punteros y los rangos de buffer se validan en `init`, fuera del frame. Si se
añade/reemplaza un puntero o cambia una dirección/capacidad, llame a
`fwk_entity_render_revalidate` en `IDLE` antes del siguiente `prepare_dirty`.
Para retirar una entidad: quite
`VISIBLE`, active `DIRTY`, complete el ciclo y solo después retire/reutilice el
puntero; revalide la lista si modifica el slot. Los slots de entidades con
`HAS_BACKGROUND` no pueden moverse.

El módulo no es reentrante ni desactiva interrupciones. Una ISR no puede llamar
al renderer, a las rutinas de sprites, modificar sus estructuras ni escribir
en las mismas zonas de VRAM.
