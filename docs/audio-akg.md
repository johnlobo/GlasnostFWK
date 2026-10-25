# Audio Arkos Tracker 3 AKG

`src/audio/akg.s` adapta la ABI del framework al player AKG que ya distribuye
la revisión fijada de CPCTelera Next. El player solo se incorpora cuando un
manifiesto declara `cpct_modules`; el resto de ejemplos no lo enlaza.

## Ejemplo ejecutable

`examples/audio` inicializa una canción y una tabla de efectos, registra el
player como callback una vez por frame y deja la música activa. Sus comandos
observables en RAM son:

- `audio_command=1`: dispara el efecto 3 en el canal B.
- `audio_command=2`: para el player y silencia el PSG.
- `audio_command=3`: reanuda el callback.
- `audio_command_ack`: conserva el último comando atendido.

La prueba no deduce audio a partir de esos comandos. Lee además
`fwk_audio_tick_count` y el estado PSG de AmSpiriT: exige volumen musical no
nulo, ticks detenidos y los tres volúmenes a cero tras `stop`, ticks de nuevo
tras `start`, y periodo y volumen no nulos en el canal B durante el SFX.

## Procedencia y licencia

Los datos se regeneraron con `SongToAkg` y `SongToSoundEffects` de Arkos
Tracker 3.7 Linux, descargado del índice oficial:

`https://www.julien-nevo.com/arkostracker/release/3.7/linux64/ArkosTracker-linux64-3.7.zip`

El ZIP tiene SHA-256
`7e22d5762a611a09f21e83fa07cef0aeddc37fc28e159b67e2e0a949617024cf`.
Las entradas fueron el recurso musical `A Harmless Grenade` y la tabla
`SoundEffects` que el paquete distribuye junto al player bajo MIT. Los exports
resultantes tienen SHA-256 `1778af7b…b0b1a7` y `8eb010d3…29ad0`.
La licencia completa está en `licenses/Arkos-Tracker-MIT.txt`. El player
convertido que aporta CPCTelera Next conserva su LGPL-3.0-or-later.

## Coste y límites

El callback ejecuta exactamente un `Play` por frame activo. La envoltura
segura de CPCtelera documenta 184 ciclos por IRQ y se ejecuta en las seis IRQ
del frame; son 1.104 ciclos/frame antes del trabajo del handler. En el frame
que llama al player, el adaptador activo añade 187 ciclos, excluido el coste
variable del propio AKG y del escaneo de teclado.

No se ha medido todavía el peor caso del player ni el tiempo total de una
escena, por lo que esta integración no constituye una garantía de 50 Hz. No
hay validación en hardware real ni captura analógica de la salida; sí hay
verificación del estado PSG producido por el player emulado.
