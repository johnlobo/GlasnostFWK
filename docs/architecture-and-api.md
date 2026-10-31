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

`performance.md` publica mediciones reproducibles en emulador para nueve
operaciones representativas. No constituyen un conteo de todos los caminos ni
una garantía global de 50 Hz. Los tamaños enlazados se obtienen de los mapas
SDCC en `build-sizes.md`.

### Configuración e inicialización del proyecto

El manifiesto admite las capacidades opcionales `"transparency": {"pen": 3}`
y `"extended_memory": true`. El pen debe ser un entero Mode 0 entre 0 y 15. El
generador crea la tabla de 256 máscaras en `0x0100` y enlaza
`video/transparency.s`. La memoria extendida enlaza `resources/bank.s`, reserva
el stub y scratch en `0x0200..0x0215` y desplaza el código de `0x0200` a
`0x0216`, la primera dirección libre. La detección prueba temporalmente
`0x4000`, con interrupciones
deshabilitadas, y restaura tanto RAM normal como banco 0; no deja una sonda
reservada dentro de `0x4000..0x7FFF`.

- `fwk_project_init`: inicializa el sistema; después copia una sola vez la
  tabla configurada y/o detecta la memoria extendida. Debe llamarse una sola vez.
- Sin `transparency`, los módulos consumidores son rechazados y los símbolos
  públicos transparentes no se ensamblan.
- Sin `extended_memory`, el módulo bancario no puede seleccionarse.

`fwk_system_init` continúa siendo el primitivo inferior para integraciones
especiales, pero no instala capacidades del proyecto.

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

No itera pools ni consulta mapas. La consulta y resolución opcionales se
seleccionan por separado; la selección del cuerpo y el render permanecen fuera.

### Tilemap y colisión de plataforma opcionales

El descriptor de tilemap tiene 11 bytes: punteros a datos y tabla de tipos,
ancho/alto, shifts y tamaños X/Y, y número de tipos. Los datos son ids de 8 bits
en orden de filas; el mapa y las tablas pertenecen al consumidor.

- `fwk_tilemap_query`: `IX=descriptor`, `B=Y`, `C=X`; devuelve tipo en `A` y
  carry limpio. Fuera de mapa, descriptor inválido o id fuera de tabla devuelve
  `A=0` y carry activo. Preserva `BC,IX,IY`; altera `AF,DE,HL`.
- `fwk_platform_tilemap_resolve`: se llama inmediatamente después de
  `fwk_physics_platform_step`, con `IY=estado` e `IX=tilemap`; corrige posición,
  velocidad y flags y devuelve una máscara de contactos en `A`. Los sólidos
  bloquean todos los ejes; una plataforma de una dirección solo bloquea al
  descender y sostiene un cuerpo ya apoyado.

Ambos son reentrantes para datos/estados separados. Las coordenadas son de 8
bits, los tamaños deben ser potencias de dos coherentes con sus shifts y no hay
barrido continuo: una velocidad capaz de saltar un tile puede atravesarlo. No
hay render, escritura del mapa, pendientes, habitaciones, portales ni colisión
entre cuerpos. El contrato completo está en `tilemap-collision.md`.

### Render de tilemap opcional

Descriptor mutable de 10 bytes: puntero al tileset Mode 0, cámara X/Y en tiles,
origen de pantalla (`x` byte, `y` palabra), ancho/alto del viewport en tiles y
número de gráficos. Cada gráfico ocupa `map.x_size * map.y_size` bytes
contiguos, por filas y sin padding. El render opaco admite las geometrías
CPCTelera 2x4, 2x8, 4x4 y 4x8 bytes y llama respectivamente a las primitivas
`cpct_drawTileAligned*_f_asm`; el origen Y debe estar alineado al alto.

- `fwk_tilemap_render_view`: `IX=tilemap`, `IY=render`; valida toda la
  geometría, el span del tileset y los ids seleccionados antes de escribir.
  Dibuja el viewport completo o devuelve carry sin escrituras.
- `fwk_tilemap_render_cell`: además recibe `B=fila`, `C=columna` relativas al
  viewport; valida y redibuja solo esa celda.

Ambas preservan `IX,IY`, alteran `AF,BC,DE,HL` y no son reentrantes por su
scratch interno. La variante transparente consume un único tileset con el pen
clave configurado y usa la tabla compartida de `0x0100`. No ofrecen clipping,
scroll sub-tile, doble buffer,
bancos, dirty rectangles automáticos ni política de cámara. El mapa permanece
de solo lectura. Detalles en `tilemap-render.md`.

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

### Sprites Mode 0 opcionales

Descriptor mutable de 8 bytes: puntero a datos, X/Y con signo de 16 bits,
ancho en bytes Mode 0 y alto en scanlines. Los datos ocupan `width*height`
bytes por filas, sin padding.

- `fwk_sprite_draw`: `IX=descriptor`; valida dimensiones/span, recorta contra
  los cuatro bordes y dibuja el rectángulo visible de forma opaca.
