#!/bin/bash

export DOCKER_HOST=unix:///var/run/docker-nvme.sock
INSIDE_PATH=${1/fastdata/fastdata2}
LOG_NAME=$(basename "$1")
LOG_NAME=${LOG_NAME/_compile_commands.json/_pairgen.log}
OUT_NAME=$(basename "$INSIDE_PATH")
OUT_NAME=${OUT_NAME/_compile_commands.json/_pairs.jsonl}
docker run --init --rm \
    -v /data:/data \
    -v /fastdata:/fastdata2 \
    -v /home/moyix/func_asm_pairgen:/pairgen \
    --tmpfs /build:exec \
    --tmpfs /fastdata:exec \
    pairgen \
    python3 /pairgen/func_extract.py binary_comments ${INSIDE_PATH} -o /fastdata2/pairs/${OUT_NAME} \
    &> /fastdata/pairgen_logs/${LOG_NAME}
zstd -q --rm /fastdata/pairs/"${OUT_NAME}"
