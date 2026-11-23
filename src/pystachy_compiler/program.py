"""Program component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.reflection import refl_needs_eh, refl_props
from src.pystachy_compiler.builtin_bases import builtin_base
from src.pystachy_compiler.analysis import all_imports, chk_names, collect, constant_writes, defines, module_anns, module_ints, module_reads, module_strs, module_values, name_nodes, needs_eh, none_assigns, reads_builtin
from src.pystachy_compiler import diagnostics
from src.pystachy_compiler.diagnostics import NeedHierarchy, Rejoin, dynamic_program, fail, shown
from src.pystachy_compiler.dynamic import comparison_properties, comparison_storage
from src.pystachy_compiler.generators import reads_cause, reads_handled, uses_protocol
from src.pystachy_compiler.ir import Val
from src.pystachy_compiler.symbols import ClassInfo, FnInfo
from src.pystachy_compiler.module import Mod
from src.pystachy_compiler.names import ENUMCLASSES, LOCALS, ORDERED, RENAMED, local_class, owner, short
from src.pystachy_compiler.pipeline import PreparedProgram
from src.pystachy_compiler.specs import (
    ABSTRACT_DECOS,
    CABCS,
    EXCBASES,
    EXCEPTIONS,
    FINAL_FIELD,
    PLAIN_EXC_BASES,
    exc_derives,
    GALIAS,
    GENERICS,
    INERT,
    INERT_DECOS,
    is_excname,
    ITERS,
    MODATTRS,
    OBJECTS,
    PURE,
    PYBUILTINS,
    RAISERS,
    COMPLEXS,
    RANGES,
    RTSYM,
    TYPING,
    UNSUPPORTED,
)
from src.pystachy_compiler.syntax import NOKIDS, Node, dc_args, has_kind, mentions, mk, names_in
from src.pystachy_compiler.utils import (
    RtFn,
    clone,
    elem,
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
            if first != "" and second != "":
                # An exception class of the program as one of two exception bases (decimal's
                # DivisionByZero is a DecimalException and a ZeroDivisionError). The first base gives
                # the object its layout, methods and text; the second only what catches it and what
                # isinstance() and issubclass() tell (derives), so it defines nothing itself.
                if (first not in self.classes and first not in PLAIN_EXC_BASES) or (second not in self.classes and second not in PLAIN_EXC_BASES):
                    return "two builtin exception bases must be independent and have ordinary Exception behavior"
                if self.derives(first, second) or self.derives(second, first):
                    return "the two exception bases of a class must be independent: neither derives from the other"
                ancestor = second
                while ancestor in self.classes and not self.derives(first, ancestor):
                    # (as far as an ancestor that the first base shares, whose own the object has)
                    info = self.classes[ancestor]
                    for d in info.node.kids[0].kids:
                        if d.kind != "pass" and not (d.kind == "expr" and d.kids[0].kind == "str"):
                            return f"a second exception base must define no methods or fields, which {ancestor} does: the first base gives the object its own"
                    if info.excsecond != "":
                        return "a second exception base with two bases of its own is not supported"
                    ancestor = info.base
                if ancestor not in self.classes and ancestor != "Exception" and ancestor not in PLAIN_EXC_BASES:
                    return "two builtin exception bases must be independent and have ordinary Exception behavior"
                if len(st.kids[0].kids) > 1:
                    return "an exception class with a decorator is not supported"
                return ""
        if any(b.kind != "name" for b in st.kids[1:]):
            return why
        primary = st.kids[1].s
        secondaries = [b.s for b in st.kids[2:]]
        if primary in self.bsubn or len([b for b in secondaries if b in self.bsubn]) > 0:
            return "multiple inheritance with a class that derives from a builtin container is not supported"
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
                # (an __init__ that stores the base's attributes: role_attrs)
                if d.kind != "def" or (d.s.startswith("__") and d.s != "__init__") or (len(d.kids) != 3 and not abstract) or len(d.kids[0].kids) == 0:
                    return why
                if "_pys_cm_" + d.s in methods and len(attrs) > 0:
                    continue  # (a @contextmanager method's own code is _pys_cm_<name>, checked as a method: this one makes its context manager, loader.py)
                if role_body_uses_storage(d.kids[2], d.kids[0].kids[0].s, methods, attrs):
                    return "secondary base methods may not use super() or read or write the instance"

    if st.kids[1].kind == "name" and st.kids[1].s in self.classes and self.classes[st.kids[1].s].exc == "":
        base_ci = self.classes[st.kids[1].s]
        dc = len(st.kids[0].kids) == 2 and self.imported(st.kids[0].kids[1].s) == "dataclasses.dataclass"
        if base_ci.name in self.bsubn:
            return f"inheritance from {shown(base_ci.name)}, which derives from {builtin_base(self.bsubn[base_ci.name])}, is not supported: only a class that names the builtin type as its one base"
        if base_ci.name in self.nts:
            return "inheritance from a NamedTuple is not supported"
        if self.is_dc(base_ci.name) and not dc:
            return "inheritance from a dataclass is only supported by a @dataclass class"
        root = self.template_root(base_ci.name)
        if root != "":
            # (a class template, or a class that derives from one without an __init__ of its own:
            # template_bases)
            why = self.template_subclass(st, base_ci.name, root)
            if why != "":
                return why
        elif self.init_template(base_ci.node, True) or self.init_template(st.kids[0], True) or (st.s not in self.hierarchies and self.fixed_hierarchy(base_ci.name)):
            return "inheritance with generic class templates is not supported: " + self.template_fix([base_ci.node, st.kids[0]])
        if dc and not self.is_dc(base_ci.name):
            return "a @dataclass class whose base is not a dataclass is not supported"
        if len(st.kids[0].kids) > 1 and not dc:
            return "a class with inheritance and a decorator is not supported"
        return ""
    b = self.exc_base(st.kids[1])
    if b == "" and len(st.kids) == 2 and builtin_base(st.kids[1]) != "" and not self.bound(builtin_base(st.kids[1])):
        # class C(list), class C(list[T]): its objects begin as the builtin's do (builtin_bases.py)
        if len(st.kids[0].kids) > 1:
            return f"a class that derives from {builtin_base(st.kids[1])} with a decorator is not supported"
        return ""
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
            # (class IntBox(Box[int]): its objects begin as those of the specialization Box[int]
            # names, which template_bases makes its base; only as its one base, of types)
            xs = b.kids[1].kids if b.kids[1].kind == "tuple" else [b.kids[1]]
            if len(st.kids) != 2 or len(own) > 0 or self.typevar_in(xs, []) != "":
                return f"a subclass of {shown(g)}[...] is not supported: the __init__ of {shown(g)} binds its type variables, as its calls' arguments do (a subclass of one specialization, class C({short(g)}[X]) of types X, is)"
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

def gen_iter_abc(self, st: Node) -> str:
    # "Iterator" or "Iterable" where class statement st, without decorators, has one base,
    # typing's or collections.abc's (subscripted or not, with no TypeVarTuple), and a body that
    # defines the methods that abstract base requires, __iter__ and __next__ (__iter__): the base
    # then gives the class nothing it uses (its __iter__ mixin is the class's own); else ""
    b = st.kids[1]
    r = self.imported_ref(b.kids[0] if b.kind == "index" else b)  # (the import, not an annotation's name: a class base is evaluated)
    r = r[r.rfind(".") + 1 :] if r in ["typing.Iterator", "typing.Iterable", "collections.abc.Iterator", "collections.abc.Iterable"] else ""
    if r == "" or len(st.kids[0].kids) != 1 or (b.kind == "index" and not self.inert_subscript(b.kids[1])):
        return ""
    names: dict[str, bool] = {}
    name_nodes(b, names)
    if len([x for x in names if x in self.tvtuples]) > 0:
        return ""
    defs = [d.s for d in st.kids[0].kids[0].kids if d.kind == "def"]
    if "__iter__" not in defs or (r == "Iterator" and "__next__" not in defs):
        return ""
    return r

def gen_inert_subscript(self, n: Node) -> bool:
    # can a class base's subscript n be left out where the class statement runs, as nothing of it
    # can raise or run the program's code: type variables, builtin types the program does not
    # rebind, typing's and collections.abc's names, strings (forward references), None and ...,
    # and subscripts and tuples of those (set[T]); not a call, nor an attribute read through a
    # module, which a circular import may not have bound yet
    if n.kind == "name":
        ref = self.imported_ref(n)
        return n.s in self.typevars or ref.startswith("typing.") or ref.startswith("collections.abc.") or (n.s in ["int", "str", "float", "bool", "bytes", "object", "list", "dict", "set", "frozenset", "tuple", "type"] and not self.bound(n.s))
    if n.kind == "str" or n.kind == "None" or n.kind == "ellipsis":
        return True
    if n.kind == "index" or n.kind == "tuple":
        for k in n.kids:
            if not self.inert_subscript(k):
                return False
        return True
    return False

def gen_iterabc_derived(self, c: str) -> bool:
    # does class c (or a specialization's origin) derive from a class whose base was collections.abc's
    # Iterator or Iterable (iter_abc), or from a class of lib's port of collections.abc (Loader's
    # abc_classes), whose objects have ABCMeta's attributes too
    while c in self.classes:
        if c in self.iterabc or self.classes[c].origin in self.iterabc or c.startswith(CABCS + "$"):
            return True
        c = self.classes[c].base
    return False

def subscript_tvars(n: Node, typevars: list[str], out: list[str]) -> None:
    # the type variables that a base's subscript n names anywhere, in order of first appearance,
    # as CPython's __parameters__ lists them (Iterator[set[T]]: T)
    if n.kind == "name" and n.s in typevars and n.s not in out:
        out.append(n.s)
    for k in n.kids:
        subscript_tvars(k, typevars, out)

def gen_implicit_tparams(self, st: Node) -> list[str]:
    # class S(A[T], B), without Generic[...]: the type variables that its subscripted bases, of
    # generic classes, name as their arguments, in order of first appearance; [] where a base is
    # another subscript or no class name
    out: list[str] = []
    for b in st.kids[1:]:
        if b.kind == "index" and b.kids[0].kind == "name" and b.kids[0].s in self.tparams:
            for x in b.kids[1].kids if b.kids[1].kind == "tuple" else [b.kids[1]]:
                if x.kind == "name" and x.s in self.typevars and x.s not in out:
                    out.append(x.s)
        elif b.kind != "name":
            return []
    return out

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
        src = f
        defined = f.clsdef
        if self.copies and m not in ci.methods and not f.clsuse and f.deco == "classmethod" and b.origin in self.classes and m in self.classes[b.origin].methods:
            # (a specialization's class method is declared again from its template's def, in
            # which cls already reads the template's name: the template's is the one that uses
            # cls, and a class deriving from the specialization gets its own copy of it, as
            # from any other base. Its cls names the class, or its template: materialize, #1744)
            tf = self.classes[b.origin].methods[m]
            if tf.deco == "classmethod" and tf.clsuse and tf.node is f.node:
                src = tf
                defined = tf.cls
        if m not in ci.methods and src.clsuse and src.mod == ci.mod and len([x for x in src.defaults if not is_const(x) and x.kind != "noann"]) == 0:
            self.line = src.node.line
            self.lib = src.mod != ""
            self.selfcls = ci.name
            # Clone the declaration only. Its immutable body is shared until the method
            # is needed; declaring and flowing a copy per subclass costs body * subclasses
            # even when no inherited method is called.
            d = Node(src.orig.kind, src.orig.s, src.orig.line, [src.orig.kids[i] if i == 2 else clone(src.orig.kids[i]) for i in range(len(src.orig.kids))])
            g = self.declare_fn(d, ci.name, True)
            if g.tvret == "":
                # (f.orig was cloned after its declaration erased the TypeVar annotations: their
                # binding plan, over the same parameters, carries over: tv_plan)
                g.tvret = src.tvret
                g.tvbparams = list(src.tvbparams)
                g.tvbclass = list(src.tvbclass)
                g.tvbpos = list(src.tvbpos)
            g.orig = src.orig
            g.clsuse = True
            g.clsdef = defined
            if defined != "":
                # (in this copy cls is the class where it was the template: what cls(...) makes
                # and takes, and what the method stores through cls, are the class's now, so code
                # here or anywhere that compiled with the template's may not. From here on the
                # compilation is a trial, which the driver gives up for the one without these
                # copies where a pass fails or declines an attempt: diagnostics.TRYING)
                diagnostics.TRYING = True
                diagnostics.COPIED = True
            g.pending = True
            g.bad = g.bad if g.bad != "" else src.bad  # the defining declaration checked the body
            ci.methods[m] = g
            self.selfcls = ""
            self.lib = False
            ci.methods[m].mod = src.mod
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
                if method not in b.methods and method in seen and seen[method] != r and own and method != "__init__":
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
                elif method == "__init__" and method in b.methods:
                    # (the primary chain's comes first in CPython's method resolution order, as here;
                    # the class's code may call the base's own as C.__init__(self, ...))
                    continue
                elif method in b.methods or (method in ci.methods and ci.methods[method].cls != ci.name):
                    # (also another secondary base's: CPython's method resolution order picks one)
                    self.line = ci.node.line
                    self.bad_class(ci, f"both bases declare method '{method}'")
                elif method not in ci.methods:
                    ci.methods[method] = original
            fn = ci.methods[method]
            if method == "__init__":
                continue  # (a constructor's own signature: no value of the base's type calls the class's)
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


# the ordering methods that functools.total_ordering() computes one another from, in the order
# CPython's max(roots) prefers them
ORDER_OPS = ["__lt__", "__le__", "__gt__", "__ge__"]


def gen_ordering_ops(self, c: str, seen: list[str]) -> list[str]:
    # the ones of __lt__, __le__, __gt__ and __ge__ that class c has other than object's, which
    # CPython's functools.total_ordering() takes as roots (getattr(cls, op) is not object's),
    # in ORDER_OPS's order: those its body binds, among them those @total_ordering wrote
    # (Loader's functools_classes); all four for a NamedTuple (tuple's) and a dataclass with
    # order=True; and those of its bases (an exception class's builtin bases have none). Classes
    # in seen are left out (each base once)
    if c not in self.classes or c in seen:
        return []
    seen.append(c)
    ci = self.classes[c]
    if c in self.nts or "order" in ci.dcopts:
        return list(ORDER_OPS)
    has: dict[str, bool] = {}
    for d in ci.node.kids[0].kids:
        if d.kind == "def" and d.s in ORDER_OPS:
            has[d.s] = True
        for t in d.kids[:-1] if d.kind == "assign" else d.kids[:1] if d.kind == "annassign" and len(d.kids) == 3 else NOKIDS:
            if t.kind == "name" and t.s in ORDER_OPS:
                has[t.s] = True
    for b in [ci.base] + ci.roles:
        for op in self.ordering_ops(b, seen):
            has[op] = True
    return [op for op in ORDER_OPS if op in has]

def gen_ordered_class(self, ci: ClassInfo) -> None:
    # class ci, decorated @total_ordering: the loader wrote the ordering methods its body lacks
    # from the greatest of those it defines (functools_classes, ORDERED). CPython's decorator
    # also takes as roots those the class inherits (ordering_ops), all four of a NamedTuple and
    # those of a dataclass with order=True applied before it; it writes only the others, each
    # computed from the greatest root (max(roots)). The methods written for a root the class
    # inherits are left out of its body, so that it inherits that one; where the others are
    # computed from an inherited root, which the loader did not read, the class is rejected
    words = ORDERED[ci.node.line].split()
    own = [op for op in ORDER_OPS if op in words]
    inherited: list[str] = list(ORDER_OPS) if ci.name in self.nts or ("+" in words and "order" in ci.dcopts) else []
    seen: list[str] = [ci.name]
    bases = [ci.base] + ci.roles
    for b in bases:
        for op in self.ordering_ops(b, seen):
            if op not in inherited:
                inherited.append(op)
    roots = [op for op in ORDER_OPS if op in own or op in inherited]
    made = [op for op in ORDER_OPS if op not in roots]  # (what CPython's decorator writes)
    self.line = ci.node.line
    if len(roots) == 0:
        self.err("ValueError: must define at least one ordering operation: < > <= >=")
    if len(roots) == len(own):
        return  # (as the loader wrote them)
    if len(made) > 0 and (len(own) == 0 or own[0] != roots[0]):
        held = [b for b in bases if roots[0] in self.ordering_ops(b, [])]
        listed = made[0] if len(made) == 1 else ", ".join(made[:-1]) + " and " + made[-1]
        self.err(f"@total_ordering of class {short(ci.name)} is not supported where it inherits {roots[0]}" + (f" from {short(held[0])}" if len(held) > 0 else "") +
                 f": CPython's decorator computes {listed} from that method" + (f", not from {own[0]} of its body" if len(own) > 0 else ""))
    drop = [op for op in roots if op not in own]
    ci.node.kids[0].kids = [d for d in ci.node.kids[0].kids if d.kind != "def" or d.s not in drop]

def gen_on_chain(self, c: str, a: str) -> bool:
    # is class a class c or one of the classes c derives from by its primary bases
    while c in self.classes:
        if c == a:
            return True
        c = self.classes[c].base
    return False

def role_attrs(c: Node) -> list[str]:
    # the attributes class c (its class node) declares by annotation alone (x: T), which a
    # secondary base may: no object has them until its class's code stores them; and those its
    # __init__ stores (self.x = v), the fields of its own objects and of the classes combining it,
    # which their __init__ give it by calling its own (C.__init__(self, ...))
    out = [d.kids[0].s for d in c.kids[0].kids if d.kind == "annassign" and len(d.kids) == 2 and d.kids[0].kind == "name" and d.kids[0].s != "__slots__"]
    for d in c.kids[0].kids:
        if d.kind == "def" and d.s == "__init__" and len(d.kids[0].kids) > 0:
            me = d.kids[0].kids[0].s
            for st in d.kids[2].kids:
                for t in st.kids[:-1] if st.kind == "assign" else st.kids[:1] if st.kind == "annassign" else []:
                    if t.kind == "attr" and t.kids[0].kind == "name" and t.kids[0].s == me and t.s not in out:
                        out.append(t.s)
    return out

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
        if info.excsecond != "" and self.derives(info.excsecond, base):
            return True  # (its second exception base, a builtin class or one of the program)
        c = info.base
    return c in EXCBASES and exc_derives(c, base)

def gen_tmpl_derives(self, c: str, base: str) -> bool:
    # is class c, of the program, of class template base: a specialization of it, or derived from
    # one, as a template hierarchy's classes are (template_bases); isinstance(x, base) of an object
    # of c (derives, which names specializations, not their template)
    while c in self.classes:
        if c == base or self.classes[c].origin == base:
            return True
        c = self.classes[c].base
    return False

def gen_init_generic(self, st: Node, hier: bool = False) -> bool:
    # is class statement st a class template: no decorator (a dataclass's fields are annotated)
    # and an __init__ of its own with a parameter but self that has no annotation, mentions Any,
    # is object, or names a class template; each object belongs to a specialization, whose fields
    # are typed by the arguments of the call that makes it (see specialize). hier: st takes part
    # in an inheritance hierarchy, where a template is an error: a class-template object that
    # __init__ stores into an annotated field then types nothing (init_makes_tmpl). Elsewhere it
    # still does, as before: a template compiles only once used, so an unused class's other
    # fields are never inferred
    if len(st.kids) > 1 or (st.s in self.nts and st.s not in self.cnts):
        return False
    for d in st.kids[0].kids:
        if d.kind == "def" and d.s == "__init__" and len(d.kids) == 3:
            if st.s in self.tparams and st.s not in self.implicitgen:
                return True  # (its context can bind variables absent from __init__ parameters; not an
                # implicitly generic class's, which, as one without __init__, binds nothing)
            ps = d.kids[0].kids
            for i in range(1, len(ps)):
                a = ps[i].kids[0]
                if a.kind == "noann" or (self.any_in([a]) and (not self.dyn_policy(d.line) or ps[i].kind != "param")) or (ps[i].kind == "param" and ((a.kind == "name" and a.s == "object") or self.tmpl_ann(a))):
                    return True  # (also *args or **kwargs without an annotation, or with Any, which only a template takes)
                if st.s in self.tparams and self.names_tv(ps[i].kids[0], self.tparams[st.s]):
                    return True  # (a generic class whose objects bind its type variables, see bind)
            fixed: dict[str, bool] = {}
            for b in st.kids[0].kids:
                if b.kind == "annassign" and b.kids[0].kind == "name" and self.fixed_template_field_ann(b.kids[1]):
                    fixed[b.kids[0].s] = True
            if self.init_makes_tmpl(d.kids[2], ps[0].s if len(ps) > 0 else "", fixed) if hier else self.makes_tmpl(d.kids[2]):
                return True  # (a field may hold an object of a class template: typed where the object is made)
            if not hier and stores_enum_class(d.kids[2], ps[0].s if len(ps) > 0 else "", self.classes):
                return True  # (a field holds an enum class's EnumType object, of a class template too)
    return False

def stores_enum_class(n: Node, me: str, classes: dict[str, ClassInfo]) -> bool:
    # does __init__'s code n store an enum class, its EnumType object (Loader's enum_classes), into
    # a field of me (self.kind = Color), which is of a specialization of lib/enum.py's class
    # template, as the object of a class template is
    if n.kind == "assign" and len(n.kids) == 2 and n.kids[0].kind == "attr" and n.kids[0].kids[0].kind == "name" and n.kids[0].kids[0].s == me:
        v = n.kids[1]
        if v.kind == "name" and v.s in classes and classes[v.s].node.line in ENUMCLASSES:
            return True
    for k in n.kids:
        if stores_enum_class(k, me, classes):
            return True
    return False


def fixed_ann_shape(a: Node, classes: dict[str, ClassInfo]) -> bool:
    if a.kind == "str" or a.kind == "noann":
        return False
    if a.kind == "index" and a.kids[0].kind == "name" and a.kids[0].s in classes:
        return False
    return all([fixed_ann_shape(k, classes) for k in a.kids])

def gen_fixed_ann(self, a: Node) -> bool:
    # A layout annotation that can be checked without making a class specialization or
    # parsing a deferred string. Those paths retain their existing lazy template handling.
    if not fixed_ann_shape(a, self.classes) or self.any_in([a]) or self.tmpl_ann(a):
        return False
    return self.ann_problem(a, False) == ""

def gen_fixed_stores(self, n: Node, receiver: str, fields: dict[str, str]) -> bool:
    # Every attribute initialized on self must have one independent storage annotation.
    # scan_fields sees stores in source order. An annotation must establish storage before
    # an unannotated store; a later annotation cannot prevent argument-dependent inference.
    if n.kind in ["assign", "augassign"] and not fixed_assignments(n, receiver, fields):
        return False
    if n.kind == "annassign" and n.kids[0].kind == "attr" and n.kids[0].kids[0].kind == "name" and n.kids[0].kids[0].s == receiver:
        if not self.fixed_ann(n.kids[1]):
            return False
        name = n.kids[0].s
        t = self.ann(n.kids[1])
        if name in fields and fields[name] != t:
            return False
        fields[name] = t
    for k in n.kids:
        if not self.fixed_stores(k, receiver, fields):
            return False
    return True

def fixed_targets(n: Node, receiver: str, fields: dict[str, str]) -> bool:
    if n.kind == "attr" and n.kids[0].kind == "name" and n.kids[0].s == receiver:
        return n.s in fields
    return all([fixed_targets(k, receiver, fields) for k in n.kids])

def fixed_assignments(n: Node, receiver: str, fields: dict[str, str]) -> bool:
    if n.kind in ["assign", "annassign", "augassign"]:
        targets = n.kids[:-1] if n.kind == "assign" else n.kids[:1]
        for target in targets:
            if not fixed_targets(target, receiver, fields):
                return False
    return all([fixed_assignments(k, receiver, fields) for k in n.kids])

def fixed_properties(st: Node, fields: dict[str, str]) -> bool:
    # The annotation of a property assignment says nothing about the storage its
    # setter writes. Leave that layout to the existing specialization analysis.
    for d in st.kids[0].kids:
        if d.kind == "def" and d.s in fields and len(d.kids) == 4:
            deco = d.kids[3].s
            if deco == "property" or deco.endswith(".setter") or deco.endswith(".deleter"):
                return False
    return True

def fixed_receiver(n: Node, receiver: str, fields: dict[str, str]) -> bool:
    # A field list from this body does not describe initialization delegated through
    # self's methods, an alias or a helper. Such calls can reach a subclass's fields.
    if n.kind == "call" and n.kids[0].kind == "attr":
        target = n.kids[0].kids[0]
        if target.kind == "name" and target.s == receiver:
            return False
    if n.kind == "attr" and n.kids[0].kind == "name" and n.kids[0].s == receiver:
        return n.s in fields  # extracting a bound method can delegate initialization too
    if n.kind == "name" and n.s == receiver:
        return False
    return all([fixed_receiver(k, receiver, fields) for k in n.kids])

def gen_fixed_init(self, st: Node) -> bool:
    # An unused imported subclass stays excluded until a real use needs its hierarchy.
    # A retry admits only that class and its ancestors, keeping unused sibling overrides
    # out of closed-world dispatch. No constructor-dependent layout survives the retry.
    if st.s not in self.hierarchies:
        for n in self.cnodes.values():
            if n.kind == "subclass":
                if n.s == st.s:
                    return False
                for b in n.kids[1:]:
                    base = b.kids[0] if b.kind == "index" else b
                    if base.kind == "name" and base.s == st.s:
                        return False
    if sub_args_generic(self, st):
        # (a subclass of a class template whose super().__init__(...) passes it what its own
        # parameters take, of any type: the specialization it derives from, and so its layout, is
        # each call's, a template's, tmpl_sub)
        return False
    return self.fixed_layout(st)

def sub_args_generic(self, st: Node) -> bool:
    # (fixed_init) does class statement st, of a class that derives from a class template, pass a
    # parameter of its own __init__ that init_generic makes a template's, unannotated, Any or
    # object, to its base's __init__ (super_inits)?
    if st.s not in self.classes or self.classes[st.s].base not in self.classes or self.template_root(self.classes[st.s].base) == "":
        return False
    for d in st.kids[0].kids:
        if d.kind == "def" and d.s == "__init__" and len(d.kids) == 3 and len(d.kids[0].kids) > 0:
            ps = d.kids[0].kids
            generic = [ps[i].s for i in range(1, len(ps)) if ps[i].kind != "param" or ps[i].kids[0].kind == "noann" or self.any_in([ps[i].kids[0]]) or (ps[i].kids[0].kind == "name" and ps[i].kids[0].s == "object") or self.tmpl_ann(ps[i].kids[0])]
            calls: list[Node] = []
            super_inits(d.kids[2], self.classes[st.s].base, ps[0].s, calls)
            for call in calls:
                for a in super_init_args(call):
                    if mentions(a, generic):
                        return True
    return False


def gen_fixed_hierarchy(self, name: str) -> bool:
    # An activated generic initializer anywhere in this primary chain changed the
    # formerly excluded descendants' admission. Other ordinary hierarchies stay unchanged.
    while name in self.classes:
        ci = self.classes[name]
        if name in self.hierarchies and self.init_generic(ci.node) and self.template_root(name) != name:
            return True  # (not a template hierarchy's root, whose classes derive as template_bases has them)
        name = ci.base
    return False


def gen_hierarchy_chain(self, name: str, chain: list[str], seen: list[str]) -> bool:
    # A requested declaration, its ordinary bases and constructor-type dependencies.
    # A dependency may use annotated template-valued fields under the existing hierarchy
    # rule; generic parameters still need an independent fixed-layout proof. Only syntax,
    # never tentative inferred fields, justifies retaining a name across the retry.
    if name in chain:
        return True
    if name in seen:
        return False
    seen.append(name)
    node = self.nokey
    for n in self.cnodes.values():
        if n.s == name:
            node = n
    if node is self.nokey:
        return False
    st = node.kids[0] if node.kind == "subclass" else node
    if name in self.tparams or name in self.nts or len(st.kids) != 1:
        return False
    if node.kind == "subclass":
        for base in node.kids[1:]:
            if base.kind != "name":
                return False
            before = len(chain)
            if not self.hierarchy_chain(base.s, chain, seen):
                # (a class template that stays one, the root of a template hierarchy whose
                # classes derive from its specializations, template_bases: kept with them where
                # it needs no dependency of its own)
                if len(chain) != before or base.s not in self.classes or self.template_root(base.s) != base.s or self.template_hierarchy(self.classes[base.s]) != "":
                    return False
                chain.append(base.s)
    if self.init_generic(st, True) and not self.fixed_layout(st):
        # Imported descendants may be deferred before acquiring a tag. Discover
        # dependencies only when this layout needs their annotations to become nominal.
        # A constructor with an already fixed layout can still specialize for a
        # variable-layout parameter without activating that parameter's class.
        named: dict[str, bool] = {}
        self.init_param_classes(st, named)
        for c in named:
            if c != name and c in self.tmpl and not self.hierarchy_chain(c, chain, seen):
                return False
        if node.kind == "subclass" and len(node.kids) == 2 and node.kids[1].kind == "name" and node.kids[1].s in self.classes and self.template_root(node.kids[1].s) != "":
            # (a subclass of a class template whose own __init__ is one, tmpl_sub: a template of
            # the hierarchy whose classes derive as template_bases has them, as a member is)
            chain.append(name)
            return True
        return False  # recheck after a fresh pass, with only verified dependencies retained
    chain.append(name)
    return True


def gen_request_hierarchy(self, name: str) -> None:
    if self.xtry != "":
        return  # a speculative adapter may decline without ever using this class
    if len(self.newhints) > 0 and not self.final:
        raise Rejoin()
    chain: list[str] = []
    if name in self.hierarchies:
        return
    self.hierarchy_chain(name, chain, [])
    # A constructor parameter or field may name its still-templated base or dependency.
    # Admit verified names first, then re-evaluate the child's annotation in a fresh Gen.
    # Incomplete chains retain no unverified child; retries must add a new name.
    if any(c not in self.hierarchies for c in chain):
        for c in chain:
            self.hierarchies[c] = True
        # Main-module declarations already require eager validity. Batch their safe
        # chains, without inspecting references in unused imported bodies or branches.
        # Imported subclasses still activate only on a compiled use.
        for n in self.cnodes.values():
            if n.kind == "subclass" and owner(n.s) == "" and n.s not in self.hierarchies:
                local_chain: list[str] = []
                if self.hierarchy_chain(n.s, local_chain, []):
                    for c in local_chain:
                        self.hierarchies[c] = True
        raise NeedHierarchy()


def gen_request_fixed_params(self, name: str) -> None:
    # A hierarchy's class, name, is a class template: where only because its __init__ takes an
    # object of a class whose own hierarchy no use has requested yet (_PurePathParents(path:
    # PurePosixPath), whose subclass PosixPath a program may never name), and that class has a
    # fixed layout, admit that class as request_hierarchy would have at its subclass's first use.
    # Its unused subclass stays deferred. Nothing is admitted for a class whose own parameters or
    # fields make it a template: the error stands
    if self.xtry != "":
        return
    named: dict[str, bool] = {}
    self.init_param_classes(self.classes[name].node, named)
    chain: list[str] = []
    for c in named:
        if c != name and c in self.tmpl and c not in self.hierarchies:
            self.hierarchy_chain(c, chain, [])
    if any(c not in self.hierarchies for c in chain):
        for c in chain:
            self.hierarchies[c] = True
        raise NeedHierarchy()


def gen_retry_hierarchy(self, msg: str) -> None:
    # Deferred annotation failures may be kept on a lazy function/class until its first
    # use. Retry only when that exact stored class diagnostic would become terminal.
    for name in self.deferred_hierarchies:
        if name in self.unsupported and self.unsupported[name] in msg:
            self.request_hierarchy(name)


def gen_fixed_layout(self, st: Node) -> bool:
    # A self-reference annotates this prospective nominal layout, even if an earlier
    # pass classified the class as a template or a subclass has not been registered yet.
    # Only syntax-safe field annotations are read below; no fields or specializations
    # are inferred. Restore both registries even on an error or retry.
    if st.s in self.classes and st.s not in self.tmpl:
        return self.fixed_layout_body(st)
    classes = self.classes
    templates = self.tmpl
    if st.s not in classes:
        self.classes = dict(classes)
        self.classes[st.s] = ClassInfo(st.s, st)
    if st.s in templates:
        self.tmpl = dict(templates)
        del self.tmpl[st.s]
    try:
        return self.fixed_layout_body(st)
    finally:
        self.classes = classes
        self.tmpl = templates


def gen_fixed_layout_body(self, st: Node) -> bool:
    # Constructor arguments may specialize code without specializing storage. Keep the
    # source class itself when all its instance fields have concrete annotations; an
    # Iterable field, inferred field, explicit generic class or deferred annotation still
    # needs the existing class-template path.
    if len(st.kids) != 1 or st.s in self.tparams or st.s in self.nts:
        return False
    fields: dict[str, str] = {}
    init = st
    for d in st.kids[0].kids:
        if d.kind == "annassign" and d.kids[0].kind == "name":
            if not self.fixed_ann(d.kids[1]):
                return False
            fields[d.kids[0].s] = self.ann(d.kids[1])
        elif d.kind == "def" and d.s == "__init__" and len(d.kids) == 3:
            init = d
    if init is st or len(init.kids[0].kids) == 0 or has_kind(init.kids[2], "def") or has_kind(init.kids[2], "class"):
        return False
    if reads_builtin(init.kids[2], "callable", False, {}):
        # scan_fields can choose different fields and field order after callable type
        # guards. Retain those layouts, including their observable vars() order.
        return False
    receiver = init.kids[0].kids[0].s
    if not self.fixed_stores(init.kids[2], receiver, fields) or not fixed_receiver(init.kids[2], receiver, fields):
        return False
    if not fixed_properties(st, fields) or not self.fixed_base_properties(st.s, fields, []):
        return False
    return fixed_assignments(init.kids[2], receiver, fields)

def gen_fixed_base_properties(self, name: str, fields: dict[str, str], seen: list[str]) -> bool:
    # A subclass's annotated assignment may still call an inherited property's setter.
    # Its annotation then establishes no storage, just as for a property declared here.
    if name in seen:
        return True
    seen.append(name)
    for n in self.cnodes.values():
        if n.s == name and n.kind == "subclass":
            for b in n.kids[1:]:
                if b.kind != "name":
                    return False
                for parent in self.cnodes.values():
                    if parent.s == b.s:
                        st = parent.kids[0] if parent.kind == "subclass" else parent
                        if not fixed_properties(st, fields) or not self.fixed_base_properties(b.s, fields, seen):
                            return False
    return True


def gen_init_template(self, st: Node, hier: bool = False) -> bool:
    return self.init_generic(st, hier) and not self.fixed_init(st)

def gen_init_param_classes(self, st: Node, out: dict[str, bool]) -> None:
    # the program's classes that, were one a class template, would make class statement st one
    # by a parameter of its own __init__ (init_template's rule, which this follows: no decorator,
    # a parameter that is not *args or **kwargs, and a name where tmpl_ann looks for a template:
    # Box, Box | None, list[Box]; a string's where its text is such an expression of names as the
    # program's classes have them). A class that any other annotation names stays as it was: a
    # template or not, that annotation compiled
    if len(st.kids) > 1 or (st.s in self.nts and st.s not in self.cnts):
        return
    for d in st.kids[0].kids:
        if d.kind == "def" and d.s == "__init__" and len(d.kids) == 3:
            for p in d.kids[0].kids[1:]:
                if p.kind == "param":
                    self.ann_classes(p.kids[0], out)

def gen_ann_classes(self, a: Node, out: dict[str, bool]) -> None:
    # (as tmpl_ann reads annotation a: of a generic class's subscript, the arguments only)
    if a.kind == "str":
        if a.s.replace("_", "a").replace(".", "a").replace("[", "a").replace("]", "a").replace(",", "a").replace("|", "a").replace(" ", "a").isalnum():
            self.ann_classes(self.parse_expr(a.s), out)
        return
    if a.kind == "name":
        if a.s in self.classes:
            out[a.s] = True
        return
    if a.kind == "index" and a.kids[0].kind == "name" and a.kids[0].s in self.tparams:
        self.ann_classes(a.kids[1], out)
        return
    for k in a.kids:
        self.ann_classes(k, out)

def gen_fixed_template_field_ann(self, a: Node) -> bool:
    # does annotation a give a field a type of its own: no Any, object or class template (whose
    # specializations are types of their own, see tmpl_ann), as init_template requires of the
    # annotations of __init__'s parameters
    if a.kind == "str":
        a = self.parse_expr(a.s)
    return a.kind != "noann" and not self.any_in([a]) and not (a.kind == "name" and a.s == "object") and not self.tmpl_ann(a)

def gen_init_makes_tmpl(self, n: Node, me: str, fixed: dict[str, bool]) -> bool:
    # makes_tmpl for __init__'s statements n, me its first parameter, but for the value it stores into
    # a field of me that the class body, or the store itself, annotates with a type of its own
    # (fixed_template_field_ann, fixed): the field takes the object as that type, as a store by another method does
    if (n.kind == "assign" or n.kind == "annassign") and len(n.kids) == (2 if n.kind == "assign" else 3):
        t = n.kids[0]
        if t.kind == "attr" and t.kids[0].kind == "name" and t.kids[0].s == me and (t.s in fixed or (n.kind == "annassign" and self.fixed_template_field_ann(n.kids[1]))):
            return False
    if n.kind == "call" and n.kids[0].kind == "name" and (n.kids[0].s in self.tmpl or (n.kids[0].s == "iter" and len(n.kids) == 2 and ITERS + "$list_iterator" in self.classes)):
        return True
    for k in n.kids:
        if self.init_makes_tmpl(k, me, fixed):
            return True
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

# ---- template hierarchies (#962). A class template R (no base of its own) may have subclasses.
# One without an __init__ of its own is a template too, a member of R's (tmpl_member): each
# specialization of R, R-k, is made with one of each member, whose objects begin as R-k's do and
# whose base R-k is (templates.member_spec), so that a value of R-k's type dispatches over all
# the classes whose objects it may be. Any other subclass has an __init__ of its own that is no
# template, and derives from one specialization of R (or of a member), made where the classes
# are declared, before any code is compiled (template_bases): the one its class statement names
# (class IntBox(Box[int])), or the one its super().__init__(...) makes, which the types of its
# arguments, as guess infers them there, decide. Each specialization is thus a hierarchy's class.

def gen_template_root(self, name: str) -> str:
    # the class template whose __init__ the objects of class name run, name or a class it derives
    # from without an __init__ of its own between them: one that stays a template in a hierarchy,
    # where request_hierarchy cannot admit it with a fixed layout (fixed_layout: that path is
    # tried first, as before); else ""
    c = name
    while c in self.classes:
        if self.declares(c, "__init__"):
            node = self.classes[c].node
            return c if self.init_generic(node, True) and not self.fixed_layout(node) else ""
        c = self.classes[c].base
    return ""

def super_inits(n: Node, base: str, me: str, out: list[Node]) -> None:
    # the calls super().__init__(...) in code n, also nested, and base.__init__(me, ...) of class
    # base, which class_call calls as the specialization of me's class derives from (out)
    if n.kind == "call" and n.kids[0].kind == "attr" and n.kids[0].s == "__init__" and n.kids[0].kids[0].kind == "call" and n.kids[0].kids[0].kids[0].kind == "name" and n.kids[0].kids[0].kids[0].s == "super":
        out.append(n)
    elif n.kind == "call" and n.kids[0].kind == "attr" and n.kids[0].s == "__init__" and n.kids[0].kids[0].kind == "name" and n.kids[0].kids[0].s == base and len(n.kids) > 1 and n.kids[1].kind == "name" and n.kids[1].s == me:
        out.append(n)
    for k in n.kids:
        super_inits(k, base, me, out)

def super_init_args(call: Node) -> list[Node]:
    # the arguments that a call of super_inits passes to the base's __init__: but self
    return call.kids[1:] if call.kids[0].kids[0].kind == "call" else call.kids[2:]

def gen_super_init_problem(self, name: str, init: Node, base: str, root: str) -> str:
    # why __init__ init of class name, whose class statement names base, a class template root
    # or one that derives from root, does not tell which specialization the class derives from:
    # it must call super().__init__(...) (no arguments to super()), or base.__init__(self, ...),
    # once, in a statement of its own in its body; else ""
    calls: list[Node] = []
    super_inits(init.kids[2], base, init.kids[0].kids[0].s if len(init.kids[0].kids) > 0 else "", calls)
    top = [st for st in init.kids[2].kids if st.kind == "expr" and len(calls) == 1 and st.kids[0] is calls[0]]
    if len(calls) != 1 or len(top) != 1 or (calls[0].kids[0].kids[0].kind == "call" and len(calls[0].kids[0].kids[0].kids) != 1):
        return f"the __init__ of {short(name)}, a subclass of class template {shown(root)}, must call super().__init__(...) once, in a statement of its own: the types of its arguments decide which specialization of {short(root)} its objects begin as"
    return ""

def gen_template_subclass(self, st: Node, base: str, root: str) -> str:
    # why class statement st, whose base base is class template root or derives from it without
    # an __init__ of its own, cannot be compiled, or "": its class is a member of root's or
    # derives from one specialization (see template_bases)
    old = "inheritance with generic class templates is not supported: " + self.template_fix([self.classes[base].node, st.kids[0]])
    if owner(st.s) != "" and st.s not in self.hierarchies:
        # (an imported module's class: left out until the program uses it, which requests its
        # hierarchy, hierarchy_chain, as an imported subclass of a fixed layout's is)
        return old
    rc = self.classes[root]
    # (root may derive from a class template itself, whose own __init__ is one: tmpl_sub)
    if (rc.base != "" and self.template_root(rc.base) == "") or len(rc.roles) > 0 or root in self.nts or root in self.cnts or root in self.bsubn or self.is_dc(root) or self.literal_class(root):
        return old
    if len(st.kids) != 2:
        return f"a subclass of class template {shown(root)} with a secondary base is not supported"
    if len(st.kids[0].kids) > 1:
        return f"a subclass of class template {shown(root)} with a decorator is not supported"
    inits = [d for d in st.kids[0].kids[0].kids if d.kind == "def" and d.s == "__init__"]
    if len(inits) == 0:
        return ""
    if self.init_generic(st.kids[0], True):
        # (a template too, tmpl_sub: each of its specializations derives from the one that its
        # super().__init__(...) makes, for the types of its own arguments; also one whose own
        # fields keep one layout, fixed_layout, whose calls' arguments may still make that one,
        # and so its base, differ)
        if (st.s in self.genargs and base in self.genargs[st.s]) or root in self.tparams:
            return f"a subclass of class template {shown(root)} whose own __init__ is a class template is not supported: annotate the parameters of {short(st.s)}.__init__ with concrete types (not Any or object)"
        return self.super_init_problem(st.s, inits[0], base, root)
    if st.s in self.genargs and base in self.genargs[st.s]:
        return ""  # (class IntBox(Box[int]): that specialization)
    return self.super_init_problem(st.s, inits[0], base, root)

def gen_tmpl_member(self, ci: ClassInfo) -> bool:
    # is class ci a member of a template hierarchy: no __init__ of its own, its base a class
    # template (a member too, or the hierarchy's root), and no specialization named as its base
    return ci.base in self.tmpl and ci.origin == "" and not self.declares(ci.name, "__init__") and not (ci.name in self.genargs and ci.base in self.genargs[ci.name])

def gen_tmpl_sub(self, ci: ClassInfo) -> bool:
    # is class template ci a subclass of a class template whose own __init__ is one too (#962):
    # each of its specializations derives from the specialization of its base that its
    # super().__init__(...) makes, for the types of its own arguments (sub_base), and is made
    # where the classes are declared, before any code is compiled (late_sub, template_bases)
    return ci.base in self.tmpl and ci.origin == "" and ci.name in self.tmpl and self.declares(ci.name, "__init__") and ci.name not in self.tparams and not (ci.name in self.genargs and ci.base in self.genargs[ci.name])

def gen_template_hierarchy(self, ci: ClassInfo) -> str:
    # why class template ci, in a hierarchy, cannot be compiled, or "": a member of a template
    # hierarchy, a subclass of a template whose own __init__ is one (tmpl_sub), or its root, a
    # class template with an __init__ of its own and no base
    if self.tmpl_member(ci) or self.tmpl_sub(ci):
        return ""
    if ci.base != "" or len(ci.roles) > 0 or not self.declares(ci.name, "__init__") or ci.name in self.nts or ci.name in self.cnts or ci.name in self.bsubn or self.is_dc(ci.name) or self.literal_class(ci.name):
        return "inheritance with generic class templates is not supported: " + self.template_fix([ci.node])
    return ""

def gen_template_bases(self) -> None:
    # each class whose base is a class template and which is no template itself (template_root):
    # its base becomes the specialization its objects begin as, made now, before any code is
    # compiled (as its class tag is assigned), so that dispatch on that specialization's values
    # knows it. Its base's methods and fields are then inherited from that specialization
    for ci in list(self.classes.values()):
        if ci.base not in self.tmpl or ci.name in self.tmpl or ci.origin != "":
            continue
        self.line = ci.node.line
        b = ci.base
        root = b
        while not self.declares(root, "__init__"):
            root = self.classes[root].base
        given: dict[str, str] = {}
        ts: list[str] = []
        named = ci.name in self.genargs and b in self.genargs[ci.name] and b in self.tparams
        if named:
            tvs = self.tparams[b]
            for i in range(len(tvs)):
                given[tvs[i]] = self.genargs[ci.name][b][i]
        else:
            if "__init__" not in ci.methods or ci.methods["__init__"].cls != ci.name:
                self.err(f"class {short(ci.name)} derives from class template {shown(root)} without an __init__ of its own and without being a template: not supported")
            init = ci.methods["__init__"]
            why = self.super_init_problem(ci.name, init.node, b, root)
            if why != "":
                self.err(why)
            calls: list[Node] = []
            super_inits(init.node.kids[2], b, init.params[0], calls)
            ts = self.super_arg_types(self.classes[root].methods["__init__"], super_init_args(calls[0]), init)
            if "!" in ts:
                self.line = calls[0].line
                self.err(f"the types of the arguments of super().__init__(...) in {short(ci.name)}.__init__ must be known where class {short(ci.name)} is declared (literals, its parameters' annotations, functions, the defaults of {short(root)}.__init__): they decide which specialization of class template {short(root)} its objects begin as")
        # (its fields are typed there too, as guess types them before code is compiled, a class
        # template's object too (tbasing: Semaphore's Condition(Lock())); an error in them says so,
        # after the specialization's own note)
        depth = len(self.making)
        self.making.append(f"making the specialization of class template {shown(root)} that {short(ci.name)} derives from, where it is declared, before any code is compiled")
        self.tbasing += 1
        try:
            ci.base = self.specialize(b, ts, given, named, {})
        finally:
            self.tbasing -= 1
            while len(self.making) > depth:
                self.making.pop()
    for k in list(self.tlate):
        # (the specializations of subclasses whose own __init__ is a template, tmpl_sub, that an
        # earlier pass's code made, late_sub: made here in turn, with their bases, before any code
        # is compiled; a class that this pass does not declare, an imported one that the program
        # does not use yet, has none)
        c = self.tlate[k][0]
        if c not in self.classes or not self.tmpl_sub(self.classes[c]):
            continue
        ts = self.tlate[k][1:]
        self.line = self.classes[c].node.line
        depth = len(self.making)
        self.making.append(f"making the specialization {short(c)}({', '.join([typestr(x) for x in ts])}) that code of the program makes, where the classes are declared, before any code is compiled")
        self.tbasing += 1
        try:
            self.specialize(c, ts, {}, False, {})
        finally:
            self.tbasing -= 1
            while len(self.making) > depth:
                self.making.pop()
    for s in list(self.classes.values()):
        # (the members' specializations of those made before every class statement was declared,
        # as an annotation makes Box[int] before a subclass's: specialize leaves them for now)
        if s.origin in self.tmpl and s.tag != 0:
            for m in [x.name for x in self.classes.values() if x.base == s.origin and self.tmpl_member(x)]:
                self.member_spec(s.name, m)

def gen_sub_base(self, t: ClassInfo, init: FnInfo, ts: list[str]) -> str:
    # the specialization that the specialization of class t (tmpl_sub) for arguments of types ts
    # derives from: the one of t's base that its __init__ init's super().__init__(...) (or
    # base.__init__(self, ...)) makes, for the types that guess gives its arguments where ts types
    # init's parameters, as template_bases gives a fixed subclass's
    root = t.base
    while not self.declares(root, "__init__"):
        root = self.classes[root].base
    why = self.super_init_problem(t.name, init.node, t.base, root)
    if why != "":
        self.err(why)
    f = FnInfo("__init__", init.ll, init.node, t.name)
    f.params = init.params
    f.ptypes = [t.name] + ts
    f.mod = init.mod
    calls: list[Node] = []
    super_inits(init.node.kids[2], t.base, init.params[0], calls)
    pts = self.super_arg_types(self.classes[root].methods["__init__"], super_init_args(calls[0]), f)
    if "!" in pts:
        self.line = calls[0].line
        self.err(f"the types of the arguments of super().__init__(...) in {short(t.name)}.__init__ must be known from the types of its parameters (literals, its parameters, functions, the defaults of {short(root)}.__init__): they decide which specialization of class template {short(root)} its objects begin as")
    return self.specialize(t.base, pts, {}, False, {})

def gen_late_sub(self, c: str, ts: list[str], doing: str) -> None:
    # a specialization of class c (tmpl_sub) for arguments of types ts (doing: specialize's key of
    # it), which compiled code makes: code that dispatches on a value of its base's type, or tests
    # its class, may have been compiled without it. It is kept in tlate, which the passes keep, as
    # hierarchies, and the pass ends (NeedHierarchy, once discovery has compiled the program, or at
    # an error, err): the next one makes it where the classes are declared (template_bases), so
    # that every class a value may be of is known before code is compiled. Only for types that
    # the declarations know, all of the same name in each pass: no specialization of a class
    # template, nor a lambda, nested function or bound method, which a pass makes as its code
    # needs them (late_type)
    if doing in self.tlate:
        self.err(f"internal error: the specialization {short(c)}({', '.join([typestr(x) for x in ts])}) made where the classes are declared is made again by compiled code")
    for x in ts:
        if not late_type(x):
            self.err(f"a subclass of a class template whose own __init__ is a class template, {short(c)}, is not supported for an argument of type {typestr(x)} (an object of a class template's specialization, a lambda, a nested function or a bound method): its specializations are made where the classes are declared, before code makes these")
    self.tlate[doing] = [c] + ts
    self.newlate = True

def late_type(t: str) -> bool:
    # (late_sub) does type t name only what the declarations know: no specialization (C-1), and of
    # functions (fn[...]) only a module's (f:), a builtin module's (b:) or a builtin type's method
    # (u:), not a lambda or nested function (c:) or a bound method (m:)
    if "-" in t or "<" in t:
        return False
    i = t.find("fn[")
    while i >= 0:
        if t[i + 3 : i + 5] != "f:" and t[i + 3 : i + 5] != "b:" and t[i + 3 : i + 5] != "u:":
            return False
        i = t.find("fn[", i + 3)
    return True

def super_arg_type(self, e: Node, f: FnInfo) -> str:
    # (super_arg_types) the type of argument e of a call in function f, as guess infers it; None's
    # and an empty tuple's too, which call_fn passes as such
    if e.kind == "None":
        return "None"
    if e.kind == "tuple" and len(e.kids) == 0:
        return self.ctype("tuple", [])
    return self.guess(e, f)

def gen_super_arg_types(self, init: FnInfo, args: list[Node], f: FnInfo) -> list[str]:
    # the types of the arguments that super().__init__(args), in __init__ f of a subclass of a
    # class template, passes to the template's __init__ init (after self), as call_fn binds them:
    # by position and by name, a default where none is given, *args as a tuple and **kwargs as a
    # record (guess_varargs); each as guess infers it, None and () too. ["!"] where one cannot be
    np = len(init.params)
    ts = [""] * (np - 1)
    extra: list[str] = []
    names: list[str] = []
    types: list[str] = []
    pos = 1
    if init.vartup != "":
        return ["!"]
    for a in args:
        if a.kind == "starred" or a.kind == "dstar":
            return ["!"]
        t = super_arg_type(self, a.kids[0] if a.kind == "kw" else a, f)
        if t == "" or t.startswith("!"):
            return ["!"]
        if a.kind == "kw":
            j = init.params.index(a.s) if a.s in init.params else -1
            if init.kwarg >= 0 and (j < 0 or j < init.posonly or j == init.kwarg or j == init.vararg):
                if a.s in names:
                    return ["!"]
                names.append(a.s)
                types.append(init.kwelem if init.kwelem != "" else t)
            elif j < 1 or j < init.posonly or j == init.vararg or ts[j - 1] != "":
                return ["!"]
            else:
                ts[j - 1] = t
        elif init.vararg >= 0 and pos >= init.vararg:
            extra.append(init.varelem if init.varelem != "" else t)
        elif pos >= np or pos == init.kwarg or (init.npos >= 0 and pos >= init.npos):
            return ["!"]
        else:
            ts[pos - 1] = t
            pos += 1
    for i in range(1, np):
        if i == init.vararg:
            ts[i - 1] = self.ctype("tuple", extra)
        elif i == init.kwarg:
            ts[i - 1] = "kw[" + ",".join([names[j] + ":" + types[j] for j in range(len(names))]) + "]"
        elif ts[i - 1] == "" and init.defaults[i].kind == "noann":
            return ["!"]
        elif ts[i - 1] == "":
            t = super_arg_type(self, init.defaults[i], FnInfo("", "", init.node, ""))
            if t == "" or t.startswith("!"):
                return ["!"]
            ts[i - 1] = t
    return ts

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
            for i in range(len(ps) if not template_ok(b.s) and not (b.s == "__init__" and (not exc or st.s in self.hierarchies) and self.init_generic(st)) else 0):
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
    self.modchk(c)  # (the names of the identity decorators the loader dropped: Loader.identity_decos)
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
    # does class c derive from abc.ABC, or from a class whose statement passes metaclass=ABCMeta,
    # or whose base was collections.abc's Iterator or Iterable (iter_abc): ABCMeta makes it
    while c in self.classes:
        if c == "abc$ABC" or c in self.abcmeta or c in self.iterabc or self.classes[c].origin in self.iterabc:
            return True  # (collections.abc's Iterator and Iterable are ABCMeta's too: iter_abc)
        c = self.classes[c].base
    return False

def tv_reads(st: Node) -> list[Node]:
    # the names that TypeVar statement st's constraints and bound read, as qualified (Loader.qexpr)
    out: list[Node] = []
    todo = [a.kids[0] if a.kind == "kw" else a for a in st.kids[1].kids[2:] if a.kind != "kw" or a.s == "bound"]
    while len(todo) > 0:
        n = todo.pop()
        if n.kind == "name":
            out.append(n)
        for k in n.kids:
            todo.append(k)
    return out


# typing's names that TypeVar's bound may not be plain (typing._type_check's TypeError)
BOUND_FORMS = "Annotated ClassVar Concatenate Final Generic Literal NotRequired Optional Protocol ReadOnly Required TypeGuard TypeIs Union Unpack".split()

# typing's names that typing._type_check takes as types (as TypeVar's bound, and as an argument of
# a subscript of typing's), each with the number of type arguments that it takes: 0, the special
# forms that are types; * any (Tuple); the others typing's aliases of classes
TV_TYPES = (
    "Any:0 LiteralString:0 Never:0 NoReturn:0 Self:0 TypeAlias:0 AbstractSet:1 AsyncContextManager:1-2 AsyncGenerator:1-2 "
    "AsyncIterable:1 AsyncIterator:1 Awaitable:1 Callable:2 ChainMap:2 Collection:1 Container:1 ContextManager:1-2 "
    "Coroutine:3 Counter:1 DefaultDict:2 Deque:1 Dict:2 FrozenSet:1 Generator:1-3 ItemsView:2 Iterable:1 Iterator:1 "
    "KeysView:1 List:1 Mapping:2 MappingView:1 Match:1 MutableMapping:2 MutableSequence:1 MutableSet:1 OrderedDict:2 "
    "Pattern:1 Reversible:1 Sequence:1 Set:1 Tuple:* Type:1 ValuesView:1"
).split()

# why tv_problem() rejects what it cannot tell evaluates
TVFORMS = "only classes, type aliases, TypeVars, typing's types, their subscripts and '|' of them, None and strings are supported in a TypeVar's constraints and bound, which Pystachy does not evaluate (CPython does, when the assignment runs)"


def tv_type(nm: str) -> str:
    # (TV_TYPES) how many type arguments typing's nm takes, a type that TypeVar takes as its
    # bound; or "" if it is no such type
    for x in TV_TYPES:
        if x.startswith(nm + ":"):
            return x[len(nm) + 1 :]
    return ""


def gen_bound_problem(self, x: Node) -> str:
    # the TypeError CPython's TypeVar raises for bound x (typing._type_check): a plain special
    # form (Union), Generic or Protocol, a subscript of ClassVar, Final, Generic or Protocol, or
    # a tuple; else ""
    if x.kind == "tuple":
        return "Bound must be a type. Got a tuple"
    b = x.kids[0] if x.kind == "index" else x
    p = self.imported_ref(b) if b.kind == "name" or b.kind == "attr" else ""
    nm = p[p.rfind(".") + 1 :]
    if not (p.startswith("typing.") or p.startswith("typing_extensions.")) or nm not in BOUND_FORMS:
        return ""
    if x.kind == "index":
        return f"typing.{nm}[...] is not valid as type argument" if nm in ["ClassVar", "Final", "Generic", "Protocol"] else ""
    return f"Plain <class 'typing.{nm}'> is not valid as type argument" if nm == "Generic" or nm == "Protocol" else f"Plain typing.{nm} is not valid as type argument"


def gen_tv_names(self, e: Node) -> str:
    # what name or attribute e of a TypeVar's constraints or bound names: "class" (also a
    # builtin one), "typevar", "alias" (a type alias), or "typing.<name>" or
    # "collections.abc.<name>"; else "" (a variable, a function, a class's attribute)
    if e.kind == "name" and (e.s in self.classes or e.s in GENERICS or e.s in ["int", "float", "complex", "str", "bytes", "bool", "object"]):
        return "class"
    if e.kind == "name" and e.s in self.typevars:
        return "typevar" if e.s not in self.tvtuples else ""
    if e.kind == "name" and e.s in self.taliases:
        return "alias"
    p = self.imported_ref(e)
    p = "typing." + p[18:] if p.startswith("typing_extensions.") else p
    return p if (p.startswith("typing.") and p[7:] in TYPING) or p.startswith("collections.abc.") else ""


def gen_tv_problem(self, e: Node, ctx: int) -> str:
    # why Pystachy cannot drop e, part of a TypeVar's constraint (ctx 0) or bound (1), which it
    # does not evaluate: CPython's error there, or "!" where it cannot tell that CPython
    # evaluates e without error (or running code of the program) and TypeVar takes it; else "".
    # e may also be an argument of a subscript of typing's (2: typing._type_check checks it as
    # TypeVar checks a bound, and makes a string a forward reference, which it compiles), of a
    # builtin class's or collections.abc's (3: any), of a generic class's (4: a string is a
    # forward reference), or an operand of '|' (5)
    k = e.kind
    if k == "None":
        return ""
    if k == "str":
        return "" if ctx == 0 or ctx == 1 or ctx == 3 else "!"
    if k == "badattr":
        # (a module or its __dict__, which TypeVar takes: a missing attribute is typevar_def's)
        return "" if ctx < 2 and (e.s.endswith("cannot be used as a value") or e.s == "module attribute '__dict__' is not supported") else "!"
    if k == "name" or k == "attr":
        r = self.tv_names(e)
        if r == "class" or r == "typevar" or r.startswith("collections.abc."):
            return ""
        if r == "alias":
            # (its value, which CPython evaluated where it assigned it)
            st = self.taliases[e.s]
            return self.tv_problem(st.kids[-1], ctx) if st.kind != "typealias" else ""
        nm = r[7:]
        if r == "":
            return "!"
        if ctx == 0 or ctx == 3 or ctx == 4 or tv_type(nm) != "":
            return ""
        if nm in BOUND_FORMS and ctx != 5:
            return f"Plain <class 'typing.{nm}'> is not valid as type argument" if nm == "Generic" or nm == "Protocol" else f"Plain typing.{nm} is not valid as type argument"
        return "!"
    if k == "binop" and e.s == "|":
        if e.kids[0].kind == "None" and e.kids[1].kind == "None":
            return "unsupported operand type(s) for |: 'NoneType' and 'NoneType'"
        r = self.tv_problem(e.kids[0], 5)
        return r if r != "" else self.tv_problem(e.kids[1], 5)
    if k != "index":
        return "!"
    b = e.kids[0]
    xs = e.kids[1].kids if e.kids[1].kind == "tuple" else [e.kids[1]]
    r = self.tv_names(b) if b.kind == "name" or b.kind == "attr" else ""
    nm = r[r.rfind(".") + 1 :]
    if r == "class" and b.s in GENERICS:
        return self.tv_items(xs, 3, b.s == "tuple")  # (types.GenericAlias: any arguments)
    if r == "class" and b.s in self.tparams:
        return self.tv_items(xs, 4, False)  # (the number of them: alias_problem)
    if nm == "Callable" and (r.startswith("typing.") or r.startswith("collections.abc.")):
        # (Callable[[A, B], R] or Callable[..., R]; typing's makes each of A and B a forward
        # reference if a string, and checks R)
        c = 2 if r.startswith("typing.") else 3
        if len(xs) != 2 or (xs[0].kind != "list" and xs[0].kind != "ellipsis"):
            return "Callable must be used as Callable[[arg, ...], result]"
        p = self.tv_items(xs[0].kids, 4 if c == 2 else 3, False)
        return p if p != "" else self.tv_problem(xs[1], c)
    if r.startswith("collections.abc."):
        return self.tv_items(xs, 3, False)
    w = tv_type(nm) if r.startswith("typing.") else ""
    if nm != "Optional" and nm != "Union" and (w == "" or w == "0"):
        return "!"  # (Literal, Annotated, ClassVar, ...: not supported)
    lo = 1 if nm == "Optional" or nm == "Union" else 0 if w == "*" else int(w[0])
    hi = 1 if nm == "Optional" else len(xs) if w == "*" or nm == "Union" else int(w[-1])
    if len(xs) < lo or len(xs) > hi:
        return f"Too {'many' if len(xs) > hi else 'few'} arguments for typing.{nm}; actual {len(xs)}, expected {str(hi) if lo == hi else 'at least ' + str(lo) if len(xs) < lo else str(hi)}"
    return self.tv_items(xs, 2, nm == "Tuple")


def gen_tv_items(self, xs: list[Node], ctx: int, tup: bool) -> str:
    # (tv_problem) the first problem of xs, a subscript's arguments, each in ctx; of a tuple's
    # (tup), the last of two or more may be ...
    for i in range(len(xs)):
        if xs[i].kind == "ellipsis" and tup and i > 0 and i == len(xs) - 1:
            continue
        r = self.tv_problem(xs[i], ctx)
        if r != "":
            return r
    return ""


def gen_prepare_program(self, mods: list[Mod]) -> PreparedProgram:
    self.pipeline.begin("prepare")
    started = timing_start()
    phase = "runtime" if self.rtmode else "program"
    self.opts = optimizations()
    self.identity_modules(mods)  # (which modules' code tracks numeric identity: dynamic.py)
    self.clsbodies = [m.body for m in mods]  # (class_values.py's class_value_annotated)
    # (lib's modules of range objects, of object()'s and of complex numbers bind no global of another module: the
    # names they bind do not keep a global of the program from being constant)
    own = [m for m in mods if m.name != RANGES and m.name != OBJECTS and m.name != COMPLEXS]
    if "moduleints" in self.opts:
        self.intglobals = module_ints(own, self.intat)
    self.strglobals = module_strs(own, self.strtuples)
    module_anns(own, self.globanns)
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
    tvdefs: list[Node] = []  # (the TypeVar statements, whose arguments are checked below)
    for m in mods:
        m.body.kids = self.typing_forms(m, m.body.kids, False, False, True)
        for i in range(len(m.body.kids)):
            st = m.body.kids[i]
            if (st.kind == "class" or st.kind == "subclass") and local_class(st.s):
                # (a class that a function's body defines: its __qualname__ is F.<locals>.C,
                # Loader's local_classes)
                RENAMED[st.s] = st.s.replace(LOCALS, ".<locals>.")
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
            elif st.kind == "subclass" and len(st.kids) == 2 and self.iter_abc(st) != "":
                # class C(Iterator[T]) of typing or collections.abc, which defines the methods
                # that abstract base requires (iter_abc): a class of its own, generic in the type
                # variables its subscript names, as with Generic[T] (the base gives it nothing it
                # uses; ABCMeta's attributes are rejected where reflection would show them)
                m.body.kids[i] = st.kids[0]
                self.iterabc[st.s] = True
                tvs: list[str] = []
                subscript_tvars(st.kids[1], self.typevars, tvs)
                if len(tvs) > 0:
                    self.tparams[st.s] = tvs
            elif st.kind == "subclass" and len(self.implicit_tparams(st)) > 0:
                # class S(Visitor[T]): generic in the type variables that its bases' subscripts
                # name, as with Generic[T] first (PEP 484), which generic_subclass passes on
                self.tparams[st.s] = self.implicit_tparams(st)
                self.implicitgen[st.s] = True
            elif st.kind == "subclass" and st.kids[1].kind == "typeparams" and self.class_params(st) == "":
                m.body.kids[i] = st.kids[0]  # class C[T]: as class C(Generic[T]) (see class_params)
                self.tparams[st.s] = st.kids[1].s.split()
                self.pep695[st.s] = True
            elif self.typevar_def(st):
                self.typevars.append(st.kids[0].s)
                tvdefs.append(st)
                m.body.kids[i] = mk("pass", "", st.line, [])
            elif st.kind == "typealias" and st.s in self.taliases:
                m.body.kids[i] = mk("pass", "", st.line, [])  # (a type alias, which only annotations name)
            elif st.kind == "assign" and st.kids[0].kind == "name" and st.kids[0].s in self.taliases and self.taliases[st.kids[0].s] is st and not self.alias_kept(st.kids[0].s):
                # (N = NewType("N", T) binds N where it runs, as a def does: a call N(x) that may come
                # first checks it, see call. CPython evaluates an alias's value there, which may read
                # a class through its module before that module binds it: see ann_reads)
                vreads: dict[str, bool] = {}
                chk_names(st.kids[1], vreads)
                m.body.kids[i] = mk("newtype", st.kids[0].s, st.line, []) if self.newtype_name(st.kids[0].s) else mk("aliasvalue", st.kids[0].s, st.line, []) if len(vreads) > 0 else mk("pass", "", st.line, [])
    module_values(own, self.globvalues, self.globowners, self.globalts)  # (after typing_forms: x: Final = v is x = v)
    for q in self.taliases:
        # (CPython evaluates an assigned alias's value where it assigns it, a type statement's
        # only where its __value__ is read)
        # (of N = NewType("N", T), T: alias_value)
        why = self.alias_problem(self.alias_value(q)) if self.taliases[q].kind == "assign" else ""
        if why != "":
            self.line = self.taliases[q].line
            what = "this NewType's type" if self.newtype_name(q) else "this type alias's value"
            self.err(why[1:] if why.startswith("!") else f"{why} (CPython evaluates {what} when the assignment runs)")
    for st in tvdefs:
        # a TypeVar's constraints and bound are evaluated as an alias's value is, where a subscript
        # with the wrong number of arguments raises CPython's TypeError (Callable[int], Box[int,
        # str] of a Box(Generic[T])); what Pystachy could not compile in an alias is no error here,
        # as these types bind nothing (typevar_def)
        if self.imported_ref(st.kids[1].kids[0]) != "typing.TypeVar":
            continue
        for a in st.kids[1].kids[2:]:
            why = self.alias_problem(a.kids[0] if a.kind == "kw" else a) if a.kind != "kw" or a.s == "bound" else ""
            if why != "" and not why.startswith("!"):
                self.line = st.line
                self.err(f"{why} (CPython evaluates a TypeVar's constraints and bound when the assignment runs)")
    if len(self.taliases) > 0:
        self.recursive_aliases()
        # an annotation that names a type alias is its value (unalias)
        for m in mods:
            self.unalias_all(m.body)
    class_counts: dict[str, int] = {}
    for m in mods:
        for st in m.body.kids:
            if st.kind == "class" or st.kind == "subclass":
                self.cnodes[st.line] = st
                if m.name != "":
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
            deferred = st.kind == "subclass" and (why.startswith("inheritance with generic class templates") or any(b.kind == "name" and b.s in self.deferred_hierarchies for b in st.kids[1:]))
            if deferred:
                self.deferred_hierarchies[st.s] = True
            for x in (st.kids[0] if st.kind == "subclass" else st).kids[0].kids if why != "" else []:
                if x.kind == "assign" and x.s == "Final":
                    # (x: Final = v, which typing_forms made a class attribute: rejected where it
                    # is, as before, in a class that is not compiled, whose creation may read its
                    # annotations, as a NamedTuple's or a TypedDict's does)
                    self.line = x.line
                    self.err(FINAL_FIELD)
            if why != "" and m.name == "":
                if deferred:
                    self.request_hierarchy(st.s)
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
                if ci.base == "" and len(st.kids) == 2 and builtin_base(st.kids[1]) != "":
                    self.bsubn[st.s] = st.kids[1]  # (an ordinary class but for its objects' header: builtin_bases.py)
                elif ci.exc == "":
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
    for ci in list(self.classes.values()):
        if ci.node.line in ORDERED:
            self.ordered_class(ci)  # (before the methods of the class bodies are declared)
    for m in mods:
        self.class_stores(m.body.kids, "", "")  # (before an annotation makes a class template's specialization)
    for ci in self.classes.values():
        for d in ci.node.kids[0].kids:
            # (a class method's cls.x = v, as declare_fn takes the method: its one decorator)
            if d.kind == "def" and len(d.kids) == 4 and len(d.kids[3].kids) == 0 and d.kids[3].s == "classmethod" and len(d.kids[0].kids) > 0 and d.kids[0].kids[0].kind == "param":
                self.class_stores(d.kids[2].kids, d.kids[0].kids[0].s, ci.name)
    for m in mods:
        self.any_variables(m.body, False)
    # the sentinels, NAME = object() (also NAME: Final[Any] = object()), that nothing else binds,
    # in any module: constant_writes also counts global declarations and other modules' stores
    # of mod.NAME. A parameter annotated T whose default is one is a sentinel parameter (declare_fn)
    writes: dict[str, int] = {}
    for m in own:
        constant_writes(m.body, writes)
    for m in mods:
        for st in m.body.kids:
            v = st.kids[-1] if (st.kind == "assign" and len(st.kids) == 2) or (st.kind == "annassign" and len(st.kids) == 3) else None
            if v is not None and st.kids[0].kind == "name" and v.kind == "call" and len(v.kids) == 1 and v.kids[0].kind == "name" and v.kids[0].s == "object" and writes.get(st.kids[0].s, 0) == 1:
                self.sentinelglobals[st.kids[0].s] = True
    # Only ordinary inheritance hierarchies need a runtime class tag. Keeping unrelated
    # classes unchanged preserves their compact layout, including dataclasses and tuples.
    for ci in self.classes.values():
        if ci.exc == "" and ci.base in self.classes:
            ci.tag = 1
            self.classes[ci.base].tag = 1
            for secondary in ci.roles:
                if secondary in self.classes[ci.base].roles:
                    continue
                # (an interface's own chain, role_chain: each class of it is a secondary base of
                # this class too, and of the objects that a value of its type may be)
                chain = self.role_chain(ci.base, secondary)
                for role in chain if len(chain) > 0 else [secondary]:
                    self.classes[role].tag = 1
                    self.classes[role].isrole = True
                    self.classes[role].isiface = self.classes[role].isiface or len(chain) > 0
                    # These unrelated static types can now denote the same instance: the
                    # primary ancestors, and the other secondary bases, each with the classes
                    # it extends (role_chain).
                    others: list[str] = []
                    for r in ci.roles:
                        if r != secondary:
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
    self.ntag = tag  # (a template hierarchy's specializations take the next ones: templates.new_tag)
    self.cm_exits()  # (decided while the class templates are classes too: see cm_exits)
    # The classes for which a template is an error, as init_template's hier takes them: those of
    # a hierarchy, and the classes that the __init__ of one of these takes as a parameter
    # (Checker(errors: Errors)), which a template would make a template in turn. A program with
    # such a parameter was rejected while its class stayed a template, so only programs that did
    # not compile see the class compiled as an ordinary one, used or not
    # Activated dependencies may have no class tag: their requesting imported child
    # was still deferred when declarations were collected on this pass.
    fixedcls: dict[str, bool] = dict(self.hierarchies)
    for ci in self.classes.values():
        if ci.tag > 0:
            fixedcls[ci.name] = True
    grow = True
    while grow:
        grow = False
        for ci in list(self.classes.values()):
            if ci.name in fixedcls:
                named: dict[str, bool] = {}
                self.init_param_classes(ci.node, named)
                for c in named:
                    if c not in fixedcls and self.classes[c].exc == "":
                        fixedcls[c] = True
                        grow = True
    grow = True
    while grow:
        # the class templates: an __init__ parameter without an annotation, or with one that
        # names a class template (Holder(b: Box)), which then types nothing either
        grow = False
        for ci in self.classes.values():
            if ci.name not in self.tmpl and ci.exc == "" and (self.init_template(ci.node, ci.name in fixedcls) or self.tmpl_member(ci)):
                self.tmpl[ci.name] = True
                grow = True
    for ci in self.classes.values():
        ci.init_only = ci.exc == "" and ci.name not in self.tmpl and self.init_generic(ci.node)
        if ci.tag != 0 and ci.name in self.tmpl:
            self.request_fixed_params(ci.name)
            why = self.template_hierarchy(ci)  # (a template hierarchy's root or member: template_bases)
            if why != "":
                self.line = ci.node.line
                self.err(why)
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
                cd = mk("cdefaults", st.s, st.line, [])
                cd.mchk = (st.kids[0] if st.kind == "subclass" else st).mchk  # (its identity decorators' reads: Loader.identity_decos)
                top.append(cd)
            else:
                top.append(st)
        tops.append(top)
    self.template_bases()  # (the specializations that a template hierarchy's classes derive from)
    for ci in self.classes.values():
        self.inherit(ci)
    for m in mods:
        for q in m.finals:
            # CPython's @final sets the class's __final__ to True, over what its body or a base's
            # binds, which the class would read where the loader dropped the decorator
            c = q
            while c in self.classes and q in self.classes:
                if "__final__" in self.body_names(self.classes[c].node):
                    self.line = self.classes[q].node.line
                    self.err(f"@final on class {short(q)} is not supported where {'its body' if c == q else 'the body of ' + short(c)} binds __final__ (CPython's @final sets __final__ to True)")
                c = self.classes[c].base
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
    for k in list(self.cstores):
        if k not in self.cvars:
            del self.cstores[k]  # (no class variable: a dataclass's, or no attribute of the class's body)
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
    for st in tvdefs:
        # a class that a TypeVar's bound or constraints read through its module (a.Later), which
        # that module may not have defined there, as during a circular import: CPython's
        # AttributeError, which isinstance() would check (isinst_reads) but a TypeVar's
        # arguments, which Pystachy does not evaluate, cannot
        for rd in tv_reads(st):
            if rd.chk and rd.s in self.gflag and rd.s in self.classes:
                self.line = st.line
                self.err(f"class '{shown(rd.s)}' may not be defined where this TypeVar reads it through its module (as during a circular import): not supported (CPython raises AttributeError if it is not)")
        for a in st.kids[1].kids[2:] if self.imported_ref(st.kids[1].kids[0]) == "typing.TypeVar" else NOKIDS:
            # (what TypeVar checks of its bound, typing._type_check; and what Pystachy cannot tell
            # CPython evaluates without error, which it rejects: tv_problem)
            if a.kind == "kw" and a.s != "bound":
                continue
            x = a.kids[0] if a.kind == "kw" else a
            why = self.bound_problem(x) if a.kind == "kw" else ""
            why = self.tv_problem(x, 1 if a.kind == "kw" else 0) if why == "" and not is_const(x) else why
            self.line = st.line
            if why == "!":
                self.err(TVFORMS)
            if why != "":
                self.err(f"{why} (CPython evaluates a TypeVar's constraints and bound when the assignment runs)")
    for nm in self.gflag:
        if nm in self.funcs or nm in self.classes or self.newtype_name(nm):
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
    early: dict[str, str] = {}  # (the types of the constants typed before any module code compiles)
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
                    early[st.kids[0].s] = k
                elif k == "True" or k == "False":
                    self.declare(st.kids[0].s, "bool")
                    early[st.kids[0].s] = "bool"
    grown = True
    while grown:
        # and so is a module's copy of such a constant of another module (from m import K, also as
        # mypy's types.py re-exports type_visitor's ANY_STRATEGY), or of such a copy: typed where a
        # circular import reads it (earlycopies, Gen.load_name), as the import binds it before its
        # module imports any module after it, and a read before then raises ImportError, as for
        # the constant itself
        grown = False
        for m in mods:
            for st in m.body.kids if m.name != "" else []:
                if st.kind == "assign" and st.s == "from" and len(st.kids) == 2 and st.kids[0].kind == "name" and st.kids[1].kind == "name" and st.kids[1].s in early and st.kids[0].s not in early and st.kids[0].s not in self.gtypes and st.kids[0].s not in self.noneglobals:
                    early[st.kids[0].s] = early[st.kids[1].s]
                    self.earlycopies[st.kids[0].s] = early[st.kids[1].s]
                    grown = True
    for m in mods:
        self.mfile[m.name] = m.path[2:] if m.path.startswith("./") else m.path
    timing_end(phase + ".prepare", started)
    self.pipeline.complete("prepare")
    return PreparedProgram(self.pipeline, mods, tops)


def gen_discover_program(self, prepared: PreparedProgram) -> None:
    if prepared.owner is not self.pipeline:
        fail("internal error: prepared program belongs to another compiler attempt", 0)
    self.pipeline.begin("discover")
    started = timing_start()
    phase = "runtime" if self.rtmode else "program"
    mods = prepared.modules
    tops = prepared.tops
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
        if mods[i].name != ITERS and mods[i].name != RANGES and mods[i].name != OBJECTS and mods[i].name != COMPLEXS:
            # (lib's modules of iter()'s classes, of range's, of object's and of complex's run no
            # code: nothing imports them, see Loader.program)
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
                self.extern_decl(f, True)
            else:
                self.untold(f, [f.ret] + f.ptypes, "declared")
                self.extern_decl(f)
        elif not f.generic and f.ll not in self.compiled:
            self.function(f, f.node.kids[2].kids)
    for ci in [x for x in self.classes.values()]:
        for f in ci.methods.values():
            if f.cls != ci.name or (ci.name in self.tmpl and f.deco == ""):
                continue  # (an exception class's base's; a class template's, but its static and class methods: its specializations')
            if (ci.mod != "" or ci.init_only) and f.ll not in self.lazy:
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
    if self.newlate:
        raise NeedHierarchy()  # (code made a specialization that the next pass makes first: late_sub)
    if len(self.newhints) > 0 and (not self.final or any(k.startswith("cmpfield:") or k.startswith("cmpwrite:") for k in self.newhints)):
        raise Rejoin()  # (joins found wider types: the next pass compiles them, see join_hint)
    self.pipeline.complete("discover")

# ---- definite assignment, before code generation: CPython raises UnboundLocalError or
# NameError when a read finds its variable unassigned. Reads that cannot are plain loads;
# the others (Node.chk) test an "is assigned" flag kept only for the variables they read.
