"""Program component of the self-hosting Pystachy compiler."""
from __future__ import annotations
import os
import sys
from src.pystachy_compiler.callbacks import specialize_callbacks
from src.pystachy_compiler.reflection import refl_needs_eh, refl_props
from src.pystachy_compiler.analysis import all_imports, collect, defines, module_ints, module_reads, module_strs, needs_eh, none_assigns, reads_builtin
from src.pystachy_compiler.diagnostics import Rejoin, dynamic_program, fail, shown
from src.pystachy_compiler.dynamic import comparison_properties, comparison_storage
from src.pystachy_compiler.generators import reads_cause, reads_handled, uses_protocol
from src.pystachy_compiler.ir import Val, ClassInfo, FnInfo, NOLABELS, NONUMS, NOVALS, one_nums_intact
from src.pystachy_compiler.module import Mod
from src.pystachy_compiler.names import RENAMED, short
from src.pystachy_compiler.specs import (
    ABSTRACT_DECOS,
    EXCBASES,
    EXCEPTIONS,
    PLAIN_EXC_BASES,
    exc_derives,
    GALIAS,
    INERT,
    INERT_DECOS,
    is_excname,
    ITERS,
    MODATTRS,
    OBJECTS,
    PURE,
    PYBUILTINS,
    RAISERS,
    RANGES,
    RTSYM,
    TYPING,
    UNSUPPORTED,
)
from src.pystachy_compiler.syntax import Node, dc_args, has_kind, mentions, mk, names_in
from src.pystachy_compiler.utils import (
    RtFn,
    clone,
    elem,
    fxs,
    hpop,
    hpush,
    int_lit,
    is_const,
    is_dict,
    is_list,
    lt,
    may_raise,
    optimizations,
    raising,
    raising_op,
    rt_subset,
    short_ascii,
    targs,
    template_ok,
    timing_end,
    timing_start,
    typestr,
    unopt,
)


def role_body_uses_storage(n: Node, receiver: str, methods: list[str], attrs: list[str]) -> bool:
    # Ordinary calls can use the role's public method contract without depending on
    # the layout of the concrete receiver. Check the explicit arguments normally.
    # An attribute the role declares (attrs: role_attrs) is the concrete receiver's own field.
    if n.kind == "name":
        return n.s == receiver or n.s == "super"
    if n.kind == "attr" and n.s in attrs and n.kids[0].kind == "name" and n.kids[0].s == receiver:
        return False
    kids = n.kids
    if n.kind == "call" and kids[0].kind == "attr":
        target = kids[0]
        if target.s in methods and target.kids[0].kind == "name" and target.kids[0].s == receiver:
            kids = kids[1:]
    for child in kids:
        if role_body_uses_storage(child, receiver, methods, attrs):
            return True
    return False


def stores_attr(n: Node, receiver: str) -> bool:
    # does code n store to or delete an attribute of name receiver (self.x = v, self.x += v,
    # del self.x), also in what it nests
    if (n.kind == "assign" or n.kind == "augassign" or n.kind == "annassign" or n.kind == "del") and len(n.kids) > 0:
        for t in n.kids[:-1] if n.kind == "assign" else n.kids[:1] if n.kind != "del" else n.kids:
            if t.kind == "attr" and t.kids[0].kind == "name" and t.kids[0].s == receiver:
                return True
    for k in n.kids:
        if stores_attr(k, receiver):
            return True
    return False


def fieldless(c: Node) -> bool:
    # does class c (its class node) add no fields: no class-body variable, annotated or not (a
    # class attribute has a slot in its objects too), no __init__, no store to an attribute of a
    # method's first parameter, and no __slots__ but ()
    for d in c.kids[0].kids:
        slots = (d.kind == "assign" or d.kind == "annassign") and d.kids[0].kind == "name" and d.kids[0].s == "__slots__"
        if slots and not (d.kids[-1].kind == "tuple" and len(d.kids[-1].kids) == 0 and len(d.kids) == (2 if d.kind == "assign" else 3)):
            return False
        if (d.kind == "annassign" or d.kind == "assign" or d.kind == "augassign") and not slots:
            return False
        if d.kind == "def" and (d.s == "__init__" or (len(d.kids[0].kids) > 0 and stores_attr(d.kids[2], d.kids[0].kids[0].s))):
            return False
    return True


def super_calls(n: Node, shadow: dict[str, bool]) -> bool:
    # does code n use super() otherwise than as super().m(...) of a method m that no secondary
    # base defines (shadow): CPython's method resolution order puts the secondary bases after
    # the primary's, so such a call finds what the primary base's bases have, as Pystachy's does
    if n.kind == "name" and n.s == "super":
        return True
    kids = n.kids
    if n.kind == "call" and kids[0].kind == "attr" and kids[0].kids[0].kind == "call" and len(kids[0].kids[0].kids) == 1 and kids[0].kids[0].kids[0].kind == "name" and kids[0].kids[0].kids[0].s == "super":
        if kids[0].s in shadow:
            return True
        kids = kids[1:]
    for k in kids:
        if super_calls(k, shadow):
            return True
    return False


def gen_subclass_problem(self, st: Node) -> str:
    # why class statement st, which names bases, cannot be compiled, or "": one ordinary
    # class declared before it, or one of the supported exception bases
    if st.kids[1].kind == "typeparams":
        return self.class_params(st)
    if st.kids[1].kind == "call" and st.kids[1].kids[0].kind == "name" and st.kids[1].kids[0].s == "collections$namedtuple":
        return "inheritance from a namedtuple() class is not supported"
    if st.kids[1].kind == "index" and self.imported_ref(st.kids[1].kids[0]) == "typing.Generic":
        return "a generic class's one base is Generic[...] of its TypeVars, and at most one TypeVarTuple, unpacked (Generic[T, *Ts]), each once" if len(st.kids) == 2 else "a generic class with another base than Generic[...] is not supported"
    if len(st.kids) > 2:
        why = "multiple inheritance requires an ordinary primary base and an independent method-only secondary base, or several"
        if len(st.kids) == 3:
            first = self.exc_base(st.kids[1])
            second = self.exc_base(st.kids[2])
            if first in EXCBASES and first not in self.classes and second in EXCBASES and second not in self.classes:
                if first not in PLAIN_EXC_BASES or second not in PLAIN_EXC_BASES or exc_derives(first, second) or exc_derives(second, first):
                    return "two builtin exception bases must be independent and have ordinary Exception behavior"
                if len(st.kids[0].kids) > 1:
                    return "an exception class with a decorator is not supported"
                return ""
        if any(b.kind != "name" for b in st.kids[1:]):
            return why
        primary = st.kids[1].s
        secondaries = [b.s for b in st.kids[2:]]
        if primary not in self.classes or self.abc_class(primary) or self.classes[primary].exc != "" or self.is_dc(primary) or len(st.kids[0].kids) != 1:
            return why
        shadow: dict[str, bool] = {}  # (the methods of the secondary bases' own classes: super_calls)
        for secondary in secondaries:
            if secondary not in self.classes or secondaries.count(secondary) > 1 or self.derives(primary, secondary):
                return why
            # (a root class of methods alone; a generic one binds nothing: it has no __init__. Or
            # a trait, as mypyc's: a class of methods alone whose bases end at a class of the
            # primary base's chain, so its objects' fields come first in the primary's too)
            role = self.classes[secondary]
            if (role.base != "" and self.trait_root(primary, secondary) == "" and len(self.role_chain(primary, secondary)) == 0) or len(role.node.kids) != 1 or secondary in self.nts or self.abc_class(secondary):
                return why
            c = secondary
            while c in self.classes and not self.on_chain(primary, c):
                for d in self.classes[c].node.kids[0].kids:
                    if d.kind == "def":
                        shadow[d.s] = True
                c = self.classes[c].base
        root = ""
        first = ""
        for secondary in self.classes[primary].roles + secondaries:
            # (traits of one class, also those its primary base has, derive from one class of the
            # primary chain, as mypy's do from Node: a trait of another class there would reorder
            # CPython's method resolution order around the primary chain's classes between them,
            # which super() and the checks of inherit do not follow)
            t = self.trait_root(primary, secondary) if self.classes[secondary].base != "" else ""
            if t != "" and root != "" and t != root:
                return f"traits {short(first)} and {short(secondary)} of one class derive from different classes of its primary base's chain, {short(root)} and {short(t)}: not supported"
            first = secondary if t != "" and root == "" else first
            root = t if t != "" else root
        ancestor = primary
        while ancestor in self.classes:
            info = self.classes[ancestor]
            if super_calls(info.node, shadow):
                return "super() in a primary hierarchy with a secondary base is not supported"
            ancestor = info.base
        if super_calls(st.kids[0], shadow):
            return "super() in a class with a secondary base is not supported"
        for secondary in secondaries:
            role = self.classes[secondary]
            trait = role.base != "" and self.trait_root(primary, secondary) != ""
            # (an interface's own chain, role_chain: each class's body is checked as the base's)
            chain = [secondary] if trait else self.role_chain(primary, secondary)
            methods: list[str] = []
            attrs: list[str] = []  # (the attributes it declares, which its methods may read and store)
            for rc in chain:
                methods += [d.s for d in self.classes[rc].node.kids[0].kids if d.kind == "def"]
                if not trait:
                    attrs += role_attrs(self.classes[rc].node)
                    # (... and its properties, which the receiver's class may override)
                    attrs += [d.s for d in self.classes[rc].node.kids[0].kids if d.kind == "def" and len([x for x in d.kids[3:] if x.s == "property" and len(x.kids) == 0]) > 0]
            body: list[Node] = []
            for rc in chain:
                body += self.classes[rc].node.kids[0].kids
            for d in body:
                if d.kind == "pass" or (d.kind == "expr" and d.kids[0].kind == "str"):
                    continue
                if not trait and d.kind == "annassign" and len(d.kids) == 2 and d.kids[0].kind == "name" and d.kids[0].s != "__slots__":
                    continue  # (an attribute declared for the classes that combine it: role_field)
                if trait and (d.kind == "assign" or d.kind == "annassign") and d.kids[0].kind == "name" and d.kids[0].s == "__slots__":
                    continue  # (an empty one: fieldless)
                if trait and d.kind == "def" and not d.s.startswith("__") and len(d.kids[0].kids) > 0 and len([x for x in d.kids[3:] if len(x.kids) > 0 or (self.imported(x.s) != "abc.abstractmethod" and x.s not in ["property", "classmethod", "staticmethod"])]) == 0:
                    # (a trait's methods may read the instance, whose fields are its bases', and be
                    # properties, class or static methods, abstract or not; they may not call super())
                    if mentions(d, ["super"]):
                        return "secondary base methods may not use super() or read or write the instance"
                    continue
                # (abc's @abstractmethod, without abc.ABCMeta, marks a method only: CPython makes
                # its objects as any other's)
                # (... and @property a getter, abstract or not, which the class may override)
                abstract = d.kind == "def" and len(d.kids) > 3 and len([x for x in d.kids[3:] if len(x.kids) > 0 or (self.imported(x.s) != "abc.abstractmethod" and x.s != "property")]) == 0
                if d.kind != "def" or d.s.startswith("__") or (len(d.kids) != 3 and not abstract) or len(d.kids[0].kids) == 0:
                    return why
                if "_pys_cm_" + d.s in methods and len(attrs) > 0:
                    continue  # (a @contextmanager method's own code is _pys_cm_<name>, checked as a method: this one makes its context manager, loader.py)
                if role_body_uses_storage(d.kids[2], d.kids[0].kids[0].s, methods, attrs):
                    return "secondary base methods may not use super() or read or write the instance"

    if st.kids[1].kind == "name" and st.kids[1].s in self.classes and self.classes[st.kids[1].s].exc == "":
        base_ci = self.classes[st.kids[1].s]
        dc = len(st.kids[0].kids) == 2 and self.imported(st.kids[0].kids[1].s) == "dataclasses.dataclass"
        if base_ci.name in self.nts:
            return "inheritance from a NamedTuple is not supported"
        if self.is_dc(base_ci.name) and not dc:
            return "inheritance from a dataclass is only supported by a @dataclass class"
        if self.init_template(base_ci.node) or self.init_template(st.kids[0]):
            return "inheritance with generic class templates is not supported: " + self.template_fix([base_ci.node, st.kids[0]])
        if dc and not self.is_dc(base_ci.name):
            return "a @dataclass class whose base is not a dataclass is not supported"
        if len(st.kids[0].kids) > 1 and not dc:
            return "a class with inheritance and a decorator is not supported"
        return ""
    b = self.exc_base(st.kids[1])
    if b == "" and len(st.kids) == 2 and st.kids[1].kind == "name" and short(st.kids[1].s) == "object":
        return UNSUPPORTED["subclass"] + " (the module may have rebound the name 'object' before this statement)"
    if b == "":
        return "unsupported base class: single inheritance requires a previously declared ordinary class or a supported exception class"
    if b not in self.classes and (EXCEPTIONS.get(b, "-") == "-" or EXCEPTIONS.get(b, "") == "u" or exc_derives(b, "SyntaxError")):
        return f"deriving from {b} is not supported"  # (u: a UnicodeError whose five arguments make its message)
    if len(st.kids[0].kids) > 1:
        return f"an exception class with a decorator (@{st.kids[0].kids[1].s}) is not supported"
    return ""

