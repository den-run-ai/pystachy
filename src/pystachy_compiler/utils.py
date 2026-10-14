"""Utils component of the self-hosting Pystachy compiler."""
from __future__ import annotations
import os
from src.pystachy_compiler.diagnostics import fail
from src.pystachy_compiler.ir import FnInfo
from src.pystachy_compiler.names import short
from src.pystachy_compiler.specs import (
    CODECS,
    FSETMETHODS,
    FX,
    FXALL,
    FXBIT,
    HEX,
    INERT,
    METHODS,
    OPTS,
    RAWR,
    RAWW,
    RUNTIME,
    SETMETHODS,
    SPECIAL,
    SPECSHOW,
)
from src.pystachy_compiler.syntax import Node


def codec(e: str) -> int:
    # 1 UTF-8, 2 Latin-1, 0 another (runtime.c's codec()): the name normalized is an alias, or one
    # with "." read as "_", or the codec's module name
    n = normcodec(e)
    if n.find(".") >= 0:
        return CODECS.get(n.replace(".", "_"), 0)
    return 1 if n == "utf_8" else 2 if n == "latin_1" else CODECS.get(n, 0)


def normcodec(e: str) -> str:
    # an encoding's name normalized as CPython's codec lookup does: lowercase, and a run of
    # characters other than ASCII letters, digits and "." is one "_" between them
    n = ""
    punct = False
    for c in e:
        if c >= "A" and c <= "Z":
            n += "_" if punct and n != "" else ""
            n += c.lower()
            punct = False
        elif (c >= "a" and c <= "z") or (c >= "0" and c <= "9") or c == ".":
            n += "_" if punct and n != "" else ""
            n += c
            punct = False
        else:
            punct = True
    return n
# the most positional arguments a builtin takes: more are a compile error (a TypeError in CPython)
def lt(t: str) -> str:
    if t == "int":
        return "i64"
    if t == "float":
        return "double"
    if t == "bool":
        return "i1"
    if t == "None":
        return "void"
    if t == "%slot":
        return "i64"  # (the IR's pseudo-type of a value in an 8-byte container slot)
    return "ptr"


def rtt(t: str) -> str:
    return "i64" if t == "bool" else lt(t)


def rtll(t: str) -> str:
    # the LLVM type of a type of a RUNTIME signature
    if t.startswith("*"):
        return "i64"
    if t == "S" or t == "#":
        return "ptr"
    if t == "%ovf":
        return "{i64, i1}"
    if t.startswith("%"):
        return t[1:]
    return rtt(t)


def rtsig(k: str) -> list[str]:
    # the result and parameter types of runtime function k, as RUNTIME spells them
    e = RUNTIME[k]
    c = e.find(":")
    return [e[:c]] + targs("f[" + e[c + 1 : e.find("|")] + "]")  # (a parameter's type may hold commas: dict[T,V])


def rtsym(k: str) -> str:
    s = RUNTIME[k][RUNTIME[k].rfind("|") + 1 :]
    return s if s != "" else "pys_" + k.replace(".", "_")


def rt_subset(k: str, ts: list[str]) -> str:
    # "" if a function with result and parameter types ts (as the subset spells them) has the types
    # of RUNTIME entry k, else the entry's, spelt for a message. A bool is an int there (the ABI
    # passes bools as i64); a type variable, a slot (*X), a descriptor (#) or an LLVM type (%X) is
    # checked by its LLVM type only (rt and Gen.function), and so is the receiver S but of a str
    # or file method
    sig = rtsig(k)
    ok = len(sig) == len(ts)
    out: list[str] = []
    for j in range(len(sig)):
        w = sig[j]
        if w == "S":
            w = k[: k.find(".")] if k.startswith("str.") or k.startswith("file.") else ""
        if w == "bool":
            w = "int"
        tok = ""
        for c in w + ",":
            if c == "[" or c == "]" or c == ",":
                if tok != "" and tok not in ("int", "float", "str", "None", "list", "dict", "tuple", "file"):
                    w = ""  # (a type variable, *X, # or %X)
                tok = ""
            else:
                tok += c
        out.append(typestr(w) if w != "" else "_")
        if w != "" and j < len(ts) and ts[j] != w:
            ok = False
    return "" if ok else f"{out[0]}({', '.join(out[1:])})"


