#!/bin/bash
# usage: fuzz2.sh FROM TO : gen2.py seeds on the base and the fixed compiler against CPython
BASE=${BASE_COMPILER:?set BASE_COMPILER to the base ./pystachy}
FIX=${FIXED_COMPILER:?set FIXED_COMPILER to the patched ./pystachy}
ok=0; base_rej=0; fix_rej=0; diffs=0
for s in $(seq $1 $2); do
  python3.13 gen2.py $s > u$s.py
  exp=$(timeout 30 python3.13 u$s.py 2>&1); ec=$?
  if [ $ec -ne 0 ]; then echo "seed $s: cpython failed: $(echo "$exp" | tail -1 | cut -c1-150)"; rm -f u$s.py; continue; fi
  b=$(PYSTACHY_PROGRAM_CACHE=0 timeout 120 $BASE run u$s.py 2>&1); bc=$?
  f=$(PYSTACHY_PROGRAM_CACHE=0 timeout 120 $FIX run u$s.py 2>&1); fc=$?
  keep=0
  if echo "$b" | head -1 | grep -q "^u$s.py:[0-9]*: error:"; then base_rej=$((base_rej+1)); elif [ "$b" != "$exp" ]; then diffs=$((diffs+1)); keep=1; echo "seed $s BASE-OUTPUT-DIFF (status $bc)"; echo "$exp" > u$s.exp; echo "$b" > u$s.base; fi
  if echo "$f" | head -1 | grep -q "^u$s.py:[0-9]*: error:"; then fix_rej=$((fix_rej+1)); keep=1; l=$(echo "$f" | head -1 | sed -n "s/^u$s.py:\([0-9]*\):.*/\1/p"); echo "seed $s FIXED-REJECT: $(echo "$f" | head -1 | cut -d: -f3- | cut -c1-110) :: $(sed -n "${l}p" u$s.py | cut -c1-150)";
  elif [ "$f" != "$exp" ]; then diffs=$((diffs+1)); keep=1; echo "seed $s FIXED-OUTPUT-DIFF (status $fc)"; echo "$exp" > u$s.exp; echo "$f" > u$s.fixed; else ok=$((ok+1)); fi
  [ $keep = 0 ] && rm -f u$s.py
done
echo "range $1..$2: fixed-ok=$ok base-rejected=$base_rej fixed-rejected=$fix_rej output-diffs=$diffs"
