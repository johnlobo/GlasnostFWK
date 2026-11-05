# Especificación ABI de GlasnostFWK ECS 2.0

Estado: normativa aprobada en la puerta G1 el 2026-11-03. La API del entity
manager definida en la sección 6.2 está implementada desde la fase 2; los
sistemas y el generador de perfiles pertenecen a fases posteriores.

Este documento fija el contrato binario que compartirán el código generado,
el framework y el juego. Las palabras **DEBE**, **NO DEBE**, **PUEDE** y
**RECOMENDADO** se usan con sentido normativo.

## 1. Principios y alcance

- El modelo es AoS: cada slot contiene un registro de entidad completo.
- Un proyecto genera un único layout de entidad y PUEDE declarar varios
  managers con ese mismo layout.
- Los slots son estables y nunca se compactan. Una referencia persistente es
  un puntero Z80 de 16 bits al inicio del slot.
- No existe contador de generación. El propietario de un puntero DEBE
  invalidarlo cuando la entidad entra en `PENDING_DESTROY` o se libera.
- Los componentes aportan campos al layout, no almacenamientos paralelos.
- Esta ABI cubre entidades, managers, recorridos, lifecycle, render y el
  formato de eventos de colisión. Los servicios globales de vídeo, audio,
  recursos, disco, texto y tilemaps conservan sus contratos propios.
- Todo el ABI público usa memoria visible en el espacio base de 64 KiB. Un
  array de entidades NO DEBE residir en una ventana bancaria que pueda
  desaparecer durante un recorrido.

## 2. Representación básica

### 2.1 Tipos

| Tipo | Bytes | Representación |
|---|---:|---|
| `u8`, `i8` | 1 | byte sin signo / complemento a dos |
| `u16`, `i16` | 2 | little-endian / complemento a dos |
| `pointer` | 2 | dirección Z80 little-endian; cero significa nulo |
| `fixed_8_8` | 2 | byte bajo fracción, byte alto entero |
| `bytes[n]` | n | bytes opacos, sin relleno implícito |

`fixed_8_8` mide la misma unidad que el atributo asociado. En posiciones, el
byte entero es sin signo (`0..255`) y la velocidad compatible usa complemento
a dos 8.8. Para X en Mode 0, la parte entera es una columna de byte de pantalla,
no un píxel. El generador DEBE rechazar este formato si el perfil necesita una
coordenada positiva mayor de 255.

### 2.2 Empaquetado y límites

- Los registros están empaquetados y no tienen alineación ni padding
  implícito.
- Todos los offsets públicos deben estar entre 0 y 127 para poder usarse con
  `IX+d`/`IY+d`. Por ello `ECS_ENTITY_SIZE` DEBE estar entre 1 y 128 bytes.
- El stride del manager es exactamente `ECS_ENTITY_SIZE`, se almacena en un
  byte y `fwk_ecs_manager_init` rechaza cualquier descriptor que no coincida
  con el perfil seleccionado.
- La capacidad de un manager está entre 1 y 255 slots.
- `base + capacity * stride` NO DEBE superar `0x10000` ni envolver.
- X y anchura usan bytes de pantalla; Y y altura usan scanlines. Anchura y
  altura son siempre `u8` y no pueden ser cero en una entidad renderizable o
  colisionable.

## 3. Layout generado de entidad

El generador produce `generated/ecs_profile.inc`. Todos los consumidores
DEBEN usar sus símbolos; ningún sistema debe codificar offsets numéricos.

Los identificadores de formato generados son `ECS_FORMAT_U8=1`,
`ECS_FORMAT_U16=2` y `ECS_FORMAT_FIXED_8_8=3`. `ECS_X_FORMAT` y
`ECS_Y_FORMAT` contienen uno de esos valores; sus tamaños se publican por
separado.

### 3.1 Cabecera universal

| Símbolo generado | Offset | Tamaño | Contenido |
|---|---:|---:|---|
| `ECS_E_COMPONENTS` | 0 | 2 | máscara de componentes |
| `ECS_E_STATUS` | 2 | 1 | estado de lifecycle |
| `ECS_E_TYPE` | 3 | 1 | tipo definido por el juego |
| `ECS_E_X` | 4 | `ECS_X_SIZE` | posición horizontal |
| `ECS_E_Y` | siguiente | `ECS_Y_SIZE` | posición vertical |
| `ECS_E_WIDTH` | siguiente | 1 | anchura en bytes |
| `ECS_E_HEIGHT` | siguiente | 1 | altura en scanlines |

