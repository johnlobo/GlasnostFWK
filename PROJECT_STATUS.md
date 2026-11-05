# Estado del proyecto

Última actualización: 2026-11-04 UTC. Última versión publicada: `v0.2.0`.

Este archivo es el registro canónico recuperable entre sesiones. Debe
actualizarse en cada commit con cambios funcionales, de construcción o de
publicación.

El manual de usuario canónico está en `docs/manual.html` y su versión para
impresión en `docs/manual.pdf`. Toda funcionalidad nueva debe ampliar el HTML,
regenerar el PDF con `make manual` y superar las pruebas de cobertura y checksum.

## Estado confirmado

- Las nueve fases del encargo inicial están implementadas como primera versión
  utilizable: reconocimiento, arquitectura, núcleo, módulos, recursos,
  generadores, perfil experimental, ejemplos y documentación.
- Los veintitrés ejemplos construyen BIN con CPCTelera Next fijada en
  `11e61fe30175ad7b328de9bcd859c46fd61b26a5`; veintidós construyen además CDT
  y todos los BIN se reúnen en un único DSK de pruebas con 25 entradas.
- La suite host contiene 115 pruebas; el manual cubre todos los ejemplos y
  módulos seleccionados.
- Cada ejemplo se compila y ejecuta por separado desde su carpeta con
  `make`, `make run` y `make clean`, como un proyecto CPCtelera, sin copiar el
  framework fuera de `.build/`.
- `vertical` es la primera integración jugable. Está automatizada en CPC 6128
  y CPC 464 mediante AmSpiriT-Lite 1.15.3.
- El perfil estándar 160x200 está probado. El modelo de memoria 160x288 está
  probado, pero su temporización CRTC sigue siendo experimental.
- El repositorio público es `johnlobo/GlasnostFWK` y la rama principal es
  `main`.

## Fase completada: distribución v0.1.0

- [x] Empaquetador determinista para los BIN, CDT y DSK de los seis ejemplos.
- [x] Instrucciones de ejecución y manifiesto dentro del paquete.
- [x] `SHA256SUMS` para verificar la descarga.
- [x] Workflow que reconstruye desde el tag publicado y adjunta el paquete a
  una GitHub Release.
- [x] Pruebas locales completas: 14 pruebas, seis construcciones y paquete de
  20 archivos; checksum comprobado desde `dist/`.
- [x] Commit `d8ea9f6` y push en `main`; CI remota `40206661927` correcta.
- [x] GitHub Release pública `v0.1.0`, asociada exactamente a `d8ea9f6`.
- [x] Workflow de release `40206700297` correcto.
- [x] ZIP y `SHA256SUMS` descargados de la release y verificados de forma
  independiente. El ZIP contiene el manifiesto esperado y los 18 artefactos.

## Evidencia y comandos

```sh
make test
make release VERSION=0.1.0
(cd dist && sha256sum --check SHA256SUMS)
python3 tests/emulator_smoke.py vertical
python3 tests/emulator_smoke.py --model 464 vertical
```

El detalle de qué se ha implementado, compilado y ejecutado está en
`docs/validation.md`. Los tamaños enlazados están en `docs/build-sizes.md`.

Release: <https://github.com/johnlobo/GlasnostFWK/releases/tag/v0.1.0>

## Fase completada: distribución v0.2.0

- [x] Tag remoto `v0.2.0` asociado exactamente a `13312a6`.
- [x] GitHub Release pública, no borrador ni prerelease, publicada el
  2026-10-27: <https://github.com/johnlobo/GlasnostFWK/releases/tag/v0.2.0>.
- [x] CI remota `40427399657` y workflow de release `40427406803` correctos
  para el SHA completo `13312a6a3133b8c75ff7aee5ba9dc13caf9b3588`.

## Limitaciones confirmadas

- No existe verificación en hardware real.
- No se ha validado visualmente el perfil experimental 160x288 en varios CRTC.
- El tilemap es de solo lectura. Su render no incluye transparencia, clipping,
  scroll sub-tile, bancos ni dirty rectangles automáticos; la colisión no
  resuelve pendientes ni colisión entre cuerpos.
- `vertical` y `platformer` son escenas jugables; los demás ejemplos son
  pruebas técnicas. `diskload` se ejecuta solo desde el DSK común porque
  requiere dos payloads auxiliares.
- Los sprites enmascarados son una API separada del camino opaco y del lote
  ordenado. Su coste 6x8 está medido, pero no existe una promesa global de 50 Hz.

## Fase completada: carga desde disco y ZX7B

- [x] Backend AMSDOS separado de bancos, manifiestos y política de errores.
- [x] Archivos crudos o ZX7B añadidos al DSK desde `disk_files`, sin enlazarlos
  dentro del ejecutable.
- [x] Adaptador ZX7B opcional sobre la rutina de CPCTelera Next.
- [x] Ejemplo `diskload`: 256 B crudos y los mismos datos comprimidos a 23 B.
- [x] Los 256 B leídos y descomprimidos se verificaron en AmSpiriT-Lite 1.15.3
  tanto con CPC 6128 como con CPC 464.
- [x] Suite host: 19 pruebas; construcción completa: siete ejemplos.
- [x] CI construye y verifica explícitamente el compresor ZX7B incluso cuando
  restaura una caché anterior. La ejecución `40208485165` detectó esta omisión
  de CI después del primer push; el código y las pruebas host sí habían pasado.
- [x] Implementación publicada en `main` mediante `70efbb1` y corrección de CI
  `9ccf00e`; la ejecución remota `40208554369` terminó correctamente.

Comandos específicos:

```sh
python3 tests/emulator_smoke.py diskload
python3 tests/emulator_smoke.py --model 464 diskload
```

## Fase completada: audio AKG ejecutable

- [x] Adaptador conectado a la ABI real del player AKG de CPCTelera Next.
- [x] Player externo seleccionado mediante `cpct_modules`, sin incorporarlo a
  ejemplos que no usan audio.
- [x] Música y cinco SFX procedentes de recursos oficiales MIT de Arkos
  Tracker 3.7; licencia, hashes y generación documentados.
- [x] Contadores observables de ticks y solicitudes SFX.
- [x] Smoke de música, stop, restart y SFX contra registros PSG reales de
  AmSpiriT-Lite 1.15.3 en CPC 6128 y CPC 464.
- [x] Suite host: 19 pruebas; construcción completa: ocho ejemplos; paquete de
  prueba determinista: 25 entradas y checksum correcto.
- [x] Los ocho DSK pasaron la batería completa en CPC 6128; `audio` pasó además
  la misma comprobación específica en CPC 464.
- [x] Coste fijo documentado: 1.104 ciclos/frame de envolturas IRQ de CPCtelera
  más 187 ciclos del adaptador en el tick activo; coste AKG variable aún no
  medido y, por tanto, sin garantía de 50 Hz.
- [x] Implementación registrada en `fb19078` y estado persistido en `c881de3`;
  ambos sincronizados en `origin/main`.
- [x] CI remota `40210414557` correcta para `c881de3`: 19 pruebas, ocho
  construcciones, artefactos BIN/DSK y los siete CDT verificados y publicados
  como artefacto temporal del workflow.

Comandos específicos:

```sh
python3 tests/emulator_smoke.py audio
python3 tests/emulator_smoke.py --model 464 audio
```

## Fase completada: animación reutilizable

- [x] Se auditaron las cuatro bases reales. `model01` contiene un cursor de
  frames reutilizable, pero acoplado a entidad, sala, movimiento y render;
  `DeckTower` implementa una máquina de estados específica para impactos;
  `boop` y `PocketFever` no aportan un reproductor genérico equivalente.
- [x] `src/extensions/animation.s` conserva únicamente el cursor temporal:
  descriptor inmutable, estado de 4 bytes, cambio estable de descriptor y loop.
- [x] El llamador controla cuándo consume ticks, qué animación selecciona y
  cómo dibuja; no existe dependencia de VSYNC, entidades o formato de sprite.
- [x] `animation` recorre tres frames sintéticos cada cuatro ticks y demuestra
  selección idempotente, pausa y reanudación.
- [x] La prueba específica pasó en AmSpiriT-Lite 1.15.3 para CPC 6128 y CPC
  464, comprobando además el byte de frame en RAM de vídeo.
- [x] Suite local: 19 pruebas host, construcción de nueve BIN/DSK y ocho CDT,
  paquete determinista de 28 entradas y checksum correcto.
- [x] Los nueve DSK pasaron la batería completa en CPC 6128; `animation` pasó
  además su comprobación específica en CPC 464.
- [x] Implementación registrada en `7c21d3d`.
- [x] Estado registrado en `2a69a8a`; ambos commits están sincronizados en
  `origin/main`.
- [x] CI remota `40211091152` correcta para `2a69a8a`: 19 pruebas, nueve
  construcciones, artefactos BIN/DSK y los ocho CDT verificados y publicados
  como artefacto temporal del workflow.

Comandos específicos:

```sh
python3 tests/emulator_smoke.py animation
python3 tests/emulator_smoke.py --model 464 animation
```

## Fase completada: manual de usuario en castellano

- [x] Manual HTML autocontenido con instalación, construcción, manifiestos,
  contratos de los módulos seleccionables, perfiles, recursos, ejemplos,
  emulación, distribución, diagnóstico y mantenimiento.
- [x] PDF A4 de 16 páginas generado desde el mismo HTML mediante WeasyPrint
  70.0, con texto seleccionable, índice y numeración.
- [x] Dependencia de documentación fijada en `docs/requirements-manual.txt` y
  objetivo reproducible `make manual`.
- [x] `tests/test_manual.py` obliga a cubrir cada ejemplo y módulo seleccionado,
  valida el PDF y detecta un PDF desfasado mediante el hash del HTML.
- [x] Revisión visual de portada, referencia de API y página final; extracción
  de texto comprobada en las 16 páginas.
- [x] Suite local: 21 pruebas host y construcción completa de nueve ejemplos.
- [x] Implementación registrada en `fc5111e`.
- [x] Estado registrado en `795e981`; ambos commits están sincronizados en
  `origin/main`.
- [x] CI remota `40212147675` correcta para `795e981`: 21 pruebas, nueve
  construcciones y artefactos distributables verificados.

## Fase completada: ventanas y mensajes reutilizables

