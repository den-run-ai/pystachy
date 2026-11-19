"""Typed IR records of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.specs import FXALL, VALUE_AT
from src.pystachy_compiler.symbols import FnInfo
from src.pystachy_compiler.syntax import Node


class Val:
    def __init__(self, v: str, t: str):
        self.v = v
        self.t = t
        self.infer_from = ""  # direct recursive call whose inferred return still defaults to None
        self.lit = False  # a numeric literal's own value, as gen_expr made it (dyn_box: its constant box)
        self.idslot = ""  # the box slot of the int or float variable it was read from (dyn_box: idbox)
        self.idheld = ""  # the box that slot held then, null where it held none yet (dyn_id_read)
        self.idgen = 0  # the stores into that slot that the compiler had emitted then (idstores)
        self.idcounter = ""  # local binding generation slot (possibly selected by a phi)
        self.idversion = ""  # that slot's generation at the read
        self.idexact = False  # private call-result slot is null or this exact numeric object
        self.idfrom = ""  # the box of the Any value that an int or float was read from (dyn_box)

    def identity(self, source: Val) -> Val:
        # A representation-only extraction keeps the binding that owns its number.
        # Arithmetic and conversions that change the Python value must not use this.
        self.idslot = source.idslot
        self.idheld = source.idheld
        self.idgen = source.idgen
        self.idcounter = source.idcounter
        self.idversion = source.idversion
        self.idfrom = source.idfrom
        self.idexact = source.idexact
        return self


# What an operand's value (Val.v) may be, by kind (operand_kind): a value an instruction of the
# function defines (%t<n>), a parameter (%a<n>, its numeric identity companion %aid<n>, or the
# identity result %idret), a slot's register (slot_register: %<name>.<n>), a symbol of the module
# (@<name>), a constant (an int, a decimal float, true, false, null or undef), or one of three
# constant expressions over a symbol or a float's bits (constant_expression). The set is closed:
# the IR check rejects any other spelling, so an operand holds no instruction text. The
# spellings are still LLVM's, which lowering prints as they are.
OPERAND_VALUE = 0
OPERAND_PARAM = 1
OPERAND_SLOT = 2
OPERAND_GLOBAL = 3
OPERAND_CONST = 4
OPERAND_EXPR = 5
OPERAND_KINDS: list[str] = ["value", "param", "slot", "global", "const", "expr"]


def digits(v: str, lo: int, hi: int) -> bool:
    # v[lo:hi] is one decimal digit or more
    if lo >= hi:
        return False
    for j in range(lo, hi):
        c = ord(v[j])
        if c < 48 or c > 57:
            return False
    return True


def symbol_end(v: str, lo: int) -> int:
    # where the symbol @<name> that starts at v[lo] ends, or -1: its name is letters, digits
    # and _ . $ -
    if lo >= len(v) or v[lo] != "@":
        return -1
    j = lo + 1
    while j < len(v):
        c = ord(v[j])
        if not ((48 <= c <= 57) or (65 <= c <= 90) or (97 <= c <= 122) or c == 95 or c == 46 or c == 36 or c == 45 or c >= 128):
            break
        j += 1
    return j if j > lo + 1 else -1


def integer_end(v: str, lo: int) -> int:
    # where the decimal integer that starts at v[lo] ends, or -1
    j = lo + 1 if lo < len(v) and v[lo] == "-" else lo
    k = j
    while k < len(v) and 48 <= ord(v[k]) <= 57:
        k += 1
    return k if k > j else -1


def constant_expression(v: str) -> bool:
    # ptrtoint (ptr @G to i64), ptrtoint (ptr getelementptr (i8, ptr @G, i64 N) to i64): a
    # constant's address, or an address inside it, as a container slot's bits; and
    # bitcast (i64 N to double): a float that has no decimal spelling, by its bits
    if v.startswith("bitcast (i64 "):
        j = integer_end(v, 13)
        return j > 0 and v[j:] == " to double)"
    if v.startswith("ptrtoint (ptr getelementptr (i8, ptr "):
        j = symbol_end(v, 37)
        if j < 0 or not v.startswith(", i64 ", j):
            return False
        j = integer_end(v, j + 6)
        return j > 0 and v[j:] == ") to i64)"
    if v.startswith("ptrtoint (ptr "):
        j = symbol_end(v, 14)
        return j > 0 and v[j:] == " to i64)"
    return False


def operand_kind(v: str) -> int:
    # the kind of an operand's value (OPERAND_KINDS), or -1 if it has none
    n = len(v)
    if n == 0:
        return -1
    c = ord(v[0])
    if c == 37:
        if n > 2 and v[1] == "t" and digits(v, 2, n):
            return OPERAND_VALUE
        if (n > 2 and v[1] == "a" and digits(v, 2, n)) or (v.startswith("%aid") and digits(v, 4, n)) or v == "%idret":
            return OPERAND_PARAM
        j = n
        while j > 0 and 48 <= ord(v[j - 1]) <= 57:
            j -= 1
        return OPERAND_SLOT if j < n and j >= 3 and v[j - 1] == "." else -1
    if c == 64:
        return OPERAND_GLOBAL if symbol_end(v, 0) == n else -1
    if v == "true" or v == "false" or v == "null" or v == "undef":
        return OPERAND_CONST
    j = integer_end(v, 0)
    if j == n:
        return OPERAND_CONST
    if j > 0 and v[j] == "." and j + 1 < n:
        # a decimal float: digits, a point, digits, and an exponent if it has one
        k = j + 1
        while k < n and 48 <= ord(v[k]) <= 57:
            k += 1
        if k == j + 1:
            return -1
        if k == n:
            return OPERAND_CONST
        if v[k] == "e" and k + 1 < n:
            k += 2 if v[k + 1] == "+" or v[k + 1] == "-" else 1
            return OPERAND_CONST if digits(v, k, n) else -1
        return -1
    return OPERAND_EXPR if constant_expression(v) else -1


class Data:
    # Immutable module data: string bytes, callable/exception references, constant tuple slots
    # (whose type its text is), or pointer-free scalar slots copied into fresh lists.
    # LLVM's concrete layout and declaration syntax belong to lower_module.
    def __init__(self, kind: str, name: str):
        self.kind = kind
        self.name = name
        self.text = ""
        self.refs: list[str] = []
        self.items: list[Val] = []  # typed constant slots; listdata permits only int/float/bool


NONUMS: list[int] = []
NOVALS: list[Val] = []
NOLABELS: list[str] = []
# Value n's name, %t<n>, and the numbers of an op that defines value n alone, [n]: each made at
# its first use and shared from then on. No code changes an op's numbers in place (a pass gives
# an op a new list), and a str never changes, so sharing them changes nothing the IR says; but
# an op and the values that name it no longer make a list and strs of their own. The program's
# IR stays until it is lowered, and every collection marks all of it: with the collector
# running every 5,000 allocations (gc-self), those objects made its cost grow with the square
# of the compiler's size (#1181)
TMPNAMES: list[str] = []
ONENUMS: list[list[int]] = []


def tmpname(n: int) -> str:
    if n < 0:
        return f"%t{n}"
    while len(TMPNAMES) <= n:
        TMPNAMES.append(f"%t{len(TMPNAMES)}")
    return TMPNAMES[n]


def one_num(n: int) -> list[int]:
    if n < 0:
        return [n]
    while len(ONENUMS) <= n:
        ONENUMS.append([len(ONENUMS)])
    return ONENUMS[n]


def one_nums_intact() -> bool:
    # (what Gen.program checks once the program is lowered: no op changed a shared list)
    for n in range(len(ONENUMS)):
        if len(ONENUMS[n]) != 1 or ONENUMS[n][0] != n:
            return False
    return True


class Ins:
    # one instruction: op decides which fields mean something
    def __init__(self, op: str, t: str, s: str):
        self.line = 0  # encoded source position; zero for synthesized operations
        self.op = op  # a key of IROPS
        self.t = t  # its result type ("" if it defines no value; an rt op's as RUNTIME spells it), a slot's type
        # slot.pack/unpack keep the native type in the operand/result and use %slot for
        # the opaque eight-byte container payload. Only LLVM lowering chooses its bitcast.
        # union.tag reads a nonoptional union's tag; union.payload reads its member's
        # opaque slot (s: member type, r: address then payload). Narrowing proves those reads safe.
        # union.raw copies those bits without claiming a member (s: empty); its tag travels
        # with the bits when unionslots splits storage or rebuilds a box.
        # dyn.type reads a dynamic value's DynType pointer and dyn.payload its slot (s: the type
        # a test proved it holds, r: address then payload); the box never changes (dynamic.py).
        # dyn.raw reads opaque identity bits with no member claim (s: empty), for
        # direct integer equality only; r is again the address then payload.
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
        # int immediate: a slot's kind (1: an "is assigned" flag, 2: a stack tuple; slot_register),
        # a hole (Gen.holes, from 1), the layout index or a finite machine-address flag
        self.k = 0
        # an rt op's descriptor of the static type it works on (for its # parameter): RUNTIME's U?
        # is U when it holds a class (O<id>), or an exception (E) in a program that makes objects of
        # exception classes; a call's "inline" where listguard's copy of a loop marks it to be
        # inlined (alwaysinline: gen_listguard)
        self.x = ""
        self.r: list[int] = NONUMS  # the numbers of the values it defines, given when it was built
        self.a: list[Val] = NOVALS  # operands, in evaluation order (an rt op's typed as RUNTIME spells its parameters)
        self.b: list[str] = NOLABELS  # labels: the successors of br, cbr and check; a phi's predecessors


def slot_register(i: Ins) -> str:
    # the register that lowering allocates for a slot op, which every analysis of slots must
    # name the same way: a local's "is assigned" flag and its numeric identity companions share
    # its number, so a slot's number alone is no name (a stack tuple's register is its value)
    if i.k == 1:
        return f"%{i.s}.def.{i.r[0]}"
    if i.k == 2:
        return f"%stk.{i.r[0]}"
    return f"%{i.s or 'h'}.{i.r[0]}"


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
        self.inc = Val("", "")  # a range loop's step, evaluated once
        self.nonnegative = False  # range: a nonnegative constant start and positive constant step


class Try:
    # the shape of one try statement, for structured backends; lowering needs only Blk.handler
    def __init__(self, body: str):
        self.body = body  # the block where its body starts
        self.landing = ""  # the landing block of its except clauses ("" without them)
        self.final = ""  # the landing block of its finally block ("" without one)
        self.orelse = ""  # the block where its else block starts ("" without one)
        self.exit = ""  # where the normal path goes on: the copy of its finally block starts there


class IFn:
    # one compiled function: a function, a method, a module's code, a helper or a template's function
    def __init__(self, f: FnInfo):
        self.f = f  # f.ret is final once the IFn is complete
        # Syntax-only names bound outside except targets, built lazily by bind_as.
        # Frame retains this IFn during nested compilation; a retry gets a fresh one.
        # dry() may retain the index: it depends on no inferred or speculative state.
        self.otherbinds: dict[str, bool] | None = None
        self.numeric_only = False  # function_body proved local numeric identity unobservable
        self.scalar_reads = False  # scoped numeric arithmetic/comparison; no operand identity escapes
        # Lazy numeric field locals (Gen.lazy_fields): local -> the parameter whose field it reads,
        # that field, its bit in lazymasks, and its "shares the field's object" flag slot
        self.lazyobj: dict[str, str] = {}
        self.lazyfield: dict[str, str] = {}
        self.lazybit: dict[str, int] = {}
        self.lazyflag: dict[str, str] = {}
        self.lazyreads: list[Node] = []  # the x = o.f statements that share without a box
        self.lazywbs: list[Node] = []  # the o.f = x statements that write such a local back
        self.lazylines: dict[int, list[Node]] = {}  # statements by line, and the lazy locals
        self.lazymasks: dict[int, list[int]] = {}  # live where each starts (analysis.lazy_block)
        self.lazyoff = 0  # inside a while loop whose test may run code: no sharing starts
        self.lazywb = ""  # the local whose write-back setfield is compiling
        self.idmove = False  # a lone assignment stores a call's result (dyn_id_store)
        self.idpass = False  # a copy or argument moves a local (Gen.id_move)
        self.movebit: dict[str, int] = {}  # locals a read may move: their bits in lazymasks
        self.idstmt: Node | None = None  # the statement being compiled, where movebit has any
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
        # Native recursion counts the activations of source functions that recursion can
        # repeat (Gen.recursionscope), never dispatch adapters: counted is whether this is
        # a source function until that pass decides, then whether it counts. rdepth is the
        # entry op's value, the depth every local landing restores (landed: some landing
        # does); a generator refreshes gdepth on each resume, since it may have another caller.
        self.counted = False
        self.rdepth = ""
        self.landed = False
        self.gdepth = ""
        self.resumes = False  # whether it resumes or drops a generator (Gen.recursionscope looks for the sites)
        self.setslimit = False  # whether it calls sys.setrecursionlimit, which reads the depth (Gen.recursionscope)
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
                how = VALUE_AT.get(i.op, 0)
                if how == 1 and len(i.r) == 1:
                    self.at[i.r[0]] = j * self.stride + x
                elif how == 2 and len(i.r) == 2:
                    self.at[i.r[1]] = j * self.stride + x
                elif how == 3:
                    for r in i.r:
                        self.at[r] = j * self.stride + x
