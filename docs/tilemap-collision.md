# Tilemaps y colisión de escenario

Fecha: 2026-10-26 UTC.

Esta extensión separa tres responsabilidades: el consumidor conserva los datos
del mapa, `tilemap` traduce una coordenada de mundo a un tipo de colisión y
`platform_tilemap` corrige el estado producido por `physics_platform`. No hay
entidad universal, render de mapa, habitaciones, portales ni reglas de juego.

## Descriptor y consulta

Incluya `extensions/tilemap.inc` y declare un descriptor de 11 bytes:

```asm
tile_types: .db FWK_TILE_PASSABLE, FWK_TILE_SOLID, FWK_TILE_ONE_WAY
tile_data:  .db 0, 1, 0, 2

FWK_TILEMAP_DESCRIPTOR level_map, tile_data, tile_types, 4, 1, 2, 3, 4, 8, 3
```

Los campos son puntero a datos, puntero a tabla de tipos, ancho y alto en
tiles, desplazamientos X/Y, tamaños X/Y y número de entradas de la tabla de
tipos. Los datos son índices de 8 bits en orden de filas. Los tamaños deben ser
potencias de dos coherentes con sus desplazamientos (`4` con shift `2`, `8`
con shift `3`); esa coherencia es responsabilidad del consumidor.

`fwk_tilemap_query` recibe `IX=descriptor`, `B=Y` y `C=X`. Devuelve en `A` el
tipo del tile y carry limpio. Para coordenadas fuera del mapa, descriptor
inválido o id fuera de la tabla devuelve `A=0` y carry activo. Preserva
`BC,IX,IY`, altera `AF,DE,HL` y no escribe en el mapa.

## Resolver un cuerpo de plataforma

Seleccione juntos `extensions/physics_platform.s`, `extensions/tilemap.s` y
`extensions/platform_tilemap.s`:

```asm
ld iy, #player_state
ld ix, #physics_config
call fwk_physics_platform_step

ld ix, #level_map
call fwk_platform_tilemap_resolve
; A = máscara FWK_PLATFORM_HIT_*
```

La segunda llamada debe hacerse inmediatamente después de la primera: usa la
velocidad actual para reconstruir la posición vertical anterior. Los tiles
sólidos bloquean izquierda, derecha, techo y suelo. Los tiles de una dirección
dejan pasar al subir y solo sostienen o bloquean un cruce descendente. El bit
`FWK_PLATFORM_TILE_GROUNDED` distingue ese apoyo del suelo global del perfil.

La máscara devuelta puede combinar `FWK_PLATFORM_HIT_LEFT`,
`FWK_PLATFORM_HIT_RIGHT`, `FWK_PLATFORM_HIT_CEILING`,
`FWK_PLATFORM_HIT_FLOOR` y `FWK_PLATFORM_SUPPORT_LOST`. Una consulta inválida
o fuera de mapa se trata como espacio transitable.

## Límites confirmados

- Las coordenadas, dimensiones y tamaños del mundo son de 8 bits.
- Ancho, alto, tamaños y tabla de tipos deben ser no nulos; los shifts son
  menores que ocho. No se verifica que tamaño y shift sean coherentes.
- La velocidad por paso no debe atravesar un tile completo en el eje
  correspondiente; no hay barrido continuo ni subdivisión automática.
- Solo se consultan las esquinas del rectángulo. No hay pendientes ni formas
  distintas de sólido, pasable y plataforma de una dirección.
- El mapa es de solo lectura y no se dibuja. Render, edición, streaming y
  animación de tiles pertenecen al consumidor o a una extensión posterior.
- La colisión entre entidades o bolas y la física 8.8 no forman parte de este
  contrato.

`examples/tilecoll` recorre automáticamente un escenario sintético: golpea
techo, pared derecha y suelo, dibuja geometría cian y trayectoria amarilla y
deja un estado exacto que comprueba el smoke de emulador.
