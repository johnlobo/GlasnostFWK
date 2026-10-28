# Estado del proyecto

Última actualización: 2026-10-28 UTC. Última versión publicada: `v0.2.0`.

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
- Los veintidós ejemplos construyen BIN con CPCTelera Next fijada en
  `11e61fe30175ad7b328de9bcd859c46fd61b26a5`; veintiuno construyen además CDT
  y todos los BIN se reúnen en un único DSK de pruebas con 24 entradas.
- La suite host contiene 56 pruebas; el manual cubre todos los ejemplos y
  módulos seleccionados.
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
- [x] El HUD de `platformer` restaura sus tres filas de tiles antes de cambiar
  texto enmascarado, separa verticalmente sus dos líneas y solo se redibuja al
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
