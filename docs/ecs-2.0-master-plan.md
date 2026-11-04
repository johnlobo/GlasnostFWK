# Plan maestro de migración a GlasnostFWK ECS 2.0

Estado del plan: aprobado para ejecución por fases el 2026-11-03.

Este documento es la referencia estable de alcance y decisiones. El punto
operativo exacto para retomar una sesión se mantiene en `PROJECT_STATUS.md`,
sección **Migración ECS 2.0: estado operativo**.

La especificación normativa de la fase 1 está en `docs/ecs-abi-2.0.md`. La
puerta G1 fue aprobada el 2026-11-03; las implementaciones posteriores deben
registrar cualquier aclaración de ABI antes de cambiar el contrato.

## Objetivo

Sustituir la arquitectura actual por un modelo Entity-Component-System ligero
AoS, adecuado para Z80 y coherente con `model01` y `PocketFever`, sin reescribir
los servicios independientes del framework. La versión final no conservará
APIs, adaptadores, ejemplos ni documentación de la arquitectura no ECS; Git sí
mantendrá su historial.

## Decisiones vinculantes

- El desarrollo se realiza en `ecs-v2`; `main` conserva el último estado no
  ECS estable hasta alcanzar paridad.
- Entidades AoS de tamaño fijo. Un proyecto genera una sola estructura de
  entidad y puede declarar varios managers con ella.
- Cada manager tiene capacidad fija. Sus slots son estables, no se compactan y
  se reutilizan después de quedar libres.
- Las referencias persistentes son punteros directos. No se usa contador de
  generación; el consumidor debe invalidarlas al destruir la entidad apuntada.
- La entidad contiene directamente sus atributos. Los sistemas no almacenan
  estado propio de cada entidad.
- Campos obligatorios: máscara de componentes, estado, tipo, X, Y, anchura,
  altura y datos de render.
- X y anchura se expresan en bytes de pantalla; Y y altura, en líneas de
  píxel. Anchura y altura son `u8`. El formato de X/Y y velocidad se selecciona
  al configurar el proyecto (`u8`, `u16`, `fixed_8_8` y combinaciones
  compatibles).
- La máscara de componentes es siempre de 16 bits. Sus bits se asignan de forma
  determinista al generar el proyecto. Se rechazan perfiles con más de 16
  componentes.
- Los componentes habilitados incorporan sus campos a todos los registros del
  perfil; la máscara individual decide qué sistemas procesan cada entidad.
- La coincidencia de un sistema es inclusiva: deben estar presentes todos sus
  bits requeridos y puede haber bits adicionales.
- `status` separa `FREE`, `ACTIVE`, `PENDING_DESTROY` y `DISABLED` de la
  máscara de componentes.
- Crear, reutilizar slots y cambiar máscaras solo se permite entre recorridos.
  Un callback puede marcar `PENDING_DESTROY`; render restaura su fondo antes de
  que el manager libere el slot al final del frame.
- Las entidades se crean copiando una plantilla completa. Al destruir solo se
  cambia el estado; la siguiente plantilla sobrescribe el registro.
- Los recorridos se ejecutan en el bucle principal, no son reentrantes ni
  seguros desde IRQ.
- El juego invoca los sistemas explícitamente en el orden requerido. Cada
  llamada recorre todas las entidades compatibles del manager recibido.
- `behavior` evalúa todas las entidades `ACTIVE|BEHAVIOR` una vez por llamada.
  Sus programas son inmutables y compartibles; cursor, temporizador y estado
  pertenecen a cada entidad.
- Animación comparte descriptores inmutables y conserva frame/temporizador por
  entidad.
- Existe un solo componente `COLLISION`; flags internos distinguen
  `COLLIDER` y `COLLISIONABLE`. El sistema emite `ENTER`, `STAY` y `EXIT` a un
  callback de juego y usa un buffer fijo configurable con overflow observable.
- La colisión entre entidades permanece separada de la colisión con tilemaps y
  puede operar dentro de un manager o entre dos managers.
