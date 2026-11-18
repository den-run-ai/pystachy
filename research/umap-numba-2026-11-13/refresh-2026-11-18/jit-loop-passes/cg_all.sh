#!/bin/bash
SP=/tmp/claude-0/-home-user-pystachy/d93c2c20-f8ea-590f-9162-601d62fd95f8/scratchpad
out=$SP/passx/callgrind.tsv; rm -f $out
export PATH=$SP/venv-dev/bin:$PATH
unset PYSTACHY_HOME PYSTACHY_OPT PYSTACHY_LLVM PYSTACHY_JIT_OPT
cd $SP/pr-jitlp
while read -r name args; do
  $SP/passx/callgrind_loops.sh $SP/pr-jitlp $out $name $args
done <<'LIST'
json_loads bench/pyperformance/json_loads.py 200
chaos bench/pyperformance/chaos.py 10
richards bench/pyperformance/richards.py 20
nbody bench/pyperformance/nbody.py 10
raytrace bench/pyperformance/raytrace.py 4
go bench/pyperformance/go.py 4
scimark bench/pyperformance/scimark.py 2
hexiom bench/pyperformance/hexiom.py 20
generators bench/pyperformance/generators.py 10
float bench/pyperformance/float.py 10
fannkuch bench/pyperformance/fannkuch.py 2
nqueens bench/pyperformance/nqueens.py 10
spectral_norm bench/pyperformance/spectral_norm.py 10
json_dumps bench/pyperformance/json_dumps.py 20
regex_v8 bench/pyperformance/regex_v8.py 2
LIST
