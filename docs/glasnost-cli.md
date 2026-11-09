# glasnost: interfaz única del SDK

`bin/glasnost` es la entrada de todo lo que se hace con el SDK. Mensajes en
castellano (predeterminado) e inglés: `--lang en`, o `GLASNOST_LANG=en`.
`--lang` solo admite `es` o `en`. El flag gana a la variable; de `GLASNOST_LANG`
se leen las dos primeras letras y un valor desconocido cae a castellano.

Primera parte de la fase 12 (P3). Sin `sudo`, sin tocar nada fuera del
repositorio salvo lo que se indica en «Alcance».

## Ayuda

`glasnost --help` (o `-h`, o `glasnost` a secas) lista los comandos agrupados por función, cada
uno con su explicación y todas sus opciones; `glasnost <comando> --help` o `glasnost help
<comando>` muestran la de un comando con su línea de uso. Sale en castellano o en inglés
(`--lang`). Se genera desde el propio parser, así que no puede quedar desactualizada; la
tabla de abajo es la referencia larga.

## Comandos

| Comando | Qué hace |
|---|---|
| `glasnost doctor [--network]` | Comprueba python3 >= 3.10, git, make, gcc, g++, bison, flex, cabeceras de Boost y CPCTelera Next. Sale con 1 si falta algo y dice cómo arreglarlo (con un lockfile inválido, muestra su error y sale con 1). `--network` comprueba también el acceso al repositorio de CPCTelera. |
| `glasnost install-toolchain [--dry-run] [--force]` | Descarga el commit fijado y compila SDCC, hex2bin, iDSK, 2cdt, cpc2cdt, img2cpc (convierte los PNG de `assets/src`), la biblioteca y zx7b. `--dry-run` solo lista los pasos. `--force` rehace desde cero. |
| `glasnost new [nombre] [--manifest F] [--title T] [--extended-memory] [--dir D] [--no-git] [--no-build]` | Crea un proyecto en `projects/<nombre>` (ver «Proyectos»). Sin nombre ni manifiesto, en una terminal, lanza el asistente. |
| `glasnost config [--title T] [--extended-memory \| --no-extended-memory] [--dry-run]` | Dentro de un proyecto: sin opciones muestra la configuración y regenera los ficheros de `generated/` si están desactualizados; con ellas regenera lo que posee glasnost. |
| `glasnost update [--dry-run]` | Dentro de un proyecto: lo actualiza al formato de este glasnost con migraciones consecutivas, en una rama de Git (ver «Actualizar proyectos»). |
| `glasnost rollback [--delete]` | Sale de una rama de actualización y vuelve a la rama de origen sin perder nada; `--delete` borra además la rama de actualización. |
| `glasnost projects [--dir D]` | Lista los proyectos de `projects/` con su rama Git (`*` si tienen cambios) y si están al día. |
| `glasnost build [ejemplo...]` | Fuera de un proyecto: `make generate` y `tools/build/build_examples.py` con el toolchain resuelto (todos los ejemplos si no se nombra ninguno). Dentro de un proyecto: compila ese proyecto. |
| `glasnost test` | Fuera de un proyecto: `make test`. Dentro: comprueba la coherencia del proyecto y que compila. |
| `glasnost run [ejemplo] [-- opciones]` | Abre el ejemplo (o el proyecto actual, sin nombre) en el emulador (`tools/glasnost/run_example.py`). Las opciones del emulador van tras `--`. Si no hay emulador configurado y estás en una terminal, te ofrece configurar uno (ver «Emulador»). |
| `glasnost emulator [--set RUTA] [--download [rvm\|bluepixel]] [--reset]` | Muestra el emulador que usa `run` y, en una terminal, permite cambiarlo. `--set` guarda un ejecutable (o un `.app` de macOS), `--download` baja Retro Virtual Machine (o BluePixel, en macOS), `--reset` borra la configuración. |
| `glasnost toolchains` | Lista los toolchains instalados (commit, completo o parcial, tamaño) y marca el que fija el lockfile. |
| `glasnost clean-toolchains [--yes] [--keep REV]` | Sin `--yes` solo muestra qué borraría. Con `--yes` borra todos los toolchains salvo el del lockfile y los `--keep` (commit completo, repetible). |
| `glasnost install-cli [--prefix DIR] [--dry-run] [--force]` | Crea el enlace simbólico `~/.local/bin/glasnost` hacia `bin/glasnost` de este SDK (sin `sudo`). Avisa si el directorio no está en el `PATH`. |
| `glasnost uninstall-cli [--prefix DIR]` | Quita ese enlace, solo si apunta a este SDK. |
| `glasnost path` | Imprime la ruta de CPCTelera Next en uso. |
| `glasnost version` | `git describe --tags --always` del SDK. |
| `glasnost help [comando]` | Lo mismo que `--help`, o la ayuda de un comando. |

