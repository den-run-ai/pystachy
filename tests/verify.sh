#!/bin/sh
# Verification harness: every check below runs (a failing step does not stop the others) and the
# results go to build/verification.json -- per step: name, pass/fail, duration, counts -- with the
# toolchain versions, git commit and a timestamp. Exit status 0 only if every step passed.
#   bootstrap      CPython -> stage1 -> stage2 -> stage3 compilers emit identical LLVM IR
#   tests-cpython-0/-1/-2 tests/run.sh with the CPython-hosted compiler, JIT and AOT, each on one of
#                  three disjoint thirds of the corpus (see shard_cases), together the whole of it
#   tests-native-0/-1 tests/run.sh with the stage-2 native compiler, JIT and AOT, each on one of two
#                  disjoint halves of the corpus (shard_cases)
#   tests-opt-off-0/-1 tests/run.sh with the stage-2 compiler and every optimization on the IR turned
#                  off (PYSTACHY_OPT=-all), each on one of two disjoint halves of the corpus
#                  (shard_cases): the passes change no output
#   runtime-cache  tests/cache.sh with both compilers: the cached runtime is used while nothing it is
#                  built from changes, built again when runtime.c, a file it includes from ryu/,
#                  runtime.py, the compiler or a tool changes (also by a same-size edit whose mtime is
#                  set back, or one made while it is built), keyed by the flags too, never left by a
#                  failed build; ext's glue cached beside it; a run's own runtime while a tool is not
#                  settled; PATH's rules
#   python-free-0/-1/-2 PATH holds only symlinks to the LLVM tools, the linker and the POSIX tools
#                  that the driver and tests/run.sh call (no python3): the native compiler rebuilds
#                  its runtime and itself, reproduces the same IR and passes the tests of the shard's
#                  third of the corpus
#   ubsan-0/-1/-2  PYSTACHY_CFLAGS="$UBSAN" (private PYSTACHY_HOME, so a fresh runtime cache): the
#                  compiler built that way reproduces the IR, and every test of the shard's third of the
#                  corpus passes AOT-built with it and JIT-run on the sanitized runtime (lli gets the
#                  UBSan runtime via LD_PRELOAD)
#   check-ir       tools/check_ir.sh: the compiler's IR check (PYSTACHY_IRCHECK=1) and llvm-as accept the
#                  IR of every program of the corpus (the tests, the benchmarks, the tests/ir probes and
#                  the compiler itself) and of runtime.py
#   runtime-table  tools/check_runtime.py: the compiler's RUNTIME table agrees with runtime.c and
#                  runtime.py (types, coverage, and the effects their call graphs show), and no
#                  function of runtime.py reaches itself through runtime.c
#   gc-self        the native compiler collecting every 5000 allocations reproduces the IR
#   gc-jit-*/gc-aot-* every test passes in each mode with a collection at every program allocation
#                  (PYSTACHY_GC_STRESS_PROGRAM=1), compiled by the compiler collecting every 1000;
#                  gc-jit-0/-1 each take one of two disjoint halves of the corpus and gc-aot-0/-1/-2
#                  one of three thirds (shard_cases)
#   benchmarks     bench/*.py print exactly what CPython prints, JIT and AOT; timings recorded
#   rtcheck        tools/rtcheck.py: runtime.py, run by CPython, gives what CPython's str methods and
#                  math functions give on random inputs
#   re-fuzz        tools/re_fuzz.py: lib/re, run by CPython, compiles random patterns to the code and
#                  errors CPython's re does and matches, splits and substitutes as it does, on CPython's
#                  strs and on Pystachy's UTF-8 ones, and so do test_re's cases too big for gc-stress
#   re-probe       tools/re_probe.py: lib/re, run by CPython, enters its matcher and makes contexts no
#                  more often than fixed limits allow for textwrap's patterns (deterministic counts),
#                  with the results of CPython's re
#   rt-abi         tools/rtabi.py: each function runtime.py defines or declares has the same LLVM
#                  signature in runtime.py, runtime.c and every program of the corpus
#   inherited-ast tools/inheritprobe.py: unused inherited methods retain linear AST storage
#   streaming      tools/streamprobe.py: sum(), min() and max() of range() and of generator expressions
#                  take the items as they come: 100,000,000 of them in 64 MiB, AOT
#   ffi            tests/ffi/run.sh with the stage-2 compiler: @ffi.extern's C calls and the FFI's
#                  compile-time errors, then, with $PY's libpython, lib/pyobj.py embedding CPython and
#                  pystachy ext's extension modules, against the twins in tools/rt_cpython (docs/ffi.md)
#   list-storage   tools/listprobe.c: cleared reachable lists release backing capacity and live bytes;
#                  empty operations/reuse preserve sort's sentinel, without allocation in clear
#   container-eq   tools/eqprobe.c: shared DAG comparisons stop within a fixed comparison budget,
#                  including ordering and list searches, normally and with GC stress
#   file-buffers   tools/fileprobe.c: writable files' malloc'd buffers count as heap bytes, so files
#                  dropped without close() run collections; every close takes back exactly what was
#                  counted, a standard stream's are never counted (deterministic counts, no RSS)
#   dict-probes    tools/dictprobe.c: dict lookups visit few table slots for keys that defeat a weak
#                  hash or probe sequence (deterministic counts against a fixed limit, no timings);
#                  the collector scans the key tables of strs and tuples, and none of ints
#   compile-limits tools/compilelimits.py: hosted/native ir/run/build reject growing types,
#                  specialization breadth and the signature bytes specializations retain under
#                  256 MiB / ten CPU seconds, with short diagnostics;
#                  finite controls and reuse at the retained-instance boundary still compile
#   jit-dead-code  tools/jitprobe.py: unused functions never reach lli, and a small helper reaches it
#                  inlined (not with PYSTACHY_JIT_INLINE=0); live code and runtime callbacks still
#                  execute as in CPython, with both compilers
#   unicode-audit  tools/unicode_audit.py: optional byte-boundary checks in JIT/AOT, cache
#                  reuse, ASCII/Unicode controls and GC-stress exception paths, both compilers
#   scaling-0/-1   tools/scaling.py --check: both compilers compile its generated programs (500 and 1000
#                  functions, globals, classes, modules, chained imports, breaks, elifs, ...), and the
#                  lines the CPython-hosted compiler executes, and the items its builtin calls copy or
#                  scan, grow no faster than the programs; scaling-0 checks the shapes of SCALING_0 and
#                  scaling-1 every other one
# A step that runs tests/run.sh over the suite passes only with as many passes as the checks the suite
# holds, counted from its files (checks): a run that covered fewer cases fails.
# usage: tests/verify.sh [GROUP]   (make verify runs all)   env: PY (default python3), PYSTACHY_LLVM (LLVM 18 bin dir)
cd "$(dirname "$0")/.." || exit 1
# shellcheck disable=SC3045 # (ulimit -c is not POSIX, but dash, bash, ksh and busybox have it)
ulimit -c 0 2> /dev/null  # (no core file of a crashing compiler or test program in the tree)
ROOT=$(pwd)
# CI selects independent groups; a local run without arguments still runs every check.
# --list exposes the same plan to the final CI report gate, which rejects missing groups/steps.
plan() {
  case $1 in
    all) echo 'bootstrap tests-cpython-0 tests-cpython-1 tests-cpython-2 tests-native-0 tests-native-1 tests-opt-off-0 tests-opt-off-1 runtime-cache python-free-0 python-free-1 python-free-2 ubsan-0 ubsan-1 ubsan-2 check-ir runtime-table gc-self gc-jit-0 gc-jit-1 gc-aot-0 gc-aot-1 gc-aot-2 benchmarks rtcheck re-fuzz re-probe rt-abi inherited-ast streaming ffi list-storage container-eq file-buffers dict-probes compile-limits jit-dead-code unicode-audit scaling-0 scaling-1' ;;
    hosted-0) echo 'bootstrap tests-cpython-0' ;;
    hosted-1) echo 'bootstrap tests-cpython-1' ;;
    hosted-2) echo 'bootstrap tests-cpython-2' ;;
    hosted) echo 'bootstrap tests-cpython-0 tests-cpython-1 tests-cpython-2' ;; # local alias
    native-0) echo 'bootstrap tests-native-0' ;;
    native-1) echo 'bootstrap tests-native-1' ;;
    native) echo 'bootstrap tests-native-0 tests-native-1' ;; # local alias
    opt-off-0) echo 'bootstrap tests-opt-off-0' ;;
    opt-off-1) echo 'bootstrap tests-opt-off-1' ;;
    opt-off) echo 'bootstrap tests-opt-off-0 tests-opt-off-1' ;; # local alias
    python-free-0) echo 'bootstrap python-free-0' ;;
    python-free-1) echo 'bootstrap python-free-1' ;;
    python-free-2) echo 'bootstrap python-free-2' ;;
    python-free) echo 'bootstrap python-free-0 python-free-1 python-free-2' ;; # local alias (one rebuild for the three thirds)
    ubsan-0) echo 'bootstrap ubsan-0' ;;
    ubsan-1) echo 'bootstrap ubsan-1' ;;
    ubsan-2) echo 'bootstrap ubsan-2' ;;
    ubsan) echo 'bootstrap ubsan-0 ubsan-1 ubsan-2' ;; # local alias (one sanitized build for the three thirds)
    gc-self) echo 'bootstrap gc-self' ;;
    gc-jit-0) echo 'bootstrap gc-jit-0' ;;
    gc-jit-1) echo 'bootstrap gc-jit-1' ;;
    gc-aot-0) echo 'bootstrap gc-aot-0' ;;
    gc-aot-1) echo 'bootstrap gc-aot-1' ;;
    gc-aot-2) echo 'bootstrap gc-aot-2' ;;
    gc-jit) echo 'bootstrap gc-jit-0 gc-jit-1' ;; # local aliases are not CI groups
    gc-aot) echo 'bootstrap gc-aot-0 gc-aot-1 gc-aot-2' ;;
    gc-stress) echo 'bootstrap gc-self gc-jit-0 gc-jit-1 gc-aot-0 gc-aot-1 gc-aot-2' ;;
    runtime-cache) echo 'bootstrap runtime-cache' ;;
    contracts) echo 'bootstrap check-ir runtime-table rtcheck re-fuzz re-probe rt-abi inherited-ast streaming ffi list-storage container-eq file-buffers dict-probes compile-limits jit-dead-code unicode-audit' ;;
    benchmarks) echo 'bootstrap benchmarks scaling-0' ;;
    scaling-1) echo 'bootstrap scaling-1' ;;
    scaling) echo 'bootstrap scaling-0 scaling-1' ;; # local alias
    *) echo "verify: unknown group: $1" >&2; return 2 ;;
  esac
}
[ $# -le 1 ] || { echo 'usage: tests/verify.sh [all|hosted-0|hosted-1|hosted-2|hosted|native-0|native-1|native|opt-off-0|opt-off-1|opt-off|python-free-0|python-free-1|python-free-2|python-free|ubsan-0|ubsan-1|ubsan-2|ubsan|gc-self|gc-jit-0|gc-jit-1|gc-jit|gc-aot-0|gc-aot-1|gc-aot-2|gc-aot|gc-stress|runtime-cache|contracts|benchmarks|scaling-1|scaling|--list]' >&2; exit 2; }
GROUP=${1:-all}
if [ "$GROUP" = --list ]; then
  for g in all hosted-0 hosted-1 hosted-2 native-0 native-1 opt-off-0 opt-off-1 python-free-0 python-free-1 python-free-2 ubsan-0 ubsan-1 ubsan-2 gc-self gc-jit-0 gc-jit-1 gc-aot-0 gc-aot-1 gc-aot-2 runtime-cache contracts benchmarks scaling-1; do
    printf '%s %s\n' "$g" "$(plan "$g")"
  done
  exit 0
fi
SELECTED=$(plan "$GROUP") || exit 2
want() { case " $SELECTED " in *" $1 "*) return 0 ;; *) return 1 ;; esac; }
expected=0
for x in $SELECTED; do expected=$((expected + 1)); done
PY=${PY:-python3}
UBSAN="-fsanitize=undefined -fno-sanitize-recover=all"
V=$ROOT/build/verify
OUT=$ROOT/build/verification.json
rm -rf "$V" "$OUT"
mkdir -p "$V/home" "$V/ubsan-home"
cp runtime.c runtime.py "$V/home/"
cp runtime.c runtime.py "$V/ubsan-home/"
cp -R lib ryu "$V/home/"
cp -R lib ryu "$V/ubsan-home/"
export PYSTACHY_HOME="$ROOT"
# The steps set the knobs they test themselves: one left in the caller's environment would weaken a
# step (PYSTACHY_GC=off: gc-stress collects nothing) or fail it falsely (PYSTACHY_OPT=-all), so they
# are dropped, and the report lists them (PYSTACHY_LLVM and PYSTACHY_JOBS are kept)
ign=$(env | sed -nE 's/^(PYSTACHY_(PATH|CFLAGS|GC|GC_STRESS|GC_STRESS_PROGRAM|IRCHECK|IRFX|OPT|JIT_INLINE|JIT_CODEGEN|UNICODE_AUDIT|ARGV0))=.*$/\1/p' | sort -u)
for e in $ign; do echo "verify: ignoring $e=$(printenv "$e")"; unset "$e"; done
LLVM=${PYSTACHY_LLVM:+${PYSTACHY_LLVM%/}/}

