"""Diagnostics component of the self-hosting Pystachy compiler."""
from __future__ import annotations
import sys
from src.pystachy_compiler.names import RENAMED, unspec


SRC = "<input>"
# the files of the program's modules: a node of FILES[k] has line k * LINES + its line in the file
LINES = 10000000
FILES: list[str] = []
# how deeply source may nest: CPython's tokenizer allows 200 open brackets and 99 indentation
# levels; past MAXNEST levels of nested expressions or elif branches (a ** or lambda counts twice)
# Pystachy rejects the program, below the depths where CPython's parser and compiler give up, and
# so that neither compiler runs out of stack
MAXNEST = 5000
TOODEEP = f"source too complex: nested more than {MAXNEST} levels deep"
# CPython's parser gives up past 6,000 levels of its rules (MemoryError), some 34 of them below a
# statement's expression: Parser.deeper() counts its own levels and the rules CPython goes through
# besides (Parser.extra), as measured, to stop where CPython does or a few levels before
CPYSTACK = 5960
MODDUNDERS = "__file__ __doc__ __spec__ __loader__ __package__ __builtins__"  # (which CPython's modules have)
# the encoding the compiler reads source files and writes IR in, so that a str holds their bytes,
# one character each: Latin-1 under CPython; in Pystachy (where len("\xe9") is 2), whose str holds
# bytes, UTF-8, which it reads and writes unchecked (a Latin-1 file's text would hold each byte
# from 0x80 on as two, its character's UTF-8)
RAW = "latin-1" if len("\xe9") == 1 else "utf-8"


# the files of the modules that compile typing.Any as a dynamic type (docs/dynamic-any.md), by
# their index in FILES: those whose lines before their first line of code hold DYNPRAGMA
DYNFILES: dict[int, bool] = {}
DYNPRAGMA = "# pystachy: dynamic-any"


def dynamic_pragma(src: str) -> bool:
    # does source src opt in: a comment line DYNPRAGMA (spaces around it allowed) among the
    # comment and blank lines it starts with (after a byte order mark)
    return leading_pragma(src, DYNPRAGMA)


def leading_pragma(src: str, pragma: str) -> bool:
    # is comment line pragma among the comment and blank lines source src starts with
    at = 3 if src.startswith(chr(239) + chr(187) + chr(191)) else 0
    while at < len(src):
        e = src.find("\n", at)
        ln = (src[at:] if e < 0 else src[at:e]).strip()
        if ln != "" and not ln.startswith("#"):
            return False
        if ln == pragma:
            return True
        at = len(src) if e < 0 else e + 1
    return False


def dynamic_file(k: int) -> bool:
    return k in DYNFILES


# the files of the modules whose ints promote past 64 bits, as CPython's do (docs/python-int.md),
# by their index in FILES: those whose lines before their first line of code hold INTPRAGMA
INTFILES: dict[int, bool] = {}
INTPRAGMA = "# pystachy: python-int"


def int_pragma(src: str) -> bool:
    return leading_pragma(src, INTPRAGMA)


def int_file(k: int) -> bool:
    return k in INTFILES


def dynamic_program() -> bool:
    # does a module of the program opt in, so that values may be dynamic (dyn)
    return len(DYNFILES) > 0


def int_lists() -> bool:
    # do the program's lists of ints hold promoting ints past 64 bits (docs/python-int.md): a module
    # opts in to them, and none to dynamic Any, whose lists of ints keep identities instead
    # (runtime.c's BIGIDS). Its modules then read a list's int through a test (Gen.list_value)
    return len(INTFILES) > 0 and len(DYNFILES) == 0


def shown(s: str) -> str:
    # a name as Python spells it: the "$" of a qualified name (heapq$heappush) between two
    # identifier characters is the "." of a module attribute; the main program's names are
    # its own (__main__$len, a def that shadows a builtin, is len), and a class template's
    # specializations its class's (Box-2 is Box)
    if len(RENAMED) > 0 and unspec(s) in RENAMED:
        s = unspec(s)[: unspec(s).rfind("$") + 1] + RENAMED[unspec(s)]
    s = unspec(s.replace("__main__$", ""))
    out: list[str] = []
    for i in range(len(s)):
        c = s[i]
        if c == "$" and i > 0 and i + 1 < len(s) and (s[i - 1].isalnum() or s[i - 1] == "_") and (s[i + 1].isalnum() or s[i + 1] == "_"):
            c = "."
        out.append(c)
    return "".join(out)


def where(line: int) -> str:
    # file:line of a node's line
    if line >= LINES:
        return f"{FILES[line // LINES]}:{line % LINES}"
    return f"{SRC}:{line}"


def fail(msg: str, line: int) -> None:
    print(f"{where(line)}: error: {shown(msg)}", file=sys.stderr)
    sys.exit(1)


class Rejoin(Exception):
    # a value that a location (a variable, a field, a function's result) does not take, the type
    # of which was inferred: Gen.newhints has the location's join, the union of both types, and
    # the driver compiles the program again with it, as if annotated (see Gen.join_hint)
    pass


# ---------------------------------------------------------------- lexer
