#!/bin/sh
# Compare CPython vs Pystachy JIT (lli) vs Pystachy AOT (clang) on each benchmark; outputs must match.
cd "$(dirname "$0")/.." || exit 1
PYS=${PYS:-./pystachy}
t() { s=$(date +%s.%N); "$@" > /tmp/pystachy-bench.out 2>&1; e=$(date +%s.%N); echo "$e - $s" | bc; }
printf "%-10s %10s %10s %10s %9s\n" bench cpython jit aot speedup
for b in bench/*.py; do
  n=$(basename "$b" .py)
  cp=$(t python3 "$b"); cp /tmp/pystachy-bench.out /tmp/pystachy-bench.ref
  jit=$(t $PYS run "$b"); cmp -s /tmp/pystachy-bench.out /tmp/pystachy-bench.ref || echo "  $n: JIT output differs"
  $PYS build "$b" -o /tmp/pystachy-bench.exe
  aot=$(t /tmp/pystachy-bench.exe); cmp -s /tmp/pystachy-bench.out /tmp/pystachy-bench.ref || echo "  $n: AOT output differs"
  printf "%-10s %9.2fs %9.2fs %9.2fs %8.0fx\n" "$n" "$cp" "$jit" "$aot" "$(echo "$cp / $aot" | bc -l)"
done
