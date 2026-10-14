"""Bounded, opt-in straight-line local binding versions.

Each unconditional rebinding can get a fresh native slot. Existing typing still
checks every expression and every branch/loop store; this pass introduces no
dynamic values and makes no assumptions from runtime observations.
"""
from __future__ import annotations
from src.pystachy_compiler.analysis import local_names
from src.pystachy_compiler.ir import FnInfo
from src.pystachy_compiler.syntax import Node
from src.pystachy_compiler.utils import clone


def versionable(n: Node, blocked: dict[str, bool]) -> bool:
    # These constructs can expose cells, defer reads, bind outside this walk, or
    # observe a partly executed assignment. Retain the existing compiler path.
    if n.kind in "def lambda class subclass try with global nonlocal walrus yield await listcomp nestedcomp asynccomp setcomp dictcomp match import bound".split():
        return False
    if n.kind == "annassign" and n.kids[0].kind == "name":
        blocked[n.kids[0].s] = True
    if n.kind == "del":
        local_names([n], blocked)
    for k in n.kids:
        if not versionable(k, blocked):
            return False
    return True


def version_names(n: Node, versions: dict[str, str]) -> None:
    if n.kind == "name" and n.s in versions:
        n.s = versions[n.s]
    for k in n.kids:
        version_names(k, versions)


def local_versions(f: FnInfo, body: list[Node]) -> list[Node]:
    # A closure's environment and *args escape tracking also refer to original
    # binding names. Keep them unchanged until their analyses understand versions.
    if f.clo >= 0 or f.vararg >= 0 or f.kwarg >= 0 or f.node.kind != "def":
        return body
    blocked: dict[str, bool] = dict(f.uflags)
    for p in f.node.kids[0].kids:
        if p.kids[0].kind != "noann":
            blocked[p.s] = True  # an explicit annotation remains a contract
    for n in body:
        if not versionable(n, blocked):
            return body
    seen: dict[str, bool] = {}
    for name in f.params:
        seen[name] = True
    versions: dict[str, str] = {}
    out: list[Node] = []
    serial = 0
    for n in body:
        c = clone(n)
        if n.kind == "assign" and len(n.kids) == 2 and n.kids[0].kind == "name":
            name = n.kids[0].s
            # The RHS reads the preceding binding, even in x = convert(x).
            version_names(c.kids[1], versions)
            if name in seen and name not in blocked:
                serial += 1
                versions[name] = name + ".flow." + str(serial)
            c.kids[0].s = versions.get(name, name)
        else:
            # No new versions inside branches or loops: their stores retain the
            # existing single-slot checks, and joins cannot silently change type.
            version_names(c, versions)
        local_names([n], seen)
        out.append(c)
    return out if serial > 0 else body
