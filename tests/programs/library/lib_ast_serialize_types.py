# ast_serialize.parse_type_string(), the parser of string annotations (forward references) that
# mypy's native parser calls: the length and CRC-32 of each type's bytes for cache versions 0, 2
# and 5 (lib/ast_serialize/ here, ast_serialize 0.13.1's Rust extension in CPython).
import binascii

from ast_serialize import parse_type_string

CASES = [
    "int", "List[int]", "Dict[str, int]", "int | None", "None", "a.b.C", "Callable[[int], str]",
    "Tuple[()]", "Tuple[int, ...]", "Literal['a', 1, -2, True, None, b'x']", "1 + 2", "", " ",
    "x y", "(int)", "'int'", "List['int']", "*Ts", "Unpack[Ts]", "f(x)", "f(x, y=1)", "lambda: 1",
    "[int, str]", "{'a': int, 'b': 'str'}", "int | str | bytes", "Optional[\"Foo\"]",
    "é", "List[é]", "x.y[z]", "3.5", "-3", "+3", "--3", "~3", "not x", "a if b else c",
    "...", "Annotated[int, Arg(int, 'x')]", "Callable[[Arg(int, 'x'), DefaultArg(str)], None]",
    "Callable[[VarArg(int), KwArg(str)], None]", "type[int]", "x[1:2]", "int  # comment",
    "int\nstr", "f'x'", "18446744073709551616", "Literal[18446744073709551615]", "Literal[0x10]",
    "Literal[1_000]", "x[*Ts]", "x[int,]", "(int, str)", "int, str", "a.b()",
]
for text in CASES:
    out = []
    for cv in (0, 2, 5):
        t = parse_type_string(text, (10, 4, 12, 30), cv)
        out.append(str(len(t)) + ":" + str(binascii.crc32(t)))
    print(repr(text), " ".join(out))
