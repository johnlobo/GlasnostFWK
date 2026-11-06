# Fase 10: paridad y rendimiento de `platformer_ecs`

Criterio de salida (G3 del plan maestro): `platformer_ecs` juega igual que
`platformer` y no es más lento ni más grande de forma injustificada.

## Contrato observable de `platformer` (lo que hay que igualar)

| Área | Comportamiento de referencia |
|---|---|
| Jugador | 8x8, arranca en (16, 184), vx ±2, salto vy -8 solo desde suelo, física `physics_platform` y resolución contra tilemap |
| Monedas | 4 (16,24), (56,24), (16,168), (56,168); 4x8; al solaparse con el jugador desaparecen y suben `score` |
| Enemigos | 3 de 4x8: H (patrulla x 32..54, y 122), V (x 64, y 56..152), V2 (x 8, y 56..152); programas `behavior` + movimiento `u8`; V2 se actualiza cada frame, H y V se alternan (uno por frame) |
| Contacto | solape jugador/enemigo en transición resta una vida (inicio 10); efecto de parpadeo al perder vida |
| Puerta | invisible hasta tener las 4 monedas; tocarla ganada reinicia monedas, puntuación, jugador y enemigos y carga el nivel 2 |
| Niveles | 2 mapas ZX7B, 20x25 tiles, el activo dibujado una vez |
| Animación | 2 frames de jugador y enemigos, cambio cada 8 frames |
| HUD | `COINS: n/4`, `LIFE: nn`, textos de pista y victoria, redibujo por celdas |
| Estado público | `platformer_status/score/lives/enemy_contacts` observables por el smoke |

## Rebanadas (un PR cada una, cada una con prueba diferencial)

1. **Entidades y reglas**: monedas, 3 enemigos, puerta, vidas y puntuación en
   ECS (colisión de fase 7, animación de fase 8, render de fase 9). Sin HUD.
2. **HUD y efectos**: texto, victoria, parpadeo al perder vida. Hecha (2026-11-06), ver abajo.
3. **Segundo nivel** y reinicio por puerta. Hecha (2026-11-06), ver abajo.
4. **Rendimiento**: medir fotogramas por iteración y T-states por sistema en
   `platformer` y `platformer_ecs`, y reducir el coste de `prepare` (puntero en
   vez de `call _ecsr_entry`).

## Prueba diferencial

**Estado: no existe todavía.** La rebanada 1 se entrega sin ella. Lo que sí hay
es el recorrido del smoke original repetido sobre `platformer_ecs`, con
aserciones de reglas (vidas iniciales, puerta oculta, victoria solo con 4
monedas, huecos de moneda liberados, límites de patrulla, animación, una vida por
contacto y por enemigo, enemigos inofensivos tras ganar, puerta). La prueba
diferencial real (el mismo guion de entradas en los dos juegos, comparando
jugador, puntuación, vidas, estado y enemigos fotograma a fotograma) se construye
en la rebanada 4, junto con el presupuesto. La comparación de VRAM completa
solo es exigible tras la rebanada 2.

## Presupuesto de tamaño y velocidad

Se fija antes de construir cada rebanada y se mide con 8 a 16 entidades:

- Código ECS añadido por la rebanada 1: por fijar tras medir el original (ver
  `docs/build-sizes.md`, fila `platformer`).
- Velocidad: `platformer_ecs` no baja de los fotogramas por iteración del
  original medidos con el mismo guion.

Referencia de tamaño: `platformer` ocupa 9.390 B de código y 1.992 de datos
(`docs/build-sizes.md`).

## Rebanada 1: hecha (2026-11-06)

`platformer_ecs` usa los **mismos assets** que `platformer`. La carpeta
`examples/platformer_ecs/assets/` es una copia con el manifiesto, la paleta, los
PNG y el TMX originales y la salida generada. El pipeline es el mismo
(`tools/import_assets.py`, conversión incremental por SHA-256, mapas ZX7B), y
`make` en el ejemplo convierte solo si cambió un asset. La copia es deliberada:
la fase 11 elimina `platformer`, y el ejemplo ECS debe quedarse con sus assets.

Cuatro managers: ítems (4 monedas y la puerta), rápido (jugador y el enemigo
vertical izquierdo, cada fotograma), y uno para el horizontal y otro para el
vertical derecho, que se alternan un fotograma cada uno como en el original
(la primera versión puso el vertical derecho en el rápido y iba al doble de
velocidad: lo halló el crítico en frío). Las entidades se crean desde una tabla de filas
(`PFE_ROW`), no con plantillas de 42 bytes escritas a mano.

Resultados medidos:

- El recorrido completo del smoke original (cuatro monedas, subida por las cinco
  plataformas, puerta) pasa en CPC 6128 y 464 con las mismas aserciones de resultado, pero
  **con tres teletransportes** (`write_ram`) donde el original camina con teclas
  (bajo la moneda inferior derecha y en los dos extremos de la plataforma
  superior), porque la latencia del emulador hacía caer al jugador por el borde.
  Las pruebas de contacto con enemigos también colocan al jugador con `write_ram`.
