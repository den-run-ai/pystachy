#!/bin/sh
# Record what CPython prints for differential tests, the way tests/run.sh runs them, beside each
# program tests/programs/AREA/NAME.py (tests/corpus.sh): NAME.out is stdout followed by "[exit N]";
# NAME.err, kept only where CPython wrote to stderr, is the last line it wrote there. NAME.in, if
# present, is stdin; if NAME.full exists, stdout is /dev/full (so NAME.out holds only the exit
# status); if NAME.path exists, it is PYTHONPATH (tests/run.sh makes it PYSTACHY_PATH).
# CPython's environment holds PATH and that PYTHONPATH, nothing else of the caller's: FORCE_COLOR
# would color its tracebacks, the caller's PYTHONPATH add modules, PYTHONUNBUFFERED change what
# reaches a stdout the program shares with os.system's commands. Without LANG and LC_*, the locale
# is C, in which CPython runs in UTF-8 mode (PEP 540: PYTHONUTF8=1 changes nothing). It must be the
# CPython of .python-version: another minor version is refused (3.12 prints otherwise for 28
# tests), another patch version warned about.
# tests/record.sh --check records every test into a temporary directory instead, and fails where
# that differs from NAME.out or NAME.err; where CPython prints what a tests/deviations/NAME.py must
# print (its .out: the deviation is gone); where a module of lib/ is not the CPython file whose
# SHA-256 lib/README.md lists; where a .out, .err, .in, .full or .path has no NAME.py beside it;
# where a test lies outside the corpus's areas (tests/corpus.sh's corpus_strays), or two programs,
# or two rejections, have one name (tests/run.sh names a case's files by it); and where a *.rej,
# *.orig or core file lies in the tree.
# usage: tests/record.sh NAME...      (a program's name, or its path; PYTHON=python3.13 picks one)
#        tests/record.sh --check
cd "$(dirname "$0")/.." || exit 1
. tests/corpus.sh
# shellcheck disable=SC3045 # (ulimit -c is not POSIX, but dash, bash, ksh and busybox have it)
ulimit -c 0 2> /dev/null
PY=${PYTHON:-python3}
[ $# != 0 ] || { echo "usage: tests/record.sh NAME... | --check" >&2; exit 2; }
want=$(cat .python-version) || exit 2
have=$(env -i PATH="$PATH" "$PY" -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])') || exit 2
case $have in
  "$want") ;;
  "${want%.*}".*) echo "tests/record.sh: warning: $PY is CPython $have, not $want (.python-version)" >&2 ;;
  *) echo "tests/record.sh: $PY is CPython $have, not ${want%.*} (.python-version: $want)" >&2; exit 2 ;;
esac
T=$(mktemp -d "${TMPDIR:-/tmp}/pystachy-record.XXXXXX") || exit 1
trap 'rm -rf "$T"' EXIT
trap 'exit 130' INT TERM
exec 3> /dev/full

# cpython B: B.py (B: a program's path without .py) run as tests/run.sh runs it, its stdout and
# "[exit N]" to $T/NAME.out, its stderr to $T/NAME.stderr
cpython() {
  n=${1##*/}
  in=/dev/null; [ -f "$1.in" ] && in="$1.in"
  o=1; [ -f "$1.full" ] && o=3
  mp=; [ -f "$1.path" ] && mp=$(cat "$1.path")
  (env -i PATH="$PATH" ${mp:+"PYTHONPATH=$mp"} "$PY" "$1.py" a1 a2 < "$in" >&$o; echo "[exit $?]") > "$T/$n.out" 2> "$T/$n.stderr"
}

if [ "$1" != --check ]; then
  for a; do
    # the program: the path given, or the one tests/programs/AREA/NAME.py of that name
    case $a in
      */*) b=${a#./}; b=${b%.py}; [ -f "$b.py" ] && case $b in tests/programs/*/*) ;; *) false ;; esac ||
        { echo "tests/record.sh: no program $a (programs are tests/programs/AREA/NAME.py)" >&2; exit 2; } ;;
      *)
        b=; for f in tests/programs/*/"${a%.py}.py"; do
          [ -f "$f" ] || continue
          [ -z "$b" ] || { echo "tests/record.sh: two programs are named ${a%.py}: $b.py and $f" >&2; exit 2; }
          b=${f%.py}
        done
        [ -n "$b" ] || { echo "tests/record.sh: no tests/programs/AREA/${a%.py}.py" >&2; exit 2; } ;;
    esac
    n=${b##*/}
    cpython "$b"
    mv "$T/$n.out" "$b.out"
    if [ -s "$T/$n.stderr" ]; then tail -1 "$T/$n.stderr" > "$b.err"; else rm -f "$b.err"; fi
    echo "$n: $(tail -1 "$b.out") $(cat "$b.err" 2>/dev/null)"
  done
  exit 0
