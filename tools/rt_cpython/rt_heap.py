"""A model of machine memory for running runtime.py's memory code on CPython (tools/rtcheck.py).

runtime.py reads and writes runtime.c's records and arrays through _rt's machine primitives,
which nothing checks in a compiled runtime. Here each is checked, so that fuzzing the code on
CPython finds what a compiled run would only corrupt:

- an access outside the block that an allocation gave (the allocator's byte of slack is part
  of the block; blocks are apart, so one past the end is in none);
- a read of bytes that nothing has written (pys_rt_raw zeroes nothing);
- a typed read of a slot that another type last wrote: the three alias rules of
  docs/runtime-in-subset.md, which LLVM's type-based alias analysis relies on. A record's
  fields are read and written as fields (_rt.get, _rt.set, _rt.getp, _rt.setp) and an array's
  words as words (_rt.word, _rt.put); bytes, 32-bit words and the block operations carry no
  type, and neither does what runtime.c writes;
- a sum, difference or product past 64 bits in a function that is @_rt.unchecked, whose
  arithmetic is runtime.c's: undefined there (load() rewrites those functions to check it);
- overlapping _rt.cpy ranges, and sizes below zero.

A fault raises Fault, which is no exception of the runtime's: a test that expects CPython's
outcome reports it as a failure.

Addresses are ints; an _rt.Ptr is an interned object of its address, so that `is` compares
addresses as it does compiled. A str that the memory code made (_rt.as_str) is a Str here: a
view of its header and bytes, whose text() is the CPython str. A CPython str that the memory
code is given is copied into the heap once, with no cached count.
"""
import ast
import bisect
import os
import sys

M64 = (1 << 64) - 1
MIN = -(1 << 63)
MAX = (1 << 63) - 1


class Fault(Exception):
    """Something that a compiled runtime would not notice: a bug in runtime.py's memory code."""


class Ptr:
    __slots__ = ("addr",)

    def __init__(self, addr):
        self.addr = addr

    def __repr__(self):
        return f"<Ptr {self.addr:#x}>"


