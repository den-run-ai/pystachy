"""Compile a typed-IR module's text to a WebAssembly module, without LLVM (wasm/README.md).

    tir_wasm.py MODULE.tir OUT.wasm

MODULE.tir is a module as tools/typed_ir_text.py prints a typed-after snapshot (`complete`). The
module written imports the shared runtime, runtime.wasm (wasm/build.sh runtime-wasm): its memory
(env.memory), the base of the block that the loader allocates for this module's data (env.data,
an i32 global), the runtime functions it calls (rt.SYMBOL) and the recursion state's address
(rt.pys_recursion_state). It exports its module code as `init`; wasm/run.mjs --runtime loads both.
Its custom section `pystachy.data` holds the data block's size, which the loader reads first.

Each typed-IR value is a WebAssembly local of its LLVM type's WebAssembly type (i64, f64, or i32
for i1, i8, i32 and pointers); a slot whose address only loads and stores read is a local too.
A function's blocks are laid out in order inside nested blocks and a loop: a branch forward to
a block is a br to its label, a branch backward sets the next block's index and continues the
loop, whose br_table dispatches it. A phi's values are assigned on each edge, all read first.

It lowers what the first version needs (wasm/README.md's cuts): no exception handlers, no
generators, no function values, no dynamic values or class dispatchers, no collector roots (the
runtime's collector is off). Anything else it refuses by name: it exits with status 3 after one
line `tir_wasm: refused: WHAT` on stderr, and wasm/build.sh then compiles the program through
LLVM. Run it as PYTHONPATH=. python3 wasm/tir_wasm.py, or compiled: PYSTACHY_PATH=. ./pystachy
build wasm/tir_wasm.py, from the repository root (it reads the compiler's RUNTIME table).
"""
import struct
import sys

from src.pystachy_compiler.specs import RTSYM
from src.pystachy_compiler.utils import RtFn, atomic_dict, atomic_list, lt, rtsym, tslots

I32 = 0x7F
I64 = 0x7E
F64 = 0x7C
VOID = 0x40


# the C library's functions that RUNTIME declares with i64 lengths (wasm/wasm32_ir.py's SIZED)
SIZED: list[str] = ["memcmp", "memchr", "memmem"]
# machine_ir.WORD_READS: layout reads that load an object's word, by its index
WORD_READS: dict[str, int] = {"union.tag": 0, "dyn.type": 0, "union.payload": 1, "union.raw": 1, "dyn.payload": 1, "dyn.raw": 1}
# LLVM's ordered fcmp predicates and une, as WebAssembly's f64 comparisons
FCMP_OPS: dict[str, int] = {"oeq": 0x61, "une": 0x62, "olt": 0x63, "ogt": 0x64, "ole": 0x65, "oge": 0x66}


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
        self.blocks: list[Block] = []
        self.cold: dict[str, str] = {}


class ClassDecl:
    def __init__(self, name: str):
        self.name = name
        self.ftypes: list[str] = []
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
        self.classes: dict[str, ClassDecl] = {}
        self.holes: dict[int, str] = {}
        self.keykinds: dict[str, str] = {}
        self.builtkinds: dict[str, str] = {}
        self.funcs: list[Func] = []


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
            else:
                out.append(e)
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


def fields(text: str, at: int, end: int) -> dict[str, str]:
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
        if k < end and text[k] == "=":
            if text[k + 1] == "[":
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
            if line[at:] != ":":
                raise Refused(f"block {label} has a handler (exceptions)")
            block = Block(label)
            fn.blocks.append(block)
        elif in_function:
            ins = instruction(line)
            if ins.op == "slot":
                if len(fn.blocks) > 0:
                    raise Refused("a slot after the entry")
                fn.slots[ins.res[0]] = ins.t
            else:
                block.code.append(ins)
        else:
            raise Refused(f"unexpected line {line!r}")
    return m


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
        raise Refused(f"{name} is a generator")
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
        if " items=(" in line:
            k = line.index(" items=(")
            c.items, _ = operands(line, k + len(" items="))
            f = fields(line, at, k)
        else:
            f = fields(line, at, len(line))
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
            for item in typed_items(f["fields"]):
                cd.ftypes.append(item)
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
    elif keyword == "runtime" or keyword == "root":
        return
    else:
        raise Refused(f"module declaration {keyword}")