Los formatos `ECS_X_FORMAT` y `ECS_Y_FORMAT` se seleccionan de forma
independiente entre `u8`, `u16` y `fixed_8_8`. Los componentes de movimiento
generan velocidades compatibles: `i8` para posición `u8`, `i16` para `u16` y
`fixed_8_8` para posición fraccionaria.

Después de la cabecera aparecen, sin huecos:

1. los bloques de campos de componentes, en orden ascendente de bit;
2. los campos universales propios del juego, en el orden del manifiesto.

El generador publica los campos de componente como
`ECS_E_<COMPONENTE>_<CAMPO>`, los campos universales como `ECS_E_<CAMPO>` y
termina con `ECS_ENTITY_SIZE`. Reordenar componentes o campos es un cambio de
layout que debe revisarse antes de regenerar.

### 3.2 Máscara de componentes

- La máscara es `u16` little-endian.
- `RENDER` es obligatorio en el perfil y ocupa el bit 0.
- Los demás componentes resueltos ocupan los bits 1..15 en el orden explícito
  del manifiesto. Las dependencias insertadas por el generador se muestran en
  la vista previa y pasan a formar parte de ese orden resuelto.
- Se rechazan más de 16 componentes y nombres duplicados.
- Una entidad activa PUEDE tener máscara cero. `FREE` se determina únicamente
  con `status`, nunca con la máscara.
- Un sistema con máscara requerida `R` acepta una entidad solo cuando:

  ```text
  status == ECS_STATUS_ACTIVE AND (components AND R) == R
  ```

  Los bits adicionales no excluyen la entidad. `R=0` selecciona todas las
  entidades activas.

### 3.3 Estados

| Símbolo | Valor | Semántica |
|---|---:|---|
| `ECS_STATUS_FREE` | 0 | slot reutilizable; el resto de bytes es indeterminado |
| `ECS_STATUS_ACTIVE` | 1 | procesable por sistemas compatibles |
| `ECS_STATUS_PENDING_DESTROY` | 2 | no recibe lógica nueva; espera limpieza visual |
| `ECS_STATUS_DISABLED` | 3 | conserva slot y datos, pero no recibe sistemas |

No se admiten otros valores. Las transiciones válidas son:

```text
FREE -> ACTIVE                    creación desde plantilla
ACTIVE <-> DISABLED              entre recorridos
ACTIVE|DISABLED -> PENDING_DESTROY
PENDING_DESTROY -> FREE          recolección al final del frame
```

No existe resurrección desde `PENDING_DESTROY`. El juego NO DEBE escribir
directamente `status` ni la máscara: usa la API para que render y los contadores
del manager permanezcan coherentes.

Retirar `ECS_C_RENDER` mediante `fwk_ecs_entity_set_mask` se rechaza con
`FWK_ECS_ERR_RENDER` mientras `ECS_RENDER_HAS_BACKGROUND` esté activo. El
llamador debe esperar a que la fase de render restaure y libere esa captura.

## 4. Bloque RENDER obligatorio en el perfil

Aunque todas las entidades reservan este bloque, solo las que tienen el bit
`ECS_C_RENDER` son procesadas por render.

| Campo | Tipo | Función |
|---|---|---|
| `ECS_E_RENDER_SPRITE` | `pointer` | datos del sprite actual |
| `ECS_E_RENDER_PREVIOUS_X` | formato X | posición de la captura vigente |
| `ECS_E_RENDER_PREVIOUS_Y` | formato Y | posición de la captura vigente |
| `ECS_E_RENDER_PREVIOUS_WIDTH` | `u8` | anchura capturada |
| `ECS_E_RENDER_PREVIOUS_HEIGHT` | `u8` | altura capturada |
| `ECS_E_RENDER_BACKGROUND` | `pointer` | buffer propiedad del juego |
| `ECS_E_RENDER_BACKGROUND_CAP` | `u16` | capacidad del buffer en bytes |
| `ECS_E_RENDER_FLAGS` | `u8` | flags descritos abajo |
| `ECS_E_RENDER_SOURCE_PEN` | `u8` | pen sustituido, 0..15 |
| `ECS_E_RENDER_REPLACEMENT_PEN` | `u8` | pen nuevo, 0..15 |
| `ECS_E_RENDER_SORT_OFFSET_Y` | `i16` | ajuste para orden vertical |
| `ECS_E_RENDER_PREVIOUS_SORT_Y` | `i16` | clave usada en el frame capturado |

