#!/bin/sh
# The compiler under a CPython other than .python-version's (make python-versions;
# docs/testing.md#other-cpython-versions), three checks:
#   ir   the CPython-hosted compiler's IR of itself and of runtime.py is, byte for byte, stage 1's:
#        REFERENCE/stage1.ll and REFERENCE/rt1.ll (make writes them to build/, tests/verify.sh
#        bootstrap to build/verify/, with the CPython of .python-version in CI)
#   run  the CPython-hosted compiler, JIT and AOT, on a sample of the corpus, as make test-py runs it
#        (FILES selects other cases)
#   ffi  tests/ffi/run.sh with this CPython's libpython: C calls, CPython embedded, and extension
#        modules (abi3, or abi3t on a free-threaded CPython). It may skip only what this CPython
#        cannot run: the py_ and ext cases before 3.12, the ext cases on a free-threaded CPython
#        before 3.15, and the JSON repair replay, whose oracle is the pinned CPython
# The caller's settings that tests/verify.sh drops are dropped. Fails when a check fails.
# usage: tools/python_versions.sh PYTHON [COMPILER [REFERENCE]]   (default: ./pystachy and build)
cd "$(dirname "$0")/.." || exit 1
[ $# -ge 1 ] && [ $# -le 3 ] || { echo "usage: tools/python_versions.sh PYTHON [COMPILER [REFERENCE]]" >&2; exit 2; }
PY=$1
PYS=${2:-./pystachy}
REF=${3:-build}
FILES=${FILES:-tests/programs/syntax/*.py tests/programs/imports/*.py}
ign=$(env | sed -nE 's/^(PYSTACHY_(PATH|CFLAGS|AOT_OPT|PROFILE_GENERATE|PROFILE_USE|RUNTIME_C_CACHE|GC|GC_MIN|GC_STRESS|GC_STRESS_PROGRAM|IRCHECK|IRFX|TIMING|OPT|JIT_INLINE|JIT_OPT|JIT_CODEGEN|JIT_LAUNCHER|PROGRAM_CACHE|PROGRAM_CACHE_TRACE|PROGRAM_CACHE_INPUTS|PROGRAM_CACHE_LOCK|DEBUG_LINES|ARGV0|CASE_TIMES))=.*$/\1/p' | sort -u)
for e in $ign; do echo "tools/python_versions.sh: ignoring $e=$(printenv "$e")"; unset "$e"; done
PYSTACHY_HOME=$(pwd); export PYSTACHY_HOME
info=$("$PY" -I -c 'import platform, sys, sysconfig
print(platform.python_version(), "t" if sysconfig.get_config_var("Py_GIL_DISABLED") else "-", sys.version_info[1])') ||
  { echo "tools/python_versions.sh: $PY does not run" >&2; exit 2; }
# shellcheck disable=SC2086
set -- $info
VER=$1; FT=${2#-}; MINOR=$3
NAME="CPython $VER$FT"
PINNED=$(cat .python-version) || exit 2
for f in stage1.ll rt1.ll; do
  [ -s "$REF/$f" ] || { echo "tools/python_versions.sh: no $REF/$f (make writes it to build/)" >&2; exit 2; }
done
case $PYS in *" "*) ;; *) [ -x "$PYS" ] || { echo "tools/python_versions.sh: no compiler $PYS (make, or COMPILER)" >&2; exit 2; } ;; esac
T=$(mktemp -d "${TMPDIR:-/tmp}/pystachy-python-versions.XXXXXX") || exit 1
trap 'rm -rf "$T"' EXIT
trap 'exit 130' INT TERM
bad=0
ok() { echo "ok   $NAME: $*"; }
fail() { bad=$((bad + 1)); echo "FAIL $NAME: $*"; }

# ir: the hosted compiler's output must not depend on the CPython that runs it
for s in "pystachy.py stage1.ll ir" "runtime.py rt1.ll rt"; do
  # shellcheck disable=SC2086
  set -- $s
  if "$PY" pystachy.py "$3" "$1" -o "$T/$2" && cmp -s "$T/$2" "$REF/$2"; then
    ok "the hosted compiler's IR of $1 is $REF/$2 ($(wc -l < "$T/$2" | tr -d ' ') lines)"
  else
    fail "the hosted compiler's IR of $1 is not $REF/$2"
  fi
done

# run: as make test-py, whose bytecode CPython checks by hash
"$PY" -c 'import glob, py_compile as c; [c.compile(p, doraise=True, invalidation_mode=c.PycInvalidationMode.CHECKED_HASH) for p in ["pystachy.py"] + sorted(glob.glob("src/**/*.py", recursive=True))]' ||
  fail "cannot compile the compiler's bytecode"
# shellcheck disable=SC2086
if tests/run.sh "$PY -m pystachy" "jit aot" $FILES > "$T/run.log" 2>&1; then
  ok "the hosted compiler, JIT and AOT: $(tail -1 "$T/run.log")"
else
  tail -40 "$T/run.log" 2> /dev/null
  fail "the hosted compiler, JIT and AOT: $(tail -1 "$T/run.log" 2> /dev/null)"
fi

# ffi: every skip must be one this CPython cannot run
PY="$PY" tests/ffi/run.sh "$PYS" "jit aot" > "$T/ffi.log" 2>&1; st=$?
last=$(tail -1 "$T/ffi.log")
printf '%s\n' "$last" | sed -n 's/^[0-9]* passed, [0-9]* failed; skipped: //p' |
  awk -F'; ' '{ for (i = 1; i <= NF; i++) print $i }' > "$T/skips"
extra=
while IFS= read -r s; do
  case $s in
    "the py_ and ext cases (no "*) [ "$MINOR" -lt 12 ] && continue ;;
    "the ext cases (a free-threaded CPython before 3.15 "*) [ -n "$FT" ] && [ "$MINOR" -lt 15 ] && continue ;;
    "the CPython JSON repair extension replay (its oracle is CPython $PINNED, not $VER)") [ -z "$FT" ] && continue ;;
  esac
  extra="${extra:+$extra; }$s"
done < "$T/skips"
case $last in [1-9]*" passed, 0 failed"*) passed=1 ;; *) passed= ;; esac
if [ $st = 0 ] && [ -n "$passed" ] && [ -z "$extra" ]; then
  ok "the FFI: $last"
else
  grep -A12 '^FAIL' "$T/ffi.log" | head -60
  fail "the FFI${extra:+, which skipped what $NAME runs ($extra)}: $last"
fi

if [ $bad = 0 ]; then echo "$NAME: every check passed"; else echo "$NAME: $bad checks failed"; exit 1; fi
