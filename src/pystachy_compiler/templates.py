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
from src.pystachy_compiler.syntax import Node, mentions, mk
from src.pystachy_compiler.utils import (
    elem,
    is_callable,
    is_dict,
    is_list,
    is_set,
    is_tuple,
    kw_types,
    nones,
    selem,
    takes_self,
    targs,
    typestr,
    unopt,
)


def gen_specialize(self, c: str, ts: list[str], given: dict[str, str], named: bool) -> str:
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
    doing = c + ("[" if named else "(") + ",".join(ts) + ")"
    doing += "".join([f";{x}={given[x]}" for x in self.tparams.get(c, []) if x in given])
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
    s.slots = t.slots
    s.slotlimit = t.slotlimit
    s.fields = [x for x in t.fields]  # (its class attributes, which its specializations share)
    for x in t.fields:
        s.fpos[x] = t.fpos[x]
        s.ftypes[x] = t.ftypes[x]
    if "__slots__" in t.ftypes:
        s.ftypes["__slots__"] = t.ftypes["__slots__"]
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
        s.tvars = self.bind(c, ts, given)  # (before its fields, which its type variables may type)
    if named:
        fi.ptypes = [name] + self.named_params(c, init.node)
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

def gen_bind(self, c: str, ts: list[str], given: dict[str, str]) -> dict[str, str]:
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
        if x not in tv and x in given:
            tv[x] = given[x]
        if x not in tv:
            self.err(f"{short(c)}() does not bind its type variable '{short(x)}': no argument's type gives it; name it where the object goes (q: {short(c)}[int] = {short(c)}(...), a field or a parameter annotated so) or in the call ({short(c)}[int](...))")
    return tv

def gen_want_tvars(self, c: str, want: str) -> dict[str, str]:
    # the bindings of generic class c's type variables that the context of a call c(...) names,
    # where it expects one of c's specializations (x: c[int] = c(), see generic_ann); else none
    w = unopt(want)
    if c in self.tparams and w in self.classes and self.classes[w].origin == c:
        return dict(self.classes[w].tvars)
    return {}

def gen_constructor_unions(self, c: str, ts: list[str]) -> list[str]:
    # Ordinary matching wins. On conflicting direct scalar TypeVars only, use
    # their closed union and box arguments before specializing the constructor.
    ps = self.classes[c].methods["__init__"].node.kids[0].kids[1:]
    tvs = self.tparams[c]
    inferred: dict[str, str] = {}
    conflict = False
    for i in range(len(ts)):
        if self.match(ps[i].kids[0], ts[i], inferred, tvs) != "":
            conflict = True
            break
    if not conflict:
        return []
    names: list[str] = []
    bound: dict[str, str] = {}
    for i in range(len(ts)):
        a = ps[i].kids[0]
        if a.kind == "str":
            a = self.parse_expr(a.s)
        name = ""
        if self.names_tv(a, tvs):
            if ps[i].kind != "param" or a.kind != "name" or a.s not in tvs or a.s in self.tvtuples:
                return []
            name = a.s
            if name not in bound:
                bound[name] = ts[i]
            elif bound[name] != ts[i]:
                scalars = all([unopt(t) in ["int", "float", "bool", "str", "None"] or self.scalar_union(t) for t in [bound[name], ts[i]]])
                joined = self.join(bound[name], ts[i]) if bound[name] != "None" and ts[i] != "None" else ""
                if not scalars and joined == "":
                    return []
                bound[name] = self.union_type([bound[name], ts[i]]) if scalars else joined
        names.append(name)
    if any([t == "None" for t in bound.values()]):
        return []  # (a TypeVar still needs at least one non-None binding)
    return [bound[names[i]] if names[i] != "" else ts[i] for i in range(len(ts))]

def gen_want_params(self, c: str, want: str) -> list[str]:
    # the types for which the arguments of c(...), a call of generic class c whose context
    # expects its specialization want, are compiled: __init__'s annotations that name c's type
    # variables, bound as in want (an Iterable[T] taken as a list[T]); "" for the others
    w = unopt(want)
    if c not in self.tparams or w not in self.classes or self.classes[w].origin != c:
        return []
    sel = self.selfcls
    self.selfcls = w  # (c's type variables are bound as in want, see tvar)
    out = [""]  # (self's)
    for p in self.classes[c].methods["__init__"].node.kids[0].kids[1:]:
        a = p.kids[0]
        t = ""
        if p.kind == "param" and a.kind != "noann" and self.names_tv(a, self.tparams[c]):
            if a.kind == "index" and (a.kids[0].kind == "name" or a.kids[0].kind == "attr") and self.ann_base(a.kids[0]) in ("iterable", "iterator"):
                t = self.ann(a.kids[1])
                t = self.ctype("list", [t]) if not t.startswith("!") else ""
            else:
                t = self.ann(a)
        out.append("" if t.startswith("!") else t)
    self.selfcls = sel
    return out