Códigos de salida: 0 bien, 1 fallo (mensaje traducido en stderr), 2 uso
incorrecto, 130 interrumpido con Ctrl-C. Un error del sistema (carpeta no
escribible, `git` o `make` ausentes) sale con 1 y mensaje traducido, sin
traza. `build`, `test` y `run` devuelven el código de la herramienta que
ejecutan.

## Emulador

`glasnost run` necesita un emulador de CPC. El orden con que se elige:

1. `--emulator RUTA` tras `--` (solo esa ejecución).
2. La variable `GLASNOST_EMULATOR`.
3. El emulador guardado en `tools/emulators/emulator.json` (ignorado por git, dentro del
   SDK: no toca tu `HOME` ni tu shell).
4. Sin nada de lo anterior y en una terminal: `glasnost run` pregunta una vez.

```
No hay ningún emulador configurado para `glasnost run`.
  1) Usar uno que ya tengo en este equipo
  2) Descargar Retro Virtual Machine 2.1.20 para linux-x86_64 (~93 MB) en tools/emulators/
  3) Ahora no: solo mostrar la ruta de la imagen
  4) No volver a preguntar
```

En un Mac con Apple Silicon se añade, antes de «Ahora no», `Descargar la última versión de
BluePixel (johnlobo/BluePixel en GitHub, Apple Silicon)`; las opciones se numeran solas.

- **1** lista los emuladores que encuentra (AmSpiriT junto al repositorio, los del `PATH`,
  las `.app` de `/Applications` y `~/Applications`, lo ya descargado en `tools/emulators/`) y
  admite escribir otra ruta; un `.app` de macOS se resuelve a su ejecutable.
- **2** baja Retro Virtual Machine de su servidor oficial (`static.retrovm.org`) para tu
  sistema (Linux x86_64 o arm64, Windows x64, macOS), comprueba su SHA-256 contra el fijado en
  `tools/glasnost/emulator_setup.py` (una descarga distinta o corrupta no se instala), la deja en
  `tools/emulators/retro-virtual-machine-<versión>-<plataforma>/` y la guarda como emulador.
  En macOS monta el `.dmg` con `hdiutil`, copia el `.app` y lo desmonta.
- **BluePixel** consulta el último release de `johnlobo/BluePixel` en la API de GitHub, baja su
  zip de macOS arm64, comprueba el SHA-256 que publica GitHub para ese fichero (un release sin
  digest se rechaza), lo extrae en `tools/emulators/bluepixel-<tag>-macos-arm64/` y lo guarda.
  Se lanza con `imagen [/A] [/SYM:fichero.noi]`.
- **3** no guarda nada; se volverá a preguntar. **4** (solo si no hay ninguno guardado) deja de
  preguntar: sin terminal, o tras elegirla, `run` sigue usando lo que encuentre y si no, imprime
  la ruta de la imagen, hasta que ejecutes `glasnost emulator`. Con un emulador ya guardado,
  `glasnost emulator` no ofrece olvidarlo (para eso, `--reset`).