fi
[ $# = 1 ] || { echo "usage: tests/record.sh --check" >&2; exit 2; }

bad=0; nrec=0; ndev=0; nlib=0
corpus > "$T/corpus"
while IFS= read -r f; do
  case $f in tests/programs/*) ;; *) continue ;; esac
  b=${f%.py}; n=${b##*/}; nrec=$((nrec + 1))
  cpython "$b"
  if ! cmp -s "$T/$n.out" "$b.out"; then
    bad=$((bad + 1)); echo "FAIL $n: $b.out (<) is not what CPython prints (>)"; diff "$b.out" "$T/$n.out" | head -10
  fi
  if [ -s "$T/$n.stderr" ]; then
    tail -1 "$T/$n.stderr" > "$T/$n.err"
    if [ ! -f "$b.err" ]; then
      bad=$((bad + 1)); echo "FAIL $n: CPython writes to stderr, and there is no $b.err: '$(cat "$T/$n.err")'"
    elif ! cmp -s "$T/$n.err" "$b.err"; then
      bad=$((bad + 1)); echo "FAIL $n: CPython's last line of stderr is not $b.err: want '$(cat "$b.err")', CPython '$(cat "$T/$n.err")'"
    fi
  elif [ -f "$b.err" ]; then
    bad=$((bad + 1)); echo "FAIL $n: CPython writes nothing to stderr, but $b.err exists"
  fi
done < "$T/corpus"
# A deviation is gone where CPython prints the hand-written .out: its stdout, the last line of its
# stderr (where Pystachy reports an uncaught exception, after flushing stdout) and its exit status,
# as tests/run.sh runs it
for f in tests/deviations/*.py; do
  n=$(basename "$f" .py); ndev=$((ndev + 1))
  env -i PATH="$PATH" "$PY" "$f" a1 a2 < /dev/null > "$T/dev.out" 2> "$T/dev.err"
  st=$?
  { cat "$T/dev.out"; tail -1 "$T/dev.err"; echo "[exit $st]"; } > "$T/dev.all"
  if cmp -s "$T/dev.all" "tests/deviations/$n.out"; then
    bad=$((bad + 1)); echo "FAIL deviations/$n: CPython prints tests/deviations/$n.out: no deviation left (make it a differential test)"
  fi
done
# lib/README.md's table: | `module` | `Lib/PATH` | `SHA-256` | ... for each unmodified copy lib/PATH
sha() { if command -v sha256sum > /dev/null; then sha256sum "$1"; else shasum -a 256 "$1"; fi 2> /dev/null | cut -c1-64; }
sed -n 's/^| `[^`]*` | `Lib\/\([^`]*\)` | `\([0-9a-f]\{64\}\)` |.*$/\2 lib\/\1/p' lib/README.md > "$T/lib"
while read -r h f; do
  nlib=$((nlib + 1))
  [ "$(sha "$f")" = "$h" ] || { bad=$((bad + 1)); echo "FAIL $f: not the CPython file of lib/README.md (SHA-256 $h)"; }
done < "$T/lib"
[ $nlib != 0 ] || { bad=$((bad + 1)); echo "FAIL lib/README.md: no SHA-256 found in its table"; }
for f in tests/programs/*/*.out tests/programs/*/*.err tests/programs/*/*.in tests/programs/*/*.full \
  tests/programs/*/*.path tests/errors/*/*.path tests/deviations/*.out; do
  [ ! -f "$f" ] || [ -f "${f%.*}.py" ] || { bad=$((bad + 1)); echo "FAIL $f: there is no ${f%.*}.py"; }
done
corpus_strays > "$T/strays"
while read -r f; do
  bad=$((bad + 1)); echo "FAIL $f: no run tests it here (programs are tests/programs/AREA/NAME.py, rejections tests/errors/AREA/NAME.py)"
done < "$T/strays"
for d in programs errors; do
  for f in tests/$d/*/*.py; do [ -f "$f" ] && printf '%s\n' "${f##*/}"; done | sort | uniq -d > "$T/twice"
  while read -r n; do bad=$((bad + 1)); echo "FAIL tests/$d/*/$n: two cases have that name"; done < "$T/twice"
done
find . \( -path ./.git -o -path ./build -o -path ./.claude \) -prune -o -type f \
  \( -name '*.rej' -o -name '*.orig' -o -name core -o -name 'core.[0-9]*' \) -print | sed 's|^\./||' > "$T/stray"
while read -r f; do bad=$((bad + 1)); echo "FAIL $f: a stray file (a patch's leftover, a core dump)"; done < "$T/stray"
echo "CPython $have: $nrec recordings, $ndev deviations, $nlib files of lib/ checked; $bad failed"
[ $bad = 0 ]
