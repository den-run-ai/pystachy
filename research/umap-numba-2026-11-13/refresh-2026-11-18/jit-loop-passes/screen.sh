#!/bin/bash
# screen.sh NAME EXTRA-PASSES : one probe run with EXTRA spliced into the JIT cleanup
SP=/tmp/claude-0/-home-user-pystachy/d93c2c20-f8ea-590f-9162-601d62fd95f8/scratchpad
name=$1; extra=$2; shift 2
env -u PYSTACHY_OPT -u PYSTACHY_HOME PYSTACHY_LLVM=$SP/passx/llvm PYSTACHY_PROGRAM_CACHE=0 PYSTACHY_TIMING=1 EXTRA="$extra" "$@" \
  taskset -c 1 $SP/stack-now/pystachy run $SP/probe/umap_core.py 10000 16 10 15 200 7 > $SP/passx/$name.out 2> $SP/passx/$name.err
code=$?
cmp -s $SP/passx/$name.out $SP/probe/build/rt10k.out && same=same || same=DIFFERS
opt=$(awk -F'\t' '$2=="program.jit_optimize"{print $3}' $SP/passx/$name.err)
t=$(grep -o "knn=[0-9.]* graph=[0-9.]* layout=[0-9.]*" $SP/passx/$name.err)
echo "$name exit=$code $same opt=$opt $t"
