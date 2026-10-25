# Ventanas y mensajes reutilizables

`src/ui/window.s` contiene únicamente la parte común observada en los cuatro
proyectos de origen: validar una región, capturar su fondo, dibujar una caja y
restaurar los bytes anteriores. No contiene texto, entrada, esperas, combate ni
un buffer global.

## Descriptor

Incluya `ui/window.inc` y mantenga un descriptor persistente de siete bytes:

```asm
my_window:
    .db 10       ; x, en bytes Mode 0
    .dw 40       ; y, 16 bits
    .db 20       ; ancho en bytes
    .db 16       ; alto en scanlines
    .db 0xFF     ; patrón del borde
    .db 0x00     ; patrón del relleno
```

Ancho y alto deben ser al menos 2. La esquina final debe caber en las
dimensiones exportadas por el perfil de vídeo. Un ancho de 20 y alto de 16
requiere un buffer de `20*16 = 320` bytes.

## Operaciones

- `fwk_window_capture`: `IX=descriptor`, `DE=buffer`. Copia la región y deja
  carry limpio; carry activo significa geometría inválida.
- `fwk_window_draw`: `IX=descriptor`. Dibuja un borde de un byte y rellena el
  interior; usa la tabla de líneas, no una fórmula fija de pantalla estándar.
- `fwk_window_restore`: `IX=descriptor`, `HL=buffer`. Restaura exactamente la
  captura previa.

Las tres preservan `IX` y alteran `AF,BC,DE,HL`; captura y restauración también
alteran `IY`. No comprueban el tamaño real del buffer. El descriptor y su
geometría deben permanecer iguales hasta restaurar.

## Composición y prueba

`examples/window` llena la pantalla con `0x55`, comprueba que una ventana fuera
de límites se rechaza, captura una región de 320 bytes, dibuja borde `0xFF` y
relleno `0x00`, y compone `GLASNOST` mediante `ui/text.s`. Un comando observable
restaura las 16 filas y otro vuelve a abrir la ventana.

El smoke verifica el buffer, filas de borde/relleno, testigos exteriores,
restauración completa y reapertura en CPC 6128 y CPC 464 emulados. No se ha
medido el coste temporal ni se ha probado en hardware real.
