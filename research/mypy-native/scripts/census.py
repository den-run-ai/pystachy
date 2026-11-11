"""Static feature census of a Python source tree (reads only; never imports it)."""
import ast, collections, json, os, sys

root, out = sys.argv[1], sys.argv[2]
pkgs = sys.argv[3:]
C = collections.Counter()
imports = collections.Counter()
import_sites = collections.defaultdict(set)
multi = []
metas = []
decos = collections.Counter()
calls = collections.Counter()
typing_names = collections.Counter()
files = 0
lines = 0
per_file = {}
INTEREST_CALLS = {"getattr","setattr","hasattr","delattr","eval","exec","globals","locals","vars","isinstance","issubclass","type","super","id","hash","cast","open","iter","next","sorted","repr","callable","__import__","compile","dir","memoryview","bytearray","object","property","staticmethod","classmethod","zip","enumerate","reversed","print","frozenset","NewType","TypeVar","namedtuple"}

def base_name(b):
    if isinstance(b, ast.Subscript):
        return base_name(b.value)
    if isinstance(b, ast.Attribute):
        return b.attr
    if isinstance(b, ast.Name):
        return b.id
    return ast.dump(b)[:30]

for pkg in pkgs:
    for dp, dn, fn in os.walk(os.path.join(root, pkg)):
        dn[:] = sorted(d for d in dn if d not in ("typeshed", "test", "test-data", "__pycache__", "lib-rt", "doc", "external", "xml"))
        for f in sorted(fn):
            if not f.endswith(".py"):
                continue
            path = os.path.join(dp, f)
            rel = os.path.relpath(path, root)
            src = open(path, encoding="utf-8").read()
            tree = ast.parse(src)
            files += 1
            n = src.count("\n")
            lines += n
            fc = collections.Counter()
            for node in ast.walk(tree):
                t = type(node).__name__
                if isinstance(node, ast.Import):
                    for a in node.names:
                        imports[a.name] += 1; import_sites[a.name].add(rel)
                elif isinstance(node, ast.ImportFrom):
                    m = ("." * node.level) + (node.module or "")
                    imports[m] += 1; import_sites[m].add(rel)
                    if m in ("typing", "typing_extensions", "mypy_extensions", "collections.abc", "abc", "enum", "dataclasses", "functools", "contextlib"):
                        for a in node.names:
                            typing_names[m + "." + a.name] += 1
                elif isinstance(node, ast.ClassDef):
                    fc["class"] += 1
                    bases = [base_name(b) for b in node.bases]
                    real = [b for b in bases if b not in ("Generic", "Protocol")]
                    if len(real) > 1:
                        multi.append((rel, node.name, bases, [base_name(d.func if isinstance(d, ast.Call) else d) for d in node.decorator_list]))
                    for k in node.keywords:
                        if k.arg == "metaclass":
                            metas.append((rel, node.name, base_name(k.value)))
                    for d in node.decorator_list:
                        decos["class:" + base_name(d.func if isinstance(d, ast.Call) else d)] += 1
                    for st in node.body:
                        if isinstance(st, ast.Assign) and any(isinstance(x, ast.Name) and x.id == "__slots__" for x in st.targets):
                            fc["__slots__"] += 1
                        if isinstance(st, ast.ClassDef):
                            fc["nested_class"] += 1
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    fc["def"] += 1
                    if isinstance(node, ast.AsyncFunctionDef): fc["async_def"] += 1
                    for d in node.decorator_list:
                        decos["def:" + base_name(d.func if isinstance(d, ast.Call) else d)] += 1
                    if node.args.vararg: fc["*args_def"] += 1
                    if node.args.kwarg: fc["**kwargs_def"] += 1
                    if node.args.kwonlyargs: fc["kwonly_def"] += 1
                    if node.args.posonlyargs: fc["posonly_def"] += 1
                    for sub in node.body:
                        for x in ast.walk(sub):
                            if isinstance(x, (ast.FunctionDef, ast.Lambda)) and x is not node:
                                fc["nested_def_or_lambda"] += 1
                                break
                    if node.name.startswith("__") and node.name.endswith("__"):
                        decos["dunder:" + node.name] += 1
                elif isinstance(node, ast.Call):
                    f2 = node.func
                    nm = f2.id if isinstance(f2, ast.Name) else None
                    if nm in INTEREST_CALLS:
                        calls[nm] += 1
                    if any(isinstance(a, ast.Starred) for a in node.args): fc["call_star"] += 1
                    if any(k.arg is None for k in node.keywords): fc["call_starstar"] += 1
                else:
                    if t in ("Match","Lambda","Yield","YieldFrom","Await","Global","Nonlocal","With","AsyncWith","Try","TryStar","Raise","Assert","Delete","ListComp","SetComp","DictComp","GeneratorExp","NamedExpr","JoinedStr","Starred","While","For","IfExp","TypeAlias","Slice"):
                        fc[t] += 1
            C.update(fc)
            per_file[rel] = {"lines": n, **{k: v for k, v in fc.items() if k in ("class","def","Match","Yield","nested_def_or_lambda","Lambda")}}

json.dump({"files": files, "lines": lines, "counts": C.most_common(), "imports": imports.most_common(),
           "import_sites": {k: sorted(v)[:8] for k, v in import_sites.items()},
           "multi": multi, "metas": metas, "decos": decos.most_common(), "calls": calls.most_common(),
           "typing": typing_names.most_common(), "per_file": per_file}, open(out, "w"), indent=1)
print(files, lines)
print("counts", C.most_common())
print("calls", calls.most_common())
