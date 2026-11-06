# Estado de validación

Fecha: 2026-11-04 UTC.

## Implementado

- Núcleo de IRQ/VSYNC, entrada con estado/flancos y pool genérico.
- Vídeo Mode 0 generado, CRTC explícito, tabla 16-bit y limpieza de regiones.
- Texto Mode 0 mediante sprites recoloreables de 2x9, números pequeños de 2x5,
  audio AKG con música/SFX, copia bancaria 128 KB, lectura AMSDOS
  y descompresión ZX7B opcionales.
- Cursor de animación opcional, independiente de entidad, render y política de
  juego.
- Física de plataforma con velocidad byte, gravedad, límites y aterrizaje; e
  integrador 8.8 separado con fricción vectorial y rebote.
- Consulta row-major de tilemap de solo lectura y resolución opcional de
  sólidos/plataformas de una dirección para el perfil de plataforma.
- Render de tilemap Mode 0 con geometrías nativas 2x4/2x8/4x4/4x8, primitivas
  alineadas de CPCTelera Next, cámara, prevalidación completa y actualización
  parcial explícita de una celda; la variante transparente usa el color clave
  configurado para el proyecto.
- Sprites rectangulares Mode 0 con coordenadas de 16 bits con signo, clipping
  por los cuatro bordes y captura/restauración del fondo visible.
- Dibujo transparente opcional sobre el mismo descriptor, con pen Mode 0
  configurable, tabla implícita en `0x0100` y validación del span fuente.
- Lote opcional de sprites con inserción estable por clave, restauración
  inversa y captura/dibujo directo para solapamientos; el lote usa el camino
  opaco y no integra todavía la máscara.
- Ventanas opcionales con validación, captura, borde/relleno y restauración;
  texto, entrada y cierre permanecen en el consumidor.
- Generadores de vídeo/recursos y veintitrés ejemplos, incluidas dos escenas jugables.
- Entity manager ECS con slots estables, copia de plantillas, lifecycle diferido,
  máscaras de 16 bits, locks, recorrido por máscara y recolección.
- Frontera de dependencias y exclusión física de módulos.
- Inicialización generada por proyecto: código en `0x0200`, o en `0x0216` al
  activar memoria extendida para reservar el stub de bancos en `0x0200`.
- Manual HTML/PDF en castellano con cobertura automática de todos los ejemplos
  y módulos seleccionados.

## Validación de sistemas ECS de behavior y movimiento, fase 4

- El catálogo ECS define `MOTION` (`velocity_x`, `velocity_y`, `flags`) y
  `BEHAVIOR` (`program`, `timer`, `state`), con dependencia `BEHAVIOR -> MOTION`.
- `core/ecs_behavior.s` adapta el intérprete de behavior existente mediante un
  registro temporal privado; `core/ecs_motion.s` integra velocidades `u8` con
  saturación al perfil de vídeo y marca render dirty.
- `ecsmanager` selecciona ambos componentes, ejecuta cuatro ciclos behavior ->
  movimiento y comprueba la posición y velocidad generadas.
- Se corrigió el staging para invalidar objetos CPCTelera cuando cambia el
  perfil ECS; sin esta invalidación el build podía enlazar un layout anterior.
- Smoke focalizado correcto en AmSpiriT-Lite 1.15.3/CPC 6128 después de
  reconstruir los objetos con el perfil de 32 bytes.
- `make test` pasó 125 pruebas host, construyó 23 BIN y 22 CDT y generó el DSK
  común con 25 entradas. `ecsmanager` ocupa 1.973 bytes enlazados.

- La implementación se publicó como
  `6bf71a011a9b4f065437f20ca6d74be02c80b50a`. La CI manual
  `41807544677` terminó correctamente en 17 segundos y publicó el artefacto
  temporal `glasnostfwk-6bf71a...` (ID `13309469104`, 114053 bytes).
- No se ejecutó CPC 464 ni hardware real: el sistema actual exige coordenadas
  `u8` y no cambia el modelo de bancos, CRTC ni loader.

## Validación del generador de perfiles ECS, fase 3 (2026-11-04)

- `make test` pasó 123 pruebas host, construyó 23 BIN y 22 CDT y generó el DSK
  común con 25 entradas.
- Las pruebas específicas cubrieron generación determinista, orden e inserción
  de dependencias, formatos de coordenadas y velocidades, rechazos del
  manifiesto, detección de include obsoleto, diferencias de layout y preview
  sin escritura.
- El perfil generado de `ecsmanager` conserva el layout ejecutable anterior de
  25 bytes y la máscara válida `0x0003`; ya no existe el fixture manual como
  entrada de configuración.
- Después de la reconstrucción global, el smoke focalizado de `ecsmanager`
  volvió a pasar en AmSpiriT-Lite 1.15.3/CPC 6128 y confirmó que el programa
  ejecuta y avanza frames.
- No se ejecutó CPC 464: el generador solo se ejecuta en el host y su salida
  conserva el layout ya validado. No se probó hardware real.
