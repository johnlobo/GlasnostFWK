# Estado del proyecto

Última actualización: 2026-10-25 UTC. Última versión publicada: `v0.1.0`.

Este archivo es el registro canónico recuperable entre sesiones. Debe
actualizarse en cada commit con cambios funcionales, de construcción o de
publicación.

## Estado confirmado

- Las nueve fases del encargo inicial están implementadas como primera versión
  utilizable: reconocimiento, arquitectura, núcleo, módulos, recursos,
  generadores, perfil experimental, ejemplos y documentación.
- Los nueve ejemplos construyen BIN y DSK con CPCTelera Next fijada en
  `11e61fe30175ad7b328de9bcd859c46fd61b26a5`; ocho construyen además CDT.
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
- Ventanas y perfiles completos de física siguen pendientes de integración
  ejecutable.
- Solo `vertical` es una escena jugable; los otros ocho ejemplos son pruebas
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
- [ ] Pendiente en este punto del registro: commit, sincronización y CI remota
  de la fase.

Comandos específicos:

```sh
python3 tests/emulator_smoke.py animation
python3 tests/emulator_smoke.py --model 464 animation
```

## Fase siguiente: ventanas y mensajes reutilizables

Auditar primero las implementaciones reales de paneles, cajas y mensajes de
los cuatro proyectos. Extraer solo geometría, limpieza y composición que tenga
un contrato común ejecutable; conservar como lógica de juego cualquier menú,
combate, texto o temporización que no sea verdaderamente compartida.