- [x] Auditoría de las cuatro implementaciones: todas capturan/restauran fondo
  y dibujan caja; DeckTower/PocketFever comparten trazado, mientras texto,
  espera, combate, temporización y ubicación del buffer divergen.
- [x] `src/ui/window.s` extrae solo descriptor geométrico, validación contra el
  perfil, captura a un buffer del consumidor, borde/relleno y restauración.
- [x] Coordenada vertical de 16 bits y consulta de dimensiones públicas de
  vídeo; no se fija `0xC000` ni una fórmula de scanlines estándar.
- [x] `window` demuestra rechazo fuera de límites, captura de 320 bytes,
  composición de texto, restauración y reapertura.
- [x] La prueba específica pasó en AmSpiriT-Lite 1.15.3 para CPC 6128 y CPC
  464, comprobando RAM de vídeo y testigos exteriores.
- [x] Manual ampliado y PDF de 17 páginas regenerado; cobertura automática de
  diez ejemplos y doce módulos seleccionados.
- [x] Suite local: 21 pruebas host, diez BIN/DSK, nueve CDT, paquete
  determinista de 31 entradas y checksum correcto.
- [x] Los diez DSK pasaron la batería completa en CPC 6128; `window` pasó además
  su comprobación específica en CPC 464.
- [x] Implementación registrada en `fc6d0a3`.
- [x] Estado registrado en `5d9277f`; ambos commits están sincronizados en
  `origin/main`.
- [x] CI remota `40212959229` correcta para `5d9277f`: 21 pruebas, diez
  construcciones, artefactos BIN/DSK y los nueve CDT verificados y publicados
  como artefacto temporal del workflow.

Comandos específicos:

```sh
python3 tests/emulator_smoke.py window
python3 tests/emulator_smoke.py --model 464 window
```

## Fase completada: DSK de pruebas unificado

- [x] `make examples` y `make test` generan un único
  `.build/tests/GlasnostFWK-tests.dsk` como salida de disco pública.
- [x] El catálogo contiene los diez BIN de ejemplo con nombres AMSDOS 8.3 y
  conserva las direcciones de carga y ejecución extraídas del build real.
- [x] El mismo DSK incluye `RAWDATA.BIN` y `PACKDATA.ZX7`, requeridos por
  `diskload`; su catálogo reproducible queda en `.build/tests/catalog.json`.
- [x] Los DSK individuales de CPCTelera se tratan como intermedios y se eliminan
  después de construir el disco común.
- [x] El smoke, CI y paquete de release consumen el DSK compartido; el ZIP pasa
  de 31 a 22 entradas: diez BIN, nueve CDT, un DSK, manifiesto e instrucciones.
- [x] Manual HTML/PDF y documentación de validación actualizados.
- [x] Suite local: 24 pruebas correctas; catálogo real: 12 entradas y
  exactamente un DSK final; paquete determinista de 22 entradas con checksum
  correcto.
- [x] Los diez programas pasaron el smoke completo desde el mismo DSK en CPC
  6128; `diskload` pasó además en CPC 464 desde ese medio común.
- [x] Implementación y validación local registradas en `4848af3`.
- [x] Estado persistente registrado en `c769815`; ambos commits están
  sincronizados en `origin/main`.
- [x] CI remota `40213858551` correcta para `c769815`: 24 pruebas, diez
  construcciones, exactamente un DSK común, nueve CDT y catálogo publicados
  como artefacto temporal del workflow.

## Fase completada: perfiles de física especializados

- [x] Auditoría contra fuentes reales: `model01` usa física de plataforma con
  bytes; `PocketFever` usa posiciones/velocidades 8.8 y fricción vectorial;
  `boop` y `DeckTower` no aportan otro integrador general equivalente.
- [x] `extensions/physics_platform` opera sobre un estado de siete bytes del
  consumidor y una configuración separada; aplica movimiento horizontal,
  gravedad, caída máxima, techo, suelo y estado aéreo.
- [x] `extensions/physics_8_8` opera sobre un estado independiente de nueve
  bytes; conserva el resto sub-LSB, aplica fricción en la dirección del vector
  e integra/rebota dentro de límites configurables.
- [x] No se creó una entidad universal ni dependencias con mapas, bolas, pools,
  sprites, render o reglas de juego.
- [x] `gravity` y `physics88` aportan recorridos ejecutables de 48 y 64 pasos;
  sus estados finales se contrastan con modelos host y se leen de la RAM Z80.
- [x] Suite local: 26 pruebas, doce BIN, once CDT, DSK común con 14 entradas y
  paquete determinista de 26 entradas con checksum correcto.
- [x] Los doce programas pasaron desde el mismo DSK en CPC 6128; los dos
  perfiles nuevos también pasaron con estado exacto en CPC 464.
- [x] Manual HTML/PDF, procedencia y límites actualizados.
- [x] Implementación registrada en `362d878` y estado persistente en
  `d3b9c98`; ambos commits están sincronizados en `origin/main`.
- [x] CI remota `40241297476` correcta para `d3b9c98`: 26 pruebas, doce
  construcciones, un DSK común con catálogo y once CDT publicados como
  artefacto temporal.

## Corrección posterior: visibilidad de las demos físicas

- [x] Reproducida en AmSpiriT-Lite la salida aparentemente vacía de `gravity`:
  la demo escribía `0xF0` en VRAM, pero el pen 5 heredado de BASIC era negro y
  el fondo del pen 0 era azul.
- [x] `gravity` fija negro/amarillo brillante y `physics88` negro/cian brillante
  sin imponer una paleta global al framework.
- [x] El smoke comprueba ahora estado físico, registros Gate Array y byte final
  en VRAM, cubriendo cálculo y visibilidad por separado.
- [x] Captura manual confirmada en AmSpiriT-Lite: `gravity` muestra la traza
  amarilla sobre negro; smoke exacto correcto en CPC 6128 y CPC 464 para
  `gravity` y `physics88`.
- [x] `make test`: 26 pruebas, doce construcciones y DSK común regenerado;
  manual HTML/PDF y checksum sincronizados, e informe de tamaños actualizado.
- [x] Corrección registrada en `aba05c9`; cierres de estado `08ade20` y
  `ea9da1f`, sincronizados en `origin/main`.
- [x] CI remota final `40242850476` correcta para `ea9da1f`: 26 pruebas, doce
  construcciones, un DSK común con catálogo y once CDT publicados como
  artefacto temporal.
- [x] Validación manual del usuario recibida el 2026-10-26: confirma que el DSK
  corregido funciona. No se especificaron emulador, modelo ni hardware, por lo
  que esta confirmación no se registra como prueba en hardware real.
- [x] Confirmación persistida en `25acf49`, sincronizada en `origin/main`; CI
  remota `40250484819` correcta para ese commit.

## Fase completada localmente: tilemaps y colisión de escenario

- [x] Auditoría de `model01`: se conservaron la consulta row-major y la tabla
  id -> tipo; se excluyeron habitaciones, entidades, portales, render y reglas.
- [x] `extensions/tilemap` ofrece una consulta de solo lectura con descriptor
  del consumidor, validación de límites e ids y resultado carry explícito.
- [x] `extensions/platform_tilemap` compone sólidos y plataformas de una
  dirección con `physics_platform`, devuelve máscara de contactos y detecta
  pérdida de apoyo sin mezclar el suelo global.
- [x] `tilecoll` recorre 96 pasos, golpea techo, pared derecha y suelo y dibuja
  geometría cian y trayectoria amarilla. Estado final exacto:
  `(58,156,0,0,2,4,FWK_PLATFORM_TILE_GROUNDED)`, máscara `0x0E`.
- [x] Cuatro pruebas host cubren consulta/límites, recorrido completo,
  plataforma de una dirección y pérdida de apoyo.
- [x] `make test`: 30 pruebas, trece BIN, doce CDT y DSK común con 15 entradas.
- [x] `make manual`: HTML, PDF y checksum sincronizados; cobertura de trece
  ejemplos y dieciséis módulos.
- [x] `make report` actualizado; paquete local `0.2.0` con 28 entradas y
  checksum correcto. Esto no publica una release.
- [x] `tilecoll` pasó estado, máscara, paleta y testigos VRAM en AmSpiriT-Lite
  1.15.3 para CPC 6128 y CPC 464; salida inspeccionada visualmente.
- [x] Dos baterías completas expusieron carreras en los testigos de render de
  `animation` y `vertical`: el estado final se publica antes del dibujo del
  mismo frame. Ambos casos pasaron aislados y el smoke espera ahora el byte de
  VRAM en vez de leerlo inmediatamente. La batería completa posterior pasó los
  trece casos en CPC 6128 en una sola ejecución.
- [x] Implementación y validación local registradas en `c29da93`.
- [x] Estado persistido en `5750a3c`; ambos commits están sincronizados en
  `origin/main`.
- [x] CI remota `40254093387` correcta para `5750a3c`: 30 pruebas, trece
  construcciones, un DSK común con catálogo y doce CDT verificados y publicados
  como artefacto temporal.

Límites de esa fase: coordenadas de 8 bits, tiles potencia de dos coherentes con
sus shifts y velocidad menor que un tile por paso. No hay barrido continuo,
edición, pendientes, habitaciones, portales ni colisión entre cuerpos. En ese
momento todavía no existía el render añadido en la fase posterior.

## Fase completada localmente: render de tilemaps

- [x] `extensions/tilemap_render` consume el descriptor de mapa de solo lectura
  y un descriptor de render de 10 bytes con tileset, cámara, destino y viewport.
- [x] `fwk_tilemap_render_view` prevalida geometría, rango del tileset e ids antes
  de la primera escritura y dibuja tiles Mode 0 rectangulares sin padding.
- [x] `fwk_tilemap_render_cell` actualiza una celda indicada por fila y columna
  relativas al viewport, sin imponer una política de dirty rectangles.
- [x] `tilerender` prueba cámara `(0,0) -> (2,1)`, rechazo de coordenada exterior,
  daño deliberado y restauración parcial de una celda.
- [x] Cinco pruebas host nuevas cubren límites de viewport/pantalla, selección de
  cámara, ids inválidos, desbordamiento del tileset y coordenadas parciales.
- [x] `make test`: 35 pruebas, catorce BIN, trece CDT y DSK común con 16 entradas.
- [x] `make manual`: HTML, PDF y checksum sincronizados; cobertura de catorce
  ejemplos y diecisiete módulos.
