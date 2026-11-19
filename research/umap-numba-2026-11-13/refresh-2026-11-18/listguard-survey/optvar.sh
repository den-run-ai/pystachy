#!/bin/bash
# optvar.sh MODULE NAME EXTRA: time opt over MODULE (a captured JIT input) with the cleanup and EXTRA after it, 3 runs, min
SP=/tmp/claude-0/-home-user-pystachy/d93c2c20-f8ea-590f-9162-601d62fd95f8/scratchpad
m=$1; name=$2; extra=$3
base="globaldce,always-inline,function(mem2reg,instcombine<no-verify-fixpoint>,simplifycfg),function(early-cse,adce),forceattrs,forceattrs,always-inline"
p="$base"; [ -n "$extra" ] && p="$base,$extra"
best=99
for r in 1 2 3; do
  s=$(date +%s.%N)
  taskset -c 1 /usr/lib/llvm-18/bin/opt -passes="$p" -force-remove-attribute=pys_new:noinline -force-attribute=pys_new:alwaysinline -force-remove-attribute=pys_alloc:noinline -force-attribute=pys_alloc:alwaysinline $m -o /dev/null || exit 1
  e=$(date +%s.%N)
  t=$(echo "$e - $s" | bc)
  best=$(echo "if ($t < $best) $t else $best" | bc)
done
echo "$(basename $m .in.ll) $name $best"