- El catálogo contiene únicamente `render`, porque es el único componente con
  layout normativo aprobado. `behavior` y movimiento se especificarán en la
  fase 4.
- La implementación se publicó como
  `6127a2ba4e553be8a22b13779596d242fc434bb8`. La CI manual
  `41802820638` terminó correctamente y publicó el artefacto temporal
  `glasnostfwk-6127a2ba...` (ID `13308661285`, 113.077 bytes).

## Validación del entity manager ECS, fase 2 (2026-11-03)

- La regresión local `make test` pasó 114 pruebas host, construyó 23 BIN y 22
  CDT y generó el DSK común con 25 entradas. La CI final añadió la prueba del
  listado explícito de artefactos y pasó 115 pruebas.
- `ecsmanager` ejecutó en AmSpiriT-Lite 1.15.3/CPC 6128 desde el DSK común. El
  smoke leyó la RAM y confirmó tres slots estables `ACTIVE`, máscara `0x0003`,
  contadores `ACTIVE/LIVE=3/3`, lock liberado y `DIRTY` tras reactivar.
- El recorrido ejecutable cubrió filtro por máscara, destrucción permitida
  durante callback, rechazo de mutación estructural bajo lock, recolección y
  reutilización del primer slot. También cubrió máscara fuera del perfil,
  retirada insegura de render y normalización de aborto de callback.
- El BIN enlazado mide 1.483 bytes: 1.366 de código y 117 de datos. Carga en
  `0x0200` y ejecuta en `0x022F`.
- No se ejecutó CPC 464 porque esta fase no cambia código dependiente del
  modelo, bancos, CRTC ni representación de vídeo. No se probó hardware real.
- La CI manual `41630455820` terminó correctamente para
  `7d209340fadbd32ddefd3f051b953db46b164775` y publicó 46 archivos en el
  artefacto temporal `glasnostfwk-7d209340...` (ID `13227278502`).

## Validación de configuración inicial (2026-10-29)

- `make test` pasó 71 pruebas host, construyó 22 BIN, 21 CDT y el DSK común de
  24 entradas.
- Los proyectos normales enlazaron desde `0x0200`; `resources128`, con
  `extended_memory=true`, enlazó desde `0x0216`, añadió automáticamente
  `resources/bank.s` y superó la detección/copia bancaria en AmSpiriT-Lite CPC
  6128; el fallback pasó también en CPC 464.
- La sonda fija `0x7FF0` fue retirada tras contrastarla con DeckTower. La nueva
  detección usa temporalmente `0x4000` bajo `DI` y restaura tanto RAM normal
  como banco 0.
- `spritemask` configuró el pen 3 y el smoke comparó los 256 bytes instalados en
  `0x0100` con la tabla generada, además de sus testigos VRAM y clipping.
- `board` verificó la tabla pen 0 y el texto; `tilemask` verificó el consumidor
  transparente de tilemaps. Los cuatro casos pasaron en CPC 6128.
- En un build sin transparencia (`spriteclip`) el símbolo
  `fwk_sprite_draw_masked` no aparece en el NOI. Las pruebas host cubren los 16
  pens y el rechazo de configuraciones inválidas.
- Manual y guía de plataformas HTML/PDF se regeneraron y sus checksums pasaron.

Las menciones posteriores a máscaras paralelas describen validaciones
históricas de la implementación sustituida y no constituyen el contrato actual.

## Validación de sprite transparente recoloreable (2026-10-29)

- `fwk_sprite_draw_masked_recolor` valida pens 0..15, conserva el descriptor y
  el clipping de cuatro bordes, sustituye un pen Mode 0 y compone después con
  el color clave configurado.
- Las pruebas host cubren reemplazo en los dos píxeles empaquetados, interacción
  entre recoloreado y transparencia y rechazo de pens inválidos.
- `spritemask` usa transparencia pen 3 y reemplaza pen 5 por pen 15 sobre fondo
  no uniforme. Los testigos exactos de VRAM pasaron en AmSpiriT-Lite 1.15.3
  para CPC 6128 y CPC 464.
- Se comprobó que un proyecto sin transparencia no exporta el nuevo símbolo.
- `make test` pasó 74 pruebas host, construyó 22 BIN, 21 CDT y el DSK común con
  24 entradas. `make manual` regeneró PDF y checksum correctamente.

No existe validación en hardware real y el coste temporal de la nueva ruta no
se ha medido todavía.

## Compilado

Los veintitrés ejemplos generan `.bin` con CPCTelera Next `11e61fe3…`/SDCC 4.5.0;
veintidós generan además `.cdt`. Sus veintitrés BIN y los dos payloads de
`diskload` se reúnen en un único `.build/tests/GlasnostFWK-tests.dsk` con 25
entradas; los DSK individuales intermedios se eliminan. `diskload` no genera CDT
porque sus payloads auxiliares no están en cinta. `docs/build-sizes.md` contiene
tamaños enlazados.

## Probado automáticamente

