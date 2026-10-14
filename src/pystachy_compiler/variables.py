"""Variables component of the self-hosting Pystachy compiler."""
from __future__ import annotations
import os
from src.pystachy_compiler.analysis import (
    aliases,
    assigns,
    chk_names,
    closure_free,
    deleted,
    globals_in,
    lambda_def,
    lambda_flags,
    local_names,
    nested_defs,
    only_none,
    scope_binds,
    shows_items,
    stmt_binds,
    typed_default,
)
from src.pystachy_compiler.diagnostics import MODDUNDERS, where
from src.pystachy_compiler.ir import Blk, Closure, FnInfo, Frame, Ins, Val
from src.pystachy_compiler.names import owner, short
from src.pystachy_compiler.specs import INERT_DECOS, NONEVAR, OPTTYPES, PYBUILTINS, UNSUPPORTED
from src.pystachy_compiler.syntax import Node, mk, name_targets, names_in
from src.pystachy_compiler.utils import (
    elem,
    elem_problem,
    empty_ann,
    empty_default,
    empty_display,
    is_const,
    is_dict,
    is_fset,
    is_kw,
    is_list,
    is_opt,
    is_set,
    is_tuple,
    key_problem,
    lt,
    same_kind,
    selem,
    targs,
    tname,
    typestr,
    unopt,
)


def gen_global_var(self, g: str, ty: str) -> None:
    # every module-level variable, visible or hidden, is defined here: the garbage
    # collector scans the pointer-typed ones, whose addresses @main hands to pys_init
    self.globs.append(f"{g} = internal global {ty} zeroinitializer")
    if ty == "ptr":
        self.gcroots.append(g)

def gen_is_global(self, name: str) -> bool:
    if name in self.ltype or name in self.compvars:
        return False
    return self.modlevel or name in self.gdecl or "$" in name

def gen_unbound_local(self, name: str) -> bool:
    # a local of the function that is not declared yet: one that the function assigns later
    # (which hides the module's variable, function, class or import of that name)
    return name in self.assigned and name not in self.gdecl and name not in self.ltype

def gen_read_ahead(self, name: str) -> None:
    # a read of name where it is such a local, which CPython reads unbound there
    # (UnboundLocalError): an error, as a read before a local's first assignment is
    if self.unbound_local(name):
        self.err(f"local variable '{name}' is read before its first assignment; declare it first ({name}: T)")

def gen_class_ahead(self, name: str) -> None:
    # read_ahead() for a read of class name (C.x, C.m(), isinstance(o, C)), but not while dry()
    # types an expression from further on in the function (lookahead()), where the function may
    # have bound the name by then: the read is checked where it is compiled
    if self.drying == 0:
        self.read_ahead(name)

def gen_no_type(self, name: str) -> None:
    # the error for the empty list or dict of variable name, still without a type where a use
    # needs it (an annotation of it belongs where the container was made, see origin)
    t = self.qtype(name)
    src = name
    while src in self.origin and name not in self.ltype:
        src = self.origin[src]
    self.err(f"cannot infer the type of '{short(name)}', an empty {tname(t)} so far: annotate it{self.where_def(src)} ({short(src)}: {empty_ann(t)})")

def gen_load_name(self, name: str) -> Val:
    if (name in self.nonevars or name in self.noneglobals) and name not in self.ltype:
        return Val("null", "None")
    if "?" in self.qtype(name) and not self.allowq and self.lookahead(name) == "":
        t = self.qtype(name)
        if self.unfilled(name) and self.dead and not aliases(self.curfn.node.kids[2], name):
            # only code these argument types leave out fills it, and nothing else gets it to
            # fill: it is always empty here
            self.refine(name, "list[int]" if is_list(t) else "set[int]" if is_set(t) else "dict[int,int]")
            self.guessed[self.curfn.ll] = f"'{name}' of {short(self.curfn.name)}() is always empty for these arguments, and taken as {typestr(self.ltype[name])}: annotate it ({name}: {empty_ann(t)})"
        elif not self.globread(name) or self.copying or "?" in self.early(name):
            self.no_type(name)
    if name in self.ltype:
        t = self.ltype[name]
        if t == NONEVAR:
            t = self.none_read(name)
            if t == "None":
                return Val("null", "None")
        r = self.ins(f"load {lt(t)}, ptr {self.lreg[name]}")
        if name == self.selfname and name not in self.compvars:
            self.nn[r] = True
        if name in self.narrowed and is_opt(t) and t != NONEVAR:
            return self.deref(Val(r, t))  # known not to be None here
        return Val(r, t)
    self.read_ahead(name)
    if name in self.gtypes:
        t = self.gtypes[name]
        r = self.ins(f"load {lt(t)}, ptr @g.{name}")
        if is_opt(t):
            self.wide[self.curfn.ll + r] = True  # (not narrowed, see coerce)
        return Val(r, t)
    if name == "__name__":
        return Val(self.sconst("__main__"), "str")
    if name in self.aliases:
        return self.modattr(self.aliases[name])
    if name in self.funcs:
        return self.fn_value(name)
    if name in self.classes:
        self.err(f"class '{name}' cannot be used as a value (classes are not values: call it, or read an attribute, C.x)")
    if name in self.fglobals:
        self.err(f"name '{name}' is not defined yet here: a function assigns it, so declare it at module level{self.where_def(name)} first ({short(name)}: T)")
    if name in self.mvars and owner(name) != self.curfn.mod and owner(name) not in self.inited and self.comp[owner(name)] == self.comp[self.curfn.mod]:
        # (see ahead; this module imports that one, as it reads its global: that module imports
        # this one back if both are in one component of the import graph)
        self.err(f"'{short(name)}' of module {owner(name)} is read here while that module is still being imported (a circular import), when only its constants (NAME = literal) can be read: read it in a function that runs after the import")
    if name in self.mvars and owner(name) != self.curfn.mod and owner(name) not in self.inited:
        # no cycle: this module imports it later (in a function), so its code is compiled later
        self.err(f"the type of '{short(name)}' of module {owner(name)} is not known here, as this module's code is compiled before that module's code, which it imports later: import {owner(name)} at the top of {self.mfile[self.curfn.mod]}")
    if name in self.mvars:
        src = self.origin.get(name, name)
        self.err(f"the type of '{short(name)}' is not known yet here, before its module's code assigns it: declare it at module level{self.where_def(src)} first ({short(src)}: T)")
    if name in self.unsupported:
        self.err(self.unsupported[name])
    if name in PYBUILTINS and name[0].islower():
        return Val("null", f"fn[b:{name}]")  # (a builtin function, or a class such as int: calling it calls it)
    if name in PYBUILTINS:
        self.err(f"the builtin '{name}' cannot be used as a value (not supported)")
    if name in MODDUNDERS.split():
        self.err(f"'{name}' is not supported")  # (a module attribute that CPython defines)
    if name in self.typevars:
        self.err(f"TypeVar '{short(name)}' cannot be used as a value (only annotations may name it)")
    self.err(f"name '{short(name)}' is not defined")
    return Val("", "")

def gen_applies(self, st: Node, top: bool, loc: dict[str, bool]) -> bool:
    # does def st have a decorator that CPython calls on the function: one Pystachy does not
    # leave out, typing's (overload, final, ...) or, at a module's top level (top), another of
    # INERT_DECOS (ffi.extern; staticmethod and the like, which declare_fn rejects there). One
    # named by a variable of the function the def is in (loc) is that variable, not an import
    for x in st.kids[3:]:
        if x.s == "async":
            continue
        if (x.s[: x.s.find(".")] if "." in x.s else x.s) in loc:
            return True
        key = self.imported(x.s) if self.imported(x.s) != "" else x.s
        key = key[9:] if key.startswith("builtins.") else key
        typing = key.startswith("typing.") or key.startswith("typing_extensions.")
        if not typing and not (top and "f" in INERT_DECOS.get(key, "")):
            return True
    return False

def gen_scope_names(self) -> dict[str, bool]:
    # the names local to the function being compiled: its parameters, the variables it binds
    # anywhere, and those it takes from the functions around it
    out: dict[str, bool] = {}
    for nm in self.ltype:
        out[nm] = True
    for nm in self.curfn.params:
        out[nm] = True
    if self.curfn.node.kind == "def":
        local_names(self.curfn.node.kids[2].kids, out)
    return out

def gen_decorate(self, n: Node) -> Val:
    # def n with decorators: CPython evaluates the decorators, from the top (a call, @d(args), runs
    # then), makes the function (its defaults first), and calls each decorator, from the bottom,
    # with what the one below gave; n's name binds the last result
    callees: list[Node] = []
    decos = [x for x in n.kids[3:] if x.s != "async"]  # (from the bottom up, as the parser adds them)
    for i in range(len(decos) - 1, -1, -1):
        self.line = decos[i].line
        self.modchk(decos[i])  # (a name that an import in a try statement binds: Loader.qdeco)
        e = self.deco_callee(decos[i], self.curfn.mod)
        callees.append(self.vnode(self.call(e, "")) if len(decos[i].kids) > 0 else e)
    v = self.closure(n)
    for j in range(len(callees) - 1, -1, -1):
        self.line = callees[j].line
        v = self.call(mk("call", "", callees[j].line, [callees[j], self.vnode(v)]), "")
    return v

