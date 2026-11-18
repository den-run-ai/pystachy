#!/bin/bash
# Redo the JIT and build phases with a warm-up run per commit and three timed runs (resumable).
set -u
S=/tmp/claude-0/-home-user-pystachy/878ad953-6ea7-597d-82db-1ba899e22ec2/scratchpad
SW=$S/sweep; V=$S/v2; PY=/usr/local/bin/python3.13
for v in $(env | grep -o '^PYSTACHY_[A-Z0-9_]*'); do unset "$v"; done
echo "jit/build start $(date -u +%H:%M:%S); load $(cut -d' ' -f1-3 /proc/loadavg)"
(cd $SW && $PY -I timing.py $SW/commits_v2.txt $V/raw/timing.json --aot-reps 5 --micro-reps 7 --jit-reps 3 --build-reps 3 --cpu 3 --warmup --resume 2>&1 | grep --line-buffered -E "^(aot|jit|build) |timing done|Error|Traceback")
echo "all done $(date -u +%H:%M:%S); load $(cut -d' ' -f1-3 /proc/loadavg)"