El orden exacto de estos campos en el bloque es el de la tabla. La clave actual
se calcula en 16 bits como `integer(y) + sort_offset_y` y vive en el work array
de render; no se duplica como atributo persistente.

Flags, compatibles con la semántica del renderer no ECS:

| Flag | Valor |
|---|---:|
| `ECS_RENDER_VISIBLE` | `0x01` |
| `ECS_RENDER_DIRTY` | `0x02` |
| `ECS_RENDER_HAS_BACKGROUND` | `0x04` |
| `ECS_RENDER_MASKED` | `0x08` |
| `ECS_RENDER_RECOLOR` | `0x10` |

Los bits `0x20..0x80` se reservan y DEBEN ser cero. Cambiar X, Y, sprite,
visibilidad, geometría o recoloreado DEBE activar `DIRTY`. Anchura y altura no
se cambian mientras `HAS_BACKGROUND` esté activo: primero debe ejecutarse la
restauración de la geometría anterior.

`PENDING_DESTROY` y `DISABLED` no se dibujan, pero render DEBE restaurar su
fondo si `HAS_BACKGROUND` estaba activo. Rehabilitar una entidad renderizable
activa `DIRTY`.

## 5. Descriptor de manager

Un manager ocupa ocho bytes y su storage pertenece al juego:

| Símbolo | Offset | Tamaño |
|---|---:|---:|
| `FWK_ECS_MANAGER_STORAGE` | 0 | 2 |
| `FWK_ECS_MANAGER_CAPACITY` | 2 | 1 |
| `FWK_ECS_MANAGER_STRIDE` | 3 | 1 |
| `FWK_ECS_MANAGER_ACTIVE_COUNT` | 4 | 1 |
| `FWK_ECS_MANAGER_LIVE_COUNT` | 5 | 1 |
| `FWK_ECS_MANAGER_LOCK` | 6 | 1 |
| `FWK_ECS_MANAGER_FLAGS` | 7 | 1 |
| `FWK_ECS_MANAGER_SIZE` |  | 8 |

`ACTIVE_COUNT` cuenta solo `ACTIVE`; `LIVE_COUNT` cuenta todos los estados no
`FREE`. Son observables, pero solo el manager los modifica.

`LOCK` usa `FWK_ECS_LOCK_TRAVERSAL=0x01` y
`FWK_ECS_LOCK_RENDER=0x02`. Crear, habilitar, deshabilitar, recolectar o cambiar
máscaras requiere `LOCK=0`. Marcar `PENDING_DESTROY` está permitido durante
un recorrido lógico, pero no después de preparar render.

`FLAGS` solo define por ahora `FWK_ECS_MANAGER_INITIALIZED=0x01`; los demás
bits se reservan. Inicializar marca todos los slots `FREE` y pone ambos
contadores a cero.

## 6. Convención de llamada Z80

### 6.1 Resultado común

- Éxito: carry limpio y `A=FWK_ECS_OK` (`0`).
- Error recuperable: carry activo y `A` contiene un código no cero.
- Salvo una salida documentada, `IX` e `IY` se preservan.
- `AF`, `BC`, `DE` y `HL` son volátiles.
- Las rutinas no son reentrantes, no pueden anidarse y NO DEBEN llamarse desde
  IRQ. Los callbacks se ejecutan en el bucle principal.

### 6.2 API del manager que debe implementar la fase 2

| Rutina | Entrada | Salida adicional |
|---|---|---|
| `fwk_ecs_manager_init` | `IX=manager` | ninguna |
| `fwk_ecs_entity_create` | `IX=manager`, `HL=plantilla completa` | `IY=slot` o `IY=0` en error |
| `fwk_ecs_entity_mark_destroy` | `IX=manager`, `IY=entidad` | ninguna |
| `fwk_ecs_entity_disable` | `IX=manager`, `IY=entidad` | ninguna |
| `fwk_ecs_entity_enable` | `IX=manager`, `IY=entidad` | ninguna |
| `fwk_ecs_entity_set_mask` | `IX=manager`, `IY=entidad`, `BC=máscara` | ninguna |
| `fwk_ecs_system_run` | `IX=manager`, `BC=máscara requerida`, `HL=callback` | ninguna |
| `fwk_ecs_manager_collect` | `IX=manager` | `B=slots liberados` |

