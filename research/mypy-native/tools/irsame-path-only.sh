#!/bin/sh
# two.sh FILE OUTDIR: of FILE's IR difference between the two compilers, the lines that differ but
# for the reference compiler's library path (build/ref/lib/): prints "PATHONLY FILE" or "REAL n FILE"
f=$1; d=$(mktemp -d "$2/w.XXXXXX") || exit 1
mp=$PYSTACHY_PATH
if [ -f "${f%.py}.path" ]; then mp=$(sh tests/prepare_path.sh "$f" "$d") || { echo "PATHFAIL $f"; exit 0; }; fi
how=ir
case $f in runtime.py | */rtmode_*.py) how=rt ;; esac
PYSTACHY_HOME= PYSTACHY_PATH=$mp build/ref/pystachy $how "$f" -o "$d/old.ll" > /dev/null 2>&1
PYSTACHY_HOME= PYSTACHY_PATH=$mp ./pystachy $how "$f" -o "$d/new.ll" > /dev/null 2>&1
n=$(diff "$d/old.ll" "$d/new.ll" | grep '^[<>]' | grep -vc '/lib/[A-Za-z0-9_/]*\.py')
if [ "$n" = 0 ]; then echo "PATHONLY $f"; else echo "REAL $n $f"; fi
rm -rf "$d"
