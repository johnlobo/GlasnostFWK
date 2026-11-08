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

# 2. Toolchain (CPCTelera Next + SDCC)
# En macOS, compilar SDCC desde fuente no es compatible con clang/modern headers:
# se recomienda usar una instalacion precompilada (CPCT_NEXT_PATH) o Docker/Linux.
echo "==> [2/5] Toolchain"
if [ "$(uname -s)" = "Darwin" ] && [ -z "${CPCT_NEXT_PATH:-}" ]; then
    echo "    Aviso: en macOS la compilacion desde fuente de SDCC no esta soportada."
    echo "    Opciones:"
    echo "      - Usa un CPCTelera Next precompilado: export CPCT_NEXT_PATH=/ruta/a/cpctelera"
    echo "      - Usa Docker/VM con Linux y ejecuta ./setup.sh dentro."
    echo "    Continuando de todos modos (puede fallar)..."
fi
"$GLASNOST" install-toolchain

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
echo "    Emulador: GLASNOST_EMULATOR=/ruta/a/cpct_macape make run"