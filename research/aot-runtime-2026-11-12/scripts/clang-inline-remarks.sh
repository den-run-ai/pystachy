#!/bin/sh
# Adds inline remarks to the AOT program's optimization step (input .../prog.bc) for analysis.
for a in "$@"; do
  case "$a" in
    */prog.bc) exec /usr/lib/llvm-18/bin/clang "$@" -Rpass=inline ;;
  esac
done
exec /usr/lib/llvm-18/bin/clang "$@"
