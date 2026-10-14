"""Profile-guided annotations: the types one CPython run observes, written where the source has none.

usage: python3 tools/trace_annotate.py PROGRAM.py -o ANNOTATED.py [--report REPORT.json] [-- ARGS...]

The program runs once under CPython with a profile hook. The hook records the classes of every
parameter and return of the program's own functions, and samples instance fields: of `self` when a
method returns, of user objects passed as arguments, and of module-level objects. It reads only
`type()`, raw instance dictionaries, slots and built-in containers, so no `__getattr__`, `__eq__` or
`__hash__` of the program runs. Recorded classes join as Pystachy's typing does
(docs/language/typing.md): `None` makes a type optional, different user classes join to their
nearest common base, an empty container takes its item type from the other observations, and
`int`, `bool` and `float` stay distinct. A call through a base annotation must accept every
override, so same-named methods of one hierarchy with the same number of parameters share one
joined signature. Constructors are not dispatched: each keeps its own observations, and a
parameter that saw only `None` borrows the nearest base constructor's.

Only missing annotations are added: parameters, returns, and the first plain `self.f = ...` of each
`__init__` (a field first stored another way, as in `self.x = x = ...`, is declared in the class
body). A position whose observations do not join (mixed types, only `None`, or only empty
containers) is left unannotated and listed in the report with its counts: calls for parameters and
returns, sampled snapshots for fields. They show where a static subset needs another
representation; they are not counts of operations. The output is `ast.unparse`d with
`from __future__ import annotations`, since recorded classes may be forward references; comments
are not kept. Observations cover one run's paths only.
"""
import argparse
import ast
from collections import Counter, defaultdict
import inspect
import json
import sys

CONTAINERS = (list, set, dict, tuple)


def fields_of(value):
    """The fields of a program object (its instance dictionary and set slots), without calling its code."""
    if type(value).__module__ != "__main__" or isinstance(value, type):
        return None
    try:
        d = object.__getattribute__(value, "__dict__")
    except AttributeError:
        d = {}
    fields = dict(d) if type(d) is dict else {}
    for cls in type(value).__mro__:
        slots = cls.__dict__.get("__slots__", ())
        for name in [slots] if isinstance(slots, str) else list(slots):
            if name not in ("__dict__", "__weakref__"):
                try:  # a slot's member descriptor; an unset slot raises without __getattr__
                    fields[name] = object.__getattribute__(value, name)
                except AttributeError:
                    pass
    return fields if fields or type(d) is dict else None


def common_base(classes):
    """The nearest common base of program classes other than object, or None."""
    for c in classes[0].__mro__:
        if c is not object and all(c in k.__mro__ for k in classes[1:]):
            return c
    return None


def deep(value, depth=0):
    """A Pystachy-style type name for one value, sampling up to 16 container items."""
    t = type(value)
    if value is None:
        return "None"
    if t in (list, set) and depth < 2:
        sample = list(value)[:16]
        kinds = {type(x) for x in sample}
        users = [k for k in kinds if k.__module__ == "__main__"]
        if users and len(users) == len(kinds - {type(None)}):
            base = common_base(users)
            if base is None:
                return "MIXED"
            return f"{t.__name__}[{base.__qualname__}{' | None' if type(None) in kinds else ''}]"
        items = {deep(x, depth + 1) for x in sample}
        if not items:
            return f"{t.__name__}[?]"
        return f"{t.__name__}[{items.pop()}]" if len(items) == 1 else "MIXED"
    if t is dict and depth < 2:
        keys = {deep(k, depth + 1) for k in list(value)[:16]}
        values = {deep(v, depth + 1) for v in list(value.values())[:16]}
        if not keys:
            return "dict[?]"
        return f"dict[{keys.pop()}, {values.pop()}]" if len(keys) == 1 and len(values) == 1 else "MIXED"
    if t is tuple and depth < 2 and len(value) <= 9:
        return "tuple[" + ", ".join(deep(x, depth + 1) for x in value) + "]" if value else "tuple[()]"
    if t in CONTAINERS:
        return "MIXED"
    return t.__qualname__ if t.__module__ in ("__main__", "builtins") else "MIXED"


