# Arquitectura y contratos públicos

## Dirección de dependencias

```text
ejemplo/juego -> extensión opcional -> núcleo -> CPCTelera Next / hardware
              -> audio AKG ---------> sistema
              -> recursos ----------> firmware AMSDOS / bancos / ZX7B
herramientas -> perfiles/manifiestos -> fuentes/tablas generadas
```

Ningún archivo de `src/` importa `examples/` ni símbolos de un juego. La prueba
`test_framework_never_imports_examples` mantiene esta frontera. Los manifiestos
de ejemplo seleccionan módulos antes del ensamblado; no existe un registro
dinámico que arrastre código no usado. `game_sources` permite declarar varios
archivos fuente propios del consumidor, por ejemplo lógica y recursos
separados; las rutas absolutas y los recorridos `..` se rechazan antes de
copiarlos.

## Contratos

Los costes temporales no se publican todavía: no se han medido en emulador y no
se ha realizado un conteo de todos los caminos. Los tamaños enlazados sí se
obtienen de los mapas SDCC en `build-sizes.md`.

### Sistema

- `fwk_system_init`: sin entrada/salida; altera `AF,BC,DE,HL`. Desactiva
  firmware, instala IRQ y deja callback nulo. No reentrante durante instalación.
- `fwk_system_wait_frame`: altera `AF,BC,DE,HL`; espera VSYNC.
- `fwk_system_set_irq_callback`: `HL=callback|0`; no altera registros. El
  callback corre una vez por seis IRQ, después del scan de teclado. Cambiarlo
  mientras está activo requiere interrupciones deshabilitadas por el llamador.
- Estado persistente: `fwk_system_irq_count` (1 B),
  `fwk_system_frame_count` (2 B), callback (2 B). El callback puede alterar los
  registros principales; un driver de audio debe preservarlos.

### Entrada

- `fwk_input_set_bindings`: `HL` apunta a entradas `.dw key,.db mask`, con
  máscara cero como terminador. La tabla debe persistir.
- `fwk_input_update`: altera `AF,BC,DE,HL,IY`; consume el buffer que la IRQ
  escanea. Actualiza tres bytes públicos: `fwk_input_held`,
  `fwk_input_pressed`, `fwk_input_released`.
- `fwk_input_init`: altera `AF` y borra estado. Soporta hasta ocho acciones por
  máscaras de bits; no contiene semántica del juego.

### Pool

Descriptor de 5 bytes: puntero base, capacidad, tamaño de registro y count.
`FWK_POOL_DESCRIPTOR` lo materializa durante ensamblado.

- `fwk_pool_init`: `IX=descriptor`; altera `A`.
- `fwk_pool_get`: `IX`, `A=index`; devuelve `HL` y carry limpio, o carry activo;
  altera `AF,B,DE,HL`.
- `fwk_pool_alloc`: devuelve slot sin inicializar en `HL`; carry indica lleno.
- `fwk_pool_remove`: `A=index`; compacta con `LDIR`; altera `AF,BC,DE,HL`.
- `fwk_pool_foreach`: `DE=callback`, callback recibe `IY=registro`; altera
  registros principales e `IY`. Usa `CALL` automodificable: no es reentrante y
  no debe reentrarse desde IRQ.

El pool no interpreta el contenido de los registros ni impone componentes.
La vertical jugable comprueba en Z80 real emulado una secuencia de tres
eliminaciones con compactación, además de las pruebas host de arquitectura.

### Física de plataforma opcional

Estado mutable de 7 bytes: `x,y,vx,vy,width,height,flags`. Configuración de 4
bytes: ancho del mundo, coordenada inclusiva del suelo, gravedad y caída máxima.

- `fwk_physics_platform_step`: `IY=estado`, `IX=configuración`; aplica velocidad
  horizontal con saturación, gravedad, techo, suelo y actualiza el bit
  `FWK_PLATFORM_AIRBORNE`. Altera `AF,BC` y preserva `IX,IY`.
- Es reentrante si ningún contexto comparte el registro. Dimensiones, gravedad
  y velocidades deben cumplir los límites documentados en
  `physics-profiles.md`; no hay validación dinámica.