def gen_deco_callee(self, x: Node, mod: str) -> Node:
    # what decorator x, of module mod, evaluates to the function it calls: its call @d(args), or
    # its dotted name as name and attribute nodes, made once, so that a read flow analysis
    # marks (Node.chk) is the one decorate compiles
    if len(x.kids) > 0:
        return x.kids[0]
    key = f"{mod} {x.line}"
    if key not in self.decoexprs:
        e = mk("name", x.s[: x.s.find(".")] if "." in x.s else x.s, x.line, [])
        for part in x.s.split(".")[1:]:
            e = mk("attr", part, x.line, [e])
        self.decoexprs[key] = e
    return self.decoexprs[key]

def gen_cellvars(self, f: FnInfo, body: list[Node]) -> list[str]:
    # the variables of function f that the defs and lambdas in it take (closure_free): its
    # parameters and the names it binds, but those it declares global or nonlocal
    ds: list[Node] = []
    for st in body:
        nested_defs(st, ds)
    out: list[str] = []
    if len(ds) == 0:
        return out
    loc: dict[str, bool] = {}
    for p in f.params:
        loc[p] = True
    decl: dict[str, str] = {}
    scope_binds(body, loc, decl)
    for d in ds:
        free: dict[str, bool] = {}
        closure_free(d if d.kind == "def" else lambda_def(d), free)
        for x in free:
            if x in loc and x not in decl and x not in out:
                out.append(x)
    return out

def gen_qualname(self, f: FnInfo) -> str:
    # f's __qualname__: a method's is Class.name, a closure's outer.<locals>.name
    if f.clo >= 0:
        return self.closures[f.clo].qual
    return f"{short(f.cls)}.{f.name}" if f.cls != "" else short(f.name)

def gen_closure(self, n: Node) -> Val:
    # def or lambda n inside a function (or a lambda in module code): a new function value. Its
    # env holds the cells of the variables it takes from around it, which the functions around it
    # keep them in (so it reads their values when it runs, and nonlocal assigns them), then the
    # default values that are no constants, which CPython evaluates when the def runs, then the
    # cells of the flags of the names a lambda reads that an import in a try statement binds
    what = "the lambda" if n.kind == "lambda" else f"{n.s}()"
    if n.mchk != "":
        x = n.mchk.split(" ")[0]
        if n.kind == "def" and x == n.s:
            self.err(f"{what} reads its own name, which binds what its decorators give once they have run: not supported in a def inside a function")
        self.err(f"{what} reads '{x}', which may not be assigned yet where it is defined: not supported (a function reads the variables around it when it runs: assign '{x}' before the {'lambda' if n.kind == 'lambda' else 'def'})")
    key = f"{self.curfn.ll} {n.line}:{n.s if n.kind == 'lambda' else 'def ' + n.s}"
    c = self.closures[self.clokeys[key]] if key in self.clokeys else self.new_closure(n, key)
    f = c.f
    dvals: list[Val] = []
    for j in c.defs:
        t = f.ptypes[j]
        v = self.expr(f.defaults[j], t)
        v = self.coerce(v, t) if t != "" else v
        if v.t == "None" and t == "":
            self.err(f"a default value None of a parameter of {what} is not supported here: annotate the parameter ({f.params[j]}: T | None = None)")
        if f.dtypes[j] == "":
            f.dtypes[j] = v.t
        dvals.append(self.coerce(v, f.dtypes[j]))
    env = self.rt("pys_alloc", "ptr", [f"i64 {8 * max(len(c.caps) + len(c.defs) + len(c.iflags), 1)}"])
    for i in range(len(c.caps)):
        if c.ctypes[i] != "None":
            x = c.caps[i]
            a = self.ins(f"getelementptr inbounds ptr, ptr {env}, i64 {i}")
            self.emit(f"store ptr {self.cells[x] if x in self.cells else self.lreg[x]}, ptr {a}")
    for j in range(len(dvals)):
        a = self.ins(f"getelementptr inbounds i64, ptr {env}, i64 {len(c.caps) + j}")
        self.emit(f"store {lt(dvals[j].t)} {dvals[j].v}, ptr {a}")
    for j in range(len(c.iflags)):
        a = self.ins(f"getelementptr inbounds ptr, ptr {env}, i64 {len(c.caps) + len(c.defs) + j}")
        self.emit(f"store ptr {self.iflag[c.iflags[j]]}, ptr {a}")
    self.nn[env] = True
    return Val(env, c.t)

def gen_new_closure(self, n: Node, key: str) -> Closure:
    # the function that def or lambda n compiles to where this function defines it (closure)
    d = n if n.kind == "def" else lambda_def(n)
    outer = self.curfn
    name = n.s if n.kind == "def" else "<lambda>"
    qual = name if self.modlevel else self.qualname(outer) + ".<locals>." + name
    idx = len(self.closures)
    f = self.declare_fn(mk("def", d.s, d.line, d.kids[:3]), "")  # (its decorators apply to the closure: decorate)
    f.ll = f"@c.{idx}"
    f.name = qual
    f.mod = outer.mod
    f.clo = idx
    f.generic = True
    f.ret = f.ret if d.kids[1].kind != "noann" else ""
    # its env is its first parameter, passed as a method's object is (CPython's messages leave it out)
    f.params.insert(0, ".env")
    f.ptypes.insert(0, "env")
    f.defaults.insert(0, mk("noann", "", n.line, []))
    f.dglob.insert(0, "")
    f.dtypes.insert(0, "")
    f.npos += 1
    f.posonly += 1
    if f.vararg >= 0:
        f.vararg += 1
    if f.kwarg >= 0:
        f.kwarg += 1
    c = Closure(f, name, qual)
    c.t = f"fn[c:{idx}:{qual}@{where(n.line)}]"  # (where it is defined, which messages show)
    self.closures.append(c)
    self.clokeys[key] = idx
    # the variables it takes: those of the function around it (its cells), and those that function
    # takes itself, which its env holds
    mine: dict[str, bool] = {}
    for x in self.closures[outer.clo].caps if outer.clo >= 0 else []:
        mine[x] = True
    free: dict[str, bool] = {}
    closure_free(d, free)
    # (a variable that a del unbinds, in the function around it or in this one, which a nonlocal
    # one may be: CPython's closure would find it unassigned, which nothing checks here)
    dels: dict[str, bool] = {}
    deleted(d.kids[2].kids, dels)
    if not self.modlevel and outer.node.kind == "def":
        deleted(outer.node.kids[2].kids, dels)
    for x in free:
        if x in self.compvars:
            self.err(f"{'the lambda' if n.kind == 'lambda' else name + '()'} reads '{x}', a variable of the comprehension it is in: not supported")
        if x not in self.cells and x not in mine:
            continue  # (a global, a builtin, or a name nothing binds)
        t = ""
        if n.kind == "def" and x == n.s and not self.applies(n, False, self.scope_names()):
            t = c.t  # its own name, assigned once it is made
        elif x in self.nonevars and x not in self.ltype:
            if x in self.assigned and x in self.cells:
                self.err(f"{'the lambda' if n.kind == 'lambda' else name + '()'} reads '{x}', a parameter whose argument is None here, which {short(outer.name)}() assigns: not supported (annotate the parameter)")
            t = "None"
        elif x in self.ltype:
            t = self.ltype[x]
            if t == NONEVAR or "?" in t:
                t = self.lookahead(x, True) if "?" in t else t
            if t == NONEVAR or "?" in t or t == "":
                self.err(f"cannot infer the type of '{x}', which {'the lambda' if n.kind == 'lambda' else name + '()'} reads, where it is defined: annotate it ({x}: T = ...)")
        else:
            self.err(f"{'the lambda' if n.kind == 'lambda' else name + '()'} reads '{x}', which is not assigned yet where it is defined: not supported (assign it before)")
        if x in dels:
            self.err(f"{'the lambda' if n.kind == 'lambda' else name + '()'} reads '{x}', which del unbinds: not supported")
        c.caps.append(x)
        c.ctypes.append(t)
        if x in self.nlw:
            c.nlw[x] = True
    # the defaults that are no constants: the env holds their values, after the cells
    for j in range(1, len(f.params)):
        if not is_const(f.defaults[j]):
            f.dglob[j] = f"&{len(c.caps) + len(c.defs)}"
            c.defs.append(j)
    lf: dict[str, bool] = {}
    if n.kind == "lambda":
        lambda_flags(n.kids[1], True, lf)  # (and its env the cells of their flags, after the defaults)
    for x in lf:
        c.iflags.append(x)
    # its locals that a read may find unassigned (flow_body marked those reads)
    marked: dict[str, bool] = {}
    for st in d.kids[2].kids:
        chk_names(st, marked)
    loc: dict[str, bool] = {}
    decl: dict[str, bool] = {}
    local_names(d.kids[2].kids, loc)
    globals_in(d.kids[2].kids, decl)
    for p in d.kids[0].kids:
        loc[p.s] = True
    for nm in marked:
        if nm in loc and nm not in decl and nm not in c.caps:
            f.uflags[nm] = True
    return c