def runtime_decl(k: str) -> str:
    ps = rtsig(k)
    return f"declare {rtll(ps[0])} @{rtsym(k)}({', '.join([rtll(p) for p in ps[1:]])})"


# every effect letter but N (it is no summary's): U's, and a summary not computed yet
def fxmask(letters: str) -> int:
    # effect letters (FX) as bits (U: FXALL)
    m = 0
    for x in letters.split():
        if x == "U":
            return FXALL
        m |= FXBIT[x]
    return m


def fxs(m: int) -> str:
    # bits of effect letters as letters
    return " ".join([x for x in FX if m & FXBIT[x] != 0])


def optimizations() -> dict[str, bool]:
    # the optimizations to run (OPTS): every one but those PYSTACHY_OPT turns off ("-name",
    # comma-separated; "-all": every one), as name -> True
    on: dict[str, bool] = {}
    for o in OPTS:
        on[o] = True
    for w in os.getenv("PYSTACHY_OPT", "").split(","):
        w = w.strip()
        if w == "-all":
            on = {}
        elif w.startswith("-") and w[1:] in OPTS:
            if w[1:] in on:
                on.pop(w[1:])
        elif w != "":
            fail(f"PYSTACHY_OPT: no optimization {w} (it takes {', '.join(['-' + o for o in OPTS])} or -all, comma-separated)", 0)
    return on


def rawfx(s: str, fa: dict[str, bool]) -> int:
    # the effects (FX bits) of a raw op, whose LLVM text s loads, stores or computes: a load or a
    # store of a slot (%name.N, an alloca, which is never address-taken) has none, of a global
    # (@name) rG or wG, of an object's field or flag (an address in fa, IFn.fa) rO or wO; one
    # through another address may read (RAWR) or write (RAWW) a list or a dict
    st = s.startswith("store ")
    if not st and not s.startswith("load ", s.find(" = ") + 3):
        return 0
    a = s.rfind(" ") + 1  # where the address is: the last word of "load T, ptr A" and "store T V, ptr A"
    if s.startswith("@", a):
        return FXBIT["wG"] if st else FXBIT["rG"]
    if s.find(".", a) >= 0:
        return 0  # (a temporary, %tN, has no dot)
    if len(fa) > 0 and s[a:] in fa:
        return FXBIT["wO"] if st else FXBIT["rO"]
    return RAWW if st else RAWR


class RtFn:
    # a runtime function, as its RUNTIME entry k gives it
    def __init__(self, k: str):
        e = RUNTIME[k]
        fx = e[e.find("|") + 1 : e.rfind("|")]
        self.sym = rtsym(k)  # its LLVM symbol
        self.sig: list[str] = rtsig(k)  # its result and parameter types, as RUNTIME spells them
        self.ll: list[str] = [rtll(p) for p in self.sig]  # and as LLVM types
        self.decl = runtime_decl(k)  # its declare line
        self.fx = fxmask(fx.replace("U?", ""))  # its effects (FX bits), but U?
        self.q = "U?" in fx  # whether it has U? (U when the descriptor of its # parameter holds a class)


def tname(t: str) -> str:
    # the CPython name of a type, for error messages
    if t == "None":
        return "NoneType"
    if t == "file":
        return "TextIOWrapper"
    if t.startswith("opt["):
        return tname(t[4:-1]) + " | None"
    if is_union(t):
        return typestr(t)
    if t == "exc":
        return "BaseException"
    if is_kw(t):
        return "dict"
    if is_fn(t):
        if t.startswith("fn[u:"):
            return "method_descriptor"
        return "builtin_function_or_method" if t.startswith("fn[b:") or t.startswith("fn[d:") else "method" if t.startswith("fn[m:") else "function"
    if is_callable(t):
        return "function"
    b = t.find("[")
    return t[:b] if b >= 0 else short(t)


