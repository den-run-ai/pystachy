#!/bin/sh
# WebAssembly through LLVM (wasm/README.md): the runtime, runtime.c and runtime.py, compiled once
# for wasm32-wasi, and programs compiled from the LLVM IR the compiler emits, then linked with it.
# usage: wasm/build.sh runtime                 build build/wasm/runtime.o and stubs.o if their
#                                              sources changed (or WASM_RUNTIME's directory)
#        wasm/build.sh program FILE.py OUT.wasm  compile FILE.py and link OUT.wasm (a WASI
#                                              command: node wasm/run.mjs OUT.wasm ARGS...)
# Without LLVM (wasm/README.md's typed IR emitter):
#        wasm/build.sh runtime-wasm            build/wasm/runtime.wasm, the runtime as a module that
#                                              programs import, if runtime.o or reactor.c changed
#        wasm/build.sh emitter                 build native tools for source and module-text input
#        wasm/build.sh direct FILE.py OUT.wasm emit from finalized typed IR, exit 3 on refusal
#        wasm/build.sh link                    stream retained LLVM IR to a WASI command on stdout
#                                              at -O0 for one-shot calls (WASM_OPT overrides)
#        wasm/build.sh tir FILE.py OUT.wasm    same, with LLVM fallback on an emitter refusal
#                                              WASM_TIR_LOG records emitted or refused per file
# Environment: PYSTACHY, the compiler (default ./pystachy; "python3 pystachy.py" works too);
# PYSTACHY_LLVM, LLVM's bin directory (clang, llvm-link, opt, and wasm-ld there or on PATH);
# WASI_SYSROOT, a wasi-libc sysroot (default: Ubuntu's wasi-libc package, whose headers and
# libraries lie in /usr/include/wasm32-wasi and /usr/lib/wasm32-wasi); WASM_RUNTIME, the
# runtime's directory (default build/wasm); WASM_OPT, the -O level of programs (default 2); PY,
# the Python that runs wasm/wasm32_ir.py (default python3). WASM_EH=standard targets try_table;
# linking LLVM programs with catches then requires Binaryen wasm-opt with --emit-exnref.
set -eu
cd "$(dirname "$0")/.."
PYSTACHY=${PYSTACHY:-./pystachy}
LLVM=${PYSTACHY_LLVM:+$PYSTACHY_LLVM/}
RT=${WASM_RUNTIME:-build/wasm}
OPT=${WASM_OPT:-2}
PY=${PY:-python3}
EH=${WASM_EH-legacy}
case "$EH" in
  legacy|standard) ;;
  *) echo "WASM_EH must be legacy or standard" >&2; exit 2 ;;
esac
TARGET=wasm32-wasi
# runtime.c's POSIX that WASI lacks: wasm/include's headers and pystachy_wasi.h declare it,
# wasm/wasi_stubs.c defines it; the C library emulates signal(), clock() and getpid(). (Its
# <sys/mman.h> declares munmap, which wasi_stubs.c defines: the page heap maps nothing)
EMUL="-D_WASI_EMULATED_SIGNAL -D_WASI_EMULATED_PROCESS_CLOCKS -D_WASI_EMULATED_GETPID -D_WASI_EMULATED_MMAN"
LIBS="-lwasi-emulated-signal -lwasi-emulated-process-clocks -lwasi-emulated-getpid"

sysroot() { # the sysroot clang is given: WASI_SYSROOT, or one of links to Ubuntu's wasi-libc
  if [ -n "${WASI_SYSROOT:-}" ]; then echo "$WASI_SYSROOT"; return; fi
  [ -f /usr/include/wasm32-wasi/stdio.h ] && [ -f /usr/lib/wasm32-wasi/libc.a ] || {
    echo "wasm/build.sh: no WASI sysroot: install wasi-libc and libclang-rt-18-dev-wasm32 (apt), or set WASI_SYSROOT" >&2
    exit 1
  }
  s=$RT/sysroot
  if [ ! -d "$s/lib" ]; then
    mkdir -p "$s/lib"
    ln -sfn /usr/include/wasm32-wasi "$s/include"
    ln -sfn /usr/lib/wasm32-wasi "$s/lib/$TARGET"
  fi
  echo "$s"
}