def gen_generic_subclass(self, st: Node) -> str:
    # class V(Visitor[str]): a base that subscripts a generic class without an __init__ of its
    # own, which binds nothing (Visitor[str] is Visitor, see generic_ann), is that class, whose
    # methods' parameters that name its type variables take each call's types. Its type
    # arguments are checked as the annotation Visitor[str] checks them, and the statement then
    # names the class itself, as the rest of declaration reads its base (#962). Each base of
    # several so (secondary bases: subclass_problem); a generic class's own type variables may
    # be such a base's arguments (class N(Generic[T], A[T], B[T]), generic_traits), which N's
    # subclasses bind (tv_bound). "" or why not
    own = self.tparams.get(st.s, [])
    for j in range(1, len(st.kids)):
        b = st.kids[j]
        if b.kind != "index" or b.kids[0].kind != "name" or b.kids[0].s not in self.tparams or b.kids[0].s not in self.classes:
            continue
        g = b.kids[0].s
        if self.init_template(self.classes[g].node):
            return f"a subclass of {shown(g)}[...] is not supported: the __init__ of {shown(g)} binds its type variables, as its calls' arguments do"
        if "__class_getitem__" in self.body_names(self.classes[g].node):
            # (as generic_ann: g[T] calls it, which may run code or name another class; also
            # where the arguments are the class's own type variables, passed on)
            return f"{short(g)}[...] with a custom __class_getitem__ is not supported"
        xs = b.kids[1].kids if b.kids[1].kind == "tuple" else [b.kids[1]]
        args: list[str] = []
        if self.typevar_in(xs, []) == "" or len(own) == 0:
            t = self.generic_ann(g, b.kids[1])
            if t.startswith("!"):
                return t[1:]
            args = [self.ann(x) for x in xs]
        else:
            tvs = self.tparams[g]
            if len(xs) != len(tvs) or len([x for x in tvs if x in self.tvtuples]) > 0:
                return f"{shown(g)}[...] as a base takes one type for each of its type variables ({', '.join([short(x) for x in tvs])}), not a TypeVarTuple's"
            for x in xs:
                if x.kind == "name" and x.s in own and x.s not in self.tvtuples:
                    args.append("~" + x.s)  # (its own type variable, passed on)
                elif self.typevar_in([x], []) != "":
                    return f"the type arguments of base {shown(g)}[...] must be types or type variables of {shown(st.s)}"
                else:
                    t = self.ann(x)
                    if t.startswith("!"):
                        return t[1:]
                    args.append(t)
        if st.s not in self.genargs:
            self.genargs[st.s] = {}
        self.genargs[st.s][g] = args
        st.kids[j] = b.kids[0]
    return ""

def gen_generic_traits(self, st: Node) -> int:
    # class N(Generic[T], A[T], B[T], C): a generic class whose first other base is a generic
    # class, subscripted (generic_subclass), and whose others are classes too (secondary bases,
    # subclass_problem): the position of its Generic[...] base, else 0
    k = 0
    first = True
    for j in range(1, len(st.kids)):
        b = st.kids[j]
        if len(self.generic_base(b)) > 0 and k == 0:
            k = j
        elif b.kind == "index" and b.kids[0].kind == "name" and b.kids[0].s in self.tparams:
            first = False
        elif first or b.kind != "name":
            return 0
    return k

def gen_exc_base(self, b: Node) -> str:
    # the exception class that b, the base of a class statement, names: a class of the program
    # or a builtin one (IOError and EnvironmentError are OSError; builtins.X and os.error
    # too), else ""
    s = b.s
    if b.kind == "attr" and b.kids[0].kind == "name" and self.imported(b.kids[0].s) == "builtins" and is_excname(b.s):
        s = b.s
    elif b.kind == "attr" and b.kids[0].kind == "name" and self.imported(b.kids[0].s) == "os" and b.s == "error":
        s = "OSError"
    elif b.kind != "name":
        return ""
    if s in self.classes:
        return s if self.classes[s].exc != "" else ""
    if is_excname(s):
        return "OSError" if s == "IOError" or s == "EnvironmentError" else s
    return ""

def gen_inherit(self, ci: ClassInfo) -> None:
    # a class has the methods of its base that it does not define: the same
    # functions, compiled for the base (its objects begin as the base's do), but for a class
    # method that uses cls, which is compiled again with cls naming this class (unless a
    # default value of it needs evaluating when its def runs, or the base is another
    # module's: cls_bound rejects its calls).
    # Ordinary instance methods specialize for the receiver and dispatch on its class.
    # Exception methods retain their existing restricted override rules.
    if ci.base not in self.classes:
        return
    b = self.classes[ci.base]
    for m in b.methods:
        f = b.methods[m]
        if f.acc != "" and m not in ci.methods and f.node.s in ci.methods and ci.methods[f.node.s].cls == ci.name:
            continue  # (its own @property def makes a new property, without the base's setter and deleter)
        if m not in ci.methods and f.clsuse and f.mod == ci.mod and len([x for x in f.defaults if not is_const(x) and x.kind != "noann"]) == 0:
            self.line = f.node.line
            self.lib = f.mod != ""
            self.selfcls = ci.name
            # Clone the declaration only. Its immutable body is shared until the method
            # is needed; declaring and flowing a copy per subclass costs body * subclasses
            # even when no inherited method is called.
            d = Node(f.orig.kind, f.orig.s, f.orig.line, [f.orig.kids[i] if i == 2 else clone(f.orig.kids[i]) for i in range(len(f.orig.kids))])
            g = self.declare_fn(d, ci.name, True)
            g.orig = f.orig
            g.clsuse = True
            g.pending = True
            g.bad = g.bad if g.bad != "" else f.bad  # the defining declaration checked the body
            ci.methods[m] = g
            self.selfcls = ""
            self.lib = False
            ci.methods[m].mod = f.mod
            self.lazy[ci.methods[m].ll] = ci.methods[m]  # (compiled only if called: cls(...) may not fit this class)
        elif m not in ci.methods:
            ci.methods[m] = f
        elif f.prop != ci.methods[m].prop:
            self.line = ci.methods[m].node.line
            self.bad_class(ci, f"overriding '{m}' as a different kind of attribute (property or method) is not supported")
        elif ci.exc == "" and f.deco != ci.methods[m].deco:
            self.line = ci.methods[m].node.line
            self.bad_class(ci, f"overriding '{m}' of '{short(b.name)}' with another kind of method (instance, static or class method) in '{short(ci.name)}' is not supported")
        elif ci.exc != "" and m != "__init__" and m != "__str__" and m != "__repr__":
            self.line = ci.methods[m].node.line
            self.err(f"method '{m}' of '{short(ci.name)}' overrides that of '{short(b.methods[m].cls)}': only __init__, __str__ and __repr__ may be overridden")
    seen: dict[str, str] = {}  # (the secondary base whose method of each name comes first)
    order = self.mro(ci.name) if len(ci.roles) > 0 else []  # (CPython's method resolution order)
    if len(ci.roles) > 0 and len(order) == 0:
        self.line = ci.node.line
        self.bad_class(ci, "Cannot create a consistent method resolution order (MRO) for its bases (CPython's TypeError)")
    for r in ci.roles:
        role = self.classes[r]
        # (a generic secondary base's methods leave out the annotations that name its type
        # variables, declare_fn: an override's own types them, as a generic primary base's does)
        generic = r in self.tparams
        trait = role.base != "" and len(self.role_chain(ci.base, r)) == 0  # (else an interface that extends another: as a root base)
        for method in role.methods:
            original = role.methods[method]
            if role.base != "" and self.on_chain(ci.base, self.declarer(r, method)):
                continue  # (a trait's from a class of the primary chain, which the primary base has too)
            if r not in b.roles:
                # (the classes that define it, not FnInfo.cls: inherit copies a class method that
                # uses cls for each class that inherits it)
                own = self.declares(ci.name, method)
                if method not in b.methods and method in seen and seen[method] != r and own:
                    # (also where the class's own overrides both: a Callable of its bound method
                    # would differ by the base it is read through, adapter's method families)
                    self.line = ci.node.line
                    self.bad_class(ci, f"secondary bases {short(seen[method])} and {short(r)} both declare method '{method}' (not supported, also where {short(ci.name)} overrides it)")
                seen[method] = seen.get(method, r)
                first = self.mro_first(order, method)
                if trait and first == r and method in b.methods:
                    # (the trait's comes first in CPython's method resolution order: before the
                    # primary chain's from the classes it derives from, and the primary base's
                    # earlier traits' and other bases' that do not declare it)
                    if original.deco == "classmethod" and original.clsuse:
                        # (its cls names the trait, where CPython's names the class: compiled for
                        # the trait, as it is, it would read the trait's class attributes)
                        pm = self.declarer(ci.base, method)
                        self.line = ci.node.line
                        self.bad_class(ci, f"class method '{method}' of trait {short(r)} uses cls where it overrides that of {short(pm if pm != '' else b.methods[method].cls)}: not supported")
                    for acc in [method + ".setter", method + ".deleter"] if original.prop else []:
                        if acc in ci.methods and acc not in role.methods:
                            del ci.methods[acc]  # (its property replaces the one with that accessor)
                    ci.methods[method] = original
                elif trait and method in b.methods:
                    pass  # (the class's own, or one that comes before the trait's: kept, and checked against it)
                elif method in b.methods or (method in ci.methods and ci.methods[method].cls != ci.name):
                    # (also another secondary base's: CPython's method resolution order picks one)
                    self.line = ci.node.line
                    self.bad_class(ci, f"both bases declare method '{method}'")
                elif method not in ci.methods:
                    ci.methods[method] = original
            fn = ci.methods[method]
            same = len(fn.ptypes) == len(original.ptypes)
            for j in range(1, len(fn.ptypes) if same else 0):
                if fn.ptypes[j] != original.ptypes[j] and not (generic and original.ptypes[j] == ""):
                    same = False
            # (an override may return a class that derives from what the secondary base's returns,
            # as one of a primary base's may: its objects are the base's, also in a trait's view)
            covariant = unopt(fn.ret) in self.classes and unopt(original.ret) in self.classes and (fn.ret == unopt(fn.ret)) == (original.ret == unopt(original.ret)) and self.derives(unopt(fn.ret), unopt(original.ret))
            if fn is not original and (fn.cls == ci.name or trait) and (
                fn.deco != original.deco or fn.prop != original.prop or not same or (fn.ret != original.ret and not (generic and original.ret == "") and not covariant)
                or fn.posonly > original.posonly or fn.npos != original.npos
                or fn.kwarg != original.kwarg or fn.vararg != original.vararg
            ):
                self.line = fn.node.line
                self.bad_class(ci, f"secondary base method '{method}' needs a matching instance method signature")
    for m in ci.methods:
        f = ci.methods[m]
        if f.cls == ci.name and f.acc != "" and short(f.accof) != f.node.s:
            # @Base.x.setter: a new property x with the getter (and deleter) of Base's, the
            # property this class inherits, and this method
            p = f.node.s
            bn = f.accof[: f.accof.rfind(".")]
            if p not in ci.methods or not ci.methods[p].prop or ci.methods[p].cls == ci.name or bn not in self.classes or p not in self.classes[bn].methods or ci.methods[p] is not self.classes[bn].methods[p]:
                self.line = f.node.line
                self.bad_class(ci, f"@{short(f.accof)}.{f.acc} is not supported here: {short(bn)} must be the base class whose property {f.node.s} this class inherits")