- Direcciones estándar conocidas, bordes y cruces de bloques.
- 23.040 direcciones únicas para 160x288 y cruce `0xBEB0 -> 0xC000`.
- Ocho huecos estándar fuera del conjunto visible.
- Generación determinista byte a byte.
- Rechazo de solapamientos, destinos reservados y bancos no disponibles.
- Ausencia de imports `src -> examples/game` y selección de módulos.
- Validación de fuentes de juego declaradas, existentes y sin recorridos inseguros.
- Construcción completa de los veintitrés ejemplos y validación de nombres 8.3,
  rutas locales y selección de medio para los archivos añadidos al DSK.
- Composición de máscara, offsets de clipping compartidos, preservación de un
  píxel Mode 0 con `0xF0`, span de máscara sin wrap y la invariante de datos cero
  bajo bits preservados.
- Validación de ventanas: geometría válida, ajuste exacto, límites exteriores y
  rechazo de `y+height` con desbordamiento de 16 bits.
- 58 pruebas host en total. Las pruebas específicas de texto verifican los 918
  bytes de los 51 glifos, los 100 bytes de los diez dígitos, la tabla de máscara
  de 256 bytes y la presencia de la API y el mapeo original. El manual cubre
  todos los ejemplos y módulos seleccionados; su checksum corresponde al HTML
  que generó el PDF vigente. Dos pruebas adicionales validan los enlaces, las
  cinco capturas PNG y el PDF de la guía específica de plataformas.

## Ejecutado en emulador

Ejecutado con AmSpiriT-Lite 1.15.3, CRTC 1:

- `board` instaló la tabla de transparencia exacta en `0x0100`, dibujó el título
  con los glifos normales y produjo en VRAM los bytes exactos de `7`, `42` y
  `255` con los números pequeños, además de un `8` con cada uno de los quince
  índices válidos de recoloreado. Pasó en CPC 6128 y CPC 464.

- Los veintidós programas arrancaron desde el único
  `GlasnostFWK-tests.dsk` en un CPC 6128 de 128 KB y superaron sus comprobaciones
  de estado y VRAM. `board` y `platformer` se repitieron además en CPC 464.
- `video` conservó el testigo `0xA5` en `0xC7D0` después de limpiar pantalla.
- `resources128` detectó 128 KB y recuperó `GLASNOST` tras el viaje
  RAM normal -> banco 0 -> RAM normal.
- `resources128` se repitió en CPC 464: reportó 64 KB y continuó por su ruta de
  fallback sin intentar el roundtrip.
- `diskload` se ejecutó desde el DSK común en CPC 6128 y CPC 464. En ambos leyó
  `RAWDATA.BIN` (256 B) y `PACKDATA.ZX7` (23 B), descomprimió el segundo a
  256 B y se compararon todos los bytes contra el testigo esperado.
- `audio` se ejecutó en CPC 6128 y CPC 464. En ambos se observó avance del
  player, volumen PSG musical no nulo, parada con los tres canales a volumen
  cero y contador inmóvil, reanudación del contador, y periodo/volumen no nulos
  en el canal B al disparar el SFX 3.
- `animation` recorrió tres frames sintéticos con una duración exacta de cuatro
  ticks, mantuvo su cursor al volver a seleccionar el mismo descriptor, se
  congeló al pausar el tick y continuó al reanudarlo. Pasó en CPC 6128 y CPC
  464, incluyendo la comprobación del byte dibujado en RAM de vídeo.
- `gravity` completó 48 pasos en CPC 6128 y CPC 464: terminó en
  `(x=76,y=192)`, apoyado, con ambas velocidades a cero y dimensiones `4x8`.
- `physics88` completó 64 pasos en CPC 6128 y CPC 464: posición final
  `(&0BDC,&75C0)`, velocidad `(&0100,&0080)` y resto de fricción cero.
- `tilecoll` completó 96 pasos en CPC 6128 y CPC 464: terminó en
  `(x=58,y=156)`, velocidades cero, dimensiones `2x4`, apoyado en tile y con
  máscara acumulada `0x0E` (derecha, techo y suelo). También se verificaron la
  paleta, el cuerpo final y testigos de techo, pared y suelo en VRAM.
- `tilerender` rechazó una celda exterior al viewport, dibujó la cámara inicial,
  cambió a `(2,1)` y restauró una celda dañada mediante una única actualización
  parcial. Se comprobaron el contador, cuatro patrones dentro del viewport y un
  testigo exterior en VRAM. Pasó en CPC 6128 y CPC 464 y su salida final se
  inspeccionó visualmente.
- `spriteclip` rechazó dimensión nula y span gráfico con wrap, aceptó sin
  escrituras un sprite totalmente exterior, recortó cada borde y capturó/restauró
  exactamente un fondo no uniforme de 4x5 bytes. Pasó en CPC 6128 y CPC 464;
  los sprites de borde y centro se inspeccionaron visualmente.
- `spritemask` rechazó un span de máscara con wrap, aceptó sin escrituras un
  sprite exterior, compuso una máscara paralela sobre bandas de fondo no
  uniformes y dibujó el mismo asset centrado y recortado arriba/izquierda. Se
  comprobaron estado y testigos VRAM en CPC 6128 y CPC 464.
