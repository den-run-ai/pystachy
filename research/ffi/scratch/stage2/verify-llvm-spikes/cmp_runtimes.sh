#!/bin/sh
# usage: cmp_runtimes.sh OUTDIR test1 test2 ...   runs each tests/NAME.py JIT and AOT with home_orig and home_mod
V=$(dirname "$0"); O=$1; shift; mkdir -p "$O"
T=/home/user/pystachy/tests
for n in "$@"; do
  in=/dev/null; [ -f "$T/$n.in" ] && in="$T/$n.in"
  for h in home_orig home_mod; do
    H=$V/$h
    (PYSTACHY_HOME=$H python3 $H/pystachy.py run "$T/$n.py" a1 a2 < "$in"; echo "[exit $?]") > "$O/$n.$h.jit" 2> "$O/$n.$h.jit.err"
    PYSTACHY_HOME=$H python3 $H/pystachy.py build "$T/$n.py" -o "$O/$n.$h.exe" 2> "$O/$n.$h.aot.err" &&
      ("$O/$n.$h.exe" a1 a2 < "$in"; echo "[exit $?]") > "$O/$n.$h.aot" 2>> "$O/$n.$h.aot.err"
    if [ -n "$STRESS" ]; then
      (PYSTACHY_GC_STRESS=$STRESS "$O/$n.$h.exe" a1 a2 < "$in"; echo "[exit $?]") > "$O/$n.$h.aotstress" 2>> "$O/$n.$h.aot.err"
    fi
  done
  r=""
  for m in jit aot ${STRESS:+aotstress}; do
    if cmp -s "$O/$n.home_orig.$m" "$O/$n.home_mod.$m"; then s=same; else s=DIFF; fi
    if cmp -s "$O/$n.home_mod.$m" "$T/$n.out"; then e=ok; else e=NOTCPY; fi
    if cmp -s "$O/$n.home_orig.$m.err" "$O/$n.home_mod.$m.err" 2>/dev/null || [ $m = aotstress ]; then es=""; else es="(stderr differs)"; fi
    r="$r $m:$s/$e$es"
  done
  echo "$n:$r"
done