def gen_fn_value(self, name: str) -> Val:
    # the program's function name as a value: a call through it calls the function, compiled as a
    # call of it by name is (call_value)
    f = self.funcs[name]
    if f.bad != "" and not f.generic:
        self.err(f.bad)  # (a template's is an error where a call needs an instance of it)
    return Val("null", f"fn[f:{name}]")

def gen_none_read(self, name: str) -> str:
    # a read of local name, which only None has been assigned so far: a binding of another value
    # in the function's source that can be typed here gives it its type, else only a comparison
    # with None may read it
    t = self.none_type(name)
    if t != "":
        self.ltype[name] = t
        return t
    body = self.curfn.node.kids[2].kids if self.curfn.node.kind == "def" else self.curfn.node.kids
    if only_none(body, name):
        return "None"  # (it is None wherever it is assigned)
    if not self.nonecmp:
        self.err(f"cannot infer the type of '{name}' from None here, before a value of another type is assigned to it; annotate it ({name}: T | None)")
    return NONEVAR

def gen_none_type(self, name: str) -> str:
    # the type of variable name, first assigned None: T | None for the first other value that
    # the code of its function (or module) assigns it, also by unpacking, that can be typed here
    # (as lookahead does); "" if there is none
    body = self.curfn.node.kids[2].kids if self.curfn.node.kind == "def" else self.curfn.node.kids
    found: list[Node] = []
    self.none_values(body, name, found)
    for e in found:
        if e.kind != "None" and not empty_display(e) and self.typed_now(e) and not self.calls_open(e, {}):
            # (typed as where it is assigned, under tests of the optional locals it reads)
            pre = self.narrowed
            self.narrowed = dict(pre)
            for nm in self.ltype:
                self.narrowed[nm] = True
            t = self.dry(e)
            self.narrowed = pre
            if t != "None" and t != "" and "?" not in t and t != NONEVAR:
                if self.optional(t) == "":
                    self.err(f"'{name}' is assigned None and {typestr(t)}, and None/Optional is only supported for {OPTTYPES}")
                return self.optional(t)
    return ""

def gen_none_values(self, body: list[Node], name: str, out: list[Node]) -> None:
    # the values that statements in body (into blocks, in order) assign to variable name: of
    # a, b = e the item of e (an index node if e is not a display)
    for st in body:
        if st.kind == "def" or st.kind == "class" or st.kind == "subclass":
            continue
        if st.kind == "assign":
            e = st.kids[-1]
            for t in st.kids[:-1]:
                if t.kind == "name" and t.s == name:
                    out.append(e)
                elif t.kind == "tuple" or t.kind == "list":
                    for i in range(len(t.kids)):
                        if t.kids[i].kind == "name" and t.kids[i].s == name:
                            disp = (e.kind == "tuple" or e.kind == "list") and len(e.kids) == len(t.kids)
                            out.append(e.kids[i] if disp else mk("index", "", e.line, [e, mk("int", str(i), e.line, [])]))
        for kid in st.kids:
            if kid.kind == "block":
                self.none_values(kid.kids, name, out)
            elif kid.kind == "except":
                self.none_values(kid.kids[1].kids, name, out)

def gen_read(self, n: Node) -> Val:
    # a variable read; if flow analysis found it may be unassigned, check at run time
    name = n.s
    self.gtype(name)
    constant = name in self.intglobals and self.globread(name) and self.gtypes.get(name, "") == "int"
    # The function's own def cannot run before an earlier direct assignment in its module.
    # That proves initialization even if flow conservatively marked an earlier import as
    # a possible call. Module code, foreign reads and functions defined earlier keep checks.
    initialized = constant and not self.modlevel and owner(name) == self.curfn.mod and self.curfn.node.kind == "def" and self.intat[name] < self.curfn.node.line
    if n.chk and name in self.ltype:
        if name in self.lflag and name not in self.compvars:
            bad = self.ins(f"xor i1 {self.ins(f'load i1, ptr {self.lflag[name]}')}, true")
            self.guard(bad, f"UnboundLocalError: cannot access local variable '{name}' where it is not associated with a value")
    elif not initialized and (n.chk or self.foreign(name)) and name in self.gflag and (name in self.gtypes or (name in self.funcs and name not in self.ltype)):
        # (a global, or a function whose def statement may not have run yet)
        bad = self.ins(f"xor i1 {self.ins(f'load i1, ptr @g.{name}.def')}, true")
        self.guard(bad, self.unbound(name, self.copying))
    if constant:
        # Keep a variable read dynamic for frontend rules (tuple index/length), while LLVM
        # folds the identity operation to a literal for opcode dispatch and other arithmetic.
        return Val(self.ins(f"add i64 {self.intglobals[name]}, 0"), "int")
    return self.load_name(name)

def gen_modchk(self, n: Node) -> None:
    # n reads a name that an import in a try statement binds, or a module's attribute through it
    # (Node.mchk): where no import has bound the name yet (that one raised, or did not run),
    # CPython finds it unbound, as its flag says (imp_flag). Then each submodule read as its
    # package's attribute, which an import sets once the submodule's code has run to its end: its
    # done flag, which is set from the start of the code and cleared if the code raises
    for c in n.mchk.split(";") if n.mchk != "" else []:
        p = c.split(" ")
        un = f"NameError: name '{p[1]}' is not defined"
        if p[2] == "A":
            un = f"AttributeError: module '{p[0][: p[0].rfind('.')]}' has no attribute '{p[1]}'"
        elif p[2] == "L" and self.curfn.clo >= 0 and self.closures[self.curfn.clo].name == "<lambda>":
            un = f"NameError: cannot access free variable '{p[1]}' where it is not associated with a value in enclosing scope"
        elif p[2] == "L":
            un = f"UnboundLocalError: cannot access local variable '{p[1]}' where it is not associated with a value"
        flag = f"@init.{p[0]}.done" if p[2] == "A" else self.imp_flag(p[0], p[2] == "G")
        self.guard(self.ins(f"xor i1 {self.ins(f'load i1, ptr {flag}')}, true"), un)

def gen_imp_flag(self, x: str, glob: bool) -> str:
    # the flag of name x, which an import in a try statement binds (Loader.import_binds()), set
    # where an import binds it ("bound" nodes): module code's (glob, x qualified) is a global,
    # a function's its slot, or the cell that the lambdas in it that read x share (lambda_flags)
    if glob:
        if x not in self.impg:
            self.impg[x] = True
            self.global_var(f"@g.{x}.imp", "i1")
        return f"@g.{x}.imp"
    if x not in self.iflag:
        self.n += 1
        i = Ins("slot", "bool", x)
        i.k = 1
        i.r = [self.n]
        self.fn.slots.append(i)
        self.iflag[x] = f"%{x}.def.{self.n}"
    return self.iflag[x]

def gen_foreign(self, name: str) -> bool:
    # another module's global that may be unbound when this code reads it
    return name in self.late and owner(name) != self.curfn.mod

def gen_unbound(self, name: str, imp: bool = False) -> str:
    # what CPython raises for reading name unbound (as M.x from another module, or imp: by
    # from M import x, naming the file of M, as found when compiling)
    if self.foreign(name) and imp:
        f = self.mfile[owner(name)]
        where = os.path.realpath(f) if f.endswith(".py") else "unknown location"
        return f"ImportError: cannot import name '{short(name)}' from '{owner(name)}' ({where})"
    if self.foreign(name):
        return f"AttributeError: module '{owner(name)}' has no attribute '{short(name)}'"
    return f"NameError: name '{short(name)}' is not defined"

def gen_qtype(self, name: str) -> str:
    # the type of variable name here, or ""
    if name in self.ltype:
        return self.ltype[name]
    if name not in self.compvars and (self.is_global(name) or name not in self.assigned):
        return self.gtypes.get(name, "")
    return ""

def gen_rtype(self, name: str) -> str:
    # the type of variable name read here (see gtype), or ""
    return self.gtype(name) if self.globread(name) else self.qtype(name)

def gen_globread(self, name: str) -> bool:
    # does reading name here read a module global
    return name not in self.ltype and name not in self.compvars and name not in self.nonevars and (self.is_global(name) or name not in self.assigned)

def gen_where_def(self, name: str) -> str:
    # " in FILE" for a global of another module than the code being compiled: where a fix-it goes
    return f" in {self.mfile[owner(name)]}" if "$" in name and owner(name) in self.mfile and owner(name) != self.curfn.mod else ""

def gen_gtype(self, name: str) -> str:
    # the type of module global name read here, also where the code that gives it its type
    # has not been compiled yet (see ahead and early), or ""
    if name not in self.gtypes and name in self.mvars and name not in self.noneglobals and not self.copying and self.globread(name) and self.ahead(name) == "":
        self.early(name)
    return self.gtypes.get(name, "")