- Los flags `VISIBLE`, `DIRTY`, `MASKED`, `RECOLOR` y de fondo son estado de
  render, no componentes ECS. Los cambios relevantes marcan `DIRTY`
  explícitamente; render propaga solapamientos.
- Render recibe una escena con uno o varios managers, combina globalmente sus
  entidades y usa `sort_y = y + sort_offset_y`.
- Se mantiene el ciclo: sistemas, prepare, VSYNC, restore, draw y liberación de
  destruidas.
- Sistema/IRQ, vídeo hardware, audio, tilemaps, recursos, bancos, disco,
  compresión, texto y ventanas siguen siendo servicios globales. Input de
  entidades, behavior, movimiento/física, colisión, animación y render son
  sistemas ECS.
- El núcleo obligatorio de un juego generado incluye sistema, input básico,
  entity manager, array de entidades, vídeo, render y texto.
- Debug y release comparten ABI. Debug añade validaciones; release se usa para
  rendimiento. Los fallos recuperables devuelven carry y código en A.

## Configuración y generación

- El manifiesto es la fuente de verdad. Los offsets, máscaras, tablas y perfil
  se generan y se versionan en Git; el build falla si están desactualizados.
- La reconfiguración muestra campos añadidos/eliminados, cambios de tamaño e
  incompatibilidades antes de escribir.
- Archivos editables y generados viven separados; reconfigurar nunca
  sobrescribe código del usuario.
- Tipos iniciales: `u8`, `i8`, `u16`, `i16`, `fixed_8_8`, `pointer` y
  `bytes[n]`.
- Se admiten campos universales, componentes y sistemas propios del juego. Los
  esqueletos propios solo se crean si no existen.
- El importador convierte dimensiones gráficas a bytes según el modo y rechaza
  sprites no representables por las rutinas alineadas seleccionadas.

## SDK y ciclo de vida

- `glasnost` será la interfaz única, bilingüe (castellano predeterminado e
  inglés), instalada sin `sudo` en `GlasnostFWK/bin` y opcionalmente
  `~/.local/bin`.
- CPCTelera Next es un toolchain administrado dentro de
  `.toolchain/cpctelera-next/<commit>`, fuera de Git. Cada versión del framework
  fija una revisión compatible y valida biblioteca, cabeceras, cfg, SDCC,
  BIN/CDT/DSK, conversores y herramientas.
- Pueden coexistir varias versiones de GlasnostFWK y CPCTelera Next. El lockfile
  fija ambas; una ruta local puede sustituirlas durante desarrollo.
- Los proyectos se crean por defecto en `projects/`, ignorada por el Git del
  framework. Cada proyecto es un repositorio Git independiente. Actualizar,
  reparar o desinstalar el SDK no puede borrar proyectos, paquetes ni backups.
- El creador funciona de modo interactivo o desde manifiesto, genera un juego
  compilable con mensaje de bienvenida, BIN/CDT/DSK, debug/release, pruebas,
  documentación y primer commit validado.
- Las actualizaciones son explícitas: requieren Git limpio, vista previa, rama,
  migraciones consecutivas, regeneración, pruebas y rollback. `make` nunca
  consulta la red ni actualiza dependencias.
- Versionado semántico para framework, proyectos y paquetes. Se mantiene la
  mayor actual y la anterior; las más antiguas siguen instalables sin soporte
  activo.
- El SDK funciona offline una vez instaladas las dependencias y puede exportar
  un bundle verificable. Linux x86_64 y WSL2 son las plataformas oficiales
  iniciales.
- Cada proyecto ofrece GitHub Actions y empaquetado reproducible con binarios,
  fuentes correspondientes, checksums, manifiesto, lockfile, licencias,
  procedencia y validaciones reales. Publicar repositorio o release siempre
  requiere autorización separada.
- GlasnostFWK es GPL-3.0; los proyectos generados usan `GPL-3.0-only` por
  defecto y conservan avisos y obligaciones de sus dependencias.
