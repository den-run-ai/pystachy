"""Adapt the compiler's LLVM IR to wasm32 (wasm/README.md): python3 wasm/wasm32_ir.py IN.ll OUT.ll

The compiler's constants hold an object's address as a 64-bit int where runtime.c's slots are
64 bits (a tuple constant's items: `[2 x i64] [i64 ptrtoint (ptr @s.1 to i64), ...]`). WebAssembly's
object files relocate a 32-bit address only, so llc refuses such an initializer. On wasm32 the
address zero-extended is the same 8 bytes as `<{ptr @s.1, i32 0}>` (little-endian), which it can
relocate: each such item becomes that, its aggregate's type follows (an array whose items now
differ becomes a packed struct of the same layout), and nothing else changes. Code reads these
constants by its own types (opaque pointers), not by the global's.
It also renames the program's main for WASI's C library, which calls a main of argc and argv as
__main_argc_argv (clang renames C's), and its calls of the C library functions whose lengths it
declares as i64 (SIZED).
"""
import sys

ADDRESS = "<{ptr, i32}>"


class Parser:
    def __init__(self, text: str):
        self.text = text
        self.at = 0

    def space(self) -> None:
        while self.at < len(self.text) and self.text[self.at] == " ":
            self.at += 1

    def peek(self, token: str) -> bool:
        self.space()
        return self.text.startswith(token, self.at)

    def take(self, token: str) -> None:
        if not self.peek(token):
            raise ValueError(f"expected {token!r} at {self.text[self.at:self.at + 40]!r}")
        self.at += len(token)

    def word(self) -> str:
        # a type name, value or keyword: up to a delimiter (a quoted name or c"..." whole)
        self.space()
        start = self.at
        while self.at < len(self.text) and self.text[self.at] not in " ,{}[]()<>":
            if self.text[self.at] == '"':
                self.at = self.text.index('"', self.at + 1)
            self.at += 1
        if self.at == start:
            raise ValueError(f"expected a word at {self.text[self.at:self.at + 40]!r}")
        return self.text[start:self.at]

    def balanced(self) -> str:
        # a parenthesized group, whole: a constant expression's operands
        self.space()
        start = self.at
        depth = 0
        while True:
            c = self.text[self.at]
            if c == '"':
                self.at = self.text.index('"', self.at + 1)
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    self.at += 1
                    return self.text[start:self.at]
            self.at += 1

    def type(self) -> str:
        self.space()
        if self.peek("<{"):
            self.take("<{")
            items = self.list_of(self.type, "}>")
            return "<{" + ", ".join(items) + "}>"
        if self.peek("{"):
            self.take("{")
            items = self.list_of(self.type, "}")
            return "{" + ", ".join(items) + "}"
        if self.peek("["):
            self.take("[")
            n = self.word()
            self.take("x")
            item = self.type()
            self.take("]")
            return f"[{n} x {item}]"
        return self.word()

    def list_of(self, item, close: str) -> list:
        items = []
        if self.peek(close):
            self.take(close)
            return items
        while True:
            items.append(item())
            if self.peek(","):
                self.take(",")
                continue
            self.take(close)
            return items

    def typed(self) -> tuple:
        # (type, value) of a typed constant, with its items' addresses rewritten
        t = self.type()
        return rewrite(t, self.value(t))

    def value(self, t: str):
        # a constant's value: a list of typed items for an aggregate, else its text
        self.space()
        for open_, close in (("<{", "}>"), ("{", "}"), ("[", "]")):
            if self.peek(open_) and (t.startswith(open_) or open_ == "[" and t.startswith("[")):
                self.take(open_)
                return self.list_of(self.typed, close)
        w = self.word()
        if self.peek("("):
            return w + " " + self.balanced()
        if w in ("getelementptr", "inbounds"):
            raise ValueError("a constant expression without operands")
        return w


def address(v) -> str:
    # the pointer operand of `ptrtoint (ptr X to i64)`, or "" for any other value
    if isinstance(v, str) and v.startswith("ptrtoint (ptr ") and v.endswith(" to i64)"):
        return v[len("ptrtoint (ptr "):-len(" to i64)")]
    return ""


def split_types(inner: str) -> list:
    # the member types of a struct type's text between its braces
    p = Parser(inner + "}")
    return p.list_of(p.type, "}")


