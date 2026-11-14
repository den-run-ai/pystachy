"""Count calls of the runtime's copied functions in loop blocks (in a CFG cycle) and elsewhere.

usage: loop_sites.py TABLE PROGRAM.ll...
"""
import re
import sys

table = open(sys.argv[1]).read()
copied = set(re.findall(r"^; item helper (@[\w.$]+) ", table, re.M))
sizes = {}
for block in table.split("; item helper ")[1:]:
    name = block.split(" ")[0]
    body = block.split("\n", 1)[1].split("\n; item ")[0]
    sizes[name] = sum(1 for line in body.split("\n") if line.startswith("  "))


def functions(ir):
    lines = ir.split("\n")
    i = 0
    while i < len(lines):
        if lines[i].startswith("define "):
            j = i
            while lines[j] != "}":
                j += 1
            yield lines[i:j + 1]
            i = j
        i += 1


for path in sys.argv[2:]:
    ir = open(path).read()
    inloop = {}
    outloop = {}
    for fn in functions(ir):
        blocks = {}
        order = []
        cur = "%entry0"
        blocks[cur] = []
        order.append(cur)
        for line in fn[1:-1]:
            m = re.match(r"^([\w.$\"-]+):", line)
            if m:
                cur = "%" + m.group(1)
                blocks[cur] = []
                order.append(cur)
            else:
                blocks[cur].append(line)
        succ = {b: set(re.findall(r"label (%[\w.$\"-]+)", "\n".join(blocks[b]))) for b in blocks}
        # blocks in a cycle: reachable from one of their successors
        incycle = set()
        for b in blocks:
            seen = set()
            todo = list(succ[b])
            while todo:
                x = todo.pop()
                if x == b:
                    incycle.add(b)
                    break
                if x in seen or x not in succ:
                    continue
                seen.add(x)
                todo.extend(succ[x])
        for b in blocks:
            for line in blocks[b]:
                for h in re.findall(r"\b(?:call|invoke)\b[^@\n]*(@[\w.$]+)\(", line):
                    if h in copied:
                        d = inloop if b in incycle else outloop
                        d[h] = d.get(h, 0) + 1
    add_in = sum(n * sizes[h] for h, n in inloop.items())
    add_out = sum(n * sizes[h] for h, n in outloop.items())
    print(f"{path.split('/')[-1]:24s} in loops {sum(inloop.values()):5d} sites (~{add_in} instructions), elsewhere {sum(outloop.values()):5d} sites (~{add_out} instructions)")
    top = sorted(outloop.items(), key=lambda kv: -kv[1] * sizes[kv[0]])[:6]
    print("   elsewhere, most code:", ", ".join(f"{h[1:]} {n}x{sizes[h]}" for h, n in top))