def gen_ahead(self, name: str) -> str:
    # module global name, read by code compiled before its module's code assigns it (a template's
    # function called before that, a function compiled early): its first binding in that code
    # (in the branches that run, see live_blocks) gives it its type now, if it is an annotation,
    # or an assignment (also a, b = ...) whose value can be typed here (its variables have
    # types), or of an empty container that code fills (as lookahead finds it, also through
    # its twins); "" if not. Not for code of another module: that runs while the module is
    # still being imported (a circular import), and when the global is unbound then, CPython's
    # AttributeError says so and names the module's file
    if name in self.gtypes or name in self.busy or owner(name) not in self.inits or owner(name) != self.curfn.mod:
        return self.gtypes.get(name, "")
    self.busy[name] = True
    fr = self.modframe(owner(name), self.line)
    st = self.first_binding(self.inits[owner(name)].node.kids, name)
    if st is None:
        self.restore(fr)
        del self.busy[name]
        return ""
    self.line = st.line
    e = st.kids[-1]
    copying = self.copying
    self.copying = st.s == "from" and self.foreign(e.s)  # (see copying)
    if st.kind == "annassign" and st.kids[0].kind == "name":
        self.new_global(name, self.vtype(st.kids[1]))
    elif st.kind == "assign" and assigns(st, name) and self.empty_of(e) != "":
        self.new_global(name, "dict[?,?]" if e.kind == "dict" else f"{self.empty_of(e)}[?]")
        self.lookahead(name, True)
    elif st.kind == "assign" and len(st.kids) == 2 and assigns(st, name) and e.kind == "name" and not self.copying and self.globread(e.s) and "?" in self.gtype(e.s):
        # X = Y of such a container (from m import Y): twins (see stmt), typed as above
        self.new_global(name, self.gtypes[e.s])
        self.twin(name, e.s)
        self.lookahead(name, True)
    elif st.kind == "assign" and len(st.kids) == 2 and st.kids[0].kind == "tuple":
        t = self.unpacked(st, name)
        if t != "" and t != "None" and "?" not in t and name not in self.gtypes:
            self.new_global(name, t)
    elif st.kind == "assign" and assigns(st, name) and self.typed_now(e) and not self.calls_open(e, {}):
        t = self.dry(e)
        # (typing e may have typed name: a function it compiled assigns it, and the module's
        # code checks the value's type where it stores it)
        if t != "" and t != "None" and "?" not in t and name not in self.gtypes:
            self.new_global(name, t)
    if self.copying and name not in self.gtypes:
        self.origin[name] = e.s  # (a declaration of it belongs in its module, see load_name)
    self.copying = copying
    self.restore(fr)
    del self.busy[name]
    return self.gtypes.get(name, "")

def gen_unpacked(self, st: Node, name: str) -> str:
    # the type that a, b = ... (assignment st) gives name, one of its targets, if its value can
    # be typed here (see typed_now) and calls no template being compiled (see calls_open); or ""
    t0 = st.kids[0]
    e = st.kids[1]
    i = 0
    while i < len(t0.kids) and not (t0.kids[i].kind == "name" and t0.kids[i].s == name):
        i += 1
    if i == len(t0.kids):
        return ""
    if (e.kind == "tuple" or e.kind == "list") and len(e.kids) == len(t0.kids):
        e = e.kids[i]  # (each item is assigned on its own, see stmt)
        return self.dry(e) if self.typed_now(e) and not self.calls_open(e, {}) else ""
    if not self.typed_now(e) or self.calls_open(e, {}):
        return ""
    t = self.dry(e)
    if is_tuple(t):
        return targs(t)[i] if len(targs(t)) == len(t0.kids) else ""
    return elem(t) if is_list(t) else t if t == "str" else ""

def gen_twin(self, x: str, y: str) -> None:
    # module globals x and y hold the same empty container without a type (x = y): one type,
    # which the first use of either gives (an annotation belongs where y got the container)
    # (and the twins of either: from m2 import Y, where m2 did from m1 import Y)
    a = self.twin_of.get(x, x)
    b = self.twin_of.get(y, y)
    if a != b:
        if len(self.twin_set.get(a, [a])) < len(self.twin_set.get(b, [b])):
            c = a
            a = b
            b = c
        if a not in self.twin_set:
            self.twin_set[a] = [a]
            self.twin_of[a] = a
        for nm in self.twin_set.pop(b, [b]):
            self.twin_of[nm] = a
            self.twin_set[a].append(nm)
        self.origin[x] = y

def gen_twins(self, x: str) -> list[str]:
    # the twins of global x
    return [nm for nm in self.twin_set.get(self.twin_of.get(x, ""), []) if nm != x]

def gen_calls_open(self, n: Node, seen: dict[str, bool]) -> bool:
    # does n call, also through the templates' functions it calls (which a call compiles), a
    # template's function being compiled whose return type is not known yet (as the read that
    # ahead types may be in it)
    if n.kind == "call" and n.kids[0].kind == "name" and n.kids[0].s in self.funcs and self.funcs[n.kids[0].s].generic and n.kids[0].s not in seen:
        f = self.funcs[n.kids[0].s]
        seen[n.kids[0].s] = True
        for g in f.insts.values():
            if g.ret == "" or "?" in g.ret:
                return True  # (or whose return type is open, see retval)
        if self.calls_open(f.node.kids[2], seen):
            return True
    for k in n.kids:
        if self.calls_open(k, seen):
            return True
    return False

def gen_modframe(self, mod: str, line: int) -> Frame:
    # compile in the frame of module mod's top-level code from here (at line) to restore(the
    # frame returned)
    fr = self.save()
    self.modlevel = True
    self.lenient = False
    self.enter(self.inits[mod], [])
    self.line = line
    return fr

def gen_modtype(self, e: Node, mod: str) -> str:
    # the type of expression e of module mod's top-level code, compiled here into code that is
    # dropped; "" if a variable it reads has no type yet
    fr = self.modframe(mod, self.line)
    t = self.dry(e) if self.typed_now(e) else ""
    self.restore(fr)
    return t

def gen_early(self, name: str) -> str:
    # module global name, which has no type here or holds an empty container without one,
    # read before the function that shows its type is compiled: a function that assigns the
    # global or fills the container (or the twins of name, see twins) is compiled now
    names = [name] + self.twins(name)
    fs: list[FnInfo] = [f for f in self.funcs.values()]
    for ci in self.classes.values():
        if ci.bad == "" and ci.name not in self.tmpl:
            fs.extend(ci.methods.values())
    for f in fs:
        if name in self.gtypes and "?" not in self.gtypes[name]:
            break
        if f.generic or f.bad != "" or f.ll in self.compiled or not self.sets(f, names) or not self.decides(f, names) or self.unready(f.node.kids[2], f.mod, {}):
            continue
        self.making.append(f"compiling {f.name if f.cls == '' else f.cls + '.' + f.name}() for the type of '{name}' at {where(self.line)}")
        fr = self.save()
        self.modlevel = False
        self.lenient = False
        self.function(f, f.node.kids[2].kids)
        self.restore(fr)
        self.making.pop()
    return self.gtypes.get(name, "")

def gen_unready(self, n: Node, mod: str, seen: dict[str, bool]) -> bool:
    # does n, code of module mod, read a global without a type of another module whose code is
    # not compiled yet, also through the templates' functions it calls (which a call compiles):
    # compiled now (see early), it would seem to read it during a circular import
    if n.kind == "name" and n.s in self.mvars and n.s not in self.gtypes and n.s not in self.noneglobals and owner(n.s) != mod and owner(n.s) not in self.inited:
        return True
    if n.kind == "call" and n.kids[0].kind == "name" and n.kids[0].s in self.funcs and self.funcs[n.kids[0].s].generic and n.kids[0].s not in seen:
        f = self.funcs[n.kids[0].s]
        seen[n.kids[0].s] = True
        if self.unready(f.node.kids[2], f.mod, seen):
            return True
    for k in n.kids:
        if self.unready(k, mod, seen):
            return True
    return False

def gen_decides(self, f: FnInfo, names: list[str]) -> bool:
    # does the first fill of the containers names in function f (see fills) show what they
    # hold, so that compiling f now can give them a type: not d[k] = [] or d.setdefault(k, {}),
    # unless the type expected of the call types its empty default (return d.get(k, []))
    self.materialize(f)
    body = f.node.kids[2].kids
    fr = self.save()
    self.modlevel = False
    self.enter(f, body)
    found: list[Node] = []
    for nm in names:
        self.fills(body, nm, found)
    self.restore(fr)
    return len(found) == 0 or not empty_display(found[-1]) or typed_default(body, found[-1], is_list(f.ret) or is_dict(f.ret))

