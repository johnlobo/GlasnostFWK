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
| `ECS_E_CADENCE` | siguiente | 1 | cadencia de ejecución, ver 6.2.1 |

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
| `ECS_E_RENDER_BACKGROUND` | `pointer` | buffer de fondo; lo asigna y libera el renderer (0 = sin buffer) |
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
| `fwk_ecs_system_run_any` | igual, ignorando `ECS_E_CADENCE` | ninguna |
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

#### 6.2.1 Cadencia

`ECS_E_CADENCE` decide en qué iteraciones del bucle del juego ejecutan una
entidad los sistemas que pasan por `fwk_ecs_system_run` (behavior, input,
platform, movimiento, animación). Es un byte `(fase << 4) | (cada - 1)`, con
`cada` igual a 1, 2, 4, 8 o 16 (potencia de dos) y `fase` en 0..`cada - 1`:

| Byte | Significado |
|---|---|
| `0x00` | todas las iteraciones (valor por defecto de una plantilla a cero) |
| `0x01` | una de cada 2, iteraciones pares |
| `0x11` | una de cada 2, iteraciones impares |
| `0x33` | una de cada 4, cuando `tick AND 3 = 3` |

La entidad se ejecuta cuando `((fwk_ecs_tick XOR fase) AND (cada - 1)) = 0`.
La fase DEBE ser menor que `cada` (`fase <= cada - 1`). El test es sin estado:
no hay contador por entidad y todos los sistemas ven el mismo resultado en la
misma iteración. Coste por entidad que pasa el filtro de máscara, contado por
instrucciones y sin medir en el emulador: unos 35 T con cadencia `0x00` y unos
110 T con cualquier otra.

- `fwk_ecs_tick` es un byte global que el JUEGO incrementa una vez por
  iteración de su bucle (`ld hl,#fwk_ecs_tick` / `inc (hl)`). NO es el contador
  de interrupciones de 50 Hz: un juego que itera cada dos interrupciones vería
  siempre la misma paridad.
- Crear una entidad cuyo byte de cadencia no tenga la forma
  `(fase << 4) | (2^k - 1)` con `fase <= 2^k - 1` devuelve
  `FWK_ECS_ERR_TEMPLATE`.
- `fwk_ecs_system_run` y `fwk_ecs_system_run_any` comparten el estado de la
  pasada (callback, máscara y modo de cadencia), así que tampoco son
  reentrantes: un callback no puede iniciar otra pasada, tampoco de otro manager.
- La cadencia solo afecta a los sistemas que filtran mediante
  `fwk_ecs_system_run`. No afecta a render ni a `fwk_ecs_manager_*`, y tampoco
  a los objetivos de `fwk_ecs_collide`, que recorre con `fwk_ecs_system_run_any`
  (mismo contrato, ignora el byte de cadencia): un objetivo que desapareciera
  en sus iteraciones de descanso cerraría y reabriría el contacto cada dos
  iteraciones y emitiría `ENTER` de nuevo cada vez.
- El contador de animación y los temporizadores de behavior avanzan una vez por
  ejecución, no por iteración: una entidad con cadencia 2 necesita la mitad de
  ticks para conservar el mismo tiempo real.

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

*Revisado el 2026-11-05 (fase 9).* El renderer no ECS actual pesa unos 2.100
bytes porque valida listas, duplicados y solapes de buffers contra llamantes
hostiles. El renderer ECS mantiene su algoritmo (restaurar y redibujar solo lo
afectado) y elimina esa defensa. Presupuesto vinculante para `video/ecs_render.s`:
**1.400 bytes de código y 40 de datos internos**, medidos con transparencia del
proyecto activa. Eran 1.150 (1.139 con la transparencia apagada, algo más de la mitad
del renderer anterior) hasta la ABI 2.2; los pools de fondos suman 235 B (1.385
medidos) y sustituyen al buffer que cada proyecto declaraba a mano por entidad. El
array de trabajo lo reserva el proyecto. La cifra
inicial de 900 era una estimación previa a medir: el algoritmo esencial
(candidatas, cajas, cierre de solapes, orden y las tres fases) ocupaba 1.099
tras reducirlo con cajas envolventes por entidad y descriptores de sprite
construidos con `ldi`.

