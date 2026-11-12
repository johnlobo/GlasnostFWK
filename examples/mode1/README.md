# Mode 1, 192 × 192

Demo para comprobar en el emulador el perfil experimental Mode 1. Muestra un
área azul de 192 × 192 píxeles, un marco blanco, cuatro estrellas, texto Mode 1
dos franjas de tiles (opacos a la izquierda, enmascarados a la derecha, 8x8 píxeles
por gráfico de 2x8 bytes) y una nave amarilla/blanca que se mueve sobre el fondo sin borrarlo.

## Compilar y probar

```sh
cd examples/mode1
make
```

Los ficheros `mode1.bin`, `mode1.cdt` y `mode1.dsk` quedan en esta carpeta.
Carga el CDT como cinta y ejecuta `RUN"` si no arranca automáticamente. Para
el DSK, ejecuta `RUN"MODE1"`. También puedes usar `make run` si tienes
configurado un emulador para el proyecto.

**Controles:** O/P mueve la nave a izquierda/derecha; Q/A la mueve arriba/abajo.
Cada paso horizontal equivale a cuatro píxeles de Mode 1. La nave permanece
en la zona azul entre las estrellas; al soltar las teclas deja de redibujarse.

La imagen original está en `assets/src/sprites.png`. `make assets` vuelve a
convertirla con `img2cpc` a los datos ensamblados. El perfil CRTC aún no se ha
comprobado visualmente: interesa confirmar que se vean las cuatro esquinas,
que el marco sea rectangular y que la nave no deje rastros al moverse.
