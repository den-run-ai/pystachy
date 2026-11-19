#!/bin/bash
# kreport.sh DIR PASSES KERNEL...: run opt PASSES over DIR/KERNEL.yaml.in.bc with f.kernel kept out of
# line, then print f.kernel's vectorizer remarks and its innermost machine loops
SP=/tmp/claude-0/-home-user-pystachy/d93c2c20-f8ea-590f-9162-601d62fd95f8/scratchpad
dir=$1; passes=$2; shift 2
mkdir -p $dir/r
for k in "$@"; do
  /usr/lib/llvm-18/bin/opt -passes="$passes" -force-attribute=f.kernel:noinline $dir/$k.yaml.in.bc -o $dir/r/$k.bc \
    -pass-remarks-output=$dir/r/$k.yaml -pass-remarks-filter='loop-vectorize|loop-unroll' || { echo "$k: opt failed"; continue; }
  /usr/lib/llvm-18/bin/llc -O2 -filetype=obj $dir/r/$k.bc -o $dir/r/$k.o
  echo "=== $k"
  python3 $SP/simd/remarks.py $dir/r/$k.yaml | grep "f.kernel" | grep -v "MissedDetails" | sed 's/^  //' | cut -c1-170
  python3 $SP/simd/loops_asm.py $dir/r/$k.o f.kernel 2>&1 | grep -v "^f.kernel:" | head -12
done