def raising_op(op: str) -> bool:
    # does binary operator op raise on some values of builtin types (1 // 0, 0 ** -1, 1 << -1)
    return op == "/" or op == "//" or op == "%" or op == "**" or op == "<<" or op == ">>"


def raising(e: Node) -> bool:
    # is expression e an operation that may raise on values of builtin types: a division or
    # modulo, a power or shift, an index, or a call (int("x"))
    return (e.kind == "binop" and raising_op(e.s)) or e.kind == "index" or e.kind == "call"


def int_lit(e: Node) -> str:
    # the value of e if it is an int literal (or its negation), else ""
    if e.kind == "unary" and e.s == "-" and e.kids[0].kind == "int":
        return "-" + e.kids[0].s
    return e.s if e.kind == "int" else ""


def short_ascii(s: str) -> bool:
    # is s printable ASCII with at most 18 digits, so that int(s) is what CPython's is: an int of
    # 64 bits or a ValueError (not an int beyond 64 bits, or one of other digits)
    n = 0
    for c in s:
        if c < " " or c > "~":
            return False
        if c >= "0" and c <= "9":
            n += 1
    return n <= 18


def may_raise(e: Node) -> bool:
    # does expression e hold such an operation
    if raising(e):
        return True
    for x in e.kids:
        if may_raise(x):
            return True
    return False


def plain_args(args: list[Node]) -> bool:
    # arguments passed by position, none unpacked
    for a in args:
        if a.kind == "kw" or a.kind == "starred" or a.kind == "dstar":
            return False
    return True


def is_super(e: Node) -> bool:
    # super(...)
    return e.kind == "call" and e.kids[0].kind == "name" and e.kids[0].s == "super"


def is_const(e: Node) -> bool:
    # literals: re-evaluating them on every call is indistinguishable from evaluating once
    k = e.kind
    if k == "int" or k == "float" or k == "str" or k == "True" or k == "False" or k == "None" or k == "noann":
        return True
    return k == "unary" and e.s == "-" and (e.kids[0].kind == "int" or e.kids[0].kind == "float")


def is_list(t: str) -> bool:
    return t.startswith("list[")


def is_dict(t: str) -> bool:
    return t.startswith("dict[")


def is_set(t: str) -> bool:
    # set[T] or frozenset[T] (runtime.c's sets): a frozenset is a set that no method changes
    return t.startswith("set[") or t.startswith("frozenset[")


def empty_ann(t: str) -> str:
    # the annotation that types an empty list, set or dict t, as the error suggesting it shows it
    return "list[T] = []" if is_list(t) else "set[T] = set()" if is_set(t) else "dict[K, V] = {}"


def is_fset(t: str) -> bool:
    return t.startswith("frozenset[")


def selem(t: str) -> str:
    # the element type of a set or frozenset
    return t[t.find("[") + 1 : -1]


def is_tuple(t: str) -> bool:
    return t.startswith("tuple[")


def is_opt(t: str) -> bool:
    # opt[T]: T | None for T str, int, float, bool, list, dict or tuple (a class type includes None already)
    return t.startswith("opt[")


def unopt(t: str) -> str:
    # the type an optional value has when it is not None
    return t[4:-1] if t.startswith("opt[") else t


def is_sopt(t: str) -> bool:
    # int, float or bool | None: a pointer to an immutable box of the value (runtime.c's pys_box)
    return t == "opt[int]" or t == "opt[float]" or t == "opt[bool]"


def pure_arg(e: Node) -> bool:
    # an argument whose value nothing evaluated before it can change, and that changes nothing: a
    # constant or an empty display (Gen.star_call leaves it for its parameter to type)
    k = e.kind
    return k in INERT or ((k == "list" or k == "dict" or k == "tuple") and len(e.kids) == 0)


def has_method(base: str, m: str) -> bool:
    # does builtin type base ("str", "list", "dict", "set", "file", ...) have method m that
    # Pystachy compiles (METHODS, and those Gen.bmethod and Gen.smethod dispatch themselves)
    if base == "set" or base == "frozenset":
        return m in (SETMETHODS if base == "set" else FSETMETHODS)
    return base + "." + m in METHODS or (base == "list" and m == "sort") or (base == "dict" and m == "update")


