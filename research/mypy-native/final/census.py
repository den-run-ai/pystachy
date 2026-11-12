"""Count the uses of typing.Final and typing.final in Python sources, by form.

    python3 -I census.py LABEL=DIR [LABEL=DIR ...] [--json OUT] [--examples N]

Reads sources with ast only; nothing is imported or run. A name counts when the file
imports it from typing or typing_extensions (also through a module alias); files that
do not parse are counted and skipped.
"""

import ast
import json
import os
import sys

FORMS = [
    "module: X: Final = v",
    "module: X: Final[T] = v",
    "module: X: Final[T]",
    "class: X: Final = constant",
    "class: X: Final = other value",
    "class: X: Final[T] = v",
    "class: X: Final[T]",
    "method: self.x: Final = v",
    "method: self.x: Final[T] = v",
    "function: x: Final = v",
    "function: x: Final[T] = v",
    "other Final",
    "@final class",
    "@final method",
    "@final function",
]


def names_of(tree):
    """the local names that mean Final / final, and the module aliases of typing"""
    final_ann, final_dec, mods = set(), set(), set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module in ("typing", "typing_extensions"):
            for a in n.names:
                if a.name == "Final":
                    final_ann.add(a.asname or a.name)
                elif a.name == "final":
                    final_dec.add(a.asname or a.name)
        elif isinstance(n, ast.Import):
            for a in n.names:
                if a.name in ("typing", "typing_extensions"):
                    mods.add(a.asname or a.name)
    return final_ann, final_dec, mods


def is_ref(n, names, mods, attr):
    if isinstance(n, ast.Name):
        return n.id in names
    return isinstance(n, ast.Attribute) and n.attr == attr and isinstance(n.value, ast.Name) and n.value.id in mods


def final_kind(ann, names, mods):
    """'' (not Final), 'bare' or 'sub'; a string annotation is parsed"""
    if isinstance(ann, ast.Constant) and isinstance(ann.value, str):
        try:
            ann = ast.parse(ann.value, mode="eval").body
        except SyntaxError:
            return ""
    if is_ref(ann, names, mods, "Final"):
        return "bare"
    if isinstance(ann, ast.Subscript) and is_ref(ann.value, names, mods, "Final"):
        return "sub"
    return ""


def constant(v):
    if isinstance(v, ast.UnaryOp) and isinstance(v.op, (ast.USub, ast.UAdd)):
        v = v.operand
    return isinstance(v, ast.Constant) and isinstance(v.value, (int, float, str, bytes, bool))


def value_kind(v):
    if constant(v):
        return "constant"
    if isinstance(v, (ast.List, ast.Dict, ast.Set, ast.Tuple)):
        return type(v).__name__.lower() + " display"
    if isinstance(v, ast.Call):
        return "call"
    if isinstance(v, (ast.Name, ast.Attribute)):
        return "name"
    if isinstance(v, (ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)):
        return "comprehension"
    return "expression"


class Census(ast.NodeVisitor):
    def __init__(self, path, names, decs, mods, out):
        self.path, self.names, self.decs, self.mods, self.out = path, names, decs, mods, out
        self.scope = ["module"]

    def add(self, form, node, detail=""):
        self.out.append((form, f"{self.path}:{node.lineno}", detail))

    def decorated(self, node, form):
        for d in node.decorator_list:
            if is_ref(d, self.decs, self.mods, "final"):
                self.add(form, node)

    def visit_ClassDef(self, node):
        self.decorated(node, "@final class")
        self.scope.append("class")
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node):
        self.decorated(node, "@final method" if self.scope[-1] == "class" else "@final function")
        self.scope.append("method" if self.scope[-1] == "class" else "function")
        self.generic_visit(node)
        self.scope.pop()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_AnnAssign(self, node):
        k = final_kind(node.annotation, self.names, self.mods)
        if k:
            s = self.scope[-1]
            t = node.target
            ann = "Final" if k == "bare" else "Final[T]"
            if isinstance(t, ast.Attribute):
                if isinstance(t.value, ast.Name) and t.value.id == "self" and node.value is not None:
                    self.add(f"method: self.x: {ann} = v", node)
                else:
                    self.add("other Final", node, "attribute target")
            elif node.value is None:
                if k == "sub" and s in ("module", "class"):
                    self.add(f"{s}: X: Final[T]", node)
                else:
                    self.add("other Final", node, f"{s}: no value")
            elif s == "class" and k == "bare":
                vk = value_kind(node.value)
                self.add("class: X: Final = constant" if vk == "constant" else "class: X: Final = other value", node, vk)
            elif s == "class":
                self.add("class: X: Final[T] = v", node)
            elif s == "module":
                self.add(f"module: X: {ann} = v", node, value_kind(node.value))
            else:
                self.add(f"function: x: {ann} = v", node)
        self.generic_visit(node)


def scan(root):
    out, files, bad, using = [], 0, 0, 0
    for d, subdirs, fs in os.walk(root):
        subdirs.sort()
        for f in sorted(fs):
            if not f.endswith(".py"):
                continue
            p = os.path.join(d, f)
            files += 1
            try:
                with open(p, "rb") as h:
                    tree = ast.parse(h.read())
            except (SyntaxError, ValueError, RecursionError):
                bad += 1
                continue
            names, decs, mods = names_of(tree)
            if not (names or decs or mods):
                continue
            n = len(out)
            Census(os.path.relpath(p, root), names, decs, mods, out).visit(tree)
            using += len(out) > n
    return out, files, bad, using


def main():
    args = sys.argv[1:]
    jout, nex = "", 0
    if "--json" in args:
        i = args.index("--json")
        jout = args[i + 1]
        del args[i : i + 2]
    if "--examples" in args:
        i = args.index("--examples")
        nex = int(args[i + 1])
        del args[i : i + 2]
    result = {}
    for a in args:
        label, root = a.split("=", 1)
        out, files, bad, using = scan(root)
        counts = {f: 0 for f in FORMS}
        details = {}
        for form, where, detail in out:
            counts[form] += 1
            if detail:
                details.setdefault(form, {}).setdefault(detail, 0)
                details[form][detail] += 1
        result[label] = {"files": files, "unparsed": bad, "files_using": using, "counts": counts, "details": details}
        print(f"== {label}: {files} files ({bad} unparsed), {using} use Final/final, {len(out)} uses")
        for f in FORMS:
            if counts[f]:
                d = details.get(f)
                print(f"  {counts[f]:6d}  {f}" + (f"   {d}" if d else ""))
                for form, where, detail in [o for o in out if o[0] == f][:nex]:
                    print(f"            {where} {detail}")
    if jout:
        with open(jout, "w") as h:
            json.dump(result, h, indent=1, sort_keys=True)
            h.write("\n")


main()