- `renderorder` ordenó dos entradas dadas en orden inverso, dejó la clave mayor
  por encima, rechazó capacidad excedida y doble captura, restauró exactamente
  doce filas no uniformes, conservó una actualización de fondo entre pases y
  restauró la posición movida. Pasó en CPC 6128 y CPC 464 mediante testigos de
  estado, lote, flags y VRAM; no se registró una inspección visual separada.
- Tras reproducir una salida aparentemente vacía en `gravity`, se comprobó que
  la demo heredaba de BASIC fondo azul en el pen 0 y negro en el pen 5 usado por
  la traza. `gravity` fija ahora negro/amarillo y `physics88` negro/cian. El
  smoke verifica tanto los registros de paleta como el byte final en VRAM.
- `window` rechazó una geometría fuera de pantalla y un `y=0xFFFF` con alto 10
  que desbordaba la suma de 16 bits, capturó 320 bytes, dibujó borde/relleno sin
  tocar los testigos exteriores, restauró las 16 filas y volvió a abrirse. Pasó
  en CPC 6128 y CPC 464.
- `vertical` cargó jugador y tres coleccionables desde fuentes de recursos
  separadas. CursorRight se mantuvo mediante la matriz de teclado: el jugador
  recogió los tres, el pool (versión anterior, sin ECS) se compactó de cuatro
  registros a uno y se activó el estado de victoria. También se comprobaron en RAM de vídeo los bytes de
  jugador, coleccionables y victoria. La misma prueba pasó en CPC 6128 y CPC 464.
- `platformer`, ya migrado a `entity_render`, completó su recorrido jugable
  automatizado, recogió cuatro monedas y alcanzó la victoria en CPC 6128 y CPC
  464. Jugador y monedas usan prefijos de entidad, buffers propios, propagación
  dirty y orden por Y. La ruta prepara validación, solapamientos y orden antes
  del VSYNC, y mantiene consecutivas las escrituras de restauración/dibujo. Al
  cambiar el marcador, restauró dos celdas para el dígito o el tramo de estado;
  el smoke comparó el glifo intermedio con la fuente vigente y comprobó que las
  celdas de las monedas inferiores quedaron limpias. La ruta CPC 6128 produjo
  capturas PNG reales de la escena inicial y la victoria. La regresión de fase
  0 dejó de identificar frames de vídeo con iteraciones de juego: mantiene cada
  dirección hasta alcanzar una posición observable, con timeout y comprobación
  posterior del intervalo. Así conserva el recorrido funcional aunque el coste
  de render haga que una iteración abarque más de un frame. No se midieron
  ciclos ni hardware real.

La entrada está automatizada para `vertical` y `platformer`. `tilecoll`, `tilerender` y
`spriteclip` se inspeccionaron visualmente en emulador y su salida resultó
visible. No se validó
visualmente el perfil experimental 160x288 ni se capturó la salida analógica de
audio. Dos ejecuciones completas históricas expusieron carreras de observación en los
testigos finales de `animation` y `vertical`: ambos publican estado antes de
dibujar en ese mismo frame. El smoke espera ahora explícitamente el byte de
VRAM; las repeticiones aisladas ya habían pasado y la batería actual de
veintidós casos terminó en una sola ejecución correcta.

## Verificado en hardware

No verificado.

## Pendiente o bloqueado

- Ampliar las mediciones de `performance.md` a escenas completas; las nueve
  operaciones medidas no implican una promesa global de 50 Hz.
- Validar la temporización CRTC 160x288 en varios tipos CRTC y hardware. El
  modelo de memoria sí está probado; la señal de vídeo no.
- El tilemap continúa siendo de solo lectura. No hay edición, streaming,
  transparencia, scroll sub-tile ni dirty rectangles automáticos.
- `entity_render` sustituye al lote opaco: admite opaco, máscara, recoloreado y
  ambas opciones combinadas; valida capacidades y solapamiento de buffers
  activos. Sigue trabajando con rectángulos completos, capacidad fija aportada
  por el juego y sin mezcla alfa ni asignación dinámica.
- Ciclos del dibujo enmascarado medidos en `docs/performance.md` (6x8 ≈ 11022
  T-estados). No se promete 50 Hz para una escena arbitraria.
- Ampliar las pruebas Z80 más allá de los recorridos cubiertos actualmente:
  `vertical` prueba entrada, movimiento y recogida de entidades y `resources128`
  prueba detección/copia bancaria; las ramas de error de disco y los payloads
  ZX7B corruptos no están automatizados.

## Comandos reproducibles

La validación cotidiana se divide en niveles para evitar repetir la matriz
completa tras cada edición:

1. Durante el cambio: `make check CHECK_EXAMPLES="..."`, o el módulo unittest
   concreto mientras se depura.
2. Si cambió código Z80 ejecutado: un smoke del ejemplo afectado en CPC 6128.
   CPC 464 solo es obligatorio para cambios dependientes del modelo, bancos,
   memoria o para una release.
3. Al cerrar una tarea o antes del commit: una única ejecución de `make test`.
4. PDF, informe de tamaños, DSK global y matriz amplia de emulador se regeneran
   una vez al final, y no después de cada ajuste intermedio.