runtime() {
  mkdir -p "$RT"
  SYS=$(sysroot)
  stamp=$RT/runtime.stamp
  if [ -f "$stamp" ] && [ -f "$RT/runtime.o" ] && [ -f "$RT/stubs.o" ] && [ -f "$RT/command-eh.o" ] &&
    [ -z "$(find runtime.c runtime.py ryu mpz wasm pystachy.py src -newer "$stamp" -type f | head -1)" ]; then
    return 0
  fi
  t=$(mktemp -d "$RT/rt.XXXXXX")
  trap 'rm -rf "$t"' EXIT
  W="--target=$TARGET --sysroot=$SYS -isystem wasm/include -include pystachy_wasi.h $EMUL"
  # runtime.py's IR declares the C library's memcmp, memchr and memmem with LP64's i64 lengths:
  # wasi_stubs.c's pys_wasi_* take those and convert them (a mismatched call would trap)
  # shellcheck disable=SC2086 # (PYSTACHY and W are word lists)
  $PYSTACHY rt runtime.py -o "$t/rt-py.ll"
  "$PY" wasm/wasm32_ir.py "$t/rt-py.ll" "$t/rt-py-wasi.ll"
  # shellcheck disable=SC2086
  "${LLVM}clang" $W -O2 -c -emit-llvm runtime.c -o "$t/rt-c.bc"
  # (runtime.py's module has no data layout: runtime.c's gives the linked one)
  "${LLVM}llvm-link" "$t/rt-c.bc" "$t/rt-py-wasi.ll" -o "$t/rt.bc" 2> "$t/link.err" || { cat "$t/link.err" >&2; exit 1; }
  "${LLVM}opt" -O2 "$t/rt.bc" -o "$t/rt-opt.bc"
  "${LLVM}clang" --target=$TARGET -O2 -c "$t/rt-opt.bc" -o "$t/runtime.o"
  # shellcheck disable=SC2086
  "${LLVM}clang" $W -O2 -Wall -Wextra -Werror -c wasm/wasi_stubs.c -o "$t/stubs.o"
  # shellcheck disable=SC2086
  "${LLVM}clang" $W -O2 -fwasm-exceptions -Wall -Wextra -Werror -c wasm/command_eh.c -o "$t/command-eh.o"
  mv "$t/command-eh.o" "$RT/command-eh.o"
  mv "$t/runtime.o" "$RT/runtime.o"; mv "$t/stubs.o" "$RT/stubs.o"
  rm -rf "$t"; trap - EXIT
  touch "$stamp"
}

program() ( # source|ir INPUT OUTPUT (a dash streams IR input or Wasm output)
  [ -f "$RT/runtime.o" ] && [ -f "$RT/stubs.o" ] || { echo "wasm/build.sh: no runtime in $RT: run wasm/build.sh runtime" >&2; exit 1; }
  SYS=$(sysroot)
  t=$(mktemp -d "${TMPDIR:-/tmp}/pystachy-wasm.XXXXXX")
  trap 'rm -rf "$t"' EXIT
  ir=$2
  if [ "$1" = source ]; then
    ir=$t/prog.ll
    # shellcheck disable=SC2086
    $PYSTACHY ir "$2" -o "$ir"
  elif [ "$ir" = - ]; then
    ir=$t/prog.ll
    cat > "$ir"
  fi
  destination=$3
  output=$destination
  if [ "$output" = - ]; then output=$t/program.wasm; fi
  # (wasm32's constants and main: wasm/wasm32_ir.py)
  "$PY" wasm/wasm32_ir.py "$ir" "$t/prog-wasi.ll"
  set -- "$RT/runtime.o" "$RT/stubs.o"
  ehflag=
  standard_command=false
  if grep -q '^declare void @pys_wasi_uncaught(ptr)$' "$t/prog-wasi.ll"; then
    [ -f "$RT/command-eh.o" ] || { echo "wasm/build.sh: rebuild the exception runtime with wasm/build.sh runtime" >&2; exit 1; }
    if [ "$EH" = standard ]; then
      command -v wasm-opt >/dev/null || { echo "wasm/build.sh: WASM_EH=standard needs Binaryen wasm-opt for LLVM exception handlers" >&2; exit 1; }
      standard_command=true
      output=$t/legacy.wasm
    fi
    ehflag=-fwasm-exceptions
    set -- "$@" "$RT/command-eh.o"
  fi
  "${LLVM}clang" --target=$TARGET -O"$OPT" ${ehflag:+"$ehflag"} -c -x ir "$t/prog-wasi.ll" -o "$t/prog.o" -Wno-override-module
  # --fatal-warnings: a call whose signature differs from its definition's (which would trap)
  # shellcheck disable=SC2086
  "${LLVM}clang" --target=$TARGET --sysroot="$SYS" "$t/prog.o" "$@" -o "$output" \
    -Wl,--fatal-warnings -Wl,-z,stack-size=8388608 $LIBS
  if [ "$standard_command" = true ]; then
    wasm-opt --enable-exception-handling --emit-exnref "$output" -o "$t/standard.wasm"
    output=$t/standard.wasm
    if [ "$destination" != - ]; then mv "$output" "$destination"; fi
  fi
  if [ "$destination" = - ]; then cat "$output"; fi
)

