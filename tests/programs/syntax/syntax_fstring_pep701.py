# PEP 701 (Python 3.12) f-strings: a replacement field's expression is code, where strings may
# reuse the f-string's quote and f-strings nest, and backslashes, comments and newlines may stand
import sys

d = {"key": 1, "k'q": 2, 'a"b': 3}
u = {"é": "ü"}
x = 5
w = 6
xs = ["a", "b", "c"]

# the f-string's own quote, in each kind of f-string
print(f"{d["key"]}|{d["k'q"]}|{d['a"b']}")
print(f'{d['key']}|{d['k\'q']}|{d["a\"b"]}')
print(f"""{d["""key"""]}|{d["key"] + d["""k'q"""]}""")
print(f'''{d['key']}|{d['''a"b''']}''')
print(rf"{d["key"]}|\d{x}")
print(f"{"a" "b" 'c'}|{"yes" if x else "no"}|{"" or "empty"}")
print(f"{", ".join(xs)}|{"-".join([s.upper() for s in xs])}|{", ".join(f"{k}={v!r}" for k, v in d.items())}")
print(f"{u["é"]}|{"é" * 2}|{"ü" + "€"}|{"ü"!r}|{"€"!a}")
print(f"{sys.stdout.write("abc")}")


# the forms of CPython 3.13's traceback.py and turtle.py
def _safe_string(value: ValueError, what: str, func: str) -> str:
    return f"<{what} {value!r}>"


e = ValueError("v")
call_args = ["x", "y"]
print(f'Ignored error getting __notes__: {_safe_string(e, '__notes__', "repr")}', f'({', '.join(call_args)})')

# nested f-strings with the same quotes
print(f"{f"{x}"}|{f"{f"{f"{x + 1}"}"}"}|{f"{f'{f"{x}"}'}"}")
print(f"{f"{"inner"}" + f'{"quote"}'}|{f"{x:{f"{w}"}}"}")
print(f"{f"""{f'''{x}'''}"""}|{f"{x}" f"{w}" "!"}")
deep = f"{f"{f"{f"{f"{f"{f"{f"{f"{f"{x}"}"}"}"}"}"}"}"}"}"
print(deep, len(deep))

# backslashes and escapes in a field's expression
print(f"{'\n'.join(xs)}")
print(f"{"\t".join(xs)!r}|{'\\'}|{'\x41\u00e9'}|{r'\d+'}")
print(rf"{'\n'!r}|{r'\n'!r}|\n")
print(f"\\{x}|\\\\{x}|{x}\\|{"\"q\""}|{'\'q\''}")
print(rf"\{x}|\}}|\{{")

# a field over lines, with comments, in a single-quoted f-string
print(f"{
    x  # the value
    + 1  # plus one, a # in a comment and a quote: " '
}|{d[
    "key"
]}|{x # a comment
=}|{x # c
!r:>4}")
print(f'{", ".join([
    "a",  # first
    "b",
])}')
print(f"{x \
+ 1}")

# format specs: nested fields with strings, quotes as fill characters, escapes
print(f"{x:{"*"}^{w}}|{x:{'0'}>{w}}|{"abc":{"<"}{w}}|{x:'>4}|{x:\x3e4}|")
print(f"{x!r:{"^"}{w}}|{d["key"]:>{d["k'q"]}}|{3.14159:.{d["k'q"]}f}")
print(f"{x:{w}}}}|{{{x}}}|{{}}|{ {x}!r}|{ {"a": x}["a"] }")
print(f"{x:{{'>'}.pop()}3}|{{\x41}}|{x}}}\t|{{{"\u00e9"}")

# self-documenting fields: their text, then repr unless a conversion or spec is given
print(f"{d["key"]=}|{"q"=}|{x = }|{x=!s}|{"q"=:}|{"q"=:>4}|{"q"=:>{w}}|{x=:{''}}|")
print(f"{"a" + 'b'=}|{f"{x}"=}|{len("ab") * 2 = }")

# evaluation order, left to right and inside out
log: list[str] = []


def note(s: str) -> str:
    log.append(s)
    return s


print(f"{note("a")}{f"{note("b")}{note("c")}"}{note("d"):{note(">3")}}{note("f")!r}")
print(log)


# in functions, methods, closures and classes
def greet(name: str) -> str:
    return f"{"hello"} {f"{name!r}"}"


class Box:
    tag = f"{"box"}"

    def __init__(self, v: dict[str, int]):
        self.v = v

    def show(self) -> str:
        return f"{self.tag}[{", ".join(f"{k}:{self.v[k]}" for k in sorted(self.v))}]"


def outer() -> str:
    pre = "<"

    def inner(s: str) -> str:
        return f"{pre}{s.replace("a", "@")}{">"}"
    return inner("banana")


print(greet("Ann"), Box({"b": 2, "a": 1}).show(), Box.tag, outer())


# a template (compiled for each argument type) and a lambda
def show(v):
    return f"{v!r:{"^"}{len(f"{v}") + 4}}|{f"{v}" * 2}"


wrap = lambda s: f"<{s.replace("a", "\\")}>"
print(show(12), show("ab"), show(1.5), wrap("banana"))
try:
    print(f"{d["missing"]}")
except KeyError as e:
    print("KeyError", f"{e!r}")
try:
    print(f"{x:{"bad"}}")
except ValueError as e:
    print("ValueError", f"{str(e)}")
