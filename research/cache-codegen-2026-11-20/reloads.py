"""Count the stack reloads in UMAP kNN's per-pair loop (the loop around listguard's copy of the
distance loop, block %L297.i) in an llc assembly file, and print the copy itself.
usage: reloads.py FILE.s"""
import re, sys
lines = open(sys.argv[1]).read().split("\n")
s = next(i for i, l in enumerate(lines) if l.startswith("f.main:"))
e = next(i for i in range(s, len(lines)) if lines[i].startswith(".Lfunc_end"))
body = lines[s:e]
lab = {re.match(r"^(\.LBB\d+_\d+):", l).group(1): k for k, l in enumerate(body) if re.match(r"^\.LBB\d+_\d+:", l)}
inner = [k for k, l in enumerate(body) if re.match(r"^\.LBB\d+_\d+:\s+# %L297\.i", l)][0]
best = None
for k, l in enumerate(body):
    m = re.match(r"^\s+j\w+\s+(\.LBB\d+_\d+)", l)
    if m and m.group(1) in lab and lab[m.group(1)] < inner < k:
        if best is None or k - lab[m.group(1)] < best[0]:
            best = (k - lab[m.group(1)], lab[m.group(1)], k)
_, a, b = best
seg = [l for l in body[a:b + 1] if re.match(r"^\s+[a-z]", l)]
j = inner
while not re.match(r"^\s+j\w+\s", body[j]) or "L297" not in "".join(body[inner:inner+1]):
    j += 1
copy = [l.strip() for l in body[inner + 1:j + 1] if re.match(r"^\s+[a-z]", l)]
fold = any("Folded Reload" in l for l in copy)
print(f"{sys.argv[1]}: per-pair loop {len(seg)} instructions, {sum('Reload' in l for l in seg)} reloads; distance copy {len(copy)} instructions, bound {'reloaded each iteration' if fold else 'in a register'}")