`make check` ejecuta todas las pruebas host, pero compila solo los nombres de
`CHECK_EXAMPLES` y no reemplaza el DSK común.

```sh
cd /config/workspace/GlasnostFWK
make check CHECK_EXAMPLES=platformer
make test
make report
python3 tests/emulator_smoke.py
python3 tests/emulator_smoke.py --model 464 resources128
python3 tests/emulator_smoke.py diskload
python3 tests/emulator_smoke.py --model 464 diskload
python3 tests/emulator_smoke.py audio
python3 tests/emulator_smoke.py --model 464 audio
python3 tests/emulator_smoke.py animation
python3 tests/emulator_smoke.py --model 464 animation
python3 tests/emulator_smoke.py gravity physics88
python3 tests/emulator_smoke.py --model 464 gravity physics88
python3 tests/emulator_smoke.py --model 464 tilecoll
python3 tests/emulator_smoke.py tilerender
python3 tests/emulator_smoke.py --model 464 tilerender
python3 tests/emulator_smoke.py spriteclip spritemask
python3 tests/emulator_smoke.py --model 464 spriteclip spritemask
python3 tests/emulator_smoke.py renderorder
python3 tests/emulator_smoke.py --model 464 renderorder
python3 tests/emulator_smoke.py window
python3 tests/emulator_smoke.py --model 464 window
python3 tests/emulator_smoke.py --model 464 vertical
```

### Fase 5 ECS: plataforma aislada

- `make test` pasó 125 pruebas host, construyó 24 BIN, 23 CDT y el DSK común
  con 26 entradas.
- `python3 tests/emulator_smoke.py platformer_ecs` pasó en AmSpiriT-Lite
  1.15.3/CPC 6128: el player y dos enemigos se crean como slots ECS, los
  sistemas behavior/motion avanzan los enemigos y el puente de render dibuja
  los sprites.
- La prueba es una integración vertical limitada: el ejemplo todavía
  renderiza todos los slots mediante un puente temporal, y no tiene input,
  física, tilemap ni colisiones ECS. Esas capacidades pertenecen a las fases
  6-9.

### Fase 6 ECS: adaptadores iniciales

- El perfil `platformer_ecs` incorpora `INPUT` y `PLATFORM`, con dependencias
  explícitas hacia `MOTION`.
- `core/ecs_input.s` adapta el estado global de entrada a velocidad y salto;
  `core/ecs_platform.s` adapta el estado de entidad al contrato legacy de
  física de plataforma y resolución contra tilemap.
- `platformer_ecs` renderiza un tilemap 20x25 mediante las primitivas
  CPCTelera Next y compila los dos nuevos sistemas dentro del BIN común.
- `make test` pasó 125 pruebas host, construyó 24 BIN, 23 CDT y el DSK común.
- El smoke inicial de ejecución y suelo no era fiable y ocultaba tres defectos
  (corregidos en el cierre de la fase 6):
  1. El bucle borra y redibuja la pantalla en cada iteración, de modo que una
     única lectura de vídeo casi siempre veía el fotograma borrado. El smoke
     sondea ahora hasta ver el suelo.
  2. El jugador nacía sin `AIRBORNE`, y `physics_platform` solo aplica
     gravedad a cuerpos aéreos: flotaba en y=80. Ahora nace aéreo.
  3. `ecs_motion.s` integraba también a las entidades `PLATFORM` (doble
     velocidad, atravesaba el suelo de 8 px) y detectaba desbordamiento por
     signo, poniendo a 0 cualquier coordenada mayor que 127. Ahora omite las
     entidades `PLATFORM` y satura por acarreo.
- Smoke CPC 6128 de cierre: el jugador cae desde y=80 y aterriza en y=184 con
  `vy=0` y `TILE_GROUNDED`, se mantiene estable, camina a derecha e izquierda
  y se detiene al soltar, salta y vuelve a aterrizar en y=184. Mutaciones
  comprobadas: con el nacimiento no aéreo o con el `ecs_motion.s` anterior el
  smoke falla en "landing on the floor".
- `ecsmanager` ejecuta ahora ocho casos límite de `fwk_ecs_system_motion_u8`
  (posiciones mayores que 127, saturación en ambos extremos, subdesbordamiento
  por eje y posiciones fuera de rango que retroceden). Con el `ecs_motion.s`
  anterior el smoke falla. El builder rechaza además `platform` con
  `core/ecs_motion.s` si falta `core/ecs_platform.s`.
- Observación de rendimiento (no corregida, fuera del alcance de la fase 6):
  el puente de render redibuja todo el tilemap en cada iteración y el bucle
  corre a unas 1,3 iteraciones por segundo (otras notas hablan de unos 19 fotogramas por
  iteración, que serían ~2,6; las dos cifras vienen de mediciones distintas y
  no se han reconciliado) en AmSpiriT-Lite. Los timeouts del
  smoke están dimensionados para ese ritmo.

### Fase 7 ECS: colisión entre entidades

