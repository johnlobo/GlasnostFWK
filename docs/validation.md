# Estado de validación

Fecha: 2026-10-29 UTC.

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
  parcial explícita de una celda; la variante enmascarada usa su blitter de
  sprites enmascarados.
- Sprites rectangulares Mode 0 con coordenadas de 16 bits con signo, clipping
  por los cuatro bordes y captura/restauración del fondo visible.
- Dibujo enmascarado opcional sobre el mismo descriptor, con máscara paralela,
  composición `(pantalla AND máscara) OR datos` y validación del span completo.
- Lote opcional de sprites con inserción estable por clave, restauración
  inversa y captura/dibujo directo para solapamientos; el lote usa el camino
  opaco y no integra todavía la máscara.
- Ventanas opcionales con validación, captura, borde/relleno y restauración;
  texto, entrada y cierre permanecen en el consumidor.
- Generadores de vídeo/recursos y veintidós ejemplos, incluidas dos escenas jugables.
- Frontera de dependencias y exclusión física de módulos.
- Manual HTML/PDF en castellano con cobertura automática de todos los ejemplos
  y módulos seleccionados.

## Compilado

Los veintidós ejemplos generan `.bin` con CPCTelera Next `11e61fe3…`/SDCC 4.5.0;
veintiuno generan además `.cdt`. Sus veintidós BIN y los dos payloads de
`diskload` se reúnen en un único `.build/tests/GlasnostFWK-tests.dsk` con 24
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
- Construcción completa de los veintidós ejemplos y validación de nombres 8.3,
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
  recogió los tres, el pool se compactó de cuatro registros a uno y se activó
  el estado de victoria. También se comprobaron en RAM de vídeo los bytes de
  jugador, coleccionables y victoria. La misma prueba pasó en CPC 6128 y CPC 464.
- `platformer` completó su recorrido jugable automatizado, recogió cuatro
  monedas y alcanzó la victoria en CPC 6128 y CPC 464. Al cambiar el marcador,
  restauró las tres filas de tiles bajo el HUD antes de redibujar; el smoke
  comparó el glifo final con la composición exacta de fuente, máscara y tileset,
  y comprobó que las celdas de las monedas inferiores quedaron limpias. La ruta
  CPC 6128 produjo capturas PNG reales de la escena inicial y la victoria.

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
- El camino opaco sigue siendo la base del lote ordenado. La máscara es bit a
  bit: en Mode 0 permite preservar un píxel de 4 bits y sustituir el otro del
  mismo byte, sin color-key ni mezcla alfa. No está integrada en `sprite_batch`;
  tampoco hay recoloreado ni comprobación de capacidad del buffer. El código
  enmascarado comparte `video/sprite.s` y se enlaza en todo ejemplo con sprites.
  El lote ordenado tiene capacidad fija y no ofrece eliminación ni cambio
  automático de clave.
- Ciclos del dibujo enmascarado medidos en `docs/performance.md` (6x8 ≈ 11022
  T-estados). No se promete 50 Hz para una escena arbitraria.
- Ampliar las pruebas Z80 más allá de los recorridos cubiertos actualmente:
  `vertical` prueba entrada/movimiento/eliminación del pool y `resources128`
  prueba detección/copia bancaria; las ramas de error de disco y los payloads
  ZX7B corruptos no están automatizados.

## Comandos reproducibles

```sh
cd /config/workspace/GlasnostFWK
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
