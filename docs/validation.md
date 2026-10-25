# Estado de validación

Fecha: 2026-10-25 UTC.

## Implementado

- Núcleo de IRQ/VSYNC, entrada con estado/flancos y pool genérico.
- Vídeo Mode 0 generado, CRTC explícito, tabla 16-bit y limpieza de regiones.
- Texto Mode 0, adaptador AKG optativo, copia bancaria 128 KB, lectura AMSDOS
  y descompresión ZX7B opcionales.
- Generadores de vídeo/recursos y siete ejemplos, incluida una vertical jugable.
- Frontera de dependencias y exclusión física de módulos.

## Compilado

Los siete ejemplos generan `.bin` y `.dsk` con CPCTelera Next
`11e61fe3…`/SDCC 4.5.0; seis generan además `.cdt`. `diskload` es solo DSK
porque sus payloads auxiliares no están en cinta. `docs/build-sizes.md`
contiene tamaños enlazados.

## Probado automáticamente

- Direcciones estándar conocidas, bordes y cruces de bloques.
- 23.040 direcciones únicas para 160x288 y cruce `0xBEB0 -> 0xC000`.
- Ocho huecos estándar fuera del conjunto visible.
- Generación determinista byte a byte.
- Rechazo de solapamientos, destinos reservados y bancos no disponibles.
- Ausencia de imports `src -> examples/game` y selección de módulos.
- Validación de fuentes de juego declaradas, existentes y sin recorridos inseguros.
- Construcción completa de los siete ejemplos y validación de nombres 8.3,
  rutas locales y selección de medio para los archivos añadidos al DSK.

## Ejecutado en emulador

Ejecutado con AmSpiriT-Lite 1.15.3, CRTC 1:

- Los siete DSK arrancaron en un CPC 6128 de 128 KB y avanzaron su contador de
  frames.
- `video` conservó el testigo `0xA5` en `0xC7D0` después de limpiar pantalla.
- `resources128` detectó 128 KB y recuperó `GLASNOST` tras el viaje
  RAM normal -> banco 0 -> RAM normal.
- `resources128` se repitió en CPC 464: reportó 64 KB y continuó por su ruta de
  fallback sin intentar el roundtrip.
- `diskload` se ejecutó en CPC 6128 y CPC 464. En ambos leyó `RAWDATA.BIN`
  (256 B) y `PACKDATA.ZX7` (23 B) desde el DSK, descomprimió el segundo a
  256 B y se compararon todos los bytes contra el testigo esperado.
- `vertical` cargó jugador y tres coleccionables desde fuentes de recursos
  separadas. CursorRight se mantuvo mediante la matriz de teclado: el jugador
  recogió los tres, el pool se compactó de cuatro registros a uno y se activó
  el estado de victoria. También se comprobaron en RAM de vídeo los bytes de
  jugador, coleccionables y victoria. La misma prueba pasó en CPC 6128 y CPC 464.

La entrada está automatizada solo para `vertical`; el audio no se automatizó.
Tampoco se validó visualmente el perfil experimental 160x288.

## Verificado en hardware

No verificado.

## Pendiente o bloqueado

- Medir ciclos/tiempo de escena; no hay cifras ni promesa de 50 Hz.
- Validar la temporización CRTC 160x288 en varios tipos CRTC y hardware. El
  modelo de memoria sí está probado; la señal de vídeo no.
- Integrar un export AKG con licencia clara y ejecutar pruebas de audio.
- Extraer ventanas, animación y perfiles completos de plataformas/8.8 cuando
  exista una integración verificable.
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
python3 tests/emulator_smoke.py --model 464 vertical
```
