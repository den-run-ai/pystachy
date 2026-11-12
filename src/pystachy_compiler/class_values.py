"""Class objects as values component of the self-hosting Pystachy compiler.

An ordinary class of the program is a value where a module that does not opt in to dynamic Any
uses one (#7): k = B, f(B), [A, B], {"b": B}, self.kind = kind, type(x) kept in a variable. Its
type is type[C], the class object of C or of a class deriving from C, and the value is a pointer
to that class's reflection record (reflection.py's refl_record: name, qualified name, module),
the constant that type(x).__name__ and type(x) is C already read and compare. A record is the
one class object of its class, so identity compares and hashes class objects (runtime.c's
descriptor Y, which writes their repr too: <class 'module.Qualname'>); it is no collected object
and needs no root. type(x) of an x that is None is NoneType's record, which a type[C] value may
therefore be as well.

A call of a class object makes an object of the class it is. The source fixes the classes a
type[C] value may be, C and those deriving from it, so the call compares the record with each
class's and runs that class's constructor, as the call that names the class does (class_new).
Exception classes keep the class objects exceptions.py gives them (exctype), and an enum class
its EnumType object.
"""
from __future__ import annotations
from src.pystachy_compiler.diagnostics import dynamic_program, where
from src.pystachy_compiler.ir import Ins, Val
from src.pystachy_compiler.names import ENUMCLASSES, short
from src.pystachy_compiler.syntax import Node, mk
from src.pystachy_compiler.utils import clsof, is_clsval, is_opt, is_union, pure_arg, typestr, unopt

NONETYPE_ARGS = "NoneType takes no arguments"


def gen_class_value_named(self, c: str) -> bool:
    # does type[c] name a class object of this module: c is an ordinary class of the program (an
    # exception class's class object is an exctype, an enum class's its EnumType object)
    return c in self.classes and self.classes[c].exc == "" and self.classes[c].node.line not in ENUMCLASSES


def gen_class_value_problem(self, c: str) -> str:
    # why class c of the program has no class object as a value, or ""
    if not self.class_value_named(c):
        return f"class '{short(c)}' cannot be used as a value"
    ci = self.classes[c]
    if ci.bad != "":
        return ci.bad
    if c in self.tparams:
        return f"generic class '{short(c)}' cannot be used as a value: its objects are its specializations'"
    if c in self.tmpl or ci.origin != "":
        return f"class '{short(c)}' cannot be used as a value: it is a class template (its __init__ has a parameter without an annotation), whose objects are its specializations'; annotate the parameters"
    if self.refl_type_name(c, "__name__") == "":
        return f"class '{short(c)}' cannot be used as a value"
    for a in ["__module__", "__qualname__"]:
        # (the record holds the names CPython gives the class, not ones its body assigns)
        if not dynamic_program() and a in ci.fdefault and self.default_home(ci, a) is ci:
            return f"class '{short(c)}' cannot be used as a value: its body assigns {a}"
    return self.refl_class_problem(c)


def gen_class_value(self, c: str) -> Val:
    # class c of the program as a value: its class object, the reflection record of the class
    problem = self.class_value_problem(c)
    if problem != "":
        self.err(problem)
    m = self.classes[c].mod
    if m != self.curfn.mod and m in self.comp and self.curfn.mod in self.comp and self.comp[m] == self.comp[self.curfn.mod]:
        # (CPython's read of M.C in a circular import depends on how far each module's code has
        # run: a submodule is its package's attribute only once its code has ended, and an alias
        # is bound where its statement runs, which "ready" does not check, #804)
        self.err(f"class '{c}' cannot be used as a value here: its module and this one import each other (a circular import), where the read depends on how far each module's code has run")
    return Val(self.refl_record(c), "type[" + c + "]")


def gen_class_value_kinds(self, c: str) -> list[str]:
    # the classes whose class object a type[c] value may be: c and the classes deriving from it
    # that have objects (in the order of their class statements)
    return [k.name for k in self.classes.values() if k.exc == "" and not k.excluded and k.bad == "" and k.origin == "" and k.name not in self.tmpl and self.derives(k.name, c)]


def gen_class_value_bases(self, c: str, top: str) -> list[str]:
    # c and the classes it derives from that are top or derive from it: the classes that
    # isinstance() of an object of c, and issubclass() of c's class object, are true of
    return [k.name for k in self.classes.values() if k.exc == "" and self.derives(c, k.name) and self.derives(k.name, top)]


def gen_class_value_holds(self, t: str) -> bool:
    # is t the type of a class object (which may be None)
    return is_clsval(unopt(t))


def gen_class_value_of(self, v: Val, known: bool) -> Val:
    # type(v) (v.__class__) of an object v of an ordinary class as a value: the class object of
    # its class, by its class tag where classes derive from v's; NoneType's where v is None
    t = unopt(v.t)
    for leaf in self.refl_type_of(v, "__name__", known):
        if leaf.c != "None":
            problem = self.class_value_problem(leaf.c)
            if problem != "":
                self.err(problem)
    return Val(self.refl_class_of(v, known).v, "type[" + t + "]")


