# ast_serialize.parse() of invalid sources: the syntax errors (line, column, message) of the
# lexer and parser, the recovered partial tree's length and CRC-32, and the errors the serializer
# adds (lib/ast_serialize/ here, ast_serialize 0.13.1's Rust extension in CPython).
import binascii

from ast_serialize import parse, parse_type_string

SOURCES = [
    "def f(:\n    pass\n",
    "x = (1, 2\ny = 3\n",
    "if x\n    pass\n",
    "class C:\npass\n",
    "  x = 1\n",
    "if x:\n        a = 1\n    b = 2\n",
    "x = 'abc\n",
    "x = '''abc\n",
    "x = f'{a'\ny = 1\n",
    "x = f'{a!x}' f'{b!}' f'{c' f'}'\n",
    "x = f'{lambda: 1}'\n",
    "x = 1 +\n",
    "x = [1, 2,, 3]\n",
    "f(a=1, b)\nf(**a, *b)\nf(x for x in y, 1)\n",
    "del 1\n(a, b) += 1\n1 = 2\nx: int, y = 1\n",
    "def f(a=1, b, *, **c): pass\ndef g(*, a, *b): pass\ndef h(/, a): pass\n",
    "try:\n    pass\nx = 1\n",
    "match x:\n    case 1 + 1: pass\n    case {**a, **b}: pass\n    case C(x=1, 2): pass\n",
    "x = 0b2 + 0o9 + 09 + 1__0 + 0x\n",
    "x = $\ny = ?\nz = `\n",
    "async x = 1\n@d\nx = 1\n",
    "from import x\nfrom . import (a, *)\nimport\n",
    "with (a as b, c\n    pass\n",
    "x = b'\u00e9' + '\\N{NOT A NAME}' + '\\x4' + '\\u12'\n",
    "x = '\\N{TANGUT IDEOGRAPH-17000}'\ny = '\\N{KEYCAP NUMBER SIGN}'\nz = '\\N{CJK COMPATIBILITY IDEOGRAPH-0F900}'\n",
    "x = (" * 3 + "\n",
    "lambda x: (yield)\nyield = 1\n",
    "x = {**a: 1, b: **c}\ny = [*a for a in b]\nz = {**a for a in b}\n",
    "global\nnonlocal\ndel\n",
    "def f[](): pass\ntype X[] = 1\nclass C[T,,]: pass\n",
    "x = 1 if y\nz = a if b else\n",
    "if x:\n    pass\nelif:\n    pass\nelse y:\n    pass\n",
    "\\\nx = 1\n\\",
    "x = " + "(" * 220 + "1" + ")" * 220 + "\n",
]
for i, src in enumerate(SOURCES):
    for cv in (0, 5):
        r = parse("e.py", src, False, (3, 12), "linux", None, None, cv)
        print(i, cv, len(r[0]), binascii.crc32(r[0]), len(r[3]), binascii.crc32(r[3]))
        for e in r[1]:
            print("  ", e["line"], e["column"], e["blocker"], e["message"])
for text in ["List[", "a b", "(", "x[]", "1 +", "'", "lambda: (yield)", "def"]:
    t = parse_type_string(text, (3, 4, 3, 9), 5)
    print(repr(text), len(t), binascii.crc32(t))
for path in ["/nonexistent/x.py", "/"]:
    try:
        parse(path)
    except ValueError as e:
        print("ValueError", e)
