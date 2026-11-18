#!/bin/bash
# Timing on the idle machine (resumable): all samples interleaved with CPython, then the two regressions.
# Rerun after an interruption: finished benchmark blocks and finished retimes are kept.
set -u
S=/tmp/claude-0/-home-user-pystachy/878ad953-6ea7-597d-82db-1ba899e22ec2/scratchpad
SW=$S/sweep; V=$S/v2; HEAD=1117-1034_3cf23d20; PY=/usr/local/bin/python3.13
for v in $(env | grep -o '^PYSTACHY_[A-Z0-9_]*'); do unset "$v"; done
echo "timing start $(date -u +%H:%M:%S); load $(cut -d' ' -f1-3 /proc/loadavg)"
(cd $SW && $PY -I timing.py $SW/commits_v2.txt $V/raw/timing.json --aot-reps 5 --micro-reps 7 --jit-reps 2 --cpu 3 --resume 2>&1 | grep --line-buffered -E "^(aot|jit|build) |timing done|Error|Traceback")
R=$SW/retime.py
[ -f $V/raw/retime-float.json ] || (cd $SW && $PY -I $R float 15 $V/raw/retime-float.json bis_0ec827ac34 bis_b40ee875bf 1111-1528_b2182a4f 1111-1943_8434a911 1112-0850_0b13a212 1112-1351_30822255 1114-1000_80490143 $HEAD)
[ -f $V/raw/retime-micro_words.json ] || (cd $SW && $PY -I $R micro_words 15 $V/raw/retime-micro_words.json bis_6d4ed3d117 bis_a355c83ff7 1111-1528_b2182a4f 1111-1943_8434a911 1112-1351_30822255 1112-2100_bf699eb5 1114-1000_80490143 $HEAD)
echo "all done $(date -u +%H:%M:%S); load $(cut -d' ' -f1-3 /proc/loadavg)"
