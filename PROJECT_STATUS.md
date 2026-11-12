# Estado operativo del proyecto

Actualizado: 2026-11-12 UTC. Este documento contiene el estado vigente y los
próximos pasos. El [historial por fases](docs/design/project-history.md) conserva
las decisiones, mediciones y validaciones antiguas sin reescribirlas. Una casilla
abierta en ese historial no implica una tarea pendiente hoy.

## Rama, commits y validación

- Estado e historial separados en `b0aff2a`, incluidos en la PR
  [#42](https://github.com/johnlobo/GlasnostFWK/pull/42), fusionada con squash en
  `0f920235dcf3c258ae6d25514e3530ec15504378` de `main`.
- Conflictos con `07dc833` resueltos conservando la integración BluePixel.
  Validación local combinada: 595 pruebas correctas en 104,227 s, 22 BIN,
  20 CDT y DSK de 24 entradas. CI del commit combinado `6bc425c`:
  [42866267161](https://github.com/johnlobo/GlasnostFWK/actions/runs/42866267161),
  correcta, incluido smoke determinista de `nave` con BluePixel.
- Rama de implementación: `refactor/program-manifest`, creada desde `0f92023`.
  Implementación: `e71e9572406e13fc9e4ac22358f538823b92319a`,
  «Renombra el manifiesto y migra proyectos al formato 2», subida y verificada
  con `git ls-remote`. PR [#44](https://github.com/johnlobo/GlasnostFWK/pull/44);
  Integración con `b8e50e5` registrada en `7fad0e1696ada8d37f0d922af49626cf52a79c51`.
  CI [42868247527](https://github.com/johnlobo/GlasnostFWK/actions/runs/42868247527)
  correcta sobre ese SHA, incluido smoke determinista de `nave` con BluePixel
  API 1.4. La PR identifica el commit squash de entrega en `main`.
- Validación del cambio de manifiesto: `make test` correcto, 602 pruebas host
  en 105,677 s, 22 BIN, 20 CDT y DSK con 24 entradas. Las 61 pruebas de
  actualización incluyen la migración real, conservación de bytes, fallo y rollback.
  Un proyecto legado se compila de verdad antes y después de migrar.
- 21 BIN coinciden con la captura incremental anterior; `perf` difiere en ese
  árbol, pero sus construcciones limpias de antes/después son idénticas
  (`bd95e05c1140a6b85e4bbc7bb3e48fc1c2bad43dcff8208372818e90719eab69`, 6.402 B).
  Los mapas muestran distinta dirección de `_main` entre build limpio e incremental.
  No se atribuye esa diferencia al renombrado ni se garantiza reproducibilidad
  de compilaciones incrementales; se conserva como pendiente técnico.
- Manual y guía de plataformas: HTML, PDF, checksum y capturas del manifiesto
  regenerados. Paquete `0.2.0-manifest`: dos ZIP idénticos de 45 archivos y
  SHA256 correcto sobre los artefactos construidos.
- La reorganización anterior verificó además dos paquetes locales idénticos
  (45 archivos, SHA256 correcto), Makefile local de `ecsmanager` y smoke
  AmSpiriT-Lite CPC 6128 de `text` y `ecsanimation`.
- No hay nueva release; última versión publicada registrada: `v0.2.0`
  (histórica; no revisada en remoto aquí).

## Funcionalidad vigente

- ECS con slots estables, máscaras, plantillas, ciclo de vida diferido y sistemas
  de behavior, movimiento, entrada, plataforma, colisión y animación. El renderer
  selectivo usa pools de fondos. El intérprete de behavior está integrado en
  `core/ecs_behavior.s`.
- Contrato normativo: [ecs-abi-2.0.md](docs/reference/ecs-abi-2.0.md).
  Fase 1: completada, G1 aprobada. La migración y retirada del modelo anterior se
  documentan en las fases 10 y 11 del historial; no se debe retomar la antigua fase 6.
- 15 ejemplos públicos en `examples/`; `board` ahora se llama `text`.
  `nave` es el resultado de la guía inicial y `platformer` la referencia avanzada.
- 7 programas internos en `framework/validations/`: `video`, `ecsmanager`,
  `ecscollision`, `ecsanimation`, `ecsrender`, `perf` y `experimental`.
- `vertical`, su smoke y su guía específica se han eliminado. Su cobertura de
  recogida/victoria no se atribuye a otros programas.
- `tools/build/program_catalog.py` alimenta Makefile, CLI, CI, DSK y paquete;
  los programas utilizan `glasnost.manifest.json`; la lectura de `example.json`
  sigue disponible para consumidores y proyectos antiguos, rechazando pares ambiguos.
- `make examples` construye ejemplos públicos; `make validations`, los internos;
  `make test` y `make release` construyen ambos y el DSK común. `diskload` y `perf`
  declaran solo DSK. El ZIP separa ejemplos y validaciones.
- BluePixel headless integrado desde `07dc833` de `main`: adaptador stdio, smoke
  determinista de `nave` y ejecución en CI. El código y la documentación se conservan
  al resolver los conflictos con la reorganización; validación local y CI correctas.
  El CI compila BluePixel fijado en `c5e2437b4db4eb543a47b90fa8fccb90c448664f` (API 1.4),
  incorporado desde `b8e50e5` de `main` y comprobado con esta entrega en CI.
- CLI con toolchain fijada, creación/configuración de proyectos, repositorio y remoto
  propios, actualización con migraciones y rollback. Formato de proyecto actual: 2.
- Toolchain fijada: CPCTelera Next `11e61fe30175ad7b328de9bcd859c46fd61b26a5`.
  Los fuentes Z80 del framework viven en `framework/src/`, las herramientas en
  `tools/{glasnost,build,dev}` y la documentación en `docs/{guide,reference,design}`.

## Entrega autorizada, por orden

1. Separar estado e historial: completado y fusionado en la PR #42.
2. PR/CI de reorganización: completadas y fusionadas en `0f92023`.
3. Cambio a `glasnost.manifest.json`: implementado y validado localmente y en
   CI; entrega mediante PR #44. Migración de formato 1 a 2 con
   conservación byte a byte del manifiesto; elimina el nombre antiguo solo en la
   rama de actualización, recuperable ante fallo o con rollback. No se han
   modificado automáticamente los proyectos de usuario en `projects/`.

## Pendientes de producto y límites vigentes

- Tiles en Mode 1 (2026-11-12): `extensions/tilemap_render.s` y `tilemap_render_masked.s` ya no están
  en `MODE0_ONLY_MODULES` de `tools/build/build_examples.py`; solo `ui/text.s` se rechaza con un perfil Mode 1.
  Las primitivas de CPCTelera copian bytes y el renderizador resuelve direcciones con la tabla del perfil, así que
  no había causa técnica. `examples/mode1` dibuja una franja opaca y otra enmascarada; `tests/emulator_smoke.py mode1`
  lo comprobó en AmSpiriT-Lite con 11 testigos de VRAM (el perfil CRTC sigue sin validar visualmente).
  Importador de tiles Mode 1 revisado (2026-11-12): con el `img2cpc` real, tiles 8x8 y 16x8 (rejilla 2x2) coinciden byte a
  byte con un codificador independiente de la disposición Mode 1 y mantienen el orden por filas
  (`RealMode1ConversionTests` en `tests/test_import_assets.py`; se salta si no hay `img2cpc`). Sin cambios de código.
- Fase 15 (paquetes compartidos) cancelada el 2026-11-12 por decisión de David; la fase 16
  sigue con offline, backups, CI de proyectos y publicación. Los emuladores en Mac los valida David.
- Offline (fase 16, primer bloque): `glasnost export-bundle` e `install-toolchain --bundle FILE`
  ([referencia](docs/reference/glasnost-cli.md), «Instalación sin red»). El bundle lleva el commit fijado y su
  árbol sin historial, se valida contra el commit del lockfile y se compila en destino; no incluye paquetes del
  sistema ni emuladores. Verificado con el commit real `11e61fe` (2026-11-12, Linux x86_64): export de 76,5 MB en
  unos 6 s, árbol importado idéntico al repo (11.963 archivos, `fsck` limpio) e instalaciones completas sin red
  (limpia y con `--force`, SDCC compilado, `doctor` correcto) con la URL del lockfile inutilizada. pruebas
  nuevas (`tests/test_glasnost_bundle.py`) con un upstream falso, y rondas repetidas de revisión adversaria en frío
  con comprobación por mutaciones. Un checkout enlazado simbólicamente (toolchain de desarrollo) nunca se modifica ni se borra, con o
  sin `--bundle`.
  Pendiente: CI no ejercita el flujo con el toolchain real; validar en macOS (`os.replace` de carpetas,
  `O_NOFOLLOW`) y en Python 3.10/3.11 (ruta `onerror` de `remove_tree`; solo hay 3.12 aquí); reproducibilidad del
  pack entre versiones de git; `clean-toolchains` no barre restos de una ejecución matada con SIGKILL.
- Distribución reproducible y GitHub Actions para proyectos creados por el CLI;
  política de versiones y compatibilidad de actualizaciones. No confundir con
  el empaquetador del propio framework, que sí existe.
- La migración de formato 1 a 2 es la primera real y ya tiene pruebas locales;
  se conservan pruebas sintéticas para los contratos del motor y errores.
- Investigar el orden de enlazado de `perf` en árboles incrementales frente a
  builds limpios antes de prometer BIN reproducibles entre ambos. El ZIP sí es
  determinista para un conjunto fijo de artefactos.
- Eliminar la ruta local heredada de la toolchain en las herramientas de bajo nivel;
  el CLI utiliza la instalación resuelta y `CPCT_NEXT_PATH`.
- Plantilla de proyectos limitada a vídeo estándar y coordenadas Y de 8 bits.
  El perfil 160×288 tiene probado su modelo de memoria, pero sigue sin validación
  de temporización CRTC en hardware ni en varios tipos de CRTC.
- No existe validación en hardware real ni una garantía global de 50 Hz. Las cifras
  de rendimiento solo se aplican a las escenas y versiones medidas en el historial.
  El presupuesto histórico de tamaño de platformer necesita una comparación nueva
  antes de considerarlo cerrado; no se arrastra automáticamente como defecto actual.
- Colisión ECS: estado por sujeto y canal, no por pareja. Los límites exactos del
  renderer, animador y tilemaps están en sus contratos de referencia.
- Validación de RVM 2.1.20 y de BluePixel en Mac real pendiente según el historial;
  no se ha repetido en esta sesión.
- Deuda didáctica menor: cabeceras de rutinas en pasos iniciales/plantilla y uso
  consistente de «fotograma» frente a iteración de lógica. No bloquea esta tarea.

## Trabajo histórico ya resuelto

Los pools de fondos, la separación de `tools/`, la organización de `docs/`, la
migración ECS y la retirada de módulos anteriores ya tienen cierres posteriores
a las casillas que los proponían. No son tareas nuevas. Sus pruebas, SHA y medidas
se conservan en [project-history.md](docs/design/project-history.md).

## Cómo continuar

Leer primero este archivo y comprobar HEAD, sincronización y CI. Consultar el
historial solo para reconstruir una decisión o evidencia concreta. Después de cada
commit funcional registrar cambios, validaciones reales, límites y siguiente paso.
El manual canónico sigue siendo `docs/manual.html` y `docs/manual.pdf`; los cambios
funcionales requieren `make manual` y cobertura/checksum correctos.
