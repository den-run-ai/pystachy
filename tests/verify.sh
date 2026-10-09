#!/bin/sh
# Verification harness: every check below runs (a failing step does not stop the others) and the
# results go to build/verification.json -- per step: name, pass/fail, duration, counts -- with the
# toolchain versions, git commit and a timestamp. Exit status 0 only if every step passed.
#   bootstrap      CPython -> stage1 -> stage2 -> stage3 compilers emit identical LLVM IR
#   tests-cpython  tests/run.sh with the CPython-hosted compiler, JIT and AOT
#   tests-native   tests/run.sh with the stage-2 native compiler, JIT and AOT
#   tests-opt-off  tests/run.sh with the stage-2 compiler and every optimization on the IR turned off
#                  (PYSTACHY_OPT=-all): the passes change no output
#   python-free    PATH holds only symlinks to the LLVM tools, the linker and the POSIX tools that the
#                  driver and tests/run.sh call (no python3): the native compiler rebuilds its runtime
#                  and itself, reproduces the same IR and passes the tests
#   ubsan          PYSTACHY_CFLAGS="$UBSAN" (private PYSTACHY_HOME, so a fresh runtime cache): the
#                  compiler built that way reproduces the IR, and every test passes AOT-built with it
#                  and JIT-run on the sanitized runtime (lli gets the UBSan runtime via LD_PRELOAD)
#   check-ir       tools/check_ir.sh: the compiler's IR check (PYSTACHY_IRCHECK=1) and llvm-as accept the
#                  IR of every program of the corpus (the tests, the benchmarks, the tests/ir probes and
#                  the compiler itself)
#   runtime-table  tools/check_runtime.py: the compiler's RUNTIME table agrees with runtime.c (types,
#                  coverage, and the effects its call graph shows)
#   gc-stress      PYSTACHY_GC_STRESS: the native compiler collecting every 1000 allocations reproduces
#                  the IR, and every test passes JIT and AOT with a collection at every allocation of the
#                  program (PYSTACHY_GC_STRESS_PROGRAM=1), compiled by the compiler collecting every 1000
#   benchmarks     bench/*.py print exactly what CPython prints, JIT and AOT; timings recorded
#   dict-probes    tools/dictprobe.c: dict lookups visit few table slots for keys that defeat a weak
#                  hash or probe sequence (deterministic counts against a fixed limit, no timings)
#   scaling        tools/scaling.py --check: both compilers compile its generated programs (500 and 1000
#                  functions, globals, classes, modules, chained imports, breaks, elifs, ...), and the
#                  lines the CPython-hosted compiler executes, and the items its builtin calls copy or
#                  scan, grow no faster than the programs
# usage: tests/verify.sh   (make verify)   env: PY (default python3), PYSTACHY_LLVM (LLVM 18 bin dir)
cd "$(dirname "$0")/.." || exit 1
ROOT=$(pwd)
PY=${PY:-python3}
UBSAN="-fsanitize=undefined -fno-sanitize-recover=all"
V=$ROOT/build/verify
OUT=$ROOT/build/verification.json
rm -rf "$V" "$OUT"
mkdir -p "$V/home" "$V/ubsan-home"
cp runtime.c "$V/home/"
cp runtime.c "$V/ubsan-home/"
cp -R lib "$V/home/"
cp -R lib "$V/ubsan-home/"
export PYSTACHY_HOME="$ROOT"
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
# tests LOG...: JSON counts summed over tests/run.sh outputs (the "N passed, M failed" line ends
# each log, FAIL lines name the failures); false if anything failed or a log has no summary
tests() {
  np=0; nf=0; fl=""; ok=0
  for l; do
    c=$(tail -1 "$l" 2>/dev/null | sed -n 's/^\([0-9]*\) passed, \([0-9]*\) failed$/\1 \2/p')
    [ -n "$c" ] || { ok=1; continue; }
    np=$((np + ${c% *})); nf=$((nf + ${c#* }))
    fl="$fl$(sed -n 's/^FAIL \(.*\)$/\1/p' "$l" | while read -r x; do printf ', %s' "$(js "$x")"; done)"
  done
  printf ', "passed": %s, "failed": %s, "failures": [%s]' $np $nf "${fl#, }"
  [ $ok = 0 ] && [ $nf = 0 ]
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
    echo "fixed point: stage1 == stage2 == stage3 ($(lines "$V/stage1.ll") lines of IR)" && r=pass
} > "$L" 2>&1
x=""
[ $r = pass ] && x=$(printf ', "ir_identical": true, "ir_lines": %s, "ir_sha256": "%s", "native_compiler_bytes": %s, "cpython_self_compile_seconds": %s, "native_self_compile_seconds": %s' \
  "$(lines "$V/stage1.ll")" "$(sha "$V/stage1.ll")" "$(wc -c < "$V/pystachy2" | tr -d ' ')" "$(secs "$t0" "$t1")" "$(secs "$t2" "$t3")")
step bootstrap $r "$s" "$L" "$x"

# ---- differential tests with both compilers
L=$V/tests-cpython.log; s=$(now)
tests/run.sh "$PY pystachy.py" > "$L" 2>&1
x=$(tests "$L") && r=pass || r=fail
step tests-cpython $r "$s" "$L" ', "compiler": "CPython-hosted", "modes": ["jit", "aot"]'"$x"
L=$V/tests-native.log; s=$(now)
tests/run.sh "$V/pystachy2" > "$L" 2>&1
x=$(tests "$L") && r=pass || r=fail
step tests-native $r "$s" "$L" ', "compiler": "stage2", "modes": ["jit", "aot"]'"$x"
L=$V/tests-opt-off.log; s=$(now); logs=""; offs=""
for o in all; do
  PYSTACHY_OPT=-$o tests/run.sh "$V/pystachy2" > "$V/tests-opt-off-$o.log" 2>&1
  logs="$logs $V/tests-opt-off-$o.log"; offs="$offs, \"-$o\""
done
for l in $logs; do echo "== $(basename "$l")"; cat "$l"; done > "$L"
x=$(tests $logs) && r=pass || r=fail
step tests-opt-off $r "$s" "$L" ', "compiler": "stage2", "modes": ["jit", "aot"], "PYSTACHY_OPT": ['"${offs#, }"']'"$x"

# ---- python-free: the native compiler and the tests with only LLVM + POSIX tools on PATH
L=$V/python-free.log; s=$(now); r=fail; py=true
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
  # mkfifo and sleep test programs run
  for t in ld sh mkdir sed mv rm rmdir test cat cmp diff head tail grep dirname basename mkfifo sleep nproc; do tool $t || ok=0; done
  echo "PATH=$NP"; ls -l "$NP" | sed 1d
  if nopy sh -c 'command -v python3 || command -v python'; then ok=0; echo "python is reachable"
  else py=false; echo "python3, python: not found on PATH"; fi
  [ $ok = 1 ] &&
    nopy "$V/pystachy2" build pystachy.py -o "$V/pystachy-nopy" && ls "$V/home/build" &&
    nopy "$V/pystachy-nopy" ir pystachy.py -o "$V/stage-nopy.ll" &&
    cmp "$V/stage1.ll" "$V/stage-nopy.ll" && echo "rebuilt compiler emits the stage1 IR" &&
    nopy sh tests/run.sh "$V/pystachy-nopy" && r=pass
} > "$L" 2>&1
x=$(tests "$L") || r=fail
step python-free $r "$s" "$L" "$(printf ', "python_on_path": %s, "path_tools": [%s], "ir_identical": %s' "$py" \
  "$(ls "$NP" | while read -r t; do printf '"%s", ' "$t"; done | sed 's/, $//')" "$(same "$V/stage1.ll" "$V/stage-nopy.ll")")$x"
rm -rf "$NP"

# ---- ubsan: sanitized runtime in every program, the compiler included
L=$V/ubsan.log; s=$(now); r=fail; built=0
UBSO=$("${LLVM}clang" -print-file-name="libclang_rt.ubsan_standalone-$(uname -m).so")
{
  echo 'int main(void) { return 0; }' | "${LLVM}clang" -x c $UBSAN - -o "$V/ubsan-probe" ||
    { echo "clang cannot link $UBSAN: install the UBSan runtime (Ubuntu: libclang-rt-18-dev)"; false; } &&
    PYSTACHY_HOME="$V/ubsan-home" PYSTACHY_CFLAGS="$UBSAN" "$V/pystachy2" build pystachy.py -o "$V/pystachy-ubsan" &&
    "$V/pystachy-ubsan" ir pystachy.py -o "$V/stage-ubsan.ll" &&
    cmp "$V/stage1.ll" "$V/stage-ubsan.ll" && echo "sanitized compiler emits the stage1 IR" &&
    ls "$V/ubsan-home/build" && test ! -f "$V/ubsan-home/build/runtime.bc" &&
    grep -q __ubsan_handle "$V"/ubsan-home/build/runtime-*.bc && echo "cached runtime bitcode is instrumented" && built=1
  if [ $built = 1 ]; then
    PYSTACHY_HOME="$V/ubsan-home" PYSTACHY_CFLAGS="$UBSAN" tests/run.sh "$V/pystachy-ubsan" aot > "$V/ubsan-aot.log" 2>&1
    # (LD_PRELOAD reaches what a program execs too, a shell that kills itself by SIGSEGV say, where
    # UBSan's deadly-signal handler would turn the death into its report and status 1)
    env LD_PRELOAD="$UBSO" UBSAN_OPTIONS="${UBSAN_OPTIONS:+$UBSAN_OPTIONS:}handle_segv=0" PYSTACHY_HOME="$V/ubsan-home" \
      PYSTACHY_CFLAGS="$UBSAN" tests/run.sh "$V/pystachy2" jit > "$V/ubsan-jit.log" 2>&1
    for m in aot jit; do echo "-- tests ($m)"; cat "$V/ubsan-$m.log"; done
  fi
} > "$L" 2>&1
x=$(tests "$V/ubsan-aot.log" "$V/ubsan-jit.log") && [ $built = 1 ] && r=pass
step ubsan $r "$s" "$L" ", \"cflags\": $(js "$UBSAN"), \"modes\": [\"aot\", \"jit\"], \"jit_preload\": $(js "$UBSO"), \"ir_identical\": $(same "$V/stage1.ll" "$V/stage-ubsan.ll")$x"

# ---- check-ir: the IR of every program of the corpus passes the IR check and is valid LLVM
L=$V/check-ir.log; s=$(now); r=fail
tools/check_ir.sh "$V/pystachy2" > "$L" 2>&1 && r=pass
step check-ir $r "$s" "$L" "$(sed -n 's/^the IR check and llvm-as accept the IR of \([0-9]*\) programs.*$/, "programs": \1/p' "$L")"

# ---- runtime-table: the runtime functions the compiler declares, as runtime.c defines them
L=$V/runtime-table.log; s=$(now); r=fail
$PY tools/check_runtime.py > "$L" 2>&1 && r=pass
step runtime-table $r "$s" "$L" "$(sed -n 's/^\([0-9]*\) RUNTIME entries: .*$/, "entries": \1/p' "$L")"

# ---- gc-stress: collections far more often than the collector would run them
L=$V/gc-stress.log; s=$(now); r=fail
{
  # (every 1000, not 100: the compiler keeps each function's IR until the program is built, and at
  # every 100 its collections, which mark all of it, take minutes)
  PYSTACHY_GC_STRESS=1000 "$V/pystachy2" ir pystachy.py -o "$V/stage-gc.ll" &&
    cmp "$V/stage1.ll" "$V/stage-gc.ll" && echo "the compiler collecting every 1000 allocations emits the stage1 IR" && r=pass
  PYSTACHY_GC_STRESS=1000 PYSTACHY_GC_STRESS_PROGRAM=1 tests/run.sh "$V/pystachy2" > "$V/gc-stress-tests.log" 2>&1
  echo "-- tests, collecting at every allocation"; cat "$V/gc-stress-tests.log"
} > "$L" 2>&1
x=$(tests "$V/gc-stress-tests.log") || r=fail
step gc-stress $r "$s" "$L" ", \"compiler_interval\": 1000, \"tests_interval\": 1, \"tests_compiler_interval\": 1000, \"modes\": [\"jit\", \"aot\"], \"ir_identical\": $(same "$V/stage1.ll" "$V/stage-gc.ll")$x"

# ---- benchmarks: same output as CPython, JIT and AOT
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

# ---- dict-probes: table slots per dict lookup for colliding keys, sequential keys the control
L=$V/dict-probes.log; s=$(now); r=fail
{ "${LLVM}clang" -O2 tools/dictprobe.c -o "$V/dictprobe" -lm && "$V/dictprobe" && r=pass; } > "$L" 2>&1
step dict-probes $r "$s" "$L" "$(sed -n 's/^worst average: \([0-9.]*\) slots per lookup (limit \([0-9.]*\))$/, "worst_average_slots": \1, "limit": \2/p' "$L")"

# ---- scaling: compile time grows linearly with generated programs (counts need Python 3.12+)
L=$V/scaling.log; s=$(now); r=fail
$PY tools/scaling.py --check --ops -n 500,1000 -r 1 -c "hosted=$PY pystachy.py" -c "native=$V/pystachy2" > "$L" 2>&1 && r=pass
step scaling $r "$s" "$L" ', "sizes": [500, 1000]'

# ---- report
ver() { "$@" 2>&1 | head -1; }
{
  printf '{\n  "project": "Pystachy",\n  "result": "%s",\n' "$([ $nfail = 0 ] && echo pass || echo fail)"
  printf '  "summary": {"steps": %s, "passed": %s, "failed": %s, "seconds": %s},\n' $nsteps $((nsteps - nfail)) $nfail "$(secs "$start" "$(now)")"
  printf '  "timestamp_utc": "%s",\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  if c=$(git rev-parse HEAD 2>/dev/null); then d=$([ -z "$(git status --porcelain)" ] && echo false || echo true); else c=unknown; d=null; fi
  printf '  "git": {"commit": %s, "dirty": %s},\n' "$(js "$c")" "$d"
  printf '  "platform": {"system": %s, "machine": %s, "os": %s, "cpu": %s},\n' "$(js "$(uname -sr)")" "$(js "$(uname -m)")" \
    "$(js "$(sed -n 's/^PRETTY_NAME="*\([^"]*\)"*$/\1/p' /etc/os-release 2>/dev/null)")" \
    "$(js "$("${LLVM}opt" --version 2>&1 | sed -n 's/^ *Host CPU: //p')")"
  printf '  "toolchain": {"python": %s, "clang": %s, "llvm": %s, "llvm_dir": %s},\n' "$(js "$(ver $PY --version)")" \
    "$(js "$(ver "${LLVM}clang" --version)")" "$(js "$(ver "${LLVM}opt" --version)")" "$(js "${PYSTACHY_LLVM:-PATH}")"
  printf '  "sources": {"pystachy.py": {"lines": %s, "sha256": "%s"}, "runtime.c": {"lines": %s, "sha256": "%s"}, "test_programs": %s, "rejection_tests": %s},\n' \
    "$(lines pystachy.py)" "$(sha pystachy.py)" "$(lines runtime.c)" "$(sha runtime.c)" \
    "$(ls tests/*.py | wc -l | tr -d ' ')" "$(ls tests/errors/*.py | wc -l | tr -d ' ')"
  printf '  "steps": [\n'; cat "$V/steps.json"; printf '\n  ]\n}\n'
} > "$OUT"
echo "verification: $((nsteps - nfail))/$nsteps steps passed -> ${OUT#"$ROOT"/}"
[ $nfail = 0 ]