def gen_accessor(self, ci: ClassInfo, d: Node) -> str:
    # method d of class ci, decorated @x.setter or @x.deleter (or @Base.x.setter, see inherit):
    # ".setter" or ".deleter", which adds it to property x (its methods key is x.setter); else ""
    s = d.kids[3].s if len(d.kids) == 4 and len(d.kids[3].kids) == 0 else ""
    acc = s[s.rfind(".") + 1 :]
    if "." in s and acc == "getter" and short(s[: s.rfind(".")]) == d.s:
        self.err(f"unsupported decorator @{short(s)}: define the property's getter once, with @property")
    if "." not in s or (acc != "setter" and acc != "deleter"):
        return ""
    of = short(s[: s.rfind(".")])
    if of == d.s and (d.s not in ci.methods or not ci.methods[d.s].prop):
        # (CPython's NameError, or AttributeError: 'function' object has no attribute 'setter')
        self.err(f"@{of}.{acc} needs property {d.s}, a @property def {d.s} before it in the class body")
    if of != d.s and (of[of.rfind(".") + 1 :] != d.s or ci.base not in self.classes):
        self.err(f"@{of}.{acc} on method {d.s} is not supported: a property's {acc} takes its name ({of[of.rfind('.') + 1 :]}), and a base's property is named through the base class")
    return "." + acc

def gen_class_ref(self, m: Mod, s: str) -> str:
    # the class that dotted name s names in module m's code, where the loader leaves a
    # decorator's name of another module's class as written (see Loader.qdeco), else s
    root = s[: s.find(".")] if "." in s else s
    k = m.kinds.get(root[len(m.q) :] if root.startswith(m.q) else root, "")
    if k.startswith("a:"):
        return k[2:] + s[len(root) :]
    if k.startswith("m:"):
        return (k[2:] + s[len(root) :]).replace(".", "$")
    return s

def gen_dc_options(self, ci: ClassInfo) -> None:
    # class ci's decorators: @dataclass, whose options (dc_args) it keeps, and no other
    st = ci.node
    if len(st.kids) > 1 and self.imported(st.kids[1].s) == "dataclasses.dataclass" and dc_args(st.kids[1]).startswith("!"):
        self.err(dc_args(st.kids[1])[1:])
    for o in dc_args(st.kids[1]).split() if len(st.kids) > 1 and self.imported(st.kids[1].s) == "dataclasses.dataclass" else []:
        ci.dcopts[o] = True
    ci.kwonly = "kw_only" in ci.dcopts
    if "order" in ci.dcopts and "no-eq" in ci.dcopts:
        self.err("eq must be true if order is true")  # (CPython's ValueError where it creates the class)
    if "frozen" in ci.dcopts:
        self.hasfrozen = True
    if len(st.kids) > 1 and self.imported(st.kids[1].s) != "dataclasses.dataclass":
        self.err(f"unsupported decorator @{st.kids[1].s}" + (" (import dataclass from dataclasses)" if st.kids[1].s == "dataclass" else ""))
    if len(st.kids) > 2:
        self.err(f"unsupported decorator @{st.kids[2].s}")

def gen_on_chain(self, c: str, a: str) -> bool:
    # is class a class c or one of the classes c derives from by its primary bases
    while c in self.classes:
        if c == a:
            return True
        c = self.classes[c].base
    return False

def role_attrs(c: Node) -> list[str]:
    # the attributes class c (its class node) declares by annotation alone (x: T), which a
    # secondary base may: no object has them until its class's code stores them
    return [d.kids[0].s for d in c.kids[0].kids if d.kind == "annassign" and len(d.kids) == 2 and d.kids[0].kind == "name" and d.kids[0].s != "__slots__"]

def gen_role_field(self, t: str, name: str) -> bool:
    # is name an attribute that t declares (role_attrs), a class that some class names as a
    # secondary base outside its primary chain, or that such a base derives from (role_chain): an
    # object typed t is then one of t's own, with t's layout, or one of a class that combines
    # t, which holds the attribute among its own fields (class_fields). A read or store through t
    # therefore goes by the object's exact class (refl_split), where Gen.rolex names the object
    # once that class is known
    if t not in self.classes:
        return False
    ci = self.classes[t]
    return ci.isiface and name in ci.ftypes and not name.startswith(" ")

def gen_role_chain(self, primary: str, secondary: str) -> list[str]:
    # the classes of secondary base secondary's own chain, itself first, where it is no trait of
    # primary (trait_root): a root class, or one that derives from root classes alone, none of
    # them of primary's chain, with secondary bases of its own, decorated or a dataclass, a
    # NamedTuple, an exception or abstract base class (an interface that extends another, as
    # mypy's TypeCheckerSharedApi(CheckerPluginInterface)); else []
    out: list[str] = []
    c = secondary
    while c != "":
        if c not in self.classes or self.on_chain(primary, c):
            return []
        info = self.classes[c]
        if info.exc != "" or self.is_dc(c) or c in self.nts or len(info.roles) > 0 or len(info.node.kids) != 1 or self.abc_class(c):
            return []
        out.append(c)
        c = info.base
    return out

def gen_trait_root(self, primary: str, secondary: str) -> str:
    # the class of primary's chain (on_chain) that secondary base secondary derives from
    # directly, where secondary adds no fields (fieldless) and has no secondary bases of its own:
    # every object of a class deriving from both then begins with that class's fields, as
    # secondary's objects do; else "". Not through other classes: isinstance() and dispatch know
    # the secondary base itself (ClassInfo.roles), not the classes between it and the chain
    info = self.classes[secondary]
    if info.exc != "" or self.is_dc(secondary) or secondary in self.nts or len(info.roles) > 0 or not fieldless(info.node):
        return ""
    return info.base if info.base != primary and self.on_chain(primary, info.base) else ""  # (not primary itself: no consistent MRO)

def gen_declarer(self, c: str, m: str) -> str:
    # the class of c's primary chain whose own body defines method m (an inherited class method
    # that uses cls is a copy of its declaration's, inherit), or ""
    while c in self.classes:
        if self.declares(c, m):
            return c
        c = self.classes[c].base
    return ""

def gen_declares(self, c: str, m: str) -> bool:
    # does class c's own body define method m (an accessor x.setter: its def x)
    nm = m[: m.find(".")] if "." in m else m
    return len([d for d in self.classes[c].node.kids[0].kids if d.kind == "def" and d.s == nm]) > 0

def gen_mro(self, c: str) -> list[str]:
    # CPython's method resolution order of class c (C3), as far as the program's classes go: c,
    # then the merge of its bases' orders and its bases, the primary base and the secondary bases
    # it names (ClassInfo.roles after its base's: subclass_problem rejects one named again); []
    # where they have no consistent order
    info = self.classes[c]
    bases: list[str] = []
    if info.base in self.classes:
        bases.append(info.base)
        bases += info.roles[len(self.classes[info.base].roles) :]
    seqs: list[list[str]] = [self.mro(x) for x in bases]
    seqs.append(bases)
    out = [c]
    while True:
        seqs = [x for x in seqs if len(x) > 0]
        if len(seqs) == 0:
            return out
        head = ""
        for x in seqs:
            if head == "" and len([y for y in seqs if x[0] in y[1:]]) == 0:
                head = x[0]
        if head == "":
            return []
        out.append(head)
        seqs = [y[1:] if y[0] == head else y for y in seqs]

def gen_mro_first(self, order: list[str], m: str) -> str:
    # the first class of method resolution order order whose own body defines method m, or ""
    for c in order:
        if self.declares(c, m):
            return c
    return ""


def gen_slotted_trait(self, cls: str, role: str) -> bool:
    # is secondary base role of class cls a trait (trait_root) whose classes up to cls's chain
    # all declare __slots__ (an empty one): its objects then have no __dict__ in CPython
    c = role
    if self.classes[c].base == "":
        return False
    while c in self.classes and not self.on_chain(cls, c):
        if len([d for d in self.classes[c].node.kids[0].kids if (d.kind == "assign" or d.kind == "annassign") and d.kids[0].kind == "name" and d.kids[0].s == "__slots__"]) == 0:
            return False
        c = self.classes[c].base
    return True

def gen_derives(self, c: str, base: str) -> bool:
    # is c, a class of the program or a builtin exception class, base or derived from it
    while c in self.classes:
        if c == base:
            return True
        info = self.classes[c]
        if base in info.roles:
            return True
        for r in info.roles:
            if self.classes[r].base != "" and self.on_chain(self.classes[r].base, base):
                return True  # (a class its secondary base derives from: role_chain, or a trait's, which c's chain has too)
        if info.excsecond != "" and exc_derives(info.excsecond, base):
            return True
        c = info.base
    return c in EXCBASES and exc_derives(c, base)

def gen_init_template(self, st: Node) -> bool:
    # is class statement st a class template: no decorator (a dataclass's fields are annotated)
    # and an __init__ of its own with a parameter but self that has no annotation, mentions Any,
    # is object, or names a class template; each object belongs to a specialization, whose fields
    # are typed by the arguments of the call that makes it (see specialize)
    if len(st.kids) > 1 or (st.s in self.nts and st.s not in self.cnts):
        return False
    for d in st.kids[0].kids:
        if d.kind == "def" and d.s == "__init__" and len(d.kids) == 3:
            if st.s in self.tparams:
                return True  # (its context can bind variables absent from __init__ parameters)
            ps = d.kids[0].kids
            for i in range(1, len(ps)):
                a = ps[i].kids[0]
                if a.kind == "noann" or (self.any_in([a]) and (not self.dyn_policy(d.line) or ps[i].kind != "param")) or (ps[i].kind == "param" and ((a.kind == "name" and a.s == "object") or self.tmpl_ann(a))):
                    return True  # (also *args or **kwargs without an annotation, or with Any, which only a template takes)
                if st.s in self.tparams and self.names_tv(ps[i].kids[0], self.tparams[st.s]):
                    return True  # (a generic class whose objects bind its type variables, see bind)
            if self.makes_tmpl(d.kids[2]):
                return True  # (a field may hold an object of a class template: typed where the object is made)
    return False

