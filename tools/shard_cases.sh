#!/bin/sh
# The corpus cases of shard I of N, one a line: the files whose position in C order is I modulo N, as
# tests/verify.sh's shard_cases selects them, so that on every runner the N shards are disjoint and
# together are the whole corpus (rejection and syntax checks included). tools/coverage.sh,
# tools/runtime_coverage.sh and tools/variants.sh run their shards' cases (COVERAGE_SHARD and the like).
# usage: tools/shard_cases.sh I/N   (fails with status 2 unless 0 <= I < N)
cd "$(dirname "$0")/.." || exit 1
case ${1:-} in
  [0-9]*/[0-9]*) i=${1%/*}; n=${1#*/} ;;
  *) i=x; n= ;;
esac
case $i$n in *[!0-9]*) echo "tools/shard_cases.sh: '${1:-}' is not I/N" >&2; exit 2 ;; esac
[ "$n" -gt 0 ] && [ "$i" -lt "$n" ] || { echo "tools/shard_cases.sh: no shard $i of $n" >&2; exit 2; }
export LC_ALL=C
k=0
for f in tests/*.py tests/deviations/*.py tests/errors/*.py; do
  [ -f "$f" ] || continue
  [ $((k % n)) != "$i" ] || printf '%s\n' "$f"
  k=$((k + 1))
done