def gen_generic_hint(self, e: Node, t: str) -> str:
    # Infer a nonempty argument's own type before using the class context. A
    # display's first non-None item types the later ones, including empty displays.
    # Only an empty first item (or explicit heterogeneous union) needs the hint.
    pending = [e]
    while len(pending) > 0:
        n = pending.pop()
        if n.kind in ["list", "dict"] and nones(n):
            return t
        if n.kind in ["list", "dict", "set"]:
            parts = [n.kids[j] for j in range(1, len(n.kids), 2)] if n.kind == "dict" else n.kids
            if "union[" in t:
                kinds = [x.kind if x.kind in ["int", "float", "str", "None"] else "bool" if x.kind in ["True", "False"] else self.probe_type(x) for x in parts]
                if len(kinds) > 1 and "" not in kinds:
                    joined = kinds[0]
                    for kind in kinds[1:]:
                        joined = self.join(joined, kind)
                        if joined == "":
                            return t
            if n.kind == "dict":
                pending.extend(n.kids[:1])  # (the first key also fixes its type)
            for x in parts:
                if x.kind != "None":
                    pending.append(x)
                    break
        elif n.kind == "tuple":
            pending.extend(n.kids)  # (each field has its own expected type)
        elif n.kind in ["listcomp", "setcomp", "binop"]:
            pending.append(n.kids[0])  # (result body, or the left operand that types the right)
        elif n.kind == "ifexp":
            st = self.static(n.kids[0])
            pending.append(n.kids[2] if st == 0 or (st < 0 and n.kids[1].kind == "None") else n.kids[1])
        elif n.kind == "boolop":
            st = self.static(n.kids[0])
            pending.append(n.kids[1] if (st >= 0 and (st == 1) != (n.s == "or")) or (n.kids[0].kind == "None" and n.s == "or") else n.kids[0])
        # Calls, indices, tests and other operations determine their own operands'
        # types. Empty displays inside them do not receive this expression's hint.
    return ""

def gen_generic_ann(self, c: str, a: Node) -> str:
    # c[X, Y] of generic class c (a subscript of a name, a): the specialization whose type
    # variables are bound to X and Y, which the call c[X, Y](...), or c(...) where its context
    # expects that type, makes objects of; or "!" and why not. Its fields are typed by
    # __init__'s annotations (see named_params)
    tvs = self.tparams[c]
    xs = a.kids if a.kind == "tuple" else [a]
    if "__init__" not in self.classes[c].methods:
        return f"!{short(c)}[...] names a generic class that is declared further down: Pystachy needs its class statement before the annotation (or a generic class with an __init__)"
    if "__class_getitem__" in self.body_names(self.classes[c].node):
        return f"!{short(c)}[...] with a custom __class_getitem__ is not supported"
    if len([x for x in tvs if x in self.tvtuples]) > 0:
        return f"!{short(c)}[...] is not supported for a generic class with a TypeVarTuple: only its calls' arguments bind them"
    if len(xs) != len(tvs):
        return f"!{short(c)}[...] takes {len(tvs)} type{'s' if len(tvs) != 1 else ''} ({', '.join([short(x) for x in tvs])}), not {len(xs)}"
    given: dict[str, str] = {}
    for i in range(len(tvs)):
        t = self.ann(xs[i])
        if t.startswith("!"):
            return t
        given[tvs[i]] = t
    return self.specialize(c, [], given, True)

def gen_named_params(self, c: str, init: Node) -> list[str]:
    # the types of the parameters (after self) of the __init__ of generic class c, as the
    # specialization that c[X] names (see generic_ann) types them, its type variables bound:
    # their annotations, an Iterable[T] (or Iterator[T]) taken as a list[T], for the fields
    # they type
    out: list[str] = []
    for p in init.kids[0].kids[1:]:
        a = p.kids[0]
        if p.kind != "param" or a.kind == "noann":
            self.err(f"{short(c)}[...] needs each parameter of {short(c)}.__init__ annotated, and no *args or **kwargs: '{p.s}' is not")
        if a.kind == "index" and (a.kids[0].kind == "name" or a.kids[0].kind == "attr") and self.ann_base(a.kids[0]) in ("iterable", "iterator"):
            t = self.ann(a.kids[1])
            out.append(t if t.startswith("!") else self.ctype("list", [t]))
        else:
            out.append(self.ann(a))
        if out[-1].startswith("!"):
            self.err(f"{short(c)}[...]: the annotation of {short(c)}.__init__'s parameter '{p.s}': {out[-1][1:]}")
    return out


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
    if (base == "iterable" or base == "iterator") and len(xs) == 1:
        if t == "tuple[]":
            return ""  # (no items bind T; the context can still give it)
        et = self.iter_elem(t)
        return self.match(xs[0], et, tv, tvs) if et != "" else "it has no supported iterable item type"
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
    return "it does not fit the parameter's annotation (or that annotation's type variables are not supported there: they are in T, list[T], dict[K, V], set[T], tuple[T, *Ts], T | None, Iterable[T] and Callable[[T, *Ts], R])"

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

