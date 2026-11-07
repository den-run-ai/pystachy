"""Lower a bounded, immutable ctypes declaration block to the ordinary C FFI."""
from __future__ import annotations

from src.pystachy_compiler.analysis import scope_names, sole_binding
from src.pystachy_compiler.diagnostics import fail
from src.pystachy_compiler.lexer import Lexer
from src.pystachy_compiler.parser import Parser
from src.pystachy_compiler.syntax import Node, mk


# C widths are the existing FFI's LP64 contract. Other ctypes objects are not
# guessed: an unsupported declaration must fail before a foreign call is emitted.
SCALARS: dict[str, str] = {
    "c_int": "c_int", "c_int32": "c_int", "c_uint": "c_uint", "c_uint32": "c_uint",
    "c_int64": "c_int64", "c_longlong": "c_int64", "c_long": "c_int64", "c_ssize_t": "c_int64",
    "c_float": "c_float", "c_double": "float", "c_char_p": "bytes", "c_void_p": "pointer",
}
MARKERS: list[str] = ["CDLL", "POINTER"] + [x for x in SCALARS if x != "c_void_p"]


def reject(n: Node, message: str) -> None:
    fail("ctypes declarations: " + message, n.line)


def parsed(source: str, line: int) -> list[Node]:
    return Parser(Lexer(source, line).file()).module().kids


def dotted(n: Node) -> str:
    if n.kind == "name":
        return n.s
    if n.kind == "attr":
        base = dotted(n.kids[0])
        return base + "." + n.s if base != "" else ""
    return ""


def ctypes_import(n: Node) -> bool:
    return n.kind == "import" and n.s in ("", "from") and any([
        a.kind == "alias" and len(a.kids) == 2 and a.kids[1].s == "ctypes" for a in n.kids
    ])


def uses_prefix(n: Node, prefix: str) -> bool:
    return n.s.startswith(prefix) or any([uses_prefix(k, prefix) for k in n.kids])


def ctype(n: Node, aliases: dict[str, str], result: bool) -> str:
    if result and n.kind == "None":
        return "void"
    name = aliases.get(dotted(n), "")
    if name in SCALARS:
        return SCALARS[name]
    if not result and n.kind == "call" and len(n.kids) == 2 and aliases.get(dotted(n.kids[0]), "") == "POINTER" and aliases.get(dotted(n.kids[1]), "") == "c_void_p":
        return "outpointer"
    reject(n, "unsupported C type; use supported scalars or POINTER(c_void_p) arguments")
    return ""


class Prototype:
    def __init__(self, library: str, symbol: str, generated: str, at: int, line: int):
        self.library = library
        self.symbol = symbol
        self.generated = generated
        self.at = at
        self.line = line
        self.args: list[str] = []
        self.has_args = False
        self.ret = ""

    def declarations(self, prefix: str) -> list[Node]:
        raw = prefix + "_ffi"
        support = prefix + "_support"
        integer = support + "._Int"
        floating = support + "._Float"
        binary = support + "._Bytes"
        params: list[str] = []
        wrapper: list[str] = []
        values: list[str] = []
        for i in range(len(self.args)):
            typ = self.args[i]
            name = "a" + str(i)
            native = binary if typ == "bytes" else raw + ".c_void_p" if typ == "pointer" else prefix + "_list[" + raw + ".c_int64]" if typ == "outpointer" else floating if typ == "float" else raw + "." + typ
            convert = "_signed32" if typ == "c_int" else "_unsigned32" if typ == "c_uint" else "_address" if typ == "pointer" else "_borrow" if typ == "outpointer" else "_floating" if typ in ("float", "c_float") else "_integer"
            value = name if typ == "bytes" else support + "." + convert + "(" + name + ")"
            params.append(name + ": " + native)
            # Specialize conversions on the actual argument type. The support
            # helpers check the accepted ctypes types without first boxing every
            # scalar into a union. Unannotated parameters specialize even in a
            # caller module that opts into dynamic Any.
            wrapper.append(name + ": " + binary if typ == "bytes" else name)
            values.append(value)
        typ = self.ret
        native_ret = "None" if typ == "void" else binary if typ == "bytes" else raw + ".c_void_p" if typ == "pointer" else floating if typ == "float" else raw + "." + typ
        public_ret = "None" if typ == "void" else binary if typ == "bytes" else integer + " | None" if typ == "pointer" else floating if typ in ("float", "c_float") else integer
        source = "@" + raw + ".extern('', '')\ndef " + self.generated + "_raw(" + ", ".join(params) + ") -> " + native_ret + ": ...\n"
        source += "def " + self.generated + "(" + ", ".join(wrapper) + ") -> " + public_ret + ":\n"
        call = self.generated + "_raw(" + ", ".join(values) + ")"
        if typ == "pointer":
            source += "    return " + support + "._pointer_value(" + call + ")\n"
        else:
            source += "    " + ("" if typ == "void" else "return ") + call + "\n"
        out = parsed(source, self.line)
        # User library/symbol text is data in the AST, never parsed as source.
        deco = out[0].kids[3].kids[0]
        deco.kids[1].s = self.library
        deco.kids[2].s = self.symbol
        return out


