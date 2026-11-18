"""struct's calls of a format known as the program compiles: component of the self-hosting Pystachy compiler."""
from __future__ import annotations
from src.pystachy_compiler.ir import Val
from src.pystachy_compiler.specs import BIG, BYTEARRAYC, BYTEARRAYS
from src.pystachy_compiler.syntax import Node, mk
from src.pystachy_compiler.utils import is_opt, is_tuple, targs, tname

# the functions of _struct (lib/_pystachy_struct.py) whose calls the compiler makes where it knows
# the format (Gen.struct_call), which decides the types of the values
STRUCT_FNS: list[str] = ["_struct$pack", "_struct$unpack", "_struct$unpack_from", "_struct$iter_unpack", "_struct$calcsize", "_struct$pack_into"]
# each format character's size in the native table (x86-64 Linux, LP64), which is its alignment
# too, and in the standard one, which aligns nothing and has no n, N and P (lib/_pystachy_struct.py's)
NATIVE_SIZES: dict[str, int] = {"x": 1, "c": 1, "b": 1, "B": 1, "?": 1, "h": 2, "H": 2, "i": 4, "I": 4, "l": 8, "L": 8,
                                "q": 8, "Q": 8, "n": 8, "N": 8, "e": 2, "f": 4, "d": 8, "s": 1, "p": 1, "P": 8}
STANDARD_SIZES: dict[str, int] = {"x": 1, "c": 1, "b": 1, "B": 1, "?": 1, "h": 2, "H": 2, "i": 4, "I": 4, "l": 4, "L": 4,
                                  "q": 8, "Q": 8, "e": 2, "f": 4, "d": 8, "s": 1, "p": 1}
SSIZE_MAX = 9223372036854775807


class StructFmt:
    # a format of _struct, parsed as CPython's prepare_s parses it: its items but pad bytes, in
    # order (a code, its count, a repeat but for s and p, where it is the length, and the
    # offset of its first value), the struct's size, its byte order and whether it is native
    def __init__(self) -> None:
        self.codes: list[str] = []
        self.counts: list[int] = []
        self.offsets: list[int] = []
        self.size = 0
        self.little = True
        self.native = True
        self.err = ""  # (CPython's struct.error for a format it rejects)

    def itemsize(self, c: str) -> int:
        return NATIVE_SIZES[c] if self.native else STANDARD_SIZES[c]

    def nvalues(self) -> int:
        # the values the format packs and unpacks
        n = 0
        for i in range(len(self.codes)):
            n += 1 if self.codes[i] == "s" or self.codes[i] == "p" else self.counts[i]
        return n


def parse_struct(fmt: str) -> StructFmt:
    # format fmt parsed: the byte order only as its first character, whitespace between items,
    # a decimal count before a code, native alignment before an item
    sf = StructFmt()
    if "\x00" in fmt:
        sf.err = "embedded null character"
        return sf
    i = 0
    n = len(fmt)
    if n > 0 and fmt[0] in "@=<>!":
        sf.native = fmt[0] == "@"
        sf.little = fmt[0] != ">" and fmt[0] != "!"
        i = 1
    size = 0
    while i < n:
        c = fmt[i]
        i += 1
        if c in " \t\n\r\x0b\x0c":
            continue
        num = 1
        if "0" <= c <= "9":
            num = ord(c) - 48
            while i < n and "0" <= fmt[i] <= "9":
                d = ord(fmt[i]) - 48
                if num > (SSIZE_MAX - d) // 10:
                    sf.err = "total struct size too long"
                    return sf
                num = num * 10 + d
                i += 1
            if i >= n:
                sf.err = "repeat count given without format specifier"
                return sf
            c = fmt[i]
            i += 1
        if c not in (NATIVE_SIZES if sf.native else STANDARD_SIZES):
            sf.err = "bad char in struct format"
            return sf
        k = sf.itemsize(c)
        if sf.native and size > 0 and k > 1:
            size += (k - 1) - (size - 1) % k
        if num > (SSIZE_MAX - size) // k:
            sf.err = "total struct size too long"
            return sf
        if c != "x" and (num > 0 or c == "s" or c == "p"):
            sf.codes.append(c)
            sf.counts.append(num)
            sf.offsets.append(size)
        size += num * k
    sf.size = size
    return sf