La plantilla tiene exactamente `ECS_ENTITY_SIZE` bytes, declara
`ECS_STATUS_ACTIVE` y se copia completa. Crear busca el primer slot `FREE`
desde el índice cero; esta política hace reproducible la reutilización.

`fwk_ecs_system_run` recorre los `capacity` slots en orden ascendente. Antes
del primer callback activa `LOCK_TRAVERSAL` y lo limpia en todas las salidas.
El callback recibe `IX=manager`, `IY=entidad`; DEBE preservar ambos, puede
modificar los demás registros y devuelve carry limpio para continuar. Carry
activo aborta el recorrido y propaga su código de `A`.

Los sistemas especializados PUEDEN implementar su propio bucle para ahorrar
el coste del callback, pero DEBEN respetar exactamente el filtrado, orden,
locks y reglas de mutación de `fwk_ecs_system_run`.

### 6.3 Errores

| Símbolo | Valor | Causa |
|---|---:|---|
| `FWK_ECS_OK` | `0x00` | éxito |
| `FWK_ECS_ERR_ARGUMENT` | `0x01` | descriptor o argumento nulo/inválido |
| `FWK_ECS_ERR_MANAGER` | `0x02` | manager no inicializado o incoherente |
| `FWK_ECS_ERR_FULL` | `0x03` | no existe slot libre |
| `FWK_ECS_ERR_TEMPLATE` | `0x04` | plantilla o estado inicial inválido |
| `FWK_ECS_ERR_ENTITY` | `0x05` | puntero ajeno o estado no válido |
| `FWK_ECS_ERR_BUSY` | `0x06` | operación estructural durante un lock |
| `FWK_ECS_ERR_TRANSITION` | `0x07` | transición de lifecycle prohibida |
| `FWK_ECS_ERR_MASK` | `0x08` | máscara fuera del perfil |
| `FWK_ECS_ERR_CALLBACK` | `0x09` | callback nulo o aborto sin código |
| `FWK_ECS_ERR_OVERFLOW` | `0x0A` | buffer fijo insuficiente |
| `FWK_ECS_ERR_RENDER` | `0x0B` | fase/recursos de render inválidos |

Debug valida descriptor, pertenencia y alineación de punteros en los límites de
la API. Release puede omitir comprobaciones de procedencia en rutas calientes:
un puntero que no fue entregado por ese manager tiene comportamiento indefinido
en release. No se añade una comprobación de generación en cada acceso.

## 7. Ciclo de frame y mutaciones

Orden normativo:

1. aplicar creaciones, reactivaciones y cambios de máscara pendientes;
2. ejecutar sistemas lógicos en el orden explícito del juego;
3. marcar destrucciones desde callbacks cuando proceda;
4. preparar dirty, solapamientos y orden global de render;
5. esperar VSYNC;
6. restaurar en orden inverso usando el estado anterior;
7. dibujar entidades `ACTIVE|VISIBLE` en orden estable;
8. liberar fondos y limpiar flags transitorios;
9. recolectar `PENDING_DESTROY` y convertirlos en `FREE`.

Desde el paso 4 hasta terminar el 9 no se cambian punteros, máscaras, estados,
geometría ni capacidad. Los atributos ordinarios pueden cambiar dentro de un
sistema; los cambios relevantes para render activan `DIRTY`.

## 8. Render con varios managers

Una escena recibe una tabla inmutable de punteros a managers. Los recorre en
orden de tabla y cada manager en orden de slot. El work array global contiene
como mínimo puntero de entidad y `sort_y` de 16 bits. La ordenación por Y es
estable: a igualdad de clave conserva manager y slot de origen.

La capacidad del work array DEBE cubrir la suma máxima de entidades render que
puedan participar. Un preflight insuficiente devuelve
`FWK_ECS_ERR_OVERFLOW` antes de escribir VRAM. `prepare`, `restore` y `draw`
mantienen `FWK_ECS_LOCK_RENDER` en todos los managers de la escena.

Los detalles internos del descriptor de escena y del work array se fijarán al
implementar render en fase 9; no forman parte todavía del ABI público. No se
podrán cambiar los campos de entidad, flags ni reglas definidos aquí sin una
revisión de ABI.

## 9. Colisión y eventos

Existe un único componente `COLLISION`. Su bloque comienza con
`ECS_E_COLLISION_ROLES` (`u8`):

- `ECS_COLLISION_COLLIDER = 0x01`;
- `ECS_COLLISION_COLLISIONABLE = 0x02`.

Los demás bits se reservan. La AABB usa X, Y, width y height universales. La
colisión de tilemap es un sistema distinto.

