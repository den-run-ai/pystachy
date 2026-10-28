#!/bin/sh
# The corpus cases of shard I of N, one a line, heaviest first: tests/corpus.sh's corpus_shard, as
# tests/verify.sh's shard_cases selects them, so that on every runner the N shards are disjoint and
# together are the whole corpus (rejection and syntax checks included), balanced by the weights of
# tests/case_weights.txt. tools/coverage.sh, tools/runtime_coverage.sh and tools/variants.sh run their
# shards' cases (COVERAGE_SHARD and the like).
# usage: tools/shard_cases.sh I/N   (fails with status 2 unless 0 <= I < N)
cd "$(dirname "$0")/.." || exit 1
. tests/corpus.sh
case ${1:-} in
  [0-9]*/[0-9]*) i=${1%/*}; n=${1#*/} ;;
  *) i=x; n= ;;
esac
case $i$n in *[!0-9]*) echo "tools/shard_cases.sh: '${1:-}' is not I/N" >&2; exit 2 ;; esac
[ "$n" -gt 0 ] && [ "$i" -lt "$n" ] || { echo "tools/shard_cases.sh: no shard $i of $n" >&2; exit 2; }
corpus_shard "$i" "$n"
