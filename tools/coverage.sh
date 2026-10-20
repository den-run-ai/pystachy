#!/bin/sh
# Coverage of the compiler's own source (make coverage; docs/testing.md#compiler-coverage): the suites
# below, run by the CPython-hosted compiler ($PY -m pystachy, as make test-py runs it) under coverage.py
# as .coveragerc sets it: the statements and branches of src/pystachy_compiler/, one data file per
# compiler process, each suite's under a context of its name (the HTML report shows which ran a line).
#   corpus  tests/run.sh's differential, rejection and deviation cases, JIT and AOT, or the FILEs given
#   ffi     tests/ffi/run.sh, JIT and AOT (make test-ffi): C calls, CPython embedded, extension modules
#   cache   tests/cache.sh (make test-cache): the cached runtime's rules, the driver's search for LLVM
#   unit    the compiler's unit tests, tools/test_typed*.py and tools/test_function_summaries.py
#   ir      tools/check_ir.sh (make check-ir) on the programs the corpus does not compile: pystachy.py
#           and runtime.py (as the bootstrap's first stage compiles them), bench/ and the tests/ir/
#           probes, with their effect, call, attribute and TBAA contracts
# Each compiler process starts through a launcher that counts it, and a part (a suite, or a shard of
# the corpus) fails unless every process left its data: all but the one that tests/cache.sh kills in
# the middle of a build. Each part's runtime cache is a new, empty one, so that the runtime is built
# (runtime.py compiled) under coverage. Report only: it fails when a test fails or data is missing,
# never on a percentage.
# Each part leaves build/coverage/parts/: data.PART (its data, combined), PART.log (its tests' report)
# and PART.json (its counts). tools/coverage_report.py then combines the parts into build/coverage/:
# html/ (the annotated source), coverage.json, summary.md (statements and branches apart, for every
# suite and module) and badge.json (both, as a shields.io endpoint badge).
# usage: tools/coverage.sh [FILE...]   env: PY (default python3), which has coverage.py
#        (pip install -r tools/requirements-dev.txt); COVERAGE_SUITES, the suites to run (default
#        "corpus ffi cache unit ir", or corpus alone for FILEs); COVERAGE_SHARD=I/N, the corpus cases I,
#        I + N, I + 2N... alone, as tests/verify.sh's shards are; COVERAGE_REPORT=0, no report (CI
#        measures the parts in jobs of their own, then combines them)
cd "$(dirname "$0")/.." || exit 1
R=$(pwd)
PY=${PY:-python3}
case $PY in /*) ;; */*) PY=$R/$PY ;; esac   # (tests/cache.sh's compiler runs in a directory of its own)
C=build/coverage
$PY -m coverage --version > /dev/null || { echo "tools/coverage.sh: $PY has no coverage.py (pip install -r tools/requirements-dev.txt)" >&2; exit 1; }
if [ $# = 0 ]; then SUITES=${COVERAGE_SUITES:-corpus ffi cache unit ir}; else SUITES=${COVERAGE_SUITES:-corpus}; fi
for s in $SUITES; do
  case $s in corpus | ffi | cache | unit | ir) ;; *) echo "tools/coverage.sh: no suite '$s' (corpus, ffi, cache, unit, ir)" >&2; exit 2 ;; esac
done
si=; sn=
case ${COVERAGE_SHARD:-} in
  '') ;;
  [0-9]*/[0-9]*) si=${COVERAGE_SHARD%/*}; sn=${COVERAGE_SHARD#*/} ;;
  *) si=x ;;