def gen_template_fix(self, cs: list[Node]) -> str:
    # what to change so that classes cs are no class templates: their __init__'s parameters,
    # unless it calls iter() or takes an iterator (an iterator's type is its class)
    for st in cs:
        for d in st.kids[0].kids:
            if d.kind == "def" and d.s == "__init__" and len(d.kids) == 3:
                if reads_builtin(d.kids[2], "iter", False, {}) or len([p for p in d.kids[0].kids if p.kind == "param" and self.iter_item(p.kids[0]) is not None]) > 0:
                    return "an __init__ that calls iter() or takes an Iterator[T] or Iterable[T] makes one (an iterator's type is its class)"
    return "annotate __init__ parameters with concrete types (not Any or object)"

def gen_makes_tmpl(self, n: Node) -> bool:
    # does n call a class template, making an object of one of its specializations? iter(x)
    # makes one of lib's iterator classes (see guess_iter)
    if n.kind == "call" and n.kids[0].kind == "name" and (n.kids[0].s in self.tmpl or (n.kids[0].s == "iter" and len(n.kids) == 2 and ITERS + "$list_iterator" in self.classes)):
        return True
    for k in n.kids:
        if self.makes_tmpl(k):
            return True
    return False

def gen_tmpl_ann(self, a: Node) -> bool:
    # does annotation a name a class template (Box, "Box", Box | None, list[Box])? Each of its
    # specializations being a type of its own, the annotation then types nothing, as if left out;
    # as Iterator[T] and Iterable[T] do, an iterator's type being its class (see iter_)
    if a.kind == "name":
        return a.s in self.tmpl
    if a.kind == "index" and (a.kids[0].kind == "name" or a.kids[0].kind == "attr") and (self.ann_base(a.kids[0]) == "iterator" or self.ann_base(a.kids[0]) == "iterable"):
        return True
    if a.kind == "str" and ("Iterator" in a.s or "Iterable" in a.s):
        return self.tmpl_ann(self.parse_expr(a.s))
    if a.kind == "str":
        w = ""
        for c in a.s + " ":
            if c.isalnum() or c == "_":
                w += c
                continue
            if w in self.tmpl or len([t for t in self.tmpl if t.endswith("$" + w)]) > 0:
                return True
            w = ""
        return False
    if a.kind == "index" and a.kids[0].kind == "name" and a.kids[0].s in self.tparams:
        return self.tmpl_ann(a.kids[1])
    for k in a.kids:
        if self.tmpl_ann(k):
            return True
    return False

def gen_tmpl_of(self, c: str) -> str:
    # the class template that class c is or specializes, or ""
    if c in self.tmpl:
        return c
    return self.classes[c].origin if c in self.classes else ""

def gen_class_problem(self, m: Mod, st: Node, exc: bool) -> str:
    # why a class of an imported module cannot be declared, or "": its __init__ (and the special
    # methods template_ok leaves out) needs annotated parameters, where another method's
    # unannotated ones make it a template, and its body may hold only fields, methods and a
    # docstring
    if len(st.kids) > 2 or (len(st.kids) > 1 and (dc_args(st.kids[1]).startswith("!") or self.imported(st.kids[1].s) != "dataclasses.dataclass")):
        return f"its decorator @{short(st.kids[1].s)} is not supported"
    props: dict[str, bool] = {}  # (its properties, and their setters and deleters: x.setter)
    for b in st.kids[0].kids:
        if b.kind == "def":
            ps = b.kids[0].kids
            deco = b.kids[3].s if len(b.kids) == 4 and len(b.kids[3].kids) == 0 else ""
            static = deco == "staticmethod"
            # @x.setter or @x.deleter on def x after @property def x, once each; @Base.x.setter
            # in a subclass (see accessor and inherit)
            of = deco[: deco.rfind(".")] if "." in deco else ""
            acc = (deco.endswith(".setter") or deco.endswith(".deleter")) and (of == b.s and b.s in props or (exc and of.endswith("." + b.s))) and b.s + deco[deco.rfind(".") :] not in props
            if acc:
                props[b.s + deco[deco.rfind(".") :]] = True
            elif deco == "property":
                props[b.s] = True
            if len(b.kids) > 3 and ((not static and deco != "classmethod" and deco != "property" and not acc) or (b.s.startswith("__") and b.s.endswith("__"))) and not self.stub(m, b):
                return f"method {b.s}() has a decorator"  # (an @overload stub's calls are the error: see declare_fn)
            if len(ps) == 0 and not static:
                return f"method {b.s}() has no {'cls' if deco != '' else 'self'} parameter"
            for i in range(len(ps) if not template_ok(b.s) and not (b.s == "__init__" and not exc and self.init_template(st)) else 0):
                if ps[i].kind != "param":
                    return f"method {b.s}() takes *args or **kwargs"
                if (i > 0 or static) and ps[i].kids[0].kind == "noann":
                    return f"parameter '{ps[i].s}' of method {b.s}() has no type annotation"
        elif not (b.kind == "annassign" and b.kids[0].kind == "name") and not (b.kind == "assign" and len(b.kids) == 2 and b.kids[0].kind == "name") and b.kind != "pass" and not (b.kind == "expr" and (b.kids[0].kind == "str" or b.kids[0].kind == "ellipsis")):
            return "its body holds statements other than fields, methods and a docstring"
    return ""

# ---- definition time. CPython runs an imported module's def and class statements when its
# code runs, used or not. Pystachy compiles the defaults and class bodies it supports there and
# leaves the rest out, which must run no code of the program, and applies no decorator. What
# that code reads must be bound (Loader.deftime; a variable that may not be is checked here).
def gen_eager(self, e: str, why: str, does: str) -> None:
    # e: what the code Pystachy leaves out (for the reason why) may run when CPython does that
    if e != "":
        self.err(f"{why}; CPython {does} when module '{self.curfn.mod}' is imported, and {e}")

def gen_decorators(self, d: Node, decos: list[Node], local: dict[str, str]) -> str:
    # the decorators of def or class statement d: only those that run no code of the program
    # then (local: the names a class body has bound, "p" a property); the outermost one's name
    key = ""
    inst = False  # (object.__new__ has made an object of the class)
    for x in decos:
        self.line = x.line
        root = x.s.split(".")[0]
        key = self.imported(x.s) if "$" in root else x.s if root in PYBUILTINS else ""
        key = key[9:] if key.startswith("builtins.") else key
        if short(root) in local:
            key = "property" if local[short(root)] == "p" and x.s[len(root) :] in [".setter", ".getter", ".deleter"] else ""
        ok = x.s == "async" or (("f" if d.kind == "def" else "c") in INERT_DECOS.get(key, "") and (not inst or ("o" in INERT_DECOS[key] and "__setattr__" not in self.body_names(d))))
        inst = inst or key == "object.__new__"
        e = f"'{short(root)}' may not be the builtin then" if "$" in root and short(root) in PYBUILTINS and key == "" else ""
        e = e if e != "" or len(x.kids) == 0 or key == "dataclasses.dataclass" or key == "ffi.extern" else f"it calls {short(x.s)}()"
        for a in x.kids[0].kids[1:] if len(x.kids) > 0 and key == "dataclasses.dataclass" else []:
            # (@dataclass(...) tests the truth of each option)
            e = e if e != "" else self.effect(a.kids[0], {}, 1) if a.kind == "kw" else "it takes no positional argument"
        if not ok or e != "":
            self.err(f"unsupported decorator @{short(x.s)}: CPython applies it when module '{self.curfn.mod}' is imported" + (f", and {e}" if e != "" else ""))
    return key

def gen_left_out(self, st: Node, why: str) -> None:
    # class statement st of the module's code, which Pystachy leaves out (for the reason why).
    # After one whose body held an operation that may raise and was not evaluated, CPython may
    # have raised there, so the later ones evaluate none (see body_effect)
    m = self.curfn.mod
    if not self.class_effect(st, why, m not in self.unraised):
        self.unraised[m] = True

def gen_class_effect(self, st: Node, why: str, runs: bool = True) -> bool:
    # class statement st, which Pystachy leaves out (for the reason why): CPython evaluates its
    # decorators and bases, runs its body, creates the class and applies the decorators. runs:
    # the statement surely runs there (see body_effect, which gives the result)
    c = st.kids[0] if st.kind == "subclass" else st
    does = f"creates class {short(c.s)}"
    self.decorators(c, c.kids[1:], {})
    for b in st.kids[1:] if st.kind == "subclass" else []:
        self.line = b.line
        x = b.kids[0] if b.kind == "index" or b.kind == "kw" else b
        p = self.path_of(x)
        e = "it passes a metaclass" if b.kind == "kw" and b.s == "metaclass" else "" if b.kind == "typeparams" else self.effect(x, {}, 2 if b.kind == "kw" else 0)
        if e == "" and b.kind != "kw" and x.kind == "name" and x.s in self.hooks:
            h = self.chooks.get(st.line, self.hooks[x.s])  # (a nested class: its base's latest)
            e = f"it calls {h}()" if h != "" else ""
        elif e == "" and b.kind != "kw" and b.kind != "typeparams" and not ("$" not in p and p in PYBUILTINS) and self.imported(p) == "":
            e = f"its base '{short(p)}' may not be a class"  # (its __mro_entries__ may run)
        self.eager(e if e != "" or b.kind != "index" else self.effect(b.kids[1], {}, 2), why, does)
    return self.body_effect(c.kids[0].kids, {}, why, f"runs this statement of the body of class {short(c.s)}", runs)

