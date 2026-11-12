"""Probe: move local classes that capture nothing to module scope, then rerun the methods.

usage: python3.13 -I hoist_probe.py METHODS.json QUALIFIED.json OUTDIR
Writes OUTDIR/qualified-hoisted.json with transformed programs that still give CPython's
recorded result under CPython; prints how many were transformed, skipped and kept.
"""
import ast, collections, json, subprocess, symtable, sys
from pathlib import Path

methods, qualified, outdir = sys.argv[1], sys.argv[2], Path(sys.argv[3])
outdir.mkdir(parents=True, exist_ok=True)
blocked = {(r["file"], r["test"]) for r in json.load(open(methods))["records"]
           if r["status"] == "compile-error" and "a class inside a function is not supported" in r.get("detail", "")}
q = json.load(open(qualified))


def frees(t):
    out = {s.get_name() for s in t.get_symbols() if s.is_free()}
    for c in t.get_children():
        out |= frees(c)
    return out


def capturing_lines(src):
    lines = set()

    def walk(t, in_func):
        for c in t.get_children():
            if c.get_type() == "class" and in_func and frees(c):
                lines.add(c.get_lineno())
            walk(c, in_func or c.get_type() == "function")
    walk(symtable.symtable(src, "p", "exec"), False)
    return lines


stats = collections.Counter()
kept = []
for rec in q["records"]:
    if rec.get("cpython") != "ok" or (rec["file"], rec["test"]) not in blocked:
        continue
    src = Path(rec["program"]).read_text()
    tree = ast.parse(src)
    capture = capturing_lines(src)
    top_names = {n.name for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef))}
    moved, bad = [], False

    def strip(body, in_func):
        global bad
        new = []
        for n in body:
            if isinstance(n, ast.ClassDef) and in_func:
                if n.lineno in capture or n.name in top_names or any(m.name == n.name for m in moved):
                    bad = True
                    new.append(n)
                    continue
                moved.append(n)
                continue
            for field in ("body", "orelse", "finalbody"):
                if hasattr(n, field) and isinstance(getattr(n, field), list):
                    setattr(n, field, strip(getattr(n, field), in_func or isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))) or [ast.Pass()])
            if isinstance(n, ast.Try):
                for h in n.handlers:
                    h.body = strip(h.body, in_func) or [ast.Pass()]
            new.append(n)
        return new

    tree.body = strip(tree.body, False)
    if bad or not moved:
        stats["skipped (capturing, name clash or nothing to move)"] += 1
        continue
    first = next(i for i, n in enumerate(tree.body) if not isinstance(n, (ast.Import, ast.ImportFrom)))
    tree.body[first:first] = moved
    out = outdir / (Path(rec["program"]).parent.name + "__" + Path(rec["program"]).name)
    out.write_text(ast.unparse(ast.fix_missing_locations(tree)) + "\n")
    p = subprocess.run([sys.executable, "-I", str(out)], cwd=outdir, capture_output=True, text=True, timeout=120)
    if [p.returncode, p.stdout, p.stderr] != rec["expected"]:
        stats["hoisted but CPython's result changes"] += 1
        continue
    stats["hoisted, CPython result unchanged"] += 1
    kept.append(rec | {"program": str(out)})
json.dump({"python": q["python"], "records": kept}, open(outdir / "qualified-hoisted.json", "w"))
print(dict(stats), "of", len(blocked), "blocked")
