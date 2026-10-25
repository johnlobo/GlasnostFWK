# Estado del proyecto

Última actualización: 2026-10-25 UTC. Última versión publicada: `v0.1.0`.

Este archivo es el registro canónico recuperable entre sesiones. Debe
actualizarse en cada commit con cambios funcionales, de construcción o de
publicación.

## Estado confirmado

- Las nueve fases del encargo inicial están implementadas como primera versión
  utilizable: reconocimiento, arquitectura, núcleo, módulos, recursos,
  generadores, perfil experimental, ejemplos y documentación.
- Los siete ejemplos construyen BIN y DSK con CPCTelera Next fijada en
  `11e61fe30175ad7b328de9bcd859c46fd61b26a5`; seis construyen además CDT.
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

## Limitaciones confirmadas

- No existe verificación en hardware real.
- No se ha validado visualmente el perfil experimental 160x288 en varios CRTC.
- Audio AKG, carga desde disco, ZX7B, ventanas y perfiles completos de física
  siguen pendientes de integración ejecutable.
- Solo `vertical` es una escena jugable; los otros seis ejemplos son pruebas
  técnicas. `diskload` se distribuye solo como DSK.

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

Comandos específicos:

```sh
python3 tests/emulator_smoke.py diskload
python3 tests/emulator_smoke.py --model 464 diskload
```

## Fase siguiente: audio AKG ejecutable

Integrar un export AKG sintético o con licencia inequívoca, comprobar música y
efectos mediante estado observable en emulador y documentar el coste de IRQ.
El adaptador existente compila, pero todavía no tiene datos enlazados ni una
prueba de ejecución; no debe presentarse como validado hasta cerrar ese hueco.
