#!/bin/bash
# opt with EXTRA passes spliced before the JIT's final function(early-cse,adce); OPTCAP keeps input and output
[ -n "$EXTRA_NAME" ] && EXTRA=$(cat /tmp/claude-0/-home-user-pystachy/d93c2c20-f8ea-590f-9162-601d62fd95f8/scratchpad/passx/presets/$EXTRA_NAME)
args=()
for a in "$@"; do
  if [[ -n "$EXTRA" && "$a" == -passes=* && "$a" == *",function(early-cse,adce)"* ]]; then
    a="${a/,function(early-cse,adce)/,$EXTRA,function(early-cse,adce)}"
  fi
  args+=("$a")
done
[ -n "$PASSLOG" ] && printf '%s\n' "${args[*]}" >> "$PASSLOG"
/usr/lib/llvm-18/bin/opt "${args[@]}"; code=$?
if [ -n "$OPTCAP" ] && [ $code -eq 0 ] && [[ "${args[*]}" == *"function(early-cse,adce)"* ]]; then
  prev=; out=; inp=
  for a in "${args[@]}"; do [ "$prev" = "-o" ] && out=$a; [[ "$a" == *.ll ]] && inp=$a; prev=$a; done
  cp "$inp" "$OPTCAP.in.ll"; /usr/lib/llvm-18/bin/llvm-dis "$out" -o "$OPTCAP.out.ll"
fi
exit $code
