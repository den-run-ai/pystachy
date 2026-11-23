"""Templates component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.analysis import local_names, nonlocal_decls, read_names
from src.pystachy_compiler.diagnostics import int_lists, shown, where
from src.pystachy_compiler.dynamic import comparison_aliases, comparison_properties, comparison_rebinds, comparison_reserve_fields
from src.pystachy_compiler.generators import fresh_yield_context
from src.pystachy_compiler.symbols import ClassInfo, FnInfo
from src.pystachy_compiler.names import retoken, short
from src.pystachy_compiler.specs import (
    BIG,
    SPECIAL,
    SPECSHOW,
    TEMPLATE_BYTES,
    TEMPLATE_INSTANCES,
    TEMPLATE_RETAINED,
)
from src.pystachy_compiler.syntax import Node, mentions, mk
from src.pystachy_compiler.unions import ANNTYPES, ann_takes
from src.pystachy_compiler.utils import (
    clone,
    elem,
    gelem,
    int_fits,
    is_callable,
    is_dict,
    is_gen,
    is_list,
    is_opt,
    is_set,
    is_tuple,
    is_union,
    kw_types,
    nones,
    selem,
    takes_self,
    targs,
    typestr,
    umembers,
    unopt,
)


def gen_specialize(self, c: str, ts: list[str], given: dict[str, str], named: bool, lits: dict[str, Node]) -> str:
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
    if int_lists() and c in self.tparams:
        # (in a program where a module opts in to promoting ints, and none to dynamic Any, whose
        # values cannot hold them, an int that binds a type variable of generic class c, by an
        # argument or by an annotation in any module, is a promoting int: its specializations for
        # ints are one class, keyed and laid out so, bigints.py)
        ts = [promoted(ts[i]) if i + 1 >= len(init.ptypes) or init.ptypes[i + 1] == "" else ts[i] for i in range(len(ts))]
        given = {x: promoted(given[x]) for x in given}
    doing = c + ("[" if named else "(") + ",".join(ts) + ")"
    doing += "".join([f";{x}={given[x]}" for x in self.tparams.get(c, []) if x in given])
    doing += "".join([f";{x}={lit_key(lits[x])}" for x in init.params if x in lits])  # (literal_class)
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
    # Request-local context is borrowed, not semantic rollback. Completed
    # classes belong to this Gen; a failed or restarted pass still discards it.
    # Diagnostics copy making before this scope unwinds; observers own CAPTURED.
    owned = [doing]
    sel = self.selfcls
    line = self.line
    lib = self.lib
    depth = len(self.making)
    instances = self.template_instances
    canonical = ""
    try:
        s = ClassInfo(name, t.node)
        s.mod = t.mod
        s.origin = c
        s.speckey = doing
        # Readiness itself can resolve a recursive class-attribute annotation.
        # Every active request must already name a nominal class at that point.
        self.classes[name] = s
        self.declare_fields(t)
        s.fields_ready = t.fields_ready
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
        fi = FnInfo("__init__", init.ll, init.node, name)
        fi.params = init.params
        fi.ptypes = [name] + ts
        fi.mod = init.mod
        args = ", ".join([typestr(x) for x in ts])
        self.making.append(f"specializing {shown(c)}({args}) for the call at {where(self.line)}")
        self.selfcls = name  # (c names its specialization in its annotations, see ann)
        if c in self.tparams:
            s.tvars = self.bind(c, ts, given)  # (before its fields, which its type variables may type)
            if int_lists():
                s.tvars = {x: promoted(s.tvars[x]) for x in s.tvars}  # (as above: an int that an item binds, list[T] of a list[int])
        if named:
            fi.ptypes = [name] + self.named_params(c, init.node)
        elif c in self.tparams:
            # (an argument whose type bind decided later, a lambda, builtin or unannotated def, is
            # the Callable its parameter's annotation names, bound now, as call_fn passes it: also
            # for a field that __init__ stores it in unannotated)
            ps = init.node.kids[0].kids
            for i in range(min(len(ts), len(ps) - 1)):
                a = ps[i + 1].kids[0]
                if ts[i].startswith("fn[") and self.fn_sig(ts[i])[0].startswith("!") and ps[i + 1].kind == "param" and a.kind != "noann" and self.names_tv(a, self.tparams[c]):
                    pt = self.named_param(a)
                    fi.ptypes[i + 1] = pt if not pt.startswith("!") else fi.ptypes[i + 1]
        # A call and an annotation must reserve the same identity before recursive
        # member annotations are scanned. Bindings alone are not a layout key:
        # Iterable[T] can retain a list or tuple, and other parameters can infer fields.
        # Keep constructor types and literal arguments in this second request key.
        if c in self.tparams and t.fields_ready and self.template_instances == instances:
            parts = fi.ptypes[1:] + [s.tvars[x] for x in self.tparams[c]]
            pending = False
            for part in parts:
                for active in self.specing.values():
                    if retoken(part, active, "@") != part:
                        pending = True
            # Resolving a recursive constructor signature may publish a nested class
            # that refers to this placeholder. Leave those requests on the original
            # path; do not discard a placeholder that another specialization can hold.
            if not pending:
                canonical = c + "<" + ",".join(fi.ptypes[1:]) + ">"
                canonical += "".join([f";{x}={s.tvars[x]}" for x in self.tparams[c]])
                canonical += "".join([f";{x}={lit_key(lits[x])}" for x in init.params if x in lits])
                found = self.specdone.get(canonical, self.specing.get(canonical, ""))
                if found != "":
                    del self.classes[name]
                    if canonical in self.specdone:
                        self.specdone[doing] = found
                    return found
                self.specing[canonical] = name
                owned.append(canonical)
        if c in self.cnts:
            self.nts[name] = True  # (namedtuple()'s, whose objects are NamedTuples)
        self.scan_fields(s, fi, init.node.kids[2].kids, {})
        comparison_reserve_fields(self, s)  # late-created specialization, before layout
        if len(lits) > 0:
            s.lits = lits
            self.const_fields(s, init)
        self.line = line
        # (a field that holds the specialization itself, self.next: Node | None, is the same in each)
        key = ",".join([x + ":" + retoken(s.ftypes[x], name, "@") for x in s.fields])
        key += "".join([f";{x}={retoken(s.tvars[x], name, '@')}" for x in self.tparams.get(c, [])])
        key += "".join([f";{x}={lit_key(lits[x])}" for x in init.params if x in lits])  # (its __init__ reads them)
        if key in t.specs:
            del self.classes[name]
            self.nts.pop(name, False)
            # A matching layout can belong to an enclosing request whose methods
            # are still being declared. Only its owner publishes completion.
            if t.specs[key] not in self.specing.values():
                self.specdone[doing] = t.specs[key]
                if canonical != "":
                    self.specdone[canonical] = t.specs[key]
            return t.specs[key]
        if s.bad != "":
            # A needed constructor can fail before a later hierarchy use requests
            # its fixed-layout annotation dependencies. Retain only syntax-verified
            # names and retry the whole program, as for a demanded descendant.
            self.request_hierarchy(c)
            self.err(s.bad)  # (an imported module's class: where the program makes an object of it)
        if self.template_instances >= TEMPLATE_INSTANCES:
            self.err(f"compilation needs more than {TEMPLATE_INSTANCES} template specializations; annotate template parameters or reduce type combinations")
        self.template_instances += 1
        t.specs[key] = name
        shown_ts = [typestr(s.ftypes[x]) for x in s.fields if x not in t.ftypes and x not in s.fextra]
        if c in self.tparams:
            shown_ts = []  # (a generic class's: its type variables', C[int, str])
            for x in self.tparams[c]:
                shown_ts.extend([typestr(y) for y in targs(s.tvars[x])] if x in self.tvtuples else [typestr(s.tvars[x])])
        SPECSHOW[name] = f"{short(c)}[{', '.join(shown_ts)}]"
        if len(lits) > 0:
            # (one of a class that specializes on literals: its arguments, or their types)
            shown_args: list[str] = []
            for j in range(1, len(init.params)):
                x = init.params[j]
                if j == init.vararg and x in lits:
                    shown_args.extend([lit_text(y) for y in lits[x].kids])
                elif j != init.kwarg and (j != init.vararg or ts[j - 1] != "tuple[]"):
                    shown_args.append(lit_text(lits[x]) if x in lits else typestr(ts[j - 1]) if j - 1 < len(ts) else "...")
            SPECSHOW[name] = f"{short(c)}({', '.join(shown_args)})"
        for d in t.node.kids[0].kids:
            if d.kind == "def":
                self.line = d.line
                self.lib = s.mod != ""
                g = self.declare_fn(d, name)
                self.lib = False
                g.mod = s.mod
                s.methods[g.name] = g  # (x.setter: a property's setter)
        s.hook = t.hook
        if c in self.cnts:
            self.dc_methods(s)  # (its __repr__)
        for f in s.methods.values():
            self.check_special(f)
        self.fl_fields(s)
        if self.dyn_policy(s.node.line):
            comparison_properties(s)
        for f in s.methods.values():
            # the special methods that are no templates, which Pystachy calls implicitly (its
            # others are compiled where they are called, as templates are)
            # An annotation can create this class before module globals and flow
            # information are declared. The program's later method pass compiles
            # these early specializations after their declarations are ready, and
            # those of a class whose bare builtin base no fill has typed yet, which
            # the code that makes its objects may store first (builtin_bases.py).
            if self.compiling and not f.generic and f.bad == "" and f.ll not in self.compiled and "?" not in self.bbase(s.name):
                fr = self.save()
                self.modlevel = False
                self.lenient = False
                try:
                    self.function(f, f.node.kids[2].kids)
                finally:
                    self.restore(fr)
        self.specdone[doing] = name
        if canonical != "":
            self.specdone[canonical] = name
        return name
    finally:
        for request in owned:
            self.specing.pop(request, "")
        self.selfcls = sel
        self.line = line
        self.lib = lib
        while len(self.making) > depth:
            self.making.pop()


def promoted(t: str) -> str:
    # what a type variable bound to t is, in a program whose containers hold promoting ints
    # (int_lists): a promoting int for an int (specialize), else t
    return BIG if t == "int" else t

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
    init = self.classes[c].methods["__init__"].node  # (as specialize's: a template has its own)
    ps = init.kids[0].kids
    later: list[int] = []
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
            trial = dict(tv)
            why = self.match(a, t, trial, tvs)
            if why == "":
                tv = trial
            elif t.startswith("fn[") and self.fn_sig(t)[0].startswith("!"):
                # a lambda, a builtin such as int or list, or an unannotated def, whose signature
                # binds nothing: decided once the other arguments have bound theirs
                later.append(i)
                why = ""
        if why != "":
            self.err(f"{short(c)}() cannot bind its type variables from the argument for '{ps[i].s}', a {typestr(t)}: {why}")
    for i in later:
        # (where the other arguments or the context bind the Callable's type variables, its value
        # becomes that Callable where __init__ stores it)
        a = ps[i].kids[0]
        if len([x for x in tvs if x not in tv and x not in given and self.names_tv(a, [x])]) > 0:
            ints = ", ".join([typestr(tv[y]) if y in tv else typestr(given[y]) if y in given else "int" for y in tvs])  # (int: a placeholder)
            # (a private class, such as functools' cache wrapper, is not one a program names)
            hint = "" if short(c).startswith("_") else f"; or name them where the object goes (q: {short(c)}[{ints}] = {short(c)}(...)) or in the call ({short(c)}[{ints}](...))"
            self.err(f"{short(c)}() cannot bind its type variables from the argument for '{ps[i].s}', a {typestr(ts[i - 1])}: {self.match(a, ts[i - 1], dict(tv), tvs)}{hint}")
    for x in tvs:
        if x not in tv and x in given:
            tv[x] = given[x]
        if x not in tv:
            ints = ", ".join([typestr(tv[y]) if y in tv else typestr(given[y]) if y in given else "int" for y in tvs])  # (C[str, int]: the types bound, int for the others)
            self.err(f"{short(c)}() does not bind its type variable '{short(x)}': no argument's type gives it; name it where the object goes (q: {short(c)}[{ints}] = {short(c)}(...), a field or a parameter annotated so) or in the call ({short(c)}[{ints}](...))")
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
        elif n.kind in ["listcomp", "setcomp", "dictcomp", "binop"]:
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
    if c in self.unsupported:
        return "!" + self.unsupported[c]  # (an imported module's class that cannot be declared)
    tvs = self.tparams[c]
    xs = a.kids if a.kind == "tuple" else [a]
    if c in self.tmpl and "__init__" not in self.classes[c].methods:
        return f"!{short(c)}[...] names a generic class that is declared further down: Pystachy needs its class statement before the annotation"
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
    if c not in self.tmpl:
        # (no class template: without an __init__ of its own, or a dataclass, its objects bind
        # nothing and are all c's, as c() makes them; its methods' parameters that name its
        # type variables take each call's types, see declare_fn)
        return c
    return self.specialize(c, [], given, True, {})

def gen_mapping_ann(self, t: str, v: Node) -> str:
    # the type of a local, global or field that an assignment annotated t gives the value v: t,
    # but where t is a dict[K, V] (or a spelling of one, such as Mapping[K, V]: ann_base) and v
    # a call of one of lib/collections' mappings (dict_class), which derive from dict in CPython,
    # that class's specialization whose type variables K and V bind (a Counter's K, where V is
    # its counts' int), as the class's own annotation names it: the variable holds the object
    # that the call makes, which a missing key's lookup asks for its default, as CPython's does
    if not is_dict(t) or v.kind != "call":
        return t
    f = v.kids[0].kids[0] if v.kids[0].kind == "index" else v.kids[0]
    if f.kind != "name" or f.s not in self.tparams or not self.dict_class(f.s):
        return t
    kv = targs(t)
    tvs = self.tparams[f.s]
    if len(tvs) == 2:
        return self.specialize(f.s, [], {tvs[0]: kv[0], tvs[1]: kv[1]}, True, {})
    if kv[1] != "int" and kv[1] != BIG:
        return t  # (a Counter's counts are ints, also where they promote: a dict's int values do then)
    return self.specialize(f.s, [], {tvs[0]: kv[0]}, True, {})

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
        out.append(self.named_param(a))
        if out[-1].startswith("!"):
            self.err(f"{short(c)}[...]: the annotation of {short(c)}.__init__'s parameter '{p.s}': {out[-1][1:]}")
    return out

def gen_named_param(self, a: Node) -> str:
    # (see named_params) the type of a parameter annotated a; of a union that is no type here,
    # such as Iterable[tuple[K, V]] | dict[K, V] (see match), its first member's that is one
    if a.kind == "index" and (a.kids[0].kind == "name" or a.kids[0].kind == "attr") and self.ann_base(a.kids[0]) in ("iterable", "iterator"):
        t = self.ann(a.kids[1])
        return t if t.startswith("!") else self.ctype("list", [t])
    t = self.ann(a)
    u = self.parse_expr(a.s) if a.kind == "str" else a
    if t.startswith("!") and u.kind == "binop" and u.s == "|":
        for m in self.union_members(u, []):
            mt = self.named_param(m) if m.kind != "None" else "!"
            if not mt.startswith("!"):
                return mt
    return t


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
    if len(ms) > 0:
        # A | B: the first member that mentions type variables and fits binds them, an
        # Iterable[...] after the others, as Iterable[tuple[K, V]] | dict[K, V] takes a list of
        # pairs or a dict; else a member that mentions none (which the code that uses the value
        # checks)
        none = len([m for m in ms if m.kind == "None"]) > 0
        if t == "None" and none:
            return ""
        its = [m for m in ms if m.kind == "index" and (m.kids[0].kind == "name" or m.kids[0].kind == "attr") and self.ann_base(m.kids[0]) in ("iterable", "iterator")]
        why = ""
        for m in [m for m in ms if m not in its] + its:
            if m.kind != "None" and self.names_tv(m, tvs):
                trial = dict(tv)
                w = self.match(m, unopt(t) if none else t, trial, tvs)
                if w == "":
                    for x in trial:
                        tv[x] = trial[x]
                    return ""
                why = w if why == "" else why
        return "" if len([m for m in ms if m.kind != "None" and not self.names_tv(m, tvs)]) > 0 else why
    base = self.ann_base(a.kids[0]) if a.kind == "index" and (a.kids[0].kind == "name" or a.kids[0].kind == "attr") else ""
    xs = (a.kids[1].kids if a.kids[1].kind == "tuple" else [a.kids[1]]) if a.kind == "index" else []
    gc = a.kids[0].s if a.kind == "index" and a.kids[0].kind == "name" and a.kids[0].s in self.tparams else ""
    if gc != "" and t in self.classes and self.classes[t].origin == gc and len([x for x in self.tparams[gc] if x in self.tvtuples]) == 0:
        return self.match_items(xs, [self.classes[t].tvars[x] for x in self.tparams[gc]], tv, tvs)  # (C[K, V] of a C object)
    if (base == "iterable" or base == "iterator" or base == "generator") and is_gen(t) and len(xs) >= 1:
        # (a generator, where the annotation is Iterable[T], Iterator[T] or Generator[T, S, R]:
        # what it yields binds T; the rest of Generator[...] binds nothing)
        return self.match(xs[0], gelem(t), tv, tvs)
    if (base == "iterable" or base == "iterator") and len(xs) == 1:
        if t == "tuple[]":
            return ""  # (no items bind T; the context can still give it)
        et = self.iter_elem(t) if t not in self.classes else self.next_type(t)  # (an object's: its iterator's)
        return self.match(xs[0], et, tv, tvs) if et != "" else "it has no supported iterable item type"
    if base == "list" and is_list(t) and len(xs) == 1:
        return self.match(xs[0], elem(t), tv, tvs)
    if (base == "set" or base == "frozenset" or base == "aset") and is_set(t) and len(xs) == 1:
        return self.match_key(xs[0], selem(t), tv, tvs)
    if base == "dict" and is_dict(t) and len(xs) == 2:
        why = self.match_key(xs[0], targs(t)[0], tv, tvs)
        return why if why != "" else self.match(xs[1], targs(t)[1], tv, tvs)
    if base == "tuple" and is_tuple(t):
        return self.match_items(xs, targs(t), tv, tvs)
    if base == "callable" and len(xs) == 2 and xs[0].kind == "list":
        sig = self.fn_sig(t)
        if sig[0].startswith("!"):
            return sig[0][1:]
        why = self.match_items(xs[0].kids, sig[1:], tv, tvs)
        return why if why != "" else self.match(xs[1], sig[0], tv, tvs)
    return "it does not fit the parameter's annotation (or that annotation's type variables are not supported there: they are in T, list[T], dict[K, V], set[T], tuple[T, *Ts], T | None, Iterable[T], Callable[[T, *Ts], R], a generic class's C[T] and unions of these)"

def gen_match_key(self, a: Node, t: str, tv: dict[str, str], tvs: list[str]) -> str:
    # match for the element type of a set, or the key type of a dict: None is one (a set[None]'s,
    # utils.none_key), and binds a type variable as any other type does, where an argument that is
    # None itself binds none (match)
    if a.kind == "str":
        a = self.parse_expr(a.s)
    if t != "None" or a.kind != "name" or not self.names_tv(a, tvs) or a.s in self.tvtuples:
        return self.match(a, t, tv, tvs)
    j = self.join(tv[a.s], t) if a.s in tv else t
    if j == "":
        return f"'{short(a.s)}' is {typestr(tv[a.s])} already, and {typestr(t)} here"
    tv[a.s] = j
    return ""

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
        if j < f.npos and f.ptypes[j] == "" and f.params[j] in f.anys:
            return [f"!{name}'s parameter '{f.params[j]}' is annotated Any, which gives no type to the type variables it matches"]
        if j < f.npos and f.ptypes[j] == "":
            return [f"!{name}'s parameter '{f.params[j]}' has no annotation, which the type variables it matches take their type from"]
        if j < f.npos:
            out.append(f.ptypes[j])
    if f.ret == "" and "" in f.anys:
        return [f"!{name}'s return is annotated Any, which gives no type to the type variable it matches"]
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

def comparison_missing(n: Node, aliases: list[str], fields: dict[str, str]) -> None:
    # The adapter's field/binding proof applies to these reads, including reads
    # captured by nested functions. Carry the proof on a private AST, so nested
    # compilation and retries cannot lose it or leak it to the typed method.
    if n.kind == "attr" and n.kids[0].kind == "name" and n.kids[0].s in aliases and n.s in fields:
        field = n.s
        n.kind = "cmpmissing"
        n.s = fields[field]
        n.kids.append(mk("str", field, n.line, []))
        return
    for kid in n.kids:
        comparison_missing(kid, aliases, fields)


def gen_instance(self, f: FnInfo, ts: list[str], nnp: list[str], want: str = "", resultsoft: bool = False, cmpfields: str = "", nullable_self: bool = False, lits: dict[str, Node] | None = None, fwd: dict[str, str] | None = None, frm: str = "") -> FnInfo:
    # the function template f compiles to for arguments of types ts, compiled when first
    # needed, in the middle of the function that calls it: its first return statement
    # decides what it returns; nnp: the parameters whose objects are known not to be None;
    # lits, fwd and frm: of a template whose literal arguments choose its result, the call's
    # (selector_args), which key an instance of their own
    # Only container contexts can type fresh displays. Include the full context
    # in the key and budgets: two callers may require different native storage.
    # A lambda's Callable result type, a generic class's specialization, types the C(...) it
    # returns (see call_fn): lambda: defaultdict(int) as a defaultdict[str, int]'s factory.
    body = f.orig.kids[2] if f.pending else f.node.kids[2]
    yield_context = not resultsoft and fresh_yield_context(f, want)
    context = f.ret == "" and "?" not in want and ("list[" in want or "dict[" in want or "set[" in want or "tuple[" in want)
    context = context or (f.ret == "" and f.node.s == "<lambda>" and unopt(want) in self.classes and self.classes[unopt(want)].origin in self.tparams)
    locals = local_result(body.kids, f.params) if context and not resultsoft else []
    want = want if yield_context or (context and (contextual_result(body) or len(locals) > 0)) else ""
    cmpops = cmpfields != "" or self.curfn.cmpops
    cmptypes = dict(self.curfn.cmptypes)
    if cmpfields != "":
        actual = self.classes[ts[1]]
        canonical = self.classes[cmpfields]
        readable = list(canonical.ftypes) + [a for a in canonical.methods if canonical.methods[a].prop]
        if any(a not in actual.ftypes and a not in actual.methods for a in readable):
            cmptypes[ts[1]] = cmpfields
    readkey = "".join(" missing " + a + "=" + cmptypes[a] for a in sorted(cmptypes))
    readkey += " runtime-errors" if cmpops else ""
    # Length hints validate the method's result at runtime, after its effects.
    # Keep that specialization separate from typed len(), which requires int.
    raw_hint = f.name == "__len__" and self.curfn.name == "dyn.lengthhint" and self.xtry.startswith("protocol-hint:")
    readkey += " length-hint" if raw_hint else ""
    nullable_self = nullable_self or f.nullable_self
    readkey += " nullable-self" if nullable_self else ""
    chosen: dict[str, Node] = lits if lits is not None else {}
    if len(chosen) > 0:
        # (the literal arguments of its selectors, whose tests the instance decides: selector_const)
        readkey += "".join([f";{p}={lit_key(chosen[p])}" for p in f.params if p in chosen])
    key = ",".join(ts) + (" " + ",".join(nnp) if len(nnp) > 0 else "") + readkey
    if cmpfields != "":
        key += " fields " + cmpfields  # never reuse the ordinary typed call's specialization
    if key in f.insts and f.insts[key].ll in self.building:
        # Recursion into the active argument specialization must retain its
        # inference cycle, including the diagnostic for an open empty result.
        want = ""
    mode = " ~ " if resultsoft else " -> "
    size = len(ts) + len(nnp) + len(want) + len(readkey) + (len(mode) if want != "" else 0) + (len(cmpfields) + 8 if cmpfields != "" else 0)
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
            elif f.gen:
                self.err(f"cannot infer what {short(f.name)}() yields: it calls itself before its first yield; annotate its return type (-> Iterator[T])")
            elif f.ret != "":
                g.ret = f.ret  # (an int for a float parameter, see below: the annotation, -> float)
            elif self.may_decline(f):
                # (a comparison method that names NotImplemented returns that or a bool: a tree's
                # __eq__, whose guard is decided here, compares its children first. The
                # first-return path refuses another type)
                g.ret = "bool"
            else:
                self.err(f"cannot infer what {short(f.name)}() returns: it calls itself before a return statement does; annotate its return type")
        if g.ll in self.building:
            self.retseen[g.ll] = True  # (a return of None can no longer make it T | None)
            if g.ll != self.curfn.ll:
                self.dynseen[g.ll] = True  # (nor compiling it again change what it returns: dyn_again)
        f.lastikey = key
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
    g.nullable_self = nullable_self
    g.prop = f.prop
    g.clsuse = f.clsuse
    g.orig = f.orig
    g.iters = f.iters
    g.gen = f.gen
    g.gret = f.gret
    g.gretinfer = f.gretinfer
    g.gsend = f.gsend
    g.gclose = f.gclose
    g.gwith = f.gwith
    g.gtry = f.gtry
    g.gfirst = f.gfirst
    g.params = f.params
    g.ptypes = ts
    g.defaults = f.defaults
    g.dglob = f.dglob
    g.dtypes = f.dtypes
    g.sentinels = f.sentinels
    g.sentann = f.sentann
    g.uflags = f.uflags
    g.mod = f.mod
    g.home = f.home
    g.ret = want if yield_context else f.ret
    g.infer = f.ret == ""
    if f.tvret != "" and g.ret == "":
        # (accept(visitor) -> T of a visitor whose class derives from Visitor[X]: X, before the
        # body runs, so that a recursive call knows it: tv_bound)
        g.ret = self.tv_bound(f, ts)
        g.infer = g.ret == ""
    g.rctx = "" if yield_context else want
    g.rsoft = resultsoft and want != ""
    g.rlocals = locals if want != "" else []
    g.inst = True
    g.cmpfields = cmpfields
    if cmpfields != "" and ts[0] != ts[1] and comparison_rebinds(f.node.kids[2], f.params[0], f.params[1]):
        g.cmprebind = self.union_type([ts[0], ts[1]])
    g.cmptypes = cmptypes
    g.cmpops = cmpops
    g.lits = chosen
    if fwd is not None:
        g.selfwd = fwd
        g.selfrom = frm
    if cmpfields != "":
        g.node = clone(f.node)
        actual = self.classes[ts[1]]
        missing = {a: self.classes[cmpfields].ftypes[a] for a in self.classes[cmpfields].ftypes if a not in actual.ftypes and a not in actual.methods}
        if g.cmprebind == "":
            comparison_missing(g.node.kids[2], comparison_aliases(g.node.kids[2], f.params[1]), missing)
    late = [j for j in range(len(ts)) if j < len(f.ptypes) and f.ptypes[j] in ANNTYPES and ts[j] != f.ptypes[j] and ann_takes(self, f.ptypes[j], ts[j])]
    if len(late) > 0 and cmpfields == "":
        # an int for a float parameter, an enum member for an int or str one (see ann_param): in
        # this instance's own copy of the def the parameter has no annotation, so its body may
        # bind it again, as a template's
        g.node = clone(f.node)
        for par in g.node.kids[0].kids:
            if par.kind == "param" and par.s in [f.params[j] for j in late]:
                par.kids[0] = mk("noann", "", f.node.line, [])
        if g.ret in ANNTYPES and not f.gen:
            # -> float, -> int or -> str: what this instance returns may be its int or member,
            # which CPython returns as it is; its returns decide (the annotation again, where it
            # calls itself before one)
            g.ret = ""
            g.infer = True
    g.ikey = key
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
    nums = [f.params[j] for j in late if f.ptypes[j] == "float"]
    if len(nums) > 0 and cmpfields == "":
        why += f", which passes an int for the float parameter {' and '.join(nums)}: pass a float, as in 1.0 or float(x), to compile it as annotated"
    for j in late if cmpfields == "" else []:
        if f.ptypes[j] != "float":
            # (an enum member for an int or str parameter: ann_param)
            why += f", which passes a member of {short(ts[j]) if ts[j] in self.classes else typestr(ts[j])} for the {f.ptypes[j]} parameter {f.params[j]}: pass its .value to compile it as annotated"
    args = ", ".join(ts[1:] if f.clo >= 0 or takes_self(f) else ts) if size <= 256 else f"<{len(ts)} arguments, {size} type bytes>"  # (a closure's env, a method's self aside)
    self.making.append(f"compiling {who}({args}) for the call at {where(self.line)}{why}")
    self.template_bytes += size
    fr = self.save()
    self.modlevel = False
    self.lenient = False
    self.function(g, g.node.kids[2].kids)
    self.restore(fr)
    ret = SPECIAL[f.name][SPECIAL[f.name].find(":") + 1 :] if f.cls != "" and f.name in SPECIAL and not raw_hint else ""
    if ret != "" and g.ret != ret and not ((f.name == "__len__" or f.name == "__hash__") and g.ret == "bool") and not (ret == "int" and g.ret == BIG):
        self.err(f"{f.name} must return {ret}, and {shown(f.cls)}.{f.name}() returns {typestr(g.ret)}")
    self.making.pop()
    self.template_bytes -= size
    f.lastikey = key
    return g

# ---- templates whose literal arguments choose what they return
# def repair(s, logging=False) that returns a tuple if logging and a str otherwise: where an
# instance's returns join to no type (statements.py's return), the parameters its tests read that
# literals may give are its selectors (Gen.selectors, kept by the driver's passes: NeedSelectors).
# Each call then compiles an instance for its literal arguments of them (selector_args), whose
# tests of them are decided (selector_const), so that only the returns they reach are compiled:
# repair(" a ") returns a str, repair(" b ", logging=True) a tuple. No other program changes: the
# selectors are found only where compiling it failed otherwise (gen_err).
def gen_selector_key(self, f: FnInfo) -> str:
    # the key of template f (or of an instance of it) in Gen.selectors: its module, its def's line,
    # its class and name, the same in every pass (as fnkey's)
    return f"{f.mod}:{f.node.line}:{self.stable(f.cls)}.{f.name}"


def lit_type(t: str) -> bool:
    # can a parameter of type t take a literal that selects a result: a bool, an int, a str or None,
    # or an optional value or union of those
    if t in ["bool", "int", "str", "None", BIG]:
        return True
    if is_opt(t):
        return lit_type(unopt(t))
    return is_union(t) and all([lit_type(m) for m in umembers(t)])


def scalar_literal(n: Node | None) -> Node | None:
    # n where it is a literal that a selector takes: True, False, None, a str of ASCII characters
    # (the compiler holds a str as its UTF-8 bytes, whose count const_of's len() would give), or an
    # int that fits in 64 bits, negated or not, spelled in decimal (00 and -0 are 0, whose truth is
    # false, as static() reads an int literal's); else None
    if n is None:
        return None
    if n.kind == "True" or n.kind == "False" or n.kind == "None":
        return n
    if n.kind == "str":
        return n if ascii_strs(n) else None
    if n.kind == "int" and int_fits(n.s):
        return mk("int", str(int(n.s)), n.line, [])
    if n.kind == "unary" and n.s == "-" and len(n.kids) == 1 and n.kids[0].kind == "int" and int_fits(n.kids[0].s):
        v = int(n.kids[0].s)  # (fits: -9223372036854775808 is none, whose int() of 9223372036854775808 would not)
        return mk("int", "0", n.line, []) if v == 0 else mk("unary", "-", n.line, [mk("int", str(v), n.line, [])])
    return None


def ascii_strs(n: Node) -> bool:
    # are the str literals in expression n all of ASCII characters, whose len() const_of gives
    # (it counts a str's UTF-8 bytes, as the compiler holds it)
    if n.kind == "str" and not all([ord(ch) < 128 for ch in n.s]):
        return False
    return all([ascii_strs(k) for k in n.kids])


def tested_names(n: Node, out: dict[str, bool]) -> None:
    # the names that the tests in code n read: those of its if, elif and while statements, its
    # assertions and its conditional expressions, but in the defs, lambdas and classes in it
    k = n.kind
    if k == "def" or k == "lambda" or k == "class" or k == "subclass" or k == "lclass":
        return
    if (k == "if" or k == "while" or k == "assert" or k == "ifexp") and len(n.kids) > 0:
        read_names(n.kids[0], out)
    for c in n.kids:
        tested_names(c, out)


def import_names(n: Node, out: dict[str, bool]) -> None:
    # the names that the import statements in code n bind (not in the defs and classes in it)
    if n.kind == "def" or n.kind == "class" or n.kind == "subclass" or n.kind == "lclass":
        return
    if n.kind == "import":
        for a in n.kids:
            out[a.s] = True
    if n.kind == "uimport":
        for nm in n.s.split():
            out[nm] = True
    for c in n.kids:
        import_names(c, out)


def selector_fn(self, f: FnInfo) -> bool:
    # may the instances of instance f's template be keyed by literal arguments: a def's (no
    # lambda's) without a return annotation (Any's, which asks for inference, counts as none) that
    # is no generator, of a module-level or nested function or of an instance method that no class
    # overrides and no call dispatches (its class takes part in no inheritance), but a special
    # method, a property and a comparison's adapter
    if not f.inst or not f.infer or f.gen or f.node.kind != "def" or f.node.s == "<lambda>" or len(f.node.kids) < 3 or f.node.kids[1].kind != "noann":
        return False
    if f.cmpfields != "" or f.cmpops or f.bad != "":
        return False
    if f.cls == "":
        return True
    if (f.name.startswith("__") and f.name.endswith("__")) or f.deco != "" or f.prop or f.acc != "":
        return False
    return f.cls in self.classes and self.classes[f.cls].tag == 0


def stable_params(self, f: FnInfo) -> list[str]:
    # the parameters of instance f that its literal arguments may select by: of a type a literal
    # has (lit_type), which its body never binds again (no assignment, del, import, def, class or
    # nonlocal statement of a def in it), but self, a closure's env, *args, **kwargs and a sentinel's
    body = f.node.kids[2].kids
    bound: dict[str, bool] = {}
    local_names(body, bound)
    for st in body:
        nonlocal_decls(st, bound)
        import_names(st, bound)
    out: list[str] = []
    for j in range(1 if f.clo >= 0 or takes_self(f) else 0, len(f.params)):
        p = f.params[j]
        if j != f.vararg and j != f.kwarg and j < len(f.ptypes) and p not in bound and p not in f.sentinels and lit_type(f.ptypes[j]):
            out.append(p)
    return out


def gen_selector_args(self, f: FnInfo, npre: int, args: list[Node], lits: dict[str, Node], fwd: dict[str, str]) -> str:
    # a call of template f with arguments args (after npre given ones: self, a closure's env), where
    # f's selectors choose its result (Gen.selectors): lits gets the literal argument of each, or its
    # literal default where the call leaves it out (a parameter of the instance being compiled given
    # one is one: forwarding), and fwd the parameter of the calling instance that the call passes
    # for a selector instead, where that instance's own selectors may take it. Returns the calling
    # template's key where fwd has any (else ""). A call with * or ** arguments gives none
    names = self.selectors.get(self.selector_key(f), "").split() if len(self.selectors) > 0 else []
    if len(names) == 0:
        return ""
    given: dict[str, Node] = {}
    pos = npre
    for a in args:
        if a.kind == "starred" or a.kind == "dstar":
            return ""
        if a.kind == "kw":
            # (a positional-only parameter's name, as *args's and **kwargs's, is a **kwargs key:
            # its argument is no parameter's, as call_fn binds it)
            k = f.params.index(a.s) if a.s in f.params else -1
            if k >= f.posonly and k != f.vararg and k != f.kwarg:
                given[a.s] = a.kids[0]
        else:
            if pos < len(f.params) and (f.vararg < 0 or pos < f.vararg):
                given[f.params[pos]] = a
            pos += 1
    env: dict[str, Node] = {}
    for p in self.curfn.lits:
        if p not in self.compvars:
            env[p] = self.curfn.lits[p]
    caller = stable_params(self, self.curfn) if selector_fn(self, self.curfn) else []
    for p in names:
        if p not in f.params:
            continue
        j = f.params.index(p)
        if j == f.vararg or j == f.kwarg:
            continue
        if p in given:
            e = given[p]
            c = scalar_literal(self.const_of(e, env, False)) if ascii_strs(e) else None
            if c is not None:
                lits[p] = c
            elif e.kind == "name" and e.s in caller and e.s not in self.compvars:
                fwd[p] = e.s
        elif j < len(f.defaults) and f.defaults[j].kind != "noann" and ascii_strs(f.defaults[j]):
            c = scalar_literal(self.const_of(f.defaults[j], {}, False))
            if c is not None:
                lits[p] = c
    return self.selector_key(self.curfn) if len(fwd) > 0 else ""


def gen_selector_type(self, t: str, n: Node) -> str:
    # the type of a selector's literal argument n (selector_args) for a parameter of type t: where t
    # is an optional value or a union, the member that n's value has (None of an optional one), as
    # the parameter of the instance for n holds no other value (it never binds it again), so that
    # its uses need no test of it (key is None, in an instance for key=5, does not leave key an
    # int | None); else t
    if not is_opt(t) and not is_union(t):
        return t
    if n.kind == "None":
        return "None" if is_opt(t) else t
    k = "bool" if n.kind == "True" or n.kind == "False" else "str" if n.kind == "str" else "int"
    u = unopt(t)
    ms = umembers(u) if is_union(u) else [u]
    if k in ms:
        return k
    return BIG if k == "int" and BIG in ms else t


def gen_selector_fail(self, a: str, b: str, marks: dict[str, str]) -> str:
    # the error of a return of a value of type b in the instance being compiled, which returned a's,
    # where no union joins them. Where its tests read parameters that literals may give
    # (stable_params) and that are no selectors of its template yet, marks gets its key and its
    # selectors with them: gen_err then compiles the program again with them, instead of reporting
    # it (unless that error comes of a join or another retry). Where this instance's call gave a
    # selector no literal, the message says so; where it passed the calling instance's own
    # parameter instead, marks gets the caller's key and its selectors with that parameter, as
    # forwarding (loads(s, logging) calling repair(s, logging))
    g = self.curfn
    msg = f"{short(g.name)}() returns both {typestr(a)} and {typestr(b)} (each function has one return type)"
    if not selector_fn(self, g):
        return msg
    key = self.selector_key(g)
    have = self.selectors.get(key, "").split()
    tested: dict[str, bool] = {}
    for st in g.node.kids[2].kids:
        tested_names(st, tested)
    new = [p for p in stable_params(self, g) if p in tested and p not in have]
    if len(new) > 0:
        marks[key] = " ".join(have + new)
        return msg
    missing = [p for p in have if p not in g.lits and p in g.params and g.params.index(p) < len(g.ptypes) and lit_type(g.ptypes[g.params.index(p)])]
    if len(missing) == 0:
        return msg
    if g.selfrom != "" and all([p in g.selfwd for p in missing]):
        theirs = self.selectors.get(g.selfrom, "").split()
        more = [g.selfwd[p] for p in missing if g.selfwd[p] not in theirs]
        if len(more) > 0:
            for p in more:
                if p not in theirs:
                    theirs.append(p)
            marks[g.selfrom] = " ".join(theirs)
            return msg
    which = " and ".join([f"'{p}'" for p in missing])
    if len(missing) == 1:
        return msg + f": its parameter {which} chooses which, and this call gives it no literal: pass a literal or annotate the result"
    return msg + f": its parameters {which} choose which, and this call gives them no literals: pass literals or annotate the result"


def gen_selector_const(self, n: Node) -> Node | None:
    # the literal value of test n, where the instance being compiled was compiled for literal
    # arguments (FnInfo.lits) and n reads one of those parameters (not a comprehension's variable
    # that shadows it): of the literals' truth, ==, !=, <, <=, >, >=, in, not in, not, len() and
    # partition() (const_of), and of is and is not with None, True or False; else None
    env: dict[str, Node] = {}
    for p in self.curfn.lits:
        if p not in self.compvars:
            env[p] = self.curfn.lits[p]
    if len(env) == 0 or not mentions(n, [p for p in env]) or not ascii_strs(n):
        return None
    if n.kind == "cmp" and (n.s == "is" or n.s == "is not") and len(n.kids) == 2:
        x = self.const_of(n.kids[0], env, False)
        y = self.const_of(n.kids[1], env, False)
        one = ["None", "True", "False"]
        if x is None or y is None or (x.kind not in one and y.kind not in one):
            return None  # (the identity of ints and strs is CPython's to decide)
        return mk("True" if (x.kind == y.kind) == (n.s == "is") else "False", "", n.line, [])
    c = self.const_of(n, env, False)
    if c is not None and (c.kind == "int" or c.kind == "unary"):
        return scalar_literal(c)  # (in decimal, whose truth static() reads: (00, mode)[0] is 0)
    return c


# ---- classes that specialize on literal arguments
def gen_literal_class(self, c: str) -> bool:
    # does class template c specialize on its literal constructor arguments: only operator's
    # getters do, whose items and names must be constants (a fixed tuple's index, an attribute's
    # name), and _struct's Struct, whose format decides its values' types (Gen.struct_call). Each
    # literal value makes a specialization of its own (see const_of)
    if c not in self.classes or (self.classes[c].mod != "operator" and self.classes[c].mod != "_struct"):
        return False
    o = short(self.classes[c].origin if self.classes[c].origin != "" else c)
    if self.classes[c].mod == "_struct":
        return o == "Struct"
    return o == "itemgetter" or o == "attrgetter" or o == "methodcaller"

def gen_literal_args(self, f: FnInfo, args: list[Node]) -> dict[str, Node]:
    # the parameters of __init__ f (after self) that a call with args gives literal values (see
    # const_of), *args's as a tuple of them where each extra argument is one
    out: dict[str, Node] = {}
    extra: list[Node] = []
    every = True
    pos = 1
    for a in args:
        c = self.const_of(a.kids[0] if a.kind == "kw" else a, {}, True) if a.kind != "starred" and a.kind != "dstar" else None
        if a.kind == "kw":
            # A positional-only parameter's spelling is an ordinary **kwargs key,
            # as are the names of *args and **kwargs themselves. It must not replace
            # the literal constructor argument used to choose a getter's method.
            j = f.params.index(a.s) if a.s in f.params else -1
            if c is not None and j >= f.posonly and j != f.vararg and j != f.kwarg:
                out[a.s] = c
        elif f.vararg >= 0 and pos >= f.vararg:
            if c is None:
                every = False
            else:
                extra.append(c)
        else:
            if c is not None and pos < len(f.params):
                out[f.params[pos]] = c
            pos += 1
    if f.vararg >= 0 and every:
        out[f.params[f.vararg]] = mk("tuple", "", self.line, extra)
    return out

def lit_key(n: Node) -> str:
    # a literal node's value, as a specialization's key spells it
    if n.kind == "str":
        return f"s{len(n.s)}:{n.s}"
    if n.kind == "tuple":
        return "(" + ",".join([lit_key(x) for x in n.kids]) + ")"
    if n.kind == "unary":
        return "-" + n.kids[0].s
    return n.s if n.kind == "int" else n.kind

def lit_text(n: Node) -> str:
    # a literal node as Python source
    if n.kind == "str":
        return "'" + n.s.replace("\\", "\\\\").replace("'", "\\'") + "'"
    if n.kind == "tuple":
        return "(" + ", ".join([lit_text(x) for x in n.kids]) + ("," if len(n.kids) == 1 else "") + ")"
    return "-" + n.kids[0].s if n.kind == "unary" else n.s if n.kind == "int" else n.kind

def lit_int(n: Node) -> int:
    return -int(n.kids[0].s) if n.kind == "unary" else 1 if n.kind == "True" else 0 if n.kind == "False" else int(n.s)

def lit_same(a: Node, b: Node) -> bool:
    # do literals a and b have equal values (an int and a bool or each other's equals, as in CPython)
    num = ["int", "unary", "True", "False"]
    if a.kind in num and b.kind in num:
        return lit_int(a) == lit_int(b)
    if a.kind == "tuple" and b.kind == "tuple":
        return len(a.kids) == len(b.kids) and all([lit_same(a.kids[i], b.kids[i]) for i in range(len(a.kids))])
    return a.kind == b.kind and a.s == b.s

def gen_lit_context(self) -> bool:
    # is the function being compiled a method of a class that specializes on literals
    return self.curfn.cls in self.classes and self.literal_class(self.curfn.cls)

def gen_const_of(self, n: Node, env: dict[str, Node], live: bool) -> Node | None:
    # the literal node of n's value, where literal arguments decide it at compile time: literals
    # and tuples of them, the parameters given literals (env, or live, a literal class's
    # __init__'s), its fields that hold constants (self.k, live), and their indexing, len(), +,
    # ==, !=, in, not and str.partition(); else None
    k = n.kind
    if k == "int" or k == "str" or k == "True" or k == "False" or k == "None":
        return n
    if k == "unary" and n.s == "-" and n.kids[0].kind == "int":
        return n
    f = self.curfn
    c = self.classes[f.cls] if live and f.cls in self.classes else None
    if k == "name":
        if n.s in env:
            return env[n.s]
        if c is not None and f.name == "__init__" and n.s in c.lits:
            asg: dict[str, bool] = {}
            local_names(f.node.kids[2].kids, asg)
            return c.lits[n.s] if n.s not in asg else None
        return None
    if k == "attr" and c is not None and n.kids[0].kind == "name" and takes_self(f) and not f.nullable_self and n.kids[0].s == f.params[0] and n.s in c.fconst:
        asg = {}
        local_names(f.node.kids[2].kids, asg)
        return c.fconst[n.s] if f.params[0] not in asg else None
    if k == "tuple":
        items: list[Node] = []
        for x in n.kids:
            v = self.const_of(x, env, live) if x.kind != "starred" else None
            if v is None:
                return None
            items.append(v)
        return mk("tuple", "", n.line, items)
    if k == "unary" and n.s == "not":
        v = self.const_of(n.kids[0], env, live)
        return None if v is None or (v.kind != "True" and v.kind != "False") else mk("False" if v.kind == "True" else "True", "", n.line, [])
    if k == "index" and len(n.kids) == 2:
        a = self.const_of(n.kids[0], env, live)
        i = self.const_of(n.kids[1], env, live)
        if a is None or i is None or a.kind != "tuple" or i.kind not in ["int", "unary", "True", "False"]:
            return None
        j = lit_int(i) + (len(a.kids) if lit_int(i) < 0 else 0)
        return a.kids[j] if 0 <= j < len(a.kids) else None
    if k == "binop" and n.s == "+":
        a = self.const_of(n.kids[0], env, live)
        b = self.const_of(n.kids[1], env, live)
        if a is not None and b is not None and a.kind == b.kind and (a.kind == "tuple" or a.kind == "str"):
            return mk(a.kind, a.s + b.s if a.kind == "str" else "", n.line, a.kids + b.kids)
        return None
    if k == "cmp" and n.s in ["==", "!=", "in", "not in", "<", "<=", ">", ">="]:
        a = self.const_of(n.kids[0], env, live)
        b = self.const_of(n.kids[1], env, live)
        if a is None or b is None:
            return None
        num = ["int", "unary", "True", "False"]
        if n.s in ["<", "<=", ">", ">="]:
            if a.kind not in num or b.kind not in num:
                return None
            p = lit_int(a)
            q = lit_int(b)
            r = p < q if n.s == "<" else p <= q if n.s == "<=" else p > q if n.s == ">" else p >= q
        elif n.s == "==" or n.s == "!=":
            r = lit_same(a, b) == (n.s == "==")
        elif b.kind == "str" and a.kind == "str":
            r = (a.s in b.s) == (n.s == "in")
        elif b.kind == "tuple":
            r = (len([y for y in b.kids if lit_same(a, y)]) > 0) == (n.s == "in")
        else:
            return None
        return mk("True" if r else "False", "", n.line, [])
    if k == "call" and len(n.kids) == 2 and n.kids[0].kind == "name" and n.kids[0].s == "len" and not self.bound("len"):
        a = self.const_of(n.kids[1], env, live)
        if a is not None and (a.kind == "tuple" or a.kind == "str"):
            return mk("int", str(len(a.kids) if a.kind == "tuple" else len(a.s)), n.line, [])
        t = self.iter_static(n.kids[1]) if live and a is None else ""
        return mk("int", str(len(targs(t))), n.line, []) if is_tuple(t) else None  # (a fixed tuple's length)
    if k == "call" and len(n.kids) == 2 and n.kids[0].kind == "attr" and n.kids[0].s == "partition":
        a = self.const_of(n.kids[0].kids[0], env, live)
        sep = self.const_of(n.kids[1], env, live)
        if a is not None and sep is not None and a.kind == "str" and sep.kind == "str" and sep.s != "":
            j = a.s.find(sep.s)
            parts = [a.s, "", ""] if j < 0 else [a.s[:j], sep.s, a.s[j + len(sep.s) :]]
            return mk("tuple", "", n.line, [mk("str", x, n.line, []) for x in parts])
    return None

def self_stores(ns: list[Node], me: str, count: dict[str, int]) -> None:
    # how many statements of ns (and the blocks in them) assign each attribute of me
    for n in ns:
        if (n.kind == "assign" or n.kind == "annassign" or n.kind == "augassign") and len(n.kids) > 0:
            ts = n.kids[:-1] if n.kind == "assign" else n.kids[:1]
            for t in ts:
                xs = t.kids if t.kind == "tuple" or t.kind == "list" else [t]
                for x in xs:
                    if x.kind == "attr" and x.kids[0].kind == "name" and x.kids[0].s == me:
                        count[x.s] = count.get(x.s, 0) + 1
        self_stores(n.kids, me, count)

def gen_const_fields(self, s: ClassInfo, init: FnInfo) -> None:
    # the fields of specialization s that hold constants: each assigned once by __init__, in a
    # statement of its body of its own, a value that s's literal arguments decide (see const_of)
    count: dict[str, int] = {}
    me = init.params[0]
    self_stores(init.node.kids[2].kids, me, count)
    for st in init.node.kids[2].kids:
        if st.kind == "assign" and len(st.kids) == 2 and st.kids[0].kind == "attr" and st.kids[0].kids[0].kind == "name" and st.kids[0].kids[0].s == me and count.get(st.kids[0].s, 0) == 1:
            v = self.const_of(st.kids[1], s.lits, False)
            if v is not None:
                s.fconst[st.kids[0].s] = v