No itera pools ni consulta mapas. La colisión con tiles, la selección del cuerpo
y el render permanecen fuera para no importar la entidad de `model01`.

### Física 8.8 opcional

Estado mutable de 9 bytes: `x,y,vx,vy` como palabras 8.8 little-endian y un
byte de resto fraccional. Descriptor de 5 bytes: límites X/Y inclusivos y
fricción lineal por paso.

- `fwk_physics_8_8_step`: `IY=estado`, `IX=descriptor`; reduce la velocidad a lo
  largo del vector, integra y rebota cada eje. Altera `AF,BC,DE,HL` y preserva
  `IX,IY`.
- Usa cuatro palabras internas para magnitudes y división; no es reentrante ni
  debe llamarse de forma anidada o desde una IRQ que pueda interrumpirlo.

No conoce bolas, radios, pares de colisión ni reglas de restitución. La
magnitud máxima que evita atravesar geometría pertenece al consumidor.

### Animación opcional

Descriptor inmutable: número de frames, duración común en ticks y tabla de
punteros a frames. Estado mutable de 4 bytes: descriptor activo, índice y ticks
restantes. El módulo no conoce entidades, salas, movimiento, VSYNC ni formato
gráfico.

- `fwk_anim_clear`: `IX=estado`; lo desactiva y devuelve `HL=0`, carry limpio.
- `fwk_anim_set`: `IX=estado`, `HL=descriptor|0`; activa o desactiva. Carry
  activo indica cambio de descriptor; seleccionar otra vez el mismo conserva
  índice y temporizador. Devuelve en `HL` el frame actual o cero.
- `fwk_anim_tick`: `IX=estado`; consume exactamente un tick definido por el
  llamador. Carry activo solo cuando avanza de frame; devuelve el frame actual
  en `HL`, o cero si está inactivo.

El descriptor debe persistir y declarar `count>0` y `duration>0`. Los tres
procedimientos alteran `AF,HL` y conservan `IX`; `set/tick` también pueden
alterar `BC,DE`. La política para elegir animación, llamar al tick y dibujar el
frame pertenece al juego. El contrato y la disposición byte a byte se detallan
en `animation.md`.

### Vídeo

- `fwk_video_init`: selecciona Mode 0; altera `AF,BC,DE,HL`.
- `fwk_video_configure_crtc`: aplica la tabla CRTC explícita del perfil; altera
  `AF,BC,DE,HL,IX`. El perfil experimental no adquiere por ello estado de
  verificado.
- `fwk_video_get_ptr`: `HL=y` de 16 bits, `C=x` en bytes; devuelve `HL=puntero`;
  altera `AF,DE,HL`. Las coordenadas deben estar dentro del perfil.
- `fwk_video_plot_byte`: además recibe `A=byte Mode 0`.
- `fwk_video_clear_visible`: `A=patrón`; altera `AF,BC,DE,HL,IX`. Recorre solo
  las regiones visibles generadas y conserva todos los huecos declarados.
- Geometría pública de solo lectura por contrato: `fwk_video_width_bytes` (1 B)
  y `fwk_video_height` (2 B), consumida por la validación de ventanas.

La tabla de líneas y las regiones se generan juntas. Para 160x200: ocho tramos
de 2.000 B y ocho huecos de 48 B. Para 160x288: 288 entradas, dos segmentos y
coordenadas de 16 bits.

### Texto

- `fwk_text_set_colors`: `L=foreground`, `H=background` (0..15); altera
  `AF,BC,DE,HL`; hereda automodificación de CPCTelera y no funciona desde ROM.
- `fwk_text_draw`: `IY=ASCII NUL`, `HL=vídeo`; altera `AF,BC,DE,HL`.

### Ventanas opcionales

Descriptor inmutable de 7 bytes: `x` en bytes Mode 0, `y` de 16 bits, ancho,
alto, patrón de borde y patrón de relleno. El módulo usa la tabla de líneas del
perfil y valida que la geometría completa quepa en la pantalla.