class Recorder:
    """Profile-hook observations of one program file."""

    def __init__(self, path, namespace):
        self.path = path
        self.namespace = namespace
        self.params = defaultdict(lambda: defaultdict(Counter))   # (name, line) -> parameter -> types
        self.objects = defaultdict(lambda: defaultdict(Counter))  # object class -> field -> types
        self.globals = []
        self.size = -1
        self.events = 0

    def sample(self, value):
        d = fields_of(value)
        if d is not None:
            fields = self.objects[type(value).__qualname__]
            for name, item in list(d.items()):
                fields[name][deep(item)] += 1

    def hook(self, frame, event, arg):
        code = frame.f_code
        # Functions only: module and class bodies run without fast locals (CO_OPTIMIZED).
        if code.co_filename != self.path or event not in ("call", "return") or not code.co_flags & inspect.CO_OPTIMIZED:
            return
        key = (code.co_name, code.co_firstlineno)
        if event == "call":
            for name in code.co_varnames[:code.co_argcount + code.co_kwonlyargcount]:
                if name in frame.f_locals:
                    value = frame.f_locals[name]
                    self.params[key][name][deep(value)] += 1
                    self.sample(value)
            return
        self.params[key]["return"][deep(arg)] += 1
        self.sample(frame.f_locals.get("self"))
        # Module-level objects may change only through globals: sample them too, refreshing the
        # list when the namespace grows and now and then, rather than scanning it at every return.
        self.events += 1
        if len(self.namespace) != self.size or self.events % 256 == 0:
            self.size = len(self.namespace)
            self.globals = [v for v in list(self.namespace.values()) if fields_of(v) is not None]
        for value in self.globals:
            self.sample(value)

    def finish(self):
        for value in list(self.namespace.values()):
            self.sample(value)


def join(types, classes):
    """One annotation for the observed type names, or None when they do not join."""
    names = set(types)
    if len(names) > 1 and all(n.startswith("list[") and n.endswith("]") for n in names):
        inner = set()
        for n in names:
            if n != "list[?]":
                inner |= {part.strip() for part in n[5:-1].split(" | ")}
        item = join(inner, classes) if inner else None
        return f"list[{item}]" if item else None
    optional = "None" in names and len(names) > 1
    if optional:
        names.discard("None")
    if len(names) > 1 and all(n in classes for n in names):
        base = common_base([classes[n] for n in sorted(names)])
        if base is not None:
            names = {base.__qualname__}
    if len(names) != 1:
        return None
    name = names.pop()
    if "MIXED" in name or "?" in name:
        return None
    return f"{name} | None" if optional else name


def unjoined(where, line, samples):
    names = set(samples)
    reason = "only None observed" if names == {"None"} else ("empty container" if any("?" in n for n in names) else "mixed")
    return {"where": where, "line": line, "reason": reason, "samples": dict(samples)}


def hierarchy_root(cls):
    return [k for k in cls.__mro__ if k is not object][-1].__qualname__


