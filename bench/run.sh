#!/bin/sh
# Compare CPython vs Pystachy JIT (lli) vs Pystachy AOT (clang) on each benchmark; outputs must match.
# usage: bench/run.sh   (make bench)   env: PY (default python3), PYS (default ./pystachy)
cd "$(dirname "$0")/.." || exit 1
PY=${PY:-python3}
PYS=${PYS:-./pystachy}
T=$(mktemp -d "${TMPDIR:-/tmp}/pystachy-bench.XXXXXX") || exit 1
trap 'rm -rf "$T"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
now() { date +%s.%N; }
# t CMD...: run CMD with its output in $T/out, print the seconds it took
t() { s=$(now); "$@" > "$T/out" 2>&1; awk -v a="$s" -v b="$(now)" 'BEGIN { printf "%.3f", b - a }'; }
# (the runtime cache first: after a rebuild of the compiler, the first run rebuilds it, which the
# first JIT time would count)
echo pass > "$T/warm.py" && $PYS run "$T/warm.py" > /dev/null 2>&1
printf "%-10s %10s %10s %10s %9s\n" bench cpython jit aot speedup
for b in bench/*.py; do
  n=$(basename "$b" .py)
  cp=$(t $PY "$b"); mv "$T/out" "$T/ref"
  jit=$(t $PYS run "$b"); cmp -s "$T/out" "$T/ref" || echo "  $n: JIT output differs"
  $PYS build "$b" -o "$T/exe"
  aot=$(t "$T/exe"); cmp -s "$T/out" "$T/ref" || echo "  $n: AOT output differs"
  printf "%-10s %9.2fs %9.2fs %9.2fs %8.0fx\n" "$n" "$cp" "$jit" "$aot" "$(awk -v a="$cp" -v b="$aot" 'BEGIN { print (b > 0 ? a / b : 0) }')"
done
