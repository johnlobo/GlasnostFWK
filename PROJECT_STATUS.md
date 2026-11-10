# Estado operativo del proyecto

Actualizado: 2026-11-10 UTC. Este documento contiene el estado vigente y los
próximos pasos. El [historial por fases](docs/design/project-history.md) conserva
las decisiones, mediciones y validaciones antiguas sin reescribirlas. Una casilla
abierta en ese historial no implica una tarea pendiente hoy.

## Rama, commits y validación

- Rama: `refactor/examples-validations`, publicada en `origin`.
- Implementación: `c2b4bb91d3e32287f25717291db5f7ef42542667`,
  «Reorganiza ejemplos públicos y validaciones internas».
- Registro de sincronización: `9c93f13065e43a9936ad324d8eda6d8a28c177d6`.
  SHA remoto verificado en la sesión anterior; se comprobará el nuevo HEAD al subir.
- Base de la rama: `846047ffe0e7c7052b8cd41004d9762a06eacb7f`.
- Validación local de la reorganización: `make test`, 588 pruebas host correctas
  en 102,778 s, 22 BIN, 20 CDT y DSK de 24 entradas (22 programas y 2 payloads).
- `make -C framework/validations/ecsmanager` correcto. Paquete local
  `0.2.0-reorg`: dos ZIP idénticos, SHA256 correcto y 45 archivos.
- Smoke AmSpiriT-Lite CPC 6128: `text` y `ecsanimation` correctos; el primero
  comprueba texto/números en VRAM y el segundo el registro frente al modelo Python.
- Manual HTML/PDF y checksum regenerados; informe de tamaños actualizado.
- PR de esta rama: [#42](https://github.com/johnlobo/GlasnostFWK/pull/42), CI en curso. No hay nueva release.
  Última versión publicada registrada: `v0.2.0` (histórica; no revisada en remoto aquí).

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
  los programas todavía utilizan `example.json`.
- `make examples` construye ejemplos públicos; `make validations`, los internos;
  `make test` y `make release` construyen ambos y el DSK común. `diskload` y `perf`
  declaran solo DSK. El ZIP separa ejemplos y validaciones.
- BluePixel headless integrado desde `07dc833` de `main`: adaptador stdio, smoke
  determinista de `nave` y ejecución en CI. El código y la documentación se conservan
  al resolver los conflictos con esta reorganización; validación combinada pendiente.
  El CI compila BluePixel fijado en `c5e2437b4db4eb543a47b90fa8fccb90c448664f` (API 1.4).
- CLI con toolchain fijada, creación/configuración de proyectos, repositorio y remoto
  propios, actualización con migraciones y rollback. Formato de proyecto actual: 1.
- Toolchain fijada: CPCTelera Next `11e61fe30175ad7b328de9bcd859c46fd61b26a5`.
  Los fuentes Z80 del framework viven en `framework/src/`, las herramientas en
  `tools/{glasnost,build,dev}` y la documentación en `docs/{guide,reference,design}`.

## Próximos pasos autorizados, por orden

1. Separación de estado e historial completada en `b0aff2a`; estructura (7 pruebas)
   y ABI (9 pruebas) correctos.
2. Abrir PR de reorganización y documentación, esperar CI «Host tests and CPC builds»
   y fusionar con squash. No empujar directamente a `main`.
3. Cambiar `example.json` por `glasnost.manifest.json` en una rama posterior:
   herramientas, ejemplos, validaciones, guías y pruebas, con migración segura para
   proyectos existentes. Todavía no implementado.

## Pendientes de producto y límites vigentes

- Distribución reproducible y GitHub Actions para proyectos creados por el CLI;
  política de versiones y compatibilidad de actualizaciones. No confundir con
  el empaquetador del propio framework, que sí existe.
- La infraestructura de migraciones solo tiene pruebas sintéticas hasta el formato 1;
  el cambio de manifiesto deberá incorporar la primera migración real.
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
