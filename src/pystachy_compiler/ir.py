"""Ir component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.specs import FXALL
from src.pystachy_compiler.syntax import Node


class Val:
    def __init__(self, v: str, t: str):
        self.v = v
        self.t = t


class Data:
    # Immutable module data: string bytes, callable/exception references, or constant tuple slots.
    # LLVM's concrete layout and declaration syntax belong to lower_module.
    def __init__(self, kind: str, name: str):
        self.kind = kind
        self.name = name
        self.text = ""
        self.refs: list[str] = []
        self.items: list[Val] = []  # tuple slots: int literals or static string references


class IterArg:
    # A consumer's next argument: evaluate it after its iterator is constructed, before traversal.
    # With split, a label, there is none: the code after the iterator is constructed goes on at
    # split, and the traversal waits at trav for a branch to it (the consumer's turn to iterate).
    def __init__(self, node: Node):
        self.node = node
        self.value = Val("", "")
        self.split = ""
        self.trav = ""


class Reduce:
    # sum(), min() or max() of a generator, whose items are added or compared as they come
    # (Gen.reduce): its accumulators are made as the item is compiled, once its type is known, and
    # set at the IterArg's split, which runs after the iterator is made and before the traversal
    def __init__(self, name: str, stt: str):
        self.name = name
        self.stt = stt  # sum's start: its type, or "" where none is given
        self.t = ""  # the items' type
        self.acc = ""  # the sum so far, or the item kept (or the list of the items, collect)
        self.comp = ""  # a float sum's compensation, as runtime.c's fsum keeps it (Neumaier's)
        self.first = ""  # no item yet: min and max, and a float sum from an int start
        self.collect = False  # min() or max() of items runtime.c compares (pys_list_minmax)


class SetArg:
    # An argument of a set method that takes several iterables, evaluated with the others before
    # the method iterates any: v, the value of an iterable, or gen, a generator expression whose
    # iterator was made then (arg split), whose traversal starts at arg.trav and comes back to back.
    def __init__(self, v: Val, gen: Node):
        self.v = v
        self.gen = gen
        self.arg = IterArg(gen)
        self.back = ""


class SeqStart:
    # The state of a for loop's iterators (Gen.for_seq), each taken when the iterator is made, as
    # CPython's records it: a sequence's length then (used), and the position it reads next (st):
    # a dict's or a set's slot, a list's or a str's length for reversed() (else unused).
    def __init__(self) -> None:
        self.st: list[str] = []
        self.used: list[str] = []


class FmtArgs:
    # The arguments of a str.format() call with a constant format (Gen.str_format), evaluated:
    # the positional ones (pos), then a list of those that a list's * gives at run time (rest),
    # the keywords by name (kwn, kwv) and a dict that ** gives (kd); format_map()'s mapping is
    # kd, with mapping set. auto: CPython's AutoNumber, its state (0 none yet, 1 automatic,
    # 2 manual) and the next automatic index.
    def __init__(self, who: str) -> None:
        self.who = who
        self.pos: list[Val] = []
        self.rest = Val("", "")
        self.kwn: list[str] = []
        self.kwv: list[Val] = []
        self.kd = Val("", "")
        self.mapping = False
        self.auto: list[int] = [0, 0]


class FnInfo:
    def __init__(self, name: str, ll: str, node: Node, cls: str):
        self.name = name
        self.ll = ll
        self.node = node
        self.cls = cls
        self.params: list[str] = []
        self.ptypes: list[str] = []
        self.defaults: list[Node] = []
        self.dglob: list[str] = []  # global holding a default evaluated at def time, or ""
        self.uflags: dict[str, bool] = {}  # locals some read may find unassigned
        self.ret = "None"  # "" while a template's function is being compiled, before its first return
        self.mod = ""  # the dotted name of its module ("" for the main program)
        self.npos = -1  # how many parameters may be passed by position (-1: all; the rest are keyword-only)
        self.posonly = 0  # how many may only be passed by position
        # templates: a module-level function with an unannotated parameter, compiled per call for
        # the argument types (ptypes "" where unannotated) into the functions in insts
        self.generic = False
        self.void_default = False  # newly inferred concrete signature: recursion may retain its old None contract
        self.insts: dict[str, FnInfo] = {}
        self.dtypes: list[str] = []  # the type of each default value evaluated at def time
        self.bad = ""  # why a template cannot be compiled (it is an error only if a call needs it)
        self.infer = False  # a template's function: its first return statement decides its return type
        self.rctx = ""  # a caller's result context, only for fresh return displays and forwarding calls
        self.rsoft = False  # a comparison hint retains the original result-inference policy
        self.rlocals: list[str] = []  # proven straight-line aliases forwarding a fresh result
        self.noret = False  # a template's function that has no return and cannot end (it raises, or loops)
        self.inst = False  # a template's function, compiled for one list of argument types
        self.vararg = -1  # the index of a template's *args parameter (a tuple of the extra arguments), or -1
        self.varelem = ""  # its annotation (the type of each extra argument), or ""
        self.kwarg = -1  # the position of its **kwargs parameter, which a template's call gives a record of the extra keyword arguments (kw[...])
        self.kwelem = ""  # its annotation (the type of each extra keyword argument), or ""
        self.vartup = ""  # *args: *Ts, of a specialization of a generic class: the tuple type args is (each call passes its items)
        self.stk = -1  # 1: a call may make its *args tuple in the caller's frame (Gen.stack_ok); -1 not yet known
        self.stknames: dict[str, bool] = {}  # then *args and the locals assigned it, which may hold that tuple
        self.export = False  # runtime mode: a pys_* function defined under its C name, for runtime.c and programs
        self.extern = False  # runtime mode: a function whose body is `...`, declared under its C name and defined in C
        self.lib = ""  # @ffi.extern's library ("" the process's own)
        self.csym = ""  # and its C symbol
        self.pyexport = False  # @ffi.export: a function an extension module (pystachy ext) gives CPython
        self.iters = False  # an __iter__ that returns an Iterator[T]: ret is the list[T] it steps through (see iter_ret)
        self.synthetic = False  # a dataclass's method that the compiler writes (Gen.synth), not the program
        self.deco = ""  # a method's @staticmethod or @classmethod (whose cls names the class), or "": it takes self
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


NONUMS: list[int] = []
NOVALS: list[Val] = []
NOLABELS: list[str] = []


class Ins:
    # one instruction: op decides which fields mean something
    def __init__(self, op: str, t: str, s: str):
        self.op = op  # a key of IROPS
        self.t = t  # its result type ("" if it defines no value; an rt op's as RUNTIME spells it), a slot's type
        # slot.pack/unpack keep the native type in the operand/result and use %slot for
        # the opaque eight-byte container payload. Only LLVM lowering chooses its bitcast.
        # union.tag reads a nonoptional union's tag; union.payload reads its member's
        # opaque slot (s: member type, r: address then payload). Narrowing proves those reads safe.
        # num.cast promotes one numeric operand; num.cmp records the source comparison
        # in s and compares two operands of the same native numeric type.
        # empty.kind fixes a fresh dict/set result's key layout, using its typed
        # operand or the deferred type hole k; it never retypes a filled container.
        # mem.load/store transfer native values through an address of type *<native>.
        # Their effects retain local/global/field/unknown address classification.
        # mach.load/store additionally access runtime headers, closure slots and byte
        # buffers through %ptr. s is finite metadata: length, length.range, bytes or empty.
        # mach.addr computes an indexed address: s is its machine element type, a holds
        # the pointer and int index, and k is the inbounds flag. No LLVM text is retained.
        # int.ucmp retains unsigned order semantics for native int bounds checks.
        # ptr.cmp tests native reference identity (==/!=), including None's null.
        # alloc.fixed keeps the class or fixed tuple type; lowering computes its byte size.
        # tuple.load/store use a fixed tuple operand, k: item index, s: native item type.
        # They transfer an opaque slot; r holds its address, then the loaded slot if any.
        # text immediate: a slot's name; an rt op's RUNTIME key; the
        # symbol a call calls; the module an init runs; a check's message "Kind: text"; the
        # exception a raise raises; ovf's operator + - *
        self.s = s
        # int immediate: a slot's kind (1: an "is assigned" flag), a hole (Gen.holes, from 1), the
        # layout index or a finite machine-address flag
        self.k = 0
        # an rt op's descriptor of the static type it works on (for its # parameter): RUNTIME's U?
        # is U when it holds a class (O<id>), or an exception (E) in a program that makes objects of
        # exception classes
        self.x = ""
        self.r: list[int] = NONUMS  # the numbers of the values it defines, given when it was built
        self.a: list[Val] = NOVALS  # operands, in evaluation order (an rt op's typed as RUNTIME spells its parameters)
        self.b: list[str] = NOLABELS  # labels: the successors of br, cbr and check; a phi's predecessors


class Blk:
    # one basic block, which becomes one LLVM block
    def __init__(self, label: str):
        self.label = label  # "entry", "L<n>", or "" for one LLVM starts after a terminator
        self.code: list[Ins] = []
        # where an exception raised here goes: the landing block of the innermost try statement
        # of its function around it, or "" (it leaves the function)
        self.handler = ""


class Loop:
    # the shape of one loop, for loop passes and structured backends; lowering ignores it
    def __init__(self, kind: str, head: str, body: str, step: str, brk: str):
        self.kind = kind  # "while" "range" "rrange" "seq"
        self.mode = ""  # seq: "" enumerate zip reversed items keys values
        self.head = head  # the block that tests whether to go on
        self.body = body  # the block where its body starts
        self.step = step  # continue's target
        self.exit = brk  # break's target, after the else block
        self.seqs: list[Val] = []  # what a seq loop steps through
        # a seq loop's test of each of seqs leads to a block (tests) where the item it takes is the
        # one at idx (a list's, a str's or a tuple's index: 0 <= idx < its length when it was tested)
        self.tests: list[str] = []
        self.idx: list[str] = []
        self.ctr = ""  # the slot of its counter or index
        self.stop = Val("", "")  # a range loop's stop, evaluated once


class Try:
    # the shape of one try statement, for structured backends; lowering needs only Blk.handler
    def __init__(self, body: str):
        self.body = body  # the block where its body starts
        self.landing = ""  # the landing block of its except clauses ("" without them)
        self.final = ""  # the landing block of its finally block ("" without one)
        self.orelse = ""  # the block where its else block starts ("" without one)
        self.exit = ""  # where the normal path goes on: the copy of its finally block starts there


class StopCatch:
    # The handler of the StopIteration that a loop's __next__ calls (or next(it, default)'s)
    # raise at the end of the items (Gen.stop_catch): the try's mark and the exception being
    # handled, taken before the first call, the slot its landing block stores the exception in,
    # that block's label, and its try's shape (whose body is the first call's block)
    def __init__(self, mark: Val, old: str, slot: str, landing: str):
        self.mark = mark
        self.old = old
        self.slot = slot
        self.landing = landing
        self.tr = Try("")


class IFn:
    # one compiled function: a function, a method, a module's code, a helper or a template's function
    def __init__(self, f: FnInfo):
        self.f = f  # f.ret is final once the IFn is complete
        self.ps: list[int] = []  # the indices of its parameters that are passed (a None-typed one is not)
        self.slots: list[Ins] = []  # entry-block storage ("slot" ops)
        self.blocks: list[Blk] = [Blk("entry")]
        self.loops: list[Loop] = []
        # message "Kind: text" -> the label of the block that raises it: one per function and
        # message, numbered at the first check of it, and placed after the function's code
        self.cold: dict[str, str] = {}
        # inside a try statement, a message's key is "<landing> <message>", and its cold block raises
        # the message to that landing block: the key -> the landing block
        self.coldh: dict[str, str] = {}
        self.tries: list[Try] = []
        self.pads = False  # whether it keeps landing pads (once the exception passes have run)
        # its effect summary (FX bits): every letter (but N) until Gen.effects computes it, once
        # the whole program is built
        self.fx: int = FXALL
        # the last number its builder gave (%tN, LN, %name.N), once it is complete: a pass that
        # adds values or blocks numbers them after it (the IR check checks that none is above it)
        self.n = 0
        self.fa: dict[str, bool] = {}  # the values that are addresses of an object's field or flag (Gen.fgep)
        # a generator function's (FnInfo.gen): a presplitcoroutine, whose gen.start op ends its entry
        # block. With exceptions on (Gen.eh): gpad, the landing block around its body (it finishes
        # the generator: PEP 479, close), gbase, the slot of the unwind actions' depth when it was
        # last resumed (its try statements' marks are relative to it), and gsaved, the slot of the
        # unwind actions it set aside while suspended (FnInfo.gwith)
        self.coro = False
        self.gpad = ""
        self.gbase = ""
        self.gsaved = ""
        self.gnone = False  # some way out of it returns no value (gen_none_end)
        # FnInfo.gtry: the slots of the exception being handled where it was last resumed (its
        # resumer's), and of its own where it suspended in an except clause or a finally block
        self.gouter = ""
        self.ghand = ""


class Lookup:
    # a dict.has or dict.getitem (op, at position x of block blk of its IFn) of key k in dict d,
    # given as their canonical values (Gen.canon): a getitem or a set of the same d and k after
    # it may reuse the entry it finds (Gen.dictfuse)
    def __init__(self, op: Ins, blk: int, x: int, d: str, k: str):
        self.op = op
        self.blk = blk
        self.x = x  # its position in the block
        self.d = d
        self.k = k
        self.e = 0  # the number of the entry's index (%tN), once an op reuses it


class Values:
    # which values of an IFn are equal (Gen.canon), for dictfuse: each value's canonical value
    def __init__(self, fn: IFn, pl: dict[str, list[int]]):
        self.fn = fn
        self.pl = pl  # the blocks that branch to each block (Gen.preds)
        # by the number of a value an operation defines: its block * stride + its position
        # there (-1 for the other numbers), stride being more than the ops of any block (a block of
        # 50 xors a line for 24,000 lines holds more than 2^20)
        self.at: list[int] = [-1] * (fn.n + 1)
        self.stride = 1
        for b in fn.blocks:
            if len(b.code) >= self.stride:
                self.stride = len(b.code) + 1
        self.cn: dict[str, str] = {}  # value -> its canonical value, once asked
        self.same: dict[str, str] = {}  # a computation's text, with canonical operands -> the first value of it
        self.text: dict[str, str] = {}  # and that value -> the text
        self.fieldtype: dict[str, str] = {}  # canonical field address -> declared class
        self.fieldindex: dict[str, int] = {}  # canonical field address -> member index
        self.depth = 0  # how many calls of Gen.canon are under way (at most CANON_DEPTH)
        for j in range(len(fn.blocks)):
            code = fn.blocks[j].code
            for x in range(len(code)):
                i = code[x]
                if (i.op == "select" or i.op == "scalar.bin" or i.op == "scalar.cast" or i.op == "scalar.cmp" or i.op == "rt" or i.op == "slot.pack" or i.op == "slot.unpack" or i.op == "num.cast" or i.op == "num.cmp" or i.op == "mach.load" or i.op == "mach.addr" or i.op == "mem.load" or i.op == "field.addr" or i.op == "int.ucmp" or i.op == "ptr.cmp") and len(i.r) == 1:
                    self.at[i.r[0]] = j * self.stride + x
                elif i.op == "union.payload" and len(i.r) == 2:
                    self.at[i.r[1]] = j * self.stride + x
                elif i.op == "tuple.load" or i.op == "tuple.store":
                    for r in i.r:
                        self.at[r] = j * self.stride + x


class Exit:
    # what leaving a block through break, continue or return first does (Gen.exits)
    def __init__(self, kind: str, v: str, handler: str):
        # "with": close the file v; "handler": restore v as the exception being handled (and unbind
        # name); "finally": run body, as where its try statement is: in nloops loops and nexcs
        # except clauses. It runs under handler, the landing block around the construct
        self.kind = kind
        self.v = v
        self.handler = handler
        self.name = ""
        self.body: list[Node] = []
        self.nloops = 0
        self.nexcs = 0
        self.entry = ""  # a finally block compiled once (Gen.try_): where it starts, ""  if each way out has a copy
        self.sel = ""  # the slot of the way out it goes on to, an index into conts
        self.conts: list[str] = []


class Frame:
    # the code generator's state for one function, saved while it compiles another
    def __init__(self, curfn: FnInfo, fn: IFn, blk: Blk):
        self.fn = fn
        self.blk = blk
        self.ltype: dict[str, str] = {}
        self.lreg: dict[str, str] = {}
        self.gdecl: dict[str, bool] = {}
        self.assigned: dict[str, bool] = {}
        self.compvars: dict[str, int] = {}
        self.loops: list[Loop] = []
        self.exits: list[Exit] = []
        self.wdepth: list[int] = []
        self.handler = ""
        self.excs: list[Val] = []
        self.shadows: list[list[str]] = []
        self.lcs: list[str] = []
        self.lct: list[str] = []
        self.lcsoft: list[bool] = []
        self.ret = ""
        self.retann = False
        self.nn: dict[str, bool] = {}
        self.selfname = ""
        self.uflags: dict[str, bool] = {}
        self.lflag: dict[str, str] = {}
        self.iflag: dict[str, str] = {}
        self.appends: dict[str, bool] = {}
        self.owned: dict[str, str] = {}
        self.cells: dict[str, str] = {}
        self.nlw: dict[str, bool] = {}
        self.nonevars: dict[str, int] = {}
        self.nonesites: dict[str, list[Node]] = {}
        self.narrowed: dict[str, str] = {}
        self.lkk: dict[str, str] = {}
        self.branch = 0
        self.modlevel = False
        self.lenient = False
        self.n = 0
        self.cur = ""
        self.term = False
        self.line = 0
        self.curfn = curfn


class ClassInfo:
    def __init__(self, name: str, node: Node):
        self.name = name
        self.node = node
        self.fields: list[str] = []
        self.fpos: dict[str, int] = {}  # field -> its index in fields (and in the struct)
        self.ftypes: dict[str, str] = {}
        self.fdefault: dict[str, Node] = {}
        self.slots: list[str] = []  # literal __slots__, including inherited slots
        self.slotlimit = False  # every ordinary base and this class omit an instance dict
        self.fglob: dict[str, str] = {}
        self.fflag: dict[str, int] = {}  # field -> index of its "is assigned" flag in the struct
        self.fsure: dict[str, bool] = {}  # the flagged fields that no read finds unassigned (hasattr tests them)
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
        self.exc = ""
        self.tag = 0  # ordinary inheritance: the object's concrete class; zero outside a hierarchy
        self.nflag = 0  # the "is assigned" flags at the end of its struct (its own fields')
        self.leak = False  # its __init__ lets self escape before it ends
        self.flowed = False  # fl_fields has decided its flags
        # a class template (an __init__ parameter without an annotation): its specializations,
        # named by the types its fields get (see specialize); a specialization: its template
        self.specs: dict[str, str] = {}
        self.nspec = 0  # (the names it has given: one each, also to those found to be one already made)
        self.origin = ""
        # a specialization of a generic class (Gen.tparams): the types its type variables are bound
        # to, by the call that made it (Gen.bind); a TypeVarTuple's is a tuple type of its types
        self.tvars: dict[str, str] = {}
        # a specialization of a class that specializes on literal arguments (Gen.literal_class):
        # its __init__'s parameters given literals, and its fields that hold constants, as the
        # literal nodes of their values (see Gen.const_of)
        self.lits: dict[str, Node] = {}
        self.fconst: dict[str, Node] = {}
