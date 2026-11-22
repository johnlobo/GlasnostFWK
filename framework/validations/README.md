# Validaciones internas del framework

Estos programas CPC verifican contratos del framework o permiten medirlos.
Los ejemplos públicos y juegos para aprender están en `../../examples/`.

| Programa | Propósito |
|---|---|
| `video` | Limpieza de VRAM respetando los huecos y dibujo en esquinas. |
| `ecsmanager` | Slots, máscaras, ciclo de vida, locks, recorrido y cadencia. |
| `ecscollision` | Escenario de colisión y callbacks contrastado con el modelo Python. |
| `ecsanimation` | Estado de animación contrastado con el modelo Python. |
| `ecsrender` | Escenario de composición y comparación de VRAM con el modelo. |
| `perf` | Banco de rendimiento para `tools/dev/measure_perf.py`. |
| `experimental` | Perfil 160×288; la temporización CRTC sigue sin validación en hardware. |
| `disksave` | `fwk_disk_save` con el firmware apagado: dos escrituras, `.BAK` y área rechazada. |
| `uiinput` | Texto centrado y con borrado (normal y doble altura), e intervalos de `fwk_input_repeat`. |
| `textm1` | Texto Mode 1 normal y a doble altura. |

Desde la raíz, `make validations` construye los diez. Cada carpeta admite
`make`, `make run` y `make clean`; los resultados están en `build/<nombre>/`
y se copian junto a sus fuentes al usar el Makefile local.

`make test` ejecuta las pruebas host, construye ejemplos y validaciones y reúne
sus BIN en `build/tests/GlasnostFWK-tests.dsk`. Para comprobar un caso en
AmSpiriT-Lite, después de construir el DSK:

```sh
python3 tests/emulator_smoke.py ecsmanager ecscollision ecsanimation ecsrender video
```

La compilación, las pruebas host, la ejecución emulada y las mediciones son
comprobaciones distintas. `perf` tiene su herramienta de medición específica;
el smoke general de `experimental` solo comprueba el avance de frames.
`disksave`, `uiinput` y `textm1` se comprueban con BluePixel headless:

```sh
python3 tools/build/build_examples.py disksave uiinput textm1   # DSK propio de cada uno
python3 tests/bluepixel_validations_smoke.py --emulator BIN --rom-dir DIR
```
Los manifiestos se llaman `glasnost.manifest.json`.
