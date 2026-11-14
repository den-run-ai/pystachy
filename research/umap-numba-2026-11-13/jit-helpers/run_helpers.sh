#!/bin/bash
# PYSTACHY_OPT=-jithelpers (calls of the runtime) against the default (its small functions inlined, #705) on start-up, import-heavy, numeric, regex
# and object-heavy workloads: jit_variants.py for each, from the checkout's root (the ports read
# nothing else, but bench_pyperformance.py runs them there too).
# usage: run_all.sh CHECKOUT OUTDIR [NAME...]   (no NAME: every workload)
set -u
SP=/tmp/claude-0/-home-user-pystachy/d93c2c20-f8ea-590f-9162-601d62fd95f8/scratchpad
M=$SP/jitopt-meas
W=$M/work
root=$1; out=$2; shift 2
mkdir -p "$out"
cd "$root" || exit 1
PYS=$root/pystachy
# name rounds program args...
workloads=(
  "tiny 7 $W/tiny.py"
  "padded 5 $W/padded.py"
  "imports 5 $W/imports.py"
  "router 5 examples/route/route.py $W/rules.txt $W/events.txt --names"
  "umap 3 $W/umap_core.py 10000 16 10 15 200 7"
  "nbody 3 bench/nbody.py"
  "spectral 3 bench/spectral.py"
  "mandel 3 bench/mandel.py"
  "sieve 3 bench/sieve.py"
  "fib 3 bench/fib.py"
  "dictcount 3 bench/dictcount.py"
  "words 3 bench/words.py"
  "pp_chaos 3 bench/pyperformance/chaos.py 10"
  "pp_float 3 bench/pyperformance/float.py 10"
  "pp_nbody 3 bench/pyperformance/nbody.py 10"
  "pp_raytrace 3 bench/pyperformance/raytrace.py 4"
  "pp_scimark 3 bench/pyperformance/scimark.py 2"
  "pp_spectral_norm 3 bench/pyperformance/spectral_norm.py 10"
  "pp_fannkuch 3 bench/pyperformance/fannkuch.py 2"
  "pp_nqueens 3 bench/pyperformance/nqueens.py 10"
  "pp_regex_dna 3 bench/pyperformance/regex_dna.py 4"
  "pp_regex_effbot 3 bench/pyperformance/regex_effbot.py 20"
  "pp_regex_v8 3 bench/pyperformance/regex_v8.py 20"
  "pp_richards 3 bench/pyperformance/richards.py 20"
  "pp_go 3 bench/pyperformance/go.py 4"
  "pp_hexiom 3 bench/pyperformance/hexiom.py 100"
  "pp_json_loads 3 bench/pyperformance/json_loads.py 2000"
  "pp_json_dumps 3 bench/pyperformance/json_dumps.py 20"
  "pp_generators 3 bench/pyperformance/generators.py 10"
  "long_richards 5 bench/pyperformance/richards.py 200"
  "long_regex_effbot 5 bench/pyperformance/regex_effbot.py 200"
  "long_regex_v8 5 bench/pyperformance/regex_v8.py 100"
  "long_go 5 bench/pyperformance/go.py 40"
  "long_json_loads 5 bench/pyperformance/json_loads.py 10000"
  "long_chaos 5 bench/pyperformance/chaos.py 100"
  "long_raytrace 5 bench/pyperformance/raytrace.py 40"
  "long_scimark 5 bench/pyperformance/scimark.py 20"
  "long_nbody 5 bench/pyperformance/nbody.py 100"
  "long_generators 5 bench/pyperformance/generators.py 100"
  "long_fannkuch 5 bench/pyperformance/fannkuch.py 10"
  "long_json_dumps 5 bench/pyperformance/json_dumps.py 200"
  "long_spectral_norm 5 bench/pyperformance/spectral_norm.py 100"
  "long_float 5 bench/pyperformance/float.py 100"
  "long_hexiom 5 bench/pyperformance/hexiom.py 1000"
)
for w in "${workloads[@]}"; do
  read -r -a parts <<< "$w"
  name=${parts[0]}; rounds=${parts[1]}; program=("${parts[@]:2}")
  if [ $# -gt 0 ]; then
    case " $* " in *" $name "*) ;; *) continue ;; esac
  fi
  echo "== $name"
  JV_VARIANTS="calls=PYSTACHY_OPT=-jithelpers;helpers=" python3.13 "$M/jit_variants.py" "$rounds" "$out/$name.json" "$PYS" "${program[@]}" < /dev/null || echo "!! $name failed"
done
