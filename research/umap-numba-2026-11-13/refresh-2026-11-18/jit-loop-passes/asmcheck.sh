#!/bin/bash
# asmcheck.sh NAME EXTRA : opt the captured default input with EXTRA spliced in, llc it, print kNN's inner loop
SP=/tmp/claude-0/-home-user-pystachy/d93c2c20-f8ea-590f-9162-601d62fd95f8/scratchpad
cd $SP/passx
name=$1; extra=$2
base=$(grep -- "-passes=" passlog | tail -1 | grep -o "^-passes=[^ ]*" | sed 's/^-passes=//')
[ -n "$extra" ] && base="${base/,function(early-cse,adce)/,$extra,function(early-cse,adce)}"
s=$(date +%s.%N)
/usr/lib/llvm-18/bin/opt -passes="$base" -force-remove-attribute=pys_new:noinline -force-attribute=pys_new:alwaysinline -force-remove-attribute=pys_alloc:noinline -force-attribute=pys_alloc:alwaysinline cap-none.in.ll -o asm-$name.bc || exit 1
e=$(date +%s.%N)
/usr/lib/llvm-18/bin/llc -O2 -mcpu=native -filetype=obj -relocation-model=pic asm-$name.bc -o asm-$name.o
python3 - "$name" "$(echo "$e - $s" | bc)" <<'PY'
import re, subprocess, sys
name, secs = sys.argv[1], sys.argv[2]
dis = subprocess.run(["objdump", "-d", "--no-show-raw-insn", "--disassemble=f.main", f"asm-{name}.o"], capture_output=True, text=True).stdout
ins = [(int(m.group(1), 16), m.group(2), m.group(3)) for m in (re.match(r"^\s+([0-9a-f]+):\s+(\S+)\s*(.*)$", l) for l in dis.splitlines()) if m]
best = None
for k, (a, op, arg) in enumerate(ins):
    m = re.match(r"([0-9a-f]+) <", arg)
    if op.startswith("j") and m and int(m.group(1), 16) < a:
        t = int(m.group(1), 16)
        body = [x for x in ins if t <= x[0] <= a]
        ops = " ".join(x[1] for x in body)
        if "vsubsd" in ops and "vmulsd" in ops and "vaddsd" in ops and len(body) < 40:
            if best is None or len(body) < len(best):
                best = body
print(f"{name}: opt {float(secs):.3f}s; inner loop {len(best) if best else '?'} instructions")
for x in best or []:
    print(f"    {x[1]} {x[2]}")
PY