- El workspace admite paquetes compartidos versionados, con repositorio,
  licencia, prefijo único, pruebas, compatibilidad, dependencias transitivas,
  una versión resuelta por paquete, caché GitHub y override local.
- El SDK gestiona backups/restauración, archivado, renombrado y borrado seguro.
  Las dependencias descargadas se fijan, verifican y activan solo tras validar.
- Los emuladores son herramientas opcionales mediante adaptadores de
  capacidades (`run`, headless, captura, memoria, stop).

## Prioridades y fases

### P0: referencia fiable

0. Cerrar el estado actual: resolver el smoke pendiente de `platformer`,
   validar, documentar, commit/push de `main` y crear `ecs-v2`.
1. Especificar formalmente ABI, layouts, registros, errores y restricciones.

### P1: ECS jugable

2. Entity manager: slots estables, ciclo de vida, plantillas y recorrido por
   máscara. **Completada el 2026-11-03.**
3. Generador de perfiles y validación del manifiesto. **Completada el
   2026-11-04.**
4. Sistemas ECS de behavior y movimiento. **Completada localmente el
   2026-11-04; cierre remoto pendiente de registrar.** Hito `2.0.0-alpha.1`.
5. Crear `examples/platformer_ecs` sin alterar la referencia actual.

### P2: paridad y sustitución

6. Input de entidades, física principal y tilemaps.
7. Colisiones ECS y eventos de contacto.
8. Animación ECS.
9. Render ECS multi-manager; fase de mayor riesgo.
10. Paridad completa y rendimiento de `platformer`. Hito `2.0.0-beta.1`.
11. Migrar consumidores y eliminar todo rastro activo no ECS. Hito
    `2.0.0-beta.2`.

### P3: SDK autocontenido

12. CLI e instalador, versiones y CPCTelera Next interna.
13. Creador/reconfigurador de proyectos y proyecto de bienvenida.
14. Actualización, migraciones, rollback y ciclo local de proyectos.

### P4: ecosistema

15. Paquetes compartidos.
16. Offline, backups, emuladores, CI, publicación y releases.

### P5: cierre

17. Documentación completa, instalación limpia, validación final, retirada
    de compatibilidad y releases `2.0.0-rc.1` / `2.0.0`.

## Política de validación y commits

- Durante una fase: pruebas focalizadas, `make check` con consumidores
  afectados y un smoke CPC 6128 si cambia Z80 ejecutable.
- Al cerrar una fase: una única regresión global `make test`, debug/release,
  manual/checksums si cambia API, `PROJECT_STATUS.md`, commit y push a
  `ecs-v2`.
- CPC 464 se reserva para cambios dependientes del modelo/memoria/render y
  cierres de hitos o release.
- Cada commit registra SHA, sincronización, funcionalidad, validaciones reales,
  límites y siguiente paso. No se afirma hardware real sin probarlo.

## Puertas de avance

- G0: referencia no ECS limpia y reproducible.
- G1: ABI ECS revisado antes de implementar sistemas.
- G2: vertical ECS jugable antes de migrar todo el portfolio.
- G3: paridad y rendimiento aceptados antes de sustituir `platformer`.
- G4: cero consumidores y cero APIs no ECS antes del RC.
- G5: instalación limpia, proyecto nuevo, actualización/rollback, paquete,
  offline y backup/restore demostrados antes de 2.0.0.

## Riesgos prioritarios

1. Complejidad y coste de `entity_render`.
2. Coste de recorrer todos los slots por cada sistema.
3. Cambios de ABI al reconfigurar perfiles.
4. Límite de 16 componentes.
5. Destrucción visual y referencias directas a slots reutilizados.
6. Instalación, tamaño y portabilidad de CPCTelera Next.
7. Seguridad de proyectos almacenados dentro del SDK.
8. Resolución, licencias y reproducibilidad de paquetes.

No se introducen caches de vistas, layouts alternativos ni optimizaciones sin
medir primero el cuello de botella real.
