# Matriz comparativa y decisiones

Las decisiones siguientes se basan en los fuentes de las revisiones fijadas,
no en las hipótesis iniciales.

| Sistema | Clasificación | Base elegida y mejoras | Incompatibilidades/dependencias eliminadas | Decisión y comprobación |
|---|---|---|---|---|
| Arranque, IRQ, sincronización | Núcleo común | Estructura de 6 IRQ presente en los cuatro; callback por frame nuevo | Referencias directas a audio, render y configuración de cada juego | `core/system.s`; construye con Next y escanea teclado una vez/frame |
| Entrada | Núcleo común | Tabla de acciones de model01; flancos motivados por debounce de boop | Tablas `_menu_*`/`_match_*` de boop y entidades de model01 | Estado `held/pressed/released` por máscara configurable; entrada sostenida comprobada en la vertical |
| Array/pool | Núcleo común | `array.s` es idéntico en model01, DeckTower y PocketFever | Sus descriptores de componentes y estructuras de entidad | Pool compacto para registros arbitrarios; capacidad, `get`, borrado compacto y `foreach` |
| Entidades | Especialización | No se elige estructura universal | Model01 usa plataforma/componentes; PocketFever usa física 8.8 y bola | Registros del consumidor: `motion_u8`, `physics_platform` y `physics_8_8` permanecen separados |
| Animación | Módulo genérico opcional | Descriptor/temporizador de model01 | Eliminadas sala, velocidad, entidad y política «solo al moverse»; la animación de impacto de DeckTower sigue específica | `extensions/animation.s`; periodo, bucle, render y pausa del consumidor comprobados en 6128/464 |
| Render básico | Núcleo de vídeo + extensiones tilemap/sprite | Primitivas comunes DeckTower/PocketFever + modelo de geometría nuevo | Tablero/cartas/bola/cola de entidades y reglas de salas | Direcciones generadas, limpieza y byte plot; tilemap con viewport y sprite rectangular con clipping |
| Restauración de fondo | Módulo opcional y ejemplos | Captura rectangular común contrastada con mensajes y borrado especializado de PocketFever | Buffers globales, fondo de tapete y colas propias de cada juego | `video/sprite` captura/restaura el área visible en buffer del consumidor; `window` conserva el contrato sin clipping |
| Texto | Módulo opcional | ABI Mode 0 de CPCTelera Next | Fuentes y números específicos de juego | Adaptador `ui/text.s`; `board` demuestra uso sin assets originales |
| Ventanas/mensajes | Geometría opcional + composición del juego | Captura/restauración común en los cuatro proyectos; caja compartida por DeckTower/PocketFever | Eliminadas espera de tecla, menús, combate, texto y buffer fijo | `ui/window.s`; validación, borde/relleno, captura, restauración y reapertura comprobados en 6128/464 |
| Ventanas/mensajes | Especialización pendiente | Variantes incompatibles: model01/boop frente a buffer pequeño Deck/Pocket | Geometría, buffers y semántica de cierre | No consolidado para evitar una API falsa; cajas pueden añadirse sobre vídeo |
| Audio | Módulo genérico opcional | ABI AKG compartida por model01/boop/DeckTower y player de CPCTelera Next | Subsongs, símbolos y export Boop concretos | Adaptador genérico; `audio` enlaza player y datos MIT, y verifica música/SFX en PSG |
| Bancos 128 KB | Módulo genérico opcional | Stub de model01/DeckTower; prueba real fijada en ventana | DeckTower declaraba actualmente detección no operativa por ubicación | `resources/bank.s`; roundtrip ejecutado en 6128 y fallback en 464 |
| Disco | Módulo genérico opcional | Secuencia firmware verificada de DeckTower | Eliminadas tabla fija, política de bancos y fallo con `HALT` | `resources/disk.s`; el manifiesto añade archivos 8.3 y `diskload` verifica lectura real en 6128/464 |
| Compresión | Módulo genérico opcional | ABI ZX7B de CPCTelera Next y separación observada en DeckTower | Eliminados buffer fijo y packs concretos del juego | `resources/zx7b.s`; payload 256 B -> 23 B -> 256 B comprobado en emulador |
| Recursos | Módulo genérico opcional | Concepto de seeding de DeckTower | Tabla de payloads fija | Generador rechaza bancos, tamaños, alineación y solapamientos inválidos |
| Mapas/colisión/física | Especializaciones componibles | model01 para plataforma byte, consulta row-major y tipos de tile; PocketFever para integración 8.8 | Eliminadas entidad, salas, portales, render y reglas; colisión entre bolas incompatible | `tilemap` de solo lectura y `platform_tilemap` se componen con el perfil byte y se prueban en `tilecoll`; física 8.8 y colisión entre bolas siguen separadas |
| Bytecode | Especialización por género | model01 (comportamientos) y DeckTower (combate) son intérpretes distintos | Operaciones y estado concretos | Conservados como candidatos, no servicio universal |
| Generadores gráficos | Herramienta | Enfoque determinista de PocketFever | Supuestos de bolas, tapete y 64 direcciones | Nuevo generador de geometría/vídeo con referencia y casos conocidos |
| Dibujo de bolas | Especialización optimizada | PocketFever `ball_blit.s` | Geometría 6x8, patrones y fondo específicos | Se conserva separado; `video/sprite` ofrece el camino rectangular general sin afirmar el mismo coste |

## Resultado de las hipótesis iniciales

- Confirmado: model01 ofrece la separación `game -> sys` más explícita y sus
  pruebas de arquitectura son la referencia más fuerte.
- Confirmado: DeckTower contiene el trabajo más desarrollado de bancos,
  carga y staging, pero parte de su detector está documentada como no operativa
  en esa revisión y su tabla de payloads es específica.
- Confirmado: PocketFever aporta generación determinista y optimizaciones de
  dibujo especializadas. `ball_blit` no se convirtió en primitiva universal.
- Confirmado parcialmente: boop contiene debounce/flancos y audio AKG útil,
  pero su entrada está acoplada a callbacks concretos; solo se recuperó el
  mecanismo, no las tablas del juego.
