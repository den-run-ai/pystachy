"""Builtins component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.utils import is_union
from src.pystachy_compiler.ir import Ins, IterArg, Loop, Reduce, Val
from src.pystachy_compiler.lexer import Lexer
from src.pystachy_compiler.names import short
from src.pystachy_compiler.parser import Parser
from src.pystachy_compiler.specs import (
    ARITY,
    CALLS,
    DEFAULTS,
    ERRNO,
    FLOATINFO,
    METHODS,
    MODATTRS,
    MODFUNCS,
    NONEARG,
    NONERET,
    OPTARG,
    OPTCALLS,
    OPTTYPES,
    OSCONST,
    PYBUILTINS,
    STRLEN_RANGE,
    TBAA_LEN,
)
from src.pystachy_compiler.syntax import Node, mk
from src.pystachy_compiler.utils import (
    bool_for_int,
    elem,
    fbits,
    is_callable,
    is_dict,
    is_fn,
    is_kw,
    is_list,
    is_opt,
    is_set,
    is_sopt,
    is_tuple,
    kw_names,
    lt,
    rtt,
    selem,
    targs,
    tname,
    typestr,
    unopt,
)


def gen_dotted(self, n: Node) -> str:
    # "sys.argv", "os.path.exists", ... when n is an attribute chain on a module
    if n.kind == "name":
        if n.s in self.aliases and n.s not in self.ltype and n.s not in self.gtypes and n.s not in self.compvars and not self.unbound_local(n.s):
            return self.aliases[n.s]
    elif n.kind == "attr":
        p = self.dotted(n.kids[0])
        if p != "" and p not in MODATTRS:
            return p + "." + n.s
    return ""

def gen_modattr(self, path: str) -> Val:
    if path == "sys.argv":
        return Val(self.rt("pys_argv", "ptr", []), "list[str]")
    if path == "sys.maxsize":
        return Val("9223372036854775807", "int")
    if path == "sys.stdin" or path == "sys.stdout" or path == "sys.stderr":
        return Val(self.rt("pys_std", "ptr", [f"i64 {0 if path == 'sys.stdin' else 1 if path == 'sys.stdout' else 2}"]), "file")
    if path == "math.pi":
        return Val(fbits("3.141592653589793"), "float")
    if path == "math.e":
        return Val(fbits("2.718281828459045"), "float")
    if path == "math.inf":
        return Val(fbits("inf"), "float")
    if path == "math.tau":
        return Val(fbits("6.283185307179586"), "float")
    if path == "math.nan":
        return Val("0x7FF8000000000000", "float")
    if path == "typing.TYPE_CHECKING":
        return Val("false", "bool")
    if path in OSCONST:
        return Val(self.sconst(OSCONST[path]), "str")
    if path in FLOATINFO:
        c = FLOATINFO[path]
        return Val(fbits(c), "float") if "e" in c else Val(c, "int")
    if path == "sys.float_info":
        self.err("sys.float_info cannot be used as a value (read its attributes: sys.float_info.max, sys.float_info.epsilon, ...)")
    if path == "sys.platform":
        return Val(self.rt("pys_platform", "ptr", []), "str")
    if path.startswith("errno.") and path[6:] in ERRNO:
        return Val(self.rt("pys_errno", "i64", [f"ptr {self.sconst(path[6:])}"]), "int")
    if path in MODFUNCS:
        return Val("null", f"fn[b:{path}]")  # (a function of a builtin module as a value)
    if (path.endswith(".__name__") or path.endswith(".__qualname__")) and path[: path.rfind(".")] in MODFUNCS:
        fp = path[: path.rfind(".")]
        return Val(self.sconst(fp[fp.rfind(".") + 1 :]), "str")
    self.err(f"unsupported module attribute {path}")
    return Val("", "")

def gen_builtin(self, name: str, args: list[Node], want: str) -> Val:
    if name == "__pys_exc_repr":
        return self.exc_brepr(self.expr(args[0], ""))  # (exc_helpers)
    if name == "__pys_repr_enter" or name == "__pys_repr_leave":
        o = self.expr(args[0], "")
        r = self.rt(name[2:], "i64" if name.endswith("enter") else "void", [f"ptr {o.v}"])
        return Val(self.ins(f"icmp ne i64 {r}, 0"), "bool") if name.endswith("enter") else Val("null", "None")
    if name == "__pys_repr" or name == "__pys_str" or name == "__pys_ascii":
        # compiler-written calls (f"{x!r}", dataclass __repr__): always the builtin
        name = name[6:]
    if name.startswith("builtins."):
        name = name[9:]
    if name == "typing.NamedTuple":
        self.err("the functional NamedTuple form is not supported: write a class, class P(NamedTuple): with annotated fields")
    if "." not in name and name not in PYBUILTINS:
        self.err(f"name '{short(name)}' is not defined")
    # builtins and module functions ("os.system"); most are one call listed in CALLS
    if name == "print":
        return self.print_(args)
    if name == "open":
        return self.open_(args)
    if name == "set" or name == "frozenset":
        return self.set_new(name, args, want)
    if name == "map" or name == "filter":
        self.err(f"{name}() is supported as the argument of list(), sorted(), sum(), min(), max(), any(), all(), math.fsum(), math.prod(), str.join() and list.extend(), which take its items at once; elsewhere use a list comprehension")
    if len(args) > 0 and self.is_mapcall(args[0]) and (name == "list" or name == "sorted" or name == "sum" or name == "min" or name == "max" or name == "any" or name == "all" or name == "math.fsum" or name == "math.prod"):
        args = [self.mapgen(args[0])] + args[1:]  # (the generator expression it is)
    if name == "format" and 1 <= len(args) <= 2 and len([a for a in args if a.kind == "kw"]) == 0:
        # format(v, spec): what the f-string field {v:spec} gives, v.__format__(spec)
        return self.format_(self.expr(args[0], ""), args[1] if len(args) == 2 else mk("str", "", self.line, []))
    if name == "os.path.join" and len(args) >= 1 and len([a for a in args if a.kind == "kw"]) == 0:
        # posixpath.join: each part after the first is appended with a "/" between them, unless
        # it is absolute (it replaces the path so far) or the path so far is empty or ends in "/"
        pv = self.coerce(self.expr(args[0], "str"), "str", "argument 1 of os.path.join()")
        for k in range(1, len(args)):
            b = self.coerce(self.expr(args[k], "str"), "str", f"argument {k + 1} of os.path.join()")
            pv = Val(self.rt("pys_path_join", "ptr", [f"ptr {pv.v}", f"ptr {b.v}"]), "str")
        return pv
    if name == "hasattr" and len(args) == 2 and args[1].kind == "str":
        # decided by the static type of the object (for an object: is it None)
        hv = self.expr(args[0], "")
        if hv.t in self.classes and self.classes[hv.t].tag > 0:
            # A derived class may add this attribute, or leave its field unassigned.
            # Read a field's flag only in its concrete class's arm: it may lie beyond
            # the end of an object belonging to a smaller base class.
            attr = args[1].s
            start = self.cur
            present = self.label()
            done = self.label()
            ph = Ins("phi", "bool", "")
            self.incoming(ph, "true" if self.has("None", attr) == 1 else "false", start)
            self.cbr("true" if hv.v in self.nn else self.ins(f"icmp ne ptr {hv.v}, null"), present, done)
            self.place(present)
            tag = self.ins(f"load i64, ptr {hv.v}")
            cs = [c for c in self.classes.values() if c.tag > 0 and self.derives(c.name, hv.t)]
            for i in range(len(cs)):
                ci = cs[i]
                nxt = self.label() if i + 1 < len(cs) else ""
                if nxt != "":
                    arm = self.label()
                    self.cbr(self.ins(f"icmp eq i64 {tag}, {ci.tag}"), arm, nxt)
                    self.place(arm)
                hy = self.has(ci.name, attr)
                if attr in ci.fflag and attr not in ci.fdefault and attr not in ci.methods:
                    value = self.ins(f"load i1, ptr {self.fgep(Val(hv.v, ci.name), ci.fflag[attr])}")
                else:
                    value = "false" if hy == 0 else "true"
                self.incoming(ph, value, self.cur)
                self.br(done)
                if nxt != "":
                    self.place(nxt)
            self.place(done)
            return Val(self.phi(ph), "bool")
        hy = self.has(hv.t, args[1].s)
        if hy == -2:
            # a field that may be unassigned: not None, and its "is assigned" flag
            e0 = self.cur
            l1 = self.label()
            l2 = self.label()
            self.cbr("true" if hv.v in self.nn else self.ins(f"icmp ne ptr {hv.v}, null"), l1, l2)
            self.place(l1)
            fv = self.ins(f"load i1, ptr {self.fgep(hv, self.classes[hv.t].fflag[args[1].s])}")
            e1 = self.cur
            self.br(l2)
            self.place(l2)
            ph = Ins("phi", "bool", "")
            self.incoming(ph, "false", e0)
            self.incoming(ph, fv, e1)
            return Val(self.phi(ph), "bool")
        if hy < 0:
            return Val(self.ins(f"icmp ne ptr {hv.v}, null"), "bool")
        return Val("true" if hy == 1 else "false", "bool")
    if name == "isinstance" and len(args) == 2 and args[0].kind != "kw" and args[1].kind != "kw":
        # decided by the static types, or by whether it is None (an optional value, an object)
        v = self.expr(args[0], "")
        self.isinst_reads(args[1])
        if (v.t == "exc" or (v.t in self.classes and self.classes[v.t].exc != "")) and self.exc_classes(args[1]):
            return self.exc_isinst(v, args[1])
        if is_union(unopt(v.t)) and self.isinst(v.t, args[1]) == -1:
            return Val(self.uisinst(v, args[1]), "bool")
        known = self.isinst(v.t, args[1])
        if known < -1:
            return Val(self.ins(f"icmp {'ne' if known == -2 else 'eq'} ptr {v.v}, null"), "bool")
        if known < 0:
            if v.t in self.classes and self.classes[v.t].tag > 0:
                return self.obj_isinst(v, args[1])
            self.err("isinstance() is only supported with the builtin types and classes as its second argument")
        return Val("true" if known == 1 else "false", "bool")
    if (name == "any" or name == "all") and len(args) == 1 and (self.iterator_call(args[0]) or (args[0].kind == "listcomp" and args[0].s == "gen")):
        # these stop at the deciding item, as CPython's iterators do
        g = args[0]
        if g.kind != "listcomp":
            g = mk("listcomp", "gen", g.line, [mk("name", "__item", g.line, []), mk("name", "__item", g.line, []), g])
        return self.listcomp(g, "", name)
    if name == "sum" or name == "min" or name == "max":
        stt = self.stream_start(name, args)
        if stt != "-":
            return self.reduce(name, args, stt)
    base = [a.kids[0] for a in args if a.kind == "kw" and a.s == "base"] if name == "int" else []
    if len(base) > 0:
        # int(x, base=b) is int(x, b) (x is positional only: int(x=s) is an unknown keyword)
        args = [a for a in args if a.kind != "kw" or a.s != "base"]
        if len(args) == 0:
            self.err("int() missing string argument")
        args = args + base
    if name == "math.prod":
        # prod(iterable, /, *, start=1): start is sum()'s second argument
        npos = len([a for a in args if a.kind != "kw"])
        if npos != 1:
            self.err(f"prod() takes exactly 1 positional argument ({npos} given)")
        args = [a.kids[0] if a.kind == "kw" and a.s == "start" else a for a in args]
    npos = 0
    for a in args:
        if a.kind != "kw":
            npos += 1
        elif (name == "sorted" or name == "min" or name == "max") and a.s == "key":
            pass  # (a function the items are compared by)
        elif name != "open" and not (name == "sorted" and a.s == "reverse"):
            self.err(f"keyword argument '{a.s}' of {name}() is not supported")
    if name in ARITY and npos > ARITY[name]:
        m = ARITY[name]
        self.err(f"{name}() takes {'exactly one argument' if m == 1 else f'at most {m} arguments'} ({npos} given)")
    if len(args) == 0 and name in DEFAULTS:
        args = [self.parse_expr(DEFAULTS[name])]
    w = want if name == "list" or name == "sorted" or name == "dict" else ""
    fresh = False
    # key= and reverse= of sorted(), min() and max(), evaluated in the order written: after a
    # list comprehension has run, but once the iterator of a generator expression or of
    # range(), zip(), ... is made, before the function iterates it (as CPython calls it)
    kws = [a for a in args if a.kind == "kw" and (a.s == "key" or a.s == "reverse") and (name == "sorted" or name == "min" or name == "max")]
    kvals: list[Val] = []
    if npos == 1 and (name == "sorted" or name == "min" or name == "max" or name == "sum" or name == "any" or name == "all" or name == "list" or name == "math.fsum" or name == "math.prod"):
        # these iterate their argument at once, so range(), reversed(), enumerate() and zip() may be it
        fresh = self.iterator_call(args[0]) or args[0].kind == "listcomp"
        lazy = self.iterator_call(args[0]) or (args[0].kind == "listcomp" and args[0].s == "gen")
        ka = IterArg(mk("tuple", "", self.line, [a.kids[0] for a in kws])) if len(kws) > 0 and lazy else None
        v0 = self.consume(args[0], w, ka)
        if ka is not None:
            kvals = [self.tget(ka.value, j) for j in range(len(kws))]
        elif len(kws) > 0:
            kvals = [self.expr(a.kids[0], "") for a in kws]
        if is_opt(v0.t):
            v0 = self.unwrap(v0, "TypeError: 'NoneType' object is not iterable")
        if name == "any" and v0.t == "file":
            # any(f) reads one line: lines are never empty
            first = self.rt("pys_file_readline", "ptr", [f"ptr {v0.v}"])
            return Val(self.ins(f"icmp ne i64 {self.ins(f'load i64, ptr {first}')}, 0"), "bool")
        vals = [self.as_list(v0, name)]
        fresh = fresh or is_set(v0.t)  # (the list of a set's elements is a new one)
        if v0.t == "tuple[]" and is_list(w):
            vals[0] = Val(vals[0].v, w)  # (list(()) has no item to type: it is the list wanted)
        self.close_temp(args[0], v0)
    elif (name == "sum" or name == "math.prod") and npos == 2 and (self.iterator_call(args[0]) or (args[0].kind == "listcomp" and args[0].s == "gen")):
        # Construct the iterator first, then evaluate start, then traverse it. In particular,
        # __iter__ and range's step check run before start; reversed keeps its original length.
        it = args[0]
        if self.iterator_call(it):
            item = mk("name", "__item", it.line, [])
            it = mk("listcomp", "gen", it.line, [item, item, it])
        st = IterArg(args[1])
        vals = [self.listcomp(it, "", "", "", st), st.value]
    elif (name == "len" or name == "bool") and len(args) == 1 and args[0].kind == "name" and "?" in self.rtype(args[0].s):
        self.allowq = True
        vals = [self.read(args[0])]
        self.allowq = False
    else:
        vals = [self.expr(a, w) for a in args if a.kind != "kw"]
        kvals = [self.expr(a.kids[0], "") for a in kws]
    rev = "0"
    keyv = Val("", "")
    for j in range(len(kws)):
        if kws[j].s == "reverse":
            rev = self.reverse_val(kvals[j], name)
        elif kvals[j].t != "None":
            keyv = kvals[j]  # (key=None: the items themselves)
            self.key_check(keyv, f"{name}()")
    if (name == "sum" or name == "math.prod") and len(vals) == 2 and vals[1].t == "bool":
        self.err(f"{name}() with a bool start is not supported: it returns the bool for an empty iterable, else a number; use int(start) for a numeric result")
    if (name == "sum" or name == "math.prod") and len(vals) == 2 and (vals[0].t in self.classes or is_tuple(vals[0].t) or is_dict(vals[0].t)):
        vals[0] = self.as_list(vals[0], name)  # (sum(o, start) iterates o once start is evaluated)
    if name == "round" and len(vals) == 2 and vals[1].t == "None":
        vals = vals[:1]  # round(x, None) is round(x)
    elif name == "round" and len(vals) == 2 and is_sopt(vals[1].t) and (unopt(vals[0].t) == "int" or unopt(vals[0].t) == "bool"):
        # an ndigits that may be None: for an int, round(x, None) is round(x, 0)
        vals[1] = self.coerce(Val(self.optint(vals[1], "0"), "int"), "int")
    elif name == "round" and len(vals) == 2 and is_opt(vals[1].t):
        self.err(f"round() with an ndigits that may be None ({typestr(vals[1].t)}) is not supported: it returns an int where ndigits is None, else a float; test it with 'is not None' first")
    if name == "math.dist":
        # tuple(p), then tuple(q): p's __iter__ runs before q is found to be None, and q's
        # __iter__, which may change the list p steps through, after p's items are copied
        q = unopt(vals[1].t) if len(vals) == 2 else ""
        for i in range(len(vals)):
            t = unopt(vals[i].t)
            v = self.as_list(self.unwrap(vals[i], "TypeError: 'NoneType' object is not iterable") if is_opt(vals[i].t) else vals[i], name)
            if i == 0 and q in self.classes and q not in self.nts and (is_list(t) or (t in self.classes and t not in self.nts)):
                # (p is a list, or the list its __iter__ steps through: not a copy)
                v = Val(self.rt("pys_list_copy", "ptr", [f"ptr {v.v}"]), v.t) if v.t == "list[float]" else self.floats(v)
            vals[i] = v
    if name == "int" and len(vals) == 2:
        # CPython checks the base before x: its type (a bool is an int), then its range (as
        # pys_int_str does first; checked here too where x may be None, tested before the call)
        vals[1] = self.as_int(self.unwrap(vals[1], "TypeError: " + NONEARG["chr"]))
        nb = vals[1].v
        if is_opt(vals[0].t) and vals[1].t == "int" and not (nb.isdigit() and int(nb) <= 36 and nb != "1"):
            out = self.ins(f"icmp ugt i64 {self.ins(f'sub i64 {nb}, 2')}, 34")
            self.guard(self.ins(f"and i1 {out}, {self.ins(f'icmp ne i64 {nb}, 0')}"), "ValueError: int() base must be >= 2 and <= 36, or 0")
    for i in range(len(vals)):
        if vals[i].t == "None" and name in NONERET and len(vals) == 1:
            # None itself (a template's parameter whose argument is None): CPython's error
            self.raise_("TypeError", self.sconst(NONEARG[name]))
            return Val("0" if NONERET[name] == "int" else "false" if NONERET[name] == "bool" else fbits("0.0"), NONERET[name])
        if not is_opt(vals[i].t):
            continue
        bad = NONEARG[name] if name in NONEARG else ""
        if name == "int" and len(vals) == 2:
            bad = "int() can't convert non-string with explicit base"
        elif (name == "sum" or name == "math.prod") and i == 0:
            bad = "'NoneType' object is not iterable"
        if bad != "":
            vals[i] = self.unwrap(vals[i], "TypeError: " + bad)
        elif name not in OPTARG:
            if f"{name}({','.join([unopt(v.t) for v in vals])})" not in CALLS and name not in OPTCALLS:
                # (not for the value it holds either)
                self.err(f"unsupported call {name}({','.join([typestr(v.t) for v in vals])})")
            self.err(f"argument {i + 1} of {name}() may be None ({typestr(vals[i].t)}); test it with 'is not None' first")
    key = f"{name}({','.join([v.t for v in vals])})"
    if self.rtmode and name.startswith("_rt."):
        return self.primitive(name[4:], vals)
    if key in DEFAULTS:
        vals.append(self.expr(self.parse_expr(DEFAULTS[key]), ""))
        key = f"{name}({','.join([v.t for v in vals])})"
    if name == "input" and len(vals) == 1 and vals[0].t != "str":
        vals[0] = self.to_str(vals[0])
        key = "input(str)"
    if name == "input" and len(vals) == 0:
        # no prompt: CPython writes nothing to sys.stdout (which may be closed) before reading
        return Val(self.rt("pys_input", "ptr", ["ptr null"]), "str")
    if name == "sys.exit" or name == "exit" or name == "quit":
        if len(vals) > 1:
            self.err(f"sys.exit() takes at most 1 argument ({len(vals)} given)")
        if len(vals) == 1 and vals[0].t in self.classes and self.derives(vals[0].t, "SystemExit"):
            self.throw(self.exc_of(vals[0]))  # (a SystemExit itself is raised as it is)
            return Val("null", "None")
        self.exit_(vals if len(vals) == 0 or vals[0].t != "None" else [], True)
        return Val("null", "None")
    if (name == "os.fspath" or name == "os.path.normcase") and len(vals) == 1 and vals[0].t == "str":
        return vals[0]  # a str path is its own file system path, and posixpath's normcase() of it
    if name == "os.getenv" and (len(vals) == 1 or (len(vals) == 2 and vals[1].t == "None")):
        # without a default the result is the variable's value or None
        return Val(self.rt("pys_getenv", "ptr", [f"ptr {self.coerce(vals[0], 'str', 'argument 1 of os.getenv()').v}", "ptr null"]), "opt[str]")
    if (name == "math.floor" or name == "math.ceil" or name == "math.trunc") and len(vals) == 1 and (vals[0].t == "int" or vals[0].t == "bool"):
        return self.as_int(vals[0])
    if name == "round" and len(vals) >= 1 and (vals[0].t == "int" or vals[0].t == "bool"):
        # an int's round(x) is x, and round(x, n) rounds it to a multiple of 10**-n for n < 0
        if len(vals) == 1:
            return self.as_int(vals[0])
        nd = self.coerce(self.as_int(vals[1]), "int")
        return Val(self.rt("pys_round_int", "i64", [f"i64 {self.as_int(vals[0]).v}", f"i64 {nd.v}"]), "int")
    if key not in CALLS and name == "math.ldexp" and len(vals) == 2:
        vals = [self.as_float(self.as_int(vals[0])), self.as_int(vals[1])]
        key = f"{name}({','.join([v.t for v in vals])})"
    if key not in CALLS and (name == "math.fsum" or name == "math.prod" or name == "math.dist"):
        # CPython makes a float of each int item (in a product, of each item and the start once
        # there is a float)
        fl = [self.floats(v) for v in vals]
        if f"{name}({','.join([v.t for v in fl])})" in CALLS:
            vals = fl
            key = f"{name}({','.join([v.t for v in vals])})"
    if key not in CALLS and name.startswith("math."):
        vals = [self.as_float(v) for v in vals]
        key = f"{name}({','.join([v.t for v in vals])})"
    if (name == "any" or name == "all") and len(vals) == 1 and is_list(vals[0].t) and key not in CALLS:
        return self.anyall(vals[0], name)
    if key in CALLS:
        spec = CALLS[key].split(":")
        r = spec[1] if spec[1] != "" else vals[0].t
        return self.rres(self.rt(spec[0], rtt(r), [self.rarg(v) for v in vals]), r)
    if len(vals) == 0:
        self.err(f"unsupported call {name}()")
    v = vals[0]
    t = v.t
    if is_kw(t) and name == "len":
        return Val(str(len(kw_names(t))), "int")
    if is_kw(t) and name == "dict" and len(vals) == 1:
        return self.kw_dict(v)  # (a new dict: CPython's dict(kwargs) copies it too)
    if name == "len":
        if t in self.classes and "__len__" in self.classes[t].methods:
            self.notnone(v, "TypeError: object of type 'NoneType' has no len()")
            return self.objlen(v)
        if t in self.nts:
            self.notnone(v, "TypeError: object of type 'NoneType' has no len()")
            return Val(str(len(self.classes[t].fields)), "int")
        if t == "str" and self.rtmode:
            # (tagged as the primitives' loads are, and bounded: LLVM then sees that index
            # arithmetic on lengths cannot overflow)
            return Val(self.ins(f"load i64, ptr {v.v}, !tbaa !{TBAA_LEN}, !range !{STRLEN_RANGE}"), "int")
        if t == "str" or is_list(t) or is_dict(t) or is_set(t):
            return Val(self.ins(f"load i64, ptr {v.v}"), "int")
        if is_tuple(t):
            return Val(str(len(targs(t))), "int")
    elif name == "str":
        return self.to_str(v)
    elif name == "repr":
        return self.repr(v)
    elif name == "ascii":
        return Val(self.rt("pys_ascii", "ptr", [f"ptr {self.repr(v).v}"]), "str")
    elif name == "bool":
        return Val(self.truth(v), "bool")
    elif name == "int" and len(vals) == 2 and t != "str":
        self.err("int() can't convert non-string with explicit base")
    elif name == "int" and (t == "int" or t == "bool"):
        return self.as_int(v)
    elif name == "float" and (t == "float" or t == "int" or t == "bool"):
        return self.as_float(v)
    elif name == "abs" and (t == "int" or t == "bool"):
        v = self.as_int(v)
        c = self.ins(f"icmp slt i64 {v.v}, 0")
        neg = self.iop("-", "0", v.v)
        return Val(self.select(c, Val(neg, "int"), v), "int")
    elif (name == "hex" or name == "oct" or name == "bin") and (t == "int" or t == "bool"):
        # format()'s alternate form: hex(x) is format(x, "#x"), and hex(True) is '0x1'
        return self.format_(self.as_int(v), mk("str", "#" + ("x" if name == "hex" else name[0]), self.line, []))
    elif (name == "min" or name == "max") and len(vals) == 1 and is_list(t) and keyv.t != "":
        return self.key_minmax(v, keyv, name)
    elif (name == "min" or name == "max") and len(vals) > 1 and keyv.t != "":
        return self.key_minmax2(vals, keyv, name)
    elif (name == "min" or name == "max") and len(vals) == 1 and is_list(t):
        d = self.sconst(self.desc(elem(t), ">" if name == "max" else "<"))
        r = self.rt("pys_list_minmax", "i64", [f"ptr {v.v}", f"ptr {d}", f"i64 {1 if name == 'max' else 0}"])
        return self.from_slot(r, elem(t))
    elif (name == "min" or name == "max") and len(vals) == 1:
        self.err(f"'{tname(t)}' object is not iterable")
    elif name == "min" or name == "max":
        for b in vals[1:]:
            t = t if self.join(t, b.t) == "" else self.join(t, b.t)  # (T and T | None: the comparison raises for None)
        v = self.coerce(v, t)
        for b in vals[1:]:
            b = self.coerce(b, t)
            gt = self.cmp2(">" if name == "max" else "<", b, v)
            v = Val(self.select(gt.v, Val(b.v, t), Val(v.v, t)), t)
        return v
    elif (name == "sorted" or name == "list") and is_list(t):
        c = v.v if fresh else self.rt("pys_list_copy", "ptr", [f"ptr {v.v}"])
        if name == "sorted" and keyv.t != "":
            self.key_sort(Val(c, t), keyv, rev, False)
        elif name == "sorted":
            self.rt("pys_list_sort_r", "void", [f"ptr {c}", f"ptr {self.sconst(self.desc(elem(t), '<'))}", f"i64 {rev}"])
        return Val(c, t)
    elif name == "divmod" and len(vals) == 2 and self.isnum(t) and self.isnum(vals[1].t):
        dn = self.as_int(v)
        dd = self.as_int(vals[1])
        if dn.t == "int" and dd.t == "int":
            return self.tuple_([self.arith("//", dn, dd), self.arith("%", dn, dd)])
        dn = self.as_float(dn)
        dd = self.as_float(dd)
        self.guard(self.ins(f"fcmp oeq double {dd.v}, 0.0"), "ZeroDivisionError: float divmod()")
        return self.tuple_([self.arith("//", dn, dd), self.arith("%", dn, dd)])
    elif name == "pow" and len(vals) == 2:
        return self.arith("**", v, vals[1])
    elif name == "pow" and len(vals) == 3 and self.as_int(v).t == "int":
        pm = [self.coerce(self.as_int(x), "int").v for x in vals]
        return Val(self.rt("pys_powmod", "i64", [f"i64 {pm[0]}", f"i64 {pm[1]}", f"i64 {pm[2]}"]), "int")
    elif name == "dict" and is_dict(t):
        # not d.copy(): dict(d) merges d into an empty dict, whose table can differ (runtime.c)
        return Val(self.rt("pys_dict_from", "ptr", [f"ptr {v.v}"]), t)
    elif name == "list" and is_dict(t):
        return Val(self.rt("pys_dict_keys", "ptr", [f"ptr {v.v}"]), self.ctype("list", [targs(t)[0]]))
    elif name == "range" or name == "enumerate" or name == "zip" or name == "reversed":
        self.err(f"{name}() is only supported in a for loop, after 'in', or as the argument of list(), sorted(), sum(), min(), max(), any(), all(), math.fsum(), math.prod() or str.join()")
    if name in self.gtypes or name in self.ltype:
        self.err(f"'{name}' is not callable")
    if (name == "hex" or name == "oct" or name == "bin") and t in self.classes and "__index__" in self.classes[t].methods:
        self.err(f"{name}() of an object is not supported: Pystachy does not call __index__")
    if t in self.classes and name in NONEARG:
        self.err(NONEARG[name].replace("NoneType", tname(t)))  # (CPython's TypeError: its class has no __len__, __abs__, ...)
    if name == "hex" or name == "oct" or name == "bin":
        self.err(NONEARG[name].replace("NoneType", tname(t)))
    if name == "type" and len(vals) == 1 and (t == "exc" or (t in self.classes and self.classes[t].exc != "")):
        self.err(f"unsupported call {key}: type(e) of an exception is supported as type(e).__name__ (and isinstance(e, C) tests its class)")
    self.err(f"unsupported call {key}")
    return v

def gen_vnode(self, v: Val) -> Node:
    # a node whose value is v, computed already: an argument of a call the compiler makes (the
    # key function's, key(item))
    self.vnodes.append(v)
    return mk("val", str(len(self.vnodes) - 1), self.line, [])

def gen_key_check(self, key: Val, of: str) -> None:
    # key= of sorted(), min(), max() or list.sort(): a function value or a Callable
    if is_opt(key.t) and is_callable(unopt(key.t)):
        self.err(f"a key that may be None ({typestr(key.t)}) is not supported (the key of {of}): test it with 'is not None' first")
    if not is_fn(key.t) and not is_callable(key.t):
        self.err(f"'{tname(key.t)}' object is not callable (the key of {of})")

def gen_call_key(self, key: Val, x: Val) -> Val:
    # key(x), the key of item x: a call through function value key, or of Callable key
    return self.call_value(key, [self.vnode(x)], "") if is_fn(key.t) else self.call_callable(key, [self.vnode(x)])

def gen_keys_of(self, xs: Val, key: Val) -> Val:
    # [key(x) for x in xs]: the keys of a sort, computed in order, as CPython computes them
    # before it sorts; xs is a list that no other code sees (a copy, or the items a list gave up)
    ks = self.rt("pys_list_new", "ptr", [f"i64 {self.ins(f'load i64, ptr {xs.v}')}"])
    ctr = self.alloca("int", "")
    self.emit(f"store i64 0, ptr {ctr}")
    lc = self.label()
    lb = self.label()
    le = self.label()
    lp = Loop("seq", lc, lb, lc, le)
    lp.seqs = [xs]
    lp.tests = [lb]
    lp.ctr = ctr
    self.fn.loops.append(lp)
    self.br(lc)
    self.place(lc)
    i = self.ins(f"load i64, ptr {ctr}")
    lp.idx = [i]
    self.cbr(self.ins(f"icmp slt i64 {i}, {self.ins(f'load i64, ptr {xs.v}')}"), lb, le)
    self.place(lb)
    item = self.from_slot(self.rt("pys_list_get", "i64", [f"ptr {xs.v}", f"i64 {i}"]), elem(xs.t))
    k = self.call_key(key, item)
    if "?" in k.t:
        self.err(f"the key function returns an empty container whose type is not known here ({typestr(k.t)})")
    self.rt("pys_list_append", "void", [f"ptr {ks}", "i64 " + self.to_slot(k)])
    self.emit(f"store i64 {self.ins(f'add i64 {i}, 1')}, ptr {ctr}")
    self.br(lc)
    self.place(le)
    return Val(ks, self.ctype("list", [k.t]))

def gen_key_sort(self, xs: Val, key: Val, rev: str, taken: bool) -> None:
    # sort list xs by key(item) (sorted(xs, key=...) of the copy xs, or xs.sort(key=...) of the
    # items a list gave up, taken: pys_list_take), reversed if rev: runtime.c sorts records of the
    # keys and the items by the keys (K), as CPython sorts its keys and moves the items along
    ks = self.keys_of(xs, key)
    p = self.rt("pys_list_keyed", "ptr", [f"ptr {xs.v}", f"ptr {ks.v}", f"i64 {1 if taken else 0}"])
    self.rt("pys_list_sort_r", "void", [f"ptr {p}", f"ptr {self.sconst('K' + self.desc(elem(ks.t), '<'))}", f"i64 {rev}"])
    if not taken:
        self.rt("pys_list_unkey", "void", [f"ptr {xs.v}", f"ptr {p}"])

def gen_key_minmax(self, xs: Val, key: Val, name: str) -> Val:
    # min(xs, key=...) and max(...): CPython calls the key on each item in turn and compares the
    # key with the best so far (key < best for min, key > best for max), keeping the first best
    # item; the list's length is read again at each step, as its iterator does
    et = elem(xs.t)
    best = self.alloca(et, "")
    ctr = self.alloca("int", "")
    self.emit(f"store i64 0, ptr {ctr}")
    lc = self.label()
    lb = self.label()
    lt_ = self.label()
    ln = self.label()
    le = self.label()
    lp = Loop("seq", lc, lb, lc, le)
    lp.seqs = [xs]
    lp.tests = [lb]
    lp.ctr = ctr
    self.fn.loops.append(lp)
    self.br(lc)
    self.place(lc)
    i = self.ins(f"load i64, ptr {ctr}")
    lp.idx = [i]
    self.cbr(self.ins(f"icmp slt i64 {i}, {self.ins(f'load i64, ptr {xs.v}')}"), lb, le)
    self.place(lb)
    item = self.from_slot(self.rt("pys_list_get", "i64", [f"ptr {xs.v}", f"i64 {i}"]), et)
    self.emit(f"store i64 {self.ins(f'add i64 {i}, 1')}, ptr {ctr}")
    k = self.call_key(key, item)
    if "?" in k.t or k.t == "None":
        self.err(f"comparing the keys of {name}() is not supported: its key function returns {typestr(k.t)}")
    bk = self.alloca(k.t, "")
    # the first item is the best so far; each other is if its key compares so with the best's
    first = self.ins(f"icmp eq i64 {i}, 0")
    lf = self.label()
    self.cbr(first, ln, lf)
    self.place(lf)
    c = self.cmp2(">" if name == "max" else "<", k, Val(self.ins(f"load {lt(k.t)}, ptr {bk}"), k.t))
    self.cbr(self.truth(c), ln, lt_)
    self.place(ln)
    self.emit(f"store {lt(et)} {item.v}, ptr {best}")
    self.emit(f"store {lt(k.t)} {k.v}, ptr {bk}")
    self.br(lt_)
    self.place(lt_)
    self.br(lc)
    self.place(le)
    self.guard(self.ins(f"icmp eq i64 {self.ins(f'load i64, ptr {ctr}')}, 0"), f"ValueError: {name}() iterable argument is empty")
    return Val(self.ins(f"load {lt(et)}, ptr {best}"), et)

def gen_key_minmax2(self, vals: list[Val], key: Val, name: str) -> Val:
    # min(a, b, ..., key=f) and max(...): the key of each argument in turn, compared with the
    # best's so far (as key_minmax does)
    t = vals[0].t
    for b in vals[1:]:
        t = t if self.join(t, b.t) == "" else self.join(t, b.t)
    best = self.coerce(vals[0], t)
    bk = self.call_key(key, vals[0])
    for b in vals[1:]:
        kb = self.call_key(key, b)
        kt = bk.t if kb.t == bk.t else self.join(bk.t, kb.t)
        if kt == "" or "?" in kt or kt == "None":
            self.err(f"comparing the keys of {name}()'s arguments is not supported: they are {typestr(bk.t)} and {typestr(kb.t)}")
        c = self.truth(self.cmp2(">" if name == "max" else "<", kb, bk))
        best = Val(self.select(c, self.coerce(b, t), best), t)
        bk = Val(self.select(c, self.coerce(kb, kt), self.coerce(bk, kt)), kt)
    return best

def gen_anyall(self, v: Val, name: str) -> Val:
    # any(xs) / all(xs) by each item's truth, stopping at the first item that decides
    res = self.alloca("bool", "")
    self.emit(f"store i1 {'false' if name == 'any' else 'true'}, ptr {res}")
    ctr = self.alloca("int", "")
    self.emit(f"store i64 0, ptr {ctr}")
    lc = self.label()
    lb = self.label()
    hit = self.label()
    ls = self.label()
    le = self.label()
    lp = Loop("seq", lc, lb, ls, le)
    lp.seqs = [v]
    lp.tests = [lb]
    lp.ctr = ctr
    self.fn.loops.append(lp)
    self.place(lc)
    i = self.ins(f"load i64, ptr {ctr}")
    lp.idx = [i]
    self.cbr(self.ins(f"icmp slt i64 {i}, {self.ins(f'load i64, ptr {v.v}')}"), lb, le)
    self.place(lb)
    c = self.truth(self.from_slot(self.rt("pys_list_get", "i64", [f"ptr {v.v}", f"i64 {i}"]), elem(v.t)))
    if name == "any":
        self.cbr(c, hit, ls)
    else:
        self.cbr(c, ls, hit)
    self.place(hit)
    self.emit(f"store i1 {'true' if name == 'any' else 'false'}, ptr {res}")
    self.br(le)
    self.place(ls)
    self.emit(f"store i64 {self.ins(f'add i64 {i}, 1')}, ptr {ctr}")
    self.br(lc)
    self.place(le)
    return Val(self.ins(f"load i1, ptr {res}"), "bool")

def gen_stream_start(self, name: str, args: list[Node]) -> str:
    # whether sum(), min() or max() takes its items as they come (reduce), "-" if not: of a
    # generator expression or an iterator call (range(), zip(), ...), with no keyword (key=
    # keeps its list). Then sum's start type ("" where none is given), which must be an int or
    # a float (dry: the value is evaluated where the iterator is made, after the traversal is
    # compiled)
    if len(args) == 0 or len(args) > (2 if name == "sum" else 1):
        return "-"
    for a in args:
        if a.kind == "kw" or a.kind == "starred" or a.kind == "dstar":
            return "-"
    g = args[0]
    if not self.iterator_call(g) and not (g.kind == "listcomp" and g.s == "gen"):
        return "-"
    if len(args) == 1:
        return ""
    t = self.dry(args[1])
    return t if t == "int" or t == "float" else "-"

def gen_reduce(self, name: str, args: list[Node], stt: str) -> Val:
    # sum(), min() or max() of a generator expression or an iterator call: each item is added
    # or compared as it comes, as CPython takes them, and no list of them is made (#88). The
    # iterator is made first, then sum's start is evaluated and the accumulators set (at the
    # IterArg's split, once the traversal, compiled first, gave the items' type), then the
    # items are traversed. A sum is runtime.c's (pys_sum_int, pys_sum_float, ...), item by
    # item; min() and max() compare as max(a, b) does, but those of items other than numbers
    # and strs collect them for pys_list_minmax, as before
    g = args[0]
    if g.kind != "listcomp":
        item = mk("name", "__item", g.line, [])
        g = mk("listcomp", "gen", g.line, [item, item, g])
    key = str(len(self.reds))
    r = Reduce(name, stt)
    self.reds[key] = r
    arg = IterArg(g)
    arg.split = self.label()
    self.listcomp(g, "", "#" + key, "", arg)
    back = self.label()
    self.br(back)
    self.place(arg.split)
    if r.t == "":
        self.err("cannot infer the element type of this comprehension")
    if name == "sum":
        sv = self.expr(args[1], "") if len(args) == 2 else Val("0" if r.t != "float" else fbits("0.0"), "int" if r.t != "float" else "float")
        if r.t == "float":
            self.emit(f"store double {self.as_float(sv).v}, ptr {r.acc}")
            self.emit(f"store double {fbits('0.0')}, ptr {r.comp}")
            if r.first != "":
                self.emit(f"store i1 true, ptr {r.first}")
        elif sv.t == "float":
            self.emit(f"store double {sv.v}, ptr {r.acc}")
        else:
            self.emit(f"store i64 {self.as_int(sv).v}, ptr {r.acc}")
    elif r.collect:
        self.emit(f"store ptr {self.rt('pys_list_new', 'ptr', ['i64 0'])}, ptr {r.acc}")
    else:
        self.emit(f"store i1 true, ptr {r.first}")
    self.br(arg.trav)
    self.place(back)
    if name != "sum" and r.collect:
        d = self.sconst(self.desc(r.t, ">" if name == "max" else "<"))
        lv = self.ins(f"load ptr, ptr {r.acc}")
        return self.from_slot(self.rt("pys_list_minmax", "i64", [f"ptr {lv}", f"ptr {d}", f"i64 {1 if name == 'max' else 0}"]), r.t)
    if name != "sum":
        self.guard(self.ins(f"load i1, ptr {r.first}"), f"ValueError: {name}() iterable argument is empty")
        return Val(self.ins(f"load {lt(r.t)}, ptr {r.acc}"), r.t)
    if r.comp == "":
        ft = "float" if r.stt == "float" else "int"
        return Val(self.ins(f"load {lt(ft)}, ptr {r.acc}"), ft)
    # fsum's end: the compensation is added where it is a finite number other than 0
    s = self.ins(f"load double, ptr {r.acc}")
    c = self.ins(f"load double, ptr {r.comp}")
    fin = self.ins(f"fcmp olt double {self.rt('fabs', 'double', [f'double {c}'])}, 0x7FF0000000000000")
    nz = self.ins(f"fcmp une double {c}, {fbits('0.0')}")
    use = self.ins(f"and i1 {nz}, {fin}")
    return Val(self.select(use, Val(self.ins(f"fadd double {s}, {c}"), "float"), Val(s, "float")), "float")

def gen_reduce_item(self, r: Reduce, e: Node) -> None:
    # an item of reduce()'s generator: added to the sum, or compared with the item kept. Its
    # accumulators are made at its first compilation, which gives the items' type
    v = self.expr(e, "")
    if r.t == "":
        r.t = v.t
        if r.name == "sum" and v.t != "int" and v.t != "bool" and v.t != "float":
            self.err(f"unsupported call sum(list[{v.t}]{',' + r.stt if r.stt != '' else ''})")
        if r.name == "sum":
            r.acc = self.alloca("float" if v.t == "float" or r.stt == "float" else "int", "")
            if v.t == "float":
                r.comp = self.alloca("float", "")
                if r.stt == "int":
                    r.first = self.alloca("bool", "")
        elif v.t == "int" or v.t == "float" or v.t == "bool" or v.t == "str":
            r.acc = self.alloca(v.t, "")
            r.first = self.alloca("bool", "")
        else:
            r.collect = True
            r.acc = self.alloca(self.ctype("list", [v.t]), "")
    if r.collect:
        self.rt("pys_list_append", "void", [f"ptr {self.ins(f'load ptr, ptr {r.acc}')}", "i64 " + self.to_slot(self.coerce(v, r.t))])
        return
    if r.name != "sum":
        # the first item is kept; another where it is greater (max) or less (min) than the kept one
        take = self.label()
        test = self.label()
        skip = self.label()
        self.cbr(self.ins(f"load i1, ptr {r.first}"), take, test)
        self.place(test)
        kept = Val(self.ins(f"load {lt(r.t)}, ptr {r.acc}"), r.t)
        self.cbr(self.truth(self.cmp2(">" if r.name == "max" else "<", v, kept)), take, skip)
        self.place(take)
        self.emit(f"store {lt(r.t)} {v.v}, ptr {r.acc}")
        self.emit(f"store i1 false, ptr {r.first}")
        self.br(skip)
        self.place(skip)
        return
    if r.t != "float" and r.stt != "float":
        si = self.ins(f"load i64, ptr {r.acc}")
        self.emit(f"store i64 {self.iop('+', si, self.as_int(v).v)}, ptr {r.acc}")
        return
    if r.t != "float":
        # ints from a float start: added as floats, not compensated (pys_sum_int_float)
        sf = self.ins(f"load double, ptr {r.acc}")
        self.emit(f"store double {self.ins(f'fadd double {sf}, {self.as_float(self.as_int(v)).v}')}, ptr {r.acc}")
        return
    nm = self.label()
    if r.first != "":
        # floats from an int start: the first is added as it is (pys_sum_float_int)
        plain = self.label()
        comp = self.label()
        self.cbr(self.ins(f"load i1, ptr {r.first}"), plain, comp)
        self.place(plain)
        s0 = self.ins(f"load double, ptr {r.acc}")
        self.emit(f"store double {self.ins(f'fadd double {s0}, {v.v}')}, ptr {r.acc}")
        self.emit(f"store i1 false, ptr {r.first}")
        self.br(nm)
        self.place(comp)
    # Neumaier's step, as runtime.c's fsum takes it
    s = self.ins(f"load double, ptr {r.acc}")
    t = self.ins(f"fadd double {s}, {v.v}")
    ge = self.ins(f"fcmp oge double {self.rt('fabs', 'double', [f'double {s}'])}, {self.rt('fabs', 'double', [f'double {v.v}'])}")
    d1 = self.ins(f"fadd double {self.ins(f'fsub double {s}, {t}')}, {v.v}")
    d2 = self.ins(f"fadd double {self.ins(f'fsub double {v.v}, {t}')}, {s}")
    d = self.select(ge, Val(d1, "float"), Val(d2, "float"))
    c = self.ins(f"load double, ptr {r.comp}")
    self.emit(f"store double {self.ins(f'fadd double {c}, {d}')}, ptr {r.comp}")
    self.emit(f"store double {t}, ptr {r.acc}")
    self.br(nm)
    self.place(nm)

def gen_iterator_call(self, n: Node) -> bool:
    if n.kind != "call" or n.kids[0].kind != "name" or self.bound(n.kids[0].s):
        return False
    fn = n.kids[0].s
    return fn == "range" or fn == "reversed" or fn == "enumerate" or fn == "zip"

def gen_is_mapcall(self, n: Node) -> bool:
    # map(...) or filter(...) of the builtins
    return n.kind == "call" and n.kids[0].kind == "name" and (n.kids[0].s == "map" or n.kids[0].s == "filter") and not self.bound(n.kids[0].s)

def gen_mapgen(self, n: Node) -> Node:
    # map(f, xs, ...) or filter(f, xs) where a consumer takes its items (list(), sum(), "".join(),
    # ...): the generator expression it is, (f(x) for x in xs), with zip() for several
    # iterables, or (x for x in xs if f(x)) (if x, for filter(None, xs)), whose f is evaluated
    # now, before the iterables, as CPython evaluates map's arguments
    fn = n.kids[0].s
    args = n.kids[1:]
    line = n.line
    for a in args:
        if a.kind == "kw" or a.kind == "starred" or a.kind == "dstar":
            self.err(f"{fn}() takes positional arguments only here")
    if fn == "map" and len(args) < 2:
        self.err("map() must have at least two arguments.")
    if fn == "filter" and len(args) != 2:
        self.err(f"filter expected 2 arguments, got {len(args)}")
    f = args[0] if fn == "filter" and args[0].kind == "None" else self.vnode(self.expr(args[0], ""))
    if fn == "filter":
        cond = mk("name", "__item", line, []) if f.kind == "None" else mk("call", "", line, [f, mk("name", "__item", line, [])])
        return mk("listcomp", "gen", line, [mk("name", "__item", line, []), mk("name", "__item", line, []), args[1], cond])
    if len(args) == 2:
        return mk("listcomp", "gen", line, [mk("call", "", line, [f, mk("name", "__item", line, [])]), mk("name", "__item", line, []), args[1]])
    if self.bound("zip"):
        self.err("map() of several iterables is not supported where zip is bound")
    items = [mk("name", f"__item{i}", line, []) for i in range(len(args) - 1)]
    elt = mk("call", "", line, [f] + [mk("name", x.s, line, []) for x in items])
    return mk("listcomp", "gen", line, [elt, mk("tuple", "", line, items), mk("call", "", line, [mk("name", "zip", line, [])] + args[1:])])

def gen_consume(self, n: Node, want: str, arg: IterArg | None = None) -> Val:
    # range(), reversed(), enumerate(), zip() and generator expressions where their items are
    # used at once (list(), sorted(), "".join(), ...) become a fresh list of those items, built
    # by the for loop machinery; anywhere else they are rejected, as a list would behave
    # differently. arg: evaluated once the iterator is made, before it is iterated
    if self.is_mapcall(n):
        n = self.mapgen(n)
    if n.kind == "listcomp":
        return self.listcomp(n, want, "", "", arg)
    if not self.iterator_call(n):
        return self.expr(n, want)
    if n.kids[0].s == "range":
        vs = self.range_args(n.kids[1:])
        r = Val(self.rt("pys_range_list", "ptr", [f"i64 {vs[0]}", f"i64 {vs[1]}", f"i64 {vs[2]}"]), "list[int]")
        self.iterarg(arg)
        return r
    it = mk("name", "__item", n.line, [])
    return self.listcomp(mk("listcomp", "", n.line, [it, mk("name", "__item", n.line, []), n]), want, "", "", arg)

def gen_as_list(self, v: Val, name: str) -> Val:
    # sorted(d), max(t), ...: a dict's keys, or the items of a tuple (or NamedTuple) of one item
    # type, as a list, or the list an object's __iter__ steps through (which list() copies)
    if is_kw(v.t):
        return self.kw_list(v)  # (the names of **kwargs)
    if v.t in self.nts:
        self.notnone(v, "TypeError: 'NoneType' object is not iterable")
        v = self.ntup(v, True)
    if v.t in self.classes:
        items = self.obj_iter(v, "TypeError: can only join an iterable" if name == "join" else "TypeError: 'NoneType' object is not iterable",
                              "can only join an iterable" if name == "join" else f"'{tname(v.t)}' object is not iterable")
        if (name == "list" or name == "sorted" or name == "extend") and "__len__" in self.classes[v.t].methods:
            self.objlen(v)  # (a length hint: CPython's list() calls __len__ once __iter__ has run)
        return items
    if is_dict(v.t):
        return Val(self.rt("pys_dict_keys", "ptr", [f"ptr {v.v}"]), self.ctype("list", [targs(v.t)[0]]))
    if is_set(v.t):
        return Val(self.rt("pys_set_list", "ptr", [f"ptr {v.v}"]), self.ctype("list", [selem(v.t)]))
    if is_tuple(v.t):
        ts = targs(v.t)
        et = ts[0] if len(ts) > 0 else "str" if name == "join" else "int"  # (the empty tuple: no item to type)
        if any(x != et for x in ts):
            if (name == "math.fsum" or name == "math.dist") and all(self.isnum(x) for x in ts):
                et = "float"  # (they make a float of each item: (1, 2.5) too)
            else:
                self.err(f"{name}() of a {v.t} needs items of a single type")
        r = self.rt("pys_list_new", "ptr", [f"i64 {len(ts)}"])
        for i in range(len(ts)):
            item = self.tget(v, i)
            self.rt("pys_list_append", "void", [f"ptr {r}", "i64 " + self.to_slot(self.as_float(item) if et == "float" else item)])
        return Val(r, self.ctype("list", [et]))
    if v.t == "str" and (name == "sorted" or name == "min" or name == "max" or name == "join"):
        return Val(self.rt("pys_str_list", "ptr", [f"ptr {v.v}"]), "list[str]")
    if v.t == "file":
        return Val(self.rt("pys_file_readlines", "ptr", [f"ptr {v.v}"]), "list[str]")
    return v

def gen_reverse_arg(self, n: Node, name: str) -> str:
    return self.reverse_val(self.expr(n, "bool"), name)

def gen_reverse_val(self, r: Val, name: str) -> str:
    # sorted(..., reverse=r) and list.sort(reverse=r): r is a bool or an int, as in CPython
    if r.t != "bool" and r.t != "int":
        self.err(f"{name}() argument 'reverse' must be a bool, not {tname(r.t)}")
    return self.ins(f"zext i1 {self.truth(r)} to i64")

def gen_parse_expr(self, text: str) -> Node:
    return Parser(Lexer(text, self.line).run()).test()

def gen_print_(self, args: list[Node]) -> Val:
    # every argument is evaluated in the order written, then each is converted as it is
    # written; sys.stdout and sys.stderr directly, any other file through its checks, and an
    # object with write() (io.StringIO) through that method, a call for each piece
    sep = self.sconst(" ")
    end = self.sconst("\n")
    fd = "1"
    fv = ""
    fo = Val("", "")
    flush = ""
    vals: list[Val] = []
    temp: list[Node] = []  # file=open(...): closed after the print, as close_temp does
    for a in args:
        if a.kind != "kw":
            vals.append(self.expr(a, ""))
            continue
        x = a.kids[0]
        if a.s == "sep" or a.s == "end":
            if x.kind != "None":
                v = self.expr(x, "str")
                if is_opt(v.t):
                    # None is the default
                    v = Val(self.select(self.isnull(v), Val(sep if a.s == "sep" else end, "str"), Val(v.v, "str")), "str")
                sv = self.coerce(v, "str").v
                if a.s == "sep":
                    sep = sv
                else:
                    end = sv
        elif a.s == "file":
            p = self.dotted(x)
            if p == "sys.stdout" or p == "sys.stderr":
                fd = "2" if p == "sys.stderr" else "1"
            elif x.kind != "None":
                v = self.expr(x, "file")
                if v.t in self.classes and "write" in self.classes[v.t].methods:
                    fo = v
                elif v.t != "file":
                    self.err(f"print(file=...) needs a file, or an object with a write() method, not {v.t}")
                else:
                    fv = v.v
                    temp.append(x)
        elif a.s == "flush":
            flush = self.truth(self.expr(x, "bool"))
        else:
            self.err(f"print() got an unexpected keyword argument '{a.s}'")
    for i in range(len(vals)):
        if i > 0:
            self.pwrite(fd, fv, sep, fo)
        self.pwrite(fd, fv, self.to_str(vals[i]).v, fo)
    self.pwrite(fd, fv, end, fo)
    if flush != "" and fo.t != "" and "flush" not in self.classes[fo.t].methods:
        # CPython looks flush() up only where flush is true
        self.guard(flush, f"AttributeError: '{tname(fo.t)}' object has no attribute 'flush'")
    elif flush != "":
        l1 = self.label()
        l2 = self.label()
        self.cbr(flush, l1, l2)
        self.place(l1)
        if fo.t != "":
            self.call(mk("call", "", self.line, [mk("attr", "flush", self.line, [self.vnode(fo)])]), "")
        else:
            self.rt("pys_file_flush", "void", [f"ptr {fv if fv != '' else self.rt('pys_std', 'ptr', [f'i64 {fd}'])}"])
        self.br(l2)
        self.place(l2)
    for x in temp:
        self.close_temp(x, Val(fv, "file"))
    return Val("null", "None")

def gen_pwrite(self, fd: str, fv: str, s: str, fo: Val) -> None:
    if fo.t != "":
        # file.write(s): what it returns is not used
        self.call(mk("call", "", self.line, [mk("attr", "write", self.line, [self.vnode(fo)]), self.vnode(Val(s, "str"))]), "")
    elif fv != "":
        self.rt("pys_file_write", "i64", [f"ptr {fv}", f"ptr {s}"])
    else:
        self.rt("pys_write", "void", [f"ptr {s}", f"i64 {fd}"])

def gen_bmethod(self, o: Val, m: str, args: list[Node], first: bool = False) -> Val:
    # (first: s.split(...)[0], which index() asks for: only the first part, a str)
    if is_set(o.t):
        return self.smethod(o, m, args)
    if is_list(o.t) and m == "sort":
        rev = "0"
        keyv = Val("", "")
        for a in args:
            if a.kind != "kw":
                self.err("list.sort() takes no positional arguments")
            elif a.s == "reverse":
                rev = self.reverse_arg(a.kids[0], "sort")
            elif a.s == "key":
                keyv = self.expr(a.kids[0], "")
                if keyv.t != "None":
                    self.key_check(keyv, "sort()")
            else:
                self.err(f"sort() got an unexpected keyword argument '{a.s}'")
        if keyv.t != "" and keyv.t != "None":
            # the list gives its items up while the keys are computed (pys_list_take)
            taken = Val(self.rt("pys_list_take", "ptr", [f"ptr {o.v}"]), o.t)
            self.key_sort(taken, keyv, rev, True)
            self.rt("pys_list_give", "void", [f"ptr {taken.v}"])
            return Val("null", "None")
        self.rt("pys_list_sort_r", "void", [f"ptr {o.v}", f"ptr {self.sconst(self.desc(elem(o.t), '<'))}", f"i64 {rev}"])
        return Val("null", "None")
    if is_dict(o.t) and m == "update":
        return self.update(o, args)
    for a in args:
        if a.kind == "kw":
            self.err(f"keyword arguments to {tname(o.t)}.{m}() are not supported; pass them by position")
    if is_list(o.t) and m == "extend" and len(args) == 1 and self.is_mapcall(args[0]):
        args = [self.mapgen(args[0])]
    if is_list(o.t) and m == "extend" and len(args) == 1 and args[0].kind == "listcomp" and args[0].s == "gen":
        # each item is appended as the generator yields it: the items before a raise stay, and
        # the generator sees those it added (xs.extend(f(x) for x in xs))
        self.listcomp(args[0], o.t, "", o.v)
        return Val("null", "None")
    if is_dict(o.t) and m == "pop" and len(args) == 2:
        kv = targs(o.t)
        kx = self.dkey(self.expr(args[0], kv[0]), kv[0])
        k = self.to_slot(kx)
        d = self.expr(args[1], kv[1])
        vt = self.optdefault(d, kv[1])  # (d.pop(k, None): V | None)
        dv = self.to_slot(self.coerce(d, vt))
        fn = "pys_dict_popbox" if is_sopt(vt) and not is_sopt(kv[1]) else "pys_dict_pop_default"  # (an int's box)
        return self.from_slot(self.nonekey(kx, dv, fn, [f"ptr {o.v}", f"i64 {k}", f"i64 {dv}"]), vt)
    base = o.t
    T = ""
    K = ""
    V = ""
    if is_list(o.t):
        base = "list"
        T = elem(o.t)
    elif is_dict(o.t):
        base = "dict"
        kv = targs(o.t)
        K = kv[0]
        V = kv[1]
    elif o.t == "bool" and "int." + m in METHODS:
        base = "int"  # (a bool is an int: True.bit_length() is 1)
        o = self.as_int(o)
    key = base + "." + m
    if key not in METHODS and o.t == "exc":
        self.err(f"BaseException.{m}() is not supported (of a builtin exception, str(e), repr(e) and formatting are)")
    if key not in METHODS:
        self.err(f"'{o.t}' has no method '{m}'")
    if key == "dict.get" and (len(args) == 0 or len(args) > 2):
        # (CPython's TypeError; not left to the arity check below, as d.get(k, d2, None) would
        # read as d.get(k, None))
        self.err(f"get expected at {'least 1 argument' if len(args) == 0 else 'most 2 arguments'}, got {len(args)}")
    # d.get(k) and d.get(k, None): the value or None, for values that can be None
    optget = key == "dict.get" and (len(args) == 1 or args[-1].kind == "None") and V not in self.classes and self.optional(V) != ""
    if optget:
        args = args[:1]
    if key == "dict.get" and (len(args) == 1 or args[-1].kind == "None") and V not in self.classes and not optget:
        self.err(f"dict.get(key{', None' if len(args) == 2 else ''}) needs values that can be None ({OPTTYPES}), not {typestr(V)}: give another default")
    spec = METHODS[key]
    c = spec.find(":")
    av = [f"{lt(o.t)} {o.v}"]
    nones: list[str] = []  # optional str arguments: None raises (nmsg) once all are evaluated
    nmsg: list[str] = []
    dt = T  # the item type the # descriptor describes
    kx = Val("", "")  # a dict's key that may be None (see nonekey)
    bk = Val("", "")  # d.pop(k) of a bool where the keys are ints (bool_find)
    numx = Val("", "")  # xs.index(x), count(x) or remove(x) of a number x of another type
    numok = "true"  # (whether an item can equal it, see numkey)
    alts = Val("", "")  # s.startswith((a, b)) or endswith: the tuple whose items are tried (affix_any)
    i = 0
    for p in spec[c + 1 :].split(","):
        if p == "":
            continue
        if p == "#":
            self.exc_eq(dt)
            av.append(f"ptr {self.sconst(self.desc(dt, '=='))}")  # (count, index, remove)
            continue
        dflt = ""
        e = p.find("=")
        if e >= 0:
            dflt = p[e + 1 :]
            p = p[:e]
        slot = p.startswith("*")
        pt = self.subst(p[1:] if slot else p, T, K, V, o.t)
        # a str method's start or end (find, count, startswith, ...) that is None is omitted
        span = base == "str" and p == "int" and (dflt == "0" or dflt == "9223372036854775807")
        if i < len(args) and dflt == "null" and args[i].kind == "None":
            av.append(rtt(pt) + " null")  # an explicit None: the default
        elif i < len(args) and span and args[i].kind == "None":
            av.append("i64 " + dflt)
        elif i < len(args):
            if key == "dict.get" and i == 0 and self.lookup_key(args[0]):
                self.stkkey = args[0]  # (memo.get((i, j), -1))
            v = self.consume(args[i], pt) if key == "str.join" or key == "list.extend" else self.expr(args[i], pt)
            self.stkkey = self.nokey
            if (key == "str.startswith" or key == "str.endswith") and i == 0 and (is_tuple(unopt(v.t)) or v.t in self.nts):
                v = self.ntup(v)  # (a NamedTuple: the tuple of its fields, None if it is None)
                for x in targs(unopt(v.t)):
                    if x != "str" and x != "opt[str]":
                        self.err(f"tuple for {m} must only contain str, not {tname(x)}")  # (CPython's TypeError, at the item it reaches)
                if is_opt(v.t):
                    nones.append(v.v)
                    nmsg.append(self.none_arg(m, 1))
                alts = Val(v.v, unopt(v.t))
                v = Val("null", "str")  # (each item in its place, in affix_any)
            if is_opt(v.t) and (key == "str.join" or key == "list.extend" or key == "file.writelines"):
                v = self.unwrap(v, "TypeError: can only join an iterable" if key == "str.join" else "TypeError: 'NoneType' object is not iterable")
            if key == "str.join" or (key == "list.extend" and v.t in self.classes):
                v = self.as_list(v, "join" if key == "str.join" else "extend")
            if (key == "str.join" or key == "file.writelines") and v.t == "list[opt[str]]":
                v = Val(v.v, "list[str]")  # (an item that is None raises when it runs, as CPython's error)
            if key == "str.join" and is_list(v.t) and elem(v.t) != "str" and "?" not in v.t:
                self.err(f"sequence item 0: expected str instance, {tname(elem(v.t))} found")  # (CPython's TypeError)
            if key == "list.extend" and is_list(v.t) and v.t != pt and self.wider(v.t, pt) == pt:
                v = Val(v.v, pt)  # (its items are copied: list[str] extends a list[str | None])
            if span and is_sopt(v.t) and unopt(v.t) != "float":
                v = Val(self.optint(v, dflt), "int")
            if p == "int":
                v = self.as_int(v)  # an index or a count may be a bool, as in CPython
            if base == "dict" and i == 0 and is_opt(v.t) and ((unopt(v.t) == K and (m == "get" or m == "pop")) or (bool_for_int(unopt(v.t), K) and is_sopt(v.t) and m == "get")):
                kx = v  # (a bool | None gets the int key it equals, raising no KeyError that would name it)
                pt = v.t
            elif base == "dict" and i == 0 and (m == "get" or m == "pop"):
                if m == "pop" and bool_for_int(v.t, K):
                    bk = v
                v = self.dkey(v, K)
            elif key == "dict.setdefault" and i == 0 and bool_for_int(v.t, K):
                self.store_key(v, K)  # (rejected)
            elif key == "dict.get" and i == 1 and self.optdefault(v, V) != V:
                pt = self.optdefault(v, V)  # d.get(k, default) with a default that may be None: V | None
                optget = True
            if base == "list" and p == "*T" and self.isnum(v.t) and self.isnum(unopt(T)) and v.t != unopt(T) and (m == "index" or m == "count" or m == "remove"):
                numx = v
                nk = self.numkey(v, unopt(T))
                v = Val(nk[0], unopt(T))
                numok = nk[1]
            if is_opt(v.t) and unopt(v.t) == pt and dflt == "null":
                v = Val(v.v, pt)  # None is the default
            elif is_opt(v.t) and not slot and unopt(v.t) == pt == "str":
                nones.append(v.v)
                nmsg.append(self.none_arg(m, i + 1))
                v = Val(v.v, pt)
            elif (is_opt(v.t) or v.t == "None") and slot and p == "*T" and (unopt(v.t) == T or (v.t == "None" and T not in self.classes)) and base == "list" and m != "append" and m != "insert" and self.optional(T) != "" and not self.isnum(T):
                pt = self.optional(T)  # xs.index(None): found where xs holds None, as == finds it
                dt = pt
            v = self.coerce(v, pt, f"argument {i + 1} of {tname(o.t)}.{m}()" if is_opt(v.t) else "")
            av.append("i64 " + self.to_slot(v) if slot else self.rarg(v))
        elif dflt != "":
            av.append(("i64 " if slot else rtt(pt) + " ") + dflt)
        else:
            self.err(f"missing argument for {m}()")
        i += 1
    if i < len(args):
        self.err(f"too many arguments for {m}()")
    for j in range(len(nones)):
        self.guard(self.ins(f"icmp eq ptr {nones[j]}, null"), nmsg[j])
    if alts.t != "":
        return self.affix_any(alts, m, av)
    r = spec[:c]
    slot = r.startswith("*")
    rtype = self.subst(r[1:] if slot else r, T, K, V, o.t)
    if optget:
        rtype = self.optional(V)
    fn = f"pys_{base}_{m}"
    if first:
        fn = "pys_str_split_first"
        rtype = "str"
    if optget and is_sopt(rtype) and not is_sopt(V):
        fn = "pys_dict_getbox"  # (the value's box: an int | None)
    if numok != "true" and m == "remove":
        self.guard(self.ins(f"xor i1 {numok}, true"), "ValueError: list.remove(x): x not in list")
    if numx.t != "" and m == "index":
        fn = "pys_list_index_as"  # (its ValueError names x, not the item)
        av = av + ["i64 " + self.to_slot(Val(numok, "bool")), "i64 " + self.to_slot(numx), f"ptr {self.sconst(self.desc(numx.t, '=='))}"]
    if bk.t != "":
        self.bool_find(o.v, bk, av[1][4:])
    if kx.t != "":
        res = self.nonekey(kx, av[2][4:] if m == "get" else "", fn, av)
    else:
        res = self.rt(fn, "i64" if slot else rtt(rtype), av)
    if numok != "true" and m == "count":
        res = self.select(numok, Val(res, "int"), Val("0", "int"))
    if slot:
        return self.from_slot(res, rtype)
    return self.rres(res, rtype)

def gen_update(self, o: Val, args: list[Node]) -> Val:
    # d.update(x, k=v, ...): x a dict of d's type, merged as CPython merges one (runtime.c), or
    # a list of (key, value) tuples, set one by one; then the keywords (str keys), merged as
    # the dict CPython makes of them, which is a display's. The arguments are evaluated first
    kv = targs(o.t)
    pairs = self.ctype("list", [self.ctype("tuple", kv)])
    pos = [a for a in args if a.kind != "kw"]
    kws: list[Node] = []
    for a in args:
        if a.kind == "kw":
            kws.append(mk("str", a.s, a.line, []))
            kws.append(a.kids[0])
    if len(pos) > 1:
        self.err(f"update expected at most 1 argument, got {len(pos)}")
    if len(kws) > 0 and kv[0] != "str":
        self.err(f"dict.update() with keyword arguments adds str keys, which a {typestr(o.t)} cannot hold")
    x = Val("", "")
    if len(pos) == 1:
        x = self.expr(pos[0], pairs if pos[0].kind == "list" or pos[0].kind == "listcomp" else o.t)
    kw = self.expr(mk("dict", "", self.line, kws), o.t) if len(kws) > 0 else Val("", "")
    if is_opt(x.t):
        x = self.unwrap(x, "TypeError: 'NoneType' object is not iterable")
    if x.t == "int" or x.t == "float" or x.t == "bool" or x.t == "None":
        self.err(f"'{tname(x.t)}' object is not iterable")  # (CPython's TypeError)
    if x.t != "" and x.t != o.t and x.t != pairs:
        self.err(f"dict.update() of a {typestr(o.t)} takes a dict of its type, a {typestr(pairs)} or keyword arguments, not {typestr(x.t)}")
    if x.t != "":
        self.rt("pys_dict_update" if x.t == o.t else "pys_dict_update_pairs", "void", [f"ptr {o.v}", f"ptr {x.v}"])
    if kw.t != "":
        self.rt("pys_dict_update", "void", [f"ptr {o.v}", f"ptr {kw.v}"])
    return Val("null", "None")

# ---- sets: runtime.c's, which make them as CPython's setobject.c does
