#!/bin/sh
# Build the d93f853f snapshot's compiler with the old Makefile's stages, timing each one.
set -e
cd /tmp/claude-0/-home-user-pystachy/b0f95023-79a1-5e08-b42b-506118072379/scratchpad/ci-time/old
for v in $(env | sed -n 's/^\(PYSTACHY_[A-Z_]*\)=.*/\1/p'); do unset "$v"; done
export PYSTACHY_LLVM=/usr/lib/llvm-18/bin PYSTACHY_JOBS=2
PY=python3.13
mkdir -p build
t() { s=$(date +%s.%N); "$@"; e=$(date +%s.%N); echo "TIME $(echo "$e - $s" | bc) $*" >&2; }
t $PY pystachy.py build pystachy.py -o build/pystachy1
t build/pystachy1 build pystachy.py -o build/pystachy2
t build/pystachy2 ir pystachy.py -o build/stage3.ll
t build/pystachy1 ir pystachy.py -o build/stage2.ll
cmp build/stage2.ll build/stage3.ll && echo "fixed point stage2 == stage3 ($(wc -l < build/stage3.ll) lines)"
t build/pystachy2 rt runtime.py -o build/rt3.ll
cp build/pystachy2 pystachy
echo done