now() { date +%s.%N; }
secs() { awk -v a="$1" -v b="$2" 'BEGIN { printf "%.3f", b - a }'; }
js() { printf '"%s"' "$(printf '%s' "$1" | tr -d '\n' | sed 's/\\/\\\\/g; s/"/\\"/g')"; }
lines() { wc -l < "$1" | tr -d ' '; }
sha() { sha256sum "$1" | cut -c1-64; }
same() { cmp -s "$1" "$2" && echo true || echo false; }
start=$(now); nsteps=0; nfail=0
# step NAME pass|fail START LOG [JSON fields]: append one step to the report
step() {
  t=$(secs "$3" "$(now)")
  [ $nsteps = 0 ] || printf ',\n' >> "$V/steps.json"
  printf '    {"name": "%s", "result": "%s", "seconds": %s, "log": %s%s}' "$1" "$2" "$t" "$(js "${4#"$ROOT"/}")" "$5" >> "$V/steps.json"
  nsteps=$((nsteps + 1))
  printf '%-14s %s  %8ss  %s\n' "$1" "$2" "$t" "${4#"$ROOT"/}"
  [ "$2" = pass ] || { nfail=$((nfail + 1)); tail -15 "$4" | sed 's/^/    | /'; }
}
# checks MODES [FILE...]: checks tests/run.sh makes of these files (default: whole suite) in MODES,
# counted from the files as
# its loops make them: each program and each deviation once per mode, each rejection once, and one
# "pystachy check" more of each syntax_*.py program and of each syntax_*.py rejection whose error is
# in its own file
checks() {
  c=0; m=0
  for x in $1; do m=$((m + 1)); done
  shift
  [ $# != 0 ] || set -- tests/*.py tests/deviations/*.py tests/errors/*.py
  for f; do
    [ -f "$f" ] || continue
    case $f in
      tests/errors/*) c=$((c + 1)) ;;
      *) c=$((c + m)) ;;
    esac
    case $f in
      tests/syntax_*.py) c=$((c + 1)) ;;
      tests/errors/syntax_*.py)
        n=${f##*/}; case $(head -1 "$f") in "# error: ${n%.py}.py:"*) c=$((c + 1)) ;; esac ;;
    esac
  done
  echo $c
}
ALL=$(checks "jit aot")
# shard_cases I N OUT: write the cases of shard I of N to OUT, one per line: the files of the corpus
# whose position in C order is I modulo N, so on every runner the N shards are disjoint and together
# are the whole corpus (rejection and syntax checks included). The C locale is local to the
# selection; programs keep theirs.
shard_cases() {
  (
    export LC_ALL=C
    case_index=0
    for f in tests/*.py tests/deviations/*.py tests/errors/*.py; do
      [ -f "$f" ] || continue
      [ $((case_index % $2)) != "$1" ] || printf '%s\n' "$f"
      case_index=$((case_index + 1))
    done
  ) > "$3"
}
# tests N LOG...: JSON counts summed over tests/run.sh outputs (the "N passed, M failed" line ends
# each log, FAIL lines name the failures); false if anything failed, a log has no summary, or the
# runs passed other than the N checks the suite holds (said on stderr)
tests() {
  np=0; nf=0; fl=""; ok=0; want=$1; shift
  for l; do
    c=$(tail -1 "$l" 2>/dev/null | sed -n 's/^\([0-9]*\) passed, \([0-9]*\) failed$/\1 \2/p')
    [ -n "$c" ] || { ok=1; continue; }
    np=$((np + ${c% *})); nf=$((nf + ${c#* }))
    fl="$fl$(sed -n 's/^FAIL \(.*\)$/\1/p' "$l" | while read -r x; do printf ', %s' "$(js "$x")"; done)"
  done
  printf ', "passed": %s, "failed": %s, "expected": %s, "failures": [%s]' $np $nf "$want" "${fl#, }"
  [ $ok = 0 ] && [ $nf = 0 ] || return 1
  [ $np = "$want" ] || { echo "$np passed, where the suite holds $want checks (tests/verify.sh's checks)" >&2; false; }
}

# ---- bootstrap: fixed point of the self-hosting compiler
L=$V/bootstrap.log; s=$(now); r=fail
{
  $PY pystachy.py build pystachy.py -o "$V/pystachy1" &&
    "$V/pystachy1" build pystachy.py -o "$V/pystachy2" &&
    t0=$(now) && $PY pystachy.py ir pystachy.py -o "$V/stage1.ll" &&
    t1=$(now) && "$V/pystachy1" ir pystachy.py -o "$V/stage2.ll" &&
    t2=$(now) && "$V/pystachy2" ir pystachy.py -o "$V/stage3.ll" && t3=$(now) &&
    cmp "$V/stage1.ll" "$V/stage2.ll" && cmp "$V/stage2.ll" "$V/stage3.ll" &&
    echo "fixed point: stage1 == stage2 == stage3 ($(lines "$V/stage1.ll") lines of IR)" &&
    $PY pystachy.py rt runtime.py -o "$V/rt1.ll" && "$V/pystachy1" rt runtime.py -o "$V/rt2.ll" &&
    "$V/pystachy2" rt runtime.py -o "$V/rt3.ll" && cmp "$V/rt1.ll" "$V/rt2.ll" && cmp "$V/rt2.ll" "$V/rt3.ll" &&
    echo "fixed point: runtime.py's IR, rt1 == rt2 == rt3 ($(lines "$V/rt1.ll") lines)" && r=pass
} > "$L" 2>&1
x=""
[ $r = pass ] && x=$(printf ', "ir_identical": true, "ir_lines": %s, "ir_sha256": "%s", "native_compiler_bytes": %s, "cpython_self_compile_seconds": %s, "native_self_compile_seconds": %s' \
  "$(lines "$V/stage1.ll")" "$(sha "$V/stage1.ll")" "$(wc -c < "$V/pystachy2" | tr -d ' ')" "$(secs "$t0" "$t1")" "$(secs "$t2" "$t3")")
step bootstrap $r "$s" "$L" "$x"

# Self-compilation has its own CI runner; all/local runs can overlap earlier checks.
# Bound it separately from the CI job,
# leaving time to write/upload a failed report. timeout forwards TERM to its process group,
# including the compiler, so cancellation cannot leave the background self-compile running.
gcpid=
cancel_gc() {
  if [ -n "$gcpid" ]; then
    kill "$gcpid" 2> /dev/null
    wait "$gcpid" 2> /dev/null
  fi
  exit 130
}
trap cancel_gc INT TERM
if want gc-self && [ -x "$V/pystachy2" ]; then
  # At 1000, self-compilation spent 23 minutes in 15,543 full-heap collections.
  # 5000 still exercises thousands of collections; the test suite keeps its stronger intervals.
  echo 'gc-self: starting (10-minute limit; build/verify/gc-self.log)'
  timeout --verbose --kill-after=10s 10m sh -c '
    started=$(date +%s)
    echo "gc-self: started $(date -u +%Y-%m-%dT%H:%M:%SZ), limit 10m"
    "$@" & child=$!
    trap '\''kill "$child" 2>/dev/null'\'' INT TERM
    wait "$child"
    status=$?
    # A signal interrupts wait; stay alive until the compiler exits so timeout can
    # escalate to KILL if it ignores TERM, and cancellation reaps it before returning.
    if [ "$status" -gt 128 ]; then wait "$child"; status=$?; fi
    echo "gc-self: finished after $(($(date +%s) - started))s, exit $status"
    exit "$status"
  ' gc-self env PYSTACHY_GC=stats PYSTACHY_GC_STRESS=5000 \
    "$V/pystachy2" ir pystachy.py -o "$V/stage-gc.ll" > "$V/gc-self.log" 2>&1 &
  gcpid=$!
fi

# ---- differential tests with both compilers
# (the CPython-hosted compiler runs as a module, whose bytecode CPython caches, where it compiles a
# compiler's source again at every start; each module is checked by hash, as an
# edit within the same second may keep its mtime and size)
for shard in 0 1 2; do
  want tests-cpython-$shard || continue
  L=$V/tests-cpython-$shard.log; s=$(now); r=fail
  shard_cases $shard 3 "$V/tests-cpython-$shard-cases.log"
  set --
  while IFS= read -r f; do set -- "$@" "$f"; done < "$V/tests-cpython-$shard-cases.log"
  # An empty shard must not silently invoke run.sh's whole-suite default.
  [ $# != 0 ] || { echo 'empty CPython-hosted shard' > "$L"; step tests-cpython-$shard fail "$s" "$L" ""; continue; }
  { $PY -c 'import glob, py_compile as c; [c.compile(p, doraise=True, invalidation_mode=c.PycInvalidationMode.CHECKED_HASH) for p in ["pystachy.py"] + sorted(glob.glob("src/**/*.py", recursive=True))]' &&
    tests/run.sh "$PY -m pystachy" "jit aot" "$@"; } > "$L" 2>&1
  x=$(tests "$(checks "jit aot" "$@")" "$L" 2>> "$L") && r=pass
  step tests-cpython-$shard $r "$s" "$L" ', "compiler": "CPython-hosted", "modes": ["jit", "aot"], "shard_index": '"$shard"', "shard_count": 3'"$x"
done
for shard in 0 1; do
  want tests-native-$shard || continue
  L=$V/tests-native-$shard.log; s=$(now); r=fail
  shard_cases $shard 2 "$V/tests-native-$shard-cases.log"
  set --
  while IFS= read -r f; do set -- "$@" "$f"; done < "$V/tests-native-$shard-cases.log"
  # An empty shard must not silently invoke run.sh's whole-suite default.
  [ $# != 0 ] || { echo 'empty native shard' > "$L"; step tests-native-$shard fail "$s" "$L" ""; continue; }
  tests/run.sh "$V/pystachy2" "jit aot" "$@" > "$L" 2>&1
  x=$(tests "$(checks "jit aot" "$@")" "$L" 2>> "$L") && r=pass
  step tests-native-$shard $r "$s" "$L" ', "compiler": "stage2", "modes": ["jit", "aot"], "shard_index": '"$shard"', "shard_count": 2'"$x"
done
for shard in 0 1; do
  want tests-opt-off-$shard || continue
  L=$V/tests-opt-off-$shard.log; s=$(now); logs=""; offs=""; nl=0
  shard_cases $shard 2 "$V/tests-opt-off-$shard-cases.log"
  set --
  while IFS= read -r f; do set -- "$@" "$f"; done < "$V/tests-opt-off-$shard-cases.log"
  # An empty shard must not silently invoke run.sh's whole-suite default.
  [ $# != 0 ] || { echo 'empty opt-off shard' > "$L"; step tests-opt-off-$shard fail "$s" "$L" ""; continue; }
  # shellcheck disable=SC2043 # (a list of one, for now)
  for o in all; do
    PYSTACHY_OPT=-$o tests/run.sh "$V/pystachy2" "jit aot" "$@" > "$V/tests-opt-off-$shard-$o.log" 2>&1
    logs="$logs $V/tests-opt-off-$shard-$o.log"; offs="$offs, \"-$o\""; nl=$((nl + 1))
  done
  for l in $logs; do echo "== $(basename "$l")"; cat "$l"; done > "$L"
  x=$(tests $((nl * $(checks "jit aot" "$@"))) $logs 2>> "$L") && r=pass || r=fail
  step tests-opt-off-$shard $r "$s" "$L" ', "compiler": "stage2", "modes": ["jit", "aot"], "PYSTACHY_OPT": ['"${offs#, }"'], "shard_index": '"$shard"', "shard_count": 2'"$x"
done

# ---- runtime-cache: the cached runtime's rules, each compiler with a private home (tests/cache.sh,
# whose checks are 58 with the native compiler and 60 with CPython's, including component edits)
if want runtime-cache; then
L=$V/runtime-cache.log; s=$(now)
PY=$PY tests/cache.sh "$V/pystachy2" > "$V/cache-native.log" 2>&1
tests/cache.sh "$PY -m pystachy" > "$V/cache-cpython.log" 2>&1
for l in native cpython; do echo "== $l"; cat "$V/cache-$l.log"; done > "$L"
x=$(tests $((58 + 60)) "$V/cache-native.log" "$V/cache-cpython.log" 2>> "$L") && r=pass || r=fail
step runtime-cache $r "$s" "$L" ', "compilers": ["stage2", "CPython-hosted"]'"$x"
fi

# ---- python-free: the native compiler and the tests with only LLVM + POSIX tools on PATH
# The compiler is rebuilt once; each shard runs its third of the corpus with it.
if want python-free-0 || want python-free-1 || want python-free-2; then
pfs=$(now); PB=$V/python-free-build.log; built=0; py=true
NP=$(mktemp -d "${TMPDIR:-/tmp}/pystachy-path.XXXXXX")
tool() { # tool NAME [DIR]: symlink NAME into $NP, from DIR if given, else from $PATH
  for d in $2 $(echo "$PATH" | tr ':' ' '); do
    [ -x "$d/$1" ] && [ ! -d "$d/$1" ] && { ln -s "$d/$1" "$NP/$1"; return 0; }
  done
  echo "tool not found: $1"; return 1
}
nopy() { env -i PATH="$NP" TMPDIR="${TMPDIR:-/tmp}" PYSTACHY_HOME="$V/home" ${PYSTACHY_LLVM:+PYSTACHY_LLVM="$PYSTACHY_LLVM"} "$@"; }
{
  ok=1
  for t in clang opt lli llvm-link llvm-as; do tool $t "$PYSTACHY_LLVM" || ok=0; done
  # clang's system linker; the driver's shell commands (pystachy run's rmdir too); tests/run.sh; the rm,
  # mkfifo and sleep test programs run; the native-agent example's permission
  # preservation and bounded visible check use chmod and timeout.
  for t in ld sh mkdir mktemp sed mv chmod timeout rm rmdir test cat cmp diff head tail grep dirname basename mkfifo sleep nproc; do tool $t || ok=0; done
  echo "PATH=$NP"; ls -l "$NP" | sed 1d
  if nopy sh -c 'command -v python3 || command -v python'; then ok=0; echo "python is reachable"
  else py=false; echo "python3, python: not found on PATH"; fi
  [ $ok = 1 ] &&
    nopy "$V/pystachy2" build pystachy.py -o "$V/pystachy-nopy" && ls "$V/home/build" &&
    nopy "$V/pystachy-nopy" ir pystachy.py -o "$V/stage-nopy.ll" &&
    cmp "$V/stage1.ll" "$V/stage-nopy.ll" && echo "rebuilt compiler emits the stage1 IR" &&
    nopy "$V/pystachy-nopy" rt runtime.py -o "$V/rt-nopy.ll" && cmp "$V/rt1.ll" "$V/rt-nopy.ll" &&
    echo "rebuilt compiler emits the rt1 IR of runtime.py" && built=1
} > "$PB" 2>&1
pft=$(ls "$NP" | while read -r t; do printf '"%s", ' "$t"; done | sed 's/, $//')
for shard in 0 1 2; do
  want python-free-$shard || continue
  # (the first shard's time includes the rebuild)
  L=$V/python-free-$shard.log; s=${pfs:-$(now)}; pfs=; r=fail; suite_ok=0
  shard_cases $shard 3 "$V/python-free-$shard-cases.log"
  set --
  while IFS= read -r f; do set -- "$@" "$f"; done < "$V/python-free-$shard-cases.log"
  {
    cat "$PB"
    if [ $# = 0 ]; then
      echo 'empty python-free shard'
    elif [ $built = 1 ]; then
      nopy sh tests/run.sh "$V/pystachy-nopy" "jit aot" "$@" && suite_ok=1
    fi
  } > "$L" 2>&1
  x=""
  [ $# = 0 ] || x=$(tests "$(checks "jit aot" "$@")" "$L" 2>> "$L") && [ $suite_ok = 1 ] && r=pass
  step python-free-$shard $r "$s" "$L" "$(printf ', "python_on_path": %s, "path_tools": [%s], "ir_identical": %s, "shard_index": %s, "shard_count": 3' \
    "$py" "$pft" "$(same "$V/stage1.ll" "$V/stage-nopy.ll")" "$shard")$x"
done
rm -rf "$NP"
fi

# ---- ubsan: sanitized runtime in every program, the compiler included
# The sanitized compiler is built once; each shard runs its third of the corpus in both modes.
if want ubsan-0 || want ubsan-1 || want ubsan-2; then
ubs=$(now); UB=$V/ubsan-build.log; built=0
UBSO=$("${LLVM}clang" -print-file-name="libclang_rt.ubsan_standalone-$(uname -m).so")
{
  echo 'int main(void) { return 0; }' | "${LLVM}clang" -x c $UBSAN - -o "$V/ubsan-probe" ||
    { echo "clang cannot link $UBSAN: install the UBSan runtime (Ubuntu: libclang-rt-18-dev)"; false; } &&
    PYSTACHY_HOME="$V/ubsan-home" PYSTACHY_CFLAGS="$UBSAN" "$V/pystachy2" build pystachy.py -o "$V/pystachy-ubsan" &&
    "$V/pystachy-ubsan" ir pystachy.py -o "$V/stage-ubsan.ll" &&
    cmp "$V/stage1.ll" "$V/stage-ubsan.ll" && echo "sanitized compiler emits the stage1 IR" &&
    ls "$V/ubsan-home/build" && test -z "$(grep -L __ubsan_handle "$V"/ubsan-home/build/runtime-*.bc)" &&
    grep -q __ubsan_handle "$V"/ubsan-home/build/runtime-*.bc && echo "cached runtime bitcode is instrumented" && built=1
} > "$UB" 2>&1
for shard in 0 1 2; do
  want ubsan-$shard || continue
  # (the first shard's time includes the sanitized build)
  L=$V/ubsan-$shard.log; s=${ubs:-$(now)}; ubs=; r=fail
  shard_cases $shard 3 "$V/ubsan-$shard-cases.log"
  set --
  while IFS= read -r f; do set -- "$@" "$f"; done < "$V/ubsan-$shard-cases.log"
  {
    cat "$UB"
    if [ $# = 0 ]; then
      echo 'empty UBSan shard'
    elif [ $built = 1 ]; then
      PYSTACHY_HOME="$V/ubsan-home" PYSTACHY_CFLAGS="$UBSAN" tests/run.sh "$V/pystachy-ubsan" aot "$@" > "$V/ubsan-$shard-aot.log" 2>&1
      # (LD_PRELOAD reaches what a program execs too, a shell that kills itself by SIGSEGV say, where
      # UBSan's deadly-signal handler would turn the death into its report and status 1)
      env LD_PRELOAD="$UBSO" UBSAN_OPTIONS="${UBSAN_OPTIONS:+$UBSAN_OPTIONS:}handle_segv=0" PYSTACHY_HOME="$V/ubsan-home" \
        PYSTACHY_CFLAGS="$UBSAN" tests/run.sh "$V/pystachy2" jit "$@" > "$V/ubsan-$shard-jit.log" 2>&1
      for m in aot jit; do echo "-- tests ($m)"; cat "$V/ubsan-$shard-$m.log"; done
    fi
  } > "$L" 2>&1
  x=""
  [ $# = 0 ] || x=$(tests $(($(checks aot "$@") + $(checks jit "$@"))) "$V/ubsan-$shard-aot.log" "$V/ubsan-$shard-jit.log" 2>> "$L") &&
    [ $built = 1 ] && [ $# != 0 ] && r=pass
  step ubsan-$shard $r "$s" "$L" ", \"cflags\": $(js "$UBSAN"), \"modes\": [\"aot\", \"jit\"], \"jit_preload\": $(js "$UBSO"), \"ir_identical\": $(same "$V/stage1.ll" "$V/stage-ubsan.ll"), \"shard_index\": $shard, \"shard_count\": 3$x"
done
fi

# ---- check-ir: the IR of every program of the corpus passes the IR check and is valid LLVM
if want check-ir; then
L=$V/check-ir.log; s=$(now); r=fail
tools/check_ir.sh "$V/pystachy2" > "$L" 2>&1 && r=pass
step check-ir $r "$s" "$L" "$(sed -n 's/^the IR check and llvm-as accept the IR of \([0-9]*\) programs.*$/, "programs": \1/p' "$L")"
fi

# ---- runtime-table: the runtime functions the compiler declares, as runtime.c and runtime.py define them
if want runtime-table; then
L=$V/runtime-table.log; s=$(now); r=fail
$PY tools/check_runtime.py > "$L" 2>&1 && r=pass
step runtime-table $r "$s" "$L" "$(sed -n 's/^\([0-9]*\) RUNTIME entries, \([0-9]*\) exception classes: .*$/, "entries": \1, "exception_classes": \2/p' "$L")"
fi

# ---- gc-self: fixed-point identity under compiler GC stress
if want gc-self; then
L=$V/gc-self-check.log; s=$(now); r=fail
{
  self_ok=0; self_status=127
  if [ -n "$gcpid" ]; then
    echo '-- waiting for bounded GC self-compile (exit 124 means timeout)'
    wait "$gcpid"; self_status=$?
    [ "$self_status" = 0 ] && self_ok=1
    gcpid=  # reaped even on failure: the signal trap must never keep a stale PID
  fi
  # Include the log on failure too: timeout/signal diagnostics must reach the step summary.
  cat "$V/gc-self.log"
  echo "gc-self: exit $self_status"
  [ "$self_ok" = 1 ] &&
    cmp "$V/stage1.ll" "$V/stage-gc.ll" && echo "the compiler collecting every 5000 allocations emits the stage1 IR" &&
    r=pass
} > "$L" 2>&1
step gc-self $r "$s" "$L" ", \"compiler_interval\": 5000, \"ir_identical\": $(same "$V/stage1.ll" "$V/stage-gc.ll")"
fi

# ---- GC-stressed suite: full corpus in both modes, on independent CI runners
# JIT runs as two disjoint shards and AOT as three (shard_cases), whose union is exactly the full
# corpus on every runner; rejection/syntax checks still run in both modes.
for gc_group in gc-jit-0 gc-jit-1 gc-aot-0 gc-aot-1 gc-aot-2; do
  if want "$gc_group"; then
    L=$V/$gc_group.log; s=$(now); r=fail; mode=jit; gc_shards=2; shard=${gc_group##*-}
    case $gc_group in gc-aot-*) mode=aot; gc_shards=3 ;; esac
    shard_cases "$shard" "$gc_shards" "$V/$gc_group-cases.log"
    set --
    while IFS= read -r f; do set -- "$@" "$f"; done < "$V/$gc_group-cases.log"
    # An empty shard must not silently invoke run.sh's whole-suite default.
    [ $# != 0 ] || { echo 'empty GC shard' > "$L"; step "$gc_group" fail "$s" "$L" ""; continue; }
    PYSTACHY_GC_STRESS=1000 PYSTACHY_GC_STRESS_PROGRAM=1 tests/run.sh "$V/pystachy2" "$mode" "$@" > "$L" 2>&1
    suite_status=$?
    x=$(tests "$(checks "$mode" "$@")" "$L" 2>> "$L") && [ "$suite_status" = 0 ] && r=pass
    step "$gc_group" $r "$s" "$L" ", \"tests_interval\": 1, \"tests_compiler_interval\": 1000, \"modes\": [\"$mode\"], \"shard_index\": $shard, \"shard_count\": $gc_shards$x"
  fi
done

# ---- benchmarks: same output as CPython, JIT and AOT
if want benchmarks; then
L=$V/benchmarks.log; s=$(now); r=pass; x=""; n=0; ok=0
: > "$L"
for b in bench/*.py; do
  k=$(basename "$b" .py); n=$((n + 1)); B=$V/bench-$k
  t0=$(now); ($PY "$b"; echo "[exit $?]") > "$B.ref" 2>> "$L"
  t1=$(now); ("$V/pystachy2" run "$b"; echo "[exit $?]") > "$B.jit" 2>> "$L"
  t2=$(now); "$V/pystachy2" build "$b" -o "$B.exe" >> "$L" 2>&1
  t3=$(now); ("$B.exe"; echo "[exit $?]") > "$B.aot" 2>> "$L"
  t4=$(now)
  if cmp -s "$B.ref" "$B.jit" && cmp -s "$B.ref" "$B.aot" && grep -q '^\[exit 0\]$' "$B.ref"; then i=true; ok=$((ok + 1)); echo "ok $k"
  else i=false; r=fail; echo "FAIL $k"; diff "$B.ref" "$B.jit"; diff "$B.ref" "$B.aot"; fi >> "$L"
  x="$x$(printf '%s\n        {"name": "%s", "identical": %s, "cpython_seconds": %s, "jit_seconds": %s, "aot_build_seconds": %s, "aot_seconds": %s}' \
    "${x:+,}" "$k" $i "$(secs "$t0" "$t1")" "$(secs "$t1" "$t2")" "$(secs "$t2" "$t3")" "$(secs "$t3" "$t4")")"
done
step benchmarks $r "$s" "$L" ", \"programs\": $n, \"identical\": $ok, \"timings\": [$x]"
fi

# ---- rtcheck: runtime.py on CPython against CPython's own str methods and math functions
if want rtcheck; then
L=$V/rtcheck.log; s=$(now); r=fail
$PY tools/rtcheck.py > "$L" 2>&1 && r=pass
step rtcheck $r "$s" "$L" "$(sed -n 's/^\([0-9]*\) cases, \([0-9]*\) failed$/, "cases": \1, "failed": \2/p' "$L")"
fi

# ---- re-fuzz: lib/re on CPython against CPython's own re, on random patterns and test_re's largest cases
if want re-fuzz; then
L=$V/re-fuzz.log; s=$(now); r=fail
$PY tools/re_fuzz.py > "$L" 2>&1 && r=pass
step re-fuzz $r "$s" "$L" "$(sed -n 's/^\([0-9]*\) upstream cases and \([0-9]*\) patterns (\([0-9]*\) valid): \([0-9]*\) cases, \([0-9]*\) failed$/, "upstream_cases": \1, "patterns": \2, "valid": \3, "cases": \4, "failed": \5/p' "$L")"
fi

# ---- re-probe: lib/re's matcher entries and contexts for textwrap's patterns, against fixed limits
if want re-probe; then
L=$V/re-probe.log; s=$(now); r=fail
$PY tools/re_probe.py > "$L" 2>&1 && r=pass
step re-probe $r "$s" "$L" "$(sed -n 's/^\([0-9]*\) operations, \([0-9]*\) failed$/, "operations": \1, "failed": \2/p' "$L")"
fi

# ---- rt-abi: one signature per runtime function across runtime.py, runtime.c and the corpus
if want rt-abi; then
L=$V/rt-abi.log; s=$(now); r=fail
$PY tools/rtabi.py "$V/pystachy2" > "$L" 2>&1 && r=pass
step rt-abi $r "$s" "$L" "$(sed -n 's/^\([0-9]*\) functions of runtime.py, \([0-9]*\) uses in runtime.c and \([0-9]*\) programs, \([0-9]*\) mismatches$/, "functions": \1, "uses": \2, "programs": \3, "mismatches": \4/p' "$L")"
fi

# ---- inherited ASTs: declaration headers grow linearly; unused method bodies are shared
if want inherited-ast; then
L=$V/inherited-ast.log; s=$(now); r=fail
$PY tools/inheritprobe.py "$V/pystachy2" > "$L" 2>&1 && r=pass
step inherited-ast $r "$s" "$L" ', "sizes": [80, 160, 320], "native_size": 800, "address_space_mib": 256'
fi

# ---- streaming: sum(), min() and max() of 10^8 items in 64 MiB, which their list would exceed
if want streaming; then
L=$V/streaming.log; s=$(now); r=fail
$PY tools/streamprobe.py "$V/pystachy2" > "$L" 2>&1 && r=pass
step streaming $r "$s" "$L" ', "items": 100000000, "address_space_mib": 64'
fi

# ---- ffi: C functions, CPython embedded, extension modules (docs/ffi.md)
if want ffi; then
L=$V/ffi.log; s=$(now); r=fail
PY=$PY tests/ffi/run.sh "$V/pystachy2" > "$L" 2>&1 && r=pass
step ffi $r "$s" "$L" "$(sed -n 's/^\([0-9]*\) passed, \([0-9]*\) failed.*$/, "passed": \1, "failed": \2/p' "$L")"
fi

# ---- list-storage: deterministic capacity and live-byte checks for reachable empty lists
if want list-storage; then
L=$V/list-storage.log; s=$(now); r=fail
{ "${LLVM}clang" -O2 -S -emit-llvm tools/listprobe.c -o "$V/listprobe.ll" &&
  "${LLVM}llvm-link" "$V/rt1.ll" "$V/listprobe.ll" -o "$V/listprobe.bc" &&
  "${LLVM}clang" -O2 "$V/listprobe.bc" -o "$V/listprobe" -lm &&
  "$V/listprobe" && PYSTACHY_GC_STRESS=1 "$V/listprobe" && r=pass; } > "$L" 2>&1
step list-storage $r "$s" "$L" ', "lists": 64, "historical_slots_per_list": 65536, "live_byte_limit": 1048576'
fi

# ---- container-eq: bounded comparisons for small DAGs with exponentially many logical leaves
if want container-eq; then
L=$V/container-eq.log; s=$(now); r=fail
{ "${LLVM}clang" -O2 -S -emit-llvm tools/eqprobe.c -o "$V/eqprobe.ll" &&
  "${LLVM}llvm-link" "$V/rt1.ll" "$V/eqprobe.ll" -o "$V/eqprobe.bc" &&
  "${LLVM}clang" -O2 "$V/eqprobe.bc" -o "$V/eqprobe" -lm &&
  "$V/eqprobe" && PYSTACHY_GC_STRESS=1 "$V/eqprobe" && r=pass; } > "$L" 2>&1
step container-eq $r "$s" "$L" ', "shared_levels": 32, "comparison_limit": 64'
fi

# ---- file-buffers: dropped files' buffers run collections; opens, closes and the exit balance the counts
if want file-buffers; then
L=$V/file-buffers.log; s=$(now); r=fail
{ "${LLVM}clang" -O2 -S -emit-llvm tools/fileprobe.c -o "$V/fileprobe.ll" &&
  "${LLVM}llvm-link" "$V/rt1.ll" "$V/fileprobe.ll" -o "$V/fileprobe.bc" &&
  "${LLVM}clang" -O2 "$V/fileprobe.bc" -o "$V/fileprobe" -lm &&
  "$V/fileprobe" && "$V/fileprobe" --lib && PYSTACHY_GC_STRESS=1 "$V/fileprobe" && r=pass; } > "$L" 2>&1
step file-buffers $r "$s" "$L" ', "dropped_files": 128, "buffer_bytes": 136314880, "outstanding_limit": 41975808'
fi

# ---- dict-probes: table slots per dict lookup for colliding keys, sequential keys the control
if want dict-probes; then
L=$V/dict-probes.log; s=$(now); r=fail
{ "$V/pystachy2" rt runtime.py -o "$V/dictprobe-rt.ll" && "${LLVM}clang" -O2 -S -emit-llvm tools/dictprobe.c -o "$V/dictprobe.ll" &&
  "${LLVM}llvm-link" "$V/dictprobe-rt.ll" "$V/dictprobe.ll" -o "$V/dictprobe.bc" && "${LLVM}clang" -O2 "$V/dictprobe.bc" -o "$V/dictprobe" -lm &&
  "$V/dictprobe" && PYSTACHY_GC_STRESS=1 "$V/dictprobe" --hash-cache && r=pass; } > "$L" 2>&1
step dict-probes $r "$s" "$L" "$(sed -n 's/^worst average: \([0-9.]*\) slots per lookup (limit \([0-9.]*\))$/, "worst_average_slots": \1, "limit": \2/p' "$L")"
fi

# ---- compile limits: small sources must receive bounded source diagnostics, not exhaust memory
if want compile-limits; then
L=$V/compile-limits.log; s=$(now); r=fail
$PY tools/compilelimits.py -c "hosted=$PY pystachy.py" -c "native=$V/pystachy2" > "$L" 2>&1 && r=pass
step compile-limits $r "$s" "$L" ', "address_space_mib": 256, "cpu_seconds": 10, "modes": ["ir", "run", "build"]'
fi

# ---- JIT dead code: inspect the actual execution module, without a timing threshold
if want jit-dead-code; then
L=$V/jit-dead-code.log; s=$(now); r=fail
$PY tools/jitprobe.py -c "hosted=$PY -m pystachy" -c "native=$V/pystachy2" > "$L" 2>&1 && r=pass
step jit-dead-code $r "$s" "$L" ', "unused_functions": 35, "compilers": ["CPython-hosted", "stage2"]'
fi

# ---- Unicode audit: opt-in checks persist in AOT and do not affect runtime-cache semantics
if want unicode-audit; then
L=$V/unicode-audit.log; s=$(now); r=fail
$PY tools/unicode_audit.py -c "hosted=$PY -m pystachy" -c "native=$V/pystachy2" > "$L" 2>&1 && r=pass
step unicode-audit $r "$s" "$L" ', "compilers": ["CPython-hosted", "stage2"]'
fi

# ---- scaling: compile time grows linearly with generated programs (counts need Python 3.12+)
# scaling-0 checks the shapes of SCALING_0, about half the CPython-hosted compiler's lines that --ops
# counts, and scaling-1 every other shape of tools/scaling.py (-x), so a new shape is checked too.
SCALING_0=chain,modules,stdlib,fields,lookups,elifs,globals,topelifs
for shard in 0 1; do
  want scaling-$shard || continue
  L=$V/scaling-$shard.log; s=$(now); r=fail
  sel=-s; [ $shard = 0 ] || sel=-x
  $PY tools/scaling.py --check --ops "$sel" "$SCALING_0" -n 500,1000 -r 1 -c "hosted=$PY pystachy.py" -c "native=$V/pystachy2" > "$L" 2>&1 && r=pass
  # (the shapes the table shows, in its order)
  shapes=$(sed -n 's/^| \([a-z]*\) | 500 | .*$/"\1"/p' "$L" | paste -sd, -)
  step scaling-$shard $r "$s" "$L" ', "sizes": [500, 1000], "shapes": ['"$shapes"']'
done

# ---- report
complete=true
[ "$nsteps" = "$expected" ] || { complete=false; echo "verify: $nsteps steps ran, expected $expected for $GROUP" >&2; }
ver() { "$@" 2>&1 | head -1; }
{
  printf '{\n  "project": "Pystachy",\n  "result": "%s",\n' "$([ $nfail = 0 ] && [ "$complete" = true ] && echo pass || echo fail)"
  printf '  "group": %s,\n' "$(js "$GROUP")"
  printf '  "summary": {"steps": %s, "passed": %s, "failed": %s, "seconds": %s},\n' $nsteps $((nsteps - nfail)) $nfail "$(secs "$start" "$(now)")"
  printf '  "timestamp_utc": "%s",\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  if c=$(git rev-parse HEAD 2>/dev/null); then d=$([ -z "$(git status --porcelain)" ] && echo false || echo true); else c=unknown; d=null; fi
  printf '  "git": {"commit": %s, "dirty": %s},\n' "$(js "$c")" "$d"
  printf '  "ignored_env": [%s],\n' "$(for e in $ign; do printf ', %s' "$(js "$e")"; done | sed 's/^, //')"
  printf '  "platform": {"system": %s, "machine": %s, "os": %s, "cpu": %s},\n' "$(js "$(uname -sr)")" "$(js "$(uname -m)")" \
    "$(js "$(sed -n 's/^PRETTY_NAME="*\([^"]*\)"*$/\1/p' /etc/os-release 2>/dev/null)")" \
    "$(js "$("${LLVM}opt" --version 2>&1 | sed -n 's/^ *Host CPU: //p')")"
  printf '  "toolchain": {"python": %s, "clang": %s, "llvm": %s, "llvm_dir": %s},\n' "$(js "$(ver $PY --version)")" \
    "$(js "$(ver "${LLVM}clang" --version)")" "$(js "$(ver "${LLVM}opt" --version)")" "$(js "${PYSTACHY_LLVM:-PATH}")"
  SUITE_CHECKS=$ALL MODE_CHECKS=$(checks jit) $PY - <<'PY'
import hashlib
import json
import os
from pathlib import Path
paths = [Path(p) for p in ("pystachy.py", "runtime.c", "runtime.py")]
paths += sorted(Path("src").rglob("*.py"))
sources = {str(p): {"lines": p.read_bytes().count(b"\n"),
                    "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths}
# (suite_checks: the checks of the whole corpus in JIT and AOT, which the shards of each such suite
# make together; mode_checks: its checks in one mode, which the shards of each GC suite make, and
# the UBSan thirds once in each mode)
sources.update(test_programs=len(list(Path("tests").glob("*.py"))),
               rejection_tests=len(list(Path("tests/errors").glob("*.py"))),
               suite_checks=int(os.environ["SUITE_CHECKS"]), mode_checks=int(os.environ["MODE_CHECKS"]))
print('  "sources": ' + json.dumps(sources, sort_keys=True) + ',')
PY
  printf '  "steps": [\n'; cat "$V/steps.json"; printf '\n  ]\n}\n'
} > "$OUT"
echo "verification: $((nsteps - nfail))/$nsteps steps passed -> ${OUT#"$ROOT"/}"
[ $nfail = 0 ] && [ "$complete" = true ]