def gen_sets(self, f: FnInfo, names: list[str]) -> bool:
    # does function f assign one of the module globals names, or fill the container it holds
    body = f.node.kids[2].kids
    loc: dict[str, bool] = {}
    decl: dict[str, bool] = {}
    local_names(body, loc)
    globals_in(body, decl)
    for p in f.params:
        loc[p] = True
    if f.pending:
        loc[f.orig.kids[0].kids[0].s] = True  # the unrenamed cls is a class binding, never a global
    for nm in names:
        if (nm not in loc or nm in decl) and shows_items(mk("block", "", 0, body), nm):
            return True
    return False

def gen_first_binding(self, body: list[Node], name: str) -> Node | None:
    # the first statement in body, in order and into the blocks that run (see live_blocks; not
    # into functions and classes), that binds name (for none_ends, not to None)
    for st in body:
        if st.kind == "def" or st.kind == "class" or st.kind == "subclass":
            continue
        if stmt_binds(st, name) and not (self.whole < 0 and st.kind == "assign" and st.kids[-1].kind == "None"):
            return st
        for kid in self.live_blocks(st):
            r = self.first_binding(kid.kids, name)
            if r is not None:
                return r
    return None

def gen_only_empties(self, body: list[Node], name: str) -> bool:
    # is every binding of name in body (into the blocks that run) an assignment of an empty [],
    # {} or set()
    for st in body:
        if st.kind == "def" or st.kind == "class" or st.kind == "subclass":
            continue
        v = st.kids[-1] if st.kind == "assign" else st
        empty = len(st.kids) == 2 and st.kids[0].kind == "name" and self.empty_of(v) != ""
        if stmt_binds(st, name) and not empty:
            return False
        for kid in self.live_blocks(st):
            if not self.only_empties(kid.kids, name):
                return False
    return True

def gen_live_blocks(self, st: Node) -> list[Node]:
    # the blocks of statement st that a static test (see static) does not leave out: of an if
    # decided here the branch that runs, of a while loop whose test is false its else block
    # (and the bodies of a try statement's except clauses)
    s = -1 if st.kind != "if" and st.kind != "while" else self.static_now(st.kids[0]) if self.whole == 0 else self.static_whole(st.kids[0], st.line)
    bs: list[Node] = []
    for i in range(len(st.kids)):
        kid = st.kids[i]
        if kid.kind == "block" and not (st.kind == "if" and s >= 0 and i == (2 if s == 1 else 1)) and not (st.kind == "while" and s == 0 and kid.s != "else"):
            bs.append(kid)
        elif kid.kind == "except":
            bs.append(kid.kids[1])
    return bs

def gen_static_now(self, n: Node) -> int:
    # static(n), also in module code compiled before the code that types the globals n reads
    # (see ahead): they get their types first, as where the module's code compiles the test
    if self.modlevel:
        self.type_reads(n)
    return self.static(n)

def gen_static_whole(self, n: Node, line: int) -> int:
    # static_now(n) for the test of the if at line, in code that compiles later (see fills):
    # with the facts that hold there (see static_type)
    if self.modlevel:
        self.type_reads(n)
    here = self.line
    w = self.whole
    self.whole = line
    self.line = line
    self.unsure = False
    s = self.static(n)
    self.whole = w
    self.line = here
    return s

def gen_none_ends(self) -> None:
    # for each parameter whose argument is None, the line of the first statement, in the blocks
    # that may run, that binds it to something else than None (a large number if none does):
    # it is None before. Tests of them are decided by the lines found so far (at first none,
    # each one a line it is None up to at least), until they stay the same
    again = True
    while again:
        again = False
        for p in self.nonevars:
            self.whole = -1  # (live_blocks decides the tests as fills does)
            st = self.first_binding(self.curfn.node.kids[2].kids, p)
            self.whole = 0
            again = again or (st.line if st is not None else 1 << 40) != self.nonevars[p]
            self.nonevars[p] = st.line if st is not None else 1 << 40

def gen_type_reads(self, n: Node) -> None:
    if n.kind == "name":
        self.gtype(n.s)
    for k in n.kids:
        self.type_reads(k)

def gen_empty_of(self, e: Node) -> str:
    # the kind of empty container e makes without a type, "list", "dict" or "set" ([], {},
    # set() of the builtin set), or ""
    if (e.kind == "list" or e.kind == "dict") and len(e.kids) == 0:
        return e.kind
    if e.kind == "call" and len(e.kids) == 1 and e.kids[0].kind == "name" and e.kids[0].s == "set" and not self.bound("set"):
        return "set"
    return ""

def gen_empty(self, kind: str, name: str) -> Val:
    # [] or {} assigned to a variable without a type: the first use that shows what it holds
    # gives the variable its type (fill, refine); until then only len() and truth tests read it
    i = self.hole(kind)
    if self.is_global(name):
        self.gkk[name] = self.gkk.get(name, "") + f" {i.k}"
    else:
        self.lkk[name] = self.lkk.get(name, "") + f" {i.k}"
    return Val(f"%t{i.r[0]}", i.t)

def gen_refine(self, name: str, t: str, glob: bool = False) -> None:
    # the variable holding an empty list or dict gets the type its first use shows (the module
    # global name if glob), and so do its twins
    if "?" in t or "None" in targs(t):
        self.err(f"cannot infer the type of '{name}' from this use; annotate it")
    if is_dict(t):
        t = self.ctype("dict", [self.none_items(targs(t)[0]), targs(t)[1]])  # (d[k, None] = v)
    if is_set(t):
        t = self.ctype("frozenset" if is_fset(t) else "set", [self.none_items(selem(t))])  # (s.add((k, None)))
    toks = ""
    if name in self.ltype and not glob:
        self.ltype[name] = t
        toks = self.lkk.pop(name, "")
        if "?" in self.ret and name in self.qret.get(self.curfn.ll, "").split():
            self.adopt(t)  # the function returned it: so it returns t
    else:
        for nm in [name] + self.twins(name):
            if nm == name or "?" in self.gtypes[nm]:
                self.gtypes[nm] = t
                toks += " " + self.gkk.pop(nm, "")
    if is_dict(t) and key_problem(targs(t)[0]) != "":
        self.err(key_problem(targs(t)[0]))
    if is_set(t) and elem_problem(selem(t)) != "":
        self.err(elem_problem(selem(t)))
    for h in toks.split():
        self.holes[int(h)] = t
        if is_dict(t) or is_set(t):
            self.key_kind(targs(t)[0] if is_dict(t) else selem(t))  # (a tuple key's descriptor, a string constant from here on, which lowering prints)

def gen_lookahead(self, name: str, ahead: bool = False) -> str:
    # an empty list or dict read before the code that fills it: the first use in this
    # function's source that shows its items (an append, d[k] = v, ...; of name or of a twin
    # of the global name) decides its type now, if the item expression reads only variables
    # whose types are already known here (for ahead, whose read may be in a template's
    # function being compiled, and calls none, see calls_open); "" if there is no such use
    body = self.curfn.node.kids[2].kids if self.curfn.node.kind == "def" else self.curfn.node.kids
    names = [name]
    if self.globread(name):
        for tw in self.twins(name):
            if self.globread(tw):
                names.append(tw)
    found: list[Node] = []
    for nm in names:
        first: list[Node] = []
        self.live = True  # (a fill in a loop over the empty tuple only if no code that runs fills it)
        self.dead = False
        self.fills(body, nm, first)
        self.live = False
        if len(first) == 0 and self.dead:
            self.fills(body, nm, first)
        if len(first) > 0 and (len(found) == 0 or first[0].line < found[0].line):
            found = first
    if len(found) == 0:
        return ""
    t = self.qtype(name)
    e = found[-1]
    if self.empty_of(e) != "":
        return ""  # (d[k] = [] shows nothing of what d holds)
    for x in found:
        if not self.typed_now(x) or (ahead and self.calls_open(x, {})):
            return ""
    if found[0].kind == "omit" and not is_list(t) and not is_set(t):
        return ""  # (d += ... or d.extend(...) on a dict: an error where it is compiled)
    it = self.dry(e)
    if found[0].kind == "omit" and is_list(t):
        if not is_list(it):
            return ""
        r = it
    elif found[0].kind == "omit" and is_set(t):
        r = self.ctype("set", [self.iter_elem(it)]) if self.iter_elem(it) != "" else ""  # (s.update(xs), s |= t)
        if r == "":
            return ""
    elif is_set(t):
        r = self.ctype("set", [it])
    elif is_list(t):
        r = self.ctype("list", [it])
    else:
        r = self.ctype("dict", [self.dry(found[0]), it])
    if "?" in r or "None" in targs(r):
        return ""
    here = self.line
    self.line = e.line  # (a key type a dict cannot have is the fill's error)
    self.refine(name, r)
    self.line = here
    return r

