# Fase 10: paridad y rendimiento de `platformer_ecs`

Criterio de salida (G3 del plan maestro): `platformer_ecs` juega igual que
`platformer` y no es más lento ni más grande de forma injustificada.

## Contrato observable de `platformer` (lo que hay que igualar)

| Área | Comportamiento de referencia |
|---|---|
| Jugador | 8x8, arranca en (16, 184), vx ±2, salto vy -8 solo desde suelo, física `physics_platform` y resolución contra tilemap |
| Monedas | 4 (16,24), (56,24), (16,168), (56,168); 4x8; al solaparse con el jugador desaparecen y suben `score` |
| Enemigos | 3 de 4x8: H (patrulla x 32..54, y 122), V (x 64, y 56..152), V2 (x 8, y 56..152); programas `behavior` + movimiento `u8`; el H se actualiza cada dos frames |
| Contacto | solape jugador/enemigo en transición resta una vida (inicio 10); efecto de parpadeo al perder vida |
| Puerta | invisible hasta tener las 4 monedas; tocarla ganada reinicia/avanza de nivel |
| Niveles | 2 mapas ZX7B, 20x25 tiles, el activo dibujado una vez |
| Animación | 2 frames de jugador y enemigos, cambio cada 8 frames |
| HUD | `COINS: n/4`, `LIFE: nn`, textos de pista y victoria, redibujo por celdas |
| Estado público | `platformer_status/score/lives/enemy_contacts` observables por el smoke |

## Rebanadas (un PR cada una, cada una con prueba diferencial)

1. **Entidades y reglas**: monedas, 3 enemigos, puerta, vidas y puntuación en
   ECS (colisión de fase 7, animación de fase 8, render de fase 9). Sin HUD.
2. **HUD y efectos**: texto, victoria, parpadeo al perder vida.
3. **Segundo nivel** y reinicio por puerta.
4. **Rendimiento**: medir fotogramas por iteración y T-states por sistema en
   `platformer` y `platformer_ecs`, y reducir el coste de `prepare` (puntero en
   vez de `call _ecsr_entry`).

## Prueba diferencial

Un guion fijo de entradas (misma secuencia de teclas por fotograma) se ejecuta
en los dos juegos y se compara, fotograma a fotograma, jugador (x, y), puntuación,
vidas, estado y enemigos. La divergencia de cualquier campo falla la prueba. La
comparación de VRAM completa solo es exigible tras la rebanada 2.

## Presupuesto de tamaño y velocidad

Se fija antes de construir cada rebanada y se mide con 8 a 16 entidades:

- Código ECS añadido por la rebanada 1: por fijar tras medir el original (ver
  `docs/build-sizes.md`, fila `platformer`).
- Velocidad: `platformer_ecs` no baja de los fotogramas por iteración del
  original medidos con el mismo guion.

Referencia de tamaño: `platformer` ocupa 9.390 B de código y 1.992 de datos
(`docs/build-sizes.md`).