def local_result(body: list[Node], params: list[str]) -> list[str]:
    # A short straight-line chain may forward a fresh result through locals.
    # Each name is assigned once and read only by the next alias or return;
    # no mutation, escape, capture, control flow or parameter is widened.
    if len(body) < 2 or body[-1].kind != "return" or len(body[-1].kids) != 1 or body[-1].kids[0].kind != "name":
        return []
    values: dict[str, Node] = {}
    order: dict[str, int] = {}
    for st in body[:-1]:
        if st.kind == "expr" and st.kids[0].kind == "str":
            continue
        if st.kind != "assign" or len(st.kids) != 2 or st.kids[0].kind != "name":
            return []
        name = st.kids[0].s
        if name in values:
            return []
        order[name] = len(values)
        values[name] = st.kids[1]
    name = body[-1].kids[0].s
    aliases: list[str] = []
    while name in values and name not in params and name not in aliases and len(aliases) < 32:
        aliases.append(name)
        e = values[name]
        if e.kind == "name":
            if e.s not in order or order[e.s] >= order[name]:
                return []
            name = e.s
        elif e.kind in ["call", "list", "dict", "set", "tuple"]:
            for key in values:
                v = values[key]
                if v.kind == "name" and key in aliases:
                    continue
                if mentions(v, aliases):
                    return []
            return aliases
        else:
            return []
    return []


def contextual_result(n: Node) -> bool:
    # Only fresh return displays and direct forwarding calls can use a result
    # hint. Nested functions have their own callers; ordinary stored returns
    # keep one argument-specialized function. A top-level empty list/dict keeps
    # its existing open-result specialization shared between caller layouts.
    if n.kind == "return" and len(n.kids) > 0:
        e = n.kids[0]
        return e.kind in ["tuple", "call"] or (e.kind in ["list", "dict", "set"] and len(e.kids) > 0)
    for k in n.kids:
        if k.kind not in ["def", "class", "subclass", "lambda"] and contextual_result(k):
            return True
    return False

def gen_instance(self, f: FnInfo, ts: list[str], nnp: list[str], want: str = "", resultsoft: bool = False) -> FnInfo:
    # the function template f compiles to for arguments of types ts, compiled when first
    # needed, in the middle of the function that calls it: its first return statement
    # decides what it returns; nnp: the parameters whose objects are known not to be None
    # Only container contexts can type fresh displays. Include the full context
    # in the key and budgets: two callers may require different native storage.
    body = f.orig.kids[2] if f.pending else f.node.kids[2]
    context = f.ret == "" and "?" not in want and ("list[" in want or "dict[" in want or "set[" in want or "tuple[" in want)
    locals = local_result(body.kids, f.params) if context and not resultsoft else []
    want = want if context and (contextual_result(body) or len(locals) > 0) else ""
    key = ",".join(ts) + (" " + ",".join(nnp) if len(nnp) > 0 else "")
    if key in f.insts and f.insts[key].ll in self.building:
        # Recursion into the active argument specialization must retain its
        # inference cycle, including the diagnostic for an open empty result.
        want = ""
    mode = " ~ " if resultsoft else " -> "
    size = len(ts) + len(nnp) + len(want) + (len(mode) if want != "" else 0)
    for t in ts:
        size += len(t)
    for p in nnp:
        size += len(p)
    if size > TEMPLATE_BYTES:
        self.err(f"{short(f.name)}() template signature exceeds {TEMPLATE_BYTES} bytes; annotate its parameters")
    if want != "":
        key += mode + want
    if key in f.insts:
        g = f.insts[key]
        if g.ret == "":
            if f.void_default:
                # These signatures previously returned None. Keep recursive void
                # programs valid, but fix their consumed ABI before emitting a call.
                # The first-return path refuses any later non-None inference.
                g.ret = "None"
            else:
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
    g.prop = f.prop
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
    g.rctx = want
    g.rsoft = resultsoft and want != ""
    g.rlocals = locals if want != "" else []
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
    if ret != "" and g.ret != ret and not (f.name == "__len__" and g.ret == "bool"):
        self.err(f"{f.name} must return {ret}, and {shown(f.cls)}.{f.name}() returns {typestr(g.ret)}")
    self.making.pop()
    self.template_bytes -= size
    return g
