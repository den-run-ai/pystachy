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
declares as i64.
"""
import re
import sys

if __package__:
    from .wasi_abi import LIBC_WRAPPERS
else:
    from wasi_abi import LIBC_WRAPPERS

ADDRESS = "<{ptr, i32}>"
# LLVM quotes use hexadecimal escapes. Skip whole strings and comments so a
# Python literal containing "@memcmp(" retains its original bytes and length.
SYMBOL = re.compile(r'"[^"]*"|;.*|@([-a-zA-Z$._0-9]+)(?=\()')


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


def wasi_symbol(match: re.Match) -> str:
    name = match[1]
    return "@" + LIBC_WRAPPERS[name] if name in LIBC_WRAPPERS else match[0]


def line_of(line: str) -> str:
    if "@" in line and "(" in line:
        line = SYMBOL.sub(wasi_symbol, line)
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


# lower_module.py emits catch-all landing pads with one use of the unwind header.
# The Wasm target takes the same pointer from a catchpad. End the catch immediately
# so nested handlers and rethrows run in ordinary blocks. Preserve the original
# block label as the predecessor of its successors' phis.
LANDING = re.compile(
    r"^(?P<label>[-.\w]+):\n"
    r"  (?P<pair>%[-.\w]+) = landingpad \{ ptr, i32 \} catch ptr null(?:, !dbg !\d+)?\n"
    r"  (?P<exc>%[-.\w]+) = extractvalue \{ ptr, i32 \} (?P=pair), 0(?P<dbg>, !dbg !\d+)?$",
    re.MULTILINE,
)
UNWIND = re.compile(r"^(  (?:%[-.\w]+ = )?invoke .+ unwind label %)([-.\w]+)", re.MULTILINE)


def wasm_landing(match: re.Match) -> str:
    label = match["label"]
    dispatch = "pys.wasi.dispatch." + label
    pad = "pys.wasi.pad." + label
    return (f"{dispatch}:\n"
            f"  %{dispatch}.cs = catchswitch within none [label %{pad}] unwind to caller\n"
            f"{pad}:\n"
            f"  %{pad}.token = catchpad within %{dispatch}.cs [ptr null]\n"
            f"  {match['exc']} = call ptr @llvm.wasm.get.exception(token %{pad}.token){match['dbg'] or ''}\n"
            f"  catchret from %{pad}.token to label %{label}\n"
            f"{label}:")


# Catch only LLVM's Wasm exception tag. LLVM restores the linear stack pointer at
# each catch. A second unhandled raise while the runtime formats a user's __str__
# must reach the same reporter (runtime.c's xr.shown), after any inner handlers.
WASI_MAIN = """
declare i32 @__gxx_wasm_personality_v0(...)
declare ptr @llvm.wasm.get.exception(token)
declare void @pys_wasi_uncaught(ptr)
define i32 @__main_argc_argv(i32 %argc, ptr %argv) {
entry:
  %status = alloca i32
  br label %run
run:
  %exc = phi ptr [ null, %entry ], [ %caught, %run ]
  %caught = call ptr @pys.wasi.attempt(i32 %argc, ptr %argv, ptr %exc, ptr %status)
  %done = icmp eq ptr %caught, null
  br i1 %done, label %exit, label %run
exit:
  %result = load i32, ptr %status
  ret i32 %result
}
define internal ptr @pys.wasi.attempt(i32 %argc, ptr %argv, ptr %exc, ptr %status) noinline personality ptr @__gxx_wasm_personality_v0 {
entry:
  %first = icmp eq ptr %exc, null
  br i1 %first, label %main, label %report
main:
  %result = invoke i32 @pys.wasi.main(i32 %argc, ptr %argv) to label %done unwind label %dispatch
done:
  store i32 %result, ptr %status
  ret ptr null
report:
  invoke void @pys_wasi_uncaught(ptr %exc) to label %unreachable unwind label %dispatch
unreachable:
  unreachable
dispatch:
  %cs = catchswitch within none [label %catch] unwind to caller
catch:
  %pad = catchpad within %cs [ptr null]
  %caught = call ptr @llvm.wasm.get.exception(token %pad)
  catchret from %pad to label %escaped
escaped:
  ret ptr %caught
}
"""


def adapt_module(src: str) -> str:
    out = "\n".join(line_of(line) for line in src.split("\n"))
    if not re.search(r"^  call void @pys_eh_on\(\)", out, re.MULTILINE):
        return out
    if not re.search(r"^define i32 @__main_argc_argv\(", out, re.MULTILINE):
        raise ValueError("exception-enabled WASI input requires a command entry point")
    out = re.sub(r"^define i32 @__main_argc_argv\(", "define internal i32 @pys.wasi.main(", out, flags=re.MULTILINE)
    out = re.sub(r"^(define [^\n]+) personality ptr @pys_personality", r"\1 personality ptr @__gxx_wasm_personality_v0", out, flags=re.MULTILINE)
    out = UNWIND.sub(r"\1pys.wasi.dispatch.\2", out)
    out = LANDING.sub(wasm_landing, out)
    if re.search(r"^  %[-.\w]+ = landingpad ", out, re.MULTILINE):
        raise ValueError("unsupported WASI landing pad")
    return out + WASI_MAIN


def main() -> None:
    src = open(sys.argv[1], encoding="latin-1").read()
    out = adapt_module(src)
    f = open(sys.argv[2], "w", encoding="latin-1")
    f.write(out)
    f.close()


if __name__ == "__main__":
    main()
