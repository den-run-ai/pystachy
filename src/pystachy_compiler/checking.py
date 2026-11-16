"""Unit recovery for ``pystachy check``: failed units, bodies left out and their dependents.

An attempt is one ordinary compilation through finalization. A failure ends it with
CheckFailed; the driver starts a fresh Loader and Gen in which the failed unit's body is
left out (replaced by a raise), as an inference retry starts a fresh one. Nothing is rolled
back inside an attempt. A unit whose compilation saw the inferred result of a body left out,
or that was compiled while such a unit was being compiled, is tainted: its own failure is
reported as a possible consequence, not as an error of its own. A result seen by module code
or by a class's declaration can reach any later unit through a global or a layout: the whole
rest of the attempt is tainted then (Gen.taint's key "").
"""
from __future__ import annotations
from src.pystachy_compiler.analysis import collect
from src.pystachy_compiler.diagnostics import CheckFailed, Diagnostic, shown, where
from src.pystachy_compiler.ir import FnInfo
from src.pystachy_compiler.specs import SPECSHOW
from src.pystachy_compiler.syntax import Node, mk
from src.pystachy_compiler.utils import takes_self, typestr


def check_kind(f: FnInfo) -> str:
    # what kind of unit f's body is: "function", "method" or "closure" (a nested def or a
    # lambda), each possibly a template's instance; "module" for a module's code; "" for the
    # functions the compiler writes (helpers, dispatchers, adapters, dataclass methods)
    if f.synthetic:
        return ""
    if f.ll == "@main.init" or f.ll.startswith("@init."):
        return "module"
    if f.ll.startswith("@f."):
        return "function"
    if f.ll.startswith("@m."):
        return "method"
    if f.ll.startswith("@c."):
        return "closure"
    return ""


def check_name(f: FnInfo) -> str:
    # f as the compiler's notes name a unit: C.m(), f(), and a template's instance by the types
    # of its arguments, f(int, str), as "compiling f(int, str) for the call at ..." does; a
    # method of a class template's specialization by that specialization, Box[int].get(); an
    # inherited method's instance by its receiver's class too, Account.balance() for Savings
    who = (SPECSHOW.get(f.cls, shown(f.cls)) + "." if f.cls != "" else "") + shown(f.name)
    if not f.inst:
        return who + "()"
    ts = f.ptypes[1:] if f.clo >= 0 or takes_self(f) else f.ptypes
    who += "(" + ", ".join([typestr(t) for t in ts]) + ")"
    if f.cls != "" and takes_self(f) and len(f.ptypes) > 0 and f.ptypes[0] != f.cls:
        who += " for " + typestr(f.ptypes[0])
    return who


# the methods by which code fills a container it did not make (holes that a use types)
FILLS = "append extend insert add update setdefault appendleft extendleft"


def store_outside(t: Node, local: dict[str, bool], init: str) -> bool:
    # does storing to target t write state the function does not own: a field (but those that
    # __init__ assigns on its self, init, which its class's declaration types from its source),
    # or an item of a container that is not one of its own names
    if t.kind == "attr":
        return init == "" or t.kids[0].kind != "name" or t.kids[0].s != init
    if t.kind == "index":
        return t.kids[0].kind != "name" or t.kids[0].s not in local
    if t.kind == "tuple" or t.kind == "list" or t.kind == "starred":
        return any(store_outside(x, local, init) for x in t.kids)
    return False


def writes_outside(n: Node, local: dict[str, bool], init: str) -> bool:
    # does code n (also its nested functions) assign a global or a field, or fill a container it
    # did not make: the compiler can type a global, a field or an empty container from such code
    # (early, none_field), so leaving it out can leave one untyped or typed by a stub
    k = n.kind
    if k == "global" or k == "nonlocal":
        return True
    if k == "assign" and any(store_outside(t, local, init) for t in n.kids[:-1]):
        return True
    if (k == "augassign" or k == "annassign" or k == "del") and len(n.kids) > 0 and any(store_outside(t, local, init) for t in (n.kids if k == "del" else n.kids[:1])):
        return True
    if k == "call" and len(n.kids) > 0 and n.kids[0].kind == "attr" and n.kids[0].s in FILLS.split():
        o = n.kids[0].kids[0]
        if o.kind != "name" or o.s not in local:
            return True
    return any(writes_outside(x, local, init) for x in n.kids)


