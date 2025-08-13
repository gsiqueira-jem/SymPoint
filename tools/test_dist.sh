#!/usr/bin/env bash

export PYTHONPATH=./
GPUS=1
OMP_NUM_THREADS=$GPUS torchrun --nproc_per_node=$GPUS --master_port=$((RANDOM + 10000)) tools/test.py \
	 ./configs/svg/svg_pointT.yaml  ./checkpoints/best.pth --dist
