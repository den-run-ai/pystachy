#!/bin/bash
# clang wrapper: where clang compiles a bitcode input (the AOT pipeline's whole-program step) and
# $KEEP_BC is set, keeps a copy of that input; then runs the real clang
real=/usr/lib/llvm-18/bin/clang
bcin=""; xlang=0; comp=0; prev=""
for a in "$@"; do
  case "$a" in
    -c) comp=1 ;;
    -x) xlang=1 ;;
    *.bc) [ "$prev" != "-o" ] && bcin="$a" ;;
  esac
  prev="$a"
done
if [ $comp = 1 ] && [ $xlang = 0 ] && [ -n "$bcin" ] && [ -n "$KEEP_BC" ]; then
  cp "$bcin" "$KEEP_BC"
fi
exec "$real" "$@"
