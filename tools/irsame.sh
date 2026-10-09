#!/bin/sh
# IR oracle for refactors of the code generator: compilers OLD and NEW run `ir` on every program
# of the corpus, from the repository root as tests/run.sh runs them, and must print the same LLVM
# IR byte for byte, the same messages (all of a tests/errors/*.py rejection) and the same exit status.
# The corpus is pystachy.py (first: it takes longest), runtime.py, tests/*.py, tests/deviations/*.py,
# bench/*.py, tests/ir/*.py and tests/errors/*.py, with PYSTACHY_PATH from NAME.path where it exists,
# as tests/run.sh runs them. When both compilers have runtime mode (`pystachy rt`), runtime.py and
# tests/errors/rtmode_*.py are compiled with `rt`, as the driver and tests/run.sh compile them
# (every program's executable holds runtime.py's code); otherwise with `ir`, as programs, which
# runtime.py is not, so it then fails alike with both. tests/ir/*.py probe code-generation paths the others never
# take: they are only compiled (here and by tools/check_ir.sh), never run. tests/ir/pending/ holds
# the probes of open compiler bugs, which are not part of the corpus until the fix moves them up.
# The programs run in PYSTACHY_JOBS workers (default: one per CPU), each taking the next program
# left. The first 3 that differ are shown with the start of each diff (the IR's from its first
# differing line, named by the function that holds it); the last line counts them all. Only sh and
# the tools tests/run.sh uses are needed (no python), as in the Python-free stage of tests/verify.sh.
# usage: tools/irsame.sh OLD NEW [FILE...]   (compiler commands, e.g. build/ref/pystachy ./pystachy
#        or "python3 pystachy.py"; make irsame REF=<commit> runs it against that commit's compiler)
cd "$(dirname "$0")/.." || exit 1
[ $# -ge 2 ] || { echo "usage: tools/irsame.sh OLD NEW [FILE...]" >&2; exit 2; }
OLD=$1; NEW=$2; shift 2
for f; do [ -f "$f" ] || { echo "tools/irsame.sh: no such program: $f" >&2; exit 2; }; done
RT=0  # (whether both have runtime mode: their usage names it)
{ $OLD 2>&1 | grep -q 'pystachy rt '; } && { $NEW 2>&1 | grep -q 'pystachy rt '; } && RT=1
if [ $# = 0 ]; then
  for f in pystachy.py runtime.py tests/*.py tests/deviations/*.py bench/*.py tests/ir/*.py tests/errors/*.py; do
    [ -f "$f" ] && set -- "$@" "$f"
  done
fi
JOBS=${PYSTACHY_JOBS:-$( (nproc || getconf _NPROCESSORS_ONLN) 2> /dev/null)}
case $JOBS in '' | *[!0-9]* | 0) JOBS=1 ;; esac
SHOW=3
T=${TMPDIR:-/tmp}/pystachy-irsame.$$
rm -rf "$T"; mkdir -p "$T" || exit 1
trap 'rm -rf "$T"' EXIT
trap 'exit 130' INT TERM

# same FILE DIR: compile FILE with both compilers in DIR; DIR/report says what differs (empty: nothing)
same() {
  mp=$PYSTACHY_PATH; [ -f "${1%.py}.path" ] && mp=$(cat "${1%.py}.path")  # (as tests/run.sh)
  how=ir
  case $RT:$1 in 1:runtime.py | 1:*/runtime.py | 1:*/rtmode_*.py) how=rt ;; esac
  PYSTACHY_PATH=$mp $OLD $how "$1" -o "$2/old.ll" > "$2/old.msg" 2>&1; a=$?
  PYSTACHY_PATH=$mp $NEW $how "$1" -o "$2/new.ll" > "$2/new.msg" 2>&1; b=$?
  {
    [ $a = $b ] || echo "  exit status $a -> $b"
    if ! cmp -s "$2/old.msg" "$2/new.msg"; then
      echo "  messages:"; diff -u "$2/old.msg" "$2/new.msg" | sed 1,2d | head -12
    fi
    if [ -f "$2/old.ll" ] && [ -f "$2/new.ll" ]; then
      if ! cmp -s "$2/old.ll" "$2/new.ll"; then
        l=$(diff "$2/old.ll" "$2/new.ll" | sed -n '1s/^\([0-9]*\).*/\1/p')
        fn=$(head -n "${l:-0}" "$2/old.ll" | sed -n 's/^define [^@]*\(@[^(]*\)(.*/\1/p' | tail -1)
        echo "  IR${l:+ from line $l}${fn:+ (in $fn)}:"; diff -u "$2/old.ll" "$2/new.ll" | sed 1,2d | head -16
      fi
    elif [ -f "$2/old.ll" ] || [ -f "$2/new.ll" ]; then
      echo "  IR written by only one compiler"
    fi
  } > "$2/report.part"
  mv "$2/report.part" "$2/report"
  rm -f "$2/old.ll" "$2/new.ll"
}
# a worker: each program whose directory it is the first to create (mkdir is atomic)
worker() {
  i=0
  for f; do
    i=$((i + 1))
    if mkdir "$T/$i" 2> /dev/null; then same "$f" "$T/$i"; fi
  done
}
k=1
while [ $k -lt "$JOBS" ]; do
  worker "$@" &
  k=$((k + 1))
done
worker "$@"
wait
n=0; bad=0
for f; do
  n=$((n + 1)); r=$T/$n/report
  [ -f "$r" ] && [ ! -s "$r" ] && continue
  bad=$((bad + 1))
  if [ $bad -le $SHOW ]; then
    echo "DIFF $f"
    if [ -f "$r" ]; then cat "$r"; else echo "  no result (its worker died)"; fi
  fi
done
if [ $bad = 0 ]; then echo "$n programs identical"; else echo "$bad of $n differ"; fi
[ $bad = 0 ]