- `fwk_sprite_draw_masked`: `IX=descriptor`; solo existe si el manifiesto
  declara `transparency.pen`. Conserva los píxeles cuyo pen coincide con el
  color clave y copia los demás mediante la tabla implícita de `0x0100`.
- `fwk_sprite_draw_masked_recolor`: `IX=descriptor`, `D=pen origen`,
  `E=pen sustituto`; valida ambos pens, sustituye uno durante el render y aplica
  después el color clave. Comparte clipping y validación con el resto.
- `fwk_sprite_capture`: `IX=descriptor`, `DE=buffer`; guarda el fondo visible y
  devuelve `IY` al final de los bytes utilizados.
- `fwk_sprite_restore`: `IX=mismo descriptor`, `HL=buffer`; repone el fondo
  visible y devuelve `IY` al final.

Carry indica descriptor inválido o span de datos con wrap. Una geometría
completamente exterior es válida y no escribe.
Los tres dibujos preservan `IX` e `IY` y alteran `AF,BC,DE,HL`;
captura/restauración preservan `IX` y alteran también `IY`. El módulo usa scratch
interno y no es reentrante. El buffer, el orden de borrado/dibujo y la
sincronización pertenecen al consumidor. `entity_render` añade dirty rectangles
de entidad y propagación por solapamiento; no hay mezcla alfa ni remap completa
de paleta. El coste del nuevo recoloreado todavía no se ha medido; los casos
históricos están en `performance.md`.
Detalles funcionales en `sprites.md`.

### Render selectivo de entidades

`video/entity_render.s` recibe un descriptor de ocho bytes con array contado de
punteros, array auxiliar de cuatro bytes por slot, capacidades, contador
afectado y estado. Los punteros nulos son huecos; los duplicados son error.

- `fwk_entity_render_init`: inicializa el estado y marca las entidades visibles.
- `fwk_entity_render_revalidate`: revalida punteros y rangos estructurales en `IDLE`.
- `fwk_entity_render_mark_rect_dirty`: marca entidades tocadas por fondo externo.
- `fwk_entity_render_prepare_dirty`: prevalida, propaga y ordena sin tocar VRAM.
- `fwk_entity_render_restore_dirty`: restaura el orden ya preparado en orden inverso.
- `fwk_entity_render_draw_dirty`: ordena por `sort_y`, captura y dibuja en orden directo.

El prefijo estándar de entidad ocupa 25 bytes y comienza con el descriptor de
sprite de ocho bytes. La API admite opaco, máscara, recoloreado y su combinación.
La ruta sincronizable exige `IDLE -> PREPARED -> RESTORED -> IDLE`. La llamada
directa histórica a `restore_dirty` prepara internamente para conservar
compatibilidad. Punteros y rangos se validan al inicializar o revalidar; no
pueden cambiar durante la ruta preparada. El módulo usa scratch interno, no es
reentrante y no desactiva interrupciones. Detalles en
`render-order.md`.

### Texto

Renderer Mode 0 transparente basado en la fuente sprite de los juegos originales:
51 glifos de 2x9 bytes y diez dígitos pequeños de 2x5 bytes. Requiere
un proyecto con `transparency.pen=0`. La tabla se instala en `0x0100` mediante
`fwk_project_init`; después se llama a `fwk_text_init` para seleccionar assets.

- `fwk_text_init`: instala los assets incorporados; no vuelve a copiar la tabla.
- `fwk_text_set_assets`: `HL=fuente 51*18`, `DE=dígitos 10*10`.
- `fwk_text_set_color`: `A=índice 0..14`; carry indica índice inválido.
- `fwk_text_set_colors`: alias de migración; usa `L` como nuevo índice e ignora
  `H`. Conserva el símbolo, no la antigua semántica de números de pen.
- `fwk_text_draw`: `IY=ASCII NUL`, `HL=vídeo`; admite espacio, `!`, `-`, `/`,
  `0..9`, `:`, `>`, `?`, `@` y `A..Z`.
- `fwk_text_draw_small_digit`: `A=0..9`, `HL=vídeo`; carry si no es un dígito.
- `fwk_text_draw_small_u8`: `A=0..255`, `HL=vídeo`; decimal sin relleno.

El índice de color selecciona la tabla original; no equivale necesariamente al
número de pen de la paleta activa y el pen 14 se usa como sombra. No hay
clipping ni borrado del fondo. El scratch de 18 bytes impide reentrancia.

### Ventanas opcionales

Descriptor inmutable de 7 bytes: `x` en bytes Mode 0, `y` de 16 bits, ancho,
alto, patrón de borde y patrón de relleno. El módulo usa la tabla de líneas del
perfil y valida que la geometría completa quepa en la pantalla sin que
`y+height` desborde los 16 bits.

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

- La capacidad se activa con `"extended_memory": true`; el código comienza en
  `0x0216` y `fwk_project_init` llama automáticamente a `fwk_bank_init`.
- `fwk_bank_init`: instala el stub en `0x0200`, prueba temporalmente `0x4000`,
  preserva los bytes de RAM normal y banco 0, y
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
  de `fwk_project_init`, que inicializa el sistema y desactiva el firmware.
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
