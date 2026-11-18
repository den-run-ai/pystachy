"""Function, closure and class records of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.syntax import Node


class FnInfo:
    def __init__(self, name: str, ll: str, node: Node, cls: str):
        self.name = name
        self.ll = ll
        self.node = node
        self.cls = cls
        self.scalar_args = False  # closed body permits eliding unreturned parameter boxes
        self.scalar_only = False  # numeric_proof: no identity observations except returned aliases
        self.idnames: dict[str, bool] = {}  # numeric locals/parameters whose objects can leave
        self.params: list[str] = []
        self.ptypes: list[str] = []
        self.defaults: list[Node] = []
        self.dglob: list[str] = []  # global holding a default evaluated at def time, or ""
        self.uflags: dict[str, bool] = {}  # locals some read may find unassigned
        self.ret = "None"  # "" while a template's function is being compiled, before its first return
        self.mod = ""  # the dotted name of its module ("" for the main program)
        # the identity policy of a closure, generator expression or Callable adapter: that of the
        # code that made it ("-": its module's or its class's, Gen.fn_home)
        self.home = "-"
        self.npos = -1  # how many parameters may be passed by position (-1: all; the rest are keyword-only)
        self.posonly = 0  # how many may only be passed by position
        # templates: a module-level function with an unannotated parameter, compiled per call for
        # the argument types (ptypes "" where unannotated) into the functions in insts
        self.generic = False
        self.void_default = False  # newly inferred concrete signature: recursion may retain its old None contract
        self.insts: dict[str, FnInfo] = {}
        self.dtypes: list[str] = []  # the type of each default value evaluated at def time
        self.sentinels: dict[str, str] = {}  # a parameter p: T = S of a module's sentinel S = object(): S, by parameter (declare_fn)
        self.sentann: dict[str, str] = {}  # and T, the type that a given argument takes
        self.bad = ""  # why a template cannot be compiled (it is an error only if a call needs it)
        self.infer = False  # a template's function: its first return statement decides its return type
        self.rctx = ""  # a caller's result context, only for fresh return displays and forwarding calls
        self.rsoft = False  # a comparison hint retains the original result-inference policy
        self.rlocals: list[str] = []  # proven straight-line aliases forwarding a fresh result
        self.noret = False  # a template's function that has no return and cannot end (it raises, or loops)
        self.inst = False  # a template's function, compiled for one list of argument types
        self.cmprebind = ""  # native reference union for a comparison operand rebound across control flow
        self.cmpops = False  # isolated comparison helpers raise guaranteed builtin TypeErrors at runtime
        self.cmptypes: dict[str, str] = {}  # guarded comparison missing-read layouts, inherited by isolated helper specializations
        self.cmpfields = ""  # a structural comparison adapter's canonical field types; missing reads raise at their source position
        self.ikey = ""  # (an instance: its key in its template's insts, which joins' keys name it by: Gen.fnkey)
        self.lastikey = ""  # (a template: the key of the instance its last call compiled to)
        # a template that returns its own TypeVar (def accept(self, v: Visitor[T]) -> T): that
        # TypeVar, and the parameters whose annotation G[..., T, ...] names it (their indexes, G,
        # and T's position), which an argument of a class deriving from G[X, ...] binds (tv_bound)
        self.tvret = ""
        self.tvbparams: list[int] = []
        self.tvbclass: list[str] = []
        self.tvbpos: list[int] = []
        self.vararg = -1  # the index of a template's *args parameter (a tuple of the extra arguments), or -1
        self.varelem = ""  # its annotation (the type of each extra argument), or ""
        self.kwarg = -1  # the position of its **kwargs parameter, which a template's call gives a record of the extra keyword arguments (kw[...])
        self.kwelem = ""  # its annotation (the type of each extra keyword argument), or ""
        self.vartup = ""  # *args: *Ts, of a specialization of a generic class: the tuple type args is (each call passes its items)
        self.stk = -1  # 1: a call may make its *args tuple in the caller's frame (Gen.stack_ok); -1 not yet known
        self.stknames: dict[str, bool] = {}  # then *args and the locals assigned it, which may hold that tuple
        self.keyread = -1  # 1: it only reads its index key (Gen.key_read): o[i, j] may make that tuple in its frame; -1 not yet known
        self.export = False  # runtime mode: a pys_* function defined under its C name, for runtime.c and programs
        self.extern = False  # runtime mode: a function whose body is `...`, declared under its C name and defined in C
        self.lib = ""  # @ffi.extern's library ("" the process's own)
        self.csym = ""  # and its C symbol
        self.pyexport = False  # @ffi.export: a function an extension module (pystachy ext) gives CPython
        self.iters = False  # an __iter__ that returns an Iterator[T]: ret is the list[T] it steps through (see iter_ret)
        self.synthetic = False  # a dataclass's method that the compiler writes (Gen.synth), not the program
        self.deco = ""  # a method's @staticmethod or @classmethod (whose cls names the class), or "": it takes self
        self.nullable_self = False  # explicit C.m(o, ...): o may be None; checks belong to the body
        self.prop = False  # a @property getter: an attribute read calls this instance method
        # a property's @name.setter or @name.deleter ("setter", "deleter"; its methods key is
        # name.setter): an assignment or del of the attribute calls it; accof: what the decorator
        # names the property by, name or Base.name
        self.acc = ""
        self.accof = ""
        self.clsuse = False  # a class method that uses cls, which names the class that defines it (see cls_bound)
        self.orig = node  # and then its immutable def before cls was renamed (shared by inherited methods)
        self.pending = False  # inherited class method: node shares orig's body until materialize()
        # a template's function: the parameters whose arguments are objects known not to be None
        # (a new object, self), which its isinstance(), hasattr() and "is None" tests read as such
        self.nnp: dict[str, bool] = {}
        # a comparison method (__eq__, __lt__, ...) that returns NotImplemented (Gen.decline): mayd
        # is whether its body may (-1 not read yet, see may_decline), declines whether compiled
        # code of it does, and plain where a call that takes its result as it is was compiled
        self.mayd = -1
        self.declines = False
        self.plain = ""
        # the parameters annotated Callable[[A, B], C] with C a class template: an argument that is
        # a function is that Callable of the specialization it returns (see pat_arg)
        self.pats: dict[int, Node] = {}
        self.anys: list[str] = []  # the parameters annotated typing.Any, "" its return: left unannotated (see declare_fn)
        self.clo = -1  # a closure's function (a def or lambda inside a function): its Gen.closures position
        # a generator function (a def whose own body yields): a call makes a generator object, an
        # LLVM coroutine handle of type gen[Y] (ret; "" while a template's first yield decides Y),
        # and runs none of the body (docs/internals.md#generators)
        self.gen = False
        self.gret = ""  # its return value's type (return v, which yield from gives): "" until a return decides it
        self.gretinfer = False  # no return-value annotation, or Any in Generator[Y, S, R]'s R
        self.gsend = "None"  # what send() sends it (Generator[Y, S, R]'s S): its yields' values are S | None
        self.gclose = False  # closing it while it is suspended may run its code: a yield in try, with or yield from
        self.gwith = False  # a yield inside a with block: its unwind actions are set aside while it is suspended
        self.gtry = False  # a try statement: the exception being handled is its resumer's while it is suspended
        # a generator expression's (Gen.genexp_value) whose first iterable is a generator that only it
        # holds, which this function made: its loop over that iterable (.0) owns it
        self.gfirst: FnInfo | None = None


class Closure:
    # a def or lambda inside a function, as one function (an instance) compiles it (Gen.closure). Its
    # value, of type fn[c:<position in Gen.closures>:<qualified name>], points to an env: the cells of
    # the variables it takes from the functions around it, which they keep those variables in, then
    # the default values that are no constants, evaluated where it is defined
    def __init__(self, f: FnInfo, name: str, qual: str):
        self.f = f  # its function: a template whose first parameter (.env) is the env
        self.name = name  # its __name__: the def's name, or <lambda>
        self.qual = qual  # its __qualname__: outer.<locals>.name
        # the __name__ and __qualname__ that functools.wraps() gives it ("": its own), or why
        # they are not known as Pystachy compiles (wunknown), where reading them is an error;
        # name and qual stay its code's, which messages and its closures' names show
        self.wname = ""
        self.wqual = ""
        self.wunknown = ""
        self.t = ""  # its type
        self.caps: list[str] = []  # the variables it takes, in the env's order
        self.ctypes: list[str] = []  # their types ("None": a parameter whose argument is None, held by no cell)
        self.defs: list[int] = []  # the parameters whose defaults the env holds after the cells
        # a lambda's: the names an import of the function around it binds in a try statement that it
        # reads (lambda_flags), whose flags' cells the env holds after the defaults
        self.iflags: list[str] = []
        # the variables it takes that a closure assigns (nonlocal), which a test does not narrow: a
        # call may change them
        self.nlw: dict[str, bool] = {}


class ClassInfo:
    def __init__(self, name: str, node: Node):
        self.name = name
        self.node = node
        self.fields: list[str] = []
        self.fields_ready = False  # declare_fields prepared this declaration; specializations copy its fields
        self.fields_preparing = False  # recursive class-attribute annotations retain their provisional path
        self.init_only = False  # only constructor code specializes; annotated fields keep one class layout
        self.fpos: dict[str, int] = {}  # field -> its index in fields (and in the struct)
        self.ftypes: dict[str, str] = {}
        self.fdefault: dict[str, Node] = {}
        self.fnone: dict[str, Node] = {}  # field -> the value of __init__ that gave it its first value, None (Gen.none_field)
        self.fguess: dict[str, bool] = {}  # the fields whose type __init__'s values gave them (not annotations: Gen.join_hint)
        self.slots: list[str] = []  # literal __slots__, including inherited slots
        self.slotlimit = False  # every ordinary base and this class omit an instance dict
        self.fglob: dict[str, str] = {}
        self.fextra: dict[str, bool] = {}  # statically reserved comparison writes, absent until assigned
        self.fflag: dict[str, int] = {}  # field -> index of its "is assigned" flag in the struct
        self.fbox: dict[str, int] = {}  # numeric field -> its companion identity-box index
        self.nbox = 0  # own companion boxes after the assignment flags
        self.fsure: dict[str, bool] = {}  # the flagged fields that no read finds unassigned (hasattr tests them)
        self.funset: dict[str, bool] = {}  # the fields an object of exactly this class may be read without (fl_fields)
        self.methods: dict[str, FnInfo] = {}
        self.mod = ""
        self.bad = ""  # why a class of an imported module cannot be compiled: an error where it is used
        self.hook = ""  # the same for a special method Pystachy never calls (UNCALLED): its class statement compiles
        self.excluded = False  # bad_class: it has no objects, and dispatch on a base's class tag leaves it out
        self.kwonly = False  # @dataclass(kw_only=True): its __init__ takes the fields by keyword only
        self.dcopts: dict[str, bool] = {}  # @dataclass(...)'s other options that differ from their defaults (frozen, order, no-eq, ...: dc_args)
        # dataclasses.field(...)'s options of each field that differ from their defaults
        # (no-init, no-repr, no-compare, kw_only), and the default_factory of those that have one
        self.fopts: dict[str, dict[str, bool]] = {}
        self.factory: dict[str, Node] = {}
        # its single base (a class of the program or a builtin exception class), and the
        # builtin exception class it derives from through it ("" for an ordinary class)
        self.base = ""
        # its fieldless secondary bases: those of its primary chain, then its own, in the order
        # CPython's method resolution order takes them
        self.roles: list[str] = []
        self.isrole = False  # some class names this root as its secondary base
        self.isiface = False  # ... and it is no trait of that class: an object typed by it may have that class's layout (role_field)
        self.overlaps: list[str] = []  # unrelated bases with a common concrete subclass
        self.exc = ""
        self.excsecond = ""  # additional builtin exception ancestry; no fields or methods
        self.tag = 0  # ordinary inheritance: the object's concrete class; zero outside a hierarchy
        self.nflag = 0  # the "is assigned" flags at the end of its struct (its own fields')
        self.leak = False  # its __init__ lets self escape before it ends
        self.flowed = False  # fl_fields has decided its flags
        # a class template (an __init__ parameter without an annotation): its specializations,
        # named by the types its fields get (see specialize); a specialization: its template
        self.specs: dict[str, str] = {}
        self.nspec = 0  # (the names it has given: one each, also to those found to be one already made)
        self.origin = ""
        self.speckey = ""  # (a specialization: the types of the call that made it, see Gen.stable)
        # a specialization of a generic class (Gen.tparams): the types its type variables are bound
        # to, by the call that made it (Gen.bind); a TypeVarTuple's is a tuple type of its types
        self.tvars: dict[str, str] = {}
        # a specialization of a class that specializes on literal arguments (Gen.literal_class):
        # its __init__'s parameters given literals, and its fields that hold constants, as the
        # literal nodes of their values (see Gen.const_of)
        self.lits: dict[str, Node] = {}
        self.fconst: dict[str, Node] = {}
