# Procedencia y revisiones

Reconocimiento realizado el 2026-10-25 UTC. Los `HEAD` remotos se consultaron
con `git ls-remote --symref`; coincidían con los checkouts examinados.

| Proyecto | Remoto | Rama usada | SHA completo | Ramas visibles relevantes | Licencia comprobada |
|---|---|---|---|---|---|
| model01 | `https://github.com/johnlobo/model01.git` | `main` | `06302aefcfb1c19ab8436df657d2f49f82fc5b55` | `main`, `wip-shoot-mem` | GPL-3.0 en `LICENSE`; varios fuentes declaran LGPL-3.0-or-later |
| boop | `https://github.com/johnlobo/boop.git` | `main` | `33e4406ec468ce05ae3caf29fd14190529eeeac8` | `main` | Sin licencia de repositorio (`NOASSERTION`); fuentes examinados declaran LGPL-3.0-or-later |
| DeckTower | `https://github.com/johnlobo/DeckTower.git` | `loader-banking` | `83e15021040fd85e84bf9d505ce4973e2318decd` | `loader-banking`, `master` (`0e9fba7…`) | Sin licencia de repositorio (`NOASSERTION`); fuentes examinados declaran LGPL-3.0-or-later |
| PocketFever | `https://github.com/johnlobo/PocketFever.git` | `master` | `b879a1b08125c032ae081a5aa74f3d69ced687d7` | `master` y ramas locales de experimentos de física/dibujo | Sin licencia de repositorio (`NOASSERTION`); fuentes examinados declaran LGPL-3.0-or-later |
| CPCTelera Next | `https://github.com/Arnaud6128/cpctelera.git` | `cpctelera_next` | `11e61fe30175ad7b328de9bcd859c46fd61b26a5` | `cpctelera_next` | LGPL-3.0; copia en `licenses/CPCTelera-LGPL-3.0.txt` |
| Arkos Tracker | paquete oficial Linux 3.7 | `3.7` | ZIP SHA-256 `7e22d5762a611a09f21e83fa07cef0aeddc37fc28e159b67e2e0a949617024cf` | no aplica | MIT; copia en `licenses/Arkos-Tracker-MIT.txt` |

Las ramas locales de PocketFever observadas fueron `256-directions-step-ramp`,
`64-directions`, `aim-line`, `bigger-balls-bouncing-aim`, `charge-shot`,
`fast-ball-blit-6x8`, `fix-ball-visibility`, `fix-nudge-bounds`,
`fix-overlap-axis`, `friction-direction`, `hud-angle-power`, `master`,
`perf-moving-only`, `random-shot` y `skip-still-redraw`. Solo se utilizó
`master`; no se mezclaron revisiones.

## Procedencia por componente entregado

