#!/bin/sh
# JIT `run` cost with the program cache off vs on (each case a first-time miss, as in CI, but with the
# cache directory and its memoized toolchain hashes kept across cases, as within one CI job).
S=/tmp/claude-0/-home-user-pystachy/b0f95023-79a1-5e08-b42b-506118072379/scratchpad/ci-time
NEW=/home/user/wt/ci-time
for v in $(env | sed -n 's/^\(PYSTACHY_[A-Z_]*\)=.*/\1/p'); do unset "$v"; done
export PYSTACHY_LLVM=/usr/lib/llvm-18/bin PYSTACHY_JOBS=2
T=$(mktemp -d "$S/miss.XXXXXX")
now() { date +%s.%N; }
timed() { i=$1; shift; s=$(now); (cd "$NEW" && "$@") < "$i" > /dev/null 2> "$T/err"; st=$?; e=$(now); echo "$(echo "$e - $s" | bc | sed 's/^\./0./') $st"; }
rm -rf "$NEW/build/program-v2"
echo "warm-miss	$(timed /dev/null "$NEW/pystachy" run tests/programs/strings/bom.py)"
echo "warm-hit	$(timed /dev/null "$NEW/pystachy" run tests/programs/strings/bom.py)"
echo "other-miss	$(timed /dev/null "$NEW/pystachy" run tests/programs/strings/bytes_codecs.py)"
head -n "${1:-46}" "$S/sample_cases.txt" | while read -r c; do
  [ -n "$c" ] || continue
  in=/dev/null; [ -f "$NEW/${c%.py}.in" ] && in=$NEW/${c%.py}.in
  p=""; [ -f "$NEW/${c%.py}.path" ] && p=$(cat "$NEW/${c%.py}.path")
  x=$(timed "$in" env PYSTACHY_PATH="$p" PYSTACHY_PROGRAM_CACHE=0 "$NEW/pystachy" run "$c")
  y=$(timed "$in" env PYSTACHY_PATH="$p" "$NEW/pystachy" run "$c")
  z=$(timed "$in" env PYSTACHY_PATH="$p" "$NEW/pystachy" run "$c")
  printf '%s\t%s\t%s\t%s\n' "$c" "$x" "$y" "$z"
done
rm -rf "$T" "$NEW/build/program-v2"
