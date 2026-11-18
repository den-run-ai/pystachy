"""For the loops (strongly connected block sets) of a function in an LLVM module that hold the given
lines, list each exit edge with the condition that takes it, the calls in the loop and its size.
usage: loop_exits.py MODULE.ll FUNCTION LINE...
"""
import re
import sys
sys.path.insert(0, "/tmp/claude-0/-home-user-pystachy/d93c2c20-f8ea-590f-9162-601d62fd95f8/scratchpad/pr-loops")
from src.pystachy_compiler.jit_helpers import cyclic

lines = open(sys.argv[1]).read().split("\n")
start = next(i for i, l in enumerate(lines) if l.startswith("define") and f"@{sys.argv[2]}(" in l)
end = next(i for i in range(start, len(lines)) if lines[i] == "}")
want = [int(x) - 1 for x in sys.argv[3:]]
blocks, order, cur = {}, [], "entry"
blocks[cur] = []
order.append(cur)
where = {}
for k in range(start + 1, end):
    m = re.match(r"^([-\w.$]+):", lines[k])
    if m:
        cur = m.group(1)
        blocks[cur] = []
        order.append(cur)
    elif lines[k].strip() != "":
        blocks[cur].append(k)
        where[k] = cur
idx = {b: i for i, b in enumerate(order)}
succ = [[idx[t] for t in re.findall(r"label %([-\w.$]+)", "\n".join(lines[k] for k in blocks[b])) if t in idx] for b in order]
# strongly connected components (iterative Tarjan via cyclic's helper is boolean only): take the
# component of each wanted block by forward/backward reachability
def reach(s, edges):
    seen, todo = {s}, [s]
    while todo:
        v = todo.pop()
        for w in edges[v]:
            if w not in seen:
                seen.add(w)
                todo.append(w)
    return seen
pred = [[] for _ in order]
for v, ws in enumerate(succ):
    for w in ws:
        pred[w].append(v)
defs = {}
for k in range(start + 1, end):
    m = re.match(r"^\s+(%[-\w.$]+) = (.*)$", lines[k])
    if m:
        defs[m.group(1)] = m.group(2)
for line in want:
    b = idx[where[line]]
    comp = reach(b, succ) & reach(b, pred)
    ins = sum(len(blocks[order[v]]) for v in comp)
    calls = {}
    for v in comp:
        for k in blocks[order[v]]:
            m = re.search(r"\bcall [^@%]*([@%][-\w.$\"]+)\(", lines[k])
            if m and not m.group(1).startswith("@llvm."):
                calls[m.group(1)] = calls.get(m.group(1), 0) + 1
    print(f"== loop of line {line + 1}: {len(comp)} blocks, {ins} instructions; calls {calls}")
    for v in sorted(comp):
        term = lines[blocks[order[v]][-1]]
        outs = [t for t in re.findall(r"label %([-\w.$]+)", term) if t in idx and idx[t] not in comp]
        if not outs:
            continue
        m = re.match(r"\s+br i1 (%[-\w.$]+),", term)
        cond = defs.get(m.group(1), "?") if m else term.strip()[:60]
        # what the exit block does first (an error call, or the loop's way out)
        first = [lines[k].strip() for k in blocks[outs[0]] if "call" in lines[k] or "ret" in lines[k] or "br " in lines[k]][:1]
        print(f"   exit {order[v]} -> {outs[0]}: {cond[:90]}  | {first[0][:80] if first else ''}")