**Escena.** `FWK_ECS_RENDER_SCENE nombre, tabla, cuenta, trabajo, capacidad, pools,
cuenta_pools` declara un descriptor de 11 bytes: puntero a una tabla de punteros a
managers, número de managers, puntero al array de trabajo, su capacidad en entradas
(ocho bytes cada una: puntero a entidad, clave de 16 bits y caja envolvente), número de
entidades afectadas, estado, puntero a la tabla de pools de fondos y número de pools. Los managers se recorren en orden de tabla y
cada uno en orden de slot; el orden final es global.

**Llamadas** (`IX`=escena; carry limpio y `A=0`, o carry activo y `A=FWK_ECS_ERR_*`;
preservan `IX`/`IY`), en este orden cada frame:

| Rutina | Cuándo | Qué hace |
|---|---|---|
| `fwk_ecs_render_prepare` | antes del VSYNC | reúne las entidades candidatas, marca las afectadas, bloquea los managers con `FWK_ECS_LOCK_RENDER` |
| `fwk_ecs_render_restore` | tras el VSYNC | restaura los fondos de las afectadas en orden inverso al de su último dibujo |
| `fwk_ecs_render_draw` | justo después | captura el fondo, dibuja en orden estable por Y, actualiza el estado anterior, limpia `DIRTY` y libera los bloqueos |

Llamarlas fuera de ese orden, o con la escena ya preparada, devuelve
`FWK_ECS_ERR_RENDER`; un manager ya bloqueado, `FWK_ECS_ERR_BUSY`; más
candidatas que capacidad, `FWK_ECS_ERR_OVERFLOW`. `prepare` falla sin dejar
bloqueos y con la escena en reposo (solo puede haber marcado `DIRTY` en
entidades cuyo estado de dibujo ya difería del fondo, lo cual es inocuo).
Un error en `restore` o `draw` (sprite inválido, por ejemplo anchura 0) es
**fatal**: deja la escena a medias y los managers bloqueados, y no existe
llamada de aborto. Un `prepare` sin su `restore`/`draw` deja también la escena
preparada y bloqueada.

**Candidatas.** Entidades con el bit `RENDER` que, estando `ACTIVE` y
`VISIBLE`, deben estar dibujadas, o que tienen fondo capturado
(`HAS_BACKGROUND`) y por tanto hay que restaurar aunque ya estén `DISABLED`,
`PENDING_DESTROY` u ocultas.

**Afectadas.** Una candidata se redibuja si tiene `DIRTY`, si ya no debe
estar dibujada pero conserva fondo, si debe estar dibujada y no tiene fondo
capturado, o si su rectángulo anterior o actual solapa con el de una afectada
(cierre transitivo). Las demás no se tocan.

**Orden.** Se restaura en orden inverso al de la clave anterior
(`ECS_E_RENDER_PREVIOUS_SORT_Y`) y se dibuja en orden de la clave actual
(`Y + ECS_E_RENDER_SORT_OFFSET_Y`, 16 bits con signo), con empate resuelto por
orden de tabla de managers y slot (índice de recogida), tanto al restaurar como
al dibujar, de modo que la restauración deshace exactamente el último dibujo. Tras restaurar, `ECS_E_RENDER_PREVIOUS_WIDTH` queda a 0.