def rewrite(n: Node, libraries: dict[str, str], prototypes: dict[str, Prototype], aliases: dict[str, str], support: str) -> None:
    if n.kind == "import":
        # Declaration-only names disappear with their checked uses; the support
        # module contains real cells/helpers, not fake ctypes type objects.
        if n.s == "from":
            n.kids = [a for a in n.kids if not (a.kind == "alias" and len(a.kids) == 2 and a.kids[1].s == "ctypes" and a.kids[0].s[7:] in MARKERS)]
        return
    if n.kind == "def":
        for k in n.kids[:2] + n.kids[3:]:
            rewrite(k, libraries, prototypes, aliases, support)
        local = scope_names(n)
        visible = {k: libraries[k] for k in libraries if k not in local}
        imported = {k: aliases[k] for k in aliases if k.split(".")[0] not in local}
        rewrite(n.kids[2], visible, prototypes, imported, support)
        return
    if n.kind in ("class", "subclass", "lambda", "listcomp", "setcomp", "dictcomp"):
        # These scopes have distinct binding rules. Keep them out of this first
        # declaration lowering rather than accidentally capture a shadowed name.
        for lib in libraries:
            if mentions(n, lib):
                reject(n, "library calls in classes, lambdas and comprehensions are not supported")
        for k in n.kids:
            rewrite(k, {}, prototypes, aliases, support)
        return
    if n.kind == "call":
        name = dotted(n.kids[0])
        if n.kids[0].kind == "attr" and n.kids[0].kids[0].kind == "name" and n.kids[0].kids[0].s in libraries:
            if name not in prototypes:
                reject(n, "every foreign function needs explicit argtypes and restype")
            p = prototypes[name]
            if len(n.kids) - 1 != len(p.args) or any([a.kind in ("kw", "starred", "dstar") for a in n.kids[1:]]):
                reject(n, "foreign calls require exactly the declared positional arguments")
            n.kids[0] = mk("name", p.generated, n.line, [])
            for i in range(len(p.args)):
                argument = n.kids[i + 1]
                if p.args[i] == "outpointer" and argument.kind == "call" and len(argument.kids) == 2 and argument.kids[1].kind not in ("kw", "starred", "dstar") and aliases.get(dotted(argument.kids[0]), "") == "byref":
                    # Only the temporary wrapper disappears. The typed helper still
                    # evaluates/checks the cell here, before subsequent arguments;
                    # borrowing its storage stays in the foreign call's wrapper.
                    at = argument.kids[0].line
                    argument.kids[0] = mk("attr", "_byref_cell", at, [mk("name", support, at, [])])
                rewrite(argument, libraries, prototypes, aliases, support)
            return
    name = dotted(n)
    if name in aliases and aliases[name] in MARKERS:
        reject(n, "CDLL and C type descriptors are only supported in the module declaration block")
    if n.kind == "name" and n.s in libraries:
        reject(n, "libraries and foreign function objects cannot escape or be rebound")
    for k in n.kids:
        rewrite(k, libraries, prototypes, aliases, support)


def mentions(n: Node, name: str) -> bool:
    return (n.kind == "name" and n.s == name) or any([mentions(k, name) for k in n.kids])


