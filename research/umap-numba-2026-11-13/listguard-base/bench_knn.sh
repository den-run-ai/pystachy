#!/bin/bash
# Interleaved, CPU-pinned exact-kNN stage times: Pystachy probe builds (knn= stage) and Numba (warm call).
# usage: bench_knn.sh ROUNDS OUT.tsv VARIANT...   (VARIANT: a probe binary in build/, or numba:strict / numba:fastmath)
set -u
P=/tmp/claude-0/-home-user-pystachy/d93c2c20-f8ea-590f-9162-601d62fd95f8/scratchpad/probe
V=/tmp/claude-0/-home-user-pystachy/d93c2c20-f8ea-590f-9162-601d62fd95f8/scratchpad/venv-umap/bin/python
rounds=$1; out=$2; shift 2
cd $P/build
: > "$out"
for r in $(seq 1 "$rounds"); do
  n=$#; k=$(( (r - 1) % n )); vs=("$@"); order=("${vs[@]:k}" "${vs[@]:0:k}")
  for v in "${order[@]}"; do
    case "$v" in
      numba:*)
        t=$(NUMBA_NUM_THREADS=1 NUMBA_CACHE_DIR=$P/build/numba-cache taskset -c 1 "$V" -I -W ignore $P/numba_knn.py export.txt "${v#numba:}" \
            | "$V" -c 'import json,sys; print(json.load(sys.stdin)["warm_s"])') ;;
      *)
        t=$(taskset -c 1 ./"$v" 10000 16 10 15 200 7 2>&1 >/dev/null | sed -n 's/.*knn=\([0-9.]*\).*/\1/p') ;;
    esac
    printf '%s\t%s\t%s\n' "$r" "$v" "$t" >> "$out"
  done
done
"$V" - "$out" <<'PY'
import statistics, sys
rows = [l.split("\t") for l in open(sys.argv[1]).read().split("\n") if l]
by = {}
for _, v, t in rows:
    by.setdefault(v, []).append(float(t))
for v, ts in by.items():
    print(f"{v:24s} median {statistics.median(ts):.3f}s  min {min(ts):.3f}s  max {max(ts):.3f}s  n={len(ts)}")
PY