**Fondos.** El juego no declara buffers por entidad. Declara pools con
`FWK_ECS_RENDER_POOL nombre, bytes, cuenta`: `cuenta` huecos de `[flag de uso][bytes
de buffer]`, con un descriptor de 3 bytes (`bytes` en 2, `cuenta` en 1) y una tabla
de punteros a pools en orden creciente de `bytes`. Cuando `prepare` ve una entidad
que debe dibujarse y tiene `ECS_E_RENDER_BACKGROUND` a 0, toma el primer buffer
libre del primer pool cuyo `bytes` sea al menos `anchura * altura`, pone su flag de
uso y apunta `ECS_E_RENDER_BACKGROUND` al buffer; si ningún pool lo tiene,
`FWK_ECS_ERR_OVERFLOW` (la escena queda inactiva y desbloqueada, y lo ya asignado
se conserva). `restore` devuelve el buffer (flag a 0 y puntero a 0) de la entidad
que ya no se dibuja y tenía un fondo capturado (`PENDING_DESTROY`, `DISABLED` u
oculta). Una entidad que llega a `FREE` sin pasar por `restore` no devuelve su buffer
hasta el siguiente `fwk_ecs_render_reset`; lo mismo ocurre si `prepare` falla con
`OVERFLOW` después de asignar a una entidad y el juego la oculta antes de dibujarla. Una plantilla DEBE dejar el
campo a 0. El juego NO DEBE escribirlo. Entre `prepare` y `draw` una entidad no se
destruye ni se oculta (ya prohibido arriba): el buffer que le asignó `prepare` solo lo
devuelve `restore`, y una entidad que no llegó a capturarse no pasa por él. Tampoco
cambia `width` ni `height` mientras conserve buffer: uno mayor que el asignado se
desbordaría sobre el flag del hueco siguiente; para cambiar de tamaño hay que dejar de
dibujar la entidad y esperar a su `restore`. `FWK_ECS_RENDER_POOL` exige entre 1 y 255
huecos (el ensamblado falla con otra cantidad).
`fwk_ecs_render_reset` (`IX`=escena, con la escena inactiva; `FWK_ECS_ERR_RENDER`
si no) libera todos los buffers, sin tocar los punteros de las entidades: hay que
llamarlo tras reinicializar los managers de la escena (por ejemplo al empezar un
nivel), porque las entidades desaparecen sin pasar por `restore`. La asignación ocurre una vez por entidad y dibujo, no por frame.

**Contrato con el juego.** El renderer no busca duplicados ni solapes entre buffers.
Posiciones `u8` dentro de
pantalla, con sumas de posición y tamaño hasta 255 (el recorte por la derecha y
abajo lo hace el módulo de sprites); el build falla con coordenadas que no
sean `u8`. Las sumas de las cajas envolventes saturan en 255. Cada manager
aparece una sola vez en la tabla de la escena: repetirlo duplica sus
entidades en el array de trabajo y corrompe la pantalla.

Los sprites con `MASKED`/`RECOLOR` usan las rutinas correspondientes del
módulo de sprites.

## 9. Colisión y eventos

*Revisado el 2026-11-05 (fase 7).* La versión inicial de esta sección definía
una tabla global de pares, un buffer de eventos de cinco bytes y roles
`COLLIDER`/`COLLISIONABLE`. La primera implementación fiel a ese diseño pesó
unos 980 bytes y la optimizada unos 5.300, frente a unos 330 del AABB previo:
inaceptable para juegos de CPC que caben en 64 KB. Se sustituye por un diseño
sin estado global. Presupuesto vinculante: **300 bytes de código y ninguna
tabla ni buffer** para `core/ecs_collision.s`.

El componente `COLLISION` añade un único campo, `ECS_E_COLLISION_CONTACT`
(`u8`): ocho canales de estado, uno por bit. Cada pasada usa el canal que le
indica el llamante y guarda en él si el sujeto tocaba algo en la última pasada
de ese canal. `ECS_COLLISION_TOUCHING=0x01` es el canal por defecto.

`fwk_ecs_collide` comprueba **un sujeto contra los objetivos de un manager**:

| Registro | Entrada |
|---|---|
| `IX` | manager de los objetivos |
| `IY` | entidad sujeto |
| `BC` | máscara de componentes que debe tener el objetivo (inclusiva, como `fwk_ecs_system_run`) |
| `HL` | callback |
| `E` | canal: un bit de `ECS_E_COLLISION_CONTACT` (0 = sin estado, todo contacto es `ENTER`) |

Visita las entidades `ACTIVE` del manager que cumplan `BC`, salta el propio
sujeto y llama al callback por cada una cuya caja AABB solape con la del
sujeto. El solape es estricto en los cuatro lados y usa sumas `u8` sin
saturar: las posiciones deben estar dentro de la pantalla (`X` hasta 79, `Y`
hasta 199) y anchura y altura no pueden ser cero ni hacer que la suma pase
de 255. Los managers y los sujetos pueden coincidir; los objetivos no
necesitan el componente `COLLISION`, solo `X`, `Y`, anchura y altura.