def gen_struct_format(self, a: Node) -> Node | None:
    # the format a call gives as its first argument, where it is known as the program compiles:
    # a literal, a module's global bound once to one, a Struct's format (a field of a literal
    # class, Gen.const_of); else None
    if a.kind == "bytes":
        return a
    c = self.const_of(a, {}, True)
    if c is None and a.kind == "name" and a.s in self.strglobals and self.globread(a.s):
        c = mk("str", self.strglobals[a.s], a.line, [])
    return c if c is not None and (c.kind == "str" or c.kind == "bytes") else None


def gen_struct_call(self, name: str, args: list[Node], want: str) -> Val | None:
    # struct.pack(), pack_into(), unpack(), unpack_from(), iter_unpack() or calcsize()
    # (lib/_pystachy_struct.py's) of a format known as the program compiles: calls of the module's
    # functions for each item, whose value has the item's type (CPython's s_pack_internal and
    # s_unpack_internal); None for calcsize() of another format, which the module's function
    # parses as the program runs. The buffer that is unpacked is bytes or a bytearray, whose bytes
    # are read in place; pack_into()'s is a bytearray, written in place
    fn = name[name.find("$") + 1 :]
    line = self.line
    pos = [a for a in args if a.kind != "kw"]
    for a in args:
        if a.kind == "kw" and not (fn == "unpack_from" and (a.s == "buffer" or a.s == "offset")):
            self.err(f"{fn}() takes no keyword arguments" if fn != "unpack_from" else f"unpack_from() got an unexpected keyword argument '{a.s}'")
        if a.kind == "dstar" or (a.kind == "starred" and fn != "pack" and fn != "pack_into"):
            self.err(f"struct.{fn}() of unpacked arguments is not supported")
    if len(pos) == 0 or pos[0].kind == "starred":
        self.err(f"struct.{fn}() takes the format as its first argument")
    c = self.struct_format(pos[0])
    if c is None:
        if fn == "calcsize":
            return None
        self.err(f"struct.{fn}() of a format not known as the program compiles is not supported: the format decides the types of the values (a literal, a module's constant or a Struct's format is known)")
    sf = parse_struct(c.s)
    if sf.err != "" and fn == "calcsize":
        return None  # (the module's calcsize() raises CPython's struct.error as the program runs)
    if sf.err != "" and fn == "pack":
        for a in args[1:]:
            self.expr(a.kids[0] if a.kind == "starred" else a, "")
        self.expr(self.struct_helper("calcsize", [pos[0]]), "")  # (CPython's struct.error, once the arguments are evaluated)
        return Val(self.bconst(""), "bytes")
    if sf.err != "":
        self.err(sf.err)  # (CPython's struct.error: the format gives the values no types here)
    self.expr(pos[0], "")  # (the format, as CPython evaluates it)
    if fn == "calcsize":
        if len(args) != 1:
            self.err(f"calcsize() takes exactly one argument ({len(args)} given)")
        return Val(str(sf.size), "int")
    if fn == "pack":
        return self.struct_pack(sf, pos[1:], None, None)
    if fn == "pack_into":
        if len(pos) < 3 or pos[1].kind == "starred" or pos[2].kind == "starred":
            self.err("pack_into() takes the format, the buffer and the offset before the values")
        into = self.expr(pos[1], "")
        if into.t != BYTEARRAYC:  # (CPython's TypeError, as the program compiles: bytes cannot be written)
            self.err(f"argument must be read-write bytes-like object, not {tname(into.t)}")
        o = self.expr(pos[2], "int")
        if o.t != "int" and o.t != "bool" and o.t != BIG:
            self.err(f"'{tname(o.t)}' object cannot be interpreted as an integer")
        return self.struct_pack(sf, pos[3:], into, self.as_int(o))
    buf: Node | None = pos[1] if len(pos) > 1 else None
    off: Node | None = pos[2] if len(pos) > 2 else None
    for a in args:
        if a.kind == "kw" and a.s == "buffer":
            buf = a.kids[0]
        elif a.kind == "kw":
            off = a.kids[0]
    nmax = 3 if fn == "unpack_from" else 2
    if buf is None:
        self.err(f"{fn}() missing required argument 'buffer' (pos 2)")
    if len(args) > nmax:
        self.err(f"{fn}() takes at most {nmax} arguments ({len(args)} given)")
    b = self.expr(buf, "bytes")
    if b.t != "bytes" and b.t != BYTEARRAYC:
        self.err(f"a bytes-like object is required, not '{tname(b.t)}'")
    ln = self.vnode(b)  # (what the module's _need, _offset and _offsets measure)
    bn = ln  # (the bytes that are read)
    if b.t == BYTEARRAYC:
        # a bytearray's bytes are read in place: its buffer's, within the length that was checked
        bn = self.vnode(self.call_fn(self.funcs[BYTEARRAYS + "$_raw"], [], [ln]))
    sz = mk("int", str(sf.size), line, [])
    if fn == "unpack":
        self.expr(self.struct_helper("_need", [ln, sz]), "")
        return self.tuple_([self.expr(e, "") for e in self.struct_nodes(sf, bn, None)])
    if fn == "unpack_from":
        o = self.expr(off, "int") if off is not None else Val("0", "int")
        if o.t != "int" and o.t != "bool" and o.t != BIG:
            self.err(f"'{tname(o.t)}' object cannot be interpreted as an integer")
        at = self.expr(self.struct_helper("_offset", [ln, self.vnode(self.as_int(o)), sz]), "int")
        return self.tuple_([self.expr(e, "") for e in self.struct_nodes(sf, bn, self.vnode(at))])
    # iter_unpack(): the list of the tuples, where CPython gives an iterator of them
    starts = self.expr(self.struct_helper("_offsets", [ln, sz]), "list[int]")
    item = mk("name", "__offset", line, [])
    return self.expr(mk("listcomp", "", line, [mk("tuple", "", line, self.struct_nodes(sf, bn, item)), item, self.vnode(starts)]), want)