def gen_body_effect(self, body: list[Node], local: dict[str, str], why: str, does: str, runs: bool = True) -> bool:
    # the statements of a class body Pystachy leaves out (local: the names it has bound). Where
    # they surely run (runs: not in a branch), the operations of their values that may raise
    # (1 // 0) are compiled in order, so that they raise as CPython's do, up to the first one
    # Pystachy does not compile (raisers). False if they hold such an operation, uncompiled
    clear = True
    for b in body:
        self.line = b.line
        k = b.kind
        e = ""
        if k == "def":
            local[b.s] = "p" if self.decorators(b, b.kids[3:], local) == "property" else "f"
            clear = clear and not any(may_raise(x) for x in b.kids[3:])
            for p in b.kids[0].kids:
                self.eager(self.effect(p.kids[1], local, 0), why, does)
                clear = self.raisers(p.kids[1], local, runs and clear) and clear
        elif k == "class" or k == "subclass":
            clear = self.class_effect(b, "nested classes are not supported", runs and clear) and clear
            local[short(b.s)] = "f"
        elif k == "if":
            self.eager(self.effect(b.kids[0], local, 1), why, does)
            clear = self.raisers(b.kids[0], local, runs and clear) and clear
            yes = self.body_effect(b.kids[1].kids, local, why, does, False)
            no = self.body_effect(b.kids[2].kids, local, why, does, False)
            clear = clear and yes and no
        elif k == "assign" or k == "annassign" or k == "augassign" or k == "expr":
            # (CPython calls a class attribute's __set_name__, each unpacked one's too)
            ts: list[str] = []
            u = 0 if k == "expr" else 2 if k == "augassign" else 1
            for t in b.kids[:-1] if k == "assign" else b.kids[:1] if k == "augassign" or len(b.kids) == 3 else []:
                u = 2 if t.kind == "tuple" or t.kind == "list" else u
                e = e if e != "" or not (has_kind(t, "attr") or has_kind(t, "index") or has_kind(t, "slice")) else "it assigns to an attribute or item, which may run code"
                names_in(t, ts)
            e = e if e != "" or k != "augassign" else self.effect(b.kids[0], local, 2)
            if e == "" and (k != "annassign" or len(b.kids) == 3):
                e = self.effect(b.kids[-1], local, u)
                if e == "":
                    # (then an unpacking, or an augmented assignment's division, may raise)
                    clear = self.raisers(b.kids[-1], local, runs and clear) and clear and not (u == 2 and (k != "augassign" or raising_op(b.s)))
            for nm in ts:
                local[nm] = ""
            self.eager(e, why, does)
        elif k == "del":
            for t in b.kids:
                e = e if e != "" or (t.kind == "name" and "$" not in t.s and t.s in local) else "it deletes what the class body has not bound"
                local.pop(t.s, "")
            self.eager(e, why, does)
        elif k != "pass":
            k = "import" if k.endswith("import") else k
            self.eager(f"Pystachy does not check what {'an' if k[0] in 'aeiou' else 'a'} '{k}' statement there runs", why, does)
    return clear

def gen_raisers(self, e: Node, local: dict[str, str], run: bool) -> bool:
    # value e of a class body Pystachy leaves out (local: the names it has bound): where it
    # surely runs (run), its operations that may raise (raising) and that Pystachy computes as
    # CPython does (plain) are compiled in CPython's order, their values dropped, so that they
    # raise as CPython's do. False if e holds such an operation that is not compiled: CPython
    # may raise there first, so nothing after it is compiled
    if not may_raise(e):
        return True
    if not run:
        return False
    k = e.kind
    if raising(e) and self.plain(e, local) != "":
        self.expr(e, "")
        return True
    n = len(e.kids)
    if k == "ifexp" or k == "boolop" or k == "cmp":
        n = 2 if k == "cmp" else 1  # (the operands that surely run)
    elif k not in ["binop", "unary", "index", "slice", "call", "attr", "tuple", "list", "set", "dict", "starred", "dstar", "dictstar"]:
        return False
    for x in e.kids[:n]:
        if not self.raisers(x.kids[0] if x.kind == "kw" else x, local, True):
            return False
    return not raising(e) and not any(may_raise(x) for x in e.kids[n:])

def gen_plain(self, e: Node, local: dict[str, str]) -> str:
    # the type of value e of a class body Pystachy leaves out (local: the names it has bound) if
    # Pystachy computes e as CPython does, else "": a literal, a variable of the module of a
    # builtin type, or one of these operations on them, which may raise: //, % and / of numbers,
    # an index of a list or dict, int() of a str literal and min() and max() of a list. Not
    # where CPython's would compute an int beyond 64 bits, which Pystachy's raise OverflowError
    # for (see docs/language.md, Deviations), nor an index of a str or min() of one, which count
    # its bytes
    k = e.kind
    if k == "unary" and e.s == "-" and (e.kids[0].kind == "int" or e.kids[0].kind == "float"):
        return self.plain(e.kids[0], local)
    if k == "int":
        d = e.s[1:] if e.s.startswith("-") else e.s
        return "int" if len(d) < 19 or (len(d) == 19 and d <= "9223372036854775807") else ""  # (else an error, see expr)
    if k == "float" or k == "str":
        return k
    if k == "name":
        t = self.gtypes.get(e.s, "")
        ok = t == "int" or t == "float" or t == "str" or ((is_list(t) or is_dict(t)) and "?" not in t and not self.objects(t, 2))
        return t if "$" in e.s and ok else ""  # (not a name the body bound, which is not qualified)
    if k == "binop" and (e.s == "//" or e.s == "%" or e.s == "/"):
        a = self.plain(e.kids[0], local)
        b = self.plain(e.kids[1], local)
        if (a != "int" and a != "float") or (b != "int" and b != "float"):
            return ""
        r = int_lit(e.kids[1])
        if e.s == "//" and a == "int" and b == "int" and int_lit(e.kids[0]) == "" and (r == "" or r == "-1"):
            return ""  # (it may be -2**63 // -1)
        return "float" if e.s == "/" or a == "float" or b == "float" else "int"
    if k == "index":
        o = self.plain(e.kids[0], local)
        i = self.plain(e.kids[1], local)
        if is_list(o) and i == "int":
            return elem(o)
        return targs(o)[1] if is_dict(o) and i != "" and i == targs(o)[0] else ""
    if k == "call" and len(e.kids) == 2 and e.kids[0].kind == "name":  # (one argument: not a keyword, see a)
        f = e.kids[0].s
        a = self.plain(e.kids[1], local)
        if f not in RAISERS or f in local or self.bound(f) or a == "":
            return ""
        if f == "int":
            return "int" if e.kids[1].kind == "str" and short_ascii(e.kids[1].s) else ""
        return elem(a) if is_list(a) and (elem(a) == "int" or elem(a) == "float" or elem(a) == "str") else ""
    return ""

def gen_body_names(self, c: Node) -> dict[str, bool]:
    # the names class statement c's body binds, by assignment or def
    out: dict[str, bool] = {}
    collect(c.kids[0].kids, out)
    for b in c.kids[0].kids:
        if b.kind == "def":
            out[b.s] = True
    return out

def gen_hook(self, st: Node) -> None:
    # class statement st, in the order statements run: chooks[its line], what creating it calls
    # of its bases (by their class statements so far); hooks[its name], what subclassing or
    # subscripting it calls: the __init_subclass__ or __class_getitem__ it or its bases bind
    h = ""
    for b in st.kids[1:] if st.kind == "subclass" else []:
        x = b.kids[0] if b.kind == "index" else b
        if h == "" and x.kind == "name":
            h = self.hooks.get(x.s, "")
    self.chooks[st.line] = h
    own = self.body_names(st.kids[0] if st.kind == "subclass" else st)
    for nm in ["__init_subclass__", "__class_getitem__"]:
        if nm in own:
            h = f"{short(st.s)}.{nm}"
    self.hooks[st.s] = h
    self.cnodes[st.line] = st

def gen_path_of(self, n: Node) -> str:
    # the dotted name an attribute chain spells (its first name qualified), or ""
    if n.kind == "name":
        return n.s
    if n.kind == "attr" and self.path_of(n.kids[0]) != "":
        return self.path_of(n.kids[0]) + "." + n.s
    return ""

def gen_objects(self, t: str, use: int) -> bool:
    # may a value of type t be an object of one of the program's classes (use 2: or hold one)
    return len([x for x in t.replace("[", ",").replace("]", ",").split(",") if x in self.classes and (use >= 2 or x == t)]) > 0

def gen_pure(self, q: str) -> bool:
    # does a call of q, a builtin or a builtin module's function given builtin values, run no
    # code of the program and change nothing (or is q a builtin module's value)
    i = self.imported(q)
    return ("$" not in q and q in PURE) or i in PURE or i in MODATTRS or i.startswith("math.") or i.startswith("os.path.")

def gen_effect(self, e: Node, local: dict[str, str], use: int) -> str:
    # what evaluating e, which Pystachy leaves out, may run of the program's code ("" if
    # nothing): it may read names (checked here if they may be unbound, as in read()) and apply
    # builtin operations to values of builtin types. use: then CPython 0 stores the value, 1 may
    # call its methods (an operand, an argument, a truth test, a class attribute's
    # __set_name__), 2 its items' too (a set item, a dict key), 3 may call it too (an argument
    # of a builtin function). local: the class body's names
    k = e.kind
    if k == "name" or k == "attr" or k == "str":
        self.modchk(e)
    p = self.path_of(e) if k == "name" or k == "attr" else ""
    q = self.imported(p)
    if use == 3 and (k == "lambda" or (q != "" and not self.pure(p))):
        return f"it passes {short(p) if p != '' else 'a lambda'} to a function that may call it"
    if k in INERT or is_const(e) or q != "" or (k == "lambda" and not e.s.startswith("=")) or (k == "badattr" and e.s.endswith("cannot be used as a value")):
        return ""
    if k == "name":
        if (e.chk or self.foreign(e.s)) and e.s in self.gflag:
            self.flagged[e.s] = True
            self.guard(self.scalar('xor', [Val(self.mload('bool', f'@g.{e.s}.def'), 'bool'), Val('true', 'bool')]), self.unbound(e.s))
        t = self.gtypes.get(e.s, "")
        if use == 3 and (e.s in self.funcs or e.s in self.hooks or ("$" not in e.s and (e.s in local or (e.s in PYBUILTINS and e.s not in PURE)))):
            return f"it passes {short(e.s)} to a function that may call it"
        # (a generic class's type parameter, Class$$T, is typing's TypeVar: see Loader.qren)
        if use == 0 or "$" not in e.s or "$$" in e.s or e.s in self.funcs or e.s in self.hooks or e.s in self.noneglobals or (t != "" and not self.objects(t, use)):
            return ""
        return f"'{short(e.s)}' may be an object of one of the program's classes, whose methods CPython calls then"
    if k == "attr" and e.kids[0].kind == "name" and (e.kids[0].s in self.hooks or ("$" not in e.kids[0].s and e.kids[0].s in local)):
        # (a class's attribute: a method, or a field of a class Pystachy compiles, or what? A
        # field's class may define __get__, which reading it calls)
        ci = self.classes[e.kids[0].s] if e.kids[0].s in self.classes else ClassInfo("", e)
        t = ci.ftypes.get(e.s, "")
        if use < 3 and (e.s in ci.methods or ((t != "" or use == 0) and not self.objects(t, use if use > 0 else 1))):
            return self.effect(e.kids[0], local, 0)
        return f"it passes {short(p)} to a function that may call it" if use == 3 else f"'{short(p)}' may be an object of one of the program's classes, whose methods CPython calls then"
    if k == "call":
        f = e.kids[0]
        q = self.path_of(f)
        wrap = "$" not in q and (q == "classmethod" or q == "staticmethod" or q == "property")
        # (a method of a builtin value that only reads it)
        rt = f.kids[0].kind if f.kind == "attr" and f.kids[0].kind in ["str", "int", "float"] else self.gtypes.get(self.path_of(f.kids[0]), "") if f.kind == "attr" else ""
        method = rt in ["str", "int", "float", "bool"] or (rt.split("[")[0] in ["list", "dict", "tuple"] and f.s in ["get", "keys", "values", "items", "copy", "count", "index"] and not self.objects(rt, 2))
        if not wrap and not method and not self.pure(q):
            return f"it calls {short(q)}()" if q != "" else "it calls a function"
        r = self.effect(f.kids[0], local, 1) if method else ""
        for a in e.kids[1:]:
            r = r if r != "" else self.effect(a.kids[0] if a.kind == "kw" else a, local, 0 if wrap else 3)
        return r
    if (k == "index" or k == "slice") and e.kids[0].kind == "name" and self.hooks.get(e.kids[0].s, "") != "":
        return f"it calls {self.hooks[e.kids[0].s]}()"
    if k == "lambda" or k == "badattr":
        return e.s if k == "badattr" else "Pystachy does not check the default values of its lambda"
    if k not in ["attr", "index", "slice", "binop", "unary", "cmp", "boolop", "ifexp", "fstr", "fmt", "tuple", "list", "set", "dict", "starred", "dstar", "dictstar"]:
        return f"Pystachy does not check what {'a comprehension' if k.endswith('comp') else 'an assignment expression' if k == 'walrus' else 'a ' + k + ' expression'} there runs"
    for i in range(len(e.kids)):
        # (an operand or set item: 2; a truth test or an attribute's object: 1; the container
        # indexed: its items too if the item is used, called if it is; a tuple's, list's or
        # dict's item, an if-else's or boolop's value: as the whole, unpacked: its items too)
        u = 2 if k != "attr" else 1
        if k == "ifexp" or k == "boolop":
            u = 1 if k == "ifexp" and i == 0 else use if k == "ifexp" or use > 1 else 1
        elif (k == "index" or k == "slice") and i == 0:
            u = 3 if use == 3 else 1 if use == 0 else 2
        elif k == "tuple" or k == "list" or (k == "dict" and i % 2 == 1):
            u = use if use > 1 else 0
        elif k == "starred" or k == "dstar" or k == "dictstar":
            u = use if use > 2 else 2
        r = self.effect(e.kids[i], local, u)
        if r != "":
            return r
    return ""

