# glasnost: interfaz única del SDK

`bin/glasnost` es la entrada de todo lo que se hace con el SDK. Mensajes en
castellano (predeterminado) e inglés: `--lang en`, o `GLASNOST_LANG=en`.
`--lang` solo admite `es` o `en`. El flag gana a la variable; de `GLASNOST_LANG`
se leen las dos primeras letras y un valor desconocido cae a castellano.

Primera parte de la fase 12 (P3). Sin `sudo`, sin tocar nada fuera del
repositorio salvo lo que se indica en «Alcance».

## Comandos

| Comando | Qué hace |
|---|---|
| `glasnost doctor [--network]` | Comprueba python3 >= 3.10, git, make, gcc, g++, bison, flex, cabeceras de Boost y CPCTelera Next. Sale con 1 si falta algo y dice cómo arreglarlo (con un lockfile inválido, muestra su error y sale con 1). `--network` comprueba también el acceso al repositorio de CPCTelera. |
| `glasnost install-toolchain [--dry-run] [--force]` | Descarga el commit fijado y compila SDCC, hex2bin, iDSK, 2cdt, cpc2cdt, la biblioteca y zx7b. `--dry-run` solo lista los pasos. `--force` rehace desde cero. |
| `glasnost new [nombre] [--manifest F] [--title T] [--extended-memory] [--dir D] [--no-git] [--no-build]` | Crea un proyecto en `projects/<nombre>` (ver «Proyectos»). Sin nombre ni manifiesto, en una terminal, lanza el asistente. |
| `glasnost config [--title T] [--extended-memory \| --no-extended-memory] [--dry-run]` | Dentro de un proyecto: sin opciones muestra la configuración; con ellas regenera lo que posee glasnost. |
| `glasnost build [ejemplo...]` | Fuera de un proyecto: `make generate` y `tools/build_examples.py` con el toolchain resuelto (todos los ejemplos si no se nombra ninguno). Dentro de un proyecto: compila ese proyecto. |
| `glasnost test` | Fuera de un proyecto: `make test`. Dentro: comprueba la coherencia del proyecto y que compila. |
| `glasnost run [ejemplo] [-- opciones]` | Abre el ejemplo (o el proyecto actual, sin nombre) en el emulador (`tools/run_example.py`). Las opciones del emulador van tras `--`. |
| `glasnost toolchains` | Lista los toolchains instalados (commit, completo o parcial, tamaño) y marca el que fija el lockfile. |
| `glasnost clean-toolchains [--yes] [--keep REV]` | Sin `--yes` solo muestra qué borraría. Con `--yes` borra todos los toolchains salvo el del lockfile y los `--keep` (commit completo, repetible). |
| `glasnost install-cli [--prefix DIR] [--dry-run] [--force]` | Crea el enlace simbólico `~/.local/bin/glasnost` hacia `bin/glasnost` de este SDK (sin `sudo`). Avisa si el directorio no está en el `PATH`. |
| `glasnost uninstall-cli [--prefix DIR]` | Quita ese enlace, solo si apunta a este SDK. |
| `glasnost path` | Imprime la ruta de CPCTelera Next en uso. |
| `glasnost version` | `git describe --tags --always` del SDK. |

Códigos de salida: 0 bien, 1 fallo (mensaje traducido en stderr), 2 uso
incorrecto, 130 interrumpido con Ctrl-C. Un error del sistema (carpeta no
escribible, `git` o `make` ausentes) sale con 1 y mensaje traducido, sin
traza. `build`, `test` y `run` devuelven el código de la herramienta que
ejecutan.

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

**Qué crea `new`** (plantilla `ecs-welcome`: una nave que se mueve con el
cursor y tres drones que patrullan, sobre el ECS del framework):
`main.s` y `common.inc` (tu código, con la convención de `common.inc`),
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

`tests/test_glasnost_project.py` (72 casos) cubre el generador, `new`, `config` y los comandos dentro de un proyecto, incluida la compilación real de la plantilla en cada configuración (se omite sin toolchain). `tests/project_smoke.py` es el smoke opcional en emulador (CPC 464, 6128 y memoria extendida): la nave arranca, se mueve y no sale del área.

`tests/test_glasnost.py` (76 casos, locales, sin red): mensajes es/en con las
mismas claves y marcadores, lockfile válido e inválidos, coincidencia con el
workflow de release, instalación completa contra un repositorio Git de
juguete con la forma de CPCTelera Next, fallos por paso, reanudación,
`--force`, bloqueo, URL hostil, listado y limpieza de toolchains (símbolos, entradas ajenas, bloqueo, `--keep`), instalador del enlace, errores del sistema, Ctrl-C, commit equivocado, prerrequisitos ausentes, resolución y
validación del toolchain, `doctor`, composición de comandos y el script
`bin/glasnost` real. El CLI no usa ningún LLM, así que no tiene evals.