La siguiente vez `glasnost run` (y `make run`) usa el emulador guardado sin preguntar nada. Sin
terminal (CI, `make run` con la entrada redirigida) no se pregunta y se mantiene el
comportamiento anterior: se usa lo que se encuentre o se imprime la ruta de la imagen. Si el
emulador guardado desaparece, se avisa y se vuelve a ofrecer. Las rutas dentro del SDK se
guardan relativas, así que mover o copiar el SDK no las rompe.

Cómo se lanza cada tipo, siempre con el fichero de símbolos (`obj/<nombre>.noi`) cuando el
emulador tiene opción para ello:

| Emulador | Línea de comandos | Símbolos |
|---|---|---|
| BluePixel | `imagen.dsk /A /SYM:<nombre>.noi` (`/A` teclea `RUN"<programa>` por ti) | sí |
| Retro Virtual Machine | como `cpct_rvm` de CPCtelera: `-ns -b=<máquina> -i= imagen -c=RUN"<nombre>"\n`; CDT con `-p -w`; SNA con `-s` | no hay opción conocida |
| Otros (AmSpiriT...) | la imagen como único argumento | no |

Con BluePixel y Retro Virtual Machine, `run` abre el **DSK** (arranca solo); con cualquier otro
emulador abre el CDT si existe. `-- --image cdt|dsk` fuerza el formato (un CDT en BluePixel no
arranca solo: hay que escribir `RUN"` tras darle a reproducir). `run` imprime la línea de comandos
completa que lanza.

La máquina de Retro Virtual Machine es `cpc6128` para DSK (los ejemplos con memoria extendida la
necesitan) y `cpc464` para CDT y SNA. **No se ha probado con la 2.1.20**: la invocación sale del
script de CPCtelera, escrito para la 2.0 beta. Se puede fijar a mano en `emulator.json` con
`"args": ["-ns", "-b=cpc6128", "-i=", "{image}", ...]`, donde `{image}` es el CDT/DSK y
`{name}` el nombre del programa (8 caracteres).

## Lockfile

`toolchain.lock.json` fija el toolchain:

```json
{"schema": 1, "cpctelera_next": {"url": "https://github.com/Arnaud6128/cpctelera.git", "rev": "<40 hex>"}}
```

`rev` es un commit completo (nunca una rama o etiqueta), `url` es https. Un
lockfile inválido se rechaza con un mensaje que dice qué falla.
`.github/workflows/release.yml` fija el mismo commit y un test falla si
divergen. Cambiar de versión de CPCTelera Next es cambiar `rev` en un PR.

## Dónde vive el toolchain

`.toolchain/cpctelera-next/<commit>/` (ignorado por Git). `cpctelera/` dentro
de esa carpeta es lo que recibe `CPCT_NEXT_PATH`. Resolución, en este orden:

1. `CPCT_NEXT_PATH` si está definida (desarrollo contra una copia local; se
   valida igual que una instalación administrada).
2. La instalación administrada del commit del lockfile, solo si lleva la marca
   `.glasnost-complete`.

Sin ninguna de las dos, `build`, `test`, `run` y `path` paran con «Ejecuta
`glasnost install-toolchain`». `GLASNOST_TOOLCHAIN_DIR` cambia la carpeta base
(tests e instalaciones en otro disco). Esa variable y `CPCT_NEXT_PATH` se
convierten a ruta absoluta, así que valen rutas relativas desde cualquier
directorio.

`projects/` se añade también a `.gitignore` (decisión del plan: los proyectos
son repositorios independientes y el Git del framework no los versiona); aún
no hay comando que los cree (fase 13).

## Instalación

Mismos pasos que la publicación de releases: `git init`, `fetch --depth=1` del
commit exacto, `checkout --detach`, comprobación de que `HEAD` es el commit del
lockfile, `make` de cada herramienta y de la biblioteca, comprobación de
ficheros (no vacíos y ejecutables) y marca de instalación completa, que se
escribe la última.

- Los prerrequisitos de compilación **no se instalan**: `doctor` y
  `install-toolchain` los nombran y en Debian/Ubuntu el comando es
  `sudo apt install build-essential bison flex libboost-dev` (lo ejecutas tú).
