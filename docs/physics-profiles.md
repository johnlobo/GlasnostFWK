# Perfiles de física especializados

Fecha: 2026-10-25 UTC.

La auditoría no encontró una representación común que pueda extraerse sin
inventar una entidad universal. `model01` integra coordenadas y velocidades
enteras de 8 bits, gravedad, estado aéreo, dimensiones y colisión de mapa.
`PocketFever` usa posiciones y velocidades 8.8, fricción lineal sobre el vector
de movimiento y rebote en los límites de una mesa. `boop` y `DeckTower` no
aportan otro integrador general equivalente.

## Perfil de plataforma

`extensions/physics_platform.s` recibe `IY=estado` e `IX=configuración`. El
estado de siete bytes contiene `x,y,vx,vy,width,height,flags`; la configuración
define ancho del mundo, coordenada inclusiva del suelo, gravedad y velocidad
máxima de caída. Aplica límites horizontales, gravedad, techo, suelo y estado
aéreo. No conoce mapas, tiles, sprites, pools ni componentes: una colisión de
mapa continúa siendo política del juego.

El consumidor debe proporcionar dimensiones no nulas, `width <= world_width`,
un suelo alcanzable y parámetros que no desborden una velocidad byte con signo.

`examples/gravity` ejecuta 48 pasos reproducibles. Parte en `(75,150)` con
velocidad `(3,-8)`, satura horizontalmente en `x=76` y termina apoyado en
`y=192` con velocidad cero para un cuerpo de `4x8` y suelo `199`.

## Perfil 8.8

`extensions/physics_8_8.s` usa un estado de nueve bytes con posición y velocidad
8.8, más un acumulador fraccional de fricción. El descriptor fija límites
inclusivos y fricción. La reducción se aplica en la dirección del vector para
no detener antes el eje menor; después integra y rebota cada eje. Usa cuatro
palabras de trabajo internas, por lo que no es reentrante.

Los límites deben estar ordenados. La rutina no limita la magnitud inicial de
la velocidad ni resuelve colisiones entre cuerpos; el consumidor debe escoger
una velocidad que no atraviese su geometría relevante en un solo paso.

`examples/physics88` ejecuta 64 pasos desde `(78,70)` y velocidad `(2,1)`, con
fricción `4/256` por paso. El resultado comprobado en RAM es posición
`(&0BDC,&75C0)` y velocidad `(&0100,&0080)` después de rebotar en el límite X.

Ambos perfiles actúan sobre registros propiedad del consumidor y son módulos
opcionales independientes. No realizan iteración, render, temporización ni
entrada. Las pruebas host modelan los mismos recorridos y el smoke verifica el
resultado del Z80 en RAM; esto no sustituye una validación en hardware real.