**Callback.** `IX`=manager, `IY`=objetivo, `HL`=sujeto, `A`=tipo. Con
`IX`/`IY` así el callback puede llamar directamente a
`fwk_ecs_entity_mark_destroy` para destruir el objetivo; no puede crear
entidades ni cambiar máscaras. Puede modificar cualquier registro salvo `SP`.
Devolver carry activo detiene la pasada: `fwk_ecs_collide` devuelve carry y el
`A` del callback (como `fwk_ecs_system_run`, con `A=0` convertido en
`FWK_ECS_ERR_CALLBACK`) y **no actualiza** `ECS_E_COLLISION_CONTACT`.

**Eventos por sujeto y canal.** Los tipos son `ECS_COLLISION_ENTER=1`,
`STAY=2` y `EXIT=3`. Si el sujeto no tocaba nada en la pasada anterior *de ese
canal*, cada contacto llega como `ENTER`; si ya tocaba, como `STAY`. Cuando una
pasada termina sin contactos y el canal indicaba contacto, se hace una última
llamada con `A=EXIT`, `IY=0` (no hay objetivo) y `HL`=sujeto. Al terminar sin
error, el bit del canal queda igual a «hubo algún contacto». El estado es por
sujeto y canal, no por pareja: si el sujeto ya tocaba un objetivo del canal,
un segundo objetivo nuevo llega como `STAY`. **Cada grupo de objetivos que se
prueba contra el mismo sujeto necesita su propio canal**: con un canal
compartido, una pasada que no encuentra contactos borra el estado de la otra y
provoca `EXIT` y `ENTER` falsos en cada frame. Ocho canales por sujeto; un
juego que necesite distinguir parejas guarda su propio estado. No hay buffer
ni overflow.

**Errores.** Los de `fwk_ecs_system_run`: manager no válido, bloqueado
(`FWK_ECS_ERR_BUSY`), callback nulo, máscara fuera del perfil. Salida: carry
limpio y `A=0`, o carry activo y `A=FWK_ECS_ERR_*`; `IX` e `IY` se conservan.
Requiere coordenadas `u8` (el build falla con `u16` o `fixed_8_8`).

**Límites que conviene conocer.**

- *Efectos por objetivo frente a efectos por contacto.* El estado es por
  sujeto y canal, no por objetivo: un objetivo nuevo que empieza a tocarse
  mientras el canal ya está activo llega como `STAY`. Un efecto que debe
  ocurrir con cada objetivo (recoger una moneda) actúa en toda llamada salvo
  `EXIT`; un efecto que debe ocurrir una vez por contacto (quitar una vida)
  actúa en `ENTER`, y un segundo enemigo tocado sin haber dejado de tocar al
  primero no lo repite. Si el juego necesita otra cosa, guarda su propio
  estado (por ejemplo un temporizador de invulnerabilidad).
- `E` debe tener **exactamente un bit** (o ser 0). Con varios bits los
  estados de esos canales se funden.
- El campo `ECS_E_COLLISION_CONTACT` de una plantilla debe ser 0: las
  entidades se crean copiando la plantilla y un estado heredado produciría un
  `STAY` o `EXIT` espurio.
- No es reentrante, y no lo es de forma estricta: cualquier llamada, también
  la que devuelve un error (`BUSY`, manager no válido, máscara fuera del
  perfil), sustituye la dirección del callback, el sujeto y el canal en cuanto
  se la llama. Un callback no debe volver a llamar a la rutina.
- El estado del sujeto no se comprueba: un sujeto que un callback destruye
  sigue probándose contra el resto de objetivos de esa pasada.