- [x] `make report` actualizado; paquete local `0.2.0` con 30 entradas y checksum
  correcto. Esto no publica una release.
- [x] `tilerender` pasó estado, cámara, contador y testigos VRAM en
  AmSpiriT-Lite 1.15.3 para CPC 6128 y CPC 464; salida inspeccionada visualmente.
- [x] La batería completa pasó los catorce programas en CPC 6128 en una sola
  ejecución.
- [x] Implementación y validación local registradas en `058d4a5`, sincronizada
  en `origin/main`.
- [x] Estado persistido en `3777074`, sincronizado en `origin/main`; CI remota
  `40392730740` correcta para ese commit: 35 pruebas, catorce construcciones,
  un DSK común con catálogo y trece CDT verificados y publicados como artefacto
  temporal.

Límites: el mapa permanece inmutable y el render no ofrece transparencia,
clipping parcial, scroll sub-tile, acceso bancado ni dirty rectangles
automáticos. Las rutinas usan estado interno y no son reentrantes.

## Fase completada localmente: sprites con clipping y restauración

- [x] Auditoría de `PocketFever`: `ball_blit.s` conserva su clasificación de
  especialización 6x8; no se presentó su coste ni sus patrones como genéricos.
- [x] `video/sprite` define un descriptor de 8 bytes con datos, X/Y con signo y
  dimensiones, sin imponer entidad, física ni cola de render.
- [x] Dibujo recortado en los cuatro bordes; dimensión nula y span gráfico con
  wrap fallan antes de escribir, mientras una imagen exterior es válida y vacía.
- [x] Captura y restauración consumen solo el rectángulo visible y usan un buffer
  propiedad del consumidor, devolviendo su final en `IY`.
- [x] `spriteclip` cubre los cuatro bordes, centro, exterior, errores y una
  restauración simultáneamente recortada arriba/izquierda de 4x5 bytes.
- [x] Seis pruebas host nuevas cubren geometría, stride, vacío, span y tamaño de
  captura.
- [x] `make test`: 41 pruebas, quince BIN, catorce CDT y DSK común con 17 entradas.
- [x] `make manual`: HTML, PDF y checksum sincronizados; cobertura de quince
  ejemplos y dieciocho módulos.
- [x] Informe de tamaños actualizado; paquete local `0.2.0` con 32 entradas y
  checksum correcto. Esto no publica una release.
- [x] `spriteclip` pasó estado, buffer y testigos VRAM en AmSpiriT-Lite 1.15.3
  para CPC 6128 y CPC 464; salida inspeccionada visualmente.
- [x] La batería completa pasó los quince programas en CPC 6128 en una sola
  ejecución.
- [x] Implementación y validación local registradas en `3885f89`, sincronizada
  en `origin/main`.
- [x] Estado persistido en `098090f`, sincronizado en `origin/main`; CI remota
  `40395118414` correcta para ese commit: 41 pruebas, quince construcciones,
  un DSK común con catálogo y catorce CDT verificados y publicados como
  artefacto temporal.

Límites: sprites opacos y rectangulares, sin máscara, transparencia, recoloreado,
dirty rectangles automáticos ni comprobación de capacidad del buffer. Las
rutinas usan scratch interno, no son reentrantes y no tienen ciclos medidos.

## Fase completada localmente: orden explícito de render

- [x] Auditoría de `model01`: su cola ordenada por Y separa restauración inversa
  y redibujado directo; `PocketFever` confirma la separación de pases, pero su
  implementación permanece especializada en bolas.
- [x] `video/sprite_batch` ofrece un descriptor de lote de cuatro bytes y
  entradas de seis bytes con sprite, buffer, clave explícita y flag de captura.
- [x] El alta mantiene orden estable ascendente; capacidad cero, span con wrap
  y lote lleno devuelven carry. El lote no impone entidad ni asigna memoria.
- [x] La restauración recorre capas en orden inverso y el dibujo captura y
  compone en orden directo. Una segunda captura se rechaza antes de escribir.
- [x] `renderorder` añade la capa superior primero, prueba el orden real, el
  solapamiento, la restauración de fondo no uniforme, el movimiento y una
  actualización de escenario entre los dos pases.
- [x] Cinco pruebas host nuevas cubren orden estable, capacidad sin mutación,
  restauración inversa, doble captura y wrap del almacenamiento.
- [x] `make test`: 46 pruebas, dieciséis BIN, quince CDT y DSK común con 18
  entradas.
- [x] `make manual`: HTML, PDF y checksum sincronizados; cobertura de dieciséis
  ejemplos y diecinueve módulos.
- [x] Informe de tamaños actualizado; paquete local `0.2.0` con 34 entradas y
  checksum correcto. Esto no publica una release.
- [x] `renderorder` pasó orden, flags, fondos y testigos VRAM en AmSpiriT-Lite
  1.15.3 para CPC 6128 y CPC 464.
- [x] La batería completa pasó los dieciséis programas en CPC 6128 en una sola
  ejecución.
- [x] Implementación y validación local registradas en `48d71a2`.
- [x] Estado persistido en `cad4901`; ambos commits están sincronizados en
  `origin/main`.
- [x] CI remota `40397040993` correcta para `cad4901`: 46 pruebas, dieciséis
  construcciones, un DSK común con catálogo y quince CDT verificados y
  publicados como artefacto temporal.

Límites: capacidad y claves son propiedad del consumidor; no hay eliminación,
reordenación automática por coordenada, asignación dinámica, transparencia,
máscaras ni ciclos medidos. Un fallo de sprite durante un pase puede dejar las
entradas anteriores procesadas; el módulo usa scratch interno y no es
reentrante.

## Fase completada localmente: sprites enmascarados

- [x] `video/sprite` añade `fwk_sprite_draw_masked` sobre el descriptor de ocho
  bytes existente, sin cambiar el camino opaco de `fwk_sprite_draw`.
- [x] La máscara es paralela a los datos, con la misma geometría y offsets de
  clipping. La composición, byte a byte, es `(pantalla AND máscara) OR datos`; un
  bit 1 conserva el fondo y exige que el bit de datos correspondiente sea cero.
- [x] Se valida el span completo de datos y de máscara, además de dimensiones,
  antes de escribir. Un sprite exterior sigue siendo válido y no escribe.
- [x] `spritemask` comprueba un span de máscara con wrap, un sprite exterior,
  composición sobre fondo no uniforme y el mismo asset centrado y recortado.
- [x] Cuatro pruebas host cubren composición, offsets de clipping, span de
  máscara y la invariante de datos cero bajo bits preservados.
- [x] Se corrige la validación de ventanas para rechazar el desbordamiento de
  `y+height` de 16 bits antes de comparar con la altura del perfil. Tres pruebas
  host y un caso Z80 en `window` cubren la regresión.
- [x] `make test`: 53 pruebas, diecisiete BIN, dieciséis CDT y DSK común con 19
  entradas.
- [x] `make manual`: HTML, PDF y checksum sincronizados; cobertura de diecisiete
  ejemplos y diecinueve módulos.
- [x] `make report`: `docs/build-sizes.md` incluye los diecisiete ejemplos.
- [x] Paquete local `0.2.0` con 36 entradas y checksum correcto; no se ha
  publicado como release.
- [x] `spritemask` pasó estado y testigos VRAM en AmSpiriT-Lite 1.15.3 para CPC
  6128 y CPC 464.
- [x] `window` pasó la regresión de desbordamiento, captura, restauración y
  reapertura en CPC 6128 y CPC 464.
- [x] La batería completa pasó los diecisiete programas en CPC 6128 en una sola
  ejecución.
- [x] Implementación y validación local registradas en `ceaa68c`; el commit está
  sincronizado en `origin/main`.
- [x] CI remota `40421617471` correcta para `ceaa68c`: 53 pruebas, diecisiete
  construcciones, DSK común con catálogo y dieciséis CDT verificados y publicados
  como artefacto temporal.

Límites: la máscara es bit a bit; en Mode 0 permite preservar un píxel de 4 bits
y sustituir el otro del mismo byte. No hay color-key ni mezcla alfa.
`sprite_batch` continúa usando el camino opaco y no integra la variante
enmascarada. La rutina enmascarada comparte `video/sprite.s`, por lo que todo
ejemplo con sprites paga su código enlazado aunque no la use. No hay recoloreado,
comprobación de capacidad del buffer, dirty rectangles automáticos ni ciclos
medidos; no se promete 50 Hz para una escena enmascarada.

## Decisión vigente sobre sprites enmascarados

La fase quedó cerrada y su coste 6x8 se midió posteriormente. La ruta permanece
separada del lote ordenado por su coste aproximado de 1,77 veces el camino opaco.
Siguen pendientes la validación en hardware real y una garantía temporal para
escenas completas, no la medición básica ya registrada.

## Fase completada: rendimiento medible y presupuesto de frame

- [x] Arnés `examples/perf` con escenas deterministas: bucle vacío, limpieza
  completa, sprite opaco, sprite enmascarado, captura, restauración, lote de 8,
  tilemap completo y actualización de una celda.
- [x] Medición por frames emulados en CPC 6128 con conversión a T-estados
  (`79872` T-estados/frame) y sobrecarga del bucle calibrada.
- [x] Resultados en `docs/performance.md`: limpieza ≈ 862618 T, sprite opaco 6x8
  ≈ 6230 T, enmascarado 6x8 ≈ 11022 T, captura ≈ 5831 T, restauración ≈
  5811 T, lote de 8 ≈ 94089 T, tilemap completo ≈ 66028 T, celda ≈ 4649 T.
- [x] Decisión: `sprite_batch` sigue siendo solo opaco; la ruta enmascarada se
  mantiene separada por su coste ~1,77× y se aplaza su integración en el lote.
- [x] Herramienta `tools/measure_perf.py` para reproducir la medición.
- [x] Manual y PDF regenerados con cobertura de `perf`; suite host 53 pruebas.

## Fase completada: fuente sprite, números pequeños y plataforma jugable

- [x] El adaptador a `cpct_drawStringM0_asm` se sustituyó por el sistema de
  fuente gráfica verificado en `PocketFever`, `model01` y `DeckTower`.
