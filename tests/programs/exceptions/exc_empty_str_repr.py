# repr() of a builtin exception made of one str shows the str's repr, also an empty one:
# ValueError('') (where ValueError() has no argument), from a constant and from a str read at run
# time, for the general case, OSError, the SyntaxError family, SystemExit and KeyError, raised and
# caught too; classes of the program keep theirs


class E(Exception):
    pass


class F(ValueError):
    def __init__(self, m: str):
        super().__init__(m)


def made(text: str) -> list[str]:
    return [repr(ValueError(text)), repr(OSError(text)), repr(SyntaxError(text)), repr(StopIteration(text)),
            repr(SystemExit(text)), repr(KeyError(text)), repr(IndentationError(text)), repr(E(text)), repr(F(text))]


s = ""
print(repr(ValueError("")), repr(ValueError(s)), repr(KeyError("")), repr(E("")), repr(F("")))
print(repr(OSError("")), repr(SyntaxError("")), repr(RuntimeError(s)), repr(StopIteration("")))
print(repr(ValueError()), repr(E()), repr(ValueError("x")), repr(SystemExit("")), repr(SyntaxError()))
for text in ["", "x", "it's"]:
    print(made(text))
    print([str(ValueError(text)), str(SyntaxError(text)), str(KeyError(text))])
try:
    raise ValueError("")
except ValueError as e:
    print(repr(e), str(e) == "")
try:
    raise RuntimeError(s)
except RuntimeError as e:
    print(repr(e), repr(str(e)))
print(repr(Exception("", "")), repr(UnicodeError("")), f"{ValueError('')!r}")
