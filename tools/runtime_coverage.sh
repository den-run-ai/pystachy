#!/bin/sh
# Coverage of the native runtime's C code (make runtime-coverage; docs/testing.md#native-runtime-coverage):
# runtime.c (with the ryu/ and mpz/ files it includes), pyembed.c and pyext.c, built with clang's source-based
# coverage (PYSTACHY_CFLAGS="-fprofile-instr-generate -fcoverage-mapping") into a new runtime cache,
# while these suites run with the native compiler:
#   corpus  tests/run.sh's differential and deviation programs, JIT and AOT, or the FILEs given
#   ffi     tests/ffi/run.sh, AOT: C calls, CPython embedded (pyembed.c), extension modules (pyext.c)
# Each instrumented program adds its counts, at exit, to a profile of its kind of binary (the %m of
# LLVM_PROFILE_FILE: the JIT tier's shared runtime, AOT executables, extension modules); a program that
# ends by a signal or _exit() adds none. Each part (a suite, or a shard of the corpus) merges its
# programs' profiles into build/runtime-coverage/parts/PART.profdata, beside PART.log (its tests'
# report) and PART.json (its counts). The report merges the parts' profiles and reads them through
# objects compiled here from the same sources with the same flags: the driver compiles a copy of
# runtime.c behind a #line, which clang's coverage mapping does not follow (its lines would be off by
# one), and pyembed.c and pyext.c from standard input; clang finds a function's counters by its name
# and the hash of its body, which are the same, and the run fails on any that are not (llvm-cov's
# "mismatched data"), as on parts that do not all measure the commit the objects are compiled from.
# runtime.py, which Pystachy compiles, carries no instrumentation and is not measured; nor are the C
# probes (make dictprobe and the others), which compile runtime.c under macros of their own.
# Report only: it fails when a test fails or no profile is written, never on a percentage. Writes
# build/runtime-coverage/: html/ (llvm-cov's annotated source, branches included), coverage.json
# (llvm-cov export's summary), lcov.info, summary.md (lines, branches, functions and regions for each
# file, and for each section of runtime.c: the collector, strings, lists, dicts, exceptions...) and
# badge.json (lines and branches, as a shields.io endpoint badge).
# usage: tools/runtime_coverage.sh [FILE...]   env: COMPILER (default ./pystachy), PY (default python3:
#        the FFI suite's CPython, and the report's), PYSTACHY_LLVM (its llvm-profdata, llvm-cov and
#        clang's profile runtime, which Ubuntu's libclang-rt-18-dev holds); RUNTIME_COVERAGE_SUITES
#        (default "corpus ffi", or corpus alone for FILEs); RUNTIME_COVERAGE_SHARD=I/N, shard I of
#        N of the corpus alone (tools/shard_cases.sh); RUNTIME_COVERAGE_REPORT=0, no report
#        (CI measures the parts in jobs of their own); COVERAGE_BASE=REF, the summary also lists the
#        C code changed since REF's merge base with HEAD that the programs did not run
#        tools/runtime_coverage.sh --report   (the report alone, of the parts already in parts/)
cd "$(dirname "$0")/.." || exit 1
PYS=${COMPILER:-./pystachy}
PY=${PY:-python3}
C=build/runtime-coverage
# (plain counters, not atomic ones: the registers their updates take moved a dead File pointer into
# one that collect() scans, which showed open() keeping alive the writer it collected to close,
# tests/programs/runtime/rt_list_vacated.py, as no -O level nor register allocator did: this run is also a variant)
CF="-fprofile-instr-generate -fcoverage-mapping"
llvm=${PYSTACHY_LLVM:-$($PY -c 'import pystachy; print(pystachy.llvm_dir())')}
L=${llvm:+${llvm%/}/}
report=1
if [ "${1:-}" = --report ]; then
  [ $# = 1 ] || { echo "usage: tools/runtime_coverage.sh --report   (no FILEs)" >&2; exit 2; }
  shift; report=only
  [ -d "$C/parts" ] ||
    { echo "tools/runtime_coverage.sh: no parts in $C/parts/ (runs with RUNTIME_COVERAGE_REPORT=0 write them)" >&2; exit 1; }
  rm -rf "$C/html" "$C/objects" "$C/runtime.profdata" || exit 1
else
  [ "${RUNTIME_COVERAGE_REPORT:-1}" != 0 ] || report=
  if [ $# = 0 ]; then SUITES=${RUNTIME_COVERAGE_SUITES:-corpus ffi}; else SUITES=${RUNTIME_COVERAGE_SUITES:-corpus}; fi
  for s in $SUITES; do
    case $s in corpus | ffi) ;; *) echo "tools/runtime_coverage.sh: no suite '$s' (corpus, ffi)" >&2; exit 2 ;; esac
  done
  if [ -n "${RUNTIME_COVERAGE_SHARD:-}" ]; then
    [ $# = 0 ] || { echo "tools/runtime_coverage.sh: FILEs or RUNTIME_COVERAGE_SHARD, not both" >&2; exit 2; }
    tools/shard_cases.sh "$RUNTIME_COVERAGE_SHARD" > /dev/null || exit 2
  fi
  [ -x "$PYS" ] || { echo "tools/runtime_coverage.sh: no compiler $PYS (make, or COMPILER=...)" >&2; exit 1; }
  rm -rf "$C" && mkdir -p "$C/parts" || exit 1
fi
W=$(mktemp -d "${TMPDIR:-/tmp}/pystachy-rtcov.XXXXXX") || exit 1
trap 'rm -rf "$W"' EXIT
trap 'exit 130' INT TERM
rev=$(git rev-parse HEAD 2> /dev/null) || rev=unknown
dirty=false
[ -z "$(git status --porcelain --untracked-files=no 2> /dev/null)" ] || dirty=true

if [ "$report" != only ]; then
  echo 'int main(void) { return 0; }' | "${L}clang" -x c $CF - -o "$W/probe" ||
    { echo "tools/runtime_coverage.sh: clang cannot link $CF: install its profile runtime (Ubuntu: libclang-rt-18-dev)" >&2; exit 1; }
  # part PART SUITE CASES CMD...: runs CMD (its report in $C/parts/PART.log) with the instrumented
  # runtime, merges the profiles its programs wrote into $C/parts/PART.profdata and writes PART.json
  failed=
  part() {
    p=$1; s=$2; cases=$3; shift 3
    t0=$(date +%s)
    PYSTACHY_CACHE=$W/cache PYSTACHY_CFLAGS=$CF LLVM_PROFILE_FILE=$W/$p/%m.profraw "$@" > "$C/parts/$p.log" 2>&1
    st=$?
    secs=$(($(date +%s) - t0))
    cat "$C/parts/$p.log"
    [ $st = 0 ] || { failed="$failed $p"; return; }
    set -- "$W/$p"/*.profraw
    [ -f "$1" ] || { echo "tools/runtime_coverage.sh: $p: no program wrote a profile"; failed="$failed $p"; return; }
    "${L}llvm-profdata" merge -sparse "$@" -o "$C/parts/$p.profdata" || { failed="$failed $p"; return; }
    shard=null; [ -z "${RUNTIME_COVERAGE_SHARD:-}" ] || [ "$s" != corpus ] || shard="[${RUNTIME_COVERAGE_SHARD%/*}, ${RUNTIME_COVERAGE_SHARD#*/}]"
    sel=false; [ "$s" != corpus ] || [ "$nsel" = 0 ] || sel=true
    printf '{"part": "%s", "suite": "%s", "shard": %s, "selected": %s, "cases": %s, "report": "%s", "profiles": %s, "seconds": %s, "commit": "%s", "dirty": %s}\n' \
      "$p" "$s" "$shard" "$sel" "$cases" "$(tail -1 "$C/parts/$p.log" | sed 's/[\\"]/\\&/g')" "$#" "$secs" "$rev" "$dirty" > "$C/parts/$p.json"
  }
  nsel=$#
  if [ -n "${RUNTIME_COVERAGE_SHARD:-}" ]; then
    tools/shard_cases.sh "$RUNTIME_COVERAGE_SHARD" > "$W/cases" || exit 1
    while IFS= read -r f; do set -- "$@" "$f"; done < "$W/cases"
    [ $# != 0 ] || { echo "tools/runtime_coverage.sh: shard $RUNTIME_COVERAGE_SHARD has no case" >&2; exit 1; }
  fi
  for s in $SUITES; do
    case $s in
      corpus)
        p=corpus; [ -z "${RUNTIME_COVERAGE_SHARD:-}" ] || p=corpus-${RUNTIME_COVERAGE_SHARD%/*}
        cases=$#; [ $# != 0 ] || cases=$(. tests/corpus.sh && corpus | wc -l | tr -d ' ')
        part "$p" corpus "$cases" tests/run.sh "$PYS" "jit aot" "$@" ;;
      ffi) part ffi ffi null env PY="$PY" tests/ffi/run.sh "$PYS" aot ;;
    esac
  done
  [ -z "$failed" ] || { echo "tools/runtime_coverage.sh: the tests failed:$failed ($C/parts/)" >&2; exit 1; }
  [ -n "$report" ] || exit 0
fi
# the objects that llvm-cov reads the counts through: runtime.c's name and pyembed.c's and pyext.c's
# ("-": standard input) are the driver's, which name its static functions' counters. (Before the
# merged profile: llvm-cov warns of a profile older than its objects, and a warning fails the run.)
mkdir -p "$C/objects" || exit 1
for f in runtime pyembed pyext; do
  name=; [ $f = runtime ] || name="-Xclang -main-file-name -Xclang -"
  # shellcheck disable=SC2086
  "${L}clang" -O2 -fPIC -c -x c "$f.c" -o "$C/objects/$f.o" $CF -fexceptions -fcoverage-compilation-dir=. $name || exit 1
done
# the profiles of the parts that PART.json describes (tools/coverage_report.py checks those)
set --
for j in "$C"/parts/*.json; do
  [ -f "$j" ] || continue
  [ -f "${j%.json}.profdata" ] || { echo "tools/runtime_coverage.sh: ${j%.json}.profdata: no such profile" >&2; exit 1; }
  set -- "$@" "${j%.json}.profdata"
done
[ $# != 0 ] || { echo "tools/runtime_coverage.sh: no parts in $C/parts/" >&2; exit 1; }
"${L}llvm-profdata" merge -sparse "$@" -o "$C/runtime.profdata" || exit 1
objects="$C/objects/runtime.o -object $C/objects/pyembed.o -object $C/objects/pyext.o"
# shellcheck disable=SC2086
{
  "${L}llvm-cov" export -summary-only -instr-profile="$C/runtime.profdata" $objects > "$C/coverage.json" &&
    "${L}llvm-cov" export -format=lcov -instr-profile="$C/runtime.profdata" $objects > "$C/lcov.info" &&
    "${L}llvm-cov" show -format=html -output-dir="$C/html" -show-branches=count -show-line-counts-or-regions \
      -project-title="Pystachy native runtime coverage" -instr-profile="$C/runtime.profdata" $objects
} 2> "$C/llvm-cov.err" || { cat "$C/llvm-cov.err" >&2; exit 1; }
if [ -s "$C/llvm-cov.err" ]; then
  cat "$C/llvm-cov.err" >&2
  echo "tools/runtime_coverage.sh: llvm-cov could not read every profile through the sources' objects" >&2; exit 1
fi
$PY tools/coverage_report.py --runtime "$C" "$rev" "$dirty"
