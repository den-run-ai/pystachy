#!/bin/sh
# IR validity: every program of the tools/irsame.sh corpus, tests/errors/*.py aside (they must not
# compile), must compile and pass the compiler's own check of the IR it builds (PYSTACHY_IRCHECK=1,
# unless set otherwise), and llvm-as must accept its `ir` output; llvm-as is run from PYSTACHY_LLVM if
# set, as the driver runs it. A program the compiler rejects is a failure too, since tests/run.sh never
# compiles the tests/ir probes; so is an internal error (such as the IR check's), or an IR that llvm-as
# rejects: each failure is listed with the first lines of its message. A tests/ir/NAME.py with a
# NAME.fx is compiled with PYSTACHY_IRFX=1, which prints each function's effect summary: they must be
# the ones NAME.fx lists. One with a NAME.calls must call the runtime functions it lists: for each
# function its IR defines, the pys_ functions it calls, in the order of its text. Both are compiled
# with every optimization on (an empty PYSTACHY_OPT), whose rewrites they pin. The programs run from
# the repository root in PYSTACHY_JOBS workers (default: one per CPU). Exit status 0 only if every
# program compiled and passed its checks.
# usage: tools/check_ir.sh [COMPILER [FILE...]]   (default: ./pystachy and the corpus; make check-ir,
#        or make check-ir FILES=tests/ir/pending/NAME.py for a probe outside the corpus)
cd "$(dirname "$0")/.." || exit 1
PYS=${1:-./pystachy}
[ $# = 0 ] || shift
for f; do [ -f "$f" ] || { echo "tools/check_ir.sh: no such program: $f" >&2; exit 2; }; done
if [ $# = 0 ]; then
  for f in pystachy.py tests/*.py tests/deviations/*.py bench/*.py tests/ir/*.py; do
    [ -f "$f" ] && set -- "$@" "$f"
  done
fi
LLVM=${PYSTACHY_LLVM:+${PYSTACHY_LLVM%/}/}
export PYSTACHY_IRCHECK="${PYSTACHY_IRCHECK:-1}"
JOBS=${PYSTACHY_JOBS:-$( (nproc || getconf _NPROCESSORS_ONLN) 2> /dev/null)}
case $JOBS in '' | *[!0-9]* | 0) JOBS=1 ;; esac
T=${TMPDIR:-/tmp}/pystachy-checkir.$$
rm -rf "$T"; mkdir -p "$T" || exit 1
trap 'rm -rf "$T"' EXIT
trap 'exit 130' INT TERM

# calls IR: each function IR defines, and the runtime functions (pys_*) it calls in the order of its text
calls() {
  awk '/^define / { f = $0; sub(/\(.*/, "", f); sub(/.* /, "", f); c = "" }
    /^  .*call [^@]*@pys_/ { s = $0; sub(/^.*call [^@]*@/, "", s); sub(/\(.*/, "", s); c = c " " s }
    /^}/ && f != "" { print f ":" c; f = "" }' "$1"
}
# check FILE DIR: DIR/result is ok, skip (does not compile), internal (an internal error, such as the
# IR check's), fx (other effect summaries than FILE's .fx lists), calls (other runtime calls than its
# .calls lists) or bad (llvm-as rejects the IR); DIR/msg says why
check() {
  mp=$PYSTACHY_PATH; [ -f "${1%.py}.path" ] && mp=$(cat "${1%.py}.path")  # (as tests/run.sh)
  fx=; [ -f "${1%.py}.fx" ] && fx=1
  opt=$PYSTACHY_OPT; [ -n "$fx" ] || [ -f "${1%.py}.calls" ] && opt=
  if ! PYSTACHY_PATH=$mp PYSTACHY_IRFX=$fx PYSTACHY_OPT=$opt $PYS ir "$1" -o "$2/ir.ll" > "$2/msg" 2>&1; then
    if grep -q 'error: internal error' "$2/msg"; then r=internal; else r=skip; fi
  elif [ -n "$fx" ] && ! diff "${1%.py}.fx" "$2/msg" > "$2/fx" 2>&1; then r=fx; mv "$2/fx" "$2/msg"
  elif [ -f "${1%.py}.calls" ] && ! calls "$2/ir.ll" | diff "${1%.py}.calls" - > "$2/calls" 2>&1; then r=calls; mv "$2/calls" "$2/msg"
  elif "${LLVM}llvm-as" -o /dev/null < "$2/ir.ll" > "$2/msg" 2>&1; then r=ok
  else r=bad; fi
  rm -f "$2/ir.ll"
  echo $r > "$2/result"
}
# a worker: each program whose directory it is the first to create (mkdir is atomic)
worker() {
  i=0
  for f; do
    i=$((i + 1))
    if mkdir "$T/$i" 2> /dev/null; then check "$f" "$T/$i"; fi
  done
}
k=1
while [ $k -lt "$JOBS" ]; do
  worker "$@" &
  k=$((k + 1))
done
worker "$@"
wait
n=0; bad=0; skip=0
for f; do
  n=$((n + 1)); r=""; [ -f "$T/$n/result" ] && read -r r < "$T/$n/result"
  case $r in
    ok) ;;
    skip) skip=$((skip + 1)); echo "FAIL $f: does not compile"; head -3 "$T/$n/msg" ;;
    internal) bad=$((bad + 1)); echo "INTERNAL ERROR $f"; head -5 "$T/$n/msg" ;;
    fx) bad=$((bad + 1)); echo "OTHER EFFECTS $f (than ${f%.py}.fx lists)"; head -10 "$T/$n/msg" ;;
    calls) bad=$((bad + 1)); echo "OTHER CALLS $f (than ${f%.py}.calls lists)"; head -10 "$T/$n/msg" ;;
    bad) bad=$((bad + 1)); echo "REJECTED $f (by llvm-as)"; head -5 "$T/$n/msg" ;;
    *) bad=$((bad + 1)); echo "FAIL $f: no result (its worker died)" ;;
  esac
done
if [ $((bad + skip)) = 0 ]; then echo "the IR check and llvm-as accept the IR of $n programs"
else echo "$((bad + skip)) of $n programs fail: $skip do not compile, the checks reject $bad"; fi
[ $((bad + skip)) = 0 ]
