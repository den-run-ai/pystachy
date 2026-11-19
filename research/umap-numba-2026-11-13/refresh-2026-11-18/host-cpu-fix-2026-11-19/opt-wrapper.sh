#!/bin/bash
# the real opt; keeps a copy of each output module (-o) in $CAPTURE_DIR when set, and with
# STRIP_CPU=1 removes "target-cpu" from the program module's functions (prog.bc), keeping their
# "target-features": the JIT runner then tunes code as for no CPU (LLVM's default) with the host's ISA
out=""; prev=""
for a in "$@"; do [ "$prev" = "-o" ] && out="$a"; prev="$a"; done
/usr/lib/llvm-18/bin/opt "$@"; rc=$?
if [ $rc = 0 ] && [ "$STRIP_CPU" = 1 ] && [ "$(basename "$out")" = prog.bc ]; then
  /usr/lib/llvm-18/bin/llvm-dis "$out" -o "$out.ll" && sed -i 's/ "target-cpu"="[^"]*"//g' "$out.ll" && /usr/lib/llvm-18/bin/llvm-as "$out.ll" -o "$out" || exit 9
  rm -f "$out.ll"
fi
if [ -n "$CAPTURE_DIR" ] && [ -n "$out" ] && [ -f "$out" ]; then cp "$out" "$CAPTURE_DIR/$(date +%s%N)-$(basename "$out")"; fi
exit $rc
