# ast_serialize.parse(), mypy's native parser front end (lib/ast_serialize/ here, ast_serialize
# 0.13.1's Rust extension in CPython): the length and CRC-32 of the serialized tree and imports of
# sources covering the statements, expressions, f-strings, patterns, type parameters, type
# comments, reachability and body skipping, with the errors, ignores and extra data; then this
# file, which parse() reads.
import binascii

from ast_serialize import parse

SOURCES = [
    "import os\nx: int = 1  # type: ignore[misc]\ndef f(a, b=2):\n    return a + b\n",
    "from . import x\nfrom ..a.b import (c as d, e,)\nfrom m import *\nimport a.b as c, d\n",
    "class C(B, metaclass=M):\n    '''doc'''\n    x: int\n    def m(self, *a, k=1, **kw) -> None:\n        self.y = [i for i in a if i]\n",
    "@d1\n@d2(1)\nasync def f[T, *Ts, **P](x: T, /, y: 'List[T]' = None) -> 'T | None':\n    await g()\n    async for a in b: pass\n    async with c as d: pass\n",
    "x = f'{a=} {b!r:>{w}} {{c}} {d:%Y}' rb'\\x00' u'u' 'a' 'b'\ny = t'{n} and {m!s:x}'\n",
    "match p:\n    case [1, *r] | (2, *r): pass\n    case {'k': v, **kw} if v: pass\n    case C(1, x=y) as z: pass\n    case -1 + 2j | None | True: pass\n    case a.b: pass\n    case _: pass\n",
    "type X[T: int = str] = list[T]\nlazy import a\nlazy from b import c\nlazy = 1\nmatch = 2\ntype = 3\n",
    "a = b = c\nd, *e = f\n[g, h] = i\nj += 1\nk @= 2\ndel l, m[0], n.o\nglobal p\nnonlocal q\nassert r, 's'\nraise T from U\n",
    "x = (lambda *a, b=1, **c: a)(1, *d, e=2, **f)\ny = [*a, *b]\nz = {**a, 'b': 1}\nw = {a for a in b}\nv = {k: v for k, v in w}\nu = (yield)\nt = a if b else c\ns = not a and b or c < d <= e != f is not g not in h\n",
    "r = 18446744073709551615 + 0x8000_0000_0000_0000 + 0o777 + 0b101 + 1_000 + 1e309 + 2.5j + .5\n",
    "q = x[1:2, ::3, ...]\np = (a := 1)\no = a.b.c(d)[e]\nn = -a ** -b // ~c % d @ e << f >> g & h ^ i | j\n",
    "try:\n    pass\nexcept (A, B) as e:\n    pass\nexcept C:\n    pass\nelse:\n    pass\nfinally:\n    pass\ntry:\n    pass\nexcept* D:\n    pass\n",
    "while x:\n    break\nelse:\n    continue\nfor a, b in c:\n    pass\nelse:\n    pass\nwith a, (b as c), d as (e, f): pass\nwith (a as b, c as d,): pass\n",
    "\u00e9 = '\u00fc'\n\u4e2d\u6587 = \"\u4e2d\" + x\ndef f\u00e9(a\u00e9: '\u00e9' = '\u00e9'):\n    return a\u00e9  # \u00e9\n@d\u00e9\nclass C\u00e9: pass\n",
    "\ufeffimport os\r\nx = (1,\r\n     2)\r\nif x:\r\n\tpass\r\ny = '''a\r\nb'''\r\n",
    "x = '\\ud800' '\\U0001f600' '\\N{BULLET}' '\\x41\\101\\n' r'\\ud800'\ny = b'\\x00\\xff\\'\"'\n"
    "z = '\\N{garay capital letter a}\\N{EGYPTIAN HIEROGLYPH-1346A}\\N{LF}\\N{cjk unified ideograph-04e00}'\n",
    "x = []  # type: List[int]\ndef f(a, b):\n    # type: (int, str) -> None\n    pass\ndef g(a,  # type: int\n      b):\n    # type: (...) -> int\n    pass\nclass C:\n    def m(self, x):  # type: (int) -> None\n        pass\n",
    "y = 1  # type: int  # type: ignore[a, b]\nz = 2  # type: ignore # type: ignore\nw = 3  # type: (\nv = 4  # mypy: ignore[x]\nu = 5  # type: ignore[bad code]\nt = 6  # type:\n",
    "# type: ignore[a]\nimport os\n",
    "# mypy: always-true=FOO, always_false=\"BAR,BAZ\"\n# mypy: ignore-errors\nif FOO:\n    import a\nelif BAR:\n    import b\nelse:\n    import c\ndef f():\n    x = 1\n",
    "import sys\nif sys.version_info >= (3, 10):\n    import a\nelif sys.version_info[0] == 2:\n    import b\nif sys.platform == 'win32':\n    import c\nif sys.platform.startswith('lin') and not TYPE_CHECKING:\n    import d\nif TYPE_CHECKING:\n    import e\nelse:\n    import f\nassert sys.platform != 'linux'\nimport g\n",
    "def f():\n    yield 1\ndef g():\n    import x\n    return 1\nclass C:\n    def m(self):\n        self.x = 1\n    def n(self):\n        y = 1\n    def o(self):\n        pass\n",
    "def __getattr__(name): ...\n",
    "x: 'List[int]'\ny: 'a.b | None'\nz: Literal[-1, +2, 'a', b'\\x00', True, None]\nw: Callable[[Arg(int, 'x')], None]\nv: {'a': int}\nu: f(x)\nt: (int, str)\ns: [int]\nr: *Ts\nq: 3.5\n",
    "",
    "x = 1",
]
OPTIONS: list[tuple[tuple[int, int], str, list[str], list[str], bool, int]] = [
    ((3, 13), "linux", [], [], False, 0),
    ((3, 13), "linux", [], [], True, 5),
    ((3, 8), "win32", ["DEBUG"], ["PY3"], False, 7),
]

for i, src in enumerate(SOURCES):
    for version, platform, always_true, always_false, skip, cv in OPTIONS:
        name = "m.pyi" if i == 22 else "m.py"
        r = parse(name, src, skip, version, platform, always_true, always_false, cv)
        print(i, len(r[0]), binascii.crc32(r[0]), len(r[3]), binascii.crc32(r[3]))
        for e in r[1]:
            print("  error", e["line"], e["column"], e["blocker"], e["message"])
        print("  ignores", r[2], r[4]["mypy_ignores"], r[4]["mypy_comments"])
        print("  data", r[4]["is_partial_package"], r[4]["uses_template_strings"], r[4]["source_hash"])
r = parse("m.py", b"x = 1\n")
print("bytes", len(r[0]), binascii.crc32(r[0]), r[4]["source_hash"])
r = parse("tests/programs/library/lib_ast_serialize_parse.py")  # (this file: the tests run from the root)
print("file", len(r[0]), binascii.crc32(r[0]), len(r[3]), binascii.crc32(r[3]), len(r[1]), r[4]["source_hash"])