def gen_class_value_name(self, v: Val, what: str) -> Val:
    # c.__name__, c.__qualname__ and c.__module__ of class object c: its record's first words
    v = self.unwrap(v, f"AttributeError: 'NoneType' object has no attribute '{what}'")
    word = 0 if what == "__name__" else 1 if what == "__qualname__" else 2
    a = self.maddr('%ptr', v.v, str(word)) if word > 0 else v.v
    return Val(self.mload('str', a), "str")


def gen_class_value_asks(self, op: str, a: Val, b: Val) -> bool:
    # is a == b or a != b, one of them a class object, decided by the other's class: an object
    # whose class, or a class deriving from it, defines __eq__ or __ne__, which CPython calls
    # with the class object (cmp2's comparison of objects compiles that call)
    o = b if is_clsval(unopt(a.t)) else a
    if (op != "==" and op != "!=") or o.t not in self.classes:
        return False
    for c in self.classes.values():
        if self.derives(c.name, o.t) and ("__eq__" in c.methods or "__ne__" in c.methods):
            return True
    return False


def gen_class_value_cmp(self, op: str, a: Val, b: Val) -> Val:
    # ==, !=, is and is not with a class object: by identity (each class has one). A class
    # object is no value of another type, so it equals one only where both are None (an object
    # whose class defines __eq__ or __ne__ is asked instead: class_value_asks)
    k = a if is_clsval(unopt(a.t)) else b
    o = b if is_clsval(unopt(a.t)) else a
    same = op == "==" or op == "is"
    if is_clsval(unopt(o.t)) or o.t == "None":
        return self.ptr_cmp("==" if same else "!=", a, b)
    if o.t == "dyn" or is_union(unopt(o.t)):
        self.err(f"comparing a class with {typestr(o.t)} is not supported")
    if is_opt(k.t) and (is_opt(o.t) or o.t in self.classes):
        # (both may be None, and None is None)
        both = Val(self.scalar('and', [self.ptr_cmp("==", k, Val("null", "None")), self.ptr_cmp("==", o, Val("null", "None"))]), "bool")
        return both if same else Val(self.scalar('xor', [both, Val("true", "bool")]), "bool")
    return Val("false" if same else "true", "bool")


def gen_class_value_is(self, k: Val, c: str) -> Val:
    # whether class object k is class c's
    return self.ptr_cmp("==", k, Val(self.refl_record(c), k.t))


def gen_class_value_sub(self, c: str, k: Val) -> Val:
    # whether class c is the class of class object k or derives from it: k is the class object
    # of c or of one of the classes c derives from (among those k's type lets it be)
    out = Val("false", "bool")
    for b in self.class_value_bases(c, clsof(k.t)):
        hit = self.class_value_is(k, b)
        out = hit if out.v == "false" else Val(self.scalar('or', [out, hit]), "bool")
    return out


def gen_class_value_isinst(self, v: Val, k: Val, known: bool) -> Val:
    # isinstance(v, k) of an object v of an ordinary class and class object k: whether v's class
    # is k's or derives from it, by v's class tag; None is an instance of NoneType's alone
    k = self.unwrap(k, "TypeError: isinstance() arg 2 must be a type, a tuple of types, or a union")
    leaves = self.refl_split(v, known)
    end = self.label()
    ph = Ins("phi", "bool", "")
    for leaf in leaves:
        self.place(leaf.label)
        r = self.class_value_is(k, "None") if leaf.c == "None" else self.class_value_sub(leaf.c, k)
        self.incoming(ph, r.v, self.cur)
        self.br(end)
    self.place(end)
    return Val(self.phi(ph), "bool")


def gen_class_value_issub(self, k: Val, t: Node) -> Val:
    # issubclass(k, t) of class object k: t names an ordinary class, or is a class object
    k = self.unwrap(k, "TypeError: issubclass() arg 1 must be a class")
    base = clsof(k.t)
    kinds = self.class_value_kinds(base)
    if t.kind == "name" and t.s in self.classes and t.s not in self.ltype:
        # (a class named: the classes k may be that derive from it)
        self.isinst_reads(t)
        if not self.class_value_named(t.s):
            return Val("false", "bool")  # (no ordinary class derives from an exception or enum class)
        if self.derives(base, t.s):
            return self.ptr_cmp("!=", k, Val(self.refl_record("None"), k.t))  # (every class k may be, but NoneType)
        out = Val("false", "bool")
        for c in kinds:
            if self.derives(c, t.s):
                isk = self.class_value_is(k, c)
                out = isk if out.v == "false" else Val(self.scalar('or', [out, isk]), "bool")
        return out
    if t.kind == "name" and t.s == "object" and not self.bound("object"):
        return Val("true", "bool")  # (every class derives from object, NoneType too)
    o = self.expr(t, "")
    if o.t == "exctype" or o.t.startswith("fn[b:"):
        return Val("false", "bool")  # (an exception class, or a builtin type such as int: no class k may be derives from one)
    if not is_clsval(unopt(o.t)):
        self.err(f"issubclass() of a class takes a class or a class object as its second argument, not {typestr(o.t)}")
    o = self.unwrap(o, "TypeError: issubclass() arg 2 must be a class, a tuple of classes, or a union")
    end = self.label()
    ph = Ins("phi", "bool", "")
    for c in kinds:
        hit = self.label()
        miss = self.label()
        self.cbr(self.class_value_is(k, c).v, hit, miss)
        self.place(hit)
        self.incoming(ph, self.class_value_sub(c, o).v, self.cur)
        self.br(end)
        self.place(miss)
    # (NoneType's class object, which derives from no class of the program)
    self.incoming(ph, self.ptr_cmp("==", k, o).v, self.cur)
    self.br(end)
    self.place(end)
    return Val(self.phi(ph), "bool")


