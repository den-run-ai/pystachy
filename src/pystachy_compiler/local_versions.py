"""Mark bounded straight-line stores that may start a new native local slot.

The code generator decides from the actual types whether a slot is needed. The
source names stay intact, preserving target-context and look-ahead inference.
"""
from __future__ import annotations
from src.pystachy_compiler.analysis import local_names
from src.pystachy_compiler.ir import FnInfo
from src.pystachy_compiler.specs import OBJECTC
from src.pystachy_compiler.syntax import Node
from src.pystachy_compiler.utils import clone

# These constructs can expose cells, defer reads, bind outside this walk, or
# observe a partly executed assignment (made once: versionable visits every node)
UNVERSIONED: dict[str, bool] = {}
for _k in "def lambda class subclass try with global nonlocal walrus yield await listcomp asynccomp setcomp dictcomp match import bound typealias async".split():
    UNVERSIONED[_k] = True


def versionable(n: Node, blocked: dict[str, bool]) -> bool:
    # Retain the existing compiler path for the constructs of UNVERSIONED.
    if n.kind in UNVERSIONED:
        return False
    if n.kind == "annassign" and n.kids[0].kind == "name":
        blocked[n.kids[0].s] = True
    if n.kind == "del":
        local_names([n], blocked)
    for k in n.kids:
        if not versionable(k, blocked):
            return False
    return True


def local_versions(f: FnInfo, body: list[Node]) -> list[Node]:
    # Closure environments and variadic escape tracking use the original slots.
    if f.clo >= 0 or f.vararg >= 0 or f.kwarg >= 0 or f.node.kind != "def":
        return []
    blocked: dict[str, bool] = dict(f.uflags)
    for p in f.node.kids[0].kids:
        if p.kids[0].kind != "noann" and p.s not in f.sentinels and not (f.cmpfields != "" and f.cmprebind == "" and len(f.params) == 2 and p.s == f.params[1]):
            blocked[p.s] = True  # an explicit annotation remains a contract (but a sentinel parameter's)
    for n in body:
        if not versionable(n, blocked):
            return []
    marks: list[bool] = []
    tests: list[str] = []
    marked = False
    for n in body:
        marks.append(n.kind == "assign" and n.s == "" and len(n.kids) == 2 and n.kids[0].kind == "name" and n.kids[0].s not in blocked)
        tests.append(sentinel_test(f, n))
        marked = marked or marks[len(marks) - 1] or tests[len(tests) - 1] != ""
    if not marked:
        return []  # (copied only when a store is marked: it runs for every function)
    out: list[Node] = []
    for j in range(len(body)):
        c = clone(body[j])
        if marks[j]:
            c.s = "local-retype"
        for x in c.kids[1].kids if tests[j] != "" else []:
            # (if p is S: p = v, of a sentinel parameter p: the specialization that takes S runs
            # it, whose test Gen.static decides, as straight-line code that gives p v's type)
            if x.kind == "assign" and x.s == "" and len(x.kids) == 2 and x.kids[0].kind == "name" and x.kids[0].s == tests[j]:
                x.s = "local-retype"
        out.append(c)
    return out


def sentinel_test(f: FnInfo, n: Node) -> str:
    # the sentinel parameter p (FnInfo.sentinels) of if p is S: ..., with no else, statement n
    # of f's body; else ""
    if n.kind != "if" or len(n.kids[2].kids) > 0:
        return ""
    t = n.kids[0]
    if t.kind == "cmp" and t.s == "is" and t.kids[0].kind == "name" and t.kids[1].kind == "name" and t.kids[0].s in f.sentinels and f.sentinels[t.kids[0].s] == t.kids[1].s:
        # (only an instance whose p is the sentinel itself, where Gen.static decides the test:
        # one of Any's dyn type tests it at run time, and its store is no straight-line code)
        j = f.params.index(t.kids[0].s) if t.kids[0].s in f.params else -1
        return t.kids[0].s if j >= 0 and j < len(f.ptypes) and f.ptypes[j] == OBJECTC else ""
    return ""
