# Matriz comparativa y decisiones

Las decisiones siguientes se basan en los fuentes de las revisiones fijadas,
no en las hipótesis iniciales.

| Sistema | Clasificación | Base elegida y mejoras | Incompatibilidades/dependencias eliminadas | Decisión y comprobación |
|---|---|---|---|---|
| Arranque, IRQ, sincronización | Núcleo común | Estructura de 6 IRQ presente en los cuatro; callback por frame nuevo | Referencias directas a audio, render y configuración de cada juego | `core/system.s`; construye con Next y escanea teclado una vez/frame |
| Entrada | Núcleo común | Tabla de acciones de model01; flancos motivados por debounce de boop | Tablas `_menu_*`/`_match_*` de boop y entidades de model01 | Estado `held/pressed/released` por máscara configurable; entrada sostenida comprobada en la vertical |
| Array/pool | Núcleo común | `array.s` es idéntico en model01, DeckTower y PocketFever | Sus descriptores de componentes y estructuras de entidad | Pool compacto para registros arbitrarios; capacidad, `get`, borrado compacto y `foreach` |
| Entidades | Especialización | No se elige estructura universal | Model01 usa plataforma/componentes; PocketFever usa física 8.8 y bola | Solo perfil opcional `motion_u8`; otros perfiles quedan por migrar |
| Animación | Módulo opcional pendiente | Model01 separa descriptor/avance | Política de movimiento y estructura de entidad | No incorporada aún: no había integración coherente sin traer el perfil entero |
| Render básico | Núcleo de vídeo | Primitivas comunes DeckTower/PocketFever + modelo de geometría nuevo | Tablero/cartas/bola/cola de entidades | Direcciones generadas, limpieza visible y byte plot; casos límite automáticos |
| Restauración de fondo | Ejemplo/especialización | Patrón explícito del tablero; huecos preservados | Buffers de mensaje y colas propias de cada juego | Ejemplo `board`; ejemplo `video` usa patrón testigo en hueco |
| Texto | Módulo opcional | ABI Mode 0 de CPCTelera Next | Fuentes y números específicos de juego | Adaptador `ui/text.s`; `board` demuestra uso sin assets originales |
| Ventanas/mensajes | Especialización pendiente | Variantes incompatibles: model01/boop frente a buffer pequeño Deck/Pocket | Geometría, buffers y semántica de cierre | No consolidado para evitar una API falsa; cajas pueden añadirse sobre vídeo |
| Audio | Módulo genérico opcional | ABI AKG compartida por model01/boop/DeckTower | Subsongs, símbolos y export Boop concretos | Adaptador genérico; solo enlaza si el juego aporta export AKG |
| Bancos 128 KB | Módulo genérico opcional | Stub de model01/DeckTower; prueba real fijada en ventana | DeckTower declaraba actualmente detección no operativa por ubicación | `resources/bank.s`; compila en ejemplo 128 KB, ejecución aún no verificada |
| Disco | Pendiente | Firmware loader de DeckTower inspeccionado | Tabla fija de nombres/destinos y dependencia AMSDOS | Manifiesto ya sustituye tabla; backend de lectura de disco no extraído aún |
| Compresión | Opcional pendiente | Wrapper ZX7B de DeckTower es separable | Buffer fijo y config del juego | No incorporado en esta primera consolidación |
| Recursos | Módulo genérico opcional | Concepto de seeding de DeckTower | Tabla de payloads fija | Generador rechaza bancos, tamaños, alineación y solapamientos inválidos |
| Mapas/colisión/física | Especializaciones | model01 para plataformas; PocketFever para 8.8/bolas | Estructuras y coordenadas incompatibles | No se fusionan; ejemplo plataforma usa extensión mínima independiente |
| Bytecode | Especialización por género | model01 (comportamientos) y DeckTower (combate) son intérpretes distintos | Operaciones y estado concretos | Conservados como candidatos, no servicio universal |
| Generadores gráficos | Herramienta | Enfoque determinista de PocketFever | Supuestos de bolas, tapete y 64 direcciones | Nuevo generador de geometría/vídeo con referencia y casos conocidos |
| Dibujo de bolas | Especialización optimizada | PocketFever `ball_blit.s` | Geometría 6x6/tabla de filas específica | No se generaliza; debe migrarse como extensión si un juego la necesita |

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