def is_kw(t: str) -> bool:
    # kw[a:A,b:B]: a function's **kwargs, the record of a call's extra keyword arguments, by name
    # and type (Gen.kw_record), which is the tuple of their values at run time
    return t.startswith("kw[")


def kw_names(t: str) -> list[str]:
    return [x[: x.find(":")] for x in targs(t)]


def kw_types(t: str) -> list[str]:
    return [x[x.find(":") + 1 :] for x in targs(t)]


def is_fn(t: str) -> bool:
    # a function as a value, typed by the function it is: fn[f:NAME] the program's function NAME (a
    # def at a module's top level), fn[b:NAME] the builtin NAME (len, math.sqrt), fn[c:N:QUAL] a def
    # or lambda inside a function (Gen.closures[N]), fn[m:C.NAME] method NAME bound to an object of
    # class C, fn[d:NAME:T] method NAME of builtin type T bound to a value ("".join), fn[u:T.NAME]
    # that method read through its type (str.lower), which takes the value first. A call through
    # it is compiled as a call of that function, of a template for the call's argument types: the
    # value holds nothing (null), but a closure's, which points to its env, and a bound method's,
    # which is the object
    return t.startswith("fn[")


def is_callable(t: str) -> bool:
    # Callable[[A, B], R]: callable[R,A,B], a pointer to an object {code, env} whose code takes the
    # env and the arguments (Gen.call_callable). A function value becomes one where a Callable is
    # expected (Gen.to_callable), so one variable, field or list may hold different functions
    return t.startswith("callable[")


def callable_shown(t: str) -> str:
    # callable[R,A,B] as typing writes it: Callable[[A, B], R] (its types still to be shown)
    ts = targs(t)
    return "Callable[[" + ", ".join(ts[1:]) + "], " + ts[0] + "]"


def fn_shown(t: str) -> str:
    # function value type t for a message: the function it is, as CPython's repr names it (a
    # closure's type ends with its qualified name)
    k = t[3:-1]
    if k.startswith("u:"):
        return f"<method '{k[k.find('.') + 1 :]}' of '{k[2 : k.find('.')]}' objects>"
    if k.startswith("m:"):
        return f"<bound method {short(k[2 : k.rfind('.')])}.{k[k.rfind('.') + 1 :]}>"
    if k.startswith("d:"):
        return f"<built-in method {k[2 : k.find(':', 2)]} of {tname(k[k.find(':', 2) + 1 :])} object>"
    if k.startswith("c:"):
        q = k[k.find(":", 2) + 1 :]
        return f"<function {q[: q.find('@')]} ({q[q.find('@') + 1 :]})>"
    return f"<built-in function {k[2:]}>" if k.startswith("b:") else f"<function {short(k[2:])}>"


def meet(states: list[dict[str, str]]) -> dict[str, str]:
    # the names narrowed alike in every one of states (narrowed where paths join)
    r: dict[str, str] = {}
    for nm in states[0]:
        ok = True
        for st in states[1:]:
            ok = ok and nm in st and st[nm] == states[0][nm]
        if ok:
            r[nm] = states[0][nm]
    return r


def nones(e: Node) -> bool:
    # is e a list display of None items, or a dict display of constant keys and None values
    for i in range(len(e.kids)):
        x = e.kids[i]
        if (e.kind == "list" or i % 2 == 1) and x.kind != "None":
            return False
        if e.kind == "dict" and i % 2 == 0 and x.kind != "str" and x.kind != "int":
            return False
    return True


def int_fits(s: str) -> bool:
    # does int literal s (as the lexer gives it: decimal, maybe negated) fit in 64 bits
    neg = s.startswith("-")
    d = s[1:] if neg else s
    return not (len(d) > 19 or (len(d) == 19 and d > ("9223372036854775808" if neg else "9223372036854775807")))


