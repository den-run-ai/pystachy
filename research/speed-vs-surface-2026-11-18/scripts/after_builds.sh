#!/bin/bash
# After every sample is built and analyzed: probes at the latest commit, then timing on the idle machine.
set -u
S=/tmp/claude-0/-home-user-pystachy/878ad953-6ea7-597d-82db-1ba899e22ec2/scratchpad
SW=$S/sweep; V=$S/v2; HEAD=1117-1034_3cf23d20; WT=$S/wt/$HEAD
PY=/usr/local/bin/python3.13
for v in $(env | grep -o '^PYSTACHY_[A-Z0-9_]*'); do unset "$v"; done
until grep -q "pipeline done" $S/logs/pipeline4.log 2>/dev/null; do sleep 20; done
echo "probes start $(date -u +%H:%M:%S)"
# 1. CPython's pure-Python stdlib on the import path (the head's own import_sweep overlay rules)
rm -rf $SW/cpython-overlay-$HEAD
(cd $WT && $PY tools/import_sweep.py --overlay ./pystachy $S/dl/cpython-src/Python-3.13.16/Lib $SW/cpython-overlay-$HEAD 2>&1 | tail -2)
ls $SW/cpython-overlay-$HEAD | wc -l
(cd $S && $PY -I $SW/method_sweep.py $WT $SW/qualified.json $S/results/methods-overlay-$HEAD.json -j 2 --timeout 300 --env PYSTACHY_PATH=$SW/cpython-overlay-$HEAD 2>&1 | tail -1)
# 2. every method opted in to dynamic Any
(cd $S && $PY -I $SW/method_sweep.py $WT $SW/qualified.json $S/results/methods-dynany-$HEAD.json -j 3 --prepend '# pystachy: dynamic-any\n' 2>&1 | tail -1)
echo "probes done $(date -u +%H:%M:%S); load $(cut -d' ' -f1-3 /proc/loadavg)"
sleep 60
# 3. timing: all samples interleaved with CPython, same options as the 12 November run
echo "timing start $(date -u +%H:%M:%S); load $(cut -d' ' -f1-3 /proc/loadavg)"
(cd $SW && $PY -I timing.py $SW/commits_v2.txt $V/raw/timing.json --aot-reps 5 --micro-reps 7 --jit-reps 2 --cpu 3 2>&1 | tail -3)
# 4. the two regressions: 15 interleaved runs at the bisected endpoints, the report commit and the fixes
R=$S/sweep/retime.py
(cd $SW && $PY -I $R float 15 $V/raw/retime-float.json bis_0ec827ac34 bis_b40ee875bf 1111-1528_b2182a4f 1111-1943_8434a911 1112-0850_0b13a212 1112-1351_30822255 1114-1000_80490143 $HEAD)
(cd $SW && $PY -I $R micro_words 15 $V/raw/retime-micro_words.json bis_6d4ed3d117 bis_a355c83ff7 1111-1528_b2182a4f 1111-1943_8434a911 1112-1351_30822255 1112-2100_bf699eb5 1114-1000_80490143 $HEAD)
echo "all done $(date -u +%H:%M:%S); load $(cut -d' ' -f1-3 /proc/loadavg)"
