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
    # En macOS intentamos usar Docker automaticamente si esta disponible.
    if command -v docker >/dev/null 2>&1; then
        echo "==> macOS detectado: usando Docker para la compilacion."
        docker build -t glasnostfwk . && \
        docker run --rm -it -v "$(pwd)":/work -w /work glasnostfwk bash -c './setup.sh'
        exit $?
    fi
    echo
    echo "ERROR: la compilacion desde fuente del toolchain no esta soportada en macOS."
    echo "       (SDCC y las herramientas de CPCTelera no compilan con clang/modern headers.)"
    echo
    echo "Opciones:"
    echo "  1) Instala Docker Desktop y vuelve a ejecutar ./setup.sh (recomendado)."
    echo "  2) Usa un CPCTelera Next precompilado (si lo tienes):"
    echo "       export CPCT_NEXT_PATH=/ruta/a/cpctelera"
    echo "       ./setup.sh"
    echo "  3) Usa una VM Linux."
    echo
    exit 1
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