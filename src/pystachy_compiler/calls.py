"""Calls component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.analysis import local_names
from src.pystachy_compiler.diagnostics import shown, where
from src.pystachy_compiler.ir import FnInfo, Ins, Val
from src.pystachy_compiler.names import short
from src.pystachy_compiler.specs import EXCEPTIONS, HASATTR, MODATTRS, PYBUILTINS
from src.pystachy_compiler.syntax import Node, mk
from src.pystachy_compiler.utils import (
    codec,
    fbits,
    has_method,
    hpush,
    is_callable,
    is_const,
    is_dict,
    is_fn,
    is_fset,
    is_kw,
    is_list,
    is_opt,
    is_set,
    is_tuple,
    kw_names,
    kw_types,
    lt,
    nonetest,
    pure_arg,
    takes_self,
    targs,
    tname,
    typestr,
    unopt,
)


def gen_call(self, n: Node, want: str) -> Val:
    f = n.kids[0]
    args = n.kids[1:]
    if f.kind == "badattr":
        self.err(f.s)
    if len([a for a in args if a.kind == "starred" or a.kind == "dstar"]) > 0:
        return self.star_call(n, want)
    if f.kind == "name":
        self.modchk(f)
    if f.kind == "name" and f.s not in self.ltype:
        self.read_ahead(f.s)
        if (f.chk or self.foreign(f.s)) and f.s in self.gflag:
            # a call that may run before the def or class statement
            bad = self.ins(f"xor i1 {self.ins(f'load i1, ptr @g.{f.s}.def')}, true")
            self.guard(bad, self.unbound(f.s))
        if f.s in self.funcs:
            return self.call_fn(self.funcs[f.s], [], args, want)
        if f.s in self.aliases and f.s not in self.gtypes:
            return self.builtin(self.aliases[f.s], args, want)
        if f.s in self.classes:
            if self.classes[f.s].exc != "":
                return self.exc_object(f.s, args)
            if self.classes[f.s].bad != "":
                self.err(self.classes[f.s].bad)
            if f.s in self.tmpl:
                # a class template: the types of the arguments pick the specialization, whose
                # object call_fn makes once it has them (in made[0])
                made = [Val("", f.s)]
                self.call_fn(self.classes[f.s].methods["__init__"], made, args)
                return made[0]
            o = self.new_obj(f.s)
            self.call_fn(self.classes[f.s].methods["__init__"], [o], args, direct=True)
            return o
        if f.s in self.mvars:
            self.not_callable(f.s, self.gtype(f.s))
            return self.obj_call(self.expr(f, ""), args, want)
        if f.s in self.unsupported:
            self.err(self.unsupported[f.s])
        if f.s in EXCEPTIONS and EXCEPTIONS[f.s] != "-":
            # an exception made, not raised (raise e raises it)
            vals = self.exc_vals(self.exc_args(n), f.s)
            if f.s == "SystemExit":
                return self.exit_value(vals)
            return self.exc_value("OSError" if f.s == "IOError" or f.s == "EnvironmentError" else f.s, vals)
        return self.builtin(f.s, args, want)
    if f.kind == "attr":
        c = self.curfn.cls
        if c != "" and self.classes[c].exc != "" and f.kids[0].kind == "name" and self.derives(c, f.kids[0].s) and f.kids[0].s != c and len(args) > 0 and args[0].kind == "name" and len(self.curfn.params) > 0 and args[0].s == self.curfn.params[0] and (f.kids[0].s in self.classes or not self.bound(f.kids[0].s)):
            # Base.m(self, args) in a method of an exception class: super().m(args) for its base
            self.class_ahead(f.kids[0].s)
            if f.kids[0].s != self.classes[c].base and not (self.classes[c].base == "OSError" and (f.kids[0].s == "IOError" or f.kids[0].s == "EnvironmentError")):
                self.err(f"{f.kids[0].s}.{f.s}(self, ...) in a method of {short(c)} is supported only for its base, {short(self.classes[c].base)} (as super().{f.s}(...))")
            return self.super_call(mk("call", "", f.line, [mk("name", "super", f.line, [])]), f.s, args[1:], True)
        path = self.dotted(f)
        if path != "" and path[: path.rfind(".")] not in MODATTRS:
            self.modchk(f)
            return self.builtin(path, args, want)
        if f.kids[0].kind == "call" and f.kids[0].kids[0].kind == "name" and f.kids[0].kids[0].s == "super" and not self.bound("super"):
            return self.super_call(f.kids[0], f.s, args)
        if f.kids[0].kind == "name" and f.kids[0].s == "dict" and f.s == "fromkeys" and not self.bound("dict"):
            return self.fromkeys(args, want)
        if f.kids[0].kind == "name" and "?" in self.rtype(f.kids[0].s):
            return self.fill(f.kids[0], f.s, args, want)
        if f.kids[0].kind == "name" and f.kids[0].s in self.nts and f.kids[0].s not in self.ltype and f.s == "_make":
            self.err(f"{short(f.kids[0].s)}._make() is not supported: call {short(f.kids[0].s)}(...) with the fields")
        if f.kids[0].kind == "name" and f.kids[0].s in self.classes and f.kids[0].s not in self.ltype:
            return self.class_call(f.kids[0], f.s, args, want)
        o = self.expr(f.kids[0], self.default_want(f.kids[0], f.s, args, ""))
        r = self.method(o, f.s, args)
        if f.s != "close":
            self.close_temp(f.kids[0], o)
        return r
    if f.kind == "name":
        self.not_callable(f.s, self.ltype[f.s])
    return self.obj_call(self.expr(f, ""), args, want)

def gen_star_call(self, n: Node, want: str) -> Val:
    # f(a, *t, k=v): the items a star unpacks are positional arguments. CPython evaluates the
    # function (o.m binds o first), then the positional arguments in order, unpacking each star,
    # then the keyword ones; here each is evaluated so (but a constant or a name, which nothing
    # can change meanwhile, keeps the type its parameter wants), a tuple's items become
    # arguments, and the call is compiled with them (a list's items, which only run time knows,
    # only print() takes: a sole star's once the keywords are evaluated, as CPython unpacks it)
    f = n.kids[0]
    args = n.kids[1:]
    if f.kind == "attr" and not self.static_callee(f) and f.kids[0].kind != "val":
        f = mk("attr", f.s, f.line, [self.vnode(self.expr(f.kids[0], ""))])
    elif f.kind != "attr" and f.kind != "val" and not self.static_callee(f):
        f = self.vnode(self.expr(f, ""))
    printing = f.kind == "name" and f.s == "print" and not self.bound("print")
    sole = len([a for a in args if a.kind != "kw" and a.kind != "dstar"]) == 1
    who = self.star_who(f)
    pos: list[Node] = []
    kws: list[Node] = []
    for a in args:
        if a.kind == "kw" or a.kind == "dstar":
            continue
        if a.kind == "starred" and (a.kids[0].kind == "list" or a.kids[0].kind == "tuple") and len([x for x in a.kids[0].kids if x.kind == "starred"]) == 0:
            for x in a.kids[0].kids:
                pos.append(x if pure_arg(x) else self.vnode(self.expr(x, "")))  # (*[a, b] of a display: its items)
        elif a.kind == "starred":
            v = self.expr(a.kids[0], "")
            self.line = a.line
            v = self.unwrap(v, f"TypeError: {who + ' argument' if who != '' else 'Value'} after * must be an iterable, not NoneType")
            if is_tuple(v.t):
                for i in range(len(targs(v.t))):
                    pos.append(self.vnode(self.tget(v, i)))
            elif printing and (is_list(v.t) or v.t == "str" or is_dict(v.t)):
                # print(*xs): its items printed as arguments are, joined by sep (a sole star's
                # items as they are once the keywords are evaluated, others' as they are now)
                xs = v if sole else self.as_list(v, "print") if not is_list(v.t) else self.expr(mk("listcomp", "", a.line, [mk("name", "__pys_item", a.line, []), mk("name", "__pys_item", a.line, []), self.vnode(v)]), "")
                item = mk("name", "__pys_item", a.line, [])
                pos.append(mk("starred", "", a.line, [mk("listcomp", "", a.line, [mk("call", "", a.line, [mk("name", "str", a.line, []), item]), item, self.vnode(xs)])]))
            else:
                self.err(f"unpacking a {typestr(v.t)} into the arguments of {who if who != '' else 'a function'} is not supported (a tuple's items are)")
        else:
            pos.append(a if pure_arg(a) else self.vnode(self.expr(a, "")))
    for a in args:
        if a.kind == "kw":
            kws.append(a if pure_arg(a.kids[0]) else mk("kw", a.s, a.line, [self.vnode(self.expr(a.kids[0], ""))]))
        elif a.kind == "dstar" and a.kids[0].kind == "dict" and len([i for i in range(0, len(a.kids[0].kids), 2) if a.kids[0].kids[i].kind != "str"]) == 0:
            d = a.kids[0]
            for i in range(0, len(d.kids), 2):
                kws.append(mk("kw", d.kids[i].s, a.line, [self.vnode(self.expr(d.kids[i + 1], ""))]))  # (**{"k": v}: its items)
        elif a.kind == "dstar":
            v = self.expr(a.kids[0], "")
            if not is_kw(v.t):
                self.err(f"** of a {typestr(v.t)} is not supported: of a function's **kwargs, or a dict display with str keys, it is")
            names = kw_names(v.t)
            for i in range(len(names)):
                kws.append(mk("kw", names[i], a.line, [self.vnode(self.tget(self.kw_tuple(v), i))]))
    out = pos + kws
    if printing and len([a for a in out if a.kind == "starred"]) > 0:
        return self.print_star(n, out)
    return self.call(mk("call", n.s, n.line, [f] + out), want)

def gen_static_callee(self, f: Node) -> bool:
    # does evaluating callee f (or the object of o.m) read nothing a call's arguments may change:
    # a def, class, builtin or module's function, super(), or a variable's empty container that
    # the call fills (whose name types it)
    if f.kind == "attr":
        o = f.kids[0]
        if self.dotted(f) != "" or (o.kind == "call" and o.kids[0].kind == "name" and o.kids[0].s == "super" and not self.bound("super")):
            return True
        if o.kind != "name":
            return False
        return (o.s in self.classes and o.s not in self.ltype) or (o.s in PYBUILTINS and not self.bound(o.s)) or "?" in self.rtype(o.s)
    if f.kind != "name":
        return False
    return ((f.s in self.funcs or f.s in self.classes) and f.s not in self.ltype) or not self.bound(f.s) or (f.s in self.aliases and f.s not in self.gtypes)

def gen_star_who(self, f: Node) -> str:
    # the function f(...) calls, as CPython's messages name it (module.qualname(), a builtin's
    # name()), or "" where it is known only at run time
    t = ""
    if f.kind == "name" and f.s not in self.ltype and (f.s in self.funcs or f.s in self.classes):
        t = f"fn[f:{f.s}]" if f.s in self.funcs else ""
        if f.s in self.classes:
            m = self.classes[f.s].mod
            return f"{m if m != '' else '__main__'}.{short(f.s)}()"
    elif f.kind == "name" and not self.bound(f.s):
        return f"{f.s}()"
    elif f.kind == "val":
        t = self.vnodes[int(f.s)].t
    elif f.kind == "attr" and f.kids[0].kind == "val" and self.vnodes[int(f.kids[0].s)].t in self.classes:
        c = self.vnodes[int(f.kids[0].s)].t
        m = self.classes[c].mod
        return f"{m if m != '' else '__main__'}.{short(c)}.{f.s}()"
    if t.startswith("fn[f:"):
        m = self.funcs[t[5:-1]].mod
        return f"{m if m != '' else '__main__'}.{short(t[5:-1])}()"
    if t.startswith("fn[c:"):
        clo = self.closures[int(t[5 : t.find(":", 5)])]
        return f"{clo.f.mod if clo.f.mod != '' else '__main__'}.{clo.qual}()"
    return ""

def gen_print_star(self, n: Node, args: list[Node]) -> Val:
    # print(a, *xs, b, sep=..., end=..., file=..., flush=...) where xs is a list known only at run
    # time: one argument, the str of each item and argument joined by sep (" " if None). The
    # arguments are evaluated first, in order, then each one's str is made, as print makes them
    sep: Node = mk("str", " ", n.line, [])
    parts: list[Node] = []
    kws: list[Node] = []
    for a in args:
        if a.kind == "starred":
            parts.append(a.kids[0])  # (a list comprehension of the strs of the list's items)
        elif a.kind == "kw":
            sv = self.vnode(self.expr(a.kids[0], "str" if a.s == "sep" or a.s == "end" else ""))
            if a.s == "sep":
                sep = mk("ifexp", "", n.line, [mk("cmp", "is", n.line, [sv, mk("None", "", n.line, [])]), mk("str", " ", n.line, []), sv])
            else:
                kws.append(mk("kw", a.s, a.line, [sv]))
        else:
            parts.append(mk("list", "", n.line, [mk("call", "", n.line, [mk("name", "str", n.line, []), self.vnode(self.expr(a, ""))])]))
    joined: Node = parts[0]
    for x in parts[1:]:
        joined = mk("binop", "+", n.line, [joined, x])
    line = mk("call", "", n.line, [mk("attr", "join", n.line, [sep]), joined])
    return self.call(mk("call", n.s, n.line, [mk("name", "print", n.line, []), line] + kws), "")

def gen_not_callable(self, name: str, t: str) -> None:
    # a call of variable name's value (c() for an object c), of type t: CPython's TypeError,
    # unless it has __call__ or is a function (is_fn); a builtin's name bound as a variable is
    # rejected as such
    if is_fn(t) or is_callable(unopt(t)):
        return
    if short(name) in PYBUILTINS or t == "":
        self.err(f"'{name}' is a variable, so it cannot be called")
    if t not in self.classes or "__call__" not in self.classes[t].methods:
        self.err(f"'{tname(unopt(t))}' object is not callable")

def gen_obj_call(self, o: Val, args: list[Node], want: str) -> Val:
    # o(args), o already evaluated: a call of the function o is (is_fn), or o.__call__(args) where
    # o's class defines it, else CPython's TypeError; an o that is None raises its TypeError once
    # the arguments are evaluated
    if is_fn(o.t):
        return self.call_value(o, args, want)
    if is_callable(unopt(o.t)):
        return self.call_callable(o, args)
    if o.t not in self.classes or "__call__" not in self.classes[o.t].methods:
        self.err(f"'{tname(unopt(o.t))}' object is not callable")
    if self.cached_wrapper(o.t):
        return self.call_cache(o, args, want)
    return self.call_fn(self.classes[o.t].methods["__call__"], [o], args, want, "TypeError: 'NoneType' object is not callable")

def gen_cached_wrapper(self, t: str) -> bool:
    # Only the bundled functools wrapper uses this calling convention. Its generic
    # __wrapped__ field retains the exact function type, including names and defaults.
    return t in self.classes and self.classes[t].mod == "functools" and short(self.classes[t].origin) == "_lru_cache_wrapper"

def gen_call_cache(self, o: Val, args: list[Node], want: str) -> Val:
    t = self.classes[o.t].ftypes["__wrapped__"]
    if t.startswith("fn[c:"):
        # The env is read after the arguments, before defaults are loaded (call_fn).
        return self.call_fn(self.closures[int(t[5 : t.find(":", 5)])].f, [Val("null", "env")], args, want, "", o)
    if t.startswith("fn[f:"):
        return self.call_fn(self.funcs[t[5:-1]], [], args, want, "", o)
    self.err("cached calls with defaults or keywords need a def's signature")
    return Val("", "")

def gen_to_callable(self, v: Val, t: str) -> Val:
    # function value v as a Callable of type t: an object {code, env}, whose code is an adapter
    # that calls v's function with the env (a closure's, or a bound method's object) and t's
    # parameters. A function of a module or a builtin has no env: one constant object serves for
    # each Callable type
    code = self.adapter(v.t, t)
    if v.t.startswith("fn[f:") or v.t.startswith("fn[b:") or v.t.startswith("fn[u:"):
        g = f"@cvo.{code[4:]}"
        if g not in self.cvos:
            self.cvos[g] = True
            self.consts.append(f"{g} = private constant {{ptr, ptr}} {{ptr {code}, ptr null}}")
        return Val(g, t)
    o = self.rt("pys_alloc", "ptr", ["i64 16"])
    self.emit(f"store ptr {code}, ptr {o}")
    self.emit(f"store ptr {v.v}, ptr {self.ins(f'getelementptr inbounds ptr, ptr {o}, i64 1')}")
    self.nn[o] = True
    return Val(o, t)

def gen_adapter(self, ft: str, t: str) -> str:
    # the code of a Callable of type t (callable[R,A,B]) that holds function value type ft: a
    # function R(ptr env, A a0, B a1) whose body calls the function, def <callable>(f, a0, a1):
    # return f(a0, a1), with f typed ft (a closure's value is its env), compiled when first needed
    # The same virtual method viewed through a base or derived type remains one bound
    # method. Reuse its family's adapter when this Callable signature fits every member.
    # Return inference in adapter_ret stays receiver-specific for differing result types.
    if ft.startswith("fn[m:"):
        cls = ft[5 : ft.rfind(".")]
        method = ft[ft.rfind(".") + 1 : -1]
        if cls in self.classes and self.classes[cls].tag != 0:
            family = cls
            while self.classes[family].base in self.classes and method in self.classes[self.classes[family].base].methods:
                family = self.classes[family].base
            fits = True
            signature = targs(t)
            for ci in self.classes.values():
                if ci.tag != 0 and self.derives(ci.name, family) and method in ci.methods:
                    member = ci.methods[method]
                    if member.ret == "" or not self.widens(member.ret, signature[0]):
                        fits = False
                    for j in range(1, len(signature)):
                        if j >= len(member.ptypes) or (member.ptypes[j] != "" and not self.widens(signature[j], member.ptypes[j])):
                            fits = False
            if fits:
                ft = f"fn[m:{family}.{method}]"
            else:
                self.err(f"converting inherited method {short(cls)}.{method} to Callable requires compatible signatures and annotated return types throughout its hierarchy")
    key = ft + " " + t
    if key in self.adapters:
        return self.adapters[key]
    ts = targs(t)
    ll = f"@cv.{self.ncv}"
    self.ncv += 1
    self.adapters[key] = ll
    line = self.line
    f = FnInfo("<callable>", ll, mk("def", "<callable>", line, []), "")
    f.params = ["_f"] + [f"_a{j}" for j in range(len(ts) - 1)]
    f.ptypes = [ft] + ts[1:]
    for _ in f.params:
        f.defaults.append(mk("noann", "", line, []))
        f.dglob.append("")
        f.dtypes.append("")
    f.ret = ts[0]
    f.mod = self.curfn.mod
    call = mk("call", "", line, [mk("name", p, line, []) for p in f.params])
    body = [mk("return", "", line, [call]) if ts[0] != "None" else mk("expr", "", line, [call])]
    f.node.kids = [mk("params", "-1,-1", line, []), mk("noann", "", line, []), mk("block", "", line, body)]
    self.making.append(f"making a {typestr(t)} of {typestr(ft)} at {where(line)}")
    fr = self.save()
    self.modlevel = False
    self.lenient = False
    self.function(f, body)
    self.restore(fr)
    self.making.pop()
    return ll

def gen_callable_pat(self, a: Node) -> str:
    # the class template C of annotation a when it is Callable[[A, B], C] (C named alone, A and B
    # no class template's), else ""
    if a.kind == "str":
        return self.callable_pat(self.parse_expr(a.s))
    if a.kind != "index" or (a.kids[0].kind != "name" and a.kids[0].kind != "attr"):
        return ""
    base = self.typing_attr(a.kids[0]) if a.kids[0].kind == "attr" else self.typing_name(a.kids[0].s)
    if base != "Callable" or a.kids[1].kind != "tuple" or len(a.kids[1].kids) != 2 or a.kids[1].kids[0].kind != "list":
        return ""
    r = a.kids[1].kids[1]
    for x in a.kids[1].kids[0].kids:
        if self.tmpl_ann(x):
            return ""
    if r.kind == "str":
        r = self.parse_expr(r.s)
    return r.s if r.kind == "name" and r.s in self.tmpl else ""

def gen_pat_arg(self, v: Val, a: Node) -> Val:
    # an argument for a parameter annotated Callable[[A, B], C], C a class template: a function
    # (or such a Callable) that returns an object of a specialization S of C, given A and B, as
    # the Callable[[A, B], S], so that one type holds the functions that return S (a field of
    # it, one specialization of the class that has the field); another is left as it is
    c = self.callable_pat(a)
    if a.kind == "str":
        a = self.parse_expr(a.s)
    ps = [self.vtype(x) for x in a.kids[1].kids[0].kids]
    if is_callable(v.t):
        r = targs(v.t)[0]
        if targs(v.t)[1:] != ps:
            return v
    elif is_fn(v.t):
        r = self.adapter_ret(v.t, ps)
    else:
        return v
    if self.tmpl_of(unopt(r)) != c:
        return v
    return self.coerce(v, self.ctype("callable", [r] + ps))

def gen_adapter_ret(self, ft: str, ps: list[str]) -> str:
    # what function value type ft returns, called with arguments of types ps: the adapter of a
    # Callable of those parameters (see adapter), compiled with its return type left to its
    # return statement, and kept for the Callable that returns that
    key = ft + " " + ",".join(ps)
    if key in self.adrets:
        return self.adrets[key]
    line = self.line
    ll = f"@cv.{self.ncv}"  # (its key needs what it returns: it is registered once compiled)
    self.ncv += 1
    f = FnInfo("<callable>", ll, mk("def", "<callable>", line, []), "")
    f.params = ["_f"] + [f"_a{j}" for j in range(len(ps))]
    f.ptypes = [ft] + ps
    for _ in f.params:
        f.defaults.append(mk("noann", "", line, []))
        f.dglob.append("")
        f.dtypes.append("")
    f.ret = ""  # (decided by its return statement, as a template's)
    f.infer = True
    f.inst = True
    f.mod = self.curfn.mod
    call = mk("call", "", line, [mk("name", p, line, []) for p in f.params])
    body = [mk("return", "", line, [call])]
    f.node.kids = [mk("params", "-1,-1", line, []), mk("noann", "", line, []), mk("block", "", line, body)]
    self.making.append(f"making a Callable of {typestr(ft)} at {where(line)}")
    fr = self.save()
    self.modlevel = False
    self.lenient = False
    self.function(f, body)
    self.restore(fr)
    self.making.pop()
    self.adrets[key] = f.ret
    self.adapters[ft + " " + self.ctype("callable", [f.ret] + ps)] = ll
    return f.ret

def gen_call_callable(self, o: Val, args: list[Node]) -> Val:
    # o(args), o a Callable (callable[R,A,B]): its code, with its env and the arguments, which
    # the Callable's parameter types type (they are positional: its function's names are not known).
    # One that may be None raises once the arguments are evaluated, as CPython's call does
    ct = unopt(o.t)
    ts = targs(ct)
    for a in args:
        if a.kind == "kw" or a.kind == "starred" or a.kind == "dstar":
            self.err(f"a call of a {typestr(ct)} takes positional arguments only")
    if len(args) != len(ts) - 1:
        self.err(f"a {typestr(ct)} takes {len(ts) - 1} argument{'s' if len(ts) != 2 else ''}, but {len(args)} {'were' if len(args) != 1 else 'was'} given")
    vals: list[Val] = []
    for j in range(len(args)):
        vals.append(self.coerce(self.expr(args[j], ts[j + 1]), ts[j + 1], f"argument {j + 1} of a {typestr(ct)}"))
    o = self.unwrap(o, "TypeError: 'NoneType' object is not callable")
    code = self.ins(f"load ptr, ptr {o.v}")
    env = self.ins(f"load ptr, ptr {self.ins(f'getelementptr inbounds ptr, ptr {o.v}, i64 1')}")
    c = Ins("icall", ts[0], "")
    c.a = [Val(code, "env"), Val(env, "env")] + vals
    if ts[0] == "None":
        self.add(c)
        return Val("null", "None")
    self.put(c, 1)
    return Val(f"%t{c.r[0]}", ts[0])

def gen_call_value(self, v: Val, args: list[Node], want: str) -> Val:
    # a call through function value v (is_fn): the call of the function it is, as if called by
    # its name there (the function a module's own name binds: a builtin that the program binds
    # is still the builtin)
    k = v.t[3:-1]
    if k.startswith("u:"):
        return self.unbound_call(k[2 : k.find(".")], k[k.find(".") + 1 :], args)
    if k.startswith("m:"):
        return self.method(Val(v.v, k[2 : k.rfind(".")]), k[k.rfind(".") + 1 :], args)  # (a bound method: o.name(args))
    if k.startswith("d:"):
        return self.method(Val(v.v, k[k.find(":", 2) + 1 :]), k[2 : k.find(":", 2)], args)
    if k.startswith("b:"):
        return self.builtin(k[2:], args, want)
    if k.startswith("c:"):
        # a closure: its function takes its env first
        return self.call_fn(self.closures[int(k[2 : k.find(":", 2)])].f, [Val(v.v, "env")], args, want)
    return self.call_fn(self.funcs[k[2:]], [], args, want)

def gen_bound(self, s: str) -> bool:
    # a builtin's name that the program binds (a local, def, class or module-level variable)
    return s in self.ltype or s in self.funcs or s in self.classes or s in self.mvars

def gen_open_call(self, n: Node) -> bool:
    return n.kind == "call" and n.kids[0].kind == "name" and n.kids[0].s == "open" and not self.bound("open")

def gen_close_temp(self, n: Node, v: Val) -> None:
    # open(p).read(): nothing else refers to the file, so CPython closes it right after its use,
    # in its finalizer, which reports a failure and goes on
    if v.t == "file" and self.open_call(n):
        self.rt("pys_file_drop", "void", [f"ptr {v.v}"])

def gen_open_(self, args: list[Node]) -> Val:
    # open(file, mode="r", buffering=-1, encoding=None, errors=None, newline=None): text files
    names = ["file", "mode", "buffering", "encoding", "errors", "newline"]
    given: dict[str, Node] = {}
    pos = 0
    for a in args:
        nm = a.s if a.kind == "kw" else names[pos] if pos < len(names) else ""
        if a.kind != "kw":
            pos += 1
        if nm == "closefd" or nm == "opener" or (a.kind != "kw" and nm == ""):
            self.err("open() supports only file, mode, buffering, encoding, errors and newline")
        if nm not in names:
            self.err(f"open() got an unexpected keyword argument '{nm}'")
        if nm in given:
            self.err(f"open() got multiple values for argument '{nm}'")
        given[nm] = a.kids[0] if a.kind == "kw" else a
    if "file" not in given:
        self.err("open() missing required argument 'file' (pos 1)")
    if "mode" in given and given["mode"].kind == "str" and given["mode"].s.find("b") >= 0:
        self.err("binary files are not supported (there is no bytes type)")
    e = given.get("errors", mk("None", "", self.line, []))
    if not (e.kind == "None" or (e.kind == "str" and e.s == "strict")):
        self.err("open(errors=...) is not supported: files are UTF-8, and decoding errors are not checked")
    e = given.get("encoding", mk("None", "", self.line, []))
    if e.kind == "str" and codec(e.s) == 0:
        self.err(f"only UTF-8 and Latin-1 files are supported, not encoding='{e.s}'")
    # every argument is evaluated in the order written, then the file is opened
    vals: dict[str, str] = {"mode": self.sconst("r"), "buffering": "-1", "encoding": "null", "newline": "null"}
    nones: list[str] = []  # optional arguments that may not be None, and what None raises
    nmsg: list[str] = []
    pos = 0
    for a in args:
        nm = a.s if a.kind == "kw" else names[pos]
        if a.kind != "kw":
            pos += 1
        x = a.kids[0] if a.kind == "kw" else a
        want = "int" if nm == "buffering" else "str"
        v = self.expr(x, want)
        if v.t == "None" and (nm == "encoding" or nm == "errors" or nm == "newline"):
            continue
        if is_opt(v.t) and (nm == "encoding" or nm == "newline"):
            v = Val(v.v, "str")  # None is the default
        elif is_opt(v.t) and (nm == "file" or nm == "mode"):
            nones.append(v.v)
            nmsg.append("TypeError: expected str, bytes or os.PathLike object, not NoneType" if nm == "file" else "TypeError: open() argument 'mode' must be str, not None")
            v = Val(v.v, "str")
        vals[nm] = self.coerce(v, want).v
    for j in range(len(nones)):
        self.guard(self.ins(f"icmp eq ptr {nones[j]}, null"), nmsg[j])
    return Val(self.rt("pys_open", "ptr", [f"ptr {vals['file']}", f"ptr {vals['mode']}", f"ptr {vals['encoding']}", f"ptr {vals['newline']}",
                                           f"i64 {vals['buffering']}"]), "file")

def gen_method(self, o: Val, m: str, args: list[Node]) -> Val:
    if (o.t == "fn[b:str]" or o.t == "fn[b:list]" or o.t == "fn[b:dict]") and has_method(o.t[5:-1], m):
        return self.unbound_call(o.t[5:-1], m, args)
    if is_kw(o.t):
        return self.kw_method(o, m, args)
    if is_opt(o.t):
        o = self.unwrap(o, f"AttributeError: 'NoneType' object has no attribute '{m}'")
    if o.t in self.nts and m == "__init__":
        # p.__init__(args) of a NamedTuple (also through p.__init__ as a value): object.__init__,
        # as tuple.__new__ set the fields. It takes any arguments where the class has a __new__
        # of its own, and does nothing, also on None. The __init__ that makes the object is the
        # compiler's (see nt_class), which only construction and _replace() call
        for a in args:
            x = a.kids[0] if a.kind == "kw" else a
            if not pure_arg(x):
                self.expr(x, "")
        return Val("null", "None")
    if (o.t == "exc" or (o.t in self.classes and self.classes[o.t].exc != "")) and (m == "__str__" or m == "__repr__") and len(args) == 0 and not self.curfn.ll.startswith("@x."):
        # e.__str__() is str(e): that of the class of e's object, which may derive from o.t's
        # (but for the ExcClass's own functions, see exc_helpers)
        return self.to_str(o) if m == "__str__" else self.repr(o)
    if o.t in self.classes and m == "__init__" and self.classes[o.t].exc != "":
        for c in self.classes.values():
            if c.name != o.t and self.derives(c.name, o.t) and "__init__" in c.methods and c.methods["__init__"].cls == c.name:
                self.err(f"a call of __init__ on an object of {short(o.t)} is not supported where {short(c.name)}, deriving from it, defines __init__ again (calls are not dispatched on the object's class)")
    if o.t in self.classes:
        ci = self.classes[o.t]
        if m == "__call__" and self.cached_wrapper(o.t):
            self.notnone(o, "AttributeError: 'NoneType' object has no attribute '__call__'")
            return self.call_cache(o, args, "")
        if m not in ci.methods and ci.exc != "" and m in HASATTR["any"].split() + ["add_note", "with_traceback"]:
            self.err(f"{short(o.t)} has no method {m}() of its own, and BaseException.{m}() is not supported" + (" (call super().__init__(...) in __init__)" if m == "__init__" else ""))
        if m not in ci.methods and m in ci.ftypes:
            return self.obj_call(self.getfield(o, self.field(o, m), m), args, "")  # (o.f(args) of a field f)
        if m not in ci.methods and not ((m == "_replace" or m == "_asdict") and o.t in self.nts):
            self.err(f"'{shown(o.t)}' object has no method '{m}'")  # (a specialization's is its class's)
        self.notnone(o, f"AttributeError: 'NoneType' object has no attribute '{m}'")
        if m == "_asdict" and m not in ci.methods:
            return self.asdict(o, args)
        if m not in ci.methods:
            return self.replace(o, args)
        if ci.methods[m].iters:
            self.err(f"calling {short(o.t)}.__iter__() is not supported (its iterator is the list it steps through here): iterate over the object")
        self.cls_bound(ci.methods[m], o.t, True)
        return self.call_fn(ci.methods[m], [o] if ci.methods[m].deco == "" else [], args)  # (a static or class method gets no o)
    return self.bmethod(o, m, args)

def gen_unbound_call(self, tn: str, m: str, args: list[Node]) -> Val:
    # T.m(o, args) of builtin type T (str.lower(s), list.append(xs, x)): o.m(args), where o must
    # be a T (CPython's TypeError otherwise: a compile error here, but for None)
    if len(args) == 0 or args[0].kind == "kw" or args[0].kind == "starred" or args[0].kind == "dstar":
        self.err(f"unbound method {tn}.{m}() needs an argument")
    o = self.expr(args[0], "str" if tn == "str" else "")
    t = unopt(o.t)
    if ("list" if is_list(t) else "dict" if is_dict(t) else t) != tn:
        self.err(f"descriptor '{m}' for '{tn}' objects doesn't apply to a '{tname(t)}' object")
    rest = args[1:]
    if is_opt(o.t):
        # (an o that may be None raises once the other arguments are evaluated, as CPython's call does)
        rest = [mk("kw", a.s, a.line, [self.vnode(self.expr(a.kids[0], ""))]) if a.kind == "kw" else self.vnode(self.expr(a, "")) for a in rest]
    o = self.unwrap(o, f"TypeError: descriptor '{m}' for '{tn}' objects doesn't apply to a 'NoneType' object")
    return self.method(o, m, rest)

def gen_kw_record(self, names: list[str], vals: list[Val]) -> Val:
    # the **kwargs of a call: its extra keyword arguments, a tuple of the values typed by the
    # record of their names and types (is_kw)
    tu = self.tuple_(vals)
    ts = targs(tu.t)
    return Val(tu.v, "kw[" + ",".join([names[i] + ":" + ts[i] for i in range(len(ts))]) + "]")

def gen_kw_method(self, o: Val, m: str, args: list[Node]) -> Val:
    # kwargs.m(args): get() of a literal name and keys() from the record, the others of the dict
    # CPython makes; a method that changes it is rejected (kwargs then is another record)
    names = kw_names(o.t)
    if m == "get" and len(args) >= 1 and args[0].kind == "str" and len([a for a in args if a.kind != "kw"]) == len(args) and len(args) <= 2:
        dv = self.expr(args[1], "") if len(args) == 2 else Val("null", "None")  # (CPython evaluates the default anyway)
        if args[0].s in names:
            return self.tget(self.kw_tuple(o), names.index(args[0].s))
        return dv
    if m == "keys" and len(args) == 0:
        return self.expr(mk("list", "", self.line, [mk("str", x, self.line, []) for x in names]), "list[str]")
    if m == "pop" or m == "popitem" or m == "setdefault" or m == "update" or m == "clear":
        self.err("changing **kwargs is not supported: copy it to a dict first (d = dict(kwargs))")
    return self.method(self.kw_dict(o), m, args)

def gen_kw_repr(self, v: Val) -> Val:
    # str() and repr() of kwargs: those of the dict CPython makes, {'a': 1, 'b': 'x'}, whatever
    # its values' types
    line = self.line
    names = kw_names(v.t)
    out: Node = mk("str", "{", line, [])
    for i in range(len(names)):
        out = mk("binop", "+", line, [out, mk("str", (", " if i > 0 else "") + "'" + names[i] + "': ", line, [])])
        item = self.vnode(self.tget(self.kw_tuple(v), i))
        out = mk("binop", "+", line, [out, mk("call", "", line, [mk("name", "__pys_repr", line, []), item])])
    return self.expr(mk("binop", "+", line, [out, mk("str", "}", line, [])]), "str")

def gen_kw_list(self, v: Val) -> Val:
    # the names of kwargs v, a list[str] (what iterating it gives)
    return self.expr(mk("list", "", self.line, [mk("str", x, self.line, []) for x in kw_names(v.t)]), "list[str]")

def gen_kw_tuple(self, v: Val) -> Val:
    # kwargs v as the tuple of its values
    return Val(v.v, "tuple[" + ",".join(kw_types(v.t)) + "]")

def gen_kw_dict(self, v: Val) -> Val:
    # kwargs v as the dict CPython makes it, a new one: its values must have one type
    line = self.line
    ts = kw_types(v.t)
    jt = ts[0] if len(ts) > 0 else ""
    for x in ts[1:]:
        jt = self.join(jt, x) if jt != "" else ""
    if len(ts) > 1 and jt == "":
        self.err(f"using {typestr(v.t)} as a dict is not supported: its values have different types (read each by its name, kwargs['name'], or forward it, f(**kwargs))")
    kids: list[Node] = []
    for i in range(len(kw_names(v.t))):
        kids.append(mk("str", kw_names(v.t)[i], line, []))
        kids.append(self.vnode(self.tget(self.kw_tuple(v), i)))
    return self.expr(mk("dict", "", line, kids), "")

def gen_method_value(self, o: Val, name: str) -> Val:
    # o.name read as a value, where name is a method of o's value and no field: the method bound
    # to it, fn[m:C.name] for an object of class C, fn[d:name:T] for a str, list, dict or file,
    # whose value is the object (a call through it is o.name(...): call_value); else Val("", "")
    t = unopt(o.t)
    if (t == "fn[b:str]" or t == "fn[b:list]" or t == "fn[b:dict]") and has_method(t[5:-1], name):
        return Val("null", f"fn[u:{t[5:-1]}.{name}]")  # (str.lower: the method, which takes the str first)
    if t in self.classes:
        ci = self.classes[t]
        if name in ci.ftypes or name not in ci.methods:
            return Val("", "")
        f = ci.methods[name]
        if f.deco != "":
            self.err(f"{'a static' if f.deco == 'staticmethod' else 'a class'} method as a value ({short(t)}.{name}) is not supported: call it")
        if f.iters:
            self.err(f"{short(t)}.__iter__ as a value is not supported (its iterator is the list it steps through here): iterate over the object")
        if not (t in self.nts and name == "__init__"):  # (object.__init__, which None has too: method())
            self.notnone(o, f"AttributeError: 'NoneType' object has no attribute '{name}'")
        return Val(o.v, f"fn[m:{t}.{name}]")
    base = "list" if is_list(t) else "dict" if is_dict(t) else "frozenset" if is_fset(t) else "set" if is_set(t) else t
    if has_method(base, name) and (t == "str" or t == "file" or is_list(t) or is_dict(t) or is_set(t)):
        o = self.unwrap(o, f"AttributeError: 'NoneType' object has no attribute '{name}'")
        return Val(o.v, f"fn[d:{name}:{t}]")
    return Val("", "")

def gen_replace(self, o: Val, args: list[Node]) -> Val:
    # p._replace(f=v, ...): a new NamedTuple with the fields given, and p's others
    ci = self.classes[o.t]
    given: dict[str, Val] = {}
    npos = len([a for a in args if a.kind != "kw"])
    for a in args:
        if a.kind != "kw":
            self.err(f"{short(o.t)}._replace() takes 1 positional argument but {npos + 1} were given")
        if a.s not in ci.ftypes:
            self.err(f"Got unexpected field names: ['{a.s}']")
        given[a.s] = self.expr(a.kids[0], ci.ftypes[a.s])
    vals: list[Val] = [self.new_obj(o.t)]
    for fl in ci.fields:
        vals.append(given[fl] if fl in given else self.getfield(o, self.field(o, fl), fl))
    self.call_fn(ci.methods["__init__"], vals, [])
    return vals[0]

def gen_asdict(self, o: Val, args: list[Node]) -> Val:
    # p._asdict(): a dict from its fields' names to their values, which must then share one type
    ci = self.classes[o.t]
    if len(args) > 0:
        self.err(f"{short(o.t)}._asdict() takes 1 positional argument but {len(args) + 1} were given")
    vt = ci.ftypes[ci.fields[0]]
    for fl in ci.fields:
        vt = self.wider(vt, ci.ftypes[fl])
        if vt == "":
            self.err(f"_asdict() of a NamedTuple whose fields have different types is not supported (a dict's values have one type): {short(o.t)}")
    r = self.rt("pys_dict_new", "ptr", [f"i64 {self.key_kind('str')}", f"i64 {len(ci.fields)}"])
    for fl in ci.fields:
        v = self.coerce(self.getfield(o, self.field(o, fl), fl), vt)
        self.rt("pys_dict_set", "void", [f"ptr {r}", "i64 " + self.to_slot(Val(self.sconst(fl), "str")), "i64 " + self.to_slot(v)])
    return Val(r, self.ctype("dict", ["str", vt]))

def gen_new_obj(self, c: str) -> Val:
    # a new object of class c, which its __init__ initializes: it holds its class-body defaults
    # (but where @dataclass wrote __init__, which assigns every field itself)
    size = f"ptrtoint (ptr getelementptr (%C.{c}, ptr null, i32 1) to i64)"
    o = Val(self.rt("pys_alloc", "ptr", [f"i64 {size}"]), c)
    self.nn[o.v] = True
    if self.classes[c].tag > 0:
        self.emit(f"store i64 {self.classes[c].tag}, ptr {o.v}")
    if not (self.is_dc(c) and self.classes[c].methods["__init__"].node.kids[0].kind == "noann"):
        line = self.line
        self.class_defaults(o)
        self.line = line
    return o

def gen_pcoerce(self, v: Val, t: str, f: FnInfo, j: int) -> Val:
    # argument j of f for a parameter of type t ("": a template's unannotated parameter takes any type)
    if t == "":
        return v
    what = ""
    if is_opt(v.t):
        what = f"argument {j if takes_self(f) else j + 1} of {short(f.name)}()" if j < f.npos else f"argument '{f.params[j]}' of {short(f.name)}()"
    return self.coerce(v, t, what)

def gen_virtual_call(self, f: FnInfo, pre: list[Val], args: list[Node], want: str, none: str) -> Val:
    # Closed-world dispatch, before argument binding: an override owns its defaults. Each
    # selected body is a normal method-template instance, specialized for the concrete self.
    o = pre[0]
    cs = [c for c in self.classes.values() if c.tag > 0 and self.derives(c.name, o.t)]
    if len(cs) == 1:
        return self.call_fn(cs[0].methods[f.name], pre, args, want, none, direct=True)
    # Evaluate explicit arguments once, before reading the receiver tag (also for a None
    # callable). Defaults remain inside the selected branch. Overrides have the same typed
    # parameter interface; an unannotated argument is specialized from its value.
    bound: list[Node] = []
    pos = len(pre)
    for a in args:
        j = f.params.index(a.s) if a.kind == "kw" and a.s in f.params else pos
        t = f.ptypes[j] if j < len(f.ptypes) and j != f.vararg and j != f.kwarg else ""
        argnode = self.vnode(self.expr(a.kids[0] if a.kind == "kw" else a, t))
        bound.append(mk("kw", a.s, a.line, [argnode]) if a.kind == "kw" else argnode)
        if a.kind != "kw":
            pos += 1
    self.notnone(o, none if none != "" else f"AttributeError: 'NoneType' object has no attribute '{f.name}'")
    tag = self.ins(f"load i64, ptr {o.v}")
    end = self.label()
    vals: list[Val] = []
    edges: list[str] = []
    narrow = dict(self.narrowed)
    for i in range(len(cs)):
        c = cs[i]
        nxt = self.label() if i + 1 < len(cs) else ""
        if nxt != "":
            arm = self.label()
            self.cbr(self.ins(f"icmp eq i64 {tag}, {c.tag}"), arm, nxt)
            self.place(arm)
        self.narrowed = dict(narrow)
        v = self.call_fn(c.methods[f.name], [Val(o.v, c.name)] + pre[1:], bound, want, direct=True)
        if not self.term:
            vals.append(v)
            edges.append(self.cur)
            self.br(end)
        if nxt != "":
            self.place(nxt)
    self.narrowed = narrow
    t = vals[0].t if len(vals) > 0 else "None"
    for v in vals[1:]:
        t = self.join(t, v.t)
        if t == "":
            self.err(f"overrides of {short(o.t)}.{f.name}() return incompatible types; use a common return type")
    ph = Ins("phi", t, "")
    for i in range(len(vals)):
        self.incoming(ph, self.convert_at(vals[i], t, edges[i]).v, edges[i])
    self.place(end)
    if len(vals) == 0:
        self.unreachable()
    return Val("null", "None") if t == "None" else Val(self.phi(ph), t)

def gen_call_fn(self, f: FnInfo, pre: list[Val], args: list[Node], want: str = "", none: str = "", cache: Val | None = None, direct: bool = False) -> Val:
    # f(pre + args); none: the error where pre[0], an object called (o(args)), is None
    if f.pyexport:
        self.err(f"{f.name}() is @export, so Pystachy code may not call it (under CPython each call goes through the export's checks and conversions): call a private function that both use")
    if f.bad != "":
        self.err(f.bad)  # (before its arguments, whose types may be placeholders')
    if f.cls in self.classes and self.classes[f.cls].tag > 0 and f.deco == "" and len(pre) > 0:
        if pre[0].t not in self.classes or not self.derives(pre[0].t, f.cls):
            self.err(f"{short(f.cls)}.{f.name}() needs an instance of {short(f.cls)}")
        if not direct:
            return self.virtual_call(f, pre, args, want, none)
    if f.ll not in self.called and f.ll in self.lazyat:
        hpush(self.wake, self.lazyat[f.ll])
    self.called[f.ll] = True
    self.arity(f, len(pre), args)
    line = self.line
    np = len(f.params)
    vals: list[Val] = []
    for i in range(np):
        vals.append(self.pcoerce(pre[i], f.ptypes[i], f, i) if i < len(pre) else Val("", ""))
    pos = len(pre)
    extra: list[Val] = []
    kwn: list[str] = []
    kwv: list[Val] = []
    for a in args:
        j = pos
        e = a
        if a.kind == "starred" or a.kind == "dstar":
            self.err("star arguments are not supported")
        if a.kind != "kw" and f.vararg >= 0 and j >= f.vararg:
            t = targs(f.vartup)[len(extra)] if f.vartup != "" else f.varelem  # (*args: *Ts: its item's type, see arity)
            extra.append(self.pcoerce(self.expr(a, t), t, f, f.vararg))
            pos += 1
            continue
        if a.kind == "kw" and f.kwarg >= 0 and (a.s not in f.params or f.params.index(a.s) < f.posonly or f.params.index(a.s) == f.kwarg or f.params.index(a.s) == f.vararg):
            if a.s in kwn:
                # (two of one name, from ** of a record or display: CPython's TypeError)
                self.err(f"{f.mod if f.mod != '' else '__main__'}.{self.qualname(f)}() got multiple values for keyword argument '{a.s}'")
            kwn.append(a.s)  # (an extra keyword argument: **kwargs's)
            kwv.append(self.pcoerce(self.expr(a.kids[0], f.kwelem), f.kwelem, f, f.kwarg) if f.kwelem != "" else self.expr(a.kids[0], ""))
            continue
        if a.kind == "kw":
            j = f.params.index(a.s)
            e = a.kids[0]
        else:
            pos += 1
        vals[j] = self.pcoerce(self.expr(e, f.ptypes[j]), f.ptypes[j], f, j)
        if j in f.pats:
            vals[j] = self.pat_arg(vals[j], f.pats[j])
    if f.vararg >= 0:
        vals[f.vararg] = self.stack_tuple(extra) if len(extra) > 0 and self.stack_ok(f) else self.tuple_(extra)
    if f.kwarg >= 0:
        vals[f.kwarg] = self.kw_record(kwn, kwv)
    if none != "":
        self.notnone(pre[0], none)  # (CPython calls o once it has evaluated the arguments)
    if cache is not None:
        self.notnone(cache, "TypeError: 'NoneType' object is not callable")
        if f.clo >= 0:
            wrapped = self.getfield(cache, self.field(cache, "__wrapped__"), "__wrapped__")
            pre[0] = Val(wrapped.v, "env")
    df = self.dflt_fn(f)
    for j in range(np):
        if vals[j].t == "":
            t = f.ptypes[j]
            if df.dglob[j] == "" and not is_const(f.defaults[j]):
                self.early_default(df, j)
            if df.dglob[j].startswith("!"):
                self.err(df.dglob[j][1:])
            if df.dglob[j] == "=None":
                vals[j] = Val("null", "None")
            elif df.dglob[j].startswith("&"):
                # a closure's default: in its env (pre[0]), evaluated where it was defined
                t = t if t != "" else df.dtypes[j]
                da = self.ins(f"getelementptr inbounds i64, ptr {pre[0].v}, i64 {df.dglob[j][1:]}")
                vals[j] = Val(self.ins(f"load {lt(t)}, ptr {da}"), t)
            elif df.dglob[j] != "":
                t = t if t != "" else df.dtypes[j]
                vals[j] = Val(self.ins(f"load {lt(t)}, ptr {df.dglob[j]}"), t)
            else:
                vals[j] = self.pcoerce(self.expr(f.defaults[j], t), t, f, j)
    self.line = line
    if cache is not None:
        # Evaluate and bind as an ordinary call, including def-time closure defaults,
        # but look up a key before invoking the function. The shape is a static tag:
        # f(1), f(1, 2), f(1, b=2), and different keyword orders remain distinct.
        shape = str(len([a for a in args if a.kind != "kw"])) + ":" + ",".join([a.s for a in args if a.kind == "kw"])
        full = str(f.npos - (1 if f.clo >= 0 else 0)) + ":"
        if shape != full and shape not in self.cacheforms:
            self.cacheforms[shape] = len(self.cacheforms) + 1
        for a in args:
            if a.kind == "kw" and f.params.index(a.s) >= f.npos:
                self.err("cached calls with keyword-only arguments are not supported")
        bound = vals[1 if f.clo >= 0 else 0 : f.npos]
        forwarded = [self.vnode(Val("0" if shape == full else str(self.cacheforms[shape]), "int"))] + [self.vnode(v) for v in bound]
        return self.call_fn(self.classes[cache.t].methods["_call"], [cache], forwarded, want)
    if f.name == "__init__" and len(pre) > 0 and pre[0].v == "" and f.cls in self.tmpl:
        # C(args) of a class template C: its arguments' types decide the specialization the
        # object belongs to (see specialize), whose __init__ initializes it
        sc = self.specialize(f.cls, [v.t for v in vals[1:]])
        vals[0] = self.new_obj(sc)
        pre[0] = vals[0]
        f = self.classes[sc].methods["__init__"]
    if f.generic:
        nnp: list[str] = []
        for j in range(np):
            if vals[j].t in self.classes and vals[j].v in self.nn and self.dispatches(f, f.params[j]):
                nnp.append(f.params[j])
        f = self.instance(f, [v.t for v in vals], nnp)
    c = Ins("call", f.ret, f.ll)
    c.a = [v for v in vals if v.t != "None"]  # (an argument that is None is not passed)
    if f.noret:
        # it never returns: the code after the call is not reached, and the call's value has the
        # type its context expects (return fail("bad") in a function returning int)
        self.add(c)
        self.unreachable()
        t = want if want != "" and "?" not in want else "None"
        return Val("0" if t == "int" else fbits("0.0") if t == "float" else "false" if t == "bool" else "null", t)
    if f.ret == "None":
        self.add(c)
        return Val("null", "None")
    if f.ll in self.guessed and f.ll != self.curfn.ll:
        self.guessed[self.curfn.ll] = self.guessed[f.ll]  # (what it returns may hold a guess)
    self.put(c, 1)
    if "?" in f.ret:
        self.qused[f.ll] = True  # (a recursive call: what it returns can no longer change)
        return self.typed_empty(Val(f"%t{c.r[0]}", f.ret), want, f)
    return Val(f"%t{c.r[0]}", f.ret)

def gen_fname(self, f: FnInfo) -> str:
    # f as CPython's errors about a call's arguments name it, by its qualified name: a
    # NamedTuple's is P.__new__
    if f.name == "__init__" and f.cls in self.nts:
        return f"{short(f.cls)}.__new__"
    return f"{short(f.cls)}.{f.name}" if f.cls != "" else short(f.name)

def gen_arity(self, f: FnInfo, npre: int, args: list[Node]) -> None:
    # CPython's TypeError for a call of f whose arguments do not fit its parameters, in the order
    # its frame setup finds them: a keyword that names no parameter (or a positional-only one)
    # or one already given, too many positional arguments, then the missing positional and
    # keyword-only ones; npre values (the object of a method) come before args
    np = len(f.params)
    last = f.vararg if f.vararg >= 0 else f.npos if f.npos >= 0 else np  # (the positional parameters end there)
    last = min(last, f.kwarg) if f.kwarg >= 0 else last
    given = npre
    filled: list[bool] = [False] * np
    for j in range(min(npre, last)):
        filled[j] = True
    for a in args:
        if a.kind != "kw":
            if given < last:
                filled[given] = True
            given += 1
    kws = [a.s for a in args if a.kind == "kw"]
    for a in args:
        if a.kind != "kw":
            continue
        j = f.params.index(a.s) if a.s in f.params and a.s != (f.params[f.vararg] if f.vararg >= 0 else "") else -1
        if f.kwarg >= 0 and (j < 0 or j < f.posonly or j == f.kwarg):
            continue  # (one of the keyword arguments **kwargs takes)
        if j < 0 or j < f.posonly:
            po = [k for k in kws if k in f.params and f.params.index(k) < f.posonly]
            if len(po) > 0:
                self.err(f"{self.fname(f)}() got some positional-only arguments passed as keyword arguments: '{', '.join(po)}'")
            self.err(f"{self.fname(f)}() got an unexpected keyword argument '{a.s}'")
        if filled[j]:
            self.err(f"{self.fname(f)}() got multiple values for argument '{a.s}'")
        filled[j] = True
    off = 1 if f.deco == "classmethod" else -1 if f.clo >= 0 else 0  # (cls, which CPython counts and f.params leaves out; a closure's env, the reverse)
    if f.vararg < 0 and given > last:
        if f.name == "__init__" and f.node.kids[0].kind == "noann" and not self.is_dc(f.cls):
            self.err(f"{short(f.cls)}() takes no arguments")
        dflt = len([j for j in range(last) if f.defaults[j].kind != "noann"])
        kwg = len([j for j in range(last, np) if filled[j]])
        takes = f"from {last + off - dflt} to {last + off}" if dflt > 0 else str(last + off)
        plural = "s" if dflt > 0 or last + off != 1 else ""
        kwonly = f" positional argument{'s' if given + off != 1 else ''} (and {kwg} keyword-only argument{'s' if kwg != 1 else ''})" if kwg > 0 else ""
        self.err(f"{self.fname(f)}() takes {takes} positional argument{plural} but {given + off}{kwonly} {'was' if given + off == 1 and kwg == 0 else 'were'} given")
    if f.vartup != "" and given >= f.vararg and given - f.vararg != len(targs(f.vartup)):
        # *args: *Ts, which a generic class's specialization binds: as many as Ts has types
        n = f.vararg + len(targs(f.vartup)) + off
        self.err(f"{self.fname(f)}() takes {n} positional argument{'s' if n != 1 else ''} but {given + off} {'was' if given + off == 1 else 'were'} given (its *{f.params[f.vararg]} is a {typestr(f.vartup)})")
    for kind in ["positional", "keyword-only"]:
        miss = [f.params[j] for j in range(np) if not filled[j] and f.defaults[j].kind == "noann" and j != f.vararg and j != f.kwarg and (j < last) == (kind == "positional")]
        if len(miss) > 0:
            names = "'" + "', '".join(miss) + "'"
            if len(miss) == 2:
                names = f"'{miss[0]}' and '{miss[1]}'"
            elif len(miss) > 2:
                names = "'" + "', '".join(miss[:-1]) + f"', and '{miss[-1]}'"
            self.err(f"{self.fname(f)}() missing {len(miss)} required {kind} argument{'s' if len(miss) != 1 else ''}: {names}")

def gen_kw_type(self, f: FnInfo, name: str) -> str:
    # the type call_fn evaluates keyword argument name of a call of f with: its parameter's, or
    # that of the values f's **kwargs takes where the name goes there ("" where it fits no
    # parameter, which arity reports)
    j = f.params.index(name) if name in f.params else -1
    if f.kwarg >= 0 and (j < 0 or j < f.posonly or j == f.kwarg or j == f.vararg):
        return f.kwelem
    return f.ptypes[j] if j >= 0 else ""

def gen_dispatches(self, f: FnInfo, p: str) -> bool:
    # does template f test its parameter p with isinstance(p, ...), hasattr(p, ...) or p is
    # (not) None (or p == None, see static), and never assign it: then an object known not to
    # be None decides the tests
    asg: dict[str, bool] = {}
    local_names(f.node.kids[2].kids, asg)
    return p not in asg and self.tests(f.node.kids[2].kids, p)

def gen_tests(self, ns: list[Node], p: str) -> bool:
    # (see dispatches)
    for n in ns:
        if n.kind == "call" and n.kids[0].kind == "name" and (n.kids[0].s == "isinstance" or n.kids[0].s == "hasattr") and len(n.kids) == 3 and n.kids[1].kind == "name" and n.kids[1].s == p:
            return True
        x = nonetest(n)
        if x >= 0 and n.kids[x].kind == "name" and n.kids[x].s == p:
            return True
        if self.tests(n.kids, p):
            return True
    return False
