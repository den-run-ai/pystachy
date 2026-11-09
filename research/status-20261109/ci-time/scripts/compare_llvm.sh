#!/bin/sh
# Old (d93f853f) vs new (ce8c887) end-to-end per-case cost: JIT `run` and AOT `build`, each tree with
# its own lib/ and runtime cache. New JIT is measured with the program cache off and with a cold cache
# (CI's default: every case misses and stores). Output TSV: case, then seconds and exit status of
#   old-run old-build new-run(cache off) new-run(cold cache) new-build
S=/tmp/claude-0/-home-user-pystachy/b0f95023-79a1-5e08-b42b-506118072379/scratchpad/ci-time
OLD=$S/old
NEW=/home/user/wt/ci-time
for v in $(env | sed -n 's/^\(PYSTACHY_[A-Z_]*\)=.*/\1/p'); do unset "$v"; done
export PYSTACHY_LLVM=/usr/lib/llvm-18/bin PYSTACHY_JOBS=2
T=$(mktemp -d "$S/llvm.XXXXXX")
now() { date +%s.%N; }
# timed DIR INPUT COMMAND... : run in DIR with stdin INPUT, print "seconds status"
timed() { d=$1; i=$2; shift 2; s=$(now); (cd "$d" && "$@") < "$i" > /dev/null 2> "$T/err"; st=$?; e=$(now); echo "$(echo "$e - $s" | bc | sed 's/^\./0./') $st"; }
warm=tests/programs/strings/bom.py
timed "$OLD" /dev/null "$OLD/pystachy" run "$warm" > /dev/null
timed "$OLD" /dev/null "$OLD/pystachy" build "$warm" -o "$T/w" > /dev/null
timed "$NEW" /dev/null env PYSTACHY_PROGRAM_CACHE=0 "$NEW/pystachy" run "$warm" > /dev/null
timed "$NEW" /dev/null "$NEW/pystachy" build "$warm" -o "$T/w" > /dev/null
timed "$NEW" /dev/null "$NEW/pystachy" run "$warm" > /dev/null
head -n "${1:-24}" "$S/sample_cases.txt" | while read -r c; do
  [ -n "$c" ] || continue
  in=/dev/null; [ -f "$OLD/${c%.py}.in" ] && in=$OLD/${c%.py}.in
  p=""; [ -f "$OLD/${c%.py}.path" ] && p=$(cat "$OLD/${c%.py}.path")
  a=$(timed "$OLD" "$in" env PYSTACHY_PATH="$p" "$OLD/pystachy" run "$c")
  b=$(timed "$OLD" "$in" env PYSTACHY_PATH="$p" "$OLD/pystachy" build "$c" -o "$T/old-prog")
  in=/dev/null; [ -f "$NEW/${c%.py}.in" ] && in=$NEW/${c%.py}.in
  p=""; [ -f "$NEW/${c%.py}.path" ] && p=$(cat "$NEW/${c%.py}.path")
  x=$(timed "$NEW" "$in" env PYSTACHY_PATH="$p" PYSTACHY_PROGRAM_CACHE=0 "$NEW/pystachy" run "$c")
  rm -rf "$NEW/build/program-v2"
  y=$(timed "$NEW" "$in" env PYSTACHY_PATH="$p" "$NEW/pystachy" run "$c")
  z=$(timed "$NEW" "$in" env PYSTACHY_PATH="$p" "$NEW/pystachy" build "$c" -o "$T/new-prog")
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$c" "$a" "$b" "$x" "$y" "$z"
done
rm -rf "$T" "$NEW/build/program-v2"
