"""Compile a typed-IR module's text to a WebAssembly module, without LLVM (wasm/README.md).

    tir_wasm.py MODULE.tir OUT.wasm

MODULE.tir is a module as tools/typed_ir_text.py prints a typed-after snapshot (`complete`). The
module written imports the shared runtime, runtime.wasm (wasm/build.sh runtime-wasm): its memory
(env.memory), the base of the block that the loader allocates for this module's data (env.data,
an i32 global), the runtime functions it calls (rt.SYMBOL) and the recursion state's address
(rt.pys_recursion_state). It exports its module code as `init`; wasm/run.mjs --runtime loads both.
Its custom section `pystachy.data` holds the data block's size, which the loader reads first.

Typed-IR values use WebAssembly locals of the corresponding machine type (i64, f64, or i32
for i1, i8, i32 and pointers). Recursion-counted functions reuse locals when SSA values of
the same type have disjoint lifetimes. Addressable slots and emitter state have dedicated locals.
A function's blocks are laid out in forward order inside nested blocks. Functions with a
backedge also have a dispatch loop: a backward branch sets the next block's index and
continues the loop, whose br_table dispatches it. A phi's values are assigned on each edge, all read first.

It lowers scalar code, runtime calls and exception handlers (wasm/README.md). Around each call that
may collect and then return, a frame on the reactor's stack keeps the live values that may be
references, where the collector's stack scan finds them (WASM_GUEST_ROOTS=0: none, and no collection).
Generators can suspend in code that requires no cleanup at a yield.
Dynamic dispatch still requires LLVM. For an unsupported operation it exits with status 3 after one
line `tir_wasm: refused: WHAT` on stderr, and wasm/build.sh then compiles the program through
LLVM. Run it as PYTHONPATH=. python3 wasm/tir_wasm.py, or compiled: PYSTACHY_PATH=. ./pystachy
build wasm/tir_wasm.py, from the repository root (it reads the compiler's RUNTIME table).
"""
import os
import struct
import sys

from src.pystachy_compiler.diagnostics import LINES
from src.pystachy_compiler.machine_ir import WORD_READS
from src.pystachy_compiler.specs import CONTAINER_HEADERS, GENDONE, GENNAME, GENNEW, GENRET, GENSTATE, GENVAL, OP_TEMPS, RTSYM, RUNTIME
from src.pystachy_compiler.utils import atomic_dict, atomic_list, generator_slots, is_tuple, lt, rtll, rtsig, rtsym, tslots
from wasm.wasi_abi import LIBC_WRAPPERS

I32 = 0x7F
I64 = 0x7E
F64 = 0x7C
VOID = 0x40

# The reactor handles the other recursion operations. In particular, a failed
# resume must finish the generator before raising on depth or stack exhaustion.
INLINE_RECURSION = ("recursion.depth", "recursion.restore", "recursion.enter")
# runtime entries the emitter writes as instructions: no import, no call, no collection
INLINE_RT = ("fabs", "memmove")
# icmp predicates on i32 operands as Wasm opcodes
I32_CMP = {"eq": 0x46, "ne": 0x47, "slt": 0x48, "ult": 0x49, "sgt": 0x4A, "ugt": 0x4B,
           "sle": 0x4C, "ule": 0x4D, "sge": 0x4E, "uge": 0x4F}
# typed-IR value types that never hold a reference (guest roots leave them out)
SCALARS = ("int", "bool", "float")
# Runtime entries that may collect only on their way to raising, never and then return: a function
# whose other calls cannot either needs no guest roots (rooted_functions). wasm/check_no_collect.py,
# which wasm/build.sh runtime-wasm runs, proves each against runtime.wasm's code.
RETURNS_UNCOLLECTED = (
    "ceil", "exc.in", "f2i", "fdiv", "ffloordiv", "floor", "floordiv", "fmod", "fpow", "idiv", "mod", "ord", "pow",
    "powmod", "round", "round_int", "shl", "shr",
    "dict.key", "dict.next", "dict.val", "list.clear", "list.del", "list.get", "list.pop", "list.reverse",
    "list.set", "range.has", "range.len", "set.key", "set.next", "vtuple.get",
    "str.contains", "str.count", "str.endswith", "str.find", "str.index", "str.rfind", "str.rindex",
    "str.startswith", "text.len", "text.ord_at",
    "m.acos", "m.acosh", "m.asin", "m.asinh", "m.atan", "m.atan2", "m.atanh", "m.cbrt", "m.copysign", "m.cos",
    "m.cosh", "m.degrees", "m.erf", "m.erfc", "m.exp", "m.exp2", "m.expm1", "m.fabs", "m.fmod", "m.gamma",
    "m.gcd", "m.hypot", "m.isclose", "m.isfinite", "m.isinf", "m.isnan", "m.isqrt", "m.ldexp", "m.lgamma",
    "m.log", "m.log10", "m.log1p", "m.log2", "m.pow", "m.radians", "m.remainder", "m.sin", "m.sinh", "m.sqrt",
    "m.tan", "m.tanh", "m.trunc",
)


# LLVM's ordered fcmp predicates and une, as WebAssembly's f64 comparisons
FCMP_OPS: dict[str, int] = {"oeq": 0x61, "une": 0x62, "olt": 0x63, "ogt": 0x64, "ole": 0x65, "oge": 0x66}


def standard_eh() -> bool:
    encoding = os.getenv("WASM_EH", "legacy")
    if encoding not in ("legacy", "standard"):
        sys.stderr.write("WASM_EH must be legacy or standard\n")
        sys.exit(2)
    return encoding == "standard"


class Refused(Exception):
    def __init__(self, what: str):
        super().__init__(what)
        self.what = what


# ---------- the module text ----------

class Operand:
    def __init__(self, t: str, v: str):
        self.t = t
        self.v = v


class Inst:
    def __init__(self, op: str):
        self.op = op
        self.res: list[str] = []
        self.operator = ""
        self.fields: dict[str, str] = {}
        self.args: list[Operand] = []
        self.targets: list[str] = []
        self.t = ""
        self.keep: list[str] = []   # the values a frame keeps during its call (Emitter.spill_sets)
        self.line = 0  # its source line, as diagnostics.LINES numbers lines (0: unknown)

    def is_invoke(self) -> bool:
        return len(self.targets) != 0 and self.op in ("rt", "call", "icall", "init", "gen.resume")


class Block:
    def __init__(self, label: str):
        self.label = label
        self.code: list[Inst] = []


class Func:
    def __init__(self, name: str):
        self.name = name
        self.ptypes: list[str] = []
        self.ret = ""
        self.attrs: dict[str, str] = {}
        self.slots: dict[str, str] = {}
        self.coroutine = False
        self.generator_exceptions: set[str] = set()
        self.tuple_offsets: dict[str, int] = {}
        self.frame_bytes = 0
        self.blocks: list[Block] = []
        self.cold: dict[str, str] = {}
        self.line = 0  # its def's line, which its prologue's calls report
        self.pyname = ""  # its Python name, which a traceback shows ("": none of its frames)

    def block_indices(self) -> dict[str, int]:
        labels: dict[str, int] = {}
        for idx in range(len(self.blocks)):
            label = self.blocks[idx].label
            if label in labels:
                raise Refused(f"duplicate block {label} in {self.name}")
            labels[label] = idx
        # Both suspension analysis and recursive local packing follow these edges.
        for block in self.blocks:
            for inst in block.code:
                if inst.op == "phi" and len(inst.args) != len(inst.targets):
                    raise Refused(f"phi in {block.label} with unequal input and predecessor counts")
                for target in inst.targets:
                    if target not in labels:
                        if inst.op == "phi":
                            raise Refused(f"phi in {block.label} from unknown block {target}")
                        raise Refused(f"branch to unknown block {target}")
                if inst.op == "check":
                    key = inst.fields.get("key", "") or inst.fields.get("message", "")
                    if key not in self.cold:
                        raise Refused(f"check without a cold block ({key})")
                    if self.cold[key] not in labels:
                        raise Refused(f"branch to unknown block {self.cold[key]}")
        return labels

    def add_slot(self, name: str, t: str, kind: int) -> None:
        if kind == 2:
            if not is_tuple(t) or not t.endswith("]"):
                raise Refused(f"frame slot {name} requires a fixed tuple, got {t}")
            self.tuple_offsets[name] = self.frame_bytes
            self.frame_bytes += 8 * max(1, tslots(t))
        else:
            self.slots[name] = t


def live_after_blocks(fn: Func, labels: dict[str, int], values: dict[str, int]) -> list[set[int]]:
    count = len(fn.blocks)
    uses: list[set[int]] = [set() for _ in range(count)]
    defs: list[set[int]] = [set() for _ in range(count)]
    successors: list[set[int]] = [set() for _ in range(count)]
    edge_uses: list[set[int]] = [set() for _ in range(count)]
    for b in range(count):
        for i in fn.blocks[b].code:
            if i.op == "phi":
                # goto reads all phi inputs before assigning any destination.
                for j in range(len(i.args)):
                    if i.args[j].v in values:
                        edge_uses[labels[i.targets[j]]].add(values[i.args[j].v])
            else:
                for arg in i.args:
                    if arg.v in values and values[arg.v] not in defs[b]:
                        uses[b].add(values[arg.v])
                for label in i.targets:
                    successors[b].add(labels[label])
                if i.op == "check":
                    key = i.fields.get("key", "") or i.fields.get("message", "")
                    successors[b].add(labels[fn.cold[key]])
            for name in i.res:
                if name in values:
                    defs[b].add(values[name])

    live_in = [u.copy() for u in uses]
    live_out = [u.copy() for u in edge_uses]
    changed = True
    while changed:
        changed = False
        for b in range(count - 1, -1, -1):
            for succ in successors[b]:
                live_out[b].update(live_in[succ])
            before = uses[b] | (live_out[b] - defs[b])
            if before != live_in[b]:
                live_in[b] = before
                changed = True

    return live_out


def register_colors(fn: Func, labels: dict[str, int], locals_: dict[str, int], types: list[int]) -> tuple[list[int], list[int]]:
    # Non-SSA locals (arguments, addressable slots and emitter state) own a register throughout
    # the call. SSA values of the same type may share a register if their lifetimes do not meet.
    values = {name: locals_[name] for name in locals_ if name.startswith("%t") and name[2:].isdigit() and name not in fn.slots}
    count = len(fn.blocks)
    live_out = live_after_blocks(fn, labels, values)
    edges: dict[int, set[int]] = {idx: set() for idx in values.values()}
    for b in range(count):
        live = live_out[b].copy()
        phis: set[int] = set()
        for j in range(len(fn.blocks[b].code) - 1, -1, -1):
            inst = fn.blocks[b].code[j]
            written = {values[name] for name in inst.res if name in values}
            if inst.op == "phi":
                phis.update(written)
                continue
            read = {values[arg.v] for arg in inst.args if arg.v in values}
            # An operation can write a result before its final operand read (e.g. vtuple.make).
            interfere(edges, written, live | read | written, types)
            live.difference_update(written)
            live.update(read)
        interfere(edges, phis, live | phis, types)

    slots = [-1] * len(types)
    packed: list[int] = []
    for k in range(len(types)):
        if k not in edges:
            slots[k] = len(packed)
            packed.append(types[k])
    # Color the most constrained values first. Keep the original allocation order on ties.
    order = sorted([(-len(edges[k]), k) for k in edges])
    colors: dict[int, list[int]] = {I32: [], I64: [], F64: []}
    for pair in order:
        k = pair[1]
        wt = types[k]
        taken = {slots[other] for other in edges[k]}
        for slot in colors[wt]:
            if slot not in taken:
                slots[k] = slot
                break
        if slots[k] < 0:
            slots[k] = len(packed)
            colors[wt].append(len(packed))
            packed.append(wt)
    return (slots, packed)


def interfere(edges: dict[int, set[int]], written: set[int], live: set[int], types: list[int]) -> None:
    for dst in written:
        for src in live:
            if dst != src and types[dst] == types[src]:
                edges[dst].add(src)
                edges[src].add(dst)


class ClassDecl:
    def __init__(self, name: str):
        self.name = name
        self.ftypes: list[str] = []
        self.legacy_header = False
        self.nflag = 0
        self.nbox = 0


class Const:
    def __init__(self, name: str, kind: str):
        self.name = name
        self.kind = kind
        self.text = ""
        self.items: list[Operand] = []
        self.refs: list[str] = []


class Module:
    def __init__(self):
        self.attrs: dict[str, str] = {}
        self.consts: list[Const] = []
        self.globals: dict[str, str] = {}
        self.order: list[str] = []
        self.roots: list[str] = []
        self.classes: dict[str, ClassDecl] = {}
        self.objects: list[str] = []
        self.compared: dict[str, bool] = {}
        self.hashed: dict[str, bool] = {}
        self.holes: dict[int, str] = {}
        self.keykinds: dict[str, str] = {}
        self.builtkinds: dict[str, str] = {}
        self.funcs: list[Func] = []
        self.plain_generators: dict[str, int] = {}
        self.files: list[str] = []  # the source files that a line's index names (lines section)

    def set_object_tables(self, objects: dict[str, int], compared: dict[str, bool], hashed: dict[str, bool]) -> None:
        # Descriptors hold the numeric ID, independent of declaration or attribute order.
        names = [""] * len(objects)
        for cls in objects:
            idx = objects[cls]
            if cls == "" or cls not in self.classes:
                raise Refused(f"unknown object dispatch class {cls}")
            if idx < 0 or idx >= len(names) or names[idx] != "":
                raise Refused("object dispatch IDs must be distinct and dense from zero")
            names[idx] = cls
        for cls in list(compared) + list(hashed):
            if cls not in objects:
                raise Refused(f"no object dispatch ID for {cls}")
        self.objects = names
        self.compared = compared
        self.hashed = hashed


def unquote(text: str, at: int) -> tuple[str, int]:
    # a JSON string at `at` (its opening quote): (its value, the position after it)
    out: list[str] = []
    j = at + 1
    while text[j] != '"':
        c = text[j]
        if c == "\\":
            e = text[j + 1]
            j += 2
            if e == "n":
                out.append("\n")
            elif e == "t":
                out.append("\t")
            elif e == "r":
                out.append("\r")
            elif e == "b":
                out.append("\b")
            elif e == "f":
                out.append("\f")
            elif e == "u":
                code = int(text[j:j + 4], 16)
                j += 4
                if 0xD800 <= code < 0xDC00 and text.startswith("\\u", j):
                    low = int(text[j + 2:j + 6], 16)
                    code = 0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00)
                    j += 6
                out.append(chr(code))
            elif e == '"' or e == "\\" or e == "/":
                out.append(e)
            else:
                raise Refused("invalid escape in quoted atom")
        else:
            out.append(c)
            j += 1
    return "".join(out), j + 1


