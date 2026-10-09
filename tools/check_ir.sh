#!/bin/sh
# IR validity: the compiler's own check of the IR it builds (PYSTACHY_IRCHECK=1, unless set otherwise)
# and llvm-as must accept the `ir` output of every program of the tools/irsame.sh corpus that
# compiles, tests/errors/*.py aside (they must not compile); llvm-as is run from PYSTACHY_LLVM if set,
# as the driver runs it. A program the compiler rejects with an error of the program is listed and
# skipped; an internal error (such as the IR check's), or an IR that llvm-as rejects, is listed with
# the first lines of its message. The programs run from the repository root in PYSTACHY_JOBS workers
# (default: one per CPU). Exit status 0 only if every program that compiles passed both checks.
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

# check FILE DIR: DIR/result is ok, skip (does not compile), internal (an internal error, such as the
# IR check's) or bad (llvm-as rejects the IR); DIR/msg says why
check() {
  mp=$PYSTACHY_PATH; [ -f "${1%.py}.path" ] && mp=$(cat "${1%.py}.path")  # (as tests/run.sh)
  if ! PYSTACHY_PATH=$mp $PYS ir "$1" -o "$2/ir.ll" > "$2/msg" 2>&1; then
    if grep -q 'error: internal error' "$2/msg"; then r=internal; else r=skip; fi
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
    skip) skip=$((skip + 1)); echo "SKIP $f (does not compile): $(head -1 "$T/$n/msg")" ;;
    internal) bad=$((bad + 1)); echo "INTERNAL ERROR $f"; head -5 "$T/$n/msg" ;;
    bad) bad=$((bad + 1)); echo "REJECTED $f (by llvm-as)"; head -5 "$T/$n/msg" ;;
    *) bad=$((bad + 1)); echo "FAIL $f: no result (its worker died)" ;;
  esac
done
n=$((n - skip)); s=""; [ $skip = 0 ] || s=" ($skip more did not compile)"
if [ $bad = 0 ]; then echo "the IR check and llvm-as accept the IR of $n programs$s"; else echo "the IR of $bad of $n programs is rejected$s"; fi
[ $bad = 0 ]
