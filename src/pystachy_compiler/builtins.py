"""Builtins component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.utils import is_union, umembers
from src.pystachy_compiler.ir import Data, Ins, IterArg, Loop, Reduce, Val
from src.pystachy_compiler.lexer import Lexer
from src.pystachy_compiler.names import short
from src.pystachy_compiler.parser import Parser
from src.pystachy_compiler.reflection import VARS_USES
from src.pystachy_compiler.specs import (
    ARITY,
    CALLS,
    DEFAULTS,
    ERRNO,
    FLOATINFO,
    FROZENERR,
    FROZENUSE,
    GALIAS,
    GALIASUSE,
    IMPLEMENTATION,
    ITERS,
    METHODS,
    MODATTRS,
    MODFUNCS,
    NONEARG,
    NONERET,
    NONEVAR,
    OPTARG,
    OPTCALLS,
    OPTTYPES,
    OSCONST,
    PYBUILTINS,
    RANGEC,
    RANGES,
    TYPESMOD,
    TYPESUSE,
    VERSIONINFO,
)
from src.pystachy_compiler.syntax import Node, made_var, mk
from src.pystachy_compiler.utils import (
    atomic_dict,
    atomic_list,
    bool_for_int,
    elem,
    fbits,
    is_callable,
    is_dict,
    is_fn,
    gelem,
    is_gen,
    is_kw,
    is_list,
    is_opt,
    is_set,
    is_sopt,
    is_tuple,
    is_vtuple,
    kw_names,
    literal_format,
    lt,
    nones as only_nones,
    rtt,
    runtime_format,
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
    if path == "sys.warnoptions":
        return Val(self.rt("pys_warnoptions", "ptr", []), "list[str]")
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
    if path == "sys.implementation.name":
        return Val(self.sconst(IMPLEMENTATION), "str")
    if path.startswith(TYPESMOD + "."):
        self.err(GALIASUSE if path == GALIAS else TYPESUSE.replace("NAME", path[len(TYPESMOD) + 1 :]))
    if path == "sys.implementation":
        self.err("sys.implementation cannot be used as a value (read sys.implementation.name, which is \"pystachy\")")
    if path in VERSIONINFO:
        c = VERSIONINFO[path]
        return Val(self.sconst(c[1:-1]), "str") if c.startswith("'") else Val(c, "int")
    if path == "sys.version_info":
        # (a tuple of its items: comparisons, indexing and slicing work as on CPython's, but str()
        # and repr() show a tuple, not sys.version_info(major=3, ...))
        if path not in self.bconsts:
            vals = [self.modattr("sys.version_info." + x) for x in "major minor micro releaselevel serial".split()]
            d = Data("tuple", "@sys.version_info")
            d.items = vals
            self.consts.append(d)
            self.bconsts[path] = Val(d.name, self.ctype("tuple", [v.t for v in vals]))
        return self.bconsts[path]
    if path == "sys.platform":
        return Val(self.rt("pys_platform", "ptr", []), "str")
    if path == "sys.byteorder":
        return Val(self.sconst("little"), "str")  # (that of every target Pystachy builds for: x86-64, arm64)
    if path.startswith("errno.") and path[6:] in ERRNO:
        return Val(self.rt("pys_errno", "i64", [f"ptr {self.sconst(path[6:])}"]), "int")
    if path in MODFUNCS:
        return Val("null", f"fn[b:{path}]")  # (a function of a builtin module as a value)
    if (path.endswith(".__name__") or path.endswith(".__qualname__")) and path[: path.rfind(".")] in MODFUNCS:
        fp = path[: path.rfind(".")]
        return Val(self.sconst(fp[fp.rfind(".") + 1 :]), "str")
    if path == FROZENERR:
        self.err(FROZENUSE)
    self.err(f"unsupported module attribute {path}")
    return Val("", "")

def gen_builtin(self, name: str, args: list[Node], want: str, resultsoft: bool = False) -> Val:
    # retval's open-result marker belongs to forwarding calls, not to the
    # arguments a builtin consumes (sorted/list/dict may reuse their context).
    want = "" if want == "?" else want
    if name.startswith(TYPESMOD + "."):
        self.err(GALIASUSE if name == GALIAS else TYPESUSE.replace("NAME", name[len(TYPESMOD) + 1 :]))
    if name == "__pys_exc_repr":
        return self.exc_brepr(self.expr(args[0], ""))  # (exc_helpers)
    if name == "__pys_repr_enter" or name == "__pys_repr_leave":
        o = self.expr(args[0], "")
        r = self.rt(name[2:], "i64" if name.endswith("enter") else "void", [f"ptr {o.v}"])
        return self.num_cmp('!=', Val(r, "int"), Val('0', "int")) if name.endswith("enter") else Val("null", "None")
    if name.startswith("__pys_dict_") or name.startswith("__pys_set_"):
        return self.walk(name, args)
    if name.startswith("__pys_range_"):
        return self.range_prim(name, args)
    if name == "__pys_asdict" or name == "__pys_astuple" or name == "dataclasses.asdict" or name == "dataclasses.astuple" or name == "dataclasses.is_dataclass":
        return self.refl_dataclasses(name, args)  # (reflection.py)
    if name == "dataclasses.fields":
        self.err("dataclasses.fields() is supported as the iterable of a for loop or a list comprehension that reads each field's .name (#486)")
    if name == "__pys_repr" or name == "__pys_str" or name == "__pys_ascii" or name == "__pys_hash":
        # compiler-written calls (f"{x!r}", dataclass __repr__, hash_helper): always the builtin
        name = name[6:]
    if name.startswith("builtins."):
        name = name[9:]
    if name == "range" and RANGEC in self.classes:
        # range() as a value: an object of lib's class (lib/_pystachy_range.py), of its arguments
        # evaluated in turn, then checked (where a loop or a consumer takes its numbers at once,
        # range(...) is no value: see for_, consume)
        for a in args:
            if a.kind == "kw" or a.kind == "dstar":
                self.err("range() takes no keyword arguments")
        vs = self.range_args(args)
        o = self.new_obj(RANGEC)
        self.call_fn(self.classes[RANGEC].methods["__init__"], [o], [self.vnode(Val(x, "int")) for x in vs], direct=True)
        return o
    if RANGEC in self.classes and (name == "any" or name == "all" or name == "sum" or name == "min" or name == "max" or name == "math.fsum" or name == "math.prod") and len(args) > 0 and args[0].kind != "kw" and args[0].kind != "starred":
        nrest = len([a for a in args[1:] if a.kind != "kw"])  # (sum's start, or max(a, b)'s b)
        if (nrest == 0 or (nrest == 1 and name == "sum")) and self.probe_type(args[0]) == RANGEC:
            # of a range object: its numbers as they come, as of a generator expression over it
            # (any() and all() stop at the deciding one, and no list of them is made)
            item = made_var("__item", args[0].line)
            args = [mk("listcomp", "gen", args[0].line, [item, item, args[0]])] + args[1:]
    if (name == "str" or name == "repr" or name == "ascii" or name == "format") and len(args) == 1 and self.refl_textual(args[0]):
        # str(vars(o)), repr(getattr(o, name)), ...: the text of what it looks up (reflection.py)
        rtext = self.refl_finish(self.refl_defer(args[0]), "repr" if name == "repr" or name == "ascii" else "str")
        return Val(self.rt("pys_ascii", "ptr", [f"ptr {rtext.v}"]), "str") if name == "ascii" else rtext
    if name == "bytes":
        return self.bytes_(args)
    if name == "tuple":
        if len(args) > 1 or any(a.kind == "kw" for a in args):
            self.err("tuple() takes zero or one positional iterable argument")
        if len(args) == 0:
            return self.coerce(self.tuple_([]), want) if is_vtuple(unopt(want)) else self.tuple_([])
        if self.is_mapcall(args[0]) or (args[0].kind == "listcomp" and args[0].s == "gen"):
            # tuple(e for t in xs) of a fixed tuple xs: the tuple of each item's e (its items are
            # typed one by one); of anything else, a runtime-length tuple of the items (below).
            # Where xs is no variable, field or display, dry() types it, so that it runs once
            g = self.mapgen(args[0]) if self.is_mapcall(args[0]) else args[0]
            src = g.kids[2] if len(g.kids) == 3 else g
            fixed = src.kind == "tuple" or is_tuple(self.iter_static(src)) or (self.lit_context() and self.const_of(src, {}, True) is not None)
            if not fixed and src is not g and src.kind != "listcomp" and not self.iterator_call(src) and not self.is_mapcall(src) and self.iter_static(src) == "":
                kwsrc = src.kind == "call" and len(src.kids) == 1 and src.kids[0].kind == "attr" and (src.kids[0].s == "items" or src.kids[0].s == "values") and is_kw(self.iter_static(src.kids[0].kids[0]))
                fixed = kwsrc or is_tuple(self.dry(src))
            unrolled = self.unroll(g, True) if fixed and src is not g else None
            if unrolled is not None:
                return self.expr(mk("tuple", "", g.line, unrolled), "")
        v = self.unwrap(self.consume(args[0], self.ctype("list", [targs(unopt(want))[0]]) if is_vtuple(unopt(want)) else "", resultsoft=resultsoft), "TypeError: 'NoneType' object is not iterable")
        if is_vtuple(v.t) or is_tuple(v.t):
            return self.coerce(v, want) if is_vtuple(unopt(want)) else v
        if v.t == "str":
            v = Val(self.rt("pys_str_list", "ptr", [f"ptr {v.v}"]), "list[str]")
        if is_gen(v.t):
            v = self.gen_list(v, "")
        if v.t == "bytes":
            v = Val(self.rt("pys_bytes_list", "ptr", [f"ptr {v.v}"]), "list[int]")
        if self.iter_object(v.t) or v.t == RANGEC:
            v = self.as_list(v, "tuple")  # (the items of its iterator object; a range's numbers)
        if not is_list(v.t):
            self.err(f"tuple() of {typestr(v.t)} is not supported: use a list, string or tuple")
        if unopt(elem(v.t)) not in ["int", "float", "bool", "str"]:
            self.err("runtime-length tuple elements must be int, float, bool, str or their optional types")
        return Val(self.rt("pys_vtuple_new", "ptr", [f"ptr {v.v}"]), self.ctype("vtuple", [elem(v.t)]))
    if name == "typing.NamedTuple":
        self.err("the functional NamedTuple form is not supported: write a class, class P(NamedTuple): with annotated fields")
    if name in self.taliases:
        self.err(f"type alias '{short(name)}' cannot be used as a value (only annotations may name it)")
    if name in self.typevars:
        self.err(f"TypeVar '{short(name)}' cannot be used as a value (only annotations may name it)")
    if name == "dataclasses.replace":
        return self.dc_replace(args)
    if name == "dataclasses.field":
        self.err("dataclasses.field() is only supported as the value of a field in the body of a @dataclass class")
    if name == FROZENERR:
        self.err(FROZENUSE)
    if "." not in name and name not in PYBUILTINS:
        self.err(f"name '{short(name)}' is not defined")
    # builtins and module functions ("os.system"); most are one call listed in CALLS
    if name == "print":
        return self.print_(args)
    if name == "next":
        return self.next_(args, want)
    if name == "iter":
        return self.iter_(args)
    if name == "open":
        return self.open_(args)
    if name == "set" or name == "frozenset":
        return self.set_new(name, args, want, resultsoft)
    if name == "map" or name == "filter":
        self.err(f"{name}() is supported as the argument of list(), tuple() (with scalar or optional scalar items), bytes(), sorted(), sum(), min(), max(), any(), all(), math.fsum(), math.prod(), str.join() and list.extend(), and as the value assigned to a list slice, which take its items at once; elsewhere use a list comprehension")
    if len(args) > 0 and self.is_mapcall(args[0]) and (name == "list" or name == "sorted" or name == "sum" or name == "min" or name == "max" or name == "any" or name == "all" or name == "math.fsum" or name == "math.prod" or name == "dict"):
        args = [self.mapgen(args[0])] + args[1:]  # (the generator expression it is)
    if name == "hash":
        if len(args) != 1 or args[0].kind == "kw":
            self.err(f"hash() takes exactly one argument ({len(args)} given)")
        return self.hash_value(self.expr(args[0], ""))
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
    if name == "getattr":
        # getattr(o, "name") reads o.name: o, then the attribute, as CPython looks it up; with a
        # default, or a name only the run time knows, see refl_getattr
        if len(args) != 2 or self.getattr_name(mk("call", "", self.line, [mk("name", "getattr", self.line, [])] + args)) == "" or self.refl_derived_only(args[0], self.getattr_name(mk("call", "", self.line, [mk("name", "getattr", self.line, [])] + args))):
            return self.refl_getattr(args, want)
        return self.expr(mk("attr", self.getattr_name(mk("call", "", self.line, [mk("name", "getattr", self.line, [])] + args)), args[0].line, [args[0]]), want)
    if name == "setattr":
        return self.refl_setattr(args)
    if name == "dir" and len(args) == 1 and args[0].kind != "kw" and args[0].kind != "starred":
        return self.refl_dir(args[0])
    if name == "vars" and len(args) == 1:
        self.err(VARS_USES)
    if name == "dict" and len(args) == 1 and self.refl_dict_of(args[0]) is not None:
        return self.refl_dict_copy(args[0])
    if name == "delattr":
        self.err("delattr() is not supported: deleting an attribute needs an unbound state for each field (#489)")
    if name == "type" and len(args) == 1 and args[0].kind != "kw" and args[0].kind != "starred":
        tv = self.expr(args[0], "")
        if tv.t == "exc" or (tv.t in self.classes and self.classes[tv.t].exc != "" and tv.v in self.nn):
            # (type(e) of an exception, as a value: its class, an exctype, which is the exception)
            return Val(tv.v if tv.t == "exc" else self.exc_of(tv).v, "exctype")
        if tv.t == "exc" or (tv.t in self.classes and self.classes[tv.t].exc != ""):
            self.err(f"unsupported call type({tv.t}): type(e) of an exception is supported as type(e).__name__ (and isinstance(e, C) tests its class)")
        self.err("type(x) as a value (a class object) is not supported (#7); type(x).__name__, x.__class__.__name__, type(x) is C and type(a) == type(b) are (#486)")
    if name == "callable" and len(args) == 1 and args[0].kind != "kw" and args[0].kind != "starred":
        # decided by the static type: an object is callable where its class defines __call__
        # and it is not None
        v = self.expr(args[0], "")
        known = self.callable_type(v.t)
        if known == -2:
            return Val("true", "bool") if v.v in self.nn else self.ptr_cmp('!=', v, Val('null', 'None'))
        return Val("true" if known == 1 else "false", "bool")
    if name == "hasattr" and not (len(args) == 2 and args[1].kind == "str"):
        return self.refl_hasattr(args)  # (a name only the run time knows: reflection.py)
    if name == "hasattr" and len(args) == 2 and args[1].kind == "str":
        # decided by the static type of the object (for an object: is it None)
        hv = self.expr(args[0], "")
        if self.refl_prop_in(hv.t, args[1].s) or (self.reference_union(hv.t) and "file" not in umembers(unopt(hv.t))):
            # (a property's getter, and each class of a union of classes: reflection.py)
            return self.refl_hasattr_lit(hv, args[1].s, self.knownobj(args[0]))
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
            self.cbr("true" if hv.v in self.nn else self.ptr_cmp('!=', hv, Val('null', 'None')).v, present, done)
            self.place(present)
            tag = self.mload('int', hv.v)
            cs = [c for c in self.classes.values() if c.tag > 0 and self.derives(c.name, hv.t)]
            for i in range(len(cs)):
                ci = cs[i]
                nxt = self.label() if i + 1 < len(cs) else ""
                if nxt != "":
                    arm = self.label()
                    self.cbr(self.num_cmp('==', Val(tag, "int"), Val(str(ci.tag), "int")).v, arm, nxt)
                    self.place(arm)
                hy = self.has(ci.name, attr)
                if attr in ci.fflag and attr not in ci.fdefault and attr not in ci.methods:
                    value = self.mem_load(Val(self.fgep(Val(hv.v, ci.name), ci.fflag[attr]), "*bool")).v
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
            self.cbr("true" if hv.v in self.nn else self.ptr_cmp('!=', hv, Val('null', 'None')).v, l1, l2)
            self.place(l1)
            fv = self.mem_load(Val(self.fgep(hv, self.classes[hv.t].fflag[args[1].s]), "*bool")).v
            e1 = self.cur
            self.br(l2)
            self.place(l2)
            ph = Ins("phi", "bool", "")
            self.incoming(ph, "false", e0)
            self.incoming(ph, fv, e1)
            return Val(self.phi(ph), "bool")
        if hy < 0:
            return self.ptr_cmp('!=', hv, Val('null', 'None'))
        return Val("true" if hy == 1 else "false", "bool")
    if name == "issubclass" and len(args) == 2 and args[0].kind != "kw" and args[1].kind != "kw" and self.exc_classes(args[1]):
        # issubclass(t, C) of the class of an exception (exctype: the exception itself)
        v = self.expr(args[0], "")
        if unopt(v.t) != "exctype":
            self.err(f"issubclass() is supported for the class of an exception (type[BaseException], as __exit__ takes it), not {typestr(v.t)}")
        self.isinst_reads(args[1])
        v = self.unwrap(v, "TypeError: issubclass() arg 1 must be a class")
        return self.exc_isinst(Val(v.v, "exc"), args[1])
    if name == "isinstance" and len(args) == 2 and args[0].kind != "kw" and args[1].kind != "kw":
        # decided by the static types, or by whether it is None (an optional value, an object)
        v = self.expr(args[0], "")
        self.isinst_reads(args[1])
        if (v.t == "exc" or (v.t in self.classes and self.classes[v.t].exc != "")) and self.exc_classes(args[1]):
            return self.exc_isinst(v, args[1])
        if v.t == "opt[exc]" and self.exc_classes(args[1]):
            # (__exit__'s exception, which may be None: not an instance)
            e0 = self.cur
            l1 = self.label()
            l2 = self.label()
            self.cbr(self.ptr_cmp('==', v, Val('null', 'None')).v, l2, l1)
            self.place(l1)
            xin = self.exc_isinst(Val(v.v, "exc"), args[1]).v
            e1 = self.cur
            self.br(l2)
            self.place(l2)
            ph = Ins("phi", "bool", "")
            self.incoming(ph, "false", e0)
            self.incoming(ph, xin, e1)
            return Val(self.phi(ph), "bool")
        if v.t == "None" and self.exc_classes(args[1]):
            # (None is no exception: __exit__(None, None, None) of an unannotated __exit__)
            return Val("false", "bool")
        if is_union(unopt(v.t)) and self.isinst(v.t, args[1]) == -1:
            return Val(self.uisinst(v, args[1]), "bool")
        known = self.isinst(v.t, args[1])
        if known < -1:
            return self.ptr_cmp('!=' if known == -2 else '==', v, Val('null', 'None'))
        if known < 0:
            if v.t in self.classes and self.classes[v.t].tag > 0:
                return self.obj_isinst(v, args[1])
            self.err("isinstance() is only supported with the builtin types and classes as its second argument")
        return Val("true" if known == 1 else "false", "bool")
    if (name == "any" or name == "all") and len(args) == 1 and (self.iterator_call(args[0]) or (args[0].kind == "listcomp" and args[0].s == "gen")):
        # these stop at the deciding item, as CPython's iterators do
        g = args[0]
        if g.kind != "listcomp":
            g = mk("listcomp", "gen", g.line, [mk("name", "__item", g.line, []), made_var("__item", g.line), g])
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
    if name == "math.isclose":
        return self.isclose(args)
    if name == "math.prod":
        # prod(iterable, /, *, start=1): start is sum()'s second argument
        npos = len([a for a in args if a.kind != "kw"])
        if npos != 1:
            self.err(f"prod() takes exactly 1 positional argument ({npos} given)")
        args = [a.kids[0] if a.kind == "kw" and a.s == "start" else a for a in args]
        # A nonnumeric product must consume lazy inputs one item at a time: the
        # first multiplication may raise or invoke user code before the next item.
        if len(args) == 2 and (self.iterator_call(args[0]) or (args[0].kind == "listcomp" and args[0].s == "gen")):
            stt = self.dry(args[1])
            if stt == "str" or is_list(stt) or is_dict(stt) or is_set(stt):
                return self.reduce(name, args, stt)
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
    if name == "dict" and npos == 1 and (self.iterator_call(args[0]) or args[0].kind == "listcomp" or args[0].kind == "list"):
        # dict(zip(ks, vs)), dict(enumerate(xs)), dict((k, v) for ...), dict([(k, v), ...]): a new
        # dict of the pairs (taken at once, as list() takes them)
        a = args[0]
        fn = a.kids[0].s if a.kind == "call" else ""
        # the tuples that displays (or zip()'s arguments) show the items to be: of other than two
        # items, none starred, they are not typed by want, whose items are pairs
        shown = [a.kids[0]] if a.kind == "listcomp" else a.kids if a.kind == "list" else [mk("tuple", "", a.line, a.kids[1:])] if fn == "zip" else []
        plain = [k for k in shown if k.kind == "tuple" and len([x for x in k.kids if x.kind == "starred" or x.kind == "kw"]) == 0]
        odd = len([k for k in plain if len(k.kids) != 2]) > 0
        pw = self.ctype("list", [self.ctype("tuple", targs(unopt(want)))]) if is_dict(unopt(want)) and "?" not in want and not odd else ""
        if (fn != "" or a.s == "gen") and (fn == "reversed" or len(plain) < len(shown) or odd):
            # an iterator not shown to make pairs is typed first: of tuples of another length, it
            # is taken only up to its first item, CPython's ValueError (any() of each item's
            # 1-tuple, which is true, stops there)
            item = mk("name", "__item", a.line, [])
            g = a if fn == "" else mk("listcomp", "gen", a.line, [item, item, a])
            et = elem(self.dry(mk("listcomp", "", a.line, g.kids), pw))
            if is_tuple(et) and len(targs(et)) != 2:
                one = mk("listcomp", "gen", a.line, [mk("tuple", "", a.line, [g.kids[0]])] + g.kids[1:])
                return self.dict_pairs(Val("", self.ctype("list", [et])), want, self.listcomp(one, "", "any").v)
        return self.dict_pairs(self.consume(a, pw, None, resultsoft), want)
    if npos == 1 and (name == "sorted" or name == "min" or name == "max" or name == "sum" or name == "any" or name == "all" or name == "list" or name == "math.fsum" or name == "math.prod"):
        # these iterate their argument at once, so range(), reversed(), enumerate() and zip() may be it
        fresh = self.iterator_call(args[0]) or args[0].kind == "listcomp"
        lazy = self.iterator_call(args[0]) or (args[0].kind == "listcomp" and args[0].s == "gen")
        ka = IterArg(mk("tuple", "", self.line, [a.kids[0] for a in kws])) if len(kws) > 0 and lazy else None
        self.gencall = ""
        v0 = self.consume(args[0], w, ka, resultsoft)
        if is_gen(v0.t) and ka is None and (name == "sum" or name == "min" or name == "max" or name == "any" or name == "all" or name == "math.fsum" or name == "math.prod"):
            # (a generator's items as they come, as of a generator expression: any() and all()
            # stop at the deciding one, and nothing is kept)
            return self.gen_stream(name, v0, args[1:], want, resultsoft)
        if ka is not None:
            kvals = [self.tget(ka.value, j) for j in range(len(kws))]
        elif len(kws) > 0:
            kvals = [self.expr(a.kids[0], "") for a in kws]
        if is_opt(v0.t):
            v0 = self.unwrap(v0, "TypeError: 'NoneType' object is not iterable")
        if name == "any" and v0.t == "file":
            # any(f) reads one line: lines are never empty
            first = self.rt("pys_file_readline", "ptr", [f"ptr {v0.v}"])
            return self.num_cmp('!=', Val(self.mload('int', first), "int"), Val('0', "int"))
        kv = [kvals[j] for j in range(len(kws)) if kws[j].s == "key" and kvals[j].t != "None"]
        if (self.iter_object(v0.t) or (v0.t == RANGEC and len(kv) == 0)) and (name == "any" or name == "all" or name == "sum" or name == "min" or name == "max") and not (len(kv) > 0 and name != "sum" and self.classes[v0.t].methods["__iter__"].gen):
            # an object whose __iter__ returns an iterator object, or a range object: its items as
            # they come, as CPython takes them (any() and all() stop at the deciding one)
            if len(kv) > 0 and name != "sum":
                self.key_check(kv[0], f"{name}()")
                return self.key_minmax_next(v0, kv[0], name)
            item = made_var("__item", self.line)
            g = mk("listcomp", "gen", self.line, [item, item, self.vnode(v0)])
            return self.listcomp(g, "", name) if name == "any" or name == "all" else self.reduce(name, [g], "")
        vals = [self.as_list(v0, name)]
        fresh = fresh or is_set(v0.t) or self.iter_object(v0.t)  # (the list of a set's elements, or an iterator's items, is a new one)
        if v0.t == "tuple[]" and is_list(w):
            vals[0] = Val(vals[0].v, w)  # (list(()) has no item to type: it is the list wanted)
        self.close_temp(args[0], v0)
    elif (name == "sum" or name == "math.prod") and npos == 2 and (self.iterator_call(args[0]) or (args[0].kind == "listcomp" and args[0].s == "gen")):
        # Construct the iterator first, then evaluate start, then traverse it. In particular,
        # __iter__ and range's step check run before start; reversed keeps its original length.
        it = args[0]
        if self.iterator_call(it):
            item = made_var("__item", it.line)
            it = mk("listcomp", "gen", it.line, [item, item, it])
        st = IterArg(args[1])
        vals = [self.listcomp(it, "", "", "", st), st.value]
    elif (name == "len" or name == "bool") and len(args) == 1 and args[0].kind == "name" and "?" in self.rtype(args[0].s):
        self.allowq = True
        vals = [self.read(args[0])]
        self.allowq = False
    elif name == "len" and len(args) == 1 and args[0].kind == "name" and self.owns(args[0].s):
        self.appending = True  # (len() of a str that str_append owns keeps it owned: it loads the length alone)
        vals = [self.read(args[0])]
        self.appending = False
    else:
        vals = [self.expr(a, w, resultsoft=resultsoft) for a in args if a.kind != "kw"]
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
    if name == "sum" and len(vals) == 2 and (self.iter_object(vals[0].t) or is_gen(vals[0].t)) and (vals[1].t == "int" or vals[1].t == "float"):
        # (an iterator object's or a generator's items, added as they come)
        item = made_var("__item", self.line)
        return self.reduce(name, [mk("listcomp", "gen", self.line, [item, item, self.vnode(vals[0])]), self.vnode(vals[1])], vals[1].t)
    if (name == "sum" or name == "math.prod") and len(vals) == 2 and (vals[0].t in self.classes or is_tuple(vals[0].t) or is_dict(vals[0].t) or is_gen(vals[0].t)):
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
            out = self.int_ucmp('>', Val(self.scalar('sub', [Val(nb, 'int'), Val('2', 'int')]), "int"), Val('34', "int")).v
            nonzero = self.num_cmp("!=", Val(nb, "int"), Val("0", "int")).v
            self.guard(self.scalar('and', [Val(out, 'bool'), Val(nonzero, 'bool')]), "ValueError: int() base must be >= 2 and <= 36, or 0")
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
    asked = key  # (math's calls convert their arguments below; a rejection names them as given)
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
    if name == "sys.exception" and len(vals) == 0:
        # the exception being handled (an except clause's, a finally block's on the way out of
        # one), or None
        return Val(self.rt("pys_exc_handled", "ptr", []), "opt[exc]")
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
    if name == "math.perm" and (len(vals) == 1 or (len(vals) == 2 and vals[1].t == "None")) and (vals[0].t == "int" or vals[0].t == "bool"):
        # perm(n) and perm(n, None) are factorial(n), as math_perm_impl makes them
        return Val(self.rt("pys_m_factorial", "i64", [f"i64 {self.as_int(vals[0]).v}"]), "int")
    if (name == "math.gcd" or name == "math.lcm") and len(vals) != 2 and all(v.t == "int" or v.t == "bool" for v in vals):
        # gcd() and lcm() of other than two ints (math_gcd, math_lcm): 0 and 1 of none, |x| of one,
        # and else the first two's, then that and the third's, ... (lcm's stays 0 once it is 0)
        if len(vals) == 0:
            return Val("0" if name == "math.gcd" else "1", "int")
        acc = self.as_int(vals[0])
        if len(vals) == 1:
            neg = self.num_cmp('<', acc, Val('0', "int")).v
            return Val(self.select(neg, Val(self.iop("-", "0", acc.v), "int"), acc), "int")
        for v in vals[1:]:
            acc = Val(self.rt("pys_m_gcd" if name == "math.gcd" else "pys_m_lcm", "i64", [f"i64 {acc.v}", f"i64 {self.as_int(v).v}"]), "int")
        return acc
    if name == "math.hypot" and len(vals) != 2 and all(self.isnum(v.t) for v in vals):
        # hypot() of other than two coordinates (math_hypot): 0.0 of none, |x| of one, and else
        # the norm of them all, which math.dist's (vnorm) is
        if len(vals) == 0:
            return Val(fbits("0.0"), "float")
        if len(vals) == 1:
            return Val(self.rt("fabs", "double", [f"double {self.as_float(vals[0]).v}"]), "float")
        xs = self.rt("pys_list_new", "ptr", [f"i64 {len(vals)}"])
        for v in vals:
            self.rt("pys_list_append", "void", [f"ptr {xs}", "i64 " + self.to_slot(self.as_float(v))])
        return Val(self.rt("pys_m_hypot_list", "double", [f"ptr {xs}"]), "float")
    if name == "math.prod" and len(vals) == 2 and is_list(vals[0].t) and (vals[1].t == "str" or is_list(vals[1].t) or is_dict(vals[1].t) or is_set(vals[1].t)):
        return self.prod_seq(vals[0], vals[1])
    if key not in CALLS and name == "math.ldexp" and len(vals) == 2:
        vals = [self.as_float(self.as_int(vals[0])), self.as_int(vals[1])]
        key = f"{name}({','.join([v.t for v in vals])})"
    if key not in CALLS and name.startswith("math.") and f"{name}({','.join(['int' if v.t == 'bool' else v.t for v in vals])})" in CALLS:
        vals = [self.as_int(v) for v in vals]  # (a bool where an int is taken: comb(True, False))
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
    if name == "abs" and len(vals) == 1 and t in self.classes and "__abs__" in self.classes[t].methods:
        # abs(o) is o.__abs__(), and divmod(o, x) is o.__divmod__(x) (reflected methods
        # are not supported); for None, CPython's TypeError
        self.notnone(v, "TypeError: bad operand type for abs(): 'NoneType'")
        return self.method(v, "__abs__", [], want, resultsoft)
    if name == "divmod" and len(vals) == 2 and t in self.classes and "__divmod__" in self.classes[t].methods:
        self.none_operand("divmod()", v, vals[1])
        return self.method(v, "__divmod__", [self.vnode(vals[1])], want, resultsoft)
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
        if (t == "str" or t == "bytes") and self.rtmode:
            # (tagged as the primitives' loads are, and bounded: LLVM then sees that index
            # arithmetic on lengths cannot overflow)
            return Val(self.mload('int', v.v, 'length.range'), "int")
        if t == "str" and self.unicode_audit:
            self.rt("pys_str_audit", "void", [f"ptr {v.v}", f"ptr {self.sconst('len(str)')}"])
        if t == "str" or t == "bytes" or is_list(t) or is_dict(t) or is_set(t) or is_vtuple(t):
            return Val(self.mload('int', v.v), "int")
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
        c = self.num_cmp('<', Val(v.v, "int"), Val('0', "int")).v
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
        self.guard(self.scalar_cmp('oeq', Val(dd.v, 'float'), Val('0.0', 'float')), "ZeroDivisionError: float divmod()")
        return self.tuple_([self.arith("//", dn, dd), self.arith("%", dn, dd)])
    elif name == "pow" and len(vals) == 2:
        return self.arith("**", v, vals[1])
    elif name == "pow" and len(vals) == 3 and self.as_int(v).t == "int":
        pm = [self.coerce(self.as_int(x), "int").v for x in vals]
        return Val(self.rt("pys_powmod", "i64", [f"i64 {pm[0]}", f"i64 {pm[1]}", f"i64 {pm[2]}"]), "int")
    elif name == "dict" and (is_list(t) or is_vtuple(t) or is_tuple(t)):
        return self.dict_pairs(self.as_list(v, name) if not is_list(t) else v, want)
    elif name == "dict" and is_dict(t):
        # not d.copy(): dict(d) merges d into an empty dict, whose table can differ (runtime.c),
        # comparing keys hashed by their class (key_fx)
        return Val(self.rt("pys_dict_from", "ptr", [f"ptr {v.v}"], self.key_fx(targs(t)[0])), t)
    elif name == "list" and is_dict(t):
        return Val(self.rt("pys_dict_keys", "ptr", [f"ptr {v.v}"]), self.ctype("list", [targs(t)[0]]))
    elif name == "range" or name == "enumerate" or name == "zip" or name == "reversed":
        tuple_use = "tuple(), bytes(), " if name == "range" else "tuple() (with scalar or optional scalar items), bytes(), " if name == "reversed" else ""
        self.err(f"{name}() is only supported in a for loop, after 'in', or as the argument of list(), {tuple_use}sorted(), sum(), min(), max(), any(), all(), math.fsum(), math.prod() or str.join()")
    if name in self.gtypes or name in self.ltype:
        self.err(f"'{name}' is not callable")
    if (name == "hex" or name == "oct" or name == "bin") and t in self.classes and "__index__" in self.classes[t].methods:
        self.err(f"{name}() of an object is not supported: Pystachy does not call __index__")
    if name == "dict" and t in self.classes and ("keys" in self.classes[t].methods or "__iter__" in self.classes[t].methods):
        # (CPython copies a mapping by its keys() and __getitem__, else the pairs it iterates over)
        self.err(f"dict() of an object ('{tname(t)}') is not supported: make the dict with a comprehension ({{k: v for k, v in x.items()}})")
    if t in self.classes and name in NONEARG:
        self.err(NONEARG[name].replace("NoneType", tname(t)))  # (CPython's TypeError: its class has no __len__, __abs__, ...)
    if is_gen(t) and name == "len":
        self.err("object of type 'generator' has no len()")
    if is_gen(t) and name == "dict":
        self.err("dict() of a generator is not supported: make the dict with a comprehension ({k: v for k, v in g})")
    if name == "hex" or name == "oct" or name == "bin":
        self.err(NONEARG[name].replace("NoneType", tname(t)))
    if name == "type" and len(vals) == 1 and (t == "exc" or (t in self.classes and self.classes[t].exc != "")):
        self.err(f"unsupported call {key}: type(e) of an exception is supported as type(e).__name__ (and isinstance(e, C) tests its class)")
    self.err(f"unsupported call {(asked if name.startswith('math.') else key).replace(RANGEC, 'range')}")
    return v

def gen_callable_type(self, t: str) -> int:
    # callable(x) for x of static type t: 1 (a function or Callable), 0, or -2 (an object whose
    # class defines __call__: callable unless it is None)
    if is_fn(t) or is_callable(t):
        return 1
    if is_opt(t) and is_callable(unopt(t)):
        return -2
    cs = [t] if t in self.classes else umembers(unopt(t)) if self.reference_union(t) else []
    calls = [c for c in cs if c in self.classes and "__call__" in self.classes[c].methods]
    if len(calls) > 0 and (len(cs) > 1 or self.classes[t].exc != "" or t in self.nts):
        self.err(f"callable() of a {typestr(t)} is not supported")
    if len(calls) == 0 and len([d for d in self.classes.values() if d.tag > 0 and "__call__" in d.methods and len(cs) == 1 and self.derives(d.name, t)]) > 0:
        self.err(f"callable() of a {typestr(t)} is not supported: a derived class defines __call__")
    return -2 if len(calls) > 0 else 0

def gen_vnode(self, v: Val) -> Node:
    # a node whose value is v, computed already: an argument of a call the compiler makes (the
    # key function's, key(item))
    self.vnodes.append(v)
    return mk("val", str(len(self.vnodes) - 1), self.line, [])

def gen_key_check(self, key: Val, of: str) -> None:
    # key= of sorted(), min(), max() or list.sort(): a function value, a Callable (one that may
    # be None too, see key_none), or an object whose class defines __call__
    t = unopt(key.t) if is_opt(key.t) and is_callable(unopt(key.t)) else key.t
    if not is_fn(t) and not is_callable(t) and not (t in self.classes and "__call__" in self.classes[t].methods):
        self.err(f"'{tname(key.t)}' object is not callable (the key of {of})")

def gen_key_none(self, key: Val, et: str, use: str, of: str) -> str:
    # a key that may be None where the call runs (an object, or a Callable | None), which CPython
    # takes as no key, as key=None: a branch to the block returned, where the caller orders the
    # items (of type et, by desc(et, use)) themselves, and on in a new block where it is not
    # None (call_key); "" where it never is, or the items are not key_free (an object key is
    # called then, and raises TypeError for None)
    if not (is_opt(key.t) and is_callable(unopt(key.t))) and (key.t not in self.classes or key.v in self.nn):
        return ""
    if not self.key_free(et, use):
        if is_opt(key.t):
            self.err(f"a key that may be None ({typestr(key.t)}) is not supported for items of type {typestr(et)} (the key of {of}): test it with 'is not None' first")
        return ""
    lnone = self.label()
    lkey = self.label()
    self.cbr(self.ptr_cmp('==', key, Val('null', 'None')).v, lnone, lkey)
    self.place(lkey)
    return lnone

def gen_key_free(self, t: str, use: str) -> bool:
    # does desc(t, use) take t without an error, and without compiling a method the keyed call
    # does not: the items key_none orders without a key (not a closed union, but for ==, a
    # function or **kwargs, nor an object, inside a container or not)
    if is_union(unopt(t)):
        return use == "==" and self.ueq_type(t)
    if t == "int" or t == "float" or t == "bool" or t == "str" or t == "bytes" or t == "None" or t == "exc":
        return True
    if is_opt(t) and t != NONEVAR:
        return self.key_free(unopt(t), use)
    sub = use if use == "==" else "== " + use
    if is_list(t):
        return self.key_free(elem(t), sub)
    if is_vtuple(t):
        return self.key_free(targs(t)[0], sub)
    if is_dict(t):
        return self.key_free(targs(t)[0], use) and self.key_free(targs(t)[1], "==")
    if is_set(t):
        return self.key_free(selem(t), "==")
    if is_tuple(t):
        return len(targs(t)) <= 9 and all([self.key_free(x, sub) for x in targs(t)])
    # (nor an object: desc would compile its class's ==, <, ... and repr, which the keyed call
    # never needs, and which may not compile: a template __eq__ that returns NotImplemented)
    return False

def gen_call_key(self, key: Val, x: Val) -> Val:
    # key(x), the key of item x: a call through function value key, of Callable key (not None
    # here, see key_none), or of object key's __call__
    if key.t in self.classes:
        return self.obj_call(key, [self.vnode(x)], "")
    if is_opt(key.t):
        key = Val(key.v, unopt(key.t))
    return self.call_value(key, [self.vnode(x)], "") if is_fn(key.t) else self.call_callable(key, [self.vnode(x)])

def gen_keys_of(self, xs: Val, key: Val) -> Val:
    # [key(x) for x in xs]: the keys of a sort, computed in order, as CPython computes them
    # before it sorts; xs is a list that no other code sees (a copy, or the items a list gave up)
    ks = self.rt("pys_list_new", "ptr", [f"i64 {self.mload('int', xs.v)}"])
    ctr = self.alloca("int", "")
    self.mstore('int', '0', ctr)
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
    i = self.mload('int', ctr)
    lp.idx = [i]
    self.cbr(self.num_cmp('<', Val(i, "int"), Val(self.mload('int', xs.v), "int")).v, lb, le)
    self.place(lb)
    item = self.from_slot(self.rt("pys_list_get", "i64", [f"ptr {xs.v}", f"i64 {i}"]), elem(xs.t))
    k = self.call_key(key, item)
    if "?" in k.t:
        self.err(f"the key function returns an empty container whose type is not known here ({typestr(k.t)})")
    self.rt("pys_list_append", "void", [f"ptr {ks}", "i64 " + self.to_slot(k)])
    self.mstore('int', f"{self.scalar('add', [Val(i, 'int'), Val('1', 'int')])}", ctr)
    self.br(lc)
    self.place(le)
    return Val(ks, self.ctype("list", [k.t]))

def gen_key_sort(self, xs: Val, key: Val, rev: str, taken: bool) -> None:
    # sort list xs by key(item) (sorted(xs, key=...) of the copy xs, or xs.sort(key=...) of the
    # items a list gave up, taken: pys_list_take), reversed if rev: runtime.c sorts records of the
    # keys and the items by the keys (K), as CPython sorts its keys and moves the items along
    lnone = self.key_none(key, elem(xs.t), "<", "sort()" if taken else "sorted()")
    ks = self.keys_of(xs, key)
    p = self.rt("pys_list_keyed", "ptr", [f"ptr {xs.v}", f"ptr {ks.v}", f"i64 {1 if taken else 0}"])
    self.rt("pys_list_sort_r", "void", [f"ptr {p}", f"ptr {self.sconst('K' + self.desc(elem(ks.t), '<'))}", f"i64 {rev}"])
    if not taken:
        self.rt("pys_list_unkey", "void", [f"ptr {xs.v}", f"ptr {p}"])
    if lnone != "":
        lend = self.label()
        self.br(lend)
        self.place(lnone)
        self.rt("pys_list_sort_r", "void", [f"ptr {xs.v}", f"ptr {self.sconst(self.desc(elem(xs.t), '<'))}", f"i64 {rev}"])
        self.br(lend)
        self.place(lend)

def gen_key_minmax(self, xs: Val, key: Val, name: str) -> Val:
    # min(xs, key=...) and max(...): CPython calls the key on each item in turn and compares the
    # key with the best so far (key < best for min, key > best for max), keeping the first best
    # item; the list's length is read again at each step, as its iterator does
    et = elem(xs.t)
    lnone = self.key_none(key, et, ">" if name == "max" else "<", f"{name}()")
    best = self.alloca(et, "")
    ctr = self.alloca("int", "")
    self.mstore('int', '0', ctr)
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
    i = self.mload('int', ctr)
    lp.idx = [i]
    self.cbr(self.num_cmp('<', Val(i, "int"), Val(self.mload('int', xs.v), "int")).v, lb, le)
    self.place(lb)
    item = self.from_slot(self.rt("pys_list_get", "i64", [f"ptr {xs.v}", f"i64 {i}"]), et)
    self.mstore('int', f"{self.scalar('add', [Val(i, 'int'), Val('1', 'int')])}", ctr)
    k = self.call_key(key, item)
    if "?" in k.t or k.t == "None":
        self.err(f"comparing the keys of {name}() is not supported: its key function returns {typestr(k.t)}")
    bk = self.alloca(k.t, "")
    # the first item is the best so far; each other is if its key compares so with the best's
    first = self.num_cmp('==', Val(i, "int"), Val('0', "int")).v
    lf = self.label()
    self.cbr(first, ln, lf)
    self.place(lf)
    c = self.cmp2(">" if name == "max" else "<", k, Val(self.mload(k.t, bk), k.t))
    self.cbr(self.truth(c), ln, lt_)
    self.place(ln)
    self.mstore(et, item.v, best)
    self.mstore(k.t, k.v, bk)
    self.br(lt_)
    self.place(lt_)
    self.br(lc)
    self.place(le)
    self.guard(self.num_cmp('==', Val(self.mload('int', ctr), "int"), Val('0', "int")).v, f"ValueError: {name}() iterable argument is empty")
    return self.key_none_join(Val(self.mload(et, best), et), lnone, xs, [], name)

def gen_key_none_join(self, r: Val, lnone: str, xs: Val, vals: list[Val], name: str) -> Val:
    # r, min() or max() by a key of list xs, of arguments vals or of iterator object xs, or where
    # lnone (key_none) is a label, joined with what the block there gives: the least (greatest)
    # of the items themselves, as min() without a key finds it
    if lnone == "":
        return r
    l1 = self.cur
    lend = self.label()
    self.br(lend)
    self.place(lnone)
    if len(vals) > 0:
        xs = Val(self.rt("pys_list_new", "ptr", [f"i64 {len(vals)}"]), self.ctype("list", [r.t]))
        for v in vals:
            self.rt("pys_list_append", "void", [f"ptr {xs.v}", "i64 " + self.to_slot(self.coerce(v, r.t))])
    if is_list(xs.t):
        d = self.sconst(self.desc(r.t, ">" if name == "max" else "<"))
        r0 = self.from_slot(self.rt("pys_list_minmax", "i64", [f"ptr {xs.v}", f"ptr {d}", f"i64 {1 if name == 'max' else 0}"]), r.t)
    else:
        item = made_var("__item", self.line)  # (made: it iterates the iterator itself, as min(o) does)
        r0 = self.coerce(self.reduce(name, [mk("listcomp", "gen", self.line, [item, item, self.vnode(xs)])], ""), r.t)
    l0 = self.cur
    self.br(lend)
    self.place(lend)
    ph = Ins("phi", r.t, "")
    self.incoming(ph, r.v, l1)
    self.incoming(ph, r0.v, l0)
    return Val(self.phi(ph), r.t)

def gen_key_minmax2(self, vals: list[Val], key: Val, name: str) -> Val:
    # min(a, b, ..., key=f) and max(...): the key of each argument in turn, compared with the
    # best's so far (as key_minmax does)
    t = vals[0].t
    for b in vals[1:]:
        t = t if self.join(t, b.t) == "" else self.join(t, b.t)
    lnone = self.key_none(key, t, ">" if name == "max" else "<", f"{name}()")
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
    return self.key_none_join(best, lnone, Val("", ""), vals, name)

def gen_key_minmax_next(self, o: Val, key: Val, name: str) -> Val:
    # min(o, key=...) and max(...) of an object whose __iter__ returns an iterator object: each
    # item from __next__, its key computed and compared as it comes (key_minmax)
    lnone = self.key_none(key, self.next_type(o.t), ">" if name == "max" else "<", f"{name}()")
    it = self.obj_iterator(o, "TypeError: 'NoneType' object is not iterable", f"'{tname(o.t)}' object is not iterable")
    c = self.stop_catch()
    first = self.alloca("bool", "")
    self.mstore('bool', 'true', first)
    lc = self.label()
    le = self.label()
    self.fn.loops.append(Loop("while", lc, lc, lc, le))
    self.place(lc)
    item = self.next_in(it, c)
    self.place(self.label())
    k = self.call_key(key, item)
    if "?" in k.t or k.t == "None":
        self.err(f"comparing the keys of {name}() is not supported: its key function returns {typestr(k.t)}")
    best = self.alloca(item.t, "")
    bk = self.alloca(k.t, "")
    take = self.label()
    test = self.label()
    self.cbr(self.mload('bool', first), take, test)
    self.place(test)
    c2 = self.cmp2(">" if name == "max" else "<", k, Val(self.mload(k.t, bk), k.t))
    self.cbr(self.truth(c2), take, lc)
    self.place(take)
    self.mstore(item.t, item.v, best)
    self.mstore(k.t, k.v, bk)
    self.mstore('bool', 'false', first)
    self.br(lc)
    self.stop_landing(c, le)
    self.place(le)
    self.guard(self.mload('bool', first), f"ValueError: {name}() iterable argument is empty")
    return self.key_none_join(Val(self.mload(item.t, best), item.t), lnone, o, [], name)

def gen_iter_object(self, t: str) -> bool:
    # is t a class whose __iter__ returns an iterator object (obj_iterator), not iter(xs) of a
    # list xs (iter_ret)
    return t in self.classes and t not in self.nts and "__iter__" in self.classes[t].methods and not self.classes[t].methods["__iter__"].iters

def gen_anyall(self, v: Val, name: str) -> Val:
    # any(xs) / all(xs) by each item's truth, stopping at the first item that decides
    res = self.alloca("bool", "")
    self.mstore('bool', 'false' if name == 'any' else 'true', res)
    ctr = self.alloca("int", "")
    self.mstore('int', '0', ctr)
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
    i = self.mload('int', ctr)
    lp.idx = [i]
    self.cbr(self.num_cmp('<', Val(i, "int"), Val(self.mload('int', v.v), "int")).v, lb, le)
    self.place(lb)
    c = self.truth(self.from_slot(self.rt("pys_list_get", "i64", [f"ptr {v.v}", f"i64 {i}"]), elem(v.t)))
    if name == "any":
        self.cbr(c, hit, ls)
    else:
        self.cbr(c, ls, hit)
    self.place(hit)
    self.mstore('bool', 'true' if name == 'any' else 'false', res)
    self.br(le)
    self.place(ls)
    self.mstore('int', f"{self.scalar('add', [Val(i, 'int'), Val('1', 'int')])}", ctr)
    self.br(lc)
    self.place(le)
    return Val(self.mload('bool', res), "bool")

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
        item = made_var("__item", g.line)
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
    if name == "math.prod":
        sv = self.expr(args[1], "")
        self.mstore(r.stt, self.coerce(sv, r.stt).v, r.acc)
    elif name == "sum":
        sv = self.expr(args[1], "") if len(args) == 2 else Val("0" if r.t != "float" else fbits("0.0"), "int" if r.t != "float" else "float")
        if r.t == "float":
            self.mstore('float', self.as_float(sv).v, r.acc)
            self.mstore('float', fbits('0.0'), r.comp)
            if r.first != "":
                self.mstore('bool', 'true', r.first)
        elif sv.t == "float":
            self.mstore('float', sv.v, r.acc)
        else:
            self.mstore('int', self.as_int(sv).v, r.acc)
    elif r.collect:
        self.mstore('%ptr', self.rt('pys_list_new', 'ptr', ['i64 0']), r.acc)
    else:
        self.mstore('bool', 'true', r.first)
    self.br(arg.trav)
    self.place(back)
    if name == "math.prod":
        return Val(self.mload(r.stt, r.acc), r.stt)
    if name != "sum" and r.collect:
        d = self.sconst(self.desc(r.t, ">" if name == "max" else "<"))
        lv = self.mload('%ptr', r.acc)
        return self.from_slot(self.rt("pys_list_minmax", "i64", [f"ptr {lv}", f"ptr {d}", f"i64 {1 if name == 'max' else 0}"]), r.t)
    if name != "sum":
        self.guard(self.mload('bool', r.first), f"ValueError: {name}() iterable argument is empty")
        return Val(self.mload(r.t, r.acc), r.t)
    if r.comp == "":
        ft = "float" if r.stt == "float" else "int"
        return Val(self.mload(ft, r.acc), ft)
    # fsum's end: the compensation is added where it is a finite number other than 0
    s = self.mload('float', r.acc)
    c = self.mload('float', r.comp)
    fin = self.scalar_cmp('olt', Val(self.rt('fabs', 'double', [f'double {c}']), 'float'), Val('0x7FF0000000000000', 'float'))
    nz = self.scalar_cmp('une', Val(c, 'float'), Val(fbits('0.0'), 'float'))
    use = self.scalar('and', [Val(nz, 'bool'), Val(fin, 'bool')])
    return Val(self.select(use, Val(self.scalar('fadd', [Val(s, 'float'), Val(c, 'float')]), "float"), Val(s, "float")), "float")

def gen_reduce_item(self, r: Reduce, e: Node) -> None:
    # an item of reduce()'s generator: added to the sum, or compared with the item kept. Its
    # accumulators are made at its first compilation, which gives the items' type
    v = self.expr(e, "")
    if r.t == "":
        r.t = v.t
        if r.name == "sum" and v.t != "int" and v.t != "bool" and v.t != "float":
            self.err(f"unsupported call sum(list[{v.t}]{',' + r.stt if r.stt != '' else ''})")
        if r.name == "math.prod":
            r.acc = self.alloca(r.stt, "")
        elif r.name == "sum":
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
    if r.name == "math.prod":
        result = self.prod_item(Val(self.mload(r.stt, r.acc), r.stt), v)
        self.mstore(r.stt, self.coerce(result, r.stt, "math.prod() must preserve its start type").v, r.acc)
        return
    if r.collect:
        self.rt("pys_list_append", "void", [f"ptr {self.mload('%ptr', r.acc)}", "i64 " + self.to_slot(self.coerce(v, r.t))])
        return
    if r.name != "sum":
        # the first item is kept; another where it is greater (max) or less (min) than the kept one
        take = self.label()
        test = self.label()
        skip = self.label()
        self.cbr(self.mload('bool', r.first), take, test)
        self.place(test)
        kept = Val(self.mload(r.t, r.acc), r.t)
        self.cbr(self.truth(self.cmp2(">" if r.name == "max" else "<", v, kept)), take, skip)
        self.place(take)
        self.mstore(r.t, v.v, r.acc)
        self.mstore('bool', 'false', r.first)
        self.br(skip)
        self.place(skip)
        return
    if r.t != "float" and r.stt != "float":
        si = self.mload('int', r.acc)
        self.mstore('int', self.iop('+', si, self.as_int(v).v), r.acc)
        return
    if r.t != "float":
        # ints from a float start: added as floats, not compensated (pys_sum_int_float)
        sf = self.mload('float', r.acc)
        self.mstore('float', f"{self.scalar('fadd', [Val(sf, 'float'), Val(self.as_float(self.as_int(v)).v, 'float')])}", r.acc)
        return
    nm = self.label()
    if r.first != "":
        # floats from an int start: the first is added as it is (pys_sum_float_int)
        plain = self.label()
        comp = self.label()
        self.cbr(self.mload('bool', r.first), plain, comp)
        self.place(plain)
        s0 = self.mload('float', r.acc)
        self.mstore('float', f"{self.scalar('fadd', [Val(s0, 'float'), Val(v.v, 'float')])}", r.acc)
        self.mstore('bool', 'false', r.first)
        self.br(nm)
        self.place(comp)
    # Neumaier's step, as runtime.c's fsum takes it
    s = self.mload('float', r.acc)
    t = self.scalar('fadd', [Val(s, 'float'), Val(v.v, 'float')])
    ge = self.scalar_cmp('oge', Val(self.rt('fabs', 'double', [f'double {s}']), 'float'), Val(self.rt('fabs', 'double', [f'double {v.v}']), 'float'))
    d1 = self.scalar('fadd', [Val(self.scalar('fsub', [Val(s, 'float'), Val(t, 'float')]), 'float'), Val(v.v, 'float')])
    d2 = self.scalar('fadd', [Val(self.scalar('fsub', [Val(v.v, 'float'), Val(t, 'float')]), 'float'), Val(s, 'float')])
    d = self.select(ge, Val(d1, "float"), Val(d2, "float"))
    c = self.mload('float', r.comp)
    self.mstore('float', f"{self.scalar('fadd', [Val(c, 'float'), Val(d, 'float')])}", r.comp)
    self.mstore('float', t, r.acc)
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
    # ("...".format, which evaluates to the same method each time, is called as it is written)
    fmt = self.format_of(args[0])
    f = args[0] if fn == "filter" and args[0].kind == "None" else fmt if literal_format(fmt) else self.vnode(self.expr(args[0], ""))
    if fn == "filter":
        cond = mk("name", "__item", line, []) if f.kind == "None" else mk("call", "", line, [f, mk("name", "__item", line, [])])
        return mk("listcomp", "gen", line, [mk("name", "__item", line, []), made_var("__item", line), args[1], cond])
    if len(args) == 2:
        return mk("listcomp", "gen", line, [mk("call", "", line, [f, mk("name", "__item", line, [])]), made_var("__item", line), args[1]])
    if self.bound("zip"):
        self.err("map() of several iterables is not supported where zip is bound")
    items = [mk("name", f"__item{i}", line, []) for i in range(len(args) - 1)]
    elt = mk("call", "", line, [f] + [mk("name", x.s, line, []) for x in items])
    return mk("listcomp", "gen", line, [elt, mk("tuple", "", line, items), mk("call", "", line, [mk("name", "zip", line, [])] + args[1:])])

def gen_consume(self, n: Node, want: str, arg: IterArg | None = None, resultsoft: bool = False) -> Val:
    # range(), reversed(), enumerate(), zip() and generator expressions where their items are
    # used at once (list(), sorted(), "".join(), ...) become a fresh list of those items, built
    # by the for loop machinery; anywhere else they are rejected, as a list would behave
    # differently. arg: evaluated once the iterator is made, before it is iterated
    if self.is_mapcall(n):
        n = self.mapgen(n)
    if n.kind == "listcomp" and n.s != "gen" and arg is None:
        unrolled = self.unroll(n)  # (a list display, made before its consumer runs)
        if unrolled is not None:
            return self.expr(mk("list", "", n.line, unrolled), want, resultsoft=resultsoft)
    if n.kind == "listcomp":
        return self.listcomp(n, want, "", "", arg, resultsoft=resultsoft)
    if not self.iterator_call(n):
        return self.expr(n, want, resultsoft=resultsoft)
    if n.kids[0].s == "range":
        # The runtime backing is pointer-free: keep list[int] regardless of want.
        # Optional/union item storage needs a fresh scanned allocation, never retyping.
        vs = self.range_args(n.kids[1:])
        if arg is not None and arg.split != "":
            self.iterarg(arg)  # (xs[::0] = range(n): the consumer's turn comes before the items are made)
            return Val(self.rt("pys_range_list", "ptr", [f"i64 {vs[0]}", f"i64 {vs[1]}", f"i64 {vs[2]}"]), "list[int]")
        r = Val(self.rt("pys_range_list", "ptr", [f"i64 {vs[0]}", f"i64 {vs[1]}", f"i64 {vs[2]}"]), "list[int]")
        self.iterarg(arg)
        return r
    it = mk("name", "__item", n.line, [])
    return self.listcomp(mk("listcomp", "", n.line, [it, made_var("__item", n.line), n]), want, "", "", arg, resultsoft=resultsoft)

def gen_as_list(self, v: Val, name: str) -> Val:
    # sorted(d), max(t), ...: a dict's keys, or the items of a tuple (or NamedTuple) of one item
    # type, as a list, or the list an object's __iter__ steps through (which list() copies);
    # name "slice": the value assigned to a list slice, with its errors
    if is_kw(v.t):
        return self.kw_list(v)  # (the names of **kwargs)
    if v.t in self.nts:
        self.notnone(v, "TypeError: must assign iterable to extended slice" if name == "slice" else "TypeError: 'NoneType' object is not iterable")
        v = self.ntup(v, True)
    if v.t == RANGEC:
        # (a range object's numbers: a new list of them, as list(range(...)) makes)
        self.notnone(v, "TypeError: must assign iterable to extended slice" if name == "slice" else "TypeError: can only join an iterable" if name == "join" else "TypeError: 'NoneType' object is not iterable")
        rf = self.range_fields(v)
        return Val(self.rt("pys_range_list", "ptr", [f"i64 {rf[0]}", f"i64 {rf[1]}", f"i64 {rf[2]}"]), "list[int]")
    if v.t in self.classes and name == "slice":
        # (xs[a:b] = v: CPython's PySequence_Fast iterates v, calling no __len__: list() of iter(v),
        # which calls iter() of an iterator object again)
        items = self.obj_iterator(v, "TypeError: must assign iterable to extended slice", "must assign iterable to extended slice")
        if is_gen(items.t):
            return self.gen_list(items, "")
        if not is_list(items.t):
            items = self.obj_iterator(items, "", f"'{tname(items.t)}' object is not iterable")
        return items if is_list(items.t) else self.drain(items)
    if v.t in self.classes:
        items = self.obj_iterator(v, "TypeError: can only join an iterable" if name == "join" else "TypeError: 'NoneType' object is not iterable",
                                  "can only join an iterable" if name == "join" else f"'{tname(v.t)}' object is not iterable")
        if (name == "list" or name == "sorted" or name == "extend" or name == "tuple") and "__len__" in self.classes[v.t].methods:
            self.objlen(v)  # (a length hint: CPython's list() calls __len__ once __iter__ has run)
        if is_gen(items.t):
            return self.gen_list(items, "")  # (an __iter__ that yields: its generator's items)
        if name == "join" and not is_list(items.t):
            # (str.join() makes a list of the iterator's items, which calls iter() of it again)
            items = self.obj_iterator(items, "", f"'{tname(items.t)}' object is not iterable")
        return items if is_list(items.t) else self.drain(items)
    if is_dict(v.t):
        return Val(self.rt("pys_dict_keys", "ptr", [f"ptr {v.v}"]), self.ctype("list", [targs(v.t)[0]]))
    if is_set(v.t):
        return Val(self.rt("pys_set_list", "ptr", [f"ptr {v.v}"]), self.ctype("list", [selem(v.t)]))
    if is_vtuple(v.t):
        return Val(self.rt("pys_vtuple_list", "ptr", [f"ptr {v.v}"]), self.ctype("list", [targs(v.t)[0]]))
    if is_tuple(v.t):
        ts = targs(v.t)
        et = ts[0] if len(ts) > 0 else "str" if name == "join" else "int"  # (the empty tuple: no item to type)
        if any(x != et for x in ts):
            if (name == "math.fsum" or name == "math.dist") and all(self.isnum(x) for x in ts):
                et = "float"  # (they make a float of each item: (1, 2.5) too)
            elif name == "slice":
                self.err(f"assigning a {typestr(v.t)} to a list slice is not supported: its items have different types")
            else:
                self.err(f"{name}() of a {v.t} needs items of a single type")
        r = self.rt("pys_list_new_atomic" if atomic_list(self.ctype("list", [et])) else "pys_list_new", "ptr", [f"i64 {len(ts)}"])
        for i in range(len(ts)):
            item = self.tget(v, i)
            self.rt("pys_list_append", "void", [f"ptr {r}", "i64 " + self.to_slot(self.as_float(item) if et == "float" else item)])
        return Val(r, self.ctype("list", [et]))
    if v.t == "str" and (name == "sorted" or name == "min" or name == "max" or name == "join"):
        return Val(self.rt("pys_str_list", "ptr", [f"ptr {v.v}"]), "list[str]")
    if v.t == "bytes":
        return Val(self.rt("pys_bytes_list", "ptr", [f"ptr {v.v}"]), "list[int]")  # (its items: ints)
    if v.t == "file":
        return Val(self.rt("pys_file_readlines", "ptr", [f"ptr {v.v}"]), "list[str]")
    if is_gen(v.t):
        return self.gen_list(v, "")  # (its items, as CPython's list(), sorted(), join() take them)
    return v

def gen_bytes_(self, args: list[Node]) -> Val:
    # bytes(), bytes(n) (n zero bytes), bytes(b) (b itself), bytes(xs) of ints (a list, tuple,
    # range, generator expression or other iterable of them, which it consumes at once) and
    # bytes(s, encoding[, errors]) (s.encode(...))
    pos = [a for a in args if a.kind != "kw"]
    kws = {a.s: a.kids[0] for a in args if a.kind == "kw"}
    for k in kws:
        if k != "encoding" and k != "errors" and k != "source":
            self.err(f"bytes() got an unexpected keyword argument '{k}'")
    if "source" in kws:
        pos = [kws["source"]] + pos
    if any(a.kind == "starred" or a.kind == "dstar" for a in args) or len(pos) > 3:
        self.err("bytes() takes at most 3 arguments")
    if len(pos) == 0 and len(kws) == 0:
        return Val(self.bconst(""), "bytes")
    if len(pos) == 0:
        self.err("encoding without a string argument")
    v = self.consume(pos[0], "")
    if len(pos) > 1 or "encoding" in kws or "errors" in kws:
        enc = self.expr(pos[1] if len(pos) > 1 else kws["encoding"], "str") if len(pos) > 1 or "encoding" in kws else Val("null", "str")
        err = self.expr(pos[2] if len(pos) > 2 else kws["errors"], "str") if len(pos) > 2 or "errors" in kws else Val("null", "str")
        if v.t != "str":
            self.err("encoding without a string argument" if "encoding" in kws or len(pos) > 1 else "errors without a string argument")
        for x in [enc, err]:
            if x.t != "str" and x.v != "null":
                self.err(f"bytes() argument 'encoding' must be str, not {tname(x.t)}")
        return Val(self.rt("pys_str_encode", "ptr", [f"ptr {v.v}", f"ptr {enc.v}", f"ptr {err.v}"]), "bytes")
    if v.t == "bytes":
        return v
    if v.t == "str":
        self.err("string argument without an encoding")
    if v.t == "int" or v.t == "bool":
        return Val(self.rt("pys_bytes_zeros", "ptr", [f"i64 {self.as_int(v).v}"]), "bytes")
    if v.t == "None" or is_opt(v.t):
        v = self.unwrap(v, "TypeError: cannot convert 'NoneType' object to bytes")
    if is_tuple(v.t) or is_vtuple(v.t) or v.t in self.classes or is_set(v.t) or is_dict(v.t) or is_gen(v.t):
        v = self.as_list(v, "bytes")
    if not is_list(v.t) or (elem(v.t) != "int" and elem(v.t) != "bool"):
        self.err(f"cannot convert '{tname(v.t)}' object to bytes")
    return Val(self.rt("pys_bytes_from_list", "ptr", [f"ptr {v.v}"]), "bytes")

def bytes_like(t: str) -> bool:
    # does an argument of type t give a bytes, or None, which then raises as it runs
    return t == "bytes" or (is_opt(t) and unopt(t) == "bytes")

def gen_bytes_method(self, o: Val, m: str, args: list[Node]) -> Val:
    # bytes.maketrans(frm, to) (also of a bytes object o), o.translate(table, delete=b"") and
    # o.hex(sep, bytes_per_sep=1), with their arguments by position and by name as CPython takes
    # them, and its TypeErrors; an argument that may be None raises as it runs, once those after
    # it are evaluated (pys_bytes_maketrans, pys_bytes_translate, pys_bytes_hex_sep)
    if any(a.kind == "starred" or a.kind == "dstar" for a in args):
        self.err(f"bytes.{m}() of unpacked arguments is not supported")
    pos = [a for a in args if a.kind != "kw"]
    if m == "maketrans":
        if len(pos) < len(args):
            self.err("bytes.maketrans() takes no keyword arguments")
        if len(args) != 2:
            self.err(f"maketrans expected 2 arguments, got {len(args)}")
        vs = [self.expr(a, "bytes") for a in args]
        for v in vs:
            if not bytes_like(v.t):
                self.err(f"a bytes-like object is required, not '{tname(v.t)}'")
        vs = [self.unwrap(v, "TypeError: a bytes-like object is required, not 'NoneType'") for v in vs]
        return Val(self.rt("pys_bytes_maketrans", "ptr", [f"ptr {vs[0].v}", f"ptr {vs[1].v}"]), "bytes")
    if m == "translate":
        if len(args) > 2:
            self.err(f"translate() takes at most 2 arguments ({len(args)} given)")
        for a in args:
            if a.kind == "kw" and a.s != "delete":
                self.err(f"translate() got an unexpected keyword argument '{a.s}'")
        if len(pos) == 0:
            self.err("translate() takes at least 1 positional argument (0 given)")
        t = self.expr(pos[0], "bytes")  # (None, or a bytes | None that is: no table)
        if t.t != "None" and not bytes_like(t.t):
            self.err(f"a bytes-like object is required, not '{tname(t.t)}'")
        d = Val("null", "bytes")  # (b"")
        if len(args) == 2:
            d = self.expr(args[1].kids[0] if args[1].kind == "kw" else args[1], "bytes")
            if not bytes_like(d.t):
                self.err(f"a bytes-like object is required, not '{tname(d.t)}'")
            d = self.unwrap(d, "TypeError: a bytes-like object is required, not 'NoneType'")
        return Val(self.rt("pys_bytes_translate", "ptr", [f"ptr {o.v}", f"ptr {'null' if t.t == 'None' else t.v}", f"ptr {d.v}"]), "bytes")
    names = ["sep", "bytes_per_sep"]
    if len(args) > 2:
        self.err(f"hex() takes at most 2 arguments ({len(args)} given)")
    given: list[int] = [-1, -1]  # (the index in args of each)
    for i in range(len(args)):
        a = args[i]
        if a.kind == "kw" and a.s not in names:
            self.err(f"hex() got an unexpected keyword argument '{a.s}'")
        k = names.index(a.s) if a.kind == "kw" else i
        if given[k] >= 0:
            self.err(f"argument for hex() given by name ('{names[k]}') and position ({k + 1})")
        given[k] = i
    sep = Val("null", "str")  # (none: no separator)
    chars = 0
    if given[0] >= 0:
        a = args[given[0]]
        sep = self.expr(a.kids[0] if a.kind == "kw" else a, "")
        st = unopt(sep.t) if is_opt(sep.t) else sep.t
        if st != "str" and st != "bytes":
            self.err(f"object of type '{tname(st)}' has no len()" if st in ["int", "float", "bool", "None"] else "sep must be str or bytes.")
        chars = 1 if st == "str" else 0  # (a str's characters count, not its UTF-8 bytes)
    per = Val("1", "int")
    if given[1] >= 0:
        a = args[given[1]]
        per = self.expr(a.kids[0] if a.kind == "kw" else a, "int")
        pt = unopt(per.t) if is_opt(per.t) else per.t
        if pt != "int" and pt != "bool":
            self.err(f"'{tname(pt)}' object cannot be interpreted as an integer")
        per = self.as_int(self.unwrap(per, "TypeError: 'NoneType' object cannot be interpreted as an integer"))
    sep = self.unwrap(sep, "TypeError: object of type 'NoneType' has no len()")
    return Val(self.rt("pys_bytes_hex_sep", "ptr", [f"ptr {o.v}", f"ptr {sep.v}", f"i64 {chars}", f"i64 {per.v}"]), "str")

def gen_reverse_arg(self, n: Node, name: str) -> str:
    return self.reverse_val(self.expr(n, "bool"), name)

def gen_reverse_val(self, r: Val, name: str) -> str:
    # sorted(..., reverse=r) and list.sort(reverse=r): r is a bool or an int, as in CPython
    if r.t != "bool" and r.t != "int":
        self.err(f"{name}() argument 'reverse' must be a bool, not {tname(r.t)}")
    return self.scalar_cast('zext', Val(self.truth(r), 'bool'), 'int')

def gen_parse_expr(self, text: str) -> Node:
    return Parser(Lexer(text, self.line).run()).test()

def gen_next_(self, args: list[Node], want: str) -> Val:
    # next(it) of an iterator object: it.__next__() (of a file: its next line); next(it,
    # default): the default where that raises StopIteration (a file has no line left), the
    # call's type being both's (T | None for a None default). Both arguments are evaluated
    # first, as CPython's are
    for a in args:
        if a.kind == "kw":
            self.err("next() takes no keyword arguments")
    if len(args) == 0 or len(args) > 2:
        self.err(f"next expected {'at least 1 argument' if len(args) == 0 else 'at most 2 arguments'}, got {len(args)}")
    it = self.expr(args[0], "")
    if is_gen(unopt(it.t)):
        # (a generator's next item: gen_next_value)
        it = self.unwrap(it, "TypeError: 'NoneType' object is not an iterator")
        return self.gen_next_value(it, self.expr(args[1], gelem(it.t)) if len(args) == 2 else Val("", ""))
    if it.t != "None" and it.t != "file" and not self.is_iterator(it.t):
        self.err(f"'{tname(it.t)}' object is not an iterator")
    nt = self.classes[it.t].methods["__next__"].ret if self.is_iterator(it.t) else "str" if it.t == "file" else ""
    dv = self.expr(args[1], want if want != "" else nt) if len(args) == 2 else Val("", "")
    if it.t == "None":
        self.raise_("TypeError", self.sconst("'NoneType' object is not an iterator"))
        return Val("null", "None")
    if it.t == "file":
        line = Val(self.rt("pys_file_readline", "ptr", [f"ptr {it.v}"]), "str")
        end = self.num_cmp('==', Val(self.mload('int', line.v), "int"), Val('0', "int")).v
        if len(args) == 1:
            stop = self.label()
            more = self.label()
            self.cbr(end, stop, more)
            self.place(stop)
            self.raise_("StopIteration", self.sconst(""))
            self.place(more)
            return line
        t = "str" if dv.t == "str" else self.join("str", dv.t)
        if t == "" or "?" in t:
            self.err(f"next() of a file with a default of {typestr(dv.t)} is not supported (each call has one type)")
        return Val(self.select(end, self.coerce(dv, t), self.coerce(line, t)), t)
    self.notnone(it, "TypeError: 'NoneType' object is not an iterator")
    if len(args) == 1:
        return self.protocol(it, "__next__", [])
    c = self.stop_catch()
    v = self.next_in(it, c)
    t = v.t if v.t == dv.t else self.join(v.t, dv.t)
    if t == "" or "?" in t:
        self.err(f"next() of {short(it.t)}, whose __next__ returns {typestr(v.t)}, with a default of {typestr(dv.t)} is not supported (each call has one type)")
    self.place(self.label())
    v = self.coerce(v, t)
    e1 = self.cur
    done = self.label()
    self.br(done)
    stop = self.label()
    self.stop_landing(c, stop)
    self.place(stop)
    d = self.coerce(dv, t)
    e2 = self.cur
    self.br(done)
    self.place(done)
    if t == "None":
        return Val("null", "None")
    ph = Ins("phi", t, "")
    self.incoming(ph, v.v, e1)
    self.incoming(ph, d.v, e2)
    return Val(self.phi(ph), t)

def gen_iter_(self, args: list[Node]) -> Val:
    # iter(o): the iterator object of an object's __iter__ (obj_iterator), a file itself, or an
    # object of the iterator class of a builtin container (lib/_pystachy_iterators.py), which
    # steps through it as CPython's does: a list's or a list of a tuple's items by index, a
    # str's characters, a range's numbers, a dict's keys, values or items and a set's elements
    # by entry (failing where the dict or set changes size)
    for a in args:
        if a.kind == "kw":
            self.err("iter() takes no keyword arguments")
    if len(args) == 2:
        self.err("iter(callable, sentinel) is not supported")
    if len(args) != 1:
        self.err(f"iter expected {'at least 1 argument' if len(args) == 0 else 'at most 2 arguments'}, got {len(args)}")
    a = args[0]
    if a.kind == "call" and a.kids[0].kind == "name" and a.kids[0].s == "range" and not self.bound("range"):
        vs = self.range_args(a.kids[1:])
        if vs[2].startswith("%") or int(vs[2]) == 0:
            self.guard(self.num_cmp('==', Val(vs[2], "int"), Val('0', "int")).v, "ValueError: range() arg 3 must not be zero")
        n = Val(self.rt("pys_range_len", "i64", [f"i64 {vs[0]}", f"i64 {vs[1]}", f"i64 {vs[2]}"]), "int")
        return self.iter_obj("range_iterator", [Val(vs[0], "int"), Val(vs[2], "int"), n])
    if a.kind == "call" and len(a.kids) == 1 and a.kids[0].kind == "attr" and (a.kids[0].s == "keys" or a.kids[0].s == "values" or a.kids[0].s == "items"):
        m = a.kids[0].s
        o = self.expr(a.kids[0].kids[0], "")
        if is_dict(unopt(o.t)):
            # (the view's iterator, which walks the dict: not a list of its keys)
            o = self.unwrap(o, f"AttributeError: 'NoneType' object has no attribute '{m}'")
            return self.iter_obj("dict_keyiterator" if m == "keys" else "dict_valueiterator" if m == "values" else "dict_itemiterator", [o])
        v = self.method(o, m, [])
    else:
        v = self.expr(a, "")
    if v.t == "None":
        self.raise_("TypeError", self.sconst("'NoneType' object is not iterable"))
        return Val("null", "None")
    v = self.unwrap(v, "TypeError: 'NoneType' object is not iterable")
    if is_gen(v.t):
        return v  # (a generator is its own iterator)
    if v.t == "file":
        # (a file is its own iterator, once it is found open)
        c = self.rt("pys_file_closed", "i64", [f"ptr {v.v}"])
        self.guard(self.num_cmp('!=', Val(c, "int"), Val('0', "int")).v, "ValueError: I/O operation on closed file.")
        return v
    if v.t in self.nts:
        self.notnone(v, "TypeError: 'NoneType' object is not iterable")
        v = self.ntup(v, True)  # (the tuple of its fields)
    if v.t == RANGEC:
        # (a range object's iterator, as iter(range(...)) makes)
        self.notnone(v, "TypeError: 'NoneType' object is not iterable")
        rf = self.range_fields(v)
        n = Val(self.rt("pys_range_len", "i64", [f"i64 {rf[0]}", f"i64 {rf[1]}", f"i64 {rf[2]}"]), "int")
        return self.iter_obj("range_iterator", [Val(rf[0], "int"), Val(rf[2], "int"), n])
    if v.t in self.classes:
        it = self.obj_iterator(v, "TypeError: 'NoneType' object is not iterable", f"'{tname(v.t)}' object is not iterable")
        return self.iter_obj("list_iterator", [it]) if is_list(it.t) else it
    if is_list(v.t):
        return self.iter_obj("list_iterator", [v])
    if v.t == "str":
        return self.iter_obj("str_ascii_iterator", [v])
    if is_tuple(v.t) or is_vtuple(v.t):
        return self.iter_obj("tuple_iterator", [self.as_list(v, "iter")])
    if is_dict(v.t):
        return self.iter_obj("dict_keyiterator", [v])
    if is_set(v.t):
        return self.iter_obj("set_iterator", [v])
    self.err(f"'{tname(v.t)}' object is not iterable" if not is_kw(v.t) else "iter() of **kwargs is not supported: iterate over list(kwargs)")
    return v

def gen_iter_obj(self, name: str, vals: list[Val]) -> Val:
    # a new object of the iterator class name of lib/_pystachy_iterators.py, made of vals
    c = ITERS + "$" + name
    if c not in self.classes:
        self.err(f"internal error: iter() needs lib/{ITERS}.py (not loaded for this program)")
    args = [self.vnode(v) for v in vals]
    if c in self.tmpl:
        made = [Val("", c)]
        self.call_fn(self.classes[c].methods["__init__"], made, args)
        return made[0]
    o = self.new_obj(c)
    self.call_fn(self.classes[c].methods["__init__"], [o], args, direct=True)
    return o

def gen_walk(self, name: str, args: list[Node]) -> Val:
    # the compiler primitives lib/_pystachy_iterators.py calls: the runtime's walk of a dict's
    # entries or a set's slots, which for_seq makes. __pys_dict_next(d, at, used, count) and
    # __pys_set_next(s, at, used): the next entry (slot) from at, -1 at the end;
    # __pys_dict_key(d, j), __pys_dict_val(d, j), __pys_set_key(s, j): what it holds
    if self.curfn.mod != ITERS:
        self.err(f"name '{name}' is not defined")
    vals = [self.expr(a, "") for a in args]
    if len(vals) == 0 or (not is_dict(vals[0].t) and not is_set(vals[0].t)) or (name.startswith("__pys_dict_") != is_dict(vals[0].t)):
        self.err(f"name '{name}' is not defined")
    o = vals[0]
    ns = [f"i64 {self.coerce(self.as_int(x), 'int').v}" for x in vals[1:]]
    if name == "__pys_dict_next" and len(ns) == 3:
        return Val(self.rt("pys_dict_next", "i64", [f"ptr {o.v}"] + ns), "int")
    if name == "__pys_set_next" and len(ns) == 2:
        return Val(self.rt("pys_set_next", "i64", [f"ptr {o.v}"] + ns), "int")
    if name == "__pys_dict_key" and len(ns) == 1:
        return self.from_slot(self.rt("pys_dict_key", "i64", [f"ptr {o.v}"] + ns), targs(o.t)[0])
    if name == "__pys_dict_val" and len(ns) == 1:
        return self.from_slot(self.rt("pys_dict_val", "i64", [f"ptr {o.v}"] + ns), targs(o.t)[1])
    if name == "__pys_set_key" and len(ns) == 1:
        return self.from_slot(self.rt("pys_set_key", "i64", [f"ptr {o.v}"] + ns), selem(o.t))
    self.err(f"name '{name}' is not defined")
    return o

def gen_range_prim(self, name: str, args: list[Node]) -> Val:
    # the compiler primitives lib/_pystachy_range.py calls: __pys_range_len(start, stop, step),
    # the runtime's count of the numbers (unsigned: one of 2**63 or more is negative);
    # __pys_range_has(x, start, stop, step), x in range(start, stop, step); __pys_range_list(start,
    # stop, step), a new list of the numbers; __pys_range_at(start, step, k), start + k * step,
    # whose 64-bit arithmetic wraps (an item of the range fits in an int, though k * step may not)
    if self.curfn.mod != RANGES or len([a for a in args if a.kind == "kw" or a.kind == "starred" or a.kind == "dstar"]) > 0:
        self.err(f"name '{name}' is not defined")
    ns = [self.coerce(self.as_int(self.expr(a, "int")), "int").v for a in args]
    if name == "__pys_range_len" and len(ns) == 3:
        return Val(self.rt("pys_range_len", "i64", [f"i64 {x}" for x in ns]), "int")
    if name == "__pys_range_has" and len(ns) == 4:
        return self.num_cmp('!=', Val(self.rt("pys_range_has", "i64", [f"i64 {x}" for x in ns]), "int"), Val('0', "int"))
    if name == "__pys_range_list" and len(ns) == 3:
        return Val(self.rt("pys_range_list", "ptr", [f"i64 {x}" for x in ns]), "list[int]")
    if name == "__pys_range_at" and len(ns) == 3:
        k = self.scalar('mul', [Val(ns[2], 'int'), Val(ns[1], 'int')])
        return Val(self.scalar('add', [Val(ns[0], 'int'), Val(k, 'int')]), "int")
    self.err(f"name '{name}' is not defined")
    return Val("", "")

def gen_range_fields(self, v: Val) -> list[str]:
    # start, stop and step of range object v, which is not None (lib/_pystachy_range.py's fields,
    # which nothing but its __init__ assigns)
    ci = self.classes[RANGEC]
    return [self.mload('int', self.fgep(v, ci.fpos[f])) for f in ["start", "stop", "step"]]

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
            vals.append(self.refl_defer(a) if self.refl_textual(a) else self.expr(a, ""))  # (vars(o): reflection.py)
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
        self.pwrite(fd, fv, (self.refl_finish(vals[i], "str") if vals[i].t == "%refl" else self.to_str(vals[i])).v, fo)
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
    if o.t == "str" and (m == "format" or m == "format_map"):
        self.err(runtime_format(m))
    if (is_tuple(o.t) or is_vtuple(o.t)) and (m == "index" or m == "count"):
        tm = self.tmethod(o, m, args)
        if tm.t != "":
            return tm
    if o.t == "bytes" and (m == "maketrans" or m == "translate" or (m == "hex" and len(args) > 0)):
        return self.bytes_method(o, m, args)
    if (o.t == "str" or o.t == "bytes") and m == "replace" and len(args) == 3 and args[2].kind == "kw" and args[2].s == "count":
        args = args[:2] + [args[2].kids[0]]  # (count may be given by name, as of Python 3.13)
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
        return self.from_slot(self.nonekey(kx, dv, fn, [f"ptr {o.v}", f"i64 {k}", f"i64 {dv}"], self.key_fx(kv[0])), vt)
    base = o.t
    T = ""
    K = ""
    V = ""
    if is_list(o.t):
        base = "list"
        T = elem(o.t)
    elif is_vtuple(o.t):
        base = "vtuple"
        T = targs(o.t)[0]
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
    if (key == "str.replace" or key == "bytes.replace") and len(args) == 3:
        spec = f"{base}:{base},{base},int"  # (replace(old, new, count): pys_str_replace_count)
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
        span = (base == "str" or base == "bytes") and p == "int" and (dflt == "0" or dflt == "9223372036854775807")
        if i < len(args) and dflt == "null" and args[i].kind == "None":
            av.append(rtt(pt) + " null")  # an explicit None: the default
        elif i < len(args) and span and args[i].kind == "None":
            av.append("i64 " + dflt)
        elif i < len(args):
            if key == "dict.get" and i == 0 and self.lookup_key(args[0]):
                self.stkkey = args[0]  # (memo.get((i, j), -1))
            want_arg = pt
            if base == "list" and p == "*T" and is_union(unopt(T)) and self.ueq_type(T) and m in ["index", "count", "remove"] and args[i].kind in ["list", "dict", "listcomp"]:
                # A search needle is not stored in the list. Infer a fresh display's
                # own layout before comparing it, rather than forcing list[float]
                # into a list[int] member. Empty/None-only displays still need context.
                pending = [args[i]]
                contextual = False
                nested_union = any(["union[" in member for member in umembers(unopt(T))])
                while len(pending) > 0:
                    query = pending.pop()
                    if query.kind in ["list", "dict"] and only_nones(query):
                        contextual = True
                    if nested_union and query.kind in ["list", "dict"]:
                        parts = [query.kids[j] for j in range(1, len(query.kids), 2)] if query.kind == "dict" else query.kids
                        kinds = [self.probe_type(part) or part.kind for part in parts]
                        # Heterogeneous displays still use explicitly declared element
                        # unions; this change does not infer new union element types.
                        if len(kinds) > 1 and any([kind != kinds[0] for kind in kinds]):
                            contextual = True
                    pending.extend(query.kids)
                if not contextual:
                    want_arg = ""
            join = key == "str.join" or key == "bytes.join"
            g = self.mapgen(args[i]) if join and self.is_mapcall(args[i]) else args[i]
            unrolled = self.unroll(g) if key == "str.join" else None
            if unrolled is not None:
                v = self.expr(mk("list", "", g.line, unrolled), pt)  # (strs of items of different types)
            else:
                v = self.consume(g, pt) if join or key == "list.extend" else self.expr(args[i], want_arg, resultsoft=key in ["list.count", "list.index", "list.remove", "vtuple.count", "vtuple.index"] and i == 0)
            self.stkkey = self.nokey
            if (base == "str" or base == "bytes") and (m == "startswith" or m == "endswith") and i == 0 and (is_tuple(unopt(v.t)) or v.t in self.nts):
                v = self.ntup(v)  # (a NamedTuple: the tuple of its fields, None if it is None)
                for x in targs(unopt(v.t)):
                    if x != base and x != f"opt[{base}]":
                        self.err(f"tuple for {m} must only contain str, not {tname(x)}" if base == "str" else f"a bytes-like object is required, not '{tname(x)}'")  # (CPython's TypeError, at the item it reaches)
                if is_opt(v.t):
                    nones.append(v.v)
                    nmsg.append(self.none_arg(m, 1))
                alts = Val(v.v, unopt(v.t))
                v = Val("null", base)  # (each item in its place, in affix_any)
            if is_opt(v.t) and (join or key == "list.extend" or key == "file.writelines"):
                v = self.unwrap(v, "TypeError: can only join an iterable" if join else "TypeError: 'NoneType' object is not iterable")
            if join or (key == "list.extend" and (v.t in self.classes or is_gen(v.t))):
                v = self.as_list(v, "join" if join else "extend")
            if (key == "str.join" or key == "file.writelines") and v.t == "list[opt[str]]":
                v = Val(v.v, "list[str]")  # (an item that is None raises when it runs, as CPython's error)
            if key == "bytes.join" and v.t == "list[opt[bytes]]":
                v = Val(v.v, "list[bytes]")
            if key == "str.join" and is_list(v.t) and elem(v.t) != "str" and "?" not in v.t:
                self.err(f"sequence item 0: expected str instance, {tname(elem(v.t))} found")  # (CPython's TypeError)
            if key == "bytes.join" and is_list(v.t) and elem(v.t) != "bytes" and "?" not in v.t:
                self.err(f"sequence item 0: expected a bytes-like object, {tname(elem(v.t))} found")
            if key == "list.extend" and is_list(v.t) and v.t != pt and self.widens_items(v.t, pt):
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
            if (base == "list" or base == "vtuple") and p == "*T" and self.isnum(v.t) and self.isnum(unopt(T)) and v.t != unopt(T) and (m == "index" or m == "count" or m == "remove"):
                numx = v
                nk = self.numkey(v, unopt(T))
                v = Val(nk[0], unopt(T))
                numok = nk[1]
            if base == "list" and p == "*T" and is_union(unopt(T)) and self.ueq_type(T) and (m == "index" or m == "count" or m == "remove"):
                pt = self.union_type([T, v.t])
                dt = pt
            if is_opt(v.t) and unopt(v.t) == pt and dflt == "null":
                v = Val(v.v, pt)  # None is the default
            elif is_opt(v.t) and not slot and unopt(v.t) == pt and (pt == "str" or pt == "bytes"):
                nones.append(v.v)
                nmsg.append(self.none_arg(m, i + 1))
                v = Val(v.v, pt)
            elif (is_opt(v.t) or v.t == "None") and slot and p == "*T" and (unopt(v.t) == T or (v.t == "None" and T not in self.classes)) and (base == "list" or base == "vtuple") and m != "append" and m != "insert" and self.optional(T) != "" and not self.isnum(T):
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
        self.guard(self.scalar_cmp('eq', Val(nones[j], '%ptr'), Val('null', '%ptr')), nmsg[j])
    if alts.t != "":
        return self.affix_any(alts, m, av, base)
    r = spec[:c]
    slot = r.startswith("*")
    rtype = self.subst(r[1:] if slot else r, T, K, V, o.t)
    if optget:
        rtype = self.optional(V)
    fn = f"pys_{base}_{m}"
    if (key == "str.replace" or key == "bytes.replace") and len(args) == 3:
        fn = "pys_str_replace_count" if base == "str" else "pys_bytes_replace_count"
    if first:
        fn = "pys_str_split_first"
        rtype = "str"
    if optget and is_sopt(rtype) and not is_sopt(V):
        fn = "pys_dict_getbox"  # (the value's box: an int | None)
    if numok != "true" and m == "remove":
        self.guard(self.scalar('xor', [Val(numok, 'bool'), Val('true', 'bool')]), "ValueError: list.remove(x): x not in list")
    if numx.t != "" and m == "index" and base == "vtuple":
        if numok != "true":
            # (an item can equal x only where x is a number of the items' type: CPython's
            # ValueError is the same for every x)
            self.guard(self.scalar('xor', [Val(numok, 'bool'), Val('true', 'bool')]), "ValueError: tuple.index(x): x not in tuple")
    elif numx.t != "" and m == "index":
        fn = "pys_list_index_as"  # (its ValueError names x, not the item)
        av = av + ["i64 " + self.to_slot(Val(numok, "bool")), "i64 " + self.to_slot(numx), f"ptr {self.sconst(self.desc(numx.t, '=='))}"]
    if bk.t != "":
        self.bool_find(o.v, bk, av[1][4:])
    x = self.key_fx(K) if base == "dict" else ""  # (Ins.x of a lookup: U? where the keys are objects)
    if kx.t != "":
        res = self.nonekey(kx, av[2][4:] if m == "get" else "", fn, av, x)
    else:
        res = self.rt(fn, "i64" if slot else rtt(rtype), av, x)
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
        self.rt("pys_dict_update" if x.t == o.t else "pys_dict_update_pairs", "void", [f"ptr {o.v}", f"ptr {x.v}"], self.key_fx(kv[0]))
    if kw.t != "":
        self.rt("pys_dict_update", "void", [f"ptr {o.v}", f"ptr {kw.v}"])
    return Val("null", "None")

def gen_isclose(self, args: list[Node]) -> Val:
    # math.isclose(a, b, *, rel_tol=1e-09, abs_tol=0.0): the arguments evaluated in the order
    # written, then each made a float in the order of the parameters (an int or a bool), as the
    # call's argument parsing makes them, then math_isclose_impl (runtime.c)
    names = ["a", "b", "rel_tol", "abs_tol"]
    given: dict[str, Val] = {}
    npos = len([a for a in args if a.kind != "kw"])
    if npos > 2:
        self.err(f"isclose() takes exactly 2 positional arguments ({npos} given)")
    for a in args:
        if a.kind == "starred" or a.kind == "dstar":
            self.err("math.isclose() with * or ** arguments is not supported")
        nm = a.s if a.kind == "kw" else names[len(given)]
        if nm not in names:
            self.err(f"isclose() got an unexpected keyword argument '{nm}'")
        if nm in given:
            self.err(f"argument for isclose() given by name ('{nm}') and position ({names.index(nm) + 1})")
        given[nm] = self.expr(a.kids[0] if a.kind == "kw" else a, "float")
    for j in range(2):
        if names[j] not in given:
            self.err(f"isclose() missing required argument '{names[j]}' (pos {j + 1})")
    fs: list[str] = []
    for nm in names:
        v = given[nm] if nm in given else Val(fbits("1e-09") if nm == "rel_tol" else fbits("0.0"), "float")
        if is_opt(v.t) and self.isnum(unopt(v.t)):
            v = self.unwrap(v, "TypeError: must be real number, not NoneType")
        if not self.isnum(v.t):
            self.err(f"must be real number, not {tname(v.t)} (argument '{nm}' of math.isclose())")
        fs.append(f"double {self.as_float(v).v}")
    return self.rres(self.rt("pys_m_isclose", "i64", fs), "bool")

def gen_prod_seq(self, xs: Val, s: Val) -> Val:
    # math.prod(xs, start=s) of a str, list, dict or set s, as math_prod_impl multiplies:
    # s * x, then that * the next x, ... (PyNumber_Multiply), each a new str or list (repeated, or
    # emptied by an x < 1, after which it stays empty). For no item the result is s itself, and a
    # start that the items cannot multiply raises CPython's TypeError at the first
    et = elem(xs.t)
    acc = self.alloca(s.t, "")
    self.mstore(s.t, s.v, acc)
    ctr = self.alloca("int", "")
    self.mstore('int', '0', ctr)
    lc = self.label()
    lb = self.label()
    le = self.label()
    self.br(lc)
    self.place(lc)
    i = self.mload('int', ctr)
    self.cbr(self.num_cmp('<', Val(i, "int"), Val(self.mload('int', xs.v), "int")).v, lb, le)
    self.place(lb)
    item = self.from_slot(self.rt("pys_list_get", "i64", [f"ptr {xs.v}", f"i64 {i}"]), et)
    self.mstore(s.t, self.coerce(self.prod_item(Val(self.mload(s.t, acc), s.t), item), s.t, "math.prod() must preserve its start type").v, acc)
    self.mstore('int', self.scalar('add', [Val(i, 'int'), Val('1', 'int')]), ctr)
    self.br(lc)
    self.place(le)
    return Val(self.mload(s.t, acc), s.t)

def gen_prod_item(self, s: Val, item: Val) -> Val:
    # PyNumber_Multiply for a nonnumeric start. Keep the accumulator's static
    # type; unsupported type-changing reflected methods are diagnosed explicitly.
    if is_opt(item.t) or is_union(unopt(item.t)):
        members = umembers(unopt(item.t)) if is_union(unopt(item.t)) else [unopt(item.t)]
        if is_opt(item.t):
            members = ["None"] + members
        end = self.label()
        ph = Ins("phi", s.t, "")
        for i in range(len(members)):
            member = members[i]
            hit = self.label()
            miss = self.label() if i + 1 < len(members) else ""
            if miss == "":
                self.br(hit)
            elif member == "None":
                self.cbr(self.ptr_cmp('==', item, Val('null', 'None')).v, hit, miss)
            else:
                self.cbr(self.utest(item, [member], False), hit, miss)
            self.place(hit)
            value = Val("null", "None") if member == "None" else self.uget(Val(item.v, unopt(item.t)), member) if is_union(unopt(item.t)) else self.deref(item)
            result = self.prod_item(s, value)
            if not self.term:
                self.incoming(ph, self.coerce(result, s.t, "math.prod() must preserve its start type").v, self.cur)
                self.br(end)
            if miss != "":
                self.place(miss)
        self.place(end)
        if len(ph.a) == 0:
            self.unreachable()
            return s
        return Val(self.phi(ph), s.t)
    seq = s.t == "str" or is_list(s.t)
    if item.t in self.classes:
        methods = self.classes[item.t].methods
        protocol = "__rmul__" if "__rmul__" in methods else "__index__" if seq and "__index__" in methods else ""
        if self.classes[item.t].tag > 0:
            for cls in self.classes.values():
                if cls.tag > 0 and self.derives(cls.name, item.t):
                    selected = "__rmul__" if "__rmul__" in cls.methods else "__index__" if seq and "__index__" in cls.methods else ""
                    if selected != protocol:
                        self.err("math.prod() with subclass-dependent multiplication protocols requires narrowing with isinstance() first")
        # Class values are nullable in this subset; None has neither protocol.
        null = self.label()
        call = self.label()
        end = self.label()
        self.cbr(self.isnull(item), null, call)
        self.place(null)
        self.prod_item(s, Val("null", "None"))
        self.br(end)
        self.place(call)
        self.nn[item.v] = True
        if "__rmul__" in methods:
            result = self.protocol(item, "__rmul__", [s])
            if result.t != s.t:
                self.err("math.prod() must preserve its start type; type-changing __rmul__ is not supported")
        elif seq and "__index__" in methods:
            index = self.protocol(item, "__index__", [])
            if index.t != "int" and index.t != "bool":
                self.raise_("TypeError", self.sconst(f"__index__ returned non-int (type {tname(index.t)})"))
                result = s
            else:
                result = self.arith("*", s, index)
        else:
            bad = f"can't multiply sequence by non-int of type '{tname(item.t)}'" if seq else f"unsupported operand type(s) for *: '{tname(s.t)}' and '{tname(item.t)}'"
            self.raise_("TypeError", self.sconst(bad))
            result = s
        self.br(end)
        self.place(end)
        return result
    if seq and (item.t == "int" or item.t == "bool"):
        return self.arith("*", s, item)
    other_seq = item.t == "str" or is_list(item.t) or is_tuple(item.t) or is_vtuple(item.t)
    bad = f"can't multiply sequence by non-int of type '{tname(item.t) if seq else tname(s.t)}'" if seq or other_seq else f"unsupported operand type(s) for *: '{tname(s.t)}' and '{tname(item.t)}'"
    self.raise_("TypeError", self.sconst(bad))
    return s

def gen_dict_pairs(self, v: Val, want: str, found: str = "") -> Val:
    # dict(pairs) of a list of (key, value) tuples: a new dict, each pair inserted in turn, as
    # PyDict_MergeFromSeq2 inserts them. Of tuples of another length, an item is CPython's
    # ValueError, for element #0 (every item has the one tuple type, so the first is bad), and an
    # empty list makes an empty dict: of the dict type wanted (a union's one dict type), or else,
    # as it is always empty, dict[int, int] (as gen_load_name takes such a dict, which guessed
    # explains). found: whether an iterator of them, v being only their list's type, had an item
    et = elem(v.t) if is_list(v.t) else ""
    if not is_tuple(et):
        self.err(f"dict() of a {typestr(v.t)} is not supported: it takes a dict, or (key, value) tuples")
    if len(targs(et)) != 2:
        self.guard(found if found != "" else self.num_cmp('!=', Val(self.mload('int', v.v), "int"), Val('0', "int")).v, f"ValueError: dictionary update sequence element #0 has length {len(targs(et))}; 2 is required")
        t = unopt(want)
        if is_union(t):
            ds = [m for m in umembers(t) if is_dict(m)]
            t = ds[0] if len(ds) == 1 else ""
        if not is_dict(t) or "?" in t:
            t = self.ctype("dict", ["int", "int"])
            self.guessed[self.curfn.ll] = f"dict() at line {self.line} of tuples of {len(targs(et))} items makes only an empty dict, taken as {typestr(t)}: give it a type first, as in d: dict[K, V] = dict(...)"
        return Val(self.rt("pys_dict_new_atomic" if atomic_dict(t) else "pys_dict_new", "ptr", [f"i64 {self.key_kind(targs(t)[0])}", "i64 0"]), t)
    kv = targs(et)
    if self.key_problem(kv[0]) != "":
        self.err(self.key_problem(kv[0]))
    d = self.rt("pys_dict_new_atomic" if atomic_dict(self.ctype("dict", kv)) else "pys_dict_new", "ptr", [f"i64 {self.key_kind(kv[0])}", "i64 0"])
    self.rt("pys_dict_update_pairs", "void", [f"ptr {d}", f"ptr {v.v}"], self.key_fx(kv[0]))
    return Val(d, self.ctype("dict", kv))

def gen_tmethod(self, o: Val, m: str, args: list[Node]) -> Val:
    # t.index(x, start, stop) and t.count(x) of a tuple of fixed shape, as CPython's
    # tuple_index_impl and tuple_count: each item in turn (of index()'s span, from start
    # and stop as they clamp to the tuple) is compared as x in t compares it (titem_eq);
    # index() stops at the first that is x or equals it. The arguments are evaluated first.
    # A runtime-length tuple uses the same equality and identity rules in a loop.
    for a in args:
        if a.kind == "kw":
            self.err(f"tuple.{m}() takes no keyword arguments")
    if m == "count" and len(args) != 1:
        self.err(f"tuple.count() takes exactly one argument ({len(args)} given)")
    if m == "index" and (len(args) == 0 or len(args) > 3):
        self.err(f"index expected at {'least 1 argument' if len(args) == 0 else 'most 3 arguments'}, got {len(args)}")
    x = self.expr(args[0], "", resultsoft=True)
    if "?" in x.t:
        self.err(f"cannot infer the type of the argument of tuple.{m}(): give it a type")
    bounds: list[Val] = []
    for j in range(1, len(args)):
        bounds.append(self.coerce(self.as_int(self.expr(args[j], "int")), "int", f"argument {j + 1} of tuple.index()"))
    if is_vtuple(o.t):
        size = Val(self.mload('int', o.v), "int")
        span = [Val("0", "int"), size]
        for j in range(len(bounds)):
            b = bounds[j]
            adjusted = Val(self.scalar('add', [b, size]), "int")
            b = Val(self.select(self.num_cmp('<', b, Val('0', "int")).v, adjusted, b), "int")
            b = Val(self.select(self.num_cmp('<', b, Val('0', "int")).v, Val('0', "int"), b), "int")
            span[j] = Val(self.select(self.num_cmp('>', b, size).v, size, b), "int")
        index = self.alloca("int", "")
        count = self.alloca("int", "")
        self.mstore('int', span[0].v, index)
        self.mstore('int', '0', count)
        cond = self.label()
        body = self.label()
        hit = self.label()
        step = self.label()
        done = self.label()
        end = self.label()
        self.br(cond)
        self.place(cond)
        vi = self.mload('int', index)
        self.cbr(self.num_cmp('<', Val(vi, "int"), span[1]).v, body, done)
        self.place(body)
        item = self.from_slot(self.rt("pys_vtuple_get", "i64", [f"ptr {o.v}", f"i64 {vi}"]), targs(o.t)[0])
        matched = self.titem_eq(item, x, hit, None, "")
        self.br(step)
        if matched:
            self.place(hit)
            if m == "index":
                self.br(end)
            else:
                self.mstore('int', self.scalar('add', [Val(self.mload('int', count), 'int'), Val('1', 'int')]), count)
                self.br(step)
        self.place(step)
        self.mstore('int', self.scalar('add', [Val(vi, 'int'), Val('1', 'int')]), index)
        self.br(cond)
        self.place(done)
        if m == "index":
            self.raise_("ValueError", self.sconst("tuple.index(x): x not in tuple"))
        else:
            self.br(end)
        self.place(end)
        return Val(self.mload('int', index if m == "index" else count), "int")
    n = len(targs(o.t))
    if m == "count":
        ctr = self.alloca("int", "")
        self.mstore('int', '0', ctr)
        for i in range(n):
            hit = self.label()
            if self.titem_eq(self.tget(o, i), x, hit, None, ""):
                nx = self.label()
                self.br(nx)
                self.place(hit)
                self.mstore('int', self.scalar('add', [Val(self.mload('int', ctr), 'int'), Val('1', 'int')]), ctr)
                self.br(nx)
                self.place(nx)
        return Val(self.mload('int', ctr), "int")
    # start and stop: constants are clamped here, others where the method runs (st <= i < en)
    st = Val("0", "int")
    en = Val(str(n), "int")
    if len(bounds) > 0:
        st = bounds[0]
        if st.v.lstrip("-").isdigit():
            st = Val(str(max(int(st.v) + n, 0) if int(st.v) < 0 else int(st.v)), "int")
        else:
            neg = self.num_cmp('<', st, Val('0', "int")).v
            sum_ = Val(self.scalar('add', [st, Val(str(n), 'int')]), "int")
            low = Val(self.select(self.num_cmp('<', sum_, Val('0', "int")).v, Val("0", "int"), sum_), "int")
            st = Val(self.select(neg, low, st), "int")
    if len(bounds) > 1:
        en = bounds[1]
        if en.v.lstrip("-").isdigit():
            en = Val(str(int(en.v) + n if int(en.v) < 0 else int(en.v)), "int")
        else:
            neg = self.num_cmp('<', en, Val('0', "int")).v
            en = Val(self.select(neg, Val(self.scalar('add', [en, Val(str(n), 'int')]), "int"), en), "int")
    lend = self.label()
    ph = Ins("phi", "int", "")
    known = st.v.lstrip("-").isdigit() and en.v.lstrip("-").isdigit()
    for i in range(n):
        if known and not int(st.v) <= i < int(en.v):
            continue
        skip = ""
        if not known:
            inr = self.scalar('and', [self.num_cmp('<=', st, Val(str(i), "int")), self.num_cmp('<', Val(str(i), "int"), en)])
            test = self.label()
            skip = self.label()
            self.cbr(inr, test, skip)
            self.place(test)
        self.titem_eq(self.tget(o, i), x, lend, ph, str(i))
        if skip != "":
            self.br(skip)
            self.place(skip)
    self.raise_("ValueError", self.sconst("tuple.index(x): x not in tuple"))
    self.place(lend)
    if len(ph.a) == 0:
        return Val("0", "int")  # (not reached: no item can equal x)
    return Val(self.phi(ph), "int")

# ---- sets: runtime.c's, which make them as CPython's setobject.c does