def atom(text: str, at: int, stops: str) -> tuple[str, int]:
    # (the atom at `at`, the position after it), as tools/typed_ir_text.py's read_atom reads it
    if at < len(text) and text[at] == '"':
        return unquote(text, at)
    depth = 0
    end = at
    while end < len(text):
        c = text[end]
        if c == " " or c == '"' or c == "(" or c == ")" or c in stops:
            break
        if c == "[":
            depth += 1
        elif c == "]":
            if depth == 0:
                break
            depth -= 1
        elif c == "," and depth == 0:
            break
        end += 1
    return text[at:end], end


def operands(text: str, at: int) -> tuple[list[Operand], int]:
    # "(T V, T V)" from its "(" at `at`
    out: list[Operand] = []
    at += 1
    while True:
        t, at = atom(text, at, "")
        v, at = atom(text, at + 1, "")
        out.append(Operand(t, v))
        if text[at] == ")":
            return out, at + 1
        at += 2


def fields(text: str, at: int, end: int, const: Const | None = None) -> dict[str, str]:
    # NAME=VALUE ... (and bare flags, as NAME="1") between at and end
    out: dict[str, str] = {}
    while at < end:
        if text[at] == " ":
            at += 1
            continue
        k = at
        while k < end and text[k] != "=" and text[k] != " ":
            k += 1
        name = text[at:k]
        if name in ("objects", "compared", "hashed") and name in out:
            raise Refused(f"duplicate module attribute {name}")
        if k < end and text[k] == "=":
            if name == "items" and const is not None:
                const.items, at = operands(text, k + 1)
            elif text[k + 1] == "[":
                close = k + 1
                depth = 0
                while True:
                    if text[close] == '"':
                        _, close = unquote(text, close)
                        continue
                    if text[close] == "[":
                        depth += 1
                    elif text[close] == "]":
                        depth -= 1
                        if depth == 0:
                            break
                    close += 1
                out[name] = text[k + 1:close + 1]
                at = close + 1
            else:
                value, at = atom(text, k + 1, "")
                out[name] = value
        else:
            out[name] = "1"
            at = k
    return out


def instruction(text: str) -> Inst:
    at = 0
    res: list[str] = []
    eq = text.find(" = ")
    if text.startswith("%") or text.startswith("~"):
        for name in text[:eq].split(" "):
            res.append(name[1:] if name.startswith("~") else name)
        at = eq + 3
    k = at
    while k < len(text) and (text[k].isalpha() or text[k] == "."):
        k += 1
    ins = Inst(text[at:k])
    ins.res = res
    at = k
    # an operator, bare, then NAME=VALUE fields
    while at < len(text) and text[at] == " " and not text.startswith(" (", at) and not text.startswith(" -> ", at) \
            and not text.startswith(" : ", at) and not text.startswith(" loc(", at):
        at += 1
        j = at
        while j < len(text) and (text[j].isalpha() or text[j] == "_"):
            j += 1
        if j > at and j < len(text) and text[j] == "=":
            name = text[at:j]
            value, at = atom(text, j + 1, "")
            ins.fields[name] = value
        else:
            ins.operator, at = atom(text, at, "")
    if at < len(text) and text[at] == "(":
        ins.args, at = operands(text, at)
    elif text.startswith(" (", at):
        ins.args, at = operands(text, at + 1)
    if text.startswith(" -> ", at):
        at += 4
        while True:
            label, at = atom(text, at, "")
            ins.targets.append(label)
            if not text.startswith(", ", at):
                break
            at += 2
    if text.startswith(" : ", at):
        ins.t, at = atom(text, at + 3, "")
    if text.startswith(" loc(", at):
        at = len(text)
    if at != len(text):
        raise Refused(f"unexpected text in {text!r}")
    return ins


def parse(text: str) -> Module:
    m = Module()
    fn = Func("")
    block = Block("")
    in_module = False
    in_function = False
    for raw in text.split("\n"):
        line = raw.strip()
        if line == "" or line.startswith(";"):
            continue
        if not in_module and not in_function and line.startswith("module ") and line.endswith("{"):
            m.attrs = fields(line, len("module "), len(line) - 1)
            in_module = True
        elif in_module and line == "}":
            in_module = False
        elif in_module:
            declaration(m, line)
        elif line.startswith("function ") and line.endswith("{"):
            fn = header(line)
            m.funcs.append(fn)
            in_function = True
        elif in_function and line == "}":
            in_function = False
        elif in_function and line.startswith("cold "):
            key, at = atom(line, 5, "")
            label, at = atom(line, at + 4, "")
            fn.cold[key] = label
        elif in_function and line.startswith("loop "):
            continue
        elif in_function and not raw.startswith("  "):
            label, at = atom(line, 0, ":")
            if line.startswith(": handler=", at):
                if "exceptions" not in m.attrs:
                    raise Refused(f"block {label} has a handler without module exceptions")
                # The region label may outlive an optimized-away landing. Finalized
                # calls carry their executable unwind edges in their own target lists.
                start = at + len(": handler=")
                try:
                    handler, end = atom(line, start, "")
                except (IndexError, ValueError):
                    raise Refused(f"invalid handler on block {label}") from None
                if not handler or end != len(line) or (line[start] != '"' and handler.count("[") != handler.count("]")):
                    raise Refused(f"invalid handler on block {label}")
            elif line[at:] != ":":
                raise Refused(f"unexpected text after block label {label}")
            block = Block(label)
            fn.blocks.append(block)
        elif in_function:
            ins = instruction(line)
            if ins.op == "slot":
                if len(fn.blocks) > 0:
                    raise Refused("a slot after the entry")
                fn.add_slot(ins.res[0], ins.t, int(ins.fields.get("kind", "0")))
            else:
                block.code.append(ins)
        else:
            raise Refused(f"unexpected line {line!r}")
    if "plain" in m.attrs:
        m.plain_generators = object_table(m.attrs["plain"], "plain")
    if "objects" in m.attrs or "compared" in m.attrs or "hashed" in m.attrs:
        objects = object_table(m.attrs.get("objects", "[]"), "objects")
        compared = {c: True for c in object_table(m.attrs.get("compared", "[]"), "compared")}
        hashed = {c: True for c in object_table(m.attrs.get("hashed", "[]"), "hashed")}
        m.set_object_tables(objects, compared, hashed)
    return m


def object_table(text: str, key: str) -> dict[str, int]:
    # objects=[Name:ID ...], compared=[Name ...] and hashed=[Name ...].
    # The IR printer quotes class names containing spaces or punctuation.
    if not text.startswith("[") or not text.endswith("]"):
        raise Refused(f"invalid object dispatch table {key}")
    table: dict[str, int] = {}
    at = 1
    while at < len(text) - 1:
        name, at = atom(text, at, ":" if key == "objects" else "")
        if not name or name in table:
            raise Refused(f"empty or duplicate class name in {key}")
        idx = len(table)
        if key == "objects":
            if text[at] != ":":
                raise Refused(f"missing object dispatch ID for {name}")
            start = at + 1
            at = start
            while at < len(text) and "0" <= text[at] <= "9":
                at += 1
            digits = text[start:at]
            # A dense ID is smaller than even the text encoding the table.
            if digits == "" or len(digits) > len(str(len(text))) or (digits[0] == "0" and len(digits) > 1):
                raise Refused(f"invalid object dispatch ID for {name}")
            idx = int(digits)
        table[name] = idx
        if at != len(text) - 1:
            if text[at] != " " or at + 1 >= len(text) - 1:
                raise Refused(f"invalid separator in {key}")
            at += 1
    return table


def header(line: str) -> Func:
    at = len("function ")
    name, at = atom(line, at, "")
    fn = Func(name)
    at += 1
    while line[at] != ")":
        if line.startswith(", ", at):
            at += 2
        pname, at = atom(line, at, ":")
        t, at = atom(line, at + 2, "")
        fn.ptypes.append(t)
    fn.ret, at = atom(line, at + 5, "")
    if line.startswith(" coroutine", at):
        fn.coroutine = True
        at += len(" coroutine")
    fn.attrs = fields(line, at, len(line) - 1)
    return fn


def items_of(text: str) -> list[str]:
    # [A B C] as a list
    inner = text[1:len(text) - 1].strip()
    return [] if inner == "" else inner.split(" ")


def declaration(m: Module, line: str) -> None:
    sp = line.find(" ")
    keyword = line[:sp] if sp > 0 else line
    name, at = atom(line, sp + 1, "")
    if keyword == "const":
        c = Const(name, "")
        f = fields(line, at, len(line), c)
        c.kind = f.get("kind", "")
        c.text = f.get("text", "")
        if "refs" in f:
            c.refs = items_of(f["refs"])
        m.consts.append(c)
    elif keyword == "global":
        m.globals[name] = fields(line, at, len(line))["type"]
        m.order.append(name)
    elif keyword == "class":
        f = fields(line, at, len(line))
        cd = ClassDecl(name)
        if "fields" in f:
            for field, typ in typed_items(f["fields"]):
                if field in (" list.0", " dict.0") and typ == "str":
                    cd.legacy_header = True
                cd.ftypes.append(typ)
        cd.nflag = len(items_of(f["flags"])) if "flags" in f else 0
        cd.nbox = len(items_of(f["boxes"])) if "boxes" in f else 0
        m.classes[name] = cd
    elif keyword == "hole":
        f = fields(line, at, len(line))
        m.holes[int(name)] = f.get("type", "")
    elif keyword == "keykind":
        f = fields(line, at, len(line))
        m.keykinds[name] = f.get("kind", "")
        m.builtkinds[name] = f.get("built", "")
    elif keyword == "root":
        if not name or at != len(line):
            raise Refused("invalid global root declaration")
        m.roots.append(name)
    elif keyword == "runtime":
        return
    else:
        raise Refused(f"module declaration {keyword}")


def typed_items(text: str) -> list[tuple[str, str]]:
    # fields=[name:type " hidden":type ...] in layout order
    out: list[tuple[str, str]] = []
    at = 1
    while at < len(text) - 1:
        if text[at] == " ":
            at += 1
            continue
        field, at = atom(text, at, ":")
        t, at = atom(text, at + 1, "")
        out.append((field, t))
    return out


# ---------- WebAssembly encoding ----------

def uleb(out: bytearray, n: int) -> None:
    while True:
        b = n & 0x7F
        n = n >> 7
        if n == 0:
            out.append(b)
            return
        out.append(b | 0x80)


def sleb(out: bytearray, n: int) -> None:
    while True:
        b = n & 0x7F
        n = n >> 7
        if (n == 0 and b & 0x40 == 0) or (n == -1 and b & 0x40 != 0):
            out.append(b)
            return
        out.append(b | 0x80)


def name_bytes(out: bytearray, s: str) -> None:
    b = s.encode("utf-8")
    uleb(out, len(b))
    out.extend(b)


def word(out: bytearray, v: int) -> None:
    # a little-endian 32-bit word
    for k in range(4):
        out.append((v >> (8 * k)) & 0xFF)


def section(out: bytearray, sid: int, body: bytearray) -> None:
    out.append(sid)
    uleb(out, len(body))
    out.extend(body)


def wasm_type(ll: str) -> int:
    # the WebAssembly type of an LLVM type, as llc's wasm32 lowering gives it
    if ll == "i64":
        return I64
    if ll == "double":
        return F64
    if ll == "ptr" or ll == "i1" or ll == "i8" or ll == "i32":
        return I32
    raise Refused(f"values of LLVM type {ll}")


def value_ll(t: str) -> str:
    # the LLVM type of a typed-IR value of type t (None as a value: a null pointer)
    return "ptr" if t == "None" else "ptr" if t.startswith("&") else lt(t)


# memory access of an LLVM type: (load opcode, store opcode, log2 of its alignment, size)
def access(ll: str) -> tuple[int, int, int, int]:
    if ll == "i64":
        return 0x29, 0x37, 3, 8
    if ll == "double":
        return 0x2B, 0x39, 3, 8
    if ll == "ptr" or ll == "i32":
        return 0x28, 0x36, 2, 4
    if ll == "i1" or ll == "i8":
        return 0x2D, 0x3A, 0, 1
    raise Refused(f"memory of LLVM type {ll}")


class Types:
    def __init__(self):
        self.sigs: list[str] = []
        self.index: dict[str, int] = {}

    def of(self, params: list[int], results: list[int]) -> int:
        key = ",".join([str(p) for p in params]) + ">" + ",".join([str(r) for r in results])
        if key not in self.index:
            self.index[key] = len(self.sigs)
            self.sigs.append(key)
        return self.index[key]

    def encode(self) -> bytearray:
        out = bytearray()
        uleb(out, len(self.sigs))
        for key in self.sigs:
            ps, rs = key.split(">")[0], key.split(">")[1]
            out.append(0x60)
            plist: list[str] = [] if ps == "" else ps.split(",")
            rlist: list[str] = [] if rs == "" else rs.split(",")
            uleb(out, len(plist))
            for p in plist:
                out.append(int(p))
            uleb(out, len(rlist))
            for r in rlist:
                out.append(int(r))
        return out


class Import:
    def __init__(self, sym: str, ll: list[str], typ: int):
        self.sym = sym
        self.ll = ll
        self.typ = typ


# The public promise starts at the handle. Its optional send and throw slots
# precede the private resume label, function-table index, source slots and spills.
def promise_words(m: Module) -> int:
    return generator_slots("protocol" in m.attrs, False, False)


def frame_inst(op: str, args: list[Operand], result: str = "", t: str = "") -> Inst:
    i = Inst(op)
    i.args = args
    i.t = t
    if result:
        i.res = [result]
    return i


def frame_address(block: Block, name: str, word: int) -> None:
    addr = frame_inst("mach.addr", [Operand("%ptr", "%wasm.frame"), Operand("int", str(word))], name, "%ptr")
    addr.fields["element"] = "int"
    block.code.append(addr)


def frame_store(block: Block, address: str, value: Operand) -> None:
    block.code.append(frame_inst("mach.store", [Operand("%ptr", address), value]))


def frame_addresses(block: Block, fn: Func, promise: int) -> None:
    for name, index in [("%wasm.value", GENVAL), ("%wasm.return", GENRET), ("%wasm.state", GENSTATE),
                        ("%wasm.name", GENNAME), ("%wasm.pc", promise), ("%wasm.target", promise + 1)]:
        frame_address(block, name, index)
    at = promise + 2
    for slot in fn.slots:
        frame_address(block, slot, at)
        at += 1


