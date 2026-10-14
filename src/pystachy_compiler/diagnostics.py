"""Diagnostics component of the self-hosting Pystachy compiler."""
from __future__ import annotations
import sys
from src.pystachy_compiler.names import unspec


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


def shown(s: str) -> str:
    # a name as Python spells it: the "$" of a qualified name (heapq$heappush) between two
    # identifier characters is the "." of a module attribute; the main program's names are
    # its own (__main__$len, a def that shadows a builtin, is len), and a class template's
    # specializations its class's (Box-2 is Box)
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


# ---------------------------------------------------------------- lexer