- [x] Se incorporaron los 51 glifos originales de 2x9 bytes y los diez dígitos
  pequeños de 2x5 bytes, junto con su tabla Mode 0 de recoloreado y sombra.
- [x] `fwk_text_draw` conserva el contrato de cadena NUL y admite espacio, `!`,
  `-`, `/`, `0..9`, `:`, `>`, `?`, `@` y `A..Z` con el mapeo original.
- [x] Nuevas APIs: inicialización explícita, selección de 15 colores, assets
  sustituibles, dígito pequeño y entero decimal de 8 bits sin ceros iniciales.
- [x] La ruta de dígitos usa el blitter enmascarado estable y no copia el camino
  de colorización que está documentado como defectuoso en el juego de origen.
- [x] `board` dibuja texto normal, los valores pequeños `7`, `42` y `255` y
  quince copias del `8`, una por cada índice de color válido.
  AmSpiriT-Lite confirmó la tabla exacta en `0x0100` y los bytes exactos de los
  tres números en VRAM para CPC 6128 y CPC 464.
- [x] `window` pasó captura, texto, restauración y reapertura en CPC 6128 y CPC
  464. `platformer`, que también consume el nuevo texto, pasó su recorrido
  jugable automatizado en CPC 6128 y CPC 464.
- [x] El HUD de `platformer` restaura las celdas exactas antes de cambiar texto
  enmascarado, mantiene puntuación/estado dentro del panel y solo se redibuja al
  cambiar la puntuación. El smoke compara el glifo final con la composición
  limpia esperada en VRAM.
- [x] `make test`: 56 pruebas host, veintidós BIN, veintiún CDT y un DSK común
  de 24 entradas.
- [x] La batería integral de los veintidós programas pasó en CPC 6128; `board`
  y `platformer` pasaron además sus comprobaciones focalizadas en CPC 464.
- [x] Manual HTML/PDF, arquitectura, matriz comparativa, procedencia y estado de
  validación actualizados.

Límites confirmados: hay que llamar `fwk_text_init` tras desactivar firmware;
la tabla de máscara ocupa `0x0100..0x01FF`; los índices de color dependen de la
paleta del juego y el pen 14 se reserva para sombra. No hay minúsculas, clipping,
borrado automático ni reentrancia. Para sustituir texto enmascarado hay que
restaurar o limpiar primero el fondo. Implementación registrada en `263bbd4` y
estado persistido en `6b12268`; ambos se publicaron en `origin/main`. La CI
remota `40610742319` terminó correctamente para el SHA completo
`6b1226877394346c599e434b91fe6396d395424d`.

## Fase completada: aplicación didáctica de plataformas

- [x] `platformer` se reorganizó en `main.s`, `assets.s`, `game.inc` y
  `example.json`: constantes compartidas, inicialización, entrada, física,
  reglas y render tienen responsabilidades separadas.
- [x] El ejemplo conserva movimiento, salto, colisión sólida y unidireccional,
  cuatro monedas, actualización parcial del mapa, HUD restaurable y victoria;
  añade gráficos distinguibles y publica la última máscara de colisión.
- [x] El smoke completa el recorrido en CPC 6128 y CPC 464, comprueba estado,
  puntuación, aterrizajes, limpieza exacta de las celdas de monedas y
  composición del dígito final del HUD contra el tileset vigente.
- [x] El smoke admite `--screenshot-dir` y generó capturas PNG reales de la
  escena inicial y la victoria en CPC 6128.
- [x] Nueva guía mantenible `docs/platform-game-guide.html` y PDF equivalente:
  creación paso a paso, cinco capturas reproducibles, construcción, DSK común,
  pruebas y diagnóstico. Su generador conserva las tres capturas de terminal.
- [x] `make test`: 58 pruebas host, veintidós BIN, veintiún CDT y un DSK común
  de 24 entradas. Manual HTML/PDF y tamaños regenerados.

Límites confirmados: la aplicación sigue siendo una escena de una sola pantalla,
sin scroll, pendientes, enemigos ni animación. Las capturas proceden de
AmSpiriT-Lite 1.15.3; no existe validación en hardware real. Implementación y
documentación registradas en `6d7b928`, con estado en `343701a`; ambos se
publicaron en `origin/main`. La CI remota `40619504621` terminó correctamente
para el SHA completo `343701ae622cda40c91d70d8a2f5e222248148e8`.

## Fase implementada: tiles mediante CPCTelera Next

- [x] `extensions/tilemap_render` ya no contiene el blitter `LDIR` genérico:
  valida las geometrías 2x4, 2x8, 4x4 y 4x8 bytes y despacha a
  `cpct_drawTileAligned2x4_f_asm`, `cpct_drawTileAligned2x8_f_asm`,
  `cpct_drawTileAligned4x4_f_asm` o `cpct_drawTileAligned4x8_f_asm`.
- [x] La validación exige shifts coherentes y origen Y alineado, además de los
  límites previos de mapa, pantalla, ids y span del tileset.
- [x] `tilemap_render_masked` conserva la API de tilesets paralelos, valida
  ambos spans, entrelaza un tile en 64 bytes internos y delega la composición en
  `cpct_drawSpriteMasked_asm`.
- [x] `platformer` usa tiles CPCTelera de 4x8 bytes (8x8 píxeles Mode 0), mapa y
  viewport de 20x25, shifts 2/3 y monedas de una celda; mantiene las posiciones
  físicas y el redibujado parcial.
- [x] Manual HTML/PDF, guía HTML/PDF, arquitectura, README, validación,
  documentación específica, checksums, capturas de terminal y tamaños de build
  regenerados.
- [x] `make test`: 61 pruebas host correctas; 22 BIN, 21 CDT y DSK compartido
  con 24 entradas construidos correctamente contra CPCTelera Next.
- [x] AmSpiriT-Lite 1.15.3 volvió a arrancar mediante la ruta alternativa de su
  wrapper aunque `xvfb-run` y `Xvfb` siguen ausentes. `platformer`, `tilerender`
  y `tilemask` pasaron sus estados y testigos VRAM en CPC 6128; `platformer`
  completó además su recorrido en CPC 464.
- [x] Las capturas jugables inicial y de victoria se regeneraron después de
  pasar el smoke actual de `platformer` en CPC 6128 y la guía dejó de marcarlas
  como históricas.
- [ ] Las cifras de rendimiento del tilemap son históricas y están marcadas
  como tales; falta repetir `tools/measure_perf.py` con el emulador disponible.

Implementación y documentación registradas en
`3dfdeaf0e7df697228a854c526face48d836bc7c`, con el primer registro de estado
en `df1a2f69a367c6776c930423ba803a90ed6215f1`; ambos se publicaron en
`origin/main`. No existe validación en hardware real ni CI remota confirmada
para esta fase en el momento de cerrar el registro.

## Fase implementada: configuración inicial de transparencia y bancos

- [x] El manifiesto admite `transparency.pen` de 0 a 15 y
  `extended_memory` booleano. El constructor rechaza tipos, rangos y
  combinaciones de módulos incompatibles.
- [x] `fwk_project_init` sustituye a la inicialización directa en los 22
  ejemplos: inicializa el sistema y, una sola vez, instala la tabla de
  transparencia y/o detecta memoria extendida.
- [x] La tabla Mode 0 de 256 bytes se genera para el pen configurado y queda en
  `0x0100`. Sprites, texto y tilemaps transparentes usan esa dirección
  implícita y ya no reciben ni conservan una máscara paralela.
- [x] Sin transparencia, los símbolos transparentes no se ensamblan y los
  consumidores son rechazados. Los assets de texto incorporados exigen pen 0.
- [x] El código comienza en `0x0200` por defecto. Con memoria extendida se añade
  automáticamente `resources/bank.s`, stub y scratch ocupan
  `0x0200..0x0215` y el código comienza inmediatamente después, en `0x0216`;
  no se desperdicia el resto de la página baja hasta `0x02FF`.
- [x] La reserva fija `0x7FF0`, procedente de un intento histórico descartado
  en DeckTower, se eliminó. La detección usa temporalmente `0x4000` bajo `DI` y
  restaura los bytes originales de RAM normal y banco 0; pasó en CPC 6128 y
  CPC 464 emulados.
- [x] `spritemask` usa pen 3 para probar un color no nulo. AmSpiriT-Lite 1.15.3
  verificó la tabla completa, composición, clipping y testigos VRAM; `board`,
  `tilemask` y `resources128` también pasaron en CPC 6128.
- [x] `make test` pasó 71 pruebas host, 22 BIN, 21 CDT y el DSK compartido con
  24 entradas. El NOI de `spriteclip` confirma que
  `fwk_sprite_draw_masked` está ausente sin la capacidad.
- [x] README, arquitectura, documentación específica, manual y guía de
  plataformas HTML/PDF, checksums y tamaños fueron actualizados.

Límites confirmados: solo se soporta transparencia configurable en Mode 0; la
tabla ocupa `0x0100..0x01FF`; el blitter no ofrece clipping propio ni es
reentrante; `sprite_batch` sigue siendo opaco. Las cifras históricas del dibujo
enmascarado ya no representan esta implementación y deben volver a medirse. No
hay validación en hardware real. Esta fase aún no tiene commit, push ni CI
remota; se registrarán cuando el usuario solicite publicarla.

## Fase implementada: sprite Mode 0 transparente y recoloreable

- [x] Nueva API `fwk_sprite_draw_masked_recolor`: `IX=descriptor`, `D=pen
  origen`, `E=pen sustituto`; ambos pens se validan en 0..15 antes de escribir.
- [x] Conserva el clipping, la validación de span, el formato `width*height` y
  los registros `IX/IY` del renderer de sprites existente.
- [x] El reemplazo se realiza por píxel Mode 0 y antes de la transparencia:
  sustituir por el color clave oculta el píxel y sustituir el color clave lo
  vuelve opaco.
- [x] Se reutiliza `cpct_pens2pixelPatternPairM0_asm`; la composición posterior
  es propia porque el fast path alineado de CPCtelera presupone pen 0 y el
  framework admite cualquier pen configurado.
- [x] `spritemask` demuestra pen transparente 3, rechazo de pen inválido y
  reemplazo 5→15. Los testigos VRAM pasaron en AmSpiriT-Lite 1.15.3 para CPC
  6128 y CPC 464.