def spill_type(i: Inst, index: int) -> str:
    # Private LLVM intermediates have no guest value. A runtime bool result uses its
    # declared i64 ABI, whereas the overflow flag and ordinary bool results use i32.
    if index in OP_TEMPS.get(i.op, []) or not i.t:
        raise Refused(f"generator suspension uses an untyped result of {i.op}")
    ll = value_ll("bool" if i.op == "ovf" and index == 2 else i.t)
    if i.op == "rt":
        key = i.fields.get("entry", "")
        if key in RUNTIME:
            ll = rtll(rtsig(key)[0])
    wt = wasm_type(ll)
    return "int" if wt == I64 else "float" if wt == F64 else "%i32"


def generator_spills(fn: Func, labels: dict[str, int]) -> dict[str, list[Operand]]:
    values: dict[str, int] = {}
    definitions: list[tuple[str, Inst, int]] = []
    for block in fn.blocks:
        for i in block.code:
            for k in range(len(i.res)):
                name = i.res[k]
                values[name] = len(definitions)
                definitions.append((name, i, k))
    live = live_after_blocks(fn, labels, values)
    spills: dict[str, list[Operand]] = {}
    for b in range(len(fn.blocks)):
        block = fn.blocks[b]
        for i in block.code:
            if i.op in ("gen.start", "gen.yield"):
                if i is not block.code[-1] or len(i.targets) != 1 or (i.op == "gen.start" and b != 0):
                    raise Refused(f"generator suspension edge in {fn.name}")
                spills[block.label] = []
                for index in sorted(live[b]):
                    name, definition, k = definitions[index]
                    spills[block.label].append(Operand(spill_type(definition, k), name))
            if b and any(arg.v.startswith("%a") and arg.v[2:].isdigit() for arg in i.args):
                raise Refused(f"generator argument live across suspension in {fn.name}")
    return spills


def save_generator_position(block: Block, saved: list[Operand], words: dict[str, int], position: int) -> None:
    for value in saved:
        address = "%wasm.spill." + value.v
        frame_address(block, address, words[value.v])
        frame_store(block, address, value)
    frame_store(block, "%wasm.pc", Operand("int", str(position)))


def split_generator(fn: Func, resume: Func, target_slot: str, m: Module) -> Func:
    labels = fn.block_indices()
    if not fn.blocks or not fn.blocks[0].code or fn.frame_bytes:
        raise Refused(f"generator frame or entry in {fn.name}")
    entry = fn.blocks[0]
    start = entry.code[-1]
    if start.op != "gen.start" or len(start.args) != 1 or len(start.targets) != 1:
        raise Refused(f"generator initial suspension in {fn.name}")
    spills = generator_spills(fn, labels)
    promise = promise_words(m)
    first_spill = promise + 2 + len(fn.slots)
    words: dict[str, int] = {}
    for saved in spills.values():
        for value in saved:
            if value.v not in words:
                words[value.v] = first_spill + len(words)

    constructor = Func(fn.name)
    constructor.ptypes = fn.ptypes
    constructor.ret = fn.ret
    constructor.attrs = fn.attrs
    init = Block(entry.label)
    constructor.blocks = [init]
    size = 8 * (first_spill + len(words))
    alloc = frame_inst("rt", [Operand("int", str(size))], "%wasm.frame", "%ptr")
    alloc.fields["entry"] = "alloc"
    init.code.append(alloc)
    frame_addresses(init, fn, promise)
    init.code.extend(entry.code[:-1])
    frame_store(init, "%wasm.name", start.args[0])
    if "protocol" in m.attrs:
        frame_store(init, "%wasm.state", Operand("int", str(GENNEW)))

    resume.ret = "None"
    resume.ptypes = ["%ptr"]
    resume.cold = fn.cold
    resume.generator_exceptions = {slot for slot in fn.slots if fn.slots[slot] == "exc"}
    dispatch = Block(entry.label)
    resume.blocks.append(dispatch)
    dispatch.code.append(frame_inst("cast", [Operand("%ptr", "%a0")], "%wasm.frame", "%ptr"))
    frame_addresses(dispatch, fn, promise)
    dispatch.code.append(frame_inst("mach.load", [Operand("%ptr", "%wasm.pc")], "%wasm.position", "int"))
    switch = frame_inst("switch", [Operand("int", "%wasm.position")])
    switch.targets = ["wasm.invalid.position"]
    dispatch.code.append(switch)
    # Resume edges with phi inputs or saved registers need their own predecessor.
    # A plain edge can still dispatch straight to its original successor.
    edges: dict[str, str] = {}
    positions: dict[str, int] = {}
    for block in fn.blocks:
        if block.label not in spills:
            continue
        target = block.code[-1].targets[0]
        saved = spills[block.label]
        position = labels[target]
        if saved or any(i.op == "phi" for i in fn.blocks[position].code):
            position = len(fn.blocks) + labels[block.label]
            edge = Block(f"wasm.resume.edge.{position}")
            edges[block.label] = edge.label
            for value in saved:
                address = "%wasm.spill." + value.v
                frame_address(edge, address, words[value.v])
                edge.code.append(frame_inst("mach.load", [Operand("%ptr", address)], value.v, value.t))
                frame_store(edge, address, Operand("int", "0"))
            jump = frame_inst("br", [])
            jump.targets = [target]
            edge.code.append(jump)
            resume.blocks.append(edge)
            target = edge.label
        positions[block.label] = position
        if target not in switch.targets:
            switch.args.append(Operand("int", str(position)))
            switch.targets.append(target)
    # Save constructor temporaries before returning the handle for its first resume.
    save_generator_position(init, spills[entry.label], words, positions[entry.label])
    init.code.append(frame_inst("mach.load", [Operand("%ptr", target_slot)], "%wasm.function", "%ptr"))
    frame_store(init, "%wasm.target", Operand("%ptr", "%wasm.function"))
    init.code.append(frame_inst("ret", [Operand(fn.ret, "%wasm.frame")]))

    for block in fn.blocks[1:]:
        out = Block(block.label)
        resume.blocks.append(out)
        for i in block.code:
            if i.op == "gen.yield":
                if i.fields.get("cleanup", "0") != "0" or len(i.args) != 1:
                    raise Refused(f"generator yield with cleanup or an extended promise in {fn.name}")
                frame_store(out, "%wasm.value", i.args[0])
                save_generator_position(out, spills[block.label], words, positions[block.label])
                frame_store(out, "%wasm.state", Operand("int", "0"))
                out.code.append(frame_inst("ret", []))
            elif i.op == "gen.ret":
                if len(i.args) > 1:
                    raise Refused(f"extended generator return in {fn.name}")
                if i.args:
                    frame_store(out, "%wasm.return", i.args[0])
                frame_store(out, "%wasm.state", Operand("int", str(GENDONE)))
                out.code.append(frame_inst("ret", []))
            elif i.op == "gen.promise" and not i.args:
                out.code.append(frame_inst("cast", [Operand("%ptr", "%wasm.frame")], i.res[0], "%ptr"))
            elif i.op == "phi":
                phi = frame_inst("phi", i.args, i.res[0], i.t)
                phi.targets = [edges.get(pred, pred) for pred in i.targets]
                out.code.append(phi)
            else:
                out.code.append(i)
    invalid = Block("wasm.invalid.position")
    invalid.code.append(frame_inst("unreachable", []))
    resume.blocks.append(invalid)
    return constructor


def generator_functions(m: Module, targets: dict[str, str], handles: set[str]) -> list[Func]:
    functions: list[Func] = []
    for fn in m.funcs:
        if fn.coroutine:
            resume = Func("@wasm.resume." + fn.name)
            slot = "@wasm.resume.address." + fn.name
            targets[slot] = resume.name
            handles.add(fn.ret)
            constructor = split_generator(fn, resume, slot, m)
            constructor.line = fn.line
            resume.line = fn.line
            constructor.pyname = fn.pyname
            resume.pyname = fn.pyname
            functions.append(constructor)
            functions.append(resume)
        else:
            functions.append(fn)
    if handles:
        check_generator_drops(m)
    return functions


def check_generator_drops(m: Module) -> None:
    # A counted drop enters the runtime only to run suspended cleanup. Match the
    # original SSA handle before splitting the coroutine inserts spill reloads.
    constructors: dict[str, str] = {}
    cleanup: set[str] = set()
    for fn in m.funcs:
        if fn.coroutine:
            if any(i.op == "gen.yield" and i.fields.get("cleanup", "0") != "0" for b in fn.blocks for i in b.code):
                cleanup.add(fn.ret)
            else:
                constructors[fn.name] = fn.ret
    for fn in m.funcs:
        dropped: dict[str, str] = {}
        for block in fn.blocks:
            for i in block.code:
                if i.op == "gen.drop" and len(i.args) == 1:
                    handle = i.args[0]
                    if handle.t not in m.plain_generators or handle.t in cleanup:
                        dropped[handle.v] = handle.t
        if dropped:
            found: set[str] = set()
            for block in fn.blocks:
                for i in block.code:
                    for name in i.res:
                        if name in dropped:
                            if i.op != "call" or constructors.get(i.fields.get("callee", ""), "") != dropped[name]:
                                raise Refused(f"counted generator drop in {fn.name}")
                            found.add(name)
            if len(found) != len(dropped):
                raise Refused(f"counted generator drop in {fn.name}")


# ---------- emission ----------