- Diseño final (ABI 9 revisado el 2026-11-05): `fwk_ecs_collide` comprueba un
  sujeto contra los objetivos de un manager, con estado de contacto de un byte
  por entidad. Sin tabla de pares ni buffer de eventos.
- Tamaño medido en el `.rel`: unos 210 bytes de código y 7 de datos. Presupuesto
  vinculante 300 y 8, comprobado por `tests/test_ecs_collision.py`. Para
  comparar: AABB no ECS anterior unos 330 bytes; primer diseño fiel al ABI
  original unos 980; versión optimizada para 255+255 entidades unos 5.300.
- `examples/ecscollision`: escenario de 26 pasos generado desde
  `tools/ecs_collision_model.py`; el smoke compara el registro del emulador con
  el modelo byte a byte (ENTER, STAY, EXIT sin objetivo, máscara de componentes,
  contacto por borde, destrucción desde el callback, aborto del callback, EXIT
  fallido, manager bloqueado, callback nulo, dos canales independientes). CPC 6128 y CPC 464 correctos.
- El harness encontró un defecto real antes de publicar: con callback nulo,
  `fwk_ecs_system_run` solo valida el callback interno y la rutina saltaba a la
  dirección 0 (reinicio del equipo). Ahora devuelve `FWK_ECS_ERR_CALLBACK`.
- `ecs_manager.inc` solo declara los `.globl` de behavior y movimiento si el
  perfil incluye esos componentes; sin eso un proyecto sin ellos no enlazaba.
- Un crítico en frío encontró un fallo de diseño que el escenario no veía: con
  un único bit de estado por sujeto, probar monedas y enemigos en el mismo frame
  producía `EXIT` y `ENTER` falsos en cada frame (una vida perdida por frame).
  Ahora el llamante indica el canal (un bit de `ECS_E_COLLISION_CONTACT`) en `E`
  y el escenario incluye dos canales intercalados. También corregidos: el
  ejemplo del manual, la guarda de build para coordenadas no `u8` y los límites
  documentados (no reentrante, sujeto sin comprobar, `EXIT` tras destruir).
- Segundo crítico en frío: el código resiste (IX/IY, errores, canales); el
  único fallo era el ejemplo del manual, que destruía la moneda solo en
  `ENTER` y perdía una moneda nueva que llega como `STAY`. Corregido y fijado
  con tres pasos más del escenario; documentados: un solo bit en `E`, `CONTACT`
  a 0 en las plantillas y que cualquier llamada con error pisa el estado
  interno.

### Fase 8 ECS: animación

- `core/ecs_animation.s`: `fwk_ecs_system_animation` y `fwk_ecs_anim_set`, con
  el mismo descriptor que el animador no ECS (`count`, `duration`, punteros de
  frame). Tamaño medido en el `.rel`: 109 bytes de código y 0 de datos;
  presupuesto vinculante 150 y 0, comprobado por `tests/test_ecs_animation.py`.
- `examples/ecsanimation`: 14 pasos y cinco entidades generados desde
  `tools/ecs_animation_model.py`: cuenta atrás, avance y vuelta, duración 1,
  entidad sin descriptor, cambio de descriptor, descriptor ya activo a mitad de
  ciclo, parada con 0, un descriptor de 130 frames que cruza el frame 128 y una
  entidad copiada de una plantilla que ya trae el descriptor con temporizador 0,
  una animación de un solo frame y una entidad parada que se vuelve a elegir.
  El smoke compara frame, temporizador, sprite y `DIRTY` de cada entidad con el
  modelo byte a byte. CPC 6128 y CPC 464 correctos.
- Mutaciones, comprobadas a mano en el emulador y **no automatizadas**: frame
  sin vuelta, `DIRTY` sin marcar, reinicio al elegir el descriptor activo,
  temporizador sin recargar, índice de frame de 8 bits y descriptor con
  temporizador 0 tratado como activo; las seis hacen fallar el smoke. La del
  descriptor activo pasó inadvertida con el primer escenario (con duración 1
  reiniciar y continuar coinciden) y obligó a añadir un caso a mitad de ciclo.
- Un crítico en frío encontró dos defectos reales, ya corregidos: con `count`
  entre 129 y 255 el índice de frame desbordaba 8 bits y mostraba sprites
  equivocados en silencio (el animador no ECS tenía el mismo defecto y también
  se corrigió), y `fwk_ecs_anim_set` no arrancaba una entidad copiada de una
  plantilla con descriptor y temporizador 0. Documentados además el efecto del
  orden de llamadas sobre la duración del frame 0, el tamaño del sprite y los
  descriptores con `count` o `duration` cero.
- Regresión del animador no ECS: `examples/animation` comprueba al arrancar un
  descriptor de 130 frames (tras 128 ticks debe estar en el frame 128) y el
  smoke lo exige; con el índice de 8 bits anterior falla.

### Fase 9 ECS: renderer multi-manager

