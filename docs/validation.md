# Estado de validación

Fecha: 2026-10-26 UTC.

## Implementado

- Núcleo de IRQ/VSYNC, entrada con estado/flancos y pool genérico.
- Vídeo Mode 0 generado, CRTC explícito, tabla 16-bit y limpieza de regiones.
- Texto Mode 0, audio AKG con música/SFX, copia bancaria 128 KB, lectura AMSDOS
  y descompresión ZX7B opcionales.
- Cursor de animación opcional, independiente de entidad, render y política de
  juego.
- Física de plataforma con velocidad byte, gravedad, límites y aterrizaje; e
  integrador 8.8 separado con fricción vectorial y rebote.
- Consulta row-major de tilemap de solo lectura y resolución opcional de
  sólidos/plataformas de una dirección para el perfil de plataforma.
- Ventanas opcionales con validación, captura, borde/relleno y restauración;
  texto, entrada y cierre permanecen en el consumidor.
- Generadores de vídeo/recursos y trece ejemplos, incluida una vertical jugable.
- Frontera de dependencias y exclusión física de módulos.
- Manual HTML/PDF en castellano con cobertura automática de todos los ejemplos
  y módulos seleccionados.

## Compilado

Los trece ejemplos generan `.bin` con CPCTelera Next `11e61fe3…`/SDCC 4.5.0;
doce generan además `.cdt`. Sus trece BIN y los dos payloads de `diskload` se
reúnen en un único `.build/tests/GlasnostFWK-tests.dsk`; los DSK individuales
intermedios se eliminan. `diskload` no genera CDT porque sus payloads auxiliares
no están en cinta. `docs/build-sizes.md` contiene tamaños enlazados.

## Probado automáticamente

- Direcciones estándar conocidas, bordes y cruces de bloques.
- 23.040 direcciones únicas para 160x288 y cruce `0xBEB0 -> 0xC000`.
- Ocho huecos estándar fuera del conjunto visible.
- Generación determinista byte a byte.
- Rechazo de solapamientos, destinos reservados y bancos no disponibles.
- Ausencia de imports `src -> examples/game` y selección de módulos.
- Validación de fuentes de juego declaradas, existentes y sin recorridos inseguros.
- Construcción completa de los trece ejemplos y validación de nombres 8.3,
  rutas locales y selección de medio para los archivos añadidos al DSK.
- 30 pruebas host en total. El manual cubre los trece ejemplos y dieciséis módulos;
  su checksum corresponde al HTML que generó el PDF vigente.

## Ejecutado en emulador

Ejecutado con AmSpiriT-Lite 1.15.3, CRTC 1:

- Los trece programas arrancaron desde el único `GlasnostFWK-tests.dsk` en un
  CPC 6128 de 128 KB y avanzaron su contador de frames.
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
- Tras reproducir una salida aparentemente vacía en `gravity`, se comprobó que
  la demo heredaba de BASIC fondo azul en el pen 0 y negro en el pen 5 usado por
  la traza. `gravity` fija ahora negro/amarillo y `physics88` negro/cian. El
  smoke verifica tanto los registros de paleta como el byte final en VRAM.
- `window` rechazó una geometría fuera de pantalla, capturó 320 bytes, dibujó
  borde/relleno sin tocar los testigos exteriores, restauró las 16 filas y
  volvió a abrirse. Pasó en CPC 6128 y CPC 464.
- `vertical` cargó jugador y tres coleccionables desde fuentes de recursos
  separadas. CursorRight se mantuvo mediante la matriz de teclado: el jugador
  recogió los tres, el pool se compactó de cuatro registros a uno y se activó
  el estado de victoria. También se comprobaron en RAM de vídeo los bytes de
  jugador, coleccionables y victoria. La misma prueba pasó en CPC 6128 y CPC 464.

La entrada está automatizada solo para `vertical`. `tilecoll` se inspeccionó
visualmente en emulador y su geometría/traza resultaron visibles. No se validó
visualmente el perfil experimental 160x288 ni se capturó la salida analógica de
audio. Dos ejecuciones completas expusieron carreras de observación en los
testigos finales de `animation` y `vertical`: ambos publican estado antes de
dibujar en ese mismo frame. El smoke espera ahora explícitamente el byte de
VRAM; las repeticiones aisladas ya habían pasado y una tercera batería completa
pasó los trece casos en una sola ejecución.

## Verificado en hardware

No verificado.

## Pendiente o bloqueado

- Medir ciclos/tiempo de escena; no hay cifras ni promesa de 50 Hz.
- Validar la temporización CRTC 160x288 en varios tipos CRTC y hardware. El
  modelo de memoria sí está probado; la señal de vídeo no.
- Añadir render o edición de tilemaps si una fase futura lo requiere; el
  contrato actual es deliberadamente de solo lectura y colisión.
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
python3 tests/emulator_smoke.py window
python3 tests/emulator_smoke.py --model 464 window
python3 tests/emulator_smoke.py --model 464 vertical
```