def gen_unfilled(self, name: str) -> bool:
    # is name a local empty list or dict without a type, which no use in its function's source
    # types here (lookahead) and nothing in the function fills or rebinds, so that it is empty
    # wherever it is read? Fills in code the argument types leave out (a loop over the empty
    # tuple, a branch a static test removes) do not count; self.dead tells whether there are any
    if "?" not in self.ltype.get(name, "") or name in self.compvars or self.curfn.node.kind != "def" or self.lookahead(name) != "":
        return False
    found: list[Node] = []
    self.dead = False
    self.live = True
    self.fills(self.curfn.node.kids[2].kids, name, found)
    self.live = False
    return len(found) == 0 and self.only_empties(self.curfn.node.kids[2].kids, name)

def gen_retval(self, e: Node, want: str) -> Val:
    # the value of return e, where the function returns want ("" while a template's function
    # infers it). A template's function returns an empty container that nothing fills (see
    # unfilled) as it is, and each call gives it the type its context expects (typed_empty),
    # unless a use further on (in a loop, a call or another return) gives it a type (adopt)
    q = self.qret.get(self.curfn.ll, "")
    known = e.kind == "name" and e.s in q.split() and "?" in self.ltype.get(e.s, "")  # (and still so)
    if e.kind == "name" and (want == "" or "?" in want) and (known or self.unfilled(e.s)):
        self.qret[self.curfn.ll] = q if known else q + " " + e.s
        self.allowq = True
        v = self.read(e)
        self.allowq = False
        return v
    return self.expr(e, want)

def gen_adopt(self, t: str) -> None:
    # the template's function being compiled, which returned an empty container without a
    # type (see retval), returns t: the containers it returned have that type too
    if self.curfn.ll in self.qused:
        self.err(f"cannot infer what {short(self.curfn.name)}() returns: it calls itself before a use shows what the {tname(t)} it returns holds; annotate its return type")
    self.ret = t
    self.curfn.ret = t
    for nm in self.qret[self.curfn.ll].split():
        if "?" in self.ltype[nm]:
            self.refine(nm, t)

def gen_typed_empty(self, v: Val, want: str, f: FnInfo) -> Val:
    # the empty list or dict a template's function f returns (see retval): the type the call's
    # context expects, else list[int] or dict[int, int] (as sum() of an empty list is the int 0),
    # which a type error further on in this function then explains (guessed). A new dict is made
    # by each call, so it gets the key kind of its type here (a dict's second word)
    t = want if same_kind(want, v.t) and "?" not in want else "list[int]" if is_list(v.t) else "set[int]" if is_set(v.t) else "dict[int,int]"
    if t != want:
        self.guessed[self.curfn.ll] = f"{short(f.name)}() at line {self.line} returns an empty {tname(t)} taken as {typestr(t)}: give it a type first, as in v: {'list[T]' if is_list(t) else 'set[T]' if is_set(t) else 'dict[K, V]'} = {short(f.name)}()"
    if is_dict(t) or is_set(t):
        self.emit(f"store i64 {self.key_kind(targs(t)[0] if is_dict(t) else selem(t))}, ptr {self.ins(f'getelementptr i64, ptr {v.v}, i64 1')}")
    return Val(v.v, t)

def gen_fills(self, body: list[Node], name: str, found: list[Node]) -> bool:
    # the first statement in body (searched in order, into blocks) that fills variable name:
    # found gets [key or omit, item]. True if body ends in a return, raise, break or continue
    # (also in the branch of an if that the types decide), after which nothing in it runs
    for st in body:
        if len(found) > 0:
            return False
        if st.kind == "def" or st.kind == "class" or st.kind == "subclass":
            continue
        k = st.kind
        s = self.static_whole(st.kids[0], st.line) if k == "if" or k == "while" else -1
        if k == "return" or k == "raise" or k == "break" or k == "continue":
            self.fill_calls(st, name, found)
            return True
        if (k == "assign" or k == "augassign") and st.kids[0].kind == "index" and st.kids[0].kids[0].kind == "name" and st.kids[0].kids[0].s == name and k == "assign":
            found.append(st.kids[0].kids[1])
            found.append(st.kids[-1])
        elif k == "assign" and len(st.kids) == 2 and st.kids[0].kind == "index" and empty_default(st.kids[0].kids[0], name, "dict"):
            # name.setdefault(k, {})[k2] = v: the item is {k2: v} (see default_want)
            found.append(st.kids[0].kids[0].kids[1])
            found.append(mk("dict", "", st.line, [st.kids[0].kids[1], st.kids[1]]))
        elif k == "augassign" and st.kids[0].kind == "name" and st.kids[0].s == name and (st.s == "+" or (st.s == "|" and is_set(self.qtype(name)))):
            found.append(mk("omit", "", st.line, []))  # (xs += ys, s |= t)
            found.append(st.kids[1])
        elif k == "if" and s >= 0:
            # a test that the types decide there: only the branch that runs
            self.dead = self.dead or shows_items(st.kids[2 if s == 1 else 1], name)
            if self.fills(st.kids[1 if s == 1 else 2].kids, name, found):
                return True
        elif (k == "if" or k == "while") and self.unsure and shows_items(st, name):
            # a test that types not known yet may decide: which branch runs is not known
            found.append(mk("lambda", "", st.line, []))  # (which no look-ahead compiles)
        elif (k == "for" and self.live and st.kids[1].kind == "name" and self.qtype(st.kids[1].s) == "tuple[]") or (k == "while" and s == 0):
            # a loop over the empty tuple (*args without extra arguments), or whose test the
            # types make false: only its else block runs
            self.dead = self.dead or shows_items(st.kids[2 if k == "for" else 1], name)
            if st.kids[-1].s == "else":
                self.fills(st.kids[-1].kids, name, found)
        else:
            self.fill_calls(st, name, found)
            for kid in st.kids:
                if kid.kind == "block":
                    self.fills(kid.kids, name, found)
                elif kid.kind == "except":
                    self.fills(kid.kids[1].kids, name, found)
    return False

def gen_fill_calls(self, n: Node, name: str, found: list[Node]) -> None:
    # name.append(v), insert(i, v), extend(xs), setdefault(k, v), get(k, v) anywhere in n
    if len(found) > 0 or n.kind == "block" or n.kind == "listcomp":
        return  # (a comprehension's names are its own)
    if n.kind == "call" and n.kids[0].kind == "attr" and len(n.kids) == (3 if n.kids[0].s == "insert" else 2) and (n.kids[0].s == "append" or n.kids[0].s == "insert") and n.kids[-1].kind != "kw" and empty_default(n.kids[0].kids[0], name, "list"):
        # name.setdefault(k, []).append(v): the item is [v] (see default_want)
        found.append(n.kids[0].kids[0].kids[1])
        found.append(mk("list", "", n.line, [n.kids[-1]]))
        return
    if n.kind == "call" and n.kids[0].kind == "attr" and len(n.kids) == 2 and n.kids[0].s == "add" and n.kids[-1].kind != "kw" and empty_default(n.kids[0].kids[0], name, "set"):
        # name.setdefault(k, set()).add(v): the item is {v}
        found.append(n.kids[0].kids[0].kids[1])
        found.append(mk("set", "", n.line, [n.kids[-1]]))
        return
    if n.kind == "call" and n.kids[0].kind == "attr" and n.kids[0].kids[0].kind == "name" and n.kids[0].kids[0].s == name:
        m = n.kids[0].s
        a = n.kids[1:]
        if (m == "append" and len(a) == 1) or (m == "insert" and len(a) == 2) or (m == "add" and len(a) == 1):
            found.append(mk("int", "0", n.line, []))
            found.append(a[-1])
        elif (m == "extend" and len(a) == 1) or (m == "update" and is_set(self.qtype(name)) and len(a) > 0):
            found.append(mk("omit", "", n.line, []))
            found.append(a[0])  # (s.update(xs, ys): the first one's elements)
        elif (m == "setdefault" or m == "get") and len(a) == 2:
            found.append(a[0])
            found.append(a[1])
        if len(found) > 0 and found[-1].kind == "kw":
            found.pop()
            found.pop()
        return
    s = self.static_whole(n.kids[0], n.line) if n.kind == "ifexp" or n.kind == "boolop" else -1
    if s < 0 and (n.kind == "ifexp" or n.kind == "boolop") and self.unsure and shows_items(n, name):
        found.append(mk("lambda", "", n.line, []))  # (as for an if: see fills)
    for i in range(len(n.kids)):
        # (not the operand of a conditional expression, and or or that the types leave out)
        if s < 0 or not ((n.kind == "ifexp" and i == (2 if s == 1 else 1)) or (n.kind == "boolop" and i == 1 and (s == 1) == (n.s == "or"))):
            self.fill_calls(n.kids[i], name, found)

def gen_typed_now(self, e: Node, own: str = "") -> bool:
    # can e be compiled here: every variable it reads has its type already (but own, the
    # variables of the comprehensions around e, space-separated)
    if e.kind == "name":
        if e.s in self.funcs or e.s in self.classes or e.s in self.aliases or e.s in own.split():
            return True
        t = self.rtype(e.s)
        if t != "":
            return "?" not in t and t != NONEVAR
        return not (e.s in self.assigned or e.s in self.mvars or e.s in self.nonevars)
    if e.kind == "listcomp":
        # [x for t in it if c]: x and c read the variables in t too, which the items of it type
        names: list[str] = []
        names_in(e.kids[1], names)
        inner = own + " " + " ".join(names)
        for i in range(len(e.kids)):
            if i != 1 and not self.typed_now(e.kids[i], own if i == 2 else inner):
                return False
        return True
    if e.kind == "lambda" or e.kind in UNSUPPORTED:
        return False
    for k in e.kids:
        if not self.typed_now(k, own):
            return False
    return True