def nonetest(n: Node) -> int:
    # n is x is None, x is not None, x == None or x != None (or None is x, None == x, ...): the
    # index of x in n.kids; -1 otherwise
    if n.kind != "cmp" or (n.s != "is" and n.s != "is not" and n.s != "==" and n.s != "!="):
        return -1
    return 0 if n.kids[1].kind == "None" else 1 if n.kids[0].kind == "None" else -1


def same_kind(a: str, b: str) -> bool:
    # are types a and b both lists, both dicts or both sets (a class may be named listing)
    return (is_list(a) and is_list(b)) or (is_dict(a) and is_dict(b)) or (is_set(a) and is_set(b) and is_fset(a) == is_fset(b))


def typestr(t: str) -> str:
    # type t for a message: an empty list or dict whose type is not known yet is "list" or "dict",
    # opt[T] is T | None, a builtin exception BaseException, a class its own name, a function value
    # the function (fn_shown)
    t = t.replace("[?,?]", "").replace("[?]", "")
    while "kw[" in t:
        # (**kwargs: the record of a call's extra keyword arguments)
        a = t.find("kw[")
        b = a + 3
        depth = 1
        while depth > 0:
            depth += 1 if t[b] == "[" else -1 if t[b] == "]" else 0
            b += 1
        k = t[a:b]
        t = t[:a] + "**kwargs(" + ", ".join([kw_names(k)[i] + "=" + typestr(kw_types(k)[i]) for i in range(len(kw_names(k)))]) + ")" + t[b:]
    while "fn[" in t:
        a = t.find("fn[")
        b = a + 3
        depth = 1
        while depth > 0:
            depth += 1 if t[b] == "[" else -1 if t[b] == "]" else 0
            b += 1
        t = t[:a] + fn_shown(t[a:b]) + t[b:]  # (a bound method's receiver type may hold brackets)
    while "callable[" in t:
        a = t.find("callable[")
        b = a + 9
        depth = 1
        while depth > 0:
            depth += 1 if t[b] == "[" else -1 if t[b] == "]" else 0
            b += 1
        t = t[:a] + callable_shown(t[a:b]) + t[b:]
    out: list[str] = []
    w = ""
    for c in t + ",":
        if c == "[" or c == "]" or c == ",":
            out.append("BaseException" if w == "exc" else SPECSHOW[w] if w in SPECSHOW else short(w))
            out.append(c)
            w = ""
        else:
            w += c
    return optnames(unionnames("".join(out)[:-1]))


def optnames(t: str) -> str:
    # t (a type, or a message that names types) with each opt[T] written T | None
    while "opt[" in t:
        a = t.find("opt[")
        b = a + 4
        depth = 1
        while depth > 0 and b < len(t):
            depth += 1 if t[b] == "[" else -1 if t[b] == "]" else 0
            b += 1
        x = t[a + 4 : b - 1]
        t = t[:a] + (x if x == "None" else x + " | None") + t[b:]
    return t


def literal(e: Node) -> bool:
    # is e a constant that CPython's compiler always makes one of: a literal, a sign on a number, or
    # a tuple of those (an operator's result may exceed its limits, "a" * 4097, and is left to run)
    k = e.kind
    if k == "int" or k == "float" or k == "str" or k == "True" or k == "False" or k == "None" or k == "ellipsis":
        return True
    if k == "unary" and (e.s == "-" or e.s == "+") and (e.kids[0].kind == "int" or e.kids[0].kind == "float"):
        return True
    if k == "tuple":
        for x in e.kids:
            if not literal(x):
                return False
        return True
    return False


def folds(e: Node) -> bool:
    # is e a constant once CPython's AST optimizer has run (ast_opt.c): a literal, a tuple of
    # constants, or an operator applied to constants (a set display of constants is then a
    # frozenset constant, whose table decides the order of its elements)
    k = e.kind
    if k == "int" or k == "float" or k == "str" or k == "True" or k == "False" or k == "None" or k == "ellipsis":
        return True
    if k == "tuple" or k == "unary" or (k == "binop" and e.s != "%"):
        for x in e.kids:
            if not folds(x):
                return False
        return True
    return False


def empty_display(e: Node) -> bool:
    return (e.kind == "list" or e.kind == "dict") and len(e.kids) == 0


