#!/bin/bash
# usage: fuzz4.sh FROM TO [MODE] : gen4.py seeds, three ways (CPython, BASE_COMPILER, FIXED_COMPILER)
# every program BASE compiles must compile with FIXED and print the same; every program FIXED
# compiles must print what CPython prints, or what BASE prints where BASE compiles it
BASE=${BASE_COMPILER:?}; FIX=${FIXED_COMPILER:?}; MODE=${3:-}
D=${OUT:-out4}; mkdir -p $D
n=0; both=0; newacc=0; bothrej=0; REGRESS=0; fixdiff=0; basediff=0; outchg=0
for s in $(seq $1 $2); do
  f=$D/q$MODE$s.py
  python3.13 gen4.py $s $MODE > $f
  exp=$(timeout 30 python3.13 $f 2>&1); ec=$?
  if [ $ec -ne 0 ]; then echo "seed $s: cpython failed: $(echo "$exp" | tail -1)"; continue; fi
  n=$((n+1))
  b=$(PYSTACHY_PROGRAM_CACHE=0 timeout 120 $BASE run $f 2>&1); bec=$?
  x=$(PYSTACHY_HOME=${FIXED_HOME:?} PYSTACHY_PROGRAM_CACHE=0 timeout 120 $FIX run $f 2>&1); xec=$?
  brej=0; xrej=0
  echo "$b" | head -1 | grep -q "^$f:[0-9]*: error:" && brej=1
  echo "$x" | head -1 | grep -q "^$f:[0-9]*: error:" && xrej=1
  line=$(grep -A1 "^def f(" $f | tail -1 | cut -c1-230)
  keep=0
  if [ $brej = 0 ] && [ $xrej = 1 ]; then
    REGRESS=$((REGRESS+1)); keep=1
    echo "seed $s REGRESSION (base compiles, fixed rejects): $(echo "$x" | head -1 | cut -d: -f3- | cut -c1-80) :: $line"
  elif [ $brej = 0 ] && [ $xrej = 0 ]; then
    both=$((both+1))
    if [ "$b" != "$x" ]; then outchg=$((outchg+1)); keep=1; echo "seed $s OUTPUT-CHANGED vs base :: $line"; echo "$b" > $f.base; echo "$x" > $f.fixed; echo "$exp" > $f.exp; fi
    if [ "$b" != "$exp" ]; then basediff=$((basediff+1)); fi
  elif [ $brej = 1 ] && [ $xrej = 0 ]; then
    newacc=$((newacc+1))
    if [ "$x" != "$exp" ]; then fixdiff=$((fixdiff+1)); keep=1; echo "seed $s NEW-ACCEPT-DIFFERS from CPython :: $line"; echo "$x" > $f.fixed; echo "$exp" > $f.exp; fi
  else
    bothrej=$((bothrej+1))
  fi
  [ $keep = 0 ] && rm -f $f
done
echo "range $1..$2 mode=${MODE:-plain}: programs=$n both-compile=$both (output-changed=$outchg base-differs-from-cpython=$basediff) new-accepts=$newacc (differ-from-cpython=$fixdiff) both-reject=$bothrej REGRESSIONS=$REGRESS"