def gen_partly(self, e: Node, use: int) -> str:
    # (part of) a default value Pystachy cannot compile, used as effect() says: CPython evaluates
    # it, Pystachy the items of displays it can compile; what the rest may run (effect)
    if self.default_problem(e, "") == "":
        t = self.expr(e, "").t if not is_const(e) else ""
        return "an item may be an object of one of the program's classes, whose methods CPython calls then" if use > 0 and self.objects(t, use) else ""
    r = ""
    for i in range(len(e.kids) if e.kind in ["tuple", "list", "set", "dict"] else 0):
        r = r if r != "" else self.partly(e.kids[i], 2 if e.kind == "set" or (e.kind == "dict" and i % 2 == 0) else use)
    return r if e.kind in ["tuple", "list", "set", "dict"] else self.effect(e, {}, use)

def gen_generic_aliases(self, body: list[Node]) -> None:
    # CPython's idiom for a generic class, __class_getitem__ = classmethod(GenericAlias) of types in a
    # class body (also in a block, a function or another class), which makes C[...] a
    # types.GenericAlias: left out, as it defines nothing Pystachy has, and the class recorded
    # (galias), whose subscripts at run time are an error (index())
    for st in body:
        c = st.kids[0] if st.kind == "subclass" else st
        if c.kind == "class":
            keep: list[Node] = []
            for x in c.kids[0].kids:
                v = x.kids[1] if x.kind == "assign" and len(x.kids) == 2 and x.kids[0].kind == "name" and x.kids[0].s == "__class_getitem__" else x
                if v.kind == "call" and len(v.kids) == 2 and v.kids[0].kind == "name" and v.kids[0].s == "classmethod" and "classmethod" not in self.funcs and self.imported_ref(v.kids[1]) == GALIAS:
                    self.galias[c.s] = True
                else:
                    keep.append(x)
            c.kids[0].kids = keep if len(keep) > 0 else [mk("pass", "", c.line, [])]
        for k in c.kids:
            if k.kind == "block":
                self.generic_aliases(k.kids)
            elif k.kind == "except":
                self.generic_aliases(k.kids[1].kids)


def gen_abstract_defs(self, body: list[Node]) -> list[Node]:
    # the class statements of a module's body as the compiler applies abc's ABCMeta to them: a
    # method's @abstractmethod (the loader's qdeco names it abc$abstractmethod) is left out, the
    # method recorded as one of its class's abstract methods (abstracts), and metaclass=ABCMeta
    # is left out of a class statement's bases, the class recorded as one that makes such
    # methods abstract (abcmeta). A class statement that it leaves without a base is a plain one
    out: list[Node] = []
    for st in body:
        if st.kind == "subclass":
            keep = [st.kids[0]]
            for b in st.kids[1:]:
                if b.kind == "kw" and b.s == "metaclass" and b.kids[0].kind == "name" and b.kids[0].s == "abc$ABCMeta":
                    self.abcmeta[st.s] = True
                else:
                    keep.append(b)
            st.kids = keep
            if len(keep) == 1:
                st = keep[0]
        c = st.kids[0] if st.kind == "subclass" else st
        if c.kind == "class":
            for d in c.kids[0].kids:
                if d.kind == "def" and any(x.kind == "deco" and x.s in ABSTRACT_DECOS for x in d.kids[3:]):
                    keep = d.kids[:3]
                    for x in d.kids[3:]:
                        if x.kind != "deco" or x.s not in ABSTRACT_DECOS:
                            keep.append(x)
                        elif ABSTRACT_DECOS[x.s] != "":
                            keep.append(mk("deco", ABSTRACT_DECOS[x.s], x.line, []))  # (@abstractproperty: @property)
                    d.kids = keep
                    if st.s not in self.abstracts:
                        self.abstracts[st.s] = []
                    if d.s not in self.abstracts[st.s]:
                        self.abstracts[st.s].append(d.s)
        out.append(st)
    return out

def gen_abstract_of(self, c: str) -> list[str]:
    # the abstract methods class c leaves without an implementation (sorted), as CPython's
    # ABCMeta finds them, where c derives from abc.ABC or a class statement passes
    # metaclass=ABCMeta: those of its own (abstract_defs), and those of its base that it does
    # not define again
    ci = self.classes[c]
    if not self.abc_class(c):
        return []
    out = [n for n in self.abstracts.get(c, [])]
    if ci.base in self.classes:
        defined: list[str] = []  # (what its body binds: a def, or a class attribute)
        for st in ci.node.kids[0].kids:
            if st.kind == "def":
                defined.append(st.s)
            elif (st.kind == "assign" or st.kind == "annassign") and st.kids[0].kind == "name":
                defined.append(st.kids[0].s)
        for n in self.abstract_of(ci.base):
            if n not in out and n not in defined:
                out.append(n)
    return sorted(out)

def gen_abc_class(self, c: str) -> bool:
    # does class c derive from abc.ABC, or from a class whose statement passes metaclass=ABCMeta
    while c in self.classes:
        if c == "abc$ABC" or c in self.abcmeta:
            return True
        c = self.classes[c].base
    return False