- Un objetivo destruido en `ENTER` deja de existir, por lo que la pasada
  siguiente puede producir un `EXIT` sin objetivo (`IY=0`); los callbacks
  deben tolerarlo.

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
- `ANIMATION` (fase 8, revisado el 2026-11-05) añade tres campos por entidad:
  `ECS_E_ANIMATION_DESCRIPTOR` (`pointer`, cero = sin animación),
  `ECS_E_ANIMATION_FRAME` y `ECS_E_ANIMATION_TIMER` (`u8`). El descriptor es
  inmutable y compartible y tiene el formato de `core/ecs_animation.inc`:
  byte `count` (1..255), byte `duration` (1..255) y `count` punteros de sprite.
  - `fwk_ecs_system_animation` (`IX`=manager; resultado como
    `fwk_ecs_system_run`) recorre las entidades `ACTIVE|ANIMATION` con
    descriptor. Cada llamada decrementa su `timer`; al llegar a cero recarga
    `duration`, avanza `frame` (vuelve a 0 tras el último), pone
    `ECS_E_RENDER_SPRITE` al puntero de ese frame y activa `ECS_RENDER_DIRTY`.
    Una entidad sin descriptor no se toca.
  - `fwk_ecs_anim_set` (`IY`=entidad, `HL`=descriptor o 0; carry limpio y
    `A=0`; preserva `IX`/`IY`) cambia de animación entre recorridos. Un
    descriptor distinto reinicia en el frame 0 con el `timer` igual a la
    duración, pone el sprite y activa `DIRTY`; `HL=0` detiene la animación,
    deja `frame` y `timer` a 0 y conserva el sprite actual. Elegir el descriptor
    ya activo no cambia nada mientras el `timer` sea distinto de cero; con
    `timer` a cero («sin arrancar», como en una plantilla que ya trae el
    descriptor) se trata como un cambio y arranca. Por eso `fwk_ecs_anim_set`
    puede llamarse en cada frame con el descriptor del estado actual.
  - Una entidad nueva debe iniciarse con `fwk_ecs_anim_set` tras crearla: una
    plantilla con descriptor y `timer` a cero también arranca así.
  - **Orden de llamadas.** El sistema cuenta atrás el `timer` en la misma
    pasada en que se llamó a `fwk_ecs_anim_set` si esta fue antes: el frame 0
    dura entonces una llamada menos (con duración 1 no llega a mostrarse).
    Llamar a `fwk_ecs_anim_set` después del sistema da la duración completa.
  - `fwk_ecs_anim_set` no comprueba el estado de la entidad ni el bit
    `ANIMATION`: sobre una entidad `DISABLED` o `PENDING_DESTROY` también
    escribe el sprite y activa `DIRTY`. Una animación de un solo frame
    (`count` 1) vuelve a fijar el sprite y a activar `DIRTY` cada `duration`
    llamadas aunque no cambie nada; para una pose fija conviene `duration` 255
    o detener la animación con `HL=0` tras elegirla.
  - **Límites.** `count` y `duration` van de 1 a 255; con 0 el comportamiento
    es indefinido y **silencioso** (`duration` 0 tarda 256 llamadas en avanzar,
    `count` 0 lee un puntero fuera del descriptor). El descriptor no lleva el
    tamaño del sprite: `ECS_E_WIDTH`/`HEIGHT` no se modifican, de modo que
    frames de tamaños distintos requieren que el juego ajuste la geometría
    (respetando la regla de render con fondo capturado). Si el juego cambia
    `ECS_E_RENDER_SPRITE` por su cuenta y después llama a
    `fwk_ecs_anim_set` con el descriptor activo, el sprite no se restituye
    hasta el siguiente avance.
  - Presupuesto vinculante: **150 bytes de código y ningún dato** para
    `core/ecs_animation.s`; el valor medido es el de `docs/validation.md`.
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
ECS_ABI_MINOR = 2
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
semántica de carry requiere incrementar la versión ABI. La 2.1 añade
`ECS_E_CADENCE` (desplaza los offsets posteriores a `ECS_E_HEIGHT`),
`fwk_ecs_tick` y `fwk_ecs_system_run_any`. La 2.2 quita `ECS_E_RENDER_BACKGROUND_CAP`,
hace que el renderer sea dueño de `ECS_E_RENDER_BACKGROUND`, amplía el descriptor de
escena a 11 bytes y añade `FWK_ECS_RENDER_POOL` y `fwk_ecs_render_reset`. Añadir una rutina sin
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
