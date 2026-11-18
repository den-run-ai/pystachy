"""Summarize a function's machine code in an executable: instruction count, calls by target, and its
innermost loops (a backward jump whose span holds no other backward jump), with each loop's
instructions and the calls, checks (jumps to blocks outside it) and memory reads in it.
usage: loops_asm.py EXECUTABLE SYMBOL_SUBSTRING
"""
import re
import subprocess
import sys

exe, want = sys.argv[1], sys.argv[2]
syms = subprocess.run(["nm", "-C", exe], capture_output=True, text=True).stdout
names = [line.split()[-1] for line in syms.splitlines() if want in line.split()[-1] and line.split()[1] in "tT"]
for name in names:
    dis = subprocess.run(["objdump", "-d", "--no-show-raw-insn", f"--disassemble={name}", exe], capture_output=True, text=True).stdout
    ins = []
    for line in dis.splitlines():
        m = re.match(r"^\s+([0-9a-f]+):\s+(\S+)\s*(.*)$", line)
        if m:
            ins.append((int(m.group(1), 16), m.group(2), m.group(3)))
    calls = {}
    for _, op, arg in ins:
        if op.startswith("call"):
            t = re.search(r"<([^>]+)>", arg)
            key = t.group(1) if t else arg
            calls[key] = calls.get(key, 0) + 1
    addrs = [a for a, _, _ in ins]
    back = []
    for i, (a, op, arg) in enumerate(ins):
        if op.startswith("j"):
            t = re.match(r"([0-9a-f]+)", arg)
            if t and int(t.group(1), 16) <= a:
                back.append((int(t.group(1), 16), a))
    inner = [(s, e) for s, e in back if not any(s <= s2 and e2 <= e and (s2, e2) != (s, e) for s2, e2 in back)]
    print(f"== {name}: {len(ins)} instructions; calls: " + ", ".join(f"{k} x{v}" for k, v in sorted(calls.items(), key=lambda kv: -kv[1])))
    for s, e in sorted(inner):
        body = [x for x in ins if s <= x[0] <= e]
        exits = sum(1 for a, op, arg in body if op.startswith("j") and re.match(r"([0-9a-f]+)", arg) and not (s <= int(re.match(r"([0-9a-f]+)", arg).group(1), 16) <= e))
        cl = [re.search(r"<([^>]+)>", arg).group(1) if re.search(r"<([^>]+)>", arg) else arg for a, op, arg in body if op.startswith("call")]
        loads = sum(1 for a, op, arg in body if "(" in arg and not op.startswith(("lea", "nop")) and not arg.split(",")[-1].strip().startswith(("(", "0x(")) or (op.startswith("mov") and "(" in arg.split(",")[0]))
        fp = sum(1 for a, op, arg in body if op.startswith(("vadd", "vsub", "vmul", "vdiv", "vfmadd", "vsqrt", "add", "sub", "mul", "div")) and "sd" in op or op.startswith(("vfmadd",)))
        print(f"   loop {s:x}-{e:x}: {len(body)} instructions, {exits} exits, fp ops {fp}, calls {cl}")
