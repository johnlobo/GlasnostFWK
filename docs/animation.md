# Animación reutilizable

`src/extensions/animation.s` implementa un cursor de animación en bucle. Parte
del descriptor y temporizador de `model01`, pero no conoce entidades,
habitaciones, velocidad, sprites ni vídeo. La máquina de estados de impactos de
DeckTower tiene semántica de combate y no se ha presentado como API genérica.

## Descriptor y estado

Un descriptor persistente contiene:

```asm
.db frame_count       ; 1..255
.db duration          ; llamadas a tick por frame, 1..255
.dw frame0, frame1    ; punteros; tantos como frame_count
```

Cada reproducción requiere cuatro bytes mutables propiedad del consumidor:
puntero al descriptor, índice y ticks restantes. Los descriptores y sus frames
deben permanecer visibles en el mapeo de memoria activo.

- `fwk_anim_clear`: `IX=estado`; lo desactiva y devuelve `HL=0`, carry limpio.
- `fwk_anim_set`: `IX=estado`, `HL=descriptor|0`; aplica el primer frame al
  cambiar y devuelve carry activo. Repetir el mismo descriptor no reinicia el
  temporizador y devuelve carry limpio.
- `fwk_anim_tick`: `IX=estado`; devuelve en `HL` el puntero actual y carry
  activo únicamente cuando avanza. No consulta VSYNC.

Las tres rutinas alteran `AF,HL`; `set/tick` también pueden alterar `BC,DE`.
No son reentrantes sobre el mismo bloque de estado, pero varios estados son
independientes. `frame_count=0` o `duration=0` incumplen el contrato.

## Comprobación ejecutable

`examples/animation` usa tres frames de un byte y duración cuatro. Repite
`fwk_anim_set` antes de cada tick para demostrar que seleccionar el mismo
descriptor no lo reinicia. El propio Z80 marca error si dos cambios no quedan
separados por cuatro ticks.

El smoke de AmSpiriT espera cuatro periodos exactos, contrasta el frame con la
tabla, comprueba el byte en RAM de vídeo, deshabilita los ticks desde RAM y
verifica que índice, contador y dibujo se congelan; después reanuda el avance.
Esta secuencia pasó en CPC 6128 y CPC 464 emulados. No se ha medido aún el
coste en ciclos ni se ha validado en hardware real.
