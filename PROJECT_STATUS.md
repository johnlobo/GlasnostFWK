# Estado del proyecto

Última actualización: 2026-10-25 UTC. Objetivo de publicación: `v0.1.0`.

Este archivo es el registro canónico recuperable entre sesiones. Debe
actualizarse en cada commit con cambios funcionales, de construcción o de
publicación.

## Estado confirmado

- Las nueve fases del encargo inicial están implementadas como primera versión
  utilizable: reconocimiento, arquitectura, núcleo, módulos, recursos,
  generadores, perfil experimental, ejemplos y documentación.
- Los seis ejemplos construyen BIN, CDT y DSK con CPCTelera Next fijada en
  `11e61fe30175ad7b328de9bcd859c46fd61b26a5`.
- `vertical` es la primera integración jugable. Está automatizada en CPC 6128
  y CPC 464 mediante AmSpiriT-Lite 1.15.3.
- El perfil estándar 160x200 está probado. El modelo de memoria 160x288 está
  probado, pero su temporización CRTC sigue siendo experimental.
- El repositorio público es `johnlobo/GlasnostFWK` y la rama principal es
  `main`.

## Fase actual: distribución v0.1.0

- [x] Empaquetador determinista para los BIN, CDT y DSK de los seis ejemplos.
- [x] Instrucciones de ejecución y manifiesto dentro del paquete.
- [x] `SHA256SUMS` para verificar la descarga.
- [x] Workflow que reconstruye desde el tag publicado y adjunta el paquete a
  una GitHub Release.
- [x] Pruebas locales completas: 14 pruebas, seis construcciones y paquete de
  20 archivos; checksum comprobado desde `dist/`.
- [ ] Commit y push en `main`.
- [ ] GitHub Release pública `v0.1.0`.
- [ ] Descarga y verificación independiente de los archivos publicados.

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

## Limitaciones confirmadas

- No existe verificación en hardware real.
- No se ha validado visualmente el perfil experimental 160x288 en varios CRTC.
- Audio AKG, carga desde disco, ZX7B, ventanas y perfiles completos de física
  siguen pendientes de integración ejecutable.
- Solo `vertical` es una escena jugable; los otros cinco artefactos son pruebas
  técnicas.

## Siguiente acción después de v0.1.0

Extraer e integrar el backend de carga desde disco de forma independiente del
manifiesto de recursos, seguido por el wrapper ZX7B, con un ejemplo ejecutable
y comprobaciones en emulador. No se considerará cerrado hasta que la carga real
desde DSK esté verificada.
