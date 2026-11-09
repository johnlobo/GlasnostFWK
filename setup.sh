#!/usr/bin/env bash
# setup.sh — configuración inicial de GlasnostFWK en un solo paso.
#
# Detecta la plataforma, instala las dependencias del sistema, descarga y
# compila el toolchain fijado, verifica el entorno y construye el framework.
# Equivalente a:
#   glasnost install-deps && glasnost install-toolchain && glasnost doctor && make generate && make check
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

GLASNOST="$ROOT/bin/glasnost"

echo "==> GlasnostFWK: configuración inicial"

# 1. Dependencias del sistema (Boost, bison, flex, gcc, ...)
echo "==> [1/5] Dependencias del sistema"
"$GLASNOST" install-deps --yes

# 2. Toolchain (CPCTelera Next + SDCC, compilado desde fuente) e img2cpc
# (incluido en tools/img2cpc, sin dependencia de FreeImage).
echo "==> [2/5] Toolchain"
"$GLASNOST" install-toolchain
make -C "$ROOT/tools/img2cpc" -j4

# 3. Verificación
echo "==> [3/5] Verificación"
"$GLASNOST" doctor

# 4. Generación de recursos y vídeo
echo "==> [4/5] Generación"
make generate

# 5. Construcción y pruebas rápidas
echo "==> [5/5] Construcción y pruebas"
make check

# Opcional: dejar `glasnost` disponible en el PATH
if [ -z "${GLASNOST_SKIP_CLI:-}" ]; then
    "$GLASNOST" install-cli || true
fi

echo
echo "==> Listo. Usa 'make check' mientras desarrollas y 'make test' al cerrar."
echo "    Emulador: GLASNOST_EMULATOR=/ruta/al/emulador make run"