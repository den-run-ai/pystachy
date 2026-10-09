#!/bin/sh
# Differential tests. Every tests/*.py must print exactly what CPython printed
# (stdout + exit code, recorded in tests/*.out) both JIT-run and AOT-compiled; where
# CPython wrote to stderr, the last line (tests/*.err) must match too. Stdin comes from
# tests/*.in; where tests/NAME.full exists, stdout is /dev/full (writing it fails); where
# tests/NAME.path exists, it is PYSTACHY_PATH (as PYTHONPATH was for tests/record.sh).
# Every tests/errors/*.py must be rejected with the message in its first line, and every
# tests/deviations/*.py must print its hand-written .out (documented deviations from CPython).
# "pystachy check", which only parses, must accept tests/syntax_*.py and report the error of a
# tests/errors/syntax_*.py whose error is in its own file.
# The cases run in PYSTACHY_JOBS workers at once (default: one per CPU); the report lists them
# in the same order whatever the number of workers. Worker 0 runs in this shell and takes the
# cases about SIGINT: the other workers are asynchronous jobs, which start with SIGINT ignored.
# usage: tests/run.sh [COMPILER [MODES]]   (default: ./pystachy "jit aot"; e.g. "python3 pystachy.py")
cd "$(dirname "$0")/.." || exit 1
PYS=${1:-./pystachy}
MODES=${2:-jit aot}
JOBS=${PYSTACHY_JOBS:-$( (nproc || getconf _NPROCESSORS_ONLN) 2> /dev/null)}
case $JOBS in '' | *[!0-9]* | 0) JOBS=1 ;; esac
T=${TMPDIR:-/tmp}/pystachy-tests.$$
mkdir -p "$T"
exec 3> /dev/full

# Each case adds to $pass and $fail and prints what the report shows for it.
program() { # tests/NAME.py
  n=$(basename "$1" .py); in=/dev/null; [ -f "tests/$n.in" ] && in="tests/$n.in"
  o=1; [ -f "tests/$n.full" ] && o=3
  mp=$PYSTACHY_PATH; [ -f "tests/$n.path" ] && mp=$(cat "tests/$n.path")
  for mode in $MODES; do
    if [ $mode = jit ]; then
      (PYSTACHY_PATH=$mp $PYS run "$1" a1 a2 < "$in" >&$o; echo "[exit $?]") > "$T/$n.$mode" 2> "$T/$n.err"
    else
      PYSTACHY_PATH=$mp $PYS build "$1" -o "$T/$n.exe" 2> "$T/$n.err" &&
        ("$T/$n.exe" a1 a2 < "$in" >&$o; echo "[exit $?]") > "$T/$n.$mode" 2>> "$T/$n.err"
    fi
    if cmp -s "$T/$n.$mode" "tests/$n.out" && { [ ! -f "tests/$n.err" ] || [ "$(tail -1 "$T/$n.err")" = "$(cat "tests/$n.err")" ]; }; then
      pass=$((pass + 1)); else
      fail=$((fail + 1)); echo "FAIL $n ($mode)"; diff "tests/$n.out" "$T/$n.$mode" | head -10
      [ -f "tests/$n.err" ] && echo "  stderr: want '$(cat "tests/$n.err")', got '$(tail -1 "$T/$n.err")'"; head -5 "$T/$n.err"; fi
  done
  case $n in
    syntax_*)
      if $PYS check "$1" > "$T/chk.$n" 2>&1 && [ ! -s "$T/chk.$n" ]; then pass=$((pass + 1)); else
        fail=$((fail + 1)); echo "FAIL $n (check)"; head -5 "$T/chk.$n"; fi ;;
  esac
}
# Documented deviations from CPython: tests/deviations/*.out is written by hand and holds
# stdout and stderr together (the runtime flushes stdout before reporting an error).
deviation() { # tests/deviations/NAME.py
  n=$(basename "$1" .py); exp="tests/deviations/$n.out"
  for mode in $MODES; do
    if [ $mode = jit ]; then
      ($PYS run "$1" a1 a2 < /dev/null 2>&1; echo "[exit $?]") > "$T/dev.$n.$mode"
    else
      { $PYS build "$1" -o "$T/dev.$n.exe" 2>&1 && "$T/dev.$n.exe" a1 a2 < /dev/null 2>&1; echo "[exit $?]"; } > "$T/dev.$n.$mode"
    fi
    if cmp -s "$T/dev.$n.$mode" "$exp"; then pass=$((pass + 1)); else
      fail=$((fail + 1)); echo "FAIL deviations/$n ($mode)"; diff "$exp" "$T/dev.$n.$mode" | head -10; fi
  done
}
rejection() { # tests/errors/NAME.py
  n=$(basename "$1" .py)
  want=$(head -1 "$1" | sed 's/^# error: //')
  if $PYS ir "$1" > /dev/null 2> "$T/rej.$n" || ! grep -qF "$want" "$T/rej.$n"; then
    fail=$((fail + 1)); echo "FAIL $1: expected error '$want', got: $(cat "$T/rej.$n")"
  else pass=$((pass + 1)); fi
  case $n:$want in
    syntax_*:"$n.py:"*)
      if $PYS check "$1" > /dev/null 2> "$T/chk.$n" || ! grep -qF "$want" "$T/chk.$n"; then
        fail=$((fail + 1)); echo "FAIL $1 (check): expected error '$want', got: $(cat "$T/chk.$n")"
      else pass=$((pass + 1)); fi ;;
  esac
}
# worker K: the cases whose position in the list is K modulo $JOBS, but worker 0 takes every
# case about SIGINT; case I's report goes to $T/I.log and its counts to $T/I.n
worker() {
  i=0
  for t in tests/*.py tests/deviations/*.py tests/errors/*.py; do
    if [ ! -f "$t" ]; then w=-1
    elif grep -qE 'kill -INT|KeyboardInterrupt' "$t"; then w=0
    else w=$((i % JOBS)); fi
    if [ $w = "$1" ]; then
      pass=0; fail=0
      {
        case $t in
          tests/deviations/*) deviation "$t" ;;
          tests/errors/*) rejection "$t" ;;
          *) program "$t" ;;
        esac
      } > "$T/$i.log" 2>&1
      echo "$pass $fail" > "$T/$i.n"
    fi
    i=$((i + 1))
  done
}
k=1
while [ $k -lt "$JOBS" ]; do
  worker $k &
  k=$((k + 1))
done
worker 0
wait
pass=0; fail=0; i=0
for t in tests/*.py tests/deviations/*.py tests/errors/*.py; do
  if [ -f "$t" ]; then
    if [ -f "$T/$i.n" ]; then
      cat "$T/$i.log"
      read -r p f < "$T/$i.n"
      pass=$((pass + p)); fail=$((fail + f))
    else
      fail=$((fail + 1)); echo "FAIL $t: no result (its worker died)"
    fi
  fi
  i=$((i + 1))
done
rm -rf "$T"
echo "$pass passed, $fail failed"
[ $fail = 0 ]