def empty_default(n: Node, name: str, kind: str) -> bool:
    # is n name.setdefault(k, []) (kind "list"), name.setdefault(k, {}) (kind "dict") or
    # name.setdefault(k, set()) (kind "set")
    if n.kind != "call" or len(n.kids) != 3 or n.kids[0].kind != "attr" or n.kids[0].s != "setdefault":
        return False
    if kind == "set":
        d = n.kids[2]
        return n.kids[0].kids[0].kind == "name" and n.kids[0].kids[0].s == name and d.kind == "call" and len(d.kids) == 1 and d.kids[0].kind == "name" and d.kids[0].s == "set"
    return n.kids[0].kids[0].kind == "name" and n.kids[0].kids[0].s == name and n.kids[2].kind == kind and len(n.kids[2].kids) == 0


def key_problem(t: str) -> str:
    # why t cannot be a dict's key type, or "": keys are ints, strs, or tuples whose items are ints,
    # bools, strs, str | None or such tuples (runtime.c hashes and compares them by descriptor)
    if t == "int" or t == "str" or (is_tuple(t) and key_items(t)):
        return ""
    if is_opt(t):
        return f"dict keys must be int or str, not {typestr(t)} (a key cannot be None)"
    return f"dict keys must be int or str, or tuples of int, bool, str and str | None items, not {typestr(t)}"


def elem_problem(t: str) -> str:
    # why t cannot be the element type of a set, or "": the types of dict keys (key_problem)
    if is_opt(t):
        return f"set elements must be int or str, not {typestr(t)} (an element cannot be None)"
    return key_problem(t).replace("dict keys", "set elements")


def lookable(a: str, b: str) -> bool:
    # can a value of type a be looked up among dict keys of type b, as CPython compares them: True
    # is 1, and None (a tuple's item) is no str
    if a == b or (a == "bool" and b == "int") or (b == "str" and (a == "None" or a == "opt[str]")):
        return True
    if not is_tuple(a) or not is_tuple(b) or len(targs(a)) != len(targs(b)):
        return False
    for i in range(len(targs(a))):
        if not lookable(targs(a)[i], targs(b)[i]):
            return False
    return True


def bool_for_int(a: str, b: str) -> bool:
    # does a key of type a hold a bool where the dict's keys, of type b, hold an int: the key it
    # finds is that int, but CPython's KeyError names the key as it is (KeyError: True, not 1),
    # and CPython keeps a key it adds as it is, a bool (Gen.bool_find, Gen.store_key)
    if a == "bool":
        return b == "int"
    if not is_tuple(a) or not is_tuple(b) or len(targs(a)) != len(targs(b)):
        return False
    for i in range(len(targs(a))):
        if bool_for_int(targs(a)[i], targs(b)[i]):
            return True
    return False


def key_items(t: str) -> bool:
    for x in targs(t):
        u = unopt(x)
        if x != "int" and x != "bool" and u != "str" and not (is_tuple(u) and key_items(u)):
            return False
    return True


def elem(t: str) -> str:
    return t[5:-1]


def targs(t: str) -> list[str]:
    out: list[str] = []
    depth = 0
    start = t.find("[") + 1
    if start == len(t) - 1:
        return out  # tuple[]: the empty tuple
    for i in range(start, len(t) - 1):
        c = t[i]
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
        elif c == "," and depth == 0:
            out.append(t[start:i])
            start = i + 1
    out.append(t[start:-1])
    return out


def llstr(s: str) -> str:
    out: list[str] = []
    for c in s:
        o = ord(c)
        if o < 32 or o > 126 or c == '"' or c == "\\":
            out.append("\\" + HEX[o >> 4] + HEX[o & 15])
        else:
            out.append(c)
    return "".join(out)