def lower_ctypes(body: Node) -> None:
    aliases: dict[str, str] = {}
    imported_at: dict[str, int] = {}
    for i in range(len(body.kids)):
        st = body.kids[i]
        if not ctypes_import(st):
            continue
        for a in st.kids:
            if a.kind != "alias" or len(a.kids) != 2 or a.kids[1].s != "ctypes":
                continue
            if not sole_binding(body.kids, i, a.s):
                reject(a, "ctypes imports must have a single stable binding")
            if st.s == "from":
                aliases[a.s] = a.kids[0].s[7:]
                imported_at[a.s] = i
            else:
                for name in MARKERS + ["c_void_p", "byref", "string_at"]:
                    aliases[a.s + "." + name] = name
                    imported_at[a.s + "." + name] = i
    if len(aliases) == 0:
        return
    prefix = "_pys_ctypes"
    while uses_prefix(body, prefix):
        prefix += "_"
    libraries: dict[str, str] = {}
    prototypes: dict[str, Prototype] = {}
    skip: dict[int, bool] = {}
    opens: dict[int, Node] = {}
    first = -1
    closed = False
    pending = ""
    for i in range(len(body.kids)):
        st = body.kids[i]
        if pending != "" and st.kind in ("import", "def", "class", "subclass"):
            reject(st, "complete each argtypes/restype pair before any other declaration or execution")
        if st.kind == "assign" and len(st.kids) == 2:
            dest, value = st.kids
            if value.kind == "call" and aliases.get(dotted(value.kids[0]), "") == "CDLL":
                if imported_at[dotted(value.kids[0])] >= i:
                    reject(st, "import ctypes before declaring a library")
                if pending != "":
                    reject(st, "complete each argtypes/restype pair before any other declaration or execution")
                if closed:
                    reject(st, "CDLL and prototypes must precede executable code and function definitions")
                if dest.kind != "name" or not sole_binding(body.kids, i, dest.s):
                    reject(st, "assign CDLL to one fresh module name")
                if len(value.kids) != 2 or value.kids[1].kind not in ("str", "None"):
                    reject(value, "CDLL takes one literal library name or None, without loader options")
                lib = value.kids[1].s if value.kids[1].kind == "str" else ""
                if "\0" in lib:
                    reject(value, "library name contains a NUL")
                libraries[dest.s] = lib
                opens[i] = mk("expr", "", st.line, [mk("call", "", st.line, [
                    mk("attr", "load_library", st.line, [mk("name", prefix + "_ffi", st.line, [])]), mk("str", lib, st.line, [])
                ])])
                first = i if first < 0 else first
                continue
            if dest.kind == "attr" and dest.s in ("argtypes", "restype") and dest.kids[0].kind == "attr" and dest.kids[0].kids[0].kind == "name" and dest.kids[0].kids[0].s in libraries:
                if closed:
                    reject(st, "prototypes are immutable and must precede executable code and function definitions")
                key = dotted(dest.kids[0])
                if dest.kids[0].s.startswith("_"):
                    reject(st, "private CDLL attributes are not foreign symbol declarations")
                if pending != "" and pending != key:
                    reject(st, "complete each argtypes/restype pair before any other declaration or execution")
                if key not in prototypes:
                    prototypes[key] = Prototype(libraries[dest.kids[0].kids[0].s], dest.kids[0].s, prefix + "_fn" + str(len(prototypes)), i, st.line)
                p = prototypes[key]
                visible = {name: aliases[name] for name in aliases if imported_at[name] < i}
                if dest.s == "argtypes":
                    if p.has_args or value.kind not in ("list", "tuple"):
                        reject(st, "argtypes must be assigned once as a literal list or tuple")
                    p.args = [ctype(a, visible, False) for a in value.kids]
                    p.has_args = True
                else:
                    if p.ret != "":
                        reject(st, "restype must be assigned once")
                    p.ret = ctype(value, visible, True)
                pending = "" if p.has_args and p.ret != "" else key
                skip[i] = True
                continue
        if st.kind != "import" and st.kind != "pass" and not (st.kind == "expr" and len(st.kids) == 1 and st.kids[0].kind == "str"):
            closed = True
    for key in prototypes:
        p = prototypes[key]
        if not p.has_args or p.ret == "":
            reject(body.kids[p.at], "every foreign function needs explicit argtypes and restype")
    out: list[Node] = []
    for i in range(len(body.kids)):
        st = body.kids[i]
        if i == first:
            imports = "import ffi as " + prefix + "_ffi\nimport ctypes as " + prefix + "_support\n"
            imports += "from typing import List as " + prefix + "_list\n"
            out += parsed(imports, st.line)
        if i in opens:
            out.append(opens[i])
        elif i in skip:
            for key in prototypes:
                if prototypes[key].at == i:
                    out += prototypes[key].declarations(prefix)
        else:
            # A later byref import must not lose its unbound-name lookup. Earlier
            # function bodies conservatively keep their ordinary wrappers too.
            visible = {name: aliases[name] for name in aliases if aliases[name] != "byref" or imported_at[name] < i}
            rewrite(st, libraries, prototypes, visible, prefix + "_support")
            if st.kind != "import" or len(st.kids) > 0:
                out.append(st)
    body.kids = out
