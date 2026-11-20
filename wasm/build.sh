#!/bin/sh
# WebAssembly through LLVM (wasm/README.md): the runtime, runtime.c and runtime.py, compiled once
# for wasm32-wasi, and programs compiled from the LLVM IR the compiler emits, then linked with it.
# usage: wasm/build.sh runtime                 build build/wasm/runtime.o and stubs.o if their
#                                              sources changed (or WASM_RUNTIME's directory)
#        wasm/build.sh program FILE.py OUT.wasm  compile FILE.py and link OUT.wasm (a WASI
#                                              command: node wasm/run.mjs OUT.wasm ARGS...)
# Environment: PYSTACHY, the compiler (default ./pystachy; "python3 pystachy.py" works too);
# PYSTACHY_LLVM, LLVM's bin directory (clang, llvm-link, opt, and wasm-ld there or on PATH);
# WASI_SYSROOT, a wasi-libc sysroot (default: Ubuntu's wasi-libc package, whose headers and
# libraries lie in /usr/include/wasm32-wasi and /usr/lib/wasm32-wasi); WASM_RUNTIME, the
# runtime's directory (default build/wasm); WASM_OPT, the -O level of programs (default 2); PY,
# the Python that runs wasm/wasm32_ir.py (default python3).
set -eu
cd "$(dirname "$0")/.."
PYSTACHY=${PYSTACHY:-./pystachy}
LLVM=${PYSTACHY_LLVM:+$PYSTACHY_LLVM/}
RT=${WASM_RUNTIME:-build/wasm}
OPT=${WASM_OPT:-2}
PY=${PY:-python3}
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
  if [ -f "$stamp" ] && [ -f "$RT/runtime.o" ] && [ -f "$RT/stubs.o" ] &&
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
  sed -E 's/@(memcmp|memchr|memmem)\(/@pys_wasi_\1(/g' "$t/rt-py.ll" > "$t/rt-py-wasi.ll"
  # shellcheck disable=SC2086
  "${LLVM}clang" $W -O2 -c -emit-llvm runtime.c -o "$t/rt-c.bc"
  # (runtime.py's module has no data layout: runtime.c's gives the linked one)
  "${LLVM}llvm-link" "$t/rt-c.bc" "$t/rt-py-wasi.ll" -o "$t/rt.bc" 2> "$t/link.err" || { cat "$t/link.err" >&2; exit 1; }
  "${LLVM}opt" -O2 "$t/rt.bc" -o "$t/rt-opt.bc"
  "${LLVM}clang" --target=$TARGET -O2 -c "$t/rt-opt.bc" -o "$t/runtime.o"
  # shellcheck disable=SC2086
  "${LLVM}clang" $W -O2 -Wall -Wextra -Werror -c wasm/wasi_stubs.c -o "$t/stubs.o"
  mv "$t/runtime.o" "$RT/runtime.o"; mv "$t/stubs.o" "$RT/stubs.o"
  touch "$stamp"
}

program() { # FILE.py OUT.wasm
  [ -f "$RT/runtime.o" ] && [ -f "$RT/stubs.o" ] || { echo "wasm/build.sh: no runtime in $RT: run wasm/build.sh runtime" >&2; exit 1; }
  SYS=$(sysroot)
  t=$(mktemp -d "${TMPDIR:-/tmp}/pystachy-wasm.XXXXXX")
  trap 'rm -rf "$t"' EXIT
  # shellcheck disable=SC2086
  $PYSTACHY ir "$1" -o "$t/prog.ll"
  # (wasm32's constants and main: wasm/wasm32_ir.py)
  "$PY" wasm/wasm32_ir.py "$t/prog.ll" "$t/prog-wasi.ll"
  "${LLVM}clang" --target=$TARGET -O"$OPT" -c -x ir "$t/prog-wasi.ll" -o "$t/prog.o" -Wno-override-module
  # --fatal-warnings: a call whose signature differs from its definition's (which would trap)
  # shellcheck disable=SC2086
  "${LLVM}clang" --target=$TARGET --sysroot="$SYS" "$t/prog.o" "$RT/runtime.o" "$RT/stubs.o" -o "$2" \
    -Wl,--fatal-warnings -Wl,-z,stack-size=8388608 $LIBS
}

case ${1:-} in
  runtime) runtime ;;
  program) [ $# = 3 ] || { echo "usage: wasm/build.sh program FILE.py OUT.wasm" >&2; exit 2; }; program "$2" "$3" ;;
  *) echo "usage: wasm/build.sh runtime | program FILE.py OUT.wasm" >&2; exit 2 ;;
esac
