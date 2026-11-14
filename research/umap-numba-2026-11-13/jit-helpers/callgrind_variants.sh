#!/bin/bash
# Instructions executed (callgrind's Ir: deterministic, unlike times on a shared host) by the program
# cache's executable of a program, built from the JIT pipeline's module, with calls of the runtime's
# small functions (PYSTACHY_OPT=-jithelpers) and with their copies inlined (the default, #705).
# usage: callgrind_variants.sh CHECKOUT OUT.tsv NAME PROGRAM [ARGS...]   (run from anywhere)
set -u
root=$1; out=$2; name=$3; shift 3
cd "$root" || exit 1
python3.13 "$@" > "${out}.cpython" 2> /dev/null < /dev/null || { echo "$name: CPython failed"; exit 1; }
for variant in calls helpers; do
  opt=""
  [ "$variant" = calls ] && opt=-jithelpers
  cache=$(mktemp -d "${TMPDIR:-/tmp}/cg-cache.XXXXXX")
  cp -p build/runtime-py-* "$cache"/ 2> /dev/null
  # a miss: the entry's executable is built from the module the JIT tier would run
  PYSTACHY_CACHE="$cache" PYSTACHY_OPT=$opt ./pystachy run "$@" > "$cache/out.miss" 2> "$cache/err.miss" < /dev/null || { echo "$name $variant: miss failed"; exit 1; }
  exe=$(find "$cache" -path '*program-v2*' -type f -name '*.exe' | head -1)
  [ -n "$exe" ] || { echo "$name $variant: no executable in the cache"; find "$cache" -path '*program-v2*' | head; exit 1; }
  ir=$(valgrind --tool=callgrind --callgrind-out-file="$cache/cg.out" "$exe" "${@:2}" 2>&1 > "$cache/out.cg" < /dev/null | sed -n 's/.*Collected : \([0-9]*\).*/\1/p')
  cmp -s "$cache/out.miss" "${out}.cpython" || { echo "$name $variant: the JIT's output differs from CPython's"; exit 1; }
  cmp -s "$cache/out.cg" "${out}.cpython" || { echo "$name $variant: the cached executable's output differs from CPython's"; exit 1; }
  printf '%s\t%s\t%s\n' "$name" "$variant" "$ir" | tee -a "$out"
  rm -rf "$cache"
done
