"""Diagnostics component of the self-hosting Pystachy compiler."""
from __future__ import annotations
import sys
from src.pystachy_compiler.names import OBJECT, RENAMED, VIEWSHOW, unspec


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
# Checked optimization hints, never a promise to ignore observable identity.
IDINERT: dict[int, bool] = {}
IDPRAGMA = "# pystachy: identity-inert"
# the files of the modules that hold no dynamic value (docs/dynamic-any.md#static-modules): those
# whose lines before their first line of code hold STATICPRAGMA. An expression that is an Any
# value there, or a value boxed as one, is a compile error (Gen.static_value, dyn_box)
STATICFILES: dict[int, bool] = {}
STATICPRAGMA = "# pystachy: static"
STATICBOTH = "'# pystachy: static' and '# pystachy: dynamic-any' cannot both apply to a module: static rejects the Any values that dynamic-any makes"


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


def static_file(k: int) -> bool:
    return k in STATICFILES


# the files of the modules whose ints promote past 64 bits, as CPython's do (docs/python-int.md),
# by their index in FILES: those whose lines before their first line of code hold INTPRAGMA
INTFILES: dict[int, bool] = {}
INTPRAGMA = "# pystachy: python-int"


def int_pragma(src: str) -> bool:
    return leading_pragma(src, INTPRAGMA)


def int_file(k: int) -> bool:
    return k in INTFILES


# the lines of lib/'s definitions whose ints promote as those of a module that opts in, where a
# module of the program does (specs.INT_HELPERS, Gen.int_policy): the first and the last of each,
# in the numbering of all files' lines (LINES)
INTSPANS: list[list[int]] = []


def int_span(line: int) -> bool:
    for s in INTSPANS:
        if s[0] <= line and line <= s[1]:
            return True
    return False


def dynamic_program() -> bool:
    # does a module of the program opt in, so that values may be dynamic (dyn)
    return len(DYNFILES) > 0


def int_program() -> bool:
    # does a module of the program opt in to promoting ints (docs/python-int.md): its generators
    # then hold the pointer of one they yield or return (specs.GENVALP)
    return len(INTFILES) > 0


def int_lists() -> bool:
    # do the program's lists of ints hold promoting ints past 64 bits (docs/python-int.md), and the
    # values of its dicts of ints and the elements of its sets of ints: a module opts in. Numeric
    # identity companions can retain a wide integer's box as well as its value. The program's
    # modules then read such an int through a test (Gen.list_value, big_dict_value, big_set_value)
    return len(INTFILES) > 0


def shown(s: str) -> str:
    # a name as Python spells it: the "$" of a qualified name (heapq$heappush) between two
    # identifier characters is the "." of a module attribute; the main program's names are
    # its own (__main__$len, a def that shadows a builtin, is len), and a class template's
    # specializations its class's (Box-2 is Box)
    if len(RENAMED) > 0 and unspec(s) in RENAMED:
        s = unspec(s)[: unspec(s).rfind("$") + 1] + RENAMED[unspec(s)]
    s = s.replace("__main__$", "").replace(OBJECT, "object")  # (object's stored type and its views: names.py)
    for view in VIEWSHOW:
        s = s.replace(view, VIEWSHOW[view])
    s = unspec(s)
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


class Diagnostic:
    # A terminal compiler diagnostic, before its file/line are flattened into text.
    # Codes are deliberately coarse: PYS0001 is an ordinary compiler rejection;
    # PYS9000 is an existing explicitly marked internal error, not a Python exception.
    # Context contains the compiler's specialization notes, outermost first. These
    # are notes, not invented instruction spans or separately parsed call locations.
    def __init__(self, msg: str, line: int, context: list[str]):
        self.code: str = "PYS9000" if msg.startswith("internal error:") else "PYS0001"
        self.severity: str = "error"
        self.phase: str = PHASE
        self.message: str = shown(msg)
        self.file: str = FILES[line // LINES] if line >= LINES else SRC
        self.line: int = line % LINES if line >= LINES else line
        self.context: list[str] = [shown(note) for note in context]


# Opt-in observation for isolated hosted tooling. Normal CLI behavior stays text;
# capture does not recover from errors or make process-global compilation concurrent.
# The observer owns clearing CAPTURED and setting PHASE at actual stage boundaries.
CAPTURE = False
PHASE = "compile"
CAPTURED: list[Diagnostic] = []
# a compilation that keeps the except clauses of optional imports that it would drop before #1504
# (Loader.keeps): an error there is no diagnostic, as driver.compile_program then compiles the
# program again without them, which reports what it finds
TRIAL = False


class Untried(Exception):
    # fail() while TRIAL
    pass


def fail(msg: str, line: int, context: list[str] | None = None) -> None:
    if TRIAL:
        raise Untried()
    if CAPTURE:
        CAPTURED.append(Diagnostic(msg, line, [] if context is None else context))
    print(f"{where(line)}: error: {shown(msg)}", file=sys.stderr)
    sys.exit(1)


class Rejoin(Exception):
    # a value that a location (a variable, a field, a function's result) does not take, the type
    # of which was inferred: Gen.newhints has the location's join, the union of both types, and
    # the driver compiles the program again with it, as if annotated (see Gen.join_hint)
    pass


class NeedHierarchy(Rejoin):
    # A previously excluded fixed-layout class is used. Fresh compilation admits its
    # hierarchy so earlier dispatch sites include the newly reachable receiver.
    pass


class NeedSliceEH(Rejoin):
    # A dynamic slice needs to catch an iterator callback's TypeError, or a lookup the
    # AttributeError that a class's __getattr__ answers or raises (reflection.py). Start
    # a fresh compile with exception handling before lowering any function.
    pass


class NeedHandlers(Rejoin):
    # The statements after an optional import's imports may raise a subclass of ImportError
    # (Loader.keep_site, #1504): a fresh load keeps their except clauses at run time.
    pass


class TupleBoxes(Rejoin):
    # An isinstance(x, tuple) test of an Any value was compiled for a tuple's box alone, and the
    # program boxes objects of a NamedTuple class, which pass that test and have another layout
    # (#1581): the program is compiled again with the test that accepts them, which leaves x an
    # Any value (Gen.ntboxes)
    pass


class ClassBoxes(Rejoin):
    # A module that opts in to dynamic Any read its classes as typed class objects (type[C]) and
    # the program did not compile so, or stored an Any value where a class object's type was
    # inferred: the program is compiled from the start with those modules' classes read as the
    # class boxes they always were, Any values (class_values.py's class_value_static)
    pass


# ---------------------------------------------------------------- lexer