- Un fallo deja el trabajo parcial en su carpeta, sin marca. Repetir
  `install-toolchain` continúa desde ahí (`make` salta lo ya compilado);
  los ficheros versionados modificados vuelven al commit fijado
  (`checkout -f`) y la marca antigua se borra al empezar. `--force` borra la
  carpeta de ese commit y empieza de cero.
- Dos instalaciones del mismo commit a la vez no pueden convivir: la segunda
  falla con un aviso (bloqueo `flock` en `.toolchain/cpctelera-next/`).
- La comprobación final verifica que cada fichero existe, no está vacío y es
  ejecutable; **no ejecuta** las herramientas (límite conocido).
- Repetir sobre una instalación completa no hace nada.
- Solo este comando usa la red. `GLASNOST_CPCTELERA_URL` sustituye la URL del
  lockfile (espejos, tests) y solo acepta `https://` o `file:///`; cualquier
  otro valor (opciones, `ext::`, `ssh://`) se rechaza.

## Proyectos

Un proyecto es una carpeta con la forma de un ejemplo (tiene `example.json`)
más `glasnost.project.json` (esquema, plantilla, versión del framework con la
que se creó y título). Se reconoce desde cualquier subcarpeta, o con
`--project DIR`.

```sh
glasnost new minave                      # asistente en una terminal; con nombre, sin preguntas
glasnost new --manifest minave.json      # manifiesto: {"schema":1,"name":"minave","title":"Mi nave",
                                         #   "extended_memory":false,"git":true}
cd projects/minave && glasnost run       # RUN"MINAVE en el emulador
```

El asistente, el manifiesto y las opciones pasan por la misma validación y
producen exactamente los mismos ficheros (hay un test que lo comprueba).
Las opciones pisan al manifiesto.

**Primer juego.** [`docs/first-game.md`](first-game.md) parte de lo que crea `new` y
añade, en tres pasos con el juego compilando en cada uno, un mapa propio
(PNG y TMX importados), animación y colisiones con marcador. Un test aplica los pasos y los compila.

**Qué crea `new`** (plantilla `ecs-welcome`: una nave que se mueve con el
cursor y tres drones que patrullan, sobre un fondo de mapa, con el ECS del
framework):
`main.s` y `common.inc` (tu código, con la convención de `common.inc`),
`assets/` (sprites y tileset en PNG, mapa en TMX comprimido con ZX7B y
paleta; `assets/generated/` lo escribe la conversión al compilar, no lo edites),
`example.json`, `generated/` (título y perfil ECS), `README.md` en el idioma
elegido y `.gitignore`. Compila el proyecto antes de dar nada por bueno; si
falla borra lo creado. Después hace `git init` y el primer commit (repositorio
independiente del framework; si el commit falla por falta de identidad Git,
avisa y deja el proyecto). `new` nunca escribe en una carpeta existente.

**Quién es dueño de qué.** Tuyo: `main.s`, `common.inc`, README, y en
`example.json` las claves `modules`, `game_sources`, `ecs` y cualquier otra
que añadas. De glasnost: `generated/*` y en `example.json` las claves `name`,
`amsdos_name`, `profile`, `transparency` y `extended_memory`. `config` solo
reescribe lo de glasnost y calcula todo antes de escribir (un valor no válido
no toca nada). Escribe cada fichero con otro temporal y reemplazo, de modo que
cada fichero es atómico pero el conjunto no: si el proceso muere a mitad,
`glasnost test` y `build` lo detectan (ficheros generados desactualizados) y
`glasnost config` lo repara. `--dry-run` lista lo que cambiaría. `example.json` se reescribe con sangría de 2
espacios.

**Usar un sistema del framework (colisión, animación, ...).** Añade su
componente en `ecs.components` y su módulo en `modules` de `example.json`, y
ejecuta `glasnost config` sin opciones: regenera `generated/ecs_profile.inc` (y
`project.inc`) y no toca nada más, ni siquiera el formato de tu `example.json`.
Es lo que pide `glasnost build` cuando dice que el perfil ECS está
desactualizado. `--dry-run` muestra qué regeneraría. Si el componente o la
combinación no es válido, `config` lo dice y no escribe nada.

