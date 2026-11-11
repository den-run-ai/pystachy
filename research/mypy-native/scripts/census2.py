"""Second static census: idiom frequencies that map to the probe matrix (reads only)."""
import ast, collections, os, sys
root = sys.argv[1]; pkgs = sys.argv[2:]
C = collections.Counter(); generic_bases = collections.Counter(); visitor_T = collections.Counter()
generic_classes = []; accept_defs = 0; union_sizes = collections.Counter(); files = {}
mod_imports = collections.defaultdict(set); mod_lines = {}
def name(b):
    if isinstance(b, ast.Subscript): return name(b.value)
    if isinstance(b, ast.Attribute): return b.attr
    if isinstance(b, ast.Name): return b.id
    return "?"
def union_len(n):
    if isinstance(n, ast.BinOp) and isinstance(n.op, ast.BitOr):
        return union_len(n.left) + union_len(n.right)
    return 1
for pkg in pkgs:
    for dp, dn, fn in os.walk(os.path.join(root, pkg)):
        dn[:] = sorted(d for d in dn if d not in ("typeshed", "test", "test-data", "__pycache__", "lib-rt", "doc", "external", "xml"))
        for f in sorted(fn):
            if not f.endswith(".py"): continue
            p = os.path.join(dp, f); rel = os.path.relpath(p, root)
            mod = rel[:-3].replace(os.sep, "."); mod = mod[:-9] if mod.endswith(".__init__") else mod
            src = open(p, encoding="utf-8").read(); tree = ast.parse(src)
            mod_lines[mod] = src.count("\n")
            # module-level (eager) imports only, skipping TYPE_CHECKING blocks
            def top(stmts):
                for st in stmts:
                    if isinstance(st, ast.Import):
                        for a in st.names: mod_imports[mod].add(a.name)
                    elif isinstance(st, ast.ImportFrom):
                        base = st.module or ""
                        if st.level:
                            parts = mod.split(".")
                            is_pkg = f == "__init__.py"
                            parts = parts[: len(parts) - st.level + (1 if is_pkg else 0)]
                            base = ".".join(parts + ([st.module] if st.module else []))
                        mod_imports[mod].add(base)
                        for a in st.names: mod_imports[mod].add(base + "." + a.name)
                    elif isinstance(st, ast.If):
                        t = ast.unparse(st.test)
                        if "TYPE_CHECKING" in t: 
                            top(st.orelse); continue
                        top(st.body); top(st.orelse)
                    elif isinstance(st, ast.Try):
                        top(st.body); [top(h.body) for h in st.handlers]; top(st.orelse)
            top(tree.body)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    for b in node.bases:
                        if isinstance(b, ast.Subscript):
                            bn = name(b)
                            if bn == "Generic":
                                generic_classes.append(rel + ":" + node.name)
                            elif bn not in ("dict", "list", "Protocol", "NamedTuple", "TypedDict", "tuple"):
                                generic_bases[bn] += 1
                                visitor_T[bn + "[" + ast.unparse(b.slice) + "]"] += 1
                elif isinstance(node, ast.FunctionDef):
                    if node.name == "accept": accept_defs += 1
                    for a in node.args.args + node.args.kwonlyargs + node.args.posonlyargs:
                        if a.annotation is not None:
                            C["param_annotated"] += 1
                            s = ast.unparse(a.annotation)
                            if s in ("Any", "object"): C["param_" + s] += 1
                            n = union_len(a.annotation)
                            if n > 1: union_sizes[n] += 1
                        elif a.arg not in ("self", "cls"):
                            C["param_unannotated"] += 1
                    if node.returns is None: C["return_unannotated"] += 1
                    else: C["return_annotated"] += 1
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    fn2 = node.func.id
                    if fn2 == "isinstance" and len(node.args) == 2:
                        C["isinstance"] += 1
                        a0, a1 = node.args
                        if isinstance(a1, ast.Tuple): C["isinstance_tuple"] += 1
                        if isinstance(a0, ast.Attribute): C["isinstance_on_attribute"] += 1
                        elif isinstance(a0, ast.Name): C["isinstance_on_name"] += 1
                        else: C["isinstance_on_other_expr"] += 1
                    elif fn2 in ("getattr", "setattr", "hasattr") and len(node.args) >= 2:
                        C[fn2 + ("_literal" if isinstance(node.args[1], ast.Constant) else "_dynamic")] += 1
                    elif fn2 == "cast":
                        C["cast"] += 1
                elif isinstance(node, ast.AnnAssign):
                    n = union_len(node.annotation)
                    if n > 1: union_sizes[n] += 1
print("counts:", sorted(C.items()))
print("union widths in annotations (members -> sites):", sorted(union_sizes.items()))
print("classes with Generic[...] base:", len(generic_classes))
print("accept() definitions:", accept_defs)
print("subclasses of subscripted generic bases:", sum(generic_bases.values()), dict(generic_bases.most_common(14)))
print("distinct instantiations:", len(visitor_T)); print("  ", dict(visitor_T.most_common(40)))
# eager import closure
def closure(start):
    seen = set(); todo = [start]
    while todo:
        m = todo.pop()
        if m in seen or m not in mod_lines: continue
        seen.add(m)
        for i in mod_imports[m]:
            while i and i not in mod_lines and "." in i: i = i.rsplit(".", 1)[0]
            if i in mod_lines: todo.append(i)
            # parent packages are imported too
        parts = m.split(".")
        for k in range(1, len(parts)):
            todo.append(".".join(parts[:k]))
    return seen
for start in sys.stdin.read().split():
    cl = closure(start)
    ext = sorted({i.split(".")[0] for m in cl for i in mod_imports[m] if i.split(".")[0] not in ("mypy", "mypyc", "")})
    print(f"eager closure of {start}: {len(cl)} modules, {sum(mod_lines[m] for m in cl)} lines; external: {' '.join(ext)}")
    print("   not in closure:", " ".join(sorted(m for m in mod_lines if m not in cl and m.split('.')[0] == start.split('.')[0]))[:900])
