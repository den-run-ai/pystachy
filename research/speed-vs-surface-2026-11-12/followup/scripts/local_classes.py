"""For methods first-rejected with 'a class inside a function', count local classes that capture
enclosing function variables (closures) versus ones that could move to module scope unchanged.

usage: python3.13 -I local_classes.py METHODS.json METHODS_DIR
"""
import collections, json, sys, symtable
from pathlib import Path

recs, mdir = json.load(open(sys.argv[1]))["records"], Path(sys.argv[2])


def frees(t):
    out = set()
    for s in t.get_symbols():
        if s.is_free():
            out.add(s.get_name())
    for c in t.get_children():
        out |= frees(c)
    return out


def local_classes(t, in_func=False):
    for c in t.get_children():
        if c.get_type() == "class" and in_func:
            yield c
        yield from local_classes(c, in_func or c.get_type() == "function")


stats = collections.Counter()
names = collections.Counter()
for r in recs:
    if r["status"] != "compile-error" or "a class inside a function is not supported" not in r.get("detail", ""):
        continue
    stem = Path(r["file"]).stem
    prog = mdir / stem / (r["test"].replace(".", "__") + ".py")
    if not prog.exists():
        stats["missing"] += 1
        continue
    top = symtable.symtable(prog.read_text(), str(prog), "exec")
    cls = list(local_classes(top))
    cap = [c for c in cls if frees(c)]
    stats["methods"] += 1
    stats["methods with a capturing local class" if cap else "methods whose local classes capture nothing"] += 1
    stats["local classes"] += len(cls)
    stats["capturing local classes"] += len(cap)
    for c in cap:
        for n in frees(c):
            names[n] += 1
print(dict(stats))
print("most captured names:", names.most_common(10))