**Límites actuales.**
- La carpeta del proyecto debe llamarse como su `name` (`example.json`): si la
  renombras, `build` y `test` lo rechazan. `config` no cambia el nombre.
- `--project DIR` debe apuntar a un proyecto; si no, falla (no cae a los
  ejemplos del framework).
- Solo el perfil de vídeo `standard` (160x200): el `experimental` (288
  líneas) necesita coordenadas Y de 16 bits y la plantilla usa 8. `config
  --profile` existe, pero solo acepta `standard` hasta que haya plantilla para
  el otro.
- Los títulos usan las letras que dibuja la fuente (A-Z, cifras, espacio y
  `! - / : > ? @`, hasta 30; se pasan a mayúsculas).
- `glasnost.project.json` guarda la versión del framework para que la fase 14
  (actualización y migraciones) sepa de dónde parte; hoy no se compara.
- GitHub Actions, empaquetado y paquetes compartidos del proyecto son de las
  fases 14 a 16.

## Actualizar proyectos

El **formato** de un proyecto (`format` en `glasnost.project.json`; sin la clave
es 1) dice qué espera de glasnost. Este glasnost conoce hasta
`glasnost_project.FORMAT` (hoy 1, el primero). Subir de formato es una cadena de
migraciones de un paso, N a N+1: no se salta ninguna y un hueco es un error.
`framework` (la versión de glasnost con la que se hizo o actualizó) es
informativo; lo único que decide es el formato.

```sh
glasnost projects                 # ¿cuáles están al día?
glasnost update --dry-run         # plan: pasos, ficheros que se reescriben, tareas manuales
glasnost update                   # rama glasnost-update-N-to-M, migra, regenera, prueba y confirma
git merge glasnost-update-1-to-2  # si todo va bien (desde la rama de origen)
glasnost rollback [--delete]      # si no: vuelve a la rama de origen
```

**Qué exige `update`** (y si algo falta, no toca nada): el repositorio Git
propio del proyecto (el que crea `new`; uno ajeno que lo contenga no vale),
árbol limpio (sin modificados ni sin seguimiento), una rama (no HEAD
desacoplado), que no exista ya la rama de actualización y un toolchain
instalado. `--dry-run` no exige nada de eso.

**Qué hace:** crea `glasnost-update-N-to-M` (guarda de qué rama parte en
`branch.<rama>.glasnostBase`), aplica las migraciones, regenera `generated/*`,
comprueba la coherencia, compila y hace el commit con los pasos y las tareas
manuales en el mensaje. Tu rama de origen no se modifica. **Si algo falla**
(no compila, error de escritura, commit imposible o rechazado por un hook,
Ctrl-C en cualquier punto) vuelve a la rama de origen exactamente como estaba
y borra la rama de actualización; los ficheros que iba a escribir se restauran
byte a byte aunque Git no los siga (un `generated/` en `.gitignore`) y las
carpetas que tuvo que crear se quitan. Si ni siquiera eso es posible, lo dice
con un aviso. Lo compilado en `build/` no se restaura (es salida ignorada).

**Qué puede tocar una migración.** Es una función pura sobre
`glasnost.project.json` y `example.json` (por ejemplo, renombrar un módulo del
framework en `modules`): nunca ve `main.s` ni `common.inc`, así que no puede
editar tu código. Si un formato exige cambiar tu código, la migración lo
devuelve como **tarea manual**: aparece en la vista previa, en el informe y en
el commit, y `update` sale con código 3 si además el proyecto no compila
hasta que la hagas (la rama se conserva en ese caso; sin tareas declaradas, un
fallo de compilación deshace todo). Una migración no puede renombrar el
proyecto ni fijar el formato (lo hace el motor), y sus errores se detectan
antes de escribir nada.

**Añadir una migración** (cuando cambie lo que glasnost genera o espera): sube
`FORMAT`, añade `MIGRATIONS[N] = Migration(N, "resumen", apply)` en
`tools/glasnost/glasnost_update.py` y su prueba, en el mismo commit; un test falla si
`FORMAT` sube sin migración.

