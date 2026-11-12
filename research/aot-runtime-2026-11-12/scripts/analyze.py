import re, glob, collections, sys
rt = open(sys.argv[1]).read().split("\n")
size = {}
name = None
n = 0
for s in rt:
    if s.startswith("define "):
        m = re.search(r"@([-\w$.]+|\"[^\"]+\")\(", s)
        name = m.group(1); n = 0
    elif s == "}" and name:
        size[name] = n; name = None
    elif name and s.startswith("  ") and not s.startswith("  ;"):
        n += 1
pat = re.compile(r"'([^']+)' inlined into '([^']+)' with \(cost=(-?\d+|always), threshold=(-?\d+)\)")
into_prog = collections.Counter()
progs_per = collections.defaultdict(set)
maxcost = {}
for f in glob.glob("out-*/*.err"):
    for m in pat.finditer(open(f, errors="replace").read()):
        x, y, cost, thr = m.groups()
        if x in size and y not in size:
            into_prog[x] += 1
            progs_per[x].add(f)
rows = sorted(into_prog, key=lambda x: -size[x])
print(len(rows), "runtime functions inlined into program code;", len(size), "runtime functions")
for x in rows:
    print(f"{size[x]:6d} instr  {len(progs_per[x]):4d} programs  {x}")
sizes = sorted(size.values())
for t in [25, 50, 100, 150, 200, 300, 400, 600, 1000]:
    kept = [s for s in sizes if s <= t]
    print(f"bound {t}: {len(kept)} bodies, {sum(kept)} instructions of {sum(sizes)}")
