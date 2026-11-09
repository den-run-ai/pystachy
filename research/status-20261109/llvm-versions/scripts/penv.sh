#!/bin/bash
# usage: penv.sh N CMD...   run CMD with inherited PYSTACHY_* stripped, LLVM N (Nw: N behind the
# coro.end void-rewriting test wrapper; Nv: legacy two-argument void form; Nu: legacy two-argument
# unnamed i1 form) and a private cache for N
D=/tmp/claude-0/-home-user-pystachy/b0f95023-79a1-5e08-b42b-506118072379/scratchpad/llvmver.NWwbC2
N=$1; shift
for v in $(env | grep -o '^PYSTACHY_[A-Z_0-9]*'); do unset "$v"; done
case $N in
  *w) export PYSTACHY_LLVM=$D/corowrap-${N%w}/bin ;;
  *v) export PYSTACHY_LLVM=$D/corowrap2-${N%v}/bin ;;
  *u) export PYSTACHY_LLVM=$D/corowrap3-${N%u}/bin ;;
  *) export PYSTACHY_LLVM=/usr/lib/llvm-$N/bin ;;
esac
export PYSTACHY_CACHE=$D/cache-$N
exec "$@"
