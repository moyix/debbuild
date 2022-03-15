#!/bin/bash

export DOCKER_HOST=unix:///var/run/docker-nvme.sock
INSIDE_PATH=${1/fastdata/fastdata2}
LOG_NAME=$(basename "$1")
LOG_NAME=${LOG_NAME/_compile_commands.json/_rebuild.log}

docker run --init --rm --entrypoint bash \
    -v /data:/data \
    -v /fastdata:/fastdata2 \
    --tmpfs /build:exec \
    --tmpfs /fastdata:exec \
    debbuild \
    -c "python3 /scripts/gen_asm.py ${INSIDE_PATH}" \
    &> /fastdata/rebuild_logs/${LOG_NAME}