| Destino | Fuentes examinados | Tipo de uso | Licencia aplicada |
|---|---|---|---|
| `src/core/system.s` | los cuatro `src/sys/system.s` | Reescritura del ciclo de seis IRQ; se eliminan dependencias de juego/audio | GPL-3.0 del conjunto |
| `src/core/input.s` | `model01/src/sys/input.s`, `boop/src/sys/input.s`, `DeckTower/src/sys/input.s`, `PocketFever/src/sys/input.s` | Tabla configurable de model01 + estado de flanco motivado por boop; implementación nueva | GPL-3.0 del conjunto |
| `src/core/pool.*` | `*/src/sys/array.s`, idéntico byte a byte en model01/DeckTower/PocketFever | Contrato reducido y reimplementado para registros arbitrarios | GPL-3.0 del conjunto |
| `src/video/video.s`, `tools/gen_video.py` | render común; generadores/tablas de PocketFever; `easyoverscan` de CPCTelera Next | Reimplementación declarativa; sin supuestos de bolas | GPL-3.0; enlace con LGPL-3.0 |
| `src/ui/text.s` | variantes `src/sys/text.s`; API de strings de CPCTelera Next | Adaptador, sin copiar fuentes ni fuentes gráficas de juego | GPL-3.0; enlace con LGPL-3.0 |
| `src/audio/akg.*` | audio AKG de model01/boop/DeckTower; ABI AKG de CPCTelera Next | Adaptador genérico sobre el player fijado; no incluye datos musicales | GPL-3.0; enlace con LGPL-3.0 |
| `examples/audio/song.s`, `sfx.s` | recursos oficiales `Music_AHarmlessGrenade` y `SoundEffects` del player AKG de Arkos Tracker 3.7 | Export SDASZ80 generado con la herramienta oficial y comentarios eliminados; solo demostración | MIT |
| `src/resources/bank.s` | `model01/src/sys/mem.s`, `DeckTower/src/sys/mem.s` | Stub consolidado; prueba movida a `0x7FF0` para que sea funcional | GPL-3.0 |
| `src/resources/disk.s` | `DeckTower/src/sys/loader.s` y spike firmware de la misma revisión | API nueva reducida a reconexión y carga; sin tabla, bancos, paleta ni política de error del juego | GPL-3.0 del conjunto |
| `src/resources/zx7b.s` | `DeckTower/src/sys/compression.s`; `cpct_zx7b_decrunch_s_asm` de CPCTelera Next | Adaptador sin buffer ni packs concretos; compresor y descompresor proceden de la dependencia fijada | GPL-3.0; enlace con LGPL-3.0 |
| `tools/gen_resources.py` | tabla fija de `DeckTower/src/sys/loader.s` | Sustitución nueva mediante manifiesto validado | GPL-3.0 |
| `src/extensions/motion_u8.*` | movimiento de coordenadas enteras observado en model01 | Perfil compacto nuevo; no pretende ser física completa | GPL-3.0 |
| `src/extensions/physics_platform.*` | `model01/src/sys/physics.s`, `config.h.s` y `entity.h.s` | Reimplementación separada del núcleo portable: velocidad byte, gravedad, caída máxima, dimensiones, límites y suelo; sin mapa ni entidad de model01 | GPL-3.0 |
| `src/extensions/tilemap.*` | `model01/src/sys/map.s` y configuración de mapa | Consulta row-major reimplementada con descriptor y tabla de tipos del consumidor; sin salas, render, entidades ni escritura | GPL-3.0 |
| `src/extensions/platform_tilemap.*` | `model01/src/sys/physics.s`, `map.s` y tipos de tile | Contrato nuevo compuesto sobre `physics_platform`; sólido por ejes y plataforma de una dirección solo para suelo, sin reglas ni componentes de model01 | GPL-3.0 |
| `src/extensions/tilemap_render.*` | descriptor row-major ya extraído de model01 y `src/video/video.s` de GlasnostFWK | Implementación nueva de viewport/tileset Mode 0 sobre geometría generada; sin render, salas, portales ni entidades del juego original | GPL-3.0 |
| `src/extensions/physics_8_8.*` | `PocketFever/src/sys/physics.s`, `entity.h.s` y `tuning.h.s` | Reimplementación separada del integrador 8.8, fricción vectorial con resto y rebote; sin bolas, colisiones ni mesa fija | GPL-3.0 |
| `src/extensions/animation.*` | `model01/src/sys/anim.*`; contraste con la máquina de impactos de `DeckTower/src/game/combat.s` | Cursor de frames reimplementado sin entidad, sala, movimiento ni render; DeckTower permanece como especialización | GPL-3.0 |
| `src/ui/window.*` | `src/sys/messages.s` de los cuatro proyectos; caja idéntica en `DeckTower`/`PocketFever` `src/sys/render.s` | Geometría reimplementada sobre la tabla de vídeo, con buffer del consumidor; sin texto, espera, combate ni direcciones fijas | GPL-3.0 |
| `cfg/*.template*` | ejemplo `examples/asm/helloworld` de CPCTelera Next | Copia de plantilla de construcción con su cabecera intacta | LGPL-3.0 |

No se copiaron sprites, mapas, música ni datos de los cuatro juegos. Los datos
de `examples/audio` proceden exclusivamente de los recursos oficiales MIT de
Arkos Tracker indicados arriba. Al no
existir una declaración de licencia de repositorio en tres de ellos, el estado
se conserva como `NOASSERTION`; no se interpreta una cabecera de un archivo
como licencia de todo el repositorio.

## Construcciones base reproducidas

- `model01`: `make` correcto; `make test` correcto, 12+2 comprobaciones host,
  límite de memoria y 71 pruebas Z80.
- `boop`: `make` correcto; `make test` correcto, 20 pruebas Z80.
- `DeckTower`: `make` correcto; no existe objetivo `test`.
- `PocketFever`: `make` correcto; no existe objetivo `test`.

Las construcciones no dejaron cambios en los cuatro repositorios originales.
