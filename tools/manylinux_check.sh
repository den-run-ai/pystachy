#!/bin/sh
# The compiler on an old glibc (docs/install.md#platform-and-deployment-boundaries), run from a
# checkout inside the manylinux_2_28 image (AlmaLinux 8: glibc 2.28, GCC 8's libgcc_s, a
# compiler that builds non-PIE executables by default), with the LLVM of PYSTACHY_LLVM:
#   1. make, with PY (default: the image's CPython 3.11), bootstraps the compiler again, whatever
#      ./pystachy holds, and reaches the compiler's and the runtime's fixed points
#   2. tools/linux_abi.py: the compiler, an AOT program and an extension module that it builds
#      import no glibc symbol newer than MAX_GLIBC (default 2.28)
#   3. tests/run.sh, JIT and AOT, on corpus areas (FILES; the default leaves out the cases whose
#      output depends on libm's last digits or on /bin/sh's job messages, which differ there)
# The logs and linux_abi.py's report go to build/manylinux/. Fails when a step fails.
# usage: tools/manylinux_check.sh
cd "$(dirname "$0")/.." || exit 1
PY=${PY:-/opt/python/cp311-cp311/bin/python3}
MAX_GLIBC=${MAX_GLIBC:-2.28}
FILES=${FILES:-tests/programs/exceptions/*.py tests/programs/generators/*.py tests/programs/io/*.py tests/programs/syntax/*.py tests/errors/exceptions/*.py}
[ -n "$PYSTACHY_LLVM" ] || { echo "tools/manylinux_check.sh: set PYSTACHY_LLVM to an LLVM bin directory" >&2; exit 2; }
machine=$(uname -m)
L=build/manylinux
rm -rf "$L" && mkdir -p "$L/abi" || exit 1
echo "glibc $(getconf GNU_LIBC_VERSION | cut -d' ' -f2), $("$PYSTACHY_LLVM/clang" --version | head -1), $("$PY" -V)"

echo "== make"
make -B PY="$PY" pystachy > "$L/make.log" 2>&1 || { tail -30 "$L/make.log"; echo "tools/manylinux_check.sh: make failed" >&2; exit 1; }
grep '^fixed point' "$L/make.log"

echo "== glibc symbols (at most $MAX_GLIBC)"
cp pystachy "$L/abi/pystachy" &&
  ./pystachy build tests/programs/syntax/syntax_blocks_generic.py -o "$L/abi/program" &&
  ./pystachy ext tests/ffi/ext/fastmath.py -o "$L/abi/fastmath.abi3.so" || exit 1
"$PY" -I tools/linux_abi.py "$L/abi" --architecture "$machine" --max-glibc "$MAX_GLIBC" --json "$L/linux-abi.json" \
  > "$L/linux-abi.txt" 2>&1 || { cat "$L/linux-abi.txt"; exit 1; }
"$PY" -I -c 'import json, sys
for b in json.load(open(sys.argv[1]))["binaries"]: print(b["path"], "needs glibc", b["glibc_symbol_floor"])' "$L/linux-abi.json"

# LLVM 18 can place empty dispatch functions at the same address as the main function.
# This case needs main's handler, including when lli links an object from llc at -O0.
echo "== exception through each JIT launcher and code generation level"
for launcher in auto lli; do
  for level in 0 2; do
    log="$L/exception-$launcher-$level.log"
    PYSTACHY_JIT_LAUNCHER=$launcher PYSTACHY_JIT_CODEGEN=$level tests/run.sh ./pystachy jit \
      tests/programs/exceptions/exc_as_unbound.py > "$log" 2>&1 || { cat "$log"; exit 1; }
  done
done

echo "== corpus, JIT and AOT"
# shellcheck disable=SC2086
tests/run.sh ./pystachy "jit aot" $FILES > "$L/test.log" 2>&1; st=$?
grep -A8 '^FAIL' "$L/test.log" | head -80
tail -1 "$L/test.log"
exit $st
