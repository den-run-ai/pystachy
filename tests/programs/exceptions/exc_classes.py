# Exception classes of the program: deriving from a builtin exception class or from another
# exception class of the program, with fields, __init__, __str__, __repr__ and other methods.


class AppError(Exception):
    """The base of this program's errors."""


class ConfigError(AppError):
    pass


class ParseError(ValueError):
    def __init__(self, msg: str, line: int):
        super().__init__(msg)
        self.line = line

    def where(self) -> str:
        return f"line {self.line}"


class DetailedError(ParseError):
    def __init__(self, msg: str, line: int, col: int):
        super().__init__(msg, line)
        self.col = col

    def __str__(self) -> str:
        return f"{super().__str__()} at {self.where()}:{self.col}"


class Coded(AppError):
    code: int = 7
    label: str = "coded"

    def __repr__(self) -> str:
        return f"<Coded {self.code} {super().__repr__()}>"


class Lookup(KeyError):
    pass


class Plain(Exception):
    def __init__(self, n: int):
        self.n = n


def parse(s: str, line: int) -> int:
    if s == "":
        raise ParseError("empty", line)
    if not s.isdigit():
        raise DetailedError(f"bad number {s!r}", line, 3)
    return int(s)


e0 = AppError()
e1 = AppError("one")
e2 = AppError("two", 2)
print(repr(e0), repr(e1), repr(e2))
print(f"[{e0}] [{e1}] [{e2}]")
print(str(ConfigError("cfg")), repr(ConfigError("cfg", [1, 2])))
c = Coded("x")
print(repr(c), str(c), c.code, c.label)
c.code = 9
print(repr(c))
print(repr(Lookup("k")), str(Lookup("k")), str(Lookup()), str(Lookup("a", "b")))
p = Plain(5)
print(repr(p), str(p), p.n)
for s in ["12", "", "x1"]:
    try:
        print(parse(s, 4))
    except DetailedError as e:
        print("detailed:", e, repr(e), e.line, e.col, e.where())
    except ParseError as e:
        print("parse:", e, repr(e), e.where())
try:
    parse("", 9)
except ValueError as e:
    print("as ValueError:", e, repr(e))
try:
    parse("zz", 1)
except AppError:
    print("not an AppError")
except Exception as e:
    print("as Exception:", e)
for err in [ConfigError("missing"), Coded(), AppError("base")]:
    try:
        raise err
    except ConfigError as e:
        print("config:", e)
    except AppError as e:
        print("app:", repr(e))
    except Exception as e:
        print("other:", repr(e))
try:
    raise ConfigError
except AppError as e:
    print("class raised:", repr(e))
try:
    raise Lookup("key")
except LookupError as e:
    print("lookup:", e)
errors: list[AppError] = [AppError("a"), ConfigError("b"), Coded("c")]
print(errors)
print([str(x) for x in errors])
try:
    raise RuntimeError("wrapped") from ConfigError("cause")
except RuntimeError as e:
    print(e)
try:
    try:
        raise ParseError("inner", 2)
    except ParseError:
        raise
except ValueError as e:
    print("reraised:", repr(e))
d = DetailedError("x", 1, 2)
pe: ParseError = d
print(pe, pe.where())
raise DetailedError("fatal", 10, 20)