- `video/ecs_render.s`: `fwk_ecs_render_prepare`, `restore` y `draw` sobre una
  escena con varios managers y un único orden global por Y. Mide 1.139 bytes de
  código con transparencia apagada (1.150 con ella activa) y 31 de datos, frente a 2.078 y 43 del renderer no ECS
  (`video/entity_render.s`). Presupuesto vinculante 1.150 y 40, medido con transparencia activa y comprobado por
  `tests/test_ecs_render.py`. La cifra inicial de 900 fue una estimación previa a
  medir; se corrigió en el ABI diciéndolo. El crítico en frío halló empates de
  clave que dejaban fantasmas permanentes, cajas que desbordaban con sumas >255
  y una medición con transparencia apagada; el arreglo (índice de recogida como
  desempate y sumas saturadas) costó 40 bytes y el presupuesto pasó de 1.100 a
  1.150. Se redujo antes de 1.184 a 1.099 con
  cajas envolventes por entidad (el cierre de solapes pasa de cuatro
  comparaciones de rectángulos por par a una) y descriptores de sprite
  construidos con `ldi`.
- Oráculo independiente (`tools/ecs_render_model.py`): la imagen ideal de cada
  frame es el fondo con todas las entidades `ACTIVE` y `VISIBLE` dibujadas en
  orden estable por `Y + SORT_OFFSET_Y`. `examples/ecsrender` ejecuta 36 frames
  con 9 entidades en dos managers (movimientos, saltos, solapes con orden de Y
  distinto al de slot, un sort offset, ocultar y mostrar, deshabilitar y
  habilitar, destruir, recorte en los bordes derecho e inferior) y el smoke
  compara la VRAM completa de cada frame con la imagen ideal, byte a byte.
  Además comprueba `FWK_ECS_ERR_OVERFLOW` con un array de trabajo pequeño y
  `FWK_ECS_ERR_RENDER` con una llamada fuera de orden. CPC 6128 y CPC 464.
- Mutaciones, comprobadas a mano en el emulador y no automatizadas: sin cierre
  de solapes, dibujar sin ordenar, restaurar con la clave actual, rectángulo
  anterior sin actualizar y caja que ignora el rectángulo anterior; las cinco
  hacen fallar el smoke. La de "dibujar sin ordenar" pasó inadvertida con el
  primer escenario (casi nunca había solapes con orden de Y distinto al de slot)
  y obligó a añadir un tramo determinista de solapes, protegido ahora por una
  prueba.
- `platformer_ecs` deja el puente provisional (borrar y redibujar todo en cada
  iteración) y usa el renderer: el mapa se dibuja una vez y solo se tocan las
  entidades que cambian. El jugador aterriza en unos 1,5 s frente a unos 16 s
  (de unos 19 fotogramas por iteración a unos 2), y el smoke de caída, aterrizaje,
  caminar y saltar pasa igual.


## Fase 10: paridad y rendimiento de `platformer_ecs` (rebanada 1)

- `examples/platformer_ecs` usa una copia de los assets y del pipeline de
  `platformer` y reproduce su nivel con cuatro managers, cuatro monedas, tres
  enemigos con la misma cadencia (V2 cada fotograma; H y V alternados), puerta y
  vidas. Detalle, divergencias y lo que falta en `docs/platformer-parity.md`.
- Smoke (`tests/emulator_smoke.py`, sección `platformer_ecs`): recorrido de las
  cuatro monedas y cinco plataformas, victoria solo con cuatro monedas, huecos de
  moneda liberados, límites de patrulla y animación, enemigos inofensivos tras
  ganar, puerta y una vida por contacto y por enemigo. Pasa en CPC 6128 y 464.
  Usa `write_ram` para colocar al jugador en tres puntos del recorrido y en los
  contactos, por la latencia del emulador.
- Mutaciones a mano sobre `main.s` (seis, todas detectadas): puerta ignorada,
  victoria con 3 monedas, enemigo H inofensivo, sin `collect`, vidas iniciales y
  animación quitada. El crítico en frío había encontrado 13 de 19 mutaciones
  sin detectar antes de ampliar el smoke.
- Defecto del núcleo hallado por esta paridad: el salto de `core/ecs_input.s`
  subía 28 px en vez de 36. Cubierto por una prueba host y por el smoke.
- Pendiente: prueba diferencial entre los dos juegos,
  presupuesto de tamaño y velocidad y coste de `prepare` (4).

## Fase 10: paridad y rendimiento de `platformer_ecs` (rebanada 2)

- HUD y parpadeo del borde en `examples/platformer_ecs` con `ui/text.s`. Detalle
  y divergencias en `docs/platformer-parity.md`.
- Referencia de píxeles: el SHA-256 de cada campo de HUD (puntuación, pista,
  vidas 0..10) capturado de `platformer` en el emulador. El HUD inicial de ambos
  juegos es idéntico byte a byte. El smoke compara al inicio, con dos monedas,
  con cuatro y tras cada contacto con enemigo, y observa `border_idx` 0x1C
  durante el parpadeo y 0x14 al terminar. Pasa en CPC 6128 y 464.
- Prueba host nueva: textos, posiciones, columnas y constantes del parpadeo
  iguales a las del original, leídas de su fuente.
