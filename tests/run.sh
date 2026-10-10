#!/bin/sh
# Differential tests. Every tests/*.py must print exactly what CPython printed
# (stdout + exit code, recorded in tests/*.out) both JIT-run and AOT-compiled; where
# CPython wrote to stderr, the last line (tests/*.err) must match too. Stdin comes from
# tests/*.in; where tests/NAME.full exists, stdout is /dev/full (writing it fails); where
# tests/NAME.path exists, it is PYSTACHY_PATH (as PYTHONPATH was for tests/record.sh).
# PYSTACHY_GC_STRESS_PROGRAM=N makes the programs collect every N allocations (JIT and AOT), whatever
# PYSTACHY_GC_STRESS gives the compiler that builds them.
# Every tests/errors/*.py must be rejected with the message in its first line (rtmode_*.py as
# "pystachy rt" compiles runtime.py), and every
# tests/deviations/*.py must print its hand-written .out (documented deviations from CPython).
# "pystachy check", which only parses, must accept tests/syntax_*.py and report the error of a
# tests/errors/syntax_*.py whose error is in its own file.
# The compiler checks the IR it builds (PYSTACHY_IRCHECK=1, unless set otherwise).
# The cases run in PYSTACHY_JOBS workers at once (default: one per CPU), each taking the next case
# no other worker has claimed (mkdir is atomic); the report lists them in the same order whatever
# the number of workers. Worker 0 runs in this shell and is the only one to take the cases about
# SIGINT: the other workers are asynchronous jobs, which start with SIGINT ignored.
# usage: tests/run.sh [COMPILER [MODES [FILE...]]]   (default: ./pystachy "jit aot" and every case;
#        e.g. "python3 pystachy.py", or tests/run.sh ./pystachy jit tests/str_*.py tests/errors/x.py;
#        FILEs are relative to the repository root)
cd "$(dirname "$0")/.." || exit 1
PYS=${1:-./pystachy}
MODES=${2:-jit aot}
if [ $# -gt 2 ]; then shift 2; else set --; fi
nsel=$#
for f; do
  f=${f#./}
  case $f in tests/*.py) [ -f "$f" ] ;; *) false ;; esac || { echo "tests/run.sh: not a test: $f" >&2; exit 2; }
  set -- "$@" "$f"
done
shift $nsel
[ $nsel != 0 ] || for f in tests/*.py tests/deviations/*.py tests/errors/*.py; do [ -f "$f" ] && set -- "$@" "$f"; done
[ $# != 0 ] || { echo "tests/run.sh: no test cases" >&2; exit 2; }
export PYSTACHY_IRCHECK="${PYSTACHY_IRCHECK:-1}"
JOBS=${PYSTACHY_JOBS:-$( (nproc || getconf _NPROCESSORS_ONLN) 2> /dev/null)}
case $JOBS in '' | *[!0-9]* | 0) JOBS=1 ;; esac
XENV=${PYSTACHY_GC_STRESS_PROGRAM:+env PYSTACHY_GC_STRESS=$PYSTACHY_GC_STRESS_PROGRAM}  # (an AOT program's)
T=${TMPDIR:-/tmp}/pystachy-tests.$$
rm -rf "$T"; mkdir "$T" || exit 1
pids=
trap 'rm -rf "$T"' EXIT
# Ctrl-C or TERM: name the cases that were running (on fd 4, this script's stdout), stop the workers
trap 'for f in "$T"/now.*; do [ -f "$f" ] && echo "INTERRUPTED while running $(cat "$f")" >&4; done; kill $pids 2> /dev/null; exit 130' INT TERM
exec 3> /dev/full 4>&1
# the cases about SIGINT, found once (one grep, not one per case and worker)
SIG=" $(grep -lE 'kill -INT|KeyboardInterrupt' "$@" | while read -r f; do printf '%s ' "$f"; done)"

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
        ($XENV "$T/$n.exe" a1 a2 < "$in" >&$o; echo "[exit $?]") > "$T/$n.$mode" 2>> "$T/$n.err"
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
      { $PYS build "$1" -o "$T/dev.$n.exe" 2>&1 && $XENV "$T/dev.$n.exe" a1 a2 < /dev/null 2>&1; echo "[exit $?]"; } > "$T/dev.$n.$mode"
    fi
    if cmp -s "$T/dev.$n.$mode" "$exp"; then pass=$((pass + 1)); else
      fail=$((fail + 1)); echo "FAIL deviations/$n ($mode)"; diff "$exp" "$T/dev.$n.$mode" | head -10; fi
  done
}
rejection() { # tests/errors/NAME.py
  n=$(basename "$1" .py)
  want=$(head -1 "$1" | sed 's/^# error: //')
  how=ir
  case $n in rtmode_*) how=rt ;; esac  # compiled as runtime.py is
  if $PYS $how "$1" > /dev/null 2> "$T/rej.$n" || ! grep -qF "$want" "$T/rej.$n"; then
    fail=$((fail + 1)); echo "FAIL $1: expected error '$want', got: $(cat "$T/rej.$n")"
  else pass=$((pass + 1)); fi
  case $n:$want in
    syntax_*:"$n.py:"*)
      if $PYS check "$1" > /dev/null 2> "$T/chk.$n" || ! grep -qF "$want" "$T/chk.$n"; then
        fail=$((fail + 1)); echo "FAIL $1 (check): expected error '$want', got: $(cat "$T/chk.$n")"
      else pass=$((pass + 1)); fi ;;
  esac
}
# worker K CASE...: each case no worker has claimed yet (claiming creates $T/c.I), the cases about
# SIGINT only if K is 0; case I's report goes to $T/I.log and its counts to $T/I.n
worker() {
  k=$1; shift; i=0
  for t; do
    if [ ! -d "$T/c.$i" ]; then
      case $SIG in *" $t "*) [ "$k" = 0 ] ;; *) true ;; esac && mkdir "$T/c.$i" 2> /dev/null && {
        pass=0; fail=0; echo "$t" > "$T/now.$k"
        {
          case $t in
            tests/deviations/*) deviation "$t" ;;
            tests/errors/*) rejection "$t" ;;
            *) program "$t" ;;
          esac
        } > "$T/$i.log" 2>&1
        echo "$pass $fail" > "$T/$i.n"
      }
    fi
    i=$((i + 1))
  done
  rm -f "$T/now.$k"
}
# the cached runtime is built once, before the workers start (each would rebuild a stale one)
echo pass > "$T/warm.py" && $PYS run "$T/warm.py" > /dev/null 2>&1
k=1
while [ $k -lt "$JOBS" ]; do
  worker $k "$@" &
  pids="$pids $!"; k=$((k + 1))
done
worker 0 "$@"
wait
pass=0; fail=0; i=0
for t; do
  if [ -f "$T/$i.n" ]; then
    cat "$T/$i.log"
    read -r p f < "$T/$i.n"
    pass=$((pass + p)); fail=$((fail + f))
  else
    fail=$((fail + 1)); echo "FAIL $t: no result (its worker died)"
  fi
  i=$((i + 1))
done
[ $nsel = 0 ] || echo "selected $# cases"
echo "$pass passed, $fail failed"
[ $fail = 0 ]
