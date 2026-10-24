"""Mark bounded straight-line stores that may start a new native local slot.

The code generator decides from the actual types whether a slot is needed. The
source names stay intact, preserving target-context and look-ahead inference.
"""
from __future__ import annotations
from src.pystachy_compiler.analysis import local_names
from src.pystachy_compiler.ir import FnInfo
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
        if p.kids[0].kind != "noann" and not (f.cmpfields != "" and f.cmprebind == "" and len(f.params) == 2 and p.s == f.params[1]):
            blocked[p.s] = True  # an explicit annotation remains a contract
    for n in body:
        if not versionable(n, blocked):
            return []
    out: list[Node] = []
    marked = False
    for n in body:
        c = clone(n)
        if n.kind == "assign" and n.s == "" and len(n.kids) == 2 and n.kids[0].kind == "name" and n.kids[0].s not in blocked:
            c.s = "local-retype"
            marked = True
        out.append(c)
    return out if marked else []
