"""Templates component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.diagnostics import shown, where
from src.pystachy_compiler.ir import ClassInfo, FnInfo
from src.pystachy_compiler.names import retoken, short
from src.pystachy_compiler.specs import (
    SPECIAL,
    SPECSHOW,
    TEMPLATE_BYTES,
    TEMPLATE_INSTANCES,
    TEMPLATE_RETAINED,
)
from src.pystachy_compiler.syntax import Node, mk
from src.pystachy_compiler.utils import (
    elem,
    is_callable,
    is_dict,
    is_list,
    is_set,
    is_tuple,
    kw_types,
    selem,
    takes_self,
    targs,
    typestr,
    unopt,
)


def gen_specialize(self, c: str, ts: list[str]) -> str:
    # the specialization of class template c that c(args) makes an object of, for arguments
    # of types ts (its __init__'s, after self, as call_fn has them): the fields its __init__
    # assigns are typed as for a class whose __init__ annotates its parameters with ts, and the
    # calls whose fields get the same types share one. A specialization is a class of its
    # own (c-1, c-2, ...): CPython's names for it are c's, messages about types show its
    # fields' (Box[int]). It counts as a template specialization
    t = self.classes[c]
    init = t.methods["__init__"]
    # (an annotated parameter's argument has its type, as call_fn coerces it)
    ts = [init.ptypes[i + 1] if i + 1 < len(init.ptypes) and init.ptypes[i + 1] != "" else ts[i] for i in range(len(ts))]
    doing = c + "(" + ",".join(ts) + ")"
    if doing in self.specdone:
        # (the same argument types make the same fields: also where templates make objects of
        # each other, A's __init__ making a B whose __init__ makes an A, which gets the A made)
        return self.specdone[doing]
    if doing in self.specing:
        # (its __init__ makes another object of these types, self.next = Node(n - 1): the one
        # being made, as a recursive call of a template is)
        return self.specing[doing]
    if len(self.making) >= 100:
        self.err(f"{short(c)}() needs more than 100 nested template functions; annotate its parameters")
    t.nspec += 1
    name = f"{c}-{t.nspec}"
    self.specing[doing] = name
    s = ClassInfo(name, t.node)
    s.mod = t.mod
    s.origin = c
    s.fields = [x for x in t.fields]  # (its class attributes, which its specializations share)
    for x in t.fields:
        s.fpos[x] = t.fpos[x]
        s.ftypes[x] = t.ftypes[x]
    s.fdefault = t.fdefault
    s.fglob = t.fglob
    self.classes[name] = s
    fi = FnInfo("__init__", init.ll, init.node, name)
    fi.params = init.params
    fi.ptypes = [name] + ts
    fi.mod = init.mod
    args = ", ".join([typestr(x) for x in ts])
    self.making.append(f"specializing {shown(c)}({args}) for the call at {where(self.line)}")
    sel = self.selfcls
    self.selfcls = name  # (c names its specialization in its annotations, see ann)
    line = self.line
    if c in self.tparams:
        s.tvars = self.bind(c, ts)  # (before its fields, which its type variables may type)
    self.scan_fields(s, fi, init.node.kids[2].kids)
    self.line = line
    # (a field that holds the specialization itself, self.next: Node | None, is the same in each)
    key = ",".join([x + ":" + retoken(s.ftypes[x], name, "@") for x in s.fields])
    key += "".join([f";{x}={retoken(s.tvars[x], name, '@')}" for x in self.tparams.get(c, [])])
    del self.specing[doing]
    if key in t.specs:
        del self.classes[name]
        self.selfcls = sel
        self.making.pop()
        self.specdone[doing] = t.specs[key]
        return t.specs[key]
    if s.bad != "":
        self.err(s.bad)  # (an imported module's class: where the program makes an object of it)
    if self.template_instances >= TEMPLATE_INSTANCES:
        self.err(f"compilation needs more than {TEMPLATE_INSTANCES} template specializations; annotate template parameters or reduce type combinations")
    self.template_instances += 1
    t.specs[key] = name
    self.specdone[doing] = name
    shown_ts = [typestr(s.ftypes[x]) for x in s.fields if x not in t.ftypes]
    if c in self.tparams:
        shown_ts = []  # (a generic class's: its type variables', C[int, str])
        for x in self.tparams[c]:
            shown_ts.extend([typestr(y) for y in targs(s.tvars[x])] if x in self.tvtuples else [typestr(s.tvars[x])])
    SPECSHOW[name] = f"{short(c)}[{', '.join(shown_ts)}]"
    for d in t.node.kids[0].kids:
        if d.kind == "def":
            self.line = d.line
            self.lib = s.mod != ""
            s.methods[d.s] = self.declare_fn(d, name)
            self.lib = False
            s.methods[d.s].mod = s.mod
    s.hook = t.hook
    for f in s.methods.values():
        self.check_special(f)
    self.fl_fields(s)
    for f in s.methods.values():
        # the special methods that are no templates, which Pystachy calls implicitly (its
        # others are compiled where they are called, as templates are)
        if not f.generic and f.bad == "" and f.ll not in self.compiled:
            fr = self.save()
            self.modlevel = False
            self.lenient = False
            self.function(f, f.node.kids[2].kids)
            self.restore(fr)
    self.line = line
    self.selfcls = sel
    self.making.pop()
    return name

def gen_names_tv(self, a: Node, tvs: list[str]) -> bool:
    # does annotation a (also as a string) mention one of type variables tvs
    if a.kind == "str":
        a = self.parse_expr(a.s)
    if a.kind == "name" and a.s in tvs:
        return True
    for k in a.kids:
        if self.names_tv(k, tvs):
            return True
    return False

def gen_bind(self, c: str, ts: list[str]) -> dict[str, str]:
    # the types that c(args) binds the type variables of generic class c to, for arguments of
    # types ts (its __init__'s, after self), as a type checker infers C[int] from C(1): each
    # parameter whose annotation mentions them matches its argument's type (see match)
    tvs = self.tparams[c]
    tv: dict[str, str] = {}
    init = [d for d in self.classes[c].node.kids[0].kids if d.kind == "def" and d.s == "__init__"][0]
    ps = init.kids[0].kids
    for i in range(1, min(len(ps), len(ts) + 1)):
        a = ps[i].kids[0]
        if not self.names_tv(a, tvs):
            continue
        t = ts[i - 1]
        if ps[i].kind == "starparam":
            why = self.match_items([a] if a.kind == "starred" else [a] * len(targs(t)), targs(t), tv, tvs)  # (*args: *Ts, or *args: T)
        elif ps[i].kind == "dstarparam":
            why = self.match_items([a] * len(kw_types(t)), kw_types(t), tv, tvs)
        else:
            why = self.match(a, t, tv, tvs)
        if why != "":
            self.err(f"{short(c)}() cannot bind its type variables from the argument for '{ps[i].s}', a {typestr(t)}: {why}")
    for x in tvs:
        if x not in tv:
            self.err(f"{short(c)}() does not bind its type variable '{short(x)}': Pystachy binds a generic class's type variables from the arguments of the call that makes an object (C[int]() is not supported), and no argument's type gives it")
    return tv

def gen_match(self, a: Node, t: str, tv: dict[str, str], tvs: list[str]) -> str:
    # "" if a value of type t fits annotation a, binding (in tv) the type variables of tvs that
    # a mentions; else why not. A part of a that mentions none fits any type: the code that
    # uses the value checks it, as for any other argument
    if a.kind == "str":
        a = self.parse_expr(a.s)
    if not self.names_tv(a, tvs):
        return ""
    if "?" in t:
        return "its type is not known yet (an empty list or dict: annotate it)"
    if a.kind == "name" and a.s in self.tvtuples:
        return f"TypeVarTuple '{short(a.s)}' is only supported unpacked (*{short(a.s)})"
    if a.kind == "name" and t == "None":
        return f"'{short(a.s)}' would be None, which Pystachy binds no type variable to (a list or dict of None values has no type)"
    if a.kind == "name":
        j = self.join(tv[a.s], t) if a.s in tv else t
        if j == "":
            return f"'{short(a.s)}' is {typestr(tv[a.s])} already, and {typestr(t)} here"
        tv[a.s] = j
        return ""
    ms = self.union_members(a, []) if a.kind == "binop" and a.s == "|" else []
    if a.kind == "index" and (a.kids[0].kind == "name" or a.kids[0].kind == "attr") and self.ann_base(a.kids[0]) == "optional":
        ms = [a.kids[1], mk("None", "", a.line, [])]
    if len(ms) == 2 and (ms[0].kind == "None" or ms[1].kind == "None"):
        return "" if t == "None" else self.match(ms[0] if ms[1].kind == "None" else ms[1], unopt(t), tv, tvs)  # (T | None)
    base = self.ann_base(a.kids[0]) if a.kind == "index" and (a.kids[0].kind == "name" or a.kids[0].kind == "attr") else ""
    xs = (a.kids[1].kids if a.kids[1].kind == "tuple" else [a.kids[1]]) if a.kind == "index" else []
    if base == "list" and is_list(t) and len(xs) == 1:
        return self.match(xs[0], elem(t), tv, tvs)
    if (base == "set" or base == "frozenset") and is_set(t) and len(xs) == 1:
        return self.match(xs[0], selem(t), tv, tvs)
    if base == "dict" and is_dict(t) and len(xs) == 2:
        why = self.match(xs[0], targs(t)[0], tv, tvs)
        return why if why != "" else self.match(xs[1], targs(t)[1], tv, tvs)
    if base == "tuple" and is_tuple(t):
        return self.match_items(xs, targs(t), tv, tvs)
    if base == "callable" and len(xs) == 2 and xs[0].kind == "list":
        sig = self.fn_sig(t)
        if sig[0].startswith("!"):
            return sig[0][1:]
        why = self.match_items(xs[0].kids, sig[1:], tv, tvs)
        return why if why != "" else self.match(xs[1], sig[0], tv, tvs)
    return "it does not fit the parameter's annotation (or that annotation's type variables are not supported there: they are in T, list[T], dict[K, V], set[T], tuple[T, *Ts], T | None and Callable[[T, *Ts], R])"

def gen_match_items(self, xs: list[Node], ts: list[str], tv: dict[str, str], tvs: list[str]) -> str:
    # (see match) values of types ts for the items of tuple[...] or the parameters of
    # Callable[[...], R], annotated xs: an unpacked TypeVarTuple (*Ts) takes those the others leave
    k = -1
    for i in range(len(xs)):
        if xs[i].kind == "starred":
            k = i
    if (k < 0 and len(ts) != len(xs)) or len(ts) < len(xs) - 1:
        return f"it has {len(ts)} {'item' if len(ts) == 1 else 'items'} where the annotation has {str(len(xs)) if k < 0 else 'at least ' + str(len(xs) - 1)}"
    after = len(xs) - k - 1 if k >= 0 else 0
    for i in range(len(xs)):
        if i != k:
            why = self.match(xs[i], ts[i] if k < 0 or i < k else ts[len(ts) - len(xs) + i], tv, tvs)
            if why != "":
                return why
    if k < 0:
        return ""
    mid = self.ctype("tuple", ts[k : len(ts) - after])
    x = xs[k].kids[0]
    if x.kind == "name" and x.s in self.tvtuples and x.s in tvs:
        if x.s in tv and tv[x.s] != mid:
            return f"'{short(x.s)}' is {typestr(tv[x.s])} already, and {typestr(mid)} here"
        tv[x.s] = mid
        return ""
    return self.match(x, mid, tv, tvs)  # (*tuple[A, B])

def gen_fn_sig(self, t: str) -> list[str]:
    # the return type and the parameter types of a function value of type t, as Callable[[A, B],
    # R] has them: a def's or lambda's positional parameters (each annotated) and return
    # annotation, a Callable's; or ["!" and why not]
    if is_callable(t):
        return targs(t)
    if t.startswith("fn[f:"):
        f = self.funcs[t[5:-1]]
    elif t.startswith("fn[c:"):
        f = self.closures[int(t[5 : t.find(":", 5)])].f
    else:
        return [f"!a {typestr(t)} is no def, lambda or Callable, whose signature Callable[[...], R] matches"]
    name = "the lambda" if f.node.s == "<lambda>" else f"{short(f.name)}()"
    if f.vararg >= 0 or f.kwarg >= 0:
        return [f"!{name} takes *args or **kwargs, which Callable[[...], R] does not match"]
    out = [f.ret]
    for j in range(1 if f.clo >= 0 else 0, len(f.params)):  # (a closure's env aside)
        if j >= f.npos and f.defaults[j].kind == "noann":
            return [f"!{name} takes the keyword-only parameter '{f.params[j]}', which Callable[[...], R] does not match"]
        if j < f.npos and f.ptypes[j] == "":
            return [f"!{name}'s parameter '{f.params[j]}' has no annotation, which the type variables it matches take their type from"]
        if j < f.npos:
            out.append(f.ptypes[j])
    if f.ret == "":
        return [f"!{name} has no return annotation, which the type variable it matches takes its type from"]
    return out

def gen_instance(self, f: FnInfo, ts: list[str], nnp: list[str]) -> FnInfo:
    # the function template f compiles to for arguments of types ts, compiled when first
    # needed, in the middle of the function that calls it: its first return statement
    # decides what it returns; nnp: the parameters whose objects are known not to be None
    size = len(ts) + len(nnp)
    for t in ts:
        size += len(t)
    for p in nnp:
        size += len(p)
    if size > TEMPLATE_BYTES:
        self.err(f"{short(f.name)}() template signature exceeds {TEMPLATE_BYTES} bytes; annotate its parameters")
    key = ",".join(ts) + (" " + ",".join(nnp) if len(nnp) > 0 else "")
    if key in f.insts:
        g = f.insts[key]
        if g.ret == "":
            self.err(f"cannot infer what {short(f.name)}() returns: it calls itself before a return statement does; annotate its return type")
        if g.ll in self.building:
            self.retseen[g.ll] = True  # (a return of None can no longer make it T | None)
        return g
    if f.bad != "":
        self.err(f.bad)
    if len(self.making) >= 100:
        self.err(f"{short(f.name)}() needs more than 100 nested template functions; annotate its parameters")
    if self.template_bytes + size > TEMPLATE_BYTES:
        self.err(f"active template signatures exceed {TEMPLATE_BYTES} bytes; annotate template parameters")
    if self.template_instances >= TEMPLATE_INSTANCES:
        self.err(f"compilation needs more than {TEMPLATE_INSTANCES} template specializations; annotate template parameters or reduce type combinations")
    who = f"{shown(f.cls) + '.' if f.cls != '' else ''}{shown(f.name)}"
    if self.template_retained + size > TEMPLATE_RETAINED:
        top = ""  # (the template whose instances keep the most)
        for w in self.retainers:
            if top == "" or self.retainers[w] > self.retainers[top]:
                top = w
        self.err(f"retained template signatures exceed {TEMPLATE_RETAINED} bytes, {top}() keeping the most ({self.retainers[top]}); annotate template parameters or reduce type combinations")
    self.materialize(f)  # (an inherited class method's own body)
    g = FnInfo(f.name, f"{f.ll}.{len(f.insts) + 1}", f.node, f.cls)
    g.deco = f.deco
    g.clsuse = f.clsuse
    g.orig = f.orig
    g.iters = f.iters
    g.params = f.params
    g.ptypes = ts
    g.defaults = f.defaults
    g.dglob = f.dglob
    g.dtypes = f.dtypes
    g.uflags = f.uflags
    g.mod = f.mod
    g.ret = f.ret
    g.infer = f.ret == ""
    g.inst = True
    g.npos = f.npos
    g.posonly = f.posonly
    g.vararg = f.vararg
    g.kwarg = f.kwarg
    g.kwelem = f.kwelem
    g.clo = f.clo
    for x in nnp:
        g.nnp[x] = True
    f.insts[key] = g
    self.template_instances += 1
    self.template_retained += size
    self.retainers[who] = self.retainers.get(who, 0) + size
    maybe = [f.params[j] for j in range(len(ts)) if ts[j] in self.classes and f.params[j] not in g.nnp and self.dispatches(f, f.params[j])]
    why = f", where {' and '.join(maybe)} may be None: only a new object or self is known not to be None, which decides isinstance(), hasattr() and 'is None' at compile time" if len(maybe) > 0 else ""
    args = ", ".join(ts[1:] if f.clo >= 0 or takes_self(f) else ts) if size <= 256 else f"<{len(ts)} arguments, {size} type bytes>"  # (a closure's env, a method's self aside)
    self.making.append(f"compiling {who}({args}) for the call at {where(self.line)}{why}")
    self.template_bytes += size
    fr = self.save()
    self.modlevel = False
    self.lenient = False
    self.function(g, f.node.kids[2].kids)
    self.restore(fr)
    ret = SPECIAL[f.name][SPECIAL[f.name].find(":") + 1 :] if f.cls != "" and f.name in SPECIAL else ""
    if ret != "" and g.ret != ret:
        self.err(f"{f.name} must return {ret}, and {shown(f.cls)}.{f.name}() returns {typestr(g.ret)}")
    self.making.pop()
    self.template_bytes -= size
    return g
