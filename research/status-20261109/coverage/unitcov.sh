#!/bin/sh
# usage: unitcov.sh OUTDIR PATTERN...   runs each unittest pattern under coverage.py with the repo's .coveragerc
set -u
out=$1; shift
R=/home/user/wt/coverage-gaps
PY=/home/user/wt/devenv/bin/python3
rm -rf "$out" && mkdir -p "$out/data" || exit 1
cd "$R" || exit 1
for v in $(env | sed -n 's/^\(PYSTACHY_[A-Z_]*\)=.*/\1/p'); do unset "$v"; done
export PYSTACHY_LLVM=/usr/lib/llvm-18/bin
export COVERAGE_RCFILE=$R/.coveragerc
export PYSTACHY_CACHE=$out/cache
for p in "$@"; do
  t0=$(date +%s)
  COVERAGE_FILE=$out/data/data.unit $PY -m coverage run --context=unit -m unittest discover -s tools -p "$p" > "$out/$p.log" 2>&1
  st=$?
  echo "$p: status $st, $(($(date +%s) - t0)) s: $(grep -E '^(Ran|OK|FAILED)' "$out/$p.log" | tr '\n' ' ')"
done
ls "$out/data" | wc -l
COVERAGE_FILE=$out/data.combined $PY -m coverage combine -q "$out/data" && COVERAGE_FILE=$out/data.combined $PY -m coverage json -q -o "$out/coverage.json" && echo combined