def gen_class_value_dynamic(self, t: Node) -> bool:
    # is t, isinstance's or issubclass's second argument, an expression that gives a class
    # object of an ordinary class, as types tell without compiling t: a variable, a field of an
    # object a variable holds, type(x) of an object x, a conditional expression whose values
    # hold or name such classes, or another expression that is no type, as dry() types it
    # (kinds[0], pick(), a.b.c). Not a class named (the static test decides those), a tuple or
    # a union
    if self.dyn_policy(self.line):
        return False
    if t.kind == "name":
        if t.s not in self.ltype and (t.s in self.classes or t.s not in self.gtypes):
            return False
        return is_clsval(unopt(self.static_type(t)))
    if t.kind == "ifexp":
        for k in t.kids[1:]:
            named = k.kind == "name" and k.s not in self.ltype and self.class_value_named(k.s)
            if not named and not self.class_value_dynamic(k):
                return False
        return True
    x: Node | None = None
    if t.kind == "call" or (t.kind == "attr" and t.s == "__class__"):
        x = self.refl_typeof(t)
    if x is not None:
        return self.class_value_named(unopt(self.dry(x)))
    if t.kind == "attr" and t.kids[0].kind == "name" and self.dotted(t) == "":
        o = unopt(self.static_type(t.kids[0]))
        return o in self.classes and t.s not in self.classes[o].methods and is_clsval(unopt(self.classes[o].ftypes.get(t.s, "")))
    if (t.kind == "call" or t.kind == "index" or (t.kind == "attr" and t.s != "__class__")) and self.dotted(t) == "" and not self.puretype(t, False):
        return is_clsval(unopt(self.dry(t)))
    return False


def gen_class_value_call(self, c: Val, args: list[Node]) -> Val:
    # c(args) of class object c: an object of the class it is. CPython evaluates c, then the
    # arguments, then calls: a c that is None raises its TypeError then, and each class c may be
    # runs its own constructor with the values. NoneType's class object, which type(x) gives of
    # an x that is None, makes None of no arguments, as CPython's does
    base = clsof(unopt(c.t))
    nodes: list[Node] = []
    for a in args:
        if a.kind == "starred" or a.kind == "dstar":
            self.err("a call of a class held as a value is not supported with * or ** arguments: pass them one by one")
        x = a.kids[0] if a.kind == "kw" else a
        y = x if pure_arg(x) else self.vnode(self.expr(x, ""))
        nodes.append(mk("kw", a.s, a.line, [y]) if a.kind == "kw" else y)
    c = self.unwrap(c, "TypeError: 'NoneType' object is not callable")
    kinds = self.class_value_kinds(base)
    for k in kinds:
        if c.v == self.refl_record(k):
            return Val(self.class_new(k, nodes, "").v, base)  # (the class a constant names)
    end = self.label()
    ph = Ins("phi", base, "")
    made = 0
    for k in kinds:
        hit = self.label()
        miss = self.label()
        self.cbr(self.class_value_is(c, k).v, hit, miss)
        self.place(hit)
        # (an error in a class's constructor call names the class object it is one of)
        self.making.append(f"making an object of {short(k)}, a class that the {typestr(c.t)} called at {where(self.line)} may be")
        o = self.class_new(k, nodes, "")
        self.making.pop()
        if not self.term:
            self.incoming(ph, o.v, self.cur)
            made += 1
            self.br(end)
        self.place(miss)
    self.guard(self.ptr_cmp("!=", c, Val(self.refl_record("None"), c.t)).v, "TypeError: cannot create an object of this class through its class object")
    if len(nodes) > 0:
        self.raise_("TypeError", self.sconst(NONETYPE_ARGS))
    else:
        self.incoming(ph, "null", self.cur)
        made += 1
        self.br(end)
    if made == 0:
        return Val("null", base)
    self.place(end)
    return Val(self.phi(ph), base)
