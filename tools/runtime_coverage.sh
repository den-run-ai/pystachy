#!/bin/sh
# Coverage of the native runtime's C code (make runtime-coverage; docs/testing.md#native-runtime-coverage):
# runtime.c (with the ryu/ files it includes), pyembed.c and pyext.c, built with clang's source-based
# coverage (PYSTACHY_CFLAGS="-fprofile-instr-generate -fcoverage-mapping") into a new runtime cache,
# while these suites run with the native compiler:
#   corpus  tests/run.sh's differential and deviation programs, JIT and AOT, or the FILEs given
#   ffi     tests/ffi/run.sh, AOT: C calls, CPython embedded (pyembed.c), extension modules (pyext.c)
# Each instrumented program adds its counts, at exit, to a profile of its kind of binary (the %m of
# LLVM_PROFILE_FILE: the JIT tier's shared runtime, AOT executables, extension modules); a program that
# ends by a signal or _exit() adds none. llvm-cov reads the profiles through objects compiled here from
# the same sources with the same flags: the driver compiles a copy of runtime.c behind a #line, which
# clang's coverage mapping does not follow (its lines would be off by one), and pyembed.c and pyext.c
# from standard input; clang finds a function's counters by its name and the hash of its body, which
# are the same, and the run fails on any that are not (llvm-cov's "mismatched data").
# runtime.py, which Pystachy compiles, carries no instrumentation and is not measured; nor are the C
# probes (make dictprobe and the others), which compile runtime.c under macros of their own.
# Report only: it fails when a test fails or no profile is written, never on a percentage. Writes
# build/runtime-coverage/: html/ (llvm-cov's annotated source, branches included), coverage.json
# (llvm-cov export's summary), lcov.info, summary.md (lines, branches, functions and regions for each
# file, and for each section of runtime.c: the collector, strings, lists, dicts, exceptions...),
# badge.json (lines and branches, as a shields.io endpoint badge) and each suite's log.
# usage: tools/runtime_coverage.sh [FILE...]   env: COMPILER (default ./pystachy), PY (default python3:
#        the FFI suite's CPython, and the report's), PYSTACHY_LLVM (its llvm-profdata, llvm-cov and
#        clang's profile runtime, which Ubuntu's libclang-rt-18-dev holds); RUNTIME_COVERAGE_SUITES
#        (default "corpus ffi", or corpus alone for FILEs); COVERAGE_BASE=REF, the summary also lists
#        the C code changed since REF's merge base with HEAD that the programs did not run
cd "$(dirname "$0")/.." || exit 1
PYS=${COMPILER:-./pystachy}
PY=${PY:-python3}
C=build/runtime-coverage
# (plain counters, not atomic ones: the registers their updates take moved a dead File pointer into
# one that collect() scans, which showed open() keeping alive the writer it collected to close,
# tests/rt_list_vacated.py, as no -O level nor register allocator did: this run is also a variant)
CF="-fprofile-instr-generate -fcoverage-mapping"
llvm=${PYSTACHY_LLVM:-$($PY -c 'import pystachy; print(pystachy.llvm_dir())')}
L=${llvm:+${llvm%/}/}
if [ $# = 0 ]; then SUITES=${RUNTIME_COVERAGE_SUITES:-corpus ffi}; else SUITES=${RUNTIME_COVERAGE_SUITES:-corpus}; fi
for s in $SUITES; do
  case $s in corpus | ffi) ;; *) echo "tools/runtime_coverage.sh: no suite '$s' (corpus, ffi)" >&2; exit 2 ;; esac
done
[ -x "$PYS" ] || { echo "tools/runtime_coverage.sh: no compiler $PYS (make, or COMPILER=...)" >&2; exit 1; }
rm -rf "$C" && mkdir -p "$C/objects" || exit 1
W=$(mktemp -d "${TMPDIR:-/tmp}/pystachy-rtcov.XXXXXX") || exit 1
trap 'rm -rf "$W"' EXIT
trap 'exit 130' INT TERM
# the objects that llvm-cov reads the counts through: runtime.c's name and pyembed.c's and pyext.c's
# ("-": standard input) are the driver's, which name its static functions' counters
echo 'int main(void) { return 0; }' | "${L}clang" -x c $CF - -o "$W/probe" ||
  { echo "tools/runtime_coverage.sh: clang cannot link $CF: install its profile runtime (Ubuntu: libclang-rt-18-dev)" >&2; exit 1; }
for f in runtime pyembed pyext; do
  name=; [ $f = runtime ] || name="-Xclang -main-file-name -Xclang -"
  # shellcheck disable=SC2086
  "${L}clang" -O2 -fPIC -c -x c "$f.c" -o "$C/objects/$f.o" $CF -fexceptions -fcoverage-compilation-dir=. $name || exit 1
done

# suite NAME CMD...: runs CMD (its report in $C/NAME.log) with the instrumented runtime
failed=
suite() {
  n=$1; shift
  t0=$(date +%s)
  PYSTACHY_CACHE=$W/cache PYSTACHY_CFLAGS=$CF LLVM_PROFILE_FILE=$W/raw/%m.profraw "$@" > "$C/$n.log" 2>&1
  st=$?
  secs=$(($(date +%s) - t0))
  cat "$C/$n.log"
  [ $st = 0 ] || failed="$failed $n"
  printf '%s\t%s\t%s\n' "$n" "$(tail -1 "$C/$n.log")" "$secs" >> "$C/suites.tsv"
}
: > "$C/suites.tsv"
for s in $SUITES; do
  case $s in
    corpus) suite corpus tests/run.sh "$PYS" "jit aot" "$@" ;;
    ffi) suite ffi env PY="$PY" tests/ffi/run.sh "$PYS" aot ;;
  esac
done
[ -z "$failed" ] || { echo "tools/runtime_coverage.sh: the tests failed:$failed ($C/)" >&2; exit 1; }
set -- "$W"/raw/*.profraw
[ -f "$1" ] || { echo "tools/runtime_coverage.sh: no program wrote a profile" >&2; exit 1; }
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
rev=$(git rev-parse HEAD 2> /dev/null) || rev=unknown
dirty=false
[ -z "$(git status --porcelain --untracked-files=no 2> /dev/null)" ] || dirty=true
$PY tools/coverage_report.py --runtime "$C" "$rev" "$dirty"