def gen_struct_store(self, dst: Node, base: Node, k: int, p: Val) -> None:
    # pack_into()'s store of the bytes p at offset base + k of bytearray dst, within it (the
    # module's _into checked the struct's size there): lib/_pystachy_bytearray.py's _store
    at = base if k == 0 else mk("binop", "+", self.line, [base, mk("int", str(k), self.line, [])])
    self.call_fn(self.funcs[BYTEARRAYS + "$_store"], [], [dst, at, self.vnode(p)])


def gen_struct_helper(self, f: str, args: list[Node]) -> Node:
    # a call of lib/_pystachy_struct.py's function f
    return mk("call", "", self.line, [mk("name", "_struct$" + f, self.line, [])] + args)


def gen_struct_nodes(self, sf: StructFmt, bn: Node, base: Node | None) -> list[Node]:
    # the calls that unpack the values of format sf from the bytes of bn, each at its offset (plus
    # base, a node of an int, where given)
    line = self.line
    little = mk("True" if sf.little else "False", "", line, [])
    out: list[Node] = []
    for i in range(len(sf.codes)):
        c = sf.codes[i]
        k = sf.itemsize(c)
        for r in range(1 if c == "s" or c == "p" else sf.counts[i]):
            at: Node = mk("int", str(sf.offsets[i] + r * k), line, [])
            if base is not None:
                at = mk("binop", "+", line, [base, at])
            if c == "s" or c == "c":
                out.append(self.struct_helper("_unpack_bytes", [bn, at, mk("int", str(sf.counts[i]) if c == "s" else "1", line, [])]))
            elif c == "p":
                out.append(self.struct_helper("_unpack_pascal", [bn, at, mk("int", str(sf.counts[i]), line, [])]))
            elif c == "?":
                out.append(self.struct_helper("_unpack_bool", [bn, at]))
            elif c == "e" or c == "f" or c == "d":
                out.append(self.struct_helper("_unpack_float", [mk("str", c, line, []), bn, at, little]))
            else:
                signed = mk("True" if c in "bhilqn" else "False", "", line, [])  # (P unpacks as unsigned)
                out.append(self.struct_helper("_unpack_int", [bn, at, mk("int", str(k), line, []), signed, little]))
    return out


