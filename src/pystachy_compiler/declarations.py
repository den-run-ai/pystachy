"""Declarations component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.utils import is_union, umembers
from src.pystachy_compiler.analysis import calls_init, local_names, stmt_walrus
from src.pystachy_compiler.diagnostics import shown
from src.pystachy_compiler.ir import ClassInfo, FnInfo, Ins, Val
from src.pystachy_compiler.module import Mod
from src.pystachy_compiler.names import owner, short
from src.pystachy_compiler.specs import (
    ANYUSE,
    CLASSVAR,
    CTYPES,
    EXCATTRS,
    EXCFIELDS,
    EXCINIT,
    FROZENERR,
    IOPS,
    ITERS,
    METHODS,
    MODFUNCS,
    OPTTYPES,
    PATHLIKE,
    PYBUILTINS,
    RANGEC,
    RANGES,
    SPECIAL,
    STANDINS,
    STUB,
    TYPEARGS,
    TYPEVAR,
    TYPE_SIZE,
    TYPING,
    UNARY,
    UNCALLED,
    exc_derives,
    is_excname,
)
from src.pystachy_compiler.syntax import Node, has_kind, has_value_return, mentions, mk, other_return
from src.pystachy_compiler.utils import (
    clone,
    elem,
    gelem,
    gsend,
    is_callable,
    is_const,
    is_dict,
    is_fset,
    is_gen,
    is_list,
    is_opt,
    is_set,
    is_sopt,
    is_tuple,
    is_vtuple,
    kw_names,
    kw_types,
    literal_format,
    rename,
    selem,
    takes_self,
    targs,
    template_ok,
    tname,
    typestr,
    unopt,
)


def gen_ctype(self, base: str, ts: list[str]) -> str:
    # A composite type, checking its serialized size before join copies any children.
    # In a recursive template, a two-item tuple may double this on every instance.
    size = len(base) + 2 + (len(ts) - 1 if len(ts) > 0 else 0)
    for t in ts:
        size += len(t)
        if size > TYPE_SIZE:
            self.err(f"type representation exceeds {TYPE_SIZE} bytes; simplify the type or annotate template parameters")
    t = base + "[" + ",".join(ts) + "]"
    # Allocation and slot accesses derive a tuple's layout from its type string.
    # Reject a broken serialization before either can use a different item count.
    if base == "tuple" and targs(t) != ts:
        self.err("internal error: tuple item types do not round-trip")
    return t

def gen_none_items(self, t: str) -> str:
    # A tuple key with str | None in place of each None item.
    if t == "None":
        return "opt[str]"
    return self.ctype("tuple", [self.none_items(x) for x in targs(t)]) if is_tuple(t) else t

def gen_subst(self, t: str, T: str, K: str, V: str, S: str) -> str:
    # Instantiate a builtin method's type without allocating an oversized replacement: its K and
    # V become the key and value types at once (a key type may name a class Val)
    if t == "T":
        return T
    if t == "S":
        return S
    if len(t) + t.count("K") * (len(K) - 1) + t.count("V") * (len(V) - 1) > TYPE_SIZE:
        self.err(f"type representation exceeds {TYPE_SIZE} bytes; simplify the type or annotate template parameters")
    out = ""
    for c in t:
        out += K if c == "K" else V if c == "V" else c
    return out

def gen_typeof(self, n: Node) -> str:
    t = self.ann(n)
    if t.startswith("!"):
        self.err(t[1:])
    return t

def gen_ann(self, n: Node) -> str:
    # the type annotation n denotes, or "!" and why Pystachy does not support it (typeof's error,
    # which a declaration in an imported module defers to where the program uses it)
    k = n.kind
    if k == "None":
        return "None"
    if k == "str":
        return self.ann(self.parse_expr(n.s))
    s = n.s
    if k == "attr":
        c = self.imported_ref(n)
        if c.startswith("ffi.") and c[4:] in CTYPES:
            return "int"
        if c == "ffi.c_buf" or c == "ffi.c_float":
            return "str" if c == "ffi.c_buf" else "float"
    if k == "name":
        if s in self.tmpl and self.selfcls in self.classes and self.classes[self.selfcls].origin == s:
            return self.selfcls  # (in its specialization's methods and fields: that specialization, as Self)
        if s in self.tmpl:
            why = "namedtuple() made it, whose fields each call types" if s in self.cnts else "its __init__ takes a parameter without an annotation"
            return f"!class {shown(s)} is a class template ({why}): each call makes an object of a specialization of its own, which an annotation cannot name here; leave the annotation out"
        if s == "int" or s == "float" or s == "bool" or s == "str" or s == "bytes" or s in self.classes:
            return s
        if s == "range" and RANGEC in self.classes:
            return RANGEC  # (the class of range objects, lib/_pystachy_range.py)
        if self.imported(s).startswith("ffi.") and self.imported(s)[4:] in CTYPES:
            return "int"  # (a C integer type, in an @extern function's signature: see CTYPES)
        if self.imported(s) == "ffi.c_buf":
            return "str"  # (a str's UTF-8 bytes, NULs and all, for a C function that takes their length too)
        if self.imported(s) == "ffi.c_float":
            return "float"  # (a C float, 32 bits, in an @extern function's signature)
        if is_excname(s):
            return "exc"  # (a builtin exception class: any exception, not only those of the class)
        if s in self.taliases:
            return self.alias_ann(n)
        t = self.typing_name(s)
        if t == "TextIO" or t == "Self" or t.startswith("!"):
            return "file" if t == "TextIO" else self.self_type() if t == "Self" else t
        if t == "Any":
            return "!" + ANYUSE  # (where no call types what it annotates: see declare_fn)
        if s in self.unsupported:
            return "!" + self.unsupported[s]
        if s in self.typevars:
            t = self.tvar(s)
            if s in self.tvtuples:
                return f"!TypeVarTuple '{short(s)}' is only supported unpacked (*{short(s)}), in tuple[...], Callable[[...], R] and *args" if t != "" else f"!TypeVarTuple '{short(s)}'{TYPEVAR}"
            return t if t != "" else f"!TypeVar '{short(s)}'{TYPEVAR}"
    elif k == "attr" and self.typing_attr(n) == "TextIO":
        return "file"
    elif k == "attr" and self.typing_attr(n) == "Self":
        return self.self_type()
    elif k == "attr" and self.typing_attr(n) == "Any":
        return "!" + ANYUSE
    elif k == "binop" and n.s == "|" and self.has_path(n):
        return self.path_union(self.union_members(n, []))
    elif k == "binop" and n.s == "|" and n.kids[1].kind == "None":
        return self.opt(self.ann(n.kids[0]), n.kids[0])
    elif k == "binop" and n.s == "|" and n.kids[0].kind == "None":
        return self.opt(self.ann(n.kids[1]), n.kids[1])  # None | T
    elif k == "binop" and n.s == "|":
        ts = [self.ann(x) for x in self.union_members(n, [])]
        for t in ts:
            if t.startswith("!"):
                return t
        return self.union_type(ts)  # A | B
    elif k == "index" and n.kids[0].kind == "name" and n.kids[0].s == "type" and n.kids[1].kind == "name" and (is_excname(n.kids[1].s) or (n.kids[1].s in self.classes and self.classes[n.kids[1].s].exc != "")):
        # type[BaseException], as __exit__ takes the class of the exception: exctype, which is the
        # exception itself (its class is what it shows)
        return "exctype"
    elif k == "index" and n.kids[0].kind == "name" and n.kids[0].s in self.taliases:
        return self.alias_ann(n)
    elif k == "index" and n.kids[0].kind == "name" and n.kids[0].s in self.tparams:
        return self.generic_ann(n.kids[0].s, n.kids[1])
    elif k == "index" and (n.kids[0].kind == "name" or n.kids[0].kind == "attr"):
        base = self.ann_base(n.kids[0])
        if base.startswith("!"):
            return base
        if base == "literal" or base == "annotated":
            return "!unsupported type annotation"  # (metadata is not an annotation: Literal["Any"], Annotated[int, "Any"])
        a: list[Node] = n.kids[1].kids if n.kids[1].kind == "tuple" else [n.kids[1]]
        if base == "iterator" or base == "generator":
            # Iterator[T], Generator[Y, None, R] (typing's or collections.abc's): a generator object
            # (an iterator of another kind, as #477 makes them, is not one of these)
            yr = self.gen_ann_ret(n)
            return "!" + yr[0] if len(yr) == 1 else self.gen_type(yr[0], yr[2])
        if base == "callable":
            # Callable[[A, B], R] (typing's or collections.abc's): callable[R,A,B]
            if len(a) != 2 or (a[0].kind != "list" and a[0].kind != "ellipsis"):
                return "!Callable takes a list of parameter types and a return type: Callable[[A, B], R]"
            if a[0].kind == "ellipsis":
                return "!Callable[..., R] is not supported: name the parameter types (Callable[[A, B], R])"
            cts: list[str] = [self.ann(a[1])] + self.ann_items(a[0].kids)
            for ct in cts:
                if ct.startswith("!"):
                    return ct
            return self.ctype("callable", cts)
        if base == "union" and len([x for x in a if self.pathlike(x)]) > 0:
            return self.path_union(a)
        if base == "tuple" and len(a) == 2 and a[1].kind == "ellipsis":
            t = self.ann(a[0])
            if unopt(t) not in ["int", "float", "bool", "str"]:
                return "!runtime-length tuple elements must be int, float, bool, str or their optional types"
            return self.ctype("vtuple", [t])
        ts: list[str] = self.ann_items(a) if base == "tuple" else [self.ann(x) for x in a]
        for t in ts:
            if t.startswith("!"):
                return t
        if base == "list" and len(ts) == 1:
            return self.ctype("list", [ts[0]])
        if base == "dict" and len(ts) == 2:
            return self.ctype("dict", ts) if self.key_problem(ts[0]) == "" else "!" + self.key_problem(ts[0])
        if (base == "set" or base == "frozenset") and len(ts) == 1:
            return self.ctype(base, ts) if self.elem_problem(ts[0]) == "" else "!" + self.elem_problem(ts[0])
        if base == "tuple" and (len(ts) > 0 or n.kids[1].kind == "tuple" or n.kids[1].kind == "starred"):
            return self.ctype("tuple", ts)  # (tuple[()] is the empty tuple's, as tuple[*Ts] of no types is)
        if base == "optional" and len(ts) == 1:
            return self.opt(ts[0], a[0])
        if base == "union":
            us: list[str] = []  # (Union[int, int, None] is Optional[int], as typing collapses it)
            for t in ts:
                if t not in us:
                    us.append(t)
            if len(us) == 1:
                return us[0]  # Union[T]
            if len(us) == 2 and (us[0] == "None" or us[1] == "None"):
                return self.opt(us[0] if us[1] == "None" else us[1], [x for x in a if x.kind != "None"][0])  # Union[T, None]
            return self.union_type(us)
    if self.typing_ref(n) == "Final":
        return "!a bare Final needs a value to give its type (x: Final = v, a constant in a class body); write Final[T]"
    if self.pathlike(n):
        return "!" + PATHLIKE
    return "!unsupported type annotation"

def gen_ann_base(self, b: Node) -> str:
    # what b of annotation b[...] is (a name or attribute): list, dict, tuple, set, frozenset, or
    # typing's name in lower case (callable, optional, union, ...), with Mapping a dict, Sequence
    # a list and MutableSet a set; or "!" and why not
    base = b.s
    if b.kind == "attr":
        base = self.typing_attr(b).lower()  # typing.List[int]
    elif base != "list" and base != "dict" and base != "tuple" and base != "set" and base != "frozenset":
        base = self.typing_name(base)
        if base.startswith("!"):
            return base
        base = base.lower()
    if base == "mapping" or base == "mutablemapping":
        return "dict"  # (collections.abc's and typing's: what a dict is)
    if base == "sequence" or base == "mutablesequence":
        return "list"
    if base == "mutableset":
        return "set"
    return "!" + CLASSVAR if base == "classvar" else base

def gen_ann_items(self, xs: list[Node]) -> list[str]:
    # the types annotations xs denote, those of tuple[...] or of Callable[[...], R]'s parameters:
    # *Ts and *tuple[A, B] give the types they unpack (see unpack_ann)
    ts: list[str] = []
    for x in xs:
        if x.kind == "starred":
            u = self.unpack_ann(x)
            ts.extend([u] if u.startswith("!") else targs(u))
        else:
            ts.append(self.ann(x))
    return ts

def gen_unpack_ann(self, n: Node) -> str:
    # the tuple type that *X (starred node n) unpacks in an annotation: a TypeVarTuple, which a
    # specialization of a generic class binds (see bind), or tuple[A, B]; or "!" and why not
    x = n.kids[0]
    if x.kind == "name" and x.s in self.tvtuples:
        t = self.tvar(x.s)
        return t if t != "" else f"!TypeVarTuple '{short(x.s)}'{TYPEVAR}"
    t = self.ann(x)
    if t.startswith("!") or is_tuple(t):
        return t
    return f"!*{typestr(t)} in an annotation is not supported: a TypeVarTuple (*Ts) or a tuple (*tuple[A, B]) unpacks"

def gen_tvar(self, s: str) -> str:
    # what type variable s is bound to where an annotation names it, or "": in a specialization
    # of a generic class (its fields and methods), what the call that made the object bound
    c = self.selfcls if self.selfcls != "" else self.curfn.cls
    return self.classes[c].tvars.get(s, "") if c in self.classes else ""

def gen_self_type(self) -> str:
    # typing.Self: the class of the method or field it annotates (there is no inheritance)
    c = self.selfcls if self.selfcls != "" else self.curfn.cls
    return c if c != "" else "!typing.Self is only supported in a class, for its methods and fields"

def gen_pathlike(self, n: Node) -> bool:
    # is annotation n os.PathLike or os.PathLike[T]
    if n.kind == "str":
        n = self.parse_expr(n.s)
    return self.imported_ref(n.kids[0] if n.kind == "index" else n) == "os.PathLike"

def gen_imported_ref(self, n: Node) -> str:
    # what a name or an attribute chain on one refers to through the imports ("os.fspath"), or ""
    p = ""
    while n.kind == "attr":
        p = "." + n.s + p
        n = n.kids[0]
    return self.imported(n.s + p) if n.kind == "name" else ""

def gen_union_members(self, n: Node, out: list[Node]) -> list[Node]:
    # the members of a union annotation A | B | ..., in order
    if n.kind == "binop" and n.s == "|":
        self.union_members(n.kids[0], out)
        self.union_members(n.kids[1], out)
    else:
        out.append(n)
    return out

def gen_has_path(self, n: Node) -> bool:
    return any(self.pathlike(x) for x in self.union_members(n, []))

def gen_path_union(self, ms: list[Node]) -> str:
    # the type of a union (members ms) that holds os.PathLike, which is dropped: a value of
    # another path type cannot exist in Pystachy, so str | os.PathLike[str] is a str (and with
    # None, str | None), or "!" and the error
    s = False
    none = False
    for x in ms:
        if not self.pathlike(x):
            t = self.ann(x)
            if t.startswith("!"):
                return t
            if t != "str" and t != "None" and t != "opt[str]":
                return "!" + PATHLIKE.replace(" with str ", f" with str, not with {typestr(t)} ")
            s = s or t != "None"
            none = none or t != "str"
    return ("opt[str]" if none else "str") if s else "!" + PATHLIKE

def gen_typevar_def(self, st: Node) -> bool:
    # is st T = TypeVar("T") or Ts = TypeVarTuple("Ts") (typing's or typing_extensions'): T is
    # then a name only annotations use
    if st.kind != "assign" or len(st.kids) != 2 or st.kids[0].kind != "name" or st.kids[1].kind != "call":
        return False
    c = st.kids[1]
    ref = self.imported_ref(c.kids[0])
    kind = ref[7:] if ref.startswith("typing.") else ""
    if kind != "TypeVar" and kind != "TypeVarTuple":
        return False
    self.line = st.line
    if len(c.kids) < 2 or c.kids[1].kind != "str":
        self.err(f"{kind}() needs the type variable's name, a string, as its first argument")
    for a in c.kids[2:]:
        if a.kind != "kw" or not is_const(a.kids[0]):
            self.err("a TypeVar's constraints, and a bound other than a string, are not supported")
        if a.s == "default":
            self.tvdefaults[st.kids[0].s] = True
    if kind == "TypeVarTuple":
        self.tvtuples[st.kids[0].s] = True
    return True

def gen_typevar_in(self, anns: list[Node], skip: list[str]) -> str:
    # the first TypeVar (or TypeVarTuple) annotations anns mention (also in a string) but those
    # of skip, or ""
    if len(self.typevars) == 0:
        return ""
    for a in anns:
        if a.kind == "str":
            a = self.parse_expr(a.s)
        if a.kind == "name" and a.s in self.typevars and a.s not in skip:
            return a.s
        r = self.typevar_in(a.kids, skip)
        if r != "":
            return r
    return ""

def gen_any_in(self, anns: list[Node]) -> bool:
    # do annotations anns mention typing.Any (also in a string: Any, list[Any], Mapping[str, Any],
    # Callable[..., Any]); a type alias they name is its value already (see unalias_all)
    for a in anns:
        if a.kind == "str":
            a = self.parse_expr(a.s)
        if (a.kind == "attr" or (a.kind == "name" and a.s not in self.classes)) and self.typing_ref(a) == "Any":
            return True
        if a.kind == "index" and self.typing_ref(a.kids[0]) == "Literal":
            continue  # (its strings are values: Literal["Any"])
        if a.kind == "index" and self.typing_ref(a.kids[0]) == "Annotated":
            xs = a.kids[1].kids if a.kids[1].kind == "tuple" else [a.kids[1]]
            if self.any_in(xs[:1]):
                return True
            continue  # (only its first argument is a type; later arguments are metadata)
        if a.kind != "attr" and self.any_in(a.kids):
            return True
    return False

def gen_class_params(self, st: Node) -> str:
    # class C[T, *Ts] (subclass node st, its type parameters its first base): why it cannot be a
    # generic class as class C(Generic[T, *Ts]) is, or "" once its type parameters are type
    # variables (TypeVar's or TypeVarTuple's, as typevar_def makes them)
    tp = st.kids[1]
    names = tp.s.split()  # (each a name of its own, see Loader.qren)
    kinds = [x.s.replace("=", "") for x in tp.kids]
    if len(st.kids) > 2:
        return "a generic class (class C[T]) with a base class is not supported"
    if "**" in kinds:
        return f"ParamSpec type parameters (**{short(names[kinds.index('**')])}) are not supported"
    if kinds.count("*") > 1:
        return "a generic class with more than one TypeVarTuple type parameter (*Ts) is not supported"
    for i in range(len(names)):
        self.typevars.append(names[i])
        if kinds[i] == "*":
            self.tvtuples[names[i]] = True
        if tp.kids[i].s.endswith("="):
            self.tvdefaults[names[i]] = True
    return ""

def gen_alias_value(self, name: str) -> Node:
    # the value of type alias name: a type statement's, or that an assignment binds
    st = self.taliases[name]
    return st.kids[0].kids[0] if st.kind == "typealias" else st.kids[1]

def gen_alias_params(self, name: str) -> list[str]:
    # the type parameters of type alias name: a type statement's, or else the TypeVars its value
    # names, in order, which a subscript binds as typing's does (Pair = tuple[T, T]: Pair[int])
    st = self.taliases[name]
    if st.kind == "typealias":
        return st.kids[0].s.split()
    out: list[str] = []
    v = self.alias_whole(name)
    if v.kind != "name" or v.s not in self.typevars:  # (X = T is the TypeVar, which takes none)
        self.alias_tvars(st.kids[1], out, [name])
    return out

def gen_alias_whole(self, name: str) -> Node:
    # the value of assigned type alias name, past the assigned aliases it names whole (Y = X)
    v = self.alias_value(name)
    seen: list[str] = [name]
    while v.kind == "name" and v.s in self.taliases and self.taliases[v.s].kind == "assign" and v.s not in seen:
        seen.append(v.s)
        v = self.alias_value(v.s)
    return v

def gen_alias_problem(self, e: Node) -> str:
    # the TypeError CPython raises evaluating e, (part of) an assigned type alias's value, where
    # a subscript takes the wrong number of type arguments (Box[int, str]; Loader.type_value has
    # checked its form, and deftime what it reads), or "!" and why Pystachy does not support it;
    # or ""
    k = e.kind
    if k == "binop" or k == "tuple" or k == "list" or k == "starred":
        for x in e.kids:
            r = self.alias_problem(x)
            if r != "":
                return r
        return ""
    if k != "index":
        return ""
    r = self.alias_problem(e.kids[1])  # (its arguments are evaluated first)
    if r != "":
        return r
    b = e.kids[0]
    xs = e.kids[1].kids if e.kids[1].kind == "tuple" else [e.kids[1]]
    n = len(xs)
    p = self.imported_ref(b)
    nm = p[p.rfind(".") + 1 :]
    starred = len([x for x in xs if x.kind == "starred"]) > 0
    if p.startswith("typing.") and nm in ["Optional", "ClassVar", "Final", "Required", "NotRequired", "ReadOnly", "TypeGuard", "TypeIs", "Unpack"]:
        if e.kids[1].kind != "tuple" and not starred:
            return ""
        # (CPython's messages add the arguments' reprs)
        if nm == "Optional":
            return "typing.Optional requires a single type"
        return f"{nm} accepts only a single type" if nm in ["Required", "NotRequired", "ReadOnly"] else f"{p} accepts only single type"
    if starred:
        return ""  # (*Ts: as many as it unpacks)
    if b.kind == "name" and b.s in self.taliases:
        return self.alias_args(b.s, n)
    if b.kind == "name" and b.s in self.tparams:
        tvs = self.tparams[b.s]
        lo = len([t for t in tvs if t not in self.tvdefaults and t not in self.tvtuples])
        hi = n if len([t for t in tvs if t in self.tvtuples]) > 0 else len(tvs)
        c = shown(b.s) if "$" in b.s and not b.s.startswith("__main__$") else "__main__." + shown(b.s)
        if n < lo or n > hi:
            return f"Too {'many' if n > hi else 'few'} arguments for <class '{c}'>; actual {n}, expected {'at least ' + str(lo) if n < lo else str(hi)}"
        return ""
    if nm == "Callable" and (p.startswith("typing.") or p.startswith("collections.abc.")):
        return "Callable must be used as Callable[[arg, ...], result]" if n != 2 or (xs[0].kind != "list" and xs[0].kind != "ellipsis") else ""
    if p.startswith("collections.abc."):
        return f"type '{nm}' is not subscriptable" if nm in ["Hashable", "Sized", "Buffer"] else ""  # (the others take any)
    if not p.startswith("typing."):
        return ""  # (list[...], tuple[...]: any arguments, as types.GenericAlias takes them)
    if nm in TYPEARGS:
        lo = int(TYPEARGS[nm][0])
        hi = int(TYPEARGS[nm][-1])
        if n < lo or n > hi:
            return f"Too {'many' if n > hi else 'few'} arguments for {p}; actual {n}, expected {'at least ' + str(lo) if lo != hi else str(hi)}"
        return ""
    if nm == "Union":
        return "Cannot take a Union of no types" if n == 0 else ""
    if nm == "Annotated":
        return "Annotated[...] should be used with at least two arguments (a type and an annotation)" if n < 2 else ""
    if nm == "Tuple" or nm == "Literal":
        return ""
    return f"!{p}[...] is not supported in a type alias's value"

def gen_alias_args(self, name: str, n: int) -> str:
    # (alias_problem) CPython's TypeError for name[...] with n type arguments, name a type alias
    st = self.taliases[name]
    if st.kind == "typealias":
        return "Only generic type aliases are subscriptable" if st.kids[0].s == "" else ""  # (others take any)
    v = self.alias_whole(name)
    if v.kind == "name" and v.s in self.taliases:
        return self.alias_args(v.s, n)  # (X = Y of a type statement Y: that TypeAliasType)
    if v.kind == "name" and v.s in self.typevars:
        return f"'typing.{'TypeVarTuple' if v.s in self.tvtuples else 'TypeVar'}' object is not subscriptable"
    if v.kind == "name":
        return f"type '{short(v.s)}' is not subscriptable"  # (Pos = int)
    tps = self.alias_params(name)
    if len([t for t in tps if t in self.tvtuples]) > 0 and n >= len(tps) - 1:
        return ""  # (*Ts takes the others)
    return self.alias_arity(name, tps, n)

def gen_alias_arity(self, name: str, tps: list[str], n: int) -> str:
    # why type alias name, whose type parameters are tps, cannot take n type arguments, or ""
    if len(tps) == 0:
        return f"type alias '{short(name)}' is not generic: it takes no type arguments"
    if n != len(tps):
        return f"type alias '{short(name)}' takes {len(tps)} type argument{'s' if len(tps) != 1 else ''} ({', '.join([short(x) for x in tps])}), not {n}"
    return ""

def gen_alias_variadic(self, name: str) -> bool:
    # is a type parameter of type alias name a TypeVarTuple or a ParamSpec (a type statement's
    # kinds are Parser.typeparams')
    st = self.taliases[name]
    if st.kind == "typealias":
        return len([x for x in st.kids[0].kids[1:] if x.s.replace("=", "") != ""]) > 0
    return len([x for x in self.alias_params(name) if x in self.tvtuples]) > 0

def gen_alias_tvars(self, a: Node, out: list[str], seen: list[str]) -> None:
    # (alias_params) the TypeVars annotation a names, also through the aliases it names whole
    if a.kind == "name" and a.s in self.typevars and a.s not in out:
        out.append(a.s)
    if a.kind == "name" and a.s in self.taliases and a.s not in seen and self.taliases[a.s].kind == "assign":
        seen.append(a.s)  # (once: what it names again adds no TypeVar)
        self.alias_tvars(self.taliases[a.s].kids[1], out, seen)
    if a.kind == "index" and a.kids[0].kind == "name" and a.kids[0].s in self.taliases:
        self.alias_tvars(a.kids[1], out, seen)  # (its type arguments, not its own parameters)
        return
    for k in a.kids:
        self.alias_tvars(k, out, seen)

def gen_alias_kept(self, name: str) -> bool:
    # does the assignment that binds type alias name stay in the module's code: Pos = int binds
    # a class, which can be called (Pos("3")), as does an alias of such an alias; the other
    # values can only be named by annotations
    st = self.taliases[name]
    v = st.kids[1] if st.kind == "assign" else st
    if v.kind == "name" and v.s in self.taliases:
        return self.alias_kept(v.s)
    return v.kind == "name" and v.s in ["int", "float", "str", "bool"]

def gen_unalias(self, a: Node, seen: list[str]) -> Node:
    # annotation a with each type alias that it names replaced by the alias's value, where a
    # generic alias's type arguments replace its type parameters; what cannot be replaced (a
    # recursive alias, seen: those being replaced; a generic alias without the type arguments
    # it needs) is left for alias_ann's error
    k = a.kind
    if k == "noann":
        return a  # (a generic def's, which types nothing)
    self.unaliased += 1  # (the nodes it has made of the annotation, which aliases of aliases can double)
    if self.unaliased > TYPE_SIZE:
        self.err(f"the type aliases this annotation names expand to more than {TYPE_SIZE} nodes (not supported: simplify them)")
    if k == "name" and a.s in self.taliases and a.s not in seen and (self.taliases[a.s].kind == "assign" or self.taliases[a.s].kids[0].s == ""):
        return self.unalias(clone(self.alias_value(a.s)), seen + [a.s])
    if k == "index" and a.kids[0].kind == "name" and a.kids[0].s in self.taliases and a.kids[0].s not in seen:
        name = a.kids[0].s
        tps = self.alias_params(name)
        xs = a.kids[1].kids if a.kids[1].kind == "tuple" else [a.kids[1]]
        if len(tps) == 0 or len(xs) != len(tps) or self.alias_variadic(name):
            return a
        # (the type arguments replace the type parameters first: in type Pair[Row] = ..., Row is
        # the parameter, not the module's alias Row)
        v = self.subst_ann(clone(self.alias_value(name)), tps, [self.unalias(x, seen) for x in xs])
        return self.unalias(v, seen + [name])
    for i in range(len(a.kids)):
        a.kids[i] = self.unalias(a.kids[i], seen)
    return a

def gen_subst_ann(self, n: Node, tps: list[str], args: list[Node]) -> Node:
    # annotation n (a copy) with type parameters tps replaced by annotations args
    if n.kind == "name" and n.s in tps:
        return clone(args[tps.index(n.s)])
    for i in range(len(n.kids)):
        n.kids[i] = self.subst_ann(n.kids[i], tps, args)
    return n

def gen_alias_ann(self, n: Node) -> str:
    # the type that annotation n, type alias X or X[...], denotes, or "!" and why not
    name = n.s if n.kind == "name" else n.kids[0].s
    tps = self.alias_params(name)
    xs = (n.kids[1].kids if n.kids[1].kind == "tuple" else [n.kids[1]]) if n.kind == "index" else []
    if name in self.resolving:
        return f"!recursive type aliases are not supported: '{short(name)}' refers to itself"
    if n.kind == "index" and self.alias_variadic(name):
        return f"!type alias '{short(name)}' with a TypeVarTuple (*Ts) or ParamSpec (**P) parameter is not supported with type arguments: write its value out"
    if n.kind == "index" and self.alias_arity(name, tps, len(xs)) != "":
        return "!" + self.alias_arity(name, tps, len(xs))
    if n.kind == "name" and len(tps) > 0 and self.taliases[name].kind == "typealias":
        return f"!generic type alias '{short(name)}' needs its type arguments here ({short(name)}[{', '.join([short(x) for x in tps])}])"
    self.resolving.append(name)
    self.unaliased = 0
    t = self.ann(self.unalias(clone(n), []))
    self.resolving.pop()
    if t.startswith("!") and not t.startswith("!type alias") and not t.startswith("!recursive type aliases") and not t.startswith("!generic type alias"):
        return f"!type alias '{short(name)}': {t[1:]}"
    return t

def gen_unalias_all(self, n: Node) -> None:
    # replace the type aliases that the annotations in code n name (unalias): its defs'
    # parameters and returns and its annotated assignments, at any depth
    if n.kind == "def" or n.kind == "annassign":
        self.line = n.line
    if n.kind == "def":
        for p in n.kids[0].kids:
            self.unaliased = 0
            p.kids[0] = self.unalias(p.kids[0], [])
        self.unaliased = 0
        n.kids[1] = self.unalias(n.kids[1], [])
    elif n.kind == "annassign":
        self.unaliased = 0
        n.kids[1] = self.unalias(n.kids[1], [])
    for k in n.kids:
        self.unalias_all(k)

def gen_class_tvars(self, cls: str) -> list[str]:
    # the type variables of generic class cls, or of the one it specializes ([] for another class)
    if cls in self.tparams:
        return self.tparams[cls]
    return self.tparams.get(self.classes[cls].origin, []) if cls in self.classes else []

def gen_ann_problem(self, n: Node, ret: bool) -> str:
    # why typeof(n), for a return annotation (ret), or vtype(n) fails, or "" (one that raises
    # where CPython evaluates it is the loader's error: see Loader.deftime)
    t = self.ann(n)
    if t == "None" and not ret:
        return "None is only supported as a return type; annotate an optional value as T | None"
    return t[1:] if t.startswith("!") else ""

def gen_vtype(self, n: Node) -> str:
    # the annotation of a variable, parameter or field: None alone is only a return type
    why = self.ann_problem(n, False)
    if why != "":
        self.err(why)
    return self.ann(n)

def gen_typing_attr(self, n: Node) -> str:
    # the typing name an attribute denotes (typing.Optional, t.List after import typing as t), or ""
    p = ""
    while n.kind == "attr":
        p = "." + n.s + p
        n = n.kids[0]
    p = self.imported(n.s + p) if n.kind == "name" else ""
    return p[7:] if p.startswith("typing.") else p[16:] if p.startswith("collections.abc.") else ""

def gen_typing_ref(self, n: Node) -> str:
    # the typing (or collections.abc) name that a name or attribute n refers to, or "" (no error)
    if n.kind == "attr":
        return self.typing_attr(n)
    if n.kind != "name":
        return ""
    p = self.imported(n.s)
    if p.startswith("typing.") or p.startswith("collections.abc."):
        return p[p.rfind(".") + 1 :]
    return short(n.s) if short(n.s) in TYPING and "__future__.annotations" in self.imports.values() else ""

def gen_typing_forms(self, m: Mod, body: list[Node], cls: bool) -> list[Node]:
    # what typing decides before any code runs, in the statements of body (a class body if cls)
    # and in those they hold: a def decorated with @overload is a stub that the def after it
    # replaces, so it is dropped (unless no def of its name follows in its block, past other
    # defs, or a default is more than a constant); x: Final = v is x = v outside class bodies,
    # and a field typed by the constant v in one, x: Final[T] is x: T, and x: Final alone does
    # nothing
    out: list[Node] = []
    defs: dict[str, bool] = {}
    for i in range(len(body)):
        st = body[i]
        stub = self.stub(m, st)
        self.line = st.line
        if stub and st.s in defs:
            self.err(f"an @overload stub after the definition of '{short(st.s)}' is not supported (it would replace it)")
        if stub:
            # (one that nothing replaces is what a call finds, which raises NotImplementedError;
            # other defs between them run nothing that could call it)
            j = i + 1
            while j < len(body) and body[j].kind == "def" and (body[j].s != st.s or self.stub(m, body[j])):
                j += 1
            later = False  # (a def of its name past other statements, which could call the stub first)
            for k in body[j:]:
                later = later or (k.kind == "def" and k.s == st.s)
            if (j == len(body) or body[j].kind != "def") and m.name != "" and not later:
                out.append(st)  # (an imported module's, also a method: an error where it is called, see declare_fn)
                continue
            if j == len(body) or body[j].kind != "def":
                self.err(STUB.replace("NAME", short(st.s)))
            for p in st.kids[0].kids:
                if p.kids[1].kind != "ellipsis" and not is_const(p.kids[1]):
                    self.err("a default of an @overload stub that is not a constant (or ...) is not supported (CPython evaluates it where the def runs)")
            continue
        if st.kind == "def":
            defs[st.s] = True
        a = st.kids[1] if st.kind == "annassign" else st
        if a.kind == "index" and self.typing_ref(a.kids[0]) == "Final":
            st.kids[1] = a.kids[1]
        elif a is not st and len(st.kids) == 3 and not cls and self.typing_ref(a) == "Final":
            st.kind = "assign"
            st.kids = [st.kids[0], st.kids[2]]
        elif a is not st and len(st.kids) == 3 and self.typing_ref(a) == "Final":
            # (a field, typed by its constant)
            v = st.kids[2]
            if v.kind == "int" or v.kind == "float" or v.kind == "str" or v.kind == "bytes":
                st.kids[1] = mk("name", v.kind, v.line, [])
            elif v.kind == "True" or v.kind == "False":
                st.kids[1] = mk("name", "bool", v.line, [])
            else:
                self.err("a field annotated Final without a type needs a constant value (int, float, str or bool): annotate it Final[T]")
        elif a is not st and self.typing_ref(a) == "Final":
            st.kind = "pass"  # (x: Final alone binds nothing)
            st.kids = []
        for k in st.kids:
            if k.kind == "block":
                k.kids = self.typing_forms(m, k.kids, st.kind == "class")
            elif k.kind == "class":
                k.kids[0].kids = self.typing_forms(m, k.kids[0].kids, True)  # (a subclass's)
            elif k.kind == "except":
                k.kids[1].kids = self.typing_forms(m, k.kids[1].kids, False)
        out.append(st)
    return out if len(out) < len(body) else body

def gen_stub(self, m: Mod, st: Node) -> bool:
    # is st a def decorated with typing.overload
    r = False
    for d in st.kids[3:] if st.kind == "def" else []:
        root = d.s[: d.s.find(".")] if "." in d.s else d.s
        r = r or (self.imported(m.q + root) or self.imported(root)) + d.s[len(root) :] == "typing.overload"
    return r

def gen_typing_name(self, s: str) -> str:
    # List/Dict/Tuple/Optional/TextIO must come from typing, unless annotations are never
    # evaluated (from __future__ import annotations): the typing name s denotes, "", or "!" and
    # the error
    if self.imported(s).startswith("typing."):
        return self.imported(s)[7:]
    if self.imported(s).startswith("collections.abc."):
        return self.imported(s)[16:]
    if short(s) in TYPING and "__future__.annotations" in self.imports.values():
        return short(s)  # (also a module's name that only an if TYPE_CHECKING: block imports)
    return f"!name '{s}' is not defined (import it from typing)" if s in TYPING else ""

def gen_opt(self, t: str, x: Node) -> str:
    # T | None, Optional[T] (T annotated as x): a class type includes None already; str, int,
    # float, bool, list, dict and tuple become opt[T] (or "!" and why not)
    if t.startswith("!"):
        return t
    if t == "exc":
        return self.ctype("opt", [t])  # (an exception or None: __exit__'s exception)
    r = self.optional(t)
    return r if r != "" else f"!None/Optional is only supported for {OPTTYPES}, not {typestr(t)}"

def gen_optional(self, t: str) -> str:
    # the type of a value that is a t or None, "" if there is none
    if t in self.classes or is_opt(t):
        return t
    if is_union(t):
        # (a union that holds a class's objects may be None, as the class's objects may)
        return t if len([m for m in umembers(t) if m in self.classes]) > 0 else self.ctype("opt", [t])
    if (t == "str" or t == "bytes" or t == "exc" or t == "exctype" or self.isnum(t) or is_list(t) or is_dict(t) or is_set(t) or is_tuple(t) or is_vtuple(t) or is_callable(t) or is_gen(t)) and "?" not in t:
        return self.ctype("opt", [t])
    return ""

def gen_ann_none(self, n: Node, seen: list[str]) -> bool:
    # does annotation n make None one of its members (C | None, Optional[C], Union[C, None]; in
    # a string or a type alias's value too), which the type of a class C, including None
    # already, does not tell (see optional). seen: the aliases being looked through
    k = n.kind
    if k == "str":
        return self.ann_none(self.parse_expr(n.s), seen)
    if k == "binop" and n.s == "|":
        return self.ann_none(n.kids[0], seen) or self.ann_none(n.kids[1], seen)
    b = n.kids[0] if k == "index" else n
    if b.kind == "name" and b.s in self.taliases and b.s not in seen:
        return self.ann_none(self.alias_value(b.s), seen + [b.s])
    if k == "index" and (b.kind == "name" or b.kind == "attr") and (self.ann_base(b) == "optional" or self.ann_base(b) == "union"):
        return self.ann_base(b) == "optional" or len([x for x in (n.kids[1].kids if n.kids[1].kind == "tuple" else [n.kids[1]]) if self.ann_none(x, seen)]) > 0
    return k == "None"

def gen_join(self, a: str, b: str) -> str:
    # the type of a value that is an a or a b, where None and optional types meet (T and None
    # make T | None), or ""
    if a == b or self.widens(b, a):
        return a
    if self.widens(a, b):
        return b
    if a in self.classes and b in self.classes:
        c = self.classes[a].base
        while c in self.classes:
            if self.derives(b, c):
                return c
            c = self.classes[c].base
    if a == "None" or b == "None":
        return self.optional(b if a == "None" else a)
    if is_opt(a) or is_opt(b):
        j = self.join(unopt(a), unopt(b))
        return self.optional(j) if j != "" else ""
    if is_tuple(a) and is_tuple(b) and len(targs(a)) == len(targs(b)):
        js = [self.join(targs(a)[i], targs(b)[i]) for i in range(len(targs(a)))]  # (item by item)
        return self.ctype("tuple", js) if "" not in js else ""
    return ""

def gen_wider(self, a: str, b: str) -> str:
    # the type of values of types a and b as they are, where they differ only in what may be
    # None (list[str] and list[str | None]: list[str | None]), for comparisons and for new
    # containers made of both; "" if there is none (an int is no int | None as it is: that is a box)
    if a == b:
        return a
    if a in self.classes and b in self.classes:
        return self.join(a, b)
    if self.isnum(a) or self.isnum(b):
        return ""
    if "?" in a or "?" in b:
        return ""
    if a == "None" or b == "None":
        return self.optional(b if a == "None" else a)
    if is_opt(a) or is_opt(b):
        w = self.wider(unopt(a), unopt(b))
        return self.optional(w) if w != "" else ""
    if is_list(a) and is_list(b):
        w = self.wider(elem(a), elem(b))
        return self.ctype("list", [w]) if w != "" else ""
    if is_dict(a) and is_dict(b):
        k = self.wider(targs(a)[0], targs(b)[0])  # (tuple keys whose items may be None)
        w = self.wider(targs(a)[1], targs(b)[1])
        return self.ctype("dict", [k, w]) if k != "" and w != "" else ""
    if is_set(a) and is_set(b) and is_fset(a) == is_fset(b):
        w = self.wider(selem(a), selem(b))  # (tuple elements whose items may be None)
        return self.ctype("frozenset" if is_fset(a) else "set", [w]) if w != "" else ""
    if not is_tuple(a) or not is_tuple(b) or len(targs(a)) != len(targs(b)):
        return ""
    bs = targs(b)
    ws: list[str] = []
    for x in targs(a):
        w = self.wider(x, bs[len(ws)])
        if w == "":
            return ""
        ws.append(w)
    return self.ctype("tuple", ws)

def gen_widens_items(self, a: str, b: str) -> bool:
    # can the items of list type a be copied as they are into a list of type b (list.extend(),
    # +=, a slice assignment): wider(a, b) is b, and each item is a value of b's item type, so a
    # list[str] goes into a list[str | None], but a list[list[str]] not into a list[list[str |
    # None]], whose items, shared with it, None could then be appended to
    return self.wider(a, b) == b and self.widens(elem(a), elem(b))

def gen_boxwider(self, a: str, b: str) -> str:
    # wider(a, b) for tuple types whose items differ also where one is an int, float or bool and
    # the other an int | None, float | None or bool | None: the tuple of the latter, which the
    # tuple that is not optional itself can become (coerce boxes its items); "" if there is none
    if is_opt(a) and is_opt(b):
        return ""
    if is_opt(a) or is_opt(b):
        w = self.boxwider(unopt(a), unopt(b))
        return self.optional(w) if w != "" and unopt(a if is_opt(a) else b) == w else ""
    if not is_tuple(a) or not is_tuple(b) or len(targs(a)) != len(targs(b)):
        return ""
    bs = targs(b)
    ws: list[str] = []
    for x in targs(a):
        y = bs[len(ws)]
        w = self.wider(x, y)
        if w == "" and (is_sopt(y) and x == unopt(y) or y == "None" and self.isnum(x)):
            w = self.optional(x)
        elif w == "" and (is_sopt(x) and y == unopt(x) or x == "None" and self.isnum(y)):
            w = self.optional(y)
        elif w == "":
            w = self.boxwider(x, y)
        if w == "":
            return ""
        ws.append(w)
    return self.ctype("tuple", ws)

def gen_boxto(self, v: Val, t: str) -> Val:
    # v as a value of tuple type t = boxwider(v.t, ...), boxing its items where it needs to
    if v.t == t:
        return v
    if is_opt(t) and not is_opt(v.t):
        return Val(self.coerce(v, unopt(t)).v, t)
    return self.coerce(v, t)

def gen_widens(self, a: str, b: str) -> bool:
    # is a value of type a, as it is, a value of type b: None or T as T | None (or as an object
    # type), an object of an exception class as one of a base class (whose layout its own
    # extends), and a tuple item by item (tuples cannot change, so their items can widen)
    if a == b:
        return True
    if is_opt(b):
        return a == "None" or (not is_sopt(b) and self.widens(unopt(a), unopt(b)))  # (an int | None is a box)
    if is_gen(a) and is_gen(b) and gsend(b) == "None" and gelem(a) == gelem(b):
        return True  # (a generator that takes S from send() as one that next() alone resumes)
    if b in self.classes:
        return a == "None" or (a in self.classes and self.derives(a, b))
    if is_union(b):
        # (its box: the tags are the program's, the same in every union)
        if a == "None":
            return self.optional(b) == b
        return is_union(a) and len([m for m in umembers(a) if m not in umembers(b)]) == 0
    if is_vtuple(a) and is_vtuple(b):
        # Tuples are immutable: widening str to str | None changes no slot's
        # representation. Numeric optional elements require actual boxes instead.
        return self.widens(targs(a)[0], targs(b)[0])
    if not is_tuple(a) or not is_tuple(b) or len(targs(a)) != len(targs(b)):
        return False
    bs = targs(b)
    i = 0
    for x in targs(a):
        if not self.widens(x, bs[i]):
            return False
        i += 1
    return True

def gen_declare_fn(self, d: Node, cls: str, inherited: bool = False) -> FnInfo:
    # a function or method. A module-level function with a parameter that has no annotation
    # is a template: a call compiles it, once per list of argument types, for those types
    # (see instance), and what cannot be compiled in it is an error only then
    self.line = d.line
    # a generic class's methods: an annotation that mentions its type variables is left out
    # where they are not bound, in the class itself (whose objects are its specializations'),
    # and in its __init__'s parameters, which each call's arguments type (they bind them, see
    # bind); the def, which its specializations share, keeps it
    tvs = self.class_tvars(cls)
    held: list[Node] = []  # (the nodes whose annotations are left out, and those annotations)
    anns: list[Node] = []
    for x in d.kids[0].kids + [d] if len(tvs) > 0 and (cls in self.tparams or d.s == "__init__") else []:
        a = x.kids[1] if x.kind == "def" else x.kids[0]
        if (x.kind != "def" or cls in self.tparams) and self.typevar_in([a], []) != "" and self.typevar_in([a], tvs) == "":
            held.append(x)
            anns.append(a)
            if x.kind == "def":
                x.kids[1] = mk("noann", "", d.line, [])
            else:
                x.kids[0] = mk("noann", "", d.line, [])
    f = FnInfo(d.s, f"@f.{d.s}" if cls == "" else f"@m.{cls}.{d.s}", d, cls)
    body = d.kids[2].kids
    if self.rtmode and cls == "" and len(body) == 1 and body[0].kind == "expr" and body[0].kids[0].kind == "ellipsis":
        # def name(...) -> T: ... is runtime.c's function of that name
        if not d.s.startswith("pys_"):
            self.err(f"'{d.s}' declares a C function: in runtime.py that is one of runtime.c's, named pys_*")
        f.ll = "@" + d.s
        f.extern = True
    elif self.rtmode and cls == "" and d.s.startswith("pys_"):
        f.ll = "@" + d.s
        f.export = True
        self.rtdefs[d.s] = f
    for x in d.kids[3:] if cls == "" and not self.rtmode else []:
        if self.imported(x.s) == "ffi.extern":
            ls = self.extern_args(x, len(d.kids) != 4)
            if len(body) != 1 or body[0].kind != "expr" or body[0].kids[0].kind != "ellipsis":
                self.err(f"{short(d.s)}() is a C function (@extern): its body must be ...")
            f.extern = True
            f.lib = ls[0]
            f.csym = "@" + (ls[1] if ls[1] != "" else short(d.s))  # (the twin's symbol or f.__name__)
        elif self.imported(x.s) == "ffi.export":
            if len(x.kids) > 0 or len(d.kids) != 4:
                self.err("@export takes no arguments, and is a function's only decorator")
            f.pyexport = True
    ps = d.kids[0].kids
    deco = ""
    stub = False  # (an imported module's that no def follows: see typing_forms)
    for x in d.kids[3:]:
        if x.s != "async" and deco == "":
            deco = x.s
        stub = stub or self.imported(x.s) == "typing.overload"
    if cls != "" and len(d.kids) == 4 and len(d.kids[3].kids) == 0 and (deco == "staticmethod" or deco == "classmethod"):
        f.deco = deco  # (a method that takes no self, or its class as cls)
    f.prop = cls != "" and len(d.kids) == 4 and len(d.kids[3].kids) == 0 and deco == "property"
    if f.prop:
        for st in self.classes[cls].node.kids[0].kids:
            if st is d:
                break
            if st.s == "property" or ((st.kind == "assign" or st.kind == "annassign") and st.kids[0].kind == "name" and st.kids[0].s == "property"):
                self.err("unsupported decorator @property: the name is shadowed in the class body")
    acc = deco[deco.rfind(".") + 1 :] if cls != "" and len(d.kids) == 4 and len(d.kids[3].kids) == 0 and "." in deco else ""
    if acc == "setter" or acc == "deleter":
        # @x.setter, @Base.x.setter: the property's other method (the class checks the name, see accessor)
        f.acc = acc
        f.accof = deco[: deco.rfind(".")]
        f.name = d.s + "." + acc
        f.ll = f"@m.{cls}.{f.name}"
    deco = short(deco)
    if deco != "" and f.deco == "" and not f.prop and f.acc == "" and not self.lib and not f.extern and not f.pyexport:
        # (CPython applies a decorator when the def runs, called or not: see decorators())
        if deco in TYPING and self.imported(deco) == "" and not self.bound(deco):
            self.err(f"name '{deco}' is not defined (import it from typing)")
        self.err(f"unsupported decorator @{deco}")
    if cls != "" and len(ps) == 0 and f.deco != "staticmethod":
        self.err(f"method '{d.s}' of class '{cls}' must take {'cls' if f.deco != '' else 'self'} as its first parameter")
    tv = self.typevar_in([p.kids[0] for p in ps] + [d.kids[1]], tvs)
    if tv != "" and (cls == "" or template_ok(d.s)):
        # def f(x: T) with T = TypeVar("T"): what mentions a TypeVar is left unannotated, as in
        # def f[T](x: T) (a template); also *args: *Ts
        for p in ps:
            if self.typevar_in([p.kids[0]], tvs) != "":
                p.kids[0] = mk("noann", "", d.line, [])
        if self.typevar_in([d.kids[1]], tvs) != "":
            d.kids[1] = mk("noann", "", d.line, [])
    for i in range(len(ps)):
        # x: object, as in __eq__(self, other: object): a template's parameter, which each call
        # types (any argument: isinstance() narrows it), where a template may be
        if ps[i].kind == "param" and ps[i].kids[0].kind == "name" and ps[i].kids[0].s == "object" and not (cls != "" and i == 0 and f.deco != "staticmethod") and (cls == "" or template_ok(d.s)):
            ps[i].kids[0] = mk("noann", "", d.line, [])
    if (cls == "" or template_ok(d.s)) and not f.prop and f.acc == "" and not f.extern and not f.export and not f.pyexport:
        # typing.Any, also in list[Any] or Mapping[str, Any]: what it annotates is left to each
        # call, as a TypeVar's is. A parameter takes its argument's type (*args and **kwargs
        # those of each call's), the return what the function returns; no value is boxed, so
        # storage that a value of any type reaches (x: Any = v, a field) is still an error
        for i in range(len(ps)):
            if not (cls != "" and i == 0 and f.deco != "staticmethod") and self.any_in([ps[i].kids[0]]):
                ps[i].kids[0] = mk("noann", "", d.line, [])
                f.anys.append(ps[i].s)
        if self.any_in([d.kids[1]]):
            d.kids[1] = mk("noann", "", d.line, [])
            f.anys.append("")
    tvbad = f"method '{d.s}' of class '{short(cls)}' mentions TypeVar '{short(tv)}', which is not supported: {d.s}() is not a template (another method whose parameters mention a TypeVar is, compiled for each call's argument types)"
    if tv != "" and cls != "" and not template_ok(d.s) and not self.lib:
        self.err(tvbad)
    init = d.s == "__init__" and self.tmpl_of(cls) != ""  # (a class template's: see specialize)
    receiver = cls in self.classes and self.classes[cls].tag != 0 and f.deco == ""
    if receiver:
        # A base's inherited body must see the concrete receiver: it can call a method
        # provided by a derived class, while f.cls still anchors lexical super().
        f.generic = True
    for i in range(len(ps)):
        # a method's are too, as M2 makes them (but its self or cls; see template_ok), and a
        # class template's __init__; an annotation that names a class template types nothing
        own = cls != "" and i == 0 and f.deco != "staticmethod"
        if (cls == "" or ((template_ok(d.s) or init) and not own)) and ((ps[i].kind == "param" and (ps[i].kids[0].kind == "noann" or self.tmpl_ann(ps[i].kids[0]))) or ps[i].kind == "starparam" or ps[i].kind == "dstarparam"):
            f.generic = True
    if (cls == "" or template_ok(d.s)) and d.kids[1].kind != "noann" and self.tmpl_ann(d.kids[1]) and not (cls in self.classes and self.classes[cls].origin != ""):
        f.generic = True  # (-> Box: what it returns is one of the class's specializations)
    if cls in self.classes and self.classes[cls].origin != "" and (template_ok(d.s) or init):
        f.generic = True  # (a specialization's methods: compiled where they are called, see specialize)
    gbad = self.gen_declare(f, d) if has_kind(d.kids[2], "yield") and not self.rtmode else ""
    # an __iter__ annotated -> Iterator[T] (or Iterable[T]) that returns something other than
    # iter(x), its own object or another iterator object: its return is inferred, as an
    # unannotated one's is (an iterator class's __next__ gives the items)
    selfiter = cls != "" and d.s == "__iter__" and d.kids[1].kind != "noann" and self.iter_item(d.kids[1]) is not None and other_return(d.kids[2]) and not f.gen
    protocol = cls != "" and (d.s == "__iter__" or d.s == "__next__") and d.kids[1].kind == "noann" and d not in held
    if not f.gen and ((d.kids[1].kind == "noann" and (cls == "" or template_ok(d.s))) or selfiter or protocol) and not f.extern and not f.export and not f.pyexport and has_value_return(d.kids[2]):
        # The declared parameter types still coerce every call. Reuse return
        # inference even when all parameter types are already concrete.
        # Initializers and other implicit special methods keep their contracts.
        f.void_default = not f.generic
        f.generic = True
    marks = d.kids[0].s.split(",")
    bad = ""
    f.npos = -1
    for i in range(len(ps)):
        p = ps[i]
        if i == int(marks[1]):
            f.npos = len(f.params)
        if i == int(marks[0]):
            f.posonly = len(f.params)
        if i == 0 and f.deco == "classmethod" and p.kind == "param":
            continue  # cls: the class, which is not passed (see rename)
        if (p.kind == "starparam" or p.kind == "dstarparam") and f.generic:
            # *args: each call passes the extra positional arguments as a tuple of their types;
            # **kwargs: its extra keyword arguments as a record of their names and types
            # (kw[...]), which the instance for it is compiled with. An imported module's
            # annotation that fails is an error where a call needs the function; one that names
            # a class template types nothing, as for any other parameter (see tmpl_ann)
            typed = p.kids[0].kind != "noann" and not self.tmpl_ann(p.kids[0])
            tup = self.unpack_ann(p.kids[0]) if typed and p.kids[0].kind == "starred" else ""  # (*args: *Ts: args is that tuple)
            why = (tup[1:] if tup.startswith("!") else self.ann_problem(p.kids[0], False) if tup == "" else "") if self.lib and typed else ""
            if why != "":
                bad = f"{d.s}() is not supported: parameter '{'*' if p.kind == 'starparam' else '**'}{p.s}': {why}"
            if tup.startswith("!") and not self.lib:
                self.err(tup[1:])
            elem = self.vtype(p.kids[0]) if typed and why == "" and tup == "" else ""
            if p.kind == "starparam":
                f.vararg = len(f.params)
                f.varelem = elem
                f.vartup = tup if why == "" else ""
            else:
                f.kwarg = len(f.params)
                f.kwelem = elem
            f.params.append(p.s)
            f.defaults.append(mk("noann", "", p.line, []))
            f.dglob.append("")
            f.dtypes.append("")
            f.ptypes.append("")
            continue
        if p.kind != "param":
            bad = "**kwargs is not supported" if p.kind == "dstarparam" else "*args, **kwargs are not supported"
            continue
        f.params.append(p.s)
        f.defaults.append(p.kids[1])
        f.dglob.append("")
        f.dtypes.append("")
        if i == 0 and takes_self(f):
            f.ptypes.append("" if receiver else cls)
        elif p.kids[0].kind == "noann":
            if not f.generic and p not in held:
                # A generic class's TypeVar annotation is restored on its specializations.
                self.err(f"parameter '{p.s}' of '{d.s}' needs a type annotation")
            f.ptypes.append("")
        elif f.generic and self.tmpl_ann(p.kids[0]) and not (cls in self.classes and self.classes[cls].origin != "" and not init and not template_ok(d.s)):
            f.ptypes.append("")  # (it names a class template: any of its specializations, see tmpl_ann)
            if self.callable_pat(p.kids[0]) != "":
                f.pats[len(f.params) - 1] = p.kids[0]
        elif self.lib and self.ann_problem(p.kids[0], False) != "":
            bad = f"{cls + '.' if cls != '' else ''}{d.s}() is not supported: parameter '{p.s}': {self.ann_problem(p.kids[0], False)}"
            f.ptypes.append("")  # (any type: the def statement evaluates its default, see hoist)
        else:
            f.ptypes.append(self.vtype(p.kids[0]))
    if int(marks[0]) == len(ps) and len(ps) > 0:
        f.posonly = len(f.params)  # def f(a, b, /)
    if (f.export or f.extern) and f.generic:
        self.err(f"runtime function {d.s}() needs an annotation on every parameter, and no *args" if self.rtmode else f"C function {short(d.s)}() (@extern) needs an annotation on every parameter, and no *args")
    for x in f.defaults if self.rtmode else []:
        if not is_const(x):
            # a computed default is stored by module code, which runtime mode never runs
            self.line = x.line
            self.err(f"in runtime.py, a parameter's default value must be a literal (in {d.s}())")
    if f.npos < 0:
        f.npos = len(f.params) if f.kwarg < 0 else f.kwarg
    if f.vararg >= 0:
        f.npos = f.vararg
    if len(d.kids) > 3 and f.deco == "" and not f.prop and f.acc == "" and not f.extern and not f.pyexport:
        bad = f"unsupported decorator @{deco}" if deco != "" else "async functions are not supported"
        bad = STUB.replace("NAME", short(d.s)) if stub else bad
    if f.deco != "" and d.s.startswith("__") and d.s.endswith("__"):
        bad = f"@{f.deco} on the special method {d.s} is not supported"
    if f.prop:
        if len(ps) != 1 or ps[0].kind != "param":
            bad = f"property {d.s} must take only self"
        elif d.s.startswith("__") and d.s.endswith("__"):
            bad = f"@property on the special method {d.s} is not supported"
        elif d.kids[1].kind == "noann" and d not in held:
            bad = f"property {d.s} needs a return annotation"
    if f.acc != "" and (len(ps) != (2 if f.acc == "setter" else 1) or len([p for p in ps if p.kind != "param"]) > 0 or f.npos < len(ps)):
        bad = f"property {f.acc} {d.s} must take only self" + (" and the value, by position" if f.acc == "setter" else "")
    if not inherited and f.deco == "classmethod" and bad == "" and ps[0].kind == "param":
        # its cls parameter names the class in its body: cls(...) makes one, cls.x reads a
        # class attribute, cls.m(...) calls a static or class method
        asg: dict[str, bool] = {}
        local_names(d.kids[2].kids, asg)
        if ps[0].s in asg:
            bad = f"class method {d.s}() assigns its parameter '{ps[0].s}', which names the class: not supported"
        f.clsuse = mentions(d.kids[2], [ps[0].s])
        if f.clsuse:
            f.orig = clone(d)
        rename(d.kids[2], ps[0].s, cls)
    if bad == "" and gbad != "":
        bad = gbad  # (a generator function whose yield or annotation Pystachy does not support)
    elif bad == "" and self.rtmode and has_kind(d.kids[2], "yield"):
        bad = "generator functions are not supported in runtime.py"
    tret = d.kids[1].kind != "noann" and f.generic and self.tmpl_ann(d.kids[1]) and not (cls in self.classes and self.classes[cls].origin != "" and not template_ok(d.s)) and not f.gen
    if bad == "" and self.lib and d.kids[1].kind != "noann" and not tret and not f.gen:
        it = self.iter_item(d.kids[1]) if cls != "" and (d.s == "__iter__" or d.s == "__reversed__") else None  # (see iter_ann)
        why = self.ann_problem(d.kids[1], True) if it is None else self.ann_problem(it, False)
        if why != "":
            bad = f"{cls + '.' if cls != '' else ''}{d.s}() is not supported: return annotation: {why}"
    if tv != "" and cls != "" and not template_ok(d.s):
        bad = tvbad  # (an imported module's: an error only where it is used)
    if bad != "" and not f.generic and not self.lib:
        self.err(bad)
    f.bad = bad
    if bad != "" and self.lib:
        f.ret = "None"
    elif f.gen:
        pass  # (gen_declare: gen[Y] from its annotation, or decided by its first yield)
    elif selfiter:
        f.ret = ""  # (its iterator object's class, decided by its first return)
    elif d.kids[1].kind != "noann" and cls != "" and (d.s == "__iter__" or d.s == "__reversed__") and self.iter_ann(d.kids[1]) != "":
        f.ret = self.iter_ann(d.kids[1])
        f.iters = True
    elif tret:
        f.ret = ""  # (-> Box: decided by its first return, as an unannotated one is)
    elif d.kids[1].kind != "noann":
        f.ret = self.typeof(d.kids[1])
    elif cls != "" and d.s == "__len__" and has_value_return(d.kids[2]):
        # bool is also a legal length; infer it so an explicit obj.__len__()
        # keeps returning bool while len(obj) converts it to int.
        f.generic = True
        f.ret = ""
    elif cls != "" and d.s in ["__str__", "__repr__", "__bool__"] and has_value_return(d.kids[2]):
        # These implicit operations have a fixed result contract even without an
        # annotation; checking the body still rejects a wrong value.
        f.ret = SPECIAL[d.s][SPECIAL[d.s].find(":") + 1 :]
    elif f.generic and init:
        f.ret = "None"  # (a class template's __init__: what CPython lets it return)
    elif f.generic:
        f.ret = ""
    for i in range(len(held)):
        if held[i].kind == "def":
            held[i].kids[1] = anns[i]
        else:
            held[i].kids[0] = anns[i]
    return f

def gen_iter_ann(self, n: Node) -> str:
    # an __iter__'s (or __reversed__'s) return annotation Iterator[T] or Iterable[T] (typing's or collections.abc's):
    # list[T], the list that the iterator it returns steps through (see iter_ret); else ""
    t = self.iter_item(n)
    return self.ctype("list", [self.vtype(t)]) if t is not None else ""

def gen_iter_item(self, n: Node) -> Node:
    # T, of an __iter__'s return annotation Iterator[T] or Iterable[T]; else None
    if n.kind == "str":
        n = self.parse_expr(n.s)
    if n.kind != "index" or (self.typing_ref(n.kids[0]) != "Iterator" and self.typing_ref(n.kids[0]) != "Iterable"):
        return None
    return n.kids[1]

def gen_exc_attr(self, ci: ClassInfo, name: str) -> None:
    # a field name of class ci that is an attribute of its builtin exception class (EXCATTRS): an
    # error (for an imported module's class, where the program uses it)
    for b in EXCATTRS:
        if ci.exc != "" and name in EXCATTRS[b].split() and exc_derives(ci.exc, b):
            use = "its exit status" if b == "SystemExit" else "its str() and repr()" if b == "BaseException" else "its str()"
            why = f"a field '{name}' of exception class {short(ci.name)} is not supported: it would be {b}'s own attribute {name}, which decides {use}"
            if ci.mod == "":
                self.err(why)
            ci.bad = ci.bad if ci.bad != "" else f"class {shown(ci.name)} is not supported: {why}"
    for b in EXCINIT:
        if ci.exc != "" and name in EXCINIT[b].split() and exc_derives(ci.exc, b) and not self.init_after(ci, name) and not self.shadowed(ci, name):
            why = f"a field '{name}' of exception class {short(ci.name)} is not supported here: {b}.__init__() sets its attribute {name} as it runs, after what assigned the field before it (assign self.{name} in __init__, after super().__init__(...))"
            if ci.mod == "":
                self.err(why)
            ci.bad = ci.bad if ci.bad != "" else f"class {shown(ci.name)} is not supported: {why}"

def gen_bad_class(self, ci: ClassInfo, why: str) -> None:
    # why class ci cannot be compiled: an error, or for an imported module's class, one only where
    # the program uses it. Its objects cannot be made, so dispatch on a base's class tag leaves it
    # out, and the classes deriving from it too (see declare_fields)
    if ci.mod == "":
        self.err(why)
    ci.bad = ci.bad if ci.bad != "" else f"class {shown(ci.name)} is not supported: {why}"
    ci.excluded = True
    ci.tag = 0

def gen_shadowed(self, ci: ClassInfo, name: str) -> bool:
    # does class ci or a base of the program give attribute name a default in its class body:
    # then CPython's instances keep it in their __dict__, apart from the slot of the builtin
    # base that its __init__ sets
    c = ci.name
    while c in self.classes:
        for st in self.classes[c].node.kids[0].kids:
            if st.kind == "annassign" and len(st.kids) == 3 and st.kids[0].kind == "name" and st.kids[0].s == name:
                return True
        c = self.classes[c].base
    return False

def gen_init_after(self, ci: ClassInfo, name: str) -> bool:
    # is field name of class ci's objects assigned after its builtin base's __init__ runs, if it
    # runs: the __init__ that runs for them (of ci or the nearest base) does not call its base's,
    # or calls it in a statement of its own after which it assigns self.name (or the base's
    # __init__ does so, for its own objects), and calls it nowhere else
    if "__init__" not in ci.methods:
        return False  # (the builtin __init__ runs as the object is made)
    f = ci.methods["__init__"]
    d = self.classes[f.cls]
    me = f.params[0] if len(f.params) > 0 else ""
    body = f.node.kids[2].kids
    last = -1
    for i in range(len(body)):
        st = body[i]
        c = st.kids[0] if st.kind == "expr" else st
        a = c.kids[0] if c.kind == "call" else c
        if a.kind == "attr" and a.s == "__init__" and ((a.kids[0].kind == "call" and a.kids[0].kids[0].kind == "name" and a.kids[0].kids[0].s == "super")
                                                     or (a.kids[0].kind == "name" and len(c.kids) > 1 and c.kids[1].kind == "name" and c.kids[1].s == me)):
            last = i
        elif calls_init(st):
            return False  # (it may call the base's __init__ in another way)
    if last < 0:
        return True
    if d.base in self.classes and self.init_after(self.classes[d.base], name):
        return True
    for st in body[last + 1 :]:
        if (st.kind == "assign" or st.kind == "annassign") and st.kids[0].kind == "attr" and st.kids[0].s == name and st.kids[0].kids[0].kind == "name" and st.kids[0].kids[0].s == me:
            return True
    return False

def gen_add_field(self, ci: ClassInfo, name: str, t: str) -> None:
    if name in ci.methods and ci.methods[name].prop:
        self.err(f"field '{name}' of '{short(ci.name)}' conflicts with property '{name}'")
    if name not in ci.ftypes:
        self.exc_attr(ci, name)
    if name in ci.ftypes:
        if ci.ftypes[name] != t:
            self.err(f"field '{name}' redeclared with a different type")
        return
    ci.fpos[name] = len(ci.fields)
    ci.fields.append(name)
    ci.ftypes[name] = t

def gen_declare_fields(self, ci: ClassInfo) -> None:
    noann = mk("noann", "", ci.node.line, [])
    last = ""
    if ci.base in self.classes and self.classes[ci.base].excluded:
        why = self.classes[ci.base].bad
        self.bad_class(ci, f"its base {shown(ci.base)} is not supported: {why[why.find(': ') + 2 :]}")
    # Slot names constrain layout; the declaration remains a class attribute. A
    # subclass without its own __slots__, or with an unslotted base, has a dict.
    if ci.base in self.classes:
        ci.slots = list(self.classes[ci.base].slots)
        if "__slots__" in self.classes[ci.base].fdefault:
            ci.ftypes["__slots__"] = self.classes[ci.base].ftypes["__slots__"]
            ci.fdefault["__slots__"] = self.classes[ci.base].fdefault["__slots__"]
    slots_declared = False
    for st in ci.node.kids[0].kids:
        if st.kind not in ["assign", "annassign"] or st.kids[0].kind != "name" or st.kids[0].s != "__slots__":
            continue
        self.line = st.line
        if slots_declared:
            why = "multiple __slots__ declarations are not supported; use one literal declaration"
            if ci.mod == "":
                self.err(why)
            ci.bad = ci.bad if ci.bad != "" else f"class {shown(ci.name)} is not supported: {why}"
        slots_declared = True
        slot_node = st.kids[-1]
        names = [slot_node] if slot_node.kind == "str" else slot_node.kids if slot_node.kind in ["tuple", "list"] else []
        own_slots: list[str] = []
        why = ""
        if slot_node.kind not in ["str", "tuple", "list"] or (st.kind == "annassign" and len(st.kids) != 3):
            why = "__slots__ needs a literal string, tuple or list of strings"
        for n in names:
            if n.kind != "str" or n.s == "" or not (n.s[0].isalpha() or n.s[0] == "_") or not n.s.replace("_", "a").isalnum():
                why = "__slots__ needs literal attribute names"
            elif n.s in ["__dict__", "__weakref__"] or (n.s.startswith("__") and not n.s.endswith("__")):
                why = f"__slots__ entry '{n.s}' is not supported"
            elif ci.base in self.classes and n.s in self.classes[ci.base].methods:
                why = f"slot '{n.s}' shadows an inherited method or property: not supported"
            elif ci.base in self.classes and n.s in self.classes[ci.base].fdefault:
                why = f"slot '{n.s}' shadows an inherited class variable: not supported"
            else:
                ci.slots.append(n.s)
                own_slots.append(n.s)
        if why != "":
            if ci.mod == "":
                self.err(why)
            ci.bad = ci.bad if ci.bad != "" else f"class {shown(ci.name)} is not supported: {why}"
        # Reuse class-default globals without reserving an instance field: a
        # subclass may declare a different tuple length, or use a list/string.
        t = "str" if slot_node.kind == "str" else "list[str]" if slot_node.kind == "list" else self.ctype("tuple", ["str" for n in names])
        if st.kind == "annassign" and len(st.kids) == 3:
            why = self.ann_problem(st.kids[1], False) if ci.mod != "" else ""
            if why != "":
                ci.bad = ci.bad if ci.bad != "" else f"class {shown(ci.name)} is not supported: {why}"
            else:
                t = self.vtype(st.kids[1])
        ci.ftypes["__slots__"] = t
        ci.fdefault["__slots__"] = slot_node
        if st.kind == "assign":
            st.kind = "annassign"
            st.kids = [st.kids[0], noann, slot_node]
        ci.slotlimit = ci.exc == "" and (ci.base not in self.classes or self.classes[ci.base].slotlimit)
        # A slot's descriptor cannot coexist with a class variable or method of
        # that name. Reject shadowing inherited descriptors too.
        for d in ci.node.kids[0].kids:
            name = d.s if d.kind == "def" else d.kids[0].s if d.kind in ["assign", "annassign"] and d.kids[0].kind == "name" and (d.kind == "assign" or len(d.kids) == 3) else ""
            if name in ci.slots:
                why = f"'{name}' in __slots__ conflicts with class variable or method" if name in own_slots else f"shadowing inherited slot '{name}' with a class variable or method is not supported"
                if ci.mod == "":
                    self.err(why)
                ci.bad = ci.bad if ci.bad != "" else f"class {shown(ci.name)} is not supported: {why}"
    if ci.base in self.classes:
        # an exception class's objects begin with its base's fields (and their flags, see fl_fields)
        b = self.classes[ci.base]
        for x in b.fields:
            self.add_field(ci, x, b.ftypes[x])
            if x in b.fdefault:
                ci.fdefault[x] = b.fdefault[x]
            if x in b.fopts:
                ci.fopts[x] = b.fopts[x]  # (a dataclass's: its fields come first, as they are)
            if x in b.factory:
                ci.factory[x] = b.factory[x]
    elif ci.tag != 0:
        self.add_field(ci, " class", "int")
    elif ci.exc != "":
        # what its constructor sets (exc_object): its ExcClass, str(e) and the text between repr(e)'s
        # parentheses, and a SystemExit's status and whether its code is one (None, an int or a bool)
        xs = EXCFIELDS.split()
        for x in xs if exc_derives(ci.exc, "SystemExit") else xs[:3]:
            self.add_field(ci, " " + x[: x.find(":")], x[x.find(":") + 1 :])
    dc = self.is_dc(ci.name) and ci.name not in self.nts
    kwmode = ci.kwonly  # (@dataclass(kw_only=True), or after _: KW_ONLY)
    kwseen = False
    flines: dict[str, int] = {}  # (a dataclass's fields its body declares, and where)
    for st in ci.node.kids[0].kids:
        self.line = st.line
        binds: dict[str, bool] = {}
        stmt_walrus(st, binds)
        if has_kind(st, "walrus") or len(binds) > 0:
            why = "an assignment expression (:=) in a class body is not supported (CPython binds a class attribute)"
            if ci.mod == "":
                self.err(why)
            ci.bad = ci.bad if ci.bad != "" else f"class {shown(ci.name)} is not supported: {why}"
        if st.kind in ["assign", "annassign"] and st.kids[0].kind == "name" and st.kids[0].s == "__slots__":
            continue
        if dc and st.kind == "annassign" and st.kids[0].kind == "name" and self.imported_ref(st.kids[1]) == "dataclasses.KW_ONLY":
            # _: KW_ONLY is no field: the fields after it are keyword-only parameters of __init__
            if kwseen:
                self.err(f"'{st.kids[0].s}' is KW_ONLY, but KW_ONLY has already been specified")
            kwmode = True
            kwseen = True
            continue
        if dc and st.kind == "annassign" and st.kids[0].kind == "name":
            # (a base dataclass's field declared again has only its new default and options)
            flines[st.kids[0].s] = st.line
            ci.fopts[st.kids[0].s] = {}
            if st.kids[0].s in ci.factory:
                del ci.factory[st.kids[0].s]
        if st.kind == "annassign" and len(st.kids) == 3 and st.kids[2].kind == "call" and self.imported_ref(st.kids[2].kids[0]) == "dataclasses.field":
            if not dc:
                self.err("dataclasses.field() is only supported in the body of a @dataclass class")
            self.dc_field(ci, st)  # (its default becomes the statement's value)
        if dc and st.kind == "annassign" and st.kids[0].kind == "name":
            if st.kids[0].s in ci.fdefault and len(st.kids) < 3:
                del ci.fdefault[st.kids[0].s]
            o = ci.fopts[st.kids[0].s]
            if "kw_only" not in o and "pos" not in o and kwmode:
                o["kw_only"] = True
        if dc and st.kind == "annassign" and st.kids[0].kind == "name" and ci.base in self.classes and st.kids[0].s in self.classes[ci.base].ftypes:
            # (a base dataclass's field declared again, with or without a default)
            if self.vtype(st.kids[1]) != self.classes[ci.base].ftypes[st.kids[0].s]:
                self.bad_class(ci, f"field '{st.kids[0].s}' of '{short(ci.base)}' declared again in '{short(ci.name)}' with another type (not supported)")
                continue
        elif st.kind == "annassign" and st.kids[0].kind == "name" and ci.base in self.classes and st.kids[0].s in self.classes[ci.base].ftypes:
            # (a class attribute of the base bound again, with the same type: as x = v is)
            b = self.classes[ci.base]
            if len(st.kids) < 3 or st.kids[0].s not in b.fdefault or self.vtype(st.kids[1]) != b.ftypes[st.kids[0].s]:
                self.err(f"field '{st.kids[0].s}' of '{short(ci.base)}' declared again in '{short(ci.name)}' (not supported" + (", but for a class attribute of the same type" if st.kids[0].s in b.fdefault else "") + ")")
        if st.kind == "annassign" and st.kids[0].kind == "name" and ci.mod != "" and self.ann_problem(st.kids[1], False) != "":
            # an imported module's class: an error only where the program uses it
            ci.bad = ci.bad if ci.bad != "" else f"class {shown(ci.name)} is not supported: {self.ann_problem(st.kids[1], False)}"
            self.add_field(ci, st.kids[0].s, "int")
            if dc:
                del ci.fopts[st.kids[0].s]  # (whose default is not checked: see below)
        elif st.kind == "annassign" and st.kids[0].kind == "name":
            name = st.kids[0].s
            self.add_field(ci, name, self.vtype(st.kids[1]))
            if len(st.kids) == 3:
                ci.fdefault[name] = st.kids[2]
            if ci.name in self.nts and len(st.kids) == 3:
                last = name
            elif last != "" and ci.name in self.nts:
                self.err(f"Non-default namedtuple field {name} cannot follow default field {last}")
        elif st.kind == "assign" and len(st.kids) == 2 and st.kids[0].kind == "name" and dc and st.kids[1].kind == "call" and self.imported_ref(st.kids[1].kids[0]) == "dataclasses.field":
            self.err(f"'{st.kids[0].s}' is a field but has no type annotation")  # (CPython's TypeError where it creates the class)
        elif st.kind == "assign" and len(st.kids) == 2 and st.kids[0].kind == "name" and self.is_dc(ci.name):
            self.bad_class(ci, f"a class attribute without an annotation ({st.kids[0].s} = ...), which is no field of a {'NamedTuple' if ci.name in self.nts else 'dataclass'}, is not supported: annotate it")
        elif st.kind == "assign" and len(st.kids) == 2 and st.kids[0].kind == "name":
            # x = v: a class attribute, typed by v as a field is (and from here on read as x: T = v)
            if st.kids[1].kind == "call" and st.kids[1].kids[0].kind == "name" and st.kids[1].kids[0].s == "property" and "property" not in self.funcs:
                why = "property() called as a function is not supported: decorate the getter with @property and the setter with @x.setter"
                if ci.mod == "":
                    self.err(why)
                ci.bad = ci.bad if ci.bad != "" else f"class {shown(ci.name)} is not supported: {why}"
            t = self.guess(st.kids[1], FnInfo("", "", ci.node, ""))
            bt = self.classes[ci.base].ftypes.get(st.kids[0].s, "") if ci.base in self.classes else ""
            if t != "" and bt != "" and (self.widens(t, bt) or self.boxes(t, bt)):
                t = bt  # (a class attribute of the base bound again, with a value of its type)
            if t == "" and ci.mod == "":
                self.err(f"cannot infer the type of class attribute '{st.kids[0].s}'; annotate it ({st.kids[0].s}: T = ...)")
            if t == "":
                ci.bad = ci.bad if ci.bad != "" else f"class {shown(ci.name)} is not supported: cannot infer the type of class attribute '{st.kids[0].s}'"
                t = "int"
            self.add_field(ci, st.kids[0].s, t)
            ci.fdefault[st.kids[0].s] = st.kids[1]
            st.kind = "annassign"
            st.kids = [st.kids[0], mk("noann", "", st.line, []), st.kids[1]]
        elif st.kind != "def" and st.kind != "pass" and not (st.kind == "expr" and (st.kids[0].kind == "str" or st.kids[0].kind == "ellipsis")):
            what = "an assignment to anything but one name (x = v)" if st.kind == "assign" else "an expression statement" if st.kind == "expr" else f"a{'n' if st.kind[0] in 'aeiou' else ''} {st.kind} statement"
            self.err(f"a class body may only contain fields, methods, a docstring, pass and ..., not {what}")
    for fl in ci.fields if dc and "no-init" not in ci.dcopts else []:
        # the positional parameters of the __init__ @dataclass writes, the base's fields first
        if fl in ci.fopts and "no-init" not in ci.fopts[fl] and "kw_only" not in ci.fopts[fl]:
            if fl in ci.fdefault or fl in ci.factory:
                last = fl
            elif last != "":
                self.line = flines[fl] if fl in flines else ci.node.line
                self.err(f"non-default argument '{fl}' follows default argument '{last}'")
    if dc and ci.base in self.classes:
        # the methods @dataclass wrote for the base, after inherit() copied its others, but the
        # __init__ it writes for this class
        b = self.classes[ci.base]
        if "no-init" not in ci.dcopts and "__init__" in ci.methods and ci.methods["__init__"].cls != ci.name:
            del ci.methods["__init__"]
        for m in b.methods:
            if m not in ci.methods and (m != "__init__" or "no-init" in ci.dcopts):
                ci.methods[m] = b.methods[m]
    if ci.name in self.nts and ci.name not in self.cnts:
        self.nt_class(ci)
    if self.is_dc(ci.name) and ci.name not in self.cnts:
        self.dc_methods(ci)  # (namedtuple()'s: its specializations', see specialize)
    for m in UNCALLED:
        # a def or a class attribute (CPython calls what it binds), also a base's, then named; an
        # imported module's class: an error only where the program uses it (see hoist_class)
        owner = ci.methods[m].cls if m in ci.methods else self.default_home(ci, m).name if m in ci.fdefault else ""
        if owner == "":
            continue
        why = f"the special method {m}{'' if owner == ci.name else ' of its base ' + shown(owner)} is not supported (CPython calls it {UNCALLED[m]})"
        if ci.mod == "":
            self.line = ci.node.line if owner != ci.name else ci.methods[m].node.line if m in ci.methods else ci.fdefault[m].line
            self.err(why)
        ci.hook = ci.hook if ci.hook != "" else f"class {shown(ci.name)} is not supported: {why}"
    b = self.classes[ci.base] if ci.base in self.classes else ClassInfo("", ci.node)
    if "__init_subclass__" in b.methods or "__init_subclass__" in b.fdefault:
        # a base's (a def or a class attribute), which CPython calls when the class statement runs
        # (in an imported module, as the module is imported, whether or not the program uses the class)
        self.line = ci.node.line
        owner = short(b.methods["__init_subclass__"].cls if "__init_subclass__" in b.methods else self.default_home(b, "__init_subclass__").name)
        self.err(f"a base that defines __init_subclass__ is not supported (CPython calls {owner}.__init_subclass__() when it creates class {short(ci.name)})")
    if "__init__" not in ci.methods and ci.base in self.classes and "__init__" in self.classes[ci.base].methods and not (dc and "no-init" not in ci.dcopts):
        # A base with no explicit initializer acquired its empty one while its fields were
        # declared, after inherit() copied its other methods.
        ci.methods["__init__"] = self.classes[ci.base].methods["__init__"]
    if "__init__" in ci.methods or ci.exc != "":
        # (an exception class without __init__ of its own takes its base's, or none)
        if "__init__" in ci.methods and ci.methods["__init__"].cls == ci.name and ci.name not in self.tmpl:
            f = ci.methods["__init__"]
            self.scan_fields(ci, f, f.node.kids[2].kids, {})
    if ci.tag > 0:
        for name in ci.ftypes:
            if name in ci.methods:
                self.line = ci.node.line
                owner = short(ci.methods[name].cls)
                self.bad_class(ci, f"field '{name}' of '{short(ci.name)}' conflicts with method '{owner}.{name}': method and field shadowing in an inheritance hierarchy is not supported")
                break
    if "__init__" in ci.methods or ci.exc != "":
        return
    # synthesize __init__: @dataclass takes every field as a parameter
    body: list[Node] = []
    d = mk("def", "__init__", ci.node.line, [noann, noann, mk("block", "", ci.node.line, body)])
    f = FnInfo("__init__", f"@m.{ci.name}.__init__", d, ci.name)
    me = "self" if "self" not in ci.ftypes else "__pys_self"  # (a field may be named self)
    f.params.append(me)
    f.ptypes.append("" if ci.tag != 0 else ci.name)
    f.generic = ci.tag != 0
    f.defaults.append(noann)
    f.dglob.append("")
    if self.is_dc(ci.name) and "no-init" not in ci.dcopts:
        # its parameters: the fields with init=True, the keyword-only ones last, then for each
        # init=False field with a default_factory one that no call can name (x.factory). A call
        # that leaves out such a parameter calls the field's default_factory (dglob "()"), after
        # it evaluates its arguments, in field order (see call_fn), as the __init__ @dataclass
        # writes calls each in turn. Its body assigns each field from its parameter, else from
        # its default (CPython reads it from the class); a field with neither stays unassigned
        plain: dict[str, bool] = {}  # (a NamedTuple's field, which has no options)
        dfs = self.dc_fields(ci)
        for kw in [False, True]:
            if kw and len([x for x in ci.fields if x in ci.fopts and "kw_only" in ci.fopts[x]]) > 0:
                f.npos = len(f.params)  # (self and the positional ones)
            for fl in dfs:
                o = ci.fopts[fl] if fl in ci.fopts else plain
                if "no-init" not in o and ("kw_only" in o) == kw:
                    f.params.append(fl)
                    f.ptypes.append(ci.ftypes[fl])
                    f.defaults.append(ci.fdefault[fl] if fl in ci.fdefault else mk("None", "", d.line, []) if fl in ci.factory else noann)
                    f.dglob.append("()" if fl in ci.factory else "")
        for fl in dfs:
            if fl in ci.factory and "no-init" in ci.fopts[fl]:
                f.npos = len(f.params) if f.npos < 0 else f.npos
                f.params.append(fl + ".factory")
                f.ptypes.append(ci.ftypes[fl])
                f.defaults.append(mk("None", "", d.line, []))
                f.dglob.append("()")
        cn = mk("name", ci.name, d.line, [])
        for fl in dfs:
            o = ci.fopts[fl] if fl in ci.fopts else plain
            v = mk("name", fl, d.line, [])
            if fl in ci.factory and not (fl in b.factory and b.factory[fl] is ci.factory[fl]):
                self.dc_factory(ci, fl)  # (else the base's, which it inherits)
            if "no-init" in o and fl in ci.factory:
                v = mk("name", fl + ".factory", d.line, [])
            elif "no-init" in o and fl in ci.fdefault:
                v = mk("attr", fl, d.line, [cn])
            elif "no-init" in o:
                continue
            body.append(mk("assign", "", d.line, [mk("attr", fl, d.line, [mk("name", me, d.line, [])]), v]))
        if "__post_init__" in ci.methods:
            # (then calls __post_init__, as the __init__ @dataclass writes does)
            post = mk("attr", "__post_init__", d.line, [mk("name", me, d.line, [])])
            body.append(mk("expr", "", d.line, [mk("call", "", d.line, [post])]))
    ci.methods["__init__"] = f

def gen_nt_class(self, ci: ClassInfo) -> None:
    # class P(NamedTuple): a dataclass (its __init__ and __repr__) whose fields are never
    # assigned after __init__, read in order where it is unpacked, indexed or iterated, and
    # compared, concatenated and %-formatted as the tuple of its fields (see ntop); tuple's
    # other methods are not there
    self.line = ci.node.line
    for m in "__new__ __init__ __slots__ __getnewargs__ _fields _field_defaults _make _replace _asdict _source".split():
        if m in ci.methods:
            self.err(f"Cannot overwrite NamedTuple attribute {m}")
    for m in ["__getitem__", "__iter__"]:
        if m in ci.methods:
            self.err(f"a NamedTuple that defines {m} is not supported (Pystachy reads its fields where CPython would call it)")
    for fl in ci.fields:
        if fl.startswith("_"):
            self.err(f"Field names cannot start with an underscore: '{fl}'")
    if len(ci.fields) == 0:
        self.err("a NamedTuple without fields is not supported")

def gen_generic_base(self, n: Node) -> list[str]:
    # the type variables of a class's base n when it is typing.Generic[T, *Ts]: TypeVars and at
    # most one TypeVarTuple, unpacked, each once; else []
    if n.kind != "index" or self.imported_ref(n.kids[0]) != "typing.Generic":
        return []
    out: list[str] = []
    for x in n.kids[1].kids if n.kids[1].kind == "tuple" else [n.kids[1]]:
        v = x.kids[0] if x.kind == "starred" else x
        if v.kind != "name" or v.s not in self.typevars or (v.s in self.tvtuples) != (x.kind == "starred") or v.s in out:
            return []
        out.append(v.s)
    return out if len([v for v in out if v in self.tvtuples]) < 2 else []

def gen_nt_base(self, n: Node) -> bool:
    # does a class's base n name typing.NamedTuple
    return (n.kind == "name" and self.imported(n.s) == "typing.NamedTuple") or (n.kind == "attr" and self.typing_attr(n) == "NamedTuple")

def gen_nt_fields(self, c: str) -> list[str]:
    # the fields of NamedTuple class c: those its "namedtuple" node names where namedtuple() made
    # it, a class template, whose specializations declare them (see specialize)
    if c in self.cnts:
        return [x.s for x in self.cnts[c].kids[0].kids]
    return self.classes[c].fields

def gen_nt_defaults(self, c: str) -> Val:
    # C._field_defaults of namedtuple()'s class C (also through an object of C): the dict of its
    # fields' defaults that its class statement makes (hoist_class) and that C keeps, as CPython's
    # class attribute is kept
    if c not in self.cnts:
        self.err(f"{short(c)}._field_defaults is not supported (of a typing.NamedTuple class)")
    t = self.nt_dflt_type(c)
    if t == "":
        self.err(f"{short(c)}._field_defaults is not supported where its defaults are all None (a dict of None values)")
    return Val(self.mload(t, f"@d.c.{c}._field_defaults"), t)

def gen_nt_dflt_type(self, c: str) -> str:
    # (nt_defaults) the type of the _field_defaults of namedtuple()'s class c, whose global it
    # declares: a dict whose values have the types of its constants (a union of them, with None an
    # optional; of no defaults, a dict[str, int]); "" where there is no such type (all None)
    if c not in self.ntdflts:
        ks: list[str] = []
        for x in self.cnts[c].kids[1].kids:
            ks.append(x.kids[0].kind if x.kind == "unary" else "bool" if x.kind == "True" or x.kind == "False" else x.kind)
        t = self.union_type(ks) if len(ks) > 0 else "int"
        self.ntdflts[c] = "" if t.startswith("!") or t == "None" else self.ctype("dict", ["str", t])
        if self.ntdflts[c] != "":
            self.global_var(f"@d.c.{c}._field_defaults", self.ntdflts[c])
    return self.ntdflts[c]

def gen_nt_dflt_display(self, c: str) -> Node:
    # (nt_defaults) a dict display of the fields of namedtuple()'s class c that have defaults,
    # and their constants
    line = self.cnts[c].line
    d = mk("dict", "", line, [])
    fs = self.nt_fields(c)
    ds = self.cnts[c].kids[1].kids
    for i in range(len(ds)):
        d.kids.extend([mk("str", fs[len(fs) - len(ds) + i], line, []), clone(ds[i])])
    return d

def gen_dc_fields(self, ci: ClassInfo) -> list[str]:
    # the fields of dataclass (or NamedTuple) ci that @dataclass knows: those with options (not
    # a base's other attributes, which its own __init__ assigns, nor the class tag)
    return [x for x in ci.fields if x in ci.fopts or ci.name in self.nts]

def gen_dc_field(self, ci: ClassInfo, st: Node) -> None:
    # x: T = field(...) in the body of dataclass ci: the field's options (ci.fopts) and its
    # default_factory (ci.factory); its default, if any, becomes the statement's value, which
    # the class statement evaluates where CPython evaluates field()'s arguments
    call = st.kids[2]
    name = st.kids[0].s
    o: dict[str, bool] = {}
    dflt: list[Node] = []
    for a in call.kids[1:]:
        if a.kind != "kw":
            n = len([x for x in call.kids[1:] if x.kind != "kw"])
            if a.kind == "starred" or a.kind == "dstar":
                self.bad_class(ci, "star arguments are not supported")
                continue
            self.err(f"field() takes 0 positional arguments but {n} {'was' if n == 1 else 'were'} given")
        v = a.kids[0]
        if a.s == "default":
            dflt.append(v)
        elif a.s == "default_factory":
            ci.factory[name] = v
        elif a.s == "init" or a.s == "repr" or a.s == "compare" or a.s == "kw_only":
            if v.kind != "True" and v.kind != "False":
                self.bad_class(ci, f"field({a.s}=...) needs True or False")
            if a.s == "kw_only":
                o["kw_only" if v.kind == "True" else "pos"] = True
            elif v.kind == "False":
                o["no-" + a.s] = True
        elif a.s == "hash":
            if v.kind != "True" and v.kind != "False" and v.kind != "None":
                self.bad_class(ci, "field(hash=...) needs True, False or None")
            if v.kind == "True" or v.kind == "False":
                o["hash" if v.kind == "True" else "no-hash"] = True
        elif a.s == "metadata":
            self.bad_class(ci, "field(metadata=...) is not supported")
        else:
            self.err(f"field() got an unexpected keyword argument '{a.s}'")
    if len(dflt) > 0 and name in ci.factory:
        self.err("cannot specify both default and default_factory")  # (CPython's ValueError)
    ci.fopts[name] = o
    st.kids = st.kids[:2] + dflt

def gen_dc_factory(self, ci: ClassInfo, fl: str) -> None:
    # field fl's default_factory: a static method of the class, fl.factory, compiled if called,
    # that returns what it gives (a function's or class's call, or a lambda's body). The
    # __init__ @dataclass writes calls it for each object it is not given fl for
    line = ci.factory[fl].line
    x = ci.factory[fl]
    if x.kind == "lambda" and len(x.kids[0].kids) == 0:
        v = x.kids[1]
    elif x.kind == "name" or x.kind == "attr":
        v = mk("call", "", line, [x])
        later = (x.s in self.funcs and self.funcs[x.s].mod == ci.mod and self.funcs[x.s].node.line > ci.node.line) or (x.s in self.classes and self.classes[x.s].mod == ci.mod and self.classes[x.s].node.line >= ci.node.line)
        if x.kind == "name" and later:
            self.line = line
            self.err(f"name '{short(x.s)}' is not defined (CPython reads a default_factory when it creates the class, before this def or class statement runs)")
    else:
        self.line = line
        self.bad_class(ci, "default_factory= is only supported as a function, a class or a lambda without parameters")
        v = mk("None", "", line, [])
    f = FnInfo(fl + ".factory", f"@m.{ci.name}.{fl}.factory", mk("def", fl, line, [mk("noann", "", line, []), mk("noann", "", line, []), mk("block", "", line, [mk("return", "", line, [v])])]), ci.name)
    f.deco = "staticmethod"
    f.ret = ci.ftypes[fl]
    f.synthetic = True
    f.mod = ci.mod
    ci.methods[f.name] = f
    self.lazy[f.ll] = f

def gen_frozen_store(self, o: Val, name: str, delete: bool = False) -> bool:
    # o.name = v (delete: del o.name) of a field of a @dataclass(frozen=True) object: CPython's
    # __setattr__ (__delattr__) raises FrozenInstanceError, but in the __init__ @dataclass
    # writes, which sets the fields as object.__setattr__ does. True when it raises
    ci = self.classes[o.t]
    if "frozen" not in ci.dcopts or (not delete and self.curfn.name == "__init__" and self.derives(o.t, self.curfn.cls) and self.curfn.node.kids[0].kind == "noann"):
        return False
    self.notnone(o, f"AttributeError: 'NoneType' object has no attribute '{name}' and no __dict__ for setting new attributes")
    self.raise_(FROZENERR, self.sconst(f"cannot {'delete' if delete else 'assign to'} field '{name}'"))
    return True

def gen_frozen(self, t: str, name: str) -> None:
    # a NamedTuple's fields are assigned only by its __init__, a range object's by none (as
    # CPython's start, stop and step are read-only)
    if t == RANGEC and self.curfn.mod != RANGES:
        self.err("readonly attribute")
    if t in self.nts and not (self.curfn.name == "__init__" and self.curfn.cls == t):
        self.err(f"cannot assign to field '{name}' of NamedTuple {short(t)} (AttributeError: can't set attribute); make a new one with _replace({name}=...)")
    if t in self.classes and name in self.classes[t].fconst and not (self.curfn.name == "__init__" and self.curfn.cls == t):
        self.err(f"cannot assign to field '{name}' of {short(t)}: it holds a constant of the literal arguments the object was made with")

def gen_synth(self, ci: ClassInfo, name: str, ret: str, body: list[Node]) -> None:
    # a method the compiler writes for a dataclass, generated only if the program calls it
    line = ci.node.line
    noann = mk("noann", "", line, [])
    f = FnInfo(name, f"@m.{ci.name}.{name}", mk("def", name, line, [noann, noann, mk("block", "", line, body)]), ci.name)
    f.params.append("self")
    f.ptypes.append(ci.name)
    if name in ["__eq__", "__lt__", "__le__", "__gt__", "__ge__"]:
        f.params.append("other")
        f.ptypes.append(ci.name)
    for _ in f.params:
        f.defaults.append(noann)
        f.dglob.append("")
    f.ret = ret
    f.synthetic = True
    ci.methods[name] = f
    self.lazy[f.ll] = f

def gen_dc_methods(self, ci: ClassInfo) -> None:
    # @dataclass: __repr__ is Name(field=repr(value), ...), __eq__ compares the fields in order,
    # and order=True's __lt__, __le__, __gt__ and __ge__ compare the tuples of their values; a
    # field(repr=False) is left out of __repr__, a field(compare=False) out of the comparisons
    line = ci.node.line
    me = mk("name", "self", line, [])
    other = mk("name", "other", line, [])
    # (what it writes replaces what the class inherits, but not what its body defines)
    own: dict[str, bool] = {}
    for m in ci.methods:
        if ci.methods[m].cls == ci.name:
            own[m] = True
    reprs = [x for x in self.dc_fields(ci) if x not in ci.fopts or "no-repr" not in ci.fopts[x]]
    cmps = [x for x in self.dc_fields(ci) if x not in ci.fopts or "no-compare" not in ci.fopts[x]]
    if "no-repr" in ci.dcopts and "__repr__" in ci.methods and ci.methods["__repr__"].synthetic and "__repr__" not in own:
        self.line = line
        self.bad_class(ci, f"repr=False in a dataclass whose base's __repr__ is the one @dataclass writes is not supported (CPython's shows the object's class, {short(ci.name)})")
    if "__repr__" not in own and "no-repr" not in ci.dcopts:
        parts: list[Node] = []
        lit = short(ci.name) + "("
        for i in range(len(reprs)):
            parts.append(mk("str", lit + (", " if i > 0 else "") + reprs[i] + "=", line, []))
            parts.append(mk("call", "", line, [mk("name", "__pys_repr", line, []), mk("attr", reprs[i], line, [me])]))
            lit = ""
        parts.append(mk("str", lit + ")", line, []))
        # like reprlib.recursive_repr: an object already being printed shows as ...
        enter = mk("call", "", line, [mk("name", "__pys_repr_enter", line, []), me])
        busy = mk("block", "", line, [mk("return", "", line, [mk("str", "...", line, [])])])
        r = mk("name", "r", line, [])
        if ci.name in self.nts:
            # (a tuple's repr has no guard: a cycle through a field shows where a list's repr stops it)
            self.synth(ci, "__repr__", "str", [mk("return", "", line, [mk("fstr", "", line, parts)])])
        else:
            self.synth(ci, "__repr__", "str", [mk("if", "", line, [mk("unary", "not", line, [enter]), busy, mk("block", "", line, [])]),
                                              mk("assign", "", line, [r, mk("fstr", "", line, parts)]),
                                              mk("expr", "", line, [mk("call", "", line, [mk("name", "__pys_repr_leave", line, []), me])]),
                                              mk("return", "", line, [r])])
    isnone = mk("cmp", "is", line, [other, mk("None", "", line, [])])
    if "__eq__" not in own and ci.name not in self.nts and "no-eq" not in ci.dcopts:  # (a NamedTuple's is tuple's, see ntop)
        test = mk("True", "", line, [])
        for i in range(len(cmps)):
            c = mk("cmp", "==", line, [mk("attr", cmps[i], line, [me]), mk("attr", cmps[i], line, [other])])
            test = c if i == 0 else mk("boolop", "and", line, [test, c])
        same = mk("cmp", "is", line, [other, me])
        yes = mk("block", "", line, [mk("return", "", line, [mk("True", "", line, [])])])
        no = mk("block", "", line, [mk("return", "", line, [mk("False", "", line, [])])])
        self.synth(ci, "__eq__", "bool", [mk("if", "", line, [same, yes, mk("block", "", line, [])]),
                                        mk("if", "", line, [isnone, no, mk("block", "", line, [])]), mk("return", "", line, [test])])
    if "unsafe_hash" in ci.dcopts and "__hash__" in own:
        self.err(f"Cannot overwrite attribute __hash__ in class {short(ci.name)}")
    if "__hash__" not in own and ci.name not in self.nts and ("unsafe_hash" in ci.dcopts or ("frozen" in ci.dcopts and "no-eq" not in ci.dcopts)):
        # unsafe_hash=True, or frozen=True with eq: the hash of the tuple of the fields that
        # field(hash=True) names, or whose hash is None and that compare (CPython's _hash_add)
        hs = [x for x in self.dc_fields(ci) if x in ci.fopts and ("hash" in ci.fopts[x] or ("no-hash" not in ci.fopts[x] and "no-compare" not in ci.fopts[x]))]
        hs = [x for x in self.dc_fields(ci) if x not in ci.fopts or x in hs]
        tup = mk("tuple", "", line, [mk("attr", x, line, [me]) for x in hs])
        self.synth(ci, "__hash__", "int", [mk("return", "", line, [mk("call", "", line, [mk("name", "__pys_hash", line, []), tup])])])
    for m in ["__lt__", "__le__", "__gt__", "__ge__"] if "order" in ci.dcopts else []:
        if m in own:
            self.err(f"Cannot overwrite attribute {m} in class {short(ci.name)} Consider using functools.total_ordering")
        op = {"__lt__": "<", "__le__": "<=", "__gt__": ">", "__ge__": ">="}[m]
        mine = mk("tuple", "", line, [mk("attr", x, line, [me]) for x in cmps])
        theirs = mk("tuple", "", line, [mk("attr", x, line, [other]) for x in cmps])
        msg = mk("str", f"'{op}' not supported between instances of '{short(ci.name)}' and 'NoneType'", line, [])
        bad = mk("block", "", line, [mk("raise", "", line, [mk("call", "", line, [mk("name", "TypeError", line, []), msg])])])
        self.synth(ci, m, "bool", [mk("if", "", line, [isnone, bad, mk("block", "", line, [])]), mk("return", "", line, [mk("cmp", op, line, [mine, theirs])])])

def gen_scan_fields(self, ci: ClassInfo, f: FnInfo, body: list[Node], known: dict[str, bool]) -> None:
    # fields are the attributes assigned on self inside __init__; after a guard that exits where
    # a parameter is not callable (known), the parameter's type decides its isinstance() tests,
    # and only the branch that runs gives fields their types
    for st in body:
        self.line = st.line
        k = st.kind
        if k == "if" and self.callable_guard(st, f) != "":
            known[self.callable_guard(st, f)] = True
        x = st.kids[0] if k == "if" else st
        neg = x.kind == "unary" and x.s == "not"
        x = x.kids[0] if neg else x
        if k == "if" and x.kind == "call" and len(x.kids) == 3 and x.kids[0].kind == "name" and x.kids[0].s == "isinstance" and x.kids[1].kind == "name" and x.kids[1].s in known:
            r = self.isinst(f.ptypes[f.params.index(x.kids[1].s)], x.kids[2])
            r = 1 if r == -2 else 0 if r == -3 else r
            if r >= 0:
                self.scan_fields(ci, f, st.kids[1].kids if (r == 1) != neg else st.kids[2].kids, known)
                continue
        if (k == "assign" or k == "annassign") and st.kids[0].kind == "attr" and st.kids[0].kids[0].kind == "name" and st.kids[0].kids[0].s == f.params[0]:
            name = st.kids[0].s
            ms = self.classes[ci.origin].methods if ci.origin != "" else ci.methods  # (a specialization's are declared after its fields)
            if name not in ci.ftypes and not (name in ms and ms[name].prop):  # (a property's setter takes it)
                self.exc_attr(ci, name)
                # (Iterator[T] or Iterable[T] types nothing: the field's is its value's, see tmpl_ann)
                k = "assign" if k == "annassign" and len(st.kids) == 3 and self.iter_item(st.kids[1]) is not None else k
                why = self.ann_problem(st.kids[1], False) if k == "annassign" and ci.mod != "" else ""
                t = "" if why != "" else self.vtype(st.kids[1]) if k == "annassign" else self.guess(st.kids[-1], f)
                if t.startswith("!"):
                    why = t[1:]  # (a call of a function Pystachy cannot compile: its error)
                given = t
                t = "" if t == "None" or why != "" else t  # (f() that returns None: a field has a value type)
                if t == "" and why == "" and ci.origin in self.cnts:
                    why = f"field '{name}' of namedtuple {short(ci.name)} given {'None' if given == 'None' else 'a value whose type cannot be inferred'} is not supported (the call that makes an object types its fields)"
                if t == "" and why == "":
                    why = f"cannot infer the type of field '{name}'; annotate it (self.{name}: T = ...)"
                if t == "" and ci.mod == "":
                    self.err(why)
                if t == "":
                    # an imported module's class: an error only where the program uses it
                    ci.bad = ci.bad if ci.bad != "" else f"class {shown(ci.name)} is not supported: {why}"
                    t = "int"
                self.add_field(ci, name, t)
            elif name not in ci.ftypes and name + ".setter" in ms and ms[name + ".setter"].cls == (ci.origin if ci.origin != "" else ci.name) and ci.name + "." + name not in self.scanning:
                # self.x = v of property x in __init__ (or in a setter it calls so): the fields
                # its setter assigns too
                g = ms[name + ".setter"]
                if ci.origin != "":
                    # (a specialization's, whose value has the type of v, unless annotated with
                    # no type variable, as its __init__'s parameters have the arguments')
                    h = FnInfo(g.name, g.ll, g.node, ci.name)
                    h.params = g.params
                    h.ptypes = [ci.name, g.ptypes[1] if g.ptypes[1] != "" else self.guess(st.kids[-1], f)]
                    h.acc = g.acc
                    g = h
                self.scanning[ci.name + "." + name] = True
                self.scan_fields(ci, g, g.node.kids[2].kids, {})
                del self.scanning[ci.name + "." + name]
                self.line = st.line
        for kid in st.kids:
            if kid.kind == "block":
                self.scan_fields(ci, f, kid.kids, known)
            elif kid.kind == "except":
                self.scan_fields(ci, f, kid.kids[1].kids, known)

def gen_guess_args(self, init: FnInfo, args: list[Node], f: FnInfo) -> list[str]:
    # the types of the arguments (but self) that the call of class template __init__ init with
    # args passes, as guess infers them ([] for none); ["!"] where it cannot (a keyword or
    # star argument, *args, a type it cannot infer)
    ts: list[str] = []
    if (init.vararg >= 0 or init.kwarg >= 0) and init.vartup == "":
        return self.guess_varargs(init, args, f)
    if init.vararg >= 0 or init.kwarg >= 0 or len(args) > len(init.params) - 1:
        return ["!"]
    for i in range(1, len(init.params)):
        if i - 1 < len(args):
            a = args[i - 1]
            if a.kind == "kw" or a.kind == "starred" or a.kind == "dstar":
                return ["!"]
            t = self.guess(a, f)
        elif init.defaults[i].kind == "noann":
            return ["!"]
        else:
            t = "None" if init.defaults[i].kind == "None" else self.guess(init.defaults[i], FnInfo("", "", init.node, ""))
        if t == "" or t.startswith("!"):
            return ["!"]
        ts.append(t)
    return ts

def gen_guess_varargs(self, init: FnInfo, args: list[Node], f: FnInfo) -> list[str]:
    # guess_args for an __init__ that takes *args or **kwargs: the types call_fn binds, the extra
    # positional arguments' a tuple, the extra keyword arguments' a record (kw[...])
    np = len(init.params)
    ts = [""] * (np - 1)
    extra: list[str] = []
    names: list[str] = []
    types: list[str] = []
    pos = 1
    for a in args:
        if a.kind == "starred" or a.kind == "dstar":
            return ["!"]
        t = self.guess(a.kids[0] if a.kind == "kw" else a, f)
        if t == "" or t.startswith("!"):
            return ["!"]
        if a.kind == "kw":
            j = init.params.index(a.s) if a.s in init.params else -1
            if init.kwarg >= 0 and (j < 0 or j < init.posonly or j == init.kwarg or j == init.vararg):
                if a.s in names:
                    return ["!"]
                names.append(a.s)
                types.append(init.kwelem if init.kwelem != "" else t)
            elif j < 1 or ts[j - 1] != "":
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
            t = "None" if init.defaults[i].kind == "None" else self.guess(init.defaults[i], FnInfo("", "", init.node, ""))
            if t == "" or t.startswith("!"):
                return ["!"]
            ts[i - 1] = t
    return ts

def guess_scope(f: FnInfo) -> list[Node]:
    # the statements whose bindings hide a function from gen_guess: those of the function f, or
    # of the class body whose attribute declare_fields types (f.node is then the class's node)
    return f.node.kids[0].kids if f.node.kind == "class" else f.node.kids[2].kids


def gen_guess(self, e: Node, f: FnInfo) -> str:
    k = e.kind
    if k == "int" or k == "float" or k == "str" or k == "bytes":
        return k
    if k == "True" or k == "False":
        return "bool"
    if k == "fstr" or (k == "call" and literal_format(e.kids[0])):
        return "str"
    if (k == "call" and e.kids[0].kind == "attr" and (e.kids[0].s == "format" or e.kids[0].s == "format_map")) or (k == "binop" and e.s == "%"):
        # ("...".format(...), FMT.format(...), str.format(FMT, ...) and FMT % x of a module's
        # FMT = "...")
        o = e.kids[0].kids[0] if k == "call" else e.kids[0]
        if k == "call" and o.kind == "name" and o.s == "str" and not self.bound("str") and len(e.kids) > 1:
            o = e.kids[1]
        if o.kind == "str" or (o.kind == "name" and o.s in self.strglobals and o.s not in f.params):
            return "str"
    if k == "unary" and e.s != "not":
        t = self.guess(e.kids[0], f)
        # (-True is -1, as unary() computes it; -o is what o.__neg__ returns, unknown as for o + o)
        return "int" if t == "bool" else "" if t in self.classes and UNARY[e.s] in self.classes[t].methods else t
    if k == "name" and e.s in f.params:
        t = f.ptypes[f.params.index(e.s)]
        if t == "" and takes_self(f) and e.s == f.params[0] and self.classes[f.cls].tag != 0:
            return f.cls  # field inference precedes specialization of the concrete receiver
        return t if t != "" or f.bad == "" else "!" + f.bad  # (a parameter whose annotation failed)
    if k == "name" and (e.s in self.funcs or (e.s in PYBUILTINS and e.s[0].islower() and not self.bound(e.s))):
        # a function, which the field then holds (unless a local of the method has its name)
        asg: dict[str, bool] = {}
        local_names(guess_scope(f), asg)
        if e.s not in asg:
            return f"fn[f:{e.s}]" if e.s in self.funcs else f"fn[b:{e.s}]"
    p = self.imported_ref(e) if k == "name" or k == "attr" else ""
    if p in MODFUNCS:
        # a builtin module's function (math.sqrt, or sqrt from-imported), unless a local of the
        # method has the name it is read through
        root = e
        while root.kind == "attr":
            root = root.kids[0]
        asg = {}
        local_names(guess_scope(f), asg)
        if root.s not in asg:
            return f"fn[b:{p}]"
    # self.k, self.m(...) and self(...) before the names below: self shadows a function, class,
    # import or builtin of its name
    me = f.params[0] if takes_self(f) else ""
    if k == "attr" and e.kids[0].kind == "name" and e.kids[0].s == me:
        ci = self.classes[f.cls]
        if e.s in ci.methods and ci.methods[e.s].prop:
            return ci.methods[e.s].ret
        if e.s not in ci.ftypes and e.s in ci.methods and ci.methods[e.s].deco == "":
            return f"fn[m:{f.cls}.{e.s}]"  # (self.m: the method bound to the object)
        return ci.ftypes.get(e.s, "")
    if k == "attr" and e.kids[0].kind == "name" and e.kids[0].s in f.params and e.kids[0].s != me:
        # p.k of a parameter p holding an object: the type of its field k
        t = self.guess(e.kids[0], f)
        if t in self.classes and e.s in self.classes[t].ftypes and e.s not in self.classes[t].methods:
            return self.classes[t].ftypes[e.s]
    if k == "dictstar":
        # {**a, **b} of **kwargs records: their record, each name with its last value's type
        names: list[str] = []
        types: list[str] = []
        for x in e.kids:
            t = self.guess(x.kids[0], f) if x.kind == "dstar" else ""
            if not t.startswith("kw["):
                return t if t.startswith("!") else ""
            for j in range(len(kw_names(t))):
                if kw_names(t)[j] in names:
                    types[names.index(kw_names(t)[j])] = kw_types(t)[j]
                else:
                    names.append(kw_names(t)[j])
                    types.append(kw_types(t)[j])
        return "kw[" + ",".join([names[j] + ":" + types[j] for j in range(len(names))]) + "]"
    if k == "call" and e.kids[0].kind == "attr" and e.kids[0].kids[0].kind == "name" and e.kids[0].kids[0].s == me:
        ms = self.classes[f.cls].methods
        m = e.kids[0].s
        if m in ms and ms[m].prop:
            return targs(ms[m].ret)[0] if is_callable(ms[m].ret) else ""
        return "" if m not in ms else ms[m].ret if ms[m].bad == "" else "!" + ms[m].bad
    if k == "call" and e.kids[0].kind == "name" and e.kids[0].s == me:
        ms = self.classes[f.cls].methods  # self(...): self.__call__(...)
        return "" if "__call__" not in ms else ms["__call__"].ret if ms["__call__"].bad == "" else "!" + ms["__call__"].bad
    if k == "call" and len(e.kids) == 2 and (self.imported_ref(e.kids[0]) == "os.fspath" or self.imported_ref(e.kids[0]) == "os.path.normcase") and unopt(self.guess(e.kids[1], f)) == "str":
        return "str"  # (a str path is its own file system path, and its own posixpath normcase())
    if k == "call" and e.kids[0].kind == "name":
        c = e.kids[0].s
        if c in self.tmpl:
            # a class template's object: of the specialization its arguments' types pick, once
            # code is being compiled (a specialization compiles its special methods)
            ts = self.guess_args(self.classes[c].methods["__init__"], e.kids[1:], f) if self.compiling else ["!"]
            lits = self.literal_args(self.classes[c].methods["__init__"], e.kids[1:]) if self.literal_class(c) and "!" not in ts else {}
            return self.specialize(c, ts, {}, False, lits) if "!" not in ts else ""
        if c in self.classes or c in self.unsupported:
            return c if c in self.classes else "!" + self.unsupported[c]
        if c in self.funcs:
            helper = self.funcs[c]
            if helper.bad != "":
                return "!" + helper.bad
            if self.compiling and helper.generic and helper.ret == "" and helper.cls == "" and helper.clo < 0 and helper.vararg < 0 and helper.kwarg < 0 and not helper.extern and not helper.pyexport:
                # A constructor field can keep the return type of an ordinary
                # helper specialized for its known argument types. This compiles
                # the existing template; it neither evaluates source nor guesses
                # the return from one branch of the helper's body.
                assigned: dict[str, bool] = {}
                local_names(guess_scope(f), assigned)
                args = e.kids[1:]
                if c in f.params or c in assigned or len(args) > len(helper.params) or (helper.npos >= 0 and len(args) > helper.npos):
                    return ""
                ts: list[str] = []
                for i in range(len(helper.params)):
                    if i < len(args):
                        arg = args[i]
                        if arg.kind == "kw" or arg.kind == "starred" or arg.kind == "dstar":
                            return ""
                        t = "None" if arg.kind == "None" else self.guess(arg, f)
                    elif helper.defaults[i].kind == "noann":
                        return ""
                    else:
                        t = helper.dtypes[i]
                        if t == "":
                            t = "None" if helper.defaults[i].kind == "None" else self.guess(helper.defaults[i], FnInfo("", "", helper.node, ""))
                    if t == "" or t.startswith("!"):
                        return ""
                    target = helper.ptypes[i]
                    if target != "" and t != target:
                        if not self.widens(t, target) and not (is_sopt(target) and t == unopt(target)):
                            return ""
                        t = target
                    ts.append(t)
                return self.instance(helper, ts, []).ret
            return helper.ret
        if c == "str" or c == "int" or c == "float" or c == "bool":
            return c
        if c == "range" and RANGEC in self.classes and not self.bound(c):
            return RANGEC  # (where it is a value)
        if c == "len" or c == "ord":
            return "int"
        if c == "input" or c == "repr" or c == "chr" or c == "ascii" or c == "hex" or c == "oct" or c == "bin":
            return "str"
        if c == "open":
            return "file"
        if c == "iter" and len(e.kids) == 2 and not self.bound(c) and self.compiling:
            return self.guess_iter(e.kids[1], f)
        if c == "next" and (len(e.kids) == 2 or len(e.kids) == 3) and not self.bound(c) and self.compiling:
            # (what the iterator's __next__ returns, or a file's line; with a default, both's)
            t = unopt(self.guess(e.kids[1], f))
            r = "str" if t == "file" else self.next_type(t) if self.is_iterator(t) else gelem(t) if is_gen(t) else ""
            return r if r == "" or len(e.kids) == 2 else self.join(r, self.guess(e.kids[2], f))
    if k == "call" and e.kids[0].kind == "attr" and e.kids[0].kids[0].kind == "name" and e.kids[0].kids[0].s in self.classes:
        ms = self.classes[e.kids[0].kids[0].s].methods  # C.m(...): a static or class method
        return ms[e.kids[0].s].ret if e.kids[0].s in ms and ms[e.kids[0].s].deco != "" else ""
    if k == "cmp" or (k == "unary" and e.s == "not"):
        return "bool"
    if k == "ifexp":
        return self.guess(e.kids[1], f)
    if k == "walrus":
        return self.guess(e.kids[0], f)
    if k == "list" and len(e.kids) > 0:
        t = self.guess(e.kids[0], f)
        return self.ctype("list", [t]) if t != "" and not t.startswith("!") else t
    if k == "tuple" and 0 < len(e.kids) <= 9:
        ts = [self.guess(x, f) for x in e.kids if x.kind != "starred"]
        bad = [t for t in ts if t.startswith("!")]
        if len(bad) > 0:
            return bad[0]
        return self.ctype("tuple", ts) if "" not in ts and len(ts) == len(e.kids) else ""
    if k == "dict" and len(e.kids) > 0 and len(e.kids) % 2 == 0:
        kt = self.guess(e.kids[0], f)
        vt = self.guess(e.kids[1], f)
        if kt.startswith("!") or vt.startswith("!"):
            return kt if kt.startswith("!") else vt
        return self.ctype("dict", [kt, vt]) if kt != "" and vt != "" and self.key_problem(kt) == "" else ""
    if k == "call" and e.kids[0].kind == "name" and (e.kids[0].s == "list" or e.kids[0].s == "sorted") and len(e.kids) == 2 and not self.bound(e.kids[0].s):
        # list(range(n)), list(xs), sorted(xs): a list of the items
        arg = e.kids[1]
        if arg.kind == "call" and arg.kids[0].kind == "name" and arg.kids[0].s == "range" and not self.bound("range"):
            return "list[int]"
        t = self.guess(arg, f)
        return t if is_list(t) or t.startswith("!") else "list[int]" if t == RANGEC else ""
    if k == "binop":
        a = self.guess(e.kids[0], f)
        b = self.guess(e.kids[1], f)
        if self.isnum(a) and self.isnum(b):
            if e.s == "/" or a == "float" or b == "float":
                return "float"
            return "bool" if a == "bool" and b == "bool" and e.s in IOPS else "int"
        if a == b and (a == "str" or is_list(a)):
            return a
        if e.s == "+" and a.startswith("tuple[") and b.startswith("tuple["):
            return self.ctype("tuple", targs(a) + targs(b))
        if e.s == "*" and (is_list(a) or a == "str") and (b == "int" or b == "bool"):
            return a  # [n] * n
        if e.s == "*" and (is_list(b) or b == "str") and (a == "int" or a == "bool"):
            return b
    return ""

def gen_guess_iter(self, a: Node, f: FnInfo) -> str:
    # the type of iter(a) (guess, see iter_): a file itself, an object's iterator object, or the
    # specialization of lib/_pystachy_iterators.py's class for a builtin container
    if a.kind == "call" and a.kids[0].kind == "name" and a.kids[0].s == "range" and not self.bound("range"):
        c = ITERS + "$range_iterator"
        return self.specialize(c, ["int", "int", "int"], {}, False, {}) if c in self.tmpl else ""
    m = a.kids[0].s if a.kind == "call" and len(a.kids) == 1 and a.kids[0].kind == "attr" else ""
    t = unopt(self.guess(a.kids[0].kids[0] if m == "keys" or m == "values" or m == "items" else a, f))
    name = ""
    if t.startswith("!") or t == "file" or is_gen(t):
        return t
    if t == RANGEC and m == "":
        c = ITERS + "$range_iterator"
        return self.specialize(c, ["int", "int", "int"], {}, False, {}) if c in self.tmpl else ""
    if is_dict(t) and (m == "keys" or m == "values" or m == "items"):
        name = "dict_keyiterator" if m == "keys" else "dict_valueiterator" if m == "values" else "dict_itemiterator"
    elif m == "keys" or m == "values" or m == "items":
        return ""
    elif t in self.classes and t not in self.nts and "__iter__" in self.classes[t].methods:
        it = self.classes[t].methods["__iter__"]
        if it.iters and it.bad == "":
            name = "list_iterator"
            t = it.ret
        else:
            r = self.instance(it, [t], []).ret if it.bad == "" and it.generic and it.ret == "" else it.ret
            return r if it.bad == "" and (self.is_iterator(r) or is_gen(r)) else ""
    elif is_list(t):
        name = "list_iterator"
    elif t == "str":
        name = "str_ascii_iterator"
    elif is_tuple(t) and t != "tuple[]" and len([x for x in targs(t) if x != targs(t)[0]]) == 0:
        name = "tuple_iterator"
        t = self.ctype("list", [targs(t)[0]])
    elif is_dict(t):
        name = "dict_keyiterator"
    elif is_set(t):
        name = "set_iterator"
    c = ITERS + "$" + name
    return self.specialize(c, [t], {}, False, {}) if name != "" and c in self.tmpl else ""

def gen_field(self, o: Val, name: str, store: bool = False) -> Val:
    if o.t == "exctype":
        self.err(f"the attributes of the class of an exception (type[BaseException]) other than __name__ are not supported (.{name})")
    if name == "__class__" and (o.t == "exc" or (o.t in self.classes and self.classes[o.t].exc != "")):
        self.err("e.__class__ of an exception is not supported; type(e).__name__ is")
    if o.t == "exc":
        # (isinstance() does not change the type of the name an except clause binds)
        fl = [c for c in self.classes.values() if c.exc != "" and name in c.ftypes]
        hint = f" (to read the fields of {short(fl[0].name)}, catch it by its class: except {short(fl[0].name)} as e)" if len(fl) > 0 else ""
        self.err(f"the attributes of an exception (e.{name}) are not supported; str(e) and repr(e) are{hint}")
    if o.t not in self.classes:
        t = unopt(o.t)
        base = "list" if is_list(t) else "dict" if is_dict(t) else "int" if t == "bool" else t
        if base + "." + name in METHODS:
            self.err(f"{tname(t)}.{name} is a method: call it, {name}(...) (methods are not values)")
        if t == "str" and (name == "format" or name == "format_map"):
            self.err(f'str.{name} is a method: call it on a string literal, "...".{name}(...) (methods are not values; map() takes "...".{name})')
        self.err(f"type {typestr(o.t)} has no attribute '{name}'")
    ci = self.classes[o.t]
    if o.t == RANGEC and self.curfn.mod != RANGES and name not in ci.ftypes:
        # (CPython's range has no other attributes, and its methods cannot be assigned)
        self.err(f"'range' object attribute '{name}' is read-only" if store and name in ci.methods else f"'range' object has no attribute '{name}'" + (" and no __dict__ for setting new attributes" if store else ""))
    if name in ci.methods and ci.methods[name].prop:
        self.err(f"property '{name}' of '{short(o.t)}' is read-only")
    if store and ci.slotlimit and name not in ci.slots:
        self.err(f"field '{name}' is outside __slots__ of '{short(ci.name)}'")
    if name not in ci.ftypes:
        if name in ci.methods:
            self.err(f"{shown(o.t)}.{name} is a method: call it, {name}(...) (methods are not values)")
        if ci.exc != "":
            sub = [c for c in self.classes.values() if c.name != o.t and name in c.ftypes and self.derives(c.name, o.t)]
            if len(sub) > 0:
                self.err(f"'{short(o.t)}' object has no attribute '{name}' (it is a field of {short(sub[0].name)}, which derives from {short(o.t)}: isinstance() does not change the type of a value)")
            for b in EXCATTRS:
                if name in EXCATTRS[b].split() and exc_derives(ci.exc, b):
                    self.err(f"'{short(o.t)}' object has no attribute '{name}': {b}'s attribute {name} is not supported (str(e) and repr(e) are)")
            for b in EXCINIT:
                if name in EXCINIT[b].split() and exc_derives(ci.exc, b):
                    self.err(f"'{short(o.t)}' object has no attribute '{name}': {b}'s attribute {name} is not supported (a field of the class assigned in __init__, after super().__init__(...), is)")
            self.err(f"'{short(o.t)}' object has no attribute '{name}' (of an exception object, only the fields of its class are supported; str(e) and repr(e) are)")
        if o.t in self.nts and name == "__doc__":
            self.err(f"reading the __doc__ of NamedTuple {short(o.t)} is not supported (Pystachy keeps no docstrings of classes)")
        self.err(f"'{shown(o.t)}' object has no attribute '{name}'")
    extra = " and no __dict__ for setting new attributes" if store else ""
    self.notnone(o, f"AttributeError: 'NoneType' object has no attribute '{name}'{extra}")
    if name == "__slots__" and name not in ci.fpos:
        if store:
            self.err("rebinding __slots__ through an instance is not supported")
        self.class_default(ci, name)
        return Val(ci.fglob[name], ci.ftypes[name])
    return Val(self.fgep(o, ci.fpos[name]), ci.ftypes[name])

def gen_fn_attr_read(self, o: Val, name: str) -> None:
    # o.name read through object o, where its class binds name to a function in its body
    # (name = f): CPython binds o to the function's first parameter there, as for a method, which
    # is not supported. A builtin function (fn[b:...]) or a bound method that a class attribute
    # holds is read as itself through an object, as in CPython, and so is a function of a
    # stand-in for a C module (STANDINS: encodings.utf_8's _buffer_decode = codecs.utf_8_decode),
    # which is CPython's builtin
    ci = self.classes[o.t]
    t = ci.ftypes.get(name, "")
    if t.startswith("fn[f:") and owner(t[5:-1]) in STANDINS:
        return
    if name in ci.fdefault and (t.startswith("fn[f:") or t.startswith("fn[c:") or t.startswith("fn[u:")):
        self.err(f"class attribute '{name}' of '{short(o.t)}' holds a function ({name} = ...): reading it through an object is not supported (CPython binds the object to the function's first parameter, as for a method); read it through the class ({short(o.t)}.{name}), or define {name} with def")


def gen_fgep(self, o: Val, i: int) -> str:
    # Keep the declared object layout and member type until lowering. The address
    # remains in IFn.fa so native and machine memory operations have identical effects.
    ci = self.classes[o.t]
    t = ci.ftypes[ci.fields[i]] if i < len(ci.fields) else "bool"
    op = Ins("field.addr", "*" + t, "")
    op.k = i
    op.a = [o]
    self.put(op, 1)
    r = f"%t{op.r[0]}"
    self.fn.fa[r] = True
    return r

def gen_getfield(self, o: Val, p: Val, name: str) -> Val:
    # load a field (p = self.field(o, name)); a field __init__ may leave unassigned is checked
    ci = self.classes[o.t]
    r = ""
    bad = ""
    if name == "__slots__" and name not in ci.fpos:
        if ci.exc != "":
            # Exceptions use their runtime class identity rather than ordinary
            # object tags. Do not silently read the static base's metadata.
            for sub in self.classes.values():
                if sub.name != ci.name and self.derives(sub.name, ci.name) and name in sub.fdefault and self.default_home(sub, name) is not self.default_home(ci, name):
                    self.err(f"reading __slots__ through exception base {short(ci.name)} is not supported when a subclass overrides it; read it through the concrete class")
        r = self.mem_load(Val(p.v, "*" + p.t)).v
        if ci.tag != 0:
            tag = self.mem_load(Val(self.fgep(o, ci.fpos[" class"]), "*int")).v
            for sub in self.classes.values():
                if sub.tag != 0 and sub.name != ci.name and self.derives(sub.name, ci.name) and name in sub.fdefault:
                    if sub.ftypes[name] != p.t:
                        self.err(f"reading __slots__ through {short(ci.name)} is not supported when subclasses use different declaration types; read it through the concrete class")
                    self.class_default(sub, name)
                    dv = self.mem_load(Val(sub.fglob[name], "*" + p.t))
                    r = self.select(self.num_cmp("==", Val(tag, "int"), Val(str(sub.tag), "int")).v, dv, Val(r, p.t))
        return Val(r, p.t)
    if o.t + "." + name in self.cvars:
        # a class variable: the object's own value once it has assigned one, else the class's
        own = self.mem_load(Val(self.fgep(o, ci.fflag[name]), "*bool")).v
        fv = self.mem_load(Val(p.v, "*" + p.t))
        if ci.tag != 0:
            # Each concrete class may shadow its base's class attribute. All related
            # mutable defaults share the inherited instance-assignment flag, but their
            # fallback globals still belong to the classes that define those defaults.
            tag = self.mem_load(Val(self.fgep(o, ci.fpos[" class"]), "*int")).v
            cv = fv
            assigned = own
            for sub in self.classes.values():
                if sub.tag != 0 and self.derives(sub.name, ci.name) and name in sub.fdefault:
                    match = self.num_cmp('==', Val(tag, "int"), Val(str(sub.tag), "int")).v
                    if sub.name + "." + name in self.cvars or not is_const(sub.fdefault[name]):
                        self.class_default(sub, name)
                        dv = self.mem_load(Val(sub.fglob[name], "*" + p.t))
                    else:
                        dv = self.coerce(self.expr(sub.fdefault[name], p.t), p.t)
                    cv = Val(self.select(match, dv, cv), p.t)
                    assigned = self.scalar('or', [Val(assigned, 'bool'), Val(match, 'bool')])
            bad = self.scalar('xor', [Val(assigned, 'bool'), Val('true', 'bool')])
            r = self.select(own, fv, cv)
        else:
            self.class_default(ci, name)
            r = self.select(own, fv, self.mem_load(Val(ci.fglob[name], "*" + p.t)))
            if is_opt(p.t) or is_union(p.t):
                self.wide[self.curfn.ll + r] = True  # (not narrowed, see coerce)
            return Val(r, p.t)
    if name in ci.fflag and name not in ci.fsure:
        f = self.fgep(o, ci.fflag[name])
        if bad == "":
            bad = self.scalar('xor', [Val(self.mem_load(Val(f, '*bool')).v, 'bool'), Val('true', 'bool')])
        subs = [x for x in self.classes.values() if x.base == o.t]
        if len(subs) > 0 and (ci.exc != "" or ci.tag != 0):
            # CPython's missing-attribute error names the concrete object's class.
            l1 = self.label()
            l2 = self.label()
            self.cbr(bad, l1, l2)
            self.place(l1)
            if ci.exc != "":
                c = self.rt("pys_exc_cls", "ptr", [f"ptr {o.v}"])
            else:
                tag = self.mem_load(Val(self.fgep(o, ci.fpos[" class"]), "*int")).v
                c = self.sconst(short(ci.name))
                for sub in self.classes.values():
                    if sub.tag != 0 and sub.name != ci.name and self.derives(sub.name, ci.name):
                        match = self.num_cmp('==', Val(tag, "int"), Val(str(sub.tag), "int")).v
                        c = self.select(match, Val(self.sconst(short(sub.name)), "str"), Val(c, "str"))
            q = self.sconst("'")
            t = self.sconst("' object has no attribute '" + name + "'")
            m = self.rt("pys_str_add", "ptr", [f"ptr {q}", f"ptr {c}"])
            m = self.rt("pys_str_add", "ptr", [f"ptr {m}", f"ptr {t}"])
            self.raise_("AttributeError", m)
            self.place(l2)
        else:
            self.guard(bad, f"AttributeError: '{tname(o.t)}' object has no attribute '{name}'")
    if r == "":
        r = self.mem_load(Val(p.v, "*" + p.t)).v
    if is_opt(p.t) or is_union(p.t):
        self.wide[self.curfn.ll + r] = True  # (not narrowed, see coerce)
    return Val(r, p.t)

def gen_setfield(self, o: Val, p: Val, name: str, v: Val) -> None:
    ci = self.classes[o.t]
    what = f"the value assigned to field '{name}' ({typestr(p.t)})" if is_opt(v.t) else ""
    self.mem_store(Val(p.v, "*" + p.t), self.coerce(v, p.t, what))
    if name in ci.fflag:
        self.mem_store(Val(self.fgep(o, ci.fflag[name]), "*bool"), Val("true", "bool"))

def gen_is_prop(self, t: str, name: str) -> bool:
    # is attribute name of objects of type t a property (of the class or its specialization's template)
    if t not in self.classes:
        return False
    ci = self.classes[t]
    ms = self.classes[ci.origin].methods if ci.origin != "" else ci.methods
    return name in ms and ms[name].prop

def gen_prop_store(self, o: Val, name: str, v: Val | None) -> None:
    # o.name = v, or del o.name (v None), of a property: its setter (deleter), selected by the
    # object's class as a method call is; a class whose property has none raises CPython's
    # AttributeError, which names the object's class
    kind = "deleter" if v is None else "setter"
    key = name + "." + kind
    none = f"AttributeError: 'NoneType' object has no attribute '{name}' and no __dict__ for setting new attributes"
    args: list[Node] = []
    if v is not None:
        args.append(self.vnode(v))
    if self.frozen_store(o, name, v is None):
        return  # (a frozen dataclass's __setattr__ raises first)
    ci = self.classes[o.t]
    cs = [c for c in self.classes.values() if c.tag > 0 and self.derives(c.name, o.t)] if ci.tag > 0 else [ci]
    if len([c for c in cs if key not in c.methods]) == 0:
        self.call_fn(ci.methods[key], [o], args, none=none)
        return
    self.notnone(o, none)
    tag = self.mload('int', o.v) if len(cs) > 1 else ""
    end = self.label()
    reached = False
    narrow = dict(self.narrowed)
    for i in range(len(cs)):
        c = cs[i]
        nxt = self.label() if i + 1 < len(cs) else ""
        if nxt != "":
            arm = self.label()
            self.cbr(self.num_cmp('==', Val(tag, "int"), Val(str(c.tag), "int")).v, arm, nxt)
            self.place(arm)
        self.narrowed = dict(narrow)
        if key in c.methods:
            self.call_fn(c.methods[key], [Val(o.v, c.name)], args, direct=True)
        else:
            self.raise_("AttributeError", self.sconst(f"property '{name}' of '{short(c.name)}' object has no {kind}"))
        if not self.term:
            reached = True
            self.br(end)
        if nxt != "":
            self.place(nxt)
    self.narrowed = narrow
    if reached:
        self.place(end)

# ---- variables