- Contacto con un enemigo quita exactamente una vida por contacto.
- Tamaño provisional: 9.343 B de BIN frente a 11.382 B del original, sin HUD ni
  segundo nivel todavía, así que la comparación no es aún válida.

### Divergencias frente al original (decididas y documentadas)

| Área | Original | ECS | Motivo |
|---|---|---|---|
| Hitbox de moneda | ventana de 8x8 | el sprite real de 4x8 | una sola anchura por entidad: la del sprite |
| Contacto entre enemigos | un bit por enemigo | un canal por enemigo (V2, H y V en pasos separados) | igual que el original |
| Parpadeo al perder vida | borde rojo 3 veces, bloqueante, antes de `prepare` y VSYNC | mismas constantes y espera; se ejecuta al final del fotograma, tras dibujar | el HUD se actualiza en ese punto; ver también la fila de varias pérdidas |
| Varias vidas perdidas en un fotograma | un parpadeo por vida | un solo parpadeo (el bit de parpadeo es una marca, no un contador); las vidas y el HUD sí restan todas | caso raro, no cubierto por el smoke |
| Puerta en el nivel 2 | se oculta y termina | igual: se oculta y `won` vuelve a 0, sin reiniciar | paridad |
| Fotogramas de animación | el sprite quieto no se redibuja | el sistema de animación marca `DIRTY` en cada cambio de frame, también con el jugador y los enemigos quietos | coste conocido, a medir en la rebanada 4 |
| Arranque del jugador | `GROUNDED` | `AIRBORNE` en (16, 184), aterriza en el primer fotograma | la física solo aplica gravedad a cuerpos en el aire; un salto en el fotograma 0 se ignora |
| Orden de dibujado en empate | puerta y monedas sobre el jugador | el jugador sobre ellas; H después de V | desempate por orden de managers y slot |
| Estado público | `platformer_status` 0x5A = ganado | `platformer_ecs_status` 0x5A = inicializado; `platformer_ecs_won` marca la victoria | el smoke ECS ya usaba 0x5A para el arranque |
| Contador de contactos | `platformer_enemy_contacts` | sin equivalente | el canal de contacto vive en `ECS_E_COLLISION_CONTACT` |
| Mapa 2 | se descomprime al arrancar | se descomprime al tocar la puerta del nivel 1 | mismo resultado y misma RAM; el arranque es más corto |

## Rebanada 2: hecha (2026-11-06)

`platformer_ecs` dibuja el HUD del original con el módulo `ui/text.s` (añadido
a `example.json` junto con `"transparency": {"pen": 0}`, que el texto exige):
`COINS: n/4` (o `ALL COINS` con cuatro), `COLLECT ALL COINS` (o `GO TO THE DOOR`
tras ganar) y `LIFE: nn`. Perder una vida parpadea el borde en rojo tres veces
(pen 16, 0x1C y 0x14, espera de 0x1000 vueltas), como el original.

Diseño: un bit de suciedad por campo en `platformer_ecs_hud_dirty` (puntuación,
vidas, pista, parpadeo), activado por las reglas (callbacks de colisión y
`_pfe_apply_events`) y consumido por `_pfe_hud_update` después del dibujado. Una
sola rutina (`_pfe_hud_field`) restaura las celdas del mapa bajo el texto y lo
dibuja; las tres rutinas de campo solo eligen cadena y columnas.

Pruebas:

- **Píxeles contra el original.** `tests/emulator_smoke.py` guarda el SHA-256 de
  los campos de HUD (puntuación, pista, vidas 0..10) tal y como los dibuja
  `platformer` en el emulador, y `platformer_ecs` debe producir los mismos
  píxeles al inicio, con dos monedas, con cuatro, con cada valor de vidas de 10
  a 0 (forzado con `write_ram`) y tras cada contacto con un enemigo. El HUD inicial es idéntico byte a byte (1.280 bytes de VRAM).
- **Parpadeo observado** en el emulador (`border_idx` 0x1C durante el contacto,
  0x14 al terminar) en cada uno de los tres enemigos.
- **Prueba host** (`test_platformer_ecs_hud_and_flash_match_the_original`):
  textos, posiciones, columnas de campo y constantes del parpadeo iguales a las
  del original, leídas de su fuente.

Divergencias de esta rebanada:

| Área | Original | ECS | Motivo |
|---|---|---|---|
| Cambio de puntuación | restaura 2 celdas y redibuja un dígito | restaura y redibuja el campo entero (5 celdas, 10 glifos) | menos código; mismos píxeles finales, algo más de tiempo en el fotograma del evento |
| Vidas tras ganar | `_pf_update_hud` salta el campo de vidas con el estado `WON` | se actualiza siempre | en el original los enemigos no restan tras ganar; aquí, en el nivel 2 tras ganar y tocar la puerta final, los enemigos vuelven a restar (el original también deja de bloquearlos: pone el estado en `READY`) |
| Pasar de 3 a 4 monedas | observado: tras forzar los estados con `write_ram` el original dejó restos de `COINS:` ("ALL S:INS") | texto limpio | no investigado; el dorado del estado de cuatro monedas es el del original desde un estado limpio (0 a 4) |

