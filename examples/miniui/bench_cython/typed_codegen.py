"""Generate a separately labelled Cython static-layout implementation.

The existing classes become extension classes, their declared fields and hot
locals have C types, and hot methods become cpdef methods. Algorithm statements
are otherwise retained through ast.unparse; all containers remain Python
list/set and strings remain Python str. The particle list is deliberately not a
C array: scalar list reads are explicitly unboxed to double for arithmetic.
"""
from __future__ import annotations

import ast
from pathlib import Path
import re
import textwrap

# These helpers only forward already-typed scalar arguments to the C adapter.
# Keep helpers that allocate/validate strings, Python exports and UI methods on
# Cython's normal exception path. This list is deliberately explicit so a later
# helper with different behavior cannot silently acquire a noexcept contract.
NOEXCEPT_HELPERS = (
    "_close", "_open", "_focused", "_mouse_x", "_mouse_y", "_mouse", "_keys",
    "_character", "_dt", "_begin", "_end", "_clip", "_rect",
)


def with_scalar_noexcept(bindings: str) -> str:
    """Change only the exception declarations of known non-raising helpers."""
    for name in NOEXCEPT_HELPERS:
        pattern = r"^(cdef (?:void|int|double) " + re.escape(name) + r"\([^\n]*\)):$"
        bindings, changed = re.subn(pattern, r"\1 noexcept:", bindings, flags=re.MULTILINE)
        if changed != 1:
            raise ValueError("expected exactly one unmodified scalar helper: " + name)
    return bindings


FIELDS = {
    "Rect": {"long long": "x y w h"},
    "Input": {"long long": "x y", "bint": "down pressed released focused backspace delete left right home end tab shift enter space escape", "str": "text"},
    "Command": {"long long": "kind size caret", "Rect": "rect clip", "unsigned int": "color", "str": "text"},
    "Style": {"long long": "padding gap height font_size", "unsigned int": "background panel base hover active accent text muted"},
    "UI": {"long long": "width height cursor column y row_height", "Style": "style", "list": "commands order widths", "str": "active focus edit_id", "Input": "input", "bint": "accept_input started", "Rect": "clip area", "set": "ids"},
    "Window": {"bint": "closed"},
    "State": {"UI": "ui", "bint": "running", "double": "speed", "str": "name", "list": "positions"},
}
LOCALS = {
    "Rect.intersect": {"long long": "x y"},
    "UI.begin": {"long long": "pad", "Py_ssize_t": "index"},
    "UI.row": {"long long": "fixed flexible width remaining", "list": "resolved"},
    "UI._next": {"long long": "x", "Py_ssize_t": "i", "Rect": "rect"},
    "UI._text": {"long long": "inset", "Rect": "inner"},
    "UI._control": {"Rect": "visible", "bint": "hot"},
    "UI._clicked": {"bint": "mouse keyboard"},
    "UI._box": {"unsigned int": "color"},
    "UI.panel": {"Rect": "rect"},
    "UI.button": {"Rect": "rect", "bint": "hot"},
    "UI.checkbox": {"Rect": "rect box", "bint": "hot", "long long": "size"},
    "UI.slider": {"Rect": "rect", "bint": "hot", "long long": "span", "double": "fraction step"},
    "UI.progress": {"Rect": "rect"},
    "UI.textbox": {"Rect": "rect", "bint": "hot", "long long": "caret code", "str": "inserted char"},
    "Window.poll": {"int": "mouse keys code", "Input": "events"},
    "Window.draw": {"Command": "command", "Rect": "rect clip", "long long": "last_x last_y last_w last_h cursor offset"},
    "State.__init__": {"Py_ssize_t": "i"},
    "State.simulate": {"list": "positions", "bint": "running", "double": "speed dt", "Py_ssize_t": "i"},
    "State.make_ui": {"UI": "ui", "list": "positions", "bint": "running", "double": "speed dt", "Py_ssize_t": "i"},
    "State.checksum": {"long long": "value item", "double": "position", "Command": "command", "str": "char"},
    "loop": {"Py_ssize_t": "_ i", "Input": "events"},
    "run": {"State": "state", "Window": "window", "double": "started elapsed"},
}


def ctype(annotation: ast.expr | None, name: str = "") -> str:
    if name == "color":
        return "unsigned int"
    if annotation is None:
        return "object"
    value = ast.unparse(annotation).strip("'\"")
    return {"int": "long long", "bool": "bint", "float": "double", "None": "void",
            "list[int]": "list", "list[float]": "list", "list[Command]": "list",
            "set[str]": "set"}.get(value, value)