def layout(t: str) -> tuple:
    # (size, alignment) of an LLVM type under wasm32's data layout
    if t == "ptr" or t == "float":
        return 4, 4
    if t == "double":
        return 8, 8
    if t.startswith("i") and t[1:].isdigit():
        n = (int(t[1:]) + 7) // 8
        size = 1 if n <= 1 else 2 if n <= 2 else 4 if n <= 4 else 8 if n <= 8 else n
        return size, min(size, 8)
    if t.startswith("["):
        p = Parser(t)
        p.take("[")
        n = int(p.word())
        p.take("x")
        size, align = layout(p.type())
        return n * size, align
    if t.startswith("<{"):
        return sum([layout(m)[0] for m in split_types(t[2:-2])]), 1
    if t.startswith("{"):
        offsets, size, align = struct_layout(split_types(t[1:-1]))
        return size, align
    raise ValueError(f"no layout for {t}")


def struct_layout(members: list) -> tuple:
    # (each member's offset, the size, the alignment) of a struct (not packed) of members
    at, most, offsets = 0, 1, []
    for m in members:
        size, align = layout(m)
        at = (at + align - 1) // align * align
        offsets.append(at)
        at += size
        most = max(most, align)
    return offsets, (at + most - 1) // most * most, most


def rewrite(t: str, v) -> tuple:
    if t == "i64" and address(v) != "":
        return ADDRESS, "<{ptr " + address(v) + ", i32 0}>"
    if not isinstance(v, list):
        return t, v
    types = [item[0] for item in v]
    body = ", ".join([f"{item[0]} {item[1]}" for item in v])
    if t.startswith("["):
        if all(item[0] == types[0] for item in v) and (len(v) == 0 or f" x {types[0]}]" in t):
            return t, f"[{body}]"
        # (every item is 8 bytes, as the array's i64s were: packed, at the same offsets)
        return "<{" + ", ".join(types) + "}>", "<{" + body + "}>"
    if t.startswith("<{"):
        return "<{" + ", ".join(types) + "}>", "<{" + body + "}>"
    old = split_types(t[1:-1])
    if old == types:
        return t, "{" + body + "}"
    # A member changed to the packed address, whose alignment is 1: a packed struct with the
    # padding that puts each member where the struct placed it (and its size)
    offsets, size, _ = struct_layout(old)
    ts, vs, at = [], [], 0
    for j in range(len(v)):
        if offsets[j] > at:
            ts.append(f"[{offsets[j] - at} x i8]")
            vs.append(f"[{offsets[j] - at} x i8] zeroinitializer")
        ts.append(v[j][0])
        vs.append(f"{v[j][0]} {v[j][1]}")
        at = offsets[j] + layout(old[j])[0]
    if size > at:
        ts.append(f"[{size - at} x i8]")
        vs.append(f"[{size - at} x i8] zeroinitializer")
    return "<{" + ", ".join(ts) + "}>", "<{" + ", ".join(vs) + "}>"


# the C library's functions that the compiler declares with LP64's i64 lengths (a size_t), which
# wasm/wasi_stubs.c's pys_wasi_* take and convert: a call of wasm32's 32-bit ones would trap
SIZED = ("memcmp", "memchr", "memmem")


def line_of(line: str) -> str:
    for name in SIZED:
        line = line.replace(f"@{name}(", f"@pys_wasi_{name}(")
    if line.startswith("define i32 @main(i32 %argc, ptr %argv)"):
        return "define i32 @__main_argc_argv(i32 %argc, ptr %argv)" + line[len("define i32 @main(i32 %argc, ptr %argv)"):]
    if not line.startswith("@") or "ptrtoint (ptr " not in line or " to i64)" not in line:
        return line
    for kind in (" constant ", " global "):
        k = line.find(kind)
        if k < 0 or line.find(" = ") > k:
            continue
        p = Parser(line[k + len(kind):])
        t, v = p.typed()
        rest = p.text[p.at:]
        if t != ADDRESS and t.startswith("<{") and " align " not in rest:
            rest = ", align 8" + rest  # (a packed struct's own alignment is 1)
        return line[:k + len(kind)] + f"{t} {v}" + rest
    return line


def main() -> None:
    src = open(sys.argv[1], encoding="latin-1").read()
    out = "\n".join([line_of(line) for line in src.split("\n")])
    f = open(sys.argv[2], "w", encoding="latin-1")
    f.write(out)
    f.close()


if __name__ == "__main__":
    main()