def gen_dry(self, e: Node) -> str:
    # the type of e, compiled into blocks that are dropped (an error after it is still the read's)
    blk = self.blk
    blocks = self.fn.blocks
    loops = self.fn.loops
    cur = self.cur
    term = self.term
    line = self.line
    self.blk = Blk("")
    self.fn.blocks = []
    self.fn.loops = []
    self.drying += 1
    t = self.expr(e, "").t
    self.drying -= 1
    self.blk = blk
    self.fn.blocks = blocks
    self.fn.loops = loops
    self.cur = cur
    self.term = term
    self.line = line
    return t

def gen_fill(self, n: Node, m: str, args: list[Node], want: str = "") -> Val:
    # name.append(v), insert(i, v) or extend(xs) on a list, and name.setdefault(k, v) or
    # name.get(k, default) on a dict (where want, the type expected of the call, types an
    # empty default), whose variable has no type yet: the items decide it
    name = n.s
    self.allowq = True
    o = self.read(n)
    self.allowq = False
    for a in args:
        if a.kind == "kw" and m != "update":  # (which takes keywords: below, d's type is asked for)
            self.err(f"keyword arguments to {'list' if is_list(o.t) else 'dict'}.{m}() are not supported; pass them by position")
    if is_list(o.t) and (m == "append" or m == "extend" or m == "insert") and len(args) == (2 if m == "insert" else 1):
        if empty_display(args[-1]):
            self.no_type(name)  # (xs.append([]) shows nothing of what xs holds)
        i = self.ival(args[0]) if m == "insert" else Val("0", "int")
        if m == "extend" and self.is_mapcall(args[0]):
            args = [self.mapgen(args[0])]
        if m == "extend" and args[0].kind == "listcomp" and args[0].s == "gen":
            # (item by item, as bmethod's)
            self.refine(name, self.listcomp(args[0], "", "", o.v).t)
            return Val("null", "None")
        v = self.as_list(self.consume(args[-1], ""), "extend") if m == "extend" else self.expr(args[-1], "")
        if m == "extend" and not is_list(v.t):
            self.err(f"cannot extend a list with {v.t}")
        self.refine(name, v.t if m == "extend" else self.ctype("list", [v.t]))
        if m == "append":
            self.rt("pys_list_append", "void", [f"ptr {o.v}", "i64 " + self.to_slot(v)])
        elif m == "insert":
            self.rt("pys_list_insert", "void", [f"ptr {o.v}", f"i64 {i.v}", "i64 " + self.to_slot(v)])
        else:
            self.rt("pys_list_extend", "void", [f"ptr {o.v}", f"ptr {v.v}"])
        return Val("null", "None")
    if is_set(o.t) and m == "add" and len(args) == 1 and args[0].kind != "kw":
        if self.empty_of(args[0]) != "":
            self.no_type(name)  # (s.add(()) is an error where it is compiled; this one shows nothing)
        v = self.expr(args[0], "")
        self.refine(name, self.ctype("set", [v.t]))
        t = self.qtype(name)
        self.rt("pys_set_add", "void", [f"ptr {o.v}", "i64 " + self.to_slot(self.store_elem(v, selem(t)))])
        return Val("null", "None")
    if is_set(o.t) and m == "update" and len(args) == 1 and args[0].kind == "listcomp" and args[0].s == "gen":
        # (item by item, as smethod's)
        self.refine(name, self.listcomp(args[0], "", "", o.v, None, "set").t)
        return Val("null", "None")
    if is_set(o.t) and m == "update" and len(args) == 1 and args[0].kind != "kw":
        v = self.siter(args[0], "", "set.update()")
        self.refine(name, self.ctype("set", [self.iter_elem(v.t)]))
        self.supdate(o.v, v)
        return Val("null", "None")
    if is_set(o.t) and m == "update" and len(args) > 1 and args[0].kind != "kw":
        # s.update(xs, ys, ...): the first one's elements decide the type, then smethod runs it
        # for a set of that type (each argument evaluated before any is added, as CPython does:
        # the first one's value is taken now, and its items at its turn)
        a = self.mapgen(args[0]) if self.is_mapcall(args[0]) else args[0]
        if (a.kind != "listcomp" or a.s != "gen") and not self.iterator_call(a):
            a = self.vnode(self.consume(a, ""))
        item = mk("name", "__item", a.line, [])
        g = a if a.kind == "listcomp" else mk("listcomp", "gen", a.line, [item, item, a])
        et = elem(self.dry(mk("listcomp", "", a.line, g.kids)))  # (the type of a list of its items)
        et = self.none_items(et) if is_tuple(et) else et
        if elem_problem(et) != "":
            self.err(elem_problem(et))
        self.refine(name, self.ctype("set", [et]))
        return self.smethod(Val(o.v, self.qtype(name)), m, [a] + args[1:])
    if is_dict(o.t) and (m == "setdefault" or m == "get") and len(args) == 2:
        if self.empty_of(args[1]) != "" and (want == "" or "?" in want):
            self.no_type(name)
        k = self.expr(args[0], "")
        v = self.expr(args[1], want if "?" not in want else "")
        self.refine(name, self.ctype("dict", [k.t, v.t]))
        return self.from_slot(self.rt(f"pys_dict_{m}", "i64", [f"ptr {o.v}", "i64 " + self.to_slot(k), "i64 " + self.to_slot(v)]), v.t)
    # any other method: the type a later use shows (or an error), then the method as usual
    return self.method(self.load_name(name), m, args)

def gen_default_want(self, r: Node, m: str, args: list[Node], vt: str) -> str:
    # d.setdefault(k, []).append(v) (or insert), or d.setdefault(k, {})[k2] = v (m "[]", args
    # [k2], vt the type of v), where d has no type yet: the type of the value, which then
    # types the empty default (see fill); else ""
    if r.kind != "call" or len(r.kids) != 3 or r.kids[0].kind != "attr" or r.kids[0].s != "setdefault" or r.kids[0].kids[0].kind != "name":
        return ""
    d = r.kids[2]
    if "?" not in self.rtype(r.kids[0].kids[0].s) or self.empty_of(d) == "":
        return ""
    if self.empty_of(d) == "set":
        return self.ctype("set", [self.dry(args[0])]) if m == "add" and len(args) == 1 and args[0].kind != "kw" else ""
    if m == "[]" and d.kind == "dict":
        return self.ctype("dict", [self.dry(args[0]), vt])
    if d.kind == "list" and ((m == "append" and len(args) == 1) or (m == "insert" and len(args) == 2)) and args[-1].kind != "kw":
        return self.ctype("list", [self.dry(args[-1])])
    return ""

def gen_new_global(self, name: str, t: str) -> None:
    self.gtypes[name] = t
    self.global_var(f"@g.{name}", lt(t))
    if name in self.gflag:
        self.global_var(f"@g.{name}.def", "i1")

def gen_declare(self, name: str, t: str) -> None:
    if self.is_global(name):
        if name not in self.gtypes:
            self.new_global(name, t)
        old = self.gtypes[name]
    elif name in self.ltype:
        old = self.ltype[name]
    else:
        self.alloca(t, name)
        old = t
    if old != t:
        self.err(f"'{name}' was declared as {old}, not {t}")

