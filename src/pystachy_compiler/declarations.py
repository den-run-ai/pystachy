"""Declarations component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.analysis import calls_init, local_names
from src.pystachy_compiler.diagnostics import shown
from src.pystachy_compiler.ir import ClassInfo, FnInfo, Val
from src.pystachy_compiler.module import Mod
from src.pystachy_compiler.names import short
from src.pystachy_compiler.specs import (
    CLASSVAR,
    CTYPES,
    EXCATTRS,
    EXCFIELDS,
    EXCINIT,
    IOPS,
    METHODS,
    MODFUNCS,
    OPTTYPES,
    PATHLIKE,
    PYBUILTINS,
    STUB,
    TYPEVAR,
    TYPE_SIZE,
    TYPING,
    UNARY,
    UNCALLED,
    UNSUPPORTED,
    exc_derives,
    is_excname,
)
from src.pystachy_compiler.syntax import Node, has_kind, mentions, mk
from src.pystachy_compiler.utils import (
    clone,
    elem,
    elem_problem,
    is_callable,
    is_const,
    is_dict,
    is_fset,
    is_list,
    is_opt,
    is_set,
    is_sopt,
    is_tuple,
    key_problem,
    lt,
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
    return base + "[" + ",".join(ts) + "]"

def gen_none_items(self, t: str) -> str:
    # A tuple key with str | None in place of each None item.
    if t == "None":
        return "opt[str]"
    return self.ctype("tuple", [self.none_items(x) for x in targs(t)]) if is_tuple(t) else t

def gen_subst(self, t: str, T: str, K: str, V: str, S: str) -> str:
    # Instantiate a builtin method's type without allocating an oversized replacement.
    if t == "T":
        return T
    if t == "S":
        return S
    if len(t) + t.count("K") * (len(K) - 1) > TYPE_SIZE:
        self.err(f"type representation exceeds {TYPE_SIZE} bytes; simplify the type or annotate template parameters")
    t = t.replace("K", K)
    if len(t) + t.count("V") * (len(V) - 1) > TYPE_SIZE:
        self.err(f"type representation exceeds {TYPE_SIZE} bytes; simplify the type or annotate template parameters")
    return t.replace("V", V)

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
    if k == "name":
        if s in self.tmpl and self.selfcls in self.classes and self.classes[self.selfcls].origin == s:
            return self.selfcls  # (in its specialization's methods and fields: that specialization, as Self)
        if s in self.tmpl:
            return f"!class {shown(s)} is a class template (its __init__ takes a parameter without an annotation): each call makes an object of a specialization of its own, which an annotation cannot name here; leave the annotation out"
        if s == "int" or s == "float" or s == "bool" or s == "str" or s in self.classes:
            return s
        if self.imported(s).startswith("ffi.") and self.imported(s)[4:] in CTYPES:
            return "int"  # (a C integer type, in an @extern function's signature: see CTYPES)
        if self.imported(s) == "ffi.c_buf":
            return "str"  # (a str's UTF-8 bytes, NULs and all, for a C function that takes their length too)
        if is_excname(s):
            return "exc"  # (a builtin exception class: any exception, not only those of the class)
        t = self.typing_name(s)
        if t == "TextIO" or t == "Self" or t.startswith("!"):
            return "file" if t == "TextIO" else self.self_type() if t == "Self" else t
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
    elif k == "binop" and n.s == "|" and self.has_path(n):
        return self.path_union(self.union_members(n, []))
    elif k == "binop" and n.s == "|" and n.kids[1].kind == "None":
        return self.opt(self.ann(n.kids[0]), n.kids[0])
    elif k == "binop" and n.s == "|" and n.kids[0].kind == "None":
        return self.opt(self.ann(n.kids[1]), n.kids[1])  # None | T
    elif k == "index" and (n.kids[0].kind == "name" or n.kids[0].kind == "attr"):
        base = self.ann_base(n.kids[0])
        if base.startswith("!"):
            return base
        a: list[Node] = n.kids[1].kids if n.kids[1].kind == "tuple" else [n.kids[1]]
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
        ts: list[str] = self.ann_items(a) if base == "tuple" else [self.ann(x) for x in a]
        for t in ts:
            if t.startswith("!"):
                return t
        if base == "list" and len(ts) == 1:
            return self.ctype("list", [ts[0]])
        if base == "dict" and len(ts) == 2:
            return self.ctype("dict", ts) if key_problem(ts[0]) == "" else "!" + key_problem(ts[0])
        if (base == "set" or base == "frozenset") and len(ts) == 1:
            return self.ctype(base, ts) if elem_problem(ts[0]) == "" else "!" + elem_problem(ts[0])
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
            if v.kind == "int" or v.kind == "float" or v.kind == "str":
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
        c = short(x.s) if x.kind == "name" or x.kind == "attr" else "Exception"
        return f"!an exception that may be None ({c} | None) is not supported: only an object of an exception class of the program may be None"
    r = self.optional(t)
    return r if r != "" else f"!None/Optional is only supported for {OPTTYPES}, not {typestr(t)}"

def gen_optional(self, t: str) -> str:
    # the type of a value that is a t or None, "" if there is none
    if t in self.classes or is_opt(t):
        return t
    if (t == "str" or self.isnum(t) or is_list(t) or is_dict(t) or is_set(t) or is_tuple(t) or is_callable(t)) and "?" not in t:
        return self.ctype("opt", [t])
    return ""

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
    if b in self.classes:
        return a == "None" or (a in self.classes and self.derives(a, b))
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
    deco = short(deco)
    if deco != "" and f.deco == "" and not self.lib and not f.extern and not f.pyexport:
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
    if len(d.kids) > 3 and f.deco == "" and not f.extern and not f.pyexport:
        bad = f"unsupported decorator @{deco}" if deco != "" else "async functions are not supported"
        bad = STUB.replace("NAME", short(d.s)) if stub else bad
    if f.deco != "" and d.s.startswith("__") and d.s.endswith("__"):
        bad = f"@{f.deco} on the special method {d.s} is not supported"
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
    if not inherited and bad == "" and has_kind(d.kids[2], "yield"):
        bad = UNSUPPORTED["yield"]  # a generator function
        if cls != "" and d.s == "__iter__":
            bad += ": __iter__ can return iter(xs) of a list xs of the items"
    tret = d.kids[1].kind != "noann" and f.generic and self.tmpl_ann(d.kids[1]) and not (cls in self.classes and self.classes[cls].origin != "" and not template_ok(d.s))
    if bad == "" and self.lib and d.kids[1].kind != "noann" and not tret:
        it = self.iter_item(d.kids[1]) if cls != "" and d.s == "__iter__" else None  # (see iter_ann)
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
    elif d.kids[1].kind != "noann" and cls != "" and d.s == "__iter__" and self.iter_ann(d.kids[1]) != "":
        f.ret = self.iter_ann(d.kids[1])
        f.iters = True
    elif tret:
        f.ret = ""  # (-> Box: decided by its first return, as an unannotated one is)
    elif d.kids[1].kind != "noann":
        f.ret = self.typeof(d.kids[1])
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
    # an __iter__'s return annotation Iterator[T] or Iterable[T] (typing's or collections.abc's):
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
    if ci.base in self.classes:
        # an exception class's objects begin with its base's fields (and their flags, see fl_fields)
        b = self.classes[ci.base]
        for x in b.fields:
            self.add_field(ci, x, b.ftypes[x])
            if x in b.fdefault:
                ci.fdefault[x] = b.fdefault[x]
    elif ci.tag != 0:
        self.add_field(ci, " class", "int")
    elif ci.exc != "":
        # what its constructor sets (exc_object): its ExcClass, str(e) and the text between repr(e)'s
        # parentheses, and a SystemExit's status and whether its code is one (None, an int or a bool)
        xs = EXCFIELDS.split()
        for x in xs if exc_derives(ci.exc, "SystemExit") else xs[:3]:
            self.add_field(ci, " " + x[: x.find(":")], x[x.find(":") + 1 :])
    for st in ci.node.kids[0].kids:
        self.line = st.line
        if st.kind == "annassign" and st.kids[0].kind == "name" and ci.base in self.classes and st.kids[0].s in self.classes[ci.base].ftypes:
            # (a class attribute of the base bound again, with the same type: as x = v is)
            b = self.classes[ci.base]
            if len(st.kids) < 3 or st.kids[0].s not in b.fdefault or self.vtype(st.kids[1]) != b.ftypes[st.kids[0].s]:
                self.err(f"field '{st.kids[0].s}' of '{short(ci.base)}' declared again in '{short(ci.name)}' (not supported" + (", but for a class attribute of the same type" if st.kids[0].s in b.fdefault else "") + ")")
        if st.kind == "annassign" and st.kids[0].kind == "name" and ci.mod != "" and self.ann_problem(st.kids[1], False) != "":
            # an imported module's class: an error only where the program uses it
            ci.bad = ci.bad if ci.bad != "" else f"class {shown(ci.name)} is not supported: {self.ann_problem(st.kids[1], False)}"
            self.add_field(ci, st.kids[0].s, "int")
        elif st.kind == "annassign" and st.kids[0].kind == "name":
            self.add_field(ci, st.kids[0].s, self.vtype(st.kids[1]))
            if len(st.kids) == 3:
                ci.fdefault[st.kids[0].s] = st.kids[2]
                last = st.kids[0].s
            elif last != "" and ci.name in self.nts:
                self.err(f"Non-default namedtuple field {st.kids[0].s} cannot follow default field {last}")
            elif last != "" and self.is_dc(ci.name) and not ci.kwonly:
                self.err(f"non-default argument '{st.kids[0].s}' follows default argument '{last}'")
        elif st.kind == "assign" and len(st.kids) == 2 and st.kids[0].kind == "name" and self.is_dc(ci.name):
            self.err(f"a class attribute without an annotation ({st.kids[0].s} = ...), which is no field of a {'NamedTuple' if ci.name in self.nts else 'dataclass'}, is not supported: annotate it")
        elif st.kind == "assign" and len(st.kids) == 2 and st.kids[0].kind == "name":
            # x = v: a class attribute, typed by v as a field is (and from here on read as x: T = v)
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
    if ci.name in self.nts:
        self.nt_class(ci)
    if self.is_dc(ci.name):
        self.dc_methods(ci)
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
    if "__init__" not in ci.methods and ci.base in self.classes and "__init__" in self.classes[ci.base].methods:
        # A base with no explicit initializer acquired its empty one while its fields were
        # declared, after inherit() copied its other methods.
        ci.methods["__init__"] = self.classes[ci.base].methods["__init__"]
    if "__init__" in ci.methods or ci.exc != "":
        # (an exception class without __init__ of its own takes its base's, or none)
        if "__init__" in ci.methods and ci.methods["__init__"].cls == ci.name and ci.name not in self.tmpl:
            f = ci.methods["__init__"]
            self.scan_fields(ci, f, f.node.kids[2].kids)
    if ci.tag > 0:
        for name in ci.ftypes:
            if name in ci.methods:
                self.line = ci.node.line
                owner = short(ci.methods[name].cls)
                self.err(f"field '{name}' of '{short(ci.name)}' conflicts with method '{owner}.{name}': method and field shadowing in an inheritance hierarchy is not supported")
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
    if self.is_dc(ci.name):
        if ci.kwonly:
            f.npos = 1  # (self, and the fields by keyword)
        for fl in ci.fields:
            f.params.append(fl)
            f.ptypes.append(ci.ftypes[fl])
            f.defaults.append(ci.fdefault[fl] if fl in ci.fdefault else noann)
            f.dglob.append("")
            body.append(mk("assign", "", d.line, [mk("attr", fl, d.line, [mk("name", me, d.line, [])]), mk("name", fl, d.line, [])]))
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

def gen_frozen(self, t: str, name: str) -> None:
    # a NamedTuple's fields are assigned only by its __init__
    if t in self.nts and not (self.curfn.name == "__init__" and self.curfn.cls == t):
        self.err(f"cannot assign to field '{name}' of NamedTuple {short(t)} (AttributeError: can't set attribute); make a new one with _replace({name}=...)")

def gen_synth(self, ci: ClassInfo, name: str, ret: str, body: list[Node]) -> None:
    # a method the compiler writes for a dataclass, generated only if the program calls it
    line = ci.node.line
    noann = mk("noann", "", line, [])
    f = FnInfo(name, f"@m.{ci.name}.{name}", mk("def", name, line, [noann, noann, mk("block", "", line, body)]), ci.name)
    f.params.append("self")
    f.ptypes.append(ci.name)
    if name == "__eq__":
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
    # @dataclass: __repr__ is Name(field=repr(value), ...), __eq__ compares the fields in order
    line = ci.node.line
    me = mk("name", "self", line, [])
    other = mk("name", "other", line, [])
    if "__repr__" not in ci.methods:
        parts: list[Node] = []
        lit = short(ci.name) + "("
        for i in range(len(ci.fields)):
            parts.append(mk("str", lit + (", " if i > 0 else "") + ci.fields[i] + "=", line, []))
            parts.append(mk("call", "", line, [mk("name", "__pys_repr", line, []), mk("attr", ci.fields[i], line, [me])]))
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
    if "__eq__" not in ci.methods and ci.name not in self.nts:  # (a NamedTuple's is tuple's, see ntop)
        test = mk("True", "", line, [])
        for i in range(len(ci.fields)):
            c = mk("cmp", "==", line, [mk("attr", ci.fields[i], line, [me]), mk("attr", ci.fields[i], line, [other])])
            test = c if i == 0 else mk("boolop", "and", line, [test, c])
        same = mk("cmp", "is", line, [other, me])
        yes = mk("block", "", line, [mk("return", "", line, [mk("True", "", line, [])])])
        isnone = mk("cmp", "is", line, [other, mk("None", "", line, [])])
        no = mk("block", "", line, [mk("return", "", line, [mk("False", "", line, [])])])
        self.synth(ci, "__eq__", "bool", [mk("if", "", line, [same, yes, mk("block", "", line, [])]),
                                        mk("if", "", line, [isnone, no, mk("block", "", line, [])]), mk("return", "", line, [test])])

def gen_scan_fields(self, ci: ClassInfo, f: FnInfo, body: list[Node]) -> None:
    # fields are the attributes assigned on self inside __init__
    for st in body:
        self.line = st.line
        k = st.kind
        if (k == "assign" or k == "annassign") and st.kids[0].kind == "attr" and st.kids[0].kids[0].kind == "name" and st.kids[0].kids[0].s == f.params[0]:
            name = st.kids[0].s
            if name not in ci.ftypes:
                self.exc_attr(ci, name)
                why = self.ann_problem(st.kids[1], False) if k == "annassign" and ci.mod != "" else ""
                t = "" if why != "" else self.vtype(st.kids[1]) if k == "annassign" else self.guess(st.kids[-1], f)
                if t.startswith("!"):
                    why = t[1:]  # (a call of a function Pystachy cannot compile: its error)
                t = "" if t == "None" or why != "" else t  # (f() that returns None: a field has a value type)
                if t == "" and why == "":
                    why = f"cannot infer the type of field '{name}'; annotate it (self.{name}: T = ...)"
                if t == "" and ci.mod == "":
                    self.err(why)
                if t == "":
                    # an imported module's class: an error only where the program uses it
                    ci.bad = ci.bad if ci.bad != "" else f"class {shown(ci.name)} is not supported: {why}"
                    t = "int"
                self.add_field(ci, name, t)
        for kid in st.kids:
            if kid.kind == "block":
                self.scan_fields(ci, f, kid.kids)
            elif kid.kind == "except":
                self.scan_fields(ci, f, kid.kids[1].kids)

def gen_guess_args(self, init: FnInfo, args: list[Node], f: FnInfo) -> list[str]:
    # the types of the arguments (but self) that the call of class template __init__ init with
    # args passes, as guess infers them ([] for none); ["!"] where it cannot (a keyword or
    # star argument, *args, a type it cannot infer)
    ts: list[str] = []
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

def gen_guess(self, e: Node, f: FnInfo) -> str:
    k = e.kind
    if k == "int" or k == "float" or k == "str":
        return k
    if k == "True" or k == "False":
        return "bool"
    if k == "fstr":
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
        local_names(f.node.kids[2].kids, asg)
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
        local_names(f.node.kids[2].kids, asg)
        if root.s not in asg:
            return f"fn[b:{p}]"
    # self.k, self.m(...) and self(...) before the names below: self shadows a function, class,
    # import or builtin of its name
    me = f.params[0] if takes_self(f) else ""
    if k == "attr" and e.kids[0].kind == "name" and e.kids[0].s == me:
        ci = self.classes[f.cls]
        if e.s not in ci.ftypes and e.s in ci.methods and ci.methods[e.s].deco == "":
            return f"fn[m:{f.cls}.{e.s}]"  # (self.m: the method bound to the object)
        return ci.ftypes.get(e.s, "")
    if k == "call" and e.kids[0].kind == "attr" and e.kids[0].kids[0].kind == "name" and e.kids[0].kids[0].s == me:
        ms = self.classes[f.cls].methods
        m = e.kids[0].s
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
            return self.specialize(c, ts) if "!" not in ts else ""
        if c in self.classes or c in self.unsupported:
            return c if c in self.classes else "!" + self.unsupported[c]
        if c in self.funcs:
            return self.funcs[c].ret if self.funcs[c].bad == "" else "!" + self.funcs[c].bad
        if c == "str" or c == "int" or c == "float" or c == "bool":
            return c
        if c == "len" or c == "ord":
            return "int"
        if c == "input" or c == "repr" or c == "chr" or c == "ascii" or c == "hex" or c == "oct" or c == "bin":
            return "str"
        if c == "open":
            return "file"
    if k == "call" and e.kids[0].kind == "attr" and e.kids[0].kids[0].kind == "name" and e.kids[0].kids[0].s in self.classes:
        ms = self.classes[e.kids[0].kids[0].s].methods  # C.m(...): a static or class method
        return ms[e.kids[0].s].ret if e.kids[0].s in ms and ms[e.kids[0].s].deco != "" else ""
    if k == "cmp" or (k == "unary" and e.s == "not"):
        return "bool"
    if k == "ifexp":
        return self.guess(e.kids[1], f)
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
        return self.ctype("dict", [kt, vt]) if kt != "" and vt != "" and key_problem(kt) == "" else ""
    if k == "call" and e.kids[0].kind == "name" and (e.kids[0].s == "list" or e.kids[0].s == "sorted") and len(e.kids) == 2 and not self.bound(e.kids[0].s):
        # list(range(n)), list(xs), sorted(xs): a list of the items
        arg = e.kids[1]
        if arg.kind == "call" and arg.kids[0].kind == "name" and arg.kids[0].s == "range" and not self.bound("range"):
            return "list[int]"
        t = self.guess(arg, f)
        return t if is_list(t) or t.startswith("!") else ""
    if k == "binop":
        a = self.guess(e.kids[0], f)
        b = self.guess(e.kids[1], f)
        if self.isnum(a) and self.isnum(b):
            if e.s == "/" or a == "float" or b == "float":
                return "float"
            return "bool" if a == "bool" and b == "bool" and e.s in IOPS else "int"
        if a == b and (a == "str" or is_list(a)):
            return a
        if e.s == "*" and (is_list(a) or a == "str") and (b == "int" or b == "bool"):
            return a  # [n] * n
        if e.s == "*" and (is_list(b) or b == "str") and (a == "int" or a == "bool"):
            return b
    return ""

def gen_field(self, o: Val, name: str, store: bool = False) -> Val:
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
        self.err(f"type {typestr(o.t)} has no attribute '{name}'")
    ci = self.classes[o.t]
    if name not in ci.ftypes:
        if name in ci.methods:
            self.err(f"{o.t}.{name} is a method: call it, {name}(...) (methods are not values)")
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
        self.err(f"'{o.t}' object has no attribute '{name}'")
    extra = " and no __dict__ for setting new attributes" if store else ""
    self.notnone(o, f"AttributeError: 'NoneType' object has no attribute '{name}'{extra}")
    return Val(self.fgep(o, ci.fpos[name]), ci.ftypes[name])

def gen_fgep(self, o: Val, i: int) -> str:
    # the address of field or flag i of object o (IFn.fa holds it, for rawfx)
    r = self.ins(f"getelementptr %C.{o.t}, ptr {o.v}, i32 0, i32 {i}")
    self.fn.fa[r] = True
    return r

def gen_getfield(self, o: Val, p: Val, name: str) -> Val:
    # load a field (p = self.field(o, name)); a field __init__ may leave unassigned is checked
    ci = self.classes[o.t]
    r = ""
    bad = ""
    if o.t + "." + name in self.cvars:
        # a class variable: the object's own value once it has assigned one, else the class's
        own = self.ins(f"load i1, ptr {self.fgep(o, ci.fflag[name])}")
        fv = Val(self.ins(f"load {lt(p.t)}, ptr {p.v}"), p.t)
        if ci.tag != 0:
            # Each concrete class may shadow its base's class attribute. All related
            # mutable defaults share the inherited instance-assignment flag, but their
            # fallback globals still belong to the classes that define those defaults.
            tag = self.ins(f"load i64, ptr {self.fgep(o, ci.fpos[' class'])}")
            cv = fv
            assigned = own
            for sub in self.classes.values():
                if sub.tag != 0 and self.derives(sub.name, ci.name) and name in sub.fdefault:
                    match = self.ins(f"icmp eq i64 {tag}, {sub.tag}")
                    if sub.name + "." + name in self.cvars or not is_const(sub.fdefault[name]):
                        self.class_default(sub, name)
                        dv = Val(self.ins(f"load {lt(p.t)}, ptr {sub.fglob[name]}"), p.t)
                    else:
                        dv = self.coerce(self.expr(sub.fdefault[name], p.t), p.t)
                    cv = Val(self.select(match, dv, cv), p.t)
                    assigned = self.ins(f"or i1 {assigned}, {match}")
            bad = self.ins(f"xor i1 {assigned}, true")
            r = self.select(own, fv, cv)
        else:
            self.class_default(ci, name)
            r = self.select(own, fv, Val(self.ins(f"load {lt(p.t)}, ptr {ci.fglob[name]}"), p.t))
            if is_opt(p.t):
                self.wide[self.curfn.ll + r] = True  # (not narrowed, see coerce)
            return Val(r, p.t)
    if name in ci.fflag:
        f = self.fgep(o, ci.fflag[name])
        if bad == "":
            bad = self.ins(f"xor i1 {self.ins(f'load i1, ptr {f}')}, true")
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
                tag = self.ins(f"load i64, ptr {self.fgep(o, ci.fpos[' class'])}")
                c = self.sconst(short(ci.name))
                for sub in self.classes.values():
                    if sub.tag != 0 and sub.name != ci.name and self.derives(sub.name, ci.name):
                        match = self.ins(f"icmp eq i64 {tag}, {sub.tag}")
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
        r = self.ins(f"load {lt(p.t)}, ptr {p.v}")
    if is_opt(p.t):
        self.wide[self.curfn.ll + r] = True  # (not narrowed, see coerce)
    return Val(r, p.t)

def gen_setfield(self, o: Val, p: Val, name: str, v: Val) -> None:
    what = f"the value assigned to field '{name}' ({typestr(p.t)})" if is_opt(v.t) else ""
    self.emit(f"store {lt(p.t)} {self.coerce(v, p.t, what).v}, ptr {p.v}")
    ci = self.classes[o.t]
    if name in ci.fflag:
        self.emit(f"store i1 true, ptr {self.fgep(o, ci.fflag[name])}")

# ---- variables