class Block:
    __slots__ = ("base", "size", "data", "known", "tags", "kind", "name")

    def __init__(self, base, size, kind, name):
        self.base = base
        self.size = size
        self.data = bytearray(size)
        self.known = bytearray(b"\x01" * size if kind != "raw" else size)
        self.tags = [None] * ((size + 7) // 8)
        self.kind = kind  # "scan", "atomic", "raw" (a str's) or "static"
        self.name = name


class Str(str):
    """A str in the heap: its length and bytes are read there when asked for."""
    __slots__ = ("heap", "addr")

    def __len__(self):
        return self.heap.load(self.addr, 8, "length")

    def text(self):
        n = len(self)
        return bytes(self.heap.read(self.addr + 24, n)).decode("latin-1")

    def __repr__(self):
        return f"<Str {self.addr:#x}>"


def signed(x):
    x &= M64
    return x - (1 << 64) if x >> 63 else x


class Heap:
    def __init__(self, records):
        self.records = {name: spec.split() for name, spec in records.items()}
        self.reset()

    def reset(self):
        self.bases = []
        self.blocks = {}
        self.ptrs = {0: Ptr(0)}
        self.next = 0x10000
        self.strs = {}
        self.allocated = 0

    # ---- addresses
    def P(self, addr):
        addr &= M64
        p = self.ptrs.get(addr)
        if p is None:
            p = self.ptrs[addr] = Ptr(addr)
        return p

    def of(self, x):
        # the address of a reference: a Ptr, a heap Str, None, or a CPython str (copied in once)
        if isinstance(x, Ptr):
            return x.addr
        if x is None:
            return 0
        if isinstance(x, Str):
            return x.addr
        if isinstance(x, str):
            return self.str_addr(x)
        raise Fault(f"{x!r} is no reference")

    def new(self, n, kind, name=""):
        if not 0 <= n <= 1 << 40:
            raise MemoryError()
        size = n + 1  # (the allocator's byte of slack)
        base = self.next
        self.next += (size + 15 & ~15) + 32  # (apart: one past a block's end is in no block)
        b = Block(base, size, kind, name)
        self.bases.append(base)
        self.blocks[base] = b
        self.allocated += 1
        return base

    def static(self, words, name):
        # a static array of runtime.c's (a sentinel): its words are part of no allocation's slack
        base = self.next
        self.next += (len(words) * 8 + 15 & ~15) + 32
        b = Block(base, len(words) * 8, "static", name)
        for i, w in enumerate(words):
            b.data[i * 8 : i * 8 + 8] = (w & M64).to_bytes(8, "little")
        self.bases.append(base)
        self.blocks[base] = b
        return base

    def block(self, addr, n, what):
        if n < 0:
            raise Fault(f"{what} of {n} bytes")
        i = bisect.bisect_right(self.bases, addr) - 1
        b = self.blocks[self.bases[i]] if i >= 0 else None
        if b is None or addr + n > b.base + b.size:
            where = f"{addr - b.base} of a block of {b.size} ({b.kind} {b.name})".rstrip() if b is not None and addr < b.base + b.size + 48 else "no block"
            raise Fault(f"{what} of {n} bytes at {addr:#x}: offset {where}")
        return b

    def block_of(self, addr):
        i = bisect.bisect_right(self.bases, addr) - 1
        b = self.blocks[self.bases[i]] if i >= 0 else None
        return b if b is not None and addr < b.base + b.size else None

    # ---- typed loads and stores (tag None: no type)
    def load(self, addr, n, tag, sign=True):
        b = self.block(addr, n, "a read")
        o = addr - b.base
        if b.known[o : o + n] != b"\x01" * n:
            raise Fault(f"a read of {n} bytes at offset {o} of a block of {b.size} ({b.kind}) that nothing wrote")
        if tag is not None:
            if o & 7:
                raise Fault(f"a typed read at offset {o}, which no word starts at")
            have = b.tags[o >> 3]
            if have is not None and have != tag:
                raise Fault(f"a read as {tag} at offset {o} of a block of {b.size} ({b.kind}) of what was written as {have}")
        return int.from_bytes(b.data[o : o + n], "little", signed=sign)

    def store(self, addr, n, value, tag):
        if not isinstance(value, int):
            raise Fault(f"a store of {value!r}, which is no int")
        if tag is not None and not MIN <= value <= MAX:
            raise Fault(f"a store of {value}, which does not fit in 64 bits")
        b = self.block(addr, n, "a write")
        if b.kind == "static" and b.name.startswith("empty"):
            raise Fault(f"a write to the sentinel {b.name}")
        o = addr - b.base
        if tag is not None and o & 7:
            raise Fault(f"a typed write at offset {o}, which no word starts at")
        b.data[o : o + n] = (value & ((1 << 8 * n) - 1)).to_bytes(n, "little")
        b.known[o : o + n] = b"\x01" * n
        for s in range(o >> 3, (o + n + 7) >> 3):
            if s < len(b.tags):
                b.tags[s] = tag

    def read(self, addr, n):
        # n bytes as runtime.c or the test reads them: no type, but they are written ones
        if n == 0:
            return b""
        b = self.block(addr, n, "a read")
        o = addr - b.base
        if b.known[o : o + n] != b"\x01" * n:
            raise Fault(f"a read of {n} bytes at offset {o} of a block of {b.size} ({b.kind}), some of which nothing wrote")
        return bytes(b.data[o : o + n])

    def write(self, addr, data):
        if len(data) == 0:
            return
        b = self.block(addr, len(data), "a write")
        o = addr - b.base
        b.data[o : o + len(data)] = data
        b.known[o : o + len(data)] = b"\x01" * len(data)
        for s in range(o >> 3, (o + len(data) + 7) >> 3):
            if s < len(b.tags):
                b.tags[s] = None

    def words(self, addr, n):
        raw = self.read(addr, n * 8)
        return [int.from_bytes(raw[i * 8 : i * 8 + 8], "little", signed=True) for i in range(n)]

    def copy(self, dst, src, n, overlap):
        if n < 0:
            raise Fault(f"a copy of {n} bytes")
        if n == 0:
            return  # (any addresses: a copy of nothing reads and writes nothing)
        if not overlap and dst != src and dst < src + n and src < dst + n:
            raise Fault(f"_rt.cpy of {n} bytes between overlapping ranges ({dst:#x}, {src:#x}): _rt.move copies those")
        s = self.block(src, n, "a read")
        d = self.block(dst, n, "a write")
        if d.kind == "static" and d.name.startswith("empty"):
            raise Fault(f"a write to the sentinel {d.name}")
        so = src - s.base
        do = dst - d.base
        data = bytes(s.data[so : so + n])
        known = bytes(s.known[so : so + n])
        d.data[do : do + n] = data
        d.known[do : do + n] = known  # (bytes that nothing wrote may be copied: reading them is the fault)
        for t in range(do >> 3, (do + n + 7) >> 3):
            if t < len(d.tags):
                d.tags[t] = None

    # ---- strs
    def str_addr(self, s):
        key = id(s)
        have = self.strs.get(key)
        if have is None:
            have = self.strs[key] = (s, self.new_str(s.encode("latin-1"), 0))
        return have[1]

    def new_str(self, data, chars1):
        # a Str of runtime.c's: length, cached dict hash, cached count of code points + 1 (0: unset)
        a = self.new(24 + len(data), "atomic", "str")
        self.write(a, len(data).to_bytes(8, "little") + bytes(8) + chars1.to_bytes(8, "little") + data + b"\0")
        self.blocks[a].tags[0] = "length"
        return a

    def as_str(self, addr):
        if addr == 0:
            return None
        s = Str("")
        s.heap = self
        s.addr = addr
        return s

    def field(self, spec):
        rec, _, name = spec.partition(".")
        fields = self.records.get(rec)
        if fields is None:
            raise Fault(f"'{spec}' names no record of the runtime (RTRECORDS)")
        for i, f in enumerate(fields):
            if f.rstrip("*") == name:
                return i * 8, f.endswith("*")
        raise Fault(f"'{spec}' is no field of a record of the runtime (RTRECORDS)")


def primitives(heap):
    """_rt's machine primitives on heap, by name."""
    def nil():
        return heap.P(0)

    def ptr(i):
        return heap.P(i)

    def addr(p):
        return signed(heap.of(p))

    def ref(x):
        return heap.P(heap.of(x))

    def as_str(x):
        return x if isinstance(x, str) else heap.as_str(heap.of(x))

    def word(p, i):
        return heap.load(heap.of(p) + 8 * i, 8, "rt.word")

    def put(p, i, v):
        heap.store(heap.of(p) + 8 * i, 8, v, "rt.word")

    def byte_at(p, i):
        return heap.load(heap.of(p) + i, 1, None, False)

    def put_byte(p, i, v):
        heap.store(heap.of(p) + i, 1, v, None)

    def i32_at(p, i):
        return heap.load(heap.of(p) + 4 * i, 4, None)

    def put_i32(p, i, v):
        heap.store(heap.of(p) + 4 * i, 4, v, None)

    def at(p, i):
        return heap.P(heap.of(p) + 8 * i)

    def offset(p, n):
        return heap.P(heap.of(p) + n)

    def tag(spec, pointer):
        return "length" if spec == "Str.len" else "rt.ptr" if pointer else "rt.int"

    def get(p, spec):
        o, pointer = heap.field(spec)
        if pointer:
            raise Fault(f"_rt.get of {spec}, which holds an address")
        return heap.load(heap.of(p) + o, 8, tag(spec, pointer))

    def set_(p, spec, v):
        o, pointer = heap.field(spec)
        if pointer:
            raise Fault(f"_rt.set of {spec}, which holds an address")
        heap.store(heap.of(p) + o, 8, v, tag(spec, pointer))

    def getp(p, spec):
        o, pointer = heap.field(spec)
        if not pointer:
            raise Fault(f"_rt.getp of {spec}, which holds a word")
        return heap.P(heap.load(heap.of(p) + o, 8, tag(spec, pointer), False))

    def setp(p, spec, q):
        o, pointer = heap.field(spec)
        if not pointer:
            raise Fault(f"_rt.setp of {spec}, which holds a word")
        heap.store(heap.of(p) + o, 8, signed(heap.of(q)), tag(spec, pointer))

    def field(p, spec):
        return heap.P(heap.of(p) + heap.field(spec)[0])

    def sizeof(rec):
        if rec not in heap.records:
            raise Fault(f"'{rec}' is no record of the runtime (RTRECORDS)")
        return 8 * len(heap.records[rec])

    def move(d, s, n):
        heap.copy(heap.of(d), heap.of(s), n, True)

    def cpy(d, s, n):
        heap.copy(heap.of(d), heap.of(s), n, False)

    def fill(p, b, n):
        if n < 0:
            raise Fault(f"a fill of {n} bytes")
        heap.write(heap.of(p), bytes([b & 255]) * n)

    def cmp(a, b, n):
        if n < 0:
            raise Fault(f"a comparison of {n} bytes")
        x = heap.read(heap.of(a), n)
        y = heap.read(heap.of(b), n)
        # (memcmp's sign is what C promises: its size is not the bytes' difference everywhere)
        return (x > y) * 77 - (x < y) * 77

    def null(x):
        return x is None or (isinstance(x, Ptr) and x.addr == 0)

    out = dict(nil=nil, ptr=ptr, addr=addr, ref=ref, as_str=as_str, word=word, put=put, byte_at=byte_at, put_byte=put_byte,
               i32_at=i32_at, put_i32=put_i32, at=at, offset=offset, get=get, getp=getp, setp=setp, field=field, sizeof=sizeof,
               move=move, cpy=cpy, fill=fill, cmp=cmp, null=null)
    out["set"] = set_
    return out


def nsw(op, a, b):
    # + - * of a function that is @_rt.unchecked: runtime.c's signed arithmetic, undefined past
    # 64 bits (floats are not its business)
    r = a + b if op == "+" else a - b if op == "-" else a * b
    if type(r) is int and not MIN <= r <= MAX:
        raise Fault(f"{a} {op} {b} overflows 64 bits in an @_rt.unchecked function")
    return r


def shift(op, a, n):
    # << and >> there: by the count's low six bits, >> keeping the sign
    n &= 63
    return signed(a << n) if op == "<<" else signed(a) >> n


class Unchecked(ast.NodeTransformer):
    """Rewrite the arithmetic of @_rt.unchecked functions to what it is compiled: nsw and shift."""
    OPS = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*"}
    SHIFTS = {ast.LShift: "<<", ast.RShift: ">>"}

    def __init__(self):
        self.on = False

    def visit_FunctionDef(self, node):
        was = self.on
        self.on = any(isinstance(d, ast.Attribute) and d.attr == "unchecked" for d in node.decorator_list)
        self.generic_visit(node)
        self.on = was
        return node

    def call(self, name, op, a, b, at):
        f = ast.Attribute(ast.Name("_rt", ast.Load()), name, ast.Load())
        return ast.copy_location(ast.Call(f, [ast.Constant(op), a, b], []), at)

    def visit_BinOp(self, node):
        self.generic_visit(node)
        if self.on and type(node.op) in self.OPS:
            return self.call("nsw", self.OPS[type(node.op)], node.left, node.right, node)
        if self.on and type(node.op) in self.SHIFTS:
            return self.call("shift", self.SHIFTS[type(node.op)], node.left, node.right, node)
        return node

    def visit_UnaryOp(self, node):
        self.generic_visit(node)
        if self.on and isinstance(node.op, ast.USub) and not isinstance(node.operand, ast.Constant):
            return self.call("nsw", "-", ast.Constant(0), node.operand, node)
        return node

    def visit_AugAssign(self, node):
        self.generic_visit(node)
        if self.on and isinstance(node.target, ast.Name) and (type(node.op) in self.OPS or type(node.op) in self.SHIFTS):
            read = ast.copy_location(ast.Name(node.target.id, ast.Load()), node)
            if type(node.op) in self.OPS:
                value = self.call("nsw", self.OPS[type(node.op)], read, node.value, node)
            else:
                value = self.call("shift", self.SHIFTS[type(node.op)], read, node.value, node)
            return ast.copy_location(ast.Assign([node.target], value), node)
        return node


def load(path, name="runtime"):
    """runtime.py as a CPython module whose @_rt.unchecked functions check their arithmetic."""
    import types
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read(), path)
    tree = ast.fix_missing_locations(Unchecked().visit(tree))
    mod = types.ModuleType(name)
    mod.__file__ = os.path.abspath(path)
    sys.modules[name] = mod
    exec(compile(tree, path, "exec"), mod.__dict__)
    return mod


