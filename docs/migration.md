# Guía de migración

## Desde model01

- Sustituir `src/sys/system.s` por `core/system.s` y registrar audio mediante
  `fwk_audio_start`, no desde el handler.
- Reemplazar la tabla de `sys_input_generic_update` por el formato
  `key,action-mask`; las reglas leen los tres bytes de estado.
- Usar `extensions/physics_platform.s` para el subconjunto portable de velocidad
  byte, gravedad, dimensiones y suelo. Mantener mapas, colisión con tiles,
  componentes y scripts en el juego hasta disponer de un contrato específico.
  El cursor temporal de `extensions/animation.s` ya es reutilizable, pero la
  selección por movimiento y el render siguen siendo política del juego.
- Sustituir constantes de pantalla por un perfil JSON y consumir
  `fwk_video_get_ptr`.

## Desde boop

- Eliminar `sys_input_menu_key_actions`/`match`; aportar bindings por estado.
- Mantener los callbacks de reglas en la capa juego.
- Un export `BoopAudioAT3.s` puede acompañar `audio/akg.s`, pero debe declarar
  su propia licencia/procedencia y no se incluye en GlasnostFWK.
- Migrar ventanas como especialización: el buffer y la interacción de cierre
  no forman parte aún del núcleo.

## Desde DeckTower

- Sustituir `sl_payload_table` por `disk_files` en el manifiesto del ejemplo y,
  para destinos bancados, por el JSON validado por `gen_resources.py`.
- Mantener separados: backend de disco, copia bancaria, descompresión y
  localización. `resources/disk.s`, `resources/bank.s` y `resources/zx7b.s`
  se seleccionan por separado; el juego conserva su política de destinos.
- Los staging buffers se declaran como regiones reservadas y destinos en el
  manifiesto; el generador rechaza solapamientos y alineación incorrecta.
- El bytecode de combate permanece extensión del juego.

## Desde PocketFever

- Sustituir el integrador y fricción acoplados a bola por
  `extensions/physics_8_8.s` cuando basten límites rectangulares. Conservar
  `ball_blit`, colisión entre bolas y tablas de tiro como especializaciones;
  no adaptarlas a `motion_u8` ni al perfil de plataforma.
- Llevar el método de generadores deterministas a manifiestos del juego.
- Sustituir `row_table.s` por la tabla generada solo si la geometría coincide;
  para 160x288, todas las coordenadas verticales consumidoras deben ser 16 bit.

## Configuración que aporta cada juego

1. Perfil de vídeo y mapa de regiones reservadas.
2. Lista de módulos del ejemplo/juego.
3. Bindings de acciones de entrada.
4. Estructuras/perfiles de entidad que necesite.
5. Manifiesto de recursos y backend de medio.
6. Export AKG y datos de audio, si activa audio.