class Emitter:
    def __init__(self, m: Module, standard_exceptions: bool = False, guest_roots: bool = False):
        self.m = m
        self.funcs: list[Func] = []
        self.generator_targets: dict[str, str] = {}
        self.generator_handles: set[str] = set()
        self.standard_exceptions = standard_exceptions
        self.guest_roots = guest_roots
        self.rooted: set[str] = set()   # the functions whose calls may collect and then return (rooted_functions)
        self.collecting: set[str] = set()   # the functions whose calls may collect at all
        self.refs: set[int] = set()     # this function's locals that may hold a reference
        self.spills = False             # whether this function's calls keep values in frames (spill_sets)
        self.spill_local = -1           # the address of the call frame that keeps them
        self.late: list[str] = []       # kept values whose locals a call's frame needed before their definition
        self.types = Types()
        self.imports: dict[str, Import] = {}
        self.import_order: list[str] = []
        self.fnindex: dict[str, int] = {}
        self.data = bytearray()
        self.addr: dict[str, int] = {}
        self.relocs: list[int] = []
        self.root_table = 0
        self.callbacks: dict[str, list[int]] = {}
        self.indirect_calls = False
        self.object_rows = 0
        self.recursion = False
        self.stack_frames = False
        self.catches = False
        self.exception_local = -1
        self.handler_stack = -1
        self.frame_local = -1
        self.dispatch_local = -1
        # structured control flow (Emitter.structure): each block's reverse postorder position,
        # whether it is a loop header or a merge node, its dominator tree children, and the
        # enclosing constructs a branch can name (kind 0: opaque, 1: a loop, 2: a block before a node)
        self.structured = False
        self.tree_pos: list[int] = []
        self.tree_header: list[bool] = []
        self.tree_merge: list[bool] = []
        self.tree_children: list[list[int]] = []
        self.ctx_kind: list[int] = []
        self.ctx_node: list[int] = []
        # per function
        self.fn = Func("")
        self.line = 0                   # the line of the instruction being emitted
        self.site_at: list[int] = []    # its calls' offsets in self.code, at self.site_line's lines
        self.site_line: list[int] = []
        self.sites: list[list[int]] = []  # each body's calls: offset in the body, line, ...
        self.locals: dict[str, int] = {}
        self.ltypes: list[int] = []
        self.compact_locals = False
        self.local_sites: list[tuple[int, int, int]] = []
        self.remap: list[int] = []
        self.nparams = 0
        self.code = bytearray()
        self.bindex: dict[str, int] = {}
        self.cur = 0
        self.phis: dict[str, list[Inst]] = {}
        self.depth_local = -1

    # -- module data: constants, then globals, each 8-aligned --
    # -- module data: constants, then globals, each 8-aligned. An address in it is relative to
    # the block until the loader adds the block's base at each of relocs (pystachy.reloc) --
    def lay_out_data(self) -> None:
        at = 0
        for c in self.m.consts:
            at = (at + 7) // 8 * 8
            self.addr[c.name] = at
            at += const_size(c)
        functions: dict[str, Func] = {}
        strings: set[str] = set()
        for c in self.m.consts:
            self.align8()
            if len(self.data) != self.addr[c.name]:
                raise Refused(f"layout of constant {c.name}")
            if c.kind == "string":
                codes = [ord(ch) for ch in c.text]
                ascii_only = True
                for x in codes:
                    if x > 255:
                        raise Refused(f"string constant {c.name} holds a character past a byte")
                    if x >= 128:
                        ascii_only = False
                self.word(len(codes))
                self.word(0)
                self.word(len(codes) + 1 if ascii_only else 0)
                for x in codes:
                    self.data.append(x)
                self.data.append(0)
            elif c.kind == "tuple" or c.kind == "listdata":
                # (lower_data: an i64 slot an item, lower_module.const_slot's; the empty tuple one slot)
                for item in c.items:
                    self.slot(item)
                if c.kind == "tuple" and len(c.items) == 0:
                    self.word(0)
            elif c.kind == "fieldnames":
                for r in c.refs:
                    self.ref(r)
            elif c.kind in ("exception", "callable"):
                if not functions:
                    functions = {fn.name: fn for fn in self.m.funcs}
                    strings = {data.name for data in self.m.consts if data.kind == "string"}
                if c.kind == "exception":
                    self.exception_descriptor(c, functions, strings)
                else:
                    self.callable_constant(c, functions)
            elif c.kind == "classrec" and len(c.refs) == 5 and len(c.items) == 3:
                # {ptr, ptr, ptr, i64, i64, ptr, i64, ptr}, at wasm32's offsets 0 4 8 16 24 32 40 48
                for r in c.refs[0:3]:
                    self.ref(r)
                self.align8()
                self.slot(c.items[0])
                self.slot(c.items[1])
                self.ref(c.refs[3])
                self.align8()
                self.slot(c.items[2])
                self.ref(c.refs[4])
                self.align8()
            else:
                raise Refused(f"constants of kind {c.kind}")
        for g in self.m.order:
            self.align8()
            self.addr[g] = len(self.data)
            t = self.m.globals[g]
            n = access(value_ll(t))[3]
            for _ in range(n):
                self.data.append(0)
        self.align8()
        if self.m.objects:
            self.object_rows = len(self.data)
            functions = {fn.name: fn for fn in self.m.funcs}
            if len(functions) != len(self.m.funcs):
                raise Refused("duplicate function in object dispatch module")
            for cls in self.m.objects:
                # wasm/reactor.c indexes these four wasm32 function pointers by class ID.
                for op in ("repr", "eq", "cmp", "hash"):
                    if (op in ("eq", "cmp") and cls not in self.m.compared) or (op == "hash" and cls not in self.m.hashed):
                        self.ref("null")
                        continue
                    target = "@o." + op + "." + cls
                    params = ["int", cls, cls] if op == "cmp" else [cls] if op == "hash" else [cls, cls]
                    result = "str" if op == "repr" else "int" if op == "hash" else "bool"
                    if target not in functions or functions[target].ptypes != params or functions[target].ret != result:
                        raise Refused(f"object callback {target} must take {params} and return {result}")
                    self.callback_ref(target)
        self.root_table = len(self.data)
        for g in self.m.roots:
            if g not in self.m.globals or lt(self.m.globals[g]) != "ptr":
                raise Refused(f"global root requires a pointer slot: {g}")
            self.ref(g)

        for slot in self.generator_targets:
            self.align8()
            self.addr[slot] = len(self.data)
            self.callback_ref(self.generator_targets[slot])

    def exception_descriptor(self, c: Const, functions: dict[str, Func], strings: set[str]) -> None:
        # runtime.c's ExcClass: two string pointers, then three wasm32 function
        # pointers (table indices). SystemExit subclasses supply the last callback.
        cls = c.name[3:]
        if not c.name.startswith("@x.") or cls not in self.m.classes or len(c.refs) != 5:
            raise Refused(f"exception descriptor {c.name}")
        if c.refs[0] not in strings or c.refs[1] not in strings:
            raise Refused(f"exception descriptor {c.name} requires string names")
        self.ref(c.refs[0])
        self.ref(c.refs[1])
        for j in range(2, 5):
            target = c.refs[j]
            if j == 4 and target == "null":
                self.ref("null")
                continue
            result = "exc" if j == 4 else "str"
            if target not in functions or functions[target].ptypes != [cls] or functions[target].ret != result:
                raise Refused(f"exception callback {target} must take {cls} and return {result}")
            self.callback_ref(target)

    def callable_constant(self, c: Const, functions: dict[str, Func]) -> None:
        if c.name.startswith("@x.mk."):
            # pys_exc_ctor walks (class descriptor, constructor) pairs up to NULL.
            if len(c.refs) < 2 or len(c.refs) % 2 or c.refs[-2:] != ["null", "null"]:
                raise Refused(f"invalid exception constructor table {c.name}")
            for j in range(0, len(c.refs) - 2, 2):
                cls = c.refs[j]
                ctor = c.refs[j + 1]
                if not cls.startswith("@x.") or cls[3:] not in self.m.classes or ctor not in functions or functions[ctor].ret != "exc":
                    raise Refused(f"invalid exception constructor {ctor} for {cls}")
                self.ref(cls)
                self.callback_ref(ctor)
            self.ref("null")
            self.ref("null")
        else:
            # A static Callable stores its adapter's code and a null environment.
            if len(c.refs) != 2 or c.refs[0] not in functions or c.refs[1] != "null":
                raise Refused(f"invalid callable constant {c.name}")
            self.callback_ref(c.refs[0])
            self.ref("null")

    def callback_ref(self, target: str) -> None:
        if target not in self.callbacks:
            self.callbacks[target] = []
        self.callbacks[target].append(len(self.data))
        self.data.extend(bytes(4))

    def ref(self, name: str) -> None:
        # a 4-byte address: null, or a constant's (relocated)
        if name == "null":
            self.data.extend(bytes(4))
        elif name in self.addr:
            self.relocs.append(len(self.data))
            self.data.extend(struct.pack("<I", self.addr[name]))
        else:
            raise Refused(f"a constant's reference to {name}")

    def slot(self, v: Operand) -> None:
        # an 8-byte slot of a constant tuple's item: as lower_module.const_slot gives it
        if v.t == "int":
            self.word(int(v.v))
        elif v.t == "bool":
            self.word(1 if v.v == "true" else 0)
        elif v.v == "null":
            self.word(0)
        elif v.t == "float":
            self.data.extend(float_bytes(v.v))
        elif v.v.startswith("@"):
            self.ref(v.v)
            self.data.extend(bytes(4))
        else:
            raise Refused(f"a constant item {v.t} {v.v}")

    def align8(self) -> None:
        while len(self.data) % 8 != 0:
            self.data.append(0)

    def word(self, v: int) -> None:
        self.data.extend(struct.pack("<q", v))

    # -- runtime functions, imported from runtime.wasm by symbol --
    def runtime(self, key: str) -> Import:
        if key not in RUNTIME:
            raise Refused(f"runtime entry {key}")
        sym = rtsym(key)
        sym = LIBC_WRAPPERS.get(sym, sym)
        if not sym.startswith("pys_"):
            raise Refused(f"runtime symbol {sym}")
        if sym not in self.imports:
            ll = [rtll(t) for t in rtsig(key)]
            params = [wasm_type(t) for t in ll[1:]]
            results: list[int] = [] if ll[0] == "void" else [wasm_type(ll[0])]
            self.imports[sym] = Import(sym, ll, self.types.of(params, results))
            self.import_order.append(sym)
        return self.imports[sym]

    def import_table_setter(self, sym: str) -> None:
        self.imports[sym] = Import(sym, ["void", "ptr", "i32"], self.types.of([I32, I32], []))
        self.import_order.append(sym)

    def rooted_functions(self) -> set[str]:
        # The functions whose activations a collection can find running below them and still need:
        # those whose calls may collect and then return, and those with a handler whose calls may
        # collect on their way to it. A runtime call counts as collecting and returning unless
        # RETURNS_UNCOLLECTED names it; one that collects only as it raises (a recursion limit's
        # RecursionError, raise) does not return.
        ret: dict[str, bool] = {}
        any_: dict[str, bool] = {}
        caught: dict[str, bool] = {}
        callees: dict[str, list[str]] = {}
        for fn in self.funcs:
            r = fn.coroutine or (fn.name == "@main.init" and "@g.atexit$_hook" in self.m.globals)
            a = r or fn.frame_bytes > 0
            c = False
            out: list[str] = []
            for b in fn.blocks:
                for i in b.code:
                    if i.is_invoke():
                        c = True
                    if i.op == "rt":
                        key = i.fields.get("entry", "")
                        if key in INLINE_RECURSION:
                            a = a or key == "recursion.enter"
                        elif key not in INLINE_RT:
                            a = True
                            r = r or self.rt_key(i) not in RETURNS_UNCOLLECTED
                    elif i.op in ("icall", "gen.resume", "alloc.fixed", "vtuple.make"):
                        r = True
                    elif i.op == "exc.match":
                        a = True
                    elif i.op in ("raise", "throw"):
                        a = True
                    elif i.op == "call":
                        out.append(i.fields.get("callee", ""))
                    elif i.op == "init":
                        out.append("@init." + i.fields.get("module", ""))
            ret[fn.name] = r or (c and a)   # (a handler that takes a collection's exception may return)
            any_[fn.name] = a or r
            caught[fn.name] = c
            callees[fn.name] = out
        changed = True
        while changed:
            changed = False
            for name in callees:
                for callee in callees[name]:
                    if callee not in ret:
                        if not ret[name]:   # (refused at the call; meanwhile, unknown)
                            ret[name] = any_[name] = changed = True
                    else:
                        if ret[callee] and not ret[name]:
                            ret[name] = changed = True
                        if any_[callee] and not any_[name]:
                            any_[name] = changed = True
                if caught[name] and any_[name] and not ret[name]:
                    ret[name] = changed = True
        out_set: set[str] = set()
        for name in ret:
            if ret[name]:
                out_set.add(name)
            if any_[name]:
                self.collecting.add(name)
        return out_set

    def collect_imports(self) -> None:
        # every runtime function the functions call, before function indexes are assigned
        if "@g.atexit$_hook" in self.m.globals:
            self.runtime("exit_hook")
        if self.m.objects:
            self.import_table_setter("pys_wasi_set_object_dispatch")
        if self.m.roots:
            self.import_table_setter("pys_wasi_set_global_roots")
        if self.guest_roots:
            self.imports["pys_wasi_set_guest_roots"] = Import("pys_wasi_set_guest_roots", ["void"], self.types.of([], []))
            self.import_order.append("pys_wasi_set_guest_roots")
        for fn in self.funcs:
            if fn.frame_bytes or (self.guest_roots and fn.name in self.collecting):
                self.stack_frames = True
                self.runtime("recursion.stack")
            for b in fn.blocks:
                for i in b.code:
                    if i.is_invoke():
                        self.catches = True
                    if i.op == "rt" and i.fields.get("entry", "") in INLINE_RECURSION:
                        self.recursion = True
                        if i.fields["entry"] == "recursion.enter":
                            self.runtime("recursion.error")
                    elif i.op == "rt" and i.fields.get("entry", "") not in INLINE_RT:
                        self.runtime(self.rt_key(i))
                    elif i.op == "alloc.fixed" or i.op == "vtuple.make":
                        self.alloc_import()
                    elif i.op == "raise":
                        self.runtime("raise")
                    elif i.op == "throw":
                        self.runtime("throw")
                    elif i.op == "exc.match":
                        self.runtime("exc.in")
        if self.recursion:
            self.runtime("recursion.error")

    def alloc_import(self) -> Import:
        return self.runtime(RTSYM["pys_new" if "allocelide" in items_of(self.m.attrs.get("opts", "[]")) else "pys_alloc"])

    def rt_key(self, i: Inst) -> str:
        key = i.fields.get("entry", "")
        hole = int(i.fields.get("hole", "0"))
        if hole > 0 and key == "list.new" and atomic_list(self.m.holes.get(hole, "")):
            return RTSYM["pys_list_new_atomic"]
        if hole > 0 and key == "dict.new" and atomic_dict(self.m.holes.get(hole, "")):
            return RTSYM["pys_dict_new_atomic"]
        return key

    # -- functions --
    def local(self, name: str, wt: int, ref: bool = True) -> int:
        # ref: the value may be a reference, which guest roots keep where the collector's scan reads
        if name not in self.locals:
            self.locals[name] = len(self.ltypes)
            self.ltypes.append(wt)
            if wt != F64 and ref:
                self.refs.add(self.locals[name])
        return self.locals[name]

    def scratch(self, wt: int) -> int:
        self.ltypes.append(wt)
        return len(self.ltypes) - 1

    def op(self, b: int) -> None:
        self.code.append(b)

    def call_op(self, b: int) -> None:
        # a call (b) whose offset a traceback's frame may name: noted with the current line
        if self.line > 0:
            self.site_at.append(len(self.code))
            self.site_line.append(self.line)
        self.code.append(b)

    def local_op(self, opcode: int, k: int) -> None:
        self.code.append(opcode)
        if self.remap:
            uleb(self.code, self.remap[k])
        else:
            at = len(self.code)
            uleb(self.code, k)
            if self.compact_locals:
                self.local_sites.append((at, len(self.code), k))

    def get(self, k: int) -> None:
        self.local_op(0x20, k)

    def set(self, k: int) -> None:
        self.local_op(0x21, k)

    def spill(self, i: Inst) -> int:
        # Below the stack pointer, a frame that keeps the values a call may need once it has
        # collected, where the collector's stack scan reads them; its size, released after the call
        # (an exception's handler restores the stack pointer). i64 locals can hold packed
        # references: the conservative wasm32 scan finds their low word, as an i32 local's pointer.
        ks: list[int] = []
        for name in i.keep:
            if name not in self.locals:
                self.late.append(name)   # (defined further on: function emits fn again)
                continue
            k = self.locals[name]
            if k in self.refs and k not in ks:
                ks.append(k)
        if not ks:
            return 0
        size = (8 * len(ks) + 15) // 16 * 16
        self.op(0x23)  # global.get rt.__stack_pointer
        uleb(self.code, 2)
        self.i32c(size)
        self.op(0x6B)  # i32.sub
        self.local_op(0x22, self.spill_local)
        self.op(0x24)  # global.set rt.__stack_pointer
        uleb(self.code, 2)
        for j in range(len(ks)):
            self.get(self.spill_local)
            self.get(ks[j])
            if self.ltypes[ks[j]] == I32:
                self.op(0xAD)  # i64.extend_i32_u: the whole slot, no stale upper word
            self.mem(0x37, 3, 8 * j)
        if 8 * len(ks) < size:
            self.get(self.spill_local)
            self.i64c(0)
            self.mem(0x37, 3, 8 * len(ks))
        return size

    def release(self, size: int) -> None:
        # (cleared first: a later scan of the dead stack below a live frame must not find its values)
        for offset in range(0, size, 8):
            self.get(self.spill_local)
            self.i64c(0)
            self.mem(0x37, 3, offset)
        if size:
            self.get(self.spill_local)
            self.i32c(size)
            self.op(0x6A)
            self.op(0x24)  # global.set rt.__stack_pointer
            uleb(self.code, 2)

    def spill_sets(self, fn: Func) -> bool:
        # Sets Inst.keep for each call in fn that may collect and then return, or that may collect
        # on its way to a handler here: the parameters, slots and values live after it, and the
        # operands vtuple.make stores after its allocation (other calls' callees keep their own).
        # A call that cannot collect needs no frame. Whether any call has one.
        out = False
        for blk in fn.blocks:
            for i in blk.code:
                i.keep = []
        if not self.guest_roots or fn.name not in self.collecting:
            return out
        values: dict[str, int] = {}
        for j in range(len(fn.ptypes)):
            values[f"%a{j}"] = j
        for slot in fn.slots:
            values[slot] = len(values)
        for blk in fn.blocks:
            for i in blk.code:
                for name in i.res:
                    if name not in values:
                        values[name] = len(values)
        names = [name for name in values]
        count = len(fn.blocks)
        uses: list[set[int]] = [set() for _ in range(count)]
        defs: list[set[int]] = [set() for _ in range(count)]
        live_out: list[set[int]] = [set() for _ in range(count)]
        successors: list[set[int]] = [set() for _ in range(count)]
        for bi in range(count):
            for i in fn.blocks[bi].code:
                if i.op == "phi":
                    for j in range(len(i.args)):   # (read at the end of the edge's source)
                        if i.args[j].v in values:
                            live_out[self.bindex[i.targets[j]]].add(values[i.args[j].v])
                else:
                    for v in self.reads(i, values):
                        if v not in defs[bi]:
                            uses[bi].add(v)
                    for label in i.targets:
                        successors[bi].add(self.bindex[label])
                    if i.op == "check":
                        successors[bi].add(self.bindex[fn.cold[i.fields.get("key", "") or i.fields.get("message", "")]])
                for v in self.writes(i, values):
                    defs[bi].add(v)
        live_in = [u.copy() for u in uses]
        changed = True
        while changed:
            changed = False
            for bi in range(count - 1, -1, -1):
                for succ in successors[bi]:
                    live_out[bi].update(live_in[succ])
                before = uses[bi] | (live_out[bi] - defs[bi])
                if before != live_in[bi]:
                    live_in[bi] = before
                    changed = True
        for bi in range(count):
            live = live_out[bi].copy()
            code = fn.blocks[bi].code
            for j in range(len(code) - 1, -1, -1):
                i = code[j]
                if i.op == "phi":
                    continue
                written = self.writes(i, values)
                if self.collects(i):
                    i.keep = [names[v] for v in sorted(live) if v not in written]
                    if i.op == "vtuple.make":
                        i.keep += [a.v for a in i.args if a.v in values]
                    out = True
                for v in written:
                    live.discard(v)
                for v in self.reads(i, values):
                    live.add(v)
        return out

    def reads(self, i: Inst, values: dict[str, int]) -> list[int]:
        # the parameters, slots and values i reads (store and landing write their first operand's slot)
        out: list[int] = []
        for j in range(len(i.args)):
            v = i.args[j].v
            if v in values and not (j == 0 and v in self.fn.slots and i.op in ("store", "landing")):
                out.append(values[v])
        return out

    def writes(self, i: Inst, values: dict[str, int]) -> list[int]:
        out = [values[name] for name in i.res if name in values]
        if i.op in ("store", "landing") and i.args and i.args[0].v in self.fn.slots:
            out.append(values[i.args[0].v])
        return out

    def collects(self, i: Inst) -> bool:
        # whether a collection during i's call may need this function's values: it may collect and
        # return, or i has a handler here and may collect at all (rooted_functions' rules)
        invoke = i.is_invoke()
        if i.op == "rt":
            key = i.fields.get("entry", "")
            if key in INLINE_RECURSION or key in INLINE_RT:
                return False
            return invoke or self.rt_key(i) not in RETURNS_UNCOLLECTED
        if i.op in ("call", "init"):
            callee = i.fields.get("callee", "") if i.op == "call" else "@init." + i.fields.get("module", "")
            return callee not in self.fnindex or callee in self.rooted or (invoke and callee in self.collecting)
        return i.op in ("icall", "gen.resume", "alloc.fixed", "vtuple.make")

    def i32c(self, v: int) -> None:
        self.code.append(0x41)
        # LLVM may spell a 32-bit mask as an unsigned decimal. Wasm i32.const
        # expects a signed immediate with the same 32-bit pattern.
        sleb(self.code, v - 4294967296 if 2147483648 <= v <= 4294967295 else v)

    def i64c(self, v: int) -> None:
        self.code.append(0x42)
        sleb(self.code, v)

    def mem(self, opcode: int, align: int, offset: int) -> None:
        self.code.append(opcode)
        uleb(self.code, align)
        uleb(self.code, offset)

    def data_addr(self, sym: str, offset: int) -> None:
        # the address of module data sym: env.data's base plus its offset
        self.code.append(0x23)
        uleb(self.code, 0)
        self.i32c(self.addr[sym] + offset)
        self.op(0x6A)

    def push(self, a: Operand, ll: str) -> None:
        # push operand a as LLVM type ll
        v = a.v
        wt = wasm_type(ll)
        if v in self.fn.tuple_offsets:
            if ll != "ptr":
                raise Refused(f"tuple frame address {v} as {ll}")
            self.get(self.frame_local)
            offset = self.fn.tuple_offsets[v]
            if offset:
                self.i32c(offset)
                self.op(0x6A)
        elif v.startswith("%"):
            if v in self.fn.slots:
                raise Refused(f"the address of slot {v} as a value")
            if v not in self.locals:
                raise Refused(f"value {v} used before it is defined")
            k = self.locals[v]
            have = self.ltypes[k]
            self.get(k)
            if have != wt:
                if have == I32 and wt == I64:
                    self.op(0xAD)  # (i64.extend_i32_u: a bool to an i64 parameter)
                else:
                    raise Refused(f"{v} of type {a.t} as {ll}")
        elif v.startswith("@"):
            if v in self.addr and wt == I32:
                self.data_addr(v, 0)
            elif v in self.fnindex and ll == "ptr":
                # Bound and captured callables store code in heap objects. Read its
                # relocated table index from a slot populated by the start function.
                if v not in self.callbacks:
                    self.callback_ref(v)
                self.code.extend(b"\x23\x00")  # global.get env.data
                self.mem(0x28, 2, self.callbacks[v][0])
            else:
                raise Refused(f"symbol {v} as a value")
        elif v == "true" or v == "false":
            if wt == I64:
                self.i64c(1 if v == "true" else 0)
            else:
                self.i32c(1 if v == "true" else 0)
        elif v == "null" or v == "zeroinitializer":
            if wt != I32:
                raise Refused(f"null as {ll}")
            self.i32c(0)
        elif v.startswith("ptrtoint (ptr ") and v.endswith(" to i64)") and wt == I64:
            # A dict/set key descriptor. A populated dict can retain the KTAG bit
            # (2) in its aligned descriptor address as gen_key_kind specifies.
            sym = v[len("ptrtoint (ptr "):len(v) - len(" to i64)")]
            tag = 0
            if sym.startswith("getelementptr (i8, ptr @") and sym.endswith(", i64 2)"):
                sym = sym[len("getelementptr (i8, ptr "):len(sym) - len(", i64 2)")]
                tag = 2
            if sym not in self.addr:
                raise Refused(f"symbol {sym} as a value")
            self.data_addr(sym, tag)
            self.op(0xAD)
        elif wt == F64:
            self.op(0x44)
            self.code.extend(float_bytes(v))
        elif not is_number(v) or "." in v or "e" in v:
            raise Refused(f"an operand {v} as {ll}")
        elif wt == I64:
            self.i64c(int(v))
        else:
            self.i32c(int(v))

    def define(self, name: str, t: str) -> int:
        return self.local(name, wasm_type(value_ll(t)), t not in SCALARS)

    def function(self, fn: Func) -> bytearray:
        # Blocks follow the IR's order, which need not put a definition before every call its value
        # is live across: a second pass declares those values' locals first (spill)
        out = self.emit_function(fn, [])
        if self.late:
            late = [(name, self.ltypes[self.locals[name]], self.locals[name] in self.refs)
                    for name in self.late if name in self.locals]
            self.sites.pop()
            out = self.emit_function(fn, late)
            if self.late:
                raise Refused(f"guest root {self.late[0]} without a definition in {fn.name}")
        return out

    def emit_function(self, fn: Func, late: list[tuple[str, int, bool]]) -> bytearray:
        self.fn = fn
        self.refs = set()
        self.late = []
        self.locals = {}
        self.remap = []
        self.local_sites = []
        self.compact_locals = False
        self.ltypes = []
        self.code = bytearray()
        self.site_at = []
        self.site_line = []
        self.line = 0
        self.depth_local = -1
        # (a parameter of type None is not passed, as lowering's IFn.ps: its uses read a null local)
        for j in range(len(fn.ptypes)):
            if fn.ptypes[j] != "None":
                self.local(f"%a{j}", wasm_type(value_ll(fn.ptypes[j])), fn.ptypes[j] not in SCALARS)
        self.nparams = len(self.ltypes)
        for j in range(len(fn.ptypes)):
            if fn.ptypes[j] == "None":
                self.local(f"%a{j}", I32)
        for s in fn.slots:
            self.local(s, wasm_type(value_ll(fn.slots[s])), fn.slots[s] not in SCALARS)
        for name, wt, ref in late:
            self.local(name, wt, ref)
        self.frame_local = self.scratch(I32) if fn.frame_bytes else -1
        self.exception_local = -1
        self.handler_stack = -1
        self.bindex = fn.block_indices()
        self.spills = self.spill_sets(fn)
        self.spill_local = self.scratch(I32) if self.spills else -1
        self.phis = {}
        # Finalization marks functions whose activations can recur with recursion.enter.
        # Compact only those frames, so ordinary one-shot calls keep the short lowering path.
        # SSA values share locals where their lifetimes do not meet (register_colors): fewer locals for
        # V8's baseline compiler, which runs a long call's loops, and smaller frames for recursion
        if fn.blocks:
            self.compact_locals = True
        for b in fn.blocks:
            for i in b.code:
                if i.op != "phi" and i.targets and i is not b.code[-1]:
                    self.compact_locals = False  # only terminal edges are modeled in textual IR
                if self.exception_local < 0 and i.is_invoke():
                    self.exception_local = self.scratch(I32)
                    self.handler_stack = self.frame_local if self.frame_local >= 0 else self.scratch(I32)
                elif i.op == "phi":
                    self.define(i.res[0], i.t)
                    if b.label not in self.phis:
                        self.phis[b.label] = []
                    self.phis[b.label].append(i)
        n = len(fn.blocks)
        self.dispatch_local = -1
        self.structured = self.structure(fn)
        if self.structured:
            self.ctx_kind = []
            self.ctx_node = []
            self.do_tree(0)
        else:
            # Forward edges branch out of nested blocks. Only a backedge needs a
            # dispatcher: emit the body first so goto can request one on demand.
            for j in range(n):
                if j > 0:
                    self.op(0x0B)
                self.emit_block(j)
        packed = self.ltypes
        blocks = self.code
        calls = self.site_at
        if self.compact_locals:
            self.remap, packed = register_colors(fn, self.bindex, self.locals, self.ltypes)
            blocks = bytearray()
            at = 0
            moved: list[int] = []
            k = 0
            for site in self.local_sites:
                while k < len(calls) and calls[k] < site[0]:
                    moved.append(calls[k] + len(blocks) - at)
                    k += 1
                blocks.extend(self.code[at:site[0]])
                uleb(blocks, self.remap[site[2]])
                at = site[1]
            while k < len(calls):
                moved.append(calls[k] + len(blocks) - at)
                k += 1
            blocks.extend(self.code[at:])
            calls = moved
        lines = self.site_line
        self.site_at = []
        self.site_line = []
        self.line = fn.line  # the prologue's calls: a recursion limit's
        self.code = bytearray()
        if fn.name == "@main.init" and "@g.atexit$_hook" in self.m.globals:
            self.call_import(self.runtime("exit_hook"), [Operand("%ptr", "@g.atexit$_hook")])
        if self.frame_local >= 0:
            self.enter_frame()
        if self.handler_stack >= 0 and self.frame_local < 0:
            self.op(0x23)  # global.get rt.__stack_pointer at function entry
            uleb(self.code, 2)
            self.set(self.handler_stack)
        if self.dispatch_local >= 0:
            self.op(0x03)
            self.op(VOID)
        for j in range(1, n if not self.structured else 1):
            self.op(0x02)
            self.op(VOID)
        if self.dispatch_local >= 0:
            self.op(0x02)
            self.op(VOID)
            self.get(self.dispatch_local)
            self.op(0x0E)
            uleb(self.code, n)
            for j in range(n):
                uleb(self.code, j)
            uleb(self.code, 0)
            self.op(0x0B)
        prologue = len(self.code)
        self.code.extend(blocks)
        if self.dispatch_local >= 0:
            self.op(0x0B)
        self.op(0x00)
        self.op(0x0B)
        body = bytearray()
        # One local declaration per consecutive run of the same Wasm type.
        decls = bytearray()
        groups = 0
        j = self.nparams
        while j < len(packed):
            wt = packed[j]
            end = j + 1
            while end < len(packed) and packed[end] == wt:
                end += 1
            uleb(decls, end - j)
            decls.append(wt)
            groups += 1
            j = end
        uleb(body, groups)
        body.extend(decls)
        body.extend(self.code)
        out = bytearray()
        uleb(out, len(body))
        head = len(out) + len(body) - len(self.code)
        out.extend(body)
        # each call's offset in out, and its line: the prologue's, then the blocks'
        sites: list[int] = []
        if fn.pyname != "":
            for k in range(len(self.site_at)):
                sites.append(head + self.site_at[k])
                sites.append(self.site_line[k])
            for k in range(len(calls)):
                sites.append(head + prologue + calls[k])
                sites.append(lines[k])
        self.sites.append(sites)
        self.site_at = []
        self.site_line = []
        self.remap = []
        self.compact_locals = False
        return out

    def enter_frame(self) -> None:
        # Reserve an ABI-aligned frame on the reactor's linear-memory stack. Its
        # pys_on_stack check must recognize *args tuples before a callee keeps them.
        size = (self.fn.frame_bytes + 15) // 16 * 16
        self.op(0x23)  # global.get rt.__stack_pointer (global 2)
        uleb(self.code, 2)
        self.op(0xAD)  # i64.extend_i32_u, so subtracting a large frame cannot wrap
        self.op(0x23)  # global.get rt.pys_recursion_state
        uleb(self.code, 1)
        self.mem(0x29, 3, 16)  # native stack floor, including runtime call margin
        self.i64c(size)
        self.op(0x7C)
        self.op(0x54)  # i64.lt_u
        self.op(0x04)
        self.op(VOID)
        self.call_import(self.runtime("recursion.stack"), [])
        self.op(0x00)
        self.op(0x0B)
        self.op(0x23)
        uleb(self.code, 2)
        self.i32c(size)
        self.op(0x6B)  # i32.sub
        self.local_op(0x22, self.frame_local)  # local.tee frame
        self.op(0x24)  # global.set rt.__stack_pointer
        uleb(self.code, 2)

    def emit_block(self, j: int) -> None:
        self.cur = j
        for i in self.fn.blocks[j].code:
            if i.is_invoke():
                self.invoke(i)
            else:
                self.inst(i)

    def structure(self, fn: Func) -> bool:
        # Structured control flow (Ramsey, "Beyond Relooper", ICFP 2022). For a reducible CFG,
        # blocks follow the dominator tree: a loop header opens a loop that its back edges
        # continue; a node with two or more forward edges into it (a merge node) follows a block
        # that they leave; any other node's code is placed at its one forward edge. False where an
        # edge leaves mid-block or the CFG is irreducible (a generator's resume points): goto's
        # dispatcher then serves its back edges.
        n = len(fn.blocks)
        if n == 0:
            return False
        succ: list[list[int]] = []
        for j in range(n):
            out: list[int] = []
            code = fn.blocks[j].code
            for k in range(len(code)):
                i = code[k]
                if i.op == "phi" or (len(i.targets) == 0 and i.op != "check"):
                    continue
                if k != len(code) - 1:
                    return False
                if i.op == "check":
                    key = i.fields.get("key", "") or i.fields.get("message", "")
                    if key not in fn.cold or fn.cold[key] not in self.bindex:
                        return False
                    out.append(self.bindex[fn.cold[key]])
                for t in i.targets:
                    if t not in self.bindex:
                        return False
                    out.append(self.bindex[t])
            succ.append(out)
        # reverse postorder from the entry
        seen = [False] * n
        nxt = [0] * n
        post: list[int] = []
        stack = [0]
        seen[0] = True
        while len(stack) > 0:
            u = stack[len(stack) - 1]
            if nxt[u] < len(succ[u]):
                v = succ[u][nxt[u]]
                nxt[u] += 1
                if not seen[v]:
                    seen[v] = True
                    stack.append(v)
            else:
                post.append(u)
                stack.pop()
        rpo: list[int] = []
        for k in range(len(post) - 1, -1, -1):
            rpo.append(post[k])
        pos = [-1] * n
        for k in range(len(rpo)):
            pos[rpo[k]] = k
        preds: list[list[int]] = [[] for _ in range(n)]
        for u in rpo:
            for v in succ[u]:
                preds[v].append(u)
        # immediate dominators (Cooper, Harvey and Kennedy's iteration)
        idom = [-1] * n
        idom[0] = 0
        changed = True
        while changed:
            changed = False
            for k in range(1, len(rpo)):
                u = rpo[k]
                new = -1
                for p in preds[u]:
                    if idom[p] < 0:
                        continue
                    if new < 0:
                        new = p
                        continue
                    a = p
                    b = new
                    while a != b:
                        while pos[a] > pos[b]:
                            a = idom[a]
                        while pos[b] > pos[a]:
                            b = idom[b]
                    new = a
                if new != idom[u]:
                    idom[u] = new
                    changed = True
        header = [False] * n
        forward = [0] * n
        for u in rpo:
            for v in succ[u]:
                if pos[v] <= pos[u]:
                    w = u
                    while w != v and w != 0:
                        w = idom[w]
                    if w != v:
                        return False  # a loop entered other than through its header
                    header[v] = True
                else:
                    forward[v] += 1
        children: list[list[int]] = [[] for _ in range(n)]
        for k in range(1, len(rpo)):
            children[idom[rpo[k]]].append(rpo[k])
        self.tree_pos = pos
        self.tree_header = header
        self.tree_merge = [forward[v] >= 2 for v in range(n)]
        self.tree_children = children
        return True

    def do_tree(self, x: int) -> None:
        # x's code within the blocks that its merge-node children follow, the latest outermost
        merges: list[list[int]] = []
        for c in self.tree_children[x]:
            if self.tree_merge[c]:
                merges.append([self.tree_pos[c], c])
        merges.sort()
        nodes: list[int] = []
        for k in range(len(merges) - 1, -1, -1):
            nodes.append(merges[k][1])
        if self.tree_header[x]:
            self.op(0x03)
            self.op(VOID)
            self.ctx_kind.append(1)
            self.ctx_node.append(x)
            self.node_within(x, nodes, 0)
            self.ctx_kind.pop()
            self.ctx_node.pop()
            self.op(0x0B)
        else:
            self.node_within(x, nodes, 0)

    def node_within(self, x: int, nodes: list[int], k: int) -> None:
        if k == len(nodes):
            self.emit_block(x)
            return
        self.op(0x02)
        self.op(VOID)
        self.ctx_kind.append(2)
        self.ctx_node.append(nodes[k])
        self.node_within(x, nodes, k + 1)
        self.ctx_kind.pop()
        self.ctx_node.pop()
        self.op(0x0B)
        self.do_tree(nodes[k])

    def br_to(self, kind: int, node: int, extra_depth: int) -> None:
        for k in range(len(self.ctx_kind) - 1, -1, -1):
            if self.ctx_kind[k] == kind and self.ctx_node[k] == node:
                self.op(0x0C)
                uleb(self.code, len(self.ctx_kind) - 1 - k + extra_depth)
                return
        raise Refused(f"no enclosing construct for {self.fn.blocks[node].label} in {self.fn.name}")

    def goto(self, label: str, extra_depth: int) -> None:
        # from block self.cur, to label: its phis' values (all read, then all set), then a br
        if label not in self.bindex:
            raise Refused(f"branch to unknown block {label}")
        target = self.bindex[label]
        phis = self.phis.get(label, [])
        here = self.fn.blocks[self.cur].label
        for p in phis:
            k = p.targets.index(here) if here in p.targets else -1
            if k < 0:
                raise Refused(f"phi in {label} without a value from {here}")
            self.push(p.args[k], value_ll(p.t))
        for j in range(len(phis) - 1, -1, -1):
            self.set(self.locals[phis[j].res[0]])
        if self.structured:
            if self.tree_pos[target] <= self.tree_pos[self.cur]:
                self.br_to(1, target, extra_depth)  # a back edge: continue its loop
            elif self.tree_merge[target]:
                self.br_to(2, target, extra_depth)  # leave the block that the node follows
            else:
                # this is the node's one forward edge, from its immediate dominator: its code is here
                for _ in range(extra_depth):
                    self.ctx_kind.append(0)
                    self.ctx_node.append(-1)
                here_block = self.cur
                self.do_tree(target)
                self.cur = here_block
                for _ in range(extra_depth):
                    self.ctx_kind.pop()
                    self.ctx_node.pop()
            return
        n = len(self.fn.blocks)
        if target == self.cur + 1 and extra_depth == 0:
            return  # the successor follows immediately after this block
        if target > self.cur:
            self.op(0x0C)
            uleb(self.code, target - self.cur - 1 + extra_depth)
        else:
            if self.dispatch_local < 0:
                self.dispatch_local = self.scratch(I32)
            self.i32c(target)
            self.set(self.dispatch_local)
            self.op(0x0C)
            uleb(self.code, n - 1 - self.cur + extra_depth)

    def call_import(self, imp: Import, args: list[Operand]) -> None:
        if len(args) != len(imp.ll) - 1:
            raise Refused(f"call of {imp.sym} with {len(args)} arguments")
        for j in range(len(args)):
            self.push(args[j], imp.ll[j + 1])
        self.call_op(0x10)
        uleb(self.code, self.fnindex[imp.sym])

    def invoke(self, i: Inst) -> None:
        # Finalized invokes have explicit normal and unwind successors. Catch the
        # runtime's Python tag alone; a host exception or a Wasm trap must escape.
        if "exceptions" not in self.m.attrs or len(i.targets) != 2:
            raise Refused(f"invalid exception edges on {i.op}")
        pad = self.bindex.get(i.targets[1], -1)
        if pad < 0 or not self.fn.blocks[pad].code or self.fn.blocks[pad].code[0].op != "landing":
            raise Refused(f"invoke without a landing at {i.targets[1]}")
        if self.standard_exceptions:
            self.op(0x02)  # block (result i32): receives the caught exception pointer
            self.op(I32)
            self.op(0x1F)  # try_table, no results, one catch of tag 0 to the block
            self.op(VOID)
            self.op(1)
            self.op(0)  # catch (payload only)
            self.op(0)  # tag index
            self.op(0)  # enclosing block depth, relative to the try_table
            self.inst(i)
            self.op(0x0B)
            self.goto(i.targets[0], 1)
            self.op(0x0B)
        else:
            self.op(0x06)  # legacy try/catch for early Node 22 releases
            self.op(VOID)
            self.inst(i)
            self.op(0x07)
            uleb(self.code, 0)
        self.set(self.exception_local)
        # Both runtime C calls and emitted tuple frames use this linear stack.
        # Unwinding Wasm activation records alone leaves its global at the throw site.
        self.get(self.handler_stack)
        self.op(0x24)
        uleb(self.code, 2)
        if self.standard_exceptions:
            self.goto(i.targets[1], 0)
        else:
            self.goto(i.targets[1], 1)
            self.op(0x0B)
            self.goto(i.targets[0], 0)

    def result(self, i: Inst, k: int, t: str) -> None:
        self.set(self.define(i.res[k], t))

    def address(self, a: Operand) -> None:
        # a computed address (an i32 value)
        self.push(a, "ptr")

    def inst(self, i: Inst) -> None:
        self.line = i.line
        size = self.spill(i)
        self.operation(i)
        self.release(size)

    def operation(self, i: Inst) -> None:
        op = i.op
        if op == "phi":
            return
        if op == "rt":
            key = i.fields.get("entry", "")
            if key in INLINE_RECURSION:
                self.recursion_op(i, key)
                return
            if key == "fabs":
                self.push(i.args[0], "double")
                self.op(0x99)  # (f64.abs)
                self.result(i, 0, "float")
                return
            if key == "fdiv" or key == "m.sqrt":
                # the IEEE 754 instruction, calling the runtime only where Python raises: for a zero
                # divisor (ZeroDivisionError) or a number below zero (a math domain error)
                imp = self.runtime(key)
                self.push(i.args[-1], "double")
                self.op(0x44)
                self.code.extend(float_bytes("0.0"))
                self.op(0x61 if key == "fdiv" else 0x63)  # (f64.eq, f64.lt)
                self.op(0x04)
                self.op(F64)
                self.call_import(imp, i.args)
                self.op(0x05)
                for a in i.args:
                    self.push(a, "double")
                self.op(0xA3 if key == "fdiv" else 0x9F)  # (f64.div, f64.sqrt)
                self.op(0x0B)
                self.result(i, 0, "float")
                return
            if key == "memmove":
                # memmove(dst, src, n, volatile): Wasm's bulk copy also allows overlap
                self.push(i.args[0], "ptr")
                self.push(i.args[1], "ptr")
                self.push(i.args[2], "i64")
                self.op(0xA7)  # (i32.wrap_i64)
                self.code.extend(b"\xfc\x0a\x00\x00")  # (memory.copy 0 0)
                return
            imp = self.runtime(self.rt_key(i))
            args = i.args
            hole = int(i.fields.get("hole", "0"))
            if hole > 0 and (key == "dict.new" or key == "set.new"):
                h = self.m.holes.get(hole, "")
                kind = self.m.keykinds.get(h, "0") if h != "" else "0"
                args = [key_kind_operand(kind)] + args[1:]
            self.call_import(imp, args)
            if imp.ll[0] != "void":
                if len(i.res) == 0:
                    self.op(0x1A)
                else:
                    self.set(self.local(i.res[0], wasm_type(imp.ll[0])))
        elif op in ("call", "icall"):
            args = i.args
            if op == "icall":
                if not args or args[0].t != "%ptr" or not i.t:
                    raise Refused("invalid indirect call signature")
                args = args[1:]
            for a in args:
                if a.t != "None":
                    self.push(a, value_ll(a.t))
            if op == "icall":
                self.indirect_calls = True
                params = [wasm_type(value_ll(a.t)) for a in args if a.t != "None"]
                results: list[int] = [] if i.t == "None" else [wasm_type(value_ll(i.t))]
                self.push(i.args[0], "ptr")
                self.call_op(0x11)  # call_indirect expects the index after the arguments
                uleb(self.code, self.types.of(params, results))
                uleb(self.code, 0)
            else:
                callee = i.fields.get("callee", "")
                if callee not in self.fnindex:
                    raise Refused(f"call of {callee}")
                self.call_op(0x10)
                uleb(self.code, self.fnindex[callee])
            if i.t != "None" and i.t != "":
                if len(i.res) == 0:
                    self.op(0x1A)
                else:
                    self.result(i, 0, i.t)
        elif op in ("gen.promise", "gen.resume", "gen.drop"):
            if len(i.args) != 1 or i.args[0].t not in self.generator_handles:
                raise Refused(f"unknown generator producer in {self.fn.name}")
            self.push(i.args[0], "ptr")
            if op == "gen.promise":
                self.result(i, 0, "%ptr")
            elif op == "gen.drop":
                self.i64c(GENDONE)
                self.mem(0x37, 3, GENSTATE * 8)
            else:
                self.push(i.args[0], "ptr")
                self.mem(0x28, 2, (promise_words(self.m) + 1) * 8)
                self.call_op(0x11)  # call_indirect (frame) using this instance's producer
                uleb(self.code, self.types.of([I32], []))
                uleb(self.code, 0)
        elif op == "init":
            callee = "@init." + i.fields.get("module", "")
            if callee not in self.fnindex:
                raise Refused(f"module init {callee}")
            self.call_op(0x10)
            uleb(self.code, self.fnindex[callee])
        elif op == "cast":
            # (a cast reads its operand at another type of the same LLVM type: no instruction)
            self.push(i.args[0], value_ll(i.t))
            self.result(i, 0, i.t)
        elif op in WORD_READS:
            # (machine_ir: a load of the object's word k, at the op's type)
            ll = value_ll(i.t)
            self.address(i.args[0])
            self.mem(access(ll)[0], access(ll)[2], 8 * WORD_READS[op])
            self.result(i, len(i.res) - 1, i.t)
        elif op == "empty.kind":
            # a fresh empty dict's or set's key kind, its second word, as finalization resolved it
            hole = int(i.fields.get("hole", "0"))
            t = self.m.holes.get(hole, "") if hole > 0 else i.args[0].t
            kind = self.m.builtkinds.get(t, "") if t != "" else "0"
            self.address(i.args[0])
            self.i32c(8)
            self.op(0x6A)
            self.set(self.local(i.res[0], I32))
            self.get(self.locals[i.res[0]])
            self.push(key_kind_operand(kind), "i64")
            self.mem(0x37, 3, 0)
        elif op == "ret":
            if len(i.args) > 0 and i.args[0].v in self.fn.tuple_offsets:
                raise Refused(f"return of frame slot {i.args[0].v}")
            self.restore_frame()
            if len(i.args) > 0:
                self.push(i.args[0], value_ll(i.args[0].t))
            self.op(0x0F)
        elif op == "ret.none":
            self.restore_frame()
            if self.fn.ret == "dyn":
                raise Refused("dynamic values")
            if self.fn.ret != "None":
                self.i32c(0)
            self.op(0x0F)
        elif op == "br":
            self.goto(i.targets[0], 0)
        elif op == "cbr":
            self.push(i.args[0], "i1")
            self.op(0x04)
            self.op(VOID)
            self.goto(i.targets[0], 1)
            self.op(0x05)
            self.goto(i.targets[1], 1)
            self.op(0x0B)
            self.op(0x00)
        elif op == "check":
            key = i.fields.get("key", "") or i.fields.get("message", "")
            if key not in self.fn.cold:
                raise Refused(f"check without a cold block ({key})")
            self.push(i.args[0], "i1")
            self.op(0x04)
            self.op(VOID)
            self.goto(self.fn.cold[key], 1)
            self.op(0x0B)
            self.goto(i.targets[0], 0)
        elif op == "switch":
            for j in range(1, len(i.args)):
                self.push(i.args[0], "i64")
                self.push(i.args[j], "i64")
                self.op(0x51)
                self.op(0x04)
                self.op(VOID)
                self.goto(i.targets[j], 1)
                self.op(0x0B)
            self.goto(i.targets[0], 0)
        elif op == "raise":
            self.call_import(self.runtime("raise"), i.args)
            self.op(0x00)
        elif op == "throw":
            self.call_import(self.runtime("throw"), i.args)
            self.op(0x00)
        elif op == "exc.match":
            self.call_import(self.runtime("exc.in"), i.args)
            self.op(0x50)  # i64.eqz, i32.eqz: runtime membership != 0
            self.op(0x45)
            self.result(i, 1, "bool")
        elif op == "landing":
            if len(i.args) != 1 or len(i.targets) != 1:
                raise Refused("invalid landing operands or target")
            slot = self.slot_target(i.args[0])
            if self.exception_local < 0:
                raise Refused("landing requires an invoke and an exception slot")
            if i.args[0].v in self.fn.generator_exceptions:
                self.address(i.args[0])
                self.get(self.exception_local)
                self.mem(0x36, 2, 0)
            elif slot >= 0 and self.ltypes[slot] == I32:
                self.get(self.exception_local)
                self.set(slot)
            else:
                raise Refused("landing requires an invoke and an exception slot")
            self.goto(i.targets[0], 0)
        elif op == "unreachable":
            self.op(0x00)
        elif op == "ovf":
            self.overflow(i)
        elif op == "num.cmp" or op == "int.ucmp" or op == "ptr.cmp":
            self.compare(i)
        elif op == "scalar.bin":
            self.binary(i)
        elif op == "scalar.cmp":
            self.scalar_cmp(i)
        elif op == "scalar.cast":
            self.cast(i)
        elif op == "num.cast":
            a = i.args[0]
            if i.t == "int":
                self.push(a, "i1")
                self.op(0xAD)
            elif a.t == "bool":
                self.push(a, "i1")
                self.op(0xB8)  # (f64.convert_i32_u)
            else:
                self.push(a, "i64")
                self.op(0xB9)  # (f64.convert_i64_s)
            self.result(i, 0, i.t)
        elif op == "select":
            ll = value_ll(i.t)
            self.push(i.args[1], ll)
            self.push(i.args[2], ll)
            self.push(i.args[0], "i1")
            self.op(0x1B)
            self.result(i, 0, i.t)
        elif op == "slot.pack":
            a = i.args[0]
            if a.t == "float":
                self.push(a, "double")
                self.op(0xBD)
            elif a.t == "bool":
                self.push(a, "i1")
                self.op(0xAD)
            elif a.t == "int":
                self.push(a, "i64")
            else:
                self.push(a, "ptr")
                self.op(0xAD)
            self.set(self.local(i.res[0], I64))
        elif op == "slot.unpack":
            self.push(i.args[0], "i64")
            if i.t == "float":
                self.op(0xBF)
            elif i.t == "bool" or value_ll(i.t) == "ptr":
                self.op(0xA7)  # i32.wrap_i64
                if i.t == "bool":
                    self.i32c(1)
                    self.op(0x71)  # trunc i64 to i1
            self.result(i, 0, i.t)
        elif op == "mem.load" or op == "mach.load":
            self.load(i)
        elif op == "mem.store" or op == "mach.store":
            self.store(i)
        elif op == "mach.addr":
            self.address(i.args[0])
            element = i.fields.get("element", "")
            if element in ("list.header", "dict.header"):
                members = [lt(t) for t in CONTAINER_HEADERS[element[:-7]]]
                key = i.args[1].v
                if key not in [str(k) for k in range(len(members))]:
                    raise Refused(f"field {key} of {element}")
                self.i32c(self.member_offset(members, int(key)))
            else:
                if element not in ("int", "%ptr", "%byte"):
                    raise Refused(f"mach.addr element {element}")
                self.push(i.args[1], "i64")
                self.op(0xA7)
                self.i32c(access(lt(element))[3])
                self.op(0x6C)
            self.op(0x6A)
            self.set(self.local(i.res[0], I32))
        elif op == "field.addr":
            c = i.args[0].t
            offset = self.field_offset(c, int(i.fields.get("index", "0")))
            self.address(i.args[0])
            self.i32c(offset)
            self.op(0x6A)
            self.set(self.local(i.res[0], I32))
        elif op == "alloc.fixed":
            if i.t.startswith("tuple[") or i.t.startswith("ftuple["):
                size = 8 * tslots(i.t)
            elif i.t in self.m.classes:
                size = self.struct_size(i.t)
            else:
                raise Refused(f"allocation of {i.t}")
            imp = self.alloc_import()
            self.i64c(size)
            self.call_op(0x10)
            uleb(self.code, self.fnindex[imp.sym])
            self.set(self.local(i.res[0], I32))
        elif op == "tuple.load" or op == "tuple.store":
            # a fixed tuple's slot k: an i64 at its address plus 8 k (lowering's tuple.load/store)
            self.address(i.args[0])
            if op == "tuple.load":
                self.mem(0x29, 3, 8 * int(i.fields.get("index", "0")))
                self.set(self.local(i.res[1], I64))
            else:
                self.push(i.args[1], "i64")
                self.mem(0x37, 3, 8 * int(i.fields.get("index", "0")))
        elif op == "vtuple.make":
            # runtime.c's VTuple: its length, a null identity companion (the allocation is
            # zeroed), then each item in an 8-byte slot, stored at its own type (a bool widened)
            p = self.local(i.res[0], I32)
            imp = self.alloc_import()
            self.i64c(8 * (len(i.args) + 2))
            self.call_op(0x10)
            uleb(self.code, self.fnindex[imp.sym])
            self.set(p)
            self.get(p)
            self.i64c(len(i.args))
            self.mem(0x37, 3, 0)
            for k in range(len(i.args)):
                v = i.args[k]
                ll = "i64" if v.t == "bool" else value_ll(v.t)
                self.get(p)
                self.push(v, ll)
                self.mem(access(ll)[1], access(ll)[2], 8 * (k + 2))
        elif op == "list.load":
            self.address(i.args[0])
            self.mem(0x28, 2, 16)  # (List.a: {len, cap, a})
            self.push(i.args[1], "i64")
            self.op(0xA7)
            self.i32c(3)
            self.op(0x74)
            self.op(0x6A)
            self.mem(0x29, 3, 0)
            self.set(self.local(i.res[0], I64))
        elif op == "list.store":
            self.address(i.args[0])
            self.mem(0x28, 2, 16)
            self.push(i.args[1], "i64")
            self.op(0xA7)
            self.i32c(3)
            self.op(0x74)
            self.op(0x6A)
            self.push(i.args[2], "i64")
            self.mem(0x37, 3, 0)
        else:
            raise Refused(f"operation {op}")

    def recursion_op(self, i: Inst, key: str) -> None:
        state = 1  # (global 1: rt.pys_recursion_state's address)
        if key == "recursion.depth":
            self.code.append(0x23)
            uleb(self.code, state)
            self.mem(0x29, 3, 0)
            self.result(i, 0, "int")
        elif key == "recursion.restore":
            self.code.append(0x23)
            uleb(self.code, state)
            self.push(i.args[0], "i64")
            self.mem(0x37, 3, 0)
        elif key == "recursion.enter":
            # the depth; past the limit, RecursionError; else depth + 1, stored and returned.
            # closed recursion (a closed function) restores it at each return, as its callers'
            # depth words in registers do (lowering's rdpass)
            d = self.scratch(I64)
            self.code.append(0x23)
            uleb(self.code, state)
            self.mem(0x29, 3, 0)
            self.set(d)
            self.get(d)
            self.code.append(0x23)
            uleb(self.code, state)
            self.mem(0x29, 3, 8)
            self.op(0x59)  # (i64.ge_s)
            self.op(0x04)
            self.op(VOID)
            self.call_op(0x10)
            uleb(self.code, self.fnindex[self.runtime("recursion.error").sym])
            self.op(0x00)
            self.op(0x0B)
            self.code.append(0x23)
            uleb(self.code, state)
            self.get(d)
            self.i64c(1)
            self.op(0x7C)
            self.mem(0x37, 3, 0)
            if "closed" in self.fn.attrs:
                self.depth_local = d
            self.get(d)
            self.i64c(1)
            self.op(0x7C)
            if len(i.res) > 0:
                self.result(i, 0, "int")
            else:
                self.op(0x1A)
        else:
            raise Refused(f"runtime {key}")

    def restore_frame(self) -> None:
        if self.frame_local >= 0:
            self.get(self.frame_local)
            self.i32c((self.fn.frame_bytes + 15) // 16 * 16)
            self.op(0x6A)
            self.op(0x24)
            uleb(self.code, 2)
        if self.depth_local >= 0:
            self.code.append(0x23)
            uleb(self.code, 1)
            self.get(self.depth_local)
            self.mem(0x37, 3, 0)

    def overflow(self, i: Inst) -> None:
        a = self.local("overflow.left", I64) if self.compact_locals else self.scratch(I64)
        b = self.local("overflow.right", I64) if self.compact_locals else self.scratch(I64)
        v = self.local(i.res[1], I64)
        f = self.local(i.res[2], I32)
        self.push(i.args[0], "i64")
        self.set(a)
        self.push(i.args[1], "i64")
        self.set(b)
        o = i.operator
        if o == "+" or o == "-":
            self.get(a)
            self.get(b)
            self.op(0x7C if o == "+" else 0x7D)
            self.set(v)
            # overflow: the sign of ((a ^ v) & (b ^ v)) for +, ((a ^ b) & (a ^ v)) for -
            self.get(a)
            self.get(v)
            self.op(0x85)
            if o == "+":
                self.get(b)
                self.get(v)
            else:
                self.get(a)
                self.get(b)
            self.op(0x85)
            self.op(0x83)
            self.i64c(0)
            self.op(0x53)  # (i64.lt_s)
            self.set(f)
        elif o == "*":
            self.get(a)
            self.get(b)
            self.op(0x7E)
            self.set(v)
            # a == -1: b == MIN; a == 0: none; else v / a != b
            self.i32c(0)
            self.set(f)
            self.get(a)
            self.op(0x50)  # (i64.eqz)
            self.op(0x45)  # (i32.eqz)
            self.op(0x04)
            self.op(VOID)
            self.get(a)
            self.i64c(-1)
            self.op(0x51)
            self.op(0x04)
            self.op(VOID)
            self.get(b)
            self.i64c(-9223372036854775808)
            self.op(0x51)
            self.set(f)
            self.op(0x05)
            self.get(v)
            self.get(a)
            self.op(0x7F)  # (i64.div_s)
            self.get(b)
            self.op(0x52)
            self.set(f)
            self.op(0x0B)
            self.op(0x0B)
        else:
            raise Refused(f"ovf {o}")

    def compare(self, i: Inst) -> None:
        a = i.args[0]
        o = i.operator
        if i.op == "ptr.cmp":
            self.push(a, "ptr")
            self.push(i.args[1], "ptr")
            self.op(0x46 if o == "==" else 0x47 if o == "!=" else refuse_op(i))
        elif i.op == "int.ucmp":
            self.push(a, "i64")
            self.push(i.args[1], "i64")
            self.op(int_cmp(o, True))
        elif a.t == "float":
            self.push(a, "double")
            self.push(i.args[1], "double")
            self.op(float_cmp(o))
        elif a.t == "int":
            self.push(a, "i64")
            self.push(i.args[1], "i64")
            self.op(int_cmp(o, False))
        else:
            raise Refused(f"num.cmp of {a.t}")
        self.result(i, 0, "bool")

    def binary(self, i: Inst) -> None:
        ll = value_ll(i.args[0].t)
        o = i.operator
        for a in i.args:
            self.push(a, ll)
        table = {"i64": {"add": 0x7C, "sub": 0x7D, "mul": 0x7E, "sdiv": 0x7F, "udiv": 0x80, "srem": 0x81, "urem": 0x82,
                         "and": 0x83, "or": 0x84, "xor": 0x85, "shl": 0x86, "ashr": 0x87, "lshr": 0x88},
                 "i32": {"add": 0x6A, "sub": 0x6B, "mul": 0x6C, "and": 0x71, "or": 0x72, "xor": 0x73, "shl": 0x74},
                 "i1": {"and": 0x71, "or": 0x72, "xor": 0x73},
                 "double": {"fadd": 0xA0, "fsub": 0xA1, "fmul": 0xA2, "fdiv": 0xA3, "fneg": 0x9A}}
        if ll not in table or o not in table[ll] or (o == "fneg") != (len(i.args) == 1):
            raise Refused(f"scalar.bin {o} of {ll}")
        self.op(table[ll][o])
        self.result(i, 0, i.t)

    def cast(self, i: Inst) -> None:
        # LLVM's cast i.operator from the operand's LLVM type to the result's
        a = i.args[0]
        src = value_ll(a.t)
        dst = value_ll(i.t)
        key = f"{i.operator} {src} {dst}"
        table: dict[str, list[int]] = {
            "zext i1 i64": [0xAD], "sext i1 i64": [],
            "zext i8 i64": [0x41, 0xFF, 0x01, 0x71, 0xAD],  # i64.extend_i32_u(x & 255)
            "trunc i64 i1": [0xA7, 0x41, 0x01, 0x71], "trunc i64 i8": [0xA7, 0x41, 0xFF, 0x01, 0x71],
            "trunc i64 i32": [0xA7], "zext i32 i64": [0xAD],
            "sitofp i64 double": [0xB9], "uitofp i1 double": [0xB8], "fptosi double i64": [0xFC, 0x06],
            "bitcast i64 double": [0xBF], "bitcast double i64": [0xBD],
            "ptrtoint ptr i64": [0xAD], "inttoptr i64 ptr": [0xA7],
        }
        # (fptosi: i64.trunc_sat_f64_s, which does not trap where LLVM's result is poison, as
        # llc's lowering does not)
        if key not in table:
            raise Refused(f"scalar.cast {key}")
        self.push(a, src)
        codes = table[key]
        if key == "sext i1 i64":
            # (0 - zext: -1 for true)
            self.op(0xAD)
            k = self.scratch(I64)
            self.set(k)
            self.i64c(0)
            self.get(k)
            self.op(0x7D)
        else:
            for b in codes:
                self.op(b)
        self.result(i, 0, i.t)

    def scalar_cmp(self, i: Inst) -> None:
        ll = value_ll(i.args[0].t)
        o = i.operator
        for a in i.args:
            self.push(a, ll)
        icmp = {"eq": "==", "ne": "!=", "slt": "<", "sle": "<=", "sgt": ">", "sge": ">="}
        ucmp = {"ult": "<", "ule": "<=", "ugt": ">", "uge": ">="}
        if ll == "i64" and o in icmp:
            self.op(int_cmp(icmp[o], False))
        elif ll == "i64" and o in ucmp:
            self.op(int_cmp(ucmp[o], True))
        elif (ll == "i1" or ll == "ptr") and (o == "eq" or o == "ne"):
            self.op(0x46 if o == "eq" else 0x47)
        elif ll == "i32" and o in I32_CMP:
            self.op(I32_CMP[o])  # a C int, such as memcmp's result
        elif ll == "double" and o in FCMP_OPS:
            self.op(FCMP_OPS[o])
        else:
            raise Refused(f"scalar.cmp {o} of {ll}")
        self.result(i, 0, "bool")

    def slot_target(self, a: Operand) -> int:
        # the local of the slot an address operand names, or -1 for a memory address
        if a.v in self.fn.slots:
            return self.locals[a.v]
        return -1

    def load(self, i: Inst) -> None:
        a = i.args[0]
        k = self.slot_target(a)
        ll = value_ll(i.t)
        if k >= 0:
            self.get(k)
        elif a.v.startswith("@") and a.v in self.m.globals:
            self.code.append(0x23)
            uleb(self.code, 0)
            self.mem(access(ll)[0], access(ll)[2], self.addr[a.v])
        else:
            self.address(a)
            self.mem(access(ll)[0], access(ll)[2], 0)
        self.result(i, 0, i.t)

    def store(self, i: Inst) -> None:
        a = i.args[0]
        v = i.args[1]
        k = self.slot_target(a)
        ll = value_ll(v.t)
        if k >= 0:
            self.push(v, wasm_ll(self.ltypes[k], ll))
            self.set(k)
            return
        if a.v.startswith("@") and a.v in self.m.globals:
            self.code.append(0x23)
            uleb(self.code, 0)
            self.push(v, ll)
            self.mem(access(ll)[1], access(ll)[2], self.addr[a.v])
        else:
            self.address(a)
            self.push(v, ll)
            self.mem(access(ll)[1], access(ll)[2], 0)

    # -- class layouts, as wasm32's data layout places their LLVM members --
    def members(self, c: str) -> list[str]:
        if c not in self.m.classes:
            raise Refused(f"layout of {c}")
        d = self.m.classes[c]
        # Older IR reserved a pointer per LP64 header word and copied eight
        # bytes into each. Using that layout on wasm32 overwrites user fields.
        if d.legacy_header:
            raise Refused(f"legacy container header of {c}")
        return [lt(t) for t in d.ftypes] + ["i1" for _ in range(d.nflag)] + ["ptr" for _ in range(d.nbox)]

    def field_offset(self, c: str, k: int) -> int:
        ms = self.members(c)
        if k < 0 or k >= len(ms):
            raise Refused(f"field {k} of {c}")
        return self.member_offset(ms, k)

    def member_offset(self, ms: list[str], k: int) -> int:
        at = 0
        for j in range(k + 1):
            size = access(ms[j])[3]
            at = (at + size - 1) // size * size
            if j < k:
                at += size
        return at

    def struct_size(self, c: str) -> int:
        at = 0
        most = 1
        for t in self.members(c):
            size = access(t)[3]
            at = (at + size - 1) // size * size + size
            most = max(most, size)
        return max(most, (at + most - 1) // most * most)

    def install_callbacks(self) -> None:
        # Start runs once after the data segment is installed. Append the program's
        # passive element segment after the reactor's own C function pointers.
        self.code.extend(b"\xd0\x70")  # ref.null func
        self.i32c(len(self.callbacks))
        self.code.extend(b"\xfc\x0f\x00")  # table.grow 0
        self.local_op(0x21, 0)
        self.get(0)
        self.i32c(-1)
        self.op(0x46)  # i32.eq
        self.code.extend(b"\x04\x40\x00\x0b")  # if growth failed, trap before installing any callback
        self.get(0)
        self.i32c(0)
        self.i32c(len(self.callbacks))
        self.code.extend(b"\xfc\x0c\x00\x00")  # table.init 0 0
        j = 0
        for target in self.callbacks:
            for offset in self.callbacks[target]:
                self.code.extend(b"\x23\x00")  # global.get env.data
                self.get(0)
                self.i32c(j)
                self.op(0x6A)  # i32.add
                self.mem(0x36, 2, offset)  # i32.store
            j += 1
        if self.m.objects:
            self.register_table("pys_wasi_set_object_dispatch", self.object_rows, len(self.m.objects))

    def register_table(self, sym: str, offset: int, count: int) -> None:
        self.code.extend(b"\x23\x00")  # global.get env.data
        self.i32c(offset)
        self.op(0x6A)
        self.i32c(count)
        self.call_op(0x10)
        uleb(self.code, self.fnindex[sym])

    def initializer(self) -> bytearray:
        if self.callbacks:
            self.code = bytearray([1, 1, I32])  # one local for the old table size
            self.install_callbacks()
        else:
            self.code = bytearray([0])
        if self.m.roots:
            # Start hands the reactor the table address. The loader relocates its
            # entries before pys_wasi_run uses them to initialize the collector.
            self.register_table("pys_wasi_set_global_roots", self.root_table, len(self.m.roots))
        if self.guest_roots:
            # Tell the reactor that this module's frames hold its references: it collects only then.
            self.call_op(0x10)
            uleb(self.code, self.fnindex["pys_wasi_set_guest_roots"])
        self.op(0x0B)
        out = bytearray()
        uleb(out, len(self.code))
        out.extend(self.code)
        return out

    # -- the module --
    def module(self) -> bytearray:
        attrs = self.m.attrs
        if "complete" not in attrs:
            raise Refused("a module that does not declare lowering's state (complete)")
        for flag in ("dynamic", "promoting", "rtmode", "extension"):
            if flag in attrs:
                raise Refused(f"module attribute {flag}")
        for table in ("unequal", "crossed", "unsupported"):
            if table in attrs and attrs[table] != "[]":
                raise Refused(f"module attribute {table}")
        self.funcs = generator_functions(self.m, self.generator_targets, self.generator_handles)
        self.rooted = self.rooted_functions()
        self.lay_out_data()
        self.collect_imports()
        tag_type = self.types.of([I32], []) if self.catches else -1
        for sym in self.import_order:
            self.fnindex[sym] = len(self.fnindex)
        own: list[int] = []
        for fn in self.funcs:
            kind = fn.attrs.get("kind", "def")
            callback = kind == "class" and fn.name in self.callbacks
            if (kind not in ("def", "block") and not callback) or "export" in fn.attrs or "extern" in fn.attrs:
                raise Refused(f"function {fn.name} of kind {kind}")
            params = [wasm_type(value_ll(t)) for t in fn.ptypes if t != "None"]
            results: list[int] = [] if fn.ret == "None" else [wasm_type(value_ll(fn.ret))]
            own.append(self.types.of(params, results))
            self.fnindex[fn.name] = len(self.fnindex)
        if "@main.init" not in self.fnindex:
            raise Refused("no @main.init")
        bodies: list[bytearray] = []
        for fn in self.funcs:
            bodies.append(self.function(fn))
        if self.callbacks or self.m.roots or self.guest_roots:
            own.append(self.types.of([], []))
            bodies.append(self.initializer())
        out = bytearray(b"\x00asm\x01\x00\x00\x00")
        section(out, 1, self.types.encode())
        imp = bytearray()
        stack = self.stack_frames or self.catches
        table = self.indirect_calls or len(self.callbacks) != 0
        uleb(imp, 3 + len(self.import_order) + int(stack) + int(self.catches) + int(table))
        name_bytes(imp, "env")
        name_bytes(imp, "memory")
        imp.append(0x02)
        imp.append(0x00)
        uleb(imp, 1)
        name_bytes(imp, "env")
        name_bytes(imp, "data")
        imp.append(0x03)
        imp.append(I32)
        imp.append(0x00)
        name_bytes(imp, "rt")
        name_bytes(imp, "pys_recursion_state")
        imp.append(0x03)
        imp.append(I32)
        imp.append(0x00)
        if stack:
            name_bytes(imp, "rt")
            name_bytes(imp, "__stack_pointer")
            imp.append(0x03)
            imp.append(I32)
            imp.append(0x01)  # mutable global shared with the reactor
        if self.catches:
            name_bytes(imp, "env")
            name_bytes(imp, "pystachy_exception")
            imp.append(0x04)  # tag import
            imp.append(0x00)  # exception tag
            uleb(imp, tag_type)
        if table:
            name_bytes(imp, "rt")
            name_bytes(imp, "__indirect_function_table")
            imp.extend(b"\x01\x70\x00\x01")  # a funcref table, at least one slot (zero is NULL)
        for sym in self.import_order:
            name_bytes(imp, "rt")
            name_bytes(imp, sym)
            imp.append(0x00)
            uleb(imp, self.imports[sym].typ)
        section(out, 2, imp)
        funcs = bytearray()
        uleb(funcs, len(own))
        for t in own:
            uleb(funcs, t)
        section(out, 3, funcs)
        exp = bytearray()
        uleb(exp, 1)
        name_bytes(exp, "init")
        exp.append(0x00)
        uleb(exp, self.fnindex["@main.init"])
        section(out, 7, exp)
        if self.callbacks or self.m.roots or self.guest_roots:
            start = bytearray()
            uleb(start, len(self.import_order) + len(self.funcs))
            section(out, 8, start)
        if self.callbacks:
            elements = bytearray([1, 1, 0])  # one passive segment of function indices
            uleb(elements, len(self.callbacks))
            for target in self.callbacks:
                uleb(elements, self.fnindex[target])
            section(out, 9, elements)
        code = bytearray()
        uleb(code, len(bodies))
        starts: list[int] = []
        for b in bodies:
            starts.append(len(code))
            code.extend(b)
        size = bytearray()
        uleb(size, len(code))
        base = len(out) + 1 + len(size)  # the code section's contents, in the module
        section(out, 10, code)
        data = bytearray()
        uleb(data, 1)
        data.append(0x00)
        data.append(0x23)
        uleb(data, 0)
        data.append(0x0B)
        uleb(data, len(self.data))
        data.extend(self.data)
        section(out, 11, data)
        custom = bytearray()
        name_bytes(custom, "pystachy.data")
        uleb(custom, len(self.data))
        section(out, 0, custom)
        reloc = bytearray()
        name_bytes(reloc, "pystachy.reloc")
        uleb(reloc, len(self.relocs))
        for r in self.relocs:
            uleb(reloc, r)
        section(out, 0, reloc)
        if "exceptions" in attrs:
            marker = bytearray()
            name_bytes(marker, "pystachy.eh")
            section(out, 0, marker)
        lines = self.lines_section(base, starts)
        if len(lines) > 0:
            section(out, 0, lines)
        return out

    def lines_section(self, base: int, starts: list[int]) -> bytearray:
        # pystachy.lines: what a traceback reads (runtime.c) of the frames its host finds, whose
        # offsets in the module are their calls'. Little-endian words: the version (1), the files
        # (a count, then each one's length, its UTF-8 and a NUL), the functions' Python names (as the
        # files), then rows sorted by offset: offset, function, file, line. A line's file index past
        # the last file names the last. Empty where no call has a line or no file is known.
        names: list[str] = []
        rows: list[list[int]] = []
        for j in range(len(self.funcs)):
            sites = self.sites[j]
            if len(sites) == 0:
                continue
            fn = len(names)
            names.append(self.funcs[j].pyname)
            for k in range(0, len(sites), 2):
                line = sites[k + 1]
                rows.append([base + starts[j] + sites[k], fn, min(line // LINES, len(self.m.files) - 1), line % LINES])
        if len(rows) == 0 or len(self.m.files) == 0:
            return bytearray()
        rows.sort()
        out = bytearray()
        name_bytes(out, "pystachy.lines")
        word(out, 1)
        word(out, len(self.m.files))
        for f in self.m.files:
            text = f.encode()
            word(out, len(text))
            out.extend(text)
            out.append(0)
        word(out, len(names))
        for n in names:
            text = n.encode()
            word(out, len(text))
            out.extend(text)
            out.append(0)
        word(out, len(rows))
        for r in rows:
            for v in r:
                word(out, v)
        return out


def key_kind_operand(kind: str) -> Operand:
    digits = kind[1:] if kind.startswith("-") else kind
    if (digits.isascii() and digits.isdigit()) or kind.startswith("ptrtoint (ptr "):
        return Operand("int", kind)
    raise Refused(f"dict/set key kind {kind}")


def is_number(v: str) -> bool:
    # an int or a decimal float's text
    body = v[1:] if v.startswith("-") else v
    if body == "":
        return False
    for c in body:
        if not (c.isdigit() or c == "." or c == "e" or c == "E" or c == "+" or c == "-"):
            return False
    return body[0].isdigit()


def const_size(c: Const) -> int:
    # the bytes that lay_out_data writes for c
    if c.kind == "string":
        return 24 + len(c.text) + 1
    if c.kind == "tuple":
        return 8 * max(1, len(c.items))
    if c.kind == "listdata":
        return 8 * len(c.items)
    if c.kind in ("fieldnames", "callable"):
        return 4 * len(c.refs)
    if c.kind == "exception":
        return 20
    if c.kind == "classrec":
        return 56
    raise Refused(f"constants of kind {c.kind}")


def wasm_ll(wt: int, ll: str) -> str:
    # the LLVM type to push a value of LLVM type ll as, for a local of WebAssembly type wt
    if wt == I64 and ll == "i1":
        return "i64"
    return ll


def float_bytes(value: str) -> bytes:
    # Finite decimal operands and exact IEEE bits share one representation for
    # instruction immediates and constant data (including signed infinities).
    if value.startswith("bitcast (i64 ") and value.endswith(" to double)"):
        return struct.pack("<q", int(value[len("bitcast (i64 "):len(value) - len(" to double)")]))
    if value.startswith("0x"):
        return struct.pack("<Q", int(value[2:], 16))
    if is_number(value):
        return struct.pack("<d", float(value))
    raise Refused(f"a float operand {value}")


def int_cmp(o: str, unsigned: bool) -> int:
    signed = {"==": 0x51, "!=": 0x52, "<": 0x53, ">": 0x55, "<=": 0x57, ">=": 0x59}
    uns = {"==": 0x51, "!=": 0x52, "<": 0x54, ">": 0x56, "<=": 0x58, ">=": 0x5A}
    table = uns if unsigned else signed
    if o not in table:
        raise Refused(f"comparison {o}")
    return table[o]


def float_cmp(o: str) -> int:
    # LLVM's oeq, une, olt, ole, ogt, oge (specs.FCMP) are WebAssembly's f64 comparisons
    table = {"==": 0x61, "!=": 0x62, "<": 0x63, ">": 0x64, "<=": 0x65, ">=": 0x66}
    if o not in table:
        raise Refused(f"comparison {o}")
    return table[o]


def refuse_op(i: Inst) -> int:
    raise Refused(f"{i.op} {i.operator}")


def main() -> None:
    if len(sys.argv) != 3:
        sys.stderr.write("usage: tir_wasm.py MODULE.tir OUT.wasm\n")
        sys.exit(2)
    f = open(sys.argv[1], encoding="utf-8")
    text = f.read()
    f.close()
    try:
        out = Emitter(parse(text), standard_eh(), os.getenv("WASM_GUEST_ROOTS") != "0").module()
    except Refused as e:
        sys.stderr.write(f"tir_wasm: refused: {e.what}\n")
        sys.exit(3)
    g = open(sys.argv[2], "wb")
    g.write(bytes(out))
    g.close()


if __name__ == "__main__":
    main()