esac
case $si$sn in *[!0-9]*) echo "tools/coverage.sh: COVERAGE_SHARD=$COVERAGE_SHARD is not I/N" >&2; exit 2 ;; esac
if [ -n "$sn" ]; then
  [ "$sn" -gt 0 ] && [ "$si" -lt "$sn" ] || { echo "tools/coverage.sh: COVERAGE_SHARD=$COVERAGE_SHARD: no shard $si of $sn" >&2; exit 2; }
  [ $# = 0 ] || { echo "tools/coverage.sh: FILEs or COVERAGE_SHARD, not both" >&2; exit 2; }
fi
rm -rf "$C" && mkdir -p "$C/parts" || exit 1
W=$(mktemp -d "${TMPDIR:-/tmp}/pystachy-coverage.XXXXXX") || exit 1
trap 'rm -rf "$W"' EXIT
trap 'exit 130' INT TERM
export COVERAGE_RCFILE="$R/.coveragerc"
rev=$(git rev-parse HEAD 2> /dev/null) || rev=unknown
dirty=false
[ -z "$(git status --porcelain --untracked-files=no 2> /dev/null)" ] || dirty=true

# launcher PART SUITE: $W/PART.run, which notes each process it starts in $W/PART.procs and runs python
# there under coverage.py, with the suite's context
launcher() {
  mkdir -p "$W/$1.data" && : > "$W/$1.procs" || exit 1
  printf '#!/bin/sh\necho >> %s\nexec %s -m coverage run --context=%s "$@"\n' "'$W/$1.procs'" "$PY" "$2" > "$W/$1.run" &&
    chmod +x "$W/$1.run" || exit 1
}
# part PART SUITE CASES CMD...: runs CMD (the part's tests, CASES of the corpus or null, their report in
# $C/parts/PART.log) with a new runtime cache; then checks that every process its launcher started left
# data, combines that into $C/parts/data.PART and writes $C/parts/PART.json
failed=
part() {
  p=$1; s=$2; cases=$3; shift 3
  t0=$(date +%s)
  COVERAGE_FILE=$W/$p.data/data.$p PYSTACHY_CACHE=$W/$p.cache "$@" > "$C/parts/$p.log" 2>&1
  st=$?
  secs=$(($(date +%s) - t0))
  grep -v '^ok ' "$C/parts/$p.log"
  procs=$(wc -l < "$W/$p.procs" | tr -d ' ')
  n=$(find "$W/$p.data" -name "data.$p.*" | wc -l | tr -d ' ')
  want=$procs; [ "$s" != cache ] || want=$((procs - 1))   # (killed: CACHE_KILL)
  if [ "$s" = unit ]; then
    tests=$(sed -n 's/^Ran \([0-9]*\) tests* in .*/\1/p' "$C/parts/$p.log" | awk '{ n += $1 } END { print n + 0 }')
    report="$tests tests, OK"
  else
    report=$(tail -1 "$C/parts/$p.log" | sed 's/[\\"]/\\&/g')
  fi
  if [ $st != 0 ]; then
    echo "tools/coverage.sh: $p: the tests failed"; failed="$failed $p"; return
  elif [ "$procs" = 0 ] || [ "$n" != "$want" ]; then
    echo "tools/coverage.sh: $p: $n coverage data files, for $procs processes"; failed="$failed $p"; return
  fi
  COVERAGE_FILE=$C/parts/data.$p $PY -m coverage combine -q "$W/$p.data" || { failed="$failed $p"; return; }
  shard=null; [ -z "$sn" ] || [ "$s" != corpus ] || shard="[$si, $sn]"
  sel=false; [ "$s" != corpus ] || [ $nsel = 0 ] || sel=true
  printf '{"part": "%s", "suite": "%s", "shard": %s, "selected": %s, "cases": %s, "report": "%s", "processes": %s, "data_files": %s, "seconds": %s, "commit": "%s", "dirty": %s}\n' \
    "$p" "$s" "$shard" "$sel" "$cases" "$report" "$procs" "$n" "$secs" "$rev" "$dirty" > "$C/parts/$p.json"
  echo "$p: $report; $procs processes, $n with data, $secs s"
}

nsel=$#
if [ -n "$sn" ]; then
  # the corpus cases whose position in C order is I modulo N (tests/verify.sh's shard_cases)
  (
    export LC_ALL=C
    k=0
    for f in tests/*.py tests/deviations/*.py tests/errors/*.py; do
      [ -f "$f" ] || continue
      [ $((k % sn)) != "$si" ] || printf '%s\n' "$f"
      k=$((k + 1))
    done
  ) > "$W/cases" || exit 1
  while IFS= read -r f; do set -- "$@" "$f"; done < "$W/cases"
  [ $# != 0 ] || { echo "tools/coverage.sh: shard $si of $sn has no case" >&2; exit 1; }
fi
for s in $SUITES; do
  p=$s; [ -z "$sn" ] || [ "$s" != corpus ] || p=corpus-$si
  launcher "$p" "$s"
  case $s in
    corpus)
      cases=$#; [ $# != 0 ] || cases=$(ls tests/*.py tests/deviations/*.py tests/errors/*.py | wc -l | tr -d ' ')
      part "$p" corpus "$cases" tests/run.sh "$W/$p.run -m pystachy" "jit aot" "$@" ;;
    ffi) part ffi ffi null env PY="$PY" tests/ffi/run.sh "$W/ffi.run -m pystachy" "jit aot" ;;
    cache) part cache cache null env PY="$PY" tests/cache.sh "$W/cache.run -m pystachy" ;;
    unit)
      part unit unit null sh -c '"$1" -m unittest discover -s tools -p "test_typed*.py" && "$1" -m unittest discover -s tools -p test_function_summaries.py' unit "$W/unit.run" ;;
    # (tools/check_ir.sh's own programs but the corpus's)
    ir) part ir ir null tools/check_ir.sh "$W/ir.run -m pystachy" pystachy.py runtime.py bench/*.py bench/pyperformance/*.py tests/ir/*.py ;;
  esac
done
[ -z "$failed" ] || { echo "tools/coverage.sh: failed:$failed (build/coverage/parts/)" >&2; exit 1; }
[ "${COVERAGE_REPORT:-1}" = 0 ] || $PY tools/coverage_report.py "$C"