class CSide:
    """What runtime.py's memory code calls in runtime.c, on a Heap: the allocators, the lists'
    sentinels, the kind of an item array, the opt-in test and the identity companions' boxes.
    It reads and writes as C does, with no type that runtime.py's analysis knows."""
    LEN, CAP, A, IDS = 0, 8, 16, 24

    def __init__(self, heap, opt_in=0):
        self.heap = heap
        self.opt = opt_in
        self.setup()

    def setup(self):
        h = self.heap
        self.empty_list = h.static([0], "empty_list")
        self.empty_atomic = h.static([0], "empty_atomic")
        self.empty_inline = h.static([0], "empty_inline")
        self.empty_ids = {k: h.static([k], "empty_identity") for k in (1, 2, 3, 9, 10)}
        self.boxes = {}

    # ---- raw words
    def w(self, addr):
        return int.from_bytes(self.heap.read(addr, 8), "little", signed=True)

    def put(self, addr, v):
        self.heap.write(addr, (v & M64).to_bytes(8, "little"))

    # ---- what runtime.py declares
    def pys_alloc(self, n):
        return self.heap.P(self.heap.new(n, "scan"))

    def pys_alloc_atomic(self, n):
        return self.heap.P(self.heap.new(n, "atomic"))

    def pys_rt_raw(self, n):
        return self.heap.P(self.heap.new(n, "raw"))

    def pys_rt_oom(self):
        raise MemoryError()

    def pys_rt_opt_in(self):
        return self.opt

    def pys_rt_empty_list(self):
        return self.heap.P(self.empty_list)

    def pys_rt_empty_atomic(self):
        return self.heap.P(self.empty_atomic)

    def pys_rt_empty_inline(self):
        return self.heap.P(self.empty_inline)

    def empty_identity(self, kind):
        if kind & 8:
            return self.empty_ids[9 if kind & 3 == 1 else 10]
        return self.empty_ids[1 if kind & 3 == 1 else 2 if kind & 3 == 2 else 3]

    def pys_rt_empty_identity(self, kind):
        return self.heap.P(self.empty_identity(kind))

    def pys_rt_atomic_items(self, a):
        addr = self.heap.of(a)
        if addr == self.empty_atomic:
            return 1
        b = self.heap.block_of(addr)
        return int(b is not None and b.kind == "atomic")

    def box(self, value):
        a = self.heap.new(16, "atomic", "box")
        self.boxes[a] = value
        return a

    def list_box(self, value, kind):
        if not self.opt:
            raise Fault("list_box in a program that does not opt in")
        if kind & 8:
            raise Fault("the model has no optional numeric slots")
        return 0 if kind & 3 == 3 else self.box(value)

    def pys_rt_list_box(self, value, kind):
        return self.list_box(value, kind)

    def big_list(self, l):
        ids = self.w(l + self.IDS)
        return int(ids != 0 and self.w(ids) & 3 == 3)

    def pys_rt_big_list(self, l):
        return self.big_list(self.heap.of(l))

    def list_identity(self, l, kind):
        # runtime.c's pys_list_identity and list_identity_slow
        ids = self.w(l + self.IDS)
        if ids != 0 and not self.w(ids) & 4 and not (kind & 3 == 1 and self.big_list(l)):
            return
        if not self.opt:
            raise Fault("list_identity_slow in a program that does not opt in")
        n = self.w(l + self.LEN)
        cap = self.w(l + self.CAP)
        if self.big_list(l) and kind & 3 == 1:
            if cap == 0:
                self.put(l + self.IDS, self.empty_ids[1])
                return
            a = self.w(l + self.A)
            for i in range(n):
                m = self.w(ids + 8 * (i + 1)) if self.w(a + 8 * i) == MIN else 0
                self.put(ids + 8 * (i + 1), self.box(("big", m) if m else self.w(a + 8 * i)))
            self.put(ids, 1)
            return
        if ids == 0:
            ids = self.heap.new((cap + 1) * 8, "scan", "ids")
            self.put(ids, kind & 11)
            self.put(l + self.IDS, ids)
        a = self.w(l + self.A)
        for i in range(n):
            if self.w(ids + 8 * (i + 1)) == 0:
                self.put(ids + 8 * (i + 1), self.list_box(self.w(a + 8 * i), self.w(ids)))
        self.put(ids, self.w(ids) & 11)

    def pys_list_identity(self, l, kind):
        self.list_identity(self.heap.of(l), kind)

    def pys_rt_identity_pair(self, a, b):
        a = self.heap.of(a)
        b = self.heap.of(b)
        ai = self.w(a + self.IDS)
        bi = self.w(b + self.IDS)
        if (ai or bi) and self.opt:
            kind = self.w(ai) if ai else self.w(bi)
            if (ai and self.w(ai) & 11 == 1) or (bi and self.w(bi) & 11 == 1):
                kind = 1
            if kind & 3 == 3:
                if bi:
                    self.list_identity(a, kind)
                return
            self.list_identity(a, kind)
            self.list_identity(b, kind)

    NAMES = ("pys_alloc pys_alloc_atomic pys_rt_raw pys_rt_oom pys_rt_opt_in pys_rt_empty_list pys_rt_empty_atomic "
             "pys_rt_empty_inline pys_rt_empty_identity pys_rt_atomic_items pys_rt_list_box pys_rt_big_list "
             "pys_rt_identity_pair pys_list_identity").split()

    def install(self, module):
        # give module (runtime.py, loaded) these in place of its declarations
        for name in self.NAMES:
            if not hasattr(module, name):
                raise Fault(f"runtime.py declares no {name}")
            setattr(module, name, getattr(self, name))
