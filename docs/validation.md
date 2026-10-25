# Estado de validación

Fecha: 2026-10-25 UTC.

## Implementado

- Núcleo de IRQ/VSYNC, entrada con estado/flancos y pool genérico.
- Vídeo Mode 0 generado, CRTC explícito, tabla 16-bit y limpieza de regiones.
- Texto Mode 0, adaptador AKG optativo y copia bancaria 128 KB.
- Generadores de vídeo/recursos y cinco ejemplos.
- Frontera de dependencias y exclusión física de módulos.

## Compilado

Los cinco ejemplos generan `.bin`, `.cdt` y `.dsk` con CPCTelera Next
`11e61fe3…`/SDCC 4.5.0. `docs/build-sizes.md` contiene tamaños enlazados.

## Probado automáticamente

- Direcciones estándar conocidas, bordes y cruces de bloques.
- 23.040 direcciones únicas para 160x288 y cruce `0xBEB0 -> 0xC000`.
- Ocho huecos estándar fuera del conjunto visible.
- Generación determinista byte a byte.
- Rechazo de solapamientos, destinos reservados y bancos no disponibles.
- Ausencia de imports `src -> examples/game` y selección de módulos.
- Construcción completa de los cinco ejemplos.

## Ejecutado en emulador

Ejecutado con AmSpiriT-Lite 1.15.3, CRTC 1:

- Los cinco DSK arrancaron en un CPC 6128 de 128 KB y avanzaron su contador de
  frames.
- `video` conservó el testigo `0xA5` en `0xC7D0` después de limpiar pantalla.
- `resources128` detectó 128 KB y recuperó `GLASNOST` tras el viaje
  RAM normal -> banco 0 -> RAM normal.
- `resources128` se repitió en CPC 464: reportó 64 KB y continuó por su ruta de
  fallback sin intentar el roundtrip.

No se automatizó entrada de juego ni audio. Tampoco se validó visualmente el
perfil experimental 160x288.

## Verificado en hardware

No verificado.

## Pendiente o bloqueado

- Medir ciclos/tiempo de escena; no hay cifras ni promesa de 50 Hz.
- Validar la temporización CRTC 160x288 en varios tipos CRTC y hardware. El
  modelo de memoria sí está probado; la señal de vídeo no.
- Integrar un export AKG con licencia clara y ejecutar pruebas de audio.
- Extraer backend de disco, ZX7B, ventanas, animación y perfiles completos de
  plataformas/8.8 cuando exista una integración verificable.
- Añadir pruebas Z80 de ejecución para pool/input/bancos, no solo build y host.

## Comandos reproducibles

```sh
cd /config/workspace/GlasnostFWK
make test
make report
python3 tests/emulator_smoke.py
python3 tests/emulator_smoke.py --model 464 resources128
```
