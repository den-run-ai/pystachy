"""Class objects as values component of the self-hosting Pystachy compiler.

An ordinary class of the program is a value where a module uses one (#7): k = B, f(B), [A, B],
{"b": B}, self.kind = kind, type(x) kept in a variable. Its
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

A module that opts in to dynamic Any made a class box of each class it used as a value, an Any
value (reflection.py's refl_class_value: the record, with type's DynType), before class objects
were typed. It reads its classes as typed class objects too, and a class object that an Any
location takes is that box (class_value_box), which a type[C] location takes back
(class_value_unbox). A program that such a module compiled before must compile as it did, with
all it could do with a box: where a program that names no type[C] does not compile with typed
class objects, or stores an Any value where a class object's type was inferred, the driver
compiles it again with the classes read as boxes in the opted-in modules that name no type[C]
themselves (ClassBoxes, class_value_static).
"""
from __future__ import annotations
from src.pystachy_compiler.diagnostics import LINES, ClassBoxes, dynamic_program, where
from src.pystachy_compiler.ir import Data, Ins, Val
from src.pystachy_compiler.names import ENUMCLASSES, short
from src.pystachy_compiler.specs import ITERS, OBJECTC, RANGEC
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


def gen_class_value_static(self, c: str, mod: str, line: int) -> bool:
    # is class c's class object a typed value (type[c]) where code at source line line of module
    # mod ("": not known), which opts in to dynamic Any, reads it: where it is one in other
    # modules. Else the module keeps the class box it has always made of the class there
    # (reflection.py's refl_class_value), an Any value: as do all its reads once the program
    # does not compile with typed ones (ClassBoxes: the driver's clsany), so that the modules
    # compiled before class objects were typed are compiled as they were. A module that names
    # type[C] itself was not compiled then: its reads stay typed, and its errors are theirs
    if line // LINES in self.clsany or not self.class_value_named(c) or self.class_value_problem(c) != "":
        return False
    if c == OBJECTC or c == RANGEC or c.startswith(ITERS + "$"):
        # (lib's classes of object()'s objects, of ranges and of iterators: in a program with
        # such a module their class values are the builtin classes', object and range, whose
        # records they share: reflection.py's refl_record)
        return False
    m = self.classes[c].mod
    if mod != "" and m != mod and m in self.comp and mod in self.comp and self.comp[m] == self.comp[mod]:
        return False
    if not self.class_value_annotated(line // LINES):
        self.clsused[line // LINES] = True
    return True


def gen_class_value_annotated(self, file: int) -> bool:
    # does the module of source file file name type[C] of an ordinary class C (in an annotation:
    # nothing else subscripts type): it was not compiled before class objects were typed
    if self.clsann < 0:
        self.clsann = 0
        for body in self.clsbodies:
            if len(body.kids) > 0 and type_subscript(self, body.kids):
                self.clsannfiles[body.kids[0].line // LINES] = True
    return file in self.clsannfiles


def type_subscript(self, ns: list[Node]) -> bool:
    for n in ns:
        if n.kind == "index" and len(n.kids) == 2 and n.kids[0].kind == "name" and n.kids[0].s == "type" and n.kids[1].kind == "name" and self.class_value_named(n.kids[1].s):
            return True
        if type_subscript(self, n.kids):
            return True
    return False


def gen_class_value_box(self, v: Val) -> Val:
    # class object v (or None) as an Any value: a class box of its record, the constant that a
    # module that opts in to dynamic Any has always made of a class it names where the record
    # is known (refl_class_value)
    if v.v == "null":
        return Val(self.rtdata("pys_dyn_none_box"), "dyn")
    if v.v.startswith("@pys.refl."):
        name = "@dbc." + v.v[1:]
        if name not in self.dynboxes:
            self.dynboxes[name] = True
            box = Data("dynbox", name)
            box.refs = [self.rtdata("pys_dyntype_type"), v.v]
            self.consts.append(box)
        return Val(name, "dyn")
    if not is_opt(v.t):
        return Val(self.rt("pys_dyn_ref", "ptr", [f"ptr {self.rtdata('pys_dyntype_type')}", f"ptr {v.v}"]), "dyn")
    some = self.label()
    end = self.label()
    ph = Ins("phi", "dyn", "")
    self.incoming(ph, self.rtdata("pys_dyn_none_box"), self.cur)
    self.cbr(self.ptr_cmp("==", v, Val("null", "None")).v, end, some)
    self.place(some)
    made = self.rt("pys_dyn_ref", "ptr", [f"ptr {self.rtdata('pys_dyntype_type')}", f"ptr {v.v}"])
    self.incoming(ph, made, self.cur)
    self.br(end)
    self.place(end)
    return Val(self.phi(ph), "dyn")


def gen_class_value_isa(self, v: Val, t: str) -> str:
    # i1: is Any value v the class box of a class that a value of type t (type[C]) may be
    end = self.label()
    box = self.label()
    ph = Ins("phi", "bool", "")
    self.incoming(ph, "false", self.cur)
    self.cbr(self.ptr_cmp("==", Val(self.dyn_typeof(v), "dyntype"), Val(self.rtdata("pys_dyntype_type"), "dyntype")).v, box, end)
    self.place(box)
    rec = Val(self.mload("%ptr", self.maddr("%ptr", v.v, "1")), "%ptr")
    r = "false"
    for k in self.class_value_kinds(clsof(t)) + ["None"]:
        # (NoneType's too, which type(x) of an x that is None gives a typed location)
        if k == "None" or self.class_value_problem(k) == "":
            x = self.scalar_cmp("eq", rec, Val(self.refl_record(k), "%ptr"))
            r = x if r == "false" else self.scalar("or", [Val(r, "bool"), Val(x, "bool")])
    self.incoming(ph, r, self.cur)
    self.br(end)
    self.place(end)
    return self.phi(ph)


def gen_class_value_unbox(self, v: Val, t: str) -> Val:
    # Any value v as a class object of type t (type[C]): its record where v is the class box of
    # C or of a class deriving from it, else TypeError (as a typed location takes an Any value)
    if len(self.clsused) > 0:
        raise ClassBoxes()  # (the type may be inferred of a class a module read: that module's class box)
    self.guard(self.scalar("xor", [Val(self.class_value_isa(v, t), "bool"), Val("true", "bool")]), f"TypeError: expected {typestr(t)}")
    return Val(self.mload("%ptr", self.maddr("%ptr", v.v, "1")), t)


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


def gen_class_value_typed(self, v: Val, known: bool) -> bool:
    # is type(v) a typed class object (class_value_of) in a module that opts in to dynamic Any: v
    # is an object of an ordinary class, each class that it may be one with a class object
    if not self.class_value_named(unopt(v.t)):
        return False
    for leaf in self.refl_type_of(v, "__name__", known):
        if leaf.c != "None" and not self.class_value_static(leaf.c, self.curfn.mod, self.line):
            return False
    return True


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
    named = t.kind == "name" and t.s in self.classes and t.s not in self.ltype
    anyclass = t.kind == "name" and t.s == "object" and not self.bound("object")
    # CPython evaluates both arguments before it checks either: the second is read, or
    # evaluated, before a first that is None raises
    o = Val("", "")
    if named:
        self.isinst_reads(t)
    elif not anyclass:
        o = self.expr(t, "")
        if o.t.startswith("fn[b:") and o.t[5:-1] not in "int float bool str bytes bytearray list dict set frozenset tuple object type range complex memoryview slice".split():
            # (a builtin function, such as len, is no class: CPython's TypeError)
            self.err("issubclass() arg 2 must be a class, a tuple of classes, or a union")
    k = self.unwrap(k, "TypeError: issubclass() arg 1 must be a class")
    base = clsof(k.t)
    kinds = self.class_value_kinds(base)
    if named:
        # (a class named: the classes k may be that derive from it)
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
    if anyclass:
        return Val("true", "bool")  # (every class derives from object, NoneType too)
    if o.t == "fn[b:object]":
        return Val("true", "bool")  # (object, read through a variable: every class derives from it, as where it is named)
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
        if not self.class_value_named(unopt(self.dry(x))):
            return False
        # (where a module opts in to dynamic Any, type(x) may be a class box: class_value_typed)
        return not self.dyn_policy(self.line) or is_clsval(unopt(self.dry(t)))
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


# the names NoneType's class object has itself (dir(type(None))): a class attribute of such a
# name is not read through a class object, which may be NoneType's (but __doc__, a str)
NONETYPE_NAMES = "__bool__ __class__ __delattr__ __dir__ __doc__ __eq__ __format__ __ge__ __getattribute__ __getstate__ __gt__ __hash__ __init__ __init_subclass__ __le__ __lt__ __ne__ __new__ __reduce__ __reduce_ex__ __repr__ __setattr__ __sizeof__ __str__ __subclasshook__"


def gen_class_value_attr(self, k: Val, name: str) -> Val:
    # k.name of class object k, a class attribute (a name the class body binds): that of the
    # class k is, which is C's unless a class deriving from C binds the name anew. NoneType's
    # class object (type(x) of an x that is None) has none: CPython's AttributeError
    base = clsof(unopt(k.t))
    k = self.unwrap(k, f"AttributeError: 'NoneType' object has no attribute '{name}'")
    t = self.classes[base].ftypes[name]
    kinds = self.class_value_kinds(base)
    for c in kinds:
        if k.v == self.refl_record(c):
            return self.coerce(self.class_attr(mk("name", c, self.line, []), name), t)  # (the class a constant names)
    if name in NONETYPE_NAMES.split() and not (name == "__doc__" and t == "str"):
        self.err(f"reading {name} through a class object ({typestr(k.t)}) is not supported: the value may be NoneType's class object, which has its own {name}")
    end = self.label()
    ph = Ins("phi", t, "")
    vals: list[Val] = []
    edges: list[str] = []
    for c in kinds:
        hit = self.label()
        miss = self.label()
        self.cbr(self.class_value_is(k, c).v, hit, miss)
        self.place(hit)
        v = self.coerce(self.class_attr(mk("name", c, self.line, []), name), t)
        self.incoming(ph, v.v, self.cur)
        vals.append(v)
        edges.append(self.cur)
        self.br(end)
        self.place(miss)
    if name == "__doc__":
        # (NoneType's own, which CPython reads of the class object of None)
        v = Val(self.sconst("The type of the None singleton."), "str")
        self.incoming(ph, v.v, self.cur)
        vals.append(v)
        edges.append(self.cur)
        self.br(end)
    else:
        self.raise_("AttributeError", self.sconst(f"type object 'NoneType' has no attribute '{name}'"))
        if len(kinds) == 0:
            return Val("undef", t)
    self.place(end)
    # (a number keeps the identity of the class attribute it is, as a read through the class does)
    return self.numeric_phi(Val(self.phi(ph), t), vals, edges)


def gen_class_value_method(self, k: Val, name: str, args: list[Node], want: str, resultsoft: bool) -> Val:
    # k.name(args) of class object k, a method of its class: the call that names the class k is
    # (C.name(args): a static method, or a class method, whose cls is that class). CPython reads
    # k.name first, which None and NoneType's class object do not have, then evaluates the
    # arguments, then calls; the result has the type that the calls through each class k may
    # be share
    base = clsof(unopt(k.t))
    for a in args:
        if a.kind == "starred" or a.kind == "dstar":
            self.err("a method call through a class held as a value is not supported with * or ** arguments: pass them one by one")
    k = self.unwrap(k, f"AttributeError: 'NoneType' object has no attribute '{name}'")
    if not k.v.startswith("@"):
        self.guard(self.ptr_cmp("==", k, Val(self.refl_record("None"), k.t)).v, f"AttributeError: type object 'NoneType' has no attribute '{name}'")
    nodes: list[Node] = []
    for a in args:
        x = a.kids[0] if a.kind == "kw" else a
        y = x if pure_arg(x) else self.vnode(self.expr(x, ""))
        nodes.append(mk("kw", a.s, a.line, [y]) if a.kind == "kw" else y)
    kinds = self.class_value_kinds(base)
    for c in kinds:
        if k.v == self.refl_record(c):
            return self.class_call(mk("name", c, self.line, []), name, nodes, want, resultsoft)  # (the class a constant names)
    t = ""
    for c in kinds:
        self.making.append(f"calling {short(c)}.{name}(), of a class that the {typestr(k.t)} at {where(self.line)} may be")
        rt = self.dry(mk("call", "", self.line, [mk("attr", name, self.line, [mk("name", c, self.line, [])])] + nodes), want)
        self.making.pop()
        j = rt if t == "" or t == rt else self.join(t, rt)
        if j == "":
            self.err(f"{short(base)}.{name}() returns {typestr(t)}, and {short(c)}.{name}() of a class deriving from it {typestr(rt)}: a call through a class object has one type")
        t = j
    valued = t != "" and t != "None"
    end = self.label()
    ph = Ins("phi", t if valued else "int", "")
    vals: list[Val] = []
    edges: list[str] = []
    for c in kinds:
        hit = self.label()
        miss = self.label()
        self.cbr(self.class_value_is(k, c).v, hit, miss)
        self.place(hit)
        self.making.append(f"calling {short(c)}.{name}(), of a class that the {typestr(k.t)} at {where(self.line)} may be")
        r = self.class_call(mk("name", c, self.line, []), name, nodes, want, resultsoft)
        self.making.pop()
        if not self.term:
            if valued:
                r = self.coerce(r, t)
                self.incoming(ph, r.v, self.cur)
                vals.append(r)
                edges.append(self.cur)
            self.br(end)
        self.place(miss)
    self.raise_("AttributeError", self.sconst(f"type object 'NoneType' has no attribute '{name}'"))
    self.place(end)
    # (a number that a call returns keeps its identity, as the call through the class does)
    return self.numeric_phi(Val(self.phi(ph), t), vals, edges) if valued else Val("null", "None")
