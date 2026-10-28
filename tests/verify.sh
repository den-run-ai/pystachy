#!/bin/sh
# Verification harness: every check below runs (a failing step does not stop the others) and the
# results go to build/verification.json -- per step: name, pass/fail, duration, counts -- with the
# toolchain versions, git commit and a timestamp. Exit status 0 only if every step passed.
#   bootstrap      CPython -> stage1 -> stage2 -> stage3 compilers emit identical LLVM IR
#   tests-cpython  the CPython-hosted compiler against stage 2 on every case of the corpus
#                  (tools/irsame.sh): the same IR (`ir`, `rt` for rtmode_*), messages and exit status,
#                  byte for byte, and the same `check` output and status for each syntax_*.py, so that
#                  tests-native's JIT and AOT runs execute exactly what it compiles; a sample (shard 0
#                  of HOSTED_SAMPLE_OF, a program of each hosted_strata kind) runs end to end too, JIT
#                  and AOT
#   tests-native-0/-1/-2 tests/run.sh with the stage-2 native compiler, JIT and AOT, each on one of
#                  three disjoint thirds of the corpus (shard_cases)
#   tests-opt-off-0/-1/-2 tests/run.sh with the stage-2 compiler and every optimization on the IR
#                  turned off (PYSTACHY_OPT=-all), each on one of three disjoint thirds of the corpus
#                  (shard_cases): the passes change no output
#   runtime-cache  tests/cache.sh with both compilers: the cached runtime is used while nothing it is
#                  built from changes, built again when runtime.c, a file it includes from ryu/ or mpz/,
#                  runtime.py, the compiler or a tool changes (also by a same-size edit whose mtime is
#                  set back, or one made while it is built), keyed by the flags too, never left by a
#                  failed build; ext's glue cached beside it; a run's own runtime while a tool is not
#                  settled; PATH's rules
#   python-free-0/-1/-2 PATH holds only symlinks to the LLVM tools, the linker and the POSIX tools
#                  that the driver and tests/run.sh call (no python3): the native compiler rebuilds
#                  its runtime and itself, reproduces the same IR and passes the tests of the shard's
#                  third of the corpus
#   ubsan-0/-1/-2/-3 PYSTACHY_CFLAGS="$UBSAN" (private PYSTACHY_HOME, so a fresh runtime cache): the
#                  compiler built that way reproduces the IR, and every test of the shard's quarter of the
#                  corpus passes AOT-built with it and JIT-run on the sanitized runtime (lli gets the
#                  UBSan runtime via LD_PRELOAD)
#   check-ir       tools/check_ir.sh: the compiler's IR check (PYSTACHY_IRCHECK=1) and llvm-as accept the
#                  IR of every program of the corpus (the tests, the benchmarks, the tests/ir probes and
#                  the compiler itself) and of runtime.py
#   runtime-table  tools/check_runtime.py: the compiler's RUNTIME table agrees with runtime.c and
#                  runtime.py (types, coverage, and the effects their call graphs show), and no
#                  function of runtime.py reaches itself through runtime.c
#   gc-self        the native compiler collecting every 5000 allocations reproduces the IR
#   gc-ir-0/-1     the stage-2 compiler collecting every 1000 allocations compiles each case of one of
#                  two disjoint halves of the corpus (shard_cases), and runtime.py, exactly as stage 2
#                  does unstressed (tools/irsame.sh: the same IR, messages and exit status, byte for
#                  byte), and `check`s each syntax_*.py alike (tools/irsame.sh --check)
#   gc-jit-0/-1, gc-aot-0/-1/-2 every test of the shard passes, JIT (the same halves) or AOT (three
#                  thirds), with a collection at every program allocation (PYSTACHY_GC_STRESS_PROGRAM=1);
#                  one case in GC_SAMPLE_EVERY of the shard, heaviest first (from an offset of each
#                  mode's), runs with the compiler collecting every 1000 too (first, so it builds the
#                  runtime the step's tests use), the shard's other cases compiled by stage 2
#                  unstressed, whose IR gc-ir shows to be the stressed compiler's
#   benchmarks     bench/*.py print exactly what CPython prints, JIT and AOT; timings recorded
#   rtcheck        tools/rtcheck.py: runtime.py, run by CPython, gives what CPython's str methods and
#                  math functions give on random inputs
#   re-fuzz        tools/re_fuzz.py: lib/re, run by CPython, compiles random patterns to the code and
#                  errors CPython's re does and matches, splits and substitutes as it does, on CPython's
#                  strs and on Pystachy's UTF-8 ones, and so do test_re's cases too big for gc-stress
#   dynany-fuzz    tools/dynany_fuzz.py: 3 seeded programs, each with 150 random + 30 typed/Any
#                  parity cases; JIT/AOT, normal and program GC-stressed (sources kept on failure)
#   dynany-optin-0/-1/-2 tests/programs corpus with dynamic Any enabled, fresh CPython
#                  oracle and JIT/AOT; three disjoint shards, exact reviewed exceptions only
#   python-int-optin-0/-1/-2 tests/programs corpus with promoting ints enabled, fresh
#                  CPython oracle and JIT/AOT; three disjoint shards, reviewed exceptions only
#   re-probe       tools/re_probe.py: lib/re, run by CPython, enters its matcher and makes contexts no
#                  more often than fixed limits allow for textwrap's patterns (deterministic counts),
#                  with the results of CPython's re
#   rt-abi         tools/rtabi.py: each function runtime.py defines or declares has the same LLVM
#                  signature in runtime.py, runtime.c and every program of the corpus
#   inherited-ast tools/inheritprobe.py: unused inherited methods retain linear AST storage, and
#                  comparisons of a base's values compile to IR linear in its subclasses
#   streaming      tools/streamprobe.py: sum(), min() and max() of range() and of generator expressions
#                  take the items as they come: 100,000,000 of them in 64 MiB, AOT
#   ffi            tests/ffi/run.sh with the stage-2 compiler: @ffi.extern's C calls and the FFI's
#                  compile-time errors, then, with $PY's libpython, lib/pyobj.py embedding CPython and
#                  pystachy ext's extension modules, against the twins in tools/rt_cpython (docs/ffi.md)
#   list-storage   tools/listprobe.c: cleared reachable lists release backing capacity and live bytes;
#                  empty operations/reuse preserve sort's sentinel, without allocation in clear;
#                  dropped pointer-free large arrays, when most of what is allocated, run
#                  collections every max(4 MiB, live bytes) of them; small objects and arrays
#                  of pointers keep the 32 MiB window
#   container-eq   tools/eqprobe.c: shared DAG comparisons stop within a fixed comparison budget,
#                  including ordering and list searches, normally and with GC stress
#   weakrefs       tools/weakrefprobe.c: true weak targets and dead registry entries are cleared
#                  before sweeping, including cycles, large objects and allocation stress
#   box-slots      tools/boxprobe.c: Any and union boxes take exact 16-byte slots of the right kind;
#                  a pointer to a box's payload keeps it, one past its end does not, with GC stress too
#   file-buffers   tools/fileprobe.c: writable files' malloc'd buffers count as heap bytes, so files
#                  dropped without close() run collections; every close takes back exactly what was
#                  counted, a standard stream's are never counted (deterministic counts, no RSS)
#   select-io      tools/selectprobe.c: real pipe readiness, duplicate descriptors, EOF and EINTR
#                  timeout-deadline/blocking retries, normally and with GC stress
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
#                  reuse, ASCII/Unicode controls and GC-stress exception paths, both compilers;
#                  unicodeprobe checks code-point cache/locality, mutation and GC invalidation
#   scaling-0/-1   tools/scaling.py --check: both compilers compile its generated programs (500 and 1000
#                  functions, globals, classes, modules, chained imports, breaks, elifs, ...), and the
#                  lines the CPython-hosted compiler executes, and the items its builtin calls copy or
#                  scan, grow no faster than the programs; scaling-0 checks the shapes of SCALING_0 and
#                  scaling-1 every other one
# The shards of a suite (shard_cases: tests/corpus.sh's corpus_shard) are disjoint and together the
# whole corpus on every runner, balanced by the weights of tests/case_weights.txt, each heaviest
# first; tests-native, tests-opt-off and ubsan keep each case's time in build/verify/*-times.log,
# from which tools/case_weights.py makes that table.
# A step that runs tests/run.sh over the suite passes only with as many passes as the checks the suite
# holds, counted from its files (checks): a run that covered fewer cases fails.
# usage: tests/verify.sh [GROUP]   (make verify runs all)   env: PY (default python3), PYSTACHY_LLVM (LLVM 18 bin dir)
# CI may set VERIFY_BOOTSTRAP_DIR to a verified bundle from this run; local runs build afresh.
cd "$(dirname "$0")/.." || exit 1
. tests/corpus.sh
# shellcheck disable=SC3045 # (ulimit -c is not POSIX, but dash, bash, ksh and busybox have it)
ulimit -c 0 2> /dev/null  # (no core file of a crashing compiler or test program in the tree)
ROOT=$(pwd)
# CI selects independent groups; a local run without arguments still runs every check.
# --list exposes the same plan to the final CI report gate, which rejects missing groups/steps.
plan() {
  case $1 in
    bootstrap) echo 'bootstrap' ;;
    # (in the order a run of all records them: the contracts' steps, as their lanes report them, after
    # the opt-in sweeps)
    all) echo 'bootstrap tests-cpython tests-native-0 tests-native-1 tests-native-2 tests-opt-off-0 tests-opt-off-1 tests-opt-off-2 runtime-cache python-free-0 python-free-1 python-free-2 ubsan-0 ubsan-1 ubsan-2 ubsan-3 gc-self gc-ir-0 gc-ir-1 gc-jit-0 gc-jit-1 gc-aot-0 gc-aot-1 gc-aot-2 benchmarks dynany-optin-0 dynany-optin-1 dynany-optin-2 python-int-optin-0 python-int-optin-1 python-int-optin-2 check-ir runtime-table rtcheck re-fuzz dynany-fuzz re-probe rt-abi inherited-ast streaming ffi list-storage container-eq weakrefs box-slots file-buffers select-io dict-probes compile-limits jit-dead-code unicode-audit scaling-0 scaling-1' ;;
    hosted) echo 'bootstrap tests-cpython' ;;
    native-0) echo 'bootstrap tests-native-0' ;;
    native-1) echo 'bootstrap tests-native-1' ;;
    native-2) echo 'bootstrap tests-native-2' ;;
    native) echo 'bootstrap tests-native-0 tests-native-1 tests-native-2' ;; # local alias
    opt-off-0) echo 'bootstrap tests-opt-off-0' ;;
    opt-off-1) echo 'bootstrap tests-opt-off-1' ;;
    opt-off-2) echo 'bootstrap tests-opt-off-2' ;;
    opt-off) echo 'bootstrap tests-opt-off-0 tests-opt-off-1 tests-opt-off-2' ;; # local alias
    python-free-0) echo 'bootstrap python-free-0' ;;
    python-free-1) echo 'bootstrap python-free-1' ;;
    python-free-2) echo 'bootstrap python-free-2' ;;
    python-free) echo 'bootstrap python-free-0 python-free-1 python-free-2' ;; # local alias (one rebuild for the three thirds)
    ubsan-0) echo 'bootstrap ubsan-0' ;;
    ubsan-1) echo 'bootstrap ubsan-1' ;;
    ubsan-2) echo 'bootstrap ubsan-2' ;;
    ubsan-3) echo 'bootstrap ubsan-3' ;;
    ubsan) echo 'bootstrap ubsan-0 ubsan-1 ubsan-2 ubsan-3' ;; # local alias (one sanitized build for the four quarters)
    gc-self) echo 'bootstrap gc-self' ;;
    gc-jit-0) echo 'bootstrap gc-ir-0 gc-jit-0' ;;
    gc-jit-1) echo 'bootstrap gc-ir-1 gc-jit-1' ;;
    gc-aot-0) echo 'bootstrap gc-aot-0' ;;
    gc-aot-1) echo 'bootstrap gc-aot-1' ;;
    gc-aot-2) echo 'bootstrap gc-aot-2' ;;
    gc-ir) echo 'bootstrap gc-ir-0 gc-ir-1' ;; # local aliases are not CI groups
    gc-jit) echo 'bootstrap gc-ir-0 gc-ir-1 gc-jit-0 gc-jit-1' ;;
    gc-aot) echo 'bootstrap gc-aot-0 gc-aot-1 gc-aot-2' ;;
    gc-stress) echo 'bootstrap gc-self gc-ir-0 gc-ir-1 gc-jit-0 gc-jit-1 gc-aot-0 gc-aot-1 gc-aot-2' ;;
    runtime-cache) echo 'bootstrap runtime-cache' ;;
    dynany-optin-0|dynany-optin-1|dynany-optin-2) echo "bootstrap $1" ;;
    dynany-optin) echo 'bootstrap dynany-optin-0 dynany-optin-1 dynany-optin-2' ;; # local alias
    python-int-optin-0|python-int-optin-1|python-int-optin-2) echo "bootstrap $1" ;;
    python-int-optin) echo 'bootstrap python-int-optin-0 python-int-optin-1 python-int-optin-2' ;; # local alias
    contracts) echo 'bootstrap check-ir runtime-table rtcheck re-fuzz dynany-fuzz re-probe rt-abi inherited-ast streaming ffi list-storage container-eq weakrefs box-slots file-buffers select-io dict-probes compile-limits jit-dead-code unicode-audit' ;;
    benchmarks) echo 'bootstrap benchmarks' ;;
    scaling) echo 'bootstrap scaling-0 scaling-1' ;;
    *) echo "verify: unknown group: $1" >&2; return 2 ;;
  esac
}
[ $# -le 1 ] || { echo 'usage: tests/verify.sh [all|hosted|native-0|native-1|native-2|native|opt-off-0|opt-off-1|opt-off-2|opt-off|python-free-0|python-free-1|python-free-2|python-free|ubsan-0|ubsan-1|ubsan-2|ubsan-3|ubsan|gc-self|gc-ir|gc-jit-0|gc-jit-1|gc-jit|gc-aot-0|gc-aot-1|gc-aot-2|gc-aot|gc-stress|runtime-cache|dynany-optin-0|dynany-optin-1|dynany-optin-2|dynany-optin|python-int-optin-0|python-int-optin-1|python-int-optin-2|python-int-optin|contracts|benchmarks|scaling|--list]' >&2; exit 2; }
GROUP=${1:-all}
if [ "$GROUP" = --list ]; then
  for g in all bootstrap hosted native-0 native-1 native-2 opt-off-0 opt-off-1 opt-off-2 python-free-0 python-free-1 python-free-2 ubsan-0 ubsan-1 ubsan-2 ubsan-3 gc-self gc-jit-0 gc-jit-1 gc-aot-0 gc-aot-1 gc-aot-2 runtime-cache dynany-optin-0 dynany-optin-1 dynany-optin-2 python-int-optin-0 python-int-optin-1 python-int-optin-2 contracts benchmarks scaling; do
    printf '%s %s\n' "$g" "$(plan "$g")"
  done
  exit 0
fi
SELECTED=$(plan "$GROUP") || exit 2
# a test outside the corpus's areas would be in no step's count (tests/corpus.sh)
strays=$(corpus_strays)
[ -z "$strays" ] || { printf 'tests/verify.sh: no step tests these files, outside the corpus'"'"'s areas:\n%s\n' "$strays" >&2; exit 2; }
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
cp -R lib ryu mpz "$V/home/"
cp -R lib ryu mpz "$V/ubsan-home/"
export PYSTACHY_HOME="$ROOT"
# The steps set the knobs they test themselves: one left in the caller's environment would weaken a
# step (PYSTACHY_GC=off: gc-stress collects nothing) or fail it falsely (PYSTACHY_OPT=-all), so they
# are dropped, and the report lists them (PYSTACHY_LLVM and PYSTACHY_JOBS are kept)
ign=$(env | sed -nE 's/^(PYSTACHY_(PATH|CFLAGS|GC|GC_STRESS|GC_STRESS_PROGRAM|IRCHECK|IRFX|OPT|JIT_INLINE|JIT_CODEGEN|UNICODE_AUDIT|ARGV0|CASE_TIMES))=.*$/\1/p' | sort -u)
for e in $ign; do echo "verify: ignoring $e=$(printenv "$e")"; unset "$e"; done
LLVM=${PYSTACHY_LLVM:+${PYSTACHY_LLVM%/}/}

now() { date +%s.%N; }
secs() { awk -v a="$1" -v b="$2" 'BEGIN { printf "%.3f", b - a }'; }
js() { printf '"%s"' "$(printf '%s' "$1" | tr -d '\n' | sed 's/\\/\\\\/g; s/"/\\"/g')"; }
lines() { wc -l < "$1" | tr -d ' '; }
sha() { sha256sum "$1" | cut -c1-64; }
same() { cmp -s "$1" "$2" && echo true || echo false; }
start=$(now); nsteps=0; nfail=0
# step NAME pass|fail START LOG [JSON fields]: append one step to the report (in a lane of the
# contracts' steps, below, keep it in build/verify/lanes for the shell to append)
step() {
  t=$(secs "$3" "$(now)")
  rec=$(printf '    {"name": "%s", "result": "%s", "seconds": %s, "log": %s%s}' "$1" "$2" "$t" "$(js "${4#"$ROOT"/}")" "$5")
  if [ -n "${lane:-}" ]; then
    printf '%s\n' "$rec" > "$V/lanes/$1.json" && printf '%s %s %s\n' "$2" "$t" "$4" > "$V/lanes/$1.result"
    return
  fi
  record "$1" "$2" "$t" "$4" "$rec"
}
# record NAME pass|fail SECONDS LOG RECORD: append a step's JSON record to the report
record() {
  [ $nsteps = 0 ] || printf ',\n' >> "$V/steps.json"
  printf '%s' "$5" >> "$V/steps.json"
  nsteps=$((nsteps + 1))
  printf '%-14s %s  %8ss  %s\n' "$1" "$2" "$3" "${4#"$ROOT"/}"
  [ "$2" = pass ] || { nfail=$((nfail + 1)); tail -15 "$4" | sed 's/^/    | /'; }
}
# checks MODES [FILE...]: checks tests/run.sh makes of these files (default: whole suite) in MODES,
# counted from the files as
# its loops make them: each program and each deviation once per mode, each rejection once, and one
# "pystachy check" more of each program syntax_*.py and of each rejection syntax_*.py whose error is
# in its own file
checks() {
  c=0; m=0
  for x in $1; do m=$((m + 1)); done
  shift
  if [ $# = 0 ]; then
    corpus > "$V/corpus.list"
    while IFS= read -r f; do set -- "$@" "$f"; done < "$V/corpus.list"
  fi
  for f; do
    [ -f "$f" ] || continue
    n=${f##*/}
    case $f in
      tests/errors/*/*) c=$((c + 1)) ;;
      *) c=$((c + m)) ;;
    esac
    case $f:$n in
      tests/programs/*:syntax_*.py) c=$((c + 1)) ;;
      tests/errors/*/*:syntax_*.py)
        case $(head -1 "$f") in "# error: ${n%.py}.py:"*) c=$((c + 1)) ;; esac ;;
    esac
  done
  echo $c
}
ALL=$(checks "jit aot")
# shard_cases I N OUT: write the cases of shard I of N to OUT, one per line, heaviest first
# (tests/corpus.sh's corpus_shard): on every runner the N shards are disjoint and together are the
# whole corpus (rejection and syntax checks included), balanced by tests/case_weights.txt, which can
# change which shard runs a case but never whether one does. The C locale is local to the selection;
# programs keep theirs.
shard_cases() { corpus_shard "$1" "$2" > "$3"; }
# sample_cases I N OUT: write to OUT the cases whose position in C order is I modulo N, spread evenly
# over the areas (tests-cpython's end-to-end sample)
sample_cases() {
  (
    export LC_ALL=C
    case_index=0
    corpus > "$3.all"
    while IFS= read -r f; do
      [ $((case_index % $2)) != "$1" ] || printf '%s\n' "$f"
      case_index=$((case_index + 1))
    done < "$3.all"
    rm -f "$3.all"
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
if [ -n "${VERIFY_BOOTSTRAP_DIR:-}" ]; then
  # Never fall back silently: a corrupt or stale bundle is a verification failure.
  [ "$GROUP" != bootstrap ] && [ "$GROUP" != all ] || {
    echo 'verify: bootstrap and all must build their own fixed point' >&2; exit 2;
  }
  if ! $PY tools/verification_bootstrap.py restore "$VERIFY_BOOTSTRAP_DIR" > "$V/bootstrap-restore.log" 2>&1; then
    cat "$V/bootstrap-restore.log" >&2
    exit 1
  fi
  x=$($PY -c 'import json,sys; d=json.load(open(sys.argv[1])); print(", " + json.dumps(d)[1:-1])' "$V/bootstrap-reuse.json") || exit 1
  step bootstrap pass "$s" "$V/bootstrap-restore.log" "$x"
else
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
fi

# Self-compilation has its own CI runner; all/local runs can overlap earlier checks.
# Bound it separately from the CI job,
# leaving time to write/upload a failed report. timeout forwards TERM to its process group,
# including the compiler, so cancellation cannot leave the background self-compile running.
gcpid=
# jobtree PID...: those of the PIDs that are still this shell's children, and every process below them,
# from one listing of each process's parent (POSIX ps; without it, the PIDs alone)
jobtree() {
  { ps -A -o pid= -o ppid= 2> /dev/null || for p; do echo "$p $$"; done; } | awk -v shell=$$ -v roots="$*" '
    BEGIN { n = split(roots, r, " "); for (i = 1; i <= n; i++) root[r[i]] = 1 }
    { parent[$1] = $2 }
    END {
      for (p in parent) if ((p in root) && parent[p] == shell) tree[p] = 1
      do { more = 0; for (p in parent) if (!(p in tree) && (parent[p] in tree)) { tree[p] = 1; more = 1 } } while (more)
      for (p in tree) print p
    }'
}
# stop_jobs PID...: end these background jobs and every process they started. TERM to a job alone
# would leave its programs running, and SIGINT reaches none of them (a background job of a shell
# without job control ignores it, as do the programs it runs), so each process of their trees is
# stopped while a listing finds one not yet stopped (a stopped process starts no other), then sent
# TERM and CONT; then the jobs are reaped.
stop_jobs() {
  stopped=" "
  while :; do
    new=$(jobtree "$@" | while read -r p; do case $stopped in (*" $p "*) ;; (*) printf '%s ' "$p" ;; esac; done)
    [ -n "$new" ] || break
    # shellcheck disable=SC2086 # (a list of PIDs)
    kill -STOP $new 2> /dev/null
    stopped="$stopped$new"
  done
  # shellcheck disable=SC2086 # (a list of PIDs)
  [ "$stopped" = " " ] || { kill -TERM $stopped; kill -CONT $stopped; } 2> /dev/null
  for p; do wait "$p" 2> /dev/null; done
}
# bgjobs: 1 where ps lists this shell's processes, as jobtree needs to find what a job started; without
# it the background jobs below (runtime-cache's native run, the contracts' runtime builds and lanes) run
# in the foreground instead, one after another, as every other step does, which a Ctrl-C reaches
bgjobs=
if ps -A -o pid= -o ppid= 2> /dev/null | awk -v shell=$$ '$1 == shell { found = 1 } END { exit !found }'; then
  bgjobs=1
else
  echo 'verify: ps lists no processes here: the steps that run side by side run one after another'
fi
cancel_gc() {
  if [ -n "$gcpid" ]; then
    kill "$gcpid" 2> /dev/null
    wait "$gcpid" 2> /dev/null
  fi
  # shellcheck disable=SC2086 # (lists of PIDs)
  stop_jobs ${warmpid:-} ${lanepids:-} ${cachepid:-}
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
# tests-cpython: the CPython-hosted compiler must compile every case of the corpus exactly as stage 2
# does (tools/irsame.sh: `ir`, or `rt` for rtmode_*, with the IR check on as tests/run.sh has it; the
# IR byte for byte, every message and the exit status), and `check` each syntax_*.py alike
# (tools/irsame.sh --check), each comparison in a worker per CPU. Where the
# IR is the same, the LLVM tools build the same program from it, which tests-native runs JIT and AOT
# for every case: running it again here would add nothing; a rejection's message is the one
# tests-native checks. A sample still runs end to end with the hosted compiler, JIT and AOT, so that
# its driver's run, build and check paths after the IR run in this job too (as they do in
# runtime-cache, jit-dead-code, unicode-audit and compile-limits): the cases of shard 0 of
# HOSTED_SAMPLE_OF (sample_cases), and the first program of each kind that hosted_strata names.
# (the CPython-hosted compiler runs as a module, whose bytecode CPython caches, where it compiles a
# compiler's source again at every start; each module is checked by hash, as an
# edit within the same second may keep its mtime and size)
HOSTED_SAMPLE_OF=64
# hosted_strata CASES: KIND CASE for each kind of program whose run takes the hosted driver past the IR
# along a path of its own, CASE the first program of that kind in the list CASES (none if there is
# none): sigint, one that sends itself SIGINT (of tests/run.sh's SIG cases); full, one with NAME.full
# (stdout /dev/full); in, one with NAME.in (stdin); path, one with NAME.path (PYSTACHY_PATH); ffi, one
# that imports a module named ffi (the driver's own, unless the program's path holds one).
# tools/merge_verification.py's HOSTED_STRATA tests the kinds alike.
hosted_strata() {
  list=$1
  set --
  while IFS= read -r f; do case $f in tests/programs/*) set -- "$@" "$f" ;; esac; done < "$list"
  for kind in sigint full in path ffi; do
    first=
    [ $# = 0 ] || first=$(
      case $kind in
        (sigint) grep -l 'kill -INT' "$@" ;;
        (ffi) grep -lE '^(import|from) ffi( |$)' "$@" ;;
        (*) for f; do [ ! -f "${f%.py}.$kind" ] || printf '%s\n' "$f"; done ;;
      esac | sed -n 1p)
    printf '%s %s\n' "$kind" "${first:-none}"
  done
}
if want tests-cpython; then
  L=$V/tests-cpython.log; s=$(now); r=fail; ir_ok=false; ir_n=0; chk_ok=false; x=""
  # (in C order, in which the strata's programs are the first of their kind)
  (LC_ALL=C; export LC_ALL; corpus) > "$V/tests-cpython-cases.log"
  hosted_strata "$V/tests-cpython-cases.log" > "$V/tests-cpython-strata.log"
  sample_cases 0 $HOSTED_SAMPLE_OF "$V/tests-cpython-shard.log"
  # the sample: shard 0's cases and the strata's programs, once each, in the corpus's order
  sed 's/^[a-z]* //' "$V/tests-cpython-strata.log" | cat "$V/tests-cpython-shard.log" - > "$V/tests-cpython-want.log"
  grep -Fx -f "$V/tests-cpython-want.log" "$V/tests-cpython-cases.log" > "$V/tests-cpython-sample.log"
  grep '/syntax_[^/]*\.py$' "$V/tests-cpython-cases.log" > "$V/tests-cpython-syntax.log"
  chk_n=$(lines "$V/tests-cpython-syntax.log")
  set --
  while IFS= read -r f; do set -- "$@" "$f"; done < "$V/tests-cpython-cases.log"
  cases=$#
  {
    $PY -c 'import glob, py_compile as c; [c.compile(p, doraise=True, invalidation_mode=c.PycInvalidationMode.CHECKED_HASH) for p in ["pystachy.py"] + sorted(glob.glob("src/**/*.py", recursive=True))]' || cases=0
    # An empty corpus must not silently invoke irsame's or run.sh's whole-corpus default.
    if [ "$cases" != 0 ]; then
      echo "== IR, messages and exit status of $cases cases: stage 2, then CPython-hosted (tools/irsame.sh)"
      PYSTACHY_IRCHECK=1 tools/irsame.sh "$V/pystachy2" "$PY -m pystachy" "$@" > "$V/tests-cpython-ir.log" 2>&1
      st=$?; cat "$V/tests-cpython-ir.log"
      ir_n=$(tail -1 "$V/tests-cpython-ir.log" | sed -n 's/^\([0-9]*\) programs identical$/\1/p')
      [ $st = 0 ] && [ "${ir_n:-0}" = "$cases" ] && ir_ok=true
      set --
      while IFS= read -r f; do set -- "$@" "$f"; done < "$V/tests-cpython-syntax.log"
      if [ $# != 0 ]; then
        echo "== check of the $# syntax_*.py cases: stage 2, then CPython-hosted (tools/irsame.sh --check)"
        tools/irsame.sh --check "$V/pystachy2" "$PY -m pystachy" "$@" > "$V/tests-cpython-check.log" 2>&1
        st=$?; cat "$V/tests-cpython-check.log"
        n=$(tail -1 "$V/tests-cpython-check.log" | sed -n 's/^\([0-9]*\) programs identical$/\1/p')
        [ $st = 0 ] && [ "${n:-0}" = "$chk_n" ] && chk_ok=true
      else
        echo 'no syntax_*.py case to check'
      fi
    else
      echo 'no CPython-hosted cases (an empty corpus, or the compiler did not byte-compile)'
    fi
  } > "$L" 2>&1
  set --
  while IFS= read -r f; do set -- "$@" "$f"; done < "$V/tests-cpython-sample.log"
  {
    echo "== end to end, JIT and AOT: the $# cases of shard 0 of $HOSTED_SAMPLE_OF and the first program of each kind"
    sed 's/^/  /' "$V/tests-cpython-strata.log"
  } >> "$L"
  strata_ok=true
  ! grep -q ' none$' "$V/tests-cpython-strata.log" || { strata_ok=false; echo 'a kind without a program' >> "$L"; }
  if [ $# != 0 ] && [ "$cases" != 0 ]; then
    tests/run.sh "$PY -m pystachy" "jit aot" "$@" > "$V/tests-cpython-run.log" 2>&1
    cat "$V/tests-cpython-run.log" >> "$L"
    x=$(tests "$(checks "jit aot" "$@")" "$V/tests-cpython-run.log" 2>> "$L") && [ $ir_ok = true ] && [ $chk_ok = true ] &&
      [ "$chk_n" != 0 ] && [ $strata_ok = true ] && r=pass
  else
    echo 'empty CPython-hosted sample' >> "$L"
  fi
  sample=$(for f; do printf ', %s' "$(js "$f")"; done)
  strata=$(while read -r k f; do
    if [ "$f" = none ]; then printf ', "%s": null' "$k"; else printf ', "%s": %s' "$k" "$(js "$f")"; fi
  done < "$V/tests-cpython-strata.log")
  step tests-cpython $r "$s" "$L" ', "compiler": "CPython-hosted", "reference": "stage2", "ir_cases": '"${ir_n:-0}"', "ir_identical": '"$ir_ok"', "check_cases": '"$chk_n"', "check_identical": '"$chk_ok"', "modes": ["jit", "aot"], "sample_index": 0, "sample_count": '"$HOSTED_SAMPLE_OF"', "sample_cases": '"$#"', "sample": ['"${sample#, }"'], "sample_strata": {'"${strata#, }"'}'"$x"
fi
for shard in 0 1 2; do
  want tests-native-$shard || continue
  L=$V/tests-native-$shard.log; s=$(now); r=fail
  shard_cases $shard 3 "$V/tests-native-$shard-cases.log"
  set --
  while IFS= read -r f; do set -- "$@" "$f"; done < "$V/tests-native-$shard-cases.log"
  # An empty shard must not silently invoke run.sh's whole-suite default.
  [ $# != 0 ] || { echo 'empty native shard' > "$L"; step tests-native-$shard fail "$s" "$L" ""; continue; }
  PYSTACHY_CASE_TIMES="$V/tests-native-$shard-times.log" tests/run.sh "$V/pystachy2" "jit aot" "$@" > "$L" 2>&1
  x=$(tests "$(checks "jit aot" "$@")" "$L" 2>> "$L") && r=pass
  step tests-native-$shard $r "$s" "$L" ', "compiler": "stage2", "modes": ["jit", "aot"], "shard_index": '"$shard"', "shard_count": 3'"$x"
done
for shard in 0 1 2; do
  want tests-opt-off-$shard || continue
  L=$V/tests-opt-off-$shard.log; s=$(now); logs=""; offs=""; nl=0
  shard_cases $shard 3 "$V/tests-opt-off-$shard-cases.log"
  set --
  while IFS= read -r f; do set -- "$@" "$f"; done < "$V/tests-opt-off-$shard-cases.log"
  # An empty shard must not silently invoke run.sh's whole-suite default.
  [ $# != 0 ] || { echo 'empty opt-off shard' > "$L"; step tests-opt-off-$shard fail "$s" "$L" ""; continue; }
  # shellcheck disable=SC2043 # (a list of one, for now)
  for o in all; do
    PYSTACHY_OPT=-$o PYSTACHY_CASE_TIMES="$V/tests-opt-off-$shard-$o-times.log" \
      tests/run.sh "$V/pystachy2" "jit aot" "$@" > "$V/tests-opt-off-$shard-$o.log" 2>&1
    logs="$logs $V/tests-opt-off-$shard-$o.log"; offs="$offs, \"-$o\""; nl=$((nl + 1))
  done
  for l in $logs; do echo "== $(basename "$l")"; cat "$l"; done > "$L"
  x=$(tests $((nl * $(checks "jit aot" "$@"))) $logs 2>> "$L") && r=pass || r=fail
  step tests-opt-off-$shard $r "$s" "$L" ', "compiler": "stage2", "modes": ["jit", "aot"], "PYSTACHY_OPT": ['"${offs#, }"'], "shard_index": '"$shard"', "shard_count": 3'"$x"
done

# ---- runtime-cache: the cached runtime's rules, each compiler with a private home (tests/cache.sh,
# whose checks are 66 with the native compiler and 68 with CPython's, including mpz/component edits and,
# on Linux, which verification runs on, the JIT tier's shared library)
# Each run has its own home, LLVM wrappers and directory ($TMPDIR/pystachy-cache.PID) and builds the
# runtime in one process at a time, so the two run side by side (the native one as a background job:
# neither sends SIGINT, which a background job would ignore; one after another without bgjobs)
if want runtime-cache; then
L=$V/runtime-cache.log; s=$(now)
if [ -n "$bgjobs" ]; then
  PY=$PY tests/cache.sh "$V/pystachy2" > "$V/cache-native.log" 2>&1 &
  cachepid=$!
else
  PY=$PY tests/cache.sh "$V/pystachy2" > "$V/cache-native.log" 2>&1
fi
tests/cache.sh "$PY -m pystachy" > "$V/cache-cpython.log" 2>&1
[ -z "${cachepid:-}" ] || wait "$cachepid"; cachepid=
for l in native cpython; do echo "== $l"; cat "$V/cache-$l.log"; done > "$L"
x=$(tests $((66 + 68)) "$V/cache-native.log" "$V/cache-cpython.log" 2>> "$L") && r=pass || r=fail
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
# The sanitized compiler is built once; each shard runs its quarter of the corpus in both modes.
if want ubsan-0 || want ubsan-1 || want ubsan-2 || want ubsan-3; then
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
for shard in 0 1 2 3; do
  want ubsan-$shard || continue
  # (the first shard's time includes the sanitized build)
  L=$V/ubsan-$shard.log; s=${ubs:-$(now)}; ubs=; r=fail
  shard_cases $shard 4 "$V/ubsan-$shard-cases.log"
  set --
  while IFS= read -r f; do set -- "$@" "$f"; done < "$V/ubsan-$shard-cases.log"
  {
    cat "$UB"
    if [ $# = 0 ]; then
      echo 'empty UBSan shard'
    elif [ $built = 1 ]; then
      PYSTACHY_HOME="$V/ubsan-home" PYSTACHY_CFLAGS="$UBSAN" PYSTACHY_CASE_TIMES="$V/ubsan-$shard-aot-times.log" \
        tests/run.sh "$V/pystachy-ubsan" aot "$@" > "$V/ubsan-$shard-aot.log" 2>&1
      # (LD_PRELOAD reaches what a program execs too, a shell that kills itself by SIGSEGV say, where
      # UBSan's deadly-signal handler would turn the death into its report and status 1)
      env LD_PRELOAD="$UBSO" UBSAN_OPTIONS="${UBSAN_OPTIONS:+$UBSAN_OPTIONS:}handle_segv=0" PYSTACHY_HOME="$V/ubsan-home" \
        PYSTACHY_CFLAGS="$UBSAN" PYSTACHY_CASE_TIMES="$V/ubsan-$shard-jit-times.log" tests/run.sh "$V/pystachy2" jit "$@" \
        > "$V/ubsan-$shard-jit.log" 2>&1
      for m in aot jit; do echo "-- tests ($m)"; cat "$V/ubsan-$shard-$m.log"; done
    fi
  } > "$L" 2>&1
  x=""
  [ $# = 0 ] || x=$(tests $(($(checks aot "$@") + $(checks jit "$@"))) "$V/ubsan-$shard-aot.log" "$V/ubsan-$shard-jit.log" 2>> "$L") &&
    [ $built = 1 ] && [ $# != 0 ] && r=pass
  step ubsan-$shard $r "$s" "$L" ", \"cflags\": $(js "$UBSAN"), \"modes\": [\"aot\", \"jit\"], \"jit_preload\": $(js "$UBSO"), \"ir_identical\": $(same "$V/stage1.ll" "$V/stage-ubsan.ll"), \"shard_index\": $shard, \"shard_count\": 4$x"
done
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

# ---- GC stress: the stressed compiler's output, then the corpus in both modes, on independent CI runners
# gc-ir-0/-1: stage 2 collecting every GC_COMPILER_INTERVAL allocations must compile each case of one
# of two disjoint halves of the corpus (shard_cases) exactly as stage 2 does unstressed (tools/irsame.sh:
# `ir`, or `rt` for rtmode_*, with the IR check on as tests/run.sh has it; the IR byte for byte, every
# message and the exit status), runtime.py too (`rt`), and `check` each syntax_*.py alike
# (tools/irsame.sh --check): the two halves compile every case once a run with the stressed compiler.
# Where the IR is the same, the LLVM tools build the same program from it, so gc-jit-0/-1 (the same
# halves, JIT) and gc-aot-0/-1/-2 (three thirds, AOT) run their shard's cases with a collection at every
# program allocation (PYSTACHY_GC_STRESS_PROGRAM=1), compiled by stage 2 unstressed: compiling each case
# under stress again for each mode added nothing but time. A sample of each shard runs end to end with
# the compiler stressed too, so that the driver's paths after the IR run under stress: the runtime's
# build and cache (the sample runs first, in a cache of the GC steps' own that each run starts empty,
# so the stressed compiler builds the runtime every GC test of the run uses), opt and lli (JIT), clang
# and the link (AOT); the program-stressed run takes the shard's other cases, so each case runs exactly
# once in each mode.
# The sample is the cases at positions GC_JIT_SAMPLE_OFFSET (JIT) or GC_AOT_SAMPLE_OFFSET (AOT) modulo
# GC_SAMPLE_EVERY of the shard as shard_cases lists it, heaviest first: drawn from the job's own shard,
# it lies in that shard whatever tests/case_weights.txt does to the shards, and it is the same on every
# runner, as the shard is (corpus_shard: integer weights, the C locale). Every 16th case in weight order
# gives each job's sample about a sixteenth of its shard's weight (0.94-1.03 of it at offsets 4 to 12
# on the measured weights, where every 16th case in C order gave 0.68-1.47), so the stressed compiler's
# cost does not depend on which heavy cases a sample happens to draw. Offset 0 would put each shard's
# heaviest case in every sample; JIT's and AOT's offsets lie half a period apart, so that the modes,
# whose shards differ, stress different cases where their orders agree.
GC_COMPILER_INTERVAL=1000
GC_SAMPLE_EVERY=16
GC_JIT_SAMPLE_OFFSET=4
GC_AOT_SAMPLE_OFFSET=12
for shard in 0 1; do
  want gc-ir-$shard || continue
  L=$V/gc-ir-$shard.log; s=$(now); r=fail; ir_ok=false; ir_n=0; rt_ok=false; chk_ok=false
  shard_cases $shard 2 "$V/gc-ir-$shard-cases.log"
  grep '/syntax_[^/]*\.py$' "$V/gc-ir-$shard-cases.log" > "$V/gc-ir-$shard-syntax.log"
  chk_n=$(lines "$V/gc-ir-$shard-syntax.log")
  set --
  while IFS= read -r f; do set -- "$@" "$f"; done < "$V/gc-ir-$shard-cases.log"
  cases=$#
  {
    # An empty shard must not silently invoke irsame's whole-corpus default.
    if [ "$cases" != 0 ]; then
      echo "== runtime.py: stage 2, then stage 2 collecting every $GC_COMPILER_INTERVAL allocations (tools/irsame.sh)"
      PYSTACHY_IRCHECK=1 tools/irsame.sh "$V/pystachy2" "env PYSTACHY_GC_STRESS=$GC_COMPILER_INTERVAL $V/pystachy2" runtime.py \
        > "$V/gc-ir-$shard-rt.log" 2>&1
      st=$?; cat "$V/gc-ir-$shard-rt.log"
      [ $st = 0 ] && [ "$(tail -1 "$V/gc-ir-$shard-rt.log")" = '1 programs identical' ] && rt_ok=true
      echo "== IR, messages and exit status of $cases cases: stage 2, then stressed (tools/irsame.sh)"
      PYSTACHY_IRCHECK=1 tools/irsame.sh "$V/pystachy2" "env PYSTACHY_GC_STRESS=$GC_COMPILER_INTERVAL $V/pystachy2" "$@" \
        > "$V/gc-ir-$shard-ir.log" 2>&1
      st=$?; cat "$V/gc-ir-$shard-ir.log"
      ir_n=$(tail -1 "$V/gc-ir-$shard-ir.log" | sed -n 's/^\([0-9]*\) programs identical$/\1/p')
      [ $st = 0 ] && [ "${ir_n:-0}" = "$cases" ] && ir_ok=true
      set --
      while IFS= read -r f; do set -- "$@" "$f"; done < "$V/gc-ir-$shard-syntax.log"
      if [ $# != 0 ]; then
        echo "== check of the $# syntax_*.py cases: stage 2, then stressed (tools/irsame.sh --check)"
        tools/irsame.sh --check "$V/pystachy2" "env PYSTACHY_GC_STRESS=$GC_COMPILER_INTERVAL $V/pystachy2" "$@" \
          > "$V/gc-ir-$shard-check.log" 2>&1
        st=$?; cat "$V/gc-ir-$shard-check.log"
        n=$(tail -1 "$V/gc-ir-$shard-check.log" | sed -n 's/^\([0-9]*\) programs identical$/\1/p')
        [ $st = 0 ] && [ "${n:-0}" = "$chk_n" ] && chk_ok=true
      else
        echo 'no syntax_*.py case in this half'; chk_ok=true
      fi
    else
      echo 'empty GC identity shard'
    fi
  } > "$L" 2>&1
  [ $ir_ok = true ] && [ $rt_ok = true ] && [ $chk_ok = true ] && r=pass
  step gc-ir-$shard $r "$s" "$L" ", \"compiler_interval\": $GC_COMPILER_INTERVAL, \"reference\": \"stage2\", \"ir_cases\": ${ir_n:-0}, \"ir_identical\": $ir_ok, \"runtime_identical\": $rt_ok, \"check_cases\": $chk_n, \"check_identical\": $chk_ok, \"shard_index\": $shard, \"shard_count\": 2"
done
for gc_group in gc-jit-0 gc-jit-1 gc-aot-0 gc-aot-1 gc-aot-2; do
  want "$gc_group" || continue
  L=$V/$gc_group.log; s=$(now); r=fail; mode=jit; gc_shards=2; offset=$GC_JIT_SAMPLE_OFFSET; shard=${gc_group##*-}
  sample_ok=0; y=""
  case $gc_group in gc-aot-*) mode=aot; gc_shards=3; offset=$GC_AOT_SAMPLE_OFFSET ;; esac
  shard_cases "$shard" "$gc_shards" "$V/$gc_group-shard.log"
  shard_n=$(lines "$V/$gc_group-shard.log")
  # (in one pass over the shard, each case to exactly one of the two: the sample, or the others)
  : > "$V/$gc_group-sample-cases.log"
  awk -v every=$GC_SAMPLE_EVERY -v offset="$offset" -v sample="$V/$gc_group-sample-cases.log" \
    '(NR - 1) % every == offset { print > sample; next } { print }' "$V/$gc_group-shard.log" > "$V/$gc_group-cases.log"
  set --
  while IFS= read -r f; do set -- "$@" "$f"; done < "$V/$gc_group-sample-cases.log"
  sample_n=$#
  # Empty selections must not silently invoke run.sh's whole-suite default.
  if [ $# != 0 ]; then
    PYSTACHY_CACHE="$V/gc-cache" PYSTACHY_GC_STRESS=$GC_COMPILER_INTERVAL PYSTACHY_GC_STRESS_PROGRAM=1 \
      tests/run.sh "$V/pystachy2" "$mode" "$@" > "$V/$gc_group-sample.log" 2>&1 && sample_ok=1
    y=$(tests "$(checks "$mode" "$@")" "$V/$gc_group-sample.log" 2>> "$V/$gc_group-sample.log") || sample_ok=0
  else
    echo 'empty GC sample' > "$V/$gc_group-sample.log"
  fi
  { echo "== $mode, compiler and program GC-stressed: the $# cases at positions $offset modulo $GC_SAMPLE_EVERY of shard $shard of $gc_shards ($shard_n cases, heaviest first)"
    cat "$V/$gc_group-sample.log"; } > "$L"
  set --
  while IFS= read -r f; do set -- "$@" "$f"; done < "$V/$gc_group-cases.log"
  [ $# != 0 ] || { echo 'empty GC shard' >> "$L"; step "$gc_group" fail "$s" "$L" ""; continue; }
  echo "== $mode, program GC-stressed: the shard's other $# cases" >> "$L"
  PYSTACHY_CACHE="$V/gc-cache" PYSTACHY_GC_STRESS_PROGRAM=1 tests/run.sh "$V/pystachy2" "$mode" "$@" > "$V/$gc_group-suite.log" 2>&1
  suite_status=$?
  cat "$V/$gc_group-suite.log" >> "$L"
  x=$(tests "$(checks "$mode" "$@")" "$V/$gc_group-suite.log" 2>> "$L") && [ "$suite_status" = 0 ] && [ $sample_ok = 1 ] && r=pass
  step "$gc_group" $r "$s" "$L" ", \"tests_interval\": 1, \"tests_compiler_interval\": 0, \"modes\": [\"$mode\"], \"shard_index\": $shard, \"shard_count\": $gc_shards, \"shard_cases\": $shard_n, \"cases\": $#$x, \"stressed_sample\": {\"every\": $GC_SAMPLE_EVERY, \"offset\": $offset, \"cases\": $sample_n, \"tests_interval\": 1, \"tests_compiler_interval\": $GC_COMPILER_INTERVAL$y}"
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

# ---- dynany-optin: full program corpus opts into dynamic Any in three disjoint shards
# Every CPU runs a program (AOT builds are most of the time). A CI group (whose aggregate requires
# every group) or a run of all of them also runs tests-native, which executes the unchanged corpus
# with this compiler: --native-suite leaves to it the baseline of an exact expected failure and the
# AOT check of a program whose opted-in IR and fresh oracle are byte-identical to the original's.
for optin_index in 0 1 2; do
optin_name=dynany-optin-$optin_index
if want "$optin_name"; then
L=$V/$optin_name.log; s=$(now); r=fail; optin_fields=
optin_jobs=${PYSTACHY_JOBS:-$( (nproc || getconf _NPROCESSORS_ONLN) 2> /dev/null)}
case $optin_jobs in '' | *[!0-9]* | 0) optin_jobs=1 ;; esac
optin_native=; [ -z "${VERIFY_BOOTSTRAP_DIR:-}" ] && [ "$GROUP" != all ] || optin_native=--native-suite
if $PY tools/dynany_optin.py --compiler "$V/pystachy2" --modes jit aot ${optin_native:+"$optin_native"} \
    --jobs "$optin_jobs" --shard-index "$optin_index" --shard-count 3 \
    --report "$V/$optin_name.json" --keep "$V/$optin_name" > "$L" 2>&1; then
  if optin_fields=$($PY - "$V/$optin_name.json" "$optin_index" "$optin_native" <<'PYOPTIN'
import json
import sys
sys.path.insert(0, "tools")
import dynany_optin
from merge_verification import unique_object, invalid_constant
with open(sys.argv[1]) as stream:
    report = json.load(stream, object_pairs_hook=unique_object, parse_constant=invalid_constant)
dynany_optin.validate_report(report)
if (report["shard_index"] != int(sys.argv[2]) or report["shard_count"] != 3 or report["modes"] != ["jit", "aot"] or
        report["native_suite"] is not (sys.argv[3] == "--native-suite")):
    raise ValueError("dynamic Any sweep: wrong shard, execution modes or tests-native deferral")
print(', "optin": ' + json.dumps(report, sort_keys=True))
PYOPTIN
  ); then r=pass; fi
fi
step "$optin_name" "$r" "$s" "$L" "$optin_fields"
fi
done

# ---- python-int-optin: full program corpus opts into promoting ints in three disjoint shards
# (every CPU, and --native-suite in CI and all, as dynany-optin above)
for intoptin_index in 0 1 2; do
intoptin_name=python-int-optin-$intoptin_index
if want "$intoptin_name"; then
L=$V/$intoptin_name.log; s=$(now); r=fail; intoptin_fields=
intoptin_jobs=${PYSTACHY_JOBS:-$( (nproc || getconf _NPROCESSORS_ONLN) 2> /dev/null)}
case $intoptin_jobs in '' | *[!0-9]* | 0) intoptin_jobs=1 ;; esac
intoptin_native=; [ -z "${VERIFY_BOOTSTRAP_DIR:-}" ] && [ "$GROUP" != all ] || intoptin_native=--native-suite
if $PY tools/python_int_gate.py --compiler "$V/pystachy2" --modes jit aot ${intoptin_native:+"$intoptin_native"} \
    --jobs "$intoptin_jobs" --shard-index "$intoptin_index" --shard-count 3 \
    --report "$V/$intoptin_name.json" --keep "$V/$intoptin_name" > "$L" 2>&1; then
  if intoptin_fields=$($PY - "$V/$intoptin_name.json" "$intoptin_index" "$V/pystachy2" "$intoptin_native" <<'PYINTOPTIN'
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, "tools")
import python_int_gate
from merge_verification import unique_object, invalid_constant
with open(sys.argv[1]) as stream:
    report = json.load(stream, object_pairs_hook=unique_object, parse_constant=invalid_constant)
python_int_gate.validate_report(report)
if (report["shard_index"] != int(sys.argv[2]) or report["shard_count"] != 3 or
        report["modes"] != ["jit", "aot"] or report["gc_stress"] is not False or
        report["native_suite"] is not (sys.argv[4] == "--native-suite") or
        report["compiler_sha256"] != hashlib.sha256(Path(sys.argv[3]).read_bytes()).hexdigest()):
    raise ValueError("promoting-int sweep: wrong shard, modes, GC setting, tests-native deferral or compiler identity")
print(', "python_int_optin": ' + json.dumps(report, sort_keys=True))
PYINTOPTIN
  ); then r=pass; fi
fi
step "$intoptin_name" "$r" "$s" "$L" "$intoptin_fields"
fi
done

# The contracts group's steps share no output file and read only the bootstrap's files, so on CI's
# four vCPUs (two cores, two threads each) they run side by side, in three phases (run below, after
# their definitions; lanes of about equal CI time, run 40719438561): check-ir and rt-abi, as each
# uses every CPU itself; compile-limits, whose compilers must stay under ten CPU seconds (the hosted
# one takes about eight on CI: a busy sibling thread would add to its CPU time), beside one lane
# only, so each has a core; then four lanes. In the last two phases the shell runs one lane itself and
# the others are background jobs: a background job of a shell without job control starts with SIGINT
# and SIGQUIT ignored (POSIX), and so would every program it runs, so the steps that take SIGINT
# (ffi's py_sigint and side_sigint, selectprobe's pending SIGINT) are in the shell's lane,
# contracts_fg. In a lane, step keeps each step's record for the shell, which appends them to the
# report in the plan's order once every lane has ended: the same steps, results and fields as one
# after another, each with its own duration. Without bgjobs (no ps to list what a job starts), the
# lanes and the runtime builds before them run in the foreground, one after another.
# ---- re-probe: lib/re's matcher entries and contexts for textwrap's patterns, against fixed limits
contracts_a() {
if want re-probe; then
L=$V/re-probe.log; s=$(now); r=fail
$PY tools/re_probe.py > "$L" 2>&1 && r=pass
step re-probe $r "$s" "$L" "$(sed -n 's/^\([0-9]*\) operations, \([0-9]*\) failed$/, "operations": \1, "failed": \2/p' "$L")"
fi

# ---- re-fuzz: lib/re on CPython against CPython's own re, on random patterns and test_re's largest cases
if want re-fuzz; then
L=$V/re-fuzz.log; s=$(now); r=fail
$PY tools/re_fuzz.py > "$L" 2>&1 && r=pass
step re-fuzz $r "$s" "$L" "$(sed -n 's/^\([0-9]*\) upstream cases and \([0-9]*\) patterns (\([0-9]*\) valid): \([0-9]*\) cases, \([0-9]*\) failed$/, "upstream_cases": \1, "patterns": \2, "valid": \3, "cases": \4, "failed": \5/p' "$L")"
fi

# ---- runtime-table: the runtime functions the compiler declares, as runtime.c and runtime.py define them
if want runtime-table; then
L=$V/runtime-table.log; s=$(now); r=fail
$PY tools/check_runtime.py > "$L" 2>&1 && r=pass
step runtime-table $r "$s" "$L" "$(sed -n 's/^\([0-9]*\) RUNTIME entries, \([0-9]*\) exception classes: .*$/, "entries": \1, "exception_classes": \2/p' "$L")"
fi

# ---- inherited ASTs: declaration headers grow linearly; unused method bodies are shared
if want inherited-ast; then
L=$V/inherited-ast.log; s=$(now); r=fail
$PY tools/inheritprobe.py "$V/pystachy2" > "$L" 2>&1 && r=pass
step inherited-ast $r "$s" "$L" ', "sizes": [80, 160, 320], "native_size": 800, "address_space_mib": 256'
fi
}

contracts_b() {
# ---- Unicode audit: opt-in checks, code-point cache/locality and mutation/GC invalidation
if want unicode-audit; then
L=$V/unicode-audit.log; s=$(now); r=fail
{ $PY tools/unicode_audit.py -c "hosted=$PY -m pystachy" -c "native=$V/pystachy2" &&
  "${LLVM}clang" -O2 -S -emit-llvm tools/unicodeprobe.c -o "$V/unicodeprobe.ll" &&
  "${LLVM}llvm-link" "$V/rt2.ll" "$V/unicodeprobe.ll" -o "$V/unicodeprobe.bc" &&
  "${LLVM}clang" -O2 "$V/unicodeprobe.bc" -o "$V/unicodeprobe" -lm &&
  "$V/unicodeprobe" && PYSTACHY_GC_STRESS=1 "$V/unicodeprobe" && r=pass; } > "$L" 2>&1
step unicode-audit $r "$s" "$L" ', "compilers": ["CPython-hosted", "stage2"], "codepoint_probe_gc_modes": ["normal", "stress"]'
fi
}

contracts_c() {
# ---- rtcheck: runtime.py on CPython against CPython's own str methods and math functions
if want rtcheck; then
L=$V/rtcheck.log; s=$(now); r=fail
$PY tools/rtcheck.py > "$L" 2>&1 && r=pass
step rtcheck $r "$s" "$L" "$(sed -n 's/^\([0-9]*\) cases, \([0-9]*\) failed$/, "cases": \1, "failed": \2/p' "$L")"
fi

# ---- dynany-fuzz: seeded differential and typed/Any parity, JIT/AOT and program GC stress
if want dynany-fuzz; then
L=$V/dynany-fuzz.log; s=$(now); r=fail
if $PY tools/dynany_fuzz.py --compiler "$V/pystachy2" --keep "$V/dynany-fuzz" --aot --gc-stress 3 150 > "$L" 2>&1 &&
    [ "$(tail -1 "$L")" = '3 programs, 540 cases, 90 parity cases (JIT, AOT, JIT-GC, AOT-GC): 0 mismatches' ]; then r=pass; fi
step dynany-fuzz $r "$s" "$L" "$(tail -1 "$L" | sed -n 's/^\([0-9]*\) programs, \([0-9]*\) cases, \([0-9]*\) parity cases (JIT, AOT, JIT-GC, AOT-GC): \([0-9]*\) mismatches$/, "programs": \1, "cases": \2, "parity_cases": \3, "modes": ["jit", "aot", "jit-gc", "aot-gc"], "program_gc_interval": 1, "mismatches": \4/p')"
fi

# ---- streaming: sum(), min() and max() of 10^8 items in 64 MiB, which their list would exceed
if want streaming; then
L=$V/streaming.log; s=$(now); r=fail
$PY tools/streamprobe.py "$V/pystachy2" > "$L" 2>&1 && r=pass
step streaming $r "$s" "$L" ', "items": 100000000, "address_space_mib": 64'
fi
}

contracts_d() {
# ---- JIT dead code: inspect the actual execution module, without a timing threshold
if want jit-dead-code; then
L=$V/jit-dead-code.log; s=$(now); r=fail
$PY tools/jitprobe.py -c "hosted=$PY -m pystachy" -c "native=$V/pystachy2" > "$L" 2>&1 && r=pass
step jit-dead-code $r "$s" "$L" ', "unused_functions": 35, "compilers": ["CPython-hosted", "stage2"]'
fi

# ---- dict-probes: table slots per dict lookup for colliding keys, sequential keys the control
if want dict-probes; then
L=$V/dict-probes.log; s=$(now); r=fail
{ "$V/pystachy2" rt runtime.py -o "$V/dictprobe-rt.ll" && "${LLVM}clang" -O2 -S -emit-llvm tools/dictprobe.c -o "$V/dictprobe.ll" &&
  "${LLVM}llvm-link" "$V/dictprobe-rt.ll" "$V/dictprobe.ll" -o "$V/dictprobe.bc" && "${LLVM}clang" -O2 "$V/dictprobe.bc" -o "$V/dictprobe" -lm &&
  "$V/dictprobe" && PYSTACHY_GC_STRESS=1 "$V/dictprobe" --hash-cache && r=pass; } > "$L" 2>&1
step dict-probes $r "$s" "$L" "$(sed -n 's/^worst average: \([0-9.]*\) slots per lookup (limit \([0-9.]*\))$/, "worst_average_slots": \1, "limit": \2/p' "$L")"
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

# ---- weakrefs: handles do not keep targets alive and are pruned before their storage is reclaimed
if want weakrefs; then
L=$V/weakrefs.log; s=$(now); r=fail
{ "${LLVM}clang" -O2 -S -emit-llvm tools/weakrefprobe.c -o "$V/weakrefprobe.ll" &&
  "${LLVM}llvm-link" "$V/rt1.ll" "$V/weakrefprobe.ll" -o "$V/weakrefprobe.bc" &&
  "${LLVM}clang" -O2 "$V/weakrefprobe.bc" -o "$V/weakrefprobe" -lm &&
  "$V/weakrefprobe" && PYSTACHY_GC_STRESS=1 "$V/weakrefprobe" && r=pass; } > "$L" 2>&1
step weakrefs $r "$s" "$L" ', "referents": 2, "churned_handles": 1000'
fi

# ---- list-storage: deterministic capacity and live-byte checks for reachable empty lists, and
# collection counts for dropped large arrays
if want list-storage; then
L=$V/list-storage.log; s=$(now); r=fail
{ "${LLVM}clang" -O2 -S -emit-llvm tools/listprobe.c -o "$V/listprobe.ll" &&
  "${LLVM}llvm-link" "$V/rt1.ll" "$V/listprobe.ll" -o "$V/listprobe.bc" &&
  "${LLVM}clang" -O2 "$V/listprobe.bc" -o "$V/listprobe" -lm &&
  "$V/listprobe" && PYSTACHY_GC_STRESS=1 "$V/listprobe" && r=pass; } > "$L" 2>&1
step list-storage $r "$s" "$L" ', "lists": 64, "historical_slots_per_list": 65536, "live_byte_limit": 1048576, "large_object_budget": 4194304'
fi
}

contracts_fg() {
# ---- ffi: C functions, CPython embedded, extension modules (docs/ffi.md)
if want ffi; then
L=$V/ffi.log; s=$(now); r=fail
PY=$PY tests/ffi/run.sh "$V/pystachy2" > "$L" 2>&1 && r=pass
step ffi $r "$s" "$L" "$(sed -n 's/^\([0-9]*\) passed, \([0-9]*\) failed.*$/, "passed": \1, "failed": \2/p' "$L")"
fi

# ---- select-io: real descriptors, signal interruptions and readiness loops
if want select-io; then
L=$V/select-io.log; s=$(now); r=fail
{ "${LLVM}clang" -O2 -S -emit-llvm tools/selectprobe.c -o "$V/selectprobe.ll" &&
  "${LLVM}llvm-link" "$V/rt1.ll" "$V/selectprobe.ll" -o "$V/selectprobe.bc" &&
  "${LLVM}clang" -O2 "$V/selectprobe.bc" -o "$V/selectprobe" -lm &&
  "$V/selectprobe" && PYSTACHY_GC_STRESS=1 "$V/selectprobe" && r=pass; } > "$L" 2>&1
step select-io $r "$s" "$L" ''
fi

# ---- box-slots: boxes take 16-byte slots; a payload pointer keeps a box, one past its end does not
if want box-slots; then
L=$V/box-slots.log; s=$(now); r=fail
{ "${LLVM}clang" -O2 -S -emit-llvm tools/boxprobe.c -o "$V/boxprobe.ll" &&
  "${LLVM}llvm-link" "$V/rt1.ll" "$V/boxprobe.ll" -o "$V/boxprobe.bc" &&
  "${LLVM}clang" -O2 "$V/boxprobe.bc" -o "$V/boxprobe" -lm &&
  "$V/boxprobe" && PYSTACHY_GC_STRESS=1 "$V/boxprobe" && r=pass; } > "$L" 2>&1
step box-slots $r "$s" "$L" ', "box_bytes": 16'
fi
}

contracts_limits() {
# ---- compile limits: small sources must receive bounded source diagnostics, not exhaust memory
if want compile-limits; then
L=$V/compile-limits.log; s=$(now); r=fail
$PY tools/compilelimits.py -c "hosted=$PY pystachy.py" -c "native=$V/pystachy2" > "$L" 2>&1 && r=pass
step compile-limits $r "$s" "$L" ', "address_space_mib": 256, "cpu_seconds": 10, "modes": ["ir", "run", "build"]'
fi
}

contracts_cpus() {
# ---- check-ir: the IR of every program of the corpus passes the IR check and is valid LLVM
if want check-ir; then
L=$V/check-ir.log; s=$(now); r=fail
tools/check_ir.sh "$V/pystachy2" > "$L" 2>&1 && r=pass
step check-ir $r "$s" "$L" "$(sed -n 's/^the IR check and llvm-as accept the IR of \([0-9]*\) programs.*$/, "programs": \1/p' "$L")"
fi

# ---- rt-abi: one signature per runtime function across runtime.py, runtime.c and the corpus
if want rt-abi; then
L=$V/rt-abi.log; s=$(now); r=fail
$PY tools/rtabi.py "$V/pystachy2" > "$L" 2>&1 && r=pass
step rt-abi $r "$s" "$L" "$(sed -n 's/^\([0-9]*\) functions of runtime.py, \([0-9]*\) uses in runtime.c and \([0-9]*\) programs, \([0-9]*\) mismatches$/, "functions": \1, "uses": \2, "programs": \3, "mismatches": \4/p' "$L")"
fi
}

lane=
lanepids=
# bg LANE...: run each lane function as a background job (to its end without bgjobs), its output in
# build/verify
bg() {
  for l; do
    if [ -n "$bgjobs" ]; then
      (lane=$l; "contracts_$l") > "$V/contracts-lane-$l.log" 2>&1 &
      lanepids="$lanepids $!"
    else
      (lane=$l; "contracts_$l") > "$V/contracts-lane-$l.log" 2>&1
    fi
  done
}
if [ -n "$(for n in $(plan contracts); do [ "$n" = bootstrap ] || ! want "$n" || echo "$n"; done)" ]; then
  rm -rf "$V/lanes"; mkdir -p "$V/lanes"
  # One runtime build per compiler before the lanes, as the steps that ran one after another found it:
  # lanes would otherwise build it at once, and compile-limits' run and build under its CPU limit
  printf 'print("warm")\n' > "$V/lanes/warm.py"
  warm() { "$V/pystachy2" run "$V/lanes/warm.py"; $PY pystachy.py run "$V/lanes/warm.py"; $PY -m pystachy run "$V/lanes/warm.py"; }
  if [ -n "$bgjobs" ]; then
    warm > "$V/contracts-warm.log" 2>&1 &
    warmpid=$!
  else
    warm > "$V/contracts-warm.log" 2>&1
  fi
  lane="cpus"; contracts_cpus
  [ -z "${warmpid:-}" ] || wait "$warmpid"; warmpid=
  bg limits
  lane="fg"; contracts_fg
  for l in $lanepids; do wait "$l"; done
  lanepids=
  bg a b c
  lane="d"; contracts_d
  for l in $lanepids; do wait "$l"; done
  lane=; lanepids=
  for n in $(plan contracts); do
    [ "$n" != bootstrap ] && want "$n" || continue
    if [ -f "$V/lanes/$n.result" ] && [ -f "$V/lanes/$n.json" ]; then
      read -r res t log < "$V/lanes/$n.result"
      record "$n" "$res" "$t" "$log" "$(cat "$V/lanes/$n.json")"
    else  # (its lane ended before the step did: build/verify/contracts-lane-*.log)
      record "$n" fail 0 "$V/$n.log" "$(printf '    {"name": "%s", "result": "fail", "seconds": 0, "log": %s, "lane_ended": true}' "$n" "$(js "build/verify/$n.log")")"
    fi
  done
fi

# ---- scaling: compile time grows linearly with generated programs (counts need Python 3.12+)
# scaling-0 checks the shapes of SCALING_0, about half the CPython-hosted compiler's lines that --ops
# counts, and scaling-1 every other shape of tools/scaling.py (-x), so a new shape is checked too.
SCALING_0=chain,modules,stdlib,fields,lookups,elifs,globals,topelifs
for shard in 0 1; do
  want scaling-$shard || continue
  L=$V/scaling-$shard.log; s=$(now); r=fail
  sel=-s; [ $shard = 0 ] || sel=-x
  # (-j: shapes side by side, one per CPU; --check compares counts, which do not depend on the load)
  $PY tools/scaling.py --check --ops "$sel" "$SCALING_0" -n 500,1000 -r 1 -j "${PYSTACHY_JOBS:-0}" \
    -c "hosted=$PY pystachy.py" -c "native=$V/pystachy2" > "$L" 2>&1 && r=pass
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
  corpus > "$V/report-corpus.list"
  SUITE_CHECKS=$ALL MODE_CHECKS=$(checks jit) CORPUS_LIST=$V/report-corpus.list $PY - <<'PY'
import hashlib
import json
import os
from pathlib import Path
paths = [Path(p) for p in ("pystachy.py", "runtime.c", "runtime.py")]
paths += sorted(Path("src").rglob("*.py"))
sources = {str(p): {"lines": p.read_bytes().count(b"\n"),
                    "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths}
# (suite_checks: the checks of the whole corpus in JIT and AOT, which the shards of each such suite
# make together; mode_checks: its checks in one mode, which the shards of each GC suite make with
# their samples, and the UBSan thirds once in each mode)
# (corpus_cases and syntax_cases: the cases tests-cpython, and the gc-ir halves together, compile
# with both compilers, and those they check with both; all of them counted in tests/corpus.sh's corpus)
cases = [Path(p) for p in Path(os.environ["CORPUS_LIST"]).read_text().splitlines()]
sources.update(test_programs=sum(p.parts[:2] == ("tests", "programs") for p in cases),
               rejection_tests=sum(p.parts[:2] == ("tests", "errors") for p in cases),
               corpus_cases=len(cases), syntax_cases=sum(p.name.startswith("syntax_") for p in cases),
               suite_checks=int(os.environ["SUITE_CHECKS"]), mode_checks=int(os.environ["MODE_CHECKS"]))
print('  "sources": ' + json.dumps(sources, sort_keys=True) + ',')
PY
  printf '  "steps": [\n'; cat "$V/steps.json"; printf '\n  ]\n}\n'
} > "$OUT"
echo "verification: $((nsteps - nfail))/$nsteps steps passed -> ${OUT#"$ROOT"/}"
[ $nfail = 0 ] && [ "$complete" = true ]
