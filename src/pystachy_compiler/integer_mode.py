"""Opt-in, deliberately bounded frontend for the promoting integer prototype."""
from __future__ import annotations
from src.pystachy_compiler.analysis import targets
from src.pystachy_compiler.diagnostics import dynamic_pragma, fail
from src.pystachy_compiler.lexer import Lexer
from src.pystachy_compiler.parser import Parser
from src.pystachy_compiler.syntax import Node, mk, names_in
from src.pystachy_compiler.utils import int_fits


INT_NAMES: dict[str, str] = {"int": "integer", "pow": "power", "range": "integer_range",
                              "bin": "binary", "oct": "octal", "hex": "hexadecimal", "sum": "integer_sum"}
INT_PREFIX = "_pys_promoting_"


def integer_pragma(src: str) -> bool:
    # Only a leading comment opts in; imports have independent module contracts.
    at = 3 if src.startswith(chr(239) + chr(187) + chr(191)) else 0
    while at < len(src):
        end = src.find("\n", at)
        line = (src[at:] if end < 0 else src[at:end]).strip()
        if line != "" and not line.startswith("#"):
            return False
        if line == "# pystachy: python-int":
            return True
        at = len(src) if end < 0 else end + 1
    return False


def integer_walk(n: Node, annotation: bool = False) -> Node:
    if n.s.startswith(INT_PREFIX):
        fail("reserved name in python-int prototype", n.line)
    bindings: dict[str, bool] = {}
    targets(n, bindings)
    if n.kind == "listcomp" and len(n.kids) >= 3 and n.kids[1].kind != "compfor":
        names: list[str] = []
        names_in(n.kids[1], names)
        for name in names:
            bindings[name] = True
    if n.kind in ["def", "class", "subclass", "param", "starparam", "kwparam", "alias", "except", "typealias"]:
        bindings[n.s] = True
    if n.kind == "del":
        for child in n.kids:
            if child.kind == "name":
                bindings[child.s] = True
    for name in bindings:
        if name in INT_NAMES or name == "isinstance" or name.startswith(INT_PREFIX):
            fail("python-int prototype does not support rebinding builtin " + name, n.line)
    if n.kind == "import":
        # Qualified builtin aliases and native modules need a boundary audit first.
        for a in n.kids:
            if a.s in INT_NAMES or a.s in ["*", "isinstance"] or a.s.startswith(INT_PREFIX) or (len(a.kids) > 0 and a.kids[0].s.startswith("builtins")):
                fail("python-int prototype does not support builtin import aliases", n.line)
        return n
    if n.kind == "call" and len(n.kids) == 3 and n.kids[0].kind == "name" and n.kids[0].s == "isinstance" and n.kids[2].kind == "name" and n.kids[2].s == "int":
        return mk("call", "", n.line, [mk("name", INT_PREFIX + "is_integer", n.line, []), integer_walk(n.kids[1])])
    if n.kind == "call" and n.kids[0].kind == "name" and n.kids[0].s == "int":
        for arg in n.kids[1:]:
            if arg.kind == "kw" and arg.s != "base":
                fail("python-int prototype: int() only accepts the base keyword", arg.line)
        explicit_base = len(n.kids) > 2 or any(arg.kind == "kw" and arg.s == "base" for arg in n.kids[1:])
        helper = "convert_base" if explicit_base else "convert"
        return mk("call", "", n.line, [mk("name", INT_PREFIX + helper, n.line, [])] + [integer_walk(x) for x in n.kids[1:]])
    if n.kind == "match":
        fail("python-int prototype does not support match patterns", n.line)
    if annotation and n.kind == "str":
        parsed = Parser(Lexer("_value: " + n.s + "\n", n.line).file()).module()
        return integer_walk(parsed.kids[0].kids[1], True)
    if n.kind == "name" and n.s == "int" and not annotation:
        fail("python-int prototype supports int only in annotations, constructors and isinstance(x, int)", n.line)
    if n.kind == "name" and n.s in INT_NAMES:
        return mk("name", INT_PREFIX + n.s, n.line, [])
    if n.kind == "int" and not annotation:
        radix = n.s.startswith("0x") or n.s.startswith("0o") or n.s.startswith("0b")
        value = mk("int", n.s, n.line, []) if not radix and int_fits(n.s) else mk("str", n.s, n.line, [])
        args = [mk("name", INT_PREFIX + "int", n.line, []), value]
        if radix:
            args.append(mk("int", "0", n.line, []))
        return mk("call", "", n.line, args)
    kids: list[Node] = []
    for i in range(len(n.kids)):
        ann = annotation or (n.kind == "annassign" and i == 1) or (n.kind == "def" and i == 1) or (n.kind in ["param", "starparam", "kwparam"] and i == 0)
        kids.append(integer_walk(n.kids[i], ann))
    n.kids = kids
    return n


def integer_parse(src: str, line: int) -> Node:
    enabled = integer_pragma(src)
    if enabled and dynamic_pragma(src):
        fail("python-int prototype cannot yet be combined with dynamic-any", line)
    tokens = Lexer(src, line).file()
    parser = Parser(tokens)
    parser.exact_ints = enabled
    body = parser.module()
    if not enabled:
        return body
    body = integer_walk(body)
    imports = "from _pystachy_int import " + ", ".join([INT_NAMES[k] + " as " + INT_PREFIX + k for k in INT_NAMES]) + ", convert as " + INT_PREFIX + "convert, is_integer as " + INT_PREFIX + "is_integer, convert_base as " + INT_PREFIX + "convert_base\n"
    nodes = Parser(Lexer(imports, line).file()).module().kids
    # Keep the docstring as the first statement.
    pos = 1 if len(body.kids) > 0 and body.kids[0].kind == "expr" and body.kids[0].kids[0].kind == "str" else 0
    body.kids = body.kids[:pos] + nodes + body.kids[pos:]
    return body
