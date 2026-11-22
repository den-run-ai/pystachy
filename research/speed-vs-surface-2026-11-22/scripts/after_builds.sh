#!/bin/bash
# After every sample is built and analyzed: probes at the latest commit, then timing on the idle machine,
# re-timings of the regressions, and idle-machine bootstraps of the three editions' latest commits.
set -u
S=/tmp/claude-0/-home-user-pystachy/878ad953-6ea7-597d-82db-1ba899e22ec2/scratchpad
SW=$S/sweep; V=$S/v3; HEAD=1121-1151_4998521d; WT=$S/wt/$HEAD
PY=/usr/local/bin/python3.13
for v in $(env | grep -o '^PYSTACHY_[A-Z0-9_]*'); do unset "$v"; done
until grep -q "pipeline done" $S/logs/pipeline5.log 2>/dev/null; do sleep 20; done
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
# 3. timing: all samples interleaved with CPython; JIT and build runs after one untimed warm-up run per commit
echo "timing start $(date -u +%H:%M:%S); load $(cut -d' ' -f1-3 /proc/loadavg)"
(cd $SW && $PY -I timing.py $SW/commits_v3.txt $V/raw/timing.json --aot-reps 5 --micro-reps 7 --jit-reps 3 --build-reps 3 --warmup --cpu 3 --resume 2>&1 | grep -E "^(aot|jit|build) |timing done|Error|Traceback" | tail -4)
# 4. the regressions: 15 interleaved runs at the bisected endpoints, the editions' latest commits and v0.6.0
R=$SW/retime.py
E="1111-1943_8434a911 1117-1034_3cf23d20 1119-2044_817c9cd9 $HEAD"
[ -f $V/raw/retime-float.json ] || (cd $SW && $PY -I $R float 15 $V/raw/retime-float.json bis_0ec827ac34 bis_b40ee875bf 1112-1351_30822255 $E)
[ -f $V/raw/retime-micro_words.json ] || (cd $SW && $PY -I $R micro_words 15 $V/raw/retime-micro_words.json bis_6d4ed3d117 bis_a355c83ff7 1112-2100_bf699eb5 $E)
[ -f $V/raw/retime-micro_fib.json ] || (cd $SW && $PY -I $R micro_fib 15 $V/raw/retime-micro_fib.json 1114-0748_a73c56c9 1114-1000_80490143 $E)
echo "retimes done $(date -u +%H:%M:%S); load $(cut -d' ' -f1-3 /proc/loadavg)"
# 5. bootstrap of each edition's latest commit, one at a time, in fresh worktrees
[ -f $V/raw/bootstrap-idle.json ] || $PY -I $V/scripts/bootstrap_idle.py $V/raw/bootstrap-idle.json \
  1111-1943_8434a911=8434a911bed2064f50539806d9c05c57003241c3 \
  1117-1034_3cf23d20=3cf23d20357be84bf731090112cdb89df0749cb4 \
  $HEAD=4998521d28413c6e32506105f836b6db9afeb1d7
echo "all done $(date -u +%H:%M:%S); load $(cut -d' ' -f1-3 /proc/loadavg)"