def typed_items(text: str) -> list[str]:
    # fields=[name:type " hidden":type ...]: their types, in order
    out: list[str] = []
    at = 1
    while at < len(text) - 1:
        if text[at] == " ":
            at += 1
            continue
        _, at = atom(text, at, ":")
        t, at = atom(text, at + 1, "")
        out.append(t)
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


# ---------- emission ----------

class Emitter:
    def __init__(self, m: Module):
        self.m = m
        self.types = Types()
        self.imports: dict[str, Import] = {}
        self.import_order: list[str] = []
        self.fnindex: dict[str, int] = {}
        self.data = bytearray()
        self.addr: dict[str, int] = {}
        self.relocs: list[int] = []
        self.recursion = False
        # per function
        self.fn = Func("")
        self.locals: dict[str, int] = {}
        self.ltypes: list[int] = []
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
            if v.v.startswith("0x"):
                self.data.extend(struct.pack("<Q", int(v.v[2:], 16)))
            else:
                self.data.extend(struct.pack("<d", float(v.v)))
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
        f = RtFn(key)
        return self.runtime_sym(f.sym, f.ll)

    def runtime_sym(self, sym: str, ll: list[str]) -> Import:
        if sym in SIZED:
            sym = "pys_wasi_" + sym  # (wasm/wasi_stubs.c's, which take LP64's i64 lengths)
        elif not sym.startswith("pys_"):
            raise Refused(f"runtime symbol {sym}")
        if sym not in self.imports:
            params = [wasm_type(t) for t in ll[1:]]
            results: list[int] = [] if ll[0] == "void" else [wasm_type(ll[0])]
            self.imports[sym] = Import(sym, ll, self.types.of(params, results))
            self.import_order.append(sym)
        return self.imports[sym]

    def collect_imports(self) -> None:
        # every runtime function the functions call, before function indexes are assigned
        for fn in self.m.funcs:
            for b in fn.blocks:
                for i in b.code:
                    if i.op == "rt" and i.fields.get("entry", "").startswith("recursion."):
                        self.recursion = True
                        if i.fields["entry"] == "recursion.enter":
                            self.runtime("recursion.error")
                    elif i.op == "rt" and rtsym_of(self.rt_key(i)) != "fabs":
                        self.runtime(self.rt_key(i))
                    elif i.op == "alloc.fixed" or i.op == "vtuple.make":
                        self.alloc_import()
                    elif i.op == "raise":
                        self.runtime("raise")
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
    def local(self, name: str, wt: int) -> int:
        if name not in self.locals:
            self.locals[name] = len(self.ltypes)
            self.ltypes.append(wt)
        return self.locals[name]

    def scratch(self, wt: int) -> int:
        self.ltypes.append(wt)
        return len(self.ltypes) - 1

    def op(self, b: int) -> None:
        self.code.append(b)

    def get(self, k: int) -> None:
        self.code.append(0x20)
        uleb(self.code, k)

    def set(self, k: int) -> None:
        self.code.append(0x21)
        uleb(self.code, k)

    def i32c(self, v: int) -> None:
        self.code.append(0x41)
        sleb(self.code, v)

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
        if v.startswith("%"):
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
            if v not in self.addr or wt != I32:
                raise Refused(f"symbol {v} as a value")
            self.data_addr(v, 0)
        elif v == "true" or v == "false":
            if wt == I64:
                self.i64c(1 if v == "true" else 0)
            else:
                self.i32c(1 if v == "true" else 0)
        elif v == "null" or v == "zeroinitializer":
            if wt != I32:
                raise Refused(f"null as {ll}")
            self.i32c(0)
        elif v.startswith("ptrtoint (ptr @") and v.endswith(" to i64)") and wt == I64:
            # (a constant's address as an int: a dict's tuple-key descriptor)
            sym = v[len("ptrtoint (ptr "):len(v) - len(" to i64)")]
            if sym not in self.addr:
                raise Refused(f"symbol {sym} as a value")
            self.data_addr(sym, 0)
            self.op(0xAD)
        elif v.startswith("bitcast (i64 ") and v.endswith(" to double)") and wt == F64:
            self.op(0x44)
            self.code.extend(struct.pack("<q", int(v[len("bitcast (i64 "):len(v) - len(" to double)")])))
        elif wt == F64:
            self.op(0x44)
            if v.startswith("0x"):
                self.code.extend(struct.pack("<Q", int(v[2:], 16)))
            elif is_number(v):
                self.code.extend(struct.pack("<d", float(v)))
            else:
                raise Refused(f"a float operand {v}")
        elif not is_number(v) or "." in v or "e" in v:
            raise Refused(f"an operand {v} as {ll}")
        elif wt == I64:
            self.i64c(int(v))
        else:
            self.i32c(int(v))

    def define(self, name: str, t: str) -> int:
        return self.local(name, wasm_type(value_ll(t)))

    def function(self, fn: Func) -> bytearray:
        self.fn = fn
        self.locals = {}
        self.ltypes = []
        self.code = bytearray()
        self.depth_local = -1
        # (a parameter of type None is not passed, as lowering's IFn.ps: its uses read a null local)
        for j in range(len(fn.ptypes)):
            if fn.ptypes[j] != "None":
                self.local(f"%a{j}", wasm_type(value_ll(fn.ptypes[j])))
        self.nparams = len(self.ltypes)
        for j in range(len(fn.ptypes)):
            if fn.ptypes[j] == "None":
                self.local(f"%a{j}", I32)
        for s in fn.slots:
            self.local(s, wasm_type(value_ll(fn.slots[s])))
        self.bindex = {}
        for j in range(len(fn.blocks)):
            self.bindex[fn.blocks[j].label] = j
        self.phis = {}
        for b in fn.blocks:
            for i in b.code:
                if i.op == "phi":
                    self.define(i.res[0], i.t)
                    if b.label not in self.phis:
                        self.phis[b.label] = []
                    self.phis[b.label].append(i)
        n = len(fn.blocks)
        nxt = self.scratch(I32)
        # loop $top; block $b(n-1) ... block $b0; br_table on nxt
        self.op(0x03)
        self.op(VOID)
        for _ in range(n):
            self.op(0x02)
            self.op(VOID)
        self.get(nxt)
        self.op(0x0E)
        uleb(self.code, n)
        for j in range(n):
            uleb(self.code, j)
        uleb(self.code, 0)
        for j in range(n):
            self.op(0x0B)  # (the end of $bj: block j's code follows)
            self.cur = j
            self.block(fn.blocks[j], nxt)
        self.op(0x0B)  # (the loop's end: no block falls out of it)
        self.op(0x00)
        self.op(0x0B)
        body = bytearray()
        extra = self.ltypes[self.nparams:]
        uleb(body, len(extra))
        for wt in extra:
            uleb(body, 1)
            body.append(wt)
        body.extend(self.code)
        out = bytearray()
        uleb(out, len(body))
        out.extend(body)
        return out

    def goto(self, label: str, nxt: int) -> None:
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
        n = len(self.fn.blocks)
        if target > self.cur:
            self.op(0x0C)
            uleb(self.code, target - self.cur - 1)
        else:
            self.i32c(target)
            self.set(nxt)
            self.op(0x0C)
            uleb(self.code, n - 1 - self.cur)

    def block(self, b: Block, nxt: int) -> None:
        for i in b.code:
            self.inst(i, nxt)

    def call_import(self, imp: Import, args: list[Operand]) -> None:
        if len(args) != len(imp.ll) - 1:
            raise Refused(f"call of {imp.sym} with {len(args)} arguments")
        for j in range(len(args)):
            self.push(args[j], imp.ll[j + 1])
        self.op(0x10)
        uleb(self.code, self.fnindex[imp.sym])

    def result(self, i: Inst, k: int, t: str) -> None:
        self.set(self.define(i.res[k], t))

    def address(self, a: Operand) -> None:
        # a computed address (an i32 value)
        self.push(a, "ptr")

    def inst(self, i: Inst, nxt: int) -> None:
        op = i.op
        if op == "phi":
            return
        if op == "rt":
            key = i.fields.get("entry", "")
            if key.startswith("recursion."):
                self.recursion_op(i, key)
                return
            if rtsym_of(self.rt_key(i)) == "fabs":
                self.push(i.args[0], "double")
                self.op(0x99)  # (f64.abs)
                self.result(i, 0, "float")
                return
            imp = self.runtime(self.rt_key(i))
            args = i.args
            hole = int(i.fields.get("hole", "0"))
            if hole > 0 and (key == "dict.new" or key == "set.new"):
                h = self.m.holes.get(hole, "")
                kind = self.m.keykinds.get(h, "0") if h != "" else "0"
                if not kind.lstrip("-").isdigit():
                    raise Refused(f"key kind {kind} of {key}")
                args = [Operand("int", kind)] + args[1:]
            self.call_import(imp, args)
            if imp.ll[0] != "void":
                if len(i.res) == 0:
                    self.op(0x1A)
                else:
                    self.set(self.local(i.res[0], wasm_type(imp.ll[0])))
        elif op == "call":
            callee = i.fields.get("callee", "")
            if callee not in self.fnindex:
                raise Refused(f"call of {callee}")
            for a in i.args:
                if a.t != "None":
                    self.push(a, value_ll(a.t))
            self.op(0x10)
            uleb(self.code, self.fnindex[callee])
            if i.t != "None" and i.t != "":
                if len(i.res) == 0:
                    self.op(0x1A)
                else:
                    self.result(i, 0, i.t)
        elif op == "init":
            callee = "@init." + i.fields.get("module", "")
            if callee not in self.fnindex:
                raise Refused(f"module init {callee}")
            self.op(0x10)
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
            if not kind.lstrip("-").isdigit():
                raise Refused(f"empty.kind of {t}")
            self.address(i.args[0])
            self.i32c(8)
            self.op(0x6A)
            self.set(self.local(i.res[0], I32))
            self.get(self.locals[i.res[0]])
            self.i64c(int(kind))
            self.mem(0x37, 3, 0)
        elif op == "ret":
            self.restore_depth()
            if len(i.args) > 0:
                self.push(i.args[0], value_ll(i.args[0].t))
            self.op(0x0F)
        elif op == "ret.none":
            self.restore_depth()
            if self.fn.ret == "dyn":
                raise Refused("dynamic values")
            if self.fn.ret != "None":
                self.i32c(0)
            self.op(0x0F)
        elif op == "br":
            self.goto(i.targets[0], nxt)
        elif op == "cbr":
            self.push(i.args[0], "i1")
            self.op(0x04)
            self.op(VOID)
            self.cur_if(i.targets[0], nxt)
            self.op(0x05)
            self.cur_if(i.targets[1], nxt)
            self.op(0x0B)
            self.op(0x00)
        elif op == "check":
            key = i.fields.get("key", "") or i.fields.get("message", "")
            if key not in self.fn.cold:
                raise Refused(f"check without a cold block ({key})")
            self.push(i.args[0], "i1")
            self.op(0x04)
            self.op(VOID)
            self.cur_if(self.fn.cold[key], nxt)
            self.op(0x0B)
            self.goto(i.targets[0], nxt)
        elif op == "switch":
            for j in range(1, len(i.args)):
                self.push(i.args[0], "i64")
                self.push(i.args[j], "i64")
                self.op(0x51)
                self.op(0x04)
                self.op(VOID)
                self.cur_if(i.targets[j], nxt)
                self.op(0x0B)
            self.goto(i.targets[0], nxt)
        elif op == "raise":
            self.call_import(self.runtime("raise"), i.args)
            self.op(0x00)
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
                self.op(0xA7)  # (i32.wrap_i64: an i1 is its low bit, a pointer its low word)
            self.result(i, 0, i.t)
        elif op == "mem.load" or op == "mach.load":
            self.load(i)
        elif op == "mem.store" or op == "mach.store":
            self.store(i)
        elif op == "mach.addr":
            self.address(i.args[0])
            self.push(i.args[1], "i64")
            self.op(0xA7)
            self.i32c(access(lt(i.fields.get("element", "int")))[3])
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
            self.op(0x10)
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
            self.op(0x10)
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
        elif op == "list.len":
            self.address(i.args[0])
            self.mem(0x29, 3, 0)
            self.result(i, len(i.res) - 1, "int")
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

    def cur_if(self, label: str, nxt: int) -> None:
        # a goto from inside an if, whose own label adds one to the br's depth
        self.goto(label, nxt)
        fix_last_br(self.code)

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
            self.op(0x10)
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

    def restore_depth(self) -> None:
        if self.depth_local >= 0:
            self.code.append(0x23)
            uleb(self.code, 1)
            self.get(self.depth_local)
            self.mem(0x37, 3, 0)

    def overflow(self, i: Inst) -> None:
        a = self.scratch(I64)
        b = self.scratch(I64)
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
            "trunc i64 i1": [0xA7, 0x41, 0x01, 0x71], "trunc i64 i8": [0xA7, 0x41, 0xFF, 0x01, 0x71],
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
        return [lt(t) for t in d.ftypes] + ["i1" for _ in range(d.nflag)] + ["ptr" for _ in range(d.nbox)]

    def field_offset(self, c: str, k: int) -> int:
        at = 0
        ms = self.members(c)
        for j in range(len(ms)):
            size = access(ms[j])[3]
            at = (at + size - 1) // size * size
            if j == k:
                return at
            at += size
        raise Refused(f"field {k} of {c}")

    def struct_size(self, c: str) -> int:
        at = 0
        most = 1
        for t in self.members(c):
            size = access(t)[3]
            at = (at + size - 1) // size * size + size
            most = max(most, size)
        return max(most, (at + most - 1) // most * most)

    # -- the module --
    def module(self) -> bytearray:
        attrs = self.m.attrs
        if "complete" not in attrs:
            raise Refused("a module that does not declare lowering's state (complete)")
        for flag in ("exceptions", "dynamic", "promoting", "protocol", "rtmode", "extension"):
            if flag in attrs:
                raise Refused(f"module attribute {flag}")
        for table in ("objects", "compared", "hashed", "unequal", "crossed", "unsupported"):
            if table in attrs and attrs[table] != "[]":
                raise Refused(f"module attribute {table}")
        self.lay_out_data()
        self.collect_imports()
        for sym in self.import_order:
            self.fnindex[sym] = len(self.fnindex)
        own: list[int] = []
        for fn in self.m.funcs:
            if fn.attrs.get("kind", "def") not in ("def", "block") or "export" in fn.attrs or "extern" in fn.attrs:
                raise Refused(f"function {fn.name} of kind {fn.attrs.get('kind', 'def')}")
            params = [wasm_type(value_ll(t)) for t in fn.ptypes if t != "None"]
            results: list[int] = [] if fn.ret == "None" else [wasm_type(value_ll(fn.ret))]
            own.append(self.types.of(params, results))
            self.fnindex[fn.name] = len(self.fnindex)
        if "@main.init" not in self.fnindex:
            raise Refused("no @main.init")
        bodies: list[bytearray] = []
        for fn in self.m.funcs:
            bodies.append(self.function(fn))
        out = bytearray(b"\x00asm\x01\x00\x00\x00")
        section(out, 1, self.types.encode())
        imp = bytearray()
        uleb(imp, 2 + len(self.import_order) + 1)
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
        code = bytearray()
        uleb(code, len(bodies))
        for b in bodies:
            code.extend(b)
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
        return out


def rtsym_of(key: str) -> str:
    return rtsym(key)


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
    if c.kind == "fieldnames":
        return 4 * len(c.refs)
    if c.kind == "classrec":
        return 56
    raise Refused(f"constants of kind {c.kind}")


def wasm_ll(wt: int, ll: str) -> str:
    # the LLVM type to push a value of LLVM type ll as, for a local of WebAssembly type wt
    if wt == I64 and ll == "i1":
        return "i64"
    return ll


def fix_last_br(code: bytearray) -> None:
    # the br that goto() wrote last (0x0C, then its depth's LEB, at the end of code): depth + 1
    k = len(code) - 1
    while code[k - 1] & 0x80:
        k -= 1
    depth = 0
    shift = 0
    for j in range(k, len(code)):
        depth |= (code[j] & 0x7F) << shift
        shift += 7
    del code[k:]
    uleb(code, depth + 1)


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
        out = Emitter(parse(text)).module()
    except Refused as e:
        sys.stderr.write(f"tir_wasm: refused: {e.what}\n")
        sys.exit(3)
    g = open(sys.argv[2], "wb")
    g.write(bytes(out))
    g.close()


if __name__ == "__main__":
    main()