- [x] `make test`: 74 pruebas host, 22 BIN, 21 CDT y DSK compartido con 24
  entradas. `make manual` regeneró el PDF y su checksum; tamaños actualizados.

Límites confirmados: se sustituye un único pen por llamada, no una tabla de 16
pens; `sprite_batch` sigue siendo opaco; el coste temporal aún no se ha medido;
no existe validación en hardware real. Esta ampliación aún no tiene commit,
push ni CI remota.

## Fase implementada: render selectivo de entidades

- [x] `video/entity_render` reemplaza directamente a `video/sprite_batch`; el
  módulo y sus pruebas antiguas se retiraron.
- [x] Cada entidad empieza con un prefijo de render de 25 bytes: descriptor de
  sprite compatible, `sort_y` signed de 16 bits, buffer/capacidad, geometría y
  orden anteriores, flags y pens de recoloreado.
- [x] La lista usa un array contado de punteros con huecos nulos, rechaza
  duplicados y recibe del juego un array auxiliar de cuatro bytes por slot.
- [x] `restore_dirty` calcula el cierre transitivo de solapamientos sobre la
  unión de rectángulos anterior/actual, restaura en orden inverso y entra en
  `RESTORED`; `draw_dirty` ordena establemente por Y, captura/dibuja y vuelve a
  `IDLE`.
- [x] Se admiten las cuatro rutas: opaca, enmascarada, opaca recoloreada y
  enmascarada recoloreada. Sin transparencia, los flags enmascarados se
  rechazan antes de escribir.
- [x] `fwk_entity_render_mark_rect_dirty` permite coordinar cambios externos de
  tiles/HUD. Se validan span de sprites, capacidad visible y solapamiento de
  buffers activos antes de modificar VRAM; la propagación revierte sus flags si
  la validación falla.
- [x] `renderorder` migró al nuevo ciclo y prueba que una única entidad sucia
  propaga el estado a su capa solapada. `perf` ejercita las cuatro rutas del
  dispatcher; `spritemask` añade la ruta opaca recoloreada.
- [x] Manual HTML/PDF, arquitectura, guía de render, migración, rendimiento,
  procedencia y matriz comparativa se actualizaron.
- [x] 73 pruebas host pasaron. Los 22 BIN, 21 CDT y el DSK común de 24 entradas
  se construyeron correctamente. `renderorder`, `spritemask` y `perf` pasaron
  en AmSpiriT-Lite/CPC 6128; `renderorder` y `spritemask` pasaron también en
  CPC 464.

Límites confirmados: no se han medido ciclos del nuevo cierre, ordenación ni
dispatcher; no hay verificación en hardware real. La fase y las anteriores aún
están sin commit/push/CI remota en este árbol de trabajo.

## Aplicación migrada: `platformer` sobre `entity_render`

- [x] Jugador y cuatro monedas empiezan por el prefijo estándar de 25 bytes y
  se recorren mediante un array de punteros y un work array de cinco entradas.
- [x] El estado compacto de física permanece inmediatamente detrás del prefijo;
  las rutinas de plataforma reciben ese subregistro y el renderer recibe la
  base de la entidad.
- [x] El jugador solo activa `DIRTY` cuando cambia de posición y actualiza
  `sort_y` con su borde inferior. Al recoger una moneda se quita `VISIBLE`, se
  activa `DIRTY` y el ciclo restaura su fondo antes de dejar de dibujarla.
- [x] El HUD ocupa una región que no solapa entidades; restaura solo las celdas
  de texto modificadas y se actualiza después del dibujo de entidades.
- [x] La guía HTML se reescribió con el prefijo, descriptor, buffers, array de
  punteros, sincronización dirty y retirada segura de coleccionables.
- [x] La construcción aislada y la regresión global terminaron correctamente:
  22 BIN, 20 CDT y DSK compartido de 24 entradas. Tras reconstruir el DSK
  completo, el recorrido automatizado volvió a pasar en AmSpiriT-Lite para CPC
  6128 y CPC 464.
- [x] Pasaron 74 pruebas host, incluida la comprobación arquitectónica de que el
  ejemplo selecciona `entity_render` y ya no llama al ciclo manual de
  captura/restauración.
- [x] Se regeneraron las capturas de inicio/victoria, la guía HTML/PDF, su
  checksum, el manual HTML/PDF, su checksum y el informe de tamaños.

Observación histórica previa a la optimización posterior: la prueba de entrada
mostró aproximadamente una actualización por cada dos frames y `PF_SPEED` se
había elevado de 2 a 4. La fase posterior elimina esa compensación. Hardware
real, temporización de raster y CI remota siguen sin verificar. Cambios aún sin
commit/push.

### Ajuste local de sincronización de `platformer`

- [x] La espera de VSYNC se movió desde el inicio del bucle hasta inmediatamente
  antes del bloque destructivo; la optimización posterior dejó el HUD después
  de `restore_dirty -> draw_dirty`.
- [x] Se mantiene una sola espera: insertar otra entre restauración y dibujo
  dejaría visible únicamente el fondo durante un frame completo.
- [x] La construcción aislada y el recorrido automatizado completo pasaron en
  AmSpiriT-Lite para CPC 6128 y CPC 464 después del cambio.
- [x] El 2026-10-31 el usuario confirmó en una prueba interactiva que el
  parpadeo ha desaparecido y que la velocidad del personaje permanece estable.

## Optimización local: preparación de render y HUD acotado

- [x] `fwk_entity_render_prepare_dirty` ejecuta validación de frame, cierre de
  solapamientos, preflight y orden anterior sin escribir VRAM. La ruta queda
  `IDLE -> PREPARED -> RESTORED -> IDLE`.
- [x] `restore_dirty` conserva compatibilidad preparando desde `IDLE`, pero
  `platformer` usa explícitamente `prepare_dirty` antes de VSYNC y mantiene
  consecutivos restore/draw después.
- [x] Duplicados y rangos de buffer se validan fuera del frame en `init`; la
  nueva `fwk_entity_render_revalidate` permite comprobar cambios estructurales
  posteriores mientras la lista está en `IDLE`.
- [x] El HUD ya no se mezcla con el borde: filas 1/2 tienen interior negro,
  puntuación y ayuda comparten una línea y quedan dentro de los laterales.
- [x] Una moneda normal restaura dos celdas y un único dígito; solo la victoria
  sustituye las 18 celdas del tramo de estado. El HUD se actualiza después de
  volver a dibujar las entidades.
- [x] `PF_SPEED` vuelve de 4 a 2. Con tres monedas visibles, el diagnóstico pasó
  de 10 a 20 actualizaciones durante 19 frames de tecla programados (incluye la
  actualización del frame de activación), compatible con una iteración/frame.

Validación local cerrada:

- [x] 74 pruebas host, incluida la correspondencia HTML/PDF/checksum del
  manual y de la guía de plataformas.
- [x] Construcción global: 22 BIN, 20 CDT y DSK compartido de 24 entradas;
  `docs/build-sizes.md` regenerado.
- [x] `platformer` completó dos recorridos consecutivos en
  AmSpiriT-Lite/CPC 6128 y otro en CPC 464. `renderorder` pasó en ambos
  modelos y `perf` en CPC 6128.
- [x] Las capturas de inicio y victoria se regeneraron y se inspeccionaron: el
  texto queda dentro del panel negro y no invade el borde superior ni los
  laterales.
- [x] La prueba automatizada verifica que las monedas estáticas quedan sin
  `DIRTY`, que las recogidas no se redibujan y que el fondo y el dígito del HUD
  se restauran correctamente.

La continuidad visual y la velocidad estable están confirmadas mediante la
prueba interactiva del usuario. Siguen sin medirse ciclos exactos, no hay una
validación independiente en hardware real y no se ha ejecutado CI remota.
Cambios aún sin commit/push.

## Fase implementada: construcción y ejecución individual de ejemplos

- [x] `examples/<nombre>/Makefile` incluye `cfg/example.mk`, de modo que cada
  consumidor se compila solo con `make` desde su carpeta, igual que un proyecto
  CPCtelera, reaprovechando `tools/build_examples.py`.
- [x] `make run` compila y abre el CDT del ejemplo (que autorrancia) o su DSK
  con el emulador indicado en `GLASNOST_EMULATOR` o, si no se indica, con
  AmSpiriT-Lite junto al repositorio o con `amspirit-lite`/`amspirit` en
  `PATH`. Sin emulador imprime la ruta de la imagen.
- [x] `make clean` borra únicamente `.build/<nombre>/`; `.build/` sigue siendo
  el único destino de los artefactos y `examples/` no recibe copias del
  framework.
- [x] `tests/test_example_targets.py` exige el envoltorio idéntico en los 22
  ejemplos y comprueba en seco (`make -n`) que `build`, `clean` y `run` solo
  afectan al ejemplo invocado.
- [x] Documentado en `README.md` y en el manual; PDF y checksum regenerados.
- [x] `make test`: 102 pruebas y 22 construcciones correctas (2026-10-31).

## Fase implementada: configuración CPCtelera y assets por ejemplo

- [x] `examples/platformer` incluye `cfg/build_config.mk`, una configuración
  CPCtelera real con licencia y estructura de proyecto. El constructor la usa
  como base y solo reescribe `CPCT_PATH`, `PROJNAME`, `TARGET`, `Z80CODELOC` y
  el `-I$(SRCDIR)`; el resto de flags y rutas se conservan.
- [x] Los ejemplos sin configuración propia siguen usando
  `cfg/build_config.template.mk`, sin cambios en los otros veintiún
  consumidores.
- [x] `examples/platformer/assets/README.md` documenta el flujo completo:
  originales en `assets/src/`, manifiesto `assets.json`, paleta Mode 0 y datos
  generados en `assets/generated/`.
- [x] Cualquier carpeta `assets/` de un ejemplo se copia a `src/assets` del
  proyecto generado: los `.s` se ensamblan sin tocar `game_sources`, los `.inc`
  se incluyen como `assets/<archivo>.inc` y los originales quedan disponibles
  para las herramientas. Los enlaces simbólicos se rechazan.
- [x] `selected-modules.json` registra la configuración y los assets usados.
- [x] Documentado en README y manual; PDF y checksum regenerados.
- [x] `make test`: 102 pruebas y 22 construcciones correctas (2026-10-31).

