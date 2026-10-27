"""Syntax component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.diagnostics import MAXNEST, TOODEEP, fail


class Node:
    def __init__(self, kind: str, s: str, line: int, kids: list[Node] | None = None):
        self.kind = kind
        self.s = s
        self.line = line
        self.kids: list[Node] = kids if kids is not None else []  # (mk's: no list made to replace)
        self.chk = False  # a variable read that may find the variable unassigned
        # An import binding that may be unbound: "<its flag> <name> <L (a local) or G>" (see
        # Loader.import_binds); M checks a source module attribute and I a from-import of it.
        # Then, ";"-separated, "<submodule> <name> A" for each submodule that
        # an import in a try statement runs which the read takes as its package's attribute
        # (Loader.trysubs); else ""
        self.mchk = ""
        self.depth = 1  # levels of nodes from this one down, as mk counted them
        self.made = False  # the variable of a comprehension the compiler makes (made_var)
        self.memo = 0  # an item of a display: where Gen.dmemo remembers its dry-run type, + 1 (Gen.dyn_dry)


# an empty list of nodes for a for loop to run over where a node has no kids to visit (for k in
# n.kids if ... else NOKIDS), which no code changes: n.kids[:0] made a list at every visit
NOKIDS: list[Node] = []


def mk(kind: str, s: str, line: int, kids: list[Node]) -> Node:
    n = Node(kind, s, line, kids)
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


def made_var(name: str, line: int) -> Node:
    # the variable of a comprehension the compiler makes of a call (sum(), print(*xs), ...),
    # which iterates its iterable once: one the program writes takes iter() of an iterator
    # object again, as CPython 3.13's does (Gen.listcomp)
    n = mk("name", name, line, [])
    n.made = True
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
    elif n.kind == "starred":
        as_target(n.kids[0])  # (a, *[b, c] = ...)
    return n


# @dataclass's options that Pystachy supports, and their defaults
DCOPTS: dict[str, bool] = {"init": True, "repr": True, "eq": True, "order": False, "unsafe_hash": False, "frozen": False,
                           "match_args": True, "kw_only": False}


def dc_args(d: Node) -> str:
    # the arguments of a @dataclass(...) decorator d: the options it turns on ("kw_only",
    # "frozen", "order", "unsafe_hash") or off ("no-init", "no-repr", "no-eq", "no-match_args"),
    # each a word; "!" and the error for any other
    on: dict[str, bool] = {}
    if len(d.kids) > 0 and d.kids[0].kind != "call":
        return "!@dataclass(...) with arguments is not supported"
    for a in d.kids[0].kids[1:] if len(d.kids) > 0 else []:
        if a.kind != "kw" or a.s not in DCOPTS:
            return "!@dataclass(" + (a.s + "=..." if a.kind == "kw" else "...") + ") is not supported: its supported arguments are " + ", ".join([k + "=" for k in DCOPTS])
        if a.kids[0].kind != "True" and a.kids[0].kind != "False":
            return f"!@dataclass({a.s}=...) needs True or False"
        on[a.s] = a.kids[0].kind == "True"
    r: list[str] = []
    for k in DCOPTS:
        if k in on and on[k] != DCOPTS[k]:
            r.append(k if on[k] else "no-" + k)
    return " ".join(r)


def name_targets(t: Node) -> bool:
    # whether the targets of a tuple assignment are only plain names, whose stores run no code
    # (a nested tuple target may: its item's __iter__ or __next__)
    for k in t.kids:
        if k.kind != "name":
            return False
    return True


def starred_target(t: Node) -> bool:
    # is t a tuple or list target with a starred item (a, *b = ...)
    return t.kind == "tuple" and len([k for k in t.kids if k.kind == "starred"]) > 0


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
    if n.kind == "listcomp" or n.kind == "asynccomp":
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

def comp_names(c: Node, out: list[str]) -> None:
    # the names comprehension c binds, its own variables: those of its for clauses' targets
    names_in(c.kids[1], out)
    for x in c.kids[3:]:
        if x.kind == "compfor":
            names_in(x.kids[0], out)

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


def other_return(n: Node) -> bool:
    # does n return a value other than iter(x) or reversed(x) (outside the functions, classes and
    # lambdas it defines): an __iter__ annotated -> Iterator[T] that does returns its iterator
    # object, as an unannotated one does, rather than the list iter(x) steps through, or the new
    # list of reversed(x)'s items (Gen.iter_ret)
    if n.kind == "return":
        e = n.kids[0] if len(n.kids) > 0 else n
        return e.kind != "return" and e.kind != "None" and not (e.kind == "call" and e.kids[0].kind == "name" and (e.kids[0].s == "iter" or e.kids[0].s == "reversed") and len(e.kids) == 2)
    if n.kind in ["def", "class", "subclass", "lambda"]:
        return False
    for k in n.kids:
        if other_return(k):
            return True
    return False
