# Carga desde DSK y ZX7B

El backend separa tres responsabilidades: `disk_files` decide qué entra en el
DSK, `resources/disk.s` lee un fichero mediante AMSDOS y `resources/zx7b.s`
descomprime únicamente cuando el juego lo solicita.

## Manifiesto

Cada entrada admite `source`, `encoding` (`raw` o `hex`), nombre AMSDOS 8.3,
símbolo y compresión (`none` o `zx7b`):

```json
{
  "media": ["dsk"],
  "modules": ["resources/disk.s", "resources/zx7b.s"],
  "disk_files": [
    {
      "source": "payload.hex",
      "encoding": "hex",
      "name": "PACKDATA.ZX7",
      "symbol": "packed",
      "compression": "zx7b"
    }
  ]
}
```

La construcción rechaza rutas absolutas, recorridos `..`, enlaces simbólicos
que escapen del ejemplo, nombres que no cumplan 8.3, símbolos duplicados y
compresiones desconocidas. Genera `disk_files.inc` con el tamaño almacenado y
el tamaño original. Los payloads permanecen fuera del binario enlazado.

## Orden de arranque

1. `fwk_disk_init` reconecta AMSDOS mientras el firmware sigue disponible.
2. El juego llama a `fwk_disk_load` y valida `BC` y el contenido cargado.
3. Si corresponde, calcula ambos punteros finales y llama a
   `fwk_zx7b_unpack`.
4. Solo entonces llama a `fwk_system_init`, que desactiva el firmware.

`fwk_disk_load` reserva conceptualmente `0xF800..0xFFFF` para la cabecera. Los
destinos, el código y la pila deben quedar fuera de esa región. La API no
decide si el resultado va a RAM normal o posteriormente a un banco.

## Evidencia actual

`examples/diskload` carga desde su DSK un testigo de 256 bytes tanto crudo como
comprimido a 23 bytes. La prueba de emulador comprueba longitudes, contenido
crudo y los 256 bytes descomprimidos en CPC 6128 y CPC 464. Esto no demuestra
compatibilidad con hardware real, errores de medio ni recuperación ante un
flujo ZX7B corrupto.
