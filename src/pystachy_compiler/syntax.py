"""Syntax component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.diagnostics import MAXNEST, TOODEEP, fail


class Node:
    def __init__(self, kind: str, s: str, line: int):
        self.kind = kind
        self.s = s
        self.line = line
        self.kids: list[Node] = []
        self.chk = False  # a variable read that may find the variable unassigned
        # An import binding that may be unbound: "<its flag> <name> <L (a local) or G>" (see
        # Loader.import_binds); M checks a source module attribute and I a from-import of it.
        # Then, ";"-separated, "<submodule> <name> A" for each submodule that
        # an import in a try statement runs which the read takes as its package's attribute
        # (Loader.trysubs); else ""
        self.mchk = ""
        self.depth = 1  # levels of nodes from this one down, as mk counted them


def mk(kind: str, s: str, line: int, kids: list[Node]) -> Node:
    n = Node(kind, s, line)
    n.kids = kids
    for k in kids:
        if k.depth >= n.depth:
            n.depth = k.depth + 1
    d = n
    while n.depth > MAXNEST and len(d.kids) > 0:
        # a chain such as a + b + ..., which the parser builds without recursing: the error is on the
        # line of its deepest node
        for k in d.kids:
            if k.depth == d.depth - 1:
                d = k
                break
    if n.depth > MAXNEST:
        fail(TOODEEP, d.line)
    return n


def mentions(n: Node, names: list[str]) -> bool:
    # does expression n use one of names
    if n.kind == "name" and n.s in names:
        return True
    for k in n.kids:
        if mentions(k, names):
            return True
    return False


def flat_del(n: Node, out: list[Node]) -> None:
    if n.kind == "tuple" or n.kind == "list":
        for k in n.kids:
            flat_del(k, out)
    else:
        out.append(n)


def as_target(n: Node) -> Node:
    # [a, b] = ... and for [a, b] in ...: a list display as a target unpacks like a tuple
    if n.kind == "list" or n.kind == "tuple":
        n.kind = "tuple"
        for k in n.kids:
            as_target(k)
    return n


def dc_args(d: Node) -> str:
    # the arguments of a @dataclass(...) decorator d: "kw" for kw_only=True, "" for none (or
    # kw_only=False), "!" and the error for any other
    r = ""
    if len(d.kids) > 0 and d.kids[0].kind != "call":
        return "!@dataclass(...) with arguments is not supported"
    for a in d.kids[0].kids[1:] if len(d.kids) > 0 else []:
        if a.kind != "kw" or a.s != "kw_only":
            return "!@dataclass(" + (a.s + "=..." if a.kind == "kw" else "...") + ") is not supported: of its arguments, only kw_only= is"
        if a.kids[0].kind != "True" and a.kids[0].kind != "False":
            return "!@dataclass(kw_only=...) needs True or False"
        r = "kw" if a.kids[0].kind == "True" else ""
    return r


def name_targets(t: Node) -> bool:
    # whether the targets of an assignment are only names, which no store to another can change
    if t.kind == "tuple":
        for k in t.kids:
            if not name_targets(k):
                return False
        return True
    return t.kind == "name"


# CPython's name for an expression in its "cannot assign to" errors (_PyPegen_get_expr_name)
EXPRNAMES: dict[str, str] = {
    "attr": "attribute", "index": "subscript", "slice": "subscript", "starred": "starred", "name": "name", "list": "list",
    "tuple": "tuple", "lambda": "lambda", "call": "function call", "binop": "expression", "unary": "expression",
    "boolop": "expression", "yield": "yield expression", "await": "await expression", "setcomp": "set comprehension",
    "dictcomp": "dict comprehension", "dict": "dict literal", "dictstar": "dict literal", "set": "set display",
    "fstr": "f-string expression", "str": "literal", "int": "literal", "float": "literal", "complex": "literal",
    "bytes": "literal", "None": "None", "True": "True", "False": "False", "ellipsis": "ellipsis", "cmp": "comparison",
    "ifexp": "conditional expression", "walrus": "named expression",
}


def expr_name(n: Node) -> str:
    if n.kind == "listcomp" or n.kind == "nestedcomp" or n.kind == "asynccomp":
        return "generator expression" if n.s == "gen" else "list comprehension"
    return EXPRNAMES.get(n.kind, "expression")


def start(n: Node) -> int:
    # the line expression n starts on (an operator, call, attribute or subscript node has its
    # operator's line)
    k = n.kind
    if k == "binop" or k == "boolop" or k == "cmp" or k == "call" or k == "attr" or k == "index" or k == "slice":
        return start(n.kids[0])
    if k == "ifexp":
        return start(n.kids[1])
    return n.line


def bad_target(n: Node, delete: bool, out: list[Node]) -> None:
    # the first part of target n that cannot be assigned to (or deleted), as CPython's parser finds it
    k = n.kind
    if len(out) > 0:
        return
    if k == "tuple" or k == "list":
        for x in n.kids:
            bad_target(x, delete, out)
    elif k == "starred" and not delete:
        bad_target(n.kids[0], delete, out)
    elif k != "name" and k != "attr" and k != "index" and k != "slice":
        out.append(n)


STARTS: dict[str, bool] = {}
for _k in "id int float str fstr rfstr bytes complex ... ( [ { - + ~ not None True False lambda yield await".split():
    STARTS[_k] = True
CMPOPS: dict[str, bool] = {"<": True, ">": True, "==": True, ">=": True, "<=": True, "!=": True, "in": True}
LAMBDAS: list[int] = [0]  # the lambdas parsed so far (see Parser.test1)
AUGOPS: dict[str, bool] = {}
for _k in "+= -= *= /= //= %= **= &= |= ^= <<= >>= @=".split():
    AUGOPS[_k] = True
BINOPS: list[list[str]] = [["|"], ["^"], ["&"], ["<<", ">>"], ["+", "-"], ["*", "/", "//", "%", "@"]]


def names_in(t: Node, out: list[str]) -> None:
    # the names target t binds: a name, or those of a tuple, list or starred target
    if t.kind == "name":
        out.append(t.s)
    elif t.kind == "tuple" or t.kind == "list" or t.kind == "starred":
        for k in t.kids:
            names_in(k, out)

def has_kind(n: Node, kind: str) -> bool:
    # does n hold a node of kind (outside the functions, classes and lambdas it defines)
    if n.kind == kind:
        return True
    if n.kind == "def" or n.kind == "class" or n.kind == "subclass" or n.kind == "lambda":
        return False
    for k in n.kids:
        if has_kind(k, kind):
            return True
    return False


def has_value_return(n: Node) -> bool:
    # Explicit None and bare returns keep ordinary void functions eager. Nested
    # functions' returns do not determine the enclosing function's signature.
    if n.kind == "return":
        return len(n.kids) > 0 and n.kids[0].kind != "None"
    if n.kind in ["def", "class", "subclass", "lambda"]:
        return False
    for k in n.kids:
        if has_value_return(k):
            return True
    return False