def annotate(source, recorder, classes):
    """The annotated module source and a report of what was added or left mixed."""
    tree = ast.parse(source)
    params = recorder.params
    mixed = []
    added = 0
    # Same-named, same-arity methods of one hierarchy share one joined signature.
    family = defaultdict(list)
    inits = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name in classes:
            for f in node.body:
                if isinstance(f, ast.FunctionDef) and f.args.args and f.args.args[0].arg == "self":
                    if f.name == "__init__":
                        inits[node.name] = f
                    else:
                        family[(hierarchy_root(classes[node.name]), f.name, len(f.args.args))].append(f)
    # Constructors are not dispatched through a base: each keeps its own observations (a subclass
    # may ignore an argument, as Richards' IdleTask does). A parameter that saw only None borrows
    # the nearest base constructor's observations at its position, since constructors usually
    # forward to it.
    for name, f in inits.items():
        k = (f.name, f.lineno if not f.decorator_list else f.decorator_list[0].lineno)
        for i in range(1, len(f.args.args)):
            own = params[k].get(f.args.args[i].arg)
            if own and set(own) != {"None"}:
                continue
            for base in classes[name].__mro__[1:]:
                g = inits.get(base.__qualname__)
                if g is None or len(g.args.args) != len(f.args.args):
                    continue
                theirs = params[(g.name, g.lineno if not g.decorator_list else g.decorator_list[0].lineno)].get(g.args.args[i].arg)
                if theirs:
                    params[k][f.args.args[i].arg] = Counter(own or {}) + Counter(theirs)
                    break
    for methods in family.values():
        if len(methods) < 2:
            continue
        keys = [(f.name, f.lineno if not f.decorator_list else f.decorator_list[0].lineno) for f in methods]
        for i in range(1, len(methods[0].args.args)):
            joined = Counter()
            for f, k in zip(methods, keys):
                joined.update(params[k][f.args.args[i].arg])
            for f, k in zip(methods, keys):
                params[k][f.args.args[i].arg] = Counter(joined)
        joined = Counter()
        for k in keys:
            joined.update(params[k]["return"])
        for k in keys:
            params[k]["return"] = Counter(joined)
    owners = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            for f in node.body:
                owners[id(f)] = node.name
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        key = (node.name, node.lineno if not node.decorator_list else node.decorator_list[0].lineno)
        if key not in params:
            continue
        where = (owners[id(node)] + "." if id(node) in owners else "") + node.name
        for a in node.args.args + node.args.kwonlyargs:
            seen = params[key].get(a.arg)
            if a.annotation is not None or a.arg in ("self", "cls") or not seen:
                continue
            t = join(seen, classes)
            if t and t != "None":
                a.annotation = ast.parse(t, mode="eval").body
                added += 1
            else:
                mixed.append(unjoined(f"{where}:{a.arg}", node.lineno, seen))
        seen = params[key].get("return")
        if node.returns is None and seen:
            t = join(seen, classes)
            if t:
                node.returns = ast.parse(t, mode="eval").body
                added += 1
            else:
                mixed.append(unjoined(f"{where}:return", node.lineno, seen))
        owner = owners.get(id(node))
        if node.name != "__init__" or owner not in classes:
            continue
        # Fields: the join over instances of this class and of its subclasses.
        seen_fields = defaultdict(Counter)
        for cname, fields in recorder.objects.items():
            if cname in classes and issubclass(classes[cname], classes[owner]):
                for f, types in fields.items():
                    seen_fields[f].update(types)
        done = set()
        for parent in ast.walk(node):
            body = getattr(parent, "body", None)
            if not isinstance(body, list):
                continue
            for i, st in enumerate(body):
                if not (isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Attribute)
                        and isinstance(st.targets[0].value, ast.Name) and st.targets[0].value.id == "self"):
                    continue
                name = st.targets[0].attr
                if name in done or not seen_fields.get(name):
                    continue
                done.add(name)
                t = join(seen_fields[name], classes)
                if t and t != "None":
                    body[i] = ast.copy_location(ast.AnnAssign(target=st.targets[0], annotation=ast.parse(t, mode="eval").body,
                                                              value=st.value, simple=0), st)
                    added += 1
                else:
                    mixed.append(unjoined(f"{owner}.{name} (field)", st.lineno, seen_fields[name]))
        # A field first stored another way (`self.x = x = ...`) is declared in the class body instead,
        # which changes nothing at run time for an undecorated class with ordinary bases.
        cls = next(c for c in tree.body if isinstance(c, ast.ClassDef) and c.name == owner)
        plain = not cls.decorator_list and all(isinstance(b, ast.Name) and (b.id in classes or b.id == "object")
                                               for b in cls.bases) and not cls.keywords
        stored = sorted({t.attr for t in ast.walk(node) if isinstance(t, ast.Attribute) and isinstance(t.ctx, ast.Store)
                         and isinstance(t.value, ast.Name) and t.value.id == "self"} - done)
        declared = {st.target.id for st in cls.body if isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name)}
        for name in stored:
            if name in declared or not seen_fields.get(name):
                continue
            t = join(seen_fields[name], classes)
            if plain and t and t != "None":
                doc = 1 if isinstance(cls.body[0], ast.Expr) and isinstance(cls.body[0].value, ast.Constant) else 0
                cls.body.insert(doc, ast.AnnAssign(target=ast.Name(id=name, ctx=ast.Store()), annotation=ast.parse(t, mode="eval").body,
                                                   value=None, simple=1))
                added += 1
            else:
                mixed.append(unjoined(f"{owner}.{name} (field)", node.lineno, seen_fields[name]))
    future = any(isinstance(n, ast.ImportFrom) and n.module == "__future__" and any(a.name == "annotations" for a in n.names)
                 for n in tree.body)
    if not future:
        doc = 1 if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant) else 0
        tree.body.insert(doc, ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0))
    report = {"functions_observed": len(params), "annotations_added": added,
              "unannotated": sorted(mixed, key=lambda m: m["line"])}
    return ast.unparse(tree) + "\n", report


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("program")
    parser.add_argument("-o", "--output", required=True)
    parser.add_argument("--report", help="JSON report of added annotations and unjoined types")
    parser.add_argument("args", nargs="*", help="program arguments (after --)")
    options = parser.parse_args()
    path = options.program
    source = open(path, encoding="utf-8").read()
    code = compile(source, path, "exec")
    namespace = {"__name__": "__main__", "__file__": path, "__builtins__": __builtins__}
    recorder = Recorder(path, namespace)
    saved = sys.argv
    sys.argv = [path] + options.args
    status = 0
    sys.setprofile(recorder.hook)
    try:
        exec(code, namespace)
    except SystemExit as e:  # the observations so far are still valid
        status = e.code if isinstance(e.code, int) else 1
    finally:
        sys.setprofile(None)
        sys.argv = saved
    recorder.finish()
    classes = {v.__qualname__: v for v in namespace.values() if isinstance(v, type) and v.__module__ == "__main__"}
    annotated, report = annotate(source, recorder, classes)
    with open(options.output, "w", encoding="utf-8") as f:
        f.write(annotated)
    if options.report:
        with open(options.report, "w", encoding="utf-8") as f:
            f.write(json.dumps(report, indent=2) + "\n")
    print(f"{path}: {report['functions_observed']} functions observed, {report['annotations_added']} annotations added, "
          f"{len(report['unannotated'])} positions left unannotated", file=sys.stderr)
    sys.exit(status)


if __name__ == "__main__":
    main()