class RemoveAssignmentsAnnotations(ast.NodeTransformer):
    def visit_AnnAssign(self, node):
        if node.value is None:
            return None
        return ast.copy_location(ast.Assign(targets=[node.target], value=node.value), node)


def function_signature(node: ast.FunctionDef, declaration: bool = False) -> str:
    special = node.name.startswith("__")
    parts = []
    required = len(node.args.args) - len(node.args.defaults)
    for index, arg in enumerate(node.args.args):
        entry = arg.arg if arg.arg == "self" else ctype(arg.annotation, arg.arg) + " " + arg.arg
        if index >= required:
            entry += "=*" if declaration else "=" + ast.unparse(node.args.defaults[index - required])
        parts.append(entry)
    prefix = "def " if special else "cpdef " + ctype(node.returns) + " "
    return prefix + node.name + "(" + ", ".join(parts) + ")"


def generate_function(node: ast.FunctionDef, owner: str = "") -> tuple[str, str | None]:
    key = owner + "." + node.name if owner else node.name
    statements = [RemoveAssignmentsAnnotations().visit(statement) for statement in node.body]
    statements = [statement for statement in statements if statement is not None]
    body = "\n".join(ast.unparse(statement) for statement in statements)
    if key in ("State.simulate", "State.make_ui"):
        old = "positions[i] + dt"
        assert body.count(old) == 1
        body = body.replace(old, "<double>positions[i] + dt")
    if key == "State.make_ui":
        old = "int(positions[i])"
        assert body.count(old) == 1
        body = body.replace(old, "int(<double>positions[i])")
    definitions = []
    for typ, names in LOCALS.get(key, {}).items():
        definitions.append("cdef " + typ + " " + ", ".join(names.split()))
    if definitions:
        body = "\n".join(definitions) + "\n" + body
    definition = function_signature(node) + ":\n" + textwrap.indent(body, "    ")
    declaration = None if node.name.startswith("__") else function_signature(node, declaration=True)
    return definition, declaration


def generate_module(source: str, imports: str = "") -> tuple[str, str]:
    tree = ast.parse(source)
    definitions = []
    declarations = []
    if imports:
        definitions.append(imports)
        declarations.append(imports)
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            methods = []
            members = []
            for typ, names in FIELDS[node.name].items():
                members.append("cdef public " + typ + " " + ", ".join(names.split()))
            for statement in node.body:
                if isinstance(statement, ast.FunctionDef):
                    definition, declaration = generate_function(statement, node.name)
                    methods.append(definition)
                    if declaration:
                        members.append(declaration)
                elif isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant):
                    methods.append(ast.unparse(statement))
                else:
                    raise ValueError("unsupported class statement: " + ast.dump(statement))
            definitions.append("cdef class " + node.name + ":\n" + textwrap.indent("\n\n".join(methods), "    "))
            declarations.append("cdef class " + node.name + ":\n" + textwrap.indent("\n".join(members), "    "))
        elif isinstance(node, ast.FunctionDef):
            definition, declaration = generate_function(node)
            definitions.append(definition)
            if declaration:
                declarations.append(declaration)
        elif isinstance(node, ast.ImportFrom) and node.module in ("miniui", "raylib_backend"):
            # Their types and native functions are provided by the C import above.
            continue
        else:
            definitions.append(ast.unparse(node))
    return "\n\n".join(definitions) + "\n", "\n\n".join(declarations) + "\n"


def generate(target: Path, source: Path, bindings: str, with_workload: bool) -> None:
    core, core_pxd = generate_module((source / "miniui.py").read_text())
    (target / "miniui.pyx").write_text(core)
    (target / "miniui.pxd").write_text(core_pxd)
    backend = (source / "raylib_backend.py").read_text()
    window = backend[backend.index("class Window:"):]
    backend_pyx, backend_pxd = generate_module(window, "from miniui cimport Rect, Input, Command, UI")
    native_declarations = "\n".join(re.findall(r"^(cdef (?:void|int|double) _[^\n]+):$", bindings, re.MULTILINE))
    (target / "raylib_backend.pyx").write_text(bindings + "\n" + backend_pyx)
    (target / "raylib_backend.pxd").write_text(native_declarations + "\n" + backend_pxd)
    if with_workload:
        workload_pyx, workload_pxd = generate_module((source / "benchmark_workload.py").read_text(),
            "from miniui cimport Rect, Input, Command, UI\nfrom raylib_backend cimport Window, _rect")
        (target / "benchmark_workload.pyx").write_text(workload_pyx)
        (target / "benchmark_workload.pxd").write_text(workload_pxd)