- `fwk_window_capture`: `IX=descriptor`, `DE=buffer`; copia exactamente
  `width*height` bytes y devuelve carry si la geometría no es válida.
- `fwk_window_draw`: `IX=descriptor`; dibuja un borde de un byte y rellena el
  interior. Devuelve carry si no puede dibujarse.
- `fwk_window_restore`: `IX=descriptor`, `HL=buffer` capturado; repone la región
  exacta y devuelve carry si la geometría no es válida.

Las tres preservan `IX` y alteran `AF,BC,DE,HL`; captura/restauración también
alteran `IY`. El llamador debe reservar un buffer suficiente y conservar el
descriptor entre captura y restauración. Texto, entrada, espera, pila de
ventanas y política de cierre pertenecen al juego.

### Audio AKG opcional

Usa el player `arkosTracker_PlayerAkg.s` de la instalación fijada de CPCTelera
Next; el juego sigue aportando sus datos musicales y de efectos.
`fwk_audio_init_music` recibe `HL=canción,A=subsong`; `fwk_audio_init_sfx`
recibe `HL=tabla`; `fwk_audio_play_sfx` usa `A=id,B=volumen invertido,C=canal`.
`fwk_audio_start/stop` registran o retiran el callback del sistema. El tick
incrementa `fwk_audio_tick_count`; las solicitudes SFX incrementan
`fwk_audio_sfx_count`. El wrapper seguro de CPCtelera preserva los registros
principales, IX e IY; el adaptador preserva los alternativos alrededor del
player. Las restricciones de banco son las del
export AKG del juego: player y datos ejecutados por IRQ deben permanecer
visibles en el mapeo activo.

### Bancos 128 KB

- `fwk_bank_init`: instala stub en `0x0200`, prueba `0x7FF0`, preserva bytes y
  devuelve `A=1/NZ` para RAM independiente o `A=0/Z`; altera `AF,BC,DE,HL`.
- `fwk_bank_copy_from/to`: `A=0..3`, `HL=origen`, `DE=destino`, `BC=tamaño`;
  carry activo para banco inválido. El lado bancado debe estar en
  `0x4000..0x7FFF`; pila, callback y lado normal deben quedar fuera. El stub
  ejecuta `DI`, restaura mapeo normal, ejecuta `EI` y retorna; por tanto deja
  interrupciones habilitadas y no preserva un estado IFF previo.

No se ofrece una operación que deje un banco conectado. Esto evita dependencias
ocultas del núcleo con 128 KB y reduce el riesgo de ejecutar código paginado.

### Disco AMSDOS

- `fwk_disk_init`: sin entrada/salida; altera `AF,B,C,DE,HL`, habilita
  interrupciones y reconecta la ROM 7 con `KL INIT BACK`. Debe ejecutarse antes
  de `fwk_system_init`, que desactiva el firmware.
- `fwk_disk_load`: `HL=nombre`, `B=longitud del nombre`, `DE=destino`; devuelve
  carry activo y `BC=longitud lógica` si `CAS IN OPEN` tuvo éxito, o carry
  limpio si no pudo abrir. Altera `AF,DE,HL`. Lee con `CAS IN DIRECT` y cierra
  con `CAS IN CLOSE`.
- Usa `0xF800..0xFFFF` como buffer de cabecera de 2 KB. El código, pila y
  destino del llamador no pueden solaparlo. No es reentrante ni puede usarse
  mientras el sistema del framework mantiene el firmware desactivado.
- El firmware no proporciona aquí una comprobación de integridad: el llamador
  debe validar longitud y contenido según su formato. `diskload` hace ambas.

### ZX7B

- `fwk_zx7b_unpack`: `HL=último byte comprimido`, `DE=último byte del destino`;
  altera `AF,BC,DE,HL` y escribe hacia atrás mediante
  `cpct_zx7b_decrunch_s_asm` de CPCTelera Next.
- No comprueba límites ni corrupción. Los tamaños exactos se generan desde
  `disk_files` como `FWK_DISK_<SYMBOL>_SIZE` y
  `FWK_DISK_<SYMBOL>_UNPACKED_SIZE`.
