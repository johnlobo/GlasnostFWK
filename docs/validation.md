# Estado de validación

Fecha: 2026-10-25 UTC.

## Implementado

- Núcleo de IRQ/VSYNC, entrada con estado/flancos y pool genérico.
- Vídeo Mode 0 generado, CRTC explícito, tabla 16-bit y limpieza de regiones.
- Texto Mode 0, adaptador AKG optativo y copia bancaria 128 KB.
- Generadores de vídeo/recursos y seis ejemplos, incluida una vertical jugable.
- Frontera de dependencias y exclusión física de módulos.

## Compilado

Los seis ejemplos generan `.bin`, `.cdt` y `.dsk` con CPCTelera Next
`11e61fe3…`/SDCC 4.5.0. `docs/build-sizes.md` contiene tamaños enlazados.

## Probado automáticamente

- Direcciones estándar conocidas, bordes y cruces de bloques.
- 23.040 direcciones únicas para 160x288 y cruce `0xBEB0 -> 0xC000`.
- Ocho huecos estándar fuera del conjunto visible.
- Generación determinista byte a byte.
- Rechazo de solapamientos, destinos reservados y bancos no disponibles.
- Ausencia de imports `src -> examples/game` y selección de módulos.
- Validación de fuentes de juego declaradas, existentes y sin recorridos inseguros.
- Construcción completa de los seis ejemplos.

## Ejecutado en emulador

Ejecutado con AmSpiriT-Lite 1.15.3, CRTC 1:

- Los seis DSK arrancaron en un CPC 6128 de 128 KB y avanzaron su contador de
  frames.
- `video` conservó el testigo `0xA5` en `0xC7D0` después de limpiar pantalla.
- `resources128` detectó 128 KB y recuperó `GLASNOST` tras el viaje
  RAM normal -> banco 0 -> RAM normal.
- `resources128` se repitió en CPC 464: reportó 64 KB y continuó por su ruta de
  fallback sin intentar el roundtrip.
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
- Extraer backend de disco, ZX7B, ventanas, animación y perfiles completos de
  plataformas/8.8 cuando exista una integración verificable.
- Ampliar las pruebas Z80 más allá de los recorridos cubiertos actualmente:
  `vertical` prueba entrada/movimiento/eliminación del pool y `resources128`
  prueba detección/copia bancaria, pero no todas las ramas de error.

## Comandos reproducibles

```sh
cd /config/workspace/GlasnostFWK
make test
make report
python3 tests/emulator_smoke.py
python3 tests/emulator_smoke.py --model 464 resources128
python3 tests/emulator_smoke.py --model 464 vertical
```
