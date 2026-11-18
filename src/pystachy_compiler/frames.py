"""Code-generator state records of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.ir import Blk, IFn, Loop, Try, Val
from src.pystachy_compiler.symbols import FnInfo
from src.pystachy_compiler.syntax import Node


class IterArg:
    # A consumer's next argument: evaluate it after its iterator is constructed, before traversal.
    # Capture keeps the node's children as original values instead of storing them in a tuple,
    # whose numeric slots do not retain the identity of a consumer's default argument.
    # With split, a label, there is none: the code after the iterator is constructed goes on at
    # split, and the traversal waits at trav for a branch to it (the consumer's turn to iterate).
    def __init__(self, node: Node):
        self.node = node
        self.value = Val("", "")
        self.capture = False
        self.values: list[Val] = []
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
        self.identity = ""  # min/max numeric selected item's box in a dynamic program graph
        self.comp = ""  # a float sum's compensation, as runtime.c's fsum keeps it (Neumaier's)
        self.first = ""  # no item yet: min and max, and a float sum from an int start
        self.collect = False  # min() or max() of items runtime.c compares (pys_list_minmax)
        # a sum of a union's numbers (Gen.sum_union_item): acc the int sum, facc the float sum,
        # isf whether a float came (CPython's float phase, which comp compensates)
        self.facc = ""
        self.isf = ""
        self.phase = ""  # dynamic sum: in-range int, compensated float, or generic addition


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
        self.dynints: dict[str, bool] = {}
        self.selfname = ""
        self.uflags: dict[str, bool] = {}
        self.lflag: dict[str, str] = {}
        self.iflag: dict[str, str] = {}
        self.appends: dict[str, bool] = {}
        self.owned: dict[str, str] = {}
        self.idbox: dict[str, str] = {}
        self.idstores: dict[str, int] = {}
        self.cells: dict[str, str] = {}
        self.nlw: dict[str, bool] = {}
        self.nonevars: dict[str, int] = {}
        self.nonesites: dict[str, list[Node]] = {}
        self.nonepending: dict[str, bool] = {}
        self.narrowed: dict[str, str] = {}
        self.lkk: dict[str, str] = {}
        self.branch = 0
        self.modlevel = False
        self.lenient = False
        # the state of the operation that the function was compiling when it compiled another,
        # which that function must neither see nor change (#822): dry()'s depth, a return's value
        # while leave() compiles finally blocks, the comparison with None and the lookup key being
        # compiled, the copies unrolled loops make and the expression statement
        self.drying = 0
        self.carried = Val("", "")
        self.nonecmp = False
        self.fieldcmp = False
        self.cmpnode = Node("", "", 0)
        self.stkkey = Node("", "", 0)
        self.reflcopies = 1
        self.stmtexpr: Node | None = None
        self.dmemo: list[Node] = []
        self.dmemot: list[str] = []
        self.n = 0
        self.cur = ""
        self.term = False
        self.line = 0
        self.curfn = curfn