def stub_body(line: int) -> list[Node]:
    # what a unit left out compiles to: raise NotImplementedError(...), which no caller's type
    # depends on unless the unit's result is inferred (see gen_check_edge)
    exc = mk("name", "NotImplementedError", line, [])
    why = mk("str", "pystachy check left this body out", line, [])
    return [mk("raise", "", line, [mk("call", "", line, [exc, why])])]


def gen_check_failure(self, msg: str) -> CheckFailed:
    # the CheckFailed of msg, which ends this attempt: the unit is the body being compiled
    # (self.curfn). Module code, declarations (prepared before discovery) and the functions
    # the compiler writes have no body a later attempt may leave out
    f = self.curfn
    d = Diagnostic(msg, self.line, self.making)
    kind = check_kind(f)
    if self.pipeline.active == "prepare":
        return CheckFailed(d, "", "", "declarations", "", False, self.taint.get("", ""))
    if self.pipeline.active == "finalize":
        return CheckFailed(d, "", "", "admission", "", False, "")  # (every body is checked by then)
    if self.pipeline.active != "discover" or kind == "":
        return CheckFailed(d, "", "", "program", "", False, self.taint.get("", ""))
    after = self.taint.get(f.ll, self.taint.get("", ""))
    if kind == "module":
        name = "module code" if f.mod == "" else f"module code of {shown(f.mod)}"
        return CheckFailed(d, "", name, kind, where(f.node.line), False, after)
    # (a body already left out that fails again makes no progress: checking stops)
    return CheckFailed(d, self.fnkey(f), check_name(f), kind, where(f.node.line), f.ll not in self.stubbed, after)


def gen_check_body(self, f: FnInfo, body: list[Node]) -> list[Node]:
    # the body gen_function compiles for f in check mode: a stub if an earlier attempt failed
    # in it. A function compiled while a tainted one is (a template instance whose argument
    # types it decided) is tainted too
    if len(self.taint) > 0 and len(self.building) > 0:
        caller = list(self.building)[-1]
        if caller in self.taint and f.ll not in self.taint:
            self.taint[f.ll] = self.taint[caller]
    if len(self.stubs) > 0 and self.fnkey(f) in self.stubs:
        self.stubbed[f.ll] = check_name(f)
        local: dict[str, bool] = {p: True for p in f.params}
        collect(body, local)
        init = f.params[0] if f.name == "__init__" and f.cls != "" and takes_self(f) and len(f.params) > 0 else ""
        if "" not in self.taint and any(writes_outside(st, local, init) for st in body):
            self.taint[""] = check_name(f)  # (what typed a global or a field is left out)
        return stub_body(f.node.line)
    return body


def gen_check_edge(self, g: FnInfo) -> None:
    # the code being compiled (self.curfn) takes instance g's inferred result, or what it
    # yields: if g's body was left out, or depends on one that was, so does this code
    if (not g.infer and not g.gen) or len(self.stubbed) == 0:
        return
    via = self.stubbed.get(g.ll, "")
    if via == "":
        via = self.taint.get(g.ll, "")
    if via == "":
        return
    if self.selfcls != "" or check_kind(self.curfn) == "module" or self.pipeline.active != "discover":
        # (a class's fields or a global typed by it: any later code may read them)
        if "" not in self.taint:
            self.taint[""] = via
    elif self.curfn.ll != g.ll and self.curfn.ll not in self.taint:
        self.taint[self.curfn.ll] = via
