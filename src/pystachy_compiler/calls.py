"""Calls component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.analysis import local_names, numeric_statement
from src.pystachy_compiler.diagnostics import dynamic_program, shown, where
from src.pystachy_compiler.ir import Data, FnInfo, Ins, Val
from src.pystachy_compiler.names import short
from src.pystachy_compiler.reflection import VARS_USES, refl_attr_fields, refl_formatter
from src.pystachy_compiler.specs import EXCEPTIONS, GLUE, HASATTR, MODATTRS, PYBUILTINS, RANGEC
from src.pystachy_compiler.structs import STRUCT_FNS
from src.pystachy_compiler.syntax import Node, made_var, mk
from src.pystachy_compiler.utils import (
    opaque_class,
    atomic_dict,
    identity_abi,
    identity_default,
    numeric_identity,
    clone,
    codec,
    elem,
    fbits,
    has_method,
    hpush,
    is_callable,
    is_const,
    is_dict,
    is_fn,
    is_gen,
    is_fset,
    is_kw,
    is_list,
    is_opt,
    is_set,
    is_tuple,
    is_union,
    kw_names,
    kw_types,
    literal_format,
    nonetest,
    pure_arg,
    runtime_format,
    takes_self,
    targs,
    tname,
    typestr,
    unopt,
)


def gen_call(self, n: Node, want: str, resultsoft: bool = False, typeargs: str = "") -> Val:
    f = n.kids[0]
    args = n.kids[1:]
    if f.kind == "name":
        self.modchk(f)  # resolve the callable's binding before specialized or unpacked arguments
    if self.getattr_name(f) != "":
        # getattr(o, "m")(args) is o.m(args): o, then the method, then the arguments
        f = mk("attr", self.getattr_name(f), f.line, [f.kids[1]])
        n = mk("call", n.s, n.line, [f] + args)
    if f.kind == "badattr":
        self.err(f.s)
    if refl_formatter(f) and len(args) >= 1 and args[0].kind == "str" and refl_attr_fields(args[0].s) and "string$Formatter" in self.classes and len([a for a in args if a.kind == "kw" or a.kind == "starred" or a.kind == "dstar"]) == 0:
        # string.Formatter().format("...", args) of a constant template: str.format() of it, which
        # the base Formatter's methods do (#486: its attribute fields, {0.x}, need no run-time names)
        self.expr(f.kids[0], "")
        return self.str_format(args[0].s, "format", args[1:])
    f = self.format_of(f)
    if literal_format(f) and f.s == "format_map" and len(args) == 1 and self.refl_dict_of(args[0]) is not None:
        return self.refl_format_map(f.kids[0].s, args[0])  # ("...".format_map(vars(x)): reflection.py)
    if literal_format(f):
        return self.str_format(f.kids[0].s, f.s, args)
    if f.kind == "attr" and (f.s == "format" or f.s == "format_map") and f.kids[0].kind == "name" and f.kids[0].s == "str" and not self.bound("str") and len(args) > 0:
        fmt = self.const_str(args[0])
        if fmt.kind == "str":
            return self.str_format(fmt.s, f.s, args[1:])  # (str.format("...", args), also of a module's FMT)
        if len([a for a in args if a.kind == "starred" or a.kind == "dstar"]) > 0:
            self.err(runtime_format(f.s))
    if f.kind == "index" and f.kids[0].kind == "name" and f.kids[0].s in self.tparams and f.kids[0].s not in self.ltype:
        self.modchk(f.kids[0])
        sc = self.generic_ann(f.kids[0].s, f.kids[1])
        if sc.startswith("!"):
            self.err(sc[1:])
        return self.call(mk("call", n.s, n.line, [f.kids[0]] + args), want, resultsoft, sc)
    if f.kind == "name" and f.s in STRUCT_FNS and f.s in self.funcs and f.s not in self.ltype:
        # (_struct's functions of a format known as the program compiles: see struct_call)
        r = self.struct_call(f.s, args, want)
        if r is not None:
            return r
    if len([a for a in args if a.kind == "starred" or a.kind == "dstar"]) > 0:
        return self.star_call(n, want, resultsoft, typeargs)
    if f.kind == "name" and f.s not in self.ltype:
        self.read_ahead(f.s)
        if (f.chk or self.foreign(f.s)) and f.s in self.gflag:
            # a call that may run before the def or class statement
            bad = self.scalar('xor', [Val(self.mload('bool', f'@g.{f.s}.def'), 'bool'), Val('true', 'bool')])
            self.guard(bad, self.unbound(f.s))
        if self.lib_fn(f, "functools$wraps"):
            self.err("functools.wraps() is supported as the decorator of a def, @wraps(wrapped): call update_wrapper(wrapper, wrapped) to name another function")
        if self.lib_fn(f, "functools$update_wrapper"):
            # (CPython's update_wrapper() of a function: the compiler gives wrapper the names, as
            # wrap_names says, and the call gives wrapper)
            if len(args) == 0 or args[0].kind == "kw":
                self.err("update_wrapper() missing 1 required positional argument: 'wrapper'" if len(args) == 0 or args[0].s != "wrapper" else "update_wrapper() of keyword argument wrapper is not supported")
            if len([a for a in args if a.kind == "starred" or a.kind == "dstar"]) > 0:
                self.err("update_wrapper() of unpacked arguments is not supported")
            w = self.expr(args[0], "")
            vals = [self.expr(a.kids[0] if a.kind == "kw" else a, "") for a in args[1:]]
            self.wrap_names(w, args[1:], vals, "update_wrapper")
            return w
        if (f.s == "json$loads" or f.s == "json$dumps") and self.dyn_policy(n.line) and self.lib_fn(f, f.s):
            r = self.json_any(f.s, args, want, resultsoft)  # (of Any values: #779)
            if r is not None:
                return r
        if f.s in self.funcs:
            return self.call_fn(self.funcs[f.s], [], args, want, resultsoft=resultsoft)
        if f.s in self.aliases and f.s not in self.gtypes:
            return self.builtin(self.aliases[f.s], args, want, resultsoft)
        if f.s in self.classes:
            if self.classes[f.s].exc != "":
                return self.exc_object(f.s, args)
            if self.classes[f.s].bad != "":
                self.err(self.classes[f.s].bad)
            if self.classes[f.s].mod in GLUE and self.curfn.mod != self.classes[f.s].mod:
                m = self.classes[f.s].mod
                self.err(f"{m}.{short(f.s)}() cannot be called: Pystachy's {m} module makes its objects (with {', '.join([x for x in GLUE[m] if x != short(f.s)])})")
            ab = self.abstract_of(f.s)
            if len(ab) > 0:
                # an object of a class with abstract methods (ABCMeta): CPython evaluates the
                # arguments, and object.__new__ raises its TypeError
                for a in args:
                    self.expr(a.kids[0] if a.kind == "kw" or a.kind == "starred" or a.kind == "dstar" else a, "")
                names = ", ".join([f"'{n}'" for n in ab])
                self.raise_("TypeError", self.sconst(f"Can't instantiate abstract class {short(f.s)} without an implementation for abstract method{'s' if len(ab) > 1 else ''} {names}"))
                return Val("null", f.s)
            if f.s in self.tmpl:
                # a class template: the types of the arguments pick the specialization, whose
                # object call_fn makes once it has them (in made[0])
                made = [Val("", f.s)]
                self.init_result(self.call_fn(self.classes[f.s].methods["__init__"], made, args, want, resultsoft=resultsoft, typeargs=typeargs))
                return made[0]
            o = self.new_obj(f.s)
            self.init_result(self.call_fn(self.classes[f.s].methods["__init__"], [o], args, direct=True))
            return o
        if f.s in self.mvars:
            self.not_callable(f.s, self.gtype(f.s))
            return self.obj_call(self.expr(f, ""), args, want, resultsoft)
        if f.s in self.unsupported:
            self.err(self.unsupported[f.s])
        if f.s in EXCEPTIONS and EXCEPTIONS[f.s] != "-":
            # an exception made, not raised (raise e raises it)
            vals = self.exc_vals(self.exc_args(n), f.s)
            if f.s == "SystemExit":
                return self.exit_value(vals)
            return self.exc_value("OSError" if f.s == "IOError" or f.s == "EnvironmentError" else f.s, vals)
        return self.builtin(f.s, args, want, resultsoft)
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
            return self.builtin(path, args, want, resultsoft)
        if f.kids[0].kind == "call" and f.kids[0].kids[0].kind == "name" and f.kids[0].kids[0].s == "super" and not self.bound("super"):
            return self.super_call(f.kids[0], f.s, args)
        if f.kids[0].kind == "name" and f.kids[0].s == "dict" and f.s == "fromkeys" and not self.bound("dict"):
            return self.fromkeys(args, want, resultsoft)
        if f.kids[0].kind == "name" and "?" in self.rtype(f.kids[0].s):
            return self.fill(f.kids[0], f.s, args, want)
        if f.kids[0].kind == "name" and f.kids[0].s in self.nts and f.kids[0].s not in self.ltype and f.s == "_make":
            self.class_ready(f.kids[0])
            return self.nt_make(f.kids[0].s, args, want)
        if f.kids[0].kind == "name" and f.kids[0].s in self.classes and f.kids[0].s not in self.ltype:
            return self.class_call(f.kids[0], f.s, args, want, resultsoft)
        if self.refl_dict_of(f.kids[0]) is not None:
            if f.s == "copy" and len(args) == 0:
                return self.refl_dict_copy(f.kids[0])  # (vars(x).copy(): reflection.py)
            self.err(VARS_USES)
        o = self.expr(f.kids[0], self.default_want(f.kids[0], f.s, args, ""))
        self.mcall = n
        r = self.method(o, f.s, args, want, resultsoft)
        if f.s != "close":
            self.close_temp(f.kids[0], o)
        return r
    if f.kind == "name":
        self.not_callable(f.s, self.ltype[f.s])
    return self.obj_call(self.expr(f, ""), args, want, resultsoft)

def gen_star_call(self, n: Node, want: str, resultsoft: bool = False, typeargs: str = "") -> Val:
    # f(a, *t, k=v): the items a star unpacks are positional arguments. CPython evaluates the
    # function (o.m binds o first), then the positional arguments in order, unpacking each star,
    # then the keyword ones; here each is evaluated so (but a constant or a name, which nothing
    # can change meanwhile, keeps the type its parameter wants), a tuple's items become
    # arguments, and the call is compiled with them (a list's items, which only run time knows,
    # only print() takes: a sole star's once the keywords are evaluated, as CPython unpacks it)
    f = n.kids[0]
    args = n.kids[1:]
    if self.static_callee(f):
        if f.kind == "attr":
            self.modchk(f)
        # The callable has been read now. An argument may retry a failed module's import,
        # resetting its binding flags; the recursive call below must not read them again.
        f = clone(f)
        callee = f
        while callee.kind == "attr":
            callee.mchk = ""
            callee = callee.kids[0]
        if callee.kind == "name":
            callee.mchk = ""
    receiver = Val("", "")
    if f.kind == "attr" and not self.static_callee(f) and f.kids[0].kind != "val":
        receiver = self.expr(f.kids[0], "")
        if self.reference_union(receiver.t):
            self.err("reference union methods do not support unpacked arguments")
        if receiver.t == "str" and (f.s == "format" or f.s == "format_map"):
            self.err(runtime_format(f.s))
        f = mk("attr", f.s, f.line, [self.vnode(receiver)])
    elif f.kind != "attr" and f.kind != "val" and not self.static_callee(f):
        f = self.vnode(self.expr(f, ""))
    dynh = Val("", "")
    if f.kind == "attr" and receiver.t == "dyn":
        # (o.m(*t, **d) of an Any o: the method is found first, as CPython's LOAD_ATTR finds it,
        # with the call's shape, which the displays, tuples and **kwargs that the stars unpack
        # give without evaluating them; then the arguments: dyn_method_found)
        npos = 0
        names: list[str] = []
        known = True
        for a in args:
            if a.kind == "kw":
                names.append(a.s)
            elif a.kind == "dstar" and a.kids[0].kind == "dict" and len([i for i in range(0, len(a.kids[0].kids), 2) if a.kids[0].kids[i].kind != "str"]) == 0:
                names = names + [a.kids[0].kids[i].s for i in range(0, len(a.kids[0].kids), 2)]
            elif a.kind == "dstar" and is_kw(self.dry(a.kids[0])):
                names = names + kw_names(self.dry(a.kids[0]))
            elif a.kind == "starred" and (a.kids[0].kind == "list" or a.kids[0].kind == "tuple") and len([x for x in a.kids[0].kids if x.kind == "starred"]) == 0:
                npos += len(a.kids[0].kids)
            elif a.kind == "starred" and is_tuple(unopt(self.dry(a.kids[0]))):
                npos += len(targs(unopt(self.dry(a.kids[0]))))
            elif a.kind == "starred" or a.kind == "dstar":
                known = False
            else:
                npos += 1
        if known:
            dynh = self.dyn_lookup(receiver, f.s, npos, names)
    dynamic = dynh.v != "" or (f.kind == "val" and self.vnodes[int(f.s)].t == "dyn")
    aw = "dyn" if dynamic else ""  # (an Any call's arguments are Any values: a display is Any's storage)
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
                pos.append(x if pure_arg(x) else self.vnode(self.expr(x, aw)))  # (*[a, b] of a display: its items)
        elif a.kind == "starred":
            v = self.expr(a.kids[0], "")
            self.line = a.line
            v = self.unwrap(v, f"TypeError: {who + ' argument' if who != '' else 'Value'} after * must be an iterable, not NoneType")
            if v.t == RANGEC:
                self.notnone(v, f"TypeError: {who + ' argument' if who != '' else 'Value'} after * must be an iterable, not NoneType")
            if is_tuple(v.t):
                for i in range(len(targs(v.t))):
                    pos.append(self.vnode(self.tget(v, i)))
            elif printing and (is_list(v.t) or v.t == "str" or is_dict(v.t) or v.t == RANGEC):
                # print(*xs): its items printed as arguments are, joined by sep (a sole star's
                # items as they are once the keywords are evaluated, others' as they are now)
                xs = v if sole else self.as_list(v, "print") if not is_list(v.t) else self.expr(mk("listcomp", "", a.line, [mk("name", "__pys_item", a.line, []), made_var("__pys_item", a.line), self.vnode(v)]), "")
                item = made_var("__pys_item", a.line)
                pos.append(mk("starred", "", a.line, [mk("listcomp", "", a.line, [mk("call", "", a.line, [mk("name", "str", a.line, []), item]), item, self.vnode(xs)])]))
            else:
                self.err(f"unpacking a {typestr(v.t)} into the arguments of {who if who != '' else 'a function'} is not supported (a tuple's items are)")
        else:
            pos.append(a if pure_arg(a) else self.vnode(self.expr(a, aw)))
    ka = [a for a in args if a.kind == "kw" or a.kind == "dstar"]
    for ai in range(len(ka)):
        a = ka[ai]
        if a.kind == "kw":
            kws.append(a if pure_arg(a.kids[0]) else mk("kw", a.s, a.line, [self.vnode(self.expr(a.kids[0], aw))]))
        elif a.kind == "dstar" and a.kids[0].kind == "dict" and len([i for i in range(0, len(a.kids[0].kids), 2) if a.kids[0].kids[i].kind != "str"]) == 0:
            d = a.kids[0]
            pack: list[Node] = []
            for i in range(0, len(d.kids), 2):
                # A dict display evaluates every value, but repeated keys replace their value
                # at the first key's position. Only a duplicate across mappings is a call error.
                item = mk("kw", d.kids[i].s, a.line, [self.vnode(self.expr(d.kids[i + 1], aw))])
                names = [k.s for k in pack]
                if item.s in names:
                    pack[names.index(item.s)] = item
                else:
                    pack.append(item)
            kws = kws + pack
        elif a.kind == "dstar":
            v = self.expr(a.kids[0], "")
            if not is_kw(v.t) and is_dict(v.t) and targs(v.t)[0] == "str" and n.kids[0].kind == "name" and self.aliases.get(n.kids[0].s, "") == "dataclasses.replace" and len(pos) == 1:
                self.refl_replace_changes(pos[0], v)  # (#489's named rejection: reflection.py)
            if not is_kw(v.t):
                self.err(f"** of a {typestr(v.t)} is not supported: of a function's **kwargs, or a dict display with str keys, it is")
            names = kw_names(v.t)
            for i in range(len(names)):
                kws.append(mk("kw", names[i], a.line, [self.vnode(self.tget(self.kw_tuple(v), i))]))
        if dynamic and (a.kind == "dstar" or ai + 1 == len(ka) or ka[ai + 1].kind == "dstar"):
            # CPython merges each ** mapping, or group of explicit keywords, before evaluating
            # the next group. A duplicate raises now, after this whole mapping's values ran.
            names = [k.s for k in kws]
            if len([j for j in range(len(names)) if names[j] in names[:j]]) > 0:
                if dynh.v != "":
                    return self.dyn_method_found(receiver, f.s, pos + kws, dynh)
                return self.call(mk("call", n.s, n.line, [f] + pos + kws), want, resultsoft, typeargs)
    out = pos + kws
    if printing and len([a for a in out if a.kind == "starred"]) > 0:
        return self.print_star(n, out)
    if dynh.v != "":
        return self.dyn_method_found(receiver, f.s, out, dynh)
    return self.call(mk("call", n.s, n.line, [f] + out), want, resultsoft, typeargs)

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
    if is_fn(t) or is_callable(unopt(t)) or unopt(t) == "exctype" or t == "dyn":
        return
    if short(name) in PYBUILTINS or t == "":
        self.err(f"'{name}' is a variable, so it cannot be called")
    if t not in self.classes or "__call__" not in self.classes[t].methods:
        self.err(f"'{tname(unopt(t))}' object is not callable")

def gen_obj_call(self, o: Val, args: list[Node], want: str, resultsoft: bool = False) -> Val:
    # o(args), o already evaluated: a call of the function o is (is_fn), or o.__call__(args) where
    # o's class defines it, else CPython's TypeError; an o that is None raises its TypeError once
    # the arguments are evaluated
    if is_fn(o.t):
        return self.call_value(o, args, want, resultsoft)
    if is_callable(unopt(o.t)):
        return self.call_callable(o, args)
    if o.t == "dyn":
        return self.dyn_call_value(o, args)  # (the function its box holds: dynamic.py)
    if unopt(o.t) == "exctype":
        return self.exc_call(o, args)  # (an exception class's class object: an object of its class)
    if o.t not in self.classes or "__call__" not in self.classes[o.t].methods:
        self.err(f"'{tname(unopt(o.t))}' object is not callable")
    if self.cached_wrapper(o.t):
        return self.call_cache(o, args, want, resultsoft)
    return self.call_fn(self.classes[o.t].methods["__call__"], [o], args, want, "TypeError: 'NoneType' object is not callable", resultsoft=resultsoft)

def gen_cached_wrapper(self, t: str) -> bool:
    # Only the bundled functools wrapper uses this calling convention. Its generic
    # __wrapped__ field retains the exact function type, including names and defaults.
    return t in self.classes and self.classes[t].mod == "functools" and short(self.classes[t].origin) == "_lru_cache_wrapper"

def gen_call_cache(self, o: Val, args: list[Node], want: str, resultsoft: bool = False) -> Val:
    t = self.classes[o.t].ftypes["__wrapped__"]
    if t.startswith("fn[c:"):
        # The env is read after the arguments, before defaults are loaded (call_fn).
        return self.call_fn(self.closures[int(t[5 : t.find(":", 5)])].f, [Val("null", "env")], args, want, "", o, resultsoft=resultsoft)
    if t.startswith("fn[f:"):
        return self.call_fn(self.funcs[t[5:-1]], [], args, want, "", o, resultsoft=resultsoft)
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
            d = Data("callable", g)
            d.refs = [code, "null"]
            self.consts.append(d)
        return Val(g, t)
    o = self.rt("pys_alloc", "ptr", ["i64 16"])
    self.mstore('%ptr', code, o)
    self.mstore('%ptr', v.v, self.maddr('%ptr', f'{o}', '1', True))
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
        value = self.coerce(self.expr(args[j], ts[j + 1]), ts[j + 1], f"argument {j + 1} of a {typestr(ct)}")
        if dynamic_program() and numeric_identity(value.t):
            # A pre-evaluated vnode can also feed a sibling branch. Keep this call's
            # snapshot on its own Val, rather than publishing branch-local SSA there.
            captured = Val(value.v, value.t).identity(value)
            captured.idfrom = self.dyn_box(value).v
            value = captured
        vals.append(value)
    o = self.unwrap(o, "TypeError: 'NoneType' object is not callable")
    code = self.mload('%ptr', o.v)
    env = self.mload('%ptr', self.maddr('%ptr', f'{o.v}', '1', True))
    c = Ins("icall", ts[0], "")
    c.a = [Val(code, "env"), Val(env, "env")] + vals
    idresult = ""
    if dynamic_program():
        c.a.extend([self.dyn_box(v) for v in vals if numeric_identity(v.t)])
        if numeric_identity(ts[0]):
            idresult = self.alloca("dyn", "")
            self.mem_store(Val(idresult, "*dyn"), Val("null", "dyn"))
            c.a.append(Val(idresult, "*dyn"))
    if ts[0] == "None":
        self.add(c)
        return Val("null", "None")
    self.put(c, 1)
    result = Val(f"%t{c.r[0]}", ts[0])
    if idresult != "" and numeric_identity(ts[0]):
        result.idexact = result.t == "int" or result.t == "float"
        result.idslot = idresult
        result.idheld = self.mem_load(Val(idresult, "*dyn")).v
        result.idcounter = self.alloca("int", "")
        result.idversion = "0"
    return result

def gen_call_value(self, v: Val, args: list[Node], want: str, resultsoft: bool = False) -> Val:
    # a call through function value v (is_fn): the call of the function it is, as if called by
    # its name there (the function a module's own name binds: a builtin that the program binds
    # is still the builtin)
    k = v.t[3:-1]
    if k.startswith("u:"):
        return self.unbound_call(k[2 : k.find(".")], k[k.find(".") + 1 :], args, "" if resultsoft else want)
    if k.startswith("m:"):
        return self.method(Val(v.v, k[2 : k.rfind(".")]), k[k.rfind(".") + 1 :], args, want, resultsoft)  # (a bound method: o.name(args))
    if k.startswith("d:"):
        mn = k[2 : k.find(":", 2)]
        return self.method(Val(v.v, k[k.find(":", 2) + 1 :]), mn, args, want if (mn == "keys" or mn == "values" or mn == "items") and not resultsoft else "")
    if k.startswith("b:"):
        return self.builtin(k[2:], args, want, resultsoft)
    if k.startswith("c:"):
        # a closure: its function takes its env first
        return self.call_fn(self.closures[int(k[2 : k.find(":", 2)])].f, [Val(v.v, "env")], args, want, resultsoft=resultsoft)
    return self.call_fn(self.funcs[k[2:]], [], args, want, resultsoft=resultsoft)

def gen_bound(self, s: str) -> bool:
    # a builtin's name that the program binds (a local, def, class or module-level variable)
    return s in self.ltype or s in self.funcs or s in self.classes or s in self.mvars

def gen_ffi_at(self, n: Node) -> bool:
    # whether n calls ffi.at (from ffi import at too), which only an argument of a call of an
    # @extern function may (call_fn, at_arg)
    if n.kind != "call":
        return False
    c = n.kids[0]
    if c.kind == "name":
        return c.s not in self.ltype and c.s not in self.funcs and c.s not in self.gtypes and self.aliases.get(c.s, "") == "ffi.at"
    return c.kind == "attr" and self.dotted(c) == "ffi.at"

def gen_at_arg(self, n: Node, f: FnInfo, j: int, offs: dict[int, Val]) -> Val:
    # ffi.at(xs, k) passed for parameter j of @extern function f: xs, a list f takes as its items,
    # from index k (in offs[j]), which the call checks once the other arguments are evaluated.
    # First, as call does for a name it calls, whether ffi.at is bound where it runs: an import
    # that has not run yet (modchk), a local assigned later (read_ahead) or a global (gflag)
    c = n.kids[0]
    self.modchk(c)
    if c.kind == "name":
        self.read_ahead(c.s)
        if (c.chk or self.foreign(c.s)) and c.s in self.gflag:
            bad = self.scalar('xor', [Val(self.mload('bool', f'@g.{c.s}.def'), 'bool'), Val('true', 'bool')])
            self.guard(bad, self.unbound(c.s))
    if not is_list(f.ptypes[j]):
        self.err(f"ffi.at() passes a list from an index, but parameter '{f.params[j]}' of {f.name}() takes no list")
    if len(n.kids) != 3 or len([a for a in n.kids[1:] if a.kind == "kw" or a.kind == "starred" or a.kind == "dstar"]) > 0:
        self.err("ffi.at() takes a list and an index: ffi.at(xs, k)")
    xs = self.pcoerce(self.expr(n.kids[1], f.ptypes[j]), f.ptypes[j], f, j)
    k = self.expr(n.kids[2], "int")
    if k.t != "int" and k.t != "bool":
        self.err(f"ffi.at() takes an int index, not {typestr(k.t)}")
    offs[j] = self.as_int(k)
    return xs

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
        self.err("binary files are not supported (files read and write str)")
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
        self.guard(self.scalar_cmp('eq', Val(nones[j], '%ptr'), Val('null', '%ptr')), nmsg[j])
    return Val(self.rt("pys_open", "ptr", [f"ptr {vals['file']}", f"ptr {vals['mode']}", f"ptr {vals['encoding']}", f"ptr {vals['newline']}",
                                           f"i64 {vals['buffering']}"]), "file")

def gen_method(self, o: Val, m: str, args: list[Node], want: str = "", resultsoft: bool = False) -> Val:
    if (m == "keys" or m == "values" or m == "items") and len(args) == 0 and want != "" and not resultsoft and is_dict(unopt(o.t)):
        # (the new list of a dict's keys, values or items, which a typed list expected of it takes
        # with its items unboxed where the dict holds boxes, as list(d) does: typed_list; not where
        # want is only a hint, a comparison's other operand's type: resultsoft)
        return self.typed_list(gen_method(self, o, m, args, "", resultsoft), want)
    if o.t == "fn[b:bytes]" and m == "maketrans":
        return self.bytes_method(o, m, args)  # (the static method, of the class)
    if o.t == "fn[b:bytes]" and m == "fromhex":
        # bytes.fromhex(s), the class method, of a str
        if len(args) != 1 or args[0].kind in ["kw", "starred", "dstar"]:
            self.err("bytes.fromhex() takes exactly one positional argument")
        s = self.unwrap(self.expr(args[0], "str"), "TypeError: fromhex() argument must be str, not None")
        if s.t != "str":
            self.err(f"fromhex() argument must be str, not {tname(s.t)}")
        return Val(self.rt("pys_bytes_fromhex", "ptr", [f"ptr {s.v}"]), "bytes")
    if (o.t == "fn[b:str]" or o.t == "fn[b:list]" or o.t == "fn[b:dict]") and (has_method(o.t[5:-1], m) or (o.t == "fn[b:str]" and (m == "format" or m == "format_map"))):
        return self.unbound_call(o.t[5:-1], m, args, "" if resultsoft else want)
    if is_kw(o.t):
        return self.kw_method(o, m, args)
    if o.t == "dyn":
        return self.dyn_method(o, m, args)  # (its box's type's: dynamic.py)
    if is_opt(o.t):
        o = self.unwrap(o, f"AttributeError: 'NoneType' object has no attribute '{m}'")
    if is_union(o.t):
        return self.umethod(o, m, args)
    if (o.t in self.nts or self.literal_class(o.t)) and m == "__init__":
        # p.__init__(args) of a NamedTuple or operator getter (also as a value): object.__init__,
        # as tuple.__new__ set the fields. It takes any arguments where the class has a __new__
        # of its own, and does nothing, also on None. The __init__ that makes the object is the
        # compiler's (see nt_class), which only construction and _replace() call. Operator's
        # C getters likewise initialize through __new__; reinitialization must not mutate
        # fields whose literal values the compiler has specialized.
        for a in args:
            x = a.kids[0] if a.kind == "kw" else a
            if not pure_arg(x):
                self.expr(x, "")
        return Val("null", "None")
    if o.t in self.classes and opaque_class(self.classes[o.t], self.libdir) and m == "__init__":
        # r.__init__(obj) of a weak reference: CPython's __new__ made it, and its __init__ checks
        # the arguments (an object, and a callback) and leaves the reference as it was; a mapping
        # proxy's __init__ is object's, which takes any arguments, as its __new__ made it
        weak = self.classes[o.t].mod == "_weakref"
        if weak and len([a for a in args if a.kind == "kw"]) > 0:
            self.err("ref() takes no keyword arguments")
        if len([a for a in args if a.kind == "starred" or a.kind == "dstar"]) > 0:
            self.err(f"star arguments of __init__() of a {'weak reference' if weak else short(o.t)} are not supported")
        if weak and (len(args) == 0 or len(args) > 2):
            self.err(f"__init__ expected {'at least 1 argument' if len(args) == 0 else 'at most 2 arguments'}, got {len(args)}")
        for a in args:
            x = a.kids[0] if a.kind == "kw" else a
            if not pure_arg(x):
                self.expr(x, "")
        return Val("null", "None")
    if (o.t == "exc" or (o.t in self.classes and self.classes[o.t].exc != "")) and (m == "__str__" or m == "__repr__") and len(args) == 0 and not self.curfn.ll.startswith("@x."):
        # e.__str__() is str(e): that of the class of e's object, which may derive from o.t's
        # (but for the ExcClass's own functions, see exc_helpers)
        return self.to_str(o) if m == "__str__" else self.repr(o)
    if is_gen(o.t):
        return self.gen_method(o, m, args)
    if o.t in self.classes and m == "__init__" and self.classes[o.t].exc != "":
        for c in self.classes.values():
            if c.name != o.t and self.derives(c.name, o.t) and "__init__" in c.methods and c.methods["__init__"].cls == c.name:
                self.err(f"a call of __init__ on an object of {short(o.t)} is not supported where {short(c.name)}, deriving from it, defines __init__ again (calls are not dispatched on the object's class)")
    if o.t in self.classes:
        ci = self.classes[o.t]
        if m == "__call__" and self.cached_wrapper(o.t):
            self.notnone(o, "AttributeError: 'NoneType' object has no attribute '__call__'")
            return self.call_cache(o, args, want, resultsoft)
        if m not in ci.methods and ci.exc != "" and m in HASATTR["any"].split() + ["add_note", "with_traceback"]:
            self.err(f"{short(o.t)} has no method {m}() of its own, and BaseException.{m}() is not supported" + (" (call super().__init__(...) in __init__)" if m == "__init__" else ""))
        if m not in ci.methods and m in ci.ftypes:
            self.fn_attr_read(o, m)
            self.glue_field(o, m)
            return self.obj_call(self.getfield(o, self.field(o, m), m), args, want, resultsoft)  # (o.f(args) of a field f)
        if m not in ci.methods and not ((m == "_replace" or m == "_asdict" or m == "_make" or m == "index" or m == "count") and o.t in self.nts):
            self.err(f"'{shown(o.t)}' object has no method '{m}'")  # (a specialization's is its class's)
        self.notnone(o, f"AttributeError: 'NoneType' object has no attribute '{m}'")
        if m == "_asdict" and m not in ci.methods:
            return self.asdict(o, args)
        if m == "_make" and m not in ci.methods:
            return self.nt_make(ci.origin if ci.origin != "" else o.t, args, want)  # (a class method)
        if (m == "index" or m == "count") and m not in ci.methods:
            return self.tmethod(self.ntup(o, True), m, args)  # (tuple's, of its fields)
        if m not in ci.methods:
            return self.replace(o, args)
        if ci.methods[m].iters:
            self.err(f"calling {short(o.t)}.{m}() is not supported (its iterator is the list it steps through here): iterate over the object")
        if ci.methods[m].prop:
            return self.obj_call(self.call_fn(ci.methods[m], [o], []), args, "")
        self.cls_bound(ci.methods[m], o.t, True)
        # Only user calls consume the result context; builtin methods retain their
        # normal argument contexts, including when forwarding an open empty result.
        return self.call_fn(ci.methods[m], [o] if ci.methods[m].deco == "" else [], args, want, resultsoft=resultsoft)  # (a static or class method gets no o)
    return self.bmethod(o, m, args)

def gen_unbound_call(self, tn: str, m: str, args: list[Node], want: str = "") -> Val:
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
    # (want: the typed list expected of a dict's keys(), values() or items(), as o.keys() takes it)
    return self.method(o, m, rest, want if m == "keys" or m == "values" or m == "items" else "")

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
    if m == "get" and 1 <= len(args) <= 2 and len([a for a in args if a.kind != "kw" and a.kind != "starred"]) == len(args) and (len(names) == 0 or len([x for x in kw_types(o.t) if x != kw_types(o.t)[0]]) > 0):
        # get(k, default) of values of different types (or none): the value of the name k is,
        # of their union with the default's, or the default
        k = self.expr(args[0], "str")
        dv = self.expr(args[1], "") if len(args) == 2 else Val("null", "None")
        if k.t != "str":
            self.err(f"get() of a {typestr(k.t)} key of a {typestr(o.t)} is not supported: its keys are str")
        return self.pick(self.kw_tuple(o), [self.cmp2("==", k, Val(self.sconst(x), "str")) for x in names], "", "", f"get() of a {typestr(o.t)} with a variable key", "", dv)
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
    if t == "fn[b:str]" and (name == "format" or name == "format_map"):
        self.err(f'str.{name} as a value is not supported: call it, "...".{name}(...) or str.{name}("...", ...) of a string literal (map() takes "...".{name})')
    if t in self.classes:
        ci = self.classes[t]
        if name in ci.ftypes or name not in ci.methods:
            return Val("", "")
        f = ci.methods[name]
        if f.prop:
            self.notnone(o, f"AttributeError: 'NoneType' object has no attribute '{name}'")
            return self.call_fn(f, [o], [])
        if f.deco != "":
            self.err(f"{'a static' if f.deco == 'staticmethod' else 'a class'} method as a value ({short(t)}.{name}) is not supported: call it")
        if f.iters:
            self.err(f"{short(t)}.{name} as a value is not supported (its iterator is the list it steps through here): iterate over the object")
        if not (t in self.nts and name == "__init__"):  # (object.__init__, which None has too: method())
            self.notnone(o, f"AttributeError: 'NoneType' object has no attribute '{name}'")
        return Val(o.v, f"fn[m:{t}.{name}]")
    base = "list" if is_list(t) else "dict" if is_dict(t) else "frozenset" if is_fset(t) else "set" if is_set(t) else t
    if has_method(base, name) and (t == "str" or t == "file" or is_list(t) or is_dict(t) or is_set(t)):
        o = self.unwrap(o, f"AttributeError: 'NoneType' object has no attribute '{name}'")
        return Val(o.v, f"fn[d:{name}:{t}]")
    return Val("", "")

def gen_replace(self, o: Val, args: list[Node]) -> Val:
    # p._replace(f=v, ...): a new NamedTuple with the fields given, and p's others; of
    # namedtuple()'s class template, of the specialization their types pick
    ci = self.classes[o.t]
    given: dict[str, Val] = {}
    npos = len([a for a in args if a.kind != "kw"])
    for a in args:
        if a.kind != "kw":
            self.err(f"{short(o.t)}._replace() takes 1 positional argument but {npos + 1} were given")
    bad = [a.s for a in args if a.s not in ci.ftypes]
    if len(bad) > 0:
        self.err("Got unexpected field names: [" + ", ".join([f"'{x}'" for x in bad]) + "]")
    for a in args:
        given[a.s] = self.expr(a.kids[0], ci.ftypes[a.s], resultsoft=ci.origin in self.cnts)
    if ci.origin in self.cnts:
        return self.nt_new(ci.origin, [given[fl] if fl in given else self.getfield(o, self.field(o, fl), fl) for fl in ci.fields], "")
    vals: list[Val] = [self.new_obj(o.t)]
    for fl in ci.fields:
        vals.append(given[fl] if fl in given else self.getfield(o, self.field(o, fl), fl))
    self.call_fn(ci.methods["__init__"], vals, [])
    return vals[0]

def gen_nt_new(self, c: str, vals: list[Val], want: str) -> Val:
    # an object of NamedTuple class c whose fields hold vals, which its __init__ assigns: of the
    # specialization their types pick where namedtuple() made c, a class template
    args = [self.vnode(v) for v in vals]
    if c in self.tmpl:
        made = [Val("", c)]
        self.call_fn(self.classes[c].methods["__init__"], made, args, want)
        return made[0]
    o = self.new_obj(c)
    self.call_fn(self.classes[c].methods["__init__"], [o], args, direct=True)
    return o

def gen_nt_make(self, c: str, args: list[Node], want: str) -> Val:
    # C._make(iterable) of NamedTuple class C (also through an object of C): an object of C whose
    # fields are the iterable's items, which must be as many as its fields, else CPython's
    # TypeError (tuple.__new__ takes them all, then _make counts them; defaults are not used)
    n = len(self.nt_fields(c))
    pos = [a for a in args if a.kind != "kw"]
    for a in args:
        if a.kind == "starred" or a.kind == "dstar":
            self.err(f"{short(c)}._make() with * or ** arguments is not supported")
        if a.kind == "kw" and (a.s != "iterable" or len(pos) > 0):
            self.err(f"{short(c)}._make() got an unexpected keyword argument '{a.s}'" if a.s != "iterable" else f"{short(c)}._make() got multiple values for argument 'iterable'")
    if len(args) != 1:
        self.err(f"{short(c)}._make() missing 1 required positional argument: 'iterable'" if len(args) == 0 else f"{short(c)}._make() takes 2 positional arguments but {len(args) + 1} were given")
    v = self.expr(args[0].kids[0] if args[0].kind == "kw" else args[0], "")
    if v.t in self.nts:
        v = self.ntup(self.unwrap(v, "TypeError: 'NoneType' object is not iterable"), True)
    if is_tuple(v.t):
        if len(targs(v.t)) != n:
            k = len(targs(v.t))
            self.err(f"{short(c)}._make() of a tuple of {k} item{'s' if k != 1 else ''} is not supported: it raises TypeError: Expected {n} arguments, got {k}")
        return self.nt_new(c, [self.tget(v, i) for i in range(n)], want)
    if not is_list(v.t):
        v = self.builtin("list", [self.vnode(v)], "")
    v = self.unwrap(v, "TypeError: 'NoneType' object is not iterable")
    ln = self.mload("int", v.v)
    ok = self.label()
    bad = self.label()
    self.cbr(self.num_cmp("==", Val(ln, "int"), Val(str(n), "int")).v, ok, bad)
    self.place(bad)
    self.raise_("TypeError", self.concat([Val(self.sconst(f"Expected {n} arguments, got "), "str"), self.to_str(Val(ln, "int"))]).v)
    self.place(ok)
    return self.nt_new(c, [self.list_item(v, Val(str(i), "int")) if self.list_id_kind(v.t) != 0 else self.from_slot(self.list_slot(v, str(i)), elem(v.t)) for i in range(n)], want)

def gen_dc_replace(self, args: list[Node]) -> Val:
    # dataclasses.replace(obj, **changes): a new object of obj's class, which its __init__ makes
    # from the changes (each passed, as CPython passes them) and the values of obj's other
    # init=True fields, read in field order
    npos = len([a for a in args if a.kind != "kw"])
    if len([a for a in args if a.kind == "starred" or a.kind == "dstar"]) > 0:
        self.err("star arguments are not supported")
    if npos != 1 or args[0].kind == "kw":
        self.err("replace() missing 1 required positional argument: 'obj'" if npos == 0 else f"replace() takes 1 positional argument but {npos} were given")
    o = self.expr(args[0], "")
    if not self.is_dc(o.t) or o.t in self.nts:
        self.err(f"replace() should be called on dataclass instances, not {tname(o.t)}")
    ci = self.classes[o.t]
    given: dict[str, Val] = {}
    for a in args[1:]:
        if a.s in ci.fopts and "no-init" in ci.fopts[a.s]:
            self.err(f"field {a.s} is declared with init=False, it cannot be specified with replace()")
        given[a.s] = self.expr(a.kids[0], ci.ftypes.get(a.s, ""))
    self.notnone(o, "TypeError: replace() should be called on dataclass instances")
    # (an object of a subclass: the subclass's __init__, also given its own fields)
    cs = [c for c in self.classes.values() if c.tag > 0 and self.derives(c.name, o.t)] if ci.tag > 0 else [ci]
    tag = self.mload('int', o.v) if len(cs) > 1 else ""
    end = self.label() if len(cs) > 1 else ""
    ph = Ins("phi", o.t, "")
    r = o
    for i in range(len(cs)):
        c = cs[i]
        nxt = self.label() if i + 1 < len(cs) else ""
        if nxt != "":
            arm = self.label()
            self.cbr(self.num_cmp('==', Val(tag, "int"), Val(str(c.tag), "int")).v, arm, nxt)
            self.place(arm)
        x = Val(o.v, c.name)
        kws: list[Node] = []
        for k in given:
            kws.append(mk("kw", k, self.line, [self.vnode(given[k])]))
        for fl in self.dc_fields(c):
            if "no-init" not in c.fopts[fl] and fl not in given:
                kws.append(mk("kw", fl, self.line, [self.vnode(self.getfield(x, self.field(x, fl), fl))]))
        r = self.new_obj(c.name)
        self.init_result(self.call_fn(c.methods["__init__"], [r], kws, direct=True))
        if end != "" and not self.term:
            self.incoming(ph, r.v, self.cur)
            self.br(end)
        if nxt != "":
            self.place(nxt)
    if end == "":
        return r
    self.place(end)
    if len(ph.a) == 0:
        self.unreachable()
        return Val("null", o.t)
    return Val(self.phi(ph), o.t)

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
    dt = self.ctype("dict", ["str", vt])
    kv = targs(dt)  # (["dyn", "dyn"] where the values are Any values or containers, which a dict of them holds as boxes, keys too: ctype)
    r = self.rt("pys_dict_new_atomic" if atomic_dict(dt) else "pys_dict_new", "ptr", [f"i64 {self.key_kind(kv[0], True)}", f"i64 {len(ci.fields)}"])
    for fl in ci.fields:
        v = self.coerce(self.getfield(o, self.field(o, fl), fl), kv[1])
        self.rt("pys_dict_set", "void", [f"ptr {r}", "i64 " + self.to_slot(self.store_key(Val(self.sconst(fl), "str"), kv[0])), "i64 " + self.to_slot(v)], self.key_fx(kv[0]))
    return Val(r, dt)

def gen_init_result(self, v: Val) -> None:
    # Construction requires None from __init__, after its side effects and exceptions. An
    # explicit call of the method (including super().__init__) may return any value instead.
    # Ordinary initializers emit no extra IR; a call that never returns has no value to check.
    if v.t == "None" or self.term:
        return
    v = Val(v.v, self.rec_type(v.t))
    if v.t == "dyn":
        bad = self.label()
        end = self.label()
        self.cbr(self.cmp2("is", v, Val("null", "None")).v, end, bad)
        self.place(bad)
        msg = self.concat([Val(self.sconst("__init__() should return None, not '"), "str"), self.dyn_type_name(v), Val(self.sconst("'"), "str")])
        self.raise_("TypeError", msg.v)
        self.place(end)
        return
    # The actual type of a union member or returned subclass belongs in the error. Reuse
    # reflection's guarded split, including its None arm, without requiring every value's
    # type to support type(x).__name__ (functions, generators and files need only tname).
    leaves = self.refl_split(v)
    end = ""
    for leaf in leaves:
        self.place(leaf.label)
        if leaf.c == "None":
            end = self.label()
            self.br(end)
        elif leaf.c == "exc" or (leaf.c in self.classes and self.classes[leaf.c].exc != ""):
            name = self.refl_type_attr(self.vnode(leaf.v), "__name__")
            msg = self.concat([Val(self.sconst("__init__() should return None, not '"), "str"), name, Val(self.sconst("'"), "str")])
            self.raise_("TypeError", msg.v)
        else:
            self.raise_("TypeError", self.sconst(f"__init__() should return None, not '{tname(leaf.c)}'"))
    if end != "":
        self.place(end)

def gen_new_obj(self, c: str) -> Val:
    # a new object of class c, which its __init__ initializes: it holds its class-body defaults
    # (but where @dataclass wrote __init__, which assigns every field itself)
    o = self.alloc_fixed(c)
    self.nn[o.v] = True
    if self.classes[c].tag > 0:
        self.mstore('int', f'{self.classes[c].tag}', o.v)
    if not (self.is_dc(c) and "no-init" not in self.classes[c].dcopts and self.classes[c].methods["__init__"].node.kids[0].kind == "noann"):
        line = self.line
        self.class_defaults(o)
        self.line = line
    return o

def gen_pcoerce(self, v: Val, t: str, f: FnInfo, j: int) -> Val:
    # argument j of f for a parameter of type t ("": a template's unannotated parameter takes any type)
    what = ""
    if is_opt(v.t):
        what = f"argument {j if takes_self(f) else j + 1} of {short(f.name)}()" if j < f.npos else f"argument '{f.params[j]}' of {short(f.name)}()"
    if identity_abi(f) and numeric_identity(v.t) and numeric_identity(t) and (not f.scalar_args or f.params[j] in f.idnames):
        captured = Val(v.v, v.t).identity(v)
        captured.idfrom = self.dyn_box(v).v
        v = captured
    value = self.coerce(v, t, what) if t != "" else v
    if identity_abi(f) and numeric_identity(value.t) and (not f.scalar_args or f.params[j] in f.idnames):
        # Capture now, before a later argument can rebind the original local or cell.
        result = Val(value.v, value.t).identity(value)
        result.idfrom = self.dyn_box(value).v
        return result
    return value

def gen_virtual_call(self, f: FnInfo, pre: list[Val], args: list[Node], want: str, none: str, resultsoft: bool = False) -> Val:
    # Closed-world dispatch, before argument binding: an override owns its defaults. Each
    # selected body is a normal method-template instance, specialized for the concrete self.
    o = pre[0]
    cs = [c for c in self.classes.values() if c.tag > 0 and self.derives(c.name, o.t)]
    if len(cs) == 1:
        return self.call_fn(cs[0].methods[f.name], pre, args, want, none, direct=True, resultsoft=resultsoft)
    # Evaluate explicit arguments once, before reading the receiver tag (also for a None
    # callable). Defaults remain inside the selected branch. Overrides have the same typed
    # parameter interface; an unannotated argument is specialized from its value.
    bound: list[Node] = []
    pos = len(pre)
    for a in args:
        j = f.params.index(a.s) if a.kind == "kw" and a.s in f.params else pos
        t = f.ptypes[j] if j < len(f.ptypes) and j != f.vararg and j != f.kwarg else ""
        value = self.expr(a.kids[0] if a.kind == "kw" else a, t)
        if dynamic_program() and numeric_identity(value.t):
            captured = Val(value.v, value.t).identity(value)
            captured.idfrom = self.dyn_box(value).v
            value = captured
        argnode = self.vnode(value)
        bound.append(mk("kw", a.s, a.line, [argnode]) if a.kind == "kw" else argnode)
        if a.kind != "kw":
            pos += 1
    self.notnone(o, none if none != "" else f"AttributeError: 'NoneType' object has no attribute '{f.name}'")
    tag = self.mload('int', o.v)
    end = self.label()
    vals: list[Val] = []
    edges: list[str] = []
    narrow = dict(self.narrowed)
    for i in range(len(cs)):
        c = cs[i]
        nxt = self.label() if i + 1 < len(cs) else ""
        if nxt != "":
            arm = self.label()
            self.cbr(self.num_cmp('==', Val(tag, "int"), Val(str(c.tag), "int")).v, arm, nxt)
            self.place(arm)
        self.narrowed = dict(narrow)
        v = self.call_fn(c.methods[f.name], [Val(o.v, c.name)] + pre[1:], bound, want, direct=True, resultsoft=resultsoft)
        if not self.term:
            if dynamic_program() and numeric_identity(v.t):
                v.idfrom = self.dyn_box(v).v
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
    result = Val("null", "None") if t == "None" else Val(self.phi(ph), t)
    if dynamic_program() and numeric_identity(t):
        identity = Ins("phi", "dyn", "")
        for i in range(len(vals)):
            # A None/string/bool arm needs no numeric provenance. Its raw payload
            # remains sufficient; the optional/union boxing path handles its tag.
            self.incoming(identity, vals[i].idfrom if vals[i].idfrom != "" else "null", edges[i])
        held = self.phi(identity)
        result.idslot = self.alloca("dyn", "")
        self.mem_store(Val(result.idslot, "*dyn"), Val(held, "dyn"))
        result.idheld = held
        result.idcounter = self.alloca("int", "")
        result.idversion = "0"
    return result

def gen_scalar_call_types(self, f: FnInfo, args: list[Node]) -> list[str]:
    # A complete, inert numeric call can specialize before evaluating its arguments.
    # That lets the scalar None-body proof discard their boxes before pcoerce snapshots
    # them. Unknown types or effectful arguments must keep those early snapshots.
    if not identity_abi(f) or not f.generic or f.cls != "" or f.clo >= 0 or f.gen or f.vararg >= 0 or f.kwarg >= 0 or f.ret not in ["", "None"] or len(args) != len(f.params) or len(f.node.kids) != 3:
        return []
    ts = ["" for p in f.params]
    pos = 0
    for a in args:
        j = f.params.index(a.s) if a.kind == "kw" else pos
        e = a.kids[0] if a.kind == "kw" else a
        if a.kind != "kw":
            pos += 1
        t = e.kind if e.kind in ["int", "float"] else "bool" if e.kind in ["True", "False"] else self.static_type(e) if e.kind == "name" else self.vnodes[int(e.s)].t if e.kind == "val" else ""
        if t not in ["int", "float", "bool"] or (f.ptypes[j] != "" and f.ptypes[j] != t):
            return []
        ts[j] = t
    if any(t == "" for t in ts):
        return []
    names: dict[str, bool] = {}
    body = f.node.kids[2].kids
    local_names(body, names)
    for p in f.params:
        names[p] = True
    blocked: dict[str, bool] = {}
    for nm in ["int", "float", "bool", "range", "print"]:
        if nm in self.mvars or nm in self.gtypes or nm in self.funcs or nm in self.classes or nm in self.aliases or nm in self.fglobals:
            blocked[nm] = True
    return ts if all(numeric_statement(n, names, blocked, True, True) for n in body) else []


def gen_call_fn(self, f: FnInfo, pre: list[Val], args: list[Node], want: str = "", none: str = "", cache: Val | None = None, direct: bool = False, resultsoft: bool = False, typeargs: str = "") -> Val:
    # f(pre + args); none: the error where pre[0], an object called (o(args)), is None
    if f.pyexport:
        self.err(f"{f.name}() is @export, so Pystachy code may not call it (under CPython each call goes through the export's checks and conversions): call a private function that both use")
    if f.bad != "":
        self.err(f.bad)  # (before its arguments, whose types may be placeholders')
    if identity_abi(f) and len(f.node.kids) == 3:
        self.numeric_proof(f, f.node.kids[2].kids)
    if f.cls in self.classes and self.classes[f.cls].tag > 0 and f.deco == "" and len(pre) > 0:
        if pre[0].t not in self.classes or not self.derives(pre[0].t, f.cls):
            self.err(f"{short(f.cls)}.{f.name}() needs an instance of {short(f.cls)}")
        if not direct:
            return self.virtual_call(f, pre, args, want, none, resultsoft)
    if f.ll not in self.called and f.ll in self.lazyat:
        hpush(self.wake, self.lazyat[f.ll])
    self.called[f.ll] = True
    self.arity(f, len(pre), args)
    if len(pre) == 0 and cache is None:
        scalar_types = self.scalar_call_types(f, args)
        if len(scalar_types) > 0:
            f = self.instance(f, scalar_types, [])
    line = self.line
    np = len(f.params)
    vals: list[Val] = []
    # A surrounding annotation is a storage contract; C[T](...) alone only hints
    # at unbound or conflicting arguments. Keep both through unpacked calls.
    # C(...) of a generic class that a lambda returns is a forwarding call: the Callable's
    # result type binds C's type variables, as lambda: defaultdict(int) takes them (see instance)
    ctx = self.curfn.rctx if want == "?" and f.name == "__init__" and len(pre) > 0 and pre[0].v == "" and f.cls in self.tparams else want
    contract = f.cls in self.tparams and len(self.want_tvars(f.cls, ctx)) > 0
    context = ctx if contract or typeargs == "" else typeargs
    hint = self.want_params(f.cls, context) if f.name == "__init__" and len(pre) > 0 and pre[0].v == "" and f.cls in self.tparams else []
    for i in range(np):
        vals.append(self.pcoerce(pre[i], f.ptypes[i], f, i) if i < len(pre) else Val("", ""))
    pos = len(pre)
    extra: list[Val] = []
    kwn: list[str] = []
    kwv: list[Val] = []
    offs: dict[int, Val] = {}  # (the index of each list that an @extern call takes as ffi.at(xs, k))
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
        if f.extern and self.ffi_at(e):
            vals[j] = self.at_arg(e, f, j, offs)
            continue
        vals[j] = self.pcoerce(self.expr(e, f.ptypes[j] if f.ptypes[j] != "" or j >= len(hint) else self.generic_hint(e, hint[j])), f.ptypes[j], f, j)
        if self.curfn.cmpops and self.term and vals[j].v == "undef":
            return Val("undef", want if want not in ["", "?"] else f.ret if f.ret != "" else "int")
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
    facs: list[int] = []  # (the parameters whose default is a dataclass field's default_factory)
    for j in range(np):
        if vals[j].t == "":
            t = f.ptypes[j]
            if df.dglob[j] == "" and (not is_const(f.defaults[j]) or identity_default(f.defaults[j])):
                self.early_default(df, j)
            if df.dglob[j].startswith("!"):
                self.err(df.dglob[j][1:])
            if df.dglob[j] == "=None":
                vals[j] = Val("null", "None")
            elif df.dglob[j] == "()":
                facs.append(j)
            elif df.dglob[j].startswith("&"):
                # a closure's default: in its env (pre[0]), evaluated where it was defined
                t = t if t != "" else df.dtypes[j]
                da = self.maddr('int', pre[0].v, f'{df.dglob[j][1:]}', True)
                vals[j] = Val(self.mload(t, da), t)
                if dynamic_program() and numeric_identity(t):
                    closure = self.closures[f.clo]
                    ba = self.maddr('%ptr', pre[0].v, str(int(df.dglob[j][1:]) + len(closure.defs) + len(closure.iflags)), True)
                    vals[j].idfrom = self.mload('dyn', ba)
            elif df.dglob[j] != "":
                t = t if t != "" else df.dtypes[j]
                vals[j] = Val(self.mload(t, df.dglob[j]), t)
                if dynamic_program() and numeric_identity(t):
                    vals[j].idfrom = self.mload('dyn', df.dglob[j] + '.box')
            else:
                vals[j] = self.pcoerce(self.expr(f.defaults[j], t), t, f, j)
    for fl in self.dc_fields(self.classes[f.cls]) if len(facs) > 0 else []:
        # a dataclass field's default_factory, called for each object (see dc_factory), after
        # the other defaults, which only read globals, in field order (see declare_fields)
        for j in facs:
            if f.params[j] == fl or f.params[j] == fl + ".factory":
                vals[j] = self.call_fn(self.classes[f.cls].methods[fl + ".factory"], [], [])
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
        return self.call_fn(self.classes[cache.t].methods["_call"], [cache], forwarded, want, resultsoft=resultsoft)
    if f.name == "__init__" and len(pre) > 0 and pre[0].v == "" and f.cls in self.tmpl:
        # C(args) of a class template C: its arguments' types decide the specialization the
        # object belongs to (see specialize), whose __init__ initializes it
        if len(hint) > 0:
            inferred: dict[str, str] = {}
            conflict = False
            for j in range(1, len(hint)):
                if self.match(f.node.kids[0].kids[j].kids[0], vals[j].t, inferred, self.tparams[f.cls]) != "":
                    conflict = True
                    break
            targets = [j for j in range(1, len(hint)) if is_union(unopt(hint[j])) or is_opt(hint[j])]
            fits = all([self.widens(vals[j].t, hint[j]) or (self.boxes(vals[j].t, hint[j]) and (not is_opt(vals[j].t) or self.optional(hint[j]) == hint[j])) for j in targets])
            if (conflict or contract) and fits:
                # Check the complete candidate before changing any value. A nested
                # invariant argument can still conflict; report its original types.
                candidate: dict[str, str] = {}
                for j in range(1, len(hint)):
                    t = hint[j] if j in targets else vals[j].t
                    if self.match(f.node.kids[0].kids[j].kids[0], t, candidate, self.tparams[f.cls]) != "":
                        fits = False
                        break
            if (conflict or contract) and fits:
                # A destination needs its named union storage even for homogeneous values.
                # Explicit type arguments alone still preserve consistent inferred types;
                # no existing mutable container is reinterpreted as a wider member type.
                for j in targets:
                    vals[j] = self.pcoerce(vals[j], hint[j], f, j)
        elif f.cls in self.tparams:
            union_args = self.constructor_unions(f.cls, [v.t for v in vals[1:]])
            for j in range(len(union_args)):
                vals[j + 1] = self.pcoerce(vals[j + 1], union_args[j], f, j + 1)
        sc = self.specialize(f.cls, [v.t for v in vals[1:]], self.want_tvars(f.cls, context), False, self.literal_args(f, args) if self.literal_class(f.cls) else {})
        vals[0] = self.new_obj(sc)
        pre[0] = vals[0]
        f = self.classes[sc].methods["__init__"]
    if f.generic:
        nnp: list[str] = []
        for j in range(np):
            if vals[j].t in self.classes and vals[j].v in self.nn and self.dispatches(f, f.params[j]):
                nnp.append(f.params[j])
        # A direct return-call keeps the open-result marker for an empty callee,
        # while forwarding the caller's separate fresh-display context.
        f = self.instance(f, [v.t for v in vals], nnp, self.curfn.rctx if want == "?" else want, self.curfn.rsoft if want == "?" else resultsoft)
    c = Ins("call", f.ret, f.ll)
    c.a = [v for v in vals if v.t != "None"]  # (an argument that is None is not passed)
    idresult = ""
    if identity_abi(f):
        c.a.extend([self.dyn_box(vals[j]) if not f.scalar_args or f.params[j] in f.idnames else Val("null", "dyn") for j in range(np) if numeric_identity(f.ptypes[j])])
        if numeric_identity(f.ret):
            idresult = self.alloca("dyn", "")
            self.mem_store(Val(idresult, "*dyn"), Val("null", "dyn"))
            c.a.append(Val(idresult, "*dyn"))
    if len(offs) > 0:
        # a list as ffi.at(xs, k): the stub that takes an index after the arguments for each list
        # (0 for one passed as it is), which it checks as the call starts (cextern)
        if f.ll + ".at" not in self.externs:
            self.cextern(f, True)
            self.line = line
        c = Ins("call", f.ret, f.ll + ".at")
        c.a = [v for v in vals if v.t != "None"] + [offs[j] if j in offs else Val("0", "int") for j in range(np) if is_list(f.ptypes[j])]
    if f.noret:
        # it never returns: the code after the call is not reached, and the call's value has the
        # type its context expects (return fail("bad") in a function returning int)
        self.add(c)
        self.unreachable()
        t = want if want != "" and "?" not in want else "None"
        return Val("0" if t == "int" else fbits("0.0") if t == "float" else "false" if t == "bool" else "null", t)
    if f.ret == "None":
        self.add(c)
        v = Val("null", "None")
        if f.infer and f.ll in self.building:
            v.infer_from = short(f.name)
        return v
    if f.ll in self.guessed and f.ll != self.curfn.ll:
        self.guessed[self.curfn.ll] = self.guessed[f.ll]  # (what it returns may hold a guess)
    self.put(c, 1)
    self.gencall = f"%t{c.r[0]}" if f.gen else ""  # (a new generator: a loop over it owns it, see owned_gen)
    self.gencallf = f if f.gen else None
    if "?" in f.ret:
        # f returns an open empty result: its own, or also that of the call cycle's functions
        # it returns unchanged (qchain), one of which may have its type now: f returns it too
        chain = self.qchain(f)
        known = ""
        for g in chain:
            if known == "" and g.ret != "" and "?" not in g.ret:
                v = self.typed_empty(Val(f"%t{c.r[0]}", f.ret), g.ret, f)
                if v.t != g.ret:
                    self.err(f"cannot infer what {short(f.name)}() returns: it returns what {short(g.name)}() does, {typestr(g.ret)}; annotate its return type")
                known = g.ret
        if known == "":
            v = self.typed_empty(Val(f"%t{c.r[0]}", f.ret), want, f)
        if "?" not in v.t:
            # A recursive call may already consume a concrete layout. Later
            # inference can adopt exactly that layout, never a different one.
            # One that forwards the result still open (return a(n)) consumes none.
            for g in chain:
                if g.ll in self.building:
                    old = self.qused.get(g.ll, v.t)
                    self.qused[g.ll] = v.t if old == v.t else "?"
        return v
    result = Val(f"%t{c.r[0]}", f.ret)
    if idresult != "" and numeric_identity(f.ret):
        result.idexact = result.t == "int" or result.t == "float"
        result.idslot = idresult
        result.idheld = self.mem_load(Val(idresult, "*dyn")).v
        result.idcounter = self.alloca("int", "")
        result.idversion = "0"
    return result

def gen_fname(self, f: FnInfo) -> str:
    # f as CPython's errors about a call's arguments name it, by its qualified name: a
    # NamedTuple's is P.__new__
    if f.name == "__init__" and f.cls in self.nts:
        return f"{short(f.cls)}.__new__"
    return f"{short(f.cls)}.{f.name}" if f.cls != "" else short(f.name)

def gen_arity(self, f: FnInfo, npre: int, args: list[Node]) -> None:
    # CPython's TypeError for a call of f whose arguments do not fit its parameters (arity_error)
    e = self.arity_error(f, npre, args)
    if e != "":
        self.err(e)

def gen_arity_error(self, f: FnInfo, npre: int, args: list[Node]) -> str:
    # CPython's TypeError for a call of f whose arguments do not fit its parameters, in the order
    # its frame setup finds them: a keyword that names no parameter (or a positional-only one)
    # or one already given, too many positional arguments, then the missing positional and
    # keyword-only ones; npre values (the object of a method) come before args; "" where they fit
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
                return f"{self.fname(f)}() got some positional-only arguments passed as keyword arguments: '{', '.join(po)}'"
            return f"{self.fname(f)}() got an unexpected keyword argument '{a.s}'"
        if filled[j]:
            return f"{self.fname(f)}() got multiple values for argument '{a.s}'"
        filled[j] = True
    off = 1 if f.deco == "classmethod" else -1 if f.clo >= 0 else 0  # (cls, which CPython counts and f.params leaves out; a closure's env, the reverse)
    if f.vararg < 0 and given > last:
        if f.name == "__init__" and f.node.kids[0].kind == "noann" and (not self.is_dc(f.cls) or "no-init" in self.classes[f.cls].dcopts):
            return f"{short(f.cls)}() takes no arguments"
        dflt = len([j for j in range(last) if f.defaults[j].kind != "noann"])
        kwg = len([j for j in range(last, np) if filled[j]])
        takes = f"from {last + off - dflt} to {last + off}" if dflt > 0 else str(last + off)
        plural = "s" if dflt > 0 or last + off != 1 else ""
        kwonly = f" positional argument{'s' if given + off != 1 else ''} (and {kwg} keyword-only argument{'s' if kwg != 1 else ''})" if kwg > 0 else ""
        return f"{self.fname(f)}() takes {takes} positional argument{plural} but {given + off}{kwonly} {'was' if given + off == 1 and kwg == 0 else 'were'} given"
    if f.vartup != "" and given >= f.vararg and given - f.vararg != len(targs(f.vartup)):
        # *args: *Ts, which a generic class's specialization binds: as many as Ts has types
        n = f.vararg + len(targs(f.vartup)) + off
        return f"{self.fname(f)}() takes {n} positional argument{'s' if n != 1 else ''} but {given + off} {'was' if given + off == 1 else 'were'} given (its *{f.params[f.vararg]} is a {typestr(f.vartup)})"
    for kind in ["positional", "keyword-only"]:
        miss = [f.params[j] for j in range(np) if not filled[j] and f.defaults[j].kind == "noann" and j != f.vararg and j != f.kwarg and (j < last) == (kind == "positional")]
        if len(miss) > 0:
            names = "'" + "', '".join(miss) + "'"
            if len(miss) == 2:
                names = f"'{miss[0]}' and '{miss[1]}'"
            elif len(miss) > 2:
                names = "'" + "', '".join(miss[:-1]) + f"', and '{miss[-1]}'"
            return f"{self.fname(f)}() missing {len(miss)} required {kind} argument{'s' if len(miss) != 1 else ''}: {names}"
    return ""

def gen_kw_type(self, f: FnInfo, name: str) -> str:
    # the type call_fn evaluates keyword argument name of a call of f with: its parameter's, or
    # that of the values f's **kwargs takes where the name goes there ("" where it fits no
    # parameter, which arity reports)
    j = f.params.index(name) if name in f.params else -1
    if f.kwarg >= 0 and (j < 0 or j < f.posonly or j == f.kwarg or j == f.vararg):
        return f.kwelem
    return f.ptypes[j] if j >= 0 else ""

def gen_dispatches(self, f: FnInfo, p: str) -> bool:
    # does template f test its parameter p with isinstance(p, ...), hasattr(p, ...), getattr(p,
    # name, default), type(p) or p is (not) None (or p == None, see static), and never assign it: then an object known not to
    # be None decides the tests
    asg: dict[str, bool] = {}
    local_names(f.node.kids[2].kids, asg)
    return p not in asg and self.tests(f.node.kids[2].kids, p)

def gen_tests(self, ns: list[Node], p: str) -> bool:
    # (see dispatches)
    for n in ns:
        if n.kind == "call" and n.kids[0].kind == "name" and (n.kids[0].s == "isinstance" or n.kids[0].s == "hasattr") and len(n.kids) == 3 and n.kids[1].kind == "name" and n.kids[1].s == p:
            return True
        if n.kind == "call" and n.kids[0].kind == "name" and ((n.kids[0].s == "getattr" and len(n.kids) == 4) or (n.kids[0].s == "type" and len(n.kids) == 2)) and n.kids[1].kind == "name" and n.kids[1].s == p:
            return True  # (getattr(p, name, default) and type(p): reflection.py)
        x = nonetest(n)
        if x >= 0 and n.kids[x].kind == "name" and n.kids[x].s == p:
            return True
        if self.tests(n.kids, p):
            return True
    return False

def gen_getattr_name(self, n: Node) -> str:
    # n is getattr(o, name) with a str literal name (or a constant one, in a class that
    # specializes on literals): that name; else ""
    if n.kind != "call" or len(n.kids) != 3 or n.kids[0].kind != "name" or n.kids[0].s != "getattr" or self.bound("getattr") or n.kids[1].kind in ["kw", "starred"] or n.kids[2].kind in ["kw", "starred"]:
        return ""
    if n.kids[2].kind == "attr" and n.kids[2].s == "name" and n.kids[2].kids[0].kind == "dcfield":
        return n.kids[2].kids[0].s  # (f.name of a dataclasses.Field: reflection.py)
    c = self.const_of(n.kids[2], {}, True) if self.lit_context() else n.kids[2] if n.kids[2].kind == "str" else None
    return c.s if c is not None and c.kind == "str" and c.s != "" else ""