**`rollback`** solo actúa en una rama `glasnost-update-*` creada por glasnost,
exige árbol limpio (no pierde trabajo sin confirmar) y conserva la rama de
actualización salvo con `--delete`, que además se niega (código 1, la rama
se conserva) si en ella hay commits tuyos aparte del de la actualización. Un proyecto de un formato **más nuevo**
que el de este glasnost se rechaza en `build`, `test` y `update`: nunca se
degrada.

`update` y `rollback` no usan la red (un test lo comprueba) y `make` nunca
actualiza nada.

## Instalar el comando y varias versiones

`install-cli` solo crea un enlace (`GLASNOST_BIN_DIR` o `--prefix` cambian
el directorio; las rutas relativas se resuelven desde donde ejecutas).
Nunca sobrescribe un fichero o enlace ajeno sin `--force`, y `uninstall-cli`
solo borra un enlace que apunte a este SDK. Ninguno toca el SDK, el
toolchain, `projects/` ni paquetes.

Varias versiones del framework pueden coexistir con distintos CPCTelera Next
porque cada toolchain vive en su carpeta de commit. Cada copia del SDK tiene su
`.toolchain/`; para compartir descargas entre copias, apunta todas a la misma
carpeta con `GLASNOST_TOOLCHAIN_DIR`. En ese caso `clean-toolchains` de una
copia vería los commits que fijan las otras: protégelos con `--keep` (la
vista previa sin `--yes` existe para eso). `clean-toolchains` solo considera
carpetas reales con nombre de commit de 40 caracteres hexadecimales: ignora
cualquier otra cosa y no sigue enlaces simbólicos (ni en las entradas ni en `cpctelera-next/`). Con
`GLASNOST_TOOLCHAIN_DIR` definida, avisa de que la carpeta puede ser compartida. Si hay una instalación de
ese commit en marcha, falla en vez de borrarla.

## Alcance de esta parte y lo que falta

Hecho (fase 12 completa): lockfile, resolución, `doctor`, instalación,
`build`/`test`/`run`, instalador del comando, listado y limpieza de toolchains.
La creación de proyectos (fase 13, parte 1) está en «Proyectos».

Los ejemplos y herramientas siguen aceptando `CPCT_NEXT_PATH` y
`--cpct-path` directamente; conservan una ruta predeterminada heredada que el
CLI nunca usa porque siempre fija la variable.

## Pruebas

`tests/test_glasnost_update.py` (56 casos) cubre el motor de migraciones y `update`/`rollback`/`projects` contra repositorios Git reales (rama, árbol sucio, repositorio ajeno, HEAD desacoplado, ramas con barra, hook que rechaza, ficheros ignorados por Git, Ctrl-C en compilar y en commit, fallos de compilación, escritura y commit, Ctrl-C, tareas manuales, sin red), más un caso con compilación real.

`tests/test_glasnost_project.py` (79 casos) cubre el generador, `new`, `config` y los comandos dentro de un proyecto, incluida la compilación real de la plantilla en cada configuración (se omite sin toolchain). `tests/project_smoke.py` es el smoke opcional en emulador (CPC 464, 6128 y memoria extendida): la nave arranca, se mueve y no sale del área.

`tests/test_glasnost.py` (76 casos, locales, sin red): mensajes es/en con las
mismas claves y marcadores, lockfile válido e inválidos, coincidencia con el
workflow de release, instalación completa contra un repositorio Git de
juguete con la forma de CPCTelera Next, fallos por paso, reanudación,
`--force`, bloqueo, URL hostil, listado y limpieza de toolchains (símbolos, entradas ajenas, bloqueo, `--keep`), instalador del enlace, errores del sistema, Ctrl-C, commit equivocado, prerrequisitos ausentes, resolución y
validación del toolchain, `doctor`, composición de comandos y el script
`bin/glasnost` real. El CLI no usa ningún LLM, así que no tiene evals.