- El crítico en frío (primera ronda: FAIL) halló cuatro defectos de mayor
  gravedad: un solo destello pasaba las dos suites (la prueba host solo miraba la
  constante), sin la guarda de vidas a 0 las vidas daban la vuelta a 255, el
  documento afirmaba vidas 0..10 comparando solo 10 a 7, y en el fotograma de la
  última moneda un enemigo aún restaba una vida (el original gana primero).
  Corregidos con smoke y prueba host nuevos.
- Mutaciones a mano sobre `main.s` (siete detectadas por el smoke antes de la
  ronda del crítico: sin parpadeo, pista sin actualizar al ganar, dígitos de vida
  cambiados, dígito de puntuación sin parchear, borde que se queda rojo, vidas sin
  marcar, fila 2 sin restaurar) y las tres del crítico, repetidas tras los
  arreglos: un destello con `ld b, #1` (lo detecta solo la prueba host; el smoke
  no cuenta destellos porque el sondeo de la API no garantiza ver cada uno),
  guarda de vidas a 0 quitada (host y smoke) y guarda del fotograma de la
  última moneda quitada (host y smoke).
- Límite honesto: el dorado del estado de cuatro monedas viene del original
  desde un estado limpio; al forzar 3 a 4 con `write_ram` el original dejó
  restos de `COINS:`. No se investigó la causa.

## Fase 10: paridad y rendimiento de `platformer_ecs` (parte 3)

- Segundo nivel y reinicio por puerta en `examples/platformer_ecs`. Detalle en
  `docs/platformer-parity.md`.
- Smoke: píxeles de cuatro bandas de pantalla de ambos niveles contra el original
  (SHA-256 capturados en el emulador), mapa 2 en RAM contra el TMX, reinicio,
  física del mapa 2 y victoria del nivel 2. Tres corridas seguidas en CPC 6128 y
  una en 464. Dos fallos intermitentes del propio test se hallaron y arreglaron:
  el punto de espera sobre una moneda y una carrera al reescribir la posición del
  jugador tras la puerta.
- Mutaciones: `tools/mutate_platformer_ecs.py` reúne las 27 que se han ido
  probando a mano en las partes 1 a 3 (reglas, HUD, parpadeo, nivel 2) y las
  ejecuta contra la prueba host y el smoke (`--host-only` para la pasada rápida).
  Resultado: 27 detectadas (11 por la prueba host, 16 solo por el smoke). Una
  prueba (`tests/test_mutation_table.py`) comprueba que cada patrón sigue
  existiendo una vez en `main.s`.
- Crítico en frío de la parte 3 (primera ronda: FAIL). Halló: el original redibuja
  `LIFE: 10` fijo tras la puerta (divergencia deliberada, ahora fijada con 7 vidas
  en el smoke); "vidas conservadas" dependía de si un enemigo había golpeado antes
  (el smoke fuerza ahora 7 vidas); el reinicio de enemigos y de fase no se
  comprobaba (cotas de posición y prueba host de ceros puros); y las cifras de
  mutaciones no tenían artefacto (el script).
- Pendiente: ninguno de la fase 10; la parte 4 cierra con la medición y el presupuesto.

## Fase 10: paridad y rendimiento de `platformer_ecs` (parte 4)

- `tools/measure_game.py`: fotogramas por iteración y T-states por rutina con
  puntos de ruptura del emulador (sin tocar los juegos); `tests/test_measure_game.py`
  cubre el cálculo (resumen, fotogramas enteros, totales por rutina, lectura de
  etiquetas locales de los listados). Cifras en `docs/platformer-parity.md`.
- Defecto del original hallado y corregido: `fwk_motion_u8_step` trataba las
  posiciones `y >= 128` como negativas. La prueba del smoke de `platformer` falla
  con el código anterior (y 0..126) y pasa ahora. Afecta también a `vertical` y
  `platform`, cuyos smokes siguen pasando.
- Prueba diferencial, una sola vez y sin dejarla en el repositorio (necesita el
  emulador y `platformer` desaparece en la fase 11): idénticos en 300 iteraciones en
  dos semillas. Una tercera mostró un desfase del arnés, corregido y no repetido.
- No se probó `prepare` más allá de la medición: no se optimiza.

## Fase 11, parte A: `vertical` y `perf` en ECS

- `examples/vertical` corre sobre un manager ECS (movimiento y colisión) en lugar
  del pool. El smoke comprueba ahora las cuatro direcciones y la diagonal, que un
  paso por la fila contigua no recoge ni borra ningún punto, y la recogida exacta
  en su celda. Mutaciones a mano (puntuación sin contar, sin `collect`, jugador
  quieto, punto sin destruir, sin estado de victoria): detectadas. Sin cubrir: la
  rama de error de `_vertical_expect_ok`.
- `examples/perf`: la escena del lote de ocho usa `ecs_render` y para el programa
  con el código de error en `perf_status` si el renderer falla; `measure_perf.py`
  lo notifica. El crítico en frío (FAIL en la primera ronda) halló que la escena
  ignoraba los errores y que el smoke de `vertical` solo cubría CursorRight.

