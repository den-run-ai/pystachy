#!/bin/sh
# usage: build.sh [--no-headers] OUT [LLVM_BIN_DIR]
# Builds the prototype launcher with that LLVM's clang (default: LLVM 18's), linked with its shared
# libLLVM. By default it compiles against the LLVM C API headers that llvm-config names
# (llvm-18-dev on Ubuntu). --no-headers needs no LLVM headers or llvm-config: it declares the C API
# itself (llvm-c-decls.h) for the version lli reports and links the libLLVM that lli loads.
set -eu
decls=0
if [ "$1" = --no-headers ]; then decls=1; shift; fi
out=$1
bin=${2:-/usr/lib/llvm-18/bin}
src=$(dirname "$0")/pystachy-lljit.c
if [ $decls = 1 ]; then
  major=$("$bin/lli" --version | sed -n 's/.*LLVM version \([0-9]*\)\..*/\1/p')
  lib=$(ldd "$bin/lli" | sed -n 's/^[[:space:]]*libLLVM[^ ]* => \([^ ]*\) .*/\1/p')
  [ -n "$major" ] && [ -n "$lib" ] || { echo "build.sh: $bin/lli is not linked with a shared libLLVM" >&2; exit 1; }
  "$bin/clang" -O2 -Wall -Wextra -Werror -std=c11 -D_GNU_SOURCE -DPYS_LLVM_DECLS -DLLVM_VERSION_MAJOR="$major" \
    -o "$out" "$src" "$lib" -Wl,-rpath,"$(dirname "$lib")" -ldl
else
  inc=$("$bin/llvm-config" --includedir)
  lib=$("$bin/llvm-config" --libdir)
  # shellcheck disable=SC2046
  "$bin/clang" -O2 -Wall -Wextra -Werror -std=c11 -D_GNU_SOURCE -I"$inc" -o "$out" "$src" \
    -L"$lib" -Wl,-rpath,"$lib" $("$bin/llvm-config" --link-shared --libs) -ldl
fi