def gen_store_name(self, name: str, v: Val) -> None:
    if name in self.noneglobals and name not in self.ltype:
        if v.t != "None":
            self.err(f"'{name}' is None in its module's code: giving it a {v.t} elsewhere (a function or another module) is not supported")
        return
    if self.is_global(name):
        if name in self.falseflags and v.v != "false":
            # (through the module, m.TYPE_CHECKING = x, also after its own import of itself:
            # false_flag() leaves no other store)
            self.err(f"assigning '{owner(name)}.TYPE_CHECKING' anything but the literal False is not supported: its module assigns it False once, so its tests of it are decided at compile time")
        if name not in self.gtypes:
            t0 = self.none_type(name) if v.t == "None" and self.modlevel else ""
            if v.t == "None" and t0 == "":
                # (module code's other values for it are typed here, as far as they can be)
                self.err(f"cannot infer the type of '{name}' from None; annotate it ({name}: T | None = None)")
            if v.t == "":
                self.err(f"cannot infer the type of '{name}'; add a type annotation")
            self.declare(name, t0 if t0 != "" else v.t)
        t = self.gtypes[name]
        if "?" in t and same_kind(t, v.t) and "?" not in v.t:
            self.refine(name, v.t)
            t = v.t
        self.emit(f"store {lt(t)} {self.coerce(v, t, self.assigned_to(v, t, name)).v}, ptr @g.{name}")
        if name in self.gflag:
            self.emit(f"store i1 true, ptr @g.{name}.def")
    else:
        if name in self.nonevars and name not in self.ltype and name not in self.compvars:
            # a parameter whose argument is None: assigning None keeps it so; any other value
            # gives it that type from here on, which only code outside branches and loops can do
            if v.t == "None":
                return
            if self.branch > 0:
                self.err(f"'{name}' is None here, and giving it a {v.t if '?' not in v.t else v.t[: v.t.find('[')]} inside an if branch or a loop is not supported")
            self.nonevars[name] = self.line
        if name not in self.ltype and v.t == "None":
            # first None: T | None, typed by the first store of another value, or by a read
            # that needs the type before it (see none_read)
            self.alloca(NONEVAR, name)
        elif name not in self.ltype:
            self.alloca(v.t, name)
        t = self.ltype[name]
        if t == NONEVAR and v.t != "None":
            if self.optional(v.t) == "":
                self.err(f"'{name}' is assigned None and {typestr(v.t)}, and None/Optional is only supported for {OPTTYPES}")
            t = self.optional(v.t)
            self.ltype[name] = t
        if "?" in t and same_kind(t, v.t) and "?" not in v.t:
            self.refine(name, v.t)
            t = v.t
        self.emit(f"store {lt(t)} {self.coerce(v, t, self.assigned_to(v, t, name)).v}, ptr {self.lreg[name]}")
        if name in self.lflag and name not in self.compvars:
            self.emit(f"store i1 true, ptr {self.lflag[name]}")
        if is_opt(t) and (is_opt(v.t) or v.t == "None"):
            self.narrowed.pop(name, False)
        elif is_opt(t):
            self.narrowed[name] = True  # (it holds a value)

def gen_assigned_to(self, v: Val, t: str, name: str) -> str:
    # what names value v assigned to variable name of type t, for coerce's error
    return f"the value assigned to '{short(name)}' ({typestr(t)})" if is_opt(v.t) else ""

def gen_target_type(self, n: Node, base: bool = False) -> str:
    # expected type of an assignment target (types empty [] / {} literals): a name, or a
    # chain of attributes and subscripts on one (g.groups["a"], d["x"]["y"]), whose base
    # name is only read, so in a function it can be a module-level variable
    if n.kind == "name":
        if base and n.s not in self.ltype and (n.s not in self.assigned or n.s in self.gdecl):
            return self.gtypes.get(n.s, "")
        return self.ltype.get(n.s, self.gtypes.get(n.s, "") if self.is_global(n.s) else "")
    if n.kind == "slice":
        self.err("assignment to a slice is not supported")
    if n.kind == "attr" or n.kind == "index":
        t = self.target_type(n.kids[0], True)
        if n.kind == "attr" and t in self.classes:
            return self.classes[t].ftypes.get(n.s, "")
        if n.kind == "index" and is_list(t):
            return elem(t)
        if n.kind == "index" and is_dict(t):
            return targs(t)[1]
        if n.kind == "index" and t in self.classes and "__setitem__" in self.classes[t].methods and len(self.classes[t].methods["__setitem__"].ptypes) > 2:
            return self.classes[t].methods["__setitem__"].ptypes[2]
    return ""

def gen_assign(self, t: Node, v: Val) -> None:
    k = t.kind
    if k == "badattr":
        self.err(t.s)
    if k in UNSUPPORTED:
        self.err(UNSUPPORTED[k])
    if k == "tuple" and len([x for x in t.kids if x.kind == "starred"]) > 0:
        self.err(UNSUPPORTED["starred"])  # (before the number of targets is checked)
    if k == "name":
        self.store_name(t.s, v)
    elif k == "attr" and self.dotted(t) != "":
        self.err(f"assigning to {self.dotted(t)} is not supported; change its value in place")
    elif k == "attr" and t.kids[0].kind == "name" and t.kids[0].s in self.classes and t.kids[0].s not in self.ltype:
        self.class_store(self.cvar(t.kids[0], t.s), t.s, v)
    elif k == "attr":
        o = self.expr(t.kids[0], "")
        p = self.field(o, t.s, True)
        self.frozen(o.t, t.s)
        self.setfield(o, p, t.s, v)
    elif k == "index" and t.kids[0].kind == "name" and "?" in self.rtype(t.kids[0].s):
        # d[k] = v or xs[i] = v on an empty dict or list without a type: k and v decide it
        self.allowq = True
        o = self.read(t.kids[0])
        self.allowq = False
        if is_dict(o.t):
            kval = self.expr(t.kids[1], "")
            self.refine(t.kids[0].s, self.ctype("dict", [kval.t, v.t]))
            self.rt("pys_dict_set", "void", [f"ptr {o.v}", "i64 " + self.to_slot(kval), "i64 " + self.to_slot(v)])
        else:
            ix = self.ival(t.kids[1])
            self.refine(t.kids[0].s, self.ctype("list", [v.t]))
            self.rt("pys_list_set", "void", [f"ptr {o.v}", f"i64 {ix.v}", "i64 " + self.to_slot(v)])
    elif k == "index":
        o = self.expr(t.kids[0], self.default_want(t.kids[0], "[]", [t.kids[1]], v.t))
        nosub = "TypeError: 'NoneType' object does not support item assignment"
        if is_list(unopt(o.t)):
            ix = self.ival(t.kids[1])
            o = self.unwrap(o, nosub)
            s = self.to_slot(self.coerce(v, elem(o.t)))
            self.rt("pys_list_set", "void", [f"ptr {o.v}", f"i64 {ix.v}", f"i64 {s}"])
        elif is_dict(unopt(o.t)):
            kv = targs(unopt(o.t))
            key = self.to_slot(self.store_key(self.expr(t.kids[1], kv[0]), kv[0]))
            o = self.unwrap(o, nosub)
            self.rt("pys_dict_set", "void", [f"ptr {o.v}", f"i64 {key}", "i64 " + self.to_slot(self.coerce(v, kv[1]))])
        elif o.t in self.classes:
            # o[k] = v: o.__setitem__(k, v), once v, o and k are evaluated
            ik = self.expr(t.kids[1], self.argtype(o.t, "__setitem__", 1, f"'{tname(o.t)}' object does not support item assignment"))
            self.notnone(o, nosub)
            self.protocol(o, "__setitem__", [ik, v])
        elif is_kw(o.t):
            self.err("changing **kwargs is not supported: copy it to a dict first (d = dict(kwargs))")
        else:
            self.err(f"'{o.t}' does not support item assignment")
    elif k == "tuple" and is_opt(v.t):
        self.assign(t, self.unwrap(v, "TypeError: cannot unpack non-iterable NoneType object"))
    elif k == "tuple" and (is_list(v.t) or v.t == "str"):
        # a, b = xs: the length is checked when it runs, as CPython does. CPython takes every
        # item before it stores the first, so where a store may change the list (xs[1], xs[0] =
        # xs, or a __setitem__ that empties it), the items are all read first
        self.rt("pys_unpack_check", "void", [f"i64 {self.ins(f'load i64, ptr {v.v}')}", f"i64 {len(t.kids)}"])
        first = v.t != "str" and not name_targets(t)
        items: list[Val] = []
        for i in range(len(t.kids)):
            if v.t == "str":
                self.assign(t.kids[i], Val(self.rt("pys_str_get", "ptr", [f"ptr {v.v}", f"i64 {i}"]), "str"))
            elif first:
                items.append(self.from_slot(self.rt("pys_list_get", "i64", [f"ptr {v.v}", f"i64 {i}"]), elem(v.t)))
            else:
                self.assign(t.kids[i], self.from_slot(self.rt("pys_list_get", "i64", [f"ptr {v.v}", f"i64 {i}"]), elem(v.t)))
        for i in range(len(items)):
            self.assign(t.kids[i], items[i])
    elif k == "tuple" and v.t in self.nts:
        # a, b = p: a NamedTuple's fields in order
        fs = self.classes[v.t].fields
        if len(fs) != len(t.kids):
            self.err(f"cannot unpack {short(v.t)} ({len(fs)} fields) into {len(t.kids)} targets")
        self.notnone(v, "TypeError: cannot unpack non-iterable NoneType object")
        for i in range(len(fs)):
            self.assign(t.kids[i], self.getfield(v, self.field(v, fs[i]), fs[i]))
    elif k == "tuple" and v.t in self.classes:
        # a, b = o: what o's __iter__ steps through
        self.assign(t, self.obj_iter(v, "TypeError: cannot unpack non-iterable NoneType object", f"cannot unpack non-iterable {tname(v.t)} object"))
    elif k == "tuple":
        if not is_tuple(v.t) or len(targs(v.t)) != len(t.kids):
            self.err(f"cannot unpack {v.t} into {len(t.kids)} targets")
        for i in range(len(t.kids)):
            self.assign(t.kids[i], self.tget(v, i))
    else:
        self.err("cannot assign to this expression")

# ---- functions and the module