runtime_wasm() {
  runtime
  SYS=$(sysroot)
  if [ -f "$RT/runtime.wasm" ] && [ -z "$(find "$RT/runtime.o" "$RT/stubs.o" wasm/reactor.c -newer "$RT/runtime.wasm" | head -1)" ]; then
    return 0
  fi
  t=$(mktemp -d "$RT/rtw.XXXXXX")
  trap 'rm -rf "$t"' EXIT
  "${LLVM}clang" --target=$TARGET --sysroot="$SYS" -O2 -Wall -Wextra -Werror -c wasm/reactor.c -o "$t/reactor.o"
  # a reactor (no main) exporting every symbol: a program module imports the runtime's functions
  # and the recursion state by name; the runtime imports the program's code (program.init) and
  # the class dispatchers (env.pys_obj_*), which wasm/run.mjs supplies
  # shellcheck disable=SC2086
  "${LLVM}clang" --target=$TARGET --sysroot="$SYS" -mexec-model=reactor "$t/reactor.o" "$RT/runtime.o" "$RT/stubs.o" \
    -o "$t/runtime.wasm" -Wl,--export-all -Wl,--export=__stack_pointer -Wl,--allow-undefined-file=wasm/reactor.imports -Wl,--fatal-warnings -Wl,-z,stack-size=8388608 $LIBS
  mv "$t/runtime.wasm" "$RT/runtime.wasm"
  rm -rf "$t"; trap - EXIT
}

emitter() {
  mkdir -p "$RT"
  # shellcheck disable=SC2086 # PYSTACHY can be a hosted compiler command
  PYSTACHY_PATH=. $PYSTACHY build wasm/tir_wasm.py -o "$RT/tir_wasm"
  # shellcheck disable=SC2086
  PYSTACHY_PATH=. $PYSTACHY build tools/wasm_from_source.py -o "$RT/wasm_from_source"
}

direct() {
  if [ -x "$RT/wasm_from_source" ]; then
    PYSTACHY_HOME=${PYSTACHY_HOME:-$PWD} "$RT/wasm_from_source" "$@"
  else
    PYTHONPATH=.${PYTHONPATH:+:$PYTHONPATH} "$PY" tools/wasm_from_source.py "$@"
  fi
}

tir() {
  [ -f "$RT/runtime.wasm" ] || { echo "wasm/build.sh: no $RT/runtime.wasm: run wasm/build.sh runtime-wasm" >&2; exit 1; }
  # On refusal the frontend can lower the same finalized functions for the LLVM route.
  # Give each build its own temporary IR and publish the output only after a successful build.
  d=$(mktemp -d "${TMPDIR:-/tmp}/pystachy-tir.XXXXXX")
  trap 'rm -rf "$d"' EXIT
  status=0
  direct "$1" "$d/program.wasm" "$d/program.ll" 2> "$d/err" || status=$?
  case $status in
    0)
      cat "$d/err" >&2
      if [ -n "${WASM_TIR_LOG:-}" ]; then printf '%s emitted\n' "$1" >> "$WASM_TIR_LOG"; fi ;;
    3)
      if [ -n "${WASM_TIR_LOG:-}" ]; then
        IFS= read -r why < "$d/err" || why="emitter refused"
        printf '%s refused: %s\n' "$1" "${why#tir_wasm: refused: }" >> "$WASM_TIR_LOG"
      fi
      program ir "$d/program.ll" "$d/program.wasm" ;;
    *) cat "$d/err" >&2; return "$status" ;;
  esac
  mv "$d/program.wasm" "$2"
}

case ${1:-} in
  runtime) runtime ;;
  program) [ $# = 3 ] || { echo "usage: wasm/build.sh program FILE.py OUT.wasm" >&2; exit 2; }; program source "$2" "$3" ;;
  link) [ $# = 1 ] || { echo "usage: wasm/build.sh link < INPUT.ll > OUT.wasm" >&2; exit 2; }; OPT=${WASM_OPT:-0}; program ir - - ;;
  runtime-wasm) runtime_wasm ;;
  emitter) emitter ;;
  direct) [ $# = 3 ] || { echo "usage: wasm/build.sh direct FILE.py OUT.wasm" >&2; exit 2; }; direct "$2" "$3" ;;
  tir) [ $# = 3 ] || { echo "usage: wasm/build.sh tir FILE.py OUT.wasm" >&2; exit 2; }; tir "$2" "$3" ;;
  *) echo "usage: wasm/build.sh runtime | program FILE.py OUT.wasm | runtime-wasm | emitter | link | {direct|tir} FILE.py OUT.wasm" >&2; exit 2 ;;
esac
