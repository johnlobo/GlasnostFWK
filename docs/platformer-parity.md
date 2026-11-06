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
4. **Rendimiento y cierre**: medir fotogramas por iteración y T-states por rutina
   en los dos juegos, fijar el presupuesto con esas cifras y cerrar la fase. Hecha
   (2026-11-06), ver abajo.

## Prueba diferencial, presupuesto y rendimiento (parte 4, cerrada 2026-11-06)

**Prueba diferencial.** Se hizo una vez con un arnés de usar y tirar (no está en el
repositorio: necesita el emulador y `platformer` desaparece en la fase 11). El mismo
guion de teclas aleatorio (con semilla) se aplicó a los dos juegos, inyectando el
estado de entrada justo tras `fwk_input_update` con el emulador pausado, y se
comparó en cada iteración el jugador (x, y, velocidades), los tres enemigos,
puntuación, vidas, victoria y nivel. Resultado: **idénticos en 300 iteraciones en
dos de las tres semillas**; la tercera mostró un desfase del propio arnés (leía dos
veces la misma parada del emulador), corregido sin repetir esa corrida. No apareció
ninguna divergencia de reglas entre los dos juegos.

Lo que sí destapó: un defecto del original, en `fwk_motion_u8_step`
(`src/extensions/motion_u8.s`). Tras sumar, miraba el signo del resultado, así que
toda posición `y >= 128` se tomaba por negativa y se ponía a 0. Los enemigos
verticales, que patrullan y=56..154, saltaban a y=0 al llegar a 128, y el de la
izquierda (x=8) se colaba en la zona del HUD. Eso explica los restos de `COINS:`
("ALL S:INS") vistos al forzar estados en la parte 2. `platformer_ecs` no lo tenía
(su movimiento satura con los límites del perfil). Corregido en la extensión, con
una comprobación en el smoke de `platformer` (los enemigos verticales recorren
y=56..140 o más) que falla con el código anterior (y 0..126).

**Medición** (`tools/measure_game.py`). Un punto de ruptura en la entrada de
`cpct_waitVSYNC_asm` y otro en su `ret` fijan, con el emulador pausado, el
fotograma y la posición del haz: T = fotogramas x 79.872 + (línea - 25) x 256 +
columna / 4 (error de unos 4 T). La salida de la espera cae en el VSYNC, así que
los fotogramas por iteración son enteros exactos. El trabajo incluye la
interrupción de 300 Hz, común a los dos juegos. 150 iteraciones por escenario, CPC
6128, teclas mantenidas:

| Escenario | Juego | Fotogramas/iteración | Trabajo medio (T) | Mediana | p95 | Máximo |
|---|---|---|---:|---:|---:|---:|
| reposo | `platformer` | 2 (149 de 149) | 139.821 | 140.084 | 141.088 | 143.588 |
| reposo | `platformer_ecs` | 2 (149 de 149) | 111.208 | 104.352 | 153.248 | 154.356 |
| derecha | `platformer` | 2,12 (131 de 2, 18 de 3) | 147.997 | 142.798 | 190.114 | 193.892 |
| derecha | `platformer_ecs` | 2 (149 de 149) | 114.756 | 105.912 | 154.588 | 161.652 |
| derecha + salto | `platformer` | 2,11 (132 de 2, 17 de 3) | 139.316 | 134.696 | 178.872 | 182.160 |
| derecha + salto | `platformer_ecs` | 2 (149 de 149) | 114.828 | 105.960 | 154.720 | 163.276 |

El port ECS trabaja un 18 a 22 % menos de media y nunca pasa de 2 fotogramas por
iteración; el original sube a 3 fotogramas en el 11 a 12 % de las iteraciones al
moverse. Reparto por rutina en reposo (T por iteración, `--routines profile`):
ECS: `prepare` 28.130, `restore` 17.350, `draw` 31.737, colisiones 11.518,
plataforma 4.415, animación 4.416 (3 llamadas), movimiento 3.880, comportamiento
4.735, entrada 1.592 + 996. Original: `prepare_dirty` 74.543 (el sistema más caro),
`restore` 9.631, `draw` 24.706, el resto de la lógica (con la entrada) unos 8.100.

**Presupuesto fijado** (con las cifras de arriba; se revisa si cambia el juego):

- Velocidad: `platformer_ecs` hace 2 fotogramas por iteración en los tres
  escenarios (ninguna iteración de 3) y su trabajo medio no supera el del
  original. Hoy: 111k a 115k T contra 139k a 148k T.
- Tamaño: BIN <= 5 % por encima de `platformer`. Hoy 11.861 B frente a 11.382 B
  (+4,2 %; código 9.502 contra 9.390, datos 2.359 contra 1.992).

**Decisión: no se optimiza `prepare`.** Con la medición, el renderer ECS ya es más
rápido que el original en conjunto y el presupuesto se cumple; el máximo de 154k a
163k T roza los 159.744 T de dos fotogramas pero el VSYNC absorbe esa variación
(ninguna iteración pasó de 2). Se reabre si un juego con más entidades pierde los
2 fotogramas.

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
| Fotogramas de animación | el sprite quieto no se redibuja | el sistema de animación marca `DIRTY` en cada cambio de frame, también con el jugador y los enemigos quietos | coste medido en la parte 4: dentro del presupuesto |
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
| Pasar de 3 a 4 monedas | el original dejaba restos de `COINS:` ("ALL S:INS") | texto limpio | causa hallada en la parte 4: el enemigo vertical izquierdo, enviado a y=0 por un defecto de `fwk_motion_u8_step`, pisaba el HUD. Corregido en el original; el dorado del estado de cuatro monedas es el del original desde un estado limpio |

Tamaño actual: 11.798 B de BIN (código 9.453 + datos 2.345) frente a 11.382 B
(9.390 + 1.992) del original, con HUD y texto pero sin nivel 2. El port ECS ya es
416 B mayor y aún le falta el nivel 2: el presupuesto de bytes y su reducción
(los dos juegos usan el mismo módulo de texto; de dónde sale el resto, por
ejemplo managers, renderer ECS o tablas de filas) queda dentro del presupuesto de la parte 4.

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