def gen_program(self, mods: list[Mod]) -> str:
    started = timing_start()
    phase = "runtime" if self.rtmode else "program"
    self.opts = optimizations()
    self.identity_modules(mods)  # (which modules' code tracks numeric identity: dynamic.py)
    # (lib's modules of range objects and of object()'s bind no global of another module: the
    # names they bind do not keep a global of the program from being constant)
    own = [m for m in mods if m.name != RANGES and m.name != OBJECTS]
    if "moduleints" in self.opts:
        self.intglobals = module_ints(own, self.intat)
    self.strglobals = module_strs(own, self.strtuples)
    for m in mods:
        m.body.kids = self.abstract_defs(m.body.kids)
    # the modules in the order their code may first run, the main program last
    tops: list[list[Node]] = []
    props: dict[str, bool] = {}
    for m in mods:
        refl_props(m.body, props)
    for m in mods:
        self.scan_imports(m.body.kids)
        self.eh = self.eh or needs_eh(m.body.kids) or self.ext != ""  # (an extension's calls are tries)
        self.eh = self.eh or refl_needs_eh(m.body, props)  # (reflection.py: a getter's AttributeError caught)
        self.gproto = self.gproto or uses_protocol(m.body)  # (generators: send(), throw(), a yield's value)
        self.excread = self.excread or reads_handled(m.body)  # (sys.exception() in a generator)
        self.causeread = self.causeread or reads_cause(m.body)  # (e.__cause__: lib/contextlib.py's)
        for q in m.taliases:
            self.taliases[q] = m.taliases[q]
        self.typevars.extend(m.deftps)
    if dynamic_program() and any(defines(m.body, "__len__") or defines(m.body, "__next__") or module_reads(m.body, "getattr") for m in mods):
        # Dynamic next, length hints and getattr(default) catch protocol exceptions.
        # module_reads also finds qualified/imported/aliased builtin references.
        self.eh = True
    if any(defines(m.body, "__len__") for m in mods) and any(defines(m.body, "__iter__") for m in mods):
        self.eh = True  # typed consumers also ignore TypeError from optional length hints
    if not self.eh and len([m for m in mods if defines(m.body, "__next__")]) > 0:
        # a __next__ method's StopIteration is caught where a loop (or unpacking, in, a consumer)
        # takes the items of an object through its __iter__ (obj_iterator, the only way to an
        # iterator object's), and by next(it, default) (not range's __iter__, which steps through
        # a list)
        self.eh = dynamic_program() or len([m for m in mods if (defines(m.body, "__iter__") and m.name != RANGES) or module_reads(m.body, "next")]) > 0
    for m in mods:
        self.generic_aliases(m.body.kids)
    for m in mods:
        m.body.kids = self.typing_forms(m, m.body.kids, False)
        for i in range(len(m.body.kids)):
            st = m.body.kids[i]
            if st.kind == "subclass" and len(st.kids) == 2 and self.nt_base(st.kids[1]):
                m.body.kids[i] = st.kids[0]  # class P(NamedTuple): a class (see nt_class)
                self.nts[st.s] = True
            elif st.kind == "subclass" and st.kids[1].kind == "namedtuple":
                # NAME = namedtuple(...): a NamedTuple that is a class template, its fields typed by
                # each call (Loader.nt_class); the class's name is the call's typename
                m.body.kids[i] = st.kids[0]
                self.nts[st.s] = True
                self.cnts[st.s] = st.kids[1]
                if st.kids[1].s != short(st.s):
                    RENAMED[st.s] = st.kids[1].s
            elif st.kind == "subclass" and len(st.kids) == 2 and len(self.generic_base(st.kids[1])) > 0:
                m.body.kids[i] = st.kids[0]  # class C(Generic[T]): a class whose objects bind T (see bind)
                self.tparams[st.s] = self.generic_base(st.kids[1])
            elif st.kind == "subclass" and len(st.kids) > 2 and self.generic_traits(st) > 0:
                # class N(Generic[T], A[T], B[T]): generic class N's other bases (generic_subclass)
                gk = self.generic_traits(st)
                self.tparams[st.s] = self.generic_base(st.kids[gk])
                st.kids = [st.kids[j] for j in range(len(st.kids)) if j != gk]
            elif st.kind == "subclass" and st.kids[1].kind == "typeparams" and self.class_params(st) == "":
                m.body.kids[i] = st.kids[0]  # class C[T]: as class C(Generic[T]) (see class_params)
                self.tparams[st.s] = st.kids[1].s.split()
                self.pep695[st.s] = True
            elif self.typevar_def(st):
                self.typevars.append(st.kids[0].s)
                m.body.kids[i] = mk("pass", "", st.line, [])
            elif st.kind == "typealias" and st.s in self.taliases:
                m.body.kids[i] = mk("pass", "", st.line, [])  # (a type alias, which only annotations name)
            elif st.kind == "assign" and st.kids[0].kind == "name" and st.kids[0].s in self.taliases and self.taliases[st.kids[0].s] is st and not self.alias_kept(st.kids[0].s):
                m.body.kids[i] = mk("pass", "", st.line, [])
    for q in self.taliases:
        # (CPython evaluates an assigned alias's value where it assigns it, a type statement's
        # only where its __value__ is read)
        why = self.alias_problem(self.taliases[q].kids[1]) if self.taliases[q].kind == "assign" else ""
        if why != "":
            self.line = self.taliases[q].line
            self.err(why[1:] if why.startswith("!") else f"{why} (CPython evaluates this type alias's value when the assignment runs)")
    if len(self.taliases) > 0:
        self.recursive_aliases()
        # an annotation that names a type alias is its value (unalias)
        for m in mods:
            self.unalias_all(m.body)
    class_counts: dict[str, int] = {}
    for m in mods:
        for st in m.body.kids if m.name != "" else []:
            if st.kind == "class" or st.kind == "subclass":
                class_counts[st.s] = class_counts.get(st.s, 0) + 1
    for m in mods:
        for st in m.body.kids:
            self.line = st.line
            why = ""
            if st.kind == "class" or st.kind == "subclass":
                self.hook(st)
            if (st.kind == "class" or st.kind == "subclass") and class_counts.get(st.s, 0) > 1:
                # Imported redefinitions cannot share one native class. Leave every body
                # to class_effect in statement order, retaining each base's hook snapshot;
                # keeping the earlier ClassInfo would silently construct the stale class.
                why = f"redefinition of class '{st.s}' is not supported"
            elif st.kind == "subclass":
                why = self.generic_subclass(st)
                if why == "":
                    why = self.subclass_problem(st)
                if why == "" and m.name != "":
                    why = self.class_problem(m, st.kids[0], True)
            elif st.kind == "class" and m.name != "":
                why = self.class_problem(m, st, False)
            if why != "" and m.name == "":
                self.err(why)
            if why != "":
                # a class of an imported module that Pystachy cannot compile: an error only
                # where the program uses it
                self.unsupported[st.s] = f"class {shown(st.s)} is not supported: {why}"
            elif st.kind == "subclass":
                # an ordinary class or an exception class (subclass_problem)
                if st.s in self.classes:
                    self.err(f"redefinition of class '{st.s}' is not supported")
                ci = ClassInfo(st.s, st.kids[0])
                ci.mod = m.name
                ci.base = st.kids[1].s if st.kids[1].kind == "name" and st.kids[1].s in self.classes else self.exc_base(st.kids[1])
                ci.exc = self.classes[ci.base].exc if ci.base in self.classes else ci.base
                if ci.exc == "":
                    # (its base's secondary bases, then its own: subclass_problem)
                    ci.roles = list(self.classes[ci.base].roles)
                    for b in st.kids[2:]:
                        if b.s not in ci.roles:
                            ci.roles.append(b.s)
                elif len(st.kids) == 3:
                    ci.excsecond = self.exc_base(st.kids[2])
                self.classes[st.s] = ci
                if self.is_dc(st.s):
                    # a dataclass deriving from another (subclass_problem): frozen as its base is
                    self.dc_options(ci)
                    if "frozen" in self.classes[ci.base].dcopts and "frozen" not in ci.dcopts:
                        self.err("cannot inherit non-frozen dataclass from a frozen one")  # (CPython's TypeError where it creates the class)
                    if "frozen" in ci.dcopts and "frozen" not in self.classes[ci.base].dcopts:
                        self.err("cannot inherit frozen dataclass from a non-frozen one")
            elif st.kind == "class":
                if st.s in self.classes:
                    self.err(f"redefinition of class '{st.s}' is not supported")
                self.classes[st.s] = ClassInfo(st.s, st)
                self.classes[st.s].mod = m.name
                self.dc_options(self.classes[st.s])
    for m in mods:
        self.any_variables(m.body, False)
    # Only ordinary inheritance hierarchies need a runtime class tag. Keeping unrelated
    # classes unchanged preserves their compact layout, including dataclasses and tuples.
    for ci in self.classes.values():
        if ci.exc == "" and ci.base in self.classes:
            ci.tag = 1
            self.classes[ci.base].tag = 1
            for named in ci.roles:
                if named in self.classes[ci.base].roles:
                    continue
                # (an interface's own chain, role_chain: each class of it is a secondary base of
                # this class too, and of the objects that a value of its type may be)
                chain = self.role_chain(ci.base, named)
                for role in chain if len(chain) > 0 else [named]:
                    self.classes[role].tag = 1
                    self.classes[role].isrole = True
                    self.classes[role].isiface = self.classes[role].isiface or len(chain) > 0
                    # These unrelated static types can now denote the same instance: the
                    # primary ancestors, and the other secondary bases, each with the classes
                    # it extends (role_chain).
                    others: list[str] = []
                    for r in ci.roles:
                        if r != named:
                            extended = self.role_chain(ci.base, r)
                            others += extended if len(extended) > 0 else [r]
                    ancestor = ci.base
                    while ancestor in self.classes:
                        if not self.on_chain(role, ancestor):  # (a trait's own bases are its bases)
                            others.append(ancestor)
                        ancestor = self.classes[ancestor].base
                    for other in others:
                        if role not in self.classes[other].overlaps:
                            self.classes[other].overlaps.append(role)
                            self.classes[role].overlaps.append(other)
    tag = 0
    for ci in self.classes.values():
        if ci.tag != 0:
            tag += 1
            ci.tag = tag
    self.cm_exits()  # (decided while the class templates are classes too: see cm_exits)
    grow = True
    while grow:
        # the class templates: an __init__ parameter without an annotation, or with one that
        # names a class template (Holder(b: Box)), which then types nothing either
        grow = False
        for ci in self.classes.values():
            if ci.name not in self.tmpl and ci.exc == "" and self.init_template(ci.node):
                self.tmpl[ci.name] = True
                grow = True
    for ci in self.classes.values():
        if ci.tag != 0 and ci.name in self.tmpl:
            self.line = ci.node.line
            self.err("inheritance with generic class templates is not supported: " + self.template_fix([ci.node]))
    for m in mods:
        # (made now: a specialization that a declaration's annotation names may compile a
        # method whose call needs a default's type, which its module's frame gives, see modtype)
        self.inits[m.name] = FnInfo("<module>", "@init." + m.name if m.name != "" else "@main.init", m.body, "")
        self.inits[m.name].mod = m.name
    for m in mods:
        top: list[Node] = []
        for st in m.body.kids:
            self.line = st.line
            if self.rtmode and m.name == "" and (st.kind != "def" or self.applies(st, True, {})) and st.kind != "import" and st.kind != "pass" and not (st.kind == "expr" and st.kids[0].kind == "str"):
                # nothing runs runtime.py's module code: pys_init comes before any program code
                self.err("runtime.py may hold only functions, imports and docstrings at module level")
            if st.kind == "def" and self.applies(st, True, {}):
                # a def whose decorators CPython calls on the function: module code makes the
                # function and binds its name to what they give (decorate), a module variable
                for dk in st.kids[3:]:
                    root = dk.s[: dk.s.find(".")] if "." in dk.s else dk.s
                    if root in TYPING and self.imported(root) == "" and not self.bound(root):
                        self.line = dk.line
                        self.err(f"name '{root}' is not defined (import it from typing)")
                if st.s in self.funcs or st.s in self.classes or st.s in self.decorated:
                    self.err(f"redefinition of '{st.s}' is not supported")
                self.decorated[st.s] = True
                top.append(st)
            elif st.kind == "def":
                if st.s in self.funcs or st.s in self.classes or st.s in self.decorated:
                    self.err(f"redefinition of '{st.s}' is not supported")
                self.lib = m.name != ""
                self.funcs[st.s] = self.declare_fn(st, "")
                self.lib = False
                self.funcs[st.s].mod = m.name
                if st.s == "collections$namedtuple" and m.path == self.libdir + "/collections/__init__.py":
                    # (lib's, which the compiler carries out: Loader.nt_class)
                    self.funcs[st.s].bad = "namedtuple() is only supported as NAME = namedtuple(...) in a module's top-level code, with literal arguments (the compiler makes the class)"
                top.append(mk("defaults", st.s, st.line, []))
            elif (st.kind == "class" or st.kind == "subclass") and st.s not in self.classes:
                top.append(mk("lclass", st.s, st.line, []))  # (a class it leaves out: class_effect)
            elif st.kind == "class" or st.kind == "subclass":
                for d in self.classes[st.s].node.kids[0].kids:
                    if d.kind == "def":
                        self.line = d.line
                        key = d.s + self.accessor(self.classes[st.s], d)
                        if key in self.classes[st.s].methods:
                            self.err(f"redefinition of method '{st.s}.{d.s}' is not supported")
                        self.lib = m.name != ""
                        self.selfcls = st.s
                        g = self.declare_fn(d, st.s)
                        self.selfcls = ""
                        self.lib = False
                        g.mod = m.name
                        if "." in g.accof:
                            g.accof = self.class_ref(m, g.accof[: g.accof.rfind(".")]) + g.accof[g.accof.rfind(".") :]  # (@Base.x.setter)
                        self.classes[st.s].methods[key] = g
                top.append(mk("cdefaults", st.s, st.line, []))
            else:
                top.append(st)
        tops.append(top)
    for ci in self.classes.values():
        self.inherit(ci)
    for ci in [x for x in self.classes.values()]:
        # (a dataclass's field annotated C[X] makes that specialization of generic class C here,
        # which specialize declares itself)
        self.selfcls = ci.name
        self.declare_fields(ci)
        if self.dyn_policy(ci.node.line):
            comparison_properties(ci)
        self.selfcls = ""
        ci.bad = ci.bad if ci.bad != "" else ci.hook  # (after the problems declare_fields finds, see hoist_class)
        for f in ci.methods.values():
            self.check_special(f)
    comparison_storage(self)
    for m in mods:
        self.cvar_stores(m.body.kids)
    for m in mods:
        imps: list[str] = []
        all_imports(m.body.kids, imps)
        self.deps[m.name] = " ".join(imps)
    # the import graph's strongly connected components (see user_call)
    num: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    for m in mods:
        if m.name not in num:
            self.scc(m.name, num, low, stack)
    # each module's functions and classes, in the order they were declared
    mfns: dict[str, list[FnInfo]] = {}
    mcls: dict[str, list[ClassInfo]] = {}
    for m in mods:
        mfns[m.name] = []
        mcls[m.name] = []
    for f in self.funcs.values():
        mfns[f.mod].append(f)
    for ci in self.classes.values():
        mcls[ci.mod].append(ci)
    for i in range(len(mods)):
        self.flow_program(tops[i], mods[i].name, mfns[mods[i].name], mcls[mods[i].name], i == 0)
    for nm in self.gflag:
        if nm in self.funcs or nm in self.classes:
            self.global_var(f"@g.{nm}.def", "bool")
    for m in mods:
        # a module global that module code only sets to None (an optional accelerator's
        # fallback, _json = None, or a cache a function fills, _varsub = None) and that is
        # assigned before any read is the constant None; a compiled function that gives it
        # another value is an error (in the program's module, one whose global statement
        # binds it is left to the advice to annotate it)
        vals: dict[str, list[Node]] = {}
        none_assigns(m.body.kids, vals)
        for nm in vals:
            nones = True
            for v in vals[nm]:
                if v.kind != "None":
                    nones = False
            if nones and nm not in self.gflag and nm in self.mvars and (m.name != "" or nm not in m.fnglobal):
                self.noneglobals[nm] = True
        if m.falseat >= 0:
            self.constflags[m.q + "TYPE_CHECKING"] = "False"
        for nm in m.flagat:
            self.constflags[m.q + nm] = "True" if m.flagval[nm] == 1 else "False"
    docinfer: dict[str, bool] = {}
    for m in mods:
        for st in m.body.kids if m.name != "" else []:
            if st.kind == "assign" and st.s == "docinit":
                docinfer[st.kids[0].s] = True
    for m in mods:
        for st in m.body.kids if m.name != "" else []:
            # The loader's implicit __doc__ value exists before a circular import can read
            # it. Its optional type must precede the later literal's usual predeclaration.
            if st.kind == "annassign" and st.s == "docinit":
                self.declare(st.kids[0].s, self.vtype(st.kids[1]))
            # an imported module's constants (NAME = literal) are typed before any module code
            # compiles: a module it imports, which imports it back, may read them first
            if st.kind == "assign" and len(st.kids) == 2 and st.kids[0].kind == "name" and st.kids[0].s not in self.gtypes and st.kids[0].s not in self.noneglobals and st.kids[0].s not in docinfer:
                k = st.kids[1].kids[0].kind if st.kids[1].kind == "unary" and is_const(st.kids[1]) else st.kids[1].kind  # (-1, -2.5)
                if k == "int" or k == "float" or k == "str":
                    self.declare(st.kids[0].s, k)
                elif k == "True" or k == "False":
                    self.declare(st.kids[0].s, "bool")
    for m in mods:
        self.mfile[m.name] = m.path[2:] if m.path.startswith("./") else m.path
    timing_end(phase + ".prepare", started)
    started = timing_start()
    self.compiling = True
    self.modlevel = True
    for m in mods:
        for st in m.body.kids if m.name != "" else []:
            if st.kind == "assign" and st.s == "docinit" and st.kids[0].s not in self.noneglobals:
                name = st.kids[0].s
                fr = self.modframe(m.name, st.line)
                t = self.none_type(name)
                self.restore(fr)
                self.line = st.line
                if t == "":
                    self.err(f"cannot infer the initial optional type of '{short(name)}'; annotate its later assignment")
                self.declare(name, t)
    for i in range(len(mods)):
        if mods[i].name != ITERS and mods[i].name != RANGES and mods[i].name != OBJECTS:
            # (lib's modules of iter()'s classes, of range's and of object's run no code: nothing
            # imports them, see Loader.program)
            self.function(self.inits[mods[i].name], tops[i])
        self.inited[mods[i].name] = True
    self.modlevel = False
    # the functions and methods of imported modules are compiled only if the program calls
    # them, as templates are (a function compiled early, see early, is compiled already)
    for f in self.funcs.values():
        if f.extern and not self.rtmode:
            self.cextern(f)
        elif f.mod != "" and not f.generic:
            self.lazy[f.ll] = f
        elif f.extern:
            self.line = f.node.line
            for t in f.ptypes + [f.ret]:
                if t == "bool" or t == "":
                    self.err(f"C function {f.name}() takes or returns {typestr(t) if t != '' else 'an untyped value'}: the runtime ABI passes bools as int")
            have = [lt(f.ret)] + [lt(t) for t in f.ptypes]
            if f.ll[1:] in RTSYM:
                # one the compiler calls too: declared once, from RUNTIME, whose types it must have
                e = RtFn(RTSYM[f.ll[1:]]).ll
                if have != e:
                    self.err(f"{f.name}() is declared as {have[0]}({', '.join(have[1:])}), but the compiler calls it as {e[0]}({', '.join(e[1:])}) (RUNTIME's {RTSYM[f.ll[1:]]})")
                if rt_subset(RTSYM[f.ll[1:]], [f.ret] + f.ptypes) != "":
                    self.err(f"{f.name}() is declared as {typestr(f.ret)}({', '.join([typestr(t) for t in f.ptypes])}), but the compiler calls it as {rt_subset(RTSYM[f.ll[1:]], [f.ret] + f.ptypes)} (RUNTIME's {RTSYM[f.ll[1:]]})")
                self.runtime(f.ll[1:])
                self.externs[f.ll] = ""
            else:
                self.untold(f, [f.ret] + f.ptypes, "declared")
                self.extern_decl(f)
        elif not f.generic and f.ll not in self.compiled:
            self.function(f, f.node.kids[2].kids)
    for ci in [x for x in self.classes.values()]:
        for f in ci.methods.values():
            if f.cls != ci.name or (ci.name in self.tmpl and f.deco == ""):
                continue  # (an exception class's base's; a class template's, but its static and class methods: its specializations')
            if ci.mod != "" and f.ll not in self.lazy:
                self.lazy[f.ll] = f
            elif f.ll not in self.lazy and f.ll not in self.compiled and not f.generic:
                self.function(f, f.node.kids[2].kids)
    # generate on demand: dataclass methods that were called, and helpers for classes that
    # appear inside containers (which can make more of both necessary). Each pass compiles,
    # in the order of lazy, the functions called by the time it gets to them: it takes their
    # positions from wake (call_fn adds them), so that it costs what it compiles
    lz = [x for x in self.lazy.values()]
    for i in range(len(lz)):
        self.lazyat[lz[i].ll] = i
        if lz[i].ll in self.called:
            hpush(self.wake, i)
    done: dict[str, bool] = {}
    helped: dict[str, bool] = {}
    cmped: dict[str, bool] = {}
    hashed: dict[str, bool] = {}
    xmade: dict[str, bool] = {}
    ned: dict[str, bool] = {}
    xed: dict[str, bool] = {}
    while True:
        before = len(done) + len(helped) + len(cmped) + len(hashed) + len(xmade) + len(ned) + len(xed) + len(self.xctors)
        for c in [x for x in self.ocls]:
            if c not in helped:
                helped[c] = True
                if c in self.ocmp and c not in cmped:
                    cmped[c] = True
                    self.obj_helpers(c, [0, 1, 2])  # (in the order of a class's helpers before ocmp)
                else:
                    self.obj_helpers(c, [2])  # (and @o.eq and @o.cmp, where ocmp, made by a pass before)
        for c in [x for x in self.ocmp]:
            if c not in cmped:
                cmped[c] = True
                self.obj_helpers(c, [0, 1])
        for c in [x for x in self.one]:
            if c not in ned:
                ned[c] = True
                self.obj_helpers(c, [3])
        for c in [x for x in self.xobj]:
            if c not in xed:
                xed[c] = True
                self.dyn_xhelper(c)  # (its comparisons with dynamic values of other types: dynamic.py)
        for c in [x for x in self.hcls]:
            if c not in hashed:
                hashed[c] = True
                self.hash_helper(c)
        for c in [x for x in self.xcls]:
            if c not in xmade:
                xmade[c] = True
                self.exc_helpers(c)
        self.exc_ctors()  # (calls of class objects: the functions that make objects of the program's classes)
        at = -1
        later: list[int] = []
        while len(self.wake) > 0:
            i = hpop(self.wake)
            if i <= at:
                later.append(i)  # called after the pass went by: the next pass compiles it
            elif lz[i].ll not in done:
                at = i
                done[lz[i].ll] = True
                if lz[i].ll not in self.compiled and not lz[i].generic:
                    self.function(lz[i], lz[i].node.kids[2].kids)
        for i in later:
            hpush(self.wake, i)
        # (the dispatchers of dynamic values, compiled again while more classes are boxed: dynamic.py)
        if len(done) + len(helped) + len(cmped) + len(hashed) + len(xmade) + len(ned) + len(xed) + len(self.xctors) == before and not self.dyn_dispatchers():
            break
    self.exc_tables()
    for nm in self.flagged:
        if nm not in self.gtypes and nm not in self.funcs and nm not in self.classes:
            self.global_var(f"@g.{nm}.def", "bool")  # (a variable no compiled code assigns)
    timing_end(phase + ".discover", started)
    # Finite comparison field discoveries only grow (incompatible joins are
    # terminal). Finish these even if earlier fields used the ordinary join budget.
    if len(self.newhints) > 0 and (not self.final or any(k.startswith("cmpfield:") or k.startswith("cmpwrite:") for k in self.newhints)):
        raise Rejoin()  # (joins found wider types: the next pass compiles them, see join_hint)
    started = timing_start()
    # The completed adapter set makes candidate discovery independent of which
    # caller first compiled a kernel. Versions add no frontend inference state.
    if not self.rtmode and "callbacks" in self.opts:
        specialize_callbacks(self.fns, self.adapters, self.cvos)
    # the whole program is built: its functions are printed in the order they were completed
    for j in range(len(self.fns)):
        self.fll[self.fns[j].f.ll] = j
    if len(NONUMS) + len(NOVALS) + len(NOLABELS) > 0:
        fail("internal error: an op changed the lists all ops start with", 0)
    chk = os.getenv("PYSTACHY_IRCHECK", "") == "1"
    dump = os.getenv("PYSTACHY_IRFX", "") == "1" and not self.rtcache
    on = self.opts
    if self.eh or len(on) > 0 or chk or dump or not self.rtmode:
        # the passes and eh_ir read the effect summaries (eh_ir: which calls may raise), and so
        # does the native depth policy, which is no optimization; the IR check computes them
        # too, so that the tests run effects even with every pass off
        self.effects()
    if not self.rtmode:
        # which source functions count toward the recursion limit (docs/internals.md#native-recursion-depth):
        # their guards' effects join the summaries before any pass or verification reads them
        self.recursionscope()
    if chk:
        # Union proofs distinguish read-only callees from calls that can invalidate
        # storage facts, so the first verification uses complete effect summaries too.
        for fn in self.fns:
            self.verify(fn, False)
    timing_end(phase + ".analysis", started)
    started = timing_start()
    if len(on) > 0:
        # (before eh_ir: a block that a try statement covers keeps its exception edge to the
        # landing block, Blk.handler, which the passes count, see preds)
        changed = False
        for fn in self.fns:
            if self.optimize(fn, on) > 0:
                changed = True  # optimize verifies each changed pass when checks are enabled
        if changed and dump:
            self.effects()  # (what the passes left: tests/ir/*.fx pin them)
    timing_end(phase + ".optimize", started)
    started = timing_start()
    for fn in self.fns if self.eh else self.fns[:0]:
        if len(fn.tries) > 0:
            self.eh_ir(fn)
            if chk:
                self.verify(fn, True)
    if dump:
        for fn in self.fns:
            print(f"{fn.f.ll}: {fxs(fn.fx)}".rstrip(), file=sys.stderr)
    if "tupleret" in on:
        self.tuple_rets()  # (which functions return their tuples' slots by value: lowering reads it)
    timing_end(phase + ".finalize", started)
    started = timing_start()
    for fn in self.fns:
        self.lower(fn)
        # its LLVM text is all that is left to print: its IR goes (its summary, IFn.fx, stays)
        fn.blocks = []
        fn.slots = []
        fn.loops = []
        fn.cold = {}
        fn.fa = {}
    for op in ["eq", "cmp", "repr"] if not self.rtmode else []:
        self.dispatch(op)  # (each program defines them: runtime.py calls them like runtime.c)
    ir = self.lower_module()
    timing_end(phase + ".lower", started)
    if not one_nums_intact():
        fail("internal error: an op changed the shared list of its number (one_num)", 0)
    RENAMED.clear()  # (the program's classes': runtime.py, which the driver may compile next, has none)
    return ir

# ---- definite assignment, before code generation: CPython raises UnboundLocalError or
# NameError when a read finds its variable unassigned. Reads that cannot are plain loads;
# the others (Node.chk) test an "is assigned" flag kept only for the variables they read.