def hpush(h: list[int], x: int) -> None:
    # h is a binary min-heap (heapq's layout)
    h.append(x)
    i = len(h) - 1
    while i > 0 and h[(i - 1) // 2] > x:
        h[i] = h[(i - 1) // 2]
        i = (i - 1) // 2
    h[i] = x


def hpop(h: list[int]) -> int:
    top = h[0]
    x = h.pop()
    if len(h) > 0:
        i = 0
        while 2 * i + 1 < len(h):
            c = 2 * i + 1
            if c + 1 < len(h) and h[c + 1] < h[c]:
                c += 1
            if x <= h[c]:
                break
            h[i] = h[c]
            i = c
        h[i] = x
    return top


def hexn(v: int, n: int) -> str:
    s = ""
    for i in range(n):
        s = HEX[v & 15] + s
        v = v >> 4
    return s


def fbits(text: str) -> str:
    # exact IEEE-754 bits of a float literal, via float.hex(), as an LLVM hex constant
    h = float(text).hex()
    sign = 0
    if h.startswith("-"):
        sign = 2048
        h = h[1:]
    if h == "inf":
        return "0x" + hexn(sign + 2047, 3) + "0" * 13
    if h == "nan":
        return "0x7FF8000000000000"
    dot = h.find(".")
    p = h.find("p")
    frac = h[dot + 1 : p] if dot >= 0 else ""
    frac = frac + "0" * (13 - len(frac))
    e = 0 if h[2] == "0" else int(h[p + 1 :]) + 1023
    return "0x" + hexn(sign + e, 3) + frac.upper()


def template_ok(name: str) -> bool:
    # may a method of this name be a template, its unannotated parameters typed by each call (M2)?
    # Not __init__, whose parameters type the fields it assigns, nor a special method that CPython
    # calls implicitly, but an operator's (SPECIAL's of two parameters) and __call__, __getitem__
    # and __contains__, which a call compiles as any other
    if not (name.startswith("__") and name.endswith("__")):
        return True
    return name in "__call__ __getitem__ __contains__".split() or (name in SPECIAL and SPECIAL[name].startswith("2:"))


def takes_self(f: FnInfo) -> bool:
    # is f a method that takes its object as its first parameter (not a static or class method)
    return f.cls != "" and f.deco == ""


def clone(n: Node) -> Node:
    # a copy of tree n (a class method's def, compiled again for a class that inherits it)
    c = Node(n.kind, n.s, n.line)
    c.kids = [clone(k) for k in n.kids]
    c.chk = n.chk
    c.mchk = n.mchk
    c.depth = n.depth
    return c


def rename(n: Node, name: str, to: str) -> None:
    # the reads of name in n read to instead (a class method's cls is its class)
    if n.kind == "name" and n.s == name:
        n.s = to
    for k in n.kids:
        rename(k, name, to)


# ---------------------------------------------------------------- the IR
# Gen builds one IFn per compiled function: blocks of instructions (Ins), each an op string
# whose fields mean what the op says (docs/typed-ir.md 3.4). Until all of Gen builds ops, most
# are "raw": one line of LLVM text. Once the whole program is built, lowering prints the LLVM
# text of each IFn (lower).
# The lists an op starts with: shared, and never changed (Gen.program checks it). An op that has
# numbers, operands or labels gets lists of its own (most ops are raw and have none of them).


def is_union(t: str) -> bool:
    # union[A,B,...]: a value of one of two or more types (A | B), none of them None, a union or an
    # optional; a pointer to a box of the value's tag (its type's, see Gen.utag) and its slot
    # (runtime.c's pys_ubox). None is null: in opt[union[...]], or where a member is a class
    return t.startswith("union[")

def umembers(t: str) -> list[str]:
    # the member types of union t, in their (sorted) order
    return targs(t)

def unionnames(t: str) -> str:
    # t (a type, or a message that names types) with each union[A,B] written A | B
    while "union[" in t:
        a = t.find("union[")
        b = a + 6
        depth = 1
        ms: list[str] = []
        m = a + 6
        while depth > 0 and b < len(t):
            depth += 1 if t[b] == "[" else -1 if t[b] == "]" else 0
            if (depth == 1 and t[b] == ",") or depth == 0:
                ms.append(t[m:b])
                m = b + 1
            b += 1
        t = t[:a] + " | ".join(ms) + t[b:]
    return t
