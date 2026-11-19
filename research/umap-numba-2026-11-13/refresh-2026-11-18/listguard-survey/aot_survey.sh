#!/bin/bash
# aot_survey.sh TREE OUTDIR KERNEL...: AOT-build each kernel with TREE's compiler, saving LLVM's
# vectorizer/LICM/unroll remarks (OUTDIR/NAME.yaml) and the executable (OUTDIR/NAME)
SP=/tmp/claude-0/-home-user-pystachy/d93c2c20-f8ea-590f-9162-601d62fd95f8/scratchpad
tree=$1; out=$2; shift 2
mkdir -p $out
for k in "$@"; do
  rm -f $out/$k.yaml
  env -u PYSTACHY_HOME PYSTACHY_PROGRAM_CACHE=0 PYSTACHY_LLVM=$SP/simd/llvm REMARKS=$out/$k.yaml \
    $SP/$tree/pystachy build $SP/simd/k/$k.py -o $out/$k > $out/$k.build.log 2>&1 || echo "$k: build failed"
done