## Fase implementada: conversión incremental de imágenes y tilemaps

- [x] `tools/import_assets.py` convierte PNG Mode 0 con `img2cpc -of bin -nt` y
  genera un único `.s` SDCC con etiquetas globales, además de un `.inc` con
  tamaños y constantes.
- [x] Las capas de Tiled se leen del CSV del `.tmx` aplicando la misma
  reindexación que `cpct_tmx2csv`: `0` sigue siendo `0` y cada gid positivo se
  reduce en uno. Se rechazan capas no CSV, tiles volteados y símbolos
  duplicados.
- [x] La conversión es incremental: `assets/generated/pipeline.json` guarda un
  SHA-256 del manifiesto, la paleta y cada PNG/TMX, más el hash de las salidas.
  Un `make` sin cambios no invoca `img2cpc` ni `zx7b`.
- [x] `make assets` ejecuta solo esa comprobación/conversión; `make` la ejecuta
  antes de compilar y `tools/build_examples.py` la integra en el flujo global.
- [x] Los mapas declarados con `"compression": "zx7b"` se comprimen con
  `tools/zx7b`; los bytes comprimidos quedan en ROM, el buffer en RAM y
  `main.s` descomprime una vez al inicializar con `resources/zx7b.s`.
- [x] Los datos generados se versionan para que una comprobación limpia no
  requiera las herramientas; editar un original sí las exige y el error indica
  cómo instalarlas (incluida la variante macOS con FreeImage de Homebrew).
- [x] `tests/test_import_assets.py` cubre reindexación TMX, validación del
  manifiesto, detección de fuentes obsoletas, símbolos y tamaños generados, y
  la ida y vuelta de ZX7B contra las capas del `.tmx`.
- [x] La música no se enlaza por defecto para no alterar el presupuesto de
  frame ni el smoke; `assets/README.md` documenta el camino opt-in reutilizando
  la canción MIT de `examples/audio`.
- [x] `make test`: 102 pruebas y 22 construcciones correctas (2026-10-31);
  `docs/build-sizes.md` regenerado.

## Fase implementada: compilación incremental y artefactos locales

- [x] `tools/build_examples.py` ya no borra `.build/<nombre>/` en cada ejecución:
  conserva `obj/` y sincroniza solo las fuentes staging, de modo que CPCTelera
  decide qué recompilar según sus dependencias.
- [x] Las fuentes, cabeceras generadas (`project_config.*`, `video_config.inc`,
  `disk_files.inc`) y la configuración se escriben solo si su contenido cambia,
  preservando mtimes y evitando recompilaciones innecesarias.
- [x] `make` en una carpeta de ejemplo no compila nada si las fuentes no han
  cambiado, y recompila únicamente los ficheros afectados cuando cambian.
- [x] `cfg/example.mk` copia tras compilar `BIN`, `CDT` y `DSK` a la carpeta del
  ejemplo (ignorados por git) y `make clean` los elimina junto con
  `.build/<nombre>/`.
- [x] `tests/test_example_targets.py` cubre la copia y la limpieza de artefactos.
- [x] `make test`: 102 pruebas y 22 construcciones correctas (2026-10-31).

## Fase implementada: emulador MacAPE

- [x] Creado `cpctelera_next/cpctelera/tools/scripts/cpct_macape`, un wrapper
  WinAPE-style para MacAPE que carga DSK/CDT/SNA y auto-ejecuta el primer
  programa de un DSK con `/A` (o `/A:nombre`).
- [x] `tools/run_example.py` detecta MacAPE automáticamente
  (`/Applications/MacAPE.app`, `~/Proyectos/macape`) y añade `/A` al abrir un DSK.
- [x] `make run` puede usar MacAPE mediante `GLASNOST_EMULATOR=.../cpct_macape`.
- [x] Documentado en README y manual; PDF y checksum regenerados.
- [x] `make test`: 102 pruebas y 22 construcciones correctas (2026-10-31).

## Fase implementada: paleta en códigos de firmware

- [x] `assets/palette.json` usa ahora `"type": "firmware"` con 16 códigos de
  firmware (0-26) en lugar de colores RGB.
- [x] `tools/import_assets.py` valida la paleta firmware y genera un bloque
  `platformer_palette` con los valores hardware equivalentes en
  `assets/generated/assets.s`, más `PLATFORMER_PALETTE_SIZE` en `assets.inc`.
- [x] `examples/platformer/main.s` carga la paleta generada con
  `cpct_setPalette_asm` en la inicialización, eliminando los `cpct_setPALColour_asm`
  codificados a mano.
- [x] Los datos de imagen generados siguen siendo byte a byte idénticos a los
  anteriores.
- [x] `make test`: 102 pruebas y 22 construcciones correctas (2026-10-31).

## Corrección: visibilidad de la puerta en `platformer`

- [x] `palette.json` se había regenerado con una permutación incorrecta de
  códigos de firmware; restaurada la paleta prevista
  `[0,1,2,3,4,24,6,7,8,9,4,11,12,13,14,20]`.
- [x] Los PNG se regeneraron con los colores RGB equivalentes y `import_assets`
  vuelve a producir los datos de puerta originales (`0xFF,0x80,...`).
- [x] `make test`: 102 pruebas y 22 construcciones correctas (2026-10-31).

## Corrección: puerta fuera de pantalla en `platformer`

- [x] La puerta se declaraba en `X=144` (píxeles), pero `entity_render` interpreta
  `X` en bytes; se corrige a `72` (144 píxeles) para que quede dentro de la
  pantalla y se pueda capturar/dibujar.
- [x] `make test`: 102 pruebas y 22 construcciones correctas (2026-10-31).

## Corrección: contactos, puerta y HUD de `platformer`

- [x] El tercer enemigo vertical se comprueba aunque no haya contacto con el
  primero y conserva su bit de contacto, por lo que un solapamiento sostenido
  no descuenta una vida en cada frame.
- [x] El reinicio de flags vuelve a ocultar explícitamente la puerta; recoger
  las cuatro monedas sigue siendo la única ruta que activa `VISIBLE|DIRTY`.
- [x] La restauración del HUD usa las columnas correspondientes a los bytes
  reales del texto: 3 para puntuación, 19 para vidas, 0--4 para el contador y
  6--14 para la ayuda/estado. El mensaje se corrigió a `GO TO THE DOOR`.
- [x] `make test` pasó 103 pruebas host, construyó los 22 ejemplos y regeneró
  el DSK común. El nuevo smoke focalizado comprobó contacto/latch del tercer
  enemigo, puerta oculta y actualización de VRAM del HUD en CPC 6128 y 464.
- [x] Manual y guía HTML/PDF, checksums y capturas reproducibles de terminal
  regenerados.

Límite detectado entonces: el recorrido completo de `platformer` en CPC 6128
fallaba en la comprobación de movimiento existente: después de 20 frames de
vídeo programados hacia la derecha obtenía `x=30`, fuera del intervalo esperado.
La fase 0 confirmó que la prueba suponía incorrectamente una iteración de juego
por frame de vídeo y sustituyó esa temporización por objetivos observables; no
era una colisión en X=30. Hardware real continúa sin validar.

## Corrección e integración: módulo `behavior`

- [x] `FWK_BEHAVIOR_WAIT` termina ahora su tabla con
  `FWK_BEHAVIOR_CONDITIONS_END`; mientras el temporizador estaba activo, la
  macro anterior podía interpretar la acción siguiente como otra condición.
- [x] `behavior.inc` exporta la API pública usada por sus macros y la suite
  host comprueba el terminador.
- [x] Los tres enemigos de `platformer` sustituyeron sus rebotes manuales por
  registros de ocho bytes y un adaptador compartido
  `fwk_behavior_run -> fwk_motion_u8_step -> entity_render`.
- [x] El horizontal conserva X=32..54 con esperas de 19/23 ticks. Los dos
  verticales comparten el mismo programa inmutable de 49 ticks para Y=56..152,
  pero cada uno mantiene cursor y temporizador propios. El planificador conserva
  la frecuencia previa: horizontal/vertical derecho alternos y vertical
  izquierdo cada frame.
- [x] Se eliminaron `_platformer_enemy_h_dx`, `_platformer_enemy_v_dy`, las
  ramas manuales de incremento, clamp y cambio de sentido, el sincronizador
  exclusivo del tercer enemigo y el programa vertical duplicado.
- [x] El smoke focalizado observa avance y sincronización de los tres registros
  `behavior`, además de contacto/latch, puerta y HUD, en CPC 6128. CPC 464 no
  se repitió porque esta migración no cambia contratos dependientes del modelo;
  la versión inmediatamente anterior del módulo sí había pasado allí.
- [x] Tras migrar los tres enemigos, `make test` pasó 106 pruebas host,
  construyó los 22 ejemplos y regeneró el DSK común. Manual y guía HTML/PDF,
  checksums y capturas reproducibles se regeneraron; el smoke focalizado final
  pasó en CPC 6128. CPC 464 conserva la validación de la versión inmediatamente
  anterior, no de esta migración completa.

Límites: `behavior` no ejecuta movimiento, colisión ni render por sí mismo; el
consumidor debe componer esos pasos. Su presupuesto de 16 despachos usa estado
global, por lo que no es reentrante ni debe invocarse de forma anidada o desde
una interrupción. El recorrido jugable completo quedó recuperado en la fase 0;
el hardware real sigue sin verificar.

## Política de validación simplificada

- [x] `make check` ejecuta las 106 pruebas host y compila únicamente los
  consumidores indicados por `CHECK_EXAMPLES` (`platformer` por defecto), sin
  reconstruir el DSK común.
- [x] Durante una implementación se usan pruebas focalizadas o `make check`.
  `make test` se ejecuta una sola vez al cerrar la tarea o antes del commit.
- [x] Un cambio Z80 ejecutado recibe normalmente un smoke focalizado en CPC
  6128. CPC 464 se reserva para cambios de modelo, memoria/bancos y releases.
- [x] Manual/PDF, informe, DSK global y matrices amplias se regeneran una sola
  vez al final cuando correspondan, no después de cada ajuste intermedio.
- [x] Flujo comprobado: `make check CHECK_EXAMPLES=platformer` pasó las 106
  pruebas host en 0,893 s y confirmó que `platformer` estaba actualizado sin
  reconstruir el DSK. Al cerrar la migración de los tres enemigos se ejecutó
  una sola vez `make test` como regresión completa final.

