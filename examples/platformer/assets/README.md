# Assets de `platformer`

Esta carpeta es el punto de entrada de gráficos, mapas y audio del ejemplo,
igual que `assets/` en un proyecto CPCtelera. El código del juego sigue en
`main.s`; aquí van los **originales editables** y los datos generados que no
forman parte de la lógica.

```
assets/
├── assets.json          manifiesto del pipeline
├── palette.json         paleta RGB Mode 0 para img2cpc
├── src/
│   ├── tiles.png        empty, solid, one_way y star (4 tiles de 8x8)
│   ├── sprites.png      coin, enemy, enemy2 y door (4 tiles de 8x8)
│   ├── sprites_wide.png player y player2 (2 tiles de 16x8)
│   └── level.tmx        capas CSV `level` y `level2` (20x25)
└── generated/
    ├── assets.s         datos SDCC listos para ensamblar
    ├── assets.inc       constantes de tamaño
    └── pipeline.json    hashes de fuentes y salidas
```

`tools/build_examples.py` copia esta carpeta en `src/assets` del proyecto
generado (`.build/platformer/`). Allí:

- los archivos `.s` se ensamblan automáticamente, sin tocar `example.json`;
- los `.inc` se incluyen con `.include "assets/generated/assets.inc"`;
- el resto de archivos (PNG, TMX, JSON) se copian para dejar trazabilidad.

## Conversión incremental

`make` ejecuta `tools/import_assets.py` antes de compilar. El pipeline calcula
un SHA-256 del manifiesto, de la paleta y de cada PNG/TMX. Si coincide con
`generated/pipeline.json` y las salidas siguen intactas, **no ejecuta ninguna
herramienta**:

```sh
cd examples/platformer
make            # convierte solo si cambió algún asset y luego compila
make assets     # fuerza la comprobación/conversión sin compilar
```

Al guardar un PNG o un TMX nuevo, el siguiente `make` vuelve a convertir y
reescribe `generated/assets.s` y `generated/assets.inc`. Los datos generados se
versionan para que una comprobación limpia no necesite `img2cpc`; si edita un
original, sí necesita las herramientas instaladas.

## Herramientas

El pipeline usa `img2cpc` incluido en el framework (`tools/img2cpc`, sin
FreeImage; `./setup.sh` ya lo compila) y `zx7b` de la revisión fijada de
CPCTelera Next:

```sh
make -C tools/img2cpc                       # PNG -> datos Mode 0
make -C "$CPCT_NEXT_PATH/tools/zx7b"        # compresión opcional
```

También puede indicar binarios propios con `IMG2CPC=/ruta/img2cpc` y
`ZX7B=/ruta/zx7b`. El pipeline solo busca herramientas si hay algo que
convertir; un árbol sin cambios no las necesita.

## Formato de `assets.json`

Cada imagen declara su tamaño en píxeles y los símbolos de sus tiles, en orden
de izquierda a derecha. El primer símbolo de un grupo puede ser además el
nombre del tileset completo:

```json
{
  "source": "src/tiles.png",
  "width": 8,
  "height": 8,
  "symbol": "platformer_tileset",
  "tiles": ["platformer_tile_empty", "platformer_tile_solid"]
}
```

`width` debe ser par: en Mode 0 cada byte contiene dos píxeles. El pipeline
llama a `img2cpc -of bin -nt`, comprueba que el tamaño coincide con
`(width / 2) * height * tiles` y escribe un único `.s` con etiquetas globales.

Cada tilemap declara una capa de Tiled exportada como CSV:

```json
{
  "source": "src/level.tmx",
  "layer": "level",
  "symbol": "platformer_map",
  "compression": "zx7b"
}
```

Se aplica la misma reindexación que `cpct_tmx2csv`: una celda vacía (`0`) sigue
siendo `0` y cada gid positivo se reduce en uno. No se admiten capas XML,
comprimidas, ni tiles volteados o rotados; el error indica cómo corregirlo.

## Compresión

Con `"compression": "zx7b"` el mapa se comprime con `tools/zx7b` y se genera:

- `platformer_map_packed` en ROM, con los bytes comprimidos;
- `platformer_map` en RAM, como buffer de descompresión;
- `PLATFORMER_MAP_SIZE` y `PLATFORMER_MAP_PACKED_SIZE` en `assets.inc`.

`main.s` llama una vez a `fwk_zx7b_unpack` al inicializar
(`src/resources/zx7b.s`, incluido en `example.json`). Los mapas son estáticos:
la descompresión no entra en el presupuesto de frame. Para dejar un mapa sin
comprimir, use `"compression": "none"` y elimine su llamada de
`_pf_decompress_levels`.

## Música

La música no se enlaza por defecto: el platformer ya está cerca de un frame de
trabajo y el smoke de juego es sensible al tiempo. El ejemplo MIT ya generado
está en `examples/audio/song.s` (procedencia en `docs/provenance.md`).

Para activarla en una copia del ejemplo:

1. Copie `examples/audio/song.s` a `assets/music/song.s` (se ensambla solo).
2. Añada `audio/akg.s` a `modules` y
   `audio/arkosTracker_PlayerAkg.s` a `cpct_modules` en `example.json`.
3. Inicialice con `fwk_audio_init_music`, `fwk_audio_start` y actualice con
   `fwk_audio_update` en el IRQ o el bucle, como en `examples/audio/main.s`.
4. Vuelva a medir el frame; el smoke espera el jugador en una ventana concreta
   tras 20 frames.

Regeneración desde un `.aks` (requiere Arkos Tracker 3 y sus utilidades, que
CPCTelera distribuye como ejecutables de Windows):

```sh
cpct_aks2c -gs -m 0x4000 -o song -od assets/music song.aks
```

## Reglas prácticas

- No edite `.build/platformer/`: se regenera en cada `make`.
- No edite `generated/assets.s` ni `generated/assets.inc` a mano: cambie los
  originales y ejecute `make assets`.
- Mantenga los originales (PNG, TMX, paleta) junto a los generados.
- Los nombres AMSDOS del DSK se declaran en `example.json`; esta carpeta no
  altera el disco.
