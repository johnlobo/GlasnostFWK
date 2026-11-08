# Dockerfile para compilar GlasnostFWK en un entorno Linux reproducible.
# Uso:
#   docker build -t glasnostfwk .
#   docker run --rm -it -v "$(pwd)":/work -w /work glasnostfwk make check
# O para una shell interactiva:
#   docker run --rm -it -v "$(pwd)":/work -w /work glasnostfwk bash
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV GLASNOST_LANG=es

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip git make build-essential \
        gcc g++ bison flex libboost-dev \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /work

# El toolchain se descarga en ./.toolchain (fuera de Git). Se comparte entre
# ejecuciones mediante un volumen si se desea.
CMD ["bash"]