## Migración ECS 2.0: estado operativo

Plan aprobado el 2026-11-03 y persistido en
`docs/ecs-2.0-master-plan.md`. Ese documento contiene las decisiones de
arquitectura, SDK, toolchain, proyectos, paquetes, ciclo de vida, prioridades,
fases y puertas de avance.

### Fase 0: completada, punto de restauración

- [x] Plan maestro consolidado y aprobado.
- [x] `main` identificado en `8eacbb816d61499952e94b049dacd6dade4697bd`
  antes del commit de cierre; el árbol contiene la integración todavía no
  confirmada de contactos/puerta/HUD, corrección de `behavior`, migración de los
  tres enemigos y política de validación simplificada.
- [x] Fallo reproducido: X=30 tras 20 frames de vídeo. No era una colisión; el
  smoke suponía incorrectamente que cada frame de vídeo completaba una
  iteración de juego.
- [x] El recorrido mantiene las direcciones hasta alcanzar posiciones
  observables del jugador, con timeout y comprobación de intervalo. También se
  actualizaron sus referencias obsoletas a la tabla de transparencia y a la
  antigua posición del HUD.
- [x] Validación focalizada CPC 6128: recorrido completo de `platformer`, smoke
  de behavior/contactos/puerta/HUD y `board` correctos.
- [x] Regresión global final del 2026-11-03: 106 pruebas host en 0,888 s, 22
  ejemplos construidos y DSK común de 24 entradas (22 programas y dos payloads
  de `diskload`). Manual y guía HTML/PDF con checksums regenerados.
- [x] El recorrido completo se repitió correctamente en CPC 6128 después de
  reconstruir el DSK. CPC 464 y hardware real no se ejecutaron en este cierre.
- [x] Referencia funcional no ECS publicada en `main` como
  `5e9743630a3729fd137de557736df100e085e448`; `origin/main` se verificó en ese
  SHA y la CI remota `41623906057` terminó correctamente.
- [x] `ecs-v2` creada desde el cierre documentado de `main`
  (`e757fd00d8cdb5ec2f72d17e06085ffb073cc90d`) y verificada en
  `origin/ecs-v2` en ese mismo SHA. No contiene todavía implementación ECS.

Condición G0 alcanzada: la referencia no ECS está limpia, sincronizada y
reproducible, con SHA y CI registrados y sin un fallo de recorrido ambiguo.

### Fase 1: objetivo

Redactar y revisar layouts, offsets, máscaras, registros de llamada, errores,
estados y restricciones del ECS. No se implementará el entity manager hasta
aprobar esa especificación (puerta G1).

### Fase 1: completada, G1 aprobada

- [x] Se contrastaron las decisiones con `model01` y `PocketFever`: ambos
  confirman AoS, máscara al principio, plantillas copiadas y punteros directos,
  pero sus managers antiguos mezclan slots reutilizables con compactación y no
  ofrecen una convención uniforme de errores. Esas limitaciones no se copian.
- [x] `docs/ecs-abi-2.0.md` fija la propuesta de cabecera, bloques generados,
  máscara de 16 bits, lifecycle, render, descriptor de manager, llamadas Z80,
  errores, frame, colisión y compatibilidad.
- [x] Se propone un límite de 128 bytes por entidad: los desplazamientos
  indexados `IX+d`/`IY+d` solo alcanzan offsets 0..127. Es una restricción real
  del ABI directo, no una preferencia estética.
- [x] La especificación conserva slots estables y no añade `generation`; las
  validaciones de procedencia pueden existir en debug, pero no se pagan en cada
  acceso release.
- [x] No se ha creado código de manager ni símbolos ECS enlazables.
- [x] Se añadieron cinco pruebas de contrato para cabecera, lifecycle, API,
  errores, render, colisión y referencias cruzadas. `make check
  CHECK_EXAMPLES=platformer` pasó 111 pruebas host en 0,968 s y compiló el
  ejemplo.
- [x] Manual HTML/PDF y checksum regenerados; README, plan maestro y estado
  enlazan la propuesta y advierten que aún no es una API ejecutable.
- [x] Propuesta publicada en `ecs-v2` como
  `601b6e84be5c562d63a236a6e20f736730208ea7` y verificada en el remoto.
- [x] CI manual de la rama `41625865832` correcta: 111 pruebas host, los 22
  ejemplos, DSK común y artefactos distributables verificados.
- [x] El 2026-11-03 el usuario aprobó expresamente los ocho contratos de G1;
  `docs/ecs-abi-2.0.md` pasa de candidata a normativa.
- [x] Cierre G1 revalidado: manual HTML/PDF y checksum regenerados; `make check
  CHECK_EXAMPLES=platformer` pasó 111 pruebas host en 0,979 s y confirmó el
  ejemplo actualizado.
- [x] Aprobación registrada y publicada en
  `3a0eabc830ed29b4542a8500cdffb4c81b1b38ad`; `origin/ecs-v2` se verificó en
  ese SHA. La CI manual `41628752201` terminó correctamente con 111 pruebas,
  22 ejemplos, DSK común y artefacto `glasnostfwk-3a0eabc...`.

G1 queda alcanzada. No se ejecutó smoke porque no cambió código Z80. La CI
ejecutó la regresión global sobre el contenido técnico de la especificación;
el cierre documental se revalida después de retirar las marcas de candidata.

### Fase 2: completada, entity manager ejecutable

- [x] `src/core/ecs_manager.s` implementa los ocho símbolos aprobados en G1:
  inicialización, creación desde plantilla, destrucción diferida,
  habilitación/deshabilitación, cambio de máscara, recorrido y recolección.
- [x] Los slots son estables y se reutiliza siempre el primer `FREE`; no hay
  compactación ni contador `generation`. `ACTIVE_COUNT` y `LIVE_COUNT` se
  mantienen al aplicar cada transición.
- [x] El manager valida descriptor, storage, capacidad, stride exacto del
  perfil, máscaras y pertenencia de punteros. Las operaciones estructurales se
  rechazan bajo lock; marcar destrucción sí está permitido durante recorrido.
- [x] `fwk_ecs_system_run` filtra `ACTIVE` por inclusión de máscara, recorre en
  orden de slot, propaga abortos y libera siempre el lock. `IX` e `IY` se
  preservan conforme a la ABI.
- [x] Retirar `RENDER` con `HAS_BACKGROUND` activo devuelve
  `FWK_ECS_ERR_RENDER`; la aclaración se incorporó a la ABI normativa para no
  perder una captura que el render deba restaurar.
- [x] El staging acepta temporalmente `ecs_profile` y lo instala como
  `ecs_profile.inc`. `examples/ecsmanager` aporta un fixture manual; la fase 3
  debe reemplazarlo por generación desde manifiesto.
- [x] El ejemplo ejecutable comprueba inicialización, tres creaciones, lleno,
  disable/enable, máscara inválida, lock durante callback, destrucción,
  recolección, reutilización estable, error de render y aborto de callback.
- [x] Validación focalizada en AmSpiriT-Lite 1.15.3/CPC 6128: estado final
  `0x5A`, tres slots `ACTIVE` con máscara `0x0003`, contadores `3/3`, lock cero
  y render marcado `DIRTY` después de reactivar.
- [x] Regresión local de cierre: 114 pruebas host, 23 BIN, 22 CDT y DSK común
  de 25 entradas. `ECSMANAG.BIN` carga en `0x0200`, ejecuta en `0x022F` y ocupa
  1.483 bytes de BIN enlazado (1.366 de código y 117 de datos).
- [x] Manual HTML/PDF y checksum regenerados; informe de tamaños actualizado.
- [x] La CI comprueba explícitamente el BIN y CDT de `ecsmanager`, además de
  incluirlo en `make test` y en el DSK común.
- [x] Implementación publicada en `ecs-v2` mediante
  `3a9b1a573f628a8bed5e8b9bfe6c3d92a1b67594`; verificación explícita de
  artefactos corregida y publicada en
  `7d209340fadbd32ddefd3f051b953db46b164775`.
- [x] CI manual `41630455820` correcta para `7d209340...`: 115 pruebas host,
  23 ejemplos, BIN/CDT de `ecsmanager`, DSK común y artefacto temporal
  `glasnostfwk-7d209340...` (ID `13227278502`) verificados.

No se repitió CPC 464 porque el manager no depende del modelo, memoria
extendida, CRTC ni render físico. No existe validación en hardware real. El
manager usa `CALL` automodificable para el callback y, como fija la ABI, no es
reentrante, no puede anidarse ni llamarse desde IRQ.

### Fase 3: completada, generador de perfiles ECS

- [x] `tools/gen_ecs_profile.py` genera de forma determinista
  `ecs_profile.inc` desde el bloque `ecs` del manifiesto y el catálogo
  versionado `manifests/ecs-components.json`.
- [x] El generador resuelve primero las dependencias, conserva `render` en el
  bit 0 y admite hasta 16 componentes entre catálogo y definiciones propias
  del proyecto.
- [x] Los formatos de coordenadas configurables son `u8`, `u16` y `fixed_8_8`;
  los campos admiten tipos escalares, punteros y bloques `bytes[n]`. Los tipos
  derivados `x_format`, `y_format`, `velocity_x` y `velocity_y` siguen la
  configuración del proyecto.
- [x] Se validan esquema, nombres, tipos, duplicados, dependencias desconocidas
  o cíclicas, rango del perfil de vídeo, máximo de 16 bits, nombres reservados
  y límite ABI de 128 bytes por entidad.
- [x] `--preview` muestra el layout y sus cambios sin escribir; `--check` y el
  objetivo `make generate` impiden construir con un include versionado
  obsoleto. `make generate-ecs` es la operación explícita de regeneración.
- [x] `tools/build_examples.py` exige el bloque `ecs` cuando se selecciona el
  manager, comprueba el include versionado y prepara ese contenido para el
  ensamblado. La entrada temporal `ecs_profile` de la fase 2 fue eliminada.
- [x] `ecsmanager` genera el mismo layout de 25 bytes y la misma máscara
  `0x0003` que el fixture anterior. El manager consume ahora el nombre
  normativo `ECS_COMPONENT_VALID_MASK`.
- [x] Ocho pruebas nuevas cubren reproducibilidad, dependencias, formatos,
  rechazos, detección de include obsoleto, diferencias de layout y preview sin
  escritura. La regresión local pasó 123 pruebas host, construyó 23 BIN y 22
  CDT y generó el DSK común con 25 entradas.
- [x] Smoke focalizado posterior al build global correcto en
  AmSpiriT-Lite 1.15.3/CPC 6128: `ecsmanager` ejecuta y avanza frames.
- [x] Manual HTML/PDF, checksum, ABI, README e informe de tamaños actualizados.
- [x] Implementación publicada en `ecs-v2` como
  `6127a2ba4e553be8a22b13779596d242fc434bb8`; `origin/ecs-v2` se verificó en
  ese mismo SHA.
- [x] CI manual `41802820638` correcta para `6127a2ba...`: 123 pruebas host,
  23 BIN, 22 CDT, DSK común y artefacto temporal
  `glasnostfwk-6127a2ba...` (ID `13308661285`) verificados.

El cierre de la fase 3 dejó únicamente `render` en el catálogo. La fase 4 añade
ahora `motion` y `behavior` con contratos explícitos; física, colisión y
animación siguen fuera del portfolio normativo. No se ejecutó CPC 464 porque
esta fase solo usa coordenadas `u8` ya validadas en CPC 6128. No existe
validación en hardware real.

### Fase 4: completada, sistemas ECS de behavior y movimiento

- [x] El catálogo añade `MOTION` (`velocity_x`, `velocity_y`, `flags`) y
  `BEHAVIOR` (`program`, `timer`, `state`), con dependencia `BEHAVIOR -> MOTION`.
- [x] `src/core/ecs_behavior.s` adapta el intérprete de behavior existente a
  los campos de entidad mediante un registro temporal privado y copia de vuelta
  velocidades, programa y temporizador.
- [x] `src/core/ecs_motion.s` implementa movimiento `u8` con saturación contra
  `ECS_X_MAX/ECS_Y_MAX` y activa `ECS_RENDER_DIRTY` al cambiar X/Y.
- [x] `ecsmanager` selecciona ambos componentes, ejecuta cuatro ciclos
  behavior -> movimiento y verifica posición y velocidad resultantes.
- [x] El staging invalida los objetos CPCTelera cuando cambia el include
  generado; así no se enlaza un layout ECS anterior por reutilización de `.rel`.
- [x] Validación focalizada: 21 pruebas host del área ECS/manual, build de
  `ecsmanager` y smoke correcto en AmSpiriT-Lite 1.15.3/CPC 6128.
- [x] Regresión global: 125 pruebas host, 23 BIN, 22 CDT y DSK común de 25
  entradas. `ecsmanager` enlaza 1.973 bytes (1.791 código, 182 datos).
- [x] Manual HTML/PDF, checksum, ABI, README, informe de tamaños y validación
  actualizados.
- [x] Implementación publicada en `ecs-v2` como
  `6bf71a011a9b4f065437f20ca6d74be02c80b50a`; `origin/ecs-v2` se verificó en
  ese mismo SHA.
- [x] CI manual `41807544677` correcta para `6bf71a0...`: 125 pruebas host,
  23 BIN, 22 CDT, DSK común y artefacto temporal
  `glasnostfwk-6bf71a0...` (ID `13309469104`) verificados.

No se ejecutó CPC 464 porque el sistema está restringido a coordenadas `u8`
ya validadas en CPC 6128 y no cambia el modelo de bancos, CRTC ni loader. No
existe validación en hardware real.

### Siguiente fase: 5, ejemplo `platformer_ecs`

Crear `examples/platformer_ecs` con entidades y sistemas ECS, sin alterar el
`platformer` de referencia. La migración debe reutilizar los contratos de
behavior y movimiento ya cerrados y dejar preparada la paridad posterior.

### Fase 5: completada, integración vertical `platformer_ecs`

- [x] Se añadió `examples/platformer_ecs` como consumidor aislado del ABI ECS
  2.0, sin modificar `examples/platformer`.
- [x] El manifiesto selecciona manager, behavior, motion, vídeo y sprites;
  `ecs_profile.inc` contiene `render`, `motion` y `behavior` en una entidad de
  32 bytes.
- [x] La escena crea un player ECS y dos enemigos ECS. Los enemigos usan los
  programas behavior compartidos y `fwk_ecs_system_motion_u8`; el player usa
  render/motion sin behavior.
- [x] Se añadió un puente temporal de render que adapta el puntero de sprite y
  las coordenadas ECS a `fwk_sprite_draw`. Recorre todos los slots
  renderizables; no pretende ser todavía el renderer ECS dirty/multi-manager de
  la fase 9.
- [x] El nuevo BIN usa el nombre AMSDOS `PECS.BIN` para evitar la colisión de
  ocho caracteres con `PLATFORM.BIN`, y se incluye en el DSK común y la CI.
- [x] Smoke focalizado correcto en AmSpiriT-Lite 1.15.3/CPC 6128:
  `platformer_ecs` crea los tres slots, mantiene al player inmóvil y observa
  movimiento de los enemigos.
- [x] Manual HTML/PDF y checksum regenerados; el plan y la validación reflejan
  la integración y sus límites.
- [x] Commit publicado en `ecs-v2` como `c1c14c47dd1b0401c363cf2cc2b2249ba4ba9c3f`;
  `origin/ecs-v2` se verificó en ese SHA.
- [x] CI manual `41811578372` correcta: job `126511876002` completado en 19 s,
  host tests, 24 BIN, 23 CDT, DSK común y artefacto temporal verificados.

La siguiente fase es la 6: añadir input de entidades, física principal y
tilemaps ECS. No se debe presentar `platformer_ecs` como paridad completa con
la referencia hasta cerrar las fases 6-10.

### Fase 6: completada, adaptadores de input, plataforma y tilemap

- [x] El portfolio ECS añade `input` y `platform`; `platform` depende de
  `motion` y el perfil generado de `platformer_ecs` queda en 37 bytes por
  entidad.
- [x] `src/core/ecs_input.s` adapta `fwk_input_held/pressed` a velocidad
  horizontal y salto según `action_mask`.
- [x] `src/core/ecs_platform.s` adapta cada entidad al estado de siete bytes de
  `physics_platform`, ejecuta `platform_tilemap_resolve` y copia de vuelta
  posición, velocidad y flags, marcando render dirty cuando cambia la posición.
- [x] `platformer_ecs` contiene un tilemap estático 20x25 y lo dibuja con
  `fwk_tilemap_render_view`, manteniendo el render ECS como puente temporal.
- [x] Regresión local: 125 pruebas host, 24 BIN, 23 CDT y DSK común; smoke CPC
  6128 correcto para ejecución, frames y suelo visible.
- [x] Cierre de la fase 6: el smoke inicial ocultaba tres defectos (carrera
  de lectura de vídeo, nacimiento no aéreo del jugador, y `ecs_motion.s` con
  doble integración de entidades `PLATFORM` y desbordamiento por signo). Los
  tres están corregidos y el smoke demuestra caída, aterrizaje en y=184,
  desplazamiento izquierda/derecha y ciclo de salto/aterrizaje. Detalle en
  `docs/validation.md`.
- [ ] Pendiente de seguimiento: el puente de render redibuja todo en cada
  iteración (~1,3 it/s en AmSpiriT-Lite); se resuelve con el render por
  suciedad de fases posteriores.
- [x] Implementación publicada en `ecs-v2` como
  `e5bc741e29ab169e29378687ee08c3ae53bbc051`; CI manual
  `41816216332`/job `126527519587` correcta en 25 s, con 125 pruebas host,
  24 BIN, 23 CDT, DSK común y artefacto temporal verificados.

### Fase 7: completada, colisión ECS (rediseño mínimo)

Decisión del 2026-11-05: el primer diseño (tabla global de pares, buffer de
eventos, roles, hasta 255 entidades por manager) pesaba entre 980 y 5.300
bytes y se había optimizado para casos que ningún juego de CPC tiene. Se
sustituyó por un diseño mínimo con presupuesto de tamaño fijado de antemano.

- [x] ABI 9 revisado: `fwk_ecs_collide` (sujeto contra objetivos de un
  manager), callback con `IX`=manager, `IY`=objetivo, `HL`=sujeto,
  `A`=`ENTER`/`STAY`/`EXIT`, un byte de estado por entidad.
- [x] `src/core/ecs_collision.{inc,s}`: unos 210 bytes de código y 7 de datos
  (presupuesto 300 y 8, comprobado por una prueba). El llamante elige el canal
  de estado (`E`); ocho canales por sujeto.
- [x] Modelo y escenario de 26 pasos, `examples/ecscollision`, smoke en CPC
  6128 y 464.
- [x] Principio añadido al plan maestro: presupuesto de bytes por sistema antes
  de construir, sin tablas ni buffers globales fijos, rendimiento medido con
  entidades de un juego.
- [x] El PR #2 (diseño anterior) queda sustituido por este.
- [ ] Limitaciones: estado por sujeto y canal, no por pareja; posiciones dentro de
  pantalla y sumas `u8` sin saturar; no reentrante.

### Fase 8: completada, animación ECS

- [x] ABI 10 concreto: componente `animation` (descriptor, frame, temporizador),
  mismo formato de descriptor que el animador no ECS, presupuesto de 150 bytes
  de código y ningún dato fijado antes de escribir código.
- [x] `src/core/ecs_animation.{inc,s}`: 109 bytes de código y 0 de datos.
  `fwk_ecs_system_animation` avanza frames y marca `DIRTY`;
  `fwk_ecs_anim_set` cambia de animación sin reiniciar la activa.
- [x] Modelo y escenario de 14 pasos con cinco entidades (130 frames, plantilla
  con descriptor), `examples/ecsanimation`, smoke en CPC 6128 y 464; seis
  mutaciones comprobadas a mano (no automatizadas).
- [ ] Limitaciones: `count` o `duration` cero son indefinidos y silenciosos;
  el descriptor no lleva tamaño de sprite; llamar a `fwk_ecs_anim_set` antes
  del sistema acorta el frame 0 en una llamada.
- [ ] Siguiente: fase 9, render ECS multi-manager (la de mayor riesgo), con su
  presupuesto de bytes y un criterio de rendimiento medido en un juego real
  antes de escribir código.