Cada evento ocupa cinco bytes empaquetados:

| Campo | Tamaño |
|---|---:|
| entidad A | 2 |
| entidad B | 2 |
| tipo | 1 |

Tipos: `ECS_COLLISION_ENTER=1`, `STAY=2`, `EXIT=3`. Los pares se normalizan y
se emiten en orden determinista de manager/slot. El callback recibe
`IX=entidad A`, `IY=entidad B`, `A=tipo`, `HL=manager A`, `DE=manager B`.
Puede marcar destrucción, pero no crear entidades ni cambiar máscaras.

El buffer tiene capacidad fija configurable. Si se llena, el sistema conserva
los primeros eventos, activa un flag observable y devuelve
`FWK_ECS_ERR_OVERFLOW`; nunca escribe fuera del buffer. Tras overflow no se
garantiza una secuencia completa `ENTER/STAY/EXIT`, por lo que el juego DEBE
tratarlo como error de capacidad, no como una situación normal.

### 9.1 Aclaración de fase 7: estado de contacto y llamada

Aprobada el 2026-11-05 antes de implementar `fwk_ecs_system_collision`. No
cambia ningún campo de entidad ni evento definido arriba.

**Estado del sistema.** Cada instancia del sistema tiene un descriptor creado
con `FWK_ECS_COLLISION_STATE nombre, callback, capacidad_eventos,
capacidad_pares`. Recuerda los pares en contacto de la llamada anterior en una
tabla de pares propia, de capacidad fija; la entidad no almacena contactos.
Layout público (el resto es privado de la implementación):

| Offset | Campo | Tamaño |
|---|---|---:|
| 0 | `FWK_ECS_COLLISION_CALLBACK` | 2 |
| 2 | `FWK_ECS_COLLISION_EVENTS` (buffer de eventos) | 2 |
| 4 | `FWK_ECS_COLLISION_EVENT_CAPACITY` | 1 |
| 5 | `FWK_ECS_COLLISION_EVENT_COUNT` (eventos conservados en la última llamada) | 1 |
| 6 | `FWK_ECS_COLLISION_FLAGS`; bit 0 `FWK_ECS_COLLISION_OVERFLOW` | 1 |
| 7 | `FWK_ECS_COLLISION_PAIR_COUNT` (pares en contacto tras la última llamada) | 1 |
| 8 | `FWK_ECS_COLLISION_PAIR_CAPACITY` | 1 |

**Llamada.** `fwk_ecs_system_collision`: `IX`=descriptor, `HL`=manager A,
`DE`=manager B. Si `HL==DE` se evalúa un único manager. Salida: carry limpio y
`A=0`, o carry activo y `A=FWK_ECS_ERR_*`. Preserva `IX`/`IY`. Un manager
bloqueado devuelve `FWK_ECS_ERR_BUSY` sin tocar el estado; un manager no
inicializado o un puntero nulo, `FWK_ECS_ERR_MANAGER`/`ARGUMENT`.

**Participantes.** Solo entidades `ACTIVE` con el bit `COLLISION`. Un par
`{e1,e2}` es válido si `e1` es `COLLIDER` y `e2` `COLLISIONABLE`, o al revés.
Con dos managers se evalúa cada `a` de A contra cada `b` de B. Con un solo
manager se evalúa cada par sin orden una única vez y se normaliza con la
dirección menor como entidad A. Una entidad con ambos roles no duplica el par.

**Solape.** Estricto en los cuatro lados: `ax < bx+bw`, `bx < ax+aw`,
`ay < by+bh`, `by < ay+ah`, con coordenadas `u8` y sumas sin desbordar
(la suma se satura a 255). Anchura o altura cero no solapan nunca.

**Eventos y orden.** Se recorren las entidades A por slot ascendente y, para
cada una, las B por slot ascendente. Cada par en contacto emite `ENTER` si no
estaba en la tabla anterior y `STAY` si estaba, en ese orden de recorrido. A
continuación se emite un `EXIT` por cada par de la tabla anterior que ya no
está en contacto (porque no solapa, o porque una entidad ya no está `ACTIVE`,
fue destruida o liberada), en el orden de la tabla anterior. La tabla nueva
contiene los pares en contacto en orden de recorrido.