Tamaño actual: 11.798 B de BIN (código 9.453 + datos 2.345) frente a 11.382 B
(9.390 + 1.992) del original, con HUD y texto pero sin nivel 2. El port ECS ya es
416 B mayor y aún le falta el nivel 2: el presupuesto de bytes y su reducción
(los dos juegos usan el mismo módulo de texto; de dónde sale el resto, por
ejemplo managers, renderer ECS o tablas de filas, está por medir) se fijan y atacan en la rebanada 4.

## Parte 3: hecha (2026-11-06)

Al tocar la puerta del nivel 1, `platformer_ecs` pasa al nivel 2 y reinicia como
el original: monedas, puntuación, `won`, jugador, enemigos y HUD, con el mapa 2
dibujado y las vidas conservadas. En el nivel 2 la puerta solo se oculta.

Diseño: el arranque del juego es ahora `_pfe_start_level` (dibuja el mapa y el
HUD, reinicia los cuatro managers y crea todas las entidades desde la tabla de
filas). El arranque y la puerta la llaman: el nivel 2 empieza en el mismo estado
que el 1 por construcción, sin una segunda lista de reinicios que mantener. La
puerta descomprime el mapa 2, cambia `_pfe_map_desc` (que usan la física del
jugador y la restauración del HUD) y vuelve a llamarla. Ambos mapas miden 20x25,
así que sirven la misma vista (lo comprueba una prueba host).

Presupuesto fijado antes de escribir: BIN <= 11.798 + 80 = 11.878 B. Resultado:
11.861 B (código 9.502, datos 2.359), 63 B más que la parte 2.

Pruebas:

- **Píxeles contra el original en los dos niveles.** Cuatro bandas de pantalla
  que ninguna entidad cruza se comparan por SHA-256 con las que dibuja
  `platformer` (nivel 1 al arrancar, nivel 2 tras la puerta, llevada con
  `write_ram`). Los ocho hashes difieren entre niveles.
- **Mapa 2 en RAM** igual a la capa `level2` del TMX, leída por el smoke con su
  propio lector (independiente de la tubería de assets).
- **Reinicio**: con 7 vidas fijadas antes de la puerta, el nivel 2 las conserva
  (RAM y HUD), puntuación y `won` a 0, puerta oculta, cuatro monedas recreadas,
  mismos slots de jugador y enemigos, HUD inicial, jugador exactamente en (16, 184)
  y enemigos en su inicio (cotas de posición).
- **Física del mapa 2**: desde (48, 40) el jugador aterriza en y=88 (en el mapa 1
  se pararía en y=56).
- **Victoria del nivel 2**: cuatro monedas, aparece la puerta, la puerta la oculta
  sin reiniciar (puntuación 4 y huecos de moneda libres).
- **Prueba host**: ambos mapas del mismo tamaño, el arranque y la puerta llaman a
  la misma rutina, ningún `ld` a las vidas en la ruta de la puerta ni en el arranque,
  los reinicios de estado son ceros puros, la física y el HUD siguen el mapa activo.
  Es textual: lo que cubre el comportamiento es el smoke.
- Tres corridas seguidas del smoke final en CPC 6128 y una en 464 (seis seguidas antes del último ajuste del orden de comprobaciones).

Divergencias:

| Área | Original | ECS | Motivo |
|---|---|---|---|
| Vidas en el HUD tras la puerta | redibuja la cadena fija `LIFE: 10` (`_pf_draw_hud_initial`), aunque las vidas reales sean otras | muestra las vidas reales | defecto del original (comprobado en el emulador: con 7 vidas la RAM dice 7 y la pantalla 10); el smoke lo fija con 7 vidas antes de la puerta |
| Descompresión del mapa 2 | al arrancar | al tocar la puerta del nivel 1 | mismo resultado y misma RAM; el arranque es más corto |

Limitación de las pruebas: la restauración del HUD con el mapa activo no se puede
distinguir por píxeles (las filas 1 y 2 son idénticas en los dos mapas); solo la
cubre la prueba host textual. Observación del original: tras el cambio de nivel el original no
borra los fondos capturados por el renderer, que proceden del mapa 1; no se
investigó si deja restos. En `platformer_ecs` las entidades se recrean, así que no
hay fondos viejos.

### Defecto de paridad corregido en el núcleo

`core/ecs_input.s` activaba `AIRBORNE` al saltar, así que la gravedad actuaba
antes del primer movimiento y el salto subía 28 píxeles en lugar de 36. Con esa
altura el jugador no alcanzaba la plataforma de y=152. Ahora el sistema de
entrada solo pone la velocidad y deja que la física haga el resto, igual que el
original.
