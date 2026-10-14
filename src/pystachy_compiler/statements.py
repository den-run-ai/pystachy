"""Statements component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.analysis import builtin_has
from src.pystachy_compiler.diagnostics import shown
from src.pystachy_compiler.ir import Blk, ClassInfo, Exit, FnInfo, Ins, IterArg, Loop, SeqStart, Val
from src.pystachy_compiler.names import owner, short
from src.pystachy_compiler.specs import (
    ABCS,
    DUNDER,
    FUTURE,
    FXBIT,
    MODULES,
    NONEVAR,
    OPTTYPES,
    ORDOP,
    PYBUILTINS,
    SPECIAL,
    TYPING,
    UNSUPPORTED,
)
from src.pystachy_compiler.syntax import Node, mk, names_in
from src.pystachy_compiler.utils import (
    bool_for_int,
    elem,
    elem_problem,
    folds,
    is_const,
    is_dict,
    is_fset,
    is_kw,
    is_list,
    is_opt,
    is_set,
    is_sopt,
    is_tuple,
    is_vtuple,
    lt,
    meet,
    same_kind,
    selem,
    targs,
    tname,
    typestr,
    unopt,
)


def gen_stmts(self, body: list[Node]) -> None:
    for s in body:
        if self.term and self.curfn.inst:
            # after a return, raise, break or continue: in a template's function, where a
            # static test leaves code for other argument types behind one, it is not compiled
            return
        self.stmt(s)

def gen_obj_helpers(self, c: str) -> None:
    # @o.eq/cmp/repr.<class>: what the runtime's generic ==, ordering and repr do with objects
    # of class c. They are compiled leniently: an operation the class does not support
    # raises TypeError when it runs rather than failing the compilation.
    line = self.classes[c].node.line
    a = mk("name", "a", line, [])
    b = mk("name", "b", line, [])
    op = mk("name", "op", line, [])
    cmp: list[Node] = []
    for o in ["<", "<=", ">"]:
        hit = mk("block", "", line, [mk("return", "", line, [mk("cmp", o, line, [a, b])])])
        cmp.append(mk("if", "", line, [mk("cmp", "==", line, [op, mk("int", str(ORDOP[o]), line, [])]), hit, mk("block", "", line, [])]))
    cmp.append(mk("return", "", line, [mk("cmp", ">=", line, [a, b])]))
    bodies = [[mk("return", "", line, [mk("cmp", "==", line, [a, b])])], cmp,
              [mk("return", "", line, [mk("call", "", line, [mk("name", "__pys_repr", line, []), a])])]]
    ops = ["eq", "cmp", "repr"]
    self.lenient = True
    for i in range(3):
        f = FnInfo(ops[i], f"@o.{ops[i]}.{c}", self.classes[c].node, "")
        f.params = ["op", "a", "b"] if i == 1 else ["a", "b"]
        f.ptypes = ["int", c, c] if i == 1 else [c, c]
        f.ret = "str" if i == 2 else "bool"
        self.function(f, bodies[i])
    self.lenient = False

def gen_dispatch(self, op: str) -> None:
    # pys_obj_<op>(class id, [op code,] a, b), called by the runtime for "O<id>" descriptors
    r = "ptr" if op == "repr" else "i64"
    self.out.append(f"define {r} @pys_obj_{op}(i64 %c, {'i64 %op, ' if op == 'cmp' else ''}i64 %a, i64 %b) {{")
    self.out.append("entry:")
    self.out.append("  %pa = inttoptr i64 %a to ptr")
    self.out.append("  %pb = inttoptr i64 %b to ptr")
    self.out.append(f"  switch i64 %c, label %none [{' '.join([f'i64 {self.ocls[c]}, label %k{self.ocls[c]}' for c in self.ocls])}]")
    for c in self.ocls:
        i = self.ocls[c]
        self.out.append(f"k{i}:")
        if op == "repr":
            self.out.append(f"  %r{i} = call ptr @o.repr.{c}(ptr %pa, ptr %pb)")
            self.out.append(f"  ret ptr %r{i}")
        else:
            self.out.append(f"  %r{i} = call i1 @o.{op}.{c}({'i64 %op, ' if op == 'cmp' else ''}ptr %pa, ptr %pb)")
            self.out.append(f"  %z{i} = zext i1 %r{i} to i64")
            self.out.append(f"  ret i64 %z{i}")
    self.out.append("none:")
    self.out.append("  unreachable")
    self.out.append("}")

def gen_check_special(self, f: FnInfo) -> None:
    # the special methods Pystachy calls implicitly must have the shape it relies on; in an
    # imported module's class, a wrong one is an error where the method is called, as is a
    # method whose declaration failed (f.bad: its types are placeholders)
    if f.name not in SPECIAL or f.bad != "":
        return
    self.line = f.node.line
    spec = SPECIAL[f.name]
    n = int(spec[: spec.find(":")])
    ret = spec[spec.find(":") + 1 :]
    if len(f.params) != n or f.vararg >= 0 or f.kwarg >= 0:
        # (an operator passes its operand by position: a template's *args would not take it)
        f.bad = f"{f.name} must take {n - 1} argument{'s' if n != 2 else ''} besides self"
    elif f.generic:
        pass  # (a template: each instance's return type is checked where it is compiled, see instance)
    elif f.name == "__bool__" and f.ret != "bool":
        f.bad = f"__bool__ should return bool, returned {tname(f.ret)}"  # (CPython's TypeError)
    elif ret != "" and f.ret != ret and not (f.name == "__len__" and f.ret == "bool"):
        f.bad = f"{f.name} must return {ret}"  # (a bool is an int to len())
    elif f.name == "__format__" and f.ptypes[1] != "str":
        f.bad = "__format__ takes the format spec as a str"
    if f.bad != "" and self.classes[f.cls].mod == "":
        self.err(f.bad)

def gen_scan_imports(self, body: list[Node]) -> None:
    # every import anywhere in the program, checked up front; the alias table that code
    # generation uses is still filled statement by statement
    for st in body:
        self.line = st.line
        if st.kind == "import":
            for a in st.kids:
                self.check_import(a)
                self.imports[a.s] = a.kids[0].s
        for k in st.kids:
            if k.kind == "block":
                self.scan_imports(k.kids)
            elif k.kind == "except":
                self.scan_imports(k.kids[1].kids)
        if st.kind == "def" or st.kind == "class":
            self.scan_imports(st.kids[-1].kids if st.kind == "class" else st.kids[2].kids)

def gen_imported(self, name: str) -> str:
    # what an imported name (possibly dotted) refers to, or ""
    root = name[: name.find(".")] if "." in name else name
    return self.imports[root] + name[len(root) :] if root in self.imports else ""

def gen_check_import(self, a: Node) -> None:
    mod = a.kids[1].s
    tgt = a.kids[0].s
    if mod not in MODULES and mod != "collections.abc":
        self.err(f"module '{mod}' is not supported (available: {', '.join(MODULES.keys())})")
    if tgt == mod or tgt == mod[: mod.find(".")] or (tgt + ".") == mod[: len(tgt) + 1]:
        return
    x = tgt[len(mod) + 1 :]
    if mod == "__future__":
        if x not in FUTURE:
            self.err(f"future feature {x} is not defined")
    elif mod == "typing" or mod == "collections.abc":
        if x not in (TYPING if mod == "typing" else ABCS):
            self.err(f"cannot import name '{x}' from '{mod}'")
    elif mod == "dataclasses":
        if x != "dataclass":
            self.err(f"dataclasses.{x} is not supported")
    elif not builtin_has(mod, x):
        self.err(f"cannot import name '{x}' from '{mod}': Pystachy's {mod} module has no '{x}'")

def gen_hidden(self, name: str, v: Val) -> str:
    # a compiler-made global, assigned here
    self.global_var(name, lt(v.t))
    self.emit(f"store {lt(v.t)} {v.v}, ptr {name}")
    return name

def gen_dflt_fn(self, f: FnInfo) -> FnInfo:
    # the function whose def statement evaluates f's default values (hoist): f, but for a method
    # of a class template's specialization, the template's method, as each specialization's is
    # the same def, whose defaults CPython evaluates once, when the class statement runs
    o = self.classes[f.cls].origin if f.cls in self.classes else ""
    if o != "" and f.name in self.classes[o].methods and self.classes[o].methods[f.name].node is f.node:
        return self.classes[o].methods[f.name]
    return f

def gen_early_default(self, f: FnInfo, j: int) -> None:
    # a call that leaves out parameter j of f, compiled before f's def statement (in a
    # template's function, or a function compiled early): the global that is to hold the
    # default value is declared now, and the def statement stores the value into it (hoist)
    if f.cls != "" and f.name == "__init__" and f.node.kids[0].kind == "noann":
        # a dataclass's __init__: the class statement evaluates the field's default
        self.class_default(self.classes[f.cls], f.params[j])
        f.dglob[j] = self.classes[f.cls].fglob[f.params[j]]
        return
    t = f.ptypes[j]
    bad = self.default_problem(f.defaults[j], t) if f.mod != "" else ""
    if bad != "":
        f.dglob[j] = "!" + bad
        return
    if t == "":
        t = self.modtype(f.defaults[j], f.mod)
        if t == "" or "?" in t:
            self.err(f"the default value of parameter '{f.params[j]}' of {f.name}() cannot be typed here, before its def statement runs; annotate the parameter")
    self.pending[f"{f.ll}.{j}"] = True
    if t == "None":
        f.dglob[j] = "=None"
        return
    f.dtypes[j] = t
    f.dglob[j] = f"@d.{f.ll[1:]}.{f.params[j]}"
    self.global_var(f.dglob[j], lt(t))

def gen_class_default(self, ci: ClassInfo, fl: str) -> None:
    # a class-body default read before the class statement runs (see early_default), or a
    # class variable's global: that of the class whose body binds it (default_home), which an
    # exception class deriving from it shares
    h = self.default_home(ci, fl)
    if fl not in h.fglob:
        h.fglob[fl] = f"@d.c.{h.name}.{fl}"
        self.global_var(h.fglob[fl], lt(h.ftypes[fl]))
        self.pending[h.fglob[fl]] = True
    ci.fglob[fl] = h.fglob[fl]

def gen_hoist(self, f: FnInfo) -> None:
    # Python evaluates default values once, when the def statement runs
    for j in range(len(f.params)):
        d = f.defaults[j]
        early = f"{f.ll}.{j}" in self.pending
        if (f.dglob[j] == "" or early) and not is_const(d):
            t = f.ptypes[j] if f.bad == "" else ""  # (an unsupported annotation is no type)
            self.line = d.line
            bad = self.default_problem(d, t) if f.mod != "" else ""
            if bad != "":
                # a function of an imported module: the default is an error only where a call
                # needs it, if evaluating it when the def runs does nothing
                self.eager(self.partly(d, 0), bad, "evaluates this default value")
                f.dglob[j] = "!" + bad
                continue
            v = self.expr(d, t)
            if early:
                # a call compiled before this statement declared its global (early_default)
                del self.pending[f"{f.ll}.{j}"]
                if f.dglob[j] != "=None":
                    self.emit(f"store {lt(f.dtypes[j])} {self.coerce(v, f.dtypes[j]).v}, ptr {f.dglob[j]}")
                continue
            if v.t == "None" and t == "":
                f.dglob[j] = "=None"  # a None value is no global: calls pass None
                continue
            f.dtypes[j] = v.t
            f.dglob[j] = self.hidden(f"@d.{f.ll[1:]}.{f.params[j]}", self.coerce(v, t) if t != "" else v)

def gen_default_problem(self, e: Node, t: str) -> str:
    # why default value e of a parameter of type t ("": a template's) cannot be compiled, as far
    # as its form shows, or ""
    if e.kind == "name" and e.s in self.classes:
        return f"class '{short(e.s)}' cannot be used as a value (classes are not values: call it, or read an attribute, C.x)"
    if e.kind == "name" and e.s in PYBUILTINS and "$" not in e.s and not e.s[0].islower():
        return f"the builtin '{e.s}' cannot be used as a value (not supported)"
    if t == "" and (e.kind == "list" or e.kind == "dict") and len(e.kids) == 0:
        return f"cannot infer the type of an empty {e.kind} as a default value; annotate the parameter"
    if e.kind == "badattr":
        return e.s
    if e.kind in UNSUPPORTED:
        return UNSUPPORTED[e.kind]
    for k in e.kids:
        if e.kind == "call" and k is e.kids[0] and k.kind == "name":
            continue  # the function called
        r = self.default_problem(k, "?")
        if r != "":
            return r
    return ""

def gen_hoist_class(self, ci: ClassInfo) -> None:
    # class-body defaults are evaluated once, when the class statement runs, in body order,
    # and shared. Pystachy has no class scope: names bound earlier in the body are rejected.
    # (A class whose only problem is ci.hook still compiles here: CPython runs its body.)
    ci.bad = "" if ci.bad == ci.hook else ci.bad
    for st in ci.node.kids[0].kids if ci.mod != "" and ci.bad == "" else []:
        if st.kind == "annassign" and len(st.kids) == 3 and st.kids[0].kind == "name":
            why = self.default_problem(st.kids[2], ci.ftypes[st.kids[0].s])
            if why != "":
                ci.bad = f"class {shown(ci.name)} is not supported: {why}"
    if ci.bad != "":
        # an imported module's class Pystachy cannot compile: an error only where used
        self.left_out(self.cnodes[ci.node.line], ci.bad)
        return
    bound: dict[str, bool] = {}
    syn = "__init__" in ci.methods and ci.methods["__init__"].node.kids[0].kind == "noann"  # (a dataclass's)
    later = ""
    for st in ci.node.kids[0].kids:
        self.line = st.line
        if st.kind == "annassign" and len(st.kids) == 3 and st.kids[0].kind == "name":
            fl = st.kids[0].s
            self.no_class_names(st.kids[2], bound, ci)
            bound[fl] = True
            t = ci.ftypes[fl]
            u = unopt(t)  # (a default of a T | None field that is not None is a T)
            if self.is_dc(ci.name) and ci.name not in self.nts and not is_const(st.kids[2]) and (is_list(u) or is_dict(u) or self.unhashable(u) or (self.is_dc(u) and u not in self.nts)):
                self.err(f"mutable default {u} for dataclass field '{fl}' is not allowed")
            for m in ["__set_name__", "__get__", "__set__", "__delete__"] if t in self.classes and not is_const(st.kids[2]) else []:
                # (__set_name__ runs when CPython creates the class, __get__ too with @dataclass)
                now = m == "__set_name__" or (m == "__get__" and self.is_dc(ci.name))
                why = f"a class attribute whose class defines {m} is not supported (CPython calls it {'when it creates the class' if now else 'where the attribute is used'})"
                if m in self.classes[t].methods and (now or ci.mod == ""):
                    self.err(why)
                later = later if later != "" or m not in self.classes[t].methods else f"class {shown(ci.name)} is not supported: {why}"
            cv = ci.name + "." + fl in self.cvars  # (a class variable's constant default needs its global too)
            if (cv or not is_const(st.kids[2])) and fl in ci.fglob and ci.fglob[fl] in self.pending:
                # code compiled before this statement declared its global (class_default)
                del self.pending[ci.fglob[fl]]
                self.emit(f"store {lt(t)} {self.coerce(self.expr(st.kids[2], t), t).v}, ptr {ci.fglob[fl]}")
            elif (cv or not is_const(st.kids[2])) and fl not in ci.fglob:
                ci.fglob[fl] = self.hidden(f"@d.c.{ci.name}.{fl}", self.coerce(self.expr(st.kids[2], t), t))
        elif st.kind == "def":
            f = ci.methods[st.s]
            for d in f.defaults:
                self.no_class_names(d, bound, ci)
            bound[st.s] = True
            if f.name != "__init__" or not syn:
                self.hoist(f)
    if syn:
        init = ci.methods["__init__"]
        for j in range(1, len(init.params)):
            init.dglob[j] = ci.fglob.get(init.params[j], "")
    ci.bad = later if later != "" else ci.hook  # (an imported module's class: an error where the program uses it)

def gen_no_class_names(self, e: Node, bound: dict[str, bool], ci: ClassInfo) -> None:
    # (the loader leaves a class body's names unqualified where it reads them: qstmts)
    if e.kind == "name" and "$" not in e.s and e.s in bound:
        self.err(f"class attribute '{e.s}' of '{short(ci.name)}' used in a class-body default is not supported")
    for k in e.kids:
        self.no_class_names(k, bound, ci)

def gen_unhashable(self, t: str) -> bool:
    # a class that defines __eq__ without __hash__ has __hash__ = None in CPython (a NamedTuple
    # has a tuple's)
    return t in self.classes and "__eq__" in self.classes[t].methods and "__hash__" not in self.classes[t].methods and t not in self.nts

def gen_while_(self, n: Node) -> None:
    l1 = self.label()
    l2 = self.label()
    l3 = self.label()
    lp = Loop("while", l1, l2, l1, l3)
    self.fn.loops.append(lp)
    after = self.forget(n.kids[1].kids, n.kids[1])
    self.place(l1)
    self.cbr(self.cond(n.kids[0]), l2, l3)
    self.place(l2)
    self.narrow_by(n.kids[0], True)
    brks = self.loop(n.kids[1].kids, lp)
    self.br(l1)
    self.narrowed = after
    # after the loop: what holds where its test is false (never for while True) and at each
    # break that leaves it here (a loop with an else block breaks past it)
    self.narrow_by(n.kids[0], False)
    ends: list[dict[str, bool]] = []
    if n.kids[0].kind != "True":
        ends.append(self.narrowed)
    if n.kids[1].kids is not self.elsekids:
        ends.extend(brks)
    self.narrowed = meet(ends) if len(ends) > 0 else after
    self.place(l3)

def gen_loop(self, body: list[Node], lp: Loop) -> list[dict[str, bool]]:
    # the body of loop lp: continue jumps to lp.step, break to lp.exit; what narrowed holds at
    # its breaks is returned (see while_)
    if body is self.elsekids:
        lp.exit = self.elsebrk  # the loop of a for/while ... else: break skips the else block
    self.loops.append(lp)
    self.wdepth.append(len(self.exits))
    self.brks.append([])
    self.branch += 1
    self.stmts(body)
    self.branch -= 1
    self.wdepth.pop()
    self.loops.pop()
    r = self.brks.pop()
    if body is self.elsekids:
        self.elsebrks = r
    return r

def gen_leave(self, depth: int) -> bool:
    # leaving the code inside exits[depth:] (break, continue, return, the end of a with block):
    # what each exit requires, innermost first, each in a block that the landing block around
    # its construct covers. A with block's file closes (its unwind action forgotten first); an
    # except clause restores the exception being handled before it, and unbinds its name; a
    # finally block runs as where its try statement is: in its loops, within the exits
    # outside it (where its own break or return goes). True if one of those took the way out
    # over (its own return, break, continue or raise), so that the caller's is not compiled
    here = self.handler
    cv = self.carried
    ended = False
    for i in range(len(self.exits) - 1, depth - 1, -1):
        if ended:
            break
        x = self.exits[i]
        self.handler = x.handler
        if self.blk.handler != x.handler:
            self.place(self.label())
        if x.kind == "with":
            if self.eh:
                self.rt("pys_unwind_pop", "void", [])
            self.rt("pys_file_close", "void", [f"ptr {x.v}"])
        elif x.kind == "handler":
            self.rt("pys_exc_restore", "void", [f"ptr {x.v}"])
            self.unbind(x.name)
        elif x.entry != "":
            # a finally block compiled once (try_): it goes on here, by its index in conts; a
            # return's value is kept in a slot, as other ways out reach the code after it too
            sl = ""
            if cv.v.startswith("%"):
                sl = self.alloca(cv.t, "")
                self.emit(f"store {lt(cv.t)} {cv.v}, ptr {sl}")
            self.emit(f"store i64 {len(x.conts)}, ptr {x.sel}")
            x.conts.append(self.label())
            self.br(x.entry)
            self.place(x.conts[-1])
            self.narrowed = self.unnarrowed([x.body])  # (what the block may bind on the way)
            if sl != "":
                cv = Val(self.ins(f"load {lt(cv.t)}, ptr {sl}"), cv.t)
        else:
            exits = self.exits
            loops = self.loops
            wdepth = self.wdepth
            excs = self.excs
            self.exits = exits[:i]
            self.loops = loops[: x.nloops]
            self.wdepth = wdepth[: x.nloops]
            self.excs = excs[: x.nexcs]
            t0 = self.term
            self.branch += 1
            self.stmts(x.body)
            self.branch -= 1
            ended = self.term and not t0
            self.exits = exits
            self.loops = loops
            self.wdepth = wdepth
            self.excs = excs
    self.handler = here
    self.carried = cv
    return ended

def gen_stmt(self, n: Node) -> None:
    self.line = n.line
    k = n.kind
    if self.curfn.vararg >= 0 and self.stack_ok(self.curfn):
        self.keep_stack(n)
    if k == "expr":
        if n.kids[0].kind != "str" and n.kids[0].kind != "ellipsis":
            self.expr(n.kids[0], "")  # (a string or ... alone does nothing)
    elif k == "assign":
        val = n.kids[-1]
        t0 = n.kids[0]
        self.copying = n.s == "from" and self.foreign(val.s)
        ekind = self.empty_of(val)
        if len(n.kids) == 2 and t0.kind == "name" and ekind != "" and self.ltype.get(t0.s, "") == NONEVAR and not self.is_global(t0.s):
            self.err(f"cannot infer the type of '{t0.s}' from None and an empty {ekind}; annotate it ({t0.s}: {ekind}[{'K, V' if ekind == 'dict' else 'T'}] | None = None)")
        if len(n.kids) == 2 and t0.kind == "name" and ekind != "" and (self.target_type(t0) == "" or "?" in self.target_type(t0)):
            self.assign(t0, self.empty(ekind, t0.s))
        elif len(n.kids) == 2 and t0.kind == "name" and val.kind == "call" and len(val.kids) == 2 and val.kids[0].kind == "name" and val.kids[0].s == "dict" and not self.bound("dict") and val.kids[1].kind == "name" and self.static_type(val.kids[1]) == "kw[]" and (self.target_type(t0) == "" or "?" in self.target_type(t0)):
            self.assign(t0, self.empty("dict", t0.s))  # (d = dict(kwargs) of a call without extra keywords: d = {})
        elif len(n.kids) == 2 and t0.kind == "name" and val.kind == "name" and self.is_global(t0.s) and (t0.s not in self.gtypes or self.twin_of.get(t0.s, "-") == self.twin_of.get(val.s, "")) and t0.s not in self.noneglobals and not self.copying and self.globread(val.s) and "?" in self.gtypes.get(val.s, ""):
            # X = Y between module globals, Y an empty container without a type yet (from m
            # import Y copies it so): they are twins, which the first use of either types
            # (ahead may have made them so already)
            self.allowq = True
            self.assign(t0, self.read(val))
            self.allowq = False
            self.twin(t0.s, val.s)
        elif len(n.kids) == 2 and t0.kind == "tuple" and (val.kind == "tuple" or val.kind == "list") and len(t0.kids) == len(val.kids):
            vs: list[Val] = []
            for i in range(len(val.kids)):
                vs.append(self.expr(val.kids[i], self.target_type(t0.kids[i])))
            for i in range(len(vs)):
                self.assign(t0.kids[i], vs[i])
        else:
            if t0.kind == "index" and t0.kids[0].kind == "name" and "?" in self.rtype(t0.kids[0].s) and self.empty_of(val) != "":
                self.no_type(t0.kids[0].s)  # (d[k] = [] shows nothing of what d holds)
            v = self.expr(val, self.target_type(t0))
            for i in range(len(n.kids) - 1):
                self.assign(n.kids[i], v)
        self.copying = False
    elif k == "annassign" and self.tmpl_ann(n.kids[1]):
        # an annotation that names a class template types nothing: x: Box = v is x = v
        if len(n.kids) == 3:
            self.stmt(mk("assign", "", n.line, [n.kids[0], n.kids[2]]))
    elif k == "annassign":
        if n.s != "" and self.ann_problem(n.kids[1], False) != "":
            self.err(n.s)  # (the declaration of a local that only dropped code binds: Loader.dropped_locals())
        t = self.vtype(n.kids[1])
        if n.kids[0].kind == "name":
            self.declare(n.kids[0].s, t)
        if len(n.kids) == 3:
            v = self.expr(n.kids[2], t)
            # (x: T | None = <a T> knows x holds a T, see narrowed)
            self.assign(n.kids[0], v if n.kids[0].kind == "name" and is_opt(t) and self.widens(v.t, t) else self.coerce(v, t))
    elif k == "augassign":
        self.augassign(n)
    elif k == "if":
        st = self.static(n.kids[0])
        if st >= 0:
            # the static types decide the test (isinstance(x, str), x is None): only the branch
            # that runs is compiled
            self.static_reads(n.kids[0])
            self.stmts(n.kids[1].kids if st == 1 else n.kids[2].kids)
            return
        c = self.cond(n.kids[0])
        l1 = self.label()
        l2 = self.label()
        l3 = self.label()
        self.cbr(c, l1, l2)
        self.branch += 1
        self.place(l1)
        pre = self.narrow_by(n.kids[0], True)
        self.stmts(n.kids[1].kids)
        yes = self.narrowed
        ygo = not self.term
        self.br(l3)
        self.place(l2)
        self.narrowed = pre
        self.narrow_by(n.kids[0], False)
        self.stmts(n.kids[2].kids)
        ngo = not self.term
        self.branch -= 1
        self.place(l3)
        # after the if: what holds at the end of each branch that goes on
        if ygo and not ngo:
            self.narrowed = yes
        elif ygo and ngo and len(yes) + len(self.narrowed) > 0:
            no = self.narrowed
            self.narrowed = {}
            for both in yes:
                if both in no:
                    self.narrowed[both] = True
    elif k == "while" and self.static(n.kids[0]) == 0:
        # a loop whose test is false from the start (while x: with x None): only its else block runs
        self.static_reads(n.kids[0])
        if n.kids[-1].s == "else":
            self.stmts(n.kids[-1].kids)
    elif (k == "while" or k == "for") and n.kids[-1].s == "else":
        # for/while ... else: break leaves the loop past the else block
        ek = self.elsekids
        eb = self.elsebrk
        self.elsekids = n.kids[2 if k == "for" else 1].kids
        self.elsebrk = self.label()
        self.elsebrks = []  # (a loop over () has no body to compile)
        lb = self.elsebrk
        if k == "for":
            self.for_(n, [])
        else:
            self.while_(n)
        self.elsekids = ek
        self.elsebrk = eb
        brks = self.elsebrks
        self.branch += 1
        self.stmts(n.kids[-1].kids)
        self.branch -= 1
        # after it: what holds at the end of the else block (if it goes on) and at each break
        if not self.term:
            brks.append(self.narrowed)
        if len(brks) > 0:
            self.narrowed = meet(brks)
        self.place(lb)
    elif k == "while":
        self.while_(n)
    elif k == "for":
        self.for_(n, [])
    elif k == "return":
        if self.modlevel:
            self.err("'return' outside function")
        if self.ret == "":
            # the first return of a template's function with a value decides what the function
            # returns; a return of None before it is lowered from what that decided
            v = self.retval(n.kids[0], "") if len(n.kids) > 0 else Val("null", "None")
            if v.t != "None":
                t = v.t
                if self.optional(t) != t and self.optional(t) != "" and self.returned_none():
                    t = self.optional(t)  # after a return of None: T | None (before it calls itself)
                self.ret = t
                self.curfn.ret = t
                v = self.coerce(v, t)
            self.carried = v
            ended = self.leave(0)
            v = self.carried
            self.carried = Val("", "")
            if ended:
                pass  # (a finally block returned instead)
            elif v.t == "None":
                self.add(Ins("ret.none", "", ""))
            else:
                self.ret_(v)
        elif len(n.kids) == 0 or (self.ret == "None" and n.kids[0].kind == "None"):
            if self.ret != "None" and self.curfn.infer and self.optional(self.ret) != self.ret and self.optional(self.ret) != "":
                self.reopt(self.optional(self.ret))  # a template's function returns T, and None: T | None
            if self.ret != "None" and not (self.curfn.infer and self.ret in self.classes) and not is_opt(self.ret):
                self.err(self.nonemix(self.curfn, self.ret) if self.curfn.infer else f"missing return value of type {self.ret}")
            if not self.leave(0):
                self.ret_(Val("null", self.ret))
        elif self.ret == "None":
            # return f() where f returns None
            v = self.expr(n.kids[0], "")
            if v.t != "None" and self.curfn.infer:
                self.err(self.nonemix(self.curfn, v.t))
            if v.t != "None":
                self.err(f"returning {v.t} from a function declared to return None" if self.retann else "returning a value from a function without a return annotation")
            if not self.leave(0):
                self.ret_(Val("null", "None"))
        else:
            v = self.iter_ret(n.kids[0]) if self.curfn.iters else self.retval(n.kids[0], self.ret)
            if "?" in self.ret and "?" not in v.t and same_kind(v.t, self.ret):
                self.adopt(v.t)  # (it returned an empty container without a type before)
            j = self.join(self.ret, v.t) if self.curfn.infer and v.t != self.ret else self.ret
            if j != self.ret and j != "" and is_opt(j):
                self.reopt(j)  # a template's function returns T and None (or T | None): T | None
            if self.curfn.infer and v.t != self.ret and not (v.t == "None" and self.ret in self.classes) and not self.widens(v.t, self.ret) and not self.boxes(v.t, self.ret):
                if v.t == "None":
                    self.err(self.nonemix(self.curfn, self.ret))
                self.err(f"{short(self.curfn.name)}() returns both {typestr(self.ret)} and {typestr(v.t)} (each function has one return type)")
            v = self.coerce(v, self.ret, f"the value {short(self.curfn.name)}() returns ({typestr(self.ret)})" if is_opt(v.t) else "")
            self.carried = v  # (the value first: a finally block runs after it is computed)
            ended = self.leave(0)
            v = self.carried
            self.carried = Val("", "")
            if not ended:
                self.ret_(Val(v.v, self.ret))
        self.term = True
    elif k == "break" or k == "continue":
        if len(self.loops) == 0:
            self.err(f"'{k}' outside loop")
        self.leave(self.wdepth[-1])
        if k == "break" and not self.term:
            self.brks[-1].append(dict(self.narrowed))
        self.br(self.loops[-1].exit if k == "break" else self.loops[-1].step)
    elif k == "global":
        if self.rtmode:
            # module globals would be garbage collector roots that runtime mode does not register
            self.err("runtime.py's functions cannot use global variables")
        for nm in n.kids:
            self.gdecl[nm.s] = True
    elif k == "assert" and (self.static(n.kids[0]) == 0 or n.kids[0].kind == "False"):
        # an assertion that cannot hold (assert x is not None with x None, assert False): code
        # after it never runs
        self.static_reads(n.kids[0])
        self.assert_fails(n)
        self.term = True
    elif k == "assert" and self.static(n.kids[0]) == 1:
        self.static_reads(n.kids[0])
    elif k == "assert":
        l1 = self.label()
        l2 = self.label()
        self.cbr(self.cond(n.kids[0]), l2, l1)
        self.place(l1)
        self.assert_fails(n)
        self.place(l2)
        self.narrow_by(n.kids[0], True)
    elif k == "raise":
        self.raise_stmt(n)
    elif k == "try":
        self.try_(n)
    elif k == "del":
        for dt in n.kids:
            if dt.kind == "name":
                self.del_name(dt)
                continue
            o = self.expr(dt.kids[0], "") if dt.kind == "index" else Val("", "")
            nodel = "TypeError: 'NoneType' object does not support item deletion"
            if is_list(unopt(o.t)):
                ix = self.ival(dt.kids[1])
                self.rt("pys_list_del", "void", [f"ptr {self.unwrap(o, nodel).v}", f"i64 {ix.v}"])
            elif is_dict(unopt(o.t)):
                # del d[k] looks k up as d[k] does (dkey): a key that may be None raises
                # KeyError: None (nonekey), and a bool deletes the int key it equals
                kt = targs(unopt(o.t))[0]
                kval = self.expr(dt.kids[1], kt)
                kx = self.dkey(kval, kt)
                key = self.to_slot(kx)
                o = self.unwrap(o, nodel)
                if bool_for_int(kval.t, kt):
                    self.bool_find(o.v, kval, key)
                self.nonekey(kx, "", "pys_dict_pop", [f"ptr {o.v}", "i64 " + key])
            elif o.t in self.classes:
                # del o[k]: o.__delitem__(k)
                ik = self.expr(dt.kids[1], self.argtype(o.t, "__delitem__", 1, f"'{tname(o.t)}' object doesn't support item deletion"))
                self.notnone(o, nodel)
                self.protocol(o, "__delitem__", [ik])
            elif is_kw(o.t):
                self.err("changing **kwargs is not supported: copy it to a dict first (d = dict(kwargs))")
            else:
                self.err("only 'del list[i]' and 'del dict[key]' are supported")
    elif k == "with":
        # with open(p) as f: the file closes when the block is left, at its end or through
        # break, continue or return. An exception that leaves the block closes it too: it is
        # an unwind action while the block runs (a landing pad runs it, and so does an
        # exception that nothing catches), even in a program without a try statement
        n0 = len(self.exits)
        for it in n.kids[:-1]:
            v = self.expr(it.kids[0], "")
            if v.t != "file":
                self.err(f"'with' is supported for files only (with open(...) as f:), not {v.t}")
            if not self.open_call(it.kids[0]):
                # (a file's __enter__ raises if it is closed)
                c = self.rt("pys_file_closed", "i64", [f"ptr {v.v}"])
                self.guard(self.ins(f"icmp ne i64 {c}, 0"), "ValueError: I/O operation on closed file.")
            if self.eh:
                self.rt("pys_unwind_file", "void", [f"ptr {v.v}"])
            if len(it.kids) == 2:
                self.assign(it.kids[1], v)
            self.exits.append(Exit("with", v.v, self.handler))
        self.stmts(n.kids[-1].kids)
        if not self.term:
            self.leave(n0)
        self.exits = self.exits[:n0]
    elif k == "reduce":
        self.reduce_item(self.reds[n.s], n.kids[0])
    elif k == "anyall":
        hit = self.label()
        go = self.label()
        c = self.cond(n.kids[0])
        if n.s == "any":
            self.cbr(c, hit, go)
        else:
            self.cbr(c, go, hit)
        self.place(hit)
        self.emit(f"store i1 {'true' if n.s == 'any' else 'false'}, ptr {self.lcs[-1]}")
        self.br(self.loops[-1].exit)
        self.place(go)
    elif k == "lcappend":
        et = self.lct[-1]
        v = self.expr(n.kids[0], et)
        if et == "":
            self.lct[-1] = self.none_items(v.t) if n.s == "set" and is_tuple(v.t) else v.t
            et = self.lct[-1]
            if n.s == "set" and elem_problem(et) != "":
                self.err(elem_problem(et))
        if n.s == "set":
            self.rt("pys_set_add", "void", [f"ptr {self.lcs[-1]}", "i64 " + self.to_slot(self.store_elem(v, et))])
        elif n.s == "discard":
            self.sdiscard(f"ptr {self.lcs[-1]}", v, et)
        else:
            self.rt("pys_list_append", "void", [f"ptr {self.lcs[-1]}", "i64 " + self.to_slot(self.coerce(v, et))])
    elif k == "defaults" or k == "cdefaults":
        if k == "defaults":
            self.decorators(self.funcs[n.s].node, self.funcs[n.s].node.kids[3:] if self.curfn.mod != "" else [], {})
            self.hoist(self.funcs[n.s])
            ef = self.funcs[n.s]
            if ef.extern and not self.rtmode:
                # @ffi.extern looks its C function up when the def runs, as ctypes.CDLL does (cextern)
                xs = ef.ll[1:]
                self.rt("pys_c_bind", "void", [f"ptr @ffi.fp.{xs}", f"ptr @ffi.lib.{xs}", f"ptr @ffi.sym.{xs}"])
        else:
            self.hoist_class(self.classes[n.s])
        if n.s in self.gflag:
            self.emit(f"store i1 true, ptr @g.{n.s}.def")
    elif k == "lclass":
        self.left_out(self.cnodes[n.line], self.unsupported[n.s])
    elif k == "import":
        for a in n.kids:
            self.aliases[a.s] = a.kids[0].s
    elif k == "uimport":
        for x in n.kids:
            if x.kind == "guard":
                # an optional import of a module whose code raises ImportError: it returns there
                self.emit(f"store i1 true, ptr @init.{x.s}.guard")
                self.add(Ins("init", "", x.s))
                self.emit(f"store i1 false, ptr @init.{x.s}.guard")
            else:
                self.add(Ins("init", "", x.s))
    elif k == "bound":
        # an import has bound these names, which an import in a try statement may leave unbound
        self.modchk(n)  # a from-import must read an existing source-module attribute first
        for bn in n.s.split():
            self.emit(f"store i1 true, ptr {self.imp_flag(bn, self.modlevel)}")
    elif k == "def" and (n.s in self.decorated if self.modlevel else self.applies(n, False, self.scope_names())):
        self.store_name(n.s, self.decorate(n))  # (its name binds what its decorators give)
    elif k == "def" and not self.modlevel:
        self.store_name(n.s, self.closure(n))  # (a def inside a function: a closure)
    elif k == "nonlocal":
        # the variables a closure takes: its cells hold them (see closure)
        caps = self.closures[self.curfn.clo].caps if self.curfn.clo >= 0 else []
        for x in n.kids:
            if x.s not in caps:
                self.err(f"nonlocal '{x.s}' is not supported here: the function around it does not bind it where this function is defined")
    elif k == "def" or k == "class" or k == "subclass":
        if self.modlevel:
            self.err(f"a {'class' if k == 'subclass' else k} statement inside a block of a module's code (if, try, for, while, with) is not supported: only at its top level")
        self.err("a class inside a function is not supported")
    elif k == "badimport":
        self.err(n.s)
    elif k in UNSUPPORTED:
        self.err(UNSUPPORTED[k])
    elif k != "pass":
        self.err(f"unsupported statement '{k}'")

def gen_nonemix(self, f: FnInfo, t: str) -> str:
    # why template f, which returns None and a t, cannot return t | None
    if "?" in t:
        k = tname(t)
        return f"{short(f.name)}() returns None and an empty {k} whose items' type it does not show; annotate its return type (-> {k}[{'T' if k == 'list' else 'K, V'}] | None)"
    return f"{short(f.name)}() returns both None and {typestr(t)}, and None/Optional is only supported for {OPTTYPES}"

def gen_reopt(self, t: str) -> None:
    # the template's function being compiled, which returned a T, returns None too: T | None
    if self.curfn.ll in self.retseen:
        self.err(f"cannot infer what {short(self.curfn.name)}() returns: it calls itself before a return of None shows that it returns {typestr(t)}; annotate its return type")
    if is_sopt(t) or self.reboxes(self.ret, t):
        # its returns of an int so far return its box: each gets one before its ret
        for b in self.fn.blocks:
            if len(b.code) > 0 and b.code[-1].op == "ret" and len(b.code[-1].a) == 1 and b.code[-1].a[0].t != t:
                b.code[-1].a = [self.convert_in(b.code[-1].a[0], t, b)]
    self.ret = t
    self.curfn.ret = t

def gen_del_name(self, n: Node) -> None:
    # del x: x is unbound afterwards. Reads that may follow test its "is assigned" flag
    # (definite assignment marks them), so clearing the flag is all it takes.
    name = n.s
    if name in self.unsupported:
        return  # a class of an imported module that is never compiled
    if name not in self.ltype and (name in self.funcs or name in self.classes or name in self.aliases):
        # (a function's local hides the module's function, class or import of that name)
        self.err(f"del of '{name}' is not supported: only variables can be deleted")
    if not self.modlevel and self.is_global(name):
        self.err(f"del of the global '{name}' in a function is not supported")
    if owner(name) != self.curfn.mod:
        self.err(f"del of module {owner(name)}'s attribute '{short(name)}' is not supported")
    if name in self.falseflags and self.is_global(name):
        self.err(f"del of '{owner(name)}.TYPE_CHECKING' is not supported: its module assigns it False once, so its tests of it are decided at compile time")
    self.nonecmp = True  # (a local only None was assigned to may be deleted)
    self.read(n)  # del of a name that is not bound raises as its read does
    self.nonecmp = False
    self.narrowed.pop(name, False)
    if name in self.ltype and name in self.lflag:
        self.emit(f"store i1 false, ptr {self.lflag[name]}")
    elif name not in self.ltype and name in self.gflag:
        self.emit(f"store i1 false, ptr @g.{name}.def")

def gen_augassign(self, n: Node) -> None:
    t = n.kids[0]
    op = n.s
    if t.kind == "name" and op == "+" and is_list(self.rtype(t.s)) and "?" in self.qtype(t.s):
        # xs += [...] on an empty list without a type
        self.allowq = True
        cur = self.read(t)
        self.allowq = False
        v = self.expr(n.kids[1], "")
        if not is_list(v.t):
            self.err(f"cannot extend a list with {v.t}")
        self.refine(t.s, v.t)
        self.rt("pys_list_extend", "void", [f"ptr {cur.v}", f"ptr {v.v}"])
        self.store_name(t.s, Val(cur.v, v.t))  # (the right operand may have rebound the name)
    elif t.kind == "name" and op == "|" and is_set(self.rtype(t.s)) and "?" in self.qtype(t.s):
        # s |= t on an empty set without a type
        self.allowq = True
        cur = self.read(t)
        self.allowq = False
        v = self.expr(n.kids[1], "")
        if not is_set(v.t):
            self.err(f"unsupported operand type(s) for |=: 'set' and '{tname(v.t)}'")
        self.refine(t.s, self.ctype("set", [selem(v.t)]))
        self.rt("pys_set_update", "void", [f"ptr {cur.v}", f"ptr {v.v}"])
        self.store_name(t.s, Val(cur.v, self.qtype(t.s)))
    elif t.kind == "name":
        cur = self.read(t)
        self.store_name(t.s, self.inplace(op, cur, n.kids[1]))
    elif t.kind == "attr" and self.dotted(t) != "":
        self.err(f"assigning to {self.dotted(t)} is not supported; change its value in place")
    elif t.kind == "attr" and t.kids[0].kind == "name" and t.kids[0].s in self.classes and t.kids[0].s not in self.ltype:
        # C.x op= v: the class variable's value, then the new one stored back
        ci = self.cvar(t.kids[0], t.s)
        self.class_store(ci, t.s, self.inplace(op, self.class_attr(t.kids[0], t.s), n.kids[1]))
    elif t.kind == "attr":
        o = self.expr(t.kids[0], "")
        p = self.field(o, t.s, False)
        self.frozen(o.t, t.s)
        cur = self.getfield(o, p, t.s)
        self.setfield(o, p, t.s, self.inplace(op, cur, n.kids[1]))
    elif t.kind == "index":
        o = self.expr(t.kids[0], "")
        sub = "TypeError: 'NoneType' object is not subscriptable"
        if is_list(unopt(o.t)):
            et = elem(unopt(o.t))
            i = self.ival(t.kids[1])
            o = self.unwrap(o, sub)
            cur = self.from_slot(self.rt("pys_list_get", "i64", [f"ptr {o.v}", f"i64 {i.v}"]), et)
            r = self.coerce(self.inplace(op, cur, n.kids[1]), et)
            self.rt("pys_list_set", "void", [f"ptr {o.v}", f"i64 {i.v}", "i64 " + self.to_slot(r)])
        elif is_dict(unopt(o.t)):
            # d[k] op= v stores k where d[k] has found it: k is looked up as d[k] does (dkey),
            # so a key that may be None raises KeyError: None, past which it is a key of d's
            # type; a bool where the keys are ints finds the int key it equals (bool_find), whose
            # value it sets, unless the right operand may change a dict or run code of the
            # program: where it deletes k, CPython adds k as the bool it is (store_key rejects it)
            kv = targs(unopt(o.t))
            kval = self.expr(t.kids[1], kv[0])
            kx = self.dkey(kval, kv[0])
            key = "" if is_sopt(kx.t) else self.to_slot(kx)
            o = self.unwrap(o, sub)
            if bool_for_int(kval.t, kv[0]):
                e = self.bool_find(o.v, kval, key)
                cur = self.from_slot(self.rt("pys_dict_val", "i64", [f"ptr {o.v}", f"i64 {e}"]), kv[1])
                b0 = self.blk
                x0 = len(b0.code)
                n0 = len(self.fn.blocks)
                r = self.coerce(self.inplace(op, cur, n.kids[1]), kv[1])
                if self.may_change(b0, x0, n0):
                    self.store_key(kval, kv[0])  # (rejected)
                self.rt("pys_dict_entry_set", "void", [f"ptr {o.v}", f"i64 {e}", "i64 " + self.to_slot(r)])
                return
            if is_opt(kx.t):
                self.guard(self.ins(f"icmp eq ptr {kx.v}, null"), "KeyError: None")
                if is_sopt(kx.t):
                    key = self.to_slot(self.deref(kx))  # (an int key is the int its box holds)
            cur = self.from_slot(self.rt("pys_dict_getitem", "i64", [f"ptr {o.v}", f"i64 {key}"]), kv[1])
            r = self.coerce(self.inplace(op, cur, n.kids[1]), kv[1])
            self.rt("pys_dict_set", "void", [f"ptr {o.v}", f"i64 {key}", "i64 " + self.to_slot(r)])
        elif o.t in self.classes:
            # o[k] op= v: o.__setitem__(k, o.__getitem__(k) op v), k evaluated once
            ik = self.expr(t.kids[1], self.argtype(o.t, "__getitem__", 1, f"'{tname(o.t)}' object is not subscriptable"))
            self.argtype(o.t, "__setitem__", 1, f"'{tname(o.t)}' object does not support item assignment")
            self.notnone(o, sub)
            cur = self.protocol(o, "__getitem__", [ik])
            self.protocol(o, "__setitem__", [ik, self.inplace(op, cur, n.kids[1])])
        elif is_kw(o.t):
            self.err("changing **kwargs is not supported: copy it to a dict first (d = dict(kwargs))")
        else:
            self.err(f"'{o.t}' does not support item assignment")
    else:
        self.err("invalid target for augmented assignment")

def gen_may_change(self, b0: Blk, x0: int, n0: int) -> bool:
    # may an op built since position x0 of block b0, or in a block placed after the first n0
    # of the function, change a dict (wD) or run code of the program (U; every call, whose
    # callee's effects are not known yet)
    bad = FXBIT["wD"] | FXBIT["U"]
    for i in b0.code[x0:]:
        if self.opfx(i, self.fn.fa) & bad != 0:
            return True
    for b in self.fn.blocks[n0:]:
        for i in b.code:
            if self.opfx(i, self.fn.fa) & bad != 0:
                return True
    return False

def gen_inplace(self, op: str, cur: Val, rhs: Node) -> Val:
    # the new value of cur op= rhs: lists change in place (+= extends, *= repeats), objects
    # use __iadd__ & co when they define them, anything else is cur op rhs
    if is_list(unopt(cur.t)) and op == "+":
        b = self.expr(rhs, cur.t)
        if is_opt(cur.t) or is_opt(b.t):
            self.none_operands(op, cur, b, "+=")
            cur = Val(cur.v, unopt(cur.t))
            b = Val(b.v, unopt(b.t))
        if is_list(b.t) and b.t != cur.t and self.wider(b.t, cur.t) == cur.t:
            b = Val(b.v, cur.t)  # (as extend: the items are copied)
        self.rt("pys_list_extend", "void", [f"ptr {cur.v}", f"ptr {self.coerce(b, cur.t).v}"])
        return cur
    if is_list(unopt(cur.t)) and op == "*":
        b = self.as_int(self.expr(rhs, 'int'))
        if is_opt(cur.t):
            self.none_operands(op, cur, b, "*=")
            cur = Val(cur.v, unopt(cur.t))
        self.rt("pys_list_imul", "void", [f"ptr {cur.v}", f"i64 {self.coerce(b, 'int').v}"])
        return cur
    if is_set(unopt(cur.t)) and not is_fset(unopt(cur.t)) and (op == "|" or op == "&" or op == "-" or op == "^"):
        # s |= t, s &= t, s -= t, s ^= t of a set t: s changes in place (a frozenset s is
        # rebound to s op t, as CPython's has no in-place operators)
        b = self.expr(rhs, unopt(cur.t))
        if is_opt(cur.t) or is_opt(b.t):
            self.none_operands(op, cur, b, op + "=")
            cur = Val(cur.v, unopt(cur.t))
            b = Val(b.v, unopt(b.t))
        if not is_set(b.t):
            self.err(f"unsupported operand type(s) for {op}=: '{tname(cur.t)}' and '{tname(b.t)}'")
        if self.wider(selem(b.t), selem(cur.t)) != selem(cur.t):
            self.err(f"unsupported operand types for {op}=: {typestr(cur.t)} and {typestr(b.t)} (a set holds elements of one type)")
        if op == "&":
            self.rt("pys_set_assign", "void", [f"ptr {cur.v}", f"ptr {self.rt('pys_set_and', 'ptr', [f'ptr {cur.v}', f'ptr {b.v}'])}"])
        else:
            self.rt("pys_set_update" if op == "|" else "pys_set_isub" if op == "-" else "pys_set_ixor", "void", [f"ptr {cur.v}", f"ptr {b.v}"])
        return cur
    im = "__i" + DUNDER.get(op, "__?")[2:]
    if cur.t in self.classes and im in self.classes[cur.t].methods:
        b = self.expr(rhs, "")
        self.none_operand(op + "=", cur, b)
        return self.call_fn(self.classes[cur.t].methods[im], [cur, b], [])
    return self.arith(op, cur, self.expr(rhs, cur.t), op + "=")

def gen_objlen(self, v: Val) -> Val:
    r = self.as_int(self.call_fn(self.classes[v.t].methods["__len__"], [v], []))
    self.guard(self.ins(f"icmp slt i64 {r.v}, 0"), "ValueError: __len__() should return >= 0")
    return r

def gen_none_operand(self, op: str, a: Val, b: Val) -> None:
    # a is None: TypeError naming b's run-time type, as CPython reports it
    if a.t not in self.classes or a.v in self.nn:
        return
    lerr = self.label()
    lok = self.label()
    self.cbr(self.ins(f"icmp eq ptr {a.v}, null"), lerr, lok)
    self.place(lerr)
    m1 = self.sconst(f"unsupported operand type(s) for {op}: 'NoneType' and 'NoneType'")
    m2 = self.sconst(f"unsupported operand type(s) for {op}: 'NoneType' and '{tname(unopt(b.t))}'")
    self.raise_("TypeError", self.select(self.isnull(b), Val(m1, "str"), Val(m2, "str")))
    self.place(lok)

def gen_none_operands(self, op: str, a: Val, b: Val, shown: str) -> None:
    # a op b with an optional operand that is None: CPython's TypeError, which names the other
    # operand's run-time type, or for str + None and list + None its own message
    sh = shown if shown != "" else "** or pow()" if op == "**" else op
    x = unopt(a.t)
    y = unopt(b.t)
    if is_opt(a.t):
        m1 = self.sconst(f"unsupported operand type(s) for {sh}: 'NoneType' and 'NoneType'")
        m2 = self.sconst(f"unsupported operand type(s) for {sh}: 'NoneType' and '{tname(y)}'")
        if op == "*" and is_sopt(a.t) and (y == "str" or is_list(y)):
            m2 = self.sconst("can't multiply sequence by non-int of type 'NoneType'")
        lerr = self.label()
        lok = self.label()
        self.cbr(self.ins(f"icmp eq ptr {a.v}, null"), lerr, lok)
        self.place(lerr)
        self.raise_("TypeError", self.select(self.ins(f"icmp eq ptr {b.v}, null"), Val(m1, "str"), Val(m2, "str")) if is_opt(b.t) else m2)
        self.place(lok)
    if is_opt(b.t):
        msg = f"unsupported operand type(s) for {sh}: '{tname(x)}' and 'NoneType'"
        if op == "+" and x == y and (x == "str" or is_list(x)):
            msg = "'NoneType' object is not iterable" if sh == "+=" and is_list(x) else f'can only concatenate {tname(x)} (not "NoneType") to {tname(x)}'
        elif op == "*" and (x == "str" or is_list(x)):
            msg = "can't multiply sequence by non-int of type 'NoneType'"
        self.guard(self.ins(f"icmp eq ptr {b.v}, null"), "TypeError: " + msg)

def gen_hide(self, names: list[str]) -> None:
    # comprehension variables shadow outer names once the iterable has been evaluated
    for nm in names:
        if nm in self.ltype:
            del self.ltype[nm]
        self.compvars[nm] = self.compvars.get(nm, 0) + 1

def gen_iterarg(self, arg: IterArg | None) -> None:
    if arg is not None and arg.split != "":
        # the iterator is made: what follows goes on at split, and the traversal compiled next
        # runs once a branch to trav starts it, after the consumer's other arguments
        arg.trav = self.label()
        self.br(arg.split)
        self.place(arg.trav)
    elif arg is not None:
        arg.value = self.expr(arg.node, "")

def gen_for_(self, n: Node, hide: list[str], arg: IterArg | None = None) -> None:
    tgt = n.kids[0]
    it = n.kids[1]
    body = n.kids[2].kids
    names: list[str] = []
    names_in(tgt, names)
    for nm in names:
        if nm in self.nonevars and nm not in self.ltype and nm not in hide:
            self.err(f"'{nm}' is None here, and binding it as a for loop's target is not supported")
    if it.kind == "call" and it.kids[0].kind == "name" and not self.bound(it.kids[0].s):
        fn = it.kids[0].s
        args = it.kids[1:]
        if fn == "range":
            vs = self.range_args(args)
            self.for_range(tgt, vs[0], vs[1], vs[2], body, hide, arg)
            return
        if fn == "reversed" and len(args) == 1 and args[0].kind == "call" and args[0].kids[0].kind == "name" and args[0].kids[0].s == "range" and not self.bound("range"):
            self.for_rrange(tgt, self.range_args(args[0].kids[1:]), body, hide, arg)
            return
        for a in args:
            if self.iterator_call(a) and (fn == "enumerate" or fn == "zip" or fn == "reversed"):
                self.err(f"{a.kids[0].s}() cannot be nested in {fn}() here; make it a list first, list({a.kids[0].s}(...))")
            if a.kind == "kw" and fn == "zip":
                self.err(f"zip({a.s}=...) is not supported")
        if ((fn == "enumerate" or fn == "reversed") and len(args) == 1) or (fn == "zip" and len(args) > 0):
            evs: list[Val] = []
            for a in args:
                v = self.expr(a, "")
                if fn == "reversed" and v.t in self.classes and v.t not in self.nts:
                    # (CPython calls __reversed__, or __len__ and __getitem__, never __iter__)
                    self.err(f"'{tname(v.t)}' object is not reversible" if "__getitem__" not in self.classes[v.t].methods else f"reversed() of {short(v.t)} by its __len__ and __getitem__ is not supported")
                evs.append(v if is_opt(v.t) or v.t in self.classes else self.iterable(v))  # (None raises, and __iter__ runs, once all are evaluated)
            notit = "TypeError: 'NoneType' object is not reversible" if fn == "reversed" else "TypeError: 'NoneType' object is not iterable"
            seqs: list[Val] = []
            if len(evs) == 1:
                seqs.append(self.iterable(evs[0], notit))
                self.for_seq(tgt, seqs, fn, body, "0", hide, arg)
            else:
                # zip() makes its iterators in turn, and a dict's or a set's records its size
                # then, before a later operand's __iter__ runs (which may change it)
                made = SeqStart()
                for v in evs:
                    seqs.append(self.iterable(v, notit))
                    self.seq_start(seqs[-1], fn, made)
                self.for_seq(tgt, seqs, fn, body, "0", hide, arg, made)
            for i in range(len(args)):
                self.close_temp(args[i], seqs[i])
            return
        if fn == "enumerate" and len(args) == 2 and (args[1].kind != "kw" or args[1].s == "start"):
            seq = self.expr(args[0], "")
            seq = seq if is_opt(seq.t) or seq.t in self.classes else self.iterable(seq)
            a1 = args[1].kids[0] if args[1].kind == "kw" else args[1]
            st = self.ival(a1).v
            seq = self.iterable(seq)
            self.for_seq(tgt, [seq], fn, body, st, hide, arg)
            self.close_temp(args[0], seq)
            return
    if it.kind == "call" and len(it.kids) == 1 and it.kids[0].kind == "attr":
        m = it.kids[0].s
        if m == "items" or m == "keys" or m == "values":
            o = self.unwrap(self.expr(it.kids[0].kids[0], ""), f"AttributeError: 'NoneType' object has no attribute '{m}'")
            if is_dict(o.t):
                self.for_seq(tgt, [o], m, body, "0", hide, arg)
            elif o.t == "kw[]" and m != "keys":
                # **kwargs of a call that passes no extra keyword arguments: no values, of the
                # type its annotation gives them (**kwargs: T), else of none. Only the parameter
                # itself is known to be this function's record: another name may hold one that
                # a call returned or passed in, from a function annotated otherwise
                f = self.curfn
                x = it.kids[0].kids[0]
                if f.kwarg >= 0 and f.kwelem != "" and x.kind == "name" and x.s == f.params[f.kwarg]:
                    et = f.kwelem if m == "values" else "tuple[str," + f.kwelem + "]"
                    self.for_seq(tgt, [self.expr(mk("list", "", it.line, []), "list[" + et + "]")], "", body, "0", hide, arg)
                    return
                self.iterarg(arg)
                self.hide(hide)
                return  # nothing to iterate: the body never runs (and its types are unknown), as for ()
            else:
                self.for_seq(tgt, [self.method(o, m, [])], "", body, "0", hide, arg)
            return
    if it.kind == "set" and folds(mk("tuple", "", it.line, it.kids)):
        # (CPython iterates the frozenset constant it makes of a display of constants)
        seq = self.set_display(it, "", True)
    else:
        seq = self.iterable(self.expr(it, ""))
    if seq.t == "tuple[]":
        self.iterarg(arg)
        self.hide(hide)  # (a comprehension's variables, which it forgets after the loop)
        return  # nothing to iterate: the body never runs (and its types are unknown)
    self.for_seq(tgt, [seq], "", body, "0", hide, arg)
    self.close_temp(it, seq)

def gen_iterable(self, v: Val, msg: str = "TypeError: 'NoneType' object is not iterable") -> Val:
    # what a for loop steps through (for_seq): a tuple as it is, whose items must then share
    # one type (with PYSTACHY_OPT=-tupleiter, a list of them), an object the list its __iter__
    # steps through; None raises msg
    v = self.unwrap(v, msg)
    if is_kw(v.t):
        return self.kw_list(v)  # (iterating **kwargs gives the names)
    if v.t in self.nts:
        self.notnone(v, msg)
        v = self.ntup(v, True)  # (the tuple of its fields)
    if v.t in self.classes:
        return self.obj_iter(v, msg, f"'{tname(v.t)}' object is not iterable")
    if is_tuple(v.t) and "tupleiter" in self.opts and all(x == targs(v.t)[0] for x in targs(v.t)):
        return v  # (no list: for_seq reads its slots, as many as its type has)
    if not is_tuple(v.t) or v.t == "tuple[]":
        return v
    ts = targs(v.t)
    for x in ts:
        if x != ts[0]:
            self.err(f"cannot iterate over {typestr(v.t)}: its items have different types")
    return self.as_list(v, "iter")

def gen_ival(self, n: Node, none: str = "") -> Val:
    # an index, slice bound or range() argument: an int, or a bool used as one (as CPython does);
    # an int | None that is None raises none ("Kind: text")
    v = self.expr(n, "int")
    if is_sopt(v.t) and none != "":
        v = self.unwrap(v, none)
    return self.coerce(self.as_int(v), "int")

def gen_range_args(self, args: list[Node]) -> list[str]:
    # A call evaluates every argument before checking their index types.
    vals = [self.expr(a, "int") for a in args]
    vs: list[str] = []
    for v in vals:
        if is_sopt(v.t):
            v = self.unwrap(v, "TypeError: 'NoneType' object cannot be interpreted as an integer")
        vs.append(self.coerce(self.as_int(v), "int").v)
    if len(vs) == 1:
        vs.insert(0, "0")
    if len(vs) == 2:
        vs.append("1")
    if len(vs) != 3:
        self.err("range() takes 1 to 3 arguments")
    return vs

def gen_for_range(self, tgt: Node, start: str, stop: str, step: str, body: list[Node], hide: list[str], arg: IterArg | None = None) -> None:
    if step.startswith("%") or int(step) == 0:
        self.guard(self.ins(f"icmp eq i64 {step}, 0"), "ValueError: range() arg 3 must not be zero")
    self.iterarg(arg)
    self.hide(hide)
    after = self.forget(body, tgt)
    ctr = self.alloca("int", "")
    self.emit(f"store i64 {start}, ptr {ctr}")
    lc = self.label()
    lb = self.label()
    ls = self.label()
    le = self.label()
    lp = Loop("range", lc, lb, ls, le)
    lp.ctr = ctr
    lp.stop = Val(stop, "int")
    self.fn.loops.append(lp)
    self.place(lc)
    i = self.ins(f"load i64, ptr {ctr}")
    if not step.startswith("%"):
        c = self.ins(f"icmp {'slt' if int(step) > 0 else 'sgt'} i64 {i}, {stop}")
    else:
        up = self.ins(f"icmp slt i64 {i}, {stop}")
        dn = self.ins(f"icmp sgt i64 {i}, {stop}")
        pos = self.ins(f"icmp sgt i64 {step}, 0")
        c = self.select(pos, Val(up, "bool"), Val(dn, "bool"))
    self.cbr(c, lb, le)
    self.place(lb)
    self.assign(tgt, Val(i, "int"))
    self.loop(body, lp)
    self.place(ls)
    if self.rtmode and (step == "1" or step == "-1"):
        # i < stop (or i > stop), so i + 1 (i - 1) fits: an nsw add, which lets LLVM bound i
        # and drop the index checks that compare it with a length. (This would hold for every
        # program, but it changes their IR: see docs/runtime-in-subset.md.)
        self.emit(f"store i64 {self.ins(f'add nsw i64 {i}, {step}')}, ptr {ctr}")
        self.br(lc)
        self.place(le)
        return
    # a step that overflows 64 bits has passed any stop value: the loop is over
    r = self.checked("+", i, step)
    self.emit(f"store i64 {r[0]}, ptr {ctr}")
    self.cbr(r[1], le, lc)
    self.place(le)
    self.narrowed = after

def gen_for_rrange(self, tgt: Node, vs: list[str], body: list[Node], hide: list[str], arg: IterArg | None = None) -> None:
    # reversed(range(a, b, s)): the range's items from the last, a + k*s for k = len-1 .. 0
    # (the length is unsigned, and the arithmetic wraps: every result is an item of the range)
    n = self.rt("pys_range_len", "i64", [f"i64 {vs[0]}", f"i64 {vs[1]}", f"i64 {vs[2]}"])
    self.iterarg(arg)
    self.hide(hide)
    after = self.forget(body, tgt)
    ctr = self.alloca("int", "")
    self.emit(f"store i64 {n}, ptr {ctr}")
    lc = self.label()
    lb = self.label()
    ls = self.label()
    le = self.label()
    lp = Loop("rrange", lc, lb, ls, le)
    lp.ctr = ctr
    self.fn.loops.append(lp)
    self.place(lc)
    c = self.ins(f"load i64, ptr {ctr}")
    self.cbr(self.ins(f"icmp ne i64 {c}, 0"), lb, le)
    self.place(lb)
    k = self.ins(f"sub i64 {c}, 1")
    self.emit(f"store i64 {k}, ptr {ctr}")
    self.assign(tgt, Val(self.ins(f"add i64 {vs[0]}, {self.ins(f'mul i64 {k}, {vs[2]}')}"), "int"))
    self.loop(body, lp)
    self.place(ls)
    self.br(lc)
    self.place(le)
    self.narrowed = after

def gen_for_seq(self, tgt: Node, seqs: list[Val], mode: str, body: list[Node], start: str, hide: list[str], arg: IterArg | None = None, made: SeqStart | None = None) -> None:
    # One loop serves lists, strings, tuples, dicts, sets, enumerate, zip and reversed. Each
    # round takes the next item of every sequence, in order, the way its CPython iterator
    # would: lists and strings by index, checked against their current length (reversed:
    # counting down from the length at the start), tuples by index below the length their type
    # gives; dicts by entry position, skipping deleted entries and failing if the dict changed
    # size; sets by slot, failing if the set changed size. The loop ends at the first
    # exhausted sequence. made: the state of each iterator, taken as it was made (seq_start),
    # else taken now
    ctr = self.alloca("int", "")
    self.emit(f"store i64 0, ptr {ctr}")
    if made is None:
        made = SeqStart()
        for s in seqs:
            self.seq_start(s, mode, made)
    st = made.st
    used = made.used
    self.iterarg(arg)
    self.hide(hide)
    after = self.forget(body, tgt)
    lc = self.label()
    ls = self.label()
    le = self.label()
    lp = Loop("seq", lc, "", ls, le)
    lp.mode = mode
    lp.seqs = seqs
    lp.ctr = ctr
    self.fn.loops.append(lp)
    self.place(lc)
    i = self.ins(f"load i64, ptr {ctr}")
    at: list[str] = []
    for k in range(len(seqs)):
        s = seqs[k]
        if s.t == "file":
            j = self.rt("pys_file_readline", "ptr", [f"ptr {s.v}"])
            ok = self.ins(f"icmp ne i64 {self.ins(f'load i64, ptr {j}')}, 0")
            nx = ""
        elif is_set(s.t):
            # the slot of the next element, as CPython's set iterator finds it
            j = self.rt("pys_set_next", "i64", [f"ptr {s.v}", f"i64 {self.ins(f'load i64, ptr {st[k]}')}", f"i64 {used[k]}"])
            nx = self.ins(f"add i64 {j}, 1")
            ok = self.ins(f"icmp sge i64 {j}, 0")
        elif is_dict(s.t):
            p = self.ins(f"load i64, ptr {st[k]}")
            if mode == "reversed":
                j = self.rt("pys_dict_prev", "i64", [f"ptr {s.v}", f"i64 {p}", f"i64 {used[k]}", f"i64 {i}"])
                nx = self.ins(f"sub i64 {j}, 1")
            else:
                j = self.rt("pys_dict_next", "i64", [f"ptr {s.v}", f"i64 {p}", f"i64 {used[k]}", f"i64 {i}"])
                nx = self.ins(f"add i64 {j}, 1")
            ok = self.ins(f"icmp sge i64 {j}, 0")
        elif mode == "reversed":
            j = self.ins(f"sub i64 {self.ins(f'sub i64 {st[k]}, 1')}, {i}")
            # 0 <= j < the current length, as CPython's reversed iterator checks
            ok = self.ins(f"icmp ult i64 {j}, {self.ins(f'load i64, ptr {s.v}') if is_list(s.t) else st[k]}")
        else:
            j = i
            ok = self.ins(f"icmp slt i64 {i}, {self.ins(f'load i64, ptr {s.v}') if not is_tuple(s.t) else st[k]}")
        go = self.label()
        self.cbr(ok, go, le)
        self.place(go)
        lp.body = go
        lp.tests.append(go)
        lp.idx.append(j)
        if is_dict(s.t) or is_set(s.t):
            self.emit(f"store i64 {nx}, ptr {st[k]}")
        at.append(j)
    vals: list[Val] = []
    if mode == "enumerate":
        vals.append(Val(i if start == "0" else self.iop("+", i, start), "int"))
    for k in range(len(seqs)):
        s = seqs[k]
        j = at[k]
        if is_list(s.t):
            vals.append(self.from_slot(self.rt("pys_list_get", "i64", [f"ptr {s.v}", f"i64 {j}"]), elem(s.t)))
        elif is_vtuple(s.t):
            off = self.ins(f"add i64 {j}, 1")
            vals.append(self.from_slot(self.ins(f"load i64, ptr {self.ins(f'getelementptr i64, ptr {s.v}, i64 {off}')}"), targs(s.t)[0]))
        elif is_tuple(s.t):
            vals.append(self.from_slot(self.ins(f"load i64, ptr {self.ins(f'getelementptr i64, ptr {s.v}, i64 {j}')}"), targs(s.t)[0]))
        elif s.t == "str":
            vals.append(Val(self.rt("pys_str_get", "ptr", [f"ptr {s.v}", f"i64 {j}"]), "str"))
        elif s.t == "file":
            vals.append(Val(j, "str"))
        elif is_set(s.t):
            vals.append(self.from_slot(self.rt("pys_set_key", "i64", [f"ptr {s.v}", f"i64 {j}"]), selem(s.t)))
        else:
            kv = targs(s.t)
            if mode != "values":
                vals.append(self.from_slot(self.rt("pys_dict_key", "i64", [f"ptr {s.v}", f"i64 {j}"]), kv[0]))
            if mode == "values" or mode == "items":
                vals.append(self.from_slot(self.rt("pys_dict_val", "i64", [f"ptr {s.v}", f"i64 {j}"]), kv[1]))
    if len(vals) == 1 and mode != "zip":
        self.assign(tgt, vals[0])
    elif (tgt.kind == "tuple" or tgt.kind == "list") and len(tgt.kids) == len(vals):
        for k2 in range(len(vals)):
            self.assign(tgt.kids[k2], vals[k2])
    else:
        self.assign(tgt, self.tuple_(vals))
    self.loop(body, lp)
    self.place(ls)
    nx2 = self.ins(f"add i64 {i}, 1")
    self.emit(f"store i64 {nx2}, ptr {ctr}")
    self.br(lc)
    self.place(le)
    self.narrowed = after

def gen_seq_start(self, s: Val, mode: str, made: SeqStart) -> None:
    # the state of an iterator over sequence s (for_seq, in mode), as CPython's takes it when it
    # is made: a dict's or a set's size, and the slot it reads first; a list's or a str's
    # length, from which reversed() counts down
    if is_set(s.t) and mode == "reversed":
        self.err(f"'{tname(s.t)}' object is not reversible")
    if not (s.t == "str" or is_list(s.t) or is_vtuple(s.t) or is_dict(s.t) or is_set(s.t) or (s.t == "file" and mode != "reversed") or (is_tuple(s.t) and s.t != "tuple[]")):
        self.err(f"cannot iterate over {s.t}" if s.t != "file" else "a file is not reversible")
    if s.t == "file":
        made.st.append("")
        made.used.append("")
        return
    n0 = self.ins(f"load i64, ptr {s.v}") if not is_tuple(s.t) else str(len(targs(s.t)))
    made.used.append(n0)
    if is_dict(s.t) or is_set(s.t):
        pos = self.alloca("int", "")
        p0 = "0"
        if mode == "reversed":
            p0 = self.ins(f"sub i64 {self.rt('pys_dict_end', 'i64', [f'ptr {s.v}'])}, 1")
        self.emit(f"store i64 {p0}, ptr {pos}")
        made.st.append(pos)
    else:
        made.st.append(n0)

# ---- narrowing: optional locals known not to be None