**Entrega.** Primero se calculan todos los eventos y se actualiza la tabla;
después se entrega cada evento conservado al callback, en orden. Durante la
entrega ambos managers tienen `FWK_ECS_LOCK_TRAVERSAL` (se libera al terminar,
también si el callback aborta), de modo que el callback puede llamar a
`fwk_ecs_entity_mark_destroy` (con `IX`=manager recibido en `HL`/`DE`) pero no
crear entidades ni cambiar máscaras. El callback puede destruir registros:
en un `EXIT` los punteros pueden apuntar a un slot ya `PENDING_DESTROY` o
`FREE`, y el callback debe consultar `ECS_E_STATUS`. El callback puede
modificar todos los registros menos `SP`. Si devuelve carry activo, la entrega
se detiene y el sistema devuelve `FWK_ECS_ERR_CALLBACK` (con `A` del callback
distinto de cero se conserva el contrato de `fwk_ecs_system_run`).

**Capacidad.** El buffer de eventos y la tabla de pares tienen capacidad fija.
Si un evento no cabe se descarta, se activa `FWK_ECS_COLLISION_OVERFLOW` y la
llamada devuelve `FWK_ECS_ERR_OVERFLOW` después de entregar los conservados.
Un par en contacto que no cabe en la tabla no se recuerda: su `ENTER` se
repetirá en la llamada siguiente mientras siga en contacto. Nunca se escribe
fuera de ningún buffer. `FWK_ECS_COLLISION_FLAGS` se pone a cero al empezar
cada llamada.

## 10. Behavior, animación y datos compartidos

- `MOTION` almacena por entidad `velocity_x`, `velocity_y` y `flags`. Las
  velocidades usan el formato con signo compatible con X/Y; en la fase 4 el
  sistema ejecutable exige coordenadas `u8`, satura en `0..ECS_X_MAX` y
  `0..ECS_Y_MAX` y activa `ECS_RENDER_DIRTY` si cambia una coordenada.
- `BEHAVIOR` almacena por entidad cursor, timer y estado; el programa es un
  puntero inmutable y puede compartirse. En la fase 4 depende de `MOTION` y el
  adaptador copia de vuelta las velocidades, el puntero y el temporizador tras
  ejecutar el intérprete de bytecode; `state` queda disponible para el juego.
- `fwk_ecs_system_behavior` y `fwk_ecs_system_motion_u8` reciben
  `IX=manager`, filtran mediante `fwk_ecs_system_run` y respetan su orden,
  lock y convención de carry. El orden recomendado por frame es behavior y
  después movimiento.
- `ANIMATION` almacena por entidad frame y timer; su descriptor y frames son
  inmutables y compartibles.
- Los sistemas procesan una entidad compatible una vez por llamada explícita.
- Ningún sistema conserva un puntero implícito a «la entidad actual» después
  de retornar.

La fase 4 no convierte todavía `MOTION` en física: no hay gravedad, colisión,
fricción ni integración 8.8. Tampoco migra el `platformer`; esas capacidades
pertenecen a fases posteriores.

## 11. Código generado y compatibilidad

El include generado debe publicar como mínimo:

```text
ECS_ABI_MAJOR = 2
ECS_ABI_MINOR = 0
ECS_ENTITY_SIZE
ECS_X_FORMAT / ECS_X_SIZE
ECS_Y_FORMAT / ECS_Y_SIZE
ECS_E_* para todos los campos
ECS_C_* para todos los componentes
ECS_COMPONENT_VALID_MASK
```

El manifiesto y el include generado se versionan. El build falla si difieren.
La reconfiguración debe mostrar cambios de offsets, tamaños y máscaras antes de
escribir. Debug y release comparten layout, símbolos y convención de llamada.

Cambiar tamaño, orden, offset, valor de flag, estado, registro de entrada o
semántica de carry requiere incrementar la versión ABI. Añadir una rutina sin
alterar contratos existentes puede incrementar solo `ECS_ABI_MINOR`.

## 12. Puerta G1 aprobada

El 2026-11-03 se aceptaron expresamente:

1. el límite de 128 bytes motivado por desplazamientos indexados Z80;
2. cabecera universal, orden de bloques y asignación de bits;
3. valores y transiciones de lifecycle;
4. bloque de render y regla de limpieza de `DISABLED/PENDING_DESTROY`;
5. descriptor de manager de ocho bytes;
6. registros, preservación, carry y códigos de error;
7. recorrido estable, locks y ciclo de frame;
8. formato preliminar pero normativo de eventos de colisión.

Estos ocho contratos son normativos para la fase 2. Cualquier cambio posterior
debe registrarse como revisión de ABI antes de modificar la implementación.
