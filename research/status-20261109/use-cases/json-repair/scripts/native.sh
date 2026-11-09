#!/bin/sh
# Native parity spot check on a main-equivalent compiler; all writes stay in $S.
S=/tmp/claude-0/-home-user-pystachy/b0f95023-79a1-5e08-b42b-506118072379/scratchpad/agentI-jsonrepair.IqW3dA
M=$S/main
C=/home/user/wt/alpha2-qual/pystachy
for v in $(env | sed -n 's/^\(PYSTACHY[A-Z0-9_]*\)=.*/\1/p'); do unset "$v"; done
export PYSTACHY_HOME=$M PYSTACHY_CACHE=$S/cache PYSTACHY_PATH=$M/ports PYSTACHY_JOBS=2 PYTHONPYCACHEPREFIX=$S/pycache
PAR="python3.13 -I $M/tools/json_repair_parity.py"
cd $S/run || exit 1
t() { s=$(date +%s.%N); "$@"; rc=$?; e=$(date +%s.%N); echo "[rc=$rc, $(echo "$e - $s" | bc) s] $*" >&2; return $rc; }
echo "== compiler: $($C --version) sha256 $(sha256sum $C | cut -c1-16)"; env | grep '^PYSTACHY' | sort
echo "== AOT build"; t timeout 600 $C build $M/tests/upstream/json_repair/replay.py -o $S/run/replay-aot
echo "== AOT corpus"; t timeout 300 ./replay-aot inputs.jsonl > native-aot.out; $PAR native-aot.out --report native-aot-report.json | head -3
echo "== AOT probes"; t timeout 120 ./replay-aot probes.jsonl > probes-aot.out; wc -l < probes-aot.out
echo "== JIT corpus"; t timeout 600 $C run $M/tests/upstream/json_repair/replay.py inputs.jsonl > native-jit.out; $PAR native-jit.out --report native-jit-report.json | head -3
echo "== JIT probes"; t timeout 300 $C run $M/tests/upstream/json_repair/replay.py probes.jsonl > probes-jit.out; wc -l < probes-jit.out
echo "== extension build (the JSON verifier path)"; rm -rf $S/ext; mkdir -p $S/ext/pystachy_json_repair && cp $M/examples/json_repair/pystachy_json_repair/__init__.py $S/ext/pystachy_json_repair/ &&
  (cd $M && t timeout 600 $C ext examples/json_repair/_native.py -o $S/ext/pystachy_json_repair/_native.abi3.so)
echo "== extension verifier"; (cd $S && t timeout 300 python3.13 -I $M/tests/upstream/json_repair/extension.py $S/ext)
echo "== AOT corpus, GC stress every allocation (capped 240 s)"; t timeout 240 env PYSTACHY_GC_STRESS=1 ./replay-aot inputs.jsonl > native-aot-gc.out; $PAR native-aot-gc.out --report native-aot-gc-report.json | head -3
echo "== done"