def gen_struct_pack(self, sf: StructFmt, args: list[Node], into: Val | None, offset: Val | None) -> Val:
    # pack(format, *values) of format sf: the values evaluated in order, then each item's bytes,
    # with pad bytes and native alignment between them. pack_into(format, into, offset, *values):
    # as CPython's s_pack_into, the offset checked once the values are evaluated, the struct's
    # bytes of the bytearray zeroed, then each item's stored in its turn, so that an item that
    # raises leaves those before it written
    line = self.line
    vals: list[Val] = []
    for a in args:
        if a.kind == "starred":
            t = self.expr(a.kids[0], "")
            if not is_tuple(t.t):
                self.err(f"struct.pack() of *{tname(t.t)} is not supported: of a tuple whose length is known as the program compiles, it is")
            tn = self.vnode(t)
            for i in range(len(targs(t.t))):
                vals.append(self.expr(mk("index", "", line, [tn, mk("int", str(i), line, [])]), ""))
        else:
            vals.append(self.expr(a, ""))
    n = sf.nvalues()
    if len(vals) != n:
        self.err(f"{'pack' if into is None else 'pack_into'} expected {n} items for packing (got {len(vals)})")
    little = mk("True" if sf.little else "False", "", line, [])
    dst: Node | None = None
    base: Node | None = None
    if into is not None and offset is not None:
        dst = self.vnode(into)
        base = self.vnode(self.expr(self.struct_helper("_into", [dst, self.vnode(offset), mk("int", str(sf.size), line, [])]), "int"))
        if sf.size > 0:
            self.struct_store(dst, base, 0, Val(self.bconst("\x00" * sf.size), "bytes"))
    parts: list[Val] = []
    done = 0  # (the bytes so far)
    j = 0
    for i in range(len(sf.codes)):
        c = sf.codes[i]
        k = sf.itemsize(c)
        if sf.offsets[i] > done and dst is None:
            parts.append(Val(self.bconst("\x00" * (sf.offsets[i] - done)), "bytes"))
        for r in range(1 if c == "s" or c == "p" else sf.counts[i]):
            v = vals[j]
            j += 1
            if is_opt(v.t) and c != "?":
                self.err(f"struct.pack() of a value that may be None ({tname(v.t)}) is not supported")
            vn = self.vnode(v)
            if c == "s" or c == "p":
                if v.t != "bytes":
                    self.err(f"argument for '{c}' must be a bytes object")
                e = self.struct_helper("_pack_bytes", [vn, mk("int", str(sf.counts[i]), line, []), mk("True" if c == "p" else "False", "", line, [])])
            elif c == "c":
                if v.t != "bytes":
                    self.err("char format requires a bytes object of length 1")
                e = self.struct_helper("_pack_char", [vn])
            elif c == "?":
                e = self.struct_helper("_pack_bool", [self.vnode(Val(self.truth(v), "bool"))])
            elif c == "e" or c == "f" or c == "d":
                if v.t != "float" and v.t != "int" and v.t != "bool" and v.t != BIG:
                    self.err("required argument is not a float")
                x = self.as_float(v)
                e = self.struct_helper("_pack_float", [mk("str", c, line, []), self.vnode(x), little])
            else:
                if v.t != "int" and v.t != "bool" and v.t != BIG:
                    self.err("required argument is not an integer")  # (a promoting int: as_int narrows it)
                signed = mk("True" if c in "bhilqnP" else "False", "", line, [])  # (P packs any int, as CPython's PyLong_AsVoidPtr does)
                if dst is not None and base is not None:
                    # (pack_into()'s integer: its bytes stored as they are made, once its range is checked)
                    checked = self.struct_helper("_check_int", [mk("str", c, line, []), self.vnode(self.as_int(v)), mk("int", str(k), line, []), signed])
                    at = base if sf.offsets[i] + r * k == 0 else mk("binop", "+", line, [base, mk("int", str(sf.offsets[i] + r * k), line, [])])
                    self.call_fn(self.funcs[BYTEARRAYS + "$_store_int"], [], [dst, at, checked, mk("int", str(k), line, []), little])
                    continue
                e = self.struct_helper("_pack_int", [mk("str", c, line, []), self.vnode(self.as_int(v)), mk("int", str(k), line, []), signed, little])
            if dst is not None and base is not None:
                self.struct_store(dst, base, sf.offsets[i] + r * k, self.expr(e, "bytes"))
            else:
                parts.append(self.expr(e, "bytes"))
        done = sf.offsets[i] + (sf.counts[i] if c == "s" or c == "p" else sf.counts[i] * k)
    if dst is not None:
        return Val("null", "None")
    if sf.size > done:
        parts.append(Val(self.bconst("\x00" * (sf.size - done)), "bytes"))
    if len(parts) == 0:
        return Val(self.bconst(""), "bytes")
    out = parts[0]
    for p in parts[1:]:
        out = Val(self.rt("pys_bytes_add", "ptr", [f"ptr {out.v}", f"ptr {p.v}"]), "bytes")
    return out
