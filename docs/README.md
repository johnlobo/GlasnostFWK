# Documentación

- [`manual.html`](manual.html) / [`manual.pdf`](manual.pdf): el manual completo (se regenera con `make manual`).
- [`guide/`](guide/): para empezar y aprender. Tu primer juego (`first-game.md` y sus pasos),
  el recorrido por el código de `nave`, la guía del juego de plataformas y la instalación en
  Apple Silicon.
- [`reference/`](reference/): contratos y uso de cada pieza. CLI `glasnost`, arquitectura y API,
  ABI del ECS, sprites, tilemaps, física, audio, disco y ZX7B, ventanas, migración.
- [`design/`](design/): por qué es como es. Plan del ECS 2.0, matriz comparativa, procedencia,
  paridad del juego de plataformas, validación, rendimiento y tamaños.

Los 15 ejemplos públicos viven en `examples/`; las 7 validaciones y mediciones
internas, en `framework/validations/`. El catálogo de ambos está en la sección 8
del manual. `text` sustituye a `board`; `vertical` se ha retirado.
