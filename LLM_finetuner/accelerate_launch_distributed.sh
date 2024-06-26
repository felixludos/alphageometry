#!/usr/bin/env bash

set -eux

GPUS_PER_NODE=$(nvidia-smi --query-gpu=name --format=csv,noheader | wc -l)
export ACCELERATE_LOG_LEVEL=info

accelerate launch --config_file ~/reinforcement/alphageometry/LLM_finetuner/distributed_tests/distributed_example.yaml \
    --num_processes $((NUM_MACHINES * GPUS_PER_NODE)) \
    --num_machines "$NUM_MACHINES" \
    --rdzv_backend c10d \
    --main_process_ip "$MASTER_IP" \
    --main_process_port 29500 \
    --machine_rank "$MACHINE_RANK" \
    "$@"