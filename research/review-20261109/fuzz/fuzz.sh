#!/bin/bash
# usage: fuzz.sh FROM TO [aot]  : generate seeds, compare CPython with pystachy JIT (and AOT every 5th when "aot")
P=${PYSTACHY_REPO:?set PYSTACHY_REPO to the checkout that holds ./pystachy}/pystachy
ok=0; rej=0; diffs=0
for s in $(seq $1 $2); do
  python3.13 gen.py $s > f$s.py
  exp=$(timeout 30 python3.13 f$s.py 2>&1); ec=$?
  if [ $ec -ne 0 ]; then echo "seed $s: cpython failed ($ec): $(echo "$exp" | tail -1 | cut -c1-150)"; rm -f f$s.py; continue; fi
  got=$(PYSTACHY_PROGRAM_CACHE=0 timeout 120 $P run f$s.py 2>&1); gc=$?
  if echo "$got" | head -1 | grep -q "^f$s.py:[0-9]*: error:"; then rej=$((rej+1)); echo "seed $s REJECT: $(echo "$got" | head -1 | cut -c1-170)"; rm -f f$s.py; continue; fi
  if [ "$exp" != "$got" ] || [ $gc -ne 0 ]; then diffs=$((diffs+1)); echo "seed $s DIFF (status $gc)"; echo "$exp" > f$s.exp; echo "$got" > f$s.got; continue; fi
  if [ "$3" = "aot" ] && [ $((s % 4)) -eq 0 ]; then
    if timeout 300 $P build f$s.py -o f$s.bin 2>/dev/null; then
      got2=$(timeout 60 ./f$s.bin 2>&1); g2=$?
      if [ "$exp" != "$got2" ] || [ $g2 -ne 0 ]; then diffs=$((diffs+1)); echo "seed $s DIFF-AOT (status $g2)"; echo "$exp" > f$s.exp; echo "$got2" > f$s.got; continue; fi
      rm -f f$s.bin
    else echo "seed $s AOT build failed"; fi
  fi
  ok=$((ok+1)); rm -f f$s.py
done
echo "range $1..$2: ok=$ok rejected=$rej diffs=$diffs"